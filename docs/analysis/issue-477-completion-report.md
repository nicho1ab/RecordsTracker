# Issue #477 operator source-coverage dashboard completion report

## Completion decision

Issue #477 is repository-complete for the supported read-only operator
source-coverage dashboard and may close after this completion record merges.
The repository scope is the authenticated, GET-only diagnostic surface defined
by the merged Issues #453/#477 ownership and contract package. It does not
include the mutation console proposed in the issue's original broad wording.

Retry, dry-run submission, apply, confirmation, cancel, resume, backfill or
retrieval execution, job/checkpoint mutation, scheduling, persistence,
retention cleanup, deployment, and infrastructure administration remain
separately governed work. Their absence is not missing Issue #477 dashboard
code and does not authorize adding them to the completed routes.

## Merged implementation record

- PR #510 defined contract `1.0.0`, producer/consumer ownership, and the
  read-only/no-mutation boundary.
- PR #512 added the authenticated summary, facility, job, aggregate CSV, and
  bounded Facility ID CSV routes with deterministic fixture evidence.
- PR #513 connected the dashboard to Issue #453's stable validated producer
  boundary without duplicating coverage calculations.
- PR #515 added the production-style bridge: verified Cloudflare Access JWT
  authentication, exact operator-email allowlisting, SELECT-only PostgreSQL
  package generation, atomic validated publication, and automated
  LocalProductionAuth/Hosted acceptance tooling.

The exact routes are:

- `/operator/source-coverage`;
- `/operator/source-coverage/facilities`;
- `/operator/source-coverage/jobs`;
- `/operator/source-coverage/export.csv`; and
- `/operator/source-coverage/facility-ids.csv?group=<allowed-group>`.

They remain GET-only. No action route, action form, mutation API, or mutating
GET exists.

## Acceptance criteria

### Authorization and information tiers

Every route authenticates and authorizes before opening the configured package.
Production requests require a verified Cloudflare Access JWT and an exact,
case-insensitive email match in `CCLD_OPERATOR_COVERAGE_ALLOWED_EMAILS`. The
actor must have the existing `audit_read` permission and matching scope.
Unauthenticated, disabled, revoked, reviewer/tester, non-allowlisted, and
out-of-scope actors are denied before package data is read or serialized.

Operator navigation is rendered only in the authorized operator context.
Reviewer navigation, pages, APIs, and exports do not expose the operator route
or operator diagnostics.

### Deterministic contract consumption

The dashboard imports the stable `ccld_complaints.source_to_screen_coverage`
read boundary, not the producer implementation. Producer-owned schema,
identities, hashes, media types, closed enums, counts, classifications,
release assessment, and reconciliation are validated without dashboard-owned
recounting or reclassification.

Aggregate counts and safe facility/job indexes reconcile at the contract
boundary. Invalid version, identity, hash, media type, enum, artifact, or
reconciliation state fails closed without serializing stale package values.
Unavailable operational dimensions remain unavailable rather than becoming
zero or success.

### Bounded reads and safe exports

Facility filtering and sorting use contract allowlists. Page size defaults to
25 and is capped at 100. Deterministic ordering includes normalized Facility ID
and facility-entry identity tie-breakers, with null timestamps last. Opaque
report/filter/sort-bound seek cursors provide adjacent navigation without SQL
`OFFSET`, page-number jumps, or deep offset traversal.

The aggregate export contains no Facility IDs or operator-index rows. Facility
ID downloads require exactly one approved group and emit only `report_id`,
`group`, and `facility_id` in deterministic order. All routes remain read-only.

### Truthful and accessible states

Automated coverage includes complete, verified empty, filtered empty, partial,
unavailable, interrupted with previous accepted data active, controlled
failure, hash failure, reconciliation failure, unsupported version, raw `733`
unresolved, authorization denial, and adjacent keyset pages.

