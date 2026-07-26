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

### Read-only delivery-state snapshots

`scripts/delivery_state.py snapshot` produces a versioned JSON record of the
current local Git and live GitHub state for a bounded issue worktree. It is a
read-only inspection tool: it does not fetch, change refs, create or realign
worktrees, inspect stash contents, stage, commit, publish, edit a PR, rerun a
check, merge, close an issue, deploy, or mutate production data.

The committed schema is `schemas/delivery-state-snapshot-v1.schema.json`.
Snapshots identify their local-Git and GitHub sources, collection times,
expected-versus-observed immutable identifiers, and the fact that Git and
GitHub do not provide one globally atomic read. A changed critical identifier
is reported as instability rather than hidden by a stale success result.

Historical merged or closed PRs that reuse a branch name at a different head
SHA are informational. A live GitHub ref is authoritative for remote-branch
existence; a local `origin/<branch>` ref may therefore be stale and is also
informational when no live branch or ownership conflict exists. An exact-head
open PR is an idempotent reuse state. A closed or merged PR at the exact current
head is a blocking historical-publication condition until an authorized review
establishes its disposition; creating another PR would otherwise be duplicate
or inconsistent.

Expected PR base branch/SHA and head branch/SHA are compared separately and
fail closed. Required-check records retain both their observed and expected
head SHAs; successful evidence from another head is marked stale and cannot
satisfy the current-head check requirement.

The snapshot records only durable delivery facts: repository and SHA identity,
worktree and protected-stash metadata, changed scope, PR/check linkage, source
attribution, and typed findings. Human-readable wording and command layout are
supersedable. It does not decide product correctness, visual acceptance,
deployment, issue closure, or production-data operations, and it never grants
mutation authority.

Use a fixed `--at` value only for deterministic fixture evidence. An explicitly
requested output path is refused when it already exists unless safe replacement
is deliberately requested; live snapshots belong under ignored evidence storage
rather than tracked source paths. The PowerShell invocation remains one line:

```powershell
python scripts/delivery_state.py snapshot --issue <number> --expected-main-sha <sha> --protected-stash <sha>
```

Findings use `INFORMATIONAL_DISCREPANCY`, `RECOVERABLE_AUTOMATION_FAILURE`,
`AUTHORIZATION_BLOCKER`, `DEPENDENCY_BLOCKER`,
`MATERIAL_IMPLEMENTATION_BLOCKER`, `DESTRUCTIVE_ACTION_BLOCKER`, and
`GOVERNED_BOUNDARY_REVIEW_REQUIRED`. Informational history does not fail the
command; actual blockers and execution failures do. Future dependency or
lifecycle integration must retain this schema and read-only boundary rather
than creating a parallel governance path.

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

## Pull-request evidence preflight

Before creating a pull-request body, render the authoritative template with
`scripts/prepare_pr_body.py render` and run
`scripts/prepare_pr_body.py preflight` against the proposed body and the actual
changed-file list. Local automatic discovery includes staged, unstaged, and
untracked files. The preflight calls the same independent-verification rules as
CI and fails with the same actionable messages. It does not replace required
GitHub checks or human review. Reviewer-facing work must also identify affected,
added, updated, superseded, or specifically not-applicable entries in
`docs/developer/reviewer-ui-regression-contracts.md`.

All PR-body paths use the validator's one canonical boundary before template
mode detection or any evidence parsing. It converts CRLF and lone CR to LF,
preserves Unicode, Markdown, substantive whitespace, and trailing-newline
state, and never repairs mojibake. The same canonical UTF-8 normalized body
representation supplies validation and body hashes; changed-file scope is
complete, slash-normalized, and deduplicated in first-seen order. Local
preflight, CI body-file validation, and open-PR live JSON validation therefore
return the same decision and ordered violations for equivalent body and scope.
An unresolved non-comment instruction such as `Not run - <reason>` fails with
an actionable violation; a truthful completed `Not run - reason` explanation
remains valid. This contract does not replace DA-030 transport-persistence
work, add automatic retry, or add rollback.

### Open-PR body lifecycle

The same repository-owned command supports an already-open PR without creating
a parallel governance path. It derives the current GitHub repository from
`origin` (or rejects a mismatched explicit repository), accepts a PR number,
qualified reference, or GitHub PR URL, fetches the live body and complete
paginated changed-file list, and identifies the current base, head, and head
SHA. It rejects missing, inaccessible, malformed, or closed PRs. It never
prints a full body unless another supported output mode is added deliberately.

Validate the current live body without mutation:

```powershell
python scripts/prepare_pr_body.py open-pr validate --pr <number-or-reference> --repo <owner/repository>
```

Preview a file-based governed proposal against that exact live scope without
mutation. The output supplies the normalized current-body SHA-256 and reports
whether the proposal differs materially; it does not regenerate or overwrite
evidence:

```powershell
python scripts/prepare_pr_body.py open-pr preview --pr <number-or-reference> --repo <owner/repository> --body <proposed-body-path>
```

