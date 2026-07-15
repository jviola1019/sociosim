"""Aggregate-fit regression: the history-matched profile stays below the
history-matching cutoff and explains any out-of-band component. This is an
aggregate-fit diagnostic on synthetic targets, not a calibration claim."""

from socio_sim.config import RunConfig
from socio_sim.pipeline import run_and_analyze


def test_aggregate_matched_profile_is_within_cutoff_and_replays():
    """History-matched against the SOURCE-VERIFIED targets, the profile
    scores below the 3-sigma cutoff, and the STRUCTURAL graph/temporal
    aggregates (a social-network model's job to reproduce) land in band.
    The residual is the ad/appeal terms, whose real sources are
    incompatible surfaces and are small-count in one run."""
    a = run_and_analyze(
        RunConfig.aggregate_matched_prototype(jurisdictions=("EU",)),
        verify_replay=True)
    assert a.implausibility < 3.0, a.implausibility
    assert a.replay["ok"]
    structural = ("degree_tail_exponent", "clustering", "diurnal_peak_hour",
                  "posts_per_agent_day")
    for name in structural:
        spec = a.targets[name]
        o = a.observed.get(name)
        assert o is not None and o == o, name
        z = abs(o - spec["value"]) / spec["tolerance"]
        assert z <= 1.0001, (name, o, spec, z)
    # The remaining out-of-band term is one of the incompatible-source
    # ad/appeal metrics, never a structural one.
    assert a.implausibility_dominant_metric in ("ad_ctr", "appeal_grant_rate")


def test_config_model_graph_reaches_the_verified_tail_and_clusters():
    """The cm generator's whole point: a realized degree tail near 2.3
    (which preferential attachment cannot reach) AND real clustering."""
    import numpy as np

    from socio_sim.graph.generators import make_graph
    from socio_sim.graph.metrics import average_clustering
    from socio_sim.rng import SeedTree
    from socio_sim.validation.targets import hill_exponent
    g = make_graph("cm", 1000, SeedTree(1).generator("graph", 0),
                   gamma=2.05, min_degree=2, triangle_swaps=15.0)
    deg = np.array([d for _, d in g.degree()], dtype=float)
    # Heavy tail near ~2.3 (seed-dependent realization), far below the
    # gamma->3 that preferential attachment (BA/PLC) asymptotes to.
    assert 2.0 < hill_exponent(deg) < 2.6, hill_exponent(deg)
    assert average_clustering(g) > 0.15              # genuine clustering


def test_aggregate_matched_profile_beats_unmatched_baseline():
    matched = run_and_analyze(
        RunConfig.aggregate_matched_prototype(jurisdictions=("EU",)),
        verify_replay=False).implausibility
    base = run_and_analyze(RunConfig.quick(jurisdictions=("EU",)),
                           verify_replay=False).implausibility
    assert matched < base  # history matching reduced target distance


def test_legacy_calibrated_factory_still_aliases_the_matched_profile():
    # RunConfig.calibrated is kept only as a migration alias; it must stay
    # behaviourally identical to aggregate_matched_prototype.
    legacy = RunConfig.calibrated(jurisdictions=("EU",))
    honest = RunConfig.aggregate_matched_prototype(jurisdictions=("EU",))
    assert legacy.config_hash() == honest.config_hash()


def test_plc_graph_has_higher_clustering_than_ba():
    from socio_sim.graph.generators import make_graph
    from socio_sim.graph.metrics import average_clustering
    from socio_sim.rng import SeedTree
    ba = make_graph("ba", 500, SeedTree(1).generator("graph", 0), m=5)
    plc = make_graph("plc", 500, SeedTree(1).generator("graph", 0), m=5, p=0.7)
    assert average_clustering(plc) > average_clustering(ba) + 0.1


def test_cm_graph_is_deterministic_from_the_seed():
    from socio_sim.graph.generators import make_graph
    from socio_sim.rng import SeedTree
    a = make_graph("cm", 400, SeedTree(3).generator("graph", 0), gamma=2.1)
    b = make_graph("cm", 400, SeedTree(3).generator("graph", 0), gamma=2.1)
    assert sorted(a.edges()) == sorted(b.edges())
