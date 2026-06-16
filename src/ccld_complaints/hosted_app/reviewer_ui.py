# ruff: noqa: E501

from __future__ import annotations

import html
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qs, urlencode, urlparse

from sqlalchemy import create_engine
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.pool import StaticPool

from ccld_complaints.hosted_app.auth import (
    AuthenticatedActor,
    HostedAccessScope,
    HostedAccountStatus,
    HostedTesterRole,
)
from ccld_complaints.hosted_app.ccld_facility_lookup import (
    CCLD_FACILITY_LOOKUP_PATH,
    CCLD_RECORD_REQUEST_PATH,
)
from ccld_complaints.hosted_app.reviewer_created_state import REVIEWER_STATUS_VALUES
from ccld_complaints.hosted_app.reviewer_created_state_routes import (
    REVIEWER_CREATED_STATE_API_PREFIX,
    ReviewerCreatedStateApiContext,
    route_reviewer_created_state_api_response,
)
from ccld_complaints.hosted_app.reviewer_workflow_shell import (
    REVIEWER_WORKFLOW_API_PREFIX,
    ReviewerWorkflowShellContext,
    route_reviewer_workflow_shell_response,
)
from ccld_complaints.hosted_app.seeded_import import (
    hosted_seeded_import_metadata,
    import_seeded_corpus_artifact,
    load_seeded_corpus_artifact,
)
from ccld_complaints.hosted_app.source_derived_routes import (
    SOURCE_DERIVED_API_PREFIX,
    SourceDerivedApiContext,
    route_source_derived_api_response,
)
from ccld_complaints.hosted_app.ui_shell import render_page_shell

