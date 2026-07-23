"""Deterministic structural catalog for the source-to-screen completeness audit.

The catalog deliberately reads schema definitions and CSV header rows only.  It never
copies complaint narrative, facility row values, source URLs, or machine-specific paths
into catalog output.  Population and raw-artifact observations belong to the audit
adapters; this module only describes what may be measured and how known structural gaps
are classified.
"""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

from ccld_complaints.source_profiling import FACILITY_SOURCE_COLUMN_MAPPINGS

_CANONICAL_SCHEMA_ENTITIES = (
    "allegation",
    "complaint",
    "event",
    "extraction_audit",
    "facility",
    "source_document",
)

GAP_CLASSIFICATIONS: tuple[str, ...] = (
    "SOURCE_NOT_PROVIDED",
    "RAW_PRESENT_EXTRACTION_MISSING",
    "EXTRACTED_CANONICAL_MAPPING_MISSING",
    "CANONICAL_IMPORT_NOT_POPULATED",
    "SQLITE_POSTGRES_DIVERGENCE",
    "STORED_QUERY_OMISSION",
    "UI_DISPLAY_OMISSION",
    "UNEXPLAINED_BLANK",
    "AGGREGATE_DATA_INSUFFICIENT",
    "FIXTURE_RUNTIME_DIVERGENCE",
    "INTENTIONALLY_INTERNAL",
    "NOT_APPLICABLE",
)

COVERAGE_TERMINAL_CLASSIFICATIONS: tuple[str, ...] = (
    "present_and_populated",
    "present_but_not_extracted",
    "extracted_but_not_allocated",
    "allocated_but_not_imported",
    "stored_but_not_read",
    "read_but_not_rendered",
    "rendered_incorrectly",
    "present_blank",
    "source_label_absent",
    "source_artifact_unavailable",
    "unsupported_layout",
    "conflicting_sources",
    "intentionally_internal",
    "not_applicable",
)

COMPLAINT_REPORT_INVENTORY_VERSION = "1.0.0"
COMPLAINT_REPORT_INVENTORY_PATH = Path(
    "docs/data/complaint-report-field-inventory.csv"
)
COMPLAINT_REPORT_INVENTORY_FIELDNAMES: tuple[str, ...] = (
    "schema_version",
    "field_id",
    "domain",
    "user_facing_concept",
    "source_artifact_type",
    "source_section",
    "source_label",
    "source_presence_state",
    "extractor_field",
    "normalized_field",
    "canonical_table",
    "canonical_column",
    "source_precedence",
    "conflict_behavior",
    "postgresql_population_state",
    "read_model_field",
    "complaint_page_rendering_state",
    "facility_hub_rendering_state",
    "presentation_tier",
    "authoritative_status",
    "required_action",
    "related_issue",
    "safe_notes",
)
COMPLAINT_REPORT_REQUIRED_DOMAINS: tuple[str, ...] = (
    "allegation_categories",
    "allegations",
    "canonical_provenance",
    "complainants_participants",
    "complaint_dates",
    "complaint_identity",
    "confidence_warning_metadata",
    "correction_actions",
    "correction_due_dates",
    "deficiencies",
    "dispositions",
    "document_identity",
    "extraction_metadata",
    "facility_address_contact",
    "facility_identity",
    "facility_type_license_status",
    "findings",
    "import_metadata",
    "investigation_timing",
    "normalization_metadata",
    "office_agency_regional_office",
    "plans_of_correction",
    "regulation_citations",
    "reviewer_operator_presentation",
    "signatures_signatory_roles",
    "source_report_identity",
    "source_traceability",
    "substantiation_state",
    "type_a_type_b_indicators",
    "visits_investigation_activities",
)
COMPLAINT_REPORT_SOURCE_PRESENCE_STATES: tuple[str, ...] = (
    "artifact_unavailable",
    "derived",
    "label_absent",
    "not_applicable",
    "observed_blank",
    "observed_populated",
    "unsupported_layout",
)
COMPLAINT_REPORT_PRESENTATION_TIERS: tuple[str, ...] = (
    "internal",
    "operator",
    "reviewer",
    "reviewer_and_operator",
)
COMPLAINT_REPORT_REQUIRED_ACTIONS: tuple[str, ...] = (
    "blocked_source_unavailable",
    "blocked_unsupported_layout",
    "fully_covered",
    "intentionally_internal",
    "issue_447_canonical_allocation",
    "issue_450_missing_state_presentation",
    "no_action_not_applicable",
)


@dataclass(frozen=True)
class ElementSpec:
    """One safe, structural source-to-screen data-element description."""

    data_element_id: str
    reviewer_facing_name: str
    ownership: str
    source_artifact_type: str
    source_field_or_extractor_reference: str
    source_availability_status: str
    extraction_status: str
    canonical_entity: str | None
    canonical_column: str | None
    data_type: str
    null_meaning: str
    blank_meaning: str
    zero_meaning: str
    query_service_consumer: str
    current_display_route_or_export: str
    recommended_display_location: str
    recommended_display_method: str
    traceability_availability: str
    validation_coverage: str
    gap_classification: str
    disposition: str
    priority: str
    evidence_reference_location: str
    source_observation_field: str | None
    source_observation_sources: tuple[str, ...]
    runtime_table: str | None
    runtime_column: str | None
    reviewer_relevant: bool
    facility_hub_relevant: bool
    complaint_detail_relevant: bool
    dependencies: str
    validation_requirement: str
    authoritative_status: str | None = None


@dataclass(frozen=True)
class ComplaintReportFieldSpec:
    """One value-free Issue #481 complaint-report inventory row."""

    schema_version: str
    field_id: str
    domain: str
    user_facing_concept: str
    source_artifact_type: str
    source_section: str
    source_label: str
    source_presence_state: str
    extractor_field: str
    normalized_field: str
    canonical_table: str
    canonical_column: str
    source_precedence: str
    conflict_behavior: str
    postgresql_population_state: str
    read_model_field: str
    complaint_page_rendering_state: str
    facility_hub_rendering_state: str
    presentation_tier: str
    authoritative_status: str
    required_action: str
    related_issue: str
    safe_notes: str


@dataclass(frozen=True)
class AggregateFeatureSpec:
    """Prerequisite fields and a safe readiness rule for one aggregate feature."""

    feature_id: str
    reviewer_feature: str
    current_route_or_export: str
    required_data_elements: tuple[str, ...]
    gap_classification: str
    zero_or_unavailable_cause: str
    known_query_limit: str
    evidence_reference_location: str
    recommended_validation: str


@dataclass(frozen=True)
class QueryCoverageGap:
    """A query limitation that is not itself a source data element."""

    gap_id: str
    data_element_id: str
    title: str
    description: str
    ownership: str
    gap_classification: str
    priority: str
    disposition: str
    recommended_display_location: str
    dependencies: str
    evidence_reference_location: str
    validation_requirement: str


@dataclass(frozen=True)
class _Presentation:
    consumer: str
    current: str
    recommended_location: str
    recommended_method: str


@dataclass(frozen=True)
class _KnownGap:
    classification: str
    source_status: str
    extraction_status: str
    disposition: str
    priority: str
    evidence: str
    dependencies: str
    validation: str


def stable_data_element_id(*parts: str) -> str:
    """Return ``data.<ownership>.<entity>.<field>`` with safe readable slugs."""

    if len(parts) != 3:
        raise ValueError("Exactly ownership, entity, and field identity parts are required.")
    normalized: list[str] = []
    for part in parts:
        value = unicodedata.normalize("NFKC", part).replace("\\", "/")
        value = " ".join(value.split()).casefold()
        value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
        if not value:
            raise ValueError("Identity parts must not be blank.")
        normalized.append(value)
    return "data." + ".".join(normalized)


