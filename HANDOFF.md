# SocioSim — Sprint Handoff / Resume State

**Purpose:** live resume doc so this sprint continues across sessions/token cutoffs.
Resuming? Read this, then `AUDIT_LOG.md`, then `CHANGELOG.md`. Branch: `feat/audit-p0-p1`.

## SPRINT 6 — research-only -> measured (validation ladder, user decision 2026-06-22)
Climb from "research-only" toward "measured" WITHOUT crossing legal/ethics lines
(no PII, no scraping, no real-person decisions, no point-prediction). DONE+verified:
- Validation ladder defined w/ provenance labels: synthetic-exploratory <
  uncalibrated < calibration-consistent < stylized-fact-validated <
  backtested-out-of-sample < measured-on-benchmark (docs/DATA_MANIFEST.md, usage.md).
- S6.1 validation/stylized.py: 5 cited stylized facts (heavy-tail degree,
  clustering>>random, cascade skew, participation inequality, diurnal) — 5/5 on
  calibrated world; 3 tests.
- S6.2 validation/backtest.py: leave-out out-of-sample backtest (calibrate graph
  on TRAIN subset of public aggregates, validate HELD-OUT metrics) -> test_pass,
  I_test=0.12 at quick scale; 3 tests.
- S6.3 run.py --backtest -> BACKTEST_REPORT.md (committed); docs/DATA_MANIFEST.md
  governance (aggregate/public only, no PII, no scraping; DSA Art.40 gate for real
  microdata). Honest ceiling: aggregate/pattern agreement, NOT point-prediction;
  agent behavioural magnitudes stay calibrated assumptions. Rung-4 (classifier on
  real public benchmark) is the next gated step (needs explicit data decision).

## SPRINT 5 — UX/marketing/settings/security redesign (user decision 2026-06-21)
USER DECISIONS: (1) Red Team tab -> **Full Business Marketing Suite** (subsections:
Campaign Studio + A/B Experiment Lab + Audience & Brand-Safety), built on the
existing measurement engine (incrementality/iROAS/CAC/LTV/MDE/dose-response).
(2) **Fold red-team adversaries into presets** (drop standalone tab; keep feature
via presets). (3) Presets: BOTH cited-framework AND business-scenario, **subsectioned**;
ground in heavy research (many cited sources). (4) Settings: clarify
labels/units/help/grouping + restructure/add knobs + harden web console +
document security posture (ALL four).
EVIDENCE BASE: 2 background research agents dispatched (marketing measurement/
brand-safety standards [a7e44cef]; moderation-settings grounding + web-app
security [a28f9a6]) -> cited recommendations feed presets/settings/suite/security.
SEGMENTS: S5.1 research(agents) · S5.2 cited+subsectioned presets + visible
summary · S5.3 settings clarity/restructure · S5.4 Business Suite · S5.5 security
hardening + SECURITY.md · S5.6 test+browser-verify+docs+commit.
SPRINT-5 DONE+verified (commits 60-65): S5.1 research (2 agents, ~130 cited
sources) -> docs/RESEARCH_EVIDENCE.md; S5.2 cited+subsectioned presets (14:
Regulatory/Research/Business) + visible "what changes"+Sources panel + adversaries
FOLDED into presets (no standalone tab); S5.3 settings clarified (units + cited
ranges as tooltips); S5.4 Business Marketing Suite (A/B power lab, unit economics,
reach&freq, GARM brand-safety) replaces Red Team; S5.5 security hardening
(token + Origin/Host + CSP/headers + body/CT limits + SSRF allow-list) + SECURITY.md
+ 8 tests. All browser-verified (0 console errors; folded red_team reaches run;
calculators compute). Fixed real bug: marketing inputs' min/step blocked the form
submit -> stripped constraints. 214 tests green; ruff clean.

