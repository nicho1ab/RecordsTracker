# Exporting Data

Exports should include clear headers and source traceability fields.

## Export a local review bundle

After populating the local SQLite database, use the review bundle script to write source-traceable CSV files and a short README with review cautions:

```powershell
.\scripts\export-review-bundle.ps1
```

The default output folder is `data/processed/review-bundle`. Use `-DbPath` and `-OutputDir` when exporting from a custom database path:

```powershell
.\scripts\export-review-bundle.ps1 -DbPath data\processed\live-ccld.sqlite -OutputDir data\processed\live-review-bundle
```

The bundle includes:

- `complaint_review_with_source_traceability.csv` for complaint review fields with source URL, raw SHA-256 hash, raw path, connector metadata, retrieval timestamp, and report index.
- `delay_review_flags_with_source_traceability.csv` for triage records with one or more review flags and the same source traceability fields.
- `source_traceability.csv` for checking source URL, raw hash, connector metadata, retrieval time, report index, document type, and content type.
- `README.md` with review notes and delay-flag caution language.

Unknown database values are exported as `unknown`. Delay review flags in the bundle are screening aids for closer review, not conclusions that an investigation was delayed.

## Export from Datasette

1. Open the table you want to review.
2. Apply any needed filters in Datasette.
3. Use Datasette's CSV export link for the filtered table or query.
4. Keep the header row in the exported CSV.
5. Keep source traceability columns in review exports so each record can be checked against the public source.

For complaint review, start with the `complaint_review_summary` view because it includes complaint fields, allegation count and summary, delay review fields, source URL, and raw path in one export. Use `facility_complaint_summary` for facility-level counts, `delay_review_flags` for records that need closer delay review, and `source_traceability_review` when checking source URLs, raw hashes, connector metadata, retrieval time, and report indexes.

If you are unsure which export path to use, open the `review_home` saved query first. Its export row points to `complaint_review_export_with_traceability` and reminds reviewers to keep clear headers plus source URL, raw hash, connector metadata, retrieval time, and report index when available.

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
