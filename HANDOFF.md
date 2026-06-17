# SocioSim — Sprint Handoff / Resume State

**Purpose:** live resume doc so this sprint continues across sessions/token cutoffs.
Resuming? Read this, then `AUDIT_LOG.md`, then `CHANGELOG.md`. Branch: `feat/audit-p0-p1`.

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

## Remaining punch-list to a literal 10/10 (audit-2, prioritised)
Done since: ruff+CI; CUPED/BH-FDR/ROAS/iROAS/CAC/LTV; **Network topology force-graph**
(backend `graph_sample` + Network tab, browser-verified 140 nodes/500 edges).
Remaining, highest-leverage first:
1. Campaign editor (S3) — Marketing 9->10. Backend: run_and_analyze(campaigns_fn=...)
   so custom campaigns flow to single + MC runs; web parses a `campaigns` body list;
   UI add/remove rows (id/advertiser/bid/budget/targeting/base_ctr/base_cvr). Browser-verify.
2. Cascade-propagation replay over the timeline scrubber — 3D 6->8+ (animate share trees).
3. Multi-route: Compare (experiments.runner baseline-vs-intervention) + Audit-log explorer
   + in-UI Transparency export button — UX 7.5->9.5. Provenance badges on metric cards.
4. Dark control-room theme toggle — Visual. State-communicating motion — Motion.
5. Engineering: order-preserving hot-loop perf + parallel MC + documented scale ceiling.
6. Deployment: Dockerfile + coverage gate + Playwright smoke in CI.
7. Quant: power/MDE, chain ABC posterior -> MC, wire KS distributional gates.
8. Regulatory/Gov: appeals SLA, trusted-flagger queue, rights-impact metrics, retention setting.

## Notes for the multi-route UI (P6)
- Keep the stdlib server canonical; add an OPTIONAL SPA over the JSON API only if needed.
- Routes: Setup / Run / Compare (experiments.runner) / Validate (sensitivity tornado + calibration)
  / Audit (event-log explorer) / Transparency (policy transparency-report export).
- Add provenance badges on every number; replicate ribbons; delta CIs; 2D canvas force-graph
  + cascade replay (WebGL only if justified); a11y (role=img/aria-label, data tables, slider aria-valuetext).
- Fix S1 (preset reset-then-apply), S2 (SBM blocks from n_agents), S3 (campaign editor), S5 (tick_hours divisors).
