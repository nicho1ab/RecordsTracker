<#
.SYNOPSIS
Summarizes safe QNAP pilot seeded import evidence.
.DESCRIPTION
Reads the QNAP pilot env shape and, when available, runs read-only PostgreSQL
summary queries through Docker Compose. This script does not mutate data, run
imports, run retrieval, call live CCLD, call GitHub, print secrets, print raw
artifact contents, print raw server paths, or make public-source completeness or
legal conclusions.
.PARAMETER EnvFile
Path to the untracked .env file. Defaults to .env.
.PARAMETER ComposeFile
Docker Compose file to use for read-only PostgreSQL checks. Defaults to docker-compose.qnap.yml.
.PARAMETER DatabaseService
Docker Compose service name for PostgreSQL. Defaults to postgres.
.PARAMETER SkipDatabaseCheck
Skip Docker/PostgreSQL read-only checks and print env/configuration evidence only.
.EXAMPLE
.\scripts\summarize-qnap-pilot-seeded-import-evidence.ps1 -EnvFile .env
.EXAMPLE
.\scripts\summarize-qnap-pilot-seeded-import-evidence.ps1 -EnvFile .env.example -SkipDatabaseCheck
.NOTES
Run from the repository root. Keep real .env files untracked.
#>
param(
    [string]$EnvFile = ".env",
    [string]$ComposeFile = "docker-compose.qnap.yml",
    [string]$DatabaseService = "postgres",
    [switch]$SkipDatabaseCheck
)

$ErrorActionPreference = "Stop"
$failureCount = 0
$warningCount = 0

function Write-EvidenceInfo {
    param([string]$Message)
    Write-Host "[INFO] $Message"
}

function Write-EvidencePass {
    param([string]$Message)
    Write-Host "[PASS] $Message"
}

function Write-EvidenceWarn {
    param([string]$Message)
    $script:warningCount += 1
    Write-Warning $Message
}

function Write-EvidenceFail {
    param([string]$Message)
    $script:failureCount += 1
    Write-Host "[FAIL] $Message"
}

function Read-EnvValues {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        Write-EvidenceWarn "Env file '$Path' was not found. Copy .env.example to .env and keep .env untracked before QNAP pilot evidence capture."
        return @{}
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

function Invoke-PostgresScalar {
    param([string]$Sql)
    $arguments = @(
        "compose",
        "-f",
        $ComposeFile,
        "--env-file",
        $EnvFile,
        "exec",
        "-T",
        $DatabaseService,
        "sh",
        "-lc",
        "psql -U `"`$POSTGRES_USER`" -d `"`$POSTGRES_DB`" -At -F '|' -c `"$Sql`""
    )
    $output = & docker @arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw ($output -join "`n")
    }
    return @($output | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) })
}

