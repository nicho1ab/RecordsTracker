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
Create a failing regression test or fixture for this bug first. Then fix the smallest amount of code needed. Run or describe the validation commands I should run.
```

## Guardrails

- Do not accept broad rewrites.
- Do not accept schema changes without migration, docs, and tests.
- Do not accept extraction changes without fixture tests.
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

Use commands that avoid account-specific details when possible:

```powershell
git add <changed-files>
git commit -m "<concise imperative commit message>"
git push -u origin HEAD
```

Post-merge cleanup should usually be:

```powershell
git switch main
git pull --ff-only
git branch --delete <merged-branch-name>
git remote prune origin
git switch -c <next-branch-name>
```

The PR body should state whether user-facing or documentation-impacting behavior
changed. If no documentation changes are needed for a future task, use the exact
statement: no user-facing or documentation-impacting behavior changed.

The next Copilot prompt should point to the governance files and ask for the
smallest safe, tested change. Do not include personal paths, usernames, account
details, private URLs, tokens, secrets, or machine-specific configuration in the
handoff.

## Next task selection

Do not repeatedly recommend documentation-only work in the next Copilot prompt.
Documentation-only work is appropriate only when documentation is stale,
validation is failing, governance files are missing, or the user explicitly asks
for documentation work. Otherwise, select the next product or technical milestone from `ROADMAP.md`.

Prefer feature work that improves ingestion, review usability, extraction
quality, exports, accessibility validation, or release readiness. The recommended
next branch and next Copilot prompt must move the project forward on the current
roadmap backlog unless validation failed or documentation is stale.
