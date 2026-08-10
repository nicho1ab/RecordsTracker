from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
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
    SeededSourceDerivedRecord,
    _deduplicate_source_record_projections,
    _prepared_source_record_values,
    flatten_seeded_corpus_records,
    hosted_import_batches,
    hosted_source_derived_records,
    import_seeded_corpus_artifact,
)
from ccld_complaints.utils.hash import sha256_bytes

BackfillOperation = Literal[
    "all",
    "facility-reference",
    "preserved-artifacts",
    "canonical-complaint-observations",
]
_REPO_ROOT = Path(__file__).resolve().parents[3]
_IDENTITY_ORDINAL_PATTERN = re.compile(r"(?:^|[-:])(\d+)(?=$|[-:])")


@dataclass(frozen=True)
class CcldHostedBackfillRequest:
    facility_numbers: tuple[str, ...]
    all_existing: bool = False
    operation: BackfillOperation = "all"
    batch_size: int = 100
    apply_changes: bool = False
    checkpoint_file: Path | None = None
    restart: bool = False
    max_facilities: int | None = None


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
    candidates: int = 0
    excluded: int = 0
    intended_updates: int = 0


@dataclass(frozen=True)
class CcldHostedBackfillDifference:
    facility_number: str
    entity_type: str
    source_record_key: str
    differing_fields: tuple[str, ...]
    persisted: Mapping[str, object]
    prepared: Mapping[str, object]


@dataclass
class _BackfillCheckpoint:
    selected_facility_numbers: tuple[str, ...]
    completed_facility_numbers: set[str]
    failed_attempts: dict[str, int]


def run_ccld_hosted_backfill(
    connection: Connection,
    request: CcldHostedBackfillRequest,
    *,
    now: datetime | None = None,
) -> CcldHostedBackfillResult:
    _validate_request(connection, request)
    selected, candidate_count, selection_conflicts, missing_count = _selected_facilities(
        connection, request
    )
    selected_by_number = dict(selected)
    checkpoint = _load_checkpoint(request)
    new_checkpoint = checkpoint is None
    frozen_selection_excluded = 0
    if checkpoint is not None:
        unavailable = tuple(
            value
            for value in checkpoint.selected_facility_numbers
            if value not in selected_by_number
        )
        if unavailable:
            raise ValueError(
                "Backfill checkpoint selection is no longer available; restart is required."
            )
        selected = tuple(
            (value, selected_by_number[value])
            for value in checkpoint.selected_facility_numbers
        )
        frozen_selection_excluded = len(selected_by_number) - len(selected)
    else:
        checkpoint = _BackfillCheckpoint(
            selected_facility_numbers=tuple(value for value, _row in selected),
            completed_facility_numbers=set(),
            failed_attempts={},
        )
    completed = checkpoint.completed_facility_numbers
    pending = tuple(item for item in selected if item[0] not in completed)
    limit = request.max_facilities or len(pending)
    active_pending = pending[:limit]
    deferred_count = len(pending) - len(active_pending)
    if request.apply_changes and _uses_facility_reference(request.operation):
        validate_approved_facility_reference_configuration(
            connection,
            tuple(facility_number for facility_number, _facility in active_pending),
        )
    if request.apply_changes and new_checkpoint:
        _write_checkpoint(request, checkpoint)

    counts = {
        "examined": 0,
        "eligible": 0,
        "updated": 0,
        "unchanged": 0,
        "skipped": (
            len(selected)
            - len(pending)
            + missing_count
            + selection_conflicts
            + deferred_count
            + frozen_selection_excluded
        ),
        "conflicted": selection_conflicts,
        "warnings": 0,
        "failed": 0,
    }
    active_now = now or datetime.now(UTC)
    for offset in range(0, len(active_pending), request.batch_size):
        batch = active_pending[offset : offset + request.batch_size]
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
                    connection.commit()
                counts["eligible"] += int(outcome["eligible"])
                counts["updated"] += int(outcome["updated"])
                counts["unchanged"] += int(outcome["unchanged"])
                counts["skipped"] += int(outcome["skipped"])
                counts["conflicted"] += int(outcome["conflicted"])
                counts["warnings"] += int(outcome["warnings"])
                if request.apply_changes:
                    completed.add(facility_number)
                    checkpoint.failed_attempts.pop(facility_number, None)
                    _write_checkpoint(request, checkpoint)
            except Exception:
                if transaction.is_active:
                    transaction.rollback()
                else:
                    connection.rollback()
                counts["failed"] += 1
                if request.apply_changes:
                    checkpoint.failed_attempts[facility_number] = (
                        checkpoint.failed_attempts.get(facility_number, 0) + 1
                    )
                    _write_checkpoint(request, checkpoint)

    return CcldHostedBackfillResult(
        apply_changes=request.apply_changes,
        candidates=candidate_count,
        excluded=(
            missing_count
            + selection_conflicts
            + deferred_count
            + frozen_selection_excluded
        ),
        examined=counts["examined"],
        eligible=counts["eligible"],
        intended_updates=counts["updated"],
        updated=counts["updated"],
        unchanged=counts["unchanged"],
        skipped=counts["skipped"],
        conflicted=counts["conflicted"],
        warnings=counts["warnings"],
        failed=counts["failed"],
    )


