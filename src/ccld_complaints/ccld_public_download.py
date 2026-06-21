"""Local profiling and cohort generation for CCLD public download CSVs.

Reads CCLD public download CSV files (downloaded from ccld.dss.ca.gov) and:
- Profiles each file: row count, header count, row-width warnings, facility
  type/status/county counts, and facility-number presence.
- Emits a normalized facility-reference CSV with canonical field names for use
  with the stakeholder extract's -FacilityReferenceCsv parameter.
- Supports optional filtering by FacilityType and FacilityStatus to produce
  targeted cohort CSVs.

Boundaries
----------
- Reads only. Does not write to any database.
- Does not parse trailing Complaint Info columns into complaint records.
- Does not import rows into canonical database tables.
- Does not make network requests.
- Public portal remains source of record. Reference CSV rows are reference aids
  only. Absence or zero counts is not source completeness.
- Does not add risk scores, legal conclusions, facility-wide conclusions, or
  source-completeness claims.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Standard CCLD public download CSV structure
# ---------------------------------------------------------------------------
# All five CCLD public download files share this 31-column header. The last
# column, "Complaint Info-...", holds zero or more repeated groups of
# complaint-event values beyond the header column count. Rows with extra
# values are tolerated; the leading HEADER_COL_COUNT values are kept.

CCLD_DOWNLOAD_HEADER_COL_COUNT = 31

# Canonical column indices (0-based) within the standard header
_COL_FACILITY_TYPE = 0
_COL_FACILITY_NUMBER = 1
_COL_FACILITY_NAME = 2
_COL_FACILITY_CITY = 7
_COL_COUNTY_NAME = 10
_COL_FACILITY_CAPACITY = 12
_COL_FACILITY_STATUS = 13
_COL_LICENSE_FIRST_DATE = 14
_COL_CLOSED_DATE = 15
_COL_LAST_VISIT_DATE = 16

# Normalized output column names
FACILITY_REFERENCE_FIELDS: tuple[str, ...] = (
    "FacilityNumber",
    "FacilityName",
    "FacilityType",
    "ProgramType",
    "Status",
    "City",
    "County",
    "Capacity",
    "LicenseFirstDate",
    "ClosedDate",
    "LastVisitDate",
    "SourceFile",
)

LIMITATIONS_NOTE = (
    "Reference aid derived from CCLD public download CSV. "
    "Public CCLD portal (ccld.dss.ca.gov) is the source of record. "
    "Absence or zero counts is not source completeness."
)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class FacilityRefRow:
    facility_number: str
    facility_name: str
    facility_type: str
    program_type: str  # not present in CCLD download files — empty by default
    status: str
    city: str
    county: str
    capacity: str
    license_first_date: str
    closed_date: str
    last_visit_date: str
    source_file: str


@dataclass
class ParsedDownloadFile:
    path: Path
    file_name: str
    row_count: int
    header_count: int
    row_width_warning_count: int
    facility_number_present: bool
    facility_type_counts: dict[str, int] = field(default_factory=dict)
    status_counts: dict[str, int] = field(default_factory=dict)
    county_counts: dict[str, int] = field(default_factory=dict)
    rows: list[FacilityRefRow] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_ccld_download_csv(path: Path) -> ParsedDownloadFile:
    """Parse a single CCLD public download CSV.

    Tolerates rows with extra trailing complaint-info values beyond the
    declared header column count.  Only the first CCLD_DOWNLOAD_HEADER_COL_COUNT
    values in each data row are used.

    Raises ValueError if the file cannot be read.
    """
    content = path.read_bytes()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.reader(text.splitlines())
    rows_raw = list(reader)

    if not rows_raw:
        return ParsedDownloadFile(
            path=path, file_name=path.name,
            row_count=0, header_count=0,
            row_width_warning_count=0,
            facility_number_present=False,
        )

    header_row = rows_raw[0]
    header_count = len(header_row)
    data_rows_raw = rows_raw[1:]

    # Check facility number presence by looking for a column whose name
    # casefolds to a known alias
    _fnum_aliases = {
        "facility number", "facilitynumber", "license number",
        "licensenumber", "fac_nbr", "facility_number",
    }
    facility_number_present = any(
        h.strip().casefold() in _fnum_aliases for h in header_row
    )

    row_width_warning_count = 0
    facility_type_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    county_counts: dict[str, int] = {}
    ref_rows: list[FacilityRefRow] = []

    for raw in data_rows_raw:
        if not raw or all(v.strip() == "" for v in raw):
            continue  # skip blank rows
        if len(raw) > CCLD_DOWNLOAD_HEADER_COL_COUNT:
            row_width_warning_count += 1

        # Pad short rows so index access is safe
        padded = list(raw) + [""] * max(0, CCLD_DOWNLOAD_HEADER_COL_COUNT - len(raw))
        row = padded[:CCLD_DOWNLOAD_HEADER_COL_COUNT]

        facility_type = _val(row, _COL_FACILITY_TYPE)
        facility_number = _val(row, _COL_FACILITY_NUMBER)
        facility_name = _val(row, _COL_FACILITY_NAME)
        city = _val(row, _COL_FACILITY_CITY)
        county = _val(row, _COL_COUNTY_NAME)
        capacity = _val(row, _COL_FACILITY_CAPACITY)
        status = _val(row, _COL_FACILITY_STATUS)
        license_first_date = _val(row, _COL_LICENSE_FIRST_DATE)
        closed_date = _val(row, _COL_CLOSED_DATE)
        last_visit_date = _val(row, _COL_LAST_VISIT_DATE)

        if facility_type:
            facility_type_counts[facility_type] = (
                facility_type_counts.get(facility_type, 0) + 1
            )
        if status:
            status_counts[status] = status_counts.get(status, 0) + 1
        if county:
            county_counts[county] = county_counts.get(county, 0) + 1

        ref_rows.append(FacilityRefRow(
            facility_number=facility_number,
            facility_name=facility_name,
            facility_type=facility_type,
            program_type="",
            status=status,
            city=city,
            county=county,
            capacity=capacity,
            license_first_date=license_first_date,
            closed_date=closed_date,
            last_visit_date=last_visit_date,
            source_file=path.name,
        ))

    return ParsedDownloadFile(
        path=path,
        file_name=path.name,
        row_count=len(ref_rows),
        header_count=header_count,
        row_width_warning_count=row_width_warning_count,
        facility_number_present=facility_number_present,
        facility_type_counts=facility_type_counts,
        status_counts=status_counts,
        county_counts=county_counts,
        rows=ref_rows,
    )


def filter_rows(
    rows: list[FacilityRefRow],
    *,
    facility_type: str | None = None,
    status: str | None = None,
) -> list[FacilityRefRow]:
    """Return only rows matching the given filters (case-insensitive).

    None means "no filter" (all values pass).
    """
    result = rows
    if facility_type is not None:
        ft_lower = facility_type.casefold()
        result = [r for r in result if r.facility_type.casefold() == ft_lower]
    if status is not None:
        st_lower = status.casefold()
        result = [r for r in result if r.status.casefold() == st_lower]
    return result


def write_facility_reference_csv(
    rows: list[FacilityRefRow],
    output_path: Path,
) -> int:
    """Write normalized facility-reference CSV. Returns number of rows written."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FACILITY_REFERENCE_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "FacilityNumber": row.facility_number,
                "FacilityName": row.facility_name,
                "FacilityType": row.facility_type,
                "ProgramType": row.program_type,
                "Status": row.status,
                "City": row.city,
                "County": row.county,
                "Capacity": row.capacity,
                "LicenseFirstDate": row.license_first_date,
                "ClosedDate": row.closed_date,
                "LastVisitDate": row.last_visit_date,
                "SourceFile": row.source_file,
            })
    return len(rows)


