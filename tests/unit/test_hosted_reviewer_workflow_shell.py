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
from ccld_complaints.hosted_app.reviewer_workflow_shell import (
    ReviewerWorkflowShellContext,
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


def test_reviewer_workflow_shell_lists_authenticated_review_queue() -> None:
    with _seeded_connection() as connection:
        status, content_type, body = route_response(
            "/api/reviewer/source-derived-review/queue?limit=10",
            reviewer_workflow_shell_context=_workflow_context(connection),
        )

    payload = _json_body(body)

    assert status == 200
    assert content_type == "application/json; charset=utf-8"
    assert payload["workflow_shell"]["workflow_id"] == (
        "authenticated-source-derived-review-shell"
    )
    assert payload["workflow_shell"]["scope"] == {
        "scope_type": "seeded_corpus",
        "scope_id": TEST_SCOPE.scope_id,
    }
    assert payload["workflow_shell"]["reviewer_created_state_persistence"] is False
    assert payload["workflow_shell"]["reviewer_actions_enabled"] == []
    assert payload["queue"]["empty"] is False
    assert payload["queue"]["pagination"] == {
        "limit": 10,
        "offset": 0,
        "returned_count": 1,
    }
    assert payload["queue"]["filters"] == {"entity_type": "complaint"}
    [item] = payload["queue"]["records"]
    source_record = item["source_record"]
    assert source_record["identity"] == {
        "source_record_key": COMPLAINT_KEY,
        "entity_type": "complaint",
        "stable_source_id": COMPLAINT_STABLE_ID,
        "facility_id": "ccld:facility:157806098",
    }
    assert source_record["source_document"]["source_document_id"] == (
        "ccld:document:157806098:3"
    )
    assert source_record["source_document"]["source_url"].startswith(
        "https://www.ccld.dss.ca.gov/"
    )
    assert source_record["source_document"]["raw_sha256"] == (
        "6088c9627374baac647e2f2a54f6e389cb68c1b92db42da00020aaf508a853bd"
    )
    assert source_record["source_document"]["connector_name"] == "ccld_facility_reports"
    assert source_record["original_values"]["finding"] == "Unsubstantiated"
    assert source_record["source_traceability"]["source_artifact_identity"] == (
        FIXTURE.as_posix()
    )
    assert source_record["import_batch"]["import_batch_id"] == TEST_SCOPE.scope_id
    assert item["reviewer_created_state_boundary"] == {
        "persistence_enabled": False,
        "reads_create_or_modify_state": False,
        "anonymous_reviewer_created_state_allowed": False,
        "available_actions": [],
        "deferred_actions": [
            "queue state persistence",
            "review status changes",
            "annotations",
            "correction proposals",
            "tester feedback",
            "export packet decisions",
        ],
    }
    assert "review_status" not in source_record["original_values"]
    assert "annotation" not in source_record["original_values"]


def test_reviewer_workflow_shell_fetches_authenticated_detail() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            "/api/reviewer/source-derived-review/detail"
            f"?source_record_key={quote(COMPLAINT_KEY)}",
            reviewer_workflow_shell_context=_workflow_context(connection),
        )

    payload = _json_body(body)

    assert status == 200
    assert payload["detail"]["detail_id"] == (
        f"source-derived-review-detail-shell:{COMPLAINT_KEY}"
    )
    assert payload["detail"]["source_record"]["identity"]["source_record_key"] == (
        COMPLAINT_KEY
    )
    assert payload["detail"]["source_record"]["import_batch"][
        "validation_status"
    ] == "validated"
    assert payload["detail"]["reviewer_created_state_boundary"][
        "persistence_enabled"
    ] is False


def test_reviewer_workflow_shell_rejects_unauthenticated_actor() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            "/api/reviewer/source-derived-review/queue",
            reviewer_workflow_shell_context=_workflow_context(connection, actor=None),
        )

    payload = _json_body(body)

    assert status == 401
    assert payload["error"]["code"] == "authentication_required"


@pytest.mark.parametrize("account_status", ["disabled", "revoked"])
def test_reviewer_workflow_shell_rejects_disabled_or_revoked_actor(
    account_status: str,
) -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            "/api/reviewer/source-derived-review/queue",
            reviewer_workflow_shell_context=_workflow_context(
                connection,
                actor=_actor(account_status=account_status),
            ),
        )

    payload = _json_body(body)

    assert status == 403
    assert payload["error"]["code"] == "account_disabled_or_revoked"


def test_reviewer_workflow_shell_rejects_role_without_read_permission() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            "/api/reviewer/source-derived-review/queue",
            reviewer_workflow_shell_context=_workflow_context(
                connection,
                actor=_actor(roles=()),
            ),
        )

    payload = _json_body(body)

    assert status == 403
    assert payload["error"]["code"] == "role_denied"


def test_reviewer_workflow_shell_rejects_out_of_scope_actor() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            "/api/reviewer/source-derived-review/queue",
            reviewer_workflow_shell_context=_workflow_context(
                connection,
                actor=_actor(scopes=(OTHER_SCOPE,)),
            ),
        )

    payload = _json_body(body)

    assert status == 403
    assert payload["error"]["code"] == "scope_denied"


def test_reviewer_workflow_shell_returns_empty_queue_without_seeded_records() -> None:
    with _empty_connection() as connection:
        status, _content_type, body = route_response(
            "/api/reviewer/source-derived-review/queue",
            reviewer_workflow_shell_context=_workflow_context(connection),
        )

    payload = _json_body(body)

    assert status == 200
    assert payload["queue"]["empty"] is True
    assert payload["queue"]["records"] == []
    assert payload["queue"]["pagination"] == {
        "limit": 100,
        "offset": 0,
        "returned_count": 0,
    }


def test_reviewer_workflow_shell_returns_not_found_for_missing_detail() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            "/api/reviewer/source-derived-review/detail?source_record_key=missing-record",
            reviewer_workflow_shell_context=_workflow_context(connection),
        )

    payload = _json_body(body)

    assert status == 404
    assert payload["error"]["code"] == "source_derived_record_not_found"


def test_reviewer_workflow_shell_requires_explicit_local_test_context() -> None:
    status, _content_type, body = route_response("/api/reviewer/source-derived-review/queue")

    payload = _json_body(body)

    assert status == 503
    assert payload["error"]["code"] == "reviewer_workflow_shell_context_required"


def _json_body(body: bytes) -> dict[str, Any]:
    loaded = json.loads(body)
    assert isinstance(loaded, dict)
    return loaded


def _workflow_context(
    connection: Connection,
    *,
    actor: AuthenticatedActor | None | object = DEFAULT_ACTOR,
    scope: HostedAccessScope = TEST_SCOPE,
) -> ReviewerWorkflowShellContext:
    context_actor = _actor() if actor is DEFAULT_ACTOR else actor
    return ReviewerWorkflowShellContext(
        source_derived_api_context=SourceDerivedApiContext(
            connection=connection,
            actor=cast(AuthenticatedActor | None, context_actor),
            scope=scope,
        )
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
    connection = _empty_connection()
    transaction = connection.begin()
    artifact = load_seeded_corpus_artifact(FIXTURE)
    import_seeded_corpus_artifact(connection, artifact)
    transaction.commit()
    return connection


def _empty_connection() -> Connection:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)
    return engine.connect()