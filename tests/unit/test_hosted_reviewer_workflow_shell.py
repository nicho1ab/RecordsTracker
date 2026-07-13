from __future__ import annotations

import json
from collections.abc import Mapping
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
    REVIEWER_CREATED_STATE_API_PREFIX,
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
FACILITY_KEY = "facility:ccld:facility:157806098"
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
    assert payload["workflow_shell"]["mode"] == "local_test_read_with_workflow_actions"
    assert payload["workflow_shell"]["reviewer_created_state_persistence"] is True
    assert payload["workflow_shell"]["reviewer_created_state_reads_enabled"] is True
    assert payload["workflow_shell"]["reviewer_created_state_read_route_source"] == (
        "/api/reviewer-created-state"
    )
    assert payload["workflow_shell"]["reviewer_note_action_enabled"] is True
    assert payload["workflow_shell"]["reviewer_note_action_route_source"] == (
        "/api/reviewer/source-derived-review/detail/reviewer-note"
    )
    assert payload["workflow_shell"]["reviewer_status_action_enabled"] is True
    assert payload["workflow_shell"]["reviewer_status_action_route_source"] == (
        "/api/reviewer/source-derived-review/detail/reviewer-status"
    )
    assert payload["workflow_shell"]["reviewer_actions_enabled"] == [
        "create_reviewer_note",
        "create_reviewer_status",
    ]
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
        "persistence_enabled": True,
        "workflow_note_action_enabled": True,
        "workflow_note_action_route_source": (
            "/api/reviewer/source-derived-review/detail/reviewer-note"
        ),
        "workflow_status_action_enabled": True,
        "workflow_status_action_route_source": (
            "/api/reviewer/source-derived-review/detail/reviewer-status"
        ),
        "associated_state_reads_enabled": True,
        "associated_state_read_route_source": "/api/reviewer-created-state",
        "associated_state_reads_require_reviewer_state_read_permission": True,
        "reads_create_or_modify_state": False,
        "anonymous_reviewer_created_state_allowed": False,
        "available_actions": ["create_reviewer_note", "create_reviewer_status"],
        "deferred_actions": [
            "queue state persistence",
            "full annotation workflow",
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
        "workflow_note_action_enabled"
    ] is True
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
        "payload_kinds_present": [],
        "reviewer_statuses_present": [],
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
        "payload_kinds_present": [],
        "reviewer_statuses_present": [],
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
        "payload_kinds_present": [],
        "reviewer_statuses_present": [],
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
        "payload_kinds_present": ["reviewer_note_scaffold"],
        "reviewer_statuses_present": [],
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


