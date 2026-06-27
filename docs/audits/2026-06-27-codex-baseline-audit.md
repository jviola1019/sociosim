# 2026-06-27 Codex Baseline Audit

## Scope

Repository: `C:\Users\jviol\Downloads\socio_sim` on branch
`feat/audit-p0-p1`. Worktree was clean before baseline verification.
Python: `3.11.9`. No root `AGENTS.md` existed before this remediation.

## Commands Run

| Command | Status | Runtime | Evidence |
| --- | --- | ---: | --- |
| `python -m pip install -e ".[dev,e2e]"` | passed | ~80s | Editable install succeeded; dev/e2e deps installed. |
| `python -m ruff check .` | passed | 2.66s | Exit code 0. |
| `python -m pytest -q --cov=socio_sim --cov-report=term-missing --cov-fail-under=85` | passed | 413.81s | Exit code 0. |
| `python -m coverage report -m` | passed | 2.9s | Total coverage 93%. |
| `python run.py --profile test --agents 80 --ticks 12 --seed 123 --out out/audit-baseline-det1` | passed | 5.26s | Stream hash `8759b62f850995270738b7482298a3817c68c3d142f05bdf885d23796c1e7016`; replay ok. |
| `python run.py --profile test --agents 80 --ticks 12 --seed 123 --out out/audit-baseline-det2` | passed | 5.20s | Same stream hash; replay ok. |
| `python examples\policy_stress_demo.py --replicates 2 --profile test` | failed | 4.82s | `ModuleNotFoundError: socio_sim.experiments.runner`. |
| Direct `socio_sim.experiments.compare.compare(...)` policy smoke | passed with caveat | 4.71s | Returned deltas; tiny sample produced `nan` for undefined precision/recall. |
| `python examples\ad_experiment_demo.py` | passed with caveat | 5.61s | Ran holdout demo, but printed raw lift without FDR/economics provenance. |
| `python examples\quickstart.py` | passed | 24.55s | 104853 events; replay ok. |
| `python run.py --measure-classifier` | passed | 7.90s | Civil Comments F1 0.736 ROC-AUC 0.805; spam F1 0.990 ROC-AUC 0.999. |
| `python run.py --backtest` | passed with claim caveat | ~60s | `test_pass=True`, `I_test=0.12`, stylized 5/5. |
| `python run.py --validate --sens-samples 4` | passed with sample-size caveat | ~328s | Wrote `VALIDATION_REPORT.md`, `I=1.67`. |
| `python run.py --web --no-open --port 9876` + `GET /api/meta` | passed | manual smoke | API returned research notice, token, presets, profiles. Server stopped by PID after PTY Ctrl-C was unavailable. |
| `python -m pytest -q tests\test_e2e_playwright.py` | passed | 13.32s | `1 passed`. |
| `docker --version` | skipped | n/a | Docker command unavailable. |
| `python -m pip_audit --version` | skipped | n/a | Module unavailable. |
| `python -m bandit --version` | skipped | n/a | Module unavailable. |

## Coverage

`coverage report -m` produced total coverage of 93% over 3397 statements. The
coverage gate of 85% passed.

## Determinism and Replay

Two fixed-seed CLI runs produced identical event-stream hash
`8759b62f850995270738b7482298a3817c68c3d142f05bdf885d23796c1e7016`.
Both reported deterministic replay success.

## Feature Inventory

- Simulation engine: synthetic personas, graph generation, content generation,
  moderation, feed ranking, ads, event logs, manifests, replay.
- Policy packs: US Section 230, EU DSA approximation, CN AI labeling, FTC.
- Validation: calibration targets, sensitivity, stylized facts, aggregate
  backtest, classifier benchmark measurement.
- Web console: stdlib local server, scenario controls, run history, compare API,
  report exports, static assets, Playwright smoke test.
- Marketing: campaign dataclass, auction, holdout assignment, lift/economics
  measurement, FDR correction in production summaries.

## Documentation Claim Matrix

