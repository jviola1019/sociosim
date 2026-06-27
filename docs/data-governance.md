# Data Governance

SocioSim should use synthetic personas, synthetic event streams, and published
aggregate or licensed benchmark data only.

Rules:

- Do not ingest PII or private individual-level behavioral data.
- Keep source provenance in `SOURCE_LEDGER.md` or `docs/DATA_MANIFEST.md`.
- Store manifests, config hashes, seeds, policy-pack versions, and event hashes.
- Do not store secrets, private tokens, or chain-of-thought in logs, reports, or
  manifests.
- Generated text and media are presentation artifacts and cannot mutate
  executable scenario state.
