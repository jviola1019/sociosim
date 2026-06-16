"""Deterministic seed tree: one independent numpy Generator per (module, replicate).

No module ever shares a Generator with another; this is what makes per-module
changes non-contaminating and replays bit-identical.
"""

from __future__ import annotations

import hashlib

import numpy as np


class SeedTree:
    def __init__(self, root_seed: int):
        self.root_seed = int(root_seed)

    def generator(self, module: str, replicate: int = 0) -> np.random.Generator:
        # Stable 64-bit key from the module name (Python's hash() is salted
        # per-process, so a cryptographic digest is required for replays).
        key = int.from_bytes(
            hashlib.blake2s(module.encode(), digest_size=8).digest(), "big"
        )
        seq = np.random.SeedSequence([self.root_seed, int(replicate), key])
        return np.random.default_rng(seq)
