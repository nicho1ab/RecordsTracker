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
- Accepted the hosted tester MVP operational boundaries for audit logging,
  export generation, reset/reload, and tester data retention, clearing the next
  product-moving path toward provider-specific authentication, concrete
  database/migration decisions, minimal hosted schema/API scaffold, seeded
  corpus import/reset, and the first authenticated tester workflow without
  implementing those layers prematurely.
- Accepted the hosted tester MVP auth provider and role implementation
	direction, choosing a managed standards-based OpenID Connect/OAuth 2.0
	provider class and minimum role/scope/audit-identity boundaries without
	adding auth middleware, schemas, API routes, provider configuration, secrets,
	hosted URLs, deployment, live crawling, or connector execution.
- Accepted the hosted tester MVP database and migration tooling direction,
	choosing PostgreSQL and Alembic-managed migrations to support future hosted
	source-derived imports, reviewer-created state, audit events, export packet
	state, tester feedback, reset/reload metadata, and auth role/scope references
	without adding schemas, tables, migrations, API routes, imports, reset
	commands, auth middleware, secrets, deployment, CI configuration, live
	crawling, or connector execution.
- Added minimal PostgreSQL/Alembic project wiring for the hosted tester MVP,
	including no-secret database URL validation, an Alembic script location with no
	domain migration revisions, scaffold-only persistence/API boundary descriptors,
	dependency declarations, local setup checks, and focused tests without adding
	domain tables, API routes, imports, reset/reload commands, auth middleware,
	secrets, deployment, live crawling, or connector execution.
- Added the first controlled hosted tester seeded corpus import path, including
	a PostgreSQL/Alembic migration for import batch metadata and source-derived
	record staging, a local validated JSON artifact importer, a tiny fixture
	artifact, and focused tests for import batch identity, stable source-derived
	identity, source traceability, idempotent staging, and no reviewer-created
	state writes without adding reset/reload behavior, API routes, auth
	middleware, reviewer workflows, production automation, hosted live crawling,
	or connector execution.
- Added a narrow database-backed source-derived read service over staged hosted
	seeded corpus records, with list and fetch helpers that return source
	traceability, original values, stable source-derived identities, and import
	batch context without adding HTTP API routes, auth middleware, reviewer
	workflows, reset/reload behavior, production automation, hosted live crawling,
	or connector execution.
- Added a focused hosted tester auth/authz boundary scaffold with managed
	OIDC/OAuth2 provider-class configuration validation, local/test actor, role,
	scope, account-status, authorization-target, and audit-context models, and
	protected source-derived read service guards without adding real login flow,
	provider registration, secrets, tokens, cookies, auth middleware, user tables,
	reviewer-created state, audit persistence, API routes, deployment, live
	crawling, or connector execution.
- Added a narrow local/test authenticated source-derived HTTP/API read route
	seam over staged seeded corpus records, with JSON list, fetch-by-key, and
	fetch-by-stable-identity handlers that preserve source traceability, original
	values, import batch context, auth guard behavior, and the source-derived
	versus reviewer-created state boundary without adding real login flow, auth
	middleware, reviewer-created state, audit persistence, exports, reset/reload,
	production automation, hosted live crawling, connector execution, deployment,
	or schema changes.
- Added the first narrow local/test authenticated reviewer-facing workflow shell
	over the source-derived read route seam, with read-only queue and detail JSON
	payloads that preserve record identity, original values, source traceability,
	source document metadata, import batch context, auth guard behavior, and the
	source-derived versus reviewer-created state boundary without adding real
	login flow, auth middleware, reviewer-created state persistence, annotations,
	corrections, review status, audit persistence, exports, reset/reload,
	production automation, hosted live crawling, connector execution, deployment,
	or schema changes.
- Added a narrow local/test reviewer workflow shell detail integration that
	composes associated reviewer-created state read route output for a selected
	source-derived record, preserving separate source-derived and reviewer-state
	read permissions, non-secret payloads, no-mutation behavior, and the no-write,
	no-full-workflow, no-production-auth, no-deployment, no-schema-change boundary.
- Added a local/test authenticated seeded corpus reset/reload dry-run seam that
	reports existing seeded import batch metadata, source-derived record counts by
	entity, future reviewer-created state handling modes, required permissions,
	validation requirements, audit requirements, and deferred destructive actions
	without deleting, truncating, overwriting, archiving, importing, reloading,
	persisting audit events, running hosted live crawling, executing connectors,
	deploying, or changing schemas.
