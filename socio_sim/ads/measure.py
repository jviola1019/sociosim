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
                and "blocked_rule" not in e["data"]]
    clicks = [e for e in log.by_kind("ad_click")
              if e["data"].get("campaign_id") == cid]
    convs = [e for e in log.by_kind("ad_conversion")
             if e["data"].get("campaign_id") == cid]

    impressions = len(auctions)
    spend = float(sum(e["data"]["price"] for e in auctions))
    n_clicks, n_convs = len(clicks), len(convs)

    ctr = n_clicks / impressions if impressions else 0.0
    cvr = n_convs / n_clicks if n_clicks else 0.0
    revenue = float(sum(e["data"]["value"] for e in convs))

    # Incremental lift: exposed vs holdout conversion rate per agent.
    exposed = {e["actor_id"] for e in auctions}
    converted = {e["actor_id"] for e in convs}
    holdout = {a for a in range(n_agents) if ads.in_holdout(cid, a)}
    exposed_rate = (len(exposed & converted) / len(exposed)) if exposed else 0.0
    holdout_rate = (len(holdout & converted) / len(holdout)) if holdout else 0.0
    lift = exposed_rate - holdout_rate
    se = float(np.sqrt(
        (exposed_rate * (1 - exposed_rate) / max(len(exposed), 1))
        + (holdout_rate * (1 - holdout_rate) / max(len(holdout), 1))))

    return {
        "campaign_id": cid,
        "impressions": impressions,
        "clicks": n_clicks,
        "conversions": n_convs,
        "spend": spend,
        "ctr": ctr,
        "ctr_ci": beta_interval(n_clicks, impressions),
        "cvr": cvr,
        "cvr_ci": beta_interval(n_convs, max(n_clicks, 1), prior=(1.0, 19.0)),
        "cpm": (spend / impressions * 1000) if impressions else 0.0,
        "cpc": (spend / n_clicks) if n_clicks else float("nan"),
        "roi": ((revenue - spend) / spend) if spend else float("nan"),
        "lift": lift,
        "lift_ci": (lift - 1.96 * se, lift + 1.96 * se),
        "n_exposed": len(exposed),
        "n_holdout": len(holdout),
    }
