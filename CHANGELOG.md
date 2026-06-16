# Changelog

All notable changes to SocioSim. Format: Keep a Changelog. Branch: `feat/audit-p0-p1`.

## [Unreleased] — audit P0/P1 remediation

### Added
- `graph.metrics.summary` now reports `degree_tail_exponent` (Hill estimator);
  `validation.targets.compute_observed` surfaces it so the published target is
  actually compared in implausibility (was silently dropped). (P1b)
- `analytics.metrics.wilson_interval` — analytic 95% interval for proportions;
  applied to moderation precision/recall and appeal-grant rate. (P1c)
- Run report now has an **Uncertainty provenance** section stating that
  single-run intervals are within-run / analytic, NOT Monte Carlo. (P1c)
- `web.app.safe_static_path` contains `/static/` requests within STATIC_DIR. (P5a)
- Tooling/docs: `AUDIT_LOG.md` (issue ledger), `HANDOFF.md` (resume state),
  `tests/test_determinism_regression.py` (locked EU/US/CN stream-hash guard).

### Fixed
- **Security:** directory traversal in the web static file handler. (P5a)
- **Docs:** corrected overclaims — "Monte Carlo replication is built in" and
  "every aggregate has a 95% CI" now accurately describe single-run vs
  multi-replicate provenance; `content_mode` doc lists all four backends. (P1c, Q-DOC)

### Determinism
- All changes so far are outside the event stream; the three locked
  baseline stream hashes are unchanged and the full suite is green.

### Pending (see HANDOFF.md / AUDIT_LOG.md)
- P1d BehaviorParams extraction · P1e Monte Carlo modes · P2 organic-baseline
  incrementality · P3 policy-as-code citations + transparency exporter ·
  P4 calibration + sensitivity · P5b perf/SBM/follow-unfollow/LLM accounting ·
  P6 multi-route studio + force-graph + a11y.
