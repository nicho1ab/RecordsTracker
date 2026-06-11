from __future__ import annotations

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
    days_received_to_first_activity INTEGER,
    days_received_to_report INTEGER,
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
        "days_received_to_first_activity",
        "days_received_to_report",
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


def initialize_database(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()


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
    assignments = ", ".join(
        f"{column} = excluded.{column}" for column in columns if column != primary_key
    )
    values = [_sqlite_value(record.get(column)) for column in columns]

    conn.execute(
        f"""
        INSERT INTO {table_name} ({column_names})
        VALUES ({placeholders})
        ON CONFLICT({primary_key}) DO UPDATE SET {assignments}
        """,
        values,
    )


def _sqlite_value(value: object) -> SqliteValue:
    if value is None or isinstance(value, str | int | float):
        return value
    raise TypeError(f"Unsupported SQLite value type: {type(value).__name__}")
