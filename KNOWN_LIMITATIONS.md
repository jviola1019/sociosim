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
- **Feed hot loop optimised** (per-tick author index + O(k) exploration-pool
  sampling, replacing per-agent O(recent_posts) scans). Measured (template mode,
  single-threaded): ~6.6 s for 1,000 agents × 168 ticks, ~13 s for 2,000
  (≈linear, ~16k events/s). The standard profile (10k × 672) extrapolates to
  ~5 min/replicate single-threaded; **parallel Monte Carlo replicates (process
  pool) is the remaining scale lever** for the 100-replicate standard runs.
- Exact `nx.average_clustering` is still O(n·⟨k²⟩) on very large graphs; an
  approximate estimator for very large n is a further option.
- **Static social graph:** no follow/unfollow/churn in v1 (dead event kinds
  removed; spec corrected).

## Marketing
- Incrementality is valid (organic baseline + Newcombe/Beta CI + CUPED + BH-FDR).
  ROAS/iROAS/CAC/LTV are reported but **synthetic** (depend on conversion_value /
  ltv_multiplier assumptions). Lift is ITT over the realized frequency mix; no
  dose-response curve or attribution-window modelling yet. No campaign editor in
  the UI (S3 open).

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

## Formerly out-of-scope (spec §6) — now delivered, with honest caveats
- **Real image/video synthesis:** deterministic procedural PNG (real bytes,
  offline, zero-dep). It is deliberate generative art, not photoreal; video is
  frame sequences (container encoding e.g. APNG/MP4 not yet wired); a diffusion
  backend is a pluggable hook, not bundled (would break offline/determinism).
- **Distributed/GPU:** distributed Monte Carlo via a pluggable executor
  (ProcessPool verified; Dask/Ray-ready). **GPU is NOT verified here** — kernels
  are numpy with a CuPy drop-in possible; treat GPU as opt-in/unverified.
- **Bundled empirical datasets:** published *aggregate* sets only (no PII);
  values are research approximations with wide tolerances; Facebook degree-tail
  omitted (not power-law, Ugander 2011) rather than fabricated.
- **Real moderation-model training:** the trained classifier is real and its P/R
  is measured, but it is trained on **synthetic templated** content, so it learns
  the simulator's injected signal — NOT evidence of real-world moderation
  accuracy. Use it to study FP/FN *dynamics*, not as a deployable model.

## Tooling
- **ruff not installed** (dev deps = pytest only); add to `pyproject.toml` to
  enforce a lint gate.

See `AUDIT_LOG.md` for the full issue ledger with status, and `HANDOFF.md` for
the resume plan.
