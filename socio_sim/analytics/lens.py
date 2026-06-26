"""Run 'lens' — which decision domain a configuration emphasises, and what the
headline output therefore means.

A run is read through up to two lenses:
  * **Government / Regulatory** — jurisdiction packs (US §230, EU DSA, CN AI-label,
    FTC), classifier operating point, human review, appeals, transparency. The
    output to read is the compliance/safety surface.
  * **Marketing** — advertising with the organic-baseline RCT holdout. The output
    to read is incrementality/ROI.

The settings audit (docs/MODELS.md) shows knobs are lens-specific, so the report
and UI state which lens is active and what its ending output represents. This is
descriptive labelling, not a new model.
"""

from __future__ import annotations

PACK_NAMES = {"US": "§230", "EU": "DSA", "CN": "AI-label"}

#: Which lens each configurable setting belongs to (for UI tagging + docs).
SETTING_LENS = {
    # Government / Regulatory
    "jurisdictions": "government", "ftc_enabled": "government",
    "classifier_precision": "government", "classifier_recall": "government",
    "classifier_mode": "government", "human_review_accuracy": "government",
    "human_review_delay_ticks": "government", "appeal_grant_fp_rate": "government",
    "eu_optout_rate": "government", "red_team": "government",
    "rate_hate": "government", "rate_harassment": "government",
    "rate_fraud": "government", "rate_misinfo": "government",
    "rate_adult": "government", "rate_illegal_goods": "government",
    "rate_self_harm": "government", "rate_ai_generated": "government",
    # Marketing
    "ads_enabled": "marketing", "ftc_compliance": "marketing",
    "holdout_fraction": "marketing", "ad_frequency_cap_per_day": "marketing",
    "ad_slot_interval": "marketing", "campaigns": "marketing",
    # Core / neutral (shared substrate)
    "graph_kind": "core", "homophily_rewire_fraction": "core",
    "feed_strategy": "core", "exploration_epsilon": "core", "feed_size": "core",
    "n_agents": "core", "n_ticks": "core", "n_topics": "core",
    "follow_rate": "core", "unfollow_rate": "core", "churn_rate": "core",
    "profile": "core", "benchmark": "core", "root_seed": "core",
    "tick_hours": "core", "n_replicates": "core", "verify_replay": "core",
    "content_mode": "core", "llm_model": "core", "llm_base_url": "core",
}


def run_lens(config: dict, summary: dict) -> dict:
    """Return the active lens(es) + a plain-language interpretation of the output."""
    juris = list(config.get("jurisdictions", []) or [])
    ftc = bool(config.get("ftc_enabled", False))
    ads = bool(config.get("ads_enabled", False))
    packs = [f"{j}·{PACK_NAMES.get(j, j)}" for j in juris] + (["FTC"] if ftc else [])

    def _n(x, d=2):  # format a possibly-NaN metric cleanly ("n/a" not "nan")
        return f"{x:.{d}f}" if isinstance(x, (int, float)) and x == x else "n/a"

    he = summary["harmful_exposure"]["rate"]
    mod = summary["moderation"]
    gov_out = (f"harmful-exposure {_n(he, 4)}/impression · moderation precision "
               f"{_n(mod['precision'])} / recall {_n(mod['recall'])} · appeals + "
               f"transparency tally")

    # Marketing headline numbers (so the marketing view shows ROI data, not just
    # prose) — best-lift campaign from the run's ad metrics.
    ads_sum = summary.get("ads") or {}
    mkt_rows = [m for m in ads_sum.values() if isinstance(m, dict)]
    mkt_out = ""
    if ads and mkt_rows:
        best = max(ads_sum.items(),
                   key=lambda kv: (kv[1].get("lift", 0.0) if isinstance(kv[1], dict) else 0.0))
        cid, m = best
        mkt_out = (f"top campaign '{cid}' incremental lift {_n(m.get('lift'), 4)} · "
                   f"CTR {_n(m.get('ctr'), 4)} · ROI {_n(m.get('roi'))}")

    lines = [
        f"**Government / Regulatory lens — ACTIVE** ({', '.join(packs) or 'none'}). "
        f"Output to read: {gov_out}.",
        (f"**Marketing lens — ACTIVE** (advertising on). Output to read: {mkt_out or 'incremental lift / ROAS per campaign'} "
         "— see the Ads tab / 'Ad campaigns' report section (incremental lift vs the "
         "organic-baseline RCT holdout)."
         if ads else "**Marketing lens — off** (advertising disabled)."),
        ("Switching a **Government** setting (jurisdiction pack, classifier "
         "operating point, human review, appeals) changes the COMPLIANCE/SAFETY "
         "output; switching a **Marketing** setting (ads, holdout, frequency, "
         "campaigns) changes the INCREMENTALITY/ROI output."),
    ]
    return {"government_active": True, "marketing_active": ads,
            "packs": packs, "lines": lines,
            "government_output": gov_out, "marketing_output": mkt_out}


def render_lens_md(config: dict, summary: dict) -> list:
    lens = run_lens(config, summary)
    return ["## Run lens & output interpretation", *[f"- {ln}" for ln in lens["lines"]], ""]
