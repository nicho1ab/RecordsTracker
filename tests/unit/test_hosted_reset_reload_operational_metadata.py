from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

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
    SEEDED_CORPUS_RESET_RELOAD_DRY_RUN_API_PATH,
    SeededCorpusResetReloadDryRunContext,
    create_seeded_corpus_reset_reload_planning_metadata,
    get_seeded_corpus_reset_reload_planning_metadata,
    hosted_reset_reload_planning_metadata,
    list_seeded_corpus_reset_reload_planning_metadata,
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


def test_reset_reload_planning_metadata_can_be_persisted_separately() -> None:
    with _seeded_connection() as connection:
        before_counts = _table_counts(connection)

        created = create_seeded_corpus_reset_reload_planning_metadata(
            connection,
            _operator_actor(),
            scope=TEST_SCOPE,
            reviewer_state_mode="archive",
            planning_context={"requested_by": "focused_test"},
        )
        listed = list_seeded_corpus_reset_reload_planning_metadata(
            connection,
            _operator_actor(),
            scope=TEST_SCOPE,
        )
        fetched = get_seeded_corpus_reset_reload_planning_metadata(
            connection,
            _operator_actor(),
            scope=TEST_SCOPE,
            planning_record_id=created.planning_record_id,
        )
        after_counts = _table_counts(connection)

    assert before_counts == {
        "import_batches": 1,
        "source_records": 6,
        "reviewer_created_state": 0,
        "audit_events": 0,
        "reset_reload_planning_metadata": 0,
    }
    assert after_counts == {
        **before_counts,
        "reset_reload_planning_metadata": 1,
    }
    assert listed == (created,)
    assert fetched == created
    assert created.planning_record_id.startswith("reset-reload-plan:")
    assert created.operation == "seeded_corpus_reset_reload_dry_run"
    assert created.requested_operation_mode == "dry_run"
    assert created.scope == TEST_SCOPE
    assert created.reviewer_state_handling_mode == "archive"
    assert created.actor_provider_subject == "fixture-subject-operator"
    assert created.actor_provider_issuer == "fixture-managed-oidc-provider"
    assert created.actor_display_name == "Fixture Operator"
    assert created.actor_category == "operator"
    assert created.authorization_permission == "import_reload"
    assert created.source_derived_summary["existing_source_derived_record_count"] == 6
    assert created.reviewer_created_state_summary["selected_handling_mode"] == "archive"
    assert created.audit_event_summary["current_event_count"] == 0
    assert "validation_requirements" in created.validation_summary
    assert created.planning_context == {"requested_by": "focused_test"}
    assert created.future_execution_permissions == ("import_reload",)
    assert "import or reload seeded corpus artifacts" in created.deferred_actions
    assert created.data_mutations_performed is False


def test_reset_reload_dry_run_without_persistence_does_not_create_metadata() -> None:
    with _seeded_connection() as connection:
        before_counts = _table_counts(connection)
        status, _content_type, body = route_response(
            SEEDED_CORPUS_RESET_RELOAD_DRY_RUN_API_PATH,
            reset_reload_dry_run_context=_dry_run_context(connection),
        )
        after_counts = _table_counts(connection)

    payload = _json_body(body)

    assert status == 200
    assert before_counts == after_counts
    assert "operational_metadata" not in payload
    assert payload["safety"] == {
        "data_mutations_performed": False,
        "queries_only": True,
        "dry_run_does_not_execute_reset_reload": True,
    }


def test_reset_reload_dry_run_persists_metadata_only_when_explicitly_requested() -> None:
    path = f"{SEEDED_CORPUS_RESET_RELOAD_DRY_RUN_API_PATH}?persist_planning_metadata=true"
    with _seeded_connection() as connection:
        before_counts = _table_counts(connection)
        status, _content_type, body = route_response(
            path,
            reset_reload_dry_run_context=_dry_run_context(connection),
        )
        after_counts = _table_counts(connection)
        [persisted] = list_seeded_corpus_reset_reload_planning_metadata(
            connection,
            _operator_actor(),
            scope=TEST_SCOPE,
        )

    payload = _json_body(body)

    assert status == 200
    assert after_counts == {
        **before_counts,
        "reset_reload_planning_metadata": 1,
    }
    assert before_counts["import_batches"] == after_counts["import_batches"] == 1
    assert before_counts["source_records"] == after_counts["source_records"] == 6
    assert before_counts["reviewer_created_state"] == after_counts["reviewer_created_state"] == 0
    assert before_counts["audit_events"] == after_counts["audit_events"] == 0
    assert payload["operational_metadata"] == {
        "persisted": True,
        "planning_record_id": persisted.planning_record_id,
        "generated_at": persisted.generated_at,
        "requested_operation_mode": "dry_run",
        "reviewer_state_handling_mode": "preserve",
    }
    assert persisted.planning_context == {
        "persisted_from": "reset_reload_dry_run_route",
        "route_path": SEEDED_CORPUS_RESET_RELOAD_DRY_RUN_API_PATH,
    }


