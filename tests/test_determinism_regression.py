"""Characterization guard: locks the event-stream hash for fixed configs.

This is a refactor safety net (not new behavior): behavior-preserving changes
(e.g. extracting magic numbers into BehaviorParams) MUST keep these hashes
identical. Intentional behavior changes (e.g. adding the organic-conversion
channel) update these constants in the same commit, with a note in CHANGELOG.md.
"""

from socio_sim.config import RunConfig
from socio_sim.engine import Simulation

# Baselines re-locked after the DSA Art. 22 trusted-flagger priority review
# (trusted-flagger escalations get a shorter review deadline, shifting review
# timing). Earlier intentional regens (feed perf redesign, P2 baseline channel)
# are in git history. Run-to-run determinism and replay still hold (verified).
BASELINE_STREAM_HASHES = {
    "EU": "b50e70fb0831119e148bbf82d115a39ab8ac8933fbb1584471b5a36d3e4104d0",
    "US": "c3d3b6894d9e08fca6a62be07d16fec3f4871e5f85d4e3396549bfcd75827585",
    "CN": "7519aae688c9634d319c8a80ef2c3c532c569b2f7d833b06d3d7afb4f1c4b7b8",
}


def test_stream_hashes_match_locked_baselines():
    for jur, expected in BASELINE_STREAM_HASHES.items():
        got = Simulation(RunConfig.test(jurisdictions=(jur,))).run().log.stream_hash()
        assert got == expected, (
            f"determinism regression for {jur}: behavior changed unexpectedly.\n"
            f"  expected {expected}\n  got      {got}\n"
            "If this change was intentional, update BASELINE_STREAM_HASHES and "
            "note it in CHANGELOG.md.")
