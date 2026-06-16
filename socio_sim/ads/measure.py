"""Ad measurement with Bayesian uncertainty (Spec §3.7).

CTR/CVR get Beta-Binomial posteriors (benchmark-derived priors); incremental
lift compares exposed vs holdout conversion rates with a normal-approximation
interval. Every metric ships with its interval — no point estimates alone.
"""

from __future__ import annotations

from scipy import stats

from socio_sim.ads.campaigns import Campaign
from socio_sim.logs.events import EventLog
from socio_sim.stats import newcombe_diff_ci, prob_diff_positive

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
    org_convs = [e for e in log.by_kind("organic_conversion")
                 if e["data"].get("campaign_id") == cid]

    impressions = len(auctions)
    spend = float(sum(e["data"]["price"] for e in auctions))
    n_clicks, n_convs = len(clicks), len(convs)

    ctr = n_clicks / impressions if impressions else 0.0
    cvr = n_convs / n_clicks if n_clicks else 0.0
    revenue = float(sum(e["data"]["value"] for e in convs))

    # Incremental lift via clean-holdout RCT. An agent "converts" if it
    # converted through EITHER channel (ad OR organic baseline); holdout agents
    # can only convert organically, so exposed_rate - holdout_rate isolates the
    # ad's incremental effect. Both arms are restricted to the targeted
    # population so the comparison is apples-to-apples. CI: Newcombe
    # (Wilson-hybrid) difference of two proportions; P(lift>0) from independent
    # Jeffreys-Beta posteriors. Provenance: analytic / Bayesian, NOT Monte Carlo
    # across replicates (run multiple replicates for that).
    exposed = {e["actor_id"] for e in auctions}
    holdout = {a for a in range(n_agents)
               if ads.in_holdout(cid, a) and ads._targeting_match(campaign, a)}
    converted = ({e["actor_id"] for e in convs}
                 | {e["actor_id"] for e in org_convs})
    n_exposed, n_holdout = len(exposed), len(holdout)
    x_exposed = len(exposed & converted)
    x_holdout = len(holdout & converted)
    exposed_rate = (x_exposed / n_exposed) if n_exposed else 0.0
    holdout_rate = (x_holdout / n_holdout) if n_holdout else 0.0
    lift = exposed_rate - holdout_rate

    return {
        "campaign_id": cid,
        "impressions": impressions,
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
        "lift_ci": newcombe_diff_ci(x_exposed, n_exposed, x_holdout, n_holdout),
        "exposed_rate": exposed_rate,
        "holdout_rate": holdout_rate,
        "prob_lift_positive": prob_diff_positive(x_exposed, n_exposed,
                                                 x_holdout, n_holdout),
        "n_exposed": n_exposed,
        "n_holdout": n_holdout,
    }
