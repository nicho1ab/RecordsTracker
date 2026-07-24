from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Connection, Engine

from ccld_complaints.hosted_app.ccld_retrieval_jobs import (
    hosted_ccld_retrieval_jobs,
    retrieval_import_batch_id,
)
from ccld_complaints.hosted_app.facility_reference_preload import (
    FACILITY_REFERENCE_DATASET_URL,
    hosted_facility_reference_metadata,
    hosted_facility_reference_records,
)
from ccld_complaints.hosted_app.representative_coverage import (
    build_representative_coverage_report,
)
from ccld_complaints.hosted_app.retrieval_provenance_repair import (
    repair_live_retrieval_provenance,
)
from ccld_complaints.hosted_app.seeded_import import (
    hosted_import_batches,
    hosted_seeded_import_metadata,
    hosted_source_derived_records,
)
from ccld_complaints.hosted_app.source_derived_reads import CCLD_CONNECTOR_NAME

REAL_RESOURCES = {
    "Child Care Center": (
        "7aed8063-cea7-4367-8651-c81643164ae0",
        "Child Care Centers",
        "ChildCareCenters06072026.csv",
    ),
    "Foster Family Agency": (
        "5f5f7124-1a38-4b61-93b9-4e4be3b3b07d",
        "Foster Family Agencies",
        "FosterFamilyAgencies06072026.csv",
    ),
    "Home Care Organization": (
        "b4d78b7f-12df-4b0c-a81a-ff40b949bc75",
        "Home Care Organizations",
        "HomeCareOrganizations06072026.csv",
    ),
}
DEFAULT_BATCH_ID = "representative-coverage-batch"
DEFAULT_JOB_ID = "coverage-job"
DEFAULT_ARTIFACT_IDENTITY = f"ccld-retrieval-job:{DEFAULT_JOB_ID}"
DEFAULT_RETRIEVED_AT = "2026-07-11T12:00:00+00:00"
DEFAULT_RAW_SHA = "a" * 64


def test_empty_database_is_not_ready_and_read_only() -> None:
    engine = _engine()
    with _connection(engine) as connection:
        before_counts = _table_counts(connection)

        report = build_representative_coverage_report(
            connection,
            generated_at=datetime(2026, 7, 11, 12, 0, 0, tzinfo=UTC),
        )

        after_counts = _table_counts(connection)

    assert report["generated_at"] == "2026-07-11T12:00:00+00:00"
    assert report["representative_coverage_status"]["status"] == "not_ready"
    assert report["complaint_coverage_status"]["status"] == "not_ready"
    assert report["facility_reference_coverage_status"]["status"] == "not_ready"
    assert report["facility_reference"]["current_hosted_row_count"] == 0
    assert report["complaints"]["current_hosted_row_count"] == 0
    assert before_counts == after_counts == {
        "facility_reference": 0,
        "source_derived": 0,
        "import_batches": 0,
        "retrieval_jobs": 0,
    }


def test_fixture_only_rows_are_classified_and_not_representative() -> None:
    with _connection(_engine()) as connection:
        _insert_import_batch(
            connection,
            source_artifact_identity="tests/fixtures/hosted_seeded_corpus.json",
            source_pipeline_version="fixture-pipeline-output-0.1.0",
        )
        _insert_retrieval_job(
            connection,
            source_artifact_identity="tests/fixtures/hosted_seeded_corpus.json",
            safe_message="Controlled CCLD retrieval (fixture/mock mode): imported records.",
        )
        _insert_facility_reference(
            connection,
            facility_number="111111111",
            facility_type="Child Care Center",
            source_resource_id="fixture-child-care",
            source_resource_name="Tiny fixture child care centers",
            source_dataset_url="tests/fixtures/public_source_facilities",
        )
        _insert_source_document(connection, facility_number="111111111", report_index="1")
        _insert_complaint(connection, facility_number="111111111", report_index="1")

        report = build_representative_coverage_report(connection)

    assert report["representative_coverage_status"]["status"] == "not_ready"
    assert report["facility_reference"]["provenance_counts"]["fixture_demo_test"] == 1
    assert report["complaints"]["provenance_counts"]["fixture_demo_test"] == 1
    assert report["facility_reference"]["eligible_representative_row_count"] == 0
    assert report["complaints"]["eligible_representative_complaint_count"] == 0
    assert report["complaint_coverage_status"]["warnings"] == (
        "fixture/demo/test complaint rows are loaded but excluded from representative counts",
    )
    assert report["facility_reference_coverage_status"]["warnings"] == (
        "fixture/demo/test facility-reference rows are loaded but excluded from "
        "representative counts",
    )


def test_fixture_mock_retrieval_rows_are_excluded_from_representative_counts() -> None:
    with _connection(_engine()) as connection:
        _insert_real_facilities(connection)
        _insert_live_batch_and_job(
            connection,
            source_artifact_identity="ccld-retrieval-job:fixture-demo-job",
            retrieval_job_id="fixture-demo-job",
            safe_message="Controlled CCLD retrieval (fixture/mock mode): imported records.",
        )
        _insert_source_document(
            connection,
            facility_number="111111111",
            report_index="1",
            source_artifact_identity="ccld-retrieval-job:fixture-demo-job",
        )
        _insert_complaint(
            connection,
            facility_number="111111111",
            report_index="1",
            source_artifact_identity="ccld-retrieval-job:fixture-demo-job",
        )

        report = build_representative_coverage_report(connection)

    assert report["representative_coverage_status"]["status"] == "partial"
    assert report["complaints"]["provenance_counts"]["fixture_demo_test"] == 1
    assert report["complaints"]["eligible_representative_complaint_count"] == 0


def test_unknown_provenance_is_not_candidate_even_with_real_facilities() -> None:
    with _connection(_engine()) as connection:
        _insert_real_facilities(connection)
        _insert_import_batch(
            connection,
            source_artifact_identity="local-artifact-without-retrieval-job",
            source_pipeline_version="local-validated-output",
        )
        _insert_source_document(connection, facility_number="111111111", report_index="1")
        _insert_complaint(connection, facility_number="111111111", report_index="1")

        report = build_representative_coverage_report(connection)

    assert report["representative_coverage_status"]["status"] == "partial"
    assert report["complaints"]["provenance_counts"]["unknown"] == 1
    assert report["complaints"]["eligible_representative_complaint_count"] == 0
    assert report["complaint_coverage_status"]["status"] == "not_ready"
    assert "some loaded complaint rows have unknown provenance" in report[
        "complaint_coverage_status"
    ]["blockers"]
    assert "some loaded rows have unknown provenance" in report[
        "representative_coverage_status"
    ]["blockers"]


def test_mixed_fixture_and_live_imports_count_only_live_complaints() -> None:
    live_batch_id = retrieval_import_batch_id(DEFAULT_JOB_ID)
    fixture_batch_id = "seeded-ccld-fixture-2026-06-13"
    fixture_artifact_identity = "tests/fixtures/hosted_seeded_corpus.json"
    with _connection(_engine()) as connection:
        _insert_real_facilities(connection)
        _insert_import_batch(
            connection,
            import_batch_id=fixture_batch_id,
            source_artifact_identity=fixture_artifact_identity,
            source_pipeline_version="fixture-pipeline-output-0.1.0",
            record_counts={"source_document": 1, "complaint": 1},
        )
        _insert_live_batch_and_job(
            connection,
            import_batch_id=live_batch_id,
            record_counts={"source_document": 1, "complaint": 1},
        )
        _insert_source_document(
            connection,
            facility_number="111111111",
            report_index="1",
            import_batch_id=live_batch_id,
        )
        _insert_complaint(
            connection,
            facility_number="111111111",
            report_index="1",
            import_batch_id=live_batch_id,
        )
        _insert_source_document(
            connection,
            facility_number="111111111",
            report_index="2",
            import_batch_id=fixture_batch_id,
            source_artifact_identity=fixture_artifact_identity,
        )
        _insert_complaint(
            connection,
            facility_number="111111111",
            report_index="2",
            import_batch_id=fixture_batch_id,
            source_artifact_identity=fixture_artifact_identity,
        )

        report = build_representative_coverage_report(connection)

    assert report["complaints"]["current_hosted_row_count"] == 2
    assert report["complaints"]["provenance_counts"] == {
        "real_public_source": 1,
        "fixture_demo_test": 1,
        "unknown": 0,
    }
    assert report["complaints"]["eligible_representative_complaint_count"] == 1


def test_real_public_facilities_and_traceable_complaint_are_candidate() -> None:
    with _connection(_engine()) as connection:
        _insert_real_facilities(connection)
        _insert_live_batch_and_job(connection)
        _insert_source_document(connection, facility_number="111111111", report_index="1")
        _insert_complaint(connection, facility_number="111111111", report_index="1")

        report = build_representative_coverage_report(connection)

    assert report["representative_coverage_status"]["status"] == "candidate"
    assert report["complaint_coverage_status"]["status"] == "candidate"
    assert report["facility_reference_coverage_status"]["status"] == "candidate"
    assert "validated_status_rule" in report["representative_coverage_status"]
    assert "does not mark complaint coverage as validated" in report[
        "complaint_coverage_status"
    ]["validated_status_rule"]
    assert "does not mark facility-reference coverage as validated" in report[
        "facility_reference_coverage_status"
    ]["validated_status_rule"]
    assert report["facility_reference"]["eligible_distinct_facility_number_count"] == 2
    assert report["facility_reference"]["eligible_facility_type_count"] == 2
    assert report["complaints"]["eligible_representative_complaint_count"] == 1
    assert report["complaints"]["eligible_traceability_complete_complaint_count"] == 1
    assert report["complaints"]["source_document_linkage"]["exact_match_count"] == 1
    assert report["complaints"]["source_document_linked_complaint_count"] == 1
    assert "displayable_row_count" not in report["complaints"]


def test_complaint_candidate_is_separate_from_unknown_facility_provenance() -> None:
    with _connection(_engine()) as connection:
        _insert_real_facilities(connection)
        _insert_facility_reference(
            connection,
            facility_number="333333333",
            facility_type="Child Care Center",
            source_resource_id="unverified-facility-resource",
            source_resource_name="Unverified facility reference",
            source_dataset_url="https://example.invalid/facilities",
        )
        _insert_live_batch_and_job(connection)
        _insert_source_document(connection, facility_number="111111111", report_index="1")
        _insert_complaint(connection, facility_number="111111111", report_index="1")

        report = build_representative_coverage_report(connection)

    assert report["complaint_coverage_status"]["status"] == "candidate"
    assert report["facility_reference_coverage_status"]["status"] == "partial"
    assert "some loaded facility-reference rows have unknown provenance" in report[
        "facility_reference_coverage_status"
    ]["blockers"]
    assert report["representative_coverage_status"]["status"] == "partial"
    assert "some loaded rows have unknown provenance" in report[
        "representative_coverage_status"
    ]["blockers"]


def test_facility_threshold_gap_is_separate_from_complaint_candidate() -> None:
    with _connection(_engine()) as connection:
        _insert_facility_reference(
            connection,
            facility_number="111111111",
            facility_type="Child Care Center",
        )
        _insert_live_batch_and_job(connection)
        _insert_source_document(connection, facility_number="111111111", report_index="1")
        _insert_complaint(connection, facility_number="111111111", report_index="1")

        report = build_representative_coverage_report(connection)

    assert report["complaint_coverage_status"]["status"] == "candidate"
    assert report["facility_reference_coverage_status"]["status"] == "partial"
    assert report["facility_reference_coverage_status"]["blockers"] == (
        "fewer real/public-source facilities than the configured threshold",
        "fewer real/public-source facility types than the configured threshold",
    )
    assert report["representative_coverage_status"]["status"] == "partial"


def test_repair_live_retrieval_provenance_relinks_reused_fixture_batch() -> None:
    reused_fixture_batch_id = "seeded-ccld-fixture-2026-06-13"
    target_batch_id = retrieval_import_batch_id(DEFAULT_JOB_ID)
    with _connection(_engine()) as connection:
        _insert_real_facilities(connection)
        _insert_import_batch(
            connection,
            import_batch_id=reused_fixture_batch_id,
            source_artifact_identity="tests/fixtures/hosted_seeded_corpus.json",
            source_pipeline_version="fixture-pipeline-output-0.1.0",
            record_counts={"source_document": 1, "complaint": 1},
        )
        _insert_retrieval_job(connection)
        _insert_source_document(
            connection,
            facility_number="111111111",
            report_index="1",
            import_batch_id=reused_fixture_batch_id,
        )
        _insert_complaint(
            connection,
            facility_number="111111111",
            report_index="1",
            import_batch_id=reused_fixture_batch_id,
        )

        before_report = build_representative_coverage_report(connection)
        dry_run = repair_live_retrieval_provenance(connection)
        after_dry_run_report = build_representative_coverage_report(connection)
        applied = repair_live_retrieval_provenance(connection, dry_run=False)
        repaired_rows = connection.execute(
            select(hosted_source_derived_records.c.import_batch_id)
            .where(hosted_source_derived_records.c.import_batch_id == target_batch_id)
        ).all()
        after_report = build_representative_coverage_report(connection)
        second_apply = repair_live_retrieval_provenance(connection, dry_run=False)

    assert before_report["complaints"]["provenance_counts"]["fixture_demo_test"] == 1
    assert before_report["complaints"]["eligible_representative_complaint_count"] == 0
    assert dry_run.candidate_source_record_count == 2
    assert dry_run.repaired_source_record_count == 0
    assert after_dry_run_report == before_report
    assert applied.candidate_source_record_count == 2
    assert applied.repaired_source_record_count == 2
    assert applied.inserted_import_batch_count == 1
    assert applied.repaired_import_batch_ids == (target_batch_id,)
    assert len(repaired_rows) == 2
    assert after_report["complaints"]["provenance_counts"]["real_public_source"] == 1
    assert after_report["complaints"]["eligible_representative_complaint_count"] == 1
    assert second_apply.candidate_source_record_count == 0
    assert second_apply.repaired_source_record_count == 0


def test_incomplete_complaint_traceability_keeps_real_rows_partial() -> None:
    with _connection(_engine()) as connection:
        _insert_real_facilities(connection)
        _insert_live_batch_and_job(connection)
        _insert_source_document(connection, facility_number="111111111", report_index="1")
        _insert_complaint(
            connection,
            facility_number="111111111",
            report_index="1",
            raw_sha256="",
        )

        report = build_representative_coverage_report(connection)

    assert report["representative_coverage_status"]["status"] == "partial"
    assert report["complaints"]["traceability_complete_complaint_count"] == 0
    assert report["complaints"]["traceability_incomplete_complaint_count"] == 1
    assert report["complaint_coverage_status"]["status"] == "partial"
    assert "not all eligible real/public-source complaints are traceability-complete" in report[
        "representative_coverage_status"
    ]["blockers"]


def test_missing_source_document_link_blocks_candidate() -> None:
    with _connection(_engine()) as connection:
        _insert_real_facilities(connection)
        _insert_live_batch_and_job(connection)
        _insert_complaint(connection, facility_number="111111111", report_index="1")

        report = build_representative_coverage_report(connection)

    linkage = report["complaints"]["source_document_linkage"]
    assert report["representative_coverage_status"]["status"] == "partial"
    assert linkage["missing_link_count"] == 1
    assert linkage["linked_count"] == 0
    assert report["complaint_coverage_status"]["status"] == "partial"
    assert "source-document linkage is missing or conflicting" in report[
        "complaint_coverage_status"
    ]["blockers"]
    assert "source-document linkage is missing or conflicting" in report[
        "representative_coverage_status"
    ]["blockers"]


def test_conflicting_source_document_fields_are_reported() -> None:
    with _connection(_engine()) as connection:
        _insert_real_facilities(connection)
        _insert_live_batch_and_job(connection)
        _insert_source_document(
            connection,
            facility_number="111111111",
            report_index="1",
            source_url="https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports"
            "?facNum=111111111&inx=conflicting",
            raw_sha256="b" * 64,
        )
        _insert_complaint(connection, facility_number="111111111", report_index="1")

        report = build_representative_coverage_report(connection)

    linkage = report["complaints"]["source_document_linkage"]
    assert report["representative_coverage_status"]["status"] == "partial"
    assert linkage["conflicting_link_count"] == 1
    assert linkage["conflicting_field_counts"] == {
        "raw_sha256": 1,
        "source_url": 1,
    }
    assert report["complaint_coverage_status"]["status"] == "partial"
    assert "source-document linkage is missing or conflicting" in report[
        "complaint_coverage_status"
    ]["blockers"]


def test_duplicate_stable_identities_are_reported_when_database_contains_them() -> None:
    engine = _engine_without_source_identity_constraint()
    with _connection(engine) as connection:
        _insert_real_facilities(connection)
        _insert_live_batch_and_job(connection, record_counts={"source_document": 1, "complaint": 2})
        _insert_source_document(connection, facility_number="111111111", report_index="1")
        _insert_complaint(
            connection,
            facility_number="111111111",
            report_index="1",
            source_record_key="complaint:duplicate:one",
            stable_source_id="complaint:duplicate",
        )
        _insert_complaint(
            connection,
            facility_number="111111111",
            report_index="1",
            source_record_key="complaint:duplicate:two",
            stable_source_id="complaint:duplicate",
        )

        report = build_representative_coverage_report(connection)

    assert report["representative_coverage_status"]["status"] == "partial"
    assert report["complaints"]["duplicate_stable_identity_rows"] == 1
    assert report["complaint_coverage_status"]["status"] == "partial"
    assert "duplicate source-derived stable identities are present" in report[
        "complaint_coverage_status"
    ]["blockers"]
    assert "duplicate source-derived stable identities are present" in report[
        "representative_coverage_status"
    ]["blockers"]


def test_retrieval_failures_are_not_counted_as_validation_rejections() -> None:
    with _connection(_engine()) as connection:
        _insert_live_batch_and_job(
            connection,
            result_counts={
                "imported_source_derived_records": 1,
                "report_failures": 2,
                "validation_rejections": 1,
                "skipped_records": 3,
                "duplicate_source_records": 4,
            },
        )

        report = build_representative_coverage_report(connection)

    retrieval = report["reconciliation"]["retrieval_jobs"]
    assert retrieval["reported_imported_source_derived_record_count"] == 1
    assert retrieval["reported_retrieval_failure_count"] == 2
    assert retrieval["reported_validation_rejection_count"] == 1
    assert retrieval["reported_skipped_record_count"] == 3
    assert retrieval["reported_duplicate_or_idempotent_record_count"] == 4


def test_import_batch_reconciliation_reports_declared_minus_current_counts() -> None:
    with _connection(_engine()) as connection:
        _insert_real_facilities(connection)
        _insert_live_batch_and_job(
            connection,
            record_counts={"source_document": 1, "complaint": 2},
        )
        _insert_source_document(connection, facility_number="111111111", report_index="1")
        _insert_complaint(connection, facility_number="111111111", report_index="1")

        report = build_representative_coverage_report(connection)

    batch_summary = report["reconciliation"]["import_batches"][0]
    assert batch_summary["declared_record_counts"] == {
        "complaint": 2,
        "source_document": 1,
    }
    assert batch_summary["current_persisted_record_counts"] == {
        "complaint": 1,
        "source_document": 1,
    }
    assert batch_summary["declared_minus_current_differences"] == {"complaint": 1}
    assert report["reconciliation"]["unresolved_differences"] == (
        "Import batch representative-coverage-batch declared counts differ from current "
        "persisted rows: {'complaint': 1}",
    )


def test_report_ordering_is_deterministic() -> None:
    with _connection(_engine()) as connection:
        _insert_real_facilities(connection, reversed_order=True)
        _insert_live_batch_and_job(connection)
        _insert_source_document(connection, facility_number="111111111", report_index="1")
        _insert_complaint(connection, facility_number="111111111", report_index="1")

        first = build_representative_coverage_report(
            connection,
            generated_at=datetime(2026, 7, 11, 12, 0, 0, tzinfo=UTC),
        )
        second = build_representative_coverage_report(
            connection,
            generated_at=datetime(2026, 7, 11, 12, 0, 0, tzinfo=UTC),
        )

    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["complaint_coverage_status"] == second["complaint_coverage_status"]
    assert first["facility_reference_coverage_status"] == second[
        "facility_reference_coverage_status"
    ]
    assert [item["facility_type"] for item in first["facility_reference"]["facility_types"]] == [
        "Child Care Center",
        "Foster Family Agency",
    ]
    assert [
        item["source_resource_name"] for item in first["facility_reference"]["source_files"]
    ] == ["Foster Family Agencies", "Child Care Centers"]


def _engine() -> Engine:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)
    hosted_facility_reference_metadata.create_all(engine)
    return engine


def _engine_without_source_identity_constraint() -> Engine:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_import_batches.create(engine)
    hosted_ccld_retrieval_jobs.create(engine)
    hosted_facility_reference_metadata.create_all(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE hosted_source_derived_records (
                source_record_key VARCHAR(160) NOT NULL PRIMARY KEY,
                entity_type VARCHAR(32) NOT NULL,
                stable_source_id TEXT NOT NULL,
                import_batch_id VARCHAR(96),
                source_document_id TEXT NOT NULL,
                facility_id TEXT,
                source_url TEXT NOT NULL,
                raw_sha256 VARCHAR(64) NOT NULL,
                raw_path TEXT,
                connector_name TEXT NOT NULL,
                connector_version TEXT NOT NULL,
                retrieved_at VARCHAR(40) NOT NULL,
                agency_name TEXT,
                deficiency_texts JSON,
                investigation_findings_narrative TEXT,
                complaint_report_contact TEXT,
                original_values JSON NOT NULL,
                source_traceability JSON NOT NULL
            )
            """
        )
    return engine


def _connection(engine: Engine) -> Connection:
    return engine.connect()


def _table_counts(connection: Connection) -> dict[str, int]:
    return {
        "facility_reference": connection.execute(
            select(func.count()).select_from(hosted_facility_reference_records)
        ).scalar_one(),
        "source_derived": connection.execute(
            select(func.count()).select_from(hosted_source_derived_records)
        ).scalar_one(),
        "import_batches": connection.execute(
            select(func.count()).select_from(hosted_import_batches)
        ).scalar_one(),
        "retrieval_jobs": connection.execute(
            select(func.count()).select_from(hosted_ccld_retrieval_jobs)
        ).scalar_one(),
    }


def _insert_real_facilities(
    connection: Connection,
    *,
    reversed_order: bool = False,
) -> None:
    rows = (
        ("111111111", "Child Care Center"),
        ("222222222", "Foster Family Agency"),
    )
    if reversed_order:
        rows = tuple(reversed(rows))
    for facility_number, facility_type in rows:
        _insert_facility_reference(
            connection,
            facility_number=facility_number,
            facility_type=facility_type,
        )


def _insert_live_batch_and_job(
    connection: Connection,
    *,
    import_batch_id: str = DEFAULT_BATCH_ID,
    source_artifact_identity: str = DEFAULT_ARTIFACT_IDENTITY,
    retrieval_job_id: str = DEFAULT_JOB_ID,
    safe_message: str = (
        "Controlled CCLD retrieval (live public CCLD mode): imported records."
    ),
    record_counts: dict[str, int] | None = None,
    result_counts: dict[str, int] | None = None,
) -> None:
    _insert_import_batch(
        connection,
        import_batch_id=import_batch_id,
        source_artifact_identity=source_artifact_identity,
        record_counts=record_counts,
    )
    _insert_retrieval_job(
        connection,
        retrieval_job_id=retrieval_job_id,
        source_artifact_identity=source_artifact_identity,
        safe_message=safe_message,
        result_counts=result_counts,
    )


def _insert_import_batch(
    connection: Connection,
    *,
    import_batch_id: str = DEFAULT_BATCH_ID,
    source_artifact_identity: str = DEFAULT_ARTIFACT_IDENTITY,
    source_pipeline_version: str = "ccld-controlled-retrieval-job-0.1.0",
    record_counts: dict[str, int] | None = None,
) -> None:
    connection.execute(
        hosted_import_batches.insert().values(
            import_batch_id=import_batch_id,
            imported_at=DEFAULT_RETRIEVED_AT,
            source_artifact_identity=source_artifact_identity,
            source_pipeline_version=source_pipeline_version,
            validation_status="validated",
            raw_hash_validation_status="validated",
            record_counts=record_counts or {"source_document": 1, "complaint": 1},
            warnings=[],
            errors=[],
        )
    )


def _insert_retrieval_job(
    connection: Connection,
    *,
    retrieval_job_id: str = DEFAULT_JOB_ID,
    source_artifact_identity: str = DEFAULT_ARTIFACT_IDENTITY,
    safe_message: str = (
        "Controlled CCLD retrieval (live public CCLD mode): imported records."
    ),
    result_counts: dict[str, int] | None = None,
) -> None:
    connection.execute(
        hosted_ccld_retrieval_jobs.insert().values(
            retrieval_job_id=retrieval_job_id,
            created_at=DEFAULT_RETRIEVED_AT,
            updated_at=DEFAULT_RETRIEVED_AT,
            job_state="completed",
            facility_number="111111111",
            record_type="complaints",
            start_date="2026-06-01",
            end_date="2026-06-30",
            source_scope_type="corpus",
            source_scope_id=DEFAULT_BATCH_ID,
            actor_provider_subject="fixture-reviewer",
            actor_provider_issuer="fixture-provider",
            actor_display_name="Fixture Reviewer",
            actor_category="tester",
            authorization_permission="retrieval_job_trigger",
            request_limit="5",
            retry_limit="0",
            timeout_seconds="5",
            raw_storage_path="raw",
            source_artifact_identity=source_artifact_identity,
            result_counts=result_counts
            or {
                "retrieved_record_bundles": 1,
                "imported_source_derived_records": 2,
                "report_failures": 0,
            },
            warnings=[],
            errors=[],
            safe_message=safe_message,
            data_mutations_performed=True,
        )
    )


def _insert_facility_reference(
    connection: Connection,
    *,
    facility_number: str,
    facility_type: str,
    source_resource_id: str | None = None,
    source_resource_name: str | None = None,
    source_file_name: str | None = None,
    source_dataset_url: str = FACILITY_REFERENCE_DATASET_URL,
) -> None:
    default_resource_id, default_resource_name, default_file_name = REAL_RESOURCES[
        facility_type
    ]
    connection.execute(
        hosted_facility_reference_records.insert().values(
            source_resource_id=source_resource_id or default_resource_id,
            facility_number=facility_number,
            facility_name=f"Facility {facility_number}",
            facility_type=facility_type,
            program_type=None,
            licensee_name=f"Licensee {facility_number}",
            facility_administrator=None,
            telephone=None,
            address=None,
            city="Sacramento",
            state="CA",
            zip="95814",
            county="Sacramento",
            regional_office=None,
            capacity=12,
            status="Licensed",
            license_first_date=None,
            closed_date=None,
            snapshot_date="2026-06-07",
            source_resource_name=source_resource_name or default_resource_name,
            source_dataset_slug="ccl-facilities",
            source_dataset_url=source_dataset_url,
            source_accessed_at="2026-07-01T12:00:00+00:00",
            source_file_name=source_file_name or default_file_name,
            original_row_json={"Facility Number": facility_number},
        )
    )


def _insert_source_document(
    connection: Connection,
    *,
    facility_number: str,
    report_index: str,
    source_url: str | None = None,
    raw_sha256: str = DEFAULT_RAW_SHA,
    import_batch_id: str = DEFAULT_BATCH_ID,
    source_artifact_identity: str = DEFAULT_ARTIFACT_IDENTITY,
) -> None:
    connection.execute(
        hosted_source_derived_records.insert().values(
            **_source_record_values(
                entity_type="source_document",
                stable_source_id=f"source-document:{facility_number}:{report_index}",
                source_document_id=f"source-document:{facility_number}:{report_index}",
                facility_id=f"facility:{facility_number}",
                facility_number=facility_number,
                report_index=report_index,
                source_url=source_url,
                raw_sha256=raw_sha256,
                import_batch_id=import_batch_id,
                source_artifact_identity=source_artifact_identity,
                original_values={
                    "document_id": f"source-document:{facility_number}:{report_index}",
                    "facility_id": f"facility:{facility_number}",
                    "source_url": source_url or _source_url(facility_number, report_index),
                    "raw_sha256": raw_sha256,
                    "connector_name": CCLD_CONNECTOR_NAME,
                    "connector_version": "test",
                    "retrieved_at": DEFAULT_RETRIEVED_AT,
                },
            )
        )
    )


def _insert_complaint(
    connection: Connection,
    *,
    facility_number: str,
    report_index: str,
    source_record_key: str | None = None,
    stable_source_id: str | None = None,
    source_url: str | None = None,
    raw_sha256: str = DEFAULT_RAW_SHA,
    import_batch_id: str = DEFAULT_BATCH_ID,
    source_artifact_identity: str = DEFAULT_ARTIFACT_IDENTITY,
) -> None:
    stable_id = stable_source_id or f"complaint:{facility_number}:{report_index}"
    values = _source_record_values(
        entity_type="complaint",
        stable_source_id=stable_id,
        source_document_id=f"source-document:{facility_number}:{report_index}",
        facility_id=f"facility:{facility_number}",
        facility_number=facility_number,
        report_index=report_index,
        source_url=source_url,
        raw_sha256=raw_sha256,
        import_batch_id=import_batch_id,
        source_artifact_identity=source_artifact_identity,
        original_values={
            "complaint_id": stable_id,
            "facility_id": f"facility:{facility_number}",
            "external_facility_number": facility_number,
            "document_id": f"source-document:{facility_number}:{report_index}",
            "complaint_received_date": "2026-06-01",
        },
    )
    if source_record_key is not None:
        values["source_record_key"] = source_record_key
    connection.execute(hosted_source_derived_records.insert().values(**values))


def _source_record_values(
    *,
    entity_type: str,
    stable_source_id: str,
    source_document_id: str,
    facility_id: str,
    facility_number: str,
    report_index: str,
    original_values: dict[str, Any],
    source_url: str | None = None,
    raw_sha256: str = DEFAULT_RAW_SHA,
    import_batch_id: str = DEFAULT_BATCH_ID,
    source_artifact_identity: str = DEFAULT_ARTIFACT_IDENTITY,
) -> dict[str, Any]:
    resolved_url = source_url or _source_url(facility_number, report_index)
    return {
        "source_record_key": f"{entity_type}:{stable_source_id}",
        "entity_type": entity_type,
        "stable_source_id": stable_source_id,
        "import_batch_id": import_batch_id,
        "source_document_id": source_document_id,
        "facility_id": facility_id,
        "source_url": resolved_url,
        "raw_sha256": raw_sha256,
        "raw_path": "ccld/raw.html",
        "connector_name": CCLD_CONNECTOR_NAME,
        "connector_version": "test",
        "retrieved_at": DEFAULT_RETRIEVED_AT,
        "original_values": original_values,
        "source_traceability": {
            "source_document_id": source_document_id,
            "source_url": resolved_url,
            "raw_sha256": raw_sha256,
            "connector_name": CCLD_CONNECTOR_NAME,
            "connector_version": "test",
            "retrieved_at": DEFAULT_RETRIEVED_AT,
            "source_artifact_identity": source_artifact_identity,
        },
    }


def _source_url(facility_number: str, report_index: str) -> str:
    return (
        "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports"
        f"?facNum={facility_number}&inx={report_index}"
    )
