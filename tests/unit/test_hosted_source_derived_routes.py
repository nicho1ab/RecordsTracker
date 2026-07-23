from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Connection

from ccld_complaints.hosted_app.app import route_response
from ccld_complaints.hosted_app.auth import (
    CCLD_RETRIEVAL_CORPUS_SCOPE,
    AuthenticatedActor,
    HostedAccessScope,
    HostedAccountStatus,
    HostedActorCategory,
    HostedTesterRole,
)
from ccld_complaints.hosted_app.ccld_retrieval_jobs import retrieval_import_batch_id
from ccld_complaints.hosted_app.seeded_import import (
    hosted_import_batches,
    hosted_seeded_import_metadata,
    hosted_source_derived_records,
    import_seeded_corpus_artifact,
    load_seeded_corpus_artifact,
)
from ccld_complaints.hosted_app.source_derived_routes import SourceDerivedApiContext

FIXTURE = Path("tests/fixtures/hosted_seeded_corpus/validated_seeded_corpus.json")
TEST_SCOPE = HostedAccessScope("seeded_corpus", "seeded-ccld-fixture-2026-06-13")
OTHER_SCOPE = HostedAccessScope("seeded_corpus", "different-seeded-corpus")
POSTGRES_SCOPE = CCLD_RETRIEVAL_CORPUS_SCOPE
COMPLAINT_KEY = "complaint:ccld:complaint:32-CR-20220407124448"
COMPLAINT_STABLE_ID = "ccld:complaint:32-CR-20220407124448"
DEFAULT_ACTOR = object()


def test_source_derived_api_lists_authorized_staged_records() -> None:
    with _seeded_connection() as connection:
        status, content_type, body = route_response(
            "/api/source-derived-records",
            source_derived_api_context=_api_context(connection),
        )

    payload = _json_body(body)

    assert status == 200
    assert content_type == "application/json; charset=utf-8"
    assert payload["pagination"] == {
        "limit": None,
        "offset": 0,
        "returned_count": 7,
        "eligible_count": 7,
        "truncated": False,
        "status": "available",
        "cause": "The result includes every eligible record in the selected range.",
    }
    assert payload["filters"] == {"entity_type": None}
    complaint = next(
        record for record in payload["records"] if record["entity_type"] == "complaint"
    )
    assert complaint["source_record_key"] == COMPLAINT_KEY
    assert complaint["stable_source_id"] == COMPLAINT_STABLE_ID
    assert complaint["source_url"].startswith("https://www.ccld.dss.ca.gov/")
    assert complaint["raw_sha256"] == (
        "6088c9627374baac647e2f2a54f6e389cb68c1b92db42da00020aaf508a853bd"
    )
    assert complaint["connector_name"] == "ccld_facility_reports"
    assert complaint["retrieved_at"] == "2026-06-10T00:00:00+00:00"
    assert complaint["original_values"]["finding"] == "Unsubstantiated"
    assert complaint["original_value_presentations"]["finding"] == {
        "stored_value": "Unsubstantiated",
        "stored": True,
        "state": "present",
        "display": "Unsubstantiated",
        "export": "Unsubstantiated",
        "explanation": "A source value is present.",
    }
    assert complaint["original_values"]["days_received_to_first_activity"] == 7
    expected_durations = {
        "days_received_to_first_activity": (7, "present"),
        "days_received_to_visit": (139, "present"),
        "days_received_to_report": (139, "present"),
        "days_report_to_signed": (2, "present"),
    }
    for field_name, (stored_value, state) in expected_durations.items():
        assert complaint["original_values"][field_name] == stored_value
        assert complaint["original_value_presentations"][field_name]["state"] == state
        assert complaint["original_value_presentations"][field_name]["display"] == str(
            stored_value
        )
    facility = next(
        record for record in payload["records"] if record["entity_type"] == "facility"
    )
    assert facility["original_values"]["capacity"] == 48
    assert facility["original_value_presentations"]["capacity"]["state"] == "present"
    assert (
        facility["original_value_presentations"]["closed_date"]["state"]
        == "source_label_absent"
    )
    assert complaint["source_traceability"]["source_artifact_identity"] == FIXTURE.as_posix()
    assert complaint["import_batch"]["import_batch_id"] == TEST_SCOPE.scope_id
    assert "review_status" not in complaint["original_values"]
    assert "annotation" not in complaint["original_values"]


