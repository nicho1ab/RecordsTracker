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
.PARAMETER PythonExecutable
Verified Python executable to pass to the fixture/demo launcher. Required for a
secondary worktree that has no local virtual environment.
.PARAMETER Issue502
Capture the focused Issue #502 Home and Find a Facility evidence packet.
.PARAMETER Issue420
Capture the focused Issue #420 Facility Overview evidence packet.
.PARAMETER Issue642
Capture the focused Issue #642 Compare Facilities interaction evidence packet.
.PARAMETER Issue642LicensingSourceUnavailable
Launch the separate Issue #642 fixture state with the Licensing source absent.
.EXAMPLE
.\scripts\run-and-capture-hosted-ui-evidence.ps1 -Mode fixture -Port 8010 -KillExistingPortProcess
.EXAMPLE
.\scripts\run-and-capture-hosted-ui-evidence.ps1 -Mode fixture -Port 8010 -Issue502
.EXAMPLE
.\scripts\run-and-capture-hosted-ui-evidence.ps1 -Mode fixture -Port 8010 -Issue420
#>
param(
    [ValidateSet("live", "fixture", "scaffold")]
    [string]$Mode = "fixture",

    [int]$Port = 0,

    [string]$OutputDir = "data/processed/ui-evidence",

    [switch]$KillExistingPortProcess,

    [string]$PythonExecutable = "",

    [switch]$Issue502,

    [switch]$Issue420,

    [switch]$Issue642,

    [switch]$Issue642LicensingSourceUnavailable
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

if ($Mode -eq "fixture" -and [string]::IsNullOrWhiteSpace($PythonExecutable)) {
    $worktreePython = Join-Path $PWD ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $worktreePython -PathType Leaf) {
        $PythonExecutable = $worktreePython
    }
    else {
        throw "Fixture mode requires -PythonExecutable when the current worktree has no local virtual environment."
    }
}

$shell = (Get-Command pwsh -ErrorAction SilentlyContinue)
if (-not $shell) { $shell = Get-Command powershell -ErrorAction Stop }

$launcherArguments = @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $scriptPath,
    "-Port",
    [string]$Port
)
if ($Mode -eq "fixture") {
    $launcherArguments += @("-PythonExecutable", $PythonExecutable)
    if ($Issue642) { $launcherArguments += "-Issue642Evidence" }
    if ($Issue642LicensingSourceUnavailable) { $launcherArguments += "-Issue642LicensingSourceUnavailable" }
}
$launcherLogDir = Join-Path $OutputDir "launcher-logs"
New-Item -ItemType Directory -Force -Path $launcherLogDir | Out-Null
$launcherLogPrefix = "{0}-{1}" -f $Mode, (Get-Date).ToUniversalTime().ToString("yyyyMMdd-HHmmssZ")
$launcherStdout = Join-Path $launcherLogDir "$launcherLogPrefix.stdout.log"
$launcherStderr = Join-Path $launcherLogDir "$launcherLogPrefix.stderr.log"
$process = Start-Process -FilePath $shell.Source -ArgumentList $launcherArguments -WorkingDirectory $PWD -RedirectStandardOutput $launcherStdout -RedirectStandardError $launcherStderr -WindowStyle Hidden -PassThru

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
    $process.Refresh()
    Write-Host "Started process ID: $($process.Id)"
    Write-Host "Stop command: Stop-Process -Id $($process.Id)"
    Write-Host "Launcher stdout: $launcherStdout"
    Write-Host "Launcher stderr: $launcherStderr"
    if ($process.HasExited) {
        throw "Hosted app launcher exited with code $($process.ExitCode) before $baseUrl/ became ready."
    }
    throw "Hosted app did not respond at $baseUrl/ before timeout."
}

Write-Host "URL to open: $baseUrl/"
Write-Host "Started process ID: $($process.Id)"
Write-Host "Stop command: Stop-Process -Id $($process.Id)"

$captureArguments = @{
    BaseUrl = $baseUrl
    Mode = $Mode
    OutputDir = $OutputDir
}
if ($Issue502) { $captureArguments.Issue502 = $true }
if ($Issue420) { $captureArguments.Issue420 = $true }
if ($Issue642) { $captureArguments.Issue642 = $true }
if ($Issue642LicensingSourceUnavailable) {
    $captureArguments.Issue642 = $true
    $captureArguments.Issue642LicensingSourceUnavailable = $true
}
& .\scripts\capture-hosted-ui-evidence.ps1 @captureArguments
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Evidence capture complete for $Mode mode at $baseUrl/."
Write-Host "Keep the app process running only as long as needed for review."
