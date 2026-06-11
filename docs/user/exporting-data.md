# Exporting Data

Exports should include clear headers and source traceability fields.

## Export from Datasette

1. Open the table you want to review.
2. Apply any needed filters in Datasette.
3. Use Datasette's CSV export link for the filtered table or query.
4. Keep the header row in the exported CSV.
5. Keep source traceability columns in review exports so each record can be checked against the public source.

For complaint review, start with the `complaint_review_summary` view because it includes complaint fields, allegation count and summary, delay review fields, source URL, and raw path in one export. Use `facility_complaint_summary` for facility-level counts, `delay_review_flags` for records that need closer delay review, and `source_traceability_review` when checking source URLs, raw hashes, connector metadata, retrieval time, and report indexes.

If a view does not include all needed low-level fields, export the normalized tables and preserve the ID columns so reviewers can join or compare records.

Recommended export columns:

- Facility number
- Facility name
- Complaint control number
- Complaint received date
- First investigation activity date
- Report date
- Finding
- Allegations
- Source URL
- Raw SHA-256 hash
- Connector name
- Retrieval timestamp

Do not remove source URL or raw hash fields from research exports.

## Accessible CSV review

For accessible tabular output:

- Keep clear column headers from the database or data dictionary.
- Do not replace headers with abbreviations that are not explained.
- Do not communicate findings, warnings, or status by color alone.
- Include a note that delay review flags are screening aids, not conclusions.
- Include a note that the public portal remains the source of record.
- When exporting `delay_review_flags`, label the export as a triage or review list rather than a list of delayed investigations.
- Avoid adding personal paths, account names, emails, private URLs, or machine-specific details to exported files.
- Share CSV or spreadsheet formats with readable headers instead of PDF unless PDF accessibility can be validated.
