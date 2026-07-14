# Data Dictionary

## How missing and special values are shown

RecordsTracker keeps the stored source value separate from its reviewer-facing
label. A verified numeric zero is shown as `0`. A source field that is present
but blank is shown as `Not provided`; a field not supplied for that record type
is shown as `Not collected`; source-unavailable, governed not-applicable,
undated, and invalid values use `Not available from source`, `Not applicable`,
`Date not available`, and `Invalid source value`. Missing or invalid numeric
values never become zero. Reviewer dates display as `MM/DD/YYYY`; stored and CSV
dates remain ISO `YYYY-MM-DD`.

## facility_name

Name of the facility as shown in the source data.

## external_facility_number

Facility number assigned by the source system.

## address

On the facility hub, the governed street address, city, state, and ZIP code are
assembled into one readable **Address** value. A residential street-address
source field may supply the street portion, but its raw source column name is
not reviewer-facing. Missing components are not repeated as separate raw fields.

## facility_type

Facility type from the explicit CCLD complaint-report `FACILITY TYPE` field or
an approved facility-reference `Facility Type`/`FAC_TYPE_DESC` value. An
explicit numeric complaint-report code such as `733` is retained. The unrelated
numeric CHHS `TYPE` field is not used. For hosted refresh, an approved nonblank
facility-reference value takes precedence and conflicts remain traceable.

## program_type

Source-provided facility program label, when available. It remains distinct
from facility type and appears as a secondary facility fact on the facility hub.

## county

Source-provided county label, when available. Hosted canonical county is owned
by the newest approved nonblank facility-reference row; missing reference data
does not erase an existing value.

## status

Source-provided facility status label, when available. It is not inferred from
closed date. Hosted canonical status is owned by the newest approved nonblank
facility-reference row; missing reference data does not erase an existing value.

## capacity

Source-provided facility capacity as an integer, when available. A verified zero
is distinct from missing or blank source data.

## regional_office

Source-provided CCLD regional-office label, when available. A governed facility-
directory description field may supply this value, but the hub uses the plain
reviewer label **Regional office** rather than exposing the raw source column.

## closed_date

Source-reference closed date, when available. The facility hub shows a valid
date as `MM/DD/YYYY`; missing, blank, unavailable, undated, or malformed values
use the governed presentation labels. A missing closed date does not establish
that a facility is open and does not replace facility status.

## complaint_received_date

Date the complaint was reportedly received by the licensing office.

## first_investigation_activity_date

Earliest valid investigation activity date from explicit report narrative or a
structured `VISIT DATE`, if available. When both exist, the earliest date wins.
Report date alone is not first-activity evidence.

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

On reviewer detail, these four stored durations appear under **Elapsed days**
with human-readable labels beside the five ordered complaint milestones. The
display does not infer a missing milestone or silently recalculate a stored
duration. If valid milestone dates conflict with a stored duration, both remain
visible and a **Timing mismatch** cue directs the reviewer to check the source.
The governed missing, blank, unavailable, invalid, and verified-zero labels at
the top of this dictionary apply to each duration.

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

## Facility-reference-only fields

`all_visit_dates`, `inspection_visit_dates`, and `other_visit_dates` are nullable,
sorted, deduplicated ISO-date arrays retained with facility-reference rows. They
are not canonical complaint events. `client_served` and `closed_date` are also
nullable source-reference fields; they do not replace facility type or status,
and missing closed date does not mean that a facility is open. The composite
complaint-information CSV value remains raw provenance and is not exposed as a
single complaint or allegation fact.
