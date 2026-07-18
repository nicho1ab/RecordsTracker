from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal, cast
from urllib.parse import parse_qs, urlparse

from sqlalchemy import (
    Integer,
    Select,
    String,
    and_,
    case,
    func,
    literal,
    or_,
    select,
    tuple_,
)
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


@dataclass(frozen=True)
class FacilityIntelligenceReadFilters:
    start_date: str | None = None
    end_date: str | None = None
    date_dimension: str = "complaint_received_date"
    facility_type: str = ""
    geography: str = ""
    finding: str = ""
    serious_topic: str = ""
    coverage: str = "all"
    sort: str = "priority"


@dataclass(frozen=True)
class FacilityIntelligenceSeek:
    direction: Literal["next", "previous"]
    anchor: tuple[int | str, ...]
    start_position: int
    expected_total: int


@dataclass(frozen=True)
class FacilityIntelligenceCursorAnchor:
    order_values: tuple[int | str, ...]
    start_position: int


@dataclass(frozen=True)
class FacilityIntelligenceFilterOptions:
    facility_types: tuple[str, ...] = ()
    geographies: tuple[str, ...] = ()
    findings: tuple[str, ...] = ()
    serious_topics: tuple[str, ...] = ()


@dataclass(frozen=True)
class FacilityIntelligencePageRead:
    records: tuple[SourceDerivedRecordRead, ...]
    facility_identities: tuple[str, ...]
    total_matching_facility_count: int
    total_authorized_facility_count: int
    first_position: int
    last_position: int
    previous_anchor: FacilityIntelligenceCursorAnchor | None
    next_anchor: FacilityIntelligenceCursorAnchor | None
    review_next_facility_identity: str | None
    filter_options: FacilityIntelligenceFilterOptions


CCLD_CONNECTOR_NAME = "ccld_facility_reports"
CCLD_REVIEW_DATE_FIELDS = (
    "complaint_received_date",
    "first_investigation_activity_date",
    "visit_date",
    "report_date",
    "date_signed",
)

