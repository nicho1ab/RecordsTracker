# ADR-0008: Define Hosted Tester MVP Data and Review-State Model Boundary

## Status

Accepted

## Context

The project is in production-discovery for a source-traceable public-record
review solution. The proof of concept has proven Python ingestion and
extraction, raw source preservation, source traceability, local SQLite storage,
retained Datasette validation and inspection workflows, fixture-backed
regression coverage, and source-traceable exports.

ADR-0005 established that Datasette is retained as a validation, inspection,
debugging, local exploration, and export-support layer, not the governed primary
future reviewer UX. ADR-0006 established the hosted tester MVP architecture
boundary and requires a primary reviewer application layer separate from
Datasette. ADR-0007 recommends a hybrid transition: preserve the existing Python
ingestion/extraction engine and local SQLite/Datasette validation layer while
planning a hosted relational reviewer-state boundary and hosted reviewer
application/API.

The next production-discovery decision is the conceptual data and review-state
boundary for the hosted tester MVP. This ADR defines that boundary only. It does
not implement schemas, migrations, queues, annotations, corrections, hosted
exports, authentication, app scaffolding, or extraction behavior.

Current note: ADR-0012 later approved scaffold-first sequencing, and later local
implementation PRs added only the local scaffold, setup checks, read-only sample
source-record shell, and semantic/accessibility validation. This ADR still does
not approve data schemas, migrations, reviewer-created state persistence,
queues, annotations, corrections, exports, authentication, or extraction
behavior.

## Decision

The hosted tester MVP must use two distinct data domains:

- Source-derived data domain.
- Reviewer-created state domain.

The source-derived data domain contains imported or public-source-derived
records and evidence. It must preserve the existing source traceability chain,
raw source preservation, deterministic extraction expectations, extraction audit
context, and data-contract discipline.

The reviewer-created state domain contains tester and reviewer workflow data. It
must never overwrite source-derived canonical data, raw source files, source
document records, extraction audit records, source URLs, raw hashes, connector
metadata, retrieval timestamps, or original extracted values.

The two domains may be related by stable identifiers and traceable links, but
they must remain distinguishable in future storage models, API contracts, UI
labels, exports, documentation, tests, and audit history.

## Source-Derived Data Domain

The source-derived domain contains records and evidence produced from public
source ingestion and deterministic extraction. These records must remain
traceable and protected:

- Facility.
- Source document.
- Complaint.
- Allegation.
- Event.
- Extraction audit.
- Raw source files.
- Source URL.
- Raw SHA-256 hash.
- Raw path when available.
- Connector name.
- Connector version.
- Retrieval timestamp.
- Report index where available.
- Original extracted values.
- Extraction confidence where available.
- Extraction warning where available.

Future hosted review workflows may display, filter, cite, queue, annotate, link
to, or export source-derived records. Those workflows must not redefine
source-derived records as reviewer-created state and must not mutate them
through review actions.

## Reviewer-Created State Domain

The reviewer-created state domain contains tester, reviewer, and workflow data
created by the hosted reviewer application or approved review processes. The
future hosted MVP must support these concepts:

- Review project or review corpus.
- Review item.
- Review status.
- Queue membership.
- Assignment if applicable.
- Annotation.
- Field-level note.
- Source verification note.
- Proposed correction.
- Correction decision.
- Tester feedback.
- Export packet.
- Export packet item.
- Audit event.

Reviewer-created state must remain clearly marked as reviewer or application
state. It may reference source-derived records, extraction audit fields, review
items, or export packet items, but it must not become a new canonical
source-derived field without a later data-contract and schema decision.

## Review Statuses

The hosted tester MVP must support at least these review status concepts before
external tester use. This ADR does not implement an enum or schema:

- Not reviewed.
- In review.
- Source check needed.
- Source checked.
- Correction proposed.
- Correction reviewed.
- Reviewed.
- Included in export.
- Excluded from export.

These statuses are reviewer workflow states. They are not public-source facts,
legal conclusions, facility-wide conclusions, source-completeness assertions, or
findings about delay, harm, abuse, neglect, liability, or rights deprivation.
Export inclusion and exclusion are scoped to a review project, review corpus, or
export packet context rather than treated as permanent facts about the source
record.

## Annotation Boundaries

Annotations are reviewer-created notes. They may be linked to a facility,
complaint, allegation, event, source document, extraction audit field, export
packet item, or review item.

Annotations must not change source-derived data, raw source files, canonical
extracted fields, extraction audit records, source document metadata, source
URLs, raw hashes, connector metadata, retrieval timestamps, or original
extracted values.

