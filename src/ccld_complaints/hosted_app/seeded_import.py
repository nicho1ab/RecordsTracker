from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    ForeignKey,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    select,
    update,
)
from sqlalchemy.engine import Connection

SourceDerivedEntityType = Literal[
    "facility",
    "source_document",
    "complaint",
    "allegation",
    "event",
    "extraction_audit",
]

SOURCE_DERIVED_ENTITY_TYPES: tuple[SourceDerivedEntityType, ...] = (
    "facility",
    "source_document",
    "complaint",
    "allegation",
    "event",
    "extraction_audit",
)

ENTITY_ID_FIELDS: Mapping[SourceDerivedEntityType, str] = {
    "facility": "facility_id",
    "source_document": "document_id",
    "complaint": "complaint_id",
    "allegation": "allegation_id",
    "event": "event_id",
    "extraction_audit": "audit_id",
}

FACILITY_CANONICAL_FIELDS = frozenset(
    {
        "facility_id",
        "source_id",
        "external_facility_number",
        "facility_name",
        "facility_type",
        "licensee_name",
        "county",
        "status",
        "capacity",
        "regional_office",
    }
)

COMPLAINT_REFRESH_FIELDS = frozenset(
    {
        "agency_name",
        "deficiency_texts",
        "investigation_findings_narrative",
        "complaint_report_contact",
        "complaint_control_number",
        "complaint_received_date",
        "first_investigation_activity_date",
        "visit_date",
        "report_date",
        "date_signed",
        "finding",
        "days_received_to_first_activity",
        "days_received_to_visit",
        "days_received_to_report",
        "days_report_to_signed",
        "review_delay_over_30_days",
        "review_delay_over_60_days",
        "review_delay_over_90_days",
        "review_delay_over_120_days",
        "missing_first_activity_date",
        "report_date_used_as_proxy",
    }
)
FINGERPRINTED_COMPLAINT_REFRESH_FIELDS = frozenset(
    {
        "agency_name",
        "deficiency_texts",
        "investigation_findings_narrative",
        "complaint_report_contact",
    }
)

RAW_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")

hosted_seeded_import_metadata = MetaData()

hosted_import_batches = Table(
    "hosted_import_batches",
    hosted_seeded_import_metadata,
    Column("import_batch_id", String(96), primary_key=True),
    Column("imported_at", String(40), nullable=False),
    Column("source_artifact_identity", Text, nullable=False),
    Column("source_pipeline_version", Text, nullable=True),
    Column("validation_status", String(32), nullable=False),
    Column("raw_hash_validation_status", String(32), nullable=False),
    Column("record_counts", JSON, nullable=False),
    Column("warnings", JSON, nullable=False),
    Column("errors", JSON, nullable=False),
    CheckConstraint(
        "validation_status = 'validated'",
        name="ck_hosted_import_batches_validation_status",
    ),
    CheckConstraint(
        "raw_hash_validation_status = 'validated'",
        name="ck_hosted_import_batches_raw_hash_validation_status",
    ),
)

hosted_source_derived_records = Table(
    "hosted_source_derived_records",
    hosted_seeded_import_metadata,
    Column("source_record_key", String(160), primary_key=True),
    Column("entity_type", String(32), nullable=False),
    Column("stable_source_id", Text, nullable=False),
    Column("import_batch_id", String(96), ForeignKey("hosted_import_batches.import_batch_id")),
    Column("source_document_id", Text, nullable=False),
    Column("facility_id", Text, nullable=True),
    Column("source_url", Text, nullable=False),
    Column("raw_sha256", String(64), nullable=False),
    Column("raw_path", Text, nullable=True),
    Column("connector_name", Text, nullable=False),
    Column("connector_version", Text, nullable=False),
    Column("retrieved_at", String(40), nullable=False),
    Column("agency_name", Text, nullable=True),
    Column("deficiency_texts", JSON, nullable=True),
    Column("investigation_findings_narrative", Text, nullable=True),
    Column("complaint_report_contact", Text, nullable=True),
    Column("original_values", JSON, nullable=False),
    Column("source_traceability", JSON, nullable=False),
    UniqueConstraint(
        "entity_type",
        "stable_source_id",
        name="uq_hosted_source_derived_records_stable_identity",
    ),
    CheckConstraint(
        "entity_type IN "
        "('facility', 'source_document', 'complaint', 'allegation', 'event', "
        "'extraction_audit')",
        name="ck_hosted_source_derived_records_entity_type",
    ),
)


