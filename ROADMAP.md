# Roadmap

## Phase 0: Governance and scaffolding

- Establish repo structure.
- Add Copilot instructions and prompts.
- Add data contract and connector contract.
- Add testing, documentation, accessibility, and security rules.
- Add local setup and CI workflows.

## Phase 1: CCLD single-facility POC

- Implement CCLD connector discovery for one facility.
- Download/store raw report files.
- Extract fields from complaint reports.
- Write records to SQLite.
- Generate Datasette browse/search interface.
- Add fixture-based tests for known reports.

## Phase 2: Extraction hardening

- Add additional report fixtures.
- Add narrative date/event extraction.
- Add extraction confidence and audit records.
- Add duplicate detection and raw source hash validation.
- Add edge-case tests for report types and missing fields.

## Phase 3: Multi-facility support

- Expand discovery to multiple facilities.
- Add facility-level summary exports.
- Add batch reprocessing commands.
- Add data quality dashboard queries.

## Phase 4: Review workflow

- Add export/review workflow for extracted rows.
- Add correction import or lightweight review table.
- Evaluate whether Baserow provides sufficient value for collaborative review.

## Phase 5: Multi-source support

- Add a second connector under the source connector contract.
- Validate canonical object model with a distinct source structure.
- Update documentation and known limitations.

## Phase 6: Public presentation hardening

- Validate accessibility requirements.
- Add accessible end-user documentation.
- Add release checklist and publication workflow.
