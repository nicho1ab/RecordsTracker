from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy import event as sqlalchemy_event

from ccld_complaints.connectors.base import SourceDocument
from ccld_complaints.connectors.ccld.facility_reports import CcldFacilityReportsConnector
from ccld_complaints.hosted_app import ccld_backfill
from ccld_complaints.hosted_app.audit_events import hosted_audit_events
from ccld_complaints.hosted_app.auth import HostedAccessScope
from ccld_complaints.hosted_app.ccld_backfill import (
    CcldHostedBackfillRequest,
    _deduplicate_facility_projections,
    diagnose_ccld_preserved_artifact_differences,
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
    load_seeded_corpus_artifact,
)
from ccld_complaints.utils.hash import sha256_bytes

RAW_FIXTURE = Path("tests/fixtures/ccld/raw/425802141_inx1_governed_refresh.html")
STRUCTURED_RAW_FIXTURE = Path(
    "tests/fixtures/ccld/raw/900000001_inx1_issue574_structured_fields.html"
)
SOURCE_URL = (
    "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports"
    "?facNum=425802141&inx=1"
)
HISTORICAL_SEEDED_CORPUS_FIXTURE = Path(
    "tests/fixtures/hosted_seeded_corpus/validated_seeded_corpus.json"
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
                    operation="preserved-artifacts",
                    apply_changes=True,
                    max_facilities=1,
                ),
            )
        with pytest.raises(ValueError, match="explicit max_facilities"):
            run_ccld_hosted_backfill(
                connection,
                CcldHostedBackfillRequest(
                    facility_numbers=("425802141",),
                    operation="preserved-artifacts",
                    apply_changes=True,
                    checkpoint_file=tmp_path / "checkpoint.json",
                ),
            )
        with pytest.raises(ValueError, match="approved facility-reference"):
            run_ccld_hosted_backfill(
                connection,
                CcldHostedBackfillRequest(
                    facility_numbers=("425802141",),
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


def test_complaint_observation_backfill_is_bounded_idempotent_and_preserves_state(
    tmp_path: Path,
) -> None:
    content = STRUCTURED_RAW_FIXTURE.read_bytes()
    connector = CcldFacilityReportsConnector()
    record = connector.normalize(
        connector.extract(
            SourceDocument(
                source_url=(
                    "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports"
                    "?facNum=900000001&inx=1"
                ),
                raw_path=STRUCTURED_RAW_FIXTURE,
                raw_sha256=sha256_bytes(content),
                retrieved_at="2026-07-23T00:00:00+00:00",
                content_type="text/html",
            )
        )
    )
    expected_complaint = cast(dict[str, Any], record["complaint"])
    initial_record = copy.deepcopy(record)
    initial_complaint = cast(dict[str, Any], initial_record["complaint"])
    for field_name in (
        "agency_name",
        "deficiency_texts",
        "investigation_findings_narrative",
        "complaint_report_contact",
    ):
        initial_complaint.pop(field_name, None)

    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)
    hosted_facility_reference_metadata.create_all(engine)
    checkpoint = tmp_path / "complaint-observations.json"
    request = CcldHostedBackfillRequest(
        facility_numbers=("900000001",),
        operation="canonical-complaint-observations",
        batch_size=1,
        apply_changes=True,
        checkpoint_file=checkpoint,
        max_facilities=1,
    )
    with engine.connect() as connection:
        import_seeded_corpus_artifact(
            connection,
            _artifact("complaint-observations-initial", initial_record),
        )
        complaint_key = connection.execute(
            select(hosted_source_derived_records.c.source_record_key).where(
                hosted_source_derived_records.c.entity_type == "complaint"
            )
        ).scalar_one()
        _insert_reviewer_state_and_audit(connection, complaint_key)
        connection.commit()
        initial_state = _reviewer_snapshot(connection)
        before_dry_run = _entity_values(connection, "complaint")

        dry_run = run_ccld_hosted_backfill(
            connection,
            replace(
                request,
                apply_changes=False,
                checkpoint_file=None,
                max_facilities=None,
            ),
        )
        assert _entity_values(connection, "complaint") == before_dry_run

        first = run_ccld_hosted_backfill(connection, request)
        connection.commit()
        complaint_row = (
            connection.execute(
                select(hosted_source_derived_records).where(
                    hosted_source_derived_records.c.entity_type == "complaint"
                )
            )
            .mappings()
            .one()
        )
        repeat = run_ccld_hosted_backfill(
            connection,
            replace(request, restart=True),
        )
        connection.commit()
        final_state = _reviewer_snapshot(connection)

    assert dry_run.candidates == dry_run.examined == dry_run.eligible == 1
    assert dry_run.intended_updates == 1
    assert dry_run.updated == 1
    assert dry_run.apply_changes is False
    assert first.candidates == first.examined == first.eligible == 1
    assert first.updated == 1
    assert first.failed == 0
    assert complaint_row["agency_name"] == expected_complaint["agency_name"]
    assert complaint_row["deficiency_texts"] == expected_complaint["deficiency_texts"]
    assert complaint_row["investigation_findings_narrative"] == (
        expected_complaint["investigation_findings_narrative"]
    )
    assert complaint_row["complaint_report_contact"] == (
        expected_complaint["complaint_report_contact"]
    )
    assert repeat.updated == 0
    assert repeat.unchanged == 1
    assert repeat.failed == 0
    assert final_state == initial_state
    checkpoint_payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert checkpoint_payload["completed_facility_numbers"] == ["900000001"]


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


def test_deduplicate_facility_projections_retains_document_bundles() -> None:
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


def test_preserved_artifact_repeat_is_unchanged_with_duplicate_complaint_projections(
    tmp_path: Path,
) -> None:
    first_record = _initial_missing_record()
    second_raw_path = tmp_path / "425802141_inx33_changed_finding.html"
    second_raw_path.write_text(
        RAW_FIXTURE.read_text(encoding="utf-8").replace(
            "Finding: Unsubstantiated",
            "Finding: Substantiated",
        ),
        encoding="utf-8",
    )
    second_record = _initial_missing_record(
        raw_fixture=second_raw_path,
        source_url=SOURCE_URL.replace("inx=1", "inx=33"),
    )
    first_document = cast(dict[str, Any], first_record["source_document"])
    second_document = cast(dict[str, Any], second_record["source_document"])
    first_complaint = cast(dict[str, Any], first_record["complaint"])
    second_complaint = cast(dict[str, Any], second_record["complaint"])
    assert first_document["document_id"] != second_document["document_id"]
    assert first_complaint["complaint_id"] == second_complaint["complaint_id"]
    assert first_complaint["finding"] == "Unsubstantiated"
    assert second_complaint["finding"] == "Substantiated"

    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)
    hosted_facility_reference_metadata.create_all(engine)
    artifact = replace(
        _artifact("duplicate-complaint-projections", first_record),
        records=(first_record, second_record),
    )
    checkpoint = tmp_path / "duplicate-complaint-projections.json"
    apply_request = CcldHostedBackfillRequest(
        facility_numbers=("425802141",),
        operation="preserved-artifacts",
        batch_size=1,
        apply_changes=True,
        checkpoint_file=checkpoint,
        max_facilities=1,
    )
    dry_run_request = replace(
        apply_request,
        apply_changes=False,
        checkpoint_file=None,
        max_facilities=None,
    )

    with engine.connect() as connection:
        import_seeded_corpus_artifact(connection, artifact)
        complaint_key = f"complaint:{first_complaint['complaint_id']}"
        _insert_reviewer_state_and_audit(connection, complaint_key)
        connection.commit()
        initial_counts = _source_counts(connection)
        initial_identities = _stable_identities(connection)
        initial_source_hashes = _source_hash_snapshot(connection)
        initial_import_scope = _import_scope_snapshot(connection)
        initial_reviewer_state = _reviewer_snapshot(connection)
        initial_source_rows = _source_rows_snapshot(connection)
        assert initial_counts["facility"] == 1
        assert initial_counts["source_document"] == 2
        assert initial_counts["complaint"] == 1
        assert initial_counts["allegation"] == 1
        assert initial_counts["event"] == 1
        assert initial_counts["extraction_audit"] > 1

        first_dry_run = run_ccld_hosted_backfill(
            connection,
            dry_run_request,
            now=datetime(2026, 7, 13, tzinfo=UTC),
        )
        assert _source_rows_snapshot(connection) == initial_source_rows

        first_apply = run_ccld_hosted_backfill(
            connection,
            apply_request,
            now=datetime(2026, 7, 13, tzinfo=UTC),
        )
        connection.commit()
        after_apply_source_rows = _source_rows_snapshot(connection)
        applied_complaint = _entity_values(
            connection,
            "complaint",
            str(first_complaint["complaint_id"]),
        )
        applied_traceability = _entity_traceability(
            connection,
            "complaint",
            str(first_complaint["complaint_id"]),
        )
        applied_artifact_identity = applied_traceability[
            "source_artifact_identity"
        ]
        applied_conflicts = tuple(applied_traceability["refresh_conflicts"])

        repeat_dry_run = run_ccld_hosted_backfill(
            connection,
            dry_run_request,
            now=datetime(2026, 7, 14, tzinfo=UTC),
        )
        assert _source_rows_snapshot(connection) == after_apply_source_rows

        equivalent_operation_dry_run = run_ccld_hosted_backfill(
            connection,
            replace(
                dry_run_request,
                operation="canonical-complaint-observations",
            ),
            now=datetime(2026, 7, 14, tzinfo=UTC),
        )
        assert _source_rows_snapshot(connection) == after_apply_source_rows

        second_apply = run_ccld_hosted_backfill(
            connection,
            replace(apply_request, restart=True),
            now=datetime(2026, 7, 14, tzinfo=UTC),
        )
        connection.commit()
        final_traceability = _entity_traceability(
            connection,
            "complaint",
            str(first_complaint["complaint_id"]),
        )

        assert first_dry_run.updated == 1
        assert first_dry_run.unchanged == 0
        assert first_apply.updated == 1
        assert first_apply.unchanged == 0
        assert applied_complaint["first_investigation_activity_date"] == "2025-11-07"
        assert applied_complaint["finding"] == "Substantiated"
        assert isinstance(applied_artifact_identity, str)
        assert applied_artifact_identity.startswith(
            "preserved-ccld-backfill:preserved-artifacts:425802141:"
        )
        assert applied_conflicts
        assert repeat_dry_run.updated == 0
        assert repeat_dry_run.unchanged == 1
        assert repeat_dry_run.conflicted == 0
        assert equivalent_operation_dry_run.updated == 0
        assert equivalent_operation_dry_run.unchanged == 1
        assert equivalent_operation_dry_run.conflicted == 0
        assert second_apply.updated == 0
        assert second_apply.unchanged == 1
        assert second_apply.conflicted == 0
        assert _source_rows_snapshot(connection) == after_apply_source_rows
        assert (
            final_traceability["source_artifact_identity"]
            == applied_artifact_identity
        )
        assert tuple(final_traceability["refresh_conflicts"]) == applied_conflicts
        assert _source_counts(connection) == initial_counts
        assert _stable_identities(connection) == initial_identities
        assert _source_hash_snapshot(connection) == initial_source_hashes
        assert _import_scope_snapshot(connection) == initial_import_scope
        assert _reviewer_snapshot(connection) == initial_reviewer_state


