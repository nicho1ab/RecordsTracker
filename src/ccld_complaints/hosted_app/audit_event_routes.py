from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlparse

from sqlalchemy.engine import Connection

from ccld_complaints.hosted_app.audit_events import (
    HOSTED_AUDIT_ACTIONS,
    HostedAuditAction,
    HostedAuditEventRead,
    get_hosted_audit_event_scaffold,
    list_hosted_audit_events_scaffold,
)
from ccld_complaints.hosted_app.auth import (
    AuthenticatedActor,
    HostedAccessScope,
    HostedAccountDisabledError,
    HostedAuthenticationRequiredError,
    HostedRoleDeniedError,
    HostedScopeDeniedError,
)

AUDIT_EVENTS_API_PREFIX = "/api/audit-events"
MAX_AUDIT_EVENTS_API_LIMIT = 100


@dataclass(frozen=True)
class AuditEventsApiContext:
    connection: Connection
    actor: AuthenticatedActor | None
    scope: HostedAccessScope


def route_audit_events_api_response(
    path: str,
    context: AuditEventsApiContext | None,
) -> tuple[int, str, bytes]:
    parsed_url = urlparse(path)
    query_values = parse_qs(parsed_url.query, keep_blank_values=True)
    try:
        if context is None:
            return _json_error(
                503,
                "audit_events_api_context_required",
                "Local/test audit events API context is not configured.",
            )
        if parsed_url.path == AUDIT_EVENTS_API_PREFIX:
            return _list_audit_events(query_values, context)
        if parsed_url.path == f"{AUDIT_EVENTS_API_PREFIX}/by-id":
            return _get_audit_event_by_id(query_values, context)
        return _json_error(
            404,
            "audit_events_api_route_not_found",
            "Audit events API route not found.",
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


def _list_audit_events(
    query_values: Mapping[str, list[str]],
    context: AuditEventsApiContext,
) -> tuple[int, str, bytes]:
    action = _optional_audit_action(query_values)
    target_reviewer_state_id = _optional_query_value(
        query_values,
        "target_reviewer_state_id",
    )
    source_record_key = _optional_query_value(query_values, "source_record_key")
    actor_provider_subject = _optional_query_value(query_values, "actor_provider_subject")
    source_entity_type = _optional_query_value(query_values, "source_entity_type")
    source_stable_source_id = _optional_query_value(
        query_values,
        "source_stable_source_id",
    )
    source_document_id = _optional_query_value(query_values, "source_document_id")
    limit = _bounded_int_query_value(query_values, "limit", default=100, minimum=1)
    offset = _bounded_int_query_value(query_values, "offset", default=0, minimum=0)

    events = list_hosted_audit_events_scaffold(
        context.connection,
        context.actor,
        scope=context.scope,
        target_reviewer_state_id=target_reviewer_state_id,
        source_record_key=source_record_key,
        action=action,
        actor_provider_subject=actor_provider_subject,
        source_entity_type=source_entity_type,
        source_stable_source_id=source_stable_source_id,
        source_document_id=source_document_id,
        limit=limit,
        offset=offset,
    )
    return _json_response(
        200,
        {
            "audit_events": [_audit_event_payload(event) for event in events],
            "filters": {
                "target_reviewer_state_id": target_reviewer_state_id,
                "source_record_key": source_record_key,
                "action": action,
                "actor_provider_subject": actor_provider_subject,
                "source_entity_type": source_entity_type,
                "source_stable_source_id": source_stable_source_id,
                "source_document_id": source_document_id,
            },
            "pagination": {
                "limit": limit,
                "offset": offset,
                "returned_count": len(events),
            },
        },
    )


def _get_audit_event_by_id(
    query_values: Mapping[str, list[str]],
    context: AuditEventsApiContext,
) -> tuple[int, str, bytes]:
    audit_event_id = _required_query_value(query_values, "audit_event_id")
    event = get_hosted_audit_event_scaffold(
        context.connection,
        context.actor,
        scope=context.scope,
        audit_event_id=audit_event_id,
    )
    if event is None:
        return _json_error(
            404,
            "audit_event_not_found",
            "Audit event not found.",
        )
    return _json_response(200, {"audit_event": _audit_event_payload(event)})


def _audit_event_payload(event: HostedAuditEventRead) -> dict[str, Any]:
    return {
        "audit_event_id": event.audit_event_id,
        "occurred_at": event.occurred_at,
        "actor": {
            "provider_subject": event.actor_provider_subject,
            "provider_issuer": event.actor_provider_issuer,
            "display_name": event.actor_display_name,
            "actor_category": event.actor_category,
        },
        "authorization_permission": event.authorization_permission,
        "scope": {
            "scope_type": event.scope.scope_type,
            "scope_id": event.scope.scope_id,
        },
        "action": event.action,
        "target": {
            "target_type": event.target_type,
            "target_reviewer_state_id": event.target_reviewer_state_id,
        },
        "source": {
            "source_record_key": event.source_record_key,
            "source_entity_type": event.source_entity_type,
            "source_stable_source_id": event.source_stable_source_id,
            "source_document_id": event.source_document_id,
        },
        "context_metadata": dict(event.context_metadata),
    }


def _optional_audit_action(
    query_values: Mapping[str, list[str]],
) -> HostedAuditAction | None:
    raw_action = _optional_query_value(query_values, "action")
    if raw_action is None:
        return None
    if raw_action not in HOSTED_AUDIT_ACTIONS:
        allowed_values = ", ".join(HOSTED_AUDIT_ACTIONS)
        raise ValueError(f"action must be one of: {allowed_values}.")
    return raw_action


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
    if key == "limit" and value > MAX_AUDIT_EVENTS_API_LIMIT:
        raise ValueError(f"limit must be at most {MAX_AUDIT_EVENTS_API_LIMIT}.")
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