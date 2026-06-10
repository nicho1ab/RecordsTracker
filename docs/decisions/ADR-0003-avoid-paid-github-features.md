# ADR-0003: Avoid Paid GitHub Features in Baseline Workflow

## Status

Accepted

## Context

The user does not want to pay for GitHub features not included in their University of Illinois GitHub Enterprise account/organization.

## Decision

The baseline workflow will use local VS Code, GitHub repository files, GitHub Actions where available, branch protection/rulesets where available, and repository Copilot instructions. It will avoid depending on Codespaces, GitHub Advanced Security paid features, Copilot Enterprise-only features, or metered usage beyond included quotas.

## Reason

The project should remain portable and usable without unexpected billing.

## Consequences

- Local development is the primary workflow.
- GitHub Actions workflows are lightweight and can be disabled if organization policy or usage limits require it.
- Security scanning is handled through free/local tools in the baseline.
