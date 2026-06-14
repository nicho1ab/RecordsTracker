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
outputs, deployment, QNAP, Azure, AWS, or public URL behavior.

Minimal PostgreSQL/Alembic project wiring now exists for local/test validation:
dependency declarations, no-secret database URL validation, an Alembic script
location, one domain migration for controlled seeded corpus import batch
metadata and source-derived record staging, a local validated JSON artifact
importer, a local/test database-backed read service over staged source-derived
records, a local/test auth boundary scaffold with actor, role, scope, target,
and audit-context models, a narrow local/test authenticated source-derived
HTTP/API read route seam, a narrow local/test authenticated read-only reviewer
workflow shell over the route seam, a local/test authenticated reset/reload
dry-run route seam, and scaffold/API boundary descriptors. The dry-run reports
what a future seeded corpus reset/reload would affect, including existing import
batch metadata, source-derived record counts by entity, future reviewer-created
state handling modes, required permissions, validation requirements, audit
requirements, and deferred destructive actions, without mutating data. This path does
not implement real login flow, provider registration, tokens, cookies, auth
middleware, production API framework behavior, run migrations against a local
database during scaffold tests, load live public data, run connector execution,
automate production imports, execute reset/reload, archive or clear reviewer-
created state, persist audit events, create stateful queues, or persist reviewer-created state.

The next safe hosted-view increment should remain similarly narrow and
fixture-backed, preserving fixture/sample labels, read-only behavior,
source-derived versus reviewer-created state separation, semantic structure,
accessibility validation, and the no-real-login, no-reviewer-created-state,
no-deployment boundary.

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
service seams. It establishes authenticated actor, role, permission, scope,
target, account-status, and audit-context models, but it does not authenticate
browser users, validate provider tokens, store sessions, persist role/scope
assignments, or create reviewer-created state.

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
audit persistence, reviewer-created state, operational metadata, and import
artifact decisions are implemented. The current local/test dry-run seam supports
planning only and does not execute reset/reload or persist operational state.

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
