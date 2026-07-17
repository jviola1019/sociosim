# SocioSim Handoff

## Context-Reset Packet — 2026-07-16 SPRINT 12 (markets/UX/coherence, from main @ e7ca1f9, branch feat/sprint12-markets-ux)

- **Objective (user directive):** fix Campaigns spacing; NAMED markets with
  honest sourced anchors; tooltips on every setting; full synthetic
  settings sweep with printed docs; persona sandbox testing (marketing +
  government first-time users); rate limiting; repo file audit/pruning;
  graphs/ADA; ship only after GitHub CI green.
- **Done & verified:** PR #8 merged (main e7ca1f9; exact-SHA push run
  29548709876 success, ledger row added). socio_sim/ads/markets.py — 8
  named content markets + 9 iPinYou-sourced advertiser verticals (Tables
  2+3 of the hash-pinned artifact; anchors recorded as
  sourced_vertical_anchor provenance). Campaign editor rebuilt as labeled
  cards (fixed class-collision bug found by persona test). 34 tooltips
  added. Settings sweep: 76/76 cases coherent + 5/5 directional checks
  (docs/SETTINGS_SWEEP.md); found+fixed engine int-coercion crash
  (exploration_pool_size float) and ITT-lift NaN poisoning in
  _headline_metrics. 4 persona flows green. POST rate limiter (60/min,
  burst 20, 429) + SECURITY.md control #9 + RLS N/A restated. Repo audit
  subagent: 286 tracked files; removed asset_contactsheet_review.py +
  docs/ASSET_MANIFEST.md. Feed cards: real Day/HH:00 timestamps; ad cards
  "Sponsored" chip; NO fabricated engagement counts (honesty).
- **Constraint honoured:** no per-industry "benchmark" tables from
  commercial aggregators (non-auditable — rejected in the 2026-07-13
  pass); iPinYou is the only citable per-vertical CTR source and its
  limits are stated everywhere it surfaces.
- **Not done / next:** run full pytest+coverage suite, commit increments,
  push branch, PR, verify CI green on head + merge SHAs; update the
  RELEASE ledger for the next merge in the following cycle.

## Context-Reset Packet — 2026-07-16 material-audit remediation (from main @ 86bb4b7)

- **Objective:** remediate the 2026-07-16 material audit (exact-SHA CI proof;
  multi-seed validity of the aggregate profile; reproducible source
  verification; supply-chain pinning; cache regression tests; UI honesty +
  a11y).
- **Done & verified:** (1) exact SHA 86bb4b7 has a successful push CI run
  29398446514 (headSha equal; recorded in docs/RELEASE.md ledger);
  (2) seed-generalization protocol built + full 60-seed replay-verified
  evaluation run twice with identical results — holdout 12/20 = 60% pass
  (needs >=80%), so the profile label is DOWNGRADED to "seed-42 aggregate
  demonstration profile" across config/docs/UI, artifact committed at
  socio_sim/data/seed_protocol_results_v1.json, honesty coupled by tests;
  (3) all 7 sourced targets carry source_artifact hashes; verify_sources.py
  re-verified them over the network; evidence gate now rejects unreproducible
  source-verified claims; (4) Syft pinned v1.48.0 + checksum, actions pinned
  by full SHA, mutable-ref/pipe-to-shell CI guard tests; (5) cache gap tests
  (ClaudeAdapter adoption, win32 lock, lock-file secrets, byte-identical
  winner); (6) web UI: real cm profile fidelity, status-hierarchy chips,
  per-target provenance drawers, a11y fixes — Playwright-verified with
  screenshots; axe/e2e suites green.
- **Confirmed facts:** protocol evaluation is deterministic across re-runs;
  appeal_grant_rate (30% of holdout seeds) and ad_ctr are the failing terms
  (small-count rates), structural metrics stable.
