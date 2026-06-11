from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import cast

from ccld_complaints.connectors.base import SourceDocument
from ccld_complaints.connectors.ccld import CcldFacilityReportsConnector
from ccld_complaints.storage.sqlite import write_normalized_records
from ccld_complaints.utils.hash import sha256_bytes

FIXTURE_URL = "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=157806098&inx=3"
RAW_FIXTURE = Path("tests/fixtures/ccld/raw/157806098_inx3.html")
RETRIEVED_AT = "2026-06-10T00:00:00+00:00"


def test_write_normalized_ccld_report_to_sqlite(tmp_path: Path) -> None:
    db_path = tmp_path / "ccld.sqlite"
    normalized = _normalized_fixture()

    write_normalized_records(db_path, [normalized])

    assert _row_count(db_path, "facilities") == 1
    assert _row_count(db_path, "source_documents") == 1
    assert _row_count(db_path, "complaints") == 1
    assert _row_count(db_path, "allegations") == 2
    assert _row_count(db_path, "events") == 0
    assert _row_count(db_path, "extraction_audit") == 11
    assert _source_traceability(db_path) == {
        "source_url": FIXTURE_URL,
        "raw_sha256": sha256_bytes(RAW_FIXTURE.read_bytes()),
        "raw_path": RAW_FIXTURE.as_posix(),
        "connector_name": "ccld_facility_reports",
        "connector_version": "0.1.0",
        "retrieved_at": RETRIEVED_AT,
        "report_index": 3,
    }


def test_write_normalized_ccld_report_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "ccld.sqlite"
    normalized = _normalized_fixture()

    write_normalized_records(db_path, [normalized])
    write_normalized_records(db_path, [normalized])

    assert _row_count(db_path, "facilities") == 1
    assert _row_count(db_path, "source_documents") == 1
    assert _row_count(db_path, "complaints") == 1
    assert _row_count(db_path, "allegations") == 2
    assert _row_count(db_path, "extraction_audit") == 11


def test_written_complaint_and_allegations_link_to_parent_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "ccld.sqlite"
    normalized = _normalized_fixture()

    write_normalized_records(db_path, [normalized])

    with sqlite3.connect(db_path) as conn:
        complaint = conn.execute(
            """
            SELECT complaint_id, facility_id, document_id
            FROM complaints
            """
        ).fetchone()
        facility_id = conn.execute(
            "SELECT facility_id FROM facilities WHERE facility_id = ?",
            (complaint[1],),
        ).fetchone()
        document_id = conn.execute(
            "SELECT document_id FROM source_documents WHERE document_id = ?",
            (complaint[2],),
        ).fetchone()
        allegation_links = conn.execute(
            "SELECT DISTINCT complaint_id FROM allegations"
        ).fetchall()

    assert facility_id == (complaint[1],)
    assert document_id == (complaint[2],)
    assert allegation_links == [(complaint[0],)]


def test_extraction_audit_rows_are_stored_if_emitted(tmp_path: Path) -> None:
    db_path = tmp_path / "ccld.sqlite"
    normalized = _normalized_fixture()

    write_normalized_records(db_path, [normalized])

    with sqlite3.connect(db_path) as conn:
        audit_row = conn.execute(
            """
            SELECT document_id, field_name, extraction_method, extractor_version, confidence
            FROM extraction_audit
            WHERE field_name = 'facility_number'
            """
        ).fetchone()

    source_document = cast(dict[str, object], normalized["source_document"])
    assert audit_row == (
        source_document["document_id"],
        "facility_number",
        "ccld_facility_report_html_labels",
        "0.1.0",
        1.0,
    )


def _normalized_fixture() -> dict[str, object]:
    connector = CcldFacilityReportsConnector()
    raw_content = RAW_FIXTURE.read_bytes()
    document = SourceDocument(
        source_url=FIXTURE_URL,
        raw_path=RAW_FIXTURE,
        raw_sha256=sha256_bytes(raw_content),
        retrieved_at=RETRIEVED_AT,
        content_type="text/html",
    )
    return connector.normalize(connector.extract(document))


def _row_count(db_path: Path, table_name: str) -> int:
    with sqlite3.connect(db_path) as conn:
        count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    return cast(int, count)


def _source_traceability(db_path: Path) -> dict[str, object]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT source_url,
                   raw_sha256,
                   raw_path,
                   connector_name,
                   connector_version,
                   retrieved_at,
                   report_index
            FROM source_documents
            """
        ).fetchone()
    return dict(row)