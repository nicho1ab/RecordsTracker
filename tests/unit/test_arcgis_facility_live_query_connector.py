from __future__ import annotations

import json
from copy import deepcopy
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
    ARCGIS_RAW_FIELDS,
    ARCGIS_SERVICE_URL,
    CATALOG_URL,
    LICENSES_URL,
    LIVE_QUERY_SCOPE,
    provisional_attribution,
)
from ccld_complaints.connectors.arcgis_ccl_facilities.live_query import (
    LiveArcGisConnectorError,
    capture_live_arcgis_query_snapshot,
    validate_governed_request,
)
from ccld_complaints.hosted_app.source_snapshot_lifecycle import (
    ISOLATED_NONPRODUCTION_SCOPE,
    accept_arcgis_fixture_snapshot,
    accept_arcgis_live_query_snapshot,
    inspect_arcgis_live_query_package,
    promote_arcgis_fixture_snapshot,
    promote_arcgis_live_query_snapshot,
    rollback_arcgis_fixture_snapshot,
    rollback_arcgis_live_query_snapshot,
    source_snapshot_metadata,
    source_snapshot_pointers,
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

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "arcgis_ccl_facilities"
LIFECYCLE_FIXTURE_ROOT = (
    Path(__file__).resolve().parents[1] / "fixtures" / "source_snapshot_lifecycle"
)
ACCESSED_AT = "2026-07-20T20:00:00Z"


class FixtureTransport:
    def __init__(self) -> None:
        self.item = _json("item.json")
        self.service = _json("service.json")
        self.layer = _json("layer.json")
        self.rows = [
            dict(feature["attributes"])
            for feature in _json("page-00000.json")["features"]
        ]
        self.object_ids = [int(row["ObjectId"]) for row in self.rows]
        self.requested_urls: list[str] = []
        self.redirect_endpoint: str | None = None

    def get(self, url: str, *, timeout_seconds: float) -> HttpResponse:
        assert timeout_seconds > 0
        validate_governed_request(url)
        self.requested_urls.append(url)
        endpoint = safe_endpoint_identity(url)
        content_type = "application/json"
        if endpoint == CATALOG_URL:
            body = (FIXTURE_ROOT / "catalog.html").read_bytes()
            content_type = "text/html"
        elif endpoint == LICENSES_URL:
            body = (FIXTURE_ROOT / "licenses.html").read_bytes()
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
                    "objectIds": self.object_ids,
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
            raise AssertionError(f"Unexpected test endpoint: {endpoint}")
        final_url = self.redirect_endpoint or url
        return HttpResponse(
            request_url=url,
            final_url=final_url,
            status=200,
            content_type=content_type,
            body=body,
            redirect_chain=(self.redirect_endpoint,) if self.redirect_endpoint else (),
        )


@pytest.fixture
def lifecycle_connection() -> Connection:
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    connection = engine.connect()
    source_snapshot_metadata.create_all(connection)
    try:
        yield connection
    finally:
        connection.close()
        engine.dispose()


def test_live_capture_preserves_exact_contract_and_terminal_page(tmp_path: Path) -> None:
    transport = FixtureTransport()
    capture = capture_live_arcgis_query_snapshot(
        tmp_path,
        page_size=1,
        transport=transport,
        accessed_at=ACCESSED_AT,
    )

    assert capture.row_count == 2
    assert capture.unique_object_id_count == 2
    assert capture.unique_facility_number_count == 1
    assert capture.duplicate_facility_number_count == 1
    assert capture.nonempty_page_count == 2
    assert capture.terminal_offset == 2
    assert capture.evidence_directory.relative_to(tmp_path).as_posix() == (
        "data/raw/source-profiling/issue-518-live-query/20260720T200000Z"
    )

    manifest = json.loads(capture.manifest_path.read_text(encoding="utf-8"))
    assert manifest["validation"]["id_reconciliation"] == "exact"
    assert manifest["validation"]["empty_terminal_page"] is True
    assert manifest["validation"]["raw_733_label_invented"] is False
    assert manifest["schema_fields"][0]["name"] == "FAC_LATITUDE"
    assert manifest["schema_fields"][-1]["name"] == "ObjectId"
    assert manifest["provisional_attribution"] == provisional_attribution(
        capture.snapshot_id, "2026-07-20"
    )
    assert manifest["catalog_identity"]["license_version"] is None
    assert manifest["source_identity"]["item_id"] == "db31b0884a074cff9260facb3f2ade45"
    assert manifest["page_evidence"]["pages"][-1]["row_count"] == 0
    assert len(manifest["retrieval_artifacts"]) == 9
    assert all(artifact["redirect_chain"] == [] for artifact in manifest["retrieval_artifacts"])

    inspection = inspect_arcgis_live_query_package(
        capture.manifest_path,
        execution_scope=ISOLATED_NONPRODUCTION_SCOPE,
    )
    assert inspection.storage_scope == LIVE_QUERY_SCOPE
    assert inspection.rejection_reasons == ()
    assert inspection.normalized_content_sha256 == capture.normalized_content_sha256
    assert inspection.rows[0]["normalized_record"]["raw_type_code"]["value"] == 733
    assert "client_served" not in inspection.rows[0]["normalized_record"]
    assert "facility_county_number" not in inspection.rows[0]["normalized_record"]


def test_live_capture_reconciles_id_set_exactly(tmp_path: Path) -> None:
    transport = FixtureTransport()
    transport.object_ids.append(999999)

    with pytest.raises(LiveArcGisConnectorError, match="omitted=1, unexpected=0"):
        capture_live_arcgis_query_snapshot(
            tmp_path,
            transport=transport,
            accessed_at=ACCESSED_AT,
        )

    evidence_directory = (
        tmp_path / "data/raw/source-profiling/issue-518-live-query/20260720T200000Z"
    )
    assert (evidence_directory / "object-ids.json").exists()
    assert not (evidence_directory / "snapshot-manifest.json").exists()


def test_unchanged_content_keeps_distinct_retrieval_snapshot_identity(tmp_path: Path) -> None:
    first = capture_live_arcgis_query_snapshot(
        tmp_path,
        transport=FixtureTransport(),
        accessed_at="2026-07-20T20:00:00Z",
    )
    second = capture_live_arcgis_query_snapshot(
        tmp_path,
        transport=FixtureTransport(),
        accessed_at="2026-07-20T20:01:00Z",
    )

    assert first.snapshot_id != second.snapshot_id
    assert first.normalized_content_sha256 == second.normalized_content_sha256
    assert first.manifest_path != second.manifest_path


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda transport: transport.rows.reverse(), "not ordered"),
        (
            lambda transport: transport.rows.__setitem__(1, dict(transport.rows[0])),
            "duplicated or not ordered",
        ),
        (
            lambda transport: transport.rows[0].pop("COUNTY"),
            "19-field boundary",
        ),
    ],
)
def test_live_capture_rejects_reordering_duplicates_and_omissions(
    tmp_path: Path,
    mutator: Any,
    message: str,
) -> None:
    transport = FixtureTransport()
    mutator(transport)

    with pytest.raises(LiveArcGisConnectorError, match=message):
        capture_live_arcgis_query_snapshot(
            tmp_path,
            transport=transport,
            accessed_at=ACCESSED_AT,
        )


