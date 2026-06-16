"""Run analytics (Spec §3.8): exposure, moderation quality, appeals, cascades,
welfare proxy, fairness diagnostics — every aggregate with a bootstrap 95% CI.

All functions are pure over the event log (plus personas where grouping is
needed), so they work identically on live results and replayed logs.
"""

from __future__ import annotations

import numpy as np

from socio_sim.ads.measure import measure_campaign
from socio_sim.logs.events import EventLog
from socio_sim.rng import SeedTree

HARMFUL = {"hate", "harassment", "fraud", "misinfo", "adult",
           "illegal_goods", "self_harm"}

TERMINAL_ACTIONS = {"remove", "downrank"}

#: Welfare proxy weights (design §1): satisfaction per engagement, penalty per
#: harmful impression, small attention cost per impression.
W_ENGAGE, W_HARM, W_ATTENTION = 1.0, 2.0, 0.01


def _truth_map(log: EventLog) -> dict:
    return {e["content_id"]: set(e["data"].get("true_categories", []))
            for e in log.by_kind("post")}


def bootstrap_ci(values, stat=np.mean, n_resamples: int = 1000,
                 rng: np.random.Generator | None = None) -> tuple:
    values = np.asarray(values, dtype=float)
    if len(values) == 0:
        return (float("nan"), float("nan"))
    rng = rng or SeedTree(0).generator("bootstrap", 0)
    idx = rng.integers(0, len(values), size=(n_resamples, len(values)))
    stats = stat(values[idx], axis=1)
    return (float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5)))


def moderation_confusion(log: EventLog) -> dict:
    truth = _truth_map(log)
    actioned = {e["content_id"] for e in log.by_kind("moderation")
                if e["data"].get("action") in TERMINAL_ACTIONS}
    tp = fp = fn = tn = 0
    for cid, cats in truth.items():
        harmful = bool(cats & HARMFUL)
        hit = cid in actioned
        tp += harmful and hit
        fn += harmful and not hit
        fp += (not harmful) and hit
        tn += (not harmful) and not hit
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": tp / (tp + fp) if (tp + fp) else float("nan"),
        "recall": tp / (tp + fn) if (tp + fn) else float("nan"),
        "fpr": fp / (fp + tn) if (fp + tn) else float("nan"),
        "fnr": fn / (fn + tp) if (fn + tp) else float("nan"),
    }


def harmful_exposure(log: EventLog) -> tuple:
    """Returns (overall harmful-impression rate, per-agent rates)."""
    truth = _truth_map(log)
    per_agent_harm: dict = {}
    per_agent_total: dict = {}
    for e in log.by_kind("impression"):
        aid = e["actor_id"]
        per_agent_total[aid] = per_agent_total.get(aid, 0) + 1
        if truth.get(e["content_id"], set()) & HARMFUL:
            per_agent_harm[aid] = per_agent_harm.get(aid, 0) + 1
    total = sum(per_agent_total.values())
    harm = sum(per_agent_harm.values())
    rates = {aid: per_agent_harm.get(aid, 0) / n
             for aid, n in per_agent_total.items()}
    return (harm / total if total else 0.0), rates


def appeal_stats(log: EventLog) -> dict:
    filed = [e for e in log.by_kind("appeal") if e["data"]["stage"] == "filed"]
    resolved = [e for e in log.by_kind("appeal")
                if e["data"]["stage"] == "resolved"]
    granted = [e for e in resolved if e["data"]["granted"]]
    reviews = [e for e in log.by_kind("moderation")
               if e["data"].get("stage") == "human_review"]
    misses = [e for e in reviews if e["data"].get("deadline_missed")]
    return {
        "filed": len(filed),
        "resolved": len(resolved),
        "granted_rate": len(granted) / len(resolved) if resolved else float("nan"),
        "mean_resolution_ticks": (
            float(np.mean([e["data"]["resolution_ticks"] for e in resolved]))
            if resolved else float("nan")),
        "human_reviews": len(reviews),
        "deadline_miss_rate": len(misses) / len(reviews) if reviews else 0.0,
    }


def notice_stats(log: EventLog) -> dict:
    removals = [e for e in log.by_kind("moderation")
                if e["data"].get("action") == "remove"]
    noticed_ids = {e["content_id"] for e in log.by_kind("notice")}
    covered = [e for e in removals if e["content_id"] in noticed_ids]
    return {
        "notices_sent": len(log.by_kind("notice")),
        "removals": len(removals),
        "removal_notice_coverage": (
            len(covered) / len(removals) if removals else float("nan")),
    }


