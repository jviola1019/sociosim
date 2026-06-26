# Static Image Asset Manifest

Generated assets are bundled for offline, deterministic dashboard display. They
are not real brand creatives, endorsements, people, or platform content.

## 2026-06-24 v2 Atlases

| Asset | Use | Source | SHA-256 |
| --- | --- | --- | --- |
| `socio_sim/web/static/assets/feed-atlas-v2.png` | 12 realistic feed cover source panels | Built-in image generation, prompt: realistic 4x3 social-feed thumbnail atlas; no readable text/logos/faces | `CA24E23C6BCAD28D89F6CC2A255B2686C7FBACEECC50C57882FFA11982451F59` |
| `socio_sim/web/static/assets/ad-atlas-v2.png` | 12 realistic ad creative source panels | Built-in image generation, prompt: realistic 4x3 ad/product creative atlas; no readable text/logos/faces/claims | `A2CB24C777DADEC2C408BCA74AC9BE65A6DF0CD4711AA7456FE2DC89C6E5D54F` |

Derived assets:

- `feed-cover-v2-00.png` through `feed-cover-v2-11.png`: 3:2 crops/resizes from `feed-atlas-v2.png`.
- `ad-creative-v2-00.png` through `ad-creative-v2-11.png`: 2:1 crops/resizes from `ad-atlas-v2.png`.

Metadata policy:

- C2PA/OpenAI provenance chunks may be present and are intentionally preserved
  rather than stripped.
- No credentials, personal data, trademarks, or campaign claims are embedded by
  project code. The assets are visual examples for simulated outputs only.
- If replacing these files, regenerate this manifest and rerun the binary
  metadata/secret scan plus wheel asset inspection.

## 2026-06-26 v3 Atlases

| Asset | Use | Source | SHA-256 |
| --- | --- | --- | --- |
| `socio_sim/web/static/assets/feed-atlas-v3.png` | 12 realistic social-feed source panels | Built-in image generation, prompt: realistic social feed atlas with editorial/smartphone/product/UI/community variety and fictional labels only | `F201803B3C4A763D3CF18B23E2A5AA3FB54C5A9FA758F7E1A76F97D9BAB18547` |
| `socio_sim/web/static/assets/ad-atlas-v3.png` | 12 realistic 2:1 ad creative source panels | Built-in image generation, prompt: fictional-brand ad atlas with product shots, UI mockups, offer badges, event countdowns, creator/social-proof tactics, no real brands | `E89FE7771CCAFDEE041269C0DE6507FBD02140A26C6CB2B11C3A8C686C54D214` |

Derived assets:

- `feed-cover-v3-00.png` through `feed-cover-v3-11.png`: 3:2 900x600 crops/resizes from `feed-atlas-v3.png`.
- `ad-creative-v3-00.png` through `ad-creative-v3-11.png`: 2:1 1024x512 crops/resizes from `ad-atlas-v3.png`.

The v3 pack is the active dashboard pack. It uses fictional brands, invented
marks, and simulated campaign/feed scenes only; it is not an endorsement,
licensed brand asset, public-service notice, news item, or real ad campaign.