function Invoke-ReadOnlyDatabaseEvidence {
    if (-not (Test-Path -LiteralPath $ComposeFile)) {
        Write-EvidenceWarn "Compose file '$ComposeFile' was not found. Skipping PostgreSQL evidence queries."
        return
    }

    try {
        $alembicOutput = & docker compose -f $ComposeFile --env-file $EnvFile run --rm app alembic current 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-EvidencePass "Alembic current check completed."
            foreach ($line in $alembicOutput) {
                if (-not [string]::IsNullOrWhiteSpace([string]$line)) {
                    Write-Host "  alembic: $line"
                }
            }
        }
        else {
            Write-EvidenceWarn "Alembic current check could not be completed. Confirm migrations before inviting testers."
        }
    }
    catch {
        Write-EvidenceWarn "Alembic current check could not be completed. Confirm migrations before inviting testers."
    }

    try {
        $tableRows = Invoke-PostgresScalar "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name IN ('hosted_import_batches', 'hosted_source_derived_records') ORDER BY table_name;"
        $tables = @($tableRows)
        if ($tables -contains "hosted_import_batches" -and $tables -contains "hosted_source_derived_records") {
            Write-EvidencePass "Hosted seeded import tables are present."
        }
        else {
            Write-EvidenceWarn "Hosted seeded import tables are missing or incomplete."
        }
    }
    catch {
        Write-EvidenceWarn "PostgreSQL evidence queries could not connect. Confirm containers and database readiness."
        return
    }

    try {
        $batchCountRows = Invoke-PostgresScalar "SELECT count(*) FROM hosted_import_batches;"
        $batchCount = [int]$batchCountRows[0]
        Write-Host "Import batches: $batchCount"
        if ($batchCount -eq 0) {
            Write-EvidenceFail "No hosted import batches were found. Import a validated CCLD artifact before inviting testers."
        }

        $mostRecentRows = Invoke-PostgresScalar "SELECT COALESCE(max(imported_at), 'none') FROM hosted_import_batches;"
        Write-Host "Most recent import batch timestamp: $($mostRecentRows[0])"

        $sourceCountRows = Invoke-PostgresScalar "SELECT count(*) FROM hosted_source_derived_records;"
        $sourceCount = [int]$sourceCountRows[0]
        Write-Host "Source-derived records: $sourceCount"
        if ($sourceCount -eq 0) {
            Write-EvidenceFail "No hosted source-derived rows were found. Import validated CCLD rows before inviting testers."
        }

        Write-Host "Source-derived row counts by entity type:"
        $entityRows = Invoke-PostgresScalar "SELECT entity_type, count(*) FROM hosted_source_derived_records GROUP BY entity_type ORDER BY entity_type;"
        if ($entityRows.Count -eq 0) {
            Write-Host "  none"
        }
        foreach ($row in $entityRows) {
            $parts = ([string]$row).Split("|", 2)
            if ($parts.Count -eq 2) {
                Write-Host "  $($parts[0]): $($parts[1])"
            }
        }

        $linkageRows = Invoke-PostgresScalar "SELECT count(source_url), count(raw_sha256), count(connector_name), count(source_traceability ->> 'source_artifact_identity') FROM hosted_source_derived_records;"
        $linkageParts = ([string]$linkageRows[0]).Split("|", 4)
        $sourceUrlCount = [int]$linkageParts[0]
        $rawHashCount = [int]$linkageParts[1]
        $connectorCount = [int]$linkageParts[2]
        $artifactIdentityCount = [int]$linkageParts[3]
        Write-Host "Rows with source URL: $sourceUrlCount"
        Write-Host "Rows with raw SHA-256 linkage: $rawHashCount"
        Write-Host "Rows with connector name: $connectorCount"
        Write-Host "Rows with source artifact identity: $artifactIdentityCount"
        if ($sourceCount -gt 0) {
            if ($sourceUrlCount -lt $sourceCount -or $rawHashCount -lt $sourceCount -or $connectorCount -lt $sourceCount -or $artifactIdentityCount -lt $sourceCount) {
                Write-EvidenceWarn "Some source-derived linkage counts are incomplete. Review import traceability before inviting testers."
            }
            else {
                Write-EvidencePass "Source-derived linkage counts are complete for the imported rows."
            }
        }
    }
    catch {
        Write-EvidenceWarn "PostgreSQL evidence queries were interrupted. Confirm containers, migrations, and table availability."
    }
}

Write-Host "QNAP pilot seeded import evidence summary"
Write-Host "Read-only: does not mutate data, run imports, run retrieval, call live CCLD, or call GitHub."
Write-Host "Safe output: does not print secrets, raw artifact contents, raw source narrative, or raw server paths."
Write-Host "Conclusion boundary: no public-source completeness, legal, facility-wide, harm, abuse, neglect, or liability conclusion."

$envValues = Read-EnvValues -Path $EnvFile
$envPresent = $envValues.Count -gt 0
if ($envPresent) {
    Write-EvidencePass "Env file is present. Keep .env untracked."
}

