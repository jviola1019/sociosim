"""Calibration targets (Spec §3.9): named aggregate benchmarks + observation
extraction from runs. KS distances are available for distributional targets."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy import stats

# Packaged inside socio_sim/ so it ships in the wheel and the Docker image
# (was a repo-relative path that broke any installed/containerised run).
DEFAULT_TARGETS_PATH = (Path(__file__).resolve().parents[1]
                        / "data" / "benchmarks" / "default_targets.json")


def load_targets(path: str | Path | None = None) -> dict:
    p = Path(path) if path else DEFAULT_TARGETS_PATH
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
