from __future__ import annotations

from pathlib import Path

from ccld_complaints.hosted_app.facility_review_signals import (
    FacilityReviewSignalsSummary,
    load_facility_review_signals,
)


def test_supported_program_summary_csv_loads_facility_review_signals(
    tmp_path: Path,
) -> None:
    csv_path = tmp_path / "24HourResidentialCareforChildren06072026.csv"
    _write_program_summary_csv(
        csv_path,
        rows=(
            _program_summary_row(
                facility_number="015202256",
                facility_name="A Better Way Fixture",
                capacity="050",
                status="LICENSED",
                license_first_date="3/18/2011",
                last_visit_date="4/23/2026",
                inspection_visits="3",
                complaint_visits="2",
                other_visits="1",
                total_visits="6",
                citation_numbers="1565(c), 80061(b)",
                poc_dates="05/23/2025, 06/01/2025",
                inspect_type_a="A1",
                inspect_type_b="B1, B2",
            ),
        ),
    )

    result = load_facility_review_signals((csv_path,))
    summary = result.summary_for_facility("015202256")

    assert result.loaded_source_count == 1
    assert result.unsupported_source_count == 0
    assert result.skipped_malformed_row_count == 0
    assert result.skipped_unsupported_row_count == 0
    assert result.parsed_row_count == 1
    assert isinstance(summary, FacilityReviewSignalsSummary)
    assert summary.facility_number == "015202256"
    assert isinstance(summary.facility_number, str)
    assert summary.facility_name == "A Better Way Fixture"
    assert summary.facility_types == ("FOSTER FAMILY AGENCY",)
    assert summary.statuses == ("LICENSED",)
    assert summary.capacities == ("050",)
    assert summary.counties == ("Alameda",)
    assert summary.regional_offices == ("Bay Area",)
    assert summary.license_first_dates == ("2011-03-18",)
    assert summary.closed_dates == ()
    assert summary.last_visit_date == "2026-04-23"
    assert summary.inspection_visit_count == 3
    assert summary.complaint_visit_count == 2
    assert summary.other_visit_count == 1
    assert summary.total_visit_count == 6
    assert summary.citation_count == 2
    assert summary.type_a_citation_count == 1
    assert summary.type_b_citation_count == 2
    assert summary.poc_date_count == 2
    assert summary.source_dataset_labels == ("24HourResidentialCareforChildren06072026.csv",)
    assert "Recent visit activity" in summary.review_cues
    assert "Complaint visit activity present" in summary.review_cues
    assert "Citation indicator present" in summary.review_cues
    assert "POC indicator present" in summary.review_cues
    assert "High-capacity facility" in summary.review_cues


def test_program_summary_rows_deduplicate_and_aggregate_by_facility(
    tmp_path: Path,
) -> None:
    csv_path = tmp_path / "ChildCareCenters06072026.csv"
    duplicate_row = _program_summary_row(
        facility_number="123456789",
        facility_name="Fixture Center",
        last_visit_date="1/5/2024",
        inspection_visits="1",
        complaint_visits="0",
        other_visits="0",
        total_visits="1",
        citation_numbers="101, 102",
    )
    distinct_row = _program_summary_row(
        facility_number="123456789",
        facility_name="Fixture Center",
        last_visit_date="2/6/2025",
        inspection_visits="0",
        complaint_visits="1",
        other_visits="2",
        total_visits="3",
        poc_dates="02/10/2025",
    )
    _write_program_summary_csv(csv_path, rows=(duplicate_row, duplicate_row, distinct_row))

    result = load_facility_review_signals((csv_path,))
    summary = result.summary_for_facility("123456789")

    assert result.parsed_row_count == 2
    assert summary is not None
    assert summary.last_visit_date == "2025-02-06"
    assert summary.inspection_visit_count == 1
    assert summary.complaint_visit_count == 1
    assert summary.other_visit_count == 2
    assert summary.total_visit_count == 4
    assert summary.citation_count == 2
    assert summary.poc_date_count == 1


