"""Stakeholder facility overview extract generator.

Reads from the local SQLite database that is already populated by the
normal CCLD ingestion pipeline and writes a stakeholder-ready ZIP package
containing:

- facility-overview.csv        per-facility aggregation
- substantiated-complaints.csv individual substantiated/equivalent records
- README.md                    plain-language scope and limitations
- manifest.json                generation metadata and row counts

Definitions
-----------
Substantiated/equivalent uses the same conservative keyword matching as
the hosted cross-facility triage page: a finding/resolution/status value
is substantiated-equivalent when it contains "substantiated", "founded", or
"sustained" but does NOT contain "unsubstantiated" or "not substantiated".

Boundaries
----------
- Reads only. Never writes to the database.
- Does not include raw narrative text from allegations.
- Does not add risk scores, severity scores, or rankings.
- Does not make legal conclusions, facility-wide conclusions, or
  source-completeness claims.
- Produces empty CSVs with headers if the database is absent or empty
  rather than raising.
- Optional facility reference CSV enriches facility metadata but never
  implies that zero loaded complaints means no public complaints exist.
"""
from __future__ import annotations

import csv
import json
import sqlite3
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

DEFAULT_STAKEHOLDER_EXTRACT_ROOT = Path("data/processed/stakeholder-extracts")
UNKNOWN = "not available"

# ---------------------------------------------------------------------------
# Facility reference CSV column aliases
# ---------------------------------------------------------------------------
# Each tuple lists accepted header spellings (case-insensitive, stripped) for
# that logical field. First match wins.
_FACILITY_NUMBER_ALIASES: tuple[str, ...] = (
    "facilitynumber",
    "facility number",
    "licensenumber",
    "license number",
    "license_number",
    "facility_number",
    "fac_nbr",
)
_FACILITY_NAME_ALIASES: tuple[str, ...] = (
    "facilityname",
    "facility name",
    "facility_name",
    "name",
)
_FACILITY_TYPE_ALIASES: tuple[str, ...] = (
    "facilitytype",
    "fac_type_desc",
    "facility type",
    "facility_type",
    "programtype",
    "program type",
    "program_type",
)
_STATUS_ALIASES: tuple[str, ...] = (
    "status",
    "facilitystatus",
    "facility status",
    "facility_status",
)
_CITY_ALIASES: tuple[str, ...] = ("city", "res_city")
_COUNTY_ALIASES: tuple[str, ...] = ("county",)

# ---------------------------------------------------------------------------
# Substantiated/equivalent matching — mirrors reviewer_ui._is_substantiated_equivalent
# ---------------------------------------------------------------------------
_SUBSTANTIATED_KEYWORDS: tuple[str, ...] = ("substantiated", "founded", "sustained")
_EXCLUDE_PREFIXES: tuple[str, ...] = ("unsubstantiated", "not substantiated")

# Keywords used for deterministic keyword review cues derived from non-narrative
# source-extracted fields only (finding, allegation_category).  Matches signal
# a review topic; they are NOT severity scores, risk scores, or verified findings.
_KEYWORD_REVIEW_CUE_KEYWORDS: tuple[str, ...] = (
    "sexual assault",
    "abuse",
    "neglect",
    "injury",
    "restraint",
    "runaway",
    "awol",
    "medication",
    "staff misconduct",
)


def is_substantiated_equivalent(value: str | None) -> bool:
    """Return True when *value* indicates a substantiated or equivalent finding."""
    if not value:
        return False
    normalized = " ".join(value.strip().casefold().split())
    if not normalized:
        return False
    for prefix in _EXCLUDE_PREFIXES:
        if prefix in normalized:
            return False
    return any(kw in normalized for kw in _SUBSTANTIATED_KEYWORDS)


# ---------------------------------------------------------------------------
# SQL queries (read-only, no narrative text)
# ---------------------------------------------------------------------------

_FACILITY_COMPLAINTS_SQL = """
SELECT
    f.external_facility_number  AS facility_number,
    f.facility_name,
    f.facility_type,
    f.status,
    f.county,
    c.complaint_id,
    c.complaint_control_number,
    c.complaint_received_date,
    c.report_date,
    c.finding,
    sd.source_url,
    sd.raw_sha256,
    sd.raw_path,
    CASE WHEN sd.raw_sha256 IS NOT NULL AND sd.raw_sha256 != '' THEN 1 ELSE 0 END
        AS has_traceability
FROM complaints c
JOIN facilities f ON f.facility_id = c.facility_id
JOIN source_documents sd ON sd.document_id = c.document_id
ORDER BY f.external_facility_number, c.complaint_received_date DESC
"""

_ALL_COMPLAINTS_SQL = """
SELECT
    f.external_facility_number  AS facility_number,
    c.complaint_control_number,
    c.complaint_received_date,
    c.report_date,
    c.finding,
    sd.document_type            AS complaint_type,
    sd.source_url,
    sd.raw_sha256,
    (
        SELECT GROUP_CONCAT(DISTINCT a.allegation_category)
        FROM allegations a
        WHERE a.complaint_id = c.complaint_id
          AND a.allegation_category IS NOT NULL
          AND a.allegation_category != ''
    ) AS allegation_categories
FROM complaints c
JOIN facilities f ON f.facility_id = c.facility_id
JOIN source_documents sd ON sd.document_id = c.document_id
ORDER BY f.external_facility_number, c.complaint_received_date DESC
"""

# Try to get city from facility if the column exists (populated in some setups)
_FACILITY_CITY_SQL = """
SELECT f.external_facility_number AS facility_number, NULL AS city
FROM facilities f
GROUP BY f.external_facility_number
"""