def test_preserved_artifact_scopes_new_audits_to_historical_document_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_record = _normalized_record(
        raw_fixture=STRUCTURED_RAW_FIXTURE,
        source_url=SOURCE_URL.replace("425802141", "900000001"),
    )
    second_raw_path = tmp_path / "900000001_inx33_structured_fields.html"
    second_raw_path.write_text(
        STRUCTURED_RAW_FIXTURE.read_text(encoding="utf-8").replace(
            "Synthetic Facility",
            "Second Synthetic Facility",
        ),
        encoding="utf-8",
    )
    second_record = _normalized_record(
        raw_fixture=second_raw_path,
        source_url=SOURCE_URL.replace("425802141", "900000001").replace(
            "inx=1",
            "inx=33",
        ),
    )
    historical_document_ids = (
        "ccld:document:900000001:z-preserved",
        "ccld:document:900000001:a-preserved",
    )
    complete_records = tuple(
        _record_with_historical_document_identity(record, document_id)
        for record, document_id in zip(
            (first_record, second_record),
            historical_document_ids,
            strict=True,
        )
    )
    sparse_records = tuple(
        copy.deepcopy(record)
        for record in sorted(
            complete_records,
            key=lambda item: str(
                cast(Mapping[str, Any], item["source_document"])["document_id"]
            ),
        )
    )
    for record in sparse_records:
        audits = cast(list[dict[str, Any]], record["extraction_audit"])
        audits[:] = [audit for audit in audits if audit["field_name"] == "deficiency_text"]
        assert len(audits) == 2
        document = cast(dict[str, Any], record["source_document"])
        for audit in audits:
            assert str(audit["audit_id"]).startswith(str(document["document_id"]))
            assert audit["document_id"] == document["document_id"]

    historical = replace(
        _artifact("document-scoped-historical-audits", sparse_records[0]),
        records=sparse_records,
    )
    complete_audit_keys = {
        f"extraction_audit:{audit['audit_id']}"
        for record in complete_records
        for audit in cast(list[dict[str, Any]], record["extraction_audit"])
    }
    historical_audit_keys = {
        f"extraction_audit:{audit['audit_id']}"
        for record in sparse_records
        for audit in cast(list[dict[str, Any]], record["extraction_audit"])
    }

    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)
    hosted_facility_reference_metadata.create_all(engine)
    apply_request = CcldHostedBackfillRequest(
        facility_numbers=("900000001",),
        operation="preserved-artifacts",
        batch_size=1,
        apply_changes=True,
        checkpoint_file=tmp_path / "document-scoped-historical-audits.json",
        max_facilities=1,
    )
    dry_run_request = replace(
        apply_request,
        apply_changes=False,
        checkpoint_file=None,
        max_facilities=None,
    )
    change_mode: str | None = None
    original_reprocess = ccld_backfill._reprocess_preserved_document

    def reprocess_preserved_document(
        connection: Any,
        facility_number: str,
        facility_row: Mapping[str, Any],
        source_document_row: Mapping[str, Any],
    ) -> Mapping[str, Any] | None:
        normalized = original_reprocess(
            connection,
            facility_number,
            facility_row,
            source_document_row,
        )
        if normalized is None or source_document_row["stable_source_id"] != (
            historical_document_ids[0]
        ):
            return normalized
        if change_mode == "document":
            cast(dict[str, Any], normalized["source_document"])["content_type"] = (
                "application/test-changed"
            )
        audits = cast(list[dict[str, Any]], normalized["extraction_audit"])
        if change_mode == "audit":
            next(audit for audit in audits if audit["field_name"] == "agency_name")[
                "extracted_value"
            ] = "changed governed audit evidence"
        elif change_mode == "new-audit":
            new_audit = copy.deepcopy(audits[0])
            new_audit.update(
                audit_id=f"{historical_document_ids[0]}-new-governed-audit",
                field_name="new_governed_audit",
                extracted_value="new governed audit evidence",
            )
            audits.append(new_audit)
        elif change_mode == "removed-audit":
            audits[:] = [
                audit for audit in audits if audit["field_name"] != "agency_name"
            ]
        return normalized

    monkeypatch.setattr(
        ccld_backfill,
        "_reprocess_preserved_document",
        reprocess_preserved_document,
    )

    with engine.connect() as connection:
        import_seeded_corpus_artifact(connection, historical)
        complaint = cast(dict[str, Any], complete_records[0]["complaint"])
        complaint_id = str(complaint["complaint_id"])
        _insert_reviewer_state_and_audit(
            connection,
            f"complaint:{complaint_id}",
            complaint_stable_id=complaint_id,
            source_document_id=historical_document_ids[0],
        )
        connection.commit()
        initial_source_document_keys = {
            key
            for entity_type, key in _stable_identities(connection)
            if entity_type == "source_document"
        }
        initial_hashes = dict(_source_hash_snapshot(connection))
        initial_import_scope = dict(_import_scope_snapshot(connection))
        initial_reviewer_state = _reviewer_snapshot(connection)

        source_document_rows = tuple(
            connection.execute(
                select(hosted_source_derived_records)
                .where(hosted_source_derived_records.c.entity_type == "source_document")
                .order_by(hosted_source_derived_records.c.stable_source_id)
            ).mappings()
        )
        assert tuple(row["stable_source_id"] for row in source_document_rows) == (
            historical_document_ids[1],
            historical_document_ids[0],
        )
        assert tuple(
            cast(Mapping[str, Any], row["original_values"])["source_url"]
            for row in source_document_rows
        ) == (
            cast(Mapping[str, Any], complete_records[1]["source_document"])["source_url"],
            cast(Mapping[str, Any], complete_records[0]["source_document"])["source_url"],
        )

        differences = diagnose_ccld_preserved_artifact_differences(
            connection,
            ("900000001",),
        )
        new_audit_keys = {
            difference.source_record_key
            for difference in differences
            if difference.entity_type == "extraction_audit"
            and difference.differing_fields == ("persisted_record",)
        }
        source_document_differences = tuple(
            difference
            for difference in differences
            if difference.entity_type == "source_document"
        )
        assert new_audit_keys == complete_audit_keys - historical_audit_keys
        assert source_document_differences
        assert {
            difference.differing_fields for difference in source_document_differences
        } == {("source_traceability.source_artifact_identity",)}

        first_dry_run = run_ccld_hosted_backfill(connection, dry_run_request)
        first_apply = run_ccld_hosted_backfill(connection, apply_request)
        connection.commit()
        after_apply_rows = _source_rows_snapshot(connection)
        after_apply_hashes = dict(_source_hash_snapshot(connection))
        after_apply_import_scope = dict(_import_scope_snapshot(connection))
        after_apply_reviewer_state = _reviewer_snapshot(connection)
        after_apply_identities = _stable_identities(connection)
        audit_rows = tuple(
            connection.execute(
                select(hosted_source_derived_records).where(
                    hosted_source_derived_records.c.entity_type == "extraction_audit"
                )
            ).mappings()
        )

        assert first_dry_run.updated == 1
        assert first_dry_run.unchanged == 0
        assert first_apply.updated == 1
        assert first_apply.unchanged == 0
        assert {
            key
            for entity_type, key in after_apply_identities
            if entity_type == "source_document"
        } == initial_source_document_keys
        assert {
            f"extraction_audit:{key}"
            for entity_type, key in after_apply_identities
            if entity_type == "extraction_audit"
        } == complete_audit_keys
        assert all(
            str(row["stable_source_id"]).startswith(str(row["source_document_id"]))
            and cast(Mapping[str, Any], row["original_values"])["document_id"]
            == row["source_document_id"]
            for row in audit_rows
        )
        assert all(after_apply_hashes[key] == value for key, value in initial_hashes.items())
        assert all(
            after_apply_import_scope[key] == value
            for key, value in initial_import_scope.items()
        )
        assert after_apply_reviewer_state == initial_reviewer_state

        assert diagnose_ccld_preserved_artifact_differences(
            connection,
            ("900000001",),
        ) == ()
        repeat = run_ccld_hosted_backfill(connection, dry_run_request)
        equivalent_operation = run_ccld_hosted_backfill(
            connection,
            replace(dry_run_request, operation="canonical-complaint-observations"),
        )
        second_apply = run_ccld_hosted_backfill(
            connection,
            replace(apply_request, restart=True),
        )
        connection.commit()

        assert repeat.updated == 0
        assert repeat.unchanged == 1
        assert equivalent_operation.updated == 0
        assert equivalent_operation.unchanged == 1
        assert second_apply.updated == 0
        assert second_apply.unchanged == 1
        assert _source_rows_snapshot(connection) == after_apply_rows
        assert _reviewer_snapshot(connection) == initial_reviewer_state

        change_mode = "document"
        changed_document = run_ccld_hosted_backfill(connection, dry_run_request)
        change_mode = "audit"
        changed_audit = run_ccld_hosted_backfill(connection, dry_run_request)
        change_mode = "new-audit"
        new_audit = diagnose_ccld_preserved_artifact_differences(
            connection,
            ("900000001",),
        )
        change_mode = "removed-audit"
        removed_audit = run_ccld_hosted_backfill(connection, dry_run_request)
        change_mode = None

        assert changed_document.updated == 1
        assert changed_audit.updated == 1
        assert any(
            difference.source_record_key
            == f"extraction_audit:{historical_document_ids[0]}-new-governed-audit"
            and difference.differing_fields == ("persisted_record",)
            for difference in new_audit
        )
        assert removed_audit.updated == 1
        assert _source_rows_snapshot(connection) == after_apply_rows
        assert _reviewer_snapshot(connection) == initial_reviewer_state

        new_document_record = _normalized_record(
            raw_fixture=STRUCTURED_RAW_FIXTURE,
            source_url=SOURCE_URL.replace("425802141", "900000001").replace(
                "inx=1",
                "inx=44",
            ),
        )
        new_document = cast(dict[str, Any], new_document_record["source_document"])
        new_document_id = str(new_document["document_id"])
        assert new_document_id not in initial_source_document_keys
        new_document_result = import_seeded_corpus_artifact(
            connection,
            _artifact("genuinely-new-document", new_document_record),
            preserve_existing_import_batch=True,
        )
        assert new_document_result.inserted_record_count > 0
        assert (
            "source_document",
            new_document_id,
        ) in _stable_identities(connection)
        assert _reviewer_snapshot(connection) == initial_reviewer_state


