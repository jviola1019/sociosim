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
- The SSRF guard on `llm_base_url` re-resolves DNS and re-checks the
  allow-list on every transport call and refuses redirects, but `urllib`
  performs its own DNS lookup after ours: a narrow DNS-rebind TOCTOU window
  remains. Closing it fully would require connecting to the pinned
  allow-listed IP with an explicit Host header; deferred as low-risk for a
  loopback-default, single-user tool (audit finding E-05).
- CI has no automated accessibility gate (e.g. axe-core): the WCAG-oriented
  pass in SECURITY.md was browser-verified manually, and no WCAG-AA
  conformance is claimed (audit finding G-02).
