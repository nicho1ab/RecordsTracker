# Issue #477 Codex prompt — read-only operator coverage dashboard

## Dispatch instructions

Use this prompt only after the Issues #453/#477 planning package has merged to
`main`. Before dispatch, replace every `{{...}}` value. Do not dispatch with a
placeholder.

Recommended Codex effort: `xhigh`.

---

Task name: Issue #477 phase 1 — read-only operator coverage dashboard

Repository: RecordsTracker

Base branch: `main`

Verified base SHA: `{{ISSUES_453_477_PLANNING_MERGE_SHA}}`

Granted capabilities:

- `RO` for read-only inspection of the exact GitHub issue URLs in the network
  allowlist below.
- `II` for isolated implementation and focused local validation only in the
  assigned worktree and owned files below.
- `HV-READ` after II validation for automated GET/navigation, responsive,
  keyboard, focus, accessibility, print, screenshot, download, and evidence
  verification on the exact local route allowlist below.

Continuous execution is authorized only for this phase sequence:

1. Read-only preflight and required-context review.
2. Isolated fixture adapter, authenticated read-only route, presentation,
   download, test, evidence-tool, and operator-documentation implementation.
3. Focused local II validation.
4. Fresh local server start and HV-READ automated evidence capture.
5. Final evidence/validation audit and handoff.

Do not stop between those phases unless a stop condition below is met. Stop
after the HV-READ/II handoff. `HV-WORKFLOW`, `RL-PREPARE`, `RL-MERGE`, and HQ are
not granted.

Exact branch: `issue-477-operator-coverage-dashboard`

Exact worktree: `<repo-parent>\CCLD-complaints-poc-issue-477`

The dispatcher substitutes the exact local repository parent outside tracked
content. Do not add a personal path to code, docs, fixtures, evidence, or
handoff.

Read-only GitHub network allowlist:

- `https://github.com/nicho1ab/RecordsTracker/issues/453` and its comments.
- `https://github.com/nicho1ab/RecordsTracker/issues/477` and its comments.
- `https://github.com/nicho1ab/RecordsTracker/issues/490` and its comments.

Use the connected GitHub app only for those issue reads if available. Do not
modify issue state, comments, labels, assignees, or reactions.

Local browser/network allowlist for HV-READ:

- `http://127.0.0.1:<assigned-port>/operator/source-coverage`
- `http://127.0.0.1:<assigned-port>/operator/source-coverage/facilities`
- `http://127.0.0.1:<assigned-port>/operator/source-coverage/jobs`
- `http://127.0.0.1:<assigned-port>/operator/source-coverage/export.csv`
- `http://127.0.0.1:<assigned-port>/operator/source-coverage/facility-ids.csv?group=<allowed-group>`
- existing local `/health` only to confirm the assigned fixture server is ready.

Substitute one unused loopback port before evidence. Do not navigate to another
route, hostname, remote deployment, source site, or private URL. Browser actions
are GET/navigation, focus/keyboard, print preview, screenshots, and safe local
downloads only. No form submission or other mutation is allowed.

Required checks for a later PR remain `validate`, `docs-check`, `fixtures`, and
`security`, but this task has no RL-PREPARE authority and must not create or
monitor a PR.

RL-MERGE granted: no.

## Goal

Implement the read-only first phase of Issue #477: an authenticated
operator-facing dashboard that consumes deterministic fixtures conforming to the
Issues #453/#477 shared coverage contract and lets an authorized operator
understand source-to-screen coverage separately from retrieval/import/refresh
health.

Provide safe summary, filtering, deterministic sorting, seek/keyset pagination,
facility/job drill-down, aggregate CSV, and explicit Facility ID list downloads.
Implement clear empty, partial, unavailable, interrupted, failed, hash-failed,
reconciliation-failed, and version-mismatch states.

This phase implements no write action. It does not connect to live source
retrieval, execute backfill, add job records, mutate a database, or expose the
dashboard to reviewers.

## Required contract and context

Read before editing:

