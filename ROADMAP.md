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
- Added fixture-backed hardening for numbered allegation rows in CCLD report
	layouts.
- Preserved raw source files and SHA-256 hashes before extraction.
- Normalized extracted records into facility, source document, complaint,
	allegation, event, and extraction audit records.
- Wrote normalized records to SQLite with idempotent upsert behavior.
- Added controlled live fetch for explicitly provided facility numbers.
- Added multi-facility input for live fetch workflows scoped to user-provided
	facility numbers.
- Added live fetch summary output for discovered, selected, skipped, fetched,
	written, and failed report counts.
- Added SQLite review views for complaint review, facility summaries, delay
	review flags, and source traceability.
- Added a low-noise first-pass complaint review view that preserves source
	traceability and lower-level IDs while hiding implementation-heavy fields from
	the initial review surface.
- Added Datasette metadata and saved queries to guide review, filtering,
	source-checking, and export workflows.
- Added a source-traceable start-here saved query for guided complaint review in
	Datasette.
- Added a `review_home` Datasette saved query as a task-based start-here surface
	for complaint review, delay triage, facility comparison, source verification,
	and CSV export paths before any dashboard or custom web interface decision.
- Added contextual help to primary Datasette review views and saved queries for
	when to use each item, what not to conclude, and what source traceability to
	preserve when exporting.
- Added a local review bundle export workflow for source-traceable complaint
	review, delay triage, and source traceability CSV files.
- Grouped sample and live fetch script next steps by reviewer task, including
	what to open first, delay triage, source verification, and CSV export.
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

## Near-term milestones

- Keep roadmap, changelog, setup, runbook, and Copilot workflow documentation
	current after each meaningful capability or workflow change.
- Reduce review noise and increase reviewer signal through task-based local
	review improvements before deciding whether a dashboard or custom web
	application is justified.
- Harden extraction with additional representative fixtures and edge-case tests.
- Expand narrative date and event extraction only when source text, confidence,
	and fixture-backed regression tests are included.
- Strengthen data quality checks for duplicates, date consistency, source hash
	presence, and raw source traceability.
- Improve local review documentation for repeated reviewer tasks and export
	cautions.
- Keep release checklist guidance current as validation, accessibility, and PR
	workflow requirements evolve.

## Current next priorities

These priorities should be implemented as incremental local review improvements
before deciding whether Datasette has been outgrown or a dashboard/custom web
interface is justified.

1. Group review workflows by user task rather than by implementation table,
	using task labels such as review complaints, find records needing closer
	review, compare facilities, verify sources, and export CSVs.
2. Add additional CCLD fixtures and extraction hardening for representative
	report layouts, missing fields, and edge cases.
3. Evaluate persistent navigation, lightweight dashboard options, or a custom
	web interface only after the task-based Datasette review workflow is validated
	and documented as sufficient or insufficient for repeated review.

## Web app transition path

Datasette remains useful as the proof-of-concept review surface while the team
validates data quality, extraction behavior, source traceability, review language,
and task-based workflows. The project should treat Datasette as outgrown when
reviewers repeatedly need capabilities it cannot provide cleanly, such as
persistent navigation, grouped task dashboards, guided review queues, saved user
state, annotations, correction workflows, richer contextual help, or fewer-click
paths that Datasette metadata and saved queries cannot reasonably support.

Before building the eventual web app, use the local review workflow to identify
and test the smallest useful product shape:

1. Define the core user tasks and the minimum fields each task needs.
2. Keep SQLite views, saved queries, and exports as the stable data access layer.
3. Prototype low-noise review surfaces locally before adding accounts, hosted
	infrastructure, or role-based workflows.
4. Preserve source traceability, accessibility, and public-source caution
	language as non-negotiable web app requirements.
5. Decide whether to extend Datasette with templates/plugins, add a lightweight
	dashboard, or start a custom frontend based on validated reviewer friction.

## Decision points

- Decide when the proof of concept has enough fixture coverage to treat CCLD
	extraction as stable for broader review.
- Decide whether collaborative review needs a lightweight correction table,
	correction import workflow, or an external review tool.
- Decide whether Baserow, Metabase, or another tool provides enough value to
	justify adding it outside the baseline workflow.
- Decide whether repeated reviewer friction means Datasette should remain the
	local validation surface while a separate web app becomes the primary user
	experience.
- Decide when to add a second public source connector under the source connector
	contract.
- Decide what accessibility checks are required before any public or stable
	release.
- Decide whether and when a custom frontend is justified by validated product
	needs rather than visual polish.

## Deferred product work

- Custom frontend application, unless the web app transition path confirms that
	Datasette cannot provide the needed persistent navigation, grouped review
	workflows, contextual help, and few-click task paths.
- Hosted review queues, reviewer accounts, assignments, or role-based access
	control.
- Interactive dashboards beyond the local SQLite and Datasette proof of concept.
- PDF report generation unless accessibility can be validated.
- Optional paid platform dependencies unless explicitly approved and documented.
- Statewide crawling or automatic search expansion beyond explicitly provided
	facility numbers.
