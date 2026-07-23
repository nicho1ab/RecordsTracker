# ruff: noqa: E501

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from dataclasses import dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, parse_qsl, urlencode, urlparse

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from ccld_complaints.hosted_app.audit_coverage_plan import (
    AUDIT_COVERAGE_PLAN_API_PATH,
    AuditCoveragePlanContext,
    route_audit_coverage_plan_response,
)
from ccld_complaints.hosted_app.audit_event_routes import (
    AUDIT_EVENTS_API_PREFIX,
    AuditEventsApiContext,
    route_audit_events_api_response,
)
from ccld_complaints.hosted_app.auth import (
    CLOUDFLARE_ACCESS_PROVIDER_CLASS,
    CloudflareAccessAuthError,
    HostedAuthConfigError,
    HostedAuthRuntimeConfig,
    JwksFetcher,
    authenticate_cloudflare_access_request,
    load_hosted_auth_runtime_config,
)
from ccld_complaints.hosted_app.auth_provider_integration_plan import (
    AUTH_PROVIDER_INTEGRATION_PLAN_API_PATH,
    AuthProviderIntegrationPlanContext,
    route_auth_provider_integration_plan_response,
)
from ccld_complaints.hosted_app.ccld_facility_lookup import (
    CCLD_FACILITY_LOOKUP_PATH,
    CCLD_FACILITY_REVIEW_HUB_PATH,
    CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH,
    CCLD_FACILITY_REVIEW_PRIORITY_PATH,
    CCLD_FACILITY_SUGGESTIONS_PATH,
    CcldFacilityLookupResult,
    CcldFacilityReferenceSource,
    CcldFacilityReviewContext,
    facility_lookup_record_from_projection,
    facility_lookup_result_from_projections,
    facility_reference_from_source_derived_records,
    no_reference_facility_source,
    render_ccld_facility_lookup_page,
    route_ccld_facility_lookup_response,
    route_ccld_facility_lookup_response_with_source,
)
from ccld_complaints.hosted_app.ccld_record_request_ui import (
    CCLD_HELP_PATH,
    CCLD_RECORD_REQUEST_PATH,
    CCLD_UI_PREFIX,
    CcldRecordRequestUiContext,
    ccld_record_request_context_for_reviewer_context,
    default_ccld_record_request_ui_context,
    route_ccld_record_request_ui_response,
)
from ccld_complaints.hosted_app.ccld_retrieval_jobs import (
    CcldFixtureRetrievalClient,
    CcldHttpRetrievalClient,
    CcldRetrievalContext,
    load_ccld_retrieval_config,
)
from ccld_complaints.hosted_app.facility_identity_projection import (
    load_authorized_facility_identity_projections,
)
from ccld_complaints.hosted_app.facility_reference_preload import (
    facility_reference_source_from_connection,
    facility_reference_source_summary_from_connection,
    search_facility_reference_records,
)
from ccld_complaints.hosted_app.feedback import (
    FEEDBACK_PATH,
    FeedbackContext,
    GitHubFeedbackConfig,
    GitHubIssueClient,
    GitHubRestIssueClient,
    load_github_feedback_config,
    route_feedback_response,
)
from ccld_complaints.hosted_app.operator_coverage_dashboard import (
    OPERATOR_COVERAGE_EXPORT_PATH,
    OPERATOR_COVERAGE_FACILITY_IDS_PATH,
    OPERATOR_COVERAGE_PREFIX,
    OperatorCoverageDashboardContext,
    default_operator_coverage_context,
    route_operator_coverage_response,
)
from ccld_complaints.hosted_app.persistence import (
    HostedDatabaseConfigError,
    load_hosted_database_config,
)
from ccld_complaints.hosted_app.reset_reload_dry_run import (
    SEEDED_CORPUS_RESET_RELOAD_DRY_RUN_API_PATH,
    SeededCorpusResetReloadDryRunContext,
    route_seeded_corpus_reset_reload_dry_run_response,
)
from ccld_complaints.hosted_app.reset_reload_execution_plan import (
    SEEDED_CORPUS_RESET_RELOAD_EXECUTION_PLAN_API_PATH,
    SeededCorpusResetReloadExecutionPlanContext,
    route_seeded_corpus_reset_reload_execution_plan_response,
)
from ccld_complaints.hosted_app.reset_reload_planning_routes import (
    RESET_RELOAD_PLANNING_METADATA_API_PREFIX,
    ResetReloadPlanningMetadataApiContext,
    route_reset_reload_planning_metadata_api_response,
)
from ccld_complaints.hosted_app.reviewer_created_state_routes import (
    REVIEWER_CREATED_STATE_API_PREFIX,
    ReviewerCreatedStateApiContext,
    route_reviewer_created_state_api_response,
)
from ccld_complaints.hosted_app.reviewer_ui import (
    LOCAL_REVIEWER_UI_SCOPE,
    POSTGRES_REVIEWER_UI_SCOPE,
    REVIEWER_UI_FACILITY_PRIORITIES_PATH,
    REVIEWER_UI_FACILITY_TRENDS_PATH,
    REVIEWER_UI_PREFIX,
    REVIEWER_UI_SUBSTANTIATED_EXPORT_PATH,
    ReviewerUiContext,
    build_facility_review_context,
    complaint_export_attachment_filename,
    default_local_test_reviewer_ui_context,
    local_test_reviewer_actor,
    reviewer_ui_context_for_connection,
    route_reviewer_ui_response,
)
from ccld_complaints.hosted_app.reviewer_workflow_shell import (
    ReviewerWorkflowShellContext,
    route_reviewer_workflow_shell_response,
)
from ccld_complaints.hosted_app.source_derived_routes import (
    SourceDerivedApiContext,
    route_source_derived_api_response,
)
from ccld_complaints.hosted_app.ui_shell import (
    FAVICON_PATH,
    render_document_head,
    render_page_shell,
)

APP_NAME = "CCLD Records Review"
SCAFFOLD_NOTICE = "Local/test scaffold only: not a production reviewer workflow."
SAMPLE_DATA_NOTICE = "Local sample source-derived data only; no live public-source data is loaded."
AUTH_LOGIN_PATH = "/auth/login"
AUTH_LOGOUT_PATH = "/auth/logout"
AUTH_STATUS_PATH = "/auth/status"
PAGE_DATA_MODE_ENV = "CCLD_HOSTED_PAGE_DATA_MODE"
POSTGRES_PAGE_DATA_MODE = "postgres"
FIXTURE_DEMO_PAGE_DATA_MODE = "fixture-demo"
PUBLIC_SOURCE_FACILITY_FIXTURE_DIR = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "public_source_facilities"
)
FAVICON_FILE = Path(__file__).resolve().parent / "static" / "favicon.ico"
SOURCE_COVERAGE_FACILITY_FIXTURE = "chhs_facility_master_tiny.csv"
_DEFAULT_POSTGRES_REVIEWER_UI_CONTEXT: ReviewerUiContext | None = None


@dataclass(frozen=True)
class SampleSourceRecord:
    record_id: str
    jurisdiction: str
    source_family: str
    source_type: str
    facility_name: str
    facility_number: str
    complaint_id: str
    complaint_control_number: str
    finding: str
    source_url: str
    raw_sha256: str
    connector_name: str
    retrieved_at: str
    report_index: str
    extraction_note: str


@dataclass(frozen=True)
class SourceRecordFilters:
    query: str = ""
    jurisdiction: str = ""
    source_family: str = ""


@dataclass(frozen=True)
class TraceabilityFieldSummary:
    label: str
    present_count: int


@dataclass(frozen=True)
class SourceTraceabilitySummary:
    total_records: int
    complete_record_count: int
    fields: tuple[TraceabilityFieldSummary, ...]
    jurisdictions: tuple[str, ...]
    source_families: tuple[str, ...]


@dataclass(frozen=True)
class SampleFacilityRecord:
    record_id: str
    facility_number: str
    facility_name: str
    facility_type: str
    program_type: str
    county: str
    status: str
    capacity: str
    source_family: str
    jurisdiction: str
    source_fixture: str
    profiled_source_shape: str
    source_dataset_reference: str
    source_url: str
    raw_sha256: str
    retrieved_at: str


TRACEABILITY_FIELDS = (
    ("source_url", "Sample source URL"),
    ("raw_sha256", "Raw SHA-256"),
    ("connector_name", "Connector name"),
    ("retrieved_at", "Retrieved at"),
    ("report_index", "Report index"),
    ("extraction_note", "Extraction note"),
    ("jurisdiction", "Jurisdiction"),
    ("source_family", "Source family"),
)


