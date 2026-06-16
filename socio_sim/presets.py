"""Scenario presets for the web console.

Each preset is a partial set of form fields the UI applies on selection. They
are convenience starting points organised by research question — jurisdiction
regimes and use-case scenarios — not the only way to configure a run. Every
field remains individually editable afterwards.
"""

from __future__ import annotations

PRESETS = {
    "custom": {
        "label": "Custom",
        "desc": "Start from defaults and set every parameter yourself.",
        "fields": {},
    },
    "eu_dsa": {
        "label": "EU · DSA regime",
        "desc": "Digital Services Act: removal notices, appeals, easy flagging, "
                "non-personalised feed option, ad bans for minors/sensitive data.",
        "fields": {
            "jurisdictions": ["EU"], "ftc_enabled": True,
            "feed_strategy": "personalized", "eu_optout_rate": 0.30,
            "human_review_accuracy": 0.94, "human_review_delay_ticks": 12,
            "appeal_grant_fp_rate": 0.75,
        },
    },
    "us_230": {
        "label": "US · Section 230",
        "desc": "Good-Samaritan immunity for good-faith removals; criminal / IP "
                "/ privacy carve-outs escalate. No mandated notices or appeals.",
        "fields": {
            "jurisdictions": ["US"], "ftc_enabled": True,
            "feed_strategy": "personalized", "human_review_accuracy": 0.90,
        },
    },
    "cn_label": {
        "label": "China · AI labelling",
        "desc": "2025 measures: explicit + implicit AI-content labels; platform "
                "adds notices to unlabelled synthetic media; 6-month log retention.",
        "fields": {
            "jurisdictions": ["CN"], "ftc_enabled": False,
            "rate_ai_generated": 0.20, "human_review_accuracy": 0.93,
        },
    },
    "multi_regime": {
        "label": "Multi-jurisdiction",
        "desc": "All three packs active at once — compare overlapping obligations "
                "in a single world.",
        "fields": {
            "jurisdictions": ["US", "EU", "CN"], "ftc_enabled": True,
            "eu_optout_rate": 0.25,
        },
    },
    "marketing_ab": {
        "label": "Marketing experiment",
        "desc": "Ad A/B focus: larger RCT holdout, FTC disclosure on, frequency "
                "caps relaxed to measure incremental lift.",
        "fields": {
            "jurisdictions": ["US"], "ftc_enabled": True, "ftc_compliance": True,
            "ads_enabled": True, "holdout_fraction": 0.25,
            "ad_frequency_cap_per_day": 6, "ad_slot_interval": 4,
        },
    },
    "misinfo_stress": {
        "label": "Misinformation stress test",
        "desc": "Elevated misinfo prevalence with amplifier + spammer adversaries; "
                "EU pack engaged to test downranking and labelling response.",
        "fields": {
            "jurisdictions": ["EU"], "rate_misinfo": 0.10, "rate_fraud": 0.03,
            "red_team": ["misinfo_amplifier", "spammer"],
            "feed_strategy": "personalized", "exploration_epsilon": 0.15,
        },
    },
    "harassment_audit": {
        "label": "Moderation fairness audit",
        "desc": "Higher harassment/hate prevalence and a weaker classifier to "
                "surface false-positive / false-negative disparities across groups.",
        "fields": {
            "jurisdictions": ["EU"], "rate_harassment": 0.05, "rate_hate": 0.04,
            "classifier_precision": 0.80, "classifier_recall": 0.75,
            "human_review_accuracy": 0.85,
        },
    },
}
