# SocioSim Validation Report

> Provenance: **synthetic exploratory**. Behaviour parameters are not empirically calibrated; this report records their sensitivity and the run's distance from published aggregate benchmarks. It is NOT evidence that the simulator predicts real behaviour.

Profile `test` · 200 agents × 48 ticks · seed 42.

## 1. Sensitivity of posts/agent to BehaviorParams
First-order variance-based indices (LHS, n=16; output mean 0.8872, sd 0.2467).

| BehaviorParam | first-order index S1 |
|---|---|
| `p_post_given_active` | 0.988 |
| `p_flag_scale` | 0.766 |
| `p_share_given_engaged` | 0.639 |
| `impression_fatigue` | 0.317 |
| `engagement_base` | 0.203 |

Interpretation: parameters with high S1 dominate this output and MUST be calibrated (or their dependent claims flagged uncalibrated) before use. Low-S1 parameters are safe to leave at documented defaults.

## 1b. Multi-output sensitivity (Sobol design, multi-seed)
First-order indices for 3 outputs over a Sobol design (n=16) averaged across 3 seeds (mean ± sd of S1 across seeds).

| BehaviorParam | n_posts | harmful_exposure_rate | welfare_mean |
|---|---|---|---|
| `engagement_base` | 0.766±0.008 | 0.354±0.122 | 0.574±0.088 |
| `impression_fatigue` | 0.953±0.007 | 0.541±0.197 | 0.476±0.242 |
| `p_flag_scale` | 0.104±0.115 | 0.443±0.224 | 0.614±0.023 |
| `p_post_given_active` | 0.986±0.003 | 0.754±0.054 | 0.542±0.147 |
| `p_share_given_engaged` | 0.098±0.094 | 0.389±0.158 | 0.500±0.164 |

## 2. Calibration vs published benchmarks
Implausibility **I = 1.80** (history-matching cutoff 3.0; I<3 = not implausible).
Diurnal distribution KS gap = 0.048 (0 = posting-hour distribution matches the diurnal curve exactly).

| Target | observed | benchmark | tolerance | within tol? |
|---|---|---|---|---|
| degree_tail_exponent | 3.4007 | 2.5 | 0.5 | NO |
| clustering | 0.1122 | 0.2 | 0.1 | yes |
| diurnal_peak_hour | 20.0000 | 17 | 2 | NO |
| diurnal_trough_hour | 4.0000 | 5 | 2 | yes |
| posts_per_agent_day | 0.4500 | 0.5 | 0.35 | yes |
| ad_ctr | 0.0075 | 0.01 | 0.008 | yes |
| appeal_grant_rate | n/a | 0.25 | 0.15 | — |

## 2b. Parameter-uncertainty propagation (ABC posterior -> output)
Calibrated `posts_per_agent_day` over 8 accepted parameter sets (provenance: abc-posterior-propagated): median 0.4975, 95% [0.4229, 0.5999].

## 3. Limitations
- Bounds are +/-50% of defaults, not empirically derived.
- Section 1b now sweeps MULTIPLE outputs over a Sobol design across MULTIPLE seeds; section 1 keeps the single-output LHS view for continuity. Indices are first-order only (no higher-order/total effects).
- Benchmark targets are coarse published aggregates with wide tolerances; use `--profile calibrated` for a history-matched, in-band configuration.
- `degree_tail_exponent` / network targets depend on the graph model, not BehaviorParams.