def test_live_capture_rejects_schema_and_domain_drift(tmp_path: Path) -> None:
    transport = FixtureTransport()
    transport.layer = deepcopy(transport.layer)
    transport.layer["fields"][0]["domain"] = {"type": "codedValue"}

    with pytest.raises(LiveArcGisConnectorError, match="unapproved domain"):
        capture_live_arcgis_query_snapshot(
            tmp_path,
            transport=transport,
            accessed_at=ACCESSED_AT,
        )


def test_live_capture_rejects_redirects(tmp_path: Path) -> None:
    transport = FixtureTransport()
    transport.redirect_endpoint = "https://example.invalid/redirected"

    with pytest.raises(LiveArcGisConnectorError, match="attempted a redirect"):
        capture_live_arcgis_query_snapshot(
            tmp_path,
            transport=transport,
            accessed_at=ACCESSED_AT,
        )


@pytest.mark.parametrize(
    "url",
    [
        "http://services.arcgis.com/XLPEppdz2H9dOiqp/arcgis/rest/services/"
        "CDSS_CCL_Facilities/FeatureServer/0?f=json",
        f"{ARCGIS_LAYER_URL}?f=html",
        f"{ARCGIS_LAYER_URL}?f=json&token=secret-placeholder",
        f"{ARCGIS_QUERY_URL}?where=ObjectId%3E0&returnIdsOnly=true&f=json",
        f"{ARCGIS_QUERY_URL}?where=1%3D1&returnIdsOnly=true&f=json#fragment",
        "https://services.arcgis.com/other/path?f=json",
    ],
)
def test_request_policy_rejects_unapproved_host_path_scheme_and_parameters(url: str) -> None:
    with pytest.raises(LiveArcGisConnectorError):
        validate_governed_request(url)


def test_request_policy_accepts_only_approved_metadata_and_query_shapes() -> None:
    for url in (
        CATALOG_URL,
        LICENSES_URL,
        f"{ARCGIS_ITEM_URL}?f=pjson",
        f"{ARCGIS_SERVICE_URL}?f=json",
        f"{ARCGIS_LAYER_URL}?f=json",
        f"{ARCGIS_QUERY_URL}?where=1%3D1&returnIdsOnly=true&f=json",
        (
            f"{ARCGIS_QUERY_URL}?where=1%3D1&outFields="
            f"{','.join(ARCGIS_RAW_FIELDS)}&returnGeometry=false&"
            "orderByFields=ObjectId+ASC&resultOffset=0&resultRecordCount=1000&f=json"
        ),
    ):
        validate_governed_request(url)


