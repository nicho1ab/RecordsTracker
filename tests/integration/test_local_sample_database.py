from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import cast

from pytest import MonkeyPatch

from ccld_complaints.local_sample import (
    datasette_command,
    datasette_metadata,
    datasette_metadata_path,
    populate_sample_database,
    review_workflow_lines,
    write_datasette_metadata,
)
from ccld_complaints.utils.hash import sha256_bytes

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_FIXTURE = REPO_ROOT / "tests/fixtures/ccld/raw/157806098_inx3.html"


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
    assert _row_count(db_path, "extraction_audit") == 21
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
    assert _row_count(db_path, "extraction_audit") == 21


def test_populate_sample_database_uses_bundled_fixtures_from_other_cwd(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    db_path = tmp_path / "ccld.sqlite"
    monkeypatch.chdir(tmp_path)

    result = populate_sample_database(db_path)

    assert len(result.ingestion.records) == 1
    assert len(result.ingestion.candidates) == 40
    assert len(result.ingestion.failures) == 39
    assert _row_count(db_path, "source_documents") == 1
    assert _source_document(db_path) == {
        "source_url": "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=157806098&inx=3",
        "raw_sha256": sha256_bytes(RAW_FIXTURE.read_bytes()),
        "connector_name": "ccld_facility_reports",
        "connector_version": "0.1.0",
        "report_index": 3,
    }


def test_datasette_command_quotes_database_path() -> None:
    assert datasette_command(Path("data/processed/ccld.sqlite")) == (
        'datasette "data/processed/ccld.sqlite" '
        '--metadata "data/processed/ccld.datasette-metadata.json"'
    )


def test_datasette_metadata_uses_database_stem_for_custom_paths() -> None:
    metadata = datasette_metadata(Path("data/processed/live-ccld.sqlite"))

    assert metadata["title"] == "CCLD Complaints Review"
    assert "live-ccld" in metadata["databases"]
    database_metadata = metadata["databases"]["live-ccld"]
    assert "complaint_review_summary" in database_metadata["tables"]
    assert "delay_review_flags" in database_metadata["tables"]
    assert "source_traceability_review" in database_metadata["tables"]
    assert "complaints_by_facility" in database_metadata["queries"]
    assert "records_with_delay_review_flags" in database_metadata["queries"]
    assert "source_traceability_check" in database_metadata["queries"]
    assert "allegation_summary_by_facility" in database_metadata["queries"]
    assert "newest_reports" in database_metadata["queries"]
    assert (
        "screening aids"
        in database_metadata["tables"]["delay_review_flags"]["description"]
    )
    assert (
        "Public source URL"
        in database_metadata["tables"]["source_traceability_review"]["columns"]["source_url"]
    )


def test_write_datasette_metadata_writes_json_next_to_database(tmp_path: Path) -> None:
    db_path = tmp_path / "review.sqlite"

    metadata_path = write_datasette_metadata(db_path)

    assert metadata_path == datasette_metadata_path(db_path)
    assert metadata_path.exists()
    assert '"review"' in metadata_path.read_text(encoding="utf-8")


def test_review_workflow_lines_name_first_views() -> None:
    lines = review_workflow_lines()

    assert "Open these Datasette views first:" in lines
    assert any("complaint_review_summary" in line for line in lines)
    assert any("facility_complaint_summary" in line for line in lines)
    assert any("delay_review_flags" in line for line in lines)
    assert any("source_traceability_review" in line for line in lines)


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