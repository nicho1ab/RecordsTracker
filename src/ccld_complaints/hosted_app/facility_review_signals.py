# ruff: noqa: E501

from __future__ import annotations

import csv
import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

FACILITY_REVIEW_SIGNALS_CSVS_ENV = "CCLD_FACILITY_REVIEW_SIGNALS_CSVS"
DEFAULT_FACILITY_REVIEW_SIGNAL_PATHS = (
    Path("data/raw/source-profiling/HomeCare06072026.csv"),
    Path("data/raw/source-profiling/CHILDCAREHOMEmorethan806072026.csv"),
    Path("data/raw/source-profiling/ChildCareCenters06072026.csv"),
    Path("data/raw/source-profiling/24HourResidentialCareforChildren06072026.csv"),
    Path("data/raw/source-profiling/FosterFamilyAgencies06072026.csv"),
)

_SUPPORTED_PROGRAM_SUMMARY_COLUMNS = (
    "Facility Type",
    "Facility Number",
    "Facility Name",
    "Facility City",
    "Facility State",
    "Facility Zip",
    "County Name",
    "Regional Office",
    "Facility Capacity",
    "Facility Status",
    "License First Date",
    "Closed Date",
    "Last Visit Date",
    "Inspection Visits",
    "Complaint Visits",
    "Other Visits",
    "Total Visits",
    "Citation Numbers",
    "POC Dates",
    "Inspect TypeA",
    "Inspect TypeB",
    "Other TypeA",
    "Other TypeB",
)


@dataclass(frozen=True)
class FacilityReviewSignalRecord:
    facility_number: str
    facility_name: str
    facility_type: str
    city: str
    state: str
    zip_code: str
    county: str
    regional_office: str
    capacity: str
    status: str
    license_first_date: str
    closed_date: str
    last_visit_date: str
    inspection_visit_count: int
    complaint_visit_count: int
    other_visit_count: int
    total_visit_count: int
    citation_count: int
    type_a_citation_count: int
    type_b_citation_count: int
    poc_date_count: int
    source_dataset_label: str


@dataclass(frozen=True)
class FacilityReviewSignalsSummary:
    facility_number: str
    facility_name: str
    facility_types: tuple[str, ...]
    statuses: tuple[str, ...]
    capacities: tuple[str, ...]
    counties: tuple[str, ...]
    regional_offices: tuple[str, ...]
    license_first_dates: tuple[str, ...]
    closed_dates: tuple[str, ...]
    last_visit_date: str
    inspection_visit_count: int
    complaint_visit_count: int
    other_visit_count: int
    total_visit_count: int
    citation_count: int
    type_a_citation_count: int
    type_b_citation_count: int
    poc_date_count: int
    source_dataset_labels: tuple[str, ...]
    review_cues: tuple[str, ...]


@dataclass(frozen=True)
class FacilityReviewSignalsLoadResult:
    summaries: tuple[FacilityReviewSignalsSummary, ...]
    loaded_source_count: int
    unsupported_source_count: int
    skipped_malformed_row_count: int
    skipped_unsupported_row_count: int
    parsed_row_count: int

    def summary_for_facility(
        self,
        facility_number: str,
    ) -> FacilityReviewSignalsSummary | None:
        for summary in self.summaries:
            if summary.facility_number == facility_number:
                return summary
        return None


def load_active_facility_review_signals() -> FacilityReviewSignalsLoadResult:
    configured_paths = os.environ.get(FACILITY_REVIEW_SIGNALS_CSVS_ENV)
    if configured_paths:
        paths = tuple(Path(value) for value in configured_paths.split(os.pathsep) if value)
    else:
        paths = DEFAULT_FACILITY_REVIEW_SIGNAL_PATHS
    return load_facility_review_signals(paths)


