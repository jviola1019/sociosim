"""P4: sensitivity of headline outputs to BehaviorParams + calibration check."""

import numpy as np

from socio_sim.config import RunConfig
from socio_sim.validation.study import (behavior_sensitivity,
                                        calibration_implausibility,
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
