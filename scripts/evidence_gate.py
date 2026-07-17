"""Fail closed when evidence metadata or stale generated reports are missing."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from socio_sim.evidence import validate_registry

ROOT = Path(__file__).resolve().parents[1]

# C-03: generated reports are scanned with the SAME risky-term vocabulary +
# hedge/negation logic as the repo-wide claim scanner, not a private
# two-phrase list a regenerated report could trivially sidestep.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import claim_scan  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


#: verification_status values that CLAIM the value was read out of (or
#: derived from) a primary source. Such a claim without a reproducible
#: statistic location -- and, for derived values, an explicit derivation --
#: is unauditable and must fail the gate.
_SOURCE_VERIFIED_STATUSES = {
    "value_verified_against_source",
    "value_derived_from_verified_source",
}


def sourced_target_errors() -> list:
    """Reject source-verified claims that another auditor could not reproduce:
    every such target needs a quoted statistic_location, a stated
    transformation, and a hashed source artifact with retrieval instructions."""
    errors = []
    path = ROOT / "socio_sim" / "data" / "benchmarks" / "sourced_aggregates_v1.json"
    if not path.is_file():
        # Fail CLOSED: without the default target set the sourced-claim
        # checks cannot run, which is itself a gate failure, not a skip.
        return [f"sourced targets file missing: {path} "
                "(source-verified claims cannot be checked; gate fails closed)"]
    targets = json.loads(path.read_text(encoding="utf-8"))["targets"]
    for name, spec in targets.items():
        status = spec.get("verification_status", "")
        if status not in _SOURCE_VERIFIED_STATUSES:
            continue
        where = f"sourced_aggregates_v1:{name}"
        if not str(spec.get("statistic_location", "")).strip():
            errors.append(f"{where}: claims {status} but has no "
                          "statistic_location (not reproducible)")
        if not str(spec.get("transformation", "")).strip():
            errors.append(f"{where}: claims {status} but has no "
                          "transformation statement")
        if (status == "value_derived_from_verified_source"
                and str(spec.get("transformation", "")).strip().lower()
                .startswith("none")):
            errors.append(f"{where}: derived value must state its "
                          "derivation, not 'none'")
        art = spec.get("source_artifact") or {}
        if not (art.get("sha256") and art.get("artifact_url")
                and art.get("retrieval_instructions")):
            errors.append(f"{where}: claims {status} but source_artifact is "
                          "missing sha256/artifact_url/retrieval_instructions")
        elif spec.get("source_hash") != art.get("sha256"):
            errors.append(f"{where}: source_hash does not match "
                          "source_artifact.sha256")
    return errors


def main() -> int:
    errors = validate_registry()
    errors.extend(sourced_target_errors())
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
            # G-01: every asset needs a text alternative (WCAG 2.2 SC 1.1.1)
            # for the UI to render meaningful alt attributes.
            if not str(asset.get("accessibility_alt_template", "")).strip():
                errors.append(
                    f"asset {asset_id}: missing accessibility_alt_template "
                    "(WCAG 1.1.1 text alternative)")
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
    # AGGREGATE_FIT_NOTE.md is the renamed CALIBRATION_REPORT.md; the old
    # name stays in the tuple as a guard against the file being recreated.
    for report in ("BENCHMARK_REPORT.md", "BACKTEST_REPORT.md",
                   "VALIDATION_REPORT.md", "AGGREGATE_FIT_NOTE.md",
                   "CALIBRATION_REPORT.md"):
        p = ROOT / report
        if p.exists():
            text = p.read_text(encoding="utf-8", errors="replace")
            if ("highest rung" in text.lower()
                    or "validates aggregate" in text.lower()):
                errors.append(f"{report}: stale positive claim remains")
            errors.extend(claim_scan._stale_phrase_errors(report, text))
            errors.extend(claim_scan._context_aware_errors(report, text))
    if errors:
        print("\n".join(errors))
        return 1
    print("evidence gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