def test_reviewer_workflow_shell_note_action_creates_note_from_selected_detail() -> None:
    with _seeded_connection() as connection:
        before_source_rows = _source_rows(connection)

        status, content_type, body = route_response(
            "/api/reviewer/source-derived-review/detail/reviewer-note"
            f"?source_record_key={quote(COMPLAINT_KEY)}",
            request_body=_json_bytes(
                {
                    "note_text": "Created through the workflow shell.",
                    "source_record_key": FACILITY_KEY,
                }
            ),
            reviewer_workflow_shell_context=_workflow_context(
                connection,
                actor=_actor(
                    roles=("tester_reviewer",),
                    provider_subject="fixture-subject-note-action",
                    display_name="Fixture Note Action Reviewer",
                ),
            ),
        )

        read_status, _content_type, read_body = route_response(
            f"{REVIEWER_CREATED_STATE_API_PREFIX}"
            f"?source_record_key={quote(COMPLAINT_KEY)}",
            reviewer_created_state_api_context=ReviewerCreatedStateApiContext(
                connection=connection,
                actor=_actor(),
                scope=TEST_SCOPE,
            ),
        )
        after_source_rows = _source_rows(connection)
        counts = _table_counts(connection)
        [audit_event] = connection.execute(select(hosted_audit_events)).mappings().all()

    payload = _json_body(body)
    read_payload = _json_body(read_body)

    assert status == 201
    assert content_type == "application/json; charset=utf-8"
    assert read_status == 200
    assert before_source_rows == after_source_rows
    assert counts == {
        "import_batches": 1,
        "source_records": 7,
        "reviewer_created_state": 1,
        "audit_events": 1,
        "reset_reload_planning_metadata": 0,
    }
    assert payload["workflow_action"] == {
        "action_id": "create-reviewer-note-from-selected-detail-shell",
        "action_source": "/api/reviewer/source-derived-review/detail/reviewer-note",
        "delegated_route_source": "/api/reviewer-created-state/reviewer-note",
        "created_reviewer_note": True,
        "selected_source_record_key": COMPLAINT_KEY,
        "source_record_binding_forced_from_selected_detail": True,
        "local_test_only": True,
        "writes_create_audit_event": True,
        "source_of_record": "public portal",
        "does_not_mutate_source_derived_records": True,
    }
    state_row = payload["reviewer_created_state"]
    assert state_row["source_record_key"] == COMPLAINT_KEY
    assert state_row["state_payload"] == {
        "payload_kind": "reviewer_note_scaffold",
        "note_text": "Created through the workflow shell.",
        "note_format": "plain_text",
        "source_record_key": COMPLAINT_KEY,
        "local_test_only": True,
    }
    assert state_row["created_by"]["provider_subject"] == (
        "fixture-subject-note-action"
    )
    assert payload["delegated_reviewer_created_state_workflow"][
        "route_source"
    ] == "/api/reviewer-created-state/reviewer-note"
    assert [
        row["reviewer_state_id"]
        for row in payload["detail"]["associated_reviewer_created_state"][
            "reviewer_created_state"
        ]
    ] == [state_row["reviewer_state_id"]]
    assert payload["detail"]["associated_reviewer_created_state_summary"][
        "total_associated_rows"
    ] == 1
    assert [
        row["reviewer_state_id"]
        for row in read_payload["reviewer_created_state"]
    ] == [state_row["reviewer_state_id"]]
    assert audit_event["target_reviewer_state_id"] == state_row["reviewer_state_id"]
    assert audit_event["source_record_key"] == COMPLAINT_KEY
    assert audit_event["context_metadata"] == {
        "state_kind": "review_item_state_scaffold",
        "state_payload_keys": [
            "local_test_only",
            "note_format",
            "note_text",
            "payload_kind",
            "source_record_key",
        ],
        "source_record_key": COMPLAINT_KEY,
    }
    serialized_body = body.decode("utf-8").casefold()
    assert "token" not in serialized_body
    assert "cookie" not in serialized_body
    assert "tester@example.invalid" not in serialized_body