SAMPLE_SOURCE_RECORDS = [
    SampleSourceRecord(
        record_id="sample-complaint-001",
        jurisdiction="California",
        source_family="CCLD complaint reports",
        source_type="HTML portal/detail page",
        facility_name="Synthetic Orchard Child Care",
        facility_number="900000001",
        complaint_id="sample-complaint-001",
        complaint_control_number="SAMPLE-CC-001",
        finding="Unknown",
        source_url="https://example.invalid/sample-ccld-source-document-001",
        raw_sha256="0" * 64,
        connector_name="sample-ccld-fixture",
        retrieved_at="2026-01-01T00:00:00+00:00",
        report_index="sample-1",
        extraction_note="Sample-only value; not extracted from live public-source data.",
    ),
    SampleSourceRecord(
        record_id="sample-complaint-002",
        jurisdiction="California",
        source_family="CCLD complaint reports",
        source_type="HTML portal/detail page",
        facility_name="Synthetic Valley Family Agency",
        facility_number="900000002",
        complaint_id="sample-complaint-002",
        complaint_control_number="SAMPLE-CC-002",
        finding="Unknown",
        source_url="https://example.invalid/sample-ccld-source-document-002",
        raw_sha256="1" * 64,
        connector_name="sample-ccld-fixture",
        retrieved_at="2026-01-02T00:00:00+00:00",
        report_index="sample-2",
        extraction_note="Sample-only value; not extracted from live public-source data.",
    ),
]


def _read_csv_fixture(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fixture_file:
        return [dict(row) for row in csv.DictReader(fixture_file)]


def _load_facility_fixture_manifest() -> dict[str, dict[str, str]]:
    manifest_path = PUBLIC_SOURCE_FACILITY_FIXTURE_DIR / "source_fixture_manifest.csv"
    return {row["fixture_file"]: row for row in _read_csv_fixture(manifest_path)}


def _facility_record_id(fixture_file: str, facility_number: str) -> str:
    fixture_slug = fixture_file.removesuffix(".csv").replace("_", "-")
    return f"{fixture_slug}-{facility_number}"


def _facility_manifest_value(
    manifest_by_file: dict[str, dict[str, str]], fixture_file: str, key: str
) -> str:
    return manifest_by_file[fixture_file][key]


def _facility_from_ccld_program_row(
    row: dict[str, str], manifest_by_file: dict[str, dict[str, str]]
) -> SampleFacilityRecord:
    fixture_file = "ccld_program_facilities_tiny.csv"
    facility_number = row["Facility Number"]
    return SampleFacilityRecord(
        record_id=_facility_record_id(fixture_file, facility_number),
        facility_number=facility_number,
        facility_name=row["Facility Name"],
        facility_type=row["Facility Type"],
        program_type=row["Facility Type"],
        county=row["County Name"],
        status=row["Facility Status"],
        capacity=row["Facility Capacity"],
        source_family=_facility_manifest_value(manifest_by_file, fixture_file, "source_family"),
        jurisdiction=_facility_manifest_value(manifest_by_file, fixture_file, "jurisdiction"),
        source_fixture=fixture_file,
        profiled_source_shape=_facility_manifest_value(
            manifest_by_file, fixture_file, "profiled_source_shape"
        ),
        source_dataset_reference=_facility_manifest_value(
            manifest_by_file, fixture_file, "source_dataset_reference"
        ),
        source_url=_facility_manifest_value(
            manifest_by_file, fixture_file, "source_url_placeholder"
        ),
        raw_sha256=_facility_manifest_value(
            manifest_by_file, fixture_file, "raw_sha256_placeholder"
        ),
        retrieved_at=_facility_manifest_value(
            manifest_by_file, fixture_file, "retrieved_at_placeholder"
        ),
    )


def _facility_from_chhs_master_row(
    row: dict[str, str], manifest_by_file: dict[str, dict[str, str]]
) -> SampleFacilityRecord:
    fixture_file = "chhs_facility_master_tiny.csv"
    facility_number = row["FAC_NBR"]
    return SampleFacilityRecord(
        record_id=_facility_record_id(fixture_file, facility_number),
        facility_number=facility_number,
        facility_name=row["NAME"],
        facility_type=row["FAC_TYPE_DESC"],
        program_type=row["PROGRAM_TYPE"],
        county=row["COUNTY"],
        status=row["STATUS"],
        capacity=row["CAPACITY"],
        source_family=_facility_manifest_value(manifest_by_file, fixture_file, "source_family"),
        jurisdiction=_facility_manifest_value(manifest_by_file, fixture_file, "jurisdiction"),
        source_fixture=fixture_file,
        profiled_source_shape=_facility_manifest_value(
            manifest_by_file, fixture_file, "profiled_source_shape"
        ),
        source_dataset_reference=_facility_manifest_value(
            manifest_by_file, fixture_file, "source_dataset_reference"
        ),
        source_url=_facility_manifest_value(
            manifest_by_file, fixture_file, "source_url_placeholder"
        ),
        raw_sha256=_facility_manifest_value(
            manifest_by_file, fixture_file, "raw_sha256_placeholder"
        ),
        retrieved_at=_facility_manifest_value(
            manifest_by_file, fixture_file, "retrieved_at_placeholder"
        ),
    )


def load_sample_facility_records() -> list[SampleFacilityRecord]:
    manifest_by_file = _load_facility_fixture_manifest()
    ccld_rows = _read_csv_fixture(
        PUBLIC_SOURCE_FACILITY_FIXTURE_DIR / "ccld_program_facilities_tiny.csv"
    )
    chhs_rows = _read_csv_fixture(
        PUBLIC_SOURCE_FACILITY_FIXTURE_DIR / "chhs_facility_master_tiny.csv"
    )
    return [
        *(_facility_from_ccld_program_row(row, manifest_by_file) for row in ccld_rows),
        *(_facility_from_chhs_master_row(row, manifest_by_file) for row in chhs_rows),
    ]


def _first_query_value(query_values: dict[str, list[str]], key: str) -> str:
    values = query_values.get(key, [])
    if not values:
        return ""
    return values[0].strip()


def source_record_filters_from_query(query: str) -> SourceRecordFilters:
    query_values = parse_qs(query, keep_blank_values=True)
    return SourceRecordFilters(
        query=_first_query_value(query_values, "q"),
        jurisdiction=_first_query_value(query_values, "jurisdiction"),
        source_family=_first_query_value(query_values, "source_family"),
    )


def _normalized_filter_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _record_search_text(record: SampleSourceRecord) -> str:
    return _normalized_filter_text(
        " ".join(
            [
                record.record_id,
                record.jurisdiction,
                record.source_family,
                record.source_type,
                record.facility_name,
                record.facility_number,
                record.complaint_id,
                record.complaint_control_number,
                record.finding,
                record.connector_name,
                record.report_index,
            ]
        )
    )


def filter_sample_source_records(filters: SourceRecordFilters) -> list[SampleSourceRecord]:
    query = _normalized_filter_text(filters.query)
    return [
        record
        for record in SAMPLE_SOURCE_RECORDS
        if (not query or query in _record_search_text(record))
        and (not filters.jurisdiction or record.jurisdiction == filters.jurisdiction)
        and (not filters.source_family or record.source_family == filters.source_family)
    ]


def _has_traceability_value(record: SampleSourceRecord, field_name: str) -> bool:
    return bool(str(getattr(record, field_name)).strip())


def _has_complete_traceability(record: SampleSourceRecord) -> bool:
    return all(
        _has_traceability_value(record, field_name) for field_name, _label in TRACEABILITY_FIELDS
    )


def build_source_traceability_summary(
    records: list[SampleSourceRecord],
) -> SourceTraceabilitySummary:
    return SourceTraceabilitySummary(
        total_records=len(records),
        complete_record_count=sum(1 for record in records if _has_complete_traceability(record)),
        fields=tuple(
            TraceabilityFieldSummary(
                label=label,
                present_count=sum(
                    1 for record in records if _has_traceability_value(record, field_name)
                ),
            )
            for field_name, label in TRACEABILITY_FIELDS
        ),
        jurisdictions=tuple(sorted({record.jurisdiction for record in records})),
        source_families=tuple(sorted({record.source_family for record in records})),
    )


def _unique_record_values(field_name: str) -> list[str]:
    return sorted({str(getattr(record, field_name)) for record in SAMPLE_SOURCE_RECORDS})


def format_host(host: object) -> str:
    if isinstance(host, bytes):
        return host.decode("ascii")
    return str(host)


def _check_source_data_loaded() -> bool:
    """Return True if at least one row exists in hosted_source_derived_records."""
    try:
        config = load_hosted_database_config()
        if config.database_url is None:
            return False
        engine = create_engine(config.database_url)
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT COUNT(*) FROM hosted_source_derived_records")
            )
            count = result.scalar()
            return (count or 0) > 0
    except Exception:  # noqa: BLE001
        return False


