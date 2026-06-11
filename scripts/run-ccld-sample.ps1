<#
.SYNOPSIS
Populates the sample SQLite database.
.DESCRIPTION
Initializes the local SQLite database and writes the bundled fixture-backed CCLD report data for local Datasette browsing.
.PARAMETER DbPath
SQLite database path to initialize and populate.
.EXAMPLE
.\scripts\run-ccld-sample.ps1
.EXAMPLE
.\scripts\run-ccld-sample.ps1 -DbPath data\processed\sample.sqlite
.NOTES
Run from the repository root.
#>
param(
    [string]$DbPath = "data\processed\ccld.sqlite"
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
        & $python -m ccld_complaints.cli.populate_sample_db --db-path $DbPath
    }
    else {
        python -m ccld_complaints.cli.populate_sample_db --db-path $DbPath
    }
}
finally {
    $env:PYTHONPATH = $previousPythonPath
}
