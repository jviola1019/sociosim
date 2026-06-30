"""Audit only the production dependencies declared in pyproject.toml.

This deliberately excludes test/E2E extras (playwright pulls starlette/pillow
which carry unrelated CVEs that socio_sim itself does not depend on or ship).
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    with open(ROOT / "pyproject.toml", "rb") as fh:
        data = tomllib.load(fh)
    deps: list[str] = data["project"]["dependencies"]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt",
                                    delete=False, encoding="utf-8") as fh:
        fh.write("\n".join(deps) + "\n")
        req_path = fh.name

    print(f"Auditing {len(deps)} production dependency spec(s):")
    for d in deps:
        print(f"  {d}")
    print()

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip_audit", "-r", req_path],
            cwd=ROOT,
        )
        return result.returncode
    finally:
        try:
            os.unlink(req_path)
        except OSError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
