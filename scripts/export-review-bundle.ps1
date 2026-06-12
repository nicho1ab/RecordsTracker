<#
.SYNOPSIS
Exports source-traceable CSV review outputs.
.DESCRIPTION
Reads the local SQLite database and writes a derived complaint review bundle with accessible CSV headers, source traceability fields, and review caution notes.
.PARAMETER DbPath
SQLite database path to export from.
.PARAMETER OutputDir
Directory where review bundle CSV files will be written.
.EXAMPLE
.\scripts\export-review-bundle.ps1
.EXAMPLE
.\scripts\export-review-bundle.ps1 -DbPath data\processed\live-ccld.sqlite -OutputDir data\processed\live-review-bundle
.NOTES
Run from the repository root after populating the SQLite database.
#>
param(
    [string]$DbPath = "data\processed\ccld.sqlite",
    [string]$OutputDir = "data\processed\review-bundle"
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

    if (Test-Path $python) {
        & $python -m ccld_complaints.cli.export_review_bundle --db-path $DbPath --output-dir $OutputDir
    }
    else {
        python -m ccld_complaints.cli.export_review_bundle --db-path $DbPath --output-dir $OutputDir
    }
}
finally {
    $env:PYTHONPATH = $previousPythonPath
}