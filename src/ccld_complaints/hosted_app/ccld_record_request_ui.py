from __future__ import annotations

import html
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from ccld_complaints.hosted_app.reviewer_ui import (
    REVIEWER_UI_DETAIL_PATH,
    REVIEWER_UI_RECORDS_PATH,
    ReviewerUiContext,
    default_local_test_reviewer_ui_context,
)
from ccld_complaints.hosted_app.source_derived_routes import (
    SOURCE_DERIVED_API_PREFIX,
    route_source_derived_api_response,
)

CCLD_UI_PREFIX = "/ccld"
CCLD_RECORD_REQUEST_PATH = f"{CCLD_UI_PREFIX}/records/request"
_FACILITY_NUMBER_RE = re.compile(r"^\d+$")
_DATE_FIELDS = (
    "complaint_received_date",
    "visit_date",
    "report_date",
    "date_signed",
    "retrieved_at",
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
class CcldRecordRequest:
    facility_number: str
    start_date: str | None = None
    end_date: str | None = None


@dataclass(frozen=True)
class CcldRecordRequestValidation:
    request: CcldRecordRequest | None
    errors: tuple[str, ...]


@dataclass(frozen=True)
class CcldRequestSearchResult:
    matched_records: tuple[Mapping[str, Any], ...]
    matched_complaint_keys: tuple[str, ...]
    all_facility_records: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True)
class CcldRecordRequestUiContext:
    reviewer_ui_context: ReviewerUiContext


_DEFAULT_CCLD_RECORD_REQUEST_CONTEXT: CcldRecordRequestUiContext | None = None


def default_ccld_record_request_ui_context() -> CcldRecordRequestUiContext:
    global _DEFAULT_CCLD_RECORD_REQUEST_CONTEXT
    if _DEFAULT_CCLD_RECORD_REQUEST_CONTEXT is None:
        _DEFAULT_CCLD_RECORD_REQUEST_CONTEXT = CcldRecordRequestUiContext(
            reviewer_ui_context=default_local_test_reviewer_ui_context()
        )
    return _DEFAULT_CCLD_RECORD_REQUEST_CONTEXT


def ccld_record_request_context_for_reviewer_context(
    reviewer_ui_context: ReviewerUiContext,
) -> CcldRecordRequestUiContext:
    return CcldRecordRequestUiContext(reviewer_ui_context=reviewer_ui_context)


def route_ccld_record_request_ui_response(
    path: str,
    context: CcldRecordRequestUiContext | None,
    *,
    method: str = "GET",
    request_body: bytes | None = None,
) -> tuple[int, str, bytes]:
    parsed_url = urlparse(path)
    if context is None:
        return _html_response(
            503,
            _render_message_page(
                title="CCLD record request unavailable",
                heading="CCLD record request unavailable",
                message="Local/test CCLD record request context is not configured.",
                guidance=(
                    "Return to the hosted scaffold home and retry the local/test request page."
                ),
                links=(("Hosted scaffold home", "/"),),
            ),
        )
    if parsed_url.path not in {CCLD_UI_PREFIX, CCLD_RECORD_REQUEST_PATH}:
        return _html_response(
            404,
            _render_message_page(
                title="CCLD request page not found",
                heading="CCLD request page not found",
                message="The requested local/test CCLD page was not found.",
                guidance="Open the CCLD record request page and submit a facility number.",
                links=(("Open CCLD record request", CCLD_RECORD_REQUEST_PATH),),
            ),
        )
    if method == "GET":
        return _html_response(200, _render_request_form())
    if method == "POST":
        return _post_request_response(request_body, context)
    return _html_response(
        405,
        _render_message_page(
            title="CCLD request method unavailable",
            heading="CCLD request method unavailable",
            message="The CCLD request page supports browser GET pages and form POST actions only.",
            guidance="Return to the request page and submit the CCLD-only form.",
            links=(("Return to CCLD request", CCLD_RECORD_REQUEST_PATH),),
        ),
    )


def validate_ccld_record_request(
    form_values: Mapping[str, list[str]],
) -> CcldRecordRequestValidation:
    facility_number = _first_form_value(form_values, "facility_number")
    start_date = _optional_date_value(form_values, "start_date")
    end_date = _optional_date_value(form_values, "end_date")
    errors: list[str] = []
    if not facility_number:
        errors.append("Facility/license number is required.")
    elif not _FACILITY_NUMBER_RE.match(facility_number):
        errors.append(
            "Facility/license number must contain digits only for this CCLD-only request."
        )
    for label, raw_value, parsed_value in (
        ("Start date", _first_form_value(form_values, "start_date"), start_date),
        ("End date", _first_form_value(form_values, "end_date"), end_date),
    ):
        if raw_value and parsed_value is None:
            errors.append(f"{label} must use YYYY-MM-DD format.")
    if start_date is not None and end_date is not None and end_date < start_date:
        errors.append("End date must not be before start date.")
    if errors:
        return CcldRecordRequestValidation(request=None, errors=tuple(errors))
    return CcldRecordRequestValidation(
        request=CcldRecordRequest(
            facility_number=facility_number,
            start_date=start_date.isoformat() if start_date is not None else None,
            end_date=end_date.isoformat() if end_date is not None else None,
        ),
        errors=(),
    )


