"""Ad experiment: FTC disclosure compliance toggle + per-campaign diagnostics.

Usage: python examples/ad_experiment_demo.py [--profile test|quick]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from socio_sim.ads.measure import measure_campaign
from socio_sim.config import RunConfig
from socio_sim.engine import Simulation
from socio_sim.experiments.scenarios import disclosure_evader_campaigns


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="test", choices=["test", "quick"])
    args = parser.parse_args()
    factory = RunConfig.quick if args.profile == "quick" else RunConfig.test

    cfg = factory(ftc_enabled=True)
    campaigns = disclosure_evader_campaigns(cfg)
    print(f"Running {cfg.n_agents} agents x {cfg.n_ticks} ticks with "
          f"{len(campaigns)} campaigns (incl. disclosure evader, FTC pack ON)\n")
    result = Simulation(cfg, campaigns=campaigns).run()

    violations = [e for e in result.log.by_kind("moderation")
                  if e["data"].get("ftc_violation")]
    print(f"FTC disclosure violations caught and fixed: {len(violations)}")

    print(f"\n{'campaign':16s} {'impr':>6s} {'CTR':>8s} {'CTR diag interval':>20s} "
          f"{'lift':>8s} {'spend':>8s}")
    for c in result.campaigns:
        m = measure_campaign(result.log, c, result.ads, cfg.n_agents)
        lo, hi = m["ctr_ci"]
        print(f"{c.id:16s} {m['impressions']:6d} {m['ctr']:8.4f} "
              f"[{lo:.4f}, {hi:.4f}]    {m['lift']:8.4f} {m['spend']:8.2f}")
    print("\nIntervals are synthetic-run diagnostics; lift = exposed minus "
          "holdout conversion rate. Research use only.")


if __name__ == "__main__":
    main()
