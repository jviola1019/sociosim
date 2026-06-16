import numpy as np

from socio_sim.agents.personas import Personas
from socio_sim.config import RunConfig
from socio_sim.content.items import ContentItem
from socio_sim.logs.events import EventLog
from socio_sim.moderation.workflow import ModerationSystem
from socio_sim.policy.engine import PolicyEngine
from socio_sim.rng import SeedTree


def setup(jurisdictions=("EU",), **cfg_overrides):
    cfg = RunConfig.test(jurisdictions=jurisdictions, **cfg_overrides)
    personas = Personas.sample(
        50, degrees=np.ones(50), rng=SeedTree(2).generator("agents", 0))
    log = EventLog()
    engine = PolicyEngine(jurisdictions, ftc_enabled=cfg.ftc_enabled)
    mod = ModerationSystem(cfg, engine, personas, log,
                           SeedTree(2).generator("moderation", 0))
    return mod, log, personas


def item(**kw):
    base = dict(id="c1", author_id=1, tick=0, media_type="text", topic=0,
                stance=0.0, text="x")
    base.update(kw)
    return ContentItem(**base)


def test_removal_with_notice_and_rationale():
    mod, log, _ = setup(("EU",))
    it = item(true_categories={"hate"})
    mod.handle(it, scores={"hate": 0.95}, tick=0)
    assert it.status == "removed"
    notices = log.by_kind("notice")
    assert notices and notices[0]["data"]["rule_id"] == "EU-ILLEGAL-1"
    mods = log.by_kind("moderation")
    assert any("EU-ILLEGAL-1" in m["data"]["decision_rationale"] for m in mods)


def test_downrank_and_label_for_misinfo():
    mod, log, _ = setup(("EU",))
    it = item(true_categories={"misinfo"})
    mod.handle(it, scores={"misinfo": 0.7}, tick=0)
    assert it.status == "downranked"
    assert "misinfo" in it.applied_labels


def test_escalation_review_restores_clean_content():
    # Perfect human review: false-positive escalation gets cleared.
    mod, log, _ = setup(("EU",), human_review_accuracy=1.0,
                        human_review_delay_ticks=2)
    clean = item(id="clean", true_categories=set())
    mod.handle(clean, scores={"harassment": 0.6}, tick=0,
               context={"user_flagged": True})
    assert mod.pending_reviews
    mod.process_queues(tick=1)
    assert mod.pending_reviews  # not due yet
    mod.process_queues(tick=2)
    assert not mod.pending_reviews
    reviews = [e for e in log.by_kind("moderation")
               if e["data"].get("stage") == "human_review"]
    assert reviews and reviews[0]["data"]["outcome"] == "cleared"


def test_escalation_review_removes_true_violation():
    mod, log, _ = setup(("EU",), human_review_accuracy=1.0,
                        human_review_delay_ticks=1)
    bad = item(id="bad", true_categories={"harassment"})
    mod.handle(bad, scores={"harassment": 0.6}, tick=0,
               context={"user_flagged": True})
    mod.process_queues(tick=1)
    assert bad.status == "removed"


def test_appeal_reverses_false_positive():
    mod, log, personas = setup(("EU",), appeal_grant_fp_rate=1.0,
                               human_review_delay_ticks=1)
    personas.moderation_attitude[:] = 1.0  # always appeal
    fp = item(id="fp", true_categories=set())  # classifier FP on hate
    mod.handle(fp, scores={"hate": 0.95}, tick=0)
    assert fp.status == "removed"
    assert mod.pending_appeals
    mod.process_queues(tick=1)
    assert fp.status == "visible"
    appeals = log.by_kind("appeal")
    assert any(a["data"]["stage"] == "resolved" and a["data"]["granted"]
               for a in appeals)


def test_deadline_miss_recorded():
    mod, log, _ = setup(("EU",), human_review_delay_ticks=72,
                        human_review_accuracy=1.0)
    bad = item(id="late", true_categories={"self_harm"})
    # Borderline score: only the flag/escalation path fires (below 0.9 removal)
    mod.handle(bad, scores={"self_harm": 0.6}, tick=0,
               context={"user_flagged": True})
    mod.process_queues(tick=72)
    reviews = [e for e in log.by_kind("moderation")
               if e["data"].get("stage") == "human_review"]
    assert reviews and reviews[0]["data"]["deadline_missed"] is True


def test_determinism():
    def run():
        mod, log, personas = setup(("EU",))
        personas.moderation_attitude[:] = 0.5
        for i in range(30):
            it = item(id=f"c{i}", true_categories={"hate"} if i % 3 else set())
            mod.handle(it, scores={"hate": 0.95}, tick=0)
        mod.process_queues(tick=10)
        return log.stream_hash()
    assert run() == run()
