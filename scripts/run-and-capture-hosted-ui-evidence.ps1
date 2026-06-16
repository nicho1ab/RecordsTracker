<#
.SYNOPSIS
Starts a local hosted CCLD mode and captures a UI evidence packet.
.DESCRIPTION
Convenience wrapper for local review only. It starts one existing hosted app script
in live, fixture, or scaffold mode, waits for the root route, then calls
scripts/capture-hosted-ui-evidence.ps1. It does not submit forms, trigger
retrieval, import data, mutate reviewer-created state, or call GitHub.
.PARAMETER Mode
Mode to run: live, fixture, or scaffold.
.PARAMETER Port
Local port to bind. Defaults to 8003 for live, 8010 for fixture, and 8000 for scaffold.
.PARAMETER OutputDir
Evidence output root. Defaults to data/processed/ui-evidence.
.PARAMETER KillExistingPortProcess
Stop any process listening on the chosen local port before launch.
.EXAMPLE
.\scripts\run-and-capture-hosted-ui-evidence.ps1 -Mode fixture -Port 8010 -KillExistingPortProcess
#>
param(
    [ValidateSet("live", "fixture", "scaffold")]
    [string]$Mode = "fixture",

    [int]$Port = 0,

    [string]$OutputDir = "data/processed/ui-evidence",

    [switch]$KillExistingPortProcess
)

$ErrorActionPreference = "Stop"

if ($Port -eq 0) {
    if ($Mode -eq "live") { $Port = 8003 }
    elseif ($Mode -eq "fixture") { $Port = 8010 }
    else { $Port = 8000 }
}

$baseUrl = "http://127.0.0.1:$Port"

if ($KillExistingPortProcess) {
    Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
}
elseif (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
    throw "Port $Port is already in use. Re-run with -KillExistingPortProcess or choose another port."
}

$scriptPath = switch ($Mode) {
    "live" { ".\scripts\run-hosted-complaint-retrieval-live.ps1" }
    "fixture" { ".\scripts\run-hosted-complaint-retrieval-demo.ps1" }
    default { ".\scripts\run-hosted-scaffold.ps1" }
}

$shell = (Get-Command pwsh -ErrorAction SilentlyContinue)
if (-not $shell) { $shell = Get-Command powershell -ErrorAction Stop }

$process = Start-Process -FilePath $shell.Source -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $scriptPath,
    "-Port",
    [string]$Port
) -PassThru

$deadline = (Get-Date).AddSeconds(30)
$ready = $false
while ((Get-Date) -lt $deadline) {
    try {
        $response = Invoke-WebRequest -Uri "$baseUrl/" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ([int]$response.StatusCode -eq 200) { $ready = $true; break }
    }
    catch {
        Start-Sleep -Milliseconds 500
    }
}

if (-not $ready) {
    Write-Host "Started process ID: $($process.Id)"
    Write-Host "Stop command: Stop-Process -Id $($process.Id)"
    throw "Hosted app did not respond at $baseUrl/ before timeout."
}

Write-Host "URL to open: $baseUrl/"
Write-Host "Started process ID: $($process.Id)"
Write-Host "Stop command: Stop-Process -Id $($process.Id)"

& .\scripts\capture-hosted-ui-evidence.ps1 -BaseUrl $baseUrl -Mode $Mode -OutputDir $OutputDir
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Evidence capture complete for $Mode mode at $baseUrl/."
Write-Host "Keep the app process running only as long as needed for review."
