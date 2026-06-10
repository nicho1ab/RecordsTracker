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

The initial CCLD connector implementation targets the public FacilityReports endpoint for facility `157806098`, report index `3`. It extracts labeled HTML fields deterministically and normalizes them into the existing facility, source document, complaint, allegation, and extraction audit records without adding source-specific canonical columns.
