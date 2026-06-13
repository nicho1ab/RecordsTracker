# Local Review Workflow

This guide describes the first local review workflow for non-technical reviewers using Datasette. It uses the existing SQLite database, review views, metadata, and saved query examples. It is not a custom web application.

## What to open first

After running the sample or live fetch script, open the Datasette command printed by the script. The command includes a metadata file that adds clearer labels, descriptions, column notes, and saved query examples. The scripts also print grouped next steps for what to open first, delay triage, source verification, CSV export, and other useful review paths.

On the Datasette database page, open the `review_home` saved query first. It gives one task-based starting place for the local review workflow and points to the complaint review, delay triage, facility comparison, source verification, and CSV export paths. The `workflow_group` column labels each path by reviewer task so you can scan by purpose before opening a view or saved query. This is an incremental Datasette review aid, not a dashboard or custom web application.

Then open `complaint_review_start_here` or `complaint_first_pass_review` for a low-noise complaint list that preserves facility context, a single review flag summary, source URL, raw SHA-256 hash, raw path, connector metadata, retrieval time, report index, and lower-level IDs for follow-up.

For public-record discovery, open `public_record_allegation_search` and enter a cautious keyword or phrase. The saved query searches source-derived allegation text, allegation categories, and findings while keeping complaint dates, review flags, source URL, raw SHA-256 hash, raw path, connector metadata, retrieval time, report index, and lower-level IDs visible. Treat results as screening aids over the derived dataset, not as legal conclusions or a complete public portal search.

Use the review view titles and descriptions from the metadata as the next guide. The metadata gives short contextual help for when to use each primary view or saved query, what not to conclude from it, and which source traceability fields to preserve when exporting. The metadata also labels the normalized tables for lower-level checks, but routine browsing should begin with the review home, guided complaint query, and review views.

Use the printed groups as quick navigation after each sample or live fetch run: open first with `review_home`, `complaint_review_start_here`, or `complaint_first_pass_review`; use `public_record_allegation_search` for public-record discovery; use `complaint_timeline_review` for timeline review; use `delay_review_flags` for delay triage; use `source_traceability_review` and `field_source_traceability_review` for source verification; and use `complaint_review_export_with_traceability` or `export-review-bundle.ps1` for source-traceable CSV export.

Open these views first:

1. `complaint_first_pass_review` for low-noise first-pass complaint review.
2. `complaint_timeline_review` for complaint milestone dates and extracted event dates with source traceability.
3. `complaint_review_summary` for the fuller complaint review across facilities.
4. `facility_complaint_summary` for facility-level counts and date ranges.
5. `delay_review_flags` for records with one or more review flags.
6. `source_traceability_review` to verify public source URL, raw hash, connector details, retrieval time, and report index.
7. `field_source_traceability_review` to check extracted field values, source text, extraction warnings, confidence, and source document traceability together.

Use normalized tables such as `complaints`, `allegations`, `source_documents`, and `extraction_audit` only when you need lower-level detail.

## What each view means

`review_home` is a saved query that acts as the local start-here surface. Each row names a workflow group, reviewer task, the view or saved query to open next, when to use it, and the caution language to preserve.

`complaint_review_start_here` is a saved query for guided complaint review with source traceability. Use it before narrowing to filters or exports.

`public_record_allegation_search` is a saved query for keyword discovery over source-derived allegation text, allegation categories, and findings. Use it to find records for closer public-source review while preserving source traceability. Do not treat a search match as proof of harm, liability, rights deprivation, abuse, neglect, or any legal element.

`complaint_timeline_review` is a view with one row per extracted complaint milestone date or event date. Use it to see complaint received, first investigation activity when available, visit, report, signature, and extracted event dates in one source-traceable sequence. Missing dates are unknown in the derived dataset; absence from this view does not prove an event did not occur.

`complaint_first_pass_review` is the low-noise first-pass complaint view. It keeps facility details, complaint dates, finding, allegation count and summary, one plain-language review flag summary, source URL, raw SHA-256 hash, raw path, connector metadata, retrieval time, report index, and IDs for lower-level follow-up. It intentionally hides detailed delay calculations, separate flag columns, and extraction confidence from the first screen.

`complaint_review_summary` is the fuller complaint review view. Open it when you need detailed delay calculations, separate review flag columns, extraction confidence, or the broader complaint review context after first-pass triage.

`facility_complaint_summary` gives one row per facility. Use it to compare complaint counts, allegation counts, the earliest and latest complaint received dates, and how many records have delay review flags.

`delay_review_flags` is a filtered triage list. A record appears here when one or more delay or review flags is set. This view helps reviewers decide what to inspect next; it does not prove an investigation was delayed.

`source_traceability_review` helps verify where each derived record came from. It includes source URL, raw SHA-256 hash, raw path, connector name, connector version, retrieval timestamp, report index, document type, and content type.

`field_source_traceability_review` helps verify specific extracted fields. It combines extraction audit context with complaint context and source document traceability, including extracted value, source text, source section, warning, confidence, extraction method, extractor version, source URL, raw SHA-256 hash, connector metadata, retrieval timestamp, and report index.

## How to find concerning records

Start with `delay_review_flags` when looking for records that may need closer review. Sort by `days_received_to_report` or `days_received_to_visit` descending to review larger calculated intervals first.

