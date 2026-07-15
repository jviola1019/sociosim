"""Held-out aggregate backtest: fit the graph triad probability on a TRAIN
subset of the targets, then score DISJOINT held-out metrics.

Note on what these tests do and do not assert. They pin the backtest
MECHANISM (disjoint split, determinism, structured rows, a verdict that is
consistent with its own rows). They deliberately do NOT require the
simulator to pass: against the source-verified targets it does not, and a
test that demanded a pass would be pressure to loosen tolerances or retune
until the number looked good. The honest outcome is recorded instead --
see docs/AGGREGATE_FIT_FINDINGS.md.
"""

import pytest

from socio_sim.validation.backtest import PROVENANCE, leave_out_backtest


@pytest.fixture(scope="module")
def bt():
    """Against the SOURCE-VERIFIED targets (the default set)."""
    return leave_out_backtest(profile="test", n_agents=400, n_ticks=120,
                              grid=[0.4, 0.6, 0.8], seed=42)


@pytest.fixture(scope="module")
def bt_legacy():
    """Against the retired, unverifiable target set -- kept only so the
    pre-verification behaviour stays reproducible."""
    return leave_out_backtest(benchmark="legacy_unsupported_default",
                              profile="test", n_agents=400, n_ticks=120,
                              grid=[0.4, 0.6, 0.8], seed=42)


def test_train_and_holdout_are_disjoint(bt):
    assert set(bt["train_metrics"]).isdisjoint(set(bt["holdout_metrics"]))
    assert set(bt["holdout_metrics"]) <= {"degree_tail_exponent",
                                          "diurnal_peak_hour"}
    assert bt["chosen_p"] in (0.4, 0.6, 0.8)          # p chosen from the grid


def test_verdict_is_consistent_with_its_own_rows(bt):
    """The mechanism invariant: the pass/fail verdict is exactly 'every
    held-out metric within tolerance', and no NaN leaks into a row."""
    assert bt["provenance"] == PROVENANCE
    for row in bt["test"]:
        assert row["z"] == row["z"]                   # finite (no NaN leaked)
        assert row["within_tolerance"] == (row["z"] <= 1.0)
    assert bt["test_pass"] == all(r["within_tolerance"] for r in bt["test"])


def test_backtest_against_verified_targets_does_not_pass(bt):
    """Records the MEASURED reality (2026-07-13 verification pass): held out
    against targets whose values were actually read out of their sources, the
    simulator's degree tail is far outside tolerance.

    If the model is ever genuinely improved to pass, update this test
    deliberately -- and never by widening a tolerance, which is a scenario
    knob, not a confidence bound.
    """
    assert not bt["test_pass"], (
        "the simulator is not expected to reproduce real measured aggregates; "
        "see docs/AGGREGATE_FIT_FINDINGS.md")
    tail = next(r for r in bt["test"] if r["metric"] == "degree_tail_exponent")
    assert tail["z"] > 1.0 and not tail["within_tolerance"]


def test_legacy_set_remains_reproducible(bt_legacy):
    """The retired set still loads and scores, so old runs can be reproduced
    -- it is simply never the default and never decision-facing."""
    assert bt_legacy["benchmark"] == "legacy_unsupported_default"
    assert bt_legacy["test"] and bt_legacy["chosen_p"] in (0.4, 0.6, 0.8)


def test_backtest_is_deterministic():
    a = leave_out_backtest(profile="test", n_agents=400, n_ticks=120,
                           grid=[0.4, 0.6, 0.8], seed=42)
    b = leave_out_backtest(profile="test", n_agents=400, n_ticks=120,
                           grid=[0.4, 0.6, 0.8], seed=42)
    assert a["chosen_p"] == b["chosen_p"]
    assert a["implausibility_test"] == b["implausibility_test"]
