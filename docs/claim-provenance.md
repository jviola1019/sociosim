# Claim Provenance

Every user-visible result should be labeled with one of these classes:

| Class | Meaning |
| --- | --- |
| `model_derived` | Computed from a simulation run under declared assumptions. |
| `calibration_consistent` | Consistent with named aggregate calibration targets. |
| `aggregate_backtested` | Compared with held-out aggregate or stylized targets. |
| `component_measured` | Measured behavior of a software component or benchmarked model. |
| `synthetic_assumption` | Scenario parameter supplied by the user or preset. |
| `unsupported` | Not backed by code, data, or validation artifact. |

Validation must say what was validated. A measured classifier component does
not validate the whole ABM as a real-world predictor.
