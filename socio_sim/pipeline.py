"""Single source of truth for the run → analyze → calibrate → verify pipeline.

The CLI launcher (run.py), the web backend (web/app.py) and the example scripts
all call `run_and_analyze` so they can never drift. Anything UI-specific
(progress bars, JSON shaping, charts) wraps this; the core stays here.
"""

from __future__ import annotations

from dataclasses import dataclass

from socio_sim.analytics.metrics import summarize_run
from socio_sim.analytics.report import render
from socio_sim.config import RunConfig
from socio_sim.engine import Simulation
from socio_sim.logs.replay import verify
from socio_sim.validation.calibrate import implausibility
from socio_sim.validation.targets import compute_observed, load_targets

#: Replay verification doubles runtime, so it is auto-skipped above this size.
REPLAY_AGENT_LIMIT = 2000


@dataclass
class Analysis:
    result: object        # engine RunResult
    summary: dict
    report_md: str
    observed: dict
    targets: dict
    implausibility: float
    replay: dict          # {checked, ok, msg}


def run_and_analyze(cfg: RunConfig, *, write: bool = True,
                    verify_replay: bool | None = None,
                    progress_callback=None, on_phase=None) -> Analysis:
    """Run a simulation and produce the full analytic bundle.

    verify_replay: None auto-decides by scale (<= REPLAY_AGENT_LIMIT agents).
    progress_callback(tick, n_ticks): per-tick hook (e.g. web progress meter).
    on_phase(str): coarse phase labels ("simulating", "verifying replay").
    """
    def phase(p):
        if on_phase:
            on_phase(p)

    if verify_replay is None:
        verify_replay = cfg.n_agents <= REPLAY_AGENT_LIMIT

    phase("simulating")
    result = Simulation(cfg).run(write=write, progress_callback=progress_callback)
    summary = summarize_run(result)
    observed = compute_observed(result, summary)
    targets = load_targets()

    replay = {"checked": False, "ok": None, "msg": "skipped (large run)"}
    if verify_replay:
        phase("verifying replay")
        ok, msg = verify(
            result.manifest, result.log.stream_hash(),
            lambda cd: Simulation(RunConfig.from_dict(cd)).run().log)
        replay = {"checked": True, "ok": bool(ok), "msg": msg}

    return Analysis(
        result=result, summary=summary,
        report_md=render(summary, result.manifest),
        observed=observed, targets=targets,
        implausibility=implausibility(observed, targets), replay=replay)
