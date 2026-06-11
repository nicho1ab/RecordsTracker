<#
.SYNOPSIS
Fetches live public CCLD report content for explicit facilities.
.DESCRIPTION
Explicitly user-invoked live workflow that discovers public CCLD reports for one or more provided facility numbers, downloads a limited number of raw report files into a gitignored local data/raw path, then ingests the saved raw files into SQLite for Datasette review.
.PARAMETER FacilityNumber
Public CCLD facility number to fetch. Repeat or pass multiple values for multiple explicit facilities.
.PARAMETER FacilityInputPath
Small text or CSV file containing public CCLD facility numbers to fetch.
.PARAMETER DbPath
SQLite database path to initialize and populate.
.PARAMETER RawDir
Local gitignored directory for downloaded raw report files.
.PARAMETER Limit
Maximum number of discovered reports to fetch per facility. Use a small number first.
.PARAMETER MaxRequests
Safety guard for the maximum number of total report requests allowed.
.PARAMETER All
Fetch all discovered reports for each explicit facility, subject to MaxRequests.
.EXAMPLE
.\scripts\run-ccld-live-fetch.ps1 -Limit 1
.EXAMPLE
.\scripts\run-ccld-live-fetch.ps1 -FacilityNumber 157806098, 123456789 -Limit 1 -MaxRequests 2
.EXAMPLE
.\scripts\run-ccld-live-fetch.ps1 -FacilityInputPath .\facility-numbers.csv -Limit 1 -MaxRequests 3
.EXAMPLE
.\scripts\run-ccld-live-fetch.ps1 -Limit 3 -MaxRequests 5 -DbPath data\processed\live-ccld.sqlite
.EXAMPLE
.\scripts\run-ccld-live-fetch.ps1 -All -MaxRequests 50
.NOTES
Run from the repository root. This command accesses a public external site only when invoked by the user.
#>
param(
    [string[]]$FacilityNumber = @(),
    [string]$FacilityInputPath,
    [string]$DbPath = "data\processed\ccld.sqlite",
    [string]$RawDir = "data\raw\ccld",
    [ValidateRange(0, [int]::MaxValue)]
    [int]$Limit = 1,
    [ValidateRange(0, [int]::MaxValue)]
    [int]$MaxRequests = 5,
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
        "--db-path",
        $DbPath,
        "--raw-dir",
        $RawDir,
        "--max-requests",
        $MaxRequests
    )

    foreach ($number in $FacilityNumber) {
        $arguments += @("--facility-number", $number)
    }

    if (-not [string]::IsNullOrWhiteSpace($FacilityInputPath)) {
        $arguments += @("--facility-input-path", $FacilityInputPath)
    }

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