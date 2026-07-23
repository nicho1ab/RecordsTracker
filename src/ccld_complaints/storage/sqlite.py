from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Mapping
from pathlib import Path

SqliteValue = str | int | float | None

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS facilities (
    facility_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    external_facility_number TEXT NOT NULL,
    facility_name TEXT NOT NULL,
    facility_type TEXT,
    licensee_name TEXT,
    county TEXT,
    status TEXT,
    capacity INTEGER,
    regional_office TEXT
);

CREATE TABLE IF NOT EXISTS source_documents (
    document_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    facility_id TEXT NOT NULL,
    source_url TEXT NOT NULL UNIQUE,
    retrieved_at TEXT NOT NULL,
    raw_sha256 TEXT NOT NULL,
    connector_name TEXT NOT NULL,
    connector_version TEXT NOT NULL,
    raw_path TEXT,
    document_type TEXT,
    report_index INTEGER,
    http_status INTEGER,
    content_type TEXT
);

CREATE TABLE IF NOT EXISTS complaints (
    complaint_id TEXT PRIMARY KEY,
    facility_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    complaint_control_number TEXT,
    complaint_received_date TEXT,
    first_investigation_activity_date TEXT,
    visit_date TEXT,
    report_date TEXT,
    date_signed TEXT,
    finding TEXT,
    agency_name TEXT,
    deficiency_texts TEXT,
    investigation_findings_narrative TEXT,
    complaint_report_contact TEXT,
    days_received_to_first_activity INTEGER,
    days_received_to_visit INTEGER,
    days_received_to_report INTEGER,
    days_report_to_signed INTEGER,
    review_delay_over_30_days INTEGER NOT NULL DEFAULT 0,
    review_delay_over_60_days INTEGER NOT NULL DEFAULT 0,
    review_delay_over_90_days INTEGER NOT NULL DEFAULT 0,
    review_delay_over_120_days INTEGER NOT NULL DEFAULT 0,
    missing_first_activity_date INTEGER NOT NULL DEFAULT 0,
    report_date_used_as_proxy INTEGER NOT NULL DEFAULT 0,
    extraction_confidence REAL
);

CREATE TABLE IF NOT EXISTS allegations (
    allegation_id TEXT PRIMARY KEY,
    complaint_id TEXT NOT NULL,
    allegation_text TEXT NOT NULL,
    allegation_category TEXT,
    finding TEXT,
    extraction_confidence REAL
);

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    complaint_id TEXT NOT NULL,
    event_date TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_text TEXT,
    extracted_from_section TEXT,
    extraction_confidence REAL
);

CREATE TABLE IF NOT EXISTS extraction_audit (
    audit_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    field_name TEXT NOT NULL,
    extraction_method TEXT NOT NULL,
    extractor_version TEXT NOT NULL,
    extracted_value TEXT,
    confidence REAL,
    source_text TEXT,
    source_section TEXT,
    warning TEXT
);
"""

REVIEW_VIEWS_SQL = """
DROP VIEW IF EXISTS delay_review_flags;
DROP VIEW IF EXISTS facility_complaint_summary;
DROP VIEW IF EXISTS complaint_first_pass_review;
DROP VIEW IF EXISTS complaint_timeline_review;
DROP VIEW IF EXISTS field_source_traceability_review;
DROP VIEW IF EXISTS multi_facility_source_traceability_review;
DROP VIEW IF EXISTS facility_pattern_review;
DROP VIEW IF EXISTS facility_comparison_review;
DROP VIEW IF EXISTS complaint_review_summary;
DROP VIEW IF EXISTS source_traceability_review;