Only an explicitly authorized caller may apply a body repair. `apply` requires
both `--confirm-update` and the hash obtained from a current preview when a
mutation is needed. It validates the proposal before update, refetches and
compares the live body immediately before update to reject stale proposals,
updates only the PR `body` field, refetches the persisted body and current
changed-file list, then reruns the production validator. A normalized LF/CRLF
match is a no-op and makes no update request. GitHub does not provide this tool
with a body-field conditional update. The explicit current-body hash therefore
detects a stale proposal immediately before PATCH, but cannot remove the narrow
race between that final refetch and the update request. A post-update refetch
detects an ordinary persistence mismatch and revalidates the persisted body; it
does not claim atomic compare-and-swap behavior or rollback.

```powershell
python scripts/prepare_pr_body.py open-pr apply --pr <number-or-reference> --repo <owner/repository> --body <proposed-body-path> --expected-body-sha256 <previewed-hash> --confirm-update
```

This lifecycle changes only the PR body. It does not authorize code changes,
commits, branch or check changes, labels, reviewers, draft state, approvals,
merges, or issue closure. The authoritative template and production validator
remain the source of truth, including compact-summary eligibility, required
headings, governed-boundary disclosure, and Issue #504 classification; no static
body snapshot is a repair contract. Future approved template changes continue
through the existing template/validator parity checks.

#### DA-030 guarded transport and persistence evidence

The same `open-pr apply` lifecycle is the only supported body-mutation path;
there is no second transport or repair command. An authorized invocation binds
the repository and PR number to immutable expected state: open/draft state,
base and head names and SHAs, complete canonical changed-file-scope hash,
current normalized live-body hash, and validated candidate normalized-body
hash. It also requires explicit `body-only` intent and confirmation. A changed
identity, scope, or body hash stops before mutation.

The one permitted request is constructed as exact UTF-8 JSON with no BOM and
exactly one top-level key, `body`. The implementation records hashes of the
request-body bytes, canonical candidate body, and exact JSON payload bytes. It
uses a temporary byte-safe payload file rather than shell interpolation or a
multiline command argument, removes that file after the request, and never
records credentials, headers, environment content, or a full PR body in
evidence.

Each invocation has a production-enforced mutation budget of zero or one PATCH.
After that budget is consumed, every remaining operation is read-only; no branch
may retry, roll back, or hide another PATCH in a helper. The sanitized,
versioned `pr-body-persistence-attempt-v1` evidence model records immutable
expected values, hashes, payload-key proof, mutation count, REST and GraphQL
observations, classifications, production-validator result, source attribution,
and `globally_atomic: false`. It is distinct from the read-only delivery-state
snapshot because a body mutation attempt has different privacy and lifecycle
responsibilities. Store optional evidence only in an ignored path.

Immediately after PATCH, the lifecycle records the REST response, REST refetch,
and GraphQL representation where available. It then permits at most three
additional read-only stabilization observations at a one-second interval. The
count and interval are injectable for deterministic tests, and the defaults are
intentionally short because PR #615 showed delayed convergence without
justifying a long unattended delay. REST and GraphQL compare canonical
normalized text, so LF/CRLF equivalents match while mojibake remains distinct.
GraphQL unavailability is informational only when REST convergence and
post-persistence production validation are otherwise proven; a stable REST /
GraphQL semantic disagreement is not success.

The final machine-readable classifications distinguish no-mutation precondition
failure, mutation API or response failure, immediate or delayed convergence,
transient representation disagreement, stable mismatch, changed PR identity,
unexplained non-candidate body change, post-persistence validation failure, GraphQL
unavailability, and observation failure. Success requires final candidate-hash
equality, stable PR identity and scope, and a passing canonical production
validator. An immediate mismatch is therefore evidence, not an automatic claim
of permanent corruption; it never authorizes a second mutation or rollback.

This transport/persistence contract is bounded DA-030 work in Issue #616. It
does not implement Issue #617 grouped lifecycle orchestration, consume any
authorization automatically, alter issue closure behavior, or change CI
permissions, required checks, branch protection, or rulesets.

## Delivery-automation failure and prevention registry

Issue #617 owns the repository's canonical delivery-automation failure and
prevention registry. The machine-readable source is
`.github/delivery-automation-registry.json`, its versioned local schema is
`schemas/delivery-automation-registry-v1.schema.json`, and the offline
validator is `scripts/delivery_automation_registry.py`. The validator is part
of the existing documentation-validation path; it does not contact GitHub or
mutate the registry, repository, issues, pull requests, checks, or worktrees.

Each stable `DA-NNN` identifier is unique, uppercase, numerically ordered, and
never silently renumbered or reused. A declared historical gap is a truthful
absence of authoritative evidence, not an empty failure record. DA-001 through
DA-028 are explicitly unavailable because the #617 readiness audit found no
authoritative repository evidence; only DA-029 through DA-031 are seeded.

