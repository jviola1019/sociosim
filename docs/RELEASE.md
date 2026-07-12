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

## Branch protection

Requiring the `test` check on `main` needs GitHub Pro on private repos
(the API returns 403 "Upgrade to GitHub Pro" — attempted 2026-07-11).
Until the repo is public or upgraded, the enforced substitute is this
release gate: **never tag or announce a release whose exact SHA lacks a
completed successful run** (`gh run list --commit <sha>` +
`gh api .../commits/<sha>/check-runs`). CI also has `workflow_dispatch`
so any ref can be re-proven manually.

## Corrupted run-history database (recovery)

`python run.py --status` reports DB health (`PRAGMA integrity_check`).
If it reports corruption: stop the console, move `out/sociosim.db` aside,
and restart — the schema is recreated empty. The DB is a local cache;
every run's authoritative record is its `out/<run>/events.jsonl` +
`manifest.json`, and determinism means any run is reproducible from
config + seed. To salvage rows first: `sqlite3 out/sociosim.db ".recover" |
sqlite3 recovered.db`.

## Local data retention & cleanup

- Every run writes `out/<name>/` (events.jsonl, manifest.json, report.md)
  and the web console appends to `out/sociosim.db`. Nothing leaves the
  machine.
- Retention is OPT-IN via the CLI: `python run.py --status` (inventory,
  disk headroom, DB health), `--cleanup --keep-last N / --max-age-days D`
  (dry run by default; `--yes` to delete — this also prunes orphaned
  history rows and vacuums the DB), `--vacuum-db`.
- Bulk backup: `python run.py --export-all DEST` copies every run with a
  per-run sha256 `integrity.json`; `--verify-export DIR` re-checks an
  archived copy. Exports are plain directories, no archive format.

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