_FACILITY_SQL = """
SELECT
    f.external_facility_number AS facility_number,
    MAX(f.facility_name) AS facility_name,
    MAX(f.facility_type) AS facility_type,
    MAX(f.status) AS status,
    MAX(f.county) AS county
FROM facilities f
GROUP BY f.external_facility_number
"""


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class _FacilityRow:
    facility_number: str
    facility_name: str
    facility_type: str
    status: str
    city: str
    county: str
    loaded_complaint_count: int = 0
    substantiated_count: int = 0
    complaint_dates: list[str] = field(default_factory=list)
    source_traceability_ready: int = 0
    missing_traceability: int = 0


@dataclass(frozen=True)
class _SubstantiatedRow:
    facility_number: str
    facility_name: str
    complaint_control_number: str
    complaint_received_date: str
    report_date: str
    finding_or_resolution: str
    source_url: str
    raw_hash_or_artifact_reference: str
    reviewer_detail_path: str
    limitations: str


@dataclass(frozen=True)
class _ComplaintRecordRow:
    facility_number: str
    facility_name: str
    facility_type: str
    status: str
    city: str
    county: str
    complaint_control_number: str
    complaint_received_date: str
    report_date: str
    finding_or_resolution: str
    finding_group: str
    complaint_type: str
    allegation_category: str
    keyword_review_cues: str
    source_url: str
    raw_hash_or_artifact_reference: str
    reviewer_detail_path: str
    limitations: str


@dataclass(frozen=True)
class StakeholderExtractResult:
    output_dir: Path
    facility_overview_path: Path
    substantiated_complaints_path: Path
    readme_path: Path
    manifest_path: Path
    xlsx_path: Path
    facility_row_count: int
    substantiated_complaint_row_count: int
    git_commit: str
    input_source: str
    limitations: str
    facility_reference_csv: str
    facility_reference_row_count: int
    facility_reference_matched_count: int
    only_facility_reference_rows: bool
    complaint_records_path: Path
    complaint_record_row_count: int


# ---------------------------------------------------------------------------
# Finding group and keyword review cue derivation
# ---------------------------------------------------------------------------

def _derive_finding_group(finding: str | None) -> str:
    """Classify a source-derived finding into a broad group label.

    Groups are derived only from source-derived finding/resolution text and
    do not constitute an independent legal determination.

    - SubstantiatedOrEquivalent:    finding contains substantiated/founded/sustained
    - NotSubstantiatedOrEquivalent: finding is present but not substantiated-equivalent
    - UnknownOrMissing:             finding is absent, empty, or UNKNOWN
    """
    if not finding or finding == UNKNOWN:
        return "UnknownOrMissing"
    if is_substantiated_equivalent(finding):
        return "SubstantiatedOrEquivalent"
    return "NotSubstantiatedOrEquivalent"


def _derive_keyword_review_cues(
    finding: str | None,
    allegation_categories: str | None,
) -> str:
    """Return a review-cue label when an extracted field matches a keyword.

    Checks only source-derived non-narrative fields: finding and
    allegation_category.  Does not inspect raw allegation text.

    This is a review cue, not a severity score, not a risk score, not a
    verified finding, and not a legal classification.

    Returns UNKNOWN when no keyword matches.
    """
    parts: list[str] = []
    if finding:
        parts.append(finding)
    if allegation_categories:
        parts.append(allegation_categories)
    haystack = " ".join(parts).casefold()
    if any(keyword in haystack for keyword in _KEYWORD_REVIEW_CUE_KEYWORDS):
        return "Possible serious allegation topic"
    return UNKNOWN


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def export_stakeholder_facility_overview(
    db_path: Path,
    output_root: Path = DEFAULT_STAKEHOLDER_EXTRACT_ROOT,
    facility_reference_csv: Path | None = None,
    only_facility_reference_rows: bool = False,
) -> StakeholderExtractResult:
    """Generate a stakeholder facility overview extract package.

    If *db_path* does not exist or contains no facilities, produces empty
    CSVs with correct headers, README, manifest, and ZIP without failing.

    If *facility_reference_csv* is provided its rows are merged into
    facility-overview.csv. Facilities present in the reference CSV but
    absent from the database are included with zero complaint counts.
    Complaint-derived counts are always based only on loaded records.

    If *only_facility_reference_rows* is True, only facilities whose
    facility number appears in the reference CSV are included in output.
    Raises FacilityReferenceFilterError when used without a reference CSV.
    """
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_dir = output_root / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    if only_facility_reference_rows and facility_reference_csv is None:
        raise FacilityReferenceFilterError(
            "--only-facility-reference-rows requires --facility-reference-csv to be set."
        )

    db_exists = db_path.exists()
    input_source = db_path.as_posix() if db_exists else f"{db_path.as_posix()} (not found)"
    limitations = _limitations_sentence()

    if db_exists:
        facility_rows, substantiated_rows, complaint_sql_rows = _read_db(db_path)
    else:
        facility_rows, substantiated_rows, complaint_sql_rows = [], [], []

    # Merge optional facility reference CSV
    ref_row_count = 0
    ref_matched_count = 0
    ref_csv_value = "none"
    ref_numbers: set[str] = set()
    if facility_reference_csv is not None:
        ref_records = read_facility_reference_csv(facility_reference_csv)
        ref_row_count = len(ref_records)
        ref_csv_value = facility_reference_csv.as_posix()
        ref_numbers = {r["facility_number"] for r in ref_records}
        facility_rows, ref_matched_count = _merge_reference_facilities(
            facility_rows, ref_records
        )

    # Build enriched facility map (used to enrich complaint record rows)
    all_facility_map: dict[str, _FacilityRow] = {
        row.facility_number: row for row in facility_rows
    }

    # Build complaint record rows from all loaded complaints, enriched by facility map
    complaint_record_rows = _build_complaint_records(complaint_sql_rows, all_facility_map)

    # Apply reference-only filter when requested
    if only_facility_reference_rows:
        facility_rows = [
            r for r in facility_rows if r.facility_number in ref_numbers
        ]
        substantiated_rows = [
            r for r in substantiated_rows if r.facility_number in ref_numbers
        ]
        complaint_record_rows = [
            r for r in complaint_record_rows if r.facility_number in ref_numbers
        ]

    facility_overview_path = output_dir / "facility-overview.csv"
    substantiated_complaints_path = output_dir / "substantiated-complaints.csv"
    complaint_records_path = output_dir / "complaint-records.csv"
    readme_path = output_dir / "README.md"
    manifest_path = output_dir / "manifest.json"
    xlsx_name = f"stakeholder-facility-overview-{timestamp}.xlsx"
    xlsx_path = output_dir / xlsx_name

    _write_facility_overview_csv(facility_overview_path, facility_rows)
    _write_substantiated_complaints_csv(substantiated_complaints_path, substantiated_rows)
    _write_complaint_records_csv(complaint_records_path, complaint_record_rows)
    readme_path.write_text(_readme_text(), encoding="utf-8")

    git_commit = _get_git_commit()
    manifest = _build_manifest(
        generated_at=timestamp,
        input_source=input_source,
        facility_row_count=len(facility_rows),
        substantiated_complaint_row_count=len(substantiated_rows),
        complaint_record_row_count=len(complaint_record_rows),
        git_commit=git_commit,
        output_files=[
            "facility-overview.csv",
            "substantiated-complaints.csv",
            "complaint-records.csv",
            "README.md",
            "manifest.json",
            xlsx_name,
        ],
        limitations=limitations,
        facility_reference_csv=ref_csv_value,
        facility_reference_row_count=ref_row_count,
        facility_reference_matched_count=ref_matched_count,
        only_facility_reference_rows=only_facility_reference_rows,
    )
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    _write_xlsx_workbook(
        xlsx_path,
        facility_rows=facility_rows,
        substantiated_rows=substantiated_rows,
        complaint_record_rows=complaint_record_rows,
        manifest=manifest,
    )

    return StakeholderExtractResult(
        output_dir=output_dir,
        facility_overview_path=facility_overview_path,
        substantiated_complaints_path=substantiated_complaints_path,
        complaint_records_path=complaint_records_path,
        readme_path=readme_path,
        manifest_path=manifest_path,
        xlsx_path=xlsx_path,
        facility_row_count=len(facility_rows),
        substantiated_complaint_row_count=len(substantiated_rows),
        complaint_record_row_count=len(complaint_record_rows),
        git_commit=git_commit,
        input_source=input_source,
        limitations=limitations,
        facility_reference_csv=ref_csv_value,
        facility_reference_row_count=ref_row_count,
        facility_reference_matched_count=ref_matched_count,
        only_facility_reference_rows=only_facility_reference_rows,
    )


