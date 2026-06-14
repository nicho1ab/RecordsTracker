from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Connection

from ccld_complaints.hosted_app.app import route_response
from ccld_complaints.hosted_app.audit_coverage_plan import (
    AUDIT_COVERAGE_PLAN_API_PATH,
    AuditCoveragePlanContext,
    plan_audit_coverage,
)
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
COMPLAINT_KEY = "complaint:ccld:complaint:32-CR-20220407124448"
DEFAULT_ACTOR = object()


def test_audit_coverage_plan_returns_bounded_non_mutating_plan() -> None:
    with _seeded_connection() as connection:
        _create_existing_audit_event(connection)
        before_counts = _table_counts(connection)

        status, content_type, body = route_response(
            AUDIT_COVERAGE_PLAN_API_PATH,
            audit_coverage_plan_context=_plan_context(connection),
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
    assert payload["audit_coverage_plan"] is True
    assert payload["operation"] == "audit_coverage_plan"
    assert payload["authorization"]["permission"] == "audit_read"
    assert payload["authorization"]["actor"]["roles"] == ["developer_operator"]
    assert payload["current_coverage"]["current_scoped_audit_event_count"] == 1
    assert payload["current_coverage"]["implemented_event_sources"] == [
        {
            "source": "reviewer_created_state_scaffold_writes",
            "actions": ["reviewer_created_state_scaffold.create"],
            "target_types": ["reviewer_created_state"],
            "covered_payload_kinds": [
                "review_item_state_scaffold",
                "reviewer_note_scaffold",
                "reviewer_status_scaffold",
            ],
        }
    ]
    assert [step["sequence"] for step in payload["readiness_plan"]] == list(
        range(1, 9)
    )
    assert [step["category"] for step in payload["readiness_plan"]] == [
        "implemented audit event sources",
        "current audit read/history seams",
        "actor attribution model",
        "target/source-derived context model",
        "no-secret metadata rules",
        "deferred audit event categories",
        "future implementation order",
        "non-goals for this branch",
    ]
    deferred_categories = {
        category["category"] for category in payload["deferred_audit_event_categories"]
    }
    assert deferred_categories == {
        "future provider login/auth events",
        "future provider claim/role/scope mapping events",
        "future reset/reload execution events",
        "future export packet generation events",
        "future annotation/correction/status-transition events",
        "future administrative configuration events",
        "future retention/disposition events",
    }
    assert payload["safety"] == {
        "data_mutations_performed": False,
        "persistence_performed": False,
        "audit_rows_created": 0,
        "source_derived_rows_mutated": 0,
        "reviewer_created_state_rows_mutated": 0,
        "audit_event_rows_mutated": 0,
        "import_rows_mutated": 0,
        "operational_rows_mutated": 0,
        "auth_related_rows_mutated": 0,
        "secrets_exposed": False,
    }
    serialized = body.decode("utf-8").casefold()
    for forbidden_text in (
        "super-secret-value",
        "actual-access-token",
        "actual-refresh-token",
        "actual-cookie-value",
        "private-header-value",
        "connection-string-value",
        "client-secret-value",
        "https://",
        "operator@example.invalid",
    ):
        assert forbidden_text not in serialized


def test_audit_coverage_plan_service_ordering_is_deterministic() -> None:
    with _seeded_connection() as connection:
        first = plan_audit_coverage(connection, _operator_actor(), scope=TEST_SCOPE)
        second = plan_audit_coverage(connection, _operator_actor(), scope=TEST_SCOPE)

    assert [step.step_id for step in first.plan_steps] == [
        step.step_id for step in second.plan_steps
    ] == [
        "implemented_audit_event_sources",
        "current_audit_read_history_seams",
        "actor_attribution_model",
        "target_source_context_model",
        "no_secret_metadata_rules",
        "deferred_audit_event_categories",
        "future_implementation_order",
        "non_goals_for_this_branch",
    ]


def test_audit_coverage_plan_requires_explicit_context() -> None:
    status, _content_type, body = route_response(AUDIT_COVERAGE_PLAN_API_PATH)

    payload = _json_body(body)

    assert status == 503
    assert payload["error"]["code"] == "audit_coverage_plan_context_required"


def test_audit_coverage_plan_rejects_unauthenticated_actor() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            AUDIT_COVERAGE_PLAN_API_PATH,
            audit_coverage_plan_context=_plan_context(connection, actor=None),
        )

    payload = _json_body(body)

    assert status == 401
    assert payload["error"]["code"] == "authentication_required"