- `AGENTS.md`
- `.github/copilot-instructions.md`
- `PROJECT_CHARTER.md`
- `ARCHITECTURE.md`
- `DATA_CONTRACT.md`
- `SOURCE_CONNECTOR_CONTRACT.md`
- `SECURITY_AND_PRIVACY.md`
- `DESIGN_AND_USABILITY.md`
- `ACCESSIBILITY_REQUIREMENTS.md`
- `TESTING_STRATEGY.md`
- `DOCUMENTATION_STRATEGY.md`
- `KNOWN_LIMITATIONS.md`
- `ROADMAP.md`
- `docs/product/records-tracker-product-ux-lead-charter.md`
- `docs/planning/records-tracker-ui-ux-data-completeness-remediation-plan.md`
- `docs/product/records-tracker-approved-design-decisions.md`
- `docs/analysis/issue-490-completion-report.md`
- `docs/analysis/issue-490-technical-source-profile.md`
- `docs/planning/issues-453-477-shared-coverage-contract.md`
- `docs/planning/issues-453-477-parallel-ownership.md`
- `docs/developer/hosted-scaffold.md`
- `docs/developer/ui-evidence-review.md`

Read GitHub Issues #453, #477, and #490 plus their comments from the exact
allowlist. The shared coverage contract `1.0.0` is required and frozen. Do not
edit a planning-package file or reinterpret a producer count, classification,
enum, invariant, source-selection state, or privacy rule.

Preserve Issue #490's outcome: existing program-specific sources are retained
for the evaluated scope, every statewide candidate remains inactive, no
statewide completeness baseline exists, no refresh cadence is approved, and raw
value `733` has no approved STRTP or other facility-type mapping.

## Preflight

Before any write or browser use:

1. Confirm the current worktree and branch exactly match this prompt.
2. Confirm `HEAD`, local `main`, and `origin/main` all equal
   `{{ISSUES_453_477_PLANNING_MERGE_SHA}}`.
3. Confirm the assigned worktree is clean.
4. Inspect branches, worktrees, unpushed commits, active ownership, and possible
   file overlap.
5. Confirm Workstream A has no write authority over a Workstream B path.
6. Confirm all dispatch and local-port placeholders are replaced.
7. Confirm `data/processed/ui-evidence/**` and its zip outputs are ignored before
   writing generated evidence.
8. Confirm no existing server is reused; evidence must run against a fresh
   server from this worktree and exact branch.

Stop and report any mismatch. Do not create a different branch or worktree,
clean another worktree, or change local/global Git configuration.

## Exclusive tracked-file ownership

You may create or edit only:

- `src/ccld_complaints/hosted_app/operator_coverage_dashboard.py`
- `src/ccld_complaints/hosted_app/app.py`
- `tests/unit/test_hosted_operator_coverage_dashboard.py`
- `tests/unit/test_hosted_operator_coverage_evidence.py`
- `tests/unit/test_hosted_app_scaffold.py`
- `tests/fixtures/hosted_operator_coverage_dashboard/**`
- `scripts/capture-operator-coverage-dashboard-evidence.ps1`
- `docs/developer/operator-source-coverage-dashboard.md`

Use the smallest subset needed. Generated local evidence may be written only
under ignored `data/processed/ui-evidence/**`, including the corresponding zip,
and must remain untracked.

## Prohibited paths and actions

Do not edit:

- `src/ccld_complaints/hosted_app/auth.py`;
- `src/ccld_complaints/hosted_app/ui_shell.py` or shared navigation;
- any Workstream A producer, schema, test, fixture, or technical document;
- any `docs/planning/issues-453-477-*.md` file;
- `docs/planning/issue-453-codex-prompt.md`;
- `docs/planning/issue-477-read-only-dashboard-codex-prompt.md`;
- `CHANGELOG.md`;
- `ROADMAP.md`;
- `GOVERNANCE_INVENTORY.md`;
- any final Issue #453 or #477 completion report;
- any shared contract-version registry, index, or combined summary;
- migrations, database initialization, persistence tables, retrieval, import,
  backfill, checkpoint mutation, scheduler, deployment, Docker, QNAP, or
  Cloudflare files.

Do not:

- add or change an auth role, permission, authorization target, provider,
  middleware, session, cookie, claim, account rule, or login flow;
- add POST, PUT, PATCH, DELETE, action form, action API, or mutating GET behavior;
- implement retry, dry-run submission, apply, confirmation, cancel, resume,
  database mutation, job creation, new job table, migration, source retrieval,
  connector execution, import, backfill, or schedule behavior;
- import Workstream A implementation modules or duplicate its counting,
  classification, threshold, baseline, or reconciliation logic;
