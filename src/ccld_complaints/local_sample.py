from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ccld_complaints.connectors.base import SourceDocument, SourceDocumentCandidate
from ccld_complaints.connectors.ccld import CcldFacilityReportsConnector, FacilityIngestionResult
from ccld_complaints.connectors.ccld.facility_reports import ingest_facility_reports_for_facility
from ccld_complaints.review_bundle import COMPLAINT_REVIEW_EXPORT_SQL
from ccld_complaints.storage.sqlite import initialize_database
from ccld_complaints.utils.hash import sha256_bytes

DEFAULT_SAMPLE_DB_PATH = Path("data/processed/ccld.sqlite")
DEFAULT_CCLD_FIXTURE_DIR = Path("tests/fixtures/ccld")
DEFAULT_SAMPLE_FACILITY_NUMBER = "157806098"
DEFAULT_SAMPLE_RETRIEVED_AT = "2026-06-10T00:00:00+00:00"
DATASSETTE_METADATA_SUFFIX = ".datasette-metadata.json"
_REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class SampleDatabaseResult:
    db_path: Path
    ingestion: FacilityIngestionResult


def populate_sample_database(
    db_path: Path = DEFAULT_SAMPLE_DB_PATH,
    *,
    fixture_dir: Path = DEFAULT_CCLD_FIXTURE_DIR,
) -> SampleDatabaseResult:
    initialize_database(db_path)
    connector = CcldFacilityReportsConnector(db_path=db_path, schema_dir=_REPO_ROOT / "schemas")
    detail_fixture = _resolve_fixture_path(
        fixture_dir / "raw" / f"{DEFAULT_SAMPLE_FACILITY_NUMBER}_facility_detail.html"
    )

    result = ingest_facility_reports_for_facility(
        facility_number=DEFAULT_SAMPLE_FACILITY_NUMBER,
        connector=connector,
        facility_detail_html=detail_fixture.read_text(encoding="utf-8"),
        discovered_at=DEFAULT_SAMPLE_RETRIEVED_AT,
        load_document=lambda candidate: _load_report_fixture(candidate, fixture_dir),
    )

    return SampleDatabaseResult(db_path=db_path, ingestion=result)


def datasette_command(db_path: Path) -> str:
    metadata_path = datasette_metadata_path(db_path)
    return f'datasette "{db_path.as_posix()}" --metadata "{metadata_path.as_posix()}"'


def datasette_metadata_path(db_path: Path) -> Path:
    return db_path.with_name(f"{db_path.stem}{DATASSETTE_METADATA_SUFFIX}")


def write_datasette_metadata(db_path: Path) -> Path:
    metadata_path = datasette_metadata_path(db_path)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(datasette_metadata(db_path), indent=2) + "\n",
        encoding="utf-8",
    )
    return metadata_path


def datasette_metadata(db_path: Path) -> dict[str, Any]:
    return {
        "title": "CCLD Complaints Review",
        "description": (
            "Local review database for derived CCLD complaint records. "
            "The public portal remains the source of record; delay flags are screening aids."
        ),
        "databases": {
            db_path.stem: {
                "title": "CCLD Complaints Review Database",
                "description": (
                    "Open the review_home saved query first, then use review views before "
                    "opening normalized source tables. Keep source URL and raw hash fields "
                    "when exporting review data."
                ),
                "tables": _datasette_table_metadata(),
                "queries": _datasette_saved_queries(),
            }
        },
    }


def review_workflow_lines() -> list[str]:
    return [
        "Open the review_home saved query first for task-based review paths.",
        "Open these Datasette review views first, in order:",
        "1. complaint_first_pass_review - low-noise first-pass complaint review.",
        "2. complaint_review_summary - full complaint review across facilities.",
        "3. facility_complaint_summary - facility-level counts and date range.",
        "4. delay_review_flags - triage list for records with review flags.",
        "5. source_traceability_review - source URLs, hashes, connector details, and report index.",
        "Saved queries for common workflows:",
        "- review_home - start-here task menu for local review workflows.",
        "- complaint_review_start_here - guided complaint review with source traceability.",
        "- complaints_by_facility - filter complaint review by facility number.",
        "- complaint_review_export_with_traceability - export complaint fields with source hashes.",
        "- records_with_delay_review_flags - triage review flags as screening aids only.",
        (
            "- facilities_with_delay_review_flags - find facilities with records needing "
            "closer review."
        ),
        "- source_traceability_by_facility - check source provenance for one facility.",
        "- newest_reports - review most recently retrieved source documents.",
        "Delay flags are screening aids only; verify important details against source documents.",
    ]


