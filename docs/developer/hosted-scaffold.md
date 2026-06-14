# Hosted Scaffold

## Purpose

This document explains how to run the first local hosted tester MVP scaffold.
The scaffold is a runnable placeholder app shell and smoke route only. It is not
a functioning reviewer workflow.

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
import command. No cloud resources, public URLs, app registrations, cloud
databases, DNS records, deployment credentials, secrets, or tokens are required.

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
itself as a scaffold and not a functioning reviewer workflow. It must not imply
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
and no-database, no-import, no-authentication, no-deployment boundary.
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
import/sync, authenticate users, persist reviewer-created state, or prove source
completeness, statewide coverage, official facility status, or legal or
facility-wide conclusions.

## PostgreSQL and Alembic seeded import wiring

The repository now includes minimal PostgreSQL/Alembic project wiring and a
controlled seeded corpus import path for hosted tester MVP persistence. The
wiring includes:

- `alembic.ini` with an empty committed database URL setting.
- `migrations/` as the Alembic script location.
- `migrations/versions/20260613_0001_seeded_corpus_import.py` with import batch
  metadata and source-derived record staging tables only.
- `ccld_complaints.hosted_app.persistence` for no-secret database URL validation
  and ADR-0010 persistence boundary descriptors.
- `ccld_complaints.hosted_app.schema_api_scaffold` for scaffold-only source-
  derived and reviewer-created state API boundary descriptors.
- `ccld_complaints.hosted_app.seeded_import` for loading a controlled validated
  JSON artifact into the seeded import tables.
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

The current path does not implement database-backed API routes, database-backed
review views, authentication, authorization, reviewer-created state persistence,
reviewer workflows, audit persistence, export builders, reset/reload behavior,
production import automation, hosted live crawling, hosted connector execution,
QNAP, Azure, AWS, public hosting, public URLs, or production deployment.

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
- Authorization.
- Production schema beyond the seeded import table group.
- Reviewer-created state, audit, export, feedback, auth, or reset/reload tables.
- Database-backed reads or API routes.
- Production import/sync automation.
- Queues.
- Annotations.
- Corrections.
- Exports.
- Tester feedback.
- Audit trail.
- Reset/reload.
- Hosted live crawling.
- Hosted connector execution.
- Reviewer-created state persistence.
- Source-derived canonical field changes.
- Extraction behavior changes.
- QNAP, Azure, AWS, public hosting, public URLs, or production deployment.

The sample source-derived view shell is also local-only and read-only. It is not
an import workflow, a database-backed source record view, a queue, a correction
workflow, or a reviewer-created state surface.

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