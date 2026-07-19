# Issue #453 Codex prompt — source-to-screen coverage reporting

## Dispatch instructions

Use this prompt only after the Issues #453/#477 planning package has merged to
`main`. Before dispatch, replace every `{{...}}` value. Do not dispatch with a
placeholder.

Recommended Codex effort: `xhigh`.

---

Task name: Issue #453 — deterministic source-to-screen coverage reporting

Repository: RecordsTracker

Base branch: `main`

Verified base SHA: `{{ISSUES_453_477_PLANNING_MERGE_SHA}}`

Granted capabilities:

- `RO` for read-only inspection of the exact GitHub issue URLs in the network
  allowlist below.
- `II` for isolated implementation and focused local validation only in the
  assigned worktree and owned files below.

Continuous execution is authorized only for this phase sequence:

1. Read-only preflight and required-context review.
2. Isolated producer, schema, fixture, test, and technical-documentation work.
3. Focused local validation and handoff.

Do not stop between those phases unless a stop condition below is met. Stop
after the II handoff. `HV-READ`, `HV-WORKFLOW`, `RL-PREPARE`, `RL-MERGE`, and HQ
are not granted.

Exact branch: `issue-453-source-to-screen-coverage`

Exact worktree: `<repo-parent>\CCLD-complaints-poc-issue-453`

The dispatcher substitutes the exact local repository parent outside tracked
content. Do not add a personal path to code, docs, fixtures, output, or handoff.

Network allowlist, read-only only:

- `https://github.com/nicho1ab/RecordsTracker/issues/453` and its comments.
- `https://github.com/nicho1ab/RecordsTracker/issues/477` and its comments.
- `https://github.com/nicho1ab/RecordsTracker/issues/490` and its comments.

Use the connected GitHub app only for those issue reads if available. Do not
modify issue state, comments, labels, assignees, or reactions. Do not access a
source site, deployed database, remote runtime, search engine, or URL outside the
allowlist.

Browser/computer-use allowlist: none. Do not use browser or computer-use tools.

Required checks for a later PR remain `validate`, `docs-check`, `fixtures`, and
`security`, but this task has no RL-PREPARE authority and must not create or
monitor a PR.

RL-MERGE granted: no.

## Goal

Complete Issue #453's deterministic, aggregate-only source-to-screen coverage
producer by extending the existing `source_to_screen_audit` foundation to emit
the versioned Issues #453/#477 contract package.

The producer must measure field-level and pipeline-stage coverage; classify the
approved missing, failure, conflict, and intentional states; report safe
operational aggregates from existing read-only boundaries; reconcile all totals;
compare explicit governed baselines and thresholds; and serialize deterministic
JSON, JSONL, and aggregate CSV without retaining record values or source bodies.

This task does not implement operator UI, routes, authorization, retrieval,
refresh, import, backfill, job actions, persistence changes, deployment, or QNAP
operations.

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
- `docs/data/source-to-screen-audit.md`
- `docs/data/source-to-screen-inventory.md`
- `docs/data/source-to-screen-remediation-plan.md`

Read GitHub Issues #453, #477, and #490 plus their comments from the exact
allowlist. The shared coverage contract `1.0.0` is required and frozen for this
workstream. Do not edit a planning-package file or reinterpret an enum,
invariant, authorization boundary, source-selection state, or privacy rule.

Preserve Issue #490's outcome: existing program-specific sources are retained
for the evaluated scope, every statewide candidate remains inactive, no
statewide completeness baseline exists, no refresh cadence is approved, and raw
value `733` has no approved STRTP or other facility-type mapping.

## Preflight

Before any write:

1. Confirm the current worktree and branch exactly match this prompt.
2. Confirm `HEAD`, local `main`, and `origin/main` all equal
   `{{ISSUES_453_477_PLANNING_MERGE_SHA}}`.
3. Confirm the assigned worktree is clean.
4. Inspect branches, worktrees, unpushed commits, active ownership, and possible
   file overlap.
