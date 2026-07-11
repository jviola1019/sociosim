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
  `status` ("accepted" | "blocked"), `reason_codes`, `guard_version`, and a
  `record_hash` binding all four together. Any entry whose `record_hash`
  doesn't match its own fields has been altered since it was written and is
  discarded -- treated exactly like a cache miss, so the prompt is
  regenerated and freshly re-screened.
- A `status == "blocked"` entry is never served as content, regardless of
  its stored text: it means the LLM response failed the semantic guard and
  the adapter must fall back to template text. It is honoured (no remote
  call, no re-screening) only while its stored `guard_version` matches the
  current `BLOCKED_GUARD_VERSION`; a mismatch means the guard's rules
  changed since this prompt was screened, so it is treated as a miss and
  re-sent.
- A `status == "accepted"` entry is likewise served only while its stored
  `guard_version` matches `BLOCKED_GUARD_VERSION` (E-01): text accepted
  under an older, weaker guard must be re-screened after a guard change,
  not served forever. A missing/stale `guard_version` on an accepted entry
  is a plain miss (deliberate invalidation), not tampering.
- Legacy entries (bare strings, or dicts without a `status` field) were
  never screened under the current guard and are treated as cache misses:
  regenerated and freshly re-screened, never served as trusted text.
- A `status` value outside {"accepted", "blocked"} cannot have been written
  by this module and is treated as tampered/corrupt, not as an unknown-but-
  valid state.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import NamedTuple

#: Bump to deliberately force re-evaluation of every previously screened
#: prompt -- blocked AND accepted -- e.g. after a semantic-guard rule
#: change. See module docstring.
BLOCKED_GUARD_VERSION = 1

_KNOWN_STATUSES = {"accepted", "blocked"}


def record_hash(text: str, status: str, reason_codes: list[str],
                guard_version: int | None = None) -> str:
    """Integrity hash binding text+status+reason_codes+guard_version so none
    can be altered independently without detection. guard_version is omitted
    from the payload when None so hashes of entries written before
    guard-version stamping still verify (they then miss on the version
    check, which is a clean re-screen, not a false tamper report)."""
    fields: dict = {"text": text, "status": status,
                    "reason_codes": sorted(reason_codes)}
    if guard_version is not None:
        fields["guard_version"] = guard_version
    payload = json.dumps(fields, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def make_entry(text: str, status: str, reason_codes: list[str],
               guard_version: int | None = None) -> dict:
    """Build a cache entry in the current schema, ready to store.

    Every entry records the guard version it was screened under (E-01);
    callers that don't pass one get the current BLOCKED_GUARD_VERSION."""
    if guard_version is None:
        guard_version = BLOCKED_GUARD_VERSION
    reason_list = list(reason_codes)
    entry = {
        "text": text,
        "status": status,
        "reason_codes": reason_list,
        "guard_version": guard_version,
    }
    entry["record_hash"] = record_hash(text, status, reason_list, guard_version)
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
        # Recompute with the entry's own stored guard_version: entries that
        # predate guard-version stamping have no such field and verify under
        # the old formula; deleting or editing the field on a new entry
        # breaks the hash and reads as tampering (E-03).
        expected = record_hash(text or "", status or "", reasons,
                               cached.get("guard_version"))
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
    if cached.get("guard_version") != BLOCKED_GUARD_VERSION:
        # E-01: accepted under a different (or unknown) guard version --
        # deliberate invalidation, re-screen. Not tampering: the record
        # hash already verified above.
        return CacheLookup(hit=False, text=None, degradation=None)
    return CacheLookup(hit=True, text=text, degradation=None)


def load(path: Path, on_error=None) -> dict:
    """Load a cache file, failing safe (empty cache) on any corruption."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        if on_error is not None:
            on_error(f"cache file is corrupt ({exc!r}); starting with an "
                      "empty cache")
        return {}
    if not isinstance(data, dict):
        if on_error is not None:
            on_error(f"cache file is not a JSON object "
                     f"(got {type(data).__name__}); starting with an "
                     "empty cache")
        return {}
    return data


def save(path: Path, cache: dict) -> None:
    """Atomically persist the cache.

    Serialize to a temp file in the same directory, flush + fsync, then
    os.replace() over the target: a crash, interruption, or racing writer
    at any point leaves either the old complete file or the new complete
    file on disk -- never a truncated or interleaved mix. (record_hash
    detects accidental corruption after the fact; this layer prevents the
    save path from being the thing that corrupts it.)"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(cache, sort_keys=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent,
                                    prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def file_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()
