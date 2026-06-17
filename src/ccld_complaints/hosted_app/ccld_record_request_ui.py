# ruff: noqa: E501

from __future__ import annotations

import html
import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from ccld_complaints.hosted_app.auth import (
    HostedAccountDisabledError,
    HostedAuthenticationRequiredError,
    HostedRoleDeniedError,
    HostedScopeDeniedError,
)
from ccld_complaints.hosted_app.ccld_facility_lookup import (
    _FACILITY_COMBOBOX_JS,
    CCLD_FACILITY_LOOKUP_PATH,
    CcldFacilityReferenceSource,
    _build_facility_json_data,
    _limited_reference_note,
    _render_facility_selected_card_html,
    _user_facing_source_label,
    load_active_ccld_facility_reference,
)
from ccld_complaints.hosted_app.ccld_import_reload import (
    CcldImportReloadContext,
    CcldImportReloadRequest,
    CcldImportReloadResult,
    ccld_import_reload_context_for_connection,
    import_reload_validated_ccld_records,
)
from ccld_complaints.hosted_app.ccld_retrieval_jobs import (
    RECORD_TYPE_LABELS,
    SUPPORTED_RECORD_TYPES,
    CcldRetrievalContext,
    CcldRetrievalJobHistoryEntry,
    CcldRetrievalJobResult,
    get_ccld_retrieval_job,
    list_recent_ccld_retrieval_jobs,
    run_ccld_retrieval_job,
    validate_ccld_retrieval_request,
)
from ccld_complaints.hosted_app.facility_case_brief import (
    FacilityCaseBrief,
    FacilityCaseBriefRecord,
    has_review_flag,
    priority_reason_labels,
    render_facility_case_brief,
)
from ccld_complaints.hosted_app.reviewer_created_state_routes import (
    REVIEWER_CREATED_STATE_API_PREFIX,
    route_reviewer_created_state_api_response,
)
from ccld_complaints.hosted_app.reviewer_ui import (
    REVIEWER_UI_DETAIL_PATH,
    REVIEWER_UI_PACKET_DRAFT_PATH,
    REVIEWER_UI_PACKET_PREVIEW_PATH,
    REVIEWER_UI_RECORDS_PATH,
    ReviewerUiContext,
    default_local_test_reviewer_ui_context,
)
from ccld_complaints.hosted_app.source_derived_routes import (
    SOURCE_DERIVED_API_PREFIX,
    route_source_derived_api_response,
)
from ccld_complaints.hosted_app.ui_shell import render_page_shell

CCLD_UI_PREFIX = "/ccld"
CCLD_RECORD_REQUEST_PATH = f"{CCLD_UI_PREFIX}/records/request"
CCLD_HELP_PATH = f"{CCLD_UI_PREFIX}/help"
CCLD_RETRIEVAL_JOBS_PATH = f"{CCLD_UI_PREFIX}/retrieval/jobs"
CCLD_RETRIEVAL_JOB_DETAIL_PATH = f"{CCLD_RETRIEVAL_JOBS_PATH}/detail"
_IMPORT_RELOAD_ACTION_FIELD = "ccld_import_reload_action"
_IMPORT_RELOAD_ACTION_VALUE = "load_local_validated_ccld_records"
_RETRIEVAL_ACTION_FIELD = "ccld_retrieval_action"
_RETRIEVAL_ACTION_VALUE = "run_controlled_ccld_retrieval"
_FEEDBACK_PATH = "/feedback"
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
    record_type: str = "complaints"
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
    retrieval_context: CcldRetrievalContext | None = None


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


def reset_default_ccld_record_request_ui_context() -> None:
    global _DEFAULT_CCLD_RECORD_REQUEST_CONTEXT
    _DEFAULT_CCLD_RECORD_REQUEST_CONTEXT = None


