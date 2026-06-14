# Developer Architecture

See root `ARCHITECTURE.md` for the canonical architecture.

## Package layout

```text
src/ccld_complaints/
  cli/
  connectors/
  extraction/
  hosted_app/
  storage/
  quality/
  utils/
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
  and architecture decisions.
10. Run the local hosted tester MVP scaffold only as a placeholder app shell and
  smoke route until later implementation PRs add approved hosted behavior.

## Hosted scaffold boundary

The first hosted tester MVP scaffold is a local-first Python standard-library
HTTP app shell. It provides a placeholder page and health route for smoke
validation on a Windows development workstation. Its local setup check verifies
Python and development-tool prerequisites without installing software, requiring
admin rights, or requiring Node, Docker, QNAP, Azure, AWS, cloud resources, or a
public URL.

The scaffold also includes a local-only read-only source-derived view shell over
fixture/sample records. This view is an app-facing placeholder for source record
list and detail navigation only. It does not read from SQLite or a hosted
database, run import/sync, load live public-source data, authenticate users, or
persist reviewer-created state.

The scaffold does not implement authentication, authorization, production
schema, migrations, import/sync, queues, annotations, corrections, exports,
tester feedback, audit trail, reset/reload, hosted live crawling, hosted
connector execution, deployment, source-derived canonical field changes,
reviewer-created state persistence, or extraction behavior. It does not require
Docker, QNAP Container Station, Azure, AWS, a public URL, secrets, or cloud
resources.

See `docs/developer/hosted-scaffold.md` for local run and smoke-check commands.

## Current ingestion boundary

The CCLD connector includes `ingest_facility_reports_for_facility()` for the initial single-facility workflow. It discovers report candidates and runs each available report through fetch or fixture load, raw storage for live fetches, extraction, normalization, validation, and emit.

When the CCLD connector is initialized with a SQLite database path, the emit step writes normalized facility, source document, complaint, allegation, event, and extraction audit records to the existing SQLite schema. Writes are idempotent upserts keyed by the canonical record identifiers, so rerunning the same ingestion updates existing rows rather than duplicating them.

In tests, report content must be loaded through injected fixture loaders. Tests must not make live CCLD web requests.
