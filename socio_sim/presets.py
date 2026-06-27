"""Scenario presets for the web console.

Each preset is a partial set of form fields the UI applies on selection, grouped
by `category` (Regulatory / Research / Business) and carrying `sources` — the
real frameworks/literature it encodes (see docs/RESEARCH_EVIDENCE.md for the full
cited evidence base). Every field remains individually editable afterwards.
Values are research-grounded scenario anchors, not predictions.
"""

from __future__ import annotations

PRESETS = {
    "custom": {
        "label": "Custom",
        "category": "General",
        "desc": "Start from defaults and set every parameter yourself.",
        "sources": [],
        "fields": {},
    },

    # ---- Regulatory regimes -------------------------------------------------
    "eu_dsa": {
        "label": "EU · DSA regime",
        "category": "Regulatory",
        "desc": "Digital Services Act: notice-and-action, statement of reasons, "
                "internal appeals (≥6 months, not solely automated), trusted-"
                "flagger priority, non-personalised feed option.",
        "sources": ["EU Reg. 2022/2065 (DSA) Arts. 16, 17, 20, 22"],
        "fields": {
            "jurisdictions": ["EU"], "ftc_enabled": True,
            "feed_strategy": "personalized", "eu_optout_rate": 0.30,
            "human_review_accuracy": 0.94, "human_review_delay_ticks": 12,
            "appeal_grant_fp_rate": 0.75,
        },
    },
    "us_230": {
        "label": "US · Section 230",
        "category": "Regulatory",
        "desc": "Good-Samaritan immunity for good-faith removals; criminal / IP "
                "/ privacy / FOSTA-SESTA carve-outs escalate. No mandated "
                "notices or appeals.",
        "sources": ["47 U.S.C. § 230 (c)(1)/(c)(2)/(e); FOSTA-SESTA 2018"],
        "fields": {
            "jurisdictions": ["US"], "ftc_enabled": True,
            "feed_strategy": "personalized", "human_review_accuracy": 0.90,
        },
    },
    "cn_label": {
        "label": "China · AI labelling",
        "category": "Regulatory",
        "desc": "2025 measures: explicit + implicit AI-content labels; platform "
                "adds notices to unlabelled synthetic media; log retention.",
        "sources": ["CAC AI-content labelling measures (eff. 2025-09-01); GB 45438-2025"],
        "fields": {
            "jurisdictions": ["CN"], "ftc_enabled": False,
            "rate_ai_generated": 0.20, "human_review_accuracy": 0.93,
        },
    },
    "ftc_disclosure": {
        "label": "US · FTC disclosures",
        "category": "Regulatory",
        "desc": "FTC endorsement guides + fake-reviews rule: clear & conspicuous "
                "disclosure of material connections; AI/bot reviews barred.",
        "sources": ["16 CFR Part 255 (rev. 2023); 16 CFR Part 465 (2024)"],
        "fields": {
            "jurisdictions": ["US"], "ftc_enabled": True, "ftc_compliance": True,
            "ads_enabled": True,
        },
    },
    "nist_rmf": {
        "label": "NIST AI RMF profile",
        "category": "Regulatory",
        "desc": "Govern/Map/Measure/Manage posture: documented classifier "
                "operating points + human-in-the-loop review, GenAI labelling on.",
        "sources": ["NIST AI RMF 1.0 (2023); NIST AI 600-1 GenAI Profile (2024)"],
        "fields": {
            "jurisdictions": ["US", "EU"], "ftc_enabled": True,
            "classifier_precision": 0.85, "classifier_recall": 0.85,
            "human_review_accuracy": 0.78, "rate_ai_generated": 0.12,
        },
    },
    "multi_regime": {
        "label": "Multi-jurisdiction",
        "category": "Regulatory",
        "desc": "All three packs active at once — compare overlapping obligations "
                "in a single world.",
        "sources": ["DSA + §230 + CN labelling, concurrently"],
        "fields": {
            "jurisdictions": ["US", "EU", "CN"], "ftc_enabled": True,
            "eu_optout_rate": 0.25,
        },
    },

    # ---- Research scenarios (adversaries folded in here) --------------------
    "misinfo_stress": {
        "label": "Misinformation stress test",
        "category": "Research",
        "desc": "Elevated misinfo prevalence with amplifier + spammer adversaries; "
                "EU pack engaged to test downranking and labelling response.",
        "sources": ["Prevalence ordering: Meta CSER; adversary model Spec §3.10"],
        "fields": {
            "jurisdictions": ["EU"], "rate_misinfo": 0.10, "rate_fraud": 0.03,
            "red_team": ["misinfo_amplifier", "spammer"],
            "feed_strategy": "personalized", "exploration_epsilon": 0.15,
        },
    },
    "harassment_audit": {
        "label": "Moderation fairness audit",
        "category": "Research",
        "desc": "Higher harassment/hate prevalence and a weaker classifier "
                "(operating point near literature lows) to surface FP/FN "
                "disparities across groups.",
        "sources": ["Classifier P/R ranges: hate-speech detection benchmarks (2025)"],
        "fields": {
            "jurisdictions": ["EU"], "rate_harassment": 0.05, "rate_hate": 0.04,
            "classifier_precision": 0.80, "classifier_recall": 0.75,
            "human_review_accuracy": 0.85,
        },
    },
    "coordinated_brigading": {
        "label": "Coordinated brigading",
        "category": "Research",
        "desc": "A brigading ring + spammers coordinate flags/engagement to game "
                "moderation and ranking; EU appeals engaged.",
        "sources": ["Coordinated inauthentic behaviour; adversary model Spec §3.10"],
        "fields": {
            "jurisdictions": ["EU"], "red_team": ["brigading_ring", "spammer"],
            "rate_harassment": 0.03, "exploration_epsilon": 0.12,
        },
    },

    # ---- Business / marketing scenarios ------------------------------------
    "marketing_ab": {
        "label": "Incrementality A/B test",
        "category": "Business",
        "desc": "Ad A/B focus: larger RCT holdout for an incremental-lift "
                "preview; use Research mode or larger scale before treating "
                "results as decision-grade.",
        "sources": ["Gordon et al. 2019 (RCT > attribution); Cohen 1988 (power)"],
        "fields": {
            "jurisdictions": ["US"], "ftc_enabled": True, "ftc_compliance": True,
            "ads_enabled": True, "holdout_fraction": 0.25,
            "ad_frequency_cap_per_day": 6, "ad_slot_interval": 4,
        },
    },
    "brand_launch": {
        "label": "Brand launch (reach)",
        "category": "Business",
        "desc": "Upper-funnel reach: frequency capped in the effective 3–7 band, "
                "personalised feed, FTC disclosures on.",
        "sources": ["Effective frequency ~3 (Krugman 1972); caps 3–7"],
        "fields": {
            "jurisdictions": ["US"], "ads_enabled": True, "ftc_compliance": True,
            "feed_strategy": "personalized", "ad_frequency_cap_per_day": 5,
            "holdout_fraction": 0.10, "ad_slot_interval": 5,
        },
    },
    "performance_campaign": {
        "label": "Performance campaign",
        "category": "Business",
        "desc": "Lower-funnel conversion: stronger holdout signal, tighter ad "
                "spacing, higher frequency for response.",
        "sources": ["Holdout 10–20% (Meta CL); LTV:CAC ≥3:1 (Skok ~2010)"],
        "fields": {
            "jurisdictions": ["US"], "ads_enabled": True, "ftc_compliance": True,
            "holdout_fraction": 0.20, "ad_frequency_cap_per_day": 7,
            "ad_slot_interval": 3,
        },
    },
    "brand_safety_stress": {
        "label": "Brand-safety stress",
        "category": "Business",
        "desc": "Stress-tests a harmful-content environment under elevated "
                "misinfo plus amplifier/spam adversaries. Ad-adjacency "
                "suitability is not directly measured in this simulator.",
        "sources": ["WFA/GARM Brand Safety Floor + Adjacency Standards (2020–22)"],
        "fields": {
            "jurisdictions": ["US"], "ads_enabled": True, "ftc_compliance": True,
            "rate_misinfo": 0.08, "red_team": ["misinfo_amplifier", "spammer"],
        },
    },
}
