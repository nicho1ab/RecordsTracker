from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

from ccld_complaints.source_profiling import profile_csv_file, profile_csv_tree
from ccld_complaints.utils.hash import sha256_bytes

FIXTURE_DIR = Path("tests/fixtures/source_profiling")


def test_profiles_normal_csv_with_hash_missing_values_and_candidates() -> None:
    fixture_path = FIXTURE_DIR / "facilities_profile_sample.csv"

    profile = profile_csv_file(fixture_path, FIXTURE_DIR, Path("."))

    assert profile["source_file_path"] == (
        "tests/fixtures/source_profiling/facilities_profile_sample.csv"
    )
    assert profile["file_name"] == "facilities_profile_sample.csv"
    assert profile["sha256"] == sha256_bytes(fixture_path.read_bytes())
    assert profile["encoding"] == "utf-8-sig"
    assert profile["row_count"] == 3
    assert profile["column_count"] == 6
    assert profile["header_names"] == [
        "facility_number",
        "facility_name",
        "county",
        "inspection_date",
        "license_id",
        "status",
    ]
    assert profile["has_duplicate_headers"] is False
    assert profile["has_blank_headers"] is False
    assert profile["parser_warning_count"] == 0
    assert profile["malformed_row_count"] == 0
    assert "inspection_date" in profile["date_like_column_candidates"]
    assert "facility_number" in profile["identifier_like_column_candidates"]
    assert "facility_number" in profile["likely_facility_number_source_identifier_candidates"]
    assert "county" in profile["likely_county_geography_candidates"]
    assert profile["suitable_for_tiny_fixture_creation"] is True

    columns = {column["header_name"]: column for column in profile["columns"]}
    assert columns["facility_name"]["missing_value_count"] == 1
    assert columns["county"]["missing_value_count"] == 1
    assert columns["status"]["missing_value_count"] == 1
    assert columns["facility_name"]["sample_values"] == [
        "Synthetic Family Home",
        "Synthetic Center",
    ]


def test_profiles_duplicate_blank_headers_and_irregular_rows() -> None:
    fixture_path = FIXTURE_DIR / "irregular_headers_sample.csv"

    profile = profile_csv_file(fixture_path, FIXTURE_DIR, Path("."))

    assert profile["has_duplicate_headers"] is True
    assert profile["duplicate_headers"] == ["county"]
    assert profile["has_blank_headers"] is True
    assert profile["blank_header_indexes"] == [2]
    assert profile["malformed_row_count"] == 2
    assert profile["rows_with_unexpected_column_count"] == [
        {"row_number": 3, "expected_column_count": 5, "actual_column_count": 3},
        {"row_number": 4, "expected_column_count": 5, "actual_column_count": 6},
    ]
    assert profile["parser_warning_count"] == 0
    assert "updated_date" in profile["date_like_column_candidates"]
    assert "facility_number" in profile["likely_facility_number_source_identifier_candidates"]
    assert "county" in profile["likely_county_geography_candidates"]


def test_profile_tree_writes_json_csv_and_log_outputs(tmp_path: Path) -> None:
    source_root = tmp_path / "source-profiling"
    nested = source_root / "downloads"
    nested.mkdir(parents=True)
    shutil.copy(FIXTURE_DIR / "facilities_profile_sample.csv", source_root / "normal.csv")
    shutil.copy(FIXTURE_DIR / "irregular_headers_sample.csv", nested / "irregular.csv")
    (source_root / "not-a-csv.html").write_text("<html>not profiled</html>", encoding="utf-8")
    output_dir = tmp_path / "processed" / "source-profiling"
    log_path = tmp_path / "logs" / "source-profiling.log"

    summary = profile_csv_tree(source_root, output_dir, log_path, workspace_root=tmp_path)

    assert summary["outputs_are_local_only"] is True
    assert summary["raw_files_modified"] is False
    assert summary["imports_data"] is False
    assert summary["creates_canonical_fields"] is False
    assert summary["totals"]["csv_file_count"] == 2
    assert summary["totals"]["skipped_non_csv_file_count"] == 1
    assert summary["totals"]["total_row_count"] == 6
    assert summary["totals"]["total_malformed_row_count"] == 2
    assert (output_dir / "csv-profile-summary.json").is_file()
    assert (output_dir / "csv-profile-summary.csv").is_file()
    assert log_path.is_file()

    json_summary = json.loads((output_dir / "csv-profile-summary.json").read_text(encoding="utf-8"))
    assert json_summary["totals"] == summary["totals"]
    assert {profile["source_relative_path"] for profile in json_summary["profiles"]} == {
        "downloads/irregular.csv",
        "normal.csv",
    }

    with (output_dir / "csv-profile-summary.csv").open(encoding="utf-8", newline="") as csv_file:
        rows = list(csv.DictReader(csv_file))
    assert len(rows) == 2
    assert {row["file_name"] for row in rows} == {"normal.csv", "irregular.csv"}
    assert "Local-only boundary" in log_path.read_text(encoding="utf-8")


def test_invalid_sniffed_dialect_falls_back_to_standard_csv(tmp_path: Path) -> None:
    source_root = tmp_path / "source-profiling"
    source_root.mkdir()
    csv_path = source_root / "sample.csv"
    csv_path.write_text("a,b\n1,2\n", encoding="utf-8")

    class InvalidDialect(csv.Dialect):
        delimiter = ""
        quotechar = '"'
        escapechar = None
        doublequote = True
        skipinitialspace = False
        lineterminator = "\r\n"
        quoting = csv.QUOTE_MINIMAL

    profile = profile_csv_file(csv_path, source_root, tmp_path, None, InvalidDialect)

    assert profile["row_count"] == 1
    assert profile["column_count"] == 2
    assert profile["parser_warning_count"] == 1
    assert "dialect warning" in profile["parser_warnings"][0]