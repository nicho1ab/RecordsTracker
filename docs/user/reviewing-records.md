# Reviewing Records

For a step-by-step reviewer workflow, start with [Local Review Workflow](local-review-workflow.md).

## Suggested review steps

1. Open the `review_home` saved query first for the task-based local review paths.
2. Open `public_record_allegation_search` when you need cautious keyword discovery over source-derived allegation text, allegation categories, and findings with source traceability visible.
3. Open `complaint_timeline_review` when you need to see complaint milestone dates and extracted event dates in a source-traceable sequence.
4. Open `complaint_review_start_here` or `complaint_first_pass_review` for the guided low-noise complaint list with source traceability.
5. Open the `complaint_review_summary` view when you need detailed delay calculations, separate review flag columns, extraction confidence, or broader complaint review context.
6. Open the `facility_complaint_summary` view to compare complaint counts, allegation counts, complaint date range, and delay review flag counts by facility.
7. Open the `facility_pattern_review` view to compare finding mix, allegation categories, missing first activity dates, report-date proxy usage, review flag counts, and source document counts by facility.
8. Open the `facility_comparison_review` view to compare facility/category/finding rows with source-document counts, traceability-completeness counts, same-category/finding facility counts, and cautious scope notes.
9. Open the `delay_review_flags` view to triage records with one or more delay or review flags.
10. Open the `source_traceability_review` view to confirm source URL, raw file hash, raw path, connector name, connector version, retrieval time, and report index.
11. Open the `multi_facility_source_traceability_review` view when you need traceability status and linked derived-record counts by source document across multiple facilities.
12. Open the `field_source_traceability_review` view when you need extracted value, source text, source section, warnings, confidence, extraction method, extractor version, and source traceability together.
13. Open the normalized `facilities`, `source_documents`, `complaints`, `allegations`, `events`, and `extraction_audit` tables when you need lower-level detail beyond the review views.
14. Start with records flagged as low confidence when confidence fields are available.
15. Note any extraction issue for correction.

The local database is a derived review aid. The public portal remains the source of record, and source reports may be incomplete, corrected later, removed, or formatted differently across time.

Search matches from `public_record_allegation_search` are screening aids over the derived dataset. They do not prove harm, liability, rights deprivation, abuse, neglect, or any legal element. Verify important details against the public source before relying on them.

## Hosted complaint worklist

Open `/reviewer` to choose the next loaded complaint to review. Search and the
matching-result summary appear before one compact worklist. The summary states
how many matching complaints are shown and whether the current 100-record bound
omits additional matching records; it is not a public-source completeness
claim.

Each worklist row shows the complaint number, facility name and Facility ID,
complaint/visit/report dates, finding or resolution, review-flag badges,
reviewer status, note presence, CCLD-source availability, and one **Review
complaint** action. The **Review next** cue explains the existing reviewer-state
reason for starting with that row. It does not assign or claim the complaint,
create a legal priority score, or change the governed query order. At narrow
widths and browser zoom, the same labeled values stack vertically so the
primary review action remains reachable without horizontal scrolling.

In the hosted reviewer workflow, use `/reviewer/records/serious-topics` to filter loaded complaint records by governed serious-review themes. Treat `Source category` rows as official source-derived categories and `Keyword-assisted cue` rows as separate review prompts when the source category is missing or unknown. Do not summarize keyword cues as findings or verified events.

Use `/reviewer/facilities/trends` when the review task is to compare loaded complaint and finding activity over time. Coverage and anomaly labels describe only the displayed, qualifying loaded records; open the contributing complaint record and its existing public-report action before relying on an individual complaint.

Use `/ccld/facilities/intelligence` when the task starts across facilities. The
dashboard applies complaint-level filters before reconciling facility counts,
shows source coverage as available, partial, or unavailable, and links every
summary and facility count to the exact contributing complaint records. Open the
recommended next complaint for the first result under the selected visible
ordering, or continue to that Facility Review Hub or filtered complaint queue.
These indicators describe only the authorized loaded corpus and do not make a
legal, facility-wide, or public-source completeness conclusion.

## Facility hub fact placement

The facility hub gives each selected reviewer-facing facility fact one home:

