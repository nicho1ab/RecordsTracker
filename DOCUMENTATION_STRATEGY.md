# Documentation Strategy

## Audiences

### Developer audience

Developers need setup, architecture, connector rules, testing rules, release process, and troubleshooting guidance.

### End-user audience

End users need plain-language instructions for browsing, searching, filtering, understanding fields, exporting data, and understanding limitations.

## Required developer docs

- `docs/developer/setup.md`
- `docs/developer/copilot-workflow.md`
- `docs/developer/architecture.md`
- `docs/developer/adding-a-source.md`
- `docs/developer/testing.md`
- `docs/developer/data-contract.md`
- `docs/developer/accessibility.md`
- `docs/developer/release-process.md`

## Required user docs

- `docs/user/getting-started.md`
- `docs/user/reviewing-records.md`
- `docs/user/searching-and-filtering.md`
- `docs/user/data-dictionary.md`
- `docs/user/exporting-data.md`
- `docs/user/known-limitations.md`

## Update rules

- If user-visible behavior changes, update user docs.
- If developer workflow changes, update developer docs.
- If schema changes, update data dictionary and schemas.
- If connector behavior changes, update connector docs and known limitations.
- If accessibility behavior changes, update accessibility docs and test notes.

## Public documentation hygiene

Public documentation, examples, templates, and repository metadata must avoid personal or environment-specific details. Do not publish personal names, handles, email addresses, local machine names, private URLs, tokens, secrets, or machine-specific paths.

Use neutral placeholders in public examples:

- `<repo-root>` for the repository root.
- `<local-project-path>` for local filesystem paths.
- `<your-github-org-or-user>` for GitHub owners.
- `<repository-name>` for repository names.

Do not include account-specific billing or entitlement details. State the governance rule as: avoid project dependencies on optional paid platform features.
