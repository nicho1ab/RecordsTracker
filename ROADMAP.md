# Roadmap

This roadmap reflects the production-discovery phase for a source-traceable
public-record review solution. The project has completed the initial CCLD
proof-of-concept threshold for ingestion, extraction, raw preservation, source
traceability, local review, and exports. Datasette remains useful for validation,
inspection, debugging, local exploration, and export support, but it is no longer
the governed primary future review experience.

## Completed foundation

- Established the governed repository structure, Copilot instructions, and core
	project documentation.
- Defined the data contract, source connector contract, testing strategy,
	documentation strategy, accessibility requirements, security rules, and
	decision log.
- Adopted Python, SQLite, and Datasette for the proof of concept.
- Documented raw source preservation, source traceability, accessibility, and
	optional paid platform dependency rules.

## Completed CCLD proof-of-concept capabilities

- Implemented the CCLD single-facility fixture workflow for the initial facility.
- Added a small fixture-backed multi-facility sample corpus for offline coverage
	of intake diagnostics, fetch summaries, source traceability, facility
	comparison, and review-bundle export paths without live public requests.
- Added fixture-backed extraction and regression coverage for known CCLD reports.
- Added fixture-backed hardening for numbered allegation rows in CCLD report
	layouts.
- Preserved raw source files and SHA-256 hashes before extraction.
- Normalized extracted records into facility, source document, complaint,
	allegation, event, and extraction audit records.
- Wrote normalized records to SQLite with idempotent upsert behavior.
- Added controlled live fetch for explicitly provided facility numbers.
- Added multi-facility input for live fetch workflows scoped to user-provided
	facility numbers.
- Added facility identifier intake diagnostics for controlled live fetch runs,
  including accepted identifiers, duplicate identifiers ignored, ignored input
  values, and invalid-format rejection before public requests begin.
- Added live fetch summary output for discovered, selected, skipped, fetched,
	written, and failed report counts.
- Added controlled multi-facility live fetch outcome summaries that distinguish
  records discovered, no records discovered, discovery failures,
  skipped-by-limit reports, partial report failures, and written records.
- Added SQLite review views for complaint review, facility summaries, delay
	review flags, and source traceability.
- Added a low-noise first-pass complaint review view that preserves source
	traceability and lower-level IDs while hiding implementation-heavy fields from
	the initial review surface.
- Added Datasette metadata and saved queries to guide review, filtering,
	source-checking, and export workflows.
- Added a source-traceable start-here saved query for guided complaint review in
	Datasette.
- Added a source-traceable public-record allegation search saved query for
  cautious keyword discovery over source-derived allegation text, categories,
  and findings.
- Added a source-traceable complaint timeline review view and facility-filtered
	saved query for complaint milestone dates and extracted event dates.
- Added a field-level source traceability review view and facility-filtered
	saved query for extraction audit context alongside source document metadata.
- Added a multi-facility source traceability review view and facility-filtered
	saved query for checking source traceability status and linked derived-record
	counts by source document across facilities.
- Added a facility pattern review view and saved query for comparing finding mix,
	allegation categories, missingness, report-date proxy usage, review flags, and
	source document coverage across facilities.
- Added a facility comparison review view and repeated category/finding saved
  query for cautious cross-facility source-review queues over the local derived
  dataset.
- Added a `review_home` Datasette saved query as a task-based start-here surface
	for complaint review, delay triage, facility comparison, source verification,
	and CSV export paths before any dashboard or custom web interface decision.
- Added contextual help to primary Datasette review views and saved queries for
	when to use each item, what not to conclude, and what source traceability to
	preserve when exporting.
- Added a local review bundle export workflow for source-traceable complaint
	review, delay triage, source traceability, multi-facility source traceability,
	complaint timeline, field traceability, facility pattern, and facility
	comparison CSV files.
- Grouped sample and live fetch script next steps by reviewer task, including
	what to open first, delay triage, source verification, and CSV export.
