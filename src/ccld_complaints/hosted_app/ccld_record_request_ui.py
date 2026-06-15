from __future__ import annotations

import html
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from ccld_complaints.hosted_app.ccld_facility_lookup import (
    CCLD_FACILITY_LOOKUP_PATH,
    CcldFacilityReferenceSource,
    load_active_ccld_facility_reference,
)
from ccld_complaints.hosted_app.ccld_import_reload import (
    CcldImportReloadContext,
    CcldImportReloadRequest,
    CcldImportReloadResult,
    ccld_import_reload_context_for_connection,
    import_reload_validated_ccld_records,
)
from ccld_complaints.hosted_app.reviewer_created_state_routes import (
    REVIEWER_CREATED_STATE_API_PREFIX,
    route_reviewer_created_state_api_response,
)
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
CCLD_HELP_PATH = f"{CCLD_UI_PREFIX}/help"
_IMPORT_RELOAD_ACTION_FIELD = "ccld_import_reload_action"
_IMPORT_RELOAD_ACTION_VALUE = "load_local_validated_ccld_records"
_REQUEST_CONTEXT_ORIGIN_FIELD = "request_context_origin"
_LOOKUP_FACILITY_NAME_FIELD = "lookup_facility_name"
_FACILITY_NUMBER_RE = re.compile(r"^\d+$")
_DATE_FIELDS = (
    "complaint_received_date",
    "visit_date",
    "report_date",
    "date_signed",
    "retrieved_at",
)
_STATUS_FILTER_VALUES = (
    "all",
    "not_started",
    "in_review",
    "needs_follow_up",
    "reviewed",
    "blocked",
)
_STATUS_LABELS = {
    "all": "All queue records",
    "not_started": "Not started",
    "in_review": "In review",
    "needs_follow_up": "Needs follow-up",
    "reviewed": "Reviewed",
    "blocked": "Blocked",
}
_NEXT_REVIEW_STATUS_ORDER = (
    "not_started",
    "in_review",
    "needs_follow_up",
    "blocked",
    "reviewed",
)
_REQUEST_CONTEXT_ORIGIN_VALUES = (
    "manual_entry",
    "facility_lookup",
    "prefilled_link",
)
_REQUEST_CONTEXT_ORIGIN_LABELS = {
    "manual_entry": "Manual facility/license entry",
    "facility_lookup": "Facility lookup result",
    "prefilled_link": "Prefilled facility/license link",
}
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
    reviewer_status_filter: str = "all"
    request_context_origin: str = "manual_entry"
    lookup_facility_name: str | None = None


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
class CcldRequestQueueItem:
    complaint_record: Mapping[str, Any]
    source_document_record: Mapping[str, Any] | None
    facility_name: str | None
    related_record_count: int
    allegation_count: int
    extraction_audit_count: int
    reviewer_state: Mapping[str, Any]


@dataclass(frozen=True)
class CcldRecordRequestUiContext:
    reviewer_ui_context: ReviewerUiContext
    import_reload_context: CcldImportReloadContext | None = None


_DEFAULT_CCLD_RECORD_REQUEST_CONTEXT: CcldRecordRequestUiContext | None = None


def default_ccld_record_request_ui_context() -> CcldRecordRequestUiContext:
    global _DEFAULT_CCLD_RECORD_REQUEST_CONTEXT
    if _DEFAULT_CCLD_RECORD_REQUEST_CONTEXT is None:
        reviewer_ui_context = default_local_test_reviewer_ui_context()
        _DEFAULT_CCLD_RECORD_REQUEST_CONTEXT = CcldRecordRequestUiContext(
            reviewer_ui_context=reviewer_ui_context,
            import_reload_context=_import_reload_context_for_reviewer_ui_context(
                reviewer_ui_context
            ),
        )
    return _DEFAULT_CCLD_RECORD_REQUEST_CONTEXT


def ccld_record_request_context_for_reviewer_context(
    reviewer_ui_context: ReviewerUiContext,
) -> CcldRecordRequestUiContext:
    return CcldRecordRequestUiContext(
        reviewer_ui_context=reviewer_ui_context,
        import_reload_context=_import_reload_context_for_reviewer_ui_context(reviewer_ui_context),
    )


