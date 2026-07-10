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


def targets_metadata_complete(targets: dict) -> bool:
    """True only if every target carries an evidence record whose kind is
    not 'unsupported'. Shared gate for the web UI AND the CLI (audit C-02):
    neither surface may show an observed-vs-target distance comparison for
    targets whose evidence is unsupported. The legacy bundled benchmark
    targets are all 'unsupported' (missing source version/date range/
    population/source hash/tolerance rationale), so this is currently
    always False; it flips automatically if a fully-sourced target set is
    ever added."""
    if not targets:
        return False
    for t in targets.values():
        evidence_id = t.get("evidence_id")
        if not evidence_id:
            return False
        try:
            if get_evidence(evidence_id).kind is EvidenceKind.UNSUPPORTED:
                return False
        except KeyError:
            return False
    return True


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


#: Required per-default fields on every scenario_assumptions.json entry. Each
#: entry maps ONE decision-facing numeric default (not a whole module/class)
#: to its own identity, current value, and a short rationale -- this is what
#: keeps a single evidence_id (the shared "what kind of source is this"
#: record) from standing in for dozens of unrelated numeric defaults.
ASSUMPTION_REQUIRED_FIELDS = (
    "id", "evidence_id", "label", "path", "value", "units", "scope", "rationale",
)

#: Placeholder strings that must never appear as a live label/rationale -- if
#: present, the entry was drafted but never actually written.
_PLACEHOLDER_MARKERS = ("TODO", "TBD", "FIXME", "xxx", "lorem ipsum")


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
    _absent = object()
    # "value" may legitimately be 0, 0.0, or False (e.g. a disabled-by-default
    # rate), so presence is checked by key, not truthiness; the other fields
    # are all non-empty strings and truthiness is the right check for those.
    seen_paths: dict[str, str] = {}
    for item in scenario_assumptions().values():
        item_id = str(item.get("id", "<missing id>"))
        missing = [f for f in ASSUMPTION_REQUIRED_FIELDS
                   if item.get(f, _absent) is _absent
                   or (f != "value" and not item.get(f))]
        if missing:
            errors.append(f"{item_id}: missing/empty required fields {missing}")
            continue
        evidence_id = str(item["evidence_id"])
        if evidence_id not in evidence_registry():
            errors.append(f"{item_id}: unknown evidence_id {evidence_id}")
        elif evidence_registry()[evidence_id].kind is not EvidenceKind.SCENARIO_ASSUMPTION:
            errors.append(f"{item_id}: assumption must use scenario_assumption evidence")
        path = str(item["path"])
        if path in seen_paths:
            errors.append(
                f"{item_id}: path {path!r} duplicates {seen_paths[path]!r} -- "
                "one numeric default must not be claimed by two entries")
        seen_paths[path] = item_id
        for field in ("label", "rationale"):
            text = str(item[field])
            if any(marker.lower() in text.lower() for marker in _PLACEHOLDER_MARKERS):
                errors.append(f"{item_id}: {field} contains a placeholder marker")
    errors.extend(
        f"numeric default missing a scenario_assumptions.json provenance entry: {p}"
        for p in sorted(missing_numeric_default_provenance())
    )
    return errors


def missing_numeric_default_provenance() -> set[str]:
    """Decision-facing numeric defaults in code that have no matching `path`
    in scenario_assumptions.json. Covers the dataclass/dict-based registries
    that can be introspected mechanically (BehaviorParams, Campaign,
    category_base_rates, classifier_targets); does not (yet) cover defaults
    expressed as bare module-level constants or inline literals, which are
    tracked by hand (see AUDIT_LOG.md R6)."""
    from dataclasses import fields as dc_fields

    from socio_sim.ads.campaigns import Campaign
    from socio_sim.behavior import BehaviorParams
    from socio_sim.config import _default_base_rates, _default_classifier_targets

    present = {str(item["path"]) for item in scenario_assumptions().values()
               if item.get("path")}
    expected: set[str] = set()

    for f in dc_fields(BehaviorParams):
        expected.add(f"socio_sim.behavior.BehaviorParams.{f.name}")

    for cat in _default_base_rates():
        expected.add(f"socio_sim.config._default_base_rates['{cat}']")

    # classifier_targets applies one precision and one recall value uniformly
    # across every category (see assumption.classifier_target.*), not a
    # distinct claim per category.
    sample_target = next(iter(_default_classifier_targets().values()))
    if "precision" in sample_target:
        expected.add("socio_sim.config._default_classifier_targets()[*]['precision']")
    if "recall" in sample_target:
        expected.add("socio_sim.config._default_classifier_targets()[*]['recall']")

    campaign_exempt = {
        "id", "advertiser", "bid", "budget", "targeting",
        "holdout_fraction", "ftc_override",
    }
    for f in dc_fields(Campaign):
        if f.name.startswith("_") or f.name in campaign_exempt:
            continue
        expected.add(f"socio_sim.ads.campaigns.Campaign.{f.name}")

    return expected - present
