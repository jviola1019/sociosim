"""Policy-as-code engine (Spec §3.6).

Loads jurisdiction rule packs (YAML), evaluates them against classified
content, and composes decisions: the highest-priority terminal action wins
while every side obligation (notices, escalations, logging, labels) is
preserved. Severe categories with no matching rule fail closed — they
escalate with a POLICY-GAP marker rather than passing silently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from socio_sim.content.items import ContentItem

PACK_FILES = {
    "US": "us_section230.yaml",
    "EU": "eu_dsa.yaml",
    "CN": "cn_ai_label.yaml",
}
FTC_PACK_FILE = "ftc.yaml"

REQUIRED_RULE_FIELDS = (
    "rule_id", "trigger", "action", "notice_required", "appeal_allowed",
    "deadline_hours", "evidence_threshold", "log_required", "priority",
)

#: Actions that decide an item's fate; higher wins composition.
TERMINAL_PRIORITY = ("remove", "block_ad", "downrank", "add_platform_label", "label")

#: Categories that must never pass unhandled (fail-closed floor).
SEVERE_CATEGORIES = ("self_harm", "illegal_goods")
SEVERE_FLOOR_SCORE = 0.5


class PackError(ValueError):
    """Raised when a rule pack fails schema validation."""


@dataclass
class PolicyDecision:
    rule_id: str
    jurisdiction: str
    action: str
    notice_required: bool
    appeal_allowed: bool
    deadline_hours: int
    log_required: bool
    priority: int
    rationale: str
    immunity: str | None = None
    retention_months: int = 0
    matched_categories: list = field(default_factory=list)


def _validate_pack(pack: dict):
    for key in ("pack", "version", "jurisdiction", "rules"):
        if key not in pack:
            raise PackError(f"pack missing top-level field: {key}")
    for rule in pack["rules"]:
        for f in REQUIRED_RULE_FIELDS:
            if f not in rule:
                raise PackError(
                    f"rule {rule.get('rule_id', '<unnamed>')} missing field: {f}")
        trig = rule["trigger"]
        if not trig.get("categories") and not trig.get("conditions"):
            raise PackError(
                f"rule {rule['rule_id']}: trigger needs categories or conditions")


def load_packs(jurisdictions, ftc_enabled: bool, extra_pack: dict | None = None):
    packs = []
    pack_dir = Path(__file__).parent / "packs"
    files = [PACK_FILES[j] for j in jurisdictions]
    if ftc_enabled:
        files.append(FTC_PACK_FILE)
    for fname in files:
        pack = yaml.safe_load((pack_dir / fname).read_text(encoding="utf-8"))
        _validate_pack(pack)
        packs.append(pack)
    if extra_pack is not None:
        _validate_pack(extra_pack)
        packs.append(extra_pack)
    return packs


def _condition_holds(name: str, item: ContentItem, context: dict) -> bool:
    if name == "user_flagged":
        return bool(context.get("user_flagged"))
    if name == "is_ad":
        return bool(context.get("is_ad") or item.sponsored)
    if name == "targets_minor":
        return bool(context.get("targets_minor"))
    if name == "sensitive_targeting":
        return bool(context.get("sensitive_targeting"))
    if name == "ai_generated_unlabeled":
        return not item.explicit_label
    if name == "sponsored_without_disclosure":
        return item.sponsored and not item.disclosure_present
    if name == "good_faith":
        return bool(context.get("good_faith", True))
    raise PackError(f"unknown trigger condition: {name}")


class PolicyEngine:
    def __init__(self, jurisdictions=("US",), ftc_enabled: bool = True,
                 extra_pack: dict | None = None):
        self.jurisdictions = tuple(jurisdictions)
        self.packs = load_packs(self.jurisdictions, ftc_enabled, extra_pack)

    def pack_versions(self) -> dict:
        return {p["pack"]: p["version"] for p in self.packs}

    def _effective_scores(self, item: ContentItem, scores: dict) -> dict:
        eff = dict(scores)
        # CN detection path: implicit metadata watermarks and explicit labels
        # identify synthetic content with certainty.
        if item.implicit_watermark is not None or item.explicit_label:
            eff["ai_generated"] = 1.0
        return eff

    def evaluate(self, item: ContentItem, scores: dict,
                 context: dict) -> list[PolicyDecision]:
        eff = self._effective_scores(item, scores)
        decisions: list[PolicyDecision] = []
        matched_severe: set = set()

        for pack in self.packs:
            for rule in pack["rules"]:
                trig = rule["trigger"]
                threshold = float(rule["evidence_threshold"])

                conditions = trig.get("conditions", [])
                if not all(_condition_holds(c, item, context) for c in conditions):
                    continue

                cats = trig.get("categories", [])
                hit_cats = [c for c in cats if eff.get(c, 0.0) >= threshold]
                if cats and not hit_cats:
                    continue

                if hit_cats:
                    top = max(hit_cats, key=lambda c: eff[c])
                    why = f"{top} score {eff[top]:.2f} >= {threshold}"
                    matched_severe.update(c for c in hit_cats
                                          if c in SEVERE_CATEGORIES)
                else:
                    why = f"conditions met: {', '.join(conditions)}"

                decisions.append(PolicyDecision(
                    rule_id=rule["rule_id"],
                    jurisdiction=pack["jurisdiction"],
                    action=rule["action"],
                    notice_required=bool(rule["notice_required"]),
                    appeal_allowed=bool(rule["appeal_allowed"]),
                    deadline_hours=int(rule["deadline_hours"]),
                    log_required=bool(rule["log_required"]),
                    priority=int(rule["priority"]),
                    rationale=f"{rule['rule_id']}: {why}; action={rule['action']}",
                    immunity=rule.get("immunity"),
                    retention_months=int(rule.get("retention_months", 0)),
                    matched_categories=hit_cats,
                ))

        # Fail closed: severe signal with no rule coverage escalates.
        for cat in SEVERE_CATEGORIES:
            if eff.get(cat, 0.0) >= SEVERE_FLOOR_SCORE and cat not in matched_severe:
                decisions.append(PolicyDecision(
                    rule_id="POLICY-GAP",
                    jurisdiction="*",
                    action="escalate",
                    notice_required=False,
                    appeal_allowed=False,
                    deadline_hours=6,
                    log_required=True,
                    priority=999,
                    rationale=(f"POLICY-GAP: severe category {cat} score "
                               f"{eff[cat]:.2f} unmatched by any rule; fail closed"),
                    matched_categories=[cat],
                ))

        decisions.sort(key=lambda d: -d.priority)
        return decisions

    @staticmethod
    def terminal_action(decisions: list[PolicyDecision]) -> str | None:
        for action in TERMINAL_PRIORITY:
            if any(d.action == action for d in decisions):
                return action
        return None
