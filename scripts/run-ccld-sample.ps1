<#
.SYNOPSIS
Initializes the sample SQLite database.
.DESCRIPTION
Creates the SQLite database schema for the initial CCLD proof of concept. This is a scaffold command; ingestion implementation is added later.
.PARAMETER None
This script does not accept parameters.
.EXAMPLE
.\scripts\run-ccld-sample.ps1
.NOTES
Run from the repository root.
#>
$ErrorActionPreference = "Stop"
$python = Join-Path $PWD ".venv\Scripts\python.exe"
if (Test-Path $python) { & $python -m ccld_complaints.cli.init_db } else { python -m ccld_complaints.cli.init_db }
Write-Host "SQLite database is at data\processed\ccld.sqlite"