def classify_gap(
    *,
    applicable: bool = True,
    intentionally_internal: bool = False,
    fixture_runtime_divergent: bool = False,
    source_available: bool | None = None,
    raw_present: bool = False,
    extracted: bool | None = None,
    canonical_mapped: bool | None = None,
    canonical_populated: bool | None = None,
    sqlite_populated: bool | None = None,
    postgresql_populated: bool | None = None,
    stored: bool | None = None,
    query_consumed: bool | None = None,
    displayed: bool | None = None,
    unexplained_blank: bool = False,
    aggregate_data_sufficient: bool | None = None,
) -> str:
    """Classify the earliest actionable gap using deterministic precedence.

    Precedence is: not applicable, intentional internal scope, fixture/runtime
    divergence, raw extraction, missing source, canonical allocation, canonical import,
    store parity, unexplained blank, query consumption, presentation, aggregate
    readiness, and finally no applicable gap.  Raw presence outranks a contradictory
    source-unavailable flag because it is the more concrete observation.
    """

    if not applicable:
        return "NOT_APPLICABLE"
    if intentionally_internal:
        return "INTENTIONALLY_INTERNAL"
    if fixture_runtime_divergent:
        return "FIXTURE_RUNTIME_DIVERGENCE"
    if raw_present and extracted is False:
        return "RAW_PRESENT_EXTRACTION_MISSING"
    if source_available is False:
        return "SOURCE_NOT_PROVIDED"
    if extracted is True and canonical_mapped is False:
        return "EXTRACTED_CANONICAL_MAPPING_MISSING"
    if canonical_mapped is True and canonical_populated is False:
        return "CANONICAL_IMPORT_NOT_POPULATED"
    if (
        sqlite_populated is not None
        and postgresql_populated is not None
        and sqlite_populated != postgresql_populated
    ):
        return "SQLITE_POSTGRES_DIVERGENCE"
    if unexplained_blank:
        return "UNEXPLAINED_BLANK"
    value_is_stored = canonical_populated if stored is None else stored
    if value_is_stored is True and query_consumed is False:
        return "STORED_QUERY_OMISSION"
    if query_consumed is True and displayed is False:
        return "UI_DISPLAY_OMISSION"
    if aggregate_data_sufficient is False:
        return "AGGREGATE_DATA_INSUFFICIENT"
    return "NOT_APPLICABLE"


def safe_facility_source_header(header: str, column_index: int) -> str:
    """Return an allowlisted source header or a value-free positional placeholder."""

    known_headers = set(_PRELOAD_HEADER_TO_COLUMN)
    known_headers.update(_SIGNAL_HEADER_TO_FIELD)
    known_headers.update(_INTERNAL_FACILITY_HEADERS)
    known_headers.update(_source_profile_header_map())
    if header in known_headers:
        return header
    return f"Unmapped source column {column_index + 1}"


_OWNERSHIP_BY_ENTITY: Mapping[str, str] = {
    "facility": "facility",
    "source_document": "shared",
    "complaint": "complaint",
    "allegation": "complaint",
    "event": "complaint",
    "extraction_audit": "shared",
}


def _canonical_id(entity: str, column: str) -> str:
    return stable_data_element_id(
        _OWNERSHIP_BY_ENTITY.get(entity, "shared"),
        entity,
        column,
    )


AGGREGATE_FEATURES: tuple[AggregateFeatureSpec, ...] = (
    AggregateFeatureSpec(
        feature_id="facility-priorities",
        reviewer_feature="Facility priorities",
        current_route_or_export="/reviewer/facilities/priorities",
        required_data_elements=(
            _canonical_id("facility", "external_facility_number"),
            _canonical_id("facility", "status"),
            _canonical_id("complaint", "finding"),
        ),
        gap_classification="AGGREGATE_DATA_INSUFFICIENT",
        zero_or_unavailable_cause="facility and complaint coverage may be incomplete",
        known_query_limit="facility priority result window is 100 rows",
        evidence_reference_location="src/ccld_complaints/hosted_app/ccld_facility_lookup.py",
        recommended_validation="Use governed production-style facility and complaint coverage.",
    ),
    AggregateFeatureSpec(
        feature_id="substantiated-review",
        reviewer_feature="Substantiated review",
        current_route_or_export="/reviewer/records/substantiated",
        required_data_elements=(
            _canonical_id("complaint", "finding"),
            _canonical_id("complaint", "complaint_received_date"),
            _canonical_id("complaint", "complaint_control_number"),
        ),
        gap_classification="NOT_APPLICABLE",
        zero_or_unavailable_cause="a zero requires populated finding coverage",
        known_query_limit="page size is bounded; aggregate counts use a separate query",
        evidence_reference_location="src/ccld_complaints/hosted_app/reviewer_ui.py",
        recommended_validation="Verify finding variants and an explicit valid-zero corpus.",
    ),
    AggregateFeatureSpec(
        feature_id="serious-topic-review",
        reviewer_feature="Serious-topic review",
        current_route_or_export="/reviewer/records/serious-topics",
        required_data_elements=(
            _canonical_id("allegation", "allegation_text"),
            _canonical_id("allegation", "allegation_category"),
        ),
        gap_classification="AGGREGATE_DATA_INSUFFICIENT",
        zero_or_unavailable_cause="source-derived allegation categories are not populated",
        known_query_limit="keyword cues are fallback evidence, not source categories",
        evidence_reference_location="src/ccld_complaints/hosted_app/reviewer_ui.py",
        recommended_validation="Separate source categories from cautious keyword cues.",
    ),
    AggregateFeatureSpec(
        feature_id="complaint-trends",
        reviewer_feature="Complaint trends and anomaly cues",
        current_route_or_export="/reviewer/facilities/trends",
        required_data_elements=(
            _canonical_id("complaint", "facility_id"),
            _canonical_id("complaint", "complaint_received_date"),
            _canonical_id("complaint", "finding"),
        ),
        gap_classification="NOT_APPLICABLE",
        zero_or_unavailable_cause="date and facility linkage determine eligibility",
        known_query_limit="date-range and incomplete-period states are explicit",
        evidence_reference_location="src/ccld_complaints/hosted_app/facility_trends.py",
        recommended_validation="Test valid zero, unavailable coverage, and incomplete periods.",
    ),
    AggregateFeatureSpec(
        feature_id="complaint-facility-exports",
        reviewer_feature="Complaint and facility exports",
        current_route_or_export="review bundle and stakeholder workbook exports",
        required_data_elements=(
            _canonical_id("facility", "external_facility_number"),
            _canonical_id("complaint", "complaint_control_number"),
            _canonical_id("complaint", "finding"),
            _canonical_id("source_document", "source_url"),
        ),
        gap_classification="NOT_APPLICABLE",
        zero_or_unavailable_cause="export coverage follows the inspected loaded corpus",
        known_query_limit="no default row limit; explicit limits report truncation",
        evidence_reference_location="src/ccld_complaints/review_bundle.py",
        recommended_validation="Compare export counts with governed store aggregates.",
    ),
)


QUERY_COVERAGE_GAPS: tuple[QueryCoverageGap, ...] = ()


_TABLE_BY_ENTITY: Mapping[str, str] = {
    "facility": "facilities",
    "source_document": "source_documents",
    "complaint": "complaints",
    "allegation": "allegations",
    "event": "events",
    "extraction_audit": "extraction_audit",
}

_GOVERNED_FACILITY_FIXTURES: tuple[Path, ...] = (
    Path("tests/fixtures/public_source_facilities/ccld_program_facilities_tiny.csv"),
    Path("tests/fixtures/public_source_facilities/chhs_facility_master_tiny.csv"),
)

_COMPLAINT_SOURCE_IDS = (
    "retained_raw_complaint_artifacts",
    "governed_complaint_fixtures",
)
_RAW_FACILITY_SOURCE_IDS = (
    *_COMPLAINT_SOURCE_IDS,
    "governed_facility_page_fixtures",
)
_FACILITY_SOURCE_IDS = (
    "governed_facility_fixtures",
    "governed_facility_page_fixtures",
    "retained_facility_reference_artifacts",
)

