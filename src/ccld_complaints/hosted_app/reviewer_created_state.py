from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, cast
from uuid import uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    ForeignKey,
    String,
    Table,
    Text,
    func,
    or_,
    select,
)
from sqlalchemy.engine import Connection, RowMapping

from ccld_complaints.hosted_app.audit_events import create_hosted_audit_event
from ccld_complaints.hosted_app.auth import (
    REVIEWER_STATE_READ_PERMISSION,
    REVIEWER_STATE_WRITE_PERMISSION,
    AuthenticatedActor,
    AuthorizationTarget,
    HostedAccessScope,
    HostedScopeDeniedError,
    require_permission,
)
from ccld_complaints.hosted_app.seeded_import import (
    hosted_seeded_import_metadata,
    hosted_source_derived_records,
)
from ccld_complaints.hosted_app.source_derived_reads import get_source_derived_record_by_key

ReviewerCreatedStateKind = Literal["review_item_state_scaffold"]
REVIEWER_CREATED_STATE_KINDS: tuple[ReviewerCreatedStateKind, ...] = (
    "review_item_state_scaffold",
)

hosted_reviewer_created_state = Table(
    "hosted_reviewer_created_state",
    hosted_seeded_import_metadata,
    Column("reviewer_state_id", String(96), primary_key=True),
    Column(
        "source_record_key",
        String(160),
        ForeignKey(hosted_source_derived_records.c.source_record_key),
        nullable=False,
    ),
    Column("scope_type", String(32), nullable=False),
    Column("scope_id", String(96), nullable=False),
    Column("state_kind", String(48), nullable=False),
    Column("state_payload", JSON, nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("created_by_provider_subject", Text, nullable=False),
    Column("created_by_provider_issuer", Text, nullable=False),
    Column("created_by_display_name", Text, nullable=True),
    Column("created_by_actor_category", String(32), nullable=False),
    Column("authorization_permission", String(64), nullable=False),
    CheckConstraint(
        "state_kind IN ('review_item_state_scaffold')",
        name="ck_hosted_reviewer_created_state_kind",
    ),
    CheckConstraint(
        "authorization_permission = 'reviewer_state_write'",
        name="ck_hosted_reviewer_created_state_write_permission",
    ),
)


@dataclass(frozen=True)
class ReviewerCreatedStateRead:
    reviewer_state_id: str
    source_record_key: str
    scope: HostedAccessScope
    state_kind: ReviewerCreatedStateKind
    state_payload: Mapping[str, Any]
    created_at: str
    created_by_provider_subject: str
    created_by_provider_issuer: str
    created_by_display_name: str | None
    created_by_actor_category: str
    authorization_permission: str


class ReviewerCreatedStateReferenceError(ValueError):
    pass


def create_reviewer_created_state_scaffold(
    connection: Connection,
    actor: AuthenticatedActor | None,
    *,
    scope: HostedAccessScope,
    source_record_key: str,
    state_payload: Mapping[str, Any],
    state_kind: ReviewerCreatedStateKind = "review_item_state_scaffold",
) -> ReviewerCreatedStateRead:
    if state_kind not in REVIEWER_CREATED_STATE_KINDS:
        raise ValueError("Reviewer-created state kind is not supported by this scaffold.")
    if not source_record_key.strip():
        raise ValueError("Source-derived record key is required.")
    if not state_payload:
        raise ValueError("Reviewer-created state payload must not be empty.")

    authorized = require_permission(
        actor,
        permission=REVIEWER_STATE_WRITE_PERMISSION,
        scope=scope,
        target=AuthorizationTarget("reviewer_created_state", source_record_key),
    )
    source_record = get_source_derived_record_by_key(connection, source_record_key)
    if source_record is None:
        raise ReviewerCreatedStateReferenceError(
            "Reviewer-created state must reference an existing staged source-derived record."
        )
    if source_record.import_batch.import_batch_id != scope.scope_id:
        raise HostedScopeDeniedError(
            "Reviewer-created state source-derived reference is outside the authorized scope."
        )

    reviewer_state_id = f"reviewer-state:{uuid4().hex}"
    values = {
        "reviewer_state_id": reviewer_state_id,
        "source_record_key": source_record_key,
        "scope_type": scope.scope_type,
        "scope_id": scope.scope_id,
        "state_kind": state_kind,
        "state_payload": dict(state_payload),
        "created_at": authorized.authorized_at,
        "created_by_provider_subject": authorized.actor.provider_subject,
        "created_by_provider_issuer": authorized.actor.provider_issuer,
        "created_by_display_name": authorized.actor.display_name,
        "created_by_actor_category": authorized.actor.actor_category,
        "authorization_permission": authorized.permission,
    }
    with connection.begin_nested():
        connection.execute(hosted_reviewer_created_state.insert().values(**values))
        created = _read_model_from_row(
            connection.execute(
                select(hosted_reviewer_created_state).where(
                    hosted_reviewer_created_state.c.reviewer_state_id == reviewer_state_id
                )
            )
            .mappings()
            .one()
        )
        create_hosted_audit_event(
            connection,
            authorized=authorized,
            action="reviewer_created_state_scaffold.create",
            target_type="reviewer_created_state",
            target_reviewer_state_id=reviewer_state_id,
            source_record=source_record,
            context_metadata={
                "state_kind": state_kind,
                "state_payload_keys": sorted(state_payload.keys()),
                "source_record_key": source_record_key,
            },
        )
    return created


def list_reviewer_created_state_scaffold(
    connection: Connection,
    actor: AuthenticatedActor | None,
    *,
    scope: HostedAccessScope,
    source_record_key: str | None = None,
    state_kind: ReviewerCreatedStateKind | None = None,
    actor_provider_subject: str | None = None,
    search_query: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[ReviewerCreatedStateRead, ...]:
    if limit < 1:
        raise ValueError("Reviewer-created state list limit must be at least 1.")
    if offset < 0:
        raise ValueError("Reviewer-created state list offset must be at least 0.")
    if state_kind is not None and state_kind not in REVIEWER_CREATED_STATE_KINDS:
        raise ValueError("Reviewer-created state kind is not supported by this scaffold.")
    normalized_search_query = _normalized_search_query(search_query)
    require_permission(
        actor,
        permission=REVIEWER_STATE_READ_PERMISSION,
        scope=scope,
        target=AuthorizationTarget("reviewer_created_state", scope.scope_id),
    )

    query = select(hosted_reviewer_created_state).where(
        hosted_reviewer_created_state.c.scope_type == scope.scope_type,
        hosted_reviewer_created_state.c.scope_id == scope.scope_id,
    )
    if source_record_key is not None:
        query = query.where(
            hosted_reviewer_created_state.c.source_record_key == source_record_key
        )
    if state_kind is not None:
        query = query.where(hosted_reviewer_created_state.c.state_kind == state_kind)
    if actor_provider_subject is not None:
        query = query.where(
            hosted_reviewer_created_state.c.created_by_provider_subject
            == actor_provider_subject
        )
    if normalized_search_query is not None:
        search_pattern = _like_search_pattern(normalized_search_query)
        query = query.where(
            or_(
                func.lower(hosted_reviewer_created_state.c.reviewer_state_id).like(
                    search_pattern,
                    escape="\\",
                ),
                func.lower(hosted_reviewer_created_state.c.source_record_key).like(
                    search_pattern,
                    escape="\\",
                ),
                func.lower(hosted_reviewer_created_state.c.state_kind).like(
                    search_pattern,
                    escape="\\",
                ),
                func.lower(hosted_reviewer_created_state.c.created_at).like(
                    search_pattern,
                    escape="\\",
                ),
                func.lower(
                    hosted_reviewer_created_state.c.created_by_provider_subject
                ).like(search_pattern, escape="\\"),
                func.lower(
                    hosted_reviewer_created_state.c.created_by_display_name
                ).like(search_pattern, escape="\\"),
                func.lower(
                    hosted_reviewer_created_state.c.created_by_actor_category
                ).like(search_pattern, escape="\\"),
                func.lower(hosted_reviewer_created_state.c.authorization_permission).like(
                    search_pattern,
                    escape="\\",
                ),
            )
        )
    query = (
        query.order_by(
            hosted_reviewer_created_state.c.created_at,
            hosted_reviewer_created_state.c.reviewer_state_id,
        )
        .limit(limit)
        .offset(offset)
    )
    return tuple(_read_model_from_row(row) for row in connection.execute(query).mappings().all())


def _normalized_search_query(search_query: str | None) -> str | None:
    if search_query is None:
        return None
    normalized = " ".join(search_query.casefold().split())
    return normalized or None


def _like_search_pattern(search_query: str) -> str:
    escaped = (
        search_query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    )
    return f"%{escaped}%"


def get_reviewer_created_state_scaffold(
    connection: Connection,
    actor: AuthenticatedActor | None,
    *,
    scope: HostedAccessScope,
    reviewer_state_id: str,
) -> ReviewerCreatedStateRead | None:
    if not reviewer_state_id.strip():
        raise ValueError("Reviewer-created state ID is required.")
    require_permission(
        actor,
        permission=REVIEWER_STATE_READ_PERMISSION,
        scope=scope,
        target=AuthorizationTarget("reviewer_created_state", reviewer_state_id),
    )
    row = (
        connection.execute(
            select(hosted_reviewer_created_state).where(
                hosted_reviewer_created_state.c.scope_type == scope.scope_type,
                hosted_reviewer_created_state.c.scope_id == scope.scope_id,
                hosted_reviewer_created_state.c.reviewer_state_id == reviewer_state_id,
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None
    return _read_model_from_row(row)


def _read_model_from_row(row: RowMapping) -> ReviewerCreatedStateRead:
    return ReviewerCreatedStateRead(
        reviewer_state_id=_string_value(row, "reviewer_state_id"),
        source_record_key=_string_value(row, "source_record_key"),
        scope=HostedAccessScope(
            cast(Any, _string_value(row, "scope_type")),
            _string_value(row, "scope_id"),
        ),
        state_kind=_state_kind(row),
        state_payload=_mapping_value(row, "state_payload"),
        created_at=_string_value(row, "created_at"),
        created_by_provider_subject=_string_value(row, "created_by_provider_subject"),
        created_by_provider_issuer=_string_value(row, "created_by_provider_issuer"),
        created_by_display_name=_optional_string_value(row, "created_by_display_name"),
        created_by_actor_category=_string_value(row, "created_by_actor_category"),
        authorization_permission=_string_value(row, "authorization_permission"),
    )


def _state_kind(row: RowMapping) -> ReviewerCreatedStateKind:
    value = _string_value(row, "state_kind")
    if value == "review_item_state_scaffold":
        return "review_item_state_scaffold"
    raise ValueError(f"Unknown reviewer-created state kind: {value}")


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