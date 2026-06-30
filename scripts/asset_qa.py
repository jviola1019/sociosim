"""Validate the SocioSim v4 asset registry and packaged PNG files."""

from __future__ import annotations

import hashlib
import json
import struct
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "socio_sim" / "web" / "static" / "assets" / "v4"
REGISTRY = ASSET_DIR / "registry.json"
DOC = ROOT / "docs" / "ASSET_QA.md"


def png_dims(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path}: not a PNG")
    return struct.unpack(">II", data[16:24])


def png_chunks(path: Path) -> list[str]:
    data = path.read_bytes()
    chunks = []
    i = 8
    while i < len(data):
        n = struct.unpack(">I", data[i:i + 4])[0]
        typ = data[i + 4:i + 8].decode("ascii")
        chunks.append(typ)
        i += 12 + n
    return chunks


def phash(path: Path) -> str:
    data = path.read_bytes()
    import zlib
    w, h = png_dims(path)
    i = 8
    raw = bytearray()
    while i < len(data):
        n = struct.unpack(">I", data[i:i + 4])[0]
        typ = data[i + 4:i + 8]
        body = data[i + 8:i + 8 + n]
        if typ == b"IDAT":
            raw.extend(zlib.decompress(body))
        i += 12 + n
    stride = w * 3 + 1
    rows = []
    for y in range(h):
        row = raw[y * stride + 1:(y + 1) * stride]
        rows.append(row)
    import numpy as np
    rgb = np.frombuffer(b"".join(rows), dtype=np.uint8).reshape(h, w, 3)
    small = rgb[:: max(h // 16, 1), :: max(w // 16, 1), :][:16, :16]
    gray = small.mean(axis=2)
    bits = gray > gray.mean()
    value = 0
    for bit in bits.flatten():
        value = (value << 1) | int(bit)
    return f"{value:064x}"


def hamming_hex(a: str, b: str) -> int:
    return (int(a, 16) ^ int(b, 16)).bit_count()


def make_contact_sheet(records: list[dict]) -> str:
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return "not generated: Pillow unavailable"
    thumbs = []
    for rec in records:
        im = Image.open(ROOT / rec["file_path"]).resize((180, 120))
        canvas = Image.new("RGB", (180, 146), "white")
        canvas.paste(im, (0, 0))
        draw = ImageDraw.Draw(canvas)
        draw.text((4, 124), rec["asset_id"], fill=(0, 0, 0))
        thumbs.append(canvas)
    cols = 8
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 180, rows * 146), "white")
    for i, im in enumerate(thumbs):
        sheet.paste(im, ((i % cols) * 180, (i // cols) * 146))
    out = ASSET_DIR / "contact-sheet-v4.png"
    sheet.save(out)
    return str(out.relative_to(ROOT))


def main() -> int:
    errors: list[str] = []
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = registry.get("assets", [])
    seen_files = set()
    seen_sha = {}
    hashes = []
    expected = {"feed_cover": (1200, 800), "ad_creative": (1200, 600),
                "editorial_system": (1600, 900)}
    for rec in records:
        path = ROOT / rec["file_path"]
        seen_files.add(path.resolve())
        if not path.is_file():
            errors.append(f"missing file {path}")
            continue
        dims = png_dims(path)
        if dims != expected.get(rec["role"]):
            errors.append(f"{path}: dimensions {dims} do not match role {rec['role']}")
        chunks = png_chunks(path)
        bad_chunks = {"tEXt", "iTXt", "zTXt", "eXIf"} & set(chunks)
        if bad_chunks:
            errors.append(f"{path}: unsupported metadata chunks {sorted(bad_chunks)}")
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        if sha != rec.get("sha256"):
            errors.append(f"{path}: stale sha256")
        if sha in seen_sha:
            errors.append(f"{path}: exact duplicate of {seen_sha[sha]}")
        seen_sha[sha] = rec["asset_id"]
        ph = phash(path)
        if ph != rec.get("perceptual_hash"):
            errors.append(f"{path}: stale perceptual hash")
        hashes.append((rec["asset_id"], ph))
        alt = rec["accessibility_alt_template"].lower()
        if "evidence" in alt and "not evidence" not in alt:
            errors.append(f"{path}: alt text implies evidence")
    for i, (aid, hp) in enumerate(hashes):
        for bid, hq in hashes[i + 1:]:
            if hamming_hex(hp, hq) <= 4:
                errors.append(f"suspicious near duplicate: {aid} {bid}")
    orphans = sorted(p for p in ASSET_DIR.glob("*.png")
                     if p.name != "contact-sheet-v4.png" and p.resolve() not in seen_files)
    if orphans:
        errors.append("orphaned files: " + ", ".join(str(p) for p in orphans))
    tracked = subprocess.run(["git", "grep", "-nE",
                              "feed-atlas-v3|ad-atlas-v3|feed-cover-v3|ad-creative-v3"],
                             cwd=ROOT, text=True, capture_output=True)
    stale_lines = [
        line for line in tracked.stdout.splitlines()
        if "AUDIT_REMEDIATION_REPORT" not in line
        and "ASSET_QA" not in line
        and "scripts/asset_qa.py" not in line
        and "tests/test_asset_v4.py" not in line
    ]
    if stale_lines:
        errors.append("legacy asset references remain:\n" + "\n".join(stale_lines[:40]))
    sheet_status = make_contact_sheet(records)
    DOC.write_text("\n".join([
        "# SocioSim Asset QA",
        "",
        "Status: " + ("PASS" if not errors else "FAIL"),
        f"Registered assets: {len(records)}",
        f"Contact sheet: `{sheet_status}`",
        "",
        "Human visual review: not performed. Do not claim visual verification.",
        "",
        "Known limitations:",
        "- Perceptual hash duplicate checks are automated screening, not human review.",
        "- Assets are synthetic decorative artwork, not evidence.",
        "",
        "Errors:",
        *(f"- {e}" for e in errors),
        "",
    ]), encoding="utf-8")
    if errors:
        print("\n".join(errors))
        return 1
    print(f"asset QA passed for {len(records)} records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
