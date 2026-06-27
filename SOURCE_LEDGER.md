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
- **Common Random Numbers in ABMs** — *Noise-free comparison of stochastic
  agent-based simulations using common random numbers* (2024), arXiv:2409.02086.
- **Newcombe difference-of-proportions CI** — Newcombe (1998), *Interval
  estimation for the difference between independent proportions*, Statistics in
  Medicine. (Wilson-hybrid; used in `stats.newcombe_diff_ci`.)
- **Bayesian A/B (Beta-difference posterior, P(lift>0))** — arXiv:2003.02769.
- **False-discovery-rate control** — Benjamini & Hochberg (1995). Implemented
  for multi-campaign comparisons as BH q-values (`ads.measure.apply_fdr`;
  covered by `tests/test_ads.py`).
- **Holdout / Ghost-Ads incrementality** — Johnson, Lewis & Nubbemeyer (Google),
  *Ghost Ads*; industry incrementality/iROAS guides (Measured, Improvado).

## Component benchmark data

- **Civil Comments toxicity sample** — bundled licensed aggregate/component
  benchmark for classifier measurement; see `docs/DATA_MANIFEST.md` and
  `BENCHMARK_REPORT.md`. Component-measured only; not ABM validation.
- **Spam detection sample** — bundled licensed aggregate/component benchmark
  for classifier measurement; see `docs/DATA_MANIFEST.md` and
  `BENCHMARK_REPORT.md`. Component-measured only; not ABM validation.

## Calibration targets (`data/benchmarks/default_targets.json`)
- Scale-free degree exponent 2–3 — Barabási & Albert (1999) and successors.
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

Research recommendations for the incrementality design were produced by two
background research agents (2026-06-16) and recorded in `HANDOFF.md`.
