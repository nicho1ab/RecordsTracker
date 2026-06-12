from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass
from pathlib import Path

DEFAULT_REVIEW_BUNDLE_DIR = Path("data/processed/review-bundle")
UNKNOWN_EXPORT_VALUE = "unknown"

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
    cr.days_received_to_first_activity,
    cr.days_received_to_visit,
    cr.days_received_to_report,
    cr.days_report_to_signed,
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
    dr.days_received_to_first_activity,
    dr.days_received_to_visit,
    dr.days_received_to_report,
    dr.days_report_to_signed,
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

EXPORTS: tuple[tuple[str, str], ...] = (
    ("complaint_review_with_source_traceability.csv", COMPLAINT_REVIEW_EXPORT_SQL),
    ("delay_review_flags_with_source_traceability.csv", DELAY_REVIEW_EXPORT_SQL),
    ("source_traceability.csv", SOURCE_TRACEABILITY_EXPORT_SQL),
)


@dataclass(frozen=True)
class ReviewBundleFile:
    path: Path
    row_count: int


@dataclass(frozen=True)
class ReviewBundleResult:
    output_dir: Path
    files: tuple[ReviewBundleFile, ...]
    readme_path: Path


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
            row_count = _write_csv(conn, sql, output_path)
            exported_files.append(ReviewBundleFile(path=output_path, row_count=row_count))

    readme_path = output_dir / "README.md"
    readme_path.write_text(_bundle_readme(), encoding="utf-8")
    return ReviewBundleResult(
        output_dir=output_dir,
        files=tuple(exported_files),
        readme_path=readme_path,
    )


def _write_csv(conn: sqlite3.Connection, sql: str, output_path: Path) -> int:
    cursor = conn.execute(sql)
    column_names = [description[0] for description in cursor.description or ()]
    rows = cursor.fetchall()
    with output_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(column_names)
        for row in rows:
            writer.writerow([_export_value(row[column_name]) for column_name in column_names])
    return len(rows)


def _export_value(value: object) -> object:
    if value is None:
        return UNKNOWN_EXPORT_VALUE
    return value


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
            "source URL, raw SHA-256 hash, local raw path, connector metadata, retrieval "
            "timestamp, and report index."
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
        "- Unknown database values are exported as \"unknown\".",
        "- Keep source URL and raw SHA-256 hash columns when sharing or citing review outputs.",
        (
            "- Verify important details against the public source document before relying "
            "on extracted fields."
        ),
    ]
    return "\n".join(lines) + "\n"