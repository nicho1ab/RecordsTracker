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