5. Confirm Workstream B has no write authority over a Workstream A path.
6. Confirm all dispatch placeholders are replaced.
7. Confirm `data/processed/source-to-screen-audit/**` is ignored before writing
   generated artifacts.

Stop and report any mismatch. Do not create a different branch or worktree,
clean another worktree, or change local/global Git configuration.

## Exclusive tracked-file ownership

You may create or edit only:

- `src/ccld_complaints/source_to_screen_audit.py`
- `src/ccld_complaints/source_to_screen_catalog.py`
- `schemas/issues-453-477-coverage-report-v1.schema.json`
- `tests/unit/test_source_to_screen_audit.py`
- `tests/fixtures/source_to_screen_coverage/**`
- `docs/data/source-to-screen-audit.md`
- `docs/data/source-to-screen-inventory.md`
- `docs/data/source-to-screen-remediation-plan.md`
- `docs/analysis/issue-453-source-to-screen-coverage.md`

Use the smallest subset needed. Reuse the existing
`python -m ccld_complaints.source_to_screen_audit` entry point instead of adding
a duplicate CLI unless a concrete blocker is documented. Generated packages may
be written only under ignored `data/processed/source-to-screen-audit/**` and
must remain untracked.

## Prohibited paths and actions

Do not edit:

- any `src/ccld_complaints/hosted_app/**` file;
- any Workstream B test, fixture, evidence script, or operator document;
- any `docs/planning/issues-453-477-*.md` file;
- `docs/planning/issue-453-codex-prompt.md`;
- `docs/planning/issue-477-read-only-dashboard-codex-prompt.md`;
- `CHANGELOG.md`;
- `ROADMAP.md`;
- `GOVERNANCE_INVENTORY.md`;
- any final Issue #453 or #477 completion report;
- any shared navigation, contract-version registry, index, or combined summary;
- application auth, route, UI, retrieval, import, backfill, checkpoint, job,
  persistence, schema/migration, deployment, Docker, QNAP, or Cloudflare files.

Do not:

- add or change a canonical field, persisted schema, migration, table, database
  row, import, backfill, source connector, retrieval, or refresh behavior;
- access a deployed database, QNAP, SSH, Docker/Compose runtime, cloud console,
  private host, or production-like service;
- implement an operator route, template, dashboard, download, authorization
  rule, retry, dry-run/apply submission, cancel, resume, or other job action;
- use a live source call in code, fixtures, tests, or validation;
- store or emit record values, source bodies, narratives, raw HTML, source URLs,
  raw paths, absolute paths, private URLs, container names, secrets, credentials,
  authentication claims, stack traces, SQL, or uncontrolled errors;
- label `733` as STRTP or any facility type;
- claim a statewide source, source-of-record, completeness, currentness,
  freshness, or cadence is approved;
- stage, commit, push, create/update/monitor a PR, merge, clean up, close an
  issue, deploy, or begin another issue.

## Implementation requirements

### Contract package

Implement contract `1.0.0` exactly as documented in
`issues-453-477-shared-coverage-contract.md`:

- `manifest.json`;
- aggregate-only `coverage-report.json`;
- operator-safe `operator-facility-index.jsonl` when fixture/read boundary data
  is available;
- operator-safe `operator-job-index.jsonl` when existing read boundary data is
  available;
- optional aggregate-only `aggregate-coverage.csv`.

The schema must close required enums and reject prohibited/unknown values where
the contract requires a closed set. All artifact versions, report IDs, hashes,
and availability states must reconcile with the manifest.

### Deterministic identity and serialization

- Implement the exact canonical identity tuple and
  `coverage-report-v1-<sha256>` report ID.
- Capture `generated_at` once in UTC `Z` form and exclude it from identity.
- Use canonical JSON/JSONL/CSV serialization, stable field order, stable row
  order, LF line endings, and lowercase SHA-256 values.
