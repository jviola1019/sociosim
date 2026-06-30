# SocioSim Usage

SocioSim runs synthetic scenarios under explicit assumptions. Outputs are not
estimates of real-world performance.

## Run

```bash
python run.py
python run.py --web
python run.py --profile aggregate_matched_prototype
python run.py --classifier synthetic_template_classifier
python run.py --measure-classifier
```

Classifier modes are synthetic mechanics modes:

- `synthetic_noise_classifier`
- `synthetic_template_classifier`

## Evidence

Machine-readable evidence records live in:

- `socio_sim/data/evidence_registry.json`
- `socio_sim/data/scenario_assumptions.json`

Every metric exported by the web/API/report payload carries provenance metadata
with valid and invalid uses.

## Assets

The dashboard uses registered v4 assets under
`socio_sim/web/static/assets/v4/`. They are synthetic decorative artwork, not
visual evidence.

Run:

```bash
python scripts/asset_qa.py
```

## Verification

Use:

```bash
python -m ruff check socio_sim tests run.py
python -m pytest -q --cov=socio_sim --cov-report=term-missing --cov-fail-under=85
python scripts/evidence_gate.py
python scripts/claim_scan.py
python scripts/secret_scan.py
python scripts/asset_qa.py
```
