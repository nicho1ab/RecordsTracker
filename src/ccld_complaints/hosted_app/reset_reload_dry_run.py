from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from sqlalchemy import JSON, Boolean, CheckConstraint, Column, String, Table, Text, func, select
from sqlalchemy.engine import Connection, RowMapping

from ccld_complaints.hosted_app.audit_events import hosted_audit_events
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
    hosted_seeded_import_metadata,
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
ResetReloadRequestedOperationMode = Literal["dry_run"]

hosted_reset_reload_planning_metadata = Table(
    "hosted_reset_reload_planning_metadata",
    hosted_seeded_import_metadata,
    Column("planning_record_id", String(96), primary_key=True),
    Column("generated_at", String(40), nullable=False),
    Column("operation", String(80), nullable=False),
    Column("requested_operation_mode", String(32), nullable=False),
    Column("source_scope_type", String(32), nullable=False),
    Column("source_scope_id", String(96), nullable=False),
    Column("reviewer_state_handling_mode", String(16), nullable=False),
    Column("actor_provider_subject", Text, nullable=False),
    Column("actor_provider_issuer", Text, nullable=False),
    Column("actor_display_name", Text, nullable=True),
    Column("actor_category", String(32), nullable=False),
    Column("authorization_permission", String(64), nullable=False),
    Column("source_derived_summary", JSON, nullable=False),
    Column("reviewer_created_state_summary", JSON, nullable=False),
    Column("audit_event_summary", JSON, nullable=False),
    Column("validation_summary", JSON, nullable=False),
    Column("planning_context", JSON, nullable=False),
    Column("future_execution_permissions", JSON, nullable=False),
    Column("deferred_actions", JSON, nullable=False),
    Column("data_mutations_performed", Boolean, nullable=False),
    CheckConstraint(
        "operation = 'seeded_corpus_reset_reload_dry_run'",
        name="ck_hosted_reset_reload_planning_metadata_operation",
    ),
    CheckConstraint(
        "requested_operation_mode = 'dry_run'",
        name="ck_hosted_reset_reload_planning_metadata_requested_mode",
    ),
    CheckConstraint(
        "reviewer_state_handling_mode IN ('preserve', 'archive', 'clear')",
        name="ck_hosted_reset_reload_planning_metadata_state_mode",
    ),
    CheckConstraint(
        "authorization_permission = 'import_reload'",
        name="ck_hosted_reset_reload_planning_metadata_permission",
    ),
)

SECRET_CONTEXT_MARKERS = (
    "authorization",
    "client_secret",
    "connection string",
    "connection_string",
    "cookie",
    "password",
    "private_header",
    "private header",
    "secret",
    "token",
)


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
class AuditEventImpact:
    persistence_implemented: bool
    current_event_count: int
    planning_note: str


@dataclass(frozen=True)
class SeededCorpusResetReloadDryRunPlan:
    dry_run: bool
    operation: str
    scope: HostedAccessScope
    authorized: AuthorizationDecision
    source_derived_impact: SourceDerivedImpact
    reviewer_created_state_impact: ReviewerCreatedStateImpact
    audit_event_impact: AuditEventImpact
    future_execution_permissions: tuple[str, ...]
    validation_requirements: tuple[str, ...]
    audit_requirements: tuple[str, ...]
    deferred_actions: tuple[str, ...]
    data_mutations_performed: bool = False


