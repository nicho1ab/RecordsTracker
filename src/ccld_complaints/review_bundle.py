from __future__ import annotations

import csv
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from ccld_complaints.aggregate_results import build_aggregate_result
from ccld_complaints.presentation_values import presentation_value_for_field

DEFAULT_REVIEW_BUNDLE_DIR = Path("data/processed/review-bundle")

DAYS_RECEIVED_TO_FIRST_ACTIVITY_LABEL = (
    "Days from Complaint Received to First Investigation Activity"
)
DAYS_RECEIVED_TO_VISIT_LABEL = "Days from Complaint Received to Visit"
DAYS_RECEIVED_TO_REPORT_LABEL = "Days from Complaint Received to Report"
DAYS_REPORT_TO_SIGNED_LABEL = "Days from Report to Signed"

_REVIEW_BUNDLE_PRESENTATION_FIELDS = {
    DAYS_RECEIVED_TO_FIRST_ACTIVITY_LABEL: "days_received_to_first_activity",
    DAYS_RECEIVED_TO_VISIT_LABEL: "days_received_to_visit",
    DAYS_RECEIVED_TO_REPORT_LABEL: "days_received_to_report",
    DAYS_REPORT_TO_SIGNED_LABEL: "days_report_to_signed",
}

COMPLAINT_REVIEW_EXPORT_SQL = """
SELECT
    cr.facility_number,
    cr.facility_name,
    cr.complaint_control_number,
    cr.complaint_received_date,
    cr.first_investigation_activity_date,
    cr.visit_date,
    cr.report_date,
    cr.date_signed,
    cr.finding,
    cr.allegation_count,
    cr.allegation_summary,
    cr.days_received_to_first_activity AS
        "Days from Complaint Received to First Investigation Activity",
    cr.days_received_to_visit AS "Days from Complaint Received to Visit",
    cr.days_received_to_report AS "Days from Complaint Received to Report",
    cr.days_report_to_signed AS "Days from Report to Signed",
    cr.review_delay_over_30_days,
    cr.review_delay_over_60_days,
    cr.review_delay_over_90_days,
    cr.review_delay_over_120_days,
    cr.missing_first_activity_date,
    cr.report_date_used_as_proxy,
    cr.source_url,
    sd.raw_sha256,
    cr.raw_path,
    sd.connector_name,
    sd.connector_version,
    sd.retrieved_at,
    sd.report_index
FROM complaint_review_summary cr
JOIN complaints c ON c.complaint_id = cr.complaint_id
JOIN source_documents sd ON sd.document_id = c.document_id
ORDER BY cr.facility_number, cr.complaint_received_date DESC, cr.report_date DESC
""".strip()

DELAY_REVIEW_EXPORT_SQL = """
SELECT
    dr.facility_number,
    dr.facility_name,
    dr.complaint_control_number,
    dr.complaint_received_date,
    dr.first_investigation_activity_date,
    dr.visit_date,
    dr.report_date,
    dr.date_signed,
    dr.finding,
    dr.days_received_to_first_activity AS
        "Days from Complaint Received to First Investigation Activity",
    dr.days_received_to_visit AS "Days from Complaint Received to Visit",
    dr.days_received_to_report AS "Days from Complaint Received to Report",
    dr.days_report_to_signed AS "Days from Report to Signed",
    dr.review_delay_over_30_days,
    dr.review_delay_over_60_days,
    dr.review_delay_over_90_days,
    dr.review_delay_over_120_days,
    dr.missing_first_activity_date,
    dr.report_date_used_as_proxy,
    dr.source_url,
    sd.raw_sha256,
    dr.raw_path,
    sd.connector_name,
    sd.connector_version,
    sd.retrieved_at,
    sd.report_index
FROM delay_review_flags dr
JOIN complaints c ON c.complaint_id = dr.complaint_id
JOIN source_documents sd ON sd.document_id = c.document_id
ORDER BY dr.days_received_to_report DESC, dr.complaint_received_date DESC
""".strip()

SOURCE_TRACEABILITY_EXPORT_SQL = """
SELECT *
FROM source_traceability_review
ORDER BY facility_number, report_index DESC, retrieved_at DESC
""".strip()

MULTI_FACILITY_SOURCE_TRACEABILITY_EXPORT_SQL = """
SELECT *
FROM multi_facility_source_traceability_review
ORDER BY facility_number, retrieved_at DESC, report_index DESC
""".strip()