- silently substitute fixtures in production-style mode;
- expose source narratives, allegation/complaint text, raw HTML, record values,
  secrets, credentials, tokens, cookies, claims, private URLs, absolute/raw
  paths, container names, connection strings, stack traces, SQL, uncontrolled
  errors, or source/completeness/authentication claims;
- expose an operator route, link, summary, Facility ID, CSV, job state, hash, or
  diagnostic to reviewer pages, reviewer navigation, reviewer exports, or a
  reviewer role;
- claim a statewide source, source-of-record, completeness, currentness,
  freshness, or cadence is approved, or label `733`;
- stage, commit, push, create/update/monitor a PR, merge, clean up, close an
  issue, deploy, access QNAP, or begin another phase/task.

## Exact routes

Implement only these GET routes:

- `/operator/source-coverage`
- `/operator/source-coverage/facilities`
- `/operator/source-coverage/jobs`
- `/operator/source-coverage/export.csv`
- `/operator/source-coverage/facility-ids.csv?group=<allowed-group>`

The summary route separates source-to-screen coverage from operational refresh
status. The facility and job routes provide safe contract-defined drill-down.
The two downloads implement the exact contract boundaries.

Do not add these routes to primary reviewer navigation. Direct authorized access
is sufficient for the parallel phase; shared operator navigation is reserved for
integration.

## Contract fixture and adapter requirements

Create tiny deterministic contract-package fixtures under
`tests/fixtures/hosted_operator_coverage_dashboard/**` for every named contract
scenario:

- complete balanced;
- verified empty;
- partial unavailable stage;
- failed reconciliation;
- version mismatch;
- hash-validation failure;
- interrupted job with previous accepted data active;
- raw `733` unresolved;
- adjacent keyset pages;
- prohibited content rejected.

Implement one narrow read-only adapter in
`operator_coverage_dashboard.py`. It must:

- accept an explicit package directory/context supplied by local/test code;
- validate contract compatibility, required artifacts, report identity, hashes,
  required fields, closed enums, availability, and reconciliation;
- return producer-supplied aggregate and safe index values without recounting or
  reclassifying them;
- expose controlled unavailable/partial/mismatch/failure results;
- reject prohibited content at the boundary;
- use deterministic filter/sort/keyset behavior and opaque report-bound cursors;
- perform no database write, source access, job action, or persistence;
- default production-style runtime without a configured validated package to
  `Coverage report unavailable`.

Fixture mode must be explicit and visibly labeled `Fixture coverage data`.
Fixture packages are test inputs, not current runtime, production, QNAP, or
statewide evidence.

## Authorization boundary

Reuse the existing `AUDIT_READ_PERMISSION`/`audit_read` permission and existing
scope enforcement pattern. Use an existing authorization target type and the
current audit-read route/service pattern; do not add or alter auth vocabulary.

The dashboard is available only to an active authenticated `admin` or
`developer_operator` actor with `audit_read` and matching scope. Prove denial
for:

- unauthenticated actor;
- disabled or revoked actor;
- `tester_reviewer`;
- `read_only_tester`;
- `feedback_tester`;
- an otherwise operator-capable actor outside the requested scope.

Source-derived read permission alone does not grant operator coverage access.
Authorization occurs before package or fixture data is serialized.

No raw provider subject, issuer, email, claim, token, cookie, or authentication
assertion may appear in HTML, CSV, fixture, error, log, screenshot, or docs.

## Safe operator information tier

Show only contract-permitted information:

- report/source/evaluation/criteria identity and safe versions;
- UTC generation and last-success timestamps with truthful labels;
- aggregate coverage stage/classification totals and reconciliation status;
- operational refresh, processing, change, artifact, hash, checkpoint, and job
  totals;
- safe Facility ID metadata on the authorized facility page;
- safe job IDs and aggregate job metadata on the authorized job page;
- explicit previous-accepted-report state after a current failure;
- controlled warning/failure categories and operator-intervention boolean.

Present raw hashes/fingerprints only when the shared contract marks them as safe
operator metadata; never include them in aggregate CSV or Facility ID lists.
Do not show facility names, addresses, telephone numbers, licensees, complaint
counts, narratives, source bodies, raw errors, paths, hosts, or commands.

Keep coverage and operations in distinct headings, tables, filters, and status
labels. Do not imply that successful refresh proves correct rendering or that a
coverage gap proves an operational failure.

## Filtering, sorting, and pagination

