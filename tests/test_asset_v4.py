import json
from pathlib import Path


def test_v4_asset_registry_counts_and_no_legacy_files():
    root = Path(__file__).resolve().parents[1]
    registry = root / "socio_sim" / "web" / "static" / "assets" / "v4" / "registry.json"
    data = json.loads(registry.read_text(encoding="utf-8"))
    rows = data["assets"]
    assert sum(r["role"] == "feed_cover" for r in rows) == 48
    assert sum(r["role"] == "ad_creative" for r in rows) == 32
    assert sum(r["role"] == "editorial_system" for r in rows) == 12
    assets_root = root / "socio_sim" / "web" / "static" / "assets"
    registry_text = registry.read_text(encoding="utf-8")
    for stale in (
        "feed-atlas-" + "v3",
        "ad-atlas-" + "v3",
        "feed-cover-" + "v3",
        "ad-creative-" + "v3",
    ):
        assert stale not in registry_text
        assert not list(assets_root.glob(f"*{stale}*"))


def test_asset_registry_alt_text_does_not_claim_evidence():
    root = Path(__file__).resolve().parents[1]
    registry = root / "socio_sim" / "web" / "static" / "assets" / "v4" / "registry.json"
    data = json.loads(registry.read_text(encoding="utf-8"))
    for row in data["assets"]:
        alt = row["accessibility_alt_template"].lower()
        assert "not evidence" in alt
        assert row["source_type"] == "synthetic_decorative_artwork"
