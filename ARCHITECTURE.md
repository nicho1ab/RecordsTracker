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

ADR-0015 chooses PostgreSQL as the hosted tester MVP database product and
Alembic-managed migrations in the Python toolchain as the migration tooling
direction. PostgreSQL is the target persistence store for hosted source-derived
imports, reviewer-created state, audit events, export packet state, tester
feedback, reset/reload metadata, and auth role/scope references. SQLite and
Datasette remain retained for validation, inspection, debugging, local
exploration, export support, and transition comparison.
The first production-like runtime envelope is QNAP-first Docker Compose with a
Python app container and PostgreSQL in Docker. Application configuration must
remain host-portable: QNAP-specific host paths, backup locations, share names,
and operator procedures belong in deployment docs or host-local configuration,
not application code. The same environment-variable, migration, and persistent-
volume model should be movable later to AWS, Azure, DigitalOcean, Render, Fly.io,
or another host without a major rewrite.

ADR-0016 approves the next narrow source-ingestion boundary: browser-triggered,
server-executed CCLD retrieval jobs. The browser may submit only bounded CCLD
facility/license, record-type, and date-range inputs; the server or worker must
perform controlled CCLD discovery/fetch, raw artifact preservation, raw hash
computation, deterministic extraction/normalization, validation, PostgreSQL
import, safe job status, and existing hosted-queue review. This supersedes the
previous permanent blocker only for CCLD-only, facility/date/type-bounded,
authenticated, permissioned, rate-limited retrieval jobs. Direct browser
scraping, statewide crawling, automatic source expansion, non-CCLD sources,
private/authenticated source scraping, production OIDC implementation,
deployment changes, schema changes, and legal/completeness conclusions remain
unapproved until focused work explicitly adds and tests them.

The earlier hosted scaffold sample pages remain local-only and sample-only. The
Python standard-library app shell still includes health and smoke validation,
local setup checks, and a read-only `/source-records` list/detail shell over
fixture/sample records with local sample filtering/search, fixture/sample-only
source traceability summary panels, and semantic/accessibility validation. Those
sample pages do not read from SQLite or a hosted database, load live public-
source data, run import/sync, perform real provider login, persist reviewer-
created state, deploy to QNAP/Azure/AWS, or expose a public URL.

