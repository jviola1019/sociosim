# Changelog

All notable changes to SocioSim. Format: Keep a Changelog. Branch: `feat/audit-p0-p1`.

## [Unreleased] — audit P0/P1 remediation

### Added
- **P2 incrementality:** organic (non-ad) conversion channel. Agents carry a
  latent `base_conversion` propensity (Personas); a daily `simulate_baseline`
  pass (dedicated `"conversion"` RNG stream) emits `organic_conversion` events
  for every agent, so holdout agents have a measurable baseline rate. New
  `socio_sim/stats.py` (Wilson, Newcombe difference CI, Beta `P(lift>0)`).
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
- **P2 (P0):** the incremental-lift / holdout metric was a tautology — holdout
  agents never converted, so `lift == exposed conversion rate`. Now
  `lift = exposed_rate - holdout_rate` over the targeted population, with a
  Newcombe difference CI and `prob_lift_positive`. Tests prove lift~0 under a
  null ad effect (CI brackets 0) and lift>0 only when the ad adds conversions.
- **Security:** directory traversal in the web static file handler. (P5a)
- **Docs:** corrected overclaims — "Monte Carlo replication is built in" and
  "every aggregate has a 95% CI" now accurately describe single-run vs
  multi-replicate provenance; `content_mode` doc lists all four backends. (P1c, Q-DOC)

### Determinism
- P1b/P1c/P5a were outside the event stream (hashes unchanged). P2 intentionally
  appends `organic_conversion` events, so the three locked baseline stream
  hashes were regenerated in the same commit (pre-P2 values in git history).
  Replay + same-seed determinism tests still pass.

### Pending (see HANDOFF.md / AUDIT_LOG.md)
- P1d BehaviorParams extraction · P1e Monte Carlo modes · P3 policy-as-code
  citations + transparency exporter · P4 calibration + sensitivity ·
  P5b perf/SBM/follow-unfollow/LLM accounting · P6 multi-route studio +
  force-graph + a11y.
