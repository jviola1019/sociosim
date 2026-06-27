# Changelog

All notable changes to SocioSim. Format: Keep a Changelog. Branch: `feat/audit-p0-p1`.

## [Unreleased] — audit P0/P1 remediation

### Added
- **Audit-4 black-box remediation:** ad auctions now enforce hard campaign
  budgets, reports render undefined metrics as `n/a` instead of literal `nan`,
  minor-ad language is jurisdiction-aware, moderation/fairness outputs include
  sufficiency denominators, calibration exports include per-target z-scores and
  the dominant metric, transparency exports carry research/legal/no-real-person
  caveats, and determinism baselines were intentionally re-locked for the budget
  behavior change.
- **Audit-3 web/corporate remediation:** realistic v2 feed/ad PNG assets plus
  split 3:2 feed covers and 2:1 ad creatives; `/api/creative` now serves
  deterministic realistic dashboard creatives for 2:1 requests. Added
  `ad_opportunity` events so campaign lift uses eligible-opportunity ITT
  denominators while paid impressions/spend remain priced-auction only. MC
  intervals are persisted into `report.md`, behavior params are validated, and
  compare includes ad/disclosure headline deltas. Determinism baselines were
  intentionally re-locked because the event stream now includes the new audit
  events.
- **Audit-3 UI/security readiness:** preset switching resets all run-affecting
  form state, trained classifier mode disables precision/recall target sliders,
  compare mode clears stale tabs, exports use header-authenticated fetches
  instead of query-token URLs, remote `/api/creative` is token-protected, and the
  history drawer has dialog/focus handling.
- **Audit-2 quant/marketing strengthening:** CUPED-adjusted lift (covariate =
  each agent's latent baseline propensity; Deng et al. 2013), a two-proportion
  lift p-value, and Benjamini-Hochberg FDR across campaigns (`lift_significant`)
  so many-campaign runs don't manufacture false "significant lift". Added
  synthetic marketing economics on the now-valid incrementality — ROAS, iROAS,
  CAC, LTV, incremental_ltv (clearly labelled synthetic). New
  `stats.benjamini_hochberg` / `stats.two_proportion_p`; surfaced in the report.
- **Tooling:** ruff lint gate (config + dev dep) and a GitHub Actions CI
  workflow (ruff + pytest); all pre-existing lint findings cleared.
- **P6 UI (partial):** preset selection now resets to documented defaults before
  applying overrides (S1, no stale carryover); a Monte Carlo Replicates control
  reaches Research mode (S4) and the run header shows preview/research provenance;
  MC intervals + transparency report surface in the Log tab; `tick_hours` is a
  divisor-of-24 select (S5); charts get role=img/aria-label; the CSS header
  comment now matches what's implemented (Q-CSS). Multi-route studio + force-graph
  + campaign editor (S3) deferred (HANDOFF.md).
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
- **Distribution bug (would crash every installed/Docker run):** the benchmark
  targets JSON loaded via a repo-relative path and was not packaged, so an
  installed wheel / the Docker image would `FileNotFoundError` at `load_targets()`
  on every run. Moved `default_targets.json` inside the package
  (`socio_sim/data/benchmarks/`), fixed the loader to a package-relative path,
  added it to package-data, and a CI build step that asserts the wheel ships the
  targets JSON + 4 policy packs. Verified by loading from an extracted wheel with
  the source tree off `sys.path`. Regression test added.
- **P5b S2:** web SBM graph now sizes its blocks to the agent count (was a
  hardcoded [500,500] that crashed at any n_agents != 1000). Q-KINDS: removed
  declared-but-never-emitted `follow`/`unfollow`/`policy_gap` event kinds and
  corrected the spec (static graph in v1). Hot-loop perf + LLM token/cost
  accounting deferred (determinism constraints — see HANDOFF.md).
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
