from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, ValidationError
from jsonschema import validate as jsonschema_validate
from sqlalchemy import JSON, Column, Integer, MetaData, String, Table, create_engine

from ccld_complaints.source_to_screen_audit import (
    COVERAGE_CONTRACT_VERSION,
    COVERAGE_INVARIANT_IDS,
    COVERAGE_STAGE_STATES,
    COVERAGE_STAGES,
    COVERAGE_TERMINAL_CLASSIFICATIONS,
    MANDATORY_OUTPUTS,
    AuditResult,
    CoverageContractError,
    classify_scalar,
    deduplicate_recommended_issues,
    detect_raw_artifact_fields,
    generate_coverage_package,
    inspect_raw_artifacts,
    inspect_runtime_store,
    inspect_sqlite_store,
    load_coverage_fixture_scenario,
    redact_sensitive_text,
    run_audit,
    validate_coverage_package,
)
from ccld_complaints.source_to_screen_catalog import (
    GAP_CLASSIFICATIONS,
    ElementSpec,
    classify_gap,
    discover_element_specs,
    stable_data_element_id,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
RECORD_VALUE_CANARY = "synthetic-record-value-must-not-escape"
COVERAGE_FIXTURE_BUNDLE = (
    REPO_ROOT / "tests" / "fixtures" / "source_to_screen_coverage" / "scenarios.json"
)
COVERAGE_FIXED_TIME = datetime(2026, 7, 19, 18, 0, 0, tzinfo=UTC)


def _spec(**overrides: Any) -> ElementSpec:
    values: dict[str, Any] = {
        "data_element_id": "data.complaint.complaint.audit_field",
        "reviewer_facing_name": "Audit field",
        "ownership": "complaint",
        "source_artifact_type": "synthetic governed artifact",
        "source_field_or_extractor_reference": "Audit Field label",
        "source_availability_status": "available in governed fixture",
        "extraction_status": "deterministically extracted",
        "canonical_entity": "complaint",
        "canonical_column": "audit_field",
        "data_type": "string",
        "null_meaning": "source did not provide the field",
        "blank_meaning": "unexpected blank requiring review",
        "zero_meaning": "not applicable to a text field",
        "query_service_consumer": "synthetic test query",
        "current_display_route_or_export": "/complaints/{record_id}",
        "recommended_display_location": "complaint detail",
        "recommended_display_method": "labeled text",
        "traceability_availability": "source document reference retained",
        "validation_coverage": "synthetic aggregate adapter test",
        "gap_classification": "NOT_APPLICABLE",
        "disposition": "retain",
        "priority": "P2",
        "evidence_reference_location": "tests/unit/test_source_to_screen_audit.py",
        "source_observation_field": "complaint_control_number",
        "source_observation_sources": ("governed_complaint_fixtures",),
        "runtime_table": None,
        "runtime_column": None,
        "reviewer_relevant": True,
        "facility_hub_relevant": False,
        "complaint_detail_relevant": True,
        "dependencies": "",
        "validation_requirement": "Run the focused source-to-screen audit tests.",
    }
    values.update(overrides)
    return ElementSpec(**values)


def _coverage_fixture(scenario: str) -> Mapping[str, Any]:
    return load_coverage_fixture_scenario(COVERAGE_FIXTURE_BUNDLE, scenario)


def _generate_coverage_scenario(
    tmp_path: Path, scenario: str, *, directory_name: str | None = None
) -> Any:
    return generate_coverage_package(
        _coverage_fixture(scenario),
        output_dir=tmp_path / (directory_name or scenario),
        repo_root=REPO_ROOT,
        generated_at=COVERAGE_FIXED_TIME,
    )


def test_gap_classification_vocabulary_is_exact() -> None:
    assert tuple(GAP_CLASSIFICATIONS) == (
        "SOURCE_NOT_PROVIDED",
        "RAW_PRESENT_EXTRACTION_MISSING",
        "EXTRACTED_CANONICAL_MAPPING_MISSING",
        "CANONICAL_IMPORT_NOT_POPULATED",
        "SQLITE_POSTGRES_DIVERGENCE",
        "STORED_QUERY_OMISSION",
        "UI_DISPLAY_OMISSION",
        "UNEXPLAINED_BLANK",
        "AGGREGATE_DATA_INSUFFICIENT",
        "FIXTURE_RUNTIME_DIVERGENCE",
        "INTENTIONALLY_INTERNAL",
        "NOT_APPLICABLE",
    )


@pytest.mark.parametrize(
    ("inputs", "expected"),
    (
        ({}, "NOT_APPLICABLE"),
        ({"applicable": False}, "NOT_APPLICABLE"),
        ({"intentionally_internal": True}, "INTENTIONALLY_INTERNAL"),
        (
            {"raw_present": True, "extracted": False, "source_available": False},
            "RAW_PRESENT_EXTRACTION_MISSING",
        ),
        (
            {"extracted": True, "canonical_mapped": False},
            "EXTRACTED_CANONICAL_MAPPING_MISSING",
        ),
        (
            {"query_consumed": True, "displayed": False},
            "UI_DISPLAY_OMISSION",
        ),
    ),
)
def test_classify_gap_uses_the_exact_vocabulary_and_precedence(
    inputs: dict[str, bool],
    expected: str,
) -> None:
    assert classify_gap(**inputs) == expected


def test_discovery_identifiers_and_canonical_mappings_are_stable() -> None:
    assert stable_data_element_id("complaint", "complaint", "report_date") == (
        "data.complaint.complaint.report_date"
    )
    assert stable_data_element_id("facility", "facility", "facility_name") == (
        "data.facility.facility.facility_name"
    )

    specs = discover_element_specs(REPO_ROOT)
    identifiers = [spec.data_element_id for spec in specs]

    assert identifiers == sorted(identifiers)
    assert len(identifiers) == len(set(identifiers))
    assert all(
        re.fullmatch(r"data\.[a-z0-9_]+\.[a-z0-9_]+\.[a-z0-9_]+", value)
        for value in identifiers
    )

    by_id = {spec.data_element_id: spec for spec in specs}
    complaint_control = by_id[
        stable_data_element_id("complaint", "complaint", "complaint_control_number")
    ]
    facility_number = by_id[
        stable_data_element_id("facility", "facility", "external_facility_number")
    ]
    allegation_text = by_id[
        stable_data_element_id("complaint", "allegation", "allegation_text")
    ]

    assert (complaint_control.canonical_entity, complaint_control.canonical_column) == (
        "complaint",
        "complaint_control_number",
    )
    assert (facility_number.canonical_entity, facility_number.canonical_column) == (
        "facility",
        "external_facility_number",
    )
    assert (allegation_text.canonical_entity, allegation_text.canonical_column) == (
        "allegation",
        "allegation_text",
    )


def test_issue_447_source_reference_allocations_are_not_canonical_gaps() -> None:
    specs = discover_element_specs(REPO_ROOT)
    by_id = {spec.data_element_id: spec for spec in specs}
    program_scope = "facility_fixture_ccld_program_facilities_tiny"
    master_scope = "facility_fixture_chhs_facility_master_tiny"
    program_allocations = {
        "All Visit Dates": "all_visit_dates",
        "Inspection Visit Dates": "inspection_visit_dates",
        "Other Visit Dates": "other_visit_dates",
        "Closed Date": "closed_date",
        (
            "Complaint Info- Date, #Sub Aleg, # Inc Aleg, # Uns Aleg, # TypeA, "
            "# TypeB ..."
        ): None,
    }

    for header, runtime_column in program_allocations.items():
        spec = by_id[stable_data_element_id("facility", program_scope, header)]
        assert spec.gap_classification == "NOT_APPLICABLE"
        assert spec.canonical_entity is None
        assert spec.canonical_column is None
        assert spec.runtime_table == "hosted_facility_reference_records"
        assert spec.runtime_column == runtime_column

    client_served = by_id[
        stable_data_element_id("facility", master_scope, "CLIENT_SERVED")
    ]
    numeric_type = by_id[stable_data_element_id("facility", master_scope, "TYPE")]
    assert client_served.gap_classification == "NOT_APPLICABLE"
    assert client_served.runtime_column == "client_served"
    assert client_served.canonical_column is None
    assert numeric_type.gap_classification == "INTENTIONALLY_INTERNAL"
    assert numeric_type.canonical_column is None


def test_discovery_uses_an_explicit_reviewer_surface_inventory(tmp_path: Path) -> None:
    repo = tmp_path / "catalog-only-repo"
    schema_dir = repo / "schemas"
    schema_dir.mkdir(parents=True)
    for source in sorted((REPO_ROOT / "schemas").glob("*.schema.json")):
        (schema_dir / source.name).write_bytes(source.read_bytes())

    specs = discover_element_specs(repo)
    displayed = [spec for spec in specs if spec.current_display_route_or_export]

    assert displayed
    assert all(spec.evidence_reference_location for spec in displayed)
    assert all(spec.query_service_consumer for spec in displayed)
    complaint_control = next(
        spec
        for spec in displayed
        if (spec.canonical_entity, spec.canonical_column)
        == ("complaint", "complaint_control_number")
    )
    assert complaint_control.current_display_route_or_export == (
        "/reviewer/records; /reviewer/records/detail"
    )


def test_unknown_retained_csv_headers_cannot_enter_catalog_or_baseline(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "retained-header-repo"
    schema_dir = repo / "schemas"
    schema_dir.mkdir(parents=True)
    for source in sorted((REPO_ROOT / "schemas").glob("*.schema.json")):
        (schema_dir / source.name).write_bytes(source.read_bytes())
    retained_dir = repo / "data" / "raw" / "source-profiling"
    retained_dir.mkdir(parents=True)
    (retained_dir / "configured.csv").write_text(
        f"{RECORD_VALUE_CANARY},another-unsafe-header\n",
        encoding="utf-8",
    )

    specs = discover_element_specs(repo)
    serialized = json.dumps([asdict(spec) for spec in specs], sort_keys=True)

    assert RECORD_VALUE_CANARY not in serialized
    assert "another-unsafe-header" not in serialized
    assert "Unmapped source column 1" in serialized

    run_audit(
        mode="local",
        output_dir=repo / "data" / "processed" / "audit",
        write_tracked_baseline=True,
        repo_root=repo,
        generated_at=datetime(2026, 7, 13, tzinfo=UTC),
        environ={},
    )
    baseline = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((repo / "docs" / "data").glob("*.md"))
    )
    assert RECORD_VALUE_CANARY not in baseline
    assert "another-unsafe-header" not in baseline


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        (None, "null"),
        ("", "blank"),
        (" \t ", "blank"),
        ("unknown", "literal_unknown"),
        ("Unavailable", "literal_unavailable"),
        ("N/A", "literal_not_applicable"),
        ("undated", "date_unavailable"),
        (0, "verified_zero"),
        (0.0, "verified_zero"),
        (False, "verified_false"),
        ("0", "populated_text"),
    ),
)
def test_classify_scalar_preserves_missing_and_zero_semantics(
    value: object,
    expected: str,
) -> None:
    assert classify_scalar(value) == expected


