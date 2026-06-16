"""History matching + ABC rejection calibration (Spec §3.9).

History matching rules out implausible parameter regions first (implausibility
I = max standardized discrepancy, conventional cutoff I < 3); ABC rejection
then keeps the closest fraction of survivors as an empirical posterior with
credible intervals.
"""

from __future__ import annotations

from typing import Callable

import numpy as np
from scipy.stats import qmc


def implausibility(observed: dict, targets: dict) -> float:
    discrepancies = []
    for name, spec in targets.items():
        if name not in observed or not np.isfinite(observed[name]):
            continue
        discrepancies.append(abs(observed[name] - spec["value"])
                             / spec["tolerance"])
    return max(discrepancies) if discrepancies else float("inf")


def lhs_samples(bounds: dict, n_samples: int, rng: np.random.Generator) -> list:
    names = sorted(bounds)
    sampler = qmc.LatinHypercube(d=len(names),
                                 seed=int(rng.integers(0, 2**31 - 1)))
    unit = sampler.random(n_samples)
    out = []
    for row in unit:
        params = {}
        for j, name in enumerate(names):
            lo, hi = bounds[name]
            params[name] = float(lo + row[j] * (hi - lo))
        out.append(params)
    return out


def history_match(run_fn: Callable[..., dict], bounds: dict, targets: dict,
                  n_samples: int, rng: np.random.Generator,
                  threshold: float = 3.0) -> list:
    """LHS over `bounds`, evaluate `run_fn(params, rng)` -> observed dict,
    keep parameter sets with implausibility < threshold."""
    survivors = []
    for params in lhs_samples(bounds, n_samples, rng):
        observed = run_fn(params, rng)
        i_score = implausibility(observed, targets)
        if i_score < threshold:
            survivors.append({"params": params, "implausibility": i_score,
                              "observed": observed})
    return survivors


def abc_posterior(survivors: list, accept_fraction: float = 0.1) -> dict:
    """ABC rejection: accept the epsilon-closest fraction of survivors; report
    per-parameter empirical posterior median + 95% credible interval."""
    if not survivors:
        raise ValueError("no survivors to build a posterior from")
    ranked = sorted(survivors, key=lambda s: s["implausibility"])
    k = max(int(len(ranked) * accept_fraction), 5)
    accepted = ranked[:k]
    names = sorted(accepted[0]["params"])
    posterior = {}
    for name in names:
        values = np.array([s["params"][name] for s in accepted])
        posterior[name] = {
            "median": float(np.median(values)),
            "ci": (float(np.percentile(values, 2.5)),
                   float(np.percentile(values, 97.5))),
            "n_accepted": len(values),
        }
    return posterior
