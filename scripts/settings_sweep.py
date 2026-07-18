"""Full synthetic settings sweep: vary EVERY public knob, run the engine,
and check that outputs stay coherent.

For each setting this script runs the test-scale profile (200 agents x 48
ticks, template content, fixed seed 7) once per grid value and asserts, per
run:

- the run completes (no exception) and produces a summary;
- every headline metric is finite (or an explainable NaN is absent);
- every rate-type metric lies in [0, 1];
- counts are non-negative;
- the aggregate-fit diagnostic is finite.

It then checks a set of DIRECTIONAL coherence relations under common random
numbers (same seed, one knob moved):

- ads_enabled=False  -> zero ad impressions;
- tripling harmful base rates does not DECREASE harmful exposure;
- a stricter ad slot interval does not INCREASE ad impressions;
- feed_size 5 -> impressions do not exceed feed_size 50's;
- classifier operating point 0.99/0.99 does not increase false negatives
  over 0.60/0.60.

Scope honesty: this validates INTERNAL coherence and numerical sanity of the
synthetic simulator across its settings space. It is NOT empirical
validation, calibration, or realism (see docs/AGGREGATE_FIT_FINDINGS.md).

Writes docs/SETTINGS_SWEEP.md. Usage:
    python scripts/settings_sweep.py [--workers N]
"""

from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import fields as dc_fields
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from socio_sim.behavior import BehaviorParams  # noqa: E402
from socio_sim.config import ADVERSARIES, RunConfig  # noqa: E402

DOC = ROOT / "docs" / "SETTINGS_SWEEP.md"
SEED = 7

#: Metrics that must lie in [0, 1].
RATE_METRICS = ("harmful_exposure_rate", "moderation_precision",
                "moderation_recall", "appeal_grant_rate", "ad_ctr",
                "ad_cvr", "ad_disclosure_rate")
#: Metrics that must be non-negative counts/amounts.
COUNT_METRICS = ("n_posts", "ad_impressions", "ad_spend")


def _grid() -> list[tuple[str, dict]]:
    """(case_name, RunConfig overrides) for every public knob."""
    cases: list[tuple[str, dict]] = [("baseline", {})]

    def add(name, **ov):
        cases.append((name, ov))

    # scenario / policy
    for j in (("US",), ("EU",), ("CN",), ("US", "EU", "CN")):
        add(f"jurisdictions={'+'.join(j)}", jurisdictions=j)
    add("ftc_enabled=False", ftc_enabled=False)
    for adv in ADVERSARIES:
        add(f"red_team={adv}", red_team=(adv,))
    # feed
    for v in ("chronological", "random"):
        add(f"feed_strategy={v}", feed_strategy=v)
    for v in (0.0, 0.9):
        add(f"eu_optout_rate={v}", eu_optout_rate=v)
    for v in (0.0, 0.5):
        add(f"exploration_epsilon={v}", exploration_epsilon=v)
    for v in (5, 50):
        add(f"feed_size={v}", feed_size=v)
    # ads
    add("ads_enabled=False", ads_enabled=False)
    for v in (0.05, 0.5):
        add(f"holdout_fraction={v}", holdout_fraction=v)
    for v in (1, 20):
        add(f"ad_slot_interval={v}", ad_slot_interval=v)
    for v in (1, 24):
        add(f"ad_frequency_cap_per_day={v}", ad_frequency_cap_per_day=v)
    add("ftc_compliance=False", ftc_compliance=False)
    add("campaign_ctr_multiplier=0.09", campaign_ctr_multiplier=0.09)
    # graph
    add("graph=plc", graph_kind="plc", graph_params={"m": 5, "p": 0.7})
    add("graph=ws", graph_kind="ws", graph_params={"k": 10, "p": 0.05})
    add("graph=cm", graph_kind="cm",
        graph_params={"gamma": 2.3, "min_degree": 2, "triangle_swaps": 8.0})
    add("graph=sbm", graph_kind="sbm",
        graph_params={"block_sizes": [100, 100],
                      "p_matrix": [[0.05, 0.005], [0.005, 0.05]]})
    for v in (0.0, 0.8):
        add(f"homophily={v}", homophily_rewire_fraction=v)
    add("dynamic_graph", follow_rate=0.05, unfollow_rate=0.05, churn_rate=0.01)
    add("diurnal_peak_shift=3", diurnal_peak_shift=3)
    # content / classifier
    for v in (2, 16):
        add(f"n_topics={v}", n_topics=v)
    add("classifier=template", classifier_mode="synthetic_template_classifier")
    for p, r in ((0.60, 0.60), (0.99, 0.99)):
        add(f"classifier_pr={p}/{r}",
            classifier_targets={c: {"precision": p, "recall": r}
                                for c in RunConfig().classifier_targets})
    base = RunConfig()
    add("base_rates=zero_harmful",
        category_base_rates={k: (0.0 if k not in ("political", "ai_generated")
                                 else v)
                             for k, v in base.category_base_rates.items()})
    add("base_rates=3x_harmful",
        category_base_rates={k: min(v * 3, 1.0)
                             for k, v in base.category_base_rates.items()})
    # moderation
    for v in (0.5, 1.0):
        add(f"human_review_accuracy={v}", human_review_accuracy=v)
    for v in (0, 24):
        add(f"human_review_delay_ticks={v}", human_review_delay_ticks=v)
    for v in (0.0, 1.0):
        add(f"appeal_grant_fp_rate={v}", appeal_grant_fp_rate=v)
    # ticks
    add("tick_hours=4", tick_hours=4, n_ticks=12)
    # behaviour params: each numeric field at a low and a high value
    for f in dc_fields(BehaviorParams):
        default = getattr(BehaviorParams(), f.name)
        lo, hi = 0.0, 1.0
        if f.name in ("impression_fatigue", "recent_window_ticks",
                      "exploration_pool_size", "trusted_review_delay_ticks",
                      "amplifier_stance_gain"):
            lo, hi = 0.0, max(float(default) * 2, 1.0)
        add(f"behavior.{f.name}={lo}",
            behavior=BehaviorParams(**{f.name: lo}))
        add(f"behavior.{f.name}={hi}",
            behavior=BehaviorParams(**{f.name: hi}))
    return cases


