<#
.SYNOPSIS
Captures GET-only Issue #477 operator coverage dashboard evidence.
.DESCRIPTION
Starts a fresh local fixture server for each deterministic contract scenario,
verifies the exact worktree branch and server health markers, and uses Playwright
with local Microsoft Edge to capture route, responsive, keyboard-focus, 200%
scale, print, and download evidence. It never submits a form or invokes a write.
.EXAMPLE
.\scripts\capture-operator-coverage-dashboard-evidence.ps1 -OutputRoot data\processed\ui-evidence -Port 8027 -FixtureMode contract-v1
#>
param(
    [string]$OutputRoot = "data\processed\ui-evidence",

    [Parameter(Mandatory = $true)]
    [ValidateRange(1024, 65535)]
    [int]$Port,

    [Parameter(Mandatory = $true)]
    [ValidateSet("contract-v1")]
    [string]$FixtureMode
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$expectedBranch = "issue-477-operator-coverage-dashboard"
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$fixtureRoot = Join-Path $repoRoot "tests\fixtures\hosted_operator_coverage_dashboard"
$processedRoot = [IO.Path]::GetFullPath((Join-Path $repoRoot "data\processed"))
$resolvedOutputRoot = [IO.Path]::GetFullPath((Join-Path $repoRoot $OutputRoot))
if (-not $resolvedOutputRoot.StartsWith($processedRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "OutputRoot must remain under the ignored data/processed directory."
}

$branch = (& git -C $repoRoot branch --show-current).Trim()
$commitSha = (& git -C $repoRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $branch -ne $expectedBranch -or -not $commitSha) {
    throw "Evidence capture must run from branch $expectedBranch at a resolved HEAD."
}

$pythonCandidates = @(
    (Join-Path $repoRoot ".venv\Scripts\python.exe"),
    (Join-Path ($repoRoot -replace "-issue-477$", "") ".venv\Scripts\python.exe")
) | Select-Object -Unique
$python = $pythonCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $python) {
    throw "A repository virtual environment with Python and Playwright is required."
}
& $python -c "import playwright.sync_api" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "The selected repository virtual environment does not include Playwright."
}

function Test-LoopbackPortInUse {
    param([int]$Number)
    $client = [Net.Sockets.TcpClient]::new()
    try {
        $pending = $client.BeginConnect("127.0.0.1", $Number, $null, $null)
        if (-not $pending.AsyncWaitHandle.WaitOne(250)) { return $false }
        try { $client.EndConnect($pending); return $true }
        catch { return $false }
    }
    finally { $client.Dispose() }
}

if (Test-LoopbackPortInUse -Number $Port) {
    throw "Port $Port is already in use; refusing to reuse an existing server."
}

$timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd-HHmmss'Z'")
$packetDir = Join-Path $resolvedOutputRoot "$timestamp-issue-477-operator-coverage"
$screenshotsDir = Join-Path $packetDir "screenshots"
$htmlDir = Join-Path $packetDir "html"
$downloadsDir = Join-Path $packetDir "downloads"
$diagnosticsDir = Join-Path $packetDir "diagnostics"
New-Item -ItemType Directory -Force -Path $screenshotsDir, $htmlDir, $downloadsDir, $diagnosticsDir | Out-Null

$browserHelper = Join-Path $diagnosticsDir "capture-browser.py"
$browserSource = @'
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

