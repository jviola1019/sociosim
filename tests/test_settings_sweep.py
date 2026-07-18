"""CI-fast regression of the settings-sweep coherence properties.

The full 76-case sweep is `python scripts/settings_sweep.py` (writes
docs/SETTINGS_SWEEP.md); this holds its invariants on a small subset plus
the two defects the first full sweep found:

- a FLOAT exploration_pool_size crashed numpy inside the engine (validate()
  accepts any non-negative number for that field);
- one campaign's undefined (n/a) lift NaN-poisoned the exposure-weighted
  ITT mean even when other campaigns measured fine.
"""

import importlib.util
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "settings_sweep",
    Path(__file__).resolve().parents[1] / "scripts" / "settings_sweep.py")
sweep = importlib.util.module_from_spec(_spec)
sys.modules["settings_sweep"] = sweep
_spec.loader.exec_module(sweep)


def test_subset_of_setting_cases_stays_coherent():
    cases = [
        ("baseline", {}),
        ("ads_enabled=False", {"ads_enabled": False}),
        ("base_rates=zero_harmful", dict(sweep._grid())["base_rates=zero_harmful"]),
        ("base_rates=3x_harmful", dict(sweep._grid())["base_rates=3x_harmful"]),
        ("graph=cm", {"graph_kind": "cm",
                      "graph_params": {"gamma": 2.3, "min_degree": 2,
                                       "triangle_swaps": 8.0}}),
    ]
    results = {name: sweep.run_case((name, ov)) for name, ov in cases}
    for name, r in results.items():
        assert r["ok"], (name, r["problems"])
    # directional subset under common random numbers
    assert results["ads_enabled=False"]["metrics"]["ad_impressions"] == 0
    assert results["base_rates=zero_harmful"]["metrics"][
        "harmful_exposure_rate"] == 0
    assert (results["base_rates=3x_harmful"]["metrics"]["harmful_exposure_rate"]
            >= results["baseline"]["metrics"]["harmful_exposure_rate"])


def test_float_exploration_pool_size_no_longer_crashes_the_engine():
    from socio_sim.behavior import BehaviorParams
    r = sweep.run_case(("float_pool",
                        {"behavior": BehaviorParams(exploration_pool_size=20.0)}))
    assert r["ok"], r["problems"]


def test_undefined_campaign_lift_does_not_poison_the_itt_mean():
    """_headline_metrics must exclude undefined-lift strata, and report NaN
    (honest n/a) only when NO campaign has a defined lift with exposure."""
    from socio_sim.pipeline import _headline_metrics

    class _FakeResult:
        pass

    def fake_summary(_):
        return {
            "harmful_exposure": {"rate": 0.0},
            "moderation": {"precision": 1.0, "recall": 1.0},
            "appeals": {"granted_rate": 0.0},
            "welfare": {"mean": 0.0},
            "n_posts": 10,
            "ads": {
                "a": {"impressions": 100, "clicks": 1, "conversions": 0,
                      "spend": 1.0, "revenue": 0.0, "n_exposed": 50,
                      "lift": 0.02, "disclosure_present": True},
                "b": {"impressions": 100, "clicks": 0, "conversions": 0,
                      "spend": 1.0, "revenue": 0.0, "n_exposed": 50,
                      "lift": float("nan"), "disclosure_present": True},
            },
        }

    import socio_sim.pipeline as pl
    orig = pl.summarize_run
    pl.summarize_run = fake_summary
    try:
        m = _headline_metrics(_FakeResult())
    finally:
        pl.summarize_run = orig
    assert m["ad_lift_itt"] == 0.02        # defined stratum only, not NaN
    # ...and all-undefined -> NaN (n/a), never a fabricated 0
    def all_nan(_):
        s = fake_summary(_)
        s["ads"]["a"]["lift"] = float("nan")
        return s
    pl.summarize_run = all_nan
    try:
        m = _headline_metrics(_FakeResult())
    finally:
        pl.summarize_run = orig
    assert m["ad_lift_itt"] != m["ad_lift_itt"]


def test_sweep_grid_covers_every_behavior_field_and_all_graph_kinds():
    from dataclasses import fields as dc_fields

    from socio_sim.behavior import BehaviorParams
    names = [n for n, _ in sweep._grid()]
    for f in dc_fields(BehaviorParams):
        assert any(n.startswith(f"behavior.{f.name}=") for n in names), f.name
    for g in ("plc", "ws", "cm", "sbm"):
        assert f"graph={g}" in names
