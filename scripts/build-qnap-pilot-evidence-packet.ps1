<#
.SYNOPSIS
Builds a redacted local QNAP pilot evidence packet.
.DESCRIPTION
Runs the existing QNAP verifier, seeded import evidence, and route evidence
commands, redacts their captured text output, and writes a local Markdown packet
for operator review. This script is read-only with respect to the app and data
stores: it does not mutate the app database, run imports, run retrieval, send
feedback, call GitHub, call live CCLD, execute POST requests, or create public
reports, product exports, audit exports, or certifications.
.PARAMETER EnvFile
Path to the untracked env file. Defaults to .env.
.PARAMETER BaseUrl
Hosted app base URL for route evidence. Defaults to http://127.0.0.1:8000.
.PARAMETER OutputDir
Ignored local output directory. Defaults to data/processed/qnap-pilot-evidence.
.PARAMETER SkipDatabaseCheck
Pass through to the seeded import evidence command for template validation.
.PARAMETER AllowRouteUnavailable
Pass through to the route evidence command for safe placeholder validation.
.PARAMETER FeedbackDecision
Operator decision for feedback configuration. Keep it short and non-secret.
.PARAMETER RetrievalDecision
Operator decision for controlled retrieval configuration. Keep it short and non-secret.
.PARAMETER AuthDecision
Operator decision for auth readiness. Keep it short and non-secret.
.PARAMETER TesterInvitationDecision
Operator decision for tester invitation/access control. Keep it short and non-secret.
.PARAMETER PostgresBackupPlan
Operator PostgreSQL backup plan summary. Do not include host paths or private URLs.
.PARAMETER RawArtifactBackupPlan
Operator raw artifact backup plan summary. Do not include host paths or private URLs.
.PARAMETER KnownLimitationsAcknowledged
Record that known limitations were reviewed and acknowledged by the operator.
.EXAMPLE
.\scripts\build-qnap-pilot-evidence-packet.ps1 -EnvFile .env
.EXAMPLE
.\scripts\build-qnap-pilot-evidence-packet.ps1 -EnvFile .env.example -SkipDatabaseCheck -AllowRouteUnavailable -BaseUrl http://127.0.0.1:9
.NOTES
Run from the repository root. Generated packets stay local and must not be committed.
#>
param(
    [string]$EnvFile = ".env",
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$OutputDir = "data/processed/qnap-pilot-evidence",
    [switch]$SkipDatabaseCheck,
    [switch]$AllowRouteUnavailable,
    [string]$FeedbackDecision = "not recorded",
    [string]$RetrievalDecision = "not recorded",
    [string]$AuthDecision = "not recorded",
    [string]$TesterInvitationDecision = "not recorded",
    [string]$PostgresBackupPlan = "not recorded",
    [string]$RawArtifactBackupPlan = "not recorded",
    [switch]$KnownLimitationsAcknowledged
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$verifierScript = Join-Path $PSScriptRoot "verify-qnap-pilot-workflow.ps1"
$seededEvidenceScript = Join-Path $PSScriptRoot "summarize-qnap-pilot-seeded-import-evidence.ps1"
$routeEvidenceScript = Join-Path $PSScriptRoot "summarize-qnap-pilot-route-evidence.ps1"

function Stop-PacketFail {
    param([string]$Message)
    throw "[FAIL] $Message"
}

function Get-FullPath {
    param([string]$Path)
    if ([System.IO.Path]::IsPathRooted($Path)) {
        return [System.IO.Path]::GetFullPath($Path)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $repoRoot $Path))
}

function Test-IsUnderPath {
    param(
        [string]$Path,
        [string]$Parent
    )
    $fullPath = (Get-FullPath -Path $Path).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
    $fullParent = (Get-FullPath -Path $Parent).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
    return $fullPath.Equals($fullParent, [System.StringComparison]::OrdinalIgnoreCase) -or
        $fullPath.StartsWith($fullParent + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase) -or
        $fullPath.StartsWith($fullParent + [System.IO.Path]::AltDirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)
}