- Added data quality coverage that verifies derived complaint, allegation,
  event, and extraction audit records trace back to source documents with source
  URL, raw hash, connector metadata, and retrieval timestamp.
- Added data quality coverage that checks sample-derived canonical tables for
  duplicate record identifiers and duplicate source URLs.
- Added data quality coverage that verifies complaint date ordering and stored
  delay calculation fields against deterministic date math.
- Added data quality coverage that verifies source document hashes are present
  as lowercase SHA-256 hex values.
- Added data quality coverage that verifies source document hashes match the
  preserved raw files referenced by `raw_path`.
- Added inline complaint received date extraction hardening with a
	fixture-backed CCLD report layout regression test.
- Added fixture-backed missing visit date coverage for CCLD report-date proxy
	delay review behavior.
- Added fixture-backed labeled finding extraction hardening for CCLD report
	layouts that provide findings after an explicit `Finding:` label.
- Added fixture-backed wrapped allegation extraction hardening for CCLD report
	layouts where one allegation continues across adjacent lines.
- Added fixture-backed split finding label extraction hardening for CCLD report
	layouts where the finding value appears on the line after a standalone label.
- Added fixture-backed allegation heading variant extraction hardening for CCLD
	report layouts that use an `ALLEGATIONS:` section heading.
- Added fixture-backed investigation finding heading variant extraction
	hardening for CCLD report layouts that use an `INVESTIGATION FINDING:`
	section heading.
- Added fixture-backed no-colon allegation heading extraction hardening for CCLD
	report layouts that use an `ALLEGATIONS` section heading.
- Added fixture-backed punctuated finding extraction hardening for CCLD report
	layouts where a normalized finding value includes trailing punctuation.
- Added fixture-backed dashed finding label extraction hardening for CCLD report
	layouts where an inline `Finding -` label precedes the normalized finding.
- Added fixture-backed was-received complaint date extraction hardening for CCLD
	report layouts that use a `complaint was received in our office on` phrase.
- Added fixture-backed split report date label extraction hardening for CCLD
	report layouts where `Report Date` is followed by the date value.
- Added fixture-backed split date signed label extraction hardening for CCLD
	report layouts where `Date Signed` is followed by the signed date value.
- Added fixture-backed split visit date label extraction hardening for CCLD
	report layouts where `VISIT DATE` is followed by the visit date value.
- Added fixture-backed split complaint control number label extraction hardening
	for CCLD report layouts where `COMPLAINT CONTROL NUMBER` is followed by the
	complaint control number value.
- Added fixture-backed split facility name label extraction hardening for CCLD
	report layouts where `FACILITY NAME` is followed by the facility name value.
- Added fixture-backed split facility number label extraction hardening for CCLD
	report layouts where `FACILITY NUMBER` is followed by the facility number
	value.
- Added fixture-backed report type case hardening for CCLD report layouts where
	the complaint investigation report heading uses different casing.
- Added fixture-backed spaced allegation heading extraction hardening for CCLD
	report layouts that use an `ALLEGATION (S):` section heading.
- Added fixture-backed no-colon investigation findings heading extraction
	hardening for CCLD report layouts that use an `INVESTIGATION FINDINGS`
	section heading.
- Added fixture-backed punctuated complaint received date phrase hardening for
	CCLD report layouts where punctuation separates the narrative phrase from the
	received date value.
- Added fixture-backed punctuated report type heading hardening for CCLD report
	layouts where the complaint investigation report heading includes trailing
	punctuation.
- Added fixture-backed dashed investigation findings heading hardening for CCLD
	report layouts that use an `INVESTIGATION FINDINGS -` section heading.
- Added fixture-backed dashed allegation heading hardening for CCLD report
	layouts that use an `ALLEGATION(S) -` section heading.
- Added fixture-backed spaced-colon report date label hardening for CCLD report
	layouts that use a `Report Date :` label variant.
- Added fixture-backed spaced-colon date signed label hardening for CCLD report
	layouts that use a `Date Signed :` label variant.
