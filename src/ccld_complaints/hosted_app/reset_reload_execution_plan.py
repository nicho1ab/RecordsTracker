from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import parse_qs, urlparse

from sqlalchemy import func, select
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
    DEFAULT_REVIEWER_STATE_HANDLING_MODE,
    REVIEWER_STATE_HANDLING_OPTIONS,
    ResetReloadPlanningMetadataRead,
    ReviewerStateHandlingMode,
    SeededCorpusResetReloadDryRunPlan,
    hosted_reset_reload_planning_metadata,
    persist_seeded_corpus_reset_reload_planning_metadata,
    plan_seeded_corpus_reset_reload_dry_run,
)

SEEDED_CORPUS_RESET_RELOAD_EXECUTION_PLAN_API_PATH = (
    "/api/operations/seeded-corpus-reset-reload/execution-plan"
)
ExecutionPlanMode = Literal["bounded_non_destructive_plan"]
DEFAULT_EXECUTION_PLAN_MODE: ExecutionPlanMode = "bounded_non_destructive_plan"


@dataclass(frozen=True)
class SeededCorpusResetReloadExecutionPlanContext:
    connection: Connection
    actor: AuthenticatedActor | None
    scope: HostedAccessScope


@dataclass(frozen=True)
class ResetReloadActionPlanStep:
    sequence: int
    step_id: str
    category: str
    summary: str
    inputs: Mapping[str, Any]
    data_mutations_performed: bool = False
    destructive_action_deferred: bool = True


@dataclass(frozen=True)
class SeededCorpusResetReloadExecutionPlan:
    execution_plan_mode: ExecutionPlanMode
    operation: str
    scope: HostedAccessScope
    dry_run_plan: SeededCorpusResetReloadDryRunPlan
    existing_planning_metadata_context: Mapping[str, Any]
    action_plan: tuple[ResetReloadActionPlanStep, ...]
    data_mutations_performed: bool = False


