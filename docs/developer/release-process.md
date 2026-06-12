# Release Process

## Task completion checklist

Use this checklist before handing a completed task back to the user or opening a
pull request.

### Validation

- Run linting and type checks:

	```powershell
	.\scripts\lint.ps1
	```

- Run the full test suite:

	```powershell
	.\scripts\test.ps1
	```

- Run the documentation check:

	```powershell
	.\scripts\docs.ps1
	```

- Record whether each command passed in the Copilot completion handoff and PR
	body.

### Accessibility review

- Review `ACCESSIBILITY_REQUIREMENTS.md` and `docs/developer/accessibility.md`
	for any user-facing documentation, Datasette output, export, or presentation
	change.
- Use the local output checklist in `docs/developer/accessibility.md` for
	Datasette views, generated metadata, saved queries, CSV exports, review bundle
	files, and script output.
- Confirm delay fields and review flags are described as screening aids, not
	conclusions.
- Confirm source traceability remains visible where reviewers may cite, export,
	or rely on derived records.
- Document any known accessibility blocker in `KNOWN_LIMITATIONS.md` before a
	stable release.

### Pull request checks

- Include validation results in the PR body.
- State whether user-facing or documentation-impacting behavior changed.
- For bug and CI-failure fixes, state the root cause and whether a governance
	rule was added or updated to prevent recurrence.
- Wait for Required GitHub checks to pass before merge, including CI,
	documentation, regression, and security checks when those workflows are
	enabled.
- When GitHub CLI is installed and authenticated, use `gh pr view` and
	`gh pr checks --watch` to verify PR status instead of relying on memory or
	manual browser refreshes. Do not include token values or authentication secrets
	in PR bodies, docs, handoffs, logs, or commits.

Useful status command:

```powershell
gh pr view --json number,state,isDraft,mergeStateStatus,url,statusCheckRollup
```

Useful checks command:

```powershell
gh pr checks --watch
```

### Squash merge automation

After required checks pass and no conflicts remain, GitHub CLI may perform the
squash merge and remote branch deletion:

```powershell
gh pr merge --squash --delete-branch
```

If repository auto-merge is enabled, set squash auto-merge so GitHub completes
the merge when checks pass:

```powershell
gh pr merge --squash --auto --delete-branch
```

When `gh` completes PR creation, check verification, squash merge, remote branch
deletion, and local branch cleanup, the completion note may summarize what was
done instead of giving the user manual PR and cleanup commands. Use the full
copy/paste-safe handoff when any GitHub or git step still needs user action.
Even in the abbreviated successful-`gh` completion note, include the recommended
next branch name and exact next Copilot prompt.

### Merge cleanup

After the PR merges, update `main`, delete the merged branch, and prune stale
remote-tracking branches:

```powershell
git switch main
git pull --ff-only
git branch --delete <merged-branch-name>
git remote prune origin
```

### Next-task handoff

End every completed Copilot task with the required handoff from
`docs/developer/copilot-workflow.md`: summary of changes, validation results,
exact commit and push commands, PR title, PR body, Required GitHub checks,
post-merge cleanup commands, recommended next branch name, and next Copilot
prompt. The handoff must include a next Copilot prompt that points to the
governance files and asks for the smallest safe, tested change.

Do not automatically continue through multiple roadmap items without a user
checkpoint. After an automated merge, return to updated `main`, summarize the
completed task, and provide the next branch and exact prompt for the user to
approve or send.

Start follow-up work from updated `main`:

```powershell
git switch main
git pull --ff-only
git switch -c <next-branch-name>
```

## Stable release checklist

- Tests pass.
- Linting passes.
- Documentation check passes.
- Accessibility checklist completed.
- Known limitations reviewed.
- Changelog updated.
- Version tag created if applicable.

## Versioning

Use semantic versioning after the first stable release.

Initial milestones:

- `v0.1.0`: Single-facility CCLD POC
- `v0.2.0`: Multi-facility support
- `v0.3.0`: Review workflow
- `v1.0.0`: Stable connector contract
