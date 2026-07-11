[CmdletBinding(SupportsShouldProcess=$true)]
param(
    [string]$Repo = "",
    [switch]$GenerateFiles,
    [switch]$SyncIssues,
    [string]$AssignRequirementId = "",
    [switch]$OpenIssues,
    [string]$OutputManifest = "requirements\stakeholder-issue-manifest.json"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Write-Utf8File {
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [Parameter(Mandatory=$true)][string]$Content
    )

    if ([System.IO.Path]::IsPathRooted($Path)) {
        $ResolvedPath = $Path
    }
    else {
        $ResolvedPath = Join-Path (Get-Location) $Path
    }

    $Parent = Split-Path -Parent $ResolvedPath

    if ($Parent -and -not (Test-Path -LiteralPath $Parent)) {
        New-Item -ItemType Directory -Path $Parent -Force | Out-Null
    }

    [System.IO.File]::WriteAllText(
        $ResolvedPath,
        $Content,
        (New-Object System.Text.UTF8Encoding($false))
    )
}

function Invoke-GhJson {
    param([Parameter(Mandatory=$true)][string[]]$Arguments)
    $raw = & gh @Arguments
    if ($LASTEXITCODE -ne 0) { throw "GitHub CLI command failed: gh $($Arguments -join ' ')" }
    if ([string]::IsNullOrWhiteSpace(($raw -join "`n"))) { return $null }
    return (($raw -join "`n") | ConvertFrom-Json)
}

function Resolve-Repo {
    if (-not [string]::IsNullOrWhiteSpace($Repo)) { return $Repo }
    $view = Invoke-GhJson -Arguments @("repo","view","--json","nameWithOwner")
    if (-not $view.nameWithOwner) { throw "Unable to resolve the current GitHub repository. Run inside the repository or pass -Repo owner/name." }
    return [string]$view.nameWithOwner
}

function Get-IssueByRequirementId {
    param([string]$Repository,[string]$RequirementId)

    $marker = "<!-- recordstracker-requirement-id: $RequirementId -->"
    $items = Invoke-GhJson -Arguments @(
        "issue",
        "list",
        "--repo",
        $Repository,
        "--state",
        "all",
        "--limit",
        "200",
        "--json",
        "number,title,url,state,body"
    )

    if ($null -eq $items) {
        return $null
    }

    $match = @(
        $items |
        Where-Object {
            $_.body -and $_.body.Contains($marker)
        } |
        Select-Object -First 1
    )

    if ($match.Count -eq 0) {
        return $null
    }

    return $match[0]
}

function Ensure-Label {
    param([string]$Repository,[string]$Name,[string]$Color,[string]$Description)
    & gh label create $Name --repo $Repository --color $Color --description $Description --force | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Failed to create or update label '$Name'." }
}

