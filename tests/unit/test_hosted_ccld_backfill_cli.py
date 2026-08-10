from __future__ import annotations

import importlib.util
from contextlib import nullcontext
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from ccld_complaints.hosted_app.ccld_backfill import (
    CcldHostedBackfillDifference,
    CcldHostedBackfillResult,
)


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
            candidates=2,
            excluded=1,
            examined=1,
            eligible=1,
            intended_updates=1,
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
    assert "candidates=2" in output
    assert "excluded=1" in output
    assert "intended_updates=1" in output
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

    assert cli.main(
        [
            "--facility-number",
            "425802141",
            "--apply",
            "--operation",
            "facility-reference",
            "--checkpoint-file",
            "checkpoint.json",
            "--max-facilities",
            "1",
        ]
    ) == 1
    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert "failed=1" in capsys.readouterr().out


def test_cli_exposes_bounded_preserved_artifact_apply_operations(
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
            apply_changes=True,
            candidates=1,
            examined=1,
            eligible=1,
            intended_updates=1,
            updated=1,
            unchanged=0,
            skipped=0,
            conflicted=0,
            warnings=0,
            failed=0,
        )

    monkeypatch.setattr(cli, "run_ccld_hosted_backfill", fake_run)

    for operation in (
        "preserved-artifacts",
        "canonical-complaint-observations",
    ):
        assert cli.main(
            [
                "--facility-number",
                "900000001",
                "--operation",
                operation,
                "--apply",
                "--checkpoint-file",
                f"{operation}.json",
                "--max-facilities",
                "1",
            ]
        ) == 0

    assert [request.operation for request in captured_request] == [
        "preserved-artifacts",
        "canonical-complaint-observations",
    ]
    assert all(request.apply_changes is True for request in captured_request)
    assert all(request.max_facilities == 1 for request in captured_request)
    assert [request.checkpoint_file for request in captured_request] == [
        Path("preserved-artifacts.json"),
        Path("canonical-complaint-observations.json"),
    ]
    assert connection.commits == 2
    assert connection.rollbacks == 0
    assert "intended_updates=1" in capsys.readouterr().out


def test_cli_difference_diagnostic_is_explicit_read_only_json(
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
        "diagnose_ccld_preserved_artifact_differences",
        lambda _connection, _facility_numbers: (
            CcldHostedBackfillDifference(
                facility_number="425802141",
                entity_type="allegation",
                source_record_key="allegation:public-stable-id",
                differing_fields=("original_values.allegation_text",),
                persisted={
                    "original_values.allegation_text": {
                        "type": "string",
                        "length": 20,
                        "sha256": "a" * 64,
                    }
                },
                prepared={
                    "original_values.allegation_text": {
                        "type": "string",
                        "length": 21,
                        "sha256": "b" * 64,
                    }
                },
            ),
        ),
    )
    monkeypatch.setattr(
        cli,
        "run_ccld_hosted_backfill",
        lambda *_args, **_kwargs: pytest.fail("write-capable backfill must not run"),
    )

    assert (
        cli.main(
            [
                "--facility-number",
                "425802141",
                "--operation",
                "preserved-artifacts",
                "--diagnose-differences",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    assert '"schema_version":"recordstracker.ccld-backfill-differences.v1"' in output
    assert '"difference_count":1' in output
    assert "original_values.allegation_text" in output
    assert "a" * 64 in output
    assert connection.commits == 0
    assert connection.rollbacks == 1


def test_cli_difference_diagnostic_rejects_unbounded_selection(capsys: Any) -> None:
    cli = _load_cli_module()
    assert (
        cli.main(
            [
                "--all-existing",
                "--operation",
                "preserved-artifacts",
                "--diagnose-differences",
            ]
        )
        == 2
    )
    assert "requires explicit Facility IDs" in capsys.readouterr().err


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
        "$MaxFacilities",
        "$CheckpointFile",
        "$Restart",
        "$Apply",
        "$DryRun",
        "$DiagnoseDifferences",
        "$QnapContainer",
        "docker compose",
    ):
        assert token in wrapper
    assert "Omit both for dry-run" in wrapper
    assert "canonical-complaint-observations" in wrapper
    assert "--diagnose-differences" in wrapper
    diagnostic_start = wrapper.index('if ($DiagnoseDifferences) {')
    diagnostic_end = wrapper.index('if ($QnapContainer)', diagnostic_start)
    diagnostic_mode = wrapper[diagnostic_start:diagnostic_end]
    diagnostic_branch = diagnostic_mode.split('elseif ($Apply)', 1)[0]
    assert '$arguments += "--diagnose-differences"' in diagnostic_branch
    assert '"--dry-run"' not in diagnostic_branch
    assert '"--apply"' not in diagnostic_branch
    assert 'elseif ($Apply)' in diagnostic_mode
    assert 'else {\n    $arguments += "--dry-run"\n}' in diagnostic_mode
    assert (
        '@("facility-reference", "preserved-artifacts", '
        '"canonical-complaint-observations")'
        in wrapper
    )


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
