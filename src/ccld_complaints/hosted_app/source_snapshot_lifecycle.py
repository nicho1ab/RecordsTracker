from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal, cast

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    select,
    update,
)
from sqlalchemy.engine import Connection

from ccld_complaints.connectors.arcgis_ccl_facilities.contract import (
    ARCGIS_DATASET_TITLE,
    ARCGIS_ITEM_ID,
    ARCGIS_ITEM_URL,
    ARCGIS_LAYER_ID,
    ARCGIS_LAYER_NAME,
    ARCGIS_LAYER_URL,
    ARCGIS_LICENSE_DESIGNATION,
    ARCGIS_PUBLISHER,
    ARCGIS_QUERY_URL,
    ARCGIS_RAW_FIELDS,
    ARCGIS_SERVICE_NAME,
    ARCGIS_SERVICE_URL,
    ARCGIS_SUPPLEMENT_SOURCE_FAMILY_ID,
    CATALOG_URL,
    LICENSES_URL,
    LIVE_QUERY_OBSERVATION_KIND,
    LIVE_QUERY_SCOPE,
    SNAPSHOT_CONTRACT_VERSION,
    live_snapshot_id,
    normalize_arcgis_source_row,
    provisional_attribution,
    validate_arcgis_schema_fields,
)
from ccld_complaints.connectors.arcgis_ccl_facilities.contract import (
    ARCGIS_NORMALIZED_FIELD_SOURCES as _ARCGIS_NORMALIZED_FIELD_SOURCES,
)
from ccld_complaints.statewide_facility_source_evaluation import canonical_fingerprint

OFFLINE_FIXTURE_SCOPE = "repository_synthetic_fixture"
OFFLINE_FIXTURE_NOTICE = "SYNTHETIC TEST DATA - NO REAL FACILITIES"
ISOLATED_NONPRODUCTION_SCOPE = "isolated_nonproduction"
ARCGIS_NORMALIZED_FIELD_SOURCES = _ARCGIS_NORMALIZED_FIELD_SOURCES

_MANIFEST_FIELDS = frozenset(
    {
        "contract_version",
        "fixture_kind",
        "source_family_id",
        "observation_kind",
        "recorded_at",
        "raw_payload_ref",
        "raw_payload_sha256",
        "schema_fields",
    }
)
_LIVE_MANIFEST_FIELDS = frozenset(
    {
        "contract_version",
        "evidence_kind",
        "source_family_id",
        "observation_kind",
        "snapshot_id",
        "recorded_at",
        "accessed_date",
        "catalog_identity",
        "source_identity",
        "provisional_attribution",
        "raw_payload_ref",
        "raw_payload_sha256",
        "normalized_content_sha256",
        "schema_fingerprint",
        "domain_fingerprint",
        "schema_fields",
        "retrieval_artifacts",
        "raw_response_set_sha256",
        "id_evidence",
        "page_evidence",
        "validation",
    }
)
_OBSERVATION_KINDS = ("synthetic_query", "synthetic_export")
LifecycleState = Literal["candidate", "validated", "rejected", "accepted"]

source_snapshot_metadata = MetaData()

source_snapshots = Table(
    "hosted_source_snapshots",
    source_snapshot_metadata,
    Column("snapshot_id", String(80), primary_key=True),
    Column("source_family_id", String(96), nullable=False),
    Column("fixture_scope", String(40), nullable=False),
    Column("observation_kind", String(32), nullable=False),
    Column("lifecycle_state", String(16), nullable=False),
    Column("manifest_ref", Text, nullable=False),
    Column("manifest_sha256", String(64), nullable=False),
    Column("raw_payload_ref", Text, nullable=False),
    Column("raw_payload_sha256", String(64), nullable=False),
    Column("normalized_content_sha256", String(64), nullable=False),
    Column("schema_fingerprint", String(64), nullable=False),
    Column("domain_fingerprint", String(64), nullable=False),
    Column("row_count", Integer, nullable=False),
    Column("stored_row_count", Integer, nullable=False),
    Column("duplicate_object_id_count", Integer, nullable=False),
    Column("duplicate_facility_number_count", Integer, nullable=False),
    Column("omitted_field_count", Integer, nullable=False),
    Column("invalid_field_count", Integer, nullable=False),
    Column("warning_count", Integer, nullable=False),
    Column("rejection_reason_count", Integer, nullable=False),
    Column("validation_report", JSON(none_as_null=True), nullable=False),
    Column("recorded_at", String(40), nullable=False),
    Column("validated_at", String(40), nullable=True),
    Column("rejected_at", String(40), nullable=True),
    Column("accepted_at", String(40), nullable=True),
    CheckConstraint(
        "fixture_scope IN ('repository_synthetic_fixture', 'governed_live_query')",
        name="ck_hosted_source_snapshots_fixture_scope",
    ),
    CheckConstraint(
        "observation_kind IN ('synthetic_query', 'synthetic_export', 'live_query')",
        name="ck_hosted_source_snapshots_observation_kind",
    ),
    CheckConstraint(
        "lifecycle_state IN ('candidate', 'validated', 'rejected', 'accepted')",
        name="ck_hosted_source_snapshots_lifecycle_state",
    ),
    CheckConstraint(
        "row_count >= 0 AND stored_row_count >= 0",
        name="ck_hosted_source_snapshots_nonnegative_rows",
    ),
    UniqueConstraint(
        "source_family_id",
        "manifest_sha256",
        "raw_payload_sha256",
        name="uq_hosted_source_snapshots_fixture_identity",
    ),
)
Index(
    "ix_hosted_source_snapshots_family_state",
    source_snapshots.c.source_family_id,
    source_snapshots.c.lifecycle_state,
    source_snapshots.c.recorded_at,
)

