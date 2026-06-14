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
FACILITY_KEY = "facility:ccld:facility:157806098"
DEFAULT_ACTOR = object()


def test_reviewer_created_state_api_lists_authenticated_rows() -> None:
    with _seeded_connection() as connection:
        created = create_reviewer_created_state_scaffold(
            connection,
            _reviewer_actor(),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            state_payload={"scaffold_state": "in_review"},
        )

        status, content_type, body = route_response(
            REVIEWER_CREATED_STATE_API_PREFIX,
            reviewer_created_state_api_context=_api_context(connection),
        )

    payload = _json_body(body)

    assert status == 200
    assert content_type == "application/json; charset=utf-8"
    assert payload["pagination"] == {"limit": 100, "offset": 0, "returned_count": 1}
    [state_row] = payload["reviewer_created_state"]
    assert state_row["reviewer_state_id"] == created.reviewer_state_id
    assert state_row["source_record_key"] == COMPLAINT_KEY
    assert state_row["scope"] == {
        "scope_type": "seeded_corpus",
        "scope_id": TEST_SCOPE.scope_id,
    }
    assert state_row["state_kind"] == "review_item_state_scaffold"
    assert state_row["state_payload"] == {"scaffold_state": "in_review"}
    assert state_row["created_by"] == {
        "provider_subject": "fixture-subject-reviewer",
        "provider_issuer": "fixture-managed-oidc-provider",
        "display_name": "Fixture Tester Reviewer",
        "actor_category": "tester",
    }
    assert state_row["authorization_permission"] == "reviewer_state_write"
    assert state_row["safety"] == {
        "read_only_route": True,
        "does_not_mutate_source_derived_records": True,
        "does_not_mutate_reviewer_created_state": True,
        "does_not_mutate_audit_events": True,
        "does_not_mutate_operational_metadata": True,
    }
    serialized_body = body.decode("utf-8").casefold()
    assert "token" not in serialized_body
    assert "cookie" not in serialized_body
    assert "tester@example.invalid" not in serialized_body


def test_reviewer_created_state_api_fetches_one_authorized_row_by_id() -> None:
    with _seeded_connection() as connection:
        created = create_reviewer_created_state_scaffold(
            connection,
            _reviewer_actor(),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            state_payload={"scaffold_state": "source_check_needed"},
        )

        status, _content_type, body = route_response(
            f"{REVIEWER_CREATED_STATE_API_PREFIX}/by-id"
            f"?reviewer_state_id={quote(created.reviewer_state_id)}",
            reviewer_created_state_api_context=_api_context(connection),
        )

    payload = _json_body(body)

    assert status == 200
    assert payload["reviewer_created_state"]["reviewer_state_id"] == (
        created.reviewer_state_id
    )
    assert payload["reviewer_created_state"]["state_payload"] == {
        "scaffold_state": "source_check_needed"
    }


def test_reviewer_created_state_api_returns_empty_list_for_scope_without_rows() -> None:
    with _empty_connection() as connection:
        status, _content_type, body = route_response(
            REVIEWER_CREATED_STATE_API_PREFIX,
            reviewer_created_state_api_context=_api_context(connection),
        )

    payload = _json_body(body)

    assert status == 200
    assert payload["reviewer_created_state"] == []
    assert payload["pagination"] == {"limit": 100, "offset": 0, "returned_count": 0}


def test_reviewer_created_state_api_returns_not_found_for_missing_record() -> None:
    with _empty_connection() as connection:
        status, _content_type, body = route_response(
            f"{REVIEWER_CREATED_STATE_API_PREFIX}/by-id"
            "?reviewer_state_id=reviewer-state:missing",
            reviewer_created_state_api_context=_api_context(connection),
        )

    payload = _json_body(body)

    assert status == 404
    assert payload["error"]["code"] == "reviewer_created_state_not_found"


