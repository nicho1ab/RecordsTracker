# ADR-0010: Define Hosted Tester MVP Schema and Migration Strategy

## Status

Accepted

## Context

ADR-0007 recommends a hybrid transition architecture for the hosted tester MVP:
preserve the existing Python ingestion and extraction pipeline, retain SQLite
and Datasette for validation and transition comparison, and plan a hosted
relational reviewer-state boundary with a future hosted reviewer
application/API.

ADR-0008 separates source-derived imported records from reviewer-created state.
Source-derived records carry public-source-derived values, raw source
traceability, extraction audit context, and data-contract discipline.
Reviewer-created state carries review progress, annotations, proposed
corrections, tester feedback, export packet decisions, and audit events.

ADR-0009 recommends controlled snapshot imports from validated pipeline output
for the tester MVP. It keeps the Python pipeline as the source-derived data
producer, requires import batch metadata and stable source-derived identity,
and avoids hosted live crawling or hosted connector execution unless a later ADR
approves that behavior.

The next decision is how future physical schemas and migrations should be
organized without weakening traceability, raw source preservation,
deterministic extraction expectations, fixture-backed regression expectations,
reviewer-state safety, accessibility, security/privacy, or cautious
public-source language. This ADR defines the schema and migration strategy
boundary only. It does not create actual schema files, migration files,
database code, import code, reset/reload code, or app scaffold work.

Current note: ADR-0012 later approved scaffold-first sequencing, and later local
implementation PRs added only the local scaffold, setup checks, read-only sample
source-record shell, and semantic/accessibility validation. This ADR still does
not approve schemas, migrations, database creation, import code, reset/reload
code, or reviewer-created state persistence.

## Decision

Future hosted schema work must organize persisted data into separate physical
schema areas or clearly separated table groups for these concerns:

- Import and batch metadata.
- Source-derived imported records.
- Reviewer-created state.
- Audit events.
- Export packet state.
- Tester feedback.
- Operational and reset/reload metadata.

The physical model must preserve the ADR-0008 separation between
source-derived data and reviewer-created state. Reviewer-created state may link
to source-derived records through stable identities, but it must not be stored
inside source-derived canonical records or treated as public-source facts.

Future schema work should use a hybrid source-derived strategy for the tester
MVP: stable current source-derived identities for reviewer links, import batch
membership for every imported record, and enough import/change history to detect
changed extracted values across imports. Detailed append-only historical
versioning is deferred to the concrete schema design, but the physical model
must not hide source-derived changes between imports.

This ADR does not choose a database product, migration tool, ORM, table names,
column names, indexes, constraints, API framework, hosting platform, or import
artifact format.

## Source-Derived Physical Boundary

Future schema and migration work for imported source-derived records must
preserve these concepts:

- Stable source-derived identity.
- Facility identity.
- Source document identity.
- Complaint identity.
- Allegation identity.
- Event identity.
- Extraction audit identity.
- Source URL.
- Raw SHA-256 hash.
- Raw path when available.
- Connector name.
- Connector version.
- Retrieval timestamp.
- Report index where available.
- Original extracted values.
- Extraction confidence where available.
- Extraction warnings where available.
- Import batch linkage.

Source-derived physical areas or table groups must remain governed by
`DATA_CONTRACT.md`, source connector rules, raw source preservation, and
fixture-backed extraction expectations. Future hosted review workflows may read,
filter, link to, annotate, cite, or export source-derived records, but review
workflows must not mutate source-derived canonical values or erase original
extracted values.

Source-derived tables may include implementation-specific fields needed for
hosted import mechanics only after a later schema PR follows the normal schema,
documentation, migration, and test path. Those fields must not become new
canonical source-derived fields without an approved data-contract change.

## Reviewer-Created Physical Boundary

Future schema work must organize reviewer-created state into clearly separated
table groups for these concepts:

- Review project or corpus.
- Review item.
- Review status history.
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

Reviewer-created state must link to source-derived records through stable
source-derived identities or approved review-item references. It must not
overwrite source-derived canonical data, raw source files, source document
records, extraction audit records, source URLs, raw hashes, connector metadata,
retrieval timestamps, or original extracted values.

