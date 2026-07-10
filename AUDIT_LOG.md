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
| R6-EVIDENCEGRAIN | P1 | `socio_sim/data/evidence_registry.json`, `socio_sim/data/scenario_assumptions.json` (pre-fix) | 7 broad-category records, not per-numeric-default provenance; violates "no generic assumption record may stand in for dozens of unrelated numeric defaults" | Exploded `scenario_assumptions.json` into 64 individual entries (one `path`+`label`+`value`+`rationale` per decision-facing numeric default: 13 BehaviorParams fields, 9 category base rates, 2 classifier operating points, 15 RunConfig/graph/auction defaults, 4 profile-scale presets, 12 persona distributions, 5 Campaign defaults, 3 demo-campaign entries); added `missing_numeric_default_provenance()` to `socio_sim/evidence.py`, wired into `validate_registry()` (already a CI gate via `evidence_gate.py`), mechanically checking BehaviorParams/Campaign/category_base_rates/classifier_targets fields against the registry; cross-referenced the 7 legacy benchmark targets (×3 target sets) to `ev.unsupported.aggregate_targets_legacy` via a new `evidence_id` field | `tests/test_evidence.py`: `test_scenario_assumptions_are_individually_mapped_not_broad_category`, `test_no_numeric_default_lacks_provenance`, `test_coverage_gate_catches_a_removed_provenance_entry` (proves the gate fails closed by deleting a real entry and asserting it's caught) | **DONE** |
| R7-ASSETART | P1 | `scripts/generate_v4_assets.py:40-73` | Still procedural gradient/ellipse/noise generation (the exact pattern the brief says to delete); 3 roles, not 8 required visual families; only 92 of 96+ required | Replace with deliberately authored, art-directed compositions across 8 families | none yet | **OPEN** (sized, not started; see HANDOFF) |
| R8-CLAIMSCAN | P2 | `scripts/claim_scan.py:10-21` (pre-fix) | 10-phrase literal blacklist, not the context-aware policy scanner required | Two-layer rewrite: (1) exact stale-phrase blacklist, unchanged, repo-wide; (2) new context-aware layer scanning only docs/*.md, web UI (*.html/*.js), and run.py's CLI-facing text for validation/calibrated/confidence/causal/decision-ready/production/visual-verification/predictive/verified, each flagged only if no hedge/negation marker (not/no/unsupported/incomplete/invalid uses/etc.) or known-fine exempt phrase ("Validation Ladder" framework name, "validates dimensions"/"validates registry" software-validation sense, replay/browser-verified) appears nearby; skips markdown inline-code spans, Python import lines, and dict/attribute-subscript identifiers (when first prototyped against the full .py-inclusive corpus this cut 138 raw hits to 39, then to 2 after the exemptions/fixes below -- see `scripts/claim_scan.py`'s module docstring for the full rationale). Files with a "HISTORICAL RECORD" banner, or in a small living-retrospective-document allowlist (CHANGELOG.md, PLAN_P2.md, CALIBRATION_REPORT.md), are exempt from layer 2 only. Fixed 3 residual findings surfaced while tuning it: `docs/nist_ai_rmf_map.md` had a stale "Calibration measured against..." line (rewritten to reflect the R9 unsupported-target framing) and a "part of validation" phrase reworded to "part of the automated test suite"; added "HISTORICAL RECORD" banners to the two `docs/superpowers/` pre-implementation planning docs (dated 2026-06-12, clearly superseded) | `tests/test_claim_scan.py`: 8 tests, including one proving an unhedged claim IS flagged, one proving the same claim WITH a hedge is NOT, one for the "Validation Ladder" exemption, one for inline-code-span stripping, one for import-line skipping, one for dict-subscript skipping, and an end-to-end "the repo as committed passes clean" assertion | **DONE** |
| R9-OVERCLAIM | P1 | `socio_sim/web/static/app.js:747` (pre-fix), `index.html:333,117` (pre-fix), `socio_sim/agents/personas.py:63` (pre-fix) | Found while building R6: (a) target-distance UI unconditionally claimed "lower = closer to published aggregate benchmarks" and showed in/out pass-fail styling for targets whose evidence record is `kind=unsupported` / `metadata_incomplete` -- a false claim and a forbidden pass/fail seal on unsupported targets; (b) tab literally labeled "Calibration"; (c) `personas.py` comment called a synthetic Beta(2,50) draw "a realistic baseline organic conversion rate" with no citation; (d) `app.js` hate-rate tooltip claimed "realistic platform prevalence is far lower" with no citation | Added `_targets_metadata_complete()` (web/app.py) checking each target's evidence-record kind; `app.js` now branches: complete -> existing diagnostic view, incomplete (current bundled targets, always) -> "Unsupported legacy target comparison" with no pass/fail styling and no published-benchmark claim; renamed "Calibration" tab -> "Target Comparison", benchmark selector label -> "Benchmark *unsupported legacy target set*"; rewrote both unsourced "realistic" claims to state they are scenario assumptions | `tests/test_e2e_playwright.py` (clicks the renamed tab via its unchanged `data-otab` attribute, still passes); manually verified `_targets_metadata_complete()` returns `False` for all 3 bundled target sets | **DONE** |

**Deferred, explicitly not attempted in R6/R9:** a full rename of the backend `implausibility`/`calibration_implausibility` function, dataclass-field, and report-section names (≈15+ call sites across `pipeline.py`, `validation/calibrate.py`, `validation/study.py`, `validation/backtest.py`, and their tests) -- this is invasive enough to warrant its own scoped segment rather than being rushed alongside R6. Also deferred: fetching real, verifiable source URLs/DOIs/retrieval dates for the 7×3 benchmark-target citations in `socio_sim/data/benchmarks/*.json` (each already has a one-line citation but not the full required metadata schema) -- per the no-fabrication mandate this needs an explicit research pass (e.g. WebSearch to confirm real DOIs), not values written from memory.

## Session 2026-07-02: R2-LLMCACHE's "DONE" was incomplete (duplicate adapter missed) + R8 shipped with CI red

Picked up this branch expecting to continue the R7-ASSETART item flagged as
the one remaining large gap in `HANDOFF.md`. Before doing so, re-verified CI
status per project policy (never trust a prior "DONE" without re-running the
check) and found the branch's own last two pushes (R8-CLAIMSCAN's commit and
its PR) both showed GitHub Actions `failure` — the exact recurring failure
mode this project's audit process exists to catch.

| ID | Sev | File:line | Issue | Fix | Test | Status |
|----|-----|-----------|-------|-----|------|--------|
| R11-CISELFFLAG | P0 | `tests/test_claim_scan.py:21` (pre-fix) | The R8 claim-scanner rewrite's own test fixture literally contains the stale phrase `"evidence-based"` (used to prove the detector catches it); `claim_scan.py`'s whole-repo scan isn't scoped away from test files, so it flagged its own fixture as a live violation. Both `python scripts/claim_scan.py` and `pytest tests/test_claim_scan.py::test_full_scan_of_repo_passes` failed — meaning R8 was pushed without a clean `pytest` run first, breaking CI on two consecutive runs | Add `tests/test_claim_scan.py` to `claim_scan.py`'s `ALLOW` list, same rationale already used for `scripts/claim_scan.py` itself (discusses claim language, isn't a claim surface) | re-ran `pytest` (300 passed) and `python scripts/claim_scan.py` (pass) before this fix; both green after | **DONE** (`3461c4b`) |
| R2-LLMCACHE was incomplete | P0 | `socio_sim/content/claude_adapter.py:71-80` (pre-fix) | R2-LLMCACHE's report claimed the blocked-cache-bypass bug was fixed, and it was — but only in `llm_adapter.py`. `claude_adapter.py` is a separate, live, tested, first-class content mode (`content_mode="claude"`, wired in `engine.py`, `VALID_CONTENT_MODES`, `examples/quickstart.py`) implementing the *identical* caching pattern, and its `generate()` still did `text = cached.get("text") if isinstance(cached, dict) else cached` with zero check of `status` — a second identical request under Claude mode would leak a previously blocked LLM response verbatim. Zero tests covered blocked/legacy/CN-label cache-hit behavior for `ClaudeAdapter` before this fix (only cache-key-uniqueness and no-key-fallback were tested — see old Q-CLAUDE row above, a different issue) | Extracted the cache-trust decision into a new shared module `socio_sim/content/llm_cache.py` (`resolve()`, `make_entry()`, `load()`/`save()`/`file_hash()`) so `LLMAdapter` and `ClaudeAdapter` share one code path and cannot drift out of sync on this safety-critical logic again | 24 new tests: 14 direct unit tests of `llm_cache.resolve()` (`tests/test_llm_cache.py`) + a full mirror of the blocked/accepted/legacy/CN-label/deterministic-replay/tamper scenario matrix added to `tests/test_content.py` for `ClaudeAdapter` (previously had none of it) + 3 new tamper/corrupt-file tests added to `tests/test_llm_adapter.py` | **DONE** (`fc625fc`) |
| R12-CACHETAMPER | P1 | `socio_sim/content/llm_cache.py` (new) | The spec's "tampered cache data" regression scenario (poisoned/hand-edited cache entries — e.g. flipping a blocked entry's `status` to `accepted` while leaving the bad text in place) had no coverage or protection in either adapter; `semantic_hash` was written to every entry but never verified on read | Added `record_hash` binding `(text, status, reason_codes)` together, verified on every cache read; a mismatch, or a `status` value outside `{accepted, blocked}`, is treated as tampered/corrupt and discarded (treated as a cache miss, forcing fresh regeneration + re-screening) rather than served. Documented as a plain integrity check, not a defense against a filesystem-level adversary who also recomputes the hash — that threat model doesn't apply to a local single-user tool. Corrupt/non-JSON cache files now fail safe to an empty cache (`llm_cache.load(..., on_error=...)`) instead of crashing adapter construction | `test_tampered_record_hash_is_discarded_as_a_miss`, `test_tampered_text_is_discarded_as_a_miss`, `test_unknown_status_value_is_discarded_as_a_miss`, `test_load_corrupt_json_returns_empty_dict_and_reports` (`tests/test_llm_cache.py`) + adapter-level mirrors in both `test_llm_adapter.py` and `test_content.py` | **DONE** (`fc625fc`) |

Both fixes verified CI-green from a clean checkout (not just locally) before
being reported: `gh run watch` on runs `28560638302` (push) and `28560638906`
(pull_request), both `completed success`, all 13 named steps green,
`gh pr checks 5` -> `test pass` ×2.

## Session 2026-07-09: headless Fable fix-loop left HEAD broken + uncommitted; full 0159-audit remediation (18/20 findings)

Between 2026-07-02 and 07-03 a headless orchestration loop (`claude.exe
--model claude-fable-5 -p` driven by root-level `.vbs`/`.ps1` scripts) ran a
Fable audit (`docs/audits/fable_audit_20260703_0159.md`, 20 findings
A-01..H-03) and attempted fixes via one-shot subprocess prompts. Outcome
found this session, and the reason that workflow is now retired in favor of
in-session TDD: the fix commits were unreliable — `283dff9` ("all fixes
applied") actually *reverted* the H-01 evidence_gate hunk; HEAD's
`llm_cache.py` was truncated mid-token (unimportable — the whole suite was
red at HEAD); the real fix code sat uncommitted in the working tree with 4
failing tests; and three stale `.git/*.lock` files from crashed runs blocked
all commits. The prior commit trail (c71d02e..283dff9) also whole-file
rewrote line endings, making diffs unreadable.

This session: consolidated + verified the working tree (`0985a9b`), then
closed the 0159 findings with test-first fixes, one verified commit per
group. 328 -> 358 tests.

| ID | Sev | Fix | Status |
|----|-----|-----|--------|
| E-01 accepted-entry guard-versioning gap (P1) | P1 | `make_entry` stamps `guard_version` on every entry (both adapters inherit — no per-adapter code to drift); accepted path in `resolve()` misses on stale/absent version | **DONE** (`ae3ad4a`) |
| E-02 docstring said legacy entries "trusted as accepted" | P3 | docstring matches safe code; pinned by test | **DONE** (`ae3ad4a`) |
| E-03 guard_version outside tamper envelope; dead `semantic_hash` | P3 | `record_hash` binds guard_version (old-formula entries verify then miss cleanly); dead field removed | **DONE** (`ae3ad4a`) |
| E-04 blocked-success didn't reset `_fail_streak` | P3 | reset on guard-blocked transport success | **DONE** (`ae3ad4a`) |
| H-02 evidence gate silently skipped missing sha256/file (P1) | P1 | fail-closed: both are hard errors | **DONE** (`9c5c994`) |
| F-01 whole-second `out_dir` collision corrupts audit artifacts | P2 | uuid suffix | **DONE** (`394b994`) |
| F-03 `/api/job` iterated live dict while workers inserted keys | P3 | `_job_set()` under `_LOCK` + locked snapshot reader | **DONE** (`394b994`) |
| C-01 "95%" label on 2-replicate percentile range | P2 | `N=<n>` label below 20 replicates (web UI already honest) | **DONE** (`394b994`) |
| C-02 CLI printed target table the web suppresses | P2 | shared `evidence.targets_metadata_complete` gate + CLI suppression notice | **DONE** (`394b994`) |
| A-04 unlabeled cutoff 3.0 | P3 | 3-sigma convention cited | **DONE** (`394b994`) |
| F-02 IPv6 `[::1]` Host rejected | P3 | bracket-aware parse | **DONE** (`ae70ce0`) |
| F-04 cleartext-token risk unstated | P3 | RuntimeError + warning name cleartext HTTP / TLS proxy | **DONE** (`ae70ce0`) |
| H-03 registry.json served as octet-stream | P3 | `.json` content type | **DONE** (`ae70ce0`) |
| D-01 lift/p-values emitted with holdout<=0 | P2 | rejected when ads enabled | **DONE** (`ae70ce0`) |
| A-05 profile scales hand-copied in 3 places | P2 | `_profile_scales()` derived from RunConfig factories, shared with /api/meta | **DONE** (`ae70ce0`) |
| G-01 no alt-text enforcement | P2 | evidence_gate requires `accessibility_alt_template` (all 92 real assets carry one; UI already renders alt) | **DONE** (`ae70ce0`) |
| B-01 CLI asserted "licensed" bare | P3 | cites docs/DATA_MANIFEST.md | **DONE** (`ae70ce0`) |
| B-02 scanner missing achieves/outperforms/accuracy | P3 | added + "Reviewer accuracy" input-label exemption | **DONE** (`ae70ce0`) |
| C-03 report gate was a 2-phrase list | P3 | reuses claim_scan vocabulary + hedge logic | **DONE** (`ae70ce0`) |
| A-01/A-02/A-03 unlabeled scenario constants | P2 | named constants + per-field campaign `economics_provenance` + `/api/meta` `defaults_provenance` | **DONE** (`b76de4f`) |
| H-01 (0159) `web_path` split-before-normalize | P2 | `_asset_web_path` normalizes first, skips marker-less records; found by this session's code-review pass (the earlier "H-01" commit fixed a *different* audit generation's H-01) | **DONE** (`5e87bc5`) |
| E-05 DNS-rebind TOCTOU (validate-then-urlopen second lookup) | P3 | `validate_llm_url` now returns the exact IP it checked; the transport TCP-connects to that pinned IP via `_PinnedHTTP(S)Connection` (hostname kept for Host header + TLS SNI), replacing urllib entirely — no second DNS lookup exists to rebind, and any 3xx is a hard error. +3 tests (pinned dial captured; rebound resolver never dialed; real-server 302 refused) | **DONE** (session 2026-07-10) |
| G-02 no automated a11y (axe-core) gate in CI | P3 | `tests/test_a11y_axe.py` (axe-playwright-python, new `e2e` extra dep) scans the initial AND rendered dashboard views under prefers-reduced-motion, failing on any serious/critical WCAG 2.0/2.1 A+AA violation; wired as its own CI step. The first run caught 5 REAL light-theme contrast defects (version badge 1.43:1, run-button white-on-#0a84ff 3.64:1, run-button subtitle w/ opacity stacking-context 1.07:1, checked-chip + slider-value same pattern, lens-badge green 4.35:1) — all fixed in style.css. Scan ≠ WCAG-AA conformance claim (disclosed in KNOWN_LIMITATIONS.md) | **DONE** (session 2026-07-10) |

Post-remediation verification: 358 passed, ruff clean, claim_scan /
evidence_gate / secret_scan all pass; independent code-review agent pass on
the six fix commits found zero >=80-confidence issues and confirmed the
determinism and blocked-cache invariants; security review of the branch diff
returned an empty report (all deltas tighten posture).

## Determinism baselines (locked pre-refactor)
- test/EU: `a8a8b243e5958c1620d5e4ed0e9bee55c866c78d4459993c57eeca3bf848bc36`
- test/US: `f7473dc24c1ff189045e807f7f1e8798ed2416a5bf43020ca8f2344edbd27190`
- test/CN: `3f3c6f2bb509e64e69ea5f7cbf716a078932bc8e5c73d137afa9db785cb8cd14`
Baseline suite: 108 tests passing at branch point.
