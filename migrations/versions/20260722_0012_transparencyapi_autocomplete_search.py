"""Add a normalized TransparencyAPI autocomplete search projection.

Revision ID: 20260722_0012
Revises: 20260722_0011
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260722_0012"
down_revision = "20260722_0011"
branch_labels = None
depends_on = None

_TABLE_NAME = "hosted_transparencyapi_snapshot_rows"
_INDEX_NAME = "ix_transparencyapi_rows_autocomplete_search_trgm"


def upgrade() -> None:
    op.add_column(
        _TABLE_NAME,
        sa.Column("autocomplete_search_text", sa.Text(), nullable=False, server_default=""),
    )
    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(
        sa.text(
            """
            UPDATE hosted_transparencyapi_snapshot_rows
            SET autocomplete_search_text = lower(concat_ws(' ',
                facility_number,
                resolved_current_reference -> 'facility_name' ->> 'value',
                resolved_current_reference -> 'facility_city' ->> 'value',
                resolved_current_reference -> 'county_name' ->> 'value',
                resolved_current_reference -> 'facility_zip' ->> 'value',
                resolved_current_reference -> 'facility_state' ->> 'value',
                resolved_current_reference -> 'facility_type' ->> 'value',
                resolved_current_reference -> 'bulk_status' ->> 'value'
            ))
            """
        )
    )
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_index(
        _INDEX_NAME,
        _TABLE_NAME,
        ["autocomplete_search_text"],
        postgresql_using="gin",
        postgresql_ops={"autocomplete_search_text": "gin_trgm_ops"},
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.drop_index(_INDEX_NAME, table_name=_TABLE_NAME)
    with op.batch_alter_table(_TABLE_NAME) as batch_op:
        batch_op.drop_column("autocomplete_search_text")
