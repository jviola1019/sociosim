# Data Manifest And Governance

Every shipped dataset or generated asset must have source, license/provenance,
PII status, source hash where applicable, and valid-use limits recorded before it
can support a claim.

## Governance Rules

1. No individual-level platform data is bundled.
2. No scraping is used for bundled data.
3. Licenses and redistribution basis must be recorded.
4. Real platform microdata would require a formal data-use agreement or vetted
   researcher access and must not be added ad hoc.
5. Outputs may not claim more than the dataset or asset evidence metadata allows.

## Bundled Aggregate Targets

| Dataset | Path | Status | Valid Use |
|---|---|---|---|
| Default targets | `socio_sim/data/benchmarks/default_targets.json` | legacy aggregate target manifest with incomplete evidence metadata | `aggregate_fit_check` only |
| Twitter-like targets | `socio_sim/data/benchmarks/twitter_like.json` | legacy aggregate target manifest with incomplete evidence metadata | `aggregate_fit_check` only |
| Facebook-like targets | `socio_sim/data/benchmarks/facebook_like.json` | legacy aggregate target manifest with incomplete evidence metadata | `aggregate_fit_check` only |

Invalid uses for these target files: empirical validation, calibration seals,
backtest seals, operational decisions, or real-platform prediction.

## Bundled Classifier Benchmark Samples

| Dataset | Path | Status | Valid Use |
|---|---|---|---|
| Civil Comments subset | `socio_sim/data/benchmarks/moderation/civil_comments.jsonl.gz` | bundled licensed benchmark sample with PII-like text scrubbed | `component_benchmark` diagnostics |
| Spam detection subset | `socio_sim/data/benchmarks/moderation/spam_detection.jsonl.gz` | bundled licensed benchmark sample with PII-like text scrubbed | `component_benchmark` diagnostics |

These samples diagnose benchmark algorithms and protocols. They do not make any
runtime classifier mode real-deployable and do not validate SocioSim outputs.

## Bundled V4 Assets

| Asset Set | Path | Status | Valid Use |
|---|---|---|---|
| v4 feed/ad/editorial PNGs | `socio_sim/web/static/assets/v4/` | deterministic project-owned synthetic decorative assets with registry hashes and QA status | UI decoration only |

v4 assets do not depict real people, brands, or KPIs and are not evidence.

## Active Validation-Ladder Labels

- `synthetic_mechanism_check`
- `aggregate_fit_check`
- `external_temporal_holdout`
- `external_platform_holdout`
- `component_benchmark`
- `operational_validation`

Current bundled artifacts support only `synthetic_mechanism_check`,
`aggregate_fit_check`, and `component_benchmark` in the limited senses above.
