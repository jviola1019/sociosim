"""Seed-generalization protocol for the aggregate-fit profile (Spec §3.9).

A stochastic simulator cannot claim to "match" aggregate targets on the
evidence of ONE realization. This module defines the protocol that replaces
the original single-seed (root_seed=42) demonstration with a proper
fit / validation / locked-holdout split over root seeds:

- ``FITTING_SEEDS``   -- seeds on which model parameters MAY be tuned.
  Seed 42 is here because it is the seed the 2026-07-14 history-matching
  pass actually used; the rest are reserved for future mechanism work.
- ``VALIDATION_SEEDS`` -- seeds used to check generalization while tuning.
- ``HOLDOUT_SEEDS``    -- locked, never used for any parameter choice.
  Their list is hash-pinned (tests) and evaluated only by
  ``scripts/seed_protocol_eval.py``; the committed artifact records the
  attestation that no parameter was selected using holdout results.

The three lists are pairwise disjoint (test-enforced). Success is defined
over the DISTRIBUTION of holdout implausibilities (see ``acceptance``),
never by any single seed being below the cutoff.

Outcome (2026-07-16 evaluation, committed at
``socio_sim/data/seed_protocol_results_v1.json``): the profile FAILS the
holdout acceptance criteria -- the honest label is therefore
``seed-42 aggregate demonstration profile``, not a matched/validated one.
See docs/AGGREGATE_FIT_FINDINGS.md for the full distributions.
"""

from __future__ import annotations

import hashlib
import json
from importlib import resources
from pathlib import Path

import numpy as np

#: History-matching cutoff (max standardized discrepancy), same convention
#: as socio_sim.validation.calibrate.
CUTOFF = 3.0

#: Structural aggregates a social-network model is responsible for
#: reproducing (graph + temporal); the ad/appeal terms are small-count
#: behavioural rates whose real sources are incompatible surfaces.
STRUCTURAL_METRICS = (
    "degree_tail_exponent",
    "clustering",
    "diurnal_peak_hour",
    "diurnal_trough_hour",
    "posts_per_agent_day",
)

#: Seeds parameters may be tuned on. 42 = the historical fitting seed.
FITTING_SEEDS = (42,) + tuple(range(101, 120))
#: Seeds used to check generalization during tuning (never for selection
#: of the final reported numbers).
VALIDATION_SEEDS = tuple(range(201, 221))
#: LOCKED holdout seeds: never used for any parameter decision. The list is
#: hash-pinned by tests/test_seed_protocol.py; changing it invalidates every
#: committed protocol artifact.
HOLDOUT_SEEDS = tuple(range(9001, 9021))

#: The default committed protocol artifact (ships in the wheel).
RESULTS_RESOURCE = "seed_protocol_results_v1.json"

#: The honest label for the profile given the committed protocol outcome.
PROFILE_LABEL_DEMONSTRATION = "seed-42 aggregate demonstration profile"
PROFILE_LABEL_VALIDATED = "aggregate-matched profile (holdout-validated)"