CREATE VIEW complaint_review_summary AS
SELECT
    f.external_facility_number AS facility_number,
    f.facility_name,
    c.complaint_id,
    c.complaint_control_number,
    c.complaint_received_date,
    c.first_investigation_activity_date,
    c.visit_date,
    c.report_date,
    c.date_signed,
    c.finding,
    COUNT(a.allegation_id) AS allegation_count,
    GROUP_CONCAT(a.allegation_text, '; ') AS allegation_summary,
    c.days_received_to_first_activity,
    c.days_received_to_visit,
    c.days_received_to_report,
    c.days_report_to_signed,
    c.review_delay_over_30_days,
    c.review_delay_over_60_days,
    c.review_delay_over_90_days,
    c.review_delay_over_120_days,
    c.missing_first_activity_date,
    c.report_date_used_as_proxy,
    c.extraction_confidence,
    sd.source_url,
    sd.raw_path
FROM complaints c
JOIN facilities f ON f.facility_id = c.facility_id
JOIN source_documents sd ON sd.document_id = c.document_id
LEFT JOIN allegations a ON a.complaint_id = c.complaint_id
GROUP BY
    f.external_facility_number,
    f.facility_name,
    c.complaint_id,
    c.complaint_control_number,
    c.complaint_received_date,
    c.first_investigation_activity_date,
    c.visit_date,
    c.report_date,
    c.date_signed,
    c.finding,
    c.days_received_to_first_activity,
    c.days_received_to_visit,
    c.days_received_to_report,
    c.days_report_to_signed,
    c.review_delay_over_30_days,
    c.review_delay_over_60_days,
    c.review_delay_over_90_days,
    c.review_delay_over_120_days,
    c.missing_first_activity_date,
    c.report_date_used_as_proxy,
    c.extraction_confidence,
    sd.source_url,
    sd.raw_path;

CREATE VIEW facility_complaint_summary AS
SELECT
    f.external_facility_number AS facility_number,
    f.facility_name,
    COUNT(DISTINCT c.complaint_id) AS complaint_count,
    COUNT(a.allegation_id) AS allegation_count,
    MIN(c.complaint_received_date) AS earliest_complaint_received_date,
    MAX(c.complaint_received_date) AS latest_complaint_received_date,
    COUNT(DISTINCT CASE
        WHEN c.review_delay_over_30_days = 1
          OR c.review_delay_over_60_days = 1
          OR c.review_delay_over_90_days = 1
          OR c.review_delay_over_120_days = 1
          OR c.missing_first_activity_date = 1
          OR c.report_date_used_as_proxy = 1
        THEN c.complaint_id
    END) AS records_with_delay_review_flags
FROM facilities f
LEFT JOIN complaints c ON c.facility_id = f.facility_id
LEFT JOIN allegations a ON a.complaint_id = c.complaint_id
GROUP BY f.external_facility_number, f.facility_name;

CREATE VIEW complaint_first_pass_review AS
SELECT
    f.external_facility_number AS facility_number,
    f.facility_name,
    c.complaint_control_number,
    c.complaint_received_date,
    c.visit_date,
    c.report_date,
    c.finding,
    COUNT(a.allegation_id) AS allegation_count,
    GROUP_CONCAT(a.allegation_text, '; ') AS allegation_summary,
    NULLIF(RTRIM(
        CASE WHEN c.review_delay_over_30_days = 1 THEN 'over 30 days; ' ELSE '' END ||
        CASE WHEN c.review_delay_over_60_days = 1 THEN 'over 60 days; ' ELSE '' END ||
        CASE WHEN c.review_delay_over_90_days = 1 THEN 'over 90 days; ' ELSE '' END ||
        CASE WHEN c.review_delay_over_120_days = 1 THEN 'over 120 days; ' ELSE '' END ||
        CASE
            WHEN c.missing_first_activity_date = 1
            THEN 'missing first activity date; '
            ELSE ''
        END ||
        CASE WHEN c.report_date_used_as_proxy = 1 THEN 'report date used as proxy; ' ELSE '' END,
        '; '
    ), '') AS review_flags_summary,
    sd.source_url,
    sd.raw_sha256,
    sd.raw_path,
    sd.connector_name,
    sd.connector_version,
    sd.retrieved_at,
    sd.report_index,
    c.complaint_id,
    sd.document_id
