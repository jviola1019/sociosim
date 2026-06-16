"""Policy stress test: US §230 pack vs EU DSA pack under common random numbers.

Usage: python examples/policy_stress_demo.py [--replicates 5] [--profile test|quick]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from socio_sim.analytics.metrics import (appeal_stats, harmful_exposure,
                                         moderation_confusion, notice_stats)
from socio_sim.config import RunConfig
from socio_sim.experiments.runner import compare


def metrics(result):
    exposure, _ = harmful_exposure(result.log)
    cm = moderation_confusion(result.log)
    app = appeal_stats(result.log)
    notices = notice_stats(result.log)
    return {
        "harmful_exposure_rate": exposure,
        "moderation_recall": cm["recall"] if cm["recall"] == cm["recall"] else 0.0,
        "moderation_fpr": cm["fpr"] if cm["fpr"] == cm["fpr"] else 0.0,
        "appeals_filed": app["filed"],
        "notices_sent": notices["notices_sent"],
        "removals": notices["removals"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--replicates", type=int, default=5)
    parser.add_argument("--profile", default="test", choices=["test", "quick"])
    args = parser.parse_args()

    factory = RunConfig.quick if args.profile == "quick" else RunConfig.test
    baseline = factory(jurisdictions=("US",))
    intervention = factory(jurisdictions=("EU",))

    print(f"Comparing US-§230 vs EU-DSA: {baseline.n_agents} agents x "
          f"{baseline.n_ticks} ticks x {args.replicates} paired replicates "
          f"(common random numbers)\n")
    res = compare(baseline, intervention, args.replicates, metrics)

    print(f"{'metric':28s} {'US (median)':>12s} {'EU (median)':>12s} "
          f"{'delta':>9s}  95% interval")
    for name, r in res.items():
        lo, hi = r["delta_ci"]
        print(f"{name:28s} {r['baseline_median']:12.4f} "
              f"{r['intervention_median']:12.4f} {r['delta_median']:9.4f}  "
              f"[{lo:.4f}, {hi:.4f}]")
    print("\nDeltas are EU minus US. Counterfactual projections under stated "
          "assumptions — not predictions.")


if __name__ == "__main__":
    main()