def test_reviewer_created_state_api_filters_schema_backed_fields() -> None:
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
            source_record_key=FACILITY_KEY,
            state_payload={"scaffold_state": "source_check_needed"},
        )

        by_source_status, _content_type, by_source_body = route_response(
            f"{REVIEWER_CREATED_STATE_API_PREFIX}"
            f"?source_record_key={quote(COMPLAINT_KEY)}"
            "&state_kind=review_item_state_scaffold",
            reviewer_created_state_api_context=_api_context(connection),
        )
        by_actor_status, _content_type, by_actor_body = route_response(
            f"{REVIEWER_CREATED_STATE_API_PREFIX}"
            "?actor_provider_subject=fixture-subject-admin",
            reviewer_created_state_api_context=_api_context(connection),
        )

    by_source_payload = _json_body(by_source_body)
    by_actor_payload = _json_body(by_actor_body)

    assert by_source_status == 200
    assert [
        record["reviewer_state_id"]
        for record in by_source_payload["reviewer_created_state"]
    ] == [first.reviewer_state_id]
    assert by_source_payload["filters"] == {
        "source_record_key": COMPLAINT_KEY,
        "state_kind": "review_item_state_scaffold",
        "actor_provider_subject": None,
        "q": None,
    }
    assert by_actor_status == 200
    assert [
        record["reviewer_state_id"]
        for record in by_actor_payload["reviewer_created_state"]
    ] == [second.reviewer_state_id]


def test_reviewer_created_state_api_searches_non_secret_scaffold_fields() -> None:
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
            source_record_key=FACILITY_KEY,
            state_payload={"scaffold_state": "source_check_needed"},
        )

        display_status, _content_type, display_body = route_response(
            f"{REVIEWER_CREATED_STATE_API_PREFIX}?q=fixture%20admin",
            reviewer_created_state_api_context=_api_context(connection),
        )
        source_status, _content_type, source_body = route_response(
            f"{REVIEWER_CREATED_STATE_API_PREFIX}?q={quote(COMPLAINT_KEY.upper())}",
            reviewer_created_state_api_context=_api_context(connection),
        )

    display_payload = _json_body(display_body)
    source_payload = _json_body(source_body)

    assert display_status == 200
    assert [
        record["reviewer_state_id"]
        for record in display_payload["reviewer_created_state"]
    ] == [second.reviewer_state_id]
    assert display_payload["filters"] == {
        "source_record_key": None,
        "state_kind": None,
        "actor_provider_subject": None,
        "q": "fixture admin",
    }
    assert source_status == 200
    assert [
        record["reviewer_state_id"]
        for record in source_payload["reviewer_created_state"]
    ] == [first.reviewer_state_id]


def test_reviewer_created_state_api_search_returns_empty_list() -> None:
    with _seeded_connection() as connection:
        create_reviewer_created_state_scaffold(
            connection,
            _reviewer_actor(),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            state_payload={"scaffold_state": "in_review"},
        )

        status, _content_type, body = route_response(
            f"{REVIEWER_CREATED_STATE_API_PREFIX}?q=no-matching-state",
            reviewer_created_state_api_context=_api_context(connection),
        )

    payload = _json_body(body)

    assert status == 200
    assert payload["reviewer_created_state"] == []
    assert payload["filters"] == {
        "source_record_key": None,
        "state_kind": None,
        "actor_provider_subject": None,
        "q": "no-matching-state",
    }
    assert payload["pagination"] == {"limit": 100, "offset": 0, "returned_count": 0}


