"""Moderation workflows (Spec §3.6): apply policy decisions, run escalation
and appeal queues with a simulated human reviewer, track deadlines.

Every action logs a structured `decision_rationale` (rule ids + scores +
thresholds) — never free-form reasoning.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from socio_sim.config import RunConfig
from socio_sim.content.items import ContentItem
from socio_sim.logs.events import EventLog
from socio_sim.policy.engine import PolicyDecision, PolicyEngine


@dataclass
class _Review:
    item: ContentItem
    decision: PolicyDecision
    filed_tick: int
    due_tick: int


@dataclass
class _Appeal:
    item: ContentItem
    decision: PolicyDecision
    was_false_positive: bool
    filed_tick: int
    due_tick: int


class ModerationSystem:
    def __init__(self, cfg: RunConfig, engine: PolicyEngine, personas,
                 log: EventLog, rng: np.random.Generator):
        self.cfg = cfg
        self.engine = engine
        self.personas = personas
        self.log = log
        self.rng = rng
        self.pending_reviews: list[_Review] = []
        self.pending_appeals: list[_Appeal] = []

    # -- intake -----------------------------------------------------------
    def handle(self, item: ContentItem, scores: dict, tick: int,
               context: dict | None = None) -> list[PolicyDecision]:
        context = context or {}
        decisions = self.engine.evaluate(item, scores, context)
        terminal = self.engine.terminal_action(decisions)

        for d in decisions:
            if d.action == "remove" and item.status != "removed" \
                    and terminal == "remove":
                item.status = "removed"
                self._log_action(item, d, tick)
                self._maybe_notice(item, d, tick)
                self._maybe_appeal(item, d, scores, tick)
            elif d.action == "downrank" and item.status == "visible" \
                    and terminal == "downrank":
                item.status = "downranked"
                self._log_action(item, d, tick)
                self._maybe_notice(item, d, tick)
            elif d.action == "label":
                label = d.matched_categories[0] if d.matched_categories else "policy"
                if label not in item.applied_labels:
                    item.applied_labels.append(label)
                self._log_action(item, d, tick)
            elif d.action == "add_platform_label":
                if not item.platform_label_added:
                    item.platform_label_added = True
                    item.text = "[Platform notice: AI-generated content] " + item.text
                self._log_action(item, d, tick)
                self._maybe_notice(item, d, tick)
            elif d.action == "insert_disclosure":
                if not item.disclosure_present:
                    item.disclosure_present = True
                    item.text = item.text + " #ad (paid partnership)"
                self._log_action(item, d, tick, extra={"ftc_violation": True})
            elif d.action == "escalate":
                self.pending_reviews.append(_Review(
                    item=item, decision=d, filed_tick=tick,
                    due_tick=tick + self.cfg.human_review_delay_ticks))
                self._log_action(item, d, tick, extra={"stage": "escalated"})
                self._maybe_notice(item, d, tick)
            # block_ad / strip_targeting are enforced upstream by the ads module.

        return decisions

    # -- queues -----------------------------------------------------------
    def process_queues(self, tick: int):
        due = [r for r in self.pending_reviews if r.due_tick <= tick]
        self.pending_reviews = [r for r in self.pending_reviews if r.due_tick > tick]
        for review in due:
            self._human_review(review, tick)

        due_appeals = [a for a in self.pending_appeals if a.due_tick <= tick]
        self.pending_appeals = [a for a in self.pending_appeals
                                if a.due_tick > tick]
        for appeal in due_appeals:
            self._resolve_appeal(appeal, tick)

    def _human_review(self, review: _Review, tick: int):
        item, d = review.item, review.decision
        relevant = set(d.matched_categories) & item.true_categories
        truly_violating = bool(relevant) or bool(
            item.true_categories & {"hate", "harassment", "fraud", "misinfo",
                                    "adult", "illegal_goods", "self_harm"})
        correct = self.rng.random() < self.cfg.human_review_accuracy
        verdict_violating = truly_violating if correct else not truly_violating

        if verdict_violating:
            item.status = "removed"
            outcome = "removed"
        else:
            outcome = "cleared"

        deadline_missed = (
            d.deadline_hours > 0
            and (tick - review.filed_tick) * self.cfg.tick_hours > d.deadline_hours
        )
        self.log.append(tick=tick, kind="moderation", actor_id=-1,
                        content_id=item.id, data={
                            "stage": "human_review",
                            "rule_id": d.rule_id,
                            "outcome": outcome,
                            "deadline_missed": deadline_missed,
                            "decision_rationale": (
                                f"{d.rule_id}: human review verdict={outcome}; "
                                f"filed t={review.filed_tick}, resolved t={tick}"),
                        })

    def _resolve_appeal(self, appeal: _Appeal, tick: int):
        grant_p = (self.cfg.appeal_grant_fp_rate
                   if appeal.was_false_positive else 0.05)
        granted = self.rng.random() < grant_p
        if granted:
            appeal.item.status = "visible"
        self.log.append(tick=tick, kind="appeal", actor_id=appeal.item.author_id,
                        content_id=appeal.item.id, data={
                            "stage": "resolved",
                            "granted": bool(granted),
                            "rule_id": appeal.decision.rule_id,
                            "resolution_ticks": tick - appeal.filed_tick,
                        })

    # -- helpers ----------------------------------------------------------
    def _maybe_appeal(self, item: ContentItem, d: PolicyDecision, scores: dict,
                      tick: int):
        if not d.appeal_allowed:
            return
        attitude = float(self.personas.moderation_attitude[item.author_id])
        if self.rng.random() < 0.2 + 0.6 * attitude:
            was_fp = not (set(d.matched_categories) & item.true_categories)
            self.pending_appeals.append(_Appeal(
                item=item, decision=d, was_false_positive=was_fp,
                filed_tick=tick,
                due_tick=tick + self.cfg.human_review_delay_ticks))
            self.log.append(tick=tick, kind="appeal", actor_id=item.author_id,
                            content_id=item.id,
                            data={"stage": "filed", "rule_id": d.rule_id})

    def _maybe_notice(self, item: ContentItem, d: PolicyDecision, tick: int):
        if d.notice_required:
            self.log.append(tick=tick, kind="notice", actor_id=item.author_id,
                            content_id=item.id, data={
                                "rule_id": d.rule_id,
                                "action": d.action,
                                "appeal_allowed": d.appeal_allowed,
                            })

    def _log_action(self, item: ContentItem, d: PolicyDecision, tick: int,
                    extra: dict | None = None):
        if not d.log_required:
            return
        data = {
            "action": d.action,
            "rule_id": d.rule_id,
            "jurisdiction": d.jurisdiction,
            "decision_rationale": d.rationale,
            "immunity": d.immunity,
            "retention_months": d.retention_months,
        }
        if extra:
            data.update(extra)
        self.log.append(tick=tick, kind="moderation", actor_id=-1,
                        content_id=item.id, data=data)