def _datasette_table_metadata() -> dict[str, Any]:
    delay_flag_caution = (
        "Delay and review flags are screening aids for closer review, not conclusions that an "
        "investigation was delayed. Verify source documents before making claims."
    )
    source_traceability_note = (
        "Source URL, raw SHA-256 hash, raw path, connector, retrieval time, and report index help "
        "reviewers trace each derived record back to public source evidence."
    )
    review_table_metadata = {
        "complaint_first_pass_review": {
            "title": "Complaint First-Pass Review",
            "description": (
                "Low-noise first-pass view with facility, complaint dates, finding, allegation "
                "summary, a single review flag summary, source URL, raw SHA-256 hash, raw path, "
                "connector metadata, retrieval time, report index, and IDs for lower-level "
                "follow-up. Use this before the fuller complaint_review_summary; do not treat "
                "the derived fields as official source records."
            ),
            "sort_desc": "report_date",
            "columns": {
                "facility_number": "Public CCLD facility number used for filtering.",
                "facility_name": "Facility name extracted from source reports.",
                "complaint_control_number": "Complaint control number when available.",
                "complaint_received_date": "Date the complaint was reportedly received.",
                "visit_date": "Visit date shown in the source report when available.",
                "report_date": "Report date shown in the source report.",
                "finding": "Normalized finding value from the data contract.",
                "allegation_count": "Number of allegation rows linked to the complaint.",
                "allegation_summary": "Combined allegation text for quick review.",
                "review_flags_summary": (
                    "Plain-language summary of delay or review flags. Review flags are "
                    "screening aids, not conclusions."
                ),
                "source_url": "Public source URL for checking the derived record.",
                "raw_sha256": "SHA-256 hash for the preserved raw source file.",
                "raw_path": "Local raw file path for preserved source content.",
                "connector_name": "Connector that retrieved and normalized the document.",
                "connector_version": "Connector version used for extraction.",
                "retrieved_at": "Timestamp when source content was retrieved.",
                "report_index": "CCLD report index when available.",
                "complaint_id": "Stable local complaint identifier for lower-level follow-up.",
                "document_id": "Source document identifier for lower-level source checks.",
            },
        },
        "complaint_review_summary": {
            "title": "Complaint Review Summary",
            "description": (
                "Main review view combining facility, complaint, allegation summary, delay fields, "
                "review flags, source URL, and raw path. Sort by complaint_received_date or "
                "report_date descending when reviewing newer records first. Use after "
                "complaint_first_pass_review when detailed delay fields, separate flags, or "
                "extraction confidence are needed; do not treat extracted rows as official "
                "source records. Keep source URL and raw path when exporting. "
                f"{delay_flag_caution}"
            ),
            "sort_desc": "report_date",
            "columns": {
                "facility_number": "Public CCLD facility number used for filtering.",
                "facility_name": "Facility name extracted from the source report.",
                "complaint_control_number": "Complaint control number when available.",
                "complaint_received_date": "Date the complaint was reportedly received.",
                "first_investigation_activity_date": (
                    "Earliest deterministic investigation activity date when extracted."
                ),
                "visit_date": "Visit date shown in the source report when available.",
                "report_date": "Report date shown in the source report.",
                "date_signed": "Date the report was signed when available.",
                "finding": "Normalized finding value from the data contract.",
                "allegation_count": "Number of allegation rows linked to the complaint.",
                "allegation_summary": "Combined allegation text for quick review.",
                "days_received_to_first_activity": (
                    "Days from complaint received date to first activity date when available."
                ),
                "days_received_to_visit": "Days from complaint received date to visit date.",
                "days_received_to_report": "Days from complaint received date to report date.",
                "days_report_to_signed": "Days from report date to signature date.",
                "review_delay_over_30_days": delay_flag_caution,
                "review_delay_over_60_days": delay_flag_caution,
                "review_delay_over_90_days": delay_flag_caution,
                "review_delay_over_120_days": delay_flag_caution,
                "missing_first_activity_date": (
                    "Set when complaint received date exists but first activity date is missing."
                ),
                "report_date_used_as_proxy": (
                    "Set only when report date is used as the delay review basis because earlier "
                    "activity or visit dates are unavailable."
                ),
                "extraction_confidence": "Extractor confidence value when available.",
                "source_url": "Public source URL for checking the derived record.",
                "raw_path": "Local raw file path for preserved source content.",
            },
        },
        "facility_complaint_summary": {
            "title": "Facility Complaint Summary",
            "description": (
                "One row per facility with complaint count, allegation count, complaint date "
                "range, "
                "and count of records with delay review flags. Sort by complaint_count descending "
                "to find facilities with more reviewed records. Use for local comparison, not as "
                "a complete or official facility history; verify important counts against source "
                "records before citing them."
            ),
            "sort_desc": "complaint_count",
            "columns": {
                "facility_number": "Public CCLD facility number.",
                "facility_name": "Facility name extracted from source reports.",
                "complaint_count": "Number of complaint records in the local database.",
                "allegation_count": "Number of allegation records linked to facility complaints.",
                "earliest_complaint_received_date": "Earliest complaint received date in the data.",
                "latest_complaint_received_date": "Latest complaint received date in the data.",
                "records_with_delay_review_flags": (
                    "Complaint records with at least one delay or review flag. "
                    f"{delay_flag_caution}"
                ),
            },
        },
        "delay_review_flags": {
            "title": "Delay Review Flags",
            "description": (
                "Filtered triage view showing records with one or more delay or review flags. "
                "Sort by days_received_to_visit or days_received_to_report descending to review "
                "larger calculated intervals first. Use for closer review, not as a list of "
                "delayed investigations. Preserve source URL and raw path when exporting. "
                f"{delay_flag_caution}"
            ),
            "sort_desc": "days_received_to_report",
            "columns": {
                "facility_number": "Public CCLD facility number used for filtering.",
                "complaint_control_number": "Complaint control number when available.",
                "days_received_to_first_activity": (
                    "Days from complaint received date to first activity date when available."
                ),
                "days_received_to_visit": "Days from complaint received date to visit date.",
                "days_received_to_report": "Days from complaint received date to report date.",
                "review_delay_over_30_days": delay_flag_caution,
                "review_delay_over_60_days": delay_flag_caution,
                "review_delay_over_90_days": delay_flag_caution,
                "review_delay_over_120_days": delay_flag_caution,
                "missing_first_activity_date": (
                    "Set when complaint received date exists but first activity date is missing."
                ),
                "report_date_used_as_proxy": (
                    "Set only when report date is used as the delay review basis."
                ),
                "source_url": "Public source URL for checking the derived record.",
                "raw_path": "Local raw file path for preserved source content.",
            },
        },
        "source_traceability_review": {
            "title": "Source Traceability Review",
            "description": (
                "Use this view to verify source provenance before relying on extracted fields. "
                f"{source_traceability_note} Sort by retrieved_at or report_index descending "
                "when checking newest retrieved reports first. Use before citation or export; do "
                "not use this view alone as a complaint summary."
            ),
            "sort_desc": "retrieved_at",
            "columns": {
                "facility_number": "Public CCLD facility number.",
                "facility_name": "Facility name extracted from source reports.",
                "document_id": "Stable local source document identifier.",
                "source_url": "Public source URL used for retrieval.",
                "raw_sha256": "SHA-256 hash for the preserved raw source file.",
                "raw_path": "Local path to preserved raw source content.",
                "connector_name": "Connector that retrieved and normalized the document.",
                "connector_version": "Connector version used for extraction.",
                "retrieved_at": "Timestamp when source content was retrieved.",
                "report_index": "CCLD report index when available.",
                "document_type": "Document type extracted from the source report when available.",
                "content_type": "Fetched source content type when available.",
            },
        },
    }
    return review_table_metadata | _normalized_table_metadata()


