# Data Dictionary

## facility_name

Name of the facility as shown in the source data.

## external_facility_number

Facility number assigned by the source system.

## complaint_received_date

Date the complaint was reportedly received by the licensing office.

## first_investigation_activity_date

Earliest investigation activity date extracted from the report narrative, if available.

## visit_date

Date shown as the visit date in the source report, if available. This is tracked separately from the first investigation activity date.

## report_date

Date shown on the report. The report date may not be the same as the first investigation activity date.

## date_signed

Date and time the report was signed, if available.

## finding

Normalized finding value such as Substantiated, Unsubstantiated, Inconclusive, or Unknown.

## days_received_to_report

Number of days between complaint received date and report date.

## days_received_to_first_activity

Number of days between complaint received date and first investigation activity date, when both dates are available.

## days_received_to_visit

Number of days between complaint received date and visit date, when both dates are available.

## days_report_to_signed

Number of days between report date and date signed, when both dates are available.

## review_delay_over_30_days

Review flag set to true when the earliest available deterministic delay basis is more than 30 days. This is a screening flag, not a conclusion that an investigation was delayed.

## review_delay_over_60_days

Review flag set to true when the earliest available deterministic delay basis is more than 60 days. This is a screening flag, not a conclusion that an investigation was delayed.

## review_delay_over_90_days

Review flag set to true when the earliest available deterministic delay basis is more than 90 days. This is a screening flag, not a conclusion that an investigation was delayed.

## review_delay_over_120_days

Review flag set to true when the earliest available deterministic delay basis is more than 120 days. This is a screening flag, not a conclusion that an investigation was delayed.

## missing_first_activity_date

Review flag set to true when the complaint received date is available but no first investigation activity date was extracted.

## report_date_used_as_proxy

Review flag set to true only when report date is used as the delay review basis because no first investigation activity date or visit date is available. Do not use this field to claim the report date was the first investigative activity.

## extraction_confidence

Numeric or categorical estimate of extraction confidence. Low-confidence records should be manually reviewed.
