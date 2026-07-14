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
        "Issue418",
        "manifest.json",
        "route-status.csv",
        "route-assertions.csv",
        "issue-415-count-summaries.csv",
        "issue-415-href-inventory.csv",
        "issue-416-count-summaries.csv",
        "issue-417-count-summaries.csv",
        "issue-418-count-summaries.csv",
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
        'if ($Mode -eq "fixture") { "900000001" } else { "434417302" }',
        "/ccld/facilities/detail?facility_number=$facilityHubNumber",
        "/ccld/records/request",
        "/ccld/retrieval/jobs",
        "/reviewer",
        "/reviewer/facilities/priorities",
        "/reviewer/facilities/trends",
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
    assert '$Html.Contains("Complaint worklist")' in script
    assert '$Html.Contains("Review complaint")' in script
    assert "05-reviewer-complaint-exports.png" in script
    assert 'Join-RouteUrl -Base $normalizedBaseUrl -Path "/reviewer"' in script
    assert "#complaint-export-controls" in script
    assert "complaint export" in script.lower()
    assert "-Issue415" in script
    assert "-Issue416" in script
    assert "-Issue417" in script
    assert "-Issue418" in script
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
        "issue417 semantic contract",
        "issue417 no unsupported conclusions",
        "issue417 source category basis",
        "issue417 keyword cue basis",
        "issue417 filtered controls",
        "issue417 filtered empty",
        "issue417 no narrative leak",
    ):
        assert issue_417_assertion in script
    for issue_418_route in (
        "/reviewer/facilities/trends?facility=157806098",
        "time_grain=quarter&period_count=4",
        "Issue418Kind = \"increased\"",
        "Issue418Kind = \"secondary-cue\"",
        "Issue418Kind = \"incomplete\"",
        "finding=Substantiated&start_date=2022-04-01",
    ):
        assert issue_418_route in script
    for issue_418_assertion in (
        "issue418 h1",
        "issue418 count reconciliation",
        "issue418 semantic table",
        "issue418 labeled controls",
        "issue418 transparent rules",
        "issue418 increased activity cue",
        "issue418 incomplete period",
        "issue418 zero qualifying",
        "issue418 safe aggregate output",
    ):
        assert issue_418_assertion in script


def issue_417_assertion_function() -> str:
    script = CAPTURE_SCRIPT.read_text(encoding="utf-8")
    start = script.index("function Test-Issue417RouteAssertions")
    end = script.index("\nfunction Get-SafeDynamicHref", start)
    return script[start:end]


