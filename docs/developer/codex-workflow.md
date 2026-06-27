# Codex Workflow

This repository can be worked on with local Codex, but Codex should be treated as a controlled local engineering agent, not as an autonomous deployment operator.

## Default local posture

Recommended user-level Codex defaults:

```toml
model = "gpt-5.5"
approval_policy = "on-request"
sandbox_mode = "workspace-write"

[sandbox_workspace_write]
network_access = false
```

This lets Codex read and edit the active workspace while keeping network activity, remote access, browser/computer-use, and external tooling out of the default path.

## Role split

- ChatGPT/project architect: scope review, prompt review, risk gate, final review.
- Codex local: multi-file repo implementation, focused refactoring, validation, and test fixes.
- GitHub Copilot: narrow editor assistance.
- Human operator: final approval, QNAP actions, protected-branch merge authority until Codex is proven on this repo.

## Do not enable by default

Do not enable these for normal RecordsTracker work unless explicitly required by the current task:

- MCP servers.
- Browser/computer-use.
- QNAP SSH or remote shell access.
- Cloudflare/admin-console access.
- GitHub token pages or repository settings access.
- Automatic PR merge/delete-branch workflows.
- Access to `.env`, deployment secrets, private keys, cookies, or tokens.

## Safe first tasks

Good early Codex tasks:

- Repo-wide audit with no edits.
- Small docs/script cleanup that improves operator reliability.
- Focused bug fix with clear tests.
- QNAP operator workflow simplification limited to docs/scripts and no SSH.

Avoid starting with broad UI rewrites, deployment automation, live retrieval, Cloudflare work, or destructive reset/import flows.

## Worktrees

Worktrees are useful after the repo-level guardrails are committed. Do not copy `.env`, QNAP credentials, private host details, generated data, or evidence packets into Codex-managed worktrees.

## Validation

For code changes, normally run:

```powershell
.\scripts\lint.ps1
.\scripts\test.ps1
.\scripts\docs.ps1
```

For docs-only changes, normally run:

```powershell
.\scripts\docs.ps1
git diff --check
```

Use narrower focused tests first when appropriate, but do not present unrun validation as passed.
