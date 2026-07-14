from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any, cast
from urllib.parse import parse_qs, urlparse

from sqlalchemy import Integer, Select, String, and_, case, func, literal, or_, select
from sqlalchemy import cast as sql_cast
from sqlalchemy.engine import Connection, RowMapping
from sqlalchemy.sql.selectable import CompoundSelect

from ccld_complaints.aggregate_results import AggregateResult, build_aggregate_result
from ccld_complaints.hosted_app.seeded_import import (
    SourceDerivedEntityType,
    hosted_import_batches,
    hosted_source_derived_records,
)
from ccld_complaints.presentation_values import (
    PresentationValue,
    presentation_values_for_record,
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

    @property
    def original_value_presentations(self) -> Mapping[str, PresentationValue]:
        return presentation_values_for_record(self.entity_type, self.original_values)


@dataclass(frozen=True)
class CcldSourceDerivedRequestLookup:
    matched_records: tuple[SourceDerivedRecordRead, ...]
    matched_complaint_keys: tuple[str, ...]
    all_facility_records: tuple[SourceDerivedRecordRead, ...]


@dataclass(frozen=True)
class SourceDerivedRecordListResult:
    records: tuple[SourceDerivedRecordRead, ...]
    aggregate: AggregateResult
    offset: int


@dataclass(frozen=True)
class SourceDerivedComplaintBundleResult:
    records: tuple[SourceDerivedRecordRead, ...]
    related_records: tuple[SourceDerivedRecordRead, ...]
    aggregate: AggregateResult


CCLD_CONNECTOR_NAME = "ccld_facility_reports"
CCLD_REVIEW_DATE_FIELDS = (
    "complaint_received_date",
    "first_investigation_activity_date",
    "visit_date",
    "report_date",
    "date_signed",
)


def list_source_derived_records(
    connection: Connection,
    *,
    entity_type: SourceDerivedEntityType | None = None,
    entity_types: tuple[SourceDerivedEntityType, ...] | None = None,
    import_batch_id: str | None = None,
    import_batch_ids: tuple[str, ...] | None = None,
    import_batch_query: Select[Any] | CompoundSelect[Any] | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[SourceDerivedRecordRead, ...]:
    if limit is not None and limit < 1:
        raise ValueError("Source-derived record list limit must be at least 1.")
    if offset < 0:
        raise ValueError("Source-derived record list offset must be at least 0.")
    if sum(
        value is not None
        for value in (import_batch_id, import_batch_ids, import_batch_query)
    ) > 1:
        raise ValueError(
            "Source-derived record list accepts one import batch filter mode."
        )
    if entity_type is not None and entity_types is not None:
        raise ValueError("Source-derived record list accepts one entity filter mode.")

    query = _source_derived_read_query()
    filters = _source_derived_filters(
        entity_type=entity_type,
        entity_types=entity_types,
        import_batch_id=import_batch_id,
        import_batch_ids=import_batch_ids,
        import_batch_query=import_batch_query,
    )
    if filters is None:
        return ()
    if filters:
        query = query.where(and_(*filters))
    query = query.order_by(
        hosted_source_derived_records.c.entity_type,
        hosted_source_derived_records.c.stable_source_id,
    )
    if limit is not None:
        query = query.limit(limit)
    if offset:
        query = query.offset(offset)

    return tuple(
        _read_model_from_row(row) for row in connection.execute(query).mappings().all()
    )


def list_source_derived_record_result(
    connection: Connection,
    *,
    entity_type: SourceDerivedEntityType | None = None,
    entity_types: tuple[SourceDerivedEntityType, ...] | None = None,
    import_batch_id: str | None = None,
    import_batch_ids: tuple[str, ...] | None = None,
    import_batch_query: Select[Any] | CompoundSelect[Any] | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> SourceDerivedRecordListResult:
    records = list_source_derived_records(
        connection,
        entity_type=entity_type,
        entity_types=entity_types,
        import_batch_id=import_batch_id,
        import_batch_ids=import_batch_ids,
        import_batch_query=import_batch_query,
        limit=limit,
        offset=offset,
    )
    filters = _source_derived_filters(
        entity_type=entity_type,
        entity_types=entity_types,
        import_batch_id=import_batch_id,
        import_batch_ids=import_batch_ids,
        import_batch_query=import_batch_query,
    )
    if filters is None:
        eligible_count = 0
    else:
        count_query = select(func.count()).select_from(hosted_source_derived_records)
        if filters:
            count_query = count_query.where(and_(*filters))
        eligible_count = int(connection.execute(count_query).scalar_one())
    returned_count = len(records)
    visible_eligible_count = max(eligible_count - offset, 0)
    aggregate = build_aggregate_result(
        value=returned_count,
        denominator=(
            "authorized source-derived records matching the active entity and import filters"
        ),
        eligible_count=visible_eligible_count,
        returned_count=returned_count,
        source_coverage_count=visible_eligible_count,
        source_unavailable_count=0,
        filtered_count=offset,
        limit=limit,
        date_dimension="any_review_date",
    )
    return SourceDerivedRecordListResult(records=records, aggregate=aggregate, offset=offset)


def list_source_derived_records_by_entity_types(
    connection: Connection,
    *,
    entity_types: tuple[SourceDerivedEntityType, ...],
    import_batch_id: str | None = None,
    import_batch_ids: tuple[str, ...] | None = None,
    import_batch_query: Select[Any] | CompoundSelect[Any] | None = None,
) -> tuple[SourceDerivedRecordRead, ...]:
    if sum(
        value is not None
        for value in (import_batch_id, import_batch_ids, import_batch_query)
    ) > 1:
        raise ValueError(
            "Source-derived record list accepts one import batch filter mode."
        )
    if not entity_types:
        return ()

    query = _source_derived_read_query().where(
        hosted_source_derived_records.c.entity_type.in_(entity_types)
    )
    if import_batch_id is not None:
        query = query.where(hosted_source_derived_records.c.import_batch_id == import_batch_id)
    if import_batch_ids is not None:
        if not import_batch_ids:
            return ()
        query = query.where(hosted_source_derived_records.c.import_batch_id.in_(import_batch_ids))
    if import_batch_query is not None:
        query = query.where(
            hosted_source_derived_records.c.import_batch_id.in_(import_batch_query)
        )
    query = query.order_by(
        hosted_source_derived_records.c.entity_type,
        hosted_source_derived_records.c.stable_source_id,
    )
    return tuple(
        _read_model_from_row(row) for row in connection.execute(query).mappings().all()
    )


def list_source_derived_complaint_bundle(
    connection: Connection,
    *,
    import_batch_id: str | None = None,
    import_batch_ids: tuple[str, ...] | None = None,
    import_batch_query: Select[Any] | CompoundSelect[Any] | None = None,
    facility_number: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    date_dimension: str = "any_review_date",
    search_query: str | None = None,
    limit: int | None = None,
) -> SourceDerivedComplaintBundleResult:
    """Read one deterministic complaint page and only its supporting source rows."""
    if limit is not None and limit < 1:
        raise ValueError("Source-derived complaint bundle limit must be at least 1.")
    if sum(
        value is not None
        for value in (import_batch_id, import_batch_ids, import_batch_query)
    ) > 1:
        raise ValueError(
            "Source-derived complaint bundle accepts one import batch filter mode."
        )
    parsed_start = _optional_iso_date(start_date, "start_date")
    parsed_end = _optional_iso_date(end_date, "end_date")
    if parsed_start is not None and parsed_end is not None and parsed_end < parsed_start:
        raise ValueError("end_date must not be before start_date.")

    complaint_filters = [hosted_source_derived_records.c.entity_type == "complaint"]
    import_filters = _source_derived_filters(
        entity_type=None,
        entity_types=None,
        import_batch_id=import_batch_id,
        import_batch_ids=import_batch_ids,
        import_batch_query=import_batch_query,
    )
    if import_filters is None:
        return _empty_complaint_bundle(
            limit=limit,
            start_date=start_date,
            end_date=end_date,
            date_dimension=date_dimension,
        )
    complaint_filters.extend(import_filters)
    if facility_number is not None and facility_number.strip():
        complaint_filters.append(_complaint_facility_filter(facility_number))
    selected_date = _selected_complaint_date_expression(
        date_dimension,
        dialect_name=connection.dialect.name,
    )
    if parsed_start is not None:
        complaint_filters.append(selected_date >= parsed_start.isoformat())
    if parsed_end is not None:
        complaint_filters.append(selected_date <= parsed_end.isoformat())
    normalized_search = " ".join((search_query or "").casefold().split())
    if normalized_search:
        complaint_filters.append(_complaint_search_filter(normalized_search))

    eligible_count = int(
        connection.execute(
            select(func.count()).select_from(hosted_source_derived_records).where(
                and_(*complaint_filters)
            )
        ).scalar_one()
    )
    selected_keys_query = (
        select(
            hosted_source_derived_records.c.source_record_key.label(
                "source_record_key"
            )
        )
        .where(and_(*complaint_filters))
        .order_by(
            hosted_source_derived_records.c.stable_source_id,
            hosted_source_derived_records.c.source_record_key,
        )
    )
    if limit is not None:
        selected_keys_query = selected_keys_query.limit(limit)
    selected_keys = selected_keys_query.cte("selected_source_derived_complaints")

    records = tuple(
        _read_model_from_row(row)
        for row in connection.execute(
            _source_derived_read_query()
            .where(
                hosted_source_derived_records.c.source_record_key.in_(
                    select(selected_keys.c.source_record_key)
                )
            )
            .order_by(
                hosted_source_derived_records.c.stable_source_id,
                hosted_source_derived_records.c.source_record_key,
            )
        )
        .mappings()
        .all()
    )

    selected_documents = (
        select(hosted_source_derived_records.c.source_document_id)
        .where(
            hosted_source_derived_records.c.source_record_key.in_(
                select(selected_keys.c.source_record_key)
            )
        )
    )
    selected_facilities = (
        select(hosted_source_derived_records.c.facility_id)
        .where(
            hosted_source_derived_records.c.source_record_key.in_(
                select(selected_keys.c.source_record_key)
            ),
            hosted_source_derived_records.c.facility_id.is_not(None),
        )
    )
    related_filters = _source_derived_filters(
        entity_type=None,
        entity_types=None,
        import_batch_id=import_batch_id,
        import_batch_ids=import_batch_ids,
        import_batch_query=import_batch_query,
    )
    if related_filters is None:
        related_records: tuple[SourceDerivedRecordRead, ...] = ()
    else:
        related_query = _source_derived_read_query().where(
            *related_filters,
            hosted_source_derived_records.c.entity_type.in_(
                ("facility", "source_document", "complaint", "allegation", "event")
            ),
            or_(
                hosted_source_derived_records.c.source_record_key.in_(
                    select(selected_keys.c.source_record_key)
                ),
                hosted_source_derived_records.c.source_document_id.in_(
                    selected_documents
                ),
                and_(
                    hosted_source_derived_records.c.entity_type == "facility",
                    hosted_source_derived_records.c.facility_id.in_(
                        selected_facilities
                    ),
                ),
            ),
        ).order_by(
            hosted_source_derived_records.c.entity_type,
            hosted_source_derived_records.c.stable_source_id,
            hosted_source_derived_records.c.source_record_key,
        )
        related_records = tuple(
            _read_model_from_row(row)
            for row in connection.execute(related_query).mappings().all()
        )

    returned_count = len(records)
    aggregate = build_aggregate_result(
        value=returned_count,
        denominator="authorized source-derived complaint records matching the active filters",
        eligible_count=eligible_count,
        returned_count=returned_count,
        source_coverage_count=sum(bool(record.source_url) for record in records),
        source_unavailable_count=sum(not record.source_url for record in records),
        limit=limit,
        date_dimension=date_dimension,
        query_start=start_date,
        query_end=end_date,
    )
    return SourceDerivedComplaintBundleResult(
        records=records,
        related_records=related_records,
        aggregate=aggregate,
    )


def find_ccld_source_derived_records_for_request(
    connection: Connection,
    *,
    facility_number: str,
    start_date: str | None = None,
    end_date: str | None = None,
    date_dimension: str = "any_review_date",
    import_batch_id: str | None = None,
) -> CcldSourceDerivedRequestLookup:
    requested_facility = _normalized_facility_number(facility_number)
    if requested_facility is None:
        raise ValueError("facility_number must contain digits only for CCLD lookup.")
    parsed_start = _optional_iso_date(start_date, "start_date")
    parsed_end = _optional_iso_date(end_date, "end_date")
    if parsed_start is not None and parsed_end is not None and parsed_end < parsed_start:
        raise ValueError("end_date must not be before start_date.")

    records = _list_ccld_source_derived_records(
        connection,
        import_batch_id=import_batch_id,
    )
    facility_records = tuple(
        record
        for record in records
        if _ccld_record_matches_facility(record, requested_facility)
    )
    matching_complaints = tuple(
        record
        for record in facility_records
        if record.entity_type == "complaint"
        and _ccld_record_matches_date_range(
            record,
            start_date=parsed_start,
            end_date=parsed_end,
            date_dimension=date_dimension,
        )
    )
    matched_complaint_keys = tuple(record.source_record_key for record in matching_complaints)
    if parsed_start is None and parsed_end is None:
        matched_records = facility_records
    elif matching_complaints:
        document_ids = {record.source_document_id for record in matching_complaints}
        facility_ids = {
            record.facility_id
            for record in matching_complaints
            if record.facility_id is not None
        }
        matched_records = tuple(
            record
            for record in facility_records
            if record.source_document_id in document_ids
            or (
                record.entity_type == "facility"
                and record.facility_id in facility_ids
            )
        )
    else:
        matched_records = ()

    return CcldSourceDerivedRequestLookup(
        matched_records=_sort_source_derived_reads(matched_records),
        matched_complaint_keys=matched_complaint_keys,
        all_facility_records=_sort_source_derived_reads(facility_records),
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


def _list_ccld_source_derived_records(
    connection: Connection,
    *,
    import_batch_id: str | None,
) -> tuple[SourceDerivedRecordRead, ...]:
    query = _source_derived_read_query().where(
        hosted_source_derived_records.c.connector_name == CCLD_CONNECTOR_NAME
    )
    if import_batch_id is not None:
        query = query.where(hosted_source_derived_records.c.import_batch_id == import_batch_id)
    query = query.order_by(
        hosted_source_derived_records.c.entity_type,
        hosted_source_derived_records.c.stable_source_id,
    )
    return tuple(
        _read_model_from_row(row) for row in connection.execute(query).mappings().all()
    )


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


def _ccld_record_matches_facility(
    record: SourceDerivedRecordRead,
    requested_facility_number: str,
) -> bool:
    original_values = record.original_values
    candidate_values = (
        original_values.get("external_facility_number"),
        original_values.get("facility_number"),
        original_values.get("facility_id"),
        record.facility_id,
        record.stable_source_id if record.entity_type == "facility" else None,
    )
    if any(
        _normalized_facility_number(value) == requested_facility_number
        for value in candidate_values
    ):
        return True
    return _facility_number_from_source_url(record.source_url) == requested_facility_number


def _ccld_record_matches_date_range(
    record: SourceDerivedRecordRead,
    *,
    start_date: date | None,
    end_date: date | None,
    date_dimension: str,
) -> bool:
    record_dates = _ccld_record_dates(record, date_dimension=date_dimension)
    if start_date is None and end_date is None:
        return True
    return any(
        (start_date is None or record_date >= start_date)
        and (end_date is None or record_date <= end_date)
        for record_date in record_dates
    )


def _ccld_record_dates(
    record: SourceDerivedRecordRead,
    *,
    date_dimension: str = "any_review_date",
) -> tuple[date, ...]:
    if date_dimension != "any_review_date" and date_dimension not in CCLD_REVIEW_DATE_FIELDS:
        allowed = ", ".join(("any_review_date", *CCLD_REVIEW_DATE_FIELDS))
        raise ValueError(f"date_dimension must be one of: {allowed}.")
    dates: list[date] = []
    field_names = (
        CCLD_REVIEW_DATE_FIELDS
        if date_dimension == "any_review_date"
        else (date_dimension,)
    )
    for field_name in field_names:
        value = record.original_values.get(field_name)
        if isinstance(value, str):
            parsed = _parse_iso_date(value[:10])
            if parsed is not None:
                dates.append(parsed)
    return tuple(dates)


def _source_derived_filters(
    *,
    entity_type: SourceDerivedEntityType | None,
    entity_types: tuple[SourceDerivedEntityType, ...] | None,
    import_batch_id: str | None,
    import_batch_ids: tuple[str, ...] | None,
    import_batch_query: Select[Any] | CompoundSelect[Any] | None,
) -> list[Any] | None:
    filters: list[Any] = []
    if entity_type is not None:
        filters.append(hosted_source_derived_records.c.entity_type == entity_type)
    if entity_types is not None:
        if not entity_types:
            return None
        filters.append(hosted_source_derived_records.c.entity_type.in_(entity_types))
    if import_batch_id is not None:
        filters.append(hosted_source_derived_records.c.import_batch_id == import_batch_id)
    if import_batch_ids is not None:
        if not import_batch_ids:
            return None
        filters.append(hosted_source_derived_records.c.import_batch_id.in_(import_batch_ids))
    if import_batch_query is not None:
        filters.append(
            hosted_source_derived_records.c.import_batch_id.in_(import_batch_query)
        )
    return filters


def _empty_complaint_bundle(
    *,
    limit: int | None,
    start_date: str | None,
    end_date: str | None,
    date_dimension: str,
) -> SourceDerivedComplaintBundleResult:
    return SourceDerivedComplaintBundleResult(
        records=(),
        related_records=(),
        aggregate=build_aggregate_result(
            value=0,
            denominator="authorized source-derived complaint records matching the active filters",
            eligible_count=0,
            returned_count=0,
            source_coverage_count=0,
            source_unavailable_count=0,
            limit=limit,
            date_dimension=date_dimension,
            query_start=start_date,
            query_end=end_date,
        ),
    )


def _complaint_facility_filter(facility_number: str) -> Any:
    normalized = facility_number.strip()
    if not normalized:
        raise ValueError("facility_number must not be blank.")
    return or_(
        hosted_source_derived_records.c.original_values[
            "external_facility_number"
        ].as_string()
        == normalized,
        hosted_source_derived_records.c.original_values[
            "facility_number"
        ].as_string()
        == normalized,
        hosted_source_derived_records.c.facility_id.like(
            f"%{_escaped_like_value(normalized)}",
            escape="\\",
        ),
        hosted_source_derived_records.c.source_url.like(
            f"%facNum={_escaped_like_value(normalized)}%",
            escape="\\",
        ),
    )


def _complaint_search_filter(search_query: str) -> Any:
    pattern = f"%{_escaped_like_value(search_query)}%"
    values = (
        hosted_source_derived_records.c.source_record_key,
        hosted_source_derived_records.c.stable_source_id,
        hosted_source_derived_records.c.facility_id,
        hosted_source_derived_records.c.original_values[
            "complaint_control_number"
        ].as_string(),
        hosted_source_derived_records.c.original_values["finding"].as_string(),
        hosted_source_derived_records.c.source_document_id,
    )
    return or_(
        *(
            func.lower(sql_cast(value, String)).like(pattern, escape="\\")
            for value in values
        )
    )


def _escaped_like_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _selected_complaint_date_expression(
    date_dimension: str,
    *,
    dialect_name: str,
) -> Any:
    field_names: tuple[str, ...]
    if date_dimension in {"any_review_date", "latest_supported_activity"}:
        field_names = CCLD_REVIEW_DATE_FIELDS
    elif date_dimension in CCLD_REVIEW_DATE_FIELDS:
        field_names = (date_dimension,)
    else:
        allowed = ", ".join(
            ("any_review_date", "latest_supported_activity", *CCLD_REVIEW_DATE_FIELDS)
        )
        raise ValueError(f"date_dimension must be one of: {allowed}.")

    valid_dates = tuple(
        _validated_date_expression(field_name, dialect_name=dialect_name)
        for field_name in field_names
    )
    if len(valid_dates) == 1:
        return func.nullif(valid_dates[0], "")
    latest = (
        func.greatest(*valid_dates)
        if dialect_name == "postgresql"
        else func.max(*valid_dates)
    )
    return func.nullif(latest, "")


def _validated_date_expression(field_name: str, *, dialect_name: str) -> Any:
    raw_value = func.substr(
        hosted_source_derived_records.c.original_values[field_name].as_string(),
        1,
        10,
    )
    shape_is_valid = (
        raw_value.op("~")(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
        if dialect_name == "postgresql"
        else raw_value.op("GLOB")(
            "[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]"
        )
    )
    numeric_year = sql_cast(
        case((shape_is_valid, func.substr(raw_value, 1, 4)), else_="0"),
        Integer,
    )
    numeric_month = sql_cast(
        case((shape_is_valid, func.substr(raw_value, 6, 2)), else_="0"),
        Integer,
    )
    numeric_day = sql_cast(
        case((shape_is_valid, func.substr(raw_value, 9, 2)), else_="0"),
        Integer,
    )
    is_leap_year = or_(
        numeric_year % 400 == 0,
        and_(numeric_year % 4 == 0, numeric_year % 100 != 0),
    )
    days_in_month = case(
        (numeric_month.in_((4, 6, 9, 11)), 30),
        (numeric_month == 2, case((is_leap_year, 29), else_=28)),
        else_=31,
    )
    return case(
        (
            and_(
                shape_is_valid,
                numeric_month.between(1, 12),
                numeric_day.between(1, days_in_month),
            ),
            raw_value,
        ),
        else_=literal(""),
    )


def _normalized_facility_number(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return text
    suffix = text.rsplit(":", 1)[-1].strip()
    if suffix.isdigit():
        return suffix
    return None


def _facility_number_from_source_url(source_url: str) -> str | None:
    parsed = urlparse(source_url)
    query_values = parse_qs(parsed.query, keep_blank_values=True)
    for key, values in query_values.items():
        if key.casefold() in {"facnum", "facilitynumber"}:
            for value in values:
                normalized = _normalized_facility_number(value)
                if normalized is not None:
                    return normalized
    path_leaf = parsed.path.rstrip("/").rsplit("/", 1)[-1]
    return _normalized_facility_number(path_leaf)


def _optional_iso_date(value: str | None, field_name: str) -> date | None:
    if value is None or not value.strip():
        return None
    parsed = _parse_iso_date(value)
    if parsed is None:
        raise ValueError(f"{field_name} must use YYYY-MM-DD format.")
    return parsed


def _parse_iso_date(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _sort_source_derived_reads(
    records: tuple[SourceDerivedRecordRead, ...],
) -> tuple[SourceDerivedRecordRead, ...]:
    return tuple(
        sorted(
            records,
            key=lambda record: (
                _entity_sort_key(record.entity_type),
                record.stable_source_id,
            ),
        )
    )


def _entity_sort_key(entity_type: SourceDerivedEntityType) -> int:
    order = {
        "facility": 0,
        "source_document": 1,
        "complaint": 2,
        "allegation": 3,
        "event": 4,
        "extraction_audit": 5,
    }
    return order.get(entity_type, 99)


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
