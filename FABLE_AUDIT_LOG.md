# Fable Independent Audit Log — Phase 0 Baseline

**Auditor model:** `claude-fable-5` (verified via direct model-ID echo before this run)
**Invocation:** `claude.exe --model claude-fable-5 --add-dir C:\Users\jviol\Downloads\socio_sim -p <phase0 prompt>`
**Orchestrated by:** Sonnet 5, from branch `fix/p0-llm-cache-and-audit-hardening`
**Date:** 2026-07-02

## Purpose

This audit was run with an independent model (Fable) rather than the same model
family that authored the code under review, to avoid the self-referential
"CI self-flag" bias previously recorded in this repo's audit history
(see `ee229d4 docs(audit): record R11-CISELFFLAG ...`).

## Phase 0 prompt

```
You are running as claude-fable-5 on the socio_sim codebase at C:\Users\jviol\Downloads\socio_sim. Run these commands and report exact output:
1. git -C C:\Users\jviol\Downloads\socio_sim log --oneline -5
2. git -C C:\Users\jviol\Downloads\socio_sim status
3. cd C:\Users\jviol\Downloads\socio_sim && .venv\Scripts\python.exe -m pytest -q 2>&1 | tail -20
Then read socio_sim/content/llm_adapter.py and socio_sim/content/llm_cache.py and confirm the P0 cache bypass fix is present. Report findings.
```

## Fable output (verbatim, unedited)

All three commands attempted; two succeeded, pytest was blocked by the permission system. Code inspection confirms the P0 fix is present. Details below.

### 1. `git log --oneline -5` — exact output

```
ee229d4 docs(audit): record R11-CISELFFLAG + R2-LLMCACHE-was-incomplete + R12-CACHETAMPER
fc625fc fix(p0): close ClaudeAdapter blocked-cache bypass + tamper-evident cache records
3461c4b fix(ci): claim scanner must not flag its own test fixture
5bbfa77 feat(claims): context-aware claim scanner (R8), replacing the literal blacklist
6318a2e feat(evidence): per-default provenance granularity (R6) + UI overclaim removal (R9)
```

(Note: the `-C C:\...` form of the command required approval; the identical command run from the repo working directory succeeded — same result.)

### 2. `git status` — exact output

```
On branch fix/p0-llm-cache-and-audit-hardening
Your branch is up to date with 'origin/fix/p0-llm-cache-and-audit-hardening'.

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	fable_phase0.txt
	open_vscode.bat
	server.log
	start_ssh_tunnel.bat
	tunnel.log

nothing added to commit but untracked files present (use "git add" to track)
```

### 3. pytest — **could not run (permission denied)**

Every invocation was rejected by the harness permission system, and this session is non-interactive so no approval can be granted: `.venv\Scripts\python.exe -m pytest -q` via PowerShell (plain and piped), the same via Bash, and `.venv/Scripts/pytest.exe -q`. No test output was produced, so per evidence-before-assertions the suite is **not** claimed to pass. To unblock, allowlist `.venv/Scripts/python.exe` (or run the suite in an interactive session).

### P0 cache-bypass fix: present in code (verified by inspection, not by tests)

The fix from `fc625fc` is in place, structured as a single shared trust module so the two adapters can't drift:

- **`socio_sim/content/llm_cache.py`** is the shared decision point. `record_hash()` (line 52) binds text + status + reason_codes into a SHA-256 integrity hash; `make_entry()` (line 61) stamps it onto every new cache record. `resolve()` implements the trust rules:
  - `record_hash` mismatch → treated as a **miss** with a `cache_tampered:record_hash_mismatch` degradation, entry discarded and regenerated (lines 96–102).
  - Unknown `status` value → treated as tampered, not as valid (lines 104–108).
  - `status == "blocked"` → **never served as content**: returns `hit=True, text=None` with a degradation message when `guard_version` matches `BLOCKED_GUARD_VERSION`, forcing template fallback with no remote call (lines 110–115); a guard-version mismatch is a deliberate miss so the prompt gets re-screened (line 117).
- **`socio_sim/content/llm_adapter.py:101–108`**: `LLMAdapter.generate` routes every lookup through `llm_cache.resolve`, reports the degradation, and on any hit returns without calling the transport — the comment at line 108 states the invariant: "blocked or tamper-free accepted hit; never re-call". Blocked entries are written with `guard_version=llm_cache.BLOCKED_GUARD_VERSION` (lines 119–121).
- **The ClaudeAdapter side of the P0 is also closed**: `socio_sim/content/claude_adapter.py:75` uses the same `llm_cache.resolve`, and writes via `make_entry` at lines 96 and 103. The `llm_cache.py` docstring explicitly cites the original divergence (AUDIT_LOG.md R-CLAUDE-P0).
- `tests/test_llm_cache.py` covers the tamper and blocked-entry paths (record-hash mismatch, status flip, blocked-never-served, legacy entries) — but those tests **were not executed** this session for the reason above.

**Bottom line:** the P0 fix is structurally present and both adapters go through the shared tamper-evident trust logic, but the test-suite gate is unverified here because the permission system blocked pytest. Given this repo's history of "fixed" claims without green gates, treat the fix as code-confirmed / test-unverified until pytest is actually run and its output quoted.

## Open follow-up

- [x] Re-run `pytest -q` for this branch in an environment where the harness permission system allows it, and append the real (non-"tail -20"-truncated ideally full) output to this log before treating the P0 fix as test-verified. **Done 2026-07-09: full suite run in-session repeatedly (see below).**

## Session 2026-07-09: headless fix-loop retired; 0159 audit remediated in-session (Fable 5, interactive)

The subprocess-driven fix loop (`run_fable_*.vbs`/`.ps1` one-shot prompts)
is retired: its commits proved unreliable (see `AUDIT_LOG.md` "Session
2026-07-09" for the full forensic account — a "all fixes applied" commit
that reverted a fix, a truncated unimportable `llm_cache.py` at HEAD, real
fixes left uncommitted with 4 failing tests, stale `.git/*.lock` files from
crashed runs). All further Fable remediation happens in an interactive
session with test-first fixes and full-gate verification per commit.

Outcome for `docs/audits/fable_audit_20260703_0159.md` (20 findings):
**18 fixed** across commits `0985a9b`, `ae3ad4a`, `9c5c994`, `394b994`,
`ae70ce0`, `b76de4f`, `5e87bc5`; 2 initially deferred with rationale (E-05
DNS-pinning redesign; G-02 axe-core CI gate) — **both closed the next day
(2026-07-10)**, making it **20/20**: E-05 via pinned-IP connections
(`_PinnedHTTP(S)Connection`, urllib removed from the transport) and G-02
via an axe-core CI gate whose first run caught and fixed 5 real
light-theme contrast defects. See `AUDIT_LOG.md` session table. Suite grew 328 -> 358 tests;
every commit was preceded by a full green `pytest` + ruff +
claim_scan/evidence_gate/secret_scan run, quoted in the commit message.
An independent code-reviewer agent pass over the six fix commits found no
>=80-confidence issues (and surfaced that the 0159 H-01 `web_path` finding
had been conflated with an earlier audit's H-01 — fixed, `5e87bc5`);
a branch-diff security review returned an empty report.
