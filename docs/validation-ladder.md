# Validation Ladder

SocioSim uses validation language conservatively:

1. `synthetic_assumption`: user or preset input.
2. `model_derived`: deterministic simulation output under a manifest.
3. `calibration_consistent`: aggregate target consistency for named benchmarks.
4. `aggregate_backtested`: held-out aggregate or stylized-fact comparison.
5. `component_measured`: measured software component behavior on a benchmark.

The ladder does not include real-world prediction of people, events, campaigns,
or platforms. Current backtest artifacts should be read as aggregate pattern
checks until independent post-selection reruns and replicate intervals are
implemented.
