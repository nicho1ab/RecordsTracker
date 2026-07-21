from __future__ import annotations

import csv
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from sqlalchemy import (
    JSON,
    Column,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    and_,
    func,
    inspect,
    or_,
    select,
    update,
)
from sqlalchemy import (
    cast as sql_cast,
)
from sqlalchemy.engine import Connection

from ccld_complaints.hosted_app.ccld_facility_lookup import (
    MAX_FACILITY_LOOKUP_RESULTS,
    CcldFacilityLookupRecord,
    CcldFacilityLookupResult,
    CcldFacilityReferenceSource,
)
from ccld_complaints.hosted_app.persistence import load_hosted_database_config
from ccld_complaints.source_profiling import DEFAULT_SOURCE_ROOT, FACILITY_SOURCE_REGISTRY

DEFAULT_FACILITY_REFERENCE_PRELOAD_INPUT_PATH = DEFAULT_SOURCE_ROOT
FACILITY_REFERENCE_TABLE_NAME = "hosted_facility_reference_records"
FACILITY_REFERENCE_DATASET_SLUG = FACILITY_SOURCE_REGISTRY["parent_dataset"]["slug"]
FACILITY_REFERENCE_DATASET_URL = FACILITY_SOURCE_REGISTRY["parent_dataset"]["official_dataset_url"]
# Provenance-only original_row_json key for DictReader cells beyond the declared header.
SOURCE_CSV_OVERFLOW_PROVENANCE_KEY = "_source_csv_overflow_values"
_FILENAME_DATE_PATTERN = re.compile(r"(?<!\d)(\d{2})(\d{2})(\d{4})(?!\d)")
_HEADER_NORMALIZE_PATTERN = re.compile(r"[^a-z0-9]+")
_UNUSABLE_ADDRESS_VALUES = frozenset(("", "unavailable", "not listed", "unknown", "n/a", "na"))

hosted_facility_reference_metadata = MetaData()

hosted_facility_reference_records = Table(
    FACILITY_REFERENCE_TABLE_NAME,
    hosted_facility_reference_metadata,
    Column("source_resource_id", String(128), primary_key=True),
    Column("facility_number", String(32), primary_key=True),
    Column("facility_name", Text, nullable=False),
    Column("facility_type", Text, nullable=True),
    Column("program_type", Text, nullable=True),
    Column("client_served", Text, nullable=True),
    Column("licensee_name", Text, nullable=True),
    Column("facility_administrator", Text, nullable=True),
    Column("telephone", String(64), nullable=True),
    Column("address", Text, nullable=True),
    Column("city", Text, nullable=True),
    Column("state", String(16), nullable=True),
    Column("zip", String(16), nullable=True),
    Column("county", Text, nullable=True),
    Column("regional_office", Text, nullable=True),
    Column("capacity", Integer, nullable=True),
    Column("status", Text, nullable=True),
    Column("license_first_date", String(10), nullable=True),
    Column("closed_date", String(10), nullable=True),
    Column("all_visit_dates", JSON(none_as_null=True), nullable=True),
    Column("inspection_visit_dates", JSON(none_as_null=True), nullable=True),
    Column("other_visit_dates", JSON(none_as_null=True), nullable=True),
    Column("snapshot_date", String(10), nullable=True),
    Column("source_resource_name", Text, nullable=False),
    Column("source_dataset_slug", Text, nullable=False),
    Column("source_dataset_url", Text, nullable=False),
    Column("source_accessed_at", String(40), nullable=False),
    Column("source_file_name", Text, nullable=True),
    Column("original_row_json", JSON, nullable=False),
)

Index(
    "ix_hosted_facility_reference_records_facility_number",
    hosted_facility_reference_records.c.facility_number,
)
Index(
    "ix_hosted_facility_reference_records_facility_name",
    hosted_facility_reference_records.c.facility_name,
)
Index(
    "ix_hosted_facility_reference_records_type_program",
    hosted_facility_reference_records.c.facility_type,
    hosted_facility_reference_records.c.program_type,
)
Index(
    "ix_hosted_facility_reference_records_county",
    hosted_facility_reference_records.c.county,
)
Index(
    "ix_hosted_facility_reference_records_status",
    hosted_facility_reference_records.c.status,
)
Index(
    "ix_hosted_facility_reference_records_city",
    hosted_facility_reference_records.c.city,
)
Index(
    "ix_hosted_facility_reference_records_zip",
    hosted_facility_reference_records.c.zip,
)