def diagnose_ccld_preserved_artifact_differences(
    connection: Connection,
    facility_numbers: Sequence[str],
) -> tuple[CcldHostedBackfillDifference, ...]:
    """Compare replay values with persisted rows using SELECT-only preparation."""

    requested = tuple(dict.fromkeys(str(value).strip() for value in facility_numbers))
    if not requested or any(not value.isdigit() for value in requested):
        raise ValueError("Diagnostic Facility IDs must be an explicit digit-only selection.")
    request = CcldHostedBackfillRequest(
        facility_numbers=requested,
        operation="preserved-artifacts",
        apply_changes=False,
    )
    _validate_request(connection, request)
    selected, _candidate_count, selection_conflicts, missing_count = _selected_facilities(
        connection,
        request,
    )
    if selection_conflicts or missing_count or len(selected) != len(requested):
        raise ValueError(
            "Diagnostic selection must resolve every explicit Facility ID exactly once."
        )

    differences: list[CcldHostedBackfillDifference] = []
    for facility_number, facility_row in selected:
        source_documents = _source_documents_for_facility(
            connection,
            str(facility_row["facility_id"]),
        )
        records: list[Mapping[str, Any]] = []
        for source_document_row in source_documents:
            normalized = _reprocess_preserved_document(
                connection,
                facility_number,
                facility_row,
                source_document_row,
            )
            if normalized is None:
                raise ValueError(
                    "Diagnostic selection contains an unsupported preserved source document."
                )
            records.append(normalized)
        if not records:
            raise ValueError("Diagnostic selection has no preserved CCLD source documents.")
        prepared = prepare_ccld_hosted_source_records(
            connection,
            records,
            include_facility_reference=False,
        )
        artifact = _backfill_artifact(
            facility_number,
            _deduplicate_facility_projections(prepared.records),
            operation="preserved-artifacts",
            now=datetime(2000, 1, 1, tzinfo=UTC),
        )
        artifact = _stabilize_equivalent_artifact_provenance(connection, artifact)
        flattened = _deduplicate_source_record_projections(
            flatten_seeded_corpus_records(artifact)
        )
        for record in flattened:
            difference = _source_record_difference(
                connection,
                facility_number,
                record,
            )
            if difference is not None:
                differences.append(difference)
    return tuple(
        sorted(
            differences,
            key=lambda row: (
                row.facility_number,
                row.entity_type,
                row.source_record_key,
            ),
        )
    )


def _source_record_difference(
    connection: Connection,
    facility_number: str,
    record: SeededSourceDerivedRecord,
) -> CcldHostedBackfillDifference | None:
    existing = cast(
        Mapping[str, Any] | None,
        connection.execute(
            select(hosted_source_derived_records).where(
                hosted_source_derived_records.c.source_record_key
                == record.source_record_key
            )
        ).mappings().first(),
    )
    values, _conflicts = _prepared_source_record_values(
        connection,
        record,
        existing,
        preserve_existing_import_batch=True,
    )
    if existing is None:
        return CcldHostedBackfillDifference(
            facility_number=facility_number,
            entity_type=record.entity_type,
            source_record_key=record.source_record_key,
            differing_fields=("persisted_record",),
            persisted={"persisted_record": {"type": "missing"}},
            prepared={"persisted_record": _diagnostic_value_summary(values)},
        )
    fields, persisted, prepared = _differing_source_record_fields(existing, values)
    if not fields:
        return None
    return CcldHostedBackfillDifference(
        facility_number=facility_number,
        entity_type=record.entity_type,
        source_record_key=record.source_record_key,
        differing_fields=fields,
        persisted=persisted,
        prepared=prepared,
    )


