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
        "Issue415",
        "Issue416",
        "Issue417",
        "manifest.json",
        "route-status.csv",
        "route-assertions.csv",
        "issue-415-count-summaries.csv",
        "issue-415-href-inventory.csv",
        "issue-416-count-summaries.csv",
        "issue-417-count-summaries.csv",
        "route-text-markers.txt",
        "keyboard flow text",
        "accessibility",
        "diagnostics",
        "EVIDENCE_PACKET_PATH=",
        "EVIDENCE_ZIP_PATH=",
        "Compress-Archive",
        "Invoke-NativeCaptureCommand",
        "Test-HtmlScreenshotCandidate",
        "native screenshot command timed out",
        "screenshotFailures",
        "route, assertion, or screenshot failures",
        "$Route.Path -match",
        "bytes written to file",
        "do not commit them unless a specific repository workflow explicitly says to do so",
    ):
        assert expected in script
    for route in (
        "/",
        "/ccld/facilities",
        "/ccld/facilities/review-priority",
        "/ccld/facilities/intelligence",
        "/ccld/facilities/detail?facility_number=434417302",
        "/ccld/records/request",
        "/ccld/retrieval/jobs",
        "/reviewer",
        "/reviewer/facilities/priorities",
        "/reviewer/records/substantiated",
        "/reviewer/records/serious-topics",
        "/reviewer/records/matrix.csv",
        "/feedback",
        "/ccld/help",
    ):
        assert route in script
    assert "BaseUrl must be localhost or a private test IP address" in script
    assert "OutputDir must be inside the ignored data/processed folder" in script
    assert "screenshot tool" in script.lower()
    assert "Local hosted UI review evidence" in script
    assert "05-reviewer-complaint-exports.png" in script
    assert 'Join-RouteUrl -Base $normalizedBaseUrl -Path "/reviewer"' in script
    assert "#complaint-export-controls" in script
    assert "complaint export" in script.lower()
    assert "-Issue415" in script
    assert "-Issue416" in script
    assert "-Issue417" in script
    for issue_415_route in (
        "/reviewer/records/substantiated?facility=107207198",
        "/reviewer/records/substantiated?facility_type=FOSTER%20FAMILY%20AGENCY",
        "/reviewer/records/substantiated?sort=facility_asc&page_size=25",
        "/reviewer/records/substantiated?start_date=2099-01-01&end_date=2099-12-31",
    ):
        assert issue_415_route in script
    for issue_415_assertion in (
        "issue415 default total nonzero",
        "issue415 facility ids",
        "issue415 facility type rows",
        "issue415 facility sort az",
        "issue415 future empty",
        "issue415 original and workspace href inventory",
        "True browser zoom is not controlled by this script",
    ):
        assert issue_415_assertion in script
    for issue_416_route in (
        "/reviewer/facilities/priorities?facility_type=FOSTER%20FAMILY%20AGENCY&geography=Kern&min_complaints=1&min_substantiated=0&indicator=source_available",
        "/reviewer/facilities/priorities?page_size=10",
        "/reviewer/facilities/priorities?min_complaints=9999",
    ):
        assert issue_416_route in script
    for issue_416_assertion in (
        "issue416 h1",
        "issue416 no hidden score",
        "issue416 filtered controls",
        "issue416 page size",
        "issue416 filtered empty",
    ):
        assert issue_416_assertion in script
    for issue_417_route in (
        "/reviewer/records/serious-topics?match_basis=source-category",
        "/reviewer/records/serious-topics?match_basis=keyword-cue",
        "/reviewer/records/serious-topics?topic=Supervision%20topic",
        "/reviewer/records/serious-topics?topic=Runaway%2FAWOL%20topic",
    ):
        assert issue_417_route in script
    for issue_417_assertion in (
        "issue417 h1",
        "issue417 concepts labeled",
        "issue417 no unsupported conclusions",
        "issue417 category/cue wording",
        "issue417 source category basis",
        "issue417 keyword cue basis",
        "issue417 filtered controls",
        "issue417 filtered empty",
        "issue417 no narrative leak",
    ):
        assert issue_417_assertion in script


def test_capture_script_review_context_is_get_only_and_non_mutating() -> None:
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
        assert "EVIDENCE_ZIP_PATH=" in output
        assert "Output counts:" in output
        packets = sorted(output_dir.glob("*-fixture"))
        assert packets, output
        packet = packets[-1]
        zips = sorted(output_dir.glob("*-fixture.zip"))
        assert zips, output
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
        assert "Local hosted UI review evidence" in manifest["evidencePurpose"]
        assert manifest["output"]["zipPacket"].endswith(".zip")
        assert manifest["output"]["counts"]["html"] == 0
        assert manifest["output"]["counts"]["text"] == 0
        assert manifest["output"]["counts"]["diagnostics"] >= 3
        assert manifest["output"]["counts"]["accessibility"] >= 4
        assert zips[-1].exists()
    finally:
        shutil.rmtree(output_dir, ignore_errors=True)


