# ADR-0013: Define Hosted Tester MVP Operational Boundaries

## Status

Accepted

## Context

The project is moving from local scaffold validation toward a user-facing
hosted tester MVP. Recent implementation PRs established a local-only hosted
scaffold, fixture/sample source-record views, facility master sample views,
facility source coverage panels, public-source CSV profiling, and tiny
public-source fixtures. Those increments validate useful future review
patterns, but they are not the hosted tester product.

ADR-0008 separated source-derived records from reviewer-created state.
ADR-0009 required hosted source-derived records to come from controlled imports
of validated pipeline output rather than hosted live crawling. ADR-0010 defined
future physical schema separation for source-derived records, reviewer-created
state, audit events, export packet state, tester feedback, and operational/reset
metadata. ADR-0011 required authenticated, role-scoped tester access. ADR-0012
allowed scaffold-first implementation while keeping business workflows,
schemas, authentication implementation, imports, exports, audit logging,
reset/reload, and reviewer-created state persistence deferred.

The next product-enabling decision is the minimum operational boundary needed
before implementation branches can move toward authenticated testers using a
seeded, source-traceable corpus to search facilities, review complaint and
source records, inspect source traceability, add annotations and corrections,
prepare export packets, reset or reload test data, and submit feedback.

This ADR defines planning boundaries for audit logging, export generation,
reset/reload, and tester data retention. It does not implement those features.

## Decision

The hosted tester MVP must treat audit logging, export packet generation,
reset/reload, and tester data retention as operational boundaries that protect
the source-derived and reviewer-created state separation.

After this ADR, implementation work may proceed toward concrete provider,
database, schema, API, import/reset, and first authenticated tester workflow
branches, provided each branch stays inside the accepted boundaries below and
adds validation for the layer it implements.

This ADR clears the product path; it is not a generic policy document and does
not choose final technology, schemas, APIs, commands, retention durations, or
hosting providers.

## Audit Logging Boundary

Before testers can use reviewer-created state, the product must have an audit
logging design for the actions that can change review context, export context,
tester data, or operational state.

Actor identity must distinguish at least these categories:

- Tester: an authenticated tester account acting within an assigned corpus,
  project, role, or permission scope.
- Operator: an authorized administrator or developer/operator performing
  import, reload, reset, troubleshooting, or elevated tester-MVP operations.
- System: an approved process identity performing scheduled, scripted, or
  automated work.

Audit timestamps must use a generated ISO datetime with timezone. Future
implementation must record when the audited action occurred and, when useful,
when it was recorded if those differ. Audit timestamps must not replace source
retrieval timestamps or extraction audit timestamps.

The following reviewer-created actions must eventually be auditable before the
affected feature is available to testers:

- Review status changes.
- Queue or assignment changes where implemented.
- Annotation creation, update, deletion, or archival.
- Field-level note and source verification note creation, update, deletion, or
  archival.
- Proposed correction creation, update, withdrawal, supersession, and decision.
- Tester feedback submission, triage, status changes, and linkage to workflow
  context.

The following source-derived operational events must eventually be auditable
before the affected operation is available in the hosted tester environment:

- Import batch creation or load from validated pipeline output.
- Import validation result recording.
- Seeded corpus reload.
- Reset operation request, approval where applicable, execution, failure, or
  rollback/recovery note.
- Comparison against retained SQLite/Datasette validation output where
  applicable.

The following export packet actions must eventually be auditable before testers
can prepare review handoff outputs:

- Export packet creation, update, rename, archival, or deletion.
- Item inclusion, exclusion, or removal from a packet.
- Export generation, regeneration, finalization, download, or delivery event
  where implementation can observe it.
- Export-blocking condition acknowledgement, such as unresolved corrections,
  missing source traceability, or known limitation review.

Audit events must reference the relevant project, corpus, source-derived record,
reviewer-created record, export packet, import batch, reset event, or operational
scope when available. Audit events must preserve enough context to understand
what changed without storing secrets or unnecessary sensitive narrative content.

Audit events must not overwrite source-derived records, raw source files,
source document metadata, extraction audit records, source URLs, raw hashes,
connector metadata, retrieval timestamps, original extracted values, or prior
audit events.

