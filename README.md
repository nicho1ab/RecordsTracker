# CCLD Complaints Data

This repository supports governed ingestion, preservation, extraction,
validation, local review, and production-discovery for public complaint and
facility report records from the California Community Care Licensing Division
public portal.

The initial proof of concept proved Python connectors, preserved raw source
files, SQLite storage, Datasette local review, and source-traceable exports. The
current phase is production-discovery for a source-traceable public-record review
solution. Datasette is retained as a validation, inspection, debugging, local
exploration, and export-support layer, not as the primary future review
experience.

## What This Project Does

- Discovers CCLD public facility report records for explicitly provided facility
   numbers.
- Preserves raw public source files before extraction.
- Stores normalized facility, source document, complaint, allegation, event, and
   extraction audit records in SQLite.
- Presents retained review views and saved query examples in Datasette for local
   browsing, filtering, source checking, validation, inspection, and CSV export.
- Exports a local review bundle with complaint review, delay triage, source
   traceability, multi-facility traceability, and comparison CSV files.
- Preserves source traceability through source URL, raw SHA-256 hash, raw path,
   connector name, connector version, retrieval timestamp, and report index when
   available.
- Uses fixture-backed tests to protect deterministic extraction and local review
   behavior from regressions.
- Includes a small fixture-backed multi-facility corpus for offline tests of
   intake diagnostics, fetch summaries, traceability views, comparison views,
   and review-bundle exports without live public requests.
- Supports a controlled live fetch workflow that is explicitly user-invoked,
   rate-limited by script options, and scoped to provided facility numbers.

## Core Principles

- The public portal remains the source of record.
- Extracted records are a derived review aid and may contain extraction errors.
- Delay review flags are screening aids, not conclusions that an investigation
   was delayed.
- Source traceability and raw source preservation must not be removed.
- Datasette remains useful for validation, inspection, debugging, local
   exploration, and export support, but production-discovery will define the
   future primary reviewer UX.
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

The developer test suite also includes a small two-facility fixture corpus that
uses tracked source-shaped fixtures only. It is an offline regression aid for the
multi-facility review paths, not an official or complete facility comparison.

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

To profile ignored local public-source CSV examples before any source expansion
implementation is proposed, run:

```powershell
.\scripts\profile-public-source-csvs.ps1
```

The profiler reads CSV files from `data\raw\source-profiling`, skips non-CSV
files, and writes ignored local summaries under `data\processed\source-profiling`
and `data\logs\source-profiling.log`. It does not import data, modify raw files,
create canonical fields, approve schemas or migrations, add connectors, or load
anything into the hosted scaffold.

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
- Review [PRODUCTION_DISCOVERY_REQUIREMENTS.md](PRODUCTION_DISCOVERY_REQUIREMENTS.md)
   before planning hosted reviewer app requirements, architecture ADRs, tester
   MVP workflows, review state, annotations, corrections, or export packet state.
- Review [GOVERNANCE_INVENTORY.md](GOVERNANCE_INVENTORY.md) for the current
   production-discovery phase, hosted scaffold status, completed ADR decisions,
   remaining deferred decisions, stale-guidance assessment, and next-phase gap
   analysis.
- Review [PUBLIC_SOURCE_DATA_INVENTORY.md](PUBLIC_SOURCE_DATA_INVENTORY.md)
   before planning public-source expansion, uploaded CSV profiling,
   multi-source adapters, attorney focus areas, or feedback intake paths.
- Use [docs/developer/hosted-scaffold.md](docs/developer/hosted-scaffold.md) to
   run the local hosted tester MVP scaffold. The scaffold is a placeholder app
   shell with a controlled seeded corpus import path for validated local
   pipeline-output artifacts and a local/test database-backed read service for
   staged source-derived records. It also includes a local/test auth boundary
   scaffold for actor, role, scope, and account-status guards plus a narrow
   local/test authenticated source-derived read API route seam and read-only
   reviewer workflow shell that can include associated reviewer-created state
   read route output on selected detail responses. It also includes a narrow local/test reviewer-
   created state persistence scaffold table/service, a narrow local/test audit
   event scaffold for successful reviewer-created state scaffold writes only, a
   narrow local/test authenticated audit history read route seam for those audit
   rows, a narrow local/test authenticated reviewer-created state read route
   seam for listing or fetching persisted scaffold rows, and a local/test
   authenticated reset/reload dry-run route seam that reports
   what a future seeded corpus reset/reload would affect and can optionally
   persist a separate operational planning metadata record when explicitly
   requested by local/test code, plus a narrow local/test read-only route seam
   for listing or fetching those persisted planning records. It does not
   implement real login flow, auth middleware, full reviewer workflows,
   annotations, corrections, review status UI, production import automation,
   full audit coverage, audit UI, audit export, reset/reload execution, exports,
   deployment, QNAP, Azure, or AWS.
   Start with `scripts/check-hosted-scaffold-local.ps1` to verify local Python
   and development-tool prerequisites without installing software or requiring
   admin rights.
   The local `/source-records` route shows fixture/sample source-derived records
   only, with local sample filtering/search controls, sample
   source-traceability summary panels, sample traceability-style fields, and no
   live data, database-backed reads, real login flow, or reviewer-created state
   persistence. Database-backed service reads, auth boundary guards, the
   source-derived API route seam, and the read-only reviewer workflow shell are
   limited to local/test seams and are not wired into the sample UI routes.
   Workflow shell detail payloads can compose associated reviewer-created state
   read output only when tests or local callers provide explicit source-derived
   and reviewer-created state route contexts.
   The reset/reload dry-run seam is also local/test only and requires an
   explicit database, actor, and scope context from tests or local callers. Its
   operational metadata scaffold stores dry-run planning metadata only, requires
   import/reload permission, rejects unauthenticated, disabled or revoked,
   role-denied, and out-of-scope actors, supports read-only list/fetch routes
   over those planning records, and does not execute reset/reload. The
   reviewer-created state scaffold is also local/test only, requires explicit
   authenticated actor context and reviewer-state write permission for writes,
   and stores scaffold rows separately from source-derived records. The audit
   event scaffold is also local/test only and records successful reviewer-
   created state scaffold writes separately from both source-derived and
   reviewer-created rows. The audit history read seam is local/test only,
   requires explicit database, actor, and scope context plus audit-read
   permission, and returns non-secret audit row fields without mutating source-
   derived, reviewer-created, or audit rows.
   The reviewer-created state read seam is local/test only, requires explicit
   database, actor, and scope context plus reviewer-state read permission, and
   returns non-secret scaffold row fields without mutating source-derived,
   reviewer-created, audit, or operational metadata rows.
   Source-derived read access alone does not grant workflow-shell access to
   associated reviewer-created state context.
   The local `/facilities` route shows a read-only facility master
   sample view backed only by committed tiny public-source facility fixtures and
   manifest placeholder metadata. Facility detail pages include fixture-only
   source coverage indicators and related fixture/sample source-record links
   where the local sample mapping exists; they do not read ignored raw CSVs,
   generated profiling outputs, SQLite, a hosted database, or live
   public-source data.

## Validation

Run the standard checks before completing changes:

```powershell
.\scripts\lint.ps1
.\scripts\test.ps1
.\scripts\docs.ps1
```
