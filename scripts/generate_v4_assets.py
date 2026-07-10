"""Generate SocioSim v4 direct-use synthetic decorative assets (R7).

Eight art-directed visual families, each a deliberate composition system
with its own palette and motif grammar -- not the retired gradient/ellipse/
noise pattern. Every asset is deterministic (seeded per asset id), project-
owned abstract artwork, and intentionally contains no people, brands,
dashboard KPIs, screenshots, testimonials, text glyphs, or claims.

Families
--------
- strata:      layered sediment horizons with sine-displaced band edges
- orbits:      concentric rings and satellite nodes on a deep night field
- lattice:     isometric diamond grid with per-cell tonal variation
- currents:    flowing ribbon streams bent by a slow transverse wave
- terrace:     split-panel composition with paper gutters (grid collage)
- halftone:    screen-print dot field whose dot size follows a light sweep
- prisms:      overlapping translucent triangles over a dusk gradient
- archipelago: metaball islands with shoreline rings on a sea gradient

Distribution: every family contributes 6 feed covers + 4 ad creatives +
2 editorial visuals = 12 assets/family, 96 assets total.
"""

from __future__ import annotations

import hashlib
import json
import math
import struct
import zlib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "socio_sim" / "web" / "static" / "assets" / "v4"


def _png(rgb: np.ndarray) -> bytes:
    h, w, _ = rgb.shape
    raw = bytearray()
    row = rgb.reshape(h, w * 3)
    for y in range(h):
        raw.append(0)
        raw.extend(row[y].tobytes())
    comp = zlib.compress(bytes(raw), 9)

    def chunk(typ: bytes, data: bytes) -> bytes:
        body = typ + data
        return (struct.pack(">I", len(data)) + body
                + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", comp) + chunk(b"IEND", b"")


# --------------------------------------------------------------------------
# Shared composition helpers
# --------------------------------------------------------------------------
def _grid(w: int, h: int):
    yy, xx = np.mgrid[0:h, 0:w].astype(float)
    return xx / max(w - 1, 1), yy / max(h - 1, 1)


def _fill(w: int, h: int, top, bottom) -> np.ndarray:
    """Vertical two-stop wash used as a base ground by several families."""
    _, ny = _grid(w, h)
    top = np.asarray(top, dtype=float)
    bottom = np.asarray(bottom, dtype=float)
    return top * (1 - ny[..., None]) + bottom * ny[..., None]


def _fill_dir(w: int, h: int, c1, c2, angle: float) -> np.ndarray:
    """Directional two-stop wash. Varying the angle per variant keeps the
    16x16 perceptual hash driven by composition, not by a shared vertical
    gradient (which made soft-wash families read as near-duplicates)."""
    nx, ny = _grid(w, h)
    t = nx * math.cos(angle) + ny * math.sin(angle)
    t = (t - t.min()) / max(t.max() - t.min(), 1e-9)
    c1 = np.asarray(c1, dtype=float)
    c2 = np.asarray(c2, dtype=float)
    return c1 * (1 - t[..., None]) + c2 * t[..., None]


def _grain(field: np.ndarray, rng, sigma: float = 2.5) -> np.ndarray:
    return np.clip(field + rng.normal(0, sigma, size=field.shape), 0, 255)


def _blend(field: np.ndarray, mask: np.ndarray, color, alpha: float) -> np.ndarray:
    color = np.asarray(color, dtype=float)
    a = np.clip(mask, 0, 1)[..., None] * alpha
    return field * (1 - a) + color * a


# --------------------------------------------------------------------------
# Family renderers. Each takes (variant rng, w, h) and returns float (h,w,3).
# --------------------------------------------------------------------------
_STRATA = [(74, 59, 50), (176, 103, 74), (216, 166, 112), (236, 222, 199),
           (122, 121, 96), (58, 76, 74)]


def _fam_strata(rng, w: int, h: int) -> np.ndarray:
    nx, ny = _grid(w, h)
    n_bands = int(rng.integers(6, 10))
    order = rng.permutation(len(_STRATA))
    f1, f2 = rng.uniform(1.0, 2.6), rng.uniform(3.0, 6.0)
    p1, p2 = rng.uniform(0, 2 * math.pi, 2)
    amp = rng.uniform(0.02, 0.06)
    drift = (amp * np.sin(nx * 2 * math.pi * f1 + p1)
             + amp * 0.5 * np.sin(nx * 2 * math.pi * f2 + p2))
    level = ny + drift
    field = _fill(w, h, _STRATA[order[0]], _STRATA[order[1]])
    edges = np.sort(rng.uniform(0.08, 0.95, n_bands))
    for k, edge in enumerate(edges):
        color = np.asarray(_STRATA[order[(k + 2) % len(_STRATA)]], dtype=float)
        below = np.clip((level - edge) * h / 14.0, 0, 1)
        field = _blend(field, below, color, 1.0)
        # thin light seam on each horizon top
        seam = np.clip(1 - np.abs(level - edge) * h / 3.0, 0, 1)
        field = _blend(field, seam, (244, 238, 224), 0.35)
    return _grain(field, rng)


def _fam_orbits(rng, w: int, h: int) -> np.ndarray:
    nx, ny = _grid(w, h)
    field = _fill(w, h, (18, 24, 48), (34, 42, 74))
    cx, cy = rng.uniform(0.3, 0.7), rng.uniform(0.35, 0.65)
    aspect = w / h
    dist = np.sqrt(((nx - cx) * aspect) ** 2 + (ny - cy) ** 2)
    ring_colors = [(217, 164, 65), (232, 227, 213), (96, 176, 168),
                   (154, 118, 196)]
    radii = np.sort(rng.uniform(0.08, 0.72, int(rng.integers(4, 7))))
    for k, r in enumerate(radii):
        thickness = rng.uniform(0.004, 0.012)
        ring = np.clip(1 - np.abs(dist - r) / thickness, 0, 1)
        field = _blend(field, ring, ring_colors[k % len(ring_colors)], 0.85)
        # one satellite node per ring at a deterministic bearing
        theta = rng.uniform(0, 2 * math.pi)
        sx, sy = cx + r * math.cos(theta) / aspect, cy + r * math.sin(theta)
        node = np.exp(-(((nx - sx) * aspect) ** 2 + (ny - sy) ** 2)
                      / (2 * (0.012 ** 2)))
        field = _blend(field, node, (240, 234, 216), 0.95)
    glow = np.exp(-dist ** 2 / (2 * 0.05 ** 2))
    field = _blend(field, glow, (250, 240, 210), 0.5)
    return _grain(field, rng, 2.0)


_LATTICE = [(48, 66, 84), (86, 118, 130), (140, 168, 162), (198, 208, 194),
            (233, 233, 224), (105, 88, 106)]


def _fam_lattice(rng, w: int, h: int) -> np.ndarray:
    nx, ny = _grid(w, h)
    cols = int(rng.integers(7, 12))
    rows = int(rng.integers(5, 9))
    s = nx * cols + ny * rows
    t = nx * cols - ny * rows
    ci = np.floor(s).astype(int)
    cj = np.floor(t).astype(int)
    salt = int(rng.integers(1, 10_000))
    tone = ((ci * 73_856_093) ^ (cj * 19_349_663) ^ salt) % len(_LATTICE)
    palette = np.asarray(_LATTICE, dtype=float)[rng.permutation(len(_LATTICE))]
    field = palette[tone]
    # depth wash so the grid reads as a lit surface, not flat tiles
    field = field * (0.82 + 0.18 * (1 - ny))[..., None]
    fs, ft = s - np.floor(s), t - np.floor(t)
    gutter = np.minimum(np.minimum(fs, 1 - fs), np.minimum(ft, 1 - ft))
    line = np.clip(1 - gutter * cols * 1.6, 0, 1)
    field = _blend(field, line, (30, 36, 42), 0.55)
    return _grain(field, rng)


_CURRENTS = [(23, 58, 84), (39, 96, 120), (72, 148, 150), (140, 196, 178),
             (222, 234, 220), (238, 202, 130)]


def _fam_currents(rng, w: int, h: int) -> np.ndarray:
    nx, ny = _grid(w, h)
    n_ribbons = int(rng.integers(7, 12))
    bend = rng.uniform(0.05, 0.14)
    f_main = rng.uniform(0.8, 1.8)
    phase = rng.uniform(0, 2 * math.pi)
    stream = ny + bend * np.sin(nx * 2 * math.pi * f_main + phase) \
        + 0.03 * np.sin(nx * 2 * math.pi * 4.3 + phase * 1.7)
    idx = np.clip((stream * n_ribbons).astype(int) % len(_CURRENTS),
                  0, len(_CURRENTS) - 1)
    palette = np.asarray(_CURRENTS, dtype=float)[rng.permutation(len(_CURRENTS))]
    field = palette[idx]
    frac = stream * n_ribbons - np.floor(stream * n_ribbons)
    seam = np.clip(1 - np.minimum(frac, 1 - frac) * n_ribbons * 2.2, 0, 1)
    field = _blend(field, seam, (246, 244, 234), 0.4)
    return _grain(field, rng)


_TERRACE = [(214, 116, 84), (240, 196, 116), (114, 142, 120), (86, 96, 130),
            (206, 186, 166), (52, 58, 66)]


def _fam_terrace(rng, w: int, h: int) -> np.ndarray:
    field = np.empty((h, w, 3), dtype=float)
    gutter_color = np.asarray((238, 232, 220), dtype=float)
    field[:] = gutter_color
    g = max(2, int(round(min(w, h) * 0.008)))
    x_edges = [0, *sorted(int(v * w) for v in rng.uniform(0.18, 0.86, int(rng.integers(2, 4)))), w]
    palette = np.asarray(_TERRACE, dtype=float)[rng.permutation(len(_TERRACE))]
    tone = 0
    for xi in range(len(x_edges) - 1):
        x0, x1 = x_edges[xi], x_edges[xi + 1]
        y_edges = [0, *sorted(int(v * h) for v in rng.uniform(0.2, 0.85, int(rng.integers(1, 4)))), h]
        for yi in range(len(y_edges) - 1):
            y0, y1 = y_edges[yi], y_edges[yi + 1]
            color = palette[tone % len(palette)]
            tone += 1
            # inner shading: each panel gets a subtle top-light ramp
            ph = max(y1 - y0 - 2 * g, 1)
            ramp = np.linspace(1.06, 0.94, ph)[:, None, None]
            field[y0 + g:y1 - g, x0 + g:x1 - g] = color * ramp
    return _grain(field, rng)


def _fam_halftone(rng, w: int, h: int) -> np.ndarray:
    nx, ny = _grid(w, h)
    inks = [(52, 62, 118), (150, 62, 48), (36, 92, 70), (94, 58, 110)]
    ink = np.asarray(inks[int(rng.integers(0, len(inks)))], dtype=float)
    paper = np.asarray((242, 237, 228), dtype=float)
    field = np.empty((h, w, 3), dtype=float)
    field[:] = paper
    angle = rng.uniform(0, math.pi / 2)
    ca, sa = math.cos(angle), math.sin(angle)
    aspect = w / h
    u = (nx * ca * aspect + ny * sa)
    v = (-nx * sa * aspect + ny * ca)
    cells = rng.uniform(26, 40)
    fu = (u * cells) - np.floor(u * cells) - 0.5
    fv = (v * cells) - np.floor(v * cells) - 0.5
    d = np.sqrt(fu ** 2 + fv ** 2)
    # dot radius follows a diagonal light sweep across the sheet
    sweep_dir = rng.uniform(0, 2 * math.pi)
    sweep = (nx * math.cos(sweep_dir) * aspect + ny * math.sin(sweep_dir))
    sweep = (sweep - sweep.min()) / max(sweep.max() - sweep.min(), 1e-9)
    radius = 0.08 + 0.40 * sweep
    dots = np.clip((radius - d) * cells * 1.5, 0, 1)
    field = _blend(field, dots, ink, 1.0)
    return _grain(field, rng, 1.8)


def _fam_prisms(rng, w: int, h: int) -> np.ndarray:
    nx, ny = _grid(w, h)
    field = _fill_dir(w, h, (66, 56, 96), (208, 132, 106),
                      rng.uniform(0, 2 * math.pi))
    colors = [(244, 196, 108), (120, 178, 178), (196, 110, 130),
              (236, 230, 214), (92, 108, 172)]
    order = rng.permutation(len(colors))
    for k in range(int(rng.integers(6, 10))):
        pts = rng.uniform(-0.2, 1.2, (3, 2))
        (x1, y1), (x2, y2), (x3, y3) = pts

        # Standard edge function: edge(A,B) evaluated at P is the z-component
        # of (B-A) x (P-A); P is inside when all three edges share the sign
        # of the triangle's own orientation (edge(A,B) evaluated at C).
        def edge(ax, ay, bx, by):
            return (bx - ax) * (ny - ay) - (by - ay) * (nx - ax)

        e1 = edge(x1, y1, x2, y2)
        e2 = edge(x2, y2, x3, y3)
        e3 = edge(x3, y3, x1, y1)
        orient = (x2 - x1) * (y3 - y1) - (y2 - y1) * (x3 - x1)
        sgn = 1.0 if orient >= 0 else -1.0
        inside = (e1 * sgn >= 0) & (e2 * sgn >= 0) & (e3 * sgn >= 0)
        field = _blend(field, inside.astype(float),
                       colors[order[k % len(colors)]], 0.55)
    return _grain(field, rng, 2.0)


def _fam_archipelago(rng, w: int, h: int) -> np.ndarray:
    nx, ny = _grid(w, h)
    field = _fill_dir(w, h, (22, 66, 96), (118, 180, 196),
                      rng.uniform(0, 2 * math.pi))
    aspect = w / h
    blob = np.zeros((h, w))
    for _ in range(int(rng.integers(6, 10))):
        bx, by = rng.uniform(0.1, 0.9), rng.uniform(0.15, 0.85)
        sx = rng.uniform(0.07, 0.2)
        sy = rng.uniform(0.07, 0.2)
        blob += np.exp(-(((nx - bx) * aspect) ** 2 / (2 * sx ** 2)
                         + (ny - by) ** 2 / (2 * sy ** 2)))
    sea_level = rng.uniform(0.45, 0.68)
    island = np.clip((blob - sea_level) * 24, 0, 1)
    shore = np.clip(1 - np.abs(blob - sea_level) * 30, 0, 1)
    shallows = np.clip(1 - np.abs(blob - sea_level * 0.72) * 16, 0, 1)
    field = _blend(field, shallows, (150, 208, 200), 0.35)
    field = _blend(field, shore, (238, 226, 190), 0.75)
    field = _blend(field, island, (104, 138, 92), 0.9)
    highlands = np.clip((blob - sea_level - 0.35) * 20, 0, 1)
    field = _blend(field, highlands, (196, 200, 168), 0.6)
    return _grain(field, rng)


FAMILIES = {
    "strata": (_fam_strata, "layered sediment horizons"),
    "orbits": (_fam_orbits, "concentric orbital rings with satellite nodes"),
    "lattice": (_fam_lattice, "isometric diamond lattice"),
    "currents": (_fam_currents, "flowing ribbon streams"),
    "terrace": (_fam_terrace, "split-panel terrace composition"),
    "halftone": (_fam_halftone, "screen-print halftone dot sweep"),
    "prisms": (_fam_prisms, "overlapping translucent prisms at dusk"),
    "archipelago": (_fam_archipelago, "metaball island archipelago"),
}
_FAMILY_ORDER = list(FAMILIES)

_ROLE_LABEL = {
    "feed_cover": "feed cover",
    "ad_creative": "ad creative",
    "editorial_system": "editorial visual",
}


def _write(role: str, prefix: str, count: int, w: int, h: int, aspect: str,
           start_seed: int):
    rows = []
    for i in range(count):
        family = _FAMILY_ORDER[i % len(_FAMILY_ORDER)]
        render, blurb = FAMILIES[family]
        asset_id = f"{prefix}-{i:02d}"
        name = f"{asset_id}.png"
        rng = np.random.default_rng(start_seed + i)
        rgb = np.clip(render(rng, w, h), 0, 255).astype(np.uint8)
        data = _png(rgb)
        path = OUT / name
        path.write_bytes(data)
        rows.append({
            "asset_id": asset_id,
            "family": family,
            "file_path": f"socio_sim/web/static/assets/v4/{name}",
            "role": role,
            "aspect_ratio": aspect,
            "intrinsic_width": w,
            "intrinsic_height": h,
            "source_type": "synthetic_decorative_artwork",
            "license": "MIT project-owned",
            "provenance": ("generated by scripts/generate_v4_assets.py "
                           f"(art-directed '{family}' family); no real "
                           "people, brands, screenshots, or KPIs"),
            "content_risk_tags": ["decorative", "non_documentary",
                                  "no_people", "no_brands"],
            "accessibility_alt_template": (
                f"Synthetic decorative artwork ({blurb}) used as a SocioSim "
                f"{_ROLE_LABEL[role]}; not evidence."),
            "sha256": hashlib.sha256(data).hexdigest(),
            "perceptual_hash": _phash(rgb),
            "approval_status": "qa_pending",
        })
    return rows


def _phash(rgb: np.ndarray) -> str:
    small = rgb[:: max(rgb.shape[0] // 16, 1), :: max(rgb.shape[1] // 16, 1), :][:16, :16]
    gray = small.mean(axis=2)
    bits = gray > gray.mean()
    value = 0
    for bit in bits.flatten():
        value = (value << 1) | int(bit)
    return f"{value:064x}"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.png"):
        old.unlink()
    records = []
    records += _write("feed_cover", "feed-cover-v4", 48, 1200, 800, "3:2", 1100)
    records += _write("ad_creative", "ad-creative-v4", 32, 1200, 600, "2:1", 2100)
    records += _write("editorial_system", "editorial-v4", 16, 1600, 900, "16:9", 3100)
    registry = {
        "schema_version": 2,
        "generated_by": "scripts/generate_v4_assets.py",
        "families": {name: blurb for name, (_, blurb) in FAMILIES.items()},
        "human_review": {
            "status": "not_reviewed",
            "reviewer": "",
            "date": "",
            "scope": "",
            "defects_found": [],
        },
        "assets": records,
    }
    (OUT / "registry.json").write_text(json.dumps(registry, indent=2, sort_keys=True),
                                       encoding="utf-8")
    per_family: dict = {}
    for rec in records:
        per_family[rec["family"]] = per_family.get(rec["family"], 0) + 1
    print(f"generated {len(records)} v4 assets in {OUT} "
          f"({len(per_family)} families: {per_family})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