Implement only the contract allowlisted filters and sort keys. Default to 25
rows and cap at 100. Every ordering appends normalized Facility ID and stable
facility-entry ID tie-breakers. Null timestamps sort last.

Use report/filter/sort-bound seek/keyset cursors. Do not use SQL `OFFSET`, deep
or progressive offset, scan-and-discard equivalents, arbitrary page-number
jumps, or full-corpus application-memory slicing. In-memory processing is
permitted only for the tiny explicit fixtures. Changing a filter/sort returns to
the first page. Adjacent-page tests must prove no duplicates or omissions.

Use visible result text `Showing X–Y of Z facilities`. Previous/Next controls
preserve active filters/sort, use semantic disabled states, and have descriptive
accessible names.

## Read-only downloads

`/operator/source-coverage/export.csv` emits the aggregate contract CSV only.
It has no Facility IDs or operator-index rows.

`/operator/source-coverage/facility-ids.csv` requires exactly one explicit group:
`changed`, `unchanged`, `warning`, `failed`, `missing_artifact`, or
`retry_eligible`. It emits exactly `report_id`, `group`, `facility_id`, sorted as
the contract requires.

Both downloads require authorization before serialization, validate the active
contract, set an accurate CSV content type, use clear headers/LF line endings,
and perform no write. Reject missing, multiple, unsupported, or unauthorized
group requests. A verified-empty list retains its header and must reconcile to
the producer aggregate.

No download includes an action instruction, retry payload, source body, path,
URL, hash, error message, or authentication data.

## No write actions

This phase displays `execution_mode`, `retry_eligibility`, and checkpoint state
as facts already present in fixtures. It provides no action button, form, API,
command, or mutation.

Do not implement:

- live retry;
- dry-run start;
- apply or apply confirmation;
- cancel or resume;
- selection persistence;
- a retry-list submission;
- job creation or mutation;
- checkpoint creation/update;
- database or artifact mutation.

The separate dry-run/apply and later mutation rules in the shared contract are
future requirements only. A later separately authorized phase must define its
own routes, permissions, state disposition/cleanup, evidence, and stop point.

## Design, accessibility, and responsive requirements

This is an operator diagnostics surface, not a reviewer redesign. No operator-
specific approved Figma frame is named by this planning package. Reuse the
existing server-rendered shell, approved sitewide tokens/components, and safe
operator-diagnostics patterns without modifying shared shell/navigation or
inventing a new visual system. If the required composition cannot be achieved
within those constraints, stop and request an approved operator design artifact.

Apply and classify these approved design requirements in evidence:

- `RT-DOM-001` — source-derived/operational metadata must not appear as
  reviewer-created state;
- `RT-TIER-001` — operator information stays out of the reviewer tier;
- `RT-STATE-001` — explicit empty, partial, unavailable, error, selected, focus,
  and disabled states;
- `RT-RWD-001` — desktop, narrow, mobile, and 200% zoom reflow;
- `RT-A11Y-001` — visible keyboard focus;
- `RT-A11Y-002` — status never relies on color alone;
- `RT-STRESS-001` — long safe identifiers and unavailable values reflow;
- `RT-PRINT-001` — print-safe text/borders and no control-only meaning;
- `RT-SAFE-001` — no invented scores, conclusions, or decorative KPI tiles.

`RT-PAG-001` is specific to `/ccld/facilities/intelligence` and is not reused as
visual authority for this route. The shared contract independently requires
seek/keyset pagination and no deep OFFSET.

Requirements:

- ordered semantic headings and a skip-to-main/equivalent;
- table captions and scoped column headings;
- labeled filters and downloads;
- keyboard-operable Previous/Next and filter controls;
- visible active filters, sort, result counts, unavailable reasons, and recovery;
- text/icon/accessibility labels paired with semantic colors;
- logical DOM/focus order and visible focus on all interactive controls;
- no horizontal page scrolling at 390 px, narrow desktop, or 200% zoom;
- print keeps report identity, scope, timestamps, status text, summaries, and
  visible rows while removing navigation and interactive controls;
- no JavaScript required to understand state or use core GET/filter/download
  behavior;
- accessible long-content and missing/unavailable-value behavior.

## Required UI states

Implement and test:

1. complete summary;
2. filtered facility page;
3. verified-empty report;
4. filtered-empty result with recovery;
5. partial coverage with named unavailable stages;
6. unavailable package;
7. interrupted job with previous accepted report still active;
8. failed operational state with controlled category;
9. hash-validation failure;
10. reconciliation failure;
11. unsupported contract version;
12. unauthorized/reviewer denial.

