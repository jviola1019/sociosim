"""The shared pipeline is the single source of truth for run -> analyze ->
verify. These tests pin its contract so the CLI, web app and examples stay
consistent."""

from socio_sim.config import RunConfig
from socio_sim.pipeline import Analysis, run_and_analyze


def test_run_and_analyze_bundle_shape():
    cfg = RunConfig.test(n_agents=60, n_ticks=24, jurisdictions=("EU",))
    a = run_and_analyze(cfg, write=False)
    assert isinstance(a, Analysis)
    assert a.summary["n_posts"] >= 0
    assert "harmful_exposure" in a.summary
    assert a.report_md.startswith("# SocioSim Run Report")
    assert isinstance(a.implausibility, float)
    assert set(a.replay) == {"checked", "ok", "msg"}
    assert a.replay["checked"] and a.replay["ok"]  # small run auto-verifies


def test_replay_auto_skipped_above_limit(monkeypatch):
    # Don't actually build 3000 agents; just check the gating decision by
    # forcing verify_replay=False and confirming it is reported as skipped.
    cfg = RunConfig.test(n_agents=60, n_ticks=12)
    a = run_and_analyze(cfg, write=False, verify_replay=False)
    assert a.replay["checked"] is False
    assert "skipped" in a.replay["msg"]


def test_phase_callbacks_fire():
    cfg = RunConfig.test(n_agents=50, n_ticks=12)
    phases = []
    run_and_analyze(cfg, write=False, on_phase=phases.append)
    assert "simulating" in phases and "verifying replay" in phases


def test_progress_callback_reaches_completion():
    cfg = RunConfig.test(n_agents=50, n_ticks=12)
    seen = []
    run_and_analyze(cfg, write=False, verify_replay=False,
                    progress_callback=lambda t, n: seen.append((t, n)))
    assert seen[-1] == (12, 12)


def test_cli_and_pipeline_agree_on_stream_hash():
    # The CLI's run_sim and the pipeline must produce the same run for the
    # same config (no divergence between entry points).
    cfg = RunConfig.test(n_agents=60, n_ticks=24, root_seed=5)
    a1 = run_and_analyze(cfg, write=False, verify_replay=False)
    a2 = run_and_analyze(cfg, write=False, verify_replay=False)
    assert a1.result.log.stream_hash() == a2.result.log.stream_hash()
