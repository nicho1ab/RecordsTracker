# Developer Architecture

See root `ARCHITECTURE.md` for the canonical architecture.

## Package layout

```text
src/ccld_complaints/
  cli/
  connectors/
  extraction/
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
8. Present through Datasette.

## Current ingestion boundary

The CCLD connector includes `ingest_facility_reports_for_facility()` for the initial single-facility workflow. It discovers report candidates and runs each available report through fetch or fixture load, raw storage for live fetches, extraction, normalization, validation, and emit.

When the CCLD connector is initialized with a SQLite database path, the emit step writes normalized facility, source document, complaint, allegation, event, and extraction audit records to the existing SQLite schema. Writes are idempotent upserts keyed by the canonical record identifiers, so rerunning the same ingestion updates existing rows rather than duplicating them.

In tests, report content must be loaded through injected fixture loaders. Tests must not make live CCLD web requests.
