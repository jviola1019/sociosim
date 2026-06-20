# Known Limitations

Honest residual limitations after the P0/P1 audit remediation (branch
`feat/audit-p0-p1`). See `docs/ethics_and_limitations.md` for the v1 baseline
list; this file tracks what remains open or newly surfaced.

## Quant / validation
- **A calibrated profile now exists.** `RunConfig.calibrated()` / `--profile
  calibrated` history-matches the graph (Holme–Kim `plc`, p=0.7) so **every**
  published-aggregate observable falls within one tolerance band (implausibility
  I=1.0 < 3.0; `CALIBRATION_REPORT.md`, replay-verified). Honest scope: this is
  calibration *consistency* against wide published **aggregates**, not predictive
  validation — the model stays a synthetic ABM (projections, not predictions).
- **The default profile is still uncalibrated** (BA graph, I≈1.7, clustering
  below band) and BehaviorParams remain synthetic scenario knobs. Use the
  calibrated profile when calibration consistency matters.
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
- Average clustering is exact for n≤5000 and a deterministic sampled estimate
  above that, so very large graphs stay fast.
- **Dynamic social graph available** (opt-in `follow_rate`/`unfollow_rate`/
  `churn_rate`, or `--dynamic-graph`): daily follow (triadic closure)/unfollow/
  churn, emitted as events, deterministic + replayable. Default is still static
  (rates 0) so baseline runs are unchanged. Residual: tie formation is a simple
  triadic-closure/random model, not fit to a measured rewiring process.

## Marketing
- Incrementality is valid (organic baseline + Newcombe/Beta CI + CUPED + BH-FDR);
  dose-response by frequency and an attribution-window model **are** implemented,
  and the UI has a campaign editor. ROAS/iROAS/CAC/LTV remain **synthetic** —
  they depend on conversion_value / ltv_multiplier assumptions, so treat the
  money figures as scenario inputs, not measured returns.

## Regulatory
- Policy packs are research approximations with statute citations and
  `legal_uncertainty` notes — **not legal advice**. Deadlines (e.g. EU 24h) are
  modelling assumptions, not statutory mandates.

## UI
- Multi-tab studio is built: Overview/Feed/Charts/Network (interactive 3D
  force-graph)/Cascade replay/Fairness/Ads/Calibration/Compare (A/B)/Audit/Log,
  plus the `n_replicates` control, preset reset-then-apply, theme toggle, and a
  campaign editor. Remaining UI polish: full a11y pass (slider aria-valuetext,
  focus order, data tables) and provenance badges on individual content cards.

## Formerly out-of-scope (spec §6) — now delivered, with honest caveats
- **Real image/video synthesis:** deterministic procedural PNG **and a real
  playable APNG video** (`synth_video`), offline + zero-dep. An external
  diffusion/image model is plugged in via `set_image_backend`. Honest residual:
  the default art is deliberate generative geometry, not photoreal — photoreal
  requires the (optional) diffusion backend, which trades away offline/determinism.
- **Distributed/GPU:** distributed Monte Carlo via a pluggable executor
  (ProcessPool verified; Dask/Ray-ready); `accel.py` routes the classifier
  training matmuls to CuPy when a GPU is present, else NumPy (numpy path
  verified). Honest residual: the **GPU path is not exercised on hardware here**
  (CI has no device) — opt-in, verify on a GPU box to claim it.
- **Bundled empirical datasets:** published *aggregate* sets only (no PII);
  values are research approximations with wide tolerances; Facebook degree-tail
  omitted (not power-law, Ugander 2011) rather than fabricated.
- **Real moderation-model training:** the trained classifier is real and its P/R
  is measured, but it is trained on **synthetic templated** content, so it learns
  the simulator's injected signal — NOT evidence of real-world moderation
  accuracy. Use it to study FP/FN *dynamics*, not as a deployable model.

## Tooling
- ruff is a dev dependency and a CI gate (lint passes clean); pytest-cov enforces
  an 85% coverage floor (actual ~92%). GitHub Actions runs ruff + pytest + a real
  Playwright E2E + a wheel build with a data-asset assertion.

See `AUDIT_LOG.md` for the full issue ledger with status, and `HANDOFF.md` for
the resume plan.