def find_ccld_records_for_request(
    request: CcldRecordRequest,
    records: list[Mapping[str, Any]],
) -> CcldRequestSearchResult:
    ccld_records = [record for record in records if _is_ccld_record(record)]
    facility_records = [
        record
        for record in ccld_records
        if _record_matches_facility(record, request.facility_number)
    ]
    matching_complaints = [
        record
        for record in facility_records
        if _string(record, "entity_type") == "complaint"
        and _record_matches_date_range(record, request)
    ]
    matched_complaint_keys = tuple(
        _string(record, "source_record_key") for record in matching_complaints
    )
    if request.start_date is None and request.end_date is None:
        matched_records = facility_records
    elif matching_complaints:
        document_ids = {_string(record, "source_document_id") for record in matching_complaints}
        facility_ids = {
            facility_id
            for record in matching_complaints
            if (facility_id := _optional_string(record, "facility_id")) is not None
        }
        matched_records = [
            record
            for record in facility_records
            if _string(record, "source_document_id") in document_ids
            or _optional_string(record, "facility_id") in facility_ids
        ]
    else:
        matched_records = []
    return CcldRequestSearchResult(
        matched_records=tuple(_sort_source_records(matched_records)),
        matched_complaint_keys=matched_complaint_keys,
        all_facility_records=tuple(_sort_source_records(facility_records)),
    )


def _post_request_response(
    request_body: bytes | None,
    context: CcldRecordRequestUiContext,
) -> tuple[int, str, bytes]:
    form_values = _form_values(request_body)
    validation = validate_ccld_record_request(form_values)
    if validation.request is None:
        return _html_response(400, _render_invalid_request(validation.errors))
    source_status, source_records_or_body = _source_derived_records(context)
    if source_status != 200:
        return _html_response(
            source_status,
            _render_message_page(
                title="CCLD local/test records unavailable",
                heading="CCLD local/test records unavailable",
                message="The local/test source-derived records could not be read.",
                guidance=(
                    "Return to the request page and retry with an authorized local/test context."
                ),
                links=(("Return to CCLD request", CCLD_RECORD_REQUEST_PATH),),
            ),
        )
    if isinstance(source_records_or_body, bytes):
        raise ValueError("Expected source-derived records.")
    result = find_ccld_records_for_request(validation.request, source_records_or_body)
    return _html_response(200, _render_request_result(validation.request, result))


def _source_derived_records(
    context: CcldRecordRequestUiContext,
) -> tuple[int, list[Mapping[str, Any]] | bytes]:
    status, _content_type, body = route_source_derived_api_response(
        f"{SOURCE_DERIVED_API_PREFIX}?limit=100",
        context.reviewer_ui_context.workflow_shell_context.source_derived_api_context,
    )
    if status != 200:
        return status, body
    payload = _json_object(body)
    return 200, _record_list(payload, "records")


def _render_request_form() -> str:
    return _page(
        title="CCLD record request",
        heading="CCLD record request",
        main=f"""    <section aria-labelledby="request-scope-heading">
      <h2 id="request-scope-heading">CCLD-only local/test request</h2>
            <p>Enter a CCLD facility/license number and optional date range. This
            local/test page reads existing seeded source-derived records and does not
            run live crawling or imports.</p>
    </section>
    <section aria-labelledby="request-form-heading">
      <h2 id="request-form-heading">Request CCLD records</h2>
      <form action="{CCLD_RECORD_REQUEST_PATH}" method="post">
        <p>
          <label for="facility_number">CCLD facility/license number</label>
          <input id="facility_number" name="facility_number" inputmode="numeric" required>
        </p>
        <p>
          <label for="start_date">Start date (optional)</label>
          <input id="start_date" name="start_date" type="date">
        </p>
        <p>
          <label for="end_date">End date (optional)</label>
          <input id="end_date" name="end_date" type="date">
        </p>
        <p><button type="submit">Request CCLD records</button></p>
      </form>
    </section>
    <section aria-labelledby="request-boundary-heading">
      <h2 id="request-boundary-heading">What happens next</h2>
            <p>If matching seeded CCLD records are already available, this page links
            to reviewer list/detail pages. If not, it explains the existing CCLD
            pipeline command that must run outside the hosted UI.</p>
    </section>""",
    )


