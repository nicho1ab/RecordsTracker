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
    hosted_reset_reload_planning_metadata,
    plan_seeded_corpus_reset_reload_dry_run,
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


def test_reset_reload_dry_run_reports_seeded_corpus_impact_without_mutation() -> None:
    with _seeded_connection() as connection:
        before_counts = _table_counts(connection)

        status, content_type, body = route_response(
            SEEDED_CORPUS_RESET_RELOAD_DRY_RUN_API_PATH,
            reset_reload_dry_run_context=_dry_run_context(connection),
        )

        after_counts = _table_counts(connection)

    payload = _json_body(body)

    assert status == 200
    assert content_type == "application/json; charset=utf-8"
    assert before_counts == after_counts == {
        "import_batches": 1,
        "source_records": 7,
        "reviewer_created_state": 0,
        "audit_events": 0,
        "reset_reload_planning_metadata": 0,
    }
    assert payload["dry_run"] is True
    assert payload["operation"] == "seeded_corpus_reset_reload_dry_run"
    assert payload["scope"] == {
        "scope_type": "seeded_corpus",
        "scope_id": TEST_SCOPE.scope_id,
    }
    assert payload["authorization"]["permission"] == "import_reload"
    assert payload["authorization"]["actor"]["roles"] == ["developer_operator"]
    assert payload["source_derived_impact"] == {
        "existing_import_batch_count": 1,
        "existing_source_derived_record_count": 7,
        "counts_by_entity": {
            "facility": 1,
            "source_document": 1,
            "complaint": 1,
            "allegation": 2,
            "event": 1,
            "extraction_audit": 1,
        },
        "import_batches": [
            {
                "import_batch_id": TEST_SCOPE.scope_id,
                "imported_at": "2026-06-13T00:00:00+00:00",
                "source_artifact_identity": FIXTURE.as_posix(),
                "source_pipeline_version": "fixture-pipeline-output-0.1.0",
                "validation_status": "validated",
                "raw_hash_validation_status": "validated",
                "record_counts": {
                    "facility": 1,
                    "source_document": 1,
                    "complaint": 1,
                    "allegation": 2,
                    "event": 1,
                    "extraction_audit": 1,
                },
                "warnings": [
                    "Tiny fixture-backed seeded corpus for local import tests only; "
                    "not complete source coverage."
                ],
                "errors": [],
            }
        ],
        "future_reload_scope": "seeded source-derived records for the requested corpus scope",
    }
    reviewer_impact = payload["reviewer_created_state_impact"]
    assert reviewer_impact["persistence_implemented"] is True
    assert reviewer_impact["selected_handling_mode"] == "preserve"
    assert reviewer_impact["handling_options"] == ["preserve", "archive", "clear"]
    assert reviewer_impact["current_state_count"] == 0
    assert "annotations" in reviewer_impact["affected_state_categories"]
    assert payload["audit_event_impact"]["persistence_implemented"] is True
    assert payload["audit_event_impact"]["current_event_count"] == 0
    assert payload["future_execution_permissions"] == ["import_reload"]
    assert payload["safety"] == {
        "data_mutations_performed": False,
        "queries_only": True,
        "dry_run_does_not_execute_reset_reload": True,
    }
    assert "import or reload seeded corpus artifacts" in payload["deferred_actions"]
    assert "operational_metadata" not in payload
    assert (
        "this dry-run counts existing audit scaffold rows but does not persist a new audit event"
        in payload["audit_requirements"]
    )


def test_reset_reload_dry_run_supports_future_clear_mode_planning_only() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            f"{SEEDED_CORPUS_RESET_RELOAD_DRY_RUN_API_PATH}?reviewer_state_mode=clear",
            reset_reload_dry_run_context=_dry_run_context(connection),
        )

    payload = _json_body(body)

    assert status == 200
    assert payload["reviewer_created_state_impact"]["selected_handling_mode"] == "clear"
    assert payload["future_execution_permissions"] == [
        "import_reload",
        "reset_destructive",
    ]
    assert payload["safety"]["data_mutations_performed"] is False


