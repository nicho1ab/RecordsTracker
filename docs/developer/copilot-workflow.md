# Copilot Workflow

## Primary rule

Use chat to ask Copilot to make small, testable changes. Always point Copilot to governance files before requesting code changes.

## Recommended first prompt in VS Code Chat

```text
Read .github/copilot-instructions.md, PROJECT_CHARTER.md, DATA_CONTRACT.md, SOURCE_CONNECTOR_CONTRACT.md, TESTING_STRATEGY.md, DOCUMENTATION_STRATEGY.md, DESIGN_AND_USABILITY.md, ACCESSIBILITY_REQUIREMENTS.md, and DECISIONS.md. Summarize the project rules you must follow before making code changes.
```

## Add a feature prompt

```text
Using the governance files, implement the smallest safe version of <feature>. Add or update tests, update developer docs and user docs if behavior changes, and do not change the data contract unless you explain why first.
```

## Fix a bug prompt

```text
Create a failing regression test or fixture for this bug first. Then fix the smallest amount of code needed. Identify the root cause and update governance rules if a missing or unclear rule allowed the bug. Run or describe the validation commands I should run.
```

## Guardrails

- Do not accept broad rewrites.
- Do not accept schema changes without migration, docs, and tests.
- Do not accept extraction changes without fixture tests.
- Do not accept bug or CI-failure fixes that skip root-cause governance review.
- When a bug or CI failure reveals a missing or unclear rule, update the relevant
	governance, testing, fixture, connector, or workflow documentation in the same
	change.
- Ask Copilot to show changed files and summarize validation results.

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