def test_preserved_artifact_reuses_shared_historical_audit_identities(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_source_url = SOURCE_URL.replace("425802141", "900000001")
    first_record = _normalized_record(
        raw_fixture=STRUCTURED_RAW_FIXTURE,
        source_url=first_source_url,
    )
    second_record = _normalized_record(
        raw_fixture=STRUCTURED_RAW_FIXTURE,
        source_url=first_source_url.replace("inx=1", "inx=33"),
    )
    first_document = cast(dict[str, Any], first_record["source_document"])
    second_document = cast(dict[str, Any], second_record["source_document"])
    assert first_document["document_id"] != second_document["document_id"]

    for record in (first_record, second_record):
        occurrences: dict[str, int] = {}
        for audit in cast(list[dict[str, Any]], record["extraction_audit"]):
            field_name = str(audit["field_name"])
            occurrences[field_name] = occurrences.get(field_name, 0) + 1
            if record is first_record and field_name == "facility_number":
                continue
            audit["audit_id"] = f"historical-audit:{field_name}:{occurrences[field_name]}"
    assert (
        sum(
            audit["field_name"] == "deficiency_text"
            for audit in cast(list[dict[str, Any]], first_record["extraction_audit"])
        )
        == 2
    )

    historical = replace(
        _artifact("shared-historical-audits", first_record),
        records=(first_record, second_record),
    )
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)
    hosted_facility_reference_metadata.create_all(engine)
    checkpoint = tmp_path / "shared-historical-audits.json"
    apply_request = CcldHostedBackfillRequest(
        facility_numbers=("900000001",),
        operation="preserved-artifacts",
        batch_size=1,
        apply_changes=True,
        checkpoint_file=checkpoint,
        max_facilities=1,
    )
    dry_run_request = replace(
        apply_request,
        apply_changes=False,
        checkpoint_file=None,
        max_facilities=None,
    )
    change_mode: str | None = None
    original_reprocess = ccld_backfill._reprocess_preserved_document

    def reprocess_preserved_document(
        connection: Any,
        facility_number: str,
        facility_row: Mapping[str, Any],
        source_document_row: Mapping[str, Any],
    ) -> Mapping[str, Any] | None:
        normalized = original_reprocess(
            connection,
            facility_number,
            facility_row,
            source_document_row,
        )
        target_document_id = (
            first_document["document_id"]
            if change_mode == "new"
            else second_document["document_id"]
        )
        if normalized is None or source_document_row["stable_source_id"] != target_document_id:
            return normalized
        audits = cast(list[dict[str, Any]], normalized["extraction_audit"])
        if change_mode == "changed":
            next(audit for audit in audits if audit["field_name"] == "facility_number")[
                "extracted_value"
            ] = "governed-change"
        elif change_mode == "new":
            audits.append(
                {
                    "audit_id": f"{first_document['document_id']}-new-governed-audit",
                    "document_id": first_document["document_id"],
                    "field_name": "new_governed_audit",
                    "extraction_method": "ccld_facility_report_html_labels",
                    "extractor_version": "0.1.0",
                    "extracted_value": "new governed evidence",
                    "confidence": 1.0,
                    "source_text": "new governed evidence",
                    "source_section": "fixture section",
                    "warning": None,
                }
            )
        elif change_mode == "removed":
            audits[:] = [audit for audit in audits if audit["field_name"] != "agency_name"]
        return normalized

    monkeypatch.setattr(
        ccld_backfill,
        "_reprocess_preserved_document",
        reprocess_preserved_document,
    )

    with engine.connect() as connection:
        import_seeded_corpus_artifact(connection, historical)
        complaint = cast(dict[str, Any], second_record["complaint"])
        complaint_id = str(complaint["complaint_id"])
        _insert_reviewer_state_and_audit(
            connection,
            f"complaint:{complaint_id}",
            complaint_stable_id=complaint_id,
            source_document_id=str(second_document["document_id"]),
        )
        connection.commit()
        initial_rows = _source_rows_snapshot(connection)
        initial_audit_ids = {
            stable_id
            for entity_type, stable_id in _stable_identities(connection)
            if entity_type == "extraction_audit"
        }
        initial_hashes = _source_hash_snapshot(connection)
        initial_import_scope = _import_scope_snapshot(connection)
        initial_reviewer_state = _reviewer_snapshot(connection)

        differences = diagnose_ccld_preserved_artifact_differences(
            connection,
            ("900000001",),
        )
        first_dry_run = run_ccld_hosted_backfill(connection, dry_run_request)
        first_apply = run_ccld_hosted_backfill(connection, apply_request)
        connection.commit()
        repeat = run_ccld_hosted_backfill(connection, dry_run_request)
        equivalent_operation = run_ccld_hosted_backfill(
            connection,
            replace(dry_run_request, operation="canonical-complaint-observations"),
        )
        second_apply = run_ccld_hosted_backfill(
            connection,
            replace(apply_request, restart=True),
        )
        connection.commit()

        assert differences == ()
        assert first_dry_run.updated == 0
        assert first_dry_run.unchanged == 1
        assert first_apply.updated == 0
        assert first_apply.unchanged == 1
        assert repeat.updated == 0
        assert repeat.unchanged == 1
        assert equivalent_operation.updated == 0
        assert equivalent_operation.unchanged == 1
        assert second_apply.updated == 0
        assert second_apply.unchanged == 1
        assert {
            stable_id
            for entity_type, stable_id in _stable_identities(connection)
            if entity_type == "extraction_audit"
        } == initial_audit_ids

        change_mode = "changed"
        changed = run_ccld_hosted_backfill(connection, dry_run_request)
        change_mode = "new"
        new_differences = diagnose_ccld_preserved_artifact_differences(
            connection,
            ("900000001",),
        )
        new_audit_key = f"extraction_audit:{first_document['document_id']}-new-governed-audit"
        change_mode = "removed"
        removed = run_ccld_hosted_backfill(connection, dry_run_request)

        assert changed.updated == 1
        assert any(
            difference.source_record_key == new_audit_key
            and difference.differing_fields == ("persisted_record",)
            for difference in new_differences
        )
        assert removed.updated == 1
        assert _source_rows_snapshot(connection) == initial_rows
        assert _source_hash_snapshot(connection) == initial_hashes
        assert _import_scope_snapshot(connection) == initial_import_scope
        assert _reviewer_snapshot(connection) == initial_reviewer_state


