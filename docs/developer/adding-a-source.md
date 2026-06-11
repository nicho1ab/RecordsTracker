# Adding a Source

## Required steps

1. Create `src/ccld_complaints/connectors/<source>/`.
2. Implement the source connector contract.
3. Add source documentation.
4. Add at least three raw fixtures.
5. Add expected JSON fixture outputs.
6. Add connector contract tests.
7. Update known limitations.
8. Update user docs if new fields or behavior are exposed.

## Required review

A source connector cannot be accepted until it passes:

- Unit tests
- Fixture tests
- Data contract validation
- Accessibility review for any user-facing output
- Documentation checks

## CCLD FacilityReports baseline

The CCLD connector discovers public FacilityReports URLs from the facility detail page for facility `157806098`. Discovery normalizes each rendered report link into a source document candidate with source name, facility number, report index, source URL, visible report date, and optional discovery timestamp. Duplicate URLs and duplicate report indexes are removed before candidates are returned.

Discovery does not download or parse each report body. Fetching, raw storage, extraction, normalization, validation, and emission remain separate connector contract steps.

The initial deterministic extraction fixture targets report index `3`. It extracts labeled HTML fields deterministically and normalizes them into the existing facility, source document, complaint, allegation, and extraction audit records without adding source-specific canonical columns.

The initial single-facility ingestion helper returns validated records in memory and records per-candidate failures. Offline tests should inject fixture loaders for report bodies; live fetching is only used when no loader is provided, and raw content is stored before extraction.
