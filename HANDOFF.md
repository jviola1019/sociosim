# SocioSim Handoff

This is an evidence-first remediation program, now in its second working
branch: `fix/p0-llm-cache-and-audit-hardening` (PR #5), based on `main` with
PR #4 already merged. Current boundaries:

- Runtime classifier modes are synthetic mechanics modes.
- Built-in defaults are scenario assumptions unless a user supplies evidence.
- Legacy aggregate targets are aggregate-fit diagnostics only.
- v4 dashboard images are synthetic decorative artwork, not visual evidence.
- Advertising outputs are synthetic diagnostics and assumption-ledger rows, not
  recommendations.
- "calibrated" is not a publicly selectable profile; it migrates to
  `aggregate_matched_prototype` only through `_migrate_legacy_profile`.
- A cached LLM response with `status: "blocked"` is never served as content
  and never triggers a new remote call (see `llm_adapter.py::generate`).

**Read `AUDIT_REMEDIATION_REPORT.md`'s addendum first.** PR #4's report
claimed several things ("CI green", the P0 cache fix, `asset_qa.py` passing)
that did not hold under independent re-verification. The addendum documents
exactly what was false, what was fixed, what was confirmed correct, and what
is still genuinely incomplete (evidence-registry per-default granularity, the
art-directed 96+-asset visual rebuild, a context-aware claim scanner, and an
unreviewed causal/accessibility surface). Do not assume anything in this repo
is done because a prior report says so — re-run the check.

CI is green on PR #5 (run `28481398083`, all 13 steps). Next session should
pick up the "Confirmed still incomplete" list in the addendum, largest item
first (evidence registry granularity, then the visual system rebuild).