def test_reset_reload_dry_run_reports_empty_scope_without_mutation() -> None:
    with _empty_connection() as connection:
        plan = plan_seeded_corpus_reset_reload_dry_run(
            connection,
            _operator_actor(),
            scope=TEST_SCOPE,
        )

    assert plan.source_derived_impact.existing_import_batch_count == 0
    assert plan.source_derived_impact.existing_source_derived_record_count == 0
    assert dict(plan.source_derived_impact.counts_by_entity) == {
        "facility": 0,
        "source_document": 0,
        "complaint": 0,
        "allegation": 0,
        "event": 0,
        "extraction_audit": 0,
    }
    assert plan.source_derived_impact.import_batches == ()
    assert plan.data_mutations_performed is False


def test_reset_reload_dry_run_rejects_unauthenticated_actor() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            SEEDED_CORPUS_RESET_RELOAD_DRY_RUN_API_PATH,
            reset_reload_dry_run_context=_dry_run_context(connection, actor=None),
        )

    payload = _json_body(body)

    assert status == 401
    assert payload["error"]["code"] == "authentication_required"


@pytest.mark.parametrize("account_status", ["disabled", "revoked"])
def test_reset_reload_dry_run_rejects_disabled_or_revoked_actor(
    account_status: str,
) -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            SEEDED_CORPUS_RESET_RELOAD_DRY_RUN_API_PATH,
            reset_reload_dry_run_context=_dry_run_context(
                connection,
                actor=_operator_actor(account_status=account_status),
            ),
        )

    payload = _json_body(body)

    assert status == 403
    assert payload["error"]["code"] == "account_disabled_or_revoked"


def test_reset_reload_dry_run_rejects_read_only_actor() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            SEEDED_CORPUS_RESET_RELOAD_DRY_RUN_API_PATH,
            reset_reload_dry_run_context=_dry_run_context(
                connection,
                actor=_actor(roles=("read_only_tester",)),
            ),
        )

    payload = _json_body(body)

    assert status == 403
    assert payload["error"]["code"] == "role_denied"


def test_reset_reload_dry_run_rejects_out_of_scope_actor() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            SEEDED_CORPUS_RESET_RELOAD_DRY_RUN_API_PATH,
            reset_reload_dry_run_context=_dry_run_context(
                connection,
                actor=_operator_actor(scopes=(OTHER_SCOPE,)),
            ),
        )

    payload = _json_body(body)

    assert status == 403
    assert payload["error"]["code"] == "scope_denied"


def test_reset_reload_dry_run_rejects_invalid_reviewer_state_mode() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            f"{SEEDED_CORPUS_RESET_RELOAD_DRY_RUN_API_PATH}?reviewer_state_mode=delete",
            reset_reload_dry_run_context=_dry_run_context(connection),
        )

    payload = _json_body(body)

    assert status == 400
    assert payload["error"]["code"] == "invalid_request"
    assert "reviewer_state_mode" in payload["error"]["message"]


def test_reset_reload_dry_run_requires_explicit_local_test_context() -> None:
    status, _content_type, body = route_response(SEEDED_CORPUS_RESET_RELOAD_DRY_RUN_API_PATH)

    payload = _json_body(body)

    assert status == 503
    assert payload["error"]["code"] == "reset_reload_dry_run_context_required"


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
    )


def _actor(
    *,
    roles: tuple[str, ...],
    scopes: tuple[HostedAccessScope, ...] = (TEST_SCOPE,),
    account_status: str = "active",
    actor_category: str = "tester",
) -> AuthenticatedActor:
    return AuthenticatedActor(
        provider_subject="fixture-subject-operator",
        provider_issuer="fixture-managed-oidc-provider",
        display_name="Fixture Operator",
        email="operator@example.invalid",
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