function Get-RelativePathForDisplay {
    param([string]$Path)
    $fullPath = Get-FullPath -Path $Path
    $relative = [System.IO.Path]::GetRelativePath($repoRoot, $fullPath)
    return ($relative -replace "\\", "/")
}

function Get-SafeFileNameForDisplay {
    param([string]$Path)
    return [System.IO.Path]::GetFileName($Path)
}

function Test-PrivateMarkerValue {
    param([string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) { return $false }
    $patterns = @(
        "ghp_[A-Za-z0-9_]{20,}",
        "github_pat_[A-Za-z0-9_]{20,}",
        "(?i)bearer\s+[A-Za-z0-9._-]+",
        "(?i)(token|password|secret|client[_-]?secret)\s*[:=]",
        "(?i)connection\s*string",
        "(?i)tenant[_ -]?id",
        "(?i)callback\s*(url|secret)",
        "https?://",
        "[A-Za-z]:\\",
        "(?i)/share/",
        "(?i)/volume"
    )
    foreach ($pattern in $patterns) {
        if ($Value -match $pattern) { return $true }
    }
    return $false
}

function Assert-SafeOperatorInput {
    param(
        [string]$Label,
        [string]$Value
    )
    if (Test-PrivateMarkerValue -Value $Value) {
        Stop-PacketFail "$Label contains a secret-like or private marker. Replace it with a short non-secret decision summary."
    }
}

function Redact-EvidenceText {
    param([string]$Text)
    if ([string]::IsNullOrEmpty($Text)) { return "" }

    $redacted = $Text
    $redacted = $redacted -replace "ghp_[A-Za-z0-9_]{20,}", "[REDACTED_GITHUB_TOKEN]"
    $redacted = $redacted -replace "github_pat_[A-Za-z0-9_]{20,}", "[REDACTED_GITHUB_TOKEN]"
    $redacted = $redacted -replace "(?i)(authorization:\s*bearer\s+)[^\s]+", "`${1}[REDACTED]"
    $redacted = $redacted -replace "(?i)(set-cookie:\s*)[^\r\n]+", "`${1}[REDACTED]"
    $redacted = $redacted -replace "(?i)(cookie=)[^\s;]+", "`${1}[REDACTED]"
    $redacted = $redacted -replace "(?i)(token|password|secret|client[_-]?secret)\s*[:=]\s*[^\s\r\n]+", "`${1}=[REDACTED]"
    $redacted = $redacted -replace "(?i)(connection\s*string|connection_string)\s*[:=]\s*[^\r\n]+", "`${1}=[REDACTED]"
    $redacted = $redacted -replace "postgresql(\+psycopg)?://[^\s\)\]\""']+", "postgresql://[REDACTED]"
    $redacted = $redacted -replace "https?://(?!127\.0\.0\.1(?::\d+)?(?:/|\s|$)|localhost(?::\d+)?(?:/|\s|$)|<host-name-or-ip>)[^\s\)\]\""']+", "http://<redacted-url>"
    $redacted = $redacted -replace "[A-Za-z]:\\[^\r\n]+", "<redacted-local-path>"
    $redacted = $redacted -replace "(?i)(/share/|/volume)[^\s\r\n]+", "<redacted-server-path>"
    $redacted = $redacted -replace "(?i)provider[_ -]?subjects?", "private auth identifiers"
    $redacted = $redacted -replace "(?i)provider[_ -]?issuers?", "private auth authorities"
    $redacted = $redacted -replace "(?i)raw provider claims", "private auth claims"
    $redacted = $redacted -replace "(?i)tenant[_ -]?ids?", "private tenant markers"
    $redacted = $redacted -replace "(?i)callback (url|urls|secret|secrets)", "private callback markers"
    $redacted = $redacted -replace "(?i)response bodies", "route response content"
    $redacted = $redacted -replace "(?i)raw artifact contents", "raw artifact material"
    $redacted = $redacted -replace "(?i)raw server-specific paths", "server layout details"
    $redacted = $redacted -replace "(?i)raw server paths", "server layout details"
    $redacted = $redacted -replace "(?i)\btokens?\b", "private credentials"
    $redacted = $redacted -replace "(?i)\bcookies?\b", "private browser state"
    $redacted = $redacted -replace "(?i)callback urls?", "private callback markers"
    $redacted = $redacted -replace "(?i)connection strings?", "private connection details"
    $redacted = $redacted -replace "(?i)client secrets?", "private client credentials"
    $redacted = $redacted -replace "(?i)private urls?", "private location markers"
    return $redacted.TrimEnd()
}

function Invoke-PacketCommand {
    param(
        [string]$Label,
        [string]$ScriptPath,
        [string[]]$CommandArguments
    )

    $shell = (Get-Command pwsh -ErrorAction SilentlyContinue).Source
    if ([string]::IsNullOrWhiteSpace($shell)) {
        $shell = (Get-Command powershell -ErrorAction SilentlyContinue).Source
    }
    if ([string]::IsNullOrWhiteSpace($shell)) {
        Stop-PacketFail "PowerShell is required to run the evidence packet command."
    }

    $processArguments = @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $ScriptPath
    ) + $CommandArguments

    $output = & $shell @processArguments 2>&1
    $exitCode = $LASTEXITCODE
    $text = ($output | ForEach-Object { [string]$_ }) -join "`n"
    return [pscustomobject]@{
        Label = $Label
        ExitCode = $exitCode
        Output = (Redact-EvidenceText -Text $text)
    }
}

