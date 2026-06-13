# Architecture

## Current architecture and production-discovery boundary

```text
Public source portal/API
   -> connector discovery
   -> raw fetcher
   -> raw file storage
   -> extractor
   -> normalizer
   -> contract validator
   -> SQLite database
      -> Datasette validation/inspection/export-support layer
      -> production-discovery boundary for future primary review UX
         -> future reviewer-created state layer
            (review state, annotations, proposed corrections, tester feedback,
             export packet decisions)
```

The proof of concept proved the ingestion, extraction, raw preservation, source
traceability, local review, and export path. Datasette is retained over SQLite
for validation, inspection, debugging, local exploration, and export support. It
is no longer the terminal primary presentation layer for the future product
direction.

The production-discovery boundary is where the project defines requirements and
architecture decisions for reviewer state, guided queues, annotations,
corrections, collaboration, accessibility, exports, and source traceability. This
document does not select a production stack.

ADR-0006 defines the hosted tester MVP architecture boundary. It requires a
primary reviewer application layer separate from Datasette, keeps Datasette as a
validation, inspection, debugging, local exploration, export-support, and
transition-comparison layer, and defers production stack selection to future
ADRs.

ADR-0007 recommends a hybrid transition direction for hosted tester MVP
planning: preserve the existing Python ingestion and extraction pipeline, retain
SQLite and Datasette for validation and transition comparison, and introduce a
hosted relational database plus hosted reviewer application/API boundary for
tester workflows after the remaining data model, authentication, sync, export,
audit, retention, and implementation ADRs are accepted.

ADR-0008 defines the hosted tester MVP data and review-state model boundary. It
requires two distinct data domains: a source-derived data domain for imported or
public-source-derived records with preserved traceability, and a
reviewer-created state domain for review projects, review items, statuses,
queues, annotations, proposed corrections, correction decisions, tester
feedback, export packets, and audit events. Reviewer-created state must not
overwrite canonical source-derived records or original extracted values.

## Components

### Connectors

Connectors are source-specific modules responsible for discovering, fetching, and extracting data from one public data source.

### Raw source storage

Raw source files are stored in ordinary file storage under `data/raw/`. Each file must have a stable name, source URL, retrieval timestamp, and SHA-256 hash.

### Structured storage

SQLite is the initial validation database. A hosted relational database is the
preferred future direction for hosted tester reviewer-created state and imported
source-derived records, but the specific database product and schema remain
deferred to future ADRs.

### Presentation

Datasette is the retained browser/search/API interface for validation,
inspection, debugging, local exploration, and export support because it can
expose SQLite data quickly without creating a custom application.

### Production-discovery review boundary

The future primary review experience is undecided. Production-discovery must
define product requirements and architecture boundaries before selecting a stack
or building a production application.

The future review boundary must account for persistent navigation, guided
queues, saved reviewer state, annotations, correction workflows, contextual help,
collaboration constraints, accessible exports, and source traceability.

The minimum workflow and hosted tester readiness requirements are defined in
`PRODUCTION_DISCOVERY_REQUIREMENTS.md`.
The hosted tester MVP architecture boundary is defined in
`docs/decisions/ADR-0006-hosted-tester-mvp-architecture-boundaries.md`.

### Future reviewer-created state layer

Review state, annotations, proposed corrections, tester feedback, and export
packet inclusion decisions are future application/reviewer state. They must stay
separate from source-derived canonical data unless a future schema ADR approves
the persistence model.

The layer must preserve original extracted values, source document traceability,
raw source preservation, and extraction audit context where available. Proposed
corrections may influence a reviewed export presentation only through an
explicit traceable correction layer; they must not overwrite raw files or erase
original extracted values.

ADR-0008 further defines the minimum reviewer-created concepts for hosted tester
MVP planning: review project or corpus, review item, review status, queue
membership, assignment if applicable, annotation, field-level note, source
verification note, proposed correction, correction decision, tester feedback,
export packet, export packet item, and audit event. These concepts are planning
boundaries only until future schema, import/sync, API, export, audit, and
retention ADRs approve implementation details.

## Boundaries

- The repository owns ingestion, extraction, validation, storage, documentation, and tests.
- The public portal remains the public source of record.
- Raw storage is evidence for reproducibility and regression testing, not a replacement for the public portal.
- Datasette is a retained validation, inspection, debugging, local exploration,
  and export-support layer, not the governed primary future reviewer UX.
- Reviewer-created state for hosted review workflows is separate from
  source-derived canonical records and must be defined by production-discovery
  requirements and future ADRs before implementation.
- Production stack selection belongs in future ADRs after production-discovery
  requirements are documented.
- The preferred hosted tester MVP direction is hybrid, not Datasette-primary:
  preserve the Python extraction pipeline and local SQLite/Datasette validation
  path while planning a hosted relational review-state store and hosted
  reviewer app/API boundary.
- Production app scaffolding, hosted schemas, authentication implementation,
  correction workflows, queues, annotations, and hosted export builders are not
  approved until the relevant future ADRs are complete.

## Accessibility

Any user-facing output must meet the accessibility requirements in `ACCESSIBILITY_REQUIREMENTS.md`. Retained Datasette views, Datasette templates/plugins, exports, prototypes, and future UI layers must be evaluated before use.
