# SocioSim Evidence-First Remediation Report

Branch: `fix/evidence-first-v4-assets`

Base: `59632c4d5336bfc2920214d84df83b328c529478`

## Summary

Implemented the evidence-first remediation as a claim downgrade. Public runtime
classifier modes are now `synthetic_noise_classifier` and
`synthetic_template_classifier`; legacy `noise` / `trained` strings are accepted
only through manifest/config migration paths. Runtime and report surfaces now
label synthetic outputs, metric provenance, validation-ladder limits, ad
measurement timing, and v4 synthetic decorative assets.

## Major Changes

- Added typed evidence infrastructure in `socio_sim/evidence.py`,
  `socio_sim/data/evidence_registry.json`, and
  `socio_sim/data/scenario_assumptions.json`.
- Added metric provenance to summaries, reports, and web payloads.
- Refactored classifier benchmark reporting with source hashes, split
  provenance, normalized duplicate leakage checks, bootstrap intervals,
  reliability data, threshold sweeps, and component-only wording.
- Renamed ad CUPED output to
  `oracle_covariate_adjusted_simulation_diagnostic` and added assignment,
  eligibility, and observation timing fields.
- Added deterministic LLM semantic guard checks for PII-like text, topic/category
  contradictions, unsafe placeholder terms, reason-coded cache records, and
  cache-hash tests.
- Replaced v3 image assets with 92 deterministic v4 PNG assets: 48 feed covers,
  32 ad creatives, 12 editorial/system visuals, plus registry and contact sheet.
- Removed v3 asset references from active code, package contents, and tests.
- Added security/reproducibility gates: pinned Docker base digest, non-root user,
  Bandit, pip-audit, secret scan, license inventory, evidence gate, claim scan,
  asset QA, and wheel content checks.

## Deleted Assets

- `feed-atlas-v3.png`
- `ad-atlas-v3.png`
- `feed-cover-v3-00.png` through `feed-cover-v3-11.png`
- `ad-creative-v3-00.png` through `ad-creative-v3-11.png`

## New Files

- `BASELINE_AUDIT_SNAPSHOT.md`
- `AUDIT_REMEDIATION_REPORT.md`
- `docs/ASSET_QA.md`
- `scripts/asset_qa.py`
- `scripts/claim_scan.py`
- `scripts/evidence_gate.py`
- `scripts/generate_v4_assets.py`
- `scripts/license_inventory.py`
- `scripts/secret_scan.py`
- `socio_sim/evidence.py`
- `socio_sim/content/semantic_guard.py`
- `socio_sim/data/evidence_registry.json`
- `socio_sim/data/scenario_assumptions.json`
- `socio_sim/web/static/assets/v4/*`
- `tests/test_asset_v4.py`
- `tests/test_evidence.py`

## Final Verification

| Check | Result |
|---|---|
| `python -m ruff check socio_sim tests run.py scripts examples` | PASS |
| `python -m pytest -q` | PASS, 277 tests |
| `python -m pytest --cov=socio_sim --cov-report=term-missing --cov-fail-under=80` | PASS, 277 tests, 92.76% coverage |
| `python -m pytest -q tests/test_e2e_playwright.py` | PASS |
| `python run.py --measure-classifier` | PASS |
| `python run.py --validate --profile test --sens-samples 8` | PASS |
| `python run.py --backtest` | PASS |
| `python scripts/asset_qa.py` | PASS, 92 records |
| `python scripts/evidence_gate.py` | PASS |
| `python scripts/claim_scan.py` | PASS |
| `python scripts/secret_scan.py` | PASS |
| `python -m bandit -q -r socio_sim` | PASS |
| `python -m pip_audit` | PASS, no known vulnerabilities found; skipped local/unpublished packages `mlb-show-terminal` and `socio-sim` |
| `python scripts/license_inventory.py` | PASS, wrote 94-package inventory |
| `python -m build --wheel C:\Users\jviol\Downloads\socio_sim` | PASS |
| wheel content inspection | PASS, no v3 paths, 48 feed v4, 32 ad v4, 12 editorial v4, evidence registries present |

## Final Artifact Hashes

| Artifact | SHA-256 |
|---|---|
| `BENCHMARK_REPORT.md` | `357f6a9ffda08c17610621f55a50a465693f1d5b25e17e02d6f55471d0fc93b6` |
| `BACKTEST_REPORT.md` | `9742476b4ae26917b663e5c0a29e9f09006d41938c4c61419431b505f50ef3b1` |
| `VALIDATION_REPORT.md` | `4a242884a8d803ca91f01d59db0050c7bfee9179e4fac6be697569aa7a4bb64a` |
| `socio_sim/data/evidence_registry.json` | `3af882a272d02348b4cf3a8dac8b93437577921f119aca210b2e1bb99eab3579` |
| `socio_sim/data/scenario_assumptions.json` | `f8ff1514c18ea539dd9150a103b6fb1d619941f6c7419eb9721a4f25b0f0f09f` |
| `socio_sim/web/static/assets/v4/registry.json` | `92c795821744a26aeeac8ab64724b5dcc57c724c751851c46ba614178e7bd09e` |
| `dist/socio_sim-0.1.0-py3-none-any.whl` | `7cca1b40a95d3c15b2a1c66609ee4aa8fa95d412b03477bee8c9218eb669b122` |
| `out/license_inventory.json` | `c0a006cd4804604d2fa040694706633e1d7fe1125c5f498b778ccaad10ae231d` |

## Asset QA

- Registry records: 92
- Roles: 48 `feed_cover`, 32 `ad_creative`, 12 `editorial_system`
- Contact sheet: `socio_sim/web/static/assets/v4/contact-sheet-v4.png`
- Human visual review: not claimed
- Metadata/duplicate screening: automated only

## Leakage And Benchmark Results

- Civil Comments component benchmark: F1 `0.731`, ROC-AUC `0.821`, leakage
  check `pass`, source hash recorded.
- Spam Detection component benchmark: F1 `0.989`, ROC-AUC `1.000`, leakage
  check `pass`, source hash recorded.
- These are component diagnostics only and do not validate runtime classifier
  deployment.

## Remaining Evidence Gaps

- Legacy aggregate target manifests still lack complete source version, date
  range, population, unit, source hash, and tolerance-rationale metadata.
- No external temporal holdout, external platform holdout, operational
  validation, or lawful real-deployable runtime classifier artifact is present.
- V4 visual QA is automated; no human-review claim is made.
- `.coverage` is a tracked generated artifact and was modified by the local
  coverage run.

## Operational Limits

SocioSim remains research-use-only synthetic scenario software. Outputs must not
be used to target or rank real individuals, predict real events, make
enforcement decisions, claim real-platform performance, or justify operational
campaign spend.
