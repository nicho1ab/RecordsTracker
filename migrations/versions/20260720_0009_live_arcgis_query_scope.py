"""Authorize governed live-query candidates in the source snapshot lifecycle.

Revision ID: 20260720_0009
Revises: 20260720_0008
Create Date: 2026-07-20 00:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260720_0009"
down_revision = "20260720_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("hosted_source_snapshots") as batch_op:
        batch_op.drop_constraint(
            "ck_hosted_source_snapshots_fixture_scope",
            type_="check",
        )
        batch_op.create_check_constraint(
            "ck_hosted_source_snapshots_fixture_scope",
            "fixture_scope IN ('repository_synthetic_fixture', 'governed_live_query')",
        )
        batch_op.drop_constraint(
            "ck_hosted_source_snapshots_observation_kind",
            type_="check",
        )
        batch_op.create_check_constraint(
            "ck_hosted_source_snapshots_observation_kind",
            "observation_kind IN ('synthetic_query', 'synthetic_export', 'live_query')",
        )


def downgrade() -> None:
    connection = op.get_bind()
    live_row_count = connection.scalar(
        sa.text(
            "SELECT COUNT(*) FROM hosted_source_snapshots "
            "WHERE fixture_scope = 'governed_live_query' OR observation_kind = 'live_query'"
        )
    )
    if int(live_row_count or 0) > 0:
        raise RuntimeError(
            "Downgrade is blocked while governed live-query snapshot history exists."
        )
    with op.batch_alter_table("hosted_source_snapshots") as batch_op:
        batch_op.drop_constraint(
            "ck_hosted_source_snapshots_fixture_scope",
            type_="check",
        )
        batch_op.create_check_constraint(
            "ck_hosted_source_snapshots_fixture_scope",
            "fixture_scope = 'repository_synthetic_fixture'",
        )
        batch_op.drop_constraint(
            "ck_hosted_source_snapshots_observation_kind",
            type_="check",
        )
        batch_op.create_check_constraint(
            "ck_hosted_source_snapshots_observation_kind",
            "observation_kind IN ('synthetic_query', 'synthetic_export')",
        )
