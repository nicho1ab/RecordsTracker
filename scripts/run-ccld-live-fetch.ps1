<#
.SYNOPSIS
Fetches live public CCLD report content for the POC facility.
.DESCRIPTION
Explicitly user-invoked live workflow that discovers public CCLD reports, downloads a limited number of raw report files into a gitignored local data/raw path, then ingests the saved raw files into SQLite for Datasette review.
.PARAMETER FacilityNumber
Public CCLD facility number to fetch.
.PARAMETER DbPath
SQLite database path to initialize and populate.
.PARAMETER RawDir
Local gitignored directory for downloaded raw report files.
.PARAMETER Limit
Maximum number of discovered reports to fetch. Use a small number first.
.PARAMETER All
Fetch all discovered reports for the facility.
.EXAMPLE
.\scripts\run-ccld-live-fetch.ps1 -Limit 1
.EXAMPLE
.\scripts\run-ccld-live-fetch.ps1 -Limit 3 -DbPath data\processed\live-ccld.sqlite
.EXAMPLE
.\scripts\run-ccld-live-fetch.ps1 -All
.NOTES
Run from the repository root. This command accesses a public external site only when invoked by the user.
#>
param(
    [string]$FacilityNumber = "157806098",
    [string]$DbPath = "data\processed\ccld.sqlite",
    [string]$RawDir = "data\raw\ccld",
    [ValidateRange(0, [int]::MaxValue)]
    [int]$Limit = 1,
    [switch]$All
)

$ErrorActionPreference = "Stop"
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
        "-m",
        "ccld_complaints.cli.fetch_live_ccld",
        "--facility-number",
        $FacilityNumber,
        "--db-path",
        $DbPath,
        "--raw-dir",
        $RawDir
    )

    if ($All) {
        $arguments += "--all"
    }
    else {
        $arguments += @("--limit", $Limit)
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