- Prove repeat generation from identical inputs produces identical identities,
  classifications, counts, ordering, and artifact bytes except for explicitly
  allowed generation metadata.
- Reject two different result payloads that claim the same evaluation identity.

### Field and pipeline-stage coverage

Consume the approved source-to-screen inventory rather than creating a parallel
field catalog. Report every required stage:

- source presence;
- extraction;
- normalization;
- canonical allocation;
- PostgreSQL population;
- read-model exposure;
- complaint-page rendering;
- facility-hub rendering.

For each field/stage, emit only the aggregate eligible and mutually exclusive
state counts. Preserve blank, absent, unavailable, unsupported, conflict,
failure, skipped, internal, and not-applicable semantics. Do not retain or
serialize the inspected values.

Implement every canonical terminal classification, including the Issue #453
alias mapping for source absent, source unavailable, and conflicting source.
Never collapse failure categories to generic missing.

### Operational aggregate bridge

Report refresh, retrieval, import, preserved-artifact, hash-validation,
checkpoint, job, processing, and change state only through existing read-only
boundaries or governed fixtures. Do not add a table, query raw source content,
or perform an operation.

Keep source-to-screen coverage and operational refresh state separate. Tests
must prove a successful operation can still have a rendering gap and a failed
operation can retain a previous accepted report.

### Aggregate reconciliation

Implement every contract invariant and stable invariant ID. Fail closed when an
invariant does not balance. The producer must not omit a failed invariant or
change counts to force a pass.

The dashboard consumer will treat `reconciliation_status=failed` as unavailable,
so include a controlled aggregate failure result without source values or error
text.

### Baselines, thresholds, and release assessment

Add versioned, explicit, deterministic baseline/threshold metadata under a
stable `criteria_set_id`. Use only retained existing or active accepted source
scope. Do not create a statewide baseline.

At minimum, assess:

- previously populated governed fields becoming blank;
- verified descriptive facility-type labels regressing to unresolved raw codes;
- unexpected facility-count decline against a named threshold;
- source-to-screen stage regression;
- aggregate reconciliation failure;
- unresolved/conflicting facility identity or type evidence.

The result is `passed`, `warning`, `failed`, or
`reviewed_exception_required`. An exception must be explicit data in the
criteria input; the producer does not approve it.

### Privacy and safe serialization

Use allowlists, not after-the-fact best-effort redaction, for output fields.
Retain defense-in-depth redaction/rejection at serialization boundaries.

The aggregate report and CSV contain no Facility IDs. The operator facility
index contains only the exact contract-permitted Facility ID metadata. Reject
any fixture or adapter value containing narratives, raw HTML, secrets,
credentials, private/absolute paths, private URLs, container names,
authentication claims, connection strings, stack traces, SQL, or uncontrolled
errors.

### Fixture scenarios

Create deterministic producer fixtures for every named contract scenario:

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

Fixtures must be tiny, synthetic or minimized, safe to publish, documented, and
incapable of acting as raw-source dumps or production imports.

### Technical documentation

Update the existing source-to-screen audit documentation and create
`docs/analysis/issue-453-source-to-screen-coverage.md` covering:

- contract and producer schema versions;
- package artifacts and identities;
- exact field/stage and failure semantics;
- baseline, threshold, release, and reconciliation behavior;
- aggregate-only and operator-index privacy boundaries;
- local fixture/report command and runtime-command shape without executing a
  deployed runtime;
- retention/provenance behavior and pending retention-policy duration;
- Issue #490 source/cadence/`733` limits;
- validation performed and remaining production-style integration evidence.

Do not create a final Issue #453 completion report or say the issue is complete
solely because code exists.

## Acceptance criteria

- Contract `1.0.0` validates through the new schema.
- Report identity, stable IDs, ordering, serialization, and hashes are
  deterministic and portable.
- Output contains only aggregate counts and contract-permitted safe metadata.
- Every required coverage stage and terminal failure category is represented.
- Blank, absent, unavailable, unsupported, conflict, warning, failure, skipped,
  unchanged, changed, successful, and not-yet-processed remain distinct.
