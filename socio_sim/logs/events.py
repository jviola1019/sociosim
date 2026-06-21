"""Append-only structured event log (Spec §3.8).

Events carry structured rationales and evidence fields only — never
chain-of-thought and never PII. The canonical stream hash is the replay
fingerprint: equal hashes == identical runs.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

#: Allowed event kinds. `degradation` = LLM-adapter fallback to templates.
#: Fail-closed POLICY-GAP escalations are logged as `moderation` events
#: (rule_id "POLICY-GAP"), not a separate kind. follow/unfollow/churn are emitted
#: only when the optional dynamic-graph rates are set (>0); the default graph is
#: static, so they are absent from default runs.
EVENT_KINDS = {
    "post",
    "impression",
    "engagement",
    "flag",
    "classify",
    "moderation",
    "notice",
    "appeal",
    "ad_auction",
    "ad_click",
    "ad_conversion",
    "organic_conversion",
    "llm_call",
    "degradation",
    "follow",
    "unfollow",
    "churn",
}


def _canonical(event: dict) -> str:
    return json.dumps(event, sort_keys=True, separators=(",", ":"))


class EventLog:
    """In-memory event list with optional append-only JSONL persistence."""

    def __init__(self, path: str | Path | None = None):
        self.events: list[dict] = []
        self._path = Path(path) if path else None
        self._fh = None
        if self._path:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = open(self._path, "a", encoding="utf-8")

    def append(self, tick: int, kind: str, actor_id: int, content_id: str | None,
               data: dict | None = None) -> dict:
        if kind not in EVENT_KINDS:
            raise ValueError(f"unknown event kind: {kind}")
        event = {
            "tick": int(tick),
            "kind": kind,
            "actor_id": int(actor_id),
            "content_id": content_id,
            "data": data or {},
        }
        self.events.append(event)
        if self._fh:
            self._fh.write(_canonical(event) + "\n")
        return event

    def flush(self):
        if self._fh:
            self._fh.flush()

    def close(self):
        if self._fh:
            self._fh.close()
            self._fh = None

    def stream_hash(self) -> str:
        h = hashlib.sha256()
        for e in self.events:
            h.update(_canonical(e).encode())
            h.update(b"\n")
        return h.hexdigest()

    def by_kind(self, kind: str) -> list[dict]:
        return [e for e in self.events if e["kind"] == kind]

    @classmethod
    def load(cls, path: str | Path) -> "EventLog":
        log = cls()
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    log.events.append(json.loads(line))
        return log
