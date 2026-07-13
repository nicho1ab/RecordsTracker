"""Add governed source-reference allocation columns.

Revision ID: 20260714_0007
Revises: 20260701_0006
Create Date: 2026-07-14 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260714_0007"
down_revision = "20260701_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "hosted_facility_reference_records",
        sa.Column("all_visit_dates", sa.JSON(none_as_null=True), nullable=True),
    )
    op.add_column(
        "hosted_facility_reference_records",
        sa.Column("inspection_visit_dates", sa.JSON(none_as_null=True), nullable=True),
    )
    op.add_column(
        "hosted_facility_reference_records",
        sa.Column("other_visit_dates", sa.JSON(none_as_null=True), nullable=True),
    )
    op.add_column(
        "hosted_facility_reference_records",
        sa.Column("client_served", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("hosted_facility_reference_records", "client_served")
    op.drop_column("hosted_facility_reference_records", "other_visit_dates")
    op.drop_column("hosted_facility_reference_records", "inspection_visit_dates")
    op.drop_column("hosted_facility_reference_records", "all_visit_dates")
