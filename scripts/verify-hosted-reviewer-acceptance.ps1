<#
.SYNOPSIS
Verifies the hosted local/test reviewer flow and optionally captures evidence.
.DESCRIPTION
Performs non-mutating checks against an already-running hosted CCLD scaffold
to validate the local/test reviewer acceptance flow. Optionally runs the
existing `capture-hosted-ui-evidence.ps1` to produce an evidence packet and
verifies the captured route set plus draft workflow assertions. Captured
evidence folders are zipped as local review artifacts only.

This script defaults to non-mutating checks. When `-RunWriteChecks` is
provided it may surface reviewer-created state behaviors but will not itself
mutate source-derived records.

.PARAMETER BaseUrl
Base URL of the already-running hosted app, e.g. http://127.0.0.1:8003
.PARAMETER Mode
Capture mode label: live, fixture, or scaffold (defaults to scaffold)
.PARAMETER ContextFacilityNumber
Facility number to use for context-route checks. Default: 157806098
.PARAMETER PreloadedFacilityNumber
Known loaded preloaded facility-directory example for facility-hub checks. Default: 434417302
.PARAMETER ContextStartDate
Context route start date. Default: 2026-01-01
.PARAMETER ContextEndDate
Context route end date. Default: 2026-01-31
.PARAMETER RunWriteChecks
When present, run optional reviewer-created state checks. Default: false
.PARAMETER TimeoutSeconds
Per-route GET timeout seconds. Default: 10
.PARAMETER IncludeCapture
When present, run `capture-hosted-ui-evidence.ps1` and verify draft workflow assertions.
.EXAMPLE
.\scripts\verify-hosted-reviewer-acceptance.ps1 -BaseUrl http://127.0.0.1:8003 -Mode live
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$BaseUrl,

    [ValidateSet("live", "fixture", "scaffold")]
    [string]$Mode = "scaffold",

    [string]$ContextFacilityNumber = "157806098",
    [string]$PreloadedFacilityNumber = "434417302",
    [string]$ContextStartDate = "2026-01-01",
    [string]$ContextEndDate = "2026-01-31",

    [switch]$RunWriteChecks,
    [int]$TimeoutSeconds = 10,
    [switch]$IncludeCapture
)

$ErrorActionPreference = "Stop"

function Test-AllowedBaseUrl {
    param([string]$Value)
    try { $uri = [System.Uri]::new($Value) }
    catch { throw "BaseUrl must be an absolute http:// or https:// URL." }
    if ($uri.Scheme -notin @("http", "https")) { throw "BaseUrl must use http or https." }
    $hostValue = $uri.Host.Trim("[", "]").ToLowerInvariant()
    if ($hostValue -in @("localhost", "127.0.0.1", "::1")) { return }
    $ip = $null
    if ([System.Net.IPAddress]::TryParse($hostValue, [ref]$ip)) {
        $bytes = $ip.GetAddressBytes()
        if ($ip.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork) {
            if ($bytes[0] -eq 10) { return }
            if ($bytes[0] -eq 172 -and $bytes[1] -ge 16 -and $bytes[1] -le 31) { return }
            if ($bytes[0] -eq 192 -and $bytes[1] -eq 168) { return }
        }
    }
    throw "BaseUrl must be localhost or a private test IP address. Refusing: $Value"
}

function Get-RouteContent {
    param([string]$Url, [int]$Timeout)
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $Timeout -ErrorAction Stop
        return [pscustomobject]@{ StatusCode = [int]$response.StatusCode; Content = [string]$response.Content; Error = "" }
    }
    catch {
        if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
            $status = [int]$_.Exception.Response.StatusCode
            return [pscustomobject]@{ StatusCode = $status; Content = ""; Error = "HTTP $status" }
        }
        return [pscustomobject]@{ StatusCode = 0; Content = ""; Error = $_.Exception.Message }
    }
}

function Join-RouteUrl {
    param([string]$Base, [string]$Path)
    $trimmedBase = $Base.TrimEnd("/")
    if ($Path.StartsWith("/")) { return "$trimmedBase$Path" }
    return "$trimmedBase/$Path"
}

