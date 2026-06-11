# Reviewing Records

## Suggested review steps

1. Open the `facilities` table to confirm the facility being reviewed.
2. Open the `source_documents` table to confirm source URL, raw file hash, connector name, retrieval time, and report index.
3. Open the `complaints` table to review complaint dates, findings, delay fields, review flags, and complaint control numbers.
4. Open the `allegations` table to review allegation text linked by complaint ID.
5. Open the `events` and `extraction_audit` tables when you need dated event details, source text, confidence, or extraction warnings.
6. Start with records flagged as low confidence when confidence fields are available.
7. Note any extraction issue for correction.

The local database is a derived review aid. The public portal remains the source of record, and source reports may be incomplete, corrected later, removed, or formatted differently across time.

## Delay fields

Delay fields are calculated from extracted dates. If either date needed for a calculation is missing, the delay should be blank or marked unknown.

Use `days_received_to_first_activity` when it is available because it is closest to the question of when investigation activity began. If that field is blank, compare it with `days_received_to_visit`, `days_received_to_report`, `missing_first_activity_date`, and `report_date_used_as_proxy` before drawing any conclusions.

The `review_delay_over_30_days`, `review_delay_over_60_days`, `review_delay_over_90_days`, and `review_delay_over_120_days` fields are review flags. They identify records that may deserve closer review. They do not prove that CCLD delayed an investigation.

Report date may not equal first investigative activity. Do not claim an investigation was delayed based only on `days_received_to_report` or `report_date_used_as_proxy`; check the source report and any available activity or visit dates.

Use neutral language when summarizing delay fields. For example, say that a record is "flagged for review based on available extracted dates" rather than saying that the source agency delayed an investigation. If the first activity date is missing, say that explicitly.

## Source limitations

Avoid overstating what the local output can prove:

- Treat the public portal as the source of record.
- Treat extracted records as derived data that may contain extraction errors.
- Confirm important findings against the source URL and raw hash in `source_documents`.
- Do not treat missing dates as evidence that an event did not occur.
- Do not redistribute raw narrative text unless it is needed for the review purpose.