def health_response() -> dict[str, object]:
    payload: dict[str, object] = {
        "status": "ok",
        "service": "hosted-tester-mvp-scaffold",
        "scaffold_only": True,
        "local_test_reviewer_ui_shell": True,
        "review_workflows_implemented": False,
        "authentication_implemented": False,
        "source_data_loaded": _check_source_data_loaded(),
    }
    fixture_mode = os.environ.get("CCLD_OPERATOR_COVERAGE_FIXTURE_MODE", "").strip()
    fixture_commit = os.environ.get("CCLD_OPERATOR_COVERAGE_COMMIT_SHA", "").strip()
    fixture_branch = os.environ.get("CCLD_OPERATOR_COVERAGE_BRANCH", "").strip()
    if fixture_mode:
        payload["operator_coverage_fixture_mode"] = fixture_mode
    if fixture_commit:
        payload["operator_coverage_commit_sha"] = fixture_commit
    if fixture_branch:
        payload["operator_coverage_branch"] = fixture_branch
    return payload


def get_sample_source_record(record_id: str) -> SampleSourceRecord | None:
    for record in SAMPLE_SOURCE_RECORDS:
        if record.record_id == record_id:
            return record
    return None


def get_sample_facility_record(record_id: str) -> SampleFacilityRecord | None:
    for record in load_sample_facility_records():
        if record.record_id == record_id:
            return record
    return None


def related_sample_source_records_for_facility(
    facility: SampleFacilityRecord,
) -> list[SampleSourceRecord]:
    if facility.source_fixture != SOURCE_COVERAGE_FACILITY_FIXTURE:
        return []
    return [
        record
        for record in SAMPLE_SOURCE_RECORDS
        if record.facility_number == facility.facility_number
        and record.jurisdiction == facility.jurisdiction
    ]


def related_sample_facility_records_for_source_record(
    source_record: SampleSourceRecord,
) -> list[SampleFacilityRecord]:
    return [
        facility
        for facility in load_sample_facility_records()
        if facility.source_fixture == SOURCE_COVERAGE_FACILITY_FIXTURE
        and facility.facility_number == source_record.facility_number
        and facility.jurisdiction == source_record.jurisdiction
    ]


def _render_filter_option(value: str, selected_value: str) -> str:
    selected = ' selected="selected"' if value == selected_value else ""
    return f'<option value="{html.escape(value)}"{selected}>{html.escape(value)}</option>'


def render_source_record_filters(filters: SourceRecordFilters) -> str:
    jurisdiction_options = "\n".join(
        _render_filter_option(value, filters.jurisdiction)
        for value in _unique_record_values("jurisdiction")
    )
    source_family_options = "\n".join(
        _render_filter_option(value, filters.source_family)
        for value in _unique_record_values("source_family")
    )
    return f"""<section aria-labelledby="filter-heading">
      <h2 id="filter-heading">Sample filtering/search</h2>
      <p>Filters apply only to the local fixture/sample records shown on this
      page. They do not query live public-source data or a database.</p>
      <form action="/source-records" method="get">
        <fieldset>
          <legend>Filter sample source records</legend>
          <p>
            <label for="q">Search sample records</label>
            <input id="q" name="q" type="search" value="{html.escape(filters.query)}">
          </p>
          <p>
            <label for="jurisdiction">Jurisdiction</label>
            <select id="jurisdiction" name="jurisdiction">
              <option value="">All jurisdictions</option>
{jurisdiction_options}
            </select>
          </p>
          <p>
            <label for="source_family">Source family</label>
            <select id="source_family" name="source_family">
              <option value="">All source families</option>
{source_family_options}
            </select>
          </p>
          <p>
            <button type="submit">Apply filters</button>
            <a href="/source-records">Clear filters</a>
          </p>
        </fieldset>
      </form>
    </section>"""


def render_scope_notice() -> str:
    return """<section aria-labelledby="scope-heading">
      <h2 id="scope-heading">Local view-shell scope</h2>
      <p>Fixture/sample data only. No live public-source data is loaded.</p>
      <p>No reviewer workflow is active, no authentication is implemented, and
      no reviewer-created state is persisted.</p>
      <p>Source-derived sample records and future reviewer-created state remain
      separate. This shell does not create queues, annotations, corrections,
      exports, feedback, audit history, reset/reload behavior, or imports.</p>
    </section>"""


def render_facility_fixture_scope_notice() -> str:
    return """<section aria-labelledby="facility-scope-heading">
      <h2 id="facility-scope-heading">Facility fixture scope</h2>
      <p>Fixture/sample data only. No live public-source data is loaded.</p>
      <p>This read-only sample view uses only the committed tiny public-source
      facility fixtures. It does not read ignored raw CSVs, generated profiling
      outputs, SQLite, a hosted database, or an import/sync process.</p>
      <p>No reviewer workflow is active, no authentication is implemented, and
      no reviewer-created state is persisted.</p>
      <p>Source-derived sample records and future reviewer-created state remain
      separate. These rows are not official facility lists, complete statewide
      coverage, source completeness proof, or legal or facility-wide
      conclusions.</p>
    </section>"""


def _format_summary_values(values: tuple[str, ...]) -> str:
    if not values:
        return "None in the current fixture/sample result set"
    return ", ".join(values)


def render_source_traceability_summary(records: list[SampleSourceRecord]) -> str:
    summary = build_source_traceability_summary(records)
    field_rows = "\n".join(
        f"""        <tr>
          <th scope="row">{html.escape(field.label)}</th>
          <td>{field.present_count} of {summary.total_records}</td>
        </tr>"""
        for field in summary.fields
    )
    return f"""<section aria-labelledby="traceability-summary-heading">
      <h2 id="traceability-summary-heading">Sample source traceability summary</h2>
      <p>This panel summarizes visible traceability-style metadata for the
      current fixture/sample result set only. It does not verify live
      public-source completeness and does not read from a database.</p>
      <p>{summary.complete_record_count} of {summary.total_records} fixture/sample records
      have all tracked sample traceability fields visible.</p>
      <dl>
        <dt>Jurisdictions represented</dt>
        <dd>{html.escape(_format_summary_values(summary.jurisdictions))}</dd>
        <dt>Source families represented</dt>
        <dd>{html.escape(_format_summary_values(summary.source_families))}</dd>
      </dl>
      <table>
        <caption>Visible sample traceability fields in the current result set</caption>
        <thead>
          <tr>
            <th scope="col">Traceability-style field</th>
            <th scope="col">Fixture/sample records with visible value</th>
          </tr>
        </thead>
        <tbody>
{field_rows}
        </tbody>
      </table>
    </section>"""


def render_source_traceability_detail(record: SampleSourceRecord) -> str:
    visible_field_labels = ", ".join(
        label
        for field_name, label in TRACEABILITY_FIELDS
        if _has_traceability_value(record, field_name)
    )
    return f"""<section aria-labelledby="traceability-detail-heading">
      <h2 id="traceability-detail-heading">Sample source traceability block</h2>
      <p>This fixture/sample record has visible sample traceability metadata for:
      {html.escape(visible_field_labels)}.</p>
      <p>These values are sample-only indicators for the local scaffold. They do
      not verify a live public-source record, source completeness, reviewer
      state, or import status.</p>
    </section>"""


