from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import IntegrityError


def test_live_query_scope_migration_is_bounded_and_reversible() -> None:
    lifecycle = _load_migration("20260720_0008_source_snapshot_lifecycle.py")
    live_scope = _load_migration("20260720_0009_live_arcgis_query_scope.py")
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        lifecycle.op = operations
        lifecycle.upgrade()
        live_scope.op = operations
        live_scope.upgrade()

        snapshots = sa.Table("hosted_source_snapshots", sa.MetaData(), autoload_with=connection)
        connection.execute(snapshots.insert().values(**_live_snapshot_values()))
        assert connection.scalar(sa.select(sa.func.count()).select_from(snapshots)) == 1

        with pytest.raises(RuntimeError, match="live-query snapshot history exists"):
            live_scope.downgrade()
        connection.execute(sa.delete(snapshots))
        live_scope.downgrade()

        snapshots = sa.Table("hosted_source_snapshots", sa.MetaData(), autoload_with=connection)
        with pytest.raises(IntegrityError):
            connection.execute(snapshots.insert().values(**_live_snapshot_values()))

    engine.dispose()


def test_live_query_scope_migration_extends_the_single_head() -> None:
    migration = _load_migration("20260720_0009_live_arcgis_query_scope.py")
    assert migration.revision == "20260720_0009"
    assert migration.down_revision == "20260720_0008"


def _live_snapshot_values() -> dict[str, Any]:
    return {
        "snapshot_id": "arcgis-live-" + "a" * 48,
        "source_family_id": "arcgis-ccl-facilities-supplement",
        "fixture_scope": "governed_live_query",
        "observation_kind": "live_query",
        "lifecycle_state": "candidate",
        "manifest_ref": "snapshot-manifest.json",
        "manifest_sha256": "1" * 64,
        "raw_payload_ref": "lifecycle-source-records.json",
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
        "recorded_at": "2026-07-20T20:00:00Z",
    }


def _load_migration(name: str) -> Any:
    migration_path = Path(__file__).resolve().parents[2] / "migrations" / "versions" / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), migration_path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Could not load migration {name}.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
