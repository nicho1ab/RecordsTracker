# CCLD Complaint Review Bundle

This folder contains derived CSV review outputs from the local SQLite database. The public portal remains the source of record.

## Files

- complaint_review_with_source_traceability.csv: complaint review fields with source URL, raw SHA-256 hash, local raw path, connector metadata, retrieval timestamp, and report index.
- delay_review_flags_with_source_traceability.csv: triage records with one or more review flags, plus source traceability fields.
- source_traceability.csv: source URL, raw SHA-256 hash, local raw path, connector metadata, retrieval timestamp, report index, document type, and content type.
- multi_facility_source_traceability.csv: one row per source document with facility context, traceability status, source metadata, and linked derived-record counts.
- complaint_timeline_with_source_traceability.csv: complaint milestone dates and extracted event dates with source traceability. Missing dates are unknown in the derived dataset.
- field_source_traceability.csv: extracted values, source text, source section, warnings, confidence, extraction method, extractor version, and source document traceability.
- facility_pattern_review.csv: facility-level complaint counts, source document counts, allegation categories, finding mix, missingness, report-date proxy usage, review flag counts, and date ranges.
- facility_comparison_review.csv: facility/category/finding rows with source-document counts, traceability-completeness counts, same-category/finding facility counts, and cautious scope notes.

## Review Notes

- Delay review flags are screening aids for closer review, not conclusions that an investigation was delayed.
- Use language such as "flagged for review based on available extracted dates" when discussing flagged records.
- Unknown database values are exported as "unknown".
- Keep source URL and raw SHA-256 hash columns when sharing or citing review outputs.
- Facility pattern counts and timeline rows are screening aids over the derived dataset, not findings about a facility or proof that an event did or did not occur.
- Multi-facility traceability and comparison rows are source-review aids over the derived dataset, not conclusions about facilities, public-source completeness, or facility-wide conduct.
- Field traceability rows are provided so reviewers can check extracted values against source text, warnings, confidence, and the public source.
- Verify important details against the public source document before relying on extracted fields.
