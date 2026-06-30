"""Second-price ad auction with policy constraints (Spec §3.7).

Holdout membership is a stable hash of (campaign, agent, root seed) so RCT
assignment is reproducible and independent of call order.
"""

from __future__ import annotations

import hashlib

import numpy as np

from socio_sim.ads.campaigns import Campaign
from socio_sim.agents.personas import Personas
from socio_sim.agents.state import AgentState
from socio_sim.config import RunConfig
from socio_sim.content.items import ContentItem
from socio_sim.logs.events import EventLog
from socio_sim.policy.engine import PolicyEngine
from socio_sim.rng import SeedTree

RESERVE_PRICE = 0.005  # per impression


class AdSystem:
    def __init__(self, cfg: RunConfig, campaigns: list[Campaign],
                 personas: Personas, state: AgentState, engine: PolicyEngine,
                 log: EventLog, rng: np.random.Generator,
                 baseline_rng: np.random.Generator | None = None,
                 latency_rng: np.random.Generator | None = None):
        self.cfg = cfg
        self.campaigns = campaigns
        self.personas = personas
        self.state = state
        self.engine = engine
        self.log = log
        self.rng = rng
        # Organic-conversion draws use a DEDICATED stream, never `rng` (the
        # auction stream): baseline outcomes must not depend on how many auction
        # draws were consumed, or the holdout stops being a clean counterfactual
        # and replays break. Default keeps standalone construction reproducible.
        self.baseline_rng = (baseline_rng if baseline_rng is not None
                             else SeedTree(cfg.root_seed).generator(
                                 "conversion", cfg.replicate_id))
        # Dedicated stream: conversion latency is metadata only — drawing it does
        # not perturb auction/response decisions (which use self.rng).
        self.latency_rng = (latency_rng if latency_rng is not None
                            else SeedTree(cfg.root_seed).generator(
                                "ad_latency", cfg.replicate_id))
        # Proto-creatives for policy checks (one per campaign, FTC-compliant
        # per config so disclosure rules behave like production creatives).
        self._protos = {c.id: c.make_creative(0, self._compliance(c))
                        for c in campaigns}

    def _compliance(self, campaign: Campaign) -> bool:
        return (campaign.ftc_override if campaign.ftc_override is not None
                else self.cfg.ftc_compliance)

    # -- RCT holdout ------------------------------------------------------
    def in_holdout(self, campaign_id: str, agent_id: int) -> bool:
        campaign = next(c for c in self.campaigns if c.id == campaign_id)
        fraction = (campaign.holdout_fraction
                    if campaign.holdout_fraction is not None
                    else self.cfg.holdout_fraction)
        digest = hashlib.blake2s(
            f"{campaign_id}|{agent_id}|{self.cfg.root_seed}".encode(),
            digest_size=8).digest()
        return int.from_bytes(digest, "big") / 2**64 < fraction

    # -- eligibility ------------------------------------------------------
    def _policy_block(self, campaign: Campaign, agent_id: int, tick: int) -> str | None:
        """Returns blocking rule_id, or None. Sensitive targeting is stripped
        (handled in _targeting_match), not blocking."""
        context = {
            "is_ad": True,
            "targets_minor": bool(self.personas.is_minor[agent_id]),
            "sensitive_targeting": campaign.has_sensitive_targeting(),
        }
        decisions = self.engine.evaluate(self._protos[campaign.id], {}, context)
        for d in decisions:
            if d.action == "strip_targeting":
                self.log.append(tick=tick, kind="ad_auction", actor_id=agent_id,
                                content_id=None, data={
                                    "campaign_id": campaign.id,
                                    "action": "strip_targeting",
                                    "rule_id": d.rule_id,
                                })
            if d.action == "block_ad":
                return d.rule_id
        return None

    def _targeting_strip_sensitive(self) -> bool:
        return "EU" in self.cfg.jurisdictions

    def _targeting_match(self, campaign: Campaign, agent_id: int) -> bool:
        t = campaign.targeting
        if not t:
            return True
        if "age_groups" in t and self.personas.age_group[agent_id] not in t["age_groups"]:
            return False
        if "topics" in t:
            top_interest = int(np.argmax(self.personas.interests[agent_id]))
            if top_interest not in t["topics"]:
                return False
        if "ideology" in t and not self._targeting_strip_sensitive():
            side = "left" if self.personas.ideology[agent_id, 0] < 0 else "right"
            if side != t["ideology"]:
                return False
        # In EU mode sensitive keys are stripped: they never narrow the audience.
        return True

    # -- auction ----------------------------------------------------------
    @staticmethod
    def _effective_bid(campaign: Campaign) -> float:
        return min(float(campaign.bid), float(campaign.budget))

    def run_auction(self, agent_id: int, tick: int) -> ContentItem | None:
        if not self.cfg.ads_enabled:
            return None
        if self.state.ad_exposures_today[agent_id] >= self.cfg.ad_frequency_cap_per_day:
            return None

        bidders = []
        for c in self.campaigns:
            if self._effective_bid(c) < RESERVE_PRICE:
                continue
            if not self._targeting_match(c, agent_id):
                continue
            holdout = self.in_holdout(c.id, agent_id)
            self.log.append(tick=tick, kind="ad_opportunity", actor_id=agent_id,
                            content_id=None, data={
                                "campaign_id": c.id,
                                "holdout": holdout,
                                "eligibility_tick": tick,
                                "randomized_assignment_tick": tick,
                                "observation_start_tick": tick,
                                "observation_end_tick": self.cfg.n_ticks - 1,
                            })
            if holdout:
                continue
            block_rule = self._policy_block(c, agent_id, tick)
            if block_rule:
                self.log.append(tick=tick, kind="ad_auction", actor_id=agent_id,
                                content_id=None, data={
                                    "campaign_id": c.id,
                                    "blocked_rule": block_rule,
                                })
                continue
            bidders.append(c)

        if not bidders:
            return None
        bidders.sort(key=lambda c: (-self._effective_bid(c), c.id))
        winner = bidders[0]
        price = (max(self._effective_bid(bidders[1]), RESERVE_PRICE)
                 if len(bidders) > 1 else RESERVE_PRICE)
        price = min(price, self._effective_bid(winner))
        winner.budget = max(0.0, float(winner.budget) - price)

        creative = winner.make_creative(tick, self._compliance(winner))
        self.state.ad_exposures_today[agent_id] += 1
        self.log.append(tick=tick, kind="ad_auction", actor_id=agent_id,
                        content_id=creative.id, data={
                            "campaign_id": winner.id,
                            "price": price,
                            "n_bidders": len(bidders),
                        })
        return creative

    # -- response model ---------------------------------------------------
    def simulate_response(self, agent_id: int, creative: ContentItem, tick: int):
        campaign = next(c for c in self.campaigns if c.id == creative.campaign_id)
        fatigue_mult = 1.0 / (1.0 + float(self.state.fatigue[agent_id]))
        p_click = np.clip(
            campaign.base_ctr
            * (0.5 + float(self.personas.ad_responsiveness[agent_id]))
            * fatigue_mult, 0, 1)
        if self.rng.random() < p_click:
            self.log.append(tick=tick, kind="ad_click", actor_id=agent_id,
                            content_id=creative.id,
                            data={"campaign_id": campaign.id})
            if self.rng.random() < campaign.base_cvr:
                # Conversion latency (ticks after impression) -> attribution
                # windows become meaningful. Drawn from the dedicated stream.
                latency = int(self.latency_rng.geometric(0.25)) - 1
                conversion_tick = tick + latency
                if conversion_tick >= self.cfg.n_ticks:
                    return
                self.log.append(tick=conversion_tick, kind="ad_conversion",
                                actor_id=agent_id, content_id=creative.id,
                                data={"campaign_id": campaign.id,
                                      "value": campaign.conversion_value,
                                      "impression_tick": tick,
                                      "latency": latency})

    # -- organic baseline -------------------------------------------------
    def simulate_baseline(self, agent_id: int, tick: int):
        """Organic (non-ad) conversion opportunity, run for EVERY agent —
        exposed and holdout alike — so the holdout is a valid counterfactual.

        Conversion probability is the agent's latent `base_conversion`, drawn
        only from `baseline_rng` and independent of any ad exposure. Targeting
        is applied symmetrically so both arms represent the same target
        population. One draw per (agent, matched campaign), fixed campaign
        order -> deterministic and replay-stable. Lift = exposed_rate -
        holdout_rate then isolates the incremental ad effect.
        """
        if not self.cfg.ads_enabled:
            return
        b = float(self.personas.base_conversion[agent_id])
        for c in self.campaigns:
            if not self._targeting_match(c, agent_id):
                continue
            if self.baseline_rng.random() < b:
                self.log.append(tick=tick, kind="organic_conversion",
                                actor_id=agent_id, content_id=None,
                                data={"campaign_id": c.id,
                                      "value": c.conversion_value})