def _differing_source_record_fields(
    existing: Mapping[str, Any],
    values: Mapping[str, Any],
) -> tuple[tuple[str, ...], dict[str, object], dict[str, object]]:
    fields: list[str] = []
    persisted: dict[str, object] = {}
    prepared: dict[str, object] = {}
    for key in sorted(values):
        before = existing.get(key)
        after = values[key]
        if before == after:
            continue
        if key in {"original_values", "source_traceability"} and isinstance(
            before, Mapping
        ) and isinstance(after, Mapping):
            nested_keys = sorted(set(before) | set(after))
            for nested_key in nested_keys:
                nested_before = before.get(nested_key)
                nested_after = after.get(nested_key)
                if nested_before == nested_after:
                    continue
                path = f"{key}.{nested_key}"
                fields.append(path)
                persisted[path] = _diagnostic_value_summary(nested_before)
                prepared[path] = _diagnostic_value_summary(nested_after)
            continue
        fields.append(key)
        persisted[key] = _diagnostic_value_summary(before)
        prepared[key] = _diagnostic_value_summary(after)
    return tuple(fields), persisted, prepared


def _diagnostic_value_summary(value: object) -> Mapping[str, object]:
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "boolean", "value": value}
    if isinstance(value, int | float):
        return {"type": "number", "value": value}
    if isinstance(value, str):
        encoded = value.encode("utf-8")
        return {
            "type": "string",
            "length": len(value),
            "sha256": sha256_bytes(encoded),
        }
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    summary: dict[str, object] = {
        "type": "mapping" if isinstance(value, Mapping) else "sequence",
        "sha256": sha256_bytes(canonical.encode("utf-8")),
    }
    if isinstance(value, Mapping | Sequence) and not isinstance(value, str | bytes):
        summary["count"] = len(value)
    return summary


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
        _deduplicate_facility_projections(prepared.records),
        operation=request.operation,
        now=now,
    )
    artifact = _stabilize_equivalent_artifact_provenance(connection, artifact)
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
        prior = tuple(
            (row for row in existing if row["entity_type"] == entity_type),
        )
        semantic_fields: tuple[str, ...] = ()
        if entity_type == "allegation":
            semantic_fields = (
                "allegation_text",
                "allegation_category",
                "finding",
                "extraction_confidence",
            )
        _preserve_sequence_stable_identities(
            items,
            prior,
            id_field,
            semantic_fields=semantic_fields,
        )
        for item in items:
            item["complaint_id"] = complaint_id
    prior_audits: dict[str, list[Mapping[str, Any]]] = {}
    for row in sorted(
        (row for row in existing if row["entity_type"] == "extraction_audit"),
        key=lambda row: str(row["stable_source_id"]),
    ):
        field_name = str(
            cast(Mapping[str, Any], row["original_values"]).get("field_name")
        )
        prior_audits.setdefault(field_name, []).append(row)
    audits = cast(list[dict[str, Any]], normalized.get("extraction_audit", []))
    audits_by_field: dict[str, list[dict[str, Any]]] = {}
    for audit in audits:
        audit["document_id"] = document_id
        field_name = str(audit.get("field_name") or "")
        audits_by_field.setdefault(field_name, []).append(audit)
    for field_name, field_audits in audits_by_field.items():
        assigned_indexes = _preserve_sequence_stable_identities(
            field_audits,
            prior_audits.get(field_name, ()),
            "audit_id",
        )
        for index, audit in enumerate(field_audits):
            if index in assigned_indexes:
                continue
            if str(audit.get("audit_id", "")).startswith(old_document_id):
                audit["audit_id"] = (
                    document_id
                    + str(audit["audit_id"])[len(old_document_id) :]
                )