| Facility fact | Disposition | Reviewer-facing home |
| --- | --- | --- |
| Facility name | Primary reviewer fact | Facility heading, with a copy control |
| Facility ID | Primary reviewer fact | Primary facility facts, with a copy control |
| Facility type, status, county, and capacity | Primary reviewer facts | Primary facility facts |
| Street address, city, state, and ZIP code | Primary reviewer fact | One composed **Address** value in primary facility facts |
| Program type, regional office, and closed date | Secondary reviewer facts | One collapsed **More facility facts** disclosure |
| Deduplicated complaint count and relevant date range | Review signals | **Review summary**, linked to exact contributing complaints |
| Finding distribution, serious-review categories, and monthly anomaly cues | Review signals | **Review summary**, with each aggregate linked to its exact contributing complaints |
| Original CCLD report coverage | Review signals | Available, partial, or unavailable **Source coverage**, linked to the applicable complaints |
| Reviewer-created status and note counts | Review signals from separate reviewer-created state | Clearly labeled rows in **Review summary**, linked to the applicable complaints |
| Deterministic recommended complaint | Review action | Default-visible **Review next**, using the governed date and stable-identity tie order |
| Visit, citation, POC, and last-visit cues | Review signals | **Additional review signals** |
| Facility-reference source filename/resource label | Support/operator-only | Not shown on the primary facility hub |
| Raw source column names, source row/internal IDs, hashes, connector/import metadata, and source bundle dumps | Support/operator-only or intentionally excluded | Not shown on the primary facility hub |

The regional-office value may be derived from a governed facility-directory
description field, and the street-address value may be derived from a governed
residential-address field. The hub labels them **Regional office** and
**Address**; raw source column names are retained only for internal provenance.
Closed dates display as `MM/DD/YYYY`. The governed labels described in the data
dictionary distinguish verified zero, blank, null, unavailable, not-applicable,
malformed, undated, and not-collected values without inventing a fact. A missing
closed date does not mean that a facility is open.

When the hub is opened from cross-facility intelligence, it keeps the selected
date dimension/range, finding, serious-review category, and source-coverage
context that contributed to the facility result. The primary actions open the
recommended complaint, the exact contributing complaints, or Request Records.
Complaint links use stable source-derived identities. Reviewer-created statuses
and notes remain separate from public-record facts, and note text is not exposed
in the hub summary.

Current priorities, facility priorities, trends, serious-topic review, and
substantiated review show the loaded-record universe, eligible denominator,
active date dimension/range, source coverage, and a reason for zero or
unavailable results. Choose first investigation activity when the review range
is about the first governed investigation event; do not substitute complaint
received, visit, report, or signed dates. Pagination changes the visible page,
not the aggregate denominator.

Facility pattern counts summarize the local derived dataset only. Use them to choose records for closer source review, not as findings about a facility or the public source record.

Facility comparison rows summarize local derived facility/category/finding groups only. Use same-category/finding facility counts to find records for closer source review, not as findings about a facility or facility-wide conduct.

Source traceability counts summarize linked records in the local derived dataset only. Use them to find source documents that need checking, not as proof that the public source is complete or incomplete.

Timeline rows in `complaint_timeline_review` show extracted dates that are available in the local derived dataset. Reviewer pages label missing, blank, unavailable, undated, or invalid dates explicitly; none of those labels proves that an event did not occur.

## Delay fields

Reviewer detail shows five ordered milestones: complaint received, first
investigation activity, visit, report, and signed. The adjacent **Elapsed days**
summary uses plain labels for the four stored intervals: complaint received to
first investigation activity, complaint received to visit, complaint received
to report, and report to signed. Visible dates use `MM/DD/YYYY`.

The stored duration remains visible even when an associated milestone date is
missing; RecordsTracker does not infer the missing date or replace the stored
duration with a new calculation. Null and blank durations are labeled `Not
provided`, a source-unavailable duration is `Not available from source`, and a
malformed duration is `Invalid source value`. A same-day interval remains the
verified numeric value `0`. When valid displayed milestone dates do not agree
with a governed stored duration, reviewer detail keeps both source-derived facts
and shows a concise **Timing mismatch** cue so the source can be checked.

The attorney-tier detail uses the source-derived finding/status and shows
governed allegation categories with allegations and findings; there is no
separate canonical complaint-type field to invent or display. Internal complaint,
facility-relation, and document IDs, extraction confidence, raw hashes, connector
and import metadata, full raw source bodies, and technical field tables remain
outside the primary reviewer page because they support extraction, audit, or
operator troubleshooting rather than the current review decision. The compact
public-source availability cue and source action remain visible.

Use `days_received_to_first_activity` when it is available because it is closest to the question of when investigation activity began. If that field has a missing or unavailable label, compare it with `days_received_to_visit`, `days_received_to_report`, `missing_first_activity_date`, and `report_date_used_as_proxy` before drawing any conclusions.

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
- Use `multi_facility_source_traceability_review` when checking source traceability status and linked derived-record counts across multiple facilities.
- Use `facility_comparison_review` when checking repeated category/finding rows across facilities; verify source records before citing any comparison.
- Use `field_source_traceability_review` when checking a specific extracted field against source text and extraction audit context.
- Do not treat missing dates as evidence that an event did not occur.
- Do not redistribute raw narrative text unless it is needed for the review purpose.
