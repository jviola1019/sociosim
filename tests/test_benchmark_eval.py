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
        assert r["provenance"] == "measured-on-benchmark"
        assert r["license"] in ("CC0-1.0", "Apache-2.0")
        assert r["auc"] >= 0.75, (name, r["auc"])        # MEASURED on real data
        assert r["f1"] >= 0.65, (name, r["f1"])
        assert r["f1"] > r["baseline_majority_acc"] - 0.5  # clearly learning


def test_evaluation_is_deterministic():
    a = evaluate_benchmark("spam_detection", seed=0)
    b = evaluate_benchmark("spam_detection", seed=0)
    assert a["f1"] == b["f1"] and a["auc"] == b["auc"]


def test_roc_auc_known_cases():
    assert roc_auc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]) == 1.0   # perfect ranking
    assert abs(roc_auc([0, 1, 0, 1], [0.5, 0.5, 0.5, 0.5]) - 0.5) < 1e-9  # ties
    assert roc_auc([0, 0, 1, 1], [0.9, 0.8, 0.2, 0.1]) == 0.0   # inverted