- Added a minimal local/test reset/reload operational metadata scaffold with a
	separate PostgreSQL/Alembic table and service boundary for explicitly requested
	dry-run planning records, preserving source-derived, reviewer-created, and
	audit rows without adding reset/reload execution, archive execution, clear
	execution, relinking, production automation, hosted live crawling, connector
	execution, deployment, or production API behavior.
- Added narrow local/test read-only reset/reload planning metadata routes over
	those persisted planning records, with JSON list and fetch-by-ID handlers,
	schema-backed filters, import/reload permission checks, and no-mutation
	coverage without adding reset/reload execution, archive execution, clear
	execution, relinking, scheduler behavior, production automation, hosted live
	crawling, connector execution, deployment, or production API behavior.
- Added a minimal local/test reviewer-created state persistence scaffold with a
	separate PostgreSQL/Alembic table and service boundary for authenticated
	review-item-state placeholder rows linked to staged source-derived record
	keys, preserving source-derived records and original extracted values without
	adding full reviewer workflows, annotations, corrections, audit persistence,
	exports, reset/reload execution, real login flow, auth middleware, hosted live
	crawling, connector execution, deployment, or production API behavior.
- Added narrow local/test read-only reviewer-created state routes over persisted
	scaffold rows, with JSON list and fetch-by-ID handlers, reviewer-state read
	permission checks, schema-backed filters, and no-mutation coverage without
	adding reviewer-created state writes, full reviewer workflows, annotations,
	corrections, exports, real login flow, auth middleware, hosted live crawling,
	connector execution, deployment, or production API behavior.
- Added a minimal local/test audit event persistence scaffold with a separate
	PostgreSQL/Alembic table and service boundary for successful reviewer-created
	state scaffold writes only, preserving source-derived records and reviewer-
	created state rows while recording authenticated actor attribution,
	permission, scope, action, target, source-derived context, and concise metadata
	without adding full audit coverage, audit UI, audit export, retention
	automation, full reviewer workflows, annotations, corrections, real login flow,
	auth middleware, hosted live crawling, connector execution, deployment, or
	production API behavior.
- Added a narrow local/test authenticated audit history read route seam over the
	first audit event scaffold, with JSON list and fetch-by-ID handlers, scoped
	filters, audit-read permission checks, and no-mutation coverage without adding
	audit UI, audit export, full audit coverage, retention automation, real login
	flow, auth middleware, hosted live crawling, connector execution, deployment,
	or production API behavior.
- Added the first local hosted tester MVP scaffold with a Python standard-library
	app shell, health route, smoke check, focused tests, and local Windows
	PowerShell run documentation without adding cloud, QNAP, Docker, schema,
	authentication, authorization, import/sync, or reviewer workflow behavior.
- Added local hosted scaffold setup-check tooling so developers can verify
  Python and development-tool prerequisites on Windows without installing
  software, requiring admin rights, or requiring Node, Docker, QNAP, cloud
  resources, or a public URL.
- Added the first local-only read-only source-derived hosted view shell using
	fixture/sample records, sample source-traceability-style fields, and clear
	labels that no live data, database, import/sync, authentication, or
	reviewer-created state persistence is active.
- Added local-only semantic/accessibility validation coverage for the hosted
	source-record list/detail shell using Python standard-library HTML parsing.
- Added a governance inventory and gap analysis for the production-discovery
	state, local hosted scaffold implementation, completed ADRs, deferred
	decisions, stale-guidance assessment, and next implementation phase.
- Added a public-source data inventory for structured CSV/open-data sources,
	HTML portal/detail pages, PDFs, metadata/catalog pages, uploaded CSV example
	planning, future multi-source adapters, attorney focus areas, and gated
	feedback or GitHub intake planning without implementing source behavior.
- Added local-only sample filtering/search to the hosted source-record shell
  using query, jurisdiction, and source-family controls over fixture/sample
  records only, preserving the no-database, no-import, no-authentication,
  no-reviewer-state, and no-deployment boundary.
- Added fixture/sample-only source traceability summary panels to the hosted
	source-record list/detail shell using visible sample metadata indicators only,
	preserving the no-database, no-import, no-authentication, no-reviewer-state,
	and no-deployment boundary.
- Added local-only public-source CSV profiling tooling for ignored
	`data/raw/source-profiling/` CSV files, writing ignored JSON, CSV, and log
	outputs for source discovery without importing data, adding connectors,
	creating schemas or migrations, changing canonical fields, or loading hosted
	app behavior.
