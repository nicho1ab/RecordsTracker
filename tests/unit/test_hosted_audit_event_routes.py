from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Connection

from ccld_complaints.hosted_app.app import route_response
from ccld_complaints.hosted_app.audit_event_routes import AuditEventsApiContext
from ccld_complaints.hosted_app.audit_events import hosted_audit_events
from ccld_complaints.hosted_app.auth import (
    AuthenticatedActor,
    HostedAccessScope,
    HostedAccountStatus,
    HostedActorCategory,
    HostedTesterRole,
)
from ccld_complaints.hosted_app.reviewer_created_state import (
    create_reviewer_created_state_scaffold,
    hosted_reviewer_created_state,
)
from ccld_complaints.hosted_app.seeded_import import (
    hosted_import_batches,
    hosted_seeded_import_metadata,
    hosted_source_derived_records,
    import_seeded_corpus_artifact,
    load_seeded_corpus_artifact,
)

FIXTURE = Path("tests/fixtures/hosted_seeded_corpus/validated_seeded_corpus.json")
TEST_SCOPE = HostedAccessScope("seeded_corpus", "seeded-ccld-fixture-2026-06-13")
OTHER_SCOPE = HostedAccessScope("seeded_corpus", "different-seeded-corpus")
COMPLAINT_KEY = "complaint:ccld:complaint:32-CR-20220407124448"
DEFAULT_ACTOR = object()


def test_audit_events_api_lists_authenticated_audit_history() -> None:
    with _seeded_connection() as connection:
        created = create_reviewer_created_state_scaffold(
            connection,
            _reviewer_actor(),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            state_payload={"scaffold_state": "in_review"},
        )

        status, content_type, body = route_response(
            "/api/audit-events",
            audit_events_api_context=_api_context(connection),
        )

    payload = _json_body(body)

    assert status == 200
    assert content_type == "application/json; charset=utf-8"
    assert payload["pagination"] == {"limit": 100, "offset": 0, "returned_count": 1}
    [audit_event] = payload["audit_events"]
    assert audit_event["audit_event_id"].startswith("audit-event:")
    assert audit_event["occurred_at"] == created.created_at
    assert audit_event["actor"] == {
        "provider_subject": "fixture-subject-reviewer",
        "provider_issuer": "fixture-managed-oidc-provider",
        "display_name": "Fixture Tester Reviewer",
        "actor_category": "tester",
    }
    assert audit_event["authorization_permission"] == "reviewer_state_write"
    assert audit_event["scope"] == {
        "scope_type": "seeded_corpus",
        "scope_id": TEST_SCOPE.scope_id,
    }
    assert audit_event["action"] == "reviewer_created_state_scaffold.create"
    assert audit_event["target"] == {
        "target_type": "reviewer_created_state",
        "target_reviewer_state_id": created.reviewer_state_id,
    }
    assert audit_event["source"] == {
        "source_record_key": COMPLAINT_KEY,
        "source_entity_type": "complaint",
        "source_stable_source_id": "ccld:complaint:32-CR-20220407124448",
        "source_document_id": "ccld:document:157806098:3",
    }
    assert audit_event["context_metadata"] == {
        "state_kind": "review_item_state_scaffold",
        "state_payload_keys": ["scaffold_state"],
        "source_record_key": COMPLAINT_KEY,
    }
    serialized_body = body.decode("utf-8").casefold()
    assert "token" not in serialized_body
    assert "cookie" not in serialized_body
    assert "tester@example.invalid" not in serialized_body


def test_audit_events_api_fetches_one_authorized_event_by_id() -> None:
    with _seeded_connection() as connection:
        create_reviewer_created_state_scaffold(
            connection,
            _reviewer_actor(),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            state_payload={"scaffold_state": "in_review"},
        )
        [audit_event_id] = connection.execute(
            select(hosted_audit_events.c.audit_event_id)
        ).scalars()

        status, _content_type, body = route_response(
            f"/api/audit-events/by-id?audit_event_id={quote(audit_event_id)}",
            audit_events_api_context=_api_context(connection),
        )

    payload = _json_body(body)

    assert status == 200
    assert payload["audit_event"]["audit_event_id"] == audit_event_id
    assert payload["audit_event"]["source"]["source_record_key"] == COMPLAINT_KEY


