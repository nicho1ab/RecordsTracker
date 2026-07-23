from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import sqlalchemy as sa

from ccld_complaints.connectors.ccld_transparency_api.connector import (
    HttpArtifactResponse,
    TransparencyApiConnector,
)
from ccld_complaints.connectors.ccld_transparency_api.contract import (
    BASE_URL,
    EXPORT_IDS,
    SOURCE_FAMILY_ID,
    expected_headers,
)
from ccld_complaints.connectors.ccld_transparency_api.lifecycle import (
    accept_transparencyapi_snapshot,
    promote_transparencyapi_snapshot,
    rollback_transparencyapi_snapshot,
    stage_transparencyapi_snapshot,
    transparency_disappearances,
    transparency_quarantines,
    transparency_rows,
    validate_transparencyapi_snapshot,
)
from ccld_complaints.hosted_app.source_snapshot_lifecycle import (
    source_snapshot_metadata,
    source_snapshot_pointers,
    source_snapshots,
)


class _Transport:
    def __init__(self, responses: dict[str, tuple[str, bytes]]) -> None:
        self.responses = responses

    def get(self, url: str, *, timeout_seconds: float) -> HttpArtifactResponse:
        media_type, body = self.responses[url]
        return HttpArtifactResponse(
            request_url=url,
            final_url=url,
            status=200,
            headers=(("Content-Type", media_type),),
            body=body,
        )


def test_complete_candidate_is_idempotent_and_promotes_and_rolls_back_atomically(
    tmp_path: Path,
) -> None:
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    source_snapshot_metadata.create_all(engine)
    first = _capture(tmp_path / "first", _responses(), "2026-07-21T00:00:00+00:00")
    second_responses = _responses(
        overrides={
            EXPORT_IDS[0]: [
                _row(
                    EXPORT_IDS[0],
                    number="900000001",
                    address="Unavailable",
                    telephone="",
                )
            ]
        }
    )
    second = _capture(tmp_path / "second", second_responses, "2026-07-21T01:00:00+00:00")
    with engine.begin() as connection:
        inspection = stage_transparencyapi_snapshot(connection, first)
        repeated = stage_transparencyapi_snapshot(connection, first)
        assert repeated.snapshot_id == inspection.snapshot_id
        assert len(repeated.rows) == len(inspection.rows)
        assert len(repeated.artifacts) == len(inspection.artifacts)
        assert (
            validate_transparencyapi_snapshot(
                connection, inspection.snapshot_id, validated_at="2026-07-21T00:01:00Z"
            )
            == "validated"
        )
        accept_transparencyapi_snapshot(
            connection, inspection.snapshot_id, accepted_at="2026-07-21T00:02:00Z"
        )
        first_pointer = promote_transparencyapi_snapshot(
            connection, inspection.snapshot_id, promoted_at="2026-07-21T00:03:00Z"
        )
        assert first_pointer.active_snapshot_id == inspection.snapshot_id
        assert first_pointer.prior_accepted_snapshot_id is None

        second_inspection = stage_transparencyapi_snapshot(connection, second)
        preserved = connection.execute(
            sa.select(
                transparency_rows.c.resolved_current_reference,
                transparency_rows.c.autocomplete_search_text,
            ).where(
                transparency_rows.c.snapshot_id == second_inspection.snapshot_id,
                transparency_rows.c.facility_number == "900000001",
            )
        ).mappings().one()
        resolved = preserved["resolved_current_reference"]
        assert resolved["facility_address"]["value"] == "100 Synthetic Way"
        assert resolved["facility_address"]["preserved_from_prior"] is True
        assert resolved["facility_telephone_number"]["value"] == "555-0100"
        assert preserved["autocomplete_search_text"] == (
            "900000001 synthetic facility fixture city fixture county 90000 ca "
            "synthetic type licensed"
        )
        assert (
            validate_transparencyapi_snapshot(
                connection,
                second_inspection.snapshot_id,
                validated_at="2026-07-21T01:01:00Z",
            )
            == "validated"
        )
        accept_transparencyapi_snapshot(
            connection,
            second_inspection.snapshot_id,
            accepted_at="2026-07-21T01:02:00Z",
        )
        pointer = promote_transparencyapi_snapshot(
            connection,
            second_inspection.snapshot_id,
            promoted_at="2026-07-21T01:03:00Z",
        )
        assert pointer.prior_accepted_snapshot_id == inspection.snapshot_id
        rolled_back = rollback_transparencyapi_snapshot(
            connection,
            expected_active_snapshot_id=second_inspection.snapshot_id,
            rolled_back_at="2026-07-21T01:04:00Z",
        )
        assert rolled_back.active_snapshot_id == inspection.snapshot_id
        assert rolled_back.prior_accepted_snapshot_id == second_inspection.snapshot_id
        assert connection.scalar(sa.select(sa.func.count()).select_from(source_snapshots)) == 2

    engine.dispose()


