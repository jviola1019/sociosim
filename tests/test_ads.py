import numpy as np

from socio_sim.ads.auction import AdSystem
from socio_sim.ads.campaigns import Campaign
from socio_sim.ads.measure import apply_fdr, beta_interval, measure_campaign
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


def test_second_price_auction_respects_remaining_budget():
    camp = [
        Campaign(id="tight", advertiser="T", bid=5.0, budget=1.0),
        Campaign(id="runner", advertiser="R", bid=3.0, budget=100.0),
    ]
    ads, log, personas, _ = setup(campaigns=camp, holdout_fraction=0.0)
    creative = ads.run_auction(agent_id=adult_id(personas), tick=1)
    assert creative is not None
    assert creative.campaign_id == "runner"
    assert camp[0].budget == 1.0
    assert camp[1].budget == 99.0  # pays tight campaign's effective bid, not 3.0
    auction = [e for e in log.by_kind("ad_auction") if "price" in e["data"]][0]
    assert auction["data"]["price"] == 1.0


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


def test_eu_sensitive_targeting_strip_is_logged():
    camp = [Campaign(id="sens", advertiser="S", bid=5.0, budget=1000,
                     targeting={"ideology": "left"})]
    ads, log, personas, _ = setup(("EU",), campaigns=camp, holdout_fraction=0.0)
    assert ads.run_auction(agent_id=adult_id(personas), tick=7) is not None
    strips = [e for e in log.by_kind("ad_auction")
              if e["data"].get("action") == "strip_targeting"]
    assert strips
    assert strips[0]["tick"] == 7
    assert strips[0]["data"]["rule_id"] == "EU-ADS-SENS-1"


def test_eu_sensitive_strip_event_is_not_counted_as_paid_impression():
    camp = [Campaign(id="sens", advertiser="S", bid=5.0, budget=1000,
                     targeting={"ideology": "left"})]
    ads, log, personas, _ = setup(("EU",), campaigns=camp, holdout_fraction=0.0)
    assert ads.run_auction(agent_id=adult_id(personas), tick=7) is not None
    priced = [e for e in log.by_kind("ad_auction") if "price" in e["data"]]
    strips = [e for e in log.by_kind("ad_auction")
              if e["data"].get("action") == "strip_targeting"]
    assert len(priced) == 1 and strips
    m = measure_campaign(log, camp[0], ads, n_agents=100)
    apply_fdr([m])
    assert m["impressions"] == 1
    assert m["spend"] == priced[0]["data"]["price"]


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


def test_ad_conversion_logged_at_actual_tick_and_horizon_limited():
    class FixedLatency:
        def __init__(self, draw):
            self.draw = draw
        def geometric(self, p):
            return self.draw

    camp = [Campaign(id="lat", advertiser="L", bid=5.0, budget=1000,
                     base_ctr=1.0, base_cvr=1.0)]
    ads, log, personas, _ = setup(campaigns=camp, holdout_fraction=0.0)
    ads.latency_rng = FixedLatency(3)  # latency = 2 ticks
    creative = ads.run_auction(adult_id(personas), tick=5)
    ads.simulate_response(adult_id(personas), creative, tick=5)
    conv = log.by_kind("ad_conversion")[-1]
    assert conv["tick"] == 7
    assert conv["data"]["impression_tick"] == 5

    ads2, log2, personas2, _ = setup(campaigns=[Campaign(id="late", advertiser="L",
                                         bid=5.0, budget=1000,
                                         base_ctr=1.0, base_cvr=1.0)],
                                     holdout_fraction=0.0, n_ticks=6)
    ads2.latency_rng = FixedLatency(3)  # tick 5 + 2 falls beyond horizon
    creative2 = ads2.run_auction(adult_id(personas2), tick=5)
    ads2.simulate_response(adult_id(personas2), creative2, tick=5)
    assert not log2.by_kind("ad_conversion")


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


def test_attribution_window_limits_credited_conversions():
    """A tighter attribution window must credit no more ad conversions (and no
    more lift) than a wide one — measured on the same run."""
    camp = [Campaign(id="aw", advertiser="A", bid=5.0, budget=100_000,
                     base_ctr=1.0, base_cvr=1.0)]
    ads, log, personas, _ = setup(campaigns=camp, holdout_fraction=0.3,
                                  ad_frequency_cap_per_day=100)
    personas.base_conversion[:] = 0.02
    _run_baseline(ads, personas, n=100)
    for t in range(48):
        for aid in range(100):
            if personas.is_minor[aid]:
                continue
            cr = ads.run_auction(aid, t)
            if cr:
                ads.simulate_response(aid, cr, t)
    wide = measure_campaign(log, Campaign(id="aw", advertiser="A", bid=5.0,
                            budget=100_000, attribution_window_ticks=9999), ads, 100)
    tight = measure_campaign(log, Campaign(id="aw", advertiser="A", bid=5.0,
                             budget=100_000, attribution_window_ticks=0), ads, 100)
    assert wide["attributed_ad_conversions"] >= 1
    assert tight["attributed_ad_conversions"] <= wide["attributed_ad_conversions"]
    assert tight["lift"] <= wide["lift"] + 1e-9


def test_marketing_metrics_present_and_consistent():
    """ROAS/iROAS/CAC/LTV + oracle diagnostic + lift p-value are reported and coherent
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
    apply_fdr([m])
    for k in ("roas", "iroas", "cac", "ltv", "incremental_ltv",
              "oracle_covariate_adjusted_simulation_diagnostic",
              "lift_pvalue", "lift_pvalue_raw", "lift_qvalue_bh",
              "lift_significant", "lift_significant_bh_fdr", "mde",
              "budget_configured", "budget_remaining", "budget_exhausted",
              "economics_provenance", "economic_inputs", "lift_ci_method",
              "revenue"):
        assert k in m, f"missing {k}"
    assert m["mde"] > 0  # holdout sized -> a finite detectable effect
    assert "dose_response" in m and len(m["dose_response"]) >= 1
    for bucket in m["dose_response"]:
        assert "freq" in bucket and bucket["n"] > 0 and 0 <= bucket["conv_rate"] <= 1
    assert m["lift"] > 0 and m["iroas"] > 0 and m["roas"] > 0
    assert m["revenue"] > 0
    assert m["lift_pvalue"] < 0.05 and m["lift_significant"] is True
    assert m["lift_qvalue_bh"] <= 0.05 and m["lift_significant_bh_fdr"] is True
    assert m["spend"] <= m["budget_configured"] + 1e-9
    assert m["economics_provenance"] == "scenario_assumption"
    assert m["lift_ci_method"] == "uncorrected_newcombe_95"
    assert np.isfinite(m["oracle_covariate_adjusted_simulation_diagnostic"])
    assert m["ltv"] == 2.0 * camp[0].ltv_multiplier


def test_apply_fdr_reports_bh_qvalues_across_campaign_family():
    measures = [
        {"lift_pvalue": 0.01},
        {"lift_pvalue": 0.03},
        {"lift_pvalue": 0.20},
    ]
    apply_fdr(measures)
    assert [round(m["lift_qvalue_bh"], 4) for m in measures] == [0.03, 0.045, 0.2]
    assert [m["lift_significant_bh_fdr"] for m in measures] == [True, True, False]
    assert [m["lift_significant"] for m in measures] == [True, True, False]
