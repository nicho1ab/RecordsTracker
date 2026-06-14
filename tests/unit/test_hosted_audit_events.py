from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Connection

import ccld_complaints.hosted_app.reviewer_created_state as reviewer_created_state
from ccld_complaints.hosted_app.audit_events import (
    hosted_audit_events,
    list_hosted_audit_events_scaffold,
)
from ccld_complaints.hosted_app.auth import (
    AuthenticatedActor,
    HostedAccessScope,
    HostedAccountStatus,
    HostedActorCategory,
    HostedRoleDeniedError,
    HostedTesterRole,
)
from ccld_complaints.hosted_app.reviewer_created_state import (
    create_reviewer_created_state_scaffold,
    create_reviewer_note_scaffold,
    hosted_reviewer_created_state,
    list_reviewer_created_state_scaffold,
)
from ccld_complaints.hosted_app.seeded_import import (
    hosted_seeded_import_metadata,
    hosted_source_derived_records,
    import_seeded_corpus_artifact,
    load_seeded_corpus_artifact,
)

FIXTURE = Path("tests/fixtures/hosted_seeded_corpus/validated_seeded_corpus.json")
TEST_SCOPE = HostedAccessScope("seeded_corpus", "seeded-ccld-fixture-2026-06-13")
OTHER_SCOPE = HostedAccessScope("seeded_corpus", "different-seeded-corpus")
COMPLAINT_KEY = "complaint:ccld:complaint:32-CR-20220407124448"


def test_audit_event_is_created_for_successful_reviewer_state_write_only() -> None:
    with _seeded_connection() as connection:
        source_rows_before = _source_rows(connection)
        created = create_reviewer_created_state_scaffold(
            connection,
            _reviewer_actor(),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            state_payload={"scaffold_state": "source_check_needed"},
        )

        [audit_event] = list_hosted_audit_events_scaffold(
            connection,
            _operator_actor(),
            scope=TEST_SCOPE,
            target_reviewer_state_id=created.reviewer_state_id,
        )
        source_rows_after = _source_rows(connection)
        reviewer_state_rows = connection.execute(
            select(func.count()).select_from(hosted_reviewer_created_state)
        ).scalar_one()
        [reviewer_state_after_audit] = list_reviewer_created_state_scaffold(
            connection,
            _read_only_actor(),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
        )

    assert source_rows_before == source_rows_after
    assert reviewer_state_rows == 1
    assert reviewer_state_after_audit == created
    assert audit_event.audit_event_id.startswith("audit-event:")
    assert audit_event.occurred_at == created.created_at
    assert audit_event.actor_provider_subject == "fixture-subject-reviewer"
    assert audit_event.actor_provider_issuer == "fixture-managed-oidc-provider"
    assert audit_event.actor_display_name == "Fixture Tester Reviewer"
    assert audit_event.actor_category == "tester"
    assert audit_event.authorization_permission == "reviewer_state_write"
    assert audit_event.scope == TEST_SCOPE
    assert audit_event.action == "reviewer_created_state_scaffold.create"
    assert audit_event.target_type == "reviewer_created_state"
    assert audit_event.target_reviewer_state_id == created.reviewer_state_id
    assert audit_event.source_record_key == COMPLAINT_KEY
    assert audit_event.source_entity_type == "complaint"
    assert audit_event.source_stable_source_id == "ccld:complaint:32-CR-20220407124448"
    assert audit_event.source_document_id == "ccld:document:157806098:3"
    assert audit_event.context_metadata == {
        "state_kind": "review_item_state_scaffold",
        "state_payload_keys": ["scaffold_state"],
        "source_record_key": COMPLAINT_KEY,
    }


