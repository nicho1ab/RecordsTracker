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

- `complaints_by_facility` filters the main complaint review view by facility number.
- `complaint_review_export_with_traceability` prepares complaint review fields with source traceability columns for CSV export.
- `records_with_delay_review_flags` lists records with one or more delay or review flags.
- `facilities_with_delay_review_flags` ranks facilities by records with delay or review flags for triage.
- `source_traceability_check` helps check source URLs, raw hashes, connector metadata, retrieval time, and report indexes.
- `source_traceability_by_facility` filters source traceability details by facility number.
- `allegation_summary_by_facility` summarizes complaint and allegation counts by facility.
- `newest_reports` lists the most recently retrieved source documents first.

Use `delay_review_flags` and the saved delay query as triage aids only. Delay flags do not prove that an investigation was delayed.
