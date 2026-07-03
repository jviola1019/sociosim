"""Shared JSON response-cache trust logic for LLM content adapters
(LLMAdapter, ClaudeAdapter). Both adapters cache surface-text responses keyed
by prompt hash so a completed run replays bit-identically offline; this
module is the single place that decides whether a stored entry may be
trusted and served, so the two adapters cannot drift out of sync on this
safety-critical decision (they previously did: see AUDIT_LOG.md R-CLAUDE-P0).

Trust model (deliberately conservative -- this is a local single-user
research tool, not a defense against a filesystem-level adversary who can
recompute hashes; `record_hash` catches accidental corruption, stale
hand-edits, and naive tampering, not a sophisticated attacker with write
access who also updates the hash to match their forged content):

- A cache entry written by this module is a dict with `text`,
  `status` ("accepted" | "blocked"), `reason_codes`, and a `record_hash`
  binding all three together. Any entry whose `record_hash` doesn't match
  its own (text, status, reason_codes) has been altered since it was
  written and is discarded -- treated exactly like a cache miss, so the
  prompt is regenerated and freshly re-screened.
- A `status == "blocked"` entry is never served as content, regardless of
  its stored text: it means the LLM response failed the semantic guard and
  the adapter must fall back to template text. It is honoured (no remote
  call, no re-screening) only while its stored `guard_version` matches the
  current `BLOCKED_GUARD_VERSION`; a mismatch means the guard's rules
  changed since this prompt was screened, so it is treated as a miss and
  re-sent.
- Legacy entries (bare strings, or dicts without a `status` field) predate
  this schema and are trusted as accepted text -- they cannot describe a
  blocked result because that status didn't exist yet when they were
  written.
- A `status` value outside {"accepted", "blocked"} cannot have been written
  by this module and is treated as tampered/corrupt, not as an unknown-but-
  valid state.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import NamedTuple

from socio_sim.content.semantic_guard import semantic_hash

#: Bump to deliberately force re-evaluation of every previously blocked
#: prompt (e.g. after a semantic-guard rule change). See module docstring.
BLOCKED_GUARD_VERSION = 1

_KNOWN_STATUSES = {"accepted", "blocked"}


def record_hash(text: str, status: str, reason_codes: list[str]) -> str:
    """Integrity hash binding text+status+reason_codes together so none of
    the three can be altered independently without detection."""
    payload = json.dumps(
        {"text": text, "status": status, "reason_codes": sorted(reason_codes)},
        sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def make_entry(text: str, status: str, reason_codes: list[str],
               guard_version: int | None = None) -> dict:
    """Build a cache entry in the current schema, ready to store."""
    reason_list = list(reason_codes)
    entry = {
        "text": text,
        "semantic_hash": semantic_hash(text),
        "status": status,
        "reason_codes": reason_list,
    }
    if guard_version is not None:
        entry["guard_version"] = guard_version
    entry["record_hash"] = record_hash(text, status, reason_list)
    return entry


class CacheLookup(NamedTuple):
    hit: bool                  #: True => do not call the remote transport
    text: str | None           #: text to serve verbatim; None => use template
    degradation: str | None    #: reason to report via on_degradation, if any


def resolve(cached: object) -> CacheLookup:
    """Decide what a raw cache-dict value means for this request."""
    if cached is None:
        return CacheLookup(hit=False, text=None, degradation=None)

    if not isinstance(cached, dict):
        # Legacy bare-string entry: predates status/tampering fields, so it
        # was never screened under the current guard — treat as a miss so
        # the text is regenerated and freshly re-screened.
        return CacheLookup(hit=False, text=None, degradation=None)

    text = cached.get("text")
    status = cached.get("status")
    reasons = cached.get("reason_codes") or []

    if status is not None and "record_hash" not in cached:
        # E-01 fix: any entry with a status field must have record_hash —
        # make_entry() always writes both. An entry with status but no hash
        # was hand-edited or field-deleted (naive tampering the module
        # docstring explicitly claims to catch). Treat as tampered/miss.
        return CacheLookup(
            hit=False, text=None,
            degradation="cache_tampered:status_without_record_hash; "
                        "entry discarded and regenerated")

    if "record_hash" in cached:
        expected = record_hash(text or "", status or "", reasons)
        if cached["record_hash"] != expected:
            return CacheLookup(
                hit=False, text=None,
                degradation="cache_tampered:record_hash_mismatch; "
                            "entry discarded and regenerated")

    if status is not None and status not in _KNOWN_STATUSES:
        return CacheLookup(
            hit=False, text=None,
            degradation=f"cache_tampered:unknown_status:{status!r}; "
                        "entry discarded and regenerated")

    if status == "blocked":
        if cached.get("guard_version") == BLOCKED_GUARD_VERSION:
            return CacheLookup(
                hit=True, text=None,
                degradation=f"semantic_mismatch:{','.join(reasons)}; "
                            "cached blocked result; template text used")
        # guard_version mismatch: deliberate invalidation, re-screen.
        return CacheLookup(hit=False, text=None, degradation=None)

    if status is None:
        # Legacy dict without a status field: never screened under the
        # current guard — treat as a miss and re-screen.
        return CacheLookup(hit=False, text=None, degradation=None)

    # status == "accepted".
    return CacheLookup(hit=True, text=text, degradation=None)


def load(path: Path, on_error=None) -> dict:
    """Load a cache file, failing safe (empty cache) on any corruption."""
    if not path.exists():
        return {}
    try:
        dat