@dataclass(frozen=True)
class FacilityReferenceRecord:
    facility_number: str
    facility_name: str
    facility_type: str | None
    program_type: str | None
    client_served: str | None
    licensee_name: str | None
    facility_administrator: str | None
    telephone: str | None
    address: str | None
    city: str | None
    state: str | None
    zip: str | None
    county: str | None
    regional_office: str | None
    capacity: int | None
    status: str | None
    license_first_date: str | None
    closed_date: str | None
    all_visit_dates: tuple[str, ...] | None
    inspection_visit_dates: tuple[str, ...] | None
    other_visit_dates: tuple[str, ...] | None
    snapshot_date: str | None
    source_resource_id: str
    source_resource_name: str
    source_dataset_slug: str
    source_dataset_url: str
    source_accessed_at: str
    source_file_name: str
    original_row_json: Mapping[str, Any]

    def values(self) -> dict[str, Any]:
        return {
            "source_resource_id": self.source_resource_id,
            "facility_number": self.facility_number,
            "facility_name": self.facility_name,
            "facility_type": self.facility_type,
            "program_type": self.program_type,
            "client_served": self.client_served,
            "licensee_name": self.licensee_name,
            "facility_administrator": self.facility_administrator,
            "telephone": self.telephone,
            "address": self.address,
            "city": self.city,
            "state": self.state,
            "zip": self.zip,
            "county": self.county,
            "regional_office": self.regional_office,
            "capacity": self.capacity,
            "status": self.status,
            "license_first_date": self.license_first_date,
            "closed_date": self.closed_date,
            "all_visit_dates": _date_collection_json_value(self.all_visit_dates),
            "inspection_visit_dates": _date_collection_json_value(self.inspection_visit_dates),
            "other_visit_dates": _date_collection_json_value(self.other_visit_dates),
            "snapshot_date": self.snapshot_date,
            "source_resource_name": self.source_resource_name,
            "source_dataset_slug": self.source_dataset_slug,
            "source_dataset_url": self.source_dataset_url,
            "source_accessed_at": self.source_accessed_at,
            "source_file_name": self.source_file_name,
            "original_row_json": dict(self.original_row_json),
        }


@dataclass(frozen=True)
class FacilityReferenceParserWarning:
    source_file_name: str
    row_number: int
    message: str


@dataclass(frozen=True)
class FacilityReferenceParseResult:
    source_resource_id: str
    source_resource_name: str
    source_file_name: str
    records: tuple[FacilityReferenceRecord, ...]
    skipped_row_count: int
    warnings: tuple[FacilityReferenceParserWarning, ...]


@dataclass(frozen=True)
class FacilityReferencePreloadResourceResult:
    source_resource_id: str
    source_resource_name: str
    source_file_name: str
    parsed_row_count: int
    inserted_row_count: int
    updated_row_count: int
    unchanged_row_count: int
    skipped_row_count: int
    warning_count: int
    warnings: tuple[FacilityReferenceParserWarning, ...]


@dataclass(frozen=True)
class FacilityReferencePreloadResult:
    apply_changes: bool
    input_path: Path
    resource_results: tuple[FacilityReferencePreloadResourceResult, ...]

    @property
    def inserted_row_count(self) -> int:
        return sum(result.inserted_row_count for result in self.resource_results)

    @property
    def updated_row_count(self) -> int:
        return sum(result.updated_row_count for result in self.resource_results)

    @property
    def unchanged_row_count(self) -> int:
        return sum(result.unchanged_row_count for result in self.resource_results)

    @property
    def skipped_row_count(self) -> int:
        return sum(result.skipped_row_count for result in self.resource_results)

    @property
    def warning_count(self) -> int:
        return sum(result.warning_count for result in self.resource_results)


@dataclass(frozen=True)
class FacilityReferenceAddressDiagnostic:
    facility_number: str
    facility_name: str
    source_resource_id: str
    source_resource_name: str
    source_file_name: str
    normalized_address_fields: Mapping[str, str | None]
    raw_address_fields: Mapping[str, str]
    conclusion: str

    @property
    def raw_has_usable_address_fields(self) -> bool:
        return _raw_has_usable_address_fields(self.raw_address_fields)

    @property
    def normalized_has_missing_address_fields(self) -> bool:
        return any(
            not _is_usable_address_value(value)
            for key, value in self.normalized_address_fields.items()
            if key in {"address", "city", "state", "zip"}
        )


def parse_facility_reference_csv(
    path: Path,
    *,
    source_accessed_at: str | None = None,
) -> FacilityReferenceParseResult:
    source_metadata = _source_metadata_for_path(path)
    accessed_at = source_accessed_at or _file_accessed_at(path)
    snapshot_date = _snapshot_date_from_filename(path.name)
    records: list[FacilityReferenceRecord] = []
    warnings: list[FacilityReferenceParserWarning] = []
    skipped = 0

    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        fieldnames = tuple(reader.fieldnames or ())
        row_shape = _row_shape(fieldnames)
        if row_shape is None:
            return FacilityReferenceParseResult(
                source_resource_id=source_metadata["source_resource_id"],
                source_resource_name=source_metadata["source_resource_name"],
                source_file_name=path.name,
                records=(),
                skipped_row_count=0,
                warnings=(
                    FacilityReferenceParserWarning(
                        source_file_name=path.name,
                        row_number=0,
                        message="CSV header does not match a supported CCLD facility shape.",
                    ),
                ),
            )
        for row_number, row in enumerate(reader, start=2):
            record, row_warnings = _normalize_facility_row(
                row,
                row_shape=row_shape,
                source_metadata=source_metadata,
                source_file_name=path.name,
                source_accessed_at=accessed_at,
                snapshot_date=snapshot_date,
                row_number=row_number,
            )
            warnings.extend(row_warnings)
            if record is None:
                skipped += 1
            else:
                records.append(record)

    return FacilityReferenceParseResult(
        source_resource_id=source_metadata["source_resource_id"],
        source_resource_name=source_metadata["source_resource_name"],
        source_file_name=path.name,
        records=tuple(records),
        skipped_row_count=skipped,
        warnings=tuple(warnings),
    )


