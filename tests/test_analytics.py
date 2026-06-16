import numpy as np

from socio_sim.analytics.metrics import (bootstrap_ci, cascade_sizes,
                                         fairness_diagnostics,
                                         harmful_exposure,
                                         moderation_confusion, summarize_run)
from socio_sim.analytics.report import render
from socio_sim.config import RunConfig
from socio_sim.engine import Simulation
from socio_sim.logs.events import EventLog
from socio_sim.rng import SeedTree


def fixture_log():
    """Known stream: 2 harmful posts (1 removed, 1 missed), 1 clean post
    (1 wrongly removed... no, kept), impressions and a cascade."""
    log = EventLog()
    log.append(0, "post", 1, "bad1", {"true_categories": ["hate"], "topic": 0,
                                      "parent_id": None})
    log.append(0, "post", 2, "bad2", {"true_categories": ["misinfo"], "topic": 0,
                                      "parent_id": None})
    log.append(0, "post", 3, "ok1", {"true_categories": [], "topic": 1,
                                     "parent_id": None})
    log.append(0, "post", 4, "ok2", {"true_categories": [], "topic": 1,
                                     "parent_id": None})
    # moderation: bad1 removed (TP), ok2 removed (FP); bad2 untouched (FN)
    log.append(1, "moderation", -1, "bad1", {"action": "remove", "rule_id": "R",
                                             "decision_rationale": "r"})
    log.append(1, "moderation", -1, "ok2", {"action": "remove", "rule_id": "R",
                                            "decision_rationale": "r"})
    # impressions: agent 5 sees bad2 and ok1
    log.append(2, "impression", 5, "bad2", {"position": 0, "strategy": "p",
                                            "score": 1.0, "features": {}})
    log.append(2, "impression", 5, "ok1", {"position": 1, "strategy": "p",
                                           "score": 0.9, "features": {}})
    # cascade: ok1 shared twice, one nested
    log.append(3, "post", 6, "s1", {"true_categories": [], "topic": 1,
                                    "parent_id": "ok1"})
    log.append(4, "post", 7, "s2", {"true_categories": [], "topic": 1,
                                    "parent_id": "s1"})
    return log


def test_moderation_confusion_exact():
    cm = moderation_confusion(fixture_log())
    # clean posts: ok1, s1, s2 untouched (TN=3); ok2 removed (FP)
    assert cm["tp"] == 1 and cm["fn"] == 1 and cm["fp"] == 1 and cm["tn"] == 3
    assert cm["recall"] == 0.5 and cm["precision"] == 0.5


def test_harmful_exposure_exact():
    rate, per_agent = harmful_exposure(fixture_log())
    assert rate == 0.5  # 1 harmful of 2 impressions
    assert per_agent[5] == 0.5


def test_cascade_sizes_exact():
    sizes = cascade_sizes(fixture_log())
    assert max(sizes) == 3  # ok1 -> s1 -> s2
    assert sorted(sizes)[-1] == 3


def test_bootstrap_ci_contains_mean():
    rng = SeedTree(1).generator("boot", 0)
    values = np.array([1.0, 2.0, 3.0, 4.0, 5.0] * 20)
    lo, hi = bootstrap_ci(values, rng=rng)
    assert lo < values.mean() < hi


def test_fairness_keys_and_run_summary():
    cfg = RunConfig.test(jurisdictions=("EU",))
    result = Simulation(cfg).run()
    summary = summarize_run(result)
    for key in ("harmful_exposure", "moderation", "appeals", "cascades",
                "welfare", "fairness", "ads", "notices", "n_posts"):
        assert key in summary, f"missing {key}"
    assert "ci" in summary["harmful_exposure"]
    fair = summary["fairness"]
    assert "age_group" in fair and "ideology" in fair and "vulnerable" in fair


def test_report_contains_disclaimer_and_intervals():
    cfg = RunConfig.test(jurisdictions=("EU",))
    result = Simulation(cfg).run()
    summary = summarize_run(result)
    md = render(summary, result.manifest)
    assert "Research use only" in md
    assert "95%" in md
    assert result.manifest.config_hash[:8] in md


def test_wilson_interval_brackets_and_orders():
    from socio_sim.analytics.metrics import wilson_interval
    lo, hi = wilson_interval(50, 100)
    assert lo < 0.5 < hi and 0.0 <= lo < hi <= 1.0
    lo0, hi0 = wilson_interval(0, 10)
    assert lo0 >= 0.0 and hi0 > 0.0           # never degenerate at 0 successes
    # more data -> tighter interval around the same proportion
    wide = wilson_interval(2, 10)
    narrow = wilson_interval(200, 1000)
    assert (narrow[1] - narrow[0]) < (wide[1] - wide[0])
    # empty sample is honest NaN, not a fake interval
    assert all(np.isnan(x) for x in wilson_interval(0, 0))


def test_moderation_confusion_reports_intervals():
    cm = moderation_confusion(fixture_log())
    assert "precision_ci" in cm and "recall_ci" in cm
    assert cm["precision_ci"][0] <= cm["precision"] <= cm["precision_ci"][1]
    assert cm["recall_ci"][0] <= cm["recall"] <= cm["recall_ci"][1]


def test_report_states_uncertainty_provenance():
    """A single-run report must not imply its intervals are Monte Carlo."""
    cfg = RunConfig.test(jurisdictions=("EU",))
    result = Simulation(cfg).run()
    md = render(summarize_run(result), result.manifest)
    low = md.lower()
    assert "provenance" in low or "not monte carlo" in low or "single-run" in low