- Added fixture-backed spaced-colon visit date label hardening for CCLD report
	layouts that use a `VISIT DATE :` label variant.
- Added fixture-backed spaced-colon complaint control number label hardening for
	CCLD report layouts that use a `COMPLAINT CONTROL NUMBER :` label variant.
- Added fixture-backed spaced-colon facility name label hardening for CCLD
	report layouts that use a `FACILITY NAME :` label variant.
- Added fixture-backed spaced-colon facility number label hardening for CCLD
	report layouts that use a `FACILITY NUMBER :` label variant.
- Added fixture-backed split spaced-colon finding label hardening for CCLD
	report layouts that split a `Finding :` label from its value.
- Added fixture-backed semicolon facility name label hardening for CCLD report
  layouts that use a `FACILITY NAME;` label variant.

## Completed governance and review experience improvements

- Added design and usability governance for the local Datasette review
	experience.
- Documented delay review flags as screening aids, not conclusions.
- Documented accessible CSV export expectations and source traceability review.
- Added documentation checks to guard against stale scaffold language and missing
	required public guidance.
- Added Copilot workflow guidance for small, testable changes under the project
	governance rules.
- Added release checklist guidance for validation, accessibility review, PR
	checks, merge cleanup, and next-task handoff.
- Added governance requiring GitHub branch protection or repository rulesets for
	`main`, including required `validate`, `docs-check`, `fixtures`, and
	`security` status checks before squash merge.
- Added governance feedback-loop rules so bug and CI-failure fixes update
	relevant governance when a missing or unclear rule allowed the failure.
- Added a local output accessibility checklist for Datasette views, generated
	metadata, saved queries, CSV exports, review bundles, and script output.
- Accepted the Datasette exit governance transition: Datasette is retained as a
  validation, inspection, debugging, local exploration, and export-support layer,
  while production-discovery defines the future primary reviewer UX requirements.
- Defined the minimum production-discovery requirements for a future hosted
	primary reviewer application, including review state, annotations,
	corrections, tester readiness, export packet preparation, and source
	traceability boundaries.
- Accepted the hosted tester MVP architecture boundary, separating Datasette's
  retained validation role from a future primary reviewer application layer and
  deferring stack, persistence, authentication, sync, export, audit log, and
  retention decisions to future ADRs.
- Accepted the hosted tester MVP stack evaluation, recommending a hybrid
	direction that preserves the Python ingestion/extraction pipeline and retained
	SQLite/Datasette validation layer while planning a hosted relational reviewer
	state store and hosted reviewer application/API boundary.
- Accepted the hosted tester MVP data and review-state model boundary,
  separating source-derived imported records from reviewer-created review state
  before schema, migration, import/sync, authentication, export, audit, or
  scaffold decisions.
- Accepted the hosted tester MVP import/sync strategy, keeping the Python
	pipeline as the source-derived data producer and starting hosted tester data
	population with controlled snapshot imports from validated pipeline output.
- Accepted the hosted tester MVP schema and migration strategy boundary,
  requiring future hosted schema work to separate import metadata,
  source-derived imported records, reviewer-created state, audit events, export
  packet state, tester feedback, and operational/reset metadata without
  implementing schemas or migrations prematurely.
- Accepted the hosted tester MVP authentication and access boundary, requiring
	authenticated invited or provisioned tester access, simple role-based access,
	revocable tester accounts, permissioned import/reload/reset and export
	actions, and auditable reviewer-created actions where feasible.
- Accepted the hosted tester MVP scope and scaffold sequencing boundary,
  allowing hosted implementation to begin through a scaffold-first sequence
  while keeping schemas, authentication, authorization, import/sync, queues,
  annotations, corrections, exports, reset/reload, hosted deployment, and
  extraction behavior out of the first scaffold branch.

## Near-term milestones

- Begin the first hosted MVP scaffold implementation branch with a runnable,
  testable app shell, smoke validation, local development instructions, and no
  business workflow behavior.
