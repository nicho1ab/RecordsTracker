# Documentation Strategy

## Audiences

### Developer audience

Developers need setup, architecture, connector rules, testing rules, release process, and troubleshooting guidance.

### End-user audience

End users need plain-language instructions for browsing, searching, filtering, understanding fields, exporting data, and understanding limitations.

## Required developer docs

- `docs/developer/setup.md`
- `docs/developer/copilot-workflow.md`
- `docs/developer/codex-workflow.md`
- `docs/developer/development-loop-label-taxonomy.md`
- `docs/developer/development-loop-pilot-evidence.md`
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

## Required production-discovery docs

- `PRODUCTION_DISCOVERY_REQUIREMENTS.md`
- `GOVERNANCE_INVENTORY.md`
- `PUBLIC_SOURCE_DATA_INVENTORY.md`

Future hosted primary reviewer application work must keep this requirements
document current until ADRs and implementation docs supersede specific sections.
The governance inventory must stay current when the active phase, hosted
scaffold state, completed ADR assessment, deferred decisions, stale-guidance
assessment, or next-phase gap analysis changes.
The public-source data inventory must stay current when new source candidates,
uploaded examples, source metadata, parsing risks, source limitations,
multi-source planning assumptions, attorney focus-area planning, or feedback
intake planning changes.

## Update rules

- If user-visible behavior changes, update user docs.
- If developer workflow changes, update developer docs.
- If schema changes, update data dictionary and schemas.
- If connector behavior changes, update connector docs and known limitations.
- If accessibility behavior changes, update accessibility docs and test notes.
- If milestones, implemented capabilities, workflow scope, or deferred work
	changes, update `ROADMAP.md`.
- If hosted reviewer requirements, review-state boundaries, annotation or
  correction boundaries, tester-readiness expectations, or future primary review
  workflow scope changes, update `PRODUCTION_DISCOVERY_REQUIREMENTS.md`.
- If implemented capabilities or user-visible workflows change, update
	`CHANGELOG.md` under Unreleased.

## Documentation impact and currency

Every feature, workflow, source connector, CLI or script, database or view, or
user-facing behavior change must evaluate whether public, user, developer,
contract, limitation, design, and decision documentation needs to change.

At minimum, review these documentation surfaces for impact:

- `README.md`
- `GOVERNANCE_INVENTORY.md`
- `PUBLIC_SOURCE_DATA_INVENTORY.md`
- `ROADMAP.md`
- `CHANGELOG.md`
- `docs/user/*`
- `docs/developer/*`
- `DATA_CONTRACT.md`
- `SOURCE_CONNECTOR_CONTRACT.md`
- `KNOWN_LIMITATIONS.md`
- `DESIGN_AND_USABILITY.md`
- `DECISIONS.md and ADRs` in `docs/decisions/`

Not every change requires every document to change. However, every pull request
must either update affected documentation or explicitly state that no user-facing
or documentation-impacting behavior changed. In PR text, use a clear statement
such as: no user-facing or documentation-impacting behavior changed.

Root public documentation must describe the active CCLD complaints project and
its current phase, not obsolete scaffold, template, packaging, or stale
Datasette-primary POC language. The README must stay current with implemented
project capabilities, including local SQLite and Datasette validation/review
support, source traceability, fixture-backed tests, controlled live fetch
behavior, source-traceable exports, and production-discovery governance.

Documentation checks prevent stale, missing, or misleading documentation. They
should not become the default next milestone when validation is passing and the
documentation is current; future work should then come from the active roadmap
backlog.

## Redesign artifact currency

For a material reviewer-facing redesign, classify directly affected active and
historical documentation under
`docs/product/records-tracker-reviewer-redesign-artifact-governance.md`.
Current user and developer guidance must change with the implementation.
Accurate changelog entries, accepted evidence reports, and prior decision
records remain historical documentation and must not be rewritten to look
current or allowed to govern the replacement design.

An exact heading, route name, helper paragraph, disclosure, screenshot label,
or markup description in active documentation requires an approved design or
other durable reason. Otherwise update or remove it when the approved design
supersedes it. The PR and handoff must state which documentation assertions
were preserved, rewritten, removed, or retained as history.

## ChatGPT Project Sources precedence and currency

Repository `main` is authoritative. ChatGPT Project Sources are static
contextual copies and do not automatically update from GitHub. A Project Source
that mirrors a repository file must remain an exact unchanged copy; do not
prepend source metadata to the mirrored file.

A separate steering-only ChatGPT Project Source named
`CCLD RecordsTracker Project Sources Manifest.md` tracks each source's display
name, repository path or steering-only status, source commit SHA, upload date,
and current/stale status. The manifest is not part of this repository and must
not be created or committed here.

Similar filenames are not sufficient evidence that two Project Sources are
duplicates. Remove a superseded source only after verifying its identity,
replacement, readability, and lack of unique content.

Merged repository governance becomes authoritative immediately. Mirrored
Project Sources must be replaced before a ChatGPT Project relies on them as
current, but replacement is not a prerequisite for Codex to follow repository
`main` directly. Between merge and Project Source replacement, planning chats
must inspect repository `main`.

## Public documentation hygiene

Public documentation, examples, templates, and repository metadata must avoid personal or environment-specific details. Do not publish personal names, handles, email addresses, local machine names, private URLs, tokens, secrets, or machine-specific paths.

Use neutral placeholders in public examples:

- `<repo-root>` for the repository root.
- `<local-project-path>` for local filesystem paths.
- `<your-github-org-or-user>` for GitHub owners.
- `<repository-name>` for repository names.

Do not include account-specific billing or entitlement details. State the governance rule as: avoid project dependencies on optional paid platform features.
