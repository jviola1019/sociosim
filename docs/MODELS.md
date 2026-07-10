# Model and Evidence Boundaries

SocioSim is an evidence-first synthetic scenario simulator. It can test software
mechanics, deterministic replay, policy workflow logic, and synthetic scenario
comparisons. It cannot present synthetic assumptions as measured evidence.

## Classifier Modes

- `synthetic_noise_classifier`: scores are generated from configured scenario
  operating points and category base-rate assumptions.
- `synthetic_template_classifier`: a deterministic logistic-regression artifact
  is fitted during runtime on synthetic template text with category signal
  tokens.

Neither runtime mode is a real deployable classifier. Component benchmark
diagnostics from `validation/benchmark_eval.py` apply only to the benchmark
artifact produced by that command.

## Validation Ladder

The ladder defines six labels; only the three marked "exercised" are
currently produced by code (`validation/stylized.py`,
`validation/backtest.py`, `validation/benchmark_eval.py`) — the other three
are defined rungs with no supporting artifact yet:

- `synthetic_mechanism_check` (exercised)
- `aggregate_fit_check` (exercised)
- `external_temporal_holdout` (defined only)
- `external_platform_holdout` (defined only)
- `component_benchmark` (exercised)
- `operational_validation` (defined only)

Current built-in aggregate target files have incomplete metadata for external
validation claims. They may be used only as synthetic aggregate-fit diagnostics
until source version, source hash, date range, population, unit, tolerance
rationale, and disjoint train/evaluation target metadata are complete.

## Uncertainty

Within-run resampling is labeled:

`descriptive resampling interval under agent-independence approximation`

Replicate-level simulation uncertainty, parameter uncertainty, source
measurement uncertainty, and structural model uncertainty are separate and must
not be merged into one confidence claim.

## Advertising Measurement

Ad outputs are synthetic scenario diagnostics. The latent-propensity adjustment
is named `oracle_covariate_adjusted_simulation_diagnostic` because it uses a
simulated covariate unavailable in real experiments. ROAS, iROAS, CAC, LTV, CTR,
CVR, bids, conversion values, and attribution windows are scenario assumptions
unless supplied and evidenced by the user.
