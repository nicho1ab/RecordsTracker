<#
.SYNOPSIS
Generates a read-only representative CCLD coverage report.
.DESCRIPTION
Reads hosted PostgreSQL facility-reference, source-derived complaint, and
retrieval-job metadata tables to summarize loaded facility types, source files,
source URLs, snapshot/retrieval dates, traceability, duplicate checks, and
reconciliation counts. This script does not download sources, run retrieval,
write raw artifacts, import rows, or mutate reviewer-created state. Clearly
identified fixture/demo/test rows and unknown-provenance rows are reported
separately and excluded from representative coverage counts.
.PARAMETER OutputJson
Optional JSON output path. Omit to print the report to stdout.
.EXAMPLE
.\scripts\report-representative-coverage.ps1 -OutputJson data\processed\representative-coverage\coverage-report.json
#>
param(
    [string]$OutputJson
)

$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptRoot "..")
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$srcPath = Join-Path $repoRoot "src"
$previousPythonPath = $env:PYTHONPATH

Push-Location $repoRoot
try {
    if ([string]::IsNullOrWhiteSpace($previousPythonPath)) {
        $env:PYTHONPATH = $srcPath
    }
    else {
        $env:PYTHONPATH = "$srcPath;$previousPythonPath"
    }

    $arguments = @("scripts\report_representative_coverage.py")
    if (-not [string]::IsNullOrWhiteSpace($OutputJson)) {
        $arguments += @("--output-json", $OutputJson)
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
    Pop-Location
}
