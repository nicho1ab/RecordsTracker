from __future__ import annotations

import csv
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.engine import Connection

from ccld_complaints.hosted_app import facility_reference_preload as preload_module
from ccld_complaints.hosted_app.app import route_response
from ccld_complaints.hosted_app.auth import load_hosted_auth_runtime_config
from ccld_complaints.hosted_app.ccld_facility_lookup import CCLD_FACILITY_LOOKUP_PATH
from ccld_complaints.hosted_app.ccld_record_request_ui import (
    ccld_record_request_context_for_reviewer_context,
)
from ccld_complaints.hosted_app.facility_reference_preload import (
    FACILITY_REFERENCE_TABLE_NAME,
    diagnose_facility_reference_address,
    facility_reference_source_from_connection,
    hosted_facility_reference_metadata,
    hosted_facility_reference_records,
    load_facility_reference_preload,
    parse_facility_reference_csv,
)
from ccld_complaints.hosted_app.reviewer_ui import reviewer_ui_context_for_connection
from ccld_complaints.hosted_app.seeded_import import hosted_seeded_import_metadata


def test_facility_reference_table_shape_includes_lookup_columns_and_indexes() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_facility_reference_metadata.create_all(engine)
    inspector = inspect(engine)

    columns = {column["name"] for column in inspector.get_columns(FACILITY_REFERENCE_TABLE_NAME)}
    indexes = {index["name"] for index in inspector.get_indexes(FACILITY_REFERENCE_TABLE_NAME)}
    primary_key = inspector.get_pk_constraint(FACILITY_REFERENCE_TABLE_NAME)

    assert {
        "facility_number",
        "facility_name",
        "facility_type",
        "program_type",
        "client_served",
        "licensee_name",
        "facility_administrator",
        "telephone",
        "address",
        "city",
        "state",
        "zip",
        "county",
        "regional_office",
        "capacity",
        "status",
        "license_first_date",
        "closed_date",
        "all_visit_dates",
        "inspection_visit_dates",
        "other_visit_dates",
        "snapshot_date",
        "source_resource_id",
        "source_resource_name",
        "source_dataset_slug",
        "source_dataset_url",
        "source_accessed_at",
        "source_file_name",
        "original_row_json",
    }.issubset(columns)
    assert primary_key["constrained_columns"] == ["source_resource_id", "facility_number"]
    assert {
        "ix_hosted_facility_reference_records_facility_number",
        "ix_hosted_facility_reference_records_facility_name",
        "ix_hosted_facility_reference_records_type_program",
        "ix_hosted_facility_reference_records_county",
        "ix_hosted_facility_reference_records_status",
        "ix_hosted_facility_reference_records_city",
        "ix_hosted_facility_reference_records_zip",
    }.issubset(indexes)


