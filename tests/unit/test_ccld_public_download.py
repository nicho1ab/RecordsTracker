"""Focused unit tests for ccld_public_download module."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from ccld_complaints.ccld_public_download import (
    CCLD_DOWNLOAD_HEADER_COL_COUNT,
    FACILITY_REFERENCE_FIELDS,
    LIMITATIONS_NOTE,
    FacilityRefRow,
    ParsedDownloadFile,
    filter_rows,
    parse_ccld_download_csv,
    write_facility_reference_csv,
    write_profile_csv,
    write_profile_json,
)

# ---------------------------------------------------------------------------
# Fixture CSV content helpers
# ---------------------------------------------------------------------------

# Standard 31-column CCLD public download header (same in all download files)
_STANDARD_HEADER = (
    '"Facility Type","Facility Number","Facility Name","Licensee",'
    '"Facility Administrator","Facility Telephone Number","Facility Address",'
    '"Facility City","Facility State","Facility Zip","County Name",'
    '"Regional Office","Facility Capacity","Facility Status",'
    '"License First Date","Closed Date","Last Visit Date",'
    '"Inspection Visits","Complaint Visits","Other Visits","Total Visits",'
    '"Citation Numbers","POC Dates","All Visit Dates","Inspection Visit Dates",'
    '"Inspect TypeA","Inspect TypeB","Other Visit Dates","Other TypeA",'
    '"Other TypeB",'
    '"Complaint Info- Date, #Sub Aleg, # Inc Aleg, # Uns Aleg, # TypeA, # TypeB ..."'
)

def _normal_row(
    ftype: str = "DAY CARE CENTER",
    fnum: str = "100001",
    fname: str = "Test Facility",
    city: str = "Sacramento",
    county: str = "Sacramento",
    status: str = "LICENSED",
    capacity: str = "22",
    license_first: str = "1/1/2010",
    closed: str = "",
    last_visit: str = "6/1/2023",
    complaint_info: str = "No Complaints",
) -> str:
    """Build a normal 31-column data row (no extra trailing values)."""
    cols = [
        ftype, fnum, fname,
        "LICENSEE NAME", "ADMIN NAME", "(916) 555-0001",
        "123 MAIN ST", city, "CA", "95814",
        county, "REGIONAL OFFICE", capacity, status,
        license_first, closed, last_visit,
        "1", "0", "0", "1",
        "", "", "", "",
        "0", "0", "", "0", "0",
        complaint_info,
    ]
    return ",".join(f'"{c}"' for c in cols)


def _row_with_extra_complaint_info(
    fnum: str = "200001",
    fname: str = "Multi-Complaint Facility",
    ftype: str = "DAY CARE CENTER",
    status: str = "LICENSED",
    county: str = "Los Angeles",
    city: str = "Los Angeles",
) -> str:
    """Build a row with extra trailing complaint-info values (> 31 columns)."""
    base = _normal_row(
        ftype=ftype, fnum=fnum, fname=fname, city=city,
        county=county, status=status,
    )
    # Append extra repeating complaint-info groups (each group: date + 5 ints)
    extras = '"06/03/2024","0","0","4","0","0","08/17/2023","0","0","2","0","0"'
    return base.rstrip('"') + f',{extras}'


def _write_csv(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests: parse_ccld_download_csv
# ---------------------------------------------------------------------------


class TestParseCcldDownloadCsv:
    def test_normal_rows_parsed_correctly(self, tmp_path: Path) -> None:
        """Normal rows produce correct FacilityRefRow values."""
        csv_path = tmp_path / "test.csv"
        _write_csv(csv_path, [
            _STANDARD_HEADER,
            _normal_row(fnum="100001", fname="Alpha Center", city="Fresno",
                        county="Fresno", status="LICENSED", capacity="30"),
        ])

        result = parse_ccld_download_csv(csv_path)

        assert result.row_count == 1
        assert result.header_count == CCLD_DOWNLOAD_HEADER_COL_COUNT
        assert result.row_width_warning_count == 0
        assert result.facility_number_present is True
        row = result.rows[0]
        assert row.facility_number == "100001"
        assert row.facility_name == "Alpha Center"
        assert row.city == "Fresno"
        assert row.county == "Fresno"
        assert row.status == "LICENSED"
        assert row.capacity == "30"
        assert row.source_file == "test.csv"

    def test_extra_trailing_columns_tolerated(self, tmp_path: Path) -> None:
        """Rows with extra complaint-info trailing values do not raise."""
        csv_path = tmp_path / "test.csv"
        _write_csv(csv_path, [
            _STANDARD_HEADER,
            _row_with_extra_complaint_info(fnum="200001"),
        ])

        result = parse_ccld_download_csv(csv_path)

        assert result.row_count == 1
        assert result.row_width_warning_count == 1
        # Core facility fields are still parsed correctly
        assert result.rows[0].facility_number == "200001"

    def test_mixed_normal_and_extra_column_rows(self, tmp_path: Path) -> None:
        """Files with both normal and extra-column rows are profiled correctly."""
        csv_path = tmp_path / "test.csv"
        _write_csv(csv_path, [
            _STANDARD_HEADER,
            _normal_row(fnum="100001"),
            _row_with_extra_complaint_info(fnum="200001"),
            _normal_row(fnum="300001"),
        ])

        result = parse_ccld_download_csv(csv_path)

        assert result.row_count == 3
        assert result.row_width_warning_count == 1

    def test_facility_type_counts_accumulated(self, tmp_path: Path) -> None:
        """facility_type_counts tracks counts by type."""
        csv_path = tmp_path / "test.csv"
        _write_csv(csv_path, [
            _STANDARD_HEADER,
            _normal_row(fnum="1", ftype="DAY CARE CENTER"),
            _normal_row(fnum="2", ftype="DAY CARE CENTER"),
            _normal_row(fnum="3", ftype="TEMPORARY SHELTER CARE FACILITY"),
        ])

        result = parse_ccld_download_csv(csv_path)

        assert result.facility_type_counts["DAY CARE CENTER"] == 2
        assert result.facility_type_counts["TEMPORARY SHELTER CARE FACILITY"] == 1

    def test_status_counts_accumulated(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "test.csv"
        _write_csv(csv_path, [
            _STANDARD_HEADER,
            _normal_row(fnum="1", status="LICENSED"),
            _normal_row(fnum="2", status="CLOSED"),
            _normal_row(fnum="3", status="LICENSED"),
        ])

        result = parse_ccld_download_csv(csv_path)

        assert result.status_counts["LICENSED"] == 2
        assert result.status_counts["CLOSED"] == 1

    def test_county_counts_accumulated(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "test.csv"
        _write_csv(csv_path, [
            _STANDARD_HEADER,
            _normal_row(fnum="1", county="Fresno"),
            _normal_row(fnum="2", county="Sacramento"),
            _normal_row(fnum="3", county="Fresno"),
        ])

        result = parse_ccld_download_csv(csv_path)

        assert result.county_counts["Fresno"] == 2
        assert result.county_counts["Sacramento"] == 1

    def test_empty_file_returns_empty_result(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "empty.csv"
        csv_path.write_text("", encoding="utf-8")

        result = parse_ccld_download_csv(csv_path)

        assert result.row_count == 0
        assert result.header_count == 0
        assert result.rows == []

    def test_header_only_file_has_zero_rows(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "header_only.csv"
        _write_csv(csv_path, [_STANDARD_HEADER])

        result = parse_ccld_download_csv(csv_path)

        assert result.row_count == 0
        assert result.header_count == CCLD_DOWNLOAD_HEADER_COL_COUNT

    def test_program_type_is_empty_string(self, tmp_path: Path) -> None:
        """ProgramType is always empty — CCLD download files have no such column."""
        csv_path = tmp_path / "test.csv"
        _write_csv(csv_path, [_STANDARD_HEADER, _normal_row(fnum="100001")])

        result = parse_ccld_download_csv(csv_path)

        assert result.rows[0].program_type == ""

    def test_extra_columns_do_not_bleed_into_facility_fields(
        self, tmp_path: Path
    ) -> None:
        """Extra trailing values must not contaminate facility-reference fields."""
        csv_path = tmp_path / "test.csv"
        _write_csv(csv_path, [
            _STANDARD_HEADER,
            _row_with_extra_complaint_info(fnum="200001", fname="Correct Name"),
        ])

        result = parse_ccld_download_csv(csv_path)

        row = result.rows[0]
        # None of the trailing complaint-info values should appear in facility fields
        assert row.facility_number == "200001"
        assert row.facility_name == "Correct Name"
        # last_visit_date is column 16 — should be the standard value, not complaint info
        assert "200001" not in row.last_visit_date


# ---------------------------------------------------------------------------
# Tests: filter_rows
# ---------------------------------------------------------------------------


class TestFilterRows:
    def _make_rows(self) -> list[FacilityRefRow]:
        def _row(fnum: str, ftype: str, status: str) -> FacilityRefRow:
            return FacilityRefRow(
                facility_number=fnum,
                facility_name=f"Facility {fnum}",
                facility_type=ftype,
                program_type="",
                status=status,
                city="Sacramento",
                county="Sacramento",
                capacity="10",
                license_first_date="",
                closed_date="",
                last_visit_date="",
                source_file="test.csv",
            )

        return [
            _row("1", "DAY CARE CENTER", "LICENSED"),
            _row("2", "TEMPORARY SHELTER CARE FACILITY", "LICENSED"),
            _row("3", "TEMPORARY SHELTER CARE FACILITY", "CLOSED"),
            _row("4", "DAY CARE CENTER", "CLOSED"),
        ]

    def test_no_filter_returns_all(self) -> None:
        rows = self._make_rows()
        assert filter_rows(rows) == rows

    def test_facility_type_filter(self) -> None:
        rows = self._make_rows()
        result = filter_rows(rows, facility_type="TEMPORARY SHELTER CARE FACILITY")
        assert len(result) == 2
        assert all(r.facility_type == "TEMPORARY SHELTER CARE FACILITY" for r in result)

    def test_status_filter(self) -> None:
        rows = self._make_rows()
        result = filter_rows(rows, status="LICENSED")
        assert len(result) == 2
        assert all(r.status == "LICENSED" for r in result)

    def test_combined_filter(self) -> None:
        rows = self._make_rows()
        result = filter_rows(
            rows,
            facility_type="TEMPORARY SHELTER CARE FACILITY",
            status="LICENSED",
        )
        assert len(result) == 1
        assert result[0].facility_number == "2"

    def test_case_insensitive_filter(self) -> None:
        rows = self._make_rows()
        result = filter_rows(rows, facility_type="temporary shelter care facility")
        assert len(result) == 2

    def test_no_match_returns_empty(self) -> None:
        rows = self._make_rows()
        result = filter_rows(rows, facility_type="DOES NOT EXIST")
        assert result == []

    def test_facility_status_excludes_closed_rows(self) -> None:
        """Status filter must exclude rows whose status does not match."""
        rows = self._make_rows()  # 2 LICENSED, 2 CLOSED across all types
        result = filter_rows(rows, status="LICENSED")
        assert all(r.status == "LICENSED" for r in result)
        assert not any(r.status == "CLOSED" for r in result)

    def test_facility_status_excludes_pending_rows(self) -> None:
        """Status filter excludes rows with any non-matching status value."""
        def _row(fnum: str, status: str) -> FacilityRefRow:
            return FacilityRefRow(
                facility_number=fnum, facility_name=f"F{fnum}",
                facility_type="DAY CARE CENTER", program_type="",
                status=status, city="", county="", capacity="",
                license_first_date="", closed_date="", last_visit_date="",
                source_file="test.csv",
            )

        rows = [
            _row("1", "LICENSED"),
            _row("2", "PENDING"),
            _row("3", "CLOSED"),
            _row("4", "LICENSED"),
        ]
        result = filter_rows(rows, status="LICENSED")
        assert len(result) == 2
        assert {r.facility_number for r in result} == {"1", "4"}

    def test_combined_filter_excludes_wrong_type_and_wrong_status(self) -> None:
        """Combined FacilityType + FacilityStatus filter excludes both mismatches."""
        rows = self._make_rows()
        # Only facility #2 is TSCF+LICENSED
        result = filter_rows(
            rows,
            facility_type="TEMPORARY SHELTER CARE FACILITY",
            status="LICENSED",
        )
        assert len(result) == 1
        assert result[0].facility_number == "2"
        # Confirm TSCF+CLOSED (#3) was excluded
        assert not any(r.facility_number == "3" for r in result)
        # Confirm DAY CARE CENTER+LICENSED (#1) was excluded
        assert not any(r.facility_number == "1" for r in result)


# ---------------------------------------------------------------------------
# Tests: write_facility_reference_csv
# ---------------------------------------------------------------------------


class TestWriteFacilityReferenceCsv:
    def _make_row(self, fnum: str = "100001", ftype: str = "DAY CARE CENTER") -> FacilityRefRow:
        return FacilityRefRow(
            facility_number=fnum,
            facility_name="Test Facility",
            facility_type=ftype,
            program_type="",
            status="LICENSED",
            city="Sacramento",
            county="Sacramento",
            capacity="22",
            license_first_date="1/1/2010",
            closed_date="",
            last_visit_date="6/1/2023",
            source_file="source.csv",
        )

    def test_writes_correct_headers(self, tmp_path: Path) -> None:
        out = tmp_path / "ref.csv"
        write_facility_reference_csv([self._make_row()], out)

        with out.open(encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            headers = next(reader)
        assert headers == list(FACILITY_REFERENCE_FIELDS)

    def test_writes_facility_number(self, tmp_path: Path) -> None:
        out = tmp_path / "ref.csv"
        write_facility_reference_csv([self._make_row(fnum="999001")], out)

        with out.open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["FacilityNumber"] == "999001"

    def test_source_file_column_present(self, tmp_path: Path) -> None:
        out = tmp_path / "ref.csv"
        write_facility_reference_csv([self._make_row()], out)

        with out.open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["SourceFile"] == "source.csv"

    def test_returns_row_count(self, tmp_path: Path) -> None:
        out = tmp_path / "ref.csv"
        count = write_facility_reference_csv(
            [self._make_row("1"), self._make_row("2"), self._make_row("3")], out
        )
        assert count == 3

    def test_no_complaint_narrative_in_output(self, tmp_path: Path) -> None:
        """Output must not contain any complaint-info text."""
        csv_source = tmp_path / "source.csv"
        _write_csv(csv_source, [
            _STANDARD_HEADER,
            _row_with_extra_complaint_info(fnum="200001"),
        ])
        parsed = parse_ccld_download_csv(csv_source)
        out = tmp_path / "ref.csv"
        write_facility_reference_csv(parsed.rows, out)

        content = out.read_text(encoding="utf-8")
        # None of the extra complaint-info column names should appear
        assert "Complaint Info" not in content
        assert "Sub Aleg" not in content


# ---------------------------------------------------------------------------
# Tests: write_profile_json / write_profile_csv
# ---------------------------------------------------------------------------


class TestWriteProfileOutputs:
    def _parsed(self, tmp_path: Path) -> ParsedDownloadFile:
        csv_path = tmp_path / "input.csv"
        _write_csv(csv_path, [
            _STANDARD_HEADER,
            _normal_row(fnum="1", ftype="DAY CARE CENTER", status="LICENSED",
                        county="Fresno"),
            _row_with_extra_complaint_info(fnum="2", ftype="DAY CARE CENTER",
                                           status="LICENSED", county="Sacramento"),
        ])
        return parse_ccld_download_csv(csv_path)

    def test_profile_json_structure(self, tmp_path: Path) -> None:
        parsed = self._parsed(tmp_path)
        out = tmp_path / "profile.json"
        write_profile_json([parsed], out)

        data = json.loads(out.read_text(encoding="utf-8"))
        assert "limitations" in data
        assert "files" in data
        assert len(data["files"]) == 1
        file_entry = data["files"][0]
        assert file_entry["row_count"] == 2
        assert file_entry["row_width_warning_count"] == 1
        assert file_entry["facility_number_present"] is True
        assert "facility_type_counts" in file_entry
        assert "status_counts" in file_entry
        assert "county_counts" in file_entry

    def test_profile_json_includes_limitations(self, tmp_path: Path) -> None:
        parsed = self._parsed(tmp_path)
        out = tmp_path / "profile.json"
        write_profile_json([parsed], out)

        data = json.loads(out.read_text(encoding="utf-8"))
        assert LIMITATIONS_NOTE in data["limitations"]

    def test_profile_csv_headers(self, tmp_path: Path) -> None:
        parsed = self._parsed(tmp_path)
        out = tmp_path / "profile.csv"
        write_profile_csv([parsed], out)

        with out.open(encoding="utf-8", newline="") as f:
            headers = next(csv.reader(f))
        assert "file_name" in headers
        assert "row_count" in headers
        assert "row_width_warning_count" in headers
        assert "facility_number_present" in headers

    def test_profile_csv_row_count_value(self, tmp_path: Path) -> None:
        parsed = self._parsed(tmp_path)
        out = tmp_path / "profile.csv"
        write_profile_csv([parsed], out)

        with out.open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["row_count"] == "2"
        assert rows[0]["row_width_warning_count"] == "1"


# ---------------------------------------------------------------------------
# Tests: end-to-end parse → filter → write
# ---------------------------------------------------------------------------


class TestEndToEnd:
    def test_filter_then_write_produces_cohort_csv(self, tmp_path: Path) -> None:
        """Parsing, filtering, and writing a cohort CSV works end-to-end."""
        csv_path = tmp_path / "download.csv"
        _write_csv(csv_path, [
            _STANDARD_HEADER,
            _normal_row(fnum="1", ftype="DAY CARE CENTER", status="LICENSED"),
            _normal_row(fnum="2", ftype="TEMPORARY SHELTER CARE FACILITY",
                        status="LICENSED"),
            _normal_row(fnum="3", ftype="TEMPORARY SHELTER CARE FACILITY",
                        status="CLOSED"),
        ])
        parsed = parse_ccld_download_csv(csv_path)
        filtered = filter_rows(
            parsed.rows,
            facility_type="TEMPORARY SHELTER CARE FACILITY",
            status="LICENSED",
        )
        out = tmp_path / "cohort.csv"
        count = write_facility_reference_csv(filtered, out)

        assert count == 1
        with out.open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["FacilityNumber"] == "2"
        assert rows[0]["FacilityType"] == "TEMPORARY SHELTER CARE FACILITY"

    def test_extra_complaint_info_rows_do_not_contaminate_reference_csv(
        self, tmp_path: Path
    ) -> None:
        """Rows with trailing complaint values produce correct reference output."""
        csv_path = tmp_path / "download.csv"
        _write_csv(csv_path, [
            _STANDARD_HEADER,
            _row_with_extra_complaint_info(
                fnum="200001", fname="Multi-Complaint Facility",
                ftype="DAY CARE CENTER", status="LICENSED",
            ),
        ])
        parsed = parse_ccld_download_csv(csv_path)
        out = tmp_path / "ref.csv"
        write_facility_reference_csv(parsed.rows, out)

        with out.open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1
        row = rows[0]
        assert row["FacilityNumber"] == "200001"
        assert row["FacilityName"] == "Multi-Complaint Facility"
        # Verify the reference CSV only has the expected columns
        assert set(rows[0].keys()) == set(FACILITY_REFERENCE_FIELDS)