def test_audit_event_is_created_for_successful_reviewer_note_write() -> None:
    with _seeded_connection() as connection:
        created = create_reviewer_note_scaffold(
            connection,
            _reviewer_actor(),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            note_text="Audit this local test note.",
        )

        [audit_event] = list_hosted_audit_events_scaffold(
            connection,
            _operator_actor(),
            scope=TEST_SCOPE,
            target_reviewer_state_id=created.reviewer_state_id,
        )

    assert audit_event.action == "reviewer_created_state_scaffold.create"
    assert audit_event.target_reviewer_state_id == created.reviewer_state_id
    assert audit_event.context_metadata == {
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


def test_failed_reviewer_state_authorization_does_not_create_audit_event() -> None:
    with _seeded_connection() as connection:
        with pytest.raises(HostedRoleDeniedError, match="reviewer_state_write"):
            create_reviewer_created_state_scaffold(
                connection,
                _read_only_actor(),
                scope=TEST_SCOPE,
                source_record_key=COMPLAINT_KEY,
                state_payload={"scaffold_state": "in_review"},
            )

        assert _reviewer_state_count(connection) == 0
        assert _audit_event_count(connection) == 0


@pytest.mark.parametrize("account_status", ["disabled", "revoked"])
def test_disabled_or_revoked_failed_write_does_not_create_audit_event(
    account_status: str,
) -> None:
    with _seeded_connection() as connection:
        with pytest.raises(PermissionError, match="disabled or revoked"):
            create_reviewer_created_state_scaffold(
                connection,
                _reviewer_actor(account_status=account_status),
                scope=TEST_SCOPE,
                source_record_key=COMPLAINT_KEY,
                state_payload={"scaffold_state": "in_review"},
            )

        assert _reviewer_state_count(connection) == 0
        assert _audit_event_count(connection) == 0


def test_out_of_scope_failed_write_does_not_create_audit_event() -> None:
    with _seeded_connection() as connection:
        with pytest.raises(PermissionError, match="project or corpus scope"):
            create_reviewer_created_state_scaffold(
                connection,
                _reviewer_actor(scopes=(OTHER_SCOPE,)),
                scope=TEST_SCOPE,
                source_record_key=COMPLAINT_KEY,
                state_payload={"scaffold_state": "in_review"},
            )

        assert _reviewer_state_count(connection) == 0
        assert _audit_event_count(connection) == 0


def test_audit_persistence_failure_rolls_back_reviewer_state_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_audit_write(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("fixture audit persistence failure")

    with _seeded_connection() as connection:
        monkeypatch.setattr(
            reviewer_created_state,
            "create_hosted_audit_event",
            fail_audit_write,
        )

        with pytest.raises(RuntimeError, match="fixture audit persistence failure"):
            create_reviewer_created_state_scaffold(
                connection,
                _reviewer_actor(),
                scope=TEST_SCOPE,
                source_record_key=COMPLAINT_KEY,
                state_payload={"scaffold_state": "in_review"},
            )

        assert _reviewer_state_count(connection) == 0
        assert _audit_event_count(connection) == 0


def test_audit_event_read_requires_audit_permission() -> None:
    with _seeded_connection() as connection:
        create_reviewer_created_state_scaffold(
            connection,
            _reviewer_actor(),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            state_payload={"scaffold_state": "in_review"},
        )

        with pytest.raises(HostedRoleDeniedError, match="audit_read"):
            list_hosted_audit_events_scaffold(
                connection,
                _read_only_actor(),
                scope=TEST_SCOPE,
            )


def test_audit_event_context_omits_secret_like_actor_fields() -> None:
    with _seeded_connection() as connection:
        create_reviewer_created_state_scaffold(
            connection,
            _reviewer_actor(),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            state_payload={"scaffold_state": "in_review"},
        )

        [audit_event] = list_hosted_audit_events_scaffold(
            connection,
            _operator_actor(),
            scope=TEST_SCOPE,
        )

    serialized_context = str(dict(audit_event.context_metadata)).casefold()
    assert "token" not in serialized_context
    assert "cookie" not in serialized_context
    assert "authorization" not in serialized_context
    assert "connection" not in serialized_context
    assert "tester@example.invalid" not in serialized_context


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


def _operator_actor() -> AuthenticatedActor:
    return _actor(
        roles=("developer_operator",),
        scopes=(TEST_SCOPE,),
        account_status="active",
        actor_category="operator",
        provider_subject="fixture-subject-operator",
        display_name="Fixture Operator",
        email="operator@example.invalid",
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


def _source_rows(connection: Connection) -> list[dict[str, object]]:
    rows = connection.execute(
        select(hosted_source_derived_records).order_by(
            hosted_source_derived_records.c.source_record_key
        )
    ).mappings()
    return [dict(row) for row in rows]


def _reviewer_state_count(connection: Connection) -> int:
    return connection.execute(
        select(func.count()).select_from(hosted_reviewer_created_state)
    ).scalar_one()


def _audit_event_count(connection: Connection) -> int:
    return connection.execute(
        select(func.count()).select_from(hosted_audit_events)
    ).scalar_one()