def load_facility_reference_preload(
    input_path: Path = DEFAULT_FACILITY_REFERENCE_PRELOAD_INPUT_PATH,
    *,
    connection: Connection,
    apply_changes: bool,
    source_accessed_at: str | None = None,
) -> FacilityReferencePreloadResult:
    csv_paths = _csv_paths(input_path)
    resource_results: list[FacilityReferencePreloadResourceResult] = []
    for csv_path in csv_paths:
        parse_result = parse_facility_reference_csv(
            csv_path,
            source_accessed_at=source_accessed_at,
        )
        inserted = 0
        updated = 0
        unchanged = 0
        for record in parse_result.records:
            operation = _preload_record(connection, record, apply_changes=apply_changes)
            if operation == "inserted":
                inserted += 1
            elif operation == "updated":
                updated += 1
            else:
                unchanged += 1
        resource_results.append(
            FacilityReferencePreloadResourceResult(
                source_resource_id=parse_result.source_resource_id,
                source_resource_name=parse_result.source_resource_name,
                source_file_name=parse_result.source_file_name,
                parsed_row_count=len(parse_result.records),
                inserted_row_count=inserted,
                updated_row_count=updated,
                unchanged_row_count=unchanged,
                skipped_row_count=parse_result.skipped_row_count,
                warning_count=len(parse_result.warnings),
                warnings=parse_result.warnings,
            )
        )
    return FacilityReferencePreloadResult(
        apply_changes=apply_changes,
        input_path=input_path,
        resource_results=tuple(resource_results),
    )


def facility_reference_source_from_connection(
    connection: Connection,
) -> CcldFacilityReferenceSource:
    if _active_transparency_snapshot_id(connection) is not None:
        return facility_reference_source_summary_from_connection(connection)
    rows = connection.execute(
        select(hosted_facility_reference_records).order_by(
            hosted_facility_reference_records.c.facility_name,
            hosted_facility_reference_records.c.facility_number,
        )
    ).mappings()
    records = tuple(_lookup_record_from_reference_row(dict(row)) for row in rows)
    notices: tuple[str, ...] = ()
    if not records:
        notices = (
            "Facility lookup suggestions are not available. Preload facility reference "
            "rows before using PostgreSQL-backed lookup suggestions.",
        )
    return CcldFacilityReferenceSource(
        source_kind="postgres_facility_reference",
        label="PostgreSQL facility reference records",
        path_label=FACILITY_REFERENCE_TABLE_NAME,
        records=records,
        notices=notices,
        record_count=len(records),
    )


def facility_reference_source_summary_from_connection(
    connection: Connection,
) -> CcldFacilityReferenceSource:
    active_snapshot_id = _active_transparency_snapshot_id(connection)
    if active_snapshot_id is not None:
        from ccld_complaints.connectors.ccld_transparency_api.lifecycle import (
            transparency_rows,
        )

        record_count = connection.execute(
            select(func.count(func.distinct(transparency_rows.c.facility_number))).where(
                transparency_rows.c.snapshot_id == active_snapshot_id,
                transparency_rows.c.is_quarantined.is_(False),
                transparency_rows.c.facility_number.is_not(None),
            )
        ).scalar_one()
        return CcldFacilityReferenceSource(
            source_kind="postgres_transparencyapi_reference",
            label="Accepted CCLD facility reference snapshot",
            path_label="active accepted TransparencyAPI snapshot",
            records=(),
            notices=(),
            record_count=record_count,
        )
    record_count = connection.execute(
        select(func.count()).select_from(hosted_facility_reference_records)
    ).scalar_one()
    notices: tuple[str, ...] = ()
    if record_count == 0:
        notices = (
            "Facility lookup suggestions are not available. Preload facility reference "
            "rows before using PostgreSQL-backed lookup suggestions.",
        )
    return CcldFacilityReferenceSource(
        source_kind="postgres_facility_reference",
        label="PostgreSQL facility reference records",
        path_label=FACILITY_REFERENCE_TABLE_NAME,
        records=(),
        notices=notices,
        record_count=record_count,
    )