def render_facility_source_coverage_panel(record: SampleFacilityRecord) -> str:
    related_source_records = related_sample_source_records_for_facility(record)
    related_status = (
        "sample source-record context available"
        if related_source_records
        else "not represented in this fixture/sample mapping"
    )
    related_items = "\n".join(
        f"""        <li><a href="/source-records/{html.escape(source_record.record_id)}">
          {html.escape(source_record.complaint_control_number)} for
          {html.escape(source_record.facility_name)}
        </a></li>"""
        for source_record in related_source_records
    )
    if not related_items:
        related_items = """        <li>No related fixture/sample source-record context is
          represented in this scaffold for this facility number.</li>"""
    return f"""<section aria-labelledby="source-coverage-heading">
      <h2 id="source-coverage-heading">Sample source coverage</h2>
      <p>This read-only panel connects the selected facility fixture row to
      fixture/sample source-record context when a local sample relationship is
      available. It is local-only, fixture-backed, sample-only, and not live
      public-source coverage.</p>
      <p>Use the sample indicators to inspect fixture relationships and open the
      related sample source-record pages when available.</p>
      <table>
        <caption>Fixture source coverage indicators for this sample facility</caption>
        <thead>
          <tr>
            <th scope="col">Coverage indicator</th>
            <th scope="col">Fixture/sample status</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <th scope="row">Facility fixture metadata</th>
            <td>fixture metadata available</td>
          </tr>
          <tr>
            <th scope="row">Related sample source-record context</th>
            <td>{html.escape(related_status)}</td>
          </tr>
          <tr>
            <th scope="row">Live public-source coverage</th>
            <td>unknown/not implemented; not live data</td>
          </tr>
          <tr>
            <th scope="row">Database or import coverage</th>
            <td>not implemented; not imported data and not database-backed</td>
          </tr>
          <tr>
            <th scope="row">Source completeness</th>
            <td>not assessed; no completeness conclusion</td>
          </tr>
        </tbody>
      </table>
      <dl>
        <dt>Source family</dt>
        <dd>{html.escape(record.source_family)}</dd>
        <dt>Jurisdiction</dt>
        <dd>{html.escape(record.jurisdiction)}</dd>
        <dt>Source fixture</dt>
        <dd>{html.escape(record.source_fixture)}</dd>
        <dt>Profiled source shape</dt>
        <dd>{html.escape(record.profiled_source_shape)}</dd>
        <dt>Source dataset reference</dt>
        <dd>{html.escape(record.source_dataset_reference)}</dd>
        <dt>Source URL placeholder</dt>
        <dd>{html.escape(record.source_url)}</dd>
        <dt>Raw SHA-256 placeholder</dt>
        <dd>{html.escape(record.raw_sha256)}</dd>
        <dt>Retrieved at placeholder</dt>
        <dd>{html.escape(record.retrieved_at)}</dd>
      </dl>
      <section aria-labelledby="related-source-records-heading">
        <h3 id="related-source-records-heading">Related fixture/sample source-record context</h3>
        <p>Related links use fixture/sample facility number and jurisdiction
        only. They do not join live sources, imports, databases, or reviewer
        workflow state.</p>
        <ul>
{related_items}
        </ul>
      </section>
    </section>"""


def render_related_facility_context(record: SampleSourceRecord) -> str:
    related_facilities = related_sample_facility_records_for_source_record(record)
    if not related_facilities:
        return """<section aria-labelledby="related-facility-heading">
      <h2 id="related-facility-heading">Related sample facility context</h2>
      <p>No related fixture/sample facility context is represented in this local
      scaffold for this source record. This is an unknown/not implemented sample
      state, not a public-source completeness conclusion.</p>
    </section>"""
    related_items = "\n".join(
        f"""        <li><a href="/facilities/{html.escape(facility.record_id)}">
          {html.escape(facility.facility_name)} from {html.escape(facility.source_fixture)}
        </a></li>"""
        for facility in related_facilities
    )
    return f"""<section aria-labelledby="related-facility-heading">
      <h2 id="related-facility-heading">Related sample facility context</h2>
      <p>This read-only block links fixture/sample source-record context back to
      committed tiny facility fixture rows by sample facility number and
      jurisdiction. It is not imported data, not database-backed, not live
      public-source coverage, and not reviewer-created state.</p>
      <ul>
{related_items}
      </ul>
    </section>"""


def render_app_shell(
    reference_source: CcldFacilityReferenceSource | None = None,
) -> str:
    return render_ccld_facility_lookup_page(
        reference_source=reference_source,
        active_path="/",
    )


def render_source_record_list(filters: SourceRecordFilters | None = None) -> str:
    active_filters = filters or SourceRecordFilters()
    filtered_records = filter_sample_source_records(active_filters)
    rows = "\n".join(
        f"""        <tr>
          <td><a href="/source-records/{html.escape(record.record_id)}">
            {html.escape(record.complaint_control_number)}
          </a></td>
          <td>{html.escape(record.jurisdiction)}</td>
          <td>{html.escape(record.source_family)}</td>
          <td>{html.escape(record.source_type)}</td>
          <td>{html.escape(record.facility_name)}</td>
          <td>{html.escape(record.facility_number)}</td>
          <td>{html.escape(record.finding)}</td>
          <td>{html.escape(record.raw_sha256)}</td>
        </tr>"""
        for record in filtered_records
    )
    if not rows:
        rows = """        <tr>
          <td colspan="8">No fixture/sample records match the current filters.</td>
        </tr>"""
    filter_count_text = (
        f"Showing {len(filtered_records)} of {len(SAMPLE_SOURCE_RECORDS)} fixture/sample records."
    )
    return f"""<!doctype html>
<html lang="en">
{render_document_head(title=f"Sample source-derived records - {APP_NAME}")}
<body>
  <header>
    <p>{html.escape(SAMPLE_DATA_NOTICE)}</p>
    <h1>Sample source-derived records</h1>
  </header>
  <nav aria-label="Local scaffold navigation">
    <ul>
      <li><a href="/">Home</a></li>
      <li><a href="/health">Health check</a></li>
    </ul>
  </nav>
  <main>
    {render_scope_notice()}
    {render_source_record_filters(active_filters)}
    {render_source_traceability_summary(filtered_records)}
    <section aria-labelledby="records-heading">
      <h2 id="records-heading">Fixture/sample source record list</h2>
      <p>These rows are sample-only placeholders for a future read-only hosted
      source-derived view. They are not imported records and are not official
      public-source facts.</p>
      <p>{html.escape(filter_count_text)}</p>
      <table>
        <caption>Local sample source-derived complaint records</caption>
        <thead>
          <tr>
            <th scope="col">Complaint control number</th>
            <th scope="col">Jurisdiction</th>
            <th scope="col">Source family</th>
            <th scope="col">Source type</th>
            <th scope="col">Facility name</th>
            <th scope="col">Facility number</th>
            <th scope="col">Finding</th>
            <th scope="col">Raw SHA-256</th>
          </tr>
        </thead>
        <tbody>
{rows}
        </tbody>
      </table>
    </section>
  </main>
</body>
</html>
"""


def render_source_record_detail(record: SampleSourceRecord) -> str:
    return f"""<!doctype html>
<html lang="en">
{render_document_head(title=f"{record.complaint_control_number} - {APP_NAME}")}
<body>
  <header>
    <p>{html.escape(SAMPLE_DATA_NOTICE)}</p>
    <h1>{html.escape(record.complaint_control_number)}</h1>
  </header>
  <nav aria-label="Local scaffold navigation">
    <ul>
      <li><a href="/">Home</a></li>
      <li><a href="/source-records">Sample source-derived records</a></li>
      <li><a href="/health">Health check</a></li>
    </ul>
  </nav>
  <main>
    {render_scope_notice()}
    {render_source_traceability_detail(record)}
    {render_related_facility_context(record)}
    <section aria-labelledby="detail-heading">
      <h2 id="detail-heading">Read-only sample source-derived detail</h2>
      <dl>
        <dt>Facility name</dt>
        <dd>{html.escape(record.facility_name)}</dd>
        <dt>Jurisdiction</dt>
        <dd>{html.escape(record.jurisdiction)}</dd>
        <dt>Source family</dt>
        <dd>{html.escape(record.source_family)}</dd>
        <dt>Source type</dt>
        <dd>{html.escape(record.source_type)}</dd>
        <dt>Facility number</dt>
        <dd>{html.escape(record.facility_number)}</dd>
        <dt>Complaint ID</dt>
        <dd>{html.escape(record.complaint_id)}</dd>
        <dt>Finding</dt>
        <dd>{html.escape(record.finding)}</dd>
        <dt>Sample source URL</dt>
        <dd>{html.escape(record.source_url)}</dd>
        <dt>Raw SHA-256</dt>
        <dd>{html.escape(record.raw_sha256)}</dd>
        <dt>Connector name</dt>
        <dd>{html.escape(record.connector_name)}</dd>
        <dt>Retrieved at</dt>
        <dd>{html.escape(record.retrieved_at)}</dd>
        <dt>Report index</dt>
        <dd>{html.escape(record.report_index)}</dd>
        <dt>Extraction note</dt>
        <dd>{html.escape(record.extraction_note)}</dd>
      </dl>
    </section>
  </main>
</body>
</html>
"""


