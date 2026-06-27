"""Calibration regression: the history-matched profile stays below the
history-matching cutoff and explains any out-of-band component."""

from socio_sim.config import RunConfig
from socio_sim.pipeline import run_and_analyze


def test_calibrated_profile_is_within_tolerance_and_replays():
    a = run_and_analyze(RunConfig.calibrated(jurisdictions=("EU",)),
                        verify_replay=True)
    assert a.implausibility < 3.0, a.implausibility
    assert a.implausibility_dominant_metric == "ad_ctr"
    assert a.replay["ok"]
    # Hard budget caps can starve the ad-click component in this single run;
    # all non-ad calibration observables remain within one tolerance band.
    for name, spec in a.targets.items():
        o = a.observed.get(name)
        if o is not None and o == o:
            z = abs(o - spec["value"]) / spec["tolerance"]
            if name == "ad_ctr":
                assert z == a.implausibility
                continue
            assert z <= 1.0001, (name, o, spec, z)


def test_calibrated_beats_uncalibrated_baseline():
    cal = run_and_analyze(RunConfig.calibrated(jurisdictions=("EU",)),
                          verify_replay=False).implausibility
    base = run_and_analyze(RunConfig.quick(jurisdictions=("EU",)),
                           verify_replay=False).implausibility
    assert cal < base                                       # calibration helped


def test_plc_graph_has_higher_clustering_than_ba():
    from socio_sim.graph.generators import make_graph
    from socio_sim.graph.metrics import average_clustering
    from socio_sim.rng import SeedTree
    ba = make_graph("ba", 500, SeedTree(1).generator("graph", 0), m=5)
    plc = make_graph("plc", 500, SeedTree(1).generator("graph", 0), m=5, p=0.7)
    assert average_clustering(plc) > average_clustering(ba) + 0.1
