"""Preview vs Research (Monte Carlo) run modes wired into the pipeline."""

from socio_sim.config import RunConfig
from socio_sim.pipeline import run_and_analyze


def _cfg():
    # Boost harmful prevalence so moderation recall is finite in a small run.
    rates = dict(RunConfig.test().category_base_rates)
    rates.update({"misinfo": 0.15, "hate": 0.05})
    return RunConfig.test(jurisdictions=("EU",), n_agents=120, n_ticks=24,
                          category_base_rates=rates)


def test_preview_mode_has_no_monte_carlo_bundle():
    a = run_and_analyze(_cfg(), n_replicates=1, verify_replay=False)
    assert a.mc is None  # single run -> within-run intervals only, no MC


def test_research_mode_produces_mc_percentile_intervals():
    a = run_and_analyze(_cfg(), n_replicates=4, verify_replay=False)
    assert a.mc is not None
    assert "harmful_exposure_rate" in a.mc
    assert "## Monte Carlo intervals" in a.report_md
    assert "mc-replicated" in a.report_md
    for name, d in a.mc.items():
        assert d["provenance"] == "mc-replicated", name
        assert d["ci"][0] <= d["median"] <= d["ci"][1], name
        assert d["n_replicates"] >= 1


def test_research_mode_intervals_are_reproducible():
    a1 = run_and_analyze(_cfg(), n_replicates=4, verify_replay=False)
    a2 = run_and_analyze(_cfg(), n_replicates=4, verify_replay=False)
    assert a1.mc["harmful_exposure_rate"]["median"] == \
        a2.mc["harmful_exposure_rate"]["median"]


def test_parallel_replicates_identical_to_sequential():
    """Parallel Monte Carlo (process pool) must give bit-identical aggregates to
    the sequential path — replicates are seeded independently and aggregation is
    order-independent."""
    from socio_sim.pipeline import _headline_metrics
    from socio_sim.validation.montecarlo import run_replicates
    cfg = RunConfig.test(jurisdictions=("EU",), n_agents=80, n_ticks=12)
    seq = run_replicates(cfg, 4, _headline_metrics, workers=1)
    par = run_replicates(cfg, 4, _headline_metrics, workers=2)
    assert seq["n_posts"]["values"] == par["n_posts"]["values"]
    assert seq["harmful_exposure_rate"]["median"] == \
        par["harmful_exposure_rate"]["median"]


def test_pluggable_distributed_executor_matches_sequential():
    """A pluggable executor (here a ProcessPoolExecutor; in production a Dask/Ray
    executor) must produce identical aggregates to the sequential path."""
    from concurrent.futures import ProcessPoolExecutor

    from socio_sim.pipeline import _headline_metrics
    from socio_sim.validation.montecarlo import run_replicates
    cfg = RunConfig.test(jurisdictions=("EU",), n_agents=80, n_ticks=12)
    seq = run_replicates(cfg, 4, _headline_metrics)
    with ProcessPoolExecutor(max_workers=2) as ex:
        dist = run_replicates(cfg, 4, _headline_metrics, executor=ex)
    assert seq["n_posts"]["values"] == dist["n_posts"]["values"]
    assert seq["welfare_mean"]["median"] == dist["welfare_mean"]["median"]
