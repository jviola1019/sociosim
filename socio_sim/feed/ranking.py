"""Feed ranking engine (Spec §3.5).

Strategies: chronological, personalized (weighted feature score), random.
Every impression is logged with its strategy, score, and feature vector so an
analyst can audit exactly why a post was shown. EU mode: opted-out agents are
always served chronologically (DSA non-personalised feed right).
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np

from socio_sim.agents.personas import Personas
from socio_sim.agents.state import AgentState
from socio_sim.config import RunConfig
from socio_sim.content.items import ContentItem
from socio_sim.logs.events import EventLog

#: Personalized-score weights (scenario tuning knobs).
WEIGHTS = {
    "recency": 0.30,
    "affinity": 0.25,
    "engagement": 0.30,
    "trust": 0.15,
}
DOWNRANK_PENALTY = 0.3
RECENCY_HALF_LIFE_TICKS = 12.0


class FeedRanker:
    def __init__(self, cfg: RunConfig, personas: Personas, state: AgentState,
                 log: EventLog, rng: np.random.Generator):
        self.cfg = cfg
        self.personas = personas
        self.state = state
        self.log = log
        self.rng = rng
        # (agent -> author -> engagement count); affinity feature source.
        self._engagements: dict = defaultdict(lambda: defaultdict(int))

    def record_engagement(self, agent_id: int, author_id: int):
        self._engagements[agent_id][author_id] += 1

    # -- scoring ----------------------------------------------------------
    def _features(self, agent_id: int, item: ContentItem, tick: int) -> dict:
        recency = float(np.exp(-(tick - item.tick) / RECENCY_HALF_LIFE_TICKS))
        counts = self._engagements[agent_id]
        total = sum(counts.values()) or 1
        affinity = counts.get(item.author_id, 0) / total
        interest = float(self.personas.interests[agent_id, item.topic])
        belief = float(self.state.beliefs[agent_id, item.topic])
        engagement = interest * (1.0 - abs(item.stance - belief) / 2.0)
        if 0 <= item.author_id < self.personas.n:
            trust = float(self.personas.trust[item.author_id])
            if self.personas.influencer[item.author_id]:
                trust = min(1.0, trust + 0.2)
        else:
            trust = 0.5
        return {"recency": recency, "affinity": affinity,
                "engagement": engagement, "trust": trust}

    def _score(self, features: dict, item: ContentItem) -> float:
        s = sum(WEIGHTS[k] * features[k] for k in WEIGHTS)
        if item.status == "downranked":
            s *= DOWNRANK_PENALTY
        return s

    # -- serving ----------------------------------------------------------
    def serve(self, agent_id: int, candidates: list, ads: list, tick: int,
              opted_out: bool = False,
              exploration_pool: list | None = None) -> list:
        visible = [c for c in candidates if c.status != "removed"]
        strategy = self.cfg.feed_strategy
        if opted_out:
            strategy = "chronological"

        scored: list[tuple[float, dict, ContentItem]] = []
        for item in visible:
            features = self._features(agent_id, item, tick)
            if strategy == "chronological":
                score = float(item.tick)
            elif strategy == "random":
                score = float(self.rng.random())
            else:
                score = self._score(features, item)
            scored.append((score, features, item))
        scored.sort(key=lambda t: (-t[0], t[2].id))
        feed = scored[: self.cfg.feed_size]

        # Bandit exploration: with prob ε replace the tail slot with an
        # unseen-author candidate (exploration_pool).
        if (strategy == "personalized" and exploration_pool
                and self.rng.random() < self.cfg.exploration_epsilon):
            pool = [p for p in exploration_pool if p.status != "removed"]
            if pool:
                pick = pool[int(self.rng.integers(0, len(pool)))]
                features = self._features(agent_id, pick, tick)
                slot = (float("-inf"), {**features, "explored": True}, pick)
                feed = feed[:-1] + [slot] if feed else [slot]

        # Interleave ads at fixed slots.
        items: list[tuple] = list(feed)
        for i, ad in enumerate(ads):
            pos = (i + 1) * self.cfg.ad_slot_interval - 1
            ad_entry = (0.0, {"ad": True}, ad)
            if pos <= len(items):
                items.insert(pos, ad_entry)
            else:
                items.append(ad_entry)

        result = []
        for position, (score, features, item) in enumerate(items):
            result.append(item)
            self.log.append(tick=tick, kind="impression", actor_id=agent_id,
                            content_id=item.id, data={
                                "position": position,
                                "strategy": "ad" if features.get("ad") else strategy,
                                "score": round(float(score), 6),
                                "features": {k: round(float(v), 6)
                                             for k, v in features.items()
                                             if isinstance(v, (int, float))},
                            })
        return result