def test_reviewer_workflow_shell_status_action_creates_status_from_selected_detail() -> None:
    with _seeded_connection() as connection:
        before_source_rows = _source_rows(connection)

        status, content_type, body = route_response(
            "/api/reviewer/source-derived-review/detail/reviewer-status"
            f"?source_record_key={quote(COMPLAINT_KEY)}",
            request_body=_json_bytes(
                {
                    "reviewer_status": "needs_follow_up",
                    "source_record_key": FACILITY_KEY,
                }
            ),
            reviewer_workflow_shell_context=_workflow_context(
                connection,
                actor=_actor(
                    roles=("tester_reviewer",),
                    provider_subject="fixture-subject-status-action",
                    display_name="Fixture Status Action Reviewer",
                ),
            ),
        )

        read_status, _content_type, read_body = route_response(
            f"{REVIEWER_CREATED_STATE_API_PREFIX}"
            f"?source_record_key={quote(COMPLAINT_KEY)}",
            reviewer_created_state_api_context=ReviewerCreatedStateApiContext(
                connection=connection,
                actor=_actor(),
                scope=TEST_SCOPE,
            ),
        )
        detail_status, _content_type, detail_body = route_response(
            "/api/reviewer/source-derived-review/detail"
            f"?source_record_key={quote(COMPLAINT_KEY)}",
            reviewer_workflow_shell_context=_workflow_context(connection),
        )
        after_source_rows = _source_rows(connection)
        counts = _table_counts(connection)
        [audit_event] = connection.execute(select(hosted_audit_events)).mappings().all()

    payload = _json_body(body)
    read_payload = _json_body(read_body)
    detail_payload = _json_body(detail_body)

    assert status == 201
    assert content_type == "application/json; charset=utf-8"
    assert read_status == 200
    assert detail_status == 200
    assert before_source_rows == after_source_rows
    assert counts == {
        "import_batches": 1,
        "source_records": 7,
        "reviewer_created_state": 1,
        "audit_events": 1,
        "reset_reload_planning_metadata": 0,
    }
    assert payload["workflow_action"] == {
        "action_id": "create-reviewer-status-from-selected-detail-shell",
        "action_source": "/api/reviewer/source-derived-review/detail/reviewer-status",
        "delegated_route_source": "/api/reviewer-created-state/reviewer-status",
        "created_reviewer_status": True,
        "selected_source_record_key": COMPLAINT_KEY,
        "source_record_binding_forced_from_selected_detail": True,
        "local_test_only": True,
        "writes_create_audit_event": True,
        "source_of_record": "public portal",
        "does_not_mutate_source_derived_records": True,
    }
    state_row = payload["reviewer_created_state"]
    assert state_row["source_record_key"] == COMPLAINT_KEY
    assert state_row["state_payload"] == {
        "payload_kind": "reviewer_status_scaffold",
        "reviewer_status": "needs_follow_up",
        "source_record_key": COMPLAINT_KEY,
        "local_test_only": True,
    }
    assert state_row["created_by"]["provider_subject"] == (
        "fixture-subject-status-action"
    )
    assert payload["delegated_reviewer_created_state_workflow"][
        "route_source"
    ] == "/api/reviewer-created-state/reviewer-status"
    assert [
        row["reviewer_state_id"]
        for row in payload["detail"]["associated_reviewer_created_state"][
            "reviewer_created_state"
        ]
    ] == [state_row["reviewer_state_id"]]
    assert payload["detail"]["associated_reviewer_created_state_summary"][
        "reviewer_statuses_present"
    ] == ["needs_follow_up"]
    assert [
        row["reviewer_state_id"]
        for row in read_payload["reviewer_created_state"]
    ] == [state_row["reviewer_state_id"]]
    assert detail_payload["detail"]["associated_reviewer_created_state_summary"][
        "reviewer_statuses_present"
    ] == ["needs_follow_up"]
    assert audit_event["target_reviewer_state_id"] == state_row["reviewer_state_id"]
    assert audit_event["source_record_key"] == COMPLAINT_KEY
    assert audit_event["context_metadata"] == {
        "state_kind": "review_item_state_scaffold",
        "state_payload_keys": [
            "local_test_only",
            "payload_kind",
            "reviewer_status",
            "source_record_key",
        ],
        "source_record_key": COMPLAINT_KEY,
    }
    serialized_body = body.decode("utf-8").casefold()
    assert "token" not in serialized_body
    assert "cookie" not in serialized_body
    assert "tester@example.invalid" not in serialized_body


@pytest.mark.parametrize(
    ("actor_case", "expected_status", "expected_code"),
    [
        ("unauthenticated", 401, "authentication_required"),
        ("disabled", 403, "account_disabled_or_revoked"),
        ("read_only", 403, "role_denied"),
        ("out_of_scope", 403, "scope_denied"),
    ],
)
def test_reviewer_workflow_shell_status_action_rejects_permission_failures(
    actor_case: str,
    expected_status: int,
    expected_code: str,
) -> None:
    actor: AuthenticatedActor | None
    if actor_case == "unauthenticated":
        actor = None
    elif actor_case == "disabled":
        actor = _actor(roles=("tester_reviewer",), account_status="disabled")
    elif actor_case == "out_of_scope":
        actor = _actor(roles=("tester_reviewer",), scopes=(OTHER_SCOPE,))
    else:
        actor = _actor()

    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            "/api/reviewer/source-derived-review/detail/reviewer-status"
            f"?source_record_key={quote(COMPLAINT_KEY)}",
            request_body=_json_bytes({"reviewer_status": "in_review"}),
            reviewer_workflow_shell_context=_workflow_context(
                connection,
                actor=actor,
            ),
        )
        counts = _table_counts(connection)

    payload = _json_body(body)

    assert status == expected_status
    assert payload["error"]["code"] == expected_code
    assert counts == {
        "import_batches": 1,
        "source_records": 7,
        "reviewer_created_state": 0,
        "audit_events": 0,
        "reset_reload_planning_metadata": 0,
    }


