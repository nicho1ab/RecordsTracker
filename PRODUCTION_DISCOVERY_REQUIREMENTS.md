# Production-Discovery Requirements

## Purpose

This document defines the minimum product requirements that must exist before a
hosted online tester version of the primary reviewer application is built.

The project has crossed the Datasette exit threshold for the primary future
reviewer experience. Datasette remains retained for validation, inspection,
debugging, local exploration, and export support, but hosted reviewer work must
start from these requirements and later architecture ADRs rather than from more
Datasette-primary UX.

This document does not choose a production stack, add dependencies, alter
schemas, change extraction behavior, add connectors, or define new
source-derived canonical fields.

## Current implementation status

The local hosted tester MVP scaffold has begun under ADR-0012. Current hosted
implementation is limited to a local Python standard-library app shell, health
and smoke validation, local setup checks, and a read-only `/source-records`
list/detail shell with local sample filtering/search and fixture/sample-only
source traceability summary panels over fixture/sample records with
semantic/accessibility validation. It also includes a read-only `/facilities`
list/detail sample view backed only by committed tiny public-source facility
fixtures and manifest placeholder metadata, with fixture-only source coverage
indicators and related fixture/sample source-record context on facility detail
pages where the local sample mapping exists.

This scaffold is not a hosted tester-ready stateful reviewer workflow. It does not load
live public data, perform real provider login, authorize production HTTP
routes, persist reviewer-created state, create queues, support annotations,
corrections, exports, feedback, audit trail, reset/reload, hosted live crawling,
hosted connector execution, read ignored raw CSVs or generated profiling
outputs, public deployment, production auth, Azure, AWS, cloud deployment,
production operations, or public URL behavior. A QNAP-first Docker Compose
runtime envelope now exists for production-like app/PostgreSQL validation, but it
does not make the scaffold hosted tester-ready.

Minimal PostgreSQL/Alembic project wiring now exists for local/test validation:
dependency declarations, no-secret database URL validation, an Alembic script
location, one domain migration for controlled seeded corpus import batch
metadata and source-derived record staging, a local validated JSON artifact
importer, a local/test database-backed read service over staged source-derived
records, a local/test auth boundary scaffold with actor, role, scope, target,
and audit-context models, a narrow local/test auth provider integration
planning seam for non-secret readiness/configuration planning, a narrow local/test authenticated source-derived
HTTP/API read route seam, a narrow local/test authenticated read-only reviewer
workflow shell over the route seam, a narrow local/test reviewer-created state
persistence scaffold table and service boundary, a narrow local/test audit event
persistence scaffold for successful reviewer-created state scaffold writes only,
a local/test authenticated audit history read route seam over those audit rows,
a local/test audit coverage planning seam over current and deferred audit categories,
a narrow local/test authenticated reviewer-created state read route seam for
persisted scaffold rows with schema-backed filters and bounded search, a narrow local/test reviewer workflow shell detail
integration that composes associated reviewer-created state read output for a
selected source-derived record, a compact workflow shell state summary derived
from that associated state output, a narrow local/test authenticated reviewer
note creation route over the existing reviewer-created state scaffold, a narrow
local/test authenticated reviewer status creation route over the existing
reviewer-created state scaffold, narrow local/test workflow-shell note and
status actions that resolve the selected source-derived detail context before
delegating to reviewer-created write routes, a local/test authenticated reset/reload dry-run route
seam, a separate local/test reset/reload operational planning metadata
scaffold, a narrow local/test read-only planning metadata route seam, a narrow
local/test reset/reload execution-plan route seam, and
scaffold/API boundary descriptors. The provider integration planning seam
validates the accepted managed OpenID Connect/OAuth 2.0 provider class,
summarizes existing auth boundary models, accepts only non-secret readiness
inputs, and does not persist configuration, users, roles, claims, sessions, or
credentials. The audit coverage planning seam summarizes current audit scaffold
coverage, deferred hosted tester audit categories, actor attribution, target/
source context, and non-secret metadata rules without creating audit rows or
persisting planning records. The dry-run reports
what a future seeded corpus reset/reload would affect, including existing import
batch metadata, source-derived record counts by entity, future reviewer-created
state handling modes, required permissions, validation requirements, audit
requirements, scoped reviewer-created scaffold row counts, scoped audit scaffold
row counts, and deferred
destructive actions, without mutating data. When explicitly requested by
local/test code, it can persist one non-secret planning metadata record without
executing reset/reload and can read those persisted planning records through
permissioned local/test list/fetch handlers. The execution-plan route converts
those same summaries into ordered bounded non-destructive action steps and can
optionally persist an execution-plan artifact through the same operational
planning metadata scaffold. This path does
not implement real login flow, provider registration, tokens, cookies, auth
middleware, production API framework behavior, run migrations against a local
database during scaffold tests, load live public data, run connector execution,
automate production imports, execute reset/reload, archive or clear reviewer-
created state, persist audit events beyond the narrow reviewer-created state
write scaffold, expose audit history beyond that narrow local/test read seam,
create, update, or delete reviewer-created state through the read route seam,
edit or delete reviewer notes or statuses, create stateful queues, implement full
reviewer workflows, annotations, corrections, export packet behavior, or tester
feedback.

