"""Every scenario preset must build a valid config, run, and apply its fields
accurately (no dead/typo'd preset keys, no invalid adversaries)."""

import pytest

from socio_sim.analytics.lens import SETTING_LENS, run_lens
from socio_sim.analytics.metrics import summarize_run
from socio_sim.analytics.report import render
from socio_sim.config import ADVERSARIES
from socio_sim.engine import Simulation
from socio_sim.presets import PRESETS
from socio_sim.web.app import _build_config


@pytest.mark.parametrize("name", list(PRESETS))
def test_preset_builds_runs_and_applies_fields(name):
    p = PRESETS[name]
    body = {"profile": "test", "n_agents": 80, "n_ticks": 24, **p["fields"]}
    cfg = _build_config(body)            # raises if any field is invalid
    result = Simulation(cfg).run()
    assert result.log.events
    summary = summarize_run(result)
    report = render(summary, result.manifest)
    lens = run_lens(cfg.to_dict(), summary)
    assert "Research use only" in report
    assert "95%" in report
    assert summary["harmful_exposure"]["ci"]
    assert summary["moderation"]["precision_ci"]
    assert summary["appeals"]["granted_rate_ci"]
    assert lens["government_output"]
    if cfg.ads_enabled:
        assert lens["marketing_output"]
        for metric in summary["ads"].values():
            assert "lift_ci" in metric and len(metric["lift_ci"]) == 2
            assert "lift_pvalue" in metric
            assert "mde" in metric
            assert isinstance(metric["lift_significant"], bool)
    f = p["fields"]
    if "jurisdictions" in f:
        assert tuple(cfg.jurisdictions) == tuple(f["jurisdictions"])
    if "red_team" in f:
        assert all(a in ADVERSARIES for a in f["red_team"])     # no typo'd adversary
        assert tuple(cfg.red_team) == tuple(f["red_team"])
    if "rate_misinfo" in f:
        assert cfg.category_base_rates["misinfo"] == f["rate_misinfo"]
    if "holdout_fraction" in f:
        assert cfg.holdout_fraction == f["holdout_fraction"]
    if "classifier_precision" in f:
        assert cfg.classifier_targets["hate"]["precision"] == f["classifier_precision"]


def test_every_preset_has_label_and_description():
    for name, p in PRESETS.items():
        assert p.get("label") and p.get("desc"), name
        assert isinstance(p.get("fields"), dict), name
        if name != "custom":
            assert p.get("sources"), name


def test_every_preset_field_has_lens_and_frontend_mapping():
    frontend_special = {"jurisdictions", "red_team"}
    for name, p in PRESETS.items():
        for key in p["fields"]:
            assert key in SETTING_LENS, f"{name}.{key} has no lens tag"
            assert key in frontend_special or key.startswith("rate_") or key in SETTING_LENS
