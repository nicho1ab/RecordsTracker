from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Connection

from ccld_complaints.hosted_app.app import route_response
from ccld_complaints.hosted_app.audit_events import hosted_audit_events
from ccld_complaints.hosted_app.auth import (
    AuthenticatedActor,
    HostedAccessScope,
    HostedAccountStatus,
    HostedActorCategory,
    HostedTesterRole,
)
from ccld_complaints.hosted_app.reset_reload_dry_run import (
    create_seeded_corpus_reset_reload_planning_metadata,
    hosted_reset_reload_planning_metadata,
)
from ccld_complaints.hosted_app.reset_reload_planning_routes import (
    RESET_RELOAD_PLANNING_METADATA_API_PREFIX,
    ResetReloadPlanningMetadataApiContext,
)
from ccld_complaints.hosted_app.reviewer_created_state import (
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
DEFAULT_ACTOR = object()


def test_reset_reload_planning_metadata_api_lists_authorized_records() -> None:
    with _seeded_connection() as connection:
        first = create_seeded_corpus_reset_reload_planning_metadata(
            connection,
            _operator_actor(),
            scope=TEST_SCOPE,
            reviewer_state_mode="archive",
            planning_context={"requested_by": "operator_fixture"},
        )
        second = create_seeded_corpus_reset_reload_planning_metadata(
            connection,
            _admin_actor(),
            scope=TEST_SCOPE,
            reviewer_state_mode="clear",
            planning_context={"requested_by": "admin_fixture"},
        )

        status, content_type, body = route_response(
            RESET_RELOAD_PLANNING_METADATA_API_PREFIX,
            reset_reload_planning_metadata_api_context=_api_context(connection),
        )

    payload = _json_body(body)

    assert status == 200
    assert content_type == "application/json; charset=utf-8"
    assert payload["pagination"] == {"limit": 100, "offset": 0, "returned_count": 2}
    assert payload["filters"] == {
        "reviewer_state_handling_mode": None,
        "actor_provider_subject": None,
        "requested_operation_mode": None,
    }
    planning_ids = {record["planning_record_id"] for record in payload["planning_metadata"]}
    assert planning_ids == {first.planning_record_id, second.planning_record_id}
    archive_record = next(
        record
        for record in payload["planning_metadata"]
        if record["planning_record_id"] == first.planning_record_id
    )
    assert archive_record["operation"] == "seeded_corpus_reset_reload_dry_run"
    assert archive_record["requested_operation_mode"] == "dry_run"
    assert archive_record["scope"] == {
        "scope_type": "seeded_corpus",
        "scope_id": TEST_SCOPE.scope_id,
    }
    assert archive_record["reviewer_state_handling_mode"] == "archive"
    assert archive_record["actor"] == {
        "provider_subject": "fixture-subject-operator",
        "provider_issuer": "fixture-managed-oidc-provider",
        "display_name": "Fixture Operator",
        "actor_category": "operator",
    }
    assert archive_record["authorization_permission"] == "import_reload"
    assert archive_record["source_derived_summary"]["existing_source_derived_record_count"] == 6
    assert archive_record["reviewer_created_state_summary"]["selected_handling_mode"] == (
        "archive"
    )
    assert archive_record["audit_event_summary"]["current_event_count"] == 0
    assert archive_record["planning_context"] == {"requested_by": "operator_fixture"}
    assert archive_record["safety"] == {
        "data_mutations_performed": False,
        "read_only_route": True,
        "does_not_execute_reset_reload": True,
    }
    serialized_body = body.decode("utf-8").casefold()
    assert "token" not in serialized_body
    assert "cookie" not in serialized_body
    assert "operator@example.invalid" not in serialized_body


def test_reset_reload_planning_metadata_api_fetches_one_record_by_id() -> None:
    with _seeded_connection() as connection:
        created = create_seeded_corpus_reset_reload_planning_metadata(
            connection,
            _operator_actor(),
            scope=TEST_SCOPE,
            planning_context={"requested_by": "operator_fixture"},
        )

        status, _content_type, body = route_response(
            f"{RESET_RELOAD_PLANNING_METADATA_API_PREFIX}/by-id"
            f"?planning_record_id={quote(created.planning_record_id)}",
            reset_reload_planning_metadata_api_context=_api_context(connection),
        )

    payload = _json_body(body)

    assert status == 200
    assert payload["planning_metadata"]["planning_record_id"] == created.planning_record_id
    assert payload["planning_metadata"]["requested_operation_mode"] == "dry_run"


def test_reset_reload_planning_metadata_api_returns_empty_history() -> None:
    with _empty_connection() as connection:
        status, _content_type, body = route_response(
            RESET_RELOAD_PLANNING_METADATA_API_PREFIX,
            reset_reload_planning_metadata_api_context=_api_context(connection),
        )

    payload = _json_body(body)

    assert status == 200
    assert payload["planning_metadata"] == []
    assert payload["pagination"] == {"limit": 100, "offset": 0, "returned_count": 0}


def test_reset_reload_planning_metadata_api_returns_not_found_for_missing_record() -> None:
    with _empty_connection() as connection:
        status, _content_type, body = route_response(
            f"{RESET_RELOAD_PLANNING_METADATA_API_PREFIX}/by-id"
            "?planning_record_id=reset-reload-plan:missing",
            reset_reload_planning_metadata_api_context=_api_context(connection),
        )

    payload = _json_body(body)

    assert status == 404
    assert payload["error"]["code"] == "reset_reload_planning_metadata_not_found"


def test_reset_reload_planning_metadata_api_filters_schema_backed_fields() -> None:
    with _seeded_connection() as connection:
        archive = create_seeded_corpus_reset_reload_planning_metadata(
            connection,
            _operator_actor(),
            scope=TEST_SCOPE,
            reviewer_state_mode="archive",
            planning_context={"requested_by": "operator_fixture"},
        )
        clear = create_seeded_corpus_reset_reload_planning_metadata(
            connection,
            _admin_actor(),
            scope=TEST_SCOPE,
            reviewer_state_mode="clear",
            planning_context={"requested_by": "admin_fixture"},
        )

        by_mode_status, _content_type, by_mode_body = route_response(
            f"{RESET_RELOAD_PLANNING_METADATA_API_PREFIX}"
            "?reviewer_state_handling_mode=archive&requested_operation_mode=dry_run",
            reset_reload_planning_metadata_api_context=_api_context(connection),
        )
        by_actor_status, _content_type, by_actor_body = route_response(
            f"{RESET_RELOAD_PLANNING_METADATA_API_PREFIX}"
            "?actor_provider_subject=fixture-subject-admin",
            reset_reload_planning_metadata_api_context=_api_context(connection),
        )

    by_mode_payload = _json_body(by_mode_body)
    by_actor_payload = _json_body(by_actor_body)

    assert by_mode_status == 200
    assert [
        record["planning_record_id"] for record in by_mode_payload["planning_metadata"]
    ] == [archive.planning_record_id]
    assert by_mode_payload["filters"] == {
        "reviewer_state_handling_mode": "archive",
        "actor_provider_subject": None,
        "requested_operation_mode": "dry_run",
    }
    assert by_actor_status == 200
    assert [
        record["planning_record_id"] for record in by_actor_payload["planning_metadata"]
    ] == [clear.planning_record_id]


def test_reset_reload_planning_metadata_api_rejects_unauthenticated_actor() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            RESET_RELOAD_PLANNING_METADATA_API_PREFIX,
            reset_reload_planning_metadata_api_context=_api_context(connection, actor=None),
        )

    payload = _json_body(body)
    assert status == 401
    assert payload["error"]["code"] == "authentication_required"