_PRELOAD_HEADER_TO_COLUMN: Mapping[str, str] = {
    "Facility Number": "facility_number",
    "FAC_NBR": "facility_number",
    "Facility Name": "facility_name",
    "NAME": "facility_name",
    "Facility Type": "facility_type",
    "FAC_TYPE_DESC": "facility_type",
    "Program Type": "program_type",
    "PROGRAM_TYPE": "program_type",
    "CLIENT_SERVED": "client_served",
    "Licensee": "licensee_name",
    "LICENSEE": "licensee_name",
    "Facility Administrator": "facility_administrator",
    "ADMINISTRATOR": "facility_administrator",
    "Facility Telephone Number": "telephone",
    "FAC_PHONE_NBR": "telephone",
    "PHONE": "telephone",
    "Facility Address": "address",
    "RES_STREET_ADDR": "address",
    "ADDRESS": "address",
    "Facility City": "city",
    "RES_CITY": "city",
    "CITY": "city",
    "Facility State": "state",
    "RES_STATE": "state",
    "STATE": "state",
    "Facility Zip": "zip",
    "RES_ZIP_CODE": "zip",
    "ZIP": "zip",
    "County Name": "county",
    "COUNTY": "county",
    "Regional Office": "regional_office",
    "FAC_DO_DESC": "regional_office",
    "Facility Capacity": "capacity",
    "CAPACITY": "capacity",
    "Facility Status": "status",
    "STATUS": "status",
    "License First Date": "license_first_date",
    "LICENSE_FIRST_DATE": "license_first_date",
    "Closed Date": "closed_date",
    "CLOSED_DATE": "closed_date",
    "All Visit Dates": "all_visit_dates",
    "Inspection Visit Dates": "inspection_visit_dates",
    "Other Visit Dates": "other_visit_dates",
}

_ISSUE_447_SOURCE_REFERENCE_ALLOCATIONS: Mapping[
    str, tuple[str | None, str, str, bool]
] = {
    "All Visit Dates": (
        "all_visit_dates",
        "nullable ordered array of ISO dates",
        "retain as a typed source-reference-only date collection",
        False,
    ),
    "Inspection Visit Dates": (
        "inspection_visit_dates",
        "nullable ordered array of ISO dates",
        "retain as a typed source-reference-only date collection",
        False,
    ),
    "Other Visit Dates": (
        "other_visit_dates",
        "nullable ordered array of ISO dates",
        "retain as a typed source-reference-only date collection",
        False,
    ),
    "Complaint Info- Date, #Sub Aleg, # Inc Aleg, # Uns Aleg, # TypeA, # TypeB ...": (
        None,
        "source string or CSV overflow sequence",
        "retain the unflattened source representation in original-row provenance",
        False,
    ),
    "CLIENT_SERVED": (
        "client_served",
        "nullable source string",
        "retain as typed source-reference-only context pending source confirmation",
        False,
    ),
    "Closed Date": (
        "closed_date",
        "nullable ISO date",
        "retain as a typed facility-reference lifecycle date; do not infer open status",
        True,
    ),
    "CLOSED_DATE": (
        "closed_date",
        "nullable ISO date",
        "retain as a typed facility-reference lifecycle date; do not infer open status",
        True,
    ),
}

_SIGNAL_HEADER_TO_FIELD: Mapping[str, str] = {
    "Facility Type": "facility_type",
    "Facility Number": "facility_number",
    "Facility Name": "facility_name",
    "Facility City": "city",
    "Facility State": "state",
    "Facility Zip": "zip_code",
    "County Name": "county",
    "Regional Office": "regional_office",
    "Facility Capacity": "capacity",
    "Facility Status": "status",
    "License First Date": "license_first_date",
    "Closed Date": "closed_date",
    "Last Visit Date": "last_visit_date",
    "Inspection Visits": "inspection_visit_count",
    "Complaint Visits": "complaint_visit_count",
    "Other Visits": "other_visit_count",
    "Total Visits": "total_visit_count",
    "Citation Numbers": "citation_count",
    "POC Dates": "poc_date_count",
    "Inspect TypeA": "type_a_citation_count",
    "Inspect TypeB": "type_b_citation_count",
    "Other TypeA": "type_a_citation_count",
    "Other TypeB": "type_b_citation_count",
}

_INTERNAL_FACILITY_HEADERS = frozenset(
    {
        "_id",
        "ObjectId",
        "x",
        "y",
        "FAC_LATITUDE",
        "FAC_LONGITUDE",
        "FAC_CO_NBR",
        "TYPE",
        "Facility Administrator",
        "Facility Telephone Number",
        "FAC_PHONE_NBR",
        "Licensee",
        "LICENSEE",
    }
)

_FACILITY_SIGNAL_COUNT_HEADERS = frozenset(
    {
        "Inspection Visits",
        "Complaint Visits",
        "Other Visits",
        "Total Visits",
        "Citation Numbers",
        "POC Dates",
        "Inspect TypeA",
        "Inspect TypeB",
        "Other TypeA",
        "Other TypeB",
    }
)

_PRESENTATION_REGISTRY: Mapping[tuple[str, str], _Presentation] = {
    ("facility", "external_facility_number"): _Presentation(
        "facility lookup and complaint detail",
        "/ccld/facilities; /ccld/facilities/detail; /reviewer/records/detail",
        "facility hub identity", "copyable labeled identifier",
    ),
    ("facility", "facility_name"): _Presentation(
        "facility lookup and complaint detail",
        "/ccld/facilities; /ccld/facilities/detail; /reviewer/records/detail",
        "facility hub identity", "labeled identity fact",
    ),
    ("facility", "facility_type"): _Presentation(
        "facility lookup and facility hub", "/ccld/facilities/detail",
        "facility hub license facts", "single labeled fact",
    ),
    ("facility", "county"): _Presentation(
        "facility lookup and facility hub", "/ccld/facilities/detail",
        "facility hub location facts", "single labeled fact",
    ),
    ("facility", "status"): _Presentation(
        "facility lookup and facility hub", "/ccld/facilities/detail",
        "facility hub license facts", "status badge plus labeled fact",
    ),
    ("facility", "capacity"): _Presentation(
        "facility lookup and facility review signals",
        "/ccld/facilities/detail", "facility hub license facts",
        "source-qualified numeric fact",
    ),
    ("facility", "regional_office"): _Presentation(
        "facility review signals", "/ccld/facilities/detail",
        "facility hub location facts", "single labeled fact",
    ),
    ("source_document", "source_url"): _Presentation(
        "complaint detail and exports", "/reviewer/records/detail; review bundle",
        "complaint detail primary action", "external source link",
    ),
    ("complaint", "complaint_control_number"): _Presentation(
        "review queues and complaint detail", "/reviewer/records; /reviewer/records/detail",
        "complaint detail identity", "copyable labeled identifier",
    ),
    ("complaint", "complaint_received_date"): _Presentation(
        "review queues, detail, trends, and exports",
        "/reviewer/records/detail source timeline",
        "complaint detail source timeline", "date with unavailable state",
    ),
    ("complaint", "first_investigation_activity_date"): _Presentation(
        "complaint detail", "/reviewer/records/detail source timeline",
        "complaint detail source timeline", "date with extraction-coverage qualifier",
    ),
    ("complaint", "visit_date"): _Presentation(
        "review queues, detail, trends, and exports",
        "/reviewer/records/detail source timeline",
        "complaint detail source timeline", "date with unavailable state",
    ),
    ("complaint", "report_date"): _Presentation(
        "review queues, detail, trends, and exports",
        "/reviewer/records/detail source timeline",
        "complaint detail source timeline", "date with proxy warning when applicable",
    ),
    ("complaint", "date_signed"): _Presentation(
        "review queues, detail, and exports", "/reviewer/records/detail source timeline",
        "complaint detail source timeline", "date with unavailable state",
    ),
    ("complaint", "finding"): _Presentation(
        "review queues, detail, aggregates, and exports", "/reviewer/records/detail",
        "complaint detail", "source-derived finding badge",
    ),
    ("allegation", "allegation_text"): _Presentation(
        "complaint detail and serious-topic review", "/reviewer/records/detail",
        "complaint detail allegations", "source narrative with safe empty state",
    ),
    ("allegation", "finding"): _Presentation(
        "complaint detail", "/reviewer/records/detail",
        "complaint detail allegations", "finding badge per allegation",
    ),
    ("allegation", "allegation_category"): _Presentation(
        "serious-topic service and export",
        "/reviewer/records/serious-topics; stakeholder export",
        "serious-topic review", "source-category label distinct from keyword cue",
    ),
    ("event", "event_date"): _Presentation(
        "activity and narrative helpers", "/reviewer/records/detail source timeline",
        "complaint detail source timeline", "dated event row",
    ),
    ("event", "event_type"): _Presentation(
        "activity helper", "/reviewer/records/detail source timeline",
        "complaint detail source timeline", "event-type label",
    ),
    ("event", "event_text"): _Presentation(
        "source narrative helper", "/reviewer/records/detail bounded event excerpt",
        "complaint detail narrative", "source excerpt with traceability",
    ),
}

