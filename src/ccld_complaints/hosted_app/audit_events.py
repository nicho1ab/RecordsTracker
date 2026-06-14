from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, cast
from uuid import uuid4

from sqlalchemy import JSON, CheckConstraint, Column, ForeignKey, String, Table, Text, select
from sqlalchemy.engine import Connection, RowMapping

from ccld_complaints.hosted_app.auth import (
    AUDIT_READ_PERMISSION,
    AuthenticatedActor,
    AuthorizationDecision,
    AuthorizationTarget,
    HostedAccessScope,
    require_permission,
)
from ccld_complaints.hosted_app.seeded_import import hosted_seeded_import_metadata
from ccld_complaints.hosted_app.source_derived_reads import SourceDerivedRecordRead

HostedAuditAction = Literal["reviewer_created_state_scaffold.create"]
HostedAuditTargetType = Literal["reviewer_created_state"]

HOSTED_AUDIT_ACTIONS: tuple[HostedAuditAction, ...] = (
    "reviewer_created_state_scaffold.create",
)
HOSTED_AUDIT_TARGET_TYPES: tuple[HostedAuditTargetType, ...] = (
    "reviewer_created_state",
)

hosted_audit_events = Table(
    "hosted_audit_events",
    hosted_seeded_import_metadata,
    Column("audit_event_id", String(96), primary_key=True),
    Column("occurred_at", String(40), nullable=False),
    Column("actor_provider_subject", Text, nullable=False),
    Column("actor_provider_issuer", Text, nullable=False),
    Column("actor_display_name", Text, nullable=True),
    Column("actor_category", String(32), nullable=False),
    Column("authorization_permission", String(64), nullable=False),
    Column("scope_type", String(32), nullable=False),
    Column("scope_id", String(96), nullable=False),
    Column("action", String(80), nullable=False),
    Column("target_type", String(64), nullable=False),
    Column(
        "target_reviewer_state_id",
        String(96),
        ForeignKey("hosted_reviewer_created_state.reviewer_state_id"),
        nullable=False,
    ),
    Column("source_record_key", String(160), nullable=False),
    Column("source_entity_type", String(32), nullable=False),
    Column("source_stable_source_id", Text, nullable=False),
    Column("source_document_id", Text, nullable=False),
    Column("context_metadata", JSON, nullable=False),
    CheckConstraint(
        "action IN ('reviewer_created_state_scaffold.create')",
        name="ck_hosted_audit_events_action",
    ),
    CheckConstraint(
        "target_type IN ('reviewer_created_state')",
        name="ck_hosted_audit_events_target_type",
    ),
    CheckConstraint(
        "authorization_permission = 'reviewer_state_write'",
        name="ck_hosted_audit_events_reviewer_state_write_permission",
    ),
)


@dataclass(frozen=True)
class HostedAuditEventRead:
    audit_event_id: str
    occurred_at: str
    actor_provider_subject: str
    actor_provider_issuer: str
    actor_display_name: str | None
    actor_category: str
    authorization_permission: str
    scope: HostedAccessScope
    action: HostedAuditAction
    target_type: HostedAuditTargetType
    target_reviewer_state_id: str
    source_record_key: str
    source_entity_type: str
    source_stable_source_id: str
    source_document_id: str
    context_metadata: Mapping[str, Any]


def create_hosted_audit_event(
    connection: Connection,
    *,
    authorized: AuthorizationDecision,
    action: HostedAuditAction,
    target_type: HostedAuditTargetType,
    target_reviewer_state_id: str,
    source_record: SourceDerivedRecordRead,
    context_metadata: Mapping[str, Any],
) -> HostedAuditEventRead:
    if action not in HOSTED_AUDIT_ACTIONS:
        raise ValueError("Hosted audit action is not supported by this scaffold.")
    if target_type not in HOSTED_AUDIT_TARGET_TYPES:
        raise ValueError("Hosted audit target type is not supported by this scaffold.")
    if not target_reviewer_state_id.strip():
        raise ValueError("Hosted audit event target reviewer state ID is required.")
    if not context_metadata:
        raise ValueError("Hosted audit event context metadata must not be empty.")

    audit_event_id = f"audit-event:{uuid4().hex}"
    values = {
        "audit_event_id": audit_event_id,
        "occurred_at": authorized.authorized_at,
        "actor_provider_subject": authorized.actor.provider_subject,
        "actor_provider_issuer": authorized.actor.provider_issuer,
        "actor_display_name": authorized.actor.display_name,
        "actor_category": authorized.actor.actor_category,
        "authorization_permission": authorized.permission,
        "scope_type": authorized.scope.scope_type,
        "scope_id": authorized.scope.scope_id,
        "action": action,
        "target_type": target_type,
        "target_reviewer_state_id": target_reviewer_state_id,
        "source_record_key": source_record.source_record_key,
        "source_entity_type": source_record.entity_type,
        "source_stable_source_id": source_record.stable_source_id,
        "source_document_id": source_record.source_document_id,
        "context_metadata": dict(context_metadata),
    }
    connection.execute(hosted_audit_events.insert().values(**values))
    return _read_model_from_row(
        connection.execute(
            select(hosted_audit_events).where(
                hosted_audit_events.c.audit_event_id == audit_event_id
            )
        )
        .mappings()
        .one()
    )