$pageDataMode = Get-EnvValue -Values $envValues -Key "CCLD_HOSTED_PAGE_DATA_MODE"
$authMode = Get-EnvValue -Values $envValues -Key "CCLD_HOSTED_TESTER_AUTH_MODE"
$localDevAuth = Get-EnvValue -Values $envValues -Key "CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH"
$retrievalDemoMode = Get-EnvValue -Values $envValues -Key "CCLD_RETRIEVAL_DEMO_MODE"
$retrievalEnabled = Get-EnvValue -Values $envValues -Key "CCLD_RETRIEVAL_ENABLED"
$retrievalRawDir = Get-EnvValue -Values $envValues -Key "CCLD_RETRIEVAL_RAW_DIR"
$githubFeedbackRepo = Get-EnvValue -Values $envValues -Key "GITHUB_FEEDBACK_REPO"
$githubFeedbackToken = Get-EnvValue -Values $envValues -Key "GITHUB_FEEDBACK_TOKEN"

if ($envPresent) {
    if ($pageDataMode -eq "postgres") {
        Write-EvidencePass "Expected page-data mode is PostgreSQL-backed."
    }
    else {
        Write-EvidenceFail "CCLD_HOSTED_PAGE_DATA_MODE is not postgres. QNAP pilot evidence should use PostgreSQL-backed page data."
    }

    if ($authMode -ne "production" -or $localDevAuth -ne "disabled") {
        Write-EvidenceWarn "QNAP pilot should use production auth mode with local-dev auth disabled."
    }

    if ($retrievalDemoMode -eq "mock-success") {
        Write-EvidenceFail "CCLD_RETRIEVAL_DEMO_MODE=mock-success must stay out of QNAP pilot mode."
    }
    else {
        Write-EvidencePass "Local-dev mock-success retrieval mode is not enabled for QNAP pilot evidence."
    }

    if ([string]::IsNullOrWhiteSpace($githubFeedbackRepo) -and [string]::IsNullOrWhiteSpace($githubFeedbackToken)) {
        Write-EvidencePass "GitHub feedback decision: disabled intentionally."
    }
    elseif ([string]::IsNullOrWhiteSpace($githubFeedbackRepo) -or [string]::IsNullOrWhiteSpace($githubFeedbackToken)) {
        Write-EvidenceFail "GitHub feedback decision: half-configured readiness error. Configure both repo and token server-side or leave both blank."
    }
    else {
        Write-EvidencePass "GitHub feedback decision: fully configured server-side. Token value was not printed."
    }

    if ($retrievalEnabled -eq "enabled") {
        if ([string]::IsNullOrWhiteSpace($retrievalRawDir)) {
            Write-EvidenceFail "Retrieval configuration decision: enabled without raw storage readiness error."
        }
        else {
            Write-EvidencePass "Retrieval configuration decision: configured with raw artifact storage path present. Raw path was not printed."
        }
    }
    else {
        Write-EvidencePass "Retrieval configuration decision: disabled intentionally unless explicitly enabled."
        if (-not [string]::IsNullOrWhiteSpace($retrievalRawDir)) {
            Write-EvidencePass "Raw artifact storage path is configured. Raw path was not printed."
        }
    }

    foreach ($key in @("CCLD_POSTGRES_PASSWORD", "CCLD_HOSTED_TESTER_OIDC_ISSUER", "CCLD_HOSTED_TESTER_OIDC_CLIENT_ID")) {
        $value = Get-EnvValue -Values $envValues -Key $key
        if (Test-PlaceholderValue -Value $value) {
            Write-EvidenceWarn "$key still looks like a placeholder. Replace host-local readiness values before inviting testers."
        }
    }
}

if ($SkipDatabaseCheck) {
    Write-EvidenceInfo "Skipping PostgreSQL evidence queries because -SkipDatabaseCheck was supplied."
}
elseif (-not $envPresent) {
    Write-EvidenceInfo "Skipping PostgreSQL evidence queries because env configuration was unavailable."
}
else {
    Invoke-ReadOnlyDatabaseEvidence
}

Write-Host "Raw artifact contents printed: no."
Write-Host "Raw server-specific paths printed: no."
Write-Host "Secrets printed: no."

if ($failureCount -gt 0) {
    Write-Host "Evidence summary completed with $failureCount readiness failure(s) and $warningCount warning(s)."
    exit 1
}

Write-Host "Evidence summary completed with $warningCount warning(s) and no readiness failures."
exit 0