from pathlib import Path

from socio_sim.experiments.scenario_lint import lint_paths, lint_scenario


def test_required_example_scenarios_lint_clean():
    errors = lint_paths([Path("examples/scenarios")])
    assert errors == []


def test_scenario_linter_rejects_missing_provenance_and_bad_notice():
    data = {
        "scenario_id": "bad",
        "version": "1",
        "lab_mode": "society_policy",
        "purpose": "x",
        "intended_use": ["x"],
        "prohibited_use": ["x"],
        "primary_question": "x",
        "primary_metric": "harmful_exposure_rate",
        "secondary_metrics": ["welfare_mean"],
        "assumptions": ["x"],
        "research_only_notice": "Synthetic only.",
        "config": {"profile": "test"},
    }
    errors = lint_scenario(data)
    assert any("missing required fields" in e for e in errors)
    assert any("research_only_notice" in e for e in errors)


def test_market_scenario_requires_synthetic_money_notice():
    data = {
        "scenario_id": "bad_market",
        "version": "1",
        "lab_mode": "entrepreneur_market",
        "purpose": "x",
        "intended_use": ["x"],
        "prohibited_use": ["x"],
        "primary_question": "x",
        "primary_metric": "ad_lift_itt",
        "secondary_metrics": ["ad_ctr"],
        "assumptions": ["x"],
        "provenance": "synthetic_assumption",
        "research_only_notice": "Synthetic scenario estimates only; not a real-world forecast.",
        "config": {"profile": "test"},
    }
    errors = lint_scenario(data)
    assert any("synthetic_money_notice" in e for e in errors)


def test_scenario_linter_rejects_unsupported_causal_claim():
    data = {
        "scenario_id": "bad_claim",
        "version": "1",
        "lab_mode": "society_policy",
        "purpose": "This policy will reduce misinformation.",
        "intended_use": ["x"],
        "prohibited_use": ["x"],
        "primary_question": "x",
        "primary_metric": "harmful_exposure_rate",
        "secondary_metrics": ["welfare_mean"],
        "assumptions": ["x"],
        "provenance": "synthetic_assumption",
        "research_only_notice": "Synthetic scenario estimates only; not a real-world forecast.",
        "config": {"profile": "test"},
    }
    errors = lint_scenario(data)
    assert any("unsupported claim" in e for e in errors)