def test_capture_script_issue_415_mode_writes_focused_artifacts() -> None:
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
                "live",
                "-OutputDir",
                "data/processed/ui-evidence-test",
                "-TimeoutSeconds",
                "1",
                "-IncludeScreenshots:$false",
                "-Issue415",
                "-AllowUnavailable",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        output = plain_output(result)

        assert result.returncode == 0, output
        packets = sorted(output_dir.glob("*-live-issue-415"))
        assert packets, output
        packet = packets[-1]
        manifest = json.loads((packet / "manifest.json").read_text(encoding="utf-8-sig"))
        count_csv = (packet / "issue-415-count-summaries.csv").read_text(
            encoding="utf-8-sig"
        )
        href_csv = (packet / "issue-415-href-inventory.csv").read_text(
            encoding="utf-8-sig"
        )
        assertions_csv = (packet / "route-assertions.csv").read_text(
            encoding="utf-8-sig"
        )

        assert (packet / "issue-415-count-summaries.csv").exists()
        assert (packet / "issue-415-href-inventory.csv").exists()
        assert manifest["issue415"]["enabled"] is True
        assert manifest["output"]["counts"]["issue415"] == 2
        assert len(manifest["routeList"]) == 5
        assert "/reviewer/records/substantiated?facility=107207198" in count_csv
        assert "sourceRecordKey,facilityId,complaintId,finding,date" in href_csv
        assert "issue415 count summary" in assertions_csv
        assert "True browser zoom is not controlled by this script" in json.dumps(
            manifest
        )
    finally:
        shutil.rmtree(output_dir, ignore_errors=True)


def test_capture_script_issue_416_mode_writes_focused_artifacts() -> None:
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
                "live",
                "-OutputDir",
                "data/processed/ui-evidence-test",
                "-TimeoutSeconds",
                "1",
                "-IncludeScreenshots:$false",
                "-Issue416",
                "-AllowUnavailable",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        output = plain_output(result)

        assert result.returncode == 0, output
        packets = sorted(output_dir.glob("*-live-issue-416"))
        assert packets, output
        packet = packets[-1]
        manifest = json.loads((packet / "manifest.json").read_text(encoding="utf-8-sig"))
        count_csv = (packet / "issue-416-count-summaries.csv").read_text(
            encoding="utf-8-sig"
        )
        assertions_csv = (packet / "route-assertions.csv").read_text(
            encoding="utf-8-sig"
        )
        capture_command = (packet / "diagnostics" / "capture-command.txt").read_text(
            encoding="utf-8-sig"
        )

        assert (packet / "issue-416-count-summaries.csv").exists()
        assert manifest["issue416"]["enabled"] is True
        assert manifest["issue416"]["routeCount"] == 4
        assert manifest["output"]["counts"]["issue416"] == 1
        assert len(manifest["routeList"]) == 4
        assert "/reviewer/facilities/priorities?page_size=10" in count_csv
        assert "issue416 h1" in assertions_csv
        assert "-Issue416" in capture_command
        assert "Focused issue #416 facility prioritization evidence" in manifest[
            "evidencePurpose"
        ]
    finally:
        shutil.rmtree(output_dir, ignore_errors=True)


def test_capture_script_issue_417_mode_writes_focused_artifacts() -> None:
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
                "live",
                "-OutputDir",
                "data/processed/ui-evidence-test",
                "-TimeoutSeconds",
                "1",
                "-IncludeScreenshots:$false",
                "-Issue417",
                "-AllowUnavailable",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        output = plain_output(result)

        assert result.returncode == 0, output
        packets = sorted(output_dir.glob("*-live-issue-417"))
        assert packets, output
        packet = packets[-1]
        manifest = json.loads((packet / "manifest.json").read_text(encoding="utf-8-sig"))
        count_csv = (packet / "issue-417-count-summaries.csv").read_text(
            encoding="utf-8-sig"
        )
        assertions_csv = (packet / "route-assertions.csv").read_text(
            encoding="utf-8-sig"
        )
        capture_command = (packet / "diagnostics" / "capture-command.txt").read_text(
            encoding="utf-8-sig"
        )

        assert (packet / "issue-417-count-summaries.csv").exists()
        assert manifest["issue417"]["enabled"] is True
        assert manifest["issue417"]["routeCount"] == 5
        assert manifest["output"]["counts"]["issue417"] == 1
        assert len(manifest["routeList"]) == 5
        assert "/reviewer/records/serious-topics?match_basis=keyword-cue" in count_csv
        assert "issue417 h1" in assertions_csv
        assert "-Issue417" in capture_command
        assert "Focused issue #417 serious-topic complaint worklist evidence" in manifest[
            "evidencePurpose"
        ]
    finally:
        shutil.rmtree(output_dir, ignore_errors=True)