config_path = Path(sys.argv[1])
output_path = Path(sys.argv[2])
config = json.loads(config_path.read_text(encoding="utf-8"))
packet = Path(config["packet_dir"])
results = []

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(channel="msedge", headless=True)
    try:
        for capture in config["captures"]:
            label = capture["label"]
            url = config["base_url"] + capture["path"]
            kind = capture.get("kind", "page")
            if kind == "download":
                request = urllib.request.Request(url, method="GET")
                try:
                    with urllib.request.urlopen(request, timeout=15) as response:
                        status = response.status
                        body = response.read()
                        content_type = response.headers.get("Content-Type", "")
                        disposition = response.headers.get("Content-Disposition", "")
                except urllib.error.HTTPError as error:
                    status = error.code
                    body = error.read()
                    content_type = error.headers.get("Content-Type", "")
                    disposition = error.headers.get("Content-Disposition", "")
                destination = packet / "downloads" / capture["filename"]
                destination.write_bytes(body)
                results.append(
                    {
                        "label": label,
                        "path": capture["path"],
                        "kind": kind,
                        "status": status,
                        "expected_status": capture["expected_status"],
                        "content_type": content_type,
                        "content_disposition": disposition,
                        "bytes": len(body),
                        "assertions": [
                            {
                                "name": "expected HTTP status",
                                "passed": status == capture["expected_status"],
                                "detail": f"expected {capture['expected_status']}, received {status}",
                            },
                            {
                                "name": "CSV content type",
                                "passed": content_type.startswith("text/csv"),
                                "detail": content_type,
                            },
                            {
                                "name": "attachment disposition",
                                "passed": disposition.startswith("attachment;"),
                                "detail": disposition,
                            },
                            {
                                "name": "LF line endings",
                                "passed": b"\r" not in body,
                                "detail": "CSV contains no carriage returns",
                            },
                        ],
                    }
                )
                continue

            width = capture["width"]
            height = capture["height"]
            scale = capture.get("device_scale_factor", 1)
            context = browser.new_context(
                viewport={"width": width, "height": height},
                device_scale_factor=scale,
                accept_downloads=False,
            )
            page = context.new_page()
            response = page.goto(url, wait_until="networkidle", timeout=20000)
            status = response.status if response is not None else 0
            if kind == "focus":
                for _ in range(24):
                    page.keyboard.press("Tab")
                    focused = page.evaluate(
                        """() => {
                          const e = document.activeElement;
                          if (!e) return null;
                          const s = getComputedStyle(e);
                          return {tag: e.tagName, text: (e.innerText || e.getAttribute('aria-label') || '').trim(), outline: s.outlineStyle, width: e.getBoundingClientRect().width};
                        }"""
                    )
                    if focused and focused["tag"] in {"A", "BUTTON", "INPUT", "SELECT"} and focused["width"] > 0:
                        break
            else:
                focused = None
            if kind == "print":
                page.emulate_media(media="print")

            metrics = page.evaluate(
                """() => ({
                  scrollWidth: document.documentElement.scrollWidth,
                  clientWidth: document.documentElement.clientWidth,
                  h1Count: document.querySelectorAll('h1').length,
                  captionCount: document.querySelectorAll('table caption').length,
                  primaryOperatorLinks: [...document.querySelectorAll('nav.civic-nav a')].filter(a => a.getAttribute('href')?.startsWith('/operator/source-coverage')).length,
                  forms: [...document.forms].map(f => (f.method || 'get').toLowerCase()),
                  actionControls: [...document.querySelectorAll('button,a')].map(e => (e.textContent || '').trim().toLowerCase()).filter(t => ['retry','apply','cancel','resume','backfill'].includes(t)),
                  headingLevels: [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].map(h => Number(h.tagName.substring(1)))
                })"""
            )
            markup = page.content()
            html_path = packet / "html" / f"{label}.html"
            html_path.write_text(markup, encoding="utf-8", newline="\n")
            screenshot_path = packet / "screenshots" / f"{label}.png"
            page.screenshot(path=str(screenshot_path), full_page=True)
            if kind == "print":
                page.pdf(
                    path=str(packet / "screenshots" / f"{label}.pdf"),
                    print_background=True,
                    prefer_css_page_size=True,
                )

            body_text = page.locator("body").inner_text()
            heading_levels = metrics["headingLevels"]
            no_heading_jump = all(
                current <= previous + 1
                for previous, current in zip(heading_levels, heading_levels[1:])
            )
            assertions = [
                {
                    "name": "expected HTTP status",
                    "passed": status == capture["expected_status"],
                    "detail": f"expected {capture['expected_status']}, received {status}",
                },
                {
                    "name": "single h1",
                    "passed": metrics["h1Count"] == 1,
                    "detail": f"h1 count {metrics['h1Count']}",
                },
                {
                    "name": "semantic heading order",
                    "passed": no_heading_jump,
                    "detail": json.dumps(heading_levels),
                },
                {
                    "name": "no horizontal page overflow",
                    "passed": metrics["scrollWidth"] <= metrics["clientWidth"],
                    "detail": f"scroll {metrics['scrollWidth']}; client {metrics['clientWidth']}",
                },
                {
                    "name": "operator absent from primary reviewer navigation",
                    "passed": metrics["primaryOperatorLinks"] == 0,
                    "detail": f"primary operator links {metrics['primaryOperatorLinks']}",
                },
                {
                    "name": "GET-only forms",
                    "passed": all(method == "get" for method in metrics["forms"]),
                    "detail": json.dumps(metrics["forms"]),
                },
                {
                    "name": "no mutation controls",
                    "passed": not metrics["actionControls"],
                    "detail": json.dumps(metrics["actionControls"]),
                },
                {
                    "name": "fixture label",
                    "passed": "Fixture coverage data" in body_text,
                    "detail": "visible fixture mode label",
                },
            ]
            for marker in capture.get("contains", []):
                assertions.append(
                    {
                        "name": f"contains {marker}",
                        "passed": marker in body_text,
                        "detail": marker,
                    }
                )
            for marker in capture.get("not_contains", []):
                assertions.append(
                    {
                        "name": f"omits {marker}",
                        "passed": marker.casefold() not in markup.casefold(),
                        "detail": marker,
                    }
                )
            if kind == "focus":
                assertions.append(
                    {
                        "name": "keyboard focus reaches visible control",
                        "passed": bool(focused) and focused["outline"] != "none",
                        "detail": json.dumps(focused, sort_keys=True),
                    }
                )
            results.append(
                {
                    "label": label,
                    "path": capture["path"],
                    "kind": kind,
                    "status": status,
                    "expected_status": capture["expected_status"],
                    "viewport": f"{width}x{height}",
                    "device_scale_factor": scale,
                    "metrics": metrics,
                    "focused": focused,
                    "assertions": assertions,
                }
            )
            context.close()
    finally:
        browser.close()

