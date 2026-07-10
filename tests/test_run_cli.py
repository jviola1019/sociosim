"""CLI diagnostics honesty (run.py): audit findings C-01, C-02, A-04.

C-01: a 2-replicate percentile range must not be labeled "95%".
C-02: the CLI must apply the same targets_metadata_complete gate the web
      layer uses before printing observed-vs-target comparisons (every
      bundled target's evidence is 'unsupported').
A-04: the implausibility cutoff must carry its provenance label.
"""

from types import SimpleNamespace

import run as run_cli


def _fake_analysis(**over):
    base = dict(
        observed={"degree_tail": 2.5},
        targets={"degree_tail": {"value": 2.3, "tolerance": 0.4}},
        implausibility=1.2,
        mc={"harmful_rate": {"median": 0.05, "ci": (0.01, 0.09)}},
        transparency=None,
    )
    base.update(over)
    return SimpleNamespace(**base)


def test_c02_cli_suppresses_unsupported_target_comparison(capsys):
    # Fake targets carry no evidence_id -> same as the bundled targets:
    # metadata incomplete -> the target-distance table must be suppressed.
    run_cli._print_diagnostics(_fake_analysis(), n_replicates=1)
    out = capsys.readouterr().out
    assert "suppressed" in out, "CLI must state the comparison was suppressed"
    assert "+/-" not in out, "no observed-vs-target distance rows"
    assert "observed" in out, "observed values themselves are still shown"


def test_c01_small_replicate_count_not_labeled_95pct(capsys):
    run_cli._print_diagnostics(_fake_analysis(), n_replicates=2)
    out = capsys.readouterr().out
    assert "95%" not in out, "a 2-point range is not a 95% interval"
    assert "N=2" in out


def test_c01_large_replicate_count_keeps_95pct_label(capsys):
    run_cli._print_diagnostics(_fake_analysis(), n_replicates=50)
    out = capsys.readouterr().out
    assert "95%" in out


def test_a04_implausibility_cutoff_carries_provenance_label(capsys):
    run_cli._print_diagnostics(_fake_analysis(), n_replicates=1)
    out = capsys.readouterr().out
    assert "3-sigma" in out, "cutoff 3.0 must cite its convention, not read as measured"