def test_reviewer_workflow_shell_status_action_rejects_missing_or_invalid_source_record() -> None:
    with _seeded_connection() as connection:
        missing_key_status, _content_type, missing_key_body = route_response(
            "/api/reviewer/source-derived-review/detail/reviewer-status",
            request_body=_json_bytes({"reviewer_status": "in_review"}),
            reviewer_workflow_shell_context=_workflow_context(
                connection,
                actor=_actor(roles=("tester_reviewer",)),
            ),
        )
        missing_record_status, _content_type, missing_record_body = route_response(
            "/api/reviewer/source-derived-review/detail/reviewer-status"
            "?source_record_key=complaint%3Amissing",
            request_body=_json_bytes({"reviewer_status": "in_review"}),
            reviewer_workflow_shell_context=_workflow_context(
                connection,
                actor=_actor(roles=("tester_reviewer",)),
            ),
        )
        counts = _table_counts(connection)

    assert missing_key_status == 400
    assert _json_body(missing_key_body)["error"]["code"] == "invalid_request"
    assert missing_record_status == 404
    assert _json_body(missing_record_body)["error"]["code"] == (
        "source_derived_record_not_found"
    )
    assert counts["reviewer_created_state"] == 0
    assert counts["audit_events"] == 0


def test_reviewer_workflow_shell_status_action_rejects_invalid_status_payload() -> None:
    with _seeded_connection() as connection:
        missing_body_status, _content_type, missing_body_body = route_response(
            "/api/reviewer/source-derived-review/detail/reviewer-status"
            f"?source_record_key={quote(COMPLAINT_KEY)}",
            reviewer_workflow_shell_context=_workflow_context(
                connection,
                actor=_actor(roles=("tester_reviewer",)),
            ),
        )
        empty_status, _content_type, empty_body = route_response(
            "/api/reviewer/source-derived-review/detail/reviewer-status"
            f"?source_record_key={quote(COMPLAINT_KEY)}",
            request_body=_json_bytes({"reviewer_status": "   "}),
            reviewer_workflow_shell_context=_workflow_context(
                connection,
                actor=_actor(roles=("tester_reviewer",)),
            ),
        )
        invalid_status, _content_type, invalid_body = route_response(
            "/api/reviewer/source-derived-review/detail/reviewer-status"
            f"?source_record_key={quote(COMPLAINT_KEY)}",
            request_body=_json_bytes({"reviewer_status": "source_checked"}),
            reviewer_workflow_shell_context=_workflow_context(
                connection,
                actor=_actor(roles=("tester_reviewer",)),
            ),
        )
        counts = _table_counts(connection)

    assert missing_body_status == 400
    assert _json_body(missing_body_body)["error"]["code"] == "invalid_request"
    assert empty_status == 400
    assert _json_body(empty_body)["error"]["code"] == "invalid_request"
    assert invalid_status == 400
    assert _json_body(invalid_body)["error"]["code"] == "invalid_request"
    assert counts["reviewer_created_state"] == 0
    assert counts["audit_events"] == 0


