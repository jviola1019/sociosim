"""Deep wheel-content validation (fails closed).

Goes beyond asset counts: loads the packaged registry, checks every
registered asset exists in the wheel with a matching SHA-256, decodes one
representative PNG per role (stdlib zlib/struct -- no Pillow), and asserts
the packaged data manifests are present and parseable. Run after
`python -m build --wheel`.
"""

from __future__ import annotations

import glob
import hashlib
import json
import struct
import zipfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_DATA = (
    "data/evidence_registry.json",
    "data/scenario_assumptions.json",
    "data/benchmarks/default_targets.json",
)
EXPECTED_ROLE_COUNTS = {"feed-cover-v4-": 48, "ad-creative-v4-": 32,
                        "editorial-v4-": 16}


def _decode_png(data: bytes) -> tuple[int, int]:
    """Decode a (non-interlaced RGB8) PNG fully; returns (w, h) or raises."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("bad PNG signature")
    w, h = struct.unpack(">II", data[16:24])
    idat = bytearray()
    i = 8
    while i < len(data):
        n = struct.unpack(">I", data[i:i + 4])[0]
        typ = data[i + 4:i + 8]
        if typ == b"IDAT":
            idat.extend(data[i + 8:i + 8 + n])
        i += 12 + n
    raw = zlib.decompress(bytes(idat))
    expected = h * (w * 3 + 1)  # RGB8 + one filter byte per row
    if len(raw) != expected:
        raise ValueError(f"decoded {len(raw)} bytes, expected {expected}")
    return w, h


def main() -> int:
    errors: list[str] = []
    wheels = sorted(glob.glob(str(ROOT / "dist" / "*.whl")))
    if not wheels:
        print("no wheel in dist/ -- run `python -m build --wheel` first")
        return 1
    wheel = wheels[-1]
    zf = zipfile.ZipFile(wheel)
    names = zf.namelist()

    for suffix in REQUIRED_DATA:
        matches = [n for n in names if n.endswith(suffix)]
        if not matches:
            errors.append(f"missing packaged data: {suffix}")
        else:
            try:
                json.loads(zf.read(matches[0]))
            except Exception as exc:
                errors.append(f"{suffix}: not parseable JSON ({exc!r})")
    if sum(n.endswith(".yaml") for n in names) != 4:
        errors.append("expected exactly 4 packaged policy packs")
    if any("v3" in n for n in names):
        errors.append("legacy v3 asset packaged")

    reg_matches = [n for n in names if n.endswith("assets/v4/registry.json")]
    if not reg_matches:
        errors.append("missing packaged v4 asset registry")
        print("\n".join(errors))
        return 1
    registry = json.loads(zf.read(reg_matches[0]))
    assets = registry.get("assets", [])
    by_name = {Path(a["file_path"]).name: a for a in assets}

    for prefix, count in EXPECTED_ROLE_COUNTS.items():
        packaged = [n for n in names
                    if n.endswith(".png") and Path(n).name.startswith(prefix)]
        if len(packaged) != count:
            errors.append(f"{prefix}*: {len(packaged)} packaged, want {count}")

    decoded_roles: set[str] = set()
    for n in names:
        base = Path(n).name
        rec = by_name.get(base)
        if not rec:
            continue
        blob = zf.read(n)
        if hashlib.sha256(blob).hexdigest() != rec.get("sha256"):
            errors.append(f"{base}: wheel sha256 does not match registry")
        role = rec.get("role", "")
        if role not in decoded_roles:  # one full decode per role
            try:
                w, h = _decode_png(blob)
                if (w, h) != (rec["intrinsic_width"], rec["intrinsic_height"]):
                    errors.append(f"{base}: decoded {w}x{h} != registry dims")
            except Exception as exc:
                errors.append(f"{base}: PNG decode failed ({exc!r})")
            decoded_roles.add(role)
    found_names = {Path(n).name for n in names}
    for base in by_name:
        if base not in found_names:
            errors.append(f"registry asset not packaged: {base}")

    if errors:
        print("\n".join(errors))
        return 1
    print(f"wheel QA passed: {Path(wheel).name} "
          f"({len(assets)} registered assets verified, "
          f"{len(decoded_roles)} roles decoded)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
