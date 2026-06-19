"""Typed run configuration with validation, profiles, and canonical hashing.

The config hash anchors the run manifest: two runs with equal hashes and equal
root seeds must produce identical event streams (see logs/replay.py).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field

from socio_sim.behavior import BehaviorParams

VALID_JURISDICTIONS = {"US", "EU", "CN"}
VALID_FEED_STRATEGIES = {"personalized", "chronological", "random"}
#: noise = calibrated noise model (default, fast, fully synthetic); trained = a
#: REAL numpy classifier trained on category-signal content with measured P/R.
VALID_CLASSIFIER_MODES = {"noise", "trained"}
#: template = deterministic (default); claude = Anthropic API (needs key);
#: ollama / openai_compatible = free, keyless local LLM servers.
VALID_CONTENT_MODES = {"template", "claude", "ollama", "openai_compatible"}

#: Red-team adversary archetypes (Spec §3.10). disclosure_evader and
#: auction_gamer are realized as campaign configurations (experiments.scenarios).
ADVERSARIES = ("spammer", "misinfo_amplifier", "brigading_ring",
               "auction_gamer", "disclosure_evader")

#: Policy-relevant content categories (Spec §3.4).
CATEGORIES = (
    "hate",
    "harassment",
    "fraud",
    "misinfo",
    "adult",
    "illegal_goods",
    "self_harm",
    "political",
    "ad",
    "sponsored",
    "ai_generated",
)


def _default_classifier_targets() -> dict:
    """Per-category classifier operating points (precision/recall)."""
    return {cat: {"precision": 0.90, "recall": 0.85} for cat in CATEGORIES}


def _default_base_rates() -> dict:
    """Ground-truth prevalence of organic content categories."""
    return {
        "hate": 0.010,
        "harassment": 0.015,
        "fraud": 0.008,
        "misinfo": 0.020,
        "adult": 0.010,
        "illegal_goods": 0.003,
        "self_harm": 0.004,
        "political": 0.150,
        "ai_generated": 0.080,
    }


class ConfigError(ValueError):
    """Raised when a RunConfig field is invalid; message names the field."""


@dataclass(frozen=True)
class RunConfig:
    # Scale (approved defaults: standard profile)
    n_agents: int = 10_000
    n_ticks: int = 28 * 24  # hourly ticks
    tick_hours: int = 1
    n_replicates: int = 100
    replicate_id: int = 0
    root_seed: int = 42

    # Jurisdictions & policy
    jurisdictions: tuple = ("US",)
    ftc_enabled: bool = True

    # Feed
    feed_strategy: str = "personalized"
    eu_optout_rate: float = 0.20
    exploration_epsilon: float = 0.10
    feed_size: int = 20
    ad_slot_interval: int = 5

    # Content
    content_mode: str = "template"
    classifier_mode: str = "noise"   # "noise" | "trained" (real numpy classifier)
    n_topics: int = 8
    classifier_targets: dict = field(default_factory=_default_classifier_targets)
    category_base_rates: dict = field(default_factory=_default_base_rates)
    llm_cache_path: str = ""
    llm_model: str = ""          # backend default if blank
    llm_base_url: str = ""       # backend default if blank

    # Ads
    ads_enabled: bool = True
    holdout_fraction: float = 0.10
    ad_frequency_cap_per_day: int = 4
    ftc_compliance: bool = True

    # Graph
    graph_kind: str = "ba"
    graph_params: dict = field(default_factory=lambda: {"m": 5})
    homophily_rewire_fraction: float = 0.15

    # Moderation
    human_review_accuracy: float = 0.92
    human_review_delay_ticks: int = 6
    appeal_grant_fp_rate: float = 0.70

    # Red-team adversaries (subset of experiments.scenarios.ADVERSARIES)
    red_team: tuple = ()

    # Behaviour parameters (extracted, documented, sensitivity-testable knobs)
    behavior: BehaviorParams = field(default_factory=BehaviorParams)

    # Calibration benchmark target set (bundled published aggregates)
    benchmark: str = "default"

    # Output
    out_dir: str = "out"

    # -- profiles ---------------------------------------------------------
    @classmethod
    def standard(cls, **overrides) -> "RunConfig":
        return cls(**overrides)

    @classmethod
    def quick(cls, **overrides) -> "RunConfig":
        base = dict(n_agents=1_000, n_ticks=7 * 24, n_replicates=20)
        base.update(overrides)
        return cls(**base)

    @classmethod
    def test(cls, **overrides) -> "RunConfig":
        base = dict(n_agents=200, n_ticks=48, n_replicates=2)
        base.update(overrides)
        return cls(**base)

    # -- serialization ----------------------------------------------------
    def to_dict(self) -> dict:
        d = asdict(self)  # asdict recurses into the nested BehaviorParams
        d["jurisdictions"] = list(self.jurisdictions)
        d["red_team"] = list(self.red_team)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "RunConfig":
        d = dict(d)
        d["jurisdictions"] = tuple(d.get("jurisdictions", ("US",)))
        d["red_team"] = tuple(d.get("red_team", ()))
        beh = d.get("behavior")
        if isinstance(beh, dict):       # rebuild nested dataclass from manifest
            d["behavior"] = BehaviorParams(**beh)
        return cls(**d)

    def config_hash(self) -> str:
        canon = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canon.encode()).hexdigest()

    # -- validation -------------------------------------------------------
    def validate(self) -> "RunConfig":
        def fail(fieldname: str, why: str):
            raise ConfigError(f"{fieldname}: {why}")

        if self.n_agents <= 0:
            fail("n_agents", "must be positive")
        if self.n_ticks <= 0:
            fail("n_ticks", "must be positive")
        if self.tick_hours <= 0 or 24 % self.tick_hours != 0:
            fail("tick_hours", "must be positive and divide 24")
        if self.n_replicates <= 0:
            fail("n_replicates", "must be positive")
        unknown = set(self.jurisdictions) - VALID_JURISDICTIONS
        if unknown:
            fail("jurisdictions", f"unknown: {sorted(unknown)}")
        if self.feed_strategy not in VALID_FEED_STRATEGIES:
            fail("feed_strategy", f"must be one of {sorted(VALID_FEED_STRATEGIES)}")
        unknown_adv = set(self.red_team) - set(ADVERSARIES)
        if unknown_adv:
            fail("red_team", f"unknown adversaries: {sorted(unknown_adv)}")
        if self.content_mode not in VALID_CONTENT_MODES:
            fail("content_mode", f"must be one of {sorted(VALID_CONTENT_MODES)}")
        if self.classifier_mode not in VALID_CLASSIFIER_MODES:
            fail("classifier_mode", f"must be one of {sorted(VALID_CLASSIFIER_MODES)}")
        from socio_sim.validation.targets import available_benchmarks
        if self.benchmark not in available_benchmarks():
            fail("benchmark", f"must be one of {available_benchmarks()}")
        for name in (
            "eu_optout_rate",
            "exploration_epsilon",
            "holdout_fraction",
            "homophily_rewire_fraction",
            "human_review_accuracy",
            "appeal_grant_fp_rate",
        ):
            v = getattr(self, name)
            if not (0.0 <= v <= 1.0):
                fail(name, "must be in [0, 1]")
        for cat, rate in self.category_base_rates.items():
            if not (0.0 <= rate <= 1.0):
                fail("category_base_rates", f"{cat} rate must be in [0, 1]")
        for cat, t in self.classifier_targets.items():
            for k in ("precision", "recall"):
                if not (0.0 < t.get(k, -1) <= 1.0):
                    fail("classifier_targets", f"{cat}.{k} must be in (0, 1]")
        return self
