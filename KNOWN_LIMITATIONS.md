# Known Limitations

Honest residual limitations after the P0/P1 audit remediation (branch
`feat/audit-p0-p1`). See `docs/ethics_and_limitations.md` for the v1 baseline
list; this file tracks what remains open or newly surfaced.

## Quant / validation
- **A calibrated profile now exists.** `RunConfig.calibrated()` / `--profile
  calibrated` history-matches the graph (Holme-Kim `plc`, p=0.7) and is
  calibration-consistent against the bundled benchmark (current default
  implausibility I=1.25 < 3.0, dominated by `ad_ctr`;
  `CALIBRATION_REPORT.md`, replay-verified). Honest scope: this is
  calibration *consistency* against wide published **aggregates**, not predictive
  validation — the model stays a synthetic ABM (projections, not predictions).
- **The default profile is still uncalibrated** (BA graph, I≈1.7, clustering
  below band) and BehaviorParams remain synthetic scenario knobs. Use the
  calibrated profile when calibration consistency matters.
- **Top rung reached for the classifier** (`run.py --measure-classifier`,
  `BENCHMARK_REPORT.md`): the moderation classifier is **measured on REAL,
  license-clean public benchmarks** — Civil Comments toxicity (CC0): F1≈0.74,
  ROC-AUC≈0.81; Deysi spam (Apache-2.0): F1≈0.99, ROC-AUC≈1.00 (deterministic,
  PII-scrubbed; `docs/DATA_MANIFEST.md`). Provenance `measured-on-benchmark`.
  Honest scope: this measures the CLASSIFIER COMPONENT on real text; it does not
  make the synthetic agent-based simulation predictive of any real platform, and
  no decisions are made about real individuals.
- **Now validated one rung higher** (`run.py --backtest`, `BACKTEST_REPORT.md`):
  the calibrated world reproduces 5 cited **stylized facts** (heavy-tail degree,
  clustering≫random, cascade skew, participation inequality, diurnal cycle) and
  passes a **held-out aggregate backtest** (calibrate on a train subset of public aggregates -> held-out metrics within tolerance, I_test approx 0.78 in the bundled smoke). Honest ceiling:
  this is aggregate/pattern agreement, NOT point-prediction of a real platform;
  agent behavioural magnitudes stay calibrated assumptions (no real-person
  microdata — lawful by design; see `docs/DATA_MANIFEST.md`).
- **Sensitivity is now multi-output, multi-seed, Sobol + Saltelli ST**
  (`multi_output_sensitivity`, report §1b; `saltelli_study`, report §1c):
  first-order indices for n_posts / harmful_exposure / welfare over a Sobol
  design, plus total-effect indices for `n_posts`. Residual: higher-order
  interaction decomposition is not reported; bounds are still ±50% of defaults.
- **ABC posterior is propagated to outputs** (`posterior_calibrated_mc`, report
  §2b): history-match → ABC posterior → output interval (parameter-uncertainty,
  not single-run noise). Residual: this runs in the validation study; the default
  Research MC still reports fixed-parameter replicate intervals unless you invoke
  the posterior-propagated path.

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
- Incrementality is implemented for scenario diagnostics (organic baseline +
  eligible-opportunity ITT denominator, Newcombe/Beta CI, CUPED + BH-FDR);
  dose-response by frequency and an attribution-window model **are** implemented,
  and the UI has a campaign editor. ROAS/iROAS/CAC/LTV remain **synthetic** —
  they depend on conversion_value / ltv_multiplier assumptions, so treat the
  money figures as scenario inputs, not measured returns.

- The current lift metric is an **eligible-opportunity ITT** diagnostic: the
  denominator is the randomized opportunity frame logged before holdout
  suppression; paid impressions and spend remain priced-auction only. This is
  still synthetic scenario evidence, not real-market incrementality.

## Regulatory
- Policy packs are research approximations with statute citations and
  `legal_uncertainty` notes — **not legal advice**. Deadlines (e.g. EU 24h) are
  modelling assumptions, not statutory mandates.

## UI
- Multi-tab studio is built: Overview/Feed/Charts/Network (interactive 3D
  force-graph)/Cascade replay/Fairness/Ads/Calibration/Compare (A/B)/Audit/Log,
  plus the `n_replicates` control, preset reset-then-apply, theme toggle, and a
  campaign editor.
- **Presets** are cited + subsectioned (Regulatory/Research/Business) with a
  visible "what this changes" + Sources panel on selection; red-team adversaries
  are folded into presets (no standalone tab).
- **Marketing** tab (replaced Red Team): A/B power/holdout lab, unit economics
  (ROAS/CAC/LTV:CAC), reach & frequency, and GARM brand-safety — calculators
  grounded in cited benchmarks (`docs/RESEARCH_EVIDENCE.md`).
- **Settings** carry units + researched reference ranges as tooltips.
- **Security:** hardened per `SECURITY.md` (token, Origin/Host check, CSP +
  headers, body/Content-Type limits, SSRF allow-list on the LLM URL).
- **Accessibility:** an automated **axe-core** scan runs over every dashboard tab
  in the Playwright E2E and asserts **zero** violations (contrast, landmarks,
  heading order, control names, focusable scroll regions), on top of the manual
  ARIA hardening (tablist/tab, aria-live, SVG role+label, data-table alternates).
- **Provenance:** every **secondary visualization** (the four charts, the 3D
  network, cascade replay, confusion grid, fairness table) now carries a
  server-driven provenance badge (`model-derived` / `synthetic assumption`).

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
  an 85% coverage floor (actual ~92%). Local audit verification currently passes
  ruff plus 301 pytest tests; GitHub Actions runs ruff + pytest + a real
  Playwright E2E (including an automated **axe-core** accessibility scan) +
  **Bandit** and **pip-audit** (both blocking) + a **Docker image build** + a
  wheel build with a data-asset assertion. `bandit` and `pip-audit` ship in the
  `[dev]` extra so the documented install runs them.

See `AUDIT_LOG.md` for the full issue ledger with status, and `HANDOFF.md` for
the resume plan.