The hosted scaffold now also includes minimal PostgreSQL/Alembic project wiring,
the first controlled seeded corpus import path, a narrow database-backed
source-derived read service, a local/test auth/authz boundary scaffold, a
narrow local/test authenticated source-derived HTTP/API read route seam, and a
first local/test authenticated reviewer workflow shell, a narrow local/test
reviewer-created state persistence scaffold, a narrow local/test audit event
persistence scaffold, a narrow local/test authenticated audit history read
route seam, a narrow local/test authenticated reviewer-created state read route
seam, a narrow local/test authenticated reviewer note creation route seam over
the existing reviewer-created state scaffold, a narrow local/test workflow-shell
note action and status action over the selected source-derived detail context,
a thin browser-accessible local/test reviewer UI shell at `/reviewer` and
`/reviewer/records` over those existing seams, a thin browser-accessible
read-only facility trend route at `/reviewer/facilities/trends` over authorized
loaded source-derived records with deterministic monthly/quarterly aggregation,
coverage labels, anomaly cues, and complaint-detail links,
a thin browser-accessible
local/test CCLD facility lookup page at `/ccld/facilities` that reads committed
or configured full local/test CCLD program facility reference CSV rows, searches
safe scalar fields, shows the active reference source, falls back to the committed
tiny fixture when needed, and carries a selected facility/license number into
`/ccld/records/request`,
a thin browser-accessible local/test CCLD record request page at `/ccld/records/request` that filters
existing seeded source-derived rows by CCLD facility/license number and optional
date range, can load or refresh matching rows from local validated hosted
seeded-corpus output, renders matching complaint records as a guided
facility/date-scoped review queue with help, feedback guidance, progress counts,
reviewer-status filters derived from existing reviewer-created state, reviewer
note/status cues, source-traceability availability cues, suggested next-record
links, filtered-empty guidance, and a structured copyable tester feedback
checklist that must be copied externally, and links matches into the reviewer UI,
a CCLD-only local/test artifact builder that converts validated CCLD SQLite
pipeline output into hosted seeded-corpus JSON outside browser requests,
a local/test authenticated reset/reload dry-run route seam, and a local/test
authenticated reset/reload execution-plan route seam: a
no-secret database URL configuration seam, an Alembic script location, one
domain migration for import batch metadata and source-derived record staging,
one domain migration for a separate reviewer-created state scaffold table, one
domain migration for a separate audit event scaffold table, one domain migration
for a separate reset/reload operational planning metadata scaffold table,
scaffold/API boundary descriptors, a local JSON artifact importer for validated
pipeline-output-shaped fixtures, list/fetch helpers over staged source-derived
records, managed OIDC/OAuth2 provider-class configuration validation, actor/
role/scope/target models, protected read-service guards, and JSON handlers for
local/test auth provider integration planning that accept only non-secret
readiness inputs and summarize future provider registration, claim, role/scope,
and audit attribution expectations without persistence, plus JSON handlers for
listing staged source-derived records or fetching one staged record by key or
stable identity, plus read-only queue and detail shell payloads over those route
responses, plus JSON handlers for listing or fetching scaffold reviewer-created
state rows by approved reviewer state identifiers, schema-supported filters,
and bounded search over existing non-secret scaffold fields,
plus read-only workflow-shell detail composition of associated reviewer-created
state read route output and a compact derived summary for a selected source record,
plus workflow-shell note and status actions that resolve the selected source-
derived detail context before delegating to reviewer-created write routes,
plus simple server-rendered HTML pages that let a local tester list/search a
seeded complaint record, see list-level reviewer-created note/status indicators,
open detail, view a plain-language record summary, safe source traceability
fields, safe related seeded bundle context, reviewer-created notes/statuses,
CCLD return links, and record-specific feedback clues, submit reviewer note/status forms through the existing workflow
actions, and see read-after-write reviewer-created state without exposing
sensitive narrative fields,
plus a simple server-rendered CCLD request page that accepts only CCLD digit
facility/license numbers and optional valid date ranges, shows seeded match or
no-match results, renders queue triage summaries and source-traceability cues,
links seeded matches to reviewer pages, and explains the
external live-fetch command when broader retrieval is needed, plus a local/test
validated CCLD import/reload service that reads only validated hosted seeded-
corpus JSON artifacts and stages source-derived rows through the existing
idempotent hosted seeded import path,
plus a JSON handler that stores bounded non-secret reviewer note text as reviewer-created
scaffold payload under the existing state kind,
plus a JSON handler that stores bounded reviewer status values as reviewer-created
scaffold payload under the existing state kind,
plus JSON handlers for listing or fetching scaffold audit rows by approved audit
identifiers and schema-supported filters, plus an audit coverage planning
handler that reports current scaffold coverage, deferred audit categories,
actor attribution, target/source context, and non-secret metadata rules without
creating audit rows, plus JSON handlers for listing or
fetching persisted reset/reload planning metadata rows by approved planning
identifiers and schema-supported filters, plus a dry-run handler
that reports seeded import batch counts,
source-derived record counts by entity, scoped reviewer-created state scaffold
counts, scoped audit scaffold counts, future reviewer-created state handling options, required permissions,
validation requirements, audit requirements, and deferred destructive actions
without mutating data, plus an execution-plan handler that orders those
summaries into bounded non-destructive local/test action steps and can
optionally persist one non-secret operational
planning metadata record when explicitly requested by local/test code. This path preserves import batch identity, source traceability,
original source-derived values, authenticated attribution for scaffold rows,
audit rows for successful reviewer-created state scaffold writes only, and the
separation from reviewer-created state, audit rows, and operational metadata.
It does not implement real login flow, provider registration, sessions, cookies,
tokens, auth middleware, provider discovery calls, hosted URLs, full reviewer-created workflows, annotations,
corrections, note or status editing or deletion, production review status UI,
export packet decisions, tester feedback, reset/reload execution,
reviewer-created state archive or clear behavior, full audit coverage, audit UI,
audit export, new audit write behavior, hosted live crawling, hosted connector execution, production import automation, production
API framework behavior, or deployment.

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
accepted future direction for hosted tester reviewer-created state and imported
source-derived records. ADR-0015 chooses PostgreSQL as that database product and
Alembic-managed migrations as the migration tooling direction. The current
hosted scaffold adds local/test configuration validation, an Alembic script
location, and a first narrow domain migration for seeded import batch metadata
and source-derived record staging, plus a second narrow migration for one
reviewer-created state scaffold table, plus a third narrow migration for one
audit event scaffold table, plus a fourth narrow migration for one reset/reload
operational planning metadata scaffold table. The current auth boundary,
source-derived read route seam, reviewer workflow shell with read-only queue/
detail payloads and narrow note/status actions,
reviewer-created state scaffold service, reviewer-created state read route seam,
audit history read route seam, audit coverage planning seam, reset/reload dry-run seam, reset/reload
execution-plan seam, opt-in reset/reload
planning metadata scaffold, and read-only reset/reload planning metadata route seam
are local/test only; auth tables, export tables, feedback tables, broader
reset/reload metadata tables, ORM models, stateful reviewer workflow API behavior,
deployment, hosted
connection configuration, and production import automation remain deferred, and
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
- Hosted tester MVP source-derived records may enter the hosted environment
  through controlled imports from validated pipeline output, or through the
  ADR-0016-approved browser-triggered, server-executed CCLD retrieval job
  boundary once implemented. Retrieval jobs must remain CCLD-only,
  facility/date/type bounded, server-side, raw-source-preserving,
  PostgreSQL-imported, authenticated, permissioned, rate-limited, and tested
  without live CCLD calls in CI.