Proposed corrections and correction decisions remain reviewer-created state.
They may influence a reviewed export presentation only through an explicit,
traceable correction layer approved by later implementation work. They must not
become official public-source facts or replace the imported source-derived
record.

## Import Batch and Versioning Boundary

Future schema work must support import batches that record at least:

- Import batch ID.
- Import timestamp.
- Imported by or process identity where available.
- Source pipeline version or commit where available.
- Source database or export artifact identity.
- Record counts by entity.
- Source document count.
- Raw hash validation status.
- Validation status.
- Warnings and errors.
- Reset/reload relationship where applicable.

For the tester MVP, imported source-derived records should use a hybrid
current-state plus import-batch-history strategy:

- Use stable source-derived identity for current reviewer links.
- Record import batch membership for imported records.
- Make changed source-derived values detectable across imports.
- Avoid overwriting reviewer-created state during normal imports.
- Defer detailed historical versioning implementation until concrete schema
  design.

This strategy allows review items, annotations, proposed corrections, feedback,
and export packet items to link to stable source-derived identities while still
leaving room for later implementation to record changed extracted values,
superseded imports, or import comparison results.

Future schema work must not rely on transient row order, display labels, file
order, upload order, or manual CSV position as the identity basis for hosted
reviewer links.

## Migration Strategy Boundary

Future migration work must follow these principles:

- Migrations must be repeatable in local and test environments.
- Migrations must preserve data-domain separation.
- Migrations must never overwrite raw source evidence.
- Migrations must include rollback or recovery guidance appropriate to the
  tester MVP.
- Migrations that affect reviewer-created state require explicit test coverage.
- Migrations that affect source-derived imported records require import/reload
  validation.
- Migrations must be documented in changelog or release notes when they are
  user-facing or operationally meaningful.

Migration PRs must distinguish structural changes from data loads, imports,
reset/reload operations, and reviewer-created state updates. A migration should
not silently perform a destructive reset or rewrite reviewer-created state.

## Reset and Reload Implications

Future schema and migration work must support tester reset/reload behavior that
distinguishes source-derived data from reviewer-created state.

Normal re-import must not silently delete reviewer-created state. Review status
history, annotations, field-level notes, source verification notes, proposed
corrections, correction decisions, tester feedback, export packet state, and
audit events should remain linked when stable source-derived identity matches.

Destructive reset must be explicit, documented, and auditable. A reset operation
that removes reviewer-created state or seeded tester data must identify the
scope, actor or process identity where available, timestamp, import batch or
artifact relationship, record counts affected, and recovery or rollback
expectations appropriate to the tester MVP.

Seeded tester data reload must be reproducible from a validated import artifact.
Reload behavior must preserve source traceability, raw source references,
import batch history, and public-source caution language. Reloaded data must not
be presented as complete statewide coverage, official public-source truth, or a
legal or facility-wide conclusion.

## Testing and Validation Implications

Future schema and migration implementation PRs must include tests for the level
of behavior they implement, including:

- Migration creation and application.
- Idempotent imports or controlled duplicate handling.
- Stable source-derived identity.
- Reviewer-state preservation across imports.
- Correction state not overwriting source-derived values.
- Export packet membership preservation or audited reset behavior.
- Audit event creation for significant state changes.
- Source traceability fields present after import.
- Accessibility and user-facing caution language where schema changes affect
  review or export behavior.

Implementation PRs that affect source-derived imported records must include
import/reload validation. Implementation PRs that affect reviewer-created state
must include preservation and auditability validation. Implementation PRs that
change user-facing review or export behavior must include documentation and
accessibility validation appropriate to the changed surface.

## Options Considered

Each option was evaluated against traceability, simplicity, tester MVP speed,
drift risk, reviewer-state safety, correction workflow clarity, export
reliability, migration complexity, and future production readiness.

