# ADR-0003: Avoid Optional Paid Platform Dependencies in Baseline Workflow

## Status

Accepted

## Context

The project should be usable without depending on optional paid platform features or account-specific entitlements.

## Decision

The baseline workflow will use local VS Code, repository files, GitHub Actions where available, branch protection or rulesets where available, and repository Copilot instructions. It will avoid project dependencies on optional paid platform features such as hosted development environments, advanced security add-ons, enterprise-only assistant features, or metered services unless explicitly approved.

## Reason

The project should remain portable and usable without unexpected billing.

## Consequences

- Local development is the primary workflow.
- GitHub Actions workflows are lightweight and can be disabled if project policy or usage limits require it.
- Security scanning is handled through free/local tools in the baseline.
