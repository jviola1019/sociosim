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

# Everything CI runs, in CI order.
verify: lint gates test e2e a11y asset-qa security build wheel-qa
	$(PY) scripts/license_inventory.py
