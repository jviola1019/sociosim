"""Replay verification: rerun from a manifest and compare event-stream hashes."""

from __future__ import annotations

from typing import Callable

from socio_sim.logs.events import EventLog
from socio_sim.logs.manifest import Manifest


def verify(manifest: Manifest, original_stream_hash: str,
           run_fn: Callable[[dict], EventLog]) -> tuple[bool, str]:
    """Rerun via `run_fn(manifest.config)` and compare stream hashes.

    Returns (ok, summary). `run_fn` must rebuild the simulation purely from
    the manifest's config — any hidden state breaks replay and is a bug.
    """
    replayed = run_fn(manifest.config)
    new_hash = replayed.stream_hash()
    if new_hash == original_stream_hash:
        return True, f"replay ok: {new_hash}"
    n_old, n_new = "?", len(replayed.events)
    return False, (
        f"replay mismatch: original {original_stream_hash[:12]}… vs "
        f"replayed {new_hash[:12]}… (replayed events: {n_new}, original: {n_old})"
    )
