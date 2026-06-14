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

REVIEWER_UI_PREFIX = "/reviewer"
REVIEWER_UI_RECORDS_PATH = f"{REVIEWER_UI_PREFIX}/records"
REVIEWER_UI_DETAIL_PATH = f"{REVIEWER_UI_RECORDS_PATH}/detail"
REVIEWER_UI_NOTE_PATH = f"{REVIEWER_UI_RECORDS_PATH}/note"
REVIEWER_UI_STATUS_PATH = f"{REVIEWER_UI_RECORDS_PATH}/status"
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
_SOURCE_CONTEXT_ENTITY_ORDER = {
    "facility": 0,
    "source_document": 1,
    "complaint": 2,
    "allegation": 3,
    "event": 4,
    "extraction_audit": 5,
}
_REVIEWER_STATUS_LABELS = {
    "not_started": "Needs review",
    "in_review": "In review",
    "needs_follow_up": "Needs review",
    "reviewed": "Reviewed",
    "blocked": "Blocked",
}
_DEFAULT_ACTOR = object()


@dataclass(frozen=True)
class ReviewerUiContext:
    workflow_shell_context: ReviewerWorkflowShellContext
    engine: Engine | None = None


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
            _render_blocked_page(
                title="Source record required",
                heading="Source record required",
                message="Choose a seeded source-derived record before opening reviewer detail.",
            ),
        )
    detail_path = _workflow_detail_path(source_record_key)
    status, _content_type, body = route_reviewer_workflow_shell_response(
        detail_path,
        context.workflow_shell_context,
    )
    if status != 200:
        return _workflow_error_page(status, body)
    payload = _json_object(body)
    return _detail_html_response(status, payload, context, notice=None)


def _note_form_response(
    request_body: bytes | None,
    context: ReviewerUiContext,
) -> tuple[int, str, bytes]:
    form = _form_values(request_body)
    source_record_key = _required_form_value(form, "source_record_key")
    note_text = _required_form_value(form, "note_text")
    status, _content_type, body = route_reviewer_workflow_shell_response(
        _workflow_note_path(source_record_key),
        context.workflow_shell_context,
        request_body=json.dumps({"note_text": note_text}, sort_keys=True).encode("utf-8"),
    )
    if status != 201:
        return _workflow_error_page(status, body)
    payload = _json_object(body)
    return _detail_html_response(
        200,
        payload,
        context,
        notice=(
            "Reviewer note saved through the existing local/test "
            "workflow action."
        ),
    )


def _status_form_response(
    request_body: bytes | None,
    context: ReviewerUiContext,
) -> tuple[int, str, bytes]:
    form = _form_values(request_body)
    source_record_key = _required_form_value(form, "source_record_key")
    reviewer_status = _required_form_value(form, "reviewer_status")
    status, _content_type, body = route_reviewer_workflow_shell_response(
        _workflow_status_path(source_record_key),
        context.workflow_shell_context,
        request_body=json.dumps(
            {"reviewer_status": reviewer_status},
            sort_keys=True,
        ).encode("utf-8"),
    )
    if status != 201:
        return _workflow_error_page(status, body)
    payload = _json_object(body)
    return _detail_html_response(
        200,
        payload,
        context,
        notice=(
            "Reviewer status saved through the existing local/test "
            "workflow action."
        ),
    )


