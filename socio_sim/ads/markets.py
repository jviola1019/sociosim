"""Named advertiser market verticals with SOURCE-VERIFIED display-CTR anchors.

Two different taxonomies meet in the campaign editor, and naming both kills
the old opaque "Topic 0..7" market selector:

- **Content markets** (where an ad appears): the simulator's 8 content
  topics, re-exported here by name from ``socio_sim.content.generate.TOPICS``
  (local news, sports, technology, health, politics, entertainment,
  finance, lifestyle).
- **Advertiser verticals** (what kind of advertiser is buying): the nine
  industrial categories of the iPinYou RTB benchmark (Zhang, Yuan, Wang &
  Shen 2014, arXiv:1407.7073v1 -- the SAME hash-verified artifact behind
  the ``ad_ctr`` aggregate target). Each vertical carries the paper's own
  measured training-period CTR (Table 3) as a per-vertical ``base_ctr``
  anchor a campaign row can adopt.

HONESTY BOUNDARY (read before extending): these anchors are the only
per-vertical click-through numbers in this repository with an auditable
primary source. They measure 2013 China desktop/mobile DISPLAY real-time
bidding -- NOT a social feed, NOT any 2026 market, and NOT a prediction of
campaign performance. Commercial per-industry "benchmark" tables
(WordStream and similar) were deliberately rejected during the 2026-07-13
source-verification pass because their samples are proprietary and
non-auditable. Choosing a vertical sets a documented, sourced scenario
anchor; it does not make the simulation's ad output realistic for that
industry (see docs/AGGREGATE_FIT_FINDINGS.md and each target's
applicability_limits).
"""

from __future__ import annotations

from socio_sim.content.generate import TOPICS

#: Content markets: index-aligned with the engine's topic ids, so
#: ``targeting.topics = [CONTENT_MARKETS.index(name)]`` is well defined.
CONTENT_MARKETS = tuple(TOPICS)

#: Evidence record shared with the ad_ctr aggregate target (same artifact,
#: sha256 3fed0db1... pinned in sourced_aggregates_v1.json).
EVIDENCE_ID = "ev.external_aggregate.ipinyou_2014"
SOURCE = ("Zhang, Yuan, Wang & Shen 2014, 'Real-Time Bidding Benchmarking "
          "with iPinYou Dataset' (arXiv:1407.7073v1), Table 2 (advertiser "
          "categories) + Table 3 (training-period CTR per advertiser)")
APPLICABILITY_LIMITS = (
    "2013 China desktop/mobile DISPLAY RTB; one advertiser per vertical; "
    "NOT social-feed advertising, NOT period-stable, NOT a performance "
    "prediction. Sourced anchor for scenario exploration only.")

#: Advertiser verticals: iPinYou advertiser id -> (label, measured
#: training-period CTR from Table 3, one-line note). Values are the paper's
#: own percentages converted to fractions; nothing is interpolated.
ADVERTISER_VERTICALS = {
    "vertical_ecommerce_cn": {
        "label": "E-commerce (vertical retail)",
        "ipinyou_advertiser": 1458,
        "base_ctr": 0.00080,          # Table 3: 0.080%
        "note": "Chinese vertical e-commerce advertiser, season 2",
    },
    "cpg_milk_powder": {
        "label": "Consumer packaged goods",
        "ipinyou_advertiser": 2259,
        "base_ctr": 0.00034,          # Table 3: 0.034%
        "note": "Milk-powder advertiser, season 3",
    },
    "telecom": {
        "label": "Telecom",
        "ipinyou_advertiser": 2261,
        "base_ctr": 0.00030,          # Table 3: 0.030%
        "note": "Telecom advertiser, season 3",
    },
    "apparel_footwear": {
        "label": "Apparel / footwear",
        "ipinyou_advertiser": 2821,
        "base_ctr": 0.00064,          # Table 3: 0.064%
        "note": "Footwear advertiser, season 3",
    },
    "mobile_app_install": {
        "label": "Mobile app install",
        "ipinyou_advertiser": 2997,
        "base_ctr": 0.00444,          # Table 3: 0.444%
        "note": ("Mobile e-commerce app-install advertiser; the paper "
                 "attributes the outlier CTR to the mobile 'fat finger' "
                 "effect"),
    },
    "software": {
        "label": "Software",
        "ipinyou_advertiser": 3358,
        "base_ctr": 0.00078,          # Table 3: 0.078%
        "note": "Software advertiser, season 2",
    },
    "ecommerce_international": {
        "label": "E-commerce (international)",
        "ipinyou_advertiser": 3386,
        "base_ctr": 0.00073,          # Table 3: 0.073%
        "note": "International e-commerce advertiser, season 2",
    },
    "energy_oil": {
        "label": "Energy / oil",
        "ipinyou_advertiser": 3427,
        "base_ctr": 0.00074,          # Table 3: 0.074%
        "note": "Oil advertiser, season 2",
    },
    "automotive_tire": {
        "label": "Automotive (tire)",
        "ipinyou_advertiser": 3476,
        "base_ctr": 0.00052,          # Table 3: 0.052%
        "note": "Tire advertiser, season 2",
    },
}


def vertical_base_ctr(vertical_id: str) -> float:
    """The sourced display-CTR anchor for a vertical; KeyError on unknown."""
    return float(ADVERTISER_VERTICALS[vertical_id]["base_ctr"])


def meta_payload() -> dict:
    """What the web UI needs to render both selectors, with provenance."""
    return {
        "content_markets": list(CONTENT_MARKETS),
        "advertiser_verticals": {
            vid: {"label": v["label"], "base_ctr": v["base_ctr"],
                  "ipinyou_advertiser": v["ipinyou_advertiser"],
                  "note": v["note"]}
            for vid, v in ADVERTISER_VERTICALS.items()},
        "evidence_id": EVIDENCE_ID,
        "source": SOURCE,
        "applicability_limits": APPLICABILITY_LIMITS,
    }