def load_facility_review_signals(
    paths: Iterable[Path],
) -> FacilityReviewSignalsLoadResult:
    records: list[FacilityReviewSignalRecord] = []
    loaded_source_count = 0
    unsupported_source_count = 0
    skipped_malformed_row_count = 0
    skipped_unsupported_row_count = 0
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        file_result = _load_signal_records_from_path(path)
        if file_result.supported:
            loaded_source_count += 1
        else:
            unsupported_source_count += 1
        records.extend(file_result.records)
        skipped_malformed_row_count += file_result.skipped_malformed_row_count
        skipped_unsupported_row_count += file_result.skipped_unsupported_row_count
    unique_records = tuple(dict.fromkeys(records))
    return FacilityReviewSignalsLoadResult(
        summaries=_summaries_from_records(unique_records),
        loaded_source_count=loaded_source_count,
        unsupported_source_count=unsupported_source_count,
        skipped_malformed_row_count=skipped_malformed_row_count,
        skipped_unsupported_row_count=skipped_unsupported_row_count,
        parsed_row_count=len(unique_records),
    )


@dataclass(frozen=True)
class _FileLoadResult:
    supported: bool
    records: tuple[FacilityReviewSignalRecord, ...]
    skipped_malformed_row_count: int
    skipped_unsupported_row_count: int


def _load_signal_records_from_path(path: Path) -> _FileLoadResult:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
            reader = csv.reader(csv_file)
            try:
                header = next(reader)
            except StopIteration:
                return _FileLoadResult(False, (), 0, 0)
            if not _supports_program_summary_shape(tuple(header)):
                return _FileLoadResult(False, (), 0, 0)
            records: list[FacilityReviewSignalRecord] = []
            malformed_count = 0
            unsupported_row_count = 0
            expected_column_count = len(header)
            for row in reader:
                if len(row) != expected_column_count:
                    malformed_count += 1
                    continue
                record = _record_from_program_summary_row(dict(zip(header, row, strict=True)), path.name)
                if record is None:
                    unsupported_row_count += 1
                else:
                    records.append(record)
    except (OSError, UnicodeDecodeError, csv.Error):
        return _FileLoadResult(False, (), 0, 0)
    return _FileLoadResult(True, tuple(records), malformed_count, unsupported_row_count)


def _supports_program_summary_shape(header: tuple[str, ...]) -> bool:
    return all(column in header for column in _SUPPORTED_PROGRAM_SUMMARY_COLUMNS)


def _record_from_program_summary_row(
    row: dict[str, str],
    source_dataset_label: str,
) -> FacilityReviewSignalRecord | None:
    facility_number = _clean_value(row.get("Facility Number"))
    if not facility_number.isdigit():
        return None
    return FacilityReviewSignalRecord(
        facility_number=facility_number,
        facility_name=_clean_value(row.get("Facility Name")),
        facility_type=_clean_value(row.get("Facility Type")),
        city=_clean_value(row.get("Facility City")),
        state=_clean_value(row.get("Facility State")),
        zip_code=_clean_value(row.get("Facility Zip")),
        county=_clean_value(row.get("County Name")),
        regional_office=_clean_value(row.get("Regional Office")),
        capacity=_clean_value(row.get("Facility Capacity")),
        status=_clean_value(row.get("Facility Status")),
        license_first_date=_normalize_date(row.get("License First Date")),
        closed_date=_normalize_date(row.get("Closed Date")),
        last_visit_date=_normalize_date(row.get("Last Visit Date")),
        inspection_visit_count=_safe_int(row.get("Inspection Visits")),
        complaint_visit_count=_safe_int(row.get("Complaint Visits")),
        other_visit_count=_safe_int(row.get("Other Visits")),
        total_visit_count=_safe_int(row.get("Total Visits")),
        citation_count=_count_list_values(row.get("Citation Numbers")),
        type_a_citation_count=_count_list_values(row.get("Inspect TypeA"))
        + _count_list_values(row.get("Other TypeA")),
        type_b_citation_count=_count_list_values(row.get("Inspect TypeB"))
        + _count_list_values(row.get("Other TypeB")),
        poc_date_count=_count_list_values(row.get("POC Dates")),
        source_dataset_label=source_dataset_label,
    )