@dataclass(frozen=True)
class SeededCorpusArtifact:
    import_batch_id: str
    imported_at: str
    source_artifact_identity: str
    source_pipeline_version: str | None
    validation_status: str
    raw_hash_validation_status: str
    record_counts: Mapping[str, int]
    warnings: tuple[str, ...]
    errors: tuple[str, ...]
    records: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True)
class SeededSourceDerivedRecord:
    entity_type: SourceDerivedEntityType
    stable_source_id: str
    import_batch_id: str
    source_document_id: str
    facility_id: str | None
    source_url: str
    raw_sha256: str
    raw_path: str | None
    connector_name: str
    connector_version: str
    retrieved_at: str
    original_values: Mapping[str, Any]
    source_traceability: Mapping[str, Any]

    @property
    def source_record_key(self) -> str:
        return f"{self.entity_type}:{self.stable_source_id}"


@dataclass(frozen=True)
class SeededCorpusImportResult:
    import_batch_id: str
    imported_record_count: int
    imported_counts_by_entity: Mapping[str, int]
    reviewer_created_state_written: bool = False
    inserted_record_count: int = 0
    updated_record_count: int = 0
    unchanged_record_count: int = 0
    conflicted_field_count: int = 0


def hosted_seeded_import_tables() -> tuple[Table, Table]:
    return hosted_import_batches, hosted_source_derived_records


def load_seeded_corpus_artifact(path: Path) -> SeededCorpusArtifact:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("Seeded corpus artifact must be a JSON object.")
    return parse_seeded_corpus_artifact(cast(Mapping[str, Any], loaded))


def parse_seeded_corpus_artifact(data: Mapping[str, Any]) -> SeededCorpusArtifact:
    validation_status = _required_str(data, "validation_status")
    if validation_status != "validated":
        raise ValueError("Seeded corpus artifact validation_status must be 'validated'.")

    raw_hash_validation_status = _required_str(data, "raw_hash_validation_status")
    if raw_hash_validation_status != "validated":
        raise ValueError(
            "Seeded corpus artifact raw_hash_validation_status must be 'validated'."
        )

    errors = _string_tuple(data.get("errors", ()), "errors")
    if errors:
        raise ValueError("Seeded corpus artifact must not contain validation errors.")

    return SeededCorpusArtifact(
        import_batch_id=_required_str(data, "import_batch_id"),
        imported_at=_required_str(data, "imported_at"),
        source_artifact_identity=_required_str(data, "source_artifact_identity"),
        source_pipeline_version=_optional_str(data, "source_pipeline_version"),
        validation_status=validation_status,
        raw_hash_validation_status=raw_hash_validation_status,
        record_counts=_record_counts(data.get("record_counts")),
        warnings=_string_tuple(data.get("warnings", ()), "warnings"),
        errors=errors,
        records=_record_tuple(data.get("records")),
    )


def flatten_seeded_corpus_records(
    artifact: SeededCorpusArtifact,
) -> tuple[SeededSourceDerivedRecord, ...]:
    flattened: list[SeededSourceDerivedRecord] = []
    for normalized_record in artifact.records:
        flattened.extend(_flatten_normalized_record(artifact, normalized_record))
    return tuple(flattened)


def import_seeded_corpus_artifact(
    connection: Connection,
    artifact: SeededCorpusArtifact,
    *,
    preserve_existing_import_batch: bool = False,
) -> SeededCorpusImportResult:
    flattened_records = flatten_seeded_corpus_records(artifact)
    _upsert_batch(connection, artifact)

    inserted = 0
    updated = 0
    unchanged = 0
    conflicted = 0
    for record in flattened_records:
        operation, conflict_count = _upsert_source_record(
            connection,
            record,
            preserve_existing_import_batch=preserve_existing_import_batch,
        )
        conflicted += conflict_count
        if operation == "inserted":
            inserted += 1
        elif operation == "updated":
            updated += 1
        else:
            unchanged += 1

    persisted_counts_by_entity = _unique_persisted_counts_by_entity(flattened_records)

    return SeededCorpusImportResult(
        import_batch_id=artifact.import_batch_id,
        imported_record_count=sum(persisted_counts_by_entity.values()),
        imported_counts_by_entity=persisted_counts_by_entity,
        inserted_record_count=inserted,
        updated_record_count=updated,
        unchanged_record_count=unchanged,
        conflicted_field_count=conflicted,
    )


