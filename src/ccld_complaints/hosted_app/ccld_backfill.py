from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from sqlalchemy import inspect, select
from sqlalchemy.engine import Connection

from ccld_complaints.connectors.base import SourceDocument
from ccld_complaints.connectors.ccld.facility_reports import CcldFacilityReportsConnector
from ccld_complaints.hosted_app.ccld_source_refresh import (
    prepare_ccld_hosted_source_records,
    validate_approved_facility_reference_configuration,
)
from ccld_complaints.hosted_app.seeded_import import (
    SeededCorpusArtifact,
    hosted_source_derived_records,
    import_seeded_corpus_artifact,
)
from ccld_complaints.utils.hash import sha256_bytes

BackfillOperation = Literal["all", "facility-reference", "preserved-artifacts"]
_REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class CcldHostedBackfillRequest:
    facility_numbers: tuple[str, ...]
    all_existing: bool = False
    operation: BackfillOperation = "all"
    batch_size: int = 100
    apply_changes: bool = False
    checkpoint_file: Path | None = None
    restart: bool = False


@dataclass(frozen=True)
class CcldHostedBackfillResult:
    apply_changes: bool
    examined: int
    eligible: int
    updated: int
    unchanged: int
    skipped: int
    conflicted: int
    warnings: int
    failed: int


def run_ccld_hosted_backfill(
    connection: Connection,
    request: CcldHostedBackfillRequest,
    *,
    now: datetime | None = None,
) -> CcldHostedBackfillResult:
    _validate_request(connection, request)
    selected = _selected_facilities(connection, request)
    completed = _load_checkpoint(request)
    pending = tuple(item for item in selected if item[0] not in completed)
    if request.apply_changes and _uses_facility_reference(request.operation):
        validate_approved_facility_reference_configuration(
            connection,
            tuple(facility_number for facility_number, _facility in pending),
        )

    counts = {
        "examined": 0,
        "eligible": 0,
        "updated": 0,
        "unchanged": 0,
        "skipped": len(selected) - len(pending),
        "conflicted": 0,
        "warnings": 0,
        "failed": 0,
    }
    active_now = now or datetime.now(UTC)
    for offset in range(0, len(pending), request.batch_size):
        batch = pending[offset : offset + request.batch_size]
        for facility_number, facility_row in batch:
            counts["examined"] += 1
            transaction = connection.begin_nested()
            try:
                outcome = _process_facility(
                    connection,
                    facility_number,
                    facility_row,
                    request=request,
                    now=active_now,
                )
                if not request.apply_changes:
                    transaction.rollback()
                else:
                    transaction.commit()
                counts["eligible"] += int(outcome["eligible"])
                counts["updated"] += int(outcome["updated"])
                counts["unchanged"] += int(outcome["unchanged"])
                counts["skipped"] += int(outcome["skipped"])
                counts["conflicted"] += int(outcome["conflicted"])
                counts["warnings"] += int(outcome["warnings"])
                if request.apply_changes:
                    completed.add(facility_number)
                    _write_checkpoint(request.checkpoint_file, completed)
            except Exception:
                transaction.rollback()
                counts["failed"] += 1

    return CcldHostedBackfillResult(
        apply_changes=request.apply_changes,
        examined=counts["examined"],
        eligible=counts["eligible"],
        updated=counts["updated"],
        unchanged=counts["unchanged"],
        skipped=counts["skipped"],
        conflicted=counts["conflicted"],
        warnings=counts["warnings"],
        failed=counts["failed"],
    )


def _process_facility(
    connection: Connection,
    facility_number: str,
    facility_row: Mapping[str, Any],
    *,
    request: CcldHostedBackfillRequest,
    now: datetime,
) -> Mapping[str, int | bool]:
    source_documents = _source_documents_for_facility(
        connection,
        str(facility_row["facility_id"]),
    )
    records: list[Mapping[str, Any]] = []
    warning_count = 0
    if _uses_preserved_artifacts(request.operation):
        for source_document_row in source_documents:
            normalized = _reprocess_preserved_document(
                connection,
                facility_number,
                facility_row,
                source_document_row,
            )
            if normalized is None:
                warning_count += 1
                continue
            records.append(normalized)
    elif source_documents:
        records.append(
            {
                "facility": dict(cast(Mapping[str, Any], facility_row["original_values"])),
                "source_document": dict(
                    cast(Mapping[str, Any], source_documents[0]["original_values"])
                ),
                "extraction_audit": [],
            }
        )

    if not records:
        return {
            "eligible": False,
            "updated": 0,
            "unchanged": 0,
            "skipped": 1,
            "conflicted": 0,
            "warnings": warning_count,
        }

    prepared = prepare_ccld_hosted_source_records(
        connection,
        records,
        include_facility_reference=_uses_facility_reference(request.operation),
    )
    warning_count += len(prepared.warnings)
    if request.operation == "facility-reference" and not prepared.reference_found:
        return {
            "eligible": False,
            "updated": 0,
            "unchanged": 1,
            "skipped": 0,
            "conflicted": 0,
            "warnings": warning_count,
        }

    artifact = _backfill_artifact(
        facility_number,
        prepared.records,
        operation=request.operation,
        now=now,
    )
    import_result = import_seeded_corpus_artifact(
        connection,
        artifact,
        preserve_existing_import_batch=True,
    )
    changed = import_result.inserted_record_count + import_result.updated_record_count
    return {
        "eligible": True,
        "updated": int(changed > 0),
        "unchanged": int(changed == 0),
        "skipped": 0,
        "conflicted": max(
            prepared.conflicted_field_count,
            import_result.conflicted_field_count,
        ),
        "warnings": warning_count,
    }


