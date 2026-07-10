from __future__ import annotations

import base64
import hashlib
import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, cast
from urllib.parse import urlparse
from urllib.request import urlopen

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from sqlalchemy.engine import Connection

from ccld_complaints.hosted_app.seeded_import import SourceDerivedEntityType
from ccld_complaints.hosted_app.source_derived_reads import (
    CcldSourceDerivedRequestLookup,
    SourceDerivedRecordRead,
    find_ccld_source_derived_records_for_request,
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
CLOUDFLARE_ACCESS_PROVIDER_CLASS = "cloudflare-access"
CLOUDFLARE_ACCESS_TEAM_DOMAIN_ENV = "CCLD_CLOUDFLARE_ACCESS_TEAM_DOMAIN"
CLOUDFLARE_ACCESS_AUD_ENV = "CCLD_CLOUDFLARE_ACCESS_AUD"
CLOUDFLARE_ACCESS_ALLOWED_EMAIL_DOMAINS_ENV = (
    "CCLD_CLOUDFLARE_ACCESS_ALLOWED_EMAIL_DOMAINS"
)
CLOUDFLARE_ACCESS_ALLOWED_EMAILS_ENV = "CCLD_CLOUDFLARE_ACCESS_ALLOWED_EMAILS"
CLOUDFLARE_ACCESS_JWKS_CACHE_SECONDS_ENV = (
    "CCLD_CLOUDFLARE_ACCESS_JWKS_CACHE_SECONDS"
)
CLOUDFLARE_ACCESS_ASSERTION_HEADER = "Cf-Access-Jwt-Assertion"
CLOUDFLARE_ACCESS_DEFAULT_JWKS_CACHE_SECONDS = 300
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

AuthProviderClass = Literal["managed-oidc-oauth2", "cloudflare-access"]
HostedAuthMode = Literal["production", "local-dev"]
HostedAccountStatus = Literal["active", "disabled", "revoked"]
HostedActorCategory = Literal["admin", "tester", "operator", "system"]
HostedAccessScopeType = Literal["project", "corpus", "seeded_corpus", "test_project"]
HostedTesterRole = Literal[
    "admin",
    "tester_reviewer",
    "read_only_tester",
    "developer_operator",
    "feedback_tester",
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
    "feedback_tester": frozenset({"feedback_submit"}),
    "system": frozenset({"source_derived_read", "import_reload"}),
}


class HostedAuthConfigError(ValueError):
    pass


class CloudflareAccessAuthError(HostedAuthConfigError):
    def __init__(self, message: str, *, status: int = 403) -> None:
        super().__init__(message)
        self.status = status


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
class HostedCloudflareAccessRuntimeConfig:
    team_domain: str | None
    aud: str | None
    allowed_email_domains: tuple[str, ...]
    allowed_emails: tuple[str, ...]
    jwks_cache_seconds: int = CLOUDFLARE_ACCESS_DEFAULT_JWKS_CACHE_SECONDS

    @property
    def configured(self) -> bool:
        return bool(
            self.team_domain
            and self.aud
            and (self.allowed_email_domains or self.allowed_emails)
        )

    @property
    def issuer(self) -> str | None:
        if self.team_domain is None:
            return None
        return _cloudflare_access_base_url(self.team_domain)

    @property
    def jwks_url(self) -> str | None:
        issuer = self.issuer
        if issuer is None:
            return None
        return f"{issuer}/cdn-cgi/access/certs"

    @property
    def safe_summary(self) -> Mapping[str, object]:
        return {
            "team_domain_configured": self.team_domain is not None,
            "aud_configured": self.aud is not None,
            "allowed_email_domain_count": len(self.allowed_email_domains),
            "allowed_exact_email_count": len(self.allowed_emails),
            "jwks_cache_seconds": self.jwks_cache_seconds,
            "assertion_header": CLOUDFLARE_ACCESS_ASSERTION_HEADER,
        }


@dataclass(frozen=True)
class HostedAuthRuntimeConfig:
    mode: HostedAuthMode
    provider_class: AuthProviderClass | None
    oidc: HostedOidcRuntimeConfig
    cloudflare_access: HostedCloudflareAccessRuntimeConfig
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
            "cloudflare_access": self.cloudflare_access.safe_summary,
            "local_dev_auth_enabled": self.local_dev_auth_enabled,
            "local_dev_actor_allowed": self.local_dev_actor_allowed,
            "custom_password_storage": False,
            "real_oidc_flow_implemented": False,
            "sessions_or_cookies_implemented": False,
            "cloudflare_access_jwt_bridge_implemented": True,
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
        cloudflare_access=_cloudflare_access_runtime_config(active_environ),
        local_dev_auth_enabled=local_dev_auth_enabled,
    )


