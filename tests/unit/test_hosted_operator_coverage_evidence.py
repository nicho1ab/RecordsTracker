from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "capture-operator-coverage-dashboard-evidence.ps1"


def test_operator_evidence_script_has_exact_bounded_interface_and_outputs() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert SCRIPT.is_file()
    assert len(re.findall(r"(?m)^param\(", script)) == 1
    for marker in (
        '[string]$OutputRoot = "data\\processed\\ui-evidence"',
        "[int]$Port",
        '[ValidateSet("contract-v1")]',
        "[string]$FixtureMode",
        "route-assertions.csv",
        "route-status.csv",
        "manifest.json",
        "Compress-Archive",
        "EVIDENCE_PACKET_PATH=",
        "EVIDENCE_ZIP_PATH=",
        "EVIDENCE_ASSERTIONS=PASS",
    ):
        assert marker in script
    assert "OutputRoot must remain under the ignored data/processed directory" in script


def test_operator_evidence_script_starts_fresh_branch_bound_fixture_servers() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    for marker in (
        'expectedBranch = "integrate-453-477-coverage-dashboard"',
        "git -C $repoRoot branch --show-current",
        "git -C $repoRoot rev-parse HEAD",
        "Test-LoopbackPortInUse",
        "refusing to reuse an existing server",
        "Start-Process -FilePath $python",
        "-WindowStyle Hidden",
        "Stop-Process -Id $server.Id -Force",
        "operator_coverage_fixture_mode",
        "operator_coverage_commit_sha",
        "operator_coverage_branch",
        'server_fresh_per_scenario = $true',
    ):
        assert marker in script


def test_operator_evidence_browser_paths_are_exact_get_only_allowlist() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    browser_paths = set(
        re.findall(r'\[ordered\]@\{ Label = "[^"]+"; Path = "([^"]+)"', script)
    )

    assert browser_paths
    for path in browser_paths:
        base = path.split("?", 1)[0]
        assert base in {
            "/operator/source-coverage",
            "/operator/source-coverage/facilities",
            "/operator/source-coverage/jobs",
            "/operator/source-coverage/export.csv",
            "/operator/source-coverage/facility-ids.csv",
        }
    assert 'urllib.request.Request(url, method="GET")' in script
    assert 'page.goto(url, wait_until="networkidle"' in script
    assert "page.click(" not in script
    assert "page.fill(" not in script
    assert "method=\"POST\"" not in script
    assert "http://" in script
    assert "https://" not in script


def test_operator_evidence_covers_required_states_viewports_and_accessibility() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    for scenario in (
        "producer-complete-balanced",
        "complete-balanced",
        "empty-verified",
        "partial-unavailable-stage",
        "unavailable-package",
        "interrupted-job-previous-accepted-active",
        "failed-reconciliation",
        "hash-validation-failure",
        "version-mismatch",
        "raw-733-unresolved",
        "pagination-adjacent-pages",
    ):
        assert f'Name = "{scenario}"' in script
    for marker in (
        "Width = 1440; Height = 1100",
        "Width = 720; Height = 900",
        "Width = 390; Height = 844",
        "Width = 360; Height = 450; DeviceScaleFactor = 2",
        'Kind = "focus"',
        'Kind = "print"',
        'Kind = "download"',
        "page.keyboard.press",
        'page.emulate_media(media="print")',
        "page.pdf(",
        "no horizontal page overflow",
        "semantic heading order",
        "single h1",
        "keyboard focus reaches visible control",
        "operator link present once in operator navigation",
        "GET-only forms",
        "no mutation controls",
    ):
        assert marker in script
    for requirement in (
        "RT-DOM-001",
        "RT-TIER-001",
        "RT-STATE-001",
        "RT-RWD-001",
        "RT-A11Y-001",
        "RT-A11Y-002",
        "RT-STRESS-001",
        "RT-PRINT-001",
        "RT-SAFE-001",
    ):
        assert requirement in script


def test_operator_evidence_uses_real_producer_package_through_stable_boundary() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    for marker in (
        "load_coverage_fixture_scenario",
        "generate_coverage_package",
        "validate_coverage_package",
        "load_validated_coverage_package",
        "COVERAGE_ARTIFACT_MEDIA_TYPES",
        "COVERAGE_AGGREGATE_CSV_FIELDNAMES",
        'Name = "producer-complete-balanced"',
        'producer_contract = $producerContract',
        "The real Issue 453 producer package did not pass the stable consumer boundary",
    ):
        assert marker in script


def test_operator_evidence_proves_reviewer_absence_without_browser_scope_expansion() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert 'route_response(route, page_data_mode="fixture-demo")' in script
    assert 'for route in ("/reviewer", "/ccld")' in script
    assert "operator route leaked into reviewer-tier HTML" in script
    assert "No browser navigation outside the exact allowlist was used" in script
    assert not re.search(r'Path = "/(?:reviewer|ccld)', script)


def test_operator_evidence_script_has_no_mutating_route_or_runtime_action() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    for route in (
        "/retry",
        "/apply",
        "/cancel",
        "/resume",
        "/backfill",
    ):
        assert route not in script
    assert "Invoke-RestMethod -Uri \"$baseUrl/health\" -Method Get" in script
    assert "Invoke-WebRequest" not in script
    assert "database write" in script
    assert "retry deferred" in script
    assert "apply deferred" in script


def test_operator_evidence_script_parses_as_powershell() -> None:
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if powershell is None:
        pytest.skip("PowerShell parsing is unavailable on this runner.")

    command = (
        "$tokens=$null; $errors=$null; "
        "[System.Management.Automation.Language.Parser]::ParseFile("
        f"'{SCRIPT.as_posix()}',[ref]$tokens,[ref]$errors) > $null; "
        "if($errors.Count){ $errors | Format-List; exit 1 }"
    )
    result = subprocess.run(
        [powershell, "-NoProfile", "-Command", command],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
