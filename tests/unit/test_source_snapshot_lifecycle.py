from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from ccld_complaints.hosted_app.source_snapshot_lifecycle import (
    ARCGIS_NORMALIZED_FIELD_SOURCES,
    ARCGIS_RAW_FIELDS,
    ARCGIS_SUPPLEMENT_SOURCE_FAMILY_ID,
    OfflineSnapshotLifecycleError,
    SnapshotInspection,
    accept_arcgis_fixture_snapshot,
    inspect_arcgis_fixture_package,
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

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "source_snapshot_lifecycle"
SNAPSHOT_A = FIXTURE_ROOT / "snapshot-a-manifest.json"
SNAPSHOT_B = FIXTURE_ROOT / "snapshot-b-manifest.json"
REJECTED_SNAPSHOT = FIXTURE_ROOT / "rejected-manifest.json"
VALIDATED_AT = "2026-07-20T15:00:00+00:00"
ACCEPTED_AT = "2026-07-20T15:01:00+00:00"
PROMOTED_AT = "2026-07-20T15:02:00+00:00"


@pytest.fixture()
def lifecycle_connection() -> Connection:
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    connection = engine.connect()
    source_snapshot_metadata.create_all(connection)
    try:
        yield connection
    finally:
        connection.close()
        engine.dispose()


def test_synthetic_snapshot_preserves_exact_raw_and_approved_normalized_boundaries() -> None:
    inspection = inspect_arcgis_fixture_package(SNAPSHOT_A)

    assert inspection.rejection_reasons == ()
    assert inspection.validation_report["row_count"] == 3
    assert inspection.validation_report["stored_row_count"] == 3
    assert inspection.validation_report["duplicate_facility_number_count"] == 1
    assert len(inspection.schema_fingerprint) == 64
    assert len(inspection.domain_fingerprint) == 64
    assert len(inspection.normalized_content_sha256) == 64

    first = inspection.rows[0]
    assert tuple(first["raw_record"]) == ARCGIS_RAW_FIELDS
    assert tuple(first["normalized_record"]) == tuple(ARCGIS_NORMALIZED_FIELD_SOURCES)
    assert "CLIENT_SERVED" in first["raw_record"]
    assert "FAC_CO_NBR" in first["raw_record"]
    assert "client_served" not in first["normalized_record"]
    assert "fac_co_nbr" not in first["normalized_record"]
    assert "facility_type" not in first["normalized_record"]
    assert "status" not in first["normalized_record"]

    raw_type = first["normalized_record"]["raw_type_code"]
    assert raw_type == {"source_field": "TYPE", "state": "populated", "value": 733}
    assert any("unresolved raw TYPE value 733" in warning for warning in _warnings(inspection))


def test_semantic_states_distinguish_null_blank_unavailable_absent_and_invalid() -> None:
    accepted = inspect_arcgis_fixture_package(SNAPSHOT_A)
    second = accepted.rows[1]["normalized_record"]
    third = accepted.rows[2]["normalized_record"]
    rejected = inspect_arcgis_fixture_package(REJECTED_SNAPSHOT)
    rejected_row = rejected.rows[0]["normalized_record"]

    assert second["source_latitude_raw"]["state"] == "null"
    assert second["program_type_source"]["state"] == "blank"
    assert second["telephone_source"]["state"] == "unavailable"
    assert third["facility_number"]["state"] == "null"
    assert third["county_source"]["state"] == "unavailable"
    assert rejected_row["city_source"]["state"] == "absent"
    assert rejected_row["capacity_source"]["state"] == "invalid"
    assert rejected.validation_report["omitted_field_count"] == 1
    assert rejected.validation_report["invalid_field_count"] == 1


def test_duplicate_object_id_is_rejected_without_selecting_a_winning_row(
    tmp_path: Path,
) -> None:
    raw_payload = json.loads((FIXTURE_ROOT / "snapshot-a-raw.json").read_text(encoding="utf-8"))
    raw_payload["records"][1]["ObjectId"] = raw_payload["records"][0]["ObjectId"]
    manifest_path = _write_variant_fixture(tmp_path, raw_payload)

    inspection = inspect_arcgis_fixture_package(manifest_path)

    assert inspection.validation_report["duplicate_object_id_count"] == 1
    assert inspection.rows == ()
    assert any("duplicate ObjectId identities" in reason for reason in inspection.rejection_reasons)


def test_normalized_content_fingerprint_is_independent_of_fixture_row_order(
    tmp_path: Path,
) -> None:
    original = inspect_arcgis_fixture_package(SNAPSHOT_A)
    raw_payload = json.loads((FIXTURE_ROOT / "snapshot-a-raw.json").read_text(encoding="utf-8"))
    raw_payload["records"].reverse()
    reordered = inspect_arcgis_fixture_package(_write_variant_fixture(tmp_path, raw_payload))

    assert reordered.raw_payload_sha256 != original.raw_payload_sha256
    assert reordered.normalized_content_sha256 == original.normalized_content_sha256
    assert [row["source_object_id"] for row in reordered.rows] == [910001, 910002, 910003]


def test_schema_and_domain_fingerprints_detect_drift() -> None:
    first = inspect_arcgis_fixture_package(SNAPSHOT_A)
    second = inspect_arcgis_fixture_package(SNAPSHOT_B)
    drifted = inspect_arcgis_fixture_package(REJECTED_SNAPSHOT)

    assert second.schema_fingerprint == first.schema_fingerprint
    assert second.domain_fingerprint == first.domain_fingerprint
    assert drifted.schema_fingerprint != first.schema_fingerprint
    assert drifted.domain_fingerprint != first.domain_fingerprint


def test_first_candidate_rejects_source_type_drift_without_needing_an_active_baseline(
    tmp_path: Path,
) -> None:
    raw_payload = json.loads((FIXTURE_ROOT / "snapshot-a-raw.json").read_text(encoding="utf-8"))
    manifest_path = _write_variant_fixture(tmp_path, raw_payload)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema_fields"][5]["type"] = "esriFieldTypeString"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    inspection = inspect_arcgis_fixture_package(manifest_path)

    assert any(
        "STATUS type or nullability differs" in reason
        for reason in inspection.rejection_reasons
    )


def test_snapshot_and_object_id_form_identity_while_facility_number_is_nonunique(
    lifecycle_connection: Connection,
) -> None:
    first = stage_arcgis_fixture_snapshot(lifecycle_connection, SNAPSHOT_A)
    _accept_and_promote(lifecycle_connection, first.snapshot_id)
    second = stage_arcgis_fixture_snapshot(lifecycle_connection, SNAPSHOT_B)

    grouped_rows = lifecycle_connection.execute(
        sa.select(source_snapshot_rows).where(
            source_snapshot_rows.c.snapshot_id == first.snapshot_id,
            source_snapshot_rows.c.facility_number == "SYNTHETIC-GROUP-A",
        )
    ).mappings().all()
    shared_object_id_rows = lifecycle_connection.execute(
        sa.select(source_snapshot_rows.c.snapshot_id).where(
            source_snapshot_rows.c.source_object_id == 910001
        )
    ).scalars().all()

    assert len(grouped_rows) == 2
    assert {row["source_object_id"] for row in grouped_rows} == {910001, 910002}
    assert set(shared_object_id_rows) == {first.snapshot_id, second.snapshot_id}
    assert len({row["row_fingerprint"] for row in grouped_rows}) == 2


def test_candidate_validation_acceptance_promotion_and_rollback_are_deterministic(
    lifecycle_connection: Connection,
) -> None:
    reviewer_state = sa.Table(
        "reviewer_state_sentinel",
        sa.MetaData(),
        sa.Column("review_item_id", sa.String(40), primary_key=True),
        sa.Column("note", sa.Text(), nullable=False),
    )
    reviewer_state.create(lifecycle_connection)
    lifecycle_connection.execute(
        reviewer_state.insert().values(review_item_id="synthetic-review", note="unchanged")
    )

    first = stage_arcgis_fixture_snapshot(lifecycle_connection, SNAPSHOT_A)
    assert _state(lifecycle_connection, first.snapshot_id) == "candidate"
    assert validate_arcgis_fixture_snapshot(
        lifecycle_connection,
        first.snapshot_id,
        validated_at=VALIDATED_AT,
    ) == "validated"
    accept_arcgis_fixture_snapshot(
        lifecycle_connection,
        first.snapshot_id,
        accepted_at=ACCEPTED_AT,
    )
    first_pointer = promote_arcgis_fixture_snapshot(
        lifecycle_connection,
        first.snapshot_id,
        promoted_at=PROMOTED_AT,
    )
    assert first_pointer.active_snapshot_id == first.snapshot_id
    assert first_pointer.prior_accepted_snapshot_id is None

    second = stage_arcgis_fixture_snapshot(lifecycle_connection, SNAPSHOT_B)
    assert len(second.disappearances) == 2
    assert {row["source_object_id"] for row in second.disappearances} == {910002, 910003}
    assert all(row["closure_inferred"] is False for row in second.disappearances)
    assert validate_arcgis_fixture_snapshot(
        lifecycle_connection,
        second.snapshot_id,
        validated_at=VALIDATED_AT,
    ) == "validated"
    accept_arcgis_fixture_snapshot(
        lifecycle_connection,
        second.snapshot_id,
        accepted_at=ACCEPTED_AT,
    )
    second_pointer = promote_arcgis_fixture_snapshot(
        lifecycle_connection,
        second.snapshot_id,
        promoted_at=PROMOTED_AT,
    )
    assert second_pointer.active_snapshot_id == second.snapshot_id
    assert second_pointer.prior_accepted_snapshot_id == first.snapshot_id

    repeated = promote_arcgis_fixture_snapshot(
        lifecycle_connection,
        second.snapshot_id,
        promoted_at="2026-07-20T15:03:00+00:00",
    )
    assert repeated == second_pointer
    rolled_back = rollback_arcgis_fixture_snapshot(
        lifecycle_connection,
        expected_active_snapshot_id=second.snapshot_id,
        rolled_back_at="2026-07-20T15:04:00+00:00",
    )
    assert rolled_back.active_snapshot_id == first.snapshot_id
    assert rolled_back.prior_accepted_snapshot_id == second.snapshot_id
    repeated_rollback = rollback_arcgis_fixture_snapshot(
        lifecycle_connection,
        expected_active_snapshot_id=second.snapshot_id,
        rolled_back_at="2026-07-20T15:05:00+00:00",
    )
    assert repeated_rollback == rolled_back

    assert _state(lifecycle_connection, first.snapshot_id) == "accepted"
    assert _state(lifecycle_connection, second.snapshot_id) == "accepted"
    assert lifecycle_connection.scalar(
        sa.select(sa.func.count()).select_from(source_snapshots)
    ) == 2
    assert lifecycle_connection.scalar(
        sa.select(sa.func.count()).select_from(source_snapshot_rows)
    ) == 5
    assert lifecycle_connection.scalar(
        sa.select(sa.func.count()).select_from(source_snapshot_disappearances)
    ) == 2
    assert (
        lifecycle_connection.execute(sa.select(reviewer_state.c.note)).scalar_one()
        == "unchanged"
    )


def test_rejected_candidate_retains_evidence_and_cannot_be_accepted_or_promoted(
    lifecycle_connection: Connection,
) -> None:
    first = stage_arcgis_fixture_snapshot(lifecycle_connection, SNAPSHOT_A)
    _accept_and_promote(lifecycle_connection, first.snapshot_id)
    rejected = stage_arcgis_fixture_snapshot(lifecycle_connection, REJECTED_SNAPSHOT)

    assert rejected.rejection_reasons
    assert any("unapproved domain" in reason for reason in rejected.rejection_reasons)
    assert any("schema fingerprint differs" in reason for reason in rejected.rejection_reasons)
    assert any("domain fingerprint differs" in reason for reason in rejected.rejection_reasons)
    assert any("omits fields: RES_CITY" in reason for reason in rejected.rejection_reasons)
    assert any("invalid fields: capacity_source" in reason for reason in rejected.rejection_reasons)
    assert validate_arcgis_fixture_snapshot(
        lifecycle_connection,
        rejected.snapshot_id,
        validated_at=VALIDATED_AT,
    ) == "rejected"
    assert _state(lifecycle_connection, rejected.snapshot_id) == "rejected"

    with pytest.raises(OfflineSnapshotLifecycleError, match="validated snapshot"):
        accept_arcgis_fixture_snapshot(
            lifecycle_connection,
            rejected.snapshot_id,
            accepted_at=ACCEPTED_AT,
        )
    with pytest.raises(OfflineSnapshotLifecycleError, match="accepted snapshot"):
        promote_arcgis_fixture_snapshot(
            lifecycle_connection,
            rejected.snapshot_id,
            promoted_at=PROMOTED_AT,
        )
    pointer = lifecycle_connection.execute(sa.select(source_snapshot_pointers)).mappings().one()
    assert pointer["active_snapshot_id"] == first.snapshot_id


def test_invalid_transitions_and_multiple_active_pointer_attempts_fail_closed(
    lifecycle_connection: Connection,
) -> None:
    first = stage_arcgis_fixture_snapshot(lifecycle_connection, SNAPSHOT_A)

    with pytest.raises(OfflineSnapshotLifecycleError, match="accepted snapshot"):
        promote_arcgis_fixture_snapshot(
            lifecycle_connection,
            first.snapshot_id,
            promoted_at=PROMOTED_AT,
        )
    validate_arcgis_fixture_snapshot(
        lifecycle_connection,
        first.snapshot_id,
        validated_at=VALIDATED_AT,
    )
    with pytest.raises(OfflineSnapshotLifecycleError, match="Only a candidate"):
        validate_arcgis_fixture_snapshot(
            lifecycle_connection,
            first.snapshot_id,
            validated_at=VALIDATED_AT,
        )
    accept_arcgis_fixture_snapshot(
        lifecycle_connection,
        first.snapshot_id,
        accepted_at=ACCEPTED_AT,
    )
    promote_arcgis_fixture_snapshot(
        lifecycle_connection,
        first.snapshot_id,
        promoted_at=PROMOTED_AT,
    )
    with pytest.raises(OfflineSnapshotLifecycleError, match="No prior accepted"):
        rollback_arcgis_fixture_snapshot(
            lifecycle_connection,
            expected_active_snapshot_id=first.snapshot_id,
            rolled_back_at=PROMOTED_AT,
        )
    with pytest.raises(IntegrityError):
        lifecycle_connection.execute(
            source_snapshot_pointers.insert().values(
                source_family_id=ARCGIS_SUPPLEMENT_SOURCE_FAMILY_ID,
                active_snapshot_id=first.snapshot_id,
                prior_accepted_snapshot_id=None,
                updated_at=PROMOTED_AT,
            )
        )


def test_staging_is_idempotent_and_fingerprints_are_stable(
    lifecycle_connection: Connection,
) -> None:
    first = stage_arcgis_fixture_snapshot(lifecycle_connection, SNAPSHOT_A)
    repeated = stage_arcgis_fixture_snapshot(lifecycle_connection, SNAPSHOT_A)

    assert repeated.snapshot_id == first.snapshot_id
    assert repeated.normalized_content_sha256 == first.normalized_content_sha256
    assert [row["row_fingerprint"] for row in repeated.rows] == [
        row["row_fingerprint"] for row in first.rows
    ]
    assert lifecycle_connection.scalar(
        sa.select(sa.func.count()).select_from(source_snapshots)
    ) == 1
    assert lifecycle_connection.scalar(
        sa.select(sa.func.count()).select_from(source_snapshot_rows)
    ) == 3


def test_offline_lifecycle_contains_no_network_or_endpoint_authorization_code() -> None:
    source_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "ccld_complaints"
        / "hosted_app"
        / "source_snapshot_lifecycle.py"
    )
    source = source_path.read_text(encoding="utf-8").casefold()

    for forbidden in (
        "import requests",
        "import urllib",
        "import httpx",
        "featureserver",
        "source_url",
        "allowed_host",
        "authorization header",
    ):
        assert forbidden not in source


