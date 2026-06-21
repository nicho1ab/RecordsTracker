<#
.SYNOPSIS
Exports a stakeholder facility overview extract (CSV ZIP) from local source-derived data.
.DESCRIPTION
Reads the local SQLite database and writes a stakeholder-ready ZIP package containing
a per-facility summary CSV, a substantiated/equivalent complaint CSV, a README, and
a manifest. Output goes under data/processed/stakeholder-extracts/<timestamp>/.

This is a review aid only. The public CCLD portal remains the source of record.
Counts reflect only loaded records. Does not make legal conclusions, facility-wide
conclusions, verified severity claims, or source-completeness claims. Raw narrative
text is intentionally excluded.
.PARAMETER DbPath
SQLite database path to export from.
.PARAMETER OutputRoot
Root directory under which a timestamped output folder will be created.
.PARAMETER FacilityReferenceCsv
Optional path to a facility reference CSV. When provided, facilities in the reference
are included in facility-overview.csv even when no complaint records are loaded for
them. Complaint counts are always based only on loaded records.
.EXAMPLE
.\scripts\export-stakeholder-facility-overview.ps1
.EXAMPLE
.\scripts\export-stakeholder-facility-overview.ps1 -DbPath data\processed\live-ccld.sqlite
.EXAMPLE
.\scripts\export-stakeholder-facility-overview.ps1 -FacilityReferenceCsv data\processed\facility-list.csv
.NOTES
Run from the repository root after populating the SQLite database.
Requires Python venv to be initialised (run setup-project.ps1 first).
#>
param(
    [string]$DbPath = "data\processed\ccld.sqlite",
    [string]$OutputRoot = "data\processed\stakeholder-extracts",
    [string]$FacilityReferenceCsv = ""
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

    $args_list = @(
        "-m", "ccld_complaints.cli.export_stakeholder_facility_overview",
        "--db-path", $DbPath,
        "--output-root", $OutputRoot
    )
    if (-not [string]::IsNullOrWhiteSpace($FacilityReferenceCsv)) {
        $args_list += @("--facility-reference-csv", $FacilityReferenceCsv)
    }

    if (Test-Path $python) {
        & $python @args_list
    }
    else {
        python @args_list
    }
}
finally {
    $env:PYTHONPATH = $previousPythonPath
}