Persisted reviewer-created state scaffold rows can now be read through a narrow
local/test JSON route seam when tests or local callers provide an explicit
database, authenticated actor, and scope context with reviewer-state read
permission. That seam lists or fetches only non-secret scaffold fields, supports
schema-backed filters and bounded search over existing non-secret scaffold
fields, keeps reviewer-created state separate from source-derived records,
audit rows, and operational metadata, and does not implement read-route writes,
annotations, corrections, editable review status transitions, exports, real login,
sessions, or production auth middleware.

Reviewer notes can now be created through a narrow local/test authenticated
route when tests or local callers provide an explicit database, actor, and scope
context with reviewer-state write permission. The route writes bounded non-
secret note text into the existing reviewer-created scaffold payload, reuses the
existing scaffold state kind and audit event path, and does not change the
domain schema, source-derived records, note editing/deletion behavior, exports,
or production auth behavior.

The reviewer workflow shell can now create a reviewer note for the selected
source-derived detail context through a narrow local/test action seam. The action
first resolves the selected source record through the existing source-derived
route, forces the reviewer note source-record binding from that resolved detail,
delegates to the existing reviewer note creation route, and returns created note
metadata plus refreshed workflow detail context for read-after-write tests.

Reviewer status values can now be created through a narrow local/test
authenticated route and workflow-shell action when tests or local callers provide
an explicit database, actor, and scope context with reviewer-state write
permission. The action accepts only bounded local/test status values, forces the
source-record binding from the selected detail context, stores the status as
reviewer-created scaffold data, creates the same audit event as other successful
reviewer-created writes, and returns refreshed workflow detail context for
read-after-write tests. It does not add status editing/deletion, queue
assignment, full workflow engine behavior, schema changes, exports, or
production auth behavior.

A thin local/test browser reviewer UI shell now exists at `/reviewer` and
`/reviewer/records` when the local scaffold process is running. It loads only
the tiny seeded fixture corpus into process-local test state and gives a local
tester a first browser path to list/search seeded source-derived records, open a
source-derived detail page, see list-level reviewer-created note/status
indicators, view a plain-language record summary, safe source traceability
fields, safe related seeded bundle context, reviewer-created notes/statuses,
CCLD return links, and record-specific feedback clues, submit a bounded reviewer
note, submit a bounded reviewer status, and see read-after-write reviewer-created
state. Narrative source fields are hidden in the browser shell. The UI delegates reads and writes to the existing
local/test workflow shell, reviewer-created state route, source-derived read
route, and audit scaffold; it does not add schema changes, production auth,
sessions, cookies, exports, reset/reload execution, hosted live crawling,
connector execution, deployment, hosted URLs, or full reviewer workflows.