function Format-CommandSection {
    param([pscustomobject]$Result)
    $status = if ($Result.ExitCode -eq 0) { "PASS" } else { "FAIL" }
    $body = if ([string]::IsNullOrWhiteSpace($Result.Output)) { "No output captured." } else { $Result.Output }
    return @"
## $($Result.Label)

Status: $status (exit code $($Result.ExitCode)).

````text
$body
````
"@
}

foreach ($scriptPath in @($verifierScript, $seededEvidenceScript, $routeEvidenceScript)) {
    if (-not (Test-Path -LiteralPath $scriptPath)) {
        Stop-PacketFail "Required evidence script is missing: $(Get-SafeFileNameForDisplay -Path $scriptPath)."
    }
}

$outputFullPath = Get-FullPath -Path $OutputDir
$allowedProcessedPath = Join-Path $repoRoot "data/processed"
if (-not (Test-IsUnderPath -Path $outputFullPath -Parent $allowedProcessedPath)) {
    Stop-PacketFail "OutputDir must be inside the ignored data/processed folder."
}

foreach ($decision in @(
    @{ Label = "FeedbackDecision"; Value = $FeedbackDecision },
    @{ Label = "RetrievalDecision"; Value = $RetrievalDecision },
    @{ Label = "AuthDecision"; Value = $AuthDecision },
    @{ Label = "TesterInvitationDecision"; Value = $TesterInvitationDecision },
    @{ Label = "PostgresBackupPlan"; Value = $PostgresBackupPlan },
    @{ Label = "RawArtifactBackupPlan"; Value = $RawArtifactBackupPlan }
)) {
    Assert-SafeOperatorInput -Label $decision.Label -Value $decision.Value
}

New-Item -ItemType Directory -Path $outputFullPath -Force | Out-Null

$timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH-mm-ssZ")
$generatedAt = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$outputFile = Join-Path $outputFullPath "qnap-pilot-evidence-packet-$timestamp.md"
$outputDisplayPath = Get-RelativePathForDisplay -Path $outputFile
$envFileName = Get-SafeFileNameForDisplay -Path $EnvFile
$templateOnlyNotice = ""
if ($envFileName -eq ".env.example") {
    $templateOnlyNotice = "Template validation only: .env.example output is not QNAP pilot evidence for external tester invitation."
}