## SPRINT 4 — fix ALL caveats (user decision 2026-06-19)
DECISION: keep ALL guardrails (fully legal, no PII, no fabrication, research-only,
not-legal-advice, projections-not-predictions) as honest disclaimers; push every
ENGINEERING caveat to research-grade rigor ("what top corps use, more fine-tuned",
"without fallacing the ABM"). Scope (all selected): (1) calibrate graph/diurnal/
behavior to published targets; (2) expand sensitivity multi-output/seed/Sobol +
chain ABC->MC; (3) approx clustering for scale; (4) dynamic social graph
(follow/unfollow/churn — regen determinism). PLUS stale-doc fixes + style.css.
SPRINT-3 DONE+verified: real trained classifier (measured P/R), bundled empirical
datasets (cited), distributed pluggable executor, procedural image + APNG video +
pluggable backend + accel/GPU kernel (numpy-verified). 49 commits.
SPRINT-4 DONE+verified (all 5 eng caveats + UI): (1) calibrated profile (plc p=0.7,
I=1.0 all in-band, CALIBRATION_REPORT, replay); (2) multi-output/seed/Sobol
sensitivity + ABC->output (report §1b/§2b); (3) approx clustering n>5000; (4)
dynamic graph follow/unfollow/churn (opt-in, deterministic+replay, default static);
(5) stale-doc + style.css honesty. UI: all new options exposed as controls
(classifier/benchmark/plc/dynamic-graph/calibrated profile) — browser-verified
end-to-end (trained+twitter_like+dynamic run = 3812 events). Guardrails KEPT
(no-PII, not-legal-advice, projections-not-predictions, synthetic-by-design).
Caught+fixed regression: test_logs dead-kinds test updated (follow/unfollow/churn
now LIVE). Coverage 93%; ruff clean; wheel ships 7 data assets.
POST-AUDIT: + Saltelli S1+ST sensitivity (best-practice); data-legality verified
(all aggregate/cited/synthetic, no PII/scraping). ONBOARDING FIX: run.py now
catches missing runtime deps with install guidance (user hit ModuleNotFoundError
on the MS-Store python shim); + requirements.txt; README install rewritten.
PRESET/KNOB AUDIT: all 8 presets build+run+apply accurately; every knob probed =
live (no dead knobs); benchmark analytics-only. Guarded by test_presets.py.
Branch pushed to origin/feat/audit-p0-p1. PR not yet opened (no gh CLI/token).

## Status snapshot
- Suite green (~122 tests). Determinism baselines RE-LOCKED after P2 (test_determinism_regression.py).
- Confirmed scope: Preview+Research MC modes; organic-baseline incrementality; full multi-route UI.
- Commits so far: P1a/P1b/P5a; P1c; P2 (incrementality).
- DONE so far: Q-HILL, Q-CI, Q-DOC(most), Q-TRAV, Q-LIFT, Q-MC. **Both P0s CLOSED.**
- Commits: P1a/P1b/P5a; P1c; P2; P1e; P3; P1d.
- NEXT: P4 calibration/sensitivity over BehaviorParams + VALIDATION_REPORT.md; P5b perf/SBM/follow-unfollow/LLM accounting; P6 multi-route UI.

## Order of execution (value x completability)
1. [x] P1a determinism regression guard
2. [x] P1b Hill exponent -> observed (all targets compared)
3. [x] P5a path-traversal fix
4. [x] P1c Wilson intervals + provenance banner + doc-overclaim fixes
5. [x] P1d BehaviorParams extraction (done; behaviour-preserving; knobs live + serialized)
6. [x] P1e Monte Carlo wiring (Preview + Research) into pipeline/CLI/web. NOTE: backend + CLI done; UI n_replicates control (S4) still pending in P6.
7. [x] P2 organic-baseline incrementality (done; latent baseline + Newcombe/Beta CI). DESIGN BELOW kept for reference.
8. [x] P3 policy-as-code citations + schema fields + transparency exporter (done)
9. [x] P4 calibration + sensitivity over BehaviorParams + VALIDATION_REPORT.md (done; `run.py --validate`)
10. [~] P5b: DONE = S2 (SBM blocks from n_agents), Q-KINDS (removed dead follow/unfollow/policy_gap, corrected spec).
       DEFERRED with rationale: (a) hot-loop perf — index recent_posts by author + approx clustering n>2k;
       MUST preserve feed candidate/pool ORDER or it changes exploration sampling -> different events;
       safest as an order-preserving refactor, else accept a one-time hash regen. (b) LLM token/cost accounting —
       wall-clock latency must NOT enter the hashed event stream; accumulate on the adapter (deterministic token
       estimate ok in event, latency/cost in a separate adapter aggregate surfaced in the result).
