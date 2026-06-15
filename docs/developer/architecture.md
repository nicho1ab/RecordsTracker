# Developer Architecture

See root `ARCHITECTURE.md` for the canonical architecture.

## Package layout

```text
src/ccld_complaints/
  cli/
  connectors/
  extraction/
  hosted_app/
    audit_event_routes.py
    audit_events.py
    auth.py
    persistence.py
    reviewer_created_state.py
    reviewer_created_state_routes.py
    reviewer_ui.py
    reset_reload_dry_run.py
    reviewer_workflow_shell.py
    schema_api_scaffold.py
    seeded_import.py
    source_derived_reads.py
    source_derived_routes.py
  storage/
  quality/
  utils/

migrations/
  env.py
  versions/
```

## Data flow

1. Discover report URLs.
2. Fetch raw source files.
3. Store raw files and hashes.
4. Extract structured fields.
5. Normalize to canonical objects.
6. Validate against JSON schemas.
7. Write to SQLite.
8. Expose SQLite through Datasette for validation, inspection, debugging, local
  exploration, and export support.
9. Keep future primary reviewer UX work behind production-discovery requirements
  and accepted architecture decisions.
10. Run the local hosted tester MVP scaffold only as a placeholder app shell and
  smoke route until later implementation PRs add approved hosted behavior.
11. Use the hosted seeded import path only to stage source-derived records from
  controlled validated pipeline-output artifacts into PostgreSQL/Alembic import
  batch and source-derived tables.
12. Use the hosted source-derived read service only for local/test list and
  fetch access to staged seeded corpus records with import batch context and
  preserved source traceability.
13. Use the hosted auth boundary scaffold only for local/test actor, role,
  account-status, scope, and authorization-target checks before protected
  service reads.
14. Use the hosted auth provider integration planning seam only for local/test
  user-role-admin readiness planning over the accepted managed OpenID Connect/
  OAuth 2.0 provider class, without storing configuration or implementing login.
15. Use the hosted source-derived route seam only for local/test authenticated
  JSON list and fetch access over staged seeded corpus records.
16. Use the hosted reviewer workflow shell only for local/test authenticated
  read-only queue and detail payloads that consume the source-derived route seam,
  compose associated reviewer-created state read route output plus a compact
  summary on selected detail responses, and expose narrow reviewer note/status
  actions that delegate to existing reviewer-created write routes after
  resolving the selected source record.
17. Use the hosted reviewer UI shell only as a local/test browser-accessible
  server-rendered HTML wrapper over the seeded fixture corpus and existing
  workflow seams, allowing list/search/detail, list-level reviewer-created
  note/status indicators, safe source traceability display, safe related seeded
  bundle context, note/status form submission, and read-after-write reviewer-
  created state display without exposing sensitive
  narrative fields or adding production auth, schema changes, exports, reset/reload
  execution, live crawling, connector execution, or deployment.
18. Use the hosted CCLD record request page only as a local/test browser-
  accessible server-rendered HTML wrapper over existing seeded source-derived
  reads, allowing CCLD digit facility/license number and optional date-range
  filtering, local validated hosted seeded-corpus load/refresh into existing
  source-derived records, guided facility/date-scoped request result queue
  rendering, progress counts and reviewer-status filters derived from existing
  reviewer-created state, first-time help and feedback guidance, and reviewer UI
  links without running live crawling, executing connectors, mutating reviewer-
  created state from the request page, creating audit rows from the request
  page, persisting feedback, supporting non-CCLD sources, or adding production
  auth, schema changes, or deployment.
19. Use the CCLD hosted artifact builder only as a local/test outside-browser
  conversion from validated CCLD SQLite pipeline output into hosted seeded-
  corpus JSON. It preserves source traceability and original values for CCLD
  source-derived bundles without running live crawling, executing browser
  connector work, supporting non-CCLD sources, adding schema changes, mutating
  reviewer-created state, or creating audit rows.
21. Use the hosted reviewer-created state scaffold only for local/test
  authenticated placeholder state rows linked to staged source-derived record
  keys, including bounded non-secret reviewer note payloads and bounded reviewer
  status payloads, without modifying source-derived records.
22. Use the hosted reviewer-created state read route seam only for local/test
  authenticated JSON list, fetch, filter, and bounded search access over those
  scaffold rows without mutating reviewer-created, source-derived, audit, or
  operational metadata.
