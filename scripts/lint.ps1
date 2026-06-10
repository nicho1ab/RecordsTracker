<#
.SYNOPSIS
Runs linting and type checks.
.DESCRIPTION
Runs ruff and mypy from the local virtual environment when available, otherwise uses commands from PATH.
.PARAMETER None
This script does not accept parameters.
.EXAMPLE
.\scripts\lint.ps1
.NOTES
Run from the repository root.
#>
$ErrorActionPreference = "Stop"
$ruff = Join-Path $PWD ".venv\Scripts\ruff.exe"
$mypy = Join-Path $PWD ".venv\Scripts\mypy.exe"
if (Test-Path $ruff) { & $ruff check . } else { ruff check . }
if (Test-Path $mypy) { & $mypy src } else { mypy src }
