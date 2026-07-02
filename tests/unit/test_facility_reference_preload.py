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
                "Closed Date": "",
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
    assert record.capacity == 24
    assert record.license_first_date == "2020-06-07"
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
    assert record.facility_type == "DAY CARE CENTER"
    assert record.regional_office == "North Bay"
    assert record.capacity == 24
    assert result.warnings == ()


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

    assert dry_run.inserted_row_count == 1
    assert after_dry_run_count == 0
    assert first_apply.inserted_row_count == 1
    assert second_apply.unchanged_row_count == 1
    assert refresh.updated_row_count == 1
    assert row["facility_name"] == "Family Home One Updated"
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
    fieldnames = (
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
    )
    _write_csv(path, fieldnames, rows)


def _write_master_csv(path: Path, rows: tuple[dict[str, str], ...]) -> None:
    fieldnames = (
        "FAC_NBR",
        "NAME",
        "PROGRAM_TYPE",
        "STATUS",
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