def _detail_html_response(
    status: int,
    payload: Mapping[str, Any],
    context: ReviewerUiContext,
    *,
    notice: str | None,
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
        _render_detail(payload, notice=notice, related_records=bundle_body),
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
) -> str:
    queue = _mapping(payload, "queue")
    workflow = _mapping(payload, "workflow_shell")
    returned_count = _int_value(_mapping(queue, "pagination"), "returned_count")
    rows = "\n".join(
        _render_review_item_row(record, state_summaries) for record in records
    )
    if not rows:
        rows = """        <tr>
                    <td colspan="10">No seeded source-derived review records match the
                    current search.</td>
        </tr>"""
        returned_count = _int_value(_mapping(queue, "pagination"), "returned_count")
    return _page(
        title="Local/test reviewer records",
        heading="Local/test reviewer records",
        main=f"""
    {_render_scope_notice(workflow)}
    <section aria-labelledby="reviewer-search-heading">
      <h2 id="reviewer-search-heading">Find seeded review records</h2>
      <form action="{REVIEWER_UI_RECORDS_PATH}" method="get">
        <p>
          <label for="q">Search seeded review records</label>
          <input id="q" name="q" type="search" value="{_escape(search_query)}">
        </p>
        <p>
          <button type="submit">Search</button>
          <a href="{REVIEWER_UI_RECORDS_PATH}">Clear search</a>
        </p>
      </form>
    </section>
    <section aria-labelledby="reviewer-list-heading">
      <h2 id="reviewer-list-heading">Seeded source-derived review list</h2>
            <p>Showing {len(records)} of {returned_count} seeded complaint records.</p>
      <table>
        <caption>Seeded local/test source-derived records available for reviewer actions</caption>
        <thead>
          <tr>
            <th scope="col">Open</th>
                        <th scope="col">Source record key</th>
            <th scope="col">Complaint control number</th>
            <th scope="col">Facility ID</th>
            <th scope="col">Finding</th>
            <th scope="col">Raw SHA-256</th>
                        <th scope="col">Reviewer state</th>
                        <th scope="col">Notes</th>
                        <th scope="col">Latest status</th>
                        <th scope="col">Latest reviewer state at</th>
          </tr>
        </thead>
        <tbody>
{rows}
        </tbody>
      </table>
    </section>""",
    )


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
    return f"""        <tr>
          <td><a href="{_escape(detail_href)}">Open detail</a></td>
          <td>{_escape(source_record_key)}</td>
          <td>{_escape(_optional_string(original_values, 'complaint_control_number'))}</td>
          <td>{_escape(_optional_string(identity, 'facility_id'))}</td>
          <td>{_escape(_optional_string(original_values, 'finding'))}</td>
          <td>{_escape(_optional_string(source_document, 'raw_sha256'))}</td>
          <td>{_escape(_state_summary_text(state_summary))}</td>
          <td>{_escape(_notes_indicator_text(state_summary))}</td>
          <td>{_escape(_latest_status_text(state_summary))}</td>
          <td>{_escape(_latest_created_at_text(state_summary))}</td>
        </tr>"""


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
        return "No reviewer state yet"
    if latest_status is None:
        return "Needs review"
    return _REVIEWER_STATUS_LABELS.get(latest_status, latest_status.replace("_", " "))


def _notes_indicator_text(summary: Mapping[str, Any]) -> str:
    note_count = _summary_int(summary, "note_count")
    if note_count == 0:
        return "No reviewer notes"
    if note_count == 1:
        return "1 reviewer note"
    return f"{note_count} reviewer notes"


def _latest_status_text(summary: Mapping[str, Any]) -> str:
    latest_status = _summary_optional_string(summary, "latest_status")
    if latest_status is None:
        return "No reviewer status"
    return latest_status


def _latest_created_at_text(summary: Mapping[str, Any]) -> str:
    latest_created_at = _summary_optional_string(summary, "latest_created_at")
    if latest_created_at is None:
        return "No reviewer-created state yet"
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
) -> str:
    detail = _mapping(payload, "detail")
    source_record = _mapping(detail, "source_record")
    identity = _mapping(source_record, "identity")
    source_document = _mapping(source_record, "source_document")
    source_traceability = _mapping(source_record, "source_traceability")
    original_values = _mapping(source_record, "original_values")
    import_batch = _mapping(source_record, "import_batch")
    source_record_key = _string(identity, "source_record_key")
    return _page(
        title="Local/test reviewer detail",
        heading="Local/test reviewer detail",
        main=f"""
    {_render_notice(notice)}
    {_render_scope_notice(_mapping(payload, 'workflow_shell'))}
    {_render_detail_navigation(source_record_key)}
    <section aria-labelledby="source-derived-heading">
      <h2 id="source-derived-heading">Source-derived record</h2>
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
    <section aria-labelledby="traceability-heading">
      <h2 id="traceability-heading">Source traceability</h2>
      <dl>
        <dt>Source URL</dt>
        <dd>{_escape(_string(source_document, 'source_url'))}</dd>
        <dt>Raw SHA-256</dt>
        <dd>{_escape(_string(source_document, 'raw_sha256'))}</dd>
        <dt>Raw artifact path</dt>
        <dd>{_escape(_optional_string(source_document, 'raw_path'))}</dd>
        <dt>Connector name</dt>
        <dd>{_escape(_string(source_document, 'connector_name'))}</dd>
        <dt>Connector version</dt>
        <dd>{_escape(_string(source_document, 'connector_version'))}</dd>
        <dt>Retrieved at</dt>
        <dd>{_escape(_string(source_document, 'retrieved_at'))}</dd>
        <dt>Source document ID</dt>
        <dd>{_escape(_string(source_document, 'source_document_id'))}</dd>
        <dt>Report index</dt>
        <dd>{_escape(str(source_traceability.get('report_index', 'unknown')))}</dd>
        <dt>Import batch ID</dt>
        <dd>{_escape(_string(import_batch, 'import_batch_id'))}</dd>
        <dt>Import validation status</dt>
        <dd>{_escape(_string(import_batch, 'validation_status'))}</dd>
      </dl>
            {_render_traceability_summary(source_document, source_traceability, import_batch)}
    </section>
        {_render_source_context_section(related_records, source_record_key)}
    {_render_reviewer_state_section(detail)}
        {_render_review_actions(source_record_key)}""",
    )


