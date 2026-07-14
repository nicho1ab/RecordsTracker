<#
.SYNOPSIS
Dry-runs or applies the governed hosted CCLD data backfill.
.DESCRIPTION
Uses configured PostgreSQL facility-reference rows and already-preserved CCLD
complaint artifacts. The default is dry-run. The command never downloads CCLD
reports and never writes without -Apply.
#>
param(
    [string]$FacilityNumber,
    [string]$FacilityNumberFile,
    [switch]$AllExisting,
    [ValidateSet("all", "facility-reference", "preserved-artifacts")]
    [string]$Operation = "all",
    [ValidateRange(1, 1000)]
    [int]$BatchSize = 100,
    [string]$CheckpointFile,
    [switch]$Restart,
    [switch]$Apply,
    [switch]$DryRun,
    [switch]$QnapContainer,
    [string]$ComposeFile = "docker-compose.qnap.yml",
    [string]$EnvFile = ".env"
)

$ErrorActionPreference = "Stop"
$selectionCount = @($FacilityNumber, $FacilityNumberFile, $AllExisting.IsPresent).Where({ $_ }).Count
if ($selectionCount -ne 1) {
    throw "Choose exactly one of -FacilityNumber, -FacilityNumberFile, or -AllExisting."
}
if ($Apply -and $DryRun) {
    throw "Use either -Apply or -DryRun, not both. Omit both for dry-run."
}

$arguments = @("scripts/backfill_hosted_ccld_data.py", "--operation", $Operation, "--batch-size", "$BatchSize")
if ($AllExisting) {
    $arguments += "--all-existing"
}
elseif (-not [string]::IsNullOrWhiteSpace($FacilityNumber)) {
    $arguments += @("--facility-number", $FacilityNumber)
}
else {
    $arguments += @("--facility-number-file", $FacilityNumberFile)
}
if (-not [string]::IsNullOrWhiteSpace($CheckpointFile)) {
    $arguments += @("--checkpoint-file", $CheckpointFile)
}
if ($Restart) {
    $arguments += "--restart"
}
if ($Apply) {
    $arguments += "--apply"
}
else {
    $arguments += "--dry-run"
}

if ($QnapContainer) {
    & docker compose -f $ComposeFile --env-file $EnvFile exec -T app python @arguments
}
else {
    $python = Join-Path $PWD ".venv\Scripts\python.exe"
    $srcPath = Join-Path $PWD "src"
    $previousPythonPath = $env:PYTHONPATH
    try {
        if ([string]::IsNullOrWhiteSpace($previousPythonPath)) {
            $env:PYTHONPATH = $srcPath
        }
        else {
            $env:PYTHONPATH = "$srcPath;$previousPythonPath"
        }
        if (Test-Path $python) {
            & $python @arguments
        }
        else {
            python @arguments
        }
    }
    finally {
        $env:PYTHONPATH = $previousPythonPath
    }
}
if (($null -ne $LASTEXITCODE) -and ($LASTEXITCODE -ne 0)) {
    exit $LASTEXITCODE
}