def _render_invalid_request(errors: tuple[str, ...]) -> str:
    error_items = "\n".join(f"        <li>{_escape(error)}</li>" for error in errors)
    return _page(
        title="CCLD request needs changes",
        heading="CCLD request needs changes",
        main=f"""    <section aria-labelledby="request-errors-heading">
      <h2 id="request-errors-heading">Check the CCLD request form</h2>
      <ul>
{error_items}
      </ul>
    <p>Return to the CCLD-only request page and retry with a facility/license
    number and valid dates.</p>
      <p><a href="{CCLD_RECORD_REQUEST_PATH}">Return to CCLD request</a></p>
    </section>""",
    )


def _render_request_result(
    request: CcldRecordRequest,
    result: CcldRequestSearchResult,
) -> str:
    if result.matched_records:
        return _render_matched_result(request, result)
    return _render_no_match_result(request, result)


def _render_matched_result(
    request: CcldRecordRequest,
    result: CcldRequestSearchResult,
) -> str:
    rows = "\n".join(
        _render_result_row(record, result.matched_complaint_keys)
        for record in result.matched_records
    )
    return _page(
        title="CCLD request results",
        heading="CCLD request results",
        main=f"""    <section aria-labelledby="request-accepted-heading">
      <h2 id="request-accepted-heading">CCLD request accepted</h2>
            <p>Found {len(result.matched_records)} local/test CCLD source-derived
            row(s) for facility/license number {_escape(request.facility_number)}.</p>
      {_render_date_scope(request)}
            <p>These records are already staged in the local/test hosted seeded corpus.
            The hosted UI did not run live retrieval or import.</p>
    </section>
    <section aria-labelledby="matching-records-heading">
      <h2 id="matching-records-heading">Matching imported CCLD records</h2>
      <table>
        <caption>Matching local/test CCLD source-derived records</caption>
        <thead>
          <tr>
            <th scope="col">Entity type</th>
            <th scope="col">Stable source ID</th>
            <th scope="col">Safe context</th>
            <th scope="col">Reviewer link</th>
          </tr>
        </thead>
        <tbody>
{rows}
        </tbody>
      </table>
      <p><a href="{REVIEWER_UI_RECORDS_PATH}">Open reviewer records</a></p>
    </section>
    {_render_pipeline_plan(request)}""",
    )


def _render_no_match_result(
    request: CcldRecordRequest,
    result: CcldRequestSearchResult,
) -> str:
    local_count = len(result.all_facility_records)
    return _page(
        title="No local CCLD records found",
        heading="No local CCLD records found",
        main=f"""    <section aria-labelledby="no-local-records-heading">
      <h2 id="no-local-records-heading">No matching local/test CCLD records found</h2>
            <p>No staged local/test CCLD records matched facility/license number
            {_escape(request.facility_number)} and the requested date range.</p>
      {_render_date_scope(request)}
      <p>Rows for this facility currently available before date filtering: {local_count}.</p>
      <p><a href="{CCLD_RECORD_REQUEST_PATH}">Return to CCLD request</a></p>
    </section>
    {_render_pipeline_plan(request)}""",
    )


def _render_pipeline_plan(request: CcldRecordRequest) -> str:
    live_fetch_command = (
        ".\\scripts\\run-ccld-live-fetch.ps1 "
        f"-FacilityNumber {_escape(request.facility_number)} "
        "-Limit 1 -MaxRequests 5"
    )
    return f"""<section aria-labelledby="pipeline-plan-heading">
      <h2 id="pipeline-plan-heading">CCLD pipeline step still required</h2>
            <p>This hosted UI does not run live CCLD retrieval or import. To retrieve
            records beyond the existing local/test seeded corpus, run the existing
            explicit CCLD pipeline outside the hosted UI.</p>
      <ol>
        <li>Run <code>{live_fetch_command}</code>
                when live public requests are intended.</li>
        <li>Validate the generated SQLite/Datasette output and source traceability.</li>
                <li>Prepare or import a controlled validated hosted seeded corpus
                artifact before exposing additional records in the hosted reviewer UI.</li>
      </ol>
            <p>The missing hosted execution seam is a safe CCLD-only import/reload path
            from validated pipeline output into hosted source-derived records. That
            should be handled in a separate branch with tests and no live crawling
            from browser requests.</p>
    </section>"""


