"""Held-out aggregate backtest: held-out public-aggregate metrics must fall
within tolerance after calibrating on the disjoint train subset, deterministically."""

import pytest

from socio_sim.validation.backtest import PROVENANCE, leave_out_backtest


@pytest.fixture(scope="module")
def bt():
    # fast scale + small grid; quick/calibrated scale is used for the real report
    return leave_out_backtest(benchmark="default", profile="test", n_agents=400,
                              n_ticks=120, grid=[0.4, 0.6, 0.8], seed=42,
                              test_replicates=2)


def test_train_and_holdout_are_disjoint(bt):
    assert set(bt["train_metrics"]).isdisjoint(set(bt["holdout_metrics"]))
    assert set(bt["holdout_metrics"]) <= {"degree_tail_exponent", "diurnal_peak_hour"}
    assert bt["chosen_p"] in (0.4, 0.6, 0.8)          # p chosen from the grid
    assert bt["test_observation_reused_from_training"] is False
    assert bt["test_replicate_ids"] == [1000, 1001]


def test_held_out_metrics_within_tolerance(bt):
    assert bt["provenance"] == PROVENANCE
    assert bt["test_pass"], bt["test"]                # held-out aggregate sanity check
    for row in bt["test"]:
        assert row["z"] == row["z"]                   # finite (no NaN leaked)
        assert row["observed_ci"][0] == row["observed_ci"][0]
        assert row["observed_ci"][1] == row["observed_ci"][1]
        assert "within_tolerance" in row


def test_backtest_is_deterministic():
    a = leave_out_backtest(profile="test", n_agents=400, n_ticks=120,
                           grid=[0.4, 0.6, 0.8], seed=42, test_replicates=2)
    b = leave_out_backtest(profile="test", n_agents=400, n_ticks=120,
                           grid=[0.4, 0.6, 0.8], seed=42, test_replicates=2)
    assert a["chosen_p"] == b["chosen_p"]
    assert a["implausibility_test"] == b["implausibility_test"]
