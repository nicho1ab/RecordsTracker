# Copilot Workflow

## Primary rule

Use chat to ask Copilot for small, scoped, validated changes. Always point
Copilot to governance files before requesting code, documentation, governance,
architecture, phase-transition, or prototype work.

## Recommended first prompt in VS Code Chat

```text
Read .github/copilot-instructions.md, PROJECT_CHARTER.md, DATA_CONTRACT.md, SOURCE_CONNECTOR_CONTRACT.md, TESTING_STRATEGY.md, DOCUMENTATION_STRATEGY.md, DESIGN_AND_USABILITY.md, ACCESSIBILITY_REQUIREMENTS.md, and DECISIONS.md. Summarize the project rules you must follow before making code changes.
```

## Prompt types

### Analysis-only prompts

Use analysis-only prompts when you want Copilot to inspect code, docs, issues,
test failures, or architecture options without editing files.

```text
Read the governance files and analyze <question or risk>. Do not edit files, run
mutating commands, create branches, or open a PR. Summarize findings, open
questions, and recommended next steps.
```

Analysis-only work may challenge assumptions and identify stale governance, but
it must not weaken source traceability, raw source preservation, deterministic
extraction, fixture-backed regression expectations, accessibility, security,
privacy, or public-source caution language.

### Governance-change proposals

Use governance-change prompts when rules, decision logs, roadmap language,
testing policy, documentation policy, or workflow guidance may need to change.

```text
Using the governance files, propose and implement the smallest governance update
for <change>. Preserve non-negotiable safeguards, update related docs that would
otherwise become stale, run focused documentation validation first, then standard
PR validation.
```

Governance may be challenged when project phase, reviewer needs, validation
evidence, CI failures, repeated review corrections, or architecture decisions
show that prior assumptions are stale. Source traceability, raw source
preservation, deterministic extraction where reliable, fixture-backed regression
coverage, accessibility, security/privacy, schema-change discipline, connector
contract discipline, and public-source caution language remain strict.

### Architecture decision reviews

Use architecture decision review prompts when comparing boundaries, tradeoffs, or
stack options. These prompts should produce or update ADRs and should not select
or implement a production stack unless the task explicitly asks for that decision
and the required context is available.

```text
Read the governance files and current ADRs. Review the architecture decision for
<topic>, compare options, preserve the non-negotiable safeguards, and draft the
smallest ADR or ADR update needed. Do not build the implementation.
```

### Implementation tasks

Use implementation prompts for code, schema, connector, extraction, export,
review-view, or script changes.

## Add a feature prompt

```text
Using the governance files, implement the smallest safe version of <feature>. Add or update tests, update developer docs and user docs if behavior changes, and do not change the data contract unless you explain why first.
```

## Fix a bug prompt

```text
Create a failing regression test or fixture for this bug first. Then fix the smallest amount of code needed. Identify the root cause and update governance rules if a missing or unclear rule allowed the bug. Run or describe the validation commands I should run.
```

Implementation work must keep schema, extraction, connector, traceability,
accessibility, privacy, and documentation impacts explicit. Do not treat focused
validation as a substitute for standard PR validation.

### Phase-transition tasks

Use phase-transition prompts when the project moves from POC to local
attorney-review aid, production-discovery, production-build, or production
operations governance.

```text
Implement the smallest phase-transition governance update for <phase change>.
Preserve non-negotiable safeguards, mark prior decisions as historical or
superseded only where applicable, update roadmap/design/architecture/workflow
docs that would otherwise become misleading, and do not build application code.
```

Phase-transition work may supersede stale POC-era assumptions. It must not remove
source traceability, raw source preservation, deterministic extraction
expectations, fixture-backed regression expectations, accessibility,
security/privacy, public-source caution language, or schema/connector governance.

### Prototype and spike tasks

Use prototype or spike prompts to explore uncertain approaches before production
commitment. Spikes should be clearly labeled, small, reversible, and separated
from production decisions.

```text
Create a small prototype or spike for <question>. Keep it isolated, document what
it proves and does not prove, avoid new baseline dependencies unless explicitly
approved, preserve source traceability and accessibility constraints, and do not
present it as the production stack decision.
```

## Guardrails

- Do not accept broad rewrites.
- Do not accept schema changes without migration, docs, and tests.
- Do not accept extraction changes without fixture tests.
- Do not accept bug or CI-failure fixes that skip root-cause governance review.
- Do not skip standard PR validation for implementation work.
- Use focused validation first to catch likely failures quickly, and explain why
	the focused tests matched the changed area.
- When a bug or CI failure reveals a missing or unclear rule, update the relevant
	governance, testing, fixture, connector, or workflow documentation in the same
	change.