- Source-to-screen coverage and operational refresh status are not inferred
  from each other.
- All aggregate and page invariants reconcile or fail closed.
- Baseline/threshold regression results are explicit and actionable.
- The raw `733` fixture remains unresolved and is not labeled.
- Aggregate CSV has no Facility IDs; operator indexes contain no prohibited
  fields or values.
- No input row value or source body is retained in output.
- No database/source/job mutation occurs.
- Issue #490's inactive statewide candidate and unapproved cadence remain
  explicit.
- Only Workstream A owned tracked paths change.

## Focused validation

Run the new/changed regression independently:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_source_to_screen_audit.py -q
```

Generate one contract package from governed fixtures into an ignored temporary
output directory, run it twice, and compare stable identities, canonical
artifacts, ordering, and hashes. Do not use a live database or source call.

Run targeted lint and type checks:

```powershell
.\.venv\Scripts\ruff.exe check src\ccld_complaints\source_to_screen_audit.py src\ccld_complaints\source_to_screen_catalog.py tests\unit\test_source_to_screen_audit.py
```

```powershell
.\.venv\Scripts\mypy.exe src\ccld_complaints\source_to_screen_audit.py src\ccld_complaints\source_to_screen_catalog.py
```

Run documentation validation and the focused documentation checks:

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

Also run focused assertions proving:

- schema validity and closed enums;
- deterministic and portable report identity/order;
- every reconciliation invariant;
- every named contract fixture;
- prohibited-content rejection and no record values/source bodies;
- aggregate CSV and operator-index boundaries;
- no statewide/cadence/`733` claim;
- the changed/untracked path set is a subset of Workstream A ownership;
- no Workstream B or reserved integration file changed.

Do not run the complete test suite unless a focused failure shows it is needed;
if broader validation becomes necessary, stop and request an updated task. Do
not present an unrun check as passed.

## Stop conditions

Stop before further editing and report if:

- preflight branch, worktree, SHA, clean state, ownership, or a dispatch
  placeholder is wrong;
- a required path is not exclusively owned by Workstream A;
- contract `1.0.0` is ambiguous or requires a semantic/breaking change;
- a field cannot be traced through the governed inventory without inventing a
  canonical field or classification;
- a source record value/body would need to be retained;
- a source, deployed database, QNAP, browser, network target, secret, private
  path, or authentication value is required;
- a statewide source/cadence or `733` mapping assumption is required;
- implementation needs operator UI/routes/auth/downloads, mutation, schema,
  migration, retrieval, import, backfill, checkpoint, job action, deployment,
  or a reserved integration file;
- validation exposes a real contract/reconciliation/privacy defect that cannot
  be fixed inside owned paths.

An unavailable stage or runtime database is a valid aggregate state. Do not
substitute a fixture as production data, weaken an invariant, widen an enum, or
change a threshold merely to pass validation.

## Final handoff and exact stop point

Stop after implementation and focused local validation. Report:

1. Verified base SHA, branch, worktree template, capabilities, phase sequence,
   and network/browser allowlists used.
2. Exact files changed.
3. Contract, package, schema, identity, coverage, operational, reconciliation,
   and release-assessment behavior implemented.
4. Fixture scenarios and generated ignored artifact locations/hashes.
5. Every validation command and pass/fail result, including intentionally unrun
   checks.
6. Documentation impact.
7. Security/privacy impact and prohibited-content results.
8. Issue #490/statewide/cadence/`733` confirmation.
9. Exact unresolved decisions and integration dependencies.
10. Confirmation that Workstream B and all reserved files were untouched.
11. Confirmation that no app route/UI/auth, data, job, source, deployment, QNAP,
    Git lifecycle, PR, issue, or external mutable state changed.

Do not stage, commit, push, create or update a PR, monitor checks, merge, clean
up, close Issue #453, deploy, access QNAP, or begin Issue #477 or another task.

---