A thin local/test CCLD record request page now exists at
`/ccld/records/request` when the local scaffold process is running. It accepts
a CCLD facility/license number and optional date range, reads only existing
seeded source-derived rows, shows matching seeded CCLD rows, and links matching
complaints into the reviewer UI. It validates digit-only CCLD identifiers and
date ranges, shows clear no-match guidance, and can load or refresh matching
records from local validated hosted seeded-corpus output into existing hosted
source-derived rows. The page now includes first-time user workflow guidance,
contextual help for facility/date/load/review terms, a `/ccld/help` page, and a
facility/date-scoped complaint review queue with source traceability summaries,
loaded-record context, reviewer-state indicators, progress counts, reviewer-
status filtering, reviewer note/status cues, source-traceability availability
cues, suggested next-record links, filtered-empty guidance, reviewer-detail
actions, and a structured copyable tester feedback checklist for manual external
sharing. Queue state is derived from existing source-derived records plus
existing reviewer-created note/status rows; it is not persisted as a separate
queue state model. Feedback is not persisted by the app in this slice.
The current local/test pages also include skip-to-main links, visible first-run
next-step guidance, specific form/action text, and manual checklist copy
instructions so keyboard and visible-text users can complete the MVP flow
without adding JavaScript, persistence, schemas, or new workflow state.
The local/test CCLD facility lookup page at `/ccld/facilities` reads configured
full local/test CCLD program facility reference CSV rows when available, falls
back to the committed tiny fixture when needed, searches safe scalar fields,
shows bounded results plus the active reference source, and carries the selected
facility/license number into the request page without persisting lookup data.
It does not run hosted live crawling, execute connectors, mutate reviewer-
created state from the request page, create audit rows, persist feedback, add non-CCLD source
selection, persist lookup data, or prove public-source completeness. A local/test CCLD-only artifact
builder now produces hosted seeded-corpus JSON from validated CCLD SQLite
pipeline output outside browser requests; remaining gaps include real provider
integration, production automation, persisted feedback, and deeper stateful
reviewer workflows.

The reviewer workflow shell can now include associated reviewer-created state
read route output in a selected source-record detail response when explicit
local/test source-derived and reviewer-created state contexts are supplied.
That integration can also include a compact summary derived from the associated
state route output. Queue and detail reads remain read-only, require both
source-derived read access and reviewer-state read access, and do not create or
modify reviewer-created state, source-derived rows, audit rows, or operational
metadata.

The next safe hosted-view increment should remain similarly narrow and
fixture-backed, preserving fixture/sample labels, explicit local/test actor
context, source-derived versus reviewer-created state separation, semantic
structure, accessibility validation, read/write permission separation, and the
no-real-login, no-full-reviewer-created-workflow, no-deployment boundary. Apply
the deferred-readiness/product-benefit gate in `GOVERNANCE_INVENTORY.md` before
sequencing source-verification planning, auth/provider readiness, audit/export,
reset/reload execution, deployment, database-backed lookup, persisted feedback,
or broader reviewer workflow work: the branch should unlock user-facing CCLD MVP
value or address a concrete MVP-blocking risk.

## Non-negotiable boundaries

- The public portal remains the source of record.
- Raw source files must remain preserved before extraction.
- Source-derived canonical data remains governed by `DATA_CONTRACT.md` and the
  JSON schemas.
- Reviewer-created state must stay separate from source-derived canonical data.
- Review state, annotations, correction proposals, queue position, tester
  feedback, and export inclusion decisions are application/reviewer state, not
  new source-derived facts.
- Future schema changes for persisted reviewer state require an ADR plus the
  normal schema, documentation, migration/init SQL, and test update path.
- Deterministic extraction and fixture-backed regression expectations remain in
  force.
- Accessibility, security, privacy, and cautious public-source language remain
  release gates.
