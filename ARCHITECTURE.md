# Architecture

## Initial design

```text
Public source portal/API
   -> connector discovery
   -> raw fetcher
   -> raw file storage
   -> extractor
   -> normalizer
   -> contract validator
   -> SQLite database
   -> Datasette presentation layer
```

## Components

### Connectors

Connectors are source-specific modules responsible for discovering, fetching, and extracting data from one public data source.

### Raw source storage

Raw source files are stored in ordinary file storage under `data/raw/`. Each file must have a stable name, source URL, retrieval timestamp, and SHA-256 hash.

### Structured storage

SQLite is the initial database. PostgreSQL may be introduced later if concurrency, multi-user editing, or dashboarding requires it.

### Presentation

Datasette is the initial browser/search/API interface because it can expose SQLite data quickly without creating a custom application.

### Future review UI

Baserow may be added later if non-technical users need spreadsheet-like correction and review workflows.

## Boundaries

- The repository owns ingestion, extraction, validation, storage, documentation, and tests.
- The public portal remains the public source of record.
- Raw storage is evidence for reproducibility and regression testing, not a replacement for the public portal.

## Accessibility

Any user-facing output must meet the accessibility requirements in `ACCESSIBILITY_REQUIREMENTS.md`. Datasette templates/plugins or future UI layers must be evaluated before use.
