<#
.SYNOPSIS
Runs the local hosted tester MVP scaffold.
.DESCRIPTION
Starts the Python standard-library hosted scaffold on the Windows development workstation.
This does not start authentication, reviewer workflows, imports, schemas, cloud hosting, or
deployment.
.PARAMETER HostName
Local bind host. Defaults to 127.0.0.1.
.PARAMETER Port
Local bind port. Defaults to 8000.
.EXAMPLE
.\scripts\run-hosted-scaffold.ps1 -Port 8000
.NOTES
Run from the repository root.
#>
param(
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$python = Join-Path $PWD ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }
$env:PYTHONPATH = Join-Path $PWD "src"
if (-not $env:CCLD_HOSTED_TESTER_AUTH_MODE) { $env:CCLD_HOSTED_TESTER_AUTH_MODE = "local-dev" }
if (-not $env:CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH) { $env:CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH = "enabled" }

Write-Host "Starting local hosted tester MVP scaffold at http://${HostName}:$Port/"
Write-Host "Scaffold only: explicit local-dev tester auth mode; no real OIDC flow or production auth."
& $python -m ccld_complaints.hosted_app --host $HostName --port $Port