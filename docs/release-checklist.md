# Release Checklist

Before release:

1. Confirm worktree scope and no unrelated user edits were reverted.
2. Run `python scripts/verify_release.py`.
3. Read `docs/audits/latest-release-verification.md`.
4. Resolve any failed check or document why release is blocked.
5. Confirm scenario lint, ruff, coverage, determinism/replay, policy compare,
   market holdout, validation/backtest smoke, security/config tests, and UI
   smoke status.
6. Confirm Docker/security scans are either passed or explicitly skipped due to
   unavailable tools.
7. Confirm README and docs do not overclaim real-world prediction, ROI, legal
   compliance, or validation strength.
8. Confirm monetary outputs show the synthetic-money notice.