- **Open risks / not-yet-done:** verdict remains PASS FOR LOCAL SYNTHETIC
  RESEARCH USE ONLY; making the profile genuinely pass holdout needs larger
  runs or mechanism work on appeals/ad counts (do NOT widen tolerances);
  Windows lock test runs only on win32 dev machines (CI gap documented);
  Mislove/AB587/Pew artifacts are mutable-hosted (hash valid at retrieval;
  quote-verification fallback).
- **Next target:** push to main via PR, confirm exact-SHA CI green for the
  new merge commit, add its row to the RELEASE.md ledger.

This is an evidence-first remediation program, on branch
`fix/p0-llm-cache-and-audit-hardening` (PR #5, open against `main`, CI green
at `fc625fc` — confirmed via `gh run watch` on both the push and
pull_request runs, not just locally). Current boundaries:

- Runtime classifier modes are synthetic mechanics modes.
- Built-in defaults are scenario assumptions unless a user supplies evidence,
  and (as of R6) every decision-facing numeric default that can be
  mechanically introspected (BehaviorParams, category_base_rates,
  classifier_targets, Campaign fields) has its own
  `scenario_assumptions.json` entry; a CI-wired check
  (`evidence.missing_numeric_default_provenance`) fails if a new numeric
  default is added without one.
- Legacy aggregate targets are aggregate-fit diagnostics only, and (as of R9)
  the UI will not show a pass/fail seal or "closer to published benchmarks"
  claim for them while their evidence record is `kind=unsupported` — it shows
  a plain "Unsupported legacy target comparison" instead. This auto-resumes
  normal display if a fully-sourced target set is ever added (see
  `_targets_metadata_complete` in `web/app.py`).
- v4 dashboard images are synthetic decorative artwork, not visual evidence.
- Advertising outputs are synthetic diagnostics and assumption-ledger rows, not
  recommendations.
- "calibrated" is not a publicly selectable profile; it migrates to
  `aggregate_matched_prototype` only through `_migrate_legacy_profile`.
- A cached LLM response with `status: "blocked"` is never served as content
  and never triggers a new remote call, **for both `LLMAdapter` and
  `ClaudeAdapter`** — this was only true for `LLMAdapter` until session
  2026-07-02 found `ClaudeAdapter` still had the identical bug (see
  `AUDIT_LOG.md` "R2-LLMCACHE was incomplete"). Both now share one trust
  decision via `socio_sim/content/llm_cache.py::resolve()`.
- Cache entries are tamper-evident: a `record_hash` binds `(text, status,
  reason_codes)` together; a mismatch or an unrecognized `status` value is
  discarded as untrustworthy rather than served (see `AUDIT_LOG.md`
  R12-CACHETAMPER). This is a plain integrity check, not a defense against
  an adversary who can also recompute the hash — see `llm_cache.py`'s
  docstring for the explicit scope boundary.
- (as of R8) `scripts/claim_scan.py` is a real context-aware scanner, not a
  10-phrase blacklist — see below and `AUDIT_LOG.md` R8-CLAIMSCAN. **R8 was
  originally pushed with CI red** (its own test fixture tripped its own
  scanner — see `AUDIT_LOG.md` R11-CISELFFLAG); fixed and CI-reverified
  2026-07-02.

**Read `AUDIT_REMEDIATION_REPORT.md`'s addendum first**, then `AUDIT_LOG.md`'s
dated session sections in order. Do not assume anything in this repo is done
because a prior report says so — re-run the check. This is not hypothetical:
R8 was pushed with CI genuinely red, and R2-LLMCACHE's "DONE" status was true
for one of two adapters implementing the same logic and false for the other,
both caught only by re-running gates from a clean checkout rather than
trusting the written record (see [[sociosim-audit-reports-overclaim-reverify]]).

## Session 2026-07-09: headless fix-loop cleaned up; 0159 Fable audit remediated (18/20)