FACILITY_INTELLIGENCE_PAGE_SIZE = 25
_FACILITY_INTELLIGENCE_OPTION_LIMIT = 250
_FACILITY_INTELLIGENCE_SERIOUS_CATEGORY_LABELS = {
    "abuse or mistreatment": "Mistreatment-topic",
    "neglect": "Care-omission topic",
    "inadequate supervision": "Supervision topic",
    "medication or medical care": "Medication/medical-care topic",
    "runaway or awol": "Runaway/AWOL topic",
    "staff conduct": "Staff-conduct topic",
}
_FACILITY_INTELLIGENCE_SERIOUS_CUE_TERMS = (
    "sexual assault",
    "abuse",
    "mistreatment",
    "neglect",
    "supervision",
    "unsupervised",
    "unattended",
    "medication",
    "medical care",
    "runaway",
    "awol",
    "staff misconduct",
    "injury",
    "restraint",
)
_FACILITY_INTELLIGENCE_SERIOUS_CUE_EXCLUSIONS = (
    "substance abuse",
    "abuse prevention",
    "injury prevention",
    "restraint policy",
    "restraint training",
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


def list_facility_intelligence_page(
    connection: Connection,
    *,
    filters: FacilityIntelligenceReadFilters,
    import_batch_id: str | None = None,
    import_batch_ids: tuple[str, ...] | None = None,
    import_batch_query: Select[Any] | CompoundSelect[Any] | None = None,
    seek: FacilityIntelligenceSeek | None = None,
) -> FacilityIntelligencePageRead:
    """Read one bounded facility page and only its contributing source rows."""
    if sum(
        value is not None
        for value in (import_batch_id, import_batch_ids, import_batch_query)
    ) > 1:
        raise ValueError(
            "Facility intelligence accepts one import batch filter mode."
        )
    if filters.coverage not in {"all", "available", "partial", "unavailable"}:
        raise ValueError("Facility intelligence coverage filter is not supported.")
    if filters.sort not in {
        "priority",
        "complaint_count",
        "recent_activity",
        "facility_name",
    }:
        raise ValueError("Facility intelligence sort is not supported.")
    parsed_start = _optional_iso_date(filters.start_date, "start_date")
    parsed_end = _optional_iso_date(filters.end_date, "end_date")
    if parsed_start is not None and parsed_end is not None and parsed_end < parsed_start:
        raise ValueError("end_date must not be before start_date.")

    facts = _facility_intelligence_complaint_facts(
        connection,
        filters=filters,
        import_batch_id=import_batch_id,
        import_batch_ids=import_batch_ids,
        import_batch_query=import_batch_query,
        apply_active_filters=True,
    )
    facilities = _facility_intelligence_facilities(facts, filters=filters)
    count_facts = _facility_intelligence_complaint_facts(
        connection,
        filters=filters,
        import_batch_id=import_batch_id,
        import_batch_ids=import_batch_ids,
        import_batch_query=import_batch_query,
        apply_active_filters=True,
        cte_name="facility_intelligence_count_facts",
        include_priority_signals=False,
        projection="count",
    )
    count_facilities = _facility_intelligence_count_facilities(
        count_facts,
        filters=filters,
    )
    has_active_filters = any(
        (
            filters.start_date is not None,
            filters.end_date is not None,
            bool(filters.facility_type.strip()),
            bool(filters.geography.strip()),
            bool(filters.finding.strip()),
            bool(filters.serious_topic),
            filters.coverage != "all",
        )
    )
    base_identity_facts = _facility_intelligence_complaint_facts(
        connection,
        filters=FacilityIntelligenceReadFilters(),
        import_batch_id=import_batch_id,
        import_batch_ids=import_batch_ids,
        import_batch_query=import_batch_query,
        apply_active_filters=False,
        cte_name="facility_intelligence_base_identity_facts",
        include_priority_signals=False,
        projection="identity",
    )
    matching_count = (
        select(func.count()).select_from(count_facilities).scalar_subquery()
    )
    total_statement = select(matching_count.label("matching_count"))
    if has_active_filters:
        total_statement = total_statement.add_columns(
            select(func.count(func.distinct(base_identity_facts.c.facility_identity)))
            .select_from(base_identity_facts)
            .scalar_subquery()
            .label("authorized_count")
        )
    totals = connection.execute(total_statement).mappings().one()
    total_matching = int(totals["matching_count"] or 0)
    total_authorized = (
        int(totals["authorized_count"] or 0)
        if has_active_filters
        else total_matching
    )

    order_columns, descending = _facility_intelligence_order_spec(
        facilities,
        filters.sort,
    )
    start_position = 1
    page_statement = select(facilities)
    reverse_results = False
    if seek is not None:
        if seek.expected_total != total_matching:
            raise ValueError("Facility intelligence continuation is stale.")
        if seek.direction not in {"next", "previous"}:
            raise ValueError("Facility intelligence continuation direction is invalid.")
        anchor_position = _facility_intelligence_anchor_position(
            connection,
            facilities,
            order_columns,
            descending,
            seek.anchor,
        )
        if seek.direction == "next":
            if anchor_position >= total_matching:
                raise ValueError("Facility intelligence continuation is stale.")
            derived_start_position = anchor_position + 1
        else:
            if anchor_position <= 1:
                raise ValueError("Facility intelligence continuation is stale.")
            derived_start_position = max(
                anchor_position - FACILITY_INTELLIGENCE_PAGE_SIZE,
                1,
            )
        if seek.start_position != derived_start_position:
            raise ValueError(
                "Facility intelligence continuation position does not match its anchor."
            )
        page_statement = page_statement.where(
            _facility_intelligence_seek_predicate(
                order_columns,
                descending,
                seek.anchor,
                direction=seek.direction,
            )
        )
        start_position = derived_start_position
        reverse_results = seek.direction == "previous"

    page_order = _facility_intelligence_order_clauses(
        order_columns,
        descending,
        reverse=reverse_results,
    )
    page_rows = list(
        connection.execute(
            _facility_intelligence_bounded_limit(
                page_statement.order_by(*page_order),
                FACILITY_INTELLIGENCE_PAGE_SIZE,
                dialect_name=connection.dialect.name,
            )
        ).mappings()
    )
    if reverse_results:
        page_rows.reverse()
    if seek is not None and total_matching and not page_rows:
        raise ValueError("Facility intelligence continuation is stale.")

    identities = tuple(str(row["facility_identity"]) for row in page_rows)
    records = _facility_intelligence_hydrated_records(
        connection,
        filters=filters,
        source_facility_ids=tuple(
            str(row["source_facility_id"])
            for row in page_rows
            if row["source_facility_id"] is not None
        ),
        facility_source_record_keys=tuple(
            str(row["facility_source_record_key"])
            for row in page_rows
            if row["facility_source_record_key"] is not None
        ),
        fallback_source_record_keys=tuple(
            str(row["representative_source_record_key"])
            for row in page_rows
            if row["source_facility_id"] is None
        ),
        import_batch_id=import_batch_id,
        import_batch_ids=import_batch_ids,
        import_batch_query=import_batch_query,
    )
    last_position = start_position + len(page_rows) - 1 if page_rows else 0
    previous_anchor = (
        FacilityIntelligenceCursorAnchor(
            order_values=_facility_intelligence_row_order_values(
                page_rows[0],
                order_columns,
            ),
            start_position=max(start_position - FACILITY_INTELLIGENCE_PAGE_SIZE, 1),
        )
        if page_rows and start_position > 1
        else None
    )
    next_anchor = (
        FacilityIntelligenceCursorAnchor(
            order_values=_facility_intelligence_row_order_values(
                page_rows[-1],
                order_columns,
            ),
            start_position=start_position + FACILITY_INTELLIGENCE_PAGE_SIZE,
        )
        if page_rows and last_position < total_matching
        else None
    )
    priority_columns, priority_descending = _facility_intelligence_order_spec(
        facilities,
        "priority",
    )
    review_next_identity = connection.execute(
        _facility_intelligence_bounded_limit(
            select(facilities.c.facility_identity).order_by(
            *_facility_intelligence_order_clauses(
                priority_columns,
                priority_descending,
            )
            ),
            1,
            dialect_name=connection.dialect.name,
        )
    ).scalar_one_or_none()
    return FacilityIntelligencePageRead(
        records=records,
        facility_identities=identities,
        total_matching_facility_count=total_matching,
        total_authorized_facility_count=total_authorized,
        first_position=start_position if page_rows else 0,
        last_position=last_position,
        previous_anchor=previous_anchor,
        next_anchor=next_anchor,
        review_next_facility_identity=(
            str(review_next_identity) if review_next_identity is not None else None
        ),
        filter_options=_facility_intelligence_filter_options(
            connection,
            import_batch_id=import_batch_id,
            import_batch_ids=import_batch_ids,
            import_batch_query=import_batch_query,
        ),
    )


def _facility_intelligence_complaint_facts(
    connection: Connection,
    *,
    filters: FacilityIntelligenceReadFilters,
    import_batch_id: str | None,
    import_batch_ids: tuple[str, ...] | None,
    import_batch_query: Select[Any] | CompoundSelect[Any] | None,
    apply_active_filters: bool,
    cte_name: str = "facility_intelligence_complaint_facts",
    include_priority_signals: bool = True,
    projection: Literal["full", "count", "hydration", "identity"] = "full",
    source_facility_ids: tuple[str, ...] = (),
    source_record_keys: tuple[str, ...] = (),
) -> Any:
    complaint = hosted_source_derived_records.alias(f"{cte_name}_complaint")
    facility = hosted_source_derived_records.alias(f"{cte_name}_facility")
    duplicate_complaint = hosted_source_derived_records.alias(
        f"{cte_name}_duplicate_complaint"
    )
    duplicate_facility = hosted_source_derived_records.alias(
        f"{cte_name}_duplicate_facility"
    )
    complaint_key_clauses = [
        duplicate_complaint.c.entity_type == "complaint",
        _facility_intelligence_import_filter(
            duplicate_complaint,
            import_batch_id=import_batch_id,
            import_batch_ids=import_batch_ids,
            import_batch_query=import_batch_query,
        ),
    ]
    if source_facility_ids or source_record_keys:
        complaint_key_clauses.append(
            or_(
                duplicate_complaint.c.facility_id.in_(source_facility_ids),
                duplicate_complaint.c.source_record_key.in_(source_record_keys),
            )
        )
    duplicate_complaint_id = func.coalesce(
        _json_text(duplicate_complaint, "complaint_id"),
        duplicate_complaint.c.stable_source_id,
    )
    complaint_keys = (
        select(
            duplicate_complaint_id.label("complaint_id"),
            func.min(duplicate_complaint.c.source_record_key).label(
                "source_record_key"
            ),
        )
        .where(and_(*complaint_key_clauses))
        .group_by(duplicate_complaint_id)
        .cte(f"{cte_name}_complaint_keys")
    )
    facility_keys = (
        select(
            duplicate_facility.c.import_batch_id,
            duplicate_facility.c.facility_id,
            func.min(duplicate_facility.c.source_record_key).label(
                "source_record_key"
            ),
        )
        .where(
            duplicate_facility.c.entity_type == "facility",
            duplicate_facility.c.facility_id.is_not(None),
            _facility_intelligence_import_filter(
                duplicate_facility,
                import_batch_id=import_batch_id,
                import_batch_ids=import_batch_ids,
                import_batch_query=import_batch_query,
            ),
        )
        .group_by(
            duplicate_facility.c.import_batch_id,
            duplicate_facility.c.facility_id,
        )
        .cte(f"{cte_name}_facility_keys")
    )
    facility_name = _first_nonblank_text(
        _json_text(facility, "facility_name"),
        _json_text(facility, "name"),
    )
    facility_original_identity = _first_nonblank_text(
        _json_text(facility, "facility_id"),
        _json_text(facility, "external_facility_number"),
        _json_text(facility, "facility_number"),
    )
    complaint_original_identity = _first_nonblank_text(
        _json_text(complaint, "facility_id"),
        _json_text(complaint, "external_facility_number"),
        _json_text(complaint, "facility_number"),
    )
    facility_identity = func.coalesce(
        facility_original_identity,
        func.nullif(func.trim(facility.c.facility_id), ""),
        func.nullif(func.trim(complaint.c.facility_id), ""),
        complaint_original_identity,
        literal("unknown:") + complaint.c.source_record_key,
    )
    facility_number = _first_nonblank_text(
        _json_text(facility, "external_facility_number"),
        _json_text(facility, "facility_number"),
        _json_text(facility, "license_number"),
        _json_text(complaint, "external_facility_number"),
        _json_text(complaint, "facility_number"),
        complaint.c.facility_id,
    )
    resolved_name = func.coalesce(
        facility_name,
        case(
            (
                facility_number.is_not(None),
                literal("Facility ID ") + facility_number,
            ),
            else_=literal("Unknown facility"),
        ),
    )
    source_facility_type = _first_nonblank_text(
        _json_text(facility, "facility_type"),
        _json_text(facility, "facility_type_description"),
        _json_text(facility, "type"),
    )
    facility_type = func.coalesce(
        source_facility_type,
        case(
            (
                func.lower(resolved_name).like("%foster family agency%"),
                literal("Foster Family Agency"),
            ),
            else_=literal("unknown"),
        ),
    )
    geography = _facility_intelligence_geography(facility)
    activity_date = _facility_intelligence_activity_date(
        complaint,
        filters.date_dimension,
        dialect_name=connection.dialect.name,
    )
    finding = func.coalesce(_json_text(complaint, "finding"), literal("unknown"))
    complaint_id = func.coalesce(
        _json_text(complaint, "complaint_id"),
        complaint.c.stable_source_id,
    )
    facts_from = (
        complaint.join(
            complaint_keys,
            complaint_keys.c.source_record_key == complaint.c.source_record_key,
        )
        .outerjoin(
            facility_keys,
            and_(
                facility_keys.c.import_batch_id == complaint.c.import_batch_id,
                facility_keys.c.facility_id == complaint.c.facility_id,
            ),
        )
        .outerjoin(
            facility,
            facility.c.source_record_key == facility_keys.c.source_record_key,
        )
    )
    substantiated: Any = literal(False)
    if include_priority_signals:
        related_substantiated = _facility_intelligence_related_substantiated(
            cte_name=cte_name,
            import_batch_id=import_batch_id,
            import_batch_ids=import_batch_ids,
            import_batch_query=import_batch_query,
        )
        facts_from = facts_from.outerjoin(
            related_substantiated,
            and_(
                related_substantiated.c.import_batch_id
                == complaint.c.import_batch_id,
                related_substantiated.c.complaint_id == complaint_id,
            ),
        )
        substantiated = or_(
            _substantiated_values_expression(complaint),
            related_substantiated.c.complaint_id.is_not(None),
        )
    strongest_delay = case(
        (_json_bool(complaint, "review_delay_over_120_days"), 120),
        (_json_bool(complaint, "review_delay_over_90_days"), 90),
        (_json_bool(complaint, "review_delay_over_60_days"), 60),
        (_json_bool(complaint, "review_delay_over_30_days"), 30),
        else_=0,
    )
    missing_dates = or_(
        _json_bool(complaint, "missing_first_activity_date"),
        _json_text(complaint, "visit_date").is_(None),
        _json_text(complaint, "report_date").is_(None),
        _json_text(complaint, "date_signed").is_(None),
    )
    normalized_source_url = func.lower(func.trim(complaint.c.source_url))
    source_available = and_(
        normalized_source_url != "",
        normalized_source_url.not_in(("unknown", "unavailable", "not available")),
    )
    serious_topic_match = _facility_intelligence_serious_topic_expression(
        complaint,
        complaint_id,
        filters.serious_topic,
    )
    where_clauses = [
        complaint.c.entity_type == "complaint",
        _facility_intelligence_import_filter(
            complaint,
            import_batch_id=import_batch_id,
            import_batch_ids=import_batch_ids,
            import_batch_query=import_batch_query,
        ),
    ]
    if source_facility_ids or source_record_keys:
        where_clauses.append(
            or_(
                complaint.c.facility_id.in_(source_facility_ids),
                complaint.c.source_record_key.in_(source_record_keys),
            )
        )
    if apply_active_filters:
        if filters.start_date is not None:
            where_clauses.append(activity_date >= filters.start_date)
        if filters.end_date is not None:
            where_clauses.append(activity_date <= filters.end_date)
        normalized_finding = " ".join(filters.finding.casefold().split())
        if normalized_finding:
            where_clauses.append(
                func.lower(func.trim(finding)) == normalized_finding
            )
        if filters.serious_topic:
            where_clauses.append(serious_topic_match)
        normalized_type = " ".join(filters.facility_type.casefold().split())
        if normalized_type:
            where_clauses.append(
                func.lower(func.trim(facility_type)).like(
                    f"%{_escaped_like_value(normalized_type)}%",
                    escape="\\",
                )
            )
        normalized_geography = " ".join(filters.geography.casefold().split())
        if normalized_geography:
            where_clauses.append(
                func.lower(func.trim(geography)).like(
                    f"%{_escaped_like_value(normalized_geography)}%",
                    escape="\\",
                )
            )
    if projection == "hydration":
        return (
            select(
                complaint.c.source_record_key.label("source_record_key"),
                complaint.c.source_document_id.label("source_document_id"),
                complaint.c.facility_id.label("source_facility_id"),
                facility.c.source_record_key.label("facility_source_record_key"),
                facility_identity.label("facility_identity"),
            )
            .select_from(facts_from)
            .where(and_(*where_clauses))
            .cte(cte_name)
        )
    if projection == "identity":
        return (
            select(
                complaint.c.import_batch_id.label("import_batch_id"),
                facility_identity.label("facility_identity"),
            )
            .select_from(facts_from)
            .where(and_(*where_clauses))
            .cte(cte_name)
        )
    if projection == "count":
        return (
            select(
                facility_identity.label("facility_identity"),
                case((source_available, 1), else_=0).label("source_available"),
            )
            .select_from(facts_from)
            .where(and_(*where_clauses))
            .cte(cte_name)
        )
    return (
        select(
            complaint.c.source_record_key.label("source_record_key"),
            complaint.c.stable_source_id.label("stable_complaint_id"),
            complaint.c.import_batch_id.label("import_batch_id"),
            complaint.c.source_document_id.label("source_document_id"),
            complaint.c.facility_id.label("source_facility_id"),
            facility.c.source_record_key.label("facility_source_record_key"),
            facility_identity.label("facility_identity"),
            facility_number.label("facility_number"),
            resolved_name.label("facility_name"),
            facility_type.label("facility_type"),
            geography.label("geography"),
            activity_date.label("activity_date"),
            finding.label("finding"),
            case((substantiated, 1), else_=0).label("substantiated"),
            strongest_delay.label("strongest_delay_days"),
            case((missing_dates, 1), else_=0).label("missing_dates"),
            case((source_available, 1), else_=0).label("source_available"),
        )
        .select_from(facts_from)
        .where(and_(*where_clauses))
        .cte(cte_name)
    )


def _facility_intelligence_facilities(
    facts: Any,
    *,
    filters: FacilityIntelligenceReadFilters,
) -> Any:
    complaint_count = func.count().label("complaint_count")
    substantiated_count = func.sum(facts.c.substantiated).label(
        "substantiated_count"
    )
    strongest_delay = func.max(facts.c.strongest_delay_days).label(
        "strongest_delay_days"
    )
    recent_activity = func.coalesce(
        func.max(facts.c.activity_date),
        "",
    ).label("recent_activity_date")
    source_available_count = func.sum(facts.c.source_available).label(
        "source_available_count"
    )
    statement = select(
        facts.c.facility_identity,
        func.max(facts.c.facility_number).label("facility_number"),
        func.max(facts.c.facility_name).label("facility_name"),
        func.lower(func.trim(func.max(facts.c.facility_name))).label(
            "normalized_facility_name"
        ),
        func.lower(func.trim(facts.c.facility_identity)).label(
            "normalized_facility_identity"
        ),
        func.max(facts.c.facility_type).label("facility_type"),
        func.max(facts.c.geography).label("geography"),
        func.min(facts.c.source_facility_id).label("source_facility_id"),
        func.min(facts.c.facility_source_record_key).label(
            "facility_source_record_key"
        ),
        func.min(facts.c.source_record_key).label(
            "representative_source_record_key"
        ),
        complaint_count,
        substantiated_count,
        strongest_delay,
        recent_activity,
        func.sum(facts.c.missing_dates).label("missing_date_count"),
        source_available_count,
    ).group_by(facts.c.facility_identity)
    if filters.coverage == "available":
        statement = statement.having(source_available_count == complaint_count)
    elif filters.coverage == "partial":
        statement = statement.having(
            source_available_count > 0,
            source_available_count < complaint_count,
        )
    elif filters.coverage == "unavailable":
        statement = statement.having(source_available_count == 0)
    return statement.cte("facility_intelligence_facilities")


def _facility_intelligence_count_facilities(
    facts: Any,
    *,
    filters: FacilityIntelligenceReadFilters,
) -> Any:
    complaint_count = func.count()
    source_available_count = func.sum(facts.c.source_available)
    statement = select(facts.c.facility_identity).group_by(
        facts.c.facility_identity
    )
    if filters.coverage == "available":
        statement = statement.having(source_available_count == complaint_count)
    elif filters.coverage == "partial":
        statement = statement.having(
            source_available_count > 0,
            source_available_count < complaint_count,
        )
    elif filters.coverage == "unavailable":
        statement = statement.having(source_available_count == 0)
    return statement.cte("facility_intelligence_count_facilities")


def _facility_intelligence_order_spec(
    facilities: Any,
    sort_value: str,
) -> tuple[tuple[Any, ...], tuple[bool, ...]]:
    normalized_name = facilities.c.normalized_facility_name
    normalized_identity = facilities.c.normalized_facility_identity
    if sort_value == "complaint_count":
        return (
            (
                facilities.c.complaint_count,
                normalized_name,
                normalized_identity,
            ),
            (True, False, False),
        )
    if sort_value == "recent_activity":
        return (
            (
                facilities.c.recent_activity_date,
                normalized_name,
                normalized_identity,
            ),
            (True, False, False),
        )
    if sort_value == "facility_name":
        return (
            (normalized_name, normalized_identity),
            (False, False),
        )
    return (
        (
            facilities.c.substantiated_count,
            facilities.c.complaint_count,
            facilities.c.strongest_delay_days,
            facilities.c.recent_activity_date,
            normalized_name,
            normalized_identity,
        ),
        (True, True, True, True, False, False),
    )


def _facility_intelligence_order_clauses(
    columns: Sequence[Any],
    descending: Sequence[bool],
    *,
    reverse: bool = False,
) -> tuple[Any, ...]:
    return tuple(
        column.asc()
        if is_descending == reverse
        else column.desc()
        for column, is_descending in zip(columns, descending, strict=True)
    )


def _facility_intelligence_seek_predicate(
    columns: Sequence[Any],
    descending: Sequence[bool],
    anchor: Sequence[int | str],
    *,
    direction: Literal["next", "previous"],
) -> Any:
    if len(columns) != len(anchor):
        raise ValueError("Facility intelligence continuation shape is invalid.")
    after = direction == "next"
    comparisons = []
    for index, (column, is_descending, value) in enumerate(
        zip(columns, descending, anchor, strict=True)
    ):
        seek_greater = after != is_descending
        comparison = column > value if seek_greater else column < value
        comparisons.append(
            and_(
                *(columns[prior] == anchor[prior] for prior in range(index)),
                comparison,
            )
        )
    return or_(*comparisons)


def _facility_intelligence_anchor_position(
    connection: Connection,
    facilities: Any,
    columns: Sequence[Any],
    descending: Sequence[bool],
    anchor: Sequence[int | str],
) -> int:
    if len(columns) != len(anchor):
        raise ValueError("Facility intelligence continuation shape is invalid.")
    exists_statement = (
        select(literal(1))
        .select_from(facilities)
        .where(
            and_(
                *(
                    column == value
                    for column, value in zip(columns, anchor, strict=True)
                )
            )
        )
    )
    exists = connection.execute(
        _facility_intelligence_bounded_limit(
            exists_statement,
            1,
            dialect_name=connection.dialect.name,
        )
    ).first()
    if exists is None:
        raise ValueError("Facility intelligence continuation is stale.")
    preceding_count = connection.execute(
        select(func.count())
        .select_from(facilities)
        .where(
            _facility_intelligence_seek_predicate(
                columns,
                descending,
                anchor,
                direction="previous",
            )
        )
    ).scalar_one()
    return int(preceding_count or 0) + 1


def _facility_intelligence_row_order_values(
    row: RowMapping,
    columns: Sequence[Any],
) -> tuple[int | str, ...]:
    values: list[int | str] = []
    for column in columns:
        value = row[column.key]
        if not isinstance(value, int | str):
            raise ValueError("Facility intelligence continuation value is invalid.")
        values.append(value)
    return tuple(values)


def _facility_intelligence_hydrated_records(
    connection: Connection,
    *,
    filters: FacilityIntelligenceReadFilters,
    source_facility_ids: tuple[str, ...],
    facility_source_record_keys: tuple[str, ...],
    fallback_source_record_keys: tuple[str, ...],
    import_batch_id: str | None,
    import_batch_ids: tuple[str, ...] | None,
    import_batch_query: Select[Any] | CompoundSelect[Any] | None,
) -> tuple[SourceDerivedRecordRead, ...]:
    if not source_facility_ids and not fallback_source_record_keys:
        return ()
    reference_facts = _facility_intelligence_complaint_facts(
        connection,
        filters=filters,
        import_batch_id=import_batch_id,
        import_batch_ids=import_batch_ids,
        import_batch_query=import_batch_query,
        apply_active_filters=True,
        cte_name="facility_intelligence_hydration_references",
        include_priority_signals=False,
        projection="hydration",
        source_facility_ids=source_facility_ids,
        source_record_keys=fallback_source_record_keys,
    )
    selected_complaints = connection.execute(
        select(
            reference_facts.c.source_record_key,
            reference_facts.c.source_document_id,
            reference_facts.c.source_facility_id,
        )
    ).mappings()
    selected_keys: list[str] = []
    selected_documents: set[str] = set()
    for row in selected_complaints:
        selected_keys.append(str(row["source_record_key"]))
        selected_documents.add(str(row["source_document_id"]))
    if not selected_keys:
        return ()
    related_filter = _facility_intelligence_import_filter(
        hosted_source_derived_records,
        import_batch_id=import_batch_id,
        import_batch_ids=import_batch_ids,
        import_batch_query=import_batch_query,
    )
    query = _source_derived_read_query().where(
        related_filter,
        or_(
            hosted_source_derived_records.c.source_record_key.in_(selected_keys),
            and_(
                hosted_source_derived_records.c.entity_type.in_(
                    ("source_document", "allegation", "event")
                ),
                hosted_source_derived_records.c.source_document_id.in_(
                    selected_documents,
                ),
            ),
            and_(
                hosted_source_derived_records.c.entity_type == "facility",
                hosted_source_derived_records.c.source_record_key.in_(
                    facility_source_record_keys,
                ),
            ),
        ),
    ).order_by(
        hosted_source_derived_records.c.entity_type,
        hosted_source_derived_records.c.stable_source_id,
        hosted_source_derived_records.c.source_record_key,
    )
    return tuple(
        _read_model_from_row(row)
        for row in connection.execute(query).mappings().all()
    )


def _facility_intelligence_filter_options(
    connection: Connection,
    *,
    import_batch_id: str | None,
    import_batch_ids: tuple[str, ...] | None,
    import_batch_query: Select[Any] | CompoundSelect[Any] | None,
) -> FacilityIntelligenceFilterOptions:
    def distinct_values(
        column: Any,
        from_clause: Any,
        *where_clauses: Any,
    ) -> tuple[str, ...]:
        statement = (
            select(column)
            .select_from(from_clause)
            .where(
                column.is_not(None),
                func.trim(column) != "",
                *where_clauses,
            )
            .group_by(column)
            .order_by(func.lower(column), column)
        )
        return tuple(
            str(value)
            for value in connection.execute(
                _facility_intelligence_bounded_limit(
                    statement,
                    _FACILITY_INTELLIGENCE_OPTION_LIMIT,
                    dialect_name=connection.dialect.name,
                )
            ).scalars()
        )

    complaint = hosted_source_derived_records.alias(
        "facility_intelligence_option_complaint"
    )
    facility = hosted_source_derived_records.alias(
        "facility_intelligence_option_facility"
    )
    duplicate_facility = hosted_source_derived_records.alias(
        "facility_intelligence_option_duplicate_facility"
    )
    complaint_facility_ids = (
        select(complaint.c.import_batch_id, complaint.c.facility_id)
        .where(
            complaint.c.entity_type == "complaint",
            complaint.c.facility_id.is_not(None),
            _facility_intelligence_import_filter(
                complaint,
                import_batch_id=import_batch_id,
                import_batch_ids=import_batch_ids,
                import_batch_query=import_batch_query,
            ),
        )
    )
    facility_keys = (
        select(
            duplicate_facility.c.import_batch_id,
            duplicate_facility.c.facility_id,
            func.min(duplicate_facility.c.source_record_key).label(
                "source_record_key"
            ),
        )
        .where(
            duplicate_facility.c.entity_type == "facility",
            tuple_(
                duplicate_facility.c.import_batch_id,
                duplicate_facility.c.facility_id,
            ).in_(
                complaint_facility_ids
            ),
            _facility_intelligence_import_filter(
                duplicate_facility,
                import_batch_id=import_batch_id,
                import_batch_ids=import_batch_ids,
                import_batch_query=import_batch_query,
            ),
        )
        .group_by(
            duplicate_facility.c.import_batch_id,
            duplicate_facility.c.facility_id,
        )
        .cte("facility_intelligence_option_facility_keys")
    )
    facility_options_from = facility_keys.join(
        facility,
        facility.c.source_record_key == facility_keys.c.source_record_key,
    )
    facility_name = _first_nonblank_text(
        _json_text(facility, "facility_name"),
        _json_text(facility, "name"),
    )
    facility_number = _first_nonblank_text(
        _json_text(facility, "external_facility_number"),
        _json_text(facility, "facility_number"),
        _json_text(facility, "license_number"),
        facility.c.facility_id,
    )
    resolved_name = func.coalesce(
        facility_name,
        case(
            (facility_number.is_not(None), literal("Facility ID ") + facility_number),
            else_=literal("Unknown facility"),
        ),
    )
    facility_type = func.coalesce(
        _first_nonblank_text(
            _json_text(facility, "facility_type"),
            _json_text(facility, "facility_type_description"),
            _json_text(facility, "type"),
        ),
        case(
            (
                func.lower(resolved_name).like("%foster family agency%"),
                literal("Foster Family Agency"),
            ),
            else_=literal("unknown"),
        ),
    )
    geography = _facility_intelligence_geography(facility)
    finding = func.coalesce(_json_text(complaint, "finding"), literal("unknown"))
    missing_facility_statement = select(literal(1)).select_from(complaint).where(
        complaint.c.entity_type == "complaint",
        _facility_intelligence_import_filter(
            complaint,
            import_batch_id=import_batch_id,
            import_batch_ids=import_batch_ids,
            import_batch_query=import_batch_query,
        ),
        or_(
            complaint.c.facility_id.is_(None),
            tuple_(complaint.c.import_batch_id, complaint.c.facility_id).not_in(
                select(facility_keys.c.import_batch_id, facility_keys.c.facility_id)
            ),
        ),
    )
    has_missing_facility = connection.execute(
        _facility_intelligence_bounded_limit(
            missing_facility_statement,
            1,
            dialect_name=connection.dialect.name,
        )
    ).first() is not None

    allegation = hosted_source_derived_records.alias(
        "facility_intelligence_option_allegation"
    )
    category_statement = (
        select(_json_text(allegation, "allegation_category"))
        .where(
            allegation.c.entity_type == "allegation",
            _facility_intelligence_import_filter(
                allegation,
                import_batch_id=import_batch_id,
                import_batch_ids=import_batch_ids,
                import_batch_query=import_batch_query,
            ),
        )
        .distinct()
    )
    categories = tuple(
        str(value).casefold()
        for value in connection.execute(
            _facility_intelligence_bounded_limit(
                category_statement,
                _FACILITY_INTELLIGENCE_OPTION_LIMIT,
                dialect_name=connection.dialect.name,
            )
        ).scalars()
        if value
    )
    normalized_category = func.lower(
        func.coalesce(_json_text(allegation, "allegation_category"), "")
    )
    allegation_text = func.lower(
        func.coalesce(_json_text(allegation, "allegation_text"), "")
    )
    cue_statement = select(literal(1)).where(
            allegation.c.entity_type == "allegation",
            _facility_intelligence_import_filter(
                allegation,
                import_batch_id=import_batch_id,
                import_batch_ids=import_batch_ids,
                import_batch_query=import_batch_query,
            ),
            normalized_category.in_(("", "unknown")),
            or_(
                *(
                    allegation_text.like(f"%{term}%")
                    for term in _FACILITY_INTELLIGENCE_SERIOUS_CUE_TERMS
                )
            ),
            and_(
                *(
                    allegation_text.not_like(f"%{phrase}%")
                    for phrase in _FACILITY_INTELLIGENCE_SERIOUS_CUE_EXCLUSIONS
                )
            ),
        )
    cue_exists = connection.execute(
        _facility_intelligence_bounded_limit(
            cue_statement,
            1,
            dialect_name=connection.dialect.name,
        )
    ).first()
    serious_topic_values = {
        label
        for category, label in _FACILITY_INTELLIGENCE_SERIOUS_CATEGORY_LABELS.items()
        if category in categories
    }
    if cue_exists is not None:
        serious_topic_values.add("Possible keyword cue")
    serious_topics = tuple(sorted(serious_topic_values, key=str.casefold))
    facility_types = set(
        distinct_values(facility_type, facility_options_from)
    )
    geographies = set(distinct_values(geography, facility_options_from))
    if has_missing_facility:
        facility_types.add("unknown")
        geographies.add("unknown")
    return FacilityIntelligenceFilterOptions(
        facility_types=tuple(sorted(facility_types, key=str.casefold)),
        geographies=tuple(sorted(geographies, key=str.casefold)),
        findings=distinct_values(
            finding,
            complaint,
            complaint.c.entity_type == "complaint",
            _facility_intelligence_import_filter(
                complaint,
                import_batch_id=import_batch_id,
                import_batch_ids=import_batch_ids,
                import_batch_query=import_batch_query,
            ),
        ),
        serious_topics=serious_topics,
    )


def _facility_intelligence_bounded_limit(
    statement: Any,
    limit: int,
    *,
    dialect_name: str,
) -> Any:
    if dialect_name == "sqlite":
        # SQLAlchemy renders LIMIT-only SQLite selects as ``LIMIT ? OFFSET ?``.
        # A controlled suffix keeps local query evidence free of even OFFSET 0.
        return statement.suffix_with(f"LIMIT {limit}")
    return statement.limit(limit)


def _facility_intelligence_import_filter(
    table: Any,
    *,
    import_batch_id: str | None,
    import_batch_ids: tuple[str, ...] | None,
    import_batch_query: Select[Any] | CompoundSelect[Any] | None,
) -> Any:
    if import_batch_id is not None:
        return table.c.import_batch_id == import_batch_id
    if import_batch_ids is not None:
        if not import_batch_ids:
            return literal(False)
        return table.c.import_batch_id.in_(import_batch_ids)
    if import_batch_query is not None:
        return table.c.import_batch_id.in_(import_batch_query)
    return literal(True)


def _facility_intelligence_activity_date(
    complaint: Any,
    date_dimension: str,
    *,
    dialect_name: str,
) -> Any:
    field_names: tuple[str, ...]
    if date_dimension == "latest_supported_activity":
        field_names = (
            "complaint_received_date",
            "visit_date",
            "report_date",
            "date_signed",
        )
    elif date_dimension in CCLD_REVIEW_DATE_FIELDS:
        field_names = (date_dimension,)
    else:
        allowed = ", ".join(("latest_supported_activity", *CCLD_REVIEW_DATE_FIELDS))
        raise ValueError(f"date_dimension must be one of: {allowed}.")
    values = tuple(
        _validated_date_expression_for_table(
            complaint,
            field_name,
            dialect_name=dialect_name,
        )
        for field_name in field_names
    )
    if len(values) == 1:
        return func.nullif(values[0], "")
    latest = func.greatest(*values) if dialect_name == "postgresql" else func.max(*values)
    return func.nullif(latest, "")


def _facility_intelligence_related_substantiated(
    *,
    cte_name: str,
    import_batch_id: str | None,
    import_batch_ids: tuple[str, ...] | None,
    import_batch_query: Select[Any] | CompoundSelect[Any] | None,
) -> Any:
    allegation = hosted_source_derived_records.alias(
        f"{cte_name}_substantiated_allegation"
    )
    event = hosted_source_derived_records.alias(
        f"{cte_name}_substantiated_event"
    )
    allegation_complaint_id = _json_text(allegation, "complaint_id")
    allegation_matches = select(
        allegation.c.import_batch_id.label("import_batch_id"),
        allegation_complaint_id.label("complaint_id"),
    ).where(
        allegation.c.entity_type == "allegation",
        _facility_intelligence_import_filter(
            allegation,
            import_batch_id=import_batch_id,
            import_batch_ids=import_batch_ids,
            import_batch_query=import_batch_query,
        ),
        allegation_complaint_id.is_not(None),
        _substantiated_values_expression(allegation),
    )
    event_context = func.lower(
        func.coalesce(
            _first_nonblank_text(
                *(
                    _json_text(event, key)
                    for key in (
                        "event_type",
                        "field_name",
                        "field",
                        "source_field",
                        "source_section",
                        "type",
                    )
                )
            ),
            "",
        )
    )
    event_context_matches = or_(
        *(event_context.like(f"%{marker}%") for marker in (
            "finding",
            "investigation",
            "resolution",
            "status",
        ))
    )
    event_text_matches = or_(
        *(
            _substantiated_text_expression(_json_text(event, key))
            for key in ("event_text", "summary", "description", "text")
        )
    )
    event_complaint_id = _json_text(event, "complaint_id")
    event_matches = select(
        event.c.import_batch_id.label("import_batch_id"),
        event_complaint_id.label("complaint_id"),
    ).where(
        event.c.entity_type == "event",
        _facility_intelligence_import_filter(
            event,
            import_batch_id=import_batch_id,
            import_batch_ids=import_batch_ids,
            import_batch_query=import_batch_query,
        ),
        event_complaint_id.is_not(None),
        or_(
            _substantiated_values_expression(event),
            and_(event_context_matches, event_text_matches),
        ),
    )
    matches = allegation_matches.union_all(event_matches).cte(
        f"{cte_name}_substantiated_matches"
    )
    return (
        select(matches.c.import_batch_id, matches.c.complaint_id)
        .distinct()
        .cte(f"{cte_name}_related_substantiated")
    )


def _substantiated_values_expression(table: Any) -> Any:
    candidates = tuple(
        _json_text(table, key)
        for key in (
            "finding",
            "finding_status",
            "investigation_finding",
            "normalized_finding",
            "resolution",
            "status",
        )
    )
    return or_(*(_substantiated_text_expression(value) for value in candidates))


def _substantiated_text_expression(value: Any) -> Any:
    normalized = func.lower(func.coalesce(value, ""))
    return and_(
        normalized.not_like("%unsubstantiated%"),
        normalized.not_like("%not substantiated%"),
        or_(
            normalized.like("%substantiated%"),
            normalized.like("%founded%"),
            normalized.like("%sustained%"),
        ),
    )


def _facility_intelligence_serious_topic_expression(
    complaint: Any,
    complaint_id: Any,
    requested_topic: str,
) -> Any:
    normalized_topic = " ".join(requested_topic.casefold().split())
    if not normalized_topic:
        return literal(True)
    allegation = hosted_source_derived_records.alias(
        "facility_intelligence_serious_allegation"
    )
    category = func.lower(func.coalesce(_json_text(allegation, "allegation_category"), ""))
    category_matches = [
        category == source_category
        for source_category, label in _FACILITY_INTELLIGENCE_SERIOUS_CATEGORY_LABELS.items()
        if normalized_topic in " ".join(label.casefold().split())
    ]
    cue_requested = normalized_topic in "possible keyword cue"
    allegation_text = func.lower(
        func.coalesce(_json_text(allegation, "allegation_text"), "")
    )
    cue_match = and_(
        category.in_(("", "unknown")),
        or_(
            *(
                allegation_text.like(f"%{term}%")
                for term in _FACILITY_INTELLIGENCE_SERIOUS_CUE_TERMS
            )
        ),
        and_(
            *(
                allegation_text.not_like(f"%{phrase}%")
                for phrase in _FACILITY_INTELLIGENCE_SERIOUS_CUE_EXCLUSIONS
            )
        ),
    )
    matches = list(category_matches)
    if cue_requested:
        matches.append(cue_match)
    if not matches:
        return literal(False)
    return select(literal(1)).where(
        allegation.c.entity_type == "allegation",
        allegation.c.import_batch_id == complaint.c.import_batch_id,
        _json_text(allegation, "complaint_id") == complaint_id,
        or_(*matches),
    ).exists()


def _facility_intelligence_geography(facility: Any) -> Any:
    county = _first_nonblank_text(
        _json_text(facility, "county"),
        _json_text(facility, "county_name"),
    )
    city = _json_text(facility, "city")
    state = _json_text(facility, "state")
    return func.coalesce(
        case(
            (
                and_(county.is_not(None), city.is_not(None), state.is_not(None)),
                county + literal(", ") + city + literal(", ") + state,
            ),
            (
                and_(county.is_not(None), city.is_not(None)),
                county + literal(", ") + city,
            ),
            (
                and_(county.is_not(None), state.is_not(None)),
                county + literal(", ") + state,
            ),
            (
                and_(city.is_not(None), state.is_not(None)),
                city + literal(", ") + state,
            ),
            (county.is_not(None), county),
            (city.is_not(None), city),
            (state.is_not(None), state),
        ),
        literal("unknown"),
    )


def _json_text(table: Any, key: str) -> Any:
    value = func.trim(table.c.original_values[key].as_string())
    return func.nullif(value, "")


def _json_bool(table: Any, key: str) -> Any:
    return table.c.original_values[key].as_boolean().is_(True)


def _first_nonblank_text(*values: Any) -> Any:
    return func.coalesce(*(func.nullif(func.trim(value), "") for value in values))


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
    return _validated_date_expression_for_table(
        hosted_source_derived_records,
        field_name,
        dialect_name=dialect_name,
    )


def _validated_date_expression_for_table(
    table: Any,
    field_name: str,
    *,
    dialect_name: str,
) -> Any:
    raw_value = func.substr(
        table.c.original_values[field_name].as_string(),
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