def list_hosted_audit_events_scaffold(
    connection: Connection,
    actor: AuthenticatedActor | None,
    *,
    scope: HostedAccessScope,
    target_reviewer_state_id: str | None = None,
    source_record_key: str | None = None,
    action: HostedAuditAction | None = None,
    actor_provider_subject: str | None = None,
    source_entity_type: str | None = None,
    source_stable_source_id: str | None = None,
    source_document_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[HostedAuditEventRead, ...]:
    if limit < 1:
        raise ValueError("Hosted audit event list limit must be at least 1.")
    if offset < 0:
        raise ValueError("Hosted audit event list offset must be at least 0.")
    if action is not None and action not in HOSTED_AUDIT_ACTIONS:
        raise ValueError("Hosted audit event action is not supported by this scaffold.")
    require_permission(
        actor,
        permission=AUDIT_READ_PERMISSION,
        scope=scope,
        target=AuthorizationTarget("audit_event", scope.scope_id),
    )

    query = select(hosted_audit_events).where(
        hosted_audit_events.c.scope_type == scope.scope_type,
        hosted_audit_events.c.scope_id == scope.scope_id,
    )
    if target_reviewer_state_id is not None:
        query = query.where(
            hosted_audit_events.c.target_reviewer_state_id == target_reviewer_state_id
        )
    if source_record_key is not None:
        query = query.where(hosted_audit_events.c.source_record_key == source_record_key)
    if action is not None:
        query = query.where(hosted_audit_events.c.action == action)
    if actor_provider_subject is not None:
        query = query.where(
            hosted_audit_events.c.actor_provider_subject == actor_provider_subject
        )
    if source_entity_type is not None:
        query = query.where(hosted_audit_events.c.source_entity_type == source_entity_type)
    if source_stable_source_id is not None:
        query = query.where(
            hosted_audit_events.c.source_stable_source_id == source_stable_source_id
        )
    if source_document_id is not None:
        query = query.where(hosted_audit_events.c.source_document_id == source_document_id)
    query = (
        query.order_by(
            hosted_audit_events.c.occurred_at,
            hosted_audit_events.c.audit_event_id,
        )
        .limit(limit)
        .offset(offset)
    )
    return tuple(
        _read_model_from_row(row) for row in connection.execute(query).mappings().all()
    )


def get_hosted_audit_event_scaffold(
    connection: Connection,
    actor: AuthenticatedActor | None,
    *,
    scope: HostedAccessScope,
    audit_event_id: str,
) -> HostedAuditEventRead | None:
    if not audit_event_id.strip():
        raise ValueError("Hosted audit event ID is required.")
    require_permission(
        actor,
        permission=AUDIT_READ_PERMISSION,
        scope=scope,
        target=AuthorizationTarget("audit_event", audit_event_id),
    )

    row = (
        connection.execute(
            select(hosted_audit_events).where(
                hosted_audit_events.c.scope_type == scope.scope_type,
                hosted_audit_events.c.scope_id == scope.scope_id,
                hosted_audit_events.c.audit_event_id == audit_event_id,
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None
    return _read_model_from_row(row)


def _read_model_from_row(row: RowMapping) -> HostedAuditEventRead:
    return HostedAuditEventRead(
        audit_event_id=_string_value(row, "audit_event_id"),
        occurred_at=_string_value(row, "occurred_at"),
        actor_provider_subject=_string_value(row, "actor_provider_subject"),
        actor_provider_issuer=_string_value(row, "actor_provider_issuer"),
        actor_display_name=_optional_string_value(row, "actor_display_name"),
        actor_category=_string_value(row, "actor_category"),
        authorization_permission=_string_value(row, "authorization_permission"),
        scope=HostedAccessScope(
            cast(Any, _string_value(row, "scope_type")),
            _string_value(row, "scope_id"),
        ),
        action=_audit_action(row),
        target_type=_audit_target_type(row),
        target_reviewer_state_id=_string_value(row, "target_reviewer_state_id"),
        source_record_key=_string_value(row, "source_record_key"),
        source_entity_type=_string_value(row, "source_entity_type"),
        source_stable_source_id=_string_value(row, "source_stable_source_id"),
        source_document_id=_string_value(row, "source_document_id"),
        context_metadata=_mapping_value(row, "context_metadata"),
    )


def _audit_action(row: RowMapping) -> HostedAuditAction:
    value = _string_value(row, "action")
    if value == "reviewer_created_state_scaffold.create":
        return "reviewer_created_state_scaffold.create"
    raise ValueError(f"Unknown hosted audit action: {value}")


def _audit_target_type(row: RowMapping) -> HostedAuditTargetType:
    value = _string_value(row, "target_type")
    if value == "reviewer_created_state":
        return "reviewer_created_state"
    raise ValueError(f"Unknown hosted audit target type: {value}")


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


def _mapping_value(row: RowMapping, key: str) -> Mapping[str, Any]:
    value = row[key]
    if not isinstance(value, Mapping):
        raise TypeError(f"Expected {key} to be an object.")
    return dict(value)