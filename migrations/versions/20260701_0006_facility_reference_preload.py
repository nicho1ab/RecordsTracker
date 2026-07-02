"""Add hosted facility reference preload table.

Revision ID: 20260701_0006
Revises: 20260615_0005
Create Date: 2026-07-01 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260701_0006"
down_revision = "20260615_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hosted_facility_reference_records",
        sa.Column("source_resource_id", sa.String(length=128), nullable=False),
        sa.Column("facility_number", sa.String(length=32), nullable=False),
        sa.Column("facility_name", sa.Text(), nullable=False),
        sa.Column("facility_type", sa.Text(), nullable=True),
        sa.Column("program_type", sa.Text(), nullable=True),
        sa.Column("licensee_name", sa.Text(), nullable=True),
        sa.Column("facility_administrator", sa.Text(), nullable=True),
        sa.Column("telephone", sa.String(length=64), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("city", sa.Text(), nullable=True),
        sa.Column("state", sa.String(length=16), nullable=True),
        sa.Column("zip", sa.String(length=16), nullable=True),
        sa.Column("county", sa.Text(), nullable=True),
        sa.Column("regional_office", sa.Text(), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("license_first_date", sa.String(length=10), nullable=True),
        sa.Column("closed_date", sa.String(length=10), nullable=True),
        sa.Column("snapshot_date", sa.String(length=10), nullable=True),
        sa.Column("source_resource_name", sa.Text(), nullable=False),
        sa.Column("source_dataset_slug", sa.Text(), nullable=False),
        sa.Column("source_dataset_url", sa.Text(), nullable=False),
        sa.Column("source_accessed_at", sa.String(length=40), nullable=False),
        sa.Column("source_file_name", sa.Text(), nullable=True),
        sa.Column("original_row_json", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint(
            "source_resource_id",
            "facility_number",
            name="pk_hosted_facility_reference_records",
        ),
    )
    op.create_index(
        "ix_hosted_facility_reference_records_facility_number",
        "hosted_facility_reference_records",
        ["facility_number"],
    )
    op.create_index(
        "ix_hosted_facility_reference_records_facility_name",
        "hosted_facility_reference_records",
        ["facility_name"],
    )
    op.create_index(
        "ix_hosted_facility_reference_records_type_program",
        "hosted_facility_reference_records",
        ["facility_type", "program_type"],
    )
    op.create_index(
        "ix_hosted_facility_reference_records_county",
        "hosted_facility_reference_records",
        ["county"],
    )
    op.create_index(
        "ix_hosted_facility_reference_records_status",
        "hosted_facility_reference_records",
        ["status"],
    )
    op.create_index(
        "ix_hosted_facility_reference_records_city",
        "hosted_facility_reference_records",
        ["city"],
    )
    op.create_index(
        "ix_hosted_facility_reference_records_zip",
        "hosted_facility_reference_records",
        ["zip"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_hosted_facility_reference_records_zip",
        table_name="hosted_facility_reference_records",
    )
    op.drop_index(
        "ix_hosted_facility_reference_records_city",
        table_name="hosted_facility_reference_records",
    )
    op.drop_index(
        "ix_hosted_facility_reference_records_status",
        table_name="hosted_facility_reference_records",
    )
    op.drop_index(
        "ix_hosted_facility_reference_records_county",
        table_name="hosted_facility_reference_records",
    )
    op.drop_index(
        "ix_hosted_facility_reference_records_type_program",
        table_name="hosted_facility_reference_records",
    )
    op.drop_index(
        "ix_hosted_facility_reference_records_facility_name",
        table_name="hosted_facility_reference_records",
    )
    op.drop_index(
        "ix_hosted_facility_reference_records_facility_number",
        table_name="hosted_facility_reference_records",
    )
    op.drop_table("hosted_facility_reference_records")