A between-sessions headless loop (root-level `run_fable_*.vbs`/`.ps1`
scripts driving `claude.exe -p`) had left this branch in a broken state:
HEAD unimportable (truncated `llm_cache.py`), a commit titled "all fixes
applied" that reverted a fix, the real fixes uncommitted with 4 failing
tests, and stale `.git/*.lock` files blocking commits. That workflow is
retired; full forensic account in `AUDIT_LOG.md` "Session 2026-07-09".

This session consolidated the working tree (`0985a9b`) and remediated the
`docs/audits/fable_audit_20260703_0159.md` findings test-first, one
verified commit per group (`ae3ad4a`, `9c5c994`, `394b994`, `ae70ce0`,
`b76de4f`, `5e87bc5`): E-01..E-04 cache trust model (guard_version on
accepted entries — the P1), H-02 fail-closed evidence gate (P1), F-01
out_dir uuid, F-03 locked job mutations, C-01/C-02/A-04 CLI honesty
(shared `evidence.targets_metadata_complete`), F-02 IPv6 Host, F-04
cleartext-token warnings, H-03 .json content type, D-01 holdout>0 with
ads, A-05 factory-derived profile scales, G-01 alt-template gate, B-01/
B-02/C-03 claim-scanner upgrades, A-01..A-03 scenario-assumption
constants + per-field campaign `economics_provenance`, H-01(0159)
`web_path` backslash fix. E-05 (DNS pinning) and G-02 (axe-core CI) were
deferred with rationale, then **closed on 2026-07-10 (20/20)**: E-05 by
pinning the validated IP (`validate_llm_url` returns it;
`_PinnedHTTP(S)Connection` dials it with the hostname kept for Host/SNI;
urllib removed from the transport; 3xx = hard error) and G-02 by an
axe-core CI gate (`tests/test_a11y_axe.py`, axe-playwright-python in the
e2e extra) that immediately caught 5 real light-theme contrast defects,
fixed in style.css. Suite 328 -> 364 (e2e + a11y now run locally too —
Chromium installed); every commit preceded by full green gates.
Independent code-review agent + branch security review both clean.

**R7-ASSETART CLOSED (2026-07-10):** the generator was rewritten around 8
named art-directed composition systems (strata, orbits, lattice, currents,
terrace, halftone, prisms, archipelago — palette + motif grammar each),
96 assets total (48 feed / 32 ad / 16 editorial; 12 per family spanning
every role), registry schema v2 with per-asset `family` and
family-specific alt text, and asset_qa now enforces the 8-families×3-roles
contract. Every family was visually inspected; a broken prisms
inside-triangle test (rendering bare gradients — the exact retired
pattern) was caught and fixed. Nothing from the original brief remains
unstarted.

## Session 2026-07-02: fixed CI red (R11) + a real second instance of the P0 (R2/R12)

Before continuing to R7-ASSETART (the item flagged below as the next planned
segment), re-verified this branch's own CI status per project policy and
found the last two pushes both `failure`. Root-caused and fixed (R11), then
while independently re-verifying the R2-LLMCACHE "DONE" claim against the
user's original 8-scenario regression-test requirement, found `ClaudeAdapter`
— a separate, live, tested content mode — still had the exact same
blocked-cache-bypass bug, plus a genuine gap in both adapters for the
"tampered cache data" scenario. Fixed both (R2-completion + R12), extracting
shared trust logic into `llm_cache.py` so the two adapters can't diverge on
this again. 24 new tests; full suite 324 passed, 0 failed; ruff/evidence_gate/
claim_scan/secret_scan/asset_qa/bandit/pip-audit/wheel-build all clean;
CI-verified green on both the push and pull_request runs via `gh run watch`
(not just `gh run list`, which showed a misleadingly stale duration for
several minutes on a run that was in fact progressing normally — cross-check
step timestamps via the GitHub API if `gh run list`'s duration column looks
stuck). See `AUDIT_LOG.md` for full detail.

**R7-ASSETART remains the one large item from the original brief's "confirmed
still incomplete" list; it was not started this session** (this session's
scope was entirely the CI-red fix and the newly-discovered duplicate P0,
which took priority as live, verified defects over the already-sized,
already-planned asset-generation work).

