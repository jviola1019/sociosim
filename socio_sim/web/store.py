"""Run registry — a lightweight SQLite database of completed runs.

Gives the web console persistent history: every finished run is recorded so it
can be reopened, compared, or exported later. Stdlib sqlite3 only (no install).
One row per run; the full JSON result payload is stored alongside summary
columns used for the history list and comparisons.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

DEFAULT_DB = Path("out") / "sociosim.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id            TEXT PRIMARY KEY,
    created_at    REAL NOT NULL,
    label         TEXT,
    config_hash   TEXT NOT NULL,
    stream_hash   TEXT NOT NULL,
    profile       TEXT,
    jurisdictions TEXT,
    content_mode  TEXT,
    n_agents      INTEGER,
    n_ticks       INTEGER,
    n_events      INTEGER,
    elapsed_s     REAL,
    implausibility REAL,
    replay_ok     INTEGER,
    harmful_rate  REAL,
    mod_precision REAL,
    mod_recall    REAL,
    payload       TEXT NOT NULL
);
"""


class RunStore:
    """Thread-safe SQLite store of completed runs (single-writer lock)."""

    def __init__(self, path: str | Path = DEFAULT_DB):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._connect() as cx:
            cx.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        cx = sqlite3.connect(self.path, timeout=10)
        cx.row_factory = sqlite3.Row
        return cx

    def save(self, run_id: str, result: dict, label: str = "") -> dict:
        """Persist a finished run's result payload + summary columns."""
        s = result.get("summary", {})
        cfg = result.get("config", {})
        he = s.get("harmful_exposure", {})
        mod = s.get("moderation", {})
        row = {
            "id": run_id,
            "created_at": time.time(),
            "label": label or self._auto_label(cfg, result),
            "config_hash": result["manifest"]["config_hash"],
            "stream_hash": result["manifest"]["stream_hash"],
            "profile": cfg.get("profile") or _infer_profile(cfg),
            "jurisdictions": ",".join(cfg.get("jurisdictions", [])),
            "content_mode": result.get("content_mode", "template"),
            "n_agents": cfg.get("n_agents"),
            "n_ticks": cfg.get("n_ticks"),
            "n_events": result.get("n_events"),
            "elapsed_s": result.get("elapsed_s"),
            "implausibility": result.get("implausibility"),
            # C-01: NULL=skipped, 0=checked+failed, 1=checked+ok
            "replay_ok": (
                None if not (result.get("replay") or {}).get("checked")
                else int(bool((result.get("replay") or {}).get("ok")))
            ),
            "harmful_rate": he.get("rate"),
            "mod_precision": mod.get("precision"),
            "mod_recall": mod.get("recall"),
            "payload": json.dumps(result),
        }
        cols = ",".join(row)
        ph = ",".join("?" for _ in row)
        with self._lock, self._connect() as cx:
            cx.execute(f"INSERT OR REPLACE INTO runs ({cols}) VALUES ({ph})",
                       list(row.values()))
        return self.meta(run_id)

    @staticmethod
    def _auto_label(cfg: dict, result: dict) -> str:
        juris = "+".join(cfg.get("jurisdictions", []) or ["?"])
        n = cfg.get("n_agents", "?")
        return f"{juris} · {n} agents · {result.get('content_mode', 'template')}"

    def list(self, limit: int = 100) -> list[dict]:
        with self._connect() as cx:
            rows = cx.execute(
                "SELECT id,created_at,label,profile,jurisdictions,content_mode,"
                "n_agents,n_ticks,n_events,elapsed_s,implausibility,replay_ok,"
                "harmful_rate,mod_precision,mod_recall "
                "FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def meta(self, run_id: str) -> dict | None:
        with self._connect() as cx:
            r = cx.execute(
                "SELECT id,created_at,label,profile,jurisdictions,content_mode,"
                "n_agents,n_ticks,n_events,elapsed_s,implausibility,replay_ok,"
                "harmful_rate,mod_precision,mod_recall "
                "FROM runs WHERE id=?", (run_id,)).fetchone()
        return dict(r) if r else None

    def payload(self, run_id: str) -> dict | None:
        with self._connect() as cx:
            r = cx.execute("SELECT payload FROM runs WHERE id=?",
                           (run_id,)).fetchone()
        return json.loads(r["payload"]) if r else None

    def delete(self, run_id: str) -> bool:
        with self._lock, self._connect() as cx:
            cur = cx.execute("DELETE FROM runs WHERE id=?", (run_id,))
        return cur.rowcount > 0

    def count(self) -> int:
        with self._connect() as cx:
            return cx.execute("SELECT COUNT(*) AS c FROM runs").fetchone()["c"]


def _infer_profile(cfg: dict) -> str:
    n = cfg.get("n_agents")
    return {200: "test", 1000: "quick", 10000: "standard"}.get(n, "custom")
