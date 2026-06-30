"""Characterization guard: locks the event-stream hash for fixed configs.

This is a refactor safety net (not new behavior): behavior-preserving changes
(e.g. extracting magic numbers into BehaviorParams) MUST keep these hashes
identical. Intentional behavior changes (e.g. adding the organic-conversion
channel) update these constants in the same commit, with a note in CHANGELOG.md.
"""

from socio_sim.config import RunConfig
from socio_sim.engine import Simulation

# Baselines re-locked after adding explicit ad cohort timing metadata to
# opportunity events. Run-to-run determinism and replay still hold (verified).
BASELINE_STREAM_HASHES = {
    "EU": "23f5a3ade474e0bc2799908cb0362eb90ea7636a89173722fbf74c662daf98f2",
    "US": "ac2b0376acd056e3aea601f2ec3a5d15d6384f6677fc614d3c363544afcef879",
    "CN": "7c4c6f00e0b373211d2439bc6e616b1b824d614e3f68ac249e1fc811a4117dea",
}


def test_stream_hashes_match_locked_baselines():
    for jur, expected in BASELINE_STREAM_HASHES.items():
        got = Simulation(RunConfig.test(jurisdictions=(jur,))).run().log.stream_hash()
        assert got == expected, (
            f"determinism regression for {jur}: behavior changed unexpectedly.\n"
            f"  expected {expected}\n  got      {got}\n"
            "If this change was intentional, update BASELINE_STREAM_HASHES and "
            "note it in CHANGELOG.md.")