source_snapshot_rows = Table(
    "hosted_source_snapshot_rows",
    source_snapshot_metadata,
    Column(
        "snapshot_id",
        String(80),
        ForeignKey("hosted_source_snapshots.snapshot_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("source_object_id", BigInteger, primary_key=True),
    Column("facility_number", String(32), nullable=True),
    Column("raw_record", JSON(none_as_null=True), nullable=False),
    Column("normalized_record", JSON(none_as_null=True), nullable=False),
    Column("row_fingerprint", String(64), nullable=False),
    UniqueConstraint(
        "snapshot_id",
        "row_fingerprint",
        "source_object_id",
        name="uq_hosted_source_snapshot_rows_fingerprint_identity",
    ),
)
Index(
    "ix_hosted_source_snapshot_rows_facility_number",
    source_snapshot_rows.c.facility_number,
)

source_snapshot_disappearances = Table(
    "hosted_source_snapshot_disappearances",
    source_snapshot_metadata,
    Column(
        "snapshot_id",
        String(80),
        ForeignKey("hosted_source_snapshots.snapshot_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "prior_snapshot_id",
        String(80),
        ForeignKey("hosted_source_snapshots.snapshot_id"),
        nullable=False,
    ),
    Column("source_object_id", BigInteger, primary_key=True),
    Column("facility_number", String(32), nullable=True),
    Column("prior_row_fingerprint", String(64), nullable=False),
    Column("review_state", String(24), nullable=False),
    Column("closure_inferred", Boolean, nullable=False),
    CheckConstraint(
        "review_state = 'pending_reconciliation'",
        name="ck_hosted_source_snapshot_disappearances_review_state",
    ),
    CheckConstraint(
        "closure_inferred = false",
        name="ck_hosted_source_snapshot_disappearances_no_closure_inference",
    ),
)
Index(
    "ix_hosted_source_snapshot_disappearances_facility_number",
    source_snapshot_disappearances.c.facility_number,
)

source_snapshot_pointers = Table(
    "hosted_source_snapshot_pointers",
    source_snapshot_metadata,
    Column("source_family_id", String(96), primary_key=True),
    Column(
        "active_snapshot_id",
        String(80),
        ForeignKey("hosted_source_snapshots.snapshot_id"),
        nullable=False,
        unique=True,
    ),
    Column(
        "prior_accepted_snapshot_id",
        String(80),
        ForeignKey("hosted_source_snapshots.snapshot_id"),
        nullable=True,
    ),
    Column("updated_at", String(40), nullable=False),
    CheckConstraint(
        "prior_accepted_snapshot_id IS NULL "
        "OR prior_accepted_snapshot_id <> active_snapshot_id",
        name="ck_hosted_source_snapshot_pointers_distinct_snapshots",
    ),
)


class OfflineSnapshotLifecycleError(ValueError):
    """Raised when the synthetic-only snapshot lifecycle contract is violated."""


@dataclass(frozen=True)
class SnapshotInspection:
    snapshot_id: str
    source_family_id: str
    storage_scope: str
    observation_kind: str
    manifest_ref: str
    manifest_sha256: str
    raw_payload_ref: str
    raw_payload_sha256: str
    normalized_content_sha256: str
    schema_fingerprint: str
    domain_fingerprint: str
    recorded_at: str
    rows: tuple[Mapping[str, Any], ...]
    disappearances: tuple[Mapping[str, Any], ...]
    validation_report: Mapping[str, Any]

    @property
    def rejection_reasons(self) -> tuple[str, ...]:
        values = self.validation_report.get("rejection_reasons", [])
        return tuple(str(value) for value in cast(Sequence[object], values))


@dataclass(frozen=True)
class SnapshotPointer:
    source_family_id: str
    active_snapshot_id: str
    prior_accepted_snapshot_id: str | None


def inspect_arcgis_fixture_package(
    manifest_path: Path,
    *,
    prior_rows: Sequence[Mapping[str, Any]] = (),
    prior_snapshot_id: str | None = None,
    baseline_schema_fingerprint: str | None = None,
    baseline_domain_fingerprint: str | None = None,
) -> SnapshotInspection:
    return _inspect_arcgis_package(
        manifest_path,
        storage_scope=OFFLINE_FIXTURE_SCOPE,
        prior_rows=prior_rows,
        prior_snapshot_id=prior_snapshot_id,
        baseline_schema_fingerprint=baseline_schema_fingerprint,
        baseline_domain_fingerprint=baseline_domain_fingerprint,
    )


def inspect_arcgis_live_query_package(
    manifest_path: Path,
    *,
    execution_scope: str,
    prior_rows: Sequence[Mapping[str, Any]] = (),
    prior_snapshot_id: str | None = None,
    baseline_schema_fingerprint: str | None = None,
    baseline_domain_fingerprint: str | None = None,
) -> SnapshotInspection:
    _require_isolated_nonproduction(execution_scope)
    return _inspect_arcgis_package(
        manifest_path,
        storage_scope=LIVE_QUERY_SCOPE,
        prior_rows=prior_rows,
        prior_snapshot_id=prior_snapshot_id,
        baseline_schema_fingerprint=baseline_schema_fingerprint,
        baseline_domain_fingerprint=baseline_domain_fingerprint,
    )


def _inspect_arcgis_package(
    manifest_path: Path,
    *,
    storage_scope: str,
    prior_rows: Sequence[Mapping[str, Any]],
    prior_snapshot_id: str | None,
    baseline_schema_fingerprint: str | None,
    baseline_domain_fingerprint: str | None,
) -> SnapshotInspection:
    manifest_bytes = manifest_path.read_bytes()
    manifest = _json_object(manifest_bytes, label="snapshot manifest")
    manifest_sha256 = _sha256(manifest_bytes)
    manifest_rejections = _validate_manifest(manifest, storage_scope=storage_scope)
    raw_ref = _required_text(manifest, "raw_payload_ref")
    raw_path = _resolve_fixture_reference(manifest_path, raw_ref)
    raw_bytes = raw_path.read_bytes()
    raw_sha256 = _sha256(raw_bytes)
    expected_raw_sha256 = _required_text(manifest, "raw_payload_sha256")
    if raw_sha256 != expected_raw_sha256:
        manifest_rejections.append("raw_payload_sha256 does not match the fixture bytes")

    raw_payload = _json_object(raw_bytes, label="snapshot raw payload")
    if storage_scope == OFFLINE_FIXTURE_SCOPE:
        if raw_payload.get("fixture_notice") != OFFLINE_FIXTURE_NOTICE:
            manifest_rejections.append("raw payload is not marked as fictional synthetic data")
    elif raw_payload.get("source_kind") != LIVE_QUERY_SCOPE:
        manifest_rejections.append("raw payload is not marked as a governed live query")
    raw_records = raw_payload.get("records")
    if not isinstance(raw_records, list):
        raise OfflineSnapshotLifecycleError("Fixture raw payload records must be a JSON array.")

    schema_fields = manifest.get("schema_fields")
    if not isinstance(schema_fields, list):
        schema_fields = []
    schema_fingerprint = canonical_fingerprint(schema_fields)
    domains = [
        {"name": field.get("name"), "domain": field.get("domain")}
        for field in schema_fields
        if isinstance(field, Mapping)
    ]
    domain_fingerprint = canonical_fingerprint(domains)
    schema_rejections = validate_arcgis_schema_fields(schema_fields)
    if baseline_schema_fingerprint and schema_fingerprint != baseline_schema_fingerprint:
        schema_rejections.append("schema fingerprint differs from the active accepted snapshot")
    if baseline_domain_fingerprint and domain_fingerprint != baseline_domain_fingerprint:
        schema_rejections.append("domain fingerprint differs from the active accepted snapshot")

    normalized_rows: list[dict[str, Any]] = []
    row_rejections: list[str] = []
    warnings: list[str] = []
    object_ids: Counter[int] = Counter()
    facility_numbers: Counter[str] = Counter()
    omitted_field_count = 0
    invalid_field_count = 0

    for row_index, raw_row in enumerate(raw_records, start=1):
        if not isinstance(raw_row, Mapping):
            row_rejections.append(f"row {row_index} is not a JSON object")
            continue
        raw_record = dict(raw_row)
        missing = sorted(set(ARCGIS_RAW_FIELDS) - set(raw_record))
        extra = sorted(set(raw_record) - set(ARCGIS_RAW_FIELDS))
        omitted_field_count += len(missing)
        if missing:
            row_rejections.append(f"row {row_index} omits fields: {', '.join(missing)}")
        if extra:
            row_rejections.append(f"row {row_index} adds fields: {', '.join(extra)}")

        normalized = normalize_arcgis_source_row(raw_record)
        invalid_fields = sorted(
            field_name
            for field_name, value in normalized.items()
            if isinstance(value, Mapping) and value.get("state") == "invalid"
        )
        invalid_field_count += len(invalid_fields)
        if invalid_fields:
            row_rejections.append(
                f"row {row_index} has invalid fields: {', '.join(invalid_fields)}"
            )

        object_id = _populated_int(normalized.get("object_id"))
        if object_id is None:
            row_rejections.append(f"row {row_index} has no valid ObjectId identity")
            continue
        object_ids[object_id] += 1
        facility_number = _populated_text(normalized.get("facility_number"))
        if facility_number is not None:
            facility_numbers[facility_number] += 1
        raw_type = normalized.get("raw_type_code")
        if isinstance(raw_type, Mapping) and raw_type.get("value") == 733:
            warnings.append(f"row {row_index} retains unresolved raw TYPE value 733")
        normalized_rows.append(
            {
                "source_object_id": object_id,
                "facility_number": facility_number,
                "raw_record": raw_record,
                "normalized_record": normalized,
                "row_fingerprint": canonical_fingerprint(normalized),
            }
        )

    duplicate_object_ids = sorted(value for value, count in object_ids.items() if count > 1)
    if duplicate_object_ids:
        row_rejections.append(
            "duplicate ObjectId identities: "
            + ", ".join(str(value) for value in duplicate_object_ids)
        )
        normalized_rows = []
    duplicate_facility_numbers = sorted(
        value for value, count in facility_numbers.items() if count > 1
    )
    for value in duplicate_facility_numbers:
        warnings.append(
            f"FAC_NBR {value} groups {facility_numbers[value]} distinct source rows; "
            "none is collapsed"
        )

    normalized_rows.sort(key=lambda row: cast(int, row["source_object_id"]))
    normalized_content_sha256 = canonical_fingerprint(
        [
            {
                "source_object_id": row["source_object_id"],
                "row_fingerprint": row["row_fingerprint"],
            }
            for row in normalized_rows
        ]
    )
    if storage_scope == LIVE_QUERY_SCOPE:
        if manifest.get("normalized_content_sha256") != normalized_content_sha256:
            manifest_rejections.append(
                "normalized_content_sha256 does not match the lifecycle normalization"
            )
        if manifest.get("schema_fingerprint") != schema_fingerprint:
            manifest_rejections.append("schema_fingerprint does not match schema_fields")
        if manifest.get("domain_fingerprint") != domain_fingerprint:
            manifest_rejections.append("domain_fingerprint does not match schema_fields")
    disappearances = _find_disappearances(
        normalized_rows,
        prior_rows=prior_rows,
        prior_snapshot_id=prior_snapshot_id,
    )
    if disappearances:
        warnings.append(
            f"{len(disappearances)} prior source row(s) disappeared; closure is not inferred"
        )

    rejection_reasons = _deduplicate_sorted(
        [*manifest_rejections, *schema_rejections, *row_rejections]
    )
    warnings = _deduplicate_sorted(warnings)
    report = {
        "row_count": len(raw_records),
        "stored_row_count": len(normalized_rows),
        "duplicate_object_id_count": sum(
            count - 1 for count in object_ids.values() if count > 1
        ),
        "duplicate_facility_number_count": sum(
            count - 1 for count in facility_numbers.values() if count > 1
        ),
        "omitted_field_count": omitted_field_count,
        "invalid_field_count": invalid_field_count,
        "disappearance_count": len(disappearances),
        "warnings": warnings,
        "rejection_reasons": rejection_reasons,
        "closure_inferred": False,
        "canonical_or_reviewer_fields_written": False,
    }
    if storage_scope == OFFLINE_FIXTURE_SCOPE:
        snapshot_id = "arcgis-fixture-" + canonical_fingerprint(
            {
                "source_family_id": ARCGIS_SUPPLEMENT_SOURCE_FAMILY_ID,
                "manifest_sha256": manifest_sha256,
                "raw_payload_sha256": raw_sha256,
            }
        )[:48]
    else:
        snapshot_id = _required_text(manifest, "snapshot_id")
    return SnapshotInspection(
        snapshot_id=snapshot_id,
        source_family_id=ARCGIS_SUPPLEMENT_SOURCE_FAMILY_ID,
        storage_scope=storage_scope,
        observation_kind=_required_text(manifest, "observation_kind"),
        manifest_ref=manifest_path.name,
        manifest_sha256=manifest_sha256,
        raw_payload_ref=raw_ref,
        raw_payload_sha256=raw_sha256,
        normalized_content_sha256=normalized_content_sha256,
        schema_fingerprint=schema_fingerprint,
        domain_fingerprint=domain_fingerprint,
        recorded_at=_required_text(manifest, "recorded_at"),
        rows=tuple(normalized_rows),
        disappearances=tuple(disappearances),
        validation_report=report,
    )


def stage_arcgis_fixture_snapshot(
    connection: Connection,
    manifest_path: Path,
) -> SnapshotInspection:
    return _stage_arcgis_snapshot(
        connection,
        manifest_path,
        storage_scope=OFFLINE_FIXTURE_SCOPE,
        execution_scope=None,
    )


def stage_arcgis_live_query_snapshot(
    connection: Connection,
    manifest_path: Path,
    *,
    execution_scope: str,
) -> SnapshotInspection:
    _require_isolated_nonproduction(execution_scope)
    return _stage_arcgis_snapshot(
        connection,
        manifest_path,
        storage_scope=LIVE_QUERY_SCOPE,
        execution_scope=execution_scope,
    )


def _stage_arcgis_snapshot(
    connection: Connection,
    manifest_path: Path,
    *,
    storage_scope: str,
    execution_scope: str | None,
) -> SnapshotInspection:
    active = _active_snapshot_record(connection, ARCGIS_SUPPLEMENT_SOURCE_FAMILY_ID)
    prior_rows: Sequence[Mapping[str, Any]] = ()
    prior_snapshot_id: str | None = None
    baseline_schema: str | None = None
    baseline_domain: str | None = None
    if active is not None:
        prior_snapshot_id = str(active["snapshot_id"])
        baseline_schema = str(active["schema_fingerprint"])
        baseline_domain = str(active["domain_fingerprint"])
        prior_rows = tuple(
            dict(row)
            for row in connection.execute(
                select(source_snapshot_rows).where(
                    source_snapshot_rows.c.snapshot_id == prior_snapshot_id
                )
            ).mappings()
        )

    if storage_scope == OFFLINE_FIXTURE_SCOPE:
        inspection = inspect_arcgis_fixture_package(
            manifest_path,
            prior_rows=prior_rows,
            prior_snapshot_id=prior_snapshot_id,
            baseline_schema_fingerprint=baseline_schema,
            baseline_domain_fingerprint=baseline_domain,
        )
    else:
        inspection = inspect_arcgis_live_query_package(
            manifest_path,
            execution_scope=execution_scope or "",
            prior_rows=prior_rows,
            prior_snapshot_id=prior_snapshot_id,
            baseline_schema_fingerprint=baseline_schema,
            baseline_domain_fingerprint=baseline_domain,
        )
    existing = connection.execute(
        select(source_snapshots).where(source_snapshots.c.snapshot_id == inspection.snapshot_id)
    ).mappings().one_or_none()
    if existing is not None:
        existing_snapshot = dict(existing)
        _assert_same_immutable_snapshot(existing_snapshot, inspection)
        return _stored_inspection(connection, existing_snapshot)

    report = inspection.validation_report
    connection.execute(
        source_snapshots.insert().values(
            snapshot_id=inspection.snapshot_id,
            source_family_id=inspection.source_family_id,
            fixture_scope=inspection.storage_scope,
            observation_kind=inspection.observation_kind,
            lifecycle_state="candidate",
            manifest_ref=inspection.manifest_ref,
            manifest_sha256=inspection.manifest_sha256,
            raw_payload_ref=inspection.raw_payload_ref,
            raw_payload_sha256=inspection.raw_payload_sha256,
            normalized_content_sha256=inspection.normalized_content_sha256,
            schema_fingerprint=inspection.schema_fingerprint,
            domain_fingerprint=inspection.domain_fingerprint,
            row_count=int(report["row_count"]),
            stored_row_count=int(report["stored_row_count"]),
            duplicate_object_id_count=int(report["duplicate_object_id_count"]),
            duplicate_facility_number_count=int(report["duplicate_facility_number_count"]),
            omitted_field_count=int(report["omitted_field_count"]),
            invalid_field_count=int(report["invalid_field_count"]),
            warning_count=len(cast(Sequence[object], report["warnings"])),
            rejection_reason_count=len(cast(Sequence[object], report["rejection_reasons"])),
            validation_report=dict(report),
            recorded_at=inspection.recorded_at,
        )
    )
    if inspection.rows:
        connection.execute(
            source_snapshot_rows.insert(),
            [dict(row, snapshot_id=inspection.snapshot_id) for row in inspection.rows],
        )
    if inspection.disappearances:
        connection.execute(
            source_snapshot_disappearances.insert(),
            [dict(row, snapshot_id=inspection.snapshot_id) for row in inspection.disappearances],
        )
    return inspection


def validate_arcgis_fixture_snapshot(
    connection: Connection,
    snapshot_id: str,
    *,
    validated_at: str,
) -> LifecycleState:
    return _validate_arcgis_snapshot(
        connection,
        snapshot_id,
        expected_scope=OFFLINE_FIXTURE_SCOPE,
        validated_at=validated_at,
    )


def validate_arcgis_live_query_snapshot(
    connection: Connection,
    snapshot_id: str,
    *,
    validated_at: str,
    execution_scope: str,
) -> LifecycleState:
    _require_isolated_nonproduction(execution_scope)
    return _validate_arcgis_snapshot(
        connection,
        snapshot_id,
        expected_scope=LIVE_QUERY_SCOPE,
        validated_at=validated_at,
    )


def _validate_arcgis_snapshot(
    connection: Connection,
    snapshot_id: str,
    *,
    expected_scope: str,
    validated_at: str,
) -> LifecycleState:
    snapshot = _snapshot_record(connection, snapshot_id)
    _assert_snapshot_scope(snapshot, expected_scope)
    state = str(snapshot["lifecycle_state"])
    if state != "candidate":
        raise OfflineSnapshotLifecycleError(
            f"Only a candidate snapshot may be validated; {snapshot_id} is {state}."
        )
    rejected = int(snapshot["rejection_reason_count"]) > 0
    next_state: LifecycleState = "rejected" if rejected else "validated"
    values: dict[str, Any] = {"lifecycle_state": next_state}
    if rejected:
        values["rejected_at"] = validated_at
    else:
        values["validated_at"] = validated_at
    connection.execute(
        update(source_snapshots)
        .where(source_snapshots.c.snapshot_id == snapshot_id)
        .values(**values)
    )
    return next_state


def accept_arcgis_fixture_snapshot(
    connection: Connection,
    snapshot_id: str,
    *,
    accepted_at: str,
) -> None:
    _accept_arcgis_snapshot(
        connection,
        snapshot_id,
        expected_scope=OFFLINE_FIXTURE_SCOPE,
        accepted_at=accepted_at,
    )


def accept_arcgis_live_query_snapshot(
    connection: Connection,
    snapshot_id: str,
    *,
    accepted_at: str,
    execution_scope: str,
) -> None:
    _require_isolated_nonproduction(execution_scope)
    _accept_arcgis_snapshot(
        connection,
        snapshot_id,
        expected_scope=LIVE_QUERY_SCOPE,
        accepted_at=accepted_at,
    )


def _accept_arcgis_snapshot(
    connection: Connection,
    snapshot_id: str,
    *,
    expected_scope: str,
    accepted_at: str,
) -> None:
    snapshot = _snapshot_record(connection, snapshot_id)
    _assert_snapshot_scope(snapshot, expected_scope)
    state = str(snapshot["lifecycle_state"])
    if state == "accepted":
        return
    if state != "validated":
        raise OfflineSnapshotLifecycleError(
            f"Only a validated snapshot may be accepted; {snapshot_id} is {state}."
        )
    connection.execute(
        update(source_snapshots)
        .where(source_snapshots.c.snapshot_id == snapshot_id)
        .values(lifecycle_state="accepted", accepted_at=accepted_at)
    )


def promote_arcgis_fixture_snapshot(
    connection: Connection,
    snapshot_id: str,
    *,
    promoted_at: str,
) -> SnapshotPointer:
    return _promote_arcgis_snapshot(
        connection,
        snapshot_id,
        expected_scope=OFFLINE_FIXTURE_SCOPE,
        promoted_at=promoted_at,
    )


def promote_arcgis_live_query_snapshot(
    connection: Connection,
    snapshot_id: str,
    *,
    promoted_at: str,
    execution_scope: str,
) -> SnapshotPointer:
    _require_isolated_nonproduction(execution_scope)
    return _promote_arcgis_snapshot(
        connection,
        snapshot_id,
        expected_scope=LIVE_QUERY_SCOPE,
        promoted_at=promoted_at,
    )


def _promote_arcgis_snapshot(
    connection: Connection,
    snapshot_id: str,
    *,
    expected_scope: str,
    promoted_at: str,
) -> SnapshotPointer:
    snapshot = _snapshot_record(connection, snapshot_id)
    _assert_accepted_arcgis_snapshot(snapshot, expected_scope=expected_scope)
    pointer = _pointer_record(connection, ARCGIS_SUPPLEMENT_SOURCE_FAMILY_ID)
    if pointer is None:
        connection.execute(
            source_snapshot_pointers.insert().values(
                source_family_id=ARCGIS_SUPPLEMENT_SOURCE_FAMILY_ID,
                active_snapshot_id=snapshot_id,
                prior_accepted_snapshot_id=None,
                updated_at=promoted_at,
            )
        )
        return SnapshotPointer(ARCGIS_SUPPLEMENT_SOURCE_FAMILY_ID, snapshot_id, None)
    active_snapshot_id = str(pointer["active_snapshot_id"])
    prior_snapshot_id = _optional_text(pointer.get("prior_accepted_snapshot_id"))
    if active_snapshot_id == snapshot_id:
        return SnapshotPointer(
            ARCGIS_SUPPLEMENT_SOURCE_FAMILY_ID,
            active_snapshot_id,
            prior_snapshot_id,
        )
    connection.execute(
        update(source_snapshot_pointers)
        .where(
            source_snapshot_pointers.c.source_family_id
            == ARCGIS_SUPPLEMENT_SOURCE_FAMILY_ID
        )
        .values(
            active_snapshot_id=snapshot_id,
            prior_accepted_snapshot_id=active_snapshot_id,
            updated_at=promoted_at,
        )
    )
    return SnapshotPointer(
        ARCGIS_SUPPLEMENT_SOURCE_FAMILY_ID,
        snapshot_id,
        active_snapshot_id,
    )


def rollback_arcgis_fixture_snapshot(
    connection: Connection,
    *,
    expected_active_snapshot_id: str,
    rolled_back_at: str,
) -> SnapshotPointer:
    return _rollback_arcgis_snapshot(
        connection,
        expected_active_snapshot_id=expected_active_snapshot_id,
        expected_active_scope=OFFLINE_FIXTURE_SCOPE,
        expected_prior_scope=OFFLINE_FIXTURE_SCOPE,
        rolled_back_at=rolled_back_at,
    )


def rollback_arcgis_live_query_snapshot(
    connection: Connection,
    *,
    expected_active_snapshot_id: str,
    rolled_back_at: str,
    execution_scope: str,
) -> SnapshotPointer:
    _require_isolated_nonproduction(execution_scope)
    return _rollback_arcgis_snapshot(
        connection,
        expected_active_snapshot_id=expected_active_snapshot_id,
        expected_active_scope=LIVE_QUERY_SCOPE,
        expected_prior_scope=None,
        rolled_back_at=rolled_back_at,
    )


def _rollback_arcgis_snapshot(
    connection: Connection,
    *,
    expected_active_snapshot_id: str,
    expected_active_scope: str,
    expected_prior_scope: str | None,
    rolled_back_at: str,
) -> SnapshotPointer:
    pointer = _pointer_record(connection, ARCGIS_SUPPLEMENT_SOURCE_FAMILY_ID)
    if pointer is None:
        raise OfflineSnapshotLifecycleError("No active ArcGIS fixture snapshot can be rolled back.")
    active = str(pointer["active_snapshot_id"])
    prior = _optional_text(pointer.get("prior_accepted_snapshot_id"))
    if active != expected_active_snapshot_id:
        if prior == expected_active_snapshot_id:
            _assert_accepted_arcgis_snapshot(
                _snapshot_record(connection, expected_active_snapshot_id),
                expected_scope=expected_active_scope,
            )
            return SnapshotPointer(ARCGIS_SUPPLEMENT_SOURCE_FAMILY_ID, active, prior)
        raise OfflineSnapshotLifecycleError(
            "The active ArcGIS fixture snapshot changed before rollback."
        )
    if prior is None:
        raise OfflineSnapshotLifecycleError("No prior accepted ArcGIS snapshot exists.")
    active_snapshot = _snapshot_record(connection, active)
    _assert_accepted_arcgis_snapshot(
        active_snapshot,
        expected_scope=expected_active_scope,
    )
    _assert_accepted_arcgis_snapshot(
        _snapshot_record(connection, prior),
        expected_scope=expected_prior_scope,
    )
    connection.execute(
        update(source_snapshot_pointers)
        .where(
            source_snapshot_pointers.c.source_family_id
            == ARCGIS_SUPPLEMENT_SOURCE_FAMILY_ID
        )
        .values(
            active_snapshot_id=prior,
            prior_accepted_snapshot_id=active,
            updated_at=rolled_back_at,
        )
    )
    return SnapshotPointer(ARCGIS_SUPPLEMENT_SOURCE_FAMILY_ID, prior, active)


def _validate_manifest(
    manifest: Mapping[str, Any],
    *,
    storage_scope: str,
) -> list[str]:
    if storage_scope == LIVE_QUERY_SCOPE:
        return _validate_live_manifest(manifest)
    rejections: list[str] = []
    missing = sorted(_MANIFEST_FIELDS - set(manifest))
    extra = sorted(set(manifest) - _MANIFEST_FIELDS)
    if missing:
        rejections.append("manifest omits fields: " + ", ".join(missing))
    if extra:
        rejections.append("manifest adds unauthorized fields: " + ", ".join(extra))
    if manifest.get("contract_version") != SNAPSHOT_CONTRACT_VERSION:
        rejections.append("manifest contract_version is not 1.0.0")
    if manifest.get("fixture_kind") != OFFLINE_FIXTURE_SCOPE:
        rejections.append("manifest is not a repository synthetic fixture")
    if manifest.get("source_family_id") != ARCGIS_SUPPLEMENT_SOURCE_FAMILY_ID:
        rejections.append("manifest source family is not the inactive ArcGIS supplement")
    if manifest.get("observation_kind") not in _OBSERVATION_KINDS:
        rejections.append("manifest observation_kind is not an allowed synthetic observation")
    return rejections


def _validate_live_manifest(manifest: Mapping[str, Any]) -> list[str]:
    rejections: list[str] = []
    missing = sorted(_LIVE_MANIFEST_FIELDS - set(manifest))
    extra = sorted(set(manifest) - _LIVE_MANIFEST_FIELDS)
    if missing:
        rejections.append("manifest omits fields: " + ", ".join(missing))
    if extra:
        rejections.append("manifest adds fields: " + ", ".join(extra))
    if manifest.get("contract_version") != SNAPSHOT_CONTRACT_VERSION:
        rejections.append("manifest contract_version is not 1.0.0")
    if manifest.get("evidence_kind") != LIVE_QUERY_SCOPE:
        rejections.append("manifest is not a governed live query package")
    if manifest.get("source_family_id") != ARCGIS_SUPPLEMENT_SOURCE_FAMILY_ID:
        rejections.append("manifest source family is not the inactive ArcGIS supplement")
    if manifest.get("observation_kind") != LIVE_QUERY_OBSERVATION_KIND:
        rejections.append("manifest observation_kind is not live_query")

    accessed_date = manifest.get("accessed_date")
    recorded_at = manifest.get("recorded_at")
    snapshot_id = manifest.get("snapshot_id")
    if not isinstance(accessed_date, str) or not accessed_date:
        rejections.append("manifest accessed_date is not a nonblank string")
    if not isinstance(snapshot_id, str) or not snapshot_id:
        rejections.append("manifest snapshot_id is not a nonblank string")
    if not isinstance(recorded_at, str) or not recorded_at:
        rejections.append("manifest recorded_at is not a nonblank string")
    if (
        isinstance(accessed_date, str)
        and isinstance(recorded_at, str)
        and accessed_date != recorded_at[:10]
    ):
        rejections.append("manifest accessed_date does not match recorded_at")
    if isinstance(accessed_date, str) and isinstance(snapshot_id, str):
        if manifest.get("provisional_attribution") != provisional_attribution(
            snapshot_id, accessed_date
        ):
            rejections.append("manifest provisional attribution differs from approval")

    catalog_identity = manifest.get("catalog_identity")
    expected_catalog_identity = {
        "catalog_url": CATALOG_URL,
        "licenses_url": LICENSES_URL,
        "publisher": ARCGIS_PUBLISHER,
        "dataset_title": ARCGIS_DATASET_TITLE,
        "license_designation": ARCGIS_LICENSE_DESIGNATION,
        "license_version": None,
    }
    if catalog_identity != expected_catalog_identity:
        rejections.append("manifest catalog identity differs from the approved source")

    source_identity = manifest.get("source_identity")
    expected_source_identity = {
        "item_id": ARCGIS_ITEM_ID,
        "service_name": ARCGIS_SERVICE_NAME,
        "layer_id": ARCGIS_LAYER_ID,
        "layer_name": ARCGIS_LAYER_NAME,
        "item_url": ARCGIS_ITEM_URL,
        "service_url": ARCGIS_SERVICE_URL,
        "layer_url": ARCGIS_LAYER_URL,
        "query_url": ARCGIS_QUERY_URL,
    }
    if source_identity != expected_source_identity:
        rejections.append("manifest source identity differs from the approved ArcGIS layer")

    validation = manifest.get("validation")
    if not isinstance(validation, Mapping) or validation.get("status") != "validated":
        rejections.append("manifest retrieval validation is not complete")
    id_evidence = manifest.get("id_evidence")
    object_id_set_sha256 = (
        id_evidence.get("object_id_set_sha256") if isinstance(id_evidence, Mapping) else None
    )
    if not isinstance(object_id_set_sha256, str):
        rejections.append("manifest ID evidence omits object_id_set_sha256")

    fingerprint_fields = (
        "raw_payload_sha256",
        "normalized_content_sha256",
        "schema_fingerprint",
        "domain_fingerprint",
        "raw_response_set_sha256",
    )
    fingerprint_values = {field: manifest.get(field) for field in fingerprint_fields}
    for field, value in fingerprint_values.items():
        if not isinstance(value, str) or len(value) != 64:
            rejections.append(f"manifest {field} is not a SHA-256 value")
    if (
        isinstance(snapshot_id, str)
        and isinstance(recorded_at, str)
        and isinstance(object_id_set_sha256, str)
        and all(isinstance(value, str) for value in fingerprint_values.values())
    ):
        expected_snapshot_id = live_snapshot_id(
            recorded_at=recorded_at,
            raw_payload_sha256=str(fingerprint_values["raw_payload_sha256"]),
            normalized_content_sha256=str(
                fingerprint_values["normalized_content_sha256"]
            ),
            schema_fingerprint=str(fingerprint_values["schema_fingerprint"]),
            domain_fingerprint=str(fingerprint_values["domain_fingerprint"]),
            object_id_set_sha256=object_id_set_sha256,
            raw_response_set_sha256=str(fingerprint_values["raw_response_set_sha256"]),
        )
        if snapshot_id != expected_snapshot_id:
            rejections.append("manifest snapshot_id does not match governed fingerprints")
    return rejections


def _find_disappearances(
    rows: Sequence[Mapping[str, Any]],
    *,
    prior_rows: Sequence[Mapping[str, Any]],
    prior_snapshot_id: str | None,
) -> list[dict[str, Any]]:
    if prior_snapshot_id is None:
        return []
    current_ids = {int(row["source_object_id"]) for row in rows}
    disappearances = []
    for prior in sorted(prior_rows, key=lambda row: int(row["source_object_id"])):
        object_id = int(prior["source_object_id"])
        if object_id in current_ids:
            continue
        disappearances.append(
            {
                "prior_snapshot_id": prior_snapshot_id,
                "source_object_id": object_id,
                "facility_number": _optional_text(prior.get("facility_number")),
                "prior_row_fingerprint": str(prior["row_fingerprint"]),
                "review_state": "pending_reconciliation",
                "closure_inferred": False,
            }
        )
    return disappearances


def _active_snapshot_record(
    connection: Connection,
    source_family_id: str,
) -> Mapping[str, Any] | None:
    row = connection.execute(
        select(source_snapshots)
        .join(
            source_snapshot_pointers,
            source_snapshot_pointers.c.active_snapshot_id == source_snapshots.c.snapshot_id,
        )
        .where(source_snapshot_pointers.c.source_family_id == source_family_id)
    ).mappings().one_or_none()
    return dict(row) if row is not None else None


def _snapshot_record(connection: Connection, snapshot_id: str) -> Mapping[str, Any]:
    snapshot = connection.execute(
        select(source_snapshots).where(source_snapshots.c.snapshot_id == snapshot_id)
    ).mappings().one_or_none()
    if snapshot is None:
        raise OfflineSnapshotLifecycleError(f"Unknown snapshot: {snapshot_id}")
    return dict(snapshot)


def _pointer_record(
    connection: Connection,
    source_family_id: str,
) -> Mapping[str, Any] | None:
    row = connection.execute(
        select(source_snapshot_pointers).where(
            source_snapshot_pointers.c.source_family_id == source_family_id
        )
    ).mappings().one_or_none()
    return dict(row) if row is not None else None


def _stored_inspection(
    connection: Connection,
    snapshot: Mapping[str, Any],
) -> SnapshotInspection:
    snapshot_id = str(snapshot["snapshot_id"])
    rows = []
    for row in connection.execute(
        select(source_snapshot_rows).where(source_snapshot_rows.c.snapshot_id == snapshot_id)
    ).mappings():
        stored = dict(row)
        stored.pop("snapshot_id")
        rows.append(stored)
    disappearances = []
    for row in connection.execute(
        select(source_snapshot_disappearances).where(
            source_snapshot_disappearances.c.snapshot_id == snapshot_id
        )
    ).mappings():
        stored = dict(row)
        stored.pop("snapshot_id")
        disappearances.append(stored)
    return SnapshotInspection(
        snapshot_id=snapshot_id,
        source_family_id=str(snapshot["source_family_id"]),
        storage_scope=str(snapshot["fixture_scope"]),
        observation_kind=str(snapshot["observation_kind"]),
        manifest_ref=str(snapshot["manifest_ref"]),
        manifest_sha256=str(snapshot["manifest_sha256"]),
        raw_payload_ref=str(snapshot["raw_payload_ref"]),
        raw_payload_sha256=str(snapshot["raw_payload_sha256"]),
        normalized_content_sha256=str(snapshot["normalized_content_sha256"]),
        schema_fingerprint=str(snapshot["schema_fingerprint"]),
        domain_fingerprint=str(snapshot["domain_fingerprint"]),
        recorded_at=str(snapshot["recorded_at"]),
        rows=tuple(rows),
        disappearances=tuple(disappearances),
        validation_report=dict(cast(Mapping[str, Any], snapshot["validation_report"])),
    )


def _assert_accepted_arcgis_snapshot(
    snapshot: Mapping[str, Any],
    *,
    expected_scope: str | None,
) -> None:
    if snapshot["source_family_id"] != ARCGIS_SUPPLEMENT_SOURCE_FAMILY_ID:
        raise OfflineSnapshotLifecycleError("Snapshot belongs to a different source family.")
    if expected_scope is not None:
        _assert_snapshot_scope(snapshot, expected_scope)
    elif snapshot["fixture_scope"] not in (OFFLINE_FIXTURE_SCOPE, LIVE_QUERY_SCOPE):
        raise OfflineSnapshotLifecycleError("Snapshot has an unsupported source storage scope.")
    if snapshot["lifecycle_state"] != "accepted":
        raise OfflineSnapshotLifecycleError("Only an accepted snapshot may be promoted.")


def _assert_snapshot_scope(snapshot: Mapping[str, Any], expected_scope: str) -> None:
    if snapshot["fixture_scope"] != expected_scope:
        raise OfflineSnapshotLifecycleError(
            f"Snapshot scope is not the required {expected_scope} boundary."
        )


def _require_isolated_nonproduction(execution_scope: str) -> None:
    if execution_scope != ISOLATED_NONPRODUCTION_SCOPE:
        raise OfflineSnapshotLifecycleError(
            "Live ArcGIS lifecycle operations require the explicit isolated_nonproduction "
            "execution scope."
        )


def _assert_same_immutable_snapshot(
    existing: Mapping[str, Any],
    inspection: SnapshotInspection,
) -> None:
    expected = {
        "source_family_id": inspection.source_family_id,
        "fixture_scope": inspection.storage_scope,
        "manifest_sha256": inspection.manifest_sha256,
        "raw_payload_sha256": inspection.raw_payload_sha256,
        "normalized_content_sha256": inspection.normalized_content_sha256,
        "schema_fingerprint": inspection.schema_fingerprint,
        "domain_fingerprint": inspection.domain_fingerprint,
    }
    for field, value in expected.items():
        if existing[field] != value:
            raise OfflineSnapshotLifecycleError(
                f"Immutable snapshot identity collision for {inspection.snapshot_id}."
            )


def _resolve_fixture_reference(manifest_path: Path, reference: str) -> Path:
    posix_reference = PurePosixPath(reference)
    if posix_reference.is_absolute() or ".." in posix_reference.parts or ":" in reference:
        raise OfflineSnapshotLifecycleError("Fixture raw reference must be a safe relative path.")
    target = manifest_path.parent.joinpath(*posix_reference.parts).resolve()
    parent = manifest_path.parent.resolve()
    if not target.is_relative_to(parent):
        raise OfflineSnapshotLifecycleError("Fixture raw reference escapes its manifest directory.")
    return target


def _json_object(content: bytes, *, label: str) -> dict[str, Any]:
    try:
        parsed = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise OfflineSnapshotLifecycleError(f"{label.title()} is not valid UTF-8 JSON.") from error
    if not isinstance(parsed, dict):
        raise OfflineSnapshotLifecycleError(f"{label.title()} must be a JSON object.")
    return cast(dict[str, Any], parsed)


def _required_text(value: Mapping[str, Any], field: str) -> str:
    result = value.get(field)
    if not isinstance(result, str) or not result.strip():
        raise OfflineSnapshotLifecycleError(f"{field} must be a nonblank string.")
    return result.strip()


def _optional_text(value: object) -> str | None:
    return str(value) if value is not None else None


def _populated_int(value: object) -> int | None:
    if not isinstance(value, Mapping) or value.get("state") != "populated":
        return None
    candidate = value.get("value")
    return candidate if isinstance(candidate, int) and not isinstance(candidate, bool) else None


def _populated_text(value: object) -> str | None:
    if not isinstance(value, Mapping) or value.get("state") != "populated":
        return None
    candidate = value.get("value")
    if isinstance(candidate, str):
        return candidate
    if isinstance(candidate, int) and not isinstance(candidate, bool):
        return str(candidate)
    return None


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _deduplicate_sorted(values: Sequence[str]) -> list[str]:
    return sorted(set(values))
