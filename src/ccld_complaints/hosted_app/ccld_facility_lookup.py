# ruff: noqa: E501

from __future__ import annotations

import csv
import html
import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from ccld_complaints.hosted_app.ui_shell import render_page_shell

CCLD_FACILITY_LOOKUP_PATH = "/ccld/facilities"
CCLD_RECORD_REQUEST_PATH = "/ccld/records/request"
DEFAULT_CCLD_FACILITY_REFERENCE_PATH = Path(
    "tests/fixtures/public_source_facilities/ccld_program_facilities_tiny.csv"
)
DEFAULT_FULL_CCLD_FACILITY_REFERENCE_PATH = Path(
  "data/raw/ccld/facility-reference.csv"
)
CCLD_FACILITY_REFERENCE_CSV_ENV = "CCLD_FACILITY_REFERENCE_CSV"
MAX_FACILITY_LOOKUP_RESULTS = 25
_REQUIRED_COLUMNS = (
    "Facility Number",
    "Facility Name",
    "Facility City",
    "County Name",
    "Facility Zip",
    "Facility Type",
    "Facility Status",
    "Closed Date",
)
_SECRET_HTML_MARKERS = (
    "authorization",
    "client_secret",
    "connection string",
    "connection_string",
    "cookie",
    "password",
    "private_header",
    "private header",
    "provider_issuer",
    "provider_subject",
    "secret",
    "token",
)


@dataclass(frozen=True)
class CcldFacilityLookupRecord:
    facility_number: str
    facility_name: str
    city: str
    county: str
    zip_code: str
    facility_type: str
    status: str
    closed_date: str