def ccld_record_request_context_for_reviewer_context(
    reviewer_ui_context: ReviewerUiContext,
    *,
    retrieval_context: CcldRetrievalContext | None = None,
) -> CcldRecordRequestUiContext:
    return CcldRecordRequestUiContext(
        reviewer_ui_context=reviewer_ui_context,
        import_reload_context=_import_reload_context_for_reviewer_ui_context(reviewer_ui_context),
        retrieval_context=retrieval_context,
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
    if parsed_url.path not in {
        CCLD_UI_PREFIX,
        CCLD_RECORD_REQUEST_PATH,
        CCLD_HELP_PATH,
        CCLD_RETRIEVAL_JOBS_PATH,
        CCLD_RETRIEVAL_JOB_DETAIL_PATH,
    }:
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
    if method == "GET":
        if parsed_url.path == CCLD_RETRIEVAL_JOBS_PATH:
            status, markup = _retrieval_job_history_response(context)
            return _html_response(status, markup)
        if parsed_url.path == CCLD_RETRIEVAL_JOB_DETAIL_PATH:
            status, markup = _retrieval_job_detail_response(context, parsed_url.query)
            return _html_response(status, markup)
        query_values = parse_qs(parsed_url.query, keep_blank_values=True)
        selected_facility_number = _first_form_value(query_values, "facility_number")
        return _html_response(
            200,
            _render_request_form(
                selected_facility_number=selected_facility_number,
                selected_start_date=_first_form_value(query_values, "start_date"),
                selected_end_date=_first_form_value(query_values, "end_date"),
                selected_record_type=_first_form_value(query_values, "record_type")
                or "complaints",
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
    record_type = _first_form_value(form_values, "record_type") or "complaints"
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
    if record_type not in SUPPORTED_RECORD_TYPES:
        errors.append("Choose a supported CCLD record type.")
    if request_context_origin and request_context_origin not in _REQUEST_CONTEXT_ORIGIN_VALUES:
        errors.append("Choose a supported CCLD request context.")
    if errors:
        return CcldRecordRequestValidation(request=None, errors=tuple(errors))
    return CcldRecordRequestValidation(
        request=CcldRecordRequest(
            facility_number=facility_number,
            start_date=start_date.isoformat() if start_date is not None else None,
            end_date=end_date.isoformat() if end_date is not None else None,
            record_type=record_type,
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
    retrieval_result: CcldRetrievalJobResult | None = None
    retrieval_action = _first_form_value(form_values, _RETRIEVAL_ACTION_FIELD)
    if retrieval_action and retrieval_action != _RETRIEVAL_ACTION_VALUE:
        return _html_response(
            400,
            _render_invalid_request(("Choose a supported CCLD retrieval action.",)),
        )
    if retrieval_action == _RETRIEVAL_ACTION_VALUE:
        if context.retrieval_context is None:
            return _html_response(
                503,
                _render_retrieval_setup_required_page(),
            )
        retrieval_validation = validate_ccld_retrieval_request(
            form_values,
            max_date_range_days=context.retrieval_context.config.max_date_range_days,
        )
        if retrieval_validation.request is None:
            return _html_response(400, _render_invalid_request(retrieval_validation.errors))
        retrieval_result = run_ccld_retrieval_job(
            context.retrieval_context,
            retrieval_validation.request,
        )
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
            retrieval_result=retrieval_result,
            retrieval_available=context.retrieval_context is not None,
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
    selected_record_type: str = "complaints",
    request_context_origin: str = "manual_entry",
    lookup_facility_name: str | None = None,
    reference_source: CcldFacilityReferenceSource | None = None,
) -> str:
    active_reference_source = reference_source or load_active_ccld_facility_reference()
    mode_label = _runtime_mode_label()
    mode_class = _mode_badge_class(mode_label)
    has_facility = bool(selected_facility_number.strip())
    has_date_range = bool(selected_start_date.strip() and selected_end_date.strip())
    workflow_state = _render_request_workflow_state(
        selected_facility_number=selected_facility_number,
        selected_start_date=selected_start_date,
        selected_end_date=selected_end_date,
        request_context_origin=request_context_origin,
        lookup_facility_name=lookup_facility_name,
        reference_source=active_reference_source,
        has_facility=has_facility,
        has_date_range=has_date_range,
    )
    return _page(
                                title="Retrieve complaint records",
                                heading="Retrieve complaint records",
                step_id="retrieve" if has_date_range else "date_range" if has_facility else "facility",
                next_action=(
                        "Retrieve complaint records"
                        if has_date_range
                        else "Set the date range"
                        if has_facility
                        else "Select a facility"
                ),
                main=f"""    <section class="hero-card" aria-labelledby="request-hero-heading">
                    <p class="launch-kicker">Retrieval intake</p>
                    <h2 id="request-hero-heading">Retrieve complaint records for a facility</h2>
                    <p class="launch-value">Create the review request context: confirm a CCLD facility/license number, choose a complaint date range, then retrieve or show loaded local/test complaint records.</p>
            <p><span class="{mode_class}">{mode_label}</span></p>
        </section>
                {_render_request_start_orientation()}
                {workflow_state}""",
    )


def _render_request_start_orientation() -> str:
        return """<section class="quiet-section" aria-labelledby="request-start-orientation-heading">
            <h2 id="request-start-orientation-heading">Start review request context</h2>
            <p>Facility/license number identifies the CCLD facility. Date range narrows complaint, visit, report, signed, or retrieval dates already represented in local/test source-derived records.</p>
            <p>Retrieve records uses the configured controlled server-side retrieval path only when available. Show existing queue searches loaded local/test source-derived records without proving public-source completeness.</p>
            <p>When records are found, continue to the review queue, open the recommended record, review source traceability on detail, then use packet preparation and feedback when needed.</p>
        </section>"""


def _render_request_workflow_state(
        *,
        selected_facility_number: str,
        selected_start_date: str,
        selected_end_date: str,
        request_context_origin: str,
        lookup_facility_name: str | None,
        reference_source: CcldFacilityReferenceSource,
        has_facility: bool,
        has_date_range: bool,
) -> str:
        if not has_facility:
                return _render_facility_selection_state(reference_source)
        context_card = _render_request_context_confirmation(
                facility_number=selected_facility_number,
                start_date=selected_start_date or None,
                end_date=selected_end_date or None,
                request_context_origin=request_context_origin,
                lookup_facility_name=lookup_facility_name,
                reference_source=reference_source,
                include_change_links=False,
        )
        if not has_date_range:
                return f"""<div class="request-layout">
                        <div>{_render_date_range_state(selected_facility_number, request_context_origin, lookup_facility_name, selected_start_date, selected_end_date)}</div>
                        <aside class="sidebar-stack" aria-label="Selected facility context">{context_card}</aside>
                </div>"""
        return f"""<div class="request-layout">
                        <div>{_render_date_ready_state(selected_facility_number, request_context_origin, lookup_facility_name, selected_start_date, selected_end_date)}</div>
                        <aside class="sidebar-stack" aria-label="Selected request context">{context_card}</aside>
                </div>"""


def _render_facility_selection_state(reference_source: CcldFacilityReferenceSource) -> str:
        limited_note = _limited_reference_note(reference_source)
        limited_note_markup = (
                f'<p class="helper-text limited-note">{_escape(limited_note)}</p>'
                if limited_note
                else ""
        )
        json_data = _build_facility_json_data(reference_source)
        selected_card = _render_facility_selected_card_html(mode="request")
        return f"""<section class="workflow-panel" aria-labelledby="facility-selector-heading" id="facility-selector-wrap" data-facility-mode="request">
            <p class="stage-kicker">Facility</p>
            <h2 id="facility-selector-heading">Which facility should be reviewed?</h2>
            <p>Search for a facility when you do not know the exact facility/license number, or type the digit facility/license number directly if you already have it.</p>
            <form action="{CCLD_RECORD_REQUEST_PATH}" method="get" id="facility-select-form">
                <label for="facility-search-input">Facility</label>
                <p id="facility-search-hint" class="helper-text">Search by name, license number, city, ZIP, type, or status.</p>
                <div class="facility-combobox-outer" id="facility-combobox-outer">
                    <input id="facility-search-input" name="facility_number" type="text"
                        inputmode="numeric"
                        placeholder="Facility/license number"
                        aria-describedby="facility-search-hint" required>
                    <ul id="facility-suggestion-list" class="facility-suggestions" aria-label="Facility suggestions" hidden></ul>
                </div>
                <input id="facility-origin-field" name="{_REQUEST_CONTEXT_ORIGIN_FIELD}" type="hidden" value="manual_entry">
                <input id="facility-name-field" name="{_LOOKUP_FACILITY_NAME_FIELD}" type="hidden" value="">
{limited_note_markup}
{selected_card}
                <div class="form-actions">
                    <button type="submit" id="facility-submit-btn">Confirm facility</button>
                    <a class="button button-secondary" href="{CCLD_FACILITY_LOOKUP_PATH}">Find facility</a>
                </div>
            </form>
            <script type="application/json" id="facility-reference-json">{json_data}</script>
            <script>{_FACILITY_COMBOBOX_JS}</script>
        </section>"""


def _render_date_range_state(
        facility_number: str,
        request_context_origin: str,
        lookup_facility_name: str | None,
        selected_start_date: str,
        selected_end_date: str,
) -> str:
        return f"""<section class="workflow-panel" aria-labelledby="date-range-heading">
            <p class="stage-kicker">Date range</p>
            <h2 id="date-range-heading">Choose complaint date range</h2>
            <p>Use a bounded date range that matches the complaint review period you want to inspect.</p>
            <form action="{CCLD_RECORD_REQUEST_PATH}" method="get">
                <input type="hidden" name="facility_number" value="{_escape(facility_number)}">
                <input type="hidden" name="{_REQUEST_CONTEXT_ORIGIN_FIELD}" value="{_escape(request_context_origin)}">
                <input type="hidden" name="{_LOOKUP_FACILITY_NAME_FIELD}" value="{_escape(lookup_facility_name or '')}">
                <div class="fixed-field" aria-labelledby="record-type-heading">
                    <h3 id="record-type-heading">Record type</h3>
                    <p><strong>Complaint records</strong></p>
                    <p class="helper-text">This pilot currently supports CCLD complaint records only.</p>
                </div>
                <div class="form-row">
                    <p>
                        <label for="start_date">Start date</label>
                        <input id="start_date" name="start_date" type="date" value="{_escape(selected_start_date)}" aria-describedby="date-range-help" required>
                    </p>
                    <p>
                        <label for="end_date">End date</label>
                        <input id="end_date" name="end_date" type="date" value="{_escape(selected_end_date)}" aria-describedby="date-range-help" required>
                    </p>
                </div>
                <p id="date-range-help" class="helper-text">Use the date range to narrow complaint, visit, report, signed, or retrieval dates represented in the source-derived records.</p>
                <div class="form-actions">
                    <button type="submit">Confirm date range</button>
                    <a class="button button-secondary" href="{CCLD_RECORD_REQUEST_PATH}">Change facility</a>
                </div>
            </form>
        </section>"""


def _render_date_ready_state(
        facility_number: str,
        request_context_origin: str,
        lookup_facility_name: str | None,
        selected_start_date: str,
        selected_end_date: str,
) -> str:
        return f"""<section class="workflow-panel workflow-panel-primary" aria-labelledby="retrieve-ready-heading">
            <p class="stage-kicker">Retrieve records</p>
            <h2 id="retrieve-ready-heading">Ready to retrieve complaint records</h2>
            <p>Review this facility/date context before retrieving or showing loaded local/test complaint records. After records are found, open the review queue and start with the recommended record.</p>
            <dl>
                <dt>Facility/license number</dt>
                <dd>{_escape(facility_number)}</dd>
                <dt>Date range</dt>
                <dd>{_escape(selected_start_date)} to {_escape(selected_end_date)}</dd>
                <dt>Record type</dt>
                <dd>Complaint records</dd>
            </dl>
            <form action="{CCLD_RECORD_REQUEST_PATH}" method="post">
                <input type="hidden" name="{_REQUEST_CONTEXT_ORIGIN_FIELD}" value="{_escape(request_context_origin)}">
                <input type="hidden" name="{_LOOKUP_FACILITY_NAME_FIELD}" value="{_escape(lookup_facility_name or '')}">
                <input type="hidden" name="facility_number" value="{_escape(facility_number)}">
                <input type="hidden" name="record_type" value="complaints">
                <input type="hidden" name="start_date" value="{_escape(selected_start_date)}">
                <input type="hidden" name="end_date" value="{_escape(selected_end_date)}">
                <input type="hidden" name="reviewer_status_filter" value="all">
                <div class="form-actions">
                    <button type="submit" name="{_RETRIEVAL_ACTION_FIELD}" value="{_RETRIEVAL_ACTION_VALUE}">Retrieve complaint records</button>
                    <button class="secondary" type="submit">Show existing queue</button>
                    <a class="button button-quiet" href="{CCLD_RECORD_REQUEST_PATH}?{_escape(urlencode({'facility_number': facility_number, _REQUEST_CONTEXT_ORIGIN_FIELD: request_context_origin, _LOOKUP_FACILITY_NAME_FIELD: lookup_facility_name or ''}))}">Change date range</a>
                </div>
            </form>
        </section>"""


def _render_facility_datalist_options(source: CcldFacilityReferenceSource) -> str:
        return "\n".join(
                f'                      <option value="{_escape(record.facility_number)}" '
                f'label="{_escape(_facility_suggestion_label(record))}"></option>'
                for record in source.records[:100]
        )


def _facility_suggestion_label(record: Any) -> str:
        geography = ", ".join(
                part for part in (record.city, record.county) if part
        )
        type_status = " / ".join(
                part for part in (record.facility_type, record.status) if part
        )
        pieces = [record.facility_name, record.facility_number]
        if geography:
                pieces.append(geography)
        if type_status:
                pieces.append(type_status)
        return " - ".join(pieces)


def _runtime_mode_label() -> str:
    demo_mode = os.environ.get("CCLD_RETRIEVAL_DEMO_MODE", "").strip().casefold()
    retrieval_enabled = os.environ.get("CCLD_RETRIEVAL_ENABLED", "").strip().casefold()
    raw_dir = os.environ.get("CCLD_RETRIEVAL_RAW_DIR", "").strip()
    if demo_mode == "mock-success":
        return "Fixture/mock demo"
    if retrieval_enabled == "enabled" and raw_dir:
        return "Live public CCLD"
    return "Retrieval not configured"

def _mode_badge_class(label: str) -> str:
    if label == "Live public CCLD":
        return "badge badge-live"
    if label == "Fixture/mock demo":
        return "badge badge-demo"
    return "badge badge-muted"


def _render_help_page() -> str:
        return _page(
                title="How CCLD RecordsTracker works",
                                heading="Help",
            active_path=CCLD_HELP_PATH,
            step_id="start",
            next_action="Start facility review or open the section you need",
            show_workflow_indicator=False,
                                main=f"""    <section class="hero-card" aria-labelledby="help-purpose-heading">
                        <p class="launch-kicker">Product help</p>
                            <h2 id="help-purpose-heading">Use RecordsTracker for facility complaint review</h2>
                            <p>Learn how to retrieve complaint records, review source-derived values, and add reviewer-created notes/status safely.</p>
                </section>
                <section class="help-details" aria-labelledby="help-topics-heading">
                    <h2 id="help-topics-heading">Help topics</h2>
                    <details open>
                        <summary id="help-purpose-topic-heading">What this tool helps you do</summary>
                        <p>Use RecordsTracker to select a facility, retrieve public CCLD complaint records,
                        review key source-derived values, and identify records that need source-traceable
                        attorney review.</p>
                    </details>
                    <details>
                        <summary id="help-how-heading">How to review a facility</summary>
                        <p>Facility lookup or manual entry fills a CCLD facility/license number. The
                        request page uses that context and a date range to retrieve or show matching
                        complaint records. The review queue helps you open the recommended record,
                        reviewer detail is the complaint review workspace, reviewer-created status/note
                        cues update queue progress, packet preview/draft are local/test preparation
                        checkpoints, and feedback carries safe context when something is confusing.</p>
                    </details>
                    <details>
                        <summary id="help-flags-heading">What review flags mean</summary>
                        <p>Review flags are source-derived screening aids such as possible delay indicators,
                        missing local/test date fields, proxy-date cues, or source-traceability cues. They
                        identify records needing attorney review; they are not legal conclusions.</p>
                    </details>
                    <details>
                        <summary id="help-not-prove-heading">What the app does not prove</summary>
                        <p>It does not prove no complaints exist, CCLD source coverage is complete, legal
                        conclusions, facility-wide conclusions, verified harm, abuse, neglect, liability,
                        or rights-deprivation.</p>
                    </details>
                    <details>
                        <summary id="help-traceability-heading">How source traceability works</summary>
                        <p>Imported records retain safe source URL, raw SHA-256, connector, retrieval time,
                        and source document identifiers when available. Raw artifact paths and private
                        server details are not shown in the browser.</p>
                    </details>
                    <details>
                        <summary id="help-separation-heading">How reviewer-created notes/status work</summary>
                        <p>Imported public-source-derived values remain source-derived records. Notes and
                        status are reviewer-created state and do not edit source-derived fields.</p>
                    </details>
                    <details>
                        <summary id="help-live-heading">Retrieval modes</summary>
                        <p>When the mode badge says live public retrieval, controlled server-side
                        public CCLD HTTP requests occur only after browser submit. When the mode badge
                        says fixture/mock demo, committed fixtures are used and no live CCLD calls are made.</p>
                    </details>
                    <details>
                        <summary id="help-feedback-heading">How to send useful feedback</summary>
                        <p>Include the facility/license number, date range, visible job state, complaint
                        control number when relevant, and what action or wording felt confusing. Do not
                        include private facts, credentials, legal strategy, privileged work product,
                        private URLs, private values, or unrelated sensitive details.</p>
                    </details>
                    <details>
                        <summary id="help-packet-heading">How packet preparation fits in</summary>
                        <p>Packet preview and packet draft summarize loaded local/test complaint records,
                        source traceability cues, reviewer-created status/note cues, and review-readiness
                        concerns. They are not legal reports, final exports, or source-completeness proof.</p>
                    </details>
                </section>
                <section aria-labelledby="help-next-action-heading">
                        <h2 id="help-next-action-heading">Next action</h2>
                        <p><a class="button" href="{CCLD_RECORD_REQUEST_PATH}">Retrieve complaint records</a></p>
                        <p><a class="button button-secondary" href="{CCLD_FACILITY_LOOKUP_PATH}">Find a facility</a></p>
                        <p><a href="{CCLD_RETRIEVAL_JOBS_PATH}">View retrieval jobs</a></p>
                </section>""",
        )


def _render_workflow_overview() -> str:
        return """    <section aria-labelledby="workflow-overview-heading">
            <h2 id="workflow-overview-heading">Review session path</h2>
            <ol>
                <li>Start with facility lookup when you need the facility/license number, or
                use manual entry when you already know it.</li>
                <li>Confirm the CCLD request context: facility/license number, optional date
                range, lookup/manual-entry origin, and active local/test facility reference
                source.</li>
                <li>Submit the facility/date request to search loaded local/test CCLD records.
                If no local match appears, use the no-match/load guidance without treating it as
                public-source absence.</li>
                <li>Use the CCLD review queue to choose a suggested next record, filter by
                reviewer-created status, or spot queue wording that belongs in feedback.</li>
                <li>Use reviewer detail to check source traceability, source-confidence cues,
                and field-note guidance before saving reviewer notes/status as tester-created
                observations.</li>
                <li>Return to the same queue/request context, resubmit when needed to refresh
                progress, continue to the next record, and finish by copying the single manual
                feedback checklist.</li>
            </ol>
            <p>The browser pages do not create a saved review session, persisted queue state,
            second checklist, feedback persistence, live CCLD fetch, connector execution, or
            artifact building.</p>
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


def _render_retrieval_setup_required_page() -> str:
        return _page(
                title="Controlled CCLD retrieval setup required",
                heading="Controlled CCLD retrieval setup required",
            step_id="retrieve",
            next_action="Configure retrieval or show the current queue",
                main=f"""    <section aria-labelledby="retrieval-setup-heading">
            <h2 id="retrieval-setup-heading">No retrieval job was created</h2>
            <p>Controlled CCLD retrieval needs a database-backed request context, retrieval
            enablement, and configured server-side raw source storage before the browser can
            trigger a job.</p>
            <dl>
                <dt>What you entered</dt>
                <dd>The browser submitted a CCLD facility/date/type request.</dd>
                <dt>What happened</dt>
                <dd>The server blocked retrieval before creating a job because setup is
                incomplete.</dd>
                <dt>Records imported</dt>
                <dd>none</dd>
            </dl>
        </section>
        <details class="technical-details">
            <summary id="retrieval-setup-operator-heading">Operator setup checklist</summary>
            <ul>
                <li>Run PostgreSQL migrations, including the retrieval job metadata migration.</li>
                <li>Use PostgreSQL-backed page data for the hosted runtime.</li>
                <li>Enable controlled retrieval in host configuration.</li>
                <li>Configure a server-side raw artifact directory on persistent storage.</li>
                <li>Keep retrieval CCLD-only, complaint-only for now, and server-executed.</li>
            </ul>
            <p>No connector credentials or server-side private values are shown to the browser.</p>
        </details>
        <section aria-labelledby="retrieval-setup-next-heading">
            <h2 id="retrieval-setup-next-heading">What to do next</h2>
            <p>Return to the request page to review records that are already loaded, or ask an
            operator to configure controlled retrieval. If this message is confusing, send a bug
            report from the feedback page and include the facility/date/type request.</p>
            <p><a href="{CCLD_RECORD_REQUEST_PATH}">Return to CCLD request</a></p>
            <p><a href="{_FEEDBACK_PATH}">Send tester feedback</a></p>
        </section>""",
        )


def _render_record_type_options(selected_record_type: str) -> str:
    options: list[str] = []
    for record_type in SUPPORTED_RECORD_TYPES:
        selected = ' selected="selected"' if record_type == selected_record_type else ""
        options.append(
            f'                        <option value="{html.escape(record_type)}"{selected}>'
            f"{html.escape(RECORD_TYPE_LABELS[record_type])}</option>"
        )
    return "\n".join(options)


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
        number, supported record type, and valid bounded dates.</p>
        <section aria-labelledby="request-error-next-heading">
            <h3 id="request-error-next-heading">What to check next</h3>
            <ul>
                <li>Facility/license number must contain digits only.</li>
                <li>Record type must be complaint records or all supported record types.</li>
                <li>All supported record types currently means complaint records only.</li>
                <li>Start and end dates must use YYYY-MM-DD and stay within the allowed range.</li>
            </ul>
            <p>If the validation wording is confusing, use the feedback page to send a bug
            report or feature request with the facility/date/type values you tried.</p>
        </section>
      <p><a href="{CCLD_RECORD_REQUEST_PATH}">Return to CCLD request</a></p>
            <p><a href="{_FEEDBACK_PATH}">Send tester feedback</a></p>
    </section>""",
    )


def _render_request_result(
    request: CcldRecordRequest,
    result: CcldRequestSearchResult,
    *,
    state_summaries: Mapping[str, Mapping[str, Any]],
    import_reload_result: CcldImportReloadResult | None = None,
    import_reload_available: bool = False,
    retrieval_result: CcldRetrievalJobResult | None = None,
    retrieval_available: bool = False,
) -> str:
    reference_source = load_active_ccld_facility_reference()
    if result.matched_records:
        return _render_matched_result(
            request,
            result,
            state_summaries=state_summaries,
            import_reload_result=import_reload_result,
            import_reload_available=import_reload_available,
            retrieval_result=retrieval_result,
            retrieval_available=retrieval_available,
            reference_source=reference_source,
        )
    return _render_no_match_result(
        request,
        result,
        import_reload_result=import_reload_result,
        import_reload_available=import_reload_available,
        retrieval_result=retrieval_result,
        retrieval_available=retrieval_available,
        reference_source=reference_source,
    )


def _render_matched_result(
    request: CcldRecordRequest,
    result: CcldRequestSearchResult,
    *,
    state_summaries: Mapping[str, Mapping[str, Any]],
    import_reload_result: CcldImportReloadResult | None,
    import_reload_available: bool,
    retrieval_result: CcldRetrievalJobResult | None,
    retrieval_available: bool,
    reference_source: CcldFacilityReferenceSource,
) -> str:
    queue_items = _request_queue_items(result, state_summaries)
    decision_queue_items = _decision_sorted_queue_items(request, queue_items)
    filtered_queue_items = _filtered_queue_items(
        decision_queue_items, request.reviewer_status_filter
    )
    rows = "\n".join(_render_queue_row(request, item) for item in filtered_queue_items)
    if not rows:
        rows = _render_empty_filtered_queue_row(request)
    load_text = _load_status_text(import_reload_result)
    return _page(
        title="CCLD request results",
                heading="Retrieval result",
        step_id="review_results",
        next_action="Review imported records",
            main=f"""    {_render_result_focus_panel(request, result, retrieval_result, load_text)}
        {_render_request_case_brief(request, decision_queue_items, retrieval_result)}
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
    {_render_retrieval_job_summary(retrieval_result)}
        <section aria-labelledby="review-queue-heading">
            <h2 id="review-queue-heading">CCLD review queue</h2>
            <p>Open the suggested complaint first, then check source traceability on detail before adding reviewer-created notes/status.</p>
            {_render_queue_progress_summary(decision_queue_items)}
            {_render_queue_triage_summary(request, decision_queue_items)}
            {_render_queue_filter_form(request)}
            {_render_filtered_empty_recovery(request, decision_queue_items, filtered_queue_items)}
            {_render_worklist_decision_flow(request, decision_queue_items, filtered_queue_items, reference_source)}
            <p>Showing {len(filtered_queue_items)} of {len(decision_queue_items)} matching complaint
            record(s) for queue filter {_escape(_status_label(request.reviewer_status_filter))}.</p>
            <details class="technical-details">
            <summary>Table view and queue guidance</summary>
            {_render_queue_first_run_steps()}
            {_render_queue_navigation()}
            {_render_queue_continue_guidance(request, decision_queue_items)}
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
                        <th scope="col">Loaded record/source-confidence context</th>
          </tr>
        </thead>
        <tbody>
{rows}
        </tbody>
      </table>
      <p><a href="{REVIEWER_UI_RECORDS_PATH}">Open reviewer records</a></p>
            </details>
    </section>
                <details class="technical-details">
                    <summary>Copy details for feedback</summary>
                {_render_feedback_checklist_section(
                        request,
                        decision_queue_items,
                        import_reload_result=import_reload_result,
                        matching_source_record_count=len(result.matched_records),
                        local_facility_record_count=len(result.all_facility_records),
                    reference_source=reference_source,
                )}
        {_render_feedback_guidance_section()}
                </details>
                <details class="technical-details">
                    <summary>Advanced retrieval and local load actions</summary>
        {_render_retrieval_action(request, retrieval_available)}
        {_render_import_reload_action(request, import_reload_available, refresh=True)}
    {_render_pipeline_plan(request)}
                </details>""",
    )


def _render_result_focus_panel(
    request: CcldRecordRequest,
    result: CcldRequestSearchResult,
    retrieval_result: CcldRetrievalJobResult | None,
    load_text: str,
) -> str:
    imported_count = (
        retrieval_result.result_counts.get("imported_source_derived_records", 0)
        if retrieval_result is not None
        else len(result.matched_records)
    )
    if retrieval_result is not None and imported_count > 0:
        headline = "Complaint records ready for attorney review"
    else:
        headline = "Complaint records ready for attorney review"
    mode_label = (
        _retrieval_mode_label_from_message(retrieval_result.safe_message)
        if retrieval_result is not None
        else _runtime_mode_label()
    )
    detail_link = ""
    if retrieval_result is not None:
        detail_link = (
            f'<a class="button button-secondary" href="{_escape(_retrieval_job_detail_href(retrieval_result.retrieval_job_id))}">View job details</a>'
        )
    return f"""<section class="hero-card" aria-labelledby="request-result-heading">
      <p class="stage-kicker">Result</p>
      <h2 id="request-result-heading">{_escape(headline)}</h2>
      <p><span class="{_mode_badge_class(mode_label)}">{_escape(mode_label)}</span></p>
      <p>{_escape(_request_execution_boundary_text(retrieval_result))}</p>
            <div class="metric-strip" aria-label="Retrieval result summary">
                <div class="metric-card"><strong>{imported_count}</strong><span>Records imported</span></div>
                <div class="metric-card"><strong>{len(result.matched_records)}</strong><span>Rows ready in queue</span></div>
                <div class="metric-card"><strong>{_escape(_date_scope_text(request))}</strong><span>Complaint date range</span></div>
            </div>
            <dl class="summary-list">
                <dt>Facility/license number</dt>
                <dd>{_escape(request.facility_number)}</dd>
                <dt>Load state</dt>
                <dd>{_escape(load_text)}</dd>
            </dl>
            <details class="technical-details secondary-actions">
                <summary>Other result actions</summary>
                {detail_link}
                <p><a href="{CCLD_RECORD_REQUEST_PATH}">Run another retrieval</a></p>
                <p><a href="{_FEEDBACK_PATH}">Send feedback</a></p>
            </details>
    </section>"""


def _render_no_match_result(
    request: CcldRecordRequest,
    result: CcldRequestSearchResult,
    *,
    import_reload_result: CcldImportReloadResult | None,
    import_reload_available: bool,
    retrieval_result: CcldRetrievalJobResult | None,
    retrieval_available: bool,
    reference_source: CcldFacilityReferenceSource,
) -> str:
    local_count = len(result.all_facility_records)
    headline = _no_match_headline(retrieval_result, local_count)
    primary_action = _no_match_primary_action(retrieval_result)
    return _page(
                title=headline,
                heading=headline,
                step_id="review_results",
                next_action="Adjust the request or view job details",
                main=f"""    {_render_no_match_recovery_panel(request, headline, local_count, retrieval_result, primary_action)}
        {_render_request_context_confirmation(
                facility_number=request.facility_number,
                start_date=request.start_date,
                end_date=request.end_date,
                request_context_origin=request.request_context_origin,
                lookup_facility_name=request.lookup_facility_name,
                reference_source=reference_source,
                include_change_links=True,
            )}
        <details class="technical-details">
            <summary>Technical retrieval details</summary>
        {_render_no_match_guidance(request, local_count, import_reload_result, retrieval_result)}
        {_render_import_reload_summary(import_reload_result)}
        {_render_retrieval_job_summary(retrieval_result)}
        </details>
        <details class="technical-details">
            <summary>Copy details for feedback</summary>
                {_render_feedback_checklist_section(
                        request,
                        (),
                        import_reload_result=import_reload_result,
                        matching_source_record_count=0,
                        local_facility_record_count=local_count,
                reference_source=reference_source,
                )}
        </details>
        <details class="technical-details">
            <summary>Advanced local/operator actions</summary>
        {_render_import_reload_action(request, import_reload_available, refresh=False)}
        {_render_retrieval_action(request, retrieval_available)}
    {_render_pipeline_plan(request)}
        </details>""",
    )


def _render_no_match_recovery_panel(
    request: CcldRecordRequest,
    headline: str,
    local_count: int,
    retrieval_result: CcldRetrievalJobResult | None,
    primary_action: str,
) -> str:
    reason_bucket = _no_match_reason_bucket(retrieval_result, local_count)
    return f"""<section class="hero-card recovery-panel" aria-labelledby="no-local-records-heading">
      <p class="stage-kicker">Recovery</p>
      <h2 id="no-local-records-heading">{_escape(headline)}</h2>
      <dl>
        <dt>What happened</dt>
        <dd>{_escape(reason_bucket)}</dd>
        <dt>Facility/license number</dt>
        <dd>{_escape(request.facility_number)}</dd>
        <dt>Date range</dt>
        <dd>{_escape(_date_scope_text(request))}</dd>
        <dt>Rows available before date filtering</dt>
        <dd>{local_count}</dd>
                <dt>What this does not prove</dt>
        <dd>This does not prove no complaints exist, source coverage is complete, or any legal or facility-wide conclusion.</dd>
      </dl>
            <p><strong>Recommended next action:</strong> Confirm the facility/date context, then use the action below.</p>
      <p>{primary_action}</p>
    </section>"""


def _no_match_reason_bucket(
    retrieval_result: CcldRetrievalJobResult | None,
    local_count: int,
) -> str:
    if retrieval_result is None:
        if local_count > 0:
            return "Loaded records exist for this facility, but none matched the selected date range."
        return "No loaded records are available for this facility/date request yet."
    if retrieval_result.job_state == "blocked_by_validation":
        return "The request was blocked by validation before retrieval."
    if retrieval_result.job_state == "failed":
        return "Retrieval stopped safely because a source, network, or server-side issue occurred."
    if retrieval_result.job_state == "rate_limited":
        return "Retrieval is temporarily rate-limited for this tester."
    if retrieval_result.result_counts.get("selected_report_candidates", 0) == 0:
        return "No complaint candidates matched the selected date range."
    if retrieval_result.result_counts.get("retrieved_record_bundles", 0) > 0:
        return "CCLD records were fetched, but no imported complaint rows matched this request after validation."
    return "The retrieval completed without importing matching complaint records."


def _no_match_headline(
    retrieval_result: CcldRetrievalJobResult | None,
    local_count: int,
) -> str:
    if retrieval_result is None:
        if local_count > 0:
            return "Candidates may be outside the selected date range"
        return "No loaded complaint records match this request yet"
    imported_count = retrieval_result.result_counts.get("imported_source_derived_records", 0)
    if imported_count > 0:
        return "Imported records need a queue refresh"
    return _retrieval_result_headline(retrieval_result, imported_count)


def _no_match_primary_action(result: CcldRetrievalJobResult | None) -> str:
    if result is None:
        return f'<a class="button" href="{CCLD_RECORD_REQUEST_PATH}">Adjust date range</a>'
    if result.job_state in {"failed", "completed_with_warnings"}:
        return f'<a class="button" href="{_escape(_retrieval_job_detail_href(result.retrieval_job_id))}">View job details</a>'
    if result.job_state == "blocked_by_validation":
        return f'<a class="button" href="{CCLD_RECORD_REQUEST_PATH}">Adjust request</a>'
    return f'<a class="button" href="{_FEEDBACK_PATH}">Send feedback</a>'


def _render_pipeline_plan(request: CcldRecordRequest) -> str:
    live_fetch_command = (
        ".\\scripts\\run-ccld-live-fetch.ps1 "
        f"-FacilityNumber {_escape(request.facility_number)} "
        "-Limit 1 -MaxRequests 5"
    )
    return f"""<section class="quiet-section" aria-labelledby="pipeline-plan-heading">
            <details>
            <summary id="pipeline-plan-heading">Technical preparation path</summary>
            <p>When controlled retrieval is configured, use the browser retrieval action on
            this page for a bounded CCLD facility/date/type request. When controlled
            retrieval is not configured or a separate SQLite/Datasette validation run is
            needed, use the existing explicit CCLD pipeline outside the hosted UI.</p>
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
                <p>The browser remains a trigger only. Server-side retrieval, raw preservation,
                extraction, validation, and import happen only when controlled retrieval is
                explicitly configured; SQLite conversion remains outside the browser path.</p>
            </details>
        </section>"""


def _render_no_match_guidance(
    request: CcldRecordRequest,
    local_facility_record_count: int,
    import_reload_result: CcldImportReloadResult | None,
    retrieval_result: CcldRetrievalJobResult | None,
) -> str:
    date_scope = _date_scope_text(request)
    load_state = _no_match_load_state(import_reload_result)
    return f"""    <section aria-labelledby="no-match-guidance-heading">
            <h2 id="no-match-guidance-heading">How to interpret this no-match result</h2>
            <p>{_escape(_request_execution_boundary_text(retrieval_result))}</p>
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


def _request_execution_boundary_text(
    retrieval_result: CcldRetrievalJobResult | None,
) -> str:
    if retrieval_result is None:
        return (
            "This page searched currently loaded local/test source-derived rows only. It did not "
            "submit a controlled retrieval job for this request."
        )
    return (
        "The browser triggered a controlled server-side CCLD retrieval job. The browser did "
        "not scrape, fetch source pages directly, run SQLite conversion, receive connector "
        "credentials, or receive raw artifact paths."
    )


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
                <input type="hidden" name="record_type" value="{_escape(request.record_type)}">
                <input type="hidden" name="start_date" value="{_escape(request.start_date or '')}">
                <input type="hidden" name="end_date" value="{_escape(request.end_date or '')}">
                <input type="hidden" name="reviewer_status_filter"
                    value="{_escape(request.reviewer_status_filter)}">
                <input type="hidden" name="{_IMPORT_RELOAD_ACTION_FIELD}"
                    value="{_IMPORT_RELOAD_ACTION_VALUE}">
                <p><button type="submit">{_escape(button_label)}</button></p>
            </form>
        </section>"""


def _render_retrieval_job_summary(result: CcldRetrievalJobResult | None) -> str:
    if result is None:
        return ""
    count_items = "\n".join(
        f"                <dt>{_escape(_count_label(name))}</dt>\n"
        f"                <dd>{count}</dd>"
        for name, count in sorted(result.result_counts.items())
    )
    if not count_items:
        count_items = "                <dt>Result counts</dt>\n                <dd>none</dd>"
    warning_items = _safe_list_items(result.warnings) or "        <li>none</li>"
    error_items = _safe_list_items(result.errors) or "        <li>none</li>"
    queue_link = ""
    imported_count = result.result_counts.get("imported_source_derived_records", 0)
    mode_label = _retrieval_mode_label_from_message(result.safe_message)
    headline = _retrieval_result_headline(result, imported_count)
    status_class = _status_badge_class(result.job_state)
    mode_class = _mode_badge_class(mode_label)
    stat_grid = _render_retrieval_count_grid(result.result_counts, imported_count)
    if result.job_state in {"completed", "completed_with_warnings"} and imported_count > 0:
        queue_link = (
            f'            <p><a class="button" href="{CCLD_RECORD_REQUEST_PATH}?'
            f'facility_number={_escape(result.facility_number)}&amp;'
            f'start_date={_escape(result.start_date)}&amp;'
            f'end_date={_escape(result.end_date)}&amp;'
            f'record_type={_escape(result.record_type)}">'
            "Open review queue</a></p>"
        )
    detail_href = _retrieval_job_detail_href(result.retrieval_job_id)
    return f"""    <section class="hero-card" aria-labelledby="retrieval-job-summary-heading">
            <h2 id="retrieval-job-summary-heading">{_escape(headline)}</h2>
            <p><span class="{status_class}">{_escape(_retrieval_state_label(result.job_state))}</span>
            <span class="{mode_class}">{_escape(mode_label)}</span></p>
            <p>{_escape(_retrieval_state_intro(result))}</p>
                        <details class="technical-details">
                            <summary>Technical job details</summary>
            {stat_grid}
                        <dl>
                <dt>Job state</dt>
                <dd>{_escape(_retrieval_state_label(result.job_state))}</dd>
                <dt>Machine-readable state</dt>
                <dd>{_escape(result.job_state)}</dd>
                <dt>Status message</dt>
                <dd>{_escape(result.safe_message)}</dd>
                <dt>Retrieval mode</dt>
                <dd>{_escape(mode_label)}</dd>
                <dt>Retrieval job ID</dt>
                <dd>{_escape(result.retrieval_job_id)}</dd>
                <dt>Facility/license number</dt>
                <dd>{_escape(result.facility_number)}</dd>
                <dt>Record type</dt>
                <dd>{_escape(RECORD_TYPE_LABELS.get(result.record_type, result.record_type))}</dd>
                <dt>Date range</dt>
                <dd>{_escape(result.start_date)} to {_escape(result.end_date)}</dd>
                <dt>Retrieval job created</dt>
                <dd>yes</dd>
                <dt>Records imported</dt>
                <dd>{imported_count}</dd>
{count_items}
            </dl>
            <h3>Safe warnings</h3>
            <ul>
{warning_items}
            </ul>
            <h3>Safe errors</h3>
            <ul>
{error_items}
            </ul>
            <p>The browser triggered this job only. Server-side retrieval preserved raw
            artifacts, computed hashes, validated records, and imported source-derived rows
            when the job completed. No connector credentials or server-side private values
            are shown.</p>
            </details>
            {_render_retrieval_next_steps(result, imported_count)}
                <p><a class="button button-secondary" href="{_escape(detail_href)}">View job details</a></p>
                <p><a href="{CCLD_RETRIEVAL_JOBS_PATH}">View retrieval job history</a></p>
{queue_link}
        </section>"""


def _retrieval_result_headline(result: CcldRetrievalJobResult, imported_count: int) -> str:
    if result.job_state in {"completed", "completed_with_warnings"} and imported_count > 0:
        return "Complaint records ready for attorney review"
    if result.job_state == "completed_with_warnings":
        warning_text = " ".join(result.warnings).casefold()
        if "inside the requested date range" in warning_text:
            return "Complaint candidates were outside the date range"
        if "no complaint" in warning_text or "no report" in warning_text:
            return "No complaint candidates found for this request"
        if result.result_counts.get("retrieved_record_bundles", 0) > 0:
            return "Fetched records did not produce matching imported rows"
        return "No records imported; review warnings for the next step"
    if result.job_state == "failed":
        return "Source or network issue stopped retrieval safely"
    if result.job_state == "blocked_by_validation":
        return "Request needs changes before retrieval"
    if result.job_state == "rate_limited":
        return "Retrieval is temporarily rate limited"
    if result.job_state in {"queued", "running"}:
        return "Retrieval job is in progress"
    return "Retrieval result needs review"


def _render_retrieval_count_grid(counts: Mapping[str, int], imported_count: int) -> str:
    values = (
        ("Records imported", imported_count),
        ("Discovered candidates", counts.get("discovered_report_candidates", 0)),
        ("Selected candidates", counts.get("selected_report_candidates", 0)),
        ("Retrieved bundles", counts.get("retrieved_record_bundles", 0)),
        ("Matched bundles", counts.get("matched_record_bundles", 0)),
        ("Imported rows", counts.get("imported_source_derived_records", 0)),
        ("Failures", counts.get("failed_record_bundles", 0)),
    )
    cards = "\n".join(
        f"        <div class=\"stat-card\"><strong>{count}</strong><span>{_escape(label)}</span></div>"
        for label, count in values
    )
    return f"""      <div class="stat-grid" aria-label="Retrieval result counts">
{cards}
      </div>"""


def _status_badge_class(state: str) -> str:
    if state == "completed":
        return "badge badge-live"
    if state == "completed_with_warnings":
        return "badge badge-warning"
    if state in {"failed", "blocked_by_validation", "rate_limited"}:
        return "badge badge-danger"
    return "badge badge-muted"


def _retrieval_state_intro(result: CcldRetrievalJobResult) -> str:
    if result.job_state == "completed":
        return "Controlled CCLD retrieval completed and imported validated records."
    if result.job_state == "completed_with_warnings":
        return "Controlled CCLD retrieval completed with warnings; review the counts below."
    if result.job_state == "failed":
        return "Controlled CCLD retrieval failed safely; no raw details are shown here."
    if result.job_state == "blocked_by_validation":
        return "Controlled CCLD retrieval was blocked by validation before import."
    if result.job_state == "rate_limited":
        return "Controlled CCLD retrieval was rate-limited for this tester."
    if result.job_state == "running":
        return "Controlled CCLD retrieval is running on the server."
    if result.job_state == "queued":
        return "Controlled CCLD retrieval is queued for server-side work."
    return result.safe_message


def _retrieval_state_label(state: str) -> str:
    labels = {
        "queued": "Queued",
        "running": "Running",
        "completed": "Completed",
        "completed_with_warnings": "Completed with warnings",
        "failed": "Failed",
        "blocked_by_validation": "Blocked by validation",
        "rate_limited": "Rate limited",
    }
    return labels.get(state, state)


def _retrieval_mode_label_from_message(message: str) -> str:
    normalized = message.casefold()
    if "fixture/mock mode" in normalized:
        return "Fixture/mock demo"
    if "live public ccld mode" in normalized:
        return "Live public CCLD"
    return "Not recorded"


def _render_retrieval_next_steps(result: CcldRetrievalJobResult, imported_count: int) -> str:
    if result.job_state == "completed" and imported_count > 0:
        message = "Open the imported records in the queue and review source traceability."
    elif result.job_state == "completed_with_warnings" and imported_count > 0:
        message = "Review imported records, then include warning details if sending feedback."
    elif result.job_state == "completed_with_warnings":
        message = "No records were imported; check warnings and adjust the request if needed."
    elif result.job_state == "failed":
        message = (
            "Retry later or ask an operator to inspect server logs without sharing "
            "private values."
        )
    elif result.job_state == "blocked_by_validation":
        message = "Change the facility/date/type request before retrying retrieval."
    elif result.job_state == "rate_limited":
        message = "Wait for an active retrieval job to finish before trying again."
    elif result.job_state == "running":
        message = "Refresh the request status later; do not resubmit repeatedly."
    else:
        message = "Wait for the server-side job to start, then refresh status later."
    return f"""            <section aria-labelledby="retrieval-next-steps-heading">
              <h3 id="retrieval-next-steps-heading">What to do next</h3>
              <p>{_escape(message)}</p>
              <p>If the status, counts, or next step is confusing, use the feedback page for a
              bug report or feature request. For a new source request, use the new data source
              feedback type; do not put source credentials or private values in feedback.</p>
              <p><a href="{_FEEDBACK_PATH}">Send tester feedback</a></p>
            </section>"""


def _retrieval_job_history_response(
    context: CcldRecordRequestUiContext,
) -> tuple[int, str]:
    source_context = context.reviewer_ui_context.workflow_shell_context.source_derived_api_context
    try:
        jobs = list_recent_ccld_retrieval_jobs(
            source_context.connection,
            source_context.actor,
            scope=source_context.scope,
        )
    except HostedAuthenticationRequiredError as error:
        return 401, _render_retrieval_history_blocked_page(str(error))
    except (HostedAccountDisabledError, HostedRoleDeniedError, HostedScopeDeniedError) as error:
        return 403, _render_retrieval_history_blocked_page(str(error))
    return 200, _render_retrieval_job_history_page(
        jobs,
        retrieval_configured=context.retrieval_context is not None,
    )


def _render_retrieval_history_blocked_page(message: str) -> str:
    return _render_message_page(
        title="Retrieval job history requires access",
        heading="Retrieval job history requires access",
        message=message,
        guidance=(
            "Sign in with an allowed tester or operator account before viewing controlled "
            "CCLD retrieval job history."
        ),
        links=(("Return to CCLD request", CCLD_RECORD_REQUEST_PATH),),
    )


def _render_retrieval_job_history_page(
    jobs: tuple[CcldRetrievalJobHistoryEntry, ...],
    *,
    retrieval_configured: bool,
) -> str:
    rows = "\n".join(_render_retrieval_history_row(job) for job in jobs)
    job_cards = "\n".join(_render_retrieval_history_card(job) for job in jobs)
    if not rows:
        rows = """        <tr>
          <td colspan="9">No retrieval jobs have been submitted for this authorized scope.</td>
        </tr>"""
        job_cards = f"""        <article class="empty-state-card result-card">
                    <div>
                        <h3>No retrieval jobs yet</h3>
                        <p>No retrieval jobs have been submitted for this authorized scope.</p>
                    </div>
                    <p><a class="button" href="{CCLD_RECORD_REQUEST_PATH}">Submit retrieval request</a></p>
                </article>"""
    setup_text = (
        "Controlled retrieval is configured for this runtime."
        if retrieval_configured
        else (
            "Controlled retrieval setup is missing for this runtime. Existing job history can "
            "still be read when metadata exists, but new jobs cannot be submitted until an "
            "operator enables retrieval and server-side raw source storage."
        )
    )
    return _page(
        title="Retrieval status center",
        heading="Retrieval status center",
        active_path=CCLD_RETRIEVAL_JOBS_PATH,
        step_id="review_results",
        next_action="Open a job, review records, or adjust the request",
                main=f"""    <section class="hero-card" aria-labelledby="retrieval-history-purpose-heading">
      <p class="launch-kicker">Retrieval status center</p>
      <h2 id="retrieval-history-purpose-heading">Track complaint retrieval jobs</h2>
      <p>This page shows recent controlled CCLD retrieval jobs with facility/date context,
      imported-record counts, warnings/errors, and the next action for review.</p>
            <p><a class="button" href="{CCLD_RECORD_REQUEST_PATH}">Submit or change retrieval request</a></p>
            <details class="technical-details">
                <summary>Runtime and boundary details</summary>
                <p>{_escape(setup_text)}</p>
                <p>Job states are workflow states. They do not prove public-source completeness,
                legal conclusions, facility-wide conclusions, or harm conclusions.</p>
            </details>
    </section>
        {_render_retrieval_history_summary(jobs)}
    <section aria-labelledby="retrieval-history-table-heading">
        <h2 id="retrieval-history-table-heading">Job list</h2>
            <div class="result-list" aria-label="Retrieval jobs">
{job_cards}
            </div>
            <details class="technical-details">
                <summary>Table view</summary>
      <table>
        <caption>Recent controlled CCLD retrieval jobs and safe status summaries</caption>
        <thead>
          <tr>
            <th scope="col">Job and state</th>
            <th scope="col">Requested facility/date/type</th>
            <th scope="col">Timestamps</th>
            <th scope="col">Records imported</th>
            <th scope="col">Status message</th>
            <th scope="col">Safe warnings</th>
            <th scope="col">Safe errors</th>
            <th scope="col">Raw/source artifact status</th>
            <th scope="col">Next step</th>
          </tr>
        </thead>
        <tbody>
{rows}
        </tbody>
      </table>
            </details>
    </section>
        <details class="technical-details">
            <summary id="retrieval-history-help-heading">What to do if a job looks wrong</summary>
      <p>For failed, blocked, warning, or confusing jobs, use the safe state, count, and
      message shown here first. Operators can check server logs without sharing private
      values. Testers can send feedback with the facility/date/type request and the visible
      job state.</p>
      <p><a href="{_FEEDBACK_PATH}">Send tester feedback</a></p>
      <p><a href="{CCLD_HELP_PATH}">Read CCLD workflow help</a></p>
        </details>""",
    )


def _render_retrieval_history_summary(
    jobs: tuple[CcldRetrievalJobHistoryEntry, ...],
) -> str:
    imported_total = sum(
        job.result_counts.get("imported_source_derived_records", 0) for job in jobs
    )
    warning_total = sum(len(job.warnings) for job in jobs)
    failure_total = sum(1 for job in jobs if job.job_state in {"failed", "rate_limited"})
    cards = "\n".join(
        f"        <div class=\"stat-card\"><strong>{count}</strong><span>{_escape(label)}</span></div>"
        for label, count in (
            ("Recent jobs", len(jobs)),
            ("Records imported", imported_total),
            ("Warnings", warning_total),
            ("Failures", failure_total),
        )
    )
    return f"""    <section aria-labelledby="retrieval-status-summary-heading">
      <h2 id="retrieval-status-summary-heading">Status summary</h2>
      <div class="stat-grid">
{cards}
      </div>
    </section>"""


def _render_retrieval_history_card(job: CcldRetrievalJobHistoryEntry) -> str:
        imported_count = job.result_counts.get("imported_source_derived_records", 0)
        detail_href = _retrieval_job_detail_href(job.retrieval_job_id)
        mode_label = _retrieval_mode_label_from_message(job.safe_message)
        return f"""        <article class="result-card work-item" aria-labelledby="job-{_escape(job.retrieval_job_id)}-heading">
                    <div>
                        <p><span class="{_status_badge_class(job.job_state)}">{_escape(_retrieval_state_label(job.job_state))}</span>
                        <span class="{_mode_badge_class(mode_label)}">{_escape(mode_label)}</span></p>
                        <h3 id="job-{_escape(job.retrieval_job_id)}-heading">Facility {_escape(job.facility_number)} retrieval</h3>
                        <dl>
                            <dt>Date range</dt>
                            <dd>{_escape(job.start_date)} to {_escape(job.end_date)}</dd>
                            <dt>Records imported</dt>
                            <dd>{imported_count}</dd>
                            <dt>Warning/error summary</dt>
                            <dd>{len(job.warnings)} warning(s); {len(job.errors)} error(s)</dd>
                            <dt>Status message</dt>
                            <dd>{_escape(job.safe_message)}</dd>
                        </dl>
                    </div>
                      <div>{_render_history_next_step(job, imported_count)}</div>
                    <p><a class="button button-secondary" href="{_escape(detail_href)}">View job details</a></p>
                </article>"""


def _render_retrieval_history_row(job: CcldRetrievalJobHistoryEntry) -> str:
    imported_count = job.result_counts.get("imported_source_derived_records", 0)
    detail_href = _retrieval_job_detail_href(job.retrieval_job_id)
    return f"""        <tr>
          <td>
            <p><a href="{_escape(detail_href)}">View retrieval job details</a></p>
            <p>{_escape(job.retrieval_job_id)}</p>
            <dl>
              <dt>Job state</dt>
              <dd>{_escape(_retrieval_state_label(job.job_state))}</dd>
              <dt>Machine-readable state</dt>
              <dd>{_escape(job.job_state)}</dd>
                            <dt>Retrieval mode</dt>
                            <dd>{_escape(_retrieval_mode_label_from_message(job.safe_message))}</dd>
            </dl>
          </td>
          <td>
            <dl>
              <dt>Facility/license number</dt>
              <dd>{_escape(job.facility_number)}</dd>
              <dt>Record type</dt>
              <dd>{_escape(RECORD_TYPE_LABELS.get(job.record_type, job.record_type))}</dd>
              <dt>Date range</dt>
              <dd>{_escape(job.start_date)} to {_escape(job.end_date)}</dd>
            </dl>
          </td>
          <td>
            <dl>
              <dt>Created at</dt>
              <dd>{_escape(job.created_at)}</dd>
              <dt>Started timestamp</dt>
              <dd>not separately tracked in this first slice</dd>
              <dt>Completed or last updated at</dt>
              <dd>{_escape(_completed_or_updated_text(job))}</dd>
            </dl>
          </td>
          <td>{imported_count}</td>
          <td>{_escape(job.safe_message)}</td>
          <td>{_render_history_message_list(job.warnings)}</td>
          <td>{_render_history_message_list(job.errors)}</td>
          <td>{_escape(_raw_artifact_status(job))}</td>
          <td>{_render_history_next_step(job, imported_count)}</td>
        </tr>"""


def _retrieval_job_detail_response(
    context: CcldRecordRequestUiContext,
    query: str,
) -> tuple[int, str]:
    query_values = parse_qs(query, keep_blank_values=True)
    retrieval_job_id = _safe_retrieval_job_id(_first_form_value(query_values, "job_id"))
    if retrieval_job_id is None:
        return 400, _render_retrieval_job_detail_invalid_page()
    source_context = context.reviewer_ui_context.workflow_shell_context.source_derived_api_context
    try:
        job = get_ccld_retrieval_job(
            source_context.connection,
            source_context.actor,
            scope=source_context.scope,
            retrieval_job_id=retrieval_job_id,
        )
    except HostedAuthenticationRequiredError as error:
        return 401, _render_retrieval_history_blocked_page(str(error))
    except (HostedAccountDisabledError, HostedRoleDeniedError, HostedScopeDeniedError) as error:
        return 403, _render_retrieval_history_blocked_page(str(error))
    if job is None:
        return 404, _render_retrieval_job_detail_not_found_page()
    return 200, _render_retrieval_job_detail_page(job)


def _safe_retrieval_job_id(value: str) -> str | None:
    if not value or len(value) > 96:
        return None
    if not re.match(r"^[A-Za-z0-9_.:-]+$", value):
        return None
    return value


def _render_retrieval_job_detail_invalid_page() -> str:
    return _render_message_page(
        title="Retrieval job detail needs a valid job ID",
        heading="Retrieval job detail needs a valid job ID",
        message="The retrieval job detail page needs a valid job ID from the history page.",
        guidance="Open retrieval job history and choose a job detail link.",
        links=(
            ("Return to retrieval job history", CCLD_RETRIEVAL_JOBS_PATH),
            ("Return to CCLD request", CCLD_RECORD_REQUEST_PATH),
        ),
        active_path=CCLD_RETRIEVAL_JOBS_PATH,
    )


def _render_retrieval_job_detail_not_found_page() -> str:
    return _render_message_page(
        title="Retrieval job detail not found",
        heading="Retrieval job detail not found",
        message="No retrieval job metadata matched that job ID in this authorized scope.",
        guidance=(
            "Return to retrieval job history to choose a recent job. This is a metadata "
            "lookup state, not a public-source conclusion."
        ),
        links=(
            ("Return to retrieval job history", CCLD_RETRIEVAL_JOBS_PATH),
            ("Submit or change a CCLD request", CCLD_RECORD_REQUEST_PATH),
        ),
        active_path=CCLD_RETRIEVAL_JOBS_PATH,
    )


def _render_retrieval_job_detail_page(job: CcldRetrievalJobHistoryEntry) -> str:
    imported_count = job.result_counts.get("imported_source_derived_records", 0)
    count_items = _render_detail_count_items(job.result_counts)
    count_cards = _render_retrieval_count_grid(job.result_counts, imported_count)
    warning_items = _safe_list_items(job.warnings) or "        <li>none</li>"
    error_items = _safe_list_items(job.errors) or "        <li>none</li>"
    mode_label = _retrieval_mode_label_from_message(job.safe_message)
    return _page(
        title="Retrieval job detail",
        heading="Retrieval job detail",
        active_path=CCLD_RETRIEVAL_JOBS_PATH,
        step_id="review_results",
        next_action="Review imported records or adjust the request",
                main=f"""    <section class="hero-card" aria-labelledby="retrieval-detail-summary-heading">
    <p class="launch-kicker">Retrieval job</p>
    <h2 id="retrieval-detail-summary-heading">Job summary and next step</h2>
            <p><span class="{_status_badge_class(job.job_state)}">{_escape(_retrieval_state_label(job.job_state))}</span>
            <span class="{_mode_badge_class(mode_label)}">{_escape(mode_label)}</span></p>
      <p>This read-only page shows one controlled CCLD retrieval job from existing
      operational metadata. It is not an audit export, raw artifact viewer, scheduler,
      or source-completeness report.</p>
      <p>{_escape(_retrieval_state_intro_for_history(job))}</p>
    <dl class="summary-list">
        <dt>Job state</dt>
        <dd>{_escape(_retrieval_state_label(job.job_state))}</dd>
        <dt>Status message</dt>
        <dd>{_escape(job.safe_message)}</dd>
        <dt>Retrieval mode</dt>
        <dd>{_escape(_retrieval_mode_label_from_message(job.safe_message))}</dd>
        <dt>Facility/license number</dt>
        <dd>{_escape(job.facility_number)}</dd>
        <dt>Record type</dt>
        <dd>{_escape(RECORD_TYPE_LABELS.get(job.record_type, job.record_type))}</dd>
        <dt>Date range</dt>
        <dd>{_escape(job.start_date)} to {_escape(job.end_date)}</dd>
        <dt>Records imported</dt>
        <dd>{imported_count}</dd>
      </dl>
    </section>
        {_render_retrieval_detail_next_steps(job, imported_count)}
    <details class="technical-details">
    <summary>Technical counts, warnings, and errors</summary>
    <section aria-labelledby="retrieval-detail-counts-heading">
      <h2 id="retrieval-detail-counts-heading">Result counts</h2>
            {count_cards}
      <dl>
      <dt>Retrieval job ID</dt>
      <dd>{_escape(job.retrieval_job_id)}</dd>
      <dt>Machine-readable state</dt>
      <dd>{_escape(job.job_state)}</dd>
      <dt>Created at</dt>
      <dd>{_escape(job.created_at)}</dd>
      <dt>Started timestamp</dt>
      <dd>not separately tracked in this first slice</dd>
      <dt>Last updated at</dt>
      <dd>{_escape(job.updated_at)}</dd>
      <dt>Completed timestamp</dt>
      <dd>{_escape(_completed_timestamp_text(job))}</dd>
      <dt>Raw artifact preservation</dt>
      <dd>{_escape(_raw_artifact_status(job))}</dd>
{count_items}
      </dl>
    </section>
    <section aria-labelledby="retrieval-detail-warning-heading">
      <h2 id="retrieval-detail-warning-heading">Safe warnings</h2>
      <ul>
{warning_items}
      </ul>
    </section>
    <section aria-labelledby="retrieval-detail-error-heading">
      <h2 id="retrieval-detail-error-heading">Safe errors</h2>
      <ul>
{error_items}
      </ul>
    </section>
    <section aria-labelledby="retrieval-detail-boundary-heading">
      <h2 id="retrieval-detail-boundary-heading">Display boundary</h2>
      <p>This page does not show raw source narrative content, raw artifact file contents,
      provider identifiers, private configuration values, raw stack traces, or server-specific
      raw paths. Raw artifacts remain server-side.</p>
        </section>
        </details>""",
    )


def _render_detail_count_items(counts: Mapping[str, int]) -> str:
    if not counts:
        return "        <dt>Result counts</dt>\n        <dd>none</dd>"
    return "\n".join(
        f"        <dt>{_escape(_count_label(name))}</dt>\n        <dd>{count}</dd>"
        for name, count in sorted(counts.items())
    )


def _retrieval_state_intro_for_history(job: CcldRetrievalJobHistoryEntry) -> str:
    result = CcldRetrievalJobResult(
        retrieval_job_id=job.retrieval_job_id,
        job_state=job.job_state,
        facility_number=job.facility_number,
        record_type=job.record_type,
        start_date=job.start_date,
        end_date=job.end_date,
        source_artifact_identity=job.source_artifact_identity,
        result_counts=job.result_counts,
        warnings=job.warnings,
        errors=job.errors,
        safe_message=job.safe_message,
    )
    return _retrieval_state_intro(result)


def _completed_timestamp_text(job: CcldRetrievalJobHistoryEntry) -> str:
    if job.job_state in {"queued", "running"}:
        return "not completed yet"
    return job.updated_at


def _render_retrieval_detail_next_steps(
    job: CcldRetrievalJobHistoryEntry,
    imported_count: int,
) -> str:
    queue_link = _retrieval_history_queue_link(job) if imported_count > 0 else ""
    if job.job_state == "completed" and imported_count > 0:
        message = "Open imported records in the CCLD queue and review source traceability."
    elif job.job_state == "completed_with_warnings" and imported_count > 0:
        message = "Review imported records, then include warning details if sending feedback."
    elif job.job_state == "completed_with_warnings":
        message = "No records were imported. Review warnings and adjust the request if needed."
    elif job.job_state == "failed":
        message = (
            "Retry later or ask an operator to inspect server logs without sharing "
            "private values."
        )
    elif job.job_state == "blocked_by_validation":
        message = "Change the facility/date/type request before retrying retrieval."
    elif job.job_state == "rate_limited":
        message = "Wait for an active retrieval job to finish before trying again."
    elif job.job_state == "running":
        message = "Refresh job history later; do not resubmit repeatedly."
    else:
        message = "Wait for the server-side job to start, then refresh job history later."
    return f"""    <section aria-labelledby="retrieval-detail-next-heading">
      <h2 id="retrieval-detail-next-heading">What to do next</h2>
      <p>{_escape(message)}</p>
      {queue_link}
      <ul>
        <li><a href="{CCLD_RETRIEVAL_JOBS_PATH}">Return to retrieval job history</a></li>
        <li><a href="{CCLD_RECORD_REQUEST_PATH}">Submit or change a CCLD record request</a></li>
        <li><a href="{CCLD_HELP_PATH}">Read CCLD workflow help</a></li>
        <li><a href="{_FEEDBACK_PATH}">Send tester feedback</a></li>
      </ul>
    </section>"""


def _render_history_message_list(values: tuple[str, ...]) -> str:
    items = _safe_list_items(values) or "        <li>none</li>"
    return f"<ul>\n{items}\n            </ul>"


def _completed_or_updated_text(job: CcldRetrievalJobHistoryEntry) -> str:
    if job.job_state in {"queued", "running"}:
        return f"not completed yet; last updated {job.updated_at}"
    return job.updated_at


def _raw_artifact_status(job: CcldRetrievalJobHistoryEntry) -> str:
    if job.source_artifact_identity:
        return "raw artifact preserved; source artifact identity available; raw paths not shown"
    if job.result_counts.get("retrieved_record_bundles", 0) > 0:
        return "raw artifact storage used; raw paths not shown"
    return "no raw artifact path shown"


def _render_history_next_step(job: CcldRetrievalJobHistoryEntry, imported_count: int) -> str:
    queue_link = _retrieval_history_queue_link(job) if imported_count > 0 else ""
    feedback_link = f'<p><a href="{_FEEDBACK_PATH}">Send tester feedback</a></p>'
    if job.job_state == "completed" and imported_count > 0:
        return queue_link
    if job.job_state == "completed_with_warnings" and imported_count > 0:
        return (
            "<p>Review imported records, then check warning details.</p>"
            f"{queue_link}{feedback_link}"
        )
    if job.job_state == "completed_with_warnings":
        return (
            "<p>No records were imported. Review warnings and adjust the request.</p>"
            f"{feedback_link}"
        )
    if job.job_state == "failed":
        return f"<p>Retry later or ask an operator to inspect server logs.</p>{feedback_link}"
    if job.job_state == "blocked_by_validation":
        return f"<p>Change the facility/date/type request before retrying.</p>{feedback_link}"
    if job.job_state == "rate_limited":
        return (
            "<p>Wait for an active retrieval job to finish before trying again.</p>"
            f"{feedback_link}"
        )
    if job.job_state == "running":
        return f"<p>Refresh this history page later; do not resubmit repeatedly.</p>{feedback_link}"
    return f"<p>Wait for the server-side job to start, then refresh later.</p>{feedback_link}"


def _retrieval_history_queue_link(job: CcldRetrievalJobHistoryEntry) -> str:
    query = urlencode(
        {
            "facility_number": job.facility_number,
            "start_date": job.start_date,
            "end_date": job.end_date,
            "record_type": job.record_type,
        }
    )
    return (
        f'<p><a href="{CCLD_RECORD_REQUEST_PATH}?{_escape(query)}">'
        "Review imported records in the CCLD queue</a></p>"
    )


def _retrieval_job_detail_href(retrieval_job_id: str) -> str:
    return f"{CCLD_RETRIEVAL_JOB_DETAIL_PATH}?{urlencode({'job_id': retrieval_job_id})}"


def _render_retrieval_action(
    request: CcldRecordRequest,
    retrieval_available: bool,
) -> str:
    if not retrieval_available:
        return """    <section aria-labelledby="retrieval-action-heading">
            <h2 id="retrieval-action-heading">Controlled CCLD retrieval setup required</h2>
            <p>Server-side retrieval is not configured with database context and raw source
            storage in this runtime. No retrieval job will be created from this browser page.</p>
            <p>Operators should enable retrieval only after PostgreSQL migrations, raw artifact
            storage, auth boundary, rate limits, and CCLD source allowlists are ready.</p>
            <p>If this setup state is confusing, use the feedback page to send a bug report.</p>
            <p><a href="/feedback">Send tester feedback</a></p>
        </section>"""
    return f"""    <section aria-labelledby="retrieval-action-heading">
            <h2 id="retrieval-action-heading">Controlled CCLD retrieval</h2>
            <p>This server-side action can retrieve CCLD complaint records for the bounded
            facility/date/type request. The browser submits only CCLD request inputs; the
            server performs retrieval, raw preservation, validation, and PostgreSQL import.</p>
            <form action="{CCLD_RECORD_REQUEST_PATH}" method="post">
                <input type="hidden" name="{_REQUEST_CONTEXT_ORIGIN_FIELD}"
                    value="{_escape(request.request_context_origin)}">
                <input type="hidden" name="{_LOOKUP_FACILITY_NAME_FIELD}"
                    value="{_escape(request.lookup_facility_name or '')}">
                <input type="hidden" name="facility_number"
                    value="{_escape(request.facility_number)}">
                <input type="hidden" name="record_type" value="{_escape(request.record_type)}">
                <input type="hidden" name="start_date" value="{_escape(request.start_date or '')}">
                <input type="hidden" name="end_date" value="{_escape(request.end_date or '')}">
                <input type="hidden" name="reviewer_status_filter"
                    value="{_escape(request.reviewer_status_filter)}">
                <input type="hidden" name="{_RETRIEVAL_ACTION_FIELD}"
                    value="{_RETRIEVAL_ACTION_VALUE}">
                <p><button type="submit">Run controlled CCLD retrieval</button></p>
            </form>
        </section>"""


def _safe_list_items(values: tuple[str, ...]) -> str:
    return "\n".join(f"        <li>{_escape(value)}</li>" for value in values)


def _count_label(name: str) -> str:
    return name.replace("_", " ").capitalize()


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


def _render_request_case_brief(
    request: CcldRecordRequest,
    items: tuple[CcldRequestQueueItem, ...],
    retrieval_result: CcldRetrievalJobResult | None,
) -> str:
    records = tuple(
        _case_brief_record_from_queue_item(index, request, item)
        for index, item in enumerate(items)
    )
    if not records:
        return ""
    facility_name = next((item.facility_name for item in items if item.facility_name), "")
    mode_label = (
        _retrieval_mode_label_from_message(retrieval_result.safe_message)
        if retrieval_result is not None
        else _runtime_mode_label()
    )
    return render_facility_case_brief(
        FacilityCaseBrief(
            facility_number=request.facility_number,
            facility_name=facility_name or request.lookup_facility_name or "",
            date_range=_date_scope_text(request),
            mode_label=mode_label,
            mode_badge_class=_mode_badge_class(mode_label),
            records=records,
            record_count_label="Complaint records visible/imported",
            full_queue_href=REVIEWER_UI_RECORDS_PATH,
            packet_preview_href=_packet_preview_href_for_request(request),
            packet_draft_href=_packet_draft_href_for_request(request),
        )
    )


def _case_brief_record_from_queue_item(
    index: int,
    request: CcldRecordRequest,
    item: CcldRequestQueueItem,
) -> FacilityCaseBriefRecord:
    complaint = _mapping(item.complaint_record, "original_values")
    source_record_key = _string(item.complaint_record, "source_record_key")
    latest_status = _summary_optional_string(item.reviewer_state, "latest_status")
    return FacilityCaseBriefRecord(
        source_record_key=source_record_key,
        detail_href=_reviewer_detail_href_for_request(source_record_key, request=request),
        complaint_control_number=_display_value(
            complaint.get("complaint_control_number") or source_record_key
        ),
        finding=_optional_string(complaint, "finding") or "unknown",
        complaint_received_date=_optional_string(complaint, "complaint_received_date") or "",
        visit_date=_optional_string(complaint, "visit_date") or "",
        report_date=_optional_string(complaint, "report_date") or "",
        date_signed=_optional_string(complaint, "date_signed") or "",
        facility_number=request.facility_number,
        facility_name=item.facility_name or request.lookup_facility_name or "",
        has_source_traceability=_has_source_traceability(item.complaint_record),
        reviewer_status=latest_status,
        reviewer_status_label=_status_label(latest_status) if latest_status else None,
        reviewer_note_count=_summary_int(item.reviewer_state, "note_count"),
        delay_thresholds=_delay_thresholds(complaint),
        missing_first_activity_date=complaint.get("missing_first_activity_date") is True,
        missing_visit_date=not _has_display_value(complaint.get("visit_date")),
        missing_report_date=not _has_display_value(complaint.get("report_date")),
        missing_signed_date=not _has_display_value(complaint.get("date_signed")),
        report_date_used_as_proxy=complaint.get("report_date_used_as_proxy") is True,
        order_index=index,
    )


def _delay_thresholds(values: Mapping[str, Any]) -> tuple[int, ...]:
    thresholds: list[int] = []
    for days in (30, 60, 90, 120):
        if values.get(f"review_delay_over_{days}_days") is True:
            thresholds.append(days)
    return tuple(thresholds)


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
                <li>On detail, check source traceability, source-confidence cues, and
                field-note guidance before saving reviewer notes/status.</li>
                <li>Return to this same request page, resubmit when needed to refresh queue
                progress, and continue with the next suggested record.</li>
                <li>Copy the single manual feedback checklist for both queue and detail
                observations.</li>
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
    <p>Queue summaries do not prove record completeness. Open reviewer detail for
    source-confidence cues before relying on a summary value that looks missing,
    confusing, or proxy-related.</p>
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
    <p>Carry both queue-level observations and reviewer-detail observations into that same
        manual feedback checklist; this queue does not create a second checklist or persist
        feedback.</p>
    </section>"""


def _render_worklist_decision_flow(
    request: CcldRecordRequest,
    queue_items: tuple[CcldRequestQueueItem, ...],
    filtered_queue_items: tuple[CcldRequestQueueItem, ...],
    reference_source: CcldFacilityReferenceSource,
) -> str:
    note_or_status_count = sum(
        1 for item in queue_items if _summary_int(item.reviewer_state, "total_rows") > 0
    )
    review_flag_count = sum(
        1
        for index, item in enumerate(queue_items)
        if has_review_flag(_case_brief_record_from_queue_item(index, request, item))
    )
    traceability_count = sum(1 for item in queue_items if _has_source_traceability(item.complaint_record))
    next_item = _next_queue_item(queue_items)
    next_card = _render_recommended_next_record(request, next_item)
    cards = "\n".join(
        _render_worklist_decision_card(request, item, index, is_next=item is next_item)
        for index, item in enumerate(filtered_queue_items)
    )
    if not cards:
        cards = """      <p>No record cards are visible under the selected reviewer-status filter.
      Use the filtered-empty recovery action above to show all queue records for this same
      facility/date request context.</p>"""
    change_href = _request_change_href(
        facility_number=request.facility_number,
        start_date=request.start_date,
        end_date=request.end_date,
        request_context_origin=request.request_context_origin,
        lookup_facility_name=request.lookup_facility_name,
    )
    return f"""<section aria-labelledby="worklist-decision-flow-heading">
      <h3 id="worklist-decision-flow-heading">Review-priority decision flow</h3>
      <p>Use this local/test worklist as a decision screen: confirm the CCLD request
      context, open the suggested next record, then continue to packet preparation only
      after checking source traceability on reviewer detail.</p>
      <dl>
        <dt>Active CCLD request context</dt>
        <dd>{_escape(_facility_scope_for_summary(request))}; date range {_escape(_date_scope_text(request))}</dd>
        <dt>Request origin</dt>
        <dd>{_escape(_request_origin_label(request.request_context_origin))}</dd>
        <dt>Active local/test reference source</dt>
        <dd>{_escape(_user_facing_source_label(reference_source))}</dd>
        <dt>Loaded local/test source-derived complaint records</dt>
        <dd>{len(queue_items)}</dd>
        <dt>Records with reviewer-created status/note cues</dt>
        <dd>{note_or_status_count}</dd>
        <dt>Records with review flags or possible delay indicators</dt>
        <dd>{review_flag_count}</dd>
        <dt>Records with source traceability available</dt>
        <dd>{traceability_count}</dd>
      </dl>
      {next_card}
      <div class="form-actions" aria-label="Queue decision actions">
        <a class="button button-secondary" href="{_escape(change_href)}">Return to change facility/date criteria</a>
        <a class="button button-secondary" href="{_escape(_packet_preview_href_for_request(request))}">Preview local/test preparation packet</a>
        <a class="button button-secondary" href="{_escape(_packet_draft_href_for_request(request))}">Open print/copy local/test preparation draft</a>
        <a class="button button-secondary" href="{CCLD_HELP_PATH}">Open CCLD workflow help</a>
      </div>
      <p class="helper-text">Packet preview and draft links are local/test preparation aids,
      not a legal report, final export, or source-completeness proof.</p>
      <section aria-labelledby="priority-record-cards-heading">
        <h4 id="priority-record-cards-heading">Prioritized worklist records</h4>
        <p>These record cards use existing source-derived values and existing reviewer-created
        note/status reads only. They do not assign, claim, or mutate records.</p>
{cards}
      </section>
    <p>If the queue order, a missing local/test record, an unexpected record,
    source-traceability cue, reviewer-created status/note cue, wording, keyboard flow,
    or next step is confusing, open <a href="{_escape(_feedback_href_for_queue(request))}">tester
    feedback for this queue context</a>.</p>
    </section>"""


def _render_recommended_next_record(
    request: CcldRecordRequest,
    item: CcldRequestQueueItem | None,
) -> str:
    if item is None:
        return """      <section class="summary-card" aria-labelledby="recommended-next-record-heading">
        <h4 id="recommended-next-record-heading">Recommended next record action</h4>
        <p>No source-derived complaint record is visible for this filter.</p>
      </section>"""
    source_record_key = _string(item.complaint_record, "source_record_key")
    detail_href = _reviewer_detail_href_for_request(source_record_key, request=request)
    label = _queue_record_label(item)
    reasons = _queue_priority_reason_items(request, item, 0)
    return f"""      <section class="summary-card" aria-labelledby="recommended-next-record-heading">
        <h4 id="recommended-next-record-heading">Recommended next record action</h4>
        <p><a class="button" href="{_escape(detail_href)}">Open next priority record: {_escape(label)}</a></p>
        <p>Why this record is prioritized:</p>
        <ul>
{reasons}
        </ul>
      </section>"""


def _render_worklist_decision_card(
    request: CcldRecordRequest,
    item: CcldRequestQueueItem,
    index: int,
    *,
    is_next: bool,
) -> str:
    source_record_key = _string(item.complaint_record, "source_record_key")
    detail_href = _reviewer_detail_href_for_request(source_record_key, request=request)
    label = _queue_record_label(item)
    heading_prefix = "Recommended next record" if is_next else "Worklist record"
    reasons = _queue_priority_reason_items(request, item, index)
    return f"""        <article class="summary-card" aria-labelledby="worklist-record-{index + 1}-heading">
          <h5 id="worklist-record-{index + 1}-heading">{_escape(heading_prefix)}: {_escape(label)}</h5>
          <p>{_escape(_record_review_need_label(request, item, index))}</p>
          <dl>
            <dt>Complaint/control/source-record identifier</dt>
            <dd>{_escape(label)}; source record key {_escape(source_record_key)}</dd>
            <dt>Source-derived date/finding/flag summary</dt>
            <dd>{_escape(_record_source_summary(request, item, index))}</dd>
            <dt>Reviewer-created status/note cue</dt>
            <dd>{_escape(_reviewer_state_text(item.reviewer_state))}</dd>
            <dt>Source traceability availability cue</dt>
            <dd>{_escape(_traceability_summary(item.complaint_record))}</dd>
            <dt>Loaded local/test bundle context</dt>
            <dd>{_escape(_loaded_context_text(item))}</dd>
          </dl>
          <p>Why this record is prioritized:</p>
          <ul>
{reasons}
          </ul>
          <p><a href="{_escape(detail_href)}">Open review workspace for {_escape(label)}</a></p>
        </article>"""


def _queue_priority_reason_items(
    request: CcldRecordRequest,
    item: CcldRequestQueueItem,
    index: int,
) -> str:
    record = _case_brief_record_from_queue_item(index, request, item)
    reasons = priority_reason_labels(record)
    if not reasons:
        reasons = ("No review flags are visible from loaded source-derived fields.",)
    return "\n".join(f"          <li>{_escape(reason)}</li>" for reason in reasons)


def _record_review_need_label(
    request: CcldRecordRequest,
    item: CcldRequestQueueItem,
    index: int,
) -> str:
    record = _case_brief_record_from_queue_item(index, request, item)
    if has_review_flag(record):
        return "Review need: flagged for review from source-derived cues; check detail before relying on the summary."
    if _summary_int(item.reviewer_state, "total_rows") == 0:
        return "Review need: no reviewer-created status/note recorded yet."
    return "Review need: reviewer-created status/note cue exists; continue from detail if follow-up is needed."


def _record_source_summary(
    request: CcldRecordRequest,
    item: CcldRequestQueueItem,
    index: int,
) -> str:
    complaint = _mapping(item.complaint_record, "original_values")
    record = _case_brief_record_from_queue_item(index, request, item)
    parts = [
        f"dates: {_complaint_date_summary(complaint)}",
        f"finding value: {_optional_string(complaint, 'finding') or 'unknown'}",
    ]
    if record.delay_thresholds:
        parts.append(f"possible delay indicator over {max(record.delay_thresholds)} days")
    if has_review_flag(record):
        parts.append("flagged for review; needs source check on detail")
    else:
        parts.append("no review flag visible from loaded fields")
    return "; ".join(parts)


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
            expected to see, or open <a href="{_escape(_feedback_href_for_queue(request))}">tester
            feedback for this filtered queue</a>.</p>
        </section>"""


def _feedback_href_for_queue(request: CcldRecordRequest) -> str:
    query_values = {
        "feedback_type": "Bug report",
        "workflow_area": "queue",
        "page_path": CCLD_RECORD_REQUEST_PATH,
        "facility_number": request.facility_number,
        "start_date": request.start_date or "",
        "end_date": request.end_date or "",
        "request_context_origin": request.request_context_origin,
        "reviewer_status_filter": request.reviewer_status_filter,
        "prompt": "Describe what was confusing about this queue or filter.",
    }
    return f"{_FEEDBACK_PATH}?{urlencode(query_values)}"


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


def _decision_sorted_queue_items(
    request: CcldRecordRequest,
    items: tuple[CcldRequestQueueItem, ...],
) -> tuple[CcldRequestQueueItem, ...]:
    indexed_items = tuple(enumerate(items))
    sorted_pairs = sorted(
        indexed_items,
        key=lambda pair: _queue_decision_sort_key(request, pair[1], pair[0]),
    )
    return tuple(item for _index, item in sorted_pairs)


def _queue_decision_sort_key(
    request: CcldRecordRequest,
    item: CcldRequestQueueItem,
    index: int,
) -> tuple[int, int, int, int, str, int]:
    status_rank = _NEXT_REVIEW_STATUS_ORDER.index(_queue_status(item))
    record = _case_brief_record_from_queue_item(index, request, item)
    review_flag_rank = 0 if has_review_flag(record) else 1
    no_state_rank = 0 if _summary_int(item.reviewer_state, "total_rows") == 0 else 1
    traceability_rank = 0 if _has_source_traceability(item.complaint_record) else 1
    complaint = _mapping(item.complaint_record, "original_values")
    date_value = (
        _optional_string(complaint, "complaint_received_date")
        or _optional_string(complaint, "report_date")
        or _optional_string(complaint, "visit_date")
        or _optional_string(complaint, "date_signed")
        or ""
    )
    return (
        status_rank,
        review_flag_rank,
        no_state_rank,
        traceability_rank,
        _reverse_date_key(date_value),
        index,
    )


def _queue_record_label(item: CcldRequestQueueItem) -> str:
    complaint = _mapping(item.complaint_record, "original_values")
    complaint_control_number = complaint.get("complaint_control_number")
    if _has_display_value(complaint_control_number):
        return _display_value(complaint_control_number)
    source_record_key = _string(item.complaint_record, "source_record_key")
    return source_record_key or "Complaint record"


def _reverse_date_key(value: str) -> str:
    if not value:
        return "9999-99-99"
    return "".join(str(9 - int(ch)) if ch.isdigit() else ch for ch in value)


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
        <p>Use this same manual checklist for queue observations, reviewer-detail
        observations, note/status confirmation behavior, return-to-queue refresh behavior,
        filtered-empty recovery, no-match/load guidance, and confusing wording or labels.</p>
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
        f"- Active facility reference source: {_user_facing_source_label(reference_source)}",
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
        "- Review session path was clear from home/request/help:",
        "- Reviewer detail record opened:",
        "- Source traceability cues were easy to find:",
        "- Source-confidence cues or missing local/test fields to mention:",
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
        "- The app does not create a saved review session, persisted queue state, "
        "or second checklist.",
        "- Rendering this checklist does not change source-derived records, "
        "reviewer-created state, audit rows, import batches, or operational metadata.",
        "- Browser pages only trigger controlled server-side retrieval when the retrieval "
        "action is explicitly submitted.",
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


def _packet_preview_href_for_request(request: CcldRecordRequest) -> str:
    query_values = {
        "facility_number": request.facility_number,
        "start_date": request.start_date or "",
        "end_date": request.end_date or "",
        "request_context_origin": request.request_context_origin,
        "lookup_facility_name": request.lookup_facility_name or "",
    }
    return f"{REVIEWER_UI_PACKET_PREVIEW_PATH}?{urlencode(query_values)}"


def _packet_draft_href_for_request(request: CcldRecordRequest) -> str:
    query_values = {
        "facility_number": request.facility_number,
        "start_date": request.start_date or "",
        "end_date": request.end_date or "",
        "request_context_origin": request.request_context_origin,
        "lookup_facility_name": request.lookup_facility_name or "",
    }
    return f"{REVIEWER_UI_PACKET_DRAFT_PATH}?{urlencode(query_values)}"


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
        f"{item.extraction_audit_count} extraction audit rows. "
        "Open detail for source-confidence cues before relying on missing or confusing fields."
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
    if not facility_number.strip() and not include_change_links:
        limitation = _reference_limitation_text(reference_source)
        limitation_markup = (
            f"<p class=\"helper-text\">{_escape(limitation)}</p>" if limitation else ""
        )
        return f"""    <section class="summary-card" aria-labelledby="request-context-confirmation-heading">
      <h2 id="request-context-confirmation-heading">No facility selected yet</h2>
      <p>Start by typing a facility/license number or searching by name.</p>
      <dl>
        <dt>Retrieval mode</dt>
        <dd>{_escape(_runtime_mode_label())}</dd>
        <dt>Active facility reference source</dt>
        <dd>{_escape(_user_facing_source_label(reference_source))}</dd>
        <dt>Reference rows loaded</dt>
        <dd>{len(reference_source.records)}</dd>
      </dl>
{limitation_markup}
    </section>"""
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
    limitation = _reference_limitation_text(reference_source)
    limitation_markup = (
        f"      <p class=\"helper-text\">{_escape(limitation)}</p>" if limitation else ""
    )
    return f"""    <section class="summary-card" aria-labelledby="request-context-confirmation-heading">
            <h2 id="request-context-confirmation-heading">Selected request context</h2>
            <p>Confirm this facility/date context before retrieving or reviewing records.</p>
      <dl>
        <dt>Facility/license number being requested</dt>
        <dd>{_escape(facility_display)}</dd>{lookup_name_markup}
        <dt>Date range being requested</dt>
        <dd>{_escape(_date_scope_from_values(start_date, end_date))}</dd>
            </dl>
            <details class="technical-details">
                <summary>Request and lookup details</summary>
                <dl>
                <dt>Request started from</dt>
                <dd>{_escape(_request_origin_label(request_context_origin))}</dd>
        <dt>Active facility reference source</dt>
        <dd>{_escape(_user_facing_source_label(reference_source))}</dd>
        <dt>Retrieval mode</dt>
        <dd>{_escape(_runtime_mode_label())}</dd>
        <dt>Reference rows loaded for lookup</dt>
        <dd>{len(reference_source.records)}</dd>
      </dl>
{warning_markup}
            </details>
{limitation_markup}
{change_links}
    </section>"""


def _reference_limitation_text(source: CcldFacilityReferenceSource) -> str:
    if source.source_kind == "tiny_fixture_fallback" or len(source.records) <= 2:
        return "Limited reference list: suggestions may not include every CCLD facility."
    return ""


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
    active_path: str | None = None,
) -> str:
    link_items = "\n".join(
        f'        <li><a href="{_escape(href)}">{_escape(label)}</a></li>' for label, href in links
    )
    return _page(
        title=title,
        heading=heading,
        active_path=active_path if active_path is not None else CCLD_RECORD_REQUEST_PATH,
        main=f"""    <section aria-labelledby="message-heading">
            <h2 id="message-heading">{_escape(heading)}</h2>
            <p>{_escape(message)}</p>
            <p>{_escape(guidance)}</p>
            <ul>
{link_items}
            </ul>
        </section>""",
    )


def _page(
    *,
    title: str,
    heading: str,
    main: str,
    active_path: str = CCLD_RECORD_REQUEST_PATH,
    step_id: str = "retrieve",
    next_action: str | None = None,
    show_workflow_indicator: bool = True,
) -> str:
    return render_page_shell(
        title=title,
        heading=heading,
        main=main,
        skip_label="Skip to main CCLD request content",
        nav_label="Hosted scaffold navigation",
        active_path=active_path,
        step_id=step_id,
        next_action=next_action,
        show_workflow_indicator=show_workflow_indicator,
    )
