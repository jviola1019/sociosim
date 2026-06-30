# 2026-06-29 P2 Completion Audit — Multi-Persona

**Method:** three independent subagents audited the repo cold, each from a different
posture — a senior Python developer, a non-expert end user (policy researcher on
Windows), and a security/DevOps engineer. Read-only; file:line evidence required;
commit messages were NOT trusted.
**Branch:** `feat/audit-p0-p1`
**Scope:** verify completion of the five named remaining P2 items, and whether the
tool is genuinely usable.

---

## Overall Verdict: NONE of the five P2 items are fully complete

The tool is **usable (4/5)** for a newcomer and the underlying engine/security code
is solid, but every one of the five P2 items is **PARTIAL** or **NOT-DONE**. They
remain open work, consistent with the project's own ledger.

| # | P2 item | Status | Why |
|---|---|---|---|
| 1 | LLM reclassification vs. generated surface text | **PARTIAL** | Real text-scoring path exists but is not universally wired |
| 2 | Provenance for **every** secondary UI visualization | **PARTIAL** | Provenance reaches the report, not the dashboard charts |
| 3 | Automated axe/accessibility checks | **NOT-DONE** | Manual ARIA only; no axe engine wired |
| 4 | Dependency/security scanning | **PARTIAL** | Implemented + passing, but enforcement is split/optional |
| 5 | Docker hardening | **PARTIAL** | Good baseline; `.dockerignore`/HEALTHCHECK/CI-build missing |

---

## Evidence per item

### 1 — LLM reclassification (PARTIAL)
- **Genuine text reclassification exists** under `--classifier trained`: the trained
  classifier vectorizes and scores the actual post text, never the injected label
  — `ml_classifier.py:26-30,66-69`, wired at `engine.py:205-206`
  (`predict_scores(item.text)`); deterministic + replay-pinned
  (`ml_classifier.py:21-23`, `engine.py:301-304`).
- **Gaps:** the default `noise` classifier consumes injected `true_categories`
  directly (`classify.py:28-39`) — no text reclassification in default mode. The
  commit-named "reclass guard" (`feat(p2-e)`) is a keyword-leakage filter that only
  fires when `true_categories` is empty (`llm_adapter.py:187-205,198`), not a
  category reclassification. LLM-generated text is **not** routed through the
  trained classifier. `ClaudeAdapter.generate` applies **no** guard at all
  (`claude_adapter.py:72-96`) — inconsistent safety posture vs. the Ollama/OpenAI adapter.

### 2 — Provenance for every secondary visualization (PARTIAL)
- **Has provenance:** `METRIC_PROVENANCE` covers secondary metrics
  (`metrics.py:119-225`), attached at `metrics.py:499`, rendered in the **markdown
  report** table (`report.py:61-71`); MC/compare series are labelled in the UI
  (`app.js:762-763`, `app.py:588`).
- **Missing:** the **dashboard charts carry no provenance badge** — `_chart_data`
  emits diurnal/degree/timeline/cascade series with no provenance field
  (`app.py:384-422`), and `renderCharts` never reads `summary.metric_provenance`
  (`app.js:579-592`); network 3D, cascade replay, and fairness/confusion likewise
  unlabelled. So "every secondary visualization" is not met.

### 3 — Automated axe/accessibility (NOT-DONE)
- No axe dependency anywhere (`pyproject.toml:19-24`, `requirements.txt`); E2E test
  asserts ARIA attributes manually but never injects axe or asserts 0 violations
  (`tests/test_e2e_playwright.py:177-203`); CI has no axe step (`ci.yml:24-28`).
- Still listed as remaining work in `docs/accessibility.md:11` and `PLAN_P2.md:189-192`.
- **Manual ARIA hardening is real** (tablist/tab, aria-live, SVG `role=img`+labels,
  `<details>` data tables, reduced-motion) — `index.html`, `app.js:568-590` — so the
  broader a11y P2-F work is partially done; only the *automated axe scan* is absent.

### 4 — Dependency/security scanning (PARTIAL)
- Implemented and passing: `[security]` extra (`pyproject.toml:24`), `audit_deps.py`
  (production deps only, `:21,33-37`), invoked by `verify_release.py:222-227`.
