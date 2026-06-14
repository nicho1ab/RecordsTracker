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
    hosted_reset_reload_planning_metadata,
    list_seeded_corpus_reset_reload_planning_metadata,
)
from ccld_complaints.hosted_app.reset_reload_execution_plan import (
    SEEDED_CORPUS_RESET_RELOAD_EXECUTION_PLAN_API_PATH,
    SeededCorpusResetReloadExecutionPlanContext,
    plan_seeded_corpus_reset_reload_execution_plan,
)
from ccld_complaints.hosted_app.reviewer_created_state import (
    create_reviewer_note_scaffold,
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


def test_reset_reload_execution_plan_returns_ordered_bounded_plan_without_mutation() -> None:
    with _seeded_connection() as connection:
        _create_reviewer_note(connection)
        before_counts = _table_counts(connection)

        status, content_type, body = route_response(
            SEEDED_CORPUS_RESET_RELOAD_EXECUTION_PLAN_API_PATH,
            reset_reload_execution_plan_context=_execution_plan_context(connection),
        )

        after_counts = _table_counts(connection)

    payload = _json_body(body)

    assert status == 200
    assert content_type == "application/json; charset=utf-8"
    assert before_counts == after_counts == {
        "import_batches": 1,
        "source_records": 6,
        "reviewer_created_state": 1,
        "audit_events": 1,
        "reset_reload_planning_metadata": 0,
    }
    assert payload["execution_plan"] is True
    assert payload["operation"] == "seeded_corpus_reset_reload_execution_plan"
    assert payload["execution_plan_mode"] == "bounded_non_destructive_plan"
    assert payload["authorization"]["permission"] == "import_reload"
    assert payload["source_derived_summary"] == {
        "existing_import_batch_count": 1,
        "existing_source_derived_record_count": 6,
        "counts_by_entity": {
            "facility": 1,
            "source_document": 1,
            "complaint": 1,
            "allegation": 2,
            "event": 0,
            "extraction_audit": 1,
        },
        "import_batch_ids": [TEST_SCOPE.scope_id],
    }
    assert payload["reviewer_created_state_summary"] == {
        "selected_handling_mode": "preserve",
        "handling_options": ["preserve", "archive", "clear"],
        "current_state_count": 1,
    }
    assert payload["audit_event_summary"]["current_event_count"] == 1
    assert payload["operational_planning_metadata_summary"] == {
        "existing_planning_record_count": 0,
        "latest_planning_record": None,
        "planning_metadata_rows_mutated_by_plan": 0,
    }
    assert [step["sequence"] for step in payload["action_plan"]] == list(range(1, 8))
    assert [step["category"] for step in payload["action_plan"]] == [
        "validate requested corpus/scope",
        "verify source-derived import batch readiness",
        "summarize source-derived records",
        "summarize reviewer-created state handling option",
        "summarize audit expectations",
        "summarize operational metadata/planning record behavior",
        "list destructive actions still deferred",
    ]
    assert all(step["data_mutations_performed"] is False for step in payload["action_plan"])
    assert "delete source-derived records" in payload["deferred_actions"]
    assert "import or reload seeded corpus artifacts" in payload["deferred_actions"]
    assert "operational_metadata" not in payload
    assert payload["safety"] == {
        "data_mutations_performed": False,
        "queries_only": True,
        "does_not_execute_reset_reload": True,
        "does_not_run_live_crawling_or_connectors": True,
        "source_derived_rows_mutated": 0,
        "reviewer_created_state_rows_mutated": 0,
        "audit_event_rows_mutated": 0,
        "operational_rows_mutated_except_optional_planning_metadata": 0,
    }


def test_reset_reload_execution_plan_persists_metadata_only_when_requested() -> None:
    path = (
        f"{SEEDED_CORPUS_RESET_RELOAD_EXECUTION_PLAN_API_PATH}"
        "?reviewer_state_mode=archive&persist_planning_metadata=true"
    )
    with _seeded_connection() as connection:
        before_counts = _table_counts(connection)
        status, _content_type, body = route_response(
            path,
            reset_reload_execution_plan_context=_execution_plan_context(connection),
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
        "operation": "seeded_corpus_reset_reload_dry_run",
        "requested_operation_mode": "dry_run",
        "reviewer_state_handling_mode": "archive",
        "data_mutations_performed": False,
        "planning_artifact_kind": "seeded_corpus_reset_reload_execution_plan",
    }
    assert persisted.planning_context == {
        "planning_artifact_kind": "seeded_corpus_reset_reload_execution_plan",
        "persisted_from": "reset_reload_execution_plan_route",
        "route_path": SEEDED_CORPUS_RESET_RELOAD_EXECUTION_PLAN_API_PATH,
        "execution_plan_mode": "bounded_non_destructive_plan",
        "execution_plan_operation": "seeded_corpus_reset_reload_execution_plan",
        "action_plan_step_ids": [
            "validate_requested_corpus_scope",
            "verify_source_derived_import_batch_readiness",
            "summarize_source_derived_records",
            "summarize_reviewer_created_state_handling",
            "summarize_audit_expectations",
            "summarize_operational_metadata_behavior",
            "list_deferred_destructive_actions",
        ],
        "data_mutations_performed": False,
        "reset_reload_executed": False,
    }
    assert payload["safety"]["operational_rows_mutated_except_optional_planning_metadata"] == 1


def test_reset_reload_execution_plan_without_persistence_is_default() -> None:
    with _seeded_connection() as connection:
        before_counts = _table_counts(connection)
        status, _content_type, body = route_response(
            SEEDED_CORPUS_RESET_RELOAD_EXECUTION_PLAN_API_PATH,
            reset_reload_execution_plan_context=_execution_plan_context(connection),
        )
        after_counts = _table_counts(connection)

    payload = _json_body(body)

    assert status == 200
    assert before_counts == after_counts
    assert "operational_metadata" not in payload
    assert payload["safety"]["queries_only"] is True


def test_reset_reload_execution_plan_service_ordering_is_deterministic() -> None:
    with _seeded_connection() as connection:
        first = plan_seeded_corpus_reset_reload_execution_plan(
            connection,
            _operator_actor(),
            scope=TEST_SCOPE,
        )
        second = plan_seeded_corpus_reset_reload_execution_plan(
            connection,
            _operator_actor(),
            scope=TEST_SCOPE,
        )

    assert [step.step_id for step in first.action_plan] == [
        step.step_id for step in second.action_plan
    ] == [
        "validate_requested_corpus_scope",
        "verify_source_derived_import_batch_readiness",
        "summarize_source_derived_records",
        "summarize_reviewer_created_state_handling",
        "summarize_audit_expectations",
        "summarize_operational_metadata_behavior",
        "list_deferred_destructive_actions",
    ]


def test_reset_reload_execution_plan_rejects_unauthenticated_actor() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            SEEDED_CORPUS_RESET_RELOAD_EXECUTION_PLAN_API_PATH,
            reset_reload_execution_plan_context=_execution_plan_context(
                connection,
                actor=None,
            ),
        )

    payload = _json_body(body)

    assert status == 401
    assert payload["error"]["code"] == "authentication_required"


