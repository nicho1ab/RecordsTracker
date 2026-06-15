<#
.SYNOPSIS
Checks QNAP pilot workflow configuration and optional running routes.
.DESCRIPTION
Validates the untracked QNAP pilot .env shape, runs a bounded Docker Compose
configuration check, and optionally probes a running hosted scaffold base URL.
This script does not create secrets, start containers, run live CCLD retrieval,
call GitHub, provision cloud resources, or require QNAP-specific application
paths.
.PARAMETER EnvFile
Path to the untracked .env file. Defaults to .env.
.PARAMETER ComposeFile
Docker Compose file to validate. Defaults to docker-compose.qnap.yml.
.PARAMETER BaseUrl
Optional running app base URL to probe, such as http://<host-name-or-ip>:8000.
.PARAMETER SkipComposeConfig
Skip the Docker Compose config validation step.
.PARAMETER CheckContainers
Also check running Compose services and PostgreSQL readiness. Requires running containers.
.PARAMETER AllowLocalDevDemo
Allow CCLD_RETRIEVAL_DEMO_MODE=mock-success only when explicit local-dev auth and fixture-demo mode are configured.
.EXAMPLE
.\scripts\verify-qnap-pilot-workflow.ps1 -EnvFile .env
.EXAMPLE
.\scripts\verify-qnap-pilot-workflow.ps1 -EnvFile .env -BaseUrl http://<host-name-or-ip>:8000
.NOTES
Run from the repository root. Keep real .env files untracked.
#>
param(
    [string]$EnvFile = ".env",
    [string]$ComposeFile = "docker-compose.qnap.yml",
    [string]$BaseUrl = "",
    [switch]$SkipComposeConfig,
    [switch]$CheckContainers,
    [switch]$AllowLocalDevDemo
)

$ErrorActionPreference = "Stop"

function Write-CheckPass {
    param([string]$Message)
    Write-Host "[PASS] $Message"
}

function Write-CheckWarn {
    param([string]$Message)
    Write-Warning $Message
}

function Stop-CheckFail {
    param([string]$Message)
    throw "[FAIL] $Message"
}

function Read-EnvValues {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        Stop-CheckFail "Env file '$Path' was not found. Copy .env.example to .env and replace placeholders on the deployment host."
    }
    $values = @{}
    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) { continue }
        $separator = $trimmed.IndexOf("=")
        if ($separator -le 0) { continue }
        $key = $trimmed.Substring(0, $separator).Trim()
        $value = $trimmed.Substring($separator + 1).Trim()
        $values[$key] = $value
    }
    return $values
}

function Test-PilotEnvValue {
    param(
        [hashtable]$Values,
        [string]$Key
    )
    if (-not $Values.ContainsKey($Key) -or [string]::IsNullOrWhiteSpace([string]$Values[$Key])) {
        Stop-CheckFail "Required pilot setting '$Key' is missing or empty in the env file."
    }
}

function Get-EnvValue {
    param(
        [hashtable]$Values,
        [string]$Key
    )
    if ($Values.ContainsKey($Key)) { return [string]$Values[$Key] }
    return ""
}

function Test-PlaceholderValue {
    param([string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) { return $false }
    $lower = $Value.ToLowerInvariant()
    return $lower.Contains("placeholder") -or $lower.Contains("replace-with") -or $Value.Contains("<") -or $Value.Contains(">")
}

function Test-NoHostSpecificPath {
    param(
        [string]$Label,
        [string]$Value
    )
    $lower = $Value.ToLowerInvariant()
    if ($Value.Contains("\") -or $lower.Contains("/share/") -or $lower.Contains("/volume")) {
        Stop-CheckFail "$Label must be a portable container path or environment value, not a QNAP/Windows host path."
    }
}

function Invoke-RouteCheck {
    param(
        [string]$Url,
        [int[]]$AllowedStatus,
        [string[]]$RequiredText = @()
    )
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 10 -ErrorAction Stop
        $status = [int]$response.StatusCode
        $content = [string]$response.Content
    }
    catch {
        if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
            $status = [int]$_.Exception.Response.StatusCode
            $reader = [System.IO.StreamReader]::new($_.Exception.Response.GetResponseStream())
            $content = $reader.ReadToEnd()
            $reader.Dispose()
        }
        else {
            $routeErrorMessage = $_.Exception.Message
            Stop-CheckFail ("Route check failed for " + $Url + " - " + $routeErrorMessage)
        }
    }
    if ($AllowedStatus -notcontains $status) {
        Stop-CheckFail "Route $Url returned HTTP $status; expected one of $($AllowedStatus -join ', ')."
    }
    foreach ($marker in $RequiredText) {
        if (-not $content.Contains($marker)) {
            Stop-CheckFail "Route $Url did not include expected text '$marker'."
        }
    }
    foreach ($marker in @("provider_subject", "provider-subject", "provider_issuer", "provider-issuer", "client_secret", "client-secret")) {
        if ($content.ToLowerInvariant().Contains($marker)) {
            Stop-CheckFail "Route $Url rendered private marker '$marker'."
        }
    }
    Write-CheckPass "Route $Url returned HTTP $status."
}

$envValues = Read-EnvValues -Path $EnvFile

$requiredKeys = @(
    "CCLD_POSTGRES_DB",
    "CCLD_POSTGRES_USER",
    "CCLD_POSTGRES_PASSWORD",
    "CCLD_HOSTED_PORT",
    "CCLD_HOSTED_PAGE_DATA_MODE",
    "CCLD_HOSTED_TESTER_AUTH_MODE",
    "CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH",
    "CCLD_RETRIEVAL_ENABLED",
    "CCLD_RETRIEVAL_RAW_DIR"
)
foreach ($key in $requiredKeys) { Test-PilotEnvValue -Values $envValues -Key $key }
Write-CheckPass "Required QNAP pilot env keys are present."