def route_seeded_corpus_reset_reload_execution_plan_response(
    path: str,
    context: SeededCorpusResetReloadExecutionPlanContext | None,
) -> tuple[int, str, bytes]:
    parsed_url = urlparse(path)
    query_values = parse_qs(parsed_url.query, keep_blank_values=True)
    try:
        if context is None:
            return _json_error(
                503,
                "reset_reload_execution_plan_context_required",
                "Local/test reset/reload execution-plan context is not configured.",
            )
        if parsed_url.path != SEEDED_CORPUS_RESET_RELOAD_EXECUTION_PLAN_API_PATH:
            return _json_error(
                404,
                "reset_reload_execution_plan_route_not_found",
                "Reset/reload execution-plan route not found.",
            )
        execution_plan_mode = _execution_plan_mode(query_values)
        reviewer_state_mode = _reviewer_state_mode(query_values)
        persist_planning_metadata = _persist_planning_metadata(query_values)
        execution_plan = plan_seeded_corpus_reset_reload_execution_plan(
            context.connection,
            context.actor,
            scope=context.scope,
            execution_plan_mode=execution_plan_mode,
            reviewer_state_mode=reviewer_state_mode,
        )
        persisted_metadata = None
        if persist_planning_metadata:
            persisted_metadata = persist_seeded_corpus_reset_reload_execution_plan(
                context.connection,
                execution_plan,
                route_path=parsed_url.path,
            )
        return _json_response(
            200,
            _execution_plan_payload(execution_plan, persisted_metadata),
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


def plan_seeded_corpus_reset_reload_execution_plan(
    connection: Connection,
    actor: AuthenticatedActor | None,
    *,
    scope: HostedAccessScope,
    execution_plan_mode: ExecutionPlanMode = DEFAULT_EXECUTION_PLAN_MODE,
    reviewer_state_mode: ReviewerStateHandlingMode = DEFAULT_REVIEWER_STATE_HANDLING_MODE,
) -> SeededCorpusResetReloadExecutionPlan:
    if execution_plan_mode != DEFAULT_EXECUTION_PLAN_MODE:
        raise ValueError("execution_plan_mode must be 'bounded_non_destructive_plan'.")
    dry_run_plan = plan_seeded_corpus_reset_reload_dry_run(
        connection,
        actor,
        scope=scope,
        reviewer_state_mode=reviewer_state_mode,
    )
    existing_metadata_context = _existing_planning_metadata_context(connection, scope)
    return SeededCorpusResetReloadExecutionPlan(
        execution_plan_mode=execution_plan_mode,
        operation="seeded_corpus_reset_reload_execution_plan",
        scope=scope,
        dry_run_plan=dry_run_plan,
        existing_planning_metadata_context=existing_metadata_context,
        action_plan=_action_plan_steps(
            dry_run_plan,
            execution_plan_mode=execution_plan_mode,
            existing_planning_metadata_context=existing_metadata_context,
        ),
    )


def persist_seeded_corpus_reset_reload_execution_plan(
    connection: Connection,
    execution_plan: SeededCorpusResetReloadExecutionPlan,
    *,
    route_path: str,
) -> ResetReloadPlanningMetadataRead:
    return persist_seeded_corpus_reset_reload_planning_metadata(
        connection,
        execution_plan.dry_run_plan,
        planning_context={
            "planning_artifact_kind": "seeded_corpus_reset_reload_execution_plan",
            "persisted_from": "reset_reload_execution_plan_route",
            "route_path": route_path,
            "execution_plan_mode": execution_plan.execution_plan_mode,
            "execution_plan_operation": execution_plan.operation,
            "action_plan_step_ids": [step.step_id for step in execution_plan.action_plan],
            "data_mutations_performed": False,
            "reset_reload_executed": False,
        },
    )


def _existing_planning_metadata_context(
    connection: Connection,
    scope: HostedAccessScope,
) -> dict[str, Any]:
    count = connection.execute(
        select(func.count()).select_from(hosted_reset_reload_planning_metadata).where(
            hosted_reset_reload_planning_metadata.c.source_scope_type == scope.scope_type,
            hosted_reset_reload_planning_metadata.c.source_scope_id == scope.scope_id,
        )
    ).scalar_one()
    latest_row = (
        connection.execute(
            select(
                hosted_reset_reload_planning_metadata.c.planning_record_id,
                hosted_reset_reload_planning_metadata.c.generated_at,
                hosted_reset_reload_planning_metadata.c.operation,
                hosted_reset_reload_planning_metadata.c.requested_operation_mode,
                hosted_reset_reload_planning_metadata.c.reviewer_state_handling_mode,
                hosted_reset_reload_planning_metadata.c.data_mutations_performed,
            )
            .where(
                hosted_reset_reload_planning_metadata.c.source_scope_type
                == scope.scope_type,
                hosted_reset_reload_planning_metadata.c.source_scope_id == scope.scope_id,
            )
            .order_by(
                hosted_reset_reload_planning_metadata.c.generated_at.desc(),
                hosted_reset_reload_planning_metadata.c.planning_record_id.desc(),
            )
        )
        .mappings()
        .first()
    )
    latest_record = None
    if latest_row is not None:
        latest_record = {
            "planning_record_id": latest_row["planning_record_id"],
            "generated_at": latest_row["generated_at"],
            "operation": latest_row["operation"],
            "requested_operation_mode": latest_row["requested_operation_mode"],
            "reviewer_state_handling_mode": latest_row[
                "reviewer_state_handling_mode"
            ],
            "data_mutations_performed": latest_row["data_mutations_performed"],
        }
    return {
        "existing_planning_record_count": count,
        "latest_planning_record": latest_record,
        "planning_metadata_rows_mutated_by_plan": 0,
    }


def _action_plan_steps(
    dry_run_plan: SeededCorpusResetReloadDryRunPlan,
    *,
    execution_plan_mode: ExecutionPlanMode,
    existing_planning_metadata_context: Mapping[str, Any],
) -> tuple[ResetReloadActionPlanStep, ...]:
    source_impact = dry_run_plan.source_derived_impact
    reviewer_impact = dry_run_plan.reviewer_created_state_impact
    audit_impact = dry_run_plan.audit_event_impact
    return (
        ResetReloadActionPlanStep(
            sequence=1,
            step_id="validate_requested_corpus_scope",
            category="validate requested corpus/scope",
            summary=(
                "Confirm the authenticated actor may plan reset/reload for the "
                "requested seeded corpus scope."
            ),
            inputs={
                "scope_type": dry_run_plan.scope.scope_type,
                "scope_id": dry_run_plan.scope.scope_id,
                "permission_used": dry_run_plan.authorized.permission,
                "execution_plan_mode": execution_plan_mode,
            },
        ),
        ResetReloadActionPlanStep(
            sequence=2,
            step_id="verify_source_derived_import_batch_readiness",
            category="verify source-derived import batch readiness",
            summary=(
                "Check existing seeded import batch metadata and validation status "
                "before any future reload."
            ),
            inputs={
                "existing_import_batch_count": source_impact.existing_import_batch_count,
                "import_batches": [
                    {
                        "import_batch_id": batch.import_batch_id,
                        "validation_status": batch.validation_status,
                        "raw_hash_validation_status": batch.raw_hash_validation_status,
                        "source_artifact_identity": batch.source_artifact_identity,
                    }
                    for batch in source_impact.import_batches
                ],
            },
        ),
        ResetReloadActionPlanStep(
            sequence=3,
            step_id="summarize_source_derived_records",
            category="summarize source-derived records",
            summary=(
                "Summarize scoped source-derived rows by entity without deleting, "
                "importing, reloading, or overwriting records."
            ),
            inputs={
                "existing_source_derived_record_count": (
                    source_impact.existing_source_derived_record_count
                ),
                "counts_by_entity": dict(source_impact.counts_by_entity),
            },
        ),
        ResetReloadActionPlanStep(
            sequence=4,
            step_id="summarize_reviewer_created_state_handling",
            category="summarize reviewer-created state handling option",
            summary=(
                "Record the selected future reviewer-created state handling option "
                "while leaving reviewer-created rows unchanged."
            ),
            inputs={
                "selected_handling_mode": reviewer_impact.selected_handling_mode,
                "handling_options": list(reviewer_impact.handling_options),
                "current_state_count": reviewer_impact.current_state_count,
                "affected_state_categories": list(reviewer_impact.affected_state_categories),
            },
        ),
        ResetReloadActionPlanStep(
            sequence=5,
            step_id="summarize_audit_expectations",
            category="summarize audit expectations",
            summary=(
                "Summarize existing scaffold audit rows and future audit requirements "
                "without creating reset/reload audit events."
            ),
            inputs={
                "current_event_count": audit_impact.current_event_count,
                "audit_requirements": list(dry_run_plan.audit_requirements),
            },
        ),
        ResetReloadActionPlanStep(
            sequence=6,
            step_id="summarize_operational_metadata_behavior",
            category="summarize operational metadata/planning record behavior",
            summary=(
                "Describe existing planning metadata and whether this request will "
                "persist one additional non-executing planning row."
            ),
            inputs={
                "existing_planning_metadata_context": dict(
                    existing_planning_metadata_context
                ),
                "optional_persistence_available": True,
                "persisted_rows_created_by_default": 0,
            },
            destructive_action_deferred=False,
        ),
        ResetReloadActionPlanStep(
            sequence=7,
            step_id="list_deferred_destructive_actions",
            category="list destructive actions still deferred",
            summary=(
                "List destructive or state-changing reset/reload actions that remain "
                "deferred and are not executed by this plan."
            ),
            inputs={
                "deferred_actions": list(dry_run_plan.deferred_actions),
                "future_execution_permissions": list(
                    dry_run_plan.future_execution_permissions
                ),
            },
        ),
    )


def _execution_plan_mode(
    query_values: Mapping[str, list[str]],
) -> ExecutionPlanMode:
    raw_mode = _optional_query_value(query_values, "execution_plan_mode")
    if raw_mode is None:
        return DEFAULT_EXECUTION_PLAN_MODE
    if raw_mode != DEFAULT_EXECUTION_PLAN_MODE:
        raise ValueError("execution_plan_mode must be 'bounded_non_destructive_plan'.")
    return "bounded_non_destructive_plan"


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


def _persist_planning_metadata(query_values: Mapping[str, list[str]]) -> bool:
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


def _execution_plan_payload(
    execution_plan: SeededCorpusResetReloadExecutionPlan,
    persisted_metadata: ResetReloadPlanningMetadataRead | None,
) -> dict[str, Any]:
    dry_run_plan = execution_plan.dry_run_plan
    payload: dict[str, Any] = {
        "execution_plan": True,
        "execution_plan_mode": execution_plan.execution_plan_mode,
        "operation": execution_plan.operation,
        "scope": {
            "scope_type": execution_plan.scope.scope_type,
            "scope_id": execution_plan.scope.scope_id,
        },
        "authorization": {
            "permission": dry_run_plan.authorized.permission,
            "authorized_at": dry_run_plan.authorized.authorized_at,
            "actor": {
                "actor_category": dry_run_plan.authorized.actor.actor_category,
                "account_status": dry_run_plan.authorized.actor.account_status,
                "roles": list(dry_run_plan.authorized.actor.roles),
            },
        },
        "source_derived_summary": {
            "existing_import_batch_count": (
                dry_run_plan.source_derived_impact.existing_import_batch_count
            ),
            "existing_source_derived_record_count": (
                dry_run_plan.source_derived_impact.existing_source_derived_record_count
            ),
            "counts_by_entity": dict(dry_run_plan.source_derived_impact.counts_by_entity),
            "import_batch_ids": [
                batch.import_batch_id
                for batch in dry_run_plan.source_derived_impact.import_batches
            ],
        },
        "reviewer_created_state_summary": {
            "selected_handling_mode": (
                dry_run_plan.reviewer_created_state_impact.selected_handling_mode
            ),
            "handling_options": list(
                dry_run_plan.reviewer_created_state_impact.handling_options
            ),
            "current_state_count": dry_run_plan.reviewer_created_state_impact.current_state_count,
        },
        "audit_event_summary": {
            "current_event_count": dry_run_plan.audit_event_impact.current_event_count,
            "planning_note": dry_run_plan.audit_event_impact.planning_note,
        },
        "operational_planning_metadata_summary": dict(
            execution_plan.existing_planning_metadata_context
        ),
        "action_plan": [_action_plan_step_payload(step) for step in execution_plan.action_plan],
        "deferred_actions": list(dry_run_plan.deferred_actions),
        "safety": {
            "data_mutations_performed": execution_plan.data_mutations_performed,
            "queries_only": persisted_metadata is None,
            "does_not_execute_reset_reload": True,
            "does_not_run_live_crawling_or_connectors": True,
            "source_derived_rows_mutated": 0,
            "reviewer_created_state_rows_mutated": 0,
            "audit_event_rows_mutated": 0,
            "operational_rows_mutated_except_optional_planning_metadata": (
                0 if persisted_metadata is None else 1
            ),
        },
    }
    if persisted_metadata is not None:
        payload["operational_metadata"] = {
            "persisted": True,
            "planning_record_id": persisted_metadata.planning_record_id,
            "generated_at": persisted_metadata.generated_at,
            "operation": persisted_metadata.operation,
            "requested_operation_mode": persisted_metadata.requested_operation_mode,
            "reviewer_state_handling_mode": (
                persisted_metadata.reviewer_state_handling_mode
            ),
            "data_mutations_performed": persisted_metadata.data_mutations_performed,
            "planning_artifact_kind": persisted_metadata.planning_context[
                "planning_artifact_kind"
            ],
        }
    return payload


def _action_plan_step_payload(step: ResetReloadActionPlanStep) -> dict[str, Any]:
    return {
        "sequence": step.sequence,
        "step_id": step.step_id,
        "category": step.category,
        "summary": step.summary,
        "inputs": dict(step.inputs),
        "data_mutations_performed": step.data_mutations_performed,
        "destructive_action_deferred": step.destructive_action_deferred,
    }


def _json_response(status: int, payload: Mapping[str, Any]) -> tuple[int, str, bytes]:
    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    return status, "application/json; charset=utf-8", body


def _json_error(status: int, code: str, message: str) -> tuple[int, str, bytes]:
    return _json_response(status, {"error": {"code": code, "message": message}})