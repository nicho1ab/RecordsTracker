# Searching and Filtering

Use the browse/search interface to filter by:

- Facility name
- Facility number
- Complaint received date
- Report date
- Finding
- Allegation category
- Delay threshold

Use source links to verify extracted data.

## Saved query examples

When you open Datasette with the metadata command printed by the sample or live fetch script, these saved query examples are available:

- `review_home` gives one start-here task menu for complaint review, delay triage, facility comparison, source verification, and CSV export paths.
- `public_record_allegation_search` searches source-derived allegation text, allegation categories, and findings by keyword or phrase while preserving complaint dates, review flags, source URL, raw hash, connector metadata, retrieval timestamp, and report index.
- `complaint_timeline_by_facility` filters complaint milestone dates and extracted event dates by facility number with source traceability visible.
- `complaint_review_start_here` opens a guided complaint review list with source URL, raw SHA-256 hash, connector metadata, retrieval time, and report index.
- `complaints_by_facility` filters the main complaint review view by facility number.
- `complaint_review_export_with_traceability` prepares complaint review fields with source traceability columns for CSV export.
- `records_with_delay_review_flags` lists records with one or more delay or review flags.
- `facilities_with_delay_review_flags` ranks facilities by records with delay or review flags for triage.
- `facility_patterns_with_review_flags` ranks facilities with records flagged for review and includes finding mix, allegation categories, missingness, report-date proxy counts, and source document counts.
- `repeated_facility_category_findings` lists facility/category/finding rows that appear across more than one facility in the local derived dataset.
- `source_traceability_check` helps check source URLs, raw hashes, connector metadata, retrieval time, and report indexes.
- `source_traceability_by_facility` filters source traceability details by facility number.
- `multi_facility_source_traceability_by_facility` filters source traceability status and linked derived-record counts by facility number.
- `field_traceability_by_facility` filters extracted fields, source text, extraction warnings, confidence, and source document traceability by facility number.
- `allegation_summary_by_facility` summarizes complaint and allegation counts by facility.
- `newest_reports` lists the most recently retrieved source documents first.

Read the saved query description before running or exporting it. The descriptions explain when to use the query, what not to conclude, and which source traceability fields to preserve.

Use `delay_review_flags` and the saved delay query as triage aids only. Delay flags do not prove that an investigation was delayed.

Use `public_record_allegation_search` as a discovery aid only. A keyword match means the term appears in the local derived dataset fields searched by the query; it is not a legal conclusion and it is not a complete public portal search.

Use `complaint_timeline_by_facility` when date sequence matters. Missing timeline dates are unknown in the derived dataset; absence from the timeline does not prove an event did not occur.