# ---------------------------------------------------------------------------
# Database reads
# ---------------------------------------------------------------------------

def _read_db(
    db_path: Path,
) -> tuple[list[_FacilityRow], list[_SubstantiatedRow], list[sqlite3.Row]]:
    """Read facility and complaint data from SQLite and aggregate."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        try:
            raw_rows = list(conn.execute(_FACILITY_COMPLAINTS_SQL).fetchall())
        except sqlite3.OperationalError:
            # Table does not exist yet — treat as empty
            return [], [], []
        try:
            complaint_sql_rows: list[sqlite3.Row] = list(
                conn.execute(_ALL_COMPLAINTS_SQL).fetchall()
            )
        except sqlite3.OperationalError:
            complaint_sql_rows = []

    facility_rows, substantiated_rows = _aggregate(raw_rows)
    return facility_rows, substantiated_rows, complaint_sql_rows


def _aggregate(
    raw_rows: list[sqlite3.Row],
) -> tuple[list[_FacilityRow], list[_SubstantiatedRow]]:
    facility_map: dict[str, _FacilityRow] = {}
    substantiated_rows: list[_SubstantiatedRow] = []

    for row in raw_rows:
        fnum = _str(row, "facility_number") or UNKNOWN
        if fnum not in facility_map:
            facility_map[fnum] = _FacilityRow(
                facility_number=fnum,
                facility_name=_str(row, "facility_name") or UNKNOWN,
                facility_type=_str(row, "facility_type") or UNKNOWN,
                status=_str(row, "status") or UNKNOWN,
                city=UNKNOWN,
                county=_str(row, "county") or UNKNOWN,
            )
        frow = facility_map[fnum]
        frow.loaded_complaint_count += 1

        has_trace = int(row["has_traceability"] or 0)
        if has_trace:
            frow.source_traceability_ready += 1
        else:
            frow.missing_traceability += 1

        received = _str(row, "complaint_received_date")
        if received:
            frow.complaint_dates.append(received)

        finding = _str(row, "finding")
        if is_substantiated_equivalent(finding):
            frow.substantiated_count += 1
            control_number = _str(row, "complaint_control_number") or UNKNOWN
            source_url = _str(row, "source_url") or UNKNOWN
            raw_hash = _str(row, "raw_sha256") or UNKNOWN
            detail_path = (
                f"/reviewer/records/detail?source_record_key="
                f"complaint%3Accld%3Acomplaint%3A{control_number}"
                if control_number != UNKNOWN
                else UNKNOWN
            )
            substantiated_rows.append(
                _SubstantiatedRow(
                    facility_number=fnum,
                    facility_name=frow.facility_name,
                    complaint_control_number=control_number,
                    complaint_received_date=_str(row, "complaint_received_date") or UNKNOWN,
                    report_date=_str(row, "report_date") or UNKNOWN,
                    finding_or_resolution=finding or UNKNOWN,
                    source_url=source_url,
                    raw_hash_or_artifact_reference=raw_hash,
                    reviewer_detail_path=detail_path,
                    limitations=_limitations_sentence(),
                )
            )

    facility_rows: list[_FacilityRow] = sorted(
        facility_map.values(), key=lambda f: f.facility_number
    )
    substantiated_rows.sort(
        key=lambda r: (r.facility_number, r.complaint_received_date)
    )
    return facility_rows, substantiated_rows


def _str(row: sqlite3.Row, key: str) -> str:
    val = row[key] if key in row.keys() else None
    if val is None:
        return ""
    return str(val).strip()


def _build_complaint_records(
    complaint_sql_rows: list[sqlite3.Row],
    facility_map: dict[str, _FacilityRow],
) -> list[_ComplaintRecordRow]:
    """Build complaint record rows from raw SQL rows, enriched by facility_map.

    Only source-derived non-narrative fields are used.  Raw allegation text
    is never read or included.
    """
    rows: list[_ComplaintRecordRow] = []
    for row in complaint_sql_rows:
        fnum = _str(row, "facility_number") or UNKNOWN
        frow = facility_map.get(fnum)
        facility_name = frow.facility_name if frow else UNKNOWN
        facility_type = frow.facility_type if frow else UNKNOWN
        status = frow.status if frow else UNKNOWN
        city = frow.city if frow else UNKNOWN
        county = frow.county if frow else UNKNOWN

        finding = _str(row, "finding")
        allegation_categories = _str(row, "allegation_categories")
        control_number = _str(row, "complaint_control_number") or UNKNOWN

        detail_path = (
            "/reviewer/records/detail?source_record_key="
            f"complaint%3Accld%3Acomplaint%3A{control_number}"
            if control_number != UNKNOWN
            else UNKNOWN
        )

        rows.append(
            _ComplaintRecordRow(
                facility_number=fnum,
                facility_name=facility_name,
                facility_type=facility_type,
                status=status,
                city=city,
                county=county,
                complaint_control_number=control_number,
                complaint_received_date=_str(row, "complaint_received_date") or UNKNOWN,
                report_date=_str(row, "report_date") or UNKNOWN,
                finding_or_resolution=finding or UNKNOWN,
                finding_group=_derive_finding_group(finding if finding else None),
                complaint_type=_str(row, "complaint_type") or UNKNOWN,
                allegation_category=allegation_categories or UNKNOWN,
                keyword_review_cues=_derive_keyword_review_cues(
                    finding if finding else None,
                    allegation_categories if allegation_categories else None,
                ),
                source_url=_str(row, "source_url") or UNKNOWN,
                raw_hash_or_artifact_reference=_str(row, "raw_sha256") or UNKNOWN,
                reviewer_detail_path=detail_path,
                limitations=_limitations_sentence(),
            )
        )
    return rows


# ---------------------------------------------------------------------------
# Facility reference CSV reader
# ---------------------------------------------------------------------------

class FacilityReferenceError(ValueError):
    """Raised when the facility reference CSV lacks a usable facility number column."""


class FacilityReferenceFilterError(ValueError):
    """Raised when only_facility_reference_rows is requested without a reference CSV."""


def _match_alias(
    headers: list[str], aliases: tuple[str, ...]
) -> str | None:
    """Return the first header that matches any alias (case-insensitive stripped)."""
    lower_headers = [h.strip().casefold() for h in headers]
    for alias in aliases:
        for i, lh in enumerate(lower_headers):
            if lh == alias:
                return headers[i]
    return None


def read_facility_reference_csv(
    csv_path: Path,
) -> list[dict[str, str]]:
    """Read a facility reference CSV and return normalised row dicts.

    Each returned dict has canonical keys: facility_number, facility_name,
    facility_type, status, city, county.  Unknown / missing values are the
    empty string.

    Raises FacilityReferenceError if no usable facility number column is
    found.  Duplicate facility numbers keep the first occurrence.
    """
    with csv_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        raw_rows = list(reader)
        headers = list(reader.fieldnames or [])

    if not headers and raw_rows:
        headers = list(raw_rows[0].keys())

    fnum_col = _match_alias(headers, _FACILITY_NUMBER_ALIASES)
    if fnum_col is None:
        raise FacilityReferenceError(
            f"Facility reference CSV '{csv_path}' does not contain a recognised "
            "facility/license number column. "
            f"Accepted column names (case-insensitive): "
            f"{', '.join(_FACILITY_NUMBER_ALIASES)}"
        )

    name_col = _match_alias(headers, _FACILITY_NAME_ALIASES)
    type_col = _match_alias(headers, _FACILITY_TYPE_ALIASES)
    status_col = _match_alias(headers, _STATUS_ALIASES)
    city_col = _match_alias(headers, _CITY_ALIASES)
    county_col = _match_alias(headers, _COUNTY_ALIASES)

    seen: set[str] = set()
    result: list[dict[str, str]] = []
    for raw in raw_rows:
        fnum = (raw.get(fnum_col) or "").strip()
        if not fnum:
            continue  # skip rows with no facility number
        if fnum in seen:
            continue  # first occurrence wins
        seen.add(fnum)
        result.append({
            "facility_number": fnum,
            "facility_name": (raw.get(name_col) or "").strip() if name_col else "",
            "facility_type": (raw.get(type_col) or "").strip() if type_col else "",
            "status": (raw.get(status_col) or "").strip() if status_col else "",
            "city": (raw.get(city_col) or "").strip() if city_col else "",
            "county": (raw.get(county_col) or "").strip() if county_col else "",
        })
    return result


def _merge_reference_facilities(
    complaint_rows: list[_FacilityRow],
    ref_records: list[dict[str, str]],
) -> tuple[list[_FacilityRow], int]:
    """Merge reference facility records with complaint-aggregated rows.

    Returns (merged_rows, matched_count) where matched_count is the number
    of reference facilities that already had loaded complaint records.

    Reference metadata enriches existing rows (fills in blank city/name/type
    from reference when the complaint aggregate returned UNKNOWN).  Reference
    facilities with no loaded complaints are appended with zero counts.
    """
    complaint_map: dict[str, _FacilityRow] = {
        row.facility_number: row for row in complaint_rows
    }
    matched = 0
    for ref in ref_records:
        fnum = ref["facility_number"]
        if fnum in complaint_map:
            matched += 1
            existing = complaint_map[fnum]
            # Enrich blank fields from reference without overwriting loaded data
            complaint_map[fnum] = _FacilityRow(
                facility_number=fnum,
                facility_name=(
                    existing.facility_name
                    if existing.facility_name != UNKNOWN
                    else (ref["facility_name"] or UNKNOWN)
                ),
                facility_type=(
                    existing.facility_type
                    if existing.facility_type != UNKNOWN
                    else (ref["facility_type"] or UNKNOWN)
                ),
                status=(
                    existing.status
                    if existing.status != UNKNOWN
                    else (ref["status"] or UNKNOWN)
                ),
                city=(
                    existing.city
                    if existing.city != UNKNOWN
                    else (ref["city"] or UNKNOWN)
                ),
                county=(
                    existing.county
                    if existing.county != UNKNOWN
                    else (ref["county"] or UNKNOWN)
                ),
                loaded_complaint_count=existing.loaded_complaint_count,
                substantiated_count=existing.substantiated_count,
                complaint_dates=existing.complaint_dates,
                source_traceability_ready=existing.source_traceability_ready,
                missing_traceability=existing.missing_traceability,
            )
        else:
            # Reference-only facility — zero loaded complaints
            complaint_map[fnum] = _FacilityRow(
                facility_number=fnum,
                facility_name=ref["facility_name"] or UNKNOWN,
                facility_type=ref["facility_type"] or UNKNOWN,
                status=ref["status"] or UNKNOWN,
                city=ref["city"] or UNKNOWN,
                county=ref["county"] or UNKNOWN,
            )

    merged: list[_FacilityRow] = sorted(
        complaint_map.values(), key=lambda r: r.facility_number
    )
    return merged, matched


# ---------------------------------------------------------------------------
# CSV writers
# ---------------------------------------------------------------------------

_FACILITY_OVERVIEW_FIELDS = (
    "FacilityNumber",
    "FacilityName",
    "FacilityType",
    "Status",
    "City",
    "County",
    "LoadedComplaintCount",
    "SubstantiatedOrEquivalentCount",
    "EarliestComplaintDate",
    "MostRecentComplaintDate",
    "LoadedDateRange",
    "SourceTraceabilityReadyCount",
    "MissingTraceabilityCount",
    "ComplaintDataLoadedStatus",
    "SourceSnapshotOrInput",
    "Limitations",
)

_SUBSTANTIATED_COMPLAINTS_FIELDS = (
    "FacilityNumber",
    "FacilityName",
    "ComplaintControlNumber",
    "ComplaintReceivedDate",
    "ReportDate",
    "FindingOrResolution",
    "SourceUrl",
    "RawHashOrArtifactReference",
    "ReviewerDetailPath",
    "Limitations",
)


def _write_facility_overview_csv(path: Path, facility_rows: list[_FacilityRow]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_FACILITY_OVERVIEW_FIELDS)
        writer.writeheader()
        for frow in facility_rows:
            dates = sorted(d for d in frow.complaint_dates if d)
            earliest = dates[0] if dates else UNKNOWN
            most_recent = dates[-1] if dates else UNKNOWN
            date_range = (
                f"{earliest} to {most_recent}"
                if dates
                else UNKNOWN
            )
            loaded_status = (
                "Complaints loaded"
                if frow.loaded_complaint_count > 0
                else "No complaints loaded"
            )
            writer.writerow(
                {
                    "FacilityNumber": frow.facility_number,
                    "FacilityName": frow.facility_name,
                    "FacilityType": frow.facility_type,
                    "Status": frow.status,
                    "City": frow.city,
                    "County": frow.county,
                    "LoadedComplaintCount": frow.loaded_complaint_count,
                    "SubstantiatedOrEquivalentCount": frow.substantiated_count,
                    "EarliestComplaintDate": earliest,
                    "MostRecentComplaintDate": most_recent,
                    "LoadedDateRange": date_range,
                    "SourceTraceabilityReadyCount": frow.source_traceability_ready,
                    "MissingTraceabilityCount": frow.missing_traceability,
                    "ComplaintDataLoadedStatus": loaded_status,
                    "SourceSnapshotOrInput": UNKNOWN,
                    "Limitations": _limitations_sentence(),
                }
            )


def _write_substantiated_complaints_csv(
    path: Path, substantiated_rows: list[_SubstantiatedRow]
) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_SUBSTANTIATED_COMPLAINTS_FIELDS)
        writer.writeheader()
        for row in substantiated_rows:
            writer.writerow(
                {
                    "FacilityNumber": row.facility_number,
                    "FacilityName": row.facility_name,
                    "ComplaintControlNumber": row.complaint_control_number,
                    "ComplaintReceivedDate": row.complaint_received_date,
                    "ReportDate": row.report_date,
                    "FindingOrResolution": row.finding_or_resolution,
                    "SourceUrl": row.source_url,
                    "RawHashOrArtifactReference": row.raw_hash_or_artifact_reference,
                    "ReviewerDetailPath": row.reviewer_detail_path,
                    "Limitations": row.limitations,
                }
            )


_COMPLAINT_RECORDS_FIELDS = (
    "FacilityNumber",
    "FacilityName",
    "FacilityType",
    "Status",
    "City",
    "County",
    "ComplaintControlNumber",
    "ComplaintReceivedDate",
    "ReportDate",
    "FindingOrResolution",
    "FindingGroup",
    "ComplaintType",
    "AllegationCategory",
    "KeywordReviewCues",
    "SourceUrl",
    "RawHashOrArtifactReference",
    "ReviewerDetailPath",
    "Limitations",
)


def _write_complaint_records_csv(
    path: Path, complaint_record_rows: list[_ComplaintRecordRow]
) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_COMPLAINT_RECORDS_FIELDS)
        writer.writeheader()
        for row in complaint_record_rows:
            writer.writerow(
                {
                    "FacilityNumber": row.facility_number,
                    "FacilityName": row.facility_name,
                    "FacilityType": row.facility_type,
                    "Status": row.status,
                    "City": row.city,
                    "County": row.county,
                    "ComplaintControlNumber": row.complaint_control_number,
                    "ComplaintReceivedDate": row.complaint_received_date,
                    "ReportDate": row.report_date,
                    "FindingOrResolution": row.finding_or_resolution,
                    "FindingGroup": row.finding_group,
                    "ComplaintType": row.complaint_type,
                    "AllegationCategory": row.allegation_category,
                    "KeywordReviewCues": row.keyword_review_cues,
                    "SourceUrl": row.source_url,
                    "RawHashOrArtifactReference": row.raw_hash_or_artifact_reference,
                    "ReviewerDetailPath": row.reviewer_detail_path,
                    "Limitations": row.limitations,
                }
            )


# ---------------------------------------------------------------------------
# README
# ---------------------------------------------------------------------------

def _readme_text() -> str:
    return """\