No state may turn unavailable, failed, or unprocessed into zero or success.

## Automated browser and evidence requirements

Create `scripts/capture-operator-coverage-dashboard-evidence.ps1` as the narrow
automated method for this route rather than editing the shared capture script.
Its command interface is:

```powershell
.\scripts\capture-operator-coverage-dashboard-evidence.ps1 -OutputRoot data\processed\ui-evidence -Port <assigned-port> -FixtureMode contract-v1
```

The script must:

- start or require a fresh local fixture server from this exact worktree;
- wait for local `/health` and fail if the wrong server/branch is detected;
- use only the exact route allowlist and GET/navigation actions;
- capture summary, filtered, verified-empty, filtered-empty, partial,
  unavailable, interrupted/checkpoint, failed, hash-failed,
  reconciliation-failed, and version-mismatch states;
- capture desktop `1440x1100`, narrow `720x900`, mobile `390x844`, 200% zoom,
  keyboard-focus, long-content, and print states where applicable;
- verify reviewer navigation/HTML contains no operator route or content;
- verify prohibited content is absent from HTML and CSV;
- verify aggregate CSV and each allowed Facility ID list boundary;
- record route/status/assertion metadata and exact fixture scenario;
- create a timestamped ignored evidence directory and corresponding zip;
- stop its own fresh server/browser processes without modifying app data.

Use existing repository/browser automation dependencies where practical. Do not
install software, use a remote browser, capture a signed-in private account, or
perform an ordinary-user mutation. If the existing environment cannot provide
HV-READ evidence without new authority, stop after II validation and report the
exact blocker; do not substitute manual claims.

The evidence report classifies each applicable `RT-...` requirement as `PASS`,
`VARIANCE`, `REGRESSION`, or justified `NOT APPLICABLE` and records exact route,
viewport/state, commit SHA, capability, and local fixture label.

## Operator documentation

Create `docs/developer/operator-source-coverage-dashboard.md` covering:

- direct routes and existing `audit_read` authorization;
- fixture-only parallel-phase data source and production unavailable default;
- contract version/compatibility and version-mismatch behavior;
- meaning of every coverage, refresh, processing, change, artifact, hash,
  checkpoint, job, and failure state;
- source-to-screen versus operational status distinction;
- filters, sort, keyset pagination, aggregate CSV, and Facility ID list rules;
- no-write/no-retry/no-apply/no-cancel/no-resume boundary;
- safe information tier and prohibited content;
- retention/provenance and pending retention-policy duration;
- Issue #490 source/cadence/`733` limits;
- exact focused validation and evidence command;
- integration dependency before producer-backed non-fixture consumption.

Do not create a final Issue #477 completion report or describe the later action
phase as implemented.

## Acceptance criteria

- Every route is GET-only, authenticated before serialization, and limited to
  existing `audit_read` authorization/scope.
- Reviewer/tester roles cannot access or discover operator content.
- The adapter consumes contract fixtures and does not duplicate producer logic.
- Complete, empty, partial, unavailable, interrupted, failed, hash-failed,
  reconciliation-failed, and version-mismatch states are truthful.
- Coverage and operational refresh status remain visibly separate.
- Filters/sorts are allowlisted and deterministic; keyset pages reconcile with
  no duplicates/omissions and no deep OFFSET.
- Aggregate CSV and explicit Facility ID list downloads meet exact boundaries.
- No route or download mutates any state.
- No retry/apply/cancel/resume or other action exists.
- Operator information is safe and no prohibited content appears.
- Responsive, keyboard, focus, non-color-only, 200% zoom, long-content, and
  print evidence passes on a fresh local fixture server.
- Fixture evidence is visibly labeled and is never called production or
  statewide coverage.
- Issue #490's inactive statewide candidate and unapproved cadence remain
  explicit.
- Only Workstream B owned tracked paths change.

## Focused validation

Run the new regression independently, then the smallest affected hosted set:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_hosted_operator_coverage_dashboard.py -q
```

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_hosted_operator_coverage_dashboard.py tests\unit\test_hosted_operator_coverage_evidence.py tests\unit\test_hosted_app_scaffold.py -q
```

Run targeted lint and type checks:

```powershell
.\.venv\Scripts\ruff.exe check src\ccld_complaints\hosted_app\operator_coverage_dashboard.py src\ccld_complaints\hosted_app\app.py tests\unit\test_hosted_operator_coverage_dashboard.py tests\unit\test_hosted_operator_coverage_evidence.py
```

```powershell
.\.venv\Scripts\mypy.exe src\ccld_complaints\hosted_app\operator_coverage_dashboard.py src\ccld_complaints\hosted_app\app.py
```

Run documentation validation and focused documentation checks:

```powershell
.\scripts\docs.ps1
```

```powershell
.\.venv\Scripts\python.exe -m pytest tests\data_quality\test_documentation_checks.py -q
```

Run security and diff checks:

```powershell
python scripts\check_no_secrets.py
```

```powershell
git diff --check
```

After those pass, start a fresh fixture server and run the exact evidence command
above under HV-READ. Inspect the generated route assertions, screenshots, CSV
samples, manifest, and zip before reporting pass.

Also run focused assertions proving:

- contract/hash/version/reconciliation validation;
- every required UI state and closed enum;
- reviewer/unauthenticated/disabled/revoked/out-of-scope denial;
- no writes for route, filter, pagination, drill-down, or download GETs;
- no POST/action controls or routes;
- aggregate CSV and explicit Facility ID boundaries;
- adjacent keyset pages and no OFFSET/full-corpus production slicing;
- prohibited-content rejection and reviewer-tier absence;
- no statewide/cadence/`733` claim;
- the changed/untracked path set is a subset of Workstream B ownership;
- no Workstream A or reserved integration file changed.

Do not run the complete test suite unless a focused failure shows it is needed;
if broader validation becomes necessary, stop and request an updated task. Do
not present an unrun check or uncaptured evidence state as passed.

## Stop conditions

Stop before further editing or browser use and report if:

- preflight branch, worktree, SHA, clean state, ownership, port, or a dispatch
  placeholder is wrong;
- a required path is not exclusively owned by Workstream B;
- contract `1.0.0` is ambiguous or requires a semantic/breaking change;
- the adapter would need Workstream A code or duplicate its calculations;
- existing `audit_read` cannot enforce the operator/reviewer boundary without
  changing auth policy;
- safe operator presentation requires shared shell/navigation changes or an
  unapproved new visual system;
- a source value/body, secret, credential, claim, private URL/path, container,
  uncontrolled error, or reviewer exposure would be required;
- a statewide source/cadence or `733` mapping assumption is required;
- implementation needs retry/apply/cancel/resume, mutation, persistence, schema,
  migration, retrieval, import, backfill, schedule, deployment, QNAP, or a
  reserved integration file;
- HV-READ would require a route/host/action outside the allowlist or cannot be
  captured with available approved local tools;
- validation exposes a real authorization, privacy, reconciliation,
  accessibility, or no-write defect that cannot be fixed inside owned paths.

An unavailable package or blocked fixture state is a valid UI state. Do not
substitute a fixture as production data, weaken authorization, hide a failure,
relax a contract check, add an action, or expand browser authority merely to
pass validation.

## Final handoff and exact stop point

Stop after implementation, focused local validation, and authorized HV-READ
evidence. Report:

1. Verified base SHA, branch, worktree template, capabilities, continuous phase
   sequence, and exact network/browser allowlists used.
2. Exact files changed and exact GET routes implemented.
3. Contract version/fixtures consumed and adapter behavior.
4. Authorization boundary and reviewer/tester denial results.
5. Summary, state, filter, sort, keyset, drill-down, CSV, and Facility ID list
   behavior.
6. No-write/no-action proof.
7. Every validation command and pass/fail result, including intentionally unrun
   checks.
8. Evidence directory, zip, route assertions, scenarios, viewports, and
   applicable `RT-...` classifications.
9. Documentation impact.
10. Security/privacy impact and prohibited-content results.
11. Issue #490/statewide/cadence/`733` confirmation.
12. Exact unresolved design, retention, producer, and integration decisions.
13. Confirmation that Workstream A and all reserved files were untouched.
14. Confirmation that no auth policy, data, job, source, deployment, QNAP, Git
    lifecycle, PR, issue, or external mutable state changed.

Do not stage, commit, push, create or update a PR, monitor checks, merge, clean
up, close Issue #477, deploy, access QNAP, begin the mutation phase, or start
Issue #453 or another task.

---