def test_preserved_artifact_identity_uses_final_persisted_projections() -> None:
    first_record = _initial_missing_record()
    second_record = _initial_missing_record(
        source_url=SOURCE_URL.replace("inx=1", "inx=33"),
    )
    first_document = cast(dict[str, Any], first_record["source_document"])
    second_document = cast(dict[str, Any], second_record["source_document"])
    first_complaint = cast(dict[str, Any], first_record["complaint"])
    second_complaint = cast(dict[str, Any], second_record["complaint"])
    assert first_document["document_id"] != second_document["document_id"]
    assert first_complaint["complaint_id"] == second_complaint["complaint_id"]

    baseline_records = _deduplicate_facility_projections((first_record, second_record))
    intermediate_only_change = copy.deepcopy(first_record)
    intermediate_allegation = cast(
        list[dict[str, Any]],
        intermediate_only_change["allegations"],
    )[0]
    intermediate_allegation["allegation_text"] = "Superseded duplicate allegation projection."
    equivalent_records = _deduplicate_facility_projections(
        (intermediate_only_change, second_record)
    )
    genuine_change = copy.deepcopy(second_record)
    final_allegation = cast(list[dict[str, Any]], genuine_change["allegations"])[0]
    final_allegation["allegation_text"] = "Genuinely changed final allegation."
    changed_records = _deduplicate_facility_projections((first_record, genuine_change))

    baseline = ccld_backfill._backfill_artifact(
        "425802141",
        baseline_records,
        operation="preserved-artifacts",
        now=datetime(2026, 8, 9, tzinfo=UTC),
    )
    equivalent = ccld_backfill._backfill_artifact(
        "425802141",
        equivalent_records,
        operation="preserved-artifacts",
        now=datetime(2026, 8, 10, tzinfo=UTC),
    )
    changed = ccld_backfill._backfill_artifact(
        "425802141",
        changed_records,
        operation="preserved-artifacts",
        now=datetime(2026, 8, 10, tzinfo=UTC),
    )

    assert equivalent.source_artifact_identity != baseline.source_artifact_identity
    assert equivalent.import_batch_id != baseline.import_batch_id
    assert changed.source_artifact_identity != baseline.source_artifact_identity
    assert changed.import_batch_id != baseline.import_batch_id

    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)
    with engine.connect() as connection:
        import_seeded_corpus_artifact(connection, baseline)
        connection.commit()
        baseline_rows = _source_rows_snapshot(connection)

        equivalent = ccld_backfill._stabilize_equivalent_artifact_provenance(
            connection,
            equivalent,
        )
        assert equivalent.source_artifact_identity == baseline.source_artifact_identity
        assert equivalent.import_batch_id == baseline.import_batch_id
        equivalent_result = import_seeded_corpus_artifact(
            connection,
            equivalent,
            preserve_existing_import_batch=True,
        )
        assert equivalent_result.updated_record_count == 0
        assert equivalent_result.inserted_record_count == 0
        assert _source_rows_snapshot(connection) == baseline_rows

        changed = ccld_backfill._stabilize_equivalent_artifact_provenance(
            connection,
            changed,
        )
        assert changed.source_artifact_identity != baseline.source_artifact_identity
        changed_result = import_seeded_corpus_artifact(
            connection,
            changed,
            preserve_existing_import_batch=True,
        )
        assert changed_result.updated_record_count > 0


