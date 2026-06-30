# P2 Remediation Plan — SocioSim

Generated: 2026-06-27  
Branch: feat/audit-p0-p1  
Starting state: 11/11 release-gate checks passed (0 failed, 2 skipped).

---

## Context

The P0/P1 sprint is complete. The 2 skipped checks are:

- **Docker build** — `docker` binary not present in this dev environment  
  (checked in `verify_release.py` via `optional_tool_check`)
- **pip-audit availability** — `pip_audit` module not installed  
  (checked via `optional_python_module_check`)

Both are correct "not installed here" skips, not failures. The gate
rule is `return 1 if any(c.status == "failed")` — skipped does not break it.
P2 work must not turn either of these into a `failed` status locally.

---

## Items and Scope

### P2-A · Docker hardening (Dockerfile)

**Current state (`Dockerfile`):**
```
FROM python:3.11-slim
RUN pip install -e .
```
- No pinned digest → image is mutable; a `docker pull` after a registry update
  silently changes the base.
- Process runs as root inside the container.
- No SBOM generation step documented.

**Required changes:**
1. Pin base image to its SHA256 digest: `python:3.11-slim@sha256:<digest>`.
2. Add `adduser --disabled-password --gecos '' appuser && chown -R appuser /app`
   and `USER appuser` before the CMD so the process is non-root.
3. Document SBOM generation via `syft` in a comment (or a `make sbom` target).
   We cannot run `syft` in this environment; we document the invocation and add
   a CI comment. Actual SBOM generation is deferred to the release pipeline.

**Files touched:** `Dockerfile` only.  
**Gate impact:** Docker check remains `skipped` locally (no docker binary). CI
ubuntu-latest runner has docker, so this will move to `passed` there.

---

### P2-B · pip-audit + Bandit security scanning + CI integration

**Current state:**
- `pip_audit` not installed → release gate shows `skipped`.
- `bandit` not referenced anywhere.
- `.github/workflows/ci.yml` has no security scan step.

**Required changes:**
1. Add `pip-audit` and `bandit` to `pyproject.toml` `[project.optional-dependencies]`
   under a new `security` extra.
2. Add a `bandit` CI step in `ci.yml` scanning `socio_sim/` with `-ll` severity
   filter (low confidence skipped — reduces noise on research code).
3. Add a `pip-audit` CI step. Use `--skip-editable` so the local editable install
   doesn't block the check when a CVE list cannot be fetched offline.
4. Fix any Bandit medium/high-severity findings (expected: subprocess calls in
   `llm_bootstrap.py`, URL construction in `llm_adapter.py` — may need `# nosec`
   annotations with justification comments).
5. Update `verify_release.py` to add Bandit as an `optional_python_module_check`
   (so it is `skipped` gracefully if not installed, not `failed`).

**Files touched:** `Dockerfile`, `pyproject.toml`, `.github/workflows/ci.yml`,
`scripts/verify_release.py`, possibly `socio_sim/llm_bootstrap.py`,
`socio_sim/security.py`.

**Gate impact:** `pip-audit availability` stays `skipped` until the module is
installed in the verification environment. The Bandit check will be `skipped`
too when not installed. Neither introduces new `failed` states.

---

### P2-C · SOURCE_LEDGER.md refresh

**Current state:** The ledger is authoritative on regulatory/policy citations and
quant methodology references, but is missing:
- The LLM adapter safety boundary implementation (`llm_adapter_v2_safety_boundaries`)
- The CUPED + BH-FDR implementations (cited in the ledger by paper but not mapped
  to their module/function locations)
- The incrementality/ghost-ads design (mentioned in `HANDOFF.md` as coming from
  research agents, but not in the ledger)
- Axe/accessibility tools (to be added during P2-E)
- pip-audit / Bandit references (to be added during P2-B)

**Required changes:** Update `SOURCE_LEDGER.md` to:
1. Add an "Implemented methods map" section that maps each method to its file:function.
2. Add the LLM safety-boundary spec entry (prompt-version `llm_adapter_v2_safety_boundaries`).
3. Refresh calibration dataset citations with what is actually bundled.
4. Add dependency-scan tool references (pip-audit, Bandit) once integrated.

