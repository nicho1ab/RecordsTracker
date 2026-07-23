from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, cast

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    select,
)
from sqlalchemy.engine import Connection

from ccld_complaints.connectors.ccld_transparency_api.connector import (
    TransparencyApiConnectorError,
    parse_bulk_csv,
    validate_governed_url,
)
from ccld_complaints.connectors.ccld_transparency_api.contract import (
    CONNECTOR_VERSION,
    EXPORT_IDS,
    OBSERVATION_KIND,
    SNAPSHOT_SCOPE,
    SOURCE_FAMILY_ID,
    preserve_prior_populated_values,
    schema_fingerprint,
    source_family_schema_fingerprint,
)
from ccld_complaints.hosted_app.source_snapshot_lifecycle import (
    LifecycleState,
    SnapshotPointer,
    accept_source_snapshot,
    promote_source_snapshot,
    rollback_source_snapshot,
    source_snapshot_metadata,
    source_snapshot_pointers,
    source_snapshots,
    validate_source_snapshot,
)
from ccld_complaints.statewide_facility_source_evaluation import canonical_fingerprint

transparency_artifacts = Table(
    "hosted_transparencyapi_snapshot_artifacts",
    source_snapshot_metadata,
    Column(
        "snapshot_id",
        String(80),
        ForeignKey("hosted_source_snapshots.snapshot_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("artifact_id", String(128), primary_key=True),
    Column("endpoint_kind", String(40), nullable=False),
    Column("export_id", String(64), nullable=True),
    Column("request_url", Text, nullable=False),
    Column("final_url", Text, nullable=False),
    Column("retrieved_at", String(40), nullable=False),
    Column("http_status", Integer, nullable=False),
    Column("response_headers", JSON(none_as_null=True), nullable=False),
    Column("excluded_header_names", JSON(none_as_null=True), nullable=False),
    Column("media_type", String(96), nullable=False),
    Column("content_disposition", Text, nullable=True),
    Column("byte_count", Integer, nullable=False),
    Column("raw_sha256", String(64), nullable=False),
    Column("raw_ref", Text, nullable=False),
    CheckConstraint("byte_count >= 0", name="ck_transparencyapi_artifacts_nonnegative_bytes"),
    UniqueConstraint(
        "snapshot_id", "raw_sha256", "artifact_id", name="uq_transparencyapi_artifact_identity"
    ),
)

transparency_rows = Table(
    "hosted_transparencyapi_snapshot_rows",
    source_snapshot_metadata,
    Column(
        "snapshot_id",
        String(80),
        ForeignKey("hosted_source_snapshots.snapshot_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("export_id", String(64), primary_key=True),
    Column("row_ordinal", Integer, primary_key=True),
    Column("facility_number", String(32), nullable=True),
    Column("raw_row_sha256", String(64), nullable=False),
    Column("raw_values", JSON(none_as_null=True), nullable=False),
    Column("raw_record", JSON(none_as_null=True), nullable=False),
    Column("normalized_record", JSON(none_as_null=True), nullable=False),
    Column("resolved_current_reference", JSON(none_as_null=True), nullable=False),
    Column("autocomplete_search_text", Text, nullable=False, server_default=""),
    Column("complaint_blocks", JSON(none_as_null=True), nullable=False),
    Column("row_fingerprint", String(64), nullable=False),
    Column("is_quarantined", Boolean, nullable=False),
    CheckConstraint("row_ordinal > 0", name="ck_transparencyapi_rows_positive_ordinal"),
    UniqueConstraint(
        "snapshot_id",
        "export_id",
        "row_ordinal",
        "raw_row_sha256",
        name="uq_transparencyapi_row_quarantine_identity",
    ),
)
Index(
    "ix_transparencyapi_rows_facility_number",
    transparency_rows.c.facility_number,
)
Index(
    "ix_transparencyapi_rows_snapshot_facility_number",
    transparency_rows.c.snapshot_id,
    transparency_rows.c.facility_number,
)

_AUTOCOMPLETE_SEARCH_FIELDS = (
    "facility_name",
    "facility_city",
    "county_name",
    "facility_zip",
    "facility_state",
    "facility_type",
    "bulk_status",
)

transparency_quarantines = Table(
    "hosted_transparencyapi_snapshot_quarantines",
    source_snapshot_metadata,
    Column(
        "snapshot_id",
        String(80),
        ForeignKey("hosted_source_snapshots.snapshot_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("quarantine_id", String(64), primary_key=True),
    Column("category", String(64), nullable=False),
    Column("export_id", String(64), nullable=True),
    Column("row_ordinal", Integer, nullable=True),
    Column("facility_number", String(32), nullable=True),
    Column("raw_row_sha256", String(64), nullable=True),
    Column("evidence", JSON(none_as_null=True), nullable=False),
)
Index(
    "ix_transparencyapi_quarantines_category",
    transparency_quarantines.c.category,
)

transparency_disappearances = Table(
    "hosted_transparencyapi_snapshot_disappearances",
    source_snapshot_metadata,
    Column(
        "snapshot_id",
        String(80),
        ForeignKey("hosted_source_snapshots.snapshot_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("export_id", String(64), primary_key=True),
    Column("prior_row_ordinal", Integer, primary_key=True),
    Column(
        "prior_snapshot_id",
        String(80),
        ForeignKey("hosted_source_snapshots.snapshot_id"),
        nullable=False,
    ),
    Column("facility_number", String(32), nullable=True),
    Column("prior_row_fingerprint", String(64), nullable=False),
    Column("review_state", String(24), nullable=False),
    Column("closure_inferred", Boolean, nullable=False),
    CheckConstraint(
        "review_state = 'pending_reconciliation'",
        name="ck_transparencyapi_disappearances_review_state",
    ),
    CheckConstraint(
        "closure_inferred = false",
        name="ck_transparencyapi_disappearances_no_closure_inference",
    ),
)


@dataclass(frozen=True)
class TransparencySnapshotInspection:
    snapshot_id: str
    manifest_ref: str
    manifest_sha256: str
    raw_response_set_sha256: str
    normalized_content_sha256: str
    schema_fingerprint: str
    taxonomy_fingerprint: str
    recorded_at: str
    artifacts: tuple[Mapping[str, Any], ...]
    rows: tuple[Mapping[str, Any], ...]
    quarantines: tuple[Mapping[str, Any], ...]
    disappearances: tuple[Mapping[str, Any], ...]
    validation_report: Mapping[str, Any]


def inspect_transparencyapi_package(
    manifest_path: Path,
    *,
    prior_rows: Sequence[Mapping[str, Any]] = (),
    prior_snapshot_id: str | None = None,
) -> TransparencySnapshotInspection:
    manifest_bytes = manifest_path.read_bytes()
    manifest = _json_object(manifest_bytes, label="TransparencyAPI manifest")
    rejections: list[str] = []
    warnings: list[str] = []
    if manifest.get("contract_version") != CONNECTOR_VERSION:
        rejections.append("manifest contract_version is not supported")
    if manifest.get("source_family_id") != SOURCE_FAMILY_ID:
        rejections.append("manifest source_family_id is not approved")
    source_identity = manifest.get("source_identity")
    if not isinstance(source_identity, Mapping):
        rejections.append("manifest source_identity is missing")
    elif source_identity.get("facility_search_used") is not False:
        rejections.append("manifest does not prove FacilitySearch was excluded")
    if manifest.get("source_family_schema_fingerprint") != source_family_schema_fingerprint():
        rejections.append("manifest source-family schema fingerprint differs from contract")
    if manifest.get("fixed_header_fingerprints") != {
        export_id: schema_fingerprint(export_id) for export_id in EXPORT_IDS
    }:
        rejections.append("manifest fixed-header fingerprints differ from contract")
    recorded_at = str(manifest.get("recorded_at") or "")
    reference_year = _recorded_at_year(recorded_at)
    if reference_year is None:
        rejections.append("manifest recorded_at must be an ISO 8601 timestamp with a timezone")
    artifact_values = manifest.get("artifacts")
    if not isinstance(artifact_values, list):
        artifact_values = []
        rejections.append("manifest artifacts must be an array")

    artifacts: list[dict[str, Any]] = []
    exports_seen: Counter[str] = Counter()
    taxonomy_payloads: dict[str, object] = {}
    parsed_exports = []
    for index, value in enumerate(artifact_values, start=1):
        if not isinstance(value, Mapping):
            rejections.append(f"artifact {index} is not an object")
            continue
        artifact = dict(value)
        artifact_id = str(artifact.get("artifact_id") or "")
        raw_ref = str(artifact.get("raw_ref") or "")
        try:
            raw_path = _resolve_reference(manifest_path, raw_ref)
            raw_bytes = raw_path.read_bytes()
        except (TransparencyApiConnectorError, OSError) as error:
            rejections.append(f"artifact {artifact_id or index} cannot be read: {error}")
            continue
        raw_sha = hashlib.sha256(raw_bytes).hexdigest()
        if raw_sha != artifact.get("sha256"):
            rejections.append(f"artifact {artifact_id} SHA-256 differs from preserved bytes")
        if len(raw_bytes) != artifact.get("byte_count"):
            rejections.append(f"artifact {artifact_id} byte count differs from preserved bytes")
        response_headers = artifact.get("response_headers")
        if isinstance(response_headers, list):
            for header in response_headers:
                if (
                    isinstance(header, list)
                    and len(header) == 2
                    and str(header[0]).casefold() == "content-length"
                ):
                    try:
                        declared_length = int(header[1])
                    except (TypeError, ValueError):
                        rejections.append(f"artifact {artifact_id} has an invalid Content-Length")
                    else:
                        if declared_length != len(raw_bytes):
                            rejections.append(
                                f"artifact {artifact_id} appears truncated by Content-Length"
                            )
        try:
            validate_governed_url(str(artifact.get("request_url") or ""))
        except TransparencyApiConnectorError as error:
            rejections.append(f"artifact {artifact_id} request is not governed: {error}")
        if artifact.get("final_url") != artifact.get("request_url"):
            rejections.append(f"artifact {artifact_id} redirected unexpectedly")
        if artifact.get("status") != 200:
            rejections.append(f"artifact {artifact_id} was not HTTP 200")
        kind = artifact.get("endpoint_kind")
        media_type = str(artifact.get("media_type") or "").casefold()
        if kind == "bulk_export":
            export_id = str(artifact.get("export_id") or "")
            exports_seen[export_id] += 1
            if media_type not in {"text/csv", "application/csv", "application/octet-stream"}:
                rejections.append(f"bulk export {export_id} has a non-CSV media type")
            if export_id in EXPORT_IDS:
                parsed = parse_bulk_csv(
                    raw_bytes,
                    export_id=export_id,
                    reference_year=reference_year,
                )
                parsed_exports.append(parsed)
                rejections.extend(f"{export_id}: {reason}" for reason in parsed.rejection_reasons)
            else:
                rejections.append(f"artifact {artifact_id} has an unapproved export ID")
        elif kind in {"facility_type_taxonomy", "county_taxonomy"}:
            if media_type not in {"application/json", "text/json", "text/plain"}:
                rejections.append(f"artifact {artifact_id} has a non-JSON media type")
            try:
                taxonomy_payloads[str(kind)] = json.loads(raw_bytes.decode("utf-8-sig"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                rejections.append(f"artifact {artifact_id} is not valid JSON")
        artifacts.append(
            {
                "artifact_id": artifact_id,
                "endpoint_kind": str(kind or ""),
                "export_id": artifact.get("export_id"),
                "request_url": str(artifact.get("request_url") or ""),
                "final_url": str(artifact.get("final_url") or ""),
                "retrieved_at": str(artifact.get("retrieved_at") or ""),
                "http_status": int(artifact.get("status") or 0),
                "response_headers": artifact.get("response_headers") or [],
                "excluded_header_names": artifact.get("excluded_header_names") or [],
                "media_type": media_type,
                "content_disposition": artifact.get("content_disposition"),
                "byte_count": len(raw_bytes),
                "raw_sha256": raw_sha,
                "raw_ref": raw_ref,
            }
        )

    for export_id in EXPORT_IDS:
        count = exports_seen[export_id]
        if count != 1:
            rejections.append(f"complete source family requires exactly one {export_id} export")
    if set(taxonomy_payloads) != {"facility_type_taxonomy", "county_taxonomy"}:
        rejections.append("complete source family requires Group/ and CACounty artifacts")

    all_parsed_rows = [row for parsed in parsed_exports for row in parsed.rows]
    facility_counts = Counter(
        row.facility_number for row in all_parsed_rows if row.facility_number is not None
    )
    prior_by_number = {
        str(row["facility_number"]): cast(Mapping[str, Any], row["resolved_current_reference"])
        for row in prior_rows
        if row.get("facility_number") and not row.get("is_quarantined")
    }
    rows: list[dict[str, Any]] = []
    quarantines: list[dict[str, Any]] = []
    for row in all_parsed_rows:
        categories = set(row.quarantine_categories)
        if row.facility_number and facility_counts[row.facility_number] > 1:
            categories.add("duplicate_facility_number")
        normalized = dict(row.normalized_record)
        resolved = preserve_prior_populated_values(
            normalized,
            prior_by_number.get(row.facility_number or ""),
        )
        complaint_blocks = [
            {
                "ordinal": block.ordinal,
                "raw_values": list(block.raw_values),
                "values": dict(block.values),
            }
            for block in row.complaint_blocks
        ]
        row_fingerprint = canonical_fingerprint(
            {
                "export_id": row.export_id,
                "row_ordinal": row.row_ordinal,
                "raw_row_sha256": row.raw_row_sha256,
                "normalized_record": normalized,
                "complaint_blocks": complaint_blocks,
            }
        )
        rows.append(
            {
                "export_id": row.export_id,
                "row_ordinal": row.row_ordinal,
                "facility_number": row.facility_number,
                "raw_row_sha256": row.raw_row_sha256,
                "raw_values": list(row.raw_values),
                "raw_record": dict(row.raw_record),
                "normalized_record": normalized,
                "resolved_current_reference": resolved,
                "autocomplete_search_text": _autocomplete_search_text(
                    row.facility_number,
                    resolved,
                ),
                "complaint_blocks": complaint_blocks,
                "row_fingerprint": row_fingerprint,
                "is_quarantined": bool(categories),
            }
        )
        warnings.extend(row.warnings)
        for category in sorted(categories):
            identity = {
                "snapshot_id": str(manifest.get("snapshot_id") or ""),
                "export_id": row.export_id,
                "row_ordinal": row.row_ordinal,
                "raw_row_sha256": row.raw_row_sha256,
                "category": category,
            }
            quarantines.append(
                {
                    "quarantine_id": canonical_fingerprint(identity),
                    "category": category,
                    "export_id": row.export_id,
                    "row_ordinal": row.row_ordinal,
                    "facility_number": row.facility_number,
                    "raw_row_sha256": row.raw_row_sha256,
                    "evidence": {
                        **identity,
                        "trailing_values": list(row.trailing_values),
                    },
                }
            )

    current_numbers = {
        str(row["facility_number"])
        for row in rows
        if row["facility_number"] and not row["is_quarantined"]
    }
    disappearances: list[dict[str, Any]] = []
    if prior_snapshot_id:
        for prior in prior_rows:
            number = prior.get("facility_number")
            if not number or prior.get("is_quarantined") or str(number) in current_numbers:
                continue
            disappearances.append(
                {
                    "export_id": str(prior["export_id"]),
                    "prior_row_ordinal": int(prior["row_ordinal"]),
                    "prior_snapshot_id": prior_snapshot_id,
                    "facility_number": str(number),
                    "prior_row_fingerprint": str(prior["row_fingerprint"]),
                    "review_state": "pending_reconciliation",
                    "closure_inferred": False,
                }
            )
        if disappearances:
            warnings.append(
                f"{len(disappearances)} prior source row(s) disappeared; closure is not inferred"
            )

    rows.sort(key=lambda row: (str(row["export_id"]), int(row["row_ordinal"])))
    normalized_content_sha256 = canonical_fingerprint(
        [(row["export_id"], row["row_ordinal"], row["row_fingerprint"]) for row in rows]
    )
    taxonomy_fingerprint = canonical_fingerprint(taxonomy_payloads)
    expected_taxonomy_fingerprints = {
        kind: canonical_fingerprint(payload) for kind, payload in taxonomy_payloads.items()
    }
    if manifest.get("taxonomy_fingerprints") != expected_taxonomy_fingerprints:
        rejections.append("manifest taxonomy fingerprints differ from preserved content")
    if manifest.get("domain_fingerprint") != canonical_fingerprint(expected_taxonomy_fingerprints):
        rejections.append("manifest domain fingerprint differs from taxonomy fingerprints")
    known_type_codes = _taxonomy_codes(taxonomy_payloads.get("facility_type_taxonomy"))
    if known_type_codes and "777" not in known_type_codes:
        warnings.append("facility-type taxonomy omits known valid type code 777")
    raw_response_set_sha256 = canonical_fingerprint(
        [(artifact["artifact_id"], artifact["raw_sha256"]) for artifact in artifacts]
    )
    if manifest.get("raw_response_set_sha256") != raw_response_set_sha256:
        rejections.append("manifest raw_response_set_sha256 differs from preserved artifacts")
    report = {
        "row_count": len(all_parsed_rows),
        "stored_row_count": len(rows),
        "duplicate_object_id_count": 0,
        "duplicate_facility_number_count": sum(
            count - 1 for count in facility_counts.values() if count > 1
        ),
        "omitted_field_count": 0,
        "invalid_field_count": 0,
        "quarantine_count": len(quarantines),
        "disappearance_count": len(disappearances),
        "warnings": sorted(set(warnings)),
        "rejection_reasons": sorted(set(rejections)),
        "closure_inferred": False,
        "canonical_or_reviewer_fields_written": False,
        "all_seven_exports_present": all(exports_seen[value] == 1 for value in EXPORT_IDS),
        "ckan_history_preserved": True,
        "arcgis_observations_remain_separate": True,
        "known_type_code_count": len(known_type_codes),
        "type_777_available": "777" in known_type_codes,
    }
    return TransparencySnapshotInspection(
        snapshot_id=str(manifest.get("snapshot_id") or ""),
        manifest_ref=manifest_path.name,
        manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        raw_response_set_sha256=raw_response_set_sha256,
        normalized_content_sha256=normalized_content_sha256,
        schema_fingerprint=source_family_schema_fingerprint(),
        taxonomy_fingerprint=taxonomy_fingerprint,
        recorded_at=recorded_at,
        artifacts=tuple(artifacts),
        rows=tuple(rows),
        quarantines=tuple(quarantines),
        disappearances=tuple(disappearances),
        validation_report=report,
    )


def stage_transparencyapi_snapshot(
    connection: Connection,
    manifest_path: Path,
) -> TransparencySnapshotInspection:
    active = (
        connection.execute(
            select(source_snapshots)
            .join(
                source_snapshot_pointers,
                source_snapshot_pointers.c.active_snapshot_id == source_snapshots.c.snapshot_id,
            )
            .where(source_snapshot_pointers.c.source_family_id == SOURCE_FAMILY_ID)
        )
        .mappings()
        .one_or_none()
    )
    prior_snapshot_id = str(active["snapshot_id"]) if active is not None else None
    prior_rows: Sequence[Mapping[str, Any]] = ()
    if prior_snapshot_id:
        prior_rows = tuple(
            dict(row)
            for row in connection.execute(
                select(transparency_rows).where(
                    transparency_rows.c.snapshot_id == prior_snapshot_id
                )
            ).mappings()
        )
    inspection = inspect_transparencyapi_package(
        manifest_path,
        prior_rows=prior_rows,
        prior_snapshot_id=prior_snapshot_id,
    )
    existing = (
        connection.execute(
            select(source_snapshots).where(source_snapshots.c.snapshot_id == inspection.snapshot_id)
        )
        .mappings()
        .one_or_none()
    )
    if existing is not None:
        if (
            existing["source_family_id"] != SOURCE_FAMILY_ID
            or existing["manifest_sha256"] != inspection.manifest_sha256
            or existing["raw_payload_sha256"] != inspection.raw_response_set_sha256
        ):
            raise TransparencyApiConnectorError(
                "Snapshot ID already exists with different immutable evidence."
            )
        return _stored_transparencyapi_inspection(connection, dict(existing))
    if not inspection.snapshot_id:
        raise TransparencyApiConnectorError("Snapshot manifest has no snapshot_id.")
    report = inspection.validation_report
    connection.execute(
        source_snapshots.insert().values(
            snapshot_id=inspection.snapshot_id,
            source_family_id=SOURCE_FAMILY_ID,
            fixture_scope=SNAPSHOT_SCOPE,
            observation_kind=OBSERVATION_KIND,
            lifecycle_state="candidate",
            manifest_ref=inspection.manifest_ref,
            manifest_sha256=inspection.manifest_sha256,
            raw_payload_ref="raw-response-set",
            raw_payload_sha256=inspection.raw_response_set_sha256,
            normalized_content_sha256=inspection.normalized_content_sha256,
            schema_fingerprint=inspection.schema_fingerprint,
            domain_fingerprint=inspection.taxonomy_fingerprint,
            row_count=int(report["row_count"]),
            stored_row_count=int(report["stored_row_count"]),
            duplicate_object_id_count=0,
            duplicate_facility_number_count=int(report["duplicate_facility_number_count"]),
            omitted_field_count=0,
            invalid_field_count=0,
            warning_count=len(cast(Sequence[object], report["warnings"])),
            rejection_reason_count=len(cast(Sequence[object], report["rejection_reasons"])),
            validation_report=dict(report),
            recorded_at=inspection.recorded_at,
        )
    )
    if inspection.artifacts:
        connection.execute(
            transparency_artifacts.insert(),
            [dict(value, snapshot_id=inspection.snapshot_id) for value in inspection.artifacts],
        )
    if inspection.rows:
        connection.execute(
            transparency_rows.insert(),
            [dict(value, snapshot_id=inspection.snapshot_id) for value in inspection.rows],
        )
    if inspection.quarantines:
        connection.execute(
            transparency_quarantines.insert(),
            [dict(value, snapshot_id=inspection.snapshot_id) for value in inspection.quarantines],
        )
    if inspection.disappearances:
        connection.execute(
            transparency_disappearances.insert(),
            [
                dict(value, snapshot_id=inspection.snapshot_id)
                for value in inspection.disappearances
            ],
        )
    return inspection


def validate_transparencyapi_snapshot(
    connection: Connection, snapshot_id: str, *, validated_at: str
) -> LifecycleState:
    return validate_source_snapshot(
        connection,
        snapshot_id,
        expected_source_family_id=SOURCE_FAMILY_ID,
        expected_scope=SNAPSHOT_SCOPE,
        validated_at=validated_at,
    )


def accept_transparencyapi_snapshot(
    connection: Connection, snapshot_id: str, *, accepted_at: str
) -> None:
    accept_source_snapshot(
        connection,
        snapshot_id,
        expected_source_family_id=SOURCE_FAMILY_ID,
        expected_scope=SNAPSHOT_SCOPE,
        accepted_at=accepted_at,
    )


def promote_transparencyapi_snapshot(
    connection: Connection, snapshot_id: str, *, promoted_at: str
) -> SnapshotPointer:
    return promote_source_snapshot(
        connection,
        snapshot_id,
        expected_source_family_id=SOURCE_FAMILY_ID,
        expected_scope=SNAPSHOT_SCOPE,
        promoted_at=promoted_at,
    )


def rollback_transparencyapi_snapshot(
    connection: Connection,
    *,
    expected_active_snapshot_id: str,
    rolled_back_at: str,
) -> SnapshotPointer:
    return rollback_source_snapshot(
        connection,
        expected_source_family_id=SOURCE_FAMILY_ID,
        expected_active_snapshot_id=expected_active_snapshot_id,
        expected_active_scope=SNAPSHOT_SCOPE,
        expected_prior_scope=SNAPSHOT_SCOPE,
        rolled_back_at=rolled_back_at,
    )


def _autocomplete_search_text(
    facility_number: str | None,
    resolved_current_reference: Mapping[str, Any],
) -> str:
    values = [facility_number or ""]
    for field_name in _AUTOCOMPLETE_SEARCH_FIELDS:
        observation = resolved_current_reference.get(field_name)
        if not isinstance(observation, Mapping):
            continue
        value = observation.get("value")
        if value is not None:
            values.append(str(value))
    return " ".join(" ".join(value.split()).casefold() for value in values if value.strip())


def _resolve_reference(manifest_path: Path, reference: str) -> Path:
    pure = PurePosixPath(reference)
    if not reference or pure.is_absolute() or ".." in pure.parts:
        raise TransparencyApiConnectorError("Artifact reference must be relative and contained.")
    root = manifest_path.parent.resolve()
    resolved = root.joinpath(*pure.parts).resolve()
    if not resolved.is_relative_to(root):
        raise TransparencyApiConnectorError("Artifact reference escapes the snapshot package.")
    return resolved


def _stored_transparencyapi_inspection(
    connection: Connection,
    snapshot: Mapping[str, Any],
) -> TransparencySnapshotInspection:
    snapshot_id = str(snapshot["snapshot_id"])

    def stored_rows(table: Table) -> tuple[Mapping[str, Any], ...]:
        values = connection.execute(
            select(table)
            .where(table.c.snapshot_id == snapshot_id)
            .order_by(*table.primary_key.columns)
        ).mappings()
        return tuple(
            {key: item for key, item in dict(value).items() if key != "snapshot_id"}
            for value in values
        )

    return TransparencySnapshotInspection(
        snapshot_id=snapshot_id,
        manifest_ref=str(snapshot["manifest_ref"]),
        manifest_sha256=str(snapshot["manifest_sha256"]),
        raw_response_set_sha256=str(snapshot["raw_payload_sha256"]),
        normalized_content_sha256=str(snapshot["normalized_content_sha256"]),
        schema_fingerprint=str(snapshot["schema_fingerprint"]),
        taxonomy_fingerprint=str(snapshot["domain_fingerprint"]),
        recorded_at=str(snapshot["recorded_at"]),
        artifacts=stored_rows(transparency_artifacts),
        rows=stored_rows(transparency_rows),
        quarantines=stored_rows(transparency_quarantines),
        disappearances=stored_rows(transparency_disappearances),
        validation_report=dict(cast(Mapping[str, Any], snapshot["validation_report"])),
    )


def _json_object(content: bytes, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(content.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TransparencyApiConnectorError(f"{label} is not valid JSON.") from error
    if not isinstance(value, dict):
        raise TransparencyApiConnectorError(f"{label} must be a JSON object.")
    return value


def _recorded_at_year(value: str) -> int | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.year


def _taxonomy_codes(payload: object) -> frozenset[str]:
    items: object
    if isinstance(payload, Mapping):
        items = next(
            (
                value
                for key, value in payload.items()
                if str(key).casefold() in {"groups", "data", "items", "types"}
            ),
            [],
        )
    else:
        items = payload
    if not isinstance(items, list):
        return frozenset()
    codes: set[str] = set()
    for item in items:
        if not isinstance(item, Mapping):
            continue
        by_name = {str(key).casefold(): value for key, value in item.items()}
        for name in ("type", "typecode", "groupid", "id"):
            if name in by_name and str(by_name[name]).strip():
                codes.add(str(by_name[name]).strip())
                break
    return frozenset(codes)
