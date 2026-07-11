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
- CI runs an automated axe-core scan (`tests/test_a11y_axe.py`) that fails
  on any serious/critical violation of the WCAG 2.0/2.1 A+AA machine-
  checkable rules, on both the initial and rendered dashboard views (audit
  finding G-02, closed). Automated scanning covers only a subset of WCAG
  success criteria, so a passing scan is an automated-scan result, not a
  WCAG-AA conformance claim; the manual keyboard/ARIA pass is recorded in
  SECURITY.md.