| Option | Evaluation |
|---|---|
| One combined hosted schema | Simple to start and fast for a small prototype, but weak for data-domain separation. Traceability can be preserved only by discipline in every table and query. Drift and reviewer-state safety risks rise because source-derived fields, corrections, annotations, feedback, and export state can become blurred. Correction workflow clarity and export reliability are weaker because reviewer-created values may look too much like source facts. Migration complexity looks low at first but grows when later separation is needed. Poor fit for production readiness. |
| Separate schemas or namespaces by data domain | Strong fit for ADR-0008 because source-derived records, reviewer-created state, imports, audit, exports, feedback, and operations can be organized with explicit boundaries. Traceability and reviewer-state safety are strong if relationships use stable identities. Tester MVP speed remains reasonable because the separation can be implemented as schema namespaces, table prefixes, modules, or table groups depending on the later database choice. Migration complexity is moderate, and future production readiness is strong. |
| Separate databases for source-derived and reviewer-created state | Strong physical isolation and reviewer-state safety. Traceability can be strong if cross-database links are stable and validated. However, tester MVP speed is lower, export reliability is harder because joined review packets need records from multiple stores, and migration/backup/reset complexity increases. Drift risk can be higher if synchronization between databases is not carefully designed. Better suited to a later production operations decision than the tester MVP boundary. |
| Snapshot-only source-derived tables | Simple and fast for the tester MVP. Works well with ADR-0009 snapshot imports and seeded corpus reloads. Traceability is strong if every row links to an import batch and source evidence. Risk: insufficient versioning could hide changed extracted values between imports unless comparison results or prior values are recorded elsewhere. Reviewer-state safety is good if stable identities are preserved, but future production readiness is limited without a change-detection path. |
| Append-only source-derived version tables | Strong auditability and change detection across imports. Traceability and export reliability can be excellent because each imported value can be tied to a version and batch. Tradeoff: higher migration complexity, more relationships, more query complexity for reviewer workflows, and slower tester MVP delivery. Overly complex versioning could delay the MVP before the team has implementation evidence. |
| Hybrid current-state plus import-batch history | Best balance for the tester MVP. Stable current identities support reviewer links, queues, annotations, corrections, feedback, and export packet state. Import batch linkage and change-detection requirements preserve traceability and reduce drift risk. Simpler than full append-only versioning while avoiding the blind spots of snapshot-only tables. Migration complexity is moderate, correction workflow clarity is strong, export reliability is strong if current values and changed imports are auditable, and future production readiness remains open. |

## Consequences

Benefits:

- Clear physical separation reinforces ADR-0008's source-derived and
  reviewer-created data-domain boundary.
- Import batch linkage supports ADR-0009's controlled snapshot import strategy.
- Tester reset/reload can be made safer because source-derived seeded data,
  reviewer-created state, audit events, feedback, and export state have clear
  boundaries.
- Future schema PRs have a concrete checklist for preserving source
  traceability, reviewer-state safety, correction clarity, and export caution
  language.

Tradeoffs and risks:

- The hosted tester MVP will have more tables and relationships than a simple
  proof-of-concept database.
- Overly complex versioning could delay tester MVP delivery.
- Insufficient versioning could hide changed extracted values between imports.
- Future implementation must avoid treating corrections, annotations, tester
  feedback, or export packet membership as official public-source facts.
- Future database and migration tool choices may require adapting the physical
  separation pattern to product-specific capabilities without weakening the
  domain boundary.

## Deferred Decisions

This ADR explicitly defers:

- Actual schema files.
- Actual migration files.
- Database product.
- Migration tool.
- ORM.
- Table and column names.
- Indexes.
- Constraints.
- API framework.
- Import artifact format.
- Import implementation.
- Reset/reload implementation.
- Retention policy.
- Backup/restore policy.

## Work Not Approved By This ADR

No schema changes are approved by this ADR.

This ADR does not approve:

- Schema implementation.
- Migration implementation.
- Hosted database creation.
- App scaffold.
- Import code.
- Reset/reload code.
- Authentication.
- Queues.
- Annotations.
- Corrections.
- Hosted exports.
- New source-derived canonical fields.
- Extraction behavior changes.