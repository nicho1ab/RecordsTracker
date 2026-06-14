# Hosted Scaffold

## Purpose

This document explains how to run the first local hosted tester MVP scaffold.
The scaffold is a runnable placeholder app shell and smoke route only. It is not
a functioning reviewer workflow yet; the current reviewer workflow shell is a
local/test seam with read-only queue/detail payloads and narrow reviewer
note/status actions, not a stateful hosted tester workflow.

The scaffold is local-first and must run on a Windows development workstation
before any QNAP, Azure, AWS, public hosting, or public URL work is attempted.
It uses Python standard-library HTTP tooling to avoid creating a final
production frontend, API, database, authentication, hosting, or deployment
commitment.

## Required local tools

- Windows PowerShell.
- Python 3.11 or newer.
- The repository development dependencies from `requirements-dev.txt` for
  tests, lint, and type checks.
- The runtime dependencies from `requirements.txt`, including Alembic,
  SQLAlchemy, and the PostgreSQL driver used by the scaffolded migration
  wiring.

Node.js is not required. Docker is not required. QNAP Container Station is not required.
No local PostgreSQL server is required for scaffold smoke, boundary tests, or
seeded artifact parsing tests. A PostgreSQL-compatible database URL is required
only when a developer explicitly runs Alembic migrations or the seeded corpus
import command. The database-backed read service and auth boundary scaffold can
be exercised in unit tests against in-memory SQLite and fixture actors. The auth
provider integration planning seam can be exercised in unit tests with explicit
local/test actor and scope context and non-secret readiness inputs. The
source-derived API route seam can also be exercised in unit tests with an
explicit local/test route context. The reset/reload dry-run seam can be
exercised in unit tests with an explicit database, actor, and corpus scope
context, including optional persisted planning metadata and read-only planning
metadata route access. The reset/reload execution-plan seam can also be
exercised in unit tests with that explicit local/test context and produces only
bounded non-destructive action-plan output. No cloud resources, public URLs, app
registrations, cloud databases, DNS records, deployment credentials, secrets, or
tokens are required.

## Verify local prerequisites

Run the local setup check from the repository root after installing project
dependencies:

```powershell
.\scripts\check-hosted-scaffold-local.ps1
```

The check verifies the Python version, hosted scaffold package import, and local
development tools used for focused tests, lint, and type checks. It also checks
that Alembic, SQLAlchemy, and the PostgreSQL driver are importable for the
scaffolded migration wiring. It reports that Node/npm, Docker, a local
PostgreSQL server, QNAP, cloud resources, and a public URL are not required for
local scaffold smoke, boundary tests, or seeded artifact parsing tests.

The local setup check does not install software, does not require admin rights,
does not create secrets, and does not contact cloud services.

## Install dependencies

From the repository root, create and activate a local virtual environment if one
does not already exist:

```powershell
py -m venv .venv
```

```powershell
.\.venv\Scripts\Activate.ps1
```

Install runtime and development dependencies:

```powershell
python -m pip install -r requirements.txt -r requirements-dev.txt
```

## Start the scaffold locally

Run the scaffold from the repository root:

```powershell
.\scripts\run-hosted-scaffold.ps1 -Port 8000
```

Open `http://127.0.0.1:8000/` on the same workstation. The page must identify
itself as a scaffold and not a functioning reviewer workflow yet. It must not imply
that authentication, records, workflows, cloud hosting, QNAP, Azure, or AWS are
available.

## Open the sample read-only source view shell

The scaffold includes a local-only sample source-derived view shell at:

```text
http://127.0.0.1:8000/source-records
```

The page displays fixture/sample records only. It does not load live public data,
does not read from a database, does not run import/sync, does not authenticate
users, and does not persist reviewer-created state. Its source-traceability-style
fields are sample values that exist only to exercise the future read-only
reviewer-app shape.

The list includes local sample filtering/search controls for the query text,
jurisdiction, and source family. These controls filter only the in-memory
fixture/sample records shown by the shell. They do not query live public-source
data, SQLite, a hosted database, an import process, or reviewer-created state.

