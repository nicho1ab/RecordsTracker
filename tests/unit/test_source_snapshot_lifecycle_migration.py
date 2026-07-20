from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from ccld_complaints.hosted_app.facility_reference_preload import (
    FACILITY_REFERENCE_TABLE_NAME,
)

NEW_TABLES = {
    "hosted_source_snapshots",
    "hosted_source_snapshot_rows",
    "hosted_source_snapshot_disappearances",
    "hosted_source_snapshot_pointers",
}


def test_source_snapshot_lifecycle_migration_is_additive_and_reversible() -> None:
    migration = _load_migration()
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    metadata = sa.MetaData()
    existing_table = sa.Table(
        FACILITY_REFERENCE_TABLE_NAME,
        metadata,
        sa.Column("source_resource_id", sa.String(128), primary_key=True),
        sa.Column("facility_number", sa.String(32), primary_key=True),
        sa.Column("facility_name", sa.Text(), nullable=False),
    )
    metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(
            existing_table.insert().values(
                source_resource_id="synthetic-program-resource",
                facility_number="SYNTHETIC-PROGRAM-ROW",
                facility_name="Synthetic Existing Program Row - Not Real",
            )
        )
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()

        inspector = sa.inspect(connection)
        assert NEW_TABLES <= set(inspector.get_table_names())
        assert inspector.get_pk_constraint("hosted_source_snapshot_rows")[
            "constrained_columns"
        ] == ["snapshot_id", "source_object_id"]
        assert inspector.get_pk_constraint("hosted_source_snapshot_pointers")[
            "constrained_columns"
        ] == ["source_family_id"]
        row = connection.execute(sa.select(existing_table)).mappings().one()
        assert dict(row) == {
            "source_resource_id": "synthetic-program-resource",
            "facility_number": "SYNTHETIC-PROGRAM-ROW",
            "facility_name": "Synthetic Existing Program Row - Not Real",
        }

        migration.downgrade()
        remaining = set(sa.inspect(connection).get_table_names())
        assert NEW_TABLES.isdisjoint(remaining)
        assert FACILITY_REFERENCE_TABLE_NAME in remaining
        assert connection.execute(sa.select(existing_table.c.facility_name)).scalar_one() == (
            "Synthetic Existing Program Row - Not Real"
        )

    engine.dispose()


def test_source_snapshot_lifecycle_migration_has_expected_constraints_and_indexes() -> None:
    migration = _load_migration()
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        inspector = sa.inspect(connection)

        snapshot_indexes = {
            index["name"] for index in inspector.get_indexes("hosted_source_snapshots")
        }
        row_indexes = {
            index["name"] for index in inspector.get_indexes("hosted_source_snapshot_rows")
        }
        disappearance_indexes = {
            index["name"]
            for index in inspector.get_indexes("hosted_source_snapshot_disappearances")
        }
        pointer_uniques = {
            constraint["name"]
            for constraint in inspector.get_unique_constraints("hosted_source_snapshot_pointers")
        }

        assert "ix_hosted_source_snapshots_family_state" in snapshot_indexes
        assert "ix_hosted_source_snapshot_rows_facility_number" in row_indexes
        assert (
            "ix_hosted_source_snapshot_disappearances_facility_number"
            in disappearance_indexes
        )
        assert "uq_hosted_source_snapshot_pointers_active" in pointer_uniques

    engine.dispose()


def _load_migration() -> Any:
    migration_path = (
        Path(__file__).resolve().parents[2]
        / "migrations"
        / "versions"
        / "20260720_0008_source_snapshot_lifecycle.py"
    )
    spec = importlib.util.spec_from_file_location(
        "source_snapshot_lifecycle_migration",
        migration_path,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Could not load source snapshot lifecycle migration.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