_INTENTIONALLY_INTERNAL_FIELDS = frozenset(
    {
        ("facility", "facility_id"),
        ("facility", "source_id"),
        ("facility", "licensee_name"),
        ("source_document", "document_id"),
        ("source_document", "source_id"),
        ("source_document", "facility_id"),
        ("source_document", "retrieved_at"),
        ("source_document", "raw_sha256"),
        ("source_document", "connector_name"),
        ("source_document", "connector_version"),
        ("source_document", "raw_path"),
        ("source_document", "document_type"),
        ("source_document", "report_index"),
        ("source_document", "http_status"),
        ("source_document", "content_type"),
        ("complaint", "complaint_id"),
        ("complaint", "facility_id"),
        ("complaint", "document_id"),
        ("complaint", "review_delay_over_30_days"),
        ("complaint", "review_delay_over_60_days"),
        ("complaint", "review_delay_over_90_days"),
        ("complaint", "review_delay_over_120_days"),
        ("complaint", "missing_first_activity_date"),
        ("complaint", "report_date_used_as_proxy"),
        ("complaint", "extraction_confidence"),
        ("allegation", "allegation_id"),
        ("allegation", "complaint_id"),
        ("allegation", "extraction_confidence"),
        ("event", "event_id"),
        ("event", "complaint_id"),
        ("event", "extracted_from_section"),
        ("event", "extraction_confidence"),
        ("extraction_audit", "audit_id"),
        ("extraction_audit", "document_id"),
        ("extraction_audit", "field_name"),
        ("extraction_audit", "extraction_method"),
        ("extraction_audit", "extractor_version"),
        ("extraction_audit", "extracted_value"),
        ("extraction_audit", "confidence"),
        ("extraction_audit", "warning"),
    }
)

_TIMING_DISPLAY_OMISSIONS = (
    "days_received_to_visit",
    "days_received_to_report",
    "days_report_to_signed",
)

_KNOWN_GAPS: Mapping[tuple[str, str], _KnownGap] = {
    ("complaint", "first_investigation_activity_date"): _KnownGap(
        "NOT_APPLICABLE", "governed investigation activity wording is present",
        "deterministically extracted with bounded source evidence", "retain and measure",
        "P2", "src/ccld_complaints/connectors/ccld/facility_reports.py#extract",
        "governed investigation activity wording",
        "Keep fixture regressions for supported first-activity wording and malformed dates.",
    ),
    ("complaint", "days_received_to_first_activity"): _KnownGap(
        "NOT_APPLICABLE", "derived after both dates are available",
        "deterministically populated when governed first-activity extraction succeeds",
        "retain and measure", "P2",
        "src/ccld_complaints/connectors/ccld/facility_reports.py#_delay_metrics",
        "governed first investigation activity extraction",
        "Test null prerequisite, verified zero-day interval, and positive interval.",
    ),
    ("allegation", "allegation_category"): _KnownGap(
        "SOURCE_NOT_PROVIDED", "no explicit source taxonomy is established",
        "normalizer assigns null", "retain null until a governed mapping is approved", "P1",
        "src/ccld_complaints/connectors/ccld/facility_reports.py#normalize",
        "governed serious-topic taxonomy decision",
        "Keep source categories distinct from keyword-assisted cues.",
    ),
    ("extraction_audit", "source_text"): _KnownGap(
        "NOT_APPLICABLE", "raw source body retained",
        "target audit rows capture bounded source evidence", "retain without audit exports", "P2",
        "src/ccld_complaints/connectors/ccld/facility_reports.py#_audit_records",
        "privacy-safe source evidence design",
        "Assert audit output never exports source text values.",
    ),
    ("extraction_audit", "source_section"): _KnownGap(
        "NOT_APPLICABLE", "raw report sections are deterministically identified",
        "target audit rows capture safe section labels", "retain and measure", "P2",
        "src/ccld_complaints/connectors/ccld/facility_reports.py#_audit_records",
        "section-label extraction",
        "Use label-only fixture assertions without narrative values.",
    ),
    **{
        ("complaint", field): _KnownGap(
            "UI_DISPLAY_OMISSION", "derived from populated complaint dates",
            "deterministically derived and stored when prerequisites exist",
            "show once in complaint detail timing context", "P1",
            "src/ccld_complaints/hosted_app/reviewer_ui.py#_render_complaint_timeline_section",
            "population coverage for prerequisite dates",
            "Test populated, unavailable, and verified-zero timing values.",
        )
        for field in _TIMING_DISPLAY_OMISSIONS
    },
    **{
        ("event", field): _KnownGap(
            "NOT_APPLICABLE", "governed investigation activity wording is present",
            "connector emits a bounded deterministic investigation activity event",
            "retain and measure", "P2",
            "src/ccld_complaints/connectors/ccld/facility_reports.py",
            "governed event boundary and date rules",
            "Keep governed event, malformed-date, and missing-date regressions.",
        )
        for field in ("event_date", "event_type", "event_text")
    },
}

_RAW_ONLY_FIELDS: tuple[tuple[str, str, str, str | None, str, str], ...] = (
    ("facility_address", "Facility address from complaint report", "facility", None,
     "facility hub location facts", "single labeled address fact"),
    ("facility_capacity", "Facility capacity from complaint report", "facility", "capacity",
     "facility hub license facts", "source-qualified numeric fact"),
    ("facility_city", "Facility city from complaint report", "facility", None,
     "facility hub location facts", "single labeled location fact"),
    ("regional_office", "Regional office from complaint report", "facility", "regional_office",
     "facility hub location facts", "single labeled fact"),
    ("investigation_findings_narrative", "Investigation narrative", "complaint", None,
     "complaint detail source narrative", "bounded excerpt with source link"),
)


def load_complaint_report_field_inventory(
    repo_root: Path,
) -> tuple[ComplaintReportFieldSpec, ...]:
    """Load and validate the governed, value-free Issue #481 field inventory."""

    path = repo_root / COMPLAINT_REPORT_INVENTORY_PATH
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            if tuple(reader.fieldnames or ()) != COMPLAINT_REPORT_INVENTORY_FIELDNAMES:
                raise ValueError(
                    "The complaint-report field inventory header does not match "
                    "the governed schema."
                )
            raw_rows = tuple(dict(row) for row in reader)
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise ValueError(
            "The governed complaint-report field inventory could not be read."
        ) from exc
    if not raw_rows:
        raise ValueError("The governed complaint-report field inventory is empty.")

    rows: list[ComplaintReportFieldSpec] = []
    field_ids: list[str] = []
    for raw_row in raw_rows:
        if set(raw_row) != set(COMPLAINT_REPORT_INVENTORY_FIELDNAMES):
            raise ValueError("A complaint-report field inventory row has unknown columns.")
        row = ComplaintReportFieldSpec(
            **{
                name: " ".join(str(raw_row.get(name, "")).split())
                for name in COMPLAINT_REPORT_INVENTORY_FIELDNAMES
            }
        )
        if row.schema_version != COMPLAINT_REPORT_INVENTORY_VERSION:
            raise ValueError("The complaint-report field inventory version is unsupported.")
        if not re.fullmatch(
            r"data\.[a-z0-9_]+\.[a-z0-9_]+\.[a-z0-9_]+", row.field_id
        ):
            raise ValueError("A complaint-report field identifier is invalid.")
        if row.domain not in COMPLAINT_REPORT_REQUIRED_DOMAINS:
            raise ValueError("A complaint-report field domain is not governed.")
        if row.source_presence_state not in COMPLAINT_REPORT_SOURCE_PRESENCE_STATES:
            raise ValueError("A complaint-report source-presence state is not governed.")
        if row.presentation_tier not in COMPLAINT_REPORT_PRESENTATION_TIERS:
            raise ValueError("A complaint-report presentation tier is not governed.")
        if row.authoritative_status not in COVERAGE_TERMINAL_CLASSIFICATIONS:
            raise ValueError("A complaint-report authoritative status is not governed.")
        if row.required_action not in COMPLAINT_REPORT_REQUIRED_ACTIONS:
            raise ValueError("A complaint-report required action is not governed.")
        if bool(row.canonical_table) != bool(row.canonical_column):
            raise ValueError(
                "Complaint-report canonical table and column must be allocated together."
            )
        required_text = (
            row.user_facing_concept,
            row.source_artifact_type,
            row.source_section,
            row.source_precedence,
            row.conflict_behavior,
            row.postgresql_population_state,
            row.complaint_page_rendering_state,
            row.facility_hub_rendering_state,
            row.related_issue,
            row.safe_notes,
        )
        if any(not value for value in required_text):
            raise ValueError("A complaint-report inventory row is missing required text.")
        combined = " ".join(str(getattr(row, name)) for name in row.__dataclass_fields__)
        if re.search(r"(?i)\bhttps?://|[a-z]:[\\/]|\\\\[a-z0-9_.-]+\\", combined):
            raise ValueError(
                "Complaint-report inventory rows may not contain URLs or private paths."
            )
        rows.append(row)
        field_ids.append(row.field_id)

    if field_ids != sorted(field_ids):
        raise ValueError("Complaint-report inventory rows must use deterministic ID order.")
    if len(field_ids) != len(set(field_ids)):
        raise ValueError("Complaint-report inventory field identifiers must be unique.")
    domains = {row.domain for row in rows}
    if domains != set(COMPLAINT_REPORT_REQUIRED_DOMAINS):
        raise ValueError("Complaint-report inventory domain coverage is incomplete.")
    return tuple(rows)


