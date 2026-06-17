# SocioSim Audit Log & Issue Ledger

Branch: `feat/audit-p0-p1`. Severity: P0 blocking · P1 serious · P2 important · P3 polish.
Status: OPEN / IN-PROGRESS / DONE (with commit) / DEFERRED (-> HANDOFF.md).

## Decisions (confirmed by product owner)
- **MC wiring:** Preview (single-run, within-run bootstrap CIs) + Research (N-replicate MC percentile CIs) modes.
- **Incrementality:** Add organic baseline conversion channel; lift = exposed_rate - holdout_rate. (Design validated by 2 background research agents before implementation.)
- **UI scope:** Full multi-route studio. Parallelize; maintain HANDOFF.md so work can resume at a token cutoff.

## Issue ledger

| ID | Sev | File:line | Issue | Fix | Test | Status |
|----|-----|-----------|-------|-----|------|--------|
| Q-MC | P0 | pipeline.py:48-52; run.py:55-91; web/app.py:256 | Default surfaces run 1 replicate; within-run bootstrap CIs mislabeled as "95% CI"; `run_replicates` never called outside tests | Wire MC; Preview+Research modes; provenance labels | MC-CI convergence; provenance presence | **DONE** (P1e) |
| Q-LIFT | P0 | ads/measure.py:47-56 | Holdout never converts -> lift = exposed_rate (tautology) | Organic baseline conversion channel | lift->0 under null; lift>0 only if exposed>baseline | **DONE** (P2) |
| Q-HILL | P1 | validation/targets.py:34-54 | degree_tail_exponent target never computed | Compute Hill exponent into observed | all-targets-in-observed | **DONE** (P1b) |
| Q-CI | P1 | analytics/report.py | "every aggregate has a 95% CI" false; precision/recall/appeal bare | Wilson intervals + relabel docs | CI presence per rate | **DONE** (P1c) |
| Q-PACK | P1 | policy/engine.py:26-29; packs/*.yaml | Schema lacks source_citation/legal_uncertainty/transparency_field/user_rights/human_review_required; no statute refs; EU 24h overstated | Extend schema; add citations; correct deadline framing; transparency exporter | pack-schema; transparency coverage | **DONE** (P3) |
| Q-PARAM | P1 | engine.py:35-44,312-317 | ~15 undocumented magic constants drive all outputs; never sensitivity-tested | Extract cited BehaviorParams; sensitivity sweep | determinism regression; sensitivity-rank | OPEN |
| Q-PERF | P1 | engine.py:267-349; graph/metrics.py:23 | Per-agent Python loops + exact clustering -> standard profile impractical | Index recent posts by author; approx clustering n>2k; benchmark | perf budget | OPEN |
| Q-TRAV | P1 | web/app.py:355-356 | Static-file path traversal (no containment) | resolve()+is_relative_to() | traversal returns 404 | **DONE** (P5a) |
| Q-CLAUDE | P2 | content/claude_adapter.py:54-91 | Prompt hardcodes TOPICS[0]/casual; cache key ignores topic/tick | Key by topic/stance/ideology; build prompt from item | cache-key uniqueness | OPEN |
| Q-KINDS | P2 | logs/events.py:16-33 | policy_gap/follow/unfollow declared, never emitted; graph static (no churn) | Implement follow/unfollow+churn OR remove kinds + spec claim | follow-event or kind-coverage | OPEN |
| Q-REVIEW | P2 | moderation/workflow.py:106-157 | Reviewer ground-truth heuristic + uncited appeal magic | Document/expose params | reviewer convergence | OPEN |
| S1 | P2 | web/static/app.js:79-84 | Presets are additive, not reset -> stale values persist across preset switches | Reset to defaults then apply overrides | preset-applies-clean-state | OPEN |
| S2 | P2 | web/app.py:100-101 | SBM block_sizes hardcoded [500,500], ignores n_agents | Derive blocks from n_agents | sbm-respects-n | OPEN |
| S3 | P1* | engine.py:50-62 (UI) | No campaign-level marketing controls in UI (budget/bid/targeting/variants) | Add campaign editor feeding campaigns | campaign-editor roundtrip | OPEN |
| S4 | P2 | UI | No n_replicates control (blocked on Q-MC) | Expose in Research mode | n/a | OPEN |
| S5 | P3 | index.html:56; config.py:160 | tick_hours UI allows non-divisors of 24 -> validation error | Constrain to {1,2,3,4,6,8,12,24} | n/a | OPEN |
| S6 | P3 | engine.py:96; web | Classifier global-only; political base rate not exposed; homophily attr hardcoded | Optional per-category; expose political rate | n/a | OPEN |
| Q-CSS | P3 | web/static/style.css:1-4 | Header advertises aurora-mesh/tilt/spotlight/magnetic not implemented | Implement or correct comment | n/a | OPEN |
| Q-DOC | P3 | usage.md:9,99; ethics.md:28 | "110+ tests" (108); content_mode drift; "MC built in" overclaim | Correct docs | n/a | OPEN |

\*S3 is P1 specifically for marketing/government usefulness scores.

## Determinism baselines (locked pre-refactor)
- test/EU: `a8a8b243e5958c1620d5e4ed0e9bee55c866c78d4459993c57eeca3bf848bc36`
- test/US: `f7473dc24c1ff189045e807f7f1e8798ed2416a5bf43020ca8f2344edbd27190`
- test/CN: `3f3c6f2bb509e64e69ea5f7cbf716a078932bc8e5c73d137afa9db785cb8cd14`
Baseline suite: 108 tests passing at branch point.