def search_facility_reference_records(
    connection: Connection,
    query: str,
    *,
    result_limit: int = MAX_FACILITY_LOOKUP_RESULTS,
) -> CcldFacilityLookupResult:
    if result_limit < 1:
        raise ValueError("result_limit must be at least 1.")
    source = facility_reference_source_summary_from_connection(connection)
    if source.source_kind == "postgres_transparencyapi_reference":
        return _search_active_transparency_reference_records(
            connection,
            query,
            source=source,
            result_limit=result_limit,
        )
    query_tokens = _normalized_query_tokens(query)
    if not query_tokens:
        return CcldFacilityLookupResult(
            query=query.strip(),
            total_match_count=0,
            returned_records=(),
            result_limit=result_limit,
            reference_source=source,
        )
    filters = tuple(_search_token_filter(token) for token in query_tokens)
    total_match_count = connection.execute(
        select(func.count(func.distinct(hosted_facility_reference_records.c.facility_number)))
        .select_from(hosted_facility_reference_records)
        .where(and_(*filters))
    ).scalar_one()
    matching_id_rows = connection.execute(
        select(
            hosted_facility_reference_records.c.facility_number,
            func.min(hosted_facility_reference_records.c.facility_name).label(
                "sort_name"
            ),
        )
        .where(and_(*filters))
        .group_by(hosted_facility_reference_records.c.facility_number)
        .order_by(
            func.min(hosted_facility_reference_records.c.facility_name),
            hosted_facility_reference_records.c.facility_number,
        )
        .limit(result_limit)
    ).mappings()
    matching_ids = tuple(str(row["facility_number"]) for row in matching_id_rows)
    rows = (
        connection.execute(
            select(hosted_facility_reference_records)
            .where(hosted_facility_reference_records.c.facility_number.in_(matching_ids))
            .order_by(
                hosted_facility_reference_records.c.facility_name,
                hosted_facility_reference_records.c.facility_number,
                hosted_facility_reference_records.c.source_resource_id,
            )
        ).mappings()
        if matching_ids
        else ()
    )
    records = tuple(_lookup_record_from_reference_row(dict(row)) for row in rows)
    return CcldFacilityLookupResult(
        query=query.strip(),
        total_match_count=total_match_count,
        returned_records=records,
        result_limit=result_limit,
        reference_source=source,
    )


def _search_active_transparency_reference_records(
    connection: Connection,
    query: str,
    *,
    source: CcldFacilityReferenceSource,
    result_limit: int,
) -> CcldFacilityLookupResult:
    from ccld_complaints.connectors.ccld_transparency_api.lifecycle import (
        transparency_rows,
    )

    active_snapshot_id = _active_transparency_snapshot_id(connection)
    query_tokens = _normalized_query_tokens(query)
    if active_snapshot_id is None or not query_tokens:
        return CcldFacilityLookupResult(
            query=query.strip(),
            total_match_count=0,
            returned_records=(),
            result_limit=result_limit,
            reference_source=source,
        )
    filters = tuple(_transparency_search_token_filter(token) for token in query_tokens)
    base_conditions = (
        transparency_rows.c.snapshot_id == active_snapshot_id,
        transparency_rows.c.is_quarantined.is_(False),
        transparency_rows.c.facility_number.is_not(None),
        *filters,
    )
    total_match_count = connection.execute(
        select(func.count(func.distinct(transparency_rows.c.facility_number))).where(
            *base_conditions
        )
    ).scalar_one()
    name_expression = _transparency_value_expression("facility_name")
    rows = connection.execute(
        select(transparency_rows)
        .where(*base_conditions)
        .order_by(
            func.lower(func.coalesce(name_expression, "")),
            transparency_rows.c.facility_number,
            transparency_rows.c.export_id,
            transparency_rows.c.row_ordinal,
        )
        .limit(result_limit)
    ).mappings()
    records = tuple(_lookup_record_from_transparency_row(dict(row)) for row in rows)
    return CcldFacilityLookupResult(
        query=query.strip(),
        total_match_count=total_match_count,
        returned_records=records,
        result_limit=result_limit,
        reference_source=source,
    )


def _active_transparency_snapshot_id(connection: Connection) -> str | None:
    from ccld_complaints.connectors.ccld_transparency_api.contract import (
        SNAPSHOT_SCOPE,
        SOURCE_FAMILY_ID,
    )
    from ccld_complaints.connectors.ccld_transparency_api.lifecycle import (
        transparency_rows,
    )
    from ccld_complaints.hosted_app.source_snapshot_lifecycle import (
        source_snapshot_pointers,
        source_snapshots,
    )

    inspector = inspect(connection)
    if not all(
        inspector.has_table(table_name)
        for table_name in (
            source_snapshots.name,
            source_snapshot_pointers.name,
            transparency_rows.name,
        )
    ):
        return None
    value = connection.scalar(
        select(source_snapshot_pointers.c.active_snapshot_id)
        .join(
            source_snapshots,
            source_snapshots.c.snapshot_id
            == source_snapshot_pointers.c.active_snapshot_id,
        )
        .where(
            source_snapshot_pointers.c.source_family_id == SOURCE_FAMILY_ID,
            source_snapshots.c.source_family_id == SOURCE_FAMILY_ID,
            source_snapshots.c.fixture_scope == SNAPSHOT_SCOPE,
            source_snapshots.c.lifecycle_state == "accepted",
        )
    )
    return str(value) if value is not None else None


def _transparency_value_expression(field_name: str) -> Any:
    from ccld_complaints.connectors.ccld_transparency_api.lifecycle import (
        transparency_rows,
    )

    return transparency_rows.c.resolved_current_reference[field_name]["value"].as_string()