def test_preserved_artifact_insertion_keeps_allegation_semantic_siblings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    historical = load_seeded_corpus_artifact(HISTORICAL_SEEDED_CORPUS_FIXTURE)
    historical_record = copy.deepcopy(dict(historical.records[0]))
    historical_allegations = cast(
        list[dict[str, Any]],
        historical_record["allegations"],
    )
    complaint = cast(dict[str, Any], historical_record["complaint"])
    complaint_id = str(complaint["complaint_id"])
    complaint_key = f"complaint:{complaint_id}"
    source_document = cast(dict[str, Any], historical_record["source_document"])
    source_document_id = str(source_document["document_id"])
    allegation_prefix = str(historical_allegations[0]["allegation_id"]).rsplit(":", 1)[0]
    for ordinal, label in (
        (3, "Third historical allegation."),
        (4, "Fourth historical allegation."),
    ):
        sibling = copy.deepcopy(historical_allegations[-1])
        sibling["allegation_id"] = f"{allegation_prefix}:{ordinal}"
        sibling["allegation_text"] = label
        historical_allegations.append(sibling)
    historical_artifact = replace(historical, records=(historical_record,))
    original_texts = [str(allegation["allegation_text"]) for allegation in historical_allegations]
    changed_text = False

    def fresh_normalized_record() -> dict[str, object]:
        record = copy.deepcopy(historical_record)
        prior = cast(list[dict[str, Any]], record["allegations"])
        inserted = copy.deepcopy(prior[0])
        inserted["allegation_text"] = "Newly inserted second allegation."
        allegations = [prior[0], inserted, *prior[1:]]
        for ordinal, allegation in enumerate(allegations, start=1):
            allegation["allegation_id"] = f"{allegation_prefix}:{ordinal}"
        if changed_text:
            allegations[2]["allegation_text"] = "Corrected second historical allegation."
        record["allegations"] = allegations
        return record

    def reprocess_preserved_document(
        connection: Any,
        _facility_number: str,
        facility_row: Mapping[str, Any],
        source_document_row: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        normalized = fresh_normalized_record()
        ccld_backfill._preserve_stable_identities(
            connection,
            normalized,
            facility_row,
            source_document_row,
        )
        return normalized

    monkeypatch.setattr(
        ccld_backfill,
        "_reprocess_preserved_document",
        reprocess_preserved_document,
    )
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)
    hosted_facility_reference_metadata.create_all(engine)
    apply_request = CcldHostedBackfillRequest(
        facility_numbers=("157806098",),
        operation="preserved-artifacts",
        batch_size=1,
        apply_changes=True,
        checkpoint_file=tmp_path / "semantic-sibling-insertion.json",
        max_facilities=1,
    )
    dry_run_request = replace(
        apply_request,
        apply_changes=False,
        checkpoint_file=None,
        max_facilities=None,
    )

    with engine.connect() as connection:
        import_seeded_corpus_artifact(connection, historical_artifact)
        _insert_reviewer_state_and_audit(
            connection,
            complaint_key,
            complaint_stable_id=complaint_id,
            source_document_id=source_document_id,
        )
        connection.commit()
        initial_hashes = _source_hash_snapshot(connection)
        initial_import_scope = _import_scope_snapshot(connection)
        initial_reviewer_state = _reviewer_snapshot(connection)

        first_dry_run = run_ccld_hosted_backfill(connection, dry_run_request)
        first_apply = run_ccld_hosted_backfill(connection, apply_request)
        connection.commit()
        after_apply_rows = _source_rows_snapshot(connection)
        after_apply_hashes = _source_hash_snapshot(connection)
        after_apply_import_scope = _import_scope_snapshot(connection)
        allegation_rows = tuple(
            dict(row)
            for row in connection.execute(
                select(hosted_source_derived_records).where(
                    hosted_source_derived_records.c.entity_type == "allegation"
                )
            ).mappings()
        )
        stable_id_by_text = {
            str(cast(Mapping[str, Any], row["original_values"])["allegation_text"]): str(
                row["stable_source_id"]
            )
            for row in allegation_rows
        }

        repeat_dry_run = run_ccld_hosted_backfill(connection, dry_run_request)
        equivalent_operation = run_ccld_hosted_backfill(
            connection,
            replace(dry_run_request, operation="canonical-complaint-observations"),
        )
        second_apply = run_ccld_hosted_backfill(
            connection,
            replace(apply_request, restart=True),
        )
        connection.commit()

        changed_text = True
        genuine_change = run_ccld_hosted_backfill(connection, dry_run_request)

        assert first_dry_run.updated == 1
        assert first_apply.updated == 1
        assert repeat_dry_run.updated == 0
        assert repeat_dry_run.unchanged == 1
        assert equivalent_operation.updated == 0
        assert equivalent_operation.unchanged == 1
        assert second_apply.updated == 0
        assert second_apply.unchanged == 1
        assert genuine_change.updated == 1
        assert genuine_change.unchanged == 0
        assert len(allegation_rows) == 5
        for ordinal, text in enumerate(original_texts, start=1):
            assert stable_id_by_text[text] == f"{allegation_prefix}:{ordinal}"
        assert stable_id_by_text["Newly inserted second allegation."] == f"{allegation_prefix}:5"
        assert _source_rows_snapshot(connection) == after_apply_rows
        assert _source_hash_snapshot(connection) == after_apply_hashes
        assert all(dict(after_apply_hashes)[key] == raw_hash for key, raw_hash in initial_hashes)
        assert _import_scope_snapshot(connection) == after_apply_import_scope
        assert all(
            dict(after_apply_import_scope)[key] == import_batch_id
            for key, import_batch_id in initial_import_scope
        )
        assert _reviewer_snapshot(connection) == initial_reviewer_state


