"""Ad measurement with Bayesian uncertainty (Spec §3.7).

CTR/CVR get Beta-Binomial posteriors (benchmark-derived priors); incremental
lift compares exposed vs holdout conversion rates with a normal-approximation
interval. Every metric ships with its interval — no point estimates alone.
"""

from __future__ import annotations

import numpy as np
from scipy import stats

from socio_sim.ads.campaigns import Campaign
from socio_sim.logs.events import EventLog
from socio_sim.stats import (benjamini_hochberg, min_detectable_effect,
                             newcombe_diff_ci, prob_diff_positive,
                             two_proportion_p)


def _cuped_lift(ads, exposed, holdout, converted) -> float:
    """CUPED-adjusted lift using each agent's latent baseline propensity as a
    pre-treatment covariate (Deng et al. 2013): reduces variance without bias.
    """
    personas = ads.personas
    exp, hld = sorted(exposed), sorted(holdout)
    if not exp or not hld:
        return float("nan")
    ye = np.array([1.0 if a in converted else 0.0 for a in exp])
    yh = np.array([1.0 if a in converted else 0.0 for a in hld])
    xe = np.array([float(personas.base_conversion[a]) for a in exp])
    xh = np.array([float(personas.base_conversion[a]) for a in hld])
    x_all, y_all = np.concatenate([xe, xh]), np.concatenate([ye, yh])
    var_x = float(np.var(x_all))
    if var_x <= 0:
        return float(ye.mean() - yh.mean())
    theta = float(np.cov(y_all, x_all)[0, 1] / var_x)
    xbar = float(x_all.mean())
    return float((ye - theta * (xe - xbar)).mean()
                 - (yh - theta * (xh - xbar)).mean())


def apply_fdr(measures, alpha: float = 0.05):
    """Set `lift_significant` on each campaign measure via Benjamini-Hochberg
    FDR across the family of lift p-values (avoids false 'significant lift'
    findings when many campaigns are tested). Mutates and returns `measures`."""
    valid = [(i, m["lift_pvalue"]) for i, m in enumerate(measures)
             if m.get("lift_pvalue") == m.get("lift_pvalue")]
    if valid:
        idxs, pvals = zip(*valid)
        rejected = benjamini_hochberg(pvals, alpha)
        for j, i in enumerate(idxs):
            measures[i]["lift_significant"] = rejected[j]
    return measures

#: Beta prior ≈ 1% CTR with effective sample size 200 (benchmark-aligned).
DEFAULT_CTR_PRIOR = (2.0, 198.0)


def beta_interval(successes: int, trials: int,
                  prior: tuple = DEFAULT_CTR_PRIOR) -> tuple:
    a = prior[0] + successes
    b = prior[1] + trials - successes
    lo, hi = stats.beta.ppf([0.025, 0.975], a, b)
    return float(lo), float(hi)