$verifierArgs = @("-EnvFile", $EnvFile)
$seededArgs = @("-EnvFile", $EnvFile)
if ($SkipDatabaseCheck) { $seededArgs += "-SkipDatabaseCheck" }
$routeArgs = @("-BaseUrl", $BaseUrl)
if ($AllowRouteUnavailable) { $routeArgs += "-AllowUnavailable" }

$verifierResult = Invoke-PacketCommand -Label "QNAP Verifier Summary" -ScriptPath $verifierScript -CommandArguments $verifierArgs
$seededResult = Invoke-PacketCommand -Label "Seeded Import Evidence Summary" -ScriptPath $seededEvidenceScript -CommandArguments $seededArgs
$routeResult = Invoke-PacketCommand -Label "Route Evidence Summary" -ScriptPath $routeEvidenceScript -CommandArguments $routeArgs

$knownLimitationsValue = if ($KnownLimitationsAcknowledged) { "acknowledged" } else { "not recorded" }
$decisionSections = @"
## Operator Decisions

- Auth readiness decision: $(Redact-EvidenceText -Text $AuthDecision)
- Tester invitation/access-control decision: $(Redact-EvidenceText -Text $TesterInvitationDecision)
- Feedback configuration decision: $(Redact-EvidenceText -Text $FeedbackDecision)
- Retrieval configuration decision: $(Redact-EvidenceText -Text $RetrievalDecision)
- PostgreSQL backup plan: $(Redact-EvidenceText -Text $PostgresBackupPlan)
- Raw artifact backup plan: $(Redact-EvidenceText -Text $RawArtifactBackupPlan)
- Known limitations acknowledgement: $knownLimitationsValue

## Deferred Items

- Real OIDC/login.
- OIDC/OAuth2 callback handling.
- Sessions or cookies.
- User tables.
- Self-service signup.
- Invitation workflow implementation.
- Account management UI.
- Identity provider integration.
- Deployment hardening.
- New retrieval record types.
- Non-CCLD sources.
- Export UI or audit UI.
- Raw artifact viewer.
- Broader UI redesign.

## Conclusion Boundary

This packet is local operator readiness evidence only. It is not an audit export,
legal report, product export packet, public report, official certification, or
public-source completeness proof. It makes no public-source completeness,
public-source absence, legal, facility-wide, harm, abuse, neglect, liability, or
rights-deprivation conclusions.
"@

$packet = @"
# QNAP Pilot Evidence Packet

Generated: $generatedAt

This local Markdown packet assembles redacted QNAP pilot readiness evidence from
existing checks. It is optional operator convenience only and must not be
committed without a separate review that proves it contains no private values.

## Inputs

- Env file name: $envFileName
- Base URL: supplied to the route evidence command and redacted in captured output.
- Output directory: data/processed/qnap-pilot-evidence
- Seeded database check skipped: $([bool]$SkipDatabaseCheck)
- Route unavailable allowed: $([bool]$AllowRouteUnavailable)
- Read-only: yes. The command does not mutate the app database, run imports, run retrieval, send feedback, call GitHub, call live CCLD, or execute POST requests.

$templateOnlyNotice

$(Format-CommandSection -Result $verifierResult)

$(Format-CommandSection -Result $seededResult)

$(Format-CommandSection -Result $routeResult)

$decisionSections
"@

$packet = Redact-EvidenceText -Text $packet
Set-Content -LiteralPath $outputFile -Value $packet -Encoding UTF8

$results = @($verifierResult, $seededResult, $routeResult)
$failed = @($results | Where-Object { $_.ExitCode -ne 0 })

Write-Host "QNAP pilot evidence packet command completed."
if ($templateOnlyNotice) { Write-Host $templateOnlyNotice }
Write-Host "Generated evidence packet: $outputDisplayPath"
Write-Host "Review before sharing. Keep generated evidence files untracked."

if ($failed.Count -gt 0) {
    Write-Host "Evidence packet captured $($failed.Count) readiness failure(s)."
    exit 1
}

exit 0