FROM complaints c
JOIN facilities f ON f.facility_id = c.facility_id
JOIN source_documents sd ON sd.document_id = c.document_id
LEFT JOIN allegations a ON a.complaint_id = c.complaint_id
GROUP BY
    f.external_facility_number,
    f.facility_name,
    c.complaint_id,
    c.complaint_control_number,
    c.complaint_received_date,
    c.visit_date,
    c.report_date,
    c.finding,
    c.review_delay_over_30_days,
    c.review_delay_over_60_days,
    c.review_delay_over_90_days,
    c.review_delay_over_120_days,
    c.missing_first_activity_date,
    c.report_date_used_as_proxy,
    sd.source_url,
    sd.raw_sha256,
    sd.raw_path,
    sd.connector_name,
    sd.connector_version,
    sd.retrieved_at,
    sd.report_index,
    sd.document_id;

CREATE VIEW delay_review_flags AS
SELECT
    facility_number,
    facility_name,
    complaint_id,
    complaint_control_number,
    complaint_received_date,
    first_investigation_activity_date,
    visit_date,
    report_date,
    date_signed,
    finding,
    days_received_to_first_activity,
    days_received_to_visit,
    days_received_to_report,
    days_report_to_signed,
    review_delay_over_30_days,
    review_delay_over_60_days,
    review_delay_over_90_days,
    review_delay_over_120_days,
    missing_first_activity_date,
    report_date_used_as_proxy,
    source_url,
    raw_path
FROM complaint_review_summary
WHERE review_delay_over_30_days = 1
   OR review_delay_over_60_days = 1
   OR review_delay_over_90_days = 1
   OR review_delay_over_120_days = 1
   OR missing_first_activity_date = 1
   OR report_date_used_as_proxy = 1;

CREATE VIEW source_traceability_review AS
SELECT
    f.external_facility_number AS facility_number,
    f.facility_name,
    sd.document_id,
    sd.source_url,
    sd.raw_sha256,
    sd.raw_path,
    sd.connector_name,
    sd.connector_version,
    sd.retrieved_at,
    sd.report_index,
    sd.document_type,
    sd.content_type
FROM source_documents sd
JOIN facilities f ON f.facility_id = sd.facility_id;

CREATE VIEW multi_facility_source_traceability_review AS
SELECT
    f.external_facility_number AS facility_number,
    f.facility_name,
    sd.document_id,
    sd.source_url,
    sd.raw_sha256,
    sd.raw_path,
    sd.connector_name,
    sd.connector_version,
    sd.retrieved_at,
    sd.report_index,
    sd.document_type,
    sd.content_type,
    CASE
        WHEN COALESCE(TRIM(sd.source_url), '') = ''
          OR COALESCE(TRIM(sd.raw_sha256), '') = ''
          OR COALESCE(TRIM(sd.connector_name), '') = ''
          OR COALESCE(TRIM(sd.connector_version), '') = ''
          OR COALESCE(TRIM(sd.retrieved_at), '') = ''
        THEN 'missing source traceability'
        ELSE 'complete'
    END AS traceability_status,
    COUNT(DISTINCT c.complaint_id) AS complaint_count,
    COUNT(DISTINCT a.allegation_id) AS allegation_count,
    COUNT(DISTINCT e.event_id) AS event_count,
    COUNT(DISTINCT ea.audit_id) AS extraction_audit_field_count
FROM source_documents sd
JOIN facilities f ON f.facility_id = sd.facility_id
LEFT JOIN complaints c ON c.document_id = sd.document_id
LEFT JOIN allegations a ON a.complaint_id = c.complaint_id
LEFT JOIN events e ON e.complaint_id = c.complaint_id
LEFT JOIN extraction_audit ea ON ea.document_id = sd.document_id
GROUP BY
    f.external_facility_number,
    f.facility_name,
    sd.document_id,
    sd.source_url,
    sd.raw_sha256,
    sd.raw_path,
    sd.connector_name,
    sd.connector_version,
    sd.retrieved_at,
    sd.report_index,
    sd.document_type,
    sd.content_type;