def measure_campaign(log: EventLog, campaign: Campaign, ads,
                     n_agents: int) -> dict:
    cid = campaign.id
    auctions = [e for e in log.by_kind("ad_auction")
                if e["data"].get("campaign_id") == cid
                and "price" in e["data"]]
    clicks = [e for e in log.by_kind("ad_click")
              if e["data"].get("campaign_id") == cid]
    convs = [e for e in log.by_kind("ad_conversion")
             if e["data"].get("campaign_id") == cid]
    org_convs = [e for e in log.by_kind("organic_conversion")
                 if e["data"].get("campaign_id") == cid]
    opportunities = [e for e in log.by_kind("ad_opportunity")
                     if e["data"].get("campaign_id") == cid]
    disclosure_insertions = [
        e for e in log.by_kind("moderation")
        if e["content_id"] and str(e["content_id"]).startswith(f"ad-{cid}-")
        and e["data"].get("action") == "insert_disclosure"
    ]

    impressions = len(auctions)
    spend = float(sum(e["data"]["price"] for e in auctions))
    n_clicks, n_convs = len(clicks), len(convs)

    ctr = n_clicks / impressions if impressions else 0.0
    cvr = n_convs / n_clicks if n_clicks else 0.0
    revenue = float(sum(e["data"]["value"] for e in convs))

    # Incremental lift via eligible-opportunity ITT. The auction logs an
    # opportunity for every targeted active ad slot before holdout suppression.
    # Denominators therefore match treatment/holdout users who had a real ad
    # opportunity, not merely users who happened to receive a paid impression.
    # This avoids conditioning the treatment arm on delivery/activity. CI:
    # Newcombe (Wilson-hybrid) difference of two proportions; P(lift>0) from
    # independent Jeffreys-Beta posteriors. Provenance: analytic / Bayesian,
    # NOT Monte Carlo across replicates (run multiple replicates for that).
    exposed = {e["actor_id"] for e in opportunities
               if not e["data"].get("holdout")}
    holdout = {e["actor_id"] for e in opportunities
               if e["data"].get("holdout")}
    if not opportunities:
        # Backward-compatible fallback for logs created before ad_opportunity.
        exposed = {e["actor_id"] for e in auctions}
        holdout = {a for a in range(n_agents)
                   if ads.in_holdout(cid, a) and ads._targeting_match(campaign, a)}
    # Attribution window: credit an ad conversion only if it lands within W
    # ticks of the impression (applied symmetrically; organic baseline has no
    # ad latency). A tighter window credits fewer ad conversions -> lower lift.
    window = campaign.attribution_window_ticks
    ad_convs_attr = [
        e for e in convs
        if e["tick"] - e["data"].get("impression_tick", e["tick"]) <= window
    ]
    converted = ({e["actor_id"] for e in ad_convs_attr}
                 | {e["actor_id"] for e in org_convs})
    n_exposed, n_holdout = len(exposed), len(holdout)
    x_exposed = len(exposed & converted)
    x_holdout = len(holdout & converted)
    exposed_rate = (x_exposed / n_exposed) if n_exposed else 0.0
    holdout_rate = (x_holdout / n_holdout) if n_holdout else 0.0
    lift = exposed_rate - holdout_rate
    lift_cuped = _cuped_lift(ads, exposed, holdout, converted)
    lift_pvalue = two_proportion_p(x_exposed, n_exposed, x_holdout, n_holdout)

    # Marketing economics. SYNTHETIC: depend on conversion_value / ltv_multiplier
    # assumptions, and iROAS/CAC on the (now valid) incremental lift. Not real $.
    # Frequency dose-response (ITT): conversion rate by impression count for
    # exposed agents. Baseline is frequency-independent, so a rising curve
    # reflects the ad dose. Buckets 1, 2, 3, 4+.
    impr_by_agent: dict = {}
    for e in auctions:
        impr_by_agent[e["actor_id"]] = impr_by_agent.get(e["actor_id"], 0) + 1
    dose: dict = {}
    for aid, freq in impr_by_agent.items():
        b = freq if freq < 4 else 4
        d = dose.setdefault(b, [0, 0])
        d[1] += 1
        if aid in converted:
            d[0] += 1
    dose_response = [{"freq": ("4+" if b == 4 else str(b)), "n": d[1],
                      "conv_rate": (d[0] / d[1]) if d[1] else 0.0}
                     for b, d in sorted(dose.items())]

    incr_conv = max(lift, 0.0) * n_exposed
    roas = (revenue / spend) if spend else float("nan")
    iroas = (incr_conv * campaign.conversion_value / spend) if spend else float("nan")
    cac = (spend / incr_conv) if incr_conv > 0 else float("nan")
    ltv = campaign.conversion_value * campaign.ltv_multiplier

    return {
        "campaign_id": cid,
        "advertiser": campaign.advertiser,
        "targeting": dict(campaign.targeting),
        "creative_key": "|".join([
            cid,
            campaign.advertiser,
            str(sorted(campaign.targeting.items())),
            str(campaign.base_ctr),
            str(campaign.base_cvr),
        ]),
        "disclosure_present": bool(ads._compliance(campaign) or disclosure_insertions),
        "ftc_disclosure_inserted": bool(disclosure_insertions),
        "impressions": impressions,
        "eligible_opportunities": len(opportunities),
        "clicks": n_clicks,
        "conversions": n_convs,
        "organic_conversions": len(org_convs),
        "spend": spend,
        "ctr": ctr,
        "ctr_ci": beta_interval(n_clicks, impressions),
        "cvr": cvr,
        "cvr_ci": beta_interval(n_convs, max(n_clicks, 1), prior=(1.0, 19.0)),
        "cpm": (spend / impressions * 1000) if impressions else 0.0,
        "cpc": (spend / n_clicks) if n_clicks else float("nan"),
        "roi": ((revenue - spend) / spend) if spend else float("nan"),
        "lift": lift,
        "estimand": "eligible_opportunity_itt",
        "lift_ci": newcombe_diff_ci(x_exposed, n_exposed, x_holdout, n_holdout),
        "lift_cuped": lift_cuped,
        "lift_pvalue": lift_pvalue,
        "lift_significant": bool(lift_pvalue < 0.05) if lift_pvalue == lift_pvalue
        else False,
        "exposed_rate": exposed_rate,
        "holdout_rate": holdout_rate,
        "prob_lift_positive": prob_diff_positive(x_exposed, n_exposed,
                                                 x_holdout, n_holdout),
        "mde": min_detectable_effect(n_exposed, n_holdout, holdout_rate),
        "attribution_window_ticks": window,
        "attributed_ad_conversions": len(ad_convs_attr),
        "dose_response": dose_response,
        "roas": roas,
        "iroas": iroas,
        "cac": cac,
        "ltv": ltv,
        "incremental_ltv": incr_conv * ltv,
        "n_exposed": n_exposed,
        "n_holdout": n_holdout,
    }
