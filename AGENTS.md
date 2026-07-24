# RecordsTracker Agent Instructions

These instructions apply to Codex, GitHub Copilot, and any other coding agent working in this repository.

## Required context before changing behavior

Use task-relevant context by default. The current complete GitHub issue is the
durable task specification; read it with this file, `.github/copilot-instructions.md`,
and only the governing documents that materially apply to the requested change.
List the governing files actually read and report conflicts or material findings,
not summaries of unchanged governance.

Use the following documents as a task-area router before making code, schema,
extraction, hosted reviewer, export, QNAP, or user-facing documentation changes:

- `PROJECT_CHARTER.md`
- `ROADMAP.md`
- `DECISIONS.md`
- `DATA_CONTRACT.md`
- `SOURCE_CONNECTOR_CONTRACT.md`
- `ARCHITECTURE.md`
- `TESTING_STRATEGY.md`
- `DOCUMENTATION_STRATEGY.md`
- `DESIGN_AND_USABILITY.md`
- `docs/product/records-tracker-product-ux-lead-charter.md`
- `docs/planning/records-tracker-ui-ux-data-completeness-remediation-plan.md`
- `docs/product/records-tracker-approved-design-decisions.md`
- `ACCESSIBILITY_REQUIREMENTS.md`
- `SECURITY_AND_PRIVACY.md`
- `KNOWN_LIMITATIONS.md`
- `.github/copilot-instructions.md`

Do not require every document in this list unless the task materially spans its
area. Do not rewrite governance just because it exists.

For Python validation in a secondary worktree, follow the shared primary-
repository runtime and known-prerequisite resolution rules in
`docs/developer/codex-workflow.md`; keep the working directory in the issue
worktree and report only unresolved blockers after that documented resolution
path fails.

## Capability authorization

The following capability model defines the maximum authority that a task may
grant. It does not create tools or access that the active environment does not
provide. An agent may use a capability only when repository governance
authorizes it and the active environment supports it. If a required capability
or tool is unavailable, stop and report the limitation; do not substitute
another mechanism.

- **RO — read and report only:** May inspect repository content, issue and PR
  state, provenance, and supporting evidence. It cannot edit, mutate, create
  lifecycle state, or use browser verification authority.
- **II — isolated implementation:** May edit the assigned worktree and allowed
  files and run authorized local validation. It cannot create its own branch or
  worktree, commit, push, create or update a PR, merge, clean up, use browser or
  network access unless separately granted, or access remote infrastructure.
- **HV-READ — browser read-only verification:** May use an approved browser and
  network allowlist for GET/navigation, responsive checks, keyboard and
  accessibility inspection, print inspection, screenshots, and evidence. It
  cannot mutate data.
- **HV-WORKFLOW — controlled ordinary-user workflow:** May perform only
  explicitly named ordinary-user mutations using a designated account. Every
  task must define routes, allowed mutations, maximum scope, cleanup or state
  disposition, expected evidence, and stop point. It never grants operator,
  infrastructure, authentication administration, QNAP, database, deployment,
  rollback, restore, or Cloudflare authority.
- **RL-PREPARE — repository lifecycle preparation:** May create the assigned
  branch and worktree, verify the base SHA, commit, push, create or update one
  PR, and monitor required checks. It never includes merge or cleanup authority.
- **RL-MERGE — separately authorized merge and cleanup:** May squash merge and
  clean up only after a separate current-task user authorization, successful
  required checks, no merge blockers, and completion of all required review and
  evidence gates.
- **HQ — human QNAP operator:** The user alone performs archive transfer and
  every QNAP, deployment, rollback, database, restore, and Cloudflare operation.

Capabilities expire at the exact task stop point and do not carry into another
task or conversation.

Every agent task must state the task name, repository, base branch, full
verified base SHA, granted capabilities, whether continuous execution across
phases is authorized, authorized phase sequence, required stop points, exact
branch, exact worktree, allowed files, prohibited files, browser allowlist,
network allowlist, any HV-WORKFLOW mutations and cleanup, validation, evidence,
required checks, whether RL-MERGE is granted, exact final stop point, and
prohibited actions.

The preferred phase sequence is:

1. II implements and validates, then stops and reports.
2. HV-READ or HV-WORKFLOW captures authorized evidence, then stops and reports.
3. RL-PREPARE commits, pushes, creates or updates one PR, and monitors checks,
   then stops and reports.
4. RL-MERGE runs only after separate current-task user authorization.

A session with multiple capabilities must stop between phases unless the
current task explicitly authorizes continuous execution and names the exact
phase sequence. No session may continue into another issue or roadmap task.

