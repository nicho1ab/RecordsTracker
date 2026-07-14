from __future__ import annotations

import csv
import json
from pathlib import Path

from ccld_complaints.local_sample import (
    populate_multi_facility_sample_database,
    populate_sample_database,
)
from ccld_complaints.review_bundle import _export_value, export_review_bundle


def test_export_review_bundle_writes_source_traceable_csvs(tmp_path: Path) -> None:
    db_path = tmp_path / "ccld.sqlite"
    output_dir = tmp_path / "review-bundle"
    populate_sample_database(db_path)

    result = export_review_bundle(db_path, output_dir)

    exported_paths = {exported_file.path.name: exported_file for exported_file in result.files}
    assert result.output_dir == output_dir
    assert result.readme_path.exists()
    assert result.manifest_path.exists()
    assert set(exported_paths) == {
        "complaint_review_with_source_traceability.csv",
        "delay_review_flags_with_source_traceability.csv",
        "source_traceability.csv",
        "multi_facility_source_traceability.csv",
        "complaint_timeline_with_source_traceability.csv",
        "field_source_traceability.csv",
        "facility_pattern_review.csv",
        "facility_comparison_review.csv",
    }
    assert exported_paths["complaint_review_with_source_traceability.csv"].row_count == 1
    assert exported_paths["delay_review_flags_with_source_traceability.csv"].row_count == 0
    assert exported_paths["source_traceability.csv"].row_count == 1
    assert exported_paths["multi_facility_source_traceability.csv"].row_count == 1
    assert exported_paths["complaint_timeline_with_source_traceability.csv"].row_count == 6
    assert exported_paths["field_source_traceability.csv"].row_count == 28
    assert exported_paths["facility_pattern_review.csv"].row_count == 1
    assert exported_paths["facility_comparison_review.csv"].row_count == 1

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["manifest_version"] == 2
    assert "Stored values remain unchanged" in manifest["presentation_value_contract"]
    assert manifest["date_dimension"] == "complaint_received_date"
    assert manifest["explicit_limit"] is None
    assert manifest["truncated"] is False
    assert len(manifest["exports"]) == len(exported_paths)
    complaint_manifest = next(
        item
        for item in manifest["exports"]
        if item["file"] == "complaint_review_with_source_traceability.csv"
    )
    assert complaint_manifest["eligible_count"] == 1
    assert complaint_manifest["returned_count"] == 1
    assert complaint_manifest["source_coverage_count"] == 1
    assert complaint_manifest["status"] == "available"

    complaint_rows = _read_csv(output_dir / "complaint_review_with_source_traceability.csv")
    assert complaint_rows[0]["facility_number"] == "157806098"
    assert complaint_rows[0]["source_url"].startswith("https://www.ccld.dss.ca.gov/")
    assert complaint_rows[0]["raw_sha256"]
    assert complaint_rows[0]["raw_path"]
    assert complaint_rows[0]["connector_name"] == "ccld_facility_reports"
    assert complaint_rows[0]["connector_version"] == "0.1.0"
    assert complaint_rows[0]["retrieved_at"] == "2026-06-10T00:00:00+00:00"
    assert complaint_rows[0]["report_index"] == "3"
    assert complaint_rows[0]["first_investigation_activity_date"] == "2022-04-14"
    assert complaint_rows[0][
        "Days from Complaint Received to First Investigation Activity"
    ] == "7"
    assert complaint_rows[0]["Days from Complaint Received to Visit"] == "139"
    assert complaint_rows[0]["Days from Complaint Received to Report"] == "139"
    assert complaint_rows[0]["Days from Report to Signed"] == "2"

    delay_rows = _read_csv(output_dir / "delay_review_flags_with_source_traceability.csv")
    assert delay_rows == []

    source_rows = _read_csv(output_dir / "source_traceability.csv")
    assert source_rows[0]["raw_sha256"] == complaint_rows[0]["raw_sha256"]
    assert source_rows[0]["connector_name"] == "ccld_facility_reports"

    multi_source_rows = _read_csv(output_dir / "multi_facility_source_traceability.csv")
    assert multi_source_rows[0]["facility_number"] == "157806098"
    assert multi_source_rows[0]["traceability_status"] == "complete"
    assert multi_source_rows[0]["complaint_count"] == "1"
    assert multi_source_rows[0]["allegation_count"] == "2"
    assert multi_source_rows[0]["raw_sha256"] == complaint_rows[0]["raw_sha256"]

    timeline_rows = _read_csv(output_dir / "complaint_timeline_with_source_traceability.csv")
    assert timeline_rows[0]["timeline_item_type"] == "complaint received"
    assert timeline_rows[0]["raw_sha256"] == complaint_rows[0]["raw_sha256"]
    assert timeline_rows[0]["source_url"] == complaint_rows[0]["source_url"]

    field_rows = _read_csv(output_dir / "field_source_traceability.csv")
    assert field_rows[0]["facility_number"] == "157806098"
    assert field_rows[0]["field_name"]
    assert field_rows[0]["source_url"] == complaint_rows[0]["source_url"]
    assert field_rows[0]["raw_sha256"] == complaint_rows[0]["raw_sha256"]

    pattern_rows = _read_csv(output_dir / "facility_pattern_review.csv")
    assert pattern_rows[0]["facility_number"] == "157806098"
    assert pattern_rows[0]["source_document_count"] == "1"
    assert pattern_rows[0]["records_with_review_flags"] == "0"
    assert all(value != "" for row in complaint_rows for value in row.values())

    comparison_rows = _read_csv(output_dir / "facility_comparison_review.csv")
    assert comparison_rows[0]["facility_number"] == "157806098"
    assert comparison_rows[0]["finding"] == "Unsubstantiated"
    assert comparison_rows[0]["source_document_count"] == "1"
    assert comparison_rows[0]["complete_source_traceability_document_count"] == "1"
    assert comparison_rows[0]["facilities_with_same_category_finding"] == "1"
    assert comparison_rows[0]["comparison_scope_note"] == (
        "screening aid; verify source records before citing"
    )