def test_raw_artifact_detection_returns_allowlisted_field_identities_only(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "synthetic_inx1.html"
    artifact.write_text(
        """
        <html><body>
        <dl>
          <dt>Facility Number</dt><dd>synthetic-id</dd>
          <dt>Facility Name</dt><dd>synthetic-name</dd>
          <dt>Complaint Control Number</dt><dd>synthetic-control</dd>
          <dt>Complaint Was Received</dt><dd>undated</dd>
          <dt>Investigation Findings</dt><dd>synthetic findings body</dd>
        </dl>
        <p>synthetic padding for a usable artifact with no real record content.</p>
        <script>Allegation(s): ignored script-only label</script>
        </body></html>
        """,
        encoding="utf-8",
    )

    html = artifact.read_text(encoding="utf-8")
    assert detect_raw_artifact_fields(html) == (
        "complaint_control_number",
        "complaint_received_date",
        "facility_name",
        "facility_number",
        "investigation_findings_narrative",
    )

    observation = inspect_raw_artifacts((artifact,), source_id="synthetic")
    serialized = json.dumps(asdict(observation), sort_keys=True)
    assert observation.usable_artifact_count == 1
    assert observation.field_counts["complaint_control_number"] == 1
    assert "synthetic-control" not in serialized
    assert "synthetic findings body" not in serialized


def test_sqlite_adapter_returns_aggregate_semantics_without_record_values(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "audit.sqlite"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "CREATE TABLE complaints "
            "(audit_field TEXT, numeric_field INTEGER, private_payload TEXT)"
        )
        connection.executemany(
            "INSERT INTO complaints VALUES (?, ?, ?)",
            (
                (None, None, RECORD_VALUE_CANARY),
                ("", None, RECORD_VALUE_CANARY),
                ("  ", None, RECORD_VALUE_CANARY),
                ("unknown", None, RECORD_VALUE_CANARY),
                ("unavailable", None, RECORD_VALUE_CANARY),
                ("N/A", None, RECORD_VALUE_CANARY),
                ("undated", 0, RECORD_VALUE_CANARY),
                ("present", 7, RECORD_VALUE_CANARY),
            ),
        )

    text_spec = _spec()
    numeric_spec = _spec(
        data_element_id="data.complaint.complaint.numeric_field",
        reviewer_facing_name="Numeric field",
        canonical_column="numeric_field",
        data_type="integer",
    )
    snapshot = inspect_sqlite_store(database_path, (numeric_spec, text_spec))

    text_stats = snapshot.stats[text_spec.data_element_id]
    assert asdict(text_stats) == {
        "eligible_record_count": 8,
        "populated_count": 5,
        "missing_key_count": 0,
        "null_count": 1,
        "blank_count": 2,
        "literal_unknown_count": 1,
        "literal_unavailable_count": 1,
        "literal_not_applicable_count": 1,
        "date_unavailable_count": 1,
        "verified_zero_count": 0,
    }
    assert snapshot.stats[numeric_spec.data_element_id].verified_zero_count == 1
    assert RECORD_VALUE_CANARY not in json.dumps(asdict(snapshot), sort_keys=True)


def test_runtime_sqlite_adapters_return_json_and_typed_aggregates_without_values() -> None:
    metadata = MetaData()
    source_records = Table(
        "hosted_source_derived_records",
        metadata,
        Column("row_id", Integer, primary_key=True),
        Column("entity_type", String, nullable=False),
        Column("original_values", JSON, nullable=False),
    )
    typed_records = Table(
        "hosted_facility_reference_records",
        metadata,
        Column("row_id", Integer, primary_key=True),
        Column("capacity", Integer),
        Column("private_payload", String),
    )
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata.create_all(engine)

    json_values = (
        {},
        {"audit_field": None},
        {"audit_field": ""},
        {"audit_field": "unknown"},
        {"audit_field": "unavailable"},
        {"audit_field": "N/A"},
        {"audit_field": "undated"},
        {"audit_field": 0},
        {"audit_field": 4, "private_payload": RECORD_VALUE_CANARY},
    )
    with engine.begin() as connection:
        connection.execute(
            source_records.insert(),
            [
                {"row_id": index, "entity_type": "complaint", "original_values": value}
                for index, value in enumerate(json_values, start=1)
            ],
        )
        connection.execute(
            typed_records.insert(),
            [
                {"row_id": 1, "capacity": None, "private_payload": RECORD_VALUE_CANARY},
                {"row_id": 2, "capacity": 0, "private_payload": RECORD_VALUE_CANARY},
                {"row_id": 3, "capacity": 5, "private_payload": RECORD_VALUE_CANARY},
            ],
        )
        snapshot = inspect_runtime_store(
            connection,
            (
                _spec(data_type="number"),
                _spec(
                    data_element_id="data.facility.runtime.capacity",
                    reviewer_facing_name="Capacity",
                    ownership="facility",
                    canonical_entity=None,
                    canonical_column=None,
                    data_type="integer",
                    runtime_table="hosted_facility_reference_records",
                    runtime_column="capacity",
                ),
            ),
        )

    json_stats = snapshot.stats["data.complaint.complaint.audit_field"]
    assert asdict(json_stats) == {
        "eligible_record_count": 9,
        "populated_count": 6,
        "missing_key_count": 1,
        "null_count": 1,
        "blank_count": 1,
        "literal_unknown_count": 1,
        "literal_unavailable_count": 1,
        "literal_not_applicable_count": 1,
        "date_unavailable_count": 1,
        "verified_zero_count": 1,
    }
    typed_stats = snapshot.stats["data.facility.runtime.capacity"]
    assert typed_stats.eligible_record_count == 3
    assert typed_stats.populated_count == 2
    assert typed_stats.null_count == 1
    assert typed_stats.verified_zero_count == 1
    assert RECORD_VALUE_CANARY not in json.dumps(asdict(snapshot), sort_keys=True)


def test_parity_report_is_written_only_when_both_stores_are_inspected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "parity-repo"
    repo.mkdir()
    database_path = repo / "local.sqlite"
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE complaints (audit_field TEXT)")
        connection.executemany(
            "INSERT INTO complaints VALUES (?)",
            ((None,), ("present",)),
        )

    metadata = MetaData()
    source_records = Table(
        "hosted_source_derived_records",
        metadata,
        Column("row_id", Integer, primary_key=True),
        Column("entity_type", String, nullable=False),
        Column("original_values", JSON, nullable=False),
    )
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata.create_all(engine)
    spec = _spec()
    monkeypatch.setattr(
        "ccld_complaints.source_to_screen_audit.discover_element_specs",
        lambda _repo_root: (spec,),
    )
    output_dir = repo / "audit"
    with engine.begin() as connection:
        connection.execute(
            source_records.insert(),
            [
                {
                    "row_id": 1,
                    "entity_type": "complaint",
                    "original_values": {"audit_field": None},
                },
                {
                    "row_id": 2,
                    "entity_type": "complaint",
                    "original_values": {"audit_field": "present"},
                },
            ],
        )
        result = run_audit(
            mode="local",
            output_dir=output_dir,
            repo_root=repo,
            generated_at=datetime(2026, 7, 13, tzinfo=UTC),
            environ={"CCLD_SOURCE_TO_SCREEN_SQLITE_PATH": str(database_path)},
            runtime_connection=connection,
        )

    assert len(result.parity) == 1
    assert result.parity[0]["parity_status"] == "counts match"
    assert (output_dir / "sqlite-postgres-parity.csv").is_file()


def test_redaction_removes_connections_urls_paths_and_secret_assignments() -> None:
    unsafe = (
        "postgresql://sample-user:sample-pass@private.invalid/audit "
        "https://private.invalid/record "
        "C:\\Users\\sample-user\\private\\audit.txt "
        "/home/sample-user/private/audit.txt token=synthetic-token"
    )

    safe = redact_sensitive_text(unsafe)

    assert "postgresql://" not in safe
    assert "private.invalid" not in safe
    assert "sample-user" not in safe
    assert "synthetic-token" not in safe
    assert "<redacted-connection-string>" in safe
    assert "<redacted-url>" in safe
    assert safe.count("<redacted-path>") == 2
    assert "token=<redacted>" in safe


def test_recommended_issue_deduplication_merges_stable_sorted_references() -> None:
    issues = (
        {
            "issue_id": "second-copy",
            "title": "  Close   audit gap ",
            "priority": "P1",
            "labels": ["source-to-screen"],
            "dependencies": ["beta"],
            "related_gap_identifiers": ["gap.two"],
            "acceptance_criteria": ["Second criterion"],
            "validation_requirements": ["Run beta"],
        },
        {
            "issue_id": "first-copy",
            "title": "close audit gap",
            "priority": "P1",
            "labels": ["audit", "source-to-screen"],
            "dependencies": ["alpha"],
            "related_gap_identifiers": ["gap.one", "gap.two"],
            "acceptance_criteria": ["First criterion"],
            "validation_requirements": ["Run alpha"],
        },
    )

    assert deduplicate_recommended_issues(issues) == (
        {
            "issue_id": "second-copy",
            "title": "Close audit gap",
            "priority": "P1",
            "labels": ["audit", "source-to-screen"],
            "dependencies": ["alpha", "beta"],
            "related_gap_identifiers": ["gap.one", "gap.two"],
            "acceptance_criteria": ["First criterion", "Second criterion"],
            "validation_requirements": ["Run alpha", "Run beta"],
        },
    )


def test_audit_output_and_tracked_baseline_are_deterministic_and_value_free(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "synthetic-repo"
    raw_dir = repo / "tests" / "fixtures" / "ccld" / "raw"
    raw_dir.mkdir(parents=True)
    (raw_dir / "synthetic_inx1.html").write_text(
        "<html><body><p>Facility Number: synthetic-id</p>"
        "<p>Facility Name: synthetic-name</p>"
        "<p>Complaint Control Number: "
        + RECORD_VALUE_CANARY
        + "</p><p>Investigation Findings: https://private.invalid/record "
        "C:\\Users\\sample-user\\private\\record.txt</p>"
        "<p>synthetic padding ensures this governed artifact is long enough.</p>"
        "</body></html>",
        encoding="utf-8",
    )
    database_path = repo / "data" / "processed" / "ccld.sqlite"
    database_path.parent.mkdir(parents=True)
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE complaints (audit_field TEXT)")
        connection.execute("INSERT INTO complaints VALUES (?)", (RECORD_VALUE_CANARY,))

    spec = _spec()
    monkeypatch.setattr(
        "ccld_complaints.source_to_screen_audit.discover_element_specs",
        lambda _repo_root: (spec,),
    )
    fixed_time = datetime(2026, 7, 13, 12, 34, 56, tzinfo=UTC)
    first_output = repo / "data" / "processed" / "audit-first"
    second_output = repo / "data" / "processed" / "audit-second"

    first = run_audit(
        mode="local",
        output_dir=first_output,
        write_tracked_baseline=True,
        repo_root=repo,
        generated_at=fixed_time,
        environ={},
    )
    second = run_audit(
        mode="local",
        output_dir=second_output,
        write_tracked_baseline=True,
        repo_root=repo,
        generated_at=fixed_time,
        environ={},
    )

    assert first == second
    first_files = {path.name: path.read_bytes() for path in sorted(first_output.iterdir())}
    second_files = {path.name: path.read_bytes() for path in sorted(second_output.iterdir())}
    assert first_files == second_files
    assert set(first_files) == set(MANDATORY_OUTPUTS)

    baseline_dir = repo / "docs" / "data"
    baseline_files = sorted(baseline_dir.glob("source-to-screen-*.md"))
    assert [path.name for path in baseline_files] == [
        "source-to-screen-audit.md",
        "source-to-screen-gap-register.md",
        "source-to-screen-inventory.md",
        "source-to-screen-remediation-plan.md",
    ]
    emitted_text = b"\n".join(
        (*first_files.values(), *(path.read_bytes() for path in baseline_files))
    )
    assert RECORD_VALUE_CANARY.encode() not in emitted_text
    assert b"private.invalid" not in emitted_text
    assert b"C:\\Users\\" not in emitted_text
    assert b"C:/Users/" not in emitted_text


def test_audit_result_shape_cannot_hold_source_bodies_by_default() -> None:
    fields = set(AuditResult.__dataclass_fields__)

    assert "source_values" not in fields
    assert "source_document_bodies" not in fields
    assert "record_narratives" not in fields


def test_coverage_catalog_consumes_the_tracked_inventory_only() -> None:
    inventory_text = (REPO_ROOT / "docs" / "data" / "source-to-screen-inventory.md").read_text(
        encoding="utf-8"
    )
    tracked_ids = set(
        re.findall(r"^\| `(data\.[^`]+)` \|", inventory_text, flags=re.MULTILINE)
    )
    discovered_ids = {spec.data_element_id for spec in discover_element_specs(REPO_ROOT)}

    assert discovered_ids == tracked_ids
    assert all("issue-490" not in field_id for field_id in discovered_ids)
    assert all("issues-453-477" not in field_id for field_id in discovered_ids)


def test_coverage_contract_schema_is_closed_and_valid(tmp_path: Path) -> None:
    schema = json.loads(
        (
            REPO_ROOT
            / "schemas"
            / "issues-453-477-coverage-report-v1.schema.json"
        ).read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    report = deepcopy(
        _generate_coverage_scenario(
            tmp_path,
            "complete-balanced",
            directory_name="schema-closed-fixture",
        ).report
    )

    jsonschema_validate(instance=report, schema=schema)
    report["coverage"]["field_stage_coverage"][0]["stage"] = "unknown_stage"
    with pytest.raises(ValidationError):
        jsonschema_validate(instance=report, schema=schema)

    report = deepcopy(
        _generate_coverage_scenario(
            tmp_path,
            "complete-balanced",
            directory_name="schema-closed-fixture",
        ).report
    )
    report["record_values"] = []
    with pytest.raises(ValidationError):
        jsonschema_validate(instance=report, schema=schema)


def test_coverage_package_is_deterministic_portable_reconciled_and_value_free(
    tmp_path: Path,
) -> None:
    first = _generate_coverage_scenario(tmp_path, "complete-balanced", directory_name="first")
    second = _generate_coverage_scenario(tmp_path, "complete-balanced", directory_name="second")
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"

    assert first == second
    assert first.report_id == (
        "coverage-report-v1-"
        "6b6670913151e7bb7f4ef3225f309cdd95a6724090a31f8ca9f1943f6d9a60cd"
    )
    assert re.fullmatch(r"coverage-report-v1-[0-9a-f]{64}", first.report_id)
    assert validate_coverage_package(first_dir, repo_root=REPO_ROOT) == first.manifest
    assert validate_coverage_package(second_dir, repo_root=REPO_ROOT) == second.manifest

    first_files = {path.name: path.read_bytes() for path in sorted(first_dir.iterdir())}
    second_files = {path.name: path.read_bytes() for path in sorted(second_dir.iterdir())}
    assert first_files == second_files
    assert set(first_files) == {
        "aggregate-coverage.csv",
        "coverage-report.json",
        "manifest.json",
        "operator-facility-index.jsonl",
        "operator-job-index.jsonl",
    }
    assert b"\r" not in b"".join(first_files.values())
    assert first.manifest["generated_at"] == first.report["generated_at"]
    assert first.manifest["contract_version"] == COVERAGE_CONTRACT_VERSION
    assert first.manifest["package_availability"] == "available"

    specs = discover_element_specs(REPO_ROOT)
    coverage = first.report["coverage"]
    stage_rows = coverage["field_stage_coverage"]
    assert coverage["inventory_field_total"] == len(specs)
    assert len(stage_rows) == len(specs) * len(COVERAGE_STAGES)
    assert {row["stage"] for row in stage_rows} == set(COVERAGE_STAGES)
    assert {row["field_id"] for row in stage_rows} == {
        spec.data_element_id for spec in specs
    }
    for row in stage_rows:
        assert row["eligible_count"] == sum(
            row[f"{state}_count"] for state in COVERAGE_STAGE_STATES
        )
    reconciliation = first.report["reconciliation"]
    assert reconciliation["reconciliation_status"] == "passed"
    assert tuple(row["invariant_id"] for row in reconciliation["invariants"]) == (
        COVERAGE_INVARIANT_IDS
    )
    assert all(
        row["status"] in {"passed", "not_applicable"}
        for row in reconciliation["invariants"]
    )
    assert first.report["release_assessment"]["status"] == "passed"
    facility_reference = coverage["facility_reference"]
    assert facility_reference["availability"] == "available"
    assert facility_reference["snapshot"]["selection_state"] == "active_accepted"
    assert facility_reference["release_assessment"]["status"] == "passed"
    assert first.report["source_governance"] == {
        "primary_current_source_family": (
            "ccld-transparencyapi-facility-reference"
        ),
        "primary_selection_state": "active_accepted",
        "arcgis_role": "supplementary",
        "ckan_program_role": "historical_or_controlled_fallback",
        "complaint_time_role": "historical_complaint_context",
        "current_and_complaint_time_separate": True,
        "refresh_schedule_status": "not_approved",
        "raw_733_mapping_status": "unresolved",
        "raw_733_descriptive_label_emitted": False,
    }

    report_bytes = first_files["coverage-report.json"]
    csv_bytes = first_files["aggregate-coverage.csv"]
    assert b"100000001" not in report_bytes + csv_bytes
    assert b"100000002" not in report_bytes + csv_bytes
    assert b"facility_id" not in csv_bytes.splitlines()[0]
    assert RECORD_VALUE_CANARY.encode() not in b"".join(first_files.values())
    assert b"STRTP" not in b"".join(first_files.values())
    assert b"C:\\Users\\" not in b"".join(first_files.values())
    assert b"C:/Users/" not in b"".join(first_files.values())
    assert b"http://" not in b"".join(first_files.values())
    assert b"https://" not in b"".join(first_files.values())

    allowed_facility_fields = {
        "contract_version",
        "report_id",
        "facility_entry_id",
        "facility_id",
        "source_snapshot_id",
        "refresh_eligibility",
        "preserved_source_document_count",
        "last_retrieval_attempt_at",
        "last_successful_retrieval_at",
        "last_refresh_attempt_at",
        "last_successful_refresh_at",
        "pipeline_version",
        "preserved_artifact_state",
        "hash_validation_state",
        "source_layout_classification",
        "processing_outcome",
        "change_outcome",
        "refresh_state",
        "governed_conflict",
        "operational_failure_category",
        "retry_eligibility",
        "operator_intervention_required",
        "checkpoint_state",
        "last_job_id",
    }
    assert all(set(row) == allowed_facility_fields for row in first.facility_index)


def test_every_terminal_and_stage_category_remains_distinct(tmp_path: Path) -> None:
    fixture = deepcopy(_coverage_fixture("complete-balanced"))
    fixture["evaluation_id"] = "fixture.all-coverage-categories.v1"
    field_ids = [spec.data_element_id for spec in discover_element_specs(REPO_ROOT)]
    fixture["coverage"]["terminal_overrides"] = dict(
        zip(field_ids, COVERAGE_TERMINAL_CLASSIFICATIONS, strict=False)
    )

    package = generate_coverage_package(
        fixture,
        output_dir=tmp_path / "all-coverage-categories",
        repo_root=REPO_ROOT,
        generated_at=COVERAGE_FIXED_TIME,
    )

    terminal_counts = package.report["coverage"]["terminal_classification_counts"]
    assert set(terminal_counts) == set(COVERAGE_TERMINAL_CLASSIFICATIONS)
    assert all(terminal_counts[name] > 0 for name in COVERAGE_TERMINAL_CLASSIFICATIONS)
    stage_totals = {
        state: sum(
            row[f"{state}_count"]
            for row in package.report["coverage"]["field_stage_coverage"]
        )
        for state in COVERAGE_STAGE_STATES
    }
    assert all(stage_totals[state] > 0 for state in COVERAGE_STAGE_STATES)


def test_aggregate_stage_and_terminal_counts_can_exceed_one_per_field(
    tmp_path: Path,
) -> None:
    fixture = deepcopy(_coverage_fixture("complete-balanced"))
    fixture["evaluation_id"] = "fixture.aggregate-counts.v1"
    field_id = discover_element_specs(REPO_ROOT)[0].data_element_id
    fixture["coverage"]["stage_count_overrides"] = {
        field_id: {
            "source_presence": {
                "eligible_count": 4,
                "successful_count": 3,
                "blank_count": 1,
                "absent_count": 0,
                "unavailable_count": 0,
                "unsupported_count": 0,
                "conflict_count": 0,
                "failure_count": 0,
                "skipped_count": 0,
            }
        }
    }
    fixture["coverage"]["terminal_classification_eligible_count"] = 7
    fixture["coverage"]["terminal_classification_counts"] = {
        name: 0 for name in COVERAGE_TERMINAL_CLASSIFICATIONS
    }
    fixture["coverage"]["terminal_classification_counts"][
        "present_and_populated"
    ] = 5
    fixture["coverage"]["terminal_classification_counts"]["present_blank"] = 2

    package = generate_coverage_package(
        fixture,
        output_dir=tmp_path / "aggregate-counts",
        repo_root=REPO_ROOT,
        generated_at=COVERAGE_FIXED_TIME,
    )

    stage_row = next(
        row
        for row in package.report["coverage"]["field_stage_coverage"]
        if row["field_id"] == field_id and row["stage"] == "source_presence"
    )
    assert stage_row["eligible_count"] == 4
    assert stage_row["successful_count"] == 3
    assert stage_row["blank_count"] == 1
    assert package.report["coverage"][
        "terminal_classification_eligible_count"
    ] == 7
    assert package.report["reconciliation"]["reconciliation_status"] == "passed"
    validate_coverage_package(tmp_path / "aggregate-counts", repo_root=REPO_ROOT)


def test_empty_partial_and_failed_reconciliation_scenarios_fail_closed(
    tmp_path: Path,
) -> None:
    empty = _generate_coverage_scenario(tmp_path, "empty-verified")
    assert empty.report["operations"]["existing_facility_total"] == 0
    assert empty.facility_index == ()
    assert (tmp_path / "empty-verified" / "operator-facility-index.jsonl").read_bytes() == b""
    validate_coverage_package(tmp_path / "empty-verified", repo_root=REPO_ROOT)

    partial = _generate_coverage_scenario(tmp_path, "partial-unavailable-stage")
    assert partial.report["package_availability"] == "partial"
    assert partial.report["unavailable_dimensions"] == [
        "operator_job_index",
        "postgresql_population",
    ]
    assert not (tmp_path / "partial-unavailable-stage" / "operator-job-index.jsonl").exists()
    validate_coverage_package(tmp_path / "partial-unavailable-stage", repo_root=REPO_ROOT)

    failed = _generate_coverage_scenario(tmp_path, "failed-reconciliation")
    assert failed.report["package_availability"] == "reconciliation_failed"
    assert failed.report["reconciliation"]["reconciliation_status"] == "failed"
    assert failed.report["release_assessment"]["status"] == "failed"
    assert any(
        row["status"] == "failed"
        for row in failed.report["reconciliation"]["invariants"]
    )
    with pytest.raises(CoverageContractError, match="reconciliation failed"):
        validate_coverage_package(tmp_path / "failed-reconciliation", repo_root=REPO_ROOT)


def test_version_mismatch_and_prohibited_content_are_rejected() -> None:
    with pytest.raises(CoverageContractError, match="version is not supported"):
        generate_coverage_package(
            _coverage_fixture("version-mismatch"),
            output_dir=Path("data/processed/source-to-screen-audit/version-mismatch"),
            repo_root=REPO_ROOT,
            generated_at=COVERAGE_FIXED_TIME,
        )
    with pytest.raises(CoverageContractError, match="prohibited field"):
        _coverage_fixture("prohibited-content-rejected")


def test_hash_failure_is_operationally_distinct_and_package_hashes_fail_closed(
    tmp_path: Path,
) -> None:
    package = _generate_coverage_scenario(tmp_path, "hash-validation-failure")
    assert package.report["operations"]["hash_validation_state_counts"]["failed"] == 1
    assert package.facility_index[0]["operational_failure_category"] == (
        "hash_validation_failed"
    )
    validate_coverage_package(tmp_path / "hash-validation-failure", repo_root=REPO_ROOT)

    report_path = tmp_path / "hash-validation-failure" / "coverage-report.json"
    corrupted = bytearray(report_path.read_bytes())
    corrupted[-2] = ord("]")
    report_path.write_bytes(corrupted)
    with pytest.raises(CoverageContractError, match="hash validation failed"):
        validate_coverage_package(tmp_path / "hash-validation-failure", repo_root=REPO_ROOT)


def test_interrupted_operation_retains_previous_accepted_coverage_independently(
    tmp_path: Path,
) -> None:
    package = _generate_coverage_scenario(
        tmp_path, "interrupted-job-previous-accepted-active"
    )

    assert package.job_index[0]["job_state"] == "interrupted"
    assert package.job_index[0]["previous_accepted_dataset_active"] is True
    assert package.manifest["retention"]["previous_accepted_report_id"].startswith(
        "coverage-report-v1-"
    )
    assert package.report["reconciliation"]["reconciliation_status"] == "passed"
    assert package.report["operations"]["processing_outcome_counts"]["successful"] == 2
    assert package.report["coverage"]["terminal_classification_counts"][
        "read_but_not_rendered"
    ] > 0


def test_raw_733_stays_unresolved_without_a_descriptive_label(tmp_path: Path) -> None:
    package = _generate_coverage_scenario(tmp_path, "raw-733-unresolved")
    emitted = b"".join(
        path.read_bytes() for path in sorted((tmp_path / "raw-733-unresolved").iterdir())
    )

    assert package.report["issue_490_boundaries"] == {
        "retained_source_scope": "existing_program_specific_sources",
        "statewide_candidate_selection_state": "inactive_candidate",
        "statewide_completeness_baseline": "not_established",
        "cadence_status": "not_approved",
        "raw_733_mapping_status": "unresolved",
        "raw_733_descriptive_label_emitted": False,
    }
    assert package.report["release_assessment"]["status"] == "warning"
    assert b"STRTP" not in emitted
    assert b"Short-Term Residential" not in emitted


def test_adjacent_facility_pages_have_stable_order_without_duplicates(
    tmp_path: Path,
) -> None:
    package = _generate_coverage_scenario(tmp_path, "pagination-adjacent-pages")
    facility_ids = [row["facility_id"] for row in package.facility_index]
    entry_ids = [row["facility_entry_id"] for row in package.facility_index]
    first_page = entry_ids[:2]
    second_page = entry_ids[2:4]

    assert facility_ids == ["100000001", "100000002", "100000003", "100000010"]
    assert set(first_page).isdisjoint(second_page)
    assert first_page + second_page == entry_ids
    assert len(set(entry_ids)) == len(entry_ids)
    processing = package.report["operations"]["processing_outcome_counts"]
    assert processing["successful"] == 1
    assert processing["skipped"] == 1
    assert processing["warning"] == 1
    assert processing["not_yet_processed"] == 1
    assert package.report["operations"]["change_outcome_counts"] == {
        "changed": 1,
        "not_evaluated": 2,
        "unchanged": 1,
    }


def test_same_evaluation_identity_cannot_overwrite_different_results(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "immutable-evaluation"
    fixture = deepcopy(_coverage_fixture("complete-balanced"))
    generate_coverage_package(
        fixture,
        output_dir=output_dir,
        repo_root=REPO_ROOT,
        generated_at=COVERAGE_FIXED_TIME,
    )
    fixture["criteria"]["observed_metrics"][
        "previously_populated_now_blank_total"
    ] = 1

    with pytest.raises(CoverageContractError, match="immutable"):
        generate_coverage_package(
            fixture,
            output_dir=output_dir,
            repo_root=REPO_ROOT,
            generated_at=COVERAGE_FIXED_TIME,
        )
