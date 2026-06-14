# Changelog

## Unreleased

- Added a governance inventory and gap analysis for the current
	production-discovery phase, local hosted scaffold state, completed ADRs,
	deferred decisions, stale-guidance assessment, and next hosted implementation
	gaps without changing product behavior.
- Added local-only semantic/accessibility validation coverage for the hosted
	scaffold source-record list and detail shell using Python standard-library
	HTML parsing, without browser automation or frontend test dependencies.
- Added the first local-only read-only source-derived hosted view shell with
	fixture/sample records, sample source-traceability-style fields, and explicit
	labels that no live data, database, import/sync, authentication, or
	reviewer-created state persistence is active.
- Added local hosted scaffold setup-check tooling for verifying Python and
	development-tool prerequisites on Windows without installing software,
	requiring admin rights, or requiring Node, Docker, QNAP, cloud resources, or a
	public URL.
- Updated the local secret-check script to ignore conventional `.venv*` local
	virtual environment directories so developer validation does not scan installed
	third-party packages.
- Added the first local hosted tester MVP scaffold with a Python
	standard-library app shell, health route, smoke check, focused tests, and
	Windows PowerShell run documentation while intentionally deferring cloud,
	QNAP, Docker, schema, authentication, authorization, import/sync, queues,
	annotations, corrections, exports, reset/reload, hosted deployment,
	reviewer-created state persistence, and extraction behavior.
- Added ADR-0012 defining the hosted tester MVP scope and scaffold sequencing
	boundary, allowing hosted implementation to begin through a scaffold-first
	sequence while keeping schemas, authentication, authorization, import/sync,
	queues, annotations, corrections, exports, reset/reload, hosted deployment,
	and extraction behavior out of the first scaffold branch.
- Added ADR-0011 defining the hosted tester MVP authentication and access
	boundary, requiring authenticated invited or provisioned tester access,
	simple role-based access, revocable tester accounts, permissioned
	import/reload/reset and export actions, and auditable reviewer-created actions
	where feasible while deferring provider, identity storage, session,
	authorization middleware, role schema, user table, invitation, audit schema,
	and deprovisioning implementation decisions.
- Added ADR-0010 defining the hosted tester MVP schema and migration strategy
	boundary, requiring future hosted schema work to separate import metadata,
	source-derived imported records, reviewer-created state, audit events, export
	packet state, tester feedback, and operational/reset metadata while deferring
	actual schema files, migrations, database product, migration tooling, import
	implementation, reset/reload implementation, retention, backup, and app
	scaffold decisions.
- Added ADR-0009 defining the hosted tester MVP import/sync strategy, keeping
	the Python pipeline as the source-derived data producer, starting with
	controlled snapshot imports from validated pipeline output, and deferring
	schema, migration, import implementation, reset/reload implementation,
	retention, backup, authentication, hosting, and app scaffold decisions.
- Added ADR-0008 defining the hosted tester MVP data and review-state model
	boundary, separating source-derived imported records from reviewer-created
	review state while deferring schema, migration, import/sync, authentication,
	export, audit, retention, and scaffold decisions.
- Added Copilot next-prompt quality governance, including prompt-mode guidance,
	project-aware synthesis requirements, validation expectations, PR body
	requirements, final handoff requirements, and a rule against including a next
	branch command unless the user asks for one.
- Added ADR-0007 evaluating hosted tester MVP production stack options and
	recommending a hybrid transition direction that preserves the Python
	ingestion/extraction pipeline and retained SQLite/Datasette validation layer
	while planning a hosted relational reviewer-state store and hosted reviewer
	app/API boundary.
- Added ADR-0006 for hosted tester MVP architecture boundaries, preserving
	source-derived data separately from reviewer-created state, retaining Datasette
	for validation and transition comparison, and deferring production stack
	decisions to future ADRs.
- Added minimum production-discovery requirements for the future hosted primary
	reviewer application, including hosted reviewer workflows, review-state
	boundaries, annotation and correction constraints, tester readiness, and
	source-traceable export packet expectations.