def test_parser_normalizes_program_facility_rows_and_preserves_source_metadata(
    tmp_path: Path,
) -> None:
    csv_path = tmp_path / "ChildCareCenters06072026.csv"
    _write_program_csv(
        csv_path,
        (
            {
                "Facility Number": " 900000123 ",
                "Facility Name": " Orchard Child Care ",
                "Facility Type": "Child Care Center",
                "Program Type": "Child Care",
                "Licensee": "Fixture Licensee",
                "Facility Administrator": "Fixture Admin",
                "Facility Telephone Number": "555-0100",
                "Facility Address": "1 Main St",
                "Facility City": "Sample City",
                "Facility State": "CA",
                "Facility Zip": "90001",
                "County Name": "Los Angeles",
                "Regional Office": "Regional Office",
                "Facility Capacity": "24",
                "Facility Status": "Licensed",
                "License First Date": "6/7/2020",
                "Closed Date": "07/01/2026",
                "All Visit Dates": "2026-06-15; 06/07/2026; 2026-06-15",
                "Inspection Visit Dates": "06-08-2026; 2026-06-07",
                "Other Visit Dates": "",
            },
            {
                "Facility Number": "",
                "Facility Name": "Missing Number",
            },
        ),
    )

    result = parse_facility_reference_csv(
        csv_path,
        source_accessed_at="2026-07-01T12:00:00+00:00",
    )
    [record] = result.records

    assert result.source_resource_id == "7aed8063-cea7-4367-8651-c81643164ae0"
    assert result.source_resource_name == "Child Care Centers"
    assert result.skipped_row_count == 1
    assert result.warnings[0].row_number == 3
    assert record.facility_number == "900000123"
    assert record.facility_name == "Orchard Child Care"
    assert record.facility_type == "Child Care Center"
    assert record.county == "Los Angeles"
    assert record.regional_office == "Regional Office"
    assert record.capacity == 24
    assert record.status == "Licensed"
    assert record.license_first_date == "2020-06-07"
    assert record.closed_date == "2026-07-01"
    assert record.all_visit_dates == ("2026-06-07", "2026-06-15")
    assert record.inspection_visit_dates == ("2026-06-07", "2026-06-08")
    assert record.other_visit_dates is None
    assert record.values()["all_visit_dates"] == ["2026-06-07", "2026-06-15"]
    assert record.values()["other_visit_dates"] is None
    assert record.snapshot_date == "2026-06-07"
    assert record.source_dataset_slug == "ccl-facilities"
    assert record.source_file_name == "ChildCareCenters06072026.csv"
    assert record.original_row_json["Licensee"] == "Fixture Licensee"


def test_parser_normalizes_chhs_facility_master_shape(tmp_path: Path) -> None:
    csv_path = tmp_path / "CDSS_CCL_Facilities_2065342970436235361.csv"
    _write_master_csv(
        csv_path,
        (
            {
                "FAC_NBR": "214005552",
                "NAME": "SUSD- TOMALES PRESCHOOL",
                "PROGRAM_TYPE": "CHILD CARE",
                "STATUS": "3",
                "CLIENT_SERVED": "Children",
                "CAPACITY": "24",
                "RES_STREET_ADDR": "40 JOHN STREET",
                "RES_CITY": "TOMALES",
                "RES_STATE": "CA",
                "RES_ZIP_CODE": "94971",
                "COUNTY": "Marin",
                "FAC_DO_DESC": "North Bay",
                "FAC_TYPE_DESC": "DAY CARE CENTER",
                "FAC_PHONE_NBR": "7078782214",
            },
        ),
    )

    result = parse_facility_reference_csv(csv_path)
    [record] = result.records

    assert record.source_resource_id.startswith("needs-confirmation:")
    assert record.facility_number == "214005552"
    assert record.facility_name == "SUSD- TOMALES PRESCHOOL"
    assert record.program_type == "CHILD CARE"
    assert record.client_served == "Children"
    assert record.facility_type == "DAY CARE CENTER"
    assert record.regional_office == "North Bay"
    assert record.capacity == 24
    assert record.closed_date is None
    assert record.all_visit_dates is None
    assert record.inspection_visit_dates is None
    assert record.other_visit_dates is None
    assert result.warnings == ()


def test_parser_keeps_chhs_numeric_type_as_provenance_only(tmp_path: Path) -> None:
    csv_path = tmp_path / "CDSS_CCL_Facilities_2065342970436235361.csv"
    _write_master_csv(
        csv_path,
        (
            {
                "FAC_NBR": "214005553",
                "NAME": "CHHS TYPE CODE FACILITY",
                "TYPE": "850",
                "FAC_TYPE_DESC": "",
            },
        ),
    )

    result = parse_facility_reference_csv(csv_path)
    [record] = result.records

    assert record.facility_type is None
    assert record.original_row_json["TYPE"] == "850"