def _transparency_search_token_filter(token: str) -> Any:
    from ccld_complaints.connectors.ccld_transparency_api.lifecycle import (
        transparency_rows,
    )

    pattern = f"%{token}%"
    searchable_values = (
        transparency_rows.c.facility_number,
        *(
            _transparency_value_expression(field_name)
            for field_name in (
                "facility_name",
                "facility_city",
                "facility_state",
                "facility_zip",
                "county_name",
                "facility_type",
                "bulk_status",
            )
        ),
    )
    return or_(
        *(
            func.lower(func.coalesce(sql_cast(value, String), "")).like(pattern)
            for value in searchable_values
        )
    )


def _lookup_record_from_transparency_row(
    row: Mapping[str, Any],
) -> CcldFacilityLookupRecord:
    resolved_values = row.get("resolved_current_reference")
    resolved = resolved_values if isinstance(resolved_values, Mapping) else {}

    def value(field_name: str) -> str:
        observation = resolved.get(field_name)
        if not isinstance(observation, Mapping):
            return ""
        selected = observation.get("value")
        return "" if selected is None else str(selected).strip()

    return CcldFacilityLookupRecord(
        facility_number=_row_str(row, "facility_number"),
        facility_name=value("facility_name"),
        city=value("facility_city"),
        state=value("facility_state"),
        county=value("county_name"),
        zip_code=value("facility_zip"),
        facility_type=value("facility_type"),
        program_type="",
        capacity=value("facility_capacity"),
        status=value("bulk_status"),
        closed_date=value("closed_date"),
        address=value("facility_address"),
        regional_office=value("regional_office"),
        administrator=value("facility_administrator"),
        licensee=value("licensee"),
        telephone=value("facility_telephone_number"),
    )


def diagnose_facility_reference_address(
    connection: Connection,
    facility_number: str,
) -> tuple[FacilityReferenceAddressDiagnostic, ...]:
    normalized_number = _clean_value(facility_number)
    if not normalized_number or not normalized_number.isdigit():
        raise ValueError("facility_number must contain digits only.")
    rows = connection.execute(
        select(hosted_facility_reference_records)
        .where(hosted_facility_reference_records.c.facility_number == normalized_number)
        .order_by(
            hosted_facility_reference_records.c.source_resource_name,
            hosted_facility_reference_records.c.source_file_name,
        )
    ).mappings()
    diagnostics = tuple(_address_diagnostic_from_row(dict(row)) for row in rows)
    return _mark_duplicate_source_variance(diagnostics)


def open_configured_facility_reference_connection() -> Connection:
    from sqlalchemy import create_engine

    database_config = load_hosted_database_config(require_url=True)
    engine = create_engine(cast(str, database_config.database_url))
    return engine.connect()


def _preload_record(
    connection: Connection,
    record: FacilityReferenceRecord,
    *,
    apply_changes: bool,
) -> str:
    values = record.values()
    existing = (
        connection.execute(
            select(hosted_facility_reference_records).where(
                hosted_facility_reference_records.c.source_resource_id == record.source_resource_id,
                hosted_facility_reference_records.c.facility_number == record.facility_number,
            )
        )
        .mappings()
        .first()
    )
    if existing is None:
        if apply_changes:
            connection.execute(hosted_facility_reference_records.insert().values(**values))
        return "inserted"
    comparable_existing = {key: existing[key] for key in values}
    if comparable_existing == values:
        return "unchanged"
    if apply_changes:
        connection.execute(
            update(hosted_facility_reference_records)
            .where(
                hosted_facility_reference_records.c.source_resource_id == record.source_resource_id,
                hosted_facility_reference_records.c.facility_number == record.facility_number,
            )
            .values(**values)
        )
    return "updated"


