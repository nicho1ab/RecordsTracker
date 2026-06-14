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
    hosted_reset_reload_planning_metadata,
)
from ccld_complaints.hosted_app.reviewer_created_state import (
    create_reviewer_created_state_scaffold,
    hosted_reviewer_created_state,
)
from ccld_complaints.hosted_app.reviewer_created_state_routes import (
    ReviewerCreatedStateApiContext,
)
from ccld_complaints.hosted_app.reviewer_workflow_shell import (
    ReviewerWorkflowShellContext,
)
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
    assert payload["workflow_shell"]["reviewer_created_state_reads_enabled"] is True
    assert payload["workflow_shell"]["reviewer_created_state_read_route_source"] == (
        "/api/reviewer-created-state"
    )
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
        "associated_state_reads_enabled": True,
        "associated_state_read_route_source": "/api/reviewer-created-state",
        "associated_state_reads_require_reviewer_state_read_permission": True,
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
        created = create_reviewer_created_state_scaffold(
            connection,
            _actor(roles=("tester_reviewer",)),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            state_payload={"scaffold_state": "source_check_needed"},
        )

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
    associated_state = payload["detail"]["associated_reviewer_created_state"]
    assert associated_state["route_source"] == "/api/reviewer-created-state"
    assert associated_state["empty"] is False
    assert associated_state["filters"] == {
        "source_record_key": COMPLAINT_KEY,
        "state_kind": None,
        "actor_provider_subject": None,
        "q": None,
    }
    assert associated_state["pagination"] == {
        "limit": 100,
        "offset": 0,
        "returned_count": 1,
    }
    summary = payload["detail"]["associated_reviewer_created_state_summary"]
    assert summary == {
        "summary_source": "/api/reviewer-created-state",
        "has_reviewer_created_state": True,
        "total_associated_rows": 1,
        "state_kinds_present": ["review_item_state_scaffold"],
        "latest_created_at": created.created_at,
        "actor_attribution_labels": ["Fixture Read Only Tester (tester)"],
        "actor_categories_present": ["tester"],
        "safety": {
            "derived_from_associated_state_route_output": True,
            "read_only_route": True,
            "does_not_mutate_source_derived_records": True,
            "does_not_mutate_reviewer_created_state": True,
            "does_not_mutate_audit_events": True,
            "does_not_mutate_operational_metadata": True,
        },
    }
    [state_row] = associated_state["reviewer_created_state"]
    assert state_row["reviewer_state_id"] == created.reviewer_state_id
    assert state_row["source_record_key"] == COMPLAINT_KEY
    assert state_row["state_payload"] == {"scaffold_state": "source_check_needed"}
    assert "email" not in json.dumps(associated_state).casefold()
    assert "token" not in json.dumps(associated_state).casefold()


def test_reviewer_workflow_shell_detail_includes_empty_associated_state() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            "/api/reviewer/source-derived-review/detail"
            f"?source_record_key={quote(COMPLAINT_KEY)}",
            reviewer_workflow_shell_context=_workflow_context(connection),
        )

    payload = _json_body(body)

    assert status == 200
    associated_state = payload["detail"]["associated_reviewer_created_state"]
    assert associated_state["empty"] is True
    assert associated_state["reviewer_created_state"] == []
    assert associated_state["pagination"] == {
        "limit": 100,
        "offset": 0,
        "returned_count": 0,
    }
    assert payload["detail"]["associated_reviewer_created_state_summary"] == {
        "summary_source": "/api/reviewer-created-state",
        "has_reviewer_created_state": False,
        "total_associated_rows": 0,
        "state_kinds_present": [],
        "latest_created_at": None,
        "actor_attribution_labels": [],
        "actor_categories_present": [],
        "safety": {
            "derived_from_associated_state_route_output": True,
            "read_only_route": True,
            "does_not_mutate_source_derived_records": True,
            "does_not_mutate_reviewer_created_state": True,
            "does_not_mutate_audit_events": True,
            "does_not_mutate_operational_metadata": True,
        },
    }


