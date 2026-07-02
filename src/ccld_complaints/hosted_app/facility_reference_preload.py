from __future__ import annotations

import csv
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from sqlalchemy import JSON, Column, Index, Integer, MetaData, String, Table, Text, select, update
from sqlalchemy.engine import Connection

from ccld_complaints.hosted_app.ccld_facility_lookup import (
    CcldFacilityLookupRecord,
    CcldFacilityReferenceSource,
)
from ccld_complaints.hosted_app.persistence import load_hosted_database_config
from ccld_complaints.source_profiling import DEFAULT_SOURCE_ROOT, FACILITY_SOURCE_REGISTRY

DEFAULT_FACILITY_REFERENCE_PRELOAD_INPUT_PATH = DEFAULT_SOURCE_ROOT
FACILITY_REFERENCE_TABLE_NAME = "hosted_facility_reference_records"
FACILITY_REFERENCE_DATASET_SLUG = FACILITY_SOURCE_REGISTRY["parent_dataset"]["slug"]
FACILITY_REFERENCE_DATASET_URL = FACILITY_SOURCE_REGISTRY["parent_dataset"][
    "official_dataset_url"
]
_FILENAME_DATE_PATTERN = re.compile(r"(?<!\d)(\d{2})(\d{2})(\d{4})(?!\d)")
_HEADER_NORMALIZE_PATTERN = re.compile(r"[^a-z0-9]+")

hosted_facility_reference_metadata = MetaData()

hosted_facility_reference_records = Table(
    FACILITY_REFERENCE_TABLE_NAME,
    hosted_facility_reference_metadata,
    Column("source_resource_id", String(128), primary_key=True),
    Column("facility_number", String(32), primary_key=True),
    Column("facility_name", Text, nullable=False),
    Column("facility_type", Text, nullable=True),
    Column("program_type", Text, nullable=True),
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
    snapshot_date: str | None
    source_resource_id: str
    source_resource_name: str
    source_dataset_slug: str
    source_dataset_url: str
    source_accessed_at: str
    source_file_name: str
    original_row_json: Mapping[str, str]

    def values(self) -> dict[str, Any]:
        return {
            "source_resource_id": self.source_resource_id,
            "facility_number": self.facility_number,
            "facility_name": self.facility_name,
            "facility_type": self.facility_type,
            "program_type": self.program_type,
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
    )


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
    existing = connection.execute(
        select(hosted_facility_reference_records).where(
            hosted_facility_reference_records.c.source_resource_id
            == record.source_resource_id,
            hosted_facility_reference_records.c.facility_number == record.facility_number,
        )
    ).mappings().first()
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
                hosted_facility_reference_records.c.source_resource_id
                == record.source_resource_id,
                hosted_facility_reference_records.c.facility_number
                == record.facility_number,
            )
            .values(**values)
        )
    return "updated"


def _normalize_facility_row(
    row: Mapping[str, str],
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

    return (
        FacilityReferenceRecord(
            facility_number=facility_number,
            facility_name=facility_name,
            facility_type=_none_if_empty(_value(row, "Facility Type", "FAC_TYPE_DESC", "TYPE")),
            program_type=_none_if_empty(_value(row, "Program Type", "PROGRAM_TYPE")),
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
            closed_date=_date_value(row, "Closed Date", "CLOSED_DATE"),
            snapshot_date=snapshot_date,
            source_resource_id=source_metadata["source_resource_id"],
            source_resource_name=source_metadata["source_resource_name"],
            source_dataset_slug=FACILITY_REFERENCE_DATASET_SLUG,
            source_dataset_url=FACILITY_REFERENCE_DATASET_URL,
            source_accessed_at=source_accessed_at,
            source_file_name=source_file_name,
            original_row_json={key: value for key, value in row.items() if key is not None},
        ),
        tuple(warnings),
    )


def _facility_number(row: Mapping[str, str], row_shape: str) -> str:
    raw_value = _value(row, "Facility Number") if row_shape == "program" else _value(row, "FAC_NBR")
    cleaned = _clean_value(raw_value)
    return cleaned if cleaned.isdigit() else ""


def _capacity_value(row: Mapping[str, str], row_shape: str) -> int | None:
    raw_value = (
        _value(row, "Facility Capacity")
        if row_shape == "program"
        else _value(row, "CAPACITY")
    )
    cleaned = _clean_value(raw_value).replace(",", "")
    return int(cleaned) if cleaned.isdigit() else None


def _date_value(row: Mapping[str, str], *headers: str) -> str | None:
    raw_value = _value(row, *headers)
    cleaned = _clean_value(raw_value)
    if not cleaned:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%m-%d-%y"):
        try:
            return datetime.strptime(cleaned, fmt).date().isoformat()
        except ValueError:
            continue
    return None


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
    return CcldFacilityLookupRecord(
        facility_number=_row_str(row, "facility_number"),
        facility_name=_row_str(row, "facility_name"),
        city=_row_str(row, "city"),
        state=_row_str(row, "state"),
        county=_row_str(row, "county"),
        zip_code=_row_str(row, "zip"),
        facility_type=_row_str(row, "facility_type"),
        program_type=_row_str(row, "program_type"),
        capacity=_row_str(row, "capacity"),
        status=_row_str(row, "status"),
        closed_date=_row_str(row, "closed_date"),
    )


def _value(row: Mapping[str, str], *headers: str) -> str:
    normalized_row = {_normalized_header(key): value for key, value in row.items()}
    for header in headers:
        value = row.get(header)
        if value is not None:
            return _clean_value(value)
        value = normalized_row.get(_normalized_header(header))
        if value is not None:
            return _clean_value(value)
    return ""


def _row_str(row: Mapping[str, Any], key: str) -> str:
    value = row.get(key)
    if value is None:
        return ""
    return str(value)


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


def _normalized_header(value: str) -> str:
    return _HEADER_NORMALIZE_PATTERN.sub("", value.casefold())