def test_export_review_bundle_writes_accessible_review_notes(tmp_path: Path) -> None:
    db_path = tmp_path / "ccld.sqlite"
    output_dir = tmp_path / "review-bundle"
    populate_sample_database(db_path)

    result = export_review_bundle(db_path, output_dir)

    readme_text = result.readme_path.read_text(encoding="utf-8")
    assert "# CCLD Complaint Review Bundle" in readme_text
    assert "public portal remains the source of record" in readme_text
    assert "screening aids" in readme_text
    assert "not conclusions" in readme_text
    assert "flagged for review based on available extracted dates" in readme_text
    assert "Missing database values use field-aware labels" in readme_text
    assert "verified numeric zero remains \"0\"" in readme_text
    assert "raw SHA-256 hash" in readme_text
    assert "complaint_timeline_with_source_traceability.csv" in readme_text
    assert "field_source_traceability.csv" in readme_text
    assert "facility_pattern_review.csv" in readme_text
    assert "multi_facility_source_traceability.csv" in readme_text
    assert "facility_comparison_review.csv" in readme_text
    assert "not findings about a facility" in readme_text
    assert "not conclusions about facilities" in readme_text
    assert "source text, warnings, confidence" in readme_text


def test_export_review_bundle_covers_multi_facility_fixture_corpus(tmp_path: Path) -> None:
    db_path = tmp_path / "ccld.sqlite"
    output_dir = tmp_path / "review-bundle"
    populate_multi_facility_sample_database(db_path)

    result = export_review_bundle(db_path, output_dir)

    exported_paths = {exported_file.path.name: exported_file for exported_file in result.files}
    assert exported_paths["complaint_review_with_source_traceability.csv"].row_count == 2
    assert exported_paths["multi_facility_source_traceability.csv"].row_count == 2
    assert exported_paths["facility_comparison_review.csv"].row_count == 2

    complaint_rows = _read_csv(output_dir / "complaint_review_with_source_traceability.csv")
    assert {row["facility_number"] for row in complaint_rows} == {"157806097", "157806098"}
    assert {row["connector_name"] for row in complaint_rows} == {"ccld_facility_reports"}
    assert all(row["raw_sha256"] for row in complaint_rows)
    assert all(
        row["source_url"].startswith("https://www.ccld.dss.ca.gov/")
        for row in complaint_rows
    )

    multi_source_rows = _read_csv(output_dir / "multi_facility_source_traceability.csv")
    assert {row["facility_number"] for row in multi_source_rows} == {"157806097", "157806098"}
    assert {row["traceability_status"] for row in multi_source_rows} == {"complete"}
    assert {row["complaint_count"] for row in multi_source_rows} == {"1"}

    comparison_rows = _read_csv(output_dir / "facility_comparison_review.csv")
    assert {row["facility_number"] for row in comparison_rows} == {"157806097", "157806098"}
    assert {row["finding"] for row in comparison_rows} == {"Unsubstantiated"}
    assert {row["facilities_with_same_category_finding"] for row in comparison_rows} == {"2"}
    assert {row["comparison_scope_note"] for row in comparison_rows} == {
        "screening aid; verify source records before citing"
    }


def test_review_bundle_export_values_do_not_fabricate_zero() -> None:
    assert _export_value(0, column_name="days_received_to_first_activity") == "0"
    assert (
        _export_value(
            0,
            column_name="Days from Complaint Received to Visit",
        )
        == "0"
    )
    assert _export_value(None, column_name="days_received_to_first_activity") == (
        "Not provided"
    )
    assert _export_value("", column_name="days_received_to_first_activity") == (
        "Not provided"
    )
    assert _export_value("bad", column_name="days_received_to_first_activity") == (
        "Invalid source value"
    )
    assert _export_value(
        "bad",
        column_name="Days from Complaint Received to Report",
    ) == "Invalid source value"
    assert _export_value(None, column_name="report_date") == "Date not provided"
    assert _export_value("bad", column_name="report_date") == "Invalid source value"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as csv_file:
        return list(csv.DictReader(csv_file))
