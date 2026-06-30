# Ethics, Appropriate Use, and Limitations

## Appropriate Uses

- Hypothesis generation and stress-testing of moderation policies.
- Comparing jurisdictional regimes on synthetic populations.
- Designing marketing experiments before costly real-world trials.
- Training moderators on synthetic queues and exploring unintended consequences.

## Prohibited Uses

SocioSim must not be used to:

- target, rank, profile, or otherwise make decisions about real individuals;
- predict real-world protests, elections, or other events;
- generate or justify enforcement decisions on real platforms;
- optimize real-world manipulation, influence operations, or evasion of
  moderation;
- launder synthetic results as empirical findings.

## Epistemic Status

Outputs are synthetic scenario diagnostics under stated assumptions. Single-run
intervals are descriptive resampling intervals under an agent-independence
approximation, or analytic diagnostics for the synthetic run. They are not
empirical confidence claims about a real platform.

Monte Carlo replication remains separate from parameter, source, and structural
uncertainty. Behavioural rules are scenario assumptions checked only against
legacy aggregate-fit diagnostics, not fitted to any specific platform.

## Known Limitations

1. Agent behaviour is rule-based with simple belief dynamics; no strategic
   reasoning or long-memory effects.
2. Media items carry typed metadata for policy logic, and optional deterministic
   synthetic PNG/APNG media can be synthesized for previews/demos.
3. The default classifier is `synthetic_noise_classifier`. The optional
   `synthetic_template_classifier` is trained on synthetic category-signal text.
   Component benchmarks do not make either mode real-deployable.
4. Built-in legacy aggregate targets are coarse published aggregates with wide
   tolerances and incomplete evidence metadata; they support aggregate-fit
   diagnostics only.
5. Single-machine scale is the supported operating envelope for now.
6. Legal packs are research approximations, not legal advice; consult counsel
   before drawing compliance conclusions.

## Privacy And Safety Design

- Personas are entirely synthetic; no individual-level data is ingested.
- Logs contain structured rationales only, never chain-of-thought or PII.
- LLM caches store generated post text plus semantic guard metadata.

## Residual Risks

- Misreading synthetic diagnostics as predictions, mitigated by disclaimers but
  not eliminated.
- Using red-team scenarios as manipulation recipes; scenarios are coarse
  archetypes published for defensive stress-testing.
- Evidence drift: rerun gates and aggregate-fit diagnostics when updating
  behaviour rules or target manifests.