def test_audit_events_api_returns_empty_history_for_scope_without_events() -> None:
    with _empty_connection() as connection:
        status, _content_type, body = route_response(
            "/api/audit-events",
            audit_events_api_context=_api_context(connection),
        )

    payload = _json_body(body)

    assert status == 200
    assert payload["audit_events"] == []
    assert payload["pagination"] == {"limit": 100, "offset": 0, "returned_count": 0}


def test_audit_events_api_returns_not_found_for_missing_event() -> None:
    with _empty_connection() as connection:
        status, _content_type, body = route_response(
            "/api/audit-events/by-id?audit_event_id=audit-event:missing",
            audit_events_api_context=_api_context(connection),
        )

    payload = _json_body(body)

    assert status == 404
    assert payload["error"]["code"] == "audit_event_not_found"


def test_audit_events_api_filters_without_crossing_audit_boundaries() -> None:
    with _seeded_connection() as connection:
        first = create_reviewer_created_state_scaffold(
            connection,
            _reviewer_actor(),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            state_payload={"scaffold_state": "in_review"},
        )
        second = create_reviewer_created_state_scaffold(
            connection,
            _admin_actor(),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            state_payload={"scaffold_state": "source_check_needed"},
        )

        by_actor_status, _content_type, by_actor_body = route_response(
            "/api/audit-events?actor_provider_subject=fixture-subject-admin",
            audit_events_api_context=_api_context(connection),
        )
        by_target_status, _content_type, by_target_body = route_response(
            "/api/audit-events"
            f"?target_reviewer_state_id={quote(first.reviewer_state_id)}",
            audit_events_api_context=_api_context(connection),
        )
        by_source_status, _content_type, by_source_body = route_response(
            "/api/audit-events"
            f"?source_record_key={quote(COMPLAINT_KEY)}"
            "&action=reviewer_created_state_scaffold.create"
            "&source_entity_type=complaint"
            "&source_stable_source_id=ccld%3Acomplaint%3A32-CR-20220407124448"
            "&source_document_id=ccld%3Adocument%3A157806098%3A3",
            audit_events_api_context=_api_context(connection),
        )

    by_actor_payload = _json_body(by_actor_body)
    by_target_payload = _json_body(by_target_body)
    by_source_payload = _json_body(by_source_body)

    assert by_actor_status == 200
    assert [
        event["target"]["target_reviewer_state_id"]
        for event in by_actor_payload["audit_events"]
    ] == [second.reviewer_state_id]
    assert by_target_status == 200
    assert [
        event["target"]["target_reviewer_state_id"]
        for event in by_target_payload["audit_events"]
    ] == [first.reviewer_state_id]
    assert by_source_status == 200
    assert by_source_payload["pagination"]["returned_count"] == 2


def test_audit_events_api_rejects_unauthenticated_actor() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            "/api/audit-events",
            audit_events_api_context=_api_context(connection, actor=None),
        )

    payload = _json_body(body)
    assert status == 401
    assert payload["error"]["code"] == "authentication_required"


@pytest.mark.parametrize("account_status", ["disabled", "revoked"])
def test_audit_events_api_rejects_disabled_or_revoked_actor(
    account_status: str,
) -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            "/api/audit-events",
            audit_events_api_context=_api_context(
                connection,
                actor=_operator_actor(account_status=account_status),
            ),
        )

    payload = _json_body(body)
    assert status == 403
    assert payload["error"]["code"] == "account_disabled_or_revoked"


def test_audit_events_api_rejects_role_without_audit_read_permission() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            "/api/audit-events",
            audit_events_api_context=_api_context(connection, actor=_read_only_actor()),
        )

    payload = _json_body(body)
    assert status == 403
    assert payload["error"]["code"] == "role_denied"


def test_audit_events_api_rejects_out_of_scope_actor() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            "/api/audit-events",
            audit_events_api_context=_api_context(
                connection,
                actor=_operator_actor(scopes=(OTHER_SCOPE,)),
            ),
        )

    payload = _json_body(body)
    assert status == 403
    assert payload["error"]["code"] == "scope_denied"


def test_audit_events_api_rejects_invalid_filter_and_paging_values() -> None:
    with _seeded_connection() as connection:
        invalid_action_status, _content_type, invalid_action_body = route_response(
            "/api/audit-events?action=reset_reload.execute",
            audit_events_api_context=_api_context(connection),
        )
        invalid_limit_status, _content_type, invalid_limit_body = route_response(
            "/api/audit-events?limit=0",
            audit_events_api_context=_api_context(connection),
        )

    invalid_action_payload = _json_body(invalid_action_body)
    invalid_limit_payload = _json_body(invalid_limit_body)

    assert invalid_action_status == 400
    assert invalid_action_payload["error"]["code"] == "invalid_request"
    assert invalid_limit_status == 400
    assert invalid_limit_payload["error"]["code"] == "invalid_request"