CREATE VIEW complaint_timeline_review AS
SELECT
    f.external_facility_number AS facility_number,
    f.facility_name,
    c.complaint_id,
    c.complaint_control_number,
    1 AS timeline_sequence,
    'complaint received' AS timeline_item_type,
    'complaint_received_date' AS timeline_source_field,
    c.complaint_received_date AS timeline_date,
    'Complaint received date extracted from the public source report.' AS timeline_note,
    c.finding,
    c.review_delay_over_30_days,
    c.review_delay_over_60_days,
    c.review_delay_over_90_days,
    c.review_delay_over_120_days,
    c.missing_first_activity_date,
    c.report_date_used_as_proxy,
    sd.source_url,
    sd.raw_sha256,
    sd.raw_path,
    sd.connector_name,
    sd.connector_version,
    sd.retrieved_at,
    sd.report_index,
    NULL AS event_id,
    sd.document_id
FROM complaints c
JOIN facilities f ON f.facility_id = c.facility_id
JOIN source_documents sd ON sd.document_id = c.document_id
WHERE c.complaint_received_date IS NOT NULL
UNION ALL
SELECT
    f.external_facility_number,
    f.facility_name,
    c.complaint_id,
    c.complaint_control_number,
    2,
    'first investigation activity',
    'first_investigation_activity_date',
    c.first_investigation_activity_date,
    'Earliest deterministic investigation activity date extracted when available.',
    c.finding,
    c.review_delay_over_30_days,
    c.review_delay_over_60_days,
    c.review_delay_over_90_days,
    c.review_delay_over_120_days,
    c.missing_first_activity_date,
    c.report_date_used_as_proxy,
    sd.source_url,
    sd.raw_sha256,
    sd.raw_path,
    sd.connector_name,
    sd.connector_version,
    sd.retrieved_at,
    sd.report_index,
    NULL,
    sd.document_id
FROM complaints c
JOIN facilities f ON f.facility_id = c.facility_id
JOIN source_documents sd ON sd.document_id = c.document_id
WHERE c.first_investigation_activity_date IS NOT NULL
UNION ALL
SELECT
    f.external_facility_number,
    f.facility_name,
    c.complaint_id,
    c.complaint_control_number,
    3,
    'visit',
    'visit_date',
    c.visit_date,
    'Visit date shown in the public source report when available.',
    c.finding,
    c.review_delay_over_30_days,
    c.review_delay_over_60_days,
    c.review_delay_over_90_days,
    c.review_delay_over_120_days,
    c.missing_first_activity_date,
    c.report_date_used_as_proxy,
    sd.source_url,
    sd.raw_sha256,
    sd.raw_path,
    sd.connector_name,
    sd.connector_version,
    sd.retrieved_at,
    sd.report_index,
    NULL,
    sd.document_id
FROM complaints c
JOIN facilities f ON f.facility_id = c.facility_id
JOIN source_documents sd ON sd.document_id = c.document_id
WHERE c.visit_date IS NOT NULL
UNION ALL
SELECT
    f.external_facility_number,
    f.facility_name,
    c.complaint_id,
    c.complaint_control_number,
    4,
    'report',
    'report_date',
    c.report_date,
    'Report date shown in the public source report; this may not be first activity.',
    c.finding,
    c.review_delay_over_30_days,
    c.review_delay_over_60_days,
    c.review_delay_over_90_days,
    c.review_delay_over_120_days,
    c.missing_first_activity_date,
    c.report_date_used_as_proxy,
    sd.source_url,
    sd.raw_sha256,
    sd.raw_path,
    sd.connector_name,
    sd.connector_version,
    sd.retrieved_at,
    sd.report_index,
    NULL,
    sd.document_id