Annotations must not be treated as official public-source findings. Annotation
language must support cautious attorney-review wording and must avoid implying
unsupported legal, facility-wide, public-source completeness, delay, harm,
abuse, neglect, liability, or rights-deprivation conclusions.

## Correction Boundaries

Proposed corrections are reviewer-created state. Every proposed correction must
preserve:

- Original extracted value.
- Proposed replacement value.
- Source basis or reviewer rationale.
- Reviewer or tester identity where available.
- Timestamp.
- Decision status.

Proposed corrections must remain traceable to the relevant source-derived
record, source document, and extraction audit context where available. A
correction decision may approve, reject, supersede, or otherwise disposition a
proposal only as reviewer-created review state.

Approved corrections must not overwrite raw source files or canonical
source-derived records. They may influence a reviewed export presentation only
through an explicit, traceable correction layer unless a later ADR explicitly
approves a correction application strategy.

Original extracted values must remain visible and auditable when proposed or
approved corrections exist.

## Export Packet Boundaries

Export packet membership is reviewer-created state. Export packet items may
reference source-derived records and reviewer-created annotations or correction
decisions, but membership itself is not a public-source fact.

Exports must preserve source traceability, including source URLs, raw hashes,
connector metadata, retrieval timestamps, report context where available, and
extraction audit context where relevant. Exports must distinguish
source-derived fields from reviewer-created notes, annotations, proposed
corrections, correction decisions, and export packet decisions.

Exports must retain caution language. They must not imply legal conclusions,
facility-wide conclusions, public-source completeness, verified delay, harm,
abuse, neglect, liability, or rights deprivation unless a later approved review
process establishes and documents a basis outside this derived dataset.

## Audit Events

Hosted tester MVP planning must make these activities auditable, without
designing the final audit schema in this ADR:

- Review status changes.
- Annotation creation and update.
- Proposed correction creation.
- Correction decision.
- Export packet creation and update.
- Feedback submission.
- Import, reset, and reload events if applicable.

Auditability must preserve who performed an action where available, when it
occurred, the relevant review context, the linked source-derived record or
review item, and enough detail to understand what changed without erasing prior
history.

## Import and Sync Implications

Source-derived records may be imported from the existing Python pipeline into a
hosted relational store or accessed through a future API/import process. Any
future import/sync mechanism must preserve:

- Source document identity.
- Raw hashes.
- Connector metadata.
- Retrieval timestamps.
- Extraction audit context.
- Original extracted values.
- Stable links back to retained raw or public-source evidence.

The concrete import/sync mechanism is deferred to a future ADR. That ADR must
address drift risk between local SQLite/Datasette validation output and hosted
review data, including how hosted records are refreshed, reset, reloaded, or
compared against retained local validation data.

## Consequences

Benefits:

- Clear separation between public-source-derived data and reviewer-created work.
- Support for hosted queues, annotations, corrections, exports, tester feedback,
  and auditability without weakening source traceability.
- Preservation of original extracted values and raw evidence while allowing
  reviewed export presentations to reference correction decisions through a
  traceable layer.
- A concrete conceptual model for future schema, migration, API, UI, export,
  and audit ADRs.

Tradeoffs and risks:

- Import/sync drift may occur if hosted source-derived records are not compared
  against the retained local validation dataset.
- Source-derived records may be duplicated between local validation storage and
  hosted review storage.
- Correction state may be misunderstood as official unless UI labels, export
  language, documentation, and tests keep the distinction clear.
- Future schema design needs careful migration planning because review state,
  correction decisions, export packet membership, and audit events will evolve
  during tester use.

## Deferred Decisions

This ADR explicitly defers:

- Physical database schema.
- Database product.
- ORM or migration tooling.
- API framework.
- Frontend framework.
- Authentication provider.
- Role model.
- Import/sync implementation.
- Export implementation.
- Audit log implementation.
- Correction application policy.
- Tester data retention policy.

## Work Not Approved By This ADR

No schema changes are approved by this ADR.

This ADR does not approve:

- App scaffold.
- Hosted database schema implementation.
- Migrations.
- Authentication.
- Queues.
- Annotations.
- Corrections.
- Hosted exports.
- Production deployment.
- New canonical source-derived fields.
- Changes to extraction behavior.

Future implementation branches must wait for the relevant schema, import/sync,
authentication/access, export, audit, retention, and scaffold decisions, and
must include focused tests for the implemented boundary.