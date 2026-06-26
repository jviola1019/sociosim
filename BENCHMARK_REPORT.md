# SocioSim Measured-Classifier Benchmark Report

> Provenance: **measured-on-benchmark** — the moderation classifier's precision/recall/F1/ROC-AUC measured on REAL, license-clean, de-identified public datasets (see `docs/DATA_MANIFEST.md`). Deterministic (seeded split + zero-init logistic regression). This is the highest rung of the validation ladder: a measured component, not a synthetic estimate.

| benchmark | task | license | n_test | F1 | ROC-AUC | Brier | log-loss | ECE |
|---|---|---|---|---|---|---|---|---|
| civil_comments | toxicity | CC0-1.0 | 600 | 0.736 | 0.805 | 0.181 | 0.544 | 0.040 |
| spam_detection | spam | Apache-2.0 | 600 | 0.990 | 0.999 | 0.011 | 0.045 | 0.020 |

### Proper scoring vs a climatology baseline (Brier Skill Score)
Brier/log-loss are proper scoring rules (lower = better); the baseline is the no-skill *climatology* forecast (constant = training prevalence). Brier Skill Score = 1 − Brier/Brier_baseline (> 0 means the model beats climatology on REAL held-out data).

| benchmark | Brier | Brier_climatology | Brier Skill Score | log-loss | log-loss_climatology |
|---|---|---|---|---|---|
| civil_comments | 0.181 | 0.250 | 0.275 | 0.544 | 0.693 |
| spam_detection | 0.011 | 0.250 | 0.958 | 0.045 | 0.693 |

## Honest scope
- These are REAL measured metrics on real public benchmarks — usable by businesses/governments under the datasets' licenses (CC0-1.0, Apache-2.0).
- The classifier is a transparent numpy logistic-regression over hashed features (auditable, deterministic), not a black-box LLM — a deliberate trade of peak accuracy for reproducibility + explainability.
- Brier/log-loss are scored against the datasets' REAL labels (real outcomes), and beat the no-skill climatology baseline (positive Brier Skill Score). For honest context, published transformer SOTA on these tasks scores higher (toxicity AUC ~0.95+); this transparent numpy LR is a strong, auditable baseline, not SOTA. We do NOT claim to beat real-world market/production systems — that needs their outcome data and is out of scope (would be fabrication).
- Measures the CLASSIFIER COMPONENT only; it does not make the synthetic agent-based simulation itself predictive of real platforms.
- Text was PII-scrubbed (emails/URLs/phones/@handles redacted) on top of the sources' own de-identification; no decisions about real individuals.