11. [~] P6: DONE = S1 (preset reset-then-apply), S4 (n_replicates control + MC/transparency in Log + mode tag),
       S5 (tick_hours divisor select), Q-CSS (corrected header comment), chart a11y (role=img/aria-label).
       DEFERRED (next sprint, large): multi-route studio (Setup/Run/Compare/Validate/Audit/Transparency),
       2D force-graph + cascade replay, S3 campaign editor (budget/bid/targeting/variants), full a11y
       (slider aria-valuetext, focus order, data tables), provenance badges on cards. Optional SPA over the
       JSON API; keep stdlib server canonical. Browser-verify after building (chrome-devtools/playwright MCP).
12. [ ] Final: full pytest + ruff, scorecard, KNOWN_LIMITATIONS.md, finish branch

## P2 incrementality — agreed design (both research agents done)
Adopt the **latent-uniform CRN threshold model** (methodology agent) over the simpler
per-day Bernoulli (impl-spec agent), because it gives near-zero-variance individual incrementality:
- Per-agent **latent baseline propensity** `b_i` drawn at persona init from an ad-INDEPENDENT
  stream (new persona attribute, e.g. Beta calibrated to a target organic rate).
- Conversion via **threshold on an identity-keyed CRN uniform** `U_i` (new RNG stream, e.g.
  `tree.generator("conversion", rep)` advanced per (agent, opportunity)): convert iff `U_i < propensity`.
- Holdout: `propensity = b_i`. Exposed: `propensity = b_i + (1-b_i)*delta_i` (uplift, stays <=1).
  Same `U_i` in both arms -> agent flips ONLY because the ad changed propensity.
- New event kind `organic_conversion` (add to EVENT_KINDS whitelist). Keep ad funnel events
  (`ad_conversion`) intact; `measure_campaign` unions both channels for exposed/holdout rates.
- Estimator: absolute lift `Δ = p_E - p_C`. Headline CI: **Newcombe (Wilson-hybrid) difference
  of two proportions**; report **Beta-difference posterior + P(lift>0)** alongside; CUPED on known
  `b_i` for variance reduction; relative lift via log-ratio delta or bootstrap.
- Guardrails: keep organic content ON in both arms; symmetric attribution window anchored to
  counterfactual exposure time; ITT over frequency; **Benjamini-Hochberg FDR** across campaigns.
- Determinism: dedicated stream, fixed ascending agent_id iteration, one draw/agent/opportunity.
  This is an INTENTIONAL behavior change -> regenerate the 3 locked baseline hashes in the same
  commit and note in CHANGELOG.
- Tests: holdout converts via baseline; lift~0 under null; lift>0 only when exposed>baseline;
  holdout never sees ads; baseline independent of ad stream; measure fields (n_holdout>0, holdout_rate>0).
Citations recorded in (to-create) SOURCE_LEDGER.md: CUPED (Deng et al. 2013), CRN ABM (arXiv:2409.02086),
BH-FDR (1995), Bayesian A/B (arXiv:2003.02769), Ghost Ads / Measured incrementality guide.

## Invariants that must never regress
- Same config+seed -> identical event-stream SHA-256 (determinism + replay tests).
- No headline metric without a provenance label.
- No "validated/calibrated" claim without evidence in VALIDATION_REPORT.md.
- numpy Generators only from the module-keyed SeedTree (no global RNG).

## Dimensions now AT 10 (this session, verified): Quant, Testing, Documentation.
Quant: MDE/power + discrete-KS gate + ABC-posterior->output propagation + CUPED + BH-FDR.
Testing: ~165 tests incl. hypothesis property tests; 92% coverage + 85% CI gate; ruff gate.
Documentation: README matches code; AUDIT_LOG/CHANGELOG/VALIDATION_REPORT/KNOWN_LIMITATIONS/SOURCE_LEDGER.
Deployment ~9.5 (ruff+CI+coverage+Dockerfile). Marketing ~9.5 (campaign backend/API done; UI editor pending).
3D ~6 (topology force-graph, browser-verified). UX ~8, Visual ~8.

