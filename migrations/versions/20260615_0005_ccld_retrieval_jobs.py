"""Add hosted CCLD retrieval job metadata table.

Revision ID: 20260615_0005
Revises: 20260614_0004
Create Date: 2026-06-15 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260615_0005"
down_revision = "20260614_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hosted_ccld_retrieval_jobs",
        sa.Column("retrieval_job_id", sa.String(length=96), nullable=False),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.Column("updated_at", sa.String(length=40), nullable=False),
        sa.Column("job_state", sa.String(length=32), nullable=False),
        sa.Column("facility_number", sa.String(length=32), nullable=False),
        sa.Column("record_type", sa.String(length=32), nullable=False),
        sa.Column("start_date", sa.String(length=10), nullable=False),
        sa.Column("end_date", sa.String(length=10), nullable=False),
        sa.Column("source_scope_type", sa.String(length=32), nullable=False),
        sa.Column("source_scope_id", sa.String(length=96), nullable=False),
        sa.Column("actor_provider_subject", sa.Text(), nullable=False),
        sa.Column("actor_provider_issuer", sa.Text(), nullable=False),
        sa.Column("actor_display_name", sa.Text(), nullable=True),
        sa.Column("actor_category", sa.String(length=32), nullable=False),
        sa.Column("authorization_permission", sa.String(length=64), nullable=False),
        sa.Column("request_limit", sa.String(length=16), nullable=False),
        sa.Column("retry_limit", sa.String(length=16), nullable=False),
        sa.Column("timeout_seconds", sa.String(length=16), nullable=False),
        sa.Column("raw_storage_path", sa.Text(), nullable=False),
        sa.Column("source_artifact_identity", sa.Text(), nullable=True),
        sa.Column("result_counts", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("errors", sa.JSON(), nullable=False),
        sa.Column("safe_message", sa.Text(), nullable=False),
        sa.Column("data_mutations_performed", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("retrieval_job_id", name="pk_hosted_ccld_retrieval_jobs"),
        sa.CheckConstraint(
            "job_state IN ('queued', 'running', 'completed', 'completed_with_warnings', "
            "'failed', 'blocked_by_validation', 'rate_limited')",
            name="ck_hosted_ccld_retrieval_jobs_state",
        ),
        sa.CheckConstraint(
            "record_type IN ('complaints', 'all_supported')",
            name="ck_hosted_ccld_retrieval_jobs_record_type",
        ),
        sa.CheckConstraint(
            "authorization_permission = 'retrieval_job_trigger'",
            name="ck_hosted_ccld_retrieval_jobs_permission",
        ),
    )


def downgrade() -> None:
    op.drop_table("hosted_ccld_retrieval_jobs")