# Stakeholder Facility Overview Extract

This extract is a review aid derived from locally loaded public CCLD complaint
records. It is not a certified report, legal finding, or source-completeness
proof.

## What this extract is

A summary of facility-level complaint counts and key fields drawn from records
that were loaded into the local SQLite database from publicly available CCLD
complaint report data.

## What this extract is not

- It does not make legal conclusions.
- It does not make facility-wide conclusions about a facility's conduct, safety,
  or compliance.
- It does not claim to be source-complete. Zero or low counts do not prove that
  no complaints exist; they reflect only what was loaded.
- It does not independently verify any finding or allegation. Finding/resolution
  values are source-derived values extracted from publicly available reports.
- It does not include verified severity determinations, risk scores, or rankings.
- It does not include raw narrative allegation text.

## Source of record

The public CCLD portal (ccld.dss.ca.gov) remains the source of record.
Verify important details against the public source before citing this extract.

## Counts and coverage

Counts are based only on currently loaded records. A facility may have additional
complaint records in the public source that were not retrieved or loaded.

## Finding/resolution values

Finding/resolution values such as "Substantiated", "Founded", or "Sustained" are
extracted from publicly available CCLD complaint investigation reports and are
not independently verified by RecordsTracker. Do not restate them as independently
verified findings.