def render_facility_list() -> str:
    records = load_sample_facility_records()
    rows = "\n".join(
        f"""        <tr>
          <td><a href="/facilities/{html.escape(record.record_id)}">
            {html.escape(record.facility_number)}
          </a></td>
          <td>{html.escape(record.facility_name)}</td>
          <td>{html.escape(record.facility_type)}</td>
          <td>{html.escape(record.program_type)}</td>
          <td>{html.escape(record.county)}</td>
          <td>{html.escape(record.status)}</td>
          <td>{html.escape(record.capacity)}</td>
          <td>{html.escape(record.source_family)}</td>
          <td>{html.escape(record.source_fixture)}</td>
        </tr>"""
        for record in records
    )
    return f"""<!doctype html>
<html lang="en">
{render_document_head(title=f"Sample facility master records - {APP_NAME}")}
<body>
  <header>
    <p>{html.escape(SAMPLE_DATA_NOTICE)}</p>
    <h1>Sample facility master records</h1>
  </header>
  <nav aria-label="Local scaffold navigation">
    <ul>
      <li><a href="/">Home</a></li>
      <li><a href="/source-records">Sample source-derived records</a></li>
      <li><a href="/health">Health check</a></li>
    </ul>
  </nav>
  <main>
    {render_facility_fixture_scope_notice()}
    <section aria-labelledby="facilities-heading">
      <h2 id="facilities-heading">Read-only facility master sample view</h2>
      <p>Showing {len(records)} fixture/sample facility rows from committed tiny
      public-source facility fixtures. These rows exercise facility-list display
      and manifest-backed traceability labels only.</p>
      <table>
        <caption>Committed tiny public-source facility fixture rows</caption>
        <thead>
          <tr>
            <th scope="col">Facility number</th>
            <th scope="col">Facility name</th>
            <th scope="col">Facility type</th>
            <th scope="col">Program type</th>
            <th scope="col">County</th>
            <th scope="col">Status</th>
            <th scope="col">Capacity</th>
            <th scope="col">Source family</th>
            <th scope="col">Source fixture</th>
          </tr>
        </thead>
        <tbody>
{rows}
        </tbody>
      </table>
    </section>
  </main>
</body>
</html>
"""


def render_facility_detail(record: SampleFacilityRecord) -> str:
    return f"""<!doctype html>
<html lang="en">
{render_document_head(title=f"{record.facility_number} - {APP_NAME}")}
<body>
  <header>
    <p>{html.escape(SAMPLE_DATA_NOTICE)}</p>
    <h1>{html.escape(record.facility_number)}</h1>
  </header>
  <nav aria-label="Local scaffold navigation">
    <ul>
      <li><a href="/">Home</a></li>
      <li><a href="/facilities">Sample facility master records</a></li>
      <li><a href="/source-records">Sample source-derived records</a></li>
      <li><a href="/health">Health check</a></li>
    </ul>
  </nav>
  <main>
    {render_facility_fixture_scope_notice()}
    {render_facility_source_coverage_panel(record)}
    <section aria-labelledby="facility-detail-heading">
      <h2 id="facility-detail-heading">Read-only facility fixture detail</h2>
      <dl>
        <dt>Facility name</dt>
        <dd>{html.escape(record.facility_name)}</dd>
        <dt>Facility number</dt>
        <dd>{html.escape(record.facility_number)}</dd>
        <dt>Facility type</dt>
        <dd>{html.escape(record.facility_type)}</dd>
        <dt>Program type</dt>
        <dd>{html.escape(record.program_type)}</dd>
        <dt>County</dt>
        <dd>{html.escape(record.county)}</dd>
        <dt>Status</dt>
        <dd>{html.escape(record.status)}</dd>
        <dt>Capacity</dt>
        <dd>{html.escape(record.capacity)}</dd>
        <dt>Source family</dt>
        <dd>{html.escape(record.source_family)}</dd>
        <dt>Jurisdiction</dt>
        <dd>{html.escape(record.jurisdiction)}</dd>
        <dt>Source fixture</dt>
        <dd>{html.escape(record.source_fixture)}</dd>
        <dt>Profiled source shape</dt>
        <dd>{html.escape(record.profiled_source_shape)}</dd>
        <dt>Source dataset reference</dt>
        <dd>{html.escape(record.source_dataset_reference)}</dd>
        <dt>Source URL placeholder</dt>
        <dd>{html.escape(record.source_url)}</dd>
        <dt>Raw SHA-256 placeholder</dt>
        <dd>{html.escape(record.raw_sha256)}</dd>
        <dt>Retrieved at placeholder</dt>
        <dd>{html.escape(record.retrieved_at)}</dd>
      </dl>
    </section>
  </main>
</body>
</html>
"""


