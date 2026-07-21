from __future__ import annotations

import csv
import io
import json
from collections.abc import Callable, Mapping
from pathlib import Path
from urllib.request import Request

import pytest

from ccld_complaints.cli import transparencyapi_snapshot_capture as cli
from ccld_complaints.connectors.ccld_transparency_api import connector as connector_module
from ccld_complaints.connectors.ccld_transparency_api.connector import (
    HttpArtifactResponse,
    NoRedirectGetTransport,
    SnapshotCapture,
    TransparencyApiConnector,
    TransparencyApiConnectorError,
    bulk_export_url,
    validate_governed_url,
)
from ccld_complaints.connectors.ccld_transparency_api.contract import (
    BASE_URL,
    EXPORT_IDS,
    expected_headers,
)
from ccld_complaints.connectors.ccld_transparency_api.lifecycle import (
    inspect_transparencyapi_package,
)


class _FixtureTransport:
    def __init__(
        self,
        responses: Mapping[str, tuple[str, bytes]],
        *,
        overrides: Mapping[str, Mapping[str, object]] | None = None,
    ) -> None:
        self.responses = responses
        self.overrides = overrides or {}
        self.requested_urls: list[str] = []

    def get(self, url: str, *, timeout_seconds: float) -> HttpArtifactResponse:
        assert timeout_seconds > 0
        self.requested_urls.append(url)
        media_type, body = self.responses[url]
        override = self.overrides.get(url, {})
        headers = override.get(
            "headers",
            (
                ("Content-Type", media_type),
                ("Content-Length", str(len(body))),
                ("Set-Cookie", "prohibited-cookie-value"),
                ("Authorization", "prohibited-authorization-value"),
            ),
        )
        assert isinstance(headers, tuple)
        return HttpArtifactResponse(
            request_url=url,
            final_url=str(override.get("final_url", url)),
            status=int(override.get("status", 200)),
            headers=headers,
            body=body,
        )


class _MutatingConnector:
    def __init__(
        self,
        connector: TransparencyApiConnector,
        mutation: Callable[[Path], None],
    ) -> None:
        self.connector = connector
        self.mutation = mutation

    def capture_snapshot(
        self, repository_root: Path, *, retrieved_at: str | None = None
    ) -> SnapshotCapture:
        capture = self.connector.capture_snapshot(
            repository_root,
            retrieved_at=retrieved_at,
        )
        self.mutation(capture.manifest_path)
        return capture


def test_capture_is_complete_preserved_inspected_and_aggregate_safe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _repository_root(tmp_path / "repo")
    responses = _source_family_responses()
    transport = _FixtureTransport(responses)
    connector = TransparencyApiConnector(transport=transport)

    def reject_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("unit capture must not use outbound network")

    monkeypatch.setattr("socket.create_connection", reject_network)
    payload = cli.capture_package(
        root,
        connector=connector,
        recorded_at="2026-07-21T23:00:00+00:00",
    )
    package_directory = root / str(payload["package_directory"])
    manifest_path = package_directory / str(payload["manifest_filename"])
    inspection = inspect_transparencyapi_package(manifest_path)
    manifest_text = manifest_path.read_text(encoding="utf-8")

    assert len(transport.requested_urls) == 9
    assert transport.requested_urls == [
        *(bulk_export_url(export_id) for export_id in EXPORT_IDS),
        f"{BASE_URL}/Group/",
        f"{BASE_URL}/CACounty",
    ]
    assert all("FacilitySearch" not in url for url in transport.requested_urls)
    assert payload["artifact_count"] == 9
    assert payload["export_count"] == 7
    assert payload["row_count"] == payload["stored_row_count"] == 7
    assert payload["eligible_row_count"] == 7
    assert payload["rejection_count"] == 0
    assert payload["database_mutations_performed"] is False
    assert inspection.validation_report["rejection_reasons"] == []
    assert not Path(str(payload["package_directory"])).is_absolute()
    assert str(tmp_path) not in json.dumps(payload)
    assert "prohibited-cookie-value" not in manifest_text
    assert "prohibited-authorization-value" not in manifest_text
    assert "Set-Cookie" in manifest_text
    assert "Authorization" in manifest_text
    for artifact in inspection.artifacts:
        raw_path = package_directory / str(artifact["raw_ref"])
        assert raw_path.read_bytes() == responses[str(artifact["request_url"])][1]


