# Scenario Authoring

Scenarios live in `examples/scenarios/` as YAML. They are executable research
fixtures, not forecasts or recommendations.

Required fields:

- `scenario_id`, `version`, `lab_mode`
- `purpose`, `intended_use`, `prohibited_use`
- `primary_question`, `primary_metric`, `secondary_metrics`
- `assumptions`, `provenance`, `research_only_notice`
- `config`, which must build a valid `RunConfig`

Market scenarios also require `synthetic_money_notice`:

`Synthetic scenario input/output. Not a forecast of real financial performance.`

Run:

```bash
python -m socio_sim.experiments.scenario_lint examples/scenarios
```

The linter validates required metadata, claim language, provenance class, market
money caveats, and the executable `RunConfig` block.
