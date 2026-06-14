from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Connection

from ccld_complaints.hosted_app.audit_events import hosted_audit_events
from ccld_complaints.hosted_app.auth import (
    AuthenticatedActor,
    HostedAccessScope,
    HostedAccountStatus,
    HostedActorCategory,
    HostedAuthenticationRequiredError,
    HostedRoleDeniedError,
    HostedScopeDeniedError,
    HostedTesterRole,
)
from ccld_complaints.hosted_app.reviewer_created_state import (
    ReviewerCreatedStateReferenceError,
    create_reviewer_created_state_scaffold,
    create_reviewer_note_scaffold,
    get_reviewer_created_state_scaffold,
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


def test_reviewer_created_state_is_stored_separately_without_source_mutation() -> None:
    with _seeded_connection() as connection:
        before_source_rows = _source_rows(connection)

        created = create_reviewer_created_state_scaffold(
            connection,
            _reviewer_actor(),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            state_payload={
                "scaffold_state": "source_check_needed",
                "note": "Local/test scaffold placeholder only.",
            },
        )

        after_source_rows = _source_rows(connection)
        reviewer_state_count = connection.execute(
            select(func.count()).select_from(hosted_reviewer_created_state)
        ).scalar_one()
        audit_event_count = connection.execute(
            select(func.count()).select_from(hosted_audit_events)
        ).scalar_one()

    assert before_source_rows == after_source_rows
    assert reviewer_state_count == 1
    assert audit_event_count == 1
    assert created.reviewer_state_id.startswith("reviewer-state:")
    assert created.source_record_key == COMPLAINT_KEY
    assert created.scope == TEST_SCOPE
    assert created.state_kind == "review_item_state_scaffold"
    assert created.state_payload == {
        "scaffold_state": "source_check_needed",
        "note": "Local/test scaffold placeholder only.",
    }
    assert created.created_at.endswith("+00:00")
    assert created.created_by_provider_subject == "fixture-subject-reviewer"
    assert created.created_by_provider_issuer == "fixture-managed-oidc-provider"
    assert created.created_by_display_name == "Fixture Tester Reviewer"
    assert created.created_by_actor_category == "tester"
    assert created.authorization_permission == "reviewer_state_write"


def test_reviewer_created_state_can_be_read_for_authorized_scope() -> None:
    with _seeded_connection() as connection:
        created = create_reviewer_created_state_scaffold(
            connection,
            _reviewer_actor(),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            state_payload={"scaffold_state": "in_review"},
        )

        [read] = list_reviewer_created_state_scaffold(
            connection,
            _read_only_actor(),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
        )

    assert read == created
    assert read.state_payload == {"scaffold_state": "in_review"}


def test_reviewer_note_scaffold_uses_existing_state_and_audit_path() -> None:
    with _seeded_connection() as connection:
        before_source_rows = _source_rows(connection)

        created = create_reviewer_note_scaffold(
            connection,
            _reviewer_actor(),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            note_text="Need to verify the source narrative before export.",
        )

        after_source_rows = _source_rows(connection)
        reviewer_state_count = connection.execute(
            select(func.count()).select_from(hosted_reviewer_created_state)
        ).scalar_one()
        audit_event_count = connection.execute(
            select(func.count()).select_from(hosted_audit_events)
        ).scalar_one()

    assert before_source_rows == after_source_rows
    assert reviewer_state_count == 1
    assert audit_event_count == 1
    assert created.state_kind == "review_item_state_scaffold"
    assert created.state_payload == {
        "payload_kind": "reviewer_note_scaffold",
        "note_text": "Need to verify the source narrative before export.",
        "note_format": "plain_text",
        "source_record_key": COMPLAINT_KEY,
        "local_test_only": True,
    }


def test_reviewer_note_scaffold_rejects_empty_or_secret_like_text() -> None:
    with _seeded_connection() as connection:
        with pytest.raises(ValueError, match="note text"):
            create_reviewer_note_scaffold(
                connection,
                _reviewer_actor(),
                scope=TEST_SCOPE,
                source_record_key=COMPLAINT_KEY,
                note_text="   ",
            )
        with pytest.raises(ValueError, match="secret-like"):
            create_reviewer_note_scaffold(
                connection,
                _reviewer_actor(),
                scope=TEST_SCOPE,
                source_record_key=COMPLAINT_KEY,
                note_text="Temporary token value was pasted here.",
            )

        assert connection.execute(
            select(func.count()).select_from(hosted_reviewer_created_state)
        ).scalar_one() == 0
        assert connection.execute(
            select(func.count()).select_from(hosted_audit_events)
        ).scalar_one() == 0


def test_reviewer_created_state_can_be_fetched_by_authorized_state_id() -> None:
    with _seeded_connection() as connection:
        created = create_reviewer_created_state_scaffold(
            connection,
            _reviewer_actor(),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            state_payload={"scaffold_state": "source_check_needed"},
        )

        read = get_reviewer_created_state_scaffold(
            connection,
            _read_only_actor(),
            scope=TEST_SCOPE,
            reviewer_state_id=created.reviewer_state_id,
        )

    assert read == created


def test_reviewer_created_state_write_requires_authenticated_actor() -> None:
    with _seeded_connection() as connection:
        with pytest.raises(HostedAuthenticationRequiredError, match="authenticated actor"):
            create_reviewer_created_state_scaffold(
                connection,
                None,
                scope=TEST_SCOPE,
                source_record_key=COMPLAINT_KEY,
                state_payload={"scaffold_state": "in_review"},
            )


@pytest.mark.parametrize("account_status", ["disabled", "revoked"])
def test_reviewer_created_state_write_rejects_disabled_or_revoked_actor(
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


def test_reviewer_created_state_write_rejects_role_without_write_permission() -> None:
    with _seeded_connection() as connection:
        with pytest.raises(HostedRoleDeniedError, match="reviewer_state_write"):
            create_reviewer_created_state_scaffold(
                connection,
                _read_only_actor(),
                scope=TEST_SCOPE,
                source_record_key=COMPLAINT_KEY,
                state_payload={"scaffold_state": "in_review"},
            )


def test_reviewer_created_state_write_rejects_actor_outside_requested_scope() -> None:
    with _seeded_connection() as connection:
        with pytest.raises(HostedScopeDeniedError, match="project or corpus scope"):
            create_reviewer_created_state_scaffold(
                connection,
                _reviewer_actor(scopes=(OTHER_SCOPE,)),
                scope=TEST_SCOPE,
                source_record_key=COMPLAINT_KEY,
                state_payload={"scaffold_state": "in_review"},
            )


def test_reviewer_created_state_write_rejects_source_record_outside_scope() -> None:
    with _seeded_connection() as connection:
        with pytest.raises(HostedScopeDeniedError, match="source-derived reference"):
            create_reviewer_created_state_scaffold(
                connection,
                _reviewer_actor(scopes=(OTHER_SCOPE,)),
                scope=OTHER_SCOPE,
                source_record_key=COMPLAINT_KEY,
                state_payload={"scaffold_state": "in_review"},
            )


def test_reviewer_created_state_write_rejects_invalid_source_reference() -> None:
    with _seeded_connection() as connection:
        with pytest.raises(ReviewerCreatedStateReferenceError, match="source-derived record"):
            create_reviewer_created_state_scaffold(
                connection,
                _reviewer_actor(),
                scope=TEST_SCOPE,
                source_record_key="complaint:missing",
                state_payload={"scaffold_state": "in_review"},
            )
        reviewer_state_count = connection.execute(
            select(func.count()).select_from(hosted_reviewer_created_state)
        ).scalar_one()
        audit_event_count = connection.execute(
            select(func.count()).select_from(hosted_audit_events)
        ).scalar_one()

    assert reviewer_state_count == 0
    assert audit_event_count == 0


def test_reviewer_created_state_read_requires_scope() -> None:
    with _seeded_connection() as connection:
        create_reviewer_created_state_scaffold(
            connection,
            _reviewer_actor(),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            state_payload={"scaffold_state": "in_review"},
        )

        with pytest.raises(HostedScopeDeniedError):
            list_reviewer_created_state_scaffold(
                connection,
                _read_only_actor(scopes=(OTHER_SCOPE,)),
                scope=TEST_SCOPE,
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
    )


def _read_only_actor(
    *,
    scopes: tuple[HostedAccessScope, ...] = (TEST_SCOPE,),
) -> AuthenticatedActor:
    return _actor(
        roles=("read_only_tester",),
        scopes=scopes,
        actor_category="tester",
        provider_subject="fixture-subject-read-only",
        display_name="Fixture Read Only Tester",
    )


def _actor(
    *,
    roles: tuple[str, ...],
    scopes: tuple[HostedAccessScope, ...],
    account_status: str = "active",
    actor_category: str = "tester",
    provider_subject: str,
    display_name: str,
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
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)
    connection = engine.connect()
    transaction = connection.begin()
    artifact = load_seeded_corpus_artifact(FIXTURE)
    import_seeded_corpus_artifact(connection, artifact)
    transaction.commit()
    return connection


def _source_rows(connection: Connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        select(hosted_source_derived_records).order_by(
            hosted_source_derived_records.c.source_record_key
        )
    ).mappings()
    return [dict(row) for row in rows]