COMPLAINT_TIMELINE_EXPORT_SQL = """
SELECT *
FROM complaint_timeline_review
ORDER BY facility_number, timeline_date, timeline_sequence, complaint_control_number
""".strip()

FIELD_TRACEABILITY_EXPORT_SQL = """
SELECT *
FROM field_source_traceability_review
ORDER BY facility_number, report_date DESC, complaint_received_date DESC, field_name
""".strip()

FACILITY_PATTERN_EXPORT_SQL = """
SELECT *
FROM facility_pattern_review
ORDER BY records_with_review_flags DESC, complaint_count DESC, facility_number
""".strip()

FACILITY_COMPARISON_EXPORT_SQL = """
SELECT *
FROM facility_comparison_review
ORDER BY facilities_with_same_category_finding DESC,
         source_document_count DESC,
         records_with_review_flags DESC,
         allegation_category,
         finding,
         facility_number
""".strip()

EXPORTS: tuple[tuple[str, str], ...] = (
    ("complaint_review_with_source_traceability.csv", COMPLAINT_REVIEW_EXPORT_SQL),
    ("delay_review_flags_with_source_traceability.csv", DELAY_REVIEW_EXPORT_SQL),
    ("source_traceability.csv", SOURCE_TRACEABILITY_EXPORT_SQL),
    (
        "multi_facility_source_traceability.csv",
        MULTI_FACILITY_SOURCE_TRACEABILITY_EXPORT_SQL,
    ),
    ("complaint_timeline_with_source_traceability.csv", COMPLAINT_TIMELINE_EXPORT_SQL),
    ("field_source_traceability.csv", FIELD_TRACEABILITY_EXPORT_SQL),
    ("facility_pattern_review.csv", FACILITY_PATTERN_EXPORT_SQL),
    ("facility_comparison_review.csv", FACILITY_COMPARISON_EXPORT_SQL),
)


@dataclass(frozen=True)
class ReviewBundleFile:
    path: Path
    row_count: int
    source_coverage_count: int = 0
    source_unavailable_count: int = 0


@dataclass(frozen=True)
class ReviewBundleResult:
    output_dir: Path
    files: tuple[ReviewBundleFile, ...]
    readme_path: Path
    manifest_path: Path