def validate_auth_provider_class(provider_class: str) -> AuthProviderClass:
    normalized_provider_class = provider_class.strip().lower()
    if normalized_provider_class not in {
        MANAGED_OIDC_OAUTH2_PROVIDER_CLASS,
        CLOUDFLARE_ACCESS_PROVIDER_CLASS,
    }:
        raise HostedAuthConfigError(
            f"{AUTH_PROVIDER_CLASS_ENV} must be "
            f"{MANAGED_OIDC_OAUTH2_PROVIDER_CLASS!r} or "
            f"{CLOUDFLARE_ACCESS_PROVIDER_CLASS!r}."
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


JwksFetcher = Callable[[str], Mapping[str, Any]]
_CLOUDFLARE_JWKS_CACHE: dict[str, tuple[float, Mapping[str, Any]]] = {}


def authenticate_cloudflare_access_request(
    headers: Mapping[str, str],
    config: HostedCloudflareAccessRuntimeConfig,
    *,
    scope: HostedAccessScope,
    now: datetime | None = None,
    jwks_fetcher: JwksFetcher | None = None,
) -> AuthenticatedActor:
    if not config.configured:
        raise CloudflareAccessAuthError(
            "Cloudflare Access authentication is not fully configured. "
            "Set the team domain, audience tag, and tester email allowlist.",
            status=403,
        )
    token = _cloudflare_access_assertion_from_headers(headers)
    if token is None:
        raise CloudflareAccessAuthError(
            "Cloudflare Access assertion is required. Reach RecordsTracker through "
            "the Cloudflare Access protected hostname.",
            status=401,
        )
    return authenticate_cloudflare_access_token(
        token,
        config,
        scope=scope,
        now=now,
        jwks_fetcher=jwks_fetcher,
    )


def authenticate_cloudflare_access_token(
    token: str,
    config: HostedCloudflareAccessRuntimeConfig,
    *,
    scope: HostedAccessScope,
    now: datetime | None = None,
    jwks_fetcher: JwksFetcher | None = None,
) -> AuthenticatedActor:
    header, claims, signing_input, signature = _decode_unsigned_jwt(token)
    if header.get("alg") != "RS256":
        raise CloudflareAccessAuthError("Cloudflare Access assertion was not accepted.")
    kid = header.get("kid")
    if not isinstance(kid, str) or not kid.strip():
        raise CloudflareAccessAuthError("Cloudflare Access assertion was not accepted.")
    jwks_url = config.jwks_url
    if jwks_url is None:
        raise CloudflareAccessAuthError(
            "Cloudflare Access authentication is missing the team domain."
        )
    jwks = _fetch_cloudflare_access_jwks(
        jwks_url,
        cache_seconds=config.jwks_cache_seconds,
        jwks_fetcher=jwks_fetcher,
    )
    public_key = _public_key_for_kid(jwks, kid)
    try:
        public_key.verify(signature, signing_input, padding.PKCS1v15(), hashes.SHA256())
    except InvalidSignature as error:
        raise CloudflareAccessAuthError(
            "Cloudflare Access assertion was not accepted."
        ) from error

    issuer = _required_string_claim(claims, "iss")
    expected_issuer = config.issuer
    if expected_issuer is None or issuer != expected_issuer:
        raise CloudflareAccessAuthError(
            "Cloudflare Access assertion issuer was not accepted."
        )
    _require_audience(claims, config.aud)
    _require_time_claims(claims, now=now or datetime.now(UTC))
    email = _required_string_claim(claims, "email").strip().casefold()
    if not _cloudflare_email_allowed(email, config):
        raise CloudflareAccessAuthError(
            "Cloudflare Access email is not allowed for this RecordsTracker pilot."
        )
    actor_hash = hashlib.sha256(email.encode("utf-8")).hexdigest()[:16]
    return AuthenticatedActor(
        provider_subject=f"cloudflare-access-email-sha256:{actor_hash}",
        provider_issuer=issuer,
        display_name=f"Cloudflare Access tester {actor_hash}",
        email=email,
        actor_category="tester",
        account_status="active",
        roles=("feedback_tester",),
        scopes=(scope,),
    )


def _cloudflare_access_runtime_config(
    environ: Mapping[str, str],
) -> HostedCloudflareAccessRuntimeConfig:
    team_domain = _optional_config_value(environ, CLOUDFLARE_ACCESS_TEAM_DOMAIN_ENV)
    aud = _optional_config_value(environ, CLOUDFLARE_ACCESS_AUD_ENV)
    allowed_email_domains = _normalized_config_list(
        _optional_config_value(environ, CLOUDFLARE_ACCESS_ALLOWED_EMAIL_DOMAINS_ENV)
    )
    allowed_emails = _normalized_config_list(
        _optional_config_value(environ, CLOUDFLARE_ACCESS_ALLOWED_EMAILS_ENV)
    )
    jwks_cache_seconds = _jwks_cache_seconds(
        _optional_config_value(environ, CLOUDFLARE_ACCESS_JWKS_CACHE_SECONDS_ENV)
    )
    for env_name, value in (
        (CLOUDFLARE_ACCESS_AUD_ENV, aud),
        (CLOUDFLARE_ACCESS_ALLOWED_EMAIL_DOMAINS_ENV, ",".join(allowed_email_domains)),
        (CLOUDFLARE_ACCESS_ALLOWED_EMAILS_ENV, ",".join(allowed_emails)),
    ):
        if value:
            _reject_secret_like_config(env_name, value)
    if team_domain is not None:
        _cloudflare_access_base_url(team_domain)
    return HostedCloudflareAccessRuntimeConfig(
        team_domain=team_domain,
        aud=aud,
        allowed_email_domains=allowed_email_domains,
        allowed_emails=allowed_emails,
        jwks_cache_seconds=jwks_cache_seconds,
    )


def _normalized_config_list(raw_value: str | None) -> tuple[str, ...]:
    if raw_value is None:
        return ()
    values: list[str] = []
    for value in raw_value.replace(";", ",").split(","):
        normalized = value.strip().casefold()
        if normalized and normalized not in values:
            values.append(normalized)
    return tuple(values)


def _jwks_cache_seconds(raw_value: str | None) -> int:
    if raw_value is None:
        return CLOUDFLARE_ACCESS_DEFAULT_JWKS_CACHE_SECONDS
    try:
        value = int(raw_value)
    except ValueError as error:
        raise HostedAuthConfigError(
            f"{CLOUDFLARE_ACCESS_JWKS_CACHE_SECONDS_ENV} must be an integer."
        ) from error
    if value < 0 or value > 3600:
        raise HostedAuthConfigError(
            f"{CLOUDFLARE_ACCESS_JWKS_CACHE_SECONDS_ENV} must be between 0 and 3600."
        )
    return value


def _cloudflare_access_base_url(team_domain: str) -> str:
    raw_value = team_domain.strip().rstrip("/")
    candidate = raw_value if "://" in raw_value else f"https://{raw_value}"
    parsed = urlparse(candidate)
    if parsed.scheme != "https" or not parsed.netloc or parsed.path not in {"", "/"}:
        raise HostedAuthConfigError(
            f"{CLOUDFLARE_ACCESS_TEAM_DOMAIN_ENV} must be an HTTPS team domain."
        )
    if parsed.query or parsed.fragment:
        raise HostedAuthConfigError(
            f"{CLOUDFLARE_ACCESS_TEAM_DOMAIN_ENV} must not include query or fragment."
        )
    return f"https://{parsed.netloc}"


def _cloudflare_access_assertion_from_headers(headers: Mapping[str, str]) -> str | None:
    for key, value in headers.items():
        if key.casefold() == CLOUDFLARE_ACCESS_ASSERTION_HEADER.casefold():
            token = value.strip()
            return token or None
    return None


def _decode_unsigned_jwt(
    token: str,
) -> tuple[Mapping[str, Any], Mapping[str, Any], bytes, bytes]:
    parts = token.split(".")
    if len(parts) != 3 or not all(parts):
        raise CloudflareAccessAuthError("Cloudflare Access assertion was not accepted.")
    try:
        header = json.loads(_base64url_decode(parts[0]))
        claims = json.loads(_base64url_decode(parts[1]))
        signature = _base64url_decode(parts[2])
    except (ValueError, json.JSONDecodeError) as error:
        raise CloudflareAccessAuthError(
            "Cloudflare Access assertion was not accepted."
        ) from error
    if not isinstance(header, Mapping) or not isinstance(claims, Mapping):
        raise CloudflareAccessAuthError("Cloudflare Access assertion was not accepted.")
    return header, claims, f"{parts[0]}.{parts[1]}".encode("ascii"), signature


def _base64url_decode(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _fetch_cloudflare_access_jwks(
    jwks_url: str,
    *,
    cache_seconds: int,
    jwks_fetcher: JwksFetcher | None,
) -> Mapping[str, Any]:
    now_timestamp = datetime.now(UTC).timestamp()
    cached = _CLOUDFLARE_JWKS_CACHE.get(jwks_url)
    if jwks_fetcher is None and cached is not None:
        cached_at, jwks = cached
        if cache_seconds > 0 and now_timestamp - cached_at <= cache_seconds:
            return jwks
    if jwks_fetcher is None:
        with urlopen(jwks_url, timeout=10) as response:
            loaded = json.loads(response.read().decode("utf-8"))
    else:
        loaded = jwks_fetcher(jwks_url)
    if not isinstance(loaded, Mapping):
        raise CloudflareAccessAuthError("Cloudflare Access JWKS was not accepted.")
    if jwks_fetcher is None and cache_seconds > 0:
        _CLOUDFLARE_JWKS_CACHE[jwks_url] = (now_timestamp, loaded)
    return loaded


def _public_key_for_kid(jwks: Mapping[str, Any], kid: str) -> rsa.RSAPublicKey:
    keys = jwks.get("keys")
    if not isinstance(keys, list):
        raise CloudflareAccessAuthError("Cloudflare Access JWKS was not accepted.")
    for key in keys:
        if not isinstance(key, Mapping) or key.get("kid") != kid:
            continue
        if key.get("kty") != "RSA":
            continue
        modulus = key.get("n")
        exponent = key.get("e")
        if not isinstance(modulus, str) or not isinstance(exponent, str):
            continue
        public_numbers = rsa.RSAPublicNumbers(
            _unsigned_int_from_base64url(exponent),
            _unsigned_int_from_base64url(modulus),
        )
        return public_numbers.public_key()
    raise CloudflareAccessAuthError("Cloudflare Access assertion was not accepted.")


def _unsigned_int_from_base64url(value: str) -> int:
    return int.from_bytes(_base64url_decode(value), byteorder="big", signed=False)


def _required_string_claim(claims: Mapping[str, Any], claim_name: str) -> str:
    value = claims.get(claim_name)
    if not isinstance(value, str) or not value.strip():
        raise CloudflareAccessAuthError(
            "Cloudflare Access assertion is missing a required claim."
        )
    return value.strip()


def _require_audience(claims: Mapping[str, Any], expected_audience: str | None) -> None:
    if expected_audience is None:
        raise CloudflareAccessAuthError(
            "Cloudflare Access authentication is missing the audience tag."
        )
    audience = claims.get("aud")
    accepted = False
    if isinstance(audience, str):
        accepted = audience == expected_audience
    elif isinstance(audience, list):
        accepted = any(value == expected_audience for value in audience)
    if not accepted:
        raise CloudflareAccessAuthError(
            "Cloudflare Access assertion audience was not accepted."
        )


def _require_time_claims(claims: Mapping[str, Any], *, now: datetime) -> None:
    current_timestamp = int(now.timestamp())
    exp = _required_int_claim(claims, "exp")
    if exp <= current_timestamp:
        raise CloudflareAccessAuthError("Cloudflare Access assertion has expired.")
    nbf = claims.get("nbf")
    if nbf is not None:
        if not isinstance(nbf, int):
            raise CloudflareAccessAuthError(
                "Cloudflare Access assertion is missing a required claim."
            )
        if nbf > current_timestamp:
            raise CloudflareAccessAuthError(
                "Cloudflare Access assertion is not valid yet."
            )


def _required_int_claim(claims: Mapping[str, Any], claim_name: str) -> int:
    value = claims.get(claim_name)
    if not isinstance(value, int):
        raise CloudflareAccessAuthError(
            "Cloudflare Access assertion is missing a required claim."
        )
    return value


def _cloudflare_email_allowed(
    email: str,
    config: HostedCloudflareAccessRuntimeConfig,
) -> bool:
    if email in config.allowed_emails:
        return True
    _local_part, separator, domain = email.rpartition("@")
    if not separator or not domain:
        return False
    return domain in config.allowed_email_domains


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


def find_authorized_ccld_source_derived_records_for_request(
    connection: Connection,
    actor: AuthenticatedActor | None,
    *,
    scope: HostedAccessScope,
    facility_number: str,
    start_date: str | None = None,
    end_date: str | None = None,
    import_batch_id: str | None = None,
) -> CcldSourceDerivedRequestLookup:
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
    return find_ccld_source_derived_records_for_request(
        connection,
        facility_number=facility_number,
        start_date=start_date,
        end_date=end_date,
        import_batch_id=scoped_import_batch_id,
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
