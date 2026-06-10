# Source Connector Contract

## Purpose

This contract allows the project to scale across future public data sources with different structures.

## Required connector functions

Each connector must implement:

```text
discover()
fetch()
store_raw()
extract()
normalize()
validate()
emit()
```

## Required behavior

- Discover source documents without relying on browser-only manual steps when an API or stable public endpoint is available.
- Fetch raw source content and store it before extraction.
- Compute a SHA-256 hash for every raw source file.
- Extract fields deterministically when reliable patterns exist.
- Normalize records into the canonical data contract.
- Validate output against JSON schemas.
- Emit extraction audit records.
- Include source-specific known limitations.
- Include at least three representative fixtures before production use.

## Forbidden behavior

- Do not create source-specific columns in canonical tables without an approved data contract change.
- Do not overwrite raw files without preserving hashes or retrieval history.
- Do not hide extraction failures.
- Do not use LLMs for fields that can be parsed deterministically.
- Do not bypass accessibility requirements in user-facing output.

## Connector documentation

Each connector must include:

```text
src/connectors/<source>/README.md
src/connectors/<source>/known-limitations.md
tests/fixtures/<source>/README.md
```
