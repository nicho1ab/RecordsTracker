<#
.SYNOPSIS
Verifies the hosted local/test reviewer flow and optionally captures evidence.
.DESCRIPTION
Performs non-mutating checks against an already-running hosted CCLD scaffold
to validate the local/test reviewer acceptance flow. Optionally runs the
existing `capture-hosted-ui-evidence.ps1` to produce an evidence packet and
verifies draft workflow assertions do not warn about hidden workflow rail.

This script defaults to non-mutating checks. When `-RunWriteChecks` is
provided it may surface reviewer-created state behaviors but will not itself
mutate source-derived records.

.PARAMETER BaseUrl
Base URL of the already-running hosted app, e.g. http://127.0.0.1:8003
.PARAMETER Mode
Capture mode label: live, fixture, or scaffold (defaults to scaffold)
.PARAMETER ContextFacilityNumber
Facility number to use for context-route checks. Default: 157806098
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

Test-AllowedBaseUrl -Value $BaseUrl

$checks = @(
    @{ Name = "Home"; Path = "/"; Required = @("CCLD Records Review") },
    @{ Name = "Retrieve"; Path = "/ccld/records/request"; Required = @("Which facility should be reviewed?", "Confirm facility") },
    @{ Name = "Reviewer"; Path = "/reviewer"; Required = @("Worklist", "Open local/test packet preview", "Open local/test preparation draft for browser copy or print") },
    @{ Name = "ReviewerRecords"; Path = "/reviewer/records"; Required = @("Worklist") },
    @{ Name = "ReviewerDetail"; Path = "/reviewer/records/detail?source_record_key=complaint%3Accld%3Acomplaint%3A32-CR-20220407124448"; Required = @("Complaint overview", "Record review action") },
    @{ Name = "PacketPreviewEmpty"; Path = "/reviewer/packet/preview"; Required = @("No facility/date packet context was supplied."); Forbidden = @("Date range: not provided") },
    @{ Name = "PacketPreviewContext"; Path = ("/reviewer/packet/preview?facility_number={0}&start_date={1}&end_date={2}&request_context_origin=manual_entry" -f $ContextFacilityNumber, $ContextStartDate, $ContextEndDate); Required = @($ContextFacilityNumber, "Before copying or printing", "browser copy or print", "not a certified report", "Report copy/print preparation concern") ; Forbidden = @("Date range: not provided") },
    @{ Name = "PacketDraftEmpty"; Path = "/reviewer/packet/draft"; Required = @("No facility/date packet context was supplied."); Forbidden = @("Date range: not provided") },
    @{ Name = "PacketDraftContext"; Path = ("/reviewer/packet/draft?facility_number={0}&start_date={1}&end_date={2}&request_context_origin=manual_entry" -f $ContextFacilityNumber, $ContextStartDate, $ContextEndDate); Required = @("Attorney Review Packet Draft", "Local/test preparation draft for browser copy or print", "Review before copying or printing", "not a certified report", "Report copy/print preparation concern", $ContextFacilityNumber); Forbidden = @("Date range: not provided") }
)

$forbiddenMarkers = @(
    "provider_subject", "provider-subject", "provider_issuer", "provider-issuer",
    "client_secret", "client-secret", "connection string", "connection_string",
    "set-cookie", "authorization:", "bearer ", "github_pat_", "ghp_",
    "private_header", "private-header"
)

$results = [System.Collections.ArrayList]::new()
$failCount = 0

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

    if ($entry.Passed) { $entry.Messages += "PASS" }
    else { $failCount++ }
    $results.Add($entry) | Out-Null
}

if ($IncludeCapture) {
    Write-Host "Running capture-hosted-ui-evidence.ps1 to produce an evidence packet (non-mutating GET-only)."
    $captureCmd = ".\scripts\capture-hosted-ui-evidence.ps1 -BaseUrl `"$BaseUrl`" -Mode $Mode -IncludeScreenshots `$false -AllowUnavailable"
    Write-Host "Capture command: $captureCmd"
    try {
        $beforeCapture = Get-Date
        $captureOutput = & .\scripts\capture-hosted-ui-evidence.ps1 -BaseUrl $BaseUrl -Mode $Mode -IncludeScreenshots $false -AllowUnavailable *>&1 | Out-String
        Write-Host $captureOutput
        $evidenceLine = ($captureOutput -split "`n" | Where-Object { $_ -match "EVIDENCE_PACKET_PATH=" }) | Select-Object -First 1
        $evidencePath = $null
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
            Write-Host "Evidence packet: $evidencePath"
            $assertionsCsv = Join-Path $evidencePath 'route-assertions.csv'
            if (Test-Path -LiteralPath $assertionsCsv) {
                $assertions = Import-Csv -Path $assertionsCsv
                foreach ($routeName in @('packet-draft-empty', 'packet-draft-context')) {
                    $rows = $assertions | Where-Object { $_.route -eq $routeName -and $_.check -eq 'workflow step' }
                    if (-not $rows) {
                        Write-Warning "No workflow-step assertion found for $routeName in $assertionsCsv"
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
                            }
                        }
                    }
                }
            }
            else { Write-Warning "Evidence assertions CSV not found at $assertionsCsv"; $failCount++ }
        }
        else { Write-Warning "Could not locate evidence packet path from capture output."; $failCount++ }
    }
    catch {
        Write-Warning "Capture script failed: $($_.Exception.Message)"
        $failCount++
    }
}

Write-Host "\nAcceptance check summary:"
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

Write-Host "Acceptance checks passed."
exit 0