@dataclass(frozen=True)
class ResetReloadPlanningMetadataRead:
    planning_record_id: str
    generated_at: str
    operation: str
    requested_operation_mode: ResetReloadRequestedOperationMode
    scope: HostedAccessScope
    reviewer_state_handling_mode: ReviewerStateHandlingMode
    actor_provider_subject: str
    actor_provider_issuer: str
    actor_display_name: str | None
    actor_category: str
    authorization_permission: str
    source_derived_summary: Mapping[str, Any]
    reviewer_created_state_summary: Mapping[str, Any]
    audit_event_summary: Mapping[str, Any]
    validation_summary: Mapping[str, Any]
    planning_context: Mapping[str, Any]
    future_execution_permissions: tuple[str, ...]
    deferred_actions: tuple[str, ...]
    data_mutations_performed: bool


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
        persist_planning_metadata = _persist_planning_metadata(query_values)
        plan = plan_seeded_corpus_reset_reload_dry_run(
            context.connection,
            context.actor,
            scope=context.scope,
            reviewer_state_mode=reviewer_state_mode,
        )
        persisted_metadata = None
        if persist_planning_metadata:
            persisted_metadata = persist_seeded_corpus_reset_reload_planning_metadata(
                context.connection,
                plan,
                planning_context={
                    "persisted_from": "reset_reload_dry_run_route",
                    "route_path": parsed_url.path,
                },
            )
        return _json_response(200, _plan_payload(plan, persisted_metadata))
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
            reviewer_state_mode,
        ),
        audit_event_impact=_audit_event_impact(connection, scope),
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
            "this dry-run counts existing audit scaffold rows but does not persist "
            "a new audit event",
        ),
        deferred_actions=(
            "delete source-derived records",
            "truncate source-derived tables",
            "overwrite source-derived records",
            "archive reviewer-created state",
            "clear reviewer-created state",
            "import or reload seeded corpus artifacts",
            "run live crawling or hosted connector execution",
            "persist audit events for reset/reload planning",
            "execute reset/reload from persisted operational metadata",
        ),
    )


def create_seeded_corpus_reset_reload_planning_metadata(
    connection: Connection,
    actor: AuthenticatedActor | None,
    *,
    scope: HostedAccessScope,
    reviewer_state_mode: ReviewerStateHandlingMode = DEFAULT_REVIEWER_STATE_HANDLING_MODE,
    planning_context: Mapping[str, Any] | None = None,
) -> ResetReloadPlanningMetadataRead:
    plan = plan_seeded_corpus_reset_reload_dry_run(
        connection,
        actor,
        scope=scope,
        reviewer_state_mode=reviewer_state_mode,
    )
    return persist_seeded_corpus_reset_reload_planning_metadata(
        connection,
        plan,
        planning_context={} if planning_context is None else planning_context,
    )


def persist_seeded_corpus_reset_reload_planning_metadata(
    connection: Connection,
    plan: SeededCorpusResetReloadDryRunPlan,
    *,
    planning_context: Mapping[str, Any],
) -> ResetReloadPlanningMetadataRead:
    _require_non_secret_mapping(planning_context, "planning_context")
    planning_record_id = f"reset-reload-plan:{uuid4().hex}"
    values = {
        "planning_record_id": planning_record_id,
        "generated_at": plan.authorized.authorized_at,
        "operation": plan.operation,
        "requested_operation_mode": "dry_run",
        "source_scope_type": plan.scope.scope_type,
        "source_scope_id": plan.scope.scope_id,
        "reviewer_state_handling_mode": (
            plan.reviewer_created_state_impact.selected_handling_mode
        ),
        "actor_provider_subject": plan.authorized.actor.provider_subject,
        "actor_provider_issuer": plan.authorized.actor.provider_issuer,
        "actor_display_name": plan.authorized.actor.display_name,
        "actor_category": plan.authorized.actor.actor_category,
        "authorization_permission": plan.authorized.permission,
        "source_derived_summary": _source_derived_impact_payload(
            plan.source_derived_impact
        ),
        "reviewer_created_state_summary": _reviewer_created_state_impact_payload(
            plan.reviewer_created_state_impact
        ),
        "audit_event_summary": _audit_event_impact_payload(plan.audit_event_impact),
        "validation_summary": {
            "validation_requirements": list(plan.validation_requirements),
            "audit_requirements": list(plan.audit_requirements),
        },
        "planning_context": dict(planning_context),
        "future_execution_permissions": list(plan.future_execution_permissions),
        "deferred_actions": list(plan.deferred_actions),
        "data_mutations_performed": plan.data_mutations_performed,
    }
    connection.execute(hosted_reset_reload_planning_metadata.insert().values(**values))
    return _planning_metadata_from_row(
        connection.execute(
            select(hosted_reset_reload_planning_metadata).where(
                hosted_reset_reload_planning_metadata.c.planning_record_id
                == planning_record_id
            )
        )
        .mappings()
        .one()
    )


