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