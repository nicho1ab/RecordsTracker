# Codex Workflow

This repository can be worked on with Codex or another supported agent
interface, but every task uses explicit, bounded authority. Repository
governance defines the maximum capability that may be granted; it does not
create unavailable tools. A capability may be used only when this governance
authorizes it and the active environment supports it. A prompt cannot grant
access to a tool or system that is unavailable. Stop and report a missing
capability or tool instead of substituting another mechanism.

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

## User guidance for model and reasoning effort

This is user guidance, not a repository-enforced model, model-selector, or
reasoning-effort capability. Use low effort for mechanical Git, branch,
pull-request, check-monitoring, and cleanup work; medium for routine bounded
fixes with known reproduction and scope; high for multi-file, product-sensitive,
or moderately ambiguous work; and extra-high only for difficult architecture,
source-authority, data-integrity, security, privacy, schema, ingestion, or
ambiguous debugging work.

## Capability model

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

## Required task authorization

The compact template below separates stable defaults from task-specific
authority. It does not grant any capability on its own.

**Stable defaults:** repository; required checks (`validate`, `docs-check`,
`fixtures`, `security`); no merge by default; human-only QNAP authority; no
secrets; no browser or network authority unless explicitly granted;
focused-validation default; and standard phase stop points.

## Validation environment resolution

Secondary worktrees are not expected to contain their own virtual environment.

Before running Python-based validation:

1. Read the repository’s documented validation convention.
2. Resolve the verified Python executable from the authoritative primary repository or previously verified task evidence.
3. Confirm that the executable exists and can import the required project dependencies.
4. Run validation with:
   - the working directory set to the current issue worktree; and
   - the verified primary-repository Python executable.

Do not first attempt:

- a worktree-local `.venv`;
- `python` or `pytest` from PATH;
- environment creation;
- dependency installation;
- speculative executable variants.

When the documented shared runtime is available, use it directly and continue
without treating its absence from the secondary worktree as a blocker.

Report an environment blocker only after:

- the documented runtime location was inspected;
- previously verified runtime evidence was checked;
- the executable was found missing or unusable; and
- the exact command and error were captured.

## Known-prerequisite resolution

Resolve documented, task-relevant prerequisites before beginning validation or
implementation. Do not stop or emit an interim blocker for an expected
condition that has an established repository convention.

Examples include:

- primary-repository virtual-environment use from secondary worktrees;
- exact required GitHub checks;
- authoritative main and worktree paths;
- established documentation-validation commands;
- human-only QNAP authority.

Do not perform broad speculative prerequisite discovery. Report only unresolved
prerequisites that prevent authorized work after documented resolution paths have
been exhausted.

**Task-specific authority:** governing issue; full verified base SHA; branch;
worktree; granted capabilities; exact phase sequence; allowed and prohibited
files or boundaries; browser and network allowlists where relevant; validation;
evidence; final stop point; and explicit RL-MERGE state.

Every task must state:

- task name;
- repository;
- base branch;
- full verified base SHA;
- granted capabilities;
- whether continuous execution across phases is authorized;
- authorized phase sequence;
- required stop points;
- exact branch;
- exact worktree;
- allowed files;
- prohibited files;
- browser allowlist;
- network allowlist;
- HV-WORKFLOW allowed mutations and cleanup;
- validation;
- evidence;
- required checks;
- whether RL-MERGE is granted;
- exact final stop point; and
- prohibited actions.

## Durable issues, continuation, and investigation

The current complete GitHub issue is the durable task specification. Prompts
should point to it instead of reproducing its entire body. Within an already
authorized task, a continuation prompt preserves authority only when its scope
is unchanged and states only the new output, failure, correction, or evidence.
It must restate authorization whenever authority or scope changes; a
continuation never expands authorization implicitly.

Investigation and implementation may be combined only when the defect is
reproducible, the affected boundary is known, and the permitted correction is
clear. Use a separate investigation phase when root cause is unknown, multiple
systems may be responsible, product or design authority is unresolved, source
or data-contract authority is unresolved, branch or file overlap is uncertain,
or implementation could materially affect architecture, security, privacy,
schemas, ingestion, deployment, or source traceability.

## Phase transitions

The preferred sequence is:

1. **II:** implement and validate; stop and report.
2. **HV-READ or HV-WORKFLOW:** capture the authorized evidence; stop and report.
3. **RL-PREPARE:** commit, push, create or update one PR, and monitor required
   checks; stop and report.
