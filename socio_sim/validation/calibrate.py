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
    discrepancies = [c["z"] for c in implausibility_components(observed, targets)]
    return max(discrepancies) if discrepancies else float("inf")


def implausibility_components(observed: dict, targets: dict) -> list[dict]:
    components = []
    for name, spec in targets.items():
        if name not in observed or not np.isfinite(observed[name]):
            continue
        target = float(spec["value"])
        tolerance = float(spec["tolerance"])
        if not tolerance > 0:
            # A zero/negative tolerance is undefined for a standardized
            # discrepancy; skip rather than inject inf/NaN into max().
            continue
        z = abs(float(observed[name]) - target) / tolerance
        components.append({
            "metric": name,
            "observed": float(observed[name]),
            "target": target,
            "tolerance": tolerance,
            "z": float(z),
        })
    return components


def dominant_implausibility_metric(components: list[dict]) -> str | None:
    if not components:
        return None
    return max(components, key=lambda c: c["z"])["metric"]


def _scale(unit, bounds: dict, names: list) -> list:
    out = []
    for row in unit:
        out.append({name: float(bounds[name][0]
                                + row[j] * (bounds[name][1] - bounds[name][0]))
                    for j, name in enumerate(names)})
    return out


def lhs_samples(bounds: dict, n_samples: int, rng: np.random.Generator) -> list:
    names = sorted(bounds)
    sampler = qmc.LatinHypercube(d=len(names),
                                 seed=int(rng.integers(0, 2**31 - 1)))
    return _scale(sampler.random(n_samples), bounds, names)


def sobol_samples(bounds: dict, n_samples: int, rng: np.random.Generator) -> list:
    """Balanced low-discrepancy Sobol design (2^m points, m chosen so 2^m >=
    n_samples) — better space-filling than LHS for variance-based sensitivity."""
    import math
    names = sorted(bounds)
    sampler = qmc.Sobol(d=len(names), scramble=True,
                        seed=int(rng.integers(0, 2**31 - 1)))
    m = max(1, math.ceil(math.log2(max(n_samples, 2))))
    return _scale(sampler.random_base2(m), bounds, names)


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
