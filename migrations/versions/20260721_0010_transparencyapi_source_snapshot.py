"""Add governed CCLD TransparencyAPI snapshot persistence.

Revision ID: 20260721_0010
Revises: 20260720_0009
Create Date: 2026-07-21 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260721_0010"
down_revision = "20260720_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("hosted_source_snapshots") as batch_op:
        batch_op.drop_constraint("ck_hosted_source_snapshots_fixture_scope", type_="check")
        batch_op.create_check_constraint(
            "ck_hosted_source_snapshots_fixture_scope",
            "fixture_scope IN ('repository_synthetic_fixture', 'governed_live_query', "
            "'governed_transparencyapi')",
        )
        batch_op.drop_constraint("ck_hosted_source_snapshots_observation_kind", type_="check")
        batch_op.create_check_constraint(
            "ck_hosted_source_snapshots_observation_kind",
            "observation_kind IN ('synthetic_query', 'synthetic_export', 'live_query', "
            "'bulk_export_family')",
        )

    op.create_table(
        "hosted_transparencyapi_snapshot_artifacts",
        sa.Column("snapshot_id", sa.String(length=80), nullable=False),
        sa.Column("artifact_id", sa.String(length=128), nullable=False),
        sa.Column("endpoint_kind", sa.String(length=40), nullable=False),
        sa.Column("export_id", sa.String(length=64), nullable=True),
        sa.Column("request_url", sa.Text(), nullable=False),
        sa.Column("final_url", sa.Text(), nullable=False),
        sa.Column("retrieved_at", sa.String(length=40), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=False),
        sa.Column("response_headers", sa.JSON(none_as_null=True), nullable=False),
        sa.Column("excluded_header_names", sa.JSON(none_as_null=True), nullable=False),
        sa.Column("media_type", sa.String(length=96), nullable=False),
        sa.Column("content_disposition", sa.Text(), nullable=True),
        sa.Column("byte_count", sa.Integer(), nullable=False),
        sa.Column("raw_sha256", sa.String(length=64), nullable=False),
        sa.Column("raw_ref", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint(
            "snapshot_id", "artifact_id", name="pk_hosted_transparencyapi_snapshot_artifacts"
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["hosted_source_snapshots.snapshot_id"],
            name="fk_transparencyapi_artifacts_snapshot",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "byte_count >= 0", name="ck_transparencyapi_artifacts_nonnegative_bytes"
        ),
        sa.UniqueConstraint(
            "snapshot_id",
            "raw_sha256",
            "artifact_id",
            name="uq_transparencyapi_artifact_identity",
        ),
    )

    op.create_table(
        "hosted_transparencyapi_snapshot_rows",
        sa.Column("snapshot_id", sa.String(length=80), nullable=False),
        sa.Column("export_id", sa.String(length=64), nullable=False),
        sa.Column("row_ordinal", sa.Integer(), nullable=False),
        sa.Column("facility_number", sa.String(length=32), nullable=True),
        sa.Column("raw_row_sha256", sa.String(length=64), nullable=False),
        sa.Column("raw_values", sa.JSON(none_as_null=True), nullable=False),
        sa.Column("raw_record", sa.JSON(none_as_null=True), nullable=False),
        sa.Column("normalized_record", sa.JSON(none_as_null=True), nullable=False),
        sa.Column("resolved_current_reference", sa.JSON(none_as_null=True), nullable=False),
        sa.Column("complaint_blocks", sa.JSON(none_as_null=True), nullable=False),
        sa.Column("row_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("is_quarantined", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint(
            "snapshot_id",
            "export_id",
            "row_ordinal",
            name="pk_hosted_transparencyapi_snapshot_rows",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["hosted_source_snapshots.snapshot_id"],
            name="fk_transparencyapi_rows_snapshot",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("row_ordinal > 0", name="ck_transparencyapi_rows_positive_ordinal"),
        sa.UniqueConstraint(
            "snapshot_id",
            "export_id",
            "row_ordinal",
            "raw_row_sha256",
            name="uq_transparencyapi_row_quarantine_identity",
        ),
    )
    op.create_index(
        "ix_transparencyapi_rows_facility_number",
        "hosted_transparencyapi_snapshot_rows",
        ["facility_number"],
    )

    op.create_table(
        "hosted_transparencyapi_snapshot_quarantines",
        sa.Column("snapshot_id", sa.String(length=80), nullable=False),
        sa.Column("quarantine_id", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("export_id", sa.String(length=64), nullable=True),
        sa.Column("row_ordinal", sa.Integer(), nullable=True),
        sa.Column("facility_number", sa.String(length=32), nullable=True),
        sa.Column("raw_row_sha256", sa.String(length=64), nullable=True),
        sa.Column("evidence", sa.JSON(none_as_null=True), nullable=False),
        sa.PrimaryKeyConstraint(
            "snapshot_id",
            "quarantine_id",
            name="pk_hosted_transparencyapi_snapshot_quarantines",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["hosted_source_snapshots.snapshot_id"],
            name="fk_transparencyapi_quarantines_snapshot",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_transparencyapi_quarantines_category",
        "hosted_transparencyapi_snapshot_quarantines",
        ["category"],
    )

    op.create_table(
        "hosted_transparencyapi_snapshot_disappearances",
        sa.Column("snapshot_id", sa.String(length=80), nullable=False),
        sa.Column("export_id", sa.String(length=64), nullable=False),
        sa.Column("prior_row_ordinal", sa.Integer(), nullable=False),
        sa.Column("prior_snapshot_id", sa.String(length=80), nullable=False),
        sa.Column("facility_number", sa.String(length=32), nullable=True),
        sa.Column("prior_row_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("review_state", sa.String(length=24), nullable=False),
        sa.Column("closure_inferred", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint(
            "snapshot_id",
            "export_id",
            "prior_row_ordinal",
            name="pk_hosted_transparencyapi_snapshot_disappearances",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["hosted_source_snapshots.snapshot_id"],
            name="fk_transparencyapi_disappearances_snapshot",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["prior_snapshot_id"],
            ["hosted_source_snapshots.snapshot_id"],
            name="fk_transparencyapi_disappearances_prior",
        ),
        sa.CheckConstraint(
            "review_state = 'pending_reconciliation'",
            name="ck_transparencyapi_disappearances_review_state",
        ),
        sa.CheckConstraint(
            "closure_inferred = false",
            name="ck_transparencyapi_disappearances_no_closure_inference",
        ),
    )


def downgrade() -> None:
    remaining = op.get_bind().scalar(
        sa.text(
            "SELECT COUNT(*) FROM hosted_source_snapshots "
            "WHERE fixture_scope = 'governed_transparencyapi' "
            "OR observation_kind = 'bulk_export_family'"
        )
    )
    if int(remaining or 0) > 0:
        raise RuntimeError("Downgrade is blocked while TransparencyAPI snapshot history exists.")
    op.drop_table("hosted_transparencyapi_snapshot_disappearances")
    op.drop_index(
        "ix_transparencyapi_quarantines_category",
        table_name="hosted_transparencyapi_snapshot_quarantines",
    )
    op.drop_table("hosted_transparencyapi_snapshot_quarantines")
    op.drop_index(
        "ix_transparencyapi_rows_facility_number",
        table_name="hosted_transparencyapi_snapshot_rows",
    )
    op.drop_table("hosted_transparencyapi_snapshot_rows")
    op.drop_table("hosted_transparencyapi_snapshot_artifacts")

    with op.batch_alter_table("hosted_source_snapshots") as batch_op:
        batch_op.drop_constraint("ck_hosted_source_snapshots_fixture_scope", type_="check")
        batch_op.create_check_constraint(
            "ck_hosted_source_snapshots_fixture_scope",
            "fixture_scope IN ('repository_synthetic_fixture', 'governed_live_query')",
        )
        batch_op.drop_constraint("ck_hosted_source_snapshots_observation_kind", type_="check")
        batch_op.create_check_constraint(
            "ck_hosted_source_snapshots_observation_kind",
            "observation_kind IN ('synthetic_query', 'synthetic_export', 'live_query')",
        )