| Claim | Evidence | Status |
| --- | --- | --- |
| Research-only synthetic simulator | README and package notices; CLI/web output | supported. |
| `ruff` clean | baseline command | verified. |
| 85% coverage gate and ~93% coverage | coverage report | verified. |
| Exact README test count | README line near test/CI claim | brittle; collect output is environment and parametrization dependent. |
| Deterministic replay | CLI fixed-seed run | verified for small template run. |
| Every output carries provenance | `docs/MODELS.md`; `pipeline.py` MC provenance only | overclaimed. |
| Held-out backtest proves independent aggregate validation | `validation/backtest.py` reuses selected run observations | overclaimed until rerun/split design is strengthened. |
| Marketing economics are synthetic | reports and metrics fields | mostly supported; demo needed correction. |

## Findings

### P1

- Broken shipped policy example: `examples/policy_stress_demo.py:15` imported
  removed module `socio_sim.experiments.runner`.
- EU user-flag escalation was classifier-threshold gated:
  `socio_sim/policy/packs/eu_dsa.yaml:54` and
  `socio_sim/policy/engine.py:148`. A valid user flag could be missed when the
  classifier score was below 0.50.
- Web API could start unbounded background jobs and accepted unbounded explicit
  `n_agents` / `n_ticks`: `socio_sim/web/app.py:793`,
  `socio_sim/web/app.py:260`, `socio_sim/config.py:228`.
- Held-out backtest is not an independent post-selection evaluation:
  `socio_sim/validation/backtest.py:46` selects a candidate and line 57 scores
  held-out metrics from the same run observation.

### P2

- Programmatic campaigns bypassed validation in
  `socio_sim/ads/campaigns.py:18`; the web path had validation but direct
  constructors did not.
- `human_review_required` in policy packs was metadata-only:
  `socio_sim/policy/engine.py:51`, `socio_sim/moderation/workflow.py:83`.
- Optional LLM surface text is cached/logged without a safety scrub or
  reclassification pass: `socio_sim/content/llm_adapter.py:35`,
  `socio_sim/engine.py:356`, `socio_sim/web/app.py:416`.
- `examples/ad_experiment_demo.py` printed uncorrected lift and did not show
  FDR/economics provenance.
- Dependency/security release gates lack `pip-audit`, static security scan,
  SBOM, lockfile, Docker non-root user, and container scan.
- Source ledger is stale versus implemented BH-FDR and classifier benchmark data.

### P3

- Holdout assignment is fixed across replicates; useful for common random
  numbers but under-documented for randomization-assignment variance.
- Performance tests cover correctness more than regression budgets.
- Audit Trail UI exposes a sampled event table but not a full authenticated
  event-log export.
- Accessibility tests do not include axe or full table alternatives for charts.

## Claims That Must Be Downgraded or Removed

- Avoid exact fixed test-count claims in README unless generated by CI.
- Downgrade "every output has provenance" to the surfaces that actually render
  per-metric provenance, or add mandatory per-metric provenance everywhere.
- Reword "held-out backtest" claims until selected configurations are rerun on
  fresh seeds/replicates for held-out scoring.
- Label sensitivity indices from small LHS designs as screening diagnostics,
  not strong Sobol-style variance decomposition.
- Keep classifier benchmark claims scoped to the component; they do not validate
  the synthetic ABM as a real-platform predictor.

## Remediation Roadmap

1. Fix P1 policy/example/web resource issues and add regression tests.
2. Add scenario-as-code linting, required example scenarios, and CI gate.
3. Add release verifier with honest pass/fail/skipped statuses.
4. Add per-metric provenance validation for reports/web/API.
5. Strengthen independent backtest/calibration artifacts.
6. Harden LLM output safety and replay cache provenance.
7. Add dependency/security scan, Docker hardening, and performance budget gates.

## Environment Limitations

- Docker was not installed, so image build/runtime verification was skipped.
- `pip-audit` and Bandit were not installed after the documented project install.
- PTY interrupt was unavailable for the launched web server; the listener on
  port 9876 was stopped by owning PID and verified closed.
