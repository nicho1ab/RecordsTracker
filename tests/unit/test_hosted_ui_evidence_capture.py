from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAPTURE_SCRIPT = ROOT / "scripts" / "capture-hosted-ui-evidence.ps1"
WRAPPER_SCRIPT = ROOT / "scripts" / "run-and-capture-hosted-ui-evidence.ps1"
GUIDE = ROOT / "docs" / "developer" / "ui-evidence-review.md"


def read_repo_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def powershell() -> str:
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if shell is None:
        raise AssertionError("PowerShell is required for hosted UI evidence tests.")
    return shell


def plain_output(result: subprocess.CompletedProcess[str]) -> str:
    output = result.stdout + result.stderr
    without_ansi = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", output)
    return " ".join(without_ansi.split())


def test_capture_script_declares_parameters_routes_and_outputs() -> None:
    script = CAPTURE_SCRIPT.read_text(encoding="utf-8")

    assert CAPTURE_SCRIPT.exists()
    assert len(re.findall(r"(?m)^param\(", script)) == 1
    for expected in (
        "[string]$BaseUrl",
        '[ValidateSet("live", "fixture", "scaffold")]',
        '$OutputDir = "data/processed/ui-evidence"',
        "$ViewportWidth = 1440",
        "$ViewportHeight = 1200",
        "$TimeoutSeconds = 10",
        "$IncludeHtml = $true",
        "$IncludeScreenshots = $true",
        "AllowUnavailable",
        "manifest.json",
        "route-status.csv",
        "route-assertions.csv",
        "route-text-markers.txt",
        "accessibility",
        "diagnostics",
        "EVIDENCE_PACKET_PATH=",
    ):
        assert expected in script
    for route in (
        "/",
        "/ccld/facilities",
        "/ccld/records/request",
        "/ccld/retrieval/jobs",
        "/reviewer",
        "/feedback",
        "/ccld/help",
    ):
        assert route in script
    assert "BaseUrl must be localhost or a private test IP address" in script
    assert "OutputDir must be inside the ignored data/processed folder" in script
    assert "screenshot tool" in script.lower()
    assert "This evidence packet is local UI review evidence only" in script


def test_capture_script_boundaries_are_get_only_and_non_mutating() -> None:
    script = CAPTURE_SCRIPT.read_text(encoding="utf-8")
    lowered = script.casefold()

    assert "invoke-webrequest" in lowered
    for forbidden in (
        "-method post",
        "invoke-restmethod",
        "run_controlled_ccld_retrieval",
        "load_local_validated_ccld_records",
        "reviewer_note",
        "reviewer_status",
        "api." + "github.com",
        "https://www.ccld.dss.ca.gov",
        "docker compose",
        "client_" + "secr" + "et" + "=",
    ):
        assert forbidden not in lowered
    for guarded_marker in (
        "author" + "ization:",
        "github" + "_pat_",
        "gh" + "p_",
        "set-" + "cookie",
        "traceback (most recent call last)",
    ):
        assert guarded_marker in lowered
    assert '"stack trace"' not in lowered


def test_wrapper_script_uses_existing_modes_and_prints_process_guidance() -> None:
    script = WRAPPER_SCRIPT.read_text(encoding="utf-8")

    assert WRAPPER_SCRIPT.exists()
    for expected in (
        '[ValidateSet("live", "fixture", "scaffold")]',
        "KillExistingPortProcess",
        "run-hosted-complaint-retrieval-live.ps1",
        "run-hosted-complaint-retrieval-demo.ps1",
        "run-hosted-scaffold.ps1",
        "capture-hosted-ui-evidence.ps1",
        "URL to open:",
        "Started process ID:",
        "Stop command: Stop-Process -Id",
    ):
        assert expected in script
    assert "-KillExistingPortProcess" in script
    assert "Stop-Process" in script


def test_capture_script_allow_unavailable_writes_manifest() -> None:
    output_dir = ROOT / "data" / "processed" / "ui-evidence-test"
    shutil.rmtree(output_dir, ignore_errors=True)
    try:
        result = subprocess.run(
            [
                powershell(),
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(CAPTURE_SCRIPT),
                "-BaseUrl",
                "http://127.0.0.1:9",
                "-Mode",
                "fixture",
                "-OutputDir",
                "data/processed/ui-evidence-test",
                "-TimeoutSeconds",
                "1",
                "-IncludeScreenshots:$false",
                "-AllowUnavailable",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        output = plain_output(result)

        assert result.returncode == 0, output
        assert "EVIDENCE_PACKET_PATH=" in output
        packets = sorted(output_dir.glob("*-fixture"))
        assert packets, output
        packet = packets[-1]
        manifest = json.loads((packet / "manifest.json").read_text(encoding="utf-8-sig"))

        assert (packet / "route-status.csv").exists()
        assert (packet / "route-assertions.csv").exists()
        assert (packet / "route-text-markers.txt").exists()
        assert (packet / "accessibility" / "headings.txt").exists()
        assert (packet / "diagnostics" / "capture-command.txt").exists()
        assert manifest["mode"] == "fixture"
        assert manifest["baseUrl"] == "http://127.0.0.1:9"
        assert manifest["safety"]["getOnly"] is True
        assert manifest["safety"]["formsSubmitted"] is False
        assert manifest["safety"]["retrievalSubmitted"] is False
        assert manifest["safety"]["reviewerStateMutated"] is False
        assert manifest["safety"]["importsOrReloadsRun"] is False
        assert manifest["routeFailures"]
        assert "local UI review evidence only" in manifest["boundaryStatement"]
    finally:
        shutil.rmtree(output_dir, ignore_errors=True)


def test_ui_evidence_documentation_links_commands_and_boundaries() -> None:
    guide = GUIDE.read_text(encoding="utf-8")
    testing_doc = read_repo_text("docs/developer/testing.md")
    runbook = read_repo_text("RUNBOOK.md")
    readme = read_repo_text("README.md")
    changelog = read_repo_text("CHANGELOG.md")

    assert GUIDE.exists()
    for expected in (
        "Why Evidence Packets Exist",
        ".\\scripts\\run-hosted-complaint-retrieval-live.ps1 -Port 8003",
        ".\\scripts\\capture-hosted-ui-evidence.ps1 -BaseUrl http://127.0.0.1:8003 -Mode live",
        ".\\scripts\\run-hosted-complaint-retrieval-demo.ps1 -Port 8010",
        ".\\scripts\\capture-hosted-ui-evidence.ps1 -BaseUrl http://127.0.0.1:8010 -Mode fixture",
        "8003` = live public CCLD mode",
        "8010` = fixture/mock demo mode",
        "Upload or summarize the whole timestamped folder",
        "not an audit export, legal report, source-completeness report",
        "data/processed/ui-evidence",
    ):
        assert expected in guide
    assert "docs/developer/ui-evidence-review.md" in readme
    assert "docs/developer/ui-evidence-review.md" in runbook
    assert "capture-hosted-ui-evidence.ps1" in testing_doc
    assert "capture-hosted-ui-evidence.ps1" in changelog
    assert "run-and-capture-hosted-ui-evidence.ps1" in guide
