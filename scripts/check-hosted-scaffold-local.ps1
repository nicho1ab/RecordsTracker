<#
.SYNOPSIS
Checks local prerequisites for the hosted tester MVP scaffold.
.DESCRIPTION
Verifies Python and development-tool availability for local scaffold work on a Windows
development workstation. This script does not install software, does not require admin rights,
and does not require Node, Docker, QNAP, Azure, AWS, cloud resources, or a public URL.
.EXAMPLE
.\scripts\check-hosted-scaffold-local.ps1
.NOTES
Run from the repository root.
#>

$ErrorActionPreference = "Stop"
$python = Join-Path $PWD ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }
$env:PYTHONPATH = Join-Path $PWD "src"

& $python -m ccld_complaints.hosted_app.local_check