# 2026-06-27 Outside Auditor Report

**Auditor posture:** cold read — independent outside-user audit, no assumption of prior claims.
**Branch:** `feat/audit-p0-p1`
**Date:** 2026-06-28 (run date; filename retains the 2026-06-27 audit slug)
**Python:** 3.11.9 (`.venv`)
**Scope:** full test suite, release gate (`scripts/verify_release.py`, full mode), ruff, security check (bandit + pip-audit, run for real), and documentation cold-read.

---

## Overall Verdict: PASS

The repository passes a full outside-user audit. The release gate runs **13 checks
passed, 0 failed, 1 skipped** (only the Docker build is skipped — Docker is not
installed in this environment). 296 tests pass at 92.43% coverage, ruff is clean,
determinism is bit-stable, and — unlike the prior run — **both static security
scans (bandit, pip-audit) were installed and executed for real, and both pass**.
The Python codebase contains no dead code (ruff-enforced); the only cleanup
artifacts were 7 gitignored scratch files in the repo root, which were removed as
part of this work. Remaining findings are P2/P3 (documentation and a stale issue
ledger); none block use or produce incorrect results.

---

## Section Scores

| Section | Score | Notes |
|---|---|---|
| **Tests** | 9/10 | 296 pass, 92.43% coverage; docs still show bare `pytest` (P2-A, Windows) |
| **Release gate** | 10/10 | Full run: 13 passed / 0 failed / 1 skipped (Docker only, uninstalled) |
| **Security** | 9/10 | bandit + pip-audit now run and pass; startup guard for non-loopback bind enforced |
| **Code quality** | 10/10 | Ruff clean; zero dead code in Python; only 7 gitignored temp files removed |
| **Documentation** | 8/10 | Unusually thorough + honest; two stale numbers and a stale issue ledger (P2-C/P3-C) |

---

## Evidence Record

All commands were run with the project venv interpreter
(`.venv\Scripts\python.exe`). Use `python -m pytest`, not the bare `pytest.exe`
shim, on this MS-Store Python (see P2-A).

### 1. Release gate (full)

Command: `python scripts/verify_release.py` (full mode; not `--quick`). Exit code `0`.

```
Wrote docs\audits\latest-release-verification.md
{"passed": 13, "skipped": 1}
```

| Check | Status | Runtime | Evidence |
|---|---|---|---|
| Scenario linting (12 files) | passed | 22.3s | `Scenario lint passed for 12 file(s).` |
| ruff | passed | 1.6s | `All checks passed!` |
| Unit/integration tests + coverage (85% gate) | passed | 358.8s | 92.43% total; `Required test coverage of 85% reached` |
| Determinism/replay smoke | passed | 3.1s | hash `0a02eb4a…f8493b` |
| Policy comparison smoke | passed | 3.0s | `delta_median: 0.0` at n=80 (see P3-B) |
| Market holdout smoke | passed | 2.9s | `estimand='eligible_opportunity_itt'`, `economics_provenance='scenario_assumption'` |
| Validation smoke (`--validate --sens-samples 4`) | passed | 331.3s | `implausibility I = 1.67, cutoff 3.0` |
| Backtest smoke (`--backtest`) | passed | 94.8s | `held-out test_pass=True, I_test=0.78; stylized 5/5` |
| Security/config tests (14 tests) | passed | 9.9s | `14 passed` |
| Documentation claim-language scan | passed | 0.0s | `no unsupported banned claim language found` |
| UI/browser E2E (Playwright) | passed | 11.6s | `1 passed` |
| Docker build | **skipped** | — | `'docker' is not installed in this environment` |
| **Bandit static scan (medium/high)** | **passed** | 2.1s | no findings (clean) |
| **pip-audit (production deps)** | **passed** | 66.2s | `No known vulnerabilities found` |

### 2. Test suite

Command: `python -m pytest -q --cov=socio_sim --cov-report=term-missing --cov-fail-under=85`

```
TOTAL                                     3635    275    92%
Required test coverage of 85% reached. Total coverage: 92.43%
```

Collected count: **296 tests** (`pytest --collect-only -q` → 296). All pass; no
failures, no unexpected skips. Coverage 92.43% clears the 85% floor by a wide margin.

### 3. Ruff

Command: `python -m ruff check .`

```
All checks passed!
```

Exit 0, zero findings. Because the ruff rule set includes Pyflakes (`F`), this
also proves there are **no unused imports and no undefined names** anywhere in the
tree — i.e. no dead imports to remove.

### 4. Security check (run for real this time)