output_path.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
'@
Set-Content -LiteralPath $browserHelper -Value $browserSource -Encoding utf8

$scenarios = @(
    [ordered]@{
        Name = "complete-balanced"; Package = "complete-balanced"; Captures = @(
            [ordered]@{ Label = "01-complete-summary-desktop"; Path = "/operator/source-coverage"; Width = 1440; Height = 1100; ExpectedStatus = 200; Contains = @("Coverage through reviewer surfaces", "Retrieval, import, artifacts, checkpoints, and jobs", "Seven existing program-specific sources") },
            [ordered]@{ Label = "02-filtered-facilities-narrow"; Path = "/operator/source-coverage/facilities?processing_outcome=failed&sort=last_refresh_attempt_at&direction=desc"; Width = 720; Height = 900; ExpectedStatus = 200; Contains = @("Showing 1", "of 1 facilities", "Active filters") },
            [ordered]@{ Label = "03-filtered-empty"; Path = "/operator/source-coverage/facilities?q=999999999"; Width = 720; Height = 900; ExpectedStatus = 200; Contains = @("Showing 0", "of 0 facilities", "Clear filters") },
            [ordered]@{ Label = "04-failed-operational-job"; Path = "/operator/source-coverage/jobs"; Width = 1440; Height = 1100; ExpectedStatus = 200; Contains = @("Hash validation failed", "Intervention required") },
            [ordered]@{ Label = "05-mobile-long-identifiers"; Path = "/operator/source-coverage/facilities"; Width = 390; Height = 844; ExpectedStatus = 200; Contains = @("Facility coverage details") },
            [ordered]@{ Label = "06-keyboard-focus"; Path = "/operator/source-coverage/facilities"; Width = 720; Height = 900; ExpectedStatus = 200; Kind = "focus"; Contains = @("Filter authorized facility metadata") },
            [ordered]@{ Label = "07-zoom-200-percent"; Path = "/operator/source-coverage"; Width = 360; Height = 450; DeviceScaleFactor = 2; ExpectedStatus = 200; Contains = @("Coverage through reviewer surfaces") },
            [ordered]@{ Label = "08-print-summary"; Path = "/operator/source-coverage"; Width = 1440; Height = 1100; ExpectedStatus = 200; Kind = "print"; Contains = @("Validated coverage report", "Generated at (UTC)") },
            [ordered]@{ Label = "09-aggregate-download"; Path = "/operator/source-coverage/export.csv"; ExpectedStatus = 200; Kind = "download"; Filename = "aggregate-coverage.csv" },
            [ordered]@{ Label = "10-failed-facility-ids"; Path = "/operator/source-coverage/facility-ids.csv?group=failed"; ExpectedStatus = 200; Kind = "download"; Filename = "failed-facility-ids.csv" }
        )
    },
    [ordered]@{ Name = "empty-verified"; Package = "empty-verified"; Captures = @(
        [ordered]@{ Label = "11-verified-empty"; Path = "/operator/source-coverage"; Width = 1440; Height = 1100; ExpectedStatus = 200; Contains = @("Verified empty coverage report") }
    ) },
    [ordered]@{ Name = "partial-unavailable-stage"; Package = "partial-unavailable-stage"; Captures = @(
        [ordered]@{ Label = "12-partial-unavailable-stage"; Path = "/operator/source-coverage"; Width = 720; Height = 900; ExpectedStatus = 200; Contains = @("Partial coverage", "Operator facility index") }
    ) },
    [ordered]@{ Name = "unavailable-package"; Package = "unavailable-package"; Captures = @(
        [ordered]@{ Label = "13-unavailable-package"; Path = "/operator/source-coverage"; Width = 720; Height = 900; ExpectedStatus = 503; Contains = @("Coverage report unavailable") }
    ) },
    [ordered]@{ Name = "interrupted-job-previous-accepted-active"; Package = "interrupted-job-previous-accepted-active"; Captures = @(
        [ordered]@{ Label = "14-interrupted-previous-accepted"; Path = "/operator/source-coverage/jobs"; Width = 1440; Height = 1100; ExpectedStatus = 200; Contains = @("Previous accepted report remains active", "Interrupted") }
    ) },
    [ordered]@{ Name = "failed-reconciliation"; Package = "failed-reconciliation"; Captures = @(
        [ordered]@{ Label = "15-reconciliation-failed"; Path = "/operator/source-coverage"; Width = 720; Height = 900; ExpectedStatus = 422; Contains = @("Coverage report reconciliation failed") }
    ) },
    [ordered]@{ Name = "hash-validation-failure"; Package = "hash-validation-failure"; Captures = @(
        [ordered]@{ Label = "16-hash-failed"; Path = "/operator/source-coverage"; Width = 720; Height = 900; ExpectedStatus = 422; Contains = @("Coverage report hash validation failed") }
    ) },
    [ordered]@{ Name = "version-mismatch"; Package = "version-mismatch"; Captures = @(
        [ordered]@{ Label = "17-version-mismatch"; Path = "/operator/source-coverage"; Width = 720; Height = 900; ExpectedStatus = 409; Contains = @("Coverage report version is not supported") }
    ) },
    [ordered]@{ Name = "raw-733-unresolved"; Package = "raw-733-unresolved"; Captures = @(
        [ordered]@{ Label = "18-raw-733-unresolved"; Path = "/operator/source-coverage"; Width = 390; Height = 844; ExpectedStatus = 200; Contains = @("733", "no approved facility-type mapping", "Every statewide candidate remains inactive") }
    ) },
    [ordered]@{ Name = "pagination-adjacent-pages"; Package = "pagination-adjacent-pages"; Captures = @(
        [ordered]@{ Label = "19-keyset-first-page"; Path = "/operator/source-coverage/facilities?limit=2"; Width = 720; Height = 900; ExpectedStatus = 200; Contains = @("Showing 1", "of 6 facilities", "Next facilities") }
    ) }
)