- Added tiny synthetic public-source facility fixtures selected from local CSV
	profiling results for future fixture-backed source/facility view planning,
	without committing raw files, generated profiling outputs, imports, schemas,
	connectors, or hosted app behavior.
- Added a local-only hosted scaffold `/facilities` read-only sample view and
	detail pages backed by the committed tiny public-source facility fixtures,
	preserving fixture/sample labels, semantic/accessibility validation,
	manifest-backed traceability placeholders, and the no-database, no-import,
	no-authentication, no-reviewer-state, no-deployment boundary.
- Added a local-only hosted scaffold facility source coverage panel that links
	facility-master fixture detail pages to related fixture/sample source-record
	context where the sample mapping exists, while preserving unmapped fixture
	states and the no-live-source, no-database, no-import, no-authentication,
	no-reviewer-state, no-schema-change, no-deployment boundary.

## Near-term milestones

- Keep the local hosted scaffold runnable, prerequisite-checked, smoke-tested,
	and clear about sample-only read-only source-derived views while the next
	hosted implementation decisions are made.
- Use the accepted audit, export, reset/reload, tester retention, auth
	provider-class, role, scope, audit-identity, PostgreSQL, Alembic migration,
	controlled seeded import, database-backed source-derived read, auth boundary
	scaffold, local/test source-derived read route seam, first read-only
	authenticated tester workflow shell, reviewer workflow shell associated-state
	read integration, reviewer-created state persistence scaffold, reviewer-created state read route seam, audit event persistence
	scaffold, audit history read route seam, and
	reset/reload dry-run planning seam with opt-in operational metadata persistence
	and read-only planning metadata routes to
	move the next hosted tester MVP branches toward real provider integration,
	further reset/reload execution planning beyond persisted metadata readback, and
	stateful reviewer-created workflow layers.
- Preserve Datasette, SQLite views, and review-bundle exports where they support
	validation, inspection, debugging, local exploration, and export workflows.
- Harden extraction with additional representative fixtures and edge-case tests.
- Expand narrative date and event extraction only when source text, confidence,
	and fixture-backed regression tests are included.
- Strengthen data quality checks for duplicates, date consistency, source hash
	presence, and raw source traceability.
- Keep roadmap, changelog, setup, runbook, and Copilot workflow documentation
	current after each meaningful capability, governance, or workflow change.
- Keep the public-source data inventory current when new source candidates,
	uploaded examples, source metadata, source limitations, parser risks, or
	multi-source planning assumptions are discovered.

## Current next priorities

These priorities should be implemented as incremental production-discovery,
data quality, extraction, architecture, and review-requirements work. Datasette
has been outgrown as the primary future review experience and should be extended
only where it remains useful for validation, inspection, debugging, local
exploration, or export support.

1. Implement real provider integration against the managed OpenID Connect/OAuth
	2.0 provider class after the local/test auth boundary, callback/session, and
	configuration decisions are clear.
2. Expand reset/reload planning into later reset/reload behavior for the seeded
	corpus only after reviewer-created state preservation, fuller audit coverage,
	operational metadata, and permission boundaries are broadened beyond this
	local/test planning scaffold.
3. Expand beyond the reviewer-created state and first audit event scaffolds into
	export packet state, tester feedback, reset/reload metadata, fuller audit
	coverage, and stateful reviewer-created workflow branches.
4. Implement stateful reviewer-created workflow layers over a seeded,
	source-traceable corpus after auth, schema, audit, and permission boundaries
	are ready.
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
	controlled import boundary, ADR-0010's physical separation strategy,
	ADR-0011's authenticated access boundary, ADR-0012's scaffold-first sequence,
	ADR-0013's operational boundaries, ADR-0014's auth provider-class and role
	implementation direction, and ADR-0015's PostgreSQL/Alembic direction plus the
	minimal scaffold wiring, controlled seeded import path, database-backed
	source-derived read service, local/test auth boundary scaffold, local/test
	source-derived read route seam, and first read-only authenticated workflow
	shell, reviewer-created state persistence scaffold, reviewer-created state
	read route seam, first audit event persistence scaffold, local/test audit
	history read route seam, reset/reload
	planning metadata scaffold, and read-only planning metadata route seam to move into real
	provider integration, fuller reset/reload planning,
	fuller audit coverage, export/feedback metadata, and stateful authenticated tester
	workflow implementation.

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
- Decide which public-source candidates should move from inventory and local
	profiling into approved connector, import, fixture, schema, or hosted-view
	implementation work.
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