def test_parser_keeps_invalid_and_blank_reference_dates_null_with_warnings(
    tmp_path: Path,
) -> None:
    csv_path = tmp_path / "HomeCare.csv"
    _write_program_csv(
        csv_path,
        (
            {
                "Facility Number": "920000009",
                "Facility Name": "Invalid Date Home Care",
                "Facility Capacity": "not-a-number",
                "Closed Date": "not-a-date",
                "All Visit Dates": "2026-06-07; not-a-date",
                "Inspection Visit Dates": "",
                "Other Visit Dates": "invalid",
            },
        ),
    )

    result = parse_facility_reference_csv(csv_path)
    [record] = result.records

    assert record.capacity is None
    assert record.closed_date is None
    assert record.all_visit_dates is None
    assert record.inspection_visit_dates is None
    assert record.other_visit_dates is None
    assert record.values()["all_visit_dates"] is None
    assert record.values()["inspection_visit_dates"] is None
    assert record.values()["other_visit_dates"] is None
    assert record.original_row_json["Facility Capacity"] == "not-a-number"
    assert [(warning.row_number, warning.message) for warning in result.warnings] == [
        (2, "Capacity was not numeric."),
        (2, "Closed Date was not a valid date."),
        (2, "All Visit Dates contained a value that was not a valid date."),
        (2, "Other Visit Dates contained a value that was not a valid date."),
    ]


def test_parser_preserves_declared_complaint_info_and_overflow_as_provenance(
    tmp_path: Path,
) -> None:
    csv_path = tmp_path / "ChildCareCenters.csv"
    complaint_info_header = (
        "Complaint Info- Date, #Sub Aleg, # Inc Aleg, # Uns Aleg, # TypeA, # TypeB ..."
    )
    _write_program_csv_with_overflow(
        csv_path,
        {
            "Facility Number": "900000777",
            "Facility Name": "Overflow Child Care",
            complaint_info_header: "2026-06-07: 0 sub; 1 inc; 0 uns",
        },
        ("2026-06-14", "2", "1", "0", "1", "0"),
    )

    result = parse_facility_reference_csv(csv_path)
    [record] = result.records

    assert record.original_row_json[complaint_info_header] == ("2026-06-07: 0 sub; 1 inc; 0 uns")
    assert record.original_row_json[preload_module.SOURCE_CSV_OVERFLOW_PROVENANCE_KEY] == [
        "2026-06-14",
        "2",
        "1",
        "0",
        "1",
        "0",
    ]
    assert "complaint_info" not in record.values()


def test_preload_dry_run_apply_and_refresh_are_idempotent(tmp_path: Path) -> None:
    csv_path = tmp_path / "FamilyChildCareHomes.csv"
    _write_program_csv(
        csv_path,
        (
            {
                "Facility Number": "910000001",
                "Facility Name": "Family Home One",
                "Facility Type": "Family Child Care Home",
                "Facility Capacity": "8",
                "Facility Status": "Licensed",
                "All Visit Dates": "2026-06-15; 2026-06-07; 2026-06-15",
            },
        ),
    )
    with _connection() as connection:
        dry_run = load_facility_reference_preload(
            csv_path,
            connection=connection,
            apply_changes=False,
            source_accessed_at="2026-07-01T12:00:00+00:00",
        )
        after_dry_run_count = _facility_reference_count(connection)
        first_apply = load_facility_reference_preload(
            csv_path,
            connection=connection,
            apply_changes=True,
            source_accessed_at="2026-07-01T12:00:00+00:00",
        )
        second_apply = load_facility_reference_preload(
            csv_path,
            connection=connection,
            apply_changes=True,
            source_accessed_at="2026-07-01T12:00:00+00:00",
        )
        _write_program_csv(
            csv_path,
            (
                {
                    "Facility Number": "910000001",
                    "Facility Name": "Family Home One Updated",
                    "Facility Type": "Family Child Care Home",
                    "Facility Capacity": "8",
                    "Facility Status": "Licensed",
                    "All Visit Dates": "2026-06-15; 2026-06-07; 2026-06-15",
                },
            ),
        )
        refresh = load_facility_reference_preload(
            csv_path,
            connection=connection,
            apply_changes=True,
            source_accessed_at="2026-07-01T12:00:00+00:00",
        )
        row = connection.execute(select(hosted_facility_reference_records)).mappings().one()
        null_date_columns = connection.execute(
            select(
                hosted_facility_reference_records.c.inspection_visit_dates.is_(None),
                hosted_facility_reference_records.c.other_visit_dates.is_(None),
            )
        ).one()

    assert dry_run.inserted_row_count == 1
    assert after_dry_run_count == 0
    assert first_apply.inserted_row_count == 1
    assert second_apply.unchanged_row_count == 1
    assert refresh.updated_row_count == 1
    assert row["facility_name"] == "Family Home One Updated"
    assert row["all_visit_dates"] == ["2026-06-07", "2026-06-15"]
    assert tuple(null_date_columns) == (True, True)
    assert row["original_row_json"]["Facility Name"] == "Family Home One Updated"


