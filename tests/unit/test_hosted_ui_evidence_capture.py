from __future__ import annotations

import inspect
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[2]
CAPTURE_SCRIPT = ROOT / "scripts" / "capture-hosted-ui-evidence.ps1"
WRAPPER_SCRIPT = ROOT / "scripts" / "run-and-capture-hosted-ui-evidence.ps1"
GUIDE = ROOT / "docs" / "developer" / "ui-evidence-review.md"
ISSUE_647_CAPTURE_PLAN = (
    ROOT
    / "tests"
    / "fixtures"
    / "hosted_ui_evidence_capture"
    / "issue_647_location_capture_plan.json"
)
ISSUE_644_PACKET_ACCOUNTING_FIXTURE = (
    ROOT
    / "tests"
    / "fixtures"
    / "hosted_ui_evidence_capture"
    / "issue_644_packet_accounting_fixture.ps1"
)
ISSUE_644_RUNTIME_EVENT_FIXTURE = (
    ROOT
    / "tests"
    / "fixtures"
    / "hosted_ui_evidence_capture"
    / "issue_644_runtime_event_classification_fixture.ps1"
)


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


def capture_plan_rejection_output(plan_text: str) -> str:
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary_directory:
        plan_path = Path(temporary_directory) / "capture-plan.json"
        plan_path.write_text(plan_text, encoding="utf-8")
        result = subprocess.run(
            [
                powershell(),
                "-NoProfile",
                "-File",
                str(CAPTURE_SCRIPT),
                "-BaseUrl",
                "http://127.0.0.1:1",
                "-Mode",
                "fixture",
                "-CapturePlanPath",
                str(plan_path.relative_to(ROOT)),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
    assert result.returncode != 0
    return plain_output(result)


def powershell_function(function_name: str, next_function_name: str) -> str:
    script = CAPTURE_SCRIPT.read_text(encoding="utf-8")
    start = script.index(f"function {function_name}")
    end = script.index(f"\nfunction {next_function_name}", start)
    return script[start:end]


def wrapper_port_guard_functions() -> str:
    script = WRAPPER_SCRIPT.read_text(encoding="utf-8")
    start = script.index("function Get-PortListenerObservation")
    end = script.index("\nfunction Get-TaskOwnedProcessIds", start)
    return script[start:end]


def run_optional_git_revision_resolution(
    *,
    origin_main: str | None = None,
    local_main: str | None = None,
    event_path: Path | None = None,
) -> dict[str, object]:
    resolver = powershell_function("Resolve-OptionalGitRevision", "Test-AllowedBaseUrl")
    event_literal = "$null" if event_path is None else json.dumps(str(event_path))
    origin_literal = json.dumps(origin_main or "")
    local_literal = json.dumps(local_main or "")
    mock_git = "\n".join(
        (
            "function git {",
            "  param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)",
            "  $reference = $Arguments[-1]",
            f"  if ($reference -eq 'origin/main^{{commit}}' -and {origin_literal}) {{",
            f"    {origin_literal}; $global:LASTEXITCODE = 0; return",
            "  }",
            f"  if ($reference -eq 'main^{{commit}}' -and {local_literal}) {{",
            f"    {local_literal}; $global:LASTEXITCODE = 0; return",
            "  }",
            "  $global:LASTEXITCODE = 128",
            "}",
        )
    )
    ps_script = (
        resolver
        + "\n"
        + mock_git
        + "\n"
        + "Resolve-OptionalGitRevision -GitHubEventPath "
        + event_literal
        + " | ConvertTo-Json -Depth 6\n"
    )
    result = subprocess.run(
        [powershell(), "-NoProfile", "-Command", ps_script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, plain_output(result)
    return json.loads(result.stdout)


def test_optional_git_revision_resolution_tolerates_missing_refs_without_stderr_value() -> None:
    resolution = run_optional_git_revision_resolution()

    assert resolution["Available"] is False
    assert resolution["Sha"] == ""
    assert resolution["Source"] == "unavailable"
    assert resolution["Attempts"] == ["git:origin/main", "git:main"]


def test_optional_git_revision_resolution_uses_valid_remote_then_local_ref() -> None:
    remote_sha = "A" * 40
    remote = run_optional_git_revision_resolution(origin_main=remote_sha, local_main="B" * 40)
    local = run_optional_git_revision_resolution(local_main="C" * 40)

    assert remote == {
        "Available": True,
        "Sha": remote_sha.lower(),
        "Source": "git:origin/main",
        "Attempts": [],
    }
    assert local["Available"] is True
    assert local["Sha"] == ("C" * 40).lower()
    assert local["Source"] == "git:main"
    assert local["Attempts"] == ["git:origin/main"]


def test_optional_git_revision_resolution_uses_only_valid_github_pull_request_base_metadata(
    tmp_path: Path,
) -> None:
    valid_event = tmp_path / "event.json"
    valid_event.write_text(
        json.dumps({"pull_request": {"base": {"sha": "D" * 40}}}), encoding="utf-8"
    )
    invalid_event = tmp_path / "invalid-event.json"
    invalid_event.write_text(
        json.dumps({"pull_request": {"base": {"sha": "not-a-sha"}}}), encoding="utf-8"
    )

    valid = run_optional_git_revision_resolution(event_path=valid_event)
    invalid = run_optional_git_revision_resolution(event_path=invalid_event)

    assert valid["Available"] is True
    assert valid["Sha"] == ("D" * 40).lower()
    assert valid["Source"] == "github-event:pull_request.base.sha"
    assert invalid["Available"] is False
    assert invalid["Sha"] == ""
    assert invalid["Source"] == "unavailable"
    assert invalid["Attempts"][-1] == "github-event:pull_request.base.sha-invalid"


def test_issue_655_base_revision_metadata_is_strict_or_explicitly_unavailable() -> None:
    script = CAPTURE_SCRIPT.read_text(encoding="utf-8")

    assert "function Resolve-OptionalGitRevision" in script
    assert "git rev-parse --verify --quiet" in script
    assert "2>$null" in script
    assert "Issue #655 evidence requires an authoritative base SHA" in script
    assert "-not $AllowUnavailable" in script
    assert "baseShaStatus=if ($gitBaseResolution.Available)" in script
    assert "(& git merge-base HEAD origin/main).Trim()" not in script


def run_screenshot_tool_resolution(
    requested: str,
    *,
    require_interaction: bool,
    candidates: list[dict[str, object]],
) -> dict[str, object]:
    resolver = powershell_function("Resolve-ScreenshotTool", "Join-NativeArgument")
    candidates_json = json.dumps(candidates)
    interaction_literal = "$true" if require_interaction else "$false"
    ps_script = (
        resolver
        + "\n$candidates = @(ConvertFrom-Json -InputObject @'\n"
        + candidates_json
        + "\n'@)\n"
        + "$validator = { param($candidate) [pscustomobject]@{ "
        + "Usable = [bool]$candidate.ProbeUsable; Status = [string]$candidate.ProbeStatus } }\n"
        + f"Resolve-ScreenshotTool -Requested '{requested}' "
        + f"-RequireInteractionAware {interaction_literal} "
        + "-Candidates $candidates -Validator $validator | ConvertTo-Json -Depth 8\n"
    )
    result = subprocess.run(
        [powershell(), "-NoProfile", "-Command", ps_script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, plain_output(result)
    return json.loads(result.stdout)


def run_issue_498_scenario_contract(state: str, kind: str = "state") -> dict[str, object]:
    contract_function = powershell_function(
        "Get-Issue498ScenarioContract", "Invoke-Issue498BrowserCapture"
    )
    ps_script = (
        contract_function
        + "\n$route = @{ Name = 'contract-test'; Issue498State = '"
        + state
        + "'; Issue498Kind = '"
        + kind
        + "' }\n"
        + "Get-Issue498ScenarioContract -Route $route | ConvertTo-Json -Depth 8\n"
    )
    result = subprocess.run(
        [powershell(), "-NoProfile", "-Command", ps_script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, plain_output(result)
    return json.loads(result.stdout)


def run_interaction_browser_session_constructor() -> dict[str, object]:
    constructor = powershell_function(
        "New-InteractionBrowserSessionState", "Start-InteractionAwareBrowserSession"
    )
    ps_script = (
        constructor
        + "\n$output = @(New-InteractionBrowserSessionState "
        + "-Socket ([pscustomobject]@{ Name = 'socket' }) "
        + "-Process ([pscustomobject]@{ Name = 'process' }) -ProfileDir 'profile')\n"
        + "$state = $output[0]\n"
        + "$before = $state.NextId\n"
        + "$state.NextId = 1\n"
        + "[ordered]@{ Count = $output.Count; Type = $state.GetType().FullName; "
        + "Properties = @($state.PSObject.Properties.Name); NextIdBefore = $before; "
        + "NextIdAfter = $state.NextId } | ConvertTo-Json -Depth 8\n"
    )
    result = subprocess.run(
        [powershell(), "-NoProfile", "-Command", ps_script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, plain_output(result)
    return json.loads(result.stdout)


def run_malformed_cdp_session_checks() -> dict[str, object]:
    cdp_command = powershell_function("Invoke-CdpCommand", "Invoke-CdpEvaluate")
    ps_script = (
        cdp_command
        + "\nfunction Get-GuardMessage { param([object]$Value) "
        + "try { Invoke-CdpCommand -Session $Value -Method 'test' | Out-Null; 'NO_ERROR' } "
        + "catch { $_.Exception.Message } }\n"
        + "$arrayState = @([pscustomobject]@{ NextId = 0 }, [pscustomobject]@{ NextId = 0 })\n"
        + "$missingState = [pscustomobject]@{ NextId = 0 }\n"
        + "$readOnlyState = [pscustomobject]@{ Socket = 's'; Process = 'p'; ProfileDir = 'd' }\n"
        + "$readOnlyState | Add-Member -MemberType ScriptProperty -Name NextId -Value { 0 }\n"
        + "$incrementState = [pscustomobject]@{ Socket = $null; Process = 'p'; "
        + "ProfileDir = 'd'; NextId = 0 }\n"
        + "try { Invoke-CdpCommand -Session $incrementState -Method 'test' | Out-Null } catch { }\n"
        + "[ordered]@{ Null = Get-GuardMessage $null; Array = Get-GuardMessage $arrayState; "
        + "Missing = Get-GuardMessage $missingState; ReadOnly = Get-GuardMessage $readOnlyState; "
        + "Incremented = $incrementState.NextId } "
        + "| ConvertTo-Json -Depth 8\n"
    )
    result = subprocess.run(
        [powershell(), "-NoProfile", "-Command", ps_script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, plain_output(result)
    return json.loads(result.stdout)


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
        '[ValidateSet("auto", "playwright", "edge", "chrome")]',
        '$ScreenshotToolPreference = "auto"',
        "AllowUnavailable",
        "CapturePlanPath",
        "Issue415",
        "Issue416",
        "Issue417",
        "Issue418",
        "Issue419",
        "Issue503",
        "Issue498",
        "Issue610",
        "Issue641",
        "Issue642",
        "manifest.json",
        "file-index.json",
        "reviews/independent-visual-review.json",
        "reviews/owner-acceptance.json",
        "recordstracker.hosted-ui-acceptance.v1",
        "PENDING_INDEPENDENT_VISUAL_REVIEW",
        "PENDING_OWNER_DECISION",
        "NOT_ACCEPTED",
        "automationMayAccept = $false",
        "scripts/validate_hosted_ui_acceptance.py",
        "route-status.csv",
        "route-assertions.csv",
        "issue-415-count-summaries.csv",
        "issue-415-href-inventory.csv",
        "issue-416-count-summaries.csv",
        "issue-417-count-summaries.csv",
        "issue-418-count-summaries.csv",
        "issue-419-approved-versus-rendered.csv",
        "issue-419-ui-gates.csv",
        "issue-503-route-fragment-inventory.csv",
        "issue-503-approved-versus-rendered.csv",
        "issue-503-ui-gates.csv",
        "issue-642-complaint-patterns",
        "Invoke-Issue642BrowserCapture",
        "Test-Issue642RouteAssertions",
        "nativeCheckboxControls",
        "route-text-markers.txt",
        "keyboard flow text",
        "accessibility",
        "diagnostics",
        "EVIDENCE_PACKET_PATH=",
        "EVIDENCE_ZIP_PATH=",
        "EVIDENCE_ZIP_SHA256=",
        "Compress-Archive",
        "Get-FileHash",
        "Test-EvidencePacketFiles",
        "Test-EvidenceZipIntegrity",
            "Evidence ZIP membership, sizes, or SHA-256 hashes do not match the packet file index.",
        "Invoke-NativeCaptureCommand",
        "Test-HtmlScreenshotCandidate",
        "SkipHttpErrorCheck",
        "native screenshot command timed out",
        "$visibilityDeadline",
        "Start-Sleep -Milliseconds 50",
        "screenshotFailures",
        "route, assertion, or screenshot failures",
        "governed shared shell",
        "authoritative primary navigation",
        "primary navigation product tiers",
        "mode badge",
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
    assert (
        '"facility-intelligence" = @('
        '"Find Facilities That May Need Closer Review", '
        '"Complaint Patterns")'
        in script
    )
    assert (
        'Path = "/ccld/facilities/intelligence"; '
        'Label = "02-facility-intelligence"; '
        'ActiveHref = "/ccld/facilities/intelligence"; '
        'WorkflowStep = "Review"'
        in script
    )
    assert (
        'Name = "jobs"; Path = "/ccld/retrieval/jobs"; '
        'Label = "04-job-status"; WorkflowStep = "Status"'
        in script
    )
    assert (
        'Name = "job-detail"; Path = $jobDetailHref; '
        'Label = "08-job-detail"; WorkflowStep = "Status"'
        in script
    )
    assert '$modePanelCount -eq 1' in script
    assert 'Check "mode badge" -Status "FAIL"' in script
    assert "Expected shared-shell mode marker" in script
    assert "05-reviewer-complaint-exports.png" in script
    assert 'Join-RouteUrl -Base $normalizedBaseUrl -Path "/reviewer"' in script
    assert "#complaint-export-controls" in script
    assert "complaint export" in script.lower()
    assert "-Issue415" in script
    assert "-Issue416" in script
    assert "-Issue417" in script
    assert "-Issue418" in script
    assert "-Issue419" in script
    assert "-Issue503" in script
    assert "-Issue498" in script
    assert "-Issue610" in script
    assert "-Issue641" in script
    assert "Issue #641 evidence routes are local fixture/demo-only" in script
    assert "Issue #641 geometry gate failed" in script
    assert "document.documentElement.scrollWidth > clientWidth" in script
    assert "overflowingRequired" in script
    assert "Issue #641 selected filter control text is clipped" in script
    assert "fullExpectedText" in script
    assert "clippingResult" in script
    assert "availableTextWidth" in script
    assert "pageHorizontalOverflow" in script
    assert "gridColumnCount" in script
    assert "issue641 expected visible state" in script
    assert "issue641 optional category absence" in script
    assert "issue-641-compare-1280-page-scale-200" in script
    assert "Issue641PageScaleFactor = 2.0" in script
    assert "requested page-scale evidence was not applied" in script
    assert "issue-641-evidence-gates.csv" in script
    assert "I641-GEOMETRY-003" in script
    for issue_641_control_assertion in (
        "I641-CONTROL-430-1440",
        "I641-CONTROL-733-1440",
        "I641-CONTROL-430-1024",
        "I641-CONTROL-430-768",
        "I641-CONTROL-430-400",
        "I641-CONTROL-430-390",
        "I641-CONTROL-430-200",
        "I641-CONTROL-DATE-DIMENSION-200",
        "I641-SUMMARY-RECONCILIATION",
    ):
        assert issue_641_control_assertion in script
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
        "view=complaint-priority-compatibility&facility_type=FOSTER%20FAMILY%20AGENCY&geography=Kern&min_complaints=1&min_substantiated=0&indicator=source_available",
        "view=complaint-priority-compatibility&page_size=10",
        "view=complaint-priority-compatibility&min_complaints=9999",
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
        "view=complaint-activity-over-time",
        "facility=157806098",
        "time_grain=quarter&period_count=4",
        'Issue418Kind = "increased"',
        'Issue418Kind = "secondary-cue"',
        'Issue418Kind = "incomplete"',
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
    for issue_419_scenario in (
        "issue-419-default",
        "issue-419-licensing",
        "issue-419-trends",
        "issue-419-narrow-desktop",
        "issue-419-mobile",
        "issue-419-reflow",
        "issue-419-keyboard-focus",
        "issue-419-filtered-empty",
        "issue-419-source-unavailable",
        "issue-419-limited-data",
        "issue-419-invalid",
        "issue-419-not-loaded",
        "issue-419-error",
        "issue-419-print",
        "issue-419-legacy-licensing",
        "issue-419-legacy-priorities",
        "issue-419-legacy-trends",
    ):
        assert issue_419_scenario in script
    for issue_419_contract in (
        "issue419 canonical heading",
        "issue419 consolidated views",
        "issue419 primary evidence visible",
        "issue419 reviewer-tier safety",
        "issue419 plain-language terminology",
        "issue419 public facility identity presentation",
        "issue419 complaint evidence and drill-down",
        "issue419 licensing parity and separation",
        "issue419 meaningful licensing filters",
        "issue419 Complaint Worklist terminology",
        "issue419 keyboard focus contract",
        "issue419 responsive contract",
        "issue419 print contract",
        "RT-UI-GATE-009",
        "PENDING_INDEPENDENT_VISUAL_REVIEW",
        "Issue #501 repository-readable controlled variance",
    ):
        assert issue_419_contract in script
    for issue_420_scenario in (
        "issue-420-populated-desktop",
        "issue-420-source-unavailable-filter",
        "issue-420-reviewer-state-filter",
        "issue-420-narrow-desktop",
        "issue-420-mobile",
        "issue-420-reflow",
        "issue-420-keyboard-filter",
        "issue-420-filtered-empty",
        "issue-420-zero-complaint",
        "issue-420-missing-identity-values",
        "issue-420-print",
    ):
        assert issue_420_scenario in script
    for issue_420_contract in (
        "issue420 Facility Overview heading",
        "issue420 reviewer-tier safety",
        "issue420 no primary disclosure stack",
        "issue420 canonical complaint inventory",
        "issue420 source and reviewer state separation",
        "issue420 single primary next action",
        "issue420 filter and reconciliation contract",
        "issue420 complaint return continuity",
        "issue420 compact empty state",
        "issue420 responsive contract",
        "issue420 keyboard focus contract",
        "issue420 missing identity consolidation",
        "issue420 partial and stale transparency",
        "issue420 print contract",
        "issue420 distinct missing identity screenshot",
        "issue420 partial coverage consolidation",
        "issue420 print image differs from screen",
        "issue-420-duplicate-images.json",
        "issue-420-print-validation.json",
        "render-pdf-pages.ps1",
        "Emulation.setEmulatedMedia",
        "Page.printToPDF",
        "issue-420-approved-versus-rendered.csv",
        "issue-420-source-reconciliation.csv",
        "issue-420-ui-gates.csv",
        "PENDING_INDEPENDENT_VISUAL_REVIEW",
    ):
        assert issue_420_contract in script
    for issue_498_scenario in (
        "rt-src-002-supported-closed",
        "rt-src-002-supported-open",
        "rt-src-002-supported-open-narrow-desktop",
        "rt-src-002-supported-open-mobile-compact",
        "rt-src-002-supported-open-200-percent-reflow-approximation",
        "rt-src-002-keyboard-focus",
        "rt-src-002-document-only",
        "rt-src-002-field-partial",
        "rt-src-002-source-unavailable",
        "rt-src-002-print",
        "rt-src-002-focus-return",
    ):
        assert issue_498_scenario in script
    for issue_498_contract in (
        "issue498 intended evidence state",
        "issue498 supported evidence fields",
        "issue498 document-only boundaries",
        "issue498 field-partial boundary",
        "issue498 unavailable source action",
        "issue498 keyboard focus contract",
        "issue498 print contract",
        "Issue #498 evidence routes are local fixture/demo-only",
        "exact true browser zoom remains manual visual evidence",
        "Invoke-RoutePrint",
        "Invoke-Issue498BrowserCapture",
    ):
        assert issue_498_contract in script
    for issue_610_contract in (
        "issue-610-populated-print",
        "issue-610-source-unavailable",
        "headers and footers off",
    ):
        assert issue_610_contract in script
    for fixture_key in (
        "ccld-complaint-32-CR-20240603151515-rt-src-002-supported-fixture",
        "ccld-complaint-32-CR-20240610181818-rt-src-002-document-only-fixture",
        "complaint%3Accld%3Acomplaint%3A32-CR-20220407124448",
        "ccld-complaint-32-CR-20240120111111-rt-src-002-source-unavailable-fixture",
    ):
        assert fixture_key in script


def test_capture_plan_is_reusable_fixture_only_and_covers_issue_647_location_states() -> None:
    plan = json.loads(ISSUE_647_CAPTURE_PLAN.read_text(encoding="utf-8"))
    script = CAPTURE_SCRIPT.read_text(encoding="utf-8")
    guide = GUIDE.read_text(encoding="utf-8")

    assert plan["dataMode"] == "fixture-demo"
    assert plan["governanceIssue"] == "#647"
    assert plan["purpose"]
    assert len(plan["limitations"]) >= 2
    assert {scenario["id"] for scenario in plan["scenarios"]} == {
        "facility-157806098-unavailable-location",
        "facility-900000001-complete-location",
    }
    by_id = {scenario["id"]: scenario for scenario in plan["scenarios"]}
    unavailable = by_id["facility-157806098-unavailable-location"]
    complete = by_id["facility-900000001-complete-location"]
    assert unavailable["facilityId"] == "157806098"
    assert unavailable["classification"] == "governed unavailable-location presentation"
    assert unavailable["expectedLocationState"] == "unavailable"
    unavailable_compare = unavailable["routes"][2]
    assert unavailable_compare["screenshotMode"] == "supplemental-tall"
    assert unavailable_compare["requiredText"] == [
        "A. MIRIAM JAMISON CHILDREN'S CENTER",
        "Facility ID 157806098",
        "Blank in source",
    ]
    assert complete["facilityId"] == "900000001"
    assert complete["classification"] == "explicitly synthetic governed fixture"
    assert complete["expectedLocationState"] == "complete"
    assert "100 Example Way, Sample City, CA 90001" in complete["routes"][1]["requiredText"]

    for scenario in plan["scenarios"]:
        routes = scenario["routes"]
        assert {route["kind"] for route in routes} == {
            "search",
            "overview",
            "compare",
            "complaint-detail",
        }
        for route in routes:
            if route.get("applicability") == "not-applicable":
                assert route["reason"]

    assert "function Read-CapturePlan" in script
    assert "function New-CapturePlanRoutes" in script
    assert "function Test-CapturePlanRouteAssertions" in script
    assert "function Assert-CapturePlanPropertyNames" in script
    assert "CapturePlanPath must stay inside the repository root." in script
    assert "require -Mode fixture" in script
    assert "Test-CapturePlanRouteAssertions -Route $Route" in script
    assert "fileName = $capturePlan.FileName" in script
    assert "governanceIssue = $capturePlan.GovernanceIssue" in script
    assert 'else { "#648" }' in script
    assert "['SupplementalScreenshotHeight'] = 3000" in script
    assert "Supplemental screenshot capture failed:" in script
    assert "CapturePlanPath" not in script[script.index("capturePlan            ="):]
    assert "Path=$path" not in script
    assert "complaint-detail routes are not supported" in script
    assert "if ($null -ne $capturePlan) { $routesToCapture" in script
    assert "CapturePlanPath <repository JSON path>" in guide


def test_capture_plan_rejects_invalid_data_without_execution() -> None:
    valid_plan = json.loads(ISSUE_647_CAPTURE_PLAN.read_text(encoding="utf-8"))
    cases = {
        "malformed JSON": ("{", "Capture plan JSON is malformed."),
        "empty purpose": (
            json.dumps({**valid_plan, "purpose": " "}),
            "Capture plan requires a non-empty 'purpose'.",
        ),
        "empty limitations": (
            json.dumps({**valid_plan, "limitations": []}),
            "Capture plan requires at least one limitation.",
        ),
        "unsupported mode": (
            json.dumps({**valid_plan, "dataMode": "production"}),
            "Capture plan dataMode 'production' is unsupported.",
        ),
        "malformed governance issue": (
            json.dumps({**valid_plan, "governanceIssue": "647"}),
            "Capture plan governanceIssue '647' is invalid.",
        ),
        "unknown root property": (
            json.dumps({**valid_plan, "command": "Write-Output should-not-run"}),
            "Capture plan root has unsupported property 'command'.",
        ),
        "duplicate scenario": (
            json.dumps({**valid_plan, "scenarios": valid_plan["scenarios"] * 2}),
            "Capture plan has duplicate scenario id",
        ),
        "bad facility id": (
            json.dumps(
                {
                    **valid_plan,
                    "scenarios": [
                        {**valid_plan["scenarios"][0], "facilityId": "not-a-facility"}
                    ],
                }
            ),
            "Capture plan facility id 'not-a-facility' is invalid.",
        ),
        "unsupported route": (
            json.dumps(
                {
                    **valid_plan,
                    "scenarios": [
                        {
                            **valid_plan["scenarios"][0],
                            "routes": [
                                {"kind": "external-url", "requiredText": ["safe"]}
                            ],
                        }
                    ],
                }
            ),
            "Capture plan route 'external-url' is unsupported.",
        ),
        "duplicate route kind": (
            json.dumps(
                {
                    **valid_plan,
                    "scenarios": [
                        {
                            **valid_plan["scenarios"][0],
                            "routes": [
                                {"kind": "search", "requiredText": ["one"]},
                                {"kind": "search", "requiredText": ["two"]},
                            ],
                        }
                    ],
                }
            ),
            "has duplicate route kind 'search'.",
        ),
        "unsafe route property": (
            json.dumps(
                {
                    **valid_plan,
                    "scenarios": [
                        {
                            **valid_plan["scenarios"][0],
                            "routes": [
                                {
                                    "kind": "search",
                                    "requiredText": ["safe"],
                                    "path": "/not-allowed",
                                }
                            ],
                        }
                    ],
                }
            ),
            "has unsupported property 'path'.",
        ),
        "unsupported screenshot mode": (
            json.dumps(
                {
                    **valid_plan,
                    "scenarios": [
                        {
                            **valid_plan["scenarios"][0],
                            "routes": [
                                {
                                    "kind": "compare",
                                    "screenshotMode": "arbitrary-height",
                                    "requiredText": ["safe"],
                                }
                            ],
                        }
                    ],
                }
            ),
            "Capture plan screenshotMode 'arbitrary-height' is unsupported.",
        ),
    }

    for case_name, (plan_text, expected) in cases.items():
        output = capture_plan_rejection_output(plan_text)
        assert expected in output, case_name
        assert "should-not-run" not in output


def test_capture_plan_rejects_missing_and_outside_repository_paths(tmp_path: Path) -> None:
    missing = subprocess.run(
        [
            powershell(),
            "-NoProfile",
            "-File",
            str(CAPTURE_SCRIPT),
            "-BaseUrl",
            "http://127.0.0.1:1",
            "-Mode",
            "fixture",
            "-CapturePlanPath",
            "tests/fixtures/hosted_ui_evidence_capture/missing-capture-plan.json",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    outside_plan = tmp_path / "outside-capture-plan.json"
    outside_plan.write_text("{}", encoding="utf-8")
    outside = subprocess.run(
        [
            powershell(),
            "-NoProfile",
            "-File",
            str(CAPTURE_SCRIPT),
            "-BaseUrl",
            "http://127.0.0.1:1",
            "-Mode",
            "fixture",
            "-CapturePlanPath",
            str(outside_plan),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert missing.returncode != 0
    assert "Capture plan file is missing." in plain_output(missing)
    assert outside.returncode != 0
    assert "CapturePlanPath must stay inside the repository root." in plain_output(outside)


def test_capture_script_verifies_zip_membership_sizes_and_hash(tmp_path: Path) -> None:
    stop_capture_fail = powershell_function("Stop-CaptureFail", "Test-AllowedBaseUrl")
    relative_path = powershell_function("ConvertTo-RelativeEvidencePath", "Redact-EvidenceText")
    file_index = powershell_function("Get-EvidenceFileIndex", "Test-EvidencePacketFiles")
    packet_files = powershell_function("Test-EvidencePacketFiles", "Test-EvidenceZipIntegrity")
    zip_integrity = powershell_function("Test-EvidenceZipIntegrity", "Add-AssertionResult")
    packet = tmp_path / "packet"
    zip_path = tmp_path / "packet.zip"
    packet_literal = str(packet).replace("'", "''")
    zip_literal = str(zip_path).replace("'", "''")
    ps_script = (
        stop_capture_fail
        + "\n"
        + relative_path
        + "\n"
        + file_index
        + "\n"
        + packet_files
        + "\n"
        + zip_integrity
        + "\n$packet = '"
        + packet_literal
        + "'\n$zip = '"
        + zip_literal
        + "'\n"
        + "New-Item -ItemType Directory -Path $packet | Out-Null\n"
        + "Set-Content -LiteralPath (Join-Path $packet 'manifest.json') -Value '{}' -NoNewline\n"
        + "Set-Content -LiteralPath (Join-Path $packet 'route-status.csv') "
        + "-Value 'route,status' -NoNewline\n"
        + "Set-Content -LiteralPath (Join-Path $packet 'route-assertions.csv') "
        + "-Value 'route,assertion' -NoNewline\n"
        + "Set-Content -LiteralPath (Join-Path $packet 'route-text-markers.txt') "
        + "-Value 'marker' -NoNewline\n"
        + "Set-Content -LiteralPath (Join-Path $packet 'README.txt') "
        + "-Value 'evidence' -NoNewline\n"
        + "Compress-Archive -LiteralPath $packet -DestinationPath $zip\n"
        + "$files = @(Test-EvidencePacketFiles -PacketDirectory $packet)\n"
        + "$hash = Test-EvidenceZipIntegrity -PacketDirectory $packet "
        + "-ZipPath $zip -ExpectedFiles $files\n"
        + "$file = @($files | Where-Object { $_.path -eq 'README.txt' })[0]\n"
        + "$length = (Get-Item -LiteralPath $zip).Length\n"
        + "Set-Content -LiteralPath (Join-Path $packet 'README.txt') -Value '' -NoNewline\n"
        + "try { Test-EvidencePacketFiles -PacketDirectory $packet | Out-Null; "
        + "$zero = 'not rejected' } "
        + "catch { $zero = $_.Exception.Message }\n"
        + "Set-Content -LiteralPath (Join-Path $packet 'README.txt') -Value 'evidence' -NoNewline\n"
        + "Set-Content -LiteralPath (Join-Path $packet 'manifest.json') "
        + "-Value 'not-json' -NoNewline\n"
        + "try { Test-EvidencePacketFiles -PacketDirectory $packet | Out-Null; "
        + "$invalidJson = 'not rejected' } "
        + "catch { $invalidJson = $_.Exception.Message }\n"
        + "[ordered]@{ Hash = $hash; Length = $length; FileHash = $file.sha256; "
        + "FileAction = $file.action; FileSource = $file.source; "
        + "FileTimestamp = $file.timestamp; FileSanitization = $file.sanitizationState; "
        + "ZeroLength = $zero; InvalidJson = $invalidJson } | ConvertTo-Json\n"
    )
    result = subprocess.run(
        [powershell(), "-NoProfile", "-Command", ps_script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, plain_output(result)
    verified = json.loads(result.stdout)
    assert re.fullmatch(r"[A-F0-9]{64}", verified["Hash"])
    assert re.fullmatch(r"[A-F0-9]{64}", verified["FileHash"])
    assert verified["FileAction"] == "sanitized-capture-or-derived-text"
    assert verified["FileSource"] == "local fixture evidence capture"
    assert verified["FileTimestamp"].endswith("Z")
    assert "credentials" in verified["FileSanitization"]
    assert verified["Length"] > 0
    assert "zero-length files" in verified["ZeroLength"]
    assert "invalid JSON files" in verified["InvalidJson"]


def test_issue_644_packet_accounting_reconciles_filesystem_zip_manifest_and_reported_counts(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            powershell(),
            "-NoProfile",
            "-File",
            str(ISSUE_644_PACKET_ACCOUNTING_FIXTURE),
            "-TempRoot",
            str(tmp_path),
            "-CaptureScriptPath",
            str(CAPTURE_SCRIPT),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, plain_output(result)
    accounting = json.loads(result.stdout)
    assert accounting["valid"] == {
        "sourceIndexedArtifactCount": 9,
        "finalArtifactCount": 10,
        "zipEntryCount": 10,
        "supplementalArtifactCount": 1,
        "zipSha256": accounting["valid"]["zipSha256"],
    }
    assert re.fullmatch(r"[A-F0-9]{64}", accounting["valid"]["zipSha256"])
    assert "final artifact count does not match final filesystem artifacts" in accounting[
        "incorrectManifestFailure"
    ]
    assert "Reported final artifact count does not match" in accounting[
        "incorrectReportedFailure"
    ]
    assert "supplemental artifact is missing or duplicated" in accounting[
        "omittedSupplementalFailure"
    ]
    assert "file-index self-exclusion is not explicit" in accounting[
        "unexpectedExclusionFailure"
    ]
    assert "duplicate normalized artifact paths" in accounting["duplicatePathFailure"]


def test_issue_644_packet_accounting_includes_supplemental_and_self_excluded_index() -> None:
    fixture_text = ISSUE_644_PACKET_ACCOUNTING_FIXTURE.read_text(encoding="utf-8")
    script = CAPTURE_SCRIPT.read_text(encoding="utf-8")

    assert "New-EvidencePacketAccounting" in fixture_text
    assert "New-EvidenceFileIndex" in fixture_text
    assert "Test-EvidencePacketAccounting" in fixture_text
    assert "supplementalScreenshotPath" in fixture_text
    assert "UseUnexpectedIndexExclusion" in fixture_text
    assert "Assert-UniqueEvidencePaths" in fixture_text
    for prohibited in (
        "-Command",
        "scriptblock]::Create",
        "Invoke-Expression",
        "EncodedCommand",
        "Start-Process",
        "Invoke-WebRequest",
        "msedge.exe",
        "chrome.exe",
    ):
        assert prohibited not in fixture_text
    assert "packetAccounting" in script
    assert "sourceIndexedArtifactCount" in script
    assert "finalArtifactCount" in script
    assert "indexSelfExclusion" in script
    assert "supplementalArtifactCount" in script
    assert "FINAL_ARTIFACT_COUNT=" in script


def test_issue_644_runtime_events_emit_exact_allowlisted_telemetry_classification() -> None:
    command = [
        powershell(), "-NoProfile", "-File", str(ISSUE_644_RUNTIME_EVENT_FIXTURE),
        "-CaptureScriptPath", str(CAPTURE_SCRIPT)
    ]
    result = subprocess.run(
        command,
        cwd=ROOT, text=True, capture_output=True, check=False
    )
    assert result.returncode == 0, plain_output(result)
    value = json.loads(result.stdout)
    valid = value["valid"]
    assert valid["observedConsoleOccurrences"] == valid["classifiedConsoleOccurrences"] == 1
    assert valid["observedNetworkOccurrences"] == valid["classifiedNetworkOccurrences"] == 1
    assert value["valid"]["consoleClassifications"][0]["classification"] == (
        "EXPECTED_OPTIONAL_TELEMETRY"
    )
    assert value["valid"]["consoleClassifications"][0]["correlationBasis"].startswith(
        "context-and-resource:"
    )
    zero = value["zero"]
    assert zero["observedConsoleOccurrences"] == zero["observedNetworkOccurrences"] == 0
    assert "zero inventory" not in value["zero"].get("status", "")


def test_issue_644_runtime_events_reject_unknown_or_application_failures() -> None:
    command = [
        powershell(), "-NoProfile", "-File", str(ISSUE_644_RUNTIME_EVENT_FIXTURE),
        "-CaptureScriptPath", str(CAPTURE_SCRIPT)
    ]
    result = subprocess.run(
        command,
        cwd=ROOT, text=True, capture_output=True, check=False
    )
    assert result.returncode == 0, plain_output(result)
    value = json.loads(result.stdout)
    assert "classification is incomplete" in value["unknown"]
    assert "classification is incomplete" in value["application"]
    assert "duplicate" in value["duplicate"]
    assert "occurrence totals" in value["omitted"]
    assert "omits or references" in value["unobserved"]
    assert "Test-RuntimeEventClassificationLedger" in CAPTURE_SCRIPT.read_text(encoding="utf-8")
    assert "Test-RuntimeEventClassificationLedger" in ISSUE_644_RUNTIME_EVENT_FIXTURE.read_text(
        encoding="utf-8"
    )


def test_issue_641_validation_summary_fails_when_any_failure_count_is_nonzero() -> None:
    summary_function = powershell_function(
        "Get-Issue641ValidationSummary", "Get-EvidenceFileIndex"
    )
    ps_script = f"""
{summary_function}
function Get-SummaryStatus {{
    param(
        [int]$RouteFailures = 0,
        [int]$AssertionFailures = 0,
        [int]$FeatureAssertionFailures = 0,
        [int]$ScreenshotFailures = 0
    )
    $parameters = @{{
        RouteFailures = $RouteFailures
        AssertionFailures = $AssertionFailures
        FeatureAssertionFailures = $FeatureAssertionFailures
        ScreenshotFailures = $ScreenshotFailures
        RequiredFeatureAssertions = @('I641-A')
    }}
    return (Get-Issue641ValidationSummary @parameters).status
}}
$pass = Get-SummaryStatus
$route_failure = Get-SummaryStatus -RouteFailures 1
$assertion_failure = Get-SummaryStatus -AssertionFailures 1
$feature_failure = Get-SummaryStatus -FeatureAssertionFailures 1
$screenshot_failure = Get-SummaryStatus -ScreenshotFailures 1
[ordered]@{{
    pass = $pass
    route = $route_failure
    assertion = $assertion_failure
    feature = $feature_failure
    screenshot = $screenshot_failure
}} | ConvertTo-Json -Compress
"""
    result = subprocess.run(
        [powershell(), "-NoProfile", "-Command", ps_script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, plain_output(result)
    assert json.loads(result.stdout) == {
        "pass": "PASS",
        "route": "FAIL",
        "assertion": "FAIL",
        "feature": "FAIL",
        "screenshot": "FAIL",
    }


def test_capture_script_issue_498_defines_interaction_aware_standard_artifacts() -> None:
    script = CAPTURE_SCRIPT.read_text(encoding="utf-8")

    for expected in (
        'Label = "rt-src-002-01-supported-closed"',
        'Label = "rt-src-002-02-supported-open"',
        'Label = "rt-src-002-03-supported-open-narrow-desktop"',
        "ViewportWidth = 1024; ViewportHeight = 900",
        'Label = "rt-src-002-04-supported-open-mobile-compact"',
        "ViewportWidth = 390; ViewportHeight = 844",
        'Label = "rt-src-002-05-supported-open-200-percent-reflow-approximation"',
        "ViewportWidth = 720; ViewportHeight = 600",
        'Label = "rt-src-002-06-keyboard-focus"',
        'Label = "rt-src-002-07-document-only"',
        'Label = "rt-src-002-08-field-partial"',
        'Label = "rt-src-002-09-source-unavailable"',
        'Label = "rt-src-002-10-print"',
        'Label = "rt-src-002-11-focus-return"',
        "#first-investigation-evidence-toggle",
        'Path = "$issue498SupportedPath#first-investigation-evidence"',
        "[data-source-evidence-region]",
        "toggle.click()",
        "toggle.getAttribute('aria-expanded')",
        "region.hidden",
        "document.activeElement === toggle",
        "Keyboard focus indicator is not visibly styled.",
        "Expected visible evidence text missing:",
        "Expected enabled original-source action is missing.",
        "Unavailable-source state exposes an enabled original-source action.",
        "Open evidence component extends outside the viewport horizontally.",
        "Page-level horizontal overflow was detected.",
        "required visual targets exceed the governed viewport height.",
        "Layout did not reach a stable frame.",
        "document.fonts.ready",
        "Page.captureScreenshot",
        "Emulation.setEmulatedMedia",
        "Page.printToPDF",
        "displayHeaderFooter = $false",
        "preferCSSPageSize = $true",
        "Print claim content is incomplete.",
        "Print-hidden control remains visible:",
        "-browser-state.json",
        "Issue #498 live-state capture failed:",
        'Check "workflow step" -Status "WARN"',
        'Check "keyboard flow text" -Status "WARN"',
    ):
        assert expected in script
    for expected_live_text in (
        "06/12/2024",
        "VISIT DATE: 06/12/2024",
        "report header",
        "Document-level source only.",
        "A supporting source event sentence is not available for this date.",
        "The source section is not available for this date.",
        "Field evidence incomplete.",
        "investigation findings",
        "Source document unavailable.",
        "A preserved source copy is recorded and the original public source can be opened.",
        (
            "A preserved source copy is recorded, but the original public source "
            "cannot currently be opened."
        ),
    ):
        assert expected_live_text in script
    assert "--format=A4" not in script
    assert "rt-src-002-10-print.pdf" not in script


def test_issue_498_contract_separates_claim_date_from_region_text() -> None:
    expected_contracts = {
        "supported": (
            "06/12/2024",
            [
                "VISIT DATE: 06/12/2024",
                "report header",
                "A preserved source copy is recorded and the original public source can be opened.",
            ],
        ),
        "document-only": (
            "06/20/2024",
            [
                "Document-level source only.",
                "A supporting source event sentence is not available for this date.",
                "The source section is not available for this date.",
                "A preserved source copy is recorded and the original public source can be opened.",
            ],
        ),
        "field-partial": (
            "04/14/2022",
            [
                "Field evidence incomplete.",
                "A supporting source event sentence is not available for this date.",
                "investigation findings",
                "A preserved source copy is recorded and the original public source can be opened.",
            ],
        ),
        "source-unavailable": (
            "02/10/2024",
            [
                "Source document unavailable.",
                "VISIT DATE: 02/10/2024",
                "report header",
                (
                    "A preserved source copy is recorded, but the original public source "
                    "cannot currently be opened."
                ),
            ],
        ),
    }

    resolved_contracts: dict[str, dict[str, object]] = {}
    for state, (expected_date, expected_region_texts) in expected_contracts.items():
        contract = run_issue_498_scenario_contract(state)
        resolved_contracts[state] = contract
        assert contract["expectedDate"] == expected_date
        assert contract["expectedRegionTexts"] == expected_region_texts
        assert "expectedTexts" not in contract
        assert contract["closedAccessibleName"] == (
            "View source evidence for First investigation activity date"
        )
        assert contract["openAccessibleName"] == (
            "Close source evidence for First investigation activity date"
        )

    assert "06/20/2024" not in resolved_contracts["document-only"]["expectedRegionTexts"]
    assert "04/14/2022" not in resolved_contracts["field-partial"]["expectedRegionTexts"]


def test_issue_498_capture_positions_and_verifies_visual_targets() -> None:
    script = CAPTURE_SCRIPT.read_text(encoding="utf-8")

    for positioning_contract in (
        "scrollIntoView({ behavior: 'instant', block: 'center', inline: 'nearest' })",
        "window.scrollTo({ top: centeredTop, left: 0, behavior: 'instant' })",
        "await stableFrames()",
        "fullyWithinViewport(dateElement)",
        "intersectsViewport(region)",
        "fullyWithinViewport(evidenceHeading)",
        "fullyWithinViewport(sourceEventValue)",
        "fullyWithinViewport(sourceSectionValue)",
        "fullyWithinViewport(sourceStatusValue)",
        "fullyWithinViewport(toggle)",
        "fullyWithinViewport(sourceAction)",
        "horizontallyWithinViewport(claim)",
        "horizontallyWithinViewport(region)",
        "document.documentElement.scrollWidth <= window.innerWidth + 1",
        "document.body.scrollWidth <= window.innerWidth + 1",
    ):
        assert positioning_contract in script
    assert "getClientRects().length" in script
    assert "getClientRects().length" not in script.split(
        "const intersectsViewport = (element) =>", maxsplit=1
    )[1].split("const fullyWithinViewport", maxsplit=1)[0]


def test_issue_498_keyboard_focus_uses_bounded_cdp_tab_navigation() -> None:
    script = CAPTURE_SCRIPT.read_text(encoding="utf-8")

    for keyboard_contract in (
        'Method "Input.dispatchKeyEvent"',
        '-Key "Tab" -Code "Tab" -VirtualKeyCode 9',
        "$maximumTabPresses = 64",
        "$tabIndex -le $maximumTabPresses",
        'document.activeElement.id === \'first-investigation-evidence-toggle\'',
        "Keyboard navigation did not reach the evidence trigger within",
        "toggle.matches(':focus-visible')",
        "Keyboard focus indicator is not visibly styled.",
    ):
        assert keyboard_contract in script
    assert "toggle.focus()" not in script
    assert "document.body.focus()" not in script


def test_issue_498_keyboard_initial_state_is_awaited_before_native_navigation() -> None:
    script = CAPTURE_SCRIPT.read_text(encoding="utf-8")
    initialization_start = script.index(
        "$keyboardInitialization = Invoke-CdpEvaluate"
    )
    initialization_end = script.index(
        "$keyboardTargetReached = $false", initialization_start
    )
    initialization = script[initialization_start:initialization_end]

    for contract in (
        "-AwaitPromise $true",
        "(async function ()",
        "const initialState = readState();",
        "initialState.expanded === 'true' || initialState.regionVisible === true",
        "toggle.click();",
        "const closedState = await waitForClosedState();",
        "requestAnimationFrame(resolve)",
        "const maximumClosedStateFrames = 120",
        "consecutiveClosedFrames >= 2",
        "state.expanded === 'false'",
        "state.hidden === true",
        "state.regionVisible === false",
        "state.accessibleName === closedAccessibleName",
        "Keyboard initial state is inconsistent and cannot be resolved by one setup activation",
        (
            "Keyboard initial state normalization did not reach the verified closed "
            "state after at most one setup activation"
        ),
        "keyboardInitialExpanded",
        "keyboardInitialRegionVisible",
        "keyboardInitialAccessibleName",
        "keyboardInitialStateNormalized",
        "keyboardClosedStateVerified",
    ):
        assert contract in initialization

    assert initialization.index("const closedState = await waitForClosedState();") < (
        initialization.index("start.focus();")
    )
    assert (
        "if (-not [bool]$keyboardInitialization.keyboardClosedStateVerified)"
        in initialization
    )
    for diagnostic in (
        "keyboardInitialExpanded",
        "keyboardInitialRegionVisible",
        "keyboardInitialAccessibleName",
        "keyboardInitialStateNormalized",
        "keyboardClosedStateVerified",
    ):
        assert f"-NotePropertyName {diagnostic}" in script


def test_issue_498_capture_verifies_governed_accessible_names_and_failure_cleanup() -> None:
    script = CAPTURE_SCRIPT.read_text(encoding="utf-8")

    assert "View source evidence for First investigation activity date" in script
    assert "Close source evidence for First investigation activity date" in script
    assert "toggle.getAttribute('aria-label')" in script
    assert "Closed evidence trigger accessible name is incorrect." in script
    assert "Open evidence trigger accessible name is incorrect during focus-return" in script
    assert "Focus-return closed accessible name is incorrect." in script
    assert "document.activeElement !== toggle || !region.hidden" in script
    assert "Remove-Item -LiteralPath $ScreenshotPath" in script
    assert "Issue #498 live-state capture failed:" in script
    assert "ScreenshotCreated = $false" in script


def test_issue_498_reflow_approximation_uses_governed_upper_and_lower_captures() -> None:
    script = CAPTURE_SCRIPT.read_text(encoding="utf-8")

    assert 'Label = "rt-src-002-05-supported-open-200-percent-reflow-approximation"' in script
    assert (
        'SupplementalScreenshotFileName = '
        '"rt-src-002-05b-supported-open-200-percent-reflow-approximation-lower.png"'
    ) in script
    assert script.count("SupplementalScreenshotFileName =") == 1
    assert "supplementalScreenshotPath" in script
    assert "SupplementalScreenshotCreated" in script
    assert "captureSegments" in script
    assert "name: 'upper'" in script
    assert "name: 'lower'" in script
    assert script.count("viewportWidth: window.innerWidth") >= 2
    assert script.count("viewportHeight: window.innerHeight") >= 2
    assert "window.innerWidth !== 720 || window.innerHeight !== 600" in script
    assert "elementBounds: { claimDate:" in script
    assert "evidenceHeading: bounds(evidenceHeading)" in script
    assert "sourceEvent: bounds(sourceEventValue)" in script
    assert "elementBounds: { sourceSection:" in script
    assert "preservedSourceStatus: bounds(sourceStatusValue)" in script
    assert "originalSourceAction: bounds(sourceAction)" in script
    assert script.count("scrollPosition: { x: window.scrollX, y: window.scrollY }") == 2


def test_issue_498_reflow_segments_preserve_clipping_and_failure_cleanup() -> None:
    script = CAPTURE_SCRIPT.read_text(encoding="utf-8")

    for contract in (
        "fullyWithinViewport(dateElement)",
        "fullyWithinViewport(evidenceHeading)",
        "fullyWithinViewport(sourceEventValue)",
        "fullyWithinViewport(sourceSectionValue)",
        "fullyWithinViewport(sourceStatusValue)",
        "fullyWithinViewport(sourceAction)",
        "Lower reflow evidence region does not intersect the screenshot viewport.",
        "Lower reflow evidence region extends outside the viewport horizontally.",
        "Lower reflow page-level horizontal overflow was detected.",
        "Upper and lower reflow evidence segments were not both verified.",
        "Remove-Item -LiteralPath $SupplementalScreenshotPath",
        "Remove-Item -LiteralPath $supplementalShotFile",
    ):
        assert contract in script


def test_issue_498_focus_return_uses_trusted_native_space_activation() -> None:
    script = CAPTURE_SCRIPT.read_text(encoding="utf-8")
    focus_return_start = script.index("if ($scenarioContract.shouldReturnFocus)")
    focus_return_end = script.index("$scenarioScript =", focus_return_start)
    focus_return_contract = script[focus_return_start:focus_return_end]

    for contract in (
        "Invoke-CdpSpaceActivation -Session $Session",
        'key = " "',
        'code = "Space"',
        "windowsVirtualKeyCode = 32",
        "nativeVirtualKeyCode = 32",
        'text = " "',
        'unmodifiedText = " "',
        'type = "rawKeyDown"',
        'type = "keyUp"',
        "__rtSrc002KeyboardOpenClick",
        "__rtSrc002KeyboardCloseClick",
        "event.isTrusted === true",
        "count === 1",
        "keyboardActivationKey",
        "keyboardOpenTrustedClick",
        "keyboardCloseTrustedClick",
        "focusReturnOpenAccessibleName",
        "document.activeElement.id === 'first-investigation-evidence-toggle'",
    ):
        assert contract in script
    assert "toggle.click()" not in focus_return_contract
    assert '-Key "Enter"' not in script


def test_interaction_browser_session_constructor_returns_one_mutable_state_object() -> None:
    result = run_interaction_browser_session_constructor()

    assert result == {
        "Count": 1,
        "Type": "System.Management.Automation.PSCustomObject",
        "Properties": [
            "Socket",
            "Process",
            "ProfileDir",
            "TaskProcessIds",
            "TaskProcessIdentities",
            "CleanupResult",
            "NextId",
        ],
        "NextIdBefore": 0,
        "NextIdAfter": 1,
    }


def test_browser_session_startup_suppresses_connection_output_and_guards_shape() -> None:
    script = CAPTURE_SCRIPT.read_text(encoding="utf-8")

    assert (
        "$null = $socket.ConnectAsync([Uri]$target.webSocketDebuggerUrl, "
        "$connectTimeout.Token).GetAwaiter().GetResult()"
    ) in script
    assert (
        "$null = $Session.Socket.SendAsync([ArraySegment[byte]]::new($bytes), "
        "[System.Net.WebSockets.WebSocketMessageType]::Text, $true, "
        "$sendTimeout.Token).GetAwaiter().GetResult()"
    ) in script
    assert (
        "$browserSessionOutput = @(Start-InteractionAwareBrowserSession "
        "-Tool $resolvedScreenshotTool)"
    ) in script
    assert "$browserSessionOutput.Count -ne 1" in script
    assert "Returned types: $returnedTypeSummary" in script
    assert '$requiredSessionProperties = @("Socket", "Process", "ProfileDir", "NextId")' in script
    assert "$missingSessionProperties.Count -gt 0" in script


def test_task_owned_cdp_readiness_static_fixture_is_bounded_and_fail_closed(
    tmp_path: Path,
) -> None:
    fixture = (
        ROOT
        / "tests"
        / "fixtures"
        / "hosted_ui_evidence_capture"
        / "issue_667_cdp_readiness_fixture.ps1"
    )
    result = subprocess.run(
        [
            powershell(),
            "-NoProfile",
            "-File",
            str(fixture),
            "-TempRoot",
            str(tmp_path),
            "-CaptureScriptPath",
            str(CAPTURE_SCRIPT),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, plain_output(result)
    readiness_result = json.loads(result.stdout)
    assert readiness_result["Valid"] == "ready"
    assert readiness_result["Normal"] == "ready"
    assert readiness_result["Handoff"] == "ready"
    assert readiness_result["HandoffPolls"] == 2
    assert readiness_result["HandoffRootExited"] is True
    for key in ("MissingOutput", "LateOutput", "Empty"):
        assert readiness_result[key].startswith(
            "BROWSER_AUTOMATION_NO_REQUIRED_OUTPUT:"
        )
    assert all(
        failure.startswith("BROWSER_AUTOMATION_INVALID_REQUIRED_OUTPUT:")
        for failure in readiness_result["Malformed"]
    )
    for key in ("Unreachable", "MissingTarget", "Stale"):
        assert readiness_result[key].startswith(
            "BROWSER_AUTOMATION_INVALID_REQUIRED_OUTPUT:"
        )
    assert readiness_result["OutsideProfile"] == "pending"
    assert readiness_result["OwnedProcessIds"] == [41, 51, 52]
    assert readiness_result["UnrelatedProcessSelected"] is False
    assert readiness_result["SuccessCleanupRemoved"] is True
    assert readiness_result["FailureCleanupRemoved"] is True
    assert readiness_result["ExternalProfilePreserved"] is True

    script = CAPTURE_SCRIPT.read_text(encoding="utf-8")
    for expected in (
        "function Get-TaskOwnedCdpReadiness",
        "function Wait-TaskOwnedCdpReadiness",
        "Remove-Item -LiteralPath $activePortFile -Force",
        "Wait-TaskOwnedCdpReadiness",
        "Get-CimInstance -ClassName Win32_Process",
        "Stop-TaskOwnedBrowserProcesses",
        "http://127.0.0.1:$port/json/list",
    ):
        assert expected in script
    assert 'if ($process.HasExited) {' not in script


def test_task_owned_cleanup_is_bounded_exact_and_fail_closed(tmp_path: Path) -> None:
    fixture = (
        ROOT
        / "tests"
        / "fixtures"
        / "hosted_ui_evidence_capture"
        / "issue_667_cdp_readiness_fixture.ps1"
    )
    result = subprocess.run(
        [
            powershell(),
            "-NoProfile",
            "-File",
            str(fixture),
            "-TempRoot",
            str(tmp_path),
            "-CaptureScriptPath",
            str(CAPTURE_SCRIPT),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, plain_output(result)
    cleanup = json.loads(result.stdout)["Cleanup"]

    immediate = cleanup["Immediate"]
    assert immediate["Success"] is True
    assert immediate["StopRequestedIds"] == []
    assert immediate["RemainingProcessIds"] == []
    assert immediate["ProfileRemovalAttemptCount"] == 1
    assert immediate["InitialProfileRemovalFailed"] is False
    assert immediate["ProfileRemoved"] is True

    delayed_process = cleanup["DelayedProcess"]
    assert delayed_process["Success"] is True
    assert delayed_process["StopRequestedIds"] == [401]
    assert delayed_process["ProcessProviderIds"].count(401) >= 4
    assert delayed_process["RemainingProcessIds"] == []
    assert delayed_process["ProfileRemoved"] is True

    delayed_removal = cleanup["DelayedRemoval"]
    assert delayed_removal["Success"] is True
    assert delayed_removal["InitialProfileRemovalFailed"] is True
    assert delayed_removal["ProfileRemovalAttemptCount"] == 2
    assert delayed_removal["LastRemovalExceptionType"] == "System.IO.IOException"
    assert delayed_removal["LastRemovalExceptionMessage"] == "synthetic profile is in use"
    assert delayed_removal["LastRemovalErrorId"]
    assert delayed_removal["ProfileRemoved"] is True

    permanent_removal = cleanup["PermanentRemoval"]
    assert permanent_removal["Success"] is False
    assert permanent_removal["Classification"] == "path-not-empty"
    assert permanent_removal["ProfileRemovalAttemptCount"] > 1
    assert permanent_removal["LastRemovalExceptionType"] == "System.IO.IOException"
    assert permanent_removal["LastRemovalExceptionMessage"] == (
        "synthetic directory is not empty"
    )
    assert permanent_removal["ProfileRemoved"] is False

    process_timeout = cleanup["ProcessTimeout"]
    assert process_timeout["Success"] is False
    assert process_timeout["Classification"] == "process-timeout"
    assert process_timeout["StopRequestedIds"] == [401]
    assert process_timeout["RemainingProcessIds"] == [401]
    assert process_timeout["ProfileRemovalAttemptCount"] == 0
    assert process_timeout["ProfileRemoved"] is False

    for name in (
        "Empty",
        "Relative",
        "TempRoot",
        "Parent",
        "OutsideRoot",
        "MalformedName",
    ):
        rejected = cleanup["InvalidPaths"][name]
        assert rejected["Success"] is False
        assert rejected["Classification"] == "ownership-rejected"
        assert rejected["ProfilePathValidated"] is False
        assert rejected["FixtureRemovalAttemptCount"] == 0

    assert cleanup["Reparse"]["Success"] is False
    assert cleanup["Reparse"]["Classification"] == "reparse-point-rejected"
    assert cleanup["Reparse"]["FixtureRemovalAttemptCount"] == 0
    assert cleanup["ReparseProfilePreserved"] is True

    for name in ("InsideLink", "OutsideLink", "BrokenLink"):
        link = cleanup[name]
        if cleanup["IsWindows"] and link["Created"] is False:
            assert link["Error"]
            assert link["Cleanup"] is None
            continue
        assert link["Created"] is True
        assert link["Cleanup"]["Success"] is False
        assert link["Cleanup"]["Classification"] == "reparse-point-rejected"
        assert link["Cleanup"]["FixtureRemovalAttemptCount"] == 0
    assert cleanup["InsideLinkTargetPreserved"] is True
    assert cleanup["OutsideLinkTargetPreserved"] is True

    assert cleanup["Sibling"]["Success"] is True
    assert cleanup["Sibling"]["ProfileRemoved"] is True
    assert cleanup["SiblingPreserved"] is True

    assert cleanup["PidReuse"]["Success"] is True
    assert cleanup["PidReuse"]["StopRequestedIds"] == []
    assert cleanup["PidReuse"]["ProcessProviderIds"] == [404, 404]
    assert 999 not in cleanup["PidReuse"]["ProcessProviderIds"]


def test_issue_667_static_fixture_has_no_dynamic_or_live_browser_harness() -> None:
    fixture = (
        ROOT
        / "tests"
        / "fixtures"
        / "hosted_ui_evidence_capture"
        / "issue_667_cdp_readiness_fixture.ps1"
    )
    fixture_text = fixture.read_text(encoding="utf-8")
    test_text = "\n".join(
        (
            inspect.getsource(
                test_task_owned_cdp_readiness_static_fixture_is_bounded_and_fail_closed
            ),
            inspect.getsource(test_task_owned_cleanup_is_bounded_exact_and_fail_closed),
        )
    )
    prohibited = (
        "-Command",
        "scriptblock]::Create",
        "Invoke-Expression",
        "EncodedCommand",
        "run-probe.ps1",
        "Start-Process",
        "Invoke-WebRequest",
        "msedge.exe",
        "chrome.exe",
        ".index(\"function",
    )
    for value in prohibited:
        assert value not in fixture_text
        assert value not in test_text


def test_capture_script_library_only_import_is_side_effect_free(tmp_path: Path) -> None:
    fixture = (
        ROOT
        / "tests"
        / "fixtures"
        / "hosted_ui_evidence_capture"
        / "issue_667_library_import_fixture.ps1"
    )
    result_path = tmp_path / "library-import.json"
    result = subprocess.run(
        [
            powershell(),
            "-NoProfile",
            "-File",
            str(fixture),
            "-CaptureScript",
            str(CAPTURE_SCRIPT),
            "-ResultPath",
            str(result_path),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, plain_output(result)
    assert result.stdout == ""
    import_result = json.loads(result_path.read_text(encoding="utf-8-sig"))
    assert import_result["ContinuedAfterImport"] is True
    assert import_result["CurrentDirectoryUnchanged"] is True
    assert import_result["EnvironmentUnchanged"] is True
    assert import_result["NoArtifactsCreated"] is True
    assert import_result["Functions"] == [True, True, True, True, True]
    assert sorted(path.name for path in tmp_path.iterdir()) == ["library-import.json"]

    normal_result = subprocess.run(
        [powershell(), "-NoProfile", "-File", str(CAPTURE_SCRIPT), "-Mode", "fixture"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert normal_result.returncode != 0
    assert "BaseUrl is required for standalone capture." in plain_output(normal_result)

    script = CAPTURE_SCRIPT.read_text(encoding="utf-8")
    assert "[switch]$LibraryOnly" in script
    assert "if ($LibraryOnly)" in script
    assert script.index("if ($LibraryOnly)") < script.index("$captureEnvOverrides")
    assert script.index("BaseUrl is required for standalone capture.") < script.index(
        "$captureEnvOverrides"
    )


def test_issue_667_library_import_fixture_has_no_dynamic_or_live_browser_harness() -> None:
    fixture = (
        ROOT
        / "tests"
        / "fixtures"
        / "hosted_ui_evidence_capture"
        / "issue_667_library_import_fixture.ps1"
    )
    fixture_text = fixture.read_text(encoding="utf-8")
    prohibited = (
        "-Command",
        "scriptblock]::Create",
        "Invoke-Expression",
        "EncodedCommand",
        "run-probe.ps1",
        "Start-Process",
        "Invoke-WebRequest",
        "msedge.exe",
        "chrome.exe",
        ".index(\"function",
    )
    for value in prohibited:
        assert value not in fixture_text


def test_issue_667_real_edge_probe_is_fixed_and_task_owned() -> None:
    fixture = (
        ROOT
        / "tests"
        / "fixtures"
        / "hosted_ui_evidence_capture"
        / "issue_667_real_edge_probe.ps1"
    )
    fixture_text = fixture.read_text(encoding="utf-8")

    assert fixture.exists()
    assert ". $CaptureScriptPath -LibraryOnly" in fixture_text
    assert "Test-ScreenshotToolCandidate" in fixture_text
    assert "Invoke-RouteScreenshot" in fixture_text
    assert "Start-InteractionAwareBrowserSession" in fixture_text
    assert "Stop-InteractionAwareBrowserSession" in fixture_text
    assert "$session.TaskProcessIds" in fixture_text
    assert "$session.TaskProcessIdentities" in fixture_text
    assert "$session.CleanupResult" in fixture_text
    assert "cleanupAttemptCount" in fixture_text
    assert "cleanupElapsedMilliseconds" in fixture_text
    assert "cleanupInitialDeletionFailed" in fixture_text
    assert "cleanupLastDeletionExceptionType" in fixture_text
    assert "cleanupLastDeletionExceptionMessage" in fixture_text
    assert "cleanupLastDeletionErrorId" in fixture_text
    assert "productionCleanupSucceeded" in fixture_text
    assert "$result.productionCleanupSucceeded -and" in fixture_text
    assert "$result.profileAbsentAfterHarness -and" in fixture_text
    assert "RecordsTracker-issue-667-real-edge-*" in fixture_text
    assert "result.json" in fixture_text
    assert "invocation.json" in fixture_text
    assert "validation.png" in fixture_text
    assert "Function:" not in fixture_text

    prohibited = (
        "-Command",
        "scriptblock]::Create",
        "Invoke-Expression",
        "EncodedCommand",
        "run-probe.ps1",
        "Start-Process",
        "Stop-Process",
        "msedge.exe",
        "chrome.exe",
        "http://",
        "https://",
        "Download",
        "Set-ItemProperty",
        "Register-ScheduledTask",
        "New-Service",
        "Add-MpPreference",
        ".index(\"function",
        "Substring(",
    )
    for value in prohibited:
        assert value not in fixture_text


def test_cdp_command_rejects_malformed_session_state_before_socket_use() -> None:
    messages = run_malformed_cdp_session_checks()

    assert messages["Null"] == "Malformed CDP session state: session is null."
    assert "expected one session object, received array type" in messages["Array"]
    assert "missing required properties: Socket, Process, ProfileDir" in messages["Missing"]
    assert "NextId is not writable" in messages["ReadOnly"]
    assert messages["Incremented"] == 1


def test_screenshot_tool_auto_resolution_skips_noninteractive_candidate() -> None:
    resolution = run_screenshot_tool_resolution(
        "auto",
        require_interaction=True,
        candidates=[
            {
                "Name": "playwright",
                "Kind": "playwright",
                "Command": "playwright.cmd",
                "FullPage": True,
                "InteractionAware": False,
                "Discovery": "test",
                "ProbeUsable": True,
                "ProbeStatus": "usable Playwright CLI and browser executable",
            },
            {
                "Name": "msedge-headless",
                "Kind": "edge",
                "Command": "msedge.exe",
                "FullPage": False,
                "InteractionAware": True,
                "Discovery": "test",
                "ProbeUsable": True,
                "ProbeStatus": "usable headless browser executable",
            },
        ],
    )

    assert resolution["Requested"] == "auto"
    assert resolution["Resolved"] == "msedge-headless"
    assert resolution["SupportsInteractionAwareCapture"] is True
    assert len(resolution["Attempts"]) == 2
    assert "rejected because interaction-aware capture is required" in resolution[
        "Attempts"
    ][0]["validation"]


def test_issue_502_capture_records_complete_responsive_and_keyboard_state() -> None:
    script = CAPTURE_SCRIPT.read_text(encoding="utf-8")

    assert "function Invoke-Issue502BrowserCapture" in script
    assert "Issue502CapturePurpose = \"full-page\"" in script
    assert "Issue502KeyboardSelector" in script
    assert "Issue502DistinctFrom" in script
    assert "issue-502-responsive-measurements.json" in script
    assert "issue-502-focus-state-report.json" in script
    assert "keyboard screenshot differs from ordinary route" in script


def test_issue_502_empty_aggregate_diagnostics_are_valid_json_arrays(
    tmp_path: Path,
) -> None:
    writer = powershell_function("Write-JsonAggregateFile", "Test-ScreenshotToolCandidate")
    focus_path = tmp_path / "issue-502-focus-state-report.json"
    responsive_path = tmp_path / "issue-502-responsive-measurements.json"
    populated_path = tmp_path / "populated.json"
    ps_script = f"""
{writer}
$focus = {json.dumps(str(focus_path))}
$responsive = {json.dumps(str(responsive_path))}
$populated = {json.dumps(str(populated_path))}
Write-JsonAggregateFile -Path $focus -Rows @()
Write-JsonAggregateFile -Path $responsive -Rows @()
Write-JsonAggregateFile -Path $populated -Rows @(
  [pscustomobject]@{{ route = 'one' }},
  [pscustomobject]@{{ route = 'two' }}
)
[ordered]@{{
  Focus = Get-Content -LiteralPath $focus -Raw
  Responsive = Get-Content -LiteralPath $responsive -Raw
  Populated = Get-Content -LiteralPath $populated -Raw
  FocusLength = (Get-Item -LiteralPath $focus).Length
  ResponsiveLength = (Get-Item -LiteralPath $responsive).Length
}} | ConvertTo-Json
"""
    result = subprocess.run(
        [powershell(), "-NoProfile", "-Command", ps_script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, plain_output(result)
    diagnostics = json.loads(result.stdout)
    assert diagnostics["FocusLength"] > 0
    assert diagnostics["ResponsiveLength"] > 0
    assert json.loads(diagnostics["Focus"]) == []
    assert json.loads(diagnostics["Responsive"]) == []
    assert json.loads(diagnostics["Populated"]) == [
        {"route": "one"},
        {"route": "two"},
    ]


def test_browser_exit_zero_without_required_output_is_governed_failure(
    tmp_path: Path,
) -> None:
    output_failure = powershell_function(
        "Get-BrowserAutomationOutputFailure", "Write-JsonAggregateFile"
    )
    candidate_test = powershell_function(
        "Test-ScreenshotToolCandidate", "Resolve-ScreenshotTool"
    )
    route_screenshot = powershell_function("Invoke-RouteScreenshot", "Invoke-RoutePrint")
    png_dimensions = powershell_function("Get-PngDimensions", "Invoke-Issue502BrowserCapture")
    executable = tmp_path / "browser.exe"
    empty_png = tmp_path / "empty.png"
    valid_png = tmp_path / "valid.png"
    ps_script = f"""
{png_dimensions}
{output_failure}
{candidate_test}
{route_screenshot}
$TimeoutSeconds = 1
$ViewportWidth = 1
$ViewportHeight = 1
$executable = {json.dumps(str(executable))}
$emptyPng = {json.dumps(str(empty_png))}
$validPng = {json.dumps(str(valid_png))}
Set-Content -LiteralPath $executable -Value 'test' -NoNewline
New-Item -ItemType File -Path $emptyPng | Out-Null
$pngBytes = [byte[]](
  137,80,78,71,13,10,26,10,0,0,0,13,
  73,72,68,82,0,0,0,1,0,0,0,1
)
[System.IO.File]::WriteAllBytes($validPng, $pngBytes)
$script:ProbePaths = [System.Collections.ArrayList]::new()
$script:ProbeArguments = @()
$script:ProbeScenario = ''
function Invoke-NativeCaptureCommand {{
  param([string]$Command, [string[]]$Arguments, [int]$Timeout)
  $script:ProbeArguments = @($Arguments)
  $screenshotArgument = @(
    $Arguments | Where-Object {{ $_ -like '--screenshot=*' }} | Select-Object -First 1
  )
  $screenshotPath = $screenshotArgument[0].Substring('--screenshot='.Length)
  [void]$script:ProbePaths.Add([pscustomobject]@{{
    Screenshot = $screenshotPath
    Directory = Split-Path $screenshotPath -Parent
  }})
  switch ($script:ProbeScenario) {{
    'valid' {{
      [System.IO.File]::WriteAllBytes($screenshotPath, $pngBytes)
      return [pscustomobject]@{{ ExitCode = 0; Output = '' }}
    }}
    'empty' {{
      New-Item -ItemType File -Path $screenshotPath | Out-Null
      return [pscustomobject]@{{ ExitCode = 0; Output = '' }}
    }}
    'invalid' {{
      Set-Content -LiteralPath $screenshotPath -Value 'not-a-png' -NoNewline
      return [pscustomobject]@{{ ExitCode = 0; Output = '' }}
    }}
    'command-failure' {{ return [pscustomobject]@{{ ExitCode = 7; Output = 'synthetic failure' }} }}
    default {{ return [pscustomobject]@{{ ExitCode = 0; Output = '' }} }}
  }}
}}
$candidate = [pscustomobject]@{{ Command = $executable; Kind = 'edge'; Name = 'edge-test' }}
function Invoke-CandidateScenario {{
  param([string]$Scenario)
  $script:ProbeScenario = $Scenario
  $result = Test-ScreenshotToolCandidate -Candidate $candidate
  $probePath = @($script:ProbePaths | Select-Object -Last 1)[0]
  return [pscustomobject]@{{
    Usable = [bool]$result.Usable
    Status = [string]$result.Status
    Cleanup = -not (Test-Path -LiteralPath $probePath.Directory) `
      -and -not (Test-Path -LiteralPath $probePath.Screenshot)
  }}
}}
$candidateValid = Invoke-CandidateScenario -Scenario 'valid'
$candidateMissing = Invoke-CandidateScenario -Scenario 'missing'
$candidateEmpty = Invoke-CandidateScenario -Scenario 'empty'
$candidateInvalid = Invoke-CandidateScenario -Scenario 'invalid'
$candidateCommandFailure = Invoke-CandidateScenario -Scenario 'command-failure'
$missingScreenshot = Join-Path {json.dumps(str(tmp_path))} 'missing.png'
$domMissingParameters = @{{
  Operation = 'probe'; ExitCode = 0; RequiredOutput = 'DOM'
  BrowserExecutableCategory = 'edge'; TextOutput = ''; TextOutputExpected = $true
}}
$domValidParameters = @{{
  Operation = 'probe'; ExitCode = 0; RequiredOutput = 'DOM'
  BrowserExecutableCategory = 'edge'; TextOutput = '<html></html>'; TextOutputExpected = $true
}}
$missingScreenshotParameters = @{{
  Operation = 'screenshot'; ExitCode = 0; RequiredOutput = 'screenshot'
  BrowserExecutableCategory = 'edge'; OutputPath = $missingScreenshot; RequirePng = $true
}}
$emptyScreenshotParameters = @{{
  Operation = 'screenshot'; ExitCode = 0; RequiredOutput = 'screenshot'
  BrowserExecutableCategory = 'edge'; OutputPath = $emptyPng; RequirePng = $true
}}
$validScreenshotParameters = @{{
  Operation = 'screenshot'; ExitCode = 0; RequiredOutput = 'screenshot'
  BrowserExecutableCategory = 'edge'; OutputPath = $validPng; RequirePng = $true
}}
[ordered]@{{
  CandidateValid = $candidateValid
  CandidateMissing = $candidateMissing
  CandidateEmpty = $candidateEmpty
  CandidateInvalid = $candidateInvalid
  CandidateCommandFailure = $candidateCommandFailure
  CandidateArguments = @($script:ProbeArguments)
  MissingDom = Get-BrowserAutomationOutputFailure @domMissingParameters
  MissingScreenshot = Get-BrowserAutomationOutputFailure @missingScreenshotParameters
  EmptyScreenshot = Get-BrowserAutomationOutputFailure @emptyScreenshotParameters
  ValidDom = Get-BrowserAutomationOutputFailure @domValidParameters
  ValidScreenshot = Get-BrowserAutomationOutputFailure @validScreenshotParameters
}} | ConvertTo-Json
"""
    result = subprocess.run(
        [powershell(), "-NoProfile", "-Command", ps_script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, plain_output(result)
    failures = json.loads(result.stdout)
    assert failures["CandidateValid"]["Usable"] is True
    assert failures["CandidateValid"]["Status"] == "usable headless browser screenshot executable"
    assert failures["CandidateValid"]["Cleanup"] is True
    for key in ("CandidateMissing", "CandidateEmpty"):
        assert failures[key]["Usable"] is False
        assert failures[key]["Cleanup"] is True
        assert failures[key]["Status"].startswith(
            "BROWSER_AUTOMATION_NO_REQUIRED_OUTPUT:"
        )
    for key in ("CandidateInvalid", "CandidateCommandFailure"):
        assert failures[key]["Usable"] is False
        assert failures[key]["Cleanup"] is True
    assert failures["CandidateInvalid"]["Status"].startswith(
        "BROWSER_AUTOMATION_INVALID_REQUIRED_OUTPUT:"
    )
    assert failures["CandidateCommandFailure"]["Status"].startswith(
        "BROWSER_AUTOMATION_COMMAND_FAILED:"
    )
    assert "--screenshot=" in " ".join(failures["CandidateArguments"])
    assert "--user-data-dir=" not in " ".join(failures["CandidateArguments"])
    for key in ("MissingDom", "MissingScreenshot", "EmptyScreenshot"):
        assert failures[key].startswith("BROWSER_AUTOMATION_NO_REQUIRED_OUTPUT:")
        assert "exitCode=0" in failures[key]
    assert failures["ValidDom"] == ""
    assert failures["ValidScreenshot"] == ""


def test_issue_503_capture_proves_fragments_interactions_reflow_and_print() -> None:
    script = CAPTURE_SCRIPT.read_text(encoding="utf-8")

    assert "function Invoke-Issue503BrowserCapture" in script
    for scenario in (
        "issue-503-help-desktop",
        "issue-503-help-narrow",
        "issue-503-help-mobile",
        "issue-503-help-reflow",
        "issue-503-direct-get-started",
        "issue-503-direct-understand-information",
        "issue-503-direct-manage-review-work",
        "issue-503-direct-troubleshooting",
        "issue-503-keyboard-category",
        "issue-503-child-history",
        "issue-503-invalid-fragment",
        "issue-503-secondary-disclosure",
        "issue-503-glossary",
        "issue-503-print",
    ):
        assert scenario in script
    for behavior in (
        "Issue503ExpectedFragment",
        "Issue503Interaction",
        "history.back()",
        "history.forward()",
        "keyboard-operated secondary disclosure",
        "keyboard-operated collision-safe glossary",
        "browser-observed fragment focus and viewport destination",
        "issue-503-responsive-fragment-focus-measurements.json",
        "issue-503-print-validation.json",
        "PENDING_INDEPENDENT_VISUAL_REVIEW",
        "native browser zoom and assistive-technology verification were not performed",
    ):
        assert behavior in script
    assert '(?is)<details\\b(?:(?!</details>).)*</details>' in script
    assert '[regex]::Replace($Text, "\\s+", " ")' in script


def test_explicit_screenshot_tool_failure_does_not_silently_fallback() -> None:
    resolution = run_screenshot_tool_resolution(
        "playwright",
        require_interaction=True,
        candidates=[
            {
                "Name": "playwright",
                "Kind": "playwright",
                "Command": "playwright.cmd",
                "FullPage": True,
                "InteractionAware": False,
                "Discovery": "test",
                "ProbeUsable": False,
                "ProbeStatus": "Playwright browser validation failed: missing executable",
            },
            {
                "Name": "msedge-headless",
                "Kind": "edge",
                "Command": "msedge.exe",
                "FullPage": False,
                "InteractionAware": True,
                "Discovery": "test",
                "ProbeUsable": True,
                "ProbeStatus": "usable headless browser executable",
            },
        ],
    )

    assert resolution["Requested"] == "playwright"
    assert resolution["Resolved"] == "none"
    assert resolution["SupportsInteractionAwareCapture"] is False
    assert len(resolution["Attempts"]) == 1
    assert "missing executable" in resolution["ValidationStatus"]
    assert "Explicit screenshot tool 'playwright' is unusable" in resolution["Error"]


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
        "<html><body><h1>Find Facilities That May Need Closer Review</h1>"
        "<h2>Complaint Activity Over Time</h2>"
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
            "Find Facilities That May Need Closer Review Complaint Activity Over Time",
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

    assert failed_issue_417_checks(source_assertions) == {"issue417 source category basis"}
    assert failed_issue_417_checks(keyword_assertions) == {"issue417 keyword cue basis"}


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
        "PythonExecutable",
        "-WorkingDirectory $PWD",
        "-RedirectStandardOutput $launcherStdout",
        "-RedirectStandardError $launcherStderr",
        "launcher exited with code",
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
        assert manifest["acceptance"] == {
            "schemaVersion": "recordstracker.hosted-ui-acceptance.v1",
            "governanceIssue": "#648",
            "parentIssue": "#640",
            "stakeholderIssue": "#419",
            "featureIssues": [],
            "structural": "PENDING_VALIDATION",
            "functional": "PENDING_VALIDATION",
            "visual": "PENDING_INDEPENDENT_VISUAL_REVIEW",
            "ownerAcceptance": "PENDING_OWNER_DECISION",
            "overall": "NOT_ACCEPTED",
            "independentReviewArtifact": "reviews/independent-visual-review.json",
            "ownerDecisionArtifact": "reviews/owner-acceptance.json",
            "validator": "scripts/validate_hosted_ui_acceptance.py",
            "automationMayAccept": False,
        }
        independent_review = json.loads(
            (packet / "reviews" / "independent-visual-review.json").read_text(
                encoding="utf-8-sig"
            )
        )
        owner_acceptance = json.loads(
            (packet / "reviews" / "owner-acceptance.json").read_text(
                encoding="utf-8-sig"
            )
        )
        assert independent_review["decision"] == "PENDING"
        assert independent_review["actorType"] == "HUMAN_REQUIRED"
        assert owner_acceptance["decision"] == "PENDING"
        assert owner_acceptance["actorType"] == "HUMAN_REQUIRED"
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
        count_csv = (packet / "issue-415-count-summaries.csv").read_text(encoding="utf-8-sig")
        href_csv = (packet / "issue-415-href-inventory.csv").read_text(encoding="utf-8-sig")
        assertions_csv = (packet / "route-assertions.csv").read_text(encoding="utf-8-sig")

        assert (packet / "issue-415-count-summaries.csv").exists()
        assert (packet / "issue-415-href-inventory.csv").exists()
        assert manifest["issue415"]["enabled"] is True
        assert manifest["output"]["counts"]["issue415"] == 2
        assert len(manifest["routeList"]) == 5
        assert "/reviewer/records/substantiated?facility=107207198" in count_csv
        assert "sourceRecordKey,facilityId,complaintId,finding,date" in href_csv
        assert "issue415 count summary" in assertions_csv
        assert "True browser zoom is not controlled by this script" in json.dumps(manifest)
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
        count_csv = (packet / "issue-416-count-summaries.csv").read_text(encoding="utf-8-sig")
        assertions_csv = (packet / "route-assertions.csv").read_text(encoding="utf-8-sig")
        capture_command = (packet / "diagnostics" / "capture-command.txt").read_text(
            encoding="utf-8-sig"
        )

        assert (packet / "issue-416-count-summaries.csv").exists()
        assert manifest["issue416"]["enabled"] is True
        assert manifest["issue416"]["routeCount"] == 4
        assert manifest["output"]["counts"]["issue416"] == 1
        assert len(manifest["routeList"]) == 4
        assert "view=complaint-priority-compatibility&page_size=10" in count_csv
        assert "issue416 h1" in assertions_csv
        assert "-Issue416" in capture_command
        assert "Focused issue #416 facility prioritization evidence" in manifest["evidencePurpose"]
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
        count_csv = (packet / "issue-417-count-summaries.csv").read_text(encoding="utf-8-sig")
        assertions_csv = (packet / "route-assertions.csv").read_text(encoding="utf-8-sig")
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
        assert (
            "Focused issue #417 serious-topic complaint worklist evidence"
            in manifest["evidencePurpose"]
        )
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
        count_csv = (packet / "issue-418-count-summaries.csv").read_text(encoding="utf-8-sig")
        assertions_csv = (packet / "route-assertions.csv").read_text(encoding="utf-8-sig")
        capture_command = (packet / "diagnostics" / "capture-command.txt").read_text(
            encoding="utf-8-sig"
        )

        assert (packet / "issue-418-count-summaries.csv").exists()
        assert manifest["issue418"]["enabled"] is True
        assert manifest["issue418"]["routeCount"] == 7
        assert manifest["output"]["counts"]["issue418"] == 1
        assert len(manifest["routeList"]) == 7
        assert "view=complaint-activity-over-time&facility=157806098" in count_csv
        assert "issue418 h1" in assertions_csv
        assert "-Issue418" in capture_command
        assert "Focused issue #418 complaint trend evidence" in manifest["evidencePurpose"]
    finally:
        shutil.rmtree(output_dir, ignore_errors=True)


def test_capture_script_issue_419_mode_writes_governed_review_artifacts() -> None:
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
                "-Issue419",
                "-AllowUnavailable",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        output = plain_output(result)

        assert result.returncode == 0, output
        packets = sorted(output_dir.glob("*-fixture-issue-419"))
        assert packets, output
        packet = packets[-1]
        manifest = json.loads((packet / "manifest.json").read_text(encoding="utf-8-sig"))
        comparison_csv = (packet / "issue-419-approved-versus-rendered.csv").read_text(
            encoding="utf-8-sig"
        )
        gates_csv = (packet / "issue-419-ui-gates.csv").read_text(encoding="utf-8-sig")
        capture_command = (packet / "diagnostics" / "capture-command.txt").read_text(
            encoding="utf-8-sig"
        )

        assert manifest["issue419"]["enabled"] is True
        assert manifest["issue419"]["routeCount"] == 17
        assert manifest["output"]["counts"]["issue419"] == 2
        assert len(manifest["routeList"]) == 17
        assert manifest["issue419"]["controlledVarianceAuthority"] == (
            "Issue #501 repository-readable controlled variance"
        )
        assert manifest["issue419"]["visualAcceptance"] == (
            "PENDING_INDEPENDENT_VISUAL_REVIEW"
        )
        assert "IA-419-01" in comparison_csv
        assert "IA-419-09" in comparison_csv
        for gate_number in range(1, 10):
            assert f"RT-UI-GATE-{gate_number:03d}" in gates_csv
        assert "PENDING_INDEPENDENT_VISUAL_REVIEW" in gates_csv
        assert "-Issue419" in capture_command
        assert "Focused issue #419 Compare Facilities evidence" in manifest["evidencePurpose"]
    finally:
        shutil.rmtree(output_dir, ignore_errors=True)


def test_capture_script_issue_498_mode_writes_named_local_fixture_scenarios() -> None:
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
                "-Issue498",
                "-AllowUnavailable",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        output = plain_output(result)

        assert result.returncode == 0, output
        packets = sorted(output_dir.glob("*-fixture-issue-498"))
        assert packets, output
        packet = packets[-1]
        zip_packet = packet.with_suffix(".zip")
        manifest = json.loads((packet / "manifest.json").read_text(encoding="utf-8-sig"))
        route_status_header = (packet / "route-status.csv").read_text(
            encoding="utf-8-sig"
        ).splitlines()[0]
        capture_command = (packet / "diagnostics" / "capture-command.txt").read_text(
            encoding="utf-8-sig"
        )

        assert manifest["issue498"]["enabled"] is True
        for standard_file in (
            "manifest.json",
            "route-status.csv",
            "route-assertions.csv",
            "route-text-markers.txt",
            "README.txt",
        ):
            assert (packet / standard_file).exists()
        for standard_directory in (
            "html",
            "text",
            "accessibility",
            "diagnostics",
            "screenshots",
            "print",
        ):
            assert (packet / standard_directory).is_dir()
        assert zip_packet.exists()
        assert manifest["issue498"]["routeCount"] == 11
        assert manifest["output"]["counts"]["issue498"] == 11
        assert len(manifest["routeList"]) == 11
        assert "supplementalScreenshotPath" in route_status_header
        assert all(route["supplementalScreenshotPath"] == "" for route in manifest["routes"])
        assert manifest["issue498"]["scenarios"] == [
            "rt-src-002-supported-closed",
            "rt-src-002-supported-open",
            "rt-src-002-supported-open-narrow-desktop",
            "rt-src-002-supported-open-mobile-compact",
            "rt-src-002-supported-open-200-percent-reflow-approximation",
            "rt-src-002-keyboard-focus",
            "rt-src-002-document-only",
            "rt-src-002-field-partial",
            "rt-src-002-source-unavailable",
            "rt-src-002-print",
            "rt-src-002-focus-return",
        ]
        assert manifest["screenshotTool"] == {
            "requested": "auto",
            "resolved": "none",
            "validationStatus": "screenshots not requested",
            "executable": "",
            "supportsInteractionAwareCapture": False,
            "attempts": [],
        }
        assert "exact true browser zoom remains manual visual evidence" in manifest[
            "issue498"
        ]["zoomLimitation"]
        assert "-Issue498" in capture_command
        assert "-ScreenshotToolPreference auto" in capture_command
        assert "Focused RT-SRC-002 local fixture evidence" in manifest["evidencePurpose"]
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
            'Remove-Item -LiteralPath ("Env:{0}" -f $v) '
            "-ErrorAction SilentlyContinue "
            "}; " + capture_call + post_env_json
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


def test_capture_rejects_prohibited_published_hostname() -> None:
    stop_capture_fail = powershell_function("Stop-CaptureFail", "Test-AllowedBaseUrl")
    allowed_base_url = powershell_function("Test-AllowedBaseUrl", "Assert-OutputDir")
    ps_script = (
        stop_capture_fail
        + "\n"
        + allowed_base_url
        + "\ntry { Test-AllowedBaseUrl -Value 'https://test.recordtracker.xyz' } "
        + "catch { $_.Exception.Message }\n"
    )
    result = subprocess.run(
        [powershell(), "-NoProfile", "-Command", ps_script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, plain_output(result)
    assert "Refusing non-local URL 'test.recordtracker.xyz'" in plain_output(result)


def test_issue_642_operated_capture_uses_native_input_and_records_state_metadata() -> None:
    script = CAPTURE_SCRIPT.read_text(encoding="utf-8")

    for expected in (
        "function Invoke-CdpClickSelector",
        "Input.dispatchMouseEvent",
        "function Invoke-CdpReplaceFocusedText",
        "Input.insertText",
        "function Invoke-Issue642OperatedInteractionCapture",
        "function Assert-Issue642MultiSelectVisualReadiness",
        "function Assert-Issue642TypeaheadVisualReadiness",
        "function Invoke-Issue642FocusEvidenceCapture",
        "function Test-Issue642FunctionalGate",
        "interaction_mode:'operated'",
        "issue642-typeahead-open",
        "issue642-typeahead-no-match",
        "issue642-typeahead-selected",
        "issue642-typeahead-escape",
        "issue642-multiselect-two-selected",
        "issue642-multiselect-chip-removed",
        "issue642-multiselect-all-restored",
        "issue642-multiselect-escape",
        "issue642-pagination-previous",
        "issue642-pagination-filter-change",
        "issue642-pagination-continuation-removed",
        "issue642-pagination-first-page-reset",
        "issue642-facility-overview-return",
        "issue642-facility-overview-browser-back",
        "issue642-complaint-detail-return",
        "issue642-complaint-detail-browser-back",
        "issue-642-operated-interactions",
        "issue-642-trends-populated",
        "issue-642-trends-intentional-empty",
        "facility=642900001&facility_type=430&finding=Substantiated",
        "start_date=2022-04-01&end_date=2022-04-30",
        "issue642 populated trends reconciliation",
        "issue642 intentional empty trends truthfulness",
        "No records meet the active eligibility filters",
        "wait suggestion response",
        "verify repeated query and no continuation",
        "mouseMoved",
        "Required operated control failed hit testing",
        "coordinateFormula",
        (
            "no visual-viewport scale, device scale, screenshot-pixel, "
            "or browser-window conversion is applied"
        ),
        "issue-642-native-200-operating.json",
        "function Invoke-CdpFocusByTabTraversal",
        "focus traversal did not reach the required rendered target",
        "LastFocusTraversal",
        "focusableCount + 1",
        "focus_traversal",
        "requested_zoom",
        "observed_zoom",
        "native-200% keyboard navigation did not reach the rendered multi-select trigger",
        "Invoke-CdpSpaceActivation -Session $Session",
        "trigger.getAttribute('aria-controls')",
        "style.display!=='none'",
        "style.visibility!=='hidden'",
        "labelRect.left>=panelRect.left-2&&labelRect.right<=panelRect.right+2",
        "labelRect.left>boxRect.right&&gap>=0&&gap<=16",
        "meaningfulWidth=labelRect.width>=Math.min(64,rowRect.width*0.35)",
        "label.scrollWidth>label.clientWidth+2",
        "panel_background:panelStyle.backgroundColor",
        "long_label_ok:longLabelOk",
        "longRow=rows.find((row)=>row.text&&row.text.includes('Source code 430'))",
        "issue-642-complaint-patterns-multiselect-long-label",
        "issue-642-multiselect-layout.json",
        "input.parentElement===popup.parentElement",
        "input.nextElementSibling===popup",
        "input_rect:{left:inputRect.left,top:inputRect.top,right:inputRect.right,bottom:inputRect.bottom",
        "popup_rect:{left:popupRect.left,top:popupRect.top,right:popupRect.right,bottom:popupRect.bottom",
        "visible listbox layout",
        "issue-642-typeahead-popup-layout.json",
        "issue-642-focus-evidence.json",
        "focus-local-navigation",
        "focus-typeahead-input",
        "focus-typeahead-option",
        "focus-multiselect-trigger",
        "focus-multiselect-checkbox",
        "focus-apply",
        "focus-clear",
        "focus-chip-removal",
        "focus-previous",
        "focus-next",
        "function Write-Issue642PacketDiagnostics",
        "issue-642-screenshot-states.json",
        "issue-642-console-network-summary.json",
        "screenshotStateArtifact",
        "consoleNetworkSummaryArtifact",
        "consoleWarnings",
        "issue642 unavailable heading and selected public Facility ID",
        "issue642 unavailable omits unverified counts and observations",
        "issue642 unavailable is not filtered-empty and has ordinary recovery",
        "filterControlDefinitions",
        "Relevant date",
        "filter-control--native",
        "issue-642-licensing-populated",
        "issue-642-licensing-filtered-empty",
        "issue-642-licensing-source-unavailable",
        "issue-642-licensing-typeahead-id",
        "issue-642-licensing-typeahead-name",
        "issue-642-licensing-typeahead-no-match",
        "issue-642-complaint-patterns-1280",
        "data-result-state=\"source-unavailable\"",
        "native_appearance",
        "cue_contrast",
        "trigger_control",
        "focus_visible",
        "inside_trigger",
    ):
        assert expected in script


def test_issue_642_operated_pagination_only_activates_an_enabled_next_control() -> None:
    script = CAPTURE_SCRIPT.read_text(encoding="utf-8")
    assert "for ($pageNumber = 2; $pageNumber -le 4; $pageNumber++)" not in script
    loop_start = script.index("$pageNumber = 2")
    loop_end = script.index("$page = Get-Issue642PaginationPage", loop_start)
    loop = script[loop_start:loop_end]
    assert "while ($true)" in loop
    assert "if (-not $currentPage.nextEnabled)" in loop
    click_call = (
        "Invoke-CdpClickSelector -Session $Session -Selector "
        "\"a.facility-pagination__control[aria-label^='Next facilities']\""
    )
    assert loop.index("$currentPage = Get-Issue642PaginationPage") < loop.index(
        click_call
    )


def test_issue_644_mode_composes_the_existing_compare_facilities_capture_contract() -> None:
    script = CAPTURE_SCRIPT.read_text(encoding="utf-8")
    wrapper = WRAPPER_SCRIPT.read_text(encoding="utf-8")

    for expected in (
        "[switch]$Issue644",
        "issue-644-local",
        "elseif ($Issue644) { $issue644Routes }",
        "$issue644Routes = @($issue642Routes + $issue643Routes + $issue644SurfaceRoute)",
        "issue-644-surface-1189",
        "StartsWith('issue-643-')",
        "Issue642 -or $Issue643 -or $Issue644",
        "#644 is deliberately a composition of the proven #642 contract",
        "issue642-pagination-middle-page",
        "issue642-pagination-last-page",
        "page_size = $pageSize",
        "unique_count = $uniqueIdentities.Count",
        "innerWidth",
        "visualViewportScale",
        "devicePixelRatio",
    ):
        assert expected in script
    assert "if ($Issue642 -or $Issue644) { $launcherArguments += '-Issue642Evidence' }" in wrapper
    assert "if ($Issue644) { $captureArguments.Issue644 = $true }" in wrapper


def test_issue_642_pagination_reconciliation_uses_rendered_page_size_and_fails_closed(
    tmp_path: Path,
) -> None:
    helper = powershell_function(
        "Test-Issue642PaginationReconciliation", "Invoke-Issue642OperatedInteractionCapture"
    )

    def pages(total: int, page_size: int) -> list[dict[str, object]]:
        output: list[dict[str, object]] = []
        first = 1
        page_number = 0
        while first <= total:
            page_number += 1
            last = min(first + page_size - 1, total)
            output.append(
                {
                    "first": first,
                    "last": last,
                    "total": total,
                    "identities": [
                        f"facility-intelligence-result-{index}" for index in range(first, last + 1)
                    ],
                    "previousEnabled": page_number > 1,
                    "nextEnabled": last < total,
                    "url": "http://127.0.0.1:8010/ccld/facilities/intelligence?facility_type=430&facility_type=733&start_date=1900-01-01",
                }
            )
            first = last + 1
        return output

    valid_53 = pages(53, 25)
    valid_filtered_51 = pages(51, 25)
    valid_one_page = pages(7, 25)
    cases = {
        "valid_53": valid_53,
        "valid_filtered_51": valid_filtered_51,
        "valid_one_page": valid_one_page,
        "wrong_first_count": [
            {**valid_53[0], "identities": valid_53[0]["identities"][:-1]}
        ] + valid_53[1:],
        "wrong_middle_count": [
            valid_53[0],
            {**valid_53[1], "identities": valid_53[1]["identities"][:-1]},
        ] + valid_53[2:],
        "wrong_final_remainder": valid_53[:-1]
        + [{**valid_53[-1], "identities": valid_53[-1]["identities"] + ["extra"]}],
        "duplicate": [
            valid_53[0],
            {
                **valid_53[1],
                "identities": [valid_53[0]["identities"][0]]
                + valid_53[1]["identities"][1:],
            },
        ] + valid_53[2:],
        "skipped": [valid_53[0], {**valid_53[1], "first": 16}] + valid_53[2:],
        "zero_page_size": [{**valid_53[0], "last": 0, "identities": []}] + valid_53[1:],
        "control_mismatch": [{**valid_53[0], "previousEnabled": True}] + valid_53[1:],
        "final_missing_previous": valid_53[:-1] + [{**valid_53[-1], "previousEnabled": False}],
        "one_page_has_previous": [{**valid_one_page[0], "previousEnabled": True}],
        "context_loss": [
            valid_53[0],
            {
                **valid_53[1],
                "url": "http://127.0.0.1:8010/ccld/facilities/intelligence?facility_type=430",
            },
        ] + valid_53[2:],
    }
    cases_json = json.dumps(cases).replace("'", "''")
    ps_script = f"""
{helper}
$cases = ConvertFrom-Json -InputObject '{cases_json}'
$results = [ordered]@{{}}
foreach ($property in $cases.PSObject.Properties) {{
    try {{
        $value = Test-Issue642PaginationReconciliation -Pages @($property.Value)
        $results[$property.Name] = [ordered]@{{
            pass = $true
            page_size = $value.page_size
            total = $value.total
            page_counts = @($value.page_counts)
            unique_count = $value.unique_count
            duplicate_count = $value.duplicate_count
            missing_count = $value.missing_count
        }}
    }} catch {{
        $results[$property.Name] = [ordered]@{{ pass = $false; message = $_.Exception.Message }}
    }}
}}
$results | ConvertTo-Json -Depth 8 -Compress
"""
    script_path = tmp_path / "issue642-pagination-reconciliation.ps1"
    script_path.write_text(ps_script, encoding="utf-8")
    result = subprocess.run(
        [powershell(), "-NoProfile", "-File", str(script_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, plain_output(result)
    observed = json.loads(plain_output(result).strip().splitlines()[-1])
    assert observed["valid_53"] == {
        "pass": True,
        "page_size": 25,
        "total": 53,
        "page_counts": [25, 25, 3],
        "unique_count": 53,
        "duplicate_count": 0,
        "missing_count": 0,
    }
    assert observed["valid_filtered_51"] == {
        "pass": True,
        "page_size": 25,
        "total": 51,
        "page_counts": [25, 25, 1],
        "unique_count": 51,
        "duplicate_count": 0,
        "missing_count": 0,
    }
    assert observed["valid_one_page"] == {
        "pass": True,
        "page_size": 7,
        "total": 7,
        "page_counts": [7],
        "unique_count": 7,
        "duplicate_count": 0,
        "missing_count": 0,
    }
    for name in cases:
        if name not in {"valid_53", "valid_filtered_51", "valid_one_page"}:
            assert observed[name]["pass"] is False, name
    assert "25" not in helper


def test_issue_642_canonical_inventory_cardinality_is_distinct_from_filtered_reconciliation(
) -> None:
    helper = powershell_function(
        "Test-Issue642CanonicalInventory", "Test-Issue642PaginationReconciliation"
    )
    canonical = {
        "first": 1,
        "last": 25,
        "total": 53,
        "identities": [f"facility-intelligence-result-{index}" for index in range(1, 26)],
        "previousEnabled": False,
        "nextEnabled": True,
        "url": "http://127.0.0.1:8010/ccld/facilities/intelligence",
    }
    cases = {
        "canonical": canonical,
        "canonical_total_dropped": {**canonical, "total": 51},
        "canonical_wrong_first_range": {
            **canonical,
            "last": 24,
            "identities": canonical["identities"][:-1],
        },
        "canonical_missing_next": {**canonical, "nextEnabled": False},
        "filtered_url": {**canonical, "url": canonical["url"] + "?facility_type=430"},
    }
    cases_json = json.dumps(cases).replace("'", "''")
    ps_script = f"""
{helper}
$cases = ConvertFrom-Json -InputObject '{cases_json}'
$results = [ordered]@{{}}
foreach ($property in $cases.PSObject.Properties) {{
    try {{
        $value = Test-Issue642CanonicalInventory -Page $property.Value
        $results[$property.Name] = [ordered]@{{ pass=$true; value=$value }}
    }}
    catch {{ $results[$property.Name] = [ordered]@{{ pass=$false; message=$_.Exception.Message }} }}
}}
$results | ConvertTo-Json -Depth 8 -Compress
"""
    result = subprocess.run(
        [powershell(), "-NoProfile", "-Command", ps_script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, plain_output(result)
    observed = json.loads(plain_output(result).strip().splitlines()[-1])
    assert observed["canonical"]["pass"] is True
    assert observed["canonical"]["value"]["canonicalInventoryTotal"] == 53
    for name in (
        "canonical_total_dropped",
        "canonical_wrong_first_range",
        "canonical_missing_next",
        "filtered_url",
    ):
        assert observed[name]["pass"] is False, name


def test_issue_644_automated_visual_prerequisites_fail_closed_before_packet_finalization(
    tmp_path: Path,
) -> None:
    stop_capture_fail = powershell_function("Stop-CaptureFail", "Test-AllowedBaseUrl")
    prerequisites = powershell_function(
        "Test-Issue644AutomatedVisualPrerequisites", "Write-Issue655PacketDiagnostics"
    )
    packet = tmp_path / "packet"
    diagnostics = packet / "diagnostics"
    print_dir = packet / "print"
    print_pages = packet / "print-pages"
    diagnostics.mkdir(parents=True)
    print_dir.mkdir()
    print_pages.mkdir()
    (print_dir / "compare.pdf").write_bytes(b"pdf")

    route_states = {
        "issue-643-populated-desktop": (1440, 1200, 1200 * 12),
        "issue-644-surface-1189": (1189, 671, 671 * 16),
        "issue-643-populated-500": (500, 900, 900 * 16),
        "issue-643-populated-390": (390, 844, 844 * 24),
        "issue-643-populated-zoom-200": (1280, 900, 900 * 24),
    }
    route_rows = []
    for route_name, (width, height, document_height) in route_states.items():
        state_path = diagnostics / f"{route_name}-browser-state.json"
        state_path.write_text(
            json.dumps(
                {
                    "viewport": {
                        "innerWidth": width,
                        "innerHeight": height,
                        "visualViewportScale": 1,
                        "devicePixelRatio": 1,
                    },
                    "document": {"scrollHeight": document_height},
                }
            ),
            encoding="utf-8",
        )
        route_rows.append(
            {
                "name": route_name,
                "browserStatePath": f"diagnostics/{state_path.name}",
            }
        )

    packet_literal = str(packet).replace("'", "''")
    route_rows_literal = json.dumps(route_rows).replace("'", "''")
    ps_script = f"""
{stop_capture_fail}
{prerequisites}
$packet = '{packet_literal}'
$routes = @((ConvertFrom-Json -InputObject '{route_rows_literal}'))
function Set-PrintValidation {{
    param([int]$PageCount)
    $pages = @()
    Get-ChildItem -LiteralPath (Join-Path $packet 'print-pages') -File | Remove-Item -Force
    for ($index = 1; $index -le $PageCount; $index++) {{
        $name = 'page-{{0:D3}}.png' -f $index
        Set-Content -LiteralPath (Join-Path $packet "print-pages/$name") -Value 'png' -NoNewline
        $pages += [ordered]@{{ file = $name }}
    }}
    $validation = [ordered]@{{
        pdf = 'compare.pdf'
        pageCount = $PageCount
        pages = @($pages)
    }}
    $validation | ConvertTo-Json -Depth 5 |
        Set-Content -LiteralPath (Join-Path $packet 'issue-420-print-validation.json')
}}
function Invoke-Case {{
    param([string]$Name, [scriptblock]$Action)
    try {{ & $Action; return 'PASS' }} catch {{ return $_.Exception.Message }}
}}
function Invoke-Prerequisites {{
    param([object[]]$RouteResults, [object]$Measurement = $null)
    $parameters = @{{
        PacketDirectory = $packet
        RouteResults = $RouteResults
    }}
    if ($null -ne $Measurement) {{
        $parameters.ManifestSurfaceMeasurement = $Measurement
    }}
    Test-Issue644AutomatedVisualPrerequisites @parameters | Out-Null
}}
Set-PrintValidation -PageCount 2
$valid = Test-Issue644AutomatedVisualPrerequisites -PacketDirectory $packet -RouteResults $routes
$printTwenty = Invoke-Case 'print-twenty' {{
    Set-PrintValidation -PageCount 20
    Invoke-Prerequisites -RouteResults $routes
}}
$missingPrint = Invoke-Case 'missing-print' {{
    Remove-Item -LiteralPath (Join-Path $packet 'issue-420-print-validation.json') -Force
    Invoke-Prerequisites -RouteResults $routes
}}
Set-PrintValidation -PageCount 2
$missingDensity = Invoke-Case 'missing-density' {{
    $withoutMobile = @($routes | Where-Object {{ $_.name -ne 'issue-643-populated-390' }})
    Invoke-Prerequisites -RouteResults $withoutMobile
}}
$desktop = Join-Path $packet 'diagnostics/issue-643-populated-desktop-browser-state.json'
$originalDesktop = Get-Content -LiteralPath $desktop -Raw
$state = $originalDesktop | ConvertFrom-Json
    $state.document.scrollHeight = 17057
$state | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $desktop
$densityExcess = Invoke-Case 'density-excess' {{
    Invoke-Prerequisites -RouteResults $routes
}}
Set-Content -LiteralPath $desktop -Value $originalDesktop
$surfaceConflict = Invoke-Case 'surface-conflict' {{
    $measurement = [pscustomobject]@{{
        innerWidth = 1189
        innerHeight = 671
        visualViewportScale = 1
        devicePixelRatio = 1.9250000715
    }}
    Invoke-Prerequisites -RouteResults $routes -Measurement $measurement
}}
[ordered]@{{
  ValidPrint = $valid.print.result
  ValidDensityCount = @($valid.densityResults).Count
  ValidSurfaceDpr = $valid.surfaceMeasurement.devicePixelRatio
  DensityArtifact = Test-Path -LiteralPath (Join-Path $packet $valid.densityArtifact)
  PrintTwenty = $printTwenty
  MissingPrint = $missingPrint
  MissingDensity = $missingDensity
  DensityExcess = $densityExcess
  SurfaceConflict = $surfaceConflict
  FileIndexExists = Test-Path -LiteralPath (Join-Path $packet 'file-index.json')
      ZipExists = Test-Path -LiteralPath ($packet + '.zip')
}} | ConvertTo-Json -Compress
"""
    result = subprocess.run(
        [powershell(), "-NoProfile", "-Command", ps_script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, plain_output(result)
    outcome = json.loads(result.stdout)
    assert outcome["ValidPrint"] == "PASS"
    assert outcome["ValidDensityCount"] == 5
    assert outcome["ValidSurfaceDpr"] == 1
    assert outcome["DensityArtifact"] is True
    assert "observed page count=20" in outcome["PrintTwenty"]
    assert "print validation is missing" in outcome["MissingPrint"]
    assert "mandatory MOBILE density result is missing" in outcome["MissingDensity"]
    assert "density ratio=" in outcome["DensityExcess"]
    assert "manifest Surface metadata 'devicePixelRatio' conflicts" in outcome["SurfaceConflict"]
    assert outcome["FileIndexExists"] is False
    assert outcome["ZipExists"] is False


def test_issue_655_mode_declares_dedicated_routes_operations_and_packet_artifacts() -> None:
    script = CAPTURE_SCRIPT.read_text(encoding="utf-8")
    required = (
        "function Invoke-Issue655BrowserCapture",
        "function Test-Issue655RouteAssertions",
        "function Write-Issue655PacketDiagnostics",
        "issue-655-first-recommendation",
        "issue-655-middle-recommendation",
        "issue-655-last-recommendation",
        "issue-655-one-item-sequence",
        "issue-655-empty-sequence",
        "issue-655-malformed-state",
        "issue-655-stale-state-recovery",
        "issue-655-pointer-next-first-middle",
        "issue-655-keyboard-next-middle-last",
        "a.review-next-control[rel=next]",
        "a.review-next-control[rel=prev]",
        "issue-655-browser-back",
        "issue-655-browser-forward",
        "Invoke-CdpBrowserForward",
        "issue-655-interaction-index.json",
        "issue-655-geometry.json",
        "issue-655-focus-live-region.json",
        "issue-655-screenshot-states.json",
        "issue-655-console-network-summary.json",
        "issue = '655'",
        "Local fixture evidence only",
    )
    for expected in required:
        assert expected in script
    issue655_block = script[script.index("$issue655Routes"):script.index("$routesToCapture")]
    assert "issue-643" not in issue655_block


def test_issue_655_static_scenarios_use_server_supported_state_and_fail_closed_semantics() -> None:
    script = CAPTURE_SCRIPT.read_text(encoding="utf-8")
    routes = script[script.index("$issue655Routes"):script.index("$routesToCapture")]
    assert "issue-655-middle-recommendation" in routes
    assert "?recommendation=" in routes
    assert "issue-655-one-item-sequence" in routes
    assert "?facility_type=733" in routes
    assert "issue-655-empty-sequence" in routes
    assert "?start_date=2030-01-01" in routes
    assert "facility=430000001" not in routes
    assert "facility=000000000" not in routes
    gate_start = script.index("function Test-Issue655StaticScenarioEvidence")
    gate_end = script.index("function Write-Issue642PacketDiagnostics", gate_start)
    gate = script[gate_start:gate_end]
    for required in (
        "positionNumber",
        "previousAvailable",
        "nextAvailable",
        "inventoryCount",
        "emptyStateText",
        "middle scenario is not a rendered deterministic middle recommendation",
        "one-item scenario is not exactly one rendered recommendation",
        "empty scenario is not a governed empty recommendation and inventory state",
        "middle, one-item, and empty screenshots must be distinct",
    ):
        assert required in gate
    assert "complaintDefinition?.nextElementSibling?.textContent.trim()" in script
    assert '.intelligence-message[aria-labelledby="facility-intelligence-empty-heading"]' in script
    assert "emptyStateText:emptyState?.innerText.trim()||''" in script
    assert "Test-Issue655StaticScenarioEvidence -PacketDirectory" in script


def test_issue_655_proof_urls_are_absolute_and_keep_query_and_fragment_boundaries() -> None:
    wrapper = WRAPPER_SCRIPT.read_text(encoding="utf-8")
    assert "function New-Issue655ScenarioUri" in wrapper
    assert "[System.UriBuilder]" in wrapper
    cursor = "opaque-cursor"
    scenarios = {
        "middle": f"http://127.0.0.1:20000/ccld/facilities/intelligence?recommendation={cursor}#review-next-region",
        "one-item": "http://127.0.0.1:20000/ccld/facilities/intelligence?facility_type=733",
        "empty": "http://127.0.0.1:20000/ccld/facilities/intelligence?start_date=2030-01-01",
    }
    for name, value in scenarios.items():
        parsed = urlsplit(value)
        assert parsed.scheme == "http", name
        assert parsed.netloc == "127.0.0.1:20000", name
        assert parsed.path == "/ccld/facilities/intelligence", name
    assert parse_qs(urlsplit(scenarios["middle"]).query)["recommendation"] == [cursor]
    assert urlsplit(scenarios["middle"]).fragment == "review-next-region"
    assert parse_qs(urlsplit(scenarios["one-item"]).query)["facility_type"] == ["733"]
    assert parse_qs(urlsplit(scenarios["empty"]).query)["start_date"] == ["2030-01-01"]


def test_issue_655_environment_summary_omits_legacy_issue_flags() -> None:
    script = CAPTURE_SCRIPT.read_text(encoding="utf-8")
    start = script.index("$environmentSummary = if ($Issue655)")
    issue655_summary = script[start:script.index(") } else {", start)]
    assert "issue=655" in issue655_summary
    assert "issue642FocusedCapture" not in issue655_summary
    assert "issue643FocusedCapture" not in issue655_summary


def test_issue_655_packaging_gate_requires_independent_operated_inventory() -> None:
    script = CAPTURE_SCRIPT.read_text(encoding="utf-8")
    required_ids = (
        "issue-655-pointer-next-first-middle",
        "issue-655-keyboard-next-middle-last",
        "issue-655-keyboard-previous-last-middle",
        "issue-655-pointer-previous-middle-first",
        "issue-655-browser-back",
        "issue-655-browser-forward",
        "issue-655-no-javascript-fallback",
        "issue-655-direct-valid-url",
        "issue-655-facility-overview-return",
        "issue-655-complaint-detail-return",
        "issue-655-concurrency-stale-response",
        "issue-655-enhanced-request-failure",
        "issue-655-reduced-motion",
    )
    gate_start = script.index("function Test-Issue655AcceptancePacket")
    gate_end = script.index("function Invoke-CdpBrowserForward", gate_start)
    gate = script[gate_start:gate_end]
    inventory_start = script.index("function Get-Issue655RequiredInteractionIds")
    inventory_end = script.index("function Test-Issue655AcceptancePacket", inventory_start)
    inventory = script[inventory_start:inventory_end]
    for interaction_id in required_ids:
        assert interaction_id in inventory
    assert "$id-browser-state.json" in gate
    assert "required interaction '$id' is missing or duplicated" in gate
    assert "Test-Issue655AcceptancePacket -PacketDirectory" in script
    assert "Compress-Archive" in script
    gate_call = script.index("Test-Issue655AcceptancePacket -PacketDirectory")
    archive_call = script.index("Compress-Archive")
    assert gate_call < archive_call


def test_issue_655_hygiene_gate_rejects_legacy_artifacts_and_warnings() -> None:
    script = CAPTURE_SCRIPT.read_text(encoding="utf-8")
    gate_start = script.index("function Test-Issue655AcceptancePacket")
    gate_end = script.index("function Invoke-CdpBrowserForward", gate_start)
    gate = script[gate_start:gate_end]
    assert "05-reviewer-complaint-exports.png" in gate
    assert "unrelated WARN assertion" in gate
    assert "-not $Issue655" in script
    assert "issue-655-concurrency-stale-response.json" in script
    assert "issue-655-enhanced-request-failure.json" in script
    assert "issue-655-reduced-motion.json" in script


def test_issue_655_detail_workflows_target_the_bounded_region_actions() -> None:
    script = CAPTURE_SCRIPT.read_text(encoding="utf-8")
    for helper in (
        "function Get-Issue655CompactRecommendationState",
        "function Resolve-Issue655CompactAction",
        "function Invoke-Issue655ResolvedAction",
        "function Wait-Issue655ExactDestination",
    ):
        assert helper in script
    assert "document.querySelectorAll('#review-next-region')" in script
    assert "region.querySelector('.facility-card-actions')" in script
    assert "target.isConnected" in script
    assert "visible||!focusable" in script
    assert "location.pathname===expected.pathname" in script
    assert "location.search===expected.search" in script
    assert "location.hash===expected.hash" in script
    assert "issue-655-facility-overview-return" in script
    assert "issue-655-complaint-detail-return" in script
    assert "facilityReturnTargetExpression" in script
    assert "complaintReturnTargetExpression" in script
    assert "document.querySelector('.facility-overview-summary')" in script
    assert "document.querySelector('.reviewer-detail-context')" in script
    assert "container.querySelectorAll('a[href]')" in script
    assert "Issue #655 Facility Overview return target missing." in script
    assert "Issue #655 Facility Overview return target ambiguous; count=" in script
    assert "Issue #655 Facility Overview return context mismatch:" in script
    assert "Issue #655 complaint-detail return target missing." in script
    assert "document.querySelectorAll('a[href]')).filter" not in script


def test_issue_655_detail_return_cursor_comparison_uses_active_action_urls() -> None:
    script = CAPTURE_SCRIPT.read_text(encoding="utf-8")
    for expected in (
        "Resolve-Issue655CompactAction -Session $Session -Kind 'facility-overview'",
        "Resolve-Issue655CompactAction -Session $Session -Kind 'complaint-detail'",
        "Invoke-Issue655ResolvedAction -Session $Session -Kind 'facility-overview'",
        "Invoke-Issue655ResolvedAction -Session $Session -Kind 'complaint-detail'",
        "Wait-Issue655ExactDestination -Session $Session -InteractionId "
        "'issue-655-facility-overview'",
        "Wait-Issue655ExactDestination -Session $Session -InteractionId "
        "'issue-655-complaint-detail'",
        "const detail = new URL($($facilityBefore.actionUrl | ConvertTo-Json -Compress), "
        "document.baseURI);",
        "const detail = new URL($($complaintBefore.contextUrl | ConvertTo-Json -Compress), "
        "document.baseURI);",
        "const expectedRaw = raw(detail, 'recommendation');",
        "const actualRaw = raw(url, 'recommendation');",
        "const expectedDecoded = detail.searchParams.getAll('recommendation');",
        "const actualDecoded = url.searchParams.getAll('recommendation');",
        "expectedRaw.length !== 1 || actualRaw.length !== 1",
        "expectedDecoded[0] !== actualDecoded[0]",
        "expectedRaw=' + JSON.stringify(expectedRaw)",
        "actualDecoded=' + JSON.stringify(actualDecoded)",
        "if (key === 'recommendation') continue;",
        "$facilityExpectedReturnUrl = ([string]$facilityBefore.url -replace '#.*$', '') + "
        "'#facility-intelligence-results'",
        "$complaintExpectedReturnUrl = ([string]$complaintBefore.url -replace '#.*$', '') + "
        "'#facility-intelligence-results'",
        "expectedReturnUrl=$facilityExpectedReturnUrl",
        "expectedReturnUrl=$complaintExpectedReturnUrl",
        "controlled-non-200-fetch-seam",
    ):
        assert expected in script


def test_issue_655_exact_destination_timeout_preserves_complete_navigation_diagnostic() -> None:
    script = CAPTURE_SCRIPT.read_text(encoding="utf-8")
    helper_start = script.index("function Wait-Issue655ExactDestination")
    helper_end = script.index("function Invoke-Issue642BrowserCapture", helper_start)
    helper = script[helper_start:helper_end]
    for field in (
        "interactionId",
        "stage:'destination-wait'",
        "sourceUrl",
        "expectedDestination",
        "observedUrl",
        "historyLength",
        "readyState",
        "title",
        "activeElement",
        "regionCount",
        "targetCount",
        "targetOuterHtml",
        "targetHref",
        "targetVisible",
        "targetFocusable",
        "targetRectangle",
        "hitTestElement",
        "regionBusy",
        "navigationStages",
        "responseStatus",
        "consoleEvents",
        "consoleErrors",
        "consoleWarnings",
        "recentNetworkEvents",
        "relevantCdpException",
        "scopedHtml",
        "Page.captureScreenshot",
    ):
        assert field in helper


def test_issue_655_rehearsal_uses_capture_path_without_packaging() -> None:
    capture = CAPTURE_SCRIPT.read_text(encoding="utf-8")
    wrapper = WRAPPER_SCRIPT.read_text(encoding="utf-8")
    assert "[switch]$Issue655Rehearsal" in capture
    assert "Test-Issue655AcceptancePacket -PacketDirectory" in capture
    rehearsal_start = capture.index("if ($Issue655Rehearsal) {")
    rehearsal_end = capture.index("$focusedIssueScope", rehearsal_start)
    rehearsal = capture[rehearsal_start:rehearsal_end]
    assert "rehearsal-summary.json" in rehearsal
    assert "zipCreated=$false" in rehearsal
    assert "ownerReviewCreated=$false" in rehearsal
    assert "Compress-Archive" not in rehearsal
    assert "[switch]$Issue655Rehearsal" in wrapper
    assert "$captureArguments.Issue655Rehearsal = $true" in wrapper


def test_evidence_wrapper_uses_bounded_stable_free_port_guard() -> None:
    script = WRAPPER_SCRIPT.read_text(encoding="utf-8")
    for expected in (
        "function Get-PortListenerObservation",
        "function Test-StableFreePort",
        "function Write-PortObservations",
        "RequiredConsecutiveFree = 3",
        "IntervalMilliseconds = 250",
        "MaximumObservations = 20",
        "ObservationProvider",
        "three consecutive listener-free observations",
        "Transient listener observation cleared before launch.",
    ):
        assert expected in script

    capture_script = CAPTURE_SCRIPT.read_text(encoding="utf-8")
    assert "point.x * [double]$point.scale" not in capture_script
    assert "point.y * [double]$point.scale" not in capture_script
    assert "Input.dispatchMouseEvent" in capture_script
    assert "mousePressed" in capture_script
    assert "mouseReleased" in capture_script


def test_stable_free_port_fails_closed_and_uses_netstat_only_after_primary_failure() -> None:
    guard = wrapper_port_guard_functions()
    ps_lines = (
        "$freePrimary = { param($port) }",
        "$listenerPrimary = { param($port) New-Listener $port 4242 }",
        "$deniedPrimary = { param($port) throw 'Access denied' }",
        "$fallbackFree = { param($port) @('Active Connections') }",
        "$fallbackCalls = 0",
        "function New-Listener {",
        "  param($port, $processId)",
        "  [pscustomobject]@{ LocalAddress='127.0.0.1'; LocalPort=$port;",
        "    State='Listen'; OwningProcess=$processId }",
        "}",
        "function Test-Guard {",
        "  param($primary, $fallback, $maximum = 3)",
        "  Test-StableFreePort -LocalPort 8010 -MaximumObservations $maximum `",
        "    -IntervalMilliseconds 0 -PrimaryEnumerator $primary `",
        "    -FallbackEnumerator $fallback",
        "}",
        "$fallbackV4 = { param($port) @(",
        "  '  TCP    127.0.0.1:8010' +",
        "    '         0.0.0.0:0              LISTENING       6400') }",
        "$fallbackV6 = { param($port) @(",
        "  '  TCP    [::1]:8010' +",
        "    '             [::]:0                 LISTENING       6401') }",
        "$fallbackTimeWait = { param($port) @(",
        "  '  TCP    127.0.0.1:8010' +",
        "    '         127.0.0.1:50000        TIME_WAIT       0') }",
        "$fallbackOtherPort = { param($port) @(",
        "  '  TCP    127.0.0.1:8011' +",
        "    '         0.0.0.0:0              LISTENING       6402') }",
        "$fallbackMalformed = { param($port) @(",
        "  '  TCP    127.0.0.1:8010' +",
        "    '         0.0.0.0:0              LISTENING       not-a-pid') }",
        "$unexpectedFallback = { param($port)",
        "  $script:fallbackCalls++; throw 'fallback should not run' }",
        "$free = Test-Guard $freePrimary $unexpectedFallback",
        "$primaryListener = Test-Guard $listenerPrimary $fallbackFree",
        "$fallbackListenerV4 = Get-PortListenerObservation -LocalPort 8010 `",
        "  -PrimaryEnumerator $deniedPrimary -FallbackEnumerator $fallbackV4",
        "$fallbackListenerV6 = Get-PortListenerObservation -LocalPort 8010 `",
        "  -PrimaryEnumerator $deniedPrimary -FallbackEnumerator $fallbackV6",
        "$timeWait = Get-PortListenerObservation -LocalPort 8010 `",
        "  -PrimaryEnumerator $deniedPrimary -FallbackEnumerator $fallbackTimeWait",
        "$otherPort = Get-PortListenerObservation -LocalPort 8010 `",
        "  -PrimaryEnumerator $deniedPrimary -FallbackEnumerator $fallbackOtherPort",
        "$fallbackFailure = Get-PortListenerObservation -LocalPort 8010 `",
        "  -PrimaryEnumerator $deniedPrimary -FallbackEnumerator { throw 'netstat unavailable' }",
        "$fallbackMalformedResult = Get-PortListenerObservation -LocalPort 8010 `",
        "  -PrimaryEnumerator $deniedPrimary -FallbackEnumerator $fallbackMalformed",
        "$fallbackFreeStable = Test-Guard $deniedPrimary $fallbackFree",
        "$sequence = @(",
        "  [pscustomobject]@{ state='FREE'; listeners=@() },",
        "  [pscustomobject]@{ state='LISTENER_PRESENT'; listeners=@(New-Listener 8010 4242) },",
        "  [pscustomobject]@{ state='FREE'; listeners=@() },",
        "  [pscustomobject]@{ state='FREE'; listeners=@() },",
        "  [pscustomobject]@{ state='FREE'; listeners=@() }",
        ")",
        "$sequenceIndex = 0",
        "$reset = Test-StableFreePort -LocalPort 8010 -MaximumObservations 5 `",
        "  -IntervalMilliseconds 0 -ObservationProvider { param($index)",
        "    $result=$sequence[$script:sequenceIndex]; $script:sequenceIndex++; $result }",
        "[ordered]@{",
        "  free = @($free.free, $free.state, @($free.observations).Count, $fallbackCalls)",
        "  primary_listener = @($primaryListener.free, $primaryListener.state)",
        "  fallback_v4 = @($fallbackListenerV4.state, $fallbackListenerV4.primaryEnumeration,",
        "    $fallbackListenerV4.fallbackEnumeration, $fallbackListenerV4.listeners[0].owningPid)",
        "  fallback_v6 = @($fallbackListenerV6.state, $fallbackListenerV6.listeners[0].owningPid)",
        "  time_wait = @($timeWait.state, @($timeWait.listeners).Count)",
        "  other_port = @($otherPort.state, @($otherPort.listeners).Count)",
        "  fallback_failure = @($fallbackFailure.state, @($fallbackFailure.listeners).Count)",
        "  malformed = @($fallbackMalformedResult.state,",
        "    @($fallbackMalformedResult.listeners).Count)",
        "  fallback_free = @($fallbackFreeStable.free, $fallbackFreeStable.state,",
        "    $fallbackFreeStable.observations[0].fallbackEnumeration)",
        "  reset = @($reset.free, $reset.state, $reset.transientListener,",
        "    @($reset.observations).Count)",
        "} | ConvertTo-Json -Depth 8 -Compress",
    )
    ps_script = guard + "\n" + "\n".join(ps_lines)
    result = subprocess.run(
        [powershell(), "-NoProfile", "-Command", ps_script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, plain_output(result)
    observed = json.loads(plain_output(result).strip().splitlines()[-1])
    assert observed["free"] == [True, "FREE", 3, 0]
    assert observed["primary_listener"] == [False, "LISTENER_PRESENT"]
    assert observed["fallback_v4"] == ["LISTENER_PRESENT", "failed", "succeeded", 6400]
    assert observed["fallback_v6"] == ["LISTENER_PRESENT", 6401]
    assert observed["time_wait"] == ["FREE", 0]
    assert observed["other_port"] == ["FREE", 0]
    assert observed["fallback_failure"] == ["ENUMERATION_FAILED", 0]
    assert observed["malformed"] == ["ENUMERATION_FAILED", 0]
    assert observed["fallback_free"] == [True, "FREE", "succeeded"]
    assert observed["reset"] == [True, "FREE", True, 5]
    assert "Stop-Process" not in guard


def test_issue_655_fixture_acquisition_uses_bounded_candidates_and_readiness() -> None:
    script = WRAPPER_SCRIPT.read_text(encoding="utf-8")
    required = (
        "function Get-Issue655CandidatePorts",
        "return @(20000..20009)",
        "function Test-TaskOwnedFixtureReadiness",
        "function Get-TaskOwnedProcessIds",
        "function Stop-TaskOwnedFixture",
        "foreach ($candidate in $candidatePorts | Select-Object -Unique)",
        "Test-StableFreePort -LocalPort $candidate",
        "launch collision or fixture-start failure",
        "Issue #655 fixture acquisition exhausted",
        "ISSUE655_PORT_ACQUISITION=",
        "Join-Path ([System.IO.Path]::GetTempPath())",
    )
    for expected in required:
        assert expected in script
    assert script.index("Test-TaskOwnedFixtureReadiness") < script.index(
        "$captureArguments = @{"
    )
    assert "Join-Path $OutputDir \"launcher-logs\"" not in script