def export_review_bundle(
    db_path: Path,
    output_dir: Path = DEFAULT_REVIEW_BUNDLE_DIR,
) -> ReviewBundleResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    exported_files: list[ReviewBundleFile] = []

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        for filename, sql in EXPORTS:
            output_path = output_dir / filename
            row_count, source_coverage_count, source_unavailable_count = _write_csv(
                conn,
                sql,
                output_path,
            )
            exported_files.append(
                ReviewBundleFile(
                    path=output_path,
                    row_count=row_count,
                    source_coverage_count=source_coverage_count,
                    source_unavailable_count=source_unavailable_count,
                )
            )

    readme_path = output_dir / "README.md"
    readme_path.write_text(_bundle_readme(), encoding="utf-8")
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(_bundle_manifest(exported_files), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return ReviewBundleResult(
        output_dir=output_dir,
        files=tuple(exported_files),
        readme_path=readme_path,
        manifest_path=manifest_path,
    )


def _write_csv(
    conn: sqlite3.Connection,
    sql: str,
    output_path: Path,
) -> tuple[int, int, int]:
    cursor = conn.execute(sql)
    column_names = [description[0] for description in cursor.description or ()]
    rows = cursor.fetchall()
    with output_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(column_names)
        for row in rows:
            writer.writerow(
                [
                    _export_value(row[column_name], column_name=column_name)
                    for column_name in column_names
                ]
            )
    traceability_columns = {
        column_name for column_name in column_names if column_name in {"source_url", "raw_sha256"}
    }
    if not traceability_columns:
        return len(rows), len(rows), 0
    source_coverage_count = sum(
        all(row[column_name] not in {None, ""} for column_name in traceability_columns)
        for row in rows
    )
    return len(rows), source_coverage_count, len(rows) - source_coverage_count


def _bundle_manifest(files: list[ReviewBundleFile]) -> dict[str, object]:
    export_rows = []
    for exported_file in files:
        result = build_aggregate_result(
            value=exported_file.row_count,
            denominator="all eligible rows in the corresponding governed SQLite review view",
            eligible_count=exported_file.row_count,
            returned_count=exported_file.row_count,
            source_coverage_count=exported_file.source_coverage_count,
            source_unavailable_count=exported_file.source_unavailable_count,
            date_dimension="complaint_received_date",
        )
        export_rows.append(
            {
                "file": exported_file.path.name,
                **result.to_dict(),
            }
        )
    return {
        "manifest_version": 2,
        "record_universe": "governed local SQLite review views",
        "presentation_value_contract": (
            "Stored values remain unchanged; CSV labels distinguish verified zero, "
            "not provided, date not provided, unavailable, not applicable, and invalid states."
        ),
        "date_dimension": "complaint_received_date",
        "query_start": None,
        "query_end": None,
        "explicit_limit": None,
        "truncated": False,
        "exports": export_rows,
    }


def _export_value(value: object, *, column_name: str = "value") -> object:
    presentation_field = _REVIEW_BUNDLE_PRESENTATION_FIELDS.get(
        column_name,
        column_name,
    )
    return presentation_value_for_field(
        {presentation_field: value},
        presentation_field,
    ).export_text


def _bundle_readme() -> str:
    lines = [
        "# CCLD Complaint Review Bundle",
        "",
        (
            "This folder contains derived CSV review outputs from the local SQLite database. "
            "The public portal remains the source of record."
        ),
        "",
        "## Files",
        "",
        (
            "- complaint_review_with_source_traceability.csv: complaint review fields with "
            "human-readable complaint milestone interval columns, source URL, raw SHA-256 "
            "hash, local raw path, connector metadata, retrieval timestamp, and report index."
        ),
        (
            "- delay_review_flags_with_source_traceability.csv: triage records with one or "
            "more review flags, plus source traceability fields."
        ),
        (
            "- source_traceability.csv: source URL, raw SHA-256 hash, local raw path, "
            "connector metadata, retrieval timestamp, report index, document type, and "
            "content type."
        ),
        (
            "- multi_facility_source_traceability.csv: one row per source document with "
            "facility context, traceability status, source metadata, and linked derived-record "
            "counts."
        ),
        (
            "- complaint_timeline_with_source_traceability.csv: complaint milestone dates "
            "and extracted event dates with source traceability. Missing dates use governed "
            "date-state labels in the derived export."
        ),
        (
            "- field_source_traceability.csv: extracted values, source text, source section, "
            "warnings, confidence, extraction method, extractor version, and source document "
            "traceability."
        ),
        (
            "- facility_pattern_review.csv: facility-level complaint counts, source document "
            "counts, allegation categories, finding mix, missingness, report-date proxy usage, "
            "review flag counts, and date ranges."
        ),
        (
            "- facility_comparison_review.csv: facility/category/finding rows with "
            "source-document counts, traceability-completeness counts, same-category/finding "
            "facility counts, and cautious scope notes."
        ),
        (
            "- manifest.json: record universe, eligible/exported counts, source coverage, "
            "date dimension/range, explicit limit, truncation status, and result cause "
            "for each CSV."
        ),
        "",
        "## Review Notes",
        "",
        (
            "- Delay review flags are screening aids for closer review, not conclusions "
            "that an investigation was delayed."
        ),
        (
            "- Use language such as \"flagged for review based on available extracted "
            "dates\" when discussing flagged records."
        ),
        (
            "- Missing database values use field-aware labels such as \"Not provided\" "
            "or \"Date not provided\"; verified numeric zero remains \"0\"."
        ),
        "- Keep source URL and raw SHA-256 hash columns when sharing or citing review outputs.",
        (
            "- Facility pattern counts and timeline rows are screening aids over the derived "
            "dataset, not findings about a facility or proof that an event did or did not occur."
        ),
        (
            "- Multi-facility traceability and comparison rows are source-review aids over "
            "the derived dataset, not conclusions about facilities, public-source completeness, "
            "or facility-wide conduct."
        ),
        (
            "- Field traceability rows are provided so reviewers can check extracted values "
            "against source text, warnings, confidence, and the public source."
        ),
        (
            "- Verify important details against the public source document before relying "
            "on extracted fields."
        ),
    ]
    return "\n".join(lines) + "\n"
