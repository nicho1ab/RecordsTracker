from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import IntegrityError

NEW_TABLES = {
    "hosted_transparencyapi_snapshot_artifacts",
    "hosted_transparencyapi_snapshot_rows",
    "hosted_transparencyapi_snapshot_quarantines",
    "hosted_transparencyapi_snapshot_disappearances",
}


def test_transparencyapi_migration_upgrades_and_downgrades_without_history() -> None:
    lifecycle = _load("20260720_0008_source_snapshot_lifecycle.py")
    live_scope = _load("20260720_0009_live_arcgis_query_scope.py")
    migration = _load("20260721_0010_transparencyapi_source_snapshot.py")
    autocomplete_index = _load("20260722_0011_transparencyapi_autocomplete_index.py")
    autocomplete_search = _load("20260722_0012_transparencyapi_autocomplete_search.py")
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        lifecycle.op = operations
        live_scope.op = operations
        migration.op = operations
        autocomplete_index.op = operations
        autocomplete_search.op = operations
        lifecycle.upgrade()
        live_scope.upgrade()
        migration.upgrade()
        autocomplete_index.upgrade()
        autocomplete_search.upgrade()
        inspector = sa.inspect(connection)
        assert NEW_TABLES <= set(inspector.get_table_names())
        assert inspector.get_pk_constraint("hosted_transparencyapi_snapshot_rows")[
            "constrained_columns"
        ] == ["snapshot_id", "export_id", "row_ordinal"]
        assert "ix_transparencyapi_rows_snapshot_facility_number" in {
            index["name"]
            for index in inspector.get_indexes("hosted_transparencyapi_snapshot_rows")
        }
        assert "autocomplete_search_text" in {
            column["name"]
            for column in inspector.get_columns("hosted_transparencyapi_snapshot_rows")
        }
        autocomplete_search.downgrade()
        assert "autocomplete_search_text" not in {
            column["name"]
            for column in sa.inspect(connection).get_columns(
                "hosted_transparencyapi_snapshot_rows"
            )
        }
        autocomplete_index.downgrade()
        assert "ix_transparencyapi_rows_snapshot_facility_number" not in {
            index["name"]
            for index in sa.inspect(connection).get_indexes(
                "hosted_transparencyapi_snapshot_rows"
            )
        }
        migration.downgrade()
        assert NEW_TABLES.isdisjoint(sa.inspect(connection).get_table_names())
    engine.dispose()


def test_transparencyapi_migration_blocks_downgrade_with_retained_history() -> None:
    lifecycle = _load("20260720_0008_source_snapshot_lifecycle.py")
    live_scope = _load("20260720_0009_live_arcgis_query_scope.py")
    migration = _load("20260721_0010_transparencyapi_source_snapshot.py")
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        lifecycle.op = operations
        live_scope.op = operations
        migration.op = operations
        lifecycle.upgrade()
        live_scope.upgrade()
        migration.upgrade()
        snapshots = sa.Table("hosted_source_snapshots", sa.MetaData(), autoload_with=connection)
        connection.execute(snapshots.insert().values(**_snapshot_values()))
        with pytest.raises(RuntimeError, match="snapshot history exists"):
            migration.downgrade()
        assert NEW_TABLES <= set(sa.inspect(connection).get_table_names())
        connection.execute(sa.delete(snapshots))
        migration.downgrade()
    engine.dispose()


def test_transparencyapi_scope_is_allowed_only_after_migration() -> None:
    lifecycle = _load("20260720_0008_source_snapshot_lifecycle.py")
    live_scope = _load("20260720_0009_live_arcgis_query_scope.py")
    migration = _load("20260721_0010_transparencyapi_source_snapshot.py")
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        lifecycle.op = operations
        live_scope.op = operations
        migration.op = operations
        lifecycle.upgrade()
        live_scope.upgrade()
        snapshots = sa.Table("hosted_source_snapshots", sa.MetaData(), autoload_with=connection)
        with pytest.raises(IntegrityError):
            connection.execute(snapshots.insert().values(**_snapshot_values()))
        migration.upgrade()
        snapshots = sa.Table("hosted_source_snapshots", sa.MetaData(), autoload_with=connection)
        connection.execute(snapshots.insert().values(**_snapshot_values()))
    engine.dispose()


def test_transparencyapi_migration_extends_single_head() -> None:
    migration = _load("20260721_0010_transparencyapi_source_snapshot.py")
    assert migration.revision == "20260721_0010"
    assert migration.down_revision == "20260720_0009"


def test_transparencyapi_autocomplete_index_migration_extends_single_head() -> None:
    migration = _load("20260722_0011_transparencyapi_autocomplete_index.py")

    assert migration.revision == "20260722_0011"
    assert migration.down_revision == "20260721_0010"


def test_transparencyapi_autocomplete_search_migration_extends_single_head() -> None:
    migration = _load("20260722_0012_transparencyapi_autocomplete_search.py")

    assert migration.revision == "20260722_0012"
    assert migration.down_revision == "20260722_0011"


def _snapshot_values() -> dict[str, Any]:
    return {
        "snapshot_id": "transparencyapi-" + "a" * 48,
        "source_family_id": "ccld-transparencyapi-facility-reference",
        "fixture_scope": "governed_transparencyapi",
        "observation_kind": "bulk_export_family",
        "lifecycle_state": "candidate",
        "manifest_ref": "manifest.json",
        "manifest_sha256": "1" * 64,
        "raw_payload_ref": "raw-response-set",
        "raw_payload_sha256": "2" * 64,
        "normalized_content_sha256": "3" * 64,
        "schema_fingerprint": "4" * 64,
        "domain_fingerprint": "5" * 64,
        "row_count": 0,
        "stored_row_count": 0,
        "duplicate_object_id_count": 0,
        "duplicate_facility_number_count": 0,
        "omitted_field_count": 0,
        "invalid_field_count": 0,
        "warning_count": 0,
        "rejection_reason_count": 0,
        "validation_report": {},
        "recorded_at": "2026-07-21T00:00:00Z",
    }


def _load(name: str) -> Any:
    path = Path(__file__).resolve().parents[2] / "migrations" / "versions" / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Could not load migration {name}.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
