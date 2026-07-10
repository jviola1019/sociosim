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
- Editorial/system visuals: 16 direct 16:9 PNG files, 1600 x 900.

96 assets total, drawn from eight art-directed visual families (R7), each a
deliberate composition system with its own palette and motif grammar; every
family contributes 6 feed covers + 4 ad creatives + 2 editorial visuals:

| Family | Motif |
|--------|-------|
| strata | layered sediment horizons with sine-displaced band edges |
| orbits | concentric rings and satellite nodes on a deep night field |
| lattice | isometric diamond grid with per-cell tonal variation |
| currents | flowing ribbon streams bent by a slow transverse wave |
| terrace | split-panel composition with paper gutters |
| halftone | screen-print dot field following a light sweep |
| prisms | overlapping translucent triangles over a dusk gradient |
| archipelago | metaball islands with shoreline rings on a sea gradient |

All v4 images are project-owned synthetic decorative artwork. They are not real
people, brands, screenshots, testimonials, product claims, data displays, or
evidence. `scripts/asset_qa.py` enforces the family contract (exactly 8
families, each present in every role) alongside dimensions, hashes, and
near-duplicate screening.

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
