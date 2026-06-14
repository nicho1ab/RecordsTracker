from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlparse

from ccld_complaints.hosted_app.auth import (
    AUTH_PROVIDER_CLASS_ENV,
    AUTH_REQUIRED_CLAIMS,
    MANAGED_OIDC_OAUTH2_PROVIDER_CLASS,
    ROLE_PERMISSIONS,
    USER_ROLE_ADMIN_PERMISSION,
    AuthenticatedActor,
    AuthorizationDecision,
    AuthorizationTarget,
    AuthProviderClass,
    HostedAccessScope,
    HostedAccountDisabledError,
    HostedAuthenticationRequiredError,
    HostedRoleDeniedError,
    HostedScopeDeniedError,
    HostedTesterRole,
    require_permission,
    validate_auth_provider_class,
)

AUTH_PROVIDER_INTEGRATION_PLAN_API_PATH = "/api/auth/provider-integration-plan"
AUTH_PROVIDER_INTEGRATION_PLAN_OPERATION = "auth_provider_integration_plan"

REQUIRED_READINESS_FIELDS = (
    "issuer_metadata_discovery_planned",
    "pkce_flow_planned",
    "redirect_uri_placeholders_planned",
    "claim_mapping_reviewed",
    "role_scope_mapping_reviewed",
    "audit_attribution_reviewed",
    "access_lifecycle_reviewed",
)

SECRET_INPUT_MARKERS = (
    "access_token",
    "auth_code",
    "authorization_code",
    "bearer",
    "callback_url",
    "client_secret",
    "connection string",
    "connection_string",
    "cookie",
    "hosted_url",
    "id_token",
    "password",
    "private_header",
    "private header",
    "private_key",
    "raw_provider_claim",
    "refresh_token",
    "secret",
    "session",
    "token",
)


@dataclass(frozen=True)
class AuthProviderIntegrationPlanContext:
    actor: AuthenticatedActor | None
    scope: HostedAccessScope


@dataclass(frozen=True)
class AuthProviderReadinessInputs:
    provider_class: AuthProviderClass
    readiness: Mapping[str, bool]


@dataclass(frozen=True)
class AuthProviderIntegrationPlanStep:
    sequence: int
    step_id: str
    category: str
    summary: str
    inputs: Mapping[str, Any]


@dataclass(frozen=True)
class AuthProviderIntegrationPlan:
    operation: str
    scope: HostedAccessScope
    authorized: AuthorizationDecision
    readiness_inputs: AuthProviderReadinessInputs
    auth_boundary_summary: Mapping[str, Any]
    plan_steps: tuple[AuthProviderIntegrationPlanStep, ...]
    data_mutations_performed: bool = False
    persistence_performed: bool = False
    external_network_calls_performed: bool = False


def route_auth_provider_integration_plan_response(
    path: str,
    context: AuthProviderIntegrationPlanContext | None,
) -> tuple[int, str, bytes]:
    parsed_url = urlparse(path)
    query_values = parse_qs(parsed_url.query, keep_blank_values=True)
    try:
        if context is None:
            return _json_error(
                503,
                "auth_provider_integration_plan_context_required",
                "Local/test auth provider integration plan context is not configured.",
            )
        if parsed_url.path != AUTH_PROVIDER_INTEGRATION_PLAN_API_PATH:
            return _json_error(
                404,
                "auth_provider_integration_plan_route_not_found",
                "Auth provider integration plan route not found.",
            )
        readiness_inputs = _readiness_inputs(query_values)
        plan = plan_auth_provider_integration(
            context.actor,
            scope=context.scope,
            readiness_inputs=readiness_inputs,
        )
        return _json_response(200, _plan_payload(plan))
    except HostedAuthenticationRequiredError as error:
        return _json_error(401, "authentication_required", str(error))
    except HostedAccountDisabledError as error:
        return _json_error(403, "account_disabled_or_revoked", str(error))
    except HostedRoleDeniedError as error:
        return _json_error(403, "role_denied", str(error))
    except HostedScopeDeniedError as error:
        return _json_error(403, "scope_denied", str(error))
    except ValueError as error:
        return _json_error(400, "invalid_request", str(error))


def plan_auth_provider_integration(
    actor: AuthenticatedActor | None,
    *,
    scope: HostedAccessScope,
    readiness_inputs: AuthProviderReadinessInputs,
) -> AuthProviderIntegrationPlan:
    authorized = require_permission(
        actor,
        permission=USER_ROLE_ADMIN_PERMISSION,
        scope=scope,
        target=AuthorizationTarget("auth_access", scope.scope_id),
    )
    auth_boundary_summary = _auth_boundary_summary()
    return AuthProviderIntegrationPlan(
        operation=AUTH_PROVIDER_INTEGRATION_PLAN_OPERATION,
        scope=scope,
        authorized=authorized,
        readiness_inputs=readiness_inputs,
        auth_boundary_summary=auth_boundary_summary,
        plan_steps=_plan_steps(readiness_inputs, auth_boundary_summary),
    )


