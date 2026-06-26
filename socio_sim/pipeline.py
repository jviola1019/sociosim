"""Single source of truth for the run → analyze → calibrate → verify pipeline.

The CLI launcher (run.py), the web backend (web/app.py) and the example scripts
all call `run_and_analyze` so they can never drift. Anything UI-specific
(progress bars, JSON shaping, charts) wraps this; the core stays here.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from socio_sim.analytics.metrics import summarize_run
from socio_sim.analytics.report import render
from socio_sim.ads.campaigns import campaigns_from_specs
from socio_sim.config import RunConfig
from socio_sim.engine import Simulation
from socio_sim.logs.replay import verify
from socio_sim.policy.engine import PolicyEngine
from socio_sim.policy.transparency import transparency_report
from socio_sim.validation.calibrate import implausibility
from socio_sim.validation.montecarlo import run_replicates
from socio_sim.validation.targets import compute_observed, load_targets

#: Replay verification doubles runtime, so it is auto-skipped above this size.
REPLAY_AGENT_LIMIT = 2000


def _headline_metrics(result) -> dict:
    """Scalar headline metrics extracted from one run, for MC aggregation."""
    s = summarize_run(result)
    ads = list((s.get("ads") or {}).values())
    ad_impressions = sum(float(a.get("impressions", 0)) for a in ads)
    ad_clicks = sum(float(a.get("clicks", 0)) for a in ads)
    ad_conversions = sum(float(a.get("conversions", 0)) for a in ads)
    ad_spend = sum(float(a.get("spend", 0)) for a in ads)
    ad_revenue = sum(float(a.get("revenue", 0)) for a in ads)
    exposed_n = sum(float(a.get("n_exposed", 0)) for a in ads)
    ad_lift = (sum(float(a.get("lift", 0)) * float(a.get("n_exposed", 0))
                   for a in ads) / exposed_n) if exposed_n else 0.0
    disclosures = [1.0 if a.get("disclosure_present") else 0.0 for a in ads]
    return {
        "harmful_exposure_rate": float(s["harmful_exposure"]["rate"]),
        "moderation_precision": float(s["moderation"]["precision"]),
        "moderation_recall": float(s["moderation"]["recall"]),
        "appeal_grant_rate": float(s["appeals"]["granted_rate"]),
        "welfare_mean": float(s["welfare"]["mean"]),
        "n_posts": float(s["n_posts"]),
        "ad_impressions": ad_impressions,
        "ad_ctr": (ad_clicks / ad_impressions) if ad_impressions else 0.0,
        "ad_cvr": (ad_conversions / ad_clicks) if ad_clicks else 0.0,
        "ad_spend": ad_spend,
        "ad_roas": (ad_revenue / ad_spend) if ad_spend else 0.0,
        "ad_lift_itt": ad_lift,
        "ad_disclosure_rate": float(np.mean(disclosures)) if disclosures else 0.0,
    }


def mc_bundle(cfg: RunConfig, n_replicates: int, campaigns_fn=None,
             workers: int = 1) -> dict:
    """Run N replicates and return per-metric Monte Carlo percentile intervals.

    Provenance is explicitly 'mc-replicated' to distinguish these from the
    single-run within-run/analytic intervals on the report. NaN per-replicate
    values (e.g. recall with no harmful content) are dropped before aggregating.
    """
    raw = run_replicates(cfg, n_replicates, _headline_metrics,
                         campaigns_fn=campaigns_fn, workers=workers)
    out = {}
    for name, d in raw.items():
        vals = np.array([v for v in d["values"] if v == v], dtype=float)
        if vals.size == 0:
            continue
        out[name] = {
            "median": float(np.median(vals)),
            "ci": (float(np.percentile(vals, 2.5)),
                   float(np.percentile(vals, 97.5))),
            "n_replicates": int(vals.size),
            "provenance": "mc-replicated",
        }
    return out


@dataclass
class Analysis:
    result: object        # engine RunResult
    summary: dict
    report_md: str
    observed: dict
    targets: dict
    implausibility: float
    replay: dict          # {checked, ok, msg}
    mc: object = None     # None in Preview; {metric: {median, ci, n_replicates, provenance}} in Research
    transparency: object = None  # DSA/§230/CN/FTC-style transparency-report tally


def run_and_analyze(cfg: RunConfig, *, write: bool = True,
                    verify_replay: bool | None = None, n_replicates: int = 1,
                    campaigns_fn=None, workers: int = 1, progress_callback=None,
                    on_phase=None) -> Analysis:
    """Run a simulation and produce the full analytic bundle.

    n_replicates: 1 = Preview (single run; within-run/analytic intervals only).
        >1 = Research run; additionally attaches `mc` Monte Carlo percentile
        intervals (provenance 'mc-replicated') over that many replicates.
    verify_replay: None auto-decides by scale (<= REPLAY_AGENT_LIMIT agents).
    progress_callback(tick, n_ticks): per-tick hook (e.g. web progress meter).
    on_phase(str): coarse phase labels ("simulating", "verifying replay").
    """
    def phase(p):
        if on_phase:
            on_phase(p)

    if verify_replay is None:
        verify_replay = cfg.n_agents <= REPLAY_AGENT_LIMIT

    phase("simulating")
    result = Simulation(cfg, campaigns=campaigns_fn(cfg) if campaigns_fn else None
                        ).run(write=write, progress_callback=progress_callback)
    summary = summarize_run(result)
    observed = compute_observed(result, summary)
    targets = load_targets(cfg.benchmark)

    replay = {"checked": False, "ok": None, "msg": "skipped (large run)"}
    if verify_replay:
        phase("verifying replay")
        def _replay_run(cd):
            rc = RunConfig.from_dict(cd)
            campaigns = campaigns_from_specs(result.manifest.campaign_specs)
            if campaigns is None and campaigns_fn:
                campaigns = campaigns_fn(rc)
            return Simulation(rc, campaigns=campaigns).run().log
        ok, msg = verify(result.manifest, result.log.stream_hash(), _replay_run)
        replay = {"checked": True, "ok": bool(ok), "msg": msg}

    mc = None
    if n_replicates and n_replicates > 1:
        phase("monte carlo")
        mc = mc_bundle(cfg, n_replicates, campaigns_fn, workers=workers)

    transparency = transparency_report(
        result.log, PolicyEngine(cfg.jurisdictions, cfg.ftc_enabled))

    return Analysis(
        result=result, summary=summary,
        report_md=render(summary, result.manifest, mc=mc),
        observed=observed, targets=targets,
        implausibility=implausibility(observed, targets), replay=replay, mc=mc,
        transparency=transparency)