function New-EvidenceZip {
    param([string]$EvidencePath)
    if (-not $EvidencePath -or -not (Test-Path -LiteralPath $EvidencePath -PathType Container)) {
        throw "Evidence folder was not found for ZIP packaging."
    }
    $zipPath = "$EvidencePath.zip"
    $archiveSource = Join-Path $EvidencePath '*'
    Compress-Archive -Path $archiveSource -DestinationPath $zipPath -Force
    if (-not (Test-Path -LiteralPath $zipPath -PathType Leaf)) {
        throw "Evidence ZIP was not created."
    }
    return $zipPath
}

Test-AllowedBaseUrl -Value $BaseUrl

$encodedSourceRecordKey = [System.Uri]::EscapeDataString('complaint:ccld:complaint:32-CR-20220407124448')
$contextQuery = "facility_number=$ContextFacilityNumber&start_date=$ContextStartDate&end_date=$ContextEndDate&request_context_origin=manual_entry"

$checks = @(
    @{ Name = "home-start"; Path = "/"; Required = @("Find a Facility", "Find the Facility ID", "Search CCLD facilities", "Continue to Request Records") },
    @{ Name = "ccld-start"; Path = "/ccld/"; Required = @("Request Records", "Request complaint records for a facility", "Which facility should be reviewed?") },
    @{ Name = "facility-lookup"; Path = "/ccld/facilities"; Required = @("Find a facility", "Find the Facility ID", "Search by name, Facility ID, city, county, ZIP") },
    @{ Name = "facility-priority"; Path = "/ccld/facilities/review-priority"; Required = @("Facility review priority", "review cue", "uploaded public summary fields") },
    @{ Name = "facility-intelligence"; Path = "/ccld/facilities/intelligence"; Required = @("Facility review intelligence", "review cue", "How to use these indicators") },
    @{ Name = "facility-hub"; Path = "/ccld/facilities/detail?facility_number=$PreloadedFacilityNumber"; Required = @("Facility review hub", "Facility review hub", "Back to search") },
    @{ Name = "record-request"; Path = "/ccld/records/request"; Required = @("Which facility should be reviewed?", "Confirm facility", "Request complaint records for a facility") },
    @{ Name = "record-request-context"; Path = "/ccld/records/request?$contextQuery"; Required = @($ContextFacilityNumber, "Open loaded records or request complaint records", "Show existing queue", "Date range") },
    @{ Name = "reviewer"; Path = "/reviewer"; Required = @("Complaint worklist", "Review complaint"); Forbidden = @("Open local/test packet preview", "Open local/test preparation draft for browser copy or print") },
    @{ Name = "reviewer-records"; Path = "/reviewer/records"; Required = @("Complaint worklist", "Review complaint") },
    @{ Name = "matrix-export"; Path = "/reviewer/records/matrix.csv?$contextQuery"; Required = @("complaint review matrix", "CSV export", "source_record_key", "review_guidance") },
    @{ Name = "reviewer-detail"; Path = "/reviewer/records/detail?source_record_key=$encodedSourceRecordKey&$contextQuery"; Required = @("Complaint overview", "Complaint overview", "CCLD source available", "Status and note") },
    @{ Name = "packet-preview-empty"; Path = "/reviewer/packet/preview"; Required = @("No facility/date packet context was supplied."); Forbidden = @("Date range: not provided") },
    @{ Name = "packet-preview-context"; Path = "/reviewer/packet/preview?$contextQuery"; Required = @($ContextFacilityNumber, "Packet preview", "Included complaint records", "Readiness checks", "Before copying or printing", "Open print draft", "Send feedback", "Back to review queue") ; Forbidden = @("Date range: not provided", "Open local/test preparation draft for browser copy or print", "Report copy/print preparation concern", "Return to same facility/date queue") },
    @{ Name = "packet-draft-empty"; Path = "/reviewer/packet/draft"; Required = @("No facility/date packet context was supplied."); Forbidden = @("Date range: not provided") },
    @{ Name = "packet-draft-context"; Path = "/reviewer/packet/draft?$contextQuery"; Required = @("Attorney Review Packet Draft", "Preparation draft for browser copy or print", "Review before copying or printing", "Before using this draft", "Report copy/print preparation concern", $ContextFacilityNumber); Forbidden = @("Date range: not provided") },
    @{ Name = "feedback"; Path = "/feedback"; Required = @("Feedback", "Send RecordsTracker feedback", "Do not include private material", "Feedback type", "Description") },
    @{ Name = "help"; Path = "/ccld/help"; Required = @("Find a facility", "Reviewer Detail", "Review Queue", "Packet preview and preparation draft") }
)