$requirements = @(
    [ordered]@{
        id = "STAKEHOLDER-EPIC"
        title = "Stakeholder requirements: facility intelligence and attorney review"
        priority = "p0"
        type = "epic"
        summary = "Create a traceable implementation program that helps an attorney reviewer identify facilities requiring attention, inspect the public record, and determine what to review next."
        user_outcome = "As an attorney reviewer, I can begin from a multi-facility view, identify facilities that may warrant review, and drill into source-backed complaints without first knowing which facility is problematic."
        current_gap = "RecordsTracker is strongest after a facility is already selected. The remaining product gap is systematic discovery, prioritization, cross-facility analysis, and stakeholder-confirmed acceptance."
        dependencies = @()
        labels = @("initiative:facility-intelligence","type:epic","priority:p0","needs:stakeholder-validation")
        acceptance = @(
            "All child requirements are linked from this epic and have implementation, evidence, and stakeholder-acceptance status.",
            "A reviewer can begin without supplying a known problem facility.",
            "A reviewer can understand why a facility or complaint was surfaced.",
            "A reviewer can open the original public source for every qualifying result when available.",
            "Final acceptance is based on representative stakeholder scenarios, not only merged code or passing tests."
        )
    },
    [ordered]@{
        id = "STAKEHOLDER-001"
        title = "Establish representative multi-facility data coverage"
        priority = "p0"
        type = "data"
        summary = "Load and validate enough real facility and complaint data to support meaningful cross-facility review."
        user_outcome = "As an attorney reviewer, I can search and compare a representative set of real facilities rather than a tiny fixture-only list."
        current_gap = "The application can retrieve and review selected facilities, but cross-facility intelligence is only as useful as the loaded facility and complaint coverage."
        dependencies = @()
        labels = @("initiative:facility-intelligence","type:data","priority:p0","needs:stakeholder-validation")
        acceptance = @(
            "The exact included facility types, source files, source URLs, snapshot dates, and loaded row counts are documented.",
            "Facility records are deduplicated by stable source-derived identity.",
            "Complaint records preserve source URL, raw hash, retrieval timestamp, connector metadata, and source-record linkage.",
            "Production/QNAP mode does not silently use synthetic or tiny fallback facilities.",
            "A reconciliation report compares source rows, imported rows, rejected rows, duplicate rows, and displayed rows.",
            "Representative facilities can be found by license number, partial name, city, county, ZIP, type, and operator when those source fields are available."
        )
    },
    [ordered]@{
        id = "STAKEHOLDER-002"
        title = "Add a source-traceable substantiated complaint worklist"
        priority = "p0"
        type = "feature"
        summary = "Provide a cross-facility worklist of substantiated complaints in the loaded corpus."
        user_outcome = "As an attorney reviewer, I can view substantiated complaints across loaded facilities with facility identity, complaint date, finding, and original report access."
        current_gap = "Individual findings exist, but the hosted product needs a dedicated cross-facility reviewer workflow."
        dependencies = @("STAKEHOLDER-001")
        labels = @("initiative:facility-intelligence","type:feature","priority:p0","needs:stakeholder-validation")
        acceptance = @(
            "A dedicated reviewer-facing route lists qualifying substantiated complaints across all loaded facilities.",
            "Each result shows facility name, facility/license number, complaint date, normalized finding, concise category or summary when available, and original source-report access.",
            "Filters include date range, facility identity, facility type, geography when available, and finding.",
            "Sorting includes complaint date and facility.",
            "Selecting a result opens the existing complaint review workspace.",
            "Displayed counts reconcile exactly with qualifying source-derived records.",
            "Missing source links are identified rather than silently omitted.",
            "The page avoids unsupported legal or facility-wide conclusions."
        )
    },
    [ordered]@{
        id = "STAKEHOLDER-003"
        title = "Add facility monitoring and review prioritization"
        priority = "p0"
        type = "feature"
        summary = "Help reviewers identify facilities with repeated or serious public-record patterns."
        user_outcome = "As an attorney reviewer, I can see which facilities may deserve attention first and the source-derived reasons they were surfaced."
        current_gap = "RecordsTracker has facility summaries and record-level flags but lacks a complete multi-facility prioritization workflow."
        dependencies = @("STAKEHOLDER-001","STAKEHOLDER-002")
        labels = @("initiative:facility-intelligence","type:feature","priority:p0","needs:stakeholder-validation")
        acceptance = @(
            "The view ranks or groups facilities using documented, deterministic source-derived indicators.",
            "Every surfaced indicator is explainable and traceable to displayed source-derived records.",
            "The UI shows contributing factors rather than a hidden or unexplained risk score.",
            "Reviewers can filter by facility type, geography, time window, complaint count, substantiated count, and available source-derived indicators.",
            "Users can drill directly into the qualifying complaints and original sources.",
            "Ties, missing values, and low-data facilities are handled explicitly.",
            "Fixture and integration tests prove deterministic ordering and count reconciliation."
        )
    },
    [ordered]@{
        id = "STAKEHOLDER-004"
        title = "Add serious-complaint review categories"
        priority = "p1"
        type = "feature"
        summary = "Surface source-derived complaint categories and cautious keyword-assisted review cues for serious allegations."
        user_outcome = "As an attorney reviewer, I can narrow the corpus to serious complaint themes and inspect the underlying source text and report."
        current_gap = "Keyword discovery exists in retained local review tooling, but the hosted attorney workflow does not provide governed cross-facility serious-theme review."
        dependencies = @("STAKEHOLDER-001","STAKEHOLDER-002")
        labels = @("initiative:facility-intelligence","type:feature","priority:p1","needs:stakeholder-validation")
        acceptance = @(
            "The initial category vocabulary is documented and reviewed before implementation.",
            "Category assignment is deterministic when reliable source fields exist; keyword cues remain visibly distinct from official findings.",
            "Every match exposes the matching source-derived basis and original report.",
            "False-positive and false-negative fixture cases are included.",
            "Reviewers can combine category filters with finding, facility, geography, and date filters.",
            "The UI never presents a keyword match as a legal conclusion, verified event, or facility-wide conclusion."
        )
    },
    [ordered]@{
        id = "STAKEHOLDER-005"
        title = "Add complaint trend and anomaly review"
        priority = "p1"
        type = "feature"
        summary = "Show complaint and finding patterns over time and identify unusual changes that warrant source review."
        user_outcome = "As an attorney reviewer, I can see whether complaint activity, substantiated findings, or review indicators changed over time for a facility or group of facilities."
        current_gap = "Dates and timeline views exist, but the hosted product lacks multi-period trend and anomaly review."
        dependencies = @("STAKEHOLDER-001","STAKEHOLDER-002")
        labels = @("initiative:facility-intelligence","type:feature","priority:p1","needs:stakeholder-validation")
        acceptance = @(
            "The reviewer can choose a documented time grain and date range.",
            "Trend counts reconcile with the underlying complaint records.",
            "The view distinguishes zero records, missing coverage, incomplete periods, and actual decreases.",
            "Anomaly cues use documented deterministic rules and show their contributing periods and records.",
            "Charts include accessible text alternatives or data tables.",
            "The workflow links from aggregate trends to qualifying complaints and original sources."
        )
    },
    [ordered]@{
        id = "STAKEHOLDER-006"
        title = "Build the cross-facility intelligence dashboard"
        priority = "p1"
        type = "feature"
        summary = "Provide the main attorney-facing view for deciding which facilities and complaints to review next."
        user_outcome = "As an attorney reviewer, I can start from a statewide or loaded-corpus overview, narrow the population, and choose the next facility or complaint based on source-backed indicators."
        current_gap = "RecordsTracker has facility-specific review workflows but not a unified cross-facility decision surface."
        dependencies = @("STAKEHOLDER-002","STAKEHOLDER-003","STAKEHOLDER-004","STAKEHOLDER-005")
        labels = @("initiative:facility-intelligence","type:feature","priority:p1","needs:stakeholder-validation")
        acceptance = @(
            "Above the fold answers which facilities appear to warrant review and why.",
            "Primary controls support facility type, geography, date range, finding, complaint category, and source-coverage filters when data is available.",
            "Summary metrics link to the exact contributing records.",
            "The dashboard does not duplicate detailed tables already available through drill-down routes.",
            "The design uses compact source cues and keeps technical traceability internals out of the primary reviewer tier.",
            "The exact route passes keyboard, screen-reader structure, responsive-layout, and visual evidence review."
        )
    },
    [ordered]@{
        id = "STAKEHOLDER-007"
        title = "Expand the facility review hub"
        priority = "p1"
        type = "feature"
        summary = "Synthesize facility identity, complaint history, trends, source documents, review state, and next actions."
        user_outcome = "As an attorney reviewer, I can understand the public-record picture for one facility and continue directly to the highest-priority records."
        current_gap = "Facility summaries and case briefs exist, but the hub must become the drill-down destination from cross-facility intelligence."
        dependencies = @("STAKEHOLDER-003","STAKEHOLDER-005")
        labels = @("initiative:facility-intelligence","type:feature","priority:p1","needs:stakeholder-validation")
        acceptance = @(
            "The page shows facility facts once near the top and avoids repeated context cards.",
            "The page synthesizes complaint counts, findings, serious-review categories, trends, source availability, reviewer-created status, and recommended next record.",
            "All aggregate values link to contributing records.",
            "Core identifiers and source links provide copy-to-clipboard actions where useful.",
            "CCLD terms use accessible inline definitions where helpful.",
            "Technical source-traceability details remain available outside the primary reviewer tier.",
            "The target route passes evidence-packet and manual visual review."
        )
    },
    [ordered]@{
        id = "STAKEHOLDER-008"
        title = "Complete stakeholder requirements acceptance"
        priority = "p0"
        type = "acceptance"
        summary = "Validate the implemented facility-intelligence workflow against representative stakeholder scenarios."
        user_outcome = "As the product owner, I have documented evidence that the completed workflow satisfies the external stakeholder's intended use, not merely the written implementation tasks."
        current_gap = "Merged PRs and passing tests do not independently prove that the end-to-end workflow meets the stakeholder need."
        dependencies = @("STAKEHOLDER-001","STAKEHOLDER-002","STAKEHOLDER-003","STAKEHOLDER-004","STAKEHOLDER-005","STAKEHOLDER-006","STAKEHOLDER-007")
        labels = @("initiative:facility-intelligence","type:acceptance","priority:p0","needs:stakeholder-validation")
        acceptance = @(
            "The stakeholder can begin without supplying a known problem facility.",
            "The stakeholder can identify a facility surfaced by source-derived indicators and understand why it was surfaced.",
            "The stakeholder can open all qualifying substantiated complaints for that facility.",
            "The stakeholder can reach the original public reports.",
            "The stakeholder can review trends and serious-review categories without confusing review cues with official findings.",
            "The stakeholder can identify the next facility or complaint to review.",
            "Observed gaps are recorded as linked issues.",
            "The final issue records acceptance date, representative scenarios, evidence links, and unresolved limitations."
        )
    }
)