def test_reviewer_created_state_api_creates_reviewer_note() -> None:
    with _seeded_connection() as connection:
        before_source_rows = _source_rows(connection)

        status, content_type, body = route_response(
            f"{REVIEWER_CREATED_STATE_API_PREFIX}/reviewer-note"
            f"?source_record_key={quote(COMPLAINT_KEY)}",
            request_body=_json_bytes(
                {"note_text": "Need source follow-up before export handoff."}
            ),
            reviewer_created_state_api_context=_api_context(
                connection,
                actor=_reviewer_actor(),
            ),
        )

        after_source_rows = _source_rows(connection)
        counts = _table_counts(connection)

    payload = _json_body(body)

    assert status == 201
    assert content_type == "application/json; charset=utf-8"
    assert before_source_rows == after_source_rows
    assert counts == {
        "import_batches": 1,
        "source_records": 6,
        "reviewer_created_state": 1,
        "audit_events": 1,
        "reset_reload_planning_metadata": 0,
    }
    state_row = payload["reviewer_created_state"]
    assert state_row["source_record_key"] == COMPLAINT_KEY
    assert state_row["state_kind"] == "review_item_state_scaffold"
    assert state_row["state_payload"] == {
        "payload_kind": "reviewer_note_scaffold",
        "note_text": "Need source follow-up before export handoff.",
        "note_format": "plain_text",
        "source_record_key": COMPLAINT_KEY,
        "local_test_only": True,
    }
    assert state_row["created_by"]["provider_subject"] == "fixture-subject-reviewer"
    assert payload["workflow"] == {
        "created_reviewer_note": True,
        "local_test_only": True,
        "route_source": f"{REVIEWER_CREATED_STATE_API_PREFIX}/reviewer-note",
        "writes_create_audit_event": True,
        "source_of_record": "public portal",
        "does_not_mutate_source_derived_records": True,
    }
    serialized_body = body.decode("utf-8").casefold()
    assert "token" not in serialized_body
    assert "cookie" not in serialized_body
    assert "tester@example.invalid" not in serialized_body


def test_reviewer_created_state_api_reviewer_note_is_visible_after_write() -> None:
    with _seeded_connection() as connection:
        create_status, _content_type, create_body = route_response(
            f"{REVIEWER_CREATED_STATE_API_PREFIX}/reviewer-note"
            f"?source_record_key={quote(COMPLAINT_KEY)}",
            request_body=_json_bytes({"note_text": "Visible through the read seam."}),
            reviewer_created_state_api_context=_api_context(
                connection,
                actor=_reviewer_actor(),
            ),
        )
        created = _json_body(create_body)["reviewer_created_state"]

        list_status, _content_type, list_body = route_response(
            f"{REVIEWER_CREATED_STATE_API_PREFIX}"
            f"?source_record_key={quote(COMPLAINT_KEY)}",
            reviewer_created_state_api_context=_api_context(connection),
        )
        fetch_status, _content_type, fetch_body = route_response(
            f"{REVIEWER_CREATED_STATE_API_PREFIX}/by-id"
            f"?reviewer_state_id={quote(created['reviewer_state_id'])}",
            reviewer_created_state_api_context=_api_context(connection),
        )

    list_payload = _json_body(list_body)
    fetch_payload = _json_body(fetch_body)

    assert create_status == 201
    assert list_status == 200
    assert fetch_status == 200
    assert [
        row["reviewer_state_id"]
        for row in list_payload["reviewer_created_state"]
    ] == [created["reviewer_state_id"]]
    assert fetch_payload["reviewer_created_state"] == created


def test_reviewer_created_state_api_reviewer_note_rejects_unauthenticated_actor() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            f"{REVIEWER_CREATED_STATE_API_PREFIX}/reviewer-note"
            f"?source_record_key={quote(COMPLAINT_KEY)}",
            request_body=_json_bytes({"note_text": "Needs source review."}),
            reviewer_created_state_api_context=_api_context(connection, actor=None),
        )

    payload = _json_body(body)
    assert status == 401
    assert payload["error"]["code"] == "authentication_required"


@pytest.mark.parametrize("account_status", ["disabled", "revoked"])
def test_reviewer_created_state_api_reviewer_note_rejects_disabled_or_revoked_actor(
    account_status: str,
) -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            f"{REVIEWER_CREATED_STATE_API_PREFIX}/reviewer-note"
            f"?source_record_key={quote(COMPLAINT_KEY)}",
            request_body=_json_bytes({"note_text": "Needs source review."}),
            reviewer_created_state_api_context=_api_context(
                connection,
                actor=_reviewer_actor(account_status=account_status),
            ),
        )

    payload = _json_body(body)
    assert status == 403
    assert payload["error"]["code"] == "account_disabled_or_revoked"


