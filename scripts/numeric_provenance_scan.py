"""Numeric-default provenance scanner (fails closed on new defaults).

Finds decision-facing numeric DEFAULTS and requires each to be classified:
either it is covered by an entry in scenario_assumptions.json (path match)
or it appears in scripts/provenance_allowlist.json with an explicit
per-item classification and justification. Anything else fails the scan,
so a new unlabeled default cannot land silently.

Surfaces scanned (the places a number becomes a default a user inherits):
- Python dataclass/class-body field defaults        (socio_sim/**, run.py)
- module-level UPPERCASE constants, incl. numeric dict values
- argparse add_argument(default=...) in run.py and scripts/
- HTML <input> value/min/max/step attributes         (web/static/*.html)
- JS `?? <number>` fallbacks                         (web/static/*.js)

Deliberately out of scope, with reasons (not silent exemptions):
- function keyword defaults on internal helpers: implementation plumbing,
  reached only through the surfaces above;
- tests/: test-only values by definition;
- literals inside expressions/algorithms: behavior, not defaults -- the
  claim scanner and evidence gate police what is SAID about them.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST_PATH = ROOT / "scripts" / "provenance_allowlist.json"
ASSUMPTIONS_PATH = (ROOT / "socio_sim" / "data" / "scenario_assumptions.json")

PY_ROOTS = ["socio_sim", "scripts", "examples"]
CLASSIFICATIONS = {
    "scenario_assumption", "empirical_measurement", "external_aggregate",
    "technical_constant", "security_limit", "ui_formatting", "test_only",
    "unsupported_legacy_diagnostic",
}


def _num(node) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
        and not isinstance(node.value, bool)


def _const_expr(node) -> bool:
    """Numeric literal or pure-literal arithmetic (e.g. 2 * 1024 * 1024)."""
    if _num(node):
        return True
    if isinstance(node, ast.BinOp):
        return _const_expr(node.left) and _const_expr(node.right)
    if isinstance(node, ast.UnaryOp):
        return _const_expr(node.operand)
    return False


def _scan_python(path: Path, rel: str, found: dict) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    for node in ast.walk(tree):
        # Class bodies: dataclass fields / class constants with numeric defaults.
        if isinstance(node, ast.ClassDef):
            for stmt in node.body:
                target, value = None, None
                if isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
                    target, value = stmt.target, stmt.value
                elif isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                    target, value = stmt.targets[0], stmt.value
                if isinstance(target, ast.Name) and value is not None \
                        and _const_expr(value):
                    found[f"{rel}::{node.name}.{target.id}"] = ast.unparse(value)
        # Module-level UPPERCASE constants (numbers or dicts of numbers).
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            tgt = (node.targets[0] if isinstance(node, ast.Assign)
                   and len(node.targets) == 1 else
                   node.target if isinstance(node, ast.AnnAssign) else None)
            val = node.value
            if (isinstance(tgt, ast.Name) and tgt.id.isupper()
                    and not tgt.id.startswith("_") and val is not None):
                if _const_expr(val):
                    found[f"{rel}::{tgt.id}"] = ast.unparse(val)
                elif isinstance(val, ast.Dict):
                    for k, v in zip(val.keys, val.values):
                        if isinstance(k, ast.Constant) and _const_expr(v):
                            found[f"{rel}::{tgt.id}[{k.value!r}]"] = ast.unparse(v)
        # argparse defaults.
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "add_argument":
            flag = next((a.value for a in node.args
                         if isinstance(a, ast.Constant)
                         and str(a.value).startswith("--")), None)
            for kw in node.keywords:
                if kw.arg == "default" and _const_expr(kw.value) and flag:
                    found[f"{rel}::argparse.{flag}"] = ast.unparse(kw.value)


_HTML_ATTR = re.compile(
    r'<input\b[^>]*\bid="([^"]+)"[^>]*>', re.IGNORECASE)
_ATTR_NUM = re.compile(r'\b(value|min|max|step)="(-?\d+(?:\.\d+)?)"')
_JS_FALLBACK = re.compile(r'([A-Za-z_$][\w.$]*)\s*\?\?\s*(-?\d+(?:\.\d+)?)')


def _scan_html(path: Path, rel: str, found: dict) -> None:
    for m in _HTML_ATTR.finditer(path.read_text(encoding="utf-8",
                                                errors="replace")):
        for attr, num in _ATTR_NUM.findall(m.group(0)):
            found[f"{rel}::input#{m.group(1)}.{attr}"] = num


def _scan_js(path: Path, rel: str, found: dict) -> None:
    for m in _JS_FALLBACK.finditer(path.read_text(encoding="utf-8",
                                                  errors="replace")):
        name = m.group(1).split(".")[-1]
        found[f"{rel}::{name}??"] = m.group(2)


def _registry_paths() -> list[str]:
    data = json.loads(ASSUMPTIONS_PATH.read_text(encoding="utf-8"))
    return [str(item.get("path", "")) for item in data["assumptions"]]


def collect() -> dict:
    found: dict = {}
    for root in PY_ROOTS:
        for path in sorted((ROOT / root).rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            if rel == "scripts/numeric_provenance_scan.py":
                continue  # the scanner's own regex/scaffolding numbers
            _scan_python(path, rel, found)
    _scan_python(ROOT / "run.py", "run.py", found)
    static = ROOT / "socio_sim" / "web" / "static"
    for path in sorted(static.glob("*.html")):
        _scan_html(path, path.relative_to(ROOT).as_posix(), found)
    for path in sorted(static.glob("*.js")):
        _scan_js(path, path.relative_to(ROOT).as_posix(), found)
    return found


def main() -> int:
    found = collect()
    registry_paths = _registry_paths()
    allowlist = (json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))
                 if ALLOWLIST_PATH.is_file() else {})

    errors: list[str] = []
    for key, entry in sorted(allowlist.items()):
        if entry.get("classification") not in CLASSIFICATIONS:
            errors.append(f"allowlist {key}: bad classification "
                          f"{entry.get('classification')!r}")
        if len(str(entry.get("justification", ""))) < 15:
            errors.append(f"allowlist {key}: justification required")
        if key not in found:
            errors.append(f"allowlist {key}: stale (no longer found in code)")

    unclassified = []
    for key, value in sorted(found.items()):
        qualifier = key.split("::", 1)[1].split("[")[0]
        in_registry = any(qualifier in p for p in registry_paths)
        if in_registry or key in allowlist:
            continue
        unclassified.append(f"{key} = {value}")
    if unclassified:
        errors.append(
            f"{len(unclassified)} numeric default(s) without provenance -- "
            "add a scenario_assumptions.json entry or a JUSTIFIED "
            "provenance_allowlist.json entry:")
        errors.extend(f"  {u}" for u in unclassified)

    if errors:
        print("\n".join(errors[:120]))
        return 1
    print(f"numeric provenance scan passed: {len(found)} defaults "
          f"({len(allowlist)} allowlisted, rest registry-covered)")
    return 0


if __name__ == "__main__":
    if "--dump" in sys.argv:
        for key, value in sorted(collect().items()):
            print(f"{key} = {value}")
        raise SystemExit(0)
    raise SystemExit(main())