The filter shape is intentionally source-family and jurisdiction aware so future
source-derived records from multiple jurisdictions and source families can be
presented through the same list/filter pattern after the relevant source,
import, schema, and hosted workflow decisions are approved. The current shell
still keeps the fixture/sample labels, read-only behavior, source-derived versus
reviewer-created state separation, semantic structure, accessibility validation,
and no-database, no-import, no-real-login, no-deployment boundary.
The source-derived versus reviewer-created state separation remains visible in
the sample shell text and tests.

The list also includes a fixture/sample-only source traceability summary panel.
It counts whether the current sample result set has visible sample source URL,
raw SHA-256, connector name, retrieval timestamp, report index, extraction
warning, jurisdiction, and source-family values. Detail pages include a matching
sample traceability block for the selected record. These panels are indicators
over in-memory fixture/sample records only. They do not verify live public-source
records, prove source completeness, read from SQLite or a hosted database, run
import/sync, or expose reviewer-created state.

The summary shape is intentionally jurisdiction and source-family aware so
future source-derived records from multiple jurisdictions and source families can
use the same list/filter/summary pattern after the relevant source, import,
schema, and hosted workflow decisions are approved.

## Open the sample facility master view

The scaffold also includes a local-only sample facility master view at:

```text
http://127.0.0.1:8000/facilities
```

The page displays read-only fixture/sample facility rows loaded only from the
committed tiny public-source facility fixtures under
`tests/fixtures/public_source_facilities/`. Detail pages are available from the
facility number links and show source-family, jurisdiction, profiled source
shape, source dataset reference, source URL placeholder, raw SHA-256 placeholder,
and retrieval-time placeholder metadata from the committed fixture manifest.
Facility detail pages also show fixture-only source coverage indicators and
related fixture/sample source-record context when the local sample mapping
connects a facility-master fixture row to a sample source record. Program-
specific fixture rows without that local mapping are labeled as not represented
in the fixture/sample mapping.

The facility sample view does not load live public-source data, read ignored raw
CSVs, read generated profiling outputs, read SQLite or a hosted database, run
import/sync, perform real provider login, persist reviewer-created state, or
prove source completeness, statewide coverage, official facility status, or
legal or facility-wide conclusions.

## PostgreSQL and Alembic seeded import wiring

The repository now includes minimal PostgreSQL/Alembic project wiring and a
controlled seeded corpus import path for hosted tester MVP persistence. The
wiring includes:

- `alembic.ini` with an empty committed database URL setting.
- `migrations/` as the Alembic script location.
- `migrations/versions/20260613_0001_seeded_corpus_import.py` with import batch
  metadata and source-derived record staging tables.
- `migrations/versions/20260614_0002_reviewer_created_state_scaffold.py` with
  one separate reviewer-created state scaffold table linked to staged
  source-derived record keys.
- `migrations/versions/20260614_0003_audit_event_scaffold.py` with one separate
  audit event scaffold table for successful reviewer-created state scaffold
  writes only.
- `migrations/versions/20260614_0004_reset_reload_operational_metadata.py` with
  one separate reset/reload operational planning metadata scaffold table for
  explicitly requested dry-run planning records only.
- `ccld_complaints.hosted_app.persistence` for no-secret database URL validation
  and ADR-0010 persistence boundary descriptors.
- `ccld_complaints.hosted_app.auth` for managed OIDC/OAuth2 provider-class
  configuration validation, local/test actor context, role and scope guards, and
  protected source-derived read service helpers.
- `ccld_complaints.hosted_app.auth_provider_integration_plan` for local/test
  user-role-admin readiness planning over the accepted managed OIDC/OAuth2
  provider class, accepting only non-secret planning inputs and performing no
  persistence, provider registration, token handling, or network calls.
- `ccld_complaints.hosted_app.schema_api_scaffold` for scaffold-only source-
  derived and reviewer-created state API boundary descriptors.
