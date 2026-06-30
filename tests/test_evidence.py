import json

from socio_sim.evidence import (ASSUMPTION_REQUIRED_FIELDS, evidence_registry,
                                missing_numeric_default_provenance,
                                scenario_assumptions, validate_registry)


def test_evidence_registry_is_complete_and_valid():
    assert not validate_registry()
    records = evidence_registry()
    for required in (
        "ev.scenario_assumption.default_parameters",
        "ev.synthetic_engineering.classifier_noise",
        "ev.synthetic_engineering.classifier_template",
        "ev.synthetic_engineering.assets_v4",
        "ev.unsupported.aggregate_targets_legacy",
    ):
        assert required in records


def test_scenario_assumptions_are_individually_mapped_not_broad_category():
    """Each entry maps ONE decision-facing numeric default by its own `path`,
    not a whole module/class standing in for many unrelated defaults."""
    assumptions = scenario_assumptions()
    assert len(assumptions) >= 60
    assert "assumption.behavior.p_post_given_active" in assumptions
    assert "assumption.behavior.p_share_given_engaged" in assumptions
    # Each behavioral field gets its OWN entry/path, not one shared umbrella.
    beh_paths = {a["path"] for a in assumptions.values()
                 if a["path"].startswith("socio_sim.behavior.BehaviorParams.")}
    assert len(beh_paths) == 13
    paths = [a["path"] for a in assumptions.values()]
    assert len(paths) == len(set(paths)), "every entry must own a unique path"
    for a in assumptions.values():
        for field in ASSUMPTION_REQUIRED_FIELDS:
            assert a.get(field) not in (None, ""), f"{a['id']} missing {field}"


def test_no_numeric_default_lacks_provenance():
    """Regression for AUDIT_LOG.md R6: every mechanically-introspectable
    decision-facing numeric default (BehaviorParams, category_base_rates,
    classifier_targets, Campaign) must have a matching scenario_assumptions
    entry. This is the CI gate required by the task brief item 6 ('numerical
    defaults without a provenance ID')."""
    assert missing_numeric_default_provenance() == set()


def test_coverage_gate_catches_a_removed_provenance_entry(monkeypatch):
    """Prove the gate actually fails closed, not just passes by construction:
    delete one real entry and confirm both the coverage check and
    validate_registry() report it."""
    import socio_sim.evidence as ev
    from importlib import resources
    real_text = resources.files("socio_sim").joinpath(
        "data", "scenario_assumptions.json").read_text(encoding="utf-8")
    data = json.loads(real_text)
    data["assumptions"] = [a for a in data["assumptions"]
                           if a["id"] != "assumption.behavior.p_post_given_active"]

    def fake_resource_json(name):
        if name == "scenario_assumptions.json":
            return data
        return json.loads(resources.files("socio_sim").joinpath(
            "data", name).read_text(encoding="utf-8"))

    monkeypatch.setattr(ev, "_resource_json", fake_resource_json)
    ev.scenario_assumptions.cache_clear()
    try:
        missing = ev.missing_numeric_default_provenance()
        assert "socio_sim.behavior.BehaviorParams.p_post_given_active" in missing
        errors = ev.validate_registry()
        assert any("p_post_given_active" in e for e in errors)
    finally:
        ev.scenario_assumptions.cache_clear()
