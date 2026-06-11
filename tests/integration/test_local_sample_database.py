from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import cast

from ccld_complaints.local_sample import datasette_command, populate_sample_database
from ccld_complaints.utils.hash import sha256_bytes

RAW_FIXTURE = Path("tests/fixtures/ccld/raw/157806098_inx3.html")


def test_populate_sample_database_initializes_and_writes_fixture_data(tmp_path: Path) -> None:
    db_path = tmp_path / "ccld.sqlite"

    result = populate_sample_database(db_path)

    assert result.db_path == db_path
    assert len(result.ingestion.records) == 1
    assert len(result.ingestion.candidates) == 40
    assert len(result.ingestion.failures) == 39
    assert _row_count(db_path, "facilities") == 1
    assert _row_count(db_path, "source_documents") == 1
    assert _row_count(db_path, "complaints") == 1
    assert _row_count(db_path, "allegations") == 2
    assert _row_count(db_path, "extraction_audit") == 11
    assert _source_document(db_path) == {
        "source_url": "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=157806098&inx=3",
        "raw_sha256": sha256_bytes(RAW_FIXTURE.read_bytes()),
        "connector_name": "ccld_facility_reports",
        "connector_version": "0.1.0",
        "report_index": 3,
    }


def test_populate_sample_database_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "ccld.sqlite"

    populate_sample_database(db_path)
    populate_sample_database(db_path)

    assert _row_count(db_path, "facilities") == 1
    assert _row_count(db_path, "source_documents") == 1
    assert _row_count(db_path, "complaints") == 1
    assert _row_count(db_path, "allegations") == 2
    assert _row_count(db_path, "extraction_audit") == 11


def test_datasette_command_quotes_database_path() -> None:
    assert datasette_command(Path("data/processed/ccld.sqlite")) == (
        'datasette "data/processed/ccld.sqlite"'
    )


def _row_count(db_path: Path, table_name: str) -> int:
    with sqlite3.connect(db_path) as conn:
        count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    return cast(int, count)


def _source_document(db_path: Path) -> dict[str, object]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT source_url,
                   raw_sha256,
                   connector_name,
                   connector_version,
                   report_index
            FROM source_documents
            """
        ).fetchone()
    return dict(row)