- `ccld_complaints.hosted_app.seeded_import` for loading a controlled validated
  JSON artifact into the seeded import tables.
- `ccld_complaints.hosted_app.source_derived_reads` for local/test list and
  fetch access to staged source-derived records with import batch context.
- `ccld_complaints.hosted_app.source_derived_routes` for local/test
  authenticated JSON list, fetch-by-key, and fetch-by-stable-identity route
  handlers over staged source-derived records.
- `ccld_complaints.hosted_app.reviewer_workflow_shell` for a local/test
  authenticated review queue and detail shell over source-derived route
  responses, with read-only selected detail payloads able to compose associated
  reviewer-created state read route output and narrow note/status actions that
  delegate to existing reviewer-created write routes after resolving the
  selected source record.
- `ccld_complaints.hosted_app.reviewer_created_state` for local/test
  authenticated reviewer-created state scaffold writes and scoped reads without
  mutating staged source-derived records.
- `ccld_complaints.hosted_app.reviewer_created_state_routes` for local/test
  authenticated JSON list and fetch access over persisted reviewer-created
  scaffold rows without mutating staged source-derived, reviewer-created, audit,
  or operational metadata records.
- `ccld_complaints.hosted_app.audit_events` for local/test audit rows tied to
  successful reviewer-created state scaffold writes without mutating staged
  source-derived or reviewer-created records.
- `ccld_complaints.hosted_app.audit_coverage_plan` for local/test audit-read
  coverage planning over current and deferred audit categories without creating
  audit rows, persisting planning records, or mutating hosted scaffold tables.
- `ccld_complaints.hosted_app.audit_event_routes` for local/test authenticated
  JSON list and fetch access over those scaffold audit rows without mutating
  staged source-derived, reviewer-created, or audit records.
- `ccld_complaints.hosted_app.reset_reload_dry_run` for a local/test
  authenticated seeded corpus reset/reload dry-run route seam that reports
  future impact without mutating data and can optionally persist a non-secret
  planning metadata record when explicitly requested.
- `ccld_complaints.hosted_app.reset_reload_execution_plan` for a local/test
  authenticated seeded corpus reset/reload execution-plan route seam that turns
  dry-run summaries and planning metadata context into ordered bounded non-
  destructive action steps, with optional non-secret planning metadata
  persistence when explicitly requested.
- `ccld_complaints.hosted_app.reset_reload_planning_routes` for local/test
  authenticated JSON list and fetch access over persisted reset/reload planning
  metadata records without mutating data or executing reset/reload.
- `ccld_complaints.cli.import_hosted_seeded_corpus` as a minimal local command
  wrapper for operator-initiated test imports.

The migration environment reads the database URL from
`CCLD_HOSTED_TESTER_DATABASE_URL` only when migrations are explicitly run. Do not
commit connection strings, usernames, passwords, provider settings, private
URLs, hosted URLs, tokens, or deployment-specific configuration.

The seeded import artifact format is intentionally narrow and fixture-backed.
It carries import batch metadata, validation status, raw hash validation status,
record counts, warnings, errors, and normalized source-derived records shaped
like validated pipeline output. The importer stages source-derived records with
stable identities, original source-derived values, source URL, raw SHA-256,
raw path when available, connector metadata, retrieval timestamp, and import
batch linkage.

The source-derived read service is intentionally small. It lists staged records
and fetches a single staged record by source record key or by entity type plus
stable source-derived identity. Read models include original values,
source-traceability fields, and import batch context. They do not include review
status, annotations, corrections, tester feedback, export packet state, audit
events, or other reviewer-created state.

The auth boundary scaffold is also intentionally small. It validates only the
accepted provider class value `managed-oidc-oauth2` through
`CCLD_HOSTED_TESTER_AUTH_PROVIDER_CLASS`, defines local/test actor, role,
account-status, project/corpus scope, authorization target, and audit-context
models, and exposes guards for protected service seams. It rejects
unauthenticated actors, disabled or revoked actors, actors without the required
role permission, and actors outside the requested project or corpus scope. It
does not validate provider tokens, store sessions, create cookies, configure a
tenant, register an app, persist users or roles, or implement login/logout or
callback routes.

