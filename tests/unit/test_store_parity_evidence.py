from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, cast

from sqlalchemy import create_engine, text

from ccld_complaints import store_parity_evidence as evidence_module
from ccld_complaints.store_parity_evidence import OUTPUT_FILES, run_evidence

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_local_evidence_proves_equivalent_governed_store_parity(tmp_path: Path) -> None:
    output_dir = tmp_path / "local-evidence"

    manifest = run_evidence(
        mode="local",
        output_dir=output_dir,
        repo_root=REPO_ROOT,
    )

    assertions = cast(dict[str, bool], manifest["assertions"])
    assert len(assertions) == 19
    assert all(assertions.values())
    assert set(path.name for path in output_dir.iterdir()) == set(OUTPUT_FILES)

    execution = cast(dict[str, object], manifest["execution"])
    assert execution["sqlite"] == "actual temporary SQLite execution"
    assert "temporary SQLite adapter" in str(execution["postgresql_style"])
    assert execution["actual_disposable_postgresql"] is False
    assert execution["production_runtime_inspection"] == "not requested in local mode"

    store_rows = _csv_rows(output_dir / "store-results.csv")
    canonical_rows = [row for row in store_rows if row["dimension"] != "facility_reference"]
    assert {row["dimension"] for row in canonical_rows} == {
        "facility",
        "source_document",
        "complaint",
        "allegation",
        "event",
        "extraction_audit",
    }
    assert all(row["sqlite_count"] == row["postgresql_style_count"] for row in canonical_rows)
    assert all(row["assertion_status"] == "PASS" for row in store_rows)

    field_rows = _csv_rows(output_dir / "field-parity-results.csv")
    fields = {row["field_id"] for row in field_rows}
    assert {
        "facility.capacity",
        "facility.county",
        "facility.facility_type",
        "facility.regional_office",
        "facility.status",
        "complaint.days_received_to_first_activity",
        "source_document.raw_sha256",
        "event.event_date",
        "facility_reference.all_visit_dates",
        "facility_reference.inspection_visit_dates",
        "facility_reference.other_visit_dates",
        "facility_reference.client_served",
        "facility_reference.closed_date",
    }.issubset(fields)
    assert all(row["assertion_status"] == "PASS" for row in field_rows)


def test_null_idempotency_refresh_and_gap_evidence_are_explicit(tmp_path: Path) -> None:
    output_dir = tmp_path / "semantics-evidence"
    manifest = run_evidence(mode="local", output_dir=output_dir, repo_root=REPO_ROOT)

    null_rows = {
        row["semantic_case"]: row
        for row in _csv_rows(output_dir / "null-semantics-results.csv")
    }
    assert {
        "explicit_numeric_zero",
        "canonical_null",
        "present_but_blank_audit",
        "source_unavailable_audit",
        "facility_reference_null",
        "facility_reference_blank_raw_provenance",
    } == set(null_rows)
    assert all(int(row["sqlite_count"]) > 0 for row in null_rows.values())
    assert all(row["sqlite_count"] == row["postgresql_style_count"] for row in null_rows.values())
    assert all(row["assertion_status"] == "PASS" for row in null_rows.values())

    idempotency_rows = _csv_rows(output_dir / "idempotency-results.csv")
    assert {row["check_id"] for row in idempotency_rows} == {
        "canonical_reimport",
        "facility_reference_preload",
    }
    assert all(row["first_count"] == row["second_count"] for row in idempotency_rows)
    assert all(row["duplicate_rows_after_second_run"] == "0" for row in idempotency_rows)
    canonical = next(row for row in idempotency_rows if row["check_id"] == "canonical_reimport")
    assert canonical["reviewer_state_rows_before"] == "1"
    assert canonical["reviewer_state_rows_after"] == "1"

    refresh = cast(dict[str, object], manifest["refresh_readiness"])
    assert refresh == {
        "safe_refresh_command_available": False,
        "existing_postgresql_rows_require_regeneration_or_reimport": True,
        "facility_reference_rows_require_migration_and_preload_rerun": True,
    }
    refresh_rows = _csv_rows(output_dir / "refresh-readiness-results.csv")
    assert all(row["safe_command_available"].startswith("false") for row in refresh_rows)
    assert all(row["missing_controls"] for row in refresh_rows)
    assert all(row["assertion_status"] == "PASS" for row in refresh_rows)

    gaps = {row["gap_id"]: row for row in _csv_rows(output_dir / "gap-status.csv")}
    assert gaps["store_parity_divergence"]["status"] == "CLOSED"
    assert gaps["existing_postgresql_rows"]["status"] == "OPEN"
    assert gaps["safe_refresh_command"]["status"] == "OPEN"


