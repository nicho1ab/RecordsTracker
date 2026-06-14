"""Add hosted seeded corpus import tables.

Revision ID: 20260613_0001
Revises:
Create Date: 2026-06-13 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260613_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hosted_import_batches",
        sa.Column("import_batch_id", sa.String(length=96), nullable=False),
        sa.Column("imported_at", sa.String(length=40), nullable=False),
        sa.Column("source_artifact_identity", sa.Text(), nullable=False),
        sa.Column("source_pipeline_version", sa.Text(), nullable=True),
        sa.Column("validation_status", sa.String(length=32), nullable=False),
        sa.Column("raw_hash_validation_status", sa.String(length=32), nullable=False),
        sa.Column("record_counts", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("errors", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("import_batch_id", name="pk_hosted_import_batches"),
        sa.CheckConstraint(
            "validation_status = 'validated'",
            name="ck_hosted_import_batches_validation_status",
        ),
        sa.CheckConstraint(
            "raw_hash_validation_status = 'validated'",
            name="ck_hosted_import_batches_raw_hash_validation_status",
        ),
    )

    op.create_table(
        "hosted_source_derived_records",
        sa.Column("source_record_key", sa.String(length=160), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("stable_source_id", sa.Text(), nullable=False),
        sa.Column("import_batch_id", sa.String(length=96), nullable=False),
        sa.Column("source_document_id", sa.Text(), nullable=False),
        sa.Column("facility_id", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("raw_sha256", sa.String(length=64), nullable=False),
        sa.Column("raw_path", sa.Text(), nullable=True),
        sa.Column("connector_name", sa.Text(), nullable=False),
        sa.Column("connector_version", sa.Text(), nullable=False),
        sa.Column("retrieved_at", sa.String(length=40), nullable=False),
        sa.Column("original_values", sa.JSON(), nullable=False),
        sa.Column("source_traceability", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["import_batch_id"],
            ["hosted_import_batches.import_batch_id"],
            name="fk_hosted_source_derived_records_import_batch",
        ),
        sa.PrimaryKeyConstraint(
            "source_record_key", name="pk_hosted_source_derived_records"
        ),
        sa.UniqueConstraint(
            "entity_type",
            "stable_source_id",
            name="uq_hosted_source_derived_records_stable_identity",
        ),
        sa.CheckConstraint(
            "entity_type IN "
            "('facility', 'source_document', 'complaint', 'allegation', 'event', "
            "'extraction_audit')",
            name="ck_hosted_source_derived_records_entity_type",
        ),
        sa.CheckConstraint(
            "raw_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_hosted_source_derived_records_raw_sha256",
        ),
    )


def downgrade() -> None:
    op.drop_table("hosted_source_derived_records")
    op.drop_table("hosted_import_batches")