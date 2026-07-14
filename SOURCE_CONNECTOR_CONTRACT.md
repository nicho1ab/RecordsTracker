# Source Connector Contract

## Purpose

This contract allows the project to scale across future public data sources with different structures.

Before implementing a new connector, add or update a source inventory entry in
`PUBLIC_SOURCE_DATA_INVENTORY.md`. The inventory entry should describe source
type, jurisdiction, agency, topic or domain, retrieval method, update cadence
when known, parser profile, traceability fields, caution and limitation
language, allowed use, and review status. Inventory entries are planning
artifacts only; they do not approve connector implementation, imports, schemas,
canonical fields, hosted workflows, or legal conclusions.

## Required connector functions

Document/report connectors must implement:

```text
discover()
fetch()
store_raw()
extract()
normalize()
validate()
emit()
```

Structured open-data CSV source loaders may use a narrower deterministic
download/profile/validate path when the source is an authoritative public
reference CSV rather than an individual report artifact. Loader planning must
still be recorded in `PUBLIC_SOURCE_DATA_INVENTORY.md`, and implementation still
requires a later approved task before adding download code, import code,
schemas, migrations, hosted behavior, or canonical fields.

## Required behavior

- Discover source documents without relying on browser-only manual steps when an API or stable public endpoint is available.
- Fetch raw report/document source content and store it before extraction.
- Compute a SHA-256 hash for every raw report/document source file.
- For authoritative structured public CSV facility resources, deterministically
  download or resolve the resource, profile and validate the CSV shape, preserve
  source metadata, and treat raw SHA-256 as optional diagnostic metadata rather
  than a required product/data-contract field.
- Extract fields deterministically when reliable patterns exist.
- For CCLD complaint reports, preserve the source `FACILITY TYPE` value,
  including an explicit numeric source code, as complaint-report facility-type
  evidence. Do not substitute an unrelated program or CHHS numeric type field.
- A valid structured CCLD `VISIT DATE` is eligible deterministic investigation-
  activity evidence. When narrative activity evidence also exists, use the
  earliest valid date and retain the selected evidence. Report date alone must
  not establish first investigation activity.
- Normalize records into the canonical data contract.
- Validate output against JSON schemas.
- Emit extraction audit records.
- Include source-specific known limitations.
- Include at least three representative fixtures before production use.

## Forbidden behavior

- Do not create source-specific columns in canonical tables without an approved data contract change.
- Do not overwrite raw files without preserving hashes or retrieval history.
- Do not weaken raw artifact preservation or hash requirements for
  complaint/report connectors when adding structured CSV facility loaders.
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