def _summaries_from_records(
    records: tuple[FacilityReviewSignalRecord, ...],
) -> tuple[FacilityReviewSignalsSummary, ...]:
    grouped: dict[str, list[FacilityReviewSignalRecord]] = {}
    for record in records:
        grouped.setdefault(record.facility_number, []).append(record)
    summaries = tuple(
        _summary_from_records(facility_number, tuple(group_records))
        for facility_number, group_records in grouped.items()
    )
    return tuple(sorted(summaries, key=lambda summary: summary.facility_number))


def _summary_from_records(
    facility_number: str,
    records: tuple[FacilityReviewSignalRecord, ...],
) -> FacilityReviewSignalsSummary:
    last_visit_dates = _unique_sorted(record.last_visit_date for record in records)
    closed_dates = _unique_sorted(record.closed_date for record in records)
    status_values = _unique_sorted(record.status for record in records)
    capacity_values = _unique_sorted(record.capacity for record in records)
    summary = FacilityReviewSignalsSummary(
        facility_number=facility_number,
        facility_name=_first_non_empty(record.facility_name for record in records),
        facility_types=_unique_sorted(record.facility_type for record in records),
        statuses=status_values,
        capacities=capacity_values,
        counties=_unique_sorted(record.county for record in records),
        regional_offices=_unique_sorted(record.regional_office for record in records),
        license_first_dates=_unique_sorted(record.license_first_date for record in records),
        closed_dates=closed_dates,
        last_visit_date=last_visit_dates[-1] if last_visit_dates else "",
        inspection_visit_count=sum(record.inspection_visit_count for record in records),
        complaint_visit_count=sum(record.complaint_visit_count for record in records),
        other_visit_count=sum(record.other_visit_count for record in records),
        total_visit_count=sum(record.total_visit_count for record in records),
        citation_count=sum(record.citation_count for record in records),
        type_a_citation_count=sum(record.type_a_citation_count for record in records),
        type_b_citation_count=sum(record.type_b_citation_count for record in records),
        poc_date_count=sum(record.poc_date_count for record in records),
        source_dataset_labels=_unique_sorted(record.source_dataset_label for record in records),
        review_cues=(),
    )
    return FacilityReviewSignalsSummary(
        **{**summary.__dict__, "review_cues": _review_cues(summary)}
    )


def _review_cues(summary: FacilityReviewSignalsSummary) -> tuple[str, ...]:
    cues: list[str] = []
    if summary.last_visit_date >= "2025-01-01":
        cues.append("Recent visit activity")
    elif summary.last_visit_date and summary.last_visit_date < "2023-01-01":
        cues.append("Long gap since last visit")
    if summary.complaint_visit_count > 0:
        cues.append("Complaint visit activity present")
    if summary.citation_count > 0 or summary.type_a_citation_count > 0 or summary.type_b_citation_count > 0:
        cues.append("Citation indicator present")
    if summary.poc_date_count > 0:
        cues.append("POC indicator present")
    if any("closed" in status.casefold() for status in summary.statuses) or summary.closed_dates:
        cues.append("Closed status in uploaded summary")
    if any(_safe_int(capacity) >= 50 for capacity in summary.capacities):
        cues.append("High-capacity facility")
    return tuple(cues)


def _clean_value(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(value.split())


def _safe_int(value: str | None) -> int:
    cleaned = _clean_value(value)
    return int(cleaned) if cleaned.isdigit() else 0


def _count_list_values(value: str | None) -> int:
    cleaned = _clean_value(value)
    if not cleaned:
        return 0
    return len(tuple(part for part in (part.strip() for part in cleaned.split(",")) if part))


def _normalize_date(value: str | None) -> str:
    cleaned = _clean_value(value)
    if not cleaned:
        return ""
    parts = cleaned.split("/")
    if len(parts) != 3:
        return cleaned
    month, day, year = parts
    if not (month.isdigit() and day.isdigit() and year.isdigit() and len(year) == 4):
        return cleaned
    return f"{year}-{int(month):02d}-{int(day):02d}"


def _unique_sorted(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({value for value in values if value}))


def _first_non_empty(values: Iterable[str]) -> str:
    return next((value for value in values if value), "")