"""Fail closed when evidence metadata or stale generated reports are missing."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from socio_sim.evidence import validate_registry

ROOT = Path(__file__).resolve().parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    errors = validate_registry()
    registry = ROOT / "socio_sim" / "web" / "static" / "assets" / "v4" / "registry.json"
    if not registry.is_file():
        errors.append("missing v4 asset registry")
    else:
        data = json.loads(registry.read_text(encoding="utf-8"))
        if len(data.get("assets", [])) < 92:
            errors.append("v4 asset registry has fewer than 92 assets")
        # H-01/H-02: verify sha256 of each registered asset file. The gate
        # fails CLOSED: an asset with no sha256 cannot be integrity-verified
        # and a registered file missing from disk is itself the failure --
        # neither may be silently skipped.
        for asset in data.get("assets", []):
            asset_id = asset.get("asset_id", asset.get("file_path", "?"))
            fp = ROOT / asset.get("file_path", "")
            expected_sha = asset.get("sha256", "")
            if not expected_sha:
                errors.append(
                    f"asset {asset_id}: no sha256 in registry "
                    "(integrity cannot be verified; gate fails closed)")
            elif not fp.is_file():
                errors.append(
                    f"asset {asset_id}: registered file missing: "
                    f"{asset.get('file_path')}")
            else:
                actual_sha = sha(fp)
                if actual_sha != expected_sha:
                    errors.append(
                        f"asset {asset_id}: "
                        f"sha256 mismatch (registry={expected_sha[:12]}... "
                        f"actual={actual_sha[:12]}...)"
                    )
    for report in ("BENCHMARK_REPORT.md", "BACKTEST_REPORT.md", "VALIDATION_REPORT.md"):
        p = ROOT / report
        if p.exists():
            text = p.read_text(encoding="utf-8", errors="replace").lower()
            if "highest rung" in text or "validates aggregate" in text:
                errors.append(f"{report}: stale positive claim remains")
    if errors:
        print("\n".join(errors))
        return 1
    print("evidence gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
