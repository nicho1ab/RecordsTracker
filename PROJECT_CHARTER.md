# Project Charter

## Project name

CCLD Complaints Data

## Problem statement

Public complaint and inspection records are available through the CCLD public portal, but the portal is not optimized for structured analysis, bulk review, comparison, delay analysis, or repeatable research workflows.

## Current phase

The project is in production-discovery for a source-traceable public-record
review solution.

The first production-like runtime assumption is QNAP Docker with PostgreSQL in
Docker. Application configuration and persistence boundaries must remain
portable enough to move later to AWS, Azure, DigitalOcean, Render, Fly.io, or
another host without hard-coding QNAP-specific paths into application code.

This is an independent public-interest project. The first expected
tester audience is a small group of external reviewers evaluating the hosted CCLD workflow.

Earlier project work proved ingestion, deterministic extraction, raw source
preservation, source traceability, local review, and source-traceable exports.
Current work should move RecordsTracker toward an attorney-facing public-record
review workspace that helps attorneys and advocates find a facility, select
dates, request or load records, review complaint records, prepare packet context,
print or export, and submit feedback. Product and architecture requirements
must preserve deeper operator and developer visibility, but separate those
diagnostics from the default reviewer surface.

For OpenAI Build Week 2026, the current deployed checkpoint
`d7e9b1fff9e1826c3387a7313777d14c1480d3b4` is intermediate, not final. The
governed Phase A evaluation merged at
`41d512127febdfd086432e7f082d0651da232e9f` and concluded **SUPPLEMENT**, not
replacement. The remaining completion scope is a governed dual-source model:
program-specific snapshots remain the primary facility-reference source family,
and ArcGIS is a separately versioned supplementary current-reference source.
This merged decision supersedes the original #516 replacement premise. Issues
#521-#523 completed the shared projection, named consumers/exports, and bounded
backfill for eligible existing program-reference data; they did not consume or
activate ArcGIS. The remaining work extends those governed boundaries to the
ArcGIS supplement after #518 establishes its separate snapshot lifecycle.
The required sequence is defined in the
[Build Week ArcGIS facility-reference completion plan](docs/planning/build-week-2026-arcgis-facility-reference-completion-plan.md).

## Primary goal

Advance a governed public-record review solution that ingests public facility
reports, stores raw source evidence, extracts structured complaint fields,
validates data quality, preserves source traceability, supports current local
attorney-review aid workflows, and defines the production-discovery requirements
for future reviewer state, annotations, corrections, queues, collaboration,
accessibility, and exports.

Datasette is retained as a validation, inspection, debugging, local exploration,
and export-support layer. It is no longer the governed primary future review
experience.

The Build Week facility-reference goal is one provenance-preserving identity
projection across search, facility hub, queue, complaint detail, packet views,
exports, and operator reporting; controlled dual-source reconciliation and
backfill; separate governed refresh workflows with recovery; and automated
Hosted acceptance. Program snapshots remain the primary source family, while
ArcGIS may supply only approved supplementary current-reference fields. Neither
source erases the other. Raw type value `733` must not receive a descriptive
label without verified source or governed mapping evidence.

## Initial source

California Community Care Licensing Division public facility/report portal.

Initial facility:

- Facility: A. Miriam Jamison Children's Center
- Facility number: 157806098

## Target users

- Attorneys and advocates reviewing public licensing complaint records.
- Researchers and analysts reviewing facility complaint history.
- Operators supporting safe runtime visibility for imports, retrieval jobs,
  diagnostics, and setup checks.
- Developers maintaining source connectors, extraction logic, schemas, tests,
  and local debug surfaces.
- Reviewers using source-traceable exports, retained Datasette inspection, and
  primary review workflows.

## Success criteria

- Raw public source reports can be downloaded or reproducibly retrieved.
- Structured complaint fields can be extracted into SQLite.
- Each structured record links back to source URL and raw file hash.
- Fixture-based regression tests prevent previously working extraction from breaking.
- Documentation is generated and maintained for developer and end-user audiences.
- The presentation layer meets ADA digital accessibility requirements.
- The project can add future source connectors without rewriting the architecture.
- The final Build Week release is set only after the complete ArcGIS supplement
  and dual-source reconciliation sequence is merged, deployed, reconciled, and
  accepted through automated Hosted evidence.

## Non-goals

- Do not build a production custom application before production-discovery ADRs
	and architecture decisions define the product and stack direction.
	This constraint does not prohibit the approved local/test hosted scaffold and
	reviewer workflow work described in the ADRs and roadmap, and it does not
	authorize production deployment.
- Do not add new Datasette-primary UX as a substitute for production-discovery
	requirements work.
- Avoid project dependencies on optional paid platform features.
- Do not treat portal data as complete, authoritative, or guaranteed accurate.
- Do not use LLM extraction where deterministic parsing is reliable.
- Do not include Paperless-ngx in the initial architecture unless a document-management requirement emerges.