Audit persistence implementation remains deferred until schema and API work
define the audit table or event store, stable identifiers, permissions,
retention behavior, and validation tests.

Current note: a later local/test scaffold PR added only a narrow audit event
table and service for successful reviewer-created state scaffold writes. That
scaffold validates the first audit persistence boundary but does not implement
full audit policy coverage, audit UI, audit export, retention automation, or
audit coverage for reset/reload, exports, feedback, annotations, corrections,
provider login, role changes, or operational actions.

## Export Generation Boundary

An export packet is reviewer-created/export workflow state. It is not a
source-derived fact.

Including or excluding a record is scoped to a specific export packet, review
project, or review corpus. Inclusion or exclusion must not become a permanent
fact about a facility, source document, complaint, allegation, event, or public
source.

Before testers can prepare review handoff outputs, export generation must
preserve source traceability for each exported source-derived record, including
where available:

- Source URL.
- Raw SHA-256 hash.
- Raw path or artifact reference.
- Connector name and version.
- Retrieval timestamp.
- Source document identity.
- Report index or document type.
- Extraction audit context relevant to exported fields.
- Import batch or seeded corpus context where applicable.

When corrected values are shown in an export, the export must preserve the
original extracted value, the correction decision status, the reviewer-created
correction context, and the source basis or reviewer rationale where available.
Exports must not hide the original extracted value behind an accepted correction
unless a later approved correction application policy explicitly allows a
different presentation and preserves auditability.

Exports should include relevant annotation, field-level note, source
verification note, and tester feedback context only when the export packet scope
and permissions allow it. Export labels must distinguish source-derived fields
from reviewer-created annotations, corrections, feedback, and packet decisions.

CSV or other export outputs intended for review handoff must meet the project
accessibility requirements: clear headers, plain-language labels, no
formatting-only meaning, no color-only status, stable column order where
practical, and accompanying limitations or data dictionary context.

Exports must include cautious public-source language. They must not imply
public-source completeness, official facility status, legal conclusions,
facility-wide conclusions, verified delay, harm, abuse, neglect, liability, or
rights deprivation unless a later approved review process establishes and
documents a basis outside this derived dataset.

Export builder implementation remains deferred until schema, API, permission,
storage, generation format, and accessibility validation work define the
concrete export packet model and output behavior.

## Reset and Reload Boundary

The hosted tester MVP must support repeatable seeded corpus testing without
mixing source-derived imported records and reviewer-created state.

Seeded tester corpus reload must load source-derived data only from validated
pipeline output or an approved export artifact produced by the existing
pipeline. Reload must not use hosted live crawling, hosted connector execution,
automatic public-source expansion, ignored raw CSVs, generated profiling
outputs, or ad hoc manual data entry unless a later ADR explicitly approves a
different mechanism.

Reloaded source-derived records must preserve stable source-derived identities,
source traceability, import batch metadata, raw hash context, connector
metadata, retrieval timestamps, extraction audit context, original extracted
values, warnings where available, and cautious public-source limitations.

Reset/reload must offer explicit reviewer-created state handling modes before
external tester use. The implementation may choose one or more of these modes
after schema/API decisions:

- Preserve reviewer-created state and relink it to matching stable
  source-derived identities.
- Archive reviewer-created state while reloading the seeded source-derived
  corpus.
- Clear reviewer-created state only through an explicit, elevated, audited test
  reset mode with documented warning and recovery expectations.

Reset/reload must not silently delete annotations, proposed corrections,
correction decisions, review state, tester feedback, export packets, audit
events, or operational metadata. If a reset mode removes or archives
reviewer-created state, the operation must record scope, actor or process
identity, timestamp, import batch or artifact, counts affected where available,
what was preserved, what was archived or cleared, and any recovery limitation.

Where applicable, reload validation should compare the hosted seeded corpus
against retained SQLite/Datasette validation output or a validated pipeline
artifact. Comparison should check counts, stable identifiers, source document
coverage, traceability fields, validation status, warnings, and changed values
at the level supported by the implemented artifact.

Reset/reload command or API implementation remains deferred until database,
schema, migration, API, permission, import artifact, and operational recovery
decisions are implemented and tested.

## Tester Data Retention Boundary