- The system must not make unsupported legal, facility-wide, delay, harm, abuse,
  neglect, liability, or rights-deprivation conclusions.

## Minimum hosted reviewer workflows

A hosted tester version must support these workflows before it can be considered
ready for external tester use.

### Facility search and selection

Reviewers must be able to search or filter facilities by available
source-derived identifiers and names, select a facility, see source coverage at a
high level, and navigate into that facility's complaint review queue without
manual table joins.
For the CCLD-only MVP path, the first browser step should accept a CCLD
facility/license number and optional date range, then retrieve, prepare, or show
CCLD records for that scope before sending the user into reviewer pages. Hosted
browser requests must not run live crawling unless a later approved architecture
decision adds a safe execution model with tests, audit, rate limits, and source
traceability preservation.

### Complaint review queue

Reviewers must be able to see a guided queue of complaint records for the
selected facility or review scope. The queue must expose review state, source
traceability status, correction needs, annotation presence, export inclusion
state, and cautious review flags without treating flags as conclusions.

### Complaint detail review

Reviewers must be able to inspect one complaint with its source-derived fields,
related allegations, events, extraction audit context when available, known
missing values, and review-state history. The detail view must keep original
extracted values visible when corrections are proposed.

### Source verification

Reviewers must be able to verify each complaint against source URL, raw SHA-256
hash, retrieval timestamp, connector name and version, raw path when available,
report index or document type when available, and extraction audit rows when
field-level source text exists.

### Annotation

Reviewers must be able to add reviewer notes that are clearly marked as
annotations, attributed to a reviewer, timestamped, and connected to the
relevant facility, complaint, field, source document, or export packet context.
Annotations must not change raw source records or canonical extracted values.

### Proposed correction

Reviewers must be able to propose corrections to extracted values without
overwriting the original value. Each proposal must preserve the original value,
proposed value, source basis, reviewer, timestamp, decision status, and source
traceability to the relevant source document and extraction audit when
available.

### Facility pattern review

Reviewers must be able to review source-traceable facility-level patterns over
the derived dataset, including finding mix, allegation categories, date
missingness, review flags, source document coverage, and correction/annotation
counts. Pattern review must be framed as screening and comparison over extracted
public records, not facility-wide conclusions.

### Export packet preparation

Reviewers must be able to prepare source-traceable export packets from reviewed
records, explicitly include or exclude records from export, see unresolved
corrections or caution flags, and preserve clear headers, limitations, source
URLs, raw hashes, connector details, retrieval timestamps, and correction or
annotation context needed for review handoff.

### Tester feedback

Testers must be able to submit feedback tied to the workflow step, facility,
complaint, source document, export packet, or accessibility issue being tested.
Feedback must distinguish product usability feedback from proposed corrections
to source-derived data.

## Review-state requirements

Review state is reviewer/application state. It must not be stored as or treated
as source-derived canonical data unless a future schema ADR explicitly approves
the persistence model.

ADR-0008 defines the hosted tester MVP data and review-state model boundary. It
requires a source-derived data domain for imported or public-source-derived
records and a reviewer-created state domain for tester/reviewer workflow data.
Reviewer-created state must not overwrite source-derived canonical data or
original extracted values.

Minimum review status concepts:

- `not reviewed`: no reviewer has started the record in the hosted workflow.
- `in review`: a reviewer has started review and has not completed source
  checking or disposition.
- `source check needed`: a reviewer or workflow has identified that source
  traceability or field-level source context needs review.
- `source checked`: a reviewer has checked available source traceability for the
  record.
- `correction proposed`: at least one correction proposal exists and is awaiting
  a decision.
- `correction reviewed`: correction proposals for the current review context
  have been reviewed or dispositioned.
- `reviewed`: the reviewer has completed the current review pass without open
  correction decisions blocking use.
- `included in export`: the record is selected for a specific export packet.
- `excluded from export`: the record is intentionally left out of a specific
  export packet.

State requirements:

- State changes must be attributed to a reviewer and timestamp.
- State history must be auditable; a later state must not erase earlier review
  history.
- Export inclusion and exclusion must be scoped to an export packet or review
  context, not treated as a permanent fact about the source record.
- A record may have source-derived fields that are unchanged while review state
  changes many times.
- Queue filters may use review state, but exported source-derived fields must
  remain traceable to their source documents.

## Annotation and correction boundaries

Annotations and correction proposals are reviewer-created state.

- Annotations do not change raw source records.
- Annotations do not change canonical extracted fields.
- Proposed corrections do not overwrite original extracted values.
- Every correction proposal must preserve the original value, proposed value,
  source basis, reviewer, timestamp, and decision status.
- Correction workflows must remain traceable to source documents and extraction
  audit rows where available.
- Correction decision statuses must distinguish at least pending, accepted,
  rejected, and superseded decisions before any correction can influence an
  export packet.
- Accepted corrections may affect a reviewed export presentation only through an
  explicit, traceable correction layer; they must not mutate raw files or erase
  original extracted values.
- Rejected and superseded corrections must remain auditable.
- Review notes must not assert legal, facility-wide, delay, harm, abuse,
  neglect, liability, or rights-deprivation conclusions without an approved and
  documented basis outside this derived dataset.

## Hosted tester readiness requirements

A hosted tester version is not ready until it satisfies these minimum
requirements.

### Authenticated tester access

Access must be limited to authenticated testers using an approved access model.
The repository must not store secrets, tokens, private URLs, or account-specific
configuration in committed files.

ADR-0011 defines the hosted tester MVP authentication and access boundary.
Anonymous hosted tester access is not allowed; tester access must be explicitly
invited or provisioned, role-scoped, auditable where feasible, and revocable.

ADR-0014 chooses a managed standards-based OpenID Connect/OAuth 2.0 provider
class for the hosted tester MVP. Before reviewer-created state is enabled,
implementation must enforce authenticated access, role and permission checks,
project or corpus scope, disabled-account rejection, and actor identity context
needed for audit logging.

The current auth boundary scaffold implements those checks only for local/test
service seams and provider integration planning. It establishes authenticated
actor, role, permission, scope, target, account-status, and audit-context
models, and can return a bounded non-secret provider readiness plan, but it does
not authenticate browser users, validate provider tokens, store sessions,
persist role/scope assignments, register a provider, create hosted URLs, or by
itself create reviewer-created state. The narrow reviewer-
created state scaffold reuses those local/test checks for attributed placeholder
state writes, but it does not implement browser authentication, persistent
authorization storage, full review workflows, annotations, corrections,
exports, feedback, or audit persistence beyond the narrow reviewer-created
state write scaffold.

### Seeded test corpus

The tester environment must use a seeded, documented test corpus with source
traceability. The corpus must be suitable for repeatable testing and must not be
presented as complete statewide coverage or official facility conclusions.

Source-derived hosted tester records must enter the tester environment through
the controlled import/sync boundary accepted by ADR-0009, starting with
snapshot imports from validated pipeline output unless a later ADR approves a
different import mechanism.

ADR-0015 chooses PostgreSQL as the hosted tester MVP persistence store and
Alembic-managed migrations as the migration tooling direction. Future seeded
corpus implementation must preserve source-derived and reviewer-created state
separation in PostgreSQL and must use migrations that are repeatable and
reviewable before external tester use.

### Known limitations visible

Known limitations must be visible in the hosted workflow at points where testers
review records, interpret flags, prepare exports, or submit feedback.

### Accessibility expectations

The hosted workflow must meet the project accessibility requirements for
keyboard access, logical focus order, visible focus indicators, semantic
structure, screen-reader support, contrast, non-color-only status, plain
language, and accessible exports.

### Source-traceability expectations

Source URL, raw hash, connector details, retrieval timestamp, report context,
and extraction audit context where available must remain accessible from review,
correction, annotation, queue, and export workflows.

### Export restrictions and cautions