@pytest.mark.parametrize("account_status", ["disabled", "revoked"])
def test_audit_coverage_plan_rejects_disabled_or_revoked_actor(
    account_status: str,
) -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            AUDIT_COVERAGE_PLAN_API_PATH,
            audit_coverage_plan_context=_plan_context(
                connection,
                actor=_operator_actor(account_status=account_status),
            ),
        )

    payload = _json_body(body)

    assert status == 403
    assert payload["error"]["code"] == "account_disabled_or_revoked"


def test_audit_coverage_plan_rejects_role_without_audit_permission() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            AUDIT_COVERAGE_PLAN_API_PATH,
            audit_coverage_plan_context=_plan_context(
                connection,
                actor=_read_only_actor(),
            ),
        )

    payload = _json_body(body)

    assert status == 403
    assert payload["error"]["code"] == "role_denied"


def test_audit_coverage_plan_rejects_out_of_scope_actor() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            AUDIT_COVERAGE_PLAN_API_PATH,
            audit_coverage_plan_context=_plan_context(
                connection,
                actor=_operator_actor(scopes=(OTHER_SCOPE,)),
            ),
        )

    payload = _json_body(body)

    assert status == 403
    assert payload["error"]["code"] == "scope_denied"


def _json_body(body: bytes) -> dict[str, Any]:
    loaded = json.loads(body)
    assert isinstance(loaded, dict)
    return loaded


def _plan_context(
    connection: Connection,
    *,
    actor: AuthenticatedActor | None | object = DEFAULT_ACTOR,
    scope: HostedAccessScope = TEST_SCOPE,
) -> AuditCoveragePlanContext:
    context_actor = _operator_actor() if actor is DEFAULT_ACTOR else actor
    return AuditCoveragePlanContext(
        connection=connection,
        actor=cast(AuthenticatedActor | None, context_actor),
        scope=scope,
    )


def _create_existing_audit_event(connection: Connection) -> None:
    create_reviewer_note_scaffold(
        connection,
        _reviewer_actor(),
        scope=TEST_SCOPE,
        source_record_key=COMPLAINT_KEY,
        note_text="Fixture note for audit coverage planning.",
    )


def _reviewer_actor() -> AuthenticatedActor:
    return _actor(
        roles=("tester_reviewer",),
        scopes=(TEST_SCOPE,),
        account_status="active",
        actor_category="tester",
        provider_subject="fixture-subject-reviewer",
        display_name="Fixture Tester Reviewer",
        email="tester@example.invalid",
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
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)
    connection = engine.connect()
    transaction = connection.begin()
    artifact = load_seeded_corpus_artifact(FIXTURE)
    import_seeded_corpus_artifact(connection, artifact)
    transaction.commit()
    return connection


def _table_counts(connection: Connection) -> dict[str, int]:
    return {
        "import_batches": connection.execute(
            select(func.count()).select_from(hosted_import_batches)
        ).scalar_one(),
        "source_records": connection.execute(
            select(func.count()).select_from(hosted_source_derived_records)
        ).scalar_one(),
        "reviewer_created_state": connection.execute(
            select(func.count()).select_from(hosted_reviewer_created_state)
        ).scalar_one(),
        "audit_events": connection.execute(
            select(func.count()).select_from(hosted_audit_events)
        ).scalar_one(),
        "reset_reload_planning_metadata": connection.execute(
            select(func.count()).select_from(hosted_reset_reload_planning_metadata)
        ).scalar_one(),
    }