def route_response(
    path: str,
    *,
    method: str = "GET",
    request_body: bytes | None = None,
    request_headers: dict[str, str] | None = None,
    audit_coverage_plan_context: AuditCoveragePlanContext | None = None,
    auth_provider_integration_plan_context: (
        AuthProviderIntegrationPlanContext | None
    ) = None,
    source_derived_api_context: SourceDerivedApiContext | None = None,
    audit_events_api_context: AuditEventsApiContext | None = None,
    reviewer_workflow_shell_context: ReviewerWorkflowShellContext | None = None,
    reviewer_created_state_api_context: ReviewerCreatedStateApiContext | None = None,
    reset_reload_dry_run_context: SeededCorpusResetReloadDryRunContext | None = None,
    reset_reload_execution_plan_context: (
        SeededCorpusResetReloadExecutionPlanContext | None
    ) = None,
    reset_reload_planning_metadata_api_context: (
        ResetReloadPlanningMetadataApiContext | None
    ) = None,
    auth_runtime_config: HostedAuthRuntimeConfig | None = None,
    page_data_mode: str | None = None,
    feedback_context: FeedbackContext | None = None,
    github_feedback_config: GitHubFeedbackConfig | None = None,
    github_feedback_client: GitHubIssueClient | None = None,
    cloudflare_jwks_fetcher: JwksFetcher | None = None,
    cloudflare_auth_now: datetime | None = None,
    reviewer_ui_context: ReviewerUiContext | None = None,
    ccld_record_request_ui_context: CcldRecordRequestUiContext | None = None,
    operator_coverage_context: OperatorCoverageDashboardContext | None = None,
) -> tuple[int, str, bytes]:
    parsed_url = urlparse(path)
    parsed_path = parsed_url.path
    if method == "GET":
        redirect_location = _legacy_compare_facilities_redirect_location(path)
        if redirect_location is not None:
            return _redirect_response(redirect_location)
    if parsed_path == FAVICON_PATH:
        if not FAVICON_FILE.is_file():
            return 404, "text/plain; charset=utf-8", b"Not found"
        return 200, "image/x-icon", FAVICON_FILE.read_bytes()
    active_auth_config = _active_auth_runtime_config(auth_runtime_config)
    active_page_data_mode = _active_page_data_mode(page_data_mode)
    if parsed_path == OPERATOR_COVERAGE_PREFIX or parsed_path.startswith(
        f"{OPERATOR_COVERAGE_PREFIX}/"
    ):
        active_operator_coverage_context = operator_coverage_context
        if active_operator_coverage_context is None:
            try:
                active_operator_coverage_context = default_operator_coverage_context(
                    active_auth_config,
                    request_headers=request_headers or {},
                    cloudflare_jwks_fetcher=cloudflare_jwks_fetcher,
                    cloudflare_auth_now=cloudflare_auth_now,
                )
            except CloudflareAccessAuthError as error:
                return _cloudflare_access_auth_blocked_response(error)
        return route_operator_coverage_response(
            path,
            active_operator_coverage_context,
            method=method,
        )
    if parsed_path in {AUTH_LOGIN_PATH, AUTH_LOGOUT_PATH}:
        return _auth_placeholder_response(parsed_path, active_auth_config)
    if parsed_path == AUTH_STATUS_PATH:
        return _auth_status_response(active_auth_config)
    if parsed_path == FEEDBACK_PATH:
        try:
            active_feedback_context = feedback_context or _default_feedback_context(
                active_auth_config,
                request_headers=request_headers or {},
                method=method,
                cloudflare_jwks_fetcher=cloudflare_jwks_fetcher,
                cloudflare_auth_now=cloudflare_auth_now,
                github_feedback_config=github_feedback_config,
                github_feedback_client=github_feedback_client,
            )
        except CloudflareAccessAuthError as error:
            return _cloudflare_access_auth_blocked_response(error)
        return route_feedback_response(
            path,
            active_feedback_context,
            method=method,
            request_body=request_body,
        )
    if parsed_path == "/help":
        path = CCLD_HELP_PATH
        parsed_path = CCLD_HELP_PATH
    if parsed_path == f"{CCLD_UI_PREFIX}/":
        path = CCLD_UI_PREFIX
        parsed_path = CCLD_UI_PREFIX
    if parsed_path == CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH:
        explicit_intelligence_context = reviewer_ui_context
        if (
            explicit_intelligence_context is None
            and ccld_record_request_ui_context is not None
        ):
            explicit_intelligence_context = (
                ccld_record_request_ui_context.reviewer_ui_context
            )
        active_reviewer_ui_context = _default_reviewer_context_for_mode(
            active_auth_config,
            active_page_data_mode,
            explicit_intelligence_context,
        )
        return route_reviewer_ui_response(path, active_reviewer_ui_context)
    if parsed_path in {
        CCLD_FACILITY_LOOKUP_PATH,
        CCLD_FACILITY_SUGGESTIONS_PATH,
        CCLD_FACILITY_REVIEW_HUB_PATH,
        CCLD_FACILITY_REVIEW_PRIORITY_PATH,
    }:
        if active_page_data_mode == FIXTURE_DEMO_PAGE_DATA_MODE:
            if parsed_path == CCLD_FACILITY_LOOKUP_PATH:
                return route_ccld_facility_lookup_response(path)
            if parsed_path == CCLD_FACILITY_SUGGESTIONS_PATH:
                return route_ccld_facility_lookup_response(path)
            active_ccld_context = _default_ccld_context_for_mode(
                active_auth_config,
                active_page_data_mode,
                ccld_record_request_ui_context,
            )
            facility_number = _first_query_value(
                parse_qs(parsed_url.query, keep_blank_values=True),
                "facility_number",
            )
            return route_ccld_facility_lookup_response_with_source(
                path,
                None,
                _facility_review_context_from_context(
                    active_ccld_context,
                    facility_number,
                    parse_qs(parsed_url.query, keep_blank_values=True),
                ),
            )
        active_ccld_context = _default_ccld_context_for_mode(
            active_auth_config,
            active_page_data_mode,
            ccld_record_request_ui_context,
        )
        if active_ccld_context is None:
            return _postgres_setup_required_response("Facility search setup required")
        lookup_result = None
        if parsed_path in {
            CCLD_FACILITY_LOOKUP_PATH,
            CCLD_FACILITY_SUGGESTIONS_PATH,
        }:
            query = _first_query_value(
                parse_qs(parsed_url.query, keep_blank_values=True),
                "q",
            )
            if parsed_path == CCLD_FACILITY_SUGGESTIONS_PATH:
                try:
                    source_context = active_ccld_context.reviewer_ui_context.workflow_shell_context.source_derived_api_context
                    lookup_result = search_facility_reference_records(
                        source_context.connection,
                        query,
                    )
                    facility_reference = (
                        lookup_result.reference_source
                        or _facility_reference_summary_from_context(active_ccld_context)
                    )
                except SQLAlchemyError:
                    lookup_result = None
                    facility_reference = _facility_reference_summary_from_context(
                        active_ccld_context
                    )
            else:
                facility_reference = _facility_reference_summary_from_context(
                    active_ccld_context
                )
                if facility_reference.source_kind in {
                    "postgres_facility_reference",
                    "postgres_transparencyapi_reference",
                }:
                    try:
                        source_context = active_ccld_context.reviewer_ui_context.workflow_shell_context.source_derived_api_context
                        lookup_result = search_facility_reference_records(
                            source_context.connection,
                            query,
                        )
                        lookup_result = _projected_lookup_result(
                            active_ccld_context,
                            lookup_result,
                        )
                    except SQLAlchemyError:
                        lookup_result = None
        else:
            facility_reference = _facility_reference_from_context(active_ccld_context)
        facility_number = _first_query_value(
            parse_qs(parsed_url.query, keep_blank_values=True),
            "facility_number",
        )
        if parsed_path == CCLD_FACILITY_REVIEW_HUB_PATH and facility_number.isdigit():
            try:
                facility_reference = _projected_facility_reference_for_ids(
                    active_ccld_context,
                    facility_reference,
                    (facility_number,),
                )
            except SQLAlchemyError:
                return _postgres_setup_required_response(
                    "Facility identity setup required"
                )
        routed_path = path
        if (
            parsed_path == CCLD_FACILITY_REVIEW_HUB_PATH
            and facility_number
            and not facility_reference.records
        ):
            routed_path = CCLD_FACILITY_REVIEW_HUB_PATH
            facility_number = ""
        return route_ccld_facility_lookup_response_with_source(
            routed_path,
            facility_reference,
            _facility_review_context_from_context(
                active_ccld_context,
                facility_number,
                parse_qs(parsed_url.query, keep_blank_values=True),
            ),
            lookup_result=lookup_result,
        )
    if parsed_path.startswith(CCLD_UI_PREFIX):
        active_ccld_context = _default_ccld_context_for_mode(
            active_auth_config,
            active_page_data_mode,
            ccld_record_request_ui_context,
        )
        if active_ccld_context is None and parsed_path != CCLD_HELP_PATH:
            if active_auth_config.local_dev_actor_allowed:
                return _postgres_setup_required_response("CCLD request setup required")
            return _auth_required_response(
                "CCLD workflow access requires sign-in",
                "CCLD request, feedback, retrieval, and import actions require "
                "an authenticated tester or operator in this runtime mode.",
            )
        # In live/postgres mode, pass the source-derived facility reference to the request
        # page so it never falls back to the tiny fixture with synthetic facility data.
        request_facility_reference = None
        if (
            method == "GET"
            and active_page_data_mode != FIXTURE_DEMO_PAGE_DATA_MODE
            and active_ccld_context is not None
            and parsed_path in {CCLD_UI_PREFIX, CCLD_RECORD_REQUEST_PATH}
        ):
            request_facility_reference = _facility_reference_summary_from_context(
                active_ccld_context
            )
            selected_facility_number = _first_query_value(
                parse_qs(parsed_url.query, keep_blank_values=True),
                "facility_number",
            )
            if selected_facility_number.isdigit():
                try:
                    request_facility_reference = _projected_facility_reference_for_ids(
                        active_ccld_context,
                        request_facility_reference,
                        (selected_facility_number,),
                    )
                except SQLAlchemyError:
                    return _postgres_setup_required_response(
                        "Facility identity setup required"
                    )
        return route_ccld_record_request_ui_response(
            path,
            active_ccld_context,
            method=method,
            request_body=request_body,
            facility_reference=request_facility_reference,
        )
    if parsed_path.startswith(REVIEWER_UI_PREFIX):
        active_reviewer_ui_context = _default_reviewer_context_for_mode(
            active_auth_config,
            active_page_data_mode,
            reviewer_ui_context,
        )
        if active_reviewer_ui_context is None:
            if active_auth_config.local_dev_actor_allowed:
                return _postgres_setup_required_response("Reviewer setup required")
            return _auth_required_response(
                "Reviewer access requires sign-in",
                "Reviewer-created notes/status, workflow actions, feedback, "
                "retrieval jobs, and operational actions are not available anonymously.",
            )
        return route_reviewer_ui_response(
            path,
            active_reviewer_ui_context,
            method=method,
            request_body=request_body,
        )
    if parsed_path.startswith("/api/reviewer/source-derived-review"):
        return route_reviewer_workflow_shell_response(
            path,
            reviewer_workflow_shell_context,
            request_body=request_body,
        )
    if parsed_path == AUTH_PROVIDER_INTEGRATION_PLAN_API_PATH:
        return route_auth_provider_integration_plan_response(
            path,
            auth_provider_integration_plan_context,
        )
    if parsed_path == AUDIT_COVERAGE_PLAN_API_PATH:
      return route_audit_coverage_plan_response(
        path,
        audit_coverage_plan_context,
      )
    if parsed_path.startswith(REVIEWER_CREATED_STATE_API_PREFIX):
        return route_reviewer_created_state_api_response(
            path,
            reviewer_created_state_api_context,
            request_body=request_body,
        )
    if parsed_path == SEEDED_CORPUS_RESET_RELOAD_DRY_RUN_API_PATH:
        return route_seeded_corpus_reset_reload_dry_run_response(
            path,
            reset_reload_dry_run_context,
        )
    if parsed_path == SEEDED_CORPUS_RESET_RELOAD_EXECUTION_PLAN_API_PATH:
        return route_seeded_corpus_reset_reload_execution_plan_response(
            path,
            reset_reload_execution_plan_context,
        )
    if parsed_path.startswith(RESET_RELOAD_PLANNING_METADATA_API_PREFIX):
        return route_reset_reload_planning_metadata_api_response(
            path,
            reset_reload_planning_metadata_api_context,
        )
    if parsed_path.startswith(AUDIT_EVENTS_API_PREFIX):
        return route_audit_events_api_response(path, audit_events_api_context)
    if parsed_path.startswith("/api/source-derived-records"):
        return route_source_derived_api_response(path, source_derived_api_context)
    if parsed_path == "/":
        if active_page_data_mode == FIXTURE_DEMO_PAGE_DATA_MODE:
            body = render_app_shell().encode("utf-8")
        else:
            active_ccld_context = _default_ccld_context_for_mode(
                active_auth_config,
                active_page_data_mode,
                ccld_record_request_ui_context,
            )
            reference_source = (
                _facility_reference_from_context(active_ccld_context)
                if active_ccld_context is not None
                else no_reference_facility_source()
            )
            body = render_app_shell(reference_source).encode("utf-8")
        return 200, "text/html; charset=utf-8", body
    if (
        parsed_path == "/source-records"
        or parsed_path.startswith("/source-records/")
        or parsed_path == "/facilities"
        or parsed_path.startswith("/facilities/")
    ) and active_page_data_mode != FIXTURE_DEMO_PAGE_DATA_MODE:
        return 404, "text/plain; charset=utf-8", b"Not found"
    if parsed_path == "/source-records":
        filters = source_record_filters_from_query(parsed_url.query)
        body = render_source_record_list(filters).encode("utf-8")
        return 200, "text/html; charset=utf-8", body
    if parsed_path.startswith("/source-records/"):
        record_id = parsed_path.removeprefix("/source-records/")
        source_record = get_sample_source_record(record_id)
        if source_record is not None:
            body = render_source_record_detail(source_record).encode("utf-8")
            return 200, "text/html; charset=utf-8", body
    if parsed_path == "/facilities":
        body = render_facility_list().encode("utf-8")
        return 200, "text/html; charset=utf-8", body
    if parsed_path.startswith("/facilities/"):
        record_id = parsed_path.removeprefix("/facilities/")
        facility_record = get_sample_facility_record(record_id)
        if facility_record is not None:
            body = render_facility_detail(facility_record).encode("utf-8")
            return 200, "text/html; charset=utf-8", body
    if parsed_path in {"/health", "/api/health"}:
        body = json.dumps(health_response(), sort_keys=True).encode("utf-8")
        return 200, "application/json; charset=utf-8", body
    body = b"Not found"
    return 404, "text/plain; charset=utf-8", body


