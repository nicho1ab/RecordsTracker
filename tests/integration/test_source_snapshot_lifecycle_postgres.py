from __future__ import annotations

import json
import os
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import Connection

from ccld_complaints.connectors.arcgis_ccl_facilities.contract import (
    ARCGIS_ITEM_URL,
    ARCGIS_LAYER_URL,
    ARCGIS_QUERY_URL,
    ARCGIS_SERVICE_URL,
    CATALOG_URL,
    LICENSES_URL,
)
from ccld_complaints.connectors.arcgis_ccl_facilities.live_query import (
    capture_live_arcgis_query_snapshot,
)
from ccld_complaints.hosted_app.reviewer_created_state import hosted_reviewer_created_state
from ccld_complaints.hosted_app.seeded_import import (
    hosted_seeded_import_metadata,
    import_seeded_corpus_artifact,
    load_seeded_corpus_artifact,
)
from ccld_complaints.hosted_app.source_snapshot_lifecycle import (
    ISOLATED_NONPRODUCTION_SCOPE,
    accept_arcgis_fixture_snapshot,
    accept_arcgis_live_query_snapshot,
    promote_arcgis_fixture_snapshot,
    promote_arcgis_live_query_snapshot,
    rollback_arcgis_fixture_snapshot,
    rollback_arcgis_live_query_snapshot,
    source_snapshot_disappearances,
    source_snapshot_metadata,
    source_snapshot_pointers,
    source_snapshot_rows,
    source_snapshots,
    stage_arcgis_fixture_snapshot,
    stage_arcgis_live_query_snapshot,
    validate_arcgis_fixture_snapshot,
    validate_arcgis_live_query_snapshot,
)
from ccld_complaints.statewide_facility_source_evaluation import (
    HttpResponse,
    canonical_json_bytes,
    safe_endpoint_identity,
)

POSTGRES_TEST_URL_ENV = "CCLD_TEST_POSTGRES_URL"
POSTGRES_SCHEMA_MUTATION_ENV = "CCLD_TEST_POSTGRES_ALLOW_SCHEMA_MUTATION"
LIVE_MANIFEST_ENV = "CCLD_TEST_ARCGIS_LIVE_MANIFEST"
FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "source_snapshot_lifecycle"
LIVE_FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "arcgis_ccl_facilities"
SEEDED_CORPUS_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "hosted_seeded_corpus"
    / "validated_seeded_corpus.json"
)
REVIEWER_STATE_ID = "issue518-reviewer-state-preservation"
REVIEWER_SOURCE_RECORD_KEY = "complaint:ccld:complaint:32-CR-20220407124448"


class _FixtureTransport:
    def __init__(self) -> None:
        self.item = _fixture_json("item.json")
        self.service = _fixture_json("service.json")
        self.layer = _fixture_json("layer.json")
        self.rows = [
            dict(feature["attributes"])
            for feature in _fixture_json("page-00000.json")["features"]
        ]

    def get(self, url: str, *, timeout_seconds: float) -> HttpResponse:
        assert timeout_seconds > 0
        endpoint = safe_endpoint_identity(url)
        content_type = "application/json"
        if endpoint == CATALOG_URL:
            body = (LIVE_FIXTURE_ROOT / "catalog.html").read_bytes()
            content_type = "text/html"
        elif endpoint == LICENSES_URL:
            body = (LIVE_FIXTURE_ROOT / "licenses.html").read_bytes()
            content_type = "text/html"
        elif endpoint == ARCGIS_ITEM_URL:
            body = canonical_json_bytes(self.item)
        elif endpoint == ARCGIS_SERVICE_URL:
            body = canonical_json_bytes(self.service)
        elif endpoint == ARCGIS_LAYER_URL:
            body = canonical_json_bytes(self.layer)
        elif endpoint == ARCGIS_QUERY_URL:
            params = parse_qs(urlsplit(url).query)
            if params.get("returnIdsOnly") == ["true"]:
                payload: dict[str, Any] = {
                    "objectIdFieldName": "ObjectId",
                    "objectIds": [row["ObjectId"] for row in self.rows],
                }
            else:
                offset = int(params["resultOffset"][0])
                count = int(params["resultRecordCount"][0])
                payload = {
                    "features": [
                        {"attributes": row}
                        for row in self.rows[offset : offset + count]
                    ]
                }
            body = canonical_json_bytes(payload)
        else:
            raise AssertionError(f"Unexpected fixture endpoint: {endpoint}")
        return HttpResponse(
            request_url=url,
            final_url=url,
            status=200,
            content_type=content_type,
            body=body,
        )


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
        hosted_seeded_import_metadata.create_all(connection)
        import_seeded_corpus_artifact(
            connection,
            load_seeded_corpus_artifact(SEEDED_CORPUS_FIXTURE),
        )
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