Then open the matching row in `complaint_first_pass_review` and check the dates, allegation summary, finding, source URL, raw hash, and raw path. Open `complaint_review_summary`, `source_traceability_review`, or the normalized tables when you need detailed delay calculations, extraction confidence, or lower-level source detail. If the first investigation activity date is missing, say that directly. Do not treat a missing date as proof that an activity did not happen.

Use neutral language such as "flagged for review based on available extracted dates." Do not describe a record as a delayed investigation based only on a delay flag, report date, or proxy field.

## How to filter by facility

In Datasette, open `complaint_first_pass_review` and filter `facility_number` to the facility you want to review, such as `157806098` or `157806097` when those records are present in your local database. Use `complaint_review_summary` when you need the detailed delay columns for the same facility.

You can also open the saved query named `complaints_by_facility` and enter a facility number when prompted.

For high-level comparison, open `facility_complaint_summary` and sort by `complaint_count`, `allegation_count`, or `records_with_delay_review_flags`.

## How to inspect source documents

Open `source_traceability_review` before relying on extracted complaint fields. Check that each record has a source URL, raw SHA-256 hash, connector name, connector version, retrieval timestamp, and report index when available.

Open `field_source_traceability_review` or `field_traceability_by_facility` before relying on a specific extracted field. Check the source text, source section, extraction warning, confidence, extraction method, and extractor version together with the source URL and raw hash.

Use `source_url` to compare against the public source. Use `raw_path` and `raw_sha256` to identify the locally preserved source content that was used for extraction.

Do not redistribute raw narrative text unless it is needed for the review purpose. Public complaint content may still include sensitive narrative details.

## How to export accessible CSVs

Use Datasette's CSV export for a filtered view or saved query. Keep the header row and source traceability columns in the export.

To export the standard local review bundle without opening Datasette, run:

```powershell
.\scripts\export-review-bundle.ps1
```

This writes complaint review, delay triage, and source traceability CSV files under `data/processed/review-bundle` by default. The complaint and delay CSV files include source URL, raw SHA-256 hash, raw path, connector metadata, retrieval timestamp, and report index. Unknown database values are exported as `unknown`.

For low-noise first-pass complaint exports, start with `complaint_first_pass_review`. For detailed complaint review exports, use `complaint_review_summary` or `complaint_review_export_with_traceability`. For source checks, export `source_traceability_review`. For delay triage, export `delay_review_flags` and label the file or notes as a triage list, not a list of delayed investigations.

For accessible CSV review:

- Keep clear column headers.
- Do not replace headers with unexplained abbreviations.
- Do not use color alone to communicate findings, warnings, or status.
- Include a note that delay review flags are screening aids, not conclusions.
- Include a note that the public portal remains the source of record.
- Avoid personal paths, account names, emails, private URLs, or machine-specific details.

## Saved query examples

The generated Datasette metadata includes saved query examples:

- `review_home` gives one start-here task menu for review complaints, find records needing closer review, compare facilities, verify sources, and export CSVs.
- `public_record_allegation_search` searches source-derived allegation text, allegation categories, and findings by keyword or phrase while keeping source traceability visible.
- `complaint_timeline_by_facility` filters timeline rows by facility number so reviewers can inspect complaint milestone dates and extracted event dates with source traceability.
- `complaint_review_start_here` opens a low-noise review-ready complaint list with facility context, one review flag summary, source URL, raw SHA-256 hash, raw path, connector metadata, retrieval time, report index, and lower-level IDs.
- `complaints_by_facility` filters `complaint_review_summary` by facility number and prompts for the facility number.
- `complaint_review_export_with_traceability` exports complaint review fields with source URL, raw hash, raw path, connector metadata, retrieval time, and report index.
- `records_with_delay_review_flags` opens the delay triage list with review flags described as screening aids.
- `facilities_with_delay_review_flags` ranks facilities by records with delay or review flags. Treat the counts as triage aids, not conclusions.
- `source_traceability_check` lists source URL, raw hash, connector metadata, retrieval time, and report index.
- `source_traceability_by_facility` filters source traceability details by facility number.
- `field_traceability_by_facility` filters field-level extraction audit context by facility number.
- `allegation_summary_by_facility` summarizes complaint and allegation counts by facility.
- `newest_reports` sorts source documents by retrieval timestamp and report index.

These saved queries are review aids. Start with `review_home` when you need to choose a task, then use `complaint_review_start_here` when you want a guided, source-traceable complaint list before choosing a narrower filter. If you export query results, keep clear headers and source traceability fields where available.

Read the Datasette description above a view or saved query before exporting or quoting from it. The descriptions are intentionally short contextual help, not a replacement for checking the public source record.

## What not to conclude

The local database is a derived review aid. The public portal remains the source of record.

Do not conclude that the extracted data is complete, authoritative, or free of extraction errors. Source reports may be incomplete, corrected later, removed, or formatted differently across time.

Do not conclude that an investigation was delayed based only on `delay_review_flags`, `days_received_to_report`, or `report_date_used_as_proxy`. Report date may not equal first investigation activity date.

Do not treat missing dates as evidence that an event did not occur. Missing dates should be described as missing from the extracted fields and checked against the source report when the issue matters.