def test_reviewer_created_state_api_reviewer_note_rejects_role_without_write() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            f"{REVIEWER_CREATED_STATE_API_PREFIX}/reviewer-note"
            f"?source_record_key={quote(COMPLAINT_KEY)}",
            request_body=_json_bytes({"note_text": "Needs source review."}),
            reviewer_created_state_api_context=_api_context(connection),
        )

    payload = _json_body(body)
    assert status == 403
    assert payload["error"]["code"] == "role_denied"


def test_reviewer_created_state_api_reviewer_note_rejects_out_of_scope_actor() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            f"{REVIEWER_CREATED_STATE_API_PREFIX}/reviewer-note"
            f"?source_record_key={quote(COMPLAINT_KEY)}",
            request_body=_json_bytes({"note_text": "Needs source review."}),
            reviewer_created_state_api_context=_api_context(
                connection,
                actor=_reviewer_actor(scopes=(OTHER_SCOPE,)),
            ),
        )

    payload = _json_body(body)
    assert status == 403
    assert payload["error"]["code"] == "scope_denied"


def test_reviewer_created_state_api_reviewer_note_rejects_missing_source_record() -> None:
    with _seeded_connection() as connection:
        missing_key_status, _content_type, missing_key_body = route_response(
            f"{REVIEWER_CREATED_STATE_API_PREFIX}/reviewer-note",
            request_body=_json_bytes({"note_text": "Needs source review."}),
            reviewer_created_state_api_context=_api_context(
                connection,
                actor=_reviewer_actor(),
            ),
        )
        missing_record_status, _content_type, missing_record_body = route_response(
            f"{REVIEWER_CREATED_STATE_API_PREFIX}/reviewer-note"
            "?source_record_key=complaint%3Amissing",
            request_body=_json_bytes({"note_text": "Needs source review."}),
            reviewer_created_state_api_context=_api_context(
                connection,
                actor=_reviewer_actor(),
            ),
        )
        counts = _table_counts(connection)

    assert missing_key_status == 400
    assert _json_body(missing_key_body)["error"]["code"] == "invalid_request"
    assert missing_record_status == 400
    assert _json_body(missing_record_body)["error"]["code"] == "invalid_request"
    assert counts["reviewer_created_state"] == 0
    assert counts["audit_events"] == 0


