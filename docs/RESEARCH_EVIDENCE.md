# Research Evidence Ledger

This file is a pointer ledger, not a source of validation claims. Machine-readable
records in `socio_sim/data/evidence_registry.json` control what a metric or
report may claim.

## Current Evidence Status

- Built-in behavior, persona, ad, policy, profile, and content-rate defaults are
  scenario assumptions.
- Runtime classifier modes are synthetic engineering mechanics.
- Bundled text benchmark samples support component benchmark diagnostics only.
- Legacy aggregate targets have incomplete source metadata and cannot support
  validation, calibration, backtest, or operational-use claims.

## Advertising Methods

The simulator contains a randomized holdout mechanic and analytic diagnostic
calculations. Because the adjustment uses latent simulated conversion propensity,
the output is labeled
`oracle_covariate_adjusted_simulation_diagnostic`, not a real experiment CUPED
analysis.

## Security and Accessibility References

Security posture is documented in `SECURITY.md`. CI runs lint, tests, evidence
gates, claim scanning, secret scanning, asset QA, dependency audit, and static
security scanning where tools are available.
