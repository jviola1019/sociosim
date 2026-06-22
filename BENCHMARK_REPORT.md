# SocioSim Measured-Classifier Benchmark Report

> Provenance: **measured-on-benchmark** — the moderation classifier's precision/recall/F1/ROC-AUC measured on REAL, license-clean, de-identified public datasets (see `docs/DATA_MANIFEST.md`). Deterministic (seeded split + zero-init logistic regression). This is the highest rung of the validation ladder: a measured component, not a synthetic estimate.

| benchmark | task | license | n_train | n_test | precision | recall | F1 | ROC-AUC |
|---|---|---|---|---|---|---|---|---|
| civil_comments | toxicity | CC0-1.0 | 2400 | 600 | 0.696 | 0.746 | 0.720 | 0.783 |
| spam_detection | spam | Apache-2.0 | 2400 | 600 | 0.989 | 0.975 | 0.982 | 0.998 |

## Honest scope
- These are REAL measured metrics on real public benchmarks — usable by businesses/governments under the datasets' licenses (CC0-1.0, Apache-2.0).
- The classifier is a transparent numpy logistic-regression over hashed features (auditable, deterministic), not a black-box LLM — a deliberate trade of peak accuracy for reproducibility + explainability.
- Measures the CLASSIFIER COMPONENT only; it does not make the synthetic agent-based simulation itself predictive of real platforms.
- Text was PII-scrubbed (emails/URLs/phones/@handles redacted) on top of the sources' own de-identification; no decisions about real individuals.