def _unique_persisted_counts_by_entity(
    records: Sequence[SeededSourceDerivedRecord],
) -> Mapping[str, int]:
    counts_by_entity: dict[str, int] = {
        entity_type: 0 for entity_type in SOURCE_DERIVED_ENTITY_TYPES
    }
    seen_source_record_keys: set[str] = set()
    for record in records:
        if record.source_record_key in seen_source_record_keys:
            continue
        seen_source_record_keys.add(record.source_record_key)
        counts_by_entity[record.entity_type] += 1
    return counts_by_entity


def _flatten_normalized_record(
    artifact: SeededCorpusArtifact,
    normalized_record: Mapping[str, Any],
) -> tuple[SeededSourceDerivedRecord, ...]:
    source_document = _required_mapping(normalized_record, "source_document")
    source_document_traceability = _source_traceability(source_document)
    complaint = _optional_mapping(normalized_record, "complaint")
    records: list[SeededSourceDerivedRecord] = []

    facility = _optional_mapping(normalized_record, "facility")
    if facility is not None:
        facility_traceability = dict(source_document_traceability)
        refresh_context = _optional_mapping(normalized_record, "hosted_refresh")
        if refresh_context is not None:
            facility_traceability["hosted_refresh"] = dict(refresh_context)
        records.append(
            _seeded_record(
                artifact,
                "facility",
                facility,
                facility_traceability,
                _required_str_from_mapping(source_document, "document_id"),
                _required_str_from_mapping(facility, "facility_id"),
            )
        )

    records.append(
        _seeded_record(
            artifact,
            "source_document",
            source_document,
            source_document_traceability,
            _required_str_from_mapping(source_document, "document_id"),
            _optional_str_from_mapping(source_document, "facility_id"),
        )
    )

    if complaint is not None:
        complaint_document_id = _required_str_from_mapping(complaint, "document_id")
        records.append(
            _seeded_record(
                artifact,
                "complaint",
                complaint,
                source_document_traceability,
                complaint_document_id,
                _optional_str_from_mapping(complaint, "facility_id"),
            )
        )
        for allegation in _mapping_sequence(normalized_record.get("allegations"), "allegations"):
            records.append(
                _seeded_record(
                    artifact,
                    "allegation",
                    allegation,
                    source_document_traceability,
                    complaint_document_id,
                    _optional_str_from_mapping(complaint, "facility_id"),
                )
            )
        for event in _mapping_sequence(normalized_record.get("events"), "events"):
            records.append(
                _seeded_record(
                    artifact,
                    "event",
                    event,
                    source_document_traceability,
                    complaint_document_id,
                    _optional_str_from_mapping(complaint, "facility_id"),
                )
            )

    for audit_record in _mapping_sequence(
        normalized_record.get("extraction_audit"), "extraction_audit"
    ):
        records.append(
            _seeded_record(
                artifact,
                "extraction_audit",
                audit_record,
                source_document_traceability,
                _required_str_from_mapping(audit_record, "document_id"),
                _optional_str_from_mapping(source_document, "facility_id"),
            )
        )

    return tuple(records)


def _seeded_record(
    artifact: SeededCorpusArtifact,
    entity_type: SourceDerivedEntityType,
    original_values: Mapping[str, Any],
    traceability: Mapping[str, Any],
    source_document_id: str,
    facility_id: str | None,
) -> SeededSourceDerivedRecord:
    stable_source_id = _required_str_from_mapping(original_values, ENTITY_ID_FIELDS[entity_type])
    return SeededSourceDerivedRecord(
        entity_type=entity_type,
        stable_source_id=stable_source_id,
        import_batch_id=artifact.import_batch_id,
        source_document_id=source_document_id,
        facility_id=facility_id,
        source_url=_required_str_from_mapping(traceability, "source_url"),
        raw_sha256=_validated_raw_sha256(traceability),
        raw_path=_optional_str_from_mapping(traceability, "raw_path"),
        connector_name=_required_str_from_mapping(traceability, "connector_name"),
        connector_version=_required_str_from_mapping(traceability, "connector_version"),
        retrieved_at=_required_str_from_mapping(traceability, "retrieved_at"),
        original_values=dict(original_values),
        source_traceability={
            **dict(traceability),
            "source_artifact_identity": artifact.source_artifact_identity,
        },
    )


