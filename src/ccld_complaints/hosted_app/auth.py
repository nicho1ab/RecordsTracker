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
AUTH_MODE_ENV = "CCLD_HOSTED_TESTER_AUTH_MODE"
LOCAL_DEV_AUTH_ENV = "CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH"
OIDC_ISSUER_ENV = "CCLD_HOSTED_TESTER_OIDC_ISSUER"
OIDC_CLIENT_ID_ENV = "CCLD_HOSTED_TESTER_OIDC_CLIENT_ID"
OIDC_CALLBACK_PATH_ENV = "CCLD_HOSTED_TESTER_OIDC_CALLBACK_PATH"
OIDC_SCOPES_ENV = "CCLD_HOSTED_TESTER_OIDC_SCOPES"
MANAGED_OIDC_OAUTH2_PROVIDER_CLASS = "managed-oidc-oauth2"
PRODUCTION_AUTH_MODE = "production"
LOCAL_DEV_AUTH_MODE = "local-dev"
LOCAL_DEV_AUTH_ENABLED_VALUE = "enabled"
AUTH_REQUIRED_CLAIMS = (
    "sub",
    "iss",
    "roles",
    "scopes",
    "account_status",
)

AuthProviderClass = Literal["managed-oidc-oauth2"]
HostedAuthMode = Literal["production", "local-dev"]
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
    "reviewer_state_read",
    "reviewer_state_write",
    "correction_propose",
    "correction_decide",
    "export_prepare",
    "export_finalize",
    "feedback_submit",
    "retrieval_job_trigger",
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
REVIEWER_STATE_READ_PERMISSION: HostedPermission = "reviewer_state_read"
REVIEWER_STATE_WRITE_PERMISSION: HostedPermission = "reviewer_state_write"
FEEDBACK_SUBMIT_PERMISSION: HostedPermission = "feedback_submit"
RETRIEVAL_JOB_TRIGGER_PERMISSION: HostedPermission = "retrieval_job_trigger"
IMPORT_RELOAD_PERMISSION: HostedPermission = "import_reload"
USER_ROLE_ADMIN_PERMISSION: HostedPermission = "user_role_admin"
AUDIT_READ_PERMISSION: HostedPermission = "audit_read"