23. Use the hosted audit event scaffold only for local/test audit rows created
  for successful reviewer-created state scaffold writes, without modifying
  source-derived or reviewer-created rows.
24. Use the hosted audit history read route seam only for local/test
  authenticated JSON list and fetch access over those scaffold audit rows.
25. Use the hosted audit coverage planning seam only for local/test
  authenticated, non-persistent readiness planning over current and deferred
  audit categories, without creating audit rows or mutating persisted data.
26. Use the hosted reset/reload dry-run seam only for local/test authenticated
  planning over staged seeded corpus metadata, with optional persisted
  operational planning metadata when explicitly requested, without mutating
  source-derived, reviewer-created, or audit data.
27. Use the hosted reset/reload execution-plan seam only for local/test
  authenticated, ordered, bounded non-destructive action plans over existing
  dry-run summaries and planning metadata context, with optional persisted
  operational planning metadata when explicitly requested, without mutating
  source-derived, reviewer-created, or audit data.
28. Use the hosted reset/reload planning metadata read route seam only for
  local/test authenticated JSON list and fetch access over persisted planning
  rows, without mutating operational, source-derived, reviewer-created, or audit
  data.
29. Keep full reviewer-created workflows, annotations, corrections, exports,
  full audit coverage, audit UI, audit export, reset/reload execution, real login flow, auth
  middleware, provider integration, production API framework behavior, live
  crawling, connector execution, and production automation in future focused
  branches until those layers are implemented and tested.

## Hosted scaffold boundary

The first hosted tester MVP scaffold is a local-first Python standard-library
HTTP app shell. It provides a placeholder page and health route for smoke
validation on a Windows development workstation. Its local setup check verifies
Python and development-tool prerequisites without installing software, requiring
admin rights, or requiring Node, Docker, QNAP, Azure, AWS, cloud resources, or a
public URL. The optional QNAP-first Docker Compose runtime is separate from the
local setup check and packages the same scaffold with PostgreSQL in Docker for
production-like validation.

The scaffold also includes a local-only read-only source-derived view shell over
fixture/sample records. This view is an app-facing placeholder for source-record
list, local sample filtering/search, fixture/sample-only source traceability
summary panels, and detail navigation only. Its sample list supports query,
jurisdiction, source-family filtering, and traceability summary indicators
against in-memory fixture/sample records so future source-derived records from
multiple jurisdictions and source families can use the same list/filter/summary
pattern. It does not read from SQLite or a hosted database, run import/sync,
load live public-source data, perform real provider login, or persist
reviewer-created state.

The scaffold also includes a local-only read-only `/facilities` sample view and
detail pages backed only by the committed tiny public-source facility fixtures
under `tests/fixtures/public_source_facilities/`. The facility view displays
source-shaped facility master fields and manifest placeholder metadata for
traceability-style UI validation. Facility detail pages also show fixture-only
source coverage indicators and related fixture/sample source-record context
where the local sample mapping exists. The view does not read ignored raw CSVs,
generated profiling outputs, SQLite, a hosted database, live public-source
data, import/sync output, authentication state, or reviewer-created state.