This ADR does not set final retention durations. Before external tester use,
the project must decide retention expectations for each data category below,
including normal retention, deletion or archival triggers, reset behavior,
export behavior, backup/restore expectations, and any tester notice required.

Retention categories must include:

- Source-derived imported records.
- Raw/source traceability references, including source URLs, raw hashes, raw
  paths or artifact references, connector metadata, retrieval timestamps, and
  extraction audit context.
- Reviewer-created annotations, field-level notes, and source verification
  notes.
- Proposed corrections and correction decisions.
- Review state, queue state, assignment state, and review status history.
- Tester feedback and feedback triage metadata.
- Audit events.
- Export packets, export packet items, generated export artifacts, and export
  delivery/download metadata where available.
- Import batches, reset/reload metadata, operational validation results,
  recovery notes, and comparison metadata.

Retention decisions must preserve source traceability and auditability while
avoiding unnecessary exposure of public narrative content, reviewer notes,
tester feedback, secrets, account details, private URLs, or machine-specific
configuration.

Retention behavior remains deferred until provider, database, schema, API,
storage, backup/restore, account lifecycle, and production operations decisions
define how each category is persisted, archived, deleted, exported, or restored.

## What Remains Blocked

The following implementation remains blocked until provider, database, schema,
API, permission, and storage decisions define the concrete layer being built:

- Authentication and authorization implementation.
- User, role, permission, session, and invitation persistence.
- Hosted database tables, migrations, indexes, constraints, or ORM models.
- API routes for source-derived records, reviewer-created state, audit events,
  exports, reset/reload, feedback, or imports.
- Reviewer-created state persistence.
- Audit table or event-store implementation.
- Export builder implementation.
- Reset/reload command, API, or destructive operation implementation.
- Retention automation, archival jobs, deletion workflows, or backup/restore
  implementation.
- Source import implementation or import artifact format.
- Live source loading, hosted connector execution, or hosted crawling.
- Deployment, QNAP, Azure, AWS, public URL, DNS, app registration, or cloud
  database behavior.

No schema changes are approved by this ADR.

## Implementation path unlocked by this ADR

This ADR clears the remaining operational decision blocker for the next
product-moving implementation path. After this ADR, the next decisions or
branches should be:

1. Provider-specific authentication and authorization implementation decision.
2. Concrete database product and migration tooling decision.
3. Minimal hosted schema/API scaffold for seeded source-derived records and
   reviewer-created state.
4. Seeded corpus import/reset implementation.
5. First authenticated tester workflow.

Each implementation branch must identify the accepted ADR boundary it uses,
state what remains deferred, add tests for the implemented behavior, preserve
source-derived versus reviewer-created state separation, preserve source
traceability, meet accessibility and security/privacy expectations, and keep
cautious public-source language visible where testers interpret records or
exports.

## Consequences

Benefits:

- The project can move from local scaffold validation toward the user-facing
  hosted tester MVP without reopening broad operational questions on every PR.
- Audit, export, reset/reload, and retention expectations are defined enough to
  guide database, API, import/reset, and first tester workflow implementation.
- Source-derived records remain protected from reviewer-created annotations,
  corrections, export packet decisions, feedback, and operational reset actions.
- Export and reset/reload behavior can be designed around source traceability,
  accessibility, cautious language, and tester safety from the start.

Tradeoffs and risks:

- Implementation is still blocked on concrete provider, database, schema, API,
  storage, and permission decisions.
- Retention durations are not yet chosen, so external tester use still requires
  a concrete retention plan.
- Export and reset/reload behavior may add implementation complexity, but that
  complexity is necessary to avoid unsafe reviewer-state deletion or confusing
  source-derived facts with reviewer decisions.

## Work Not Approved By This ADR

This ADR does not approve implementation of:

- Application code.
- Hosted UI changes.
- Database tables.
- Schemas.
- Migrations.
- API routes.
- Authentication or authorization.
- Reviewer-state persistence.
- Audit tables or event stores.
- Export builder logic.
- Reset/reload commands or APIs.
- Retention automation.
- Source import.
- Live source loading.
- Connectors.
- Deployment.
- QNAP, Azure, AWS, or public URL behavior.

No source-derived canonical fields are added or changed.