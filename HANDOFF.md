# SocioSim — Sprint Handoff / Resume State

**Purpose:** live resume doc so this sprint can continue across sessions/token cutoffs.
Keep this updated after every phase. If you are resuming, read this first, then `AUDIT_LOG.md`.

## Where we are
- Branch: `feat/audit-p0-p1` (off `main`).
- Baseline: 108 tests passing. Determinism hashes locked in `AUDIT_LOG.md`.
- Confirmed scope: Preview+Research MC modes; organic-baseline incrementality; full multi-route UI.

## Order of execution (value x completability)
1. [ ] P1a determinism regression test (characterization guard for refactors)
2. [ ] P1b Hill exponent -> observed (isolated)
3. [ ] P5a path-traversal fix (isolated, security)
4. [ ] P1c Wilson intervals + provenance labels + doc fixes
5. [ ] P1d BehaviorParams extraction (regression-protected)
6. [ ] P1e Monte Carlo wiring (Preview + Research) into pipeline/CLI/web
7. [ ] P2 organic baseline incrementality (apply research-agent findings)
8. [ ] P3 policy-as-code citations + schema + transparency exporter
9. [ ] P4 calibration + sensitivity over BehaviorParams + VALIDATION_REPORT.md
10. [ ] P5b SBM blocks (S2), hot-loop perf, follow/unfollow or remove dead kinds, LLM accounting
11. [ ] P6 multi-route studio + force-graph + a11y + preset reset (S1) + campaign editor (S3)
12. [ ] Final: full pytest + ruff, scorecard, KNOWN_LIMITATIONS.md, finish branch

## Background agents in flight
- Incrementality methodology research (Q2) — recommendation expected.
- Incrementality codebase implementation spec (Q2) — file:line plan expected.
Apply both before/while implementing step 7 (P2).

## Invariants that must never regress
- Same config+seed -> identical event-stream SHA-256 (determinism + replay tests).
- No headline metric without a provenance label.
- No "validated/calibrated" claim without evidence in VALIDATION_REPORT.md.
- numpy Generators only from the module-keyed SeedTree (no global RNG).

## Not yet started / deferred
- (updated as we go)
