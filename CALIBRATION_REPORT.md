# Calibration Report — history-matched profile

**Method.** History matching against the bundled *published-aggregate* benchmark
targets (`default` set). Implausibility `I = max_j |observed_j - target_j| /
tolerance_j` (Spec §3.9); conventional cutoff `I < 3`. A configuration is
calibration-consistent when the aggregate implausibility stays below that cutoff.

**What was tuned.** The default Barabási–Albert graph has near-zero clustering
(~0.04) versus the target 0.2. Switching to a **Holme–Kim power-law-cluster
graph** (`graph_kind="plc"`) adds tunable triangle formation via the triad
probability `p` while preserving a heavy-tailed degree distribution. A history
match over `p ∈ [0.2, 0.7]` selected **p = 0.7, m = 5** (quick scale, EU).
Captured via `RunConfig.calibrated()` and the `--profile calibrated` CLI option.

**Result (deterministic; replay-verified).**

| observable            | observed |   target ± tol | z (std. discrepancy) |
|-----------------------|---------:|---------------:|---------------------:|
| ad_ctr                |  0.0000  |  0.010 ± 0.008 | 1.25 |
| appeal_grant_rate     |  0.1429  |  0.250 ± 0.150 | 0.71 |
| clustering            |  0.2428  |  0.200 ± 0.100 | 0.43 |
| degree_tail_exponent  |  2.7577  |  2.500 ± 0.500 | 0.52 |
| diurnal_peak_hour     | 17.0000  | 17.000 ± 2.000 | 0.00 |
| diurnal_trough_hour   |  3.0000  |  5.000 ± 2.000 | 1.00 |
| posts_per_agent_day   |  0.5240  |  0.500 ± 0.350 | 0.07 |

**Implausibility I = 1.25** (cutoff 3.0), dominated by `ad_ctr` in the sparse
quick-scale calibrated run. Deterministic replay of the calibrated run verifies
bit-identically. Baseline (uncalibrated BA) was `I = 1.667` with clustering at
`z = 1.61`.

**Honest scope.** This is *calibration consistency* against published **aggregate**
statistics with deliberately wide tolerances — not predictive validation. The
simulator remains a synthetic agent-based model (research-only; outputs are
counterfactual projections, not predictions). The calibrated profile makes the
default-world structure plausible w.r.t. real platforms; it does not certify any
downstream effect estimate. Other bundled target sets (`twitter_like`,
`facebook_like`) can be calibrated the same way with `RunConfig.calibrated(
benchmark=...)` and re-running the history match.
