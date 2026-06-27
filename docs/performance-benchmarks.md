# Performance Benchmarks

Measured during the 2026-06-27 baseline:

| Check | Scale | Runtime |
| --- | --- | ---: |
| Fixed-seed CLI replay smoke | 80 agents, 12 ticks | ~5.2s per run |
| Quickstart | 1000 agents, 168 ticks | 24.55s |
| Full pytest with coverage | test suite | 413.81s |
| Validation smoke | quick profile, 4 samples | ~328s |

These are local measurements on the audit environment, not extrapolations.

Remaining benchmark work:

- Add representative policy and market scenario runtime reports.
- Track peak memory, events/sec, output size, and worker count.
- Add broad CI thresholds for large regressions without making CI flaky.