def _reprocess_preserved_document(
    connection: Connection,
    facility_number: str,
    facility_row: Mapping[str, Any],
    source_document_row: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    if source_document_row.get("connector_name") != CcldFacilityReportsConnector.connector_name:
        return None
    values = cast(Mapping[str, Any], source_document_row["original_values"])
    raw_path_value = _optional_text(values.get("raw_path") or source_document_row.get("raw_path"))
    if raw_path_value is None:
        return None
    raw_path = _resolved_raw_path(raw_path_value)
    content = raw_path.read_bytes()
    expected_hash = _required_text(values.get("raw_sha256"), "raw_sha256")
    if sha256_bytes(content) != expected_hash:
        raise ValueError("Preserved CCLD artifact hash validation failed.")
    document = SourceDocument(
        source_url=_required_text(values.get("source_url"), "source_url"),
        raw_path=raw_path,
        raw_sha256=expected_hash,
        retrieved_at=_optional_text(values.get("retrieved_at")),
        content_type=_optional_text(values.get("content_type")),
    )
    connector = CcldFacilityReportsConnector(
        facility_number=facility_number,
        raw_dir=raw_path.parent,
    )
    normalized = connector.normalize(connector.extract(document))
    normalized["source_document"] = dict(values)
    _preserve_stable_identities(
        connection,
        normalized,
        facility_row,
        source_document_row,
    )
    connector.validate(normalized)
    return normalized


def _preserve_stable_identities(
    connection: Connection,
    normalized: dict[str, object],
    facility_row: Mapping[str, Any],
    source_document_row: Mapping[str, Any],
) -> None:
    facility = cast(dict[str, Any], normalized["facility"])
    source_document = cast(dict[str, Any], normalized["source_document"])
    old_document_id = str(source_document["document_id"])
    facility_id = str(facility_row["stable_source_id"])
    document_id = str(source_document_row["stable_source_id"])
    facility["facility_id"] = facility_id
    source_document["document_id"] = document_id
    source_document["facility_id"] = facility_id
    complaint = cast(dict[str, Any], normalized["complaint"])
    existing = _related_records(connection, document_id)
    existing_complaint = next(
        (row for row in existing if row["entity_type"] == "complaint"),
        None,
    )
    if existing_complaint is not None:
        complaint["complaint_id"] = existing_complaint["stable_source_id"]
    complaint["facility_id"] = facility_id
    complaint["document_id"] = document_id
    complaint_id = str(complaint["complaint_id"])
    for entity_type, list_name, id_field in (
        ("allegation", "allegations", "allegation_id"),
        ("event", "events", "event_id"),
    ):
        items = cast(list[dict[str, Any]], normalized.get(list_name, []))
        prior = sorted(
            (row for row in existing if row["entity_type"] == entity_type),
            key=lambda row: str(row["stable_source_id"]),
        )
        for index, item in enumerate(items):
            if index < len(prior):
                item[id_field] = prior[index]["stable_source_id"]
            item["complaint_id"] = complaint_id
    prior_audits = {
        str(cast(Mapping[str, Any], row["original_values"]).get("field_name")): row
        for row in existing
        if row["entity_type"] == "extraction_audit"
    }
    for audit in cast(list[dict[str, Any]], normalized.get("extraction_audit", [])):
        audit["document_id"] = document_id
        field_name = str(audit.get("field_name") or "")
        prior_audit = prior_audits.get(field_name)
        if prior_audit is not None:
            audit["audit_id"] = prior_audit["stable_source_id"]
        elif str(audit.get("audit_id", "")).startswith(old_document_id):
            audit["audit_id"] = document_id + str(audit["audit_id"])[len(old_document_id) :]


def _related_records(
    connection: Connection,
    source_document_id: str,
) -> tuple[Mapping[str, Any], ...]:
    return tuple(
        dict(row)
        for row in connection.execute(
            select(hosted_source_derived_records).where(
                hosted_source_derived_records.c.source_document_id == source_document_id
            )
        ).mappings()
    )


def _source_documents_for_facility(
    connection: Connection,
    facility_id: str,
) -> tuple[Mapping[str, Any], ...]:
    return tuple(
        dict(row)
        for row in connection.execute(
            select(hosted_source_derived_records)
            .where(
                hosted_source_derived_records.c.entity_type == "source_document",
                hosted_source_derived_records.c.facility_id == facility_id,
            )
            .order_by(hosted_source_derived_records.c.stable_source_id)
        ).mappings()
    )


def _selected_facilities(
    connection: Connection,
    request: CcldHostedBackfillRequest,
) -> tuple[tuple[str, Mapping[str, Any]], ...]:
    rows = tuple(
        dict(row)
        for row in connection.execute(
            select(hosted_source_derived_records)
            .where(hosted_source_derived_records.c.entity_type == "facility")
            .order_by(hosted_source_derived_records.c.stable_source_id)
        ).mappings()
    )
    requested = set(request.facility_numbers)
    selected: list[tuple[str, Mapping[str, Any]]] = []
    for row in rows:
        values = cast(Mapping[str, Any], row["original_values"])
        facility_number = _optional_text(values.get("external_facility_number"))
        if facility_number is None:
            continue
        if request.all_existing or facility_number in requested:
            selected.append((facility_number, row))
    return tuple(selected)


def _backfill_artifact(
    facility_number: str,
    records: Sequence[Mapping[str, Any]],
    *,
    operation: BackfillOperation,
    now: datetime,
) -> SeededCorpusArtifact:
    fingerprint_source = json.dumps(records, sort_keys=True, separators=(",", ":"), default=str)
    fingerprint = sha256_bytes(fingerprint_source.encode("utf-8"))
    return SeededCorpusArtifact(
        import_batch_id=f"ccld-backfill-{fingerprint[:32]}",
        imported_at=now.replace(microsecond=0).isoformat(),
        source_artifact_identity=(
            f"preserved-ccld-backfill:{operation}:{facility_number}:{fingerprint[:16]}"
        ),
        source_pipeline_version="governed-ccld-hosted-refresh-1.0.0",
        validation_status="validated",
        raw_hash_validation_status="validated",
        record_counts=_record_counts(records),
        warnings=(),
        errors=(),
        records=tuple(records),
    )


def _record_counts(records: Sequence[Mapping[str, Any]]) -> Mapping[str, int]:
    counts: dict[str, set[str]] = {
        "facility": set(),
        "source_document": set(),
        "complaint": set(),
        "allegation": set(),
        "event": set(),
        "extraction_audit": set(),
    }
    for record in records:
        for entity, id_field in (
            ("facility", "facility_id"),
            ("source_document", "document_id"),
            ("complaint", "complaint_id"),
        ):
            values = record.get(entity)
            if isinstance(values, Mapping) and values.get(id_field):
                counts[entity].add(str(values[id_field]))
        for entity, list_name, id_field in (
            ("allegation", "allegations", "allegation_id"),
            ("event", "events", "event_id"),
            ("extraction_audit", "extraction_audit", "audit_id"),
        ):
            for values in record.get(list_name, []):
                if isinstance(values, Mapping) and values.get(id_field):
                    counts[entity].add(str(values[id_field]))
    return {key: len(values) for key, values in counts.items()}


def _validate_request(connection: Connection, request: CcldHostedBackfillRequest) -> None:
    if not inspect(connection).has_table(hosted_source_derived_records.name):
        raise ValueError("Hosted source-derived tables are not initialized.")
    if request.operation not in {"all", "facility-reference", "preserved-artifacts"}:
        raise ValueError("Unsupported CCLD hosted backfill operation.")
    if request.batch_size < 1 or request.batch_size > 1000:
        raise ValueError("batch_size must be between 1 and 1000.")
    if request.all_existing == bool(request.facility_numbers):
        raise ValueError("Select either all existing facilities or explicit facility numbers.")
    if any(not value.isdigit() for value in request.facility_numbers):
        raise ValueError("Facility numbers must contain digits only.")
    if request.restart and request.checkpoint_file is None:
        raise ValueError("restart requires a checkpoint file.")


def _load_checkpoint(request: CcldHostedBackfillRequest) -> set[str]:
    path = request.checkpoint_file
    if path is None or request.restart or not path.exists():
        return set()
    loaded = json.loads(path.read_text(encoding="utf-8"))
    values = loaded.get("completed_facility_numbers") if isinstance(loaded, dict) else None
    if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
        raise ValueError("Backfill checkpoint is not valid.")
    return set(values)


def _write_checkpoint(path: Path | None, completed: set[str]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"version": 1, "completed_facility_numbers": sorted(completed)},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _resolved_raw_path(value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        resolved = candidate
    else:
        resolved = (_REPO_ROOT / candidate).resolve()
    if not resolved.is_file():
        raise FileNotFoundError("Preserved CCLD artifact is unavailable.")
    return resolved


def _uses_facility_reference(operation: BackfillOperation) -> bool:
    return operation in {"all", "facility-reference"}


def _uses_preserved_artifacts(operation: BackfillOperation) -> bool:
    return operation in {"all", "preserved-artifacts"}


def _required_text(value: object, field_name: str) -> str:
    normalized = _optional_text(value)
    if normalized is None:
        raise ValueError(f"Missing required preserved source value: {field_name}")
    return normalized


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None