def test_preserved_artifact_repeat_is_unchanged_when_extraction_adds_child(
    tmp_path: Path,
) -> None:
    historical = load_seeded_corpus_artifact(HISTORICAL_SEEDED_CORPUS_FIXTURE)
    record = copy.deepcopy(dict(historical.records[0]))
    allegations = cast(list[dict[str, Any]], record["allegations"])
    assert len(allegations) == 2
    record["allegations"] = allegations[:1]
    pre_correction = replace(historical, records=(record,))
    complaint = cast(dict[str, Any], record["complaint"])
    complaint_id = str(complaint["complaint_id"])
    complaint_key = f"complaint:{complaint_id}"
    source_document = cast(dict[str, Any], record["source_document"])
    source_document_id = str(source_document["document_id"])

    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)
    hosted_facility_reference_metadata.create_all(engine)
    checkpoint = tmp_path / "new-child-checkpoint.json"
    apply_request = CcldHostedBackfillRequest(
        facility_numbers=("157806098",),
        operation="preserved-artifacts",
        batch_size=1,
        apply_changes=True,
        checkpoint_file=checkpoint,
        max_facilities=1,
    )
    dry_run_request = replace(
        apply_request,
        apply_changes=False,
        checkpoint_file=None,
        max_facilities=None,
    )

    with engine.connect() as connection:
        import_seeded_corpus_artifact(connection, pre_correction)
        _insert_reviewer_state_and_audit(
            connection,
            complaint_key,
            complaint_stable_id=complaint_id,
            source_document_id=source_document_id,
        )
        connection.commit()
        initial_identities = _stable_identities(connection)
        initial_import_scope = dict(_import_scope_snapshot(connection))
        initial_reviewer_state = _reviewer_snapshot(connection)

        first_dry_run = run_ccld_hosted_backfill(connection, dry_run_request)
        first_apply = run_ccld_hosted_backfill(connection, apply_request)
        connection.commit()
        after_first_apply = _source_rows_snapshot(connection)
        after_first_identities = _stable_identities(connection)
        after_first_hashes = _source_hash_snapshot(connection)
        after_first_import_scope = _import_scope_snapshot(connection)
        after_first_reviewer_state = _reviewer_snapshot(connection)
        after_first_conflicts = _entity_traceability(
            connection,
            "complaint",
            complaint_id,
        ).get("refresh_conflicts", [])

        repeat_dry_run = run_ccld_hosted_backfill(connection, dry_run_request)
        assert _source_rows_snapshot(connection) == after_first_apply

        equivalent_operation_dry_run = run_ccld_hosted_backfill(
            connection,
            replace(
                dry_run_request,
                operation="canonical-complaint-observations",
            ),
        )
        assert _source_rows_snapshot(connection) == after_first_apply

        second_apply = run_ccld_hosted_backfill(
            connection,
            replace(apply_request, restart=True),
        )
        connection.commit()

        final_conflicts = _entity_traceability(
            connection,
            "complaint",
            complaint_id,
        ).get("refresh_conflicts", [])

        assert first_dry_run.updated == 1
        assert first_dry_run.unchanged == 0
        assert first_apply.updated == 1
        assert first_apply.unchanged == 0
        assert repeat_dry_run.updated == 0
        assert repeat_dry_run.unchanged == 1
        assert equivalent_operation_dry_run.updated == 0
        assert equivalent_operation_dry_run.unchanged == 1
        assert second_apply.updated == 0
        assert second_apply.unchanged == 1
        assert _source_rows_snapshot(connection) == after_first_apply
        assert initial_identities < after_first_identities
        assert _stable_identities(connection) == after_first_identities
        assert _source_hash_snapshot(connection) == after_first_hashes
        assert _import_scope_snapshot(connection) == after_first_import_scope
        assert all(
            dict(after_first_import_scope)[key] == import_batch_id
            for key, import_batch_id in initial_import_scope.items()
        )
        assert after_first_reviewer_state == initial_reviewer_state
        assert _reviewer_snapshot(connection) == initial_reviewer_state
        assert final_conflicts == after_first_conflicts