def list_seeded_corpus_reset_reload_planning_metadata(
    connection: Connection,
    actor: AuthenticatedActor | None,
    *,
    scope: HostedAccessScope,
    reviewer_state_handling_mode: ReviewerStateHandlingMode | None = None,
    actor_provider_subject: str | None = None,
    requested_operation_mode: ResetReloadRequestedOperationMode | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[ResetReloadPlanningMetadataRead, ...]:
    if limit < 1:
        raise ValueError("Reset/reload planning metadata list limit must be at least 1.")
    if offset < 0:
        raise ValueError("Reset/reload planning metadata list offset must be at least 0.")
    if (
        reviewer_state_handling_mode is not None
        and reviewer_state_handling_mode not in REVIEWER_STATE_HANDLING_OPTIONS
    ):
        raise ValueError("Reset/reload reviewer state handling mode is not supported.")
    if requested_operation_mode is not None and requested_operation_mode != "dry_run":
        raise ValueError("Reset/reload requested operation mode is not supported.")
    require_permission(
        actor,
        permission=IMPORT_RELOAD_PERMISSION,
        scope=scope,
        target=AuthorizationTarget("import_batch", scope.scope_id),
    )
    query = (
        select(hosted_reset_reload_planning_metadata)
        .where(
            hosted_reset_reload_planning_metadata.c.source_scope_type == scope.scope_type,
            hosted_reset_reload_planning_metadata.c.source_scope_id == scope.scope_id,
        )
    )
    if reviewer_state_handling_mode is not None:
        query = query.where(
            hosted_reset_reload_planning_metadata.c.reviewer_state_handling_mode
            == reviewer_state_handling_mode
        )
    if actor_provider_subject is not None:
        query = query.where(
            hosted_reset_reload_planning_metadata.c.actor_provider_subject
            == actor_provider_subject
        )
    if requested_operation_mode is not None:
        query = query.where(
            hosted_reset_reload_planning_metadata.c.requested_operation_mode
            == requested_operation_mode
        )
    query = (
        query.order_by(
            hosted_reset_reload_planning_metadata.c.generated_at,
            hosted_reset_reload_planning_metadata.c.planning_record_id,
        )
        .limit(limit)
        .offset(offset)
    )
    return tuple(
        _planning_metadata_from_row(row)
        for row in connection.execute(query).mappings().all()
    )


def get_seeded_corpus_reset_reload_planning_metadata(
    connection: Connection,
    actor: AuthenticatedActor | None,
    *,
    scope: HostedAccessScope,
    planning_record_id: str,
) -> ResetReloadPlanningMetadataRead | None:
    if not planning_record_id.strip():
        raise ValueError("Reset/reload planning metadata ID is required.")
    require_permission(
        actor,
        permission=IMPORT_RELOAD_PERMISSION,
        scope=scope,
        target=AuthorizationTarget("import_batch", planning_record_id),
    )
    row = (
        connection.execute(
            select(hosted_reset_reload_planning_metadata).where(
                hosted_reset_reload_planning_metadata.c.source_scope_type
                == scope.scope_type,
                hosted_reset_reload_planning_metadata.c.source_scope_id == scope.scope_id,
                hosted_reset_reload_planning_metadata.c.planning_record_id
                == planning_record_id,
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None
    return _planning_metadata_from_row(row)


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
            "or execute reset/reload."
        ),
    )


def _audit_event_impact(
    connection: Connection,
    scope: HostedAccessScope,
) -> AuditEventImpact:
    current_event_count = connection.execute(
        select(func.count()).select_from(hosted_audit_events).where(
            hosted_audit_events.c.scope_type == scope.scope_type,
            hosted_audit_events.c.scope_id == scope.scope_id,
        )
    ).scalar_one()
    return AuditEventImpact(
        persistence_implemented=True,
        current_event_count=current_event_count,
        planning_note=(
            "A narrow audit event scaffold table is implemented for successful "
            "reviewer-created state scaffold writes only; this dry-run reports "
            "scoped rows but does not create, archive, clear, or export audit events."
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


def _persist_planning_metadata(
    query_values: Mapping[str, list[str]],
) -> bool:
    raw_value = _optional_query_value(query_values, "persist_planning_metadata")
    if raw_value is None:
        return False
    if raw_value == "true":
        return True
    if raw_value == "false":
        return False
    raise ValueError("persist_planning_metadata must be 'true' or 'false'.")


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


def _plan_payload(
    plan: SeededCorpusResetReloadDryRunPlan,
    persisted_metadata: ResetReloadPlanningMetadataRead | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
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
        "audit_event_impact": _audit_event_impact_payload(plan.audit_event_impact),
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
    if persisted_metadata is not None:
        payload["operational_metadata"] = {
            "persisted": True,
            "planning_record_id": persisted_metadata.planning_record_id,
            "generated_at": persisted_metadata.generated_at,
            "requested_operation_mode": persisted_metadata.requested_operation_mode,
            "reviewer_state_handling_mode": (
                persisted_metadata.reviewer_state_handling_mode
            ),
        }
    return payload


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


def _audit_event_impact_payload(impact: AuditEventImpact) -> dict[str, Any]:
    return {
        "persistence_implemented": impact.persistence_implemented,
        "current_event_count": impact.current_event_count,
        "planning_note": impact.planning_note,
    }


def _planning_metadata_from_row(row: RowMapping) -> ResetReloadPlanningMetadataRead:
    return ResetReloadPlanningMetadataRead(
        planning_record_id=_string_value(row, "planning_record_id"),
        generated_at=_string_value(row, "generated_at"),
        operation=_string_value(row, "operation"),
        requested_operation_mode=_requested_operation_mode(row),
        scope=HostedAccessScope(
            _scope_type(row),
            _string_value(row, "source_scope_id"),
        ),
        reviewer_state_handling_mode=_planning_reviewer_state_mode(row),
        actor_provider_subject=_string_value(row, "actor_provider_subject"),
        actor_provider_issuer=_string_value(row, "actor_provider_issuer"),
        actor_display_name=_optional_string_value(row, "actor_display_name"),
        actor_category=_string_value(row, "actor_category"),
        authorization_permission=_string_value(row, "authorization_permission"),
        source_derived_summary=_mapping_value(row, "source_derived_summary"),
        reviewer_created_state_summary=_mapping_value(
            row, "reviewer_created_state_summary"
        ),
        audit_event_summary=_mapping_value(row, "audit_event_summary"),
        validation_summary=_mapping_value(row, "validation_summary"),
        planning_context=_mapping_value(row, "planning_context"),
        future_execution_permissions=_string_tuple_value(
            row, "future_execution_permissions"
        ),
        deferred_actions=_string_tuple_value(row, "deferred_actions"),
        data_mutations_performed=_bool_value(row, "data_mutations_performed"),
    )


def _requested_operation_mode(row: RowMapping) -> ResetReloadRequestedOperationMode:
    value = _string_value(row, "requested_operation_mode")
    if value == "dry_run":
        return "dry_run"
    raise ValueError(f"Unknown reset/reload requested operation mode: {value}")


def _planning_reviewer_state_mode(row: RowMapping) -> ReviewerStateHandlingMode:
    value = _string_value(row, "reviewer_state_handling_mode")
    if value == "preserve":
        return "preserve"
    if value == "archive":
        return "archive"
    if value == "clear":
        return "clear"
    raise ValueError(f"Unknown reset/reload reviewer state handling mode: {value}")


def _scope_type(row: RowMapping) -> Any:
    return _string_value(row, "source_scope_type")


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


def _mapping_value(row: RowMapping, key: str) -> Mapping[str, Any]:
    value = row[key]
    if not isinstance(value, Mapping):
        raise TypeError(f"Expected {key} to be an object.")
    return dict(value)


def _bool_value(row: RowMapping, key: str) -> bool:
    value = row[key]
    if not isinstance(value, bool):
        raise TypeError(f"Expected {key} to be a boolean.")
    return value


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


def _require_non_secret_mapping(value: Mapping[str, Any], field_name: str) -> None:
    for context_key, context_value in value.items():
        _require_non_secret_text(str(context_key), field_name)
        _require_non_secret_value(context_value, field_name)


def _require_non_secret_value(value: object, field_name: str) -> None:
    if isinstance(value, str):
        _require_non_secret_text(value, field_name)
    elif isinstance(value, Mapping):
        _require_non_secret_mapping(value, field_name)
    elif isinstance(value, list | tuple):
        for item in value:
            _require_non_secret_value(item, field_name)


def _require_non_secret_text(value: str, field_name: str) -> None:
    normalized = value.casefold()
    if any(marker in normalized for marker in SECRET_CONTEXT_MARKERS):
        raise ValueError(f"Reset/reload {field_name} must not include secret-like data.")


def _json_response(status: int, payload: Mapping[str, Any]) -> tuple[int, str, bytes]:
    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    return status, "application/json; charset=utf-8", body


def _json_error(status: int, code: str, message: str) -> tuple[int, str, bytes]:
    return _json_response(status, {"error": {"code": code, "message": message}})