def _preserve_sequence_stable_identities(
    items: Sequence[dict[str, Any]],
    prior_rows: Sequence[Mapping[str, Any]],
    id_field: str,
    *,
    semantic_fields: Sequence[str] = (),
) -> set[int]:
    """Reuse stable child IDs without letting mixed ID formats reorder siblings."""

    available = {
        str(row["stable_source_id"]): row
        for row in prior_rows
    }
    assignments: dict[int, str] = {}

    if semantic_fields:
        stable_ids_by_semantics: dict[str, list[str]] = {}
        for stable_id, row in sorted(available.items()):
            values = cast(Mapping[str, Any], row["original_values"])
            signature = _semantic_identity_signature(values, semantic_fields)
            stable_ids_by_semantics.setdefault(signature, []).append(stable_id)
        for index, item in enumerate(items):
            signature = _semantic_identity_signature(item, semantic_fields)
            matching_ids = stable_ids_by_semantics.get(signature, [])
            while matching_ids and matching_ids[0] not in available:
                matching_ids.pop(0)
            if not matching_ids:
                continue
            stable_id = matching_ids.pop(0)
            assignments[index] = stable_id
            available.pop(stable_id)

    for index, item in enumerate(items):
        if index in assignments:
            continue
        generated_id = str(item.get(id_field) or "")
        if generated_id in available:
            assignments[index] = generated_id
            available.pop(generated_id)

    for index, _item in enumerate(items, start=1):
        item_index = index - 1
        if item_index in assignments:
            continue
        ordinal_matches = [
            stable_id
            for stable_id in sorted(available)
            if _stable_identity_ordinal(stable_id) == index
        ]
        if len(ordinal_matches) == 1:
            assignments[item_index] = ordinal_matches[0]
            available.pop(ordinal_matches[0])

    for item_index, stable_id in zip(
        (index for index in range(len(items)) if index not in assignments),
        sorted(available),
        strict=False,
    ):
        assignments[item_index] = stable_id

    for index, stable_id in assignments.items():
        items[index][id_field] = stable_id
    if semantic_fields:
        used_ids = set(assignments.values())
        for index, item in enumerate(items):
            if index in assignments:
                continue
            generated_id = str(item.get(id_field) or "")
            if generated_id in used_ids:
                generated_id = _next_sequence_stable_identity(
                    generated_id,
                    used_ids,
                )
                item[id_field] = generated_id
            used_ids.add(generated_id)
    return set(assignments)