def _import_reload_context_for_reviewer_ui_context(
    reviewer_ui_context: ReviewerUiContext,
) -> CcldImportReloadContext:
    source_context = reviewer_ui_context.workflow_shell_context.source_derived_api_context
    return ccld_import_reload_context_for_connection(
        source_context.connection,
        scope=source_context.scope,
    )


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
    if parsed_url.path not in {CCLD_UI_PREFIX, CCLD_RECORD_REQUEST_PATH, CCLD_HELP_PATH}:
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
    if method == "GET" and parsed_url.path == CCLD_HELP_PATH:
        return _html_response(200, _render_help_page())
    if method == "GET":
        query_values = parse_qs(parsed_url.query, keep_blank_values=True)
        selected_facility_number = _first_form_value(query_values, "facility_number")
        return _html_response(
            200,
            _render_request_form(
                selected_facility_number=selected_facility_number,
                selected_start_date=_first_form_value(query_values, "start_date"),
                selected_end_date=_first_form_value(query_values, "end_date"),
                request_context_origin=_request_context_origin_from_values(
                    query_values,
                    has_prefilled_facility=bool(selected_facility_number),
                ),
                lookup_facility_name=_optional_lookup_facility_name(query_values),
                reference_source=load_active_ccld_facility_reference(),
            ),
        )
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
    reviewer_status_filter = _first_form_value(form_values, "reviewer_status_filter") or "all"
    request_context_origin = _first_form_value(form_values, _REQUEST_CONTEXT_ORIGIN_FIELD)
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
    if reviewer_status_filter not in _STATUS_FILTER_VALUES:
        errors.append("Choose a supported reviewer-status filter.")
    if request_context_origin and request_context_origin not in _REQUEST_CONTEXT_ORIGIN_VALUES:
        errors.append("Choose a supported CCLD request context.")
    if errors:
        return CcldRecordRequestValidation(request=None, errors=tuple(errors))
    return CcldRecordRequestValidation(
        request=CcldRecordRequest(
            facility_number=facility_number,
            start_date=start_date.isoformat() if start_date is not None else None,
            end_date=end_date.isoformat() if end_date is not None else None,
            reviewer_status_filter=reviewer_status_filter,
            request_context_origin=request_context_origin or "manual_entry",
            lookup_facility_name=_optional_lookup_facility_name(form_values),
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
    import_reload_result: CcldImportReloadResult | None = None
    action = _first_form_value(form_values, _IMPORT_RELOAD_ACTION_FIELD)
    if action and action != _IMPORT_RELOAD_ACTION_VALUE:
        return _html_response(
            400,
            _render_invalid_request(("Choose a supported CCLD local/test action.",)),
        )
    if action == _IMPORT_RELOAD_ACTION_VALUE:
        if context.import_reload_context is None:
            return _html_response(
                503,
                _render_message_page(
                    title="CCLD local validated load unavailable",
                    heading="CCLD local validated load unavailable",
                    message="Local/test CCLD import/reload context is not configured.",
                    guidance="Return to the request page and retry the local/test request.",
                    links=(("Return to CCLD request", CCLD_RECORD_REQUEST_PATH),),
                ),
            )
        try:
            import_reload_result = import_reload_validated_ccld_records(
                context.import_reload_context,
                CcldImportReloadRequest(
                    facility_number=validation.request.facility_number,
                    start_date=validation.request.start_date,
                    end_date=validation.request.end_date,
                ),
            )
        except ValueError as error:
            return _html_response(400, _render_invalid_request((str(error),)))
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
    reviewer_state_records = _reviewer_created_state_records(context)
    state_summaries = _state_summaries_by_source_record(reviewer_state_records)
    return _html_response(
        200,
        _render_request_result(
            validation.request,
            result,
            state_summaries=state_summaries,
            import_reload_result=import_reload_result,
            import_reload_available=context.import_reload_context is not None,
        ),
    )


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


def _reviewer_created_state_records(
    context: CcldRecordRequestUiContext,
) -> list[Mapping[str, Any]]:
    status, _content_type, body = route_reviewer_created_state_api_response(
        REVIEWER_CREATED_STATE_API_PREFIX,
        context.reviewer_ui_context.workflow_shell_context.reviewer_created_state_api_context,
    )
    if status != 200:
        return []
    payload = _json_object(body)
    return _record_list(payload, "reviewer_created_state")


def _render_request_form(
    *,
    selected_facility_number: str = "",
    selected_start_date: str = "",
    selected_end_date: str = "",
    request_context_origin: str = "manual_entry",
    lookup_facility_name: str | None = None,
    reference_source: CcldFacilityReferenceSource | None = None,
) -> str:
    active_reference_source = reference_source or load_active_ccld_facility_reference()
    return _page(
                title="Request CCLD records",
                heading="Request CCLD records",
        main=f"""    <section aria-labelledby="request-scope-heading">
      <h2 id="request-scope-heading">CCLD-only local/test request</h2>
                    <p>This local/test app helps a tester request CCLD public complaint records
                    for one facility/license number, load validated local CCLD output when it is
                    available, and continue into a reviewer queue for notes and status.</p>
                    <p>The public CCLD portal remains the source of record. This page reads or
                    loads local/test source-derived records only; it does not run live crawling
                    or browser-triggered connector execution.</p>
                    <p><a href="{CCLD_FACILITY_LOOKUP_PATH}">Find a CCLD facility by name,
                    city, county, ZIP code, type, status, or facility/license number</a></p>
                    <p><a href="{CCLD_HELP_PATH}">Read how this CCLD review workflow
                    works</a></p>
                </section>
                {_render_workflow_overview()}
    <section aria-labelledby="request-form-heading">
      <h2 id="request-form-heading">Request CCLD records</h2>
            <p>Use the facility/license number printed by CCLD for the facility you want to
            review. Use dates only when you want to narrow the request to complaint,
            visit, report, signed, or retrieval dates already represented in local/test
            source-derived records.</p>
            {_render_request_context_confirmation(
                facility_number=selected_facility_number,
                start_date=selected_start_date or None,
                end_date=selected_end_date or None,
                request_context_origin=request_context_origin,
                lookup_facility_name=lookup_facility_name,
                reference_source=active_reference_source,
                include_change_links=False,
            )}
      <form action="{CCLD_RECORD_REQUEST_PATH}" method="post">
        <input type="hidden" name="{_REQUEST_CONTEXT_ORIGIN_FIELD}"
                    value="{_escape(request_context_origin)}">
        <input type="hidden" name="{_LOOKUP_FACILITY_NAME_FIELD}"
                    value="{_escape(lookup_facility_name or '')}">
        <p>
          <label for="facility_number">CCLD facility/license number</label>
                    <input id="facility_number" name="facility_number" inputmode="numeric"
                                                value="{_escape(selected_facility_number)}"
                                                aria-describedby="facility-number-help" required>
                    <span id="facility-number-help">Enter digits only, for example 157806098.
                    This identifies the CCLD facility or license scope to review.</span>
        </p>
        <p>
          <label for="start_date">Start date (optional)</label>
                    <input id="start_date" name="start_date" type="date"
                        value="{_escape(selected_start_date)}"
                        aria-describedby="date-range-help">
        </p>
        <p>
          <label for="end_date">End date (optional)</label>
                    <input id="end_date" name="end_date" type="date"
                        value="{_escape(selected_end_date)}"
                        aria-describedby="date-range-help">
                    <span id="date-range-help">Dates narrow the local/test result set. Missing
                    records are not proof that CCLD has no records for that period.</span>
        </p>
                <p>
                    <label for="reviewer_status_filter">Reviewer-status filter</label>
                    <select id="reviewer_status_filter" name="reviewer_status_filter"
                        aria-describedby="queue-status-filter-help">
                        <option value="all">All queue records</option>
                        <option value="not_started">Not started</option>
                        <option value="in_review">In review</option>
                        <option value="needs_follow_up">Needs follow-up</option>
                        <option value="reviewed">Reviewed</option>
                        <option value="blocked">Blocked</option>
                    </select>
                    <span id="queue-status-filter-help">The reviewer-status filter is derived
                    from existing local/test reviewer-created note/status rows. Records with no
                    saved reviewer status are counted as not started.</span>
                </p>
                <p><button type="submit">Show CCLD request queue</button></p>
      </form>
    </section>
    {_render_key_terms_section()}
    {_render_feedback_guidance_section()}
    <section aria-labelledby="request-boundary-heading">
      <h2 id="request-boundary-heading">What happens next</h2>
            <p>If matching CCLD source-derived records are already loaded, this page shows a
            CCLD review queue with one row per matching complaint record. If not, it can
            offer a bounded local validated CCLD load, then explain the outside-browser
            live-fetch and artifact-builder handoff.</p>
    </section>""",
    )


def _render_help_page() -> str:
        return _page(
                title="How CCLD review works",
                heading="How CCLD review works",
                main=f"""    <section aria-labelledby="help-purpose-heading">
            <h2 id="help-purpose-heading">What this local/test app does</h2>
            <p>The app helps a tester find CCLD source-derived complaint records for one
            facility/license number and optional date range, then continue into the reviewer
            UI to inspect source traceability, add reviewer notes, and set a reviewer
            status.</p>
            <p>It is CCLD-only and local/test only. It does not prove public-source
            completeness, make legal or facility-wide conclusions, or run live CCLD fetching
            from browser pages.</p>
        </section>
        {_render_workflow_overview()}
        {_render_key_terms_section()}
        {_render_feedback_guidance_section()}
        <section aria-labelledby="help-next-action-heading">
            <h2 id="help-next-action-heading">Next action</h2>
            <p>Start by looking up a facility or entering a facility/license number manually.
            After records are loaded, use the CCLD review queue links to open each complaint record
            in the reviewer UI.</p>
            <p><a href="{CCLD_FACILITY_LOOKUP_PATH}">Find a CCLD facility</a></p>
            <p><a href="{CCLD_RECORD_REQUEST_PATH}">Open the CCLD record request form</a></p>
        </section>""",
        )


def _render_workflow_overview() -> str:
        return """    <section aria-labelledby="workflow-overview-heading">
            <h2 id="workflow-overview-heading">Workflow overview</h2>
            <ol>
                <li>Look up a CCLD facility in local/test reference data or enter a
                facility/license number manually.</li>
                <li>Enter or confirm the optional date range.</li>
                <li>Use records already loaded locally or load validated CCLD records from a
                hosted seeded-corpus JSON artifact.</li>
                <li>Review the matching complaint records in the facility/date-scoped review
                queue.</li>
                <li>Open a record in the reviewer UI, then add a reviewer note or reviewer
                status when helpful.</li>
                <li>Provide feedback about missing records, confusing wording, friction, or
                desired features.</li>
            </ol>
        </section>"""


def _render_key_terms_section() -> str:
        return """    <section aria-labelledby="key-terms-heading">
            <h2 id="key-terms-heading">Key terms</h2>
            <dl>
                <dt>Facility/license number</dt>
                <dd>The digit identifier CCLD uses for the facility or license record scope.</dd>
                <dt>Facility lookup</dt>
                <dd>A local/test search over committed CCLD facility reference CSV fields such
                as facility/license number, name, city, county, ZIP code, type, and status.</dd>
                <dt>CCLD request context</dt>
                <dd>The facility/license number, optional date range, request origin, and active
                local/test facility reference source used for this request.</dd>
                <dt>Facility/date request</dt>
                <dd>A CCLD request for one facility/license number and optional date range.</dd>
                <dt>Date range</dt>
                <dd>An optional filter over dates already extracted into local/test CCLD records.
                It is not a live public-source search.</dd>
                <dt>Loaded local/test CCLD records</dt>
                <dd>Validated local/test CCLD records staged from hosted seeded-corpus JSON into
                source-derived records.</dd>
                <dt>Source-derived records</dt>
                <dd>Source-derived facility, source document, complaint, allegation, event, or
                extraction audit rows that preserve original values and source traceability.</dd>
                <dt>CCLD review queue</dt>
                <dd>The facility/date-scoped list of matching complaint records to review next.</dd>
                <dt>Reviewer-created notes/status</dt>
                <dd>Reviewer-created local/test note/status rows stored separately from
                source-derived records.</dd>
                <dt>Reviewer-status filter</dt>
                <dd>A queue filter based on existing reviewer-created status rows. Records with
                no saved reviewer status are counted as not started.</dd>
                <dt>Suggested next record</dt>
                <dd>Local/test navigation help derived from the current request context and
                reviewer-created note/status cues, not an assignment or record claim.</dd>
                <dt>Manual feedback checklist</dt>
                <dd>The copyable checklist testers paste into the agreed external feedback
                channel. The app does not save or send it.</dd>
                <dt>Reviewer status value</dt>
                <dd>A bounded local/test review state such as needs review, in review, reviewed,
                blocked, or needs follow-up. It is not a public-source finding.</dd>
            </dl>
        </section>"""


def _render_feedback_guidance_section() -> str:
        return """    <section aria-labelledby="feedback-guidance-heading">
            <h2 id="feedback-guidance-heading">Feedback guidance</h2>
            <p>This local/test app does not store, send, email, export, or otherwise persist
            feedback. Useful tester feedback includes the facility/license number, requested
            date range, lookup or request criteria that felt unclear, records that seemed
            missing or unexpected, source traceability cues, note/status confirmation behavior,
            return-to-queue behavior, confusing wording, workflow friction, and suggested
            improvements.</p>
            <p>After submitting a CCLD request, copy the structured checklist into the agreed
            external feedback channel. The checklist is CCLD-only and reflects only the current
            local/test request and queue state.</p>
        </section>"""


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
    *,
    state_summaries: Mapping[str, Mapping[str, Any]],
    import_reload_result: CcldImportReloadResult | None = None,
    import_reload_available: bool = False,
) -> str:
    reference_source = load_active_ccld_facility_reference()
    if result.matched_records:
        return _render_matched_result(
            request,
            result,
            state_summaries=state_summaries,
            import_reload_result=import_reload_result,
            import_reload_available=import_reload_available,
            reference_source=reference_source,
        )
    return _render_no_match_result(
        request,
        result,
        import_reload_result=import_reload_result,
        import_reload_available=import_reload_available,
        reference_source=reference_source,
    )


def _render_matched_result(
    request: CcldRecordRequest,
    result: CcldRequestSearchResult,
    *,
    state_summaries: Mapping[str, Mapping[str, Any]],
    import_reload_result: CcldImportReloadResult | None,
    import_reload_available: bool,
    reference_source: CcldFacilityReferenceSource,
) -> str:
    queue_items = _request_queue_items(result, state_summaries)
    filtered_queue_items = _filtered_queue_items(queue_items, request.reviewer_status_filter)
    rows = "\n".join(_render_queue_row(request, item) for item in filtered_queue_items)
    if not rows:
        rows = _render_empty_filtered_queue_row(request)
    load_text = _load_status_text(import_reload_result)
    return _page(
        title="CCLD request results",
        heading="CCLD request results",
        main=f"""    <section aria-labelledby="request-accepted-heading">
      <h2 id="request-accepted-heading">CCLD request accepted</h2>
            <p>Found {len(result.matched_records)} local/test CCLD source-derived
            row(s) for facility/license number {_escape(request.facility_number)}.</p>
      {_render_date_scope(request)}
                        <p>{_escape(load_text)}</p>
                        <p>The hosted UI did not run live retrieval, browser connector execution,
                        or SQLite conversion.</p>
    </section>
    {_render_request_context_confirmation(
                        facility_number=request.facility_number,
                        start_date=request.start_date,
                        end_date=request.end_date,
                        request_context_origin=request.request_context_origin,
                        lookup_facility_name=request.lookup_facility_name,
                        reference_source=reference_source,
                        include_change_links=True,
                )}
    {_render_import_reload_summary(import_reload_result)}
        <section aria-labelledby="review-queue-heading">
            <h2 id="review-queue-heading">CCLD review queue</h2>
            <p>This queue is tied to the request context confirmed above: the displayed
            facility/license number, date range, request origin, and local/test facility
            reference source. Open each complaint record only after confirming the context is
            the intended one.</p>
            <p>This queue is scoped to the requested facility/license number and date range.
            Open each complaint record to inspect source traceability, add a reviewer note,
            or set a reviewer status.</p>
            <p>After saving a note or status on reviewer detail, return here with the same
            facility/date request context and submit the same local/test request again to see
            queue progress and note/status cues derived from reviewer-created state.</p>
            {_render_queue_first_run_steps()}
            {_render_queue_navigation()}
            {_render_queue_progress_summary(queue_items)}
            {_render_queue_triage_summary(request, queue_items)}
            {_render_queue_continue_guidance(request, queue_items)}
            {_render_queue_filter_form(request)}
            {_render_filtered_empty_recovery(request, queue_items, filtered_queue_items)}
            <p>Showing {len(filtered_queue_items)} of {len(queue_items)} matching complaint
            record(s) for queue filter {_escape(_status_label(request.reviewer_status_filter))}.</p>
      <table>
                <caption>Facility/date-scoped CCLD complaint records ready for review</caption>
        <thead>
          <tr>
                        <th scope="col">Review action</th>
                        <th scope="col">Facility/license number</th>
                        <th scope="col">Request date range</th>
                        <th scope="col">Complaint and report dates</th>
                        <th scope="col">Source document/report</th>
                        <th scope="col">Source traceability summary</th>
                        <th scope="col">Reviewer-created note/status cue</th>
                        <th scope="col">Loaded record context</th>
          </tr>
        </thead>
        <tbody>
{rows}
        </tbody>
      </table>
      <p><a href="{REVIEWER_UI_RECORDS_PATH}">Open reviewer records</a></p>
    </section>
                {_render_feedback_checklist_section(
                        request,
                        queue_items,
                        import_reload_result=import_reload_result,
                        matching_source_record_count=len(result.matched_records),
                        local_facility_record_count=len(result.all_facility_records),
                    reference_source=reference_source,
                )}
        {_render_feedback_guidance_section()}
        {_render_import_reload_action(request, import_reload_available, refresh=True)}
    {_render_pipeline_plan(request)}""",
    )


def _render_no_match_result(
    request: CcldRecordRequest,
    result: CcldRequestSearchResult,
    *,
    import_reload_result: CcldImportReloadResult | None,
    import_reload_available: bool,
    reference_source: CcldFacilityReferenceSource,
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
        <p>Before loading or running outside-browser pipeline steps, confirm the request
        context below. If the facility/license number, date range, or lookup/manual-entry
        context is wrong, change the facility/date criteria before reviewing results.</p>
      <p><a href="{CCLD_RECORD_REQUEST_PATH}">Return to CCLD request</a></p>
    </section>
        {_render_request_context_confirmation(
                facility_number=request.facility_number,
                start_date=request.start_date,
                end_date=request.end_date,
                request_context_origin=request.request_context_origin,
                lookup_facility_name=request.lookup_facility_name,
                reference_source=reference_source,
                include_change_links=True,
            )}
        {_render_no_match_guidance(request, local_count, import_reload_result)}
        {_render_import_reload_summary(import_reload_result)}
                {_render_feedback_checklist_section(
                        request,
                        (),
                        import_reload_result=import_reload_result,
                        matching_source_record_count=0,
                        local_facility_record_count=local_count,
                reference_source=reference_source,
                )}
        {_render_import_reload_action(request, import_reload_available, refresh=False)}
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
            <li>Run <code>.\\scripts\\build-hosted-ccld-artifact.ps1</code> against
            the validated SQLite output to create local/test hosted seeded-corpus JSON.</li>
            <li>Return to this page and use the local validated CCLD load action.</li>
      </ol>
            <p>Use this outside-browser workflow only when the request context is correct and
            local validated data needs to be prepared or refreshed. Do not treat a no-match
            page as proof that the CCLD public portal has no matching public records.</p>
            <p>The remaining gap is production-ready automation around the validated
            artifact handoff. Browser requests still do not run live CCLD retrieval,
            connector execution, or SQLite conversion.</p>
    </section>"""


def _render_no_match_guidance(
    request: CcldRecordRequest,
    local_facility_record_count: int,
    import_reload_result: CcldImportReloadResult | None,
) -> str:
    date_scope = _date_scope_text(request)
    load_state = _no_match_load_state(import_reload_result)
    return f"""    <section aria-labelledby="no-match-guidance-heading">
            <h2 id="no-match-guidance-heading">How to interpret this no-match result</h2>
            <p>This page searched currently loaded local/test source-derived rows only. It did
            not run live CCLD retrieval, connector execution, SQLite conversion, or artifact
            building from the browser.</p>
            <dl>
                <dt>Facility/license number searched</dt>
                <dd>{_escape(request.facility_number)}</dd>
                <dt>Date range searched</dt>
                <dd>{_escape(date_scope)}</dd>
                <dt>Loaded local/test rows for this facility before date filtering</dt>
                <dd>{local_facility_record_count}</dd>
                <dt>Local validated load state</dt>
                <dd>{_escape(load_state)}</dd>
            </dl>
            <ol>
                <li>First confirm the request context above. Change the facility/license number
                or date range if they are not the intended criteria.</li>
                <li>If the context is correct and local validated records have not been loaded,
                use the local validated CCLD load action on this page when available.</li>
                <li>If local validated output has not been prepared yet, run the existing
                outside-browser live fetch and artifact-builder workflow, then return here to
                load or refresh the generated local/test artifact.</li>
                <li>If records still seem missing or unexpected after checking criteria and
                local validated data, copy the feedback checklist and include the facility/date
                request, loaded-row counts, and what seemed missing or unexpected.</li>
            </ol>
            <p>A no-match result is a local/test data state, not a public-source absence,
            record-completeness, legal, or facility-wide conclusion.</p>
        </section>"""


def _no_match_load_state(result: CcldImportReloadResult | None) -> str:
    if result is None:
        return "not submitted for this request"
    if result.import_executed:
        return "local validated rows were loaded or refreshed"
    if result.deferred_reasons:
        return "submitted, but no matching local validated rows were loaded"
    return "submitted without loading rows"


def _render_import_reload_summary(result: CcldImportReloadResult | None) -> str:
    if result is None:
        return ""
    deferred_items = ""
    if result.deferred_reasons:
        deferred_items = "\n".join(
            f"        <li>{_escape(reason)}</li>" for reason in result.deferred_reasons
        )
        deferred_items = f"""      <h3>Deferred local validated rows</h3>
            <ul>
{deferred_items}
            </ul>"""
    artifact_text = "none"
    if result.source_artifact_identities:
        artifact_text = ", ".join(
            _safe_artifact_label(identity) for identity in result.source_artifact_identities
        )
    return f"""    <section aria-labelledby="import-reload-summary-heading">
            <h2 id="import-reload-summary-heading">Local validated CCLD load result</h2>
            <p>Load executed: {_yes_no(result.import_executed)}.</p>
            <p>This result summarizes the existing local/test validated load action. It reads
            prepared hosted seeded-corpus JSON only; it does not run live CCLD retrieval,
            connector execution, or artifact building from the browser.</p>
            <dl>
                <dt>Matching rows before load</dt>
                <dd>{result.available_before_count}</dd>
                <dt>Matching rows after load</dt>
                <dd>{result.available_after_count}</dd>
                <dt>New source-derived rows staged</dt>
                <dd>{result.imported_source_record_count}</dd>
                <dt>Existing source-derived rows refreshed</dt>
                <dd>{result.refreshed_source_record_count}</dd>
                <dt>Duplicate source-derived rows avoided</dt>
                <dd>{result.skipped_duplicate_source_record_count}</dd>
                <dt>Local validated rows outside this request</dt>
                <dd>{result.skipped_non_matching_source_record_count}</dd>
                <dt>Validated artifact used</dt>
                <dd>{_escape(artifact_text)}</dd>
            </dl>
{deferred_items}
        </section>"""


def _render_import_reload_action(
    request: CcldRecordRequest,
    import_reload_available: bool,
    *,
    refresh: bool,
) -> str:
    if not import_reload_available:
        return """    <section aria-labelledby="import-reload-action-heading">
            <h2 id="import-reload-action-heading">Local validated CCLD load unavailable</h2>
            <p>This local/test process does not have a validated CCLD import/reload context.</p>
        </section>"""
    button_label = (
        "Refresh from local validated CCLD output"
        if refresh
        else "Load local validated CCLD records"
    )
    return f"""    <section aria-labelledby="import-reload-action-heading">
            <h2 id="import-reload-action-heading">Local validated CCLD load</h2>
            <p>This action reads committed local/test validated CCLD output and stages
            matching source-derived records through the existing hosted seeded import path.
            It does not run live public web requests.</p>
            <p id="local-load-help">Use this only after the CCLD pipeline output has been
            validated and converted into hosted seeded-corpus JSON outside the browser. If the
            facility/date context is wrong, change the request criteria instead of loading.</p>
            <form action="{CCLD_RECORD_REQUEST_PATH}" method="post">
                <input type="hidden" name="{_REQUEST_CONTEXT_ORIGIN_FIELD}"
                    value="{_escape(request.request_context_origin)}">
                <input type="hidden" name="{_LOOKUP_FACILITY_NAME_FIELD}"
                    value="{_escape(request.lookup_facility_name or '')}">
                <input type="hidden" name="facility_number"
                    value="{_escape(request.facility_number)}">
                <input type="hidden" name="start_date" value="{_escape(request.start_date or "")}">
                <input type="hidden" name="end_date" value="{_escape(request.end_date or "")}">
                <input type="hidden" name="reviewer_status_filter"
                    value="{_escape(request.reviewer_status_filter)}">
                <input type="hidden" name="{_IMPORT_RELOAD_ACTION_FIELD}"
                    value="{_IMPORT_RELOAD_ACTION_VALUE}">
                <p><button type="submit">{_escape(button_label)}</button></p>
            </form>
        </section>"""


def _safe_artifact_label(identity: str) -> str:
    return identity.rsplit("/", maxsplit=1)[-1]


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _render_queue_progress_summary(items: tuple[CcldRequestQueueItem, ...]) -> str:
    counts = _queue_status_counts(items)
    return f"""<section aria-labelledby="queue-progress-heading">
      <h3 id="queue-progress-heading">Queue progress summary</h3>
            <p>Counts use existing reviewer-created status rows. Records without a saved
            status are counted as not started.</p>
      <dl>
        <dt>Total matching complaint records</dt>
        <dd>{len(items)}</dd>
        <dt>Not started</dt>
        <dd>{counts['not_started']}</dd>
        <dt>In review</dt>
        <dd>{counts['in_review']}</dd>
        <dt>Needs follow-up</dt>
        <dd>{counts['needs_follow_up']}</dd>
        <dt>Reviewed</dt>
        <dd>{counts['reviewed']}</dd>
        <dt>Blocked</dt>
        <dd>{counts['blocked']}</dd>
      </dl>
    </section>"""


def _render_queue_navigation() -> str:
    return f"""<nav aria-label="CCLD queue actions">
      <ul>
        <li><a href="{CCLD_FACILITY_LOOKUP_PATH}">Find another CCLD facility</a></li>
        <li><a href="{CCLD_RECORD_REQUEST_PATH}">Start a new CCLD request</a></li>
        <li><a href="{CCLD_HELP_PATH}">Open CCLD workflow help</a></li>
        <li><a href="{REVIEWER_UI_RECORDS_PATH}">Open reviewer records list</a></li>
        <li><a href="#feedback-checklist-section">Copy tester feedback checklist</a></li>
      </ul>
    </nav>"""


def _render_queue_first_run_steps() -> str:
        return """<section aria-labelledby="queue-first-run-heading">
            <h3 id="queue-first-run-heading">First-run queue steps</h3>
            <ol>
                <li>Read the queue progress and triage summaries.</li>
                <li>Open the suggested next complaint record in reviewer detail.</li>
                <li>Add a reviewer note or status only from the detail page when useful.</li>
                <li>Return to this request page and copy the feedback checklist.</li>
            </ol>
        </section>"""


def _render_queue_triage_summary(
    request: CcldRecordRequest,
    items: tuple[CcldRequestQueueItem, ...],
) -> str:
    next_item = _next_queue_item(items)
    next_record_markup = _next_record_markup(next_item, request)
    note_count = sum(1 for item in items if _summary_int(item.reviewer_state, "note_count") > 0)
    status_count = sum(
        1 for item in items if _summary_optional_string(item.reviewer_state, "latest_status")
    )
    traceability_count = sum(1 for item in items if _has_source_traceability(item.complaint_record))
    request_scope = _facility_scope_for_summary(request)
    date_scope = _date_scope_text(request)
    return f"""<section aria-labelledby="queue-triage-heading">
      <h3 id="queue-triage-heading">Queue triage summary</h3>
      <p>Use this summary to decide what to open first. It is derived from the current
      local/test request, existing source-derived traceability fields, and existing
      reviewer-created notes/statuses.</p>
      <dl>
        <dt>Request scope</dt>
                <dd>{_escape(request_scope)}; date range {_escape(date_scope)}</dd>
        <dt>Records with reviewer-created notes</dt>
        <dd>{note_count}</dd>
        <dt>Records with reviewer-created status</dt>
        <dd>{status_count}</dd>
        <dt>Records with source traceability available</dt>
        <dd>{traceability_count}</dd>
        <dt>Suggested next record to open</dt>
        <dd>{next_record_markup}</dd>
      </dl>
    <p>The manual feedback checklist below uses these queue counts and reviewer-created
        note/status cues so testers can report missing records, record-specific
        reviewer-detail observations, confusing wording, or unexpected filter behavior.</p>
    </section>"""


def _render_queue_continue_guidance(
        request: CcldRecordRequest,
        items: tuple[CcldRequestQueueItem, ...],
) -> str:
        next_item = _next_queue_item(items)
        next_record_markup = _next_record_markup(next_item, request)
        return f"""<section aria-labelledby="queue-continue-heading">
            <h3 id="queue-continue-heading">Continue review guidance</h3>
            <p>The suggested next record is derived from this facility/date request context and
            existing reviewer-created note/status cues. It is local/test navigation help, not a
            persisted queue assignment, automatic record claim, official workflow state, or public-
            source conclusion.</p>
            <p>After reviewing detail or saving a note/status, return to this same CCLD request
            queue, submit the same request again when needed, and use the refreshed queue progress
            and suggested next record to continue.</p>
            <dl>
                <dt>Next record guidance</dt>
                <dd>{next_record_markup}</dd>
            </dl>
        </section>"""


def _render_filtered_empty_recovery(
        request: CcldRecordRequest,
        queue_items: tuple[CcldRequestQueueItem, ...],
        filtered_queue_items: tuple[CcldRequestQueueItem, ...],
) -> str:
        if filtered_queue_items or request.reviewer_status_filter == "all":
                return ""
        return f"""<section aria-labelledby="filtered-empty-recovery-heading">
            <h3 id="filtered-empty-recovery-heading">Filtered queue recovery</h3>
            <p>The selected reviewer-status filter hides all queue rows for this same
            facility/date request context. This does not mean records are missing, deleted,
            or absent from local/test data or public source material.</p>
            <dl>
                <dt>Active request context</dt>
                <dd>{_escape(_facility_scope_for_summary(request))}; date range
                {_escape(_date_scope_text(request))}</dd>
                <dt>Selected reviewer-status filter</dt>
                <dd>{_escape(_status_label(request.reviewer_status_filter))}</dd>
                <dt>Queue records before this filter</dt>
                <dd>{len(queue_items)}</dd>
            </dl>
            <p>Reviewer-status filters use existing reviewer-created state. Records without a saved
            status are counted as not started. Clear the filter or choose another status to continue
            reviewing this same request queue.</p>
            <form action="{CCLD_RECORD_REQUEST_PATH}" method="post">
                <input type="hidden" name="{_REQUEST_CONTEXT_ORIGIN_FIELD}"
                    value="{_escape(request.request_context_origin)}">
                <input type="hidden" name="{_LOOKUP_FACILITY_NAME_FIELD}"
                    value="{_escape(request.lookup_facility_name or '')}">
                <input type="hidden" name="facility_number"
                    value="{_escape(request.facility_number)}">
                <input type="hidden" name="start_date" value="{_escape(request.start_date or '')}">
                <input type="hidden" name="end_date" value="{_escape(request.end_date or '')}">
                <input type="hidden" name="reviewer_status_filter" value="all">
                <p><button type="submit">Show all queue records for this request</button></p>
            </form>
            <p>If the filter behavior is confusing, copy the manual feedback checklist and describe
            the selected filter, the same facility/date request context, and what you
            expected to see.</p>
        </section>"""


def _facility_scope_for_summary(request: CcldRecordRequest) -> str:
    return f"facility/license number {request.facility_number}"


def _next_record_markup(
    item: CcldRequestQueueItem | None,
    request: CcldRecordRequest,
) -> str:
    if item is None:
        return "No matching complaint record is available for this request."
    complaint = _mapping(item.complaint_record, "original_values")
    source_record_key = _string(item.complaint_record, "source_record_key")
    detail_href = _reviewer_detail_href_for_request(source_record_key, request=request)
    label = _display_value(complaint.get("complaint_control_number") or source_record_key)
    status = _status_label(_queue_status(item))
    return (
        f'<a href="{_escape(detail_href)}">Open reviewer detail for '
        f'{_escape(label)}</a> ({_escape(status)})'
    )


def _next_queue_item(
    items: tuple[CcldRequestQueueItem, ...],
) -> CcldRequestQueueItem | None:
    for status in _NEXT_REVIEW_STATUS_ORDER:
        for item in items:
            if _queue_status(item) == status:
                return item
    return None


def _has_source_traceability(record: Mapping[str, Any]) -> bool:
    return all(
        _has_display_value(_optional_string(record, key))
        for key in ("source_url", "raw_sha256", "connector_name", "retrieved_at")
    )


def _render_feedback_checklist_section(
    request: CcldRecordRequest,
    queue_items: tuple[CcldRequestQueueItem, ...],
    *,
    import_reload_result: CcldImportReloadResult | None,
    matching_source_record_count: int,
    local_facility_record_count: int,
    reference_source: CcldFacilityReferenceSource,
) -> str:
    checklist = _feedback_checklist_text(
        request,
        queue_items,
        import_reload_result=import_reload_result,
        matching_source_record_count=matching_source_record_count,
        local_facility_record_count=local_facility_record_count,
        reference_source=reference_source,
    )
    return f"""    <section id="feedback-checklist-section"
        aria-labelledby="feedback-checklist-heading">
      <h2 id="feedback-checklist-heading">Copyable tester feedback checklist</h2>
      <p id="feedback-checklist-help">This app does not save or send this feedback.
            Select the checklist text, copy it, paste it into the agreed external feedback
            channel, and add any tester observations before sending. The checklist is generated
            from this CCLD-only local/test request and queue state.</p>
      <p>
        <label for="feedback-checklist">Structured CCLD feedback checklist</label>
        <textarea id="feedback-checklist" rows="28" readonly
          aria-describedby="feedback-checklist-help">{_escape(checklist)}</textarea>
      </p>
    </section>"""


def _feedback_checklist_text(
    request: CcldRecordRequest,
    queue_items: tuple[CcldRequestQueueItem, ...],
    *,
    import_reload_result: CcldImportReloadResult | None,
    matching_source_record_count: int,
    local_facility_record_count: int,
    reference_source: CcldFacilityReferenceSource,
) -> str:
    counts = _queue_status_counts(queue_items)
    reviewer_state_rows = sum(
        _summary_int(item.reviewer_state, "total_rows") for item in queue_items
    )
    reviewer_note_count = sum(
        _summary_int(item.reviewer_state, "note_count") for item in queue_items
    )
    reviewer_status_count = sum(
        1 for item in queue_items if _summary_optional_string(item.reviewer_state, "latest_status")
    )
    lines = [
        "CCLD tester feedback checklist",
        "",
        "Request and lookup context",
        "- Source scope: CCLD public complaint records only",
        "- Local/test app: yes",
        "- Facility lookup used or skipped: "
        f"{_request_origin_label(request.request_context_origin)}",
        f"- Selected lookup facility name: {_display_value(request.lookup_facility_name)}",
        f"- Active facility reference source: {reference_source.label}",
        f"- Facility/license number: {request.facility_number}",
        f"- Date range requested: {_date_scope_text(request)}",
        "- Request criteria that felt unclear:",
        "- Records that seemed outside the requested facility/date scope:",
        "",
        "Queue triage and filters",
        f"- Queue filter used: {_status_label(request.reviewer_status_filter)}",
        f"- Matching source-derived rows shown: {matching_source_record_count}",
        f"- Matching complaint records in queue: {len(queue_items)}",
        f"- Local facility rows before date filtering: {local_facility_record_count}",
        f"- Not started: {counts['not_started']}",
        f"- In review: {counts['in_review']}",
        f"- Needs follow-up: {counts['needs_follow_up']}",
        f"- Reviewed: {counts['reviewed']}",
        f"- Blocked: {counts['blocked']}",
        "- Queue triage summary matched expectations:",
        "- Filter behavior that seemed unexpected:",
        "",
        "Local validated load context",
        f"- Load action submitted on this request: {_yes_no(import_reload_result is not None)}",
        "- Local validated records loaded or refreshed: "
        f"{_yes_no(_feedback_load_executed(import_reload_result))}",
        f"- New source-derived rows staged: {_feedback_imported_count(import_reload_result)}",
        "- Existing source-derived rows refreshed: "
        f"{_feedback_refreshed_count(import_reload_result)}",
        "- Local validated rows outside this request: "
        f"{_feedback_skipped_count(import_reload_result)}",
        "",
        "Reviewer-created state considered",
        f"- Reviewer-created rows read for this queue: {reviewer_state_rows}",
        f"- Reviewer-created notes present: {_yes_no(reviewer_note_count > 0)}",
        f"- Reviewer-created statuses present: {_yes_no(reviewer_status_count > 0)}",
        "",
        "Queue records to spot-check",
        *_feedback_queue_record_lines(queue_items),
        "",
        "Reviewer detail and note/status confirmation",
        "- Reviewer detail record opened:",
        "- Source traceability cues were easy to find:",
        "- Reviewer note/status action used:",
        "- Saved confirmation appeared as expected:",
        "- Saved note/status was visible after save:",
        "- Return-to-queue link worked:",
        "- Queue showed updated note/status after returning and resubmitting:",
        "",
        "Missing, unexpected, or confusing results",
        "- Records that seemed missing:",
        "- Records that seemed unexpected:",
        "- Facility lookup wording that was confusing:",
        "- Request, queue, or reviewer-detail wording that was confusing:",
        "- Keyboard, reading-order, or checklist-copy friction:",
        "- Suggested enhancements:",
        "",
        "Boundary reminders",
        "- Manual-copy only: copy this checklist into the agreed external feedback channel.",
        "- The app does not store, send, email, export, or persist this feedback.",
        "- Rendering this checklist does not change source-derived records, "
        "reviewer-created state, audit rows, import batches, or operational metadata.",
        "- Browser pages did not run live CCLD retrieval or connector execution.",
        "- Missing local/test rows are not proof that CCLD has no public records.",
        "- The CCLD public portal remains the source of record.",
    ]
    return "\n".join(lines)


def _feedback_load_executed(result: CcldImportReloadResult | None) -> bool:
    return result is not None and result.import_executed


def _feedback_imported_count(result: CcldImportReloadResult | None) -> int:
    if result is None:
        return 0
    return result.imported_source_record_count


def _feedback_refreshed_count(result: CcldImportReloadResult | None) -> int:
    if result is None:
        return 0
    return result.refreshed_source_record_count


def _feedback_skipped_count(result: CcldImportReloadResult | None) -> int:
    if result is None:
        return 0
    return result.skipped_non_matching_source_record_count


def _feedback_queue_record_lines(items: tuple[CcldRequestQueueItem, ...]) -> list[str]:
    if not items:
        return ["- None shown for this request."]
    return [_feedback_queue_record_line(item) for item in items]


def _feedback_queue_record_line(item: CcldRequestQueueItem) -> str:
    complaint = _mapping(item.complaint_record, "original_values")
    complaint_control_number = complaint.get("complaint_control_number")
    if not _has_display_value(complaint_control_number):
        complaint_control_number = _string(item.complaint_record, "source_record_key")
    return (
        f"- {_display_value(complaint_control_number)}; "
        f"reviewer status: {_status_label(_queue_status(item))}; "
        f"source traceability cue: {_traceability_summary(item.complaint_record)}; "
        f"reviewer note/status cue: {_reviewer_state_text(item.reviewer_state)}; "
        f"loaded source-derived records in bundle: {item.related_record_count}"
    )


def _render_queue_filter_form(request: CcldRecordRequest) -> str:
    options = "\n".join(
        _status_filter_option(value, selected=value == request.reviewer_status_filter)
        for value in _STATUS_FILTER_VALUES
    )
    return f"""<form action="{CCLD_RECORD_REQUEST_PATH}" method="post">
      <input type="hidden" name="{_REQUEST_CONTEXT_ORIGIN_FIELD}"
        value="{_escape(request.request_context_origin)}">
      <input type="hidden" name="{_LOOKUP_FACILITY_NAME_FIELD}"
        value="{_escape(request.lookup_facility_name or '')}">
      <input type="hidden" name="facility_number" value="{_escape(request.facility_number)}">
      <input type="hidden" name="start_date" value="{_escape(request.start_date or '')}">
      <input type="hidden" name="end_date" value="{_escape(request.end_date or '')}">
      <p>
        <label for="queue_status_filter_result">Reviewer-status filter for this queue</label>
        <select id="queue_status_filter_result" name="reviewer_status_filter"
          aria-describedby="queue-status-filter-result-help">
{options}
        </select>
                <span id="queue-status-filter-result-help">Filtering uses existing
                reviewer-created note/status rows. It does not change source-derived records
                or save queue state.</span>
      </p>
            <p><button type="submit">Apply reviewer-status filter</button></p>
    </form>"""


def _render_empty_filtered_queue_row(request: CcldRecordRequest) -> str:
        return f"""          <tr>
                        <td colspan="8">No complaint records match the selected
                        reviewer-status filter:
                        {_escape(_status_label(request.reviewer_status_filter))}. The filter is
                        hiding rows for the same request context; choose All queue records to
                        return to the full CCLD request queue.</td>
                    </tr>"""


def _status_filter_option(value: str, *, selected: bool) -> str:
    selected_attribute = " selected" if selected else ""
    return (
        f'          <option value="{_escape(value)}"{selected_attribute}>'
        f"{_escape(_status_label(value))}</option>"
    )


def _queue_status_counts(items: tuple[CcldRequestQueueItem, ...]) -> dict[str, int]:
    counts = {status: 0 for status in _STATUS_FILTER_VALUES if status != "all"}
    for item in items:
        counts[_queue_status(item)] += 1
    return counts


def _filtered_queue_items(
    items: tuple[CcldRequestQueueItem, ...],
    reviewer_status_filter: str,
) -> tuple[CcldRequestQueueItem, ...]:
    if reviewer_status_filter == "all":
        return items
    return tuple(item for item in items if _queue_status(item) == reviewer_status_filter)


def _queue_status(item: CcldRequestQueueItem) -> str:
    latest_status = _summary_optional_string(item.reviewer_state, "latest_status")
    if latest_status in {"in_review", "needs_follow_up", "reviewed", "blocked"}:
        return latest_status
    return "not_started"


def _status_label(value: str) -> str:
    return _STATUS_LABELS.get(value, value.replace("_", " "))


def _request_queue_items(
    result: CcldRequestSearchResult,
    state_summaries: Mapping[str, Mapping[str, Any]],
) -> tuple[CcldRequestQueueItem, ...]:
    source_documents = {
        _string(record, "source_document_id"): record
        for record in result.matched_records
        if _string(record, "entity_type") == "source_document"
    }
    items: list[CcldRequestQueueItem] = []
    for complaint_key in result.matched_complaint_keys:
        complaint_record = _record_by_key(result.matched_records, complaint_key)
        if complaint_record is None:
            continue
        source_document_id = _string(complaint_record, "source_document_id")
        related_records = _related_records_for_complaint(complaint_record, result.matched_records)
        facility_record = next(
            (
                record
                for record in related_records
                if _string(record, "entity_type") == "facility"
            ),
            None,
        )
        allegation_count = sum(
            1
            for record in related_records
            if _string(record, "entity_type") == "allegation"
        )
        items.append(
            CcldRequestQueueItem(
                complaint_record=complaint_record,
                source_document_record=source_documents.get(source_document_id),
                facility_name=_facility_name(facility_record),
                related_record_count=len(related_records),
                allegation_count=allegation_count,
                extraction_audit_count=sum(
                    1
                    for record in related_records
                    if _string(record, "entity_type") == "extraction_audit"
                ),
                reviewer_state=state_summaries.get(complaint_key, _empty_state_summary()),
            )
        )
    return tuple(items)


def _render_queue_row(request: CcldRecordRequest, item: CcldRequestQueueItem) -> str:
    complaint = _mapping(item.complaint_record, "original_values")
    source_document = (
        _mapping(item.source_document_record, "original_values")
        if item.source_document_record is not None
        else {}
    )
    source_record_key = _string(item.complaint_record, "source_record_key")
    detail_href = _reviewer_detail_href_for_request(source_record_key, request=request)
    action_label = _queue_action_label(item)
    return f"""          <tr>
            <td><a href="{_escape(detail_href)}">{_escape(action_label)}</a></td>
            <td>{_escape(_facility_scope_text(request.facility_number, item.facility_name))}</td>
            <td>{_escape(_date_scope_text(request))}</td>
            <td>{_escape(_complaint_date_summary(complaint))}</td>
            <td>{_escape(_source_document_summary(item.complaint_record, source_document))}</td>
            <td>{_escape(_traceability_summary(item.complaint_record))}</td>
            <td>{_escape(_reviewer_state_text(item.reviewer_state))}</td>
            <td>{_escape(_loaded_context_text(item))}</td>
          </tr>"""


def _queue_action_label(item: CcldRequestQueueItem) -> str:
    complaint = _mapping(item.complaint_record, "original_values")
    complaint_control_number = complaint.get("complaint_control_number")
    if _has_display_value(complaint_control_number):
        return f"Open reviewer detail for {_display_value(complaint_control_number)}"
    return "Open reviewer detail for this complaint record"


def _reviewer_detail_href_for_request(
    source_record_key: str,
    *,
    request: CcldRecordRequest | None,
) -> str:
    query_values = {"source_record_key": source_record_key}
    if request is not None:
        query_values.update(
            {
                "return_facility_number": request.facility_number,
                "return_start_date": request.start_date or "",
                "return_end_date": request.end_date or "",
                "return_context_origin": request.request_context_origin,
                "return_lookup_facility_name": request.lookup_facility_name or "",
            }
        )
    return f"{REVIEWER_UI_DETAIL_PATH}?{urlencode(query_values)}"


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


def _record_by_key(
    records: tuple[Mapping[str, Any], ...],
    source_record_key: str,
) -> Mapping[str, Any] | None:
    for record in records:
        if _string(record, "source_record_key") == source_record_key:
            return record
    return None


def _related_records_for_complaint(
    complaint_record: Mapping[str, Any],
    records: tuple[Mapping[str, Any], ...],
) -> tuple[Mapping[str, Any], ...]:
    source_document_id = _string(complaint_record, "source_document_id")
    facility_id = _optional_string(complaint_record, "facility_id")
    return tuple(
        record
        for record in records
        if _string(record, "source_document_id") == source_document_id
        or (
            facility_id is not None
            and _optional_string(record, "facility_id") == facility_id
            and _string(record, "entity_type") == "facility"
        )
    )


def _facility_name(record: Mapping[str, Any] | None) -> str | None:
    if record is None:
        return None
    original_values = _mapping(record, "original_values")
    facility_name = original_values.get("facility_name")
    if isinstance(facility_name, str) and facility_name.strip():
        return facility_name.strip()
    return None


def _facility_scope_text(facility_number: str, facility_name: str | None) -> str:
    if facility_name is None:
        return facility_number
    return f"{facility_number}; {facility_name}"


def _complaint_date_summary(values: Mapping[str, Any]) -> str:
    return _join_context(
        values,
        (
            "complaint_received_date",
            "visit_date",
            "report_date",
            "date_signed",
        ),
    )


def _source_document_summary(
    complaint_record: Mapping[str, Any],
    source_document: Mapping[str, Any],
) -> str:
    document_parts = []
    document_id = _string(complaint_record, "source_document_id")
    document_parts.append(f"document: {document_id}")
    report_index = source_document.get("report_index")
    if _has_display_value(report_index):
        document_parts.append(f"report index: {_display_value(report_index)}")
    document_type = source_document.get("document_type")
    if _has_display_value(document_type):
        document_parts.append(f"type: {_display_value(document_type)}")
    return "; ".join(document_parts)


def _traceability_summary(record: Mapping[str, Any]) -> str:
    fields = (
        ("source URL", _optional_string(record, "source_url")),
        ("raw SHA-256", _optional_string(record, "raw_sha256")),
        ("raw path", _optional_string(record, "raw_path")),
        ("connector", _optional_string(record, "connector_name")),
        ("retrieved", _optional_string(record, "retrieved_at")),
    )
    present = [label for label, value in fields if value]
    if len(present) == len(fields):
        return (
            "Complete source traceability: source URL, raw SHA-256, raw path, "
            "connector, retrieval time."
        )
    if present:
        return "Partial source traceability: " + ", ".join(present) + "."
    return "Source traceability not available in this local/test row."


def _loaded_context_text(item: CcldRequestQueueItem) -> str:
    return (
        f"{item.related_record_count} loaded source-derived records in bundle; "
        f"{item.allegation_count} allegation rows; "
        f"{item.extraction_audit_count} extraction audit rows."
    )


def _load_status_text(result: CcldImportReloadResult | None) -> str:
    if result is None:
        return "These records are already staged in the local/test hosted seeded corpus."
    if result.import_executed:
        return "These records were loaded or refreshed from local validated CCLD output."
    return "No local validated CCLD load was executed for this request."


def _state_summaries_by_source_record(
    state_records: list[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for record in state_records:
        source_record_key = _string(record, "source_record_key")
        grouped.setdefault(source_record_key, []).append(record)
    return {
        source_record_key: _state_summary_for_records(records)
        for source_record_key, records in grouped.items()
    }


def _state_summary_for_records(records: list[Mapping[str, Any]]) -> Mapping[str, Any]:
    note_count = 0
    latest_status: str | None = None
    latest_created_at: str | None = None
    for record in records:
        created_at = _string(record, "created_at")
        state_payload = _mapping(record, "state_payload")
        payload_kind = _optional_string(state_payload, "payload_kind")
        if payload_kind == "reviewer_note_scaffold":
            note_count += 1
        reviewer_status = state_payload.get("reviewer_status")
        if isinstance(reviewer_status, str) and reviewer_status.strip():
            if latest_created_at is None or created_at >= latest_created_at:
                latest_status = reviewer_status.strip()
        if latest_created_at is None or created_at >= latest_created_at:
            latest_created_at = created_at
    return {
        "total_rows": len(records),
        "note_count": note_count,
        "latest_status": latest_status,
        "latest_created_at": latest_created_at,
    }


def _empty_state_summary() -> Mapping[str, Any]:
    return {
        "total_rows": 0,
        "note_count": 0,
        "latest_status": None,
        "latest_created_at": None,
    }


def _reviewer_state_text(summary: Mapping[str, Any]) -> str:
    total_rows = _summary_int(summary, "total_rows")
    note_count = _summary_int(summary, "note_count")
    latest_status = _summary_optional_string(summary, "latest_status")
    if total_rows == 0:
        return "No reviewer-created notes/status yet."
    parts = [f"{total_rows} reviewer-created row(s)"]
    parts.append(f"{note_count} reviewer-created note(s)")
    if latest_status is None:
        parts.append("No reviewer-created status yet")
    else:
        parts.append(f"Latest reviewer-created status: {_status_label(latest_status)}")
    return "; ".join(parts) + "."


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


def _date_scope_text(request: CcldRecordRequest) -> str:
    if request.start_date is None and request.end_date is None:
        return "not provided"
    start_date = request.start_date or "earliest available"
    end_date = request.end_date or "latest available"
    return f"{start_date} to {end_date}"


def _date_scope_from_values(start_date: str | None, end_date: str | None) -> str:
    if start_date is None and end_date is None:
        return "not provided"
    start_display = start_date or "earliest available"
    end_display = end_date or "latest available"
    return f"{start_display} to {end_display}"


def _render_request_context_confirmation(
    *,
    facility_number: str,
    start_date: str | None,
    end_date: str | None,
    request_context_origin: str,
    lookup_facility_name: str | None,
    reference_source: CcldFacilityReferenceSource,
    include_change_links: bool,
) -> str:
    facility_display = facility_number if facility_number.strip() else "not entered yet"
    lookup_name_markup = ""
    if lookup_facility_name:
        lookup_name_markup = f"""
        <dt>Selected lookup facility name</dt>
        <dd>{_escape(lookup_facility_name)}</dd>"""
    warning_markup = ""
    if reference_source.warnings:
        warning_items = "\n".join(
            f"        <li>{_escape(warning)}</li>" for warning in reference_source.warnings
        )
        warning_markup = f"""      <ul>
{warning_items}
      </ul>"""
    change_links = ""
    if include_change_links:
        change_href = _request_change_href(
            facility_number=facility_number,
            start_date=start_date,
            end_date=end_date,
            request_context_origin=request_context_origin,
            lookup_facility_name=lookup_facility_name,
        )
        change_links = f"""      <p>If this context is not the one you intended, change the
      facility/date criteria before reviewing queue results.</p>
      <ul>
        <li><a href="{_escape(change_href)}">Change facility/date criteria for this request</a></li>
        <li><a href="{CCLD_FACILITY_LOOKUP_PATH}">Start over with a different CCLD facility</a></li>
      </ul>"""
    return f"""    <section aria-labelledby="request-context-confirmation-heading">
      <h2 id="request-context-confirmation-heading">Confirm request context</h2>
      <p>Use this context before reviewing the queue. Facility reference rows are
      local/test lookup assistance only; CCLD public portal material remains the source of
      record.</p>
      <dl>
        <dt>Request started from</dt>
        <dd>{_escape(_request_origin_label(request_context_origin))}</dd>
        <dt>Facility/license number being requested</dt>
        <dd>{_escape(facility_display)}</dd>{lookup_name_markup}
        <dt>Date range being requested</dt>
        <dd>{_escape(_date_scope_from_values(start_date, end_date))}</dd>
        <dt>Active facility reference source</dt>
        <dd>{_escape(reference_source.label)}</dd>
        <dt>Reference rows loaded for lookup</dt>
        <dd>{len(reference_source.records)}</dd>
      </dl>
{warning_markup}
{change_links}
    </section>"""


def _request_change_href(
    *,
    facility_number: str,
    start_date: str | None,
    end_date: str | None,
    request_context_origin: str,
    lookup_facility_name: str | None,
) -> str:
    query_values = {
        "facility_number": facility_number,
        "start_date": start_date or "",
        "end_date": end_date or "",
        _REQUEST_CONTEXT_ORIGIN_FIELD: request_context_origin,
        _LOOKUP_FACILITY_NAME_FIELD: lookup_facility_name or "",
    }
    return f"{CCLD_RECORD_REQUEST_PATH}?{urlencode(query_values)}"


def _request_origin_label(value: str) -> str:
    return _REQUEST_CONTEXT_ORIGIN_LABELS.get(value, "Manual facility/license entry")


def _request_context_origin_from_values(
    values: Mapping[str, list[str]],
    *,
    has_prefilled_facility: bool,
) -> str:
    raw_value = _first_form_value(values, _REQUEST_CONTEXT_ORIGIN_FIELD)
    if raw_value in _REQUEST_CONTEXT_ORIGIN_VALUES:
        return raw_value
    if has_prefilled_facility:
        return "prefilled_link"
    return "manual_entry"


def _optional_lookup_facility_name(values: Mapping[str, list[str]]) -> str | None:
    value = _first_form_value(values, _LOOKUP_FACILITY_NAME_FIELD).strip()
    if not value:
        return None
    if len(value) > 120:
        return value[:117].rstrip() + "..."
    return value


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


def _summary_int(summary: Mapping[str, Any], key: str) -> int:
    value = summary[key]
    if not isinstance(value, int):
        raise ValueError(f"Expected {key} to be an integer.")
    return value


def _summary_optional_string(summary: Mapping[str, Any], key: str) -> str | None:
    value = summary.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"Expected {key} to be a string or null.")
    return value


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
        textarea {{
            box-sizing: border-box;
            font: inherit;
            max-width: 100%;
            min-height: 24rem;
            padding: 0.5rem;
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
    <a href="#main-content">Skip to main CCLD request content</a>
    <header>
        <h1>{_escape(heading)}</h1>
        <nav aria-label="Hosted scaffold navigation">
            <ul>
                <li><a href="/">Home</a></li>
                <li><a href="{CCLD_RECORD_REQUEST_PATH}">CCLD record request</a></li>
                <li><a href="{CCLD_HELP_PATH}">How this works</a></li>
                <li><a href="{REVIEWER_UI_RECORDS_PATH}">Reviewer records</a></li>
            </ul>
        </nav>
    </header>
    <main id="main-content" tabindex="-1">
{main}
    </main>
    <footer>
        <p>Local/test hosted reviewer scaffold.</p>
    </footer>
</body>
</html>"""
