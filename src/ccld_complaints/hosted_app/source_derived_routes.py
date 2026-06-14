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
    get_authorized_source_derived_record_by_identity,
    get_authorized_source_derived_record_by_key,
    list_authorized_source_derived_records,
)
from ccld_complaints.hosted_app.seeded_import import (
    SOURCE_DERIVED_ENTITY_TYPES,
    SourceDerivedEntityType,
)
from ccld_complaints.hosted_app.source_derived_reads import (
    ImportBatchRead,
    SourceDerivedRecordRead,
)

SOURCE_DERIVED_API_PREFIX = "/api/source-derived-records"
MAX_SOURCE_DERIVED_API_LIMIT = 100


@dataclass(frozen=True)
class SourceDerivedApiContext:
    connection: Connection
    actor: AuthenticatedActor | None
    scope: HostedAccessScope


def route_source_derived_api_response(
    path: str,
    context: SourceDerivedApiContext | None,
) -> tuple[int, str, bytes]:
    parsed_url = urlparse(path)
    query_values = parse_qs(parsed_url.query, keep_blank_values=True)
    try:
        if context is None:
            return _json_error(
                503,
                "source_derived_api_context_required",
                "Local/test source-derived API context is not configured.",
            )
        if parsed_url.path == SOURCE_DERIVED_API_PREFIX:
            return _list_source_derived_records(query_values, context)
        if parsed_url.path == f"{SOURCE_DERIVED_API_PREFIX}/by-key":
            return _get_source_derived_record_by_key(query_values, context)
        if parsed_url.path == f"{SOURCE_DERIVED_API_PREFIX}/by-identity":
            return _get_source_derived_record_by_identity(query_values, context)
        return _json_error(
            404,
            "source_derived_api_route_not_found",
            "Source-derived API route not found.",
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


def _list_source_derived_records(
    query_values: Mapping[str, list[str]],
    context: SourceDerivedApiContext,
) -> tuple[int, str, bytes]:
    entity_type = _optional_entity_type(query_values)
    limit = _bounded_int_query_value(query_values, "limit", default=100, minimum=1)
    offset = _bounded_int_query_value(query_values, "offset", default=0, minimum=0)
    records = list_authorized_source_derived_records(
        context.connection,
        context.actor,
        scope=context.scope,
        entity_type=entity_type,
        limit=limit,
        offset=offset,
    )
    return _json_response(
        200,
        {
            "records": [_record_payload(record) for record in records],
            "filters": {"entity_type": entity_type},
            "pagination": {
                "limit": limit,
                "offset": offset,
                "returned_count": len(records),
            },
        },
    )


def _get_source_derived_record_by_key(
    query_values: Mapping[str, list[str]],
    context: SourceDerivedApiContext,
) -> tuple[int, str, bytes]:
    source_record_key = _required_query_value(query_values, "source_record_key")
    record = get_authorized_source_derived_record_by_key(
        context.connection,
        context.actor,
        scope=context.scope,
        source_record_key=source_record_key,
    )
    return _record_or_not_found(record)


def _get_source_derived_record_by_identity(
    query_values: Mapping[str, list[str]],
    context: SourceDerivedApiContext,
) -> tuple[int, str, bytes]:
    entity_type = _required_entity_type(query_values)
    stable_source_id = _required_query_value(query_values, "stable_source_id")
    record = get_authorized_source_derived_record_by_identity(
        context.connection,
        context.actor,
        scope=context.scope,
        entity_type=entity_type,
        stable_source_id=stable_source_id,
    )
    return _record_or_not_found(record)


def _record_or_not_found(
    record: SourceDerivedRecordRead | None,
) -> tuple[int, str, bytes]:
    if record is None:
        return _json_error(
            404,
            "source_derived_record_not_found",
            "Source-derived record not found.",
        )
    return _json_response(200, {"record": _record_payload(record)})


def _record_payload(record: SourceDerivedRecordRead) -> dict[str, Any]:
    return {
        "source_record_key": record.source_record_key,
        "entity_type": record.entity_type,
        "stable_source_id": record.stable_source_id,
        "source_document_id": record.source_document_id,
        "facility_id": record.facility_id,
        "source_url": record.source_url,
        "raw_sha256": record.raw_sha256,
        "raw_path": record.raw_path,
        "connector_name": record.connector_name,
        "connector_version": record.connector_version,
        "retrieved_at": record.retrieved_at,
        "original_values": dict(record.original_values),
        "source_traceability": dict(record.source_traceability),
        "import_batch": _import_batch_payload(record.import_batch),
    }


def _import_batch_payload(import_batch: ImportBatchRead) -> dict[str, Any]:
    return {
        "import_batch_id": import_batch.import_batch_id,
        "imported_at": import_batch.imported_at,
        "source_artifact_identity": import_batch.source_artifact_identity,
        "source_pipeline_version": import_batch.source_pipeline_version,
        "validation_status": import_batch.validation_status,
        "raw_hash_validation_status": import_batch.raw_hash_validation_status,
        "record_counts": dict(import_batch.record_counts),
        "warnings": list(import_batch.warnings),
        "errors": list(import_batch.errors),
    }


def _optional_entity_type(
    query_values: Mapping[str, list[str]],
) -> SourceDerivedEntityType | None:
    raw_entity_type = _optional_query_value(query_values, "entity_type")
    if raw_entity_type is None:
        return None
    return _validate_entity_type(raw_entity_type)


def _required_entity_type(
    query_values: Mapping[str, list[str]],
) -> SourceDerivedEntityType:
    return _validate_entity_type(_required_query_value(query_values, "entity_type"))


def _validate_entity_type(raw_entity_type: str) -> SourceDerivedEntityType:
    if raw_entity_type not in SOURCE_DERIVED_ENTITY_TYPES:
        allowed_values = ", ".join(SOURCE_DERIVED_ENTITY_TYPES)
        raise ValueError(f"entity_type must be one of: {allowed_values}.")
    return raw_entity_type


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
    if key == "limit" and value > MAX_SOURCE_DERIVED_API_LIMIT:
        raise ValueError(f"limit must be at most {MAX_SOURCE_DERIVED_API_LIMIT}.")
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