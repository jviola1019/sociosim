"""Aggregate-fit targets (Spec §3.9): named published-aggregate target sets +
observation extraction from runs. KS distances are available for
distributional targets.

Two families, and the difference is load-bearing:

- ``sourced_aggregates_v1`` (the DEFAULT): every value was read out of the
  primary source's own text/tables in the 2026-07-13 verification pass and
  is quoted in the target's ``statistic_location``. These carry complete
  metadata and non-``unsupported`` evidence records, so they may drive
  aggregate-fit DIAGNOSTICS.
- ``legacy_unsupported_*``: the pre-verification target sets. Their numbers
  could NOT be verified against the sources they cited -- several are
  contradicted by those sources, and some (e.g. a Twitter clustering value
  attributed to Kwak et al. 2010, which reports no clustering coefficient
  at all) were never in the cited paper. They are retained ONLY for
  reproducing older runs, are excluded from the default, and their evidence
  kind stays ``unsupported`` so every decision-facing comparison gate stays
  shut for them.

In neither case is a small target distance validation, calibration, realism,
or a prediction of any real platform: the populations, definitions and time
windows differ from this synthetic world (see each target's
``applicability_limits``).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy import stats

# Packaged inside socio_sim/ so it ships in the wheel and the Docker image
# (was a repo-relative path that broke any installed/containerised run).
BENCHMARK_DIR = Path(__file__).resolve().parents[1] / "data" / "benchmarks"

#: The default target set: values verified against their primary sources.
DEFAULT_BENCHMARK = "sourced_aggregates_v1"
DEFAULT_TARGETS_PATH = BENCHMARK_DIR / f"{DEFAULT_BENCHMARK}.json"

#: Prefix marking the retired, unverifiable target sets. Loadable by explicit
#: name for reproducing older runs; never the default.
LEGACY_PREFIX = "legacy_unsupported"


def available_benchmarks(include_legacy: bool = True) -> list:
    """Named bundled target sets. Sourced sets first; the legacy unsupported
    sets are listed last (and only when explicitly requested)."""
    stems = sorted(p.stem for p in BENCHMARK_DIR.glob("*.json"))
    sourced = [s for s in stems if not s.startswith(LEGACY_PREFIX)]
    legacy = [s for s in stems if s.startswith(LEGACY_PREFIX)]
    return sourced + (legacy if include_legacy else [])


def is_legacy_unsupported(name: str) -> bool:
    return str(name).startswith(LEGACY_PREFIX)


def load_targets(name: str = DEFAULT_BENCHMARK,
                 path: str | Path | None = None) -> dict:
    """Load a named bundled target set, or an explicit `path`.

    "default" is accepted as a backwards-compatible alias for the current
    default set (it used to name the legacy file); it now resolves to the
    SOURCED set, so old callers stop silently comparing against unverified
    numbers. To reproduce a pre-verification run, name the legacy set
    explicitly (e.g. ``legacy_unsupported_default``).
    """
    if path is not None:
        p = Path(path)
    else:
        if name in ("default", ""):
            name = DEFAULT_BENCHMARK
        p = BENCHMARK_DIR / f"{name}.json"
    if not p.is_file():
        raise FileNotFoundError(
            f"unknown benchmark target set: {name!r} "
            f"(available: {', '.join(available_benchmarks())})")
    return json.loads(p.read_text(encoding="utf-8"))["targets"]


def hill_exponent(sample: np.ndarray, tail_fraction: float = 0.1) -> float:
    """Hill estimator of the power-law tail exponent (alpha)."""
    x = np.sort(np.asarray(sample, dtype=float))
    k = max(int(len(x) * tail_fraction), 10)
    tail = x[-k:]
    xmin = tail[0]
    return 1.0 + k / float(np.sum(np.log(tail / xmin)))


def ks_distance(sample_a: np.ndarray, sample_b: np.ndarray) -> float:
    return float(stats.ks_2samp(sample_a, sample_b).statistic)


def compute_observed(result, summary: dict) -> dict:
    """Extract target-comparable observables from a finished run."""
    cfg = result.config
    days = cfg.n_ticks * cfg.tick_hours / 24.0
    posts = result.log.by_kind("post")
    hours = np.array([(e["tick"] * cfg.tick_hours) % 24 for e in posts])
    hour_counts = np.bincount(hours, minlength=24) if len(hours) else np.zeros(24)

    ads = summary["ads"]
    total_impr = sum(m["impressions"] for m in ads.values())
    total_clicks = sum(m["clicks"] for m in ads.values())

    observed = {
        "clustering": summary["graph"]["clustering"],
        "degree_tail_exponent": summary["graph"].get(
            "degree_tail_exponent", float("nan")),
        "posts_per_agent_day": len(posts) / (cfg.n_agents * days),
        "diurnal_peak_hour": float(np.argmax(hour_counts)),
        "diurnal_trough_hour": float(np.argmin(hour_counts)),
        "ad_ctr": (total_clicks / total_impr) if total_impr else float("nan"),
        "appeal_grant_rate": summary["appeals"]["granted_rate"],
    }
    return observed