REVIEWER_UI_PREFIX = "/reviewer"
REVIEWER_UI_RECORDS_PATH = f"{REVIEWER_UI_PREFIX}/records"
REVIEWER_UI_DETAIL_PATH = f"{REVIEWER_UI_RECORDS_PATH}/detail"
REVIEWER_UI_NOTE_PATH = f"{REVIEWER_UI_RECORDS_PATH}/note"
REVIEWER_UI_STATUS_PATH = f"{REVIEWER_UI_RECORDS_PATH}/status"
CCLD_HELP_PATH = "/ccld/help"
LOCAL_REVIEWER_UI_SCOPE = HostedAccessScope(
    "seeded_corpus",
    "seeded-ccld-fixture-2026-06-13",
)
LOCAL_REVIEWER_UI_FIXTURE = Path(
    "tests/fixtures/hosted_seeded_corpus/validated_seeded_corpus.json"
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
_SAFE_ORIGINAL_VALUE_DENYLIST = (
    "allegation_text",
    "event_text",
    "source_text",
)
_SAFE_CONTEXT_FIELDS_BY_ENTITY: Mapping[str, tuple[str, ...]] = {
    "facility": (
        "facility_name",
        "external_facility_number",
        "facility_type",
        "county",
        "source_id",
    ),
    "source_document": (
        "document_type",
        "report_index",
        "content_type",
        "source_id",
        "facility_id",
    ),
    "complaint": (
        "complaint_control_number",
        "complaint_received_date",
        "visit_date",
        "report_date",
        "date_signed",
        "finding",
        "review_delay_over_30_days",
        "review_delay_over_60_days",
        "review_delay_over_90_days",
        "review_delay_over_120_days",
        "missing_first_activity_date",
        "report_date_used_as_proxy",
        "extraction_confidence",
    ),
    "allegation": (
        "allegation_category",
        "finding",
        "extraction_confidence",
    ),
    "event": (
        "event_date",
        "event_type",
        "extracted_from_section",
        "extraction_confidence",
    ),
    "extraction_audit": (
        "field_name",
        "extraction_method",
        "extracted_value",
        "confidence",
        "source_section",
        "extractor_version",
        "warning",
    ),
}
_SOURCE_CONFIDENCE_COMPLAINT_FIELDS = (
    (
        "Complaint control number",
        "complaint_control_number",
        "Use this as the complaint identifier only after checking the source document context.",
    ),
    (
        "Complaint received date",
        "complaint_received_date",
        "Check the source traceability fields before relying on this date in notes/status.",
    ),
    (
        "Visit date",
        "visit_date",
        "If this is missing, describe it as not available locally, not as proof no visit occurred.",
    ),
    (
        "Report date",
        "report_date",
        "Check whether the report date is acting as a proxy before using delay wording.",
    ),
    (
        "Date signed",
        "date_signed",
        "Use this as a source-derived display value; verify source context before relying on it.",
    ),
    (
        "Finding",
        "finding",
        "Treat this as a source-derived local/test value, not as a new reviewer finding.",
    ),
    (
        "Extraction confidence",
        "extraction_confidence",
        "Treat this as local/test extraction metadata, not as reviewer verification.",
    ),
)
_SOURCE_CONTEXT_ENTITY_ORDER = {
    "facility": 0,
    "source_document": 1,
    "complaint": 2,
    "allegation": 3,
    "event": 4,
    "extraction_audit": 5,
}
_REVIEWER_STATUS_LABELS = {
    "not_started": "Not started",
    "in_review": "In review",
    "needs_follow_up": "Needs follow-up",
    "reviewed": "Reviewed",
    "blocked": "Blocked",
}
_REVIEWER_STATUS_ORDER = (
    "not_started",
    "in_review",
    "needs_follow_up",
    "reviewed",
    "blocked",
)
_NEXT_REVIEW_STATUS_ORDER = (
    "not_started",
    "in_review",
    "needs_follow_up",
    "blocked",
    "reviewed",
)
_DEFAULT_ACTOR = object()
_RETURN_CONTEXT_FIELDS = (
    "return_facility_number",
    "return_start_date",
    "return_end_date",
    "return_context_origin",
    "return_lookup_facility_name",
)


@dataclass(frozen=True)
class ReviewerUiContext:
    workflow_shell_context: ReviewerWorkflowShellContext
    engine: Engine | None = None


@dataclass(frozen=True)
class CcldQueueReturnContext:
    facility_number: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    context_origin: str | None = None
    lookup_facility_name: str | None = None


_DEFAULT_REVIEWER_UI_CONTEXT: ReviewerUiContext | None = None


def build_local_test_reviewer_ui_context() -> ReviewerUiContext:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    hosted_seeded_import_metadata.create_all(engine)
    connection = engine.connect()
    transaction = connection.begin()
    artifact = load_seeded_corpus_artifact(LOCAL_REVIEWER_UI_FIXTURE)
    import_seeded_corpus_artifact(connection, artifact)
    transaction.commit()
    return ReviewerUiContext(
        workflow_shell_context=_workflow_context(
            connection,
            actor=local_test_reviewer_actor(),
            scope=LOCAL_REVIEWER_UI_SCOPE,
        ),
        engine=engine,
    )


def default_local_test_reviewer_ui_context() -> ReviewerUiContext:
    global _DEFAULT_REVIEWER_UI_CONTEXT
    if _DEFAULT_REVIEWER_UI_CONTEXT is None:
        _DEFAULT_REVIEWER_UI_CONTEXT = build_local_test_reviewer_ui_context()
    return _DEFAULT_REVIEWER_UI_CONTEXT


def reset_default_local_test_reviewer_ui_context() -> None:
    global _DEFAULT_REVIEWER_UI_CONTEXT
    if _DEFAULT_REVIEWER_UI_CONTEXT is not None and _DEFAULT_REVIEWER_UI_CONTEXT.engine:
        _DEFAULT_REVIEWER_UI_CONTEXT.engine.dispose()
    _DEFAULT_REVIEWER_UI_CONTEXT = None


def local_test_reviewer_actor(
    *,
    roles: tuple[str, ...] = ("tester_reviewer",),
    scopes: tuple[HostedAccessScope, ...] = (LOCAL_REVIEWER_UI_SCOPE,),
    account_status: str = "active",
) -> AuthenticatedActor:
    return AuthenticatedActor(
        provider_subject="local-test-reviewer",
        provider_issuer="local-test-managed-identity",
        display_name="Local Test Reviewer",
        email=None,
        actor_category="tester",
        account_status=cast(HostedAccountStatus, account_status),
        roles=tuple(cast(HostedTesterRole, role) for role in roles),
        scopes=scopes,
    )


def reviewer_ui_context_for_connection(
    connection: Connection,
    *,
    actor: AuthenticatedActor | None | object = _DEFAULT_ACTOR,
    scope: HostedAccessScope = LOCAL_REVIEWER_UI_SCOPE,
) -> ReviewerUiContext:
    context_actor = local_test_reviewer_actor() if actor is _DEFAULT_ACTOR else actor
    return ReviewerUiContext(
        workflow_shell_context=_workflow_context(
            connection,
            actor=cast(AuthenticatedActor | None, context_actor),
            scope=scope,
        )
    )


def route_reviewer_ui_response(
    path: str,
    context: ReviewerUiContext | None,
    *,
    method: str = "GET",
    request_body: bytes | None = None,
) -> tuple[int, str, bytes]:
    parsed_url = urlparse(path)
    if context is None:
        return _html_response(
            503,
            _render_blocked_page(
                title="Reviewer UI unavailable",
                heading="Reviewer UI unavailable",
                message="Local/test reviewer UI context is not configured.",
            ),
        )
    try:
        if method == "POST" and parsed_url.path == REVIEWER_UI_NOTE_PATH:
            return _note_form_response(request_body, context)
        if method == "POST" and parsed_url.path == REVIEWER_UI_STATUS_PATH:
            return _status_form_response(request_body, context)
    except ValueError as error:
        return _html_response(
            400,
            _render_blocked_page(
                title="Reviewer form blocked",
                heading="Reviewer form blocked",
                message=str(error),
            ),
        )
    if method != "GET":
        return _html_response(
            405,
            _render_blocked_page(
                title="Reviewer UI method unavailable",
                heading="Reviewer UI method unavailable",
                message=(
                    "This local/test reviewer page supports browser GET pages "
                    "and form POST actions only."
                ),
            ),
        )
    if parsed_url.path in {REVIEWER_UI_PREFIX, REVIEWER_UI_RECORDS_PATH}:
        return _record_list_response(parsed_url.query, context)
    if parsed_url.path == REVIEWER_UI_DETAIL_PATH:
        return _detail_response(parsed_url.query, context)
    return _html_response(
        404,
        _render_blocked_page(
            title="Reviewer UI page not found",
            heading="Reviewer UI page not found",
            message="The requested local/test reviewer UI page was not found.",
        ),
    )


def _workflow_context(
    connection: Connection,
    *,
    actor: AuthenticatedActor | None,
    scope: HostedAccessScope,
) -> ReviewerWorkflowShellContext:
    source_context = SourceDerivedApiContext(
        connection=connection,
        actor=actor,
        scope=scope,
    )
    state_context = ReviewerCreatedStateApiContext(
        connection=connection,
        actor=actor,
        scope=scope,
    )
    return ReviewerWorkflowShellContext(
        source_derived_api_context=source_context,
        reviewer_created_state_api_context=state_context,
    )


def _record_list_response(
    query: str,
    context: ReviewerUiContext,
) -> tuple[int, str, bytes]:
    query_values = parse_qs(query, keep_blank_values=True)
    search_query = _first_form_value(query_values, "q")
    status, _content_type, body = route_reviewer_workflow_shell_response(
        f"{REVIEWER_WORKFLOW_API_PREFIX}/queue?limit=100",
        context.workflow_shell_context,
    )
    if status != 200:
        return _workflow_error_page(status, body)
    payload = _json_object(body)
    queue = _mapping(payload, "queue")
    records = _record_list(queue, "records")
    filtered_records = _filter_review_items(records, search_query)
    state_status, state_body = _reviewer_created_state_records(context)
    if state_status != 200:
        if not isinstance(state_body, bytes):
            raise ValueError("Expected reviewer-created state error body to be bytes.")
        return _workflow_error_page(state_status, state_body)
    if isinstance(state_body, bytes):
        raise ValueError("Expected reviewer-created state records.")
    state_summaries = _state_summaries_by_source_record(state_body)
    return _html_response(
        status,
        _render_record_list(
            payload,
            filtered_records,
            search_query,
            state_summaries,
            actor_label=_signed_in_actor_label(context),
        ),
    )


def _reviewer_created_state_records(
    context: ReviewerUiContext,
) -> tuple[int, list[Mapping[str, Any]] | bytes]:
    state_status, _content_type, state_body = route_reviewer_created_state_api_response(
        REVIEWER_CREATED_STATE_API_PREFIX,
        context.workflow_shell_context.reviewer_created_state_api_context,
    )
    if state_status != 200:
        return state_status, state_body
    state_payload = _json_object(state_body)
    return 200, _record_list(state_payload, "reviewer_created_state")


def _detail_response(
    query: str,
    context: ReviewerUiContext,
) -> tuple[int, str, bytes]:
    query_values = parse_qs(query, keep_blank_values=True)
    source_record_key = _first_form_value(query_values, "source_record_key")
    if not source_record_key:
        return _html_response(
            400,
            _render_message_page(
                title="Select a seeded record",
                heading="Select a seeded record",
                message="Choose a seeded source-derived record before opening reviewer detail.",
                guidance="Return to the reviewer list and open one of the seeded records.",
                links=(("Return to reviewer records", REVIEWER_UI_RECORDS_PATH),),
            ),
        )
    detail_path = _workflow_detail_path(source_record_key)
    status, _content_type, body = route_reviewer_workflow_shell_response(
        detail_path,
        context.workflow_shell_context,
    )
    if status != 200:
        return _workflow_error_page(
            status,
            body,
            missing_record_heading="Selected seeded record was not found",
        )
    payload = _json_object(body)
    return _detail_html_response(
        status,
        payload,
        context,
        notice=None,
        return_context=_return_context_from_values(query_values, related_records=None),
    )


def _note_form_response(
    request_body: bytes | None,
    context: ReviewerUiContext,
) -> tuple[int, str, bytes]:
    form = _form_values(request_body)
    source_record_key = _first_form_value(form, "source_record_key")
    note_text = _first_form_value(form, "note_text")
    return_context = _return_context_from_values(form, related_records=None)
    if not source_record_key:
        return _invalid_form_response(
            title="Reviewer note was not saved",
            message="Open a reviewer detail record before saving a reviewer note.",
            source_record_key=None,
        )
    if not note_text:
        return _invalid_form_response(
            title="Reviewer note was not saved",
            message="Enter safe plain text before saving a reviewer note for this record.",
            source_record_key=source_record_key,
        )
    status, _content_type, body = route_reviewer_workflow_shell_response(
        _workflow_note_path(source_record_key),
        context.workflow_shell_context,
        request_body=json.dumps({"note_text": note_text}, sort_keys=True).encode("utf-8"),
    )
    if status != 201:
        return _workflow_error_page(
            status,
            body,
            title="Reviewer note was not saved",
            heading="Reviewer note was not saved",
            guidance="Return to the detail page and retry with valid note text.",
            links=_retry_links(source_record_key),
        )
    payload = _json_object(body)
    return _detail_html_response(
        200,
        payload,
        context,
        notice=(
            "Reviewer note saved for this record. The note now appears in "
            "reviewer-created state below. Queue progress and note/status cues are "
            "derived from reviewer-created state. Return to the same CCLD request "
            "context and submit the same request to see updated note cues before "
            "continuing to the next record."
        ),
        return_context=return_context,
    )


def _status_form_response(
    request_body: bytes | None,
    context: ReviewerUiContext,
) -> tuple[int, str, bytes]:
    form = _form_values(request_body)
    source_record_key = _first_form_value(form, "source_record_key")
    reviewer_status = _first_form_value(form, "reviewer_status")
    return_context = _return_context_from_values(form, related_records=None)
    if not source_record_key:
        return _invalid_form_response(
            title="Reviewer status was not saved",
            message="Open a reviewer detail record before saving a reviewer status.",
            source_record_key=None,
        )
    if not reviewer_status:
        return _invalid_form_response(
            title="Reviewer status was not saved",
            message="Choose a reviewer queue status before saving this record.",
            source_record_key=source_record_key,
        )
    status, _content_type, body = route_reviewer_workflow_shell_response(
        _workflow_status_path(source_record_key),
        context.workflow_shell_context,
        request_body=json.dumps(
            {"reviewer_status": reviewer_status},
            sort_keys=True,
        ).encode("utf-8"),
    )
    if status != 201:
        return _workflow_error_page(
            status,
            body,
            title="Reviewer status was not saved",
            heading="Reviewer status was not saved",
            guidance=(
                "Return to the detail page and choose one of the listed local/test "
                "reviewer statuses. Status values update queue cues but do not change "
                "source-derived records."
            ),
            links=_retry_links(source_record_key),
        )
    payload = _json_object(body)
    return _detail_html_response(
        200,
        payload,
        context,
        notice=(
            "Reviewer status saved for this record. The status now appears in "
            "reviewer-created state below. Queue progress and note/status cues are "
            "derived from reviewer-created state. Return to the same CCLD request "
            "context and submit the same request to see updated status cues before "
            "continuing to the next record."
        ),
        return_context=return_context,
    )


def _detail_html_response(
    status: int,
    payload: Mapping[str, Any],
    context: ReviewerUiContext,
    *,
    notice: str | None,
    return_context: CcldQueueReturnContext,
) -> tuple[int, str, bytes]:
    bundle_status, bundle_body = _related_source_derived_context(payload, context)
    if bundle_status != 200:
        if not isinstance(bundle_body, bytes):
            raise ValueError("Expected related source-derived error body to be bytes.")
        return _workflow_error_page(bundle_status, bundle_body)
    if isinstance(bundle_body, bytes):
        raise ValueError("Expected related source-derived context records.")
    return _html_response(
        status,
        _render_detail(
            payload,
            notice=notice,
            related_records=bundle_body,
            return_context=_return_context_with_related_defaults(
                return_context,
                bundle_body,
            ),
            actor_label=_signed_in_actor_label(context),
        ),
    )


def _related_source_derived_context(
    payload: Mapping[str, Any],
    context: ReviewerUiContext,
) -> tuple[int, list[Mapping[str, Any]] | bytes]:
    detail = _mapping(payload, "detail")
    source_record = _mapping(detail, "source_record")
    source_status, _content_type, source_body = route_source_derived_api_response(
        f"{SOURCE_DERIVED_API_PREFIX}?limit=100",
        context.workflow_shell_context.source_derived_api_context,
    )
    if source_status != 200:
        return source_status, source_body
    source_payload = _json_object(source_body)
    records = _record_list(source_payload, "records")
    related_records = _related_source_records(source_record, records)
    return 200, related_records


def _workflow_detail_path(source_record_key: str) -> str:
    return (
        f"{REVIEWER_WORKFLOW_API_PREFIX}/detail?"
        f"{urlencode({'source_record_key': source_record_key})}"
    )


def _workflow_note_path(source_record_key: str) -> str:
    return (
        f"{REVIEWER_WORKFLOW_API_PREFIX}/detail/reviewer-note?"
        f"{urlencode({'source_record_key': source_record_key})}"
    )


def _workflow_status_path(source_record_key: str) -> str:
    return (
        f"{REVIEWER_WORKFLOW_API_PREFIX}/detail/reviewer-status?"
        f"{urlencode({'source_record_key': source_record_key})}"
    )


def _render_record_list(
    payload: Mapping[str, Any],
    records: list[Mapping[str, Any]],
    search_query: str,
    state_summaries: Mapping[str, Mapping[str, Any]],
    *,
    actor_label: str | None,
) -> str:
    queue = _mapping(payload, "queue")
    workflow = _mapping(payload, "workflow_shell")
    returned_count = _int_value(_mapping(queue, "pagination"), "returned_count")
    rows = "\n".join(
        _render_review_item_row(record, state_summaries) for record in records
    )
    if not rows:
        rows = """        <tr>
                    <td colspan="11">No seeded source-derived review records match the
                    current search.</td>
        </tr>"""
        returned_count = _int_value(_mapping(queue, "pagination"), "returned_count")
    no_results_notice = _render_no_results_notice(search_query, records)
    return _page(
                title="Complaint records ready for review",
                heading="Complaint records ready for review",
        actor_label=actor_label,
        main=f"""
        <section class="hero-card" aria-labelledby="reviewer-queue-heading">
            <h2 id="reviewer-queue-heading">{len(records)} complaint record(s) visible</h2>
            <p>Review imported source-derived complaint records, then add reviewer-created
            notes/status where supported. Source-derived data and reviewer-created state remain
            separate.</p>
            <p>{_next_review_item_markup(_next_review_item(records, state_summaries), state_summaries)}</p>
        </section>
        {_render_scope_notice(workflow)}
        <section aria-labelledby="reviewer-search-heading">
            <h2 id="reviewer-search-heading">Filter queue</h2>
                        <p>Use this queue for imported CCLD complaint records. For the primary pilot path,
                        start from facility lookup or the retrieval request page when possible.</p>
            {_render_reviewer_queue_navigation()}
      <form action="{REVIEWER_UI_RECORDS_PATH}" method="get">
        <p>
          <label for="q">Search seeded review records</label>
                    <input id="q" name="q" type="search" value="{_escape(search_query)}"
                        aria-describedby="reviewer-search-help">
                    <span id="reviewer-search-help">Search by complaint control number,
                    finding, facility/license number, source document ID, or loaded record key.</span>
        </p>
        <p>
          <button type="submit">Search</button>
          <a href="{REVIEWER_UI_RECORDS_PATH}">Clear search</a>
        </p>
      </form>
    </section>
        {no_results_notice}
    <section aria-labelledby="reviewer-list-heading">
            <h2 id="reviewer-list-heading">Queue records</h2>
                        <p>Showing {len(records)} of {returned_count} complaint records.</p>
                        {_render_reviewer_queue_summary(records, state_summaries)}
      <table>
                                <caption>Complaint records ready for review with source-derived fields and
                                reviewer-created status cues</caption>
        <thead>
          <tr>
                        <th scope="col">Review action</th>
            <th scope="col">Complaint control number</th>
                        <th scope="col">Finding</th>
                        <th scope="col">Facility/license</th>
                        <th scope="col">Complaint received date</th>
                        <th scope="col">Visit date</th>
                        <th scope="col">Report date</th>
                        <th scope="col">Reviewer status</th>
                        <th scope="col">Reviewer-created notes</th>
                                                <th scope="col">Source traceability</th>
                                                <th scope="col">Loaded record key</th>
          </tr>
        </thead>
        <tbody>
{rows}
        </tbody>
      </table>
    </section>""",
    )


def _render_no_results_notice(
        search_query: str,
        records: list[Mapping[str, Any]],
) -> str:
        if records:
                return ""
        if search_query:
                return f"""<section aria-labelledby="no-results-heading">
            <h2 id="no-results-heading">No matching seeded reviewer records</h2>
            <p>No seeded source-derived records match {_escape(search_query)}.</p>
            <p>Clear the search or return to the reviewer list to choose a seeded record.</p>
            <ul>
                <li><a href="{REVIEWER_UI_RECORDS_PATH}">Clear search</a></li>
                <li><a href="{REVIEWER_UI_PREFIX}">Return to reviewer home</a></li>
            </ul>
        </section>"""
        return f"""<section aria-labelledby="no-results-heading">
            <h2 id="no-results-heading">No seeded reviewer records are available</h2>
            <p>The local/test seeded corpus did not return reviewer records.</p>
            <p>Return to the reviewer home page and retry the local/test scaffold.</p>
            <ul>
                <li><a href="{REVIEWER_UI_PREFIX}">Return to reviewer home</a></li>
            </ul>
        </section>"""


def _render_reviewer_queue_navigation() -> str:
    return f"""<nav aria-label="Reviewer queue navigation">
            <ul>
                <li><a href="{CCLD_FACILITY_LOOKUP_PATH}">Find a CCLD facility</a></li>
                <li><a href="{CCLD_RECORD_REQUEST_PATH}">Open CCLD request or queue
                (CCLD request queue)</a></li>
                <li><a href="{CCLD_HELP_PATH}">Open CCLD workflow help</a></li>
            </ul>
        </nav>"""


def _render_reviewer_queue_summary(
    records: list[Mapping[str, Any]],
    state_summaries: Mapping[str, Mapping[str, Any]],
) -> str:
    counts = _reviewer_queue_status_counts(records, state_summaries)
    note_count = sum(
        1
        for record in records
        if _summary_int(_state_summary_for_item(record, state_summaries), "note_count") > 0
    )
    status_count = sum(
        1
        for record in records
        if _summary_optional_string(
            _state_summary_for_item(record, state_summaries),
            "latest_status",
        )
    )
    traceability_count = sum(1 for record in records if _has_visible_traceability(record))
    next_record = _next_review_item(records, state_summaries)
    status_cards = "\n".join(
        f"        <div class=\"stat-card\"><strong>{count}</strong><span>{_escape(label)}</span></div>"
        for label, count in (
            ("Not started", counts["not_started"]),
            ("In review", counts["in_review"]),
            ("Needs follow-up", counts["needs_follow_up"]),
            ("Reviewed", counts["reviewed"]),
            ("Blocked", counts["blocked"]),
        )
    )
    return f"""<section aria-labelledby="reviewer-queue-summary-heading">
        <h3 id="reviewer-queue-summary-heading">Queue status summary</h3>
        <p>This summary uses only loaded source-derived records and existing reviewer-created
        note/status rows. It does not save queue state or change source-derived records.</p>
        <p>List values are source-derived display summaries. Open reviewer detail for
        source-confidence cues before relying on missing, confusing, or proxy-related fields
        in reviewer-created notes/status or manual feedback.</p>
        <div class="stat-grid" aria-label="Reviewer status counts">
{status_cards}
        </div>
        <dl>
            <dt>Total visible records</dt>
            <dd>{len(records)}</dd>
            <dt>Records with reviewer-created notes</dt>
            <dd>{note_count}</dd>
            <dt>Records with reviewer-created status</dt>
            <dd>{status_count}</dd>
            <dt>Records with source traceability available</dt>
            <dd>{traceability_count}</dd>
            <dt>Suggested next record to open</dt>
            <dd>{_next_review_item_markup(next_record, state_summaries)}</dd>
        </dl>
    </section>"""


def _render_review_item_row(
    item: Mapping[str, Any],
    state_summaries: Mapping[str, Mapping[str, Any]],
) -> str:
    source_record = _mapping(item, "source_record")
    identity = _mapping(source_record, "identity")
    source_document = _mapping(source_record, "source_document")
    original_values = _mapping(source_record, "original_values")
    source_record_key = _string(identity, "source_record_key")
    detail_href = (
        f"{REVIEWER_UI_DETAIL_PATH}?"
        f"{urlencode({'source_record_key': source_record_key})}"
    )
    state_summary = state_summaries.get(source_record_key, _empty_state_summary())
    action_label = _review_action_label(original_values)
    return f"""        <tr>
                        <td><a class="button" href="{_escape(detail_href)}">{_escape(action_label)}</a></td>
          <td>{_escape(_optional_string(original_values, 'complaint_control_number'))}</td>
          <td>{_escape(_optional_string(original_values, 'finding'))}</td>
                    <td>{_escape(_optional_string(identity, 'facility_id'))}</td>
                    <td>{_escape(_optional_string(original_values, 'complaint_received_date'))}</td>
                    <td>{_escape(_optional_string(original_values, 'visit_date'))}</td>
                    <td>{_escape(_optional_string(original_values, 'report_date'))}</td>
          <td>{_escape(_latest_status_text(state_summary))}</td>
                    <td>{_escape(_notes_indicator_text(state_summary))}</td>
                    <td>{_escape(_source_traceability_cue(source_document))}</td>
                    <td>{_escape(source_record_key)}</td>
        </tr>"""


def _review_action_label(original_values: Mapping[str, Any]) -> str:
    complaint_control_number = original_values.get("complaint_control_number")
    if _has_display_value(complaint_control_number):
        return f"Open record {_display_value(complaint_control_number)}"
    return "Open record"


def _source_traceability_cue(source_document: Mapping[str, Any]) -> str:
    fields = (
        ("source URL", source_document.get("source_url")),
        ("raw SHA-256", source_document.get("raw_sha256")),
        ("connector", source_document.get("connector_name")),
        ("retrieval time", source_document.get("retrieved_at")),
    )
    present = [label for label, value in fields if _has_display_value(value)]
    if len(present) == len(fields):
        return "Source traceability available: source URL, raw SHA-256, connector, retrieval time."
    if present:
        return "Partial source traceability available: " + ", ".join(present) + "."
    return "Source traceability not visible in this local/test row."


def _queue_cue_text(summary: Mapping[str, Any]) -> str:
    status = _reviewer_queue_status(summary)
    note_count = _summary_int(summary, "note_count")
    if status == "not_started" and note_count == 0:
        return "Open next to begin review."
    if status == "not_started":
        return "Open next to review existing notes."
    if status == "in_review":
        return "Open next to continue review."
    if status == "needs_follow_up":
        return "Open next to resolve follow-up."
    if status == "blocked":
        return "Open when blocker context is needed."
    return "Open only if reviewed context needs checking."


def _reviewer_queue_status(summary: Mapping[str, Any]) -> str:
    latest_status = _summary_optional_string(summary, "latest_status")
    if latest_status in _REVIEWER_STATUS_LABELS:
        return latest_status
    return "not_started"


def _reviewer_queue_status_counts(
    records: list[Mapping[str, Any]],
    state_summaries: Mapping[str, Mapping[str, Any]],
) -> dict[str, int]:
    counts = {status: 0 for status in _REVIEWER_STATUS_ORDER}
    for record in records:
        counts[_reviewer_queue_status(_state_summary_for_item(record, state_summaries))] += 1
    return counts


def _state_summary_for_item(
    item: Mapping[str, Any],
    state_summaries: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any]:
    source_record = _mapping(item, "source_record")
    identity = _mapping(source_record, "identity")
    source_record_key = _string(identity, "source_record_key")
    return state_summaries.get(source_record_key, _empty_state_summary())


def _has_visible_traceability(item: Mapping[str, Any]) -> bool:
    source_record = _mapping(item, "source_record")
    source_document = _mapping(source_record, "source_document")
    return all(
        _has_display_value(source_document.get(key))
        for key in ("source_url", "raw_sha256", "connector_name", "retrieved_at")
    )


def _next_review_item(
    records: list[Mapping[str, Any]],
    state_summaries: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    for status in _NEXT_REVIEW_STATUS_ORDER:
        for record in records:
            if _reviewer_queue_status(_state_summary_for_item(record, state_summaries)) == status:
                return record
    return None


def _next_review_item_markup(
    item: Mapping[str, Any] | None,
    state_summaries: Mapping[str, Mapping[str, Any]],
) -> str:
    if item is None:
        return "No visible seeded complaint record is available."
    source_record = _mapping(item, "source_record")
    identity = _mapping(source_record, "identity")
    original_values = _mapping(source_record, "original_values")
    source_record_key = _string(identity, "source_record_key")
    detail_href = (
        f"{REVIEWER_UI_DETAIL_PATH}?"
        f"{urlencode({'source_record_key': source_record_key})}"
    )
    status = _REVIEWER_STATUS_LABELS[
        _reviewer_queue_status(_state_summary_for_item(item, state_summaries))
    ]
    label = _display_value(original_values.get("complaint_control_number") or source_record_key)
    return (
        f'<a href="{_escape(detail_href)}">Open reviewer detail for {_escape(label)}</a> '
        f'({_escape(status)})'
    )


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
        "has_status": latest_status is not None,
        "latest_status": latest_status,
        "latest_created_at": latest_created_at,
    }


def _empty_state_summary() -> Mapping[str, Any]:
    return {
        "total_rows": 0,
        "note_count": 0,
        "has_status": False,
        "latest_status": None,
        "latest_created_at": None,
    }


def _state_summary_text(summary: Mapping[str, Any]) -> str:
    total_rows = _summary_int(summary, "total_rows")
    latest_status = _summary_optional_string(summary, "latest_status")
    if total_rows == 0:
        return "No reviewer-created note/status yet"
    if latest_status is None:
        return "Needs review"
    return _REVIEWER_STATUS_LABELS.get(latest_status, latest_status.replace("_", " "))


def _notes_indicator_text(summary: Mapping[str, Any]) -> str:
    note_count = _summary_int(summary, "note_count")
    if note_count == 0:
        return "No reviewer-created notes"
    if note_count == 1:
        return "1 reviewer-created note"
    return f"{note_count} reviewer-created notes"


def _latest_status_text(summary: Mapping[str, Any]) -> str:
    latest_status = _summary_optional_string(summary, "latest_status")
    if latest_status is None:
        return "No reviewer-created status"
    return latest_status


def _latest_created_at_text(summary: Mapping[str, Any]) -> str:
    latest_created_at = _summary_optional_string(summary, "latest_created_at")
    if latest_created_at is None:
        return "No reviewer-created note/status yet"
    return latest_created_at


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


def _render_detail(
    payload: Mapping[str, Any],
    *,
    notice: str | None,
    related_records: list[Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
    actor_label: str | None,
) -> str:
    detail = _mapping(payload, "detail")
    source_record = _mapping(detail, "source_record")
    identity = _mapping(source_record, "identity")
    source_document = _mapping(source_record, "source_document")
    source_traceability = _mapping(source_record, "source_traceability")
    original_values = _mapping(source_record, "original_values")
    import_batch = _mapping(source_record, "import_batch")
    source_record_key = _string(identity, "source_record_key")
    complaint_heading = _detail_heading(original_values)
    return _page(
                title=complaint_heading,
                heading=complaint_heading,
        actor_label=actor_label,
        main=f"""
    {_render_notice(notice, source_record_key, related_records, return_context)}
                <section class="hero-card" aria-labelledby="detail-hero-heading">
                    <h2 id="detail-hero-heading">Complaint overview</h2>
                    <p>{_escape(_detail_summary_sentence(source_record, related_records))}</p>
                    <p><span class="badge badge-muted">Finding: {_escape(_optional_string(original_values, 'finding'))}</span></p>
                </section>
        {_render_record_summary_section(source_record, related_records, detail)}
                {_render_key_date_cards(original_values)}
                                {_render_source_traceability_section(
                                                identity,
                                                source_document,
                                                source_traceability,
                                                import_batch,
                                )}
        {_render_reviewer_state_section(detail)}
    <section aria-labelledby="source-derived-heading">
            <h2 id="source-derived-heading">Source-derived field details</h2>
            <p>These are safe scalar fields from the selected source-derived row. Narrative
            source text is hidden in this local/test browser UI.</p>
      <dl>
        <dt>Source record key</dt>
        <dd>{_escape(source_record_key)}</dd>
        <dt>Entity type</dt>
        <dd>{_escape(_string(identity, 'entity_type'))}</dd>
        <dt>Stable source ID</dt>
        <dd>{_escape(_string(identity, 'stable_source_id'))}</dd>
        <dt>Facility ID</dt>
        <dd>{_escape(_optional_string(identity, 'facility_id'))}</dd>
      </dl>
      <table>
        <caption>Safe source-derived values for the selected seeded record</caption>
        <thead>
          <tr>
            <th scope="col">Field</th>
            <th scope="col">Value</th>
          </tr>
        </thead>
        <tbody>
{_render_original_value_rows(original_values)}
        </tbody>
      </table>
    </section>
        {_render_source_confidence_cues_section(source_record, related_records)}
        {_render_field_note_guidance_section()}
        {_render_source_context_section(related_records, source_record_key)}
        {_render_review_actions(source_record_key, return_context)}
        {_render_detail_navigation(source_record_key, related_records, return_context)}
    {_render_scope_notice(_mapping(payload, 'workflow_shell'))}
        {_render_detail_first_run_steps(source_record_key, related_records, return_context)}
        {_render_detail_feedback_guidance(source_record, related_records, return_context)}""",
    )


def _detail_heading(original_values: Mapping[str, Any]) -> str:
    complaint_control_number = _optional_string(original_values, "complaint_control_number")
    if complaint_control_number != "unknown":
        return complaint_control_number
    return "Complaint record detail"


def _detail_summary_sentence(
    source_record: Mapping[str, Any],
    related_records: list[Mapping[str, Any]],
) -> str:
    original_values = _mapping(source_record, "original_values")
    facility = _facility_context(related_records)
    facility_name = _facility_context_value(facility, "facility_name")
    facility_number = _facility_context_value(facility, "external_facility_number")
    finding = _optional_string(original_values, "finding")
    control_number = _optional_string(original_values, "complaint_control_number")
    return (
        f"Complaint {control_number} for {facility_name} / {facility_number} has "
        f"source-derived finding {finding}. Review source traceability before adding "
        "reviewer-created notes/status."
    )


def _render_key_date_cards(original_values: Mapping[str, Any]) -> str:
    cards = "\n".join(
        f"        <div class=\"stat-card\"><strong>{_escape(value)}</strong><span>{_escape(label)}</span></div>"
        for label, value in (
            ("Complaint received", _optional_string(original_values, "complaint_received_date")),
            ("Visit", _optional_string(original_values, "visit_date")),
            ("Report", _optional_string(original_values, "report_date")),
            ("Signed", _optional_string(original_values, "date_signed")),
        )
    )
    return f"""<section aria-labelledby="key-dates-heading">
      <h2 id="key-dates-heading">Key dates and finding</h2>
      <div class="stat-grid">
{cards}
      </div>
    </section>"""


def _render_detail_first_run_steps(
    source_record_key: str,
    related_records: list[Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
) -> str:
    ccld_request_href = _ccld_request_href(related_records, return_context)
    return f"""<section aria-labelledby="detail-first-run-heading">
            <h2 id="detail-first-run-heading">First-run detail steps</h2>
            <p>This is the reviewer detail step of the same CCLD review session. Use it to
            confirm source traceability, read source-confidence cues and field-note guidance,
            and save reviewer notes/status only as tester-created observations.</p>
            <ol>
                <li>Confirm the selected complaint record in the record summary.</li>
                <li>Review the source traceability fields and source-context cues before adding
                reviewer-created notes or status.</li>
                <li>Check whether reviewer notes or statuses already exist.</li>
                <li>Add a note or status only after checking the source context and only if it
                helps the local/test review queue.</li>
                <li><a href="{_escape(ccld_request_href)}">Return to the CCLD request queue</a>
                with the same request context, resubmit when needed, and use the refreshed
                queue's suggested next record to continue.</li>
                <li>Copy the tester feedback checklist when ready.</li>
            </ol>
            <p>Next-record guidance is local/test navigation help derived from existing
            reviewer-created note/status cues. It is not a persisted assignment, automatic
            record claim, or official workflow state.</p>
            <p>Selected source record key: {_escape(source_record_key)}.</p>
        </section>"""


def _render_detail_navigation(
    source_record_key: str,
    related_records: list[Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
) -> str:
    detail_href = _reviewer_detail_href(source_record_key, return_context)
    ccld_request_href = _ccld_request_href(related_records, return_context)
    return f"""<section aria-labelledby="detail-navigation-heading">
      <h2 id="detail-navigation-heading">Detail navigation</h2>
            <ul>
                <li><a href="{_escape(ccld_request_href)}">Return to CCLD request or queue</a></li>
                <li><a href="{CCLD_FACILITY_LOOKUP_PATH}">Find another CCLD facility</a></li>
                <li><a href="{CCLD_HELP_PATH}">Open CCLD workflow help</a></li>
                <li><a href="{REVIEWER_UI_RECORDS_PATH}">Back to reviewer records</a></li>
                <li><a href="{_escape(detail_href)}">Refresh this seeded detail</a></li>
                <li><a href="#record-summary-heading">Review record summary</a></li>
                <li><a href="#source-confidence-heading">Review source-confidence cues</a></li>
                <li><a href="#field-note-guidance-heading">Review field-note guidance</a></li>
                <li><a href="#traceability-heading">Review source traceability</a></li>
                <li><a href="#source-context-heading">Review source-derived context</a></li>
                <li><a href="#reviewer-state-heading">Review notes and statuses</a></li>
                <li><a href="#review-actions-heading">Add note or status</a></li>
                <li><a href="#detail-feedback-heading">Prepare tester feedback</a></li>
            </ul>
        </section>"""


def _render_record_summary_section(
    source_record: Mapping[str, Any],
    related_records: list[Mapping[str, Any]],
    detail: Mapping[str, Any],
) -> str:
    identity = _mapping(source_record, "identity")
    source_document = _mapping(source_record, "source_document")
    original_values = _mapping(source_record, "original_values")
    state_summary = _mapping(detail, "associated_reviewer_created_state_summary")
    facility = _facility_context(related_records)
    facility_number = _facility_context_value(facility, "external_facility_number")
    facility_name = _facility_context_value(facility, "facility_name")
    reviewer_statuses = ", ".join(_string_items(state_summary.get("reviewer_statuses_present", [])))
    if not reviewer_statuses:
        reviewer_statuses = "None recorded"
    return f"""<section aria-labelledby="record-summary-heading">
      <h2 id="record-summary-heading">Record summary</h2>
      <p>This summary orients the selected local/test CCLD complaint record before a tester
      reviews source traceability, related context, and reviewer-created notes or status.</p>
      <dl>
        <dt>Complaint control number</dt>
        <dd>{_escape(_optional_string(original_values, 'complaint_control_number'))}</dd>
        <dt>Finding</dt>
        <dd>{_escape(_optional_string(original_values, 'finding'))}</dd>
        <dt>Complaint and report dates</dt>
        <dd>{_escape(_date_summary(original_values))}</dd>
        <dt>Facility/license number</dt>
        <dd>{_escape(facility_number)}</dd>
        <dt>Facility name</dt>
        <dd>{_escape(facility_name)}</dd>
        <dt>Selected source record key</dt>
        <dd>{_escape(_string(identity, 'source_record_key'))}</dd>
        <dt>Source document ID</dt>
        <dd>{_escape(_string(source_document, 'source_document_id'))}</dd>
        <dt>Reviewer-created status recorded</dt>
        <dd>{_escape(reviewer_statuses)}</dd>
      </dl>
    </section>"""


def _render_source_confidence_cues_section(
    source_record: Mapping[str, Any],
    related_records: list[Mapping[str, Any]],
) -> str:
    original_values = _mapping(source_record, "original_values")
    facility = _facility_context(related_records)
    rows = "\n".join(
        (
            _render_source_confidence_field_row(
                label,
                original_values.get(field_name),
                guidance,
            )
            for label, field_name, guidance in _SOURCE_CONFIDENCE_COMPLAINT_FIELDS
        )
    )
    rows = "\n".join(
        (
            _render_source_confidence_field_row(
                "Facility/license number",
                None if facility is None else facility.get("external_facility_number"),
                "Use this to confirm the detail matches the CCLD request context.",
            ),
            rows,
            _render_first_activity_confidence_row(original_values),
            _render_report_date_proxy_confidence_row(original_values),
        )
    )
    return f"""<section id="source-confidence-heading" aria-labelledby="source-confidence-title">
            <h2 id="source-confidence-title">Source-confidence cues</h2>
            <p>These cues summarize visible source-derived complaint fields already loaded in
            this local/test record. They help testers see which values are present, which
            expected values are not available locally, and which fields need source traceability
            review before a reviewer-created note or status observation relies on them.</p>
            <p>This section is not a source-confidence score, automated source verification,
            public-source absence finding, record-completeness claim, legal conclusion, or
            facility-wide conclusion.</p>
            <p>Missing local/test values should be described in reviewer-created notes/status or
            manual feedback as <q>not available in this local/test record</q>, not as source
            absence, record incompleteness, or data loss.</p>
            <table>
                <caption>Source-confidence cues for visible complaint fields</caption>
                <thead>
                    <tr>
                        <th scope="col">Complaint field</th>
                        <th scope="col">Source-confidence cue</th>
                        <th scope="col">Value shown</th>
                        <th scope="col">How to use it</th>
                    </tr>
                </thead>
                <tbody>
{rows}
                </tbody>
            </table>
        </section>"""


def _render_source_confidence_field_row(
    label: str,
    value: object,
    guidance: str,
) -> str:
    return f"""          <tr>
                        <th scope="row">{_escape(label)}</th>
                        <td>{_escape(_source_confidence_cue(value))}</td>
                        <td>{_escape(_source_confidence_value(value))}</td>
                        <td>{_escape(guidance)}</td>
                    </tr>"""


def _render_first_activity_confidence_row(values: Mapping[str, Any]) -> str:
    value = values.get("first_investigation_activity_date")
    missing_flag = values.get("missing_first_activity_date")
    cue = _source_confidence_cue(value)
    if not _has_display_value(value) and missing_flag is True:
        cue = (
            "Not available in this local/test record. The local/test missing-field "
            "flag is true."
        )
    return f"""          <tr>
                        <th scope="row">First investigation activity date</th>
                        <td>{_escape(cue)}</td>
                        <td>{_escape(_source_confidence_value(value))}</td>
                        <td>When relevant, say this value is not available locally; do not say
                        investigation activity did or did not happen.</td>
                    </tr>"""


def _render_report_date_proxy_confidence_row(values: Mapping[str, Any]) -> str:
    value = values.get("report_date_used_as_proxy")
    if value is True:
        cue = "Fallback/proxy-derived delay basis indicated by current local/test field."
    elif value is False:
        cue = "Current local/test field does not mark report date as the delay-review proxy."
    else:
        cue = "Not available in this local/test record."
    return f"""          <tr>
                        <th scope="row">Report date proxy flag</th>
                        <td>{_escape(cue)}</td>
                        <td>{_escape(_source_confidence_value(value))}</td>
                        <td>Use fallback/proxy wording only when this cue says the current
                        local/test field identifies a proxy-derived delay basis.</td>
                    </tr>"""


def _source_confidence_cue(value: object) -> str:
    if _has_display_value(value):
        return "Present in this local/test source-derived record."
    return "Not available in this local/test record."


def _source_confidence_value(value: object) -> str:
    if not _has_display_value(value):
        return "not available in this local/test record"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return _display_value(value)


def _render_source_traceability_section(
    identity: Mapping[str, Any],
    source_document: Mapping[str, Any],
    source_traceability: Mapping[str, Any],
    import_batch: Mapping[str, Any],
) -> str:
    return f"""<section id="traceability-heading" aria-labelledby="traceability-title">
      <h2 id="traceability-title">Source traceability</h2>
      <p>Use these fields to confirm which local/test source-derived complaint record is
      selected and how it remains tied to preserved public-source material before adding a
      reviewer-created note or status.</p>
      <p>Missing values are shown as <q>not available in this local/test record</q>. A missing
      local/test value is not proof that the public source lacks a record or that any event did
      or did not happen.</p>
      <p>This page is a local/test review aid. It does not make legal, facility-wide,
      completeness, harm, abuse, neglect, liability, or automated complaint-finding
      conclusions.</p>
      <table>
        <caption>Selected complaint source traceability fields</caption>
        <thead>
          <tr>
            <th scope="col">Traceability cue</th>
            <th scope="col">Value shown for this selected record</th>
            <th scope="col">How to use it during local/test review</th>
          </tr>
        </thead>
        <tbody>
{_render_traceability_field_rows(identity, source_document, source_traceability, import_batch)}
        </tbody>
      </table>
      {_render_traceability_summary(source_document, source_traceability, import_batch)}
    </section>"""


def _render_field_note_guidance_section() -> str:
    return """<section id="field-note-guidance-heading"
            aria-labelledby="field-note-guidance-title">
            <h2 id="field-note-guidance-title">Field-note guidance</h2>
            <p>Use this guidance after checking source traceability and the source-confidence
            cues. Reviewer notes/status are reviewer-created observations for this local/test
            queue; they do not edit source-derived fields.</p>
            <p>Keep notes short and cautious. When a value is unclear, describe what the
            local/test page showed and what still needs checking rather than making a source,
            legal, facility-wide, or official finding.</p>
            <table>
                <caption>Cautious wording for reviewer-created notes/status</caption>
                <thead>
                    <tr>
                        <th scope="col">What the cue shows</th>
                        <th scope="col">Careful reviewer-created wording</th>
                        <th scope="col">Avoid saying</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <th scope="row">Field is present</th>
                        <td>Say the local/test record shows the value and name the field you
                        checked. Example: local/test record shows complaint received date.</td>
                        <td>Do not say the value is legally verified or an official finding.</td>
                    </tr>
                    <tr>
                        <th scope="row">Field is not available locally</th>
                        <td>Say the field is not available in this local/test record.</td>
                        <td>Do not say the source does not contain this, the record is incomplete,
                        or data was lost.</td>
                    </tr>
                    <tr>
                        <th scope="row">Report-date proxy flag is shown</th>
                        <td>Say the local/test cue marks report date as a proxy before using delay
                        wording.</td>
                        <td>Do not use the proxy flag alone to say an investigation did or did not
                        happen, or that a delay is proven.</td>
                    </tr>
                    <tr>
                        <th scope="row">Field remains confusing after source traceability</th>
                        <td>Say the field remained unclear after checking source traceability and
                        include the field label or source document ID when useful.</td>
                        <td>Do not turn uncertainty into a public-source absence or facility-wide
                        conclusion.</td>
                    </tr>
                    <tr>
                        <th scope="row">Value looks like a UI or data issue</th>
                        <td>Use the manual feedback checklist for suspected wording, display, or
                        local/test data issues instead of treating the note as a source-derived
                        edit.</td>
                        <td>Do not imply the app corrected, edited, or replaced the source-derived
                        record.</td>
                    </tr>
                </tbody>
            </table>
        </section>"""


def _render_traceability_field_rows(
    identity: Mapping[str, Any],
    source_document: Mapping[str, Any],
    source_traceability: Mapping[str, Any],
    import_batch: Mapping[str, Any],
) -> str:
    fields = (
        (
            "Selected source record key",
            identity.get("source_record_key"),
            "Use this when reporting which reviewer detail page was open.",
        ),
        (
            "Stable source identity",
            identity.get("stable_source_id"),
            "Use this to distinguish the selected complaint from related local/test rows.",
        ),
        (
            "Source document ID",
            source_document.get("source_document_id"),
            "Use this to connect the complaint to its source document row.",
        ),
        (
            "Source URL",
            source_document.get("source_url"),
            "Use this as the public-source pointer when checking the source of record.",
        ),
        (
            "Raw SHA-256",
            source_document.get("raw_sha256"),
            "Use this to identify the preserved raw source bytes in local/test evidence.",
        ),
        (
            "Raw artifact preservation",
            _raw_artifact_display(source_document.get("raw_path")),
            "Use this cue to know whether raw artifact preservation is represented; raw paths are not shown in the browser.",
        ),
        (
            "Source artifact identity",
            source_traceability.get("source_artifact_identity"),
            "Use this to identify the local/test seeded-corpus artifact used for this page.",
        ),
        (
            "Report index or source page marker",
            source_traceability.get("report_index"),
            "Use this to match the selected detail back to the CCLD report/page marker "
            "when present.",
        ),
        (
            "Connector name and version",
            _connector_label(source_document),
            "Use this to report which deterministic local/test connector produced the row.",
        ),
        (
            "Retrieved at capture time",
            source_document.get("retrieved_at"),
            "Use this as the local/test capture timestamp, not as a public-source "
            "completeness claim.",
        ),
        (
            "Import batch ID",
            import_batch.get("import_batch_id"),
            "Use this to identify the local/test seeded import batch.",
        ),
        (
            "Import validation status",
            import_batch.get("validation_status"),
            "Use this to report local/test artifact validation state without changing source data.",
        ),
        (
            "Raw hash validation status",
            import_batch.get("raw_hash_validation_status"),
            "Use this to report local/test hash validation state.",
        ),
    )
    return "\n".join(
        _render_traceability_field_row(label, value, guidance)
        for label, value, guidance in fields
    )


def _render_traceability_field_row(label: str, value: object, guidance: str) -> str:
    return f"""          <tr>
            <th scope="row">{_escape(label)}</th>
            <td>{_escape(_traceability_value(value))}</td>
            <td>{_escape(guidance)}</td>
          </tr>"""


def _connector_label(source_document: Mapping[str, Any]) -> str:
    connector_name = source_document.get("connector_name")
    connector_version = source_document.get("connector_version")
    if _has_display_value(connector_name) and _has_display_value(connector_version):
        return f"{connector_name} {connector_version}"
    if _has_display_value(connector_name):
        return str(connector_name)
    if _has_display_value(connector_version):
        return str(connector_version)
    return ""


def _raw_artifact_display(value: object) -> str:
    if _has_display_value(value):
        return "available server-side; raw path not shown"
    return "not available in this local/test record"


def _traceability_value(value: object) -> str:
    if not _has_display_value(value):
        return "not available in this local/test record"
    return _display_value(value)


def _render_traceability_summary(
        source_document: Mapping[str, Any],
        source_traceability: Mapping[str, Any],
        import_batch: Mapping[str, Any],
) -> str:
        rows = "\n".join(
                _render_traceability_summary_row(label, value)
                for label, value in (
                        ("Source URL", source_document.get("source_url")),
                        ("Raw SHA-256", source_document.get("raw_sha256")),
                        ("Raw artifact preservation", _raw_artifact_display(source_document.get("raw_path"))),
                        ("Connector", source_document.get("connector_name")),
                        ("Retrieved at", source_document.get("retrieved_at")),
                        ("Report index", source_traceability.get("report_index")),
                        ("Import validation", import_batch.get("validation_status")),
                        ("Raw hash validation", import_batch.get("raw_hash_validation_status")),
                )
        )
        return f"""<p>Use these fields to confirm that the selected record remains tied to
            preserved public-source material. This summary reports whether each field is
            visible; it is not a legal or completeness conclusion.</p>
            <table>
                <caption>Visible source traceability summary</caption>
                <thead>
                    <tr>
                        <th scope="col">Traceability field</th>
                        <th scope="col">Visibility</th>
                    </tr>
                </thead>
                <tbody>
{rows}
                </tbody>
            </table>"""


def _render_traceability_summary_row(label: str, value: object) -> str:
    visibility = (
        "available" if _has_display_value(value) else "not available in this local/test record"
    )
    return f"""          <tr>
                        <th scope="row">{_escape(label)}</th>
                        <td>{_escape(visibility)}</td>
                    </tr>"""


def _render_source_context_section(
        related_records: list[Mapping[str, Any]],
        selected_source_record_key: str,
) -> str:
        rows = "\n".join(
                _render_related_source_record_row(record, selected_source_record_key)
                for record in related_records
        )
        if not rows:
                rows = """        <tr>
                    <td colspan="5">No related seeded source-derived rows are available.</td>
                </tr>"""
        return f"""<section id="source-context-heading" aria-labelledby="source-context-title">
            <h2 id="source-context-title">Related seeded source-derived context</h2>
            <p>This context comes from the same authenticated local/test source-derived
            read seam as the selected record. Narrative fields are not shown in this
            browser shell.</p>
            <p>Use this section to distinguish the selected complaint from related facility,
            source document, allegation, event, and extraction-audit rows already present in
            the seeded bundle.</p>
            {_render_source_context_summary(related_records)}
            <table>
                <caption>Safe related source-derived rows in the selected seeded bundle</caption>
                <thead>
                    <tr>
                        <th scope="col">Entity type</th>
                        <th scope="col">Stable source ID</th>
                        <th scope="col">Source document ID</th>
                        <th scope="col">Relationship</th>
                        <th scope="col">Safe context shown</th>
                    </tr>
                </thead>
                <tbody>
{rows}
                </tbody>
            </table>
        </section>"""


def _render_source_context_summary(related_records: list[Mapping[str, Any]]) -> str:
        counts = _related_entity_counts(related_records)
        rows = "\n".join(
                f"""        <tr>
                    <th scope="row">{_escape(entity_type)}</th>
                    <td>{count}</td>
                </tr>"""
                for entity_type, count in counts.items()
        )
        if not rows:
                rows = """        <tr>
                    <td colspan="2">No related source-derived rows are available.</td>
                </tr>"""
        return f"""<table>
                <caption>Selected source-derived bundle summary</caption>
                <thead>
                    <tr>
                        <th scope="col">Entity type</th>
                        <th scope="col">Related rows</th>
                    </tr>
                </thead>
                <tbody>
{rows}
                </tbody>
            </table>"""


def _render_related_source_record_row(
        record: Mapping[str, Any],
        selected_source_record_key: str,
) -> str:
    source_record_key = _string(record, "source_record_key")
    entity_type = _string(record, "entity_type")
    relationship = (
        "Selected record"
        if source_record_key == selected_source_record_key
        else "Same seeded bundle"
    )
    return f"""        <tr>
                    <th scope="row">{_escape(entity_type)}</th>
                    <td>{_escape(_string(record, 'stable_source_id'))}</td>
                    <td>{_escape(_string(record, 'source_document_id'))}</td>
                    <td>{_escape(relationship)}</td>
                    <td>{_escape(_safe_context_summary(record))}</td>
                </tr>"""


def _related_source_records(
    selected_source_record: Mapping[str, Any],
    records: list[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    identity = _mapping(selected_source_record, "identity")
    selected_source_record_key = _string(identity, "source_record_key")
    selected_source_document = _mapping(selected_source_record, "source_document")
    selected_source_document_id = _string(selected_source_document, "source_document_id")
    selected_facility_id = _optional_string(identity, "facility_id")
    related_records = [
        record
        for record in records
        if _is_related_source_record(
            record,
            selected_source_record_key=selected_source_record_key,
            selected_source_document_id=selected_source_document_id,
            selected_facility_id=selected_facility_id,
        )
    ]
    return sorted(
        related_records,
        key=lambda record: (
            _SOURCE_CONTEXT_ENTITY_ORDER.get(_string(record, "entity_type"), 99),
            _string(record, "stable_source_id"),
        ),
    )


def _is_related_source_record(
    record: Mapping[str, Any],
    *,
    selected_source_record_key: str,
    selected_source_document_id: str,
    selected_facility_id: str,
) -> bool:
    if _string(record, "source_record_key") == selected_source_record_key:
        return True
    if _optional_string(record, "source_document_id") == selected_source_document_id:
        return True
    if selected_facility_id != "unknown":
        return _optional_string(record, "facility_id") == selected_facility_id
    return False


def _related_entity_counts(records: list[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        entity_type = _string(record, "entity_type")
        counts[entity_type] = counts.get(entity_type, 0) + 1
    return dict(
        sorted(
            counts.items(),
            key=lambda item: (_SOURCE_CONTEXT_ENTITY_ORDER.get(item[0], 99), item[0]),
        )
    )


def _safe_context_summary(record: Mapping[str, Any]) -> str:
    entity_type = _string(record, "entity_type")
    original_values = _mapping(record, "original_values")
    fields = _SAFE_CONTEXT_FIELDS_BY_ENTITY.get(entity_type, ())
    values = [
        f"{field}: {_display_value(original_values[field])}"
        for field in fields
        if field in original_values and _has_display_value(original_values[field])
    ]
    if entity_type == "allegation":
        values.append("allegation_text: hidden in this local/test UI")
    if not values:
        return "No safe scalar context fields available"
    return "; ".join(values)


def _facility_context(
    related_records: list[Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    for record in related_records:
        if _string(record, "entity_type") == "facility":
            return _mapping(record, "original_values")
    return None


def _facility_context_value(
    facility: Mapping[str, Any] | None,
    key: str,
) -> str:
    if facility is None:
        return "unknown"
    value = facility.get(key)
    if value is None:
        return "unknown"
    if isinstance(value, str) and not value.strip():
        return "unknown"
    return _display_value(value)


def _ccld_request_href(
    related_records: list[Mapping[str, Any]],
    return_context: CcldQueueReturnContext | None = None,
) -> str:
    if return_context is not None and return_context.facility_number:
        query_values = {
            "facility_number": return_context.facility_number,
            "start_date": return_context.start_date or "",
            "end_date": return_context.end_date or "",
            "request_context_origin": return_context.context_origin or "manual_entry",
            "lookup_facility_name": return_context.lookup_facility_name or "",
        }
        return f"{CCLD_RECORD_REQUEST_PATH}?{urlencode(query_values)}"
    facility = _facility_context(related_records)
    facility_number = _facility_context_value(facility, "external_facility_number")
    if facility_number == "unknown":
        return CCLD_RECORD_REQUEST_PATH
    return f"{CCLD_RECORD_REQUEST_PATH}?{urlencode({'facility_number': facility_number})}"


def _return_context_from_values(
    values: Mapping[str, list[str]],
    *,
    related_records: list[Mapping[str, Any]] | None,
) -> CcldQueueReturnContext:
    context = CcldQueueReturnContext(
        facility_number=_optional_form_value(values, "return_facility_number"),
        start_date=_optional_form_value(values, "return_start_date"),
        end_date=_optional_form_value(values, "return_end_date"),
        context_origin=_optional_form_value(values, "return_context_origin"),
        lookup_facility_name=_optional_form_value(values, "return_lookup_facility_name"),
    )
    if related_records is None:
        return context
    return _return_context_with_related_defaults(context, related_records)


def _return_context_with_related_defaults(
    context: CcldQueueReturnContext,
    related_records: list[Mapping[str, Any]],
) -> CcldQueueReturnContext:
    if context.facility_number:
        return context
    facility = _facility_context(related_records)
    facility_number = _facility_context_value(facility, "external_facility_number")
    if facility_number == "unknown":
        return context
    return CcldQueueReturnContext(
        facility_number=facility_number,
        start_date=context.start_date,
        end_date=context.end_date,
        context_origin=context.context_origin or "prefilled_link",
        lookup_facility_name=context.lookup_facility_name,
    )


def _return_context_hidden_inputs(return_context: CcldQueueReturnContext) -> str:
    return "\n".join(
        f'<input type="hidden" name="{_escape(name)}" value="{_escape(value)}">'
        for name, value in _return_context_form_values(return_context)
    )


def _return_context_hidden_summary(return_context: CcldQueueReturnContext) -> str:
    if return_context.facility_number is None:
        return ""
    return f"""<section aria-labelledby="return-context-heading">
            <h3 id="return-context-heading">Return to the same CCLD queue</h3>
            <p>After saving a note or status, return to this same local/test CCLD request
            context and submit the request again to see queue progress and note/status cues
            derived from reviewer-created state.</p>
            <dl>
                <dt>Facility/license number to reuse</dt>
                <dd>{_escape(return_context.facility_number)}</dd>
                <dt>Date range to reuse</dt>
                <dd>{_escape(_return_context_date_range(return_context))}</dd>
            </dl>
        </section>"""


def _return_context_form_values(
    return_context: CcldQueueReturnContext,
) -> tuple[tuple[str, str], ...]:
    return tuple(
        (name, value or "")
        for name, value in (
            ("return_facility_number", return_context.facility_number),
            ("return_start_date", return_context.start_date),
            ("return_end_date", return_context.end_date),
            ("return_context_origin", return_context.context_origin),
            ("return_lookup_facility_name", return_context.lookup_facility_name),
        )
    )


def _return_context_date_range(return_context: CcldQueueReturnContext) -> str:
    if return_context.start_date is None and return_context.end_date is None:
        return "not provided"
    start_date = return_context.start_date or "earliest available"
    end_date = return_context.end_date or "latest available"
    return f"{start_date} to {end_date}"


def _optional_form_value(values: Mapping[str, list[str]], key: str) -> str | None:
    value = _first_form_value(values, key)
    return value or None


def _date_summary(values: Mapping[str, Any]) -> str:
    parts = []
    for field_name in (
        "complaint_received_date",
        "visit_date",
        "report_date",
        "date_signed",
    ):
        value = values.get(field_name)
        if _has_display_value(value):
            parts.append(f"{field_name}: {_display_value(value)}")
    if not parts:
        return "No complaint or report dates listed"
    return "; ".join(parts)


def _has_display_value(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _render_reviewer_state_section(detail: Mapping[str, Any]) -> str:
    associated_state = _mapping(detail, "associated_reviewer_created_state")
    summary = _mapping(detail, "associated_reviewer_created_state_summary")
    rows = "\n".join(
        _render_reviewer_state_row(record)
        for record in _record_list(associated_state, "reviewer_created_state")
    )
    if not rows:
        rows = """        <tr>
          <td colspan="5">No reviewer-created state has been recorded for this seeded record.</td>
        </tr>"""
    statuses = ", ".join(_string_items(summary.get("reviewer_statuses_present", [])))
    if not statuses:
        statuses = "None recorded"
    payload_kinds = ", ".join(_string_items(summary.get("payload_kinds_present", [])))
    if not payload_kinds:
        payload_kinds = "None recorded"
    latest_created_at = summary.get("latest_created_at")
    latest_display = (
        latest_created_at if isinstance(latest_created_at, str) else "None recorded"
    )
    return f"""<section aria-labelledby="reviewer-state-heading">
      <h2 id="reviewer-state-heading">Reviewer-created state</h2>
      <p>Reviewer-created state is stored separately from the selected source-derived record.</p>
      <p>UI actions add reviewer-created rows and audit rows; they do not edit
      source-derived fields.</p>
    <p>Use this section to see whether another local/test reviewer has already left a
    note or status for the selected record.</p>
      <dl>
        <dt>Total associated rows</dt>
        <dd>{_escape(str(_int_value(summary, 'total_associated_rows')))}</dd>
        <dt>Reviewer-created statuses present</dt>
        <dd>{_escape(statuses)}</dd>
                <dt>Reviewer-created payload kinds present</dt>
                <dd>{_escape(payload_kinds)}</dd>
                <dt>Latest reviewer-created row</dt>
                <dd>{_escape(latest_display)}</dd>
      </dl>
      <table>
        <caption>Reviewer-created notes and statuses for this source-derived record</caption>
        <thead>
          <tr>
            <th scope="col">Kind</th>
            <th scope="col">Value</th>
            <th scope="col">Created at</th>
            <th scope="col">Created by</th>
            <th scope="col">Boundary</th>
          </tr>
        </thead>
        <tbody>
{rows}
        </tbody>
      </table>
    </section>"""


def _render_review_actions(
    source_record_key: str,
    return_context: CcldQueueReturnContext,
) -> str:
        return f"""<section id="review-actions-heading" aria-labelledby="review-actions-title">
            <h2 id="review-actions-title">Reviewer actions</h2>
            <p>These local/test actions write reviewer-created state through the
            existing authenticated workflow actions. They do not edit source-derived
            fields.</p>
            <p>Review the source traceability, source-confidence cues, and field-note guidance
            first. Then add a short note when source traceability, wording, missing local/test
            values, proxy flags, or review context needs follow-up. Set a status to keep queue
            progress understandable.</p>
            {_return_context_hidden_summary(return_context)}
            {_render_note_form(source_record_key, return_context)}
            {_render_status_form(source_record_key, return_context)}
        </section>"""


def _render_reviewer_state_row(record: Mapping[str, Any]) -> str:
    state_payload = _mapping(record, "state_payload")
    created_by = _mapping(record, "created_by")
    payload_kind = _optional_string(state_payload, "payload_kind")
    value = _reviewer_state_value(state_payload)
    actor_label = _actor_label(created_by)
    return f"""        <tr>
          <td>{_escape(payload_kind or _string(record, 'state_kind'))}</td>
          <td>{_escape(value)}</td>
          <td>{_escape(_string(record, 'created_at'))}</td>
          <td>{_escape(actor_label)}</td>
          <td>Reviewer-created; source-derived record unchanged</td>
        </tr>"""


def _reviewer_state_value(state_payload: Mapping[str, Any]) -> str:
    note_text = state_payload.get("note_text")
    if isinstance(note_text, str):
        return note_text
    reviewer_status = state_payload.get("reviewer_status")
    if isinstance(reviewer_status, str):
        return reviewer_status
    return "Local/test scaffold row"


def _actor_label(created_by: Mapping[str, Any]) -> str:
    display_name = created_by.get("display_name")
    actor_category = _optional_string(created_by, "actor_category") or "actor"
    if isinstance(display_name, str) and display_name.strip():
        return f"{display_name.strip()} ({actor_category})"
    return actor_category


def _render_note_form(
        source_record_key: str,
        return_context: CcldQueueReturnContext,
) -> str:
    return f"""<section aria-labelledby="note-form-heading">
    <h3 id="note-form-heading">Add reviewer note</h3>
      <form action="{REVIEWER_UI_NOTE_PATH}" method="post">
        <input type="hidden" name="source_record_key" value="{_escape(source_record_key)}">
                {_return_context_hidden_inputs(return_context)}
        <p>
                    <label for="note_text">Reviewer note for this record</label>
                    <textarea id="note_text" name="note_text" rows="4" required
                        aria-describedby="note-text-help"></textarea>
                                            <span id="note-text-help">
                                        Use safe plain text. Notes appear below after saving.
                                        They do not change the source-derived record.</span>
        </p>
                <p><button type="submit">Save reviewer note for this record</button></p>
      </form>
    </section>"""


def _render_status_form(
    source_record_key: str,
    return_context: CcldQueueReturnContext,
) -> str:
    options = "\n".join(
        _render_status_option(status)
        for status in REVIEWER_STATUS_VALUES
    )
    return f"""<section aria-labelledby="status-form-heading">
            <h3 id="status-form-heading">Set reviewer status</h3>
      <form action="{REVIEWER_UI_STATUS_PATH}" method="post">
        <input type="hidden" name="source_record_key" value="{_escape(source_record_key)}">
                {_return_context_hidden_inputs(return_context)}
        <p>
          <label for="reviewer_status">Reviewer queue status for this record</label>
                    <select id="reviewer_status" name="reviewer_status" required
                        aria-describedby="reviewer-status-help">
{options}
          </select>
                    <span id="reviewer-status-help">Status is reviewer-created local/test state for
                    queue progress, appears below after saving, and is not a public-source
                    finding.</span>
        </p>
                <p><button type="submit">Save reviewer status for this record</button></p>
      </form>
    </section>"""


def _render_detail_feedback_guidance(
    source_record: Mapping[str, Any],
    related_records: list[Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
) -> str:
    identity = _mapping(source_record, "identity")
    original_values = _mapping(source_record, "original_values")
    source_document = _mapping(source_record, "source_document")
    facility = _facility_context(related_records)
    ccld_request_href = _ccld_request_href(related_records, return_context)
    return f"""<section id="detail-feedback-heading" aria-labelledby="detail-feedback-title">
            <h2 id="detail-feedback-title">Feedback clues for this record</h2>
            <p>If this detail looks wrong or incomplete, return to the CCLD request page and copy
            the tester feedback checklist. Include the record identifiers below and describe what
            looked missing, confusing, or unexpected.</p>
            <p>If source traceability fields are confusing or missing, report the field label and
            the wording shown on this page. Do not treat missing local/test traceability display
            as proof of public-source completeness or absence.</p>
            <p>Feedback remains manual-copy only. Return to the same CCLD request queue,
            resubmit the request when needed, and use the existing manual feedback checklist;
            this detail page does not create a second checklist or save feedback.</p>
            <dl>
                <dt>Facility/license number</dt>
                <dd>{_escape(_facility_context_value(facility, 'external_facility_number'))}</dd>
                <dt>Complaint control number</dt>
                <dd>{_escape(_optional_string(original_values, 'complaint_control_number'))}</dd>
                <dt>Source record key</dt>
                <dd>{_escape(_string(identity, 'source_record_key'))}</dd>
                <dt>Source document ID</dt>
                <dd>{_escape(_string(source_document, 'source_document_id'))}</dd>
                <dt>Return request context</dt>
                <dd>{_escape(_detail_feedback_request_context(return_context))}</dd>
            </dl>
            <section aria-labelledby="record-feedback-handoff-heading">
                <h3 id="record-feedback-handoff-heading">Record-specific feedback handoff</h3>
                <p>Carry these observations into the existing manual feedback checklist when
                they apply. This page does not save, send, export, or persist feedback.</p>
                <ul>
                    <li>Source traceability observations: fields that were easy to confirm,
                    missing, or confusing.</li>
                    <li>Source context confusion: unclear related source rows, hidden narrative
                    expectations, or labels that made this complaint hard to identify.</li>
                    <li>Request-context fit: whether this complaint seemed unexpected for the
                    facility/date request you used to open it.</li>
                    <li>Note/status behavior: whether the save confirmation appeared, the saved
                    reviewer-created state was visible, and the return-to-queue link worked.</li>
                    <li>Queue refresh behavior: whether returning to the same CCLD request
                    context and resubmitting showed understandable progress and status cues.</li>
                    <li>Friction: confusing labels, wording, keyboard flow, or next steps that
                    slowed record review.</li>
                </ul>
            </section>
            <section aria-labelledby="feedback-checklist-bridge-heading">
                <h3 id="feedback-checklist-bridge-heading">Manual feedback checklist bridge</h3>
                <p>Use the existing manual feedback checklist on the CCLD request queue for
                record-specific observations from this detail. Do not create a separate
                checklist from this page.</p>
                <p>Use that same checklist for queue-level observations and detail-level
                observations so request context, queue filters, source traceability,
                source-confidence cues, field-note uncertainty, note/status confirmation,
                return-to-queue refresh, and suggested-next-record confusion stay together.</p>
                <ul>
                    <li>Source traceability: note fields that were easy to confirm, missing, or
                    confusing.</li>
                    <li>Source-confidence cues: note present values, values not available in the
                    local/test record, or proxy-flag context that affected review.</li>
                    <li>Field-note uncertainty: note wording you were unsure how to phrase after
                    checking source traceability.</li>
                    <li>Note/status confirmation: note whether the saved reviewer-created state
                    appeared and stayed separate from source-derived fields.</li>
                    <li>Return-to-queue flow: note whether returning to the same request context,
                    refreshing queue progress, or choosing the suggested next record was
                    confusing.</li>
                </ul>
            </section>
            <ul>
                <li><a href="{_escape(ccld_request_href)}">Return to CCLD request or queue</a></li>
                <li><a href="{CCLD_HELP_PATH}">Open CCLD workflow help</a></li>
            </ul>
        </section>"""


def _detail_feedback_request_context(return_context: CcldQueueReturnContext) -> str:
    if return_context.facility_number is None:
        return "not carried from a CCLD request queue"
    return (
        f"facility/license number {return_context.facility_number}; "
        f"date range {_return_context_date_range(return_context)}"
    )


def _render_status_option(status: str) -> str:
    label = _REVIEWER_STATUS_LABELS.get(status, status.replace("_", " "))
    return f'            <option value="{_escape(status)}">{_escape(label)}</option>'


def _render_scope_notice(workflow: Mapping[str, Any]) -> str:
    scope = _mapping(workflow, "scope")
    scope_type = _escape(_string(scope, "scope_type"))
    scope_id = _escape(_string(scope, "scope_id"))
    return f"""<section aria-labelledby="reviewer-scope-heading">
      <h2 id="reviewer-scope-heading">Local/test reviewer UI shell</h2>
      <p>This browser page is local/test only and uses a fixture actor context
      supplied by the scaffold process.</p>
      <p>The seeded corpus scope is {scope_type} / {scope_id}.</p>
      <p>Source-derived records remain separate from reviewer-created notes,
      statuses, and audit rows.</p>
      <p>This shell does not implement production sign-in, deployment, exports,
      reset/reload execution, live crawling, or connector execution.</p>
    </section>"""


def _render_notice(
        notice: str | None,
        source_record_key: str,
        related_records: list[Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
) -> str:
    if notice is None:
        return ""
    detail_href = _reviewer_detail_href(source_record_key, return_context)
    ccld_request_href = _ccld_request_href(related_records, return_context)
    return f"""<section aria-labelledby="form-result-heading">
            <h2 id="form-result-heading">Reviewer update saved</h2>
      <p>{_escape(notice)}</p>
            <p>This confirmation is reviewer-created local/test state. It does not change
            source-derived records or public-source findings.</p>
            <section aria-labelledby="queue-return-progress-heading">
                <h3 id="queue-return-progress-heading">Return and refresh queue progress</h3>
                <p>Queue progress and note/status cues are derived from reviewer-created state.
                Return to the same CCLD request context, use the same facility/license number
                and date range, and submit the request again if the local/test queue page needs
                to refresh its displayed cues.</p>
                <p>After the queue shows the updated cue, open the suggested next record or the
                next not-started record to continue review.</p>
                <p>The suggested next record is not a persisted assignment, automatic record
                claim, or official workflow state. It is local/test navigation guidance based
                on the same request context and existing reviewer-created note/status cues.</p>
                <p>If the saved confirmation, same-context return link, or refreshed queue cue
                did not behave as expected, include that record-specific observation in the
                existing manual feedback checklist. Also carry forward any source traceability,
                source-confidence, or field-note wording that was confusing for this record.</p>
                <dl>
                    <dt>Same facility/license number</dt>
                    <dd>{_escape(_display_value(return_context.facility_number))}</dd>
                    <dt>Same date range</dt>
                    <dd>{_escape(_return_context_date_range(return_context))}</dd>
                </dl>
            </section>
            <ul>
                <li><a href="#reviewer-state-heading">Review saved notes and statuses below</a></li>
                <li><a href="{_escape(ccld_request_href)}">Return to CCLD request queue
                with the same request context</a></li>
                <li><a href="{_escape(detail_href)}">Refresh this reviewer detail</a></li>
            </ul>
    </section>"""


def _reviewer_detail_href(
    source_record_key: str,
    return_context: CcldQueueReturnContext,
) -> str:
    query_values = {"source_record_key": source_record_key}
    query_values.update(dict(_return_context_form_values(return_context)))
    return f"{REVIEWER_UI_DETAIL_PATH}?{urlencode(query_values)}"


def _page(*, title: str, heading: str, main: str, actor_label: str | None = None) -> str:
        return render_page_shell(
                title=title,
                heading=heading,
                main=main,
                skip_label="Skip to main reviewer content",
                nav_label="Local/test reviewer navigation",
                eyebrow=(
                    "Local/test only: source-derived review viewing with reviewer note/status "
                    "actions."
                ),
                actor_label=actor_label,
                extra_nav_links=(
                    ("Reviewer records", REVIEWER_UI_RECORDS_PATH),
                    ("Health check", "/health"),
                ),
                active_path=REVIEWER_UI_PREFIX,
                step_id="review_records",
                next_action="Open next record or add reviewer-created notes/status",
        )


def _signed_in_actor_label(context: ReviewerUiContext) -> str | None:
    actor = context.workflow_shell_context.source_derived_api_context.actor
    if actor is None:
        return None
    if actor.display_name and actor.display_name.strip():
        return actor.display_name.strip()
    return actor.actor_category


def _render_blocked_page(*, title: str, heading: str, message: str) -> str:
    return _render_message_page(
        title=title,
        heading=heading,
        message=message,
        guidance=(
            "Use the local/test reviewer list, or retry with an actor that has "
            "the required role and seeded corpus scope."
        ),
        links=(("Return to reviewer records", REVIEWER_UI_RECORDS_PATH),),
    )


def _workflow_error_page(
    status: int,
    body: bytes,
    *,
    title: str | None = None,
    heading: str | None = None,
    guidance: str | None = None,
    links: tuple[tuple[str, str], ...] | None = None,
    missing_record_heading: str = "Selected seeded record was not found",
) -> tuple[int, str, bytes]:
    payload = _json_object(body)
    error = _mapping(payload, "error")
    code = _optional_string(error, "code")
    message = _safe_error_message(_string(error, "message"))
    if code == "source_derived_record_not_found":
        return _html_response(
            status,
            _render_message_page(
                title=missing_record_heading,
                heading=missing_record_heading,
                message=(
                    "The selected seeded record is not available in this "
                    "local/test seeded corpus."
                ),
                guidance="Return to the reviewer list and select a seeded record.",
                links=(("Return to reviewer records", REVIEWER_UI_RECORDS_PATH),),
            ),
        )
    return _html_response(
        status,
        _render_message_page(
            title="Reviewer request blocked" if title is None else title,
            heading="Reviewer request blocked" if heading is None else heading,
            message=message,
            guidance=(
                "Use the local/test reviewer list, or retry with valid values "
                "and an actor that has the required permission."
                if guidance is None
                else guidance
            ),
            links=(
                (("Return to reviewer records", REVIEWER_UI_RECORDS_PATH),)
                if links is None
                else links
            ),
        ),
    )


def _invalid_form_response(
    *,
    title: str,
    message: str,
    source_record_key: str | None,
) -> tuple[int, str, bytes]:
    return _html_response(
        400,
        _render_message_page(
            title=title,
            heading=title,
            message=message,
            guidance="Return to the detail page and retry with a valid form value.",
            links=_retry_links(source_record_key),
        ),
    )


def _retry_links(source_record_key: str | None) -> tuple[tuple[str, str], ...]:
    if source_record_key is None:
        return (("Return to reviewer records", REVIEWER_UI_RECORDS_PATH),)
    detail_href = (
        f"{REVIEWER_UI_DETAIL_PATH}?"
        f"{urlencode({'source_record_key': source_record_key})}"
    )
    return (
        ("Return to selected record detail", detail_href),
        ("Return to reviewer records", REVIEWER_UI_RECORDS_PATH),
    )


def _render_message_page(
    *,
    title: str,
    heading: str,
    message: str,
    guidance: str,
    links: tuple[tuple[str, str], ...],
) -> str:
    link_items = "\n".join(
        f'        <li><a href="{_escape(href)}">{_escape(label)}</a></li>'
        for label, href in links
    )
    return _page(
        title=title,
        heading=heading,
        main=f"""    <section aria-labelledby="message-heading">
      <h2 id="message-heading">What happened</h2>
      <p>{_escape(_safe_error_message(message))}</p>
    </section>
    <section aria-labelledby="next-steps-heading">
      <h2 id="next-steps-heading">What you can do next</h2>
      <p>{_escape(guidance)}</p>
      <ul>
{link_items}
      </ul>
    </section>""",
    )


def _safe_error_message(message: str) -> str:
    lowered = message.casefold()
    if any(marker in lowered for marker in _SECRET_HTML_MARKERS):
        return (
            "The request included blocked private data. Remove credentials or "
            "private values and retry."
        )
    return message


def _render_original_value_rows(original_values: Mapping[str, Any]) -> str:
    rows: list[str] = []
    for key in sorted(original_values):
        if key in _SAFE_ORIGINAL_VALUE_DENYLIST:
            continue
        value = original_values[key]
        if isinstance(value, str | int | float | bool) or value is None:
            rows.append(
                f"""          <tr>
            <th scope="row">{_escape(key)}</th>
            <td>{_escape(_display_value(value))}</td>
          </tr>"""
            )
    if not rows:
        return """          <tr>
            <td colspan="2">No safe scalar source-derived values are available for this record.</td>
          </tr>"""
    return "\n".join(rows)


def _filter_review_items(
    records: list[Mapping[str, Any]],
    search_query: str,
) -> list[Mapping[str, Any]]:
    normalized_query = " ".join(search_query.casefold().split())
    if not normalized_query:
        return records
    return [
        record
        for record in records
        if normalized_query in _review_item_search_text(record)
    ]


def _review_item_search_text(record: Mapping[str, Any]) -> str:
    source_record = _mapping(record, "source_record")
    identity = _mapping(source_record, "identity")
    source_document = _mapping(source_record, "source_document")
    original_values = _mapping(source_record, "original_values")
    values = [
        _optional_string(identity, "source_record_key"),
        _optional_string(identity, "stable_source_id"),
        _optional_string(identity, "facility_id"),
        _optional_string(original_values, "complaint_control_number"),
        _optional_string(original_values, "finding"),
        _optional_string(source_document, "source_document_id"),
    ]
    return " ".join(value.casefold() for value in values if value)


def _form_values(request_body: bytes | None) -> Mapping[str, list[str]]:
    if request_body is None:
        raise ValueError("Form body is required.")
    return parse_qs(request_body.decode("utf-8"), keep_blank_values=True)


def _required_form_value(form: Mapping[str, list[str]], key: str) -> str:
    value = _first_form_value(form, key)
    if not value:
        raise ValueError(f"{key} is required.")
    return value


def _first_form_value(form: Mapping[str, list[str]], key: str) -> str:
    values = form.get(key, [])
    if not values:
        return ""
    return values[0].strip()


def _json_object(body: bytes) -> dict[str, Any]:
    loaded = json.loads(body)
    if not isinstance(loaded, dict):
        raise ValueError("Expected JSON object.")
    return cast(dict[str, Any], loaded)


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


def _optional_string(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if value is None:
        return "unknown"
    if isinstance(value, str):
        return value
    return str(value)


def _int_value(payload: Mapping[str, Any], key: str) -> int:
    value = payload[key]
    if not isinstance(value, int):
        raise ValueError(f"Expected {key} to be an integer.")
    return value


def _string_items(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _display_value(value: object) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _escape(value: str) -> str:
    return html.escape(value, quote=True)


def _html_response(status: int, markup: str) -> tuple[int, str, bytes]:
    _assert_no_secret_markers(markup)
    return status, "text/html; charset=utf-8", markup.encode("utf-8")


def _assert_no_secret_markers(markup: str) -> None:
    lowered = markup.casefold()
    for marker in _SECRET_HTML_MARKERS:
        if marker in lowered:
            raise ValueError(f"Reviewer UI HTML contains blocked marker: {marker}")