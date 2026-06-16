"""Advertiser campaigns and creatives (Spec §3.7).

Bids are per-impression. Targeting may name age groups and topics; anything in
SENSITIVE_KEYS counts as sensitive-data targeting and is stripped in EU mode
by rule EU-ADS-SENS-1.
"""

from __future__ import annotations

from dataclasses import dataclass, field

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
    holdout_fraction: float | None = None  # None -> use RunConfig.holdout_fraction
    ftc_override: bool | None = None  # None -> use RunConfig.ftc_compliance
    _creative_counter: int = 0

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
