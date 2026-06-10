<#
.SYNOPSIS
Runs the project test suite.
.DESCRIPTION
Runs pytest from the local virtual environment when available, otherwise uses pytest from PATH.
.PARAMETER None
This script does not accept parameters.
.EXAMPLE
.\scripts\test.ps1
.NOTES
Run from the repository root.
#>
$ErrorActionPreference = "Stop"
$pytest = Join-Path $PWD ".venv\Scripts\pytest.exe"
if (Test-Path $pytest) { & $pytest } else { pytest }
