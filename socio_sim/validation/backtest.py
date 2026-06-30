"""Held-out aggregate-fit diagnostic (validation-ladder aggregate rung).

Select the graph on a TRAIN subset of the bundled published-aggregate
benchmark, then check whether the HELD-OUT metrics fall within tolerance —
metrics that were never used to choose the parameter. This is a held-out
aggregate sanity check (provenance ``aggregate_fit_check``), distinct from
in-sample aggregate matching; it is not a broad platform-generalization proof.

Uses ONLY bundled public AGGREGATE targets (cited, no individual-level data; see
docs/DATA_MANIFEST.md). Offline, deterministic, no scraping. The same harness
accepts any additional license-clean public aggregate target set registered in
the data manifest.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from socio_sim.analytics.metrics import summarize_run
from socio_sim.config import RunConfig
from socio_sim.engine import Simulation
from socio_sim.validation.calibrate import implausibility
from socio_sim.validation.targets import compute_observed, load_targets

PROVENANCE = "aggregate_fit_check"
_PROFILES = {"test": RunConfig.test, "quick": RunConfig.quick,
             "standard": RunConfig.standard,
             "aggregate_matched_prototype": RunConfig.aggregate_matched_prototype,
             "calibrated": RunConfig.calibrated}

#: Default held-out metrics: a small held-out aggregate check. Passing these is
#: useful face validity, not proof of generalization to a specific platform.
DEFAULT_HOLDOUT = ("degree_tail_exponent", "diurnal_peak_hour")


def leave_out_backtest(benchmark: str = "default", holdout=DEFAULT_HOLDOUT,
                       grid=None, profile: str = "quick", seed: int = 42,
                       **cfg_overrides) -> dict:
    targets = load_targets(benchmark)
    holdout = tuple(h for h in holdout if h in targets)
    train_targets = {k: v for k, v in targets.items() if k not in holdout}
    test_targets = {k: v for k, v in targets.items() if k in holdout}
    base = _PROFILES[profile](jurisdictions=("EU",), root_seed=seed, **cfg_overrides)
    grid = grid or [round(float(p), 2) for p in np.linspace(0.2, 0.9, 8)]

    # --- TRAIN: pick the graph triad prob p that best fits the TRAIN metrics ---
    best = None
    for p in grid:
        cfg = replace(base, graph_kind="plc", graph_params={"m": 5, "p": float(p)})
        res = Simulation(cfg).run()
        obs = compute_observed(res, summarize_run(res))
        i_train = implausibility(obs, train_targets)
        if best is None or i_train < best["i_train"]:
            best = {"p": float(p), "i_train": float(i_train), "obs": obs}

    # --- TEST: score the held-out metrics (never used to pick p) ---
    obs = best["obs"]
    rows = []
    for k, spec in test_targets.items():
        o = obs.get(k)
        z = (abs(o - spec["value"]) / spec["tolerance"]
             if (o is not None and o == o) else float("nan"))
        rows.append({"metric": k, "observed": o, "target": spec["value"],
                     "tolerance": spec["tolerance"], "z": z,
                     "within_tolerance": bool(np.isfinite(z) and z <= 1.0)})
    return {
        "provenance": PROVENANCE, "benchmark": benchmark, "profile": profile,
        "chosen_p": best["p"], "train_metrics": sorted(train_targets),
        "holdout_metrics": sorted(test_targets),
        "implausibility_train": best["i_train"],
        "implausibility_test": float(implausibility(obs, test_targets)),
        "test": rows, "test_pass": all(r["within_tolerance"] for r in rows),
    }


def _fmt(x, d=4):
    return f"{x:.{d}f}" if isinstance(x, (int, float)) and x == x else "n/a"


def render_backtest_report(bt: dict, stylized: dict) -> str:
    lines = [
        "# SocioSim Aggregate-Fit Diagnostics Report",
        "",
        "> Scope: synthetic aggregate-fit diagnostics only. Legacy target files "
        "have incomplete source metadata and cannot support validation, backtest, "
        "calibration, or confidence seals.",
        "",
        f"## 1. Held-out aggregate diagnostic — `{bt['benchmark']}` (profile `{bt['profile']}`)",
        f"Selected graph triad p = **{bt['chosen_p']}** on the TRAIN metrics "
        f"({', '.join(bt['train_metrics'])}); implausibility I_train = "
        f"{_fmt(bt['implausibility_train'], 2)}.",
        "",
        f"Held-out metrics are reported as synthetic diagnostics "
        f"(I_test = {_fmt(bt['implausibility_test'], 2)}).",
        "",
        "| held-out metric | observed | target ± tol | z | within? |",
        "|---|---|---|---|---|",
    ]
    for r in bt["test"]:
        lines.append(f"| {r['metric']} | {_fmt(r['observed'])} | {r['target']} ± "
                     f"{r['tolerance']} | {_fmt(r['z'], 2)} | "
                     f"{'yes' if r['within_tolerance'] else 'NO'} |")
    lines += [
        "",
        "## 2. Synthetic mechanism checks",
        f"{stylized['n_pass']}/{stylized['n_total']} mechanism checks fell inside their bands.",
        "",
        "| stylized fact | observed | band | passes | source |",
        "|---|---|---|---|---|",
    ]
    for f in stylized["facts"]:
        hi = "∞" if f["hi"] is None else f["hi"]
        lines.append(f"| {f['name']} | {_fmt(f['observed'], 3)} | [{f['lo']}, {hi}] | "
                     f"{'yes' if f['passes'] else 'NO'} | {f['source']} |")
    lines += [
        "",
        "## Limitations / honest scope",
        "- Does not validate aggregate or pattern agreement with a real platform.",
        "- Synthetic agents: behavioural magnitudes remain scenario assumptions; "
        "real-person microdata is deliberately NOT used (lawful by design — no PII, "
        "no scraping). Decisions about real individuals are out of scope.",
    ]
    return "\n".join(lines)
