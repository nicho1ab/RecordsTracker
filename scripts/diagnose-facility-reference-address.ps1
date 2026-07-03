<#
.SYNOPSIS
Diagnoses missing address data for a preloaded CCLD facility reference row.
.DESCRIPTION
Reads one facility/license number from hosted_facility_reference_records and
compares normalized address fields with address-like columns preserved in
original_row_json. This script is read-only. It does not download source data,
run complaint retrieval, write database rows, modify reviewer-created state, or
contact deployment hosts.
.PARAMETER FacilityNumber
Digit CCLD facility/license number to inspect.
.PARAMETER Json
Print JSON output instead of readable text.
.EXAMPLE
.\scripts\diagnose-facility-reference-address.ps1 -FacilityNumber 347006659
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$FacilityNumber,
    [switch]$Json
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
        "scripts\diagnose_facility_reference_address.py",
        "--facility-number",
        $FacilityNumber
    )
    if ($Json) {
        $arguments += "--json"
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