def _source_traceability(source_document: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "source_document_id": _required_str_from_mapping(source_document, "document_id"),
        "source_url": _required_str_from_mapping(source_document, "source_url"),
        "raw_sha256": _validated_raw_sha256(source_document),
        "raw_path": _optional_str_from_mapping(source_document, "raw_path"),
        "connector_name": _required_str_from_mapping(source_document, "connector_name"),
        "connector_version": _required_str_from_mapping(source_document, "connector_version"),
        "retrieved_at": _required_str_from_mapping(source_document, "retrieved_at"),
        "report_index": source_document.get("report_index"),
        "document_type": source_document.get("document_type"),
    }


def _upsert_batch(connection: Connection, artifact: SeededCorpusArtifact) -> None:
    values = {
        "import_batch_id": artifact.import_batch_id,
        "imported_at": artifact.imported_at,
        "source_artifact_identity": artifact.source_artifact_identity,
        "source_pipeline_version": artifact.source_pipeline_version,
        "validation_status": artifact.validation_status,
        "raw_hash_validation_status": artifact.raw_hash_validation_status,
        "record_counts": dict(artifact.record_counts),
        "warnings": list(artifact.warnings),
        "errors": list(artifact.errors),
    }
    exists = connection.execute(
        select(hosted_import_batches.c.import_batch_id).where(
            hosted_import_batches.c.import_batch_id == artifact.import_batch_id
        )
    ).first()
    if exists is None:
        connection.execute(hosted_import_batches.insert().values(**values))
    else:
        connection.execute(
            update(hosted_import_batches)
            .where(hosted_import_batches.c.import_batch_id == artifact.import_batch_id)
            .values(**values)
        )


def _upsert_source_record(
    connection: Connection,
    record: SeededSourceDerivedRecord,
    *,
    preserve_existing_import_batch: bool = False,
) -> tuple[str, int]:
    values: dict[str, Any] = {
        "source_record_key": record.source_record_key,
        "entity_type": record.entity_type,
        "stable_source_id": record.stable_source_id,
        "import_batch_id": record.import_batch_id,
        "source_document_id": record.source_document_id,
        "facility_id": record.facility_id,
        "source_url": record.source_url,
        "raw_sha256": record.raw_sha256,
        "raw_path": record.raw_path,
        "connector_name": record.connector_name,
        "connector_version": record.connector_version,
        "retrieved_at": record.retrieved_at,
        "original_values": dict(record.original_values),
        "source_traceability": dict(record.source_traceability),
    }
    existing = connection.execute(
        select(hosted_source_derived_records).where(
            hosted_source_derived_records.c.source_record_key == record.source_record_key
        )
    ).mappings().first()
    if existing is None:
        values.update(
            _canonical_complaint_observation_columns(
                record.entity_type,
                record.original_values,
            )
        )
        if preserve_existing_import_batch:
            values["import_batch_id"] = _existing_document_import_batch_id(
                connection,
                record.source_document_id,
                fallback=record.import_batch_id,
            )
        connection.execute(hosted_source_derived_records.insert().values(**values))
        return "inserted", 0
    else:
        if preserve_existing_import_batch:
            values["import_batch_id"] = existing["import_batch_id"]
        merged_original_values, conflicts = _merge_source_original_values(
            record.entity_type,
            existing.get("original_values"),
            record.original_values,
        )
        values["original_values"] = merged_original_values
        values.update(
            _canonical_complaint_observation_columns(
                record.entity_type,
                merged_original_values,
            )
        )
        values["source_traceability"] = _merge_source_traceability(
            existing.get("source_traceability"),
            record.source_traceability,
            conflicts,
        )
        comparable_existing = {key: existing.get(key) for key in values}
        if comparable_existing == values:
            return "unchanged", len(conflicts)
        connection.execute(
            update(hosted_source_derived_records)
            .where(hosted_source_derived_records.c.source_record_key == record.source_record_key)
            .values(**values)
        )
        return "updated", len(conflicts)