@pytest.mark.parametrize(
    ("actor_case", "expected_status", "expected_code"),
    [
        ("unauthenticated", 401, "authentication_required"),
        ("read_only", 403, "role_denied"),
        ("out_of_scope", 403, "scope_denied"),
    ],
)
def test_reviewer_workflow_shell_note_action_rejects_permission_failures(
    actor_case: str,
    expected_status: int,
    expected_code: str,
) -> None:
    actor: AuthenticatedActor | None
    if actor_case == "unauthenticated":
        actor = None
    elif actor_case == "out_of_scope":
        actor = _actor(roles=("tester_reviewer",), scopes=(OTHER_SCOPE,))
    else:
        actor = _actor()

    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            "/api/reviewer/source-derived-review/detail/reviewer-note"
            f"?source_record_key={quote(COMPLAINT_KEY)}",
            request_body=_json_bytes({"note_text": "Needs source review."}),
            reviewer_workflow_shell_context=_workflow_context(
                connection,
                actor=actor,
            ),
        )
        counts = _table_counts(connection)

    payload = _json_body(body)

    assert status == expected_status
    assert payload["error"]["code"] == expected_code
    assert counts == {
        "import_batches": 1,
        "source_records": 7,
        "reviewer_created_state": 0,
        "audit_events": 0,
        "reset_reload_planning_metadata": 0,
    }


def test_reviewer_workflow_shell_note_action_rejects_missing_or_invalid_source_record() -> None:
    with _seeded_connection() as connection:
        missing_key_status, _content_type, missing_key_body = route_response(
            "/api/reviewer/source-derived-review/detail/reviewer-note",
            request_body=_json_bytes({"note_text": "Needs source review."}),
            reviewer_workflow_shell_context=_workflow_context(
                connection,
                actor=_actor(roles=("tester_reviewer",)),
            ),
        )
        missing_record_status, _content_type, missing_record_body = route_response(
            "/api/reviewer/source-derived-review/detail/reviewer-note"
            "?source_record_key=complaint%3Amissing",
            request_body=_json_bytes({"note_text": "Needs source review."}),
            reviewer_workflow_shell_context=_workflow_context(
                connection,
                actor=_actor(roles=("tester_reviewer",)),
            ),
        )
        counts = _table_counts(connection)

    assert missing_key_status == 400
    assert _json_body(missing_key_body)["error"]["code"] == "invalid_request"
    assert missing_record_status == 404
    assert _json_body(missing_record_body)["error"]["code"] == (
        "source_derived_record_not_found"
    )
    assert counts["reviewer_created_state"] == 0
    assert counts["audit_events"] == 0


def test_reviewer_workflow_shell_note_action_rejects_invalid_note_payload() -> None:
    with _seeded_connection() as connection:
        missing_body_status, _content_type, missing_body_body = route_response(
            "/api/reviewer/source-derived-review/detail/reviewer-note"
            f"?source_record_key={quote(COMPLAINT_KEY)}",
            reviewer_workflow_shell_context=_workflow_context(
                connection,
                actor=_actor(roles=("tester_reviewer",)),
            ),
        )
        empty_note_status, _content_type, empty_note_body = route_response(
            "/api/reviewer/source-derived-review/detail/reviewer-note"
            f"?source_record_key={quote(COMPLAINT_KEY)}",
            request_body=_json_bytes({"note_text": "   "}),
            reviewer_workflow_shell_context=_workflow_context(
                connection,
                actor=_actor(roles=("tester_reviewer",)),
            ),
        )
        secret_note_status, _content_type, secret_note_body = route_response(
            "/api/reviewer/source-derived-review/detail/reviewer-note"
            f"?source_record_key={quote(COMPLAINT_KEY)}",
            request_body=_json_bytes({"note_text": "A token was pasted here."}),
            reviewer_workflow_shell_context=_workflow_context(
                connection,
                actor=_actor(roles=("tester_reviewer",)),
            ),
        )
        counts = _table_counts(connection)

    assert missing_body_status == 400
    assert _json_body(missing_body_body)["error"]["code"] == "invalid_request"
    assert empty_note_status == 400
    assert _json_body(empty_note_body)["error"]["code"] == "invalid_request"
    assert secret_note_status == 400
    assert _json_body(secret_note_body)["error"]["code"] == "invalid_request"
    assert counts["reviewer_created_state"] == 0
    assert counts["audit_events"] == 0


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
        "source_records": 7,
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


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True).encode("utf-8")


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


def _source_rows(connection: Connection) -> list[dict[str, object]]:
    rows = connection.execute(
        select(hosted_source_derived_records).order_by(
            hosted_source_derived_records.c.source_record_key
        )
    ).mappings()
    return [dict(row) for row in rows]


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
