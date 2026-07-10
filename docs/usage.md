# SocioSim Usage

SocioSim runs synthetic scenarios under explicit assumptions. Outputs are not
estimates of real-world performance.

## Run

```bash
python run.py
python run.py --web
python run.py --llm                     # bootstrap a free local Ollama model
python run.py --profile aggregate_matched_prototype
python run.py --classifier synthetic_template_classifier
python run.py --measure-classifier
```

### CLI flag reference (all 23 flags)

Authoritative source: `python run.py -h`.

| Flag | Meaning |
|------|---------|
| `--web` | Launch the local web console instead of a CLI run |
| `--port` | Web console port (default 8765) |
| `--bind` | Web bind address; non-loopback requires `SOCIOSIM_ACCESS_TOKEN` + `SOCIOSIM_ALLOWED_HOSTS` and sends the token over cleartext HTTP (see SECURITY.md) |
| `--no-open` | Do not auto-open the browser with `--web` |
| `--llm` | Bootstrap a free local Ollama server + model for content generation |
| `--profile` | Scale preset: `quick`, `test`, `standard`, `aggregate_matched_prototype` |
| `--jurisdictions` | Policy packs to apply (US, EU, CN) |
| `--benchmark` | Aggregate-target set name |
| `--classifier` | `synthetic_noise_classifier` or `synthetic_template_classifier` |
| `--dynamic-graph` | Enable follow/unfollow/churn dynamics |
| `--model` | LLM model name for `--llm` |
| `--host` | LLM server host |
| `--agents` / `--ticks` | Override profile scale |
| `--seed` | Root seed (same config+seed => identical event stream) |
| `--replicates` | Monte Carlo replicates (Research mode when > 1) |
| `--workers` | Parallel workers for replicates |
| `--validate` | Sensitivity + aggregate-fit diagnostics -> `VALIDATION_REPORT.md`, then exit |
| `--backtest` | Held-out aggregate-fit diagnostics -> `BACKTEST_REPORT.md`, then exit |
| `--measure-classifier` | Classifier-component benchmark (license/source: `docs/DATA_MANIFEST.md`) -> `BENCHMARK_REPORT.md`, then exit |
| `--sens-samples` | LHS samples for `--validate` |
| `--media` | Synthesize N deterministic PNG images (+1 APNG) |
| `--out` | Output directory |

Classifier modes are synthetic mechanics modes:

- `synthetic_noise_classifier`
- `synthetic_template_classifier`

Notes on output honesty gates shared by the CLI and web UI:

- Observed-vs-target comparison tables are suppressed on both surfaces while
  the bundled targets' evidence records are `unsupported`
  (`socio_sim.evidence.targets_metadata_complete`).
- Replicate intervals are labeled "95%" only at 20+ replicates; below that
  the CLI prints "percentile range over N=<n> replicates".
- A web run with ads enabled requires `holdout_fraction > 0` (rejected with
  a 400 otherwise): lift/p-value output needs a control group.

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
python -m playwright install --with-deps chromium   # once, before the browser runs
python -m pytest -q tests/test_e2e_playwright.py
python -m pytest -q tests/test_a11y_axe.py          # axe-core accessibility gate
```

CI additionally runs `scripts/license_inventory.py`, `bandit`, `pip-audit`,
and a wheel build + packaged-data assertion (see
`.github/workflows/ci.yml`).
