from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
import sqlalchemy as sa

from ccld_complaints.cli import transparencyapi_snapshot_lifecycle as cli
from ccld_complaints.connectors.ccld_transparency_api.connector import (
    HttpArtifactResponse,
    TransparencyApiConnector,
    TransparencyApiConnectorError,
)
from ccld_complaints.connectors.ccld_transparency_api.contract import (
    BASE_URL,
    EXPORT_IDS,
    SOURCE_FAMILY_ID,
    expected_headers,
)
from ccld_complaints.hosted_app.reviewer_created_state import (
    hosted_reviewer_created_state,
)
from ccld_complaints.hosted_app.seeded_import import (
    hosted_import_batches,
    hosted_seeded_import_metadata,
    hosted_source_derived_records,
)
from ccld_complaints.hosted_app.source_snapshot_lifecycle import (
    source_snapshot_metadata,
    source_snapshot_pointers,
    source_snapshots,
)

APPROVED_IDENTITIES = (
    ("015600412", "R.E.F.U.G.E."),
    ("015600744", "R.E.F.U.G.E.II"),
    ("015650058", "R.E.F.U.G.E.III, THE"),
)


class _Transport:
    def __init__(self, names: tuple[tuple[str, str], ...] = APPROVED_IDENTITIES) -> None:
        self.names = names

    def get(self, url: str, *, timeout_seconds: float) -> HttpArtifactResponse:
        assert timeout_seconds > 0
        if url == f"{BASE_URL}/Group/":
            body = b'[{"TYPE":"733","DESCRIPTION":"Synthetic"}]'
            media_type = "application/json"
        elif url == f"{BASE_URL}/CACounty":
            body = b'[{"CODE":"00","NAME":"Fixture County"}]'
            media_type = "application/json"
        else:
            export_id = parse_qs(urlsplit(url).query)["id"][0]
            index = EXPORT_IDS.index(export_id)
            facility_id, facility_name = (
                self.names[index]
                if index < len(self.names)
                else (f"9{index:08d}", f"Synthetic Facility {index}")
            )
            body = _csv(export_id, _row(export_id, facility_id, facility_name))
            media_type = "text/csv"
        return HttpArtifactResponse(
            request_url=url,
            final_url=url,
            status=200,
            headers=(("Content-Type", media_type),),
            body=body,
        )


