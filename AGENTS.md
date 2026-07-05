# RecordsTracker Agent Instructions

These instructions apply to Codex, GitHub Copilot, and any other coding agent working in this repository.

## Required context before changing behavior

Before making code, schema, extraction, hosted reviewer, export, QNAP, or user-facing documentation changes, read the relevant parts of:

- `PROJECT_CHARTER.md`
- `ROADMAP.md`
- `DECISIONS.md`
- `DATA_CONTRACT.md`
- `SOURCE_CONNECTOR_CONTRACT.md`
- `ARCHITECTURE.md`
- `TESTING_STRATEGY.md`
- `DOCUMENTATION_STRATEGY.md`
- `DESIGN_AND_USABILITY.md`
- `ACCESSIBILITY_REQUIREMENTS.md`
- `SECURITY_AND_PRIVACY.md`
- `KNOWN_LIMITATIONS.md`
- `.github/copilot-instructions.md`

Read only the context needed for the task; do not rewrite governance just because it exists.

## Product direction

- Keep work moving toward a user-facing hosted tester/pilot build of RecordsTracker.
- Prefer changes that let a tester, reviewer, or operator do something concrete that they could not do before.
- Avoid governance-only, scaffold-only, polish-only, or documentation-only work unless it fixes stale/incorrect guidance, failing validation, repeated mistakes, or a direct blocker to tester/operator use.
- Do not describe the current app as a prototype or proof of concept in new user-facing/stakeholder-facing language. Prefer "current app," "current version," "early version," "RecordsTracker," or "pilot build" as context requires.
- Keep reviewer-facing UI in the attorney/reviewer tier: show only record identity, facility identity, source-derived facts needed for the current review task, review-flag badges, reviewer-created state/actions, and focused next actions. Move help, support, operator, source traceability internals, raw source-derived field dumps, connector metadata, hashes, debug details, first-run guidance, and issue-report bridge copy out of the primary reviewer page. If older docs or tests require outdated visible scaffold UI, update those docs/tests to the current product-tier direction instead of preserving the old UI.

## Security and privacy boundaries

- Public CCLD data may be used according to the repo's public-data boundaries; do not introduce private, PHI, credential, token, cookie, or secret handling.
- Do not read, print, store, commit, or document secrets, private host details, passwords, tokens, cookies, private keys, GitHub PATs, Cloudflare tokens, QNAP passwords, or local `.env` values.
- Do not add secrets to tests, fixtures, screenshots, docs, examples, or handoffs.
- Use placeholders such as `<repo-root>`, `<local-project-path>`, `<qnap-host>`, and `<repository-name>` for machine-specific or private values.
- Do not enable MCP servers, browser/computer-use, remote-control features, or external network access unless explicitly requested in the current task.

## QNAP and deployment boundaries

- QNAP is an operator-controlled pilot runtime. Do not SSH to QNAP, edit QNAP `.env`, run QNAP Docker commands, configure Cloudflare, invite testers, or perform destructive reset/import/retrieval actions unless the user explicitly requests that exact action in the current task.
- It is acceptable to improve QNAP docs, local validation scripts, and copy/paste-safe operator command blocks when the task calls for it.
- Keep QNAP-specific host paths and credentials out of application code. Use docs, placeholders, environment variables, or operator notes instead.

## Change behavior

- Make one small, reviewable change per branch.
- Stay inside the requested scope. Do not opportunistically refactor unrelated code.
- Preserve raw source traceability and source-document audit behavior.
- Do not invent canonical fields outside `DATA_CONTRACT.md`.
- Do not change schemas without updating schemas, docs, tests, and migration/init behavior as applicable.
- Do not change extraction behavior without adding or updating fixture-based regression tests.
- Do not use LLM extraction for fields that can be deterministically parsed.
- Do not introduce inaccessible user-facing output.
- If generated stakeholder XLSX behavior changes, require manual regeneration and workbook review after merge.

## Validation expectations

Use the smallest validation that proves the change, then run broader validation before PR.

For most code changes, run:

```powershell
.\scripts\lint.ps1
.\scripts\test.ps1
.\scripts\docs.ps1
```

For documentation-only changes, run:

```powershell
.\scripts\docs.ps1
git diff --check
```

For hosted UI or user-facing workflow changes, also run the relevant hosted scaffold/evidence checks described in `TESTING_STRATEGY.md` and `docs/developer/hosted-scaffold.md`. If evidence packets are generated, create the corresponding zip output.

Do not fake validation results. If validation was not run, say so and explain why.

## Git and PR boundaries

- Do not commit directly to `main`.
- Use a feature branch with a focused name.
- It is acceptable to prepare commits after validation passes.
- Do not push, create PRs, merge PRs, delete branches, or modify repository settings unless explicitly allowed in the current task.
- Before any merge recommendation, required checks must be confirmed: `validate`, `docs-check`, `fixtures`, and `security`.
- If required checks/rulesets are missing, stop before merge and report the blocker.

## Handoff requirements

At the end of each task, provide:

1. Summary of changed files and behavior.
2. Validation commands run and pass/fail results.
3. Documentation impact.
4. Security/privacy impact.
5. Exact remaining manual commands, if any.
6. Stop conditions or blockers.

Keep handoffs copy/paste-safe for PowerShell users. Do not include secrets, personal paths, private URLs, or machine-specific details.