def _active_auth_runtime_config(
    auth_runtime_config: HostedAuthRuntimeConfig | None,
) -> HostedAuthRuntimeConfig:
    if auth_runtime_config is not None:
        return auth_runtime_config
    try:
        return load_hosted_auth_runtime_config()
    except HostedAuthConfigError:
        return load_hosted_auth_runtime_config(environ={})


def _active_page_data_mode(page_data_mode: str | None) -> str:
    configured_mode = page_data_mode or os.environ.get(PAGE_DATA_MODE_ENV) or ""
    raw_mode = configured_mode.strip().lower()
    mode = raw_mode or POSTGRES_PAGE_DATA_MODE
    if mode not in {POSTGRES_PAGE_DATA_MODE, FIXTURE_DEMO_PAGE_DATA_MODE}:
        return POSTGRES_PAGE_DATA_MODE
    return mode


def _default_reviewer_context_for_mode(
    auth_runtime_config: HostedAuthRuntimeConfig,
    page_data_mode: str,
    explicit_context: ReviewerUiContext | None,
) -> ReviewerUiContext | None:
    if explicit_context is not None:
        return explicit_context
    if page_data_mode == FIXTURE_DEMO_PAGE_DATA_MODE:
        # Fixture/demo mode is gated to local-dev auth only.
        if not auth_runtime_config.local_dev_actor_allowed:
            return None
        return default_local_test_reviewer_ui_context()
    # Postgres mode: outer access control (e.g. Cloudflare Access) handles
    # authentication. If a request reaches here, the caller is considered
    # authorized. Full OIDC/session auth is a future milestone.
    return _default_postgres_reviewer_context()


def _default_ccld_context_for_mode(
    auth_runtime_config: HostedAuthRuntimeConfig,
    page_data_mode: str,
    explicit_context: CcldRecordRequestUiContext | None,
) -> CcldRecordRequestUiContext | None:
    if explicit_context is not None:
        return explicit_context
    reviewer_context = _default_reviewer_context_for_mode(
        auth_runtime_config,
        page_data_mode,
        None,
    )
    if reviewer_context is None:
        return None
    if page_data_mode == FIXTURE_DEMO_PAGE_DATA_MODE:
        fixture_context = default_ccld_record_request_ui_context()
        return CcldRecordRequestUiContext(
            reviewer_ui_context=fixture_context.reviewer_ui_context,
            import_reload_context=fixture_context.import_reload_context,
            retrieval_context=_default_retrieval_context_for_reviewer_context(
                fixture_context.reviewer_ui_context,
                auth_runtime_config,
            ),
        )
    return ccld_record_request_context_for_reviewer_context(
        reviewer_context,
        retrieval_context=_default_retrieval_context_for_reviewer_context(
            reviewer_context,
            auth_runtime_config,
        ),
    )


def _default_retrieval_context_for_reviewer_context(
    reviewer_context: ReviewerUiContext,
    auth_runtime_config: HostedAuthRuntimeConfig,
) -> CcldRetrievalContext | None:
    source_context = reviewer_context.workflow_shell_context.source_derived_api_context
    config = load_ccld_retrieval_config()
    if not config.configured:
        return None
    if config.mock_success_demo_enabled and not auth_runtime_config.local_dev_actor_allowed:
        return None
    retrieval_client = (
        CcldFixtureRetrievalClient()
        if config.mock_success_demo_enabled
        else CcldHttpRetrievalClient()
    )
    return CcldRetrievalContext(
        connection=source_context.connection,
        actor=source_context.actor,
        scope=source_context.scope,
        config=config,
        client=retrieval_client,
    )


def _default_feedback_context(
    auth_runtime_config: HostedAuthRuntimeConfig,
    *,
    request_headers: dict[str, str],
    method: str,
    cloudflare_jwks_fetcher: JwksFetcher | None,
    cloudflare_auth_now: datetime | None,
    github_feedback_config: GitHubFeedbackConfig | None,
    github_feedback_client: GitHubIssueClient | None,
) -> FeedbackContext:
    actor = None
    if auth_runtime_config.local_dev_actor_allowed:
        actor = local_test_reviewer_actor()
    elif (
        method == "POST"
        and auth_runtime_config.production_mode
        and auth_runtime_config.provider_class == CLOUDFLARE_ACCESS_PROVIDER_CLASS
    ):
        actor = authenticate_cloudflare_access_request(
            request_headers,
            auth_runtime_config.cloudflare_access,
            scope=LOCAL_REVIEWER_UI_SCOPE,
            now=cloudflare_auth_now,
            jwks_fetcher=cloudflare_jwks_fetcher,
        )
    return FeedbackContext(
        actor=actor,
        scope=LOCAL_REVIEWER_UI_SCOPE,
        github_config=github_feedback_config or load_github_feedback_config(),
        github_client=github_feedback_client or GitHubRestIssueClient(),
    )


def _default_postgres_reviewer_context() -> ReviewerUiContext | None:
    global _DEFAULT_POSTGRES_REVIEWER_UI_CONTEXT
    if _DEFAULT_POSTGRES_REVIEWER_UI_CONTEXT is not None:
        return _DEFAULT_POSTGRES_REVIEWER_UI_CONTEXT
    try:
        database_config = load_hosted_database_config()
    except HostedDatabaseConfigError:
        return None
    if database_config.database_url is None:
        return None
    engine = create_engine(database_config.database_url)
    connection = engine.connect()
    _DEFAULT_POSTGRES_REVIEWER_UI_CONTEXT = reviewer_ui_context_for_connection(
        connection,
        actor=local_test_reviewer_actor(scopes=(POSTGRES_REVIEWER_UI_SCOPE,)),
        scope=POSTGRES_REVIEWER_UI_SCOPE,
        manage_read_transactions=True,
    )
    return _DEFAULT_POSTGRES_REVIEWER_UI_CONTEXT


def _facility_reference_from_context(
    context: CcldRecordRequestUiContext,
) -> CcldFacilityReferenceSource:
    source_context = context.reviewer_ui_context.workflow_shell_context.source_derived_api_context
    try:
        facility_reference = facility_reference_source_from_connection(
            source_context.connection
        )
    except SQLAlchemyError:
        facility_reference = None
    if facility_reference is not None and (
        facility_reference.records or facility_reference.record_count
    ):
        return facility_reference

    status, _content_type, body = route_source_derived_api_response(
        "/api/source-derived-records?limit=100",
        source_context,
    )
    if status != 200:
        return facility_reference_from_source_derived_records(
            (),
            notice=(
                "PostgreSQL-backed source-derived facility rows could not be read. "
                "Confirm the database is migrated, imported, and accessible to this actor."
            ),
        )
    payload = json.loads(body.decode())
    records = payload.get("records", [])
    if not isinstance(records, list):
        records = []
    return facility_reference_from_source_derived_records(records)


def _facility_reference_summary_from_context(
    context: CcldRecordRequestUiContext,
) -> CcldFacilityReferenceSource:
    source_context = context.reviewer_ui_context.workflow_shell_context.source_derived_api_context
    try:
        facility_reference = facility_reference_source_summary_from_connection(
            source_context.connection
        )
    except SQLAlchemyError:
        return _facility_reference_from_context(context)
    if facility_reference.record_count:
        return facility_reference
    return _facility_reference_from_context(context)


