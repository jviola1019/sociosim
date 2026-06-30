from socio_sim.evidence import evidence_registry, scenario_assumptions, validate_registry


def test_evidence_registry_is_complete_and_valid():
    assert not validate_registry()
    records = evidence_registry()
    for required in (
        "ev.scenario_assumption.default_parameters",
        "ev.synthetic_engineering.classifier_noise",
        "ev.synthetic_engineering.classifier_template",
        "ev.synthetic_engineering.assets_v4",
    ):
        assert required in records


def test_scenario_assumptions_are_machine_readable():
    assumptions = scenario_assumptions()
    assert "assumption.behavior_defaults" in assumptions
    assert all(a["evidence_id"] == "ev.scenario_assumption.default_parameters"
               for a in assumptions.values())
