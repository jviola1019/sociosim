"""Custom campaigns (campaign editor) flow through the pipeline, MC, and replay."""

from socio_sim.ads.campaigns import Campaign
from socio_sim.config import RunConfig
from socio_sim.pipeline import run_and_analyze


def custom_fn(cfg):
    # Fresh Campaign objects each call (budget is mutated during a run).
    return [Campaign(id="solo", advertiser="X", bid=3.0,
                     budget=0.02 * cfg.n_agents, base_ctr=0.02, base_cvr=0.05)]


def test_run_and_analyze_uses_custom_campaigns():
    a = run_and_analyze(RunConfig.test(jurisdictions=("EU",)),
                        campaigns_fn=custom_fn, verify_replay=False)
    assert set(a.summary["ads"].keys()) == {"solo"}


def test_custom_campaigns_replay_is_deterministic():
    """Replay must still verify with custom campaigns (campaigns_fn is applied
    on the replay path too, in-process)."""
    a = run_and_analyze(RunConfig.test(jurisdictions=("EU",), n_agents=150),
                        campaigns_fn=custom_fn, verify_replay=True)
    assert a.replay["checked"] and a.replay["ok"], a.replay["msg"]


def test_research_mode_with_custom_campaigns():
    a = run_and_analyze(RunConfig.test(jurisdictions=("EU",), n_agents=120,
                                       n_ticks=24),
                        campaigns_fn=custom_fn, n_replicates=2,
                        verify_replay=False)
    assert a.mc is not None
    assert set(a.summary["ads"].keys()) == {"solo"}
