# Aggregate-Fit Diagnostic Note

This file supersedes the former aggregate-matching note. The "calibrated
profile" name is no longer used -- it was not a calibration claim, and the
profile is now called `aggregate_matched_prototype`.

## Current Status

- Legacy benchmark targets are incomplete evidence manifests.
- Aggregate matching is reported only as an aggregate-fit diagnostic.
- Passing an implausibility threshold is not validation, not calibration
  evidence, and not a real-platform prediction.

## Current Commands

- `python run.py --validate --profile test --sens-samples 8`
  writes `VALIDATION_REPORT.md`.
- `python run.py --backtest` writes `BACKTEST_REPORT.md`.

Both reports now use validation-ladder language and fail closed on incomplete
target metadata.