def test_reviewer_workflow_shell_detail_summarizes_multiple_associated_state_rows() -> None:
    with _seeded_connection() as connection:
        first = create_reviewer_created_state_scaffold(
            connection,
            _actor(
                roles=("tester_reviewer",),
                provider_subject="fixture-subject-active-reviewer",
                display_name="Fixture Active Reviewer",
            ),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            state_payload={"scaffold_state": "source_check_needed"},
        )
        second = create_reviewer_created_state_scaffold(
            connection,
            _actor(
                roles=("admin",),
                provider_subject="fixture-subject-admin-reviewer",
                display_name="Fixture Admin Reviewer",
                actor_category="admin",
            ),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            state_payload={"scaffold_state": "source_checked"},
        )

        status, _content_type, body = route_response(
            "/api/reviewer/source-derived-review/detail"
            f"?source_record_key={quote(COMPLAINT_KEY)}",
            reviewer_workflow_shell_context=_workflow_context(connection),
        )

    payload = _json_body(body)

    assert status == 200
    associated_state = payload["detail"]["associated_reviewer_created_state"]
    assert associated_state["pagination"] == {
        "limit": 100,
        "offset": 0,
        "returned_count": 2,
    }
    assert [
        row["reviewer_state_id"]
        for row in associated_state["reviewer_created_state"]
    ] == [first.reviewer_state_id, second.reviewer_state_id]
    assert payload["detail"]["associated_reviewer_created_state_summary"] == {
        "summary_source": "/api/reviewer-created-state",
        "has_reviewer_created_state": True,
        "total_associated_rows": 2,
        "state_kinds_present": ["review_item_state_scaffold"],
        "latest_created_at": max(first.created_at, second.created_at),
        "actor_attribution_labels": [
            "Fixture Active Reviewer (tester)",
            "Fixture Admin Reviewer (admin)",
        ],
        "actor_categories_present": ["admin", "tester"],
        "safety": {
            "derived_from_associated_state_route_output": True,
            "read_only_route": True,
            "does_not_mutate_source_derived_records": True,
            "does_not_mutate_reviewer_created_state": True,
            "does_not_mutate_audit_events": True,
            "does_not_mutate_operational_metadata": True,
        },
    }


def test_reviewer_workflow_shell_detail_filters_associated_state_search() -> None:
    with _seeded_connection() as connection:
        create_reviewer_created_state_scaffold(
            connection,
            _actor(
                roles=("tester_reviewer",),
                provider_subject="fixture-subject-active-reviewer",
                display_name="Fixture Active Reviewer",
            ),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            state_payload={"scaffold_state": "source_check_needed"},
        )
        matched = create_reviewer_created_state_scaffold(
            connection,
            _actor(
                roles=("admin",),
                provider_subject="fixture-subject-admin-reviewer",
                display_name="Fixture Admin Reviewer",
                actor_category="admin",
            ),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            state_payload={"scaffold_state": "source_checked"},
        )

        status, _content_type, body = route_response(
            "/api/reviewer/source-derived-review/detail"
            f"?source_record_key={quote(COMPLAINT_KEY)}"
            "&q=fixture%20admin"
            "&state_kind=review_item_state_scaffold",
            reviewer_workflow_shell_context=_workflow_context(connection),
        )

    payload = _json_body(body)

    assert status == 200
    associated_state = payload["detail"]["associated_reviewer_created_state"]
    assert associated_state["filters"] == {
        "source_record_key": COMPLAINT_KEY,
        "state_kind": "review_item_state_scaffold",
        "actor_provider_subject": None,
        "q": "fixture admin",
    }
    assert [
        row["reviewer_state_id"]
        for row in associated_state["reviewer_created_state"]
    ] == [matched.reviewer_state_id]
    assert payload["detail"]["associated_reviewer_created_state_summary"][
        "total_associated_rows"
    ] == 1


