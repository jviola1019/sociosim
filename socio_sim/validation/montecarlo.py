"""Monte Carlo replication (Spec §1, §3.9): outcome distributions across
replicates, reported as median + 95% percentile intervals — never a single
scenario as 'the truth'."""

from __future__ import annotations

from dataclasses import replace
from typing import Callable

import numpy as np

from socio_sim.config import RunConfig
from socio_sim.engine import Simulation


def _replicate_metric(args):
    """Top-level worker (picklable for process pools): run one replicate and
    return its metric dict. Each replicate is fully determined by (root_seed,
    replicate_id), so results are identical to the sequential path."""
    cfg, rep, metric_fn = args
    return metric_fn(Simulation(replace(cfg, replicate_id=rep)).run())


def run_replicates(cfg: RunConfig, n_replicates: int, metric_fn: Callable,
                   campaigns_fn: Callable | None = None,
                   workers: int = 1) -> dict:
    """Run `n_replicates` with distinct replicate ids; aggregate each metric
    returned by `metric_fn(result) -> dict[str, float]`.

    workers > 1 runs replicates in a process pool. Because each replicate is
    seeded independently by replicate_id and aggregation is order-independent,
    the parallel result is IDENTICAL to sequential (verified by test). Parallel
    requires picklable metric_fn (top-level) and is skipped when campaigns_fn is
    set (web closures aren't picklable) — it falls back to sequential.
    """
    per_rep: list = []
    if workers and workers > 1 and campaigns_fn is None and n_replicates > 1:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=workers) as ex:
            per_rep = list(ex.map(
                _replicate_metric,
                [(cfg, rep, metric_fn) for rep in range(n_replicates)]))
    else:
        for rep in range(n_replicates):
            rep_cfg = replace(cfg, replicate_id=rep)
            campaigns = campaigns_fn(rep_cfg) if campaigns_fn else None
            per_rep.append(metric_fn(Simulation(rep_cfg, campaigns=campaigns).run()))

    collected: dict = {}
    for md in per_rep:
        for name, value in md.items():
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