$labelDefinitions = @(
    @{ Name="initiative:facility-intelligence"; Color="0E8A16"; Description="Cross-facility attorney review and discovery initiative" },
    @{ Name="type:epic"; Color="5319E7"; Description="Parent issue coordinating a multi-issue initiative" },
    @{ Name="type:feature"; Color="1D76DB"; Description="User-facing feature work" },
    @{ Name="type:data"; Color="0052CC"; Description="Data coverage, import, mapping, or quality work" },
    @{ Name="type:acceptance"; Color="B60205"; Description="End-to-end acceptance and stakeholder validation" },
    @{ Name="priority:p0"; Color="B60205"; Description="Critical prerequisite or outcome" },
    @{ Name="priority:p1"; Color="D93F0B"; Description="High-priority product work" },
    @{ Name="needs:stakeholder-validation"; Color="FBCA04"; Description="Cannot be considered complete until stakeholder validation is recorded" }
)

function New-IssueBody {
    param([hashtable]$Requirement,[hashtable]$IssueMap,[switch]$IsEpic)
    $dependencyLines = @()
    foreach ($dependency in @($Requirement.dependencies)) {
        if ($IssueMap.ContainsKey($dependency)) {
            $dependencyLines += "- Depends on #$($IssueMap[$dependency].number) ($dependency)"
        } else {
            $dependencyLines += "- Depends on $dependency"
        }
    }
    if ($dependencyLines.Count -eq 0) { $dependencyLines = @("- None") }

    $acceptanceLines = @($Requirement.acceptance | ForEach-Object { "- [ ] $_" })
    $childLines = @()
    if ($IsEpic) {
        foreach ($child in $requirements | Where-Object { $_.id -ne "STAKEHOLDER-EPIC" }) {
            if ($IssueMap.ContainsKey($child.id)) {
                $childLines += "- [ ] #$($IssueMap[$child.id].number) - $($child.title)"
            } else {
                $childLines += "- [ ] $($child.id) - $($child.title)"
            }
        }
    }

    $body = @"
<!-- recordstracker-requirement-id: $($Requirement.id) -->

## Requirement source

- Source: External stakeholder requirements meeting, June 19, 2026
- Requirement ID: ``$($Requirement.id)``
- Initiative: Facility intelligence and attorney review
- Parent epic: $(if ($Requirement.id -eq "STAKEHOLDER-EPIC") { "This issue" } elseif ($IssueMap.ContainsKey("STAKEHOLDER-EPIC")) { "#$($IssueMap["STAKEHOLDER-EPIC"].number)" } else { "STAKEHOLDER-EPIC" })

## Intended outcome

$($Requirement.user_outcome)

## Current gap

$($Requirement.current_gap)

## Scope

$($Requirement.summary)

Implementation must preserve source traceability, separate source-derived records from reviewer-created state, use deterministic logic where reliable, and avoid unsupported legal or source-completeness conclusions.

## Non-goals

- No unsupported legal, harm, abuse, neglect, liability, rights-deprivation, or facility-wide conclusions.
- No claim of complete statewide coverage unless source coverage is measured and proven.
- No mutation of canonical source-derived values through reviewer actions.
- No hidden ranking formula or unexplained automated conclusion.
- No unrelated framework, authentication, deployment, or visual redesign work.
- No exposure of secrets, private URLs, raw server paths, tokens, cookies, or provider claims.

## Data and traceability requirements

- Every displayed complaint must resolve to a stable source-derived complaint record.
- Every qualifying result must retain source URL, raw SHA-256, retrieval timestamp, connector metadata, and source-document linkage when available.
- Counts must reconcile with the loaded corpus.
- Duplicate source-derived records must not be introduced.
- Missing values must remain missing or explicitly unavailable; they must not be transformed into conclusions.
- Production-style modes must not silently use fixture, synthetic, or tiny fallback records.

## UX and accessibility requirements

- Lead with the attorney decision or action enabled by the page.
- Use semantic headings, labeled controls, logical keyboard focus, visible focus indicators, descriptive links, and non-color-only status.
- Tables must have clear headings; charts must have accessible text alternatives or data tables.
- Keep full traceability internals in support/operator tiers unless they directly help the current attorney task.
- Use plain language without exposing internal scaffold terminology.
- Significant UI work requires exact-route visual review and an evidence packet.

## Functional acceptance criteria

$($acceptanceLines -join "`n")

## Automated validation

- [ ] Focused unit tests cover deterministic calculations, filtering, ordering, and edge cases.
- [ ] Fixture or representative-data tests cover positive, negative, missing-value, and duplicate cases.
- [ ] Integration tests reconcile UI/API counts with source-derived records.
- [ ] Accessibility tests cover structure, labels, keyboard behavior, and non-color-only meaning.
- [ ] Security tests confirm no secrets or private runtime values are exposed.
- [ ] Existing source-derived and reviewer-created state separation tests continue to pass.
- [ ] ``.\scripts\lint.ps1`` passes.
- [ ] ``.\scripts\test.ps1`` passes.
- [ ] ``.\scripts\docs.ps1`` passes.

## Human evidence required

- [ ] Exact target route reviewed in the browser.
- [ ] Hosted UI evidence packet generated for affected routes.
- [ ] Representative displayed results reconciled to original source records.
- [ ] Empty, partial-data, missing-source, and error states reviewed.
- [ ] Keyboard flow reviewed.
- [ ] Documentation impact reviewed and updated where needed.

## Stakeholder acceptance scenario

Given a representative multi-facility corpus, when an attorney reviewer uses this capability, then the reviewer can complete the intended outcome above, understand the source-derived basis, reach the underlying public records, and identify an appropriate next review action without relying on unsupported conclusions.

## Stakeholder confirmation

- [ ] Demonstrated using representative real or governed fixture data.
- [ ] Stakeholder confirmed that the workflow meets the stated need.
- [ ] Requested corrections or remaining gaps were recorded as linked issues.
- [ ] Confirmation date, scenarios, evidence links, and limitations were added to this issue.

## Dependencies

$($dependencyLines -join "`n")

$(if ($IsEpic) { "## Child requirements`n`n$($childLines -join "`n")`n" } else { "" })
## Completion rule

Do not close this issue solely because code was written, tests passed, or a pull request merged. Close it only after the functional criteria, automated validation, evidence review, source reconciliation, and stakeholder-confirmation requirements above are complete.

## Implementation handoff for Codex or GitHub Copilot

Treat this issue body as the implementation prompt. Before editing:

1. Read ``AGENTS.md`` if present, ``.github/copilot-instructions.md``, the repository governance files, and directly affected architecture/data/accessibility/testing documentation.
2. Inspect the current implementation before proposing files.
3. Keep the change narrowly scoped to this issue.
4. Add focused tests and directly impacted documentation.
5. Do not create branches, commits, PRs, merge, deploy, or capture evidence unless explicitly asked.
6. End with a concise handoff: files changed, behavior added, validation run/results, known limitations, and exact manual evidence still required.
"@
    return $body
}

function Generate-RepositoryFiles {
    $definition = [ordered]@{
        schema_version = 1
        initiative_id = "STAKEHOLDER"
        title = "External stakeholder facility intelligence requirements"
        source = [ordered]@{
            type = "meeting"
            date = "2026-06-19"
            description = "External stakeholder requirements meeting"
        }
        privacy = [ordered]@{
            use_personal_name = $false
            use_organization_name = $false
            allowed_terms = @("external stakeholder","stakeholder","attorney reviewer","external reviewer")
        }
        completion_rule = "An issue is complete only after implementation, automated validation, evidence review, source reconciliation, and required stakeholder confirmation."
        requirements = $requirements
    }
    Write-Utf8File -Path "requirements\stakeholder-requirements.json" -Content ($definition | ConvertTo-Json -Depth 12)

    $readme = @'
# External Stakeholder Requirements

This directory contains the governed, machine-readable source for the facility-intelligence GitHub issue backlog.

## Privacy rule

Do not place the stakeholder's personal name, organization name, or organization domain in issue titles, bodies, labels, branches, commits, pull requests, documentation, screenshots, evidence packets, or generated manifests. Use neutral terms such as `external stakeholder`, `stakeholder`, or `attorney reviewer`.

## Files

- `stakeholder-requirements.json`: authoritative requirement definitions.
- `stakeholder-issue-manifest.json`: generated issue numbers and URLs after synchronization.

## Synchronize issues

Preview repository changes and GitHub actions:

```powershell
.\scripts\Manage-StakeholderRequirements.ps1 -GenerateFiles -SyncIssues -WhatIf
```

Create or update labels and create missing issues:

```powershell
.\scripts\Manage-StakeholderRequirements.ps1 -GenerateFiles -SyncIssues
```

Optionally open each issue after synchronization:

```powershell
.\scripts\Manage-StakeholderRequirements.ps1 -SyncIssues -OpenIssues
```

The script is idempotent. It searches for a hidden requirement marker before creating an issue.

## Implementation workflow

Use one child issue at a time. The issue body is written to function as a Codex or GitHub Copilot implementation prompt. Do not assign the epic itself for implementation.

Before assigning an issue to an agent, review and update the issue body. Information added after a GitHub Copilot cloud-agent assignment may need to be provided on the resulting pull request instead.

Close issues only after implementation, tests, evidence review, source reconciliation, and required stakeholder confirmation.
'@
    Write-Utf8File -Path "requirements\README.md" -Content $readme

    $instructionsPath = ".github\copilot-instructions.md"
    $marker = "<!-- BEGIN STAKEHOLDER REQUIREMENTS AUTOMATION -->"
    $endMarker = "<!-- END STAKEHOLDER REQUIREMENTS AUTOMATION -->"
    $block = @'
<!-- BEGIN STAKEHOLDER REQUIREMENTS AUTOMATION -->
## External stakeholder requirement issues

When working from an issue containing `recordstracker-requirement-id`:

- Treat the issue body as the approved implementation prompt and acceptance contract.
- Never add the stakeholder's personal name, organization name, or organization domain to code, docs, issues, PRs, commits, branches, screenshots, fixtures, evidence, or generated output.
- Read `requirements/stakeholder-requirements.json`, `AGENTS.md` when present, and directly affected governance files before editing.
- Keep scope limited to one child requirement unless dependencies make a combined change unavoidable.
- Preserve source traceability and source-derived versus reviewer-created state separation.
- Do not introduce hidden risk scores or unsupported legal, source-completeness, or facility-wide conclusions.
- Add focused tests for deterministic behavior, reconciliation, missing values, duplicates, accessibility, and no-secret output.
- Update directly impacted documentation.
- Do not close the requirement merely because code or a PR exists.
- End with a concise handoff listing files changed, behavior added, tests run/results, limitations, and remaining human evidence or stakeholder validation.
<!-- END STAKEHOLDER REQUIREMENTS AUTOMATION -->
'@
    $existing = ""
    if (Test-Path -LiteralPath $instructionsPath) { $existing = Get-Content -LiteralPath $instructionsPath -Raw }
    if ($existing -match [regex]::Escape($marker) -and $existing -match [regex]::Escape($endMarker)) {
        $pattern = "(?s)" + [regex]::Escape($marker) + ".*?" + [regex]::Escape($endMarker)
        $updated = [regex]::Replace($existing, $pattern, $block.Trim())
    } elseif ([string]::IsNullOrWhiteSpace($existing)) {
        $updated = $block.Trim() + "`r`n"
    } else {
        $updated = $existing.TrimEnd() + "`r`n`r`n" + $block.Trim() + "`r`n"
    }
    Write-Utf8File -Path $instructionsPath -Content $updated

    $prompt = @'
---
mode: agent
description: Implement one external stakeholder requirement issue with focused code, tests, documentation, and handoff.
---

Implement the GitHub issue currently in context.

Requirements:

1. Treat the issue body as the approved implementation prompt and acceptance contract.
2. Read `requirements/stakeholder-requirements.json`, `.github/copilot-instructions.md`, `AGENTS.md` when present, and directly affected governance files.
3. Inspect the current code before deciding which files to change.
4. Implement only the selected child requirement and unavoidable dependencies.
5. Preserve source traceability and source-derived versus reviewer-created state separation.
6. Never include the stakeholder's personal name, organization name, or organization domain.
7. Add focused automated tests and directly impacted documentation.
8. Run the narrowest relevant validation first, then the repository-required validation.
9. Do not create or merge a PR, deploy, or capture manual evidence unless explicitly instructed.
10. End with: summary, user-visible outcome, files changed, validation results, limitations, and exact remaining human evidence/stakeholder acceptance steps.
'@
    Write-Utf8File -Path ".github\prompts\implement-stakeholder-requirement.prompt.md" -Content $prompt

    $issueForm = @'
name: External stakeholder requirement
description: Create a traceable facility-intelligence requirement without identifying the stakeholder or organization.
title: "[Requirement] "
labels:
  - "initiative:facility-intelligence"
  - "needs:stakeholder-validation"
body:
  - type: markdown
    attributes:
      value: |
        Do not enter the stakeholder's personal name, organization name, or organization domain.
  - type: input
    id: requirement_id
    attributes:
      label: Requirement ID
      placeholder: STAKEHOLDER-009
    validations:
      required: true
  - type: textarea
    id: intended_outcome
    attributes:
      label: Intended attorney-review outcome
      description: Describe what the reviewer must be able to do and why it matters.
    validations:
      required: true
  - type: textarea
    id: current_gap
    attributes:
      label: Current gap
      description: Explain what RecordsTracker does today and why it does not satisfy the requirement.
    validations:
      required: true
  - type: textarea
    id: acceptance
    attributes:
      label: Functional acceptance criteria
      description: Use testable checklist items, including source reconciliation and edge states.
      value: |
        - [ ] 
        - [ ] 
    validations:
      required: true
  - type: textarea
    id: evidence
    attributes:
      label: Required evidence and stakeholder confirmation
      value: |
        - [ ] Automated validation complete
        - [ ] Exact route or output reviewed
        - [ ] Representative results reconciled to sources
        - [ ] Stakeholder scenario completed
        - [ ] Remaining gaps recorded
    validations:
      required: true
'@
    Write-Utf8File -Path ".github\ISSUE_TEMPLATE\stakeholder-requirement.yml" -Content $issueForm

    $agent = @'
# Stakeholder Requirement Implementation Agent

Use this profile for one issue containing a `recordstracker-requirement-id` marker.

## Mission

Implement the selected child requirement as a narrow, reviewable change that satisfies its acceptance criteria and preserves RecordsTracker governance.

## Required behavior

- Read the issue body, `requirements/stakeholder-requirements.json`, `.github/copilot-instructions.md`, `AGENTS.md` when present, and directly affected governance files.
- Never use the stakeholder's personal name, organization name, or organization domain.
- Preserve source traceability, deterministic processing, accessibility, and source-derived/reviewer-created separation.
- Do not introduce hidden scores or unsupported conclusions.
- Add focused tests and directly impacted documentation.
- Stop after implementation and validation with a concise handoff unless explicitly asked to do more.
'@
    Write-Utf8File -Path ".github\agents\stakeholder-requirement-agent.md" -Content $agent

    $setup = @'
name: Copilot Setup Steps

on:
  workflow_dispatch:

jobs:
  copilot-setup-steps:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install project
        run: |
          python -m pip install --upgrade pip
          if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
          if [ -f pyproject.toml ]; then pip install -e .; fi
'@
    if (-not (Test-Path -LiteralPath ".github\workflows\copilot-setup-steps.yml")) {
        Write-Utf8File -Path ".github\workflows\copilot-setup-steps.yml" -Content $setup
    }

    Write-Host "Generated repository requirement, Copilot, prompt, agent, issue-form, and optional setup files."
}

if (-not $GenerateFiles -and -not $SyncIssues) {
    $GenerateFiles = $true
}

if ($GenerateFiles) {
    Generate-RepositoryFiles
}

if ($SyncIssues) {
    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw "GitHub CLI (gh) is required." }
    & gh auth status | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "GitHub CLI is not authenticated. Run: gh auth login" }

    $Repository = Resolve-Repo
    Write-Host "Target repository: $Repository"

    foreach ($label in $labelDefinitions) {
        if ($PSCmdlet.ShouldProcess("$Repository label $($label.Name)","Create or update")) {
            Ensure-Label -Repository $Repository -Name $label.Name -Color $label.Color -Description $label.Description
        }
    }

    $issueMap = @{}

    $epic = $requirements | Where-Object { $_.id -eq "STAKEHOLDER-EPIC" } | Select-Object -First 1
    $existingEpic = Get-IssueByRequirementId -Repository $Repository -RequirementId $epic.id
    if ($existingEpic) {
        $issueMap[$epic.id] = $existingEpic
        Write-Host "Found existing epic #$($existingEpic.number): $($existingEpic.title)"
    } else {
        $temp = Join-Path $env:TEMP "recordstracker-$($epic.id).md"
        Write-Utf8File -Path $temp -Content (New-IssueBody -Requirement $epic -IssueMap $issueMap -IsEpic)
        if ($PSCmdlet.ShouldProcess("$Repository issue '$($epic.title)'","Create")) {
            $url = (& gh issue create --repo $Repository --title $epic.title --body-file $temp --label ($epic.labels -join ",")).Trim()
            if ($LASTEXITCODE -ne 0) { throw "Failed to create epic." }
            $created = Invoke-GhJson -Arguments @("issue","view",$url,"--repo",$Repository,"--json","number,title,url,state")
            $issueMap[$epic.id] = $created
            Write-Host "Created epic #$($created.number): $($created.url)"
        }
    }

    foreach ($requirement in $requirements | Where-Object { $_.id -ne "STAKEHOLDER-EPIC" }) {
        $existing = Get-IssueByRequirementId -Repository $Repository -RequirementId $requirement.id
        if ($existing) {
            $issueMap[$requirement.id] = $existing
            Write-Host "Found existing issue #$($existing.number): $($existing.title)"
            continue
        }
        $temp = Join-Path $env:TEMP "recordstracker-$($requirement.id).md"
        Write-Utf8File -Path $temp -Content (New-IssueBody -Requirement $requirement -IssueMap $issueMap)
        if ($PSCmdlet.ShouldProcess("$Repository issue '$($requirement.title)'","Create")) {
            $url = (& gh issue create --repo $Repository --title $requirement.title --body-file $temp --label ($requirement.labels -join ",")).Trim()
            if ($LASTEXITCODE -ne 0) { throw "Failed to create issue $($requirement.id)." }
            $created = Invoke-GhJson -Arguments @("issue","view",$url,"--repo",$Repository,"--json","number,title,url,state")
            $issueMap[$requirement.id] = $created
            Write-Host "Created issue #$($created.number): $($created.url)"
        }
    }

    if ($issueMap.ContainsKey("STAKEHOLDER-EPIC")) {
        $tempEpic = Join-Path $env:TEMP "recordstracker-STAKEHOLDER-EPIC-final.md"
        Write-Utf8File -Path $tempEpic -Content (New-IssueBody -Requirement $epic -IssueMap $issueMap -IsEpic)
        if ($PSCmdlet.ShouldProcess("$Repository issue #$($issueMap["STAKEHOLDER-EPIC"].number)","Update linked child checklist")) {
            & gh issue edit $issueMap["STAKEHOLDER-EPIC"].number --repo $Repository --body-file $tempEpic | Out-Null
            if ($LASTEXITCODE -ne 0) { throw "Failed to update epic child checklist." }
        }
    }

    if (-not [string]::IsNullOrWhiteSpace($AssignRequirementId)) {
        if ($AssignRequirementId -eq "STAKEHOLDER-EPIC" -or $AssignRequirementId -eq "STAKEHOLDER-008") {
            throw "Assign a single implementation child issue, not the epic or final acceptance issue."
        }
        if (-not $issueMap.ContainsKey($AssignRequirementId)) {
            throw "Unknown or unavailable requirement ID: $AssignRequirementId"
        }
        if ($PSCmdlet.ShouldProcess("$Repository issue #$($issueMap[$AssignRequirementId].number)","Assign to Copilot")) {
            & gh issue edit $issueMap[$AssignRequirementId].number --repo $Repository --add-assignee "@copilot" | Out-Null
            if ($LASTEXITCODE -ne 0) {
                Write-Warning "Could not assign #$($issueMap[$AssignRequirementId].number) to Copilot. Assign it from GitHub.com if Copilot cloud agent is enabled for this repository."
            }
        }
    }

    $manifest = [ordered]@{
        generated_at = [DateTime]::UtcNow.ToString("o")
        repository = $Repository
        privacy = "No stakeholder personal name, organization name, or organization domain is included."
        issues = @($requirements | ForEach-Object {
            $item = $issueMap[$_.id]
            [ordered]@{
                requirement_id = $_.id
                title = $_.title
                number = if ($item) { $item.number } else { $null }
                url = if ($item) { $item.url } else { $null }
                state = if ($item) { $item.state } else { $null }
            }
        })
    }
    Write-Utf8File -Path $OutputManifest -Content ($manifest | ConvertTo-Json -Depth 8)
    Write-Host "Wrote manifest: $OutputManifest"

    if ($OpenIssues) {
        foreach ($item in $issueMap.Values) {
            if ($item.url) { Start-Process $item.url }
        }
    }
}