FROM complaints c
JOIN facilities f ON f.facility_id = c.facility_id
JOIN source_documents sd ON sd.document_id = c.document_id
WHERE c.report_date IS NOT NULL
UNION ALL
SELECT
    f.external_facility_number,
    f.facility_name,
    c.complaint_id,
    c.complaint_control_number,
    5,
    'date signed',
    'date_signed',
    c.date_signed,
    'Date the report was signed when available.',
    c.finding,
    c.review_delay_over_30_days,
    c.review_delay_over_60_days,
    c.review_delay_over_90_days,
    c.review_delay_over_120_days,
    c.missing_first_activity_date,
    c.report_date_used_as_proxy,
    sd.source_url,
    sd.raw_sha256,
    sd.raw_path,
    sd.connector_name,
    sd.connector_version,
    sd.retrieved_at,
    sd.report_index,
    NULL,
    sd.document_id
FROM complaints c
JOIN facilities f ON f.facility_id = c.facility_id
JOIN source_documents sd ON sd.document_id = c.document_id
WHERE c.date_signed IS NOT NULL
UNION ALL
SELECT
    f.external_facility_number,
    f.facility_name,
    c.complaint_id,
    c.complaint_control_number,
    6,
    'extracted event',
    e.event_type,
    e.event_date,
    e.event_text,
    c.finding,
    c.review_delay_over_30_days,
    c.review_delay_over_60_days,
    c.review_delay_over_90_days,
    c.review_delay_over_120_days,
    c.missing_first_activity_date,
    c.report_date_used_as_proxy,
    sd.source_url,
    sd.raw_sha256,
    sd.raw_path,
    sd.connector_name,
    sd.connector_version,
    sd.retrieved_at,
    sd.report_index,
    e.event_id,
    sd.document_id
FROM events e
JOIN complaints c ON c.complaint_id = e.complaint_id
JOIN facilities f ON f.facility_id = c.facility_id
JOIN source_documents sd ON sd.document_id = c.document_id;

CREATE VIEW field_source_traceability_review AS
SELECT
    f.external_facility_number AS facility_number,
    f.facility_name,
    c.complaint_id,
    c.complaint_control_number,
    c.complaint_received_date,
    c.report_date,
    ea.field_name,
    ea.extracted_value,
    ea.source_text,
    ea.source_section,
    ea.warning,
    ea.confidence,
    ea.extraction_method,
    ea.extractor_version,
    sd.document_id,
    sd.source_url,
    sd.raw_sha256,
    sd.raw_path,
    sd.connector_name,
    sd.connector_version,
    sd.retrieved_at,
    sd.report_index,
    sd.document_type
FROM extraction_audit ea
JOIN source_documents sd ON sd.document_id = ea.document_id
JOIN facilities f ON f.facility_id = sd.facility_id
LEFT JOIN complaints c ON c.document_id = sd.document_id;