def test_reviewer_created_state_api_reviewer_note_rejects_invalid_payload() -> None:
    with _seeded_connection() as connection:
        missing_body_status, _content_type, missing_body_body = route_response(
            f"{REVIEWER_CREATED_STATE_API_PREFIX}/reviewer-note"
            f"?source_record_key={quote(COMPLAINT_KEY)}",
            reviewer_created_state_api_context=_api_context(
                connection,
                actor=_reviewer_actor(),
            ),
        )
        empty_note_status, _content_type, empty_note_body = route_response(
            f"{REVIEWER_CREATED_STATE_API_PREFIX}/reviewer-note"
            f"?source_record_key={quote(COMPLAINT_KEY)}",
            request_body=_json_bytes({"note_text": "   "}),
            reviewer_created_state_api_context=_api_context(
                connection,
                actor=_reviewer_actor(),
            ),
        )
        secret_note_status, _content_type, secret_note_body = route_response(
            f"{REVIEWER_CREATED_STATE_API_PREFIX}/reviewer-note"
            f"?source_record_key={quote(COMPLAINT_KEY)}",
            request_body=_json_bytes({"note_text": "A token was pasted here."}),
            reviewer_created_state_api_context=_api_context(
                connection,
                actor=_reviewer_actor(),
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


def test_reviewer_created_state_api_reviewer_note_preserves_existing_audit_rows() -> None:
    with _seeded_connection() as connection:
        create_reviewer_created_state_scaffold(
            connection,
            _admin_actor(),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            state_payload={"scaffold_state": "in_review"},
        )
        before_source_rows = _source_rows(connection)
        before_counts = _table_counts(connection)

        status, _content_type, _body = route_response(
            f"{REVIEWER_CREATED_STATE_API_PREFIX}/reviewer-note"
            f"?source_record_key={quote(COMPLAINT_KEY)}",
            request_body=_json_bytes({"note_text": "Second reviewer note."}),
            reviewer_created_state_api_context=_api_context(
                connection,
                actor=_reviewer_actor(),
            ),
        )
        after_source_rows = _source_rows(connection)
        after_counts = _table_counts(connection)

    assert status == 201
    assert before_source_rows == after_source_rows
    assert after_counts == {
        **before_counts,
        "reviewer_created_state": before_counts["reviewer_created_state"] + 1,
        "audit_events": before_counts["audit_events"] + 1,
    }


def test_reviewer_created_state_api_creates_reviewer_status() -> None:
    with _seeded_connection() as connection:
        before_source_rows = _source_rows(connection)

        status, content_type, body = route_response(
            f"{REVIEWER_CREATED_STATE_API_PREFIX}/reviewer-status"
            f"?source_record_key={quote(COMPLAINT_KEY)}",
            request_body=_json_bytes({"reviewer_status": "in_review"}),
            reviewer_created_state_api_context=_api_context(
                connection,
                actor=_reviewer_actor(),
            ),
        )

        after_source_rows = _source_rows(connection)
        counts = _table_counts(connection)

    payload = _json_body(body)

    assert status == 201
    assert content_type == "application/json; charset=utf-8"
    assert before_source_rows == after_source_rows
    assert counts == {
        "import_batches": 1,
        "source_records": 6,
        "reviewer_created_state": 1,
        "audit_events": 1,
        "reset_reload_planning_metadata": 0,
    }
    state_row = payload["reviewer_created_state"]
    assert state_row["source_record_key"] == COMPLAINT_KEY
    assert state_row["state_kind"] == "review_item_state_scaffold"
    assert state_row["state_payload"] == {
        "payload_kind": "reviewer_status_scaffold",
        "reviewer_status": "in_review",
        "source_record_key": COMPLAINT_KEY,
        "local_test_only": True,
    }
    assert state_row["created_by"]["provider_subject"] == "fixture-subject-reviewer"
    assert payload["workflow"] == {
        "created_reviewer_status": True,
        "local_test_only": True,
        "route_source": f"{REVIEWER_CREATED_STATE_API_PREFIX}/reviewer-status",
        "writes_create_audit_event": True,
        "source_of_record": "public portal",
        "does_not_mutate_source_derived_records": True,
    }
    serialized_body = body.decode("utf-8").casefold()
    assert "token" not in serialized_body
    assert "cookie" not in serialized_body
    assert "tester@example.invalid" not in serialized_body


def test_reviewer_created_state_api_reviewer_status_is_visible_after_write() -> None:
    with _seeded_connection() as connection:
        create_status, _content_type, create_body = route_response(
            f"{REVIEWER_CREATED_STATE_API_PREFIX}/reviewer-status"
            f"?source_record_key={quote(COMPLAINT_KEY)}",
            request_body=_json_bytes({"reviewer_status": "reviewed"}),
            reviewer_created_state_api_context=_api_context(
                connection,
                actor=_reviewer_actor(),
            ),
        )
        created = _json_body(create_body)["reviewer_created_state"]

        list_status, _content_type, list_body = route_response(
            f"{REVIEWER_CREATED_STATE_API_PREFIX}"
            f"?source_record_key={quote(COMPLAINT_KEY)}",
            reviewer_created_state_api_context=_api_context(connection),
        )
        fetch_status, _content_type, fetch_body = route_response(
            f"{REVIEWER_CREATED_STATE_API_PREFIX}/by-id"
            f"?reviewer_state_id={quote(created['reviewer_state_id'])}",
            reviewer_created_state_api_context=_api_context(connection),
        )

    list_payload = _json_body(list_body)
    fetch_payload = _json_body(fetch_body)

    assert create_status == 201
    assert list_status == 200
    assert fetch_status == 200
    assert [
        row["reviewer_state_id"]
        for row in list_payload["reviewer_created_state"]
    ] == [created["reviewer_state_id"]]
    assert fetch_payload["reviewer_created_state"] == created


def test_reviewer_created_state_api_reviewer_status_rejects_invalid_payload() -> None:
    with _seeded_connection() as connection:
        missing_body_status, _content_type, missing_body_body = route_response(
            f"{REVIEWER_CREATED_STATE_API_PREFIX}/reviewer-status"
            f"?source_record_key={quote(COMPLAINT_KEY)}",
            reviewer_created_state_api_context=_api_context(
                connection,
                actor=_reviewer_actor(),
            ),
        )
        empty_status, _content_type, empty_body = route_response(
            f"{REVIEWER_CREATED_STATE_API_PREFIX}/reviewer-status"
            f"?source_record_key={quote(COMPLAINT_KEY)}",
            request_body=_json_bytes({"reviewer_status": "   "}),
            reviewer_created_state_api_context=_api_context(
                connection,
                actor=_reviewer_actor(),
            ),
        )
        invalid_status, _content_type, invalid_body = route_response(
            f"{REVIEWER_CREATED_STATE_API_PREFIX}/reviewer-status"
            f"?source_record_key={quote(COMPLAINT_KEY)}",
            request_body=_json_bytes({"reviewer_status": "source_checked"}),
            reviewer_created_state_api_context=_api_context(
                connection,
                actor=_reviewer_actor(),
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


def test_reviewer_created_state_api_rejects_unauthenticated_actor() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            REVIEWER_CREATED_STATE_API_PREFIX,
            reviewer_created_state_api_context=_api_context(connection, actor=None),
        )

    payload = _json_body(body)
    assert status == 401
    assert payload["error"]["code"] == "authentication_required"


@pytest.mark.parametrize("account_status", ["disabled", "revoked"])
def test_reviewer_created_state_api_rejects_disabled_or_revoked_actor(
    account_status: str,
) -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            REVIEWER_CREATED_STATE_API_PREFIX,
            reviewer_created_state_api_context=_api_context(
                connection,
                actor=_read_only_actor(account_status=account_status),
            ),
        )

    payload = _json_body(body)
    assert status == 403
    assert payload["error"]["code"] == "account_disabled_or_revoked"


def test_reviewer_created_state_api_rejects_role_without_reviewer_state_read() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            REVIEWER_CREATED_STATE_API_PREFIX,
            reviewer_created_state_api_context=_api_context(
                connection,
                actor=_operator_actor(),
            ),
        )

    payload = _json_body(body)
    assert status == 403
    assert payload["error"]["code"] == "role_denied"


def test_reviewer_created_state_api_rejects_out_of_scope_actor() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            REVIEWER_CREATED_STATE_API_PREFIX,
            reviewer_created_state_api_context=_api_context(
                connection,
                actor=_read_only_actor(scopes=(OTHER_SCOPE,)),
            ),
        )

    payload = _json_body(body)
    assert status == 403
    assert payload["error"]["code"] == "scope_denied"


