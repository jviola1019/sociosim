"""Held-out aggregate backtest: held-out public-aggregate metrics must fall
within tolerance after calibrating on the disjoint train subset, deterministically."""

import pytest

from socio_sim.validation.backtest import PROVENANCE, leave_out_backtest


@pytest.fixture(scope="module")
def bt():
    # fast scale + small grid; quick/calibrated scale is used for the real report
    return leave_out_backtest(benchmark="default", profile="test", n_agents=400,
                              n_ticks=120, grid=[0.4, 0.6, 0.8], seed=42)


def test_train_and_holdout_are_disjoint(bt):
    assert set(bt["train_metrics"]).isdisjoint(set(bt["holdout_metrics"]))
    assert set(bt["holdout_metrics"]) <= {"degree_tail_exponent", "diurnal_peak_hour"}
    assert bt["chosen_p"] in (0.4, 0.6, 0.8)          # p chosen from the grid


def test_held_out_metrics_within_tolerance(bt):
    assert bt["provenance"] == PROVENANCE
    assert bt["test_pass"], bt["test"]                # held-out aggregate sanity check
    for row in bt["test"]:
        assert row["z"] == row["z"]                   # finite (no NaN leaked)
        assert "within_tolerance" in row


def test_backtest_is_deterministic():
    a = leave_out_backtest(profile="test", n_agents=400, n_ticks=120,
                           grid=[0.4, 0.6, 0.8], seed=42)
    b = leave_out_backtest(profile="test", n_agents=400, n_ticks=120,
                           grid=[0.4, 0.6, 0.8], seed=42)
    assert a["chosen_p"] == b["chosen_p"]
    assert a["implausibility_test"] == b["implausibility_test"]