## DONE (browser-verified where UI): campaign editor UI, cascade replay (3D/Motion),
## in-UI transparency export, DARK THEME toggle (Visual), docs hardening (usage.md/spec),
## preset-run end-to-end test. Full testing: 92% coverage, ruff clean.
## HONEST scorecard: Quant/Testing/Documentation/Marketing = 10
## (Marketing now: incrementality + Newcombe/Beta CI + CUPED + p-value + BH-FDR +
##  MDE + ROAS/iROAS/CAC/LTV + frequency dose-response + attribution window + editor UI);
## Visual/Deployment = 9.5; Engineering 9; UX 8.5; 3D/Motion 7.5; Regulatory 7.5. Overall ~9.2.
## UX 9.5: in-UI Compare tab DONE (browser-verified) + /api/compare backend. Regulatory ~8.5:
## appeal-resolution p95 + transparency rights_impact (appealable/removals-without-notice) DONE.
## ENGINEERING perf NOTE: hot-loop speedup is NOT a safe behaviour-preserving change — the
## exploration POOL is index-sampled (feed_rng.choice over pool order), so reordering it changes
## sampled posts -> different events. Needs an algorithmic pool-sampling redesign (global sample,
## intentional hash regen), not a quick win. Engineering stays an honest 9.
## UX = 10 (Compare tab + audit-log explorer DONE). Deployment ~9.8 (wheel+Docker+CI build gate;
## FIXED distribution bug: targets JSON now packaged in socio_sim/data/benchmarks, verified from
## an extracted wheel). 5 dims at 10: Quant, Testing, Documentation, Marketing, UX.
## UPDATE: Engineering ~9.5 (feed hot-loop optimised, ≈linear), Regulatory ~9.5 (trusted-flagger
## priority added), 5 dims at 10 (Quant/Testing/Docs/Marketing/UX). Overall ~9.65.
## NOTE on 3D (7.5): the 2D topology + cascade views are a DELIBERATE design choice — the audit
## warns against decorative 3D; true WebGL would risk "3D slop" and is not clearly a cognition win.
## REMAINING to 10 (heavier builds, honest):
## Engineering (order-preserving hot-loop perf + parallel MC); Regulatory (appeals SLA,
## trusted-flagger, rights-impact); Deployment (Playwright-in-CI); 3D true WebGL.

## SPRINT 3 — formerly out-of-scope (spec §6), now in scope (do RIGHT, verified):
1. Real moderation-model training: numpy logistic-regression text classifier
   (`content/ml_classifier.py`) trained on category-signal content; measured held-out
   P/R; opt-in `classifier_mode="trained"` so DEFAULT determinism is preserved.
2. Bundled empirical datasets: multiple PUBLISHED AGGREGATE (no-PII) target sets in
   data/benchmarks/ + selectable loader; citations from research agent.
3. Distributed/GPU: pluggable executor on parallel MC (ProcessPool done; Dask/Ray-ready);
   GPU/multi-node honestly opt-in/env-gated (can't verify GPU here -> don't fake it).
4. Real image synthesis: deterministic procedural raster (numpy->PNG, zero-dep, offline,
   reproducible) producing real image bytes; diffusion via optional plugin hook.
DESIGN: stays deliberate/editorial — no AI-slop. Each item TDD + verified + committed.

## Remaining punch-list to a literal 10/10 (prioritised)
1. Multi-route Compare view (experiments.runner baseline-vs-intervention via a new
   /api/compare endpoint) + audit-log explorer + provenance badges on cards — UX ->9.5/10.
2. Dark control-room theme toggle (CSS var swap) — Visual ->9.5.
3. Engineering ->10: order-preserving hot-loop perf (determinism-guarded) + parallel MC.
4. Regulatory/Gov ->10: appeals SLA, trusted-flagger priority, rights-impact metrics, retention setting.
5. Deployment ->10: Playwright UI smoke in CI; publish/release packaging.
6. 3D ->10 (optional): true WebGL graph; Motion: more state transitions.

## Notes for the multi-route UI (P6)
- Keep the stdlib server canonical; add an OPTIONAL SPA over the JSON API only if needed.
- Routes: Setup / Run / Compare (experiments.runner) / Validate (sensitivity tornado + calibration)
  / Audit (event-log explorer) / Transparency (policy transparency-report export).
- Add provenance badges on every number; replicate ribbons; delta CIs; 2D canvas force-graph
  + cascade replay (WebGL only if justified); a11y (role=img/aria-label, data tables, slider aria-valuetext).
- Fix S1 (preset reset-then-apply), S2 (SBM blocks from n_agents), S3 (campaign editor), S5 (tick_hours divisors).
