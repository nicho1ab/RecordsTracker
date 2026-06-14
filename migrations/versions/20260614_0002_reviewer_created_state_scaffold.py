"""Add hosted reviewer-created state scaffold table.

Revision ID: 20260614_0002
Revises: 20260613_0001
Create Date: 2026-06-14 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260614_0002"
down_revision = "20260613_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hosted_reviewer_created_state",
        sa.Column("reviewer_state_id", sa.String(length=96), nullable=False),
        sa.Column("source_record_key", sa.String(length=160), nullable=False),
        sa.Column("scope_type", sa.String(length=32), nullable=False),
        sa.Column("scope_id", sa.String(length=96), nullable=False),
        sa.Column("state_kind", sa.String(length=48), nullable=False),
        sa.Column("state_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.Column("created_by_provider_subject", sa.Text(), nullable=False),
        sa.Column("created_by_provider_issuer", sa.Text(), nullable=False),
        sa.Column("created_by_display_name", sa.Text(), nullable=True),
        sa.Column("created_by_actor_category", sa.String(length=32), nullable=False),
        sa.Column("authorization_permission", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_record_key"],
            ["hosted_source_derived_records.source_record_key"],
            name="fk_hosted_reviewer_created_state_source_record",
        ),
        sa.PrimaryKeyConstraint(
            "reviewer_state_id", name="pk_hosted_reviewer_created_state"
        ),
        sa.CheckConstraint(
            "state_kind IN ('review_item_state_scaffold')",
            name="ck_hosted_reviewer_created_state_kind",
        ),
        sa.CheckConstraint(
            "authorization_permission = 'reviewer_state_write'",
            name="ck_hosted_reviewer_created_state_write_permission",
        ),
    )


def downgrade() -> None:
    op.drop_table("hosted_reviewer_created_state")