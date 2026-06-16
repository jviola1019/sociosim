"""Markdown report rendering (Spec §3.8). Every metric carries its 95%
interval; the research-only disclaimer is embedded in every report."""

from __future__ import annotations

from socio_sim import RESEARCH_USE_NOTICE
from socio_sim.logs.manifest import Manifest


def _ci(pair) -> str:
    lo, hi = pair
    return f"[{lo:.4f}, {hi:.4f}] (95%)"


def render(summary: dict, manifest: Manifest) -> str:
    mod = summary["moderation"]
    app = summary["appeals"]
    notices = summary["notices"]
    lines = [
        "# SocioSim Run Report",
        "",
        "> ## ⚠️ Research use only",
        f"> {RESEARCH_USE_NOTICE}",
        "",
        "## Run identity",
        f"- Config hash: `{manifest.config_hash}`",
        f"- Root seed: {manifest.root_seed} | package {manifest.package_version}",
        f"- Policy packs: {manifest.pack_versions}",
        f"- Event-stream hash: `{manifest.stream_hash}`",
        "",
        "## Volume",
        f"- Posts: {summary['n_posts']} | Impressions: {summary['n_impressions']}"
        f" | Engagements: {summary['n_engagements']}",
        "",
        "## Harmful-content exposure",
        f"- Rate: {summary['harmful_exposure']['rate']:.4f} per impression, "
        f"per-agent CI {_ci(summary['harmful_exposure']['ci'])}",
        "",
        "## Moderation quality",
        f"- Precision {mod['precision']:.3f} | Recall {mod['recall']:.3f} | "
        f"FPR {mod['fpr']:.4f} | FNR {mod['fnr']:.3f} "
        f"(TP {mod['tp']}, FP {mod['fp']}, FN {mod['fn']}, TN {mod['tn']})",
        "",
        "## Appeals & process",
        f"- Filed {app['filed']} | resolved {app['resolved']} | "
        f"granted rate {app['granted_rate']:.3f} | "
        f"mean resolution {app['mean_resolution_ticks']:.1f} ticks",
        f"- Human reviews {app['human_reviews']} | "
        f"deadline-miss rate {app['deadline_miss_rate']:.3f}",
        f"- Notices sent {notices['notices_sent']} | removal-notice coverage "
        f"{notices['removal_notice_coverage']:.3f}",
        "",
        "## Cascades",
        f"- Count {summary['cascades']['n']} | mean size "
        f"{summary['cascades']['mean']:.2f} | max {summary['cascades']['max']}",
        "",
        "## Welfare proxy",
        f"- Mean {summary['welfare']['mean']:.4f}, CI {_ci(summary['welfare']['ci'])}",
        "",
        "## Fairness diagnostics (moderation FPR/FNR by author group)",
    ]
    for key, groups in summary["fairness"].items():
        lines.append(f"### {key}")
        for g, d in sorted(groups.items()):
            lines.append(f"- {g}: FPR {d['fpr']:.4f} | FNR {d['fnr']:.4f} "
                         f"(n={d['n_posts']})")
    lines.append("")
    lines.append("## Ad campaigns")
    for cid, m in summary["ads"].items():
        lines.append(
            f"- **{cid}**: {m['impressions']} impr | CTR {m['ctr']:.4f} "
            f"CI {_ci(m['ctr_ci'])} | CVR {m['cvr']:.4f} | "
            f"CPM {m['cpm']:.2f} | spend {m['spend']:.2f} | ROI {m['roi']:.2f} | "
            f"lift {m['lift']:.4f} CI {_ci(m['lift_ci'])} "
            f"(exposed {m['n_exposed']}, holdout {m['n_holdout']})")
    lines.append("")
    lines.append("## Graph")
    g = summary["graph"]
    lines.append(f"- n={g['n']} m={g['m']} clustering={g['clustering']:.4f} "
                 f"degree mean/max {g['degree_mean']:.1f}/{g['degree_max']:.0f}")
    return "\n".join(lines)