def _normalize_facility_row(
    row: Mapping[str | None, Any],
    *,
    row_shape: str,
    source_metadata: Mapping[str, str],
    source_file_name: str,
    source_accessed_at: str,
    snapshot_date: str | None,
    row_number: int,
) -> tuple[FacilityReferenceRecord | None, tuple[FacilityReferenceParserWarning, ...]]:
    warnings: list[FacilityReferenceParserWarning] = []
    facility_number = _facility_number(row, row_shape)
    facility_name = _value(row, "Facility Name", "NAME")
    if not facility_number:
        warnings.append(
            _warning(
                source_file_name,
                row_number,
                "Skipped row without a usable facility number.",
            )
        )
    if not facility_name:
        warnings.append(
            _warning(source_file_name, row_number, "Skipped row without a facility name.")
        )
    if not facility_number or not facility_name:
        return None, tuple(warnings)

    capacity = _capacity_value(row, row_shape)
    if capacity is None and _value(row, "Facility Capacity", "CAPACITY"):
        warnings.append(_warning(source_file_name, row_number, "Capacity was not numeric."))

    closed_date = _date_value(row, "Closed Date", "CLOSED_DATE")
    if closed_date is None and _value(row, "Closed Date", "CLOSED_DATE"):
        warnings.append(_warning(source_file_name, row_number, "Closed Date was not a valid date."))

    all_visit_dates = _date_collection_value(
        row,
        "All Visit Dates",
        source_file_name=source_file_name,
        row_number=row_number,
        warnings=warnings,
    )
    inspection_visit_dates = _date_collection_value(
        row,
        "Inspection Visit Dates",
        source_file_name=source_file_name,
        row_number=row_number,
        warnings=warnings,
    )
    other_visit_dates = _date_collection_value(
        row,
        "Other Visit Dates",
        source_file_name=source_file_name,
        row_number=row_number,
        warnings=warnings,
    )

    return (
        FacilityReferenceRecord(
            facility_number=facility_number,
            facility_name=facility_name,
            facility_type=_none_if_empty(
                _value(row, "Facility Type")
                if row_shape == "program"
                else _value(row, "FAC_TYPE_DESC")
            ),
            program_type=_none_if_empty(_value(row, "Program Type", "PROGRAM_TYPE")),
            client_served=_none_if_empty(_value(row, "CLIENT_SERVED")),
            licensee_name=_none_if_empty(_value(row, "Licensee", "LICENSEE")),
            facility_administrator=_none_if_empty(
                _value(row, "Facility Administrator", "ADMINISTRATOR")
            ),
            telephone=_none_if_empty(
                _value(row, "Facility Telephone Number", "FAC_PHONE_NBR", "PHONE")
            ),
            address=_none_if_empty(_value(row, "Facility Address", "RES_STREET_ADDR", "ADDRESS")),
            city=_none_if_empty(_value(row, "Facility City", "RES_CITY", "CITY")),
            state=_none_if_empty(_value(row, "Facility State", "RES_STATE", "STATE")),
            zip=_none_if_empty(_value(row, "Facility Zip", "RES_ZIP_CODE", "ZIP")),
            county=_none_if_empty(_value(row, "County Name", "COUNTY")),
            regional_office=_none_if_empty(_value(row, "Regional Office", "FAC_DO_DESC")),
            capacity=capacity,
            status=_none_if_empty(_value(row, "Facility Status", "STATUS")),
            license_first_date=_date_value(row, "License First Date", "LICENSE_FIRST_DATE"),
            closed_date=closed_date,
            all_visit_dates=all_visit_dates,
            inspection_visit_dates=inspection_visit_dates,
            other_visit_dates=other_visit_dates,
            snapshot_date=snapshot_date,
            source_resource_id=source_metadata["source_resource_id"],
            source_resource_name=source_metadata["source_resource_name"],
            source_dataset_slug=FACILITY_REFERENCE_DATASET_SLUG,
            source_dataset_url=FACILITY_REFERENCE_DATASET_URL,
            source_accessed_at=source_accessed_at,
            source_file_name=source_file_name,
            original_row_json=_original_row_json(row),
        ),
        tuple(warnings),
    )


def _facility_number(row: Mapping[str | None, Any], row_shape: str) -> str:
    raw_value = _value(row, "Facility Number") if row_shape == "program" else _value(row, "FAC_NBR")
    cleaned = _clean_value(raw_value)
    return cleaned if cleaned.isdigit() else ""


def _capacity_value(row: Mapping[str | None, Any], row_shape: str) -> int | None:
    raw_value = (
        _value(row, "Facility Capacity") if row_shape == "program" else _value(row, "CAPACITY")
    )
    cleaned = _clean_value(raw_value).replace(",", "")
    return int(cleaned) if cleaned.isdigit() else None


def _date_value(row: Mapping[str | None, Any], *headers: str) -> str | None:
    return _normalized_date(_value(row, *headers))


