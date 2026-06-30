# Baseline Audit Snapshot

This snapshot records the starting point for branch
`fix/evidence-first-v4-assets`, created from clean `main` at
`59632c4d5336bfc2920214d84df83b328c529478`.

## Environment

- Python: `3.11.9`
- Initial collected tests: `270`
- Final collected tests after remediation: `277`
- Resolved dependency/license inventory: `out/license_inventory.json`
  (`94` packages after security updates)

## Baseline Commands Observed Before Remediation

| Check | Result |
|---|---|
| `ruff check socio_sim tests run.py` | PASS |
| `pytest --collect-only -q` | 270 tests collected |
| full pytest with coverage | PASS, total coverage about 93.05% |
| Playwright E2E | PASS |
| `python run.py --measure-classifier` | completed and wrote legacy `BENCHMARK_REPORT.md` |
| `python run.py --backtest` | completed and wrote legacy `BACKTEST_REPORT.md` |
| `python run.py --validate` | timed out/interrupted during baseline run |
| `python -m build --wheel` | failed locally because the repo `build/` directory shadowed the `build` module / module was not installed |

## Baseline V3 Asset Inventory

The tracked v3 asset set contained 26 PNGs:

- `socio_sim/web/static/assets/feed-atlas-v3.png`
- `socio_sim/web/static/assets/ad-atlas-v3.png`
- `socio_sim/web/static/assets/feed-cover-v3-00.png` through `feed-cover-v3-11.png`
- `socio_sim/web/static/assets/ad-creative-v3-00.png` through `ad-creative-v3-11.png`

Those files are deleted by the remediation and replaced by the v4 registry.

## Baseline Claim Posture

The starting code and reports used public-facing language around calibrated
profiles, CUPED-style output, confidence intervals, trained classifier mode, and
v3 production-style assets. This remediation treats those as claim downgrades:
missing evidence metadata becomes `scenario_assumption`,
`synthetic_engineering`, or `unsupported`.
