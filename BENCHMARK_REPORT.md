# SocioSim Classifier Component Benchmark Diagnostics

> Scope: component benchmark only. These results do not validate the runtime synthetic template classifier or any simulation output.

| benchmark | task | license | leakage | n_test | F1 | ROC-AUC | Brier | log-loss | ECE |
|---|---|---|---|---|---|---|---|---|---|
| civil_comments | toxicity | CC0-1.0 | pass | 604 | 0.731 | 0.821 | 0.173 | 0.513 | 0.032 |
| spam_detection | spam | Apache-2.0 | pass | 604 | 0.989 | 1.000 | 0.009 | 0.040 | 0.022 |

## Artifact Metadata
- civil_comments: source_sha256 `19006bae1537c57c0942c50f23c688d4654d15782d01cf69186d6642c496099b`, model_hash `61f4b654971218ebbd73350c649d558d5c4624a37c0b259d853a5edaf1ecb629`, split `deterministic_normalized_text_group_split`, duplicate families 18
- spam_detection: source_sha256 `72eeffb09cadc6f47cd8f34994a00e45bf1c2685d2e48f8e60d0b3981c260150`, model_hash `ae2ed1ab0f66f7ec5539c1f6f89fa62534b2b82fb8b4d0a3b7d642f83535acaa`, split `deterministic_normalized_text_group_split`, duplicate families 16

## Limitations
- Benchmark metrics are regenerated from bundled data and attached hashes.
- They are valid only for this component evaluation protocol.
- They do not make SocioSim outputs operationally valid.