def test_facility_reference_source_reads_database_rows_for_lookup(tmp_path: Path) -> None:
    csv_path = tmp_path / "HomeCare06072026.csv"
    _write_program_csv(
        csv_path,
        (
            {
                "Facility Number": "920000001",
                "Facility Name": "Home Care One",
                "Facility City": "Irvine",
                "Facility State": "CA",
                "Facility Zip": "92614",
                "County Name": "Orange",
                "Facility Type": "Home Care Organization",
                "Facility Capacity": "12",
                "Facility Status": "Licensed",
            },
        ),
    )
    with _connection() as connection:
        load_facility_reference_preload(
            csv_path,
            connection=connection,
            apply_changes=True,
            source_accessed_at="2026-07-01T12:00:00+00:00",
        )
        source = facility_reference_source_from_connection(connection)

    assert source.source_kind == "postgres_facility_reference"
    assert source.path_label == FACILITY_REFERENCE_TABLE_NAME
    assert source.records[0].facility_number == "920000001"
    assert source.records[0].facility_name == "Home Care One"
    assert source.records[0].city == "Irvine"


def test_address_diagnostic_distinguishes_raw_absence_from_mapping_gap() -> None:
    with _connection() as connection:
        connection.execute(
            hosted_facility_reference_records.insert(),
            (
                _diagnostic_reference_row(
                    facility_number="347006659",
                    facility_name="REFUGE SUNSET",
                    address=None,
                    city=None,
                    state=None,
                    zip_code=None,
                    original_row_json={
                        "FAC_NBR": "347006659",
                        "NAME": "REFUGE SUNSET",
                        "STATUS": "3",
                        "COUNTY": "SACRAMENTO",
                    },
                ),
                _diagnostic_reference_row(
                    facility_number="900000111",
                    facility_name="MAPPED GAP HOUSE",
                    address=None,
                    city=None,
                    state=None,
                    zip_code=None,
                    original_row_json={
                        "FAC_NBR": "900000111",
                        "NAME": "MAPPED GAP HOUSE",
                        "RES_STREET_ADDR": "10 SOURCE WAY",
                        "RES_CITY": "SOURCE CITY",
                        "RES_STATE": "CA",
                        "RES_ZIP_CODE": "90001",
                    },
                ),
            ),
        )

        refuge = diagnose_facility_reference_address(connection, "347006659")
        mapped_gap = diagnose_facility_reference_address(connection, "900000111")

    assert len(refuge) == 1
    assert refuge[0].facility_name == "REFUGE SUNSET"
    assert refuge[0].source_resource_name == "24-Hour Residential Care for Children"
    assert refuge[0].source_file_name == "ChildrenResidential.csv"
    assert refuge[0].normalized_address_fields == {
        "address": None,
        "city": None,
        "state": None,
        "zip": None,
        "county": "SACRAMENTO",
        "regional_office": None,
    }
    assert refuge[0].raw_address_fields == {"COUNTY": "SACRAMENTO"}
    assert refuge[0].conclusion == "source_missing_address"

    assert mapped_gap[0].raw_address_fields == {
        "RES_CITY": "SOURCE CITY",
        "RES_STATE": "CA",
        "RES_STREET_ADDR": "10 SOURCE WAY",
        "RES_ZIP_CODE": "90001",
    }
    assert mapped_gap[0].conclusion == "normalization_gap"