def _complaint_report_gap_classification(authoritative_status: str) -> str:
    return {
        "present_and_populated": "NOT_APPLICABLE",
        "present_but_not_extracted": "RAW_PRESENT_EXTRACTION_MISSING",
        "extracted_but_not_allocated": "EXTRACTED_CANONICAL_MAPPING_MISSING",
        "allocated_but_not_imported": "CANONICAL_IMPORT_NOT_POPULATED",
        "stored_but_not_read": "STORED_QUERY_OMISSION",
        "read_but_not_rendered": "UI_DISPLAY_OMISSION",
        "rendered_incorrectly": "UI_DISPLAY_OMISSION",
        "present_blank": "UNEXPLAINED_BLANK",
        "source_label_absent": "SOURCE_NOT_PROVIDED",
        "source_artifact_unavailable": "SOURCE_NOT_PROVIDED",
        "unsupported_layout": "AGGREGATE_DATA_INSUFFICIENT",
        "conflicting_sources": "AGGREGATE_DATA_INSUFFICIENT",
        "intentionally_internal": "INTENTIONALLY_INTERNAL",
        "not_applicable": "NOT_APPLICABLE",
    }[authoritative_status]


def _complaint_report_element_spec(row: ComplaintReportFieldSpec) -> ElementSpec:
    ownership = row.field_id.split(".")[1]
    entity_by_table = {table: entity for entity, table in _TABLE_BY_ENTITY.items()}
    canonical_entity = entity_by_table.get(row.canonical_table)
    current_homes: list[str] = []
    if row.complaint_page_rendering_state == "rendered":
        current_homes.append("/reviewer/records/detail")
    if row.facility_hub_rendering_state == "rendered":
        current_homes.append("/ccld/facilities/detail")
    reviewer_relevant = row.presentation_tier in {"reviewer", "reviewer_and_operator"}
    observation_field: str | None = (
        row.extractor_field or _source_field_id(row.source_label)
    )
    if observation_field is not None:
        observation_field = {
            "interviewed_participant": "participant_identity",
            "telephone": "facility_contact",
        }.get(observation_field, observation_field)
    if row.source_presence_state in {
        "artifact_unavailable",
        "derived",
        "label_absent",
        "not_applicable",
        "unsupported_layout",
    }:
        observation_field = None
    return ElementSpec(
        data_element_id=row.field_id,
        reviewer_facing_name=row.user_facing_concept,
        ownership=ownership,
        source_artifact_type=row.source_artifact_type,
        source_field_or_extractor_reference=(
            row.source_label or row.extractor_field or "structural inventory state"
        ),
        source_availability_status=row.source_presence_state,
        extraction_status=(
            "deterministically extracted"
            if row.extractor_field
            else "not extracted by the current complaint-report connector"
        ),
        canonical_entity=canonical_entity,
        canonical_column=row.canonical_column or None,
        data_type="source string",
        null_meaning="source value unavailable, absent, or not allocated",
        blank_meaning="present blank is distinct from an absent source label",
        zero_meaning="not applicable unless the source explicitly supplies numeric zero",
        query_service_consumer=row.read_model_field or "none",
        current_display_route_or_export="; ".join(current_homes),
        recommended_display_location=(
            "internal operator evidence"
            if row.presentation_tier in {"internal", "operator"}
            else "complaint detail or Facility Overview according to the governed field"
        ),
        recommended_display_method=(
            "governed labeled fact or explicit missing-state presentation"
        ),
        traceability_availability=(
            "stable source section and label identity; aggregate evidence excludes values"
        ),
        validation_coverage=(
            "Issue #481 governed fixture-layout and deterministic inventory tests"
        ),
        gap_classification=_complaint_report_gap_classification(
            row.authoritative_status
        ),
        disposition=row.required_action,
        priority="P1" if row.required_action.startswith("issue_") else "P2",
        evidence_reference_location=(
            f"{COMPLAINT_REPORT_INVENTORY_PATH.as_posix()}#{row.field_id}"
        ),
        source_observation_field=observation_field,
        source_observation_sources=_COMPLAINT_SOURCE_IDS if observation_field else (),
        runtime_table=None,
        runtime_column=None,
        reviewer_relevant=reviewer_relevant,
        facility_hub_relevant=row.facility_hub_rendering_state != "not_applicable",
        complaint_detail_relevant=(
            row.complaint_page_rendering_state != "not_applicable"
        ),
        dependencies=row.related_issue,
        validation_requirement=(
            "Preserve the authoritative status, missing-state distinction, and "
            "value-free evidence boundary."
        ),
        authoritative_status=row.authoritative_status,
    )


def discover_element_specs(
    repo_root: Path,
    *,
    include_retained_artifacts: bool = True,
) -> tuple[ElementSpec, ...]:
    """Discover canonical and governed fields, plus retained local headers when allowed."""

    specs: list[ElementSpec] = []
    schema_dir = repo_root / "schemas"
    schema_paths = tuple(
        sorted(
            (
                schema_dir / f"{entity}.schema.json"
                for entity in _CANONICAL_SCHEMA_ENTITIES
            ),
            key=lambda path: path.name,
        )
    )
    if not schema_paths:
        raise FileNotFoundError("No canonical schema files were found under schemas/.")
    facility_properties: set[str] = set()
    for schema_path in schema_paths:
        entity = schema_path.name.removesuffix(".schema.json")
        payload = cast(dict[str, Any], json.loads(schema_path.read_text(encoding="utf-8-sig")))
        properties_value = payload.get("properties")
        if not isinstance(properties_value, dict):
            raise ValueError(f"Schema {schema_path.name} does not define object properties.")
        properties = cast(dict[str, Any], properties_value)
        if entity == "facility":
            facility_properties.update(properties)
        required_value = payload.get("required", [])
        required = (
            {str(value) for value in required_value}
            if isinstance(required_value, list)
            else set()
        )
        for column in sorted(properties):
            property_schema = properties[column]
            if not isinstance(property_schema, dict):
                raise ValueError(f"Schema property {entity}.{column} is not an object.")
            specs.append(
                _schema_element_spec(
                    entity=entity,
                    column=column,
                    property_schema=cast(dict[str, Any], property_schema),
                    required=column in required,
                    evidence=f"schemas/{schema_path.name}#properties/{column}",
                )
            )

    profile_map = _source_profile_header_map()
    for relative_path in _GOVERNED_FACILITY_FIXTURES:
        fixture_path = repo_root / relative_path
        if not fixture_path.is_file():
            continue
        for header in _read_header_only(fixture_path):
            specs.append(
                _facility_header_spec(
                    relative_path=relative_path,
                    header=header,
                    profile_field=profile_map.get(header),
                    facility_properties=facility_properties,
                )
            )
    if include_retained_artifacts:
        retained_headers: set[str] = set()
        for retained_path in sorted(
            (repo_root / "data/raw/source-profiling").glob("*.csv"),
            key=lambda path: path.name,
        ):
            if retained_path.is_file():
                retained_headers.update(
                    safe_facility_source_header(header, index)
                    for index, header in enumerate(_read_header_only(retained_path))
                )
        safe_retained_reference = Path(
            "data/raw/source-profiling/<configured-facility-reference>.csv"
        )
        for header in sorted(retained_headers):
            specs.append(
                _facility_header_spec(
                    relative_path=safe_retained_reference,
                    header=header,
                    profile_field=profile_map.get(header),
                    facility_properties=facility_properties,
                )
            )

    specs.extend(_raw_only_specs())
    specs.extend(_curated_structural_specs())
    inventory_path = repo_root / COMPLAINT_REPORT_INVENTORY_PATH
    if inventory_path.is_file():
        complaint_report_rows = load_complaint_report_field_inventory(repo_root)
        by_id = {spec.data_element_id: spec for spec in specs}
        for row in complaint_report_rows:
            existing = by_id.get(row.field_id)
            if existing is None:
                created = _complaint_report_element_spec(row)
                specs.append(created)
                by_id[row.field_id] = created
            else:
                updated = replace(
                    existing,
                    authoritative_status=row.authoritative_status,
                )
                specs[specs.index(existing)] = updated
                by_id[row.field_id] = updated
    ordered = tuple(sorted(specs, key=lambda item: item.data_element_id))
    _assert_unique_ids(ordered)
    return ordered


