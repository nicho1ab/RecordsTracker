# Changelog

## Unreleased

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
- Added data contract, connector contract, testing strategy, documentation strategy, accessibility requirements, and GitHub Copilot instructions.
