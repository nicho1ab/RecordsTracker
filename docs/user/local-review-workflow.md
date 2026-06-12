# Local Review Workflow

This guide describes the first local review workflow for non-technical reviewers using Datasette. It uses the existing SQLite database, review views, metadata, and saved query examples. It is not a custom web application.

## What to open first

After running the sample or live fetch script, open the Datasette command printed by the script. The command includes a metadata file that adds clearer labels, descriptions, column notes, and saved query examples.

On the Datasette database page, use the review view titles and descriptions from the metadata as the starting guide. The metadata also labels the normalized tables for lower-level checks, but routine browsing should begin with the review views.

Open these views first:

1. `complaint_review_summary` for the main complaint review across facilities.
2. `facility_complaint_summary` for facility-level counts and date ranges.
3. `delay_review_flags` for records with one or more review flags.
4. `source_traceability_review` to verify public source URL, raw hash, connector details, retrieval time, and report index.

Use normalized tables such as `complaints`, `allegations`, `source_documents`, and `extraction_audit` only when you need lower-level detail.

## What each view means

`complaint_review_summary` combines the most useful review fields in one place: facility number, facility name, complaint control number, complaint dates, finding, allegation count and summary, delay calculation fields, review flags, source URL, and raw path.

`facility_complaint_summary` gives one row per facility. Use it to compare complaint counts, allegation counts, the earliest and latest complaint received dates, and how many records have delay review flags.

`delay_review_flags` is a filtered triage list. A record appears here when one or more delay or review flags is set. This view helps reviewers decide what to inspect next; it does not prove an investigation was delayed.

`source_traceability_review` helps verify where each derived record came from. It includes source URL, raw SHA-256 hash, raw path, connector name, connector version, retrieval timestamp, report index, document type, and content type.

## How to find concerning records

Start with `delay_review_flags` when looking for records that may need closer review. Sort by `days_received_to_report` or `days_received_to_visit` descending to review larger calculated intervals first.

Then open the matching row in `complaint_review_summary` and check the dates, allegation summary, finding, source URL, and raw path. If the first investigation activity date is missing, say that directly. Do not treat a missing date as proof that an activity did not happen.

Use neutral language such as "flagged for review based on available extracted dates." Do not describe a record as a delayed investigation based only on a delay flag, report date, or proxy field.

## How to filter by facility

In Datasette, open `complaint_review_summary` and filter `facility_number` to the facility you want to review, such as `157806098` or `157806097` when those records are present in your local database.

You can also open the saved query named `complaints_by_facility` and enter a facility number when prompted.

For high-level comparison, open `facility_complaint_summary` and sort by `complaint_count`, `allegation_count`, or `records_with_delay_review_flags`.

## How to inspect source documents

Open `source_traceability_review` before relying on extracted complaint fields. Check that each record has a source URL, raw SHA-256 hash, connector name, connector version, retrieval timestamp, and report index when available.

Use `source_url` to compare against the public source. Use `raw_path` and `raw_sha256` to identify the locally preserved source content that was used for extraction.

Do not redistribute raw narrative text unless it is needed for the review purpose. Public complaint content may still include sensitive narrative details.

## How to export accessible CSVs

Use Datasette's CSV export for a filtered view or saved query. Keep the header row and source traceability columns in the export.

To export the standard local review bundle without opening Datasette, run:

```powershell
.\scripts\export-review-bundle.ps1
```

This writes complaint review, delay triage, and source traceability CSV files under `data/processed/review-bundle` by default. The complaint and delay CSV files include source URL, raw SHA-256 hash, raw path, connector metadata, retrieval timestamp, and report index. Unknown database values are exported as `unknown`.

For complaint review exports, start with `complaint_review_summary`. For source checks, export `source_traceability_review`. For delay triage, export `delay_review_flags` and label the file or notes as a triage list, not a list of delayed investigations.

For accessible CSV review:

- Keep clear column headers.
- Do not replace headers with unexplained abbreviations.
- Do not use color alone to communicate findings, warnings, or status.
- Include a note that delay review flags are screening aids, not conclusions.
- Include a note that the public portal remains the source of record.
- Avoid personal paths, account names, emails, private URLs, or machine-specific details.

## Saved query examples

The generated Datasette metadata includes saved query examples:

- `complaint_review_start_here` opens a review-ready complaint list with facility context, delay screening fields, source URL, raw SHA-256 hash, connector metadata, retrieval time, and report index.
- `complaints_by_facility` filters `complaint_review_summary` by facility number and prompts for the facility number.
- `complaint_review_export_with_traceability` exports complaint review fields with source URL, raw hash, raw path, connector metadata, retrieval time, and report index.
- `records_with_delay_review_flags` opens the delay triage list with review flags described as screening aids.
- `facilities_with_delay_review_flags` ranks facilities by records with delay or review flags. Treat the counts as triage aids, not conclusions.
- `source_traceability_check` lists source URL, raw hash, connector metadata, retrieval time, and report index.
- `source_traceability_by_facility` filters source traceability details by facility number.
- `allegation_summary_by_facility` summarizes complaint and allegation counts by facility.
- `newest_reports` sorts source documents by retrieval timestamp and report index.

These saved queries are review aids. Start with `complaint_review_start_here` when you want a guided, source-traceable complaint list before choosing a narrower filter. If you export query results, keep clear headers and source traceability fields where available.

## What not to conclude

The local database is a derived review aid. The public portal remains the source of record.

Do not conclude that the extracted data is complete, authoritative, or free of extraction errors. Source reports may be incomplete, corrected later, removed, or formatted differently across time.

Do not conclude that an investigation was delayed based only on `delay_review_flags`, `days_received_to_report`, or `report_date_used_as_proxy`. Report date may not equal first investigation activity date.

Do not treat missing dates as evidence that an event did not occur. Missing dates should be described as missing from the extracted fields and checked against the source report when the issue matters.