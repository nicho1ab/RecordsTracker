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
- Builds a local/test CCLD-only hosted seeded-corpus JSON artifact from
   validated CCLD SQLite output so `/ccld/records/request` can load or refresh
   those source-derived records through the existing local validated path.
- Includes a local/test hosted CCLD record request page where a tester can enter
   a CCLD facility/license number and optional date range, read matching seeded
   source-derived records, load or refresh matching CCLD records from validated
   local/test hosted seeded-corpus output, confirm lookup-selected or manually
   entered request context with active facility reference source, review a guided
   facility/date-scoped complaint queue with triage summaries, progress counts, reviewer note/status
   cues, source-traceability availability cues, reviewer-status filtering,
   suggested next-record links, skip-to-main links, visible first-run next-step
   guidance, clearer form/action text, open records in the hosted reviewer UI,
   see clearer note/status save confirmations, return to see updated progress
   after notes/statuses, and read first-time workflow help without running live
   crawling from a browser request.

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

After validating CCLD SQLite output, build a local/test hosted seeded-corpus
JSON artifact outside the browser:

```powershell
.\scripts\build-hosted-ccld-artifact.ps1 -DbPath data\processed\ccld.sqlite -FacilityNumber 157806098 -Overwrite
```

The artifact is written to
`data/processed/hosted_seeded_corpus/validated_ccld_seeded_corpus.json` by
default. When the local hosted scaffold is running, `/ccld/records/request` can
then load or refresh matching CCLD rows from that validated JSON through the
existing local/test import/reload path. The builder does not run live public web
requests or browser-triggered connector execution.

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
   analysis. It also defines the deferred-readiness/product-benefit gate used to
   decide whether future backend readiness, hardening, planning, or checklist
   work should happen now or remain deferred behind user-facing CCLD MVP value.
- Review [PUBLIC_SOURCE_DATA_INVENTORY.md](PUBLIC_SOURCE_DATA_INVENTORY.md)
   before planning public-source expansion, uploaded CSV profiling,
   multi-source adapters, attorney focus areas, or feedback intake paths.
