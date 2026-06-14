from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy import Select, and_, select
from sqlalchemy.engine import Connection, RowMapping

from ccld_complaints.hosted_app.seeded_import import (
    SourceDerivedEntityType,
    hosted_import_batches,
    hosted_source_derived_records,
)


@dataclass(frozen=True)
class ImportBatchRead:
    import_batch_id: str
    imported_at: str
    source_artifact_identity: str
    source_pipeline_version: str | None
    validation_status: str
    raw_hash_validation_status: str
    record_counts: Mapping[str, int]
    warnings: tuple[str, ...]
    errors: tuple[str, ...]


@dataclass(frozen=True)
class SourceDerivedRecordRead:
    source_record_key: str
    entity_type: SourceDerivedEntityType
    stable_source_id: str
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
    import_batch: ImportBatchRead


def list_source_derived_records(
    connection: Connection,
    *,
    entity_type: SourceDerivedEntityType | None = None,
    import_batch_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[SourceDerivedRecordRead, ...]:
    if limit < 1:
        raise ValueError("Source-derived record list limit must be at least 1.")
    if offset < 0:
        raise ValueError("Source-derived record list offset must be at least 0.")

    query = _source_derived_read_query()
    filters = []
    if entity_type is not None:
        filters.append(hosted_source_derived_records.c.entity_type == entity_type)
    if import_batch_id is not None:
        filters.append(hosted_source_derived_records.c.import_batch_id == import_batch_id)
    if filters:
        query = query.where(and_(*filters))
    query = query.order_by(
        hosted_source_derived_records.c.entity_type,
        hosted_source_derived_records.c.stable_source_id,
    ).limit(limit).offset(offset)

    return tuple(
        _read_model_from_row(row) for row in connection.execute(query).mappings().all()
    )


def get_source_derived_record_by_key(
    connection: Connection,
    source_record_key: str,
) -> SourceDerivedRecordRead | None:
    row = connection.execute(
        _source_derived_read_query().where(
            hosted_source_derived_records.c.source_record_key == source_record_key
        )
    ).mappings().first()
    if row is None:
        return None
    return _read_model_from_row(row)


def get_source_derived_record_by_identity(
    connection: Connection,
    *,
    entity_type: SourceDerivedEntityType,
    stable_source_id: str,
) -> SourceDerivedRecordRead | None:
    row = connection.execute(
        _source_derived_read_query().where(
            hosted_source_derived_records.c.entity_type == entity_type,
            hosted_source_derived_records.c.stable_source_id == stable_source_id,
        )
    ).mappings().first()
    if row is None:
        return None
    return _read_model_from_row(row)


def _source_derived_read_query() -> Select[tuple[Any, ...]]:
    return select(
        hosted_source_derived_records.c.source_record_key,
        hosted_source_derived_records.c.entity_type,
        hosted_source_derived_records.c.stable_source_id,
        hosted_source_derived_records.c.source_document_id,
        hosted_source_derived_records.c.facility_id,
        hosted_source_derived_records.c.source_url,
        hosted_source_derived_records.c.raw_sha256,
        hosted_source_derived_records.c.raw_path,
        hosted_source_derived_records.c.connector_name,
        hosted_source_derived_records.c.connector_version,
        hosted_source_derived_records.c.retrieved_at,
        hosted_source_derived_records.c.original_values,
        hosted_source_derived_records.c.source_traceability,
        hosted_import_batches.c.import_batch_id.label("batch_import_batch_id"),
        hosted_import_batches.c.imported_at.label("batch_imported_at"),
        hosted_import_batches.c.source_artifact_identity.label(
            "batch_source_artifact_identity"
        ),
        hosted_import_batches.c.source_pipeline_version.label(
            "batch_source_pipeline_version"
        ),
        hosted_import_batches.c.validation_status.label("batch_validation_status"),
        hosted_import_batches.c.raw_hash_validation_status.label(
            "batch_raw_hash_validation_status"
        ),
        hosted_import_batches.c.record_counts.label("batch_record_counts"),
        hosted_import_batches.c.warnings.label("batch_warnings"),
        hosted_import_batches.c.errors.label("batch_errors"),
    ).join(
        hosted_import_batches,
        hosted_import_batches.c.import_batch_id
        == hosted_source_derived_records.c.import_batch_id,
    )


def _read_model_from_row(row: RowMapping) -> SourceDerivedRecordRead:
    return SourceDerivedRecordRead(
        source_record_key=_string_value(row, "source_record_key"),
        entity_type=_entity_type(row),
        stable_source_id=_string_value(row, "stable_source_id"),
        source_document_id=_string_value(row, "source_document_id"),
        facility_id=_optional_string_value(row, "facility_id"),
        source_url=_string_value(row, "source_url"),
        raw_sha256=_string_value(row, "raw_sha256"),
        raw_path=_optional_string_value(row, "raw_path"),
        connector_name=_string_value(row, "connector_name"),
        connector_version=_string_value(row, "connector_version"),
        retrieved_at=_string_value(row, "retrieved_at"),
        original_values=_mapping_value(row, "original_values"),
        source_traceability=_mapping_value(row, "source_traceability"),
        import_batch=ImportBatchRead(
            import_batch_id=_string_value(row, "batch_import_batch_id"),
            imported_at=_string_value(row, "batch_imported_at"),
            source_artifact_identity=_string_value(
                row, "batch_source_artifact_identity"
            ),
            source_pipeline_version=_optional_string_value(
                row, "batch_source_pipeline_version"
            ),
            validation_status=_string_value(row, "batch_validation_status"),
            raw_hash_validation_status=_string_value(
                row, "batch_raw_hash_validation_status"
            ),
            record_counts=_int_mapping_value(row, "batch_record_counts"),
            warnings=_string_tuple_value(row, "batch_warnings"),
            errors=_string_tuple_value(row, "batch_errors"),
        ),
    )


def _entity_type(row: RowMapping) -> SourceDerivedEntityType:
    value = _string_value(row, "entity_type")
    if value not in (
        "facility",
        "source_document",
        "complaint",
        "allegation",
        "event",
        "extraction_audit",
    ):
        raise ValueError(f"Unknown source-derived entity type: {value}")
    return cast(SourceDerivedEntityType, value)


def _string_value(row: RowMapping, key: str) -> str:
    value = row[key]
    if not isinstance(value, str):
        raise TypeError(f"Expected {key} to be a string.")
    return value


def _optional_string_value(row: RowMapping, key: str) -> str | None:
    value = row[key]
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"Expected {key} to be a string or null.")
    return value


def _mapping_value(row: RowMapping, key: str) -> Mapping[str, Any]:
    value = row[key]
    if not isinstance(value, Mapping):
        raise TypeError(f"Expected {key} to be an object.")
    return dict(value)


def _int_mapping_value(row: RowMapping, key: str) -> Mapping[str, int]:
    value = row[key]
    if not isinstance(value, Mapping):
        raise TypeError(f"Expected {key} to be an object.")
    counts: dict[str, int] = {}
    for count_key, count_value in value.items():
        if not isinstance(count_key, str) or not isinstance(count_value, int):
            raise TypeError(f"Expected {key} to map strings to integers.")
        counts[count_key] = count_value
    return counts


def _string_tuple_value(row: RowMapping, key: str) -> tuple[str, ...]:
    value = row[key]
    if not isinstance(value, list):
        raise TypeError(f"Expected {key} to be a list.")
    strings: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise TypeError(f"Expected {key} to contain strings.")
        strings.append(item)
    return tuple(strings)