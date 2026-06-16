<#
.SYNOPSIS
Runs the local hosted complaint retrieval demo.
.DESCRIPTION
Starts the Python standard-library hosted scaffold with explicit local-dev auth,
fixture/demo page data, controlled retrieval enabled, fixture-backed mock-success
retrieval, and ignored local raw source storage. This command is for local demo
validation only and does not prove CCLD public-source completeness.
.PARAMETER HostName
Local bind host. Defaults to 127.0.0.1.
.PARAMETER Port
Local bind port. Defaults to 8000.
.PARAMETER RawStorageDir
Ignored local raw storage path for demo retrieval artifacts. Defaults to
 data\raw\ccld\retrieval-demo.
.EXAMPLE
.\scripts\run-hosted-complaint-retrieval-demo.ps1 -Port 8000
.NOTES
Run from the repository root.
#>
param(
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8000,
    [string]$RawStorageDir = "data\raw\ccld\retrieval-demo"
)

$ErrorActionPreference = "Stop"
$python = Join-Path $PWD ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }
$env:PYTHONPATH = Join-Path $PWD "src"

$resolvedRawStorageDir = Join-Path $PWD $RawStorageDir
New-Item -ItemType Directory -Force -Path $resolvedRawStorageDir | Out-Null

$env:CCLD_HOSTED_TESTER_AUTH_MODE = "local-dev"
$env:CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH = "enabled"
$env:CCLD_HOSTED_PAGE_DATA_MODE = "fixture-demo"
$env:CCLD_RETRIEVAL_ENABLED = "enabled"
$env:CCLD_RETRIEVAL_RAW_DIR = $resolvedRawStorageDir
$env:CCLD_RETRIEVAL_DEMO_MODE = "mock-success"
if (-not $env:CCLD_RETRIEVAL_MAX_DATE_RANGE_DAYS) { $env:CCLD_RETRIEVAL_MAX_DATE_RANGE_DAYS = "30" }

$baseUrl = "http://${HostName}:$Port"
Write-Host "Fixture/mock demo mode"
Write-Host "Local pilot runtime: $baseUrl/"
Write-Host "Open: $baseUrl/"
Write-Host "Open: $baseUrl/ccld/records/request"
Write-Host "Open: $baseUrl/ccld/retrieval/jobs"
Write-Host "Open: $baseUrl/reviewer"
Write-Host "Open: $baseUrl/ccld/help"
Write-Host "Open: $baseUrl/feedback"
Write-Host "Fixture/mock demo mode uses committed fixtures and does not make live CCLD calls."
Write-Host "CCLD public portal remains the source of record for real public records."
Write-Host "Server-side demo raw source storage is configured under an ignored local data/raw path."

& $python -m ccld_complaints.hosted_app --host $HostName --port $Port