$environmentNames = @(
    "CCLD_HOSTED_TESTER_AUTH_MODE",
    "CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH",
    "CCLD_OPERATOR_COVERAGE_FIXTURE_MODE",
    "CCLD_OPERATOR_COVERAGE_PACKAGE_DIR",
    "CCLD_OPERATOR_COVERAGE_FIXTURE_SCENARIO",
    "CCLD_OPERATOR_COVERAGE_COMMIT_SHA",
    "CCLD_OPERATOR_COVERAGE_BRANCH"
)
$savedEnvironment = @{}
foreach ($name in $environmentNames) {
    $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
}

$allResults = [Collections.Generic.List[object]]::new()
$baseUrl = "http://127.0.0.1:$Port"
try {
    foreach ($scenario in $scenarios) {
        if (Test-LoopbackPortInUse -Number $Port) {
            throw "Port $Port became occupied before scenario $($scenario.Name)."
        }
        $env:CCLD_HOSTED_TESTER_AUTH_MODE = "local-dev"
        $env:CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH = "enabled"
        $env:CCLD_OPERATOR_COVERAGE_FIXTURE_MODE = $FixtureMode
        $env:CCLD_OPERATOR_COVERAGE_PACKAGE_DIR = Join-Path $fixtureRoot $scenario.Package
        $env:CCLD_OPERATOR_COVERAGE_FIXTURE_SCENARIO = $scenario.Name
        $env:CCLD_OPERATOR_COVERAGE_COMMIT_SHA = $commitSha
        $env:CCLD_OPERATOR_COVERAGE_BRANCH = $branch

        $stdoutLog = Join-Path $diagnosticsDir "$($scenario.Name)-server.stdout.txt"
        $stderrLog = Join-Path $diagnosticsDir "$($scenario.Name)-server.stderr.txt"
        $server = Start-Process -FilePath $python -ArgumentList @(
            "-m", "ccld_complaints.hosted_app", "--host", "127.0.0.1", "--port", $Port
        ) -WorkingDirectory $repoRoot -PassThru -WindowStyle Hidden -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog
        try {
            $health = $null
            $deadline = (Get-Date).AddSeconds(25)
            while ((Get-Date) -lt $deadline) {
                if ($server.HasExited) { throw "Fixture server exited during startup for $($scenario.Name)." }
                try {
                    $health = Invoke-RestMethod -Uri "$baseUrl/health" -Method Get -TimeoutSec 2
                    if ($health.status -eq "ok") { break }
                }
                catch { Start-Sleep -Milliseconds 150 }
            }
            if (
                $null -eq $health -or
                $health.operator_coverage_fixture_mode -ne $FixtureMode -or
                $health.operator_coverage_commit_sha -ne $commitSha -or
                $health.operator_coverage_branch -ne $branch
            ) {
                throw "Health markers do not match this worktree, branch, commit, and fixture mode."
            }

            $scenarioConfig = [ordered]@{
                packet_dir = $packetDir
                base_url = $baseUrl
                captures = @($scenario.Captures | ForEach-Object {
                    [ordered]@{
                        label = $_.Label
                        path = $_.Path
                        width = if ($_.Contains("Width")) { $_.Width } else { 0 }
                        height = if ($_.Contains("Height")) { $_.Height } else { 0 }
                        device_scale_factor = if ($_.Contains("DeviceScaleFactor")) { $_.DeviceScaleFactor } else { 1 }
                        expected_status = $_.ExpectedStatus
                        kind = if ($_.Contains("Kind")) { $_.Kind } else { "page" }
                        filename = if ($_.Contains("Filename")) { $_.Filename } else { "" }
                        contains = if ($_.Contains("Contains")) { @($_.Contains) } else { @() }
                        not_contains = @("provider_subject", "provider_issuer", "connection_string", "raw_html", "source_url", "stack_trace")
                    }
                })
            }
            $configPath = Join-Path $diagnosticsDir "$($scenario.Name)-capture-config.json"
            $resultPath = Join-Path $diagnosticsDir "$($scenario.Name)-browser-results.json"
            $scenarioConfig | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $configPath -Encoding utf8
            & $python $browserHelper $configPath $resultPath
            if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $resultPath)) {
                throw "Automated browser capture failed for $($scenario.Name)."
            }
            $results = Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
            foreach ($result in @($results)) {
                $result | Add-Member -NotePropertyName scenario -NotePropertyValue $scenario.Name
                $allResults.Add($result)
            }
        }
        finally {
            if ($server -and -not $server.HasExited) {
                Stop-Process -Id $server.Id -Force
                $server.WaitForExit(5000) | Out-Null
            }
            $releaseDeadline = (Get-Date).AddSeconds(5)
            while ((Get-Date) -lt $releaseDeadline -and (Test-LoopbackPortInUse -Number $Port)) {
                Start-Sleep -Milliseconds 100
            }
        }
    }
}
finally {
    foreach ($name in $environmentNames) {
        [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], "Process")
    }
}

