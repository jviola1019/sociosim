"""Generate a family-labeled contact sheet + human-review checklist.

Optional aid for the (still not performed) human visual review of the v4
assets. Produces out/asset_review/contact-sheet-by-family.png and a
checklist markdown whose fields mirror what registry.json requires before
human review may be marked complete (reviewer, date, scope, defects,
resolution, approval). Running this script does NOT constitute a review.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "socio_sim" / "web" / "static" / "assets" / "v4" / "registry.json"
OUT = ROOT / "out" / "asset_review"

CHECKLIST = """# v4 asset human visual review — checklist (UNREVIEWED template)

Status: NOT PERFORMED until every field below is filled in and
registry.json's human_review block is updated to match.

- Reviewer name:
- Date:
- Scope (all 96 assets? families? roles?):
- Per-family notes (strata / orbits / lattice / currents / terrace /
  halftone / prisms / archipelago):
- Defects found (asset ids + description):
- Resolution (regenerated? accepted as-is? removed?):
- Approval status (approved / rejected / needs-rework):

Review criteria: decorative only; no people, brands, text glyphs,
screenshots, KPIs, or anything that could read as evidence; families
visually distinct; no unacceptable near-duplicates beyond the automated
phash screen.
"""


def main() -> int:
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("Pillow not installed (pip install -e .[asset]); "
              "checklist written, contact sheet skipped")
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "REVIEW_CHECKLIST.md").write_text(CHECKLIST, encoding="utf-8")
        return 0

    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rows = sorted(registry["assets"],
                  key=lambda r: (r.get("family", ""), r["asset_id"]))
    thumb_w, thumb_h, label_h, cols = 180, 120, 26, 12
    n_rows = (len(rows) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * thumb_w, n_rows * (thumb_h + label_h)),
                      "white")
    draw = ImageDraw.Draw(sheet)
    for i, rec in enumerate(rows):
        im = Image.open(ROOT / rec["file_path"]).resize((thumb_w, thumb_h))
        x = (i % cols) * thumb_w
        y = (i // cols) * (thumb_h + label_h)
        sheet.paste(im, (x, y))
        draw.text((x + 4, y + thumb_h + 2),
                  f"{rec.get('family', '?')} | {rec['asset_id']}",
                  fill=(0, 0, 0))
    OUT.mkdir(parents=True, exist_ok=True)
    sheet_path = OUT / "contact-sheet-by-family.png"
    sheet.save(sheet_path)
    (OUT / "REVIEW_CHECKLIST.md").write_text(CHECKLIST, encoding="utf-8")
    print(f"wrote {sheet_path} and REVIEW_CHECKLIST.md "
          f"({len(rows)} assets, grouped by family). Running this script "
          "does NOT constitute a human review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