def test_source_derived_api_postgres_corpus_lists_loaded_retrieval_complaints() -> None:
    with _seeded_connection() as connection:
        first_key = _insert_corpus_complaint(
            connection,
            job_id="route-corpus-job-001",
            facility_number="107207198",
            complaint_control_number="24-CR-20260508083927",
        )
        second_key = _insert_corpus_complaint(
            connection,
            job_id="route-corpus-job-002",
            facility_number="425802141",
            complaint_control_number="31-CR-20240425094018",
        )

        status, _content_type, body = route_response(
            "/api/source-derived-records?entity_type=complaint",
            source_derived_api_context=_api_context(
                connection,
                actor=_actor(scopes=(POSTGRES_SCOPE,)),
                scope=POSTGRES_SCOPE,
            ),
        )

    payload = _json_body(body)
    keys = {record["source_record_key"] for record in payload["records"]}

    assert status == 200
    assert payload["pagination"]["returned_count"] == 2
    assert keys == {first_key, second_key}
    assert COMPLAINT_KEY not in keys
    for record in payload["records"]:
        presentations = record["original_value_presentations"]
        assert presentations["days_received_to_first_activity"]["state"] == (
            "verified_zero"
        )
        assert presentations["days_received_to_visit"]["display"] == "2"
        assert presentations["days_received_to_report"]["display"] == "3"
        assert presentations["days_report_to_signed"]["display"] == "1"


def test_source_derived_api_supports_entity_filter_and_paging() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            "/api/source-derived-records?entity_type=allegation&limit=1&offset=1",
            source_derived_api_context=_api_context(connection),
        )

    payload = _json_body(body)

    assert status == 200
    assert payload["filters"] == {"entity_type": "allegation"}
    assert payload["pagination"] == {
        "limit": 1,
        "offset": 1,
        "returned_count": 1,
        "eligible_count": 1,
        "truncated": False,
        "status": "available",
        "cause": "The result includes every eligible record in the selected range.",
    }
    assert [record["stable_source_id"] for record in payload["records"]] == [
        "ccld:allegation:32-CR-20220407124448:2"
    ]


def test_source_derived_api_fetches_authorized_record_by_key() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            f"/api/source-derived-records/by-key?source_record_key={quote(COMPLAINT_KEY)}",
            source_derived_api_context=_api_context(connection),
        )

    payload = _json_body(body)

    assert status == 200
    assert payload["record"]["source_record_key"] == COMPLAINT_KEY
    assert payload["record"]["source_document_id"] == "ccld:document:157806098:3"
    assert payload["record"]["import_batch"]["validation_status"] == "validated"


def test_source_derived_api_fetches_authorized_record_by_stable_identity() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            "/api/source-derived-records/by-identity"
            "?entity_type=complaint"
            f"&stable_source_id={quote(COMPLAINT_STABLE_ID)}",
            source_derived_api_context=_api_context(connection),
        )

    payload = _json_body(body)

    assert status == 200
    assert payload["record"]["source_record_key"] == COMPLAINT_KEY
    assert payload["record"]["entity_type"] == "complaint"


def test_source_derived_api_returns_not_found_for_missing_record() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            "/api/source-derived-records/by-key?source_record_key=missing-record",
            source_derived_api_context=_api_context(connection),
        )

    payload = _json_body(body)

    assert status == 404
    assert payload["error"]["code"] == "source_derived_record_not_found"


def test_source_derived_api_rejects_unauthenticated_actor() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            "/api/source-derived-records",
            source_derived_api_context=_api_context(connection, actor=None),
        )

    payload = _json_body(body)

    assert status == 401
    assert payload["error"]["code"] == "authentication_required"


@pytest.mark.parametrize("account_status", ["disabled", "revoked"])
def test_source_derived_api_rejects_disabled_or_revoked_actor(
    account_status: str,
) -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            "/api/source-derived-records",
            source_derived_api_context=_api_context(
                connection,
                actor=_actor(account_status=account_status),
            ),
        )

    payload = _json_body(body)

    assert status == 403
    assert payload["error"]["code"] == "account_disabled_or_revoked"


def test_source_derived_api_rejects_role_without_read_permission() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            "/api/source-derived-records",
            source_derived_api_context=_api_context(connection, actor=_actor(roles=())),
        )

    payload = _json_body(body)

    assert status == 403
    assert payload["error"]["code"] == "role_denied"


def test_source_derived_api_rejects_out_of_scope_actor() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            "/api/source-derived-records",
            source_derived_api_context=_api_context(
                connection,
                actor=_actor(scopes=(OTHER_SCOPE,)),
            ),
        )

    payload = _json_body(body)

    assert status == 403
    assert payload["error"]["code"] == "scope_denied"


