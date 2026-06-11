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

The CCLD connector includes `ingest_facility_reports_for_facility()` for the initial single-facility workflow. It discovers report candidates and runs each available report through fetch or fixture load, raw storage for live fetches, extraction, normalization, validation, and emit. The current emit step keeps validated records in memory; SQLite persistence remains a later architecture step.

In tests, report content must be loaded through injected fixture loaders. Tests must not make live CCLD web requests.