def _existing_document_import_batch_id(
    connection: Connection,
    source_document_id: str,
    *,
    fallback: str,
) -> str:
    value = connection.execute(
        select(hosted_source_derived_records.c.import_batch_id).where(
            hosted_source_derived_records.c.entity_type == "source_document",
            hosted_source_derived_records.c.stable_source_id == source_document_id,
        )
    ).scalar_one_or_none()
    return str(value) if value is not None else fallback


def _merge_source_original_values(
    entity_type: SourceDerivedEntityType,
    existing: object,
    incoming: Mapping[str, Any],
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    """Apply null-preserving refresh and trace governed nonblank conflicts.

    Complaint-report-owned fields use the newest successfully validated
    deterministic extraction. Facility master precedence is resolved before
    import, so a nonblank incoming canonical facility value is authoritative.
    """

    merged = dict(existing) if isinstance(existing, Mapping) else {}
    conflict_fields = (
        FACILITY_CANONICAL_FIELDS
        if entity_type == "facility"
        else COMPLAINT_REFRESH_FIELDS if entity_type == "complaint" else frozenset()
    )
    conflicts: list[dict[str, Any]] = []
    for key, value in incoming.items():
        if (
            _is_blank_refresh_field_value(key, value)
            and key in merged
            and not _is_blank_refresh_field_value(key, merged[key])
        ):
            continue
        if (
            key in conflict_fields
            and key in merged
            and not _is_blank_refresh_field_value(key, merged[key])
            and not _is_blank_refresh_field_value(key, value)
            and merged[key] != value
        ):
            conflicts.append(_refresh_conflict(key, merged[key], value))
        merged[key] = value
    return merged, tuple(conflicts)


def _canonical_complaint_observation_columns(
    entity_type: SourceDerivedEntityType,
    values: Mapping[str, Any],
) -> dict[str, object]:
    if entity_type != "complaint":
        return {}
    deficiency_texts = values.get("deficiency_texts")
    normalized_deficiencies: list[str] | None = None
    if isinstance(deficiency_texts, Sequence) and not isinstance(
        deficiency_texts, str | bytes
    ):
        normalized_deficiencies = [
            value for value in deficiency_texts if isinstance(value, str) and value.strip()
        ]
        if not normalized_deficiencies:
            normalized_deficiencies = None
    return {
        "agency_name": _canonical_historical_text(values.get("agency_name")),
        "deficiency_texts": normalized_deficiencies,
        "investigation_findings_narrative": _canonical_historical_text(
            values.get("investigation_findings_narrative")
        ),
        "complaint_report_contact": _canonical_historical_text(
            values.get("complaint_report_contact"),
            contact=True,
        ),
    }


def _canonical_historical_text(
    value: object,
    *,
    contact: bool = False,
) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split()).casefold().rstrip(".")
    placeholders = {"n/a", "na", "not available", "unavailable"}
    if contact:
        placeholders.add("see faqs")
    return value if normalized and normalized not in placeholders else None


def _refresh_conflict(
    field_name: str,
    previous_value: object,
    incoming_value: object,
) -> dict[str, Any]:
    conflict: dict[str, Any] = {
        "field_name": field_name,
        "resolution": "incoming_governed_source_precedence",
    }
    if field_name not in FINGERPRINTED_COMPLAINT_REFRESH_FIELDS:
        conflict["previous_value"] = previous_value
        conflict["incoming_value"] = incoming_value
        return conflict
    conflict["previous_value_sha256"] = _value_fingerprint(previous_value)
    conflict["incoming_value_sha256"] = _value_fingerprint(incoming_value)
    if isinstance(previous_value, Sequence) and not isinstance(
        previous_value, str | bytes
    ):
        conflict["previous_value_count"] = len(previous_value)
    if isinstance(incoming_value, Sequence) and not isinstance(
        incoming_value, str | bytes
    ):
        conflict["incoming_value_count"] = len(incoming_value)
    return conflict


