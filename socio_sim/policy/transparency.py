"""Transparency reporting from the event log (Spec §3.6; DSA Arts 15/24).

Aggregates logged moderation actions, notices, and appeals by the
`transparency_category` declared on each rule (policy-as-code), producing a
structured transparency report analogous to DSA statement-of-reasons /
transparency-report categories and CN log-retention tracking.

Reads only logged events + rule metadata — never PII, never chain-of-thought.
Provenance: a deterministic tally of one run's audit log, not an estimate.
"""

from __future__ import annotations

from socio_sim.logs.events import EventLog
from socio_sim.policy.engine import PolicyEngine


def transparency_report(log: EventLog, engine: PolicyEngine) -> dict:
    """Tally a run's enforcement actions for a transparency report.

    Groups actions by each rule's `transparency_category`; counts notices,
    appeals (filed/resolved/granted), human reviews and deadline misses; and
    records the maximum log-retention obligation across active rules.
    """
    rule_meta = {r["rule_id"]: r for p in engine.packs for r in p["rules"]}
    moderation = log.by_kind("moderation")
    notices = log.by_kind("notice")
    appeals = log.by_kind("appeal")

    by_cat: dict = {}
    for e in moderation:
        if "action" not in e["data"]:
            continue  # human-review records carry no action; counted below
        meta = rule_meta.get(e["data"].get("rule_id"), {})
        cat = meta.get("transparency_category", "uncategorized")
        d = by_cat.setdefault(cat, {"actions": 0, "by_action": {},
                                    "jurisdictions": set()})
        d["actions"] += 1
        action = e["data"].get("action", "?")
        d["by_action"][action] = d["by_action"].get(action, 0) + 1
        jur = e["data"].get("jurisdiction") or meta.get("jurisdiction")
        if jur:
            d["jurisdictions"].add(jur)

    reviews = [e for e in moderation if e["data"].get("stage") == "human_review"]
    misses = [e for e in reviews if e["data"].get("deadline_missed")]
    filed = [a for a in appeals if a["data"].get("stage") == "filed"]
    resolved = [a for a in appeals if a["data"].get("stage") == "resolved"]
    granted = [a for a in resolved if a["data"].get("granted")]
    retention = [int(r.get("retention_months", 0)) for r in rule_meta.values()]

    return {
        "pack_versions": engine.pack_versions(),
        "notices_sent": len(notices),
        "actions_by_category": {
            cat: {"actions": v["actions"], "by_action": v["by_action"],
                  "jurisdictions": sorted(v["jurisdictions"])}
            for cat, v in sorted(by_cat.items())},
        "appeals": {
            "filed": len(filed), "resolved": len(resolved),
            "granted": len(granted),
            "grant_rate": (len(granted) / len(resolved)) if resolved else None},
        "human_reviews": len(reviews),
        "deadline_misses": len(misses),
        "max_retention_months": max(retention) if retention else 0,
    }
