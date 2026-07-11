<#
.SYNOPSIS
Repairs persisted live CCLD retrieval import-batch provenance.
.DESCRIPTION
Dry-runs or applies a bounded source-derived metadata repair for rows whose own
source traceability points to a persisted live public CCLD retrieval job but
whose import batch was inherited from fixture, demo, test, seeded, or unknown
metadata. The repair does not retrieve public data, delete source-derived rows,
or mutate reviewer-created state.
.PARAMETER Apply
Apply the repair. Omit for read-only dry-run reporting.
.EXAMPLE
.\scripts\repair-live-retrieval-provenance.ps1
.EXAMPLE
.\scripts\repair-live-retrieval-provenance.ps1 -Apply
#>
param(
    [switch]$Apply
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

    $arguments = @("scripts\repair_live_retrieval_provenance.py")
    if ($Apply) {
        $arguments += "--apply"
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
