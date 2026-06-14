from __future__ import annotations

import argparse
import csv
import html
import json
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from ccld_complaints.hosted_app.audit_event_routes import (
    AUDIT_EVENTS_API_PREFIX,
    AuditEventsApiContext,
    route_audit_events_api_response,
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
from ccld_complaints.hosted_app.reviewer_workflow_shell import (
  ReviewerWorkflowShellContext,
  route_reviewer_workflow_shell_response,
)
from ccld_complaints.hosted_app.source_derived_routes import (
    SourceDerivedApiContext,
    route_source_derived_api_response,
)

APP_NAME = "CCLD Hosted Tester MVP Scaffold"
SCAFFOLD_NOTICE = "Scaffold only: not a functioning reviewer workflow yet."
SAMPLE_DATA_NOTICE = "Local sample source-derived data only; no live public-source data is loaded."
PUBLIC_SOURCE_FACILITY_FIXTURE_DIR = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "public_source_facilities"
)
SOURCE_COVERAGE_FACILITY_FIXTURE = "chhs_facility_master_tiny.csv"


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
    extraction_warning: str


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
    ("extraction_warning", "Extraction warning"),
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
        extraction_warning="Sample-only value; not extracted from live public-source data.",
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
        extraction_warning="Sample-only value; not extracted from live public-source data.",
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


def health_response() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "hosted-tester-mvp-scaffold",
        "scaffold_only": True,
        "review_workflows_implemented": False,
        "authentication_implemented": False,
        "source_data_loaded": False,
    }


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
      <p>Coverage indicators do not prove public-source completeness, statewide
      coverage, official facility status, import status, database state,
      reviewer-created state, or any legal, facility-wide, delay, harm, abuse,
      neglect, liability, or rights-deprivation conclusion.</p>
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


def render_app_shell() -> str:
    page_title = html.escape(APP_NAME)
    notice = html.escape(SCAFFOLD_NOTICE)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{page_title}</title>
</head>
<body>
  <header>
    <p>{notice}</p>
    <h1>{page_title}</h1>
  </header>
  <nav aria-label="Placeholder hosted scaffold navigation">
    <ul>
      <li><a href="#status">Scaffold status</a></li>
      <li><a href="/source-records">Sample source-derived records</a></li>
      <li><a href="/facilities">Sample facility master records</a></li>
      <li><a href="#boundaries">Not implemented yet</a></li>
      <li><a href="/health">Health check</a></li>
    </ul>
  </nav>
  <main>
    <section id="status" aria-labelledby="status-heading">
      <h2 id="status-heading">Local scaffold status</h2>
      <p>This local app shell is runnable on a Windows development workstation.</p>
      <p>No records are loaded, no users are authenticated, and no reviewer
      workflow behavior is active.</p>
      <p>The source-record and facility sample shells use fixture/sample data only.</p>
    </section>
    <section id="boundaries" aria-labelledby="boundaries-heading">
      <h2 id="boundaries-heading">Intentionally not implemented</h2>
      <ul>
        <li>Authentication and authorization.</li>
        <li>Production schema, migrations, or domain tables.</li>
        <li>Import/sync, queues, annotations, corrections, exports, feedback,
        audit trail, or reset/reload.</li>
        <li>Hosted live crawling, hosted connector execution, QNAP, Azure, AWS,
        public URLs, or deployment.</li>
      </ul>
    </section>
  </main>
</body>
</html>
"""


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
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Sample source-derived records - {html.escape(APP_NAME)}</title>
</head>
<body>
  <header>
    <p>{html.escape(SCAFFOLD_NOTICE)}</p>
    <p>{html.escape(SAMPLE_DATA_NOTICE)}</p>
    <h1>Sample source-derived records</h1>
  </header>
  <nav aria-label="Local scaffold navigation">
    <ul>
      <li><a href="/">Scaffold home</a></li>
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
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(record.complaint_control_number)} - {html.escape(APP_NAME)}</title>
</head>
<body>
  <header>
    <p>{html.escape(SCAFFOLD_NOTICE)}</p>
    <p>{html.escape(SAMPLE_DATA_NOTICE)}</p>
    <h1>{html.escape(record.complaint_control_number)}</h1>
  </header>
  <nav aria-label="Local scaffold navigation">
    <ul>
      <li><a href="/">Scaffold home</a></li>
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
        <dt>Extraction warning</dt>
        <dd>{html.escape(record.extraction_warning)}</dd>
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
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Sample facility master records - {html.escape(APP_NAME)}</title>
</head>
<body>
  <header>
    <p>{html.escape(SCAFFOLD_NOTICE)}</p>
    <p>{html.escape(SAMPLE_DATA_NOTICE)}</p>
    <h1>Sample facility master records</h1>
  </header>
  <nav aria-label="Local scaffold navigation">
    <ul>
      <li><a href="/">Scaffold home</a></li>
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
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(record.facility_number)} - {html.escape(APP_NAME)}</title>
</head>
<body>
  <header>
    <p>{html.escape(SCAFFOLD_NOTICE)}</p>
    <p>{html.escape(SAMPLE_DATA_NOTICE)}</p>
    <h1>{html.escape(record.facility_number)}</h1>
  </header>
  <nav aria-label="Local scaffold navigation">
    <ul>
      <li><a href="/">Scaffold home</a></li>
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
  request_body: bytes | None = None,
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
) -> tuple[int, str, bytes]:
    parsed_url = urlparse(path)
    parsed_path = parsed_url.path
    if parsed_path.startswith("/api/reviewer/source-derived-review"):
        return route_reviewer_workflow_shell_response(
            path,
            reviewer_workflow_shell_context,
          request_body=request_body,
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
        return 200, "text/html; charset=utf-8", render_app_shell().encode("utf-8")
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


class HostedScaffoldHandler(BaseHTTPRequestHandler):
    server_version = "CCLDHostedScaffold/0.1"

    def do_GET(self) -> None:
        status, content_type, body = route_response(self.path)
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return


def create_server(host: str, port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), HostedScaffoldHandler)


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