For conditional queued phases and acceptance evidence, follow the detailed
fail-closed transition and evidence-lifecycle contract in
`docs/developer/codex-workflow.md`. A successful earlier phase never grants a
later phase; RL-MERGE, deployment, and issue closure need explicit authority.

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
- Use browser/computer-use only under HV-READ or HV-WORKFLOW. Use external
  network access only when the granted capability needs it, including RO for
  allowlisted issue or PR inspection, and only within the task's allowlists and
  stop point. MCP or remote-control tooling remains unavailable unless
  explicitly authorized and supported.

## QNAP and deployment boundaries

- QNAP is a permanently human-operated pilot runtime. Agents never invoke SSH,
  run remote shell or QNAP Docker/Compose commands, inspect or edit QNAP `.env`,
  connect to QNAP PostgreSQL, transfer an archive, deploy, roll back, restore,
  or administer Cloudflare. The user alone performs those actions as HQ through
  the approved local transfer workflow and standalone SSH client.
- It is acceptable to improve QNAP docs, local validation scripts, and copy/paste-safe operator command blocks when the task calls for it.
- When authorized, agents may verify a release SHA locally, prepare and inspect
  a clean local archive, calculate its hash, generate local archive-transfer or
  runbook-derived QNAP command text, prepare hosted-acceptance checklists, and
  interpret safe output pasted by the user.
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

For implementation tasks, use one bounded branch/worktree and do not grant
overlapping write authority. Before branch/worktree creation or assignment,
inspect the current branch and status, local `main` SHA, `origin/main` SHA,
branches, worktrees, unpushed commits, active branches, and possible file
overlap. Create from a clean, synchronized current `main`. Stop on unexplained
dirty state, unpushed work, branch ownership, or active-task overlap. Never copy
`.env` files, secrets, private operator values, generated evidence packets, or
private configuration into an agent worktree.

## Validation expectations

Use the smallest validation that proves the change. For a focused bug fix or
similarly narrow implementation change:

- Run the new regression independently.
- Run the smallest affected test set.
- Run targeted Ruff and mypy checks appropriate to the changed files.
- Run documentation validation when documentation or governed behavior changes.
- Run `git diff --check`.

Do not run the complete local test suite by default for a focused change. Run it
when the task explicitly requests it, the change is broad or cross-cutting,
release-level validation is required, or focused or CI results require broader
investigation.

For documentation-only changes, run:

```powershell
.\scripts\docs.ps1
git diff --check
```

For hosted UI or user-facing workflow changes, also run the relevant hosted scaffold/evidence checks described in `TESTING_STRATEGY.md` and `docs/developer/hosted-scaffold.md`. If evidence packets are generated, create the corresponding zip output.

Before merge, required GitHub checks provide broader PR validation for ordinary
focused changes. Confirm `validate`, `docs-check`, `fixtures`, and `security`
pass; do not weaken or bypass them.

Do not fake validation results. If validation was not run, say so and explain why.

## Git and PR boundaries

- Do not commit directly to `main`.
- Use a feature branch with a focused name.
- Commit, push, and create or update one PR only under RL-PREPARE. Merge and
  cleanup require separately granted RL-MERGE. Repository settings are never
  implied by either capability and require their own explicit authorization.
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

## Reviewer-facing design enforcement

- For any material reviewer-facing removal, merge, rename, relocation, or
  redesign, follow
  `docs/product/records-tracker-reviewer-redesign-artifact-governance.md`.
  Inventory and classify every affected assertion before implementation; list
  preserved, rewritten, removed, and historical-only artifacts in the PR and
  handoff. Do not preserve superseded presentation solely for a stale test, and
  do not weaken accessibility, security, privacy, source, data-integrity,
  export, reviewer-state, authorization, or deterministic-reconciliation
  protections under the label of redesign.
- Do not use accordions, `<details>`, collapsed cards, tabs, or repeated disclosure sections for primary complaint inventories, allegations, findings, deficiencies, plans of correction, or source-backed records supporting reviewer-facing summaries.
- Do not render the same complaint repeatedly under multiple aggregates. Use one canonical record inventory with filters, chips, badges, highlighting, or anchor links.
- Do not accept `Not provided` for a reviewer-relevant field visibly present in governed source evidence without tracing the field through extraction, normalization, canonical allocation, persistence, import/backfill, read model, source precedence, and rendering.
- For an important reviewer-facing UI task, identify the approved Figma frame or design artifact, list prohibited interaction patterns, and stop if the implementation materially varies without approval.
- Do not invent a generic teal-primary design. Implement the approved design tokens, including approved traffic-light protocol color semantics, exactly and accessibly.

## QNAP release deployment authority

For QNAP deployment, verification, hosted acceptance, or rollback, follow the authoritative [QNAP Release Deployment Runbook](docs/developer/qnap-release-deployment-runbook.md). Do not invent or substitute another deployment procedure.