The source-derived HTTP/API route seam is intentionally small. It exposes
local/test JSON handlers for `/api/source-derived-records`,
`/api/source-derived-records/by-key`, and
`/api/source-derived-records/by-identity` only when the caller supplies an
explicit test route context with a database connection, authenticated actor or
unauthenticated test actor state, and seeded corpus scope. The handlers reuse
the protected read service, return source traceability and import batch context,
and reject unauthenticated, disabled or revoked, role-denied, out-of-scope,
invalid filter, invalid paging, and missing-record paths. They do not implement
production auth middleware, token parsing, cookies, sessions, reviewer-created
state, or a production API framework.

The reviewer workflow shell is intentionally small. It exposes local/test JSON
handlers for `/api/reviewer/source-derived-review/queue`,
`/api/reviewer/source-derived-review/detail`, and
`/api/reviewer/source-derived-review/detail/reviewer-note`, and
`/api/reviewer/source-derived-review/detail/reviewer-status` only when the caller
supplies an explicit workflow shell context backed by the source-derived route
context and the reviewer-created state route context. The shell consumes the
authenticated source-derived route seam, returns read-only queue and detail
payloads with source-derived record identity, original values, source
traceability, source document metadata, and import batch context, and can
compose associated reviewer-created state read route output plus a compact state
summary derived from that output for the selected source record on detail
responses. The note and status actions first resolve the selected source-derived
detail record, force the source-record binding from that resolved record, and
delegate to existing reviewer-created write routes and audit path. Source-
derived reads, associated reviewer-created state reads, note writes, and status
writes each enforce their own authenticated, active, role/scope-allowed access.
The shell does not create queue state, editable status transitions, full
annotations, corrections, tester feedback, export packet state, sessions,
cookies, production auth middleware, or a production API framework.

The reviewer-created state persistence scaffold is intentionally small. It can
create and read only local/test review-item-state scaffold rows after the caller
supplies an explicit database connection, authenticated actor context, and
seeded corpus scope. Writes require reviewer-state write permission, active
account status, matching scope, and an existing staged source-derived record key.
Rows are stored in a separate reviewer-created table with actor attribution and
do not overwrite source-derived records, original extracted values, raw source
metadata, import metadata, or source traceability. The scaffold does not
implement annotations, corrections, note/status editing/deletion, full review status workflows,
tester feedback, export packet decisions, sessions, cookies, production auth
middleware, or a production API framework. A narrow local/test reviewer note
creation route stores bounded non-secret note text as scaffold payload under the
existing state kind and reuses the existing write/audit path without changing the
schema. A narrow local/test reviewer status creation route stores bounded status
values as scaffold payload under the same state kind and reuses the same write/
audit path without changing the schema. Successful writes also create a separate local/test
audit event scaffold row with actor, permission, scope, action, target, and
source-derived context. If the audit row cannot be created, the reviewer-created
state write is rolled back.

The reviewer-created state read route seam is intentionally small. It exposes
local/test JSON handlers for `/api/reviewer-created-state` and
`/api/reviewer-created-state/by-id` only when the caller supplies an explicit
route context with a database connection, authenticated actor, and seeded corpus
scope. The handlers require reviewer-state read permission, support schema-
backed filters and bounded search over existing non-secret scaffold fields,
serialize non-secret scaffold fields, and reject
unauthenticated, disabled or revoked, role-denied, out-of-scope, invalid filter,
invalid paging, and missing-record paths. They do not create, update, delete,
execute, archive, clear, relink, reload, or otherwise mutate source-derived,
reviewer-created, audit, or operational metadata rows. Source-derived read
permission alone does not grant reviewer-created state read access.

