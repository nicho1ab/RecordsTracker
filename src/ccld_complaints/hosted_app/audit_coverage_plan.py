from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.engine import Connection

from ccld_complaints.hosted_app.audit_events import (
    HOSTED_AUDIT_ACTIONS,
    HOSTED_AUDIT_TARGET_TYPES,
    hosted_audit_events,
)
from ccld_complaints.hosted_app.auth import (
    AUDIT_READ_PERMISSION,
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

AUDIT_COVERAGE_PLAN_API_PATH = "/api/audit/coverage-plan"
AUDIT_COVERAGE_PLAN_OPERATION = "audit_coverage_plan"


@dataclass(frozen=True)
class AuditCoveragePlanContext:
    connection: Connection
    actor: AuthenticatedActor | None
    scope: HostedAccessScope


@dataclass(frozen=True)
class AuditCoveragePlanStep:
    sequence: int
    step_id: str
    category: str
    summary: str
    inputs: Mapping[str, Any]


@dataclass(frozen=True)
class AuditCoveragePlan:
    operation: str
    scope: HostedAccessScope
    authorized: AuthorizationDecision
    current_coverage: Mapping[str, Any]
    deferred_categories: tuple[Mapping[str, Any], ...]
    plan_steps: tuple[AuditCoveragePlanStep, ...]
    data_mutations_performed: bool = False
    persistence_performed: bool = False
    audit_rows_created: int = 0


def route_audit_coverage_plan_response(
    path: str,
    context: AuditCoveragePlanContext | None,
) -> tuple[int, str, bytes]:
    parsed_url = urlparse(path)
    try:
        if context is None:
            return _json_error(
                503,
                "audit_coverage_plan_context_required",
                "Local/test audit coverage plan context is not configured.",
            )
        if parsed_url.path != AUDIT_COVERAGE_PLAN_API_PATH:
            return _json_error(
                404,
                "audit_coverage_plan_route_not_found",
                "Audit coverage plan route not found.",
            )
        plan = plan_audit_coverage(
            context.connection,
            context.actor,
            scope=context.scope,
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


def plan_audit_coverage(
    connection: Connection,
    actor: AuthenticatedActor | None,
    *,
    scope: HostedAccessScope,
) -> AuditCoveragePlan:
    authorized = require_permission(
        actor,
        permission=AUDIT_READ_PERMISSION,
        scope=scope,
        target=AuthorizationTarget("audit_event", scope.scope_id),
    )
    current_coverage = _current_coverage(connection, scope)
    deferred_categories = _deferred_categories()
    return AuditCoveragePlan(
        operation=AUDIT_COVERAGE_PLAN_OPERATION,
        scope=scope,
        authorized=authorized,
        current_coverage=current_coverage,
        deferred_categories=deferred_categories,
        plan_steps=_plan_steps(current_coverage, deferred_categories),
    )


def _current_coverage(
    connection: Connection,
    scope: HostedAccessScope,
) -> dict[str, Any]:
    current_event_count = connection.execute(
        select(func.count()).select_from(hosted_audit_events).where(
            hosted_audit_events.c.scope_type == scope.scope_type,
            hosted_audit_events.c.scope_id == scope.scope_id,
        )
    ).scalar_one()
    return {
        "implemented_event_sources": [
            {
                "source": "reviewer_created_state_scaffold_writes",
                "actions": list(HOSTED_AUDIT_ACTIONS),
                "target_types": list(HOSTED_AUDIT_TARGET_TYPES),
                "covered_payload_kinds": [
                    "review_item_state_scaffold",
                    "reviewer_note_scaffold",
                    "reviewer_status_scaffold",
                ],
            }
        ],
        "current_scoped_audit_event_count": current_event_count,
        "audit_history_read_seams": [
            {
                "route": "/api/audit-events",
                "supports_list": True,
                "supports_fetch_by_id": True,
                "supports_schema_backed_filters": True,
                "required_permission": AUDIT_READ_PERMISSION,
            }
        ],
        "actor_attribution_model": {
            "captures_provider_subject": True,
            "captures_provider_issuer": True,
            "captures_display_label": True,
            "captures_actor_category": True,
            "captures_permission_used": True,
            "captures_scope": True,
            "captures_generated_timestamp": True,
        },
        "target_context_model": {
            "captures_reviewer_created_target": True,
            "captures_source_record_key": True,
            "captures_source_entity_type": True,
            "captures_stable_source_identity": True,
            "captures_source_document_id": True,
        },
        "metadata_rules": {
            "non_secret_metadata_only": True,
            "raw_provider_claims_deferred": True,
            "private_headers_deferred": True,
            "credential_storage_deferred": True,
        },
    }


def _deferred_categories() -> tuple[Mapping[str, Any], ...]:
    return (
        {
            "category": "future provider login/auth events",
            "examples": [
                "login success or failure where appropriate",
                "account disablement or revocation observation",
                "access lifecycle review",
            ],
        },
        {
            "category": "future provider claim/role/scope mapping events",
            "examples": [
                "role assignment changes",
                "project or corpus scope assignment changes",
                "access review outcomes",
            ],
        },
        {
            "category": "future reset/reload execution events",
            "examples": [
                "seeded corpus reload request and result",
                "reset approval where applicable",
                "rollback or recovery note",
            ],
        },
        {
            "category": "future export packet generation events",
            "examples": [
                "packet creation or update",
                "item inclusion or exclusion",
                "export generation or delivery event where observable",
            ],
        },
        {
            "category": "future annotation/correction/status-transition events",
            "examples": [
                "annotation update or archival",
                "proposed correction lifecycle",
                "stateful review status transition beyond scaffold status writes",
            ],
        },
        {
            "category": "future administrative configuration events",
            "examples": [
                "tester access approval",
                "operator access review",
                "system identity lifecycle change",
            ],
        },
        {
            "category": "future retention/disposition events",
            "examples": [
                "retention review",
                "archival decision",
                "disposition or recovery limitation note",
            ],
        },
    )


def _plan_steps(
    current_coverage: Mapping[str, Any],
    deferred_categories: tuple[Mapping[str, Any], ...],
) -> tuple[AuditCoveragePlanStep, ...]:
    return (
        AuditCoveragePlanStep(
            sequence=1,
            step_id="implemented_audit_event_sources",
            category="implemented audit event sources",
            summary=(
                "Summarize the narrow local/test audit source currently implemented "
                "for successful reviewer-created state scaffold writes."
            ),
            inputs={
                "implemented_event_sources": current_coverage[
                    "implemented_event_sources"
                ],
                "current_scoped_audit_event_count": current_coverage[
                    "current_scoped_audit_event_count"
                ],
            },
        ),
        AuditCoveragePlanStep(
            sequence=2,
            step_id="current_audit_read_history_seams",
            category="current audit read/history seams",
            summary=(
                "Describe local/test audit history read seams and their required "
                "permission without mutating audit rows."
            ),
            inputs={
                "audit_history_read_seams": current_coverage[
                    "audit_history_read_seams"
                ],
            },
        ),
        AuditCoveragePlanStep(
            sequence=3,
            step_id="actor_attribution_model",
            category="actor attribution model",
            summary="Summarize actor identity fields already captured by scaffold audit rows.",
            inputs=current_coverage["actor_attribution_model"],
        ),
        AuditCoveragePlanStep(
            sequence=4,
            step_id="target_source_context_model",
            category="target/source-derived context model",
            summary=(
                "Summarize current target and source-derived context captured by "
                "scaffold audit rows."
            ),
            inputs=current_coverage["target_context_model"],
        ),
        AuditCoveragePlanStep(
            sequence=5,
            step_id="no_secret_metadata_rules",
            category="no-secret metadata rules",
            summary=(
                "Keep audit metadata concise and non-secret, with raw claims and "
                "credential-bearing material deferred."
            ),
            inputs=current_coverage["metadata_rules"],
        ),
        AuditCoveragePlanStep(
            sequence=6,
            step_id="deferred_audit_event_categories",
            category="deferred audit event categories",
            summary=(
                "Identify hosted tester MVP audit categories from ADR-0013 and "
                "ADR-0014 that remain deferred."
            ),
            inputs={"deferred_categories": list(deferred_categories)},
        ),
        AuditCoveragePlanStep(
            sequence=7,
            step_id="future_implementation_order",
            category="future implementation order",
            summary=(
                "Order future audit coverage work by prerequisite boundaries rather "
                "than adding broad audit execution in this branch."
            ),
            inputs={
                "ordered_focus": [
                    "provider and access lifecycle audit design",
                    "stateful reviewer workflow audit coverage",
                    "reset/reload execution audit coverage",
                    "export packet audit coverage",
                    "retention and disposition audit coverage",
                ],
            },
        ),
        AuditCoveragePlanStep(
            sequence=8,
            step_id="non_goals_for_this_branch",
            category="non-goals for this branch",
            summary=(
                "Confirm this planning seam does not add audit writes, schemas, UI, "
                "exports, production auth, or operational execution."
            ),
            inputs={
                "creates_audit_rows": False,
                "persists_planning_records": False,
                "adds_schema_or_migration": False,
                "implements_audit_ui_or_export": False,
                "implements_production_auth": False,
                "executes_reset_reload": False,
            },
        ),
    )


def _plan_payload(plan: AuditCoveragePlan) -> dict[str, Any]:
    return {
        "audit_coverage_plan": True,
        "operation": plan.operation,
        "scope": {
            "scope_type": plan.scope.scope_type,
            "scope_id": plan.scope.scope_id,
        },
        "authorization": _authorization_payload(plan.authorized),
        "current_coverage": dict(plan.current_coverage),
        "deferred_audit_event_categories": [
            dict(category) for category in plan.deferred_categories
        ],
        "readiness_plan": [_step_payload(step) for step in plan.plan_steps],
        "safety": {
            "data_mutations_performed": plan.data_mutations_performed,
            "persistence_performed": plan.persistence_performed,
            "audit_rows_created": plan.audit_rows_created,
            "source_derived_rows_mutated": 0,
            "reviewer_created_state_rows_mutated": 0,
            "audit_event_rows_mutated": 0,
            "import_rows_mutated": 0,
            "operational_rows_mutated": 0,
            "auth_related_rows_mutated": 0,
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


def _step_payload(step: AuditCoveragePlanStep) -> dict[str, Any]:
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