CREATE VIEW facility_pattern_review AS
SELECT
    f.external_facility_number AS facility_number,
    f.facility_name,
    COUNT(DISTINCT c.complaint_id) AS complaint_count,
    COUNT(DISTINCT sd.document_id) AS source_document_count,
    COUNT(a.allegation_id) AS allegation_count,
    GROUP_CONCAT(DISTINCT COALESCE(a.allegation_category, 'Unknown')) AS allegation_categories,
    COUNT(DISTINCT CASE WHEN c.finding = 'Substantiated' THEN c.complaint_id END)
        AS substantiated_complaint_count,
    COUNT(DISTINCT CASE WHEN c.finding = 'Unsubstantiated' THEN c.complaint_id END)
        AS unsubstantiated_complaint_count,
    COUNT(DISTINCT CASE WHEN c.finding = 'Inconclusive' THEN c.complaint_id END)
        AS inconclusive_complaint_count,
    COUNT(DISTINCT CASE
        WHEN c.finding IS NULL OR c.finding = 'Unknown' THEN c.complaint_id
    END) AS unknown_finding_complaint_count,
    COUNT(DISTINCT CASE WHEN c.missing_first_activity_date = 1 THEN c.complaint_id END)
        AS missing_first_activity_count,
    COUNT(DISTINCT CASE WHEN c.report_date_used_as_proxy = 1 THEN c.complaint_id END)
        AS report_date_proxy_count,
    COUNT(DISTINCT CASE
        WHEN c.review_delay_over_30_days = 1
          OR c.review_delay_over_60_days = 1
          OR c.review_delay_over_90_days = 1
          OR c.review_delay_over_120_days = 1
          OR c.missing_first_activity_date = 1
          OR c.report_date_used_as_proxy = 1
        THEN c.complaint_id
    END) AS records_with_review_flags,
    MIN(c.complaint_received_date) AS earliest_complaint_received_date,
    MAX(c.complaint_received_date) AS latest_complaint_received_date,
    MIN(sd.retrieved_at) AS earliest_retrieved_at,
    MAX(sd.retrieved_at) AS latest_retrieved_at
FROM facilities f
LEFT JOIN complaints c ON c.facility_id = f.facility_id
LEFT JOIN source_documents sd ON sd.document_id = c.document_id
LEFT JOIN allegations a ON a.complaint_id = c.complaint_id
GROUP BY f.external_facility_number, f.facility_name;

CREATE VIEW facility_comparison_review AS
WITH comparison_rows AS (
    SELECT
        f.external_facility_number AS facility_number,
        f.facility_name,
        COALESCE(a.allegation_category, 'Unknown') AS allegation_category,
        COALESCE(a.finding, c.finding, 'Unknown') AS finding,
        COUNT(DISTINCT c.complaint_id) AS complaint_count,
        COUNT(a.allegation_id) AS allegation_count,
        COUNT(DISTINCT sd.document_id) AS source_document_count,
        COUNT(DISTINCT CASE
            WHEN COALESCE(TRIM(sd.source_url), '') <> ''
              AND COALESCE(TRIM(sd.raw_sha256), '') <> ''
              AND COALESCE(TRIM(sd.connector_name), '') <> ''
              AND COALESCE(TRIM(sd.connector_version), '') <> ''
              AND COALESCE(TRIM(sd.retrieved_at), '') <> ''
            THEN sd.document_id
        END) AS complete_source_traceability_document_count,
        COUNT(DISTINCT CASE
            WHEN COALESCE(TRIM(sd.source_url), '') = ''
              OR COALESCE(TRIM(sd.raw_sha256), '') = ''
              OR COALESCE(TRIM(sd.connector_name), '') = ''
              OR COALESCE(TRIM(sd.connector_version), '') = ''
              OR COALESCE(TRIM(sd.retrieved_at), '') = ''
            THEN sd.document_id
        END) AS missing_source_traceability_document_count,
        COUNT(DISTINCT CASE
            WHEN c.review_delay_over_30_days = 1
              OR c.review_delay_over_60_days = 1
              OR c.review_delay_over_90_days = 1
              OR c.review_delay_over_120_days = 1
              OR c.missing_first_activity_date = 1
              OR c.report_date_used_as_proxy = 1
            THEN c.complaint_id
        END) AS records_with_review_flags,
        MIN(c.complaint_received_date) AS earliest_complaint_received_date,
        MAX(c.complaint_received_date) AS latest_complaint_received_date,
        MIN(sd.retrieved_at) AS earliest_retrieved_at,
        MAX(sd.retrieved_at) AS latest_retrieved_at
    FROM complaints c
    JOIN facilities f ON f.facility_id = c.facility_id
    JOIN source_documents sd ON sd.document_id = c.document_id
    LEFT JOIN allegations a ON a.complaint_id = c.complaint_id
    GROUP BY
        f.external_facility_number,
        f.facility_name,
        COALESCE(a.allegation_category, 'Unknown'),
        COALESCE(a.finding, c.finding, 'Unknown')
)
SELECT
    comparison_rows.*,
    COUNT(*) OVER (
        PARTITION BY allegation_category, finding
    ) AS facilities_with_same_category_finding,
    'screening aid; verify source records before citing' AS comparison_scope_note
