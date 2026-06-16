"""Characterization guard: locks the event-stream hash for fixed configs.

This is a refactor safety net (not new behavior): behavior-preserving changes
(e.g. extracting magic numbers into BehaviorParams) MUST keep these hashes
identical. Intentional behavior changes (e.g. adding the organic-conversion
channel) update these constants in the same commit, with a note in CHANGELOG.md.
"""

from socio_sim.config import RunConfig
from socio_sim.engine import Simulation

# Baselines re-locked after P2 (organic-baseline conversion channel added).
# That change was INTENTIONAL: it appends `organic_conversion` events at the
# start of each day; everything else is bit-identical. Pre-P2 hashes are kept
# in CHANGELOG / git history.
BASELINE_STREAM_HASHES = {
    "EU": "d80bd689de2632d513de8f84764bbf687275cbfec26dfeecd2a02ff514b23f61",
    "US": "25618a88624250c1c3fe85fcf640c52d1195ce7d8ad09b2a90fd9014535db724",
    "CN": "1e25d05e92c3ab2d6331a5443fe0a53053016ae5e2e9579ea7bab9173198b7df",
}


def test_stream_hashes_match_locked_baselines():
    for jur, expected in BASELINE_STREAM_HASHES.items():
        got = Simulation(RunConfig.test(jurisdictions=(jur,))).run().log.stream_hash()
        assert got == expected, (
            f"determinism regression for {jur}: behavior changed unexpectedly.\n"
            f"  expected {expected}\n  got      {got}\n"
            "If this change was intentional, update BASELINE_STREAM_HASHES and "
            "note it in CHANGELOG.md.")
