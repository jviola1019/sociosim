# Statistical validation + model-fit work — handoff / plan

Branch `feat/durability-ops-hardening`. Two user mandates:
1. Fix the two open "errors": I = 6.03 aggregate misfit, and branch
   protection (DONE — repo made public 2026-07-14, `main` now requires the
   `test` check, strict, no force-push/delete).
2. Every model and output must be statistically/analytically validated
   across ALL code, not only recently-touched files.

An independent statistical audit (2026-07-14) reviewed every stat function.
Confirmed correct: Wilson/Newcombe/two-proportion-z, BH FDR + q-values,
MDE, discrete KS, Saltelli S1/ST, ROC-AUC (tie-corrected), Brier, log-loss,
ECE, average_clustering, assortativity, moderation confusion, fairness,
cascades, lift/attribution/incrementality NaN handling.

## Segment 1 — statistical-validity fixes (do first; correctness, low risk)

- **P1 calibration_slope** (`benchmark_eval.py`): currently an OLS slope of
  the 0/1 outcome on logit(p̂); NOT the Cox/Van Calster logistic
  calibration slope (=1 iff calibrated). Fix to a 1-D logistic-regression
  slope (Newton steps), keep it ≈1 for well-calibrated data. Test it.
- **P1 hill_exponent** (`targets.py`): use the (k+1)-th largest as the
  threshold (not the k-th, which self-includes a zero term and biases up);
  numerator = number of tail terms actually summed (fixes the len<10
  mismatch); degenerate tail (Σlog=0) → NaN not +inf. Add a small-k test.
- **P1 first_order_indices** (`sensitivity.py`): the binned
  correlation-ratio floor (~1/samples-per-bin) can read ≈0.5 for a null
  parameter on small designs; require ≥ ~10 samples/bin or document +
  point callers at saltelli_indices.
- **P2 harmful_exposure CI** (`analytics/metrics.py`): point estimate is
  impression-pooled but the CI bootstraps the unweighted per-agent mean —
  different estimand. Make the CI match (resample matching the pooled rate).
- **P3 CUPED θ** (`ads/measure.py`): np.cov (ddof=1) ÷ np.var (ddof=0) →
  N/(N−1) bias; use one consistent ddof.
- Guards + tests: tolerance=0 in `implausibility_components` → NaN guard;
  add stat-property tests for prob_diff_positive, calibration_slope,
  homophily_index (closed form), and pin ≥1 closed-form value for Wilson,
  Newcombe, two-proportion.

None of these touch the event stream, so determinism hashes are unaffected
(they are analysis/reporting functions). Some change reported summary
numbers (hill), so range-asserting tests may need updating.

## Segment 2 — model fit to the VERIFIED aggregates (error #1)

Feasibility probed: a configuration-model graph with a target exponent
gives γ≈2.34 (target 2.3±0.1, z≈0.4); degree-preserving triangle swaps lift
clustering to ~0.09 (z≈1.5, under cutoff). Plan, all ADDITIVE so default/
quick behaviour and determinism stay unchanged:
- new graph kind `cm` (configuration model + triangle swaps), deterministic
  from the seed tree;
- make the diurnal peak phase a config field (default = current 17h → no
  determinism change); `aggregate_matched_prototype` sets it to 20h to match
  the verified Golder 2007 source;
- point `aggregate_matched_prototype.benchmark` back at
  `sourced_aggregates_v1` and history-match its params; verify ad_ctr /
  appeal_grant_rate are non-zero at that profile's scale;
- report the achieved implausibility HONESTLY in
  docs/AGGREGATE_FIT_FINDINGS.md — a pass is a real result for that
  explicitly-labelled profile, with all population caveats intact; never
  widen a tolerance or edit a verified value to get there.

## Segment 3 — full verify, merge PR #7 on user say-so, prove merged-SHA CI.