def _render_detail_navigation(source_record_key: str) -> str:
    detail_href = (
        f"{REVIEWER_UI_DETAIL_PATH}?"
        f"{urlencode({'source_record_key': source_record_key})}"
    )
    return f"""<section aria-labelledby="detail-navigation-heading">
      <h2 id="detail-navigation-heading">Detail navigation</h2>
            <ul>
                <li><a href="{REVIEWER_UI_RECORDS_PATH}">Back to reviewer records</a></li>
                <li><a href="{_escape(detail_href)}">Refresh this seeded detail</a></li>
                <li><a href="#source-context-heading">Review source-derived context</a></li>
                <li><a href="#reviewer-state-heading">Review notes and statuses</a></li>
                <li><a href="#review-actions-heading">Add note or status</a></li>
            </ul>
        </section>"""


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
                        ("Raw artifact path", source_document.get("raw_path")),
                        ("Connector", source_document.get("connector_name")),
                        ("Retrieved at", source_document.get("retrieved_at")),
                        ("Report index", source_traceability.get("report_index")),
                        ("Import validation", import_batch.get("validation_status")),
                        ("Raw hash validation", import_batch.get("raw_hash_validation_status")),
                )
        )
        return f"""<table>
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
        visibility = "available" if _has_display_value(value) else "unknown or unavailable"
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
      <dl>
        <dt>Total associated rows</dt>
        <dd>{_escape(str(_int_value(summary, 'total_associated_rows')))}</dd>
        <dt>Reviewer statuses present</dt>
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


def _render_review_actions(source_record_key: str) -> str:
        return f"""<section id="review-actions-heading" aria-labelledby="review-actions-title">
            <h2 id="review-actions-title">Reviewer actions</h2>
            <p>These local/test actions write reviewer-created state through the
            existing authenticated workflow actions. They do not edit source-derived
            fields.</p>
            {_render_note_form(source_record_key)}
            {_render_status_form(source_record_key)}
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


def _render_note_form(source_record_key: str) -> str:
    return f"""<section aria-labelledby="note-form-heading">
    <h3 id="note-form-heading">Add reviewer note</h3>
      <form action="{REVIEWER_UI_NOTE_PATH}" method="post">
        <input type="hidden" name="source_record_key" value="{_escape(source_record_key)}">
        <p>
          <label for="note_text">Reviewer note</label>
          <textarea id="note_text" name="note_text" rows="4" required></textarea>
        </p>
        <p><button type="submit">Save reviewer note</button></p>
      </form>
    </section>"""


def _render_status_form(source_record_key: str) -> str:
    options = "\n".join(
        _render_status_option(status)
        for status in REVIEWER_STATUS_VALUES
    )
    return f"""<section aria-labelledby="status-form-heading">
            <h3 id="status-form-heading">Set reviewer status</h3>
      <form action="{REVIEWER_UI_STATUS_PATH}" method="post">
        <input type="hidden" name="source_record_key" value="{_escape(source_record_key)}">
        <p>
          <label for="reviewer_status">Reviewer status</label>
          <select id="reviewer_status" name="reviewer_status" required>
{options}
          </select>
        </p>
        <p><button type="submit">Save reviewer status</button></p>
      </form>
    </section>"""


def _render_status_option(status: str) -> str:
    label = status.replace("_", " ")
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


def _render_notice(notice: str | None) -> str:
    if notice is None:
        return ""
    return f"""<section aria-labelledby="form-result-heading">
      <h2 id="form-result-heading">Saved</h2>
      <p>{_escape(notice)}</p>
    </section>"""


def _page(*, title: str, heading: str, main: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_escape(title)} - CCLD Hosted Tester MVP Scaffold</title>
</head>
<body>
  <header>
    <p>Local/test only: source-derived review viewing with reviewer note/status actions.</p>
    <h1>{_escape(heading)}</h1>
  </header>
  <nav aria-label="Local/test reviewer navigation">
    <ul>
      <li><a href="/">Scaffold home</a></li>
      <li><a href="{REVIEWER_UI_PREFIX}">Reviewer home</a></li>
      <li><a href="{REVIEWER_UI_RECORDS_PATH}">Reviewer records</a></li>
      <li><a href="/health">Health check</a></li>
    </ul>
  </nav>
  <main>
{main}
  </main>
</body>
</html>
"""


def _render_blocked_page(*, title: str, heading: str, message: str) -> str:
    return _page(
        title=title,
        heading=heading,
        main=f"""    <section aria-labelledby="blocked-heading">
      <h2 id="blocked-heading">Request blocked</h2>
      <p>{_escape(message)}</p>
            <p>Local/test reviewer pages require an explicit active actor, role, and
            seeded corpus scope.</p>
    </section>""",
    )


def _workflow_error_page(status: int, body: bytes) -> tuple[int, str, bytes]:
    payload = _json_object(body)
    error = _mapping(payload, "error")
    return _html_response(
        status,
        _render_blocked_page(
            title="Reviewer request blocked",
            heading="Reviewer request blocked",
            message=_string(error, "message"),
        ),
    )


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