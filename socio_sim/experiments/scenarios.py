"""Shipped scenario configurations (Spec §3.10, §3.11).

Policy stress tests, ad/FTC experiments, and the red-team adversary suite.
Each factory returns configs (and campaign factories where relevant) ready
for experiments.compare.compare or validation.montecarlo.
"""

from __future__ import annotations

from socio_sim.ads.campaigns import Campaign
from socio_sim.config import ADVERSARIES, RunConfig
from socio_sim.engine import default_campaigns


def _profile(profile: str, **overrides) -> RunConfig:
    factory = {"standard": RunConfig.standard, "quick": RunConfig.quick,
               "test": RunConfig.test}[profile]
    return factory(**overrides)


def policy_stress_eu_vs_us(profile: str = "quick") -> tuple:
    """Same world, different law: US §230 pack vs EU DSA pack."""
    baseline = _profile(profile, jurisdictions=("US",))
    intervention = _profile(profile, jurisdictions=("EU",))
    return baseline, intervention


def ad_holdout_ftc_toggle(profile: str = "quick") -> tuple:
    """FTC-compliant disclosures vs a non-compliant counterfactual."""
    baseline = _profile(profile, ftc_compliance=True)
    intervention = _profile(profile, ftc_compliance=False)
    return baseline, intervention


def disclosure_evader_campaigns(cfg: RunConfig) -> list[Campaign]:
    """Default campaigns plus one influencer campaign that evades disclosure."""
    campaigns = default_campaigns(cfg)
    campaigns.append(Campaign(
        id="evader", advertiser="ShadyCo", bid=4.0,
        budget=0.02 * cfg.n_agents, base_ctr=0.02, base_cvr=0.05,
        ftc_override=False))
    return campaigns


def auction_gamer_campaigns(cfg: RunConfig) -> list[Campaign]:
    """Default campaigns plus a bid-sniping campaign: outbids everyone with a
    tiny budget, gaming early auctions then collapsing."""
    campaigns = default_campaigns(cfg)
    campaigns.append(Campaign(
        id="sniper", advertiser="SnipeCorp", bid=50.0,
        budget=0.001 * cfg.n_agents, base_ctr=0.001, base_cvr=0.0))
    return campaigns


def red_team_suite(profile: str = "quick") -> dict:
    """One config per adversary archetype, plus matching campaign factories."""
    suite = {}
    for adversary in ADVERSARIES:
        if adversary in ("spammer", "misinfo_amplifier", "brigading_ring"):
            suite[adversary] = {
                "config": _profile(profile, red_team=(adversary,)),
                "campaigns_fn": None,
            }
        elif adversary == "disclosure_evader":
            suite[adversary] = {
                "config": _profile(profile),
                "campaigns_fn": disclosure_evader_campaigns,
            }
        elif adversary == "auction_gamer":
            suite[adversary] = {
                "config": _profile(profile),
                "campaigns_fn": auction_gamer_campaigns,
            }
    return suite
