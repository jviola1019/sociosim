# SocioSim Aggregate-Fit Diagnostics Report

> Scope: synthetic aggregate-fit diagnostics only. Legacy target files have incomplete source metadata and cannot support validation, backtest, calibration, or confidence seals.

## 1. Held-out aggregate diagnostic — `default` (profile `quick`)
Selected graph triad p = **0.6** on the TRAIN metrics (ad_ctr, appeal_grant_rate, clustering, diurnal_trough_hour, posts_per_agent_day); implausibility I_train = 1.25.

Held-out metrics are reported as synthetic diagnostics (I_test = 0.12).

| held-out metric | observed | target ± tol | z | within? |
|---|---|---|---|---|
| degree_tail_exponent | 2.5613 | 2.5 ± 0.5 | 0.12 | yes |
| diurnal_peak_hour | 17.0000 | 17 ± 2 | 0.00 | yes |

## 2. Synthetic mechanism checks
5/5 mechanism checks fell inside their bands.

| stylized fact | observed | band | passes | source |
|---|---|---|---|---|
| heavy_tailed_degree | 2.758 | [2.0, 3.6] | yes | Power-law degree exponent ~2–3 in social networks (Barabási & Albert 1999; Clauset, Shalizi & Newman 2009) |
| clustering_exceeds_random | 24.457 | [3.0, ∞] | yes | Real networks are far more clustered than random graphs (Watts & Strogatz 1998) |
| cascade_right_skew | 6.000 | [2.0, ∞] | yes | Most diffusion cascades die quickly; a few go viral — heavy-tailed cascade sizes (Goel, Watts & Goldstein 2012) |
| participation_inequality | 0.349 | [0.3, 1.0] | yes | Participation inequality — a small minority makes most posts (Nielsen '90-9-1'; van Mierlo 2014) |
| diurnal_cycle | 1.665 | [1.5, ∞] | yes | Diurnal/circadian posting cycle (Golder & Macy 2011) |

## Limitations / honest scope
- Does not validate aggregate or pattern agreement with a real platform.
- Synthetic agents: behavioural magnitudes remain scenario assumptions; real-person microdata is deliberately NOT used (lawful by design — no PII, no scraping). Decisions about real individuals are out of scope.