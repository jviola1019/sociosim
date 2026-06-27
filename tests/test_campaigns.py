"""Custom campaigns (campaign editor) flow through the pipeline, MC, and replay."""

from socio_sim.ads.campaigns import Campaign
from socio_sim.config import RunConfig
from socio_sim.engine import Simulation
from socio_sim.logs.manifest import Manifest
from socio_sim.logs.replay import verify
from socio_sim.pipeline import run_and_analyze
import pytest


def custom_fn(cfg):
    # Fresh Campaign objects each call (budget is mutated during a run).
    return [Campaign(id="solo", advertiser="X", bid=3.0,
                     budget=0.02 * cfg.n_agents, base_ctr=0.02, base_cvr=0.05)]


def test_run_and_analyze_uses_custom_campaigns():
    a = run_and_analyze(RunConfig.test(jurisdictions=("EU",)),
                        campaigns_fn=custom_fn, verify_replay=False)
    assert set(a.summary["ads"].keys()) == {"solo"}


def test_custom_campaigns_replay_is_deterministic():
    """Replay verifies custom campaigns from manifest-persisted specs."""
    a = run_and_analyze(RunConfig.test(jurisdictions=("EU",), n_agents=150),
                        campaigns_fn=custom_fn, verify_replay=True)
    assert a.replay["checked"] and a.replay["ok"], a.replay["msg"]
    assert a.result.manifest.campaign_specs[0]["id"] == "solo"


def test_custom_campaigns_manifest_replay_after_save_load(tmp_path):
    a = run_and_analyze(RunConfig.test(jurisdictions=("EU",), n_agents=120),
                        campaigns_fn=custom_fn, verify_replay=False)
    p = tmp_path / "manifest.json"
    a.result.manifest.save(p)
    m = Manifest.load(p)
    assert m.campaign_specs and m.campaign_specs[0]["id"] == "solo"

    def replay_from_manifest(config_dict):
        return Simulation(RunConfig.from_dict(config_dict),
                          campaigns=m.campaigns()).run().log

    ok, msg = verify(m, a.result.log.stream_hash(), replay_from_manifest)
    assert ok, msg


def test_research_mode_with_custom_campaigns():
    a = run_and_analyze(RunConfig.test(jurisdictions=("EU",), n_agents=120,
                                       n_ticks=24),
                        campaigns_fn=custom_fn, n_replicates=2,
                        verify_replay=False)
    assert a.mc is not None
    assert set(a.summary["ads"].keys()) == {"solo"}


def test_campaign_measurement_uses_eligible_opportunity_itt():
    a = run_and_analyze(RunConfig.test(jurisdictions=("EU",), n_agents=120,
                                       n_ticks=24, holdout_fraction=0.5),
                        campaigns_fn=custom_fn, verify_replay=False)
    m = a.summary["ads"]["solo"]
    assert m["estimand"] == "eligible_opportunity_itt"
    assert m["eligible_opportunities"] >= m["impressions"]
    assert m["n_exposed"] + m["n_holdout"] <= m["eligible_opportunities"]
    assert all("price" not in e["data"] for e in a.result.log.by_kind("ad_opportunity"))


@pytest.mark.parametrize("kwargs, field", [
    ({"bid": 0}, "bid"),
    ({"budget": 0}, "budget"),
    ({"base_ctr": 1.2}, "base_ctr"),
    ({"base_cvr": -0.1}, "base_cvr"),
    ({"conversion_value": -1}, "conversion_value"),
    ({"ltv_multiplier": -1}, "ltv_multiplier"),
    ({"holdout_fraction": 1.5}, "holdout_fraction"),
    ({"attribution_window_ticks": -1}, "attribution_window_ticks"),
    ({"targeting": []}, "targeting"),
])
def test_campaign_constructor_rejects_invalid_programmatic_inputs(kwargs, field):
    base = dict(id="bad", advertiser="X", bid=1.0, budget=10.0)
    base.update(kwargs)
    with pytest.raises(ValueError, match=field):
        Campaign(**base)


def test_campaign_constructor_normalizes_valid_numeric_inputs():
    c = Campaign(id="ok", advertiser="X", bid="1.5", budget="10",
                 base_ctr="0.2", base_cvr="0.1",
                 attribution_window_ticks=0, holdout_fraction="0.25")
    assert c.bid == 1.5
    assert c.budget == 10.0
    assert c.attribution_window_ticks == 0
    assert c.holdout_fraction == 0.25