$assertionRows = [Collections.Generic.List[string]]::new()
$assertionRows.Add('scenario,label,path,assertion,status,detail')
$routeRows = [Collections.Generic.List[string]]::new()
$routeRows.Add('scenario,label,path,kind,status,expected_status,viewport,device_scale_factor')
$failedAssertions = 0
foreach ($result in $allResults) {
    $viewport = if ($result.PSObject.Properties.Name -contains "viewport") { $result.viewport } else { "download" }
    $scale = if ($result.PSObject.Properties.Name -contains "device_scale_factor") { $result.device_scale_factor } else { "" }
    $routeRows.Add((@($result.scenario, $result.label, $result.path, $result.kind, $result.status, $result.expected_status, $viewport, $scale) | ForEach-Object { '"' + ([string]$_).Replace('"', '""') + '"' }) -join ',')
    foreach ($assertion in $result.assertions) {
        $status = if ($assertion.passed) { "PASS" } else { "FAIL"; $failedAssertions++ }
        $assertionRows.Add((@($result.scenario, $result.label, $result.path, $assertion.name, $status, $assertion.detail) | ForEach-Object { '"' + ([string]$_).Replace('"', '""') + '"' }) -join ',')
    }
}
$assertionRows -join "`n" | Set-Content -LiteralPath (Join-Path $packetDir "route-assertions.csv") -Encoding utf8
$routeRows -join "`n" | Set-Content -LiteralPath (Join-Path $packetDir "route-status.csv") -Encoding utf8

