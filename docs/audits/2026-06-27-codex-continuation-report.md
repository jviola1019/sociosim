# 2026-06-27 Codex Continuation Report

## Remediation Completed After Baseline Commit

- Reworked `validation.backtest.leave_out_backtest()` so held-out metrics are
  scored on independent replicate IDs after parameter selection, with percentile
  intervals in `BACKTEST_REPORT.md`.
- Added machine-readable headline metric provenance to `summarize_run()` and
  rendered it in Markdown reports.
- Hardened optional local LLM generation:
  - prompt adds fictional/no-PII/no-operational-harm boundaries;
  - generated text is rejected before cache/render if it contains PII, unsafe
    operational phrases, or executable snippets;
  - cache entries include backend, model, prompt hash, prompt version,
    provenance, and `state_mutation_allowed: false`;
  - outbound LLM URLs are revalidated immediately before request.
- Added authenticated full event-log export for saved web runs at
  `/api/runs/<id>/events`, with path containment to `out/`.
- Exposed the Event Log export in the web export menu.

## Verification

Focused checks passed:

```bash
python -m ruff check .
python -m pytest -q tests/test_backtest.py tests/test_analytics.py tests/test_llm_adapter.py tests/test_web.py tests/test_security.py tests/test_e2e_playwright.py
python run.py --backtest
```

Backtest smoke result after the independent rerun change:

- `test_pass=True`
- `I_test=0.78`
- stylized facts `5/5`

## Remaining High-Priority Work

- Add LLM reclassification against generated surface text, not only deterministic
  guardrails.
- Extend provenance display from headline report metrics to every secondary UI
  chart and table.
- Add automated accessibility checks and chart/network table alternatives.
- Add dependency/security scanning and Docker hardening.
