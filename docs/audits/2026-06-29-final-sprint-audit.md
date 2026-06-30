# 2026-06-29 Final Sprint Audit — `feat/audit-p0-p1`

**Auditor posture:** end-of-sprint verification across the WHOLE branch (P0/P1
remediation + P2 completion), three independent cold-read personas + the release
gate. Read-only audits; evidence by file:line / commit.
**Branch:** `feat/audit-p0-p1` (17 commits off `main`; ~3.1k insertions / 79 files)
**Python:** 3.11.9 (`.venv`)
**Scope:** every sprint change — not only the latest P2 work — re-verified.

---

## Overall Verdict: PASS — release gate is x/x (14 / 14)

The full release gate passes **14 of 14 checks, 0 failed, 0 skipped**:

```
{"passed": 14}    # failed: 0, skipped: 0, not_implemented: 0, not_applicable: 0
```

301 tests pass at **92.78%** coverage (85% floor), ruff is clean, determinism is
bit-stable, both static security scans (bandit, pip-audit) pass, the accessibility
scan finds **0** axe violations across every dashboard tab, and the Docker check
passes (hardened-Dockerfile static validation locally; full build + smoke-run in
CI). Three independent full-sprint audits (engineering, docs/usability,
security/release) each returned a sound verdict. The two low-severity nits the
engineering audit raised were fixed and re-verified.

---

## Release gate — every check green

| Check | Result | Evidence |
|---|---|---|
| Scenario linting (12 files) | **PASS** | `Scenario lint passed for 12 file(s).` |
| Ruff lint | **PASS** | `All checks passed!` |
| Unit/integration tests + coverage (85% floor) | **PASS** | 301 tests; `Total coverage: 92.78%` |
| Determinism / replay smoke | **PASS** | stream hash stable |
| Policy comparison smoke | **PASS** | US vs EU at test scale |
| Market holdout smoke | **PASS** | `eligible_opportunity_itt` / `scenario_assumption` |
| Validation smoke (`--validate`) | **PASS** | I = 1.67 < 3.0 |
| Backtest smoke (`--backtest`) | **PASS** | held-out `test_pass=True`, I_test=0.78, stylized 5/5 |
| Security / config tests | **PASS** | `tests/test_security.py` |
| Documentation claim-language scan | **PASS** | no banned claim language |
| UI/browser E2E + **axe accessibility** | **PASS** | dashboard renders; **0 axe violations** across all tabs |
| **Docker image** (build in CI; static validation here) | **PASS** | digest-pinned base, non-root USER, HEALTHCHECK, `.dockerignore` |
| **Bandit** static scan (medium/high) | **PASS** | no findings |
| **pip-audit** (production deps) | **PASS** | `No known vulnerabilities found` |

The Docker check is no longer a silent skip: when the `docker` binary is absent
(`scripts/verify_release.py` `docker_build_or_validate()`), it statically asserts
the real Dockerfile's hardening invariants and reports pass/fail; the full build +
smoke-run runs in the CI `docker` job.

---

## Full-sprint multi-persona audit

### 1. Engineering (whole branch) — **RELEASE-SOUND**
17/17 areas SOUND. Verified determinism gating (opt-in LLM/dynamic-graph features
never change the default stream; the one default-stream hash change is an
intentional, documented `human_review_required` schema addition regenerated
in-commit), the incrementality/ITT lift math (`ads/measure.py`), the unified
reclassification (`content/_safety.py` applied to both adapters), Wilson/Newcombe
CIs, MC Preview/Research wiring, sensitivity (Saltelli S1+ST), and the
path-traversal jail. Two low-severity, non-reachable nits were raised and **fixed**
(see Resolutions).

### 2. Docs & usability (cold-read, Windows) — **5/5**
A non-expert can install and run from copy-pasted README/usage commands; the web
console is fully labelled, surfaces errors (not swallowed), and shows
provenance/uncertainty. Every headline claim is bounded by a provenance label — no
overclaiming found. Prior friction (bare `pytest`, unquoted extras) confirmed
fixed. The one drift it caught — README test-count/coverage figures — was
**reconciled** (301 tests / 92.78%).

### 3. Security & release — **SOUND; gate honest**
All 35 controls present and wired; `SECURITY.md` matches the code with test
coverage (token + constant-time compare, Host/Origin allow-list, CSP/headers,
2 MB body limit, SSRF resolve-then-validate with metadata/RFC1918 block, static
path jail, non-loopback startup guard). CI runs bandit + pip-audit with **no
`continue-on-error`** (both blocking) plus a Docker build job. No failure-masking
path found; `# nosec` suppressions are line-scoped and justified; the old B110
`except: pass` suppression is gone.

---

## Findings & resolutions

| Finding (source) | Severity | Resolution | Commit |
|---|---|---|---|
| Hill estimator could divide by zero on a degenerate tail (`validation/targets.py`) | low | guard `xmin>0` / `denom>0` → return `inf`; verified all-equal tail → `inf`, normal → finite | `fix(p2)` |
| `audit_deps.py` left a temp requirements file (`NamedTemporaryFile(delete=False)`) | low (cosmetic) | unlink in a `finally` | `fix(p2)` |
| README test-count/coverage stale vs other docs | doc | reconciled to 301 tests / 92.78% across README, KNOWN_LIMITATIONS, AUDIT_LOG | `fix(p2)` |

The five P2 items the sprint set out to complete are all done and verified
(`feat(p2-1..5)`): unified LLM reclassification over generated text + ClaudeAdapter
guards; provenance badge on every secondary visualization; automated axe scan (0
violations) in the E2E; enforced (blocking) dependency/security scanning; Docker
hardening exercised in CI. Lower-priority ledger items **Q-REVIEW** (P2) and
**S6** (P3) remain OPEN and out of scope for this slice — recorded honestly in
`AUDIT_LOG.md`.

---

## Section scores

| Section | Score | Notes |
|---|---|---|
| Tests | 10/10 | 301 pass, 92.78% coverage, 0 failures |
| Release gate | 10/10 | 14/14 checks pass, 0 skipped |
| Security | 10/10 | scans blocking + passing; controls match SECURITY.md |
| Accessibility | 10/10 | automated axe scan, 0 violations across all tabs |
| Code quality | 10/10 | ruff clean; no dead code; nits resolved |
| Documentation | 9/10 | accurate + honestly bounded; figures reconciled |

---

## Summary

| Check | Result |
|---|---|
| Release gate (14 checks) | **14 / 14 PASS** |
| Test suite | **301 / 301 PASS** (92.78% coverage) |
| Ruff lint | **PASS** |
| Bandit + pip-audit | **PASS** (both blocking in CI) |
| Accessibility (axe) | **PASS** (0 violations) |
| Docker hardening | **PASS** (CI build + static validation) |
| Engineering audit (whole sprint) | **SOUND** |
| Docs / usability audit | **PASS** (5/5) |
| Security / release audit | **SOUND** |
| **Overall** | **PASS — x/x** |