def test_postgres_live_candidate_preserves_prior_and_unrelated_reviewer_state(
    postgres_lifecycle_connection: Connection,
    tmp_path: Path,
) -> None:
    connection = postgres_lifecycle_connection
    pointer = connection.execute(sa.select(source_snapshot_pointers)).mappings().one()
    prior_snapshot_id = str(pointer["active_snapshot_id"])
    _ensure_reviewer_state(connection)
    reviewer_state_before = _reviewer_state_record(connection)

    capture = capture_live_arcgis_query_snapshot(
        tmp_path,
        transport=_FixtureTransport(),
        accessed_at="2026-07-20T20:00:00Z",
    )
    live = stage_arcgis_live_query_snapshot(
        connection,
        capture.manifest_path,
        execution_scope=ISOLATED_NONPRODUCTION_SCOPE,
    )
    assert validate_arcgis_live_query_snapshot(
        connection,
        live.snapshot_id,
        validated_at="2026-07-20T20:01:00Z",
        execution_scope=ISOLATED_NONPRODUCTION_SCOPE,
    ) == "validated"
    accept_arcgis_live_query_snapshot(
        connection,
        live.snapshot_id,
        accepted_at="2026-07-20T20:02:00Z",
        execution_scope=ISOLATED_NONPRODUCTION_SCOPE,
    )
    promoted = promote_arcgis_live_query_snapshot(
        connection,
        live.snapshot_id,
        promoted_at="2026-07-20T20:03:00Z",
        execution_scope=ISOLATED_NONPRODUCTION_SCOPE,
    )
    assert promoted.prior_accepted_snapshot_id == prior_snapshot_id
    rolled_back = rollback_arcgis_live_query_snapshot(
        connection,
        expected_active_snapshot_id=live.snapshot_id,
        rolled_back_at="2026-07-20T20:04:00Z",
        execution_scope=ISOLATED_NONPRODUCTION_SCOPE,
    )
    assert rolled_back.active_snapshot_id == prior_snapshot_id
    assert _reviewer_state_record(connection) == reviewer_state_before
    connection.commit()


def test_postgres_controlled_real_candidate_completes_and_rolls_back(
    postgres_lifecycle_connection: Connection,
) -> None:
    manifest_value = os.environ.get(LIVE_MANIFEST_ENV, "").strip()
    if not manifest_value:
        pytest.skip(
            f"Set {LIVE_MANIFEST_ENV} to a governed ignored live manifest for the controlled "
            "real-candidate lifecycle regression."
        )
    repository_root = Path(__file__).resolve().parents[2]
    governed_root = (
        repository_root / "data/raw/source-profiling/issue-518-live-query"
    ).resolve()
    manifest_path = Path(manifest_value).resolve()
    if not manifest_path.is_relative_to(governed_root):
        pytest.fail(f"{LIVE_MANIFEST_ENV} must be inside the governed ignored evidence root.")

    connection = postgres_lifecycle_connection
    pointer = connection.execute(sa.select(source_snapshot_pointers)).mappings().one()
    prior_snapshot_id = str(pointer["active_snapshot_id"])
    prior_snapshot_count = connection.scalar(
        sa.select(sa.func.count()).select_from(source_snapshots)
    )
    reviewer_state_before = _reviewer_state_record(connection)

    live = stage_arcgis_live_query_snapshot(
        connection,
        manifest_path,
        execution_scope=ISOLATED_NONPRODUCTION_SCOPE,
    )
    assert live.validation_report["row_count"] == 29_871
    assert live.validation_report["stored_row_count"] == 29_871
    assert live.validation_report["duplicate_object_id_count"] == 0
    assert live.validation_report["duplicate_facility_number_count"] == 157
    assert live.rejection_reasons == ()
    assert validate_arcgis_live_query_snapshot(
        connection,
        live.snapshot_id,
        validated_at="2026-07-20T21:10:00Z",
        execution_scope=ISOLATED_NONPRODUCTION_SCOPE,
    ) == "validated"
    accept_arcgis_live_query_snapshot(
        connection,
        live.snapshot_id,
        accepted_at="2026-07-20T21:11:00Z",
        execution_scope=ISOLATED_NONPRODUCTION_SCOPE,
    )
    promoted = promote_arcgis_live_query_snapshot(
        connection,
        live.snapshot_id,
        promoted_at="2026-07-20T21:12:00Z",
        execution_scope=ISOLATED_NONPRODUCTION_SCOPE,
    )
    assert promoted.prior_accepted_snapshot_id == prior_snapshot_id
    rolled_back = rollback_arcgis_live_query_snapshot(
        connection,
        expected_active_snapshot_id=live.snapshot_id,
        rolled_back_at="2026-07-20T21:13:00Z",
        execution_scope=ISOLATED_NONPRODUCTION_SCOPE,
    )
    assert rolled_back.active_snapshot_id == prior_snapshot_id
    assert rolled_back.prior_accepted_snapshot_id == live.snapshot_id
    assert _reviewer_state_record(connection) == reviewer_state_before
    assert connection.scalar(sa.select(sa.func.count()).select_from(source_snapshots)) == (
        int(prior_snapshot_count or 0) + 1
    )
    connection.commit()


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


def _fixture_json(name: str) -> dict[str, Any]:
    value = json.loads((LIVE_FIXTURE_ROOT / name).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _ensure_reviewer_state(connection: Connection) -> None:
    if _reviewer_state_record(connection, required=False) is not None:
        return
    connection.execute(
        hosted_reviewer_created_state.insert().values(
            reviewer_state_id=REVIEWER_STATE_ID,
            source_record_key=REVIEWER_SOURCE_RECORD_KEY,
            scope_type="seeded_corpus",
            scope_id="seeded-ccld-fixture-2026-06-13",
            state_kind="review_item_state_scaffold",
            state_payload={"note": "unchanged", "payload_kind": "reviewer_note_scaffold"},
            created_at="2026-07-20T19:45:00Z",
            created_by_provider_subject="issue518-test-reviewer",
            created_by_provider_issuer="issue518-test-provider",
            created_by_display_name="Issue 518 Test Reviewer",
            created_by_actor_category="tester",
            authorization_permission="reviewer_state_write",
        )
    )


def _reviewer_state_record(
    connection: Connection,
    *,
    required: bool = True,
) -> dict[str, Any] | None:
    row = connection.execute(
        sa.select(hosted_reviewer_created_state).where(
            hosted_reviewer_created_state.c.reviewer_state_id == REVIEWER_STATE_ID
        )
    ).mappings().one_or_none()
    if row is None and required:
        raise AssertionError("Expected the actual reviewer-created state row to remain present.")
    return dict(row) if row is not None else None
