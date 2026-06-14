"""Add hosted audit event scaffold table.

Revision ID: 20260614_0003
Revises: 20260614_0002
Create Date: 2026-06-14 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260614_0003"
down_revision = "20260614_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hosted_audit_events",
        sa.Column("audit_event_id", sa.String(length=96), nullable=False),
        sa.Column("occurred_at", sa.String(length=40), nullable=False),
        sa.Column("actor_provider_subject", sa.Text(), nullable=False),
        sa.Column("actor_provider_issuer", sa.Text(), nullable=False),
        sa.Column("actor_display_name", sa.Text(), nullable=True),
        sa.Column("actor_category", sa.String(length=32), nullable=False),
        sa.Column("authorization_permission", sa.String(length=64), nullable=False),
        sa.Column("scope_type", sa.String(length=32), nullable=False),
        sa.Column("scope_id", sa.String(length=96), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_reviewer_state_id", sa.String(length=96), nullable=False),
        sa.Column("source_record_key", sa.String(length=160), nullable=False),
        sa.Column("source_entity_type", sa.String(length=32), nullable=False),
        sa.Column("source_stable_source_id", sa.Text(), nullable=False),
        sa.Column("source_document_id", sa.Text(), nullable=False),
        sa.Column("context_metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["target_reviewer_state_id"],
            ["hosted_reviewer_created_state.reviewer_state_id"],
            name="fk_hosted_audit_events_reviewer_state",
        ),
        sa.PrimaryKeyConstraint("audit_event_id", name="pk_hosted_audit_events"),
        sa.CheckConstraint(
            "action IN ('reviewer_created_state_scaffold.create')",
            name="ck_hosted_audit_events_action",
        ),
        sa.CheckConstraint(
            "target_type IN ('reviewer_created_state')",
            name="ck_hosted_audit_events_target_type",
        ),
        sa.CheckConstraint(
            "authorization_permission = 'reviewer_state_write'",
            name="ck_hosted_audit_events_reviewer_state_write_permission",
        ),
    )


def downgrade() -> None:
    op.drop_table("hosted_audit_events")