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
    "eu_optout_rate": "government",
    # Marketing
    "ads_enabled": "marketing", "ftc_compliance": "marketing",
    "holdout_fraction": "marketing", "ad_frequency_cap_per_day": "marketing",
    "ad_slot_interval": "marketing", "campaigns": "marketing",
    # Core / neutral (shared substrate)
    "graph_kind": "core", "homophily_rewire_fraction": "core",
    "feed_strategy": "core", "exploration_epsilon": "core", "feed_size": "core",
    "n_agents": "core", "n_ticks": "core", "n_topics": "core",
    "follow_rate": "core", "unfollow_rate": "core", "churn_rate": "core",
}


def run_lens(config: dict, summary: dict) -> dict:
    """Return the active lens(es) + a plain-language interpretation of the output."""
    juris = list(config.get("jurisdictions", []) or [])
    ftc = bool(config.get("ftc_enabled", False))
    ads = bool(config.get("ads_enabled", False))
    packs = [f"{j}·{PACK_NAMES.get(j, j)}" for j in juris] + (["FTC"] if ftc else [])

    he = summary["harmful_exposure"]["rate"]
    mod = summary["moderation"]
    gov_out = (f"harmful-exposure {he:.4f}/impression · moderation precision "
               f"{mod['precision']:.2f} / recall {mod['recall']:.2f} · appeals + "
               f"transparency tally")

    lines = [
        f"**Government / Regulatory lens — ACTIVE** ({', '.join(packs) or 'none'}). "
        f"Output to read: {gov_out}.",
        ("**Marketing lens — ACTIVE** (advertising on). Output to read: incremental "
         "ad lift vs the organic-baseline RCT holdout (iROAS) + ROAS/CAC/LTV per "
         "campaign — see the Ads tab / 'Ad campaigns' report section."
         if ads else "**Marketing lens — off** (advertising disabled)."),
        ("Switching a **Government** setting (jurisdiction pack, classifier "
         "operating point, human review, appeals) changes the COMPLIANCE/SAFETY "
         "output; switching a **Marketing** setting (ads, holdout, frequency, "
         "campaigns) changes the INCREMENTALITY/ROI output."),
    ]
    return {"government_active": True, "marketing_active": ads,
            "packs": packs, "lines": lines, "government_output": gov_out}


def render_lens_md(config: dict, summary: dict) -> list:
    lens = run_lens(config, summary)
    return ["## Run lens & output interpretation", *[f"- {ln}" for ln in lens["lines"]], ""]