@dataclass(frozen=True)
class CcldFacilityReferenceSource:
    source_kind: str
    label: str
    path_label: str
    records: tuple[CcldFacilityLookupRecord, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class CcldFacilityLookupResult:
  query: str
  total_match_count: int
  returned_records: tuple[CcldFacilityLookupRecord, ...]
  result_limit: int
  reference_source: CcldFacilityReferenceSource | None = None

  @property
  def empty_search(self) -> bool:
    return not self.query.strip()

  @property
  def has_more_matches(self) -> bool:
    return self.total_match_count > len(self.returned_records)


def load_ccld_facility_reference(
    path: Path = DEFAULT_CCLD_FACILITY_REFERENCE_PATH,
) -> tuple[CcldFacilityLookupRecord, ...]:
    with path.open("r", encoding="utf-8", newline="") as fixture_file:
        reader = csv.DictReader(fixture_file)
        fieldnames = tuple(reader.fieldnames or ())
        missing_columns = [
            column for column in _REQUIRED_COLUMNS if column not in fieldnames
        ]
        if missing_columns:
            raise ValueError(
                "CCLD facility reference CSV is missing required column(s): "
                + ", ".join(missing_columns)
            )
        records = tuple(_record_from_row(row) for row in reader)
    return tuple(
        sorted(records, key=lambda record: (record.facility_name, record.facility_number))
    )


def load_active_ccld_facility_reference(
    *,
    configured_path: str | None = None,
) -> CcldFacilityReferenceSource:
    configured_value = configured_path
    if configured_value is None:
        configured_value = os.environ.get(CCLD_FACILITY_REFERENCE_CSV_ENV)
    if configured_value:
        configured_reference = Path(configured_value)
        if configured_reference.exists():
            try:
                return CcldFacilityReferenceSource(
                    source_kind="full_local_test_csv",
                    label="Full local/test CCLD facility reference CSV",
                    path_label=_safe_path_label(configured_reference),
                    records=load_ccld_facility_reference(configured_reference),
                )
            except ValueError as error:
                return _tiny_fixture_reference(
                    warnings=(
                        "Configured full local/test CCLD facility reference CSV "
                        f"could not be loaded: {error}. Using tiny fixture fallback.",
                    )
                )
        return _tiny_fixture_reference(
            warnings=(
                "Configured full local/test CCLD facility reference CSV was not found. "
                "Using tiny fixture fallback.",
            )
        )
    if DEFAULT_FULL_CCLD_FACILITY_REFERENCE_PATH.exists():
        try:
            return CcldFacilityReferenceSource(
                source_kind="full_local_test_csv",
                label="Full local/test CCLD facility reference CSV",
                path_label=_safe_path_label(DEFAULT_FULL_CCLD_FACILITY_REFERENCE_PATH),
                records=load_ccld_facility_reference(
                    DEFAULT_FULL_CCLD_FACILITY_REFERENCE_PATH
                ),
            )
        except ValueError as error:
            return _tiny_fixture_reference(
                warnings=(
                    "Default full local/test CCLD facility reference CSV could not be "
                    f"loaded: {error}. Using tiny fixture fallback.",
                )
            )
    return _tiny_fixture_reference(
        warnings=(
            "No full local/test CCLD facility reference CSV is configured or available. "
            "Using tiny fixture fallback.",
        )
    )


def search_ccld_facilities(
    query: str,
    records: Iterable[CcldFacilityLookupRecord] | None = None,
    *,
    result_limit: int = MAX_FACILITY_LOOKUP_RESULTS,
    reference_source: CcldFacilityReferenceSource | None = None,
) -> CcldFacilityLookupResult:
    if result_limit < 1:
        raise ValueError("result_limit must be at least 1.")
    normalized_query = _normalized_text(query)
    if not normalized_query:
        return CcldFacilityLookupResult(
            query=query.strip(),
            total_match_count=0,
            returned_records=(),
            result_limit=result_limit,
            reference_source=reference_source,
        )
    active_reference: CcldFacilityReferenceSource | None = reference_source
    active_records: tuple[CcldFacilityLookupRecord, ...] | None = (
        tuple(records) if records is not None else None
    )
    if active_records is None:
        active_reference = load_active_ccld_facility_reference()
        active_records = active_reference.records
    query_tokens = tuple(normalized_query.split())
    matches = tuple(
        record for record in active_records if _record_matches_query(record, query_tokens)
    )
    return CcldFacilityLookupResult(
        query=query.strip(),
        total_match_count=len(matches),
        returned_records=matches[:result_limit],
        result_limit=result_limit,
        reference_source=active_reference,
    )


def route_ccld_facility_lookup_response(path: str) -> tuple[int, str, bytes]:
    return route_ccld_facility_lookup_response_with_source(path, None)


def route_ccld_facility_lookup_response_with_source(
    path: str,
    reference_source: CcldFacilityReferenceSource | None,
) -> tuple[int, str, bytes]:
    parsed_url = urlparse(path)
    if parsed_url.path != CCLD_FACILITY_LOOKUP_PATH:
        return _html_response(
            404,
            _render_message_page(
                title="CCLD facility lookup not found",
                heading="CCLD facility lookup not found",
                message="The requested local/test CCLD facility lookup page was not found.",
            ),
        )
    query_values = parse_qs(parsed_url.query, keep_blank_values=True)
    query = _first_query_value(query_values, "q")
    return _html_response(200, render_ccld_facility_lookup_page(query, reference_source))


def render_ccld_facility_lookup_page(
    query: str = "",
    reference_source: CcldFacilityReferenceSource | None = None,
) -> str:
    reference_source = reference_source or load_active_ccld_facility_reference()
    result = search_ccld_facilities(
        query,
        reference_source.records,
        reference_source=reference_source,
    )
    return _page(
        title="Find CCLD facility",
        heading="Find CCLD facility",
                main=f"""    <section class="hero-card" aria-labelledby="facility-lookup-scope-heading">
            <h2 id="facility-lookup-scope-heading">Find the facility before retrieving complaint records</h2>
            <p>Search the local CCLD facility reference by facility/license number, facility name,
            city, county, ZIP, type, or status, then use a result to prefill the retrieval request.</p>
            <p class="sr-note">The lookup is reference assistance only. CCLD public portal remains
            the source of record.</p>
        </section>
    {_render_lookup_form(result.query)}
    {_render_reference_source_section(reference_source)}
    {_render_lookup_results(result)}
        <section class="summary-card" aria-labelledby="manual-entry-heading">
      <h2 id="manual-entry-heading">Manual facility/license entry</h2>
      <p>If you already know the CCLD facility/license number, you can still type it directly
      on the request form.</p>
            <p><a class="button button-secondary" href="{CCLD_RECORD_REQUEST_PATH}">Open manual CCLD request form</a></p>
    </section>""",
    )


def facility_reference_from_source_derived_records(
    records: Iterable[Mapping[str, Any]],
    *,
    warning: str | None = None,
) -> CcldFacilityReferenceSource:
    facility_records = tuple(
        sorted(
            (
                _facility_lookup_record_from_source_record(record)
                for record in records
                if _source_record_entity_type(record) == "facility"
            ),
            key=lambda record: (record.facility_name, record.facility_number),
        )
    )
    warnings = () if warning is None else (warning,)
    if not facility_records and warning is None:
        warnings = (
            "No PostgreSQL-backed source-derived facility rows are loaded yet. "
            "Run migrations and import a validated CCLD artifact before facility search.",
        )
    return CcldFacilityReferenceSource(
        source_kind="postgres_source_derived",
        label="PostgreSQL source-derived facility records",
        path_label="hosted_source_derived_records",
        records=facility_records,
        warnings=warnings,
    )


def _source_record_entity_type(record: Mapping[str, Any]) -> str:
    value = record.get("entity_type")
    return value if isinstance(value, str) else ""


def _facility_lookup_record_from_source_record(
    record: Mapping[str, Any],
) -> CcldFacilityLookupRecord:
    original_values = record.get("original_values")
    values = original_values if isinstance(original_values, Mapping) else {}
    facility_number = _source_value(values, "external_facility_number") or _source_value(
        values, "facility_id"
    )
    return CcldFacilityLookupRecord(
        facility_number=facility_number,
        facility_name=_source_value(values, "facility_name"),
        city=_source_value(values, "city"),
        county=_source_value(values, "county"),
        zip_code=_source_value(values, "zip_code"),
        facility_type=_source_value(values, "facility_type"),
        status=_source_value(values, "status"),
        closed_date=_source_value(values, "closed_date"),
    )


def _source_value(values: Mapping[str, Any], key: str) -> str:
    value = values.get(key)
    return value.strip() if isinstance(value, str) else ""


def _record_from_row(row: dict[str, str]) -> CcldFacilityLookupRecord:
    facility_number = _clean_value(row["Facility Number"])
    if not facility_number.isdigit():
        raise ValueError("CCLD facility reference facility numbers must contain digits only.")
    return CcldFacilityLookupRecord(
        facility_number=facility_number,
        facility_name=_clean_value(row["Facility Name"]),
        city=_clean_value(row["Facility City"]),
        county=_clean_value(row["County Name"]),
        zip_code=_clean_value(row["Facility Zip"]),
        facility_type=_clean_value(row["Facility Type"]),
        status=_clean_value(row["Facility Status"]),
        closed_date=_clean_value(row["Closed Date"]),
    )


def _tiny_fixture_reference(
    *,
    warnings: tuple[str, ...] = (),
) -> CcldFacilityReferenceSource:
    return CcldFacilityReferenceSource(
        source_kind="tiny_fixture_fallback",
        label="Tiny committed CCLD facility fixture fallback",
        path_label=DEFAULT_CCLD_FACILITY_REFERENCE_PATH.as_posix(),
        records=load_ccld_facility_reference(DEFAULT_CCLD_FACILITY_REFERENCE_PATH),
        warnings=warnings,
    )


def _record_matches_query(
    record: CcldFacilityLookupRecord,
    query_tokens: tuple[str, ...],
) -> bool:
    search_text = _normalized_text(
        " ".join(
            (
                record.facility_number,
                record.facility_name,
                record.city,
                record.county,
                record.zip_code,
                record.facility_type,
                record.status,
                record.closed_date,
            )
        )
    )
    return all(token in search_text for token in query_tokens)


def _render_lookup_form(query: str) -> str:
        return f"""    <section aria-labelledby="facility-search-heading">
            <h2 id="facility-search-heading">Search facility reference</h2>
      <p id="facility-search-help">Search by facility/license number, facility name, city,
      county, ZIP code, facility type, or status when those fields are present in the local
      reference CSV.</p>
      <form action="{CCLD_FACILITY_LOOKUP_PATH}" method="get">
        <p>
          <label for="facility_lookup_query">Facility search</label>
          <input id="facility_lookup_query" name="q" type="search"
            value="{_escape(query)}" aria-describedby="facility-search-help">
        </p>
                                <p><button type="submit">Search facilities</button></p>
      </form>
    </section>"""


def _render_reference_source_section(source: CcldFacilityReferenceSource) -> str:
    warning_markup = ""
    default_full_path = DEFAULT_FULL_CCLD_FACILITY_REFERENCE_PATH.as_posix()
    if source.warnings:
        warning_items = "\n".join(
            f"        <li>{_escape(warning)}</li>" for warning in source.warnings
        )
        warning_markup = f"""      <ul>
{warning_items}
      </ul>"""
    card_class = "warning-card" if source.source_kind == "tiny_fixture_fallback" else "summary-card"
    return f"""    <section class="{card_class}" aria-labelledby="reference-source-heading">
      <h2 id="reference-source-heading">Facility reference source</h2>
      <p id="reference-source-help">Active source: {_escape(source.label)}.</p>
      <dl aria-describedby="reference-source-help">
        <dt>Reference path</dt>
        <dd>{_escape(source.path_label)}</dd>
        <dt>Rows loaded for lookup</dt>
        <dd>{len(source.records)}</dd>
      </dl>
{warning_markup}
    <p>Full local/test CSV support is read-only. Full facility CSV files must stay outside
    the repository and are not imported or persisted by this app.</p>
            <p>To use a full local/test CSV, set <code>{CCLD_FACILITY_REFERENCE_CSV_ENV}</code>
            or place the file at <code>{default_full_path}</code>.</p>
    </section>"""


def _render_lookup_results(result: CcldFacilityLookupResult) -> str:
    if result.empty_search:
        return """    <section class="empty-state-card" aria-labelledby="facility-results-heading">
      <h2 id="facility-results-heading">Facility lookup results</h2>
      <p>Enter a facility name, facility/license number, city, county, ZIP code, facility type,
      or status to search the local/test CCLD facility reference.</p>
    </section>"""
    if not result.returned_records:
        return f"""    <section class="empty-state-card" aria-labelledby="facility-results-heading">
      <h2 id="facility-results-heading">Facility lookup results</h2>
      <p>No local/test CCLD facility reference rows matched {_escape(result.query)}.</p>
      <p>Try a shorter name, facility/license number, city, county, ZIP code, or facility type.
      You can also continue with manual facility/license number entry.</p>
    <p><a class="button button-secondary" href="{CCLD_RECORD_REQUEST_PATH}">Open manual CCLD request form</a></p>
    </section>"""
    rows = "\n".join(_render_result_row(record) for record in result.returned_records)
    more_guidance = ""
    if result.has_more_matches:
        more_guidance = f"""      <p>Showing the first {len(result.returned_records)} of
      {result.total_match_count} matching local/test facility reference rows. Add more search
      detail to narrow the list.</p>"""
    else:
        more_guidance = f"""      <p>Showing {len(result.returned_records)} of
      {result.total_match_count} matching local/test facility reference row(s).</p>"""
    return f"""    <section aria-labelledby="facility-results-heading">
      <h2 id="facility-results-heading">Facility lookup results</h2>
{more_guidance}
      <table>
        <caption>Local/test CCLD facility reference matches</caption>
        <thead>
          <tr>
            <th scope="col">Action</th>
            <th scope="col">Facility/license number</th>
            <th scope="col">Facility name</th>
            <th scope="col">City</th>
            <th scope="col">County</th>
            <th scope="col">ZIP code</th>
            <th scope="col">Facility type</th>
            <th scope="col">Status</th>
            <th scope="col">Closed date in reference file</th>
          </tr>
        </thead>
        <tbody>
{rows}
        </tbody>
      </table>
    </section>"""


def _render_result_row(record: CcldFacilityLookupRecord) -> str:
    query_values = {
        "facility_number": record.facility_number,
        "request_context_origin": "facility_lookup",
        "lookup_facility_name": record.facility_name,
    }
    href = f"{CCLD_RECORD_REQUEST_PATH}?{urlencode(query_values)}"
    return f"""          <tr>
            <td><a class="button" href="{_escape(href)}">Use for retrieval</a></td>
            <td>{_escape(record.facility_number)}</td>
            <td>{_escape(record.facility_name)}</td>
            <td>{_escape(_display_value(record.city))}</td>
            <td>{_escape(_display_value(record.county))}</td>
            <td>{_escape(_display_value(record.zip_code))}</td>
            <td>{_escape(_display_value(record.facility_type))}</td>
            <td>{_escape(_display_value(record.status))}</td>
            <td>{_escape(_display_value(record.closed_date))}</td>
          </tr>"""


def _render_message_page(*, title: str, heading: str, message: str) -> str:
    return _page(
        title=title,
        heading=heading,
        main=f"""    <section aria-labelledby="message-heading">
      <h2 id="message-heading">{_escape(heading)}</h2>
      <p>{_escape(message)}</p>
      <p><a href="{CCLD_FACILITY_LOOKUP_PATH}">Open CCLD facility lookup</a></p>
    </section>""",
    )


def _page(*, title: str, heading: str, main: str) -> str:
        return render_page_shell(
                title=title,
                heading=heading,
                main=main,
                skip_label="Skip to main CCLD facility lookup content",
                nav_label="Hosted scaffold navigation",
                active_path=CCLD_FACILITY_LOOKUP_PATH,
                step_id="facility",
                next_action="Use a facility for retrieval",
        )


def _first_query_value(query_values: dict[str, list[str]], key: str) -> str:
    values = query_values.get(key, [])
    if not values:
        return ""
    return values[0].strip()


def _safe_path_label(path: Path) -> str:
    if path.is_absolute():
        return path.name
    return path.as_posix()


def _clean_value(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(value.split())


def _normalized_text(value: str) -> str:
    return _clean_value(value).casefold()


def _display_value(value: str) -> str:
    return value if value else "not listed"


def _escape(value: str) -> str:
    return html.escape(value, quote=True)


def _html_response(status: int, markup: str) -> tuple[int, str, bytes]:
    _assert_no_secret_markers(markup)
    return status, "text/html; charset=utf-8", markup.encode("utf-8")


def _assert_no_secret_markers(markup: str) -> None:
    lowered = markup.casefold()
    for marker in _SECRET_HTML_MARKERS:
        if marker in lowered:
            raise ValueError(f"CCLD facility lookup HTML contains blocked marker: {marker}")
