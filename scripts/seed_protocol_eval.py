"""Run the full seed-generalization protocol for the aggregate profile.

Evaluates every fitting, validation and LOCKED holdout seed (deterministic
per seed; replay-verified), then writes the committed artifact
``socio_sim/data/seed_protocol_results_v1.json`` with per-seed records,
per-group distribution summaries, and the holdout acceptance verdict.

Usage:  python scripts/seed_protocol_eval.py [--workers N] [--no-replay]

The holdout seeds are evaluated ONLY here, never during tuning; the artifact
records that attestation. Runtime is ~60 runs x ~30 s (x2 with replay),
parallelized across --workers processes.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from socio_sim.validation import seed_protocol as sp  # noqa: E402

OUT_PATH = ROOT / "socio_sim" / "data" / sp.RESULTS_RESOURCE

ATTESTATION = (
    "No model parameter was selected using holdout results. The profile "
    "parameters were frozen at commit 86bb4b7 (fitted on seed 42 alone, "
    "2026-07-14) BEFORE the holdout seeds were first evaluated; this "
    "script only measures, it does not tune.")


def _evaluate_group(name: str, seeds, workers: int, verify_replay: bool) -> list:
    print(f"[{name}] evaluating {len(seeds)} seeds "
          f"(workers={workers}, replay={verify_replay}) ...", flush=True)
    t0 = time.time()
    fn = partial(sp.evaluate_seed, verify_replay=verify_replay)
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            records = list(ex.map(fn, seeds))
    else:
        records = [fn(s) for s in seeds]
    print(f"[{name}] done in {time.time() - t0:.0f} s", flush=True)
    return records


def _print_summary(name: str, summary: dict) -> None:
    print(f"\n== {name} ({summary['n_seeds']} seeds) ==")
    print(f"  median I        {summary['median_implausibility']:.3f}")
    print(f"  mean I          {summary['mean_implausibility']:.3f}")
    print(f"  p5/p25/p75/p95  {summary['p5']:.3f} / {summary['p25']:.3f} / "
          f"{summary['p75']:.3f} / {summary['p95']:.3f}")
    print(f"  max I           {summary['max_implausibility']:.3f}")
    print(f"  pass (<{sp.CUTOFF})      {summary['n_pass']}/{summary['n_seeds']} "
          f"= {summary['pass_proportion']:.0%}  "
          f"wilson95={tuple(round(x, 3) for x in summary['pass_ci_wilson95'])}  "
          f"bootstrap95={tuple(round(x, 3) for x in summary['pass_ci_bootstrap95'])}")
    print(f"  dominant failing metrics: {summary['dominant_failing_metric_frequency']}")
    print(f"  component fail rates (z>={sp.CUTOFF}): "
          f"{ {k: round(v, 2) for k, v in summary['component_failure_rates'].items()} }")
    print(f"  replay: {summary['n_replay_checked']} checked, "
          f"all_ok={summary['replay_all_ok']}; "
          f"runtime failures: {summary['n_runtime_failures']}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--no-replay", action="store_true",
                    help="skip replay verification (faster; artifact records it)")
    args = ap.parse_args()
    verify_replay = not args.no_replay

    from socio_sim.config import RunConfig
    from socio_sim.validation.targets import load_targets
    profile_cfg = RunConfig.aggregate_matched_prototype(jurisdictions=("EU",))
    targets = load_targets(profile_cfg.benchmark)

    groups = {}
    summaries = {}
    for name, seeds in (("fitting", sp.FITTING_SEEDS),
                        ("validation", sp.VALIDATION_SEEDS),
                        ("holdout", sp.HOLDOUT_SEEDS)):
        groups[name] = _evaluate_group(name, seeds, args.workers, verify_replay)
        summaries[name] = sp.summarize(groups[name])
        _print_summary(name, summaries[name])

    verdict = sp.acceptance(summaries["holdout"])
    label = (sp.PROFILE_LABEL_VALIDATED if verdict["accepted"]
             else sp.PROFILE_LABEL_DEMONSTRATION)
    print("\n== holdout acceptance ==")
    for crit, ok in verdict["criteria"].items():
        print(f"  {'PASS' if ok else 'FAIL'}  {crit}")
    print(f"  => accepted={verdict['accepted']}  label: {label}")

    artifact = {
        "protocol_version": 1,
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "profile": "aggregate_matched_prototype",
        "profile_config_hash": profile_cfg.config_hash(),
        "benchmark": profile_cfg.benchmark,
        "targets_values_sha256": sp.targets_values_sha256(targets),
        "cutoff": sp.CUTOFF,
        "verify_replay": verify_replay,
        "seed_lists": {
            "fitting": list(sp.FITTING_SEEDS),
            "validation": list(sp.VALIDATION_SEEDS),
            "holdout": list(sp.HOLDOUT_SEEDS),
        },
        "holdout_seeds_sha256": sp.seeds_sha256(sp.HOLDOUT_SEEDS),
        "attestation_no_holdout_tuning": ATTESTATION,
        "records": groups,
        "summaries": summaries,
        "acceptance": verdict,
        "profile_label": label,
        "scope_note": (
            "Aggregate-fit diagnostic over synthetic runs against sourced "
            "aggregate targets. NOT validation, calibration, realism, or "
            "prediction of any real platform (see each target's "
            "applicability_limits)."),
    }
    def _json_safe(obj):
        """numpy scalars -> Python; NaN/inf -> null (strict JSON artifact)."""
        import math

        import numpy as np
        if isinstance(obj, dict):
            return {k: _json_safe(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_json_safe(v) for v in obj]
        if isinstance(obj, (bool, np.bool_)):
            return bool(obj)
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (float, np.floating)):
            f = float(obj)
            return f if math.isfinite(f) else None
        return obj

    OUT_PATH.write_text(json.dumps(_json_safe(artifact), indent=2,
                                   allow_nan=False) + "\n", encoding="utf-8")
    print(f"\nwrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
