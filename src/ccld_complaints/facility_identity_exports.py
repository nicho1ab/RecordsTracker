from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import defaultdict
from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Any

from ccld_complaints.hosted_app.facility_identity_presenter import (
    projected_conflict_text,
    projected_context_text,
    projected_display_text,
)
from ccld_complaints.hosted_app.facility_identity_projection import (
    FacilityIdentityProjection,
    FacilityProjectionCandidate,
    FacilityProjectionField,
    FacilityProjectionSourceAvailability,
    FacilitySourceKind,
    facility_projection_candidate_from_values,
    project_facility_identity,
)

FACILITY_EXPORT_IDENTITY_FIELDS = (
    FacilityProjectionField.FACILITY_NAME,
    FacilityProjectionField.FACILITY_TYPE,
    FacilityProjectionField.STATUS,
    FacilityProjectionField.CITY,
    FacilityProjectionField.COUNTY,
)


def load_sqlite_facility_identity_projections(
    connection: sqlite3.Connection,
    *,
    reference_records: Sequence[Mapping[str, Any]] = (),
) -> Mapping[str, FacilityIdentityProjection]:
    """Project SQLite complaint observations and optional reference observations.

    The adapter supplies observation identity only. Field reconciliation and
    selection remain exclusively owned by ``project_facility_identity``.
    """

    canonical_by_id: dict[str, list[FacilityProjectionCandidate]] = defaultdict(list)
    try:
        rows = connection.execute(
            """
            SELECT f.*, MAX(sd.retrieved_at) AS projection_observed_at
            FROM facilities f
            LEFT JOIN source_documents sd ON sd.facility_id = f.facility_id
            GROUP BY f.facility_id
            ORDER BY f.external_facility_number, f.facility_id
            """
        ).fetchall()
        complaint_available = True
    except sqlite3.OperationalError:
        rows = []
        complaint_available = False
    for row in rows:
        values = dict(row)
        public_id = _public_facility_id(values.get("external_facility_number"))
        if public_id is None:
            continue
        canonical_by_id[public_id].append(
            facility_projection_candidate_from_values(
                values,
                source_kind=FacilitySourceKind.COMPLAINT_LINKED_FACILITY,
                source_row_identity=str(values.get("facility_id") or "sqlite-facility-row"),
                snapshot_identity=(
                    "sqlite-complaint-observation:"
                    f"{str(values.get('projection_observed_at') or 'undated')}"
                ),
                observed_at=_optional_text(values.get("projection_observed_at")),
                canonical_internal_identity=_optional_text(values.get("facility_id")),
            )
        )

    reference_by_id: dict[str, list[FacilityProjectionCandidate]] = defaultdict(list)
    snapshot_identity = _reference_snapshot_identity(reference_records)
    for record in reference_records:
        public_id = _public_facility_id(
            record.get("facility_number")
            or record.get("Facility Number")
            or record.get("FAC_NBR")
        )
        if public_id is None:
            continue
        reference_by_id[public_id].append(
            facility_projection_candidate_from_values(
                record,
                source_kind=FacilitySourceKind.PROGRAM_REFERENCE,
                source_row_identity=f"facility-reference:{_mapping_fingerprint(record)[:24]}",
                snapshot_identity=snapshot_identity,
                observed_at=_optional_text(
                    record.get("source_accessed_at") or record.get("snapshot_date")
                ),
            )
        )

    public_ids = sorted(set(canonical_by_id) | set(reference_by_id))
    return MappingProxyType(
        {
            public_id: project_facility_identity(
                public_id,
                (*reference_by_id[public_id], *canonical_by_id[public_id]),
                availability=FacilityProjectionSourceAvailability(
                    program_reference=bool(reference_records),
                    complaint_linked_facility=complaint_available,
                ),
            )
            for public_id in public_ids
        }
    )


def projected_facility_export_text(
    projection: FacilityIdentityProjection,
    field: FacilityProjectionField,
) -> str:
    return projected_display_text(projection, field)


def projected_facility_export_context(
    projection: FacilityIdentityProjection,
    fields: Sequence[FacilityProjectionField] = FACILITY_EXPORT_IDENTITY_FIELDS,
) -> str:
    contexts = tuple(dict.fromkeys(projected_context_text(projection, field) for field in fields))
    return "; ".join(contexts)


def projected_facility_export_conflicts(
    projection: FacilityIdentityProjection,
    fields: Sequence[FacilityProjectionField] = FACILITY_EXPORT_IDENTITY_FIELDS,
) -> str:
    return projected_conflict_text(projection, tuple(fields))


def _reference_snapshot_identity(records: Sequence[Mapping[str, Any]]) -> str:
    fingerprints = sorted(_mapping_fingerprint(record) for record in records)
    digest = hashlib.sha256("\n".join(fingerprints).encode("utf-8")).hexdigest()
    return f"facility-reference:{digest[:24]}"


def _mapping_fingerprint(values: Mapping[str, Any]) -> str:
    serialized = json.dumps(
        {str(key): values[key] for key in sorted(values, key=str)},
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _public_facility_id(value: object) -> str | None:
    text = _optional_text(value)
    return text if text is not None and text.isdigit() else None


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