ROLE_PERMISSIONS: Mapping[HostedTesterRole, frozenset[HostedPermission]] = {
    "admin": frozenset(
        {
            "source_derived_read",
            "reviewer_state_read",
            "reviewer_state_write",
            "correction_propose",
            "correction_decide",
            "export_prepare",
            "export_finalize",
            "feedback_submit",
            "retrieval_job_trigger",
            "import_reload",
            "reset_destructive",
            "user_role_admin",
            "audit_read",
        }
    ),
    "tester_reviewer": frozenset(
        {
            "source_derived_read",
            "reviewer_state_read",
            "reviewer_state_write",
            "correction_propose",
            "export_prepare",
            "feedback_submit",
            "retrieval_job_trigger",
        }
    ),
    "read_only_tester": frozenset({"source_derived_read", "reviewer_state_read"}),
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
class HostedOidcRuntimeConfig:
    issuer: str | None
    client_id: str | None
    callback_path: str | None
    scopes: tuple[str, ...]

    @property
    def configured(self) -> bool:
        return bool(self.issuer and self.client_id and self.callback_path)

    @property
    def safe_summary(self) -> Mapping[str, object]:
        return {
            "issuer_configured": self.issuer is not None,
            "client_id_configured": self.client_id is not None,
            "callback_path": self.callback_path or "<unset>",
            "scopes": list(self.scopes),
        }


@dataclass(frozen=True)
class HostedAuthRuntimeConfig:
    mode: HostedAuthMode
    provider_class: AuthProviderClass | None
    oidc: HostedOidcRuntimeConfig
    local_dev_auth_enabled: bool

    @property
    def production_mode(self) -> bool:
        return self.mode == PRODUCTION_AUTH_MODE

    @property
    def local_dev_actor_allowed(self) -> bool:
        return self.mode == LOCAL_DEV_AUTH_MODE and self.local_dev_auth_enabled

    @property
    def safe_summary(self) -> Mapping[str, object]:
        return {
            "mode": self.mode,
            "provider_class": self.provider_class or "<unset>",
            "oidc": self.oidc.safe_summary,
            "local_dev_auth_enabled": self.local_dev_auth_enabled,
            "local_dev_actor_allowed": self.local_dev_actor_allowed,
            "custom_password_storage": False,
            "real_oidc_flow_implemented": False,
            "sessions_or_cookies_implemented": False,
        }


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


def load_hosted_auth_runtime_config(
    environ: Mapping[str, str] | None = None,
) -> HostedAuthRuntimeConfig:
    active_environ = os.environ if environ is None else environ
    mode = _auth_mode(active_environ.get(AUTH_MODE_ENV, ""))
    provider_config = load_hosted_auth_config(environ=active_environ)
    local_dev_auth_enabled = (
        active_environ.get(LOCAL_DEV_AUTH_ENV, "").strip().lower()
        == LOCAL_DEV_AUTH_ENABLED_VALUE
    )
    if mode == PRODUCTION_AUTH_MODE and local_dev_auth_enabled:
        raise HostedAuthConfigError(
            f"{LOCAL_DEV_AUTH_ENV} must not be enabled when {AUTH_MODE_ENV} is production."
        )
    return HostedAuthRuntimeConfig(
        mode=mode,
        provider_class=provider_config.provider_class,
        oidc=_oidc_runtime_config(active_environ),
        local_dev_auth_enabled=local_dev_auth_enabled,
    )


def validate_auth_provider_class(provider_class: str) -> AuthProviderClass:
    normalized_provider_class = provider_class.strip().lower()
    if normalized_provider_class != MANAGED_OIDC_OAUTH2_PROVIDER_CLASS:
        raise HostedAuthConfigError(
            f"{AUTH_PROVIDER_CLASS_ENV} must be {MANAGED_OIDC_OAUTH2_PROVIDER_CLASS!r}."
        )
    return cast(AuthProviderClass, normalized_provider_class)


def _auth_mode(raw_mode: str) -> HostedAuthMode:
    normalized_mode = raw_mode.strip().lower() or PRODUCTION_AUTH_MODE
    if normalized_mode not in {PRODUCTION_AUTH_MODE, LOCAL_DEV_AUTH_MODE}:
        raise HostedAuthConfigError(
            f"{AUTH_MODE_ENV} must be 'production' or 'local-dev'."
        )
    return cast(HostedAuthMode, normalized_mode)


def _oidc_runtime_config(environ: Mapping[str, str]) -> HostedOidcRuntimeConfig:
    issuer = _optional_config_value(environ, OIDC_ISSUER_ENV)
    client_id = _optional_config_value(environ, OIDC_CLIENT_ID_ENV)
    callback_path = _optional_config_value(environ, OIDC_CALLBACK_PATH_ENV)
    scopes = tuple(
        scope
        for scope in (_optional_config_value(environ, OIDC_SCOPES_ENV) or "").split()
        if scope
    )
    if callback_path is not None and not callback_path.startswith("/"):
        raise HostedAuthConfigError(f"{OIDC_CALLBACK_PATH_ENV} must be a path placeholder.")
    for env_name, value in (
        (OIDC_CLIENT_ID_ENV, client_id),
        (OIDC_CALLBACK_PATH_ENV, callback_path),
        (OIDC_SCOPES_ENV, " ".join(scopes) if scopes else None),
    ):
        if value is not None:
            _reject_secret_like_config(env_name, value)
    return HostedOidcRuntimeConfig(
        issuer=issuer,
        client_id=client_id,
        callback_path=callback_path,
        scopes=scopes,
    )


def _optional_config_value(environ: Mapping[str, str], env_name: str) -> str | None:
    value = environ.get(env_name, "").strip()
    return value or None


def _reject_secret_like_config(env_name: str, value: str) -> None:
    normalized = value.casefold()
    forbidden_markers = (
        "client_secret",
        "cookie",
        "password",
        "private_key",
        "refresh_token",
        "secret",
        "token",
    )
    if any(marker in normalized for marker in forbidden_markers):
        raise HostedAuthConfigError(f"{env_name} must not contain secret-like data.")


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