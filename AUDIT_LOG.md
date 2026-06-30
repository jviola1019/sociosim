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
| Q-PARAM | P1 | engine.py:35-44,312-317 | ~15 undocumented magic constants drive all outputs; never sensitivity-tested | Extract cited BehaviorParams; sensitivity sweep | determinism regression; sensitivity-rank | **DONE** (P1d+P4) |
| Q-PERF | P1 | engine.py:267-349; graph/metrics.py:23 | Per-agent Python loops + exact clustering -> standard profile impractical | Index recent posts by author; approx clustering n>2k; benchmark | perf budget | DEFERRED (determinism risk; see HANDOFF) |
| Q-TRAV | P1 | web/app.py:355-356 | Static-file path traversal (no containment) | resolve()+is_relative_to() | traversal returns 404 | **DONE** (P5a) |
| Q-CLAUDE | P2 | content/claude_adapter.py:54-91 | Prompt hardcodes TOPICS[0]/casual; cache key ignores topic/tick | Key by model/full prompt/topic/stance/tick; build prompt from generated item | cache-key uniqueness | **DONE** |
| Q-KINDS | P2 | logs/events.py:16-33 | policy_gap/follow/unfollow declared, never emitted; graph static (no churn) | Removed dead kinds + corrected spec (churn deferred) | dead-kinds-removed | **DONE** (P5b) |
| Q-REVIEW | P2 | moderation/workflow.py:106-157 | Reviewer ground-truth heuristic + uncited appeal magic | Document/expose params | reviewer convergence | OPEN |
| S1 | P2 | web/static/app.js:79-84 | Presets are additive, not reset -> stale values persist across preset switches | Reset to defaults then apply overrides | preset-applies-clean-state | **DONE** (P6) |
| S2 | P2 | web/app.py:100-101 | SBM block_sizes hardcoded [500,500], ignores n_agents | Derive blocks from n_agents | sbm-respects-n | **DONE** (P5b) |
| S3 | P1* | engine.py:50-62 (UI) | No campaign-level marketing controls in UI (budget/bid/targeting/variants) | Add campaign editor feeding campaigns | campaign-editor roundtrip | DEFERRED (P6 full UI) |
| S4 | P2 | UI | No n_replicates control (blocked on Q-MC) | Expose in Research mode | live-research-http | **DONE** (P6) |
| S5 | P3 | index.html:56; config.py:160 | tick_hours UI allows non-divisors of 24 -> validation error | Constrain to divisor select | n/a | **DONE** (P6) |
| S6 | P3 | engine.py:96; web | Classifier global-only; political base rate not exposed; homophily attr hardcoded | Optional per-category; expose political rate | n/a | OPEN |
| Q-CSS | P3 | web/static/style.css:1-4 | Header advertises aurora-mesh/tilt/spotlight/magnetic not implemented | Corrected comment to match implementation | n/a | **DONE** (P6) |
| Q-DOC | P3 | usage.md:9,99; ethics.md:28 | "110+ tests" (108); content_mode drift; "MC built in" overclaim | Correct docs | n/a | **DONE** |

\*S3 is P1 specifically for marketing/government usefulness scores.

## Session 2026-06-30: independent re-verification of PR #4 (`fix/p0-llm-cache-and-audit-hardening`, PR #5)

PR #4 was merged despite GitHub Actions showing `failure`; its remediation
report was treated as unverified per project policy and re-checked from a
clean `main` checkout. Full detail and evidence in `AUDIT_REMEDIATION_REPORT.md`
addendum.

| ID | Sev | File:line | Issue | Fix | Test | Status |
|----|-----|-----------|-------|-----|------|--------|
| R1-CI | P0 | `.github/workflows/ci.yml:16-30` | Full pytest run (incl. Playwright e2e test) executed before any step installed Chromium -> clean-runner CI failure, later gates skipped | Install Playwright browsers before the test step | `tests/test_ci_workflow.py` (workflow-ordering assertion) + GitHub Actions run `28481398083` green | **DONE** (`d8aea1f`) |
| R2-LLMCACHE | P0 | `socio_sim/content/llm_adapter.py:106-123` (pre-fix) | Cached `status=="blocked"` LLM response served verbatim on a later identical request (same adapter or fresh instance reloading the cache file); guard never re-checked; no degradation event | Branch on `cached["status"]` before the read path; never serve a blocked entry as content; deterministic degradation event with preserved reason codes; `_BLOCKED_GUARD_VERSION` is the only deliberate invalidation path | 9 new tests in `tests/test_llm_adapter.py` | **DONE** (`e0a96d4`) |
| R3-CALPROFILE | P1 | `socio_sim/web/app.py:139` (pre-fix) | `profile=="calibrated"` still accepted as a first-class public API value (only hidden from the UI dropdown, not gated behind migration) | Remove from `_PROFILES`; add `_migrate_legacy_profile` so only the migration path reaches `aggregate_matched_prototype` | `tests/test_web.py::test_calibrated_profile_not_publicly_advertised` + 2 more | **DONE** (`8975ee5`) |
| R4-ASSETQA | P2 | `scripts/asset_qa.py:135-146` (pre-fix) | Legacy-v3-reference allowlist incomplete (missed `BASELINE_AUDIT_SNAPSHOT.md`, `scripts/claim_scan.py`) -> gate failed locally despite correct asset migration | Widen allowlist; label snapshot doc as historical | re-ran `python scripts/asset_qa.py` -> pass, 92 records | **DONE** (`9a9c524`) |
| R5-COVERAGE | P3 | `.coverage` (tracked) | Generated coverage DB tracked in git, churns on every local run (already flagged, not fixed, in original report) | `.gitignore` + `git rm --cached` | n/a | **DONE** (`9a9c524`) |
| R6-EVIDENCEGRAIN | P1 | `socio_sim/data/evidence_registry.json` | 7 broad-category records, not per-numeric-default provenance; violates "no generic assumption record may stand in for dozens of unrelated numeric defaults" | Map every decision-facing numeric default individually | none yet | **OPEN** (sized, not started; see HANDOFF) |
| R7-ASSETART | P1 | `scripts/generate_v4_assets.py:40-73` | Still procedural gradient/ellipse/noise generation (the exact pattern the brief says to delete); 3 roles, not 8 required visual families; only 92 of 96+ required | Replace with deliberately authored, art-directed compositions across 8 families | none yet | **OPEN** (sized, not started; see HANDOFF) |
| R8-CLAIMSCAN | P2 | `scripts/claim_scan.py:10-21` | 10-phrase literal blacklist, not the context-aware policy scanner required | Rebuild as context-aware scan (term + context + historical-doc allowance) | none yet | **OPEN** (not started) |

## Determinism baselines (locked pre-refactor)
- test/EU: `a8a8b243e5958c1620d5e4ed0e9bee55c866c78d4459993c57eeca3bf848bc36`
- test/US: `f7473dc24c1ff189045e807f7f1e8798ed2416a5bf43020ca8f2344edbd27190`
- test/CN: `3f3c6f2bb509e64e69ea5f7cbf716a078932bc8e5c73d137afa9db785cb8cd14`
Baseline suite: 108 tests passing at branch point.