def _normalized_table_metadata() -> dict[str, Any]:
    delay_flag_caution = (
        "Delay and review flags are screening aids for closer review, not conclusions that an "
        "investigation was delayed. Verify source documents before making claims."
    )
    source_traceability_note = (
        "Source URL, raw SHA-256 hash, raw path, connector name, connector version, and "
        "retrieval timestamp preserve traceability back to public source evidence."
    )
    return {
        "facilities": {
            "title": "Facilities",
            "description": (
                "Normalized facility identifiers and descriptive fields. Use review views first "
                "for routine browsing, then this table for lower-level facility details."
            ),
            "columns": {
                "facility_id": "Stable local facility identifier.",
                "source_id": "Identifier for the public data source.",
                "external_facility_number": "Public CCLD facility number.",
                "facility_name": "Facility name from the public source.",
            },
        },
        "source_documents": {
            "title": "Source Documents",
            "description": (
                "Normalized source document records. Check this table when you need raw source "
                f"provenance below the review views. {source_traceability_note}"
            ),
            "sort_desc": "retrieved_at",
            "columns": {
                "document_id": "Stable local source document identifier.",
                "source_url": "Public source URL used for retrieval.",
                "retrieved_at": "Timestamp when source content was retrieved.",
                "raw_sha256": "SHA-256 hash for the preserved raw source file.",
                "connector_name": "Connector that retrieved and normalized the document.",
                "connector_version": "Connector version used for extraction.",
                "raw_path": "Local path to preserved raw source content.",
                "report_index": "CCLD report index when available.",
            },
        },
        "complaints": {
            "title": "Complaints",
            "description": (
                "Normalized complaint records with extracted dates, findings, delay calculations, "
                f"and review flags. {delay_flag_caution}"
            ),
            "sort_desc": "report_date",
            "columns": {
                "complaint_id": "Stable local complaint identifier.",
                "facility_id": "Facility identifier linking to facilities.",
                "document_id": "Source document identifier linking to source_documents.",
                "complaint_control_number": "Complaint control number when available.",
                "complaint_received_date": "Date the complaint was reportedly received.",
                "first_investigation_activity_date": (
                    "Earliest deterministic investigation activity date when extracted."
                ),
                "visit_date": "Visit date shown in the source report when available.",
                "report_date": "Report date shown in the source report.",
                "finding": "Normalized finding value from the data contract.",
                "review_delay_over_30_days": delay_flag_caution,
                "review_delay_over_60_days": delay_flag_caution,
                "review_delay_over_90_days": delay_flag_caution,
                "review_delay_over_120_days": delay_flag_caution,
                "missing_first_activity_date": (
                    "Set when complaint received date exists but first activity date is missing."
                ),
                "report_date_used_as_proxy": (
                    "Set only when report date is used as the delay review basis because earlier "
                    "activity or visit dates are unavailable."
                ),
            },
        },
        "allegations": {
            "title": "Allegations",
            "description": (
                "Normalized allegation text and categories linked to complaint records. Review "
                "source documents before quoting narrative content."
            ),
            "columns": {
                "allegation_id": "Stable local allegation identifier.",
                "complaint_id": "Complaint identifier linking to complaints.",
                "allegation_text": "Allegation text extracted from the source report.",
                "allegation_category": "Normalized allegation category from the data contract.",
                "finding": "Normalized allegation finding when available.",
            },
        },
        "events": {
            "title": "Events",
            "description": (
                "Normalized dated events extracted from complaint records when available. Use "
                "field-level audit details when checking uncertain extraction."
            ),
            "sort_desc": "event_date",
            "columns": {
                "event_id": "Stable local event identifier.",
                "complaint_id": "Complaint identifier linking to complaints.",
                "event_date": "Date of the extracted event.",
                "event_type": "Normalized event type.",
                "event_text": "Source text associated with the event when available.",
            },
        },
        "extraction_audit": {
            "title": "Extraction Audit",
            "description": (
                "Field-level extraction audit records for checking extraction method, source text, "
                "confidence, and warnings. Use this table when verifying important derived fields."
            ),
            "columns": {
                "audit_id": "Stable local extraction audit identifier.",
                "document_id": "Source document identifier linking to source_documents.",
                "field_name": "Canonical field name audited by the extractor.",
                "extraction_method": "Method used to extract the field.",
                "extractor_version": "Extractor version that produced the audit record.",
                "extracted_value": "Extracted value when available.",
                "confidence": "Extractor confidence value when available.",
                "source_text": "Source text used for field-level review when available.",
                "warning": "Extraction warning when available.",
            },
        },
    }


