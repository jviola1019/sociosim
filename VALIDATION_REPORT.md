# SocioSim Validation Report

> Provenance: **synthetic exploratory**. Behaviour parameters are not empirically calibrated; this report records their sensitivity and the run's distance from published aggregate benchmarks. It is NOT evidence that the simulator predicts real behaviour.

Profile `quick` · 1000 agents × 168 ticks · seed 42.

## 1. Sensitivity of posts/agent to BehaviorParams
Screening first-order sensitivity indices (LHS/correlation-ratio approximation, n=4; output mean 3.4567, sd 0.9073). Treat small-n runs as ranking diagnostics, not a validated Sobol decomposition.

| BehaviorParam | first-order index S1 |
|---|---|
| `engagement_base` | 0.839 |
| `impression_fatigue` | 0.839 |
| `p_post_given_active` | 0.839 |
| `p_flag_scale` | 0.159 |
| `p_share_given_engaged` | 0.002 |

Interpretation: parameters with high screening indices should be calibrated (or dependent claims flagged uncalibrated) before use. Low indices in small-n runs are not proof that a parameter can be fixed.

## 1b. Multi-output sensitivity (Sobol design, multi-seed)
Screening first-order indices for 3 outputs over a Sobol design (n=4) averaged across 3 seeds (mean ± sd of S1 across seeds).

| BehaviorParam | n_posts | harmful_exposure_rate | welfare_mean |
|---|---|---|---|
| `engagement_base` | 0.086±0.052 | 0.214±0.180 | 0.538±0.310 |
| `impression_fatigue` | 0.713±0.102 | 0.508±0.137 | 0.058±0.069 |
| `p_flag_scale` | 0.713±0.102 | 0.508±0.137 | 0.058±0.069 |
| `p_post_given_active` | 0.713±0.102 | 0.508±0.137 | 0.058±0.069 |
| `p_share_given_engaged` | 0.086±0.052 | 0.214±0.180 | 0.538±0.310 |

## 1c. Saltelli first-order + TOTAL-effect indices
Saltelli-style variance-based sensitivity for `n_posts` (A/B/AB_i design, 28 model runs, N=4). Finite-sample estimates are noisy; ST can fall below S1 in small smoke runs and should be read as a robustness diagnostic.

| BehaviorParam | S1 (first-order) | ST (total-effect) |
|---|---|---|
| `engagement_base` | 0.021 | 0.009 |
| `impression_fatigue` | 0.003 | 0.000 |
| `p_flag_scale` | 0.033 | 0.000 |
| `p_post_given_active` | 3.779 | 2.047 |
| `p_share_given_engaged` | 0.084 | 0.007 |

## 2. Calibration vs published benchmarks
Implausibility **I = 1.67** (history-matching cutoff 3.0; I<3 = not implausible).
Diurnal distribution KS gap = 0.012 (0 = posting-hour distribution matches the diurnal curve exactly).

| Target | observed | benchmark | tolerance | within tol? |
|---|---|---|---|---|
| degree_tail_exponent | 2.9029 | 2.5 | 0.5 | yes |
| clustering | 0.0385 | 0.2 | 0.1 | NO |
| diurnal_peak_hour | 17.0000 | 17 | 2 | yes |
| diurnal_trough_hour | 3.0000 | 5 | 2 | yes |
| posts_per_agent_day | 0.5239 | 0.5 | 0.35 | yes |
| ad_ctr | 0.0000 | 0.01 | 0.008 | NO |
| appeal_grant_rate | 0.0000 | 0.25 | 0.15 | NO |

## 2b. Parameter-uncertainty propagation (ABC posterior -> output)
Calibrated `posts_per_agent_day` over 3 accepted parameter sets (provenance: abc-posterior-propagated): median 0.4297, 95% [0.3426, 0.5696].

## 3. Limitations
- Bounds are +/-50% of defaults, not empirically derived.
- Sections 1 and 1b are screening diagnostics, not proof of a stable Sobol decomposition at small sample sizes. Section 1c adds Saltelli first-order S1 and total-effect ST, but finite-sample estimates can be noisy.
- Benchmark targets are coarse published aggregates with wide tolerances; use `--profile calibrated` for a history-matched, in-band configuration.
- `degree_tail_exponent` / network targets depend on the graph model, not BehaviorParams.