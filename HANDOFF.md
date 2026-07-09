# SocioSim Handoff

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
`web_path` backslash fix. E-05 (DNS pinning) and G-02 (axe-core CI)
deferred with rationale. Suite 328 -> 358; every commit preceded by full
green gates. Independent code-review agent + branch security review both
clean. **NOT yet pushed to origin (19 commits ahead)** — push + `gh run
watch` CI verification is the next step per policy. R7-ASSETART remains
the one large unstarted item from the original brief.

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

**Smaller deferred items, not yet sized/scheduled:**

1. Full rename of backend `implausibility`/`calibration_implausibility`
   identifiers (function names, dataclass fields, report sections) — ~15+
   call sites across `pipeline.py`, `validation/calibrate.py`,
   `validation/study.py`, `validation/backtest.py`, and their tests. The
   user-facing surface (tab label, UI text) is already fixed (R9); this is
   the deeper, riskier rename of Python identifiers and
   `CALIBRATION_REPORT.md`'s naming, deliberately left alone to avoid
   rushing a wide-blast-radius refactor. `run.py:219`'s
   `study['calibration']['implausibility']` dict-key access is explicitly
   claim-scan-exempted pending this rename, not silently ignored — see
   `scripts/claim_scan.py`'s dict-subscript skip.
2. Real source URLs/DOIs/retrieval dates for the 7×3 benchmark-target
   citations in `socio_sim/data/benchmarks/*.json` (each target already has
   a one-line citation but not the full required metadata schema — source
   URL, version, retrieved_at, license, population, geography, date range,
   methodology, applicability limits). Needs an explicit WebSearch-backed
   research pass to avoid fabricating URLs from memory, not a code change.
3. Causal/uncertainty cohort-timeline audit and full accessibility
   (axe-core) audit are still unverified this program (never claimed done,
   never examined either way — genuinely unknown state, not a known gap).
4. Docker base-image digest pin / non-root user verification (listed in the
   original task brief's security section) not re-checked this session.