## Limitations column

Each row in facility-overview.csv, substantiated-complaints.csv, and
complaint-records.csv includes a Limitations column repeating this scope note
for use when rows are shared or excerpted outside this package.

## complaint-records.csv

This file contains one row per loaded complaint record for all facilities in
this extract, regardless of finding/resolution status.

- **FindingGroup** classifies each record into SubstantiatedOrEquivalent,
  NotSubstantiatedOrEquivalent, or UnknownOrMissing based on the source-derived
  finding value. This is not an independent legal determination.
- **ComplaintType** is a source-derived document type field when available;
  otherwise "not available".
- **AllegationCategory** is a source-derived category label when extracted;
  otherwise "not available". Raw narrative allegation text is not included.
- **KeywordReviewCues** is a deterministic keyword-based review-cue label
  derived from source-extracted non-narrative fields (finding, allegation
  category). A match signals a possible serious allegation topic as a review
  aid only. It is not a severity score, not a risk score, not a verified
  finding, and not a legal classification. A non-match does not confirm the
  absence of serious topics.
- Counts reflect only loaded records. Additional complaint records may exist
  in the public source that were not retrieved or loaded.
"""


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

def _build_manifest(
    *,
    generated_at: str,
    input_source: str,
    facility_row_count: int,
    substantiated_complaint_row_count: int,
    complaint_record_row_count: int,
    git_commit: str,
    output_files: list[str],
    limitations: str,
    facility_reference_csv: str,
    facility_reference_row_count: int,
    facility_reference_matched_count: int,
    only_facility_reference_rows: bool,
) -> dict[str, Any]:
    return {
        "generated_at": generated_at,
        "script_name": "export-stakeholder-facility-overview.ps1",
        "input_source": input_source,
        "output_files": output_files,
        "facility_row_count": facility_row_count,
        "substantiated_complaint_row_count": substantiated_complaint_row_count,
        "complaint_record_row_count": complaint_record_row_count,
        "git_commit": git_commit,
        "facility_reference_csv": facility_reference_csv,
        "facility_reference_row_count": facility_reference_row_count,
        "facility_reference_matched_count": facility_reference_matched_count,
        "only_facility_reference_rows": only_facility_reference_rows,
        "limitations": limitations,
    }


def _limitations_sentence() -> str:
    return (
        "Review aid over loaded source-derived records only. "
        "Does not make legal conclusions, facility-wide conclusions, "
        "source-completeness claims, verified severity claims, or abuse/neglect findings. "
        "Public CCLD portal remains the source of record."
    )


# ---------------------------------------------------------------------------
# Excel workbook writer
# ---------------------------------------------------------------------------

_XLSX_MAX_COL_WIDTH = 60


def _facility_overview_row_dicts(
    facility_rows: list[_FacilityRow],
) -> list[dict[str, Any]]:
    """Build row dicts for the facility-overview worksheet."""
    lim = _limitations_sentence()
    result: list[dict[str, Any]] = []
    for frow in facility_rows:
        dates = sorted(d for d in frow.complaint_dates if d)
        earliest = dates[0] if dates else UNKNOWN
        most_recent = dates[-1] if dates else UNKNOWN
        date_range = f"{earliest} to {most_recent}" if dates else UNKNOWN
        loaded_status = (
            "Complaints loaded" if frow.loaded_complaint_count > 0 else "No complaints loaded"
        )
        result.append(
            {
                "FacilityNumber": frow.facility_number,
                "FacilityName": frow.facility_name,
                "FacilityType": frow.facility_type,
                "Status": frow.status,
                "City": frow.city,
                "County": frow.county,
                "LoadedComplaintCount": frow.loaded_complaint_count,
                "SubstantiatedOrEquivalentCount": frow.substantiated_count,
                "EarliestComplaintDate": earliest,
                "MostRecentComplaintDate": most_recent,
                "LoadedDateRange": date_range,
                "SourceTraceabilityReadyCount": frow.source_traceability_ready,
                "MissingTraceabilityCount": frow.missing_traceability,
                "ComplaintDataLoadedStatus": loaded_status,
                "SourceSnapshotOrInput": UNKNOWN,
                "Limitations": lim,
            }
        )
    return result


def _substantiated_row_dicts(
    substantiated_rows: list[_SubstantiatedRow],
) -> list[dict[str, Any]]:
    """Build row dicts for the substantiated-complaints worksheet."""
    return [
        {
            "FacilityNumber": row.facility_number,
            "FacilityName": row.facility_name,
            "ComplaintControlNumber": row.complaint_control_number,
            "ComplaintReceivedDate": row.complaint_received_date,
            "ReportDate": row.report_date,
            "FindingOrResolution": row.finding_or_resolution,
            "SourceUrl": row.source_url,
            "RawHashOrArtifactReference": row.raw_hash_or_artifact_reference,
            "ReviewerDetailPath": row.reviewer_detail_path,
            "Limitations": row.limitations,
        }
        for row in substantiated_rows
    ]


def _complaint_record_row_dicts(
    complaint_record_rows: list[_ComplaintRecordRow],
) -> list[dict[str, Any]]:
    """Build row dicts for the complaint-records worksheet."""
    return [
        {
            "FacilityNumber": row.facility_number,
            "FacilityName": row.facility_name,
            "FacilityType": row.facility_type,
            "Status": row.status,
            "City": row.city,
            "County": row.county,
            "ComplaintControlNumber": row.complaint_control_number,
            "ComplaintReceivedDate": row.complaint_received_date,
            "ReportDate": row.report_date,
            "FindingOrResolution": row.finding_or_resolution,
            "FindingGroup": row.finding_group,
            "ComplaintType": row.complaint_type,
            "AllegationCategory": row.allegation_category,
            "KeywordReviewCues": row.keyword_review_cues,
            "SourceUrl": row.source_url,
            "RawHashOrArtifactReference": row.raw_hash_or_artifact_reference,
            "ReviewerDetailPath": row.reviewer_detail_path,
            "Limitations": row.limitations,
        }
        for row in complaint_record_rows
    ]


def _xlsx_autosize_columns(ws: Any, col_letter_fn: Any) -> None:
    """Auto-size worksheet columns, capped at _XLSX_MAX_COL_WIDTH characters."""
    for col_cells in ws.columns:
        col_letter = col_letter_fn(col_cells[0].column)
        max_len = max(
            (len(str(cell.value or "")) for cell in col_cells),
            default=0,
        )
        ws.column_dimensions[col_letter].width = max(
            min(max_len + 2, _XLSX_MAX_COL_WIDTH), 8
        )


def _xlsx_data_sheet(
    ws: Any,
    *,
    fields: tuple[str, ...],
    rows: list[dict[str, Any]],
    bold_font: Any,
    col_letter_fn: Any,
) -> None:
    """Write bold headers and data rows to a worksheet.

    Freezes the header row, applies auto-filter, and auto-sizes columns.
    The Limitations column is last in all field tuples.
    """
    for col_idx, field_name in enumerate(fields, 1):
        cell = ws.cell(row=1, column=col_idx, value=field_name)
        cell.font = bold_font
    for row_dict in rows:
        ws.append([row_dict.get(f, "") for f in fields])
    ws.freeze_panes = "A2"
    if ws.max_row >= 1 and ws.max_column >= 1:
        ws.auto_filter.ref = ws.dimensions
    # Apply hyperlinks to SourceUrl column and wrap_text to Limitations column.
    source_url_col: int | None = None
    limitations_col: int | None = None
    for _col_idx, _fname in enumerate(fields, 1):
        if _fname == "SourceUrl":
            source_url_col = _col_idx
        elif _fname == "Limitations":
            limitations_col = _col_idx
    for _row_idx in range(2, ws.max_row + 1):
        if source_url_col is not None:
            _cell = ws.cell(row=_row_idx, column=source_url_col)
            _val = str(_cell.value or "")
            if _val.startswith("http"):
                _cell.hyperlink = _val
        if limitations_col is not None:
            ws.cell(row=_row_idx, column=limitations_col).alignment = Alignment(
                wrap_text=True
            )
    _xlsx_autosize_columns(ws, col_letter_fn)


def _xlsx_populate_readme_sheet(
    ws: Any,
    *,
    manifest: dict[str, Any],
    bold_font: Any,
) -> None:
    """Populate the README worksheet with scope, limitations, and key details."""

    def _row(col_a: str, col_b: str = "") -> None:
        ws.append([col_a, col_b])

    def _section(title: str) -> None:
        ws.append([""])
        cell = ws.cell(row=ws.max_row, column=1, value=title)
        cell.font = bold_font

    _row("Stakeholder Facility Overview — Review Aid")
    ws.cell(row=1, column=1).font = Font(bold=True, size=13)

    _section("PURPOSE")
    _row(
        "This workbook is a review aid derived from locally loaded public CCLD "
        "complaint records. It is not a certified report, legal finding, or "
        "source-completeness proof."
    )

    _section("KEY DETAILS")
    _row("Generated", str(manifest.get("generated_at", "")))
    _row("Git commit", str(manifest.get("git_commit", "")))
    _row("Facilities", str(manifest.get("facility_row_count", 0)))
    _row(
        "Substantiated/equivalent complaints",
        str(manifest.get("substantiated_complaint_row_count", 0)),
    )
    _row("All loaded complaint records", str(manifest.get("complaint_record_row_count", 0)))
    _row("Facility reference CSV", str(manifest.get("facility_reference_csv", "none")))
    _row("Facility reference rows", str(manifest.get("facility_reference_row_count", 0)))
    _row(
        "Reference rows matched to loaded complaints",
        str(manifest.get("facility_reference_matched_count", 0)),
    )
    _row(
        "Reference-only filter applied",
        str(manifest.get("only_facility_reference_rows", False)),
    )

    _section("HOW TO USE THIS WORKBOOK")
    _row(
        "Start with the facility-overview tab for a per-facility summary. "
        "Use substantiated-complaints for individual records where the source-derived "
        "finding is substantiated or an equivalent value. "
        "Use complaint-records for all loaded complaint records regardless of finding status. "
        "Check the Manifest tab for generation metadata. "
        "Verify important details against the public CCLD portal before citing this extract."
    )

    _section("TABS INCLUDED")
    _row("README", "This tab — scope, limitations, how to use this workbook.")
    _row(
        "facility-overview",
        "Per-facility complaint counts, substantiated/equivalent counts, "
        "date ranges, and source-traceability counts.",
    )
    _row(
        "substantiated-complaints",
        "Individual complaint records where the source-derived finding "
        "indicates substantiated or an equivalent value.",
    )
    _row(
        "complaint-records",
        "All loaded complaint records regardless of finding status. "
        "Includes FindingGroup, ComplaintType, AllegationCategory, KeywordReviewCues.",
    )
    _row("Manifest", "Generation metadata, row counts, and output file list.")

    _section("COUNTS AND COVERAGE")
    _row(
        "Counts are based only on records currently loaded in the local database. "
        "A facility may have additional complaint records in the public source that "
        "were not retrieved or loaded. Zero or low counts do not prove that no "
        "complaints exist; they reflect only what was loaded."
    )

    _section("SOURCE OF RECORD")
    _row(
        "The public CCLD portal (ccld.dss.ca.gov) remains the source of record. "
        "Verify important details against the public source before citing this extract."
    )

    _section("IMPORTANT LIMITATIONS")
    _row(
        "This extract does not make legal conclusions, facility-wide conclusions, "
        "source-completeness claims, verified severity claims, or abuse/neglect findings. "
        "Finding/resolution values are source-derived and not independently verified by "
        "RecordsTracker. Raw narrative allegation text is intentionally excluded."
    )
    _row(
        "KeywordReviewCues is a deterministic keyword-based review-cue label derived from "
        "source-extracted non-narrative fields (finding, allegation category). A match "
        "signals a possible serious allegation topic as a review aid only. It is not a "
        "severity score, not a risk score, not a verified finding, and not a legal "
        "classification. A non-match does not confirm the absence of serious topics."
    )
    _row("")
    _row(str(manifest.get("limitations", "")))

    ws.column_dimensions["A"].width = 40
    ws.column_dimensions["B"].width = 80


def _write_xlsx_workbook(
    xlsx_path: Path,
    *,
    facility_rows: list[_FacilityRow],
    substantiated_rows: list[_SubstantiatedRow],
    complaint_record_rows: list[_ComplaintRecordRow],
    manifest: dict[str, Any],
) -> None:
    """Write the stakeholder Excel workbook.

    Sheet order: README, facility-overview, substantiated-complaints,
    complaint-records, Manifest.
    """
    wb = openpyxl.Workbook()
    default_sheet = wb.active
    if default_sheet is not None:
        wb.remove(default_sheet)  # remove the default "Sheet"
    bold = Font(bold=True)

    ws_readme = wb.create_sheet("README")
    _xlsx_populate_readme_sheet(ws_readme, manifest=manifest, bold_font=bold)

    ws_fo = wb.create_sheet("facility-overview")
    _xlsx_data_sheet(
        ws_fo,
        fields=_FACILITY_OVERVIEW_FIELDS,
        rows=_facility_overview_row_dicts(facility_rows),
        bold_font=bold,
        col_letter_fn=get_column_letter,
    )

    ws_sub = wb.create_sheet("substantiated-complaints")
    _xlsx_data_sheet(
        ws_sub,
        fields=_SUBSTANTIATED_COMPLAINTS_FIELDS,
        rows=_substantiated_row_dicts(substantiated_rows),
        bold_font=bold,
        col_letter_fn=get_column_letter,
    )

    ws_cr = wb.create_sheet("complaint-records")
    _xlsx_data_sheet(
        ws_cr,
        fields=_COMPLAINT_RECORDS_FIELDS,
        rows=_complaint_record_row_dicts(complaint_record_rows),
        bold_font=bold,
        col_letter_fn=get_column_letter,
    )

    ws_manifest = wb.create_sheet("Manifest")
    ws_manifest.append(["Key", "Value"])
    ws_manifest.cell(row=1, column=1).font = bold
    ws_manifest.cell(row=1, column=2).font = bold
    for key, value in manifest.items():
        if isinstance(value, list):
            ws_manifest.append([key, "; ".join(str(v) for v in value)])
        else:
            ws_manifest.append([key, str(value) if value is not None else ""])
    ws_manifest.freeze_panes = "A2"
    ws_manifest.auto_filter.ref = ws_manifest.dimensions
    ws_manifest.column_dimensions["A"].width = 40
    ws_manifest.column_dimensions["B"].width = 80

    wb.save(xlsx_path)


# ---------------------------------------------------------------------------
# Git commit helper
# ---------------------------------------------------------------------------

def _get_git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        commit = result.stdout.strip()
        return commit if commit else "unknown"
    except Exception:
        return "unknown"