def _semantic_identity_signature(
    values: Mapping[str, Any],
    fields: Sequence[str],
) -> str:
    return json.dumps(
        {field: values.get(field) for field in fields},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _next_sequence_stable_identity(
    generated_id: str,
    used_ids: set[str],
) -> str:
    match = re.fullmatch(r"(.*?)(\d+)", generated_id)
    if match is None:
        raise ValueError("Generated child stable identity must end in an ordinal.")
    prefix = match.group(1)
    used_ordinals = {
        int(candidate_match.group(1))
        for candidate in used_ids
        if (
            candidate_match := re.fullmatch(
                re.escape(prefix) + r"(\d+)",
                candidate,
            )
        )
    }
    next_ordinal = max(used_ordinals, default=0) + 1
    candidate = f"{prefix}{next_ordinal}"
    while candidate in used_ids:
        next_ordinal += 1
        candidate = f"{prefix}{next_ordinal}"
    return candidate


def _stable_identity_ordinal(stable_id: str) -> int | None:
    matches = _IDENTITY_ORDINAL_PATTERN.findall(stable_id)
    return int(matches[-1]) if matches else None


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


def _deduplicate_facility_projections(
    records: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    """Emit each stable facility once while retaining every document bundle.

    A facility with multiple preserved reports produces one normalized bundle per
    source document. Flattening every bundle would upsert the same facility key
    repeatedly with different document-level traceability, so an unchanged run
    could count intermediate writes even though its final state was identical.
    Keeping the last projection preserves the importer's prior final-write result.
    """

    last_index_by_facility_id: dict[str, int] = {}
    for index, record in enumerate(records):
        facility = record.get("facility")
        if isinstance(facility, Mapping):
            last_index_by_facility_id[
                _required_text(facility.get("facility_id"), "facility_id")
            ] = index

    result: list[Mapping[str, Any]] = []
    for index, record in enumerate(records):
        facility = record.get("facility")
        if not isinstance(facility, Mapping):
            result.append(record)
            continue
        facility_id = _required_text(facility.get("facility_id"), "facility_id")
        if last_index_by_facility_id[facility_id] == index:
            result.append(record)
            continue
        without_duplicate_facility = dict(record)
        without_duplicate_facility.pop("facility", None)
        without_duplicate_facility.pop("hosted_refresh", None)
        result.append(without_duplicate_facility)
    return tuple(result)


def _selected_facilities(
    connection: Connection,
    request: CcldHostedBackfillRequest,
) -> tuple[
    tuple[tuple[str, Mapping[str, Any]], ...],
    int,
    int,
    int,
]:
    rows = tuple(
        dict(row)
        for row in connection.execute(
            select(hosted_source_derived_records)
            .where(hosted_source_derived_records.c.entity_type == "facility")
            .order_by(hosted_source_derived_records.c.stable_source_id)
        ).mappings()
    )
    requested = set(request.facility_numbers)
    candidates_by_number: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        values = cast(Mapping[str, Any], row["original_values"])
        facility_number = _optional_text(values.get("external_facility_number"))
        if facility_number is None:
            continue
        if request.all_existing or facility_number in requested:
            candidates_by_number.setdefault(facility_number, []).append(row)
    selected = tuple(
        (facility_number, candidates[0])
        for facility_number, candidates in sorted(candidates_by_number.items())
        if len(candidates) == 1
    )
    ambiguous_count = sum(
        len(candidates) > 1 for candidates in candidates_by_number.values()
    )
    missing_count = 0 if request.all_existing else len(requested - candidates_by_number.keys())
    return selected, len(candidates_by_number), ambiguous_count, missing_count


def _backfill_artifact(
    facility_number: str,
    records: Sequence[Mapping[str, Any]],
    *,
    operation: BackfillOperation,
    now: datetime,
) -> SeededCorpusArtifact:
    fingerprint_source = json.dumps(records, sort_keys=True, separators=(",", ":"), default=str)
    fingerprint = sha256_bytes(fingerprint_source.encode("utf-8"))
    identity_operation = _source_artifact_identity_operation(operation)
    return SeededCorpusArtifact(
        import_batch_id=f"ccld-backfill-{fingerprint[:32]}",
        imported_at=now.replace(microsecond=0).isoformat(),
        source_artifact_identity=(
            f"preserved-ccld-backfill:{identity_operation}:{facility_number}:"
            f"{fingerprint[:16]}"
        ),
        source_pipeline_version="governed-ccld-hosted-refresh-1.0.0",
        validation_status="validated",
        raw_hash_validation_status="validated",
        record_counts=_record_counts(records),
        warnings=(),
        errors=(),
        records=tuple(records),
    )


def _stabilize_equivalent_artifact_provenance(
    connection: Connection,
    artifact: SeededCorpusArtifact,
) -> SeededCorpusArtifact:
    """Reuse provenance only when the complete persisted source state is equivalent."""

    records = _deduplicate_source_record_projections(flatten_seeded_corpus_records(artifact))
    facility_ids = {record.facility_id for record in records if record.facility_id}
    if len(facility_ids) != 1:
        return artifact
    existing_rows = tuple(
        dict(row)
        for row in connection.execute(
            select(hosted_source_derived_records).where(
                hosted_source_derived_records.c.facility_id == next(iter(facility_ids))
            )
        ).mappings()
    )
    existing_by_key = {str(row["source_record_key"]): row for row in existing_rows}
    if set(existing_by_key) != {record.source_record_key for record in records}:
        return artifact

    persisted_identities: set[str] = set()
    for record in records:
        existing = existing_by_key[record.source_record_key]
        values, _conflicts = _prepared_source_record_values(
            connection,
            record,
            existing,
            preserve_existing_import_batch=True,
        )
        existing_comparable = _without_artifact_identity(existing, values)
        prepared_comparable = _without_artifact_identity(values, values)
        if existing_comparable != prepared_comparable:
            return artifact
        traceability = cast(Mapping[str, Any], existing["source_traceability"])
        persisted_identity = _optional_text(traceability.get("source_artifact_identity"))
        if persisted_identity is None:
            return artifact
        persisted_identities.add(persisted_identity)
    if len(persisted_identities) != 1:
        return artifact

    persisted_identity = next(iter(persisted_identities))
    import_batch_ids = tuple(
        str(value)
        for value in connection.execute(
            select(hosted_import_batches.c.import_batch_id).where(
                hosted_import_batches.c.source_artifact_identity == persisted_identity
            )
        ).scalars()
    )
    if len(import_batch_ids) != 1:
        return artifact
    return replace(
        artifact,
        import_batch_id=import_batch_ids[0],
        source_artifact_identity=persisted_identity,
    )


def _without_artifact_identity(
    row: Mapping[str, Any],
    comparable_fields: Mapping[str, Any],
) -> Mapping[str, Any]:
    comparable = {key: row.get(key) for key in comparable_fields}
    traceability = comparable.get("source_traceability")
    if isinstance(traceability, Mapping):
        stable_traceability = dict(traceability)
        stable_traceability.pop("source_artifact_identity", None)
        comparable["source_traceability"] = stable_traceability
    return comparable


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
    if request.operation not in {
        "all",
        "facility-reference",
        "preserved-artifacts",
        "canonical-complaint-observations",
    }:
        raise ValueError("Unsupported CCLD hosted backfill operation.")
    if request.batch_size < 1 or request.batch_size > 1000:
        raise ValueError("batch_size must be between 1 and 1000.")
    if request.all_existing == bool(request.facility_numbers):
        raise ValueError("Select either all existing facilities or explicit facility numbers.")
    if any(not value.isdigit() for value in request.facility_numbers):
        raise ValueError("Facility numbers must contain digits only.")
    if request.restart and request.checkpoint_file is None:
        raise ValueError("restart requires a checkpoint file.")
    if request.max_facilities is not None and not 1 <= request.max_facilities <= 1000:
        raise ValueError("max_facilities must be between 1 and 1000.")
    if request.apply_changes and request.checkpoint_file is None:
        raise ValueError("apply requires a durable checkpoint file.")
    if request.apply_changes and request.max_facilities is None:
        raise ValueError("apply requires an explicit max_facilities bound.")
    if request.apply_changes and request.operation not in {
        "facility-reference",
        "preserved-artifacts",
        "canonical-complaint-observations",
    }:
        raise ValueError(
            "apply supports only the approved facility-reference canonical allocation, "
            "preserved-artifact normalization, or historical complaint-observation "
            "canonical allocation."
        )


def _load_checkpoint(request: CcldHostedBackfillRequest) -> _BackfillCheckpoint | None:
    path = request.checkpoint_file
    if path is None or request.restart or not path.exists():
        return None
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict) or loaded.get("version") != 2:
        raise ValueError("Backfill checkpoint is not valid.")
    if loaded.get("operation") != request.operation:
        raise ValueError("Backfill checkpoint operation does not match the request.")
    selector = loaded.get("request_selector")
    if selector != _checkpoint_request_selector(request):
        raise ValueError("Backfill checkpoint selection does not match the request.")
    selected = loaded.get("selected_facility_numbers")
    completed = loaded.get("completed_facility_numbers")
    failed = loaded.get("failed_attempts")
    if (
        not isinstance(selected, list)
        or not isinstance(completed, list)
        or not isinstance(failed, dict)
        or any(not isinstance(value, str) or not value.isdigit() for value in selected)
        or any(not isinstance(value, str) or value not in selected for value in completed)
        or any(
            not isinstance(key, str)
            or key not in selected
            or not isinstance(value, int)
            or value < 1
            for key, value in failed.items()
        )
    ):
        raise ValueError("Backfill checkpoint is not valid.")
    return _BackfillCheckpoint(
        selected_facility_numbers=tuple(selected),
        completed_facility_numbers=set(completed),
        failed_attempts=dict(failed),
    )


def _write_checkpoint(
    request: CcldHostedBackfillRequest,
    checkpoint: _BackfillCheckpoint,
) -> None:
    path = request.checkpoint_file
    if path is None:
        raise ValueError("Apply-mode backfill requires a durable checkpoint file.")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        {
            "version": 2,
            "operation": request.operation,
            "request_selector": _checkpoint_request_selector(request),
            "selected_facility_numbers": list(checkpoint.selected_facility_numbers),
            "completed_facility_numbers": sorted(
                checkpoint.completed_facility_numbers
            ),
            "failed_attempts": dict(sorted(checkpoint.failed_attempts.items())),
        },
        indent=2,
        sort_keys=True,
    )
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            temporary.write(payload + "\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, path)
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)


def _checkpoint_request_selector(request: CcldHostedBackfillRequest) -> list[str]:
    return ["all_existing"] if request.all_existing else sorted(request.facility_numbers)


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
    return operation in {
        "all",
        "preserved-artifacts",
        "canonical-complaint-observations",
    }


def _source_artifact_identity_operation(
    operation: BackfillOperation,
) -> BackfillOperation:
    """Use one provenance identity for equivalent preserved-document replays."""

    if operation == "canonical-complaint-observations":
        return "preserved-artifacts"
    return operation


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
