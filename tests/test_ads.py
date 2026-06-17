import numpy as np

from socio_sim.ads.auction import AdSystem
from socio_sim.ads.campaigns import Campaign
from socio_sim.ads.measure import beta_interval, measure_campaign
from socio_sim.agents.personas import Personas
from socio_sim.agents.state import AgentState
from socio_sim.config import RunConfig
from socio_sim.logs.events import EventLog
from socio_sim.policy.engine import PolicyEngine
from socio_sim.rng import SeedTree


def setup(jurisdictions=("US",), campaigns=None, **cfg_overrides):
    cfg = RunConfig.test(jurisdictions=jurisdictions, **cfg_overrides)
    n = 100
    personas = Personas.sample(
        n, degrees=np.ones(n), rng=SeedTree(8).generator("agents", 0))
    state = AgentState.init(n, cfg.n_topics)
    log = EventLog()
    engine = PolicyEngine(jurisdictions, ftc_enabled=cfg.ftc_enabled)
    if campaigns is None:
        campaigns = [
            Campaign(id="camp-a", advertiser="A", bid=5.0, budget=1000.0,
                     base_ctr=0.02, base_cvr=0.1),
            Campaign(id="camp-b", advertiser="B", bid=3.0, budget=1000.0,
                     base_ctr=0.02, base_cvr=0.1),
        ]
    ads = AdSystem(cfg, campaigns, personas, state, engine, log,
                   SeedTree(8).generator("ads", 0))
    return ads, log, personas, state


def adult_id(personas):
    return int(np.flatnonzero(~personas.is_minor)[0])


def minor_id(personas):
    return int(np.flatnonzero(personas.is_minor)[0])


def test_second_price_auction():
    ads, log, personas, _ = setup(holdout_fraction=0.0)
    creative = ads.run_auction(agent_id=adult_id(personas), tick=1)
    assert creative is not None
    assert creative.campaign_id == "camp-a"  # higher bid wins
    auction = log.by_kind("ad_auction")[0]
    assert auction["data"]["price"] == 3.0  # pays runner-up bid


def test_eu_minors_never_targeted():
    ads, log, personas, _ = setup(("EU",), holdout_fraction=0.0)
    assert ads.run_auction(agent_id=minor_id(personas), tick=1) is None
    blocks = [e for e in log.by_kind("ad_auction")
              if e["data"].get("blocked_rule") == "EU-ADS-MINOR-1"]
    assert blocks
    # Adults still served under EU
    assert ads.run_auction(agent_id=adult_id(personas), tick=1) is not None


def test_us_mode_minors_can_be_served():
    ads, _, personas, _ = setup(("US",), holdout_fraction=0.0)
    assert ads.run_auction(agent_id=minor_id(personas), tick=1) is not None


def test_frequency_cap_binds():
    ads, _, personas, state = setup(holdout_fraction=0.0,
                                    ad_frequency_cap_per_day=2)
    aid = adult_id(personas)
    served = [ads.run_auction(aid, tick=t) for t in range(5)]
    assert sum(s is not None for s in served) == 2
    state.reset_daily_counters()
    assert ads.run_auction(aid, tick=24) is not None


def test_holdout_agents_never_exposed():
    ads, _, personas, _ = setup(holdout_fraction=0.5)
    exposed_agents = set()
    for aid in np.flatnonzero(~personas.is_minor)[:40]:
        creative = ads.run_auction(int(aid), tick=1)
        if creative is not None and creative.campaign_id == "camp-a":
            exposed_agents.add(int(aid))
    in_holdout = {a for a in exposed_agents if ads.in_holdout("camp-a", a)}
    assert not in_holdout
    assert any(ads.in_holdout("camp-a", int(a)) for a in range(100))


def test_budget_exhaustion_stops_serving():
    camp = [Campaign(id="tiny", advertiser="T", bid=5.0, budget=0.006,
                     base_ctr=1.0, base_cvr=0.0)]
    ads, _, personas, _ = setup(campaigns=camp, holdout_fraction=0.0)
    aid = adult_id(personas)
    first = ads.run_auction(aid, tick=0)
    assert first is not None  # sole bidder pays reserve (0.005), budget 0.006 covers it
    ads.state.reset_daily_counters()
    assert ads.run_auction(aid, tick=1) is None  # remaining budget below reserve


def test_ftc_disclosure_on_creatives():
    camp_ok = Campaign(id="ok", advertiser="X", bid=1, budget=10)
    creative = camp_ok.make_creative(tick=0, ftc_compliance=True)
    assert creative.disclosure_present and "#ad" in creative.text
    creative2 = camp_ok.make_creative(tick=0, ftc_compliance=False)
    assert not creative2.disclosure_present and "#ad" not in creative2.text
    assert creative.sponsored and "sponsored" in creative.true_categories


def test_click_and_conversion_events_logged():
    camp = [Campaign(id="hot", advertiser="H", bid=5.0, budget=1000,
                     base_ctr=1.0, base_cvr=1.0)]
    ads, log, personas, _ = setup(campaigns=camp, holdout_fraction=0.0,
                                  ad_frequency_cap_per_day=100)
    aid = adult_id(personas)
    for t in range(10):
        creative = ads.run_auction(aid, tick=t)
        if creative:
            ads.simulate_response(aid, creative, tick=t)
    assert log.by_kind("ad_click")
    assert log.by_kind("ad_conversion")