def test_audit_events_api_requires_explicit_local_test_context() -> None:
    status, _content_type, body = route_response("/api/audit-events")

    payload = _json_body(body)

    assert status == 503
    assert payload["error"]["code"] == "audit_events_api_context_required"


def test_audit_events_api_reads_do_not_mutate_persisted_tables() -> None:
    with _seeded_connection() as connection:
        create_reviewer_created_state_scaffold(
            connection,
            _reviewer_actor(),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            state_payload={"scaffold_state": "in_review"},
        )
        [audit_event_id] = connection.execute(
            select(hosted_audit_events.c.audit_event_id)
        ).scalars()
        before_counts = _table_counts(connection)

        list_status, _content_type, _list_body = route_response(
            "/api/audit-events",
            audit_events_api_context=_api_context(connection),
        )
        fetch_status, _content_type, _fetch_body = route_response(
            f"/api/audit-events/by-id?audit_event_id={quote(audit_event_id)}",
            audit_events_api_context=_api_context(connection),
        )
        after_counts = _table_counts(connection)

    assert list_status == 200
    assert fetch_status == 200
    assert before_counts == after_counts == {
        "import_batches": 1,
        "source_records": 6,
        "reviewer_created_state": 1,
        "audit_events": 1,
    }


def _json_body(body: bytes) -> dict[str, Any]:
    loaded = json.loads(body)
    assert isinstance(loaded, dict)
    return loaded


def _api_context(
    connection: Connection,
    *,
    actor: AuthenticatedActor | None | object = DEFAULT_ACTOR,
    scope: HostedAccessScope = TEST_SCOPE,
) -> AuditEventsApiContext:
    context_actor = _operator_actor() if actor is DEFAULT_ACTOR else actor
    return AuditEventsApiContext(
        connection=connection,
        actor=cast(AuthenticatedActor | None, context_actor),
        scope=scope,
    )


def _reviewer_actor() -> AuthenticatedActor:
    return _actor(
        roles=("tester_reviewer",),
        actor_category="tester",
        provider_subject="fixture-subject-reviewer",
        display_name="Fixture Tester Reviewer",
        email="tester@example.invalid",
    )


def _read_only_actor() -> AuthenticatedActor:
    return _actor(
        roles=("read_only_tester",),
        actor_category="tester",
        provider_subject="fixture-subject-read-only",
        display_name="Fixture Read Only Tester",
        email="read-only@example.invalid",
    )


def _operator_actor(
    *,
    scopes: tuple[HostedAccessScope, ...] = (TEST_SCOPE,),
    account_status: str = "active",
) -> AuthenticatedActor:
    return _actor(
        roles=("developer_operator",),
        scopes=scopes,
        account_status=account_status,
        actor_category="operator",
        provider_subject="fixture-subject-operator",
        display_name="Fixture Operator",
        email="operator@example.invalid",
    )


def _admin_actor() -> AuthenticatedActor:
    return _actor(
        roles=("admin",),
        actor_category="admin",
        provider_subject="fixture-subject-admin",
        display_name="Fixture Admin",
        email="admin@example.invalid",
    )


def _actor(
    *,
    roles: tuple[str, ...],
    scopes: tuple[HostedAccessScope, ...] = (TEST_SCOPE,),
    account_status: str = "active",
    actor_category: str,
    provider_subject: str,
    display_name: str,
    email: str,
) -> AuthenticatedActor:
    return AuthenticatedActor(
        provider_subject=provider_subject,
        provider_issuer="fixture-managed-oidc-provider",
        display_name=display_name,
        email=email,
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


def _table_counts(connection: Connection) -> dict[str, int]:
    import_batches = connection.execute(
        select(func.count()).select_from(hosted_import_batches)
    ).scalar_one()
    source_records = connection.execute(
        select(func.count()).select_from(hosted_source_derived_records)
    ).scalar_one()
    reviewer_created_state = connection.execute(
        select(func.count()).select_from(hosted_reviewer_created_state)
    ).scalar_one()
    audit_events = connection.execute(
        select(func.count()).select_from(hosted_audit_events)
    ).scalar_one()
    return {
        "import_batches": import_batches,
        "source_records": source_records,
        "reviewer_created_state": reviewer_created_state,
        "audit_events": audit_events,
    }