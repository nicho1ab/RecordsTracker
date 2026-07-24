# Source-to-screen remediation plan

The audit proposes these deduplicated follow-up groups. This document is planning output only: it does not create GitHub issues and does not authorize broad remediation in the audit-foundation change.

## P0: Allocate extracted fields to canonical storage deliberately

Resolve canonical allocation and schema gaps in a separately reviewed change that updates contracts, mappings, migrations, and fixtures together.

Dependencies:

- `source-to-screen.raw-artifact-extraction`

Acceptance criteria:

- Canonical allocation is documented in DATA_CONTRACT.md.
- Import and initialization behavior populate the governed field.

Validation:

- Run schema, importer, and fixture regression suites.

Related stable gaps:

- `gap.data.facility.facility_fixture_ccld_program_facilities_tiny.citation_numbers.extracted_canonical_mapping_missing`
- `gap.data.facility.facility_fixture_ccld_program_facilities_tiny.complaint_visits.extracted_canonical_mapping_missing`
- `gap.data.facility.facility_fixture_ccld_program_facilities_tiny.facility_city.extracted_canonical_mapping_missing`
- `gap.data.facility.facility_fixture_ccld_program_facilities_tiny.facility_state.extracted_canonical_mapping_missing`
- `gap.data.facility.facility_fixture_ccld_program_facilities_tiny.facility_zip.extracted_canonical_mapping_missing`
- `gap.data.facility.facility_fixture_ccld_program_facilities_tiny.inspect_typea.extracted_canonical_mapping_missing`
- `gap.data.facility.facility_fixture_ccld_program_facilities_tiny.inspect_typeb.extracted_canonical_mapping_missing`
- `gap.data.facility.facility_fixture_ccld_program_facilities_tiny.inspection_visits.extracted_canonical_mapping_missing`
- `gap.data.facility.facility_fixture_ccld_program_facilities_tiny.last_visit_date.extracted_canonical_mapping_missing`
- `gap.data.facility.facility_fixture_ccld_program_facilities_tiny.license_first_date.extracted_canonical_mapping_missing`
- `gap.data.facility.facility_fixture_ccld_program_facilities_tiny.other_typea.extracted_canonical_mapping_missing`
- `gap.data.facility.facility_fixture_ccld_program_facilities_tiny.other_typeb.extracted_canonical_mapping_missing`
- `gap.data.facility.facility_fixture_ccld_program_facilities_tiny.other_visits.extracted_canonical_mapping_missing`
- `gap.data.facility.facility_fixture_ccld_program_facilities_tiny.poc_dates.extracted_canonical_mapping_missing`
- `gap.data.facility.facility_fixture_ccld_program_facilities_tiny.total_visits.extracted_canonical_mapping_missing`
- `gap.data.facility.facility_fixture_chhs_facility_master_tiny.program_type.extracted_canonical_mapping_missing`
- `gap.data.facility.facility_fixture_chhs_facility_master_tiny.res_city.extracted_canonical_mapping_missing`
- `gap.data.facility.facility_fixture_chhs_facility_master_tiny.res_state.extracted_canonical_mapping_missing`
- `gap.data.facility.facility_fixture_chhs_facility_master_tiny.res_zip_code.extracted_canonical_mapping_missing`

## P0: Close governed raw-artifact and extraction gaps

Add deterministic extraction only for reviewer-relevant fields proven present in governed raw artifacts. Preserve raw source traceability.

Dependencies:

- `None.`

Acceptance criteria:

- Every selected raw field has a fixture-based extraction regression.
- Unavailable source coverage remains distinct from an extracted blank.

Validation:

- Run complaint and facility source fixture tests.

Related stable gaps:

- `gap.data.complaint.allegation.allegation_category.source_not_provided`

## P0: Enforce SQLite and PostgreSQL import parity

Compare equivalent governed imports using aggregate counts and fix only confirmed adapter or import divergence.

Dependencies:

- `source-to-screen.canonical-allocation`

Acceptance criteria:

- Equivalent governed data yields matching eligible and populated counts.

Validation:

- Run adapter parity tests against SQLite and PostgreSQL-style storage.

Related stable gaps:

- `No current structural gap; retain as an audit coverage workstream.`

## Completed: Make reviewer aggregate outputs data-ready

Prove denominator, query-range, source-coverage, and zero semantics for current priorities, trends, topic review, and exports.

Implemented through the shared aggregate result contract, uncapped default
source-derived reads, selectable first-investigation-activity ranges, governed
facility query projections, export manifests, and aggregate-safe local/runtime
evidence. Generated source-to-screen audit snapshots remain untouched until the
normal repository regeneration workflow is explicitly run.

Dependencies:

