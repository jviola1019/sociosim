"""Validation study: sensitivity of headline outputs to BehaviorParams + a
calibration (implausibility) check against the published benchmark targets.

This is the FIRST place the model's OWN behaviour parameters are
sensitivity-tested and checked against empirical targets (audit P4 / Q-PARAM).
Results are rendered to VALIDATION_REPORT.md. Provenance: synthetic exploratory
— a parameter with high sensitivity index must be calibrated (or its dependent
outputs flagged) before being treated as more than a scenario assumption.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from socio_sim.agents.personas import DIURNAL_CURVE
from socio_sim.analytics.metrics import summarize_run
from socio_sim.config import RunConfig
from socio_sim.engine import Simulation
from socio_sim.stats import discrete_ks
from socio_sim.validation.calibrate import (abc_posterior, history_match,
                                            implausibility, lhs_samples,
                                            sobol_samples)
from socio_sim.validation.sensitivity import first_order_indices
from socio_sim.validation.targets import compute_observed, load_targets


def default_behavior_bounds() -> dict:
    """+/-50% ranges around documented BehaviorParams defaults for the most
    influential knobs (the ones that plausibly move headline outputs)."""
    return {
        "p_post_given_active": (0.15, 0.45),
        "p_share_given_engaged": (0.05, 0.20),
        "engagement_base": (0.15, 0.45),
        "impression_fatigue": (0.0025, 0.0075),
        "p_flag_scale": (0.15, 0.45),
    }


def posts_per_agent(result) -> float:
    return len(result.log.by_kind("post")) / result.config.n_agents


def behavior_sensitivity(cfg: RunConfig, bounds: dict, n_samples: int,
                         metric_fn, rng) -> dict:
    """First-order (Sobol-style) sensitivity of `metric_fn` to the named
    BehaviorParams over an LHS design. Common root seed across samples so output
    variance is attributable to the parameters, not seed noise."""
    names = sorted(bounds)
    samples = lhs_samples(bounds, n_samples, rng)
    X = np.array([[s[n] for n in names] for s in samples], dtype=float)
    y = []
    for s in samples:
        c = replace(cfg, behavior=replace(cfg.behavior, **s))
        y.append(float(metric_fn(Simulation(c).run())))
    y = np.array(y, dtype=float)
    return {
        "names": names,
        "indices": first_order_indices(X, y, names),
        "y_mean": float(y.mean()), "y_std": float(y.std()),
        "n_samples": n_samples,
    }


#: Headline outputs swept in the multi-output sensitivity study.
SENSITIVITY_OUTPUTS = ("n_posts", "harmful_exposure_rate", "welfare_mean")


def multi_output_sensitivity(cfg: RunConfig, bounds: dict, n_samples: int,
                             outputs=SENSITIVITY_OUTPUTS,
                             seeds=(1, 2, 3)) -> dict:
    """First-order (Sobol-design) indices for MULTIPLE outputs, averaged over
    MULTIPLE seeds so the estimate reflects parameter influence, not seed noise.
    Returns per-output {param: {mean, std}} of S1 across seeds."""
    from socio_sim.pipeline import _headline_metrics
    names = sorted(bounds)
    per_seed = {o: [] for o in outputs}
    n_design = 0
    for sd in seeds:
        design = sobol_samples(bounds, n_samples, np.random.default_rng(sd))
        n_design = len(design)
        X = np.array([[s[n] for n in names] for s in design], dtype=float)
        ys = {o: [] for o in outputs}
        for s in design:
            c = replace(cfg, behavior=replace(cfg.behavior, **s), root_seed=int(sd))
            metrics = _headline_metrics(Simulation(c).run())
            for o in outputs:
                ys[o].append(float(metrics[o]))
        for o in outputs:
            per_seed[o].append(first_order_indices(X, np.array(ys[o]), names))
    indices = {}
    for o in outputs:
        rows = per_seed[o]
        indices[o] = {n: {"mean": float(np.mean([r[n] for r in rows])),
                          "std": float(np.std([r[n] for r in rows]))}
                      for n in names}
    return {"names": names, "outputs": list(outputs), "n_samples": n_design,
            "n_seeds": len(seeds), "indices": indices}


def calibration_implausibility(cfg: RunConfig) -> dict:
    """Implausibility I = max standardized discrepancy of observed vs targets
    (history-matching cutoff 3.0)."""
    result = Simulation(cfg).run()
    observed = compute_observed(result, summarize_run(result))
    targets = load_targets()
    # Distributional check (not just means): KS gap between the observed
    # posting-hour distribution and the expected diurnal curve.
    hours = [(e["tick"] * cfg.tick_hours) % 24 for e in result.log.by_kind("post")]
    counts = np.bincount(hours, minlength=24) if hours else np.zeros(24)
    return {"implausibility": implausibility(observed, targets),
            "observed": observed, "targets": targets,
            "diurnal_ks": discrete_ks(counts, DIURNAL_CURVE)}


def posterior_calibrated_mc(profile: str = "test", n_samples: int = 24,
                            seed: int = 42,
                            metric: str = "posts_per_agent_day") -> dict:
    """Chain calibration -> uncertainty: history-match BehaviorParams against a
    behaviour-controllable target, build an ABC posterior, then propagate that
    parameter posterior into an interval for `metric`. This is genuine
    parameter-uncertainty propagation (not single-run noise)."""
    factory = {"test": RunConfig.test, "quick": RunConfig.quick,
               "standard": RunConfig.standard,
               "calibrated": RunConfig.calibrated}[profile]
    cfg = factory(jurisdictions=("EU",), root_seed=seed)
    rng = np.random.default_rng(seed)
    bounds = {"p_post_given_active": (0.15, 0.45),
              "engagement_base": (0.15, 0.45)}
    targets = {k: v for k, v in load_targets().items() if k == metric}

    def run_fn(params, _rng):
        c = replace(cfg, behavior=replace(cfg.behavior, **params))
        res = Simulation(c).run()
        return compute_observed(res, summarize_run(res))

    survivors = history_match(run_fn, bounds, targets, n_samples, rng,
                              threshold=3.0)
    if not survivors:
        return {"n_accepted": 0, "note": "no plausible parameter sets",
                "provenance": "abc-posterior-propagated"}
    posterior = abc_posterior(survivors, accept_fraction=0.5)
    ranked = sorted(survivors, key=lambda s: s["implausibility"])
    k = max(int(len(ranked) * 0.5), 3)
    vals = np.array([s["observed"][metric] for s in ranked[:k]
                     if np.isfinite(s["observed"].get(metric, float("nan")))])
    ci = ((float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5)))
          if vals.size else (float("nan"), float("nan")))
    return {"metric": metric, "n_accepted": int(vals.size), "posterior": posterior,
            "output_median": float(np.median(vals)) if vals.size else float("nan"),
            "output_ci": ci, "provenance": "abc-posterior-propagated"}


_PROFILES = {"test": RunConfig.test, "quick": RunConfig.quick,
             "standard": RunConfig.standard, "calibrated": RunConfig.calibrated}


def run_validation_study(profile: str = "test", n_samples: int = 24,
                         seed: int = 42) -> dict:
    cfg = _PROFILES[profile](jurisdictions=("EU",), root_seed=seed)
    rng = np.random.default_rng(seed)
    return {
        "profile": profile, "seed": seed, "n_agents": cfg.n_agents,
        "n_ticks": cfg.n_ticks,
        "sensitivity": behavior_sensitivity(
            cfg, default_behavior_bounds(), n_samples, posts_per_agent, rng),
        "multi_sensitivity": multi_output_sensitivity(
            cfg, default_behavior_bounds(), n_samples,
            seeds=(seed, seed + 1, seed + 2)),
        "calibration": calibration_implausibility(cfg),
        "posterior_mc": posterior_calibrated_mc(profile, n_samples, seed),
    }


def _pm_line(pm: dict) -> str:
    if not pm or not pm.get("n_accepted"):
        return ("ABC posterior propagation: no plausible parameter sets at this "
                "scale/seed (try more samples).")
    lo, hi = pm["output_ci"]
    return (f"Calibrated `{pm['metric']}` over {pm['n_accepted']} accepted "
            f"parameter sets (provenance: {pm['provenance']}): median "
            f"{pm['output_median']:.4f}, 95% [{lo:.4f}, {hi:.4f}].")


def render_validation_report(study: dict) -> str:
    s, c = study["sensitivity"], study["calibration"]
    pm = study.get("posterior_mc") or {}
    ranked = sorted(s["indices"].items(), key=lambda kv: kv[1], reverse=True)
    lines = [
        "# SocioSim Validation Report",
        "",
        "> Provenance: **synthetic exploratory**. Behaviour parameters are not "
        "empirically calibrated; this report records their sensitivity and the "
        "run's distance from published aggregate benchmarks. It is NOT evidence "
        "that the simulator predicts real behaviour.",
        "",
        f"Profile `{study['profile']}` · {study['n_agents']} agents × "
        f"{study['n_ticks']} ticks · seed {study['seed']}.",
        "",
        "## 1. Sensitivity of posts/agent to BehaviorParams",
        f"First-order variance-based indices (LHS, n={s['n_samples']}; "
        f"output mean {s['y_mean']:.4f}, sd {s['y_std']:.4f}).",
        "",
        "| BehaviorParam | first-order index S1 |",
        "|---|---|",
    ]
    for name, idx in ranked:
        lines.append(f"| `{name}` | {idx:.3f} |")
    lines += [
        "",
        "Interpretation: parameters with high S1 dominate this output and MUST "
        "be calibrated (or their dependent claims flagged uncalibrated) before "
        "use. Low-S1 parameters are safe to leave at documented defaults.",
    ]
    ms = study.get("multi_sensitivity")
    if ms:
        lines += [
            "",
            "## 1b. Multi-output sensitivity (Sobol design, multi-seed)",
            f"First-order indices for {len(ms['outputs'])} outputs over a Sobol "
            f"design (n={ms['n_samples']}) averaged across {ms['n_seeds']} seeds "
            "(mean ± sd of S1 across seeds).",
            "",
            "| BehaviorParam | " + " | ".join(ms["outputs"]) + " |",
            "|---|" + "|".join(["---"] * len(ms["outputs"])) + "|",
        ]
        for name in ms["names"]:
            cells = [f"{ms['indices'][o][name]['mean']:.3f}±"
                     f"{ms['indices'][o][name]['std']:.3f}" for o in ms["outputs"]]
            lines.append(f"| `{name}` | " + " | ".join(cells) + " |")
    lines += [
        "",
        "## 2. Calibration vs published benchmarks",
        f"Implausibility **I = {c['implausibility']:.2f}** "
        "(history-matching cutoff 3.0; I<3 = not implausible).",
        f"Diurnal distribution KS gap = {c.get('diurnal_ks', float('nan')):.3f} "
        "(0 = posting-hour distribution matches the diurnal curve exactly).",
        "",
        "| Target | observed | benchmark | tolerance | within tol? |",
        "|---|---|---|---|---|",
    ]
    obs, tgts = c["observed"], c["targets"]
    for name, spec in tgts.items():
        o = obs.get(name)
        if o is None or not np.isfinite(o):
            lines.append(f"| {name} | n/a | {spec['value']} | {spec['tolerance']} | — |")
            continue
        ok = abs(o - spec["value"]) <= spec["tolerance"]
        lines.append(f"| {name} | {o:.4f} | {spec['value']} | "
                     f"{spec['tolerance']} | {'yes' if ok else 'NO'} |")
    lines += [
        "",
        "## 2b. Parameter-uncertainty propagation (ABC posterior -> output)",
        _pm_line(pm),
        "",
        "## 3. Limitations",
        "- Bounds are +/-50% of defaults, not empirically derived.",
        "- Section 1b now sweeps MULTIPLE outputs over a Sobol design across "
        "MULTIPLE seeds; section 1 keeps the single-output LHS view for "
        "continuity. Indices are first-order only (no higher-order/total effects).",
        "- Benchmark targets are coarse published aggregates with wide tolerances; "
        "use `--profile calibrated` for a history-matched, in-band configuration.",
        "- `degree_tail_exponent` / network targets depend on the graph model, "
        "not BehaviorParams.",
    ]
    return "\n".join(lines)
