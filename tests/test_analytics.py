import re

import numpy as np

from socio_sim.analytics.metrics import (bootstrap_ci, cascade_sizes,
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


def test_appeal_stats_includes_resolution_p95():
    from socio_sim.analytics.metrics import appeal_stats
    log = EventLog()
    log.append(1, "appeal", 1, "c1", {"stage": "filed", "rule_id": "R"})
    log.append(5, "appeal", 1, "c1", {"stage": "resolved", "granted": True,
                                      "rule_id": "R", "resolution_ticks": 4})
    log.append(2, "appeal", 2, "c2", {"stage": "filed", "rule_id": "R"})
    log.append(9, "appeal", 2, "c2", {"stage": "resolved", "granted": False,
                                      "rule_id": "R", "resolution_ticks": 7})
    s = appeal_stats(log)
    assert "p95_resolution_ticks" in s
    assert s["p95_resolution_ticks"] >= s["mean_resolution_ticks"]


def test_harmful_exposure_exact():
    rate, per_agent_counts = harmful_exposure(fixture_log())
    assert rate == 0.5  # 1 harmful of 2 impressions (pooled)
    # per_agent_counts now carries (harm, total) so the CI can re-pool.
    assert per_agent_counts[5] == (1, 2)


def test_harmful_exposure_ci_matches_the_pooled_estimand():
    """The reported CI must bound the impression-POOLED rate, not the
    unweighted mean of per-agent rates. With one high-volume agent seeing
    all harmful content and many low-volume agents seeing none, the pooled
    rate (0.333) and the per-agent mean (0.048) diverge: the new
    ratio-of-sums CI contains the pooled rate, while the OLD per-agent-mean
    bootstrap excludes it entirely."""
    import numpy as np

    from socio_sim.analytics.metrics import bootstrap_ci, ratio_bootstrap_ci
    harm = [10] + [0] * 20          # one agent: 10 harmful impressions
    tot = [10] + [1] * 20           # + 20 agents with 1 clean impression each
    pooled = sum(harm) / sum(tot)   # 10/30 = 0.333

    lo, hi = ratio_bootstrap_ci(harm, tot, rng=np.random.default_rng(0))
    assert lo <= pooled <= hi, (lo, pooled, hi)

    # The estimand the old code used (mean of per-agent rates) yields a CI
    # that does NOT cover the pooled rate -- the bug this fix corrects.
    rates = [h / t for h, t in zip(harm, tot)]
    old_lo, old_hi = bootstrap_ci(rates, rng=np.random.default_rng(0))
    assert not (old_lo <= pooled <= old_hi), (old_lo, pooled, old_hi)


def test_cascade_sizes_exact():
    sizes = cascade_sizes(fixture_log())
    assert max(sizes) == 3  # ok1 -> s1 -> s2
    assert sorted(sizes)[-1] == 3


def test_cascade_tree_builds_largest_tree_with_depths():
    from socio_sim.analytics.metrics import cascade_tree
    t = cascade_tree(fixture_log())
    ids = {n["id"] for n in t["nodes"]}
    assert {"ok1", "s1", "s2"} <= ids       # the ok1 -> s1 -> s2 cascade
    assert t["size"] == 3 and len(t["edges"]) >= 2
    assert max(n["depth"] for n in t["nodes"]) == 2
    # nodes carry posting ticks (for time-ordered replay)
    assert all("tick" in n for n in t["nodes"])


def test_bootstrap_ci_contains_mean():
    rng = SeedTree(1).generator("boot", 0)
    values = np.array([1.0, 2.0, 3.0, 4.0, 5.0] * 20)
    lo, hi = bootstrap_ci(values, rng=rng)
    assert lo < values.mean() < hi


def test_minor_protection_counts_minor_ad_impressions():
    from socio_sim.analytics.metrics import minor_protection

    class P:
        n = 3
        is_minor = np.array([True, False, False])
    log = EventLog()
    log.append(0, "impression", 0, "a", {"strategy": "ad"})           # minor
    log.append(0, "impression", 1, "b", {"strategy": "ad"})           # adult
    log.append(0, "impression", 2, "c", {"strategy": "personalized"})  # organic
    mp = minor_protection(log, P())
    assert mp["ad_impressions"] == 2 and mp["ad_impressions_to_minors"] == 1


def test_eu_minor_ad_ban_holds_end_to_end():
    """A run-level check that EU-ADS-MINOR-1 actually prevents ad impressions to
    minors (rights-impact metric == 0), while adults are still served."""
    cfg = RunConfig.test(jurisdictions=("EU",))
    mp = summarize_run(Simulation(cfg).run())["minor_protection"]
    assert mp["ad_impressions"] > 0
    assert mp["ad_impressions_to_minors"] == 0


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
    assert "not legal advice" in md
    assert "descriptive resampling interval" in md
    assert result.manifest.config_hash[:8] in md
    assert not re.search(r"\bnan\b", md.lower())
    assert not re.search(r"\binfinity\b", md.lower())


def test_report_minor_ad_text_is_jurisdiction_aware():
    us = Simulation(RunConfig.test(jurisdictions=("US",), n_agents=80, n_ticks=12)).run()
    us_md = render(summarize_run(us), us.manifest)
    assert "EU-ADS-MINOR-1" not in us_md
    assert "no EU minor-ad ban is active" in us_md

    eu = Simulation(RunConfig.test(jurisdictions=("EU",), n_agents=80, n_ticks=12)).run()
    eu_md = render(summarize_run(eu), eu.manifest)
    assert "EU-ADS-MINOR-1" in eu_md


def test_small_eu_report_flags_insufficient_moderation_sample():
    result = Simulation(RunConfig.test(jurisdictions=("EU",), n_agents=60, n_ticks=12)).run()
    summary = summarize_run(result)
    assert summary["moderation"]["insufficient_sample"] is True
    for groups in summary["fairness"].values():
        for row in groups.values():
            assert "n_harmful" in row and "n_benign" in row
    md = render(summary, result.manifest)
    assert "insufficient sample" in md
    assert not re.search(r"\bnan\b", md.lower())


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


def test_dynamic_graph_report_uses_final_topology():
    cfg = RunConfig.test(jurisdictions=("EU",), n_ticks=72,
                         follow_rate=0.1, unfollow_rate=0.1, churn_rate=0.04)
    result = Simulation(cfg).run()
    summary = summarize_run(result)
    assert result.graph_stats["initial"]
    assert result.graph_stats["final"]
    assert summary["graph"]["m"] == result.graph_stats["final"]["m"]
    md = render(summary, result.manifest)
    assert "values above are final topology" in md
