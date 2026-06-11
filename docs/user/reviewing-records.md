# Reviewing Records

## Suggested review steps

1. Open the `complaints` table to review complaint dates, findings, and delay fields.
2. Open the `allegations` table to review allegation text linked by complaint ID.
3. Open the `source_documents` table to compare extracted fields to the source URL and raw file hash.
4. Start with records flagged as low confidence when confidence fields are available.
5. Note any extraction issue for correction.

## Delay fields

Delay fields are calculated from extracted dates. If either date needed for a calculation is missing, the delay should be blank or marked unknown.

Use `days_received_to_first_activity` when it is available because it is closest to the question of when investigation activity began. If that field is blank, compare it with `days_received_to_visit`, `days_received_to_report`, `missing_first_activity_date`, and `report_date_used_as_proxy` before drawing any conclusions.

The `review_delay_over_30_days`, `review_delay_over_60_days`, `review_delay_over_90_days`, and `review_delay_over_120_days` fields are review flags. They identify records that may deserve closer review. They do not prove that CCLD delayed an investigation.

Report date may not equal first investigative activity. Do not claim an investigation was delayed based only on `days_received_to_report` or `report_date_used_as_proxy`; check the source report and any available activity or visit dates.
