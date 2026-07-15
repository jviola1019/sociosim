"""Rung 4 — measured classifier on real licensed benchmarks: datasets are
bundled + clean, and the classifier achieves measured F1/ROC-AUC above baseline,
deterministically."""

import re

from socio_sim.validation.benchmark_eval import (available_benchmarks,
                                                 evaluate_benchmark,
                                                 load_benchmark, roc_auc)

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w]")


def test_benchmarks_bundled_balanced_and_scrubbed():
    assert set(available_benchmarks()) == {"civil_comments", "spam_detection"}
    for name in available_benchmarks():
        texts, labels = load_benchmark(name)
        assert len(texts) == len(labels) >= 2000
        assert set(labels) == {0, 1}
        pos = sum(labels)
        assert 0.4 <= pos / len(labels) <= 0.6           # balanced
        assert not any(_EMAIL.search(t) for t in texts)  # PII scrubbed
        assert all(len(t) <= 400 for t in texts)


def test_measured_metrics_beat_baseline():
    for name in available_benchmarks():
        r = evaluate_benchmark(name, seed=0)
        assert r["provenance"] == "component_benchmark"
        assert r["license"] in ("CC0-1.0", "Apache-2.0")
        assert r["source_sha256"]
        assert r["model_hash"]
        assert r["leakage_pass"]
        assert "bootstrap_ci" in r and "reliability_diagram" in r
        assert "threshold_sweep" in r
        assert r["auc"] >= 0.75, (name, r["auc"])        # MEASURED on real data
        assert r["f1"] >= 0.65, (name, r["f1"])
        assert r["f1"] > r["baseline_majority_acc"] - 0.5  # clearly learning


def test_proper_scoring_beats_climatology_baseline():
    for name in available_benchmarks():
        r = evaluate_benchmark(name, seed=0)
        # Brier/log-loss are proper scores (lower better); must beat the no-skill
        # climatology baseline on REAL held-out labels (positive skill score).
        assert r["brier"] < r["brier_baseline"], (name, r["brier"], r["brier_baseline"])
        assert r["log_loss"] < r["log_loss_baseline"], name
        assert r["brier_skill_score"] > 0.0, (name, r["brier_skill_score"])
        assert 0.0 <= r["ece"] <= 1.0


def test_proper_scoring_functions():
    from socio_sim.validation.benchmark_eval import (brier_score,
                                                     expected_calibration_error,
                                                     log_loss)
    assert brier_score([1, 0], [1.0, 0.0]) == 0.0          # perfect
    assert brier_score([1, 0], [0.0, 1.0]) == 1.0          # worst
    assert log_loss([1, 1], [0.999999, 0.999999]) < 1e-3   # confident+correct
    assert expected_calibration_error([1, 0], [1.0, 0.0]) == 0.0


def test_evaluation_is_deterministic():
    a = evaluate_benchmark("spam_detection", seed=0)
    b = evaluate_benchmark("spam_detection", seed=0)
    assert a["f1"] == b["f1"] and a["auc"] == b["auc"] and a["brier"] == b["brier"]


def test_roc_auc_known_cases():
    assert roc_auc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]) == 1.0   # perfect ranking
    assert abs(roc_auc([0, 1, 0, 1], [0.5, 0.5, 0.5, 0.5]) - 0.5) < 1e-9  # ties
    assert roc_auc([0, 0, 1, 1], [0.9, 0.8, 0.2, 0.1]) == 0.0   # inverted


def test_calibration_slope_is_the_logistic_slope_not_ols():
    """A well-calibrated model has calibration slope ~= 1 (Van Calster
    2019). A model whose probabilities are too EXTREME (over-confident) has
    slope < 1; too timid has slope > 1. The old OLS-of-y-on-logit(p) did
    not have the '=1 iff calibrated' property."""
    import numpy as np

    from socio_sim.validation.benchmark_eval import calibration_slope
    rng = np.random.default_rng(0)
    # Perfectly calibrated: y ~ Bernoulli(p), p uniform-ish over (0,1).
    p = rng.uniform(0.02, 0.98, 20000)
    y = (rng.random(20000) < p).astype(int)
    assert abs(calibration_slope(y, p) - 1.0) < 0.15, calibration_slope(y, p)
    # Over-confident: push probabilities toward the extremes -> slope < 1.
    p_over = np.clip(1 / (1 + np.exp(-2.0 * np.log(p / (1 - p)))), 1e-6, 1 - 1e-6)
    assert calibration_slope(y, p_over) < 0.85, calibration_slope(y, p_over)
    # Degenerate inputs -> NaN, not a spurious number.
    assert np.isnan(calibration_slope([1, 1, 1], [0.6, 0.6, 0.6]))
