from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Connection

from ccld_complaints.hosted_app.auth import (
    AUTH_PROVIDER_CLASS_ENV,
    IMPORT_RELOAD_PERMISSION,
    MANAGED_OIDC_OAUTH2_PROVIDER_CLASS,
    REVIEWER_STATE_READ_PERMISSION,
    REVIEWER_STATE_WRITE_PERMISSION,
    SOURCE_DERIVED_READ_PERMISSION,
    USER_ROLE_ADMIN_PERMISSION,
    AuthenticatedActor,
    AuthorizationTarget,
    HostedAccessScope,
    HostedAccountDisabledError,
    HostedAccountStatus,
    HostedActorCategory,
    HostedAuthConfigError,
    HostedAuthenticationRequiredError,
    HostedRoleDeniedError,
    HostedScopeDeniedError,
    HostedTesterRole,
    get_authorized_source_derived_record_by_key,
    list_authorized_source_derived_records,
    load_hosted_auth_config,
    require_permission,
)
from ccld_complaints.hosted_app.seeded_import import (
    hosted_seeded_import_metadata,
    import_seeded_corpus_artifact,
    load_seeded_corpus_artifact,
)

FIXTURE = Path("tests/fixtures/hosted_seeded_corpus/validated_seeded_corpus.json")
TEST_SCOPE = HostedAccessScope("seeded_corpus", "seeded-ccld-fixture-2026-06-13")
OTHER_SCOPE = HostedAccessScope("seeded_corpus", "different-seeded-corpus")
SOURCE_LIST_TARGET = AuthorizationTarget(
    "source_derived_record_list",
    "seeded-ccld-fixture-2026-06-13",
)
REVIEWER_STATE_TARGET = AuthorizationTarget("reviewer_created_state", "future-review-item")
IMPORT_TARGET = AuthorizationTarget("import_batch", "seeded-ccld-fixture-2026-06-13")
AUTH_TARGET = AuthorizationTarget("auth_access", "future-role-assignment")


def test_hosted_auth_config_is_safe_when_unset() -> None:
    config = load_hosted_auth_config(environ={})

    assert config.configured is False
    assert config.provider_class is None
    assert config.safe_provider_class == "<unset>"
    assert config.provider_class_env == AUTH_PROVIDER_CLASS_ENV
    assert config.required_claims == (
        "sub",
        "iss",
        "roles",
        "scopes",
        "account_status",
    )


def test_hosted_auth_config_accepts_managed_oidc_provider_class_only() -> None:
    config = load_hosted_auth_config(
        environ={AUTH_PROVIDER_CLASS_ENV: MANAGED_OIDC_OAUTH2_PROVIDER_CLASS}
    )

    assert config.configured is True
    assert config.provider_class == "managed-oidc-oauth2"
    assert config.safe_provider_class == "managed-oidc-oauth2"

    with pytest.raises(HostedAuthConfigError, match=AUTH_PROVIDER_CLASS_ENV):
        load_hosted_auth_config(environ={AUTH_PROVIDER_CLASS_ENV: "local-password"})


def test_hosted_auth_config_can_require_provider_class() -> None:
    with pytest.raises(HostedAuthConfigError, match=AUTH_PROVIDER_CLASS_ENV):
        load_hosted_auth_config(environ={}, require_provider_class=True)


def test_require_permission_returns_audit_ready_context_for_active_actor() -> None:
    actor = _read_only_actor()

    decision = require_permission(
        actor,
        permission=SOURCE_DERIVED_READ_PERMISSION,
        scope=TEST_SCOPE,
        target=SOURCE_LIST_TARGET,
    )

    assert decision.permission == "source_derived_read"
    assert decision.scope == TEST_SCOPE
    assert decision.target == SOURCE_LIST_TARGET
    assert decision.authorized_at.endswith("+00:00")
    assert decision.actor.provider_subject == "fixture-subject-read-only"
    assert decision.actor.provider_issuer == "fixture-managed-oidc-provider"
    assert decision.actor.actor_category == "tester"
    assert decision.actor.account_status == "active"
    assert decision.actor.roles == ("read_only_tester",)
    assert decision.actor.scopes == (TEST_SCOPE,)


def test_require_permission_rejects_unauthenticated_actor() -> None:
    with pytest.raises(HostedAuthenticationRequiredError, match="authenticated actor"):
        require_permission(
            None,
            permission=SOURCE_DERIVED_READ_PERMISSION,
            scope=TEST_SCOPE,
            target=SOURCE_LIST_TARGET,
        )


def test_require_permission_rejects_disabled_actor() -> None:
    with pytest.raises(HostedAccountDisabledError, match="disabled or revoked"):
        require_permission(
            _read_only_actor(account_status="disabled"),
            permission=SOURCE_DERIVED_READ_PERMISSION,
            scope=TEST_SCOPE,
            target=SOURCE_LIST_TARGET,
        )


def test_require_permission_rejects_role_without_required_permission() -> None:
    actor = _actor(roles=(), scopes=(TEST_SCOPE,))

    with pytest.raises(HostedRoleDeniedError, match="source_derived_read"):
        require_permission(
            actor,
            permission=SOURCE_DERIVED_READ_PERMISSION,
            scope=TEST_SCOPE,
            target=SOURCE_LIST_TARGET,
        )


