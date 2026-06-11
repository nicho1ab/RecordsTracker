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

Use this lightweight checklist for generated or local proof-of-concept outputs, including the sample SQLite database, Datasette browsing views, CSV exports, and review notes:

- The reviewer can identify which table to open first and what each table represents.
- Table and column names match the data contract or user data dictionary.
- CSV exports keep clear header rows.
- CSV exports keep source traceability fields such as source URL, raw SHA-256 hash, connector name, and retrieval timestamp when available.
- Delay fields and review flags are described as screening aids, not conclusions.
- Missing dates are described as unknown, not as proof that an event did not occur.
- Public source limitations are visible in review guidance.
- No output relies on color alone to communicate status, findings, or warnings.
- Browser review preserves keyboard navigation, visible focus, readable zoom, and understandable table headers.
- Generated examples do not include personal local paths, usernames, emails, private URLs, account names, or machine-specific details.