@pytest.mark.parametrize("account_status", ["disabled", "revoked"])
def test_reset_reload_planning_metadata_api_rejects_disabled_or_revoked_actor(
    account_status: str,
) -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            RESET_RELOAD_PLANNING_METADATA_API_PREFIX,
            reset_reload_planning_metadata_api_context=_api_context(
                connection,
                actor=_operator_actor(account_status=account_status),
            ),
        )

    payload = _json_body(body)
    assert status == 403
    assert payload["error"]["code"] == "account_disabled_or_revoked"


def test_reset_reload_planning_metadata_api_rejects_role_without_import_reload() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            RESET_RELOAD_PLANNING_METADATA_API_PREFIX,
            reset_reload_planning_metadata_api_context=_api_context(
                connection,
                actor=_read_only_actor(),
            ),
        )

    payload = _json_body(body)
    assert status == 403
    assert payload["error"]["code"] == "role_denied"


def test_reset_reload_planning_metadata_api_rejects_out_of_scope_actor() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            RESET_RELOAD_PLANNING_METADATA_API_PREFIX,
            reset_reload_planning_metadata_api_context=_api_context(
                connection,
                actor=_operator_actor(scopes=(OTHER_SCOPE,)),
            ),
        )

    payload = _json_body(body)
    assert status == 403
    assert payload["error"]["code"] == "scope_denied"


