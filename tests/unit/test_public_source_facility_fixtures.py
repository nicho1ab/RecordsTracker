from __future__ import annotations

import csv
import re
from pathlib import Path

FIXTURE_DIR = Path("tests/fixtures/public_source_facilities")
MANIFEST_PATH = FIXTURE_DIR / "source_fixture_manifest.csv"
FIXTURE_FILES = [
    FIXTURE_DIR / "ccld_program_facilities_tiny.csv",
    FIXTURE_DIR / "chhs_facility_master_tiny.csv",
]
MAX_FIXTURE_BYTES = 6_000
MAX_DATA_ROWS = 3
REQUIRED_MANIFEST_COLUMNS = {
    "fixture_file",
    "profiled_source_shape",
    "source_family",
    "jurisdiction",
    "source_dataset_reference",
    "source_url_placeholder",
    "raw_sha256_placeholder",
    "retrieved_at_placeholder",
    "intended_future_use",
    "not_for",
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as csv_file:
        return list(csv.DictReader(csv_file))


def test_public_source_facility_fixture_files_are_present_and_tiny() -> None:
    assert (FIXTURE_DIR / "README.md").is_file()
    assert MANIFEST_PATH.is_file()

    for fixture_path in FIXTURE_FILES:
        assert fixture_path.is_file()
        assert fixture_path.stat().st_size < MAX_FIXTURE_BYTES
        assert len(_read_csv(fixture_path)) <= MAX_DATA_ROWS


def test_manifest_has_traceability_style_columns_and_safe_placeholders() -> None:
    with MANIFEST_PATH.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        assert reader.fieldnames is not None
        assert REQUIRED_MANIFEST_COLUMNS.issubset(set(reader.fieldnames))
        rows = list(reader)

    assert {row["fixture_file"] for row in rows} == {
        "ccld_program_facilities_tiny.csv",
        "chhs_facility_master_tiny.csv",
    }
    for row in rows:
        assert row["jurisdiction"] == "California"
        assert row["source_family"]
        assert row["source_dataset_reference"]
        assert row["source_url_placeholder"].startswith("https://example.invalid/")
        assert re.fullmatch(r"[0-9a-f]{64}", row["raw_sha256_placeholder"])
        assert re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z",
            row["retrieved_at_placeholder"],
        )
        assert "Future read-only hosted source/facility view" in row["intended_future_use"]
        assert "Production import" in row["not_for"]


def test_ccld_program_fixture_has_required_facility_view_fields() -> None:
    rows = _read_csv(FIXTURE_DIR / "ccld_program_facilities_tiny.csv")
    assert len(rows) == 2
    assert set(rows[0]) >= {
        "Facility Type",
        "Facility Number",
        "Facility Name",
        "County Name",
        "Facility Status",
        "Facility Capacity",
    }
    assert {row["Facility Number"] for row in rows} == {"900000001", "900000002"}
    assert all(row["Facility Name"].startswith("Synthetic ") for row in rows)
    assert {row["County Name"] for row in rows} == {"Los Angeles", "Sacramento"}


def test_chhs_facility_master_fixture_has_required_facility_view_fields() -> None:
    rows = _read_csv(FIXTURE_DIR / "chhs_facility_master_tiny.csv")
    assert len(rows) == 2
    assert set(rows[0]) >= {
        "FAC_NBR",
        "NAME",
        "TYPE",
        "PROGRAM_TYPE",
        "COUNTY",
        "STATUS",
        "CAPACITY",
        "RES_CITY",
        "RES_STATE",
    }
    assert {row["FAC_NBR"] for row in rows} == {"900000001", "900000002"}
    assert all(row["NAME"].startswith("Synthetic ") for row in rows)
    assert {row["COUNTY"] for row in rows} == {"Los Angeles", "Sacramento"}


def test_public_source_facility_fixtures_do_not_look_like_full_raw_dumps() -> None:
    forbidden_paths = ("data/raw/", "data/processed/", "data/logs/")
    for fixture_path in [*FIXTURE_FILES, MANIFEST_PATH]:
        normalized_path = fixture_path.as_posix()
        assert not normalized_path.startswith(forbidden_paths)
        text = fixture_path.read_text(encoding="utf-8")
        assert "Radware Captcha" not in text
        assert "<html" not in text.casefold()
        assert text.count("\n") <= 6