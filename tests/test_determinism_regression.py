"""Characterization guard: locks the event-stream hash for fixed configs.

This is a refactor safety net (not new behavior): behavior-preserving changes
(e.g. extracting magic numbers into BehaviorParams) MUST keep these hashes
identical. Intentional behavior changes (e.g. adding the organic-conversion
channel) update these constants in the same commit, with a note in CHANGELOG.md.
"""

from socio_sim.config import RunConfig
from socio_sim.engine import Simulation

# Baselines re-locked after adding ad_opportunity audit events for eligible-
# opportunity ITT ad lift. Earlier intentional regens (trusted flagger priority,
# feed perf redesign, P2 baseline channel) are in git history. Run-to-run
# determinism and replay still hold (verified).
BASELINE_STREAM_HASHES = {
    "EU": "c4b47514eca0ec19a9ce64fa8db7bf32d7fe95efd24a87bedf46cdc027484da1",
    "US": "17385aee9b481b220d81091688828a859deb34def56cecf603173f8797e035af",
    "CN": "793de5c9103df65448272adb083c0808bc7c0d8f29ff4b09b58deaf8d77cfdeb",
}


def test_stream_hashes_match_locked_baselines():
    for jur, expected in BASELINE_STREAM_HASHES.items():
        got = Simulation(RunConfig.test(jurisdictions=(jur,))).run().log.stream_hash()
        assert got == expected, (
            f"determinism regression for {jur}: behavior changed unexpectedly.\n"
            f"  expected {expected}\n  got      {got}\n"
            "If this change was intentional, update BASELINE_STREAM_HASHES and "
            "note it in CHANGELOG.md.")
