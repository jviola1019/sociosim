# Ethics, Appropriate Use, and Limitations

## Appropriate uses

- Hypothesis generation and stress-testing of moderation policies.
- Comparing jurisdictional regimes (US §230 / EU DSA / CN labelling) on
  synthetic populations.
- Designing marketing experiments (holdouts, disclosure compliance) before
  costly real-world trials.
- Training moderators on synthetic queues; exploring unintended consequences.

## Prohibited uses

SocioSim must **not** be used to:

- target, rank, profile, or otherwise make decisions about real individuals;
- predict real-world protests, elections, or other events;
- generate or justify enforcement decisions on real platforms;
- optimise real-world manipulation, influence operations, or evasion of
  moderation;
- launder synthetic results as empirical findings.

## Epistemic status of outputs

Outputs are **counterfactual projections under stated assumptions**. Headline
metrics carry a 95% interval whose *provenance is labelled* — within-run
bootstrap, analytic Wilson/Beta credible, or Monte Carlo percentile. A single
(Preview) run reports **within-run sampling uncertainty only**; it is not Monte
Carlo across replicates. Monte Carlo replication is available via the
multi-replicate research run (`validation.montecarlo.run_replicates` and the
experiment runner) — use it before treating an interval as simulation
uncertainty. The behavioural rules are calibrated to
aggregate published statistics, not fitted to any specific platform; absolute
levels are less trustworthy than *directional, paired comparisons* under
common random numbers.

## Known limitations (v1)

1. Agent behaviour is rule-based with simple belief dynamics; no strategic
   reasoning or long-memory effects.
2. Media items are simulated as typed metadata (no actual image/video
   synthesis); CN labelling logic operates on metadata fields.
3. Classifiers are calibrated noise models (configurable precision/recall),
   not real content models — adequate for FP/FN cost analysis, not for
   evaluating real classifiers.
4. Built-in calibration targets are coarse published aggregates with wide
   tolerances; conclusions sensitive to them should be re-run against your
   own anonymised data via the targets loader.
5. Single-machine scale (10k agents standard). Larger scales need engine work.
6. Legal packs are research approximations of DSA/§230/CN/FTC obligations,
   not legal advice; consult counsel before drawing compliance conclusions.

## Privacy & safety design

- Personas are entirely synthetic; no individual-level data is ingested.
- Logs contain structured rationales only — never chain-of-thought, never PII.
- The Claude adapter stores only generated post text in its cache.

## Residual risks

- Misreading projections as predictions (mitigated by disclaimers + CIs, not
  eliminated).
- Using red-team scenarios as manipulation recipes: scenarios are coarse
  archetypes published for defensive stress-testing; they contain no
  operational evasion detail.
- Calibration drift: rerun backtests when updating behaviour rules or targets.
