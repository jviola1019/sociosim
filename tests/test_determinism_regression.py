"""Characterization guard: locks the event-stream hash for fixed configs.

This is a refactor safety net (not new behavior): behavior-preserving changes
(e.g. extracting magic numbers into BehaviorParams) MUST keep these hashes
identical. Intentional behavior changes (e.g. adding the organic-conversion
channel) update these constants in the same commit, with a note in CHANGELOG.md.
"""

from socio_sim.config import RunConfig
from socio_sim.engine import Simulation

# Baselines captured on branch feat/audit-p0-p1 (pre-refactor), 108 tests green.
BASELINE_STREAM_HASHES = {
    "EU": "a8a8b243e5958c1620d5e4ed0e9bee55c866c78d4459993c57eeca3bf848bc36",
    "US": "f7473dc24c1ff189045e807f7f1e8798ed2416a5bf43020ca8f2344edbd27190",
    "CN": "3f3c6f2bb509e64e69ea5f7cbf716a078932bc8e5c73d137afa9db785cb8cd14",
}


def test_stream_hashes_match_locked_baselines():
    for jur, expected in BASELINE_STREAM_HASHES.items():
        got = Simulation(RunConfig.test(jurisdictions=(jur,))).run().log.stream_hash()
        assert got == expected, (
            f"determinism regression for {jur}: behavior changed unexpectedly.\n"
            f"  expected {expected}\n  got      {got}\n"
            "If this change was intentional, update BASELINE_STREAM_HASHES and "
            "note it in CHANGELOG.md.")
