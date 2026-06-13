# Accessibility Testing Guide

## Manual checklist

Before release, verify:

- Pages are usable with keyboard only.
- Focus indicators are visible.
- Tables have clear column headers.
- Link text is descriptive.
- No instruction relies only on color.
- Headings are structured in order.
- Data exports have clear headers.
- Known issues are documented.

## Tools

Use available browser accessibility tools and manual review. Do not rely only on automated checks.

## Datasette review

For Datasette views, check:

- Table headings are understandable.
- Search and filter controls are keyboard accessible.
- Source links are descriptive.
- Any custom templates preserve semantic HTML.

## Local output checklist

Use this lightweight checklist for generated or local proof-of-concept outputs,
including Datasette views, generated Datasette metadata, saved queries, CSV
exports, review bundle files, and script output.

### Datasette views

- The reviewer can identify which view to open first and what each view
	represents.
- Review views start with useful context such as facility number, facility name,
	complaint control number when available, dates, findings, and source details.
- Table and column names match the data contract or user data dictionary.
- Browser review preserves keyboard navigation, visible focus, readable zoom,
	and understandable table headers.
- No view relies on color alone to communicate status, findings, warnings, or
	review flags.

### Generated metadata

- Generated Datasette metadata includes plain-language table or view titles and
	descriptions.
- Metadata column descriptions explain source traceability, delay fields,
	review flags, unknown values, and extraction confidence when those fields are
	present.
- Metadata guides reviewers toward review views before lower-level normalized
	tables.
- Metadata examples do not include personal local paths, usernames, emails,
	private URLs, account names, tokens, or machine-specific details.

### Saved queries

- Saved query names and descriptions explain the review task they support.
- Parameter prompts have accessible names and do not require unexplained field
	names.
- Saved queries that may be exported include source traceability fields such as
	source URL, raw SHA-256 hash, connector name, connector version, retrieval
	timestamp, and report index when available.
- At minimum, source traceability output should preserve source URL, raw SHA-256 hash, connector name, and retrieval timestamp when those fields are available.
- Queries that show delay review flags describe them as screening aids, not
	conclusions.

### CSV exports and review bundles

- CSV exports keep clear header rows from the database, data dictionary, or
	review bundle contract.
- CSV exports keep source traceability fields such as source URL, raw SHA-256
	hash, connector name, connector version, retrieval timestamp, and report index
	when available.
- Export README or surrounding notes explain that exported data is a derived
	review aid and that the public portal remains the source of record.
- Delay fields and review flags are described as screening aids, not
	conclusions.
- Missing dates are described as unknown, not as proof that an event did not
	occur.

### Script output

- Script output tells reviewers what file, database, Datasette command, or view
	to open next.
- Summary lines use plain text and labels, not color-only status.
- Failure summaries include enough context for follow-up without exposing
	secrets or unnecessary sensitive narrative text.
- Public source limitations are visible in review guidance when script output
	points to exported or derived records.
