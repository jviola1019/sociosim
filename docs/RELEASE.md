# Release checklist & operations notes

SocioSim is a **local single-user research tool**. "Release" means a tagged
commit whose full gate suite is green on CI for the exact SHA — nothing here
implies SaaS, multi-tenant, or production-service readiness.

## Health check

`GET /api/meta` on the running console returns version + capability flags;
a 200 with parseable JSON is the liveness signal. There is no separate
health endpoint (single-user stdlib server by design).

## Release checklist

1. Working tree clean; `git log` shows only reviewed commits.
2. `make verify` (or the same commands on Windows) fully green:
   ruff · evidence_gate · claim_scan · secret_scan · pytest+coverage ≥85 ·
   Playwright e2e · axe a11y · asset QA · bandit · pip-audit · wheel build ·
   wheel QA · license inventory.
3. Installed-wheel smoke in a clean venv (CI runs this too):
   `pip install dist/*.whl` then run a small `run_and_analyze` with
   `verify_replay=True`.
4. CI green **for the exact SHA being released** (`gh run watch <run-id>
   --exit-status`), not just a PR head.
5. Tag: `git tag -a vX.Y.Z -m "..." && git push --tags`.

## Rollback

Releases are plain git tags + wheels; no migrations, no external state.
- Code: `git checkout <previous-tag>` (or `git revert` the offending
  commits on main) and re-run `make verify`.
- Installed tool: `pip install socio-sim==<previous-version>` or the
  previous wheel file.
- Run history DB (`out/sociosim.db`) is forward-compatible sqlite; if a
  newer schema ever breaks an older build, delete or move the file — it is
  a local cache of run payloads, not a source of truth (every run's
  authoritative record is its `out/<run>/events.jsonl` + `manifest.json`).

## Local data retention & cleanup

- Every run writes `out/<name>/` (events.jsonl, manifest.json, report.md)
  and the web console appends to `out/sociosim.db`. Nothing leaves the
  machine.
- There is NO automatic retention policy: `out/` grows until you delete
  it. Safe cleanup: remove `out/` entirely (regenerable; determinism means
  any run can be reproduced from its config + seed) or delete individual
  run folders / History entries in the UI.
- Backup/export limitation: exports are per-run markdown/JSON from the
  UI/CLI; there is no bulk backup tool. Copy `out/` wholesale if you need
  an archive.

## Secrets

No secrets are required for the default workflow. `.env.example` lists the
optional variables; the web access token is runtime-generated unless
`SOCIOSIM_ACCESS_TOKEN` is set, and `ANTHROPIC_API_KEY` is read from the
environment only (never persisted). `scripts/secret_scan.py` gates the
tracked tree in CI.

## Local-only warning

Binding beyond loopback prints a cleartext-HTTP warning and hard-requires
`SOCIOSIM_ACCESS_TOKEN` + `SOCIOSIM_ALLOWED_HOSTS`; see SECURITY.md.
Multi-tenancy: **RLS/tenant isolation NOT APPLICABLE — local single-user
research tool; no tenant-isolation architecture exists.**
