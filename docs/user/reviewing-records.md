# Reviewing Records

For a step-by-step reviewer workflow, start with [Local Review Workflow](local-review-workflow.md).

## Suggested review steps

1. Open the `review_home` saved query first for the task-based local review paths.
2. Open `public_record_allegation_search` when you need cautious keyword discovery over source-derived allegation text, allegation categories, and findings with source traceability visible.
3. Open `complaint_review_start_here` or `complaint_first_pass_review` for the guided low-noise complaint list with source traceability.
4. Open the `complaint_review_summary` view when you need detailed delay calculations, separate review flag columns, extraction confidence, or broader complaint review context.
5. Open the `facility_complaint_summary` view to compare complaint counts, allegation counts, complaint date range, and delay review flag counts by facility.
6. Open the `delay_review_flags` view to triage records with one or more delay or review flags.
7. Open the `source_traceability_review` view to confirm source URL, raw file hash, raw path, connector name, connector version, retrieval time, and report index.
8. Open the normalized `facilities`, `source_documents`, `complaints`, `allegations`, `events`, and `extraction_audit` tables when you need lower-level detail, source text, confidence, or extraction warnings.
9. Start with records flagged as low confidence when confidence fields are available.
10. Note any extraction issue for correction.

The local database is a derived review aid. The public portal remains the source of record, and source reports may be incomplete, corrected later, removed, or formatted differently across time.

Search matches from `public_record_allegation_search` are screening aids over the derived dataset. They do not prove harm, liability, rights deprivation, abuse, neglect, or any legal element. Verify important details against the public source before relying on them.

## Delay fields

Delay fields are calculated from extracted dates. If either date needed for a calculation is missing, the delay should be blank or marked unknown.

Use `days_received_to_first_activity` when it is available because it is closest to the question of when investigation activity began. If that field is blank, compare it with `days_received_to_visit`, `days_received_to_report`, `missing_first_activity_date`, and `report_date_used_as_proxy` before drawing any conclusions.

The `review_delay_over_30_days`, `review_delay_over_60_days`, `review_delay_over_90_days`, and `review_delay_over_120_days` fields are review flags. They identify records that may deserve closer review. They do not prove that CCLD delayed an investigation.

The `complaint_first_pass_review` view combines delay or review flags into `review_flags_summary` so first-pass review can stay readable. Open `complaint_review_summary` or `delay_review_flags` when you need the individual flag columns or calculated day counts.

The `delay_review_flags` view is a filtered review aid. A record appears in that view when one or more delay or review flags is set, including `missing_first_activity_date` or `report_date_used_as_proxy`. Treat inclusion in the view as a prompt to check the source report, not as a finding about the investigation.

Report date may not equal first investigative activity. Do not claim an investigation was delayed based only on `days_received_to_report` or `report_date_used_as_proxy`; check the source report and any available activity or visit dates.

Use neutral language when summarizing delay fields. For example, say that a record is "flagged for review based on available extracted dates" rather than saying that the source agency delayed an investigation. If the first activity date is missing, say that explicitly.

## Source limitations

Avoid overstating what the local output can prove:

- Treat the public portal as the source of record.
- Treat extracted records as derived data that may contain extraction errors.
- Confirm important findings against the source URL and raw hash in `source_documents`.
- Do not treat missing dates as evidence that an event did not occur.
- Do not redistribute raw narrative text unless it is needed for the review purpose.
