from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote

import pytest
from sqlalchemy import create_engine, func, select

from ccld_complaints.connectors.base import SourceDocument
from ccld_complaints.connectors.ccld.facility_reports import CcldFacilityReportsConnector
from ccld_complaints.hosted_app import ccld_backfill
from ccld_complaints.hosted_app.audit_events import hosted_audit_events
from ccld_complaints.hosted_app.auth import HostedAccessScope
from ccld_complaints.hosted_app.ccld_backfill import (
    CcldHostedBackfillRequest,
    _deduplicate_facility_projections,
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
    hosted_import_batches,
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


def test_apply_requires_explicit_bound_and_durable_checkpoint(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)
    with engine.connect() as connection:
        with pytest.raises(ValueError, match="durable checkpoint"):
            run_ccld_hosted_backfill(
                connection,
                CcldHostedBackfillRequest(
                    facility_numbers=("425802141",),
                    apply_changes=True,
                    max_facilities=1,
                ),
            )
        with pytest.raises(ValueError, match="explicit max_facilities"):
            run_ccld_hosted_backfill(
                connection,
                CcldHostedBackfillRequest(
                    facility_numbers=("425802141",),
                    apply_changes=True,
                    checkpoint_file=tmp_path / "checkpoint.json",
                ),
            )
        with pytest.raises(ValueError, match="approved facility-reference"):
            run_ccld_hosted_backfill(
                connection,
                CcldHostedBackfillRequest(
                    facility_numbers=("425802141",),
                    operation="preserved-artifacts",
                    apply_changes=True,
                    checkpoint_file=tmp_path / "checkpoint.json",
                    max_facilities=1,
                ),
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
        initial_complaint = _entity_values(connection, "complaint")

        dry_run = run_ccld_hosted_backfill(
            connection,
            CcldHostedBackfillRequest(
                facility_numbers=("425802141",),
                operation="facility-reference",
                batch_size=1,
            ),
            now=datetime(2026, 7, 13, tzinfo=UTC),
        )

        assert dry_run.apply_changes is False
        assert dry_run.candidates == 1
        assert dry_run.excluded == 0
        assert dry_run.examined == 1
        assert dry_run.eligible == 1
        assert dry_run.intended_updates == 1
        assert dry_run.updated == 1
        assert dry_run.failed == 0
        assert _source_counts(connection) == initial_counts
        assert _reviewer_snapshot(connection) == initial_state

        first_apply = run_ccld_hosted_backfill(
            connection,
            CcldHostedBackfillRequest(
                facility_numbers=("425802141",),
                operation="facility-reference",
                batch_size=1,
                apply_changes=True,
                checkpoint_file=tmp_path / "checkpoint.json",
                max_facilities=1,
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
        assert complaint == initial_complaint
        assert _stable_identities(connection).issuperset(initial_identities)
        assert _reviewer_snapshot(connection) == initial_state
        assert _traceability_snapshot(connection) == initial_traceability

        repeat_apply = run_ccld_hosted_backfill(
            connection,
            CcldHostedBackfillRequest(
                facility_numbers=("425802141",),
                operation="facility-reference",
                batch_size=1,
                apply_changes=True,
                checkpoint_file=tmp_path / "checkpoint.json",
                restart=True,
                max_facilities=1,
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


def test_backfill_checkpoint_resume_and_failed_item_isolation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
        _insert_reference(connection, facility_number="999999999")
        connection.commit()
        real_process = ccld_backfill._process_facility

        def fail_selected_facility(
            process_connection: Any,
            facility_number: str,
            facility_row: Mapping[str, Any],
            **kwargs: Any,
        ) -> Mapping[str, int | bool]:
            if facility_number == "999999999":
                raise ValueError("controlled test failure")
            return real_process(
                process_connection,
                facility_number,
                facility_row,
                **kwargs,
            )

        monkeypatch.setattr(
            ccld_backfill,
            "_process_facility",
            fail_selected_facility,
        )
        checkpoint = tmp_path / "resume.json"
        result = run_ccld_hosted_backfill(
            connection,
            CcldHostedBackfillRequest(
                facility_numbers=("425802141", "999999999"),
                operation="facility-reference",
                batch_size=1,
                apply_changes=True,
                checkpoint_file=checkpoint,
                max_facilities=2,
            ),
        )
        connection.commit()
        good_values = _entity_values(connection, "facility", "ccld-facility-425802141")
        resumed = run_ccld_hosted_backfill(
            connection,
            CcldHostedBackfillRequest(
                facility_numbers=("425802141", "999999999"),
                operation="facility-reference",
                batch_size=1,
                apply_changes=True,
                checkpoint_file=checkpoint,
                max_facilities=2,
            ),
        )

    assert result.examined == 2
    assert result.updated == 1
    assert result.failed == 1
    assert good_values["facility_type"] == "Children's Residential Facility"
    assert resumed.examined == 1
    assert resumed.skipped == 1
    assert resumed.failed == 1
    checkpoint_payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert checkpoint_payload["version"] == 2
    assert checkpoint_payload["completed_facility_numbers"] == ["425802141"]
    assert checkpoint_payload["failed_attempts"] == {"999999999": 2}


def test_bounded_checkpoint_resume_finishes_frozen_selection_idempotently(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)
    hosted_facility_reference_metadata.create_all(engine)
    with engine.connect() as connection:
        import_seeded_corpus_artifact(
            connection,
            _artifact("bounded-resume", _initial_missing_record()),
        )
        template = dict(
            connection.execute(
                select(hosted_source_derived_records).where(
                    hosted_source_derived_records.c.entity_type == "facility"
                )
            ).mappings().one()
        )
        second = dict(template)
        second.update(
            source_record_key="facility:ccld-facility-425802142",
            stable_source_id="ccld-facility-425802142",
            facility_id="ccld-facility-425802142",
            original_values={
                **cast(Mapping[str, Any], template["original_values"]),
                "facility_id": "ccld-facility-425802142",
                "external_facility_number": "425802142",
            },
        )
        connection.execute(hosted_source_derived_records.insert().values(**second))
        _insert_reference(connection)
        _insert_reference(connection, facility_number="425802142")
        connection.commit()

        processed: list[str] = []

        def fake_process(
            _connection: Any,
            facility_number: str,
            _facility_row: Mapping[str, Any],
            **_kwargs: Any,
        ) -> Mapping[str, int | bool]:
            processed.append(facility_number)
            return {
                "eligible": True,
                "updated": 1,
                "unchanged": 0,
                "skipped": 0,
                "conflicted": 0,
                "warnings": 0,
            }

        monkeypatch.setattr(ccld_backfill, "_process_facility", fake_process)
        checkpoint = tmp_path / "bounded-resume.json"
        request = CcldHostedBackfillRequest(
            facility_numbers=("425802141", "425802142"),
            operation="facility-reference",
            apply_changes=True,
            checkpoint_file=checkpoint,
            max_facilities=1,
        )

        first = run_ccld_hosted_backfill(connection, request)
        second_run = run_ccld_hosted_backfill(connection, request)
        repeat = run_ccld_hosted_backfill(connection, request)

    assert first.candidates == 2
    assert first.examined == 1
    assert first.excluded == 1
    assert second_run.examined == 1
    assert second_run.excluded == 0
    assert repeat.examined == 0
    assert repeat.skipped == 2
    assert processed == ["425802141", "425802142"]
    checkpoint_payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert checkpoint_payload["selected_facility_numbers"] == [
        "425802141",
        "425802142",
    ]
    assert checkpoint_payload["completed_facility_numbers"] == [
        "425802141",
        "425802142",
    ]


def test_preserved_artifact_dry_run_is_unchanged_with_multiple_documents(
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)
    hosted_facility_reference_metadata.create_all(engine)
    first_record = _initial_missing_record()
    second_record = _record_for_second_document(_initial_missing_record())
    first_facility = cast(dict[str, Any], first_record["facility"])
    second_facility = cast(dict[str, Any], second_record["facility"])
    assert first_facility["facility_id"] == second_facility["facility_id"]
    assert first_facility["facility_name"] != second_facility["facility_name"]

    deduplicated = _deduplicate_facility_projections((first_record, second_record))
    assert "facility" not in deduplicated[0]
    assert deduplicated[1]["facility"] == second_facility
    for retained_key in (
        "source_document",
        "complaint",
        "allegations",
        "events",
        "extraction_audit",
    ):
        assert deduplicated[0][retained_key] == first_record[retained_key]
        assert deduplicated[1][retained_key] == second_record[retained_key]

    artifact = replace(
        _artifact("multiple-documents", first_record),
        records=(first_record, second_record),
    )

    with engine.connect() as connection:
        import_seeded_corpus_artifact(connection, artifact)
        connection.commit()

        first_dry_run = run_ccld_hosted_backfill(
            connection,
            CcldHostedBackfillRequest(
                facility_numbers=("425802141",),
                operation="preserved-artifacts",
                batch_size=1,
            ),
            now=datetime(2026, 7, 13, tzinfo=UTC),
        )
        first_complaint = _entity_values(
            connection,
            "complaint",
            "ccld-complaint-31-CR-20240425094018",
        )
        after_dry_run = _backfill_persistence_snapshot(connection)

        repeat_dry_run = run_ccld_hosted_backfill(
            connection,
            CcldHostedBackfillRequest(
                facility_numbers=("425802141",),
                operation="preserved-artifacts",
                batch_size=1,
            ),
            now=datetime(2026, 7, 14, tzinfo=UTC),
        )

        assert first_dry_run.updated == 1
        assert first_dry_run.unchanged == 0
        assert first_complaint["first_investigation_activity_date"] is None
        assert repeat_dry_run.updated == 1
        assert repeat_dry_run.unchanged == 0
        assert _backfill_persistence_snapshot(connection) == after_dry_run


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


def _record_for_second_document(record: dict[str, object]) -> dict[str, object]:
    old_document_id = "ccld-425802141-inx-1"
    new_document_id = "ccld-425802141-inx-33"
    old_complaint_id = "ccld-complaint-31-CR-20240425094018"
    new_complaint_id = f"{old_complaint_id}-inx-33"
    facility = cast(dict[str, Any], record["facility"])
    document = cast(dict[str, Any], record["source_document"])
    complaint = cast(dict[str, Any], record["complaint"])
    facility["facility_name"] = "SECOND DOCUMENT FACILITY PROJECTION"
    document.update(
        document_id=new_document_id,
        source_url=SOURCE_URL.replace("inx=1", "inx=33"),
        report_index=33,
    )
    complaint.update(
        complaint_id=new_complaint_id,
        document_id=new_document_id,
    )
    for allegation in cast(list[dict[str, Any]], record["allegations"]):
        allegation["allegation_id"] = str(allegation["allegation_id"]).replace(
            old_complaint_id,
            new_complaint_id,
        )
        allegation["complaint_id"] = new_complaint_id
    for event in cast(list[dict[str, Any]], record.get("events", [])):
        event["event_id"] = str(event["event_id"]).replace(
            old_complaint_id,
            new_complaint_id,
        )
        event["complaint_id"] = new_complaint_id
    for audit in cast(list[dict[str, Any]], record["extraction_audit"]):
        audit["audit_id"] = str(audit["audit_id"]).replace(
            old_document_id,
            new_document_id,
        )
        audit["document_id"] = new_document_id
    return record


def _insert_reference(
    connection: Any,
    *,
    facility_number: str = "425802141",
) -> None:
    connection.execute(
        hosted_facility_reference_records.insert().values(
            source_resource_id="c9df723a-437f-4dcd-be37-ec73ae518bb9",
            facility_number=facility_number,
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
            original_row_json={"Facility Number": facility_number},
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


def _backfill_persistence_snapshot(
    connection: Any,
) -> tuple[tuple[tuple[Any, ...], ...], tuple[tuple[Any, ...], ...]]:
    return (
        tuple(
            connection.execute(
                select(hosted_import_batches).order_by(
                    hosted_import_batches.c.import_batch_id
                )
            ).tuples()
        ),
        tuple(
            connection.execute(
                select(hosted_source_derived_records).order_by(
                    hosted_source_derived_records.c.source_record_key
                )
            ).tuples()
        ),
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
