# Known Limitations

Honest residual limitations after the P0/P1 audit remediation (branch
`feat/audit-p0-p1`). See `docs/ethics_and_limitations.md` for the v1 baseline
list; this file tracks what remains open or newly surfaced.

## Quant / validation
- **BehaviorParams are synthetic, not calibrated.** `VALIDATION_REPORT.md` shows
  every swept knob has a high first-order sensitivity index for posts/agent, yet
  none is fitted to data. Outputs depending on them are scenario assumptions,
  not predictions, until calibrated against real (anonymised) targets.
- **Calibration is coarse.** Benchmark targets are wide published aggregates;
  the default run is *not implausible* (I≈1.8<3) but `degree_tail_exponent` and
  `diurnal_peak_hour` sit outside their ±1-tolerance bands (see report).
- **Sensitivity study is small** (single output, single seed, n≈24 LHS, ±50%
  bounds, correlation-ratio estimator over-estimates at small n). A full study
  needs multiple outputs, many seeds (Monte Carlo), and Sobol sequences.
- **Monte Carlo Research mode** aggregates a fixed set of headline metrics; it
  does not yet propagate parameter-uncertainty posteriors (history-matching/ABC
  exist but are not chained into the default Research run).

## Engine / scale
- **Standard profile (10k×672) performance unverified** — per-agent Python hot
  loops + exact clustering remain (Q-PERF open). Documented ceiling pending.
- **Static social graph:** no follow/unfollow/churn; `follow`/`unfollow`/
  `policy_gap` event kinds are declared but unused (Q-KINDS open).
- **SBM ignores n_agents** in the web form (S2 open).

## Marketing
- Incrementality is now valid (organic baseline + Newcombe/Beta CI), but lift is
  ITT over the realized frequency mix; no dose-response, LTV/CAC/ROAS, or
  attribution-window modelling yet. No campaign editor in the UI (S3 open).

## Regulatory
- Policy packs are research approximations with statute citations and
  `legal_uncertainty` notes — **not legal advice**. Deadlines (e.g. EU 24h) are
  modelling assumptions, not statutory mandates.

## UI (P6 — largest open item)
- Single-screen studio only; no Compare/Validate/Audit/Transparency routes, no
  topology/force-graph or cascade replay, no `n_replicates` control (S4), no
  preset reset-then-apply (S1). Provenance badges not yet surfaced in the UI.
- `style.css` header still advertises interactions (aurora-mesh/tilt/spotlight/
  magnetic) that are not implemented (Q-CSS open).

## Tooling
- **ruff not installed** (dev deps = pytest only); add to `pyproject.toml` to
  enforce a lint gate.

See `AUDIT_LOG.md` for the full issue ledger with status, and `HANDOFF.md` for
the resume plan.