- Ask Copilot to show changed files and summarize validation results.

## Validation guidance

Use tiered validation for implementation work.

### Focused validation

Before broader validation, run the smallest relevant tests for the changed area.
Examples:

- Extraction change: targeted extractor tests and related fixture regression tests.
- Connector change: targeted connector discovery, fetch, and raw storage tests using fixtures or mocks.
- Data contract or schema change: schema validation, init or migration SQL tests, persistence tests, and affected data dictionary checks.
- Datasette, view, or export change: affected SQL, view, export, metadata, and documentation checks.
- Documentation-only change: documentation validation and link or reference checks.
- Security or privacy change: security checks and any affected tests.
- Accessibility-facing change: documentation, export, view, or presentation accessibility checks.

Copilot should state which focused validation it selected and why it matched the
change.

### Standard PR validation

Run standard PR validation before every PR unless the task is analysis-only and
no files were edited:

```powershell
.\scripts\lint.ps1
```

```powershell
.\scripts\test.ps1
```

```powershell
.\scripts\docs.ps1
```

```powershell
git diff --check
```

### Required remote validation

Before merge, verify the required GitHub checks pass:

- `validate`
- `docs-check`
- `fixtures`
- `security`

### Full release validation

Run or verify the full test suite before any release, production-readiness
milestone, schema change, connector expansion, export-contract change, or
production architecture transition.

## Required completion handoff

Every completed Copilot task must end with a handoff that includes:

- Summary of changes.
- Validation results, including exact commands run and whether each passed.
- Exact git commit and push commands.
- PR title.
- PR body.
- Required GitHub checks to wait for before merge.
- Post-merge cleanup commands.
- Recommended next branch name.
- Next Copilot prompt.

When GitHub CLI completes the PR workflow for the user, including PR creation,
check verification, squash merge, branch deletion, and returning the workspace
to updated `main`, the final response may be a concise completion summary rather
than a manual copy/paste handoff. Include the PR number, validation/check
results, merge status, current git state, recommended next branch name, and exact
next Copilot prompt. The next branch and next Copilot prompt are always required,
even when all GitHub work was automated. Use the full handoff format when any
GitHub or git step remains for the user.

Copilot should not run an unattended loop through the entire roadmap. Each task
should remain small, reviewed, validated, and merged independently. After a
successful automated merge, Copilot may recommend the next roadmap task and
provide the exact next prompt, but should wait for the user to send or approve
that prompt unless the user explicitly asks to continue in the current
conversation.

Use commands that avoid account-specific details when possible:

```powershell
git add <changed-files>
git commit -m "<concise imperative commit message>"
git -c gc.auto=0 push -u origin <branch-name>
```

When GitHub CLI is installed and authenticated, Copilot may use `gh` to reduce
manual PR work. Prefer these commands for repeatable PR operations:

```powershell
gh --version
```

```powershell
gh auth status
```

Only use `gh` automation when both commands work in the VS Code terminal. Never
print, paste, commit, or document token values from authentication output.

```powershell
gh pr view --json number,state,isDraft,mergeStateStatus,url,statusCheckRollup
```

```powershell
gh pr checks --watch
```

The `main` branch must be protected by a GitHub branch protection rule or repository ruleset
that requires pull requests and requires the `validate`,
`docs-check`, `fixtures`, and `security` status-check contexts to pass before
squash merge. Copilot must stop before merge if GitHub does not report those
checks as passing or if repository protection does not require them.

```powershell
gh pr merge --squash --delete-branch
```

Use `gh pr merge --squash --auto --delete-branch` only when repository
auto-merge is enabled and required checks are expected to pass. Never include
GitHub tokens, one-time authentication codes, or other secrets in handoffs,
documentation, PR bodies, logs, or commits.

Post-merge cleanup should usually be labeled "Run only after squash merge is complete":

```powershell
git switch main
git pull --ff-only
git branch --delete <merged-branch-name>
git remote prune origin
```

Create the next branch in a separate command block:

```powershell
git switch -c <next-branch-name>
```

The PR body should state whether user-facing or documentation-impacting behavior
changed. If no documentation changes are needed for a future task, use the exact
statement: no user-facing or documentation-impacting behavior changed.

The PR body must also include:

- Focused validation run.
- Why those focused tests matched the change.
- Full local validation results.
- Required remote check results.
- Any tests intentionally not run and why.

The next Copilot prompt should point to the governance files and ask for the
smallest safe, tested change. Do not include personal paths, usernames, account
details, private URLs, tokens, secrets, or machine-specific configuration in the
handoff.

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
next branch and next Copilot prompt must move the project forward on the current
roadmap backlog unless validation failed or documentation is stale.
