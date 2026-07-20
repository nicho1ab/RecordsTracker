from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy import inspect, select
from sqlalchemy.engine import Connection

from ccld_complaints.hosted_app.facility_identity_projection import (
    FacilityProjectionField,
    FacilityProjectionSourceAvailability,
    FacilitySourceKind,
    facility_projection_candidate_from_values,
    project_facility_identity,
)
from ccld_complaints.hosted_app.facility_reference_preload import (
    FACILITY_REFERENCE_DATASET_SLUG,
    FACILITY_REFERENCE_TABLE_NAME,
    hosted_facility_reference_records,
)
from ccld_complaints.source_profiling import FACILITY_SOURCE_REGISTRY

FACILITY_REFERENCE_EXTRACTION_METHOD = "approved_ccld_facility_reference"
FACILITY_REFERENCE_FIELD_NAMES = ("facility_type", "county", "status")
_REFERENCE_PROJECTION_FIELDS = {
    "facility_type": FacilityProjectionField.FACILITY_TYPE,
    "county": FacilityProjectionField.COUNTY,
    "status": FacilityProjectionField.STATUS,
}
_REFERENCE_FIELD_PROVENANCE_KEY = "_projection_field_provenance"
_REFERENCE_CONFLICTS_KEY = "_projection_reference_conflicts"
_UNSAFE_REFERENCE_MARKERS = frozenset(
    {"fixture", "mock", "synthetic", "sample", "tiny", "test-only", "test_only"}
)
_APPROVED_RESOURCE_IDS = frozenset(
    str(resource["resource_id"])
    for resource in FACILITY_SOURCE_REGISTRY["target_resources"]
    if resource.get("resource_id")
)


class FacilityReferenceConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class CcldSourceRefreshPreparation:
    records: tuple[Mapping[str, Any], ...]
    reference_found: bool
    warnings: tuple[str, ...]
    conflicted_field_count: int