The audit event persistence scaffold is intentionally small. It stores rows only
for successful reviewer-created state scaffold writes, using a separate audit
table linked to the reviewer-created scaffold target and source-derived context.
It does not store provider secrets, tokens, cookies, sessions, private headers,
connection strings, raw provider claims, or unnecessary sensitive narrative
content. The audit history route seam exposes local/test JSON handlers for
`/api/audit-events` and `/api/audit-events/by-id` only when the caller supplies
an explicit route context with a database connection, authenticated actor or
unauthenticated test actor state, and seeded corpus scope. The handlers require
audit-read permission, support schema-backed filters, serialize non-secret audit
fields, and reject unauthenticated, disabled or revoked, role-denied,
out-of-scope, invalid filter, invalid paging, and missing-event paths. They do
not mutate staged source-derived, reviewer-created, or audit rows. The scaffold
does not implement full audit policy coverage, production audit API framework,
audit UI, audit export, retention automation, or audit coverage for
reset/reload, exports, feedback, annotations, corrections, provider login, role
changes, or operational actions.

The reset/reload dry-run seam is intentionally small. It exposes the local/test
JSON handler `/api/operations/seeded-corpus-reset-reload/dry-run` only when the
caller supplies an explicit dry-run context with a database connection,
authenticated operator or admin-style actor, and seeded corpus scope. The
handler requires import/reload permission, reports existing import batch
metadata, source-derived record counts by entity, scoped reviewer-created
scaffold row counts, scoped audit scaffold row counts, future reviewer-created
state handling options, validation requirements, audit requirements, and deferred destructive actions. It performs
read-only inspection queries by default. When local/test code adds
`persist_planning_metadata=true`, it persists one separate operational planning
metadata record with actor attribution, permission used, scope, generated
timestamp, validation summary, impact summaries, and non-secret planning context.
The reset/reload execution-plan seam exposes the local/test JSON handler
`/api/operations/seeded-corpus-reset-reload/execution-plan` only when the caller
supplies an explicit local/test context with a database connection,
authenticated operator or admin-style actor, and seeded corpus scope. It reuses
the dry-run permission and scope checks, returns ordered bounded non-destructive
action steps, and can optionally persist an execution-plan artifact through the
same planning metadata table when local/test code adds
`persist_planning_metadata=true`.
The read-only planning metadata route seam exposes
`/api/operations/seeded-corpus-reset-reload/planning-metadata` and
`/api/operations/seeded-corpus-reset-reload/planning-metadata/by-id` only when
the caller supplies an explicit local/test context with a database connection,
authenticated operator or admin-style actor, and seeded corpus scope. The
handlers require import/reload permission, support schema-backed filters, return
non-secret planning metadata fields, and do not create, update, delete, execute,
archive, clear, relink, reload, schedule, or otherwise mutate data.
It does not delete, truncate, overwrite, archive, import, reload, create new
dry-run audit events, execute persisted metadata, run live crawling, execute
connectors, or implement a production API framework.

To run migrations or load a seeded corpus into a local PostgreSQL-compatible
test database, set `CCLD_HOSTED_TESTER_DATABASE_URL` outside the repository and
run Alembic before the import command:

```powershell
alembic upgrade head
```

```powershell
python -m ccld_complaints.cli.import_hosted_seeded_corpus tests\fixtures\hosted_seeded_corpus\validated_seeded_corpus.json
```

Do not commit connection strings, usernames, passwords, provider settings,
private URLs, hosted URLs, tokens, or deployment-specific configuration.

The current path does not implement stateful database-backed reviewer views, real
provider login, token validation, sessions, cookies, auth middleware, user or
role persistence, full reviewer-created workflows, full audit coverage, audit UI,
audit export, export builders, reset/reload execution, reviewer-created state archive or clear behavior, production import
automation, production API framework behavior, hosted live crawling, hosted
connector execution, QNAP, Azure, AWS, public hosting, public URLs, or
production deployment.

## Run the smoke check

The smoke check starts an in-process local scaffold server, checks the health
route and placeholder app shell, then stops the server:

```powershell
.\scripts\smoke-hosted-scaffold.ps1
```

The health route is also available on a running scaffold at:

```text
http://127.0.0.1:8000/health
```

## Run scaffold tests

Run the focused scaffold tests:

```powershell
pytest tests/unit/test_hosted_app_scaffold.py
```

Run the focused hosted schema/API scaffold tests:

```powershell
pytest tests/unit/test_hosted_schema_api_scaffold.py tests/unit/test_hosted_app_local_check.py
```

Run the focused hosted seeded import tests:

```powershell
pytest tests/unit/test_hosted_seeded_corpus_import.py
```

Run the focused hosted source-derived read tests:

```powershell
pytest tests/unit/test_hosted_source_derived_reads.py
```

Run the focused hosted auth boundary tests:

```powershell
pytest tests/unit/test_hosted_auth_boundary.py
```

Run the focused hosted auth provider integration planning tests:

```powershell
pytest tests/unit/test_hosted_auth_provider_integration_plan.py
```

Run the focused hosted audit coverage planning tests:

```powershell
pytest tests/unit/test_hosted_audit_coverage_plan.py
```

Run the focused hosted source-derived API route tests:

```powershell
pytest tests/unit/test_hosted_source_derived_routes.py
```

Run the focused hosted reviewer workflow shell tests:

```powershell
pytest tests/unit/test_hosted_reviewer_workflow_shell.py
```

Run the focused hosted reset/reload dry-run tests:

```powershell
pytest tests/unit/test_hosted_reset_reload_dry_run.py
```

Run the focused hosted reset/reload execution-plan tests:

```powershell
pytest tests/unit/test_hosted_reset_reload_execution_plan.py
```

Run the focused hosted reset/reload operational metadata tests:

```powershell
pytest tests/unit/test_hosted_reset_reload_operational_metadata.py
```

Run the focused hosted reset/reload planning metadata route tests:

```powershell
pytest tests/unit/test_hosted_reset_reload_planning_routes.py
```

Run the focused hosted reviewer-created state scaffold tests:

```powershell
pytest tests/unit/test_hosted_reviewer_created_state.py
```

Run the focused hosted reviewer-created state route tests:

```powershell
pytest tests/unit/test_hosted_reviewer_created_state_routes.py
```

Run the focused hosted audit event scaffold tests:

```powershell
pytest tests/unit/test_hosted_audit_events.py
```

Run the focused hosted audit history route tests:

```powershell
pytest tests/unit/test_hosted_audit_event_routes.py
```

