"""Scan decision-facing files for unsupported claim language and legacy assets."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PATTERNS = [
    "feed-atlas-v3",
    "ad-atlas-v3",
    "feed-cover-v3",
    "ad-creative-v3",
    "real trained",
    "real model",
    "decision-grade campaign winner",
    "CUPED lift",
    "visually verified",
    "evidence-based",
]

ALLOW = (
    "scripts/claim_scan.py",
    "scripts/asset_qa.py",
    "AUDIT_REMEDIATION_REPORT.md",
    "BASELINE_AUDIT_SNAPSHOT.md",
)


def tracked_files() -> list[Path]:
    out = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True)
    return [ROOT / line for line in out.splitlines()]


def main() -> int:
    errors = []
    for path in tracked_files():
        rel = path.relative_to(ROOT).as_posix()
        if rel in ALLOW or path.suffix.lower() in {".png", ".gz", ".coverage"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        lower = text.lower()
        for pat in PATTERNS:
            if pat.lower() in lower:
                errors.append(f"{rel}: unsupported/stale phrase {pat!r}")
    if errors:
        print("\n".join(errors[:80]))
        return 1
    print("claim scan passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
