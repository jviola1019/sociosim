"""Regression test for the CI ordering bug that broke PR #4.

Root cause: the "Tests (pytest + coverage gate)" step ran the full pytest
suite -- including tests/test_e2e_playwright.py, which launches a Chromium
browser -- before any step installed Playwright's browser binaries. A clean
GitHub Actions runner has no cached browser, so the embedded e2e test failed
there even though it passed on developer machines with a pre-existing
Playwright cache. All later gates (asset QA, security scans, license
inventory, wheel build) were then skipped because the failed step aborted
the job.

This test parses the workflow file directly (not by running CI) and asserts
the install step appears before the first step that runs pytest without
excluding the e2e test, so the ordering bug cannot silently regress.
"""

from pathlib import Path

import yaml

WORKFLOW_PATH = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"


def _load_steps():
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    return workflow["jobs"]["test"]["steps"]


def _step_runs(step) -> str:
    return step.get("run", "")


def test_playwright_browsers_installed_before_full_pytest_run():
    steps = _load_steps()

    install_idx = None
    pytest_idx = None
    for idx, step in enumerate(steps):
        run = _step_runs(step)
        if "playwright install" in run and install_idx is None:
            install_idx = idx
        if pytest_idx is None and "pytest" in run and "--ignore" not in run:
            # The first unscoped pytest invocation is the one that would
            # implicitly pick up tests/test_e2e_playwright.py.
            pytest_idx = idx

    assert install_idx is not None, "no step installs Playwright browsers"
    assert pytest_idx is not None, "no step runs the pytest suite"
    assert install_idx < pytest_idx, (
        "Playwright browser install must happen before the first pytest run "
        "that is not scoped away from tests/test_e2e_playwright.py, or a "
        "clean CI runner will fail with 'Executable doesn't exist' the way "
        "PR #4's CI run did"
    )


def test_no_step_runs_pytest_before_dependencies_are_installed():
    steps = _load_steps()
    install_idx = next(
        (idx for idx, step in enumerate(steps) if "pip install" in _step_runs(step)),
        None,
    )
    pytest_idx = next(
        (idx for idx, step in enumerate(steps) if "pytest" in _step_runs(step)),
        None,
    )
    assert install_idx is not None
    assert pytest_idx is not None
    assert install_idx < pytest_idx
