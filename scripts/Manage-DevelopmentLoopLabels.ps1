[CmdletBinding()]
param(
    [ValidateSet("DryRun", "Apply", "Verify")]
    [string]$Mode = "DryRun",
    [ValidatePattern("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")]
    [string]$Repository = "nicho1ab/RecordsTracker"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ExpectedRepository = "nicho1ab/RecordsTracker"
$TaxonomyPath = Join-Path $PSScriptRoot "..\.github\development-loop-labels.json"

if ($Repository -cne $ExpectedRepository) {
    throw "This governed script may target only $ExpectedRepository."
}
if (-not (Test-Path -LiteralPath $TaxonomyPath)) {
    throw "Development-loop label taxonomy not found: $TaxonomyPath"
}

$Taxonomy = Get-Content -LiteralPath $TaxonomyPath -Raw | ConvertFrom-Json
if ([string]$Taxonomy.repository -cne $ExpectedRepository) {
    throw "Taxonomy repository does not match the governed target $ExpectedRepository."
}

function Assert-GitHubAccess {
    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
        throw "GitHub CLI (gh) is required for Apply and Verify modes."
    }

    & gh auth status 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "GitHub CLI authentication is unavailable. Run 'gh auth login' and retry."
    }

    $rawRepository = & gh repo view $Repository --json nameWithOwner 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "GitHub repository access is unavailable for $Repository."
    }

    $resolvedRepository = ($rawRepository -join "`n" | ConvertFrom-Json).nameWithOwner
    if ([string]$resolvedRepository -cne $ExpectedRepository) {
        throw "Resolved repository '$resolvedRepository' does not match $ExpectedRepository."
    }
}

function Get-LabelCreateArguments {
    param([Parameter(Mandatory = $true)]$Label)

    return @(
        "label",
        "create",
        [string]$Label.name,
        "--repo",
        $Repository,
        "--color",
        [string]$Label.color,
        "--description",
        [string]$Label.description,
        "--force"
    )
}

function Confirm-DevelopmentLoopLabels {
    $rawLabels = & gh label list --repo $Repository --limit 1000 --json name,color,description 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to list labels for verification in $Repository."
    }

    $liveLabels = @($rawLabels -join "`n" | ConvertFrom-Json)
    $liveByName = @{}
    foreach ($liveLabel in $liveLabels) {
        $liveByName[[string]$liveLabel.name] = $liveLabel
    }

    $problems = [System.Collections.Generic.List[string]]::new()
    foreach ($expected in $Taxonomy.labels) {
        $name = [string]$expected.name
        if (-not $liveByName.ContainsKey($name)) {
            $problems.Add("Missing label: $name")
            continue
        }

        $actual = $liveByName[$name]
        if ([string]$actual.color -ine [string]$expected.color) {
            $problems.Add("Color mismatch for $name")
        }
        if ([string]$actual.description -cne [string]$expected.description) {
            $problems.Add("Description mismatch for $name")
        }
    }

    if ($problems.Count -gt 0) {
        throw "Development-loop label verification failed:`n- $($problems -join "`n- ")"
    }

    Write-Host "Verified $($Taxonomy.labels.Count) governed development-loop labels in $Repository."
}

if ($Mode -eq "DryRun") {
    $plan = @(
        foreach ($label in $Taxonomy.labels) {
            [ordered]@{
                command = "gh"
                arguments = @(Get-LabelCreateArguments -Label $label)
            }
        }
    )
    $plan | ConvertTo-Json -Depth 5
    exit 0
}

Assert-GitHubAccess

if ($Mode -eq "Apply") {
    foreach ($label in $Taxonomy.labels) {
        $arguments = Get-LabelCreateArguments -Label $label
        & gh @arguments | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create or update label '$($label.name)'."
        }
    }
}

Confirm-DevelopmentLoopLabels