@pytest.mark.parametrize("account_status", ["disabled", "revoked"])
def test_reset_reload_execution_plan_rejects_disabled_or_revoked_actor(
    account_status: str,
) -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            SEEDED_CORPUS_RESET_RELOAD_EXECUTION_PLAN_API_PATH,
            reset_reload_execution_plan_context=_execution_plan_context(
                connection,
                actor=_operator_actor(account_status=account_status),
            ),
        )

    payload = _json_body(body)

    assert status == 403
    assert payload["error"]["code"] == "account_disabled_or_revoked"


def test_reset_reload_execution_plan_rejects_role_denied_actor() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            SEEDED_CORPUS_RESET_RELOAD_EXECUTION_PLAN_API_PATH,
            reset_reload_execution_plan_context=_execution_plan_context(
                connection,
                actor=_read_only_actor(),
            ),
        )

    payload = _json_body(body)

    assert status == 403
    assert payload["error"]["code"] == "role_denied"


def test_reset_reload_execution_plan_rejects_out_of_scope_actor() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            SEEDED_CORPUS_RESET_RELOAD_EXECUTION_PLAN_API_PATH,
            reset_reload_execution_plan_context=_execution_plan_context(
                connection,
                actor=_operator_actor(scopes=(OTHER_SCOPE,)),
            ),
        )

    payload = _json_body(body)

    assert status == 403
    assert payload["error"]["code"] == "scope_denied"


def test_reset_reload_execution_plan_rejects_invalid_mode_and_handling_option() -> None:
    with _seeded_connection() as connection:
        invalid_mode_status, _content_type, invalid_mode_body = route_response(
            f"{SEEDED_CORPUS_RESET_RELOAD_EXECUTION_PLAN_API_PATH}"
            "?execution_plan_mode=execute_now",
            reset_reload_execution_plan_context=_execution_plan_context(connection),
        )
        invalid_handling_status, _content_type, invalid_handling_body = route_response(
            f"{SEEDED_CORPUS_RESET_RELOAD_EXECUTION_PLAN_API_PATH}"
            "?reviewer_state_mode=delete",
            reset_reload_execution_plan_context=_execution_plan_context(connection),
        )
        counts = _table_counts(connection)

    assert invalid_mode_status == 400
    assert _json_body(invalid_mode_body)["error"]["code"] == "invalid_request"
    assert "execution_plan_mode" in _json_body(invalid_mode_body)["error"]["message"]
    assert invalid_handling_status == 400
    assert _json_body(invalid_handling_body)["error"]["code"] == "invalid_request"
    assert "reviewer_state_mode" in _json_body(invalid_handling_body)["error"]["message"]
    assert counts["reset_reload_planning_metadata"] == 0


def test_reset_reload_execution_plan_requires_explicit_local_test_context() -> None:
    status, _content_type, body = route_response(
        SEEDED_CORPUS_RESET_RELOAD_EXECUTION_PLAN_API_PATH
    )

    payload = _json_body(body)

    assert status == 503
    assert payload["error"]["code"] == "reset_reload_execution_plan_context_required"


def _json_body(body: bytes) -> dict[str, Any]:
    loaded = json.loads(body)
    assert isinstance(loaded, dict)
    return loaded


def _execution_plan_context(
    connection: Connection,
    *,
    actor: AuthenticatedActor | None | object = DEFAULT_ACTOR,
    scope: HostedAccessScope = TEST_SCOPE,
) -> SeededCorpusResetReloadExecutionPlanContext:
    context_actor = _operator_actor() if actor is DEFAULT_ACTOR else actor
    return SeededCorpusResetReloadExecutionPlanContext(
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


def _create_reviewer_note(connection: Connection) -> None:
    source_record_key = connection.execute(
        select(hosted_source_derived_records.c.source_record_key).order_by(
            hosted_source_derived_records.c.source_record_key
        ).limit(1)
    ).scalar_one()
    create_reviewer_note_scaffold(
        connection,
        _admin_actor(),
        scope=TEST_SCOPE,
        source_record_key=source_record_key,
        note_text="Fixture planning note for no mutation test.",
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