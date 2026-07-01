"""Unit tests for the context-aware claim scanner (AUDIT_LOG.md R8-CLAIMSCAN).

These exercise the scanning *functions* directly against synthetic text
rather than the real repo, so they stay meaningful regardless of what the
docs currently say, and prove the scanner both fires on real overclaim
patterns and stays silent on honest hedged/historical/code-identifier text.
"""

import importlib.util
import sys
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "claim_scan", Path(__file__).resolve().parents[1] / "scripts" / "claim_scan.py")
claim_scan = importlib.util.module_from_spec(_SPEC)
sys.modules["claim_scan"] = claim_scan
_SPEC.loader.exec_module(claim_scan)


def test_stale_phrase_is_caught():
    errs = claim_scan._stale_phrase_errors("x.md", "our results are evidence-based")
    assert errs


def test_unhedged_claim_term_is_flagged():
    errs = claim_scan._context_aware_errors(
        "x.md", "This output is a calibrated, production-ready forecast.")
    assert any("calibrated" in e for e in errs)


def test_hedged_claim_term_is_not_flagged():
    text = "This output is not a validated, production-ready forecast."
    errs = claim_scan._context_aware_errors("x.md", text)
    assert errs == []


def test_exempt_phrase_validation_ladder_not_flagged():
    text = "## Validation Ladder\n\nThe implemented ladder labels are listed below."
    errs = claim_scan._context_aware_errors("x.md", text)
    assert errs == []


def test_module_path_in_inline_code_not_flagged():
    text = "Diagnostics from `validation/benchmark_eval.py` apply only here."
    errs = claim_scan._context_aware_errors("x.md", text)
    assert errs == []


def test_python_import_line_not_flagged():
    text = "from socio_sim.validation.study import render_validation_report"
    errs = claim_scan._context_aware_errors("run.py", text)
    assert errs == []


def test_dict_subscript_identifier_not_flagged():
    text = "print(f\"I = {study['calibration']['implausibility']:.2f}\")"
    errs = claim_scan._context_aware_errors("run.py", text)
    assert errs == []


def test_full_scan_of_repo_passes():
    """End-to-end: the actual repo, as committed, must currently pass clean."""
    assert claim_scan.main() == 0