def test_program_summary_loader_skips_malformed_shifted_and_unsupported_rows(
    tmp_path: Path,
) -> None:
    supported_csv = tmp_path / "HomeCare06072026.csv"
    _write_program_summary_csv(
        supported_csv,
        rows=(
            _program_summary_row(facility_number="not-a-number"),
            _program_summary_row(facility_number="987654321"),
        ),
        extra_lines=("too,few,columns",),
    )
    unsupported_csv = tmp_path / "community-care-licensing-facilities-metadata.csv"
    unsupported_csv.write_text("Field,Value\nPublisher,Fixture\n", encoding="utf-8")

    result = load_facility_review_signals((supported_csv, unsupported_csv))

    assert result.loaded_source_count == 1
    assert result.unsupported_source_count == 1
    assert result.skipped_malformed_row_count == 1
    assert result.skipped_unsupported_row_count == 1
    assert result.parsed_row_count == 1
    assert result.summary_for_facility("987654321") is not None
    assert result.summary_for_facility("not-a-number") is None


def _program_summary_row(
    *,
    facility_number: str,
    facility_name: str = "Fixture Facility",
    facility_type: str = "FOSTER FAMILY AGENCY",
    city: str = "Oakland",
    state: str = "CA",
    zip_code: str = "94601",
    county: str = "Alameda",
    regional_office: str = "Bay Area",
    capacity: str = "12",
    status: str = "LICENSED",
    license_first_date: str = "",
    closed_date: str = "",
    last_visit_date: str = "",
    inspection_visits: str = "0",
    complaint_visits: str = "0",
    other_visits: str = "0",
    total_visits: str = "0",
    citation_numbers: str = "",
    poc_dates: str = "",
    inspect_type_a: str = "",
    inspect_type_b: str = "",
    other_type_a: str = "",
    other_type_b: str = "",
) -> dict[str, str]:
    return {
        "Facility Type": facility_type,
        "Facility Number": facility_number,
        "Facility Name": facility_name,
        "Licensee": "Do Not Display Licensee",
        "Facility Administrator": "Do Not Display Admin",
        "Facility Telephone Number": "555-0199",
        "Facility Address": "1 Private Fixture Way",
        "Facility City": city,
        "Facility State": state,
        "Facility Zip": zip_code,
        "County Name": county,
        "Regional Office": regional_office,
        "Facility Capacity": capacity,
        "Facility Status": status,
        "License First Date": license_first_date,
        "Closed Date": closed_date,
        "Last Visit Date": last_visit_date,
        "Inspection Visits": inspection_visits,
        "Complaint Visits": complaint_visits,
        "Other Visits": other_visits,
        "Total Visits": total_visits,
        "Citation Numbers": citation_numbers,
        "POC Dates": poc_dates,
        "All Visit Dates": "",
        "Inspection Visit Dates": "",
        "Inspect TypeA": inspect_type_a,
        "Inspect TypeB": inspect_type_b,
        "Other Visit Dates": "",
        "Other TypeA": other_type_a,
        "Other TypeB": other_type_b,
        "Complaint Info- Date, #Sub Aleg, # Inc Aleg, # Uns Aleg, # TypeA, # TypeB ...": "",
    }


def _write_program_summary_csv(
    path: Path,
    *,
    rows: tuple[dict[str, str], ...],
    extra_lines: tuple[str, ...] = (),
) -> None:
    fieldnames = tuple(_program_summary_row(facility_number="0"))
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        csv_file.write(",".join(f'"{fieldname}"' for fieldname in fieldnames) + "\n")
        for row in rows:
            csv_file.write(
                ",".join(f'"{row.get(fieldname, "")}"' for fieldname in fieldnames)
                + "\n"
            )
        for line in extra_lines:
            csv_file.write(line + "\n")