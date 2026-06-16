<#
.SYNOPSIS
Runs the local hosted complaint retrieval path against live public CCLD.
.DESCRIPTION
Starts the Python standard-library hosted scaffold with explicit local-dev auth,
fixture/demo page data, controlled retrieval enabled, live public CCLD retrieval,
and ignored local raw source storage. This command makes live public CCLD web
requests from the server when a browser submits a controlled retrieval job.
.PARAMETER HostName
Local bind host. Defaults to 127.0.0.1.
.PARAMETER Port
Local bind port. Defaults to 8000.
.PARAMETER RawStorageDir
Ignored local raw storage path for live retrieval artifacts. Defaults to
 data\raw\ccld\retrieval-live.
.EXAMPLE
.\scripts\run-hosted-complaint-retrieval-live.ps1 -Port 8000
.NOTES
Run from the repository root. The CCLD public portal remains the source of record.
Absence of imported records is not proof that no complaints exist.
#>
param(
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8000,
    [string]$RawStorageDir = "data\raw\ccld\retrieval-live"
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
$env:CCLD_RETRIEVAL_DEMO_MODE = ""
if (-not $env:CCLD_RETRIEVAL_MAX_DATE_RANGE_DAYS) { $env:CCLD_RETRIEVAL_MAX_DATE_RANGE_DAYS = "30" }

$baseUrl = "http://${HostName}:$Port"
Write-Host "Mode: Live public CCLD retrieval"
Write-Host "Local pilot runtime: $baseUrl/"
Write-Host "Open: $baseUrl/"
Write-Host "Open: $baseUrl/ccld/records/request"
Write-Host "Open: $baseUrl/ccld/retrieval/jobs"
Write-Host "Open: $baseUrl/reviewer"
Write-Host "Open: $baseUrl/ccld/help"
Write-Host "Open: $baseUrl/feedback"
Write-Host "Public CCLD HTTP requests will be made only after a browser submits a controlled retrieval job."
Write-Host "CCLD public portal remains the source of record."
Write-Host "Absence of imported records is not proof that no complaints exist."
Write-Host "Server-side live raw source storage is configured under an ignored local data/raw path."

& $python -m ccld_complaints.hosted_app --host $HostName --port $Port
