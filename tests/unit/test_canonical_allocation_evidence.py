from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

import pytest
from sqlalchemy import create_engine, text

from ccld_complaints import canonical_allocation_evidence as evidence_module
from ccld_complaints.canonical_allocation_evidence import (
    ALLOCATION_SPECS,
    COMPOSITE_SOURCE_HEADER,
    FIELD_IDS,
    OUTPUT_FILES,
    EvidenceExecutionError,
    run_evidence,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_FIELDS = (
    "complaint.agency_name",
    "complaint.deficiency_texts",
    "complaint.investigation_findings_narrative",
    "complaint.complaint_report_contact",
    "complaint.days_received_to_first_activity",
    "facility.capacity",
    "facility.county",
    "facility.facility_type",
    "facility.regional_office",
    "facility.status",
    "ccld_program_facility.all_visit_dates",
    ("ccld_program_facility.complaint_info_date_sub_aleg_inc_aleg_uns_aleg_typea_typeb"),
    "ccld_program_facility.inspection_visit_dates",
    "ccld_program_facility.other_visit_dates",
    "chhs_facility_master.client_served",
    "facility_reference.closed_date",
)


def test_registry_has_exact_issue_447_fields_and_deliberate_allocations() -> None:
    assert FIELD_IDS == EXPECTED_FIELDS
    assert tuple(spec.field_id for spec in ALLOCATION_SPECS) == EXPECTED_FIELDS
    assert Counter(spec.allocation_decision for spec in ALLOCATION_SPECS) == {
        "existing_canonical": 10,
        "typed_source_reference": 5,
        "retained_raw_only": 1,
    }
    composite = next(
        spec for spec in ALLOCATION_SPECS if spec.allocation_decision == "retained_raw_only"
    )
    assert composite.source_element == COMPOSITE_SOURCE_HEADER
    assert composite.canonical_destination.endswith("original_row_json")
    assert OUTPUT_FILES == (
        "manifest.json",
        "allocation-results.csv",
        "import-results.csv",
        "null-semantics-results.csv",
        "migration-results.csv",
        "gap-status.csv",
        "summary.md",
    )


def test_local_evidence_is_deterministic_complete_and_aggregate_safe(
    tmp_path: Path,
) -> None:
    first_output = tmp_path / "first"
    second_output = tmp_path / "second"

    first_manifest = run_evidence(
        mode="local",
        output_dir=first_output,
        repo_root=REPO_ROOT,
    )
    second_manifest = run_evidence(
        mode="local",
        output_dir=second_output,
        repo_root=REPO_ROOT,
    )

    first_assertions = cast(dict[str, bool], first_manifest["assertions"])
    assert len(first_assertions) == 13
    assert all(first_assertions.values())
    assert first_assertions["no_synthetic_facility_ids_emitted"] is True
    assert first_manifest["counts"] == second_manifest["counts"]
    assert first_manifest == second_manifest
    assert {path.name for path in first_output.iterdir()} == set(OUTPUT_FILES)
    for file_name in OUTPUT_FILES:
        assert (first_output / file_name).read_bytes() == (second_output / file_name).read_bytes()

    combined_output = "\n".join(
        (first_output / file_name).read_text(encoding="utf-8") for file_name in OUTPUT_FILES
    )
    assert str(REPO_ROOT) not in combined_output
    assert str(REPO_ROOT).replace("\\", "/") not in combined_output
    assert "During the course of the investigation" not in combined_output
    assert "http://" not in combined_output
    assert "https://" not in combined_output
    assert "postgresql://" not in combined_output
    assert "sqlite://" not in combined_output
    assert "900000001" not in combined_output
    assert "900000002" not in combined_output

    allocation_rows = _csv_rows(first_output / "allocation-results.csv")
    implementation_rows = [
        row
        for row in _csv_rows(first_output / "import-results.csv")
        if row["evidence_scope"] == "implementation_capability"
    ]
    null_rows = _csv_rows(first_output / "null-semantics-results.csv")
    migration_rows = _csv_rows(first_output / "migration-results.csv")
    gap_rows = _csv_rows(first_output / "gap-status.csv")

    assert [row["field_id"] for row in allocation_rows] == list(EXPECTED_FIELDS)
    assert [row["field_id"] for row in implementation_rows] == list(EXPECTED_FIELDS)
    assert [row["field_id"] for row in null_rows] == list(EXPECTED_FIELDS)
    assert [row["field_id"] for row in gap_rows] == list(EXPECTED_FIELDS)
    assert all(row["assertion_status"] == "PASS" for row in allocation_rows)
    assert all(row["assertion_status"] == "PASS" for row in implementation_rows)
    assert all(row["assertion_status"] == "PASS" for row in null_rows)
    assert all(row["assertion_status"] == "PASS" for row in migration_rows)
    implementation_by_field = {row["field_id"]: row for row in implementation_rows}
    for field_id in (
        "facility.county",
        "facility.facility_type",
        "facility.status",
    ):
        row = implementation_by_field[field_id]
        assert row["populated_count"] != "0"
        assert "temporary seeded artifact" in row["adapter"]
        assert "exact source-to-canonical comparison" in row["evidence_reference"]

    migration_by_check = {row["check_id"]: row for row in migration_rows}
    alembic_row = migration_by_check["facility_reference_alembic_20260714_0007"]
    assert alembic_row["existing_row_count_before"] == "1"
    assert alembic_row["existing_row_count_after"] == "1"
    assert alembic_row["existing_rows_readable"] == "true"
    assert "executed Alembic revision 20260714_0007" in alembic_row["evidence_reference"]
    complaint_alembic_row = migration_by_check[
        "complaint_observations_alembic_20260723_0013"
    ]
    assert complaint_alembic_row["existing_row_count_before"] == "1"
    assert complaint_alembic_row["existing_row_count_after"] == "1"
    assert complaint_alembic_row["existing_rows_readable"] == "true"
    assert "upgrade, downgrade, and re-upgrade" in complaint_alembic_row[
        "evidence_reference"
    ]
    capability = cast(dict[str, object], first_manifest["implementation_capability"])
    assert capability["facility_fixture_temporary_hosted_import"] == (
        "exercised with exact canonical-value comparison"
    )
    runtime = cast(dict[str, object], first_manifest["runtime_population"])
    assert runtime["status"] == "not inspected in local mode"
    assert (
        cast(dict[str, object], runtime["hosted_source_derived"])["status"]
        == "not inspected in local mode"
    )
    assert (
        cast(dict[str, object], runtime["facility_reference"])["status"]
        == "not inspected in local mode"
    )


def test_runtime_reports_hosted_and_reference_population_separately(
    tmp_path: Path,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE hosted_source_derived_records (
                    entity_type TEXT NOT NULL,
                    original_values TEXT NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO hosted_source_derived_records
                    (entity_type, original_values)
                VALUES
                    ('complaint', :complaint),
                    ('facility', :facility)
                """
            ),
            {
                "complaint": json.dumps({"days_received_to_first_activity": 7}),
                "facility": json.dumps(
                    {
                        "capacity": 48,
                        "county": "Example County",
                        "facility_type": "Example Type",
                        "regional_office": "Example Office",
                        "status": "Active",
                    }
                ),
            },
        )
        connection.execute(
            text(
                """
                CREATE TABLE hosted_facility_reference_records (
                    capacity INTEGER,
                    county TEXT,
                    facility_type TEXT,
                    regional_office TEXT,
                    status TEXT,
                    client_served TEXT,
                    closed_date TEXT,
                    all_visit_dates TEXT,
                    inspection_visit_dates TEXT,
                    other_visit_dates TEXT,
                    original_row_json TEXT NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO hosted_facility_reference_records (
                    capacity,
                    county,
                    facility_type,
                    regional_office,
                    status,
                    client_served,
                    closed_date,
                    all_visit_dates,
                    inspection_visit_dates,
                    other_visit_dates,
                    original_row_json
                )
                VALUES (
                    48,
                    'Example County',
                    'Example Type',
                    'Example Office',
                    'Active',
                    'Example Population',
                    '2024-01-31',
                    :all_dates,
                    :inspection_dates,
                    :other_dates,
                    :original_row
                )
                """
            ),
            {
                "all_dates": json.dumps(["2024-01-01", "2024-01-15"]),
                "inspection_dates": json.dumps(["2024-01-01"]),
                "other_dates": json.dumps(["2024-01-15"]),
                "original_row": json.dumps({COMPOSITE_SOURCE_HEADER: "retained composite source"}),
            },
        )

        manifest = run_evidence(
            mode="runtime",
            output_dir=tmp_path / "runtime",
            repo_root=REPO_ROOT,
            runtime_connection=connection,
        )

    assertions = cast(dict[str, bool], manifest["assertions"])
    assert len(assertions) == 13
    assert all(assertions.values())
    runtime = cast(dict[str, object], manifest["runtime_population"])
    source = cast(dict[str, object], runtime["hosted_source_derived"])
    reference = cast(dict[str, object], runtime["facility_reference"])
    assert source["status"] == "inspected aggregate-only"
    assert reference["status"] == "inspected aggregate-only"
    assert source["record_count"] == 2
    assert reference["record_count"] == 1

    source_rows = {
        str(row["field_id"]): row for row in cast(list[dict[str, object]], source["fields"])
    }
    reference_rows = {
        str(row["field_id"]): row for row in cast(list[dict[str, object]], reference["fields"])
    }
    assert source_rows["complaint.days_received_to_first_activity"]["populated_count"] == 1
    assert source_rows["facility.capacity"]["populated_count"] == 1
    assert reference_rows["chhs_facility_master.client_served"]["populated_count"] == 1
    assert reference_rows["ccld_program_facility.all_visit_dates"]["populated_count"] == 1
    assert (
        reference_rows[
            ("ccld_program_facility.complaint_info_date_sub_aleg_inc_aleg_uns_aleg_typea_typeb")
        ]["populated_count"]
        == 1
    )

    runtime_import_rows = [
        row
        for row in _csv_rows(tmp_path / "runtime/import-results.csv")
        if row["evidence_scope"] == "runtime_population"
    ]
    assert {row["adapter"] for row in runtime_import_rows} == {
        "hosted_source_derived_records",
        "hosted_facility_reference_records",
    }
    assert all(row["assertion_status"] == "PASS" for row in runtime_import_rows)


def test_canonical_population_assertion_fails_on_exact_import_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exact_match = evidence_module._canonical_hosted_import_matches

    def mismatch_one_canonical_field(
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, bool]:
        matches = exact_match(*args, **kwargs)
        matches["facility.status"] = False
        return matches

    monkeypatch.setattr(
        evidence_module,
        "_canonical_hosted_import_matches",
        mismatch_one_canonical_field,
    )

    manifest = run_evidence(
        mode="local",
        output_dir=tmp_path / "mismatch",
        repo_root=REPO_ROOT,
    )

    assertions = cast(dict[str, bool], manifest["assertions"])
    assert assertions["governed_values_populate_canonical_destinations"] is False
    assert assertions["canonical_allocations_have_importer_or_initializer_coverage"] is False


def test_runtime_without_postgresql_never_writes_or_falls_back(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "runtime"

    with pytest.raises(
        EvidenceExecutionError,
        match="Runtime evidence requires a configured PostgreSQL database",
    ):
        run_evidence(
            mode="runtime",
            output_dir=output_dir,
            repo_root=REPO_ROOT,
            environ={},
        )

    assert not output_dir.exists()


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as csv_file:
        return list(csv.DictReader(csv_file))
