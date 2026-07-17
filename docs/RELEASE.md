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
5. Tag: `git tag -a vX.Y.Z -m "..." && git push --tags`. The
   **Release workflow** (`.github/workflows/release.yml`) then re-runs the
   entire gate suite *against the tagged SHA* and only then publishes the
   wheel, `SHA256SUMS`, an SPDX SBOM, `provenance.json` (commit, workflow
   run, gate list, scope), and release notes generated from the reviewed
   commits since the previous tag. A green PR-head run is never accepted
   as proof of a release commit; `workflow_dispatch` can also verify any
   arbitrary SHA.

Rollback verification: after checking out a previous tag, run
`make verify` (which now ends with `installed-wheel-smoke`) — the release
is only considered rolled back once that passes on the older SHA.

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

**Active and server-enforced (enabled 2026-07-14 after the repository was
made public).** `main` requires the `test` status check to pass, in strict
mode (a branch must be up to date with `main` before it can merge), and
force-pushes and branch deletion are disabled. Read the live state with:

```bash
gh api repos/<owner>/<repo>/branches/main/protection \
  --jq '{required_checks: .required_status_checks.checks, strict: .required_status_checks.strict}'
```

Historical note: while the repo was private on the free plan, both classic
protection (`PUT /repos/:owner/:repo/branches/main/protection`, 2026-07-11)
and repository rulesets (`POST /repos/:owner/:repo/rulesets`, 2026-07-13)
returned `403 Upgrade to GitHub Pro or make this repository public`; the
release gate below was the interim substitute. To re-apply protection from
scratch:

```bash
gh api -X PUT repos/<owner>/<repo>/branches/main/protection --input - <<'JSON'
{"required_status_checks":{"strict":true,"contexts":["test"]},
 "enforce_admins":false,"required_pull_request_reviews":null,
 "restrictions":null,"allow_force_pushes":false,"allow_deletions":false}
JSON
```

Independently of protection, the release gate still holds: **never tag or
announce a release whose exact SHA lacks a completed successful run**
(`gh run list --commit <sha>` + `gh api .../commits/<sha>/check-runs`).
CI has `workflow_dispatch` so any ref can be re-proven manually, and the
release workflow fails when a `workflow_dispatch` SHA does not resolve to
the exact requested commit. Release documentation must record the exact
SHA's run URL.

### Exact-SHA verification ledger

| main SHA | CI run (exact SHA, push event) | result |
|---|---|---|
| `86bb4b7ccf4867ba091d2c0e1a1e0c46c245d039` | <https://github.com/jviola1019/sociosim/actions/runs/29398446514> | success (job `test`); the run's headSha equals this merge SHA |

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