def test_help_and_pointer_guard_arguments_are_explicit(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as help_exit:
        cli.main(["--help"])
    assert help_exit.value.code == 0
    assert "inspect-package" in capsys.readouterr().out

    with pytest.raises(SystemExit) as guard_exit:
        cli.build_parser().parse_args(["promote", "snapshot-1"])
    assert guard_exit.value.code == 2

    args = cli.build_parser().parse_args(
        [
            "promote",
            "snapshot-1",
            "--expected-active",
            "none",
            "--expected-prior",
            "none",
        ]
    )
    assert args.expected_active == "none"
    assert args.expected_prior == "none"


def test_inspect_is_deterministic_aggregate_only_and_never_uses_network(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _capture(tmp_path / "package", "2026-07-21T12:00:00+00:00")

    def reject_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("outbound network use is prohibited")

    monkeypatch.setattr("socket.create_connection", reject_network)
    assert cli.main(["inspect-package", str(manifest)]) == 0
    first = capsys.readouterr().out
    assert cli.main(["inspect-package", str(manifest)]) == 0
    second = capsys.readouterr().out
    assert first == second

    payload = json.loads(first)
    assert payload["artifact_count"] == 9
    assert payload["row_count"] == 7
    assert payload["eligible_row_count"] == 7
    assert payload["rejection_count"] == 0
    assert "Synthetic Administrator" not in first
    assert "555-0100" not in first
    assert str(tmp_path) not in first
    assert "http" not in first.casefold()


def test_missing_package_failure_is_sanitized(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing = tmp_path / "private" / "operator-package.json"
    assert cli.main(["inspect-package", str(missing)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert str(tmp_path) not in captured.err
    assert "package_unavailable" in captured.err


def test_stage_is_idempotent_and_collision_fails_closed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = _database(tmp_path, monkeypatch)
    manifest = _capture(tmp_path / "first", "2026-07-21T13:00:00+00:00")
    assert cli.main(["stage", str(manifest)]) == 0
    first = json.loads(capsys.readouterr().out)
    assert cli.main(["stage", str(manifest)]) == 0
    second = json.loads(capsys.readouterr().out)
    assert second["snapshot_id"] == first["snapshot_id"]

    collision = _capture(tmp_path / "second", "2026-07-21T14:00:00+00:00")
    collision_payload = json.loads(collision.read_text(encoding="utf-8"))
    collision_payload["snapshot_id"] = first["snapshot_id"]
    collision.write_text(json.dumps(collision_payload), encoding="utf-8")
    assert cli.main(["stage", str(collision)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "immutable_evidence_or_package_invalid" in captured.err

    with sa.create_engine(database_url).connect() as connection:
        assert connection.scalar(sa.select(sa.func.count()).select_from(source_snapshots)) == 1


def test_validation_rejection_and_accept_guard_remain_closed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = _database(tmp_path, monkeypatch)
    manifest = _capture(tmp_path / "rejected", "2026-07-21T15:00:00+00:00")
    value = json.loads(manifest.read_text(encoding="utf-8"))
    value["artifacts"] = [
        artifact
        for artifact in value["artifacts"]
        if artifact.get("export_id") != EXPORT_IDS[-1]
    ]
    manifest.write_text(json.dumps(value), encoding="utf-8")

    assert cli.main(["stage", str(manifest)]) == 0
    snapshot_id = json.loads(capsys.readouterr().out)["snapshot_id"]
    assert cli.main(["validate", snapshot_id, "--at", "2026-07-21T15:01:00Z"]) == 2
    rejected = json.loads(capsys.readouterr().out)
    assert rejected["lifecycle_state"] == "rejected"
    assert rejected["rejection_count"] > 0
    assert cli.main(["accept", snapshot_id, "--at", "2026-07-21T15:02:00Z"]) == 2
    assert "lifecycle_guard_failed" in capsys.readouterr().err

    with sa.create_engine(database_url).connect() as connection:
        assert connection.scalar(
            sa.select(source_snapshots.c.lifecycle_state).where(
                source_snapshots.c.snapshot_id == snapshot_id
            )
        ) == "rejected"


def test_promotion_and_rollback_guards_preserve_pointer_history(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = _database(tmp_path, monkeypatch)
    first = _prepare_accepted(
        tmp_path / "first", "2026-07-21T16:00:00+00:00", capsys
    )
    assert cli.main(
        [
            "promote",
            first,
            "--expected-active",
            "none",
            "--expected-prior",
            "none",
            "--at",
            "2026-07-21T16:03:00Z",
        ]
    ) == 0
    capsys.readouterr()

    second = _prepare_accepted(
        tmp_path / "second",
        "2026-07-21T17:00:00+00:00",
        capsys,
        names=(
            ("015600412", "R.E.F.U.G.E. UPDATED"),
            APPROVED_IDENTITIES[1],
            APPROVED_IDENTITIES[2],
        ),
    )
    assert cli.main(
        [
            "promote",
            second,
            "--expected-active",
            "wrong",
            "--expected-prior",
            "none",
        ]
    ) == 2
    assert "expected_active_guard_failed" in capsys.readouterr().err
    _assert_pointer(database_url, first, None)

    assert cli.main(
        [
            "promote",
            second,
            "--expected-active",
            first,
            "--expected-prior",
            "none",
            "--at",
            "2026-07-21T17:03:00Z",
        ]
    ) == 0
    capsys.readouterr()
    _assert_pointer(database_url, second, first)

    assert cli.main(
        [
            "rollback",
            "--expected-active",
            second,
            "--expected-prior",
            "wrong",
        ]
    ) == 2
    assert "expected_prior_guard_failed" in capsys.readouterr().err
    _assert_pointer(database_url, second, first)

    assert cli.main(
        [
            "rollback",
            "--expected-active",
            second,
            "--expected-prior",
            first,
            "--at",
            "2026-07-21T17:04:00Z",
        ]
    ) == 0
    rolled_back = json.loads(capsys.readouterr().out)
    assert rolled_back["active_snapshot_id"] == first
    assert rolled_back["prior_accepted_snapshot_id"] == second
    _assert_pointer(database_url, first, second)

    with sa.create_engine(database_url).connect() as connection:
        assert connection.scalar(sa.select(sa.func.count()).select_from(source_snapshots)) == 2


def test_failed_mutation_rolls_back_its_transaction(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = _database(tmp_path, monkeypatch)
    manifest = _capture(tmp_path / "package", "2026-07-21T18:00:00+00:00")
    original = cli.stage_transparencyapi_snapshot

    def fail_after_stage(connection: sa.Connection, path: Path) -> object:
        original(connection, path)
        raise TransparencyApiConnectorError("forced failure with secret=value")

    monkeypatch.setattr(cli, "stage_transparencyapi_snapshot", fail_after_stage)
    assert cli.main(["stage", str(manifest)]) == 2
    assert "secret=value" not in capsys.readouterr().err
    with sa.create_engine(database_url).connect() as connection:
        assert connection.scalar(sa.select(sa.func.count()).select_from(source_snapshots)) == 0


def test_status_is_source_family_isolated(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = _database(tmp_path, monkeypatch)
    manifest = _capture(tmp_path / "package", "2026-07-21T19:00:00+00:00")
    assert cli.main(["stage", str(manifest)]) == 0
    transparency_id = json.loads(capsys.readouterr().out)["snapshot_id"]
    with sa.create_engine(database_url).begin() as connection:
        connection.execute(
            source_snapshots.insert().values(
                snapshot_id="other-family-snapshot",
                source_family_id="other-source-family",
                fixture_scope="repository_synthetic_fixture",
                observation_kind="synthetic_query",
                lifecycle_state="accepted",
                manifest_ref="fixture.json",
                manifest_sha256="a" * 64,
                raw_payload_ref="fixture.json",
                raw_payload_sha256="b" * 64,
                normalized_content_sha256="c" * 64,
                schema_fingerprint="d" * 64,
                domain_fingerprint="e" * 64,
                row_count=0,
                stored_row_count=0,
                duplicate_object_id_count=0,
                duplicate_facility_number_count=0,
                omitted_field_count=0,
                invalid_field_count=0,
                warning_count=0,
                rejection_reason_count=0,
                validation_report={},
                recorded_at="2026-07-21T19:01:00Z",
                validated_at="2026-07-21T19:02:00Z",
                accepted_at="2026-07-21T19:03:00Z",
            )
        )
    assert cli.main(["status"]) == 0
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload["snapshot_count"] == 1
    assert payload["snapshots"][0]["snapshot_id"] == transparency_id
    assert "other-family" not in output


def test_dry_run_preserves_database_and_reviewer_state_and_leading_zero_identity(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = _database(tmp_path, monkeypatch, include_reviewer_state=True)
    manifest = _capture(tmp_path / "package", "2026-07-21T20:00:00+00:00")
    before = _database_counts(database_url)
    assert cli.main(["dry-run", str(manifest)]) == 0
    output = capsys.readouterr().out
    payload = json.loads(output)
    after = _database_counts(database_url)

    assert before == after
    assert payload["database_mutations_performed"] is False
    assert payload["reviewer_created_state_count_before"] == 1
    assert payload["reviewer_created_state_count_projected_after"] == 1
    assert payload["active_snapshot_id"] is None
    assert payload["unresolved_code_count"] == 7
    assert payload["source_family_conflict_count"] == 0
    assert all(item["exists"] for item in payload["approved_identity_checks"])
    assert all(item["exact_text_identity"] for item in payload["approved_identity_checks"])
    assert all(item["leading_zero_preserved"] for item in payload["approved_identity_checks"])
    assert "reviewer note" not in output
    assert "555-0100" not in output


def _database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    include_reviewer_state: bool = False,
) -> str:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'lifecycle.db'}"
    engine = sa.create_engine(database_url)
    source_snapshot_metadata.create_all(engine)
    hosted_seeded_import_metadata.create_all(engine)
    if include_reviewer_state:
        with engine.begin() as connection:
            connection.execute(
                hosted_import_batches.insert().values(
                    import_batch_id="fixture-batch",
                    imported_at="2026-07-21T00:00:00Z",
                    source_artifact_identity="synthetic-fixture",
                    source_pipeline_version="test",
                    validation_status="validated",
                    raw_hash_validation_status="validated",
                    record_counts={"facility": 1},
                    warnings=[],
                    errors=[],
                )
            )
            connection.execute(
                hosted_source_derived_records.insert().values(
                    source_record_key="facility:fixture",
                    entity_type="facility",
                    stable_source_id="fixture",
                    import_batch_id="fixture-batch",
                    source_document_id="fixture-document",
                    facility_id="fixture",
                    source_url="https://example.invalid/fixture",
                    raw_sha256="f" * 64,
                    raw_path=None,
                    connector_name="fixture",
                    connector_version="1",
                    retrieved_at="2026-07-21T00:00:00Z",
                    original_values={},
                    source_traceability={},
                )
            )
            connection.execute(
                hosted_reviewer_created_state.insert().values(
                    reviewer_state_id="reviewer-state-fixture",
                    source_record_key="facility:fixture",
                    scope_type="seeded_corpus",
                    scope_id="fixture-batch",
                    state_kind="review_item_state_scaffold",
                    state_payload={"note": "reviewer note"},
                    created_at="2026-07-21T00:00:00Z",
                    created_by_provider_subject="fixture-reviewer",
                    created_by_provider_issuer="fixture-provider",
                    created_by_display_name="Fixture Reviewer",
                    created_by_actor_category="tester",
                    authorization_permission="reviewer_state_write",
                )
            )
    engine.dispose()
    monkeypatch.setattr(cli, "_configured_engine", lambda: sa.create_engine(database_url))
    return database_url


def _prepare_accepted(
    root: Path,
    recorded_at: str,
    capsys: pytest.CaptureFixture[str],
    *,
    names: tuple[tuple[str, str], ...] = APPROVED_IDENTITIES,
) -> str:
    manifest = _capture(root, recorded_at, names=names)
    assert cli.main(["stage", str(manifest)]) == 0
    snapshot_id = json.loads(capsys.readouterr().out)["snapshot_id"]
    assert cli.main(["validate", snapshot_id]) == 0
    capsys.readouterr()
    assert cli.main(["accept", snapshot_id]) == 0
    capsys.readouterr()
    return snapshot_id


def _assert_pointer(database_url: str, active: str, prior: str | None) -> None:
    with sa.create_engine(database_url).connect() as connection:
        pointer = connection.execute(
            sa.select(source_snapshot_pointers).where(
                source_snapshot_pointers.c.source_family_id == SOURCE_FAMILY_ID
            )
        ).mappings().one()
    assert pointer["active_snapshot_id"] == active
    assert pointer["prior_accepted_snapshot_id"] == prior


def _database_counts(database_url: str) -> tuple[int, int, int]:
    with sa.create_engine(database_url).connect() as connection:
        return (
            int(connection.scalar(sa.select(sa.func.count()).select_from(source_snapshots)) or 0),
            int(
                connection.scalar(
                    sa.select(sa.func.count()).select_from(source_snapshot_pointers)
                )
                or 0
            ),
            int(
                connection.scalar(
                    sa.select(sa.func.count()).select_from(hosted_reviewer_created_state)
                )
                or 0
            ),
        )


def _capture(
    root: Path,
    recorded_at: str,
    *,
    names: tuple[tuple[str, str], ...] = APPROVED_IDENTITIES,
) -> Path:
    return (
        TransparencyApiConnector(transport=_Transport(names))
        .capture_snapshot(root, retrieved_at=recorded_at)
        .manifest_path
    )


def _row(export_id: str, facility_id: str, facility_name: str) -> list[str]:
    headers = expected_headers(export_id)[:-1]
    values = {header: "" for header in headers}
    values.update(
        {
            "Facility Type": "733",
            "Facility Number": facility_id,
            "Facility Name": facility_name,
            "Facility Administrator": "Synthetic Administrator",
            "Facility Telephone Number": "555-0100",
            "Facility Address": "100 Synthetic Way",
            "Facility City": "Fixture City",
            "Facility State": "CA",
            "Facility Zip": "90000",
            "County Name": "Fixture County",
            "Facility Status": "Licensed",
        }
    )
    return [values[header] for header in headers] + ["No Complaints"]


def _csv(export_id: str, row: list[str]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(expected_headers(export_id))
    writer.writerow(row)
    return output.getvalue().encode()