def write_profile_json(
    parsed_files: list[ParsedDownloadFile],
    output_path: Path,
) -> None:
    """Write a profile summary JSON for all parsed files."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {
        "limitations": LIMITATIONS_NOTE,
        "files": [],
    }
    for pf in parsed_files:
        summary["files"].append({
            "file_name": pf.file_name,
            "row_count": pf.row_count,
            "header_count": pf.header_count,
            "row_width_warning_count": pf.row_width_warning_count,
            "facility_number_present": pf.facility_number_present,
            "facility_type_counts": pf.facility_type_counts,
            "status_counts": pf.status_counts,
            "county_counts": pf.county_counts,
        })
    output_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def write_profile_csv(
    parsed_files: list[ParsedDownloadFile],
    output_path: Path,
) -> None:
    """Write a flat profile summary CSV (one row per input file)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fields = (
        "file_name",
        "row_count",
        "header_count",
        "row_width_warning_count",
        "facility_number_present",
        "unique_facility_types",
        "unique_statuses",
        "unique_counties",
    )
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for pf in parsed_files:
            writer.writerow({
                "file_name": pf.file_name,
                "row_count": pf.row_count,
                "header_count": pf.header_count,
                "row_width_warning_count": pf.row_width_warning_count,
                "facility_number_present": pf.facility_number_present,
                "unique_facility_types": len(pf.facility_type_counts),
                "unique_statuses": len(pf.status_counts),
                "unique_counties": len(pf.county_counts),
            })


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _val(row: list[str], index: int) -> str:
    try:
        return row[index].strip()
    except IndexError:
        return ""
