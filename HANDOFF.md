# SocioSim Handoff

This is an evidence-first remediation program, on branch
`fix/p0-llm-cache-and-audit-hardening` (PR #5, open against `main`, CI green).
Current boundaries:

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
  and never triggers a new remote call (see `llm_adapter.py::generate`).

**Read `AUDIT_REMEDIATION_REPORT.md`'s addendum first**, then `AUDIT_LOG.md`'s
two dated session sections. Do not assume anything in this repo is done
because a prior report says so — re-run the check.

## Session 2026-06-30 (part 2): R6 + R9 done, R7/R8 next

Picked up the "Confirmed still incomplete" list from the addendum. Completed
**R6** (evidence-registry granularity — see `AUDIT_LOG.md` R6-EVIDENCEGRAIN)
and, as a finding made while doing that work, **R9** (target-distance UI
overclaim + two unsourced "realistic" claims — see R9-OVERCLAIM). Both are
committed and gate-clean locally (ruff, full pytest+coverage, evidence_gate,
claim_scan, secret_scan, bandit all pass); not yet pushed/CI-verified as of
writing this note — **do that before claiming this segment done** (see
[[verify-and-replan-each-sprint-segment]] discipline: verify, then commit,
then re-plan, every segment).

**Still open, in priority order for the next segment:**

1. **R8-CLAIMSCAN (P2, small, do first — cheap and well-scoped).**
   `scripts/claim_scan.py` is a 10-phrase literal blacklist scanning all
   tracked files. Brief requires a context-aware policy: flag unsupported
   *standalone* use of "validation", "calibrated", "trained/production model", "confidence",
   "causal", "decision-ready", "production", etc. (not just exact stale
   phrases), with an allowance for documentation explicitly labeled
   historical (the pattern `BASELINE_AUDIT_SNAPSHOT.md` now uses — see its
   "HISTORICAL RECORD" banner). Suggested approach: per-term regex with a
   small set of "defensible nearby words" (e.g. "validation" is fine next to
   "not a validation" / "no validation claim", flag it otherwise), tested
   against fixtures of both true positives and known-fine sentences pulled
   from the current docs so the scanner doesn't immediately fail on the
   honest disclaimers that are already correct.

2. **R7-ASSETART (P1, large — budget a dedicated segment, don't rush it
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
   not a mechanical fix — recommend scoping it as its own session with a
   short art-direction spec written first (palette, composition grammar per
   family, what makes two assets "distinct" enough) before generating files,
   so QA isn't checking 96 assets against vague criteria after the fact.

3. **Deferred from R9, not yet sized:** full rename of backend
   `implausibility`/`calibration_implausibility` identifiers (function names,
   dataclass fields, report sections) — ~15+ call sites across
   `pipeline.py`, `validation/calibrate.py`, `validation/study.py`,
   `validation/backtest.py`, and their tests. The user-facing surface (tab
   label, UI text) is already fixed; this is the deeper, riskier rename of
   Python identifiers and `CALIBRATION_REPORT.md`'s naming, left alone this
   session to avoid rushing a wide-blast-radius refactor.

4. **Deferred from R6, not yet sized:** real source URLs/DOIs/retrieval
   dates for the 7×3 benchmark-target citations in
   `socio_sim/data/benchmarks/*.json` (each target already has a one-line
   citation but not the full required metadata schema — source URL, version,
   retrieved_at, license, population, geography, date range, methodology,
   applicability limits). Needs an explicit WebSearch-backed research pass to
   avoid fabricating URLs from memory, not a code change.

5. Causal/uncertainty cohort-timeline audit and full accessibility (axe-core)
   audit are still unverified this program (never claimed done, never
   examined either way).