- `source-to-screen.store-parity`

Acceptance criteria:

- Every zero-only or unavailable aggregate reports an explicit cause.
- Query limits cannot silently exclude otherwise eligible records.

Validation:

- Run aggregate tests with zero, unavailable, and over-limit data sets.

Related stable gaps:

- `gap.aggregate.complaint-facility-exports.aggregate_data_insufficient`
- `gap.aggregate.complaint-trends.aggregate_data_insufficient`
- `gap.aggregate.facility-priorities.aggregate_data_insufficient`
- `gap.aggregate.serious-topic-review.aggregate_data_insufficient`
- `gap.aggregate.substantiated-review.aggregate_data_insufficient`
- `gap.data.facility.facility_fixture_ccld_program_facilities_tiny.facility_address.stored_query_omission`
- `gap.data.facility.facility_fixture_chhs_facility_master_tiny.fac_do_desc.stored_query_omission`
- `gap.data.facility.facility_fixture_chhs_facility_master_tiny.res_street_addr.stored_query_omission`
- `gap.query.first-activity-date-range-omission`
- `gap.query.source-derived-default-100-row-cap`

## P1: Prevent unexplained reviewer-facing blank values

Preserve blank, null, unavailable, not applicable, undated, and verified zero as distinct states from import through presentation.

Dependencies:

- `source-to-screen.canonical-allocation`

Acceptance criteria:

- Blank cells have a governed meaning or are replaced by an explicit state.
- Malformed or absent values are never coerced to numeric zero.

Validation:

- Run null-semantics and hosted rendering regressions.

Related stable gaps:

- `gap.data.facility.facility_signal.blank_to_zero_risk.unexplained_blank`

## P1: Complete reviewer-relevant complaint detail coverage

Expose confirmed stored complaint facts in the appropriate attorney-tier workflow without adding raw technical traceability dumps.

Dependencies:

- `source-to-screen.store-parity`

Acceptance criteria:

- Complaint detail stays within the attorney/reviewer information tier.
- Stored reviewer-relevant fields are shown or explicitly dispositioned.

Validation:

- Run hosted reviewer detail and export tests.

Related stable gaps:

- `gap.data.complaint.complaint.days_received_to_report.ui_display_omission`
- `gap.data.complaint.complaint.days_received_to_visit.ui_display_omission`
- `gap.data.complaint.complaint.days_report_to_signed.ui_display_omission`
- `gap.data.complaint.raw_complaint_report.agency_name.ui_display_omission`
- `gap.data.complaint.raw_complaint_report.deficiency_text.ui_display_omission`
- `gap.data.complaint.raw_complaint_report.investigation_findings_narrative.ui_display_omission`
- `gap.query.first-activity-date-range-omission`
- `gap.query.source-derived-default-100-row-cap`

## P1: Complete the facility hub with one home per reviewer fact

Display only appropriate reviewer-facing facility facts at a single deliberate home after source, canonical, and query coverage are proven.

Dependencies:

- `source-to-screen.store-parity`

Acceptance criteria:

- Each selected facility fact has one reviewer-facing home.
- Technical source internals remain outside the primary reviewer page.

Validation:

- Run hosted facility lookup and accessibility tests.

Related stable gaps:

- `gap.data.facility.facility_fixture_ccld_program_facilities_tiny.facility_address.stored_query_omission`
- `gap.data.facility.facility_fixture_chhs_facility_master_tiny.fac_do_desc.stored_query_omission`
- `gap.data.facility.facility_fixture_chhs_facility_master_tiny.res_street_addr.stored_query_omission`
- `gap.data.facility.raw_complaint_report.facility_contact.ui_display_omission`
- `gap.query.source-derived-default-100-row-cap`

## P2 implementation available: automate source-to-screen coverage reporting

Run the aggregate-only audit against governed local fixtures and the deployed database without retaining record values or source bodies.

Contract `1.0.0` producer code, its closed JSON Schema, deterministic scenario
bundle, aggregate-only report/CSV, safe operator indexes, reconciliation, and
release assessment are implemented in the Issue #453 workstream. The existing
program-specific source family remains the evaluated retained scope; statewide
candidates, cadence, and raw `733` mapping remain unapproved.

This is not a completion claim. Production-style evidence still requires the
later authorized integration to supply validated aggregate field/stage and
operational read-boundary input without fixture substitution, then compare the
producer package with the independent Issue #477 consumer fixtures. Retention
duration also remains pending policy.

Dependencies:

- `None.`

Acceptance criteria:

- Audit output ordering and identifiers are deterministic.
- Runtime reports contain only aggregate counts and safe metadata.

Validation:

- Run redaction, determinism, and path-portability tests.

