import json
from pathlib import Path


def test_v4_asset_registry_counts_and_no_legacy_files():
    root = Path(__file__).resolve().parents[1]
    registry = root / "socio_sim" / "web" / "static" / "assets" / "v4" / "registry.json"
    data = json.loads(registry.read_text(encoding="utf-8"))
    rows = data["assets"]
    assert len(rows) == 96
    assert sum(r["role"] == "feed_cover" for r in rows) == 48
    assert sum(r["role"] == "ad_creative" for r in rows) == 32
    assert sum(r["role"] == "editorial_system" for r in rows) == 16
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


def test_r7_eight_art_directed_families_cover_every_role():
    """R7: 8 distinct visual families, 12 assets each (6 feed covers +
    4 ad creatives + 2 editorial visuals), every family in every role."""
    root = Path(__file__).resolve().parents[1]
    registry = root / "socio_sim" / "web" / "static" / "assets" / "v4" / "registry.json"
    data = json.loads(registry.read_text(encoding="utf-8"))
    fam_counts: dict = {}
    fam_roles: dict = {}
    for row in data["assets"]:
        fam = row.get("family")
        assert fam, f"{row['asset_id']} has no family"
        fam_counts[fam] = fam_counts.get(fam, 0) + 1
        fam_roles.setdefault(fam, set()).add(row["role"])
        assert fam in row["provenance"], "provenance must name the family"
    assert len(fam_counts) == 8, sorted(fam_counts)
    assert all(n == 12 for n in fam_counts.values()), fam_counts
    for fam, roles in fam_roles.items():
        assert roles == {"feed_cover", "ad_creative", "editorial_system"}, (fam, roles)
    assert set(data.get("families", {})) == set(fam_counts)


def test_asset_registry_alt_text_does_not_claim_evidence():
    root = Path(__file__).resolve().parents[1]
    registry = root / "socio_sim" / "web" / "static" / "assets" / "v4" / "registry.json"
    data = json.loads(registry.read_text(encoding="utf-8"))
    for row in data["assets"]:
        alt = row["accessibility_alt_template"].lower()
        assert "not evidence" in alt
        assert row["source_type"] == "synthetic_decorative_artwork"