4. **RL-MERGE:** proceed only after separate current-task user authorization.

When one session has multiple capabilities, it must stop between phases unless
the current task explicitly authorizes continuous execution and identifies the
exact phase sequence. No session may continue into another issue or roadmap
task.

### Conditional queued phase transitions

A prompt may conditionally authorize a later phase in the same execution only
when it explicitly states the ordered phase sequence, prerequisite pass
conditions, fail and stop conditions, mutations permitted in each phase,
post-correction validation, and continuous-execution authorization. The later
phase becomes authorized only through that original explicit conditional grant.

Treat a prerequisite as failed and stop when it is failed, unavailable,
ambiguous, stale, contradictory, outside scope, dependent on unperformed human
inspection, or dependent on a new product, design, legal, security, privacy,
data, deployment, or governance decision. "Ready," "recommended," "review
passed," and "no defects found" are not authorization by themselves. A
correction that expands file, behavior, or governance scope also stops the
transition.

Conditional execution cannot cross from one issue into another issue or start
a roadmap successor. RL-MERGE remains separately and explicitly authorized;
merge-to-deployment and issue closure remain separate when their evidence or
human judgment is pending.

### Fresh authoritative state after lifecycle mutations

After a state-changing GitHub operation, query the authoritative service again
before any dependent execution. This includes issue close or reopen, PR
draft/ready transitions, merge, branch deletion, PR-body corrections when
checks depend on event payload, and label or dependency mutations used as later
prerequisites. Do not rely on pre-mutation variables, cached JSON, prior search
results, stale issue lists, pasted success output, or local repository state as
a substitute for the service state.

Where state is a prerequisite, record or verify the repository, hostname,
authenticated identity, issue or PR number, exact state and reason, relevant
timestamp, and current head/base SHA when applicable. Contradictory fresh
results stop execution. This policy requires fresh authoritative state, not one
specific CLI implementation.

## Interface and role split

- ChatGPT/project architect: scope review, prompt review, risk gate, final review.
- ChatGPT Desktop Codex: only the capabilities granted for the current task;
  depending on the environment, these may include worktrees, terminal
  execution, browser verification, or GitHub lifecycle operations.
- GitHub Copilot or another interface: only its available subset of the granted
  capabilities; unavailable tooling must not be replaced with a different
  mechanism.
- Human operator: final approval and permanent HQ authority.

## Do not enable by default

Do not enable these for normal RecordsTracker work unless a capability and the
current task explicitly authorize them:

- MCP servers.
- Browser/computer-use.
- QNAP SSH or remote shell access; agents may never receive this authority.
- Cloudflare/admin-console access.
- GitHub token pages or repository settings access.
- PR merge or cleanup workflows without separately granted RL-MERGE.
- Access to `.env`, deployment secrets, private keys, cookies, or tokens.

RL-PREPARE may use supported repository lifecycle tooling only for its assigned
branch, worktree, and single PR. It may not merge or clean up. RL-MERGE may use
supported lifecycle tooling only after its separate authorization and merge
gates. Neither capability authorizes repository settings changes.

## Worktrees

Before creating or assigning a task worktree, inspect the current branch and
status, local `main` SHA, `origin/main` SHA, branches, worktrees, unpushed
commits, active branches, and possible file overlap. Branch creation must start
from a clean, synchronized current `main`.

Use one bounded branch/worktree per implementation task and do not grant
overlapping write authority. Stop on unexplained dirty state, unpushed work,
branch ownership by another worktree, active-task overlap, or unresolved file
overlap. Do not copy `.env` files, secrets, private operator values, generated
evidence packets, or private configuration into agent worktrees.

II works only in the already assigned branch/worktree. RL-PREPARE is required
to create an assigned branch/worktree or perform later repository lifecycle
steps.

### Persistent coordination branches after squash merge

Disposable implementation branches may be removed after verified merge and
normal cleanup. A narrowly authorized exact local force deletion is permitted
only after merge verification when squash history prevents normal deletion.

Persistent coordination branches must be preserved and are not assumed to be
fast-forwardable after a squash merge. Before any reset or remote update, verify
the clean worktree, expected old local and remote SHAs, exact squash SHA, and
tree equivalence or other proof that no unique unmerged content exists. Resetting
only that exact persistent branch and updating only its matching remote with
`--force-with-lease` against the known old SHA each require separate narrowly
scoped authorization. Broad force-push authority is prohibited, and no reset or
rewrite is allowed when unique branch content exists.