These tests include local-only semantic/accessibility validation for the sample
source view shell and facility master sample view. They use Python standard-library HTML parsing
to verify one page-level heading, meaningful page titles, semantic main content,
navigation links, fixture/sample caution text, read-only labels, accessible
filter labels, sample no-match behavior, source traceability summary panels,
source-derived versus reviewer-created state separation, visible
source-traceability-style fields, manifest-backed facility fixture metadata,
fixture-only source coverage indicators, and related fixture/sample source
context links.
The schema/API scaffold tests verify safe database configuration validation,
redacted connection summaries, required ADR-0010 persistence boundaries, source-
derived versus reviewer-created state API separation, and that the only enabled
domain behavior is the controlled seeded source-derived import path.
The seeded import tests verify the tiny validated artifact shape, import batch
identity, source traceability preservation, stable source-derived identity,
idempotent staging, and no reviewer-created state writes.
The source-derived read tests verify database-backed list and fetch behavior,
import batch context, source traceability preservation, stable identity lookup,
and no reviewer-created state exposure.
The auth boundary tests verify safe provider-class configuration validation,
authenticated actor context, audit-ready authorization decisions, protected
source-derived read helpers, disabled-account rejection, role-denied rejection,
out-of-scope rejection, and that source-derived read access alone does not imply
reviewer-created state read, reviewer-created state write, import/reload, or
user-administration permissions.
The auth provider integration planning tests verify accepted provider-class
planning, unsupported provider-class rejection, required non-secret readiness
inputs, secret-like input and real URL rejection without echoing values,
user-role-admin permission and scope checks, deterministic plan ordering, no
persistence, and before/after row counts proving existing hosted scaffold tables
are not mutated.
The audit coverage planning tests verify local/test audit-read planning over
current and deferred audit categories, unauthenticated, disabled or revoked,
role-denied, and out-of-scope rejections, deterministic ordering, non-secret
payloads, no audit row creation, no persistence, and before/after row counts
proving existing hosted scaffold tables are not mutated.
The source-derived API route tests verify local/test JSON list and fetch
handlers, source traceability and import batch serialization, entity filtering,
paging, missing-record responses, explicit route-context requirements, and
unauthenticated, disabled or revoked, role-denied, and out-of-scope rejections.
The reviewer workflow shell tests verify local/test authenticated queue and
detail payloads over the source-derived route seam, associated reviewer-created
state read route output for selected detail responses, derived associated-state
summary fields for empty, one-row, and multiple-row states, associated-state
filter/search pass-through, empty associated state, empty queue behavior,
missing-detail behavior, explicit workflow context requirements, source
traceability preservation, import batch context, source-derived read versus
reviewer-state read permission separation, non-secret associated state payloads,
and unauthenticated, disabled or revoked, role-denied, out-of-scope, and
read no-mutation behavior. They also verify reviewer note creation through the
workflow shell action, forced source-record binding from the selected detail
context, invalid source or note payload rejection, audit creation on success,
no audit/state mutation on failure, read-after-write visibility, and no source-
derived mutation.
The reviewer-created state scaffold tests verify separate storage from staged
source-derived records, source-derived records are not modified, authenticated
actor attribution is captured, reviewer-state write permission is required,
disabled or revoked, role-denied, out-of-scope, and invalid source-derived
reference writes are rejected, and scoped readback works where implemented.
The reviewer-created state route tests verify local/test authenticated list and
fetch handlers over persisted scaffold rows, schema-backed filters, bounded
search success and empty search results, empty list, missing-record responses,
explicit route-context requirements, unauthenticated, disabled or revoked,
role-denied, and out-of-scope rejections, source-derived read permission
separation, note creation with reviewer-state write permission, invalid note
payload and missing source rejection, read-after-write visibility, successful
note audit event creation, non-secret JSON payloads, and before/after row counts
proving reads do not mutate seeded import, reviewer-created scaffold, audit
scaffold, or operational planning metadata tables.
The audit event scaffold tests verify that successful reviewer-created state
scaffold writes, including reviewer note writes, create separate audit rows with
actor attribution and target context, failed writes do not create successful audit rows, audit persistence
failure rolls back the reviewer-created state write, source-derived rows remain
unchanged, reviewer-created rows are not modified by audit persistence, audit
read permission is required, and secret-like values are not stored in audit
context metadata.
The audit history route tests verify local/test authenticated list and fetch
handlers over scaffold audit rows, schema-backed filters, empty history,
missing-event responses, explicit route-context requirements, unauthenticated,
disabled or revoked, role-denied, and out-of-scope rejections, non-secret JSON
payloads, and before/after row counts proving reads do not mutate seeded import,
reviewer-created scaffold, or audit scaffold tables.
The reset/reload dry-run tests verify local/test authenticated planning payloads,
seeded import batch, source-derived record, reviewer-created scaffold, and audit
scaffold impact counts, reviewer-created state handling options, invalid mode rejection,
explicit dry-run context requirements, unauthenticated, disabled or revoked,
role-denied, and out-of-scope rejections, and before/after row counts proving
the dry-run does not mutate seeded import, reviewer-created scaffold, or audit
scaffold tables.
The reset/reload operational metadata tests verify explicitly requested planning
metadata persistence, scoped readback, non-secret planning context, invalid
option rejection, unauthenticated, disabled or revoked, role-denied, and out-of-
scope rejection, and before/after row counts proving persisted planning metadata
does not mutate seeded import, reviewer-created scaffold, or audit scaffold
tables or execute reset/reload.
The reset/reload execution-plan tests verify authenticated success,
unauthenticated, disabled or revoked, role-denied, and out-of-scope rejections,
invalid requested mode and reviewer-state handling option rejection, default
non-persistence, optional planning metadata persistence, deterministic action-
plan ordering, and before/after row counts proving execution-plan creation does
not mutate seeded import, source-derived, reviewer-created, audit, or
operational metadata tables except for the explicitly requested planning
metadata row.
The reset/reload planning metadata route tests verify local/test authenticated
list and fetch handlers over persisted planning rows, schema-backed filters,
empty history, missing-record responses, explicit route-context requirements,
unauthenticated, disabled or revoked, role-denied, and out-of-scope rejections,
non-secret JSON payloads, and before/after row counts proving reads do not
mutate seeded import, reviewer-created scaffold, audit scaffold, or operational
planning metadata tables.
They do not require browser automation, Node.js, Playwright, Selenium, axe,
Docker, a running PostgreSQL server, cloud services, or public URLs.