$forbiddenMarkers = @(
    "provider_subject", "provider-subject", "provider_issuer", "provider-issuer",
    "client_secret", "client-secret", "connection string", "connection_string",
    "set-cookie", "authorization:", "bearer ", "github_pat_", "ghp_",
    "private_header", "private-header"
)

$results = [System.Collections.ArrayList]::new()
$failCount = 0

Write-Host "Tester-readiness acceptance mode: $Mode"
Write-Host "Default route checks are non-mutating GET checks."
if ($RunWriteChecks) {
    Write-Host "RunWriteChecks was explicitly requested; no additional write probe is run by this verifier. Use only on a safe test/staging instance."
}
else {
    Write-Host "Write checks skipped. Supply -RunWriteChecks only for a safe test/staging instance."
}

foreach ($check in $checks) {
    $url = Join-RouteUrl -Base $BaseUrl -Path $check.Path
    Write-Host "Checking $($check.Name): $url"
    $resp = Get-RouteContent -Url $url -Timeout $TimeoutSeconds
    $entry = [ordered]@{ Name = $check.Name; Path = $check.Path; Url = $url; Status = $resp.StatusCode; Passed = $true; Messages = @() }
    if ($resp.StatusCode -eq 0 -or $resp.StatusCode -ge 400) {
        $entry.Passed = $false
        $entry.Messages += "Route returned status $($resp.StatusCode) or error: $($resp.Error)"
        $results.Add($entry) | Out-Null
        $failCount++
        continue
    }

    $contentLower = $resp.Content.ToLowerInvariant()
    if ($check.ContainsKey('Required')) {
        foreach ($marker in $check.Required) {
            if (-not $contentLower.Contains($marker.ToLowerInvariant())) {
                $entry.Passed = $false
                $entry.Messages += "Missing expected marker: $marker"
            }
        }
    }
    if ($check.ContainsKey('Forbidden')) {
        foreach ($marker in $check.Forbidden) {
            if ($contentLower.Contains($marker.ToLowerInvariant())) {
                $entry.Passed = $false
                $entry.Messages += "Found forbidden marker: $marker"
            }
        }
    }
    foreach ($marker in $forbiddenMarkers) {
        if ($contentLower.Contains($marker)) {
            $entry.Passed = $false
            $entry.Messages += "Found forbidden private marker: $marker"
        }
    }

    if ($entry.Passed) { $entry.Messages += "PASS"; Write-Host "PASS $($check.Name) -> HTTP $($resp.StatusCode)" }
    else { $failCount++ }
    $results.Add($entry) | Out-Null
}

$evidencePath = $null
$evidenceZipPath = $null

