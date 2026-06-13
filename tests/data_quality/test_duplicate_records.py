from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import cast

from ccld_complaints.local_sample import populate_sample_database

UNIQUE_FIELD_CHECKS = {
    "facilities": "facility_id",
    "source_documents": "document_id",
    "complaints": "complaint_id",
    "allegations": "allegation_id",
    "events": "event_id",
    "extraction_audit": "audit_id",
}


def test_sample_database_has_no_duplicate_canonical_record_ids(tmp_path: Path) -> None:
    db_path = tmp_path / "ccld.sqlite"

    populate_sample_database(db_path)

    with sqlite3.connect(db_path) as conn:
        for table_name, field_name in UNIQUE_FIELD_CHECKS.items():
            assert _duplicate_values(conn, table_name, field_name) == []


def test_sample_database_has_no_duplicate_source_urls(tmp_path: Path) -> None:
    db_path = tmp_path / "ccld.sqlite"

    populate_sample_database(db_path)

    with sqlite3.connect(db_path) as conn:
        assert _duplicate_values(conn, "source_documents", "source_url") == []


def _duplicate_values(
    conn: sqlite3.Connection, table_name: str, field_name: str
) -> list[str]:
    rows = conn.execute(
        f"""
        SELECT {field_name}
        FROM {table_name}
        GROUP BY {field_name}
        HAVING COUNT(*) > 1
        ORDER BY {field_name}
        """
    ).fetchall()
    return [cast(str, row[0]) for row in rows]
