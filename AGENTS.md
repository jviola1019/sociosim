# SocioSim Repository Instructions

## Project Purpose

SocioSim is a reproducible synthetic social-network scenario laboratory. It is
for comparing modeled outcomes under explicit assumptions, not for predicting
or optimizing real-world behavior.

## Prohibited Uses

- No targeting, ranking, surveillance, or enforcement decisions about real people.
- No prediction of elections, protests, companies, platforms, or public events.
- No optimization of political persuasion, harassment, evasion, or censorship.
- No ingestion of PII or private individual-level platform data.
- No real campaign ROI or legal-compliance claims.

## Required Local Gates

Run these before shipping behavior changes:

```bash
python -m ruff check .
python -m pytest -q --cov=socio_sim --cov-report=term-missing --cov-fail-under=85
python -m socio_sim.experiments.scenario_lint examples/scenarios
python scripts/verify_release.py --quick
```

Use `python scripts/verify_release.py` for release verification; it includes
slower validation/backtest smoke checks and writes a report under `docs/audits/`.

## Documentation Standards

- Every user-visible claim must identify whether it is `model_derived`,
  `calibration_consistent`, `aggregate_backtested`, `component_measured`,
  `synthetic_assumption`, or `unsupported`.
- Never state that a scenario predicts real-world outcomes.
- Monetary campaign outputs must say: "Synthetic scenario input/output. Not a
  forecast of real financial performance."
- Policy packs must be described as research approximations, not legal advice.

## Source and Citation Requirements

- Add source IDs to `SOURCE_LEDGER.md` or the relevant docs before using a named
  external aggregate, benchmark, policy source, or method as evidence.
- Calibration and backtest reports must name the target set and generated
  artifact. Do not claim validation without an artifact.

## Safety Gates

- Scenario YAML must pass `python -m socio_sim.experiments.scenario_lint`.
- LLM, media, and generated content are presentation layers only; they must not
  mutate executable scenario state.
- Web APIs must reject oversized jobs and cross-origin state-changing requests.

## How to Add a Scenario

1. Add a YAML file under `examples/scenarios/`.
2. Include the required metadata fields documented in `docs/scenario-authoring.md`.
3. Keep the `config` block executable as a `RunConfig`.
4. Run the scenario linter and add tests for new schema behavior.

## How to Add a Metric

1. Define the formula, unit, interpretation, limitations, provenance class, and
   required event-log fields in `docs/metric-catalog.md`.
2. Add tests for the formula and any report/export rendering.
3. Ensure missing provenance fails validation if the metric is user-visible.

## How to Modify a Policy Pack

1. Keep `source_citation`, `legal_uncertainty`, `user_rights`,
   `transparency_category`, and `human_review_required` current.
2. Add or update tests in `tests/test_policy.py` and `tests/test_transparency.py`.
3. Avoid statutory certainty language unless the source ledger supports it.

## Commit Expectations

Use focused commits. Do not revert unrelated user work. Generated audit reports
may be committed only when they are part of a release or verification record.