$reviewerAbsenceCommand = @'
from ccld_complaints.hosted_app.app import route_response
for route in ("/reviewer", "/ccld"):
    status, _content_type, body = route_response(route, page_data_mode="fixture-demo")
    if b"/operator/source-coverage" in body:
        raise SystemExit(f"operator route leaked into reviewer-tier HTML for {route}")
'@
$encodedReviewCheck = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($reviewerAbsenceCommand))
& $python -c "import base64;exec(base64.b64decode('$encodedReviewCheck'))"
if ($LASTEXITCODE -ne 0) { $failedAssertions++; throw "Reviewer-tier absence assertion failed." }
Add-Content -LiteralPath (Join-Path $packetDir "route-assertions.csv") -Value '"in-process","reviewer-tier-absence","/reviewer and /ccld","operator route absent from reviewer HTML","PASS","No browser navigation outside the exact allowlist was used"' -Encoding utf8

$manifest = [ordered]@{
    evidence_kind = "issue-477-read-only-operator-coverage"
    fixture_mode = $FixtureMode
    fixture_label = "Fixture coverage data"
    generated_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    branch = $branch
    commit_sha = $commitSha
    base_url = $baseUrl
    get_only = $true
    server_fresh_per_scenario = $true
    scenarios = @($scenarios.Name)
    captures = $allResults.Count
    assertions_failed = $failedAssertions
    viewports = @("1440x1100", "720x900", "390x844", "360x450 at device scale factor 2")
    design_requirements = @("RT-DOM-001", "RT-TIER-001", "RT-STATE-001", "RT-RWD-001", "RT-A11Y-001", "RT-A11Y-002", "RT-STRESS-001", "RT-PRINT-001", "RT-SAFE-001")
    mutation_features = @("retry deferred", "apply deferred", "cancel deferred", "resume deferred", "backfill execution deferred", "database writes absent")
    network_allowlist = @("$baseUrl/health", "$baseUrl/operator/source-coverage", "$baseUrl/operator/source-coverage/facilities", "$baseUrl/operator/source-coverage/jobs", "$baseUrl/operator/source-coverage/export.csv", "$baseUrl/operator/source-coverage/facility-ids.csv?group=<allowed-group>")
}
$manifest | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $packetDir "manifest.json") -Encoding utf8

Remove-Item -LiteralPath $browserHelper -Force
$zipPath = "$packetDir.zip"
Compress-Archive -LiteralPath $packetDir -DestinationPath $zipPath -Force
if ($failedAssertions -ne 0) {
    throw "Evidence capture completed with $failedAssertions failed assertion(s). See $packetDir."
}

Write-Host "EVIDENCE_PACKET_PATH=$packetDir"
Write-Host "EVIDENCE_ZIP_PATH=$zipPath"
Write-Host "EVIDENCE_ASSERTIONS=PASS"
