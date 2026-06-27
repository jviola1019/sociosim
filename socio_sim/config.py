"""Typed run configuration with validation, profiles, and canonical hashing.

The config hash anchors the run manifest: two runs with equal hashes and equal
root seeds must produce identical event streams (see logs/replay.py).
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field, fields as dataclass_fields

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
    # Dynamic-graph evolution (per active agent, per day). All 0 => static graph
    # (default; determinism baselines preserved). >0 enables follow/unfollow/churn.
    follow_rate: float = 0.0       # P(add a tie via triadic closure)
    unfollow_rate: float = 0.0     # P(drop a random current tie)
    churn_rate: float = 0.0        # P(agent permanently deactivates)

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

    @classmethod
    def calibrated(cls, **overrides) -> "RunConfig":
        """History-matched profile: a Holme-Kim graph (m=5, p=0.7) keeps the
        bundled benchmark calibration-consistent (current default I=1.25 < 3.0;
        see CALIBRATION_REPORT.md). Quick scale by default."""
        base = dict(n_agents=1_000, n_ticks=7 * 24, n_replicates=20,
                    graph_kind="plc", graph_params={"m": 5, "p": 0.7})
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
        for key in ("category_base_rates", "classifier_targets"):
            val = d.get(key)
            if isinstance(val, dict):
                ordered = {c: val[c] for c in CATEGORIES if c in val}
                ordered.update({k: val[k] for k in sorted(val) if k not in ordered})
                d[key] = ordered
        beh = d.get("behavior")
        if isinstance(beh, dict):       # rebuild nested dataclass from manifest
            d["behavior"] = BehaviorParams(**beh)
        return cls(**d)

    def config_hash(self) -> str:
        behavioral = self.to_dict()
        behavioral.pop("out_dir", None)
        if behavioral.get("classifier_mode") == "trained":
            behavioral.pop("classifier_targets", None)
        canon = json.dumps(behavioral, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canon.encode()).hexdigest()

    # -- validation -------------------------------------------------------
    def validate(self) -> "RunConfig":
        def fail(fieldname: str, why: str):
            raise ConfigError(f"{fieldname}: {why}")

        def require_int(fieldname: str, value) -> int:
            if isinstance(value, bool):
                fail(fieldname, "must be an integer")
            if isinstance(value, float) and not value.is_integer():
                fail(fieldname, "must be an integer")
            try:
                return int(value)
            except (TypeError, ValueError):
                fail(fieldname, "must be an integer")

        def require_float(fieldname: str, value) -> float:
            if isinstance(value, bool):
                fail(fieldname, "must be numeric")
            try:
                parsed = float(value)
            except (TypeError, ValueError):
                fail(fieldname, "must be numeric")
            if not math.isfinite(parsed):
                fail(fieldname, "must be finite")
            return parsed

        n_agents = require_int("n_agents", self.n_agents)
        n_ticks = require_int("n_ticks", self.n_ticks)
        tick_hours = require_int("tick_hours", self.tick_hours)
        n_topics = require_int("n_topics", self.n_topics)
        feed_size = require_int("feed_size", self.feed_size)
        ad_slot_interval = require_int("ad_slot_interval", self.ad_slot_interval)
        frequency_cap = require_int(
            "ad_frequency_cap_per_day", self.ad_frequency_cap_per_day)
        n_replicates = require_int("n_replicates", self.n_replicates)

        if n_agents <= 0:
            fail("n_agents", "must be positive")
        if n_ticks <= 0:
            fail("n_ticks", "must be positive")
        if tick_hours <= 0 or 24 % tick_hours != 0:
            fail("tick_hours", "must be positive and divide 24")
        if n_topics <= 0:
            fail("n_topics", "must be positive")
        if feed_size <= 0:
            fail("feed_size", "must be positive")
        if ad_slot_interval <= 0:
            fail("ad_slot_interval", "must be positive")
        if frequency_cap <= 0:
            fail("ad_frequency_cap_per_day", "must be positive")
        if n_replicates <= 0:
            fail("n_replicates", "must be positive")
        unknown = set(self.jurisdictions) - VALID_JURISDICTIONS
        if unknown:
            fail("jurisdictions", f"unknown: {sorted(unknown)}")
        if self.feed_strategy not in VALID_FEED_STRATEGIES:
            fail("feed_strategy", f"must be one of {sorted(VALID_FEED_STRATEGIES)}")
        if self.graph_kind not in {"ba", "plc", "ws", "sbm"}:
            fail("graph_kind", "must be one of ['ba', 'plc', 'sbm', 'ws']")
        unknown_adv = set(self.red_team) - set(ADVERSARIES)
        if unknown_adv:
            fail("red_team", f"unknown adversaries: {sorted(unknown_adv)}")
        if self.content_mode not in VALID_CONTENT_MODES:
            fail("content_mode", f"must be one of {sorted(VALID_CONTENT_MODES)}")
        if self.classifier_mode not in VALID_CLASSIFIER_MODES:
            fail("classifier_mode", f"must be one of {sorted(VALID_CLASSIFIER_MODES)}")
        try:
            gp = dict(self.graph_params or {})
        except (TypeError, ValueError):
            fail("graph_params", "must be a mapping")
        if self.graph_kind in {"ba", "plc"}:
            m = require_int("graph_params", gp.get("m", 5))
            if m <= 0 or m >= n_agents:
                fail("graph_params", f"{self.graph_kind}.m must be in [1, n_agents)")
            if self.graph_kind == "plc":
                p = require_float("graph_params", gp.get("p", 0.3))
                if not 0.0 <= p <= 1.0:
                    fail("graph_params", "plc.p must be in [0, 1]")
        elif self.graph_kind == "ws":
            k = require_int("graph_params", gp.get("k", 10))
            p = require_float("graph_params", gp.get("p", 0.05))
            if k <= 0 or k >= n_agents:
                fail("graph_params", "ws.k must be in [1, n_agents)")
            if not 0.0 <= p <= 1.0:
                fail("graph_params", "ws.p must be in [0, 1]")
        elif self.graph_kind == "sbm":
            try:
                sizes = [require_int("graph_params", s)
                         for s in list(gp.get("block_sizes", []))]
            except TypeError:
                fail("graph_params", "sbm.block_sizes must be a sequence")
            try:
                p_matrix = list(gp.get("p_matrix", []))
            except TypeError:
                fail("graph_params", "sbm.p_matrix must be a square sequence")
            if not sizes or any(s <= 0 for s in sizes):
                fail("graph_params", "sbm.block_sizes must be positive")
            if sum(sizes) != n_agents:
                fail("graph_params", "sbm.block_sizes must sum to n_agents")
            if len(p_matrix) != len(sizes):
                fail("graph_params", "sbm.p_matrix must match block_sizes")
            for row in p_matrix:
                try:
                    row_vals = list(row)
                except TypeError:
                    fail("graph_params", "sbm.p_matrix must be square")
                if len(row_vals) != len(sizes):
                    fail("graph_params", "sbm.p_matrix must be square")
                for raw_p in row_vals:
                    p = require_float("graph_params", raw_p)
                    if not 0.0 <= p <= 1.0:
                        fail("graph_params",
                             "sbm.p_matrix probabilities must be in [0, 1]")
        if (self.content_mode in {"ollama", "openai_compatible"}
                and self.llm_base_url):
            from socio_sim.security import validate_llm_url
            try:
                validate_llm_url(self.llm_base_url)
            except ValueError as exc:
                fail("llm_base_url", str(exc))
        from socio_sim.validation.targets import available_benchmarks
        if self.benchmark not in available_benchmarks():
            fail("benchmark", f"must be one of {available_benchmarks()}")
        for rname in ("follow_rate", "unfollow_rate", "churn_rate"):
            if not 0.0 <= require_float(rname, getattr(self, rname)) <= 1.0:
                fail(rname, "must be in [0, 1]")
        for name in (
            "eu_optout_rate",
            "exploration_epsilon",
            "holdout_fraction",
            "homophily_rewire_fraction",
            "human_review_accuracy",
            "appeal_grant_fp_rate",
        ):
            v = require_float(name, getattr(self, name))
            if not (0.0 <= v <= 1.0):
                fail(name, "must be in [0, 1]")
        for cat, rate in self.category_base_rates.items():
            if not (0.0 <= require_float("category_base_rates", rate) <= 1.0):
                fail("category_base_rates", f"{cat} rate must be in [0, 1]")
        for cat, t in self.classifier_targets.items():
            for k in ("precision", "recall"):
                v = require_float("classifier_targets", t.get(k, -1))
                if not (0.0 < v <= 1.0):
                    fail("classifier_targets", f"{cat}.{k} must be in (0, 1]")
        probability_fields = {
            "p_post_given_active", "p_share_given_engaged", "p_flag_scale",
            "fatigue_decay_per_tick", "engagement_base", "spammer_post_prob",
            "amplifier_misinfo_prob", "brigade_flag_prob",
        }
        nonnegative_fields = {
            "impression_fatigue", "recent_window_ticks",
            "exploration_pool_size", "trusted_review_delay_ticks",
        }
        for f in dataclass_fields(self.behavior):
            value = getattr(self.behavior, f.name)
            parsed = require_float("behavior", value)
            if f.name in probability_fields and not (0.0 <= parsed <= 1.0):
                fail("behavior", f"{f.name} must be in [0, 1]")
            if f.name in nonnegative_fields and parsed < 0.0:
                fail("behavior", f"{f.name} must be non-negative")
        amplifier_gain = require_float(
            "behavior", self.behavior.amplifier_stance_gain)
        if amplifier_gain < 0.0:
            fail("behavior", "amplifier_stance_gain must be non-negative")
        return self
