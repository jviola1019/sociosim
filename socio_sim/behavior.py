"""Agent/engine behaviour parameters, extracted from hardcoded constants.

Every default here reproduces the prior hardcoded engine value EXACTLY — the
determinism regression guard (tests/test_determinism_regression.py) locks that.
Extracting them makes the model's assumptions explicit, documented, and
sensitivity-testable (validation.sensitivity) / calibratable (validation.calibrate).

PROVENANCE: these are SYNTHETIC EXPLORATORY assumptions, not empirically
calibrated values. They must be sensitivity-tested before any output that
depends on them is treated as more than a scenario assumption (see
KNOWN_LIMITATIONS.md / VALIDATION_REPORT.md). Brief rationale per field inline.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BehaviorParams:
    # Posting / sharing
    p_post_given_active: float = 0.30      # P(post | agent active this tick), non-spammer
    p_share_given_engaged: float = 0.10    # P(reshare | an engaged like) -> cascade branching
    # Moderation interaction
    p_flag_scale: float = 0.30             # user-flag prob = p_flag_scale * moderation_attitude
    # Attention / fatigue
    # impression_fatigue is LOW-INFLUENCE (advanced): Saltelli total-effect ~0.09,
    # an order of magnitude below the other knobs across all outputs (settings
    # audit, docs/MODELS.md §6) — kept as a valid lever but don't calibrate first.
    impression_fatigue: float = 0.005      # fatigue added per impression seen
    fatigue_decay_per_tick: float = 0.05   # multiplicative fatigue decay each tick
    # Feed candidate window / exploration
    recent_window_ticks: int = 48          # how far back posts remain feed candidates
    exploration_pool_size: int = 10        # max unseen-author exploration candidates
    # Engagement
    engagement_base: float = 0.30          # base engagement propensity scalar
    # Moderation: priority review latency for trusted-flagger escalations (DSA Art. 22)
    trusted_review_delay_ticks: int = 1
    # Red-team archetype intensities (Spec 3.10)
    spammer_post_prob: float = 1.0         # spammers post every active tick
    amplifier_misinfo_prob: float = 0.6    # P(amplifier injects misinfo into a post)
    amplifier_stance_gain: float = 1.5     # stance multiplier for amplified posts
    brigade_flag_prob: float = 0.8         # P(brigader bad-faith flags an influencer post)
