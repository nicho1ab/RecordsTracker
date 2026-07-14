from __future__ import annotations

import importlib.util
from contextlib import nullcontext
from pathlib import Path
from types import ModuleType
from typing import Any

from ccld_complaints.hosted_app.ccld_backfill import CcldHostedBackfillResult


class _Connection:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def test_cli_defaults_to_dry_run_and_prints_only_safe_aggregates(
    monkeypatch: Any,
    capsys: Any,
) -> None:
    cli = _load_cli_module()
    connection = _Connection()
    captured_request: list[Any] = []

    monkeypatch.setattr(
        cli,
        "open_configured_facility_reference_connection",
        lambda: nullcontext(connection),
    )

    def fake_run(_connection: Any, request: Any) -> CcldHostedBackfillResult:
        captured_request.append(request)
        return CcldHostedBackfillResult(
            apply_changes=False,
            examined=1,
            eligible=1,
            updated=1,
            unchanged=0,
            skipped=0,
            conflicted=1,
            warnings=0,
            failed=0,
        )

    monkeypatch.setattr(cli, "run_ccld_hosted_backfill", fake_run)

    assert cli.main(["--facility-number", "425802141"]) == 0

    output = capsys.readouterr().out
    assert captured_request[0].apply_changes is False
    assert connection.commits == 0
    assert connection.rollbacks == 1
    assert "mode: dry-run" in output
    assert "examined=1" in output
    assert "no live calls" in output
    assert "https://" not in output
    assert "COMPLAINT INVESTIGATION REPORT" not in output


def test_cli_apply_commits_and_failure_exit_is_nonzero(
    monkeypatch: Any,
    capsys: Any,
) -> None:
    cli = _load_cli_module()
    connection = _Connection()
    monkeypatch.setattr(
        cli,
        "open_configured_facility_reference_connection",
        lambda: nullcontext(connection),
    )
    monkeypatch.setattr(
        cli,
        "run_ccld_hosted_backfill",
        lambda _connection, _request: CcldHostedBackfillResult(
            apply_changes=True,
            examined=2,
            eligible=1,
            updated=1,
            unchanged=0,
            skipped=0,
            conflicted=0,
            warnings=1,
            failed=1,
        ),
    )

    assert cli.main(["--facility-number", "425802141", "--apply"]) == 1
    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert "failed=1" in capsys.readouterr().out


def test_powershell_wrapper_exposes_bounded_restartable_interface() -> None:
    wrapper = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "backfill-hosted-ccld-data.ps1"
    ).read_text(encoding="utf-8-sig")

    for token in (
        "$FacilityNumber",
        "$FacilityNumberFile",
        "$AllExisting",
        "$Operation",
        "$BatchSize",
        "$CheckpointFile",
        "$Restart",
        "$Apply",
        "$DryRun",
        "$QnapContainer",
        "docker compose",
    ):
        assert token in wrapper
    assert "Omit both for dry-run" in wrapper


def _load_cli_module() -> ModuleType:
    script_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "backfill_hosted_ccld_data.py"
    )
    spec = importlib.util.spec_from_file_location("hosted_ccld_backfill_cli", script_path)
    if spec is None or spec.loader is None:
        raise AssertionError("Could not load hosted CCLD backfill CLI module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
