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
    for name, d in a.mc.items():
        assert d["provenance"] == "mc-replicated", name
        assert d["ci"][0] <= d["median"] <= d["ci"][1], name
        assert d["n_replicates"] >= 1


def test_research_mode_intervals_are_reproducible():
    a1 = run_and_analyze(_cfg(), n_replicates=4, verify_replay=False)
    a2 = run_and_analyze(_cfg(), n_replicates=4, verify_replay=False)
    assert a1.mc["harmful_exposure_rate"]["median"] == \
        a2.mc["harmful_exposure_rate"]["median"]
