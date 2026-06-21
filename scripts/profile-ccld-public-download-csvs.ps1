<#
.SYNOPSIS
Profiles CCLD public download CSVs and emits a normalized facility-reference CSV.
.DESCRIPTION
Reads CCLD public download CSV files from data\raw\ccld (or a specified directory)
and writes ignored profile and reference outputs under data\processed\ccld-public-downloads.

Outputs:
  ccld-download-profile.json   Per-file profile: row count, header count,
                               row-width warnings, facility type/status/county counts.
  ccld-download-profile.csv    Flat summary CSV (one row per input file).
  facility-reference.csv       Normalized reference CSV for use with
                               -FacilityReferenceCsv in the stakeholder export.

The reference CSV has columns:
  FacilityNumber, FacilityName, FacilityType, ProgramType, Status, City, County,
  Capacity, LicenseFirstDate, ClosedDate, LastVisitDate, SourceFile

Use -FacilityType and -FacilityStatus to produce a targeted cohort CSV.

This script does not import data into the database, modify raw files, add schemas,
add connectors, or make network requests. Public CCLD portal remains the source of
record. Absence or zero counts is not source completeness.
.PARAMETER InputPath
Directory containing CCLD public download CSV files. Defaults to data\raw\ccld.
Pass individual file paths as positional arguments to the underlying Python script
via -CsvFiles if needed.
.PARAMETER OutputDir
Ignored output directory for profile and reference files.
Defaults to data\processed\ccld-public-downloads.
.PARAMETER FacilityType
Optional facility type filter for the reference CSV (case-insensitive).
Example: "Temporary Shelter Care Facility"
.PARAMETER FacilityStatus
Optional facility status filter for the reference CSV (case-insensitive).
Example: "Licensed"
.PARAMETER ReferenceCsvName
Output file name for the normalized reference CSV.
Defaults to facility-reference.csv.
.EXAMPLE
.\scripts\profile-ccld-public-download-csvs.ps1
.EXAMPLE
.\scripts\profile-ccld-public-download-csvs.ps1 -FacilityType "Temporary Shelter Care Facility" -FacilityStatus "Licensed"
.EXAMPLE
.\scripts\profile-ccld-public-download-csvs.ps1 -OutputDir data\processed\tscf-cohort -ReferenceCsvName tscf-licensed.csv -FacilityType "Temporary Shelter Care Facility" -FacilityStatus "Licensed"
.NOTES
Run from the repository root. Requires Python venv (run setup-project.ps1 first).
Output files are gitignored.
#>
param(
    [string]$InputPath = "data\raw\ccld",
    [string]$OutputDir = "data\processed\ccld-public-downloads",
    [string]$FacilityType = "",
    [string]$FacilityStatus = "",
    [string]$ReferenceCsvName = "facility-reference.csv"
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
        "scripts\profile_ccld_public_download_csvs.py",
        "--input-dir", $InputPath,
        "--output-dir", $OutputDir,
        "--reference-csv-name", $ReferenceCsvName
    )
    if (-not [string]::IsNullOrWhiteSpace($FacilityType)) {
        $args_list += @("--facility-type", $FacilityType)
    }
    if (-not [string]::IsNullOrWhiteSpace($FacilityStatus)) {
        $args_list += @("--facility-status", $FacilityStatus)
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
