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
"""
from __future__ import annotations

import csv
import json
import sqlite3
import subprocess
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_STAKEHOLDER_EXTRACT_ROOT = Path("data/processed/stakeholder-extracts")
UNKNOWN = "not available"

# ---------------------------------------------------------------------------
# Substantiated/equivalent matching — mirrors reviewer_ui._is_substantiated_equivalent
# ---------------------------------------------------------------------------
_SUBSTANTIATED_KEYWORDS: tuple[str, ...] = ("substantiated", "founded", "sustained")
_EXCLUDE_PREFIXES: tuple[str, ...] = ("unsubstantiated", "not substantiated")


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
class StakeholderExtractResult:
    output_dir: Path
    facility_overview_path: Path
    substantiated_complaints_path: Path
    readme_path: Path
    manifest_path: Path
    zip_path: Path
    facility_row_count: int
    substantiated_complaint_row_count: int
    git_commit: str
    input_source: str
    limitations: str


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def export_stakeholder_facility_overview(
    db_path: Path,
    output_root: Path = DEFAULT_STAKEHOLDER_EXTRACT_ROOT,
) -> StakeholderExtractResult:
    """Generate a stakeholder facility overview extract package.

    If *db_path* does not exist or contains no facilities, produces empty
    CSVs with correct headers, README, manifest, and ZIP without failing.
    """
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_dir = output_root / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    db_exists = db_path.exists()
    input_source = db_path.as_posix() if db_exists else f"{db_path.as_posix()} (not found)"
    limitations = _limitations_sentence()

    if db_exists:
        facility_rows, substantiated_rows = _read_db(db_path)
    else:
        facility_rows, substantiated_rows = [], []

    facility_overview_path = output_dir / "facility-overview.csv"
    substantiated_complaints_path = output_dir / "substantiated-complaints.csv"
    readme_path = output_dir / "README.md"
    manifest_path = output_dir / "manifest.json"
    zip_name = f"stakeholder-facility-overview-{timestamp}.zip"
    zip_path = output_dir / zip_name

    _write_facility_overview_csv(facility_overview_path, facility_rows)
    _write_substantiated_complaints_csv(substantiated_complaints_path, substantiated_rows)
    readme_path.write_text(_readme_text(), encoding="utf-8")

    git_commit = _get_git_commit()
    manifest = _build_manifest(
        generated_at=timestamp,
        input_source=input_source,
        facility_row_count=len(facility_rows),
        substantiated_complaint_row_count=len(substantiated_rows),
        git_commit=git_commit,
        output_files=[
            "facility-overview.csv",
            "substantiated-complaints.csv",
            "README.md",
            "manifest.json",
            zip_name,
        ],
        limitations=limitations,
    )
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    _write_zip(
        zip_path,
        [facility_overview_path, substantiated_complaints_path, readme_path, manifest_path],
    )

    return StakeholderExtractResult(
        output_dir=output_dir,
        facility_overview_path=facility_overview_path,
        substantiated_complaints_path=substantiated_complaints_path,
        readme_path=readme_path,
        manifest_path=manifest_path,
        zip_path=zip_path,
        facility_row_count=len(facility_rows),
        substantiated_complaint_row_count=len(substantiated_rows),
        git_commit=git_commit,
        input_source=input_source,
        limitations=limitations,
    )


# ---------------------------------------------------------------------------
# Database reads
# ---------------------------------------------------------------------------

def _read_db(
    db_path: Path,
) -> tuple[list[_FacilityRow], list[_SubstantiatedRow]]:
    """Read facility and complaint data from SQLite and aggregate."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        try:
            raw_rows = list(conn.execute(_FACILITY_COMPLAINTS_SQL).fetchall())
        except sqlite3.OperationalError:
            # Table does not exist yet — treat as empty
            return [], []

    return _aggregate(raw_rows)


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

Each row in facility-overview.csv and substantiated-complaints.csv includes a
Limitations column repeating this scope note for use when rows are shared or
excerpted outside this package.
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
    git_commit: str,
    output_files: list[str],
    limitations: str,
) -> dict[str, Any]:
    return {
        "generated_at": generated_at,
        "script_name": "export-stakeholder-facility-overview.ps1",
        "input_source": input_source,
        "output_files": output_files,
        "facility_row_count": facility_row_count,
        "substantiated_complaint_row_count": substantiated_complaint_row_count,
        "git_commit": git_commit,
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
# ZIP
# ---------------------------------------------------------------------------

def _write_zip(zip_path: Path, files: list[Path]) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in files:
            zf.write(file_path, arcname=file_path.name)


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