def test_reset_reload_planning_metadata_records_clear_mode_as_planning_only() -> None:
    with _seeded_connection() as connection:
        created = create_seeded_corpus_reset_reload_planning_metadata(
            connection,
            _admin_actor(),
            scope=TEST_SCOPE,
            reviewer_state_mode="clear",
            planning_context={"requested_by": "admin_fixture"},
        )
        counts = _table_counts(connection)

    assert created.reviewer_state_handling_mode == "clear"
    assert created.future_execution_permissions == (
        "import_reload",
        "reset_destructive",
    )
    assert created.data_mutations_performed is False
    assert counts == {
        "import_batches": 1,
        "source_records": 6,
        "reviewer_created_state": 0,
        "audit_events": 0,
        "reset_reload_planning_metadata": 1,
    }


def test_reset_reload_planning_metadata_rejects_unauthenticated_actor() -> None:
    with _seeded_connection() as connection:
        with pytest.raises(PermissionError, match="authenticated actor"):
            create_seeded_corpus_reset_reload_planning_metadata(
                connection,
                None,
                scope=TEST_SCOPE,
                planning_context={"requested_by": "focused_test"},
            )

        assert _table_counts(connection)["reset_reload_planning_metadata"] == 0


@pytest.mark.parametrize("account_status", ["disabled", "revoked"])
def test_reset_reload_planning_metadata_rejects_disabled_or_revoked_actor(
    account_status: str,
) -> None:
    with _seeded_connection() as connection:
        with pytest.raises(PermissionError, match="disabled or revoked"):
            create_seeded_corpus_reset_reload_planning_metadata(
                connection,
                _operator_actor(account_status=account_status),
                scope=TEST_SCOPE,
                planning_context={"requested_by": "focused_test"},
            )

        assert _table_counts(connection)["reset_reload_planning_metadata"] == 0


def test_reset_reload_planning_metadata_rejects_role_denied_actor() -> None:
    with _seeded_connection() as connection:
        with pytest.raises(PermissionError, match="import_reload"):
            create_seeded_corpus_reset_reload_planning_metadata(
                connection,
                _read_only_actor(),
                scope=TEST_SCOPE,
                planning_context={"requested_by": "focused_test"},
            )

        assert _table_counts(connection)["reset_reload_planning_metadata"] == 0


def test_reset_reload_planning_metadata_rejects_out_of_scope_actor() -> None:
    with _seeded_connection() as connection:
        with pytest.raises(PermissionError, match="project or corpus scope"):
            create_seeded_corpus_reset_reload_planning_metadata(
                connection,
                _operator_actor(scopes=(OTHER_SCOPE,)),
                scope=TEST_SCOPE,
                planning_context={"requested_by": "focused_test"},
            )

        assert _table_counts(connection)["reset_reload_planning_metadata"] == 0


def test_reset_reload_planning_metadata_rejects_invalid_mode_before_persistence() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            f"{SEEDED_CORPUS_RESET_RELOAD_DRY_RUN_API_PATH}"
            "?reviewer_state_mode=delete&persist_planning_metadata=true",
            reset_reload_dry_run_context=_dry_run_context(connection),
        )

        assert _table_counts(connection)["reset_reload_planning_metadata"] == 0

    payload = _json_body(body)

    assert status == 400
    assert payload["error"]["code"] == "invalid_request"
    assert "reviewer_state_mode" in payload["error"]["message"]


def test_reset_reload_planning_metadata_rejects_invalid_persistence_option() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            f"{SEEDED_CORPUS_RESET_RELOAD_DRY_RUN_API_PATH}"
            "?persist_planning_metadata=yes",
            reset_reload_dry_run_context=_dry_run_context(connection),
        )

        assert _table_counts(connection)["reset_reload_planning_metadata"] == 0

    payload = _json_body(body)

    assert status == 400
    assert payload["error"]["code"] == "invalid_request"
    assert "persist_planning_metadata" in payload["error"]["message"]


def test_reset_reload_planning_metadata_rejects_secret_like_context() -> None:
    with _seeded_connection() as connection:
        with pytest.raises(ValueError, match="secret-like"):
            create_seeded_corpus_reset_reload_planning_metadata(
                connection,
                _operator_actor(),
                scope=TEST_SCOPE,
                planning_context={"token": "do-not-store"},
            )

        assert _table_counts(connection)["reset_reload_planning_metadata"] == 0


def test_reset_reload_planning_metadata_stores_non_secret_context_only() -> None:
    with _seeded_connection() as connection:
        created = create_seeded_corpus_reset_reload_planning_metadata(
            connection,
            _operator_actor(),
            scope=TEST_SCOPE,
            planning_context={"requested_by": "focused_test"},
        )

    serialized_context = str(dict(created.planning_context)).casefold()

    assert "token" not in serialized_context
    assert "cookie" not in serialized_context
    assert "connection" not in serialized_context
    assert "private" not in serialized_context
    assert "secret" not in serialized_context
    assert "operator@example.invalid" not in serialized_context


def _json_body(body: bytes) -> dict[str, Any]:
    loaded = json.loads(body)
    assert isinstance(loaded, dict)
    return loaded


def _dry_run_context(
    connection: Connection,
    *,
    actor: AuthenticatedActor | None | object = DEFAULT_ACTOR,
    scope: HostedAccessScope = TEST_SCOPE,
) -> SeededCorpusResetReloadDryRunContext:
    context_actor = _operator_actor() if actor is DEFAULT_ACTOR else actor
    return SeededCorpusResetReloadDryRunContext(
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