def test_reviewer_created_state_api_rejects_invalid_filter_and_paging_values() -> None:
    with _seeded_connection() as connection:
        invalid_kind_status, _content_type, invalid_kind_body = route_response(
            f"{REVIEWER_CREATED_STATE_API_PREFIX}?state_kind=annotation",
            reviewer_created_state_api_context=_api_context(connection),
        )
        invalid_limit_status, _content_type, invalid_limit_body = route_response(
            f"{REVIEWER_CREATED_STATE_API_PREFIX}?limit=0",
            reviewer_created_state_api_context=_api_context(connection),
        )
        invalid_search_status, _content_type, invalid_search_body = route_response(
            f"{REVIEWER_CREATED_STATE_API_PREFIX}?q={'x' * 121}",
            reviewer_created_state_api_context=_api_context(connection),
        )

    assert invalid_kind_status == 400
    assert _json_body(invalid_kind_body)["error"]["code"] == "invalid_request"
    assert invalid_limit_status == 400
    assert _json_body(invalid_limit_body)["error"]["code"] == "invalid_request"
    assert invalid_search_status == 400
    assert _json_body(invalid_search_body)["error"]["code"] == "invalid_request"


def test_reviewer_created_state_api_requires_explicit_local_test_context() -> None:
    status, _content_type, body = route_response(REVIEWER_CREATED_STATE_API_PREFIX)

    payload = _json_body(body)

    assert status == 503
    assert payload["error"]["code"] == "reviewer_created_state_api_context_required"


