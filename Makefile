# SocioSim task runner (POSIX/CI; on Windows run the same commands directly —
# each target is a thin alias, no target has hidden behavior).
PY ?= python

.PHONY: lint test e2e a11y security asset-qa gates build wheel-qa verify

lint:
	$(PY) -m ruff check socio_sim tests run.py scripts examples

gates:
	$(PY) scripts/evidence_gate.py
	$(PY) scripts/claim_scan.py
	$(PY) scripts/secret_scan.py
	$(PY) scripts/numeric_provenance_scan.py

test:
	$(PY) -m pytest -q --cov=socio_sim --cov-report=term-missing --cov-fail-under=85

e2e:
	$(PY) -m pytest -q tests/test_e2e_playwright.py

a11y:
	$(PY) -m pytest -q tests/test_a11y_axe.py

security:
	bandit -q -r socio_sim -ll
	pip-audit --skip-editable

asset-qa:
	$(PY) scripts/asset_qa.py

build:
	$(PY) -m build --wheel

wheel-qa:
	$(PY) scripts/wheel_qa.py

# Install the built wheel into a throwaway venv and run a replay-verified
# simulation from it (the same check CI and the release workflow run).
installed-wheel-smoke:
	rm -rf .wheel-env && $(PY) -m venv .wheel-env
	.wheel-env/bin/pip -q install dist/*.whl
	.wheel-env/bin/python -c "import tempfile; \
	from socio_sim.config import RunConfig; \
	from socio_sim.pipeline import run_and_analyze; \
	a = run_and_analyze(RunConfig.test(n_agents=50, n_ticks=6, out_dir=tempfile.mkdtemp()), verify_replay=True); \
	assert a.summary and a.replay['ok']; print('installed wheel smoke OK')"

# Everything CI runs, in CI order.
verify: lint gates test e2e a11y asset-qa security build wheel-qa installed-wheel-smoke
	$(PY) scripts/license_inventory.py
