from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import Connection

from ccld_complaints.hosted_app.source_snapshot_lifecycle import (
    accept_arcgis_fixture_snapshot,
    promote_arcgis_fixture_snapshot,
    rollback_arcgis_fixture_snapshot,
    source_snapshot_disappearances,
    source_snapshot_metadata,
    source_snapshot_pointers,
    source_snapshot_rows,
    source_snapshots,
    stage_arcgis_fixture_snapshot,
    validate_arcgis_fixture_snapshot,
)

POSTGRES_TEST_URL_ENV = "CCLD_TEST_POSTGRES_URL"
POSTGRES_SCHEMA_MUTATION_ENV = "CCLD_TEST_POSTGRES_ALLOW_SCHEMA_MUTATION"
FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "source_snapshot_lifecycle"


@pytest.fixture(scope="module")
def postgres_lifecycle_connection() -> Iterator[Connection]:
    database_url = os.environ.get(POSTGRES_TEST_URL_ENV, "").strip()
    mutation_allowed = os.environ.get(POSTGRES_SCHEMA_MUTATION_ENV, "").strip() == "1"
    if not database_url or not mutation_allowed:
        pytest.skip(
            f"Set {POSTGRES_TEST_URL_ENV} and {POSTGRES_SCHEMA_MUTATION_ENV}=1 "
            "to run the isolated PostgreSQL snapshot lifecycle regression."
        )
    if not database_url.startswith("postgresql+"):
        pytest.fail(f"{POSTGRES_TEST_URL_ENV} must use a PostgreSQL SQLAlchemy URL.")

    schema_name = f"issue518_lifecycle_{uuid.uuid4().hex}"
    engine = sa.create_engine(database_url)
    with engine.connect() as connection:
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema_name}"')
        connection.exec_driver_sql(f'SET search_path TO "{schema_name}"')
        source_snapshot_metadata.create_all(connection)
        connection.commit()
        try:
            yield connection
        finally:
            connection.rollback()
            connection.exec_driver_sql("SET search_path TO public")
            connection.exec_driver_sql(f'DROP SCHEMA "{schema_name}" CASCADE')
            connection.commit()
    engine.dispose()


def test_postgres_snapshot_promotion_and_rollback_preserve_complete_history(
    postgres_lifecycle_connection: Connection,
) -> None:
    connection = postgres_lifecycle_connection
    first = _stage_accept_promote(connection, "snapshot-a-manifest.json")
    second = _stage_accept_promote(connection, "snapshot-b-manifest.json")
    connection.commit()

    pointer = connection.execute(sa.select(source_snapshot_pointers)).mappings().one()
    assert pointer["active_snapshot_id"] == second
    assert pointer["prior_accepted_snapshot_id"] == first
    assert connection.scalar(sa.select(sa.func.count()).select_from(source_snapshots)) == 2
    assert connection.scalar(sa.select(sa.func.count()).select_from(source_snapshot_rows)) == 5
    assert connection.scalar(
        sa.select(sa.func.count()).select_from(source_snapshot_disappearances)
    ) == 2

    rolled_back = rollback_arcgis_fixture_snapshot(
        connection,
        expected_active_snapshot_id=second,
        rolled_back_at="2026-07-20T17:00:00+00:00",
    )
    connection.commit()
    assert rolled_back.active_snapshot_id == first
    assert rolled_back.prior_accepted_snapshot_id == second
    assert set(
        connection.execute(sa.select(source_snapshots.c.lifecycle_state)).scalars()
    ) == {"accepted"}


def _stage_accept_promote(connection: Connection, manifest_name: str) -> str:
    inspection = stage_arcgis_fixture_snapshot(connection, FIXTURE_ROOT / manifest_name)
    assert validate_arcgis_fixture_snapshot(
        connection,
        inspection.snapshot_id,
        validated_at="2026-07-20T16:00:00+00:00",
    ) == "validated"
    accept_arcgis_fixture_snapshot(
        connection,
        inspection.snapshot_id,
        accepted_at="2026-07-20T16:01:00+00:00",
    )
    promote_arcgis_fixture_snapshot(
        connection,
        inspection.snapshot_id,
        promoted_at="2026-07-20T16:02:00+00:00",
    )
    return inspection.snapshot_id