def test_reset_reload_planning_metadata_api_rejects_invalid_filter_and_paging() -> None:
    with _seeded_connection() as connection:
        invalid_mode_status, _content_type, invalid_mode_body = route_response(
            f"{RESET_RELOAD_PLANNING_METADATA_API_PREFIX}"
            "?reviewer_state_handling_mode=delete",
            reset_reload_planning_metadata_api_context=_api_context(connection),
        )
        invalid_operation_status, _content_type, invalid_operation_body = route_response(
            f"{RESET_RELOAD_PLANNING_METADATA_API_PREFIX}"
            "?requested_operation_mode=execute",
            reset_reload_planning_metadata_api_context=_api_context(connection),
        )
        invalid_limit_status, _content_type, invalid_limit_body = route_response(
            f"{RESET_RELOAD_PLANNING_METADATA_API_PREFIX}?limit=0",
            reset_reload_planning_metadata_api_context=_api_context(connection),
        )

    assert invalid_mode_status == 400
    assert _json_body(invalid_mode_body)["error"]["code"] == "invalid_request"
    assert invalid_operation_status == 400
    assert _json_body(invalid_operation_body)["error"]["code"] == "invalid_request"
    assert invalid_limit_status == 400
    assert _json_body(invalid_limit_body)["error"]["code"] == "invalid_request"


def test_reset_reload_planning_metadata_api_requires_explicit_context() -> None:
    status, _content_type, body = route_response(RESET_RELOAD_PLANNING_METADATA_API_PREFIX)

    payload = _json_body(body)

    assert status == 503
    assert payload["error"]["code"] == (
        "reset_reload_planning_metadata_api_context_required"
    )


def test_reset_reload_planning_metadata_api_reads_do_not_mutate_persisted_tables() -> None:
    with _seeded_connection() as connection:
        created = create_seeded_corpus_reset_reload_planning_metadata(
            connection,
            _operator_actor(),
            scope=TEST_SCOPE,
            planning_context={"requested_by": "operator_fixture"},
        )
        before_counts = _table_counts(connection)

        list_status, _content_type, _list_body = route_response(
            RESET_RELOAD_PLANNING_METADATA_API_PREFIX,
            reset_reload_planning_metadata_api_context=_api_context(connection),
        )
        fetch_status, _content_type, _fetch_body = route_response(
            f"{RESET_RELOAD_PLANNING_METADATA_API_PREFIX}/by-id"
            f"?planning_record_id={quote(created.planning_record_id)}",
            reset_reload_planning_metadata_api_context=_api_context(connection),
        )
        after_counts = _table_counts(connection)

    assert list_status == 200
    assert fetch_status == 200
    assert before_counts == after_counts == {
        "import_batches": 1,
        "source_records": 6,
        "reviewer_created_state": 0,
        "audit_events": 0,
        "reset_reload_planning_metadata": 1,
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
) -> ResetReloadPlanningMetadataApiContext:
    context_actor = _operator_actor() if actor is DEFAULT_ACTOR else actor
    return ResetReloadPlanningMetadataApiContext(
        connection=connection,
        actor=cast(AuthenticatedActor | None, context_actor),
        scope=scope,
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
        scopes=(TEST_SCOPE,),
        account_status="active",
        actor_category="admin",
        provider_subject="fixture-subject-admin",
        display_name="Fixture Admin",
        email="admin@example.invalid",
    )


def _read_only_actor() -> AuthenticatedActor:
    return _actor(
        roles=("read_only_tester",),
        scopes=(TEST_SCOPE,),
        account_status="active",
        actor_category="tester",
        provider_subject="fixture-subject-read-only",
        display_name="Fixture Read Only Tester",
        email="read-only@example.invalid",
    )


def _actor(
    *,
    roles: tuple[str, ...],
    scopes: tuple[HostedAccessScope, ...],
    account_status: str,
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
    reset_reload_planning_metadata = connection.execute(
        select(func.count()).select_from(hosted_reset_reload_planning_metadata)
    ).scalar_one()
    return {
        "import_batches": import_batches,
        "source_records": source_records,
        "reviewer_created_state": reviewer_created_state,
        "audit_events": audit_events,
        "reset_reload_planning_metadata": reset_reload_planning_metadata,
    }