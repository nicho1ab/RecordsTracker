from __future__ import annotations

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
) -> SeededCorpusImportResult:
    flattened_records = flatten_seeded_corpus_records(artifact)
    _upsert_batch(connection, artifact)

    counts_by_entity: dict[str, int] = {
        entity_type: 0 for entity_type in SOURCE_DERIVED_ENTITY_TYPES
    }
    for record in flattened_records:
        _upsert_source_record(connection, record)
        counts_by_entity[record.entity_type] += 1

    return SeededCorpusImportResult(
        import_batch_id=artifact.import_batch_id,
        imported_record_count=len(flattened_records),
        imported_counts_by_entity=counts_by_entity,
    )


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
        records.append(
            _seeded_record(
                artifact,
                "facility",
                facility,
                source_document_traceability,
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


def _upsert_source_record(connection: Connection, record: SeededSourceDerivedRecord) -> None:
    values = {
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
    exists = connection.execute(
        select(hosted_source_derived_records.c.source_record_key).where(
            hosted_source_derived_records.c.source_record_key == record.source_record_key
        )
    ).first()
    if exists is None:
        connection.execute(hosted_source_derived_records.insert().values(**values))
    else:
        connection.execute(
            update(hosted_source_derived_records)
            .where(hosted_source_derived_records.c.source_record_key == record.source_record_key)
            .values(**values)
        )


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