def test_postgres_facility_lookup_route_prefers_preloaded_reference_rows(
    tmp_path: Path,
) -> None:
    csv_path = tmp_path / "FosterFamilyAgencies06072026.csv"
    _write_program_csv(
        csv_path,
        (
            {
                "Facility Number": "930000001",
                "Facility Name": "Preloaded Foster Agency",
                "Facility City": "Sacramento",
                "Facility State": "CA",
                "Facility Zip": "95814",
                "County Name": "Sacramento",
                "Facility Type": "Foster Family Agency",
                "Facility Capacity": "40",
                "Facility Status": "Licensed",
            },
        ),
    )
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)
    hosted_facility_reference_metadata.create_all(engine)
    with engine.begin() as connection:
        load_facility_reference_preload(
            csv_path,
            connection=connection,
            apply_changes=True,
            source_accessed_at="2026-07-01T12:00:00+00:00",
        )
    with engine.connect() as connection:
        context = ccld_record_request_context_for_reviewer_context(
            reviewer_ui_context_for_connection(connection)
        )
        status, content_type, body = route_response(
            f"{CCLD_FACILITY_LOOKUP_PATH}?q=foster",
            auth_runtime_config=load_hosted_auth_runtime_config(
                environ={
                    "CCLD_HOSTED_TESTER_AUTH_MODE": "local-dev",
                    "CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH": "enabled",
                }
            ),
            page_data_mode="postgres",
            ccld_record_request_ui_context=context,
        )

    html = body.decode("utf-8")
    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Preloaded Foster Agency" in html
    assert "930000001" in html
    assert "Synthetic Orchard Child Care" not in html


def test_preload_cli_defaults_to_dry_run_and_apply_is_only_write_mode() -> None:
    cli = _load_preload_cli_module()
    parser = cli.build_parser()

    default_args = parser.parse_args([])
    dry_run_args = parser.parse_args(["-DryRun"])
    apply_args = parser.parse_args(["-Apply"])

    assert cli.apply_changes_from_args(default_args) is False
    assert cli.apply_changes_from_args(dry_run_args) is False
    assert cli.apply_changes_from_args(apply_args) is True


def test_preload_cli_missing_database_url_has_controlled_message(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env.pop("CCLD_HOSTED_TESTER_DATABASE_URL", None)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/load_facility_reference_preload.py",
            "--input-path",
            str(tmp_path),
            "-DryRun",
        ],
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 2
    assert "Facility reference preload requires CCLD_HOSTED_TESTER_DATABASE_URL" in (
        completed.stderr
    )
    assert "Dry-run mode also needs the database" in completed.stderr
    assert "inserted, updated, and unchanged counts" in completed.stderr
    assert "Traceback" not in completed.stderr


