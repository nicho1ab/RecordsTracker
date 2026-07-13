from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Connection

from ccld_complaints.hosted_app.app import route_response
from ccld_complaints.hosted_app.audit_events import hosted_audit_events
from ccld_complaints.hosted_app.auth import (
    MANAGED_OIDC_OAUTH2_PROVIDER_CLASS,
    AuthenticatedActor,
    HostedAccessScope,
    HostedAccountStatus,
    HostedActorCategory,
    HostedTesterRole,
)
from ccld_complaints.hosted_app.auth_provider_integration_plan import (
    AUTH_PROVIDER_INTEGRATION_PLAN_API_PATH,
    REQUIRED_READINESS_FIELDS,
    AuthProviderIntegrationPlanContext,
    plan_auth_provider_integration,
)
from ccld_complaints.hosted_app.reset_reload_dry_run import (
    hosted_reset_reload_planning_metadata,
)
from ccld_complaints.hosted_app.reviewer_created_state import (
    hosted_reviewer_created_state,
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
DEFAULT_ACTOR = object()


def test_auth_provider_integration_plan_returns_bounded_non_secret_plan() -> None:
    with _seeded_connection() as connection:
        before_counts = _table_counts(connection)
        status, content_type, body = route_response(
            _plan_path(),
            auth_provider_integration_plan_context=_plan_context(),
        )
        after_counts = _table_counts(connection)

    payload = _json_body(body)

    assert status == 200
    assert content_type == "application/json; charset=utf-8"
    assert before_counts == after_counts == {
        "import_batches": 1,
        "source_records": 7,
        "reviewer_created_state": 0,
        "audit_events": 0,
        "reset_reload_planning_metadata": 0,
    }
    assert payload["provider_integration_plan"] is True
    assert payload["operation"] == "auth_provider_integration_plan"
    assert payload["accepted_provider_class"] == {
        "provider_class": "managed-oidc-oauth2",
        "provider_class_env": "CCLD_HOSTED_TESTER_AUTH_PROVIDER_CLASS",
        "required_claims": ["sub", "iss", "roles", "scopes", "account_status"],
    }
    assert payload["authorization"]["permission"] == "user_role_admin"
    assert payload["authorization"]["actor"]["roles"] == ["admin"]
    assert payload["readiness_inputs"] == {
        field_name: True for field_name in REQUIRED_READINESS_FIELDS
    }
    assert [step["sequence"] for step in payload["readiness_plan"]] == list(
        range(1, 10)
    )
    assert [step["category"] for step in payload["readiness_plan"]] == [
        "accepted provider class",
        "required future provider registration items",
        "non-secret configuration readiness",
        "callback/redirect URI planning placeholders without real hosted URLs",
        "claim-to-actor mapping plan",
        "role/scope mapping plan",
        "audit attribution expectations",
        "local/test boundary notes",
        "deferred production implementation items",
    ]
    assert payload["safety"] == {
        "data_mutations_performed": False,
        "persistence_performed": False,
        "external_network_calls_performed": False,
        "real_login_implemented": False,
        "token_handling_implemented": False,
        "sessions_or_cookies_implemented": False,
        "provider_registration_performed": False,
        "hosted_urls_created": False,
        "secrets_exposed": False,
    }
    serialized = body.decode("utf-8").casefold()
    for forbidden_text in (
        "super-secret-value",
        "actual-access-token",
        "actual-refresh-token",
        "actual-authorization-code",
        "actual-cookie-value",
        "actual-private-key",
        "https://",
        "operator@example.invalid",
    ):
        assert forbidden_text not in serialized


def test_auth_provider_integration_plan_rejects_unsupported_provider_class() -> None:
    status, _content_type, body = route_response(
        _plan_path(provider_class="saml-enterprise"),
        auth_provider_integration_plan_context=_plan_context(),
    )

    payload = _json_body(body)

    assert status == 400
    assert payload["error"]["code"] == "invalid_request"
    assert "CCLD_HOSTED_TESTER_AUTH_PROVIDER_CLASS" in payload["error"]["message"]


def test_auth_provider_integration_plan_rejects_missing_readiness_field() -> None:
    query = _readiness_query()
    query.pop("pkce_flow_planned")

    status, _content_type, body = route_response(
        _path_from_query(query),
        auth_provider_integration_plan_context=_plan_context(),
    )

    payload = _json_body(body)

    assert status == 400
    assert payload["error"]["code"] == "invalid_request"
    assert "pkce_flow_planned is required" in payload["error"]["message"]


@pytest.mark.parametrize(
    ("query_key", "query_value"),
    [
        ("client_secret", "example"),
        ("provider_metadata", "https://provider.example.invalid/.well-known"),
        ("authorization_code", "abc123"),
        ("readiness_note", "contains refresh_token value"),
        ("private_key", "not-allowed"),
        ("cookie", "not-allowed"),
    ],
)
def test_auth_provider_integration_plan_rejects_secret_like_inputs(
    query_key: str,
    query_value: str,
) -> None:
    query = _readiness_query()
    query[query_key] = query_value

    status, _content_type, body = route_response(
        _path_from_query(query),
        auth_provider_integration_plan_context=_plan_context(),
    )

    payload = _json_body(body)

    assert status == 400
    assert payload["error"]["code"] == "invalid_request"
    assert "secret-like" in payload["error"]["message"] or "real URLs" in payload[
        "error"
    ]["message"]
    assert query_value.casefold() not in body.decode("utf-8").casefold()


def test_auth_provider_integration_plan_service_ordering_is_deterministic() -> None:
    first = plan_auth_provider_integration(
        _admin_actor(),
        scope=TEST_SCOPE,
        readiness_inputs=_readiness_inputs_model(),
    )
    second = plan_auth_provider_integration(
        _admin_actor(),
        scope=TEST_SCOPE,
        readiness_inputs=_readiness_inputs_model(),
    )

    assert [step.step_id for step in first.plan_steps] == [
        step.step_id for step in second.plan_steps
    ] == [
        "accepted_provider_class",
        "required_future_provider_registration_items",
        "non_secret_configuration_readiness",
        "callback_redirect_uri_placeholders",
        "claim_to_actor_mapping_plan",
        "role_scope_mapping_plan",
        "audit_attribution_expectations",
        "local_test_boundary_notes",
        "deferred_production_implementation_items",
    ]


def test_auth_provider_integration_plan_requires_explicit_context() -> None:
    status, _content_type, body = route_response(_plan_path())

    payload = _json_body(body)

    assert status == 503
    assert payload["error"]["code"] == (
        "auth_provider_integration_plan_context_required"
    )


def test_auth_provider_integration_plan_rejects_unauthenticated_actor() -> None:
    status, _content_type, body = route_response(
        _plan_path(),
        auth_provider_integration_plan_context=_plan_context(actor=None),
    )

    payload = _json_body(body)

    assert status == 401
    assert payload["error"]["code"] == "authentication_required"


@pytest.mark.parametrize("account_status", ["disabled", "revoked"])
def test_auth_provider_integration_plan_rejects_disabled_or_revoked_actor(
    account_status: str,
) -> None:
    status, _content_type, body = route_response(
        _plan_path(),
        auth_provider_integration_plan_context=_plan_context(
            actor=_admin_actor(account_status=account_status),
        ),
    )

    payload = _json_body(body)

    assert status == 403
    assert payload["error"]["code"] == "account_disabled_or_revoked"


def test_auth_provider_integration_plan_rejects_role_without_auth_admin() -> None:
    status, _content_type, body = route_response(
        _plan_path(),
        auth_provider_integration_plan_context=_plan_context(actor=_operator_actor()),
    )

    payload = _json_body(body)

    assert status == 403
    assert payload["error"]["code"] == "role_denied"


def test_auth_provider_integration_plan_rejects_out_of_scope_actor() -> None:
    status, _content_type, body = route_response(
        _plan_path(),
        auth_provider_integration_plan_context=_plan_context(
            actor=_admin_actor(scopes=(OTHER_SCOPE,)),
        ),
    )

    payload = _json_body(body)

    assert status == 403
    assert payload["error"]["code"] == "scope_denied"


def _json_body(body: bytes) -> dict[str, Any]:
    loaded = json.loads(body)
    assert isinstance(loaded, dict)
    return loaded


def _plan_context(
    *,
    actor: AuthenticatedActor | None | object = DEFAULT_ACTOR,
    scope: HostedAccessScope = TEST_SCOPE,
) -> AuthProviderIntegrationPlanContext:
    context_actor = _admin_actor() if actor is DEFAULT_ACTOR else actor
    return AuthProviderIntegrationPlanContext(
        actor=cast(AuthenticatedActor | None, context_actor),
        scope=scope,
    )


def _readiness_inputs_model() -> Any:
    from ccld_complaints.hosted_app.auth_provider_integration_plan import (
        AuthProviderReadinessInputs,
    )

    return AuthProviderReadinessInputs(
        provider_class="managed-oidc-oauth2",
        readiness={field_name: True for field_name in REQUIRED_READINESS_FIELDS},
    )


def _plan_path(
    *,
    provider_class: str = MANAGED_OIDC_OAUTH2_PROVIDER_CLASS,
) -> str:
    query = _readiness_query(provider_class=provider_class)
    return _path_from_query(query)


def _path_from_query(query: dict[str, str]) -> str:
    query_string = "&".join(f"{key}={value}" for key, value in query.items())
    return f"{AUTH_PROVIDER_INTEGRATION_PLAN_API_PATH}?{query_string}"


def _readiness_query(
    *,
    provider_class: str = MANAGED_OIDC_OAUTH2_PROVIDER_CLASS,
) -> dict[str, str]:
    return {
        "provider_class": provider_class,
        **{field_name: "true" for field_name in REQUIRED_READINESS_FIELDS},
    }


def _admin_actor(
    *,
    scopes: tuple[HostedAccessScope, ...] = (TEST_SCOPE,),
    account_status: str = "active",
) -> AuthenticatedActor:
    return _actor(
        roles=("admin",),
        scopes=scopes,
        account_status=account_status,
        actor_category="admin",
        provider_subject="fixture-subject-admin",
        display_name="Fixture Admin",
        email="admin@example.invalid",
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


def _table_counts(connection: Connection) -> dict[str, int]:
    return {
        "import_batches": connection.execute(
            select(func.count()).select_from(hosted_import_batches)
        ).scalar_one(),
        "source_records": connection.execute(
            select(func.count()).select_from(hosted_source_derived_records)
        ).scalar_one(),
        "reviewer_created_state": connection.execute(
            select(func.count()).select_from(hosted_reviewer_created_state)
        ).scalar_one(),
        "audit_events": connection.execute(
            select(func.count()).select_from(hosted_audit_events)
        ).scalar_one(),
        "reset_reload_planning_metadata": connection.execute(
            select(func.count()).select_from(hosted_reset_reload_planning_metadata)
        ).scalar_one(),
    }
