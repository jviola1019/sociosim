# NIST AI Risk Management Framework Mapping

How SocioSim's design aligns with the NIST AI RMF core functions (voluntary
adoption; trustworthiness across design, development, deployment).

## Govern

- Research-only use policy with explicit prohibited uses (README, ethics doc,
  run-time notice in every report).
- Versioned policy packs; package + pack versions recorded in every manifest.
- Design spec and implementation plan in-repo (`docs/superpowers/`).

## Map

- Intended context documented: counterfactual policy/marketing stress tests on
  synthetic populations.
- Known limitations enumerated (`docs/ethics_and_limitations.md`), including
  where outputs must not be trusted (absolute levels vs paired comparisons).
- Stakeholder impacts examined via fairness diagnostics on synthetic groups.

## Measure

- Uncertainty quantification mandatory: bootstrap CIs, Beta-Binomial
  posteriors, Monte Carlo percentile intervals on all reported metrics.
- Synthetic target-distance diagnostic computed against named legacy
  benchmark targets (target-distance scores, KS distances); these targets are
  evidence-kind `unsupported` (incomplete source metadata — see
  `SOURCE_LEDGER.md`) and the diagnostic is a mechanism check, not an
  empirical calibration claim. History matching + ABC give parameter credible
  intervals under the same synthetic-scenario caveat.
- Global sensitivity analysis identifies variance-driving parameters.
- Moderation quality measured as precision/recall/FPR/FNR with per-group
  disparity reporting.

## Manage

- Fail-closed policy floor (POLICY-GAP escalation) for unmatched severe
  content.
- Loud degradation: LLM failures emit `degradation` events and fall back —
  never silent.
- Full reproducibility: append-only logs + manifests + bit-identical replay
  verification support audit and incident review.
- Red-team scenario suite shipped and run as part of the automated test suite
  (`experiments.scenarios.red_team_suite`).