def test_beta_interval_covers_truth():
    lo, hi = beta_interval(successes=20, trials=1000, prior=(2, 198))
    assert lo < 0.02 < hi
    assert 0 <= lo < hi <= 1


def test_measure_campaign_reports_lift():
    ads, log, personas, _ = setup(holdout_fraction=0.3,
                                  ad_frequency_cap_per_day=100)
    camp = ads.campaigns[0]
    for t in range(48):
        for aid in range(0, 60):
            if personas.is_minor[aid]:
                continue
            creative = ads.run_auction(int(aid), tick=t)
            if creative and creative.campaign_id == camp.id:
                ads.simulate_response(int(aid), creative, tick=t)
    m = measure_campaign(log, camp, ads, n_agents=100)
    assert m["impressions"] > 0
    assert 0 <= m["ctr"] <= 1
    assert m["ctr_ci"][0] <= m["ctr"] <= m["ctr_ci"][1]
    assert "lift" in m and "spend" in m and "roi" in m


# --- P2: organic baseline -> valid incrementality -------------------------

def _run_baseline(ads, personas, n, opportunities=1):
    """Run the organic (non-ad) conversion pass for every agent."""
    for _ in range(opportunities):
        for aid in range(n):
            ads.simulate_baseline(aid, tick=0)


def test_holdout_converts_via_organic_baseline():
    """The whole point: holdout agents must be able to convert organically,
    otherwise lift is a tautology."""
    ads, log, personas, _ = setup(holdout_fraction=0.5)
    personas.base_conversion[:] = 0.9          # almost everyone converts organically
    _run_baseline(ads, personas, n=100)
    org = log.by_kind("organic_conversion")
    assert org, "no organic conversions emitted"
    cid = ads.campaigns[0].id
    converters = {e["actor_id"] for e in org if e["data"]["campaign_id"] == cid}
    assert any(ads.in_holdout(cid, a) for a in converters), \
        "no holdout agent ever converts -> lift would still be a tautology"


def test_lift_approximately_zero_under_null_ad_effect():
    """Ad adds nothing over baseline (base_cvr=0) -> incremental lift ~ 0."""
    camp = [Campaign(id="null", advertiser="N", bid=5.0, budget=10_000,
                     base_ctr=1.0, base_cvr=0.0)]   # clicks but never converts via ad
    ads, log, personas, _ = setup(campaigns=camp, holdout_fraction=0.3,
                                  ad_frequency_cap_per_day=100)
    personas.base_conversion[:] = 0.1
    _run_baseline(ads, personas, n=100, opportunities=3)
    for t in range(48):
        for aid in range(100):
            if personas.is_minor[aid]:
                continue
            cr = ads.run_auction(aid, t)
            if cr:
                ads.simulate_response(aid, cr, t)
    m = measure_campaign(log, camp[0], ads, n_agents=100)
    assert m["n_holdout"] > 0 and m["holdout_rate"] > 0     # baseline works
    # Statistically correct null guard: the holdout-based CI must bracket 0
    # (we cannot reject "no incremental effect"). Magnitude is a sanity bound.
    assert m["lift_ci"][0] <= 0 <= m["lift_ci"][1]
    assert abs(m["lift"]) < 0.2


def test_lift_positive_only_when_ad_adds_conversions():
    camp = [Campaign(id="hot", advertiser="H", bid=5.0, budget=100_000,
                     base_ctr=1.0, base_cvr=1.0)]   # ad converts on every impression
    ads, log, personas, _ = setup(campaigns=camp, holdout_fraction=0.3,
                                  ad_frequency_cap_per_day=100)
    personas.base_conversion[:] = 0.05             # low organic baseline
    _run_baseline(ads, personas, n=100)
    for t in range(48):
        for aid in range(100):
            if personas.is_minor[aid]:
                continue
            cr = ads.run_auction(aid, t)
            if cr:
                ads.simulate_response(aid, cr, t)
    m = measure_campaign(log, camp[0], ads, n_agents=100)
    assert m["lift"] > 0
    assert m["exposed_rate"] > m["holdout_rate"]
    assert m["lift_ci"][0] > 0                       # significantly positive


def test_marketing_metrics_present_and_consistent():
    """ROAS/iROAS/CAC/LTV + CUPED lift + lift p-value are reported and coherent
    under a strong (clearly incremental) ad effect."""
    camp = [Campaign(id="m", advertiser="M", bid=5.0, budget=100_000,
                     base_ctr=1.0, base_cvr=1.0, conversion_value=2.0)]
    ads, log, personas, _ = setup(campaigns=camp, holdout_fraction=0.3,
                                  ad_frequency_cap_per_day=100)
    personas.base_conversion[:] = 0.05
    _run_baseline(ads, personas, n=100)
    for t in range(48):
        for aid in range(100):
            if personas.is_minor[aid]:
                continue
            cr = ads.run_auction(aid, t)
            if cr:
                ads.simulate_response(aid, cr, t)
    m = measure_campaign(log, camp[0], ads, n_agents=100)
    for k in ("roas", "iroas", "cac", "ltv", "incremental_ltv",
              "lift_cuped", "lift_pvalue", "lift_significant", "mde"):
        assert k in m, f"missing {k}"
    assert m["mde"] > 0  # holdout sized -> a finite detectable effect
    assert m["lift"] > 0 and m["iroas"] > 0 and m["roas"] > 0
    assert m["lift_pvalue"] < 0.05 and m["lift_significant"] is True
    assert np.isfinite(m["lift_cuped"])
    assert m["ltv"] == 2.0 * camp[0].ltv_multiplier