def _readiness_inputs(
    query_values: Mapping[str, list[str]],
) -> AuthProviderReadinessInputs:
    _reject_secret_like_query_values(query_values)
    provider_class = validate_auth_provider_class(
        _required_query_value(query_values, "provider_class")
    )
    readiness = {
        field_name: _required_bool_query_value(query_values, field_name)
        for field_name in REQUIRED_READINESS_FIELDS
    }
    return AuthProviderReadinessInputs(
        provider_class=provider_class,
        readiness=readiness,
    )


def _auth_boundary_summary() -> dict[str, Any]:
    role_order: tuple[HostedTesterRole, ...] = (
        "admin",
        "tester_reviewer",
        "read_only_tester",
        "developer_operator",
        "system",
    )
    return {
        "provider_class_env": AUTH_PROVIDER_CLASS_ENV,
        "accepted_provider_class": MANAGED_OIDC_OAUTH2_PROVIDER_CLASS,
        "required_claims": list(AUTH_REQUIRED_CLAIMS),
        "actor_categories": ["admin", "tester", "operator", "system"],
        "account_statuses": ["active", "disabled", "revoked"],
        "scope_types": ["project", "corpus", "seeded_corpus", "test_project"],
        "roles": [
            {
                "role": role,
                "permissions": sorted(ROLE_PERMISSIONS[role]),
            }
            for role in role_order
        ],
        "planning_permission": USER_ROLE_ADMIN_PERMISSION,
    }


def _plan_steps(
    readiness_inputs: AuthProviderReadinessInputs,
    auth_boundary_summary: Mapping[str, Any],
) -> tuple[AuthProviderIntegrationPlanStep, ...]:
    readiness = dict(readiness_inputs.readiness)
    return (
        AuthProviderIntegrationPlanStep(
            sequence=1,
            step_id="accepted_provider_class",
            category="accepted provider class",
            summary="Use the managed OpenID Connect/OAuth 2.0 provider class accepted by ADR-0014.",
            inputs={
                "provider_class": readiness_inputs.provider_class,
                "provider_class_env": AUTH_PROVIDER_CLASS_ENV,
            },
        ),
        AuthProviderIntegrationPlanStep(
            sequence=2,
            step_id="required_future_provider_registration_items",
            category="required future provider registration items",
            summary=(
                "List provider setup items for a later branch without registering "
                "an app or storing configuration."
            ),
            inputs={
                "future_items": [
                    "provider tenant or issuer selection outside the repository",
                    "application registration outside the repository",
                    "PKCE-capable authorization code flow configuration",
                    "provider-managed account disablement or revocation support",
                    "externalized client credentials and environment configuration",
                ],
            },
        ),
        AuthProviderIntegrationPlanStep(
            sequence=3,
            step_id="non_secret_configuration_readiness",
            category="non-secret configuration readiness",
            summary=(
                "Summarize only boolean readiness inputs; do not accept provider "
                "URLs, tenant IDs, credentials, or tokens."
            ),
            inputs={
                "readiness": readiness,
                "all_readiness_inputs_true": all(readiness.values()),
            },
        ),
        AuthProviderIntegrationPlanStep(
            sequence=4,
            step_id="callback_redirect_uri_placeholders",
            category="callback/redirect URI planning placeholders without real hosted URLs",
            summary=(
                "Reserve placeholder planning for future callback and redirect URI "
                "decisions without creating hosted URLs."
            ),
            inputs={
                "redirect_uri_placeholders_planned": readiness[
                    "redirect_uri_placeholders_planned"
                ],
                "real_hosted_urls_deferred": True,
            },
        ),
        AuthProviderIntegrationPlanStep(
            sequence=5,
            step_id="claim_to_actor_mapping_plan",
            category="claim-to-actor mapping plan",
            summary=(
                "Map future provider claims into the existing local/test actor "
                "and audit-context model."
            ),
            inputs={
                "required_claims": list(AUTH_REQUIRED_CLAIMS),
                "actor_fields": [
                    "provider_subject",
                    "provider_issuer",
                    "display_name",
                    "email_when_approved",
                    "actor_category",
                    "account_status",
                ],
                "claim_mapping_reviewed": readiness["claim_mapping_reviewed"],
            },
        ),
        AuthProviderIntegrationPlanStep(
            sequence=6,
            step_id="role_scope_mapping_plan",
            category="role/scope mapping plan",
            summary=(
                "Plan future role and scope assignment mapping while preserving "
                "existing permission names."
            ),
            inputs={
                "roles": auth_boundary_summary["roles"],
                "scope_types": auth_boundary_summary["scope_types"],
                "role_scope_mapping_reviewed": readiness[
                    "role_scope_mapping_reviewed"
                ],
            },
        ),
        AuthProviderIntegrationPlanStep(
            sequence=7,
            step_id="audit_attribution_expectations",
            category="audit attribution expectations",
            summary=(
                "Capture future actor identity context for audited reviewer-created "
                "and operational actions without storing credentials."
            ),
            inputs={
                "actor_categories": auth_boundary_summary["actor_categories"],
                "account_statuses": auth_boundary_summary["account_statuses"],
                "audit_attribution_reviewed": readiness[
                    "audit_attribution_reviewed"
                ],
            },
        ),
        AuthProviderIntegrationPlanStep(
            sequence=8,
            step_id="local_test_boundary_notes",
            category="local/test boundary notes",
            summary=(
                "Keep this branch limited to explicit local/test planning context "
                "and no production authentication behavior."
            ),
            inputs={
                "explicit_local_test_context_only": True,
                "no_persistence": True,
                "external_network_calls_performed": False,
            },
        ),
        AuthProviderIntegrationPlanStep(
            sequence=9,
            step_id="deferred_production_implementation_items",
            category="deferred production implementation items",
            summary=(
                "List production auth implementation work that remains deferred "
                "after this planning seam."
            ),
            inputs={
                "deferred_items": [
                    "real login flow",
                    "authentication middleware",
                    "callback handling",
                    "authorization-code handling",
                    "token exchange or validation",
                    "refresh tokens",
                    "sessions or cookies",
                    "provider registration",
                    "client secrets",
                    "hosted URLs",
                    "user tables or role persistence",
                    "schema changes or migrations",
                    "external provider discovery calls",
                ],
            },
        ),
    )