def _accept_and_promote(connection: Connection, snapshot_id: str) -> None:
    assert validate_arcgis_fixture_snapshot(
        connection,
        snapshot_id,
        validated_at=VALIDATED_AT,
    ) == "validated"
    accept_arcgis_fixture_snapshot(connection, snapshot_id, accepted_at=ACCEPTED_AT)
    promote_arcgis_fixture_snapshot(connection, snapshot_id, promoted_at=PROMOTED_AT)


def _state(connection: Connection, snapshot_id: str) -> str:
    return str(
        connection.execute(
            sa.select(source_snapshots.c.lifecycle_state).where(
                source_snapshots.c.snapshot_id == snapshot_id
            )
        ).scalar_one()
    )


def _warnings(inspection: SnapshotInspection) -> list[str]:
    return [str(value) for value in inspection.validation_report["warnings"]]


def _write_variant_fixture(tmp_path: Path, raw_payload: object) -> Path:
    raw_bytes = (json.dumps(raw_payload, indent=2) + "\n").encode()
    raw_path = tmp_path / "variant-raw.json"
    raw_path.write_bytes(raw_bytes)
    manifest = json.loads(SNAPSHOT_A.read_text(encoding="utf-8"))
    manifest["raw_payload_ref"] = raw_path.name
    manifest["raw_payload_sha256"] = hashlib.sha256(raw_bytes).hexdigest()
    manifest["recorded_at"] = "2026-07-20T18:00:00+00:00"
    manifest_path = tmp_path / "variant-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path
