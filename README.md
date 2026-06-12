# CCLD Complaints Data POC

This repository is the active CCLD complaints proof of concept for ingesting,
preserving, extracting, validating, and locally reviewing public complaint and
facility report records from the California Community Care Licensing Division
public portal.

The project uses Python connectors, preserved raw source files, SQLite, and
Datasette to support local review without building a custom frontend during the
proof of concept.

## What This Project Does

- Discovers CCLD public facility report records for explicitly provided facility
   numbers.
- Preserves raw public source files before extraction.
- Stores normalized facility, source document, complaint, allegation, event, and
   extraction audit records in SQLite.
- Presents review views and saved query examples in Datasette for browsing,
   filtering, source checking, and CSV export.
- Exports a local review bundle with complaint review, delay triage, and source
   traceability CSV files.
- Preserves source traceability through source URL, raw SHA-256 hash, raw path,
   connector name, connector version, retrieval timestamp, and report index when
   available.
- Uses fixture-backed tests to protect deterministic extraction and local review
   behavior from regressions.
- Supports a controlled live fetch workflow that is explicitly user-invoked,
   rate-limited by script options, and scoped to provided facility numbers.

## Core Principles

- The public portal remains the source of record.
- Extracted records are a derived review aid and may contain extraction errors.
- Delay review flags are screening aids, not conclusions that an investigation
   was delayed.
- Source traceability and raw source preservation must not be removed.
- User-facing docs, exports, and presentation layers must follow the project
   accessibility requirements.
- The baseline workflow avoids optional paid platform dependencies.

## Local Review Flow

After setup, populate a sample database:

```powershell
.\scripts\run-ccld-sample.ps1
```

The script prints the SQLite database path, the generated Datasette metadata
path, and the Datasette command to open. Start with these Datasette views:

1. `complaint_review_summary`
2. `facility_complaint_summary`
3. `delay_review_flags`
4. `source_traceability_review`

For live public data, use the controlled live fetch script with explicit facility
numbers and request limits:

```powershell
.\scripts\run-ccld-live-fetch.ps1 -FacilityNumber 157806098 -Limit 5 -MaxRequests 10
```

Downloaded live raw files are saved under the ignored local `data/raw` path by
default. Treat public complaint narratives carefully because they may contain
sensitive details even when publicly available.

To export source-traceable CSV review outputs after populating the database:

```powershell
.\scripts\export-review-bundle.ps1
```

## Documentation

- Start with [docs/user/getting-started.md](docs/user/getting-started.md) for
   setup and local review.
- Use [docs/user/local-review-workflow.md](docs/user/local-review-workflow.md)
   for the guided Datasette review workflow.
- Use [docs/developer/setup.md](docs/developer/setup.md) and
   [docs/developer/copilot-workflow.md](docs/developer/copilot-workflow.md) before
   making code changes.
- Review [DATA_CONTRACT.md](DATA_CONTRACT.md),
   [SOURCE_CONNECTOR_CONTRACT.md](SOURCE_CONNECTOR_CONTRACT.md), and
   [DOCUMENTATION_STRATEGY.md](DOCUMENTATION_STRATEGY.md) before changing schemas,
   connectors, workflows, or user-facing behavior.

## Validation

Run the standard checks before completing changes:

```powershell
.\scripts\lint.ps1
.\scripts\test.ps1
.\scripts\docs.ps1
```
