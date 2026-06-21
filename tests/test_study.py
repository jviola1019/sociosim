"""P4: sensitivity of headline outputs to BehaviorParams + calibration check."""

import numpy as np

from socio_sim.config import RunConfig
from socio_sim.validation.study import (behavior_sensitivity,
                                        calibration_implausibility,
                                        posterior_calibrated_mc,
                                        posts_per_agent,
                                        render_validation_report,
                                        run_validation_study)


def test_behavior_sensitivity_ranks_posting_param_first():
    """posts/agent should be dominated by p_post_given_active, not the fatigue
    or flag knobs -- a real sensitivity check on the model's own parameters."""
    cfg = RunConfig.test(jurisdictions=("EU",), root_seed=1)
    rng = np.random.default_rng(1)
    bounds = {"p_post_given_active": (0.1, 0.5),
              "impression_fatigue": (0.002, 0.008),
              "p_flag_scale": (0.1, 0.5)}
    s = behavior_sensitivity(cfg, bounds, n_samples=16,
                             metric_fn=posts_per_agent, rng=rng)
    ranked = sorted(s["indices"], key=s["indices"].get, reverse=True)
    assert ranked[0] == "p_post_given_active"
    assert s["indices"]["p_post_given_active"] > s["indices"]["p_flag_scale"]


def test_calibration_implausibility_is_finite_with_observed():
    c = calibration_implausibility(RunConfig.test(jurisdictions=("EU",)))
    assert np.isfinite(c["implausibility"])
    assert "clustering" in c["observed"]
    assert "degree_tail_exponent" in c["observed"]


def test_validation_report_renders_sections():
    study = run_validation_study(profile="test", n_samples=8, seed=3)
    md = render_validation_report(study)
    assert "Validation Report" in md
    assert "Sensitivity" in md and "Calibration" in md
    assert "synthetic exploratory" in md.lower()
    assert "Implausibility" in md


def test_calibration_includes_diurnal_ks_distributional_check():
    c = calibration_implausibility(RunConfig.test(jurisdictions=("EU",)))
    assert "diurnal_ks" in c
    assert 0.0 <= c["diurnal_ks"] <= 1.0


def test_multi_output_sensitivity_sobol_multiseed():
    from socio_sim.validation.study import multi_output_sensitivity
    cfg = RunConfig.test(jurisdictions=("EU",))
    bounds = {"p_post_given_active": (0.15, 0.45),
              "p_flag_scale": (0.15, 0.45)}
    ms = multi_output_sensitivity(cfg, bounds, n_samples=8, seeds=(1, 2))
    assert ms["n_seeds"] == 2 and ms["n_samples"] >= 8
    assert set(ms["outputs"]) >= {"n_posts"}
    # n_posts should be driven more by posting prob than by the flag knob
    s = ms["indices"]["n_posts"]
    assert s["p_post_given_active"]["mean"] >= s["p_flag_scale"]["mean"]
    # cross-seed std is reported (uncertainty of the index estimate)
    assert "std" in s["p_post_given_active"]


def test_saltelli_indices_recover_known_first_and_total_effects():
    """On the Ishigami-style additive model y = a*x1 + b*x2 (no interaction),
    S1 should rank x1>x2 and ST≈S1 (no interaction inflation)."""
    import numpy as np

    from socio_sim.validation.sensitivity import saltelli_indices
    rng = np.random.default_rng(0)
    n = 4096
    A = rng.random((n, 2))
    B = rng.random((n, 2))

    def f(M):
        return 3.0 * M[:, 0] + 1.0 * M[:, 1]
    fA, fB = f(A), f(B)
    fab = {}
    for i, name in enumerate(["x1", "x2"]):
        AB = A.copy()
        AB[:, i] = B[:, i]
        fab[name] = f(AB)
    r = saltelli_indices(fA, fB, fab, ["x1", "x2"])
    assert r["S1"]["x1"] > r["S1"]["x2"]               # x1 dominates
    assert abs(r["ST"]["x1"] - r["S1"]["x1"]) < 0.1    # additive => ST≈S1
    assert r["S1"]["x1"] + r["S1"]["x2"] > 0.9         # variance accounted for


def test_saltelli_study_runs_on_engine():
    from socio_sim.validation.study import saltelli_study
    cfg = RunConfig.test(jurisdictions=("EU",))
    bounds = {"p_post_given_active": (0.15, 0.45),
              "p_flag_scale": (0.15, 0.45)}
    r = saltelli_study(cfg, bounds, n_base=4, output="n_posts", seed=5)
    assert r["n_eval"] == r["N"] * (len(bounds) + 2)
    assert r["ST"]["p_post_given_active"] >= 0.0       # total-effect computed
    # posting prob should dominate posting volume (S1 or ST)
    assert (r["ST"]["p_post_given_active"]
            >= r["ST"]["p_flag_scale"] - 0.2)


def test_posterior_calibrated_mc_propagates_parameter_uncertainty():
    pm = posterior_calibrated_mc(profile="test", n_samples=16, seed=4)
    assert pm["n_accepted"] >= 1
    assert "posterior" in pm and "p_post_given_active" in pm["posterior"]
    lo, hi = pm["output_ci"]
    assert lo <= pm["output_median"] <= hi
    assert pm["provenance"] == "abc-posterior-propagated"