def test_source_derived_api_rejects_invalid_filter_and_paging_values() -> None:
    with _seeded_connection() as connection:
        invalid_entity_status, _content_type, invalid_entity_body = route_response(
            "/api/source-derived-records?entity_type=review_status",
            source_derived_api_context=_api_context(connection),
        )
        invalid_limit_status, _content_type, invalid_limit_body = route_response(
            "/api/source-derived-records?limit=0",
            source_derived_api_context=_api_context(connection),
        )

    invalid_entity_payload = _json_body(invalid_entity_body)
    invalid_limit_payload = _json_body(invalid_limit_body)

    assert invalid_entity_status == 400
    assert invalid_entity_payload["error"]["code"] == "invalid_request"
    assert invalid_limit_status == 400
    assert invalid_limit_payload["error"]["code"] == "invalid_request"


def test_source_derived_api_requires_explicit_local_test_context() -> None:
    status, _content_type, body = route_response("/api/source-derived-records")

    payload = _json_body(body)

    assert status == 503
    assert payload["error"]["code"] == "source_derived_api_context_required"


def _json_body(body: bytes) -> dict[str, Any]:
    loaded = json.loads(body)
    assert isinstance(loaded, dict)
    return loaded


def _api_context(
    connection: Connection,
    *,
    actor: AuthenticatedActor | None | object = DEFAULT_ACTOR,
    scope: HostedAccessScope = TEST_SCOPE,
) -> SourceDerivedApiContext:
    context_actor = _actor() if actor is DEFAULT_ACTOR else actor
    return SourceDerivedApiContext(
        connection=connection,
        actor=cast(AuthenticatedActor | None, context_actor),
        scope=scope,
    )


def _actor(
    *,
    roles: tuple[str, ...] = ("read_only_tester",),
    scopes: tuple[HostedAccessScope, ...] = (TEST_SCOPE,),
    account_status: str = "active",
    actor_category: str = "tester",
) -> AuthenticatedActor:
    return AuthenticatedActor(
        provider_subject="fixture-subject-read-only",
        provider_issuer="fixture-managed-oidc-provider",
        display_name="Fixture Read Only Tester",
        email="tester@example.invalid",
        actor_category=cast(HostedActorCategory, actor_category),
        account_status=cast(HostedAccountStatus, account_status),
        roles=tuple(cast(HostedTesterRole, role) for role in roles),
        scopes=scopes,
    )


def _seeded_connection() -> Connection:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)
    connection = engine.connect()
    transaction = connection.begin()
    artifact = load_seeded_corpus_artifact(FIXTURE)
    import_seeded_corpus_artifact(connection, artifact)
    transaction.commit()
    return connection


def _insert_corpus_complaint(
    connection: Connection,
    *,
    job_id: str,
    facility_number: str,
    complaint_control_number: str,
) -> str:
    now = "2026-07-01T12:00:00+00:00"
    import_batch_id = retrieval_import_batch_id(job_id)
    facility_id = f"ccld:facility:{facility_number}"
    document_id = f"ccld:document:{facility_number}:1"
    complaint_id = f"ccld:complaint:{complaint_control_number}"
    source_url = (
        "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports"
        f"?facNum={facility_number}&inx=1"
    )
    connection.execute(
        hosted_import_batches.insert().values(
            import_batch_id=import_batch_id,
            imported_at=now,
            source_artifact_identity=f"fixture-artifact:{job_id}",
            source_pipeline_version="fixture-corpus",
            validation_status="validated",
            raw_hash_validation_status="validated",
            record_counts={"complaint": 1},
            warnings=[],
            errors=[],
        )
    )
    source_record_key = f"complaint:{complaint_id}"
    connection.execute(
        hosted_source_derived_records.insert().values(
            source_record_key=source_record_key,
            entity_type="complaint",
            stable_source_id=complaint_id,
            import_batch_id=import_batch_id,
            source_document_id=document_id,
            facility_id=facility_id,
            source_url=source_url,
            raw_sha256="b" * 64,
            raw_path="data/raw/ccld/fixture/report.html",
            connector_name="ccld_facility_reports",
            connector_version="fixture-corpus",
            retrieved_at=now,
            original_values={
                "complaint_id": complaint_id,
                "facility_id": facility_id,
                "document_id": document_id,
                "facility_number": facility_number,
                "complaint_control_number": complaint_control_number,
                "complaint_received_date": "2026-05-08",
                "first_investigation_activity_date": "2026-05-08",
                "visit_date": "2026-05-10",
                "report_date": "2026-05-11",
                "date_signed": "2026-05-12",
                "days_received_to_first_activity": 0,
                "days_received_to_visit": 2,
                "days_received_to_report": 3,
                "days_report_to_signed": 1,
                "finding": "Substantiated",
            },
            source_traceability={
                "source_document_id": document_id,
                "source_url": source_url,
                "raw_sha256": "b" * 64,
                "connector_name": "ccld_facility_reports",
                "retrieved_at": now,
            },
        )
    )
    return source_record_key
