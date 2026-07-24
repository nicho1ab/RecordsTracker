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


def powershell_function(function_name: str, next_function_name: str) -> str:
    script = CAPTURE_SCRIPT.read_text(encoding="utf-8")
    start = script.index(f"function {function_name}")
    end = script.index(f"\nfunction {next_function_name}", start)
    return script[start:end]


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
        "Issue415",
        "Issue416",
        "Issue417",
        "Issue418",
        "Issue419",
        "Issue498",
        "manifest.json",
        "file-index.json",
        "route-status.csv",
        "route-assertions.csv",
        "issue-415-count-summaries.csv",
        "issue-415-href-inventory.csv",
        "issue-416-count-summaries.csv",
        "issue-417-count-summaries.csv",
        "issue-418-count-summaries.csv",
        "issue-419-approved-versus-rendered.csv",
        "issue-419-ui-gates.csv",
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
        "Evidence ZIP membership and sizes do not match the packet file index.",
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
    assert "-Issue498" in script
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
        "READY FOR EXPLICIT OWNER REVIEW",
        "Issue #501 repository-readable controlled variance",
    ):
        assert issue_419_contract in script
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
    for fixture_key in (
        "ccld-complaint-32-CR-20240603151515-rt-src-002-supported-fixture",
        "ccld-complaint-32-CR-20240610181818-rt-src-002-document-only-fixture",
        "complaint%3Accld%3Acomplaint%3A32-CR-20220407124448",
        "ccld-complaint-32-CR-20240120111111-rt-src-002-source-unavailable-fixture",
    ):
        assert fixture_key in script


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
        + "$length = (Get-Item -LiteralPath $zip).Length\n"
        + "Set-Content -LiteralPath (Join-Path $packet 'README.txt') -Value '' -NoNewline\n"
        + "try { Test-EvidencePacketFiles -PacketDirectory $packet | Out-Null; "
        + "$zero = 'not rejected' } "
        + "catch { $zero = $_.Exception.Message }\n"
        + "[ordered]@{ Hash = $hash; Length = $length; ZeroLength = $zero } | ConvertTo-Json\n"
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
    assert verified["Length"] > 0
    assert "zero-length files" in verified["ZeroLength"]


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
        "Properties": ["Socket", "Process", "ProfileDir", "NextId"],
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
            "READY FOR EXPLICIT OWNER REVIEW"
        )
        assert "IA-419-01" in comparison_csv
        assert "IA-419-09" in comparison_csv
        for gate_number in range(1, 10):
            assert f"RT-UI-GATE-{gate_number:03d}" in gates_csv
        assert "READY FOR EXPLICIT OWNER REVIEW" in gates_csv
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
