from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast
from urllib.parse import parse_qs, urlencode, urlparse

from ccld_complaints.hosted_app.reviewer_created_state_routes import (
    REVIEWER_CREATED_STATE_API_PREFIX,
    ReviewerCreatedStateApiContext,
    route_reviewer_created_state_api_response,
)
from ccld_complaints.hosted_app.source_derived_routes import (
    SourceDerivedApiContext,
    route_source_derived_api_response,
)

REVIEWER_WORKFLOW_API_PREFIX = "/api/reviewer/source-derived-review"
DEFAULT_REVIEW_QUEUE_ENTITY_TYPE = "complaint"


@dataclass(frozen=True)
class ReviewerWorkflowShellContext:
    source_derived_api_context: SourceDerivedApiContext
    reviewer_created_state_api_context: ReviewerCreatedStateApiContext


def route_reviewer_workflow_shell_response(
    path: str,
    context: ReviewerWorkflowShellContext | None,
    *,
    request_body: bytes | None = None,
) -> tuple[int, str, bytes]:
    parsed_url = urlparse(path)
    query_values = parse_qs(parsed_url.query, keep_blank_values=True)
    if context is None:
        return _json_error(
            503,
            "reviewer_workflow_shell_context_required",
            "Local/test reviewer workflow shell context is not configured.",
        )
    if parsed_url.path in {
        REVIEWER_WORKFLOW_API_PREFIX,
        f"{REVIEWER_WORKFLOW_API_PREFIX}/queue",
    }:
        return _review_queue_response(query_values, context)
    if parsed_url.path == f"{REVIEWER_WORKFLOW_API_PREFIX}/detail":
        return _review_detail_response(query_values, context)
    if parsed_url.path == f"{REVIEWER_WORKFLOW_API_PREFIX}/detail/reviewer-note":
        return _create_reviewer_note_from_detail_response(
            query_values,
            context,
            request_body,
        )
    return _json_error(
        404,
        "reviewer_workflow_shell_route_not_found",
        "Reviewer workflow shell route not found.",
    )


def _review_queue_response(
    query_values: Mapping[str, list[str]],
    context: ReviewerWorkflowShellContext,
) -> tuple[int, str, bytes]:
    entity_type = _optional_query_value(query_values, "entity_type")
    source_query: dict[str, str] = {
        "entity_type": DEFAULT_REVIEW_QUEUE_ENTITY_TYPE
        if entity_type is None
        else entity_type
    }
    for key in ("limit", "offset"):
        value = _optional_query_value(query_values, key)
        if value is not None:
            source_query[key] = value

    status, content_type, body = route_source_derived_api_response(
        f"/api/source-derived-records?{urlencode(source_query)}",
        context.source_derived_api_context,
    )
    if status != 200:
        return status, content_type, body

    source_payload = _json_object(body)
    records = _record_list(source_payload, "records")
    return _json_response(
        200,
        {
            "workflow_shell": _workflow_shell_payload(context),
            "queue": {
                "queue_id": "source-derived-review-queue-shell",
                "queue_source": "source-derived route seam",
                "empty": len(records) == 0,
                "records": [_review_item_payload(record) for record in records],
                "filters": source_payload["filters"],
                "pagination": source_payload["pagination"],
            },
        },
    )


def _review_detail_response(
    query_values: Mapping[str, list[str]],
    context: ReviewerWorkflowShellContext,
) -> tuple[int, str, bytes]:
    status, content_type, body = _selected_source_record_response(query_values, context)
    if status != 200:
        return status, content_type, body

    source_payload = _json_object(body)
    record = _record_object(source_payload, "record")
    return _review_detail_response_for_record(record, query_values, context)