def test_reviewer_workflow_shell_detail_shows_created_reviewer_note() -> None:
    with _seeded_connection() as connection:
        note = create_reviewer_created_state_scaffold(
            connection,
            _actor(roles=("tester_reviewer",), display_name="Fixture Note Reviewer"),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            state_payload={
                "payload_kind": "reviewer_note_scaffold",
                "note_text": "Visible note in workflow detail.",
                "note_format": "plain_text",
                "source_record_key": COMPLAINT_KEY,
                "local_test_only": True,
            },
        )

        status, _content_type, body = route_response(
            "/api/reviewer/source-derived-review/detail"
            f"?source_record_key={quote(COMPLAINT_KEY)}",
            reviewer_workflow_shell_context=_workflow_context(connection),
        )

    payload = _json_body(body)

    assert status == 200
    associated_state = payload["detail"]["associated_reviewer_created_state"]
    assert [
        row["reviewer_state_id"]
        for row in associated_state["reviewer_created_state"]
    ] == [note.reviewer_state_id]
    [state_row] = associated_state["reviewer_created_state"]
    assert state_row["state_payload"] == {
        "payload_kind": "reviewer_note_scaffold",
        "note_text": "Visible note in workflow detail.",
        "note_format": "plain_text",
        "source_record_key": COMPLAINT_KEY,
        "local_test_only": True,
    }
    assert payload["detail"]["associated_reviewer_created_state_summary"] == {
        "summary_source": "/api/reviewer-created-state",
        "has_reviewer_created_state": True,
        "total_associated_rows": 1,
        "state_kinds_present": ["review_item_state_scaffold"],
        "latest_created_at": note.created_at,
        "actor_attribution_labels": ["Fixture Note Reviewer (tester)"],
        "actor_categories_present": ["tester"],
        "safety": {
            "derived_from_associated_state_route_output": True,
            "read_only_route": True,
            "does_not_mutate_source_derived_records": True,
            "does_not_mutate_reviewer_created_state": True,
            "does_not_mutate_audit_events": True,
            "does_not_mutate_operational_metadata": True,
        },
    }


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


def test_reviewer_workflow_shell_rejects_source_read_without_reviewer_state_read() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            "/api/reviewer/source-derived-review/detail"
            f"?source_record_key={quote(COMPLAINT_KEY)}",
            reviewer_workflow_shell_context=_workflow_context(
                connection,
                actor=_actor(roles=("developer_operator",), actor_category="operator"),
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


def test_reviewer_workflow_shell_detail_reads_do_not_mutate_persisted_tables() -> None:
    with _seeded_connection() as connection:
        create_reviewer_created_state_scaffold(
            connection,
            _actor(roles=("tester_reviewer",)),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            state_payload={"scaffold_state": "in_review"},
        )
        before_counts = _table_counts(connection)

        status, _content_type, _body = route_response(
            "/api/reviewer/source-derived-review/detail"
            f"?source_record_key={quote(COMPLAINT_KEY)}",
            reviewer_workflow_shell_context=_workflow_context(connection),
        )
        after_counts = _table_counts(connection)

    assert status == 200
    assert before_counts == after_counts == {
        "import_batches": 1,
        "source_records": 6,
        "reviewer_created_state": 1,
        "audit_events": 1,
        "reset_reload_planning_metadata": 0,
    }


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
        ),
        reviewer_created_state_api_context=ReviewerCreatedStateApiContext(
            connection=connection,
            actor=cast(AuthenticatedActor | None, context_actor),
            scope=scope,
        ),
    )


def _actor(
    *,
    provider_subject: str = "fixture-subject-read-only",
    display_name: str = "Fixture Read Only Tester",
    roles: tuple[str, ...] = ("read_only_tester",),
    scopes: tuple[HostedAccessScope, ...] = (TEST_SCOPE,),
    account_status: str = "active",
    actor_category: str = "tester",
) -> AuthenticatedActor:
    return AuthenticatedActor(
        provider_subject=provider_subject,
        provider_issuer="fixture-managed-oidc-provider",
        display_name=display_name,
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