def cascade_sizes(log: EventLog) -> list:
    posts = log.by_kind("post")
    parent = {e["content_id"]: e["data"].get("parent_id") for e in posts}

    def root(cid):
        seen = set()
        while parent.get(cid) and cid not in seen:
            seen.add(cid)
            cid = parent[cid]
        return cid

    sizes: dict = {}
    for cid in parent:
        sizes[root(cid)] = sizes.get(root(cid), 0) + 1
    return list(sizes.values())


def welfare_proxy(log: EventLog) -> dict:
    """Per-agent session satisfaction: engagements − harm penalty − attention
    cost, normalized by impressions (design §1 definition)."""
    truth = _truth_map(log)
    engagements: dict = {}
    impressions: dict = {}
    harm: dict = {}
    for e in log.by_kind("engagement"):
        engagements[e["actor_id"]] = engagements.get(e["actor_id"], 0) + 1
    for e in log.by_kind("impression"):
        aid = e["actor_id"]
        impressions[aid] = impressions.get(aid, 0) + 1
        if truth.get(e["content_id"], set()) & HARMFUL:
            harm[aid] = harm.get(aid, 0) + 1
    values = []
    for aid, n_imp in impressions.items():
        score = (W_ENGAGE * engagements.get(aid, 0)
                 - W_HARM * harm.get(aid, 0)
                 - W_ATTENTION * n_imp) / n_imp
        values.append(score)
    return {"per_agent": values,
            "mean": float(np.mean(values)) if values else float("nan")}


def fairness_diagnostics(log: EventLog, personas) -> dict:
    """Moderation FP/FN rates by author group; the core disparity check."""
    truth = _truth_map(log)
    authors = {e["content_id"]: e["actor_id"] for e in log.by_kind("post")}
    actioned = {e["content_id"] for e in log.by_kind("moderation")
                if e["data"].get("action") in TERMINAL_ACTIONS}
    groups = personas.group_labels()
    out: dict = {}
    for key, labels in groups.items():
        per_group: dict = {}
        for cid, cats in truth.items():
            author = authors.get(cid)
            if author is None or author < 0 or author >= personas.n:
                continue
            g = str(labels[author])
            d = per_group.setdefault(g, {"tp": 0, "fp": 0, "fn": 0, "tn": 0})
            harmful = bool(cats & HARMFUL)
            hit = cid in actioned
            d["tp"] += harmful and hit
            d["fn"] += harmful and not hit
            d["fp"] += (not harmful) and hit
            d["tn"] += (not harmful) and not hit
        out[key] = {
            g: {
                "fpr": (d["fp"] / (d["fp"] + d["tn"])
                        if (d["fp"] + d["tn"]) else float("nan")),
                "fnr": (d["fn"] / (d["fn"] + d["tp"])
                        if (d["fn"] + d["tp"]) else float("nan")),
                "n_posts": d["tp"] + d["fp"] + d["fn"] + d["tn"],
            } for g, d in per_group.items()
        }
    return out


def summarize_run(result, rng: np.random.Generator | None = None) -> dict:
    log = result.log
    rng = rng or SeedTree(result.config.root_seed).generator("analytics", 0)
    rate, per_agent = harmful_exposure(log)
    agent_rates = list(per_agent.values())
    welfare = welfare_proxy(log)
    return {
        "n_posts": len(log.by_kind("post")),
        "n_impressions": len(log.by_kind("impression")),
        "n_engagements": len(log.by_kind("engagement")),
        "harmful_exposure": {
            "rate": rate,
            "ci": bootstrap_ci(agent_rates, rng=rng) if agent_rates
            else (float("nan"), float("nan")),
        },
        "moderation": moderation_confusion(log),
        "appeals": appeal_stats(log),
        "notices": notice_stats(log),
        "cascades": {
            "n": len(cascade_sizes(log)),
            "max": max(cascade_sizes(log), default=0),
            "mean": float(np.mean(cascade_sizes(log) or [0])),
        },
        "welfare": {
            "mean": welfare["mean"],
            "ci": bootstrap_ci(welfare["per_agent"], rng=rng),
        },
        "fairness": fairness_diagnostics(log, result.personas),
        "ads": {c.id: measure_campaign(log, c, result.ads,
                                       result.config.n_agents)
                for c in result.campaigns},
        "graph": result.graph_stats,
    }