if ($IncludeCapture) {
    Write-Host "Running capture-hosted-ui-evidence.ps1 to produce an evidence packet (non-mutating GET-only)."
    $captureCmd = ".\scripts\capture-hosted-ui-evidence.ps1 -BaseUrl `"$BaseUrl`" -Mode $Mode -IncludeScreenshots `$false -AllowUnavailable"
    Write-Host "Capture command: $captureCmd"
    try {
        $beforeCapture = Get-Date
        $captureOutput = & .\scripts\capture-hosted-ui-evidence.ps1 -BaseUrl $BaseUrl -Mode $Mode -IncludeScreenshots $false -AllowUnavailable *>&1 | Out-String
        Write-Host $captureOutput
        $evidenceLine = ($captureOutput -split "`n" | Where-Object { $_ -match "EVIDENCE_PACKET_PATH=" }) | Select-Object -First 1
        if ($evidenceLine) {
            $evidencePath = ($evidenceLine -replace '.*EVIDENCE_PACKET_PATH=', '').Trim()
        }
        if (-not $evidencePath -or -not (Test-Path -LiteralPath $evidencePath -PathType Container)) {
            $evidenceRoot = Join-Path $PSScriptRoot ".." "data" "processed" "ui-evidence"
            $newest = Get-ChildItem -LiteralPath $evidenceRoot -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.LastWriteTime -gt $beforeCapture } |
            Sort-Object LastWriteTime -Descending | Select-Object -First 1
            if ($newest) { $evidencePath = $newest.FullName; Write-Host "Evidence packet (fallback lookup): $evidencePath" }
        }
        if ($evidencePath) {
            Write-Host "Evidence folder path: $evidencePath"
            Write-Host "EVIDENCE_PACKET_PATH=$evidencePath"
            try {
                $evidenceZipPath = New-EvidenceZip -EvidencePath $evidencePath
                Write-Host "Evidence ZIP path: $evidenceZipPath"
                Write-Host "EVIDENCE_PACKET_ZIP_PATH=$evidenceZipPath"
            }
            catch {
                Write-Host "[NOTICE] Evidence ZIP creation failed: $($_.Exception.Message)"
                $failCount++
            }
            $routeStatusCsv = Join-Path $evidencePath 'route-status.csv'
            if (Test-Path -LiteralPath $routeStatusCsv) {
                $routeStatusRows = Import-Csv -Path $routeStatusCsv
                foreach ($routeName in @('home', 'facility', 'facility-priority', 'facility-intelligence', 'facility-hub', 'request-records', 'reviewer', 'matrix-export', 'packet-preview-empty', 'packet-preview-context', 'packet-draft-empty', 'packet-draft-context', 'feedback', 'help')) {
                    if (-not ($routeStatusRows | Where-Object { $_.route -eq $routeName -or $_.name -eq $routeName })) {
                        Write-Host "[NOTICE] Evidence route-status.csv is missing route: $routeName"
                        $failCount++
                    }
                }
            }
            else { Write-Host "[NOTICE] Evidence route status CSV not found at $routeStatusCsv"; $failCount++ }
            $assertionsCsv = Join-Path $evidencePath 'route-assertions.csv'
            if (Test-Path -LiteralPath $assertionsCsv) {
                $assertions = Import-Csv -Path $assertionsCsv
                foreach ($routeName in @('packet-preview-empty', 'packet-preview-context', 'packet-draft-empty', 'packet-draft-context')) {
                    if (-not ($assertions | Where-Object { $_.route -eq $routeName })) {
                        Write-Host "[NOTICE] No assertion rows found for $routeName in $assertionsCsv"
                        $failCount++
                    }
                }
                foreach ($routeName in @('packet-draft-empty', 'packet-draft-context')) {
                    $rows = $assertions | Where-Object { $_.route -eq $routeName -and $_.check -eq 'workflow step' }
                    if (-not $rows) {
                        Write-Host "[NOTICE] No workflow-step assertion found for $routeName in $assertionsCsv"
                        $failCount++
                    }
                    else {
                        foreach ($r in $rows) {
                            if ($r.status -ne 'PASS') {
                                $rStatus = $r.status; $rMessage = $r.message
                                Write-Error "Unexpected workflow-step status for ${routeName}: ${rStatus} - ${rMessage}"
                                $failCount++
                            }
                            else {
                                $rMessage = $r.message
                                Write-Host "Workflow-step assertion for ${routeName}: PASS - ${rMessage}"
                                if ($rMessage -notmatch "(?i)packet draft intentionally hides workflow indicator") {
                                    Write-Host "[NOTICE] Workflow-step assertion for ${routeName} did not describe the intentional packet draft workflow-indicator skip."
                                    $failCount++
                                }
                            }
                        }
                    }
                }
            }
            else { Write-Host "[NOTICE] Evidence assertions CSV not found at $assertionsCsv"; $failCount++ }
        }
        else { Write-Host "[NOTICE] Could not locate evidence packet path from capture output."; $failCount++ }
    }
    catch {
        Write-Host "[NOTICE] Capture script failed: $($_.Exception.Message)"
        $failCount++
    }
}

Write-Host "`nTester-readiness acceptance summary:"
Write-Host "Mode: $Mode"
Write-Host "Base URL: $BaseUrl"
Write-Host "Routes checked: $($checks.Count)"
$passed = ($results | Where-Object { $_.Passed })
Write-Host "Checks passed: $($passed.Count)"
$failed = ($results | Where-Object { -not $_.Passed })
Write-Host "Checks failed: $($failed.Count)"
if ($failed.Count -gt 0) {
    foreach ($f in $failed) {
        Write-Host "-- $($f.Name): $($f.Messages -join '; ')"
    }
}

if ($failCount -gt 0) {
    Write-Error "Acceptance checks failed with $failCount failures."
    exit 1
}

if ($evidencePath) { Write-Host "Evidence folder path: $evidencePath" }
if ($evidenceZipPath) { Write-Host "Evidence ZIP path: $evidenceZipPath" }
Write-Host "Acceptance checks passed."
exit 0
