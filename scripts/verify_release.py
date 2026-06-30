"""Release verification orchestrator for SocioSim.

Runs the documented quality gates and writes a status report that distinguishes
passed, failed, skipped, not implemented, and not applicable checks.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs" / "audits" / "latest-release-verification.md"


@dataclass
class Check:
    name: str
    status: str
    seconds: float
    command: str
    detail: str


def run_cmd(name: str, args: list[str], timeout: int | None = None) -> Check:
    started = time.perf_counter()
    cmd_text = " ".join(args)
    try:
        proc = subprocess.run(
            args,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
        status = "passed" if proc.returncode == 0 else "failed"
        detail = proc.stdout.strip()
    except FileNotFoundError as exc:
        status = "skipped"
        detail = f"tool unavailable: {exc}"
    except subprocess.TimeoutExpired as exc:
        status = "failed"
        detail = f"timed out after {timeout}s\n{(exc.stdout or '').strip()}"
    return Check(name, status, time.perf_counter() - started, cmd_text, detail)


def python_cmd(code: str) -> list[str]:
    return [sys.executable, "-c", code]


def claim_language_check() -> Check:
    started = time.perf_counter()
    banned = [
        "will reduce misinformation",
        "will increase sales",
        "will improve roi",
        "real-world forecast",
    ]
    paths = [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]
    hits: list[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace").lower()
        for phrase in banned:
            if phrase in text and "not a real-world forecast" not in text:
                hits.append(f"{path.relative_to(ROOT)}: {phrase}")
    status = "passed" if not hits else "failed"
    detail = "no unsupported banned claim language found" if not hits else "\n".join(hits)
    return Check("Documentation/claim language validation", status,
                 time.perf_counter() - started, "internal claim-language scan", detail)


def optional_python_module_check(name: str, module: str, args: list[str]) -> Check:
    probe = subprocess.run(
        [sys.executable, "-c", f"import {module.replace('-', '_')}"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if probe.returncode != 0:
        return Check(name, "skipped", 0.0, f"{sys.executable} -m {module} {' '.join(args)}",
                     f"Python module {module!r} is not installed in this environment")
    return run_cmd(name, [sys.executable, "-m", module, *args])


def optional_python_script_check(name: str, guard_module: str, script: str) -> Check:
    """Like optional_python_module_check but runs a script file, not -m module."""
    probe = subprocess.run(
        [sys.executable, "-c", f"import {guard_module.replace('-', '_')}"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if probe.returncode != 0:
        return Check(name, "skipped", 0.0, f"python {script}",
                     f"Python module {guard_module!r} is not installed in this environment")
    return run_cmd(name, [sys.executable, script])


def docker_build_or_validate() -> Check:
    """Build the image if Docker is installed; otherwise statically validate the
    hardened Dockerfile (the full build + smoke-run runs in the CI 'docker' job).

    The static path is a real check — it asserts the hardening invariants — so a
    Docker-less environment is `passed`/`failed`, never a silent skip.
    """
    if shutil.which("docker") is not None:
        return run_cmd("Docker build", ["docker", "build", "-t", "sociosim", "."])
    started = time.perf_counter()
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    checks = {
        "digest-pinned base image": "FROM python:3.11-slim@sha256:" in dockerfile,
        "non-root USER": "\nUSER " in dockerfile,
        "HEALTHCHECK present": "HEALTHCHECK" in dockerfile,
        ".dockerignore present": (ROOT / ".dockerignore").exists(),
    }
    problems = [name for name, ok in checks.items() if not ok]
    status = "passed" if not problems else "failed"
    detail = (
        "docker not installed; Dockerfile static validation passed "
        "(" + ", ".join(checks) + "); full build + smoke-run runs in CI"
        if not problems else "Dockerfile hardening missing: " + "; ".join(problems))
    return Check("Docker image (build in CI; static Dockerfile validation here)",
                 status, time.perf_counter() - started,
                 "Dockerfile hardening static validation", detail)


def write_report(checks: list[Check]):
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    summary = {}
    for c in checks:
        summary[c.status] = summary.get(c.status, 0) + 1
    lines = [
        "# SocioSim Release Verification",
        "",
        "Generated by `python scripts/verify_release.py`.",
        "",
        "## Summary",
        "",
        "| Status | Count |",
        "| --- | ---: |",
    ]
    for status in ("passed", "failed", "skipped", "not_implemented", "not_applicable"):
        lines.append(f"| {status} | {summary.get(status, 0)} |")
    lines.extend(["", "## Checks", ""])
    for c in checks:
        detail = c.detail[-3000:] if len(c.detail) > 3000 else c.detail
        lines.extend([
            f"### {c.name}",
            "",
            f"- Status: `{c.status}`",
            f"- Runtime: `{c.seconds:.2f}s`",
            f"- Command: `{c.command}`",
            "",
            "```text",
            detail or "(no output)",
            "```",
            "",
        ])
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true",
                        help="Skip slow validation/backtest and full coverage gates.")
    args = parser.parse_args(argv)

    checks: list[Check] = []
    checks.append(run_cmd(
        "Scenario linting",
        [sys.executable, "-m", "socio_sim.experiments.scenario_lint", "examples/scenarios"]))
    checks.append(run_cmd("Lint", [sys.executable, "-m", "ruff", "check", "."]))

    if args.quick:
        checks.append(run_cmd("Unit tests", [sys.executable, "-m", "pytest", "-q"]))
        checks.append(Check("Coverage threshold", "skipped", 0.0,
                            "pytest --cov=socio_sim --cov-fail-under=85",
                            "skipped by --quick"))
    else:
        checks.append(run_cmd(
            "Unit/integration tests with coverage",
            [sys.executable, "-m", "pytest", "-q", "--cov=socio_sim",
             "--cov-report=term-missing", "--cov-fail-under=85"]))

    checks.append(run_cmd(
        "Determinism/replay smoke",
        python_cmd(
            "from socio_sim.config import RunConfig; "
            "from socio_sim.engine import Simulation; "
            "c=RunConfig.test(n_agents=80,n_ticks=12,root_seed=123); "
            "a=Simulation(c).run(); b=Simulation(c).run(); "
            "assert a.log.stream_hash()==b.log.stream_hash(); print(a.log.stream_hash())")))
    checks.append(run_cmd(
        "Policy comparison smoke",
        python_cmd(
            "from socio_sim.config import RunConfig; "
            "from socio_sim.experiments.compare import compare; "
            "from socio_sim.analytics.metrics import harmful_exposure; "
            "b=RunConfig.test(jurisdictions=('US',),n_agents=80,n_ticks=12); "
            "i=RunConfig.test(jurisdictions=('EU',),n_agents=80,n_ticks=12); "
            "m=lambda r: {'harmful_exposure_rate': harmful_exposure(r.log)[0]}; "
            "r=compare(b,i,2,m); "
            "assert 'harmful_exposure_rate' in r; print(r)")))
    checks.append(run_cmd(
        "Market holdout comparison smoke",
        python_cmd(
            "from socio_sim.config import RunConfig; "
            "from socio_sim.pipeline import run_and_analyze; "
            "from socio_sim.experiments.scenarios import disclosure_evader_campaigns; "
            "c=RunConfig.test(jurisdictions=('US',),n_agents=100,n_ticks=24,holdout_fraction=0.3); "
            "a=run_and_analyze(c,campaigns_fn=disclosure_evader_campaigns,verify_replay=False); "
            "m=next(iter(a.summary['ads'].values())); "
            "assert m['estimand']=='eligible_opportunity_itt'; "
            "assert m['economics_provenance']=='scenario_assumption'; print(m)")))

    if args.quick:
        checks.append(Check("Validation/backtest smoke", "skipped", 0.0,
                            "python run.py --validate / --backtest", "skipped by --quick"))
    else:
        checks.append(run_cmd("Validation smoke",
                              [sys.executable, "run.py", "--validate", "--sens-samples", "4"],
                              timeout=900))
        checks.append(run_cmd("Backtest smoke", [sys.executable, "run.py", "--backtest"],
                              timeout=900))

    checks.append(run_cmd("Security/config tests",
                          [sys.executable, "-m", "pytest", "-q", "tests/test_security.py"]))
    checks.append(claim_language_check())
    checks.append(run_cmd("UI/browser tests",
                          [sys.executable, "-m", "pytest", "-q",
                           "tests/test_e2e_playwright.py"], timeout=180))
    checks.append(docker_build_or_validate())
    checks.append(optional_python_module_check(
        "Bandit static security scan (medium/high)",
        "bandit", ["-r", "socio_sim/", "-ll", "-q"]))
    checks.append(optional_python_script_check(
        "pip-audit — production dependencies only",
        "pip_audit", str(ROOT / "scripts" / "audit_deps.py")))

    write_report(checks)
    print(f"Wrote {REPORT.relative_to(ROOT)}")
    print(json.dumps({c.status: sum(1 for x in checks if x.status == c.status)
                      for c in checks}, sort_keys=True))
    return 1 if any(c.status == "failed" for c in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
