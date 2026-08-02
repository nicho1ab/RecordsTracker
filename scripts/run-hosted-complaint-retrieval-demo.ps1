<#
.SYNOPSIS
Runs the local hosted complaint retrieval demo.
.DESCRIPTION
Starts the Python standard-library hosted scaffold with explicit local-dev auth,
fixture/demo page data, controlled retrieval enabled, fixture-backed mock-success
retrieval, and ignored local raw source storage. This command is for local demo
validation with committed fixtures.
.PARAMETER HostName
Local bind host. Defaults to 127.0.0.1.
.PARAMETER Port
Local bind port. Defaults to 8000.
.PARAMETER RawStorageDir
Ignored local raw storage path for demo retrieval artifacts. Defaults to
 data\raw\ccld\retrieval-demo.
.PARAMETER PythonExecutable
Verified Python executable to use. Required when the current worktree does not
contain its own virtual environment.
.PARAMETER Issue642Evidence
Enable the local-only synthetic pagination corpus used exclusively by the
Issue #642 operated evidence capture and load the tracked tiny public-source
Licensing fixture.
.PARAMETER Issue642LicensingSourceUnavailable
Launch the Issue #642 fixture with an intentionally absent Licensing source.
This is a separate local launch condition and does not add a UI query switch.
.EXAMPLE
.\scripts\run-hosted-complaint-retrieval-demo.ps1 -Port 8000
.NOTES
Run from the repository root.
#>
param(
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8000,
    [string]$RawStorageDir = "data\raw\ccld\retrieval-demo",
    [string]$PythonExecutable = "",

    [switch]$Issue642Evidence,

    [switch]$Issue642LicensingSourceUnavailable
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($PythonExecutable)) {
    $PythonExecutable = Join-Path $PWD ".venv\Scripts\python.exe"
}
if (-not (Test-Path -LiteralPath $PythonExecutable -PathType Leaf)) {
    throw "Verified Python executable not found: $PythonExecutable. Supply -PythonExecutable when running from a secondary worktree."
}
$python = (Resolve-Path -LiteralPath $PythonExecutable).Path
$env:PYTHONPATH = Join-Path $PWD "src"

$resolvedRawStorageDir = Join-Path $PWD $RawStorageDir
New-Item -ItemType Directory -Force -Path $resolvedRawStorageDir | Out-Null

$env:CCLD_HOSTED_TESTER_AUTH_MODE = "local-dev"
$env:CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH = "enabled"
$env:CCLD_HOSTED_PAGE_DATA_MODE = "fixture-demo"
$env:CCLD_RETRIEVAL_ENABLED = "enabled"
$env:CCLD_RETRIEVAL_RAW_DIR = $resolvedRawStorageDir
$env:CCLD_RETRIEVAL_DEMO_MODE = "mock-success"
if ($Issue642Evidence -or $Issue642LicensingSourceUnavailable) {
    $env:CCLD_HOSTED_ISSUE642_EVIDENCE_MODE = "enabled"
}
if ($Issue642Evidence -and -not $Issue642LicensingSourceUnavailable) {
    $issue642LicensingFixture = Join-Path $PWD "tests\fixtures\public_source_facilities\ccld_program_facilities_tiny.csv"
    if (-not (Test-Path -LiteralPath $issue642LicensingFixture -PathType Leaf)) {
        throw "Tracked Issue #642 Licensing fixture is unavailable."
    }
    $env:CCLD_FACILITY_REVIEW_SIGNALS_CSVS = (Resolve-Path -LiteralPath $issue642LicensingFixture).Path
}
elseif ($Issue642LicensingSourceUnavailable) {
    $unavailableLicensingFixture = Join-Path $PWD "tests\fixtures\public_source_facilities\issue642-source-unavailable.csv"
    if (Test-Path -LiteralPath $unavailableLicensingFixture) {
        throw "Issue #642 unavailable-source launch marker unexpectedly exists."
    }
    $env:CCLD_FACILITY_REVIEW_SIGNALS_CSVS = $unavailableLicensingFixture
}
if (-not $env:CCLD_RETRIEVAL_MAX_DATE_RANGE_DAYS) { $env:CCLD_RETRIEVAL_MAX_DATE_RANGE_DAYS = "30" }

$baseUrl = "http://${HostName}:$Port"
Write-Host "Fixture/mock demo mode"
if ($Issue642Evidence -and -not $Issue642LicensingSourceUnavailable) { Write-Host "Issue #642 Licensing source state: tracked tiny public-source fixture" }
if ($Issue642LicensingSourceUnavailable) { Write-Host "Issue #642 Licensing source state: unavailable" }
Write-Host "Local pilot runtime: $baseUrl/"
Write-Host "Open: $baseUrl/"
Write-Host "Open: $baseUrl/ccld/records/request"
Write-Host "Open: $baseUrl/ccld/retrieval/jobs"
Write-Host "Open: $baseUrl/reviewer"
Write-Host "Open: $baseUrl/ccld/help"
Write-Host "Open: $baseUrl/feedback"
Write-Host "Fixture/mock demo mode uses committed fixtures and does not make live CCLD calls."
Write-Host "Server-side demo raw source storage is configured under an ignored local data/raw path."

& $python -m ccld_complaints.hosted_app --host $HostName --port $Port