def test_blank_duplicate_and_partial_rows_are_reproducible_quarantines(
    tmp_path: Path,
) -> None:
    duplicate = "001234567"
    overrides = {
        EXPORT_IDS[0]: [_row(EXPORT_IDS[0], number=duplicate)],
        EXPORT_IDS[1]: [_row(EXPORT_IDS[1], number=duplicate)],
        EXPORT_IDS[2]: [_row(EXPORT_IDS[2], number="", tail=["01/01/2026", "1"])],
    }
    manifest = _capture(tmp_path, _responses(overrides=overrides), "2026-07-21T02:00:00+00:00")
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    source_snapshot_metadata.create_all(engine)
    with engine.begin() as connection:
        inspection = stage_transparencyapi_snapshot(connection, manifest)
        categories = (
            connection.execute(
                sa.select(transparency_quarantines.c.category).order_by(
                    transparency_quarantines.c.category,
                    transparency_quarantines.c.export_id,
                )
            )
            .scalars()
            .all()
        )
        assert categories.count("duplicate_facility_number") == 2
        assert "blank_facility_number" in categories
        assert "malformed_trailing_complaint_block" in categories
        assert inspection.validation_report["rejection_reasons"] == []
        assert (
            validate_transparencyapi_snapshot(
                connection, inspection.snapshot_id, validated_at="2026-07-21T02:01:00Z"
            )
            == "validated"
        )
        assert connection.scalar(sa.select(sa.func.count()).select_from(transparency_rows)) == 7
    engine.dispose()


def test_incomplete_seven_export_family_is_rejected_before_acceptance(tmp_path: Path) -> None:
    manifest_path = _capture(tmp_path, _responses(), "2026-07-21T03:00:00+00:00")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"] = [
        artifact
        for artifact in manifest["artifacts"]
        if artifact.get("export_id") != EXPORT_IDS[-1]
    ]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    source_snapshot_metadata.create_all(engine)
    with engine.begin() as connection:
        inspection = stage_transparencyapi_snapshot(connection, manifest_path)
        assert any(
            EXPORT_IDS[-1] in reason for reason in inspection.validation_report["rejection_reasons"]
        )
        assert (
            validate_transparencyapi_snapshot(
                connection, inspection.snapshot_id, validated_at="2026-07-21T03:01:00Z"
            )
            == "rejected"
        )
    engine.dispose()


def test_declared_content_length_truncation_rejects_candidate(tmp_path: Path) -> None:
    manifest_path = _capture(tmp_path, _responses(), "2026-07-21T03:30:00+00:00")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifact = manifest["artifacts"][0]
    artifact["response_headers"].append(["Content-Length", str(int(artifact["byte_count"]) + 1)])
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    source_snapshot_metadata.create_all(engine)
    with engine.begin() as connection:
        inspection = stage_transparencyapi_snapshot(connection, manifest_path)
        assert any(
            "appears truncated" in reason
            for reason in inspection.validation_report["rejection_reasons"]
        )
        assert (
            validate_transparencyapi_snapshot(
                connection, inspection.snapshot_id, validated_at="2026-07-21T03:31:00Z"
            )
            == "rejected"
        )
    engine.dispose()


