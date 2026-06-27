# Static Image Asset Manifest

Generated image assets are bundled for offline, deterministic dashboard display.
They are **not** real brand creatives, endorsements, people, or platform content —
they use fictional brands, invented marks, and simulated feed/ad scenes only.

## Active pack — v3 (2026-06-26)

| Asset | Use | Source | SHA-256 |
| --- | --- | --- | --- |
| `socio_sim/web/static/assets/feed-atlas-v3.png` | 12-panel realistic social-feed source atlas | Built-in image generation; prompt: realistic social-feed atlas, editorial/smartphone/product/UI/community variety, fictional labels only — no real brands/faces/PII | `28D5A6E1E2479E7E92F63413AE988C4DA26901CFA932E1EA97DA427D0DD226CB` |
| `socio_sim/web/static/assets/ad-atlas-v3.png` | 12-panel realistic 2:1 ad-creative source atlas | Built-in image generation; prompt: fictional-brand ad atlas (product shots, UI mockups, offer badges, creator/social-proof), no real brands | `E62201F96E7888BE70C102D2C419DB53E5F12B87C4C8731638DDD01CA083ED0F` |

Derived (the files the dashboard actually serves):

- `feed-cover-v3-00.png` … `-11.png` — 3:2 crops of `feed-atlas-v3.png` (Feed tab covers).
- `ad-creative-v3-00.png` … `-11.png` — 1024×512 (2:1) crops of `ad-atlas-v3.png`
  (served by `/api/creative` for dashboard ad cards, keyed by campaign).

## Metadata & security policy
- **All ancillary metadata is stripped** from bundled PNGs (only IHDR/PLTE/tRNS/
  IDAT/IEND + colorimetry chunks kept). The earlier C2PA/content-credential chunk
  (which embedded the third-party provenance CA string `ca@trufo.ai`) has been
  **removed**, so the binaries carry no embedded third-party strings, emails, EXIF,
  GPS, or credentials — a clean secret/PII scan for enterprise/government use.
- Provenance is documented **here** (these are AI-generated, not real content)
  rather than in binary metadata. No personal data, trademarks, or campaign claims
  are embedded by project code.
- Verified by a binary secret/PII scan (no matches) and a PNG integrity check
  (every file: valid CRCs, IDAT decompresses). Superseded v1/v2 packs were removed
  (~33 MB); only the active v3 pack ships.
- If replacing these files: regenerate this manifest (new SHA-256s), re-run the
  binary metadata/secret scan + PNG integrity check, and the wheel-asset inspection.
