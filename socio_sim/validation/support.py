"""Event-support accounting for rate-type aggregate metrics (audit Phase 5).

A z-distance against a tolerance is meaningless when the rate's event count
is so small that a single chance event moves the observed value by several
tolerances. This module computes, for every rate-type target, the honest
support record:

    numerator / denominator / effective sample size
    zero-denominator indicator
    Wilson 95% interval (method named)
    minimum-support threshold (the n at which the Wilson half-width at the
        TARGET rate equals the target's tolerance)
    adequately_supported flag
    acceptance inclusion + rationale

Measured on fitting/validation seeds of the aggregate profile (2026-07-17;
holdout untouched): appeals filed per run 3-12 vs ~195 required;
ad impressions 119-451 with 0-1 clicks vs ~3,800 required. Both rates are
therefore DESCRIPTIVE DIAGNOSTICS at this scale, not estimable statistics.
Protocol v1's committed verdict is NOT rewritten; the exclusion applies to
the PREDECLARED protocol v2 (see seed_protocol.PROTOCOL_V2), whose holdout
seeds have never been evaluated.
"""

from __future__ import annotations

import math

#: rate-type targets: name -> how to read numerator/denominator out of a
#: run summary.
RATE_METRICS = ("ad_ctr", "appeal_grant_rate")

_Z95 = 1.959964


def wilson_interval(k: int, n: int) -> tuple[float, float]:
    """Wilson score 95% interval for k successes in n trials."""
    if n <= 0:
        return (float("nan"), float("nan"))
    p = k / n
    z2 = _Z95 * _Z95
    denom = 1 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    half = _Z95 * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def min_support_n(target_rate: float, tolerance: float) -> int:
    """The smallest n at which a Wilson-style half-width AT THE TARGET RATE
    is no wider than the tolerance: n >= z^2 p(1-p) / tol^2."""
    p = min(max(float(target_rate), 1e-9), 1 - 1e-9)
    tol = float(tolerance)
    if tol <= 0:
        return 0
    return math.ceil(_Z95 * _Z95 * p * (1 - p) / (tol * tol))


def _counts(summary: dict, metric: str) -> tuple[int, int]:
    if metric == "ad_ctr":
        ads = summary.get("ads") or {}
        n = sum(int(c.get("impressions", 0)) for c in ads.values())
        k = sum(int(c.get("clicks", 0)) for c in ads.values())
        return k, n
    if metric == "appeal_grant_rate":
        ap = summary.get("appeals") or {}
        n = int(ap.get("filed", 0))
        rate = ap.get("granted_rate")
        k = int(round(float(rate) * n)) if (rate == rate and n) else 0
        return k, n
    raise KeyError(metric)


def rate_support(summary: dict, targets: dict) -> dict:
    """Per-rate support records for every rate-type target present."""
    out = {}
    for metric in RATE_METRICS:
        spec = targets.get(metric)
        if spec is None:
            continue
        k, n = _counts(summary, metric)
        lo, hi = wilson_interval(k, n)
        n_min = min_support_n(float(spec["value"]), float(spec["tolerance"]))
        supported = n >= n_min
        out[metric] = {
            "numerator": k,
            "denominator": n,
            "effective_sample_size": n,
            "zero_denominator": n == 0,
            "interval_method": "wilson_score_95",
            "interval": [lo, hi],
            "minimum_support_n": n_min,
            "adequately_supported": supported,
            # v1 keeps the metric in its (committed, failed) acceptance
            # score for reproducibility; v2 predeclares the exclusion.
            "included_in_acceptance_v1": True,
            "included_in_acceptance_v2": False,
            "exclusion_rationale": (
                None if supported else
                f"insufficient event support: {n} events vs the "
                f"{n_min} needed for the 95% interval at the target rate "
                f"to be as tight as the tolerance -- a single chance event "
                "moves the observed rate by multiple tolerances, so a "
                "z-distance is not meaningful at this scale; kept as a "
                "descriptive diagnostic"),
        }
    return out
