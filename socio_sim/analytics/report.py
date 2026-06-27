"""Markdown report rendering (Spec 3.8).

Headline rates carry uncertainty intervals; descriptive diagnostics are labelled
as point/count summaries. Human-facing reports never render raw NaN/Infinity.
"""

from __future__ import annotations

import math

from socio_sim import (NO_REAL_PERSON_DATA_NOTICE, NOT_LEGAL_ADVICE_NOTICE,
                       RESEARCH_USE_NOTICE)
from socio_sim.analytics.lens import render_lens_md
from socio_sim.logs.manifest import Manifest


def _finite(value) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _num(value, digits: int = 3) -> str:
    return f"{float(value):.{digits}f}" if _finite(value) else "n/a"


def _ci(pair) -> str:
    if not pair or len(pair) != 2 or not all(_finite(x) for x in pair):
        return "n/a (95%)"
    lo, hi = pair
    return f"[{lo:.4f}, {hi:.4f}] (95%)"


def render(summary: dict, manifest: Manifest, mc: dict | None = None) -> str:
    mod = summary["moderation"]
    app = summary["appeals"]
    notices = summary["notices"]
    provenance = summary.get("metric_provenance") or {}
    lines = [
        "# SocioSim Run Report",
        "",
        "> ## Research use only",
        f"> {RESEARCH_USE_NOTICE}",
        f"> {NOT_LEGAL_ADVICE_NOTICE}",
        f"> {NO_REAL_PERSON_DATA_NOTICE}",
        "",
        "## Run identity",
        f"- Config hash: `{manifest.config_hash}`",
        f"- Root seed: {manifest.root_seed} | package {manifest.package_version}",
        f"- Policy packs: {manifest.pack_versions}",
        f"- Event-stream hash: `{manifest.stream_hash}`",
        "",
        *render_lens_md(manifest.config, summary),
        "## Uncertainty provenance",
        "- Intervals below are **single-run**: within-run bootstrap (harmful "
        "exposure, welfare), analytic Wilson score (moderation precision/recall, "
        "appeal-grant rate), and Beta-Binomial credible (ad CTR/CVR). They "
        "quantify within-run sampling noise, **not** Monte Carlo variation "
        "across replicates. Run the research (multi-replicate) mode for "
        "mc-replicated intervals.",
        "",
    ]
    if provenance:
        lines.extend([
            "## Metric provenance",
            "| metric | provenance | unit | limitation |",
            "|---|---|---|---|",
        ])
        for name, meta in sorted(provenance.items()):
            lines.append(
                f"| `{name}` | `{meta.get('provenance', 'unsupported')}` | "
                f"{meta.get('unit', 'n/a')} | {meta.get('limitations', 'n/a')} |")
        lines.append("")
    if mc:
        finite_n = max((d.get("n_replicates", 0) for d in mc.values()), default=0)
        lines.extend([
            "## Monte Carlo intervals",
            f"- Provenance: **mc-replicated** ({finite_n} replicates where finite)",
        ])
        for name, d in sorted(mc.items()):
            lo, hi = d["ci"]
            lines.append(
                f"- {name.replace('_', ' ')}: median {_num(d['median'], 4)}, "
                f"95% [{_num(lo, 4)}, {_num(hi, 4)}]")
        lines.append("")
    lines.extend([
        "## Volume",
        f"- Posts: {summary['n_posts']} | Impressions: {summary['n_impressions']}"
        f" | Engagements: {summary['n_engagements']}",
        "",
        "## Harmful-content exposure",
        f"- Rate: {_num(summary['harmful_exposure']['rate'], 4)} per impression, "
        f"per-agent CI {_ci(summary['harmful_exposure']['ci'])}",
        "",
        "## Moderation quality",
        f"- Precision {_num(mod['precision'])} CI {_ci(mod['precision_ci'])} | "
        f"Recall {_num(mod['recall'])} CI {_ci(mod['recall_ci'])}",
        f"- FPR {_num(mod['fpr'], 4)} | FNR {_num(mod['fnr'])} "
        f"(TP {mod['tp']}, FP {mod['fp']}, FN {mod['fn']}, TN {mod['tn']})",
        f"- Sample sufficiency: harmful n={mod.get('n_harmful', 0)}, "
        f"benign n={mod.get('n_benign', 0)}"
        + ("; insufficient sample for stable moderation/fairness conclusions"
           if mod.get("insufficient_sample") else ""),
        "",
        "## Appeals & process",
        f"- Filed {app['filed']} | resolved {app['resolved']} | "
        f"granted rate {_num(app['granted_rate'])} CI {_ci(app['granted_rate_ci'])} | "
        f"mean resolution {_num(app['mean_resolution_ticks'], 1)} ticks",
        f"- Human reviews {app['human_reviews']} | "
        f"deadline-miss rate {_num(app['deadline_miss_rate'])}",
        f"- Notices sent {notices['notices_sent']} | removal-notice coverage "
        f"{_num(notices['removal_notice_coverage'])}",
        "",
        "## Cascades",
        f"- Count {summary['cascades']['n']} | mean size "
        f"{_num(summary['cascades']['mean'], 2)} | max {summary['cascades']['max']}",
        "",
        "## Welfare proxy",
        f"- Mean {_num(summary['welfare']['mean'], 4)}, CI {_ci(summary['welfare']['ci'])}",
        "",
        "## Fairness diagnostics (moderation FPR/FNR by author group)",
    ])
    for key, groups in summary["fairness"].items():
        lines.append(f"### {key}")
        for group, data in sorted(groups.items()):
            suffix = "; insufficient sample" if data.get("insufficient_sample") else ""
            lines.append(
                f"- {group}: FPR {_num(data['fpr'], 4)} | FNR {_num(data['fnr'], 4)} "
                f"(posts={data['n_posts']}, harmful={data.get('n_harmful', 0)}, "
                f"benign={data.get('n_benign', 0)}{suffix})")
    mp = summary.get("minor_protection")
    if mp:
        jurisdictions = set(manifest.config.get("jurisdictions", []) or [])
        lines.append("")
        lines.append("## Minor protection (rights-impact)")
        base = (f"- Ad impressions to minors: {mp['ad_impressions_to_minors']} "
                f"of {mp['ad_impressions']} ({_num(mp['minor_ad_rate'], 4)})")
        if "EU" in jurisdictions:
            lines.append(base + " - 0 expected under the EU minor-ad ban "
                         "(EU-ADS-MINOR-1).")
        else:
            lines.append(base + " - tracked for rights-impact comparison; "
                         "no EU minor-ad ban is active in this run.")
    lines.append("")
    lines.append("## Ad campaigns")
    for cid, metrics in summary["ads"].items():
        sig = "significant" if metrics.get("lift_significant_bh_fdr") else "n.s."
        lines.append(
            f"- **{cid}**: {metrics['impressions']} impr | "
            f"CTR {_num(metrics['ctr'], 4)} CI {_ci(metrics['ctr_ci'])} | "
            f"CVR {_num(metrics['cvr'], 4)} | CPM {_num(metrics['cpm'], 2)} | "
            f"spend {_num(metrics['spend'], 2)} of budget "
            f"{_num(metrics.get('budget_configured'), 2)} | "
            f"lift {_num(metrics['lift'], 4)} raw CI {_ci(metrics['lift_ci'])} "
            f"({metrics.get('lift_ci_method', 'uncorrected_newcombe_95')}; "
            f"exposed {metrics['n_exposed']}, holdout {metrics['n_holdout']})")
        lines.append(
            f"  - incrementality: {metrics.get('estimand', 'eligible-opportunity ITT')} | "
            f"CUPED-lift {_num(metrics['lift_cuped'], 4)} | "
            f"p(raw)={_num(metrics.get('lift_pvalue_raw', metrics.get('lift_pvalue')), 3)} | "
            f"q(BH)={_num(metrics.get('lift_qvalue_bh'), 3)} ({sig}, BH-FDR) | "
            f"MDE {_num(metrics['mde'], 4)}")
        lines.append(
            f"  - scenario economics ({metrics.get('economics_provenance', 'scenario_assumption')}): "
            f"ROAS {_num(metrics['roas'], 2)} | iROAS {_num(metrics['iroas'], 2)} | "
            f"CAC {_num(metrics['cac'], 2)} | LTV {_num(metrics['ltv'], 2)} | "
            f"attribution {metrics['attribution_window_ticks']}t "
            f"({metrics['attributed_ad_conversions']} credited); depends on "
            "conversion_value / ltv_multiplier assumptions")
    lines.append("")
    lines.append("## Graph")
    graph = summary["graph"]
    lines.append(f"- n={graph['n']} m={graph['m']} clustering={_num(graph['clustering'], 4)} "
                 f"degree mean/max {_num(graph['degree_mean'], 1)}/"
                 f"{_num(graph['degree_max'], 0)}")
    if "initial" in graph and "final" in graph:
        initial = graph["initial"]
        lines.append(f"- Dynamic graph: values above are final topology; initial "
                     f"m={initial['m']} clustering={_num(initial['clustering'], 4)}")
    return "\n".join(lines)