def prepare_ccld_hosted_source_records(
    connection: Connection,
    records: Sequence[Mapping[str, Any]],
    *,
    allow_test_reference: bool = False,
    include_facility_reference: bool = True,
) -> CcldSourceRefreshPreparation:
    """Enrich validated CCLD bundles before the shared hosted upsert.

    Approved facility-reference values own facility master fields. An explicit
    report facility type is retained when the approved reference has no type;
    otherwise the approved reference value wins and both values remain audited.
    """

    prepared = tuple(copy.deepcopy(dict(record)) for record in records)
    facility_numbers = {
        _required_facility_number(record)
        for record in prepared
        if isinstance(record.get("facility"), Mapping)
    }
    reference_by_facility: dict[str, Mapping[str, Any]] = {}
    warnings: list[str] = []
    if facility_numbers and include_facility_reference:
        reference_by_facility, reference_warnings = _approved_reference_rows(
            connection,
            facility_numbers,
            allow_test_reference=allow_test_reference,
        )
        warnings.extend(reference_warnings)

    conflict_count = 0
    for record in prepared:
        facility = record.get("facility")
        if not isinstance(facility, dict):
            continue
        facility_number = _required_facility_number(record)
        reference = reference_by_facility.get(facility_number)
        if reference is None:
            continue
        document = record.get("source_document")
        if not isinstance(document, Mapping):
            raise ValueError("CCLD hosted refresh record requires source_document context.")
        document_id = _required_text(document, "document_id")
        audits = record.setdefault("extraction_audit", [])
        if not isinstance(audits, list):
            raise ValueError("CCLD hosted refresh extraction_audit must be a list.")
        provenance: dict[str, Any] = {}
        conflicts: list[dict[str, Any]] = []
        projection_conflicts = reference.get(_REFERENCE_CONFLICTS_KEY)
        if isinstance(projection_conflicts, Mapping):
            for field_name in FACILITY_REFERENCE_FIELD_NAMES:
                conflict_values = projection_conflicts.get(field_name)
                if not isinstance(conflict_values, Sequence) or isinstance(
                    conflict_values, str
                ):
                    continue
                conflict_count += 1
                conflicts.append(
                    {
                        "field_name": field_name,
                        "report_or_existing_value": _optional_text(
                            facility, field_name
                        ),
                        "facility_reference_values": list(conflict_values),
                        "resolution": "unresolved_same_precedence_reference_conflict",
                    }
                )
                warnings.append(
                    "Eligible approved facility-reference rows disagree; the shared "
                    "projection left one canonical allocation field unchanged."
                )
        field_provenance = reference.get(_REFERENCE_FIELD_PROVENANCE_KEY)
        for field_name in FACILITY_REFERENCE_FIELD_NAMES:
            incoming = _optional_text(reference, field_name)
            if incoming is None:
                continue
            source_reference = (
                field_provenance.get(field_name)
                if isinstance(field_provenance, Mapping)
                else None
            )
            if not isinstance(source_reference, Mapping):
                source_reference = reference
            previous = facility.get(field_name)
            conflict = _nonblank(previous) and str(previous).strip() != incoming
            if conflict:
                conflict_count += 1
                conflicts.append(
                    {
                        "field_name": field_name,
                        "report_or_existing_value": str(previous).strip(),
                        "facility_reference_value": incoming,
                        "resolution": "approved_facility_reference_precedence",
                        "source_resource_id": _required_text(
                            source_reference, "source_resource_id"
                        ),
                        "source_dataset_slug": _required_text(
                            source_reference, "source_dataset_slug"
                        ),
                        "source_field": f"{FACILITY_REFERENCE_TABLE_NAME}.{field_name}",
                        "snapshot_date": _optional_text(
                            source_reference, "snapshot_date"
                        ),
                        "source_accessed_at": _required_text(
                            source_reference, "source_accessed_at"
                        ),
                    }
                )
            facility[field_name] = incoming
            provenance[field_name] = {
                "source_kind": "approved_facility_reference",
                "source_resource_id": _required_text(
                    source_reference, "source_resource_id"
                ),
                "source_dataset_slug": _required_text(
                    source_reference, "source_dataset_slug"
                ),
                "source_field": f"{FACILITY_REFERENCE_TABLE_NAME}.{field_name}",
                "snapshot_date": _optional_text(source_reference, "snapshot_date"),
                "source_accessed_at": _required_text(
                    source_reference, "source_accessed_at"
                ),
            }
            audits.append(
                {
                    "audit_id": f"{document_id}-facility-reference-{field_name}",
                    "document_id": document_id,
                    "field_name": f"facility.{field_name}",
                    "extraction_method": FACILITY_REFERENCE_EXTRACTION_METHOD,
                    "extractor_version": "1.0.0",
                    "extracted_value": incoming,
                    "confidence": 1.0,
                    "source_text": None,
                    "source_section": "approved facility reference",
                    "warning": (
                        "Approved facility-reference value took precedence over a conflicting "
                        "nonblank report or existing value."
                        if conflict
                        else None
                    ),
                }
            )
        if provenance or conflicts:
            record["hosted_refresh"] = {
                "facility_field_provenance": provenance,
                "facility_reference_conflicts": conflicts,
            }

    return CcldSourceRefreshPreparation(
        records=cast(tuple[Mapping[str, Any], ...], prepared),
        reference_found=bool(reference_by_facility),
        warnings=tuple(dict.fromkeys(warnings)),
        conflicted_field_count=conflict_count,
    )


def validate_approved_facility_reference_configuration(
    connection: Connection,
    facility_numbers: Sequence[str],
) -> tuple[str, ...]:
    """Validate selected reference rows before an apply-mode backfill writes."""

    if not inspect(connection).has_table(FACILITY_REFERENCE_TABLE_NAME):
        raise FacilityReferenceConfigurationError(
            "Facility-reference configuration is not initialized for hosted backfill."
        )
    _rows, warnings = _approved_reference_rows(
        connection,
        set(facility_numbers),
        allow_test_reference=False,
    )
    return warnings


def _approved_reference_rows(
    connection: Connection,
    facility_numbers: set[str],
    *,
    allow_test_reference: bool,
) -> tuple[dict[str, Mapping[str, Any]], tuple[str, ...]]:
    if not inspect(connection).has_table(FACILITY_REFERENCE_TABLE_NAME):
        return {}, ()
    rows = tuple(
        dict(row)
        for row in connection.execute(
            select(hosted_facility_reference_records).where(
                hosted_facility_reference_records.c.facility_number.in_(
                    sorted(facility_numbers)
                )
            )
        ).mappings()
    )
    unsafe_rows = tuple(row for row in rows if _unsafe_reference_row(row))
    if unsafe_rows and not allow_test_reference:
        raise FacilityReferenceConfigurationError(
            "Facility-reference configuration contains fixture, mock, tiny, synthetic, "
            "sample, or test-only provenance for a selected hosted facility."
        )
    approved_rows = tuple(
        row
        for row in rows
        if (allow_test_reference or not _unsafe_reference_row(row))
        and _approved_reference_identity(row)
    )
    selected: dict[str, Mapping[str, Any]] = {}
    warnings: list[str] = []
    for facility_number in sorted(facility_numbers):
        candidates = [
            row for row in approved_rows if row.get("facility_number") == facility_number
        ]
        if not candidates:
            warnings.append(
                "No approved facility-reference row was available for one selected facility; "
                "existing facility master values remain unchanged."
            )
            continue
        selected[facility_number] = _merge_reference_candidates(candidates)
    return selected, tuple(dict.fromkeys(warnings))