- Added Datasette exit governance for the production-discovery phase: Datasette
	is retained for validation, inspection, debugging, local exploration, and
	export support, while future primary reviewer UX work moves to requirements
	and architecture decisions.
- Added a small fixture-backed multi-facility sample corpus that exercises
	facility identifier intake diagnostics, controlled fetch summaries,
	multi-facility source traceability, facility comparison, and review-bundle
	export paths without live public requests.
- Expanded the local review bundle with multi-facility source traceability and
	facility comparison CSV files plus cautious README notes for attorney-review
	handoff packets.
- Added a facility comparison review view and repeated category/finding saved
	query for cautious cross-facility source-review queues over the local derived
	dataset.
- Added a multi-facility source traceability review view and facility-filtered
	saved query for checking source traceability status and linked derived-record
	counts by source document across facilities.
- Added clearer controlled multi-facility live fetch outcome summaries for
	records discovered, no records discovered, discovery failures,
	skipped-by-limit reports, partial report failures, and written records.
- Added facility identifier intake diagnostics to controlled live fetch runs so
  reviewers can see accepted identifiers, duplicates ignored, ignored file
  values, and invalid-format rejection before public requests begin.
- Expanded the local review bundle into a source-traceable public-record review
	packet with complaint timeline, field source traceability, and facility
	pattern CSV exports plus cautious README notes.
- Added a `facility_pattern_review` Datasette view and
	`facility_patterns_with_review_flags` saved query for comparing finding mix,
	allegation categories, missingness, report-date proxy usage, review flags, and
	source document counts across facilities without treating counts as findings.
- Added a field-level `field_source_traceability_review` Datasette view and
	`field_traceability_by_facility` saved query for reviewing extracted values,
	source text, warnings, confidence, extraction method, and source document
	traceability together.
- Added a source-traceable `complaint_timeline_review` Datasette view and
	`complaint_timeline_by_facility` saved query for reviewing complaint milestone
	dates and extracted event dates without treating missing dates as proof that
	an event did not occur.
- Added a source-traceable `public_record_allegation_search` Datasette saved
	query for cautious keyword discovery over source-derived allegation text,
	categories, and findings, with local review documentation and metadata
	coverage.
- Hardened CCLD facility name extraction for source layouts that use a
  `FACILITY NAME;` semicolon label variant, with fixture-backed regression
  coverage.
- Added data quality coverage that verifies source document hashes match the
  preserved raw files referenced by `raw_path`.
- Added data quality coverage that verifies source document hashes are present
  as lowercase SHA-256 hex values.
- Added data quality coverage that verifies complaint date ordering and stored
  delay calculation fields against deterministic date math.
- Added data quality coverage that checks sample-derived canonical tables for
  duplicate record identifiers and duplicate source URLs.
- Updated the roadmap to remove a completed local review workflow grouping item
  from current priorities and hardened documentation validation against stale
  completed roadmap priorities.
- Added a data quality test that verifies derived complaint, allegation, event,
  and extraction audit records trace back to source documents with required
  source URL, raw hash, connector metadata, and retrieval timestamp.
- Improved the `review_home` Datasette saved query with a `workflow_group`
  column so reviewers can scan local review paths by user task before opening
  implementation tables or detailed views.
- Hardened CCLD finding extraction for source layouts that split a
	`Finding :` spaced-colon label from its value, with fixture-backed regression
	coverage.
- Hardened CCLD facility number extraction for source layouts that use a
	`FACILITY NUMBER :` spaced-colon label variant, with fixture-backed regression
	coverage.
- Hardened CCLD facility name extraction for source layouts that use a
	`FACILITY NAME :` spaced-colon label variant, with fixture-backed regression
	coverage.
- Hardened CCLD complaint control number extraction for source layouts that use
	a `COMPLAINT CONTROL NUMBER :` spaced-colon label variant, with
	fixture-backed regression coverage.
- Hardened CCLD visit date extraction for source layouts that use a
	`VISIT DATE :` spaced-colon label variant, with fixture-backed regression
	coverage.
