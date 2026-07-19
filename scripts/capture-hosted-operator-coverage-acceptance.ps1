<#
.SYNOPSIS
Captures automated read-only operator coverage acceptance evidence.
.DESCRIPTION
LocalProductionAuth exercises the production Cloudflare Access branch with an
ephemeral signed assertion and JWKS kept in memory. Hosted consumes assertions
only from the configured header-provider command; it never reads cookies or
browser profiles and never writes authentication material to evidence.
.EXAMPLE
.\scripts\capture-hosted-operator-coverage-acceptance.ps1 -Mode LocalProductionAuth -Port 8031
#>
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("LocalProductionAuth", "Hosted")]
    [string]$Mode,

    [string]$BaseUrl = "",
    [string]$ExpectedCommitSha = "",
    [string]$OutputRoot = "data\processed\ui-evidence",

    [ValidateRange(1024, 65535)]
    [int]$Port = 8031
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$featureBranch = "issues-453-477-hosted-coverage-runtime"
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$branch = (& git -C $repoRoot branch --show-current).Trim()
$commitSha = (& git -C $repoRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or -not $branch -or -not $commitSha) {
    throw "Acceptance capture requires a resolved branch and HEAD."
}

$evidenceCommitSha = $commitSha
if ($Mode -eq "LocalProductionAuth") {
    if ($branch -ne $featureBranch) {
        throw "LocalProductionAuth must run from branch $featureBranch."
    }
} else {
    if (-not $ExpectedCommitSha) {
        throw "Hosted mode requires -ExpectedCommitSha."
    }
    if ($ExpectedCommitSha -cnotmatch '^[0-9a-f]{40}$') {
        throw "Hosted -ExpectedCommitSha must be an exact lowercase 40-character commit SHA."
    }
    if ($branch -ne "main") {
        throw "Hosted mode must run from branch main."
    }
    $worktreeStatus = @(& git -C $repoRoot status --porcelain --untracked-files=all)
    if ($LASTEXITCODE -ne 0 -or $worktreeStatus.Count -ne 0) {
        throw "Hosted mode requires a clean worktree."
    }
    $originMain = (& git -C $repoRoot rev-parse refs/remotes/origin/main).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $originMain) {
        throw "Hosted mode requires a resolved local origin/main reference."
    }
    if ($commitSha -cne $ExpectedCommitSha -or $originMain -cne $ExpectedCommitSha) {
        throw "Hosted mode requires local HEAD and origin/main to equal -ExpectedCommitSha."
    }
    $evidenceCommitSha = $ExpectedCommitSha
}

$processedRoot = [IO.Path]::GetFullPath((Join-Path $repoRoot "data\processed"))
$resolvedOutputRoot = [IO.Path]::GetFullPath((Join-Path $repoRoot $OutputRoot))
if (-not $resolvedOutputRoot.StartsWith($processedRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "OutputRoot must remain under the ignored data/processed directory."
}

$gitCommonDir = (& git -C $repoRoot rev-parse --git-common-dir).Trim()
if (-not $gitCommonDir) { throw "The shared Git directory could not be resolved." }
$resolvedGitCommonDir = if ([IO.Path]::IsPathRooted($gitCommonDir)) {
    [IO.Path]::GetFullPath($gitCommonDir)
} else {
    [IO.Path]::GetFullPath((Join-Path $repoRoot $gitCommonDir))
}
$sharedRepoRoot = Split-Path $resolvedGitCommonDir -Parent
$python = @(
    (Join-Path $repoRoot ".venv\Scripts\python.exe"),
    (Join-Path $sharedRepoRoot ".venv\Scripts\python.exe")
) | Select-Object -Unique | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $python) { throw "A repository virtual environment is required." }
& $python -c "import playwright.sync_api" 2>$null
if ($LASTEXITCODE -ne 0) { throw "The repository environment requires Playwright." }

$runner = Join-Path $repoRoot "scripts\capture_hosted_operator_coverage_acceptance.py"
$arguments = @(
    $runner,
    "--mode", $Mode,
    "--repo-root", $repoRoot,
    "--output-root", $resolvedOutputRoot,
    "--port", [string]$Port,
    "--branch", $branch,
    "--commit-sha", $evidenceCommitSha
)
if ($Mode -eq "Hosted") {
    if (-not $BaseUrl) { throw "Hosted mode requires -BaseUrl." }
    if (-not $env:CCLD_OPERATOR_COVERAGE_ACCEPTANCE_HEADER_PROVIDER_COMMAND) {
        throw "Hosted mode requires CCLD_OPERATOR_COVERAGE_ACCEPTANCE_HEADER_PROVIDER_COMMAND. Fully automated Cloudflare acceptance cannot proceed without an already-authorized in-memory header provider; browser cookies and stored assertions are forbidden."
    }
    $arguments += @("--base-url", $BaseUrl)
}

& $python @arguments
if ($LASTEXITCODE -ne 0) {
    throw "Automated operator coverage acceptance failed."
}
