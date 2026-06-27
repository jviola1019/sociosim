"""Scenario-as-code linting for SocioSim examples and release gates."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import yaml

from socio_sim.config import ConfigError, RunConfig


REQUIRED_FIELDS = {
    "scenario_id",
    "version",
    "lab_mode",
    "purpose",
    "intended_use",
    "prohibited_use",
    "primary_question",
    "primary_metric",
    "secondary_metrics",
    "assumptions",
    "provenance",
    "research_only_notice",
    "config",
}

LAB_MODES = {"society_policy", "entrepreneur_market", "compare"}
PROVENANCE_CLASSES = {
    "model_derived",
    "calibration_consistent",
    "aggregate_backtested",
    "component_measured",
    "synthetic_assumption",
    "unsupported",
}
PROFILE_FACTORIES = {
    "standard": RunConfig.standard,
    "quick": RunConfig.quick,
    "test": RunConfig.test,
    "calibrated": RunConfig.calibrated,
}
UNSUPPORTED_CLAIMS = (
    "will reduce misinformation",
    "will increase sales",
    "will improve roi",
    "real-world forecast",
)


def scenario_files(paths: Iterable[str | Path]) -> list[Path]:
    out: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            out.extend(sorted(path.glob("*.yml")))
            out.extend(sorted(path.glob("*.yaml")))
        else:
            out.append(path)
    return out


def load_scenario(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError("top-level YAML must be a mapping")
    return data


def config_from_scenario(data: dict) -> RunConfig:
    cfg_data = dict(data.get("config") or {})
    profile = cfg_data.pop("profile", "test")
    if profile not in PROFILE_FACTORIES:
        raise ConfigError(f"config.profile: must be one of {sorted(PROFILE_FACTORIES)}")
    return PROFILE_FACTORIES[profile](**cfg_data).validate()


def lint_scenario(data: dict) -> list[str]:
    errors: list[str] = []
    missing = sorted(REQUIRED_FIELDS - set(data))
    if missing:
        errors.append(f"missing required fields: {', '.join(missing)}")

    lab_mode = data.get("lab_mode")
    if lab_mode not in LAB_MODES:
        errors.append(f"lab_mode must be one of {sorted(LAB_MODES)}")

    for list_field in ("intended_use", "prohibited_use", "secondary_metrics", "assumptions"):
        if not isinstance(data.get(list_field), list) or not data.get(list_field):
            errors.append(f"{list_field} must be a non-empty list")

    provenance = data.get("provenance")
    if provenance not in PROVENANCE_CLASSES:
        errors.append(f"provenance must be one of {sorted(PROVENANCE_CLASSES)}")

    notice = str(data.get("research_only_notice", "")).lower()
    if "not a real-world forecast" not in notice:
        errors.append("research_only_notice must say 'not a real-world forecast'")

    combined = yaml.safe_dump(data, sort_keys=True).lower()
    for phrase in UNSUPPORTED_CLAIMS:
        if phrase in combined and phrase not in notice:
            errors.append(f"unsafe unsupported claim text: {phrase!r}")

    if lab_mode == "entrepreneur_market":
        money_notice = str(data.get("synthetic_money_notice", "")).lower()
        if "synthetic scenario input/output" not in money_notice:
            errors.append(
                "entrepreneur_market scenarios require synthetic_money_notice")

    try:
        config_from_scenario(data)
    except Exception as exc:
        errors.append(f"config invalid: {type(exc).__name__}: {exc}")
    return errors


def lint_path(path: Path) -> list[str]:
    try:
        data = load_scenario(path)
    except Exception as exc:
        return [f"{path}: load failed: {type(exc).__name__}: {exc}"]
    return [f"{path}: {err}" for err in lint_scenario(data)]


def lint_paths(paths: Iterable[str | Path]) -> list[str]:
    files = scenario_files(paths)
    if not files:
        return ["no scenario files found"]
    errors: list[str] = []
    for path in files:
        errors.extend(lint_path(path))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lint SocioSim scenario YAML files.")
    parser.add_argument("paths", nargs="*", default=["examples/scenarios"])
    args = parser.parse_args(argv)
    errors = lint_paths(args.paths)
    if errors:
        for err in errors:
            print(f"ERROR: {err}")
        return 1
    print(f"Scenario lint passed for {len(scenario_files(args.paths))} file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