**Files touched:** `SOURCE_LEDGER.md`.  
**Gate impact:** None (documentation only; claim-language scan checks `docs/`
not `SOURCE_LEDGER.md`).

---

### P2-D · Per-metric provenance extension

**Current state:** `METRIC_PROVENANCE` in `socio_sim/analytics/metrics.py` covers
8 headline metrics:
`n_posts`, `harmful_exposure_rate`, `moderation_precision`, `moderation_recall`,
`appeal_grant_rate`, `welfare_mean`, `ad_ctr`, `ad_lift_itt`, `ad_roas`.

**Missing coverage:**
- Cascade metrics: `n_cascades`, `cascade_mean_size`, `cascade_max_size`
- Fairness diagnostics: `moderation_fpr_by_group`, `moderation_fnr_by_group`
- Graph structural metrics: `degree_mean`, `clustering`, `graph_n`, `graph_m`
- Moderation confusion detail: `fpr`, `fnr`, `tp`, `fp`, `fn`, `tn` counts
- Appeals detail: `mean_resolution_ticks`, `deadline_miss_rate`
- Ad secondary: `ad_spend`, `ad_roi`, `lift_pvalue`, `mde`

**Required changes:**
1. Extend `METRIC_PROVENANCE` in `metrics.py` with entries for all secondary
   metrics currently shown in the UI (Charts, Fairness, Calib, Ads tabs).
2. Expose provenance as a machine-readable field in the JSON export
   (already in `summarize_run` → `"metric_provenance"`; ensure all new entries
   are also in there).
3. Add a test in `tests/test_analytics.py` asserting that every key returned by
   `summarize_run` has a corresponding entry in `METRIC_PROVENANCE` (or that
   `METRIC_PROVENANCE` covers a documented superset).
4. Render the extended provenance table in the web UI's Audit tab (or Log tab)
   so non-report users can see it.

**Files touched:** `socio_sim/analytics/metrics.py`, `tests/test_analytics.py`,
possibly `socio_sim/web/static/app.js`.  
**Gate impact:** New test must pass; coverage must stay ≥ 85%.

---

### P2-E · LLM reclassification and cache-hash replay validation

**Current state:**
- `LLMAdapter` replaces **surface text only**; structural metadata (topic, stance,
  categories) always comes from `TemplateGenerator`. The safety guard
  (`_safe_generated_text`) rejects PII/unsafe phrases but does not re-run the
  moderation classifier against the generated text.
- `LLMAdapter.cache_hash()` computes a SHA-256 of the cache file but there is no
  test that verifies a replay (re-instantiation from the same cache file) produces
  the same hash.

**LLM reclassification (scope is narrow — presentation text only):**
- The requirement is to verify the generated text does not contradict the template
  category. If the template says `topic=climate` and stance is neutral, LLM text
  containing e.g. crude slurs should fail the safety guard.
- Add a `_reclass_check(text, item)` method that runs a lightweight keyword-based
  secondary check: if the item template category is `safe` but the text contains
  known harm keywords (from the existing `_UNSAFE_PHRASES` list + a small extension),
  reject and degrade. This is **not** a full ML re-run; it's a consistency gate.
- Add `reclass_violations` to the LLM call's cache metadata.
- Log mismatches as `degradation` events with a `reclass` reason code.

**Cache-hash replay validation:**
- Add `test_cache_hash_stable_across_instances` to `tests/test_llm_adapter.py`:
  generate items with adapter A → record `cache_hash()` → instantiate adapter B
  from the same cache path → assert `B.cache_hash() == A.cache_hash()`.
- Add `test_cache_hash_changes_on_new_entry` to confirm the hash changes when
  a new entry is added.

**Files touched:** `socio_sim/content/llm_adapter.py`, `tests/test_llm_adapter.py`.  
**Gate impact:** New tests must pass; no change to existing determinism hashes
(LLM mode only affects presentation text, not event-stream hash).

---

### P2-F · Accessibility — axe checks, chart table alternatives, ARIA

**Current state:**
- `tests/test_e2e_playwright.py` has one smoke test (navigates, runs simulation,
  checks for a results heading).
- The HTML has `role="tablist"` on navigation, `aria-label` on theme and close
  buttons, `aria-live` on `#runMeta`, but:
  - Charts (rendered as `<div>` containers with SVG/Canvas) have no `<table>`
    alternatives or `aria-label` on the chart containers.
  - Network and cascade visualizations are canvas/SVG with no screen-reader path.
  - The campaign editor row is `aria-hidden="true"` on its header.
  - The lens-legend `<p>` is `aria-hidden="true"` (deliberate for decorative dots,
    but the text itself is informative).

**Required changes:**
1. **axe-core Playwright check** — Add `axe-playwright` or inline axe-core
   injection to the E2E test. After a run completes, inject axe via
   `page.evaluate(axe_source)` + `page.evaluate("axe.run()")` and assert
   `violations === 0` (excluding known-acceptable rules with documented justification).
2. **Chart table alternatives** — For each chart rendered in the Charts tab,
   add a visually-hidden `<table>` or `<details>/<summary>` alongside with
   the same data in tabular form. Scope: the main time-series charts and the
   calibration chart data. Network/cascade SVG: add `aria-label` on the
   container `<div>` describing the graph data in prose.
3. **ARIA hardening** — Change `aria-hidden` on `.camp-head` to `role="rowheader"`
   or use a proper `<table>` for campaign rows. Fix the lens-legend text to be
   perceivable (remove `aria-hidden="true"` from the informative text span,
   or move the decorative dots to a separate aria-hidden element).
4. **Keyboard navigation** — Verify tab order on results tabs is correct
   (already uses `role="tab"`); confirm graph/cascade container is reachable
   by keyboard with a descriptive label (no hover-only content).

**Files touched:** `socio_sim/web/static/index.html`, `socio_sim/web/static/app.js`,
`tests/test_e2e_playwright.py`.  
**Gate impact:** `UI/browser tests` check must still pass (currently passes 1 test).
New axe check must pass (0 critical/serious violations).

---

## Execution Order and Rationale

| Order | Group | Rationale |
|-------|-------|-----------|
| 1 | P2-B: Security scanning + CI | Must know findings before declaring secure; Bandit is a static scan (no internet needed); quick to run |
| 2 | P2-A: Docker hardening | Pure Dockerfile edit; zero Python changes; no risk to test suite |
| 3 | P2-C: SOURCE_LEDGER.md | Documentation; zero risk; better done before provenance/LLM work so those can reference it |
| 4 | P2-D: Provenance extension | Pure Python analytics change; well-covered test area; adds tests before touching LLM |
| 5 | P2-E: LLM reclassification + cache-hash | Touches LLMAdapter; builds on provenance metadata added in P2-D |
| 6 | P2-F: Accessibility | JavaScript + HTML + Playwright; highest UI risk; done last when Python layer is stable |

---

## Verification Protocol (per group)

After each group:

```
python -m ruff check .
python -m pytest -q tests/test_security.py tests/test_analytics.py tests/test_llm_adapter.py tests/test_web.py tests/test_e2e_playwright.py
python scripts/verify_release.py --quick
```

After all groups:

```
python scripts/verify_release.py
```

The final result must show ≥ 11 passed, 0 failed (skipped is acceptable for
Docker and pip-audit when those tools are absent from the environment).

---

## Non-negotiables

- Do not break determinism: event-stream hash from the smoke test
  (`0a02eb4a6ada07112e32410d7de3af7846deb9c42f22454e376d751e00f8493b`) must be
  unchanged at the end. If any change to the simulation engine is needed, re-lock
  the baseline with a `# DETERMINISM-LOCKED` comment and re-run the smoke.
- Do not reduce test coverage below 85%.
- Every edited `.py` file must pass `ruff check` before commit.
- Commit each group separately (P2-A, P2-B, … P2-F) with a matching message.
