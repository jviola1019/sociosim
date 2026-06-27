"""Advertiser campaigns and creatives (Spec §3.7).

Bids are per-impression. Targeting may name age groups and topics; anything in
SENSITIVE_KEYS counts as sensitive-data targeting and is stripped in EU mode
by rule EU-ADS-SENS-1.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from copy import deepcopy
import math

from socio_sim.content.items import ContentItem

SENSITIVE_KEYS = ("ideology", "health", "religion", "sexuality")


@dataclass
class Campaign:
    id: str
    advertiser: str
    bid: float                      # per impression
    budget: float
    targeting: dict = field(default_factory=dict)  # {age_groups: [...], topics: [...], ideology: ...}
    base_ctr: float = 0.01          # benchmark-calibrated click prior
    base_cvr: float = 0.05
    conversion_value: float = 1.0
    ltv_multiplier: float = 3.0     # SYNTHETIC assumption: LTV = value x this
    attribution_window_ticks: int = 168  # credit a conversion only within W ticks of impression
    holdout_fraction: float | None = None  # None -> use RunConfig.holdout_fraction
    ftc_override: bool | None = None  # None -> use RunConfig.ftc_compliance
    _creative_counter: int = 0
    _initial_budget: float | None = field(default=None, init=False, repr=False)

    def __post_init__(self):
        if not str(self.id or "").strip():
            raise ValueError("campaign.id: must be non-empty")
        if not str(self.advertiser or "").strip():
            raise ValueError("campaign.advertiser: must be non-empty")
        self.bid = _finite_float("campaign.bid", self.bid)
        self.budget = _finite_float("campaign.budget", self.budget)
        self.base_ctr = _finite_float("campaign.base_ctr", self.base_ctr)
        self.base_cvr = _finite_float("campaign.base_cvr", self.base_cvr)
        self.conversion_value = _finite_float(
            "campaign.conversion_value", self.conversion_value)
        self.ltv_multiplier = _finite_float(
            "campaign.ltv_multiplier", self.ltv_multiplier)
        if self.bid <= 0:
            raise ValueError("campaign.bid: must be positive")
        if self.budget <= 0:
            raise ValueError("campaign.budget: must be positive")
        if not 0.0 <= self.base_ctr <= 1.0:
            raise ValueError("campaign.base_ctr: must be in [0, 1]")
        if not 0.0 <= self.base_cvr <= 1.0:
            raise ValueError("campaign.base_cvr: must be in [0, 1]")
        if self.conversion_value < 0:
            raise ValueError("campaign.conversion_value: must be non-negative")
        if self.ltv_multiplier < 0:
            raise ValueError("campaign.ltv_multiplier: must be non-negative")
        if not isinstance(self.attribution_window_ticks, int):
            if isinstance(self.attribution_window_ticks, float) and self.attribution_window_ticks.is_integer():
                self.attribution_window_ticks = int(self.attribution_window_ticks)
            else:
                raise ValueError("campaign.attribution_window_ticks: must be an integer")
        if self.attribution_window_ticks < 0:
            raise ValueError("campaign.attribution_window_ticks: must be non-negative")
        if self.holdout_fraction is not None:
            self.holdout_fraction = _finite_float(
                "campaign.holdout_fraction", self.holdout_fraction)
            if not 0.0 <= self.holdout_fraction <= 1.0:
                raise ValueError("campaign.holdout_fraction: must be in [0, 1]")
        if not isinstance(self.targeting, dict):
            raise ValueError("campaign.targeting: must be a mapping")
        self.targeting = deepcopy(self.targeting)
        self._initial_budget = float(self.budget)

    @property
    def initial_budget(self) -> float:
        return float(self._initial_budget if self._initial_budget is not None else self.budget)

    def has_sensitive_targeting(self) -> bool:
        return any(k in self.targeting for k in SENSITIVE_KEYS)

    def make_creative(self, tick: int, ftc_compliance: bool) -> ContentItem:
        self._creative_counter += 1
        text = f"{self.advertiser}: check out our new offer!"
        if ftc_compliance:
            text += " #ad (paid partnership)"
        return ContentItem(
            id=f"ad-{self.id}-{self._creative_counter}",
            author_id=-1,
            tick=tick,
            media_type="text",
            topic=0,
            stance=0.0,
            text=text,
            true_categories={"ad", "sponsored"},
            sponsored=True,
            disclosure_present=ftc_compliance,
            campaign_id=self.id,
        )


def campaign_to_spec(campaign: Campaign) -> dict:
    """JSON-safe constructor args for replay manifests.

    Campaign budgets mutate during a run, so callers should serialize campaigns
    before simulation starts. Private runtime counters are intentionally omitted.
    """
    spec = {}
    for f in fields(Campaign):
        if f.name.startswith("_"):
            continue
        spec[f.name] = deepcopy(getattr(campaign, f.name))
    return spec


def campaigns_from_specs(specs: list[dict] | None) -> list[Campaign] | None:
    if not specs:
        return None
    allowed = {f.name for f in fields(Campaign) if not f.name.startswith("_")}
    return [Campaign(**{k: deepcopy(v) for k, v in spec.items() if k in allowed})
            for spec in specs]


def _finite_float(name: str, value) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name}: must be numeric")
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name}: must be numeric")
    if not math.isfinite(parsed):
        raise ValueError(f"{name}: must be finite")
    return parsed
