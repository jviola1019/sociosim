import pytest

from socio_sim.content.items import ContentItem
from socio_sim.policy.engine import PackError, PolicyEngine, load_packs


def item(**kw):
    base = dict(id="c1", author_id=1, tick=0, media_type="text", topic=0,
                stance=0.0, text="x")
    base.update(kw)
    return ContentItem(**base)


def engine(jurisdictions=("US",), ftc=True):
    return PolicyEngine(jurisdictions=jurisdictions, ftc_enabled=ftc)


def test_packs_load_with_versions():
    packs = load_packs(("US", "EU", "CN"), ftc_enabled=True)
    names = {p["pack"] for p in packs}
    assert names == {"us_section230", "eu_dsa", "cn_ai_label", "ftc"}
    for p in packs:
        assert p["version"]
        for r in p["rules"]:
            for field in ("rule_id", "action", "notice_required", "appeal_allowed",
                          "deadline_hours", "evidence_threshold", "log_required",
                          "priority", "trigger"):
                assert field in r, f"{r.get('rule_id')} missing {field}"


def test_us_good_samaritan_removal_immune_no_appeal_required():
    e = engine(("US",))
    decisions = e.evaluate(item(true_categories={"hate"}),
                           scores={"hate": 0.95}, context={})
    terminal = [d for d in decisions if d.action == "remove"]
    assert terminal
    d = terminal[0]
    assert d.rule_id.startswith("US-230-GS")
    assert d.immunity == "good_samaritan"
    assert d.appeal_allowed is False


def test_us_criminal_carveout_escalates():
    e = engine(("US",))
    decisions = e.evaluate(item(true_categories={"illegal_goods"}),
                           scores={"illegal_goods": 0.9}, context={})
    actions = {d.action for d in decisions}
    assert "remove" in actions and "escalate" in actions
    assert any(d.log_required for d in decisions)


def test_eu_illegal_removal_has_notice_appeal_deadline():
    e = engine(("EU",))
    decisions = e.evaluate(item(true_categories={"hate"}),
                           scores={"hate": 0.95}, context={})
    d = next(d for d in decisions if d.action == "remove")
    assert d.notice_required is True
    assert d.appeal_allowed is True
    assert d.deadline_hours == 24


def test_eu_misinfo_downranked_and_labelled_not_removed():
    e = engine(("EU",))
    decisions = e.evaluate(item(true_categories={"misinfo"}),
                           scores={"misinfo": 0.7}, context={})
    actions = {d.action for d in decisions}
    assert "downrank" in actions
    assert "remove" not in actions


def test_eu_user_flag_triggers_review():
    e = engine(("EU",))
    decisions = e.evaluate(item(), scores={"harassment": 0.55},
                           context={"user_flagged": True})
    assert any(d.action == "escalate" for d in decisions)


def test_cn_unlabeled_ai_content_gets_platform_label_and_retention():
    e = engine(("CN",))
    it = item(ai_generated=True, explicit_label=False, implicit_watermark=None,
              true_categories={"ai_generated"})
    decisions = e.evaluate(it, scores={"ai_generated": 0.8}, context={})
    d = next(d for d in decisions if d.action == "add_platform_label")
    assert d.log_required is True
    assert d.retention_months >= 6


def test_cn_labeled_ai_content_no_platform_label():
    e = engine(("CN",))
    it = item(ai_generated=True, explicit_label=True,
              implicit_watermark={"provider": "p", "content_ref": "r"})
    decisions = e.evaluate(it, scores={"ai_generated": 0.8}, context={})
    assert not any(d.action == "add_platform_label" for d in decisions)


def test_ftc_missing_disclosure_flagged():
    e = engine(("US",), ftc=True)
    it = item(sponsored=True, disclosure_present=False,
              true_categories={"sponsored"})
    decisions = e.evaluate(it, scores={"sponsored": 0.9}, context={})
    assert any(d.action == "insert_disclosure" for d in decisions)


def test_ftc_disabled_no_disclosure_rule():
    e = engine(("US",), ftc=False)
    it = item(sponsored=True, disclosure_present=False,
              true_categories={"sponsored"})
    decisions = e.evaluate(it, scores={"sponsored": 0.9}, context={})
    assert not any(d.action == "insert_disclosure" for d in decisions)


def test_fail_closed_severe_category_without_matching_rule():
    # Engine with no packs at all: severe categories must still escalate.
    e = PolicyEngine(jurisdictions=(), ftc_enabled=False)
    decisions = e.evaluate(item(true_categories={"self_harm"}),
                           scores={"self_harm": 0.8}, context={})
    gap = [d for d in decisions if d.action == "escalate"]
    assert gap and gap[0].rule_id == "POLICY-GAP"


def test_composition_highest_priority_terminal_wins():
    e = engine(("EU",))
    # Both illegal (remove, priority high) and misinfo (downrank) trigger
    decisions = e.evaluate(item(true_categories={"hate", "misinfo"}),
                           scores={"hate": 0.95, "misinfo": 0.7}, context={})
    terminals = [d for d in decisions if d.action in ("remove", "downrank")]
    assert [d.action for d in terminals][0] == "remove"
    assert e.terminal_action(decisions) == "remove"


def test_rationale_is_structured_and_short():
    e = engine(("EU",))
    decisions = e.evaluate(item(true_categories={"hate"}),
                           scores={"hate": 0.95}, context={})
    d = decisions[0]
    assert d.rule_id in d.rationale
    assert "0.95" in d.rationale or "0.9" in d.rationale
    assert len(d.rationale) < 200


def test_bad_pack_raises():
    with pytest.raises(PackError):
        load_packs(("US",), ftc_enabled=False,
                   extra_pack={"pack": "broken", "version": "1", "rules": [
                       {"rule_id": "X-1"}]})