def _merge_reference_candidates(
    candidates: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any]:
    """Adapt approved rows to the shared projection without selecting locally."""

    ordered = sorted(
        candidates,
        key=lambda row: (
            str(row.get("snapshot_date") or ""),
            str(row.get("source_accessed_at") or ""),
            str(row.get("source_resource_id") or ""),
        ),
        reverse=True,
    )
    selected = dict(ordered[0])
    facility_number = _required_text(selected, "facility_number")
    row_by_identity: dict[str, Mapping[str, Any]] = {}
    projection_candidates = []
    for row in ordered:
        source_resource_id = _required_text(row, "source_resource_id")
        row_identity = f"{source_resource_id}:{facility_number}"
        row_by_identity[row_identity] = row
        projection_candidates.append(
            facility_projection_candidate_from_values(
                row,
                source_kind=FacilitySourceKind.PROGRAM_REFERENCE,
                source_row_identity=row_identity,
                snapshot_identity=(
                    f"{source_resource_id}:"
                    f"{str(row.get('snapshot_date') or row.get('source_accessed_at') or '')}"
                ),
                observed_at=_optional_text(row, "source_accessed_at"),
            )
        )
    projection = project_facility_identity(
        facility_number,
        projection_candidates,
        availability=FacilityProjectionSourceAvailability(
            program_reference=True,
            complaint_linked_facility=False,
        ),
    )
    field_provenance: dict[str, Mapping[str, Any]] = {}
    projection_conflicts: dict[str, tuple[str, ...]] = {}
    for field_name, projection_field in _REFERENCE_PROJECTION_FIELDS.items():
        result = projection.field(projection_field)
        if result.conflict:
            projection_conflicts[field_name] = tuple(
                dict.fromkeys(
                    str(alternative.raw_value)
                    for alternative in result.alternatives
                    if alternative.raw_value is not None
                )
            )
        selected[field_name] = (
            str(result.display_value) if result.display_value is not None else None
        )
        source_identity = result.source_identity
        if source_identity is not None:
            field_provenance[field_name] = row_by_identity[
                source_identity.source_row_identity
            ]
    selected[_REFERENCE_FIELD_PROVENANCE_KEY] = field_provenance
    selected[_REFERENCE_CONFLICTS_KEY] = projection_conflicts
    return selected


def _approved_reference_identity(row: Mapping[str, Any]) -> bool:
    return (
        str(row.get("source_resource_id") or "") in _APPROVED_RESOURCE_IDS
        and str(row.get("source_dataset_slug") or "") == FACILITY_REFERENCE_DATASET_SLUG
    )


def _unsafe_reference_row(row: Mapping[str, Any]) -> bool:
    inspected = " ".join(
        str(row.get(key) or "").casefold()
        for key in (
            "source_resource_id",
            "source_resource_name",
            "source_file_name",
            "source_dataset_slug",
        )
    )
    return any(marker in inspected for marker in _UNSAFE_REFERENCE_MARKERS)


def _required_facility_number(record: Mapping[str, Any]) -> str:
    facility = record.get("facility")
    if not isinstance(facility, Mapping):
        raise ValueError("CCLD hosted refresh record requires facility context.")
    value = _required_text(facility, "external_facility_number")
    if not value.isdigit():
        raise ValueError("CCLD hosted refresh facility number must contain digits only.")
    return value


def _required_text(values: Mapping[str, Any], field_name: str) -> str:
    value = _optional_text(values, field_name)
    if value is None:
        raise ValueError(f"Missing required hosted refresh value: {field_name}")
    return value


def _optional_text(values: Mapping[str, Any], field_name: str) -> str | None:
    value = values.get(field_name)
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _nonblank(value: object) -> bool:
    return value is not None and (not isinstance(value, str) or bool(value.strip()))
