from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import cast

from pytest import MonkeyPatch

from ccld_complaints.cli.fetch_live_ccld import (
    facility_intake_summary_lines,
    live_fetch_summary_lines,
)
from ccld_complaints.local_sample import (
    datasette_command,
    datasette_metadata,
    datasette_metadata_path,
    populate_multi_facility_sample_database,
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


def test_populate_multi_facility_sample_database_exercises_fixture_corpus(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "ccld.sqlite"

    result = populate_multi_facility_sample_database(db_path)

    assert result.db_path == db_path
    assert result.intake.facility_numbers == ["157806098", "157806097"]
    assert result.intake.duplicate_facility_numbers == ["157806098"]
    assert result.intake.ignored_value_count == 3
    assert result.intake.invalid_values == []
    assert len(result.ingestion.facility_results) == 2
    assert len(result.ingestion.facility_failures) == 0
    assert len(result.ingestion.records) == 2
    assert _row_count(db_path, "facilities") == 2
    assert _row_count(db_path, "source_documents") == 2
    assert _row_count(db_path, "complaints") == 2
    assert _row_count(db_path, "allegations") == 3

    intake_lines = facility_intake_summary_lines(result.intake)
    assert "- Accepted facility identifiers: 157806098, 157806097" in intake_lines
    assert "- Duplicate identifiers ignored: 157806098" in intake_lines
    assert "- Ignored blank, comment, or header values: 3" in intake_lines

    summary_lines = live_fetch_summary_lines(
        result.ingestion.facility_results,
        result.ingestion.facility_failures,
    )
    assert "- Facilities requested: 2" in summary_lines
    assert "- Facilities with records discovered: 2" in summary_lines
    assert "- Records written: 2" in summary_lines
    assert any("157806098: status=partial report failures" in line for line in summary_lines)
    assert any("157806097: status=records written" in line for line in summary_lines)

    source_rows = _view_rows(
        db_path,
        """
        SELECT facility_number,
               traceability_status,
               complaint_count,
               allegation_count
        FROM multi_facility_source_traceability_review
        ORDER BY facility_number
        """,
    )
    assert source_rows == [
        {
            "facility_number": "157806097",
            "traceability_status": "complete",
            "complaint_count": 1,
            "allegation_count": 1,
        },
        {
            "facility_number": "157806098",
            "traceability_status": "complete",
            "complaint_count": 1,
            "allegation_count": 2,
        },
    ]

    comparison_rows = _view_rows(
        db_path,
        """
        SELECT facility_number,
               allegation_category,
               finding,
               source_document_count,
               complete_source_traceability_document_count,
               facilities_with_same_category_finding,
               comparison_scope_note
        FROM facility_comparison_review
        ORDER BY facility_number
        """,
    )
    assert comparison_rows == [
        {
            "facility_number": "157806097",
            "allegation_category": "Unknown",
            "finding": "Unsubstantiated",
            "source_document_count": 1,
            "complete_source_traceability_document_count": 1,
            "facilities_with_same_category_finding": 2,
            "comparison_scope_note": "screening aid; verify source records before citing",
        },
        {
            "facility_number": "157806098",
            "allegation_category": "Unknown",
            "finding": "Unsubstantiated",
            "source_document_count": 1,
            "complete_source_traceability_document_count": 1,
            "facilities_with_same_category_finding": 2,
            "comparison_scope_note": "screening aid; verify source records before citing",
        },
    ]


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
    assert "complaint_first_pass_review" in database_metadata["tables"]
    assert "complaint_timeline_review" in database_metadata["tables"]
    assert "field_source_traceability_review" in database_metadata["tables"]
    assert "multi_facility_source_traceability_review" in database_metadata["tables"]
    assert "facility_pattern_review" in database_metadata["tables"]
    assert "facility_comparison_review" in database_metadata["tables"]
    assert "complaint_review_summary" in database_metadata["tables"]
    assert "delay_review_flags" in database_metadata["tables"]
    assert "source_traceability_review" in database_metadata["tables"]
    assert "facilities" in database_metadata["tables"]
    assert "source_documents" in database_metadata["tables"]
    assert "complaints" in database_metadata["tables"]
    assert "allegations" in database_metadata["tables"]
    assert "events" in database_metadata["tables"]
    assert "extraction_audit" in database_metadata["tables"]
    assert "review_home" in database_metadata["queries"]
    assert "public_record_allegation_search" in database_metadata["queries"]
    assert "complaint_review_start_here" in database_metadata["queries"]
    assert "complaints_by_facility" in database_metadata["queries"]
    assert "complaint_timeline_by_facility" in database_metadata["queries"]
    assert "complaint_review_export_with_traceability" in database_metadata["queries"]
    assert "records_with_delay_review_flags" in database_metadata["queries"]
    assert "facilities_with_delay_review_flags" in database_metadata["queries"]
    assert "facility_patterns_with_review_flags" in database_metadata["queries"]
    assert "repeated_facility_category_findings" in database_metadata["queries"]
    assert "source_traceability_check" in database_metadata["queries"]
    assert "source_traceability_by_facility" in database_metadata["queries"]
    assert "multi_facility_source_traceability_by_facility" in database_metadata["queries"]
    assert "field_traceability_by_facility" in database_metadata["queries"]
    assert "allegation_summary_by_facility" in database_metadata["queries"]
    assert "newest_reports" in database_metadata["queries"]
    assert (
        "Low-noise first-pass view"
        in database_metadata["tables"]["complaint_first_pass_review"]["description"]
    )
    assert (
        "lower-level follow-up"
        in database_metadata["tables"]["complaint_first_pass_review"]["columns"][
            "complaint_id"
        ]
    )
    assert (
        "screening aids"
        in database_metadata["tables"]["delay_review_flags"]["description"]
    )
    assert (
        "Use after complaint_first_pass_review"
        in database_metadata["tables"]["complaint_review_summary"]["description"]
    )
    assert (
        "not as a complete or official facility history"
        in database_metadata["tables"]["facility_complaint_summary"]["description"]
    )
    assert (
        "Facility-level pattern review"
        in database_metadata["tables"]["facility_pattern_review"]["description"]
    )
    assert (
        "screening aids for closer source review"
        in database_metadata["tables"]["facility_pattern_review"]["description"]
    )
    assert (
        "Comparison-oriented review"
        in database_metadata["tables"]["facility_comparison_review"]["description"]
    )
    assert (
        "facility-wide conduct"
        in database_metadata["tables"]["facility_comparison_review"]["description"]
    )
    assert (
        "same allegation category and finding"
        in database_metadata["tables"]["facility_comparison_review"]["columns"][
            "facilities_with_same_category_finding"
        ]
    )
    assert (
        "Timeline-oriented view"
        in database_metadata["tables"]["complaint_timeline_review"]["description"]
    )
    assert (
        "absence does not prove the event did not occur"
        in database_metadata["tables"]["complaint_timeline_review"]["description"]
    )
    assert (
        "not as a list of delayed investigations"
        in database_metadata["tables"]["delay_review_flags"]["description"]
    )
    assert (
        "Use before citation or export"
        in database_metadata["tables"]["source_traceability_review"]["description"]
    )
    assert (
        "counts of linked complaints"
        in database_metadata["tables"]["multi_facility_source_traceability_review"][
            "description"
        ]
    )
    assert (
        "missing source traceability"
        in database_metadata["tables"]["multi_facility_source_traceability_review"][
            "columns"
        ]["traceability_status"]
    )
    assert (
        "Field-level extraction audit view"
        in database_metadata["tables"]["field_source_traceability_review"]["description"]
    )
    assert (
        "Source text"
        in database_metadata["tables"]["field_source_traceability_review"]["columns"][
            "source_text"
        ]
    )
    assert (
        "Public source URL"
        in database_metadata["tables"]["source_traceability_review"]["columns"]["source_url"]
    )
    assert (
        "preserve traceability"
        in database_metadata["tables"]["source_documents"]["description"]
    )
    assert (
        "screening aids"
        in database_metadata["tables"]["complaints"]["columns"][
            "review_delay_over_30_days"
        ]
    )
    assert (
        ":facility_number"
        in database_metadata["queries"]["complaints_by_facility"]["sql"]
    )
    review_home_query = database_metadata["queries"]["review_home"]
    assert "Open this first" in review_home_query["description"]
    assert "Review complaints" in review_home_query["sql"]
    assert "complaint_first_pass_review" in review_home_query["sql"]
    assert "Search allegation text" in review_home_query["sql"]
    assert "public_record_allegation_search" in review_home_query["sql"]
    assert "Review what happened and when" in review_home_query["sql"]
    assert "complaint_timeline_review" in review_home_query["sql"]
    assert "Find records needing closer review" in review_home_query["sql"]
    assert "Compare facilities" in review_home_query["sql"]
    assert "Review facility patterns" in review_home_query["sql"]
    assert "facility_pattern_review" in review_home_query["sql"]
    assert "Compare repeated categories" in review_home_query["sql"]
    assert "facility_comparison_review" in review_home_query["sql"]
    assert "Verify sources" in review_home_query["sql"]
    assert "multi_facility_source_traceability_review" in review_home_query["sql"]
    assert "Export CSVs" in review_home_query["sql"]
    assert "source URL, raw hash, connector metadata" in review_home_query["sql"]
    assert "workflow_group" in review_home_query["sql"]
    with sqlite3.connect(":memory:") as conn:
        review_home_rows = conn.execute(review_home_query["sql"]).fetchall()
    assert len(review_home_rows) == 9
    assert [row[1] for row in review_home_rows] == [
        "Complaint review",
        "Public-record discovery",
        "Timeline review",
        "Review flags",
        "Facility comparison",
        "Facility comparison",
        "Facility comparison",
        "Source verification",
        "CSV export",
    ]
    assert [row[2] for row in review_home_rows] == [
        "Review complaints",
        "Search allegation text",
        "Review what happened and when",
        "Find records needing closer review",
        "Compare facilities",
        "Review facility patterns",
        "Compare repeated categories",
        "Verify sources",
        "Export CSVs",
    ]
    allegation_search_query = database_metadata["queries"]["public_record_allegation_search"]
    assert "Search source-derived allegation text" in allegation_search_query["description"]
    assert "not as a legal conclusion" in allegation_search_query["description"]
    assert ":search_term" in allegation_search_query["sql"]
    assert "raw_sha256" in allegation_search_query["sql"]
    assert "matched_fields" in allegation_search_query["sql"]
    assert "allegation_text" in allegation_search_query["sql"]
    start_here_query = database_metadata["queries"]["complaint_review_start_here"]
    assert "Open this first" in start_here_query["description"]
    assert "guided first-pass review" in start_here_query["description"]
    assert "Preserve traceability columns" in start_here_query["description"]
    assert "raw_sha256" in start_here_query["sql"]
    assert "connector_version" in start_here_query["sql"]
    assert "retrieved_at" in start_here_query["sql"]
    assert "FROM complaint_first_pass_review" in start_here_query["sql"]
    assert "ORDER BY report_date DESC" in start_here_query["sql"]
    export_query_sql = database_metadata["queries"][
        "complaint_review_export_with_traceability"
    ]["sql"]
    assert "sd.raw_sha256" in export_query_sql
    assert "sd.connector_name" in export_query_sql
    assert "sd.retrieved_at" in export_query_sql
    assert "source_url" in export_query_sql
    assert (
        "screening aids"
        in database_metadata["queries"]["facilities_with_delay_review_flags"][
            "description"
        ]
    )
    assert (
        "not conclusions"
        in database_metadata["queries"]["facility_patterns_with_review_flags"][
            "description"
        ]
    )
    repeated_query = database_metadata["queries"]["repeated_facility_category_findings"]
    assert "source-review queue" in repeated_query["description"]
    assert "FROM facility_comparison_review" in repeated_query["sql"]
    assert "facilities_with_same_category_finding > 1" in repeated_query["sql"]
    assert (
        "do not remove traceability columns"
        in database_metadata["queries"]["complaint_review_export_with_traceability"][
            "description"
        ]
    )
    assert (
        "do not label the export as delayed investigations"
        in database_metadata["queries"]["records_with_delay_review_flags"]["description"]
    )
    assert (
        "Use before relying on or citing extracted records"
        in database_metadata["queries"]["source_traceability_check"]["description"]
    )
    assert (
        ":facility_number"
        in database_metadata["queries"]["source_traceability_by_facility"]["sql"]
    )
    multi_source_query = database_metadata["queries"][
        "multi_facility_source_traceability_by_facility"
    ]
    assert "source-checking aids" in multi_source_query["description"]
    assert ":facility_number" in multi_source_query["sql"]
    assert "FROM multi_facility_source_traceability_review" in multi_source_query["sql"]
    timeline_query = database_metadata["queries"]["complaint_timeline_by_facility"]
    assert "Missing dates are unknown" in timeline_query["description"]
    assert ":facility_number" in timeline_query["sql"]
    assert "FROM complaint_timeline_review" in timeline_query["sql"]
    field_query = database_metadata["queries"]["field_traceability_by_facility"]
    assert "source text, warnings" in field_query["description"]
    assert ":facility_number" in field_query["sql"]
    assert "FROM field_source_traceability_review" in field_query["sql"]


def test_write_datasette_metadata_writes_json_next_to_database(tmp_path: Path) -> None:
    db_path = tmp_path / "review.sqlite"

    metadata_path = write_datasette_metadata(db_path)

    assert metadata_path == datasette_metadata_path(db_path)
    assert metadata_path.exists()
    assert '"review"' in metadata_path.read_text(encoding="utf-8")


def test_review_workflow_lines_name_first_views() -> None:
    lines = review_workflow_lines()

    assert "Next review steps:" in lines
    assert "Open first:" in lines
    assert "For delay triage:" in lines
    assert "For public-record discovery:" in lines
    assert "For timeline review:" in lines
    assert "For source verification:" in lines
    assert "For CSV export:" in lines
    assert "Other useful review paths:" in lines
    assert any("start-here task menu" in line for line in lines)
    assert any("guided complaint review with source traceability" in line for line in lines)
    assert any("records with review flags for closer review" in line for line in lines)
    assert any("source-derived allegation text" in line for line in lines)
    assert any("complaint and event dates" in line for line in lines)
    assert any("screening aids only" in line for line in lines)
    assert any("source URLs, raw hashes, connector details" in line for line in lines)
    assert any("extracted fields with audit source text" in line for line in lines)
    assert any("export complaint fields with source hashes" in line for line in lines)
    assert any("export-review-bundle.ps1" in line for line in lines)
    assert any("complaint_review_summary" in line for line in lines)
    assert any("complaint_first_pass_review" in line for line in lines)
    assert any("facility_complaint_summary" in line for line in lines)
    assert any("facility_pattern_review" in line for line in lines)
    assert any("facility_comparison_review" in line for line in lines)
    assert any("repeated_facility_category_findings" in line for line in lines)
    assert any("delay_review_flags" in line for line in lines)
    assert any("source_traceability_review" in line for line in lines)
    assert any("multi_facility_source_traceability_review" in line for line in lines)
    assert any("review_home" in line for line in lines)
    assert any("complaint_review_start_here" in line for line in lines)
    assert any("public_record_allegation_search" in line for line in lines)
    assert any("complaint_timeline_review" in line for line in lines)
    assert any("complaint_timeline_by_facility" in line for line in lines)
    assert any("complaints_by_facility" in line for line in lines)
    assert any("complaint_review_export_with_traceability" in line for line in lines)
    assert any("source_traceability_by_facility" in line for line in lines)
    assert any("multi_facility_source_traceability_by_facility" in line for line in lines)
    assert any("field_source_traceability_review" in line for line in lines)
    assert any("field_traceability_by_facility" in line for line in lines)
    assert any("newest_reports" in line for line in lines)


def test_public_record_allegation_search_returns_traceable_matches(tmp_path: Path) -> None:
    db_path = tmp_path / "ccld.sqlite"
    populate_sample_database(db_path)
    query_sql = datasette_metadata(db_path)["databases"][db_path.stem]["queries"][
        "public_record_allegation_search"
    ]["sql"]

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query_sql, {"search_term": "supervision"}).fetchall()

    assert len(rows) == 1
    row = dict(rows[0])
    assert row["facility_number"] == "157806098"
    assert row["allegation_text"] == (
        "Facility staff do not provide adequate supervision to the facility clients"
    )
    assert row["matched_fields"] == "allegation text"
    assert row["source_url"].startswith("https://www.ccld.dss.ca.gov/")
    assert row["raw_sha256"]
    assert row["connector_name"] == "ccld_facility_reports"
    assert row["connector_version"] == "0.1.0"
    assert row["retrieved_at"] == "2026-06-10T00:00:00+00:00"
    assert row["report_index"] == 3


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


def _view_rows(db_path: Path, sql: str) -> list[dict[str, object]]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql).fetchall()
    return [dict(row) for row in rows]