def test_capture_script_restores_local_dev_auth_env_after_capture() -> None:
    output_dir = ROOT / "data" / "processed" / "ui-evidence-test"
    shutil.rmtree(output_dir, ignore_errors=True)
    try:
        capture_call = (
            f"& '{CAPTURE_SCRIPT}' -BaseUrl 'http://127.0.0.1:9' -Mode fixture "
            "-OutputDir 'data/processed/ui-evidence-test' -TimeoutSeconds 1 "
            "-IncludeScreenshots:$false -AllowUnavailable | Out-Null; "
        )
        post_env_json = (
            "$post=[ordered]@{ "
            "pageData=[Environment]::GetEnvironmentVariable("
            "'CCLD_HOSTED_PAGE_DATA_MODE','Process'); "
            "authMode=[Environment]::GetEnvironmentVariable("
            "'CCLD_HOSTED_TESTER_AUTH_MODE','Process'); "
            "localDev=[Environment]::GetEnvironmentVariable("
            "'CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH','Process') "
            "}; "
            "Write-Output ('POST_ENV_JSON=' + ($post | ConvertTo-Json -Compress))"
        )
        unset_command = (
            "$ErrorActionPreference='Stop'; "
            "$vars=@("
            "'CCLD_HOSTED_PAGE_DATA_MODE',"
            "'CCLD_HOSTED_TESTER_AUTH_MODE',"
            "'CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH'"
            "); "
            "foreach($v in $vars){ "
            "Remove-Item -LiteralPath (\"Env:{0}\" -f $v) "
            "-ErrorAction SilentlyContinue "
            "}; "
            + capture_call
            + post_env_json
        )
        unset_result = subprocess.run(
            [
                powershell(),
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                unset_command,
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        unset_output = plain_output(unset_result)
        assert unset_result.returncode == 0, unset_output
        unset_match = re.search(r"POST_ENV_JSON=(\{.*\})", unset_output)
        assert unset_match, unset_output
        unset_env = json.loads(unset_match.group(1))
        assert unset_env["pageData"] is None
        assert unset_env["authMode"] is None
        assert unset_env["localDev"] is None

        preserve_command = (
            "$ErrorActionPreference='Stop'; "
            "$env:CCLD_HOSTED_PAGE_DATA_MODE='pre-existing-page'; "
            "$env:CCLD_HOSTED_TESTER_AUTH_MODE='pre-existing-auth'; "
            "$env:CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH='pre-existing-local'; "
            + capture_call
            + post_env_json
        )
        preserve_result = subprocess.run(
            [
                powershell(),
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                preserve_command,
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        preserve_output = plain_output(preserve_result)
        assert preserve_result.returncode == 0, preserve_output
        preserve_match = re.search(r"POST_ENV_JSON=(\{.*\})", preserve_output)
        assert preserve_match, preserve_output
        preserved_env = json.loads(preserve_match.group(1))
        assert preserved_env["pageData"] == "pre-existing-page"
        assert preserved_env["authMode"] == "pre-existing-auth"
        assert preserved_env["localDev"] == "pre-existing-local"
    finally:
        shutil.rmtree(output_dir, ignore_errors=True)


def test_ui_evidence_documentation_links_commands_and_review_context() -> None:
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
        "Upload or summarize the sibling ZIP",
        "actual rendered UI",
        "Evidence is not useful if no one reviews it",
        "Do not commit generated",
        "tester-readiness verifier",
        "keyboard-flow marker assertions",
        "sibling ZIP",
        "local UI review artifact",
        "route, screenshot, text, and accessibility review",
        "data/processed/ui-evidence",
    ):
        assert expected in guide
    assert "docs/developer/ui-evidence-review.md" in readme
    assert "docs/developer/ui-evidence-review.md" in runbook
    assert "capture-hosted-ui-evidence.ps1" in testing_doc
    assert "capture-hosted-ui-evidence.ps1" in changelog
    assert "run-and-capture-hosted-ui-evidence.ps1" in guide
