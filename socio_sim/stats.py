"""Dependency-light proportion-statistics helpers shared across modules.

Kept in its own module so both `analytics.metrics` and `ads.measure` can use
them without an import cycle. Provenance of these intervals is *analytic*
(closed-form), never Monte Carlo across simulation replicates.
"""

from __future__ import annotations

import numpy as np


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple:
    """Wilson score interval for a binomial proportion (default 95%).

    Robust at small n and extreme p, where the Wald interval under-covers.
    Empty sample -> (nan, nan) rather than a fabricated [0, 0].
    """
    if n <= 0:
        return (float("nan"), float("nan"))
    p = successes / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    half = (z * np.sqrt(p * (1 - p) / n + z2 / (4 * n * n))) / denom
    return (float(max(0.0, center - half)), float(min(1.0, center + half)))


def newcombe_diff_ci(x1: int, n1: int, x2: int, n2: int, z: float = 1.96) -> tuple:
    """Newcombe (Wilson-hybrid) interval for the difference p1 - p2.

    Near-nominal coverage at small p / moderate n, unlike the plain Wald
    difference interval (Newcombe 1998). Empty arm -> (nan, nan).
    """
    if n1 <= 0 or n2 <= 0:
        return (float("nan"), float("nan"))
    p1, p2 = x1 / n1, x2 / n2
    l1, u1 = wilson_interval(x1, n1, z)
    l2, u2 = wilson_interval(x2, n2, z)
    diff = p1 - p2
    lo = diff - float(np.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2))
    hi = diff + float(np.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2))
    return (lo, hi)


def two_proportion_p(x1: int, n1: int, x2: int, n2: int) -> float:
    """Two-sided p-value for H0: p1 == p2 (pooled-variance z test).

    Used for lift significance; pair with FDR control across campaigns. Empty
    arm or degenerate pooled variance -> nan / 1.0.
    """
    from scipy import stats as _ss
    if n1 <= 0 or n2 <= 0:
        return float("nan")
    p1, p2 = x1 / n1, x2 / n2
    pp = (x1 + x2) / (n1 + n2)
    se = float(np.sqrt(pp * (1 - pp) * (1 / n1 + 1 / n2)))
    if se == 0:
        return 1.0
    z = (p1 - p2) / se
    return float(2 * _ss.norm.sf(abs(z)))


def benjamini_hochberg(pvalues, alpha: float = 0.05) -> list:
    """Benjamini-Hochberg FDR control. Returns a boolean rejected-mask aligned
    to `pvalues` (preferred over Bonferroni for families of campaign tests)."""
    p = np.asarray(list(pvalues), dtype=float)
    n = p.size
    if n == 0:
        return []
    order = np.argsort(p)
    ranked = p[order]
    thresh = alpha * (np.arange(1, n + 1) / n)
    below = ranked <= thresh
    rejected = np.zeros(n, dtype=bool)
    if below.any():
        kmax = int(np.max(np.where(below)[0]))
        keep = np.zeros(n, dtype=bool)
        keep[: kmax + 1] = True
        rejected[order] = keep
    return [bool(x) for x in rejected]


def prob_diff_positive(x1: int, n1: int, x2: int, n2: int,
                       draws: int = 20000) -> float:
    """P(p1 > p2) under independent Jeffreys Beta posteriors, by Monte Carlo.

    Deterministic (fixed seed) so it does not perturb run reproducibility.
    """
    if n1 <= 0 or n2 <= 0:
        return float("nan")
    rng = np.random.default_rng(0)
    a = rng.beta(0.5 + x1, 0.5 + n1 - x1, draws)
    b = rng.beta(0.5 + x2, 0.5 + n2 - x2, draws)
    return float(np.mean(a > b))
