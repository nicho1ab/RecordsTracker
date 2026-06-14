from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import parse_qs, urlparse

from sqlalchemy import func, select
from sqlalchemy.engine import Connection, RowMapping

from ccld_complaints.hosted_app.auth import (
    IMPORT_RELOAD_PERMISSION,
    AuthenticatedActor,
    AuthorizationDecision,
    AuthorizationTarget,
    HostedAccessScope,
    HostedAccountDisabledError,
    HostedAuthenticationRequiredError,
    HostedRoleDeniedError,
    HostedScopeDeniedError,
    require_permission,
)
from ccld_complaints.hosted_app.reviewer_created_state import (
    hosted_reviewer_created_state,
)
from ccld_complaints.hosted_app.seeded_import import (
    SOURCE_DERIVED_ENTITY_TYPES,
    SourceDerivedEntityType,
    hosted_import_batches,
    hosted_source_derived_records,
)

SEEDED_CORPUS_RESET_RELOAD_DRY_RUN_API_PATH = (
    "/api/operations/seeded-corpus-reset-reload/dry-run"
)
ReviewerStateHandlingMode = Literal["preserve", "archive", "clear"]
REVIEWER_STATE_HANDLING_OPTIONS: tuple[ReviewerStateHandlingMode, ...] = (
    "preserve",
    "archive",
    "clear",
)
DEFAULT_REVIEWER_STATE_HANDLING_MODE: ReviewerStateHandlingMode = "preserve"


@dataclass(frozen=True)
class SeededCorpusResetReloadDryRunContext:
    connection: Connection
    actor: AuthenticatedActor | None
    scope: HostedAccessScope


@dataclass(frozen=True)
class ImportBatchImpact:
    import_batch_id: str
    imported_at: str
    source_artifact_identity: str
    source_pipeline_version: str | None
    validation_status: str
    raw_hash_validation_status: str
    record_counts: Mapping[str, int]
    warnings: tuple[str, ...]
    errors: tuple[str, ...]


@dataclass(frozen=True)
class SourceDerivedImpact:
    existing_import_batch_count: int
    existing_source_derived_record_count: int
    counts_by_entity: Mapping[SourceDerivedEntityType, int]
    import_batches: tuple[ImportBatchImpact, ...]


@dataclass(frozen=True)
class ReviewerCreatedStateImpact:
    persistence_implemented: bool
    selected_handling_mode: ReviewerStateHandlingMode
    handling_options: tuple[ReviewerStateHandlingMode, ...]
    affected_state_categories: tuple[str, ...]
    current_state_count: int | None
    planning_note: str


@dataclass(frozen=True)
class SeededCorpusResetReloadDryRunPlan:
    dry_run: bool
    operation: str
    scope: HostedAccessScope
    authorized: AuthorizationDecision
    source_derived_impact: SourceDerivedImpact
    reviewer_created_state_impact: ReviewerCreatedStateImpact
    future_execution_permissions: tuple[str, ...]
    validation_requirements: tuple[str, ...]
    audit_requirements: tuple[str, ...]
    deferred_actions: tuple[str, ...]
    data_mutations_performed: bool = False