def test_reviewer_created_state_api_reads_do_not_mutate_persisted_tables() -> None:
    with _seeded_connection() as connection:
        created = create_reviewer_created_state_scaffold(
            connection,
            _reviewer_actor(),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            state_payload={"scaffold_state": "in_review"},
        )
        before_counts = _table_counts(connection)

        list_status, _content_type, _list_body = route_response(
            REVIEWER_CREATED_STATE_API_PREFIX,
            reviewer_created_state_api_context=_api_context(connection),
        )
        fetch_status, _content_type, _fetch_body = route_response(
            f"{REVIEWER_CREATED_STATE_API_PREFIX}/by-id"
            f"?reviewer_state_id={quote(created.reviewer_state_id)}",
            reviewer_created_state_api_context=_api_context(connection),
        )
        after_counts = _table_counts(connection)

    assert list_status == 200
    assert fetch_status == 200
    assert before_counts == after_counts == {
        "import_batches": 1,
        "source_records": 6,
        "reviewer_created_state": 1,
        "audit_events": 1,
        "reset_reload_planning_metadata": 0,
    }


def _json_body(body: bytes) -> dict[str, Any]:
    loaded = json.loads(body)
    assert isinstance(loaded, dict)
    return loaded


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True).encode("utf-8")


def _api_context(
    connection: Connection,
    *,
    actor: AuthenticatedActor | None | object = DEFAULT_ACTOR,
    scope: HostedAccessScope = TEST_SCOPE,
) -> ReviewerCreatedStateApiContext:
    context_actor = _read_only_actor() if actor is DEFAULT_ACTOR else actor
    return ReviewerCreatedStateApiContext(
        connection=connection,
        actor=cast(AuthenticatedActor | None, context_actor),
        scope=scope,
    )


def _reviewer_actor(
    *,
    scopes: tuple[HostedAccessScope, ...] = (TEST_SCOPE,),
    account_status: str = "active",
) -> AuthenticatedActor:
    return _actor(
        roles=("tester_reviewer",),
        scopes=scopes,
        account_status=account_status,
        actor_category="tester",
        provider_subject="fixture-subject-reviewer",
        display_name="Fixture Tester Reviewer",
        email="tester@example.invalid",
    )


def _read_only_actor(
    *,
    scopes: tuple[HostedAccessScope, ...] = (TEST_SCOPE,),
    account_status: str = "active",
) -> AuthenticatedActor:
    return _actor(
        roles=("read_only_tester",),
        scopes=scopes,
        account_status=account_status,
        actor_category="tester",
        provider_subject="fixture-subject-read-only",
        display_name="Fixture Read Only Tester",
        email="read-only@example.invalid",
    )


def _operator_actor() -> AuthenticatedActor:
    return _actor(
        roles=("developer_operator",),
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


def _source_rows(connection: Connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        select(hosted_source_derived_records).order_by(
            hosted_source_derived_records.c.source_record_key
        )
    ).mappings()
    return [dict(row) for row in rows]