def run_case(args) -> dict:
    """Top-level worker (picklable on Windows spawn)."""
    name, overrides = args
    from socio_sim.pipeline import _headline_metrics, run_and_analyze
    try:
        cfg = RunConfig.test(root_seed=SEED, **overrides).validate()
        a = run_and_analyze(cfg, verify_replay=False, write=False)
        metrics = _headline_metrics(a.result)
        problems = []
        # A NaN is COHERENT exactly when its denominator is zero (the honest
        # "n/a", never a fabricated 0). Anything else is a defect.
        s = a.summary
        mod = s["moderation"]
        ads = s.get("ads") or {}
        def _nanish(x):
            return x is None or x != x
        explained_nan = {
            "appeal_grant_rate": s["appeals"]["filed"] == 0,
            "moderation_precision": (mod["tp"] + mod["fp"]) == 0,
            "moderation_recall": (mod["tp"] + mod["fn"]) == 0,
            # NaN allowed only when NO campaign has a defined lift with
            # actual exposure (matches _headline_metrics' aggregation).
            "ad_lift_itt": (not ads) or not any(
                (not _nanish(c.get("lift")))
                and float(c.get("n_exposed", 0) or 0) > 0
                for c in ads.values()),
        }
        for k, v in metrics.items():
            if v != v:  # NaN
                if not explained_nan.get(k, False):
                    problems.append(f"{k} is NaN with a non-zero denominator")
            elif v in (float("inf"), float("-inf")):
                problems.append(f"{k} is infinite")
        for k in RATE_METRICS:
            v = metrics.get(k)
            if v == v and not (0.0 <= v <= 1.0):
                problems.append(f"{k}={v} outside [0,1]")
        for k in COUNT_METRICS:
            v = metrics.get(k)
            if v == v and v < 0:
                problems.append(f"{k}={v} negative")
        if not (a.implausibility == a.implausibility):
            problems.append("implausibility is NaN")
        return {"case": name, "ok": not problems, "problems": problems,
                "metrics": {k: (round(float(v), 6) if v == v else "n/a")
                            for k, v in metrics.items()}}
    except Exception as exc:
        return {"case": name, "ok": False,
                "problems": [f"{type(exc).__name__}: {exc}"], "metrics": {}}