FROM comparison_rows;
"""

TABLE_COLUMNS = {
    "facilities": (
        "facility_id",
        "source_id",
        "external_facility_number",
        "facility_name",
        "facility_type",
        "licensee_name",
        "county",
        "status",
        "capacity",
        "regional_office",
    ),
    "source_documents": (
        "document_id",
        "source_id",
        "facility_id",
        "source_url",
        "retrieved_at",
        "raw_sha256",
        "connector_name",
        "connector_version",
        "raw_path",
        "document_type",
        "report_index",
        "http_status",
        "content_type",
    ),
    "complaints": (
        "complaint_id",
        "facility_id",
        "document_id",
        "complaint_control_number",
        "complaint_received_date",
        "first_investigation_activity_date",
        "visit_date",
        "report_date",
        "date_signed",
        "finding",
        "agency_name",
        "deficiency_texts",
        "investigation_findings_narrative",
        "complaint_report_contact",
        "days_received_to_first_activity",
        "days_received_to_visit",
        "days_received_to_report",
        "days_report_to_signed",
        "review_delay_over_30_days",
        "review_delay_over_60_days",
        "review_delay_over_90_days",
        "review_delay_over_120_days",
        "missing_first_activity_date",
        "report_date_used_as_proxy",
        "extraction_confidence",
    ),
    "allegations": (
        "allegation_id",
        "complaint_id",
        "allegation_text",
        "allegation_category",
        "finding",
        "extraction_confidence",
    ),
    "events": (
        "event_id",
        "complaint_id",
        "event_date",
        "event_type",
        "event_text",
        "extracted_from_section",
        "extraction_confidence",
    ),
    "extraction_audit": (
        "audit_id",
        "document_id",
        "field_name",
        "extraction_method",
        "extractor_version",
        "extracted_value",
        "confidence",
        "source_text",
        "source_section",
        "warning",
    ),
}

PRIMARY_KEYS = {
    "facilities": "facility_id",
    "source_documents": "document_id",
    "complaints": "complaint_id",
    "allegations": "allegation_id",
    "events": "event_id",
    "extraction_audit": "audit_id",
}

# A facility row is repeated for every normalized complaint document.  Missing
# values in one document must not erase a usable facility value populated by a
# different governed document or initializer.  Non-null incoming values still
# refresh the current canonical projection, including an explicit numeric zero.
NULL_PRESERVING_UPSERT_COLUMNS = {
    "facilities": frozenset(
        {
            "facility_type",
            "licensee_name",
            "county",
            "status",
            "capacity",
            "regional_office",
        }
    ),
    "complaints": frozenset(
        {
            "agency_name",
            "deficiency_texts",
            "investigation_findings_narrative",
            "complaint_report_contact",
        }
    ),
}

COMPLAINT_COLUMN_DEFINITIONS = {
    "agency_name": "TEXT",
    "deficiency_texts": "TEXT",
    "investigation_findings_narrative": "TEXT",
    "complaint_report_contact": "TEXT",
    "days_received_to_visit": "INTEGER",
    "days_report_to_signed": "INTEGER",
    "review_delay_over_30_days": "INTEGER NOT NULL DEFAULT 0",
    "review_delay_over_60_days": "INTEGER NOT NULL DEFAULT 0",
    "review_delay_over_90_days": "INTEGER NOT NULL DEFAULT 0",
    "review_delay_over_120_days": "INTEGER NOT NULL DEFAULT 0",
    "missing_first_activity_date": "INTEGER NOT NULL DEFAULT 0",
    "report_date_used_as_proxy": "INTEGER NOT NULL DEFAULT 0",
}


def initialize_database(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA_SQL)
        _ensure_complaint_columns(conn)
        conn.executescript(REVIEW_VIEWS_SQL)
        conn.commit()


def _ensure_complaint_columns(conn: sqlite3.Connection) -> None:
    existing_columns = {
        str(row[1]) for row in conn.execute("PRAGMA table_info(complaints)").fetchall()
    }
    for column, definition in COMPLAINT_COLUMN_DEFINITIONS.items():
        if column not in existing_columns:
            conn.execute(f"ALTER TABLE complaints ADD COLUMN {column} {definition}")


def write_normalized_records(path: Path, records: Iterable[Mapping[str, object]]) -> None:
    initialize_database(path)
    with sqlite3.connect(path) as conn:
        for record in records:
            write_normalized_record(conn, record)
        conn.commit()


def write_normalized_record(
    conn: sqlite3.Connection, normalized: Mapping[str, object]
) -> None:
    _upsert_mapping(conn, "facilities", normalized.get("facility"))
    _upsert_mapping(conn, "source_documents", normalized.get("source_document"))
    _upsert_mapping(conn, "complaints", normalized.get("complaint"))
    _upsert_mapping(conn, "events", normalized.get("event"))
    _upsert_many(conn, "allegations", normalized.get("allegations"))
    _upsert_many(conn, "events", normalized.get("events"))
    _upsert_many(conn, "extraction_audit", normalized.get("extraction_audit"))


def _upsert_mapping(conn: sqlite3.Connection, table_name: str, value: object) -> None:
    if value is None:
        return
    if not isinstance(value, Mapping):
        raise TypeError(f"Expected {table_name} record to be a mapping.")
    _upsert(conn, table_name, value)


def _upsert_many(conn: sqlite3.Connection, table_name: str, value: object) -> None:
    if value is None:
        return
    if not isinstance(value, list):
        raise TypeError(f"Expected {table_name} records to be a list.")
    for item in value:
        if not isinstance(item, Mapping):
            raise TypeError(f"Expected each {table_name} record to be a mapping.")
        _upsert(conn, table_name, item)


def _upsert(
    conn: sqlite3.Connection, table_name: str, record: Mapping[str, object]
) -> None:
    columns = TABLE_COLUMNS[table_name]
    primary_key = PRIMARY_KEYS[table_name]
    column_names = ", ".join(columns)
    placeholders = ", ".join("?" for _column in columns)
    null_preserving_columns = NULL_PRESERVING_UPSERT_COLUMNS.get(
        table_name, frozenset()
    )
    assignments = ", ".join(
        (
            f"{column} = COALESCE(excluded.{column}, {table_name}.{column})"
            if column in null_preserving_columns
            else f"{column} = excluded.{column}"
        )
        for column in columns
        if column != primary_key
    )
    values = [
        _sqlite_column_value(table_name, column, record.get(column))
        for column in columns
    ]

    conn.execute(
        f"""
        INSERT INTO {table_name} ({column_names})
        VALUES ({placeholders})
        ON CONFLICT({primary_key}) DO UPDATE SET {assignments}
        """,
        values,
    )


def _sqlite_value(value: object) -> SqliteValue:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, list):
        if not value:
            return None
        return json.dumps(value, ensure_ascii=True, separators=(",", ":"))
    if value is None or isinstance(value, str | int | float):
        return value
    raise TypeError(f"Unsupported SQLite value type: {type(value).__name__}")


def _sqlite_column_value(
    table_name: str,
    column_name: str,
    value: object,
) -> SqliteValue:
    if (
        column_name
        in NULL_PRESERVING_UPSERT_COLUMNS.get(table_name, frozenset())
        and isinstance(value, str)
        and not value.strip()
    ):
        return None
    return _sqlite_value(value)