Related stable gaps:

- `gap.aggregate.complaint-facility-exports.aggregate_data_insufficient`
- `gap.aggregate.complaint-trends.aggregate_data_insufficient`
- `gap.aggregate.facility-priorities.aggregate_data_insufficient`
- `gap.aggregate.serious-topic-review.aggregate_data_insufficient`
- `gap.aggregate.substantiated-review.aggregate_data_insufficient`
- `gap.data.complaint.allegation.allegation_category.source_not_provided`
- `gap.data.complaint.allegation.allegation_id.intentionally_internal`
- `gap.data.complaint.allegation.complaint_id.intentionally_internal`
- `gap.data.complaint.allegation.extraction_confidence.intentionally_internal`
- `gap.data.complaint.complaint.complaint_id.intentionally_internal`
- `gap.data.complaint.complaint.days_received_to_report.ui_display_omission`
- `gap.data.complaint.complaint.days_received_to_visit.ui_display_omission`
- `gap.data.complaint.complaint.days_report_to_signed.ui_display_omission`
- `gap.data.complaint.complaint.document_id.intentionally_internal`
- `gap.data.complaint.complaint.extraction_confidence.intentionally_internal`
- `gap.data.complaint.complaint.facility_id.intentionally_internal`
- `gap.data.complaint.complaint.missing_first_activity_date.intentionally_internal`
- `gap.data.complaint.complaint.report_date_used_as_proxy.intentionally_internal`
- `gap.data.complaint.complaint.review_delay_over_120_days.intentionally_internal`
- `gap.data.complaint.complaint.review_delay_over_30_days.intentionally_internal`
- `gap.data.complaint.complaint.review_delay_over_60_days.intentionally_internal`
- `gap.data.complaint.complaint.review_delay_over_90_days.intentionally_internal`
- `gap.data.complaint.event.complaint_id.intentionally_internal`
- `gap.data.complaint.event.event_id.intentionally_internal`
- `gap.data.complaint.event.extracted_from_section.intentionally_internal`
- `gap.data.complaint.event.extraction_confidence.intentionally_internal`
- `gap.data.complaint.raw_complaint_report.agency_name.ui_display_omission`
- `gap.data.complaint.raw_complaint_report.deficiency_text.ui_display_omission`
- `gap.data.complaint.raw_complaint_report.investigation_findings_narrative.ui_display_omission`
- `gap.data.facility.facility.facility_id.intentionally_internal`
- `gap.data.facility.facility.licensee_name.intentionally_internal`
- `gap.data.facility.facility.source_id.intentionally_internal`
- `gap.data.facility.facility_fixture_ccld_program_facilities_tiny.all_visit_dates.intentionally_internal`
- `gap.data.facility.facility_fixture_ccld_program_facilities_tiny.citation_numbers.extracted_canonical_mapping_missing`
- `gap.data.facility.facility_fixture_ccld_program_facilities_tiny.complaint_info_date_sub_aleg_inc_aleg_uns_aleg_typea_typeb.intentionally_internal`
- `gap.data.facility.facility_fixture_ccld_program_facilities_tiny.complaint_visits.extracted_canonical_mapping_missing`
- `gap.data.facility.facility_fixture_ccld_program_facilities_tiny.facility_address.stored_query_omission`
- `gap.data.facility.facility_fixture_ccld_program_facilities_tiny.facility_administrator.intentionally_internal`
- `gap.data.facility.facility_fixture_ccld_program_facilities_tiny.facility_city.extracted_canonical_mapping_missing`
- `gap.data.facility.facility_fixture_ccld_program_facilities_tiny.facility_state.extracted_canonical_mapping_missing`
- `gap.data.facility.facility_fixture_ccld_program_facilities_tiny.facility_telephone_number.intentionally_internal`
- `gap.data.facility.facility_fixture_ccld_program_facilities_tiny.facility_zip.extracted_canonical_mapping_missing`
- `gap.data.facility.facility_fixture_ccld_program_facilities_tiny.inspect_typea.extracted_canonical_mapping_missing`
- `gap.data.facility.facility_fixture_ccld_program_facilities_tiny.inspect_typeb.extracted_canonical_mapping_missing`
- `gap.data.facility.facility_fixture_ccld_program_facilities_tiny.inspection_visit_dates.intentionally_internal`
- `gap.data.facility.facility_fixture_ccld_program_facilities_tiny.inspection_visits.extracted_canonical_mapping_missing`
- `gap.data.facility.facility_fixture_ccld_program_facilities_tiny.last_visit_date.extracted_canonical_mapping_missing`
- `gap.data.facility.facility_fixture_ccld_program_facilities_tiny.license_first_date.extracted_canonical_mapping_missing`
- `gap.data.facility.facility_fixture_ccld_program_facilities_tiny.licensee.intentionally_internal`
- `gap.data.facility.facility_fixture_ccld_program_facilities_tiny.other_typea.extracted_canonical_mapping_missing`
- `gap.data.facility.facility_fixture_ccld_program_facilities_tiny.other_typeb.extracted_canonical_mapping_missing`
- `gap.data.facility.facility_fixture_ccld_program_facilities_tiny.other_visit_dates.intentionally_internal`
- `gap.data.facility.facility_fixture_ccld_program_facilities_tiny.other_visits.extracted_canonical_mapping_missing`
- `gap.data.facility.facility_fixture_ccld_program_facilities_tiny.poc_dates.extracted_canonical_mapping_missing`
- `gap.data.facility.facility_fixture_ccld_program_facilities_tiny.total_visits.extracted_canonical_mapping_missing`
- `gap.data.facility.facility_fixture_chhs_facility_master_tiny.client_served.intentionally_internal`
- `gap.data.facility.facility_fixture_chhs_facility_master_tiny.fac_co_nbr.intentionally_internal`
- `gap.data.facility.facility_fixture_chhs_facility_master_tiny.fac_do_desc.stored_query_omission`
- `gap.data.facility.facility_fixture_chhs_facility_master_tiny.fac_latitude.intentionally_internal`
- `gap.data.facility.facility_fixture_chhs_facility_master_tiny.fac_longitude.intentionally_internal`
- `gap.data.facility.facility_fixture_chhs_facility_master_tiny.fac_phone_nbr.intentionally_internal`
- `gap.data.facility.facility_fixture_chhs_facility_master_tiny.id.intentionally_internal`
- `gap.data.facility.facility_fixture_chhs_facility_master_tiny.objectid.intentionally_internal`
- `gap.data.facility.facility_fixture_chhs_facility_master_tiny.program_type.extracted_canonical_mapping_missing`
- `gap.data.facility.facility_fixture_chhs_facility_master_tiny.res_city.extracted_canonical_mapping_missing`
- `gap.data.facility.facility_fixture_chhs_facility_master_tiny.res_state.extracted_canonical_mapping_missing`
- `gap.data.facility.facility_fixture_chhs_facility_master_tiny.res_street_addr.stored_query_omission`
- `gap.data.facility.facility_fixture_chhs_facility_master_tiny.res_zip_code.extracted_canonical_mapping_missing`
- `gap.data.facility.facility_fixture_chhs_facility_master_tiny.type.intentionally_internal`
- `gap.data.facility.facility_fixture_chhs_facility_master_tiny.x.intentionally_internal`
- `gap.data.facility.facility_fixture_chhs_facility_master_tiny.y.intentionally_internal`
- `gap.data.facility.facility_signal.blank_to_zero_risk.unexplained_blank`
- `gap.data.facility.raw_complaint_report.facility_contact.ui_display_omission`
- `gap.data.shared.extraction_audit.audit_id.intentionally_internal`
- `gap.data.shared.extraction_audit.confidence.intentionally_internal`
- `gap.data.shared.extraction_audit.document_id.intentionally_internal`
- `gap.data.shared.extraction_audit.extracted_value.intentionally_internal`
- `gap.data.shared.extraction_audit.extraction_method.intentionally_internal`
- `gap.data.shared.extraction_audit.extractor_version.intentionally_internal`
- `gap.data.shared.extraction_audit.field_name.intentionally_internal`
- `gap.data.shared.extraction_audit.source_section.intentionally_internal`
- `gap.data.shared.extraction_audit.source_text.intentionally_internal`
- `gap.data.shared.extraction_audit.warning.intentionally_internal`
- `gap.data.shared.source_document.connector_name.intentionally_internal`
- `gap.data.shared.source_document.connector_version.intentionally_internal`
- `gap.data.shared.source_document.content_type.intentionally_internal`
- `gap.data.shared.source_document.document_id.intentionally_internal`
- `gap.data.shared.source_document.document_type.intentionally_internal`
- `gap.data.shared.source_document.facility_id.intentionally_internal`
- `gap.data.shared.source_document.http_status.intentionally_internal`
- `gap.data.shared.source_document.raw_path.intentionally_internal`
- `gap.data.shared.source_document.raw_sha256.intentionally_internal`
- `gap.data.shared.source_document.report_index.intentionally_internal`
- `gap.data.shared.source_document.retrieved_at.intentionally_internal`
- `gap.data.shared.source_document.source_id.intentionally_internal`
- `gap.query.first-activity-date-range-omission`
- `gap.query.source-derived-default-100-row-cap`