def _reject_secret_like_query_values(
    query_values: Mapping[str, list[str]],
) -> None:
    for key, values in query_values.items():
        _reject_secret_like_text(key, "readiness input")
        for value in values:
            _reject_secret_like_text(value, "readiness input")


def _reject_secret_like_text(value: str, field_name: str) -> None:
    normalized = value.casefold()
    if "http://" in normalized or "https://" in normalized:
        raise ValueError(f"Auth provider {field_name} must not include real URLs.")
    if any(marker in normalized for marker in SECRET_INPUT_MARKERS):
        raise ValueError(
            f"Auth provider {field_name} must not include secret-like data."
        )


def _required_bool_query_value(
    query_values: Mapping[str, list[str]],
    key: str,
) -> bool:
    raw_value = _required_query_value(query_values, key)
    if raw_value == "true":
        return True
    if raw_value == "false":
        return False
    raise ValueError(f"{key} must be 'true' or 'false'.")


def _required_query_value(
    query_values: Mapping[str, list[str]],
    key: str,
) -> str:
    values = query_values.get(key, [])
    if not values or not values[0].strip():
        raise ValueError(f"{key} is required.")
    return values[0].strip()


def _plan_payload(plan: AuthProviderIntegrationPlan) -> dict[str, Any]:
    return {
        "provider_integration_plan": True,
        "operation": plan.operation,
        "scope": {
            "scope_type": plan.scope.scope_type,
            "scope_id": plan.scope.scope_id,
        },
        "authorization": _authorization_payload(plan.authorized),
        "accepted_provider_class": {
            "provider_class": plan.readiness_inputs.provider_class,
            "provider_class_env": AUTH_PROVIDER_CLASS_ENV,
            "required_claims": list(AUTH_REQUIRED_CLAIMS),
        },
        "readiness_inputs": dict(plan.readiness_inputs.readiness),
        "auth_boundary_summary": dict(plan.auth_boundary_summary),
        "readiness_plan": [_step_payload(step) for step in plan.plan_steps],
        "safety": {
            "data_mutations_performed": plan.data_mutations_performed,
            "persistence_performed": plan.persistence_performed,
            "external_network_calls_performed": plan.external_network_calls_performed,
            "real_login_implemented": False,
            "token_handling_implemented": False,
            "sessions_or_cookies_implemented": False,
            "provider_registration_performed": False,
            "hosted_urls_created": False,
            "secrets_exposed": False,
        },
    }


def _authorization_payload(decision: AuthorizationDecision) -> dict[str, Any]:
    return {
        "permission": decision.permission,
        "target": {
            "target_type": decision.target.target_type,
            "target_id": decision.target.target_id,
        },
        "authorized_at": decision.authorized_at,
        "actor": {
            "actor_category": decision.actor.actor_category,
            "account_status": decision.actor.account_status,
            "roles": list(decision.actor.roles),
            "scopes": [
                {"scope_type": scope.scope_type, "scope_id": scope.scope_id}
                for scope in decision.actor.scopes
            ],
        },
    }


def _step_payload(step: AuthProviderIntegrationPlanStep) -> dict[str, Any]:
    return {
        "sequence": step.sequence,
        "step_id": step.step_id,
        "category": step.category,
        "summary": step.summary,
        "inputs": dict(step.inputs),
    }


def _json_response(status: int, payload: Mapping[str, Any]) -> tuple[int, str, bytes]:
    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    return status, "application/json; charset=utf-8", body


def _json_error(status: int, code: str, message: str) -> tuple[int, str, bytes]:
    return _json_response(status, {"error": {"code": code, "message": message}})