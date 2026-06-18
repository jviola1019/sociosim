"""P3: policy-as-code citations/fields + transparency-report exporter."""

import pytest

from socio_sim.logs.events import EventLog
from socio_sim.policy.engine import PackError, PolicyEngine, load_packs
from socio_sim.policy.transparency import transparency_report

NEW_FIELDS = ("source_citation", "legal_uncertainty", "user_rights",
              "transparency_category", "human_review_required")


def test_shipped_packs_have_citations_and_transparency_fields():
    """Policy-as-code, not vibes-as-code: every shipped rule must cite a source
    and declare its transparency category, user-rights impact, review need."""
    packs = load_packs(("US", "EU", "CN"), ftc_enabled=True)
    for p in packs:
        for r in p["rules"]:
            for f in NEW_FIELDS:
                assert f in r and r[f] not in (None, ""), \
                    f"{r['rule_id']} missing {f}"


def test_pack_missing_source_citation_is_rejected():
    with pytest.raises(PackError):
        load_packs(("US",), ftc_enabled=False, extra_pack={
            "pack": "x", "version": "1", "jurisdiction": "US", "rules": [{
                "rule_id": "X-1", "trigger": {"categories": ["hate"]},
                "action": "remove", "notice_required": True,
                "appeal_allowed": True, "deadline_hours": 24,
                "evidence_threshold": 0.9, "log_required": True, "priority": 10,
                # source_citation intentionally omitted -> must raise
            }]})


def test_transparency_report_aggregates_actions_notices_appeals():
    eng = PolicyEngine(("EU",), ftc_enabled=True)
    log = EventLog()
    log.append(1, "moderation", -1, "c1", {"action": "remove",
               "rule_id": "EU-ILLEGAL-1", "jurisdiction": "EU",
               "decision_rationale": "r"})
    log.append(1, "notice", 1, "c1", {"rule_id": "EU-ILLEGAL-1",
               "action": "remove", "appeal_allowed": True})
    log.append(2, "appeal", 1, "c1", {"stage": "filed", "rule_id": "EU-ILLEGAL-1"})
    log.append(8, "appeal", 1, "c1", {"stage": "resolved", "granted": True,
               "rule_id": "EU-ILLEGAL-1", "resolution_ticks": 6})
    rep = transparency_report(log, eng)
    assert rep["notices_sent"] == 1
    assert rep["appeals"]["filed"] == 1 and rep["appeals"]["granted"] == 1
    assert rep["pack_versions"]
    cats = rep["actions_by_category"]
    assert any(v["by_action"].get("remove", 0) >= 1 for v in cats.values())
    # rights-impact: the removal is appealable (EU-ILLEGAL-1) and was noticed
    ri = rep["rights_impact"]
    assert ri["actions_total"] >= 1 and ri["appealable_actions"] >= 1
    assert ri["removals"] >= 1 and ri["removals_without_notice"] == 0
