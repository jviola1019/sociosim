# Source Ledger

Citations backing SocioSim's quant methods, policy packs, and calibration
targets. Policy packs are research approximations, NOT legal advice.

## Regulatory (policy packs)
- **EU DSA** — Regulation (EU) 2022/2065, Arts. 9, 16, 17, 20, 22, 26, 28, 34–35;
  2022 Strengthened Code of Practice on Disinformation. (`eu_dsa.yaml`)
- **US Section 230** — 47 U.S.C. § 230(c)(1), (c)(2)(A), (e)(1)–(e)(2);
  FOSTA-SESTA (Pub. L. 115-164). (`us_section230.yaml`)
- **China** — Measures for Labeling AI-Generated Synthetic Content (CAC, eff.
  2025-09-01); Provisions on the Administration of Deep Synthesis (2023);
  Network Information Content Ecosystem Governance Provisions (2020);
  Cybersecurity Law Art. 47. (`cn_ai_label.yaml`)
- **US FTC** — 16 CFR Part 255 (Endorsement Guides); FTC Act § 5
  (15 U.S.C. § 45). (`ftc.yaml`)

## Quant methodology
- **CUPED variance reduction** — Deng, Xu, Kohavi & Walker (2013), *Improving the
  Sensitivity of Online Controlled Experiments by Utilizing Pre-Experiment Data*,
  WSDM. https://robotics.stanford.edu/~ronnyk/2013-02CUPEDImprovingSensitivityOfControlledExperiments.pdf
  → implemented in `socio_sim/ads/measure.py:cuped_lift`
- **Common Random Numbers in ABMs** — *Noise-free comparison of stochastic
  agent-based simulations using common random numbers* (2024), arXiv:2409.02086.
  → implemented in `socio_sim/experiments/compare.py:compare` (shared seed tree)
- **Newcombe difference-of-proportions CI** — Newcombe (1998), *Interval
  estimation for the difference between independent proportions*, Statistics in
  Medicine. (Wilson-hybrid; used in `stats.newcombe_diff_ci`.)
  → implemented in `socio_sim/stats.py:newcombe_diff_ci`
- **Bayesian A/B (Beta-difference posterior, P(lift>0))** — arXiv:2003.02769.
  → implemented in `socio_sim/ads/measure.py:prob_lift_positive`
- **False-discovery-rate control** — Benjamini & Hochberg (1995). Implemented
  for multi-campaign comparisons as BH q-values (`ads.measure.apply_fdr`;
  covered by `tests/test_ads.py`).
  → implemented in `socio_sim/ads/measure.py:apply_fdr`
- **Holdout / Ghost-Ads incrementality** — Johnson, Lewis & Nubbemeyer (Google),
  *Ghost Ads*; industry incrementality/iROAS guides (Measured, Improvado).
  → implemented in `socio_sim/ads/measure.py:measure_campaign` (`estimand=eligible_opportunity_itt`)

## LLM content safety boundaries
- **Prompt version** `llm_adapter_v2_safety_boundaries` — implemented in
  `socio_sim/content/llm_adapter.py`. Safety properties:
  - Prompt boundaries: fictional/no-PII/no-operational-harm framing embedded in
    `_PROMPT_TEMPLATE`.
  - Output guard: PII regex patterns, unsafe-phrase list, executable-content
    detection; failure degrades to template text and logs a `degradation` event.
  - Cache entries include: `backend`, `model`, `prompt_hash`, `prompt_version`,
    `provenance="generated_presentation_text"`, `state_mutation_allowed=false`.
  - CN jurisdiction: `[AI-generated content]` label prefix preserved across
    surface-text replacement.
  - LLM generated text is presentation-only; topic, stance, categories, and all
    event-stream state come from `TemplateGenerator` (deterministic, seeded).
- **Security scanning** — static analysis via Bandit ≥1.7 (`bandit -r socio_sim/ -ll`);
  dependency CVE audit via pip-audit ≥2.7 against production deps only
  (`scripts/audit_deps.py`). Both integrated in `.github/workflows/ci.yml`.

## Component benchmark data

- **Civil Comments toxicity sample** — bundled licensed aggregate/component
  benchmark for classifier measurement; see `docs/DATA_MANIFEST.md` and
  `BENCHMARK_REPORT.md`. Component-measured only; not ABM validation.
  → loaded in `socio_sim/validation/benchmark_eval.py`
- **Spam detection sample** — bundled licensed aggregate/component benchmark
  for classifier measurement; see `docs/DATA_MANIFEST.md` and
  `BENCHMARK_REPORT.md`. Component-measured only; not ABM validation.
  → loaded in `socio_sim/validation/benchmark_eval.py`

## Calibration targets (`data/benchmarks/default_targets.json`)
- Scale-free degree exponent 2–3 — Barabási & Albert (1999) and successors.
  → validated in `socio_sim/validation/targets.py:TargetSpec`
- Online-social-network clustering ~0.1–0.3 — e.g. Mislove et al. (2007).
- Circadian posting peaks ~16–18h, troughs ~04–06h — circadian activity studies.
- Display/social ad CTR ~0.5–2%; appeal reinstatement ~10–40% — platform
  transparency reports / industry aggregates.

## Scale & architecture (design spec)
- **OASIS** (arXiv:2411.11581) — cost of 100k-agent live-LLM runs (motivates
  offline deterministic generation as default).
- **S³** (arXiv:2307.14984) — reconstructed real networks of thousands of users.
- **Mesa / mesa-frames** ABM framework benchmarks — columnar/vectorised agent
  storage for ~10× speedups at 10k+ agents.

## Implemented methods map

| Method | Module | Function/class | Test coverage |
|--------|--------|----------------|---------------|
| Harmful-exposure bootstrap CI | `analytics/metrics.py` | `bootstrap_ci` | `test_analytics.py` |
| Moderation precision/recall | `analytics/metrics.py` | `moderation_confusion` | `test_analytics.py` |
| Appeal stats & Wilson CI | `analytics/metrics.py` | `appeal_stats` | `test_analytics.py` |
| Welfare proxy index | `analytics/metrics.py` | `welfare_proxy` | `test_analytics.py` |
| Metric provenance registry | `analytics/metrics.py` | `METRIC_PROVENANCE` | `test_analytics.py` |
| BH-FDR multi-campaign | `ads/measure.py` | `apply_fdr` | `test_ads.py` |
| CUPED lift | `ads/measure.py` | `cuped_lift` | `test_ads.py` |
| Newcombe diff CI | `stats.py` | `newcombe_diff_ci` | `test_stats.py` |
| Bayesian P(lift>0) | `ads/measure.py` | `prob_lift_positive` | `test_ads.py` |
| Ghost-ads holdout ITT | `ads/measure.py` | `measure_campaign` | `test_ads.py` |
| LLM surface-text adapter | `content/llm_adapter.py` | `LLMAdapter` | `test_llm_adapter.py` |
| Deterministic replay | `logs/replay.py` | `replay` | `test_determinism_regression.py` |
| Backtest leave-one-out | `validation/backtest.py` | `leave_out_backtest` | `test_backtest.py` |
| Sensitivity analysis | `validation/sensitivity.py` | `sensitivity_sweep` | `test_validation.py` |
| Policy comparison CRN | `experiments/compare.py` | `compare` | `test_experiments.py` |
| Scenario lint | `experiments/scenario_lint.py` | (CLI module) | `test_scenario_lint.py` |

Research recommendations for the incrementality design were produced by two
background research agents (2026-06-16) and recorded in `HANDOFF.md`.
