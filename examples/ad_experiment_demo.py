"""Ad experiment: FTC disclosure compliance toggle + per-campaign measurement
with Bayesian credible intervals and RCT holdout lift.

Usage: python examples/ad_experiment_demo.py [--profile test|quick]
"""

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from socio_sim.ads.measure import apply_fdr, measure_campaign
from socio_sim.config import RunConfig
from socio_sim.engine import Simulation
from socio_sim.experiments.scenarios import disclosure_evader_campaigns


def fmt(value, digits=4):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "n/a"
    return f"{v:.{digits}f}" if math.isfinite(v) else "n/a"


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

    measures = [measure_campaign(result.log, c, result.ads, cfg.n_agents)
                for c in result.campaigns]
    apply_fdr(measures)

    print(f"\n{'campaign':16s} {'impr':>6s} {'CTR':>8s} {'lift 95% CI':>23s} "
          f"{'raw p':>8s} {'BH q':>8s} {'ROAS*':>8s}")
    for c, m in zip(result.campaigns, measures):
        lo, hi = m["ctr_ci"]
        lift_lo, lift_hi = m["lift_ci"]
        print(f"{c.id:16s} {m['impressions']:6d} {m['ctr']:8.4f} "
              f"[{fmt(lift_lo)}, {fmt(lift_hi)}] "
              f"{fmt(m['lift_pvalue_raw']):>8s} {fmt(m['lift_qvalue_bh']):>8s} "
              f"{fmt(m['roas'], 3):>8s}")
        print(f"  CTR posterior 95% CI: [{fmt(lo)}, {fmt(hi)}] | "
              f"economics provenance: {m['economics_provenance']}")
    print("\nLift is exposed minus randomized-holdout conversion rate with "
          "Benjamini-Hochberg q-values across this campaign family.")
    print("* ROAS and all monetary values are synthetic scenario inputs/outputs, "
          "not forecasts of real financial performance. Research use only.")


if __name__ == "__main__":
    main()
