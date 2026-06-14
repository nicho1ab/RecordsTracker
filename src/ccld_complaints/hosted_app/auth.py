from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, cast

from sqlalchemy.engine import Connection

from ccld_complaints.hosted_app.seeded_import import SourceDerivedEntityType
from ccld_complaints.hosted_app.source_derived_reads import (
    SourceDerivedRecordRead,
    get_source_derived_record_by_identity,
    get_source_derived_record_by_key,
    list_source_derived_records,
)

AUTH_PROVIDER_CLASS_ENV = "CCLD_HOSTED_TESTER_AUTH_PROVIDER_CLASS"
MANAGED_OIDC_OAUTH2_PROVIDER_CLASS = "managed-oidc-oauth2"
AUTH_REQUIRED_CLAIMS = (
    "sub",
    "iss",
    "roles",
    "scopes",
    "account_status",
)

AuthProviderClass = Literal["managed-oidc-oauth2"]
HostedAccountStatus = Literal["active", "disabled", "revoked"]
HostedActorCategory = Literal["admin", "tester", "operator", "system"]
HostedAccessScopeType = Literal["project", "corpus", "seeded_corpus", "test_project"]
HostedTesterRole = Literal[
    "admin",
    "tester_reviewer",
    "read_only_tester",
    "developer_operator",
    "system",
]
HostedPermission = Literal[
    "source_derived_read",
    "reviewer_state_write",
    "correction_propose",
    "correction_decide",
    "export_prepare",
    "export_finalize",
    "feedback_submit",
    "import_reload",
    "reset_destructive",
    "user_role_admin",
    "audit_read",
]
AuthorizationTargetType = Literal[
    "source_derived_record_list",
    "source_derived_record",
    "reviewer_created_state",
    "audit_event",
    "import_batch",
    "export_packet",
    "auth_access",
]

SOURCE_DERIVED_READ_PERMISSION: HostedPermission = "source_derived_read"
REVIEWER_STATE_WRITE_PERMISSION: HostedPermission = "reviewer_state_write"
IMPORT_RELOAD_PERMISSION: HostedPermission = "import_reload"
USER_ROLE_ADMIN_PERMISSION: HostedPermission = "user_role_admin"
AUDIT_READ_PERMISSION: HostedPermission = "audit_read"

ROLE_PERMISSIONS: Mapping[HostedTesterRole, frozenset[HostedPermission]] = {
    "admin": frozenset(
        {
            "source_derived_read",
            "reviewer_state_write",
            "correction_propose",
            "correction_decide",
            "export_prepare",
            "export_finalize",
            "feedback_submit",
            "import_reload",
            "reset_destructive",
            "user_role_admin",
            "audit_read",
        }
    ),
    "tester_reviewer": frozenset(
        {
            "source_derived_read",
            "reviewer_state_write",
            "correction_propose",
            "export_prepare",
            "feedback_submit",
        }
    ),
    "read_only_tester": frozenset({"source_derived_read"}),
    "developer_operator": frozenset(
        {
            "source_derived_read",
            "import_reload",
            "audit_read",
        }
    ),
    "system": frozenset({"source_derived_read", "import_reload"}),
}


class HostedAuthConfigError(ValueError):
    pass


class HostedAuthorizationError(PermissionError):
    pass


class HostedAuthenticationRequiredError(HostedAuthorizationError):
    pass


class HostedAccountDisabledError(HostedAuthorizationError):
    pass


class HostedRoleDeniedError(HostedAuthorizationError):
    pass


class HostedScopeDeniedError(HostedAuthorizationError):
    pass


@dataclass(frozen=True)
class HostedAuthConfig:
    provider_class: AuthProviderClass | None
    provider_class_env: str = AUTH_PROVIDER_CLASS_ENV
    required_claims: tuple[str, ...] = AUTH_REQUIRED_CLAIMS

    @property
    def configured(self) -> bool:
        return self.provider_class is not None

    @property
    def safe_provider_class(self) -> str:
        return "<unset>" if self.provider_class is None else self.provider_class


