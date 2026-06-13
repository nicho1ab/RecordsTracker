# ADR-0005: Retain Datasette as a Validation Layer After Primary Review UX Exit

## Status

Accepted

## Context

The initial proof of concept proved ingestion, deterministic extraction, raw
source preservation, source traceability, local review, and source-traceable
exports using Python, SQLite, and Datasette.

Reviewer needs now exceed what Datasette metadata, saved queries, and local table
views can reasonably support as the primary future review experience. Reviewers
need persistent navigation, guided queues, saved state, annotations, correction
workflows, richer contextual help, collaboration-ready paths, accessible exports,
and fewer-click reviewer workflows.

This decision does not reopen whether Datasette has been outgrown as the primary
reviewer UX. It treats that threshold as crossed.

## Decision

Datasette is no longer governed as the primary future review experience.

The project will retain Datasette as a validation, inspection, debugging, local
exploration, and export-support layer over SQLite. Datasette remains useful for
checking ingestion output, inspecting source traceability, validating review
views, supporting local attorney-review aid workflows, and exporting derived
records with source context.

The current phase is production-discovery for a source-traceable public-record
review solution. Production-discovery should define product requirements,
architecture boundaries, review-state needs, correction and annotation models,
accessibility expectations, export requirements, collaboration constraints, and
source traceability requirements before a production-build phase selects or
implements a primary review application stack.

## Phase boundaries

- POC: proven ingestion, extraction, raw preservation, source traceability, local
  review, and exports.
- Local attorney-review aid: current useful local SQLite, Datasette inspection,
  and source-traceable export workflows.
- Production-discovery: current phase for defining reviewer state, queues,
  annotations, corrections, collaboration, accessibility, exports, architecture
  boundaries, and source traceability requirements.
- Production-build: future implementation phase after ADRs and architecture
  decisions select a production direction.
- Production operations: future governance for access, audit, monitoring,
  retention, release, incident response, and operational support.

## Superseded scope

ADR-0001 and ADR-0002 remain accepted for the initial proof of concept and for
current local validation and attorney-review aid workflows. They are superseded
by this ADR only where they imply Datasette, Datasette metadata, saved queries,
or local review views should remain the primary future reviewer UX.

## Non-negotiable safeguards

This transition does not weaken the existing safeguards:

- Preserve source URL, raw hash, raw path when available, connector metadata,
  retrieval timestamp, report index, and extraction audit traceability.
- Preserve raw public source files before extraction.
- Treat the public portal as the source of record.
- Treat extracted records and review flags as derived review aids, not
  conclusions.
- Keep deterministic extraction and fixture-backed regression expectations.
- Do not add canonical fields without the full data contract, schema,
  documentation, and test update path.
- Do not add connectors outside the source connector contract.
- Do not add optional paid platform dependencies to the baseline workflow.
- Keep accessibility, security, privacy, and public-source caution language
  strict for any future primary review experience.

## Consequences

- Future review UX work should start from production-discovery requirements and
  architecture decisions, not from more Datasette-primary metadata or saved-query
  work.
- Datasette remains available for validation, inspection, debugging, local
  exploration, and export support.
- Production stack selection is deferred until requirements and architecture
  ADRs are reviewed.
- Existing user docs for local Datasette review remain valid as local workflow
  guidance, but they do not define the future primary product direction.