def _schema_element_spec(
    *,
    entity: str,
    column: str,
    property_schema: Mapping[str, Any],
    required: bool,
    evidence: str,
) -> ElementSpec:
    key = (entity, column)
    ownership = _OWNERSHIP_BY_ENTITY.get(entity, "shared")
    presentation = _PRESENTATION_REGISTRY.get(key, _default_presentation(ownership))
    internal = key in _INTENTIONALLY_INTERNAL_FIELDS
    reviewer_relevant = not internal and entity != "extraction_audit"
    gap = _KNOWN_GAPS.get(key)
    classification = classify_gap(intentionally_internal=internal)
    source_status = "source or deterministic derivation defined"
    extraction_status = "mapped by the active connector or importer"
    disposition = "retain and measure"
    priority = "P2"
    gap_evidence = evidence
    dependencies = "none"
    validation = "Validate canonical schema and aggregate population semantics."
    if gap is not None:
        classification = gap.classification
        source_status = gap.source_status
        extraction_status = gap.extraction_status
        disposition = gap.disposition
        priority = gap.priority
        gap_evidence = f"{evidence}; {gap.evidence}"
        dependencies = gap.dependencies
        validation = gap.validation
        reviewer_relevant = key not in {
            ("extraction_audit", "source_text"),
            ("extraction_audit", "source_section"),
        }
    data_type = _schema_data_type(property_schema)
    observation_field = _canonical_observation_field(entity, column)
    observation_sources: tuple[str, ...] = ()
    if observation_field is not None:
        observation_sources = (
            _RAW_FACILITY_SOURCE_IDS if entity == "facility" else _COMPLAINT_SOURCE_IDS
        )
    return ElementSpec(
        data_element_id=_canonical_id(entity, column),
        reviewer_facing_name=_reviewer_name(column),
        ownership=ownership,
        source_artifact_type=_source_artifact_type(entity),
        source_field_or_extractor_reference=_source_reference(entity, column),
        source_availability_status=source_status,
        extraction_status=extraction_status,
        canonical_entity=entity,
        canonical_column=column,
        data_type=data_type,
        null_meaning=_null_meaning(data_type, required),
        blank_meaning=_blank_meaning(data_type),
        zero_meaning=_zero_meaning(data_type),
        query_service_consumer=presentation.consumer,
        current_display_route_or_export=presentation.current,
        recommended_display_location=presentation.recommended_location,
        recommended_display_method=presentation.recommended_method,
        traceability_availability=_traceability(entity, column),
        validation_coverage=f"{evidence}; canonical JSON Schema",
        gap_classification=classification,
        disposition=disposition,
        priority=priority,
        evidence_reference_location=gap_evidence,
        source_observation_field=observation_field,
        source_observation_sources=observation_sources,
        runtime_table=None,
        runtime_column=None,
        reviewer_relevant=reviewer_relevant,
        facility_hub_relevant=ownership == "facility",
        complaint_detail_relevant=ownership == "complaint" or entity == "source_document",
        dependencies=dependencies,
        validation_requirement=validation,
    )


def _facility_header_spec(
    *,
    relative_path: Path,
    header: str,
    profile_field: str | None,
    facility_properties: set[str],
) -> ElementSpec:
    is_governed_fixture = relative_path.parts[:2] == ("tests", "fixtures")
    preload_column = _PRELOAD_HEADER_TO_COLUMN.get(header)
    signal_field = _SIGNAL_HEADER_TO_FIELD.get(header)
    source_reference_allocation = _ISSUE_447_SOURCE_REFERENCE_ALLOCATIONS.get(header)
    canonical_column = profile_field if profile_field in facility_properties else None
    internal = header in _INTERNAL_FACILITY_HEADERS
    is_count = header in _FACILITY_SIGNAL_COUNT_HEADERS
    displayed = signal_field is not None or header in {
        "Facility Number", "FAC_NBR", "Facility Name", "NAME", "Facility Type",
        "FAC_TYPE_DESC", "Program Type", "PROGRAM_TYPE", "Facility City",
        "RES_CITY", "Facility State", "RES_STATE", "Facility Zip", "RES_ZIP_CODE",
        "County Name", "COUNTY", "Facility Capacity", "CAPACITY", "Facility Status",
        "STATUS", "Closed Date", "License First Date", "Regional Office",
    }
    if source_reference_allocation is not None:
        displayed = source_reference_allocation[3]
    stored = preload_column is not None or source_reference_allocation is not None
    mapped = (
        canonical_column is not None
        or stored
        or signal_field is not None
        or source_reference_allocation is not None
    )
    query_consumed = displayed or header in {
        "Facility Address",
        "FAC_DO_DESC",
        "RES_STREET_ADDR",
    }
    classification = classify_gap(
        intentionally_internal=internal,
        extracted=True,
        canonical_mapped=mapped,
        stored=stored,
        query_consumed=query_consumed if stored else None,
        displayed=displayed if mapped else None,
    )
    if not internal and not mapped:
        classification = "EXTRACTED_CANONICAL_MAPPING_MISSING"
    if source_reference_allocation is not None:
        classification = "NOT_APPLICABLE"
    mapping_parts = ["original_row_json key preserved"]
    if profile_field is not None:
        mapping_parts.append(f"source-profiling mapping: {profile_field}")
    if preload_column is not None:
        mapping_parts.append(f"typed preload column: {preload_column}")
    if signal_field is not None:
        mapping_parts.append(f"facility signal: {signal_field}")
    if source_reference_allocation is not None:
        mapping_parts.append("DATA_CONTRACT.md issue #447 source-reference allocation")
    display_route = "/ccld/facilities/detail" if displayed else ""
    method = "coverage-qualified count" if is_count else "single labeled facility fact"
    disposition = "retain as internal provenance" if internal else "measure and retain mapping"
    if source_reference_allocation is not None:
        disposition = source_reference_allocation[2]
    if classification not in {"NOT_APPLICABLE", "INTENTIONALLY_INTERNAL"}:
        disposition = "create focused mapping/query remediation"
    data_type = (
        source_reference_allocation[1]
        if source_reference_allocation is not None
        else "integer-or-list"
        if is_count
        else "integer"
        if header in {"Facility Capacity", "CAPACITY"}
        else "source string"
    )
    field_id = _source_field_id(header)
    return ElementSpec(
        data_element_id=stable_data_element_id(
            "facility",
            (
                f"facility_fixture_{relative_path.stem}"
                if is_governed_fixture
                else f"facility_retained_{relative_path.stem}"
            ),
            header,
        ),
        reviewer_facing_name=_reviewer_name(header),
        ownership="facility",
        source_artifact_type=(
            "governed facility CSV fixture header"
            if is_governed_fixture
            else "configured retained facility reference CSV header"
        ),
        source_field_or_extractor_reference=f"CSV header: {header}",
        source_availability_status=(
            "present in governed fixture shape; runtime unmeasured"
            if is_governed_fixture
            else "present in configured retained artifact shape"
        ),
        extraction_status="; ".join(mapping_parts),
        canonical_entity="facility" if canonical_column is not None else None,
        canonical_column=canonical_column,
        data_type=data_type,
        null_meaning="source coverage unavailable or the row did not provide the field",
        blank_meaning="blank source cell; it is not a verified zero",
        zero_meaning=(
            "zero is valid only when parsed from an explicit numeric source value"
            if is_count or header in {"Facility Capacity", "CAPACITY"}
            else "not applicable unless the source field is numeric"
        ),
        query_service_consumer=(
            "facility reference lookup and facility review signals"
            if mapped and source_reference_allocation is None
            else "facility lookup lifecycle context"
            if displayed
            else "none"
        ),
        current_display_route_or_export=display_route,
        recommended_display_location=(
            "operator/support tooling" if internal else "facility hub"
        ),
        recommended_display_method=(
            "keep out of the primary reviewer page" if internal else method
        ),
        traceability_availability=(
            "header identity, original_row_json key, and governed query value with "
            "blank/unavailable distinction"
            if query_consumed
            else "header identity and original_row_json key"
        ),
        validation_coverage=(
            "governed fixture header inventory"
            if is_governed_fixture
            else "configured retained header inventory"
        ),
        gap_classification=classification,
        disposition=disposition,
        priority=(
            "P2"
            if classification in {"NOT_APPLICABLE", "INTENTIONALLY_INTERNAL"}
            else "P1"
        ),
        evidence_reference_location=f"{relative_path.as_posix()}#header/{field_id}",
        source_observation_field=field_id,
        source_observation_sources=_FACILITY_SOURCE_IDS,
        runtime_table=(
            "hosted_facility_reference_records"
            if preload_column or source_reference_allocation is not None
            else None
        ),
        runtime_column=(
            source_reference_allocation[0]
            if source_reference_allocation is not None
            else preload_column
        ),
        reviewer_relevant=displayed if source_reference_allocation is not None else not internal,
        facility_hub_relevant=(
            displayed if source_reference_allocation is not None else not internal
        ),
        complaint_detail_relevant=False,
        dependencies=(
            "facility reference preload and signal semantics"
            if mapped
            else "mapping decision"
        ),
        validation_requirement=(
            "Test blank, unavailable, verified-zero, and populated source cells separately."
        ),
    )