@dataclass(frozen=True)
class HostedAccessScope:
    scope_type: HostedAccessScopeType
    scope_id: str

    def __post_init__(self) -> None:
        if not self.scope_id.strip():
            raise ValueError("Hosted access scope ID must not be empty.")

    def matches(self, required_scope: HostedAccessScope) -> bool:
        return (
            self.scope_type == required_scope.scope_type
            and self.scope_id == required_scope.scope_id
        )


@dataclass(frozen=True)
class AuthorizationTarget:
    target_type: AuthorizationTargetType
    target_id: str

    def __post_init__(self) -> None:
        if not self.target_id.strip():
            raise ValueError("Authorization target ID must not be empty.")


@dataclass(frozen=True)
class ActorAuditContext:
    provider_subject: str
    provider_issuer: str
    display_name: str | None
    email: str | None
    actor_category: HostedActorCategory
    account_status: HostedAccountStatus
    roles: tuple[HostedTesterRole, ...]
    scopes: tuple[HostedAccessScope, ...]


@dataclass(frozen=True)
class AuthenticatedActor:
    provider_subject: str
    provider_issuer: str
    display_name: str | None
    email: str | None
    actor_category: HostedActorCategory
    account_status: HostedAccountStatus
    roles: tuple[HostedTesterRole, ...]
    scopes: tuple[HostedAccessScope, ...]

    def __post_init__(self) -> None:
        if not self.provider_subject.strip():
            raise ValueError("Authenticated actor provider subject must not be empty.")
        if not self.provider_issuer.strip():
            raise ValueError("Authenticated actor provider issuer must not be empty.")

    @property
    def permissions(self) -> frozenset[HostedPermission]:
        allowed_permissions: set[HostedPermission] = set()
        for role in self.roles:
            allowed_permissions.update(ROLE_PERMISSIONS[role])
        return frozenset(allowed_permissions)

    def has_permission(self, permission: HostedPermission) -> bool:
        return permission in self.permissions

    def has_scope(self, required_scope: HostedAccessScope) -> bool:
        return any(scope.matches(required_scope) for scope in self.scopes)

    def audit_context(self) -> ActorAuditContext:
        return ActorAuditContext(
            provider_subject=self.provider_subject,
            provider_issuer=self.provider_issuer,
            display_name=self.display_name,
            email=self.email,
            actor_category=self.actor_category,
            account_status=self.account_status,
            roles=self.roles,
            scopes=self.scopes,
        )


@dataclass(frozen=True)
class AuthorizationDecision:
    actor: ActorAuditContext
    permission: HostedPermission
    scope: HostedAccessScope
    target: AuthorizationTarget
    authorized_at: str


def load_hosted_auth_config(
    environ: Mapping[str, str] | None = None,
    *,
    require_provider_class: bool = False,
) -> HostedAuthConfig:
    active_environ = os.environ if environ is None else environ
    raw_provider_class = active_environ.get(AUTH_PROVIDER_CLASS_ENV, "").strip()
    if not raw_provider_class:
        if require_provider_class:
            raise HostedAuthConfigError(
                f"Set {AUTH_PROVIDER_CLASS_ENV} to {MANAGED_OIDC_OAUTH2_PROVIDER_CLASS}."
            )
        return HostedAuthConfig(provider_class=None)
    return HostedAuthConfig(
        provider_class=validate_auth_provider_class(raw_provider_class)
    )


def validate_auth_provider_class(provider_class: str) -> AuthProviderClass:
    normalized_provider_class = provider_class.strip().lower()
    if normalized_provider_class != MANAGED_OIDC_OAUTH2_PROVIDER_CLASS:
        raise HostedAuthConfigError(
            f"{AUTH_PROVIDER_CLASS_ENV} must be {MANAGED_OIDC_OAUTH2_PROVIDER_CLASS!r}."
        )
    return cast(AuthProviderClass, normalized_provider_class)