- Hardened CCLD date signed extraction for source layouts that use a
	`Date Signed :` spaced-colon label variant, with fixture-backed regression
	coverage.
- Hardened CCLD report date extraction for source layouts that use a
	`Report Date :` spaced-colon label variant, with fixture-backed regression
	coverage.
- Hardened CCLD allegation extraction for source layouts that use an
	`ALLEGATION(S) -` section heading variant, with fixture-backed regression
	coverage.
- Hardened CCLD allegation extraction for source layouts that use an
	`INVESTIGATION FINDINGS -` section heading variant, with fixture-backed
	regression coverage.
- Hardened CCLD report type extraction for source layouts where the complaint
	investigation report heading includes trailing punctuation, with
	fixture-backed regression coverage.
- Hardened CCLD complaint received date extraction for source layouts where
	punctuation separates the narrative received-date phrase from the date value,
	with fixture-backed regression coverage.
- Hardened CCLD allegation extraction for source layouts that use an
	`INVESTIGATION FINDINGS` section heading without a trailing colon, with
	fixture-backed regression coverage.
- Hardened CCLD allegation extraction for source layouts that use an
	`ALLEGATION (S):` section heading variant, with fixture-backed regression
	coverage.
- Hardened CCLD report type extraction for source layouts where the complaint
	investigation report heading uses different casing, with fixture-backed
	regression coverage.
- Hardened CCLD facility number extraction for source layouts where a standalone
	`FACILITY NUMBER` label is followed by the facility number value, with
	fixture-backed regression coverage.
- Hardened CCLD facility name extraction for source layouts where a standalone
	`FACILITY NAME` label is followed by the facility name value, with
	fixture-backed regression coverage.
- Hardened CCLD complaint control number extraction for source layouts where a
	standalone `COMPLAINT CONTROL NUMBER` label is followed by the complaint
	control number value, with fixture-backed regression coverage.
- Hardened CCLD visit date extraction for source layouts where a standalone
	`VISIT DATE` label is followed by the visit date value, with fixture-backed
	regression coverage.
- Hardened CCLD date signed extraction for source layouts where a standalone
	`Date Signed` label is followed by the signed date value, with fixture-backed
	regression coverage.
- Hardened CCLD report date extraction for source layouts where a standalone
	`Report Date` label is followed by the date value, with fixture-backed
	regression coverage.
- Hardened CCLD complaint received date extraction for source layouts that use a
	`complaint was received in our office on` narrative phrase, with
	fixture-backed regression coverage.
- Hardened CCLD finding extraction for source layouts where an inline `Finding -`
	label precedes the normalized finding value, with fixture-backed regression
	coverage.
- Hardened CCLD finding extraction for source layouts where normalized finding
	values include trailing punctuation, with fixture-backed regression coverage.
- Hardened CCLD allegation extraction for source layouts that use allegation
	section headings without a trailing colon, with fixture-backed regression
	coverage.
- Hardened CCLD allegation extraction for source layouts that use an
	`INVESTIGATION FINDING:` section heading variant, with fixture-backed
	regression coverage.
- Hardened CCLD allegation extraction for source layouts that use an
  `ALLEGATIONS:` section heading variant, with fixture-backed regression
  coverage.
- Hardened CCLD finding extraction for source layouts where a standalone
	`Finding` label is followed by the normalized finding value on the next line,
	with fixture-backed regression coverage.
- Hardened CCLD allegation extraction for source layouts where one allegation
	wraps across adjacent lines, with fixture-backed regression coverage.
- Hardened CCLD finding extraction for source layouts where the normalized
  finding appears after an explicit `Finding:` label, with fixture-backed
  regression coverage.
- Improved sample and live fetch script output by grouping next review steps by
	task: what to open first, delay triage, source verification, CSV export, and
	other useful review paths.
- Hardened CCLD complaint received date extraction for source layouts where the
	received date appears inline in the narrative sentence, with fixture-backed
	regression coverage.
- Added fixture-backed CCLD missing visit date coverage to preserve report-date
	proxy delay review behavior and source traceability.
