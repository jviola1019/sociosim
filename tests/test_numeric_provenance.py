"""The numeric-default provenance scanner is itself a gate: every numeric
default on a decision-facing surface must be registry-covered or carry a
justified allowlist entry, and the allowlist may not go stale."""

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "numeric_provenance_scan",
    ROOT / "scripts" / "numeric_provenance_scan.py")
scan = importlib.util.module_from_spec(_SPEC)
sys.modules["numeric_provenance_scan"] = scan
_SPEC.loader.exec_module(scan)


def test_full_scan_of_repo_passes():
    assert scan.main() == 0


def test_scanner_actually_finds_the_known_decision_surfaces():
    """Guard against the scanner silently going blind: representative
    defaults from every surface class must be discovered."""
    found = scan.collect()
    assert "socio_sim/config.py::RunConfig.eu_optout_rate" in found
    assert "socio_sim/web/app.py::MAX_BODY_BYTES" in found
    assert "run.py::argparse.--seed" in found
    assert "socio_sim/web/static/app.js::base_ctr??" in found
    assert any(k.startswith("socio_sim/web/static/index.html::input#"
                            "classifier_precision") for k in found)
    assert any("WEIGHTS[" in k for k in found)


def test_every_allowlist_entry_is_justified_and_classified():
    allowlist = json.loads(
        (ROOT / "scripts" / "provenance_allowlist.json").read_text(
            encoding="utf-8"))
    assert allowlist, "allowlist unexpectedly empty"
    for key, entry in allowlist.items():
        assert entry["classification"] in scan.CLASSIFICATIONS, key
        assert len(entry["justification"]) >= 15, key
