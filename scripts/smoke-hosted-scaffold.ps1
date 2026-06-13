<#
.SYNOPSIS
Runs the hosted scaffold smoke check.
.DESCRIPTION
Starts an in-process local scaffold server, checks the health route and placeholder app shell,
then stops it.
.PARAMETER HostName
Local bind host. Defaults to 127.0.0.1.
.PARAMETER Port
Local bind port for the temporary smoke server. Defaults to 0 for an available local port.
.EXAMPLE
.\scripts\smoke-hosted-scaffold.ps1
.NOTES
Run from the repository root.
#>
param(
    [string]$HostName = "127.0.0.1",
    [int]$Port = 0
)

$ErrorActionPreference = "Stop"
$python = Join-Path $PWD ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }
$env:PYTHONPATH = Join-Path $PWD "src"

& $python -m ccld_complaints.hosted_app.smoke --host $HostName --port $Port