"""Add hosted reset/reload operational metadata scaffold table.

Revision ID: 20260614_0004
Revises: 20260614_0003
Create Date: 2026-06-14 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260614_0004"
down_revision = "20260614_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hosted_reset_reload_planning_metadata",
        sa.Column("planning_record_id", sa.String(length=96), nullable=False),
        sa.Column("generated_at", sa.String(length=40), nullable=False),
        sa.Column("operation", sa.String(length=80), nullable=False),
        sa.Column("requested_operation_mode", sa.String(length=32), nullable=False),
        sa.Column("source_scope_type", sa.String(length=32), nullable=False),
        sa.Column("source_scope_id", sa.String(length=96), nullable=False),
        sa.Column("reviewer_state_handling_mode", sa.String(length=16), nullable=False),
        sa.Column("actor_provider_subject", sa.Text(), nullable=False),
        sa.Column("actor_provider_issuer", sa.Text(), nullable=False),
        sa.Column("actor_display_name", sa.Text(), nullable=True),
        sa.Column("actor_category", sa.String(length=32), nullable=False),
        sa.Column("authorization_permission", sa.String(length=64), nullable=False),
        sa.Column("source_derived_summary", sa.JSON(), nullable=False),
        sa.Column("reviewer_created_state_summary", sa.JSON(), nullable=False),
        sa.Column("audit_event_summary", sa.JSON(), nullable=False),
        sa.Column("validation_summary", sa.JSON(), nullable=False),
        sa.Column("planning_context", sa.JSON(), nullable=False),
        sa.Column("future_execution_permissions", sa.JSON(), nullable=False),
        sa.Column("deferred_actions", sa.JSON(), nullable=False),
        sa.Column("data_mutations_performed", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint(
            "planning_record_id", name="pk_hosted_reset_reload_planning_metadata"
        ),
        sa.CheckConstraint(
            "operation = 'seeded_corpus_reset_reload_dry_run'",
            name="ck_hosted_reset_reload_planning_metadata_operation",
        ),
        sa.CheckConstraint(
            "requested_operation_mode = 'dry_run'",
            name="ck_hosted_reset_reload_planning_metadata_requested_mode",
        ),
        sa.CheckConstraint(
            "reviewer_state_handling_mode IN ('preserve', 'archive', 'clear')",
            name="ck_hosted_reset_reload_planning_metadata_state_mode",
        ),
        sa.CheckConstraint(
            "authorization_permission = 'import_reload'",
            name="ck_hosted_reset_reload_planning_metadata_permission",
        ),
    )


def downgrade() -> None:
    op.drop_table("hosted_reset_reload_planning_metadata")