from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event, func, select

from ccld_complaints.connectors.ccld_transparency_api.contract import (
    OBSERVATION_KIND,
    SNAPSHOT_SCOPE,
    SOURCE_FAMILY_ID,
    normalized_observation,
)
from ccld_complaints.connectors.ccld_transparency_api.lifecycle import (
    transparency_quarantines,
    transparency_rows,
)
from ccld_complaints.hosted_app.facility_identity_projection import (
    FacilityProjectionField,
    FacilitySourceKind,
    facility_projection_candidate_from_values,
    project_facility_identity,
)
from ccld_complaints.hosted_app.source_snapshot_lifecycle import (
    source_snapshot_metadata,
    source_snapshot_pointers,
    source_snapshots,
)
from ccld_complaints.source_to_screen_audit import (
    AuditResult,
    build_runtime_coverage_input,
    generate_coverage_package,
    load_coverage_fixture_scenario,
)
from ccld_complaints.source_to_screen_facility_coverage import (
    FACILITY_COVERAGE_FAILURE_CATEGORIES,
    FACILITY_COVERAGE_METRICS,
    FACILITY_COVERAGE_STAGE_STATES,
    aggregate_projection_conflict_counts,
    build_runtime_facility_coverage,
    governed_fixture_facility_coverage,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = Path("tests/fixtures/source_to_screen_coverage/scenarios.json")
FIXED_TIME = datetime(2026, 7, 21, 18, 0, 0, tzinfo=UTC)
SNAPSHOT_ID = "transparencyapi-accepted-fictional-v1"


def test_runtime_facility_coverage_is_aggregate_only_select_only_and_reconciled() -> None:
    engine = create_engine("sqlite://")
    statements: list[str] = []
    with engine.connect() as connection:
        _seed_active_transparency_snapshot(connection)
        before = _table_counts(connection)

        def record_statement(
            _connection: Any,
            _cursor: Any,
            statement: str,
            _parameters: Any,
            _context: Any,
            _executemany: bool,
        ) -> None:
            statements.append(statement)

        event.listen(engine, "before_cursor_execute", record_statement)
        coverage = build_runtime_facility_coverage(connection)
        event.remove(engine, "before_cursor_execute", record_statement)
        after = _table_counts(connection)

    assert before == after
    assert statements
    assert all(
        statement.lstrip().upper().startswith(("SELECT", "WITH", "PRAGMA"))
        for statement in statements
    )
    assert coverage["availability"] == "available"
    assert coverage["snapshot"] == {
        "source_snapshot_id": SNAPSHOT_ID,
        "selection_state": "active_accepted",
        "schema_fingerprint": "a" * 64,
        "content_fingerprint": "b" * 64,
        "eligible_facility_count": 2,
    }
    metrics = {
        row["metric_id"]: row
        for row in coverage["aggregate_metrics"]
    }
    assert set(metrics) == set(FACILITY_COVERAGE_METRICS)
    assert metrics["eligible-facility-total"]["count"] == 2
    assert metrics["leading-zero-facility-number-total"]["count"] == 1
    assert metrics["blank-id-quarantine-total"]["count"] == 1
    assert metrics["duplicate-id-quarantine-total"]["count"] == 1
    assert metrics["malformed-complaint-block-quarantine-total"]["count"] == 1
    assert metrics["unknown-type-code-quarantine-total"]["count"] == 1
    assert metrics["type-777-row-total"] == {
        "metric_id": "type-777-row-total",
        "count": 0,
        "status": "valid-zero",
    }
    assert metrics["raw-733-unresolved-total"]["count"] == 1
    assert metrics["placeholder-overwrite-prevented-total"]["count"] == 1
    assert metrics["contact-populated-total"]["status"] == "unavailable"
    assert metrics["detail-status-populated-total"]["status"] == "unavailable"
    assert metrics["current-complaint-context-conflation-total"]["count"] == 0
    assert metrics["unsafe-report-url-exposure-total"]["count"] == 0
    assert metrics["reviewer-state-mutation-total"]["count"] == 0
    assert set(coverage["failure_category_counts"]) == set(
        FACILITY_COVERAGE_FAILURE_CATEGORIES
    )
    for row in coverage["field_stage_coverage"]:
        assert row["eligible_count"] == sum(
            row[f"{state}_count"] for state in FACILITY_COVERAGE_STAGE_STATES
        )

    serialized = json.dumps(coverage, sort_keys=True).casefold()
    for prohibited in (
        "fictional leading zero home",
        "a. miriam jamison children’s center",
        "fictional unresolved type home",
        "001234567",
        "733000001",
        "101 fictional avenue",
        "555-0100",
        "facility clients are being mistreated",
        "fakeout.gov",
        "reportpage",
        "c:\\users\\",
        "authorization",
        "cookie",
    ):
        assert prohibited not in serialized


def test_runtime_release_uses_prior_aggregate_baseline_and_database_reconciliation() -> None:
    engine = create_engine("sqlite://")
    previous = json.loads(json.dumps(governed_fixture_facility_coverage("complete")))
    for metric in previous["aggregate_metrics"]:
        if metric["metric_id"] == "eligible-facility-total":
            metric["count"] = 3
    with engine.connect() as connection:
        _seed_active_transparency_snapshot(connection)
        connection.execute(
            source_snapshots.update()
            .where(source_snapshots.c.snapshot_id == SNAPSHOT_ID)
            .values(stored_row_count=4)
        )
        connection.commit()
        coverage = build_runtime_facility_coverage(connection, previous=previous)

    checks = {
        row["criterion_id"]: row
        for row in coverage["release_assessment"]["checks"]
    }
    assert checks["facility-count-decline"]["baseline_count"] == 3
    assert checks["facility-count-decline"]["observed_count"] == 1
    assert checks["facility-count-decline"]["status"] == "failed"
    assert checks["postgresql-eligibility-mismatch"]["observed_count"] == 1
    assert checks["postgresql-eligibility-mismatch"]["status"] == "failed"


def test_projection_conflicts_keep_current_supplementary_and_historical_contexts_distinct() -> None:
    facility_id = "001234567"
    candidates = tuple(
        facility_projection_candidate_from_values(
            {"facility_number": facility_id, "facility_name": name},
            source_kind=source_kind,
            source_row_identity=f"row-{index}",
            snapshot_identity=f"snapshot-{index}",
            observed_at=f"2026-07-{index + 1:02d}T00:00:00Z",
        )
        for index, (source_kind, name) in enumerate(
            (
                (FacilitySourceKind.TRANSPARENCY_API_CURRENT, "Current name"),
                (FacilitySourceKind.ARCGIS_SUPPLEMENT, "Supplementary name"),
                (FacilitySourceKind.PROGRAM_REFERENCE, "Historical program name"),
                (FacilitySourceKind.COMPLAINT_LINKED_FACILITY, "Complaint-time name"),
            )
        )
    )
    projection = project_facility_identity(facility_id, candidates)

    assert projection.field(FacilityProjectionField.FACILITY_NAME).display_value == (
        "Current name"
    )
    assert aggregate_projection_conflict_counts({facility_id: projection}) == {
        "arcgis-supplementary": 1,
        "historical-complaint": 1,
        "historical-program": 1,
    }


def test_runtime_facility_coverage_reports_source_unavailable_without_zero_claim() -> None:
    engine = create_engine("sqlite://")
    with engine.connect() as connection:
        coverage = build_runtime_facility_coverage(connection)

    assert coverage["availability"] == "unavailable"
    assert coverage["reason_category"] == "read-boundary-unavailable"
    assert all(
        row["status"] == "unavailable" for row in coverage["aggregate_metrics"]
    )
    assert coverage["release_assessment"]["status"] == "warning"


def test_runtime_package_declares_active_snapshot_and_is_byte_deterministic(
    tmp_path: Path,
) -> None:
    engine = create_engine("sqlite://")
    empty_audit = AuditResult({}, (), (), (), (), (), (), (), (), ())
    with engine.connect() as connection:
        _seed_active_transparency_snapshot(connection)
        fixture = build_runtime_coverage_input(
            connection,
            empty_audit,
            repo_root=REPO_ROOT,
        )
        first = generate_coverage_package(
            fixture,
            output_dir=tmp_path / "first",
            repo_root=REPO_ROOT,
            generated_at=FIXED_TIME,
        )
        second = generate_coverage_package(
            fixture,
            output_dir=tmp_path / "second",
            repo_root=REPO_ROOT,
            generated_at=FIXED_TIME,
        )

    assert first == second
    first_bytes = _tree_bytes(tmp_path / "first")
    assert first_bytes == _tree_bytes(tmp_path / "second")
    serialized = b"".join(first_bytes.values()).decode("utf-8").casefold()
    assert str(REPO_ROOT).casefold() not in serialized
    assert str(tmp_path).casefold() not in serialized
    assert "c:\\users\\" not in serialized
    snapshots = {row["source_family_id"]: row for row in first.manifest["source_snapshots"]}
    assert snapshots[SOURCE_FAMILY_ID]["source_snapshot_id"] == SNAPSHOT_ID
    assert snapshots[SOURCE_FAMILY_ID]["selection_state"] == "active_accepted"
    assert first.report["coverage"]["facility_reference"]["snapshot"][
        "eligible_facility_count"
    ] == 2


def test_fixture_release_thresholds_fail_for_rendering_and_stage_imbalance(
    tmp_path: Path,
) -> None:
    rendered = _generate_scenario(tmp_path, "transparencyapi-read-but-not-rendered")
    imbalanced = _generate_scenario(tmp_path, "transparencyapi-stage-imbalanced")

    rendered_coverage = rendered.report["coverage"]["facility_reference"]
    imbalanced_coverage = imbalanced.report["coverage"]["facility_reference"]
    assert rendered_coverage["release_assessment"]["status"] == "failed"
    assert rendered.report["release_assessment"]["status"] == "failed"
    assert next(
        row
        for row in rendered_coverage["release_assessment"]["checks"]
        if row["criterion_id"] == "reviewer-rendering-decline"
    )["observed_count"] == 1
    assert imbalanced_coverage["release_assessment"]["status"] == "failed"
    assert imbalanced.report["release_assessment"]["status"] == "failed"
    assert next(
        row
        for row in imbalanced_coverage["release_assessment"]["checks"]
        if row["criterion_id"] == "stage-total-imbalance"
    )["observed_count"] == 1


def test_fixture_reviewed_exception_remains_explicit_and_does_not_silently_pass(
    tmp_path: Path,
) -> None:
    package = _generate_scenario(tmp_path, "transparencyapi-reviewed-exception")
    facility_release = package.report["coverage"]["facility_reference"][
        "release_assessment"
    ]

    assert package.report["release_assessment"]["status"] == (
        "reviewed_exception_required"
    )
    assert facility_release["status"] == "reviewed_exception_required"
    rendering = next(
        row
        for row in facility_release["checks"]
        if row["criterion_id"] == "reviewer-rendering-decline"
    )
    assert rendering["status"] == "reviewed_exception_required"
    assert rendering["exception_id"] == "reviewed-exception-453-v1"


def test_fixture_source_unavailable_is_partial_not_verified_zero(tmp_path: Path) -> None:
    package = _generate_scenario(tmp_path, "transparencyapi-source-unavailable")
    coverage = package.report["coverage"]["facility_reference"]

    assert package.report["package_availability"] == "partial"
    assert "facility_reference_coverage" in package.report["unavailable_dimensions"]
    assert coverage["availability"] == "unavailable"
    assert all(row["status"] == "unavailable" for row in coverage["aggregate_metrics"])


def _generate_scenario(tmp_path: Path, scenario: str) -> Any:
    return generate_coverage_package(
        load_coverage_fixture_scenario(REPO_ROOT / SCENARIOS, scenario),
        output_dir=tmp_path / scenario,
        repo_root=REPO_ROOT,
        generated_at=FIXED_TIME,
    )


def _seed_active_transparency_snapshot(connection: Any) -> None:
    source_snapshot_metadata.create_all(connection)
    connection.execute(
        source_snapshots.insert().values(
            snapshot_id=SNAPSHOT_ID,
            source_family_id=SOURCE_FAMILY_ID,
            fixture_scope=SNAPSHOT_SCOPE,
            observation_kind=OBSERVATION_KIND,
            lifecycle_state="accepted",
            manifest_ref="authority-manifest.json",
            manifest_sha256="1" * 64,
            raw_payload_ref="authority-package",
            raw_payload_sha256="2" * 64,
            normalized_content_sha256="b" * 64,
            schema_fingerprint="a" * 64,
            domain_fingerprint="3" * 64,
            row_count=3,
            stored_row_count=3,
            duplicate_object_id_count=0,
            duplicate_facility_number_count=1,
            omitted_field_count=0,
            invalid_field_count=0,
            warning_count=1,
            rejection_reason_count=0,
            validation_report={
                "all_seven_exports_present": True,
                "type_777_available": True,
            },
            recorded_at="2026-07-21T17:00:00Z",
            validated_at="2026-07-21T17:01:00Z",
            rejected_at=None,
            accepted_at="2026-07-21T17:02:00Z",
        )
    )
    connection.execute(
        source_snapshot_pointers.insert().values(
            source_family_id=SOURCE_FAMILY_ID,
            active_snapshot_id=SNAPSHOT_ID,
            prior_accepted_snapshot_id=None,
            updated_at="2026-07-21T17:02:00Z",
        )
    )
    first = _normalized_row(
        facility_number="001234567",
        facility_name="A. Miriam Jamison Children’s Center",
        facility_type="100",
        telephone="555-0100",
    )
    second = _normalized_row(
        facility_number="733000001",
        facility_name="Fictional Unresolved Type Home",
        facility_type="733",
        telephone="Unavailable",
    )
    second_resolved = dict(second)
    second_resolved["facility_telephone_number"] = {
        **normalized_observation("555-0101"),
        "preserved_from_prior": True,
        "superseding_observation": normalized_observation("Unavailable"),
    }
    connection.execute(
        transparency_rows.insert(),
        [
            _transparency_row(1, "001234567", first, first, complaint_blocks=[]),
            _transparency_row(
                2,
                "733000001",
                second,
                second_resolved,
                complaint_blocks=[
                    {
                        "ordinal": 1,
                        "raw_values": ["2026-01-01", "0", "0", "0", "0", "0"],
                        "values": {
                            "date": "2026-01-01",
                            "substantiated_allegations": "0",
                        },
                    }
                ],
            ),
            {
                **_transparency_row(3, None, first, first, complaint_blocks=[]),
                "is_quarantined": True,
            },
        ],
    )
    connection.execute(
        transparency_quarantines.insert(),
        [
            _quarantine(1, "blank_facility_number"),
            _quarantine(2, "duplicate_facility_number"),
            _quarantine(3, "malformed_trailing_complaint_block"),
            _quarantine(4, "unknown_facility_type_code"),
        ],
    )
    connection.commit()


def _normalized_row(
    *, facility_number: str, facility_name: str, facility_type: str, telephone: str
) -> dict[str, Any]:
    values = {
        "facility_number": facility_number,
        "facility_name": facility_name,
        "facility_type": facility_type,
        "licensee": "Fictional Licensee",
        "facility_administrator": "Fictional Administrator",
        "facility_telephone_number": telephone,
        "facility_address": "101 Fictional Avenue",
        "facility_city": "Example City",
        "facility_state": "CA",
        "facility_zip": "90000",
        "county_name": "Example County",
        "regional_office": "Example Office",
        "facility_capacity": "10",
        "bulk_status": "Licensed",
        "license_first_date": "2020-01-01",
        "closed_date": "2026-01-01",
        "last_visit_date": "2026-01-02",
    }
    return {key: normalized_observation(value) for key, value in values.items()}


def _transparency_row(
    ordinal: int,
    facility_number: str | None,
    normalized: dict[str, Any],
    resolved: dict[str, Any],
    *,
    complaint_blocks: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "snapshot_id": SNAPSHOT_ID,
        "export_id": "ChildCareCenters",
        "row_ordinal": ordinal,
        "facility_number": facility_number,
        "raw_row_sha256": f"{ordinal}" * 64,
        "raw_values": [],
        "raw_record": {},
        "normalized_record": normalized,
        "resolved_current_reference": resolved,
        "complaint_blocks": complaint_blocks,
        "row_fingerprint": f"{ordinal + 3}" * 64,
        "is_quarantined": False,
    }


def _quarantine(ordinal: int, category: str) -> dict[str, Any]:
    return {
        "snapshot_id": SNAPSHOT_ID,
        "quarantine_id": f"quarantine-{ordinal}",
        "category": category,
        "export_id": "ChildCareCenters",
        "row_ordinal": ordinal,
        "facility_number": None,
        "raw_row_sha256": f"{ordinal}" * 64,
        "evidence": {},
    }


def _table_counts(connection: Any) -> tuple[int, int, int, int]:
    return (
        int(connection.scalar(select(func.count()).select_from(source_snapshots)) or 0),
        int(
            connection.scalar(select(func.count()).select_from(source_snapshot_pointers))
            or 0
        ),
        int(connection.scalar(select(func.count()).select_from(transparency_rows)) or 0),
        int(
            connection.scalar(select(func.count()).select_from(transparency_quarantines))
            or 0
        ),
    )


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }
