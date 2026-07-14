from __future__ import annotations

import copy
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote

from sqlalchemy import create_engine, func, select

from ccld_complaints.connectors.base import SourceDocument
from ccld_complaints.connectors.ccld.facility_reports import CcldFacilityReportsConnector
from ccld_complaints.hosted_app.audit_events import hosted_audit_events
from ccld_complaints.hosted_app.auth import HostedAccessScope
from ccld_complaints.hosted_app.ccld_backfill import (
    CcldHostedBackfillRequest,
    run_ccld_hosted_backfill,
)
from ccld_complaints.hosted_app.ccld_retrieval_jobs import (
    CcldRetrievalConfig,
    CcldRetrievalContext,
    CcldRetrievalRequest,
    run_ccld_retrieval_job,
)
from ccld_complaints.hosted_app.facility_reference_preload import (
    FACILITY_REFERENCE_DATASET_SLUG,
    FACILITY_REFERENCE_DATASET_URL,
    hosted_facility_reference_metadata,
    hosted_facility_reference_records,
)
from ccld_complaints.hosted_app.reviewer_created_state import hosted_reviewer_created_state
from ccld_complaints.hosted_app.reviewer_ui import (
    REVIEWER_UI_DETAIL_PATH,
    local_test_reviewer_actor,
    reviewer_ui_context_for_connection,
    route_reviewer_ui_response,
)
from ccld_complaints.hosted_app.seeded_import import (
    SeededCorpusArtifact,
    hosted_seeded_import_metadata,
    hosted_source_derived_records,
    import_seeded_corpus_artifact,
)
from ccld_complaints.utils.hash import sha256_bytes

RAW_FIXTURE = Path("tests/fixtures/ccld/raw/425802141_inx1_governed_refresh.html")
SOURCE_URL = (
    "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports"
    "?facNum=425802141&inx=1"
)


def test_backfill_dry_run_apply_repeat_and_reviewer_state_preservation(
    tmp_path: Path,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)
    hosted_facility_reference_metadata.create_all(engine)
    initial = _initial_missing_record()

    with engine.connect() as connection:
        import_seeded_corpus_artifact(connection, _artifact("initial", initial))
        _insert_reference(connection)
        complaint_key = "complaint:ccld-complaint-31-CR-20240425094018"
        _insert_reviewer_state_and_audit(connection, complaint_key)
        connection.commit()
        initial_counts = _source_counts(connection)
        initial_identities = _stable_identities(connection)
        initial_state = _reviewer_snapshot(connection)
        initial_traceability = _traceability_snapshot(connection)

        dry_run = run_ccld_hosted_backfill(
            connection,
            CcldHostedBackfillRequest(
                facility_numbers=("425802141",),
                operation="all",
                batch_size=1,
            ),
            now=datetime(2026, 7, 13, tzinfo=UTC),
        )

        assert dry_run.apply_changes is False
        assert dry_run.examined == 1
        assert dry_run.eligible == 1
        assert dry_run.updated == 1
        assert dry_run.failed == 0
        assert _source_counts(connection) == initial_counts
        assert _reviewer_snapshot(connection) == initial_state

        first_apply = run_ccld_hosted_backfill(
            connection,
            CcldHostedBackfillRequest(
                facility_numbers=("425802141",),
                operation="all",
                batch_size=1,
                apply_changes=True,
                checkpoint_file=tmp_path / "checkpoint.json",
            ),
            now=datetime(2026, 7, 13, tzinfo=UTC),
        )
        connection.commit()
        first_apply_counts = _source_counts(connection)
        facility = _entity_values(connection, "facility")
        complaint = _entity_values(connection, "complaint")

        assert first_apply.updated == 1
        assert first_apply.failed == 0
        assert facility["facility_type"] == "Children's Residential Facility"
        assert facility["county"] == "Los Angeles"
        assert facility["status"] == "Licensed"
        assert complaint["visit_date"] == "2025-11-07"
        assert complaint["first_investigation_activity_date"] == "2025-11-07"
        assert complaint["days_received_to_first_activity"] == 561
        assert complaint["missing_first_activity_date"] is False
        assert _stable_identities(connection).issuperset(initial_identities)
        assert _reviewer_snapshot(connection) == initial_state
        assert _traceability_snapshot(connection) == initial_traceability

        repeat_apply = run_ccld_hosted_backfill(
            connection,
            CcldHostedBackfillRequest(
                facility_numbers=("425802141",),
                operation="all",
                batch_size=1,
                apply_changes=True,
            ),
            now=datetime(2026, 7, 14, tzinfo=UTC),
        )
        connection.commit()

        assert repeat_apply.updated == 0
        assert repeat_apply.unchanged == 1
        assert repeat_apply.failed == 0
        assert _source_counts(connection) == first_apply_counts
        assert _reviewer_snapshot(connection) == initial_state

        reviewer_scope = HostedAccessScope("seeded_corpus", "backfill-test-initial")
        status, content_type, body = route_reviewer_ui_response(
            f"{REVIEWER_UI_DETAIL_PATH}?source_record_key={quote(complaint_key)}",
            reviewer_ui_context_for_connection(
                connection,
                actor=local_test_reviewer_actor(scopes=(reviewer_scope,)),
                scope=reviewer_scope,
            ),
        )

    html = body.decode("utf-8")
    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Children&#x27;s Residential Facility" in html
    assert "Los Angeles" in html
    assert "Licensed" in html
    assert "11/07/2025" in html
    assert "561" in html


def test_backfill_checkpoint_resume_and_failed_item_isolation(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)
    hosted_facility_reference_metadata.create_all(engine)
    good = _initial_missing_record()
    bad = copy.deepcopy(good)
    bad_facility = cast(dict[str, Any], bad["facility"])
    bad_document = cast(dict[str, Any], bad["source_document"])
    bad_complaint = cast(dict[str, Any], bad["complaint"])
    bad_facility.update(
        facility_id="ccld-facility-999999999",
        external_facility_number="999999999",
    )
    bad_document.update(
        document_id="ccld-999999999-inx-1",
        facility_id="ccld-facility-999999999",
        raw_path="data/raw/ccld/missing-preserved-artifact.html",
        source_url=SOURCE_URL.replace("425802141", "999999999"),
    )
    bad_complaint.update(
        complaint_id="ccld-complaint-bad-preserved-artifact",
        facility_id="ccld-facility-999999999",
        document_id="ccld-999999999-inx-1",
        complaint_control_number="fixture-bad-preserved-artifact",
    )
    for audit in cast(list[dict[str, Any]], bad["extraction_audit"]):
        audit["audit_id"] = str(audit["audit_id"]).replace(
            "ccld-425802141-inx-1",
            "ccld-999999999-inx-1",
        )
        audit["document_id"] = "ccld-999999999-inx-1"

    with engine.connect() as connection:
        import_seeded_corpus_artifact(connection, _artifact("good", good))
        import_seeded_corpus_artifact(connection, _artifact("bad", bad))
        _insert_reference(connection)
        connection.commit()
        checkpoint = tmp_path / "resume.json"
        result = run_ccld_hosted_backfill(
            connection,
            CcldHostedBackfillRequest(
                facility_numbers=("425802141", "999999999"),
                operation="preserved-artifacts",
                batch_size=1,
                apply_changes=True,
                checkpoint_file=checkpoint,
            ),
        )
        connection.commit()
        good_values = _entity_values(connection, "facility", "ccld-facility-425802141")
        resumed = run_ccld_hosted_backfill(
            connection,
            CcldHostedBackfillRequest(
                facility_numbers=("425802141", "999999999"),
                operation="preserved-artifacts",
                batch_size=1,
                apply_changes=True,
                checkpoint_file=checkpoint,
            ),
        )

    assert result.examined == 2
    assert result.updated == 1
    assert result.failed == 1
    assert good_values["facility_type"] == "733"
    assert resumed.examined == 1
    assert resumed.skipped == 1
    assert resumed.failed == 1


def test_repeated_supported_retrieval_refreshes_existing_rows_without_state_loss(
    tmp_path: Path,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)
    hosted_facility_reference_metadata.create_all(engine)
    initial = _initial_missing_record()
    scope = HostedAccessScope("seeded_corpus", "backfill-test-initial")
    actor = local_test_reviewer_actor(scopes=(scope,))
    client = _GovernedRefreshRetrievalClient()

    with engine.connect() as connection:
        import_seeded_corpus_artifact(connection, _artifact("initial", initial))
        _insert_reference(connection)
        complaint_key = "complaint:ccld-complaint-31-CR-20240425094018"
        _insert_reviewer_state_and_audit(connection, complaint_key)
        connection.commit()
        initial_ids = _stable_identities(connection)
        initial_state = _reviewer_snapshot(connection)
        initial_counts = _source_counts(connection)

        first = run_ccld_retrieval_job(
            _retrieval_context(
                connection,
                tmp_path,
                actor,
                scope,
                client,
                datetime(2026, 7, 13, 12, 0, tzinfo=UTC),
            ),
            CcldRetrievalRequest(
                facility_number="425802141",
                record_type="complaints",
                start_date="2024-04-01",
                end_date="2024-04-30",
            ),
        )
        after_first_counts = _source_counts(connection)
        second = run_ccld_retrieval_job(
            _retrieval_context(
                connection,
                tmp_path,
                actor,
                scope,
                client,
                datetime(2026, 7, 13, 12, 1, tzinfo=UTC),
            ),
            CcldRetrievalRequest(
                facility_number="425802141",
                record_type="complaints",
                start_date="2024-04-01",
                end_date="2024-04-30",
            ),
        )
        facility = _entity_values(connection, "facility")
        complaint = _entity_values(connection, "complaint")

    assert first.job_state == "completed"
    assert second.job_state == "completed"
    assert facility["facility_type"] == "Children's Residential Facility"
    assert facility["county"] == "Los Angeles"
    assert facility["status"] == "Licensed"
    assert complaint["first_investigation_activity_date"] == "2025-11-07"
    assert complaint["days_received_to_first_activity"] == 561
    assert _stable_identity_counts(initial_ids) == _stable_identity_counts(
        _stable_identities_from_engine(engine)
    )
    assert after_first_counts == _source_counts_from_engine(engine)
    assert after_first_counts["facility"] == initial_counts["facility"]
    assert after_first_counts["source_document"] == initial_counts["source_document"]
    assert after_first_counts["complaint"] == initial_counts["complaint"]
    with engine.connect() as connection:
        assert _reviewer_snapshot(connection) == initial_state
    assert len(client.detail_calls) == 2
    assert len(client.report_calls) == 2


def _initial_missing_record() -> dict[str, object]:
    normalized = _normalized_record()
    facility = cast(dict[str, Any], normalized["facility"])
    complaint = cast(dict[str, Any], normalized["complaint"])
    facility.update(facility_type=None, county=None, status=None)
    complaint.update(
        first_investigation_activity_date=None,
        days_received_to_first_activity=None,
        missing_first_activity_date=True,
    )
    return normalized


def _normalized_record() -> dict[str, object]:
    content = RAW_FIXTURE.read_bytes()
    connector = CcldFacilityReportsConnector(facility_number="425802141")
    return connector.normalize(
        connector.extract(
            SourceDocument(
                source_url=SOURCE_URL,
                raw_path=RAW_FIXTURE,
                raw_sha256=sha256_bytes(content),
                retrieved_at="2026-07-13T00:00:00+00:00",
                content_type="text/html",
            )
        )
    )


def _artifact(name: str, record: Mapping[str, Any]) -> SeededCorpusArtifact:
    return SeededCorpusArtifact(
        import_batch_id=f"backfill-test-{name}",
        imported_at="2026-07-13T00:00:00+00:00",
        source_artifact_identity=f"backfill-test:{name}",
        source_pipeline_version="test",
        validation_status="validated",
        raw_hash_validation_status="validated",
        record_counts={},
        warnings=(),
        errors=(),
        records=(copy.deepcopy(record),),
    )


def _insert_reference(connection: Any) -> None:
    connection.execute(
        hosted_facility_reference_records.insert().values(
            source_resource_id="c9df723a-437f-4dcd-be37-ec73ae518bb9",
            facility_number="425802141",
            facility_name="GOVERNED REFRESH FIXTURE FACILITY",
            facility_type="Children's Residential Facility",
            program_type="Residential",
            client_served=None,
            licensee_name=None,
            facility_administrator=None,
            telephone=None,
            address=None,
            city=None,
            state="CA",
            zip=None,
            county="Los Angeles",
            regional_office=None,
            capacity=None,
            status="Licensed",
            license_first_date=None,
            closed_date=None,
            all_visit_dates=None,
            inspection_visit_dates=None,
            other_visit_dates=None,
            snapshot_date="2026-06-07",
            source_resource_name="24-Hour Residential Care for Children",
            source_dataset_slug=FACILITY_REFERENCE_DATASET_SLUG,
            source_dataset_url=FACILITY_REFERENCE_DATASET_URL,
            source_accessed_at="2026-06-07T00:00:00+00:00",
            source_file_name="24HourResidentialCareforChildren06072026.csv",
            original_row_json={"Facility Number": "425802141"},
        )
    )


def _insert_reviewer_state_and_audit(connection: Any, complaint_key: str) -> None:
    connection.execute(
        hosted_reviewer_created_state.insert().values(
            reviewer_state_id="reviewer-state:governed-refresh",
            source_record_key=complaint_key,
            scope_type="seeded_corpus",
            scope_id="seeded-ccld-fixture-2026-06-13",
            state_kind="review_item_state_scaffold",
            state_payload={
                "payload_kind": "reviewer_status_scaffold",
                "reviewer_status": "in_review",
            },
            created_at="2026-07-13T01:00:00+00:00",
            created_by_provider_subject="fixture-reviewer",
            created_by_provider_issuer="fixture-issuer",
            created_by_display_name="Fixture Reviewer",
            created_by_actor_category="tester",
            authorization_permission="reviewer_state_write",
        )
    )
    connection.execute(
        hosted_audit_events.insert().values(
            audit_event_id="audit-event:governed-refresh",
            occurred_at="2026-07-13T01:00:00+00:00",
            actor_provider_subject="fixture-reviewer",
            actor_provider_issuer="fixture-issuer",
            actor_display_name="Fixture Reviewer",
            actor_category="tester",
            authorization_permission="reviewer_state_write",
            scope_type="seeded_corpus",
            scope_id="seeded-ccld-fixture-2026-06-13",
            action="reviewer_created_state_scaffold.create",
            target_type="reviewer_created_state",
            target_reviewer_state_id="reviewer-state:governed-refresh",
            source_record_key=complaint_key,
            source_entity_type="complaint",
            source_stable_source_id="ccld-complaint-31-CR-20240425094018",
            source_document_id="ccld-425802141-inx-1",
            context_metadata={"payload_kind": "reviewer_status_scaffold"},
        )
    )


def _source_counts(connection: Any) -> dict[str, int]:
    return {
        entity: connection.execute(
            select(func.count()).select_from(hosted_source_derived_records).where(
                hosted_source_derived_records.c.entity_type == entity
            )
        ).scalar_one()
        for entity in (
            "facility",
            "source_document",
            "complaint",
            "allegation",
            "event",
            "extraction_audit",
        )
    }


def _stable_identities(connection: Any) -> set[tuple[str, str]]:
    return set(
        connection.execute(
            select(
                hosted_source_derived_records.c.entity_type,
                hosted_source_derived_records.c.stable_source_id,
            )
        ).tuples()
    )


def _reviewer_snapshot(connection: Any) -> tuple[tuple[Any, ...], tuple[Any, ...]]:
    states = tuple(connection.execute(select(hosted_reviewer_created_state)).tuples())
    audits = tuple(connection.execute(select(hosted_audit_events)).tuples())
    return states, audits


def _traceability_snapshot(connection: Any) -> tuple[Any, ...]:
    row = connection.execute(
        select(hosted_source_derived_records).where(
            hosted_source_derived_records.c.entity_type == "source_document"
        )
    ).mappings().one()
    return (
        row["source_url"],
        row["raw_sha256"],
        row["raw_path"],
        row["connector_name"],
        row["connector_version"],
        row["retrieved_at"],
    )


def _entity_values(
    connection: Any,
    entity_type: str,
    stable_source_id: str | None = None,
) -> Mapping[str, Any]:
    statement = select(hosted_source_derived_records.c.original_values).where(
        hosted_source_derived_records.c.entity_type == entity_type
    )
    if stable_source_id is not None:
        statement = statement.where(
            hosted_source_derived_records.c.stable_source_id == stable_source_id
        )
    return cast(Mapping[str, Any], connection.execute(statement).scalar_one())


class _GovernedRefreshRetrievalClient:
    def __init__(self) -> None:
        self.detail_calls: list[str] = []
        self.report_calls: list[str] = []

    def fetch_facility_detail(self, facility_number: str, *, timeout_seconds: int) -> str:
        self.detail_calls.append(facility_number)
        return f"""<!doctype html><html><body>
        <h2>Complaints</h2><p>Complaint Visit Dates:
        <a href="{SOURCE_URL.replace('&', '&amp;')}">04/25/2024</a>
        </p></body></html>"""

    def fetch_report(self, source_url: str, *, timeout_seconds: int) -> bytes:
        self.report_calls.append(source_url)
        return RAW_FIXTURE.read_bytes()


def _retrieval_context(
    connection: Any,
    tmp_path: Path,
    actor: Any,
    scope: HostedAccessScope,
    client: Any,
    now: datetime,
) -> CcldRetrievalContext:
    return CcldRetrievalContext(
        connection=connection,
        actor=actor,
        scope=scope,
        config=CcldRetrievalConfig(
            enabled=True,
            raw_dir=tmp_path / "raw",
            max_date_range_days=90,
            per_job_request_limit=5,
            rate_limit_per_actor=5,
            timeout_seconds=5,
            retry_limit=0,
        ),
        client=client,
        now=lambda: now,
    )


def _stable_identity_counts(values: set[tuple[str, str]]) -> dict[str, int]:
    return {
        entity: len([value for value in values if value[0] == entity])
        for entity in ("facility", "source_document", "complaint", "allegation", "event")
    }


def _stable_identities_from_engine(engine: Any) -> set[tuple[str, str]]:
    with engine.connect() as connection:
        return _stable_identities(connection)


def _source_counts_from_engine(engine: Any) -> dict[str, int]:
    with engine.connect() as connection:
        return _source_counts(connection)