def test_evidence_is_aggregate_safe_and_excludes_record_identifiers(tmp_path: Path) -> None:
    output_dir = tmp_path / "safe-evidence"
    run_evidence(mode="local", output_dir=output_dir, repo_root=REPO_ROOT)

    combined = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(output_dir.iterdir())
    )
    lowered = combined.casefold()
    assert str(REPO_ROOT).casefold() not in lowered
    assert "900000001" not in combined
    assert "900000002" not in combined
    assert "32-CR-" not in combined
    assert "6088c962" not in combined
    assert "investigation findings" not in lowered
    assert "postgresql://" not in lowered
    assert "sqlite://" not in lowered


def test_runtime_mode_without_configuration_reports_no_inspection(tmp_path: Path) -> None:
    output_dir = tmp_path / "runtime-evidence"

    manifest = run_evidence(
        mode="runtime",
        output_dir=output_dir,
        repo_root=REPO_ROOT,
        environ={},
    )

    runtime = cast(dict[str, object], manifest["runtime_inspection"])
    assertions = cast(dict[str, bool], manifest["assertions"])
    assert runtime == {
        "status": "not inspected: PostgreSQL runtime configuration is unavailable",
        "actual_postgresql_connection": False,
        "schema_status": "not inspected",
        "source_derived_count": None,
        "facility_reference_count": None,
    }
    assert all(assertions.values())
    assert "actual PostgreSQL aggregate-only inspection completed" not in (
        output_dir / "summary.md"
    ).read_text(encoding="utf-8")


def test_schema_version_mismatch_is_detected_before_runtime_counts() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE alembic_version (version_num TEXT NOT NULL)"))
            connection.execute(
                text("INSERT INTO alembic_version (version_num) VALUES ('older-revision')")
            )
            assert evidence_module._schema_version_status(connection) == "mismatch"
            inspection = evidence_module._inspect_runtime_connection(connection)
    finally:
        engine.dispose()

    assert inspection.actual_postgresql_connection is False
    assert inspection.schema_status == "mismatch"
    assert inspection.source_derived_count is None
    assert inspection.facility_reference_count is None


def test_confirmed_field_divergence_is_not_masked(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    original = evidence_module._field_parity_rows

    def mismatch_one_field(*args: Any, **kwargs: Any) -> list[dict[str, object]]:
        rows = original(*args, **kwargs)
        rows[0] = {
            **rows[0],
            "value_match_status": "mismatch",
            "assertion_status": "FAIL",
        }
        return rows

    monkeypatch.setattr(evidence_module, "_field_parity_rows", mismatch_one_field)
    output_dir = tmp_path / "mismatch-evidence"

    manifest = run_evidence(mode="local", output_dir=output_dir, repo_root=REPO_ROOT)

    assertions = cast(dict[str, bool], manifest["assertions"])
    assert manifest["confirmed_divergence_count"] == 1
    assert assertions["canonical_field_presence_matches"] is False
    assert assertions["no_confirmed_store_divergence"] is False
    gap = next(
        row
        for row in _csv_rows(output_dir / "gap-status.csv")
        if row["gap_id"] == "store_parity_divergence"
    )
    assert gap["status"] == "FAIL"
    assert gap["assertion_status"] == "FAIL"


def test_postgresql_statements_and_table_ddl_compile() -> None:
    result = evidence_module._postgresql_sql_capability()

    assert result == {"compiled": True, "statement_count": 8}


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as csv_file:
        return list(csv.DictReader(csv_file))