def _normalized_date(raw_value: str) -> str | None:
    cleaned = _clean_value(raw_value)
    if not cleaned:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%m-%d-%y"):
        try:
            return datetime.strptime(cleaned, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _date_collection_value(
    row: Mapping[str | None, Any],
    header: str,
    *,
    source_file_name: str,
    row_number: int,
    warnings: list[FacilityReferenceParserWarning],
) -> tuple[str, ...] | None:
    raw_value = _value(row, header)
    if not raw_value:
        return None
    tokens = tuple(token.strip() for token in raw_value.split(";") if token.strip())
    normalized_dates: list[str] = []
    invalid_tokens: list[str] = []
    for token in tokens:
        normalized = _normalized_date(token)
        if normalized is None:
            invalid_tokens.append(token)
        else:
            normalized_dates.append(normalized)
    if invalid_tokens or not tokens:
        warnings.append(
            _warning(
                source_file_name,
                row_number,
                f"{header} contained a value that was not a valid date.",
            )
        )
        return None
    return tuple(sorted(set(normalized_dates))) or None


def _date_collection_json_value(value: tuple[str, ...] | None) -> list[str] | None:
    return list(value) if value is not None else None


def _original_row_json(row: Mapping[str | None, Any]) -> dict[str, Any]:
    original_row = {key: value for key, value in row.items() if key is not None}
    overflow_values = row.get(None)
    if overflow_values is not None:
        original_row[SOURCE_CSV_OVERFLOW_PROVENANCE_KEY] = (
            list(overflow_values)
            if isinstance(overflow_values, (list, tuple))
            else [str(overflow_values)]
        )
    return original_row


def _row_shape(fieldnames: Iterable[str]) -> str | None:
    normalized = {_normalized_header(fieldname) for fieldname in fieldnames}
    if {"facilitynumber", "facilityname"}.issubset(normalized):
        return "program"
    if {"facnbr", "name"}.issubset(normalized):
        return "master"
    return None


def _source_metadata_for_path(path: Path) -> dict[str, str]:
    file_name = path.name
    for resource in FACILITY_SOURCE_REGISTRY["target_resources"]:
        if _matches_resource(file_name, resource):
            return {
                "source_resource_id": resource["resource_id"],
                "source_resource_name": resource["resource_name"],
            }
    for resource in FACILITY_SOURCE_REGISTRY["needs_confirmation_resources"]:
        if _matches_resource(file_name, resource):
            return {
                "source_resource_id": f"needs-confirmation:{file_name}",
                "source_resource_name": resource["resource_name"],
            }
    return {
        "source_resource_id": f"unmatched-local-csv:{file_name}",
        "source_resource_name": "Unmatched local CSV",
    }


def _matches_resource(file_name: str, resource: Mapping[str, Any]) -> bool:
    resource_id = resource.get("resource_id")
    aliases = tuple(resource.get("local_filename_aliases", ()))
    return file_name in aliases or (isinstance(resource_id, str) and resource_id in file_name)


def _csv_paths(input_path: Path) -> tuple[Path, ...]:
    if input_path.is_file():
        return (input_path,)
    if not input_path.exists():
        raise FileNotFoundError(f"Facility reference input path was not found: {input_path}")
    return tuple(sorted(path for path in input_path.rglob("*.csv") if path.is_file()))


def _lookup_record_from_reference_row(row: Mapping[str, Any]) -> CcldFacilityLookupRecord:
    original_row = row.get("original_row_json")
    original_values = original_row if isinstance(original_row, Mapping) else {}
    capacity_present, raw_capacity = _raw_reference_value(
        original_values,
        "Facility Capacity",
        "CAPACITY",
    )
    closed_date_present, raw_closed_date = _raw_reference_value(
        original_values,
        "Closed Date",
        "CLOSED_DATE",
    )
    capacity = _row_str(row, "capacity") or raw_capacity
    closed_date = _row_str(row, "closed_date") or raw_closed_date
    return CcldFacilityLookupRecord(
        facility_number=_row_str(row, "facility_number"),
        facility_name=_row_str(row, "facility_name"),
        city=_row_str(row, "city"),
        state=_row_str(row, "state"),
        county=_row_str(row, "county"),
        zip_code=_row_str(row, "zip"),
        facility_type=_row_str(row, "facility_type"),
        program_type=_row_str(row, "program_type"),
        capacity=capacity,
        status=_row_str(row, "status"),
        closed_date=closed_date,
        address=_row_str(row, "address"),
        regional_office=_row_str(row, "regional_office"),
        facility_address=_raw_reference_field(original_values, "Facility Address"),
        fac_do_desc=_raw_reference_field(original_values, "FAC_DO_DESC"),
        res_street_addr=_raw_reference_field(original_values, "RES_STREET_ADDR"),
        capacity_source_present=capacity_present,
        closed_date_source_present=closed_date_present,
    )


def _raw_reference_field(values: Mapping[str, Any], key: str) -> str | None:
    if key not in values:
        return None
    value = values.get(key)
    return "" if value is None else str(value).strip()


def _raw_reference_value(
    values: Mapping[str, Any],
    *keys: str,
) -> tuple[bool, str]:
    for key in keys:
        if key in values:
            value = values.get(key)
            return True, "" if value is None else str(value).strip()
    return False, ""


def _address_diagnostic_from_row(
    row: Mapping[str, Any],
) -> FacilityReferenceAddressDiagnostic:
    normalized_fields = {
        "address": _optional_row_str(row, "address"),
        "city": _optional_row_str(row, "city"),
        "state": _optional_row_str(row, "state"),
        "zip": _optional_row_str(row, "zip"),
        "county": _optional_row_str(row, "county"),
        "regional_office": _optional_row_str(row, "regional_office"),
    }
    original_row = row.get("original_row_json")
    original_row_mapping: Mapping[Any, Any]
    if isinstance(original_row, Mapping):
        original_row_mapping = original_row
        original_row_was_mapping = True
    else:
        original_row_mapping = {}
        original_row_was_mapping = False
    raw_fields = _raw_address_fields(original_row_mapping)
    return FacilityReferenceAddressDiagnostic(
        facility_number=_row_str(row, "facility_number"),
        facility_name=_row_str(row, "facility_name"),
        source_resource_id=_row_str(row, "source_resource_id"),
        source_resource_name=_row_str(row, "source_resource_name"),
        source_file_name=_row_str(row, "source_file_name"),
        normalized_address_fields=normalized_fields,
        raw_address_fields=raw_fields,
        conclusion=_address_diagnostic_conclusion(
            normalized_fields=normalized_fields,
            raw_fields=raw_fields,
            original_row_was_mapping=original_row_was_mapping,
        ),
    )


def _raw_address_fields(original_row: Mapping[Any, Any]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for key, value in original_row.items():
        if not isinstance(key, str):
            continue
        if _is_address_like_header(key):
            fields[key] = _clean_value(str(value)) if value is not None else ""
    return dict(sorted(fields.items()))


def _is_address_like_header(header: str) -> bool:
    return _is_mappable_address_header(header) or "county" in _header_tokens(header)


def _address_diagnostic_conclusion(
    *,
    normalized_fields: Mapping[str, str | None],
    raw_fields: Mapping[str, str],
    original_row_was_mapping: bool = True,
) -> str:
    if _has_mapped_address(normalized_fields):
        return "has_mapped_address"
    if not original_row_was_mapping:
        return "inconclusive"
    if _raw_has_usable_address_fields(raw_fields):
        return "normalization_gap"
    return "source_missing_address"


def _mark_duplicate_source_variance(
    diagnostics: tuple[FacilityReferenceAddressDiagnostic, ...],
) -> tuple[FacilityReferenceAddressDiagnostic, ...]:
    if len(diagnostics) < 2:
        return diagnostics
    any_row_has_address = any(
        _has_mapped_address(item.normalized_address_fields)
        or _raw_has_usable_address_fields(item.raw_address_fields)
        for item in diagnostics
    )
    any_row_lacks_address = any(
        not _has_mapped_address(item.normalized_address_fields)
        and not _raw_has_usable_address_fields(item.raw_address_fields)
        for item in diagnostics
    )
    if not any_row_has_address or not any_row_lacks_address:
        return diagnostics
    return tuple(
        replace(item, conclusion="duplicate_source_variance")
        if not _has_mapped_address(item.normalized_address_fields)
        and not _raw_has_usable_address_fields(item.raw_address_fields)
        else item
        for item in diagnostics
    )


def _has_mapped_address(normalized_fields: Mapping[str, str | None]) -> bool:
    return any(
        _is_usable_address_value(normalized_fields.get(key))
        for key in ("address", "city", "state", "zip")
    )


def _raw_has_usable_address_fields(raw_fields: Mapping[str, str]) -> bool:
    return any(
        _is_usable_address_value(value) and _is_mappable_address_header(key)
        for key, value in raw_fields.items()
    )


def _is_usable_address_value(value: str | None) -> bool:
    return _clean_value(value).casefold() not in _UNUSABLE_ADDRESS_VALUES


def _is_mappable_address_header(header: str) -> bool:
    tokens = set(_header_tokens(header))
    compact = _normalized_header(header)
    if "capacity" in tokens or compact.endswith("capacity"):
        return False
    if tokens.intersection(
        {
            "address",
            "addr",
            "street",
            "city",
            "state",
            "zip",
            "postal",
            "location",
            "latitude",
            "longitude",
        }
    ):
        return True
    return (
        "address" in compact
        or "addr" in compact
        or "street" in compact
        or compact.endswith("city")
        or compact.endswith("state")
        or "zip" in compact
        or "postal" in compact
    )


def _header_tokens(header: str) -> tuple[str, ...]:
    return tuple(token for token in re.split(r"[^a-z0-9]+", header.casefold()) if token)


def _value(row: Mapping[str | None, Any], *headers: str) -> str:
    normalized_row = {_normalized_header(key): value for key, value in row.items()}
    for header in headers:
        value = row.get(header)
        if isinstance(value, str):
            return _clean_value(value)
        value = normalized_row.get(_normalized_header(header))
        if isinstance(value, str):
            return _clean_value(value)
    return ""


def _row_str(row: Mapping[str, Any], key: str) -> str:
    value = row.get(key)
    if value is None:
        return ""
    return str(value)


def _optional_row_str(row: Mapping[str, Any], key: str) -> str | None:
    value = row.get(key)
    if value is None:
        return None
    return str(value)


def _normalized_query_tokens(query: str) -> tuple[str, ...]:
    normalized = re.sub(r"\s+", " ", query.casefold()).strip()
    return tuple(token for token in normalized.split(" ") if token)


def _search_token_filter(token: str) -> Any:
    pattern = f"%{token}%"
    searchable_columns = (
        hosted_facility_reference_records.c.facility_number,
        hosted_facility_reference_records.c.facility_name,
        hosted_facility_reference_records.c.city,
        hosted_facility_reference_records.c.county,
        hosted_facility_reference_records.c.zip,
        hosted_facility_reference_records.c.facility_type,
        hosted_facility_reference_records.c.program_type,
        hosted_facility_reference_records.c.status,
    )
    return or_(
        *(
            func.lower(func.coalesce(sql_cast(column, String), "")).like(pattern)
            for column in searchable_columns
        )
    )


def _snapshot_date_from_filename(file_name: str) -> str | None:
    match = _FILENAME_DATE_PATTERN.search(file_name)
    if match is None:
        return None
    month, day, year = (int(part) for part in match.groups())
    try:
        return datetime(year, month, day).date().isoformat()
    except ValueError:
        return None


def _file_accessed_at(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, UTC).replace(microsecond=0).isoformat()


def _warning(
    source_file_name: str,
    row_number: int,
    message: str,
) -> FacilityReferenceParserWarning:
    return FacilityReferenceParserWarning(
        source_file_name=source_file_name,
        row_number=row_number,
        message=message,
    )


def _clean_value(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(value.split())


def _none_if_empty(value: str) -> str | None:
    return value or None


def _normalized_header(value: str | None) -> str:
    if value is None:
        return ""
    return _HEADER_NORMALIZE_PATTERN.sub("", value.casefold())