- Future hosted schema work must preserve clear physical separation between
  import metadata, source-derived imported records, reviewer-created state,
  audit events, export packet state, tester feedback, and operational/reset
  metadata.
- Hosted tester MVP persistence must use PostgreSQL and Alembic-managed
  migrations for future schema implementation. The current scaffold may validate
  no-secret local/test database configuration, stage source-derived records from
  a controlled validated seeded artifact, and describe separated persistence and
  API boundaries, expose a local/test database-backed read service over the
  staged source-derived records, and expose a narrow local/test authenticated
  source-derived read route seam, reviewer workflow shell with read-only queue/
  detail payloads and narrow reviewer note/status actions, a thin local/test
  browser reviewer UI shell over those seams, reset/reload dry-run route seam,
  execution-plan route seam, opt-in operational planning metadata persistence plus
  read-only planning metadata routes, but it must not imply stateful
  production reviewer views, full reviewer workflows, production import
  automation, production API framework behavior, or operational reset/reload
  execution are implemented.
  SQLite and Datasette remain retained validation and transition-comparison
  tools, not the hosted reviewer-created state store.
- Hosted tester MVP access must be authenticated and role-scoped; anonymous
  hosted tester access is not approved because the hosted app includes
  reviewer-created state, tester feedback, annotations, corrections, export
  decisions, audit history, and sensitive review context.
- Hosted tester MVP authentication must use a managed standards-based OpenID
  Connect/OAuth 2.0 provider class, with provider secrets and environment
  configuration kept out of the repository. Application authorization must still
  enforce role, permission, and project/corpus scope before reviewer-created
  state is enabled. The current scaffold models that local/test auth boundary
  and protects the source-derived read service. It can also return a local/test
  non-persistent provider integration readiness plan using non-secret boolean
  inputs, but it does not implement real provider login, sessions, cookies, auth
  middleware, provider registration, hosted URLs, user tables, or role/scope
  persistence.
- Hosted tester MVP implementation may proceed from the ADR-0012 scaffold-first
  sequence into the ADR-0013, ADR-0014, and ADR-0015 product-enabling path. The
  current seeded corpus import path is limited to controlled validated artifact
  imports into import batch and source-derived staging tables plus local/test
  service reads over those staged records plus local/test auth guards for those
  reads, a narrow local/test reviewer-created state scaffold table linked to
  staged source-derived records, a narrow local/test authenticated reviewer-
  created state read route seam over those scaffold rows, a narrow local/test
  audit event scaffold table tied to successful reviewer-created state scaffold
  writes only, a narrow local/test authenticated audit history read route seam
  over those audit rows, a narrow local/test audit coverage planning seam over
  current and deferred audit categories, and a
  non-mutating reset/reload dry-run plan and execution-plan steps over staged
  seeded corpus metadata, scoped reviewer-created scaffold and audit scaffold row counts, and explicit
  dry-run planning metadata when requested, with read-only planning metadata
  list/fetch access over persisted planning rows. Real provider
  authentication implementation, persistent authorization storage, production
  API framework behavior, correction workflows, queues, annotations, full
  reviewer-created workflow persistence, reset/reload commands or APIs, hosted
  deployment, full audit coverage, audit UI, audit export, retention automation,
  production import automation, and hosted export builders remain unimplemented
  until focused implementation PRs validate the affected layer.
- QNAP Docker is the first practical production-like runtime target, using the
  committed Dockerfile and Compose file with PostgreSQL in Docker, named volumes,
  health checks, Alembic startup migration wiring, and no-secret environment
  examples. This runtime envelope does not implement public URL behavior,
  production auth, retrieval jobs, production import automation, monitoring,
  incident response, or a QNAP-specific application code path. ADR-0016 approves
  a future controlled CCLD retrieval-job boundary that this runtime or a
  portable worker/container/task can host after a focused implementation branch.
  Later cloud deployment should preserve the same environment and persistence
  contracts where possible.

## Accessibility

Any user-facing output must meet the accessibility requirements in `ACCESSIBILITY_REQUIREMENTS.md`. Retained Datasette views, Datasette templates/plugins, exports, prototypes, and future UI layers must be evaluated before use.
