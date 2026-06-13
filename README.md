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
- Exports a local review bundle with complaint review, delay triage, source
   traceability, multi-facility traceability, and comparison CSV files.
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
path, the Datasette command to open, and grouped next steps. Start with
`review_home`, `complaint_review_start_here`, or `complaint_first_pass_review`;
use `public_record_allegation_search` for cautious keyword discovery over
source-derived allegation text, categories, and findings; use
`complaint_timeline_review` for complaint milestone dates and extracted event
dates; use `delay_review_flags` for delay triage; use
`facility_pattern_review` for facility-level pattern comparison over the derived
dataset; use `facility_comparison_review` for facility/category/finding rows
with source-document counts and cautious comparison notes; use
`source_traceability_review`, `multi_facility_source_traceability_review`, and
`field_source_traceability_review` for source verification; and use
`complaint_review_export_with_traceability` or `export-review-bundle.ps1` for
source-traceable CSV export.

For live public data, use the controlled live fetch script with explicit facility
numbers and request limits:

```powershell
.\scripts\run-ccld-live-fetch.ps1 -FacilityNumber 157806098 -Limit 5 -MaxRequests 10
```

The live fetch command prints a summary of facilities requested, report
candidates discovered, selected, skipped by limit, fetched, written, and failed
so reviewers can see the run outcome before opening logs or Datasette. The
summary distinguishes facilities with records discovered, facilities with no
records discovered, and discovery failures. It also prints facility identifier
intake feedback, including accepted identifiers, duplicates ignored, and ignored
blank, comment, or header values. It then prints the same grouped next steps for
what to open first, delay triage, source verification, and CSV export.

Downloaded live raw files are saved under the ignored local `data/raw` path by
default. Treat public complaint narratives carefully because they may contain
sensitive details even when publicly available.

To export source-traceable CSV review outputs after populating the database:

```powershell
.\scripts\export-review-bundle.ps1
```

The review bundle writes complaint review, delay triage, source traceability,
multi-facility source traceability, complaint timeline, field traceability,
facility pattern, and facility comparison CSV files plus a README with cautious
public-record review notes.

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