def _raw_only_specs() -> tuple[ElementSpec, ...]:
    specs: list[ElementSpec] = []
    for field, name, ownership, canonical_column, location, method in _RAW_ONLY_FIELDS:
        is_narrative = field == "investigation_findings_narrative"
        canonical_deferred = field in {"facility_address", "facility_city"}
        canonical_entity = "facility" if canonical_column is not None else None
        specs.append(
            ElementSpec(
                data_element_id=stable_data_element_id(
                    ownership,
                    "raw_complaint_report",
                    field,
                ),
                reviewer_facing_name=name,
                ownership=ownership,
                source_artifact_type="retained or governed CCLD complaint report",
                source_field_or_extractor_reference=f"allowlisted raw label pattern: {field}",
                source_availability_status="measured from allowlisted field identity only",
                extraction_status=(
                    "extracted into hosted original values"
                    if is_narrative
                    else "deterministically extracted with field-level audit evidence"
                ),
                canonical_entity=canonical_entity,
                canonical_column=canonical_column,
                data_type="source string" if "capacity" not in field else "integer",
                null_meaning="raw field was absent or extraction was unavailable",
                blank_meaning="blank source label value; not equivalent to source absence",
                zero_meaning=(
                    "zero is valid only when the raw numeric value is explicitly verified"
                    if "capacity" in field else "not applicable"
                ),
                query_service_consumer=(
                    "complaint detail source narrative helper" if is_narrative else "none"
                ),
                current_display_route_or_export=(
                    "/reviewer/records/detail" if is_narrative else ""
                ),
                recommended_display_location=location,
                recommended_display_method=method,
                traceability_availability=(
                    "raw document identity and hash plus field-level source section and text; "
                    "aggregate evidence excludes raw values"
                ),
                validation_coverage=(
                    "governed fixture extraction and aggregate-safe evidence assertions"
                ),
                gap_classification=(
                    "EXTRACTED_CANONICAL_MAPPING_MISSING"
                    if canonical_deferred
                    else "NOT_APPLICABLE"
                ),
                disposition=(
                    "retain current hosted original-values presentation"
                    if is_narrative
                    else "defer canonical allocation to issue 447"
                    if canonical_deferred
                    else "retain deterministic extraction and traceability"
                ),
                priority="P1" if canonical_deferred else "P2",
                evidence_reference_location=(
                    "src/ccld_complaints/connectors/ccld/facility_reports.py#extract"
                ),
                source_observation_field=field,
                source_observation_sources=(
                    _COMPLAINT_SOURCE_IDS
                    if is_narrative
                    else _RAW_FACILITY_SOURCE_IDS
                ),
                runtime_table=None,
                runtime_column=None,
                reviewer_relevant=True,
                facility_hub_relevant=ownership == "facility",
                complaint_detail_relevant=ownership == "complaint",
                dependencies=(
                    "canonical storage allocation in issue 447"
                    if canonical_deferred
                    else "none"
                ),
                validation_requirement=(
                    "Prove extraction, present-blank semantics, traceability, and safe evidence."
                ),
            )
        )
    return tuple(specs)


def _curated_structural_specs() -> tuple[ElementSpec, ...]:
    return (
        ElementSpec(
            data_element_id=stable_data_element_id(
                "facility", "facility_reference", "closed_date_allocation_gap"
            ),
            reviewer_facing_name="Facility closed date canonical allocation",
            ownership="facility",
            source_artifact_type="governed facility CSV",
            source_field_or_extractor_reference="Closed Date / closed_date",
            source_availability_status="provided by the program facility source shape",
            extraction_status="typed PostgreSQL preload and facility signal only",
            canonical_entity=None,
            canonical_column=None,
            data_type="date string",
            null_meaning="source date unavailable; not proof the facility is open",
            blank_meaning="blank source date; not equivalent to open status",
            zero_meaning="not applicable",
            query_service_consumer="facility lookup and facility review signals",
            current_display_route_or_export="/ccld/facilities/detail",
            recommended_display_location="facility hub lifecycle facts",
            recommended_display_method="date with explicit unavailable state",
            traceability_availability="facility reference resource metadata",
            validation_coverage="facility reference preload and signal unit tests",
            gap_classification="NOT_APPLICABLE",
            disposition=(
                "retain as a typed facility-reference lifecycle date; do not infer "
                "open status"
            ),
            priority="P2",
            evidence_reference_location=(
                "src/ccld_complaints/hosted_app/facility_reference_preload.py#closed_date"
            ),
            source_observation_field="closed_date",
            source_observation_sources=_FACILITY_SOURCE_IDS,
            runtime_table="hosted_facility_reference_records",
            runtime_column="closed_date",
            reviewer_relevant=True,
            facility_hub_relevant=True,
            complaint_detail_relevant=False,
            dependencies="none; canonical facility bridge remains deferred",
            validation_requirement="Test blank, invalid, closed, and unavailable dates.",
        ),
        ElementSpec(
            data_element_id=stable_data_element_id(
                "facility", "facility_signal", "blank_to_zero_risk"
            ),
            reviewer_facing_name="Facility signal verified-zero provenance",
            ownership="facility",
            source_artifact_type="program facility summary CSV",
            source_field_or_extractor_reference="_safe_int and _count_list_values",
            source_availability_status="source coverage varies by field and row",
            extraction_status="blank or invalid input is currently coerced to zero",
            canonical_entity=None,
            canonical_column=None,
            data_type="integer aggregate",
            null_meaning="coverage unavailable before signal coercion",
            blank_meaning="blank must remain unavailable, not zero",
            zero_meaning="valid only with an explicit source numeric/list value",
            query_service_consumer="facility review signals",
            current_display_route_or_export="/ccld/facilities/detail",
            recommended_display_location="facility hub signal coverage state",
            recommended_display_method="verified count or explicit coverage-unavailable state",
            traceability_availability="source header identity; row values excluded from audit",
            validation_coverage="facility review signal unit tests",
            gap_classification="UNEXPLAINED_BLANK",
            disposition="preserve source availability before aggregation",
            priority="P0",
            evidence_reference_location=(
                "src/ccld_complaints/hosted_app/facility_review_signals.py#_safe_int"
            ),
            source_observation_field=None,
            source_observation_sources=(),
            runtime_table=None,
            runtime_column=None,
            reviewer_relevant=True,
            facility_hub_relevant=True,
            complaint_detail_relevant=False,
            dependencies="source-aware facility signal parser result",
            validation_requirement="Distinguish blank, invalid, explicit zero, and positive input.",
        ),
    )


def _source_profile_header_map() -> dict[str, str]:
    result: dict[str, str] = {}
    for mapping_value in FACILITY_SOURCE_COLUMN_MAPPINGS:
        app_field = mapping_value.get("app_field")
        source_columns = mapping_value.get("source_columns", ())
        if not isinstance(app_field, str) or not isinstance(source_columns, tuple):
            continue
        for source_column in source_columns:
            if isinstance(source_column, str):
                result[source_column] = app_field
    return result


def _read_header_only(path: Path) -> tuple[str, ...]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
            row = next(csv.reader(csv_file), [])
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise ValueError("Unable to read a configured facility CSV header safely.") from exc
    headers = tuple(value.strip() for value in row if value.strip())
    if len(headers) != len(set(headers)):
        raise ValueError("A configured facility CSV contains duplicate headers.")
    return headers


def _assert_unique_ids(specs: tuple[ElementSpec, ...]) -> None:
    seen: dict[str, ElementSpec] = {}
    for spec in specs:
        existing = seen.get(spec.data_element_id)
        if existing is not None:
            raise ValueError(
                "Stable data-element ID collision between "
                f"{existing.evidence_reference_location!r} and "
                f"{spec.evidence_reference_location!r}."
            )
        seen[spec.data_element_id] = spec


def _default_presentation(ownership: str) -> _Presentation:
    if ownership == "facility":
        return _Presentation("none", "", "facility hub", "single labeled fact")
    if ownership == "complaint":
        return _Presentation("none", "", "complaint detail", "task-focused labeled fact")
    return _Presentation(
        "internal traceability services",
        "",
        "operator/support tooling",
        "internal",
    )


def _schema_data_type(property_schema: Mapping[str, Any]) -> str:
    type_value = property_schema.get("type")
    if isinstance(type_value, str):
        return type_value
    if isinstance(type_value, list):
        return "|".join(str(value) for value in type_value)
    return "unknown"


def _null_meaning(data_type: str, required: bool) -> str:
    if required or "null" not in data_type.split("|"):
        return "null is not permitted by the canonical schema"
    return "source value unavailable or not extracted; the audit records the cause separately"


def _blank_meaning(data_type: str) -> str:
    if "string" in data_type:
        return "empty or whitespace-only string; distinct from null and literal unknown"
    return "not applicable to non-string canonical values"


def _zero_meaning(data_type: str) -> str:
    if "boolean" in data_type:
        return "false is a verified boolean value, not missing coverage"
    if "integer" in data_type or "number" in data_type:
        return "valid only when verified as an explicit or deterministic numeric zero"
    return "not applicable"


def _reviewer_name(value: str) -> str:
    cleaned = re.sub(r"[_-]+", " ", value).strip()
    return cleaned[:1].upper() + cleaned[1:] if cleaned else "Unnamed field"


def _source_field_id(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_") or "unknown"


def _source_artifact_type(entity: str) -> str:
    if entity == "facility":
        return "CCLD complaint report and governed facility reference CSV"
    if entity == "source_document":
        return "retained CCLD source-document metadata"
    if entity == "extraction_audit":
        return "deterministic extraction audit record"
    return "retained or governed CCLD complaint report"


def _source_reference(entity: str, column: str) -> str:
    references: Mapping[tuple[str, str], str] = {
        ("facility", "external_facility_number"): (
            "FACILITY NUMBER / Facility Number / FAC_NBR"
        ),
        ("facility", "facility_name"): "FACILITY NAME / Facility Name / NAME",
        ("facility", "facility_type"): "Facility Type / FAC_TYPE_DESC",
        ("facility", "county"): "County Name / COUNTY",
        ("facility", "status"): "Facility Status / STATUS",
        ("facility", "capacity"): "FACILITY CAPACITY / Facility Capacity / CAPACITY",
        ("facility", "regional_office"): (
            "regional-office report field / Regional Office / FAC_DO_DESC"
        ),
        ("complaint", "complaint_control_number"): "COMPLAINT CONTROL NUMBER",
        ("complaint", "complaint_received_date"): "COMPLAINT RECEIVED",
        ("complaint", "first_investigation_activity_date"): "investigation narrative",
        ("complaint", "visit_date"): "VISIT DATE",
        ("complaint", "report_date"): "Report Date",
        ("complaint", "date_signed"): "Date Signed",
        ("complaint", "finding"): "Finding / INVESTIGATION FINDING(S)",
        ("complaint", "days_received_to_first_activity"): (
            "derived from COMPLAINT RECEIVED and governed investigation activity date"
        ),
        ("allegation", "allegation_text"): "Allegation(s)",
        ("event", "event_text"): "investigation narrative",
        ("event", "event_date"): "investigation narrative date token",
        ("event", "event_type"): "investigation narrative event cue",
    }
    return references.get((entity, column), f"{entity} normalizer: {column}")


def _canonical_observation_field(entity: str, column: str) -> str | None:
    mapping: Mapping[tuple[str, str], str] = {
        ("facility", "external_facility_number"): "facility_number",
        ("facility", "facility_name"): "facility_name",
        ("facility", "capacity"): "facility_capacity",
        ("facility", "regional_office"): "regional_office",
        ("complaint", "complaint_control_number"): "complaint_control_number",
        ("complaint", "complaint_received_date"): "complaint_received_date",
        ("complaint", "first_investigation_activity_date"): "investigation_findings_narrative",
        ("complaint", "visit_date"): "visit_date",
        ("complaint", "report_date"): "report_date",
        ("complaint", "date_signed"): "date_signed",
        ("allegation", "allegation_text"): "allegation_text",
        ("event", "event_text"): "investigation_findings_narrative",
        ("event", "event_date"): "investigation_findings_narrative",
        ("event", "event_type"): "investigation_findings_narrative",
    }
    return mapping.get((entity, column))


def _traceability(entity: str, column: str) -> str:
    if entity == "source_document":
        return "source-document identity; sensitive values remain excluded from audit output"
    if entity == "extraction_audit":
        return "field-level audit record; source_text and extracted_value are never exported"
    if column.endswith("_id"):
        return "canonical relationship identity"
    return "document-level traceability plus field-level audit where emitted"


__all__ = [
    "AGGREGATE_FEATURES",
    "COMPLAINT_REPORT_INVENTORY_FIELDNAMES",
    "COMPLAINT_REPORT_INVENTORY_PATH",
    "COMPLAINT_REPORT_INVENTORY_VERSION",
    "COMPLAINT_REPORT_PRESENTATION_TIERS",
    "COMPLAINT_REPORT_REQUIRED_ACTIONS",
    "COMPLAINT_REPORT_REQUIRED_DOMAINS",
    "COMPLAINT_REPORT_SOURCE_PRESENCE_STATES",
    "COVERAGE_TERMINAL_CLASSIFICATIONS",
    "GAP_CLASSIFICATIONS",
    "QUERY_COVERAGE_GAPS",
    "AggregateFeatureSpec",
    "ComplaintReportFieldSpec",
    "ElementSpec",
    "QueryCoverageGap",
    "classify_gap",
    "discover_element_specs",
    "load_complaint_report_field_inventory",
    "safe_facility_source_header",
    "stable_data_element_id",
]
