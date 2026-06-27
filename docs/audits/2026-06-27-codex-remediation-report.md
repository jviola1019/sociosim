# 2026-06-27 Codex Remediation Report

## Completed Remediation Slice

- Added `AGENTS.md` with repository safety, testing, documentation, and scenario
  authoring instructions.
- Added scenario-as-code linter at `socio_sim/experiments/scenario_lint.py`.
- Added all required scenario files under `examples/scenarios/` and pytest
  coverage in `tests/test_scenario_lint.py`.
- Fixed `examples/policy_stress_demo.py` to import
  `socio_sim.experiments.compare`.
- Changed EU user-flag escalation to condition-only review intake and added a
  low-score regression test.
- Carried `human_review_required` into `PolicyDecision` and moderation logs.
- Centralized campaign constructor validation in `Campaign.__post_init__` with
  direct-constructor regression tests.
- Added web server scale limits and active-job rejection with HTTP 429 coverage.
- Updated `examples/ad_experiment_demo.py` to show lift intervals, raw p-values,
  BH q-values, economics provenance, and synthetic-money caveats.
- Added `scripts/verify_release.py`, which writes
  `docs/audits/latest-release-verification.md`.
- Added scenario lint to GitHub Actions.
- Added independent held-out backtest reruns with replicate intervals.
- Added machine-readable metric provenance to summaries and reports.
- Added deterministic LLM generated-text guards and metadata-rich cache entries.
- Added authenticated full event-log export for saved web runs.

## Remaining P0/P1 Items

No P0 item was found in this pass.

Remaining P1: none known after this continuation.

## Known Remaining P2 Work

- Extend per-metric provenance from headline metrics to every secondary chart
  and UI table.
- Add LLM reclassification and cache-hash replay validation.
- Add dependency/security scan tooling and Docker hardening.
- Add accessibility table alternatives and automated axe checks.
- Refresh `SOURCE_LEDGER.md` so it is authoritative for implemented methods and
  benchmark datasets.

## Verification Plan

Run:

```bash
python -m ruff check .
python -m socio_sim.experiments.scenario_lint examples/scenarios
python -m pytest -q tests/test_policy.py tests/test_campaigns.py tests/test_web.py tests/test_scenario_lint.py
python scripts/verify_release.py --quick
```

Use full `python scripts/verify_release.py` for release candidates when slower
validation/backtest smoke checks are acceptable.