def _projected_facility_reference_for_ids(
    context: CcldRecordRequestUiContext,
    reference_source: CcldFacilityReferenceSource,
    facility_ids: tuple[str, ...],
) -> CcldFacilityReferenceSource:
    valid_ids = tuple(
        dict.fromkeys(value for value in facility_ids if value and value.isdigit())
    )
    if not valid_ids:
        return CcldFacilityReferenceSource(
            source_kind=reference_source.source_kind,
            label=reference_source.label,
            path_label=reference_source.path_label,
            records=(),
            notices=reference_source.notices,
            record_count=reference_source.record_count,
        )
    source_context = (
        context.reviewer_ui_context.workflow_shell_context.source_derived_api_context
    )
    projections = load_authorized_facility_identity_projections(
        source_context.connection,
        source_context.actor,
        scope=source_context.scope,
        public_facility_ids=valid_ids,
        allow_test_candidates=source_context.scope == LOCAL_REVIEWER_UI_SCOPE,
    )
    supplemental_by_id: dict[str, list[Any]] = {value: [] for value in valid_ids}
    for record in reference_source.records:
        if record.facility_number in supplemental_by_id:
            supplemental_by_id[record.facility_number].append(record)
    return CcldFacilityReferenceSource(
        source_kind=reference_source.source_kind,
        label=reference_source.label,
        path_label=reference_source.path_label,
        records=tuple(
            facility_lookup_record_from_projection(
                projections[facility_id],
                supplemental_records=supplemental_by_id[facility_id],
            )
            for facility_id in valid_ids
            if not projections[facility_id].ineligible_candidate_excluded
        ),
        notices=reference_source.notices,
        record_count=reference_source.record_count,
    )


def _projected_lookup_result(
    context: CcldRecordRequestUiContext,
    result: CcldFacilityLookupResult,
) -> CcldFacilityLookupResult:
    source_context = (
        context.reviewer_ui_context.workflow_shell_context.source_derived_api_context
    )
    facility_ids = tuple(
        dict.fromkeys(record.facility_number for record in result.returned_records)
    )
    projections = load_authorized_facility_identity_projections(
        source_context.connection,
        source_context.actor,
        scope=source_context.scope,
        public_facility_ids=facility_ids,
        allow_test_candidates=source_context.scope == LOCAL_REVIEWER_UI_SCOPE,
    )
    return facility_lookup_result_from_projections(result, projections)


def _facility_review_context_from_context(
    context: CcldRecordRequestUiContext | None,
    facility_number: str,
    query_values: dict[str, list[str]] | None = None,
) -> CcldFacilityReviewContext:
    if context is None or not facility_number:
        return CcldFacilityReviewContext()
    return build_facility_review_context(
        context.reviewer_ui_context,
        facility_number,
        query_values,
    )


def _postgres_setup_required_response(heading: str) -> tuple[int, str, bytes]:
    return _auth_html_response(
        503,
        heading,
        "Source-derived records are not yet available. Check that the database is "
        "migrated and a CCLD artifact has been imported.",
    )


def _auth_status_response(
    auth_runtime_config: HostedAuthRuntimeConfig,
) -> tuple[int, str, bytes]:
    body = json.dumps(
        {"auth": auth_runtime_config.safe_summary},
        sort_keys=True,
    ).encode("utf-8")
    return 200, "application/json; charset=utf-8", body


def _auth_placeholder_response(
    parsed_path: str,
    auth_runtime_config: HostedAuthRuntimeConfig,
) -> tuple[int, str, bytes]:
    if parsed_path == AUTH_LOGOUT_PATH:
        heading = "Sign-out placeholder"
        message = (
            "No browser session is created by this scaffold slice. Close the browser "
            "or sign out through the configured managed identity provider when the real "
            "OIDC flow is implemented."
        )
    elif auth_runtime_config.local_dev_actor_allowed:
        heading = "Local-dev tester mode active"
        message = (
            "The scaffold is running with explicit local-dev authenticated tester mode. "
            "This mode is for local development only and is disabled by default in production."
        )
    else:
        heading = "Managed OIDC sign-in not configured in this slice"
        message = (
            "Configure the managed OpenID Connect/OAuth2 provider outside the repository. "
            "This branch documents the provider-agnostic seam but does not exchange auth "
            "codes, create sessions, or validate provider credentials."
        )
    return _auth_html_response(200, heading, message)


def _auth_required_response(heading: str, message: str) -> tuple[int, str, bytes]:
    return _auth_html_response(401, heading, message)


def _cloudflare_access_auth_blocked_response(
    error: CloudflareAccessAuthError,
) -> tuple[int, str, bytes]:
    heading = (
        "Cloudflare Access sign-in required"
        if error.status == 401
        else "Cloudflare Access authentication blocked"
    )
    return _auth_html_response(error.status, heading, str(error))


def _auth_html_response(status: int, heading: str, message: str) -> tuple[int, str, bytes]:
    body = render_page_shell(
        title=heading,
        heading=heading,
        skip_label="Skip to main content",
        main=f"""
    <p>{html.escape(message)}</p>
    <p><a href="/">Return to home</a></p>
    <p><a href="/health">Health check</a></p>
""",
    ).encode()
    return status, "text/html; charset=utf-8", body


class HostedScaffoldHandler(BaseHTTPRequestHandler):
    server_version = "CCLDHostedScaffold/0.1"

    def do_GET(self) -> None:
        status, content_type, body = route_response(
            self.path,
            method="GET",
            request_headers={key: value for key, value in self.headers.items()},
        )
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        redirect_location = _redirect_location_header(self.path, status)
        if redirect_location is not None:
            self.send_header("Location", redirect_location)
        disposition = _content_disposition_header(self.path, status, content_type)
        if disposition is not None:
            self.send_header("Content-Disposition", disposition)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0"))
        request_body = self.rfile.read(content_length) if content_length > 0 else b""
        status, content_type, body = route_response(
            self.path,
            method="POST",
            request_body=request_body,
            request_headers={key: value for key, value in self.headers.items()},
        )
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        disposition = _content_disposition_header(self.path, status, content_type)
        if disposition is not None:
            self.send_header("Content-Disposition", disposition)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return


def _legacy_compare_facilities_redirect_location(path: str) -> str | None:
    parsed = urlparse(path)
    view_by_path = {
        CCLD_FACILITY_REVIEW_PRIORITY_PATH: "licensing-visit-activity",
        REVIEWER_UI_FACILITY_PRIORITIES_PATH: "complaint-priority-compatibility",
        REVIEWER_UI_FACILITY_TRENDS_PATH: "complaint-activity-over-time",
    }
    view = view_by_path.get(parsed.path)
    if view is None:
        return None
    preserved = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key != "view"
    ]
    query = urlencode([("view", view), *preserved])
    return f"{CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH}?{query}"


def _redirect_location_header(path: str, status: int) -> str | None:
    if status not in {301, 302, 303, 307, 308}:
        return None
    return _legacy_compare_facilities_redirect_location(path)


def _redirect_response(location: str) -> tuple[int, str, bytes]:
    safe_location = html.escape(location, quote=True)
    body = render_page_shell(
        title="Moving to Compare Facilities",
        heading="Moving to Compare Facilities",
        skip_label="Skip to main content",
        active_path=CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH,
        main=f'<p><a href="{safe_location}">Continue to Compare Facilities</a>.</p>',
    ).encode("utf-8")
    return 302, "text/html; charset=utf-8", body


def create_server(host: str, port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), HostedScaffoldHandler)


def _content_disposition_header(path: str, status: int, content_type: str) -> str | None:
    if status != 200 or not content_type.startswith("text/csv"):
        return None
    parsed = urlparse(path)
    if parsed.path == REVIEWER_UI_SUBSTANTIATED_EXPORT_PATH:
        filename = complaint_export_attachment_filename(parsed.query)
    elif parsed.path == OPERATOR_COVERAGE_EXPORT_PATH:
        filename = "operator-source-coverage-aggregate.csv"
    elif parsed.path == OPERATOR_COVERAGE_FACILITY_IDS_PATH:
        group = _first_query_value(
            parse_qs(parsed.query, keep_blank_values=True),
            "group",
        )
        if not group:
            return None
        filename = f"operator-source-coverage-{group}-facility-ids.csv"
    else:
        return None
    return f'attachment; filename="{filename}"'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the local hosted tester MVP scaffold.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)

    with create_server(args.host, args.port) as server:
        host, port = server.server_address[:2]
        print(f"{APP_NAME} running locally at http://{format_host(host)}:{port}/")
        print(SCAFFOLD_NOTICE)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("Stopping local hosted tester MVP scaffold.")
    return 0