def seeds_sha256(seeds) -> str:
    """Canonical hash of a seed list (order-sensitive, JSON-canonical)."""
    canon = json.dumps([int(s) for s in seeds], separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()


def targets_values_sha256(targets: dict) -> str:
    """Hash of ONLY {name: [value, tolerance]} -- pins the fitting targets
    against tuning-time edits while allowing provenance-metadata additions
    (source hashes, retrieval notes) that do not move any number."""
    canon = json.dumps(
        {name: [float(spec["value"]), float(spec["tolerance"])]
         for name, spec in sorted(targets.items())},
        sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()


def evaluate_seed(seed: int, verify_replay: bool = True) -> dict:
    """Run the aggregate profile on one root seed and extract the per-seed
    record the protocol requires: overall implausibility, every component
    z-distance and observed value, replay success, and runtime failures."""
    from socio_sim.config import RunConfig
    from socio_sim.pipeline import run_and_analyze
    record: dict = {"seed": int(seed)}
    try:
        a = run_and_analyze(
            RunConfig.aggregate_matched_prototype(
                jurisdictions=("EU",), root_seed=int(seed)),
            verify_replay=verify_replay, write=False)
    except Exception as exc:  # runtime failures are data, not crashes
        record.update({
            "runtime_failure": f"{type(exc).__name__}: {exc}",
            "implausibility": float("nan"),
            "replay_checked": False, "replay_ok": None,
            "components": {}, "observed": {}, "dominant_metric": None,
        })
        return record
    record.update({
        "runtime_failure": None,
        "implausibility": float(a.implausibility),
        "dominant_metric": a.implausibility_dominant_metric,
        "components": {c["metric"]: float(c["z"])
                       for c in a.implausibility_components},
        "observed": {c["metric"]: float(c["observed"])
                     for c in a.implausibility_components},
        "replay_checked": bool(a.replay["checked"]),
        "replay_ok": a.replay["ok"],
    })
    return record


def _wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple:
    """Wilson score 95% interval for a proportion (deterministic)."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (float(max(0.0, center - half)), float(min(1.0, center + half)))


def _bootstrap_pass_ci(passes: list, n_boot: int = 10_000,
                       seed: int = 0) -> tuple:
    """Monte Carlo (bootstrap) 95% interval for the pass proportion,
    deterministic from its own seed."""
    if not passes:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    arr = np.asarray(passes, dtype=float)
    idx = rng.integers(0, len(arr), size=(n_boot, len(arr)))
    props = arr[idx].mean(axis=1)
    return (float(np.percentile(props, 2.5)),
            float(np.percentile(props, 97.5)))


def summarize(records: list) -> dict:
    """Distribution summary over per-seed records: never one seed's score."""
    scores = np.array([r["implausibility"] for r in records], dtype=float)
    finite = scores[np.isfinite(scores)]
    passes = [bool(np.isfinite(s) and s < CUTOFF) for s in scores]
    n = len(records)
    n_pass = sum(passes)
    failing = [r for r, ok in zip(records, passes) if not ok]
    dominant_freq: dict = {}
    for r in failing:
        key = r.get("dominant_metric") or "runtime_failure"
        dominant_freq[key] = dominant_freq.get(key, 0) + 1
    component_fail_rates = {}
    metrics = sorted({m for r in records for m in r.get("components", {})})
    for m in metrics:
        zs = [r["components"].get(m) for r in records if m in r.get("components", {})]
        component_fail_rates[m] = (
            float(np.mean([z >= CUTOFF for z in zs])) if zs else float("nan"))
    def pct(q):
        return float(np.percentile(finite, q)) if finite.size else float("nan")
    return {
        "n_seeds": n,
        "n_runtime_failures": sum(1 for r in records if r.get("runtime_failure")),
        "median_implausibility": float(np.median(finite)) if finite.size else float("nan"),
        "mean_implausibility": float(np.mean(finite)) if finite.size else float("nan"),
        "p5": pct(5), "p25": pct(25), "p75": pct(75), "p95": pct(95),
        "max_implausibility": float(np.max(finite)) if finite.size else float("nan"),
        "pass_proportion": (n_pass / n) if n else float("nan"),
        "n_pass": n_pass,
        "pass_ci_wilson95": _wilson_interval(n_pass, n),
        "pass_ci_bootstrap95": _bootstrap_pass_ci(passes),
        "dominant_failing_metric_frequency": dominant_freq,
        "component_failure_rates": component_fail_rates,
        "replay_all_ok": all(r.get("replay_ok") is True for r in records
                             if r.get("replay_checked")),
        "n_replay_checked": sum(1 for r in records if r.get("replay_checked")),
    }


def acceptance(holdout_summary: dict) -> dict:
    """The provisional acceptance criteria over the LOCKED holdout seeds.
    Success is a distributional property; one good seed proves nothing."""
    structural_rates = {
        m: holdout_summary["component_failure_rates"].get(m, float("nan"))
        for m in STRUCTURAL_METRICS}
    criteria = {
        "pass_proportion_at_least_80pct":
            bool(holdout_summary["pass_proportion"] >= 0.80),
        "median_implausibility_below_cutoff":
            bool(holdout_summary["median_implausibility"] < CUTOFF),
        "p95_reported": bool(np.isfinite(holdout_summary["p95"])),
        "no_structural_metric_fails_more_than_20pct":
            bool(all((not np.isfinite(r)) or r <= 0.20
                     for r in structural_rates.values())),
        "all_holdout_replays_ok":
            bool(holdout_summary["replay_all_ok"]
                 and holdout_summary["n_replay_checked"]
                 == holdout_summary["n_seeds"]),
        "no_runtime_failures": bool(holdout_summary["n_runtime_failures"] == 0),
    }
    return {
        "criteria": criteria,
        "accepted": all(criteria.values()),
        "structural_failure_rates": structural_rates,
    }


def profile_label(results: dict | None = None) -> str:
    """The honest human-facing label for the aggregate profile, derived from
    the committed protocol artifact -- never asserted independently of it."""
    if results is None:
        results = load_results()
    if results and results.get("acceptance", {}).get("accepted") is True:
        return PROFILE_LABEL_VALIDATED
    return PROFILE_LABEL_DEMONSTRATION


def load_results(path: str | Path | None = None) -> dict | None:
    """Load the committed protocol artifact (or an explicit path). Returns
    None when absent -- callers must treat 'no artifact' as NOT validated."""
    try:
        if path is not None:
            text = Path(path).read_text(encoding="utf-8")
        else:
            text = resources.files("socio_sim").joinpath(
                "data", RESULTS_RESOURCE).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None
    return json.loads(text)
