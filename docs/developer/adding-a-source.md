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
