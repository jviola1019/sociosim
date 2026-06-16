"""Mutable per-agent state: beliefs, fatigue, exposure counters (Spec §3.3)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class AgentState:
    beliefs: np.ndarray        # (n, n_topics) in [-1, 1]
    fatigue: np.ndarray        # (n,) >= 0; dampens engagement & ad response
    ad_exposures_today: np.ndarray  # (n,) int, reset daily for frequency caps

    @classmethod
    def init(cls, n: int, n_topics: int) -> "AgentState":
        return cls(
            beliefs=np.zeros((n, n_topics)),
            fatigue=np.zeros(n),
            ad_exposures_today=np.zeros(n, dtype=int),
        )

    def update_beliefs(self, exposed_stance: np.ndarray, trust: np.ndarray,
                       lr: float = 0.05):
        """Convex shift toward observed content stance, scaled by trust.

        exposed_stance: (n, n_topics) mean stance of content seen this tick
        (zero where nothing was seen on that topic).
        """
        seen = exposed_stance != 0
        shift = lr * trust[:, None] * (exposed_stance - self.beliefs)
        self.beliefs = np.clip(self.beliefs + np.where(seen, shift, 0.0), -1, 1)

    def add_fatigue(self, amount: np.ndarray):
        self.fatigue = self.fatigue + np.maximum(amount, 0)

    def decay_fatigue(self, rate: float = 0.2):
        self.fatigue = self.fatigue * (1 - rate)

    def reset_daily_counters(self):
        self.ad_exposures_today[:] = 0
