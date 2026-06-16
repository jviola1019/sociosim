"""Monte Carlo replication (Spec §1, §3.9): outcome distributions across
replicates, reported as median + 95% percentile intervals — never a single
scenario as 'the truth'."""

from __future__ import annotations

from dataclasses import replace
from typing import Callable

import numpy as np

from socio_sim.config import RunConfig
from socio_sim.engine import Simulation


def run_replicates(cfg: RunConfig, n_replicates: int,
                   metric_fn: Callable, campaigns_fn: Callable | None = None) -> dict:
    """Run `n_replicates` with distinct replicate ids; aggregate each metric
    returned by `metric_fn(result) -> dict[str, float]`."""
    collected: dict = {}
    for rep in range(n_replicates):
        rep_cfg = replace(cfg, replicate_id=rep)
        campaigns = campaigns_fn(rep_cfg) if campaigns_fn else None
        result = Simulation(rep_cfg, campaigns=campaigns).run()
        for name, value in metric_fn(result).items():
            collected.setdefault(name, []).append(float(value))
    out = {}
    for name, values in collected.items():
        arr = np.array(values)
        out[name] = {
            "median": float(np.median(arr)),
            "ci": (float(np.percentile(arr, 2.5)),
                   float(np.percentile(arr, 97.5))),
            "values": values,
        }
    return out