- **Enforcement is split:** bandit is a **blocking** CI gate (`ci.yml:34-37`, no
  `continue-on-error`); **pip-audit is advisory only** (`ci.yml:42`,
  `continue-on-error: true`) and production-deps-only. Both are **skippable** in
  `verify_release.py` (import-probe → `skipped`, `:87-113`) and **absent from a
  default `pip install -e .`** (behind the extra). Floor-only pins, no lockfile.

### 5 — Docker hardening (PARTIAL)
- **Present:** digest-pinned slim base (`Dockerfile:16`), non-root `USER appuser`
  (`:27-29`), no secrets, exec-form network-free default CMD (`:32`), in-container
  non-loopback guard honored (`app.py:887-894`).
- **Gaps:** no `.dockerignore` (whole context incl. `out/`/`.git`/`.coverage` sent
  to daemon), no `HEALTHCHECK`, floor-only pins (non-reproducible image), and the
  **build is never exercised in CI** — only in `verify_release.py:221`, which is
  `skipped` when docker is absent.

---

## Usability (end-user, Windows): 4/5

A newcomer can get to a running console; errors surface in a dedicated panel (not
swallowed), controls are labelled with cited tooltips, and outputs carry CI/provenance.
Friction: `docs/usage.md:7` shows `.venv\Scripts\activate` under a ```bash``` fence
(fails in Git Bash); `docs/usage.md:9` uses bare `pytest` (the MS-Store-shim trap,
`python -m pytest` is safer); unquoted `.[dev]`; README coverage figure ("~93%") vs
the 85% gate reads inconsistent.

## Other concrete issues (developer)
- **Dead JS** (out of scope of the earlier Python-only cleanup): `app.js:815` builds
  an unused `table` (only `tableV2` is used at `:831`); `authQuery()` (`app.js:105-107`)
  is leftover dead code from a token-in-URL scheme.
- **Silent failure:** run-history persistence swallows all exceptions
  (`app.py:559-562`, `except Exception: pass` / `# nosec B110`) — a corrupt DB fails
  invisibly every run.
- **Replay diagnostic placeholder:** `replay.py:22` prints `original: ?` (count never threaded through).

---

## Bottom line
The release gate is green and the tool is usable, but the five P2 items are **not
complete** — #3 is not started (automated axe), #1/#2/#4/#5 are partial. The most
user-visible gaps are: provenance badges missing on dashboard charts (#2), no
automated accessibility scan (#3), and pip-audit being advisory/optional rather than
enforced (#4). None block use; all are real, scoped follow-up work.

---

## Resolution (2026-06-29) — all five items completed

The findings above were the *pre-implementation* baseline. All five were then
implemented and verified (301 tests, ruff/bandit/pip-audit clean, axe 0
violations across every dashboard tab):

| # | Item | Status now | Evidence |
|---|------|-----------|----------|
| 1 | LLM reclassification over generated text | **DONE** | `content/_safety.py`: `reclass_violation()` is a real consistency check over the surface text applied to ALL items (not just safe ones); `ClaudeAdapter` now applies the same PII/harm + reclass guards it previously skipped. `feat(p2-1)` |
| 2 | Provenance on every secondary visualization | **DONE** | `_chart_data` emits a per-viz provenance label; `provBadge()` renders it on all four charts + the 3D network + cascade replay + confusion + fairness; E2E asserts the badges. `feat(p2-2)` |
| 3 | Automated axe/accessibility checks | **DONE** | `axe-playwright-python` wired into the Playwright E2E over every tab, asserting zero violations; all real violations fixed (contrast, `h1`, heading order, notice landmark, labelled select, focusable scroll region). `feat(p2-3)` |
| 4 | Dependency/security scanning enforced | **DONE** | bandit + pip-audit folded into `[dev]`; pip-audit step is now blocking in CI (no `continue-on-error`). `feat(p2-4)` |
| 5 | Docker hardening | **DONE** | `.dockerignore` + `HEALTHCHECK` added; a new CI `docker` job builds the image and smoke-runs the CLI, so the Dockerfile is exercised in automation. `feat(p2-5)` |

The dead-JS / silent-failure / replay-message / docs items flagged under "Other
concrete issues" were also fixed (`chore(p2)`). Lower-priority ledger items
Q-REVIEW (P2) and S6 (P3) remain open and were out of scope for this slice.
