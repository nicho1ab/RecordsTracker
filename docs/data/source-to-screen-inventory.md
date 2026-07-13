# Source-to-screen inventory

This tracked inventory is the structural baseline for the repeatable audit. It contains field identities and dispositions, not source record values or runtime population counts.

The generated audit under `data/processed/source-to-screen-audit/` is the authority for environment-specific aggregate population measurements.

| Data element | Ownership | Source or extractor reference | Canonical allocation | Current home | Classification | Priority |
| --- | --- | --- | --- | --- | --- | --- |
| `data.complaint.allegation.allegation_category` | complaint | allegation normalizer: allegation_category | `allegations.allegation_category` | /reviewer/records/serious-topics; stakeholder export | `SOURCE_NOT_PROVIDED` | P1 |
| `data.complaint.allegation.allegation_id` | complaint | allegation normalizer: allegation_id | `allegations.allegation_id` | not displayed | `INTENTIONALLY_INTERNAL` | P2 |
| `data.complaint.allegation.allegation_text` | complaint | Allegation(s) | `allegations.allegation_text` | /reviewer/records/detail | `NOT_APPLICABLE` | P2 |
| `data.complaint.allegation.complaint_id` | complaint | allegation normalizer: complaint_id | `allegations.complaint_id` | not displayed | `INTENTIONALLY_INTERNAL` | P2 |
| `data.complaint.allegation.extraction_confidence` | complaint | allegation normalizer: extraction_confidence | `allegations.extraction_confidence` | not displayed | `INTENTIONALLY_INTERNAL` | P2 |
| `data.complaint.allegation.finding` | complaint | allegation normalizer: finding | `allegations.finding` | /reviewer/records/detail | `NOT_APPLICABLE` | P2 |
| `data.complaint.complaint.complaint_control_number` | complaint | COMPLAINT CONTROL NUMBER | `complaints.complaint_control_number` | /reviewer/records; /reviewer/records/detail | `NOT_APPLICABLE` | P2 |
| `data.complaint.complaint.complaint_id` | complaint | complaint normalizer: complaint_id | `complaints.complaint_id` | not displayed | `INTENTIONALLY_INTERNAL` | P2 |
| `data.complaint.complaint.complaint_received_date` | complaint | COMPLAINT RECEIVED | `complaints.complaint_received_date` | /reviewer/records/detail source timeline | `NOT_APPLICABLE` | P2 |
| `data.complaint.complaint.date_signed` | complaint | Date Signed | `complaints.date_signed` | /reviewer/records/detail source timeline | `NOT_APPLICABLE` | P2 |
| `data.complaint.complaint.days_received_to_first_activity` | complaint | complaint normalizer: days_received_to_first_activity | `complaints.days_received_to_first_activity` | not displayed | `CANONICAL_IMPORT_NOT_POPULATED` | P1 |
| `data.complaint.complaint.days_received_to_report` | complaint | complaint normalizer: days_received_to_report | `complaints.days_received_to_report` | not displayed | `UI_DISPLAY_OMISSION` | P1 |
| `data.complaint.complaint.days_received_to_visit` | complaint | complaint normalizer: days_received_to_visit | `complaints.days_received_to_visit` | not displayed | `UI_DISPLAY_OMISSION` | P1 |
| `data.complaint.complaint.days_report_to_signed` | complaint | complaint normalizer: days_report_to_signed | `complaints.days_report_to_signed` | not displayed | `UI_DISPLAY_OMISSION` | P1 |
| `data.complaint.complaint.document_id` | complaint | complaint normalizer: document_id | `complaints.document_id` | not displayed | `INTENTIONALLY_INTERNAL` | P2 |
| `data.complaint.complaint.extraction_confidence` | complaint | complaint normalizer: extraction_confidence | `complaints.extraction_confidence` | not displayed | `INTENTIONALLY_INTERNAL` | P2 |
| `data.complaint.complaint.facility_id` | complaint | complaint normalizer: facility_id | `complaints.facility_id` | not displayed | `INTENTIONALLY_INTERNAL` | P2 |
| `data.complaint.complaint.finding` | complaint | Finding / INVESTIGATION FINDING(S) | `complaints.finding` | /reviewer/records/detail | `NOT_APPLICABLE` | P2 |
| `data.complaint.complaint.first_investigation_activity_date` | complaint | investigation narrative | `complaints.first_investigation_activity_date` | not displayed | `RAW_PRESENT_EXTRACTION_MISSING` | P0 |
| `data.complaint.complaint.missing_first_activity_date` | complaint | complaint normalizer: missing_first_activity_date | `complaints.missing_first_activity_date` | not displayed | `INTENTIONALLY_INTERNAL` | P2 |
| `data.complaint.complaint.report_date` | complaint | Report Date | `complaints.report_date` | /reviewer/records/detail source timeline | `NOT_APPLICABLE` | P2 |
| `data.complaint.complaint.report_date_used_as_proxy` | complaint | complaint normalizer: report_date_used_as_proxy | `complaints.report_date_used_as_proxy` | not displayed | `INTENTIONALLY_INTERNAL` | P2 |
| `data.complaint.complaint.review_delay_over_120_days` | complaint | complaint normalizer: review_delay_over_120_days | `complaints.review_delay_over_120_days` | not displayed | `INTENTIONALLY_INTERNAL` | P2 |
| `data.complaint.complaint.review_delay_over_30_days` | complaint | complaint normalizer: review_delay_over_30_days | `complaints.review_delay_over_30_days` | not displayed | `INTENTIONALLY_INTERNAL` | P2 |
| `data.complaint.complaint.review_delay_over_60_days` | complaint | complaint normalizer: review_delay_over_60_days | `complaints.review_delay_over_60_days` | not displayed | `INTENTIONALLY_INTERNAL` | P2 |
| `data.complaint.complaint.review_delay_over_90_days` | complaint | complaint normalizer: review_delay_over_90_days | `complaints.review_delay_over_90_days` | not displayed | `INTENTIONALLY_INTERNAL` | P2 |
| `data.complaint.complaint.visit_date` | complaint | VISIT DATE | `complaints.visit_date` | /reviewer/records/detail source timeline | `NOT_APPLICABLE` | P2 |
| `data.complaint.event.complaint_id` | complaint | event normalizer: complaint_id | `events.complaint_id` | not displayed | `INTENTIONALLY_INTERNAL` | P2 |
| `data.complaint.event.event_date` | complaint | investigation narrative date token | `events.event_date` | not populated in current connector output | `RAW_PRESENT_EXTRACTION_MISSING` | P1 |
| `data.complaint.event.event_id` | complaint | event normalizer: event_id | `events.event_id` | not displayed | `INTENTIONALLY_INTERNAL` | P2 |
| `data.complaint.event.event_text` | complaint | investigation narrative | `events.event_text` | not populated in current connector output | `RAW_PRESENT_EXTRACTION_MISSING` | P1 |
| `data.complaint.event.event_type` | complaint | investigation narrative event cue | `events.event_type` | not populated in current connector output | `RAW_PRESENT_EXTRACTION_MISSING` | P1 |
| `data.complaint.event.extracted_from_section` | complaint | event normalizer: extracted_from_section | `events.extracted_from_section` | not displayed | `INTENTIONALLY_INTERNAL` | P2 |
| `data.complaint.event.extraction_confidence` | complaint | event normalizer: extraction_confidence | `events.extraction_confidence` | not displayed | `INTENTIONALLY_INTERNAL` | P2 |
| `data.complaint.raw_complaint_report.investigation_findings_narrative` | complaint | allowlisted raw label pattern: investigation_findings_narrative | `not allocated` | /reviewer/records/detail | `EXTRACTED_CANONICAL_MAPPING_MISSING` | P2 |
| `data.facility.facility.capacity` | facility | facility normalizer: capacity | `facilities.capacity` | /ccld/facilities/detail | `NOT_APPLICABLE` | P2 |
| `data.facility.facility.county` | facility | facility normalizer: county | `facilities.county` | /ccld/facilities/detail | `NOT_APPLICABLE` | P2 |
| `data.facility.facility.external_facility_number` | facility | FACILITY NUMBER / Facility Number / FAC_NBR | `facilities.external_facility_number` | /ccld/facilities; /ccld/facilities/detail; /reviewer/records/detail | `NOT_APPLICABLE` | P2 |
| `data.facility.facility.facility_id` | facility | facility normalizer: facility_id | `facilities.facility_id` | not displayed | `INTENTIONALLY_INTERNAL` | P2 |
| `data.facility.facility.facility_name` | facility | FACILITY NAME / Facility Name / NAME | `facilities.facility_name` | /ccld/facilities; /ccld/facilities/detail; /reviewer/records/detail | `NOT_APPLICABLE` | P2 |
| `data.facility.facility.facility_type` | facility | facility normalizer: facility_type | `facilities.facility_type` | /ccld/facilities/detail | `NOT_APPLICABLE` | P2 |
| `data.facility.facility.licensee_name` | facility | facility normalizer: licensee_name | `facilities.licensee_name` | not displayed | `INTENTIONALLY_INTERNAL` | P2 |
| `data.facility.facility.regional_office` | facility | facility normalizer: regional_office | `facilities.regional_office` | /ccld/facilities/detail | `NOT_APPLICABLE` | P2 |
| `data.facility.facility.source_id` | facility | facility normalizer: source_id | `facilities.source_id` | not displayed | `INTENTIONALLY_INTERNAL` | P2 |
| `data.facility.facility.status` | facility | facility normalizer: status | `facilities.status` | /ccld/facilities/detail | `NOT_APPLICABLE` | P2 |
| `data.facility.facility_fixture_ccld_program_facilities_tiny.all_visit_dates` | facility | CSV header: All Visit Dates | `not allocated` | not displayed | `EXTRACTED_CANONICAL_MAPPING_MISSING` | P1 |
| `data.facility.facility_fixture_ccld_program_facilities_tiny.citation_numbers` | facility | CSV header: Citation Numbers | `not allocated` | /ccld/facilities/detail | `EXTRACTED_CANONICAL_MAPPING_MISSING` | P2 |
| `data.facility.facility_fixture_ccld_program_facilities_tiny.closed_date` | facility | CSV header: Closed Date | `not allocated` | /ccld/facilities/detail | `NOT_APPLICABLE` | P2 |
| `data.facility.facility_fixture_ccld_program_facilities_tiny.complaint_info_date_sub_aleg_inc_aleg_uns_aleg_typea_typeb` | facility | CSV header: Complaint Info- Date, #Sub Aleg, # Inc Aleg, # Uns Aleg, # TypeA, # TypeB ... | `not allocated` | not displayed | `EXTRACTED_CANONICAL_MAPPING_MISSING` | P1 |
| `data.facility.facility_fixture_ccld_program_facilities_tiny.complaint_visits` | facility | CSV header: Complaint Visits | `not allocated` | /ccld/facilities/detail | `EXTRACTED_CANONICAL_MAPPING_MISSING` | P2 |
| `data.facility.facility_fixture_ccld_program_facilities_tiny.county_name` | facility | CSV header: County Name | `facilities.county` | /ccld/facilities/detail | `NOT_APPLICABLE` | P2 |
| `data.facility.facility_fixture_ccld_program_facilities_tiny.facility_address` | facility | CSV header: Facility Address | `not allocated` | not displayed | `STORED_QUERY_OMISSION` | P1 |
| `data.facility.facility_fixture_ccld_program_facilities_tiny.facility_administrator` | facility | CSV header: Facility Administrator | `not allocated` | not displayed | `INTENTIONALLY_INTERNAL` | P1 |
| `data.facility.facility_fixture_ccld_program_facilities_tiny.facility_capacity` | facility | CSV header: Facility Capacity | `facilities.capacity` | /ccld/facilities/detail | `NOT_APPLICABLE` | P2 |
| `data.facility.facility_fixture_ccld_program_facilities_tiny.facility_city` | facility | CSV header: Facility City | `not allocated` | /ccld/facilities/detail | `EXTRACTED_CANONICAL_MAPPING_MISSING` | P2 |
| `data.facility.facility_fixture_ccld_program_facilities_tiny.facility_name` | facility | CSV header: Facility Name | `facilities.facility_name` | /ccld/facilities/detail | `NOT_APPLICABLE` | P2 |
| `data.facility.facility_fixture_ccld_program_facilities_tiny.facility_number` | facility | CSV header: Facility Number | `facilities.external_facility_number` | /ccld/facilities/detail | `NOT_APPLICABLE` | P2 |
| `data.facility.facility_fixture_ccld_program_facilities_tiny.facility_state` | facility | CSV header: Facility State | `not allocated` | /ccld/facilities/detail | `EXTRACTED_CANONICAL_MAPPING_MISSING` | P2 |
| `data.facility.facility_fixture_ccld_program_facilities_tiny.facility_status` | facility | CSV header: Facility Status | `facilities.status` | /ccld/facilities/detail | `NOT_APPLICABLE` | P2 |
| `data.facility.facility_fixture_ccld_program_facilities_tiny.facility_telephone_number` | facility | CSV header: Facility Telephone Number | `not allocated` | not displayed | `INTENTIONALLY_INTERNAL` | P1 |
| `data.facility.facility_fixture_ccld_program_facilities_tiny.facility_type` | facility | CSV header: Facility Type | `facilities.facility_type` | /ccld/facilities/detail | `NOT_APPLICABLE` | P2 |
| `data.facility.facility_fixture_ccld_program_facilities_tiny.facility_zip` | facility | CSV header: Facility Zip | `not allocated` | /ccld/facilities/detail | `EXTRACTED_CANONICAL_MAPPING_MISSING` | P2 |
| `data.facility.facility_fixture_ccld_program_facilities_tiny.inspect_typea` | facility | CSV header: Inspect TypeA | `not allocated` | /ccld/facilities/detail | `EXTRACTED_CANONICAL_MAPPING_MISSING` | P2 |
| `data.facility.facility_fixture_ccld_program_facilities_tiny.inspect_typeb` | facility | CSV header: Inspect TypeB | `not allocated` | /ccld/facilities/detail | `EXTRACTED_CANONICAL_MAPPING_MISSING` | P2 |
| `data.facility.facility_fixture_ccld_program_facilities_tiny.inspection_visit_dates` | facility | CSV header: Inspection Visit Dates | `not allocated` | not displayed | `EXTRACTED_CANONICAL_MAPPING_MISSING` | P1 |
| `data.facility.facility_fixture_ccld_program_facilities_tiny.inspection_visits` | facility | CSV header: Inspection Visits | `not allocated` | /ccld/facilities/detail | `EXTRACTED_CANONICAL_MAPPING_MISSING` | P2 |
| `data.facility.facility_fixture_ccld_program_facilities_tiny.last_visit_date` | facility | CSV header: Last Visit Date | `not allocated` | /ccld/facilities/detail | `EXTRACTED_CANONICAL_MAPPING_MISSING` | P2 |
| `data.facility.facility_fixture_ccld_program_facilities_tiny.license_first_date` | facility | CSV header: License First Date | `not allocated` | /ccld/facilities/detail | `EXTRACTED_CANONICAL_MAPPING_MISSING` | P2 |
| `data.facility.facility_fixture_ccld_program_facilities_tiny.licensee` | facility | CSV header: Licensee | `facilities.licensee_name` | not displayed | `INTENTIONALLY_INTERNAL` | P1 |
| `data.facility.facility_fixture_ccld_program_facilities_tiny.other_typea` | facility | CSV header: Other TypeA | `not allocated` | /ccld/facilities/detail | `EXTRACTED_CANONICAL_MAPPING_MISSING` | P2 |
| `data.facility.facility_fixture_ccld_program_facilities_tiny.other_typeb` | facility | CSV header: Other TypeB | `not allocated` | /ccld/facilities/detail | `EXTRACTED_CANONICAL_MAPPING_MISSING` | P2 |
| `data.facility.facility_fixture_ccld_program_facilities_tiny.other_visit_dates` | facility | CSV header: Other Visit Dates | `not allocated` | not displayed | `EXTRACTED_CANONICAL_MAPPING_MISSING` | P1 |
| `data.facility.facility_fixture_ccld_program_facilities_tiny.other_visits` | facility | CSV header: Other Visits | `not allocated` | /ccld/facilities/detail | `EXTRACTED_CANONICAL_MAPPING_MISSING` | P2 |
| `data.facility.facility_fixture_ccld_program_facilities_tiny.poc_dates` | facility | CSV header: POC Dates | `not allocated` | /ccld/facilities/detail | `EXTRACTED_CANONICAL_MAPPING_MISSING` | P2 |
| `data.facility.facility_fixture_ccld_program_facilities_tiny.regional_office` | facility | CSV header: Regional Office | `facilities.regional_office` | /ccld/facilities/detail | `NOT_APPLICABLE` | P2 |
| `data.facility.facility_fixture_ccld_program_facilities_tiny.total_visits` | facility | CSV header: Total Visits | `not allocated` | /ccld/facilities/detail | `EXTRACTED_CANONICAL_MAPPING_MISSING` | P2 |
| `data.facility.facility_fixture_chhs_facility_master_tiny.capacity` | facility | CSV header: CAPACITY | `facilities.capacity` | /ccld/facilities/detail | `NOT_APPLICABLE` | P2 |
| `data.facility.facility_fixture_chhs_facility_master_tiny.client_served` | facility | CSV header: CLIENT_SERVED | `not allocated` | not displayed | `EXTRACTED_CANONICAL_MAPPING_MISSING` | P1 |
| `data.facility.facility_fixture_chhs_facility_master_tiny.county` | facility | CSV header: COUNTY | `facilities.county` | /ccld/facilities/detail | `NOT_APPLICABLE` | P2 |
| `data.facility.facility_fixture_chhs_facility_master_tiny.fac_co_nbr` | facility | CSV header: FAC_CO_NBR | `not allocated` | not displayed | `INTENTIONALLY_INTERNAL` | P1 |
| `data.facility.facility_fixture_chhs_facility_master_tiny.fac_do_desc` | facility | CSV header: FAC_DO_DESC | `not allocated` | not displayed | `STORED_QUERY_OMISSION` | P1 |
| `data.facility.facility_fixture_chhs_facility_master_tiny.fac_latitude` | facility | CSV header: FAC_LATITUDE | `not allocated` | not displayed | `INTENTIONALLY_INTERNAL` | P1 |
| `data.facility.facility_fixture_chhs_facility_master_tiny.fac_longitude` | facility | CSV header: FAC_LONGITUDE | `not allocated` | not displayed | `INTENTIONALLY_INTERNAL` | P1 |
| `data.facility.facility_fixture_chhs_facility_master_tiny.fac_nbr` | facility | CSV header: FAC_NBR | `facilities.external_facility_number` | /ccld/facilities/detail | `NOT_APPLICABLE` | P2 |
| `data.facility.facility_fixture_chhs_facility_master_tiny.fac_phone_nbr` | facility | CSV header: FAC_PHONE_NBR | `not allocated` | not displayed | `INTENTIONALLY_INTERNAL` | P1 |
| `data.facility.facility_fixture_chhs_facility_master_tiny.fac_type_desc` | facility | CSV header: FAC_TYPE_DESC | `facilities.facility_type` | /ccld/facilities/detail | `NOT_APPLICABLE` | P2 |
| `data.facility.facility_fixture_chhs_facility_master_tiny.id` | facility | CSV header: _id | `not allocated` | not displayed | `INTENTIONALLY_INTERNAL` | P1 |
| `data.facility.facility_fixture_chhs_facility_master_tiny.name` | facility | CSV header: NAME | `facilities.facility_name` | /ccld/facilities/detail | `NOT_APPLICABLE` | P2 |
| `data.facility.facility_fixture_chhs_facility_master_tiny.objectid` | facility | CSV header: ObjectId | `not allocated` | not displayed | `INTENTIONALLY_INTERNAL` | P1 |
| `data.facility.facility_fixture_chhs_facility_master_tiny.program_type` | facility | CSV header: PROGRAM_TYPE | `not allocated` | /ccld/facilities/detail | `EXTRACTED_CANONICAL_MAPPING_MISSING` | P2 |
| `data.facility.facility_fixture_chhs_facility_master_tiny.res_city` | facility | CSV header: RES_CITY | `not allocated` | /ccld/facilities/detail | `EXTRACTED_CANONICAL_MAPPING_MISSING` | P2 |
| `data.facility.facility_fixture_chhs_facility_master_tiny.res_state` | facility | CSV header: RES_STATE | `not allocated` | /ccld/facilities/detail | `EXTRACTED_CANONICAL_MAPPING_MISSING` | P2 |
| `data.facility.facility_fixture_chhs_facility_master_tiny.res_street_addr` | facility | CSV header: RES_STREET_ADDR | `not allocated` | not displayed | `STORED_QUERY_OMISSION` | P1 |
| `data.facility.facility_fixture_chhs_facility_master_tiny.res_zip_code` | facility | CSV header: RES_ZIP_CODE | `not allocated` | /ccld/facilities/detail | `EXTRACTED_CANONICAL_MAPPING_MISSING` | P2 |
| `data.facility.facility_fixture_chhs_facility_master_tiny.status` | facility | CSV header: STATUS | `facilities.status` | /ccld/facilities/detail | `NOT_APPLICABLE` | P2 |
| `data.facility.facility_fixture_chhs_facility_master_tiny.type` | facility | CSV header: TYPE | `not allocated` | /ccld/facilities/detail | `EXTRACTED_CANONICAL_MAPPING_MISSING` | P2 |
| `data.facility.facility_fixture_chhs_facility_master_tiny.x` | facility | CSV header: x | `not allocated` | not displayed | `INTENTIONALLY_INTERNAL` | P1 |
| `data.facility.facility_fixture_chhs_facility_master_tiny.y` | facility | CSV header: y | `not allocated` | not displayed | `INTENTIONALLY_INTERNAL` | P1 |
| `data.facility.facility_reference.closed_date_allocation_gap` | facility | Closed Date / closed_date | `not allocated` | /ccld/facilities/detail | `EXTRACTED_CANONICAL_MAPPING_MISSING` | P1 |
| `data.facility.facility_signal.blank_to_zero_risk` | facility | _safe_int and _count_list_values | `not allocated` | /ccld/facilities/detail | `UNEXPLAINED_BLANK` | P0 |
| `data.facility.raw_complaint_report.facility_address` | facility | allowlisted raw label pattern: facility_address | `not allocated` | not displayed | `RAW_PRESENT_EXTRACTION_MISSING` | P0 |
| `data.facility.raw_complaint_report.facility_capacity` | facility | allowlisted raw label pattern: facility_capacity | `facilities.capacity` | not displayed | `RAW_PRESENT_EXTRACTION_MISSING` | P0 |
| `data.facility.raw_complaint_report.facility_city` | facility | allowlisted raw label pattern: facility_city | `not allocated` | not displayed | `RAW_PRESENT_EXTRACTION_MISSING` | P0 |
| `data.facility.raw_complaint_report.regional_office` | facility | allowlisted raw label pattern: regional_office | `facilities.regional_office` | not displayed | `RAW_PRESENT_EXTRACTION_MISSING` | P0 |
| `data.shared.extraction_audit.audit_id` | shared | extraction_audit normalizer: audit_id | `extraction_audit.audit_id` | not displayed | `INTENTIONALLY_INTERNAL` | P2 |
| `data.shared.extraction_audit.confidence` | shared | extraction_audit normalizer: confidence | `extraction_audit.confidence` | not displayed | `INTENTIONALLY_INTERNAL` | P2 |
| `data.shared.extraction_audit.document_id` | shared | extraction_audit normalizer: document_id | `extraction_audit.document_id` | not displayed | `INTENTIONALLY_INTERNAL` | P2 |
| `data.shared.extraction_audit.extracted_value` | shared | extraction_audit normalizer: extracted_value | `extraction_audit.extracted_value` | not displayed | `INTENTIONALLY_INTERNAL` | P2 |
| `data.shared.extraction_audit.extraction_method` | shared | extraction_audit normalizer: extraction_method | `extraction_audit.extraction_method` | not displayed | `INTENTIONALLY_INTERNAL` | P2 |
| `data.shared.extraction_audit.extractor_version` | shared | extraction_audit normalizer: extractor_version | `extraction_audit.extractor_version` | not displayed | `INTENTIONALLY_INTERNAL` | P2 |
| `data.shared.extraction_audit.field_name` | shared | extraction_audit normalizer: field_name | `extraction_audit.field_name` | not displayed | `INTENTIONALLY_INTERNAL` | P2 |
| `data.shared.extraction_audit.source_section` | shared | extraction_audit normalizer: source_section | `extraction_audit.source_section` | not displayed | `RAW_PRESENT_EXTRACTION_MISSING` | P1 |
| `data.shared.extraction_audit.source_text` | shared | extraction_audit normalizer: source_text | `extraction_audit.source_text` | not displayed | `RAW_PRESENT_EXTRACTION_MISSING` | P1 |
| `data.shared.extraction_audit.warning` | shared | extraction_audit normalizer: warning | `extraction_audit.warning` | not displayed | `INTENTIONALLY_INTERNAL` | P2 |
| `data.shared.source_document.connector_name` | shared | source_document normalizer: connector_name | `source_documents.connector_name` | not displayed | `INTENTIONALLY_INTERNAL` | P2 |
| `data.shared.source_document.connector_version` | shared | source_document normalizer: connector_version | `source_documents.connector_version` | not displayed | `INTENTIONALLY_INTERNAL` | P2 |
| `data.shared.source_document.content_type` | shared | source_document normalizer: content_type | `source_documents.content_type` | not displayed | `INTENTIONALLY_INTERNAL` | P2 |
| `data.shared.source_document.document_id` | shared | source_document normalizer: document_id | `source_documents.document_id` | not displayed | `INTENTIONALLY_INTERNAL` | P2 |
| `data.shared.source_document.document_type` | shared | source_document normalizer: document_type | `source_documents.document_type` | not displayed | `INTENTIONALLY_INTERNAL` | P2 |
| `data.shared.source_document.facility_id` | shared | source_document normalizer: facility_id | `source_documents.facility_id` | not displayed | `INTENTIONALLY_INTERNAL` | P2 |
| `data.shared.source_document.http_status` | shared | source_document normalizer: http_status | `source_documents.http_status` | not displayed | `INTENTIONALLY_INTERNAL` | P2 |
| `data.shared.source_document.raw_path` | shared | source_document normalizer: raw_path | `source_documents.raw_path` | not displayed | `INTENTIONALLY_INTERNAL` | P2 |
| `data.shared.source_document.raw_sha256` | shared | source_document normalizer: raw_sha256 | `source_documents.raw_sha256` | not displayed | `INTENTIONALLY_INTERNAL` | P2 |
| `data.shared.source_document.report_index` | shared | source_document normalizer: report_index | `source_documents.report_index` | not displayed | `INTENTIONALLY_INTERNAL` | P2 |
| `data.shared.source_document.retrieved_at` | shared | source_document normalizer: retrieved_at | `source_documents.retrieved_at` | not displayed | `INTENTIONALLY_INTERNAL` | P2 |
| `data.shared.source_document.source_id` | shared | source_document normalizer: source_id | `source_documents.source_id` | not displayed | `INTENTIONALLY_INTERNAL` | P2 |
| `data.shared.source_document.source_url` | shared | source_document normalizer: source_url | `source_documents.source_url` | /reviewer/records/detail; review bundle | `NOT_APPLICABLE` | P2 |

## Interpretation

`NOT_APPLICABLE` means the audit found no action represented by the selected primary classification. `INTENTIONALLY_INTERNAL` records a deliberate attorney-tier boundary; it is not permission to expose technical metadata in the primary reviewer workflow.