def _create_reviewer_note_from_detail_response(
    query_values: Mapping[str, list[str]],
    context: ReviewerWorkflowShellContext,
    request_body: bytes | None,
) -> tuple[int, str, bytes]:
    status, content_type, body = _selected_source_record_response(query_values, context)
    if status != 200:
        return status, content_type, body

    source_payload = _json_object(body)
    record = _record_object(source_payload, "record")
    resolved_source_record_key = _record_string(record, "source_record_key")
    create_status, create_content_type, create_body = (
        route_reviewer_created_state_api_response(
            f"{REVIEWER_CREATED_STATE_API_PREFIX}/reviewer-note?"
            f"{urlencode({'source_record_key': resolved_source_record_key})}",
            context.reviewer_created_state_api_context,
            request_body=request_body,
        )
    )
    if create_status != 201:
        return create_status, create_content_type, create_body

    created_payload = _json_object(create_body)
    detail_status, detail_content_type, detail_body = _review_detail_response_for_record(
        record,
        query_values,
        context,
    )
    if detail_status != 200:
        return detail_status, detail_content_type, detail_body
    detail_payload = _json_object(detail_body)
    return _json_response(
        201,
        {
            "workflow_shell": _workflow_shell_payload(context),
            "workflow_action": {
                "action_id": "create-reviewer-note-from-selected-detail-shell",
                "action_source": (
                    f"{REVIEWER_WORKFLOW_API_PREFIX}/detail/reviewer-note"
                ),
                "delegated_route_source": (
                    f"{REVIEWER_CREATED_STATE_API_PREFIX}/reviewer-note"
                ),
                "created_reviewer_note": True,
                "selected_source_record_key": resolved_source_record_key,
                "source_record_binding_forced_from_selected_detail": True,
                "local_test_only": True,
                "writes_create_audit_event": True,
                "source_of_record": "public portal",
                "does_not_mutate_source_derived_records": True,
            },
            "reviewer_created_state": created_payload["reviewer_created_state"],
            "delegated_reviewer_created_state_workflow": created_payload["workflow"],
            "detail": detail_payload["detail"],
        },
    )


def _selected_source_record_response(
    query_values: Mapping[str, list[str]],
    context: ReviewerWorkflowShellContext,
) -> tuple[int, str, bytes]:
    source_record_key = _optional_query_value(query_values, "source_record_key")
    source_path = "/api/source-derived-records/by-key"
    if source_record_key is not None:
        source_path = f"{source_path}?{urlencode({'source_record_key': source_record_key})}"

    status, content_type, body = route_source_derived_api_response(
        source_path,
        context.source_derived_api_context,
    )
    if status != 200:
        return status, content_type, body
    return status, content_type, body


def _review_detail_response_for_record(
    record: Mapping[str, Any],
    query_values: Mapping[str, list[str]],
    context: ReviewerWorkflowShellContext,
) -> tuple[int, str, bytes]:
    state_query_values = {"source_record_key": record["source_record_key"]}
    for key in ("state_kind", "actor_provider_subject", "q"):
        value = _optional_query_value(query_values, key)
        if value is not None:
            state_query_values[key] = value
    state_query = urlencode(state_query_values)
    state_status, state_content_type, state_body = route_reviewer_created_state_api_response(
        f"{REVIEWER_CREATED_STATE_API_PREFIX}?{state_query}",
        context.reviewer_created_state_api_context,
    )
    if state_status != 200:
        return state_status, state_content_type, state_body

    state_payload = _json_object(state_body)
    associated_state = _associated_reviewer_created_state_payload(state_payload)
    return _json_response(
        200,
        {
            "workflow_shell": _workflow_shell_payload(context),
            "detail": {
                "detail_id": f"source-derived-review-detail-shell:{record['source_record_key']}",
                "source_record": _source_record_payload(record),
                "associated_reviewer_created_state": associated_state,
                "associated_reviewer_created_state_summary": (
                    _associated_reviewer_created_state_summary_payload(associated_state)
                ),
                "reviewer_created_state_boundary": _reviewer_state_boundary_payload(),
            },
        },
    )


def _workflow_shell_payload(context: ReviewerWorkflowShellContext) -> dict[str, Any]:
    scope = context.source_derived_api_context.scope
    return {
        "workflow_id": "authenticated-source-derived-review-shell",
        "workflow_label": "Authenticated source-derived review shell",
        "mode": "local_test_read_with_note_action",
        "authenticated_route_source": "/api/source-derived-records",
        "scope": {"scope_type": scope.scope_type, "scope_id": scope.scope_id},
        "source_of_record": "public portal",
        "reviewer_created_state_persistence": True,
        "reviewer_created_state_reads_enabled": True,
        "reviewer_created_state_read_route_source": REVIEWER_CREATED_STATE_API_PREFIX,
        "reviewer_note_action_enabled": True,
        "reviewer_note_action_route_source": (
            f"{REVIEWER_WORKFLOW_API_PREFIX}/detail/reviewer-note"
        ),
        "reviewer_actions_enabled": ["create_reviewer_note"],
        "deferred_actions": [
            "review status persistence",
            "full annotation workflow",
            "corrections",
            "export packet builder",
            "reset/reload behavior",
        ],
    }


def _review_item_payload(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "review_item_id": f"source-derived-review-shell:{record['source_record_key']}",
        "source_record": _source_record_payload(record),
        "reviewer_created_state_boundary": _reviewer_state_boundary_payload(),
    }


