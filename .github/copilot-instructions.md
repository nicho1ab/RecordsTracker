# Repository Instructions for GitHub Copilot

You are assisting with a governed public-data ingestion and extraction project.

## Agent capability precedence

`AGENTS.md` and `docs/developer/codex-workflow.md` define the repository
capability model for every agent interface: RO, II, HV-READ, HV-WORKFLOW,
RL-PREPARE, RL-MERGE, and HQ. The model defines maximum authority; it does not
create unavailable tools. An agent may act only when repository governance
authorizes the capability and the active environment supports it. Stop and
report an unavailable capability or tool instead of substituting another
mechanism.

Every task must include the full required authorization fields defined in
`AGENTS.md`, including the verified base SHA, granted capabilities, phase
sequence and stop points, exact branch/worktree and file scope, browser/network
allowlists, validation/evidence, required checks, merge grant, and prohibited
actions. Capabilities expire at the exact task stop point and do not carry into
another task or conversation.

The preferred sequence is II implementation and validation, then HV-READ or
HV-WORKFLOW evidence, then RL-PREPARE lifecycle preparation, with a stop and
report after each phase. Continuous execution must be explicitly authorized
with the exact sequence. RL-MERGE always requires separate current-task user
authorization. No session may continue into another issue or roadmap task.

For conditional queued phases and acceptance evidence, follow the detailed
fail-closed transition and evidence-lifecycle policy in
`docs/developer/codex-workflow.md`. A successful earlier phase does not grant a
later phase; deployment and issue closure remain separate explicit decisions.

## Task-relevant context

Treat the current complete GitHub issue as the durable task specification.
Before changing behavior, read `AGENTS.md`, this file, and the task-specific
governing documents, implementation, and tests that materially apply. Do not
require every ADR, design record, source contract, deployment document, or
project-history record unless the task reaches that area. List governing files
actually read, and report only conflicts or material findings.

For Python validation, follow the documented shared primary-repository runtime
convention for secondary worktrees. Resolve documented prerequisites before
reporting a blocker; do not invent a local environment or speculative executable
variant.

## Hard rules

- Do not invent canonical fields outside `DATA_CONTRACT.md`.
- Do not change schema without updating schemas, docs, tests, and migration/init SQL.
- Do not add a source connector unless it follows `SOURCE_CONNECTOR_CONTRACT.md`.
- Do not modify extraction behavior without adding or updating fixture-based regression tests.
- Do not use LLM extraction for fields that can be deterministically parsed.
- Avoid project dependencies on optional paid platform features.
- Do not introduce inaccessible user-facing output.
- Do not make user-facing workflow, documentation, output, interface, or visual design changes without following `DESIGN_AND_USABILITY.md`.
- Do not preserve outdated visible scaffold/helper/debug UI on reviewer-facing pages when the current RecordsTracker product-tier direction says to remove or move it. Update conflicting tests and docs instead, while preserving source traceability and operator/developer diagnostics in the appropriate tier.
- Do not remove source traceability.
- Do not delete raw source preservation behavior.
- Do not store secrets in the repo.
- Under RL-PREPARE, when GitHub CLI is installed and authenticated, prefer `gh`
	for the assigned branch and single PR, including viewing PR status, waiting
	for checks, and editing the PR body. Squash merge and cleanup require
	separately granted RL-MERGE. Do not print, paste, commit, or document GitHub
	tokens or authentication secrets.
- The `main` branch must be protected by a GitHub branch protection rule or repository ruleset
	that requires pull requests and requires the `validate`,
	`docs-check`, `fixtures`, and `security` status checks to pass before merge.
	Do not recommend or perform a squash merge unless those required checks have
	passed and the PR has no merge blockers.
- When a bug, CI failure, or repeated review correction exposes a missing or
	weakable governance rule, update the relevant governance, testing, fixture,
	or workflow documentation in the same task. If no governance rule is needed,
	explicitly state why in the handoff or PR body.
- When raw fixtures are used for expected hashes, compute and verify hashes from
	Git-normalized fixture bytes governed by `.gitattributes`, not from a local
	working-tree copy with platform-specific line endings.

## Required change behavior

For every code change:

1. Keep the change small.
2. Add or update tests.
3. Update developer docs if developer behavior changes.
4. Update user docs if user-visible behavior changes.
5. Update known limitations if limitations change.
6. Check documentation impact across `README.md`, `docs/user/*`, `docs/developer/*`, `DATA_CONTRACT.md`, `SOURCE_CONNECTOR_CONTRACT.md`, `KNOWN_LIMITATIONS.md`, `DESIGN_AND_USABILITY.md`, `DECISIONS.md`, and ADRs.
7. If no documentation changes are needed, explicitly state that no user-facing or documentation-impacting behavior changed.
8. Explain validation commands.
   For a focused bug fix, run the new regression independently, the smallest
   affected test set, targeted Ruff and mypy, documentation validation when
   documentation or governed behavior changes, and `git diff --check`. Do not
   run the complete local suite by default; reserve it for explicit requests,
   broad or cross-cutting changes, release-level validation, or investigation
   that focused or CI results require.
9. For bug or CI-failure fixes, describe the root cause and whether a new or
	updated governance rule was added to prevent recurrence.
10. Before using authorized RL-PREPARE or RL-MERGE GitHub CLI automation, verify `gh --version` and
	`gh auth status` work in the VS Code terminal without printing tokens. When
	`gh` is available, use it within the granted phase to verify PR state and
	required checks. Do not merge or clean up during RL-PREPARE.

## Required task handoff

Implementation and RL-PREPARE handoffs are concise: outcome; root cause where
applicable; changed files; focused validation; documentation or governance
impact; PR number and state when applicable; blockers; and the exact stop
point. Include a manual command only when an authorized action remains for the
human; do not reproduce unused commit, push, or PR commands after Codex has
already completed them. A next-task suggestion never grants that task's
authority.

Do not start an unattended loop through multiple roadmap tasks after a merge.
Continue only when the user explicitly authorizes the next task in the current
conversation.

Do not include personal paths, usernames, account-specific URLs, private URLs,
tokens, secrets, or machine-specific details in the handoff. Use placeholders
when a repository owner, branch, or pull request URL is unknown.

Required GitHub checks must be named by status-check context in the handoff:
`validate`, `docs-check`, `fixtures`, and `security`. If GitHub does not show
those checks as required by branch protection or repository rulesets, stop before
merge and tell the user to fix repository protection for `main`.

These required checks provide broader pre-merge validation for ordinary focused
changes. Focused local validation does not weaken or replace them, and unrun
validation must never be presented as passed.

## Preferred stack

- Python
- SQLite
- Datasette
- pytest
- ruff
- mypy
- jsonschema

## Accessibility

All user-facing docs, exports, and presentation layers must meet `ACCESSIBILITY_REQUIREMENTS.md`.
Public repository hygiene:
Do not include personal local paths, usernames, personal email addresses, organization account details, private URLs, tokens, secrets, screenshots containing private account details, or machine-specific configuration in committed documentation, examples, fixtures, comments, or tests. Use placeholders such as <repo-root>, <local-project-path>, <your-github-org-or-user>, and <repository-name>.

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

Specific prohibited identity values include:

- stakeholder personal names;
- stakeholder organization names, abbreviations, and domains;
- the user's employer and institutional affiliations, including their acronyms;
- personal or institutional email addresses;
- private or test hostnames.

The repository identity check must treat organization acronyms as standalone terms so ordinary words and code identifiers containing the same letters are not false positives.

## Reviewer-facing design implementation rules

- Material reviewer-facing redesigns must use
  `docs/product/records-tracker-reviewer-redesign-artifact-governance.md`.
  Before coding, classify affected tests, evidence assertions, documentation,
  routes, accessibility requirements, changelog text, and design requirements.
  The PR and handoff must identify which assertions were preserved, rewritten,
  removed, or retained as history and why. Unexplained preservation of
  superseded UI or removal of a durable protection is a stop condition.
- A reviewer-facing redesign must not introduce accordion- or disclosure-based primary content unless the approved design blueprint explicitly requires it.
- Tests expecting generic `<details>` markup do not override approved product direction. Update stale tests rather than preserving an unapproved disclosure-heavy layout.
- Do not duplicate the same complaint under multiple aggregate headings. Implement one canonical complaint inventory and connect metrics through filters, chips, highlighting, or links.
- Do not use generic complaint labels when governed allegation topics, findings, or deficiency categories can provide meaningful source-backed wording.
- Before completing a source-field display task, report the full path: source label, extractor, normalized field, canonical allocation, database storage, import/backfill, read model, and rendered component.
- For important UI work, implement the exact approved Figma/design package. Produce pre-code and post-code variance inventories. Material unapproved visual variance is a stop condition.
- Do not default to teal primary and muted accents. Use the approved token package and approved traffic-light protocol colors for their intended semantics, paired with text and accessible labels.
- A repeated user rejection of a visual pattern is evidence of a missing or weak governance rule. Add the narrow preventive rule in the same task.

## QNAP release deployment authority

For QNAP deployment, verification, hosted acceptance, or rollback, follow the authoritative [QNAP Release Deployment Runbook](docs/developer/qnap-release-deployment-runbook.md). Do not invent or substitute another deployment procedure.
