"""Run analytics (Spec §3.8): exposure, moderation quality, appeals, cascades,
welfare proxy, and fairness diagnostics with evidence-labelled intervals.

All functions are pure over the event log (plus personas where grouping is
needed), so they work identically on live results and replayed logs.
"""

from __future__ import annotations

import numpy as np

from socio_sim.ads.measure import apply_fdr, measure_campaign
from socio_sim.config import HARMFUL_CATEGORIES
from socio_sim.evidence import metric_evidence
from socio_sim.logs.events import EventLog
from socio_sim.rng import SeedTree
from socio_sim.stats import wilson_interval  # re-exported for callers/tests

# Single source: socio_sim.config.HARMFUL_CATEGORIES.
HARMFUL = frozenset(HARMFUL_CATEGORIES)

TERMINAL_ACTIONS = {"remove", "downrank"}

#: Welfare proxy weights (design §1): satisfaction per engagement, penalty per
#: harmful impression, small attention cost per impression.
W_ENGAGE, W_HARM, W_ATTENTION = 1.0, 2.0, 0.01


METRIC_EVIDENCE_IDS = {
    "n_posts": "ev.scenario_assumption.default_parameters",
    "n_impressions": "ev.scenario_assumption.default_parameters",
    "n_engagements": "ev.scenario_assumption.default_parameters",
    "harmful_exposure": "ev.scenario_assumption.default_parameters",
    "moderation": "ev.synthetic_engineering.classifier_noise",
    "appeals": "ev.scenario_assumption.default_parameters",
    "notices": "ev.scenario_assumption.default_parameters",
    "cascades": "ev.scenario_assumption.default_parameters",
    "welfare": "ev.scenario_assumption.default_parameters",
    "fairness": "ev.scenario_assumption.default_parameters",
    "minor_protection": "ev.scenario_assumption.default_parameters",
    "ads": "ev.scenario_assumption.default_parameters",
    "graph": "ev.scenario_assumption.default_parameters",
}


def metric_provenance() -> dict:
    return {name: metric_evidence(eid) for name, eid in METRIC_EVIDENCE_IDS.items()}


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
        "precision_ci": wilson_interval(tp, tp + fp),
        "recall_ci": wilson_interval(tp, tp + fn),
        "n_harmful": tp + fn,
        "n_benign": fp + tn,
        "insufficient_sample": (tp + fp) == 0 or (tp + fn) < 10 or (fp + tn) < 10,
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
        "granted_rate_ci": wilson_interval(len(granted), len(resolved)),
        "mean_resolution_ticks": (
            float(np.mean([e["data"]["resolution_ticks"] for e in resolved]))
            if resolved else float("nan")),
        "p95_resolution_ticks": (
            float(np.percentile([e["data"]["resolution_ticks"] for e in resolved], 95))
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


def cascade_tree(log: EventLog, max_nodes: int = 150) -> dict:
    """The largest share cascade as a tree for replay: nodes carry their posting
    tick and depth so the UI can reveal them in time order (propagation replay).
    """
    posts = log.by_kind("post")
    parent = {e["content_id"]: e["data"].get("parent_id") for e in posts}
    tick = {e["content_id"]: e["tick"] for e in posts}
    children: dict = {}
    for cid, p in parent.items():
        if p is not None:
            children.setdefault(p, []).append(cid)

    def root(cid):
        seen = set()
        while parent.get(cid) and cid not in seen:
            seen.add(cid)
            cid = parent[cid]
        return cid

    sizes: dict = {}
    for cid in parent:
        sizes[root(cid)] = sizes.get(root(cid), 0) + 1
    if not sizes:
        return {"nodes": [], "edges": [], "size": 0}
    top = max(sizes, key=lambda r: (sizes[r], r))
    if sizes[top] < 2:
        return {"nodes": [], "edges": [], "size": sizes[top]}

    nodes, edges, depth, queue, seen = [], [], {top: 0}, [top], {top}
    while queue and len(nodes) < max_nodes:
        cid = queue.pop(0)
        nodes.append({"id": cid, "tick": int(tick.get(cid, 0)), "depth": depth[cid]})
        for ch in sorted(children.get(cid, [])):
            if ch not in seen and len(seen) < max_nodes:
                seen.add(ch)
                depth[ch] = depth[cid] + 1
                edges.append([cid, ch])
                queue.append(ch)
    return {"nodes": nodes, "edges": edges, "size": sizes[top]}


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
                "n_harmful": d["tp"] + d["fn"],
                "n_benign": d["fp"] + d["tn"],
                "n_posts": d["tp"] + d["fp"] + d["fn"] + d["tn"],
                "insufficient_sample": (
                    (d["tp"] + d["fp"]) == 0
                    or (d["tp"] + d["fn"]) < 10
                    or (d["fp"] + d["tn"]) < 10
                ),
            } for g, d in per_group.items()
        }
    return out


def minor_protection(log: EventLog, personas) -> dict:
    """Rights-impact: ad exposure of minors. Under the EU minor-ad ban
    (EU-ADS-MINOR-1) this should be 0; in US mode minors may be served. A direct
    check that the minor-protection rule actually bites end-to-end."""
    ad_impr = [e for e in log.by_kind("impression")
               if e["data"].get("strategy") == "ad"]
    to_minor = sum(1 for e in ad_impr
                   if 0 <= e["actor_id"] < personas.n
                   and bool(personas.is_minor[e["actor_id"]]))
    return {
        "ad_impressions": len(ad_impr),
        "ad_impressions_to_minors": to_minor,
        "minor_ad_rate": (to_minor / len(ad_impr)) if ad_impr else 0.0,
    }


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
        "minor_protection": minor_protection(log, result.personas),
        "ads": _ads_with_fdr(log, result),
        "graph": result.graph_stats,
        "metric_provenance": metric_provenance(),
    }


def _ads_with_fdr(log, result) -> dict:
    measures = {c.id: measure_campaign(log, c, result.ads, result.config.n_agents)
                for c in result.campaigns}
    apply_fdr(list(measures.values()))  # BH-FDR across campaigns (mutates in place)
    return measures