Records identify their owner issue, lifecycle status, prevention state,
governance-change classification, enforcement level, evidence completeness,
regression coverage, documentation impact, remaining work, and any
supersession, retirement, or temporary exception. Lifecycle values distinguish
identified, active, prevention-in-progress, prevented, superseded, retired,
exception-active, and review-required records. Governance changes are classified
as clarification, inconsistency correction, stronger enforcement, relaxed
enforcement, supersession, temporary exception, or obsolete-control removal.
Enforcement levels are documentation only, validation, guarded mutation,
workflow gate, and human decision; none grants autonomous execution.

Conditional workflow-learning capture is the registry's purpose, but this
foundation does not yet require automatic capture or implement an autonomous
governance engine. A preventable failure correction must retain its evidence,
identify its owner, link regression coverage and documentation impact, and
declare parity when the same contract has more than one enforcement path.

A temporary exception requires an owner, reason, scope, creation reference,
current status, replacement or exit criteria, and either an expiration date or
mandatory review trigger. It cannot silently relax a required check or an
authorization boundary. Superseded records remain historically traceable;
retirement requires a rationale, and obsolete-control removal must name its
replacement or explain why none is required. Registry evidence is limited to
public issue and pull-request identifiers, repository-relative paths, and
concise summaries. It excludes credentials, headers, environment content,
private hosts, full PR bodies, and private evidence payloads.

DA-031 remains active: future work must inspect development links and closing
references, bind closure authorization to exact issue numbers, verify
post-merge issue state, and record closure source. This registry foundation does
not implement a merge controller, issue closure, recovery mutation, grouped
RL-PREPARE or RL-MERGE execution, deployment, or production-data behavior.

### DA-031 read-only closure-linkage inspection

`scripts/closure_linkage_inspection.py` is a dedicated read-only inspector, not
a delivery-state snapshot or merge controller. It requires exact issue-outcome
declarations: repository, issue number, declared role, expected pre- and
post-merge state, explicit closure and reopen authorization, authority
reference, rationale, and must-remain-open status. Roles are declared evidence,
not autonomous semantic conclusions.

The versioned evidence schema rejects unknown fields and requires repository and
pull-request identity, normalized references, sanitized timeline facts,
observed issue state/reason/timestamps, source availability, deterministic
findings, prohibited actions, attribution, and explicit non-atomic status. It
does not retain a full PR body, credentials, private host details, environment
contents, or a recovery instruction. Contract role values are
`completed_target`, `parent`, `continuation`, `related`,
`historical_evidence`, and `unknown`; their outcome declarations remain exact
evidence rather than autonomous semantic conclusions.

The inspector observes normalized PR-body references, fully paginated GraphQL
closing issues, fully paginated timeline linkage, and issue state/state-reason
evidence where the APIs expose it. A malformed response, exhausted GraphQL
page bound, duplicate closing-reference node, partial page result, unavailable
observable source, or other collection failure is evidence incomplete and fails
closed. The GitHub development-link closure effect is instead recorded as an
explicit `platform_not_exposed` residual: supported read-only APIs expose the
links, not their closure effect. This does not claim that an unexposed mechanism
is absent. No-link evidence is ready only when every required observable source
is complete and each must-remain-open issue has an exact, immediate post-merge
state-verification obligation. Readiness grants no merge authority. Pre-merge
findings are deterministic by code, issue number, and
source; post-merge inspection separately compares declared state, state reason,
timestamps, closure source, and authorized reopen expectations without taking
recovery action.

Timeline cross-references are relationship evidence, not closure evidence. An
informational `cross-referenced` event remains visible with its exact related
issue, but does not grant closure or reopen authority and does not block a
must-remain-open outcome. Blocking linkage requires explicit closing semantics
from a recognized PR-body keyword, GraphQL closing reference, API-exposed
closing development link, or attributable post-merge close event. Unknown or
malformed timeline events fail closed; the hidden development-link closure
effect remains the separate `platform_not_exposed` residual.

Its production CLI accepts only an existing repository-relative contract path:
normalization, containment, and symlink resolution must all remain beneath the
verified repository root. It has no caller-supplied schema, evidence, output,
endpoint, HTTP method, GraphQL text, or field-selection path. Canonical schema
validation stays repository-fixed. Optional post-merge collection first
revalidates the fixed repository and pull request, then reads only issue
numbers declared by the exact outcome contract through internally constructed
read-only endpoints; partial collection is evidence incomplete.

It reports ready for separate merge authorization, not ready, or evidence
incomplete; it never merges, closes, reopens, unlinks, repairs, or rolls back
an issue. This is an independent read-only inspection surface, not a
replacement for existing delivery-state snapshots or a merge controller. #533
retains generic orchestration ownership.

CI validates the current live PR body whenever it runs. The `pull_request`
workflow includes `opened`, `reopened`, `synchronize`, and `edited`, so a title
or body edit starts the same read-only validation workflow. GitHub event
selection cannot distinguish a title edit from a body edit, but the job fetches
the current live body immediately before validation rather than using stale
event payload text. Forked PRs retain the workflow's `contents: read` and
`pull-requests: read` token permissions; no CI write permission is granted.

A freeform body cannot substitute for the full governed template. Compact
governed-summary eligibility remains controlled only by the validator.

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
