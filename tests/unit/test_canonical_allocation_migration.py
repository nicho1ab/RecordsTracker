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


def test_canonical_allocation_migration_is_additive_and_preserves_existing_rows() -> None:
    migration = _load_migration()
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    metadata = sa.MetaData()
    old_table = sa.Table(
        FACILITY_REFERENCE_TABLE_NAME,
        metadata,
        sa.Column("source_resource_id", sa.String(128), primary_key=True),
        sa.Column("facility_number", sa.String(32), primary_key=True),
        sa.Column("facility_name", sa.Text(), nullable=False),
        sa.Column("closed_date", sa.String(10), nullable=True),
    )
    metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(
            old_table.insert().values(
                source_resource_id="public-resource",
                facility_number="123456789",
                facility_name="Existing Facility",
                closed_date="2026-01-02",
            )
        )
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()

        columns = {
            column["name"]: column
            for column in sa.inspect(connection).get_columns(FACILITY_REFERENCE_TABLE_NAME)
        }
        row = (
            connection.execute(
                sa.text(
                    "SELECT source_resource_id, facility_number, facility_name, closed_date, "
                    "all_visit_dates, inspection_visit_dates, other_visit_dates, client_served "
                    f"FROM {FACILITY_REFERENCE_TABLE_NAME}"
                )
            )
            .mappings()
            .one()
        )

    for column_name in (
        "all_visit_dates",
        "inspection_visit_dates",
        "other_visit_dates",
        "client_served",
    ):
        assert columns[column_name]["nullable"] is True
    assert dict(row) == {
        "source_resource_id": "public-resource",
        "facility_number": "123456789",
        "facility_name": "Existing Facility",
        "closed_date": "2026-01-02",
        "all_visit_dates": None,
        "inspection_visit_dates": None,
        "other_visit_dates": None,
        "client_served": None,
    }


def _load_migration() -> Any:
    migration_path = (
        Path(__file__).resolve().parents[2]
        / "migrations"
        / "versions"
        / "20260714_0007_canonical_allocation.py"
    )
    spec = importlib.util.spec_from_file_location(
        "canonical_allocation_migration",
        migration_path,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Could not load canonical allocation migration.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