def _value_fingerprint(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _merge_source_traceability(
    existing: object,
    incoming: Mapping[str, Any],
    conflicts: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    merged = dict(existing) if isinstance(existing, Mapping) else {}
    for key, value in incoming.items():
        if _is_blank_refresh_value(value) and key in merged:
            continue
        merged[key] = value
    prior_conflicts = merged.get("refresh_conflicts")
    conflict_rows = list(prior_conflicts) if isinstance(prior_conflicts, list) else []
    for conflict in conflicts:
        if conflict not in conflict_rows:
            conflict_rows.append(conflict)
    if conflict_rows:
        merged["refresh_conflicts"] = conflict_rows
    return merged


def _is_blank_refresh_value(value: object) -> bool:
    return (
        value is None
        or (isinstance(value, str) and not value.strip())
        or (
            isinstance(value, Sequence)
            and not isinstance(value, str | bytes)
            and len(value) == 0
        )
    )


def _is_blank_refresh_field_value(field_name: str, value: object) -> bool:
    if field_name == "deficiency_texts":
        return not (
            isinstance(value, Sequence)
            and not isinstance(value, str | bytes)
            and any(
                isinstance(item, str) and item.strip()
                for item in value
            )
        )
    if field_name in {
        "agency_name",
        "investigation_findings_narrative",
        "complaint_report_contact",
    }:
        return _canonical_historical_text(
            value,
            contact=field_name == "complaint_report_contact",
        ) is None
    return _is_blank_refresh_value(value)


def _required_mapping(data: Mapping[str, Any], field_name: str) -> Mapping[str, Any]:
    value = data.get(field_name)
    if not isinstance(value, Mapping):
        raise ValueError(f"Seeded corpus record must include object field {field_name!r}.")
    return cast(Mapping[str, Any], value)


def _optional_mapping(data: Mapping[str, Any], field_name: str) -> Mapping[str, Any] | None:
    value = data.get(field_name)
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError(f"Seeded corpus record field {field_name!r} must be an object.")
    return cast(Mapping[str, Any], value)


def _mapping_sequence(value: object, field_name: str) -> tuple[Mapping[str, Any], ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        raise ValueError(f"Seeded corpus record field {field_name!r} must be a list.")
    records: list[Mapping[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise ValueError(f"Seeded corpus record field {field_name!r} must contain objects.")
        records.append(cast(Mapping[str, Any], item))
    return tuple(records)


def _record_tuple(value: object) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        raise ValueError("Seeded corpus artifact must include records as a list.")
    records: list[Mapping[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise ValueError("Seeded corpus artifact records must contain objects.")
        records.append(cast(Mapping[str, Any], item))
    if not records:
        raise ValueError("Seeded corpus artifact must include at least one record.")
    return tuple(records)


def _record_counts(value: object) -> Mapping[str, int]:
    if not isinstance(value, Mapping):
        raise ValueError("Seeded corpus artifact must include record_counts.")
    counts: dict[str, int] = {}
    for key, count in value.items():
        if not isinstance(key, str) or not isinstance(count, int):
            raise ValueError("Seeded corpus artifact record_counts must map strings to integers.")
        counts[key] = count
    return counts


def _string_tuple(value: object, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        raise ValueError(f"Seeded corpus artifact {field_name} must be a list of strings.")
    strings: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"Seeded corpus artifact {field_name} must contain strings.")
        strings.append(item)
    return tuple(strings)


def _required_str(data: Mapping[str, Any], field_name: str) -> str:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Seeded corpus artifact must include string field {field_name!r}.")
    return value


def _optional_str(data: Mapping[str, Any], field_name: str) -> str | None:
    value = data.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"Seeded corpus artifact field {field_name!r} must be a string.")
    return value


def _required_str_from_mapping(data: Mapping[str, Any], field_name: str) -> str:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Source-derived record must include string field {field_name!r}.")
    return value


def _optional_str_from_mapping(data: Mapping[str, Any], field_name: str) -> str | None:
    value = data.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"Source-derived record field {field_name!r} must be a string.")
    return value


def _validated_raw_sha256(data: Mapping[str, Any]) -> str:
    raw_sha256 = _required_str_from_mapping(data, "raw_sha256")
    if RAW_SHA256_PATTERN.fullmatch(raw_sha256) is None:
        raise ValueError("Source-derived record raw_sha256 must be lowercase SHA-256 hex.")
    return raw_sha256
