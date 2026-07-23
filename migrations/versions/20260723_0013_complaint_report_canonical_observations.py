"""Add canonical historical complaint-report observation columns.

Revision ID: 20260723_0013
Revises: 20260722_0012
Create Date: 2026-07-23 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260723_0013"
down_revision = "20260722_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "hosted_source_derived_records",
        sa.Column("agency_name", sa.Text(), nullable=True),
    )
    op.add_column(
        "hosted_source_derived_records",
        sa.Column("deficiency_texts", sa.JSON(none_as_null=True), nullable=True),
    )
    op.add_column(
        "hosted_source_derived_records",
        sa.Column(
            "investigation_findings_narrative",
            sa.Text(),
            nullable=True,
        ),
    )
    op.add_column(
        "hosted_source_derived_records",
        sa.Column("complaint_report_contact", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("hosted_source_derived_records", "complaint_report_contact")
    op.drop_column(
        "hosted_source_derived_records",
        "investigation_findings_narrative",
    )
    op.drop_column("hosted_source_derived_records", "deficiency_texts")
    op.drop_column("hosted_source_derived_records", "agency_name")