Run the standard project validation before opening a PR:

```powershell
.\scripts\check-hosted-scaffold-local.ps1
```

```powershell
.\scripts\lint.ps1
```

```powershell
.\scripts\test.ps1
```

```powershell
.\scripts\docs.ps1
```

```powershell
git diff --check
```

## Intentionally not implemented

The scaffold intentionally does not implement:

- Real authentication.
- Real provider token validation, sessions, cookies, or auth middleware.
- Real provider registration, callback handling, hosted URLs, or persisted auth
  configuration.
- Persistent authorization, user, role, invitation, or scope storage.
- Production schema beyond the seeded import table group, the narrow
  reviewer-created state scaffold table, the narrow audit event scaffold table,
  and the narrow reset/reload planning metadata scaffold table.
- Full reviewer-created workflow, full audit coverage, audit UI, audit export,
  export, feedback, auth, or
  reset/reload execution tables beyond the narrow planning metadata scaffold.
- HTTP API routes outside the narrow local/test source-derived read route seam,
  reviewer workflow shell queue/detail/note-action seam, reviewer-created state
  read route seam, reset/reload dry-run seam, reset/reload execution-plan seam,
  audit history read route seam, and reset/reload planning metadata read route seam.
- Stateful database-backed reviewer views or workflows.
- Production import/sync automation.
- Queues.
- Annotations.
- Corrections.
- Exports.
- Tester feedback.
- Audit trail beyond successful reviewer-created state scaffold writes.
- Reset/reload execution.
- Hosted live crawling.
- Hosted connector execution.
- Full reviewer-created state workflow persistence.
- Source-derived canonical field changes.
- Extraction behavior changes.
- QNAP, Azure, AWS, public hosting, public URLs, or production deployment.

The sample source-derived view shell is also local-only and read-only. It is not
an import workflow, a database-backed source record route, a queue, a correction
workflow, or a reviewer-created state surface. Database-backed source-derived
reads are limited to the local/test service seam over staged seeded corpus
records.

The sample facility master view is also local-only and read-only. It is not a
CSV import, source connector, database-backed facility search, official facility
master, reviewer queue, correction workflow, or reviewer-created state surface.
Its source coverage panel is a fixture-only display pattern, not evidence of
live public-source coverage, source completeness, import status, or legal or
facility-wide conclusions.

Those layers remain deferred to later ADRs or implementation PRs with focused
validation for the affected boundary.

## Tooling impact

The hosted app shell still uses Python standard-library HTTP server primitives.
The PostgreSQL/Alembic wiring follows ADR-0015 for the hosted tester persistence
target and migration tool direction, but it is only scaffold wiring for local
and test validation. It is not a final production frontend framework, API
framework, concrete auth provider instance, hosting platform, deployment
pipeline, cloud database plan, backup policy, or retention automation decision.