def test_fixed_capture_is_hash_deterministic(tmp_path: Path) -> None:
    first_root = _repository_root(tmp_path / "first")
    second_root = _repository_root(tmp_path / "second")
    recorded_at = "2026-07-21T23:10:00+00:00"
    first = cli.capture_package(
        first_root,
        connector=TransparencyApiConnector(
            transport=_FixtureTransport(_source_family_responses())
        ),
        recorded_at=recorded_at,
    )
    second = cli.capture_package(
        second_root,
        connector=TransparencyApiConnector(
            transport=_FixtureTransport(_source_family_responses())
        ),
        recorded_at=recorded_at,
    )
    assert first == second


def test_successful_main_writes_one_safe_json_object(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _repository_root(tmp_path / "repo")
    connector = TransparencyApiConnector(
        transport=_FixtureTransport(_source_family_responses())
    )
    monkeypatch.setattr(cli, "TransparencyApiConnector", lambda: connector)
    assert cli.main(["capture", "--output-dir", str(root)]) == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert captured.err == ""
    assert payload["status"] == "passed"
    assert payload["artifact_count"] == 9
    assert payload["export_count"] == 7
    assert str(tmp_path) not in captured.out
    assert "Synthetic Administrator" not in captured.out
    assert "555-0100" not in captured.out


def test_cli_has_no_caller_url_and_sanitizes_missing_endpoint_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _repository_root(tmp_path / "repo")
    responses = _source_family_responses()
    responses.pop(bulk_export_url(EXPORT_IDS[-1]))
    connector = TransparencyApiConnector(transport=_FixtureTransport(responses))
    monkeypatch.setattr(cli, "TransparencyApiConnector", lambda: connector)
    database_path = tmp_path / "must-not-exist.db"
    monkeypatch.setenv(
        "CCLD_HOSTED_TESTER_DATABASE_URL",
        f"sqlite+pysqlite:///{database_path}",
    )

    with pytest.raises(SystemExit) as parser_exit:
        cli.build_parser().parse_args(
            ["capture", "--output-dir", str(root), "--url", "https://example.invalid"]
        )
    assert parser_exit.value.code == 2
    parser_error = capsys.readouterr()
    assert "unrecognized arguments: --url" in parser_error.err
    assert cli.main(["capture", "--output-dir", str(root)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err) == {
        "operation": "capture",
        "reason_category": "capture_failed",
        "status": "failed",
    }
    assert str(tmp_path) not in captured.err
    assert not database_path.exists()


def test_duplicate_export_and_taxonomy_fail_closed(tmp_path: Path) -> None:
    duplicate_root = _repository_root(tmp_path / "duplicate")
    duplicate = _MutatingConnector(
        TransparencyApiConnector(transport=_FixtureTransport(_source_family_responses())),
        _duplicate_first_export,
    )
    with pytest.raises(cli.CaptureCliError, match="captured_source_family_incomplete"):
        cli.capture_package(
            duplicate_root,
            connector=duplicate,
            recorded_at="2026-07-21T23:20:00+00:00",
        )

    taxonomy_root = _repository_root(tmp_path / "taxonomy")
    taxonomy = _MutatingConnector(
        TransparencyApiConnector(transport=_FixtureTransport(_source_family_responses())),
        _invalidate_taxonomy,
    )
    with pytest.raises(cli.CaptureCliError, match="captured_package_rejected"):
        cli.capture_package(
            taxonomy_root,
            connector=taxonomy,
            recorded_at="2026-07-21T23:21:00+00:00",
        )


@pytest.mark.parametrize(
    "override",
    (
        {"status": 503},
        {"headers": (("Content-Type", "application/json"),)},
        {
            "headers": (
                ("Content-Type", "text/csv"),
                ("Content-Length", "999999"),
            )
        },
        {"final_url": f"{BASE_URL}/Group/"},
    ),
    ids=("status", "media-type", "truncation", "redirect"),
)
def test_transport_evidence_failures_reject_the_package(
    tmp_path: Path,
    override: Mapping[str, object],
) -> None:
    root = _repository_root(tmp_path)
    responses = _source_family_responses()
    url = bulk_export_url(EXPORT_IDS[0])
    connector = TransparencyApiConnector(
        transport=_FixtureTransport(responses, overrides={url: override})
    )
    with pytest.raises(cli.CaptureCliError, match="captured_package_rejected"):
        cli.capture_package(
            root,
            connector=connector,
            recorded_at="2026-07-21T23:30:00+00:00",
        )


@pytest.mark.parametrize(
    "url",
    (
        "https://example.invalid/transparencyapi/api/Group/",
        f"{BASE_URL}/FacilitySearch",
        f"{BASE_URL}/DownloadStateData?id=UnapprovedExport",
    ),
)
def test_hostname_path_and_export_guards_remain_closed(url: str) -> None:
    with pytest.raises(TransparencyApiConnectorError):
        validate_governed_url(url)


def test_real_transport_builds_headerless_get_without_redirect_support(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[Request] = []

    class _Response:
        status = 200
        headers = {"Content-Type": "application/json"}

        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def geturl(self) -> str:
            return f"{BASE_URL}/Group/"

        def read(self) -> bytes:
            return b"[]"

    class _Opener:
        def open(self, request: Request, *, timeout: float) -> _Response:
            assert timeout > 0
            seen.append(request)
            return _Response()

    def fake_build_opener(*handlers: object) -> _Opener:
        assert len(handlers) == 1
        assert handlers[0].__class__.__name__ == "_RejectRedirectHandler"
        return _Opener()

    monkeypatch.setattr(connector_module, "build_opener", fake_build_opener)
    response = NoRedirectGetTransport().get(
        f"{BASE_URL}/Group/",
        timeout_seconds=5,
    )
    assert response.status == 200
    assert len(seen) == 1
    assert seen[0].method == "GET"
    assert seen[0].header_items() == []


def _repository_root(path: Path) -> Path:
    (path / "src/ccld_complaints/connectors/ccld_transparency_api").mkdir(
        parents=True
    )
    (path / "data/raw").mkdir(parents=True)
    (path / "pyproject.toml").write_text("[project]\nname='fixture'\n", encoding="utf-8")
    (path / ".gitignore").write_text(
        "data/raw/*\n!data/raw/.gitkeep\n",
        encoding="utf-8",
    )
    (path / "src/ccld_complaints/connectors/ccld_transparency_api/connector.py").write_text(
        "# fixture marker\n",
        encoding="utf-8",
    )
    (path / "data/raw/.gitkeep").write_text("", encoding="utf-8")
    return path


def _duplicate_first_export(manifest_path: Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    duplicate = dict(manifest["artifacts"][0])
    duplicate["artifact_id"] = "duplicate-approved-export"
    manifest["artifacts"].append(duplicate)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def _invalidate_taxonomy(manifest_path: Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifact = next(
        item
        for item in manifest["artifacts"]
        if item["endpoint_kind"] == "facility_type_taxonomy"
    )
    taxonomy_path = manifest_path.parent / artifact["raw_ref"]
    taxonomy_path.write_bytes(b"not-json")


def _source_family_responses() -> dict[str, tuple[str, bytes]]:
    responses: dict[str, tuple[str, bytes]] = {}
    for index, export_id in enumerate(EXPORT_IDS, start=1):
        responses[bulk_export_url(export_id)] = (
            "text/csv; charset=utf-8",
            _csv_bytes(export_id, facility_number=f"0{index:08d}"),
        )
    responses[f"{BASE_URL}/Group/"] = (
        "application/json",
        b'[{"TYPE":"733","DESCRIPTION":"Synthetic"},{"TYPE":"777","DESCRIPTION":"Zero"}]',
    )
    responses[f"{BASE_URL}/CACounty"] = (
        "application/json",
        b'[{"CODE":"00","NAME":"Fixture County"}]',
    )
    return responses


def _csv_bytes(export_id: str, *, facility_number: str) -> bytes:
    headers = expected_headers(export_id)
    values = {header: "" for header in headers[:-1]}
    values.update(
        {
            "Facility Type": "SYNTHETIC TYPE",
            "Facility Number": facility_number,
            "Facility Name": f"Synthetic Facility {facility_number}",
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
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(headers)
    writer.writerow([*(values[header] for header in headers[:-1]), "No Complaints"])
    return output.getvalue().encode("utf-8")
