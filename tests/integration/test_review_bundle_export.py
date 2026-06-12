from __future__ import annotations

import csv
from pathlib import Path

from ccld_complaints.local_sample import populate_sample_database
from ccld_complaints.review_bundle import export_review_bundle


def test_export_review_bundle_writes_source_traceable_csvs(tmp_path: Path) -> None:
    db_path = tmp_path / "ccld.sqlite"
    output_dir = tmp_path / "review-bundle"
    populate_sample_database(db_path)

    result = export_review_bundle(db_path, output_dir)

    exported_paths = {exported_file.path.name: exported_file for exported_file in result.files}
    assert result.output_dir == output_dir
    assert result.readme_path.exists()
    assert set(exported_paths) == {
        "complaint_review_with_source_traceability.csv",
        "delay_review_flags_with_source_traceability.csv",
        "source_traceability.csv",
    }
    assert exported_paths["complaint_review_with_source_traceability.csv"].row_count == 1
    assert exported_paths["delay_review_flags_with_source_traceability.csv"].row_count == 1
    assert exported_paths["source_traceability.csv"].row_count == 1

    complaint_rows = _read_csv(output_dir / "complaint_review_with_source_traceability.csv")
    assert complaint_rows[0]["facility_number"] == "157806098"
    assert complaint_rows[0]["source_url"].startswith("https://www.ccld.dss.ca.gov/")
    assert complaint_rows[0]["raw_sha256"]
    assert complaint_rows[0]["raw_path"]
    assert complaint_rows[0]["connector_name"] == "ccld_facility_reports"
    assert complaint_rows[0]["connector_version"] == "0.1.0"
    assert complaint_rows[0]["retrieved_at"] == "2026-06-10T00:00:00+00:00"
    assert complaint_rows[0]["report_index"] == "3"
    assert complaint_rows[0]["first_investigation_activity_date"] == "unknown"

    delay_rows = _read_csv(output_dir / "delay_review_flags_with_source_traceability.csv")
    assert delay_rows[0]["review_delay_over_120_days"] == "1"
    assert delay_rows[0]["raw_sha256"] == complaint_rows[0]["raw_sha256"]
    assert delay_rows[0]["source_url"] == complaint_rows[0]["source_url"]

    source_rows = _read_csv(output_dir / "source_traceability.csv")
    assert source_rows[0]["raw_sha256"] == complaint_rows[0]["raw_sha256"]
    assert source_rows[0]["connector_name"] == "ccld_facility_reports"


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
    assert "Unknown database values are exported as \"unknown\"" in readme_text
    assert "raw SHA-256 hash" in readme_text


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as csv_file:
        return list(csv.DictReader(csv_file))