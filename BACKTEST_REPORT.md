# SocioSim Backtest & Stylized-Facts Report

> Provenance: **held-out-aggregate** + **stylized-fact-validated**. Calibration uses only bundled PUBLISHED AGGREGATE targets (no individual-level data; see `docs/DATA_MANIFEST.md`). This validates AGGREGATE / PATTERN agreement with real systems — NOT point-prediction of any specific platform or person (Rung 2–3 of the validation ladder; see `docs/usage.md`).

## 1. Held-out aggregate backtest — `default` (profile `quick`)
Calibrated graph triad p = **0.3** on the TRAIN metrics (ad_ctr, appeal_grant_rate, clustering, diurnal_trough_hour, posts_per_agent_day); implausibility I_train = 1.25.

Held-out metrics — never used to choose p — scored as aggregate sanity checks (I_test = 0.44): **PASS**.

| held-out metric | observed | target ± tol | z | within? |
|---|---|---|---|---|
| degree_tail_exponent | 2.7223 | 2.5 ± 0.5 | 0.44 | yes |
| diurnal_peak_hour | 17.0000 | 17 ± 2 | 0.00 | yes |

## 2. Stylized facts — face validity vs documented regularities
5/5 empirical regularities reproduced.

| stylized fact | observed | band | passes | source |
|---|---|---|---|---|
| heavy_tailed_degree | 2.758 | [2.0, 3.6] | yes | Power-law degree exponent ~2–3 in social networks (Barabási & Albert 1999; Clauset, Shalizi & Newman 2009) |
| clustering_exceeds_random | 24.457 | [3.0, ∞] | yes | Real networks are far more clustered than random graphs (Watts & Strogatz 1998) |
| cascade_right_skew | 9.000 | [2.0, ∞] | yes | Most diffusion cascades die quickly; a few go viral — heavy-tailed cascade sizes (Goel, Watts & Goldstein 2012) |
| participation_inequality | 0.350 | [0.3, 1.0] | yes | Participation inequality — a small minority makes most posts (Nielsen '90-9-1'; van Mierlo 2014) |
| diurnal_cycle | 1.626 | [1.5, ∞] | yes | Diurnal/circadian posting cycle (Golder & Macy 2011) |

## Limitations / honest scope
- Validates **aggregate / pattern** agreement against PUBLISHED AGGREGATES only — not point-prediction of a specific platform or individual.
- Synthetic agents: behavioural magnitudes remain calibrated assumptions; real-person microdata is deliberately NOT used (lawful by design — no PII, no scraping). Decisions about real individuals are out of scope.