def route_seeded_corpus_reset_reload_dry_run_response(
    path: str,
    context: SeededCorpusResetReloadDryRunContext | None,
) -> tuple[int, str, bytes]:
    parsed_url = urlparse(path)
    query_values = parse_qs(parsed_url.query, keep_blank_values=True)
    try:
        if context is None:
            return _json_error(
                503,
                "reset_reload_dry_run_context_required",
                "Local/test reset/reload dry-run context is not configured.",
            )
        if parsed_url.path != SEEDED_CORPUS_RESET_RELOAD_DRY_RUN_API_PATH:
            return _json_error(
                404,
                "reset_reload_dry_run_route_not_found",
                "Reset/reload dry-run route not found.",
            )
        reviewer_state_mode = _reviewer_state_mode(query_values)
        plan = plan_seeded_corpus_reset_reload_dry_run(
            context.connection,
            context.actor,
            scope=context.scope,
            reviewer_state_mode=reviewer_state_mode,
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


def plan_seeded_corpus_reset_reload_dry_run(
    connection: Connection,
    actor: AuthenticatedActor | None,
    *,
    scope: HostedAccessScope,
    reviewer_state_mode: ReviewerStateHandlingMode = DEFAULT_REVIEWER_STATE_HANDLING_MODE,
) -> SeededCorpusResetReloadDryRunPlan:
    authorized = require_permission(
        actor,
        permission=IMPORT_RELOAD_PERMISSION,
        scope=scope,
        target=AuthorizationTarget("import_batch", scope.scope_id),
    )
    return SeededCorpusResetReloadDryRunPlan(
        dry_run=True,
        operation="seeded_corpus_reset_reload_dry_run",
        scope=scope,
        authorized=authorized,
        source_derived_impact=_source_derived_impact(connection, scope),
        reviewer_created_state_impact=_reviewer_created_state_impact(
            connection,
            scope,
            reviewer_state_mode
        ),
        future_execution_permissions=_future_execution_permissions(reviewer_state_mode),
        validation_requirements=(
            "validated pipeline output or approved export artifact",
            "raw hash validation status must be validated",
            "record counts by source-derived entity must be checked",
            "stable source-derived identities must be preserved",
            "source traceability fields must remain present after reload",
            "reviewer-created state handling mode must be explicit before execution",
            "future execution must compare against retained SQLite/Datasette "
            "validation output where applicable",
        ),
        audit_requirements=(
            "future execution must persist actor or process identity",
            "future execution must persist generated ISO datetime with timezone",
            "future execution must persist corpus scope and import artifact or batch relationship",
            "future execution must persist source-derived counts affected",
            "future execution must persist reviewer-created state preserved, "
            "archived, or cleared counts where implemented",
            "this dry-run does not persist an audit event",
        ),
        deferred_actions=(
            "delete source-derived records",
            "truncate source-derived tables",
            "overwrite source-derived records",
            "archive reviewer-created state",
            "clear reviewer-created state",
            "import or reload seeded corpus artifacts",
            "run live crawling or hosted connector execution",
            "persist audit events or operational reset metadata",
        ),
    )


def _source_derived_impact(
    connection: Connection,
    scope: HostedAccessScope,
) -> SourceDerivedImpact:
    import_batch_count = connection.execute(
        select(func.count()).select_from(hosted_import_batches).where(
            hosted_import_batches.c.import_batch_id == scope.scope_id
        )
    ).scalar_one()
    source_record_count = connection.execute(
        select(func.count()).select_from(hosted_source_derived_records).where(
            hosted_source_derived_records.c.import_batch_id == scope.scope_id
        )
    ).scalar_one()
    counts_by_entity = {entity_type: 0 for entity_type in SOURCE_DERIVED_ENTITY_TYPES}
    rows = connection.execute(
        select(
            hosted_source_derived_records.c.entity_type,
            func.count().label("entity_count"),
        )
        .where(hosted_source_derived_records.c.import_batch_id == scope.scope_id)
        .group_by(hosted_source_derived_records.c.entity_type)
    ).mappings()
    for row in rows:
        counts_by_entity[_entity_type(row)] = _int_value(row, "entity_count")
    import_batches = tuple(
        _import_batch_impact(row)
        for row in connection.execute(
            select(hosted_import_batches).where(
                hosted_import_batches.c.import_batch_id == scope.scope_id
            )
        )
        .mappings()
        .all()
    )
    return SourceDerivedImpact(
        existing_import_batch_count=import_batch_count,
        existing_source_derived_record_count=source_record_count,
        counts_by_entity=counts_by_entity,
        import_batches=import_batches,
    )


def _reviewer_created_state_impact(
    connection: Connection,
    scope: HostedAccessScope,
    reviewer_state_mode: ReviewerStateHandlingMode,
) -> ReviewerCreatedStateImpact:
    current_state_count = connection.execute(
        select(func.count()).select_from(hosted_reviewer_created_state).where(
            hosted_reviewer_created_state.c.scope_type == scope.scope_type,
            hosted_reviewer_created_state.c.scope_id == scope.scope_id,
        )
    ).scalar_one()
    return ReviewerCreatedStateImpact(
        persistence_implemented=True,
        selected_handling_mode=reviewer_state_mode,
        handling_options=REVIEWER_STATE_HANDLING_OPTIONS,
        affected_state_categories=(
            "review status history",
            "queue state",
            "annotations",
            "field-level notes",
            "source verification notes",
            "proposed corrections",
            "correction decisions",
            "tester feedback",
            "export packets",
            "audit events",
            "operational reset/reload metadata",
        ),
        current_state_count=current_state_count,
        planning_note=(
            "A narrow reviewer-created state scaffold table is implemented, so this "
            "dry-run counts scoped scaffold rows but does not archive, clear, relink, "
            "or persist operational reset/reload state."
        ),
    )


def _future_execution_permissions(
    reviewer_state_mode: ReviewerStateHandlingMode,
) -> tuple[str, ...]:
    if reviewer_state_mode == "clear":
        return ("import_reload", "reset_destructive")
    return ("import_reload",)


def _reviewer_state_mode(
    query_values: Mapping[str, list[str]],
) -> ReviewerStateHandlingMode:
    raw_mode = _optional_query_value(query_values, "reviewer_state_mode")
    if raw_mode is None:
        return DEFAULT_REVIEWER_STATE_HANDLING_MODE
    if raw_mode not in REVIEWER_STATE_HANDLING_OPTIONS:
        allowed_values = ", ".join(REVIEWER_STATE_HANDLING_OPTIONS)
        raise ValueError(f"reviewer_state_mode must be one of: {allowed_values}.")
    if raw_mode == "preserve":
        return "preserve"
    if raw_mode == "archive":
        return "archive"
    return "clear"


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


def _plan_payload(plan: SeededCorpusResetReloadDryRunPlan) -> dict[str, Any]:
    return {
        "dry_run": plan.dry_run,
        "operation": plan.operation,
        "scope": {
            "scope_type": plan.scope.scope_type,
            "scope_id": plan.scope.scope_id,
        },
        "authorization": _authorization_payload(plan.authorized),
        "source_derived_impact": _source_derived_impact_payload(
            plan.source_derived_impact
        ),
        "reviewer_created_state_impact": _reviewer_created_state_impact_payload(
            plan.reviewer_created_state_impact
        ),
        "future_execution_permissions": list(plan.future_execution_permissions),
        "validation_requirements": list(plan.validation_requirements),
        "audit_requirements": list(plan.audit_requirements),
        "deferred_actions": list(plan.deferred_actions),
        "safety": {
            "data_mutations_performed": plan.data_mutations_performed,
            "queries_only": True,
            "dry_run_does_not_execute_reset_reload": True,
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


def _source_derived_impact_payload(impact: SourceDerivedImpact) -> dict[str, Any]:
    return {
        "existing_import_batch_count": impact.existing_import_batch_count,
        "existing_source_derived_record_count": impact.existing_source_derived_record_count,
        "counts_by_entity": dict(impact.counts_by_entity),
        "import_batches": [_import_batch_payload(batch) for batch in impact.import_batches],
        "future_reload_scope": "seeded source-derived records for the requested corpus scope",
    }


def _import_batch_payload(batch: ImportBatchImpact) -> dict[str, Any]:
    return {
        "import_batch_id": batch.import_batch_id,
        "imported_at": batch.imported_at,
        "source_artifact_identity": batch.source_artifact_identity,
        "source_pipeline_version": batch.source_pipeline_version,
        "validation_status": batch.validation_status,
        "raw_hash_validation_status": batch.raw_hash_validation_status,
        "record_counts": dict(batch.record_counts),
        "warnings": list(batch.warnings),
        "errors": list(batch.errors),
    }


def _reviewer_created_state_impact_payload(
    impact: ReviewerCreatedStateImpact,
) -> dict[str, Any]:
    return {
        "persistence_implemented": impact.persistence_implemented,
        "selected_handling_mode": impact.selected_handling_mode,
        "handling_options": list(impact.handling_options),
        "affected_state_categories": list(impact.affected_state_categories),
        "current_state_count": impact.current_state_count,
        "planning_note": impact.planning_note,
    }


def _import_batch_impact(row: RowMapping) -> ImportBatchImpact:
    return ImportBatchImpact(
        import_batch_id=_string_value(row, "import_batch_id"),
        imported_at=_string_value(row, "imported_at"),
        source_artifact_identity=_string_value(row, "source_artifact_identity"),
        source_pipeline_version=_optional_string_value(row, "source_pipeline_version"),
        validation_status=_string_value(row, "validation_status"),
        raw_hash_validation_status=_string_value(row, "raw_hash_validation_status"),
        record_counts=_int_mapping_value(row, "record_counts"),
        warnings=_string_tuple_value(row, "warnings"),
        errors=_string_tuple_value(row, "errors"),
    )


def _entity_type(row: RowMapping) -> SourceDerivedEntityType:
    value = _string_value(row, "entity_type")
    if value == "facility":
        return "facility"
    if value == "source_document":
        return "source_document"
    if value == "complaint":
        return "complaint"
    if value == "allegation":
        return "allegation"
    if value == "event":
        return "event"
    if value == "extraction_audit":
        return "extraction_audit"
    raise ValueError(f"Unknown source-derived entity type: {value}")


def _string_value(row: RowMapping, key: str) -> str:
    value = row[key]
    if not isinstance(value, str):
        raise TypeError(f"Expected {key} to be a string.")
    return value


def _optional_string_value(row: RowMapping, key: str) -> str | None:
    value = row[key]
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"Expected {key} to be a string or null.")
    return value


def _int_value(row: RowMapping, key: str) -> int:
    value = row[key]
    if not isinstance(value, int):
        raise TypeError(f"Expected {key} to be an integer.")
    return value


def _int_mapping_value(row: RowMapping, key: str) -> Mapping[str, int]:
    value = row[key]
    if not isinstance(value, Mapping):
        raise TypeError(f"Expected {key} to be an object.")
    counts: dict[str, int] = {}
    for count_key, count_value in value.items():
        if not isinstance(count_key, str) or not isinstance(count_value, int):
            raise TypeError(f"Expected {key} to map strings to integers.")
        counts[count_key] = count_value
    return counts


def _string_tuple_value(row: RowMapping, key: str) -> tuple[str, ...]:
    value = row[key]
    if not isinstance(value, list):
        raise TypeError(f"Expected {key} to be a list.")
    strings: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise TypeError(f"Expected {key} to contain strings.")
        strings.append(item)
    return tuple(strings)


def _json_response(status: int, payload: Mapping[str, Any]) -> tuple[int, str, bytes]:
    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    return status, "application/json; charset=utf-8", body


def _json_error(status: int, code: str, message: str) -> tuple[int, str, bytes]:
    return _json_response(status, {"error": {"code": code, "message": message}})