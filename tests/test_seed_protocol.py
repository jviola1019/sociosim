"""Seed-generalization protocol tests (audit P1: the aggregate profile was
"matched" on one seed).

Pins: disjoint fitting/validation/holdout seed lists; an IMMUTABLE hash-locked
holdout list; target values/tolerances unchanged during tuning; acceptance
logic that fails when only seed 42 performs well; the committed protocol
artifact's honesty coupling (a failed holdout can never yield a "matched"
label); and a live multi-seed run with deterministic replay per tested seed.
"""


import numpy as np
import pytest

from socio_sim.validation import seed_protocol as sp
from socio_sim.validation.targets import load_targets

# ---------------------------------------------------------------------------
# Locked constants. Changing either invalidates every committed protocol
# artifact and MUST be a reviewed, deliberate act (this test failing is the
# review trigger), never a side effect of tuning.
# ---------------------------------------------------------------------------
HOLDOUT_SEEDS_SHA256 = (
    "338c8bfba56e3f3def9b99ab1be2c3cbe472f8fcbffc1ab2879a304979ef260c")
TARGETS_VALUES_SHA256 = (
    "4016fe238d69f9a7e3d8453d828b8c3b450843544f22bdb1b133031a6243b403")


def test_seed_lists_are_disjoint_and_sized():
    f, v, h = set(sp.FITTING_SEEDS), set(sp.VALIDATION_SEEDS), set(sp.HOLDOUT_SEEDS)
    assert len(sp.FITTING_SEEDS) == len(f) == 20
    assert len(sp.VALIDATION_SEEDS) == len(v) == 20
    assert len(sp.HOLDOUT_SEEDS) == len(h) == 20
    assert not (f & v) and not (f & h) and not (v & h)
    assert 42 in f, "seed 42 is the historical fitting seed and must stay there"
    assert 42 not in v and 42 not in h


def test_holdout_seed_list_is_immutable():
    """The locked holdout list is hash-pinned HERE, independently of the
    module: silently editing HOLDOUT_SEEDS to friendlier seeds breaks this
    test rather than the results."""
    assert sp.seeds_sha256(sp.HOLDOUT_SEEDS) == HOLDOUT_SEEDS_SHA256


def test_target_values_and_tolerances_unchanged_during_tuning():
    """Only {value, tolerance} are hashed, so provenance-metadata additions
    (source hashes, retrieval notes) are allowed while any numeric edit --
    the 'widen the tolerance until it passes' failure mode -- fails here."""
    assert sp.targets_values_sha256(load_targets()) == TARGETS_VALUES_SHA256


def _rec(seed, imp, components=None, replay_ok=True, failure=None):
    return {"seed": seed, "implausibility": imp,
            "dominant_metric": (max(components, key=components.get)
                                if components else None),
            "components": components or {}, "observed": {},
            "replay_checked": True, "replay_ok": replay_ok,
            "runtime_failure": failure}


def test_acceptance_fails_when_only_seed_42_performs_well():
    """The exact overfitting failure the protocol exists to catch: seed 42
    scores 2.5, every holdout seed scores 5. Holdout seeds never include 42,
    so the summary is all-bad and every distributional criterion trips."""
    holdout = [_rec(s, 5.0, {"clustering": 5.0}) for s in sp.HOLDOUT_SEEDS]
    verdict = sp.acceptance(sp.summarize(holdout))
    assert verdict["accepted"] is False
    assert verdict["criteria"]["pass_proportion_at_least_80pct"] is False
    assert verdict["criteria"]["median_implausibility_below_cutoff"] is False
    assert verdict["criteria"]["no_structural_metric_fails_more_than_20pct"] is False


def test_acceptance_requires_distributional_pass_not_one_good_seed():
    # 15/20 pass (75%) is still a FAIL: one (or most) seeds under the cutoff
    # is not the criterion; >=80% is.
    recs = ([_rec(s, 2.0, {"clustering": 0.5}) for s in sp.HOLDOUT_SEEDS[:15]]
            + [_rec(s, 4.0, {"appeal_grant_rate": 4.0}) for s in sp.HOLDOUT_SEEDS[15:]])
    verdict = sp.acceptance(sp.summarize(recs))
    assert verdict["accepted"] is False
    assert verdict["criteria"]["pass_proportion_at_least_80pct"] is False
    # ...whereas 17/20 (85%) with clean structure/replay is accepted.
    recs = ([_rec(s, 2.0, {"clustering": 0.5}) for s in sp.HOLDOUT_SEEDS[:17]]
            + [_rec(s, 3.5, {"appeal_grant_rate": 3.5}) for s in sp.HOLDOUT_SEEDS[17:]])
    assert sp.acceptance(sp.summarize(recs))["accepted"] is True


