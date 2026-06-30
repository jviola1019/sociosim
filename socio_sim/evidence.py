"""Evidence and provenance records for decision-facing SocioSim outputs.

The rule here is deliberately conservative: a number without a usable evidence
record is not evidence. It is either an explicit scenario assumption, a
synthetic engineering diagnostic, user supplied, or unsupported.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any


class EvidenceKind(str, Enum):
    MEASURED = "measured"
    EXTERNAL_AGGREGATE = "external_aggregate"
    SCENARIO_ASSUMPTION = "scenario_assumption"
    SYNTHETIC_ENGINEERING = "synthetic_engineering"
    USER_SUPPLIED = "user_supplied"
    UNSUPPORTED = "unsupported"


REQUIRED_FIELDS = (
    "id",
    "kind",
    "source_title",
    "source_url",
    "source_version_or_revision",
    "retrieved_at",
    "license",
    "data_scope",
    "units",
    "population",
    "time_window",
    "known_limitations",
    "valid_uses",
    "invalid_uses",
    "verification_status",
)


@dataclass(frozen=True)
class EvidenceRecord:
    id: str
    kind: EvidenceKind
    source_title: str
    source_url: str
    source_version_or_revision: str
    retrieved_at: str
    license: str
    data_scope: str
    units: str
    population: str
    time_window: str
    known_limitations: list[str]
    valid_uses: list[str]
    invalid_uses: list[str]
    verification_status: str
    source_sha256: str | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "EvidenceRecord":
        missing = [field for field in REQUIRED_FIELDS if field not in raw]
        if missing:
            raise ValueError(f"evidence record missing fields: {missing}")
        return cls(
            id=str(raw["id"]),
            kind=EvidenceKind(str(raw["kind"])),
            source_title=str(raw["source_title"]),
            source_url=str(raw["source_url"]),
            source_version_or_revision=str(raw["source_version_or_revision"]),
            retrieved_at=str(raw["retrieved_at"]),
            license=str(raw["license"]),
            data_scope=str(raw["data_scope"]),
            units=str(raw["units"]),
            population=str(raw["population"]),
            time_window=str(raw["time_window"]),
            known_limitations=list(raw["known_limitations"]),
            valid_uses=list(raw["valid_uses"]),
            invalid_uses=list(raw["invalid_uses"]),
            verification_status=str(raw["verification_status"]),
            source_sha256=raw.get("source_sha256"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "source_title": self.source_title,
            "source_url": self.source_url,
            "source_version_or_revision": self.source_version_or_revision,
            "retrieved_at": self.retrieved_at,
            "license": self.license,
            "data_scope": self.data_scope,
            "units": self.units,
            "population": self.population,
            "time_window": self.time_window,
            "known_limitations": list(self.known_limitations),
            "valid_uses": list(self.valid_uses),
            "invalid_uses": list(self.invalid_uses),
            "verification_status": self.verification_status,
            "source_sha256": self.source_sha256,
        }


def _resource_json(name: str) -> Any:
    data = resources.files("socio_sim").joinpath("data", name).read_text(encoding="utf-8")
    return json.loads(data)


@lru_cache(maxsize=1)
def evidence_registry() -> dict[str, EvidenceRecord]:
    raw = _resource_json("evidence_registry.json")
    records = [EvidenceRecord.from_dict(item) for item in raw["records"]]
    out: dict[str, EvidenceRecord] = {}
    for rec in records:
        if rec.id in out:
            raise ValueError(f"duplicate evidence id: {rec.id}")
        out[rec.id] = rec
    return out


@lru_cache(maxsize=1)
def scenario_assumptions() -> dict[str, dict[str, Any]]:
    raw = _resource_json("scenario_assumptions.json")
    return {str(item["id"]): dict(item) for item in raw["assumptions"]}


def get_evidence(evidence_id: str) -> EvidenceRecord:
    try:
        return evidence_registry()[evidence_id]
    except KeyError as exc:
        raise KeyError(f"unknown evidence id: {evidence_id}") from exc


def evidence_dict(evidence_id: str) -> dict[str, Any]:
    return get_evidence(evidence_id).to_dict()


def metric_evidence(evidence_id: str) -> dict[str, Any]:
    rec = get_evidence(evidence_id)
    return {
        "evidence_id": rec.id,
        "evidence_kind": rec.kind.value,
        "verification_status": rec.verification_status,
        "valid_uses": list(rec.valid_uses),
        "invalid_uses": list(rec.invalid_uses),
        "known_limitations": list(rec.known_limitations),
    }


def file_sha256(path: str | Path) -> str:
    p = Path(path)
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_registry() -> list[str]:
    errors: list[str] = []
    for rec in evidence_registry().values():
        if rec.kind is EvidenceKind.MEASURED and rec.verification_status != "verified":
            errors.append(f"{rec.id}: measured evidence must be verified")
        if rec.kind is EvidenceKind.UNSUPPORTED and rec.verification_status == "verified":
            errors.append(f"{rec.id}: unsupported evidence cannot be verified")
        for field in ("known_limitations", "valid_uses", "invalid_uses"):
            if not getattr(rec, field):
                errors.append(f"{rec.id}: {field} must be non-empty")
    for item in scenario_assumptions().values():
        evidence_id = str(item.get("evidence_id", ""))
        if evidence_id not in evidence_registry():
            errors.append(f"{item.get('id')}: unknown evidence_id {evidence_id}")
        elif evidence_registry()[evidence_id].kind is not EvidenceKind.SCENARIO_ASSUMPTION:
            errors.append(f"{item.get('id')}: assumption must use scenario_assumption evidence")
    return errors