$pageDataMode = Get-EnvValue -Values $envValues -Key "CCLD_HOSTED_PAGE_DATA_MODE"
$authMode = Get-EnvValue -Values $envValues -Key "CCLD_HOSTED_TESTER_AUTH_MODE"
$localDevAuth = Get-EnvValue -Values $envValues -Key "CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH"
$retrievalDemoMode = Get-EnvValue -Values $envValues -Key "CCLD_RETRIEVAL_DEMO_MODE"
$retrievalRawDir = Get-EnvValue -Values $envValues -Key "CCLD_RETRIEVAL_RAW_DIR"

if ($retrievalDemoMode -eq "mock-success") {
    if (-not $AllowLocalDevDemo) {
        Stop-CheckFail "CCLD_RETRIEVAL_DEMO_MODE=mock-success requires -AllowLocalDevDemo and must not be used for QNAP/pilot-like production validation."
    }
    if ($authMode -ne "local-dev" -or $localDevAuth -ne "enabled" -or $pageDataMode -ne "fixture-demo") {
        Stop-CheckFail "mock-success demo mode requires local-dev auth, local-dev auth enabled, and fixture-demo page data."
    }
    Write-CheckWarn "mock-success demo mode is enabled for local-dev scaffold validation only."
}
else {
    if ($pageDataMode -ne "postgres") {
        Stop-CheckFail "QNAP pilot mode should use CCLD_HOSTED_PAGE_DATA_MODE=postgres. Use fixture-demo only for explicit local demos."
    }
    if ($authMode -ne "production" -or $localDevAuth -ne "disabled") {
        Stop-CheckFail "QNAP pilot mode should use production auth mode with local-dev auth disabled."
    }
    Write-CheckPass "QNAP pilot mode keeps PostgreSQL page data and production auth boundary defaults."
}

Test-NoHostSpecificPath -Label "CCLD_RETRIEVAL_RAW_DIR" -Value $retrievalRawDir
Write-CheckPass "Retrieval raw storage path is configurable and container-portable."

foreach ($key in @("CCLD_POSTGRES_PASSWORD", "CCLD_HOSTED_TESTER_OIDC_ISSUER", "CCLD_HOSTED_TESTER_OIDC_CLIENT_ID", "GITHUB_FEEDBACK_REPO", "GITHUB_FEEDBACK_TOKEN")) {
    $value = Get-EnvValue -Values $envValues -Key $key
    if (Test-PlaceholderValue -Value $value) {
        Write-CheckWarn "$key still looks like a placeholder. Replace it before inviting external testers or enabling that integration."
    }
}

if (-not $SkipComposeConfig) {
    if (-not (Test-Path -LiteralPath $ComposeFile)) {
        Stop-CheckFail "Compose file '$ComposeFile' was not found."
    }
    & docker compose -f $ComposeFile --env-file $EnvFile config | Out-Null
    if ($LASTEXITCODE -ne 0) { Stop-CheckFail "Docker Compose config validation failed." }
    Write-CheckPass "Docker Compose config validates with the selected env file."
}

if ($CheckContainers) {
    & docker compose -f $ComposeFile --env-file $EnvFile ps | Out-Null
    if ($LASTEXITCODE -ne 0) { Stop-CheckFail "Docker Compose services could not be listed." }
    & docker compose -f $ComposeFile --env-file $EnvFile exec -T postgres pg_isready -U (Get-EnvValue -Values $envValues -Key "CCLD_POSTGRES_USER") -d (Get-EnvValue -Values $envValues -Key "CCLD_POSTGRES_DB") | Out-Null
    if ($LASTEXITCODE -ne 0) { Stop-CheckFail "PostgreSQL readiness check failed." }
    & docker compose -f $ComposeFile --env-file $EnvFile run --rm app alembic current | Out-Null
    if ($LASTEXITCODE -ne 0) { Stop-CheckFail "Alembic current check failed." }
    Write-CheckPass "Running containers, PostgreSQL readiness, and Alembic current checks passed."
}

if (-not [string]::IsNullOrWhiteSpace($BaseUrl)) {
    $base = $BaseUrl.TrimEnd("/")
    Invoke-RouteCheck -Url "$base/" -AllowedStatus @(200) -RequiredText @("CCLD Records Review")
    Invoke-RouteCheck -Url "$base/health" -AllowedStatus @(200) -RequiredText @('"status": "ok"')
    Invoke-RouteCheck -Url "$base/auth/status" -AllowedStatus @(200) -RequiredText @("auth")
    Invoke-RouteCheck -Url "$base/feedback" -AllowedStatus @(200) -RequiredText @("Tester feedback")
    Invoke-RouteCheck -Url "$base/ccld/facilities" -AllowedStatus @(200, 401, 503)
    Invoke-RouteCheck -Url "$base/ccld/records/request" -AllowedStatus @(200, 401, 503)
    Invoke-RouteCheck -Url "$base/ccld/retrieval/jobs" -AllowedStatus @(200, 401, 503)
    Invoke-RouteCheck -Url "$base/ccld/retrieval/jobs/detail?job_id=missing-job" -AllowedStatus @(400, 401, 404, 503)
    Invoke-RouteCheck -Url "$base/ccld/help" -AllowedStatus @(200) -RequiredText @("How CCLD review works")
    Invoke-RouteCheck -Url "$base/reviewer" -AllowedStatus @(200, 401, 503)
}

Write-CheckPass "QNAP pilot workflow checks completed."