## Acceptance-evidence lifecycle

Before removing a disposable worktree that contains the only acceptance-evidence
copy, preserve it in the established ignored durable destination. Verify source
and destination existence, expected manifest and file index, file list and
count, file sizes, applicable zero-length and unexpected-file checks, ZIP
integrity, SHA-256, and ignored unstaged status. Do not create tracked evidence
artifacts unless a separate contract expressly requires them.

Stop cleanup when evidence lacks a durable verified copy, the destination
conflicts with unrelated content, integrity verification fails, or preservation
would require an unauthorized mutation. The handoff must state the durable
directory and ZIP, file count, integrity hash, preservation result, and cleanup
result.

When authorized safe local capture tooling can package evidence, the capturing
agent creates and verifies the ZIP, computes and reports its SHA-256, and does
not ask a user to package it manually. Successful capture, technical package
completion, human acceptance, and final issue completion are distinct states.

## Browser boundaries

HV-READ permits only allowlisted GET/navigation and read-only responsive,
keyboard, accessibility, print, screenshot, and evidence work. HV-WORKFLOW
permits only the exact named ordinary-user mutations, maximum scope, cleanup or
state disposition, evidence, and stop point in the task.

Neither capability permits operator actions, infrastructure or authentication
administration, QNAP access, database administration, Cloudflare, credential
inspection, or destructive actions.

## Human-only QNAP boundary

Agents may verify a release SHA locally; prepare and inspect a clean local
archive; calculate its hash; generate local archive-transfer command text;
generate QNAP command text from the authoritative runbook; prepare hosted-
acceptance checklists; and interpret safe output pasted by the user.

Agents may never invoke SSH through PowerShell, Git Bash, WSL, Python,
libraries, MCP, browser terminals, or any indirect mechanism. They may never
run remote shell commands, run QNAP Docker or Compose, inspect or modify QNAP
`.env`, connect to QNAP PostgreSQL, transfer or deploy autonomously, deploy,
roll back, restore PostgreSQL, or administer Cloudflare. The user alone performs
archive-transfer and QNAP commands through the approved local transfer workflow
and standalone SSH client.

## Project Sources

Repository `main` is authoritative. ChatGPT Project Sources are static
contextual copies and do not update automatically from GitHub. Repository-file
Project Sources must be exact unchanged mirrors without prepended source
metadata.

A separate steering-only Project Source named
`CCLD RecordsTracker Project Sources Manifest.md` tracks display name,
repository path or steering-only status, source commit SHA, upload date, and
current/stale status. The manifest is not a repository file and must not be
created here. Similar filenames do not prove duplication; remove a superseded
source only after verifying its identity, replacement, readability, and lack of
unique content.

Merged repository governance becomes authoritative immediately. Project Source
replacement is required before a ChatGPT Project relies on mirrored copies as
current, but Codex may follow repository `main` directly. Between merge and
Project Source replacement, planning chats must inspect repository `main`.

## Validation

For a material reviewer-facing redesign, complete the pre-code artifact
inventory and seven-class assessment in
`docs/product/records-tracker-reviewer-redesign-artifact-governance.md` before
editing application behavior. Update the directly affected implementation,
tests, active evidence contracts, current documentation, and approved design
register together. Accurate historical evidence stays historical. The task
handoff must list preserved, rewritten, removed, and historical-only assertions
and the replacement evidence for each.

For a focused bug fix or similarly narrow implementation change, Codex should:

- Run the new regression independently.
- Run the smallest affected test set.
- Run targeted Ruff and mypy appropriate to the changed files.
- Run documentation validation when documentation or governed behavior changes.
- Run `git diff --check`.

Do not run the complete local suite by default for a focused change. Run it only
when explicitly requested, repository governance specifically requires it, for
broad or cross-cutting work, for release-level validation, or when focused or
CI results require broader investigation.

For docs-only changes, normally run:

```powershell
.\scripts\docs.ps1
git diff --check
```

Use narrower focused tests first when appropriate, but do not present unrun validation as passed.

Before merge, the required GitHub checks remain `validate`, `docs-check`,
`fixtures`, and `security`. They provide broader pre-merge validation for
ordinary focused changes and must not be weakened or bypassed.

Reserve full local validation for releases, production-readiness milestones,
schema changes, connector expansion, export-contract changes, production
architecture transitions, broad cross-cutting changes, and investigation of
failures that focused validation cannot explain.
