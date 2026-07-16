# Aggregate-Fit Diagnostic Note

(Renamed from `CALIBRATION_REPORT.md`: the filename itself implied a
calibration artifact that does not exist.)

This file supersedes the former aggregate-matching note. The "calibrated
profile" name is no longer used -- it was not a calibration claim, and the
profile is now called `aggregate_matched_prototype`.

## Current Status

- Legacy benchmark targets are incomplete evidence manifests; the default
  `sourced_aggregates_v1` set carries per-target source-artifact hashes.
- Aggregate matching is reported only as an aggregate-fit diagnostic.
- Passing an implausibility threshold is not validation, not calibration
  evidence, and not a real-platform prediction.
- **Multi-seed status (2026-07-16):** the profile's below-cutoff score was
  established on its fitting seed (42). Under the locked seed-generalization
  protocol (20 fitting seeds / 20 validation seeds / 20 holdout seeds,
  `scripts/seed_protocol_eval.py`, artifact
  `socio_sim/data/seed_protocol_results_v1.json`) the holdout pass rate is
  60% — below the 80% acceptance bar — so the profile's honest label is
  **seed-42 aggregate demonstration profile**, and no "matched" badge is
  shown for it in the UI. See docs/AGGREGATE_FIT_FINDINGS.md for the full
  distributions.

## Current Commands

- `python run.py --validate --profile test --sens-samples 8`
  writes `VALIDATION_REPORT.md`.
- `python run.py --backtest` writes `BACKTEST_REPORT.md`.

Both reports now use validation-ladder language and fail closed on incomplete
target metadata.
