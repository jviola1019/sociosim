import numpy as np
import pytest

from socio_sim.config import RunConfig
from socio_sim.rng import SeedTree
from socio_sim.validation.calibrate import (abc_posterior, history_match,
                                            implausibility)
from socio_sim.validation.montecarlo import run_replicates
from socio_sim.validation.sensitivity import first_order_indices
from socio_sim.validation.targets import hill_exponent, load_targets


def test_targets_load_with_tolerances():
    t = load_targets()
    assert "clustering" in t and "ad_ctr" in t
    for name, spec in t.items():
        assert spec["tolerance"] > 0, name
        assert "source" in spec


def test_implausibility_monotone():
    targets = {"x": {"value": 5.0, "tolerance": 1.0}}
    assert implausibility({"x": 5.0}, targets) == 0.0
    near = implausibility({"x": 5.5}, targets)
    far = implausibility({"x": 8.0}, targets)
    assert 0 < near < far
    assert far == 3.0


def test_hill_exponent_on_powerlaw_sample():
    rng = SeedTree(5).generator("hill", 0)
    # Pareto with alpha=2.5 -> tail exponent ~2.5
    sample = (rng.pareto(1.5, size=20000) + 1)  # pareto a -> exponent a+1
    est = hill_exponent(sample)
    assert 2.2 < est < 2.9


def toy_run(params, rng=None):
    """Toy simulator: observable x = a + small noise; truth a*=5."""
    noise = 0.0 if rng is None else rng.normal(0, 0.05)
    return {"x": params["a"] + noise}


def test_history_matching_and_abc_recover_planted_parameter():
    targets = {"x": {"value": 5.0, "tolerance": 0.5}}
    bounds = {"a": (0.0, 10.0)}
    rng = SeedTree(6).generator("abc", 0)
    survivors = history_match(toy_run, bounds, targets, n_samples=400,
                              rng=rng, threshold=3.0)
    assert survivors, "history matching wiped out everything"
    surviving_a = np.array([s["params"]["a"] for s in survivors])
    assert surviving_a.min() > 2.5 and surviving_a.max() < 7.5

    posterior = abc_posterior(survivors, accept_fraction=0.2)
    a_med = posterior["a"]["median"]
    lo, hi = posterior["a"]["ci"]
    assert abs(a_med - 5.0) < 0.5
    assert lo < 5.0 < hi


def test_sensitivity_ranks_dominant_parameter_first():
    rng = SeedTree(7).generator("sens", 0)
    n = 2000
    X = rng.random((n, 3))
    y = 5.0 * X[:, 0] + 0.2 * X[:, 1] + rng.normal(0, 0.1, n)
    indices = first_order_indices(X, y, names=["a", "b", "c"])
    ranked = sorted(indices, key=indices.get, reverse=True)
    assert ranked[0] == "a"
    assert indices["a"] > 5 * indices["c"]


@pytest.mark.slow
def test_monte_carlo_replicates_summary():
    cfg = RunConfig.test(n_agents=100, n_ticks=24)

    def metric_fn(result):
        return {"posts": float(len(result.log.by_kind("post")))}

    mc = run_replicates(cfg, n_replicates=3, metric_fn=metric_fn)
    assert set(mc["posts"].keys()) >= {"median", "ci", "values"}
    assert len(mc["posts"]["values"]) == 3
    assert len(set(mc["posts"]["values"])) > 1  # replicates differ


def test_observed_includes_degree_tail_exponent():
    """The degree-tail exponent is a published calibration target; it must be
    computed into `observed` so implausibility actually compares against it."""
    from socio_sim.analytics.metrics import summarize_run
    from socio_sim.engine import Simulation
    from socio_sim.validation.targets import compute_observed
    res = Simulation(RunConfig.test(jurisdictions=("EU",))).run()
    obs = compute_observed(res, summarize_run(res))
    assert "degree_tail_exponent" in obs
    assert np.isfinite(obs["degree_tail_exponent"])
    # Scale-free graphs sit ~2-3; allow a loose finite-sample band.
    assert 1.5 < obs["degree_tail_exponent"] < 6.0


def test_all_targets_are_compared_in_implausibility():
    """Every published target should be present in observed (none silently
    dropped from the implausibility computation)."""
    from socio_sim.analytics.metrics import summarize_run
    from socio_sim.engine import Simulation
    from socio_sim.validation.targets import compute_observed
    res = Simulation(RunConfig.test(jurisdictions=("EU",))).run()
    obs = compute_observed(res, summarize_run(res))
    for name in load_targets():
        assert name in obs, f"target {name!r} never computed into observed"
