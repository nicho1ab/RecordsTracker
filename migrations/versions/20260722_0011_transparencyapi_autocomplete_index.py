"""Add the active-snapshot Facility Number autocomplete index.

Revision ID: 20260722_0011
Revises: 20260721_0010
"""

from alembic import op

revision = "20260722_0011"
down_revision = "20260721_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_transparencyapi_rows_snapshot_facility_number",
        "hosted_transparencyapi_snapshot_rows",
        ["snapshot_id", "facility_number"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_transparencyapi_rows_snapshot_facility_number",
        table_name="hosted_transparencyapi_snapshot_rows",
    )
