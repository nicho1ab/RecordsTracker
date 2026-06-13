from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import cast

from ccld_complaints.local_sample import populate_sample_database


def test_derived_records_trace_to_source_documents(tmp_path: Path) -> None:
    db_path = tmp_path / "ccld.sqlite"

    populate_sample_database(db_path)

    with sqlite3.connect(db_path) as conn:
        assert _scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM source_documents
            WHERE COALESCE(TRIM(source_url), '') = ''
               OR COALESCE(TRIM(raw_sha256), '') = ''
               OR COALESCE(TRIM(connector_name), '') = ''
               OR COALESCE(TRIM(connector_version), '') = ''
               OR COALESCE(TRIM(retrieved_at), '') = ''
            """,
        ) == 0
        assert _scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM complaints c
            LEFT JOIN source_documents sd ON sd.document_id = c.document_id
            WHERE sd.document_id IS NULL
            """,
        ) == 0
        assert _scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM allegations a
            LEFT JOIN complaints c ON c.complaint_id = a.complaint_id
            LEFT JOIN source_documents sd ON sd.document_id = c.document_id
            WHERE c.complaint_id IS NULL OR sd.document_id IS NULL
            """,
        ) == 0
        assert _scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM events e
            LEFT JOIN complaints c ON c.complaint_id = e.complaint_id
            LEFT JOIN source_documents sd ON sd.document_id = c.document_id
            WHERE c.complaint_id IS NULL OR sd.document_id IS NULL
            """,
        ) == 0
        assert _scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM extraction_audit ea
            LEFT JOIN source_documents sd ON sd.document_id = ea.document_id
            WHERE sd.document_id IS NULL
            """,
        ) == 0


def _scalar(conn: sqlite3.Connection, sql: str) -> int:
    value = conn.execute(sql).fetchone()[0]
    return cast(int, value)
