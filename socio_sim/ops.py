"""Local data lifecycle for a single-user research tool (Phase 6).

Scope is deliberately small: `out/` run directories and the sqlite run
history are local, regenerable artifacts (determinism means any run can be
reproduced from its config + seed). No cloud storage, no scheduler, no
enterprise observability -- just retention, integrity, export, and a couple
of honest health signals.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

#: Warn when the filesystem holding out/ drops below this. A research run
#: writing events.jsonl into a full disk fails late and confusingly.
LOW_DISK_WARN_BYTES = 512 * 1024 * 1024   # technical_constant: 512 MB


@dataclass
class RunDir:
    path: Path
    mtime: float
    bytes: int

    @property
    def age_days(self) -> float:
        return (time.time() - self.mtime) / 86400.0


def scan_runs(out_dir: Path) -> list[RunDir]:
    """Every run directory under out/ (newest first). A run directory is one
    that holds a manifest.json.

    Three safety rules, each protecting against a real footgun:
    1. The out/ ROOT is never a run, even if a stray manifest.json sits
       there (`python run.py --out out` writes one). Without this, a
       retention policy would nominate the entire out/ tree -- including
       the run-history database -- for deletion.
    2. A run directory never contains another run directory: nested
       candidates are dropped, so a parent can't be deleted out from under
       a child (and sizes aren't double-counted).
    3. Only real directories are considered (symlinks are skipped rather
       than followed out of the tree).
    """
    out_dir = Path(out_dir).resolve()
    if not out_dir.is_dir():
        return []
    candidates: list[Path] = []
    for manifest in out_dir.rglob("manifest.json"):
        d = manifest.parent.resolve()
        if d == out_dir:                       # rule 1
            continue
        if d.is_symlink():                     # rule 3
            continue
        candidates.append(d)
    runs: list[RunDir] = []
    for d in candidates:
        if any(other != d and other in d.parents for other in candidates):
            continue                           # rule 2: nested inside another run
        size = sum(f.stat().st_size for f in d.rglob("*")
                   if f.is_file() and not f.is_symlink())
        mtime = (d / "manifest.json").stat().st_mtime
        runs.append(RunDir(path=d, mtime=mtime, bytes=size))
    return sorted(runs, key=lambda r: r.mtime, reverse=True)


def select_for_deletion(runs: list[RunDir], keep_last: int | None = None,
                        max_age_days: float | None = None) -> list[RunDir]:
    """Runs failing the retention policy. With no policy set, nothing is
    selected -- retention is opt-in, never a surprise deletion."""
    if keep_last is None and max_age_days is None:
        return []
    doomed: list[RunDir] = []
    for i, run in enumerate(runs):          # runs are newest-first
        too_many = keep_last is not None and i >= keep_last
        too_old = max_age_days is not None and run.age_days > max_age_days
        if too_many or too_old:
            doomed.append(run)
    return doomed


def integrity_manifest(run: RunDir) -> dict:
    """SHA-256 of every file in a run directory, so an archived copy can be
    checked later. Not a signature: it detects corruption, not forgery."""
    files = {}
    for f in sorted(run.path.rglob("*")):
        if f.is_file():
            files[str(f.relative_to(run.path)).replace("\\", "/")] = (
                hashlib.sha256(f.read_bytes()).hexdigest())
    return {"run": run.path.name, "n_files": len(files),
            "bytes": run.bytes, "sha256": files}


def export_all(out_dir: Path, dest: Path) -> dict:
    """Copy every run directory to `dest` with an integrity manifest each.
    Plain directory copy: no archive format to get stuck behind."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    exported = []
    for run in scan_runs(out_dir):
        target = dest / run.path.name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(run.path, target)
        (target / "integrity.json").write_text(
            json.dumps(integrity_manifest(run), indent=2, sort_keys=True),
            encoding="utf-8")
        exported.append(run.path.name)
    return {"exported": exported, "dest": str(dest)}


def verify_export(archived: Path) -> list[str]:
    """Re-check an exported run against its integrity.json. Returns the list
    of problems (empty = intact)."""
    archived = Path(archived)
    manifest_path = archived / "integrity.json"
    if not manifest_path.is_file():
        return [f"{archived.name}: no integrity.json"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    problems = []
    for rel, expected in manifest["sha256"].items():
        f = archived / rel
        if not f.is_file():
            problems.append(f"{rel}: missing")
        elif hashlib.sha256(f.read_bytes()).hexdigest() != expected:
            problems.append(f"{rel}: sha256 mismatch")
    return problems


def disk_status(path: Path) -> dict:
    """Free space on the filesystem holding `path`, with a low-disk flag."""
    target = Path(path)
    while not target.exists() and target != target.parent:
        target = target.parent
    usage = shutil.disk_usage(target)
    return {"free_bytes": usage.free, "total_bytes": usage.total,
            "low_disk": usage.free < LOW_DISK_WARN_BYTES,
            "threshold_bytes": LOW_DISK_WARN_BYTES}


def db_health(db_path: Path) -> dict:
    """sqlite integrity check + size. Corruption is reported, never
    'repaired' silently -- see docs/RELEASE.md for recovery guidance."""
    db_path = Path(db_path)
    if not db_path.is_file():
        return {"present": False, "ok": True, "bytes": 0,
                "detail": "no run history database yet"}
    try:
        with sqlite3.connect(db_path) as cx:
            detail = cx.execute("PRAGMA integrity_check").fetchone()[0]
        return {"present": True, "ok": detail == "ok",
                "bytes": db_path.stat().st_size, "detail": detail}
    except sqlite3.DatabaseError as exc:
        return {"present": True, "ok": False,
                "bytes": db_path.stat().st_size,
                "detail": f"unreadable: {exc!r}; see docs/RELEASE.md "
                          "(corrupted-database recovery)"}


def prune_orphan_history(db_path: Path, out_root: Path) -> dict:
    """Drop run-history rows whose out/ directory no longer exists.

    Deleting run directories alone leaves the sqlite history pointing at
    runs you can no longer open -- and VACUUM then reclaims nothing,
    because the rows are still there. Retention has to cover both.
    """
    db_path = Path(db_path)
    if not db_path.is_file():
        return {"pruned": 0, "reason": "no database"}
    pruned = []
    with sqlite3.connect(db_path) as cx:
        cx.row_factory = sqlite3.Row
        for row in cx.execute("SELECT id, payload FROM runs").fetchall():
            try:
                out_dir = (json.loads(row["payload"]) or {}).get("out_dir")
            except (json.JSONDecodeError, TypeError):
                out_dir = None
            if out_dir and not (Path(out_dir).exists()
                                or (Path(out_root).parent / out_dir).exists()):
                pruned.append(row["id"])
        for run_id in pruned:
            cx.execute("DELETE FROM runs WHERE id = ?", (run_id,))
    return {"pruned": len(pruned)}


def vacuum_db(db_path: Path) -> dict:
    """Reclaim space after deletions. No-op when the DB is absent."""
    db_path = Path(db_path)
    if not db_path.is_file():
        return {"vacuumed": False, "reason": "no database"}
    before = db_path.stat().st_size
    with sqlite3.connect(db_path) as cx:
        cx.execute("VACUUM")
    return {"vacuumed": True, "bytes_before": before,
            "bytes_after": db_path.stat().st_size}
