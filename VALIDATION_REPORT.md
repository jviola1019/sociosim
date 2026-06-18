# SocioSim Validation Report

> Provenance: **synthetic exploratory**. Behaviour parameters are not empirically calibrated; this report records their sensitivity and the run's distance from published aggregate benchmarks. It is NOT evidence that the simulator predicts real behaviour.

Profile `test` · 200 agents × 48 ticks · seed 42.

## 1. Sensitivity of posts/agent to BehaviorParams
First-order variance-based indices (LHS, n=24; output mean 0.8977, sd 0.2533).

| BehaviorParam | first-order index S1 |
|---|---|
| `p_post_given_active` | 0.990 |
| `engagement_base` | 0.673 |
| `impression_fatigue` | 0.556 |
| `p_share_given_engaged` | 0.501 |
| `p_flag_scale` | 0.333 |

Interpretation: parameters with high S1 dominate this output and MUST be calibrated (or their dependent claims flagged uncalibrated) before use. Low-S1 parameters are safe to leave at documented defaults.

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
Calibrated `posts_per_agent_day` over 12 accepted parameter sets (provenance: abc-posterior-propagated): median 0.4900, 95% [0.4002, 0.5886].

## 3. Limitations
- Bounds are +/-50% of defaults, not empirically derived.
- Single output (posts/agent) and a single seed; a full study sweeps multiple outputs and many seeds (Monte Carlo).
- Benchmark targets are coarse published aggregates with wide tolerances.
- `degree_tail_exponent` / network targets depend on the graph model, not BehaviorParams.