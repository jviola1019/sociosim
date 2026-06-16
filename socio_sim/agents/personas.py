"""Synthetic agent personas, stored columnar for vectorized ticks (Spec §3.3).

Personas are entirely synthetic — never derived from real individuals.
Distribution choices are documented inline; all are calibration knobs.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

#: Hourly activity multipliers, normalized to mean 1. Shape follows the
#: circadian literature: peak late afternoon/evening (~16-19h), trough ~04-06h.
_raw = np.array([
    0.55, 0.40, 0.30, 0.25, 0.20, 0.22, 0.35, 0.60,  # 00-07
    0.90, 1.05, 1.10, 1.15, 1.25, 1.20, 1.15, 1.30,  # 08-15
    1.55, 1.65, 1.60, 1.50, 1.45, 1.35, 1.10, 0.85,  # 16-23
])
DIURNAL_CURVE = _raw / _raw.mean()

AGE_GROUPS = np.array(["13-17", "18-24", "25-34", "35-49", "50-64", "65+"])
AGE_PROBS = np.array([0.08, 0.18, 0.26, 0.25, 0.15, 0.08])


@dataclass
class Personas:
    age_group: np.ndarray        # str categorical
    is_minor: np.ndarray         # bool
    ideology: np.ndarray         # (n, 2) in [-1, 1]
    trust: np.ndarray            # [0, 1]
    activity: np.ndarray         # [0, 1], heavy-tailed (base posts/hour propensity)
    ad_responsiveness: np.ndarray  # [0, 1]
    moderation_attitude: np.ndarray  # [0, 1]; higher = more likely to flag & appeal
    influencer: np.ndarray       # bool, top ~1% by degree
    vulnerable: np.ndarray       # bool flag for fairness diagnostics
    interests: np.ndarray        # (n, n_topics) preference weights, rows sum to 1

    @property
    def n(self) -> int:
        return len(self.trust)

    @classmethod
    def sample(cls, n: int, degrees: np.ndarray, rng: np.random.Generator,
               n_topics: int = 8) -> "Personas":
        age_group = rng.choice(AGE_GROUPS, size=n, p=AGE_PROBS)
        is_minor = age_group == "13-17"
        ideology = np.clip(rng.normal(0.0, 0.45, size=(n, 2)), -1, 1)
        trust = rng.beta(2, 2, size=n)
        # Lognormal heavy tail scaled into [0, 1]; median ≈ a few posts/day.
        raw_activity = rng.lognormal(mean=-3.2, sigma=1.0, size=n)
        activity = np.clip(raw_activity, 0, 1)
        ad_responsiveness = rng.beta(2, 5, size=n)
        moderation_attitude = rng.uniform(0, 1, size=n)
        cutoff = np.quantile(degrees, 0.99)
        influencer = degrees >= cutoff
        vulnerable = is_minor | (rng.random(n) < 0.05)
        interests = rng.dirichlet(np.ones(n_topics) * 0.7, size=n)
        return cls(age_group, is_minor, ideology, trust, activity,
                   ad_responsiveness, moderation_attitude, influencer,
                   vulnerable, interests)

    def active_mask(self, hour: int, rng: np.random.Generator) -> np.ndarray:
        """Vectorized Bernoulli draw: P(active) = activity × diurnal[hour]."""
        p = np.clip(self.activity * DIURNAL_CURVE[hour % 24], 0, 1)
        return rng.random(self.n) < p

    def group_labels(self) -> dict:
        """Grouping keys for fairness diagnostics."""
        ideology_bucket = np.where(
            self.ideology[:, 0] < -0.33, "left",
            np.where(self.ideology[:, 0] > 0.33, "right", "center"),
        )
        return {
            "age_group": self.age_group,
            "ideology": ideology_bucket,
            "vulnerable": np.where(self.vulnerable, "vulnerable", "general"),
        }
