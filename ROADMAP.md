# Roadmap

This roadmap reflects the current proof-of-concept state. The project is an
active CCLD complaints ingestion and local review workflow, not a blank
governance scaffold.

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
- Added fixture-backed extraction and regression coverage for known CCLD reports.
- Preserved raw source files and SHA-256 hashes before extraction.
- Normalized extracted records into facility, source document, complaint,
	allegation, event, and extraction audit records.
- Wrote normalized records to SQLite with idempotent upsert behavior.
- Added controlled live fetch for explicitly provided facility numbers.
- Added multi-facility input for live fetch workflows scoped to user-provided
	facility numbers.
- Added SQLite review views for complaint review, facility summaries, delay
	review flags, and source traceability.
- Added Datasette metadata and saved queries to guide review, filtering,
	source-checking, and export workflows.

## Completed governance and review experience improvements

- Added design and usability governance for the local Datasette review
	experience.
- Documented delay review flags as screening aids, not conclusions.
- Documented accessible CSV export expectations and source traceability review.
- Added documentation checks to guard against stale scaffold language and missing
	required public guidance.
- Added Copilot workflow guidance for small, testable changes under the project
	governance rules.

## Near-term milestones

- Keep roadmap, changelog, setup, runbook, and Copilot workflow documentation
	current after each meaningful capability or workflow change.
- Harden extraction with additional representative fixtures and edge-case tests.
- Expand narrative date and event extraction only when source text, confidence,
	and fixture-backed regression tests are included.
- Strengthen data quality checks for duplicates, date consistency, source hash
	presence, and raw source traceability.
- Improve local review documentation for repeated reviewer tasks and export
	cautions.
- Add release checklist guidance for validation, accessibility review, PR checks,
	merge cleanup, and next-task handoff.

## Decision points

- Decide when the proof of concept has enough fixture coverage to treat CCLD
	extraction as stable for broader review.
- Decide whether collaborative review needs a lightweight correction table,
	correction import workflow, or an external review tool.
- Decide whether Baserow, Metabase, or another tool provides enough value to
	justify adding it outside the baseline workflow.
- Decide when to add a second public source connector under the source connector
	contract.
- Decide what accessibility checks are required before any public or stable
	release.
- Decide whether and when a custom frontend is justified by validated product
	needs rather than visual polish.

## Deferred product work

- Custom frontend application.
- Hosted review queues, reviewer accounts, assignments, or role-based access
	control.
- Interactive dashboards beyond the local SQLite and Datasette proof of concept.
- PDF report generation unless accessibility can be validated.
- Optional paid platform dependencies unless explicitly approved and documented.
- Statewide crawling or automatic search expansion beyond explicitly provided
	facility numbers.
