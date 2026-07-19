# Issues #453 and #477 parallel ownership

## Purpose

This document defines the non-overlapping branches, worktrees, tracked-file
ownership, coordination contract, and stop points for Issue #453 coverage
reporting and the read-only first phase of Issue #477 operator coverage
dashboard work.

Neither workstream may begin until the planning change containing this document
and the [shared coverage contract](issues-453-477-shared-coverage-contract.md)
has merged to `main`.

The executable task templates are:

- [Issue #453 coverage-report prompt](issue-453-codex-prompt.md)
- [Issue #477 read-only dashboard prompt](issue-477-read-only-dashboard-codex-prompt.md)

## Planning baseline and dispatch gate

This planning branch was verified clean at base SHA
`a8a3b07eaa863baa46f78b7cfa6189979104e597`. The parallel workstreams must not
use that pre-merge SHA as their base. They begin from the later full 40-character
planning merge SHA.

Before either branch or worktree is created or assigned, the dispatcher must:

1. Confirm this planning package is merged to `main`.
2. Record the full planning merge SHA.
3. Verify `HEAD`, local `main`, and `origin/main` all equal that SHA and the base
   worktree is clean.
4. Inspect status, branches, worktrees, unpushed commits, active ownership, and
   possible tracked-file overlap.
5. Replace every `{{ISSUES_453_477_PLANNING_MERGE_SHA}}` placeholder in the
   selected prompt with that exact SHA.
6. Substitute the local repository parent for `<repo-parent>` outside tracked
   content. Do not commit a user-specific path.
7. Confirm the other workstream has no write authority over the selected
   workstream's owned paths.
8. Confirm every capability, phase, allowlist, validation requirement, and stop
   point in the prompt remains exact.
9. Stop on unexplained dirty state, divergence, unpushed work, active-task
   overlap, an unexpected branch/worktree, or an unfilled placeholder.

The user-specified worktree directory names are fixed. The neutral
`<repo-parent>` prefix preserves public repository hygiene while allowing the
dispatcher to use the exact local repository parent.

## Branches and worktrees

| Phase | Branch | Worktree |
| --- | --- | --- |
| Workstream A — Issue #453 | `issue-453-source-to-screen-coverage` | `<repo-parent>\CCLD-complaints-poc-issue-453` |
| Workstream B — Issue #477 read-only phase | `issue-477-operator-coverage-dashboard` | `<repo-parent>\CCLD-complaints-poc-issue-477` |
| Later integration | `integrate-453-477-coverage-dashboard` | `<repo-parent>\CCLD-complaints-poc-integrate-453-477` |

Both parallel branches start from the same planning merge SHA. They do not merge
into each other, modify each other's files, or perform repository lifecycle
actions. Each stops after its own implementation, focused validation, evidence
when assigned, and handoff.

## Coordination model

```text
planning package merged to main
        |
        +-----------------------------------+
        |                                   |
        v                                   v
Workstream A                           Workstream B
Issue #453 producer                    Issue #477 consumer
coverage calculations                  fixture contract adapter
schema and serialization               read-only operator routes
producer fixtures                      presentation and downloads
        |                                   |
        +----------------+------------------+
                         |
                         v
                later integration branch
                compare contract fixtures
                connect producer to adapter
                update reserved shared files
```

The shared contract is frozen at `1.0.0` for the parallel phase. Neither branch
may edit the four planning-package files. A required breaking or semantic
contract change is reported as an integration blocker.

## Workstream A — Issue #453 coverage reporting

### Responsibility

Workstream A owns:

- the coverage-report domain model;
- the existing source-to-screen audit/catalog producer foundation;
- deterministic field, stage, source, facility, and operational aggregate
  calculations;
- contract-package generation and JSON Schema;
- safe JSON, JSONL, and CSV serialization;
- the existing Python module CLI/internal reporting entry point;
- governed producer fixtures;
- redaction, deterministic identity/order, path portability, reconciliation,
  threshold, and failure-category tests;
- Issue #453 technical documentation.

### Exclusive tracked-file ownership

Workstream A may create or edit only:

- `src/ccld_complaints/source_to_screen_audit.py`
- `src/ccld_complaints/source_to_screen_catalog.py`
- `schemas/issues-453-477-coverage-report-v1.schema.json`
- `tests/unit/test_source_to_screen_audit.py`
- `tests/fixtures/source_to_screen_coverage/**`
- `docs/data/source-to-screen-audit.md`
- `docs/data/source-to-screen-inventory.md`
- `docs/data/source-to-screen-remediation-plan.md`
- `docs/analysis/issue-453-source-to-screen-coverage.md`

Generated report packages may be written only beneath the existing ignored
boundary `data/processed/source-to-screen-audit/**`. They remain untracked. If
the path is not ignored, Workstream A stops; it does not edit `.gitignore`.

### Workstream A exclusions

Workstream A must not own or edit:

- hosted application routes, templates, UI, shell, styles, or navigation;
- authorization or authentication policy;
- operator adapters, downloads, evidence capture, or Issue #477 documentation;
- retrieval, refresh, import, backfill, checkpoint, or job-action services;
- databases, schemas for persisted data, migrations, or initialization;
- any Workstream B path;
- any reserved integration file or planning-package file.

Workstream A reports job/retrieval/import aggregates only through existing
read-only data boundaries and deterministic fixtures. It does not start, retry,
apply, cancel, resume, or mutate a job.

## Workstream B — Issue #477 read-only operator dashboard

### Responsibility

Workstream B owns:

- direct authenticated operator routes under `/operator/source-coverage`;
- a narrow read-only adapter that validates and consumes contract `1.x` fixture
  packages;
- summary, separate coverage/operations presentation, filtering, sorting,
  seek/keyset pagination, and safe facility/job drill-down;
- empty, partial, unavailable, interrupted, failed, hash-failed,
  reconciliation-failed, and version-mismatch states;
- aggregate-safe CSV and explicit Facility ID list downloads;
- reuse of the existing `audit_read` permission and scope boundary;
- responsive, keyboard, focus, non-color-only, zoom, print, and long-content
  behavior;
- automated local read-only route/evidence capture;
- operator-facing documentation and focused tests.

### Exact read-only routes

- `/operator/source-coverage`
- `/operator/source-coverage/facilities`
- `/operator/source-coverage/jobs`
- `/operator/source-coverage/export.csv`
- `/operator/source-coverage/facility-ids.csv?group=<allowed-group>`

The routes are direct operator routes. They are not added to reviewer navigation
during the parallel phase.

### Exclusive tracked-file ownership

Workstream B may create or edit only:

- `src/ccld_complaints/hosted_app/operator_coverage_dashboard.py`
- `src/ccld_complaints/hosted_app/app.py`
- `tests/unit/test_hosted_operator_coverage_dashboard.py`
- `tests/unit/test_hosted_operator_coverage_evidence.py`
- `tests/unit/test_hosted_app_scaffold.py`
- `tests/fixtures/hosted_operator_coverage_dashboard/**`
- `scripts/capture-operator-coverage-dashboard-evidence.ps1`
- `docs/developer/operator-source-coverage-dashboard.md`

Generated local evidence may be written only under the existing ignored
`data/processed/ui-evidence/**` boundary, including the corresponding zip. It
remains untracked. If the boundary is unavailable or not ignored, Workstream B
stops rather than changing `.gitignore`.

### Fixture and adapter rule

Workstream B develops against deterministic contract fixtures in its exclusive
fixture directory. The adapter accepts only the shared contract package shape,
validates version, hashes, required fields, closed enums, and reconciliation,
then presents producer-supplied values.

It must not import Workstream A implementation modules, reproduce Workstream A
counting or classification logic, inspect raw source bodies, or treat fixtures
as production data. Production-style mode without an explicitly configured and
validated package shows the unavailable state. Connecting the final Workstream A
artifact source is reserved for integration.

### Workstream B exclusions for this phase

Workstream B must not implement:

- live retry or retry submission;
- apply or dry-run submission;
- cancellation or resume;
- database, source-derived, reviewer-created, job, artifact, or checkpoint
  mutation;
- new job tables, persisted operator state, schemas, migrations, or database
  initialization;
- source retrieval, connector execution, import, backfill, or schedule behavior;
- authorization roles, permissions, targets, middleware, sessions, cookies, or
  provider changes;
- reviewer routes, reviewer content, reviewer navigation, or reviewer exports;
- Workstream A calculations, schema, fixtures, or technical documentation;
- any reserved integration file or planning-package file.

`retry_eligibility`, `execution_mode`, and checkpoint state are display-only.
There are no POST, PUT, PATCH, DELETE, action form, or action API routes.

## Tracked-file ownership proof

The two owned path sets above have an empty intersection. The only existing
broad route file assigned to a parallel workstream is
`src/ccld_complaints/hosted_app/app.py`, and it belongs exclusively to Workstream
B. Workstream A owns no hosted application file. Workstream B owns no producer,
schema, source-to-screen data document, or producer fixture.

Both workstreams validate their changed/untracked path set against their own
allowlist before handoff. Discovery of an overlapping required path is a stop
condition, not permission to edit it.

## Reserved for the later integration branch

Neither parallel workstream may modify:

- `CHANGELOG.md`
- `ROADMAP.md`
- `GOVERNANCE_INVENTORY.md`
- the final Issue #453 completion report
- the final Issue #477 completion report
- shared navigation changes or `src/ccld_complaints/hosted_app/ui_shell.py`
- a shared contract-version registry
- any shared index or combined completion summary
- any `docs/planning/issues-453-477-*.md` file
- `docs/planning/issue-453-codex-prompt.md`
- `docs/planning/issue-477-read-only-dashboard-codex-prompt.md`

The integration branch exclusively owns:

- comparing the A and B contract fixture vectors and resolving compatible
  serialization differences;
- wiring the B adapter to validated A output outside fixture mode;
- any shared contract-version registry;
- any shared navigation placement;
- combined cross-workstream validation and evidence reconciliation;
- authorized updates to the reserved roadmap, changelog, governance inventory,
  indexes, and final completion reports.

Integration remains read-only with respect to source retrieval and operator job
actions unless a separate task grants more. It does not authorize statewide
source selection, cadence, deployment, QNAP, database mutation, or the later
Issue #477 mutation phase.

## Evidence exchange

### Workstream A handoff

Workstream A reports:

- verified base SHA and branch;
- contract and producer schema versions;
- report/criteria/evaluation identity rules used;
- owned files changed;
- fixture-vector results and artifact hashes;
- reconciliation and release-assessment results;
- redaction, determinism, portability, and focused validation;
- exact unresolved producer or contract questions.

### Workstream B handoff

Workstream B reports:

- verified base SHA and branch;
- contract compatibility range and fixtures consumed;
- exact routes and existing permission used;
- owned files changed;
- safe export and no-write proofs;
- automated route, responsive, accessibility, print, and state evidence paths;
- authorization denial results for reviewer/tester roles;
- exact unresolved adapter, design, or integration questions.

Neither branch instructs the other to rewrite its owned files. A discovered
defect is returned as a separately approved follow-up or integration blocker.

## Coordination checkpoints

1. **Start:** planning merge SHA, clean synchronized worktrees, capabilities,
   allowlists, and exclusive ownership are confirmed.
2. **Contract:** both workstreams pin contract `1.0.0`; semantic changes stop
   parallel work and return to integration/planning.
3. **Fixture:** each workstream implements all named contract scenarios in its
   own directory without copying implementation logic.
4. **Producer:** A freezes its schema and validated fixture output before final
   handoff.
5. **Consumer:** B records the exact contract version and fixture set used; it
   does not depend on unmerged A code.
6. **Evidence:** B captures only GET/navigation evidence on the local route
   allowlist after II validation.
7. **Integration:** the integration owner verifies both branch heads, path
   non-overlap, reserved-file integrity, validation, evidence, and unresolved
   decisions before combining work.

## Later integration order

1. Create the integration branch from clean synchronized `main` after both
   workstreams stop and report.
2. Bring in Workstream A without changing A-owned semantics.
3. Bring in Workstream B without changing B-owned presentation semantics.
4. Compare schemas, fixture vectors, hashes, enum values, and reconciliation.
5. Wire the adapter to validated producer output through the narrow contract
   boundary.
6. Modify only explicitly authorized integration/reserved files.
7. Run combined focused validation, docs, security, evidence, and diff checks.
8. Stop for human review. Do not begin the later mutation phase.

## Common stop conditions

Either workstream stops and reports if:

- the planning package is not merged or the dispatch SHA is missing/mismatched;
- branch, worktree, clean state, `main`, `origin/main`, ownership, or an active
  task is unexplained;
- a required path is outside its exclusive allowlist or overlaps the other
  workstream;
- contract meaning must change or a contract value is ambiguous;
- a statewide source, cadence, source-precedence, or `733` mapping assumption is
  required;
- a schema, migration, database mutation, job action, retrieval, backfill,
  deployment, QNAP, or other prohibited action is required;
- a secret, credential, private URL, private path, source narrative, raw HTML,
  uncontrolled error, or authentication claim would be read or exposed;
- required fixture, validation, or evidence cannot be produced without
  expanding capability or scope.

An unavailable report, database, fixture state, or evidence state is a valid
result. Do not substitute an unapproved source, data path, browser action, or
mutable workflow.