def test_disappearance_is_preserved_without_closure_or_delete_inference(
    tmp_path: Path,
) -> None:
    first = _capture(tmp_path / "a", _responses(), "2026-07-21T04:00:00+00:00")
    second = _capture(
        tmp_path / "b",
        _responses(overrides={EXPORT_IDS[0]: [_row(EXPORT_IDS[0], number="999999999")]}),
        "2026-07-21T05:00:00+00:00",
    )
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    source_snapshot_metadata.create_all(engine)
    with engine.begin() as connection:
        first_inspection = stage_transparencyapi_snapshot(connection, first)
        validate_transparencyapi_snapshot(
            connection, first_inspection.snapshot_id, validated_at="2026-07-21T04:01:00Z"
        )
        accept_transparencyapi_snapshot(
            connection, first_inspection.snapshot_id, accepted_at="2026-07-21T04:02:00Z"
        )
        promote_transparencyapi_snapshot(
            connection, first_inspection.snapshot_id, promoted_at="2026-07-21T04:03:00Z"
        )
        second_inspection = stage_transparencyapi_snapshot(connection, second)
        disappearance = connection.execute(sa.select(transparency_disappearances)).mappings().one()
        assert disappearance["facility_number"] == "900000001"
        assert disappearance["review_state"] == "pending_reconciliation"
        assert disappearance["closure_inferred"] is False
        assert second_inspection.validation_report["canonical_or_reviewer_fields_written"] is False
    engine.dispose()


def test_source_family_pointer_does_not_replace_arcgis_or_other_source_family() -> None:
    assert SOURCE_FAMILY_ID == "ccld-transparencyapi-facility-reference"
    assert source_snapshot_pointers.c.source_family_id.primary_key is True


def _capture(
    root: Path,
    responses: dict[str, tuple[str, bytes]],
    recorded_at: str,
) -> Path:
    return (
        TransparencyApiConnector(transport=_Transport(responses))
        .capture_snapshot(root, retrieved_at=recorded_at)
        .manifest_path
    )


def _responses(
    *, overrides: dict[str, list[list[str]]] | None = None
) -> dict[str, tuple[str, bytes]]:
    response: dict[str, tuple[str, bytes]] = {}
    overrides = overrides or {}
    for index, export_id in enumerate(EXPORT_IDS, start=1):
        rows = overrides.get(export_id, [_row(export_id, number=f"9{index:08d}")])
        response[f"{BASE_URL}/DownloadStateData?id={export_id}"] = (
            "text/csv",
            _csv(export_id, rows),
        )
    response[f"{BASE_URL}/Group/"] = (
        "application/json",
        b'[{"TYPE":"733","DESCRIPTION":"Synthetic"},{"TYPE":"777","DESCRIPTION":"Zero"}]',
    )
    response[f"{BASE_URL}/CACounty"] = (
        "application/json",
        b'[{"CODE":"00","NAME":"Fixture County"}]',
    )
    return response


def _row(
    export_id: str,
    *,
    number: str,
    address: str = "100 Synthetic Way",
    telephone: str = "555-0100",
    tail: list[str] | None = None,
) -> list[str]:
    headers = expected_headers(export_id)[:-1]
    values = {header: "" for header in headers}
    values.update(
        {
            "Facility Type": "SYNTHETIC TYPE",
            "Facility Number": number,
            "Facility Name": "Synthetic Facility",
            "Facility Administrator": "Synthetic Administrator",
            "Facility Telephone Number": telephone,
            "Facility Address": address,
            "Facility City": "Fixture City",
            "Facility State": "CA",
            "Facility Zip": "90000",
            "County Name": "Fixture County",
            "Facility Status": "Licensed",
        }
    )
    return [values[header] for header in headers] + (tail or ["No Complaints"])


def _csv(export_id: str, rows: list[list[str]]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(expected_headers(export_id))
    writer.writerows(rows)
    return output.getvalue().encode()
