# ADR-0006: Define Hosted Tester MVP Architecture Boundaries

## Status

Accepted

## Context

The project is in production-discovery for a source-traceable public-record
review solution. The initial proof of concept proved ingestion, deterministic
extraction, raw source preservation, source traceability, local review, and
source-traceable exports.

ADR-0005 established that Datasette is no longer the governed primary future
reviewer experience. The future hosted tester MVP needs persistent navigation,
guided queues, saved reviewer state, annotations, correction workflows,
contextual help, source-traceable exports, tester feedback, accessibility, and
fewer-click review paths. These needs require a primary reviewer application
layer separate from Datasette.

This ADR defines what must be separated, preserved, and decided before building
the hosted tester MVP. It does not select a production stack, add dependencies,
change schemas, alter extraction behavior, add connectors, or implement hosted
application behavior.

## Decision

The hosted tester MVP requires a primary reviewer application layer separate from Datasette.

Datasette remains retained during and after the transition for:

- Validation of ingestion, extraction, SQLite views, and source traceability.
- Inspection of source-derived records and extraction audit context.
- Debugging connector, extraction, normalization, storage, and export issues.
- Local exploration by developers and local reviewers.
- Export support over the retained SQLite validation dataset.
- Comparison against hosted-application behavior during the transition, so the
  hosted tester MVP can be checked against known local review and export paths.

The hosted tester MVP architecture must separate source-derived data from
reviewer-created state. Source-derived canonical data remains governed by
`DATA_CONTRACT.md`, the JSON schemas, connector contracts, raw source
preservation, and fixture-backed regression expectations. Reviewer-created state
belongs in the future application/review layer and must not overwrite
source-derived canonical data.

## Source-derived data boundary

The source-derived boundary includes records and evidence produced by the
ingestion and extraction pipeline:

- Facility records.
- Source document records.
- Complaint records.
- Allegation records.
- Event records.
- Extraction audit records.
- Raw source files.
- Source URL.
- Raw hash.
- Connector metadata, including connector name and version.
- Retrieval timestamp.
- Report index where available.

The hosted tester MVP may display, filter, cite, export, and link to these
values, but it must not redefine them as reviewer-created state or mutate them
through review workflows.

## Reviewer-created state boundary

The reviewer-created boundary includes application state created by testers,
reviewers, or hosted workflow operations:

- Review status.
- Queue membership.
- Assignment if applicable.
- Annotations.
- Field-level notes.
- Source verification notes.
- Proposed corrections.
- Correction decisions.
- Tester feedback.
- Export packet selections.
- Audit events.

Reviewer-created state must remain distinguishable from source-derived records
in storage, API contracts, UI labels, exports, documentation, tests, and audit
history. It must not overwrite source-derived canonical data, raw source files,
source document records, extraction audit records, source URLs, raw hashes,
connector metadata, retrieval timestamps, or original extracted values.

## Correction boundary

Proposed corrections are reviewer-created state, not official public-source
facts. A proposed correction may support review and export preparation, but it
must not erase the original extracted value.

Every proposed correction must preserve:

- Original extracted value.
- Proposed value.
- Source basis.
- Reviewer identity or tester identity where available.
- Timestamp.
- Decision status.
- Link back to source document and extraction audit where available.

Correction decisions must remain auditable. Accepted corrections may influence a
reviewed export presentation only through an explicit traceable correction
layer. Rejected or superseded corrections must remain available for audit where
the retention policy requires them.

## Hosted tester MVP boundary

The hosted tester MVP boundary includes only the minimum capabilities needed to
test the future primary reviewer workflow safely:

- Authenticated tester access.
- Seeded test corpus.
- Reset and reload process.
- Known limitations visible in the UI.
- Source traceability visible in review screens and exports.
- Accessibility expectations for keyboard access, focus order, screen reader
  support, contrast, non-color-only status, plain language, and accessible
  exports.
- Export caution language that identifies outputs as derived review aids, not
  official public-source records or conclusions.
- Feedback capture tied to workflow context, source context, accessibility
  issues, correction needs, export concerns, or tester confusion.
- Auditability appropriate for pilot testing, including state changes,
  correction proposals, correction decisions, export packet selections, tester
  feedback, reset/reload events, and access-relevant events at the level later
  approved by security and privacy governance.

The hosted tester MVP must not make unsupported legal, facility-wide,
public-source completeness, delay, harm, abuse, neglect, liability, or
rights-deprivation conclusions.

## Future stack decision criteria

Future stack ADRs must compare options against these criteria before selecting
or implementing a production direction:

- Source traceability.
- Separation of source-derived data and reviewer-created state.
- Accessibility.
- Authentication and role support.
- Auditability.
- Correction workflow support.
- Export generation.
- Reset and reload support.
- Local development simplicity.
- Deployment simplicity.
- Cost.
- Long-term maintainability.
- Testability.
- Migration path from SQLite and Datasette.

## Deferred decisions

This ADR explicitly defers these decisions to future ADRs or equivalent
governance updates:

- Frontend framework.
- API framework.
- Database choice.
- Authentication provider.
- Hosting platform.
- Background job approach.
- Import or sync approach from the existing extraction pipeline.
- Export generation implementation.
- Audit log implementation.
- Tester data retention policy.

## Not yet approved for build

The following work should not be built until the relevant future ADRs are
complete:

- Production app scaffold.
- Authentication implementation.
- Hosted database schema.
- Correction workflow implementation.
- Queue implementation.
- Annotation implementation.
- Hosted export builder.

Prototype or spike work may be proposed separately only if it is clearly
isolated, reversible, documented as non-production, and does not create a casual
or implicit stack decision.

## Consequences

- Hosted tester MVP planning can proceed with a clear separation between
  source-derived data and reviewer-created state.
- Datasette remains part of the validation, inspection, debugging, local
  exploration, export-support, and transition-comparison toolkit.
- The project must make stack, persistence, authentication, hosting, sync,
  export, audit log, and retention decisions in later ADRs before build work.
- Future implementation work must preserve source traceability, raw source
  preservation, deterministic extraction expectations, fixture-backed regression
  expectations, accessibility, security, privacy, and cautious public-source
  language.