def test_require_permission_rejects_actor_outside_requested_scope() -> None:
    with pytest.raises(HostedScopeDeniedError, match="project or corpus scope"):
        require_permission(
            _read_only_actor(scopes=(OTHER_SCOPE,)),
            permission=SOURCE_DERIVED_READ_PERMISSION,
            scope=TEST_SCOPE,
            target=SOURCE_LIST_TARGET,
        )


def test_read_only_access_does_not_grant_reviewer_or_operator_permissions() -> None:
    actor = _read_only_actor()

    require_permission(
        actor,
        permission=SOURCE_DERIVED_READ_PERMISSION,
        scope=TEST_SCOPE,
        target=SOURCE_LIST_TARGET,
    )
    denied_permissions = (
        (REVIEWER_STATE_WRITE_PERMISSION, REVIEWER_STATE_TARGET),
        (IMPORT_RELOAD_PERMISSION, IMPORT_TARGET),
        (USER_ROLE_ADMIN_PERMISSION, AUTH_TARGET),
    )
    for permission, target in denied_permissions:
        with pytest.raises(HostedRoleDeniedError):
            require_permission(
                actor,
                permission=permission,
                scope=TEST_SCOPE,
                target=target,
            )


def test_source_derived_read_permission_does_not_grant_reviewer_state_read() -> None:
    actor = _actor(
        roles=("developer_operator",),
        scopes=(TEST_SCOPE,),
        actor_category="operator",
    )

    require_permission(
        actor,
        permission=SOURCE_DERIVED_READ_PERMISSION,
        scope=TEST_SCOPE,
        target=SOURCE_LIST_TARGET,
    )

    with pytest.raises(HostedRoleDeniedError, match="reviewer_state_read"):
        require_permission(
            actor,
            permission=REVIEWER_STATE_READ_PERMISSION,
            scope=TEST_SCOPE,
            target=REVIEWER_STATE_TARGET,
        )


def test_authorized_source_derived_read_service_returns_staged_records_only() -> None:
    with _seeded_connection() as connection:
        records = list_authorized_source_derived_records(
            connection,
            _read_only_actor(),
            scope=TEST_SCOPE,
            entity_type="complaint",
        )

    assert len(records) == 1
    assert records[0].entity_type == "complaint"
    assert records[0].import_batch.import_batch_id == TEST_SCOPE.scope_id
    assert records[0].original_values["finding"] == "Unsubstantiated"
    assert "review_status" not in records[0].original_values
    assert "annotation" not in records[0].original_values


def test_authorized_source_derived_fetch_rejects_unauthenticated_actor() -> None:
    with _seeded_connection() as connection:
        with pytest.raises(HostedAuthenticationRequiredError):
            get_authorized_source_derived_record_by_key(
                connection,
                None,
                scope=TEST_SCOPE,
                source_record_key="complaint:ccld:complaint:32-CR-20220407124448",
            )


def test_authorized_source_derived_list_rejects_out_of_scope_actor_before_read() -> None:
    with _seeded_connection() as connection:
        with pytest.raises(HostedScopeDeniedError):
            list_authorized_source_derived_records(
                connection,
                _read_only_actor(scopes=(OTHER_SCOPE,)),
                scope=TEST_SCOPE,
            )


def test_authorized_source_derived_list_rejects_mismatched_import_batch_scope() -> None:
    with _seeded_connection() as connection:
        with pytest.raises(HostedScopeDeniedError, match="import batch"):
            list_authorized_source_derived_records(
                connection,
                _read_only_actor(),
                scope=TEST_SCOPE,
                import_batch_id=OTHER_SCOPE.scope_id,
            )


def test_authorized_source_derived_fetch_rejects_record_outside_requested_scope() -> None:
    with _seeded_connection() as connection:
        with pytest.raises(HostedScopeDeniedError, match="source-derived record"):
            get_authorized_source_derived_record_by_key(
                connection,
                _read_only_actor(scopes=(OTHER_SCOPE,)),
                scope=OTHER_SCOPE,
                source_record_key="complaint:ccld:complaint:32-CR-20220407124448",
            )


def test_admin_scope_is_still_required_for_source_derived_reads() -> None:
    with _seeded_connection() as connection:
        with pytest.raises(HostedScopeDeniedError):
            list_authorized_source_derived_records(
                connection,
                _actor(roles=("admin",), scopes=(OTHER_SCOPE,), actor_category="admin"),
                scope=TEST_SCOPE,
            )


def _read_only_actor(
    *,
    account_status: str = "active",
    scopes: tuple[HostedAccessScope, ...] = (TEST_SCOPE,),
) -> AuthenticatedActor:
    return _actor(
        roles=("read_only_tester",),
        scopes=scopes,
        account_status=account_status,
    )


def _actor(
    *,
    roles: tuple[str, ...],
    scopes: tuple[HostedAccessScope, ...],
    account_status: str = "active",
    actor_category: str = "tester",
) -> AuthenticatedActor:
    return AuthenticatedActor(
        provider_subject="fixture-subject-read-only",
        provider_issuer="fixture-managed-oidc-provider",
        display_name="Fixture Read Only Tester",
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