def _render_result_row(
    record: Mapping[str, Any],
    matched_complaint_keys: tuple[str, ...],
) -> str:
    entity_type = _string(record, "entity_type")
    return f"""          <tr>
            <th scope="row">{_escape(entity_type)}</th>
            <td>{_escape(_string(record, "stable_source_id"))}</td>
            <td>{_escape(_safe_result_context(record))}</td>
            <td>{_render_reviewer_link(record, matched_complaint_keys)}</td>
          </tr>"""


def _render_reviewer_link(
    record: Mapping[str, Any],
    matched_complaint_keys: tuple[str, ...],
) -> str:
    source_record_key = _string(record, "source_record_key")
    if source_record_key in matched_complaint_keys:
        href = f"{REVIEWER_UI_DETAIL_PATH}?{urlencode({'source_record_key': source_record_key})}"
        return f'<a href="{_escape(href)}">Open reviewer detail</a>'
    if matched_complaint_keys:
        href = (
            f"{REVIEWER_UI_DETAIL_PATH}?"
            f"{urlencode({'source_record_key': matched_complaint_keys[0]})}"
        )
        return f'<a href="{_escape(href)}">Open matching complaint detail</a>'
    return f'<a href="{REVIEWER_UI_RECORDS_PATH}">Open reviewer records</a>'


def _safe_result_context(record: Mapping[str, Any]) -> str:
    original_values = _mapping(record, "original_values")
    entity_type = _string(record, "entity_type")
    if entity_type == "facility":
        return _join_context(
            original_values, ("facility_name", "external_facility_number", "county")
        )
    if entity_type == "source_document":
        return _join_context(original_values, ("document_type", "report_index", "content_type"))
    if entity_type == "complaint":
        return _join_context(
            original_values,
            (
                "complaint_control_number",
                "complaint_received_date",
                "visit_date",
                "report_date",
                "finding",
            ),
        )
    if entity_type == "allegation":
        return _join_context(
            original_values, ("allegation_category", "finding", "extraction_confidence")
        )
    if entity_type == "extraction_audit":
        return _join_context(
            original_values, ("field_name", "extraction_method", "extracted_value")
        )
    return "Source-derived context available"


def _join_context(values: Mapping[str, Any], keys: tuple[str, ...]) -> str:
    parts = [
        f"{key}: {_display_value(values[key])}"
        for key in keys
        if key in values and _has_display_value(values[key])
    ]
    return "; ".join(parts) if parts else "No safe scalar context fields available"


def _render_date_scope(request: CcldRecordRequest) -> str:
    if request.start_date is None and request.end_date is None:
        return "<p>Date range: not provided.</p>"
    start_date = request.start_date or "earliest available"
    end_date = request.end_date or "latest available"
    return f"<p>Date range: {_escape(start_date)} to {_escape(end_date)}.</p>"


def _is_ccld_record(record: Mapping[str, Any]) -> bool:
    return _optional_string(record, "connector_name") == "ccld_facility_reports"


def _record_matches_facility(record: Mapping[str, Any], facility_number: str) -> bool:
    original_values = _mapping(record, "original_values")
    facility_id = _optional_string(record, "facility_id") or ""
    source_url = _optional_string(record, "source_url") or ""
    return (
        original_values.get("external_facility_number") == facility_number
        or original_values.get("facility_number") == facility_number
        or facility_id.endswith(facility_number)
        or f"facNum={facility_number}" in source_url
    )


def _record_matches_date_range(record: Mapping[str, Any], request: CcldRecordRequest) -> bool:
    record_dates = _record_dates(record)
    if not record_dates:
        return request.start_date is None and request.end_date is None
    start_date = _parse_iso_date(request.start_date) if request.start_date else None
    end_date = _parse_iso_date(request.end_date) if request.end_date else None
    for record_date in record_dates:
        if start_date is not None and record_date < start_date:
            continue
        if end_date is not None and record_date > end_date:
            continue
        return True
    return False


def _record_dates(record: Mapping[str, Any]) -> tuple[date, ...]:
    original_values = _mapping(record, "original_values")
    dates: list[date] = []
    for key in _DATE_FIELDS:
        value = original_values.get(key, record.get(key))
        if isinstance(value, str):
            parsed = _parse_iso_date(value[:10])
            if parsed is not None:
                dates.append(parsed)
    return tuple(dates)