def require_permission(
    actor: AuthenticatedActor | None,
    *,
    permission: HostedPermission,
    scope: HostedAccessScope,
    target: AuthorizationTarget,
) -> AuthorizationDecision:
    authenticated_actor = _require_active_actor(actor)
    if not authenticated_actor.has_permission(permission):
        raise HostedRoleDeniedError(
            f"Hosted tester role does not allow {permission!r}."
        )
    if not authenticated_actor.has_scope(scope):
        raise HostedScopeDeniedError(
            "Hosted tester actor is not assigned to the requested project or corpus scope."
        )
    return AuthorizationDecision(
        actor=authenticated_actor.audit_context(),
        permission=permission,
        scope=scope,
        target=target,
        authorized_at=datetime.now(UTC).isoformat(),
    )


def list_authorized_source_derived_records(
    connection: Connection,
    actor: AuthenticatedActor | None,
    *,
    scope: HostedAccessScope,
    entity_type: SourceDerivedEntityType | None = None,
    import_batch_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[SourceDerivedRecordRead, ...]:
    scoped_import_batch_id = _scoped_import_batch_id(scope, import_batch_id)
    require_permission(
        actor,
        permission=SOURCE_DERIVED_READ_PERMISSION,
        scope=scope,
        target=AuthorizationTarget(
            "source_derived_record_list",
            scoped_import_batch_id,
        ),
    )
    return list_source_derived_records(
        connection,
        entity_type=entity_type,
        import_batch_id=scoped_import_batch_id,
        limit=limit,
        offset=offset,
    )


def get_authorized_source_derived_record_by_key(
    connection: Connection,
    actor: AuthenticatedActor | None,
    *,
    scope: HostedAccessScope,
    source_record_key: str,
) -> SourceDerivedRecordRead | None:
    require_permission(
        actor,
        permission=SOURCE_DERIVED_READ_PERMISSION,
        scope=scope,
        target=AuthorizationTarget("source_derived_record", source_record_key),
    )
    record = get_source_derived_record_by_key(connection, source_record_key)
    _require_record_in_scope(record, scope)
    return record


def get_authorized_source_derived_record_by_identity(
    connection: Connection,
    actor: AuthenticatedActor | None,
    *,
    scope: HostedAccessScope,
    entity_type: SourceDerivedEntityType,
    stable_source_id: str,
) -> SourceDerivedRecordRead | None:
    require_permission(
        actor,
        permission=SOURCE_DERIVED_READ_PERMISSION,
        scope=scope,
        target=AuthorizationTarget(
            "source_derived_record",
            f"{entity_type}:{stable_source_id}",
        ),
    )
    record = get_source_derived_record_by_identity(
        connection,
        entity_type=entity_type,
        stable_source_id=stable_source_id,
    )
    _require_record_in_scope(record, scope)
    return record


def _require_active_actor(actor: AuthenticatedActor | None) -> AuthenticatedActor:
    if actor is None:
        raise HostedAuthenticationRequiredError(
            "Hosted tester request requires an authenticated actor."
        )
    if actor.account_status != "active":
        raise HostedAccountDisabledError(
            "Hosted tester actor account is disabled or revoked."
        )
    return actor


def _scoped_import_batch_id(
    scope: HostedAccessScope,
    import_batch_id: str | None,
) -> str:
    if import_batch_id is not None and import_batch_id != scope.scope_id:
        raise HostedScopeDeniedError(
            "Requested source-derived import batch is outside the authorized scope."
        )
    return scope.scope_id


def _require_record_in_scope(
    record: SourceDerivedRecordRead | None,
    scope: HostedAccessScope,
) -> None:
    if record is None:
        return
    if record.import_batch.import_batch_id != scope.scope_id:
        raise HostedScopeDeniedError(
            "Requested source-derived record is outside the authorized scope."
        )