## Session 2026-06-30 (part 2): R6, R9, R8 done. R7 is the one big remaining item.

Picked up the "Confirmed still incomplete" list from the
`AUDIT_REMEDIATION_REPORT.md` addendum. Completed, each verified locally
(ruff, full pytest+coverage, evidence_gate, claim_scan, secret_scan, bandit,
asset_qa all pass) and CI-confirmed on PR #5 unless noted:

- **R6** (evidence-registry granularity) — CI green, run `28483158274`.
- **R9** (target-distance UI overclaim + two unsourced "realistic" claims,
  found while doing R6) — same commit/run as R6.
- **R8** (claim scanner: literal blacklist → context-aware, scoped to
  docs/UI/CLI, with hedge/negation and known-fine-phrase exemptions) — local
  gates pass; **push + CI verification still needed before this is "done"**
  (do that first in the next turn — see
  [[verify-and-replan-each-sprint-segment]]).

**Only one large item left from the original brief's "confirmed still
incomplete" list:**

**R7-ASSETART (P1, large — budget a dedicated segment, don't rush it
alongside other work).** `scripts/generate_v4_assets.py::_art()` is still
procedural gradient+ellipse+noise generation across 3 roles
(`feed_cover`/`ad_creative`/`editorial_system`, 92 assets total). Brief
requires 96+ deliberately authored, non-repetitive compositions across 8
distinct visual families (network topology, signal-routing diagrams,
moderation-workflow compositions, community/conversation motifs,
campaign-system objects, policy/process metaphors, research-lab editorial
illustrations, accessible data-structure abstractions), each with full
asset-record metadata (already have: asset_id, role, dims, sha256,
perceptual_hash, license, alt text; still need: visual_family field,
human-review fields actually filled in once a reviewer exists), plus
role-aware *selection* logic (topic/media-type/campaign-type/policy-
context/content-state — currently `_asset_registry()` in `web/app.py` just
returns flat lists per role with no selection logic at all) and
duplicate-avoidance within a visible page. This is a genuine design effort,
not a mechanical fix — recommend scoping it as its own session with a short
art-direction spec written first (palette, composition grammar per family,
what makes two assets "distinct" enough) before generating files, so QA
isn't checking 96 assets against vague criteria after the fact. Given its
size, this was not started this session; it's the natural next full segment.

**Smaller deferred items — ALL CLOSED 2026-07-10/11** (see `AUDIT_LOG.md`
"Session 2026-07-10/11" for full evidence):

1. Backend `calibration` identifier rename — DONE (`f0d218a`):
   `aggregate_fit_implausibility`, `abc_posterior_propagated_mc`,
   `study["aggregate_fit"]`, `AGGREGATE_FIT_NOTE.md`,
   `tests/test_aggregate_fit_profile.py`. Methodology names
   (`validation/calibrate.py`, `expected_calibration_error`) deliberately
   kept — they name real techniques/metrics, not claims.
2. Benchmark citation research pass — DONE (`062419c`), web-verified
   identifiers only (5 papers), unnamed range claims explicitly marked
   `unverified_range_claim`; targets remain kind=unsupported.
3. Cohort-timeline causal audit — DONE (`66714cc`): 14 properties verified
   correct, CT-F1..F6 fixed test-first. Accessibility: automated axe gate
   covers light+dark themes + keyboard drawer behaviors; manual scope
   documented in SECURITY.md (no WCAG-AA conformance claim).
4. Docker digest pin + non-root — re-verified 2026-07-11 directly from the
   Dockerfile (sha256-pinned python:3.11-slim; `appuser` nologin; SBOM
   guidance present).
5. P5 LLM token/cost accounting — DONE (`594b062`) within its determinism
   constraint (adapter-side counters; RunResult.llm_usage; never hashed).
6. Stale DEFERRED rows Q-PERF and S3 re-verified against current code and
   closed in the issue ledger.