def _source_record_payload(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "identity": {
            "source_record_key": record["source_record_key"],
            "entity_type": record["entity_type"],
            "stable_source_id": record["stable_source_id"],
            "facility_id": record["facility_id"],
        },
        "source_document": {
            "source_document_id": record["source_document_id"],
            "source_url": record["source_url"],
            "raw_sha256": record["raw_sha256"],
            "raw_path": record["raw_path"],
            "connector_name": record["connector_name"],
            "connector_version": record["connector_version"],
            "retrieved_at": record["retrieved_at"],
        },
        "original_values": record["original_values"],
        "source_traceability": record["source_traceability"],
        "import_batch": record["import_batch"],
    }


def _reviewer_state_boundary_payload() -> dict[str, Any]:
    return {
        "persistence_enabled": True,
        "workflow_note_action_enabled": True,
        "workflow_note_action_route_source": (
            f"{REVIEWER_WORKFLOW_API_PREFIX}/detail/reviewer-note"
        ),
        "associated_state_reads_enabled": True,
        "associated_state_read_route_source": REVIEWER_CREATED_STATE_API_PREFIX,
        "associated_state_reads_require_reviewer_state_read_permission": True,
        "reads_create_or_modify_state": False,
        "anonymous_reviewer_created_state_allowed": False,
        "available_actions": ["create_reviewer_note"],
        "deferred_actions": [
            "queue state persistence",
            "review status changes",
            "full annotation workflow",
            "correction proposals",
            "tester feedback",
            "export packet decisions",
        ],
    }


def _associated_reviewer_created_state_payload(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    records = _record_list(payload, "reviewer_created_state")
    return {
        "route_source": REVIEWER_CREATED_STATE_API_PREFIX,
        "empty": len(records) == 0,
        "reviewer_created_state": records,
        "filters": payload["filters"],
        "pagination": payload["pagination"],
        "safety": {
            "read_only_route": True,
            "does_not_mutate_source_derived_records": True,
            "does_not_mutate_reviewer_created_state": True,
            "does_not_mutate_audit_events": True,
            "does_not_mutate_operational_metadata": True,
        },
    }


def _associated_reviewer_created_state_summary_payload(
    associated_state: Mapping[str, Any],
) -> dict[str, Any]:
    records = _record_list(associated_state, "reviewer_created_state")
    created_at_values = [_record_string(record, "created_at") for record in records]
    return {
        "summary_source": REVIEWER_CREATED_STATE_API_PREFIX,
        "has_reviewer_created_state": len(records) > 0,
        "total_associated_rows": len(records),
        "state_kinds_present": sorted(
            {_record_string(record, "state_kind") for record in records}
        ),
        "latest_created_at": max(created_at_values) if created_at_values else None,
        "actor_attribution_labels": sorted(
            {_actor_attribution_label(record) for record in records}
        ),
        "actor_categories_present": sorted(
            {
                _record_string(_record_object(record, "created_by"), "actor_category")
                for record in records
            }
        ),
        "safety": {
            "derived_from_associated_state_route_output": True,
            "read_only_route": True,
            "does_not_mutate_source_derived_records": True,
            "does_not_mutate_reviewer_created_state": True,
            "does_not_mutate_audit_events": True,
            "does_not_mutate_operational_metadata": True,
        },
    }


def _actor_attribution_label(record: Mapping[str, Any]) -> str:
    created_by = _record_object(record, "created_by")
    actor_category = _record_string(created_by, "actor_category")
    display_name = created_by.get("display_name")
    if isinstance(display_name, str) and display_name.strip():
        return f"{display_name.strip()} ({actor_category})"
    return actor_category


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


def _json_object(body: bytes) -> dict[str, Any]:
    loaded = json.loads(body)
    if not isinstance(loaded, dict):
        raise ValueError("Expected JSON object response from source-derived route.")
    return cast(dict[str, Any], loaded)


def _record_list(payload: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    value = payload[key]
    if not isinstance(value, list):
        raise ValueError(f"Expected {key} to be a JSON list.")
    records: list[Mapping[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise ValueError(f"Expected {key} to contain JSON objects.")
        records.append(item)
    return records


def _record_object(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload[key]
    if not isinstance(value, Mapping):
        raise ValueError(f"Expected {key} to be a JSON object.")
    return value


def _record_string(payload: Mapping[str, Any], key: str) -> str:
    value = payload[key]
    if not isinstance(value, str):
        raise ValueError(f"Expected {key} to be a JSON string.")
    return value


def _json_response(status: int, payload: Mapping[str, Any]) -> tuple[int, str, bytes]:
    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    return status, "application/json; charset=utf-8", body


def _json_error(status: int, code: str, message: str) -> tuple[int, str, bytes]:
    return _json_response(status, {"error": {"code": code, "message": message}})