- Established the governed CCLD complaints proof-of-concept structure, including
	project charter, data contract, source connector contract, testing strategy,
	documentation strategy, accessibility requirements, security rules, decision
	log, and Copilot instructions.
- Adopted Python, SQLite, and Datasette for local ingestion, storage, and review
	without a custom frontend during the proof of concept.
- Added the CCLD connector workflow for discovering explicitly provided facility
	report records, preserving raw source files, computing raw SHA-256 hashes, and
	normalizing extracted records.
- Added fixture-backed sample ingestion and regression coverage for known CCLD
	reports.
- Added controlled live fetch scripts for explicitly provided facility numbers,
	including multi-facility input and request-limit controls.
- Added SQLite persistence for facility, source document, complaint, allegation,
	event, and extraction audit records.
- Added Datasette review views, metadata labels, column descriptions, and saved
	query examples for complaint review, facility summaries, delay review flags,
	source traceability, and CSV export workflows.
- Added design and usability governance for local review workflows, including
	plain-language delay flag guidance and accessible export expectations.
- Added documentation validation for required governance, user, developer,
	roadmap, changelog, setup, runbook, and Copilot workflow guidance.
- Expanded documentation validation to cover all required developer docs and
	the required user searching and filtering guide.
- Added release checklist guidance for validation, accessibility review, PR
	checks, merge cleanup, and next-task handoff.
- Added next-task selection guidance so Copilot handoffs prefer active roadmap
	product and technical milestones over repeated documentation-only work.
- Added copy/paste-safe handoff formatting rules for PowerShell commands, PR
	title/body separation, post-merge cleanup, and next-branch creation.
- Improved Datasette review usability with additional source-traceable saved
	queries and clearer script launch guidance for common review workflows.
- Added a local review bundle export script that writes complaint review, delay
	triage, and source traceability CSV files with source URL, raw hash, connector
	metadata, retrieval time, report index, and delay-flag caution notes.
- Hardened CCLD allegation extraction for report layouts where numeric allegation
	markers and allegation text appear on the same line, with fixture-backed
	regression coverage.
- Added governance rules requiring bug and CI-failure fixes to include root-cause
	governance review, and requiring raw fixture hashes to be verified against
	Git-normalized fixture bytes governed by `.gitattributes`.
- Added GitHub CLI governance for repeatable PR status checks, check watching,
	squash merge automation, and authentication-secret hygiene.
- Added live fetch summary output so reviewers can see discovered, selected,
	skipped, fetched, written, and failed report counts before opening logs.
- Tightened GitHub CLI completion governance so automated PR workflows still
	include the next branch and exact next Copilot prompt, and so roadmap work
	continues through explicit user checkpoints rather than unattended loops.
- Added governance requiring GitHub branch protection or repository rulesets for
	`main`, with required `validate`, `docs-check`, `fixtures`, and `security`
	status checks before squash merge, plus `gh` availability verification before
	PR automation.
- Added a local output accessibility checklist covering Datasette views,
	generated metadata, saved queries, CSV exports, review bundles, and script
	output.
- Added a `complaint_review_start_here` Datasette saved query with source URL,
	raw hash, connector metadata, retrieval time, and report index for guided
	review and export-safe triage.
- Added a `review_home` Datasette saved query that gives reviewers one
	task-based start-here surface for complaint review, delay triage, facility
	comparison, source verification, and CSV export paths before any dashboard or
	custom web interface decision.
- Added contextual help to primary Datasette review views and saved queries so
	reviewers can see when to use each item, what not to conclude, and what source
	traceability to preserve when exporting.
- Added a low-noise `complaint_first_pass_review` Datasette view and guided
	query path that hide implementation-heavy fields during first-pass review
	while preserving source URL, raw hash, raw path, connector metadata,
	retrieval time, report index, and lower-level IDs for follow-up.
- Updated the roadmap to prioritize incremental local review usability work,
	including a review home, task-based workflow grouping, contextual help,
	low-noise review views, script-output navigation, and a web app transition
	path that later informed the Datasette primary review UX exit decision.
