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
tester workflows after the data model, authentication/access, sync,
schema/migration, operational, and implementation boundaries are accepted.

ADR-0008 defines the hosted tester MVP data and review-state model boundary. It
requires two distinct data domains: a source-derived data domain for imported or
public-source-derived records with preserved traceability, and a
reviewer-created state domain for review projects, review items, statuses,
queues, annotations, proposed corrections, correction decisions, tester
feedback, export packets, and audit events. Reviewer-created state must not
overwrite canonical source-derived records or original extracted values.

ADR-0009 defines the hosted tester MVP import/sync strategy. It keeps the
Python ingestion and extraction pipeline as the source-derived data producer,
starts the tester MVP with controlled snapshot imports from validated pipeline
output, preserves stable source-derived identities and traceability fields, and
does not approve hosted live crawling, hosted connector execution, import code,
schemas, migrations, or reset/reload implementation. ADR-0012 later separately
approved scaffold-first sequencing only; it did not approve import/sync behavior.

ADR-0010 defines the hosted tester MVP physical schema and migration strategy
boundary. Future hosted schema work must separate import/batch metadata,
source-derived imported records, reviewer-created state, audit events, export
packet state, tester feedback, and operational/reset metadata through separate
physical schema areas or clearly separated table groups. It does not approve
schema files, migration files, a database product, a migration tool, import
implementation, or reset/reload implementation. ADR-0012 later separately
approved scaffold-first sequencing only; it did not approve schema work.

ADR-0011 defines the hosted tester MVP authentication and access boundary. The
hosted tester MVP must require authenticated, explicitly provisioned or invited
tester access, use simple role-based boundaries, and prevent anonymous hosted
tester access. It does not approve an authentication provider, identity storage,
authorization middleware, role schema, user tables, or hosted deployment.
ADR-0012 later separately approved scaffold-first sequencing only; it did not
approve authentication or authorization implementation.

ADR-0012 defines the hosted tester MVP scope and scaffold sequencing boundary.
Hosted implementation may begin after ADR-0012, but only through a sequenced
scaffold-first path. The first implementation branch may create a runnable,
testable hosted app scaffold with smoke validation and local development docs;
it must not implement business workflows, domain schema, authentication,
authorization, import/sync, review queues, annotations, corrections, exports,
reset/reload, hosted deployment, or extraction behavior.

ADR-0013 defines the hosted tester MVP operational boundaries for audit logging,
export generation, reset/reload, and tester data retention. It clears the next
product-moving implementation path while keeping concrete authentication,
database, migration, schema, API, import/reset, export builder, audit
persistence, retention automation, and deployment implementation deferred to
focused branches.

ADR-0014 chooses the hosted tester MVP authentication provider and role
implementation direction. The hosted tester MVP will use a managed
standards-based OpenID Connect/OAuth 2.0 identity provider class, preserve the
ADR-0011 minimum roles, require project or corpus-scoped authorization before
reviewer-created state is enabled, and capture identity context needed for
ADR-0013 audit logging. It does not approve schemas, middleware, provider
configuration, secrets, hosted URLs, or deployment.

The current hosted scaffold state is local-only and sample-only. It includes a
Python standard-library app shell, health and smoke validation, local setup
checks, and a read-only `/source-records` list/detail shell over fixture/sample
records with local sample filtering/search, fixture/sample-only source
traceability summary panels, and semantic/accessibility validation. It does not
read from SQLite or a hosted database, load live public-source data, run
import/sync, authenticate users, persist reviewer-created state, deploy to
QNAP/Azure/AWS, or expose a public URL.

## Components

### Connectors

Connectors are source-specific modules responsible for discovering, fetching, and extracting data from one public data source.

Before a new connector or import path is implemented, candidate public sources
should be inventoried in `PUBLIC_SOURCE_DATA_INVENTORY.md`. The inventory may
classify structured CSV/open-data sources, HTML portal/detail pages, PDFs,
metadata/catalog pages, and future multi-state public sources. It is a planning
surface only; it does not create source adapters, schemas, imports, hosted
workflows, or canonical fields.

### Raw source storage

Raw source files are stored in ordinary file storage under `data/raw/`. Each file must have a stable name, source URL, retrieval timestamp, and SHA-256 hash.

### Structured storage

SQLite is the initial validation database. A hosted relational database is the
preferred future direction for hosted tester reviewer-created state and imported
source-derived records. The specific database product, migration tool, table
names, columns, indexes, constraints, and implementation remain deferred, but
future hosted schema work must preserve the physical data-domain separation
accepted by ADR-0010.

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
retention implementation PRs validate the concrete layer.

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
- Hosted tester MVP source-derived records should enter the hosted environment
  through controlled imports from validated pipeline output; direct hosted live
  crawling or connector execution is not approved for the tester MVP without a
  later ADR.
- Future hosted schema work must preserve clear physical separation between
  import metadata, source-derived imported records, reviewer-created state,
  audit events, export packet state, tester feedback, and operational/reset
  metadata.
- Hosted tester MVP access must be authenticated and role-scoped; anonymous
  hosted tester access is not approved because the hosted app includes
  reviewer-created state, tester feedback, annotations, corrections, export
  decisions, audit history, and sensitive review context.
- Hosted tester MVP authentication must use a managed standards-based OpenID
  Connect/OAuth 2.0 provider class, with provider secrets and environment
  configuration kept out of the repository. Application authorization must still
  enforce role, permission, and project/corpus scope before reviewer-created
  state is enabled.
- Hosted tester MVP implementation may proceed from the ADR-0012 scaffold-first
  sequence into the ADR-0013 and ADR-0014 product-enabling path. Hosted schemas,
  concrete authentication implementation, correction workflows, queues,
  annotations, import/sync, reset/reload commands or APIs, hosted deployment,
  audit persistence, retention automation, and hosted export builders remain
  unimplemented until focused implementation PRs validate the affected layer.

## Accessibility

Any user-facing output must meet the accessibility requirements in `ACCESSIBILITY_REQUIREMENTS.md`. Retained Datasette views, Datasette templates/plugins, exports, prototypes, and future UI layers must be evaluated before use.
