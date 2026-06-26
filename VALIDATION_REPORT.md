# SocioSim Validation Report

> Provenance: **synthetic exploratory**. Behaviour parameters are not empirically calibrated; this report records their sensitivity and the run's distance from published aggregate benchmarks. It is NOT evidence that the simulator predicts real behaviour.

Profile `quick` · 1000 agents × 168 ticks · seed 42.

## 1. Sensitivity of posts/agent to BehaviorParams
First-order variance-based indices (LHS, n=24; output mean 3.7007, sd 1.0632).

| BehaviorParam | first-order index S1 |
|---|---|
| `p_post_given_active` | 0.986 |
| `engagement_base` | 0.687 |
| `impression_fatigue` | 0.526 |
| `p_share_given_engaged` | 0.512 |
| `p_flag_scale` | 0.360 |

Interpretation: parameters with high S1 dominate this output and MUST be calibrated (or their dependent claims flagged uncalibrated) before use. Low-S1 parameters are safe to leave at documented defaults.

## 1b. Multi-output sensitivity (Sobol design, multi-seed)
First-order indices for 3 outputs over a Sobol design (n=32) averaged across 3 seeds (mean ± sd of S1 across seeds).

| BehaviorParam | n_posts | harmful_exposure_rate | welfare_mean |
|---|---|---|---|
| `engagement_base` | 0.098±0.072 | 0.393±0.102 | 0.729±0.067 |
| `impression_fatigue` | 0.779±0.026 | 0.547±0.075 | 0.339±0.145 |
| `p_flag_scale` | 0.762±0.025 | 0.610±0.063 | 0.358±0.090 |
| `p_post_given_active` | 0.979±0.005 | 0.409±0.041 | 0.277±0.063 |
| `p_share_given_engaged` | 0.778±0.025 | 0.383±0.100 | 0.610±0.135 |

## 1c. Saltelli first-order + TOTAL-effect indices
Gold-standard variance-based sensitivity for `n_posts` (A/B/AB_i design, 56 model runs, N=8). ST ≥ S1; ST≈0 ⇒ the parameter can be fixed.

| BehaviorParam | S1 (first-order) | ST (total-effect) |
|---|---|---|
| `engagement_base` | 0.000 | 0.001 |
| `impression_fatigue` | 0.000 | 0.001 |
| `p_flag_scale` | 0.028 | 0.000 |
| `p_post_given_active` | 0.669 | 0.524 |
| `p_share_given_engaged` | 0.000 | 0.024 |

## 2. Calibration vs published benchmarks
Implausibility **I = 1.67** (history-matching cutoff 3.0; I<3 = not implausible).
Diurnal distribution KS gap = 0.010 (0 = posting-hour distribution matches the diurnal curve exactly).

| Target | observed | benchmark | tolerance | within tol? |
|---|---|---|---|---|
| degree_tail_exponent | 2.9029 | 2.5 | 0.5 | yes |
| clustering | 0.0385 | 0.2 | 0.1 | NO |
| diurnal_peak_hour | 17.0000 | 17 | 2 | yes |
| diurnal_trough_hour | 4.0000 | 5 | 2 | yes |
| posts_per_agent_day | 0.5230 | 0.5 | 0.35 | yes |
| ad_ctr | 0.0107 | 0.01 | 0.008 | yes |
| appeal_grant_rate | 0.0000 | 0.25 | 0.15 | NO |

## 2b. Parameter-uncertainty propagation (ABC posterior -> output)
Calibrated `posts_per_agent_day` over 12 accepted parameter sets (provenance: abc-posterior-propagated): median 0.5073, 95% [0.4010, 0.5986].

## 3. Limitations
- Bounds are +/-50% of defaults, not empirically derived.
- Section 1b sweeps MULTIPLE outputs (Sobol, multi-seed); section 1c adds Saltelli first-order S1 AND total-effect ST (interactions); section 1 keeps the single-output correlation-ratio view for continuity.
- Benchmark targets are coarse published aggregates with wide tolerances; use `--profile calibrated` for a history-matched, in-band configuration.
- `degree_tail_exponent` / network targets depend on the graph model, not BehaviorParams.