# Changelog

## Unreleased

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
	path before deciding whether Datasette has been outgrown.