def _datasette_saved_queries() -> dict[str, Any]:
    return {
        "review_home": {
            "title": "Review Home: Start Here",
            "description": (
                "Open this first for task-based local review paths before using normalized "
                "tables. Each row points to a review view or saved query and names the source "
                "traceability fields to preserve. Use it to choose a task; do not treat it as "
                "data output for citation."
            ),
            "sql": """
SELECT
    1 AS step,
    'Review complaints' AS task,
    'complaint_first_pass_review' AS open_first,
    'Use for low-noise first-pass complaint review with source URL, raw hash, ' ||
        'connector metadata, retrieval time, report index, and IDs for follow-up.' AS when_to_use,
    'Treat extracted fields as derived review aids and keep source traceability ' ||
        'columns when exporting.' AS caution
UNION ALL
SELECT
    2,
    'Find records needing closer review',
    'records_with_delay_review_flags',
    'Use for delay triage and records flagged for review based on available extracted dates.',
    'Delay review flags are screening aids, not conclusions that an investigation was delayed.'
UNION ALL
SELECT
    3,
    'Compare facilities',
    'facility_complaint_summary',
    'Use for facility-level complaint counts, allegation counts, date ranges, ' ||
        'and counts of records with review flags.',
    'Counts summarize the local derived dataset only; verify important findings ' ||
        'against source records.'
UNION ALL
SELECT
    4,
    'Verify sources',
    'source_traceability_review',
    'Use before relying on extracted fields; check source URL, raw SHA-256 hash, ' ||
        'raw path, connector name, connector version, retrieval timestamp, and ' ||
        'report index.',
    'The public portal remains the source of record.'
UNION ALL
SELECT
    5,
    'Export CSVs',
    'complaint_review_export_with_traceability',
    'Use for accessible CSV exports with complaint review fields and source traceability columns.',
    'Keep clear headers and source URL, raw hash, connector metadata, retrieval ' ||
        'time, and report index when available.'
ORDER BY step
            """.strip(),
        },
        "complaint_review_start_here": {
            "title": "Start Here: Complaint Review with Source Traceability",
            "description": (
                "Open this first for a review-ready complaint list with facility context, "
                "a single review flag summary, source URL, raw SHA-256 hash, raw path, "
                "connector metadata, retrieval time, report index, and IDs for follow-up. Use "
                "for guided first-pass review; do not treat derived fields as source "
                "conclusions. Preserve traceability columns when filtering or exporting."
            ),
            "sql": """
SELECT
    facility_number,
    facility_name,
    complaint_control_number,
    complaint_received_date,
    visit_date,
    report_date,
    finding,
    allegation_count,
    allegation_summary,
    review_flags_summary,
    source_url,
    raw_sha256,
    raw_path,
    connector_name,
    connector_version,
    retrieved_at,
    report_index,
    complaint_id,
    document_id
FROM complaint_first_pass_review
ORDER BY report_date DESC, complaint_received_date DESC, facility_number
            """.strip(),
        },
        "complaints_by_facility": {
            "title": "Complaints by Facility",
            "description": (
                "Filter the main review view by CCLD facility number. Enter the public "
                "facility number, such as 157806098, when Datasette prompts for facility_number. "
                "Use for narrowing review scope; do not assume omitted facilities have no "
                "complaints in the public portal."
            ),
            "sql": """
SELECT *
FROM complaint_review_summary
WHERE facility_number = :facility_number
ORDER BY complaint_received_date DESC, report_date DESC
            """.strip(),
        },
        "complaint_review_export_with_traceability": {
            "title": "Complaint Review Export with Source Traceability",
            "description": (
                "Export complaint review fields with source URL, raw hash, connector metadata, "
                "retrieval time, and report index. Use for accessible CSV review; keep clear "
                "headers and do not remove traceability columns from research exports."
            ),
            "sql": COMPLAINT_REVIEW_EXPORT_SQL,
        },
        "records_with_delay_review_flags": {
            "title": "Records with Delay Review Flags",
            "description": (
                "Triage records with one or more delay or review flags. These are screening aids, "
                "not conclusions. Use to decide what to inspect next; do not label the export as "
                "delayed investigations."
            ),
            "sql": """
SELECT *
FROM delay_review_flags
ORDER BY days_received_to_report DESC, complaint_received_date DESC
            """.strip(),
        },
        "facilities_with_delay_review_flags": {
            "title": "Facilities with Delay Review Flags",
            "description": (
                "Rank facilities by records with delay or review flags. Counts are screening "
                "aids, not conclusions about delays."
            ),
            "sql": """
SELECT *
FROM facility_complaint_summary
WHERE records_with_delay_review_flags > 0
ORDER BY records_with_delay_review_flags DESC, complaint_count DESC, facility_number
            """.strip(),
        },
        "source_traceability_check": {
            "title": "Source Traceability Review",
            "description": (
                "Check source URLs, hashes, connector metadata, retrieval time, and report index. "
                "Use before relying on or citing extracted records; preserve these fields when "
                "exporting."
            ),
            "sql": """
SELECT *
FROM source_traceability_review
ORDER BY facility_number, report_index DESC
            """.strip(),
        },
        "source_traceability_by_facility": {
            "title": "Source Traceability by Facility",
            "description": (
                "Filter source provenance by facility number before relying on or exporting "
                "derived complaint fields. Enter the public facility number when Datasette "
                "prompts for facility_number."
            ),
            "sql": """
SELECT *
FROM source_traceability_review
WHERE facility_number = :facility_number
ORDER BY report_index DESC, retrieved_at DESC
            """.strip(),
        },
        "allegation_summary_by_facility": {
            "title": "Allegation Summary by Facility",
            "description": "Count complaints and allegations by facility for high-level review.",
            "sql": """
SELECT
    facility_number,
    facility_name,
    COUNT(DISTINCT complaint_id) AS complaint_count,
    SUM(allegation_count) AS allegation_count
FROM complaint_review_summary
GROUP BY facility_number, facility_name
ORDER BY allegation_count DESC, complaint_count DESC
            """.strip(),
        },
        "newest_reports": {
            "title": "Newest Reports",
            "description": "Review most recently retrieved source documents first.",
            "sql": """
SELECT *
FROM source_traceability_review
ORDER BY retrieved_at DESC, report_index DESC
            """.strip(),
        },
    }


def _load_report_fixture(
    candidate: SourceDocumentCandidate,
    fixture_dir: Path,
) -> SourceDocument | None:
    raw_path = fixture_dir / "raw" / f"{candidate.facility_number}_inx{candidate.report_index}.html"
    resolved_raw_path = _resolve_fixture_path(raw_path)
    if not resolved_raw_path.exists():
        return None

    raw_content = resolved_raw_path.read_bytes()
    return SourceDocument(
        source_url=candidate.source_url,
        raw_path=_repo_relative_path(resolved_raw_path),
        raw_sha256=sha256_bytes(raw_content),
        retrieved_at=DEFAULT_SAMPLE_RETRIEVED_AT,
        content_type="text/html",
    )


def _resolve_fixture_path(path: Path) -> Path:
    if path.exists() or path.is_absolute():
        return path
    return _REPO_ROOT / path


def _repo_relative_path(path: Path) -> Path:
    try:
        return path.relative_to(_REPO_ROOT)
    except ValueError:
        return path