def test_preserved_artifact_difference_diagnostic_is_select_only_and_redacted() -> None:
    historical = load_seeded_corpus_artifact(HISTORICAL_SEEDED_CORPUS_FIXTURE)
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)
    hosted_facility_reference_metadata.create_all(engine)

    with engine.connect() as connection:
        import_seeded_corpus_artifact(connection, historical)
        connection.commit()

    statements: list[str] = []

    def capture_statement(
        _connection: Any,
        _cursor: Any,
        statement: str,
        _parameters: Any,
        _context: Any,
        _executemany: Any,
    ) -> None:
        statements.append(statement)

    sqlalchemy_event.listen(engine, "before_cursor_execute", capture_statement)
    try:
        with engine.connect() as connection:
            differences = diagnose_ccld_preserved_artifact_differences(
                connection,
                ("157806098",),
            )
    finally:
        sqlalchemy_event.remove(engine, "before_cursor_execute", capture_statement)

    assert differences
    assert all(row.facility_number == "157806098" for row in differences)
    assert any(
        "source_traceability.source_artifact_identity" in row.differing_fields
        for row in differences
    )
    serialized = json.dumps([asdict(row) for row in differences], sort_keys=True)
    assert "Facility clients are being mistreated while in care." not in serialized
    assert '"sha256"' in serialized
    assert statements
    assert not any(
        statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
        for statement in statements
    )
    assert not any(
        table_name in statement
        for statement in statements
        for table_name in ("hosted_reviewer_created_state", "hosted_audit_events")
    )


