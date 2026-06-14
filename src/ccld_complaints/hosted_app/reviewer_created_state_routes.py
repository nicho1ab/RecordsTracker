from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlparse

from sqlalchemy.engine import Connection

from ccld_complaints.hosted_app.auth import (
    AuthenticatedActor,
    HostedAccessScope,
    HostedAccountDisabledError,
    HostedAuthenticationRequiredError,
    HostedRoleDeniedError,
    HostedScopeDeniedError,
)
from ccld_complaints.hosted_app.reviewer_created_state import (
    REVIEWER_CREATED_STATE_KINDS,
    ReviewerCreatedStateKind,
    ReviewerCreatedStateRead,
    get_reviewer_created_state_scaffold,
    list_reviewer_created_state_scaffold,
)

REVIEWER_CREATED_STATE_API_PREFIX = "/api/reviewer-created-state"
MAX_REVIEWER_CREATED_STATE_API_LIMIT = 100


@dataclass(frozen=True)
class ReviewerCreatedStateApiContext:
    connection: Connection
    actor: AuthenticatedActor | None
    scope: HostedAccessScope


def route_reviewer_created_state_api_response(
    path: str,
    context: ReviewerCreatedStateApiContext | None,
) -> tuple[int, str, bytes]:
    parsed_url = urlparse(path)
    query_values = parse_qs(parsed_url.query, keep_blank_values=True)
    try:
        if context is None:
            return _json_error(
                503,
                "reviewer_created_state_api_context_required",
                "Local/test reviewer-created state API context is not configured.",
            )
        if parsed_url.path == REVIEWER_CREATED_STATE_API_PREFIX:
            return _list_reviewer_created_state(query_values, context)
        if parsed_url.path == f"{REVIEWER_CREATED_STATE_API_PREFIX}/by-id":
            return _get_reviewer_created_state_by_id(query_values, context)
        return _json_error(
            404,
            "reviewer_created_state_api_route_not_found",
            "Reviewer-created state API route not found.",
        )
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


def _list_reviewer_created_state(
    query_values: Mapping[str, list[str]],
    context: ReviewerCreatedStateApiContext,
) -> tuple[int, str, bytes]:
    source_record_key = _optional_query_value(query_values, "source_record_key")
    state_kind = _optional_state_kind(query_values)
    actor_provider_subject = _optional_query_value(
        query_values,
        "actor_provider_subject",
    )
    limit = _bounded_int_query_value(query_values, "limit", default=100, minimum=1)
    offset = _bounded_int_query_value(query_values, "offset", default=0, minimum=0)

    records = list_reviewer_created_state_scaffold(
        context.connection,
        context.actor,
        scope=context.scope,
        source_record_key=source_record_key,
        state_kind=state_kind,
        actor_provider_subject=actor_provider_subject,
        limit=limit,
        offset=offset,
    )
    return _json_response(
        200,
        {
            "reviewer_created_state": [
                _reviewer_created_state_payload(record) for record in records
            ],
            "filters": {
                "source_record_key": source_record_key,
                "state_kind": state_kind,
                "actor_provider_subject": actor_provider_subject,
            },
            "pagination": {
                "limit": limit,
                "offset": offset,
                "returned_count": len(records),
            },
        },
    )


def _get_reviewer_created_state_by_id(
    query_values: Mapping[str, list[str]],
    context: ReviewerCreatedStateApiContext,
) -> tuple[int, str, bytes]:
    reviewer_state_id = _required_query_value(query_values, "reviewer_state_id")
    record = get_reviewer_created_state_scaffold(
        context.connection,
        context.actor,
        scope=context.scope,
        reviewer_state_id=reviewer_state_id,
    )
    if record is None:
        return _json_error(
            404,
            "reviewer_created_state_not_found",
            "Reviewer-created state record not found.",
        )
    return _json_response(
        200,
        {"reviewer_created_state": _reviewer_created_state_payload(record)},
    )


def _reviewer_created_state_payload(
    record: ReviewerCreatedStateRead,
) -> dict[str, Any]:
    return {
        "reviewer_state_id": record.reviewer_state_id,
        "source_record_key": record.source_record_key,
        "scope": {
            "scope_type": record.scope.scope_type,
            "scope_id": record.scope.scope_id,
        },
        "state_kind": record.state_kind,
        "state_payload": dict(record.state_payload),
        "created_at": record.created_at,
        "created_by": {
            "provider_subject": record.created_by_provider_subject,
            "provider_issuer": record.created_by_provider_issuer,
            "display_name": record.created_by_display_name,
            "actor_category": record.created_by_actor_category,
        },
        "authorization_permission": record.authorization_permission,
        "safety": {
            "read_only_route": True,
            "does_not_mutate_source_derived_records": True,
            "does_not_mutate_reviewer_created_state": True,
            "does_not_mutate_audit_events": True,
            "does_not_mutate_operational_metadata": True,
        },
    }


def _optional_state_kind(
    query_values: Mapping[str, list[str]],
) -> ReviewerCreatedStateKind | None:
    raw_state_kind = _optional_query_value(query_values, "state_kind")
    if raw_state_kind is None:
        return None
    if raw_state_kind not in REVIEWER_CREATED_STATE_KINDS:
        allowed_values = ", ".join(REVIEWER_CREATED_STATE_KINDS)
        raise ValueError(f"state_kind must be one of: {allowed_values}.")
    return "review_item_state_scaffold"


def _bounded_int_query_value(
    query_values: Mapping[str, list[str]],
    key: str,
    *,
    default: int,
    minimum: int,
) -> int:
    raw_value = _optional_query_value(query_values, key)
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except ValueError as error:
        raise ValueError(f"{key} must be an integer.") from error
    if value < minimum:
        raise ValueError(f"{key} must be at least {minimum}.")
    if key == "limit" and value > MAX_REVIEWER_CREATED_STATE_API_LIMIT:
        raise ValueError(f"limit must be at most {MAX_REVIEWER_CREATED_STATE_API_LIMIT}.")
    return value


def _required_query_value(
    query_values: Mapping[str, list[str]],
    key: str,
) -> str:
    value = _optional_query_value(query_values, key)
    if value is None:
        raise ValueError(f"{key} is required.")
    return value


def _optional_query_value(
    query_values: Mapping[str, list[str]],
    key: str,
) -> str | None:
    values = query_values.get(key, [])
    if not values:
        return None
    value = values[0].strip()
    if not value:
        return None
    return value


def _json_response(status: int, payload: Mapping[str, Any]) -> tuple[int, str, bytes]:
    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    return status, "application/json; charset=utf-8", body


def _json_error(status: int, code: str, message: str) -> tuple[int, str, bytes]:
    return _json_response(status, {"error": {"code": code, "message": message}})