def run_issue_417_assertions(
    kind: str,
    text: str,
    *,
    matching: int = 1,
    html: str | None = None,
) -> list[dict[str, object]]:
    html_text = html or (
        "<html><body><h1>Serious-topic complaint worklist</h1>"
        '<label>Review topic</label><input name="topic">'
        '<label>Match basis</label><select name="match_basis"></select>'
        '<input name="finding"><input name="facility"><input name="geography">'
        '<input name="start_date"></body></html>'
    )
    ps_script = f"""
$script:Issue417Matching = {matching}
function Get-Issue417CountSummary {{
    param([string]$Text)
    [pscustomobject]@{{ Found = $true; Matching = $script:Issue417Matching; Total = 1 }}
}}
function Get-Issue417Rows {{
    param([string]$Html)
    @()
}}
function Add-Issue417PassFail {{
    param(
        [System.Collections.ArrayList]$Assertions,
        [string]$RouteName,
        [string]$Check,
        [bool]$Pass,
        [string]$PassMessage,
        [string]$FailMessage
    )
    [void]$Assertions.Add([pscustomobject]@{{
        route = $RouteName
        check = $Check
        passed = $Pass
        failMessage = $FailMessage
    }})
}}
{issue_417_assertion_function()}
$assertions = [System.Collections.ArrayList]::new()
$route = @{{ Name = 'issue-417-{kind}'; Issue417Kind = '{kind}' }}
$html = @'
{html_text}
'@
$text = @'
{text}
'@
Test-Issue417RouteAssertions -Route $route -Html $html -Text $text -Assertions $assertions
$assertions | ConvertTo-Json -Compress
"""
    result = subprocess.run(
        [powershell(), "-NoProfile", "-Command", ps_script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, plain_output(result)
    payload = json.loads(result.stdout)
    if isinstance(payload, dict):
        return [payload]
    return payload


def issue_417_base_text(*, links: bool = False) -> str:
    parts = [
        "Serious-topic complaint worklist",
        "Source categories come from public records.",
        "Review topics and possible keyword cues help narrow records for review.",
    ]
    if links:
        parts.extend(
            [
                "Open original public report",
                "Open complaint review workspace",
            ]
        )
    return " ".join(parts)


def failed_issue_417_checks(assertions: list[dict[str, object]]) -> set[str]:
    return {str(row["check"]) for row in assertions if row["passed"] is not True}


def issue_418_assertion_functions() -> str:
    script = CAPTURE_SCRIPT.read_text(encoding="utf-8")
    start = script.index("function Get-Issue418CountSummary")
    end = script.index("\nfunction Get-SafeDynamicHref", start)
    return script[start:end]


def run_issue_418_zero_assertion(
    *,
    qualifying: int,
    state: str,
    cue: str = "No anomaly cue",
) -> dict[str, object]:
    html_text = (
        "<html><body><h1>Review complaint trends over time</h1>"
        "<table><caption>Complaint trends</caption><tr><th>Period</th></tr></table>"
        '<input name="facility"><input name="facility_type">'
        '<input name="geography"><input name="finding">'
        '<input name="serious_topic"><input name="start_date">'
        '<input name="end_date"><input name="time_grain">'
        f'<input name="period_count"><span>{state}</span><strong>{cue}</strong>'
        "</body></html>"
    )
    text = " ".join(
        (
            "Review complaint trends over time",
            (
                f"{qualifying} qualifying complaint record(s): {qualifying} "
                "assigned to displayed periods and 0 with date unavailable"
            ),
            (
                "Anomaly cue definitions: increased activity means at least twice "
                "the preceding count; decreased activity means no more than half."
            ),
            f"{state} {cue} Current period: 0; preceding period: not available",
        )
    )
    ps_script = f"""
function Add-AssertionResult {{
    param(
        [System.Collections.ArrayList]$Target,
        [string]$RouteName,
        [string]$Check,
        [string]$Status,
        [string]$Message
    )
    [void]$Target.Add([pscustomobject]@{{
        route = $RouteName
        check = $Check
        status = $Status
        message = $Message
    }})
}}
{issue_418_assertion_functions()}
$assertions = [System.Collections.ArrayList]::new()
$route = @{{ Name = 'issue-418-zero'; Issue418Kind = 'zero' }}
$html = @'
{html_text}
'@
$text = @'
{text}
'@
Test-Issue418RouteAssertions -Route $route -Html $html -Text $text -Assertions $assertions
$assertions | Where-Object {{ $_.check -eq 'issue418 zero qualifying' }} | ConvertTo-Json -Compress
"""
    result = subprocess.run(
        [powershell(), "-NoProfile", "-Command", ps_script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, plain_output(result)
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict)
    return payload


def test_issue_418_zero_assertion_accepts_zero_qualifying_records_state() -> None:
    assertion = run_issue_418_zero_assertion(
        qualifying=0,
        state="Zero qualifying records",
    )

    assert assertion["status"] == "PASS"


def test_issue_418_zero_assertion_accepts_coverage_unavailable_state() -> None:
    assertion = run_issue_418_zero_assertion(
        qualifying=0,
        state="Coverage unavailable",
    )

    assert assertion["status"] == "PASS"


def test_issue_418_zero_assertion_rejects_decreased_activity_for_either_state() -> None:
    for state in ("Zero qualifying records", "Coverage unavailable"):
        assertion = run_issue_418_zero_assertion(
            qualifying=0,
            state=state,
            cue="Decreased activity",
        )

        assert assertion["status"] == "FAIL"


def test_issue_418_zero_assertion_rejects_nonzero_qualifying_count() -> None:
    assertion = run_issue_418_zero_assertion(
        qualifying=1,
        state="Zero qualifying records",
    )

    assert assertion["status"] == "FAIL"


def test_issue_418_zero_assertion_requires_no_anomaly_cue() -> None:
    assertion = run_issue_418_zero_assertion(
        qualifying=0,
        state="Coverage unavailable",
        cue="",
    )

    assert assertion["status"] == "FAIL"


def test_issue_417_assertions_accept_shared_semantic_explanation_without_row_labels() -> None:
    assertions = run_issue_417_assertions(
        "default",
        issue_417_base_text(links=True),
    )

    assert failed_issue_417_checks(assertions) == set()
    assert "Source category" not in issue_417_base_text()
    assert "Possible keyword cue" not in issue_417_base_text()


def test_issue_417_assertions_accept_keyword_filtered_and_empty_shared_explanation() -> None:
    keyword_assertions = run_issue_417_assertions(
        "keyword-cue",
        issue_417_base_text() + " Filter basis: Possible keyword cue.",
        matching=1,
    )
    filtered_assertions = run_issue_417_assertions(
        "filtered",
        issue_417_base_text(),
    )
    empty_assertions = run_issue_417_assertions(
        "empty",
        issue_417_base_text() + " No serious-topic complaint records matched. Clear filters",
        matching=0,
    )

    assert failed_issue_417_checks(keyword_assertions) == set()
    assert failed_issue_417_checks(filtered_assertions) == set()
    assert failed_issue_417_checks(empty_assertions) == set()


def test_issue_417_assertions_keep_route_specific_basis_checks() -> None:
    source_assertions = run_issue_417_assertions(
        "source-category",
        issue_417_base_text(),
    )
    keyword_assertions = run_issue_417_assertions(
        "keyword-cue",
        issue_417_base_text(),
        matching=1,
    )

    assert failed_issue_417_checks(source_assertions) == {
        "issue417 source category basis"
    }
    assert failed_issue_417_checks(keyword_assertions) == {
        "issue417 keyword cue basis"
    }


def test_issue_417_assertions_keep_unsupported_conclusion_check() -> None:
    assertions = run_issue_417_assertions(
        "default",
        issue_417_base_text(links=True) + " Keyword cues are findings.",
    )

    assert "issue417 no unsupported conclusions" in failed_issue_417_checks(assertions)


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


def test_capture_script_issue_418_mode_writes_focused_artifacts() -> None:
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
                "-Issue418",
                "-AllowUnavailable",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        output = plain_output(result)

        assert result.returncode == 0, output
        packets = sorted(output_dir.glob("*-live-issue-418"))
        assert packets, output
        packet = packets[-1]
        manifest = json.loads((packet / "manifest.json").read_text(encoding="utf-8-sig"))
        count_csv = (packet / "issue-418-count-summaries.csv").read_text(
            encoding="utf-8-sig"
        )
        assertions_csv = (packet / "route-assertions.csv").read_text(
            encoding="utf-8-sig"
        )
        capture_command = (packet / "diagnostics" / "capture-command.txt").read_text(
            encoding="utf-8-sig"
        )

        assert (packet / "issue-418-count-summaries.csv").exists()
        assert manifest["issue418"]["enabled"] is True
        assert manifest["issue418"]["routeCount"] == 7
        assert manifest["output"]["counts"]["issue418"] == 1
        assert len(manifest["routeList"]) == 7
        assert "/reviewer/facilities/trends?facility=157806098" in count_csv
        assert "issue418 h1" in assertions_csv
        assert "-Issue418" in capture_command
        assert "Focused issue #418 complaint trend evidence" in manifest[
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
