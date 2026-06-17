# Changelog

All notable changes to SocioSim. Format: Keep a Changelog. Branch: `feat/audit-p0-p1`.

## [Unreleased] — audit P0/P1 remediation

### Added
- **P4 validation study (closes Q-PARAM sweep):** `validation/study.py` runs a
  first-order (Sobol-style) sensitivity sweep of headline outputs over
  BehaviorParams (LHS) and a calibration/implausibility check vs the published
  targets, rendered to `VALIDATION_REPORT.md` via `run.py --validate`. The
  generated report honestly flags out-of-tolerance targets (degree-tail,
  diurnal peak) even at I<3. Adds `KNOWN_LIMITATIONS.md`, `SOURCE_LEDGER.md`.
- **P1d BehaviorParams (Q-PARAM extract):** the engine's ~12 hardcoded
  behaviour constants (posting/share/flag probabilities, fatigue, recency
  window, exploration pool, engagement base, red-team intensities) are now a
  cited, frozen `socio_sim/behavior.py::BehaviorParams` on `RunConfig.behavior`,
  serialized in the manifest and reproduced on replay. Defaults are byte-for-
  byte behaviour-preserving (determinism guard unchanged). Sensitivity sweep
  over them lands in P4.
- **P3 policy-as-code hardening (closes Q-PACK):** every rule now carries
  `source_citation` (required) plus `legal_uncertainty`, `user_rights`,
  `transparency_category`, `human_review_required`; packs cite DSA Arts
  16/17/20/26/28/34-35, §230(c)(1)/(c)(2)/(e), CN 2025 AI-label Measures +
  Deep Synthesis Provisions, 16 CFR Part 255. EU "24h" reframed via
  `legal_uncertainty` as a modeling assumption (DSA requires "timely", not 24h).
  New `policy/transparency.py` + `Analysis.transparency`; CLI prints it, web
  returns it and exports `?fmt=transparency`. Pack versions bumped to 1.1.
- **P1e Monte Carlo modes (closes Q-MC P0):** `run_and_analyze(cfg, n_replicates=N)`.
  `N=1` = Preview (single run, within-run/analytic intervals only); `N>1` =
  Research run, attaching an `mc` bundle of Monte Carlo percentile intervals
  (provenance `mc-replicated`) for headline metrics via `run_replicates`.
  CLI `--replicates N`; web accepts `n_replicates` and returns `mc`/`mode`.
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

### Status
- **Both P0s closed:** Q-LIFT (P2) and Q-MC (P1e). Q-HILL, Q-CI, Q-TRAV, Q-DOC done.

### Pending (see HANDOFF.md / AUDIT_LOG.md)
- P5b perf/SBM/follow-unfollow/LLM accounting · P6 multi-route studio +
  force-graph + a11y. (All P0s + the quant/policy P1s are closed.)
