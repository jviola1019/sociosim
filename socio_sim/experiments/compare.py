"""Baseline-vs-intervention experiment runner (Spec §2 experiment design).

Uses common random numbers: each replicate runs baseline and intervention
with the same replicate_id (and, if configured identically, the same root
seed), so paired deltas isolate the intervention from sampling noise.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Callable

import numpy as np

from socio_sim.config import RunConfig
from socio_sim.engine import Simulation


def compare(baseline_cfg: RunConfig, intervention_cfg: RunConfig,
            n_replicates: int, metric_fn: Callable,
            campaigns_fn: Callable | None = None) -> dict:
    """Returns per-metric paired deltas (intervention - baseline) with
    median and 95% percentile interval across replicates."""
    deltas: dict = {}
    base_vals: dict = {}
    int_vals: dict = {}
    for rep in range(n_replicates):
        b_cfg = replace(baseline_cfg, replicate_id=rep)
        i_cfg = replace(intervention_cfg, replicate_id=rep)
        b = Simulation(b_cfg, campaigns=campaigns_fn(b_cfg)
                       if campaigns_fn else None).run()
        i = Simulation(i_cfg, campaigns=campaigns_fn(i_cfg)
                       if campaigns_fn else None).run()
        mb, mi = metric_fn(b), metric_fn(i)
        for name in mb:
            base_vals.setdefault(name, []).append(float(mb[name]))
            int_vals.setdefault(name, []).append(float(mi[name]))
            deltas.setdefault(name, []).append(float(mi[name]) - float(mb[name]))
    out = {}
    for name, values in deltas.items():
        arr = np.array(values)
        out[name] = {
            "baseline_median": float(np.median(base_vals[name])),
            "intervention_median": float(np.median(int_vals[name])),
            "delta_median": float(np.median(arr)),
            "delta_ci": (float(np.percentile(arr, 2.5)),
                         float(np.percentile(arr, 97.5))),
            "deltas": values,
        }
    return out
