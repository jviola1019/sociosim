"""Characterization guard: locks the event-stream hash for fixed configs.

This is a refactor safety net (not new behavior): behavior-preserving changes
(e.g. extracting magic numbers into BehaviorParams) MUST keep these hashes
identical. Intentional behavior changes (e.g. adding the organic-conversion
channel) update these constants in the same commit, with a note in CHANGELOG.md.
"""

from socio_sim.config import RunConfig
from socio_sim.engine import Simulation

# Baselines re-locked after policy decisions began logging
# human_review_required and EU user flags became classifier-threshold
# independent review intake. Earlier intentional regens are in git history.
# Run-to-run determinism and replay still hold (verified).
BASELINE_STREAM_HASHES = {
    "EU": "b8b91f494a4b2346fba26a744179b243b4fba1feeb9a7457a10c9b0169fec377",
    "US": "7e0b7284bc522ff72d20d46bb72e844fdfb5efde2a76a4ddf1f657279d6ebcae",
    "CN": "1fdc00a27c39e2436d232080639d0f8752df536d0739c4fcd034edaf85bc0138",
}


def test_stream_hashes_match_locked_baselines():
    for jur, expected in BASELINE_STREAM_HASHES.items():
        got = Simulation(RunConfig.test(jurisdictions=(jur,))).run().log.stream_hash()
        assert got == expected, (
            f"determinism regression for {jur}: behavior changed unexpectedly.\n"
            f"  expected {expected}\n  got      {got}\n"
            "If this change was intentional, update BASELINE_STREAM_HASHES and "
            "note it in CHANGELOG.md.")
