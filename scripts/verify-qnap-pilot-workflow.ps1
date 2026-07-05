<#
.SYNOPSIS
Checks QNAP pilot workflow configuration, optional running routes, and an
opt-in live smoke-check that starts the stack, probes health and routes, and
stops the stack cleanly.
.DESCRIPTION
Validates the untracked QNAP pilot .env shape, checks required deployment
files, optionally checks docker/docker-compose availability, runs a bounded
Docker Compose configuration check, and optionally probes a running hosted
scaffold base URL. The opt-in -SmokeStart flag performs a full live smoke
check: starts the stack, waits for the app health endpoint, probes standard
routes, then stops the stack cleanly. Logs are collected on failure.

Default mode (no -SmokeStart, no -BaseUrl, no -CheckContainers) is a
config-and-env check only. No containers are started or stopped.

This script does not create secrets, run live CCLD retrieval, call GitHub,
provision cloud resources, or require QNAP-specific application paths.
.PARAMETER EnvFile
Path to the untracked .env file. Defaults to .env.
.PARAMETER ComposeFile
Docker Compose file to validate. Defaults to docker-compose.qnap.yml.
.PARAMETER BaseUrl
Optional running app base URL to probe against an already-running stack,
such as http://<host-name-or-ip>:8000. Not required when using -SmokeStart;
-SmokeStart derives the URL from CCLD_HOSTED_PORT or 127.0.0.1:8000.
.PARAMETER SkipComposeConfig
Skip the Docker Compose config validation step.
.PARAMETER CheckContainers
Also check running Compose services and PostgreSQL readiness. Requires running containers.
.PARAMETER AllowLocalDevDemo
Allow CCLD_RETRIEVAL_DEMO_MODE=mock-success only when explicit local-dev auth and fixture-demo mode are configured.
.PARAMETER SmokeStart
Opt-in live smoke check: starts the Docker Compose stack, waits for the app
health endpoint to respond, probes standard routes, then stops the stack.
Collects logs on failure. Mutually exclusive with -BaseUrl for route probing;
-SmokeStart derives the URL itself. Requires docker and docker compose to be
available on the PATH.
.PARAMETER SkipDockerCheck
Skip the docker and docker compose availability check. Use when docker is
known to be available but not on the PATH where PowerShell resolves commands.
.PARAMETER SmokeWaitSeconds
Maximum seconds to wait for the app health endpoint to respond when using
-SmokeStart. Defaults to 120.
.EXAMPLE
.\scripts\verify-qnap-pilot-workflow.ps1 -EnvFile .env
.EXAMPLE
.\scripts\verify-qnap-pilot-workflow.ps1 -EnvFile .env -BaseUrl http://<host-name-or-ip>:8000
.EXAMPLE
.\scripts\verify-qnap-pilot-workflow.ps1 -EnvFile .env -SmokeStart
.EXAMPLE
.\scripts\verify-qnap-pilot-workflow.ps1 -EnvFile .env -SmokeStart -SmokeWaitSeconds 180
.NOTES
Run from the repository root. Keep real .env files untracked.
-SmokeStart starts and stops real containers. Use on the QNAP Docker host or
a local Docker host, not in CI or on a machine without Docker.
#>
param(
    [string]$EnvFile = ".env",
    [string]$ComposeFile = "docker-compose.qnap.yml",
    [string]$BaseUrl = "",
    [switch]$SkipComposeConfig,
    [switch]$CheckContainers,
    [switch]$AllowLocalDevDemo,
    [switch]$SmokeStart,
    [switch]$SkipDockerCheck,
    [int]$SmokeWaitSeconds = 120
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
    Write-Host "[FAIL] $Message"
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

function Test-SecretLikeExampleValue {
    param([string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) { return $false }
    return $Value -match "ghp_[A-Za-z0-9_]{20,}" -or $Value -match "github_pat_[A-Za-z0-9_]{20,}"
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

function Test-DockerAvailable {
    try {
        $null = & docker --version 2>&1
        if ($LASTEXITCODE -ne 0) { Stop-CheckFail "'docker --version' failed. Confirm Docker is installed and on the PATH." }
    }
    catch {
        Stop-CheckFail "docker command not found. Confirm Docker Desktop or Docker Engine is installed and on the PATH."
    }
    try {
        $null = & docker compose version 2>&1
        if ($LASTEXITCODE -ne 0) { Stop-CheckFail "'docker compose version' failed. Confirm Docker Compose v2 is available." }
    }
    catch {
        Stop-CheckFail "docker compose command not found. Confirm Docker Compose v2 is available."
    }
    Write-CheckPass "docker and docker compose are available."
}

function Wait-AppHealthy {
    param(
        [string]$HealthUrl,
        [int]$MaxWaitSeconds = 120
    )
    $interval = 10
    $attempts = [Math]::Max(1, [int][Math]::Ceiling($MaxWaitSeconds / $interval))
    Write-Host "[SMOKE] Waiting for app health at $HealthUrl (up to ${MaxWaitSeconds}s)..."
    for ($i = 1; $i -le $attempts; $i++) {
        try {
            $resp = Invoke-WebRequest -Uri $HealthUrl -UseBasicParsing -TimeoutSec 8 -ErrorAction Stop
            if ([int]$resp.StatusCode -eq 200) {
                Write-CheckPass "App health endpoint responded 200 after $($i * $interval)s."
                return
            }
        }
        catch { }
        if ($i -lt $attempts) {
            Write-Host "[SMOKE] Waiting... attempt $i/$attempts"
            Start-Sleep -Seconds $interval
        }
    }
    Stop-CheckFail "App health endpoint $HealthUrl did not respond 200 within ${MaxWaitSeconds}s."
}

function Invoke-StandardRouteChecks {
    param([string]$Base)
    Invoke-RouteCheck -Url "$Base/" -AllowedStatus @(200) -RequiredText @("CCLD Records Review")
    Invoke-RouteCheck -Url "$Base/health" -AllowedStatus @(200) -RequiredText @('"status": "ok"')
    Invoke-RouteCheck -Url "$Base/auth/status" -AllowedStatus @(200) -RequiredText @("auth")
    Invoke-RouteCheck -Url "$Base/feedback" -AllowedStatus @(200) -RequiredText @("Tester feedback")
    Invoke-RouteCheck -Url "$Base/ccld/facilities" -AllowedStatus @(200, 401, 503)
    Invoke-RouteCheck -Url "$Base/ccld/records/request" -AllowedStatus @(200, 401, 503)
    Invoke-RouteCheck -Url "$Base/ccld/retrieval/jobs" -AllowedStatus @(200, 401, 503)
    Invoke-RouteCheck -Url "$Base/ccld/retrieval/jobs/detail?job_id=missing-job" -AllowedStatus @(400, 401, 404, 503)
    Invoke-RouteCheck -Url "$Base/ccld/help" -AllowedStatus @(200) -RequiredText @("How CCLD review works")
    Invoke-RouteCheck -Url "$Base/reviewer" -AllowedStatus @(200, 401, 503)
}

$envValues = Read-EnvValues -Path $EnvFile

# Required deployment files check.
$requiredDeployFiles = @("Dockerfile", $ComposeFile, ".env.example")
foreach ($f in $requiredDeployFiles) {
    if (-not (Test-Path -LiteralPath $f)) {
        Stop-CheckFail "Required deployment file '$f' was not found in the current directory. Run from the repository root."
    }
}
Write-CheckPass "Required deployment files (Dockerfile, $ComposeFile, .env.example) are present."

# Docker availability check (unless explicitly skipped).
if (-not $SkipDockerCheck) {
    if ($SmokeStart -or $CheckContainers -or (-not $SkipComposeConfig)) {
        Test-DockerAvailable
    }
}

$requiredKeys = @(
    "CCLD_POSTGRES_DB",
    "CCLD_POSTGRES_USER",
    "CCLD_POSTGRES_PASSWORD",
    "CCLD_HOSTED_PORT",
    "CCLD_HOSTED_PAGE_DATA_MODE",
    "CCLD_HOSTED_TESTER_AUTH_MODE",
    "CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH",
    "CCLD_RETRIEVAL_ENABLED"
)
foreach ($key in $requiredKeys) { Test-PilotEnvValue -Values $envValues -Key $key }
Write-CheckPass "Required QNAP pilot env keys are present."

$pageDataMode = Get-EnvValue -Values $envValues -Key "CCLD_HOSTED_PAGE_DATA_MODE"
$authMode = Get-EnvValue -Values $envValues -Key "CCLD_HOSTED_TESTER_AUTH_MODE"
$localDevAuth = Get-EnvValue -Values $envValues -Key "CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH"
$retrievalDemoMode = Get-EnvValue -Values $envValues -Key "CCLD_RETRIEVAL_DEMO_MODE"
$retrievalEnabled = Get-EnvValue -Values $envValues -Key "CCLD_RETRIEVAL_ENABLED"
$retrievalRawDir = Get-EnvValue -Values $envValues -Key "CCLD_RETRIEVAL_RAW_DIR"
$githubFeedbackRepo = Get-EnvValue -Values $envValues -Key "GITHUB_FEEDBACK_REPO"
$githubFeedbackToken = Get-EnvValue -Values $envValues -Key "GITHUB_FEEDBACK_TOKEN"

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
        Stop-CheckFail "QNAP pilot mode should use production auth mode; local-dev auth disabled is required."
    }
    Write-CheckPass "QNAP pilot mode keeps PostgreSQL page data and production auth boundary defaults."
}

if ($retrievalEnabled -eq "enabled") {
    if ([string]::IsNullOrWhiteSpace($retrievalRawDir)) {
        Write-Host "CCLD_RETRIEVAL_ENABLED=enabled requires CCLD_RETRIEVAL_RAW_DIR to preserve raw artifacts."
        Stop-CheckFail "CCLD_RETRIEVAL_ENABLED=enabled requires CCLD_RETRIEVAL_RAW_DIR to preserve raw artifacts."
    }
    Test-NoHostSpecificPath -Label "CCLD_RETRIEVAL_RAW_DIR" -Value $retrievalRawDir
    Write-CheckPass "Retrieval raw storage path is configurable and container-portable."
    Write-CheckPass "Controlled retrieval is enabled with a configured raw artifact path."
}
else {
    if (-not [string]::IsNullOrWhiteSpace($retrievalRawDir)) {
        Test-NoHostSpecificPath -Label "CCLD_RETRIEVAL_RAW_DIR" -Value $retrievalRawDir
        Write-CheckPass "Retrieval raw storage path is configurable and container-portable."
    }
    Write-CheckPass "Controlled retrieval is intentionally disabled unless CCLD_RETRIEVAL_ENABLED=enabled."
}

if ([string]::IsNullOrWhiteSpace($githubFeedbackRepo) -and [string]::IsNullOrWhiteSpace($githubFeedbackToken)) {
    Write-CheckPass "GitHub feedback intake is intentionally disabled because repo and token are blank."
}
elseif ([string]::IsNullOrWhiteSpace($githubFeedbackRepo) -or [string]::IsNullOrWhiteSpace($githubFeedbackToken)) {
    Stop-CheckFail "GitHub feedback must be either intentionally disabled with both repo/token blank or configured with both values set."
}
else {
    Write-CheckPass "GitHub feedback intake has both repo and token values present."
}

foreach ($key in @("CCLD_POSTGRES_PASSWORD", "CCLD_HOSTED_TESTER_OIDC_ISSUER", "CCLD_HOSTED_TESTER_OIDC_CLIENT_ID", "GITHUB_FEEDBACK_REPO", "GITHUB_FEEDBACK_TOKEN")) {
    $value = Get-EnvValue -Values $envValues -Key $key
    if (Test-SecretLikeExampleValue -Value $value) {
        Stop-CheckFail "$key looks like a committed real secret or token. Keep real values only in untracked host configuration."
    }
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
    Invoke-StandardRouteChecks -Base $BaseUrl.TrimEnd("/")
}

if ($SmokeStart) {
    # Derive base URL from env port if not explicitly provided.
    $smokeBase = if (-not [string]::IsNullOrWhiteSpace($BaseUrl)) {
        $BaseUrl.TrimEnd("/")
    }
    else {
        $smokePort = Get-EnvValue -Values $envValues -Key "CCLD_HOSTED_PORT"
        if ([string]::IsNullOrWhiteSpace($smokePort)) { $smokePort = "8000" }
        "http://127.0.0.1:$smokePort"
    }
    Write-Host "[SMOKE] Starting Docker Compose stack. This will start real containers."
    Write-Host "[SMOKE] Base URL: $smokeBase"
    $smokeStarted = $false
    try {
        & docker compose -f $ComposeFile --env-file $EnvFile up --build -d
        if ($LASTEXITCODE -ne 0) { Stop-CheckFail "docker compose up failed." }
        $smokeStarted = $true
        Write-CheckPass "Docker Compose stack started."

        Wait-AppHealthy -HealthUrl "$smokeBase/health" -MaxWaitSeconds $SmokeWaitSeconds

        # Container and migration state checks.
        & docker compose -f $ComposeFile --env-file $EnvFile ps
        & docker compose -f $ComposeFile --env-file $EnvFile exec -T postgres pg_isready `
            -U (Get-EnvValue -Values $envValues -Key "CCLD_POSTGRES_USER") `
            -d (Get-EnvValue -Values $envValues -Key "CCLD_POSTGRES_DB") | Out-Null
        if ($LASTEXITCODE -ne 0) { Stop-CheckFail "PostgreSQL readiness check failed during smoke start." }
        Write-CheckPass "PostgreSQL is ready."

        & docker compose -f $ComposeFile --env-file $EnvFile run --rm app alembic current | Out-Null
        if ($LASTEXITCODE -ne 0) { Stop-CheckFail "Alembic current check failed during smoke start." }
        Write-CheckPass "Alembic migrations are current."

        # Standard route probes.
        Invoke-StandardRouteChecks -Base $smokeBase

        Write-CheckPass "Smoke start route probes passed."
    }
    catch {
        Write-CheckWarn "Smoke check encountered a failure. Collecting recent logs..."
        if ($smokeStarted) {
            try {
                & docker compose -f $ComposeFile --env-file $EnvFile logs --no-color --tail 60 2>&1 | Write-Host
            }
            catch {
                Write-CheckWarn "Could not collect logs: $_"
            }
        }
        throw
    }
    finally {
        if ($smokeStarted) {
            Write-Host "[SMOKE] Stopping Docker Compose stack..."
            try {
                & docker compose -f $ComposeFile --env-file $EnvFile down
                Write-CheckPass "Docker Compose stack stopped cleanly."
            }
            catch {
                Write-CheckWarn "docker compose down encountered an issue: $_"
            }
        }
    }
}

Write-CheckPass "QNAP pilot workflow checks completed."