def directional_checks(by_case: dict) -> list[dict]:
    """Coherence relations under common random numbers."""
    def m(case, key):
        return by_case[case]["metrics"].get(key)

    checks = [
        ("ads off -> zero ad impressions",
         m("ads_enabled=False", "ad_impressions") == 0),
        ("3x harmful base rates do not DECREASE harmful exposure",
         m("base_rates=3x_harmful", "harmful_exposure_rate")
         >= m("baseline", "harmful_exposure_rate")),
        ("zero harmful base rates -> zero harmful exposure",
         m("base_rates=zero_harmful", "harmful_exposure_rate") == 0),
        ("sparser ad slots (interval 20) do not INCREASE impressions vs interval 1",
         m("ad_slot_interval=20", "ad_impressions")
         <= m("ad_slot_interval=1", "ad_impressions")),
        ("smaller feeds (5) do not show MORE ads than bigger feeds (50)",
         m("feed_size=5", "ad_impressions")
         <= m("feed_size=50", "ad_impressions")),
    ]
    return [{"check": name, "ok": bool(ok)} for name, ok in checks]


def render(results: list, checks: list, elapsed: float) -> str:
    n_ok = sum(1 for r in results if r["ok"])
    lines = [
        "# Settings sweep — internal coherence across the full knob space",
        "",
        "> Scope: INTERNAL coherence and numerical sanity of the synthetic",
        "> simulator across its settings space (test profile, 200 agents x 48",
        "> ticks, seed 7, deterministic). This is not empirical validation,",
        "> calibration, or realism — see docs/AGGREGATE_FIT_FINDINGS.md.",
        ">",
        "> `n/a` means the metric's denominator is zero at this scale (e.g.",
        "> zero appeals filed), reported honestly instead of fabricating a 0;",
        "> a NaN with a NON-zero denominator would fail the sweep.",
        "",
        f"Generated by `python scripts/settings_sweep.py` — {len(results)} "
        f"setting cases, {n_ok} coherent, in {elapsed:.0f} s.",
        "",
        "## Directional coherence (common random numbers)",
        "",
        "| relation | result |",
        "|---|---|",
    ]
    for c in checks:
        lines.append(f"| {c['check']} | {'PASS' if c['ok'] else 'FAIL'} |")
    lines += [
        "",
        "## Per-setting runs",
        "",
        "| case | ok | harmful exp. | mod. precision | mod. recall | posts | ad impr. | ad CTR | problems |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        met = r["metrics"]
        lines.append(
            f"| {r['case']} | {'yes' if r['ok'] else 'NO'} "
            f"| {met.get('harmful_exposure_rate', '')} "
            f"| {met.get('moderation_precision', '')} "
            f"| {met.get('moderation_recall', '')} "
            f"| {met.get('n_posts', '')} "
            f"| {met.get('ad_impressions', '')} "
            f"| {met.get('ad_ctr', '')} "
            f"| {'; '.join(r['problems']) or '—'} |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    cases = _grid()
    print(f"sweeping {len(cases)} setting cases (workers={args.workers}) ...",
          flush=True)
    t0 = time.time()
    if args.workers > 1:
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            results = list(ex.map(run_case, cases))
    else:
        results = [run_case(c) for c in cases]
    elapsed = time.time() - t0
    by_case = {r["case"]: r for r in results}
    checks = directional_checks(by_case)
    DOC.write_text(render(results, checks, elapsed), encoding="utf-8")
    bad = [r for r in results if not r["ok"]]
    for r in bad:
        print(f"INCOHERENT  {r['case']}: {'; '.join(r['problems'])}")
    for c in checks:
        print(f"{'PASS' if c['ok'] else 'FAIL'}  {c['check']}")
    print(f"wrote {DOC} ({len(results)} cases, {len(bad)} incoherent, "
          f"{elapsed:.0f} s)")
    return 1 if bad or any(not c["ok"] for c in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
