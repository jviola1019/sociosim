# SocioSim Evidence-First Remediation Report

## Addendum (2026-06-30): independent re-verification + P0 fixes

**This addendum is the current source of truth.** Everything below the
`## Summary` heading describes the state of branch `fix/evidence-first-v4-assets`
at the time it was authored and merged as PR #4. That report was **not**
re-verified before merge: GitHub Actions showed `failure` on both the `push`
and `pull_request` triggers for the final commit (runs `28477797199` /
`28477775565`), and PR #4 was merged into `main` anyway. Per this project's
"treat every claim as untrusted until independently verified" mandate, this
session re-ran every check in the original report's Final Verification table
from a clean checkout and found three claims that did not hold, plus
confirmed several others did hold.

Branch for this session: `fix/p0-llm-cache-and-audit-hardening`, based on
`main` at `3e015d0091cac7cb1026fe2dec7487b52012ee79` (i.e. `main` *with* PR #4
already merged in). Python 3.11.9 (local, win32) / 3.11.15 (CI, ubuntu-latest).
Commits: `d8aea1f` (CI fix), `e0a96d4` (P0 LLM cache fix), `8975ee5`
(calibrated-profile fix), `9a9c524` (asset QA allowlist + `.coverage` hygiene).
PR: [#5](https://github.com/jviola1019/sociosim/pull/5).

### Claims in the original report that did NOT hold under re-verification

| # | Original claim | What was actually found | Fix |
|---|---|---|---|
| 1 | CI green ("PASS" on every local check); implicitly fit to merge | GitHub Actions `failure` on the final commit, both triggers. Root cause: the "Tests (pytest + coverage gate)" step ran the full suite — including the Playwright-driven `tests/test_e2e_playwright.py` — *before* any step installed Chromium. A clean runner has no browser cache, so the embedded e2e test failed there; every later gate (asset QA, security scans, license inventory, wheel build) was then skipped. Local dev machines masked this because they already had a Playwright browser cache from earlier sessions. | `d8aea1f`: move `playwright install --with-deps chromium` ahead of the test step; add `tests/test_ci_workflow.py` to lock the ordering. **CI now verified green on PR #5, run `28481398083`, all 13 named steps passed.** |
| 2 | "Added deterministic LLM semantic guard checks for PII-like text... reason-coded cache records, and cache-hash tests" (implies the P0 blocked-cache bypass was fixed) | `socio_sim/content/llm_adapter.py::generate()` cached a blocked LLM response with `status: "blocked"` and correctly served template text on the *first* call — but the cache-hit branch read `cached.get("text")` (the blocked LLM text itself) without checking `status`, and fell straight through to serving it. A second identical request — same adapter instance, or a fresh instance reloading the persisted cache file — served the previously blocked text verbatim, with no guard re-check and no degradation event. No test exercised a second cache hit, so this was untested as well as unfixed. This is the exact P0 regression described in the task brief, still present after the "fix" was claimed complete. | `e0a96d4`: branch on `cached["status"]` before falling through to the read path; a blocked entry always returns the template item, emits a degradation event with the original reason codes, and never re-contacts the LLM for that prompt (a new `_BLOCKED_GUARD_VERSION` constant is the only deliberate invalidation path). 9 new regression tests. |
| 3 | `python scripts/asset_qa.py` → "PASS, 92 records" | Failed (exit 1) when re-run from a clean checkout: the legacy-v3-reference scan's allowlist excluded `scripts/asset_qa.py` and its own report outputs but not `BASELINE_AUDIT_SNAPSHOT.md` (an explicitly historical pre-remediation record that legitimately names the deleted v3 files) or `scripts/claim_scan.py` itself (which must contain those literal strings to detect them). The underlying v3→v4 asset migration was correct; the gate's allowlist was incomplete. | `9a9c524`: widen the allowlist; add an explicit "HISTORICAL RECORD" banner to the snapshot doc. |

A fourth gap was found and fixed as routine hygiene, already flagged (but not
fixed) in the original report's own "Remaining Evidence Gaps" section: the
generated `.coverage` SQLite file was tracked in git, producing spurious
diffs on every local run. Fixed in `9a9c524` (added to `.gitignore`,
untracked).

### Claims independently re-verified as correct

- Public classifier-mode labels are exactly `synthetic_noise_classifier` /
  `synthetic_template_classifier` (`socio_sim/config.py`); legacy `noise` /
  `trained` strings are mapped only inside `RunConfig.from_dict` via
  `LEGACY_CLASSIFIER_MODE_ALIASES`, never accepted as live choices in
  `socio_sim/web/app.py`.
- The evidence-record `kind` taxonomy (`measured` / `external_aggregate` /
  `scenario_assumption` / `synthetic_engineering` / `user_supplied` /
  `unsupported`) exists in `socio_sim/evidence.py` and is schema-checked by
  `scripts/evidence_gate.py`.
- v3 assets are fully deleted from the working tree, package contents, and
  (after fix #3 above) the legacy-reference scan; 92 v4 PNGs are registered
  and pass dimension/CRC/duplicate/orphan checks.

### Confirmed still incomplete against the full task brief (not claimed done; sized for follow-up)

These are real, scoped gaps against the original mega-task, not regressions
introduced this session. None of the prior reports claimed them complete
either, but the brief requires them, so they are recorded here rather than
left implicit:

1. **Evidence registry granularity.** `socio_sim/data/evidence_registry.json`
   has 7 broad-category records (e.g. one `ev.synthetic_engineering.classifier_noise`
   record covers *all* classifier-noise parameters). The brief explicitly
   requires individual provenance per decision-facing numeric default
   (every probability, persona distribution, threshold, timing, campaign
   parameter, graph parameter, etc.) and explicitly forbids "a generic
   assumption record stand[ing] in for dozens of unrelated numeric defaults."
   `scripts/evidence_gate.py` only schema-validates the existing records,
   checks the asset count, and scans for two stale phrases — it does not
   (and cannot, given the current registry shape) enforce per-default
   coverage. This is a large, multi-file mapping exercise, not a quick fix.
2. **Visual system is still procedural, not art-directed.**
   `scripts/generate_v4_assets.py::_art()` generates gradient fields with
   randomly placed rotated ellipses and Gaussian noise — the same
   "algorithmic gradient/ellipse/noise field" pattern the brief explicitly
   names as needing replacement. There are 3 roles (`feed_cover`,
   `ad_creative`, `editorial_system`), not the 8 distinct visual families
   required (network topology, signal-routing diagrams, moderation-workflow
   compositions, community/conversation motifs, campaign-system objects,
   policy/process metaphors, research-lab editorial illustrations,
   accessible data-structure abstractions). Human review remains honestly
   recorded as `not_reviewed`. Replacing this with 96+ deliberately authored,
   non-repetitive compositions across 8 families is a substantial design and
   engineering effort, not attempted this session.
3. **Claim scanner is still a literal blacklist.** `scripts/claim_scan.py`
   checks 10 fixed phrases against all tracked files. The brief calls for a
   context-aware policy (flag unsupported standalone use of "validation",
   "calibrated", "real model", "confidence", "causal", "decision-ready",
   "production", etc., with awareness of explicitly-labeled historical
   documentation). Not attempted this session.
4. **Causal/uncertainty cohort-timeline audit, full accessibility audit
   (axe-core, chart table alternatives, focus trapping), and Docker
   digest-pin/non-root verification** were not re-examined this session —
   recorded as *unverified*, not as confirmed-working or confirmed-broken.
5. The "Remaining Evidence Gaps" items from the original report below this
   addendum still stand except where this addendum says otherwise.

None of the above gaps block the P0 fixes or the CI repair in this PR; they
are scoped as follow-up work, consistent with this being an audited
multi-sprint program rather than a single-session deliverable.

---

# SocioSim Evidence-First Remediation Report (original, PR #4)

Branch: `fix/evidence-first-v4-assets`

Base: `59632c4d5336bfc2920214d84df83b328c529478`

## Summary

Implemented the evidence-first remediation as a claim downgrade. Public runtime
classifier modes are now `synthetic_noise_classifier` and
`synthetic_template_classifier`; legacy `noise` / `trained` strings are accepted
only through manifest/config migration paths. Runtime and report surfaces now
label synthetic outputs, metric provenance, validation-ladder limits, ad
measurement timing, and v4 synthetic decorative assets.

## Major Changes

- Added typed evidence infrastructure in `socio_sim/evidence.py`,
  `socio_sim/data/evidence_registry.json`, and
  `socio_sim/data/scenario_assumptions.json`.
- Added metric provenance to summaries, reports, and web payloads.
- Refactored classifier benchmark reporting with source hashes, split
  provenance, normalized duplicate leakage checks, bootstrap intervals,
  reliability data, threshold sweeps, and component-only wording.
- Renamed ad CUPED output to
  `oracle_covariate_adjusted_simulation_diagnostic` and added assignment,
  eligibility, and observation timing fields.
- Added deterministic LLM semantic guard checks for PII-like text, topic/category
  contradictions, unsafe placeholder terms, reason-coded cache records, and
  cache-hash tests.
- Replaced v3 image assets with 92 deterministic v4 PNG assets: 48 feed covers,
  32 ad creatives, 12 editorial/system visuals, plus registry and contact sheet.
- Removed v3 asset references from active code, package contents, and tests.
- Added security/reproducibility gates: pinned Docker base digest, non-root user,
  Bandit, pip-audit, secret scan, license inventory, evidence gate, claim scan,
  asset QA, and wheel content checks.

## Deleted Assets

- `feed-atlas-v3.png`
- `ad-atlas-v3.png`
- `feed-cover-v3-00.png` through `feed-cover-v3-11.png`
- `ad-creative-v3-00.png` through `ad-creative-v3-11.png`

## New Files

- `BASELINE_AUDIT_SNAPSHOT.md`
- `AUDIT_REMEDIATION_REPORT.md`
- `docs/ASSET_QA.md`
- `scripts/asset_qa.py`
- `scripts/claim_scan.py`
- `scripts/evidence_gate.py`
- `scripts/generate_v4_assets.py`
- `scripts/license_inventory.py`
- `scripts/secret_scan.py`
- `socio_sim/evidence.py`
- `socio_sim/content/semantic_guard.py`
- `socio_sim/data/evidence_registry.json`
- `socio_sim/data/scenario_assumptions.json`
- `socio_sim/web/static/assets/v4/*`
- `tests/test_asset_v4.py`
- `tests/test_evidence.py`

## Final Verification

| Check | Result |
|---|---|
| `python -m ruff check socio_sim tests run.py scripts examples` | PASS |
| `python -m pytest -q` | PASS, 277 tests |
| `python -m pytest --cov=socio_sim --cov-report=term-missing --cov-fail-under=80` | PASS, 277 tests, 92.76% coverage |
| `python -m pytest -q tests/test_e2e_playwright.py` | PASS |
| `python run.py --measure-classifier` | PASS |
| `python run.py --validate --profile test --sens-samples 8` | PASS |
| `python run.py --backtest` | PASS |
| `python scripts/asset_qa.py` | PASS, 92 records |
| `python scripts/evidence_gate.py` | PASS |
| `python scripts/claim_scan.py` | PASS |
| `python scripts/secret_scan.py` | PASS |
| `python -m bandit -q -r socio_sim` | PASS |
| `python -m pip_audit` | PASS, no known vulnerabilities found; skipped local/unpublished packages `mlb-show-terminal` and `socio-sim` |
| `python scripts/license_inventory.py` | PASS, wrote 94-package inventory |
| `python -m build --wheel C:\Users\jviol\Downloads\socio_sim` | PASS |
| wheel content inspection | PASS, no v3 paths, 48 feed v4, 32 ad v4, 12 editorial v4, evidence registries present |

## Final Artifact Hashes

| Artifact | SHA-256 |
|---|---|
| `BENCHMARK_REPORT.md` | `357f6a9ffda08c17610621f55a50a465693f1d5b25e17e02d6f55471d0fc93b6` |
| `BACKTEST_REPORT.md` | `9742476b4ae26917b663e5c0a29e9f09006d41938c4c61419431b505f50ef3b1` |
| `VALIDATION_REPORT.md` | `4a242884a8d803ca91f01d59db0050c7bfee9179e4fac6be697569aa7a4bb64a` |
| `socio_sim/data/evidence_registry.json` | `3af882a272d02348b4cf3a8dac8b93437577921f119aca210b2e1bb99eab3579` |
| `socio_sim/data/scenario_assumptions.json` | `f8ff1514c18ea539dd9150a103b6fb1d619941f6c7419eb9721a4f25b0f0f09f` |
| `socio_sim/web/static/assets/v4/registry.json` | `92c795821744a26aeeac8ab64724b5dcc57c724c751851c46ba614178e7bd09e` |
| `dist/socio_sim-0.1.0-py3-none-any.whl` | `7cca1b40a95d3c15b2a1c66609ee4aa8fa95d412b03477bee8c9218eb669b122` |
| `out/license_inventory.json` | `c0a006cd4804604d2fa040694706633e1d7fe1125c5f498b778ccaad10ae231d` |

## Asset QA

- Registry records: 92
- Roles: 48 `feed_cover`, 32 `ad_creative`, 12 `editorial_system`
- Contact sheet: `socio_sim/web/static/assets/v4/contact-sheet-v4.png`
- Human visual review: not claimed
- Metadata/duplicate screening: automated only

## Leakage And Benchmark Results

- Civil Comments component benchmark: F1 `0.731`, ROC-AUC `0.821`, leakage
  check `pass`, source hash recorded.
- Spam Detection component benchmark: F1 `0.989`, ROC-AUC `1.000`, leakage
  check `pass`, source hash recorded.
- These are component diagnostics only and do not validate runtime classifier
  deployment.

## Remaining Evidence Gaps

- Legacy aggregate target manifests still lack complete source version, date
  range, population, unit, source hash, and tolerance-rationale metadata.
- No external temporal holdout, external platform holdout, operational
  validation, or lawful real-deployable runtime classifier artifact is present.
- V4 visual QA is automated; no human-review claim is made.
- `.coverage` is a tracked generated artifact and was modified by the local
  coverage run.

## Operational Limits

SocioSim remains research-use-only synthetic scenario software. Outputs must not
be used to target or rank real individuals, predict real events, make
enforcement decisions, claim real-platform performance, or justify operational
campaign spend.
