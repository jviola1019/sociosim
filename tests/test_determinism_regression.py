"""Characterization guard: locks the event-stream hash for fixed configs.

This is a refactor safety net (not new behavior): behavior-preserving changes
(e.g. extracting magic numbers into BehaviorParams) MUST keep these hashes
identical. Intentional behavior changes (e.g. adding the organic-conversion
channel) update these constants in the same commit, with a note in CHANGELOG.md.
"""

from socio_sim.config import RunConfig
from socio_sim.engine import Simulation

# Baselines re-locked after the feed hot-loop perf redesign. That change was
# INTENTIONAL: the exploration POOL is now sampled by oversampling recent_posts
# indices (O(k)) instead of materialising the full non-neighbour list, which
# shifts which exploration posts are drawn. Run-to-run determinism and replay
# still hold (verified). Earlier baselines (pre-perf, post-P2) are in git history.
BASELINE_STREAM_HASHES = {
    "EU": "b0c0dea275c792984cd291cfd7aab8b8ed0f21368ed80892b567b43337fdf268",
    "US": "2062cec93857e1bae1573dd67610c4f99c37d9d41fbea19ca0e26e2ec3ffa7fe",
    "CN": "e9c82551135456d8474f7f267adda987b2cbfe0885a55be2197bb12cfa8b2cae",
}


def test_stream_hashes_match_locked_baselines():
    for jur, expected in BASELINE_STREAM_HASHES.items():
        got = Simulation(RunConfig.test(jurisdictions=(jur,))).run().log.stream_hash()
        assert got == expected, (
            f"determinism regression for {jur}: behavior changed unexpectedly.\n"
            f"  expected {expected}\n  got      {got}\n"
            "If this change was intentional, update BASELINE_STREAM_HASHES and "
            "note it in CHANGELOG.md.")
