# Asset Manifest

SocioSim ships v4 direct-use PNG assets only.

The authoritative registry is:

- `socio_sim/web/static/assets/v4/registry.json`

The registry records each asset ID, file path, role, dimensions, source type,
license/provenance, content-risk tags, alt-text template, SHA-256, perceptual
hash, and approval status.

## Scope

- Feed covers: 48 direct 3:2 PNG files, 1200 x 800.
- Ad creatives: 32 direct 2:1 PNG files, 1200 x 600.
- Editorial/system visuals: 12 direct 16:9 PNG files, 1600 x 900.

All v4 images are project-owned synthetic decorative artwork. They are not real
people, brands, screenshots, testimonials, product claims, data displays, or
evidence.

## Verification

Run:

```bash
python scripts/asset_qa.py
```

The command validates dimensions, registry completeness, hashes, duplicate
screening, metadata chunks, orphan files, stale legacy references, packaging
expectations, and writes `docs/ASSET_QA.md`.

Human visual review has not been performed unless `registry.json` records a
reviewer, date, scope, and defects found.