- Decide audit logging, export generation, reset/reload, tester data retention,
  provider-specific authentication details, and concrete framework/tooling
  choices before implementing the affected hosted workflow layers.
- Decide concrete database product and migration tooling only after the accepted
  schema/migration strategy, authentication/access needs, reset/reload needs,
  audit requirements, and hosted operations constraints are clear.
- Preserve Datasette, SQLite views, and review-bundle exports where they support
	validation, inspection, debugging, local exploration, and export workflows.
- Harden extraction with additional representative fixtures and edge-case tests.
- Expand narrative date and event extraction only when source text, confidence,
	and fixture-backed regression tests are included.
- Strengthen data quality checks for duplicates, date consistency, source hash
	presence, and raw source traceability.
- Keep roadmap, changelog, setup, runbook, and Copilot workflow documentation
	current after each meaningful capability, governance, or workflow change.

## Current next priorities

These priorities should be implemented as incremental production-discovery,
data quality, extraction, architecture, and review-requirements work. Datasette
has been outgrown as the primary future review experience and should be extended
only where it remains useful for validation, inspection, debugging, local
exploration, or export support.

1. Implement the first hosted MVP scaffold branch with project structure,
	minimal app/API shell as applicable, smoke validation, test harness, local run
	docs, and no business workflow behavior.
2. Draft audit log, export generation, reset/reload, and tester retention ADRs
	before implementing those hosted workflow layers.
3. Decide provider-specific authentication and authorization implementation
	details before implementing real authentication or authorization.
4. Decide concrete database product and migration tooling for the hosted tester
  MVP only after the remaining access, audit, reset/reload, export, retention,
  and operations constraints are understood.
5. Add additional CCLD fixtures and extraction hardening for representative
	report layouts, missing fields, and edge cases.

## Production-discovery transition path

Datasette has been outgrown as the primary future review experience. It remains
part of the local toolkit for validation, inspection, debugging, local
exploration, and export support over SQLite.

Before production-build work, use the production-discovery requirements to
define the smallest useful product shape:

1. Confirm the core reviewer tasks and the minimum fields, source traceability,
   and caution language each task needs.
2. Decide which architecture boundaries belong to ingestion, storage,
	validation, review state, correction state, export generation, and future
	presentation.
3. Use ADR-0007's hybrid direction, ADR-0008's data-domain boundary, ADR-0009's
	controlled import boundary, ADR-0010's physical separation strategy, and
	ADR-0011's authenticated access boundary together with ADR-0012's
	scaffold-first sequence to begin hosted scaffold implementation while deciding
	audit log, export generation, reset/reload, retention, concrete
	database/migration tooling, and provider-specific authentication
	implementation before the affected layers are built.

## Decision points

- Decide when the proof of concept has enough fixture coverage to treat CCLD
	extraction as stable for broader review.
- Decide the review-state model for saved progress, guided queues, annotations,
  corrections, and collaboration.
- Decide whether correction state belongs in SQLite, a separate review store, an
  import/export workflow, or a future production application boundary.
- Decide the production architecture boundary for the primary reviewer UX after
  production-discovery requirements are documented.
- Decide whether Baserow, Metabase, a custom application, or another tool
  provides enough value to justify adding it outside the baseline workflow.
- Decide when to add a second public source connector under the source connector
	contract.
- Decide what accessibility checks are required before any public or stable
	release.
- Decide which production operations governance is required for access, audit,
  monitoring, retention, release, incident response, and operational support.

## Deferred product work

- Production primary review application workflow build work beyond the
	ADR-0012 scaffold-first sequence until the affected production-discovery
	requirements and ADRs define the layer being implemented.
- Hosted review queues, reviewer accounts, assignments, or role-based access
	control.
- Interactive dashboards beyond validation, inspection, or prototype work.
- PDF report generation unless accessibility can be validated.
- Optional paid platform dependencies unless explicitly approved and documented.
- Statewide crawling or automatic search expansion beyond explicitly provided
	facility numbers.
