<#
.SYNOPSIS
Profiles local ignored public-source CSV files.
.DESCRIPTION
Runs the local CSV profiler against data\raw\source-profiling by default and writes ignored JSON, CSV, facility source gap-assessment, and log outputs under data\processed\source-profiling and data\logs. This script does not import data, modify raw files, create schemas, add connectors, contact the internet, or require cloud services.
.PARAMETER SourceRoot
Local source-profiling folder to scan recursively for CSV files.
.PARAMETER OutputDir
Ignored output folder for JSON and CSV profile summaries.
.PARAMETER LogPath
Ignored log file path for the profiling run.
.EXAMPLE
.\scripts\profile-public-source-csvs.ps1
.NOTES
Run from the repository root.
#>
param(
    [string]$SourceRoot = "data\raw\source-profiling",
    [string]$OutputDir = "data\processed\source-profiling",
    [string]$LogPath = "data\logs\source-profiling.log"
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
        & $python scripts\profile_public_source_csvs.py --source-root $SourceRoot --output-dir $OutputDir --log-path $LogPath
    }
    else {
        python scripts\profile_public_source_csvs.py --source-root $SourceRoot --output-dir $OutputDir --log-path $LogPath
    }
}
finally {
    $env:PYTHONPATH = $previousPythonPath
}
