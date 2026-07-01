# SocioSim Handoff

This is an evidence-first remediation program, on branch
`fix/p0-llm-cache-and-audit-hardening` (PR #5, open against `main`, CI green
through the R6+R9 commit `6318a2e`; the R8 commit below is pending push+CI
verification as this note is written). Current boundaries:

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
- (as of R8) `scripts/claim_scan.py` is a real context-aware scanner, not a
  10-phrase blacklist — see below and `AUDIT_LOG.md` R8-CLAIMSCAN.

**Read `AUDIT_REMEDIATION_REPORT.md`'s addendum first**, then `AUDIT_LOG.md`'s
dated session sections in order. Do not assume anything in this repo is done
because a prior report says so — re-run the check.

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
