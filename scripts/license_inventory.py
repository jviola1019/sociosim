"""Generate a minimal dependency license inventory from installed metadata."""

from __future__ import annotations

import importlib.metadata as md
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    rows = []
    for dist in sorted(md.distributions(), key=lambda d: d.metadata["Name"].lower()):
        meta = dist.metadata
        rows.append({
            "name": meta["Name"],
            "version": dist.version,
            "license": meta.get("License", ""),
            "summary": meta.get("Summary", ""),
        })
    out = ROOT / "out" / "license_inventory.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {out} ({len(rows)} packages)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
