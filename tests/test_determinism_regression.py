"""Characterization guard: locks the event-stream hash for fixed configs.

This is a refactor safety net (not new behavior): behavior-preserving changes
(e.g. extracting magic numbers into BehaviorParams) MUST keep these hashes
identical. Intentional behavior changes (e.g. adding the organic-conversion
channel) update these constants in the same commit, with a note in CHANGELOG.md.
"""

from socio_sim.config import RunConfig
from socio_sim.engine import Simulation

# Baselines re-locked after hard-capping campaign budgets in second-price ad
# auctions. Earlier intentional regens (trusted flagger priority, feed perf
# redesign, P2 baseline channel, eligible-opportunity ITT ad lift) are in git
# history. Run-to-run determinism and replay still hold (verified).
BASELINE_STREAM_HASHES = {
    "EU": "f807f603c269061c40e69728b8f08e87f0332886ad0ad1897f55ab8991f66e3a",
    "US": "4bff3361da19db41a0cfce56850b03c674be9501b8120c07ed51488382a6e3af",
    "CN": "08ae413920a3c7f1ce3b0d2a66c76c06240658ae1bf92bb57cfeb5c77fa82561",
}


def test_stream_hashes_match_locked_baselines():
    for jur, expected in BASELINE_STREAM_HASHES.items():
        got = Simulation(RunConfig.test(jurisdictions=(jur,))).run().log.stream_hash()
        assert got == expected, (
            f"determinism regression for {jur}: behavior changed unexpectedly.\n"
            f"  expected {expected}\n  got      {got}\n"
            "If this change was intentional, update BASELINE_STREAM_HASHES and "
            "note it in CHANGELOG.md.")