def test_powershell_preload_rejects_apply_and_dry_run_together(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    powershell_executable = shutil.which("pwsh") or shutil.which("powershell")
    if powershell_executable is None:
        pytest.skip("PowerShell executable is not available on this runner.")

    completed = subprocess.run(
        [
            powershell_executable,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "scripts/load-facility-reference-preload.ps1",
            "-InputPath",
            str(tmp_path),
            "-Apply",
            "-DryRun",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )

    combined_output = f"{completed.stdout}\n{completed.stderr}"
    assert completed.returncode != 0
    assert "Use either -Apply or -DryRun, not both" in combined_output
    assert "Traceback" not in combined_output


def _connection() -> Connection:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_facility_reference_metadata.create_all(engine)
    return engine.connect()


def _facility_reference_count(connection: Connection) -> int:
    return connection.execute(
        select(func.count()).select_from(hosted_facility_reference_records)
    ).scalar_one()


def _write_program_csv(path: Path, rows: tuple[dict[str, str], ...]) -> None:
    _write_csv(path, _program_fieldnames(), rows)


def _program_fieldnames() -> tuple[str, ...]:
    return (
        "Facility Type",
        "Facility Number",
        "Facility Name",
        "Program Type",
        "Licensee",
        "Facility Administrator",
        "Facility Telephone Number",
        "Facility Address",
        "Facility City",
        "Facility State",
        "Facility Zip",
        "County Name",
        "Regional Office",
        "Facility Capacity",
        "Facility Status",
        "License First Date",
        "Closed Date",
        "All Visit Dates",
        "Inspection Visit Dates",
        "Other Visit Dates",
        "Complaint Info- Date, #Sub Aleg, # Inc Aleg, # Uns Aleg, # TypeA, # TypeB ...",
    )


def _write_program_csv_with_overflow(
    path: Path,
    row: dict[str, str],
    overflow_values: tuple[str, ...],
) -> None:
    fieldnames = _program_fieldnames()
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(fieldnames)
        writer.writerow(
            [row.get(fieldname, "") for fieldname in fieldnames] + list(overflow_values)
        )


def _write_master_csv(path: Path, rows: tuple[dict[str, str], ...]) -> None:
    fieldnames = (
        "FAC_NBR",
        "NAME",
        "TYPE",
        "PROGRAM_TYPE",
        "STATUS",
        "CLIENT_SERVED",
        "CAPACITY",
        "RES_STREET_ADDR",
        "RES_CITY",
        "RES_STATE",
        "RES_ZIP_CODE",
        "COUNTY",
        "FAC_DO_DESC",
        "FAC_TYPE_DESC",
        "FAC_PHONE_NBR",
    )
    _write_csv(path, fieldnames, rows)


def _write_csv(
    path: Path,
    fieldnames: tuple[str, ...],
    rows: tuple[dict[str, str], ...],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _diagnostic_reference_row(
    *,
    facility_number: str,
    facility_name: str,
    address: str | None,
    city: str | None,
    state: str | None,
    zip_code: str | None,
    original_row_json: dict[str, str],
) -> dict[str, Any]:
    return {
        "source_resource_id": f"diagnostic-{facility_number}",
        "facility_number": facility_number,
        "facility_name": facility_name,
        "facility_type": "SHORT TERM RESIDENTIAL THERAPEUTIC PROGRAM",
        "program_type": "CHILDREN'S RESIDENTIAL",
        "licensee_name": None,
        "facility_administrator": None,
        "telephone": None,
        "address": address,
        "city": city,
        "state": state,
        "zip": zip_code,
        "county": "SACRAMENTO",
        "regional_office": None,
        "capacity": 6,
        "status": "3",
        "license_first_date": None,
        "closed_date": None,
        "snapshot_date": "2026-06-07",
        "source_resource_name": "24-Hour Residential Care for Children",
        "source_dataset_slug": "ccl-facilities",
        "source_dataset_url": "public-ccl-facilities",
        "source_accessed_at": "2026-07-01T12:00:00+00:00",
        "source_file_name": "ChildrenResidential.csv",
        "original_row_json": original_row_json,
    }


def _load_preload_cli_module() -> Any:
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "load_facility_reference_preload.py"
    spec = importlib.util.spec_from_file_location(
        "load_facility_reference_preload_cli",
        script_path,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Could not load facility reference preload CLI module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_value_lookup_ignores_extra_csv_fields_without_headers() -> None:
    row = {
        None: ["unexpected", "extra", "values"],
        "FAC_NBR": " 123456789 ",
    }

    assert preload_module._value(row, "FAC_NBR") == "123456789"