ADR-0013 now defines the product-enabling operational boundaries for audit
logging, export generation, reset/reload, and tester data retention. ADR-0014
now chooses a managed standards-based OpenID Connect/OAuth 2.0
provider class and role implementation direction. ADR-0015 now chooses
PostgreSQL and Alembic-managed migrations for hosted tester MVP persistence.
The scaffold now includes minimal PostgreSQL/Alembic wiring and a controlled
seeded corpus import path: no-secret database URL configuration validation, an
Alembic script location, a narrow domain migration for import batch metadata and
source-derived record staging, a second narrow domain migration for one
reviewer-created state scaffold table, a third narrow domain migration for one
audit event scaffold table, a fourth narrow domain migration for one reset/reload
operational planning metadata scaffold table, a local validated JSON artifact importer,
and scaffold/API boundary descriptors for future source-derived API routes and
reviewer-created state. It also includes a narrow database-backed
source-derived read service for local/test list and fetch access to staged
records while preserving import batch context, original source-derived values,
and source traceability. The auth boundary scaffold adds managed OIDC/OAuth2
provider-class configuration validation plus local/test authenticated actor,
role, scope, account-status, target, and audit-context models for protected
service seams. The auth provider integration planning seam adds local/test
user-role-admin readiness planning over non-secret provider inputs without
persisting configuration or implementing login. The source-derived route seam adds local/test authenticated JSON
list, fetch-by-key, and fetch-by-stable-identity handlers over those staged
records. The reviewer workflow shell adds local/test authenticated read-only
queue and detail payloads over those route responses, and detail payloads can
include associated reviewer-created state read route output and a compact
summary derived from that output for the selected source record. It also exposes
narrow local/test reviewer note/status actions that resolve the selected detail
source record before delegating to existing reviewer-created write routes, while
keeping status editing/deletion, queue assignment, full annotations,
corrections, tester feedback, export packet state, and queue-state persistence
deferred. The reset/reload dry-run seam adds
local/test authenticated planning over seeded corpus metadata: it reports
existing import batches, source-derived record counts by entity, scoped reviewer-
created scaffold row counts, scoped audit scaffold row counts, future reviewer-
created state handling options, required permissions, validation requirements,
audit requirements, and deferred destructive actions without deleting,
overwriting, archiving, importing, reloading, or creating new dry-run audit
events. The reset/reload execution-plan seam converts the same summaries and
planning metadata context into ordered bounded non-destructive action steps and
can optionally persist one non-secret planning metadata record when explicitly
requested by local/test code. The planning metadata read route
seam can list or fetch those persisted rows with schema-backed filters after
import/reload authorization, without executing reset/reload. The reviewer-created state scaffold service can create and read
placeholder review-item-state rows only after authenticated actor, role, account
status, scope, and source-derived reference checks pass; it does not implement
full reviewer workflows. The local/test reviewer note creation route writes
bounded non-secret note text through that same scaffold and audit path under the
existing state kind, without adding note editing/deletion or a schema change. The local/test reviewer-created state read route seam
can list, fetch, filter, or search those persisted scaffold rows after
reviewer-state-read authorization passes, without mutating reviewer-created,
source-derived, audit, or operational metadata. Successful reviewer-created state scaffold writes also
create a separate audit scaffold row with actor, permission, scope, target, and
source-derived context; if the audit row cannot be created, the reviewer-created
state write is rolled back. The local/test audit history read route seam can list
or fetch those audit rows only after audit-read authorization passes. The
local/test audit coverage planning seam can summarize current and deferred audit
coverage without creating audit rows or persisting planning records. The next hosted tester MVP work can move toward real
provider integration, later reset/reload execution behavior beyond this
non-destructive execution-plan seam, fuller audit coverage, and stateful reviewer-created workflow layers
when each branch validates its layer.

The scaffold does not implement real provider login, token validation, sessions,
cookies, auth middleware, role or user storage, production domain schema beyond
the seeded import table group, reviewer-created state scaffold table, and audit
event scaffold table, production API framework behavior, production import automation, stateful queues,
annotations, corrections, exports, tester feedback, full audit trail, reset/reload
execution, hosted live crawling, hosted connector execution, deployment,
source-derived canonical field changes, full reviewer-created workflow
persistence, or extraction behavior. Its database-backed reads, auth guards,
source-derived read routes, reviewer workflow shell, reviewer-created state
scaffold service, reviewer-created state read routes, audit event scaffold
service, audit history read routes, reset/reload dry-run, and planning metadata
read routes are limited to
local/test service seams. The local non-Docker workflow does not require Docker,
QNAP Container Station, Azure, AWS, a public URL, secrets, or cloud resources.
The optional QNAP-first Docker runtime provides a portable app/PostgreSQL
container envelope only and does not add production auth, public URL behavior,
hosted live crawling, connector execution, or production import automation.

See `docs/developer/hosted-scaffold.md` for local run and smoke-check commands.

## Current ingestion boundary

The CCLD connector includes `ingest_facility_reports_for_facility()` for the initial single-facility workflow. It discovers report candidates and runs each available report through fetch or fixture load, raw storage for live fetches, extraction, normalization, validation, and emit.

When the CCLD connector is initialized with a SQLite database path, the emit step writes normalized facility, source document, complaint, allegation, event, and extraction audit records to the existing SQLite schema. Writes are idempotent upserts keyed by the canonical record identifiers, so rerunning the same ingestion updates existing rows rather than duplicating them.

In tests, report content must be loaded through injected fixture loaders. Tests must not make live CCLD web requests.
