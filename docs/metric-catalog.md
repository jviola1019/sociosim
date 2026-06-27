# Metric Catalog

This catalog defines headline metrics that can appear in reports, web payloads,
scenario files, and release checks.

| Metric | Formula / Source | Unit | Interpretation | Provenance | Limitations |
| --- | --- | --- | --- | --- | --- |
| `harmful_exposure_rate` | harmful feed impressions / total feed impressions | rate | Modeled exposure to harmful categories | `model_derived` | Depends on synthetic truth labels and feed logging. |
| `moderation_precision` | true positive moderation actions / all positive actions | rate | Share of actions matching synthetic truth | `model_derived` | Undefined when no positive actions occur. |
| `moderation_recall` | true positive actions / synthetic harmful items | rate | Share of harmful items acted on | `model_derived` | Undefined when no harmful items occur. |
| `appeal_grant_rate` | granted appeals / filed appeals | rate | Modeled appeal restoration rate | `model_derived` | Sensitive to appeal filing assumptions. |
| `welfare_mean` | engagement affinity minus harm/fatigue penalties | index | Synthetic welfare proxy | `model_derived` | Not human welfare. |
| `ad_ctr` | clicks / impressions | rate | Synthetic click-through | `model_derived` | Not a real campaign estimate. |
| `ad_cvr` | conversions / clicks | rate | Synthetic conversion rate | `model_derived` | Depends on scenario conversion assumptions. |
| `ad_lift_itt` | exposed conversion rate - holdout conversion rate | rate delta | Holdout-based synthetic incrementality diagnostic | `model_derived` | Aggregate MC version is an exposure-weighted diagnostic across campaigns. |
| `ad_roas` | synthetic revenue / synthetic spend | ratio | Synthetic scenario economics | `synthetic_assumption` | Not real financial performance. |
| `ad_disclosure_rate` | disclosed campaigns / campaigns | rate | FTC disclosure scenario compliance proxy | `model_derived` | Not legal compliance certification. |

Required event fields vary by metric but include `kind`, `tick`, `actor_id`,
`content_id`, and metric-specific structured data such as `action`, `price`,
`campaign_id`, `true_categories`, `stage`, or `granted`.
