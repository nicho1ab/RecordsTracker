<#
.SYNOPSIS
Checks required documentation files.
.DESCRIPTION
Runs the repository documentation presence check.
.PARAMETER None
This script does not accept parameters.
.EXAMPLE
.\scripts\docs.ps1
.NOTES
Run from the repository root.
#>
$ErrorActionPreference = "Stop"
$python = Join-Path $PWD ".venv\Scripts\python.exe"
if (Test-Path $python) { & $python scripts\check_docs.py } else { python scripts\check_docs.py }
