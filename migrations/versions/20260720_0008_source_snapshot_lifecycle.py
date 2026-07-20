"""Add offline source-specific snapshot lifecycle tables.

Revision ID: 20260720_0008
Revises: 20260714_0007
Create Date: 2026-07-20 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260720_0008"
down_revision = "20260714_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hosted_source_snapshots",
        sa.Column("snapshot_id", sa.String(length=80), nullable=False),
        sa.Column("source_family_id", sa.String(length=96), nullable=False),
        sa.Column("fixture_scope", sa.String(length=40), nullable=False),
        sa.Column("observation_kind", sa.String(length=32), nullable=False),
        sa.Column("lifecycle_state", sa.String(length=16), nullable=False),
        sa.Column("manifest_ref", sa.Text(), nullable=False),
        sa.Column("manifest_sha256", sa.String(length=64), nullable=False),
        sa.Column("raw_payload_ref", sa.Text(), nullable=False),
        sa.Column("raw_payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("normalized_content_sha256", sa.String(length=64), nullable=False),
        sa.Column("schema_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("domain_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("stored_row_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_object_id_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_facility_number_count", sa.Integer(), nullable=False),
        sa.Column("omitted_field_count", sa.Integer(), nullable=False),
        sa.Column("invalid_field_count", sa.Integer(), nullable=False),
        sa.Column("warning_count", sa.Integer(), nullable=False),
        sa.Column("rejection_reason_count", sa.Integer(), nullable=False),
        sa.Column("validation_report", sa.JSON(none_as_null=True), nullable=False),
        sa.Column("recorded_at", sa.String(length=40), nullable=False),
        sa.Column("validated_at", sa.String(length=40), nullable=True),
        sa.Column("rejected_at", sa.String(length=40), nullable=True),
        sa.Column("accepted_at", sa.String(length=40), nullable=True),
        sa.PrimaryKeyConstraint("snapshot_id", name="pk_hosted_source_snapshots"),
        sa.UniqueConstraint(
            "source_family_id",
            "manifest_sha256",
            "raw_payload_sha256",
            name="uq_hosted_source_snapshots_fixture_identity",
        ),
        sa.CheckConstraint(
            "fixture_scope = 'repository_synthetic_fixture'",
            name="ck_hosted_source_snapshots_fixture_scope",
        ),
        sa.CheckConstraint(
            "observation_kind IN ('synthetic_query', 'synthetic_export')",
            name="ck_hosted_source_snapshots_observation_kind",
        ),
        sa.CheckConstraint(
            "lifecycle_state IN ('candidate', 'validated', 'rejected', 'accepted')",
            name="ck_hosted_source_snapshots_lifecycle_state",
        ),
        sa.CheckConstraint(
            "row_count >= 0 AND stored_row_count >= 0",
            name="ck_hosted_source_snapshots_nonnegative_rows",
        ),
    )
    op.create_index(
        "ix_hosted_source_snapshots_family_state",
        "hosted_source_snapshots",
        ["source_family_id", "lifecycle_state", "recorded_at"],
    )

    op.create_table(
        "hosted_source_snapshot_rows",
        sa.Column("snapshot_id", sa.String(length=80), nullable=False),
        sa.Column("source_object_id", sa.BigInteger(), nullable=False),
        sa.Column("facility_number", sa.String(length=32), nullable=True),
        sa.Column("raw_record", sa.JSON(none_as_null=True), nullable=False),
        sa.Column("normalized_record", sa.JSON(none_as_null=True), nullable=False),
        sa.Column("row_fingerprint", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint(
            "snapshot_id",
            "source_object_id",
            name="pk_hosted_source_snapshot_rows",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["hosted_source_snapshots.snapshot_id"],
            name="fk_hosted_source_snapshot_rows_snapshot",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "snapshot_id",
            "row_fingerprint",
            "source_object_id",
            name="uq_hosted_source_snapshot_rows_fingerprint_identity",
        ),
    )
    op.create_index(
        "ix_hosted_source_snapshot_rows_facility_number",
        "hosted_source_snapshot_rows",
        ["facility_number"],
    )

    op.create_table(
        "hosted_source_snapshot_disappearances",
        sa.Column("snapshot_id", sa.String(length=80), nullable=False),
        sa.Column("prior_snapshot_id", sa.String(length=80), nullable=False),
        sa.Column("source_object_id", sa.BigInteger(), nullable=False),
        sa.Column("facility_number", sa.String(length=32), nullable=True),
        sa.Column("prior_row_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("review_state", sa.String(length=24), nullable=False),
        sa.Column("closure_inferred", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint(
            "snapshot_id",
            "source_object_id",
            name="pk_hosted_source_snapshot_disappearances",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["hosted_source_snapshots.snapshot_id"],
            name="fk_hosted_source_snapshot_disappearances_snapshot",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["prior_snapshot_id"],
            ["hosted_source_snapshots.snapshot_id"],
            name="fk_hosted_source_snapshot_disappearances_prior",
        ),
        sa.CheckConstraint(
            "review_state = 'pending_reconciliation'",
            name="ck_hosted_source_snapshot_disappearances_review_state",
        ),
        sa.CheckConstraint(
            "closure_inferred = false",
            name="ck_hosted_source_snapshot_disappearances_no_closure_inference",
        ),
    )
    op.create_index(
        "ix_hosted_source_snapshot_disappearances_facility_number",
        "hosted_source_snapshot_disappearances",
        ["facility_number"],
    )

    op.create_table(
        "hosted_source_snapshot_pointers",
        sa.Column("source_family_id", sa.String(length=96), nullable=False),
        sa.Column("active_snapshot_id", sa.String(length=80), nullable=False),
        sa.Column("prior_accepted_snapshot_id", sa.String(length=80), nullable=True),
        sa.Column("updated_at", sa.String(length=40), nullable=False),
        sa.PrimaryKeyConstraint(
            "source_family_id",
            name="pk_hosted_source_snapshot_pointers",
        ),
        sa.ForeignKeyConstraint(
            ["active_snapshot_id"],
            ["hosted_source_snapshots.snapshot_id"],
            name="fk_hosted_source_snapshot_pointers_active",
        ),
        sa.ForeignKeyConstraint(
            ["prior_accepted_snapshot_id"],
            ["hosted_source_snapshots.snapshot_id"],
            name="fk_hosted_source_snapshot_pointers_prior",
        ),
        sa.UniqueConstraint(
            "active_snapshot_id",
            name="uq_hosted_source_snapshot_pointers_active",
        ),
        sa.CheckConstraint(
            "prior_accepted_snapshot_id IS NULL "
            "OR prior_accepted_snapshot_id <> active_snapshot_id",
            name="ck_hosted_source_snapshot_pointers_distinct_snapshots",
        ),
    )


def downgrade() -> None:
    op.drop_table("hosted_source_snapshot_pointers")
    op.drop_index(
        "ix_hosted_source_snapshot_disappearances_facility_number",
        table_name="hosted_source_snapshot_disappearances",
    )
    op.drop_table("hosted_source_snapshot_disappearances")
    op.drop_index(
        "ix_hosted_source_snapshot_rows_facility_number",
        table_name="hosted_source_snapshot_rows",
    )
    op.drop_table("hosted_source_snapshot_rows")
    op.drop_index(
        "ix_hosted_source_snapshots_family_state",
        table_name="hosted_source_snapshots",
    )
    op.drop_table("hosted_source_snapshots")