def test_acceptance_fails_on_replay_failure_or_runtime_failure():
    good = [_rec(s, 2.0, {"clustering": 0.5}) for s in sp.HOLDOUT_SEEDS]
    bad_replay = [dict(r) for r in good]
    bad_replay[0]["replay_ok"] = False
    assert sp.acceptance(sp.summarize(bad_replay))["accepted"] is False
    crashed = [dict(r) for r in good]
    crashed[0] = _rec(sp.HOLDOUT_SEEDS[0], float("nan"),
                      failure="RuntimeError: boom")
    assert sp.acceptance(sp.summarize(crashed))["accepted"] is False


def test_summarize_reports_failure_rate_distributions():
    recs = ([_rec(s, 2.0, {"clustering": 0.5, "ad_ctr": 1.0})
             for s in sp.HOLDOUT_SEEDS[:12]]
            + [_rec(s, 4.5, {"clustering": 4.5, "ad_ctr": 1.0})
               for s in sp.HOLDOUT_SEEDS[12:]])
    s = sp.summarize(recs)
    assert s["n_seeds"] == 20 and s["n_pass"] == 12
    assert s["pass_proportion"] == pytest.approx(0.6)
    assert s["median_implausibility"] == pytest.approx(2.0)
    assert s["max_implausibility"] == pytest.approx(4.5)
    assert s["p95"] >= s["p75"] >= s["p25"] >= s["p5"]
    assert s["dominant_failing_metric_frequency"] == {"clustering": 8}
    assert s["component_failure_rates"]["clustering"] == pytest.approx(0.4)
    assert s["component_failure_rates"]["ad_ctr"] == 0.0
    lo, hi = s["pass_ci_wilson95"]
    assert lo < 0.6 < hi
    blo, bhi = s["pass_ci_bootstrap95"]
    assert blo < 0.6 < bhi
    # The Monte Carlo interval is deterministic from its own seed.
    assert s["pass_ci_bootstrap95"] == sp.summarize(recs)["pass_ci_bootstrap95"]


def test_committed_artifact_exists_is_consistent_and_couples_the_label():
    """Honesty coupling: the shipped artifact must exist, cover the locked
    lists against the current targets, and the profile label must be derived
    from ITS verdict -- a failed holdout can never present as 'matched'."""
    results = sp.load_results()
    assert results is not None, (
        "socio_sim/data/seed_protocol_results_v1.json missing -- run "
        "scripts/seed_protocol_eval.py")
    assert results["holdout_seeds_sha256"] == HOLDOUT_SEEDS_SHA256
    assert results["targets_values_sha256"] == TARGETS_VALUES_SHA256
    assert results["seed_lists"]["holdout"] == list(sp.HOLDOUT_SEEDS)
    assert results["attestation_no_holdout_tuning"]
    for group in ("fitting", "validation", "holdout"):
        assert len(results["records"][group]) == 20
    # every holdout run was replay-verified and free of runtime failures
    holdout = results["records"]["holdout"]
    assert all(r["replay_checked"] and r["replay_ok"] for r in holdout)
    assert all(r["runtime_failure"] is None for r in holdout)
    # label honesty: derived from the verdict, never asserted
    accepted = results["acceptance"]["accepted"]
    label = sp.profile_label(results)
    if accepted:
        assert label == sp.PROFILE_LABEL_VALIDATED
    else:
        assert label == sp.PROFILE_LABEL_DEMONSTRATION
        assert "demonstration" in results["profile_label"]
    # the artifact's summaries must be reproducible from its own records
    resummary = sp.summarize(holdout)
    stored = results["summaries"]["holdout"]
    assert stored["n_pass"] == resummary["n_pass"]
    assert stored["median_implausibility"] == pytest.approx(
        resummary["median_implausibility"])
    assert sp.acceptance(resummary)["accepted"] == accepted


def test_no_artifact_means_not_validated():
    assert sp.profile_label({}) == sp.PROFILE_LABEL_DEMONSTRATION
    assert sp.profile_label(None) is not None  # falls back to committed file


@pytest.mark.slow
def test_live_multiseed_runs_match_the_committed_artifact_and_replay():
    """LIVE multi-seed check (not just seed 42): two protocol seeds are
    re-simulated with replay verification and must reproduce the committed
    artifact's per-seed implausibility exactly (determinism across time,
    not just within a session). Marked slow: ~2 min."""
    results = sp.load_results()
    assert results is not None
    by_seed = {r["seed"]: r for group in results["records"].values()
               for r in group}
    for seed in (sp.VALIDATION_SEEDS[0], sp.HOLDOUT_SEEDS[0]):
        live = sp.evaluate_seed(seed, verify_replay=True)
        assert live["replay_checked"] and live["replay_ok"], seed
        assert live["runtime_failure"] is None
        committed = by_seed[seed]
        assert live["implausibility"] == pytest.approx(
            committed["implausibility"], abs=1e-9), seed
        for metric, z in live["components"].items():
            assert z == pytest.approx(committed["components"][metric],
                                      abs=1e-9), (seed, metric)


def test_wilson_and_bootstrap_edge_cases():
    assert np.isnan(sp._wilson_interval(0, 0)[0])
    assert sp._wilson_interval(20, 20)[1] == 1.0
    assert np.isnan(sp._bootstrap_pass_ci([])[0])