The `[security]` optional extra was installed (`pip install -e .[security]` →
bandit 1.9.4, pip-audit 2.10.1) so both scans execute instead of being skipped.

- **Bandit** (`bandit -r socio_sim/ -ll -q`): **passed**, no medium/high findings.
- **pip-audit** (`scripts/audit_deps.py`, production deps only): **passed** —
  `No known vulnerabilities found` across `numpy>=1.26`, `networkx>=3.2`,
  `scipy>=1.11`, `pyyaml>=6.0`.

Code-level controls were spot-checked against `SECURITY.md` and confirmed present:
per-session access token with constant-time compare, Host/Origin allow-lists
(CSRF + DNS-rebinding), CSP + `nosniff` + `X-Frame-Options: DENY` headers,
2 MB JSON body limit, SSRF allow-list on `llm_base_url` (metadata-IP/RFC1918
blocked), and a static-file path jail (`safe_static_path`). The non-loopback bind
is now **hard-guarded at startup**: `serve()` raises `RuntimeError` if `--bind` is
non-loopback and `SOCIOSIM_ACCESS_TOKEN`/`SOCIOSIM_ALLOWED_HOSTS` are unset
(`socio_sim/web/app.py:887-894`) — this closes the prior audit's P3-A.

### 5. Repository hygiene / dead code

- **Python dead code:** none. Ruff (Pyflakes) is clean; a direct grep of
  `socio_sim/` for commented-out code, `breakpoint(`, and `pdb.set_trace(` returns
  nothing. The `print(...)` calls in `experiments/scenario_lint.py` and
  `web/app.py` are legitimate CLI/startup output, not debug scaffolding.
- **Scratch files (removed):** 7 untracked, **already gitignored** dev utilities
  lived in the repo root — `get_ip.bat`, `start_tunnel.bat`, `open_site.html`,
  `start_web.bat`, `public_ip.txt`, `start_web.log`, `tunnel.log`. They are not
  referenced by any code or doc (only by `.gitignore`). Removed as part of this
  audit's cleanup; deletion does not touch tracked history.

### 6. Documentation cold-read

| File | Assessment |
|---|---|
| `README.md` | Comprehensive; honest "useful / NOT useful" scope box; research-use disclaimer. Install instructions accurate (but see P2-A). |
| `docs/usage.md` | Install, web console, CLI flags, profiles, validation ladder. Documents the campaign editor (see P2-C). |
| `SECURITY.md` | OWASP-framed threat model + control table; matches the code. |
| `KNOWN_LIMITATIONS.md` | Unusually candid (uncalibrated default, synthetic economics, untested GPU). Two stale figures (see P3-C). |
| `AUDIT_LOG.md` | Issue ledger with severity/status/commit; partially stale (see P2-C). |

An outside user can understand what the tool is, how to install/run it, what the
outputs mean and don't mean, and where the honest limits are.

---

## Issues Found

### P2-A — Windows: docs show bare `pytest`; should be `python -m pytest`

**File:** `README.md:78`, `docs/usage.md:9`
**Observed:** Both quickstarts invoke `pytest` directly. On this MS-Store Python,
the `.venv\Scripts\pytest.exe` shim does not expose the venv site-packages and
fails with a spurious `ModuleNotFoundError: hypothesis`; `python -m pytest` runs
all 296 tests correctly.
**Impact:** A Windows user following the README literally sees a fake
missing-dependency failure on first run.
**Fix:** Show `python -m pytest` as the primary example (platform-unambiguous);
keep bare `pytest` as the activated-venv shorthand.

### P2-C — `AUDIT_LOG.md` issue ledger is stale

**File:** `AUDIT_LOG.md:28,25,31`
**Observed:** `S3` (campaign-level marketing controls in UI) is marked
`DEFERRED (P6 full UI)`, but the campaign editor is implemented and documented
(`docs/usage.md:42-43`, present in `socio_sim/web/static/`). `Q-REVIEW` (P2,
reviewer ground-truth heuristic / appeal magic) and `S6` (P3, classifier
global-only) remain `OPEN`.
**Impact:** The ledger understates delivered work (S3) and leaves two real P2/P3
items open without a provenance note. A reader can't trust the ledger's
OPEN/DONE state at face value.
**Fix:** Flip `S3` to DONE with the implementing commit; either close `Q-REVIEW`
with a `docs/MODELS.md` provenance note on appeal-grant dynamics, or keep it open
but reference it from the model doc.

### P3-B — Policy comparison smoke yields zero delta at test scale

