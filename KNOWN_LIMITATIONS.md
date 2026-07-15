# Known Limitations

This file tracks the evidence-first operating limits after the v4 remediation.

## Evidence Status

- SocioSim is a synthetic scenario simulator. Outputs are not predictions,
  empirical estimates, legal advice, compliance seals, or operational
  recommendations.
- Behaviour, personas, graph/profile defaults, policy timings, ad assumptions,
  benchmark targets, and UI presets are scenario assumptions unless a registry
  record says otherwise.
- Legacy aggregate targets have incomplete source metadata. They support only
  aggregate-fit diagnostics and synthetic mechanism checks.
- No real-deployable runtime moderation classifier is present.
  `synthetic_noise_classifier` and `synthetic_template_classifier` are the only
  public modes.

## Measurement Limits

- Single-run intervals are descriptive resampling intervals under an
  agent-independence approximation, or analytic diagnostics for a synthetic run.
- Replicate-level Monte Carlo intervals are separate from parameter, source, and
  structural uncertainty.
- Current ad lift outputs are synthetic diagnostics. The former CUPED-style
  field is now `oracle_covariate_adjusted_simulation_diagnostic`.
- ROAS, CAC, LTV, conversion value, and frequency assumptions are scenario
  inputs, not measured business returns.

## Assets

- v4 assets are deterministic project-owned synthetic decorative PNGs with
  registry records, SHA-256 hashes, perceptual hashes, QA status, and alt
  templates.
- v4 visuals are not evidence, do not depict real people or brands, and are not
  human-reviewed unless a reviewer/date/scope/defect record is added.

## Aggregate Fit (measured, 2026-07-13)

- Every benchmark target VALUE was checked against its cited primary source.
  Most did not survive: the old `degree_tail_exponent` 2.5 appears nowhere in
  Barabasi & Albert 1999 (which reports 2.3 +/- 0.1); the old `clustering` 0.2
  matches no network Mislove et al. 2007 measured; a Twitter clustering value
  was attributed to a paper that reports no clustering coefficient at all; the
  ad-CTR and appeal-rate targets were off by roughly an order of magnitude and
  a factor of two respectively. Corrected values, each quoting the sentence or
  table cell it came from, are in
  `socio_sim/data/benchmarks/sourced_aggregates_v1.json`. The unverifiable sets
  are retired to `legacy_unsupported_*.json`.
- **The BASE model does not reproduce the corrected targets: I = 6.03**, far
  outside the 3-sigma history-matching cutoff (degree tail 2.90 vs 2.30+/-0.10;
  diurnal peak 17h vs 20h). Published, not tuned away. The
  `aggregate_matched_prototype` profile has since been genuinely
  history-matched to the source-checked targets by moving model parameters
  only (a configuration-model graph for the ~2.3 tail, triadic closure for
  clustering, a diurnal shift to the source-checked evening peak, an ad-CTR
  multiplier toward the source-checked display measurement) -- no target or
  tolerance was touched -- reaching I = 2.50 with the structural graph/temporal
  aggregates in band and the ad/appeal residuals (from incompatible real
  surfaces) near the edge. A pass there is NOT validation/calibration/
  prediction; it is one labelled configuration reproducing seven aggregates to
  within their tolerances. Full write-up: `docs/AGGREGATE_FIT_FINDINGS.md`.
- Even a good fit would not license validation/calibration/prediction claims:
  the sources measure different populations, metric definitions (Mislove's
  clustering is directed; the simulator's is undirected) and periods. Each
  target carries its own `applicability_limits`.

## Security And Reproducibility

- The Docker base is pinned by digest and runs as a non-root user.
- SBOM generation guidance is in the Dockerfile comment; dependency audit,
  Bandit, secret scan, evidence gate, claim scan, asset QA, and wheel asset
  checks are CI gates.
- The GPU/CuPy path and optional external image/LLM backends are not validated by
  default local CI.
- The SSRF guard on `llm_base_url` checks the allow-list on every transport
  call and TCP-connects to the exact IP it checked (hostname kept for the
  Host header and TLS SNI), so there is no second DNS lookup for a
  rebinding server to exploit; redirects are refused outright (audit
  finding E-05, closed). The remaining trust boundary is the resolver at
  the moment of the check itself.
- Ad conversions whose latency crosses the end of the run are dropped while
  organic conversions have zero latency, so impressions in the final few
  ticks lose credit only in the exposed arm: lift is biased toward zero
  near the horizon (conservative, never inflating). Standard campaign-end
  censoring; audit finding F5.
- CI runs an automated axe-core scan (`tests/test_a11y_axe.py`) that fails on
  any serious/critical violation of the machine-checkable WCAG **2.2** A+AA
  rules, on the initial and rendered views, in both themes (0 violations as of
  2026-07-13), plus scripted keyboard, skip-link, target-size, 320px-reflow and
  200%-zoom checks. Automated scanning still covers only part of WCAG, **no
  screen-reader user testing has been done, and ADA certification is NOT
  claimed** — see `docs/ACCESSIBILITY.md` for the criterion-by-criterion
  self-audit and its stated gaps.