def test_live_candidate_reuses_lifecycle_and_preserves_prior_and_reviewer_state(
    tmp_path: Path,
    lifecycle_connection: Connection,
) -> None:
    reviewer_state = sa.Table(
        "reviewer_created_state_sentinel",
        sa.MetaData(),
        sa.Column("review_item_id", sa.String(40), primary_key=True),
        sa.Column("note", sa.Text(), nullable=False),
    )
    reviewer_state.create(lifecycle_connection)
    lifecycle_connection.execute(
        reviewer_state.insert().values(review_item_id="synthetic-review", note="unchanged")
    )

    prior = stage_arcgis_fixture_snapshot(
        lifecycle_connection,
        LIFECYCLE_FIXTURE_ROOT / "snapshot-a-manifest.json",
    )
    assert validate_arcgis_fixture_snapshot(
        lifecycle_connection,
        prior.snapshot_id,
        validated_at="2026-07-20T19:50:00Z",
    ) == "validated"
    accept_arcgis_fixture_snapshot(
        lifecycle_connection,
        prior.snapshot_id,
        accepted_at="2026-07-20T19:51:00Z",
    )
    promote_arcgis_fixture_snapshot(
        lifecycle_connection,
        prior.snapshot_id,
        promoted_at="2026-07-20T19:52:00Z",
    )

    capture = capture_live_arcgis_query_snapshot(
        tmp_path,
        transport=FixtureTransport(),
        accessed_at=ACCESSED_AT,
    )
    live = stage_arcgis_live_query_snapshot(
        lifecycle_connection,
        capture.manifest_path,
        execution_scope=ISOLATED_NONPRODUCTION_SCOPE,
    )
    assert live.disappearances
    assert validate_arcgis_live_query_snapshot(
        lifecycle_connection,
        live.snapshot_id,
        validated_at="2026-07-20T20:01:00Z",
        execution_scope=ISOLATED_NONPRODUCTION_SCOPE,
    ) == "validated"
    accept_arcgis_live_query_snapshot(
        lifecycle_connection,
        live.snapshot_id,
        accepted_at="2026-07-20T20:02:00Z",
        execution_scope=ISOLATED_NONPRODUCTION_SCOPE,
    )
    pointer = promote_arcgis_live_query_snapshot(
        lifecycle_connection,
        live.snapshot_id,
        promoted_at="2026-07-20T20:03:00Z",
        execution_scope=ISOLATED_NONPRODUCTION_SCOPE,
    )
    assert pointer.active_snapshot_id == live.snapshot_id
    assert pointer.prior_accepted_snapshot_id == prior.snapshot_id

    rolled_back = rollback_arcgis_live_query_snapshot(
        lifecycle_connection,
        expected_active_snapshot_id=live.snapshot_id,
        rolled_back_at="2026-07-20T20:04:00Z",
        execution_scope=ISOLATED_NONPRODUCTION_SCOPE,
    )
    assert rolled_back.active_snapshot_id == prior.snapshot_id
    assert rolled_back.prior_accepted_snapshot_id == live.snapshot_id
    assert rollback_arcgis_live_query_snapshot(
        lifecycle_connection,
        expected_active_snapshot_id=live.snapshot_id,
        rolled_back_at="2026-07-20T20:05:00Z",
        execution_scope=ISOLATED_NONPRODUCTION_SCOPE,
    ) == rolled_back
    with pytest.raises(ValueError, match="repository_synthetic_fixture"):
        rollback_arcgis_fixture_snapshot(
            lifecycle_connection,
            expected_active_snapshot_id=live.snapshot_id,
            rolled_back_at="2026-07-20T20:06:00Z",
        )
    assert lifecycle_connection.execute(sa.select(reviewer_state.c.note)).scalar_one() == (
        "unchanged"
    )
    scopes = set(
        lifecycle_connection.execute(sa.select(source_snapshots.c.fixture_scope)).scalars()
    )
    assert scopes == {"repository_synthetic_fixture", LIVE_QUERY_SCOPE}


def test_live_lifecycle_rejects_wrong_execution_scope_and_tampered_manifest(
    tmp_path: Path,
    lifecycle_connection: Connection,
) -> None:
    capture = capture_live_arcgis_query_snapshot(
        tmp_path,
        transport=FixtureTransport(),
        accessed_at=ACCESSED_AT,
    )
    with pytest.raises(ValueError, match="isolated_nonproduction"):
        stage_arcgis_live_query_snapshot(
            lifecycle_connection,
            capture.manifest_path,
            execution_scope="production",
        )

    manifest = json.loads(capture.manifest_path.read_text(encoding="utf-8"))
    manifest["provisional_attribution"] = "changed"
    capture.manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    rejected = stage_arcgis_live_query_snapshot(
        lifecycle_connection,
        capture.manifest_path,
        execution_scope=ISOLATED_NONPRODUCTION_SCOPE,
    )
    assert any("provisional attribution" in reason for reason in rejected.rejection_reasons)
    assert validate_arcgis_live_query_snapshot(
        lifecycle_connection,
        rejected.snapshot_id,
        validated_at="2026-07-20T20:05:00Z",
        execution_scope=ISOLATED_NONPRODUCTION_SCOPE,
    ) == "rejected"
    assert lifecycle_connection.execute(sa.select(source_snapshot_pointers)).first() is None


def _json(name: str) -> dict[str, Any]:
    value = json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value