def _sort_source_records(records: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return sorted(
        records, key=lambda record: (_entity_sort_key(record), _string(record, "stable_source_id"))
    )


def _entity_sort_key(record: Mapping[str, Any]) -> int:
    order = {
        "facility": 0,
        "source_document": 1,
        "complaint": 2,
        "allegation": 3,
        "event": 4,
        "extraction_audit": 5,
    }
    return order.get(_string(record, "entity_type"), 99)


def _form_values(request_body: bytes | None) -> Mapping[str, list[str]]:
    if request_body is None:
        return {}
    return parse_qs(request_body.decode("utf-8"), keep_blank_values=True)


def _first_form_value(form: Mapping[str, list[str]], key: str) -> str:
    values = form.get(key, [])
    if not values:
        return ""
    return values[0].strip()


def _optional_date_value(form: Mapping[str, list[str]], key: str) -> date | None:
    value = _first_form_value(form, key)
    if not value:
        return None
    return _parse_iso_date(value)


def _parse_iso_date(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _json_object(body: bytes) -> dict[str, Any]:
    loaded = json.loads(body)
    if not isinstance(loaded, dict):
        raise ValueError("Expected JSON object.")
    return loaded


def _record_list(payload: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    value = payload[key]
    if not isinstance(value, list):
        raise ValueError(f"Expected {key} to be a list.")
    records: list[Mapping[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise ValueError(f"Expected {key} to contain objects.")
        records.append(item)
    return records


def _mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload[key]
    if not isinstance(value, Mapping):
        raise ValueError(f"Expected {key} to be an object.")
    return value


def _string(payload: Mapping[str, Any], key: str) -> str:
    value = payload[key]
    if not isinstance(value, str):
        raise ValueError(f"Expected {key} to be a string.")
    return value


def _optional_string(payload: Mapping[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _display_value(value: object) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _has_display_value(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _escape(value: str) -> str:
    return html.escape(value, quote=True)


def _html_response(status: int, markup: str) -> tuple[int, str, bytes]:
    _assert_no_secret_markers(markup)
    return status, "text/html; charset=utf-8", markup.encode("utf-8")


def _assert_no_secret_markers(markup: str) -> None:
    lowered = markup.casefold()
    for marker in _SECRET_HTML_MARKERS:
        if marker in lowered:
            raise ValueError(f"CCLD record request HTML contains blocked marker: {marker}")


def _render_message_page(
    *,
    title: str,
    heading: str,
    message: str,
    guidance: str,
    links: tuple[tuple[str, str], ...],
) -> str:
    link_items = "\n".join(
        f'        <li><a href="{_escape(href)}">{_escape(label)}</a></li>' for label, href in links
    )
    return _page(
        title=title,
        heading=heading,
        main=f"""    <section aria-labelledby="message-heading">
            <h2 id="message-heading">{_escape(heading)}</h2>
            <p>{_escape(message)}</p>
            <p>{_escape(guidance)}</p>
            <ul>
{link_items}
            </ul>
        </section>""",
    )


def _page(*, title: str, heading: str, main: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{_escape(title)}</title>
    <style>
        body {{
            color: #1f2937;
            font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            line-height: 1.5;
            margin: 0;
        }}
        header, main, footer {{
            margin: 0 auto;
            max-width: 72rem;
            padding: 1rem;
        }}
        header {{
            border-bottom: 1px solid #d1d5db;
        }}
        nav ul {{
            display: flex;
            flex-wrap: wrap;
            gap: 1rem;
            list-style: none;
            padding: 0;
        }}
        section {{
            border-bottom: 1px solid #e5e7eb;
            padding: 1rem 0;
        }}
        label {{
            display: block;
            font-weight: 650;
            margin-bottom: 0.25rem;
        }}
        input {{
            box-sizing: border-box;
            font: inherit;
            max-width: 20rem;
            padding: 0.45rem;
            width: 100%;
        }}
        button {{
            font: inherit;
            padding: 0.55rem 0.8rem;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
        }}
        caption {{
            font-weight: 650;
            margin-bottom: 0.5rem;
            text-align: left;
        }}
        th, td {{
            border: 1px solid #d1d5db;
            padding: 0.5rem;
            text-align: left;
            vertical-align: top;
        }}
        code {{
            overflow-wrap: anywhere;
        }}
    </style>
</head>
<body>
    <header>
        <h1>{_escape(heading)}</h1>
        <nav aria-label="Hosted scaffold navigation">
            <ul>
                <li><a href="/">Home</a></li>
                <li><a href="{CCLD_RECORD_REQUEST_PATH}">CCLD record request</a></li>
                <li><a href="{REVIEWER_UI_RECORDS_PATH}">Reviewer records</a></li>
            </ul>
        </nav>
    </header>
    <main>
{main}
    </main>
    <footer>
        <p>Local/test hosted reviewer scaffold.</p>
    </footer>
</body>
</html>"""
