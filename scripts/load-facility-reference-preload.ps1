<#
.SYNOPSIS
Preloads local CHHS/CDSS CCLD facility CSV rows into PostgreSQL.
.DESCRIPTION
Reads ignored local CCLD facility CSV files, parses supported CHHS/CDSS facility
resource shapes, and compares or writes rows in the hosted facility-reference
table. This script does not download live CHHS data, run complaint retrieval,
modify reviewer-created state, or contact deployment hosts.
.PARAMETER InputPath
Local CSV file or folder to scan recursively for CSV files.
.PARAMETER Apply
Write inserts and updates. Actual preload writes require this explicit switch.
.PARAMETER DryRun
Compare local CSV rows with existing PostgreSQL table rows without writing. This
is the default when Apply is omitted.
.PARAMETER SourceAccessedAt
Optional ISO timestamp to store as source_accessed_at for all rows. Defaults to
each CSV file modification time.
.EXAMPLE
.\scripts\load-facility-reference-preload.ps1 -InputPath data\raw\source-profiling -DryRun
.EXAMPLE
.\scripts\load-facility-reference-preload.ps1 -InputPath data\raw\source-profiling -Apply
.NOTES
Set CCLD_HOSTED_TESTER_DATABASE_URL before running this script. Dry-run mode
also needs the database because it compares CSV rows with existing table rows to
calculate inserted, updated, and unchanged counts.
#>
param(
    [string]$InputPath = "data\raw\source-profiling",
    [switch]$Apply,
    [switch]$DryRun,
    [string]$SourceAccessedAt
)

$ErrorActionPreference = "Stop"
if ($Apply -and $DryRun) {
    throw "Use either -Apply or -DryRun, not both. Omit both switches for the default dry-run behavior."
}

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

    $arguments = @(
        "scripts\load_facility_reference_preload.py",
        "--input-path",
        $InputPath
    )
    if ($Apply) {
        $arguments += "-Apply"
    }
    else {
        $arguments += "-DryRun"
    }
    if (-not [string]::IsNullOrWhiteSpace($SourceAccessedAt)) {
        $arguments += @("--source-accessed-at", $SourceAccessedAt)
    }

    if (Test-Path $python) {
        & $python @arguments
    }
    else {
        python @arguments
    }
    if (($null -ne $LASTEXITCODE) -and ($LASTEXITCODE -ne 0)) {
        exit $LASTEXITCODE
    }
}
finally {
    $env:PYTHONPATH = $previousPythonPath
}
