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
from ccld_complaints.hosted_app.reset_reload_dry_run import (
    REVIEWER_STATE_HANDLING_OPTIONS,
    ResetReloadPlanningMetadataRead,
    ResetReloadRequestedOperationMode,
    ReviewerStateHandlingMode,
    get_seeded_corpus_reset_reload_planning_metadata,
    list_seeded_corpus_reset_reload_planning_metadata,
)

RESET_RELOAD_PLANNING_METADATA_API_PREFIX = (
    "/api/operations/seeded-corpus-reset-reload/planning-metadata"
)
MAX_RESET_RELOAD_PLANNING_METADATA_API_LIMIT = 100


@dataclass(frozen=True)
class ResetReloadPlanningMetadataApiContext:
    connection: Connection
    actor: AuthenticatedActor | None
    scope: HostedAccessScope


def route_reset_reload_planning_metadata_api_response(
    path: str,
    context: ResetReloadPlanningMetadataApiContext | None,
) -> tuple[int, str, bytes]:
    parsed_url = urlparse(path)
    query_values = parse_qs(parsed_url.query, keep_blank_values=True)
    try:
        if context is None:
            return _json_error(
                503,
                "reset_reload_planning_metadata_api_context_required",
                "Local/test reset/reload planning metadata API context is not configured.",
            )
        if parsed_url.path == RESET_RELOAD_PLANNING_METADATA_API_PREFIX:
            return _list_planning_metadata(query_values, context)
        if parsed_url.path == f"{RESET_RELOAD_PLANNING_METADATA_API_PREFIX}/by-id":
            return _get_planning_metadata_by_id(query_values, context)
        return _json_error(
            404,
            "reset_reload_planning_metadata_api_route_not_found",
            "Reset/reload planning metadata API route not found.",
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


def _list_planning_metadata(
    query_values: Mapping[str, list[str]],
    context: ResetReloadPlanningMetadataApiContext,
) -> tuple[int, str, bytes]:
    reviewer_state_handling_mode = _optional_reviewer_state_handling_mode(query_values)
    actor_provider_subject = _optional_query_value(query_values, "actor_provider_subject")
    requested_operation_mode = _optional_requested_operation_mode(query_values)
    limit = _bounded_int_query_value(query_values, "limit", default=100, minimum=1)
    offset = _bounded_int_query_value(query_values, "offset", default=0, minimum=0)

    records = list_seeded_corpus_reset_reload_planning_metadata(
        context.connection,
        context.actor,
        scope=context.scope,
        reviewer_state_handling_mode=reviewer_state_handling_mode,
        actor_provider_subject=actor_provider_subject,
        requested_operation_mode=requested_operation_mode,
        limit=limit,
        offset=offset,
    )
    return _json_response(
        200,
        {
            "planning_metadata": [_planning_metadata_payload(record) for record in records],
            "filters": {
                "reviewer_state_handling_mode": reviewer_state_handling_mode,
                "actor_provider_subject": actor_provider_subject,
                "requested_operation_mode": requested_operation_mode,
            },
            "pagination": {
                "limit": limit,
                "offset": offset,
                "returned_count": len(records),
            },
        },
    )


def _get_planning_metadata_by_id(
    query_values: Mapping[str, list[str]],
    context: ResetReloadPlanningMetadataApiContext,
) -> tuple[int, str, bytes]:
    planning_record_id = _required_query_value(query_values, "planning_record_id")
    record = get_seeded_corpus_reset_reload_planning_metadata(
        context.connection,
        context.actor,
        scope=context.scope,
        planning_record_id=planning_record_id,
    )
    if record is None:
        return _json_error(
            404,
            "reset_reload_planning_metadata_not_found",
            "Reset/reload planning metadata record not found.",
        )
    return _json_response(200, {"planning_metadata": _planning_metadata_payload(record)})


def _planning_metadata_payload(
    record: ResetReloadPlanningMetadataRead,
) -> dict[str, Any]:
    return {
        "planning_record_id": record.planning_record_id,
        "generated_at": record.generated_at,
        "operation": record.operation,
        "requested_operation_mode": record.requested_operation_mode,
        "scope": {
            "scope_type": record.scope.scope_type,
            "scope_id": record.scope.scope_id,
        },
        "reviewer_state_handling_mode": record.reviewer_state_handling_mode,
        "actor": {
            "provider_subject": record.actor_provider_subject,
            "provider_issuer": record.actor_provider_issuer,
            "display_name": record.actor_display_name,
            "actor_category": record.actor_category,
        },
        "authorization_permission": record.authorization_permission,
        "source_derived_summary": dict(record.source_derived_summary),
        "reviewer_created_state_summary": dict(record.reviewer_created_state_summary),
        "audit_event_summary": dict(record.audit_event_summary),
        "validation_summary": dict(record.validation_summary),
        "planning_context": dict(record.planning_context),
        "future_execution_permissions": list(record.future_execution_permissions),
        "deferred_actions": list(record.deferred_actions),
        "safety": {
            "data_mutations_performed": record.data_mutations_performed,
            "read_only_route": True,
            "does_not_execute_reset_reload": True,
        },
    }


def _optional_reviewer_state_handling_mode(
    query_values: Mapping[str, list[str]],
) -> ReviewerStateHandlingMode | None:
    raw_mode = _optional_query_value(query_values, "reviewer_state_handling_mode")
    if raw_mode is None:
        return None
    if raw_mode not in REVIEWER_STATE_HANDLING_OPTIONS:
        allowed_values = ", ".join(REVIEWER_STATE_HANDLING_OPTIONS)
        raise ValueError(f"reviewer_state_handling_mode must be one of: {allowed_values}.")
    if raw_mode == "preserve":
        return "preserve"
    if raw_mode == "archive":
        return "archive"
    return "clear"


def _optional_requested_operation_mode(
    query_values: Mapping[str, list[str]],
) -> ResetReloadRequestedOperationMode | None:
    raw_mode = _optional_query_value(query_values, "requested_operation_mode")
    if raw_mode is None:
        return None
    if raw_mode != "dry_run":
        raise ValueError("requested_operation_mode must be 'dry_run'.")
    return "dry_run"


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
    if key == "limit" and value > MAX_RESET_RELOAD_PLANNING_METADATA_API_LIMIT:
        raise ValueError(
            f"limit must be at most {MAX_RESET_RELOAD_PLANNING_METADATA_API_LIMIT}."
        )
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