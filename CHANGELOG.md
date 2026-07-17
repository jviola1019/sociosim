# Changelog

All notable changes to SocioSim. Format: Keep a Changelog. Branch: `feat/audit-p0-p1`.

## [Unreleased] — audit P0/P1 remediation

### Added (2026-07-16 sprint 12: markets, UX navigability, coherence sweep — from main @ e7ca1f9)
- **Named markets in the campaign editor** (`socio_sim/ads/markets.py`): the
  opaque "Topic 0..7" selector now shows the 8 named content markets, and a
  new advertiser-vertical selector offers 9 verticals whose base-CTR anchors
  are the ONLY auditable per-vertical measurements in the project (iPinYou
  2014 Tables 2+3, the same hash-verified artifact behind the ad_ctr target;
  applicability limits stated — 2013 China display RTB, not a forecast).
  Adopting an anchor is recorded as `sourced_vertical_anchor:<id>` in the
  per-field economics provenance; an explicit user CTR always wins.
- **Campaign editor redesign**: the misaligned header-row grid (the
  "spacing is off" defect) is replaced by per-field labeled cards that wrap
  responsively; every field carries a plain-language tooltip readable by
  both marketing and government users. Found+fixed: the wrapper labels
  initially reused the inputs' class names, breaking field lookup.
- **Settings sweep** (`scripts/settings_sweep.py` → docs/SETTINGS_SWEEP.md):
  all 76 knob cases run the engine and pass coherence checks (finite
  outputs, rates in [0,1], NaN only with a genuinely zero denominator) plus
  5 directional relations under common random numbers (ads off → 0
  impressions; 3x harmful rates never decrease exposure; etc.). The sweep
  found and fixed 2 real defects: a float `exploration_pool_size` crashed
  numpy inside the engine, and one campaign's undefined lift NaN-poisoned
  the exposure-weighted ITT mean (now excludes undefined strata; NaN only
  when NO stratum is defined). CI holds a fast subset
  (tests/test_settings_sweep.py).
- **Persona sandbox flows** (tests/test_persona_flows.py): a first-time
  marketing user (2 Business presets: configure a named-vertical campaign,
  run, read the Ads tab with its honest footnotes) and a first-time
  government analyst (EU-DSA and CN-label sandboxes: fairness table, audit
  log, transparency export, honesty chips) drive the real console
  end-to-end under Playwright.
- **Tooltips everywhere**: 34 controls that lacked hovers now explain
  themselves in one or two plain sentences (dual-audience wording).
- **POST rate limiting**: token-bucket (60/min, burst 20 → HTTP 429) on
  state-changing requests — a local DoS guard, documented in SECURITY.md
  as NOT authentication; row-level security restated as NOT APPLICABLE
  (single-user tool, no tenant rows).
- **Feed cards** show the real simulated timestamp (Day d · HH:00 from the
  event tick) and @agent handles; ad cards carry a "Sponsored" chip. No
  fabricated engagement counts — decorative numbers would be fake data.
- **Repo pruning** (286 tracked files audited): removed the orphaned
  `scripts/asset_contactsheet_review.py` (superseded by asset_qa.py's
  contact sheet) and unreferenced `docs/ASSET_MANIFEST.md`; gate-coupled
  historical records retained deliberately.
- docs/RELEASE.md exact-SHA ledger row for merge e7ca1f9 (run 29548709876).

### Added (2026-07-16 material-audit remediation, from main @ 86bb4b7)
- **Seed-generalization protocol** (`socio_sim/validation/seed_protocol.py`,
  `scripts/seed_protocol_eval.py`): 20 fitting / 20 validation / 20 LOCKED
  holdout seeds (hash-pinned), per-seed implausibility + component z-scores +
  replay verification, distribution summaries (median/mean/p5/p25/p75/p95/max,
  pass proportion with Wilson + bootstrap 95% intervals, dominant-failing-metric
  frequencies), and distributional acceptance criteria. Committed artifact:
  `socio_sim/data/seed_protocol_results_v1.json` (ships in the wheel).
  **Outcome: holdout acceptance FAILED (60% pass vs >=80% required)** — the
  profile label is downgraded to **seed-42 aggregate demonstration profile**
  everywhere (config docstring, README, KNOWN_LIMITATIONS, findings doc, web
  UI); no tolerance was widened and no parameter retuned on holdout results.
  Tests pin list disjointness, holdout immutability, target value/tolerance
  immutability, only-seed-42-good acceptance failure, artifact/label coupling,
  and live cross-session replay of protocol seeds.
- **Reproducible source verification:** every `sourced_aggregates_v1` target
  now records a `source_artifact` block (SHA-256, byte size, retrieval time,
  version-pinned URL, stability class, quote patterns mechanically re-located
  in the hashed bytes) plus `scripts/verify_sources.py` to re-verify;
  `scripts/evidence_gate.py` rejects source-verified claims lacking a
  statistic location, transformation, or hashed artifact.
- **Supply-chain pinning:** Syft pinned to v1.48.0 with published-checksum
  verification (fail closed) replacing `curl .../main/install.sh | sh`; all
  GitHub Actions pinned by full commit SHA; release `workflow_dispatch` fails
  when checkout does not resolve to the requested SHA; provenance now records
  the workflow-file hash and python/pip/setuptools/build/wheel/syft versions;
  CI tests fail any workflow that downloads executables from mutable refs or
  pipes downloads into a shell. Exact-SHA CI ledger added to docs/RELEASE.md
  (86bb4b7 -> run 29398446514).
- **Cache concurrency gap tests:** ClaudeAdapter blocked-branch adoption of a
  concurrent writer's accepted winner; byte-identical cache after a losing
  same-key update; lock sidecar holds no cache content; win32 msvcrt lock
  blocking test (documented CI gap: GitHub CI is ubuntu-only).
- **Web console honesty + fidelity:** the web "aggregate" profile now builds
  the REAL profile config (cm graph + homophily 0 — it previously built a plc
  approximation with homophily 0.15 under the profile's label); cm graph
  configurable in the form; Target Comparison tab shows the status hierarchy
  (Synthetic -> source-linked/unsupported targets -> fitting/validation/
  holdout seed group -> multi-seed holdout verdict -> "Not empirically
  validated") and a per-target provenance drawer (source, population, period,
  definition limits, transformation, tolerance origin, artifact hash, seed +
  replicates, valid/invalid uses); `/api/meta` and run payloads carry the
  seed-protocol status. A11y: fixed heading order (fairness h4->h3), export
  menu aria-expanded/Escape/focus-return, radiogroup labelling, run-phase
  aria-live, error stage role=alert.

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