def test_preserved_artifact_difference_diagnostic_fails_closed_on_selection() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)
    hosted_facility_reference_metadata.create_all(engine)
    with engine.connect() as connection:
        with pytest.raises(ValueError, match="explicit digit-only"):
            diagnose_ccld_preserved_artifact_differences(connection, ())
        with pytest.raises(ValueError, match="exactly once"):
            diagnose_ccld_preserved_artifact_differences(
                connection,
                ("157806098",),
            )


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


def _initial_missing_record(
    *,
    raw_fixture: Path = RAW_FIXTURE,
    source_url: str = SOURCE_URL,
) -> dict[str, object]:
    normalized = _normalized_record(
        raw_fixture=raw_fixture,
        source_url=source_url,
    )
    facility = cast(dict[str, Any], normalized["facility"])
    complaint = cast(dict[str, Any], normalized["complaint"])
    facility.update(facility_type=None, county=None, status=None)
    complaint.update(
        first_investigation_activity_date=None,
        days_received_to_first_activity=None,
        missing_first_activity_date=True,
    )
    return normalized


def _normalized_record(
    *,
    raw_fixture: Path = RAW_FIXTURE,
    source_url: str = SOURCE_URL,
) -> dict[str, object]:
    content = raw_fixture.read_bytes()
    connector = CcldFacilityReportsConnector(facility_number="425802141")
    return connector.normalize(
        connector.extract(
            SourceDocument(
                source_url=source_url,
                raw_path=raw_fixture,
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


def _record_with_historical_document_identity(
    record: dict[str, object],
    historical_document_id: str,
) -> dict[str, object]:
    generated_document_id = str(
        cast(dict[str, Any], record["source_document"])["document_id"]
    )
    document = cast(dict[str, Any], record["source_document"])
    complaint = cast(dict[str, Any], record["complaint"])
    document["document_id"] = historical_document_id
    complaint["document_id"] = historical_document_id
    for audit in cast(list[dict[str, Any]], record["extraction_audit"]):
        audit["audit_id"] = historical_document_id + str(audit["audit_id"])[
            len(generated_document_id) :
        ]
        audit["document_id"] = historical_document_id
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


def _insert_reviewer_state_and_audit(
    connection: Any,
    complaint_key: str,
    *,
    complaint_stable_id: str = "ccld-complaint-31-CR-20240425094018",
    source_document_id: str = "ccld-425802141-inx-1",
) -> None:
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
            source_stable_source_id=complaint_stable_id,
            source_document_id=source_document_id,
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


def _source_rows_snapshot(connection: Any) -> tuple[tuple[Any, ...], ...]:
    return tuple(
        connection.execute(
            select(hosted_source_derived_records).order_by(
                hosted_source_derived_records.c.source_record_key
            )
        ).tuples()
    )


def _source_hash_snapshot(connection: Any) -> tuple[tuple[str, str], ...]:
    return tuple(
        connection.execute(
            select(
                hosted_source_derived_records.c.source_record_key,
                hosted_source_derived_records.c.raw_sha256,
            )
            .order_by(hosted_source_derived_records.c.source_record_key)
        ).tuples()
    )


def _import_scope_snapshot(connection: Any) -> tuple[tuple[str, str], ...]:
    return tuple(
        connection.execute(
            select(
                hosted_source_derived_records.c.source_record_key,
                hosted_source_derived_records.c.import_batch_id,
            ).order_by(hosted_source_derived_records.c.source_record_key)
        ).tuples()
    )


def _entity_traceability(
    connection: Any,
    entity_type: str,
    stable_source_id: str,
) -> Mapping[str, Any]:
    return cast(
        Mapping[str, Any],
        connection.execute(
            select(hosted_source_derived_records.c.source_traceability).where(
                hosted_source_derived_records.c.entity_type == entity_type,
                hosted_source_derived_records.c.stable_source_id == stable_source_id,
            )
        ).scalar_one(),
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