Exports must be limited to reviewed, intentionally included records for the
selected packet. Export output must preserve source traceability, original values
when corrected values are shown, correction status, relevant annotations, known
limitations, and cautious public-source language.

### Feedback collection

Tester feedback must be collected with workflow context, tester identity or
approved tester identifier, timestamp, severity or priority, and enough source
context to reproduce the issue without exposing secrets or unnecessary personal
information.

### Reset and reload process

The hosted tester environment must have a documented process for resetting
reviewer-created state and reloading the seeded corpus so repeated tests can
start from a known baseline.

ADR-0013 defines the operational reset/reload boundary: seeded source-derived
data must reload from validated pipeline output, reviewer-created state must be
preserved, archived, or explicitly cleared only through an elevated audited mode,
and reset/reload execution remains deferred until schema, API, permission,
audit persistence, reviewer-created state, broader operational metadata, and
import artifact decisions are implemented. The current local/test dry-run and
execution-plan seams support planning only and do not execute reset/reload. They
can persist a separate planning metadata record only when explicitly requested
by local/test code, and they count existing audit scaffold rows but do not
create new audit events. A narrow local/test planning metadata read route can
list or fetch those records for authorized operators/admins without executing
reset/reload or mutating operational, source-derived, reviewer-created, or audit
rows.

### Operational boundaries

ADR-0013 defines the hosted tester MVP operational boundaries for audit logging,
export generation, reset/reload, and tester data retention. Before external
tester use, implementation must map those boundaries into concrete schema, API,
permission, export, reset/reload, and retention behavior with tests for the
affected layer.

## Architecture decision prerequisites

ADR-0006 defines the hosted tester MVP architecture boundary and confirms that a
primary reviewer application layer must remain separate from Datasette.
ADR-0012 allows hosted tester MVP implementation to begin through a
scaffold-first sequence after the accepted data-domain, import/sync,
schema/migration, and authentication/access boundaries. ADR-0013 defines the
operational boundaries for audit logging, export generation, reset/reload, and
tester data retention. ADR-0014 chooses the authentication provider class and
role implementation direction. ADR-0015 chooses PostgreSQL and Alembic-managed
migrations for hosted tester MVP persistence. Before hosted tester MVP
implementation expands into external tester use, implementation PRs or
equivalent governance updates must define the concrete affected layer:

- Where review state, annotations, correction proposals, feedback, and export
  packet decisions are persisted.
- How the ADR-0008 source-derived and reviewer-created data domains are mapped
  into physical schema, migrations, API contracts, UI labels, exports, tests,
  and audit history.
- How the ADR-0009 controlled import/sync strategy is mapped into import batch
  metadata, stable source-derived identities, reset/reload behavior, and
  reviewer-created state preservation.
- How the ADR-0010 physical schema and migration strategy is mapped into
  separated schema areas or table groups, migration validation, and future
  implementation tests without weakening traceability or mixing data domains.
- How ADR-0015's PostgreSQL and Alembic migration direction is mapped from the
  current local/test scaffold wiring into concrete schema configuration,
  migration review, rollback or recovery guidance, and validation without
  committing secrets, connection strings, or deployment configuration.
- How source traceability and extraction audit context remain available to the
  hosted reviewer application.
- How authenticated tester access, audit history, reset/reload, export
  restrictions, and tester data retention are implemented without storing
  secrets in the repository.
- How ADR-0011's admin, tester reviewer, read-only tester, and
  developer/operator role boundaries are mapped into implementation without
  exposing reviewer-created state as public-source facts.
- How ADR-0014's managed OpenID Connect/OAuth 2.0 provider class, identity
  claims, actor categories, project/corpus scope, access approval, disablement,
  and access review boundaries are mapped into the implementation layer.
- Which accessibility checks are required before tester access is enabled.
- Which concrete provider instance, API framework, storage, backup/restore,
  retention automation, and deployment choices are selected for the hosted
  tester MVP layer being built.