Semantic headings, table captions and scoped headers, labeled filters,
keyboard-operable controls, visible focus, non-color-only status text,
responsive reflow, 200% zoom, long-identifier wrapping, and print-safe output
are covered by the deterministic evidence tool and tests.

### Privacy and failure safety

The validated package boundary and presentation tests reject or exclude
complaint narratives, allegation text, raw HTML/source bodies, credentials,
tokens, cookies, authentication claims, private URLs or paths, container/host
details, connection strings, SQL, stack traces, and uncontrolled exception
content. Only safe stable identifiers, aggregates, controlled categories, and
contract-approved operator metadata can render.

## Evidence record

The integrated fixture/producer evidence from PR #513 recorded 23 captures and
590 passing assertions, including responsive, keyboard, print, privacy,
authorization, export, reconciliation, and failure-state evidence. Its ignored
ZIP SHA-256 was
`f22142cce46c50ad2c69613b26fcfe591f5320d1eb791e021facc43bb78d6a66`.

The production-style bridge from PR #515 recorded 20 LocalProductionAuth
captures and 113 of 113 passing assertions. Its ignored evidence ZIP SHA-256
was `df35b1cbac3e456cd1f0b7db93bf934fafa2ef89d2fb466b9ebfb0912b2da389`.
The runtime SQL was verified SELECT-only and the safe database/package/facility
index totals reconciled.

The human-operated deployment record states that the read-only runtime was
deployed at `d7e9b1fff9e1826c3387a7313777d14c1480d3b4` and its package/database
verification passed. This repository completion task does not repeat, extend,
or claim a new deployment.

## Completion-task validation

Validation from the completion branch starting at
`9391ca35b78d8fcf26c00bc8f887cd6375625185` passed:

- focused dashboard, evidence, runtime-acceptance, production-auth, runtime
  coverage, and dispatch integration tests: 62 passed;
- complete local pytest suite: 1,314 passed and two expected isolated
  PostgreSQL performance tests skipped because the opt-in database and schema-
  mutation environment was not configured;
- repository-wide Ruff: passed;
- repository-wide mypy: passed for 74 source files;
- documentation validation: passed;
- documentation-quality tests: 25 passed;
- repository no-secrets scan: passed; and
- `git diff --check`: passed.

No required failure was skipped or weakened. The two full-suite skips are
environmental opt-ins unrelated to Issue #477 and do not alter dashboard
acceptance coverage.

## Human-controlled acceptance boundary

Automated Hosted UI acceptance remains blocked until a user approves a
process-local `CCLD_OPERATOR_COVERAGE_ACCEPTANCE_HEADER_PROVIDER_COMMAND` that
supplies a current Cloudflare assertion in memory. The acceptance tooling
correctly refuses to read cookies or browser profiles, persist assertions or
headers, use service-token secrets, or bypass Cloudflare Access.

That blocker is an external acceptance prerequisite, not missing repository
implementation. QNAP deployment, Cloudflare administration, production
configuration, and hosted execution remain human-controlled. A later release
may run the existing Hosted acceptance command at its exact deployed merge SHA;
that does not reopen Issue #477's completed read-only code scope.

## Preserved limitations and deferred work

- Retention remains `pending_policy`; automated deletion is not authorized.
- Missing approved job/checkpoint read boundaries remain explicitly
  unavailable.
- Runtime coverage does not prove statewide completeness, freshness, absence
  of complaints, legal conclusions, deployment success, or correct rendering
  without corresponding evidence.
- Raw `733` remains unresolved.
- Mutation, scheduled refresh/recovery, ArcGIS operational controls, and
  deployment work remain in separately governed issues and phases. This task
  does not begin Issues #530 through #533 and creates no new follow-up issue.

## Closure gate

After this completion evidence merges and the required repository checks pass,
Issue #477 can close as completed for its supported read-only operator dashboard
scope. The closure note must preserve the human-controlled Hosted acceptance
blocker and the separate mutation/scheduling/deployment boundaries; it must not
claim new deployment, statewide completeness, retention automation, or mutation
functionality.