- Use [docs/developer/hosted-scaffold.md](docs/developer/hosted-scaffold.md) to
   run the local hosted tester MVP scaffold. The scaffold is a placeholder app
   shell with a controlled seeded corpus import path for validated local
   pipeline-output artifacts and a local/test database-backed read service for
   staged source-derived records. It also includes a local/test auth boundary
   scaffold for actor, role, scope, and account-status guards, a narrow
   local/test auth provider integration planning route for non-secret managed
   OpenID Connect/OAuth 2.0 readiness planning, plus a narrow
   local/test authenticated source-derived read API route seam and reviewer
   workflow shell with read-only queue/detail payloads, associated reviewer-
   created state read route output, a compact summary derived from that output
   on selected detail responses, and narrow local/test note/status actions that
   delegate to existing reviewer-created write routes after resolving the
   selected source record. A browser-accessible local/test CCLD facility lookup
   page is available at `/ccld/facilities` when the scaffold is running locally;
   it searches a full local/test CCLD facility reference CSV when configured via
   `CCLD_FACILITY_REFERENCE_CSV` or present at ignored path
   `data/raw/ccld/facility-reference.csv`, otherwise it falls back to the
   committed tiny fixture CSV. Search fields include facility/license number,
   facility name, city, county, ZIP code, facility type, and status. The page
   shows which reference source is active and carries the selected
   facility/license number and lookup-origin context into `/ccld/records/request`.
   A browser-accessible local/test CCLD record request page is available at
   `/ccld/records/request`; it still accepts manual facility/license entry plus
   an optional date range, displays whether the request came from lookup or
   manual entry, shows the active local/test facility reference source, reads
   existing seeded source-derived records, can load or refresh matching CCLD rows from local
   validated hosted seeded-corpus output through the existing source-derived
   import tables, links matching rows into the hosted reviewer UI, shows a guided
   facility/date-scoped result queue with contextual help, triage summaries,
   progress/status context, reviewer note/status cues, source-traceability
   availability cues, suggested next-record links, skip-to-main page structure,
   visible first-run next-step guidance, clearer form/action text, and a
   structured copyable feedback checklist intended to be pasted into an external
   feedback channel manually, and explains the explicit CCLD
   live-fetch command when broader retrieval is needed. It does not run live
   crawling, execute connectors, mutate reviewer-created state, create audit
   rows, persist lookup or feedback data, commit raw/full facility CSV files, or add non-CCLD sources from browser requests. A
   browser-accessible local/test reviewer UI shell is
   available at `/reviewer` when the scaffold is running locally; it loads the
   tiny seeded fixture corpus into process-local test state, lets a local tester
   search/select a source-derived record, see list-level reviewer-created
   note/status indicators before opening detail, view a plain-language record
   summary, safe source traceability fields, safe related seeded bundle context,
   existing reviewer notes/statuses, record-specific feedback clues, and CCLD
   return links, submit a bounded reviewer note, submit a bounded reviewer status,
   see clearer saved-state confirmations with return-to-queue links, and see
   read-after-write reviewer-created state through those same existing workflow seams. It also gives clear
   browser guidance for no search results, missing seeded records, invalid note
   or status forms, and local/test permission blocks. Narrative source
   fields are hidden in the browser shell. It also includes a narrow local/test reviewer-
   created state persistence scaffold table/service, a narrow local/test audit
   event scaffold for successful reviewer-created state scaffold writes only, a
   narrow local/test authenticated audit history read route seam for those audit
   rows, a narrow local/test audit coverage planning route that summarizes
   current and deferred audit categories without creating audit rows, a narrow local/test authenticated reviewer-created state read route
   seam for listing, fetching, filtering, or bounded search over persisted
   scaffold rows, and a local/test
   authenticated reset/reload dry-run route seam that reports
   what a future seeded corpus reset/reload would affect and can optionally
   persist a separate operational planning metadata record when explicitly
   requested by local/test code, a narrow local/test execution-plan route seam
   that turns those summaries into ordered bounded non-destructive action steps,
   plus a narrow local/test read-only route seam
   for listing or fetching those persisted planning records. It does not
   implement real login flow, auth middleware, provider registration, hosted
   URLs, user tables, role persistence, full reviewer workflows,
   annotations, corrections, production review status UI, production import automation,
   full audit coverage, new audit writes, audit UI, audit export, reset/reload execution, exports,
   deployment, QNAP, Azure, or AWS.
   Start with `scripts/check-hosted-scaffold-local.ps1` to verify local Python
   and development-tool prerequisites without installing software or requiring
   admin rights.
   The local `/source-records` route shows fixture/sample source-derived records
   only, with local sample filtering/search controls, sample
   source-traceability summary panels, sample traceability-style fields, and no
   live data, database-backed reads, real login flow, or reviewer-created state
   persistence. The separate `/reviewer` route is the local/test browser UI
   shell over the seeded database-backed route seams; `/source-records` remains
   the fixture/sample read-only display shell.
   Workflow shell detail payloads can compose associated reviewer-created state
   read output and a compact summary derived from that output only when tests or
   local callers provide explicit source-derived and reviewer-created state
   route contexts. The workflow shell note and status actions are also
   local/test only, force source-record binding from the selected detail context,
   require reviewer-state write permission, and write through the existing
   reviewer-created state and audit path.
   The reset/reload dry-run and execution-plan seams are also local/test only and require an
   explicit database, actor, and scope context from tests or local callers. The
   operational metadata scaffold stores non-executing planning metadata only, requires
   import/reload permission, rejects unauthenticated, disabled or revoked,
   role-denied, and out-of-scope actors, supports read-only list/fetch routes
   over those planning records, and does not execute reset/reload. The
   reviewer-created state scaffold is also local/test only, requires explicit
   authenticated actor context and reviewer-state write permission for writes,
   stores scaffold rows separately from source-derived records, and exposes a
   narrow local/test reviewer note creation route that stores bounded non-secret
   note text as reviewer-created scaffold payload under the existing state kind
   plus a narrow local/test reviewer status creation route that stores bounded
   status values as reviewer-created scaffold payload under the existing state
   kind without changing the schema. The audit
   event scaffold is also local/test only and records successful reviewer-
   created state scaffold writes separately from both source-derived and
   reviewer-created rows. The audit history read seam is local/test only,
   requires explicit database, actor, and scope context plus audit-read
   permission, and returns non-secret audit row fields without mutating source-
   derived, reviewer-created, or audit rows.
   The reviewer-created state read seam is local/test only, requires explicit
   database, actor, and scope context plus reviewer-state read permission, and
   returns non-secret scaffold row fields with schema-backed filters and bounded
   search over existing fields without mutating source-derived,
   reviewer-created, audit, or operational metadata rows.
   Source-derived read access alone does not grant workflow-shell access to
   associated reviewer-created state context or reviewer note creation.
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
