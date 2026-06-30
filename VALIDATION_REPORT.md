# SocioSim Validation-Ladder Diagnostics

> Scope: synthetic mechanism and aggregate-fit diagnostics only. Legacy target metadata is incomplete, so this report cannot display validation, calibration, backtest, confidence, or real-model seals.

Profile `test` · 200 agents × 48 ticks · seed 42.

## 1. Sensitivity of posts/agent to BehaviorParams
First-order variance-based indices (LHS, n=8; output mean 0.8812, sd 0.2671).

| BehaviorParam | first-order index S1 |
|---|---|
| `p_post_given_active` | 0.944 |
| `impression_fatigue` | 0.426 |
| `p_flag_scale` | 0.153 |
| `p_share_given_engaged` | 0.153 |
| `engagement_base` | 0.032 |

Interpretation: parameters with high S1 dominate this output and MUST be user-supplied or evidence-backed before use. Low-S1 parameters are safe to leave at documented defaults.

## 1b. Multi-output sensitivity (Sobol design, multi-seed)
First-order indices for 3 outputs over a Sobol design (n=8) averaged across 3 seeds (mean ± sd of S1 across seeds).

| BehaviorParam | n_posts | harmful_exposure_rate | welfare_mean |
|---|---|---|---|
| `engagement_base` | 0.953±0.016 | 0.589±0.236 | 0.612±0.096 |
| `impression_fatigue` | 0.161±0.112 | 0.490±0.247 | 0.387±0.190 |
| `p_flag_scale` | 0.775±0.033 | 0.507±0.084 | 0.508±0.149 |
| `p_post_given_active` | 0.953±0.016 | 0.589±0.236 | 0.612±0.096 |
| `p_share_given_engaged` | 0.953±0.016 | 0.589±0.236 | 0.612±0.096 |

## 1c. Saltelli first-order + TOTAL-effect indices
Gold-standard variance-based sensitivity for `n_posts` (A/B/AB_i design, 28 model runs, N=4). ST ≥ S1; ST≈0 ⇒ the parameter can be fixed.

| BehaviorParam | S1 (first-order) | ST (total-effect) |
|---|---|---|
| `engagement_base` | 0.174 | 0.015 |
| `impression_fatigue` | 0.000 | 0.000 |
| `p_flag_scale` | 0.046 | 0.013 |
| `p_post_given_active` | 3.964 | 1.979 |
| `p_share_given_engaged` | 0.032 | 0.002 |

## 2. Aggregate-fit diagnostics vs legacy benchmarks
Implausibility **I = 1.80** (history-matching cutoff 3.0; I<3 = not implausible).
Diurnal distribution KS gap = 0.048 (0 = posting-hour distribution matches the diurnal curve exactly).

| Target | observed | benchmark | tolerance | within tol? |
|---|---|---|---|---|
| degree_tail_exponent | 3.4007 | 2.5 | 0.5 | NO |
| clustering | 0.1122 | 0.2 | 0.1 | yes |
| diurnal_peak_hour | 20.0000 | 17 | 2 | NO |
| diurnal_trough_hour | 4.0000 | 5 | 2 | yes |
| posts_per_agent_day | 0.4500 | 0.5 | 0.35 | yes |
| ad_ctr | 0.0052 | 0.01 | 0.008 | yes |
| appeal_grant_rate | n/a | 0.25 | 0.15 | — |

## 2b. Parameter-uncertainty propagation (ABC posterior -> output)
Posterior-propagated `posts_per_agent_day` over 4 accepted parameter sets (provenance: abc-posterior-propagated): median 0.5038, 95% posterior interval [0.4447, 0.5512].

## 3. Limitations
- Bounds are +/-50% of defaults, not empirically derived.
- Section 1b sweeps MULTIPLE outputs (Sobol, multi-seed); section 1c adds Saltelli first-order S1 AND total-effect ST (interactions); section 1 keeps the single-output correlation-ratio view for continuity.
- Benchmark targets are coarse legacy aggregate summaries with incomplete metadata; use `--profile aggregate_matched_prototype` only as a synthetic scenario preset.
- `degree_tail_exponent` / network targets depend on the graph model, not BehaviorParams.