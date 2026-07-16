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

import re
from pathlib import Path

import yaml

WORKFLOW_DIR = Path(__file__).resolve().parents[1] / ".github" / "workflows"
WORKFLOW_PATH = WORKFLOW_DIR / "ci.yml"


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


# ---------------------------------------------------------------------------
# Supply-chain pinning guards (audit P2: the release workflow used to run
# `curl .../anchore/syft/main/install.sh | sh` -- executing a mutable
# upstream branch inside the release path that claims exact-SHA provenance).
# ---------------------------------------------------------------------------

def _all_workflow_texts():
    return {p.name: p.read_text(encoding="utf-8")
            for p in sorted(WORKFLOW_DIR.glob("*.yml"))}


#: Downloads of executable content from refs that can move underneath a
#: reviewed workflow: raw.githubusercontent.com/<org>/<repo>/{main,master,HEAD}
_MUTABLE_RAW_REF = re.compile(
    r"raw\.githubusercontent\.com/[^/\s]+/[^/\s]+/(main|master|HEAD)/", re.I)
#: Any `curl ... | sh` (or bash) pipeline: even a tag-pinned installer script
#: executes unverified bytes; the release path must verify a checksum instead.
_CURL_PIPE_SH = re.compile(r"curl[^\n|]*\|\s*(sudo\s+)?(ba)?sh\b")


def test_no_workflow_downloads_executables_from_mutable_refs():
    for name, text in _all_workflow_texts().items():
        assert not _MUTABLE_RAW_REF.search(text), (
            f"{name}: downloads from a mutable branch ref "
            "(main/master/HEAD); pin a release version and verify its "
            "published checksum instead")


def test_no_workflow_pipes_a_downloaded_script_into_a_shell():
    for name, text in _all_workflow_texts().items():
        assert not _CURL_PIPE_SH.search(text), (
            f"{name}: pipes a downloaded script into a shell; download a "
            "pinned release artifact and verify its sha256 before executing")


def test_all_third_party_actions_are_pinned_to_full_commit_shas():
    full_sha = re.compile(r"@[0-9a-f]{40}(\s|$)")
    for name, text in _all_workflow_texts().items():
        wf = yaml.safe_load(text)
        for job in wf.get("jobs", {}).values():
            for step in job.get("steps", []):
                uses = step.get("uses", "")
                if not uses or uses.startswith("./"):
                    continue
                assert full_sha.search(uses + " "), (
                    f"{name}: action {uses!r} is not pinned to a full "
                    "40-hex commit SHA (floating tags can be retargeted)")


def test_release_verifies_syft_checksum_before_generating_the_sbom():
    text = (WORKFLOW_DIR / "release.yml").read_text(encoding="utf-8")
    assert "SYFT_SHA256" in text and "sha256sum --check --strict" in text, (
        "release.yml must verify the pinned Syft checksum (fail closed) "
        "before any SBOM generation")
    # The verified install step must appear before the first syft invocation
    # that produces the SBOM.
    assert text.index("sha256sum --check --strict") < text.index("spdx-json")
