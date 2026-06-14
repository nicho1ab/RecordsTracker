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
    AuthenticatedActor,
    HostedAccessScope,
    HostedAccountStatus,
    HostedActorCategory,
    HostedTesterRole,
)
from ccld_complaints.hosted_app.seeded_import import (
    hosted_seeded_import_metadata,
    import_seeded_corpus_artifact,
    load_seeded_corpus_artifact,
)
from ccld_complaints.hosted_app.source_derived_routes import SourceDerivedApiContext

FIXTURE = Path("tests/fixtures/hosted_seeded_corpus/validated_seeded_corpus.json")
TEST_SCOPE = HostedAccessScope("seeded_corpus", "seeded-ccld-fixture-2026-06-13")
OTHER_SCOPE = HostedAccessScope("seeded_corpus", "different-seeded-corpus")
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
    assert payload["pagination"] == {"limit": 100, "offset": 0, "returned_count": 6}
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
    assert complaint["source_traceability"]["source_artifact_identity"] == FIXTURE.as_posix()
    assert complaint["import_batch"]["import_batch_id"] == TEST_SCOPE.scope_id
    assert "review_status" not in complaint["original_values"]
    assert "annotation" not in complaint["original_values"]


def test_source_derived_api_supports_entity_filter_and_paging() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            "/api/source-derived-records?entity_type=allegation&limit=1&offset=1",
            source_derived_api_context=_api_context(connection),
        )

    payload = _json_body(body)

    assert status == 200
    assert payload["filters"] == {"entity_type": "allegation"}
    assert payload["pagination"] == {"limit": 1, "offset": 1, "returned_count": 1}
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