# Repository Instructions for GitHub Copilot

You are assisting with a governed public-data ingestion and extraction project.

## Agent precedence

These Copilot-oriented PR, check, merge, and cleanup automation instructions do
not override `AGENTS.md` or `docs/developer/codex-workflow.md` when the acting
agent is Codex. Codex must follow the stricter local Codex boundaries unless the
current task explicitly authorizes the exact GitHub action.

## Required context files

Before making changes, read and follow:

- `PROJECT_CHARTER.md`
- `DECISIONS.md`
- `DATA_CONTRACT.md`
- `SOURCE_CONNECTOR_CONTRACT.md`
- `TESTING_STRATEGY.md`
- `DOCUMENTATION_STRATEGY.md`
- `DESIGN_AND_USABILITY.md`
- `ACCESSIBILITY_REQUIREMENTS.md`
- `SECURITY_AND_PRIVACY.md`
- `KNOWN_LIMITATIONS.md`

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
- When GitHub CLI is installed and authenticated, prefer `gh` for repeatable PR
	operations such as viewing PR status, waiting for checks, editing PR bodies,
	and squash merging after required checks pass. Do not print, paste, commit, or
	document GitHub tokens or authentication secrets.
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
10. Before using GitHub CLI automation, verify `gh --version` and
	`gh auth status` work in the VS Code terminal without printing tokens. When
	`gh` is available, use it to verify PR state and required checks before
	telling the user to merge or clean up a branch.

## Required task handoff

At the end of every completed task, provide a self-contained handoff that lets
the user finish the GitHub workflow and start the next Copilot task without
reconstructing context. Include all of the following:

1. Summary of changes.
2. Validation results, including commands run and whether each passed.
3. Exact git commit and push commands. For push commands, use
	`git -c gc.auto=0 push -u origin <branch-name>` to avoid auto-gc prompts.
4. PR title.
5. PR body, including test results and documentation impact.
6. Required GitHub checks to wait for before merge.
7. Post-merge cleanup commands.
8. Recommended next branch name.
9. Next Copilot prompt.

If GitHub CLI successfully creates the PR, verifies checks, completes the squash
merge, deletes the remote/local branch, and returns the workspace to updated
`main`, provide a concise completion summary instead of manual copy/paste
commands. Include PR number, validation/check results, merge status, current git
state, recommended next branch name, and exact next Copilot prompt. The next
branch and next Copilot prompt are always required, even when every GitHub step
was automated successfully. Use the full copy/paste-safe handoff when the user
still needs to complete any GitHub or git workflow step manually.

Do not start an unattended loop through multiple roadmap tasks after a merge.
Complete one small task, automate the PR lifecycle with `gh` when available,
return to updated `main`, then provide the next branch and exact next Copilot
prompt for the user to approve or send. Continue automatically only when the
user explicitly requests the next task in the current conversation.

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

## Handoff formatting rules

All completed-task handoffs must be copy/paste-safe for PowerShell users.

- Commands must be in separate fenced code blocks.
- Prose must never appear on the same line as a command.
- GitHub PR title/body must be separate from PowerShell commands.
- Post-merge cleanup commands must be clearly labeled "Run only after squash merge is complete."
- The next branch command must not be combined with cleanup commands.
- Do not concatenate commands together without a semicolon or newline.
- Prefer one short command block per step.
- For push commands, use `git -c gc.auto=0 push -u origin <branch-name>` to
	avoid auto-gc prompts.

## Next task selection

Do not repeatedly recommend documentation-only work in the next Copilot prompt.
Documentation-only work is appropriate only when documentation is stale,
validation is failing, governance files are missing, or the user explicitly asks
for documentation work. Otherwise, select the next product or technical milestone from `ROADMAP.md`.

Prefer feature work that improves ingestion, review usability, extraction
quality, exports, accessibility validation, or release readiness. The recommended
next branch and next Copilot prompt must move the project forward on that
roadmap backlog unless validation failed or documentation is stale.

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

- A reviewer-facing redesign must not introduce accordion- or disclosure-based primary content unless the approved design blueprint explicitly requires it.
- Tests expecting generic `<details>` markup do not override approved product direction. Update stale tests rather than preserving an unapproved disclosure-heavy layout.
- Do not duplicate the same complaint under multiple aggregate headings. Implement one canonical complaint inventory and connect metrics through filters, chips, highlighting, or links.
- Do not use generic complaint labels when governed allegation topics, findings, or deficiency categories can provide meaningful source-backed wording.
- Before completing a source-field display task, report the full path: source label, extractor, normalized field, canonical allocation, database storage, import/backfill, read model, and rendered component.
- For important UI work, implement the exact approved Figma/design package. Produce pre-code and post-code variance inventories. Material unapproved visual variance is a stop condition.
- Do not default to teal primary and muted accents. Use the approved token package and approved traffic-light protocol colors for their intended semantics, paired with text and accessible labels.
- A repeated user rejection of a visual pattern is evidence of a missing or weak governance rule. Add the narrow preventive rule in the same task.