**File:** `scripts/verify_release.py` (policy comparison smoke)
**Observed:** US vs EU at `n_agents=80, n_ticks=12, 2 replicates` produces
`delta_median: 0.0, delta_ci: (0.0, 0.0)` — both regimes give identical
`harmful_exposure_rate`. The check only asserts the key exists, not that the
regimes are distinguishable.
**Impact:** A genuinely broken policy comparison could pass this smoke unnoticed
at minimal scale.
**Fix:** Add a distinguishability assertion at a larger scale, or document that
zero delta at 80 agents is expected and the comparison is meaningful only at
1,000+ agents.

### P3-C — Two stale numbers in `KNOWN_LIMITATIONS.md`

**File:** `KNOWN_LIMITATIONS.md:29,116`
**Observed:** (1) The backtest paragraph states `I_test approx 0.12`, but the
reproducible `run.py --backtest` smoke reports `I_test=0.78` (still
`test_pass=True`). (2) The Tooling section says local audit passes "265 pytest
tests"; the suite now collects **296**.
**Impact:** Cosmetic/credibility only — both claims still hold directionally
(backtest passes; tests pass), but the specific figures no longer match a fresh run.
**Fix:** Update both numbers, or phrase them as "~" ranges that won't drift per run.

---

## Resolved Since The Prior Audit

- **P2-D (security tools skipped):** `bandit` + `pip-audit` were installed via the
  `[security]` extra and both **pass** in this run (previously `skipped` because
  the extra wasn't installed). Residual: the README install quickstart still omits
  `[security]`, so a user following it verbatim would still skip them — worth
  folding `[security]` into the documented install or `[dev]`.
- **P3-A (non-loopback startup guard):** now enforced — `serve()` raises on
  non-loopback bind without the required env vars (`web/app.py:887-894`).

---

## Positive Observations (not typical for research code)

1. **Honest scope + provenance ladder.** README's "NOT useful" box and the
   `synthetic-exploratory → … → measured-on-benchmark` ladder keep every claim
   bounded by its evidence label.
2. **Incrementality done correctly.** Holdout lift uses an organic baseline and an
   eligible-opportunity ITT denominator, with Newcombe CI, CUPED, and BH-FDR
   across campaigns — above standard for research tooling.
3. **Determinism locked by regression test.** The event-stream SHA-256 is stable
   (`0a02eb4a…`) and pinned in `tests/test_determinism_regression.py`.
4. **Defense-in-depth for a localhost tool.** Per-session token + Host/Origin
   allow-list + CSP closes CSRF and DNS-rebinding; SSRF allow-list blocks
   cloud-metadata IPs; static path jail prevents traversal.
5. **Clean dependency surface.** Only four production deps, all CVE-free per
   pip-audit.

---

## Recommendations

1. Fix the Windows `pytest` docs (P2-A) — one-line change, removes a confusing
   first-run failure.
2. Reconcile `AUDIT_LOG.md` (P2-C) — flip S3 to DONE; resolve or annotate Q-REVIEW.
3. Refresh the two stale numbers in `KNOWN_LIMITATIONS.md` (P3-C).
4. Fold `[security]` into the documented install so bandit/pip-audit run for a
   user following the README (P2-D residual).
5. Strengthen the policy-comparison smoke (P3-B) — distinguishability assertion or
   a documented expectation.
6. Add a Docker build to CI so the containerized path is exercised rather than
   skipped.

---

## Summary

The project passes this audit. The full release gate is green (13/13 runnable
checks; Docker the only skip, for lack of an installed engine), 296 tests pass at
92.43% coverage, ruff is clean, determinism is stable, and both static security
scans now run and pass. The Python code carries no dead code; only gitignored
scratch files were removed. The open findings are documentation-level (P2-A,
P2-C, P3-C) and one smoke-test rigor note (P3-B) — none affect correctness or
security under the tool's declared single-user localhost research scope.

| Check | Result |
|---|---|
| Test suite (296 tests, 92.43% coverage) | **PASS** |
| Ruff lint (zero findings) | **PASS** |
| Release gate (full: 13 passed, 0 failed, 1 skipped) | **PASS** |
| Validation smoke (I=1.67 < 3.0) | **PASS** |
| Backtest smoke (I_test=0.78; stylized 5/5) | **PASS** |
| Bandit static security scan | **PASS** |
| pip-audit (production deps) | **PASS** |
| Documentation cold-read | **PASS** |
| Dead-code / repo hygiene | **PASS** (7 temp files removed) |
| **Overall** | **PASS** |
