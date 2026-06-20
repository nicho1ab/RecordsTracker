# ruff: noqa: E501

from __future__ import annotations

import csv
import html
import io
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
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
    CCLD_FACILITY_REVIEW_HUB_PATH,
    CCLD_FACILITY_REVIEW_PRIORITY_PATH,
    CCLD_RECORD_REQUEST_PATH,
    load_active_ccld_facility_reference,
)
from ccld_complaints.hosted_app.facility_case_brief import (
    FacilityCaseBrief,
    FacilityCaseBriefRecord,
    priority_reason_labels,
    render_facility_case_brief,
    render_record_flag_reason_section,
)
from ccld_complaints.hosted_app.facility_review_signals import (
    load_active_facility_review_signals,
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
REVIEWER_UI_MATRIX_EXPORT_PATH = f"{REVIEWER_UI_RECORDS_PATH}/matrix.csv"
REVIEWER_UI_SUBSTANTIATED_EXPORT_PATH = f"{REVIEWER_UI_RECORDS_PATH}/substantiated.csv"
REVIEWER_UI_NOTE_PATH = f"{REVIEWER_UI_RECORDS_PATH}/note"
REVIEWER_UI_STATUS_PATH = f"{REVIEWER_UI_RECORDS_PATH}/status"
REVIEWER_UI_PACKET_PREVIEW_PATH = f"{REVIEWER_UI_PREFIX}/packet/preview"
REVIEWER_UI_PACKET_DRAFT_PATH = f"{REVIEWER_UI_PREFIX}/packet/draft"
CCLD_HELP_PATH = "/ccld/help"
FEEDBACK_PATH = "/feedback"
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
_SERIOUS_REVIEW_TOPIC_KEYWORDS: tuple[str, ...] = (
    "sexual assault",
    "abuse",
    "neglect",
    "injury",
    "restraint",
    "runaway",
    "awol",
    "medication",
    "staff misconduct",
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
        "Use this as the complaint identifier only after checking the source document context; use feedback if the identifier or next step is confusing.",
    ),
    (
        "Complaint received date",
        "complaint_received_date",
        "Check the source traceability fields before relying on this date in notes/status; if unclear, describe the local/test cue cautiously or use feedback.",
    ),
    (
        "Visit date",
        "visit_date",
        "If this is missing, describe it as not available locally, not as proof no visit occurred; use feedback if the next step is unclear.",
    ),
    (
        "Report date",
        "report_date",
        "Check whether the report date is acting as a proxy before using delay wording; use cautious reviewer-created wording only after that check.",
    ),
    (
        "Date signed",
        "date_signed",
        "Use this as a source-derived display value; check source context before relying on it or report confusion through feedback.",
    ),
    (
        "Finding",
        "finding",
        "Treat this as a source-derived local/test value, not as a new reviewer finding; use feedback if the safe wording is unclear.",
    ),
    (
        "Extraction confidence",
        "extraction_confidence",
        "Treat this as local/test extraction metadata, not as reviewer verification; do not use it as a source-confidence score.",
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
    if parsed_url.path == REVIEWER_UI_MATRIX_EXPORT_PATH:
        return _matrix_export_response(parsed_url.query, context)
    if parsed_url.path == REVIEWER_UI_SUBSTANTIATED_EXPORT_PATH:
        return _substantiated_export_response(parsed_url.query, context)
    if parsed_url.path == REVIEWER_UI_PACKET_PREVIEW_PATH:
        return _packet_preview_response(parsed_url.query, context)
    if parsed_url.path == REVIEWER_UI_PACKET_DRAFT_PATH:
        return _packet_draft_response(parsed_url.query, context)
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


def _packet_preview_response(
    query: str,
    context: ReviewerUiContext,
) -> tuple[int, str, bytes]:
    query_values = parse_qs(query, keep_blank_values=True)
    return_context = _packet_preview_context_from_values(query_values)
    # If no facility context was supplied, render a clear context-needed state
    # instead of quietly showing all loaded records under "not provided".
    if return_context.facility_number is None:
        return _html_response(
            200,
            _render_packet_preview_context_needed(actor_label=_signed_in_actor_label(context)),
        )
    status, _content_type, body = route_reviewer_workflow_shell_response(
        f"{REVIEWER_WORKFLOW_API_PREFIX}/queue?limit=100",
        context.workflow_shell_context,
    )
    if status != 200:
        return _workflow_error_page(status, body)
    payload = _json_object(body)
    queue = _mapping(payload, "queue")
    records = _record_list(queue, "records")
    filtered_records = _filter_packet_preview_items(records, return_context)
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
        _render_packet_preview(
            filtered_records,
            state_summaries,
            return_context,
            workflow=_mapping(payload, "workflow_shell"),
            actor_label=_signed_in_actor_label(context),
        ),
    )


def _matrix_export_response(
    query: str,
    context: ReviewerUiContext,
 ) -> tuple[int, str, bytes]:
    query_values = parse_qs(query, keep_blank_values=True)
    return_context = _packet_preview_context_from_values(query_values)
    status, _content_type, body = route_reviewer_workflow_shell_response(
        f"{REVIEWER_WORKFLOW_API_PREFIX}/queue?limit=100",
        context.workflow_shell_context,
    )
    if status != 200:
        return _workflow_error_page(status, body)
    payload = _json_object(body)
    queue = _mapping(payload, "queue")
    records = _filter_packet_preview_items(_record_list(queue, "records"), return_context)
    state_status, state_body = _reviewer_created_state_records(context)
    if state_status != 200:
        if not isinstance(state_body, bytes):
            raise ValueError("Expected reviewer-created state error body to be bytes.")
        return _workflow_error_page(state_status, state_body)
    if isinstance(state_body, bytes):
        raise ValueError("Expected reviewer-created state records.")
    state_summaries = _state_summaries_by_source_record(state_body)
    related_records = _all_source_derived_records(context)
    csv_text = _render_complaint_review_matrix_csv(
        records,
        state_summaries,
        related_records,
        return_context,
    )
    return 200, "text/csv; charset=utf-8", csv_text.encode("utf-8-sig")


def _all_source_derived_records(context: ReviewerUiContext) -> list[Mapping[str, Any]]:
    source_status, _content_type, source_body = route_source_derived_api_response(
        f"{SOURCE_DERIVED_API_PREFIX}?limit=100",
        context.workflow_shell_context.source_derived_api_context,
    )
    if source_status != 200:
        return []
    source_payload = _json_object(source_body)
    return _record_list(source_payload, "records")


def _render_complaint_review_matrix_csv(
    records: list[Mapping[str, Any]],
    state_summaries: Mapping[str, Mapping[str, Any]],
    all_source_records: list[Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
) -> str:
    output = io.StringIO(newline="")
    fieldnames = _matrix_fieldnames()
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\r\n")
    writer.writeheader()
    if not records:
        writer.writerow(_empty_matrix_row(return_context))
    for record in records:
        writer.writerow(
            _matrix_row_for_record(record, state_summaries, all_source_records, return_context)
        )
    return output.getvalue()


def _substantiated_fieldnames() -> list[str]:
    return [
        "Facility Name",
        "Facility/License Number",
        "Complaint Received Date",
        "Report Date",
        "Visit Date",
        "Date Signed",
        "Finding/Status",
        "Complaint Control Number",
        "Source Report URL",
        "Source Traceability Status",
        "Serious Review Cue",
        "Reviewer-created status",
        "Reviewer-created note present",
    ]


def _empty_substantiated_row(return_context: CcldQueueReturnContext) -> dict[str, str]:
    return {key: "" for key in _substantiated_fieldnames()} | {
        "Facility/License Number": return_context.facility_number or "",
    }


def _render_substantiated_complaint_csv(
    records: list[Mapping[str, Any]],
    state_summaries: Mapping[str, Mapping[str, Any]],
    all_source_records: list[Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
    complaint_status_filter: str,
    complaint_facility_filter: str | None,
    complaint_start_date_filter: str | None,
    complaint_end_date_filter: str | None,
    serious_review_cue_only: bool,
) -> str:
    output = io.StringIO(newline="")
    fieldnames = _substantiated_fieldnames()
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\r\n")
    writer.writeheader()
    # Filter to complaint records and requested finding status.
    filtered_records: list[Mapping[str, Any]] = []
    for item in records:
        try:
            src = _mapping(item, "source_record")
            if _queue_source_record_entity_type(src) != "complaint":
                continue
            row_facility_number = _complaint_export_row_facility_number(src, return_context)
            if complaint_facility_filter is not None and row_facility_number != complaint_facility_filter:
                continue
            complaint_received_date = _complaint_export_row_complaint_received_date(src)
            if not _complaint_export_date_in_range(
                complaint_received_date,
                complaint_start_date_filter,
                complaint_end_date_filter,
            ):
                continue
            vals = _mapping(src, "original_values")
            finding = vals.get("finding")
            finding_norm = _normalized_complaint_finding(finding)
            if complaint_status_filter == "all" or finding_norm == complaint_status_filter:
                if serious_review_cue_only:
                    related_records = _related_source_records(src, all_source_records)
                    if not _serious_review_cue(src, related_records):
                        continue
                filtered_records.append(item)
        except Exception:
            continue
    if not filtered_records:
        writer.writerow(_empty_substantiated_row(return_context))
        return output.getvalue()
    records = filtered_records

    # Sort: records with complaint_received_date first (desc), then missing-date rows by key
    records_with_date: list[Mapping[str, Any]] = []
    records_without_date: list[Mapping[str, Any]] = []
    for item in records:
        source_record = _mapping(item, "source_record")
        original_values = _mapping(source_record, "original_values")
        if original_values.get("complaint_received_date"):
            records_with_date.append(item)
        else:
            records_without_date.append(item)

    def _date_key(it: Mapping[str, Any]) -> str:
        src = _mapping(it, "source_record")
        vals = _mapping(src, "original_values")
        return vals.get("complaint_received_date") or ""

    records_with_date.sort(key=_date_key, reverse=True)

    def _key_by_source_record(it: Mapping[str, Any]) -> str:
        src = _mapping(it, "source_record")
        identity = _mapping(src, "identity")
        return _string(identity, "source_record_key")

    records_without_date.sort(key=_key_by_source_record)

    for record in records_with_date + records_without_date:
        writer.writerow(
            _substantiated_row_for_record(record, state_summaries, all_source_records, return_context)
        )

    return output.getvalue()


def _substantiated_row_for_record(
    item: Mapping[str, Any],
    state_summaries: Mapping[str, Mapping[str, Any]],
    all_source_records: list[Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
) -> dict[str, str]:
    source_record = _mapping(item, "source_record")
    identity = _mapping(source_record, "identity")
    source_document = _mapping(source_record, "source_document")
    original_values = _mapping(source_record, "original_values")
    source_record_key = _string(identity, "source_record_key")
    summary = state_summaries.get(source_record_key, _empty_state_summary())
    related_records = _related_source_records(source_record, all_source_records)
    facility = _facility_context(related_records)
    facility_name = _facility_context_value(facility, "facility_name")
    # Fallback: try to find a facility record in all_source_records by facility id
    if facility_name == "unknown":
        try:
            fid = return_context.facility_number or _optional_string(identity, "facility_id")
            for rec in all_source_records:
                try:
                    if _string(rec, "entity_type") != "facility":
                        continue
                    # record identity may contain facility_id
                    rec_ident = _mapping(rec, "identity")
                    rec_fid = _optional_string(rec_ident, "facility_id")
                    if rec_fid == fid:
                        facility_name = _facility_context_value(_mapping(rec, "original_values"), "facility_name")
                        break
                except Exception:
                    continue
        except Exception:
            pass
    return {
        "Facility Name": facility_name,
        "Facility/License Number": _complaint_export_row_facility_number(source_record, return_context),
        "Complaint Received Date": _optional_string(original_values, "complaint_received_date"),
        "Report Date": _optional_string(original_values, "report_date"),
        "Visit Date": _optional_string(original_values, "visit_date"),
        "Date Signed": _optional_string(original_values, "date_signed"),
        "Finding/Status": _optional_string(original_values, "finding"),
        "Complaint Control Number": _optional_string(original_values, "complaint_control_number"),
        "Source Report URL": _optional_string(source_document, "source_url"),
        "Source Traceability Status": _source_traceability_cue(source_document),
        "Serious Review Cue": _serious_review_cue(source_record, related_records),
        "Reviewer-created status": _latest_status_label_text(summary),
        "Reviewer-created note present": "yes" if _summary_int(summary, "note_count") > 0 else "no",
    }


def _substantiated_export_response(
    query: str,
    context: ReviewerUiContext,
) -> tuple[int, str, bytes]:
    query_values = parse_qs(query, keep_blank_values=True)
    return_context = _packet_preview_context_from_values(query_values)
    complaint_start_date_filter, complaint_end_date_filter = _complaint_export_date_filters(query_values)
    export_context = CcldQueueReturnContext(
        facility_number=return_context.facility_number,
        start_date=complaint_start_date_filter,
        end_date=complaint_end_date_filter,
        context_origin=return_context.context_origin,
        lookup_facility_name=return_context.lookup_facility_name,
    )
    status, _content_type, body = route_reviewer_workflow_shell_response(
        f"{REVIEWER_WORKFLOW_API_PREFIX}/queue?limit=100",
        context.workflow_shell_context,
    )
    if status != 200:
        return _workflow_error_page(status, body)
    payload = _json_object(body)
    queue = _mapping(payload, "queue")
    records = _filter_packet_preview_items(_record_list(queue, "records"), export_context)

    complaint_status_filter = _complaint_export_status_filter(query_values)
    complaint_facility_filter = _complaint_export_facility_filter(query_values)
    serious_review_cue_only = _complaint_export_serious_review_cue_filter(query_values)

    state_status, state_body = _reviewer_created_state_records(context)
    if state_status != 200:
        if not isinstance(state_body, bytes):
            raise ValueError("Expected reviewer-created state error body to be bytes.")
        return _workflow_error_page(state_status, state_body)
    if isinstance(state_body, bytes):
        raise ValueError("Expected reviewer-created state records.")
    state_summaries = _state_summaries_by_source_record(state_body)
    related_records = _all_source_derived_records(context)
    # Let the renderer filter records for substantiated findings to avoid
    # mismatches between queue item shapes and source-derived records.
    csv_text = _render_substantiated_complaint_csv(
        records,
        state_summaries,
        related_records,
        export_context,
        complaint_status_filter,
        complaint_facility_filter,
        complaint_start_date_filter,
        complaint_end_date_filter,
        serious_review_cue_only,
    )
    return 200, "text/csv; charset=utf-8", csv_text.encode("utf-8-sig")


def complaint_export_attachment_filename(query: str) -> str:
    query_values = parse_qs(query, keep_blank_values=True)
    status = _complaint_export_status_filter(query_values)
    facility = _complaint_export_filename_facility_segment(query_values)
    start_date, end_date = _complaint_export_date_filters(query_values)

    segments = ["complaints", status]
    if facility is not None:
        segments.extend(("facility", facility))
    if start_date is not None and end_date is not None:
        segments.extend((start_date, "to", end_date))
    elif start_date is not None:
        segments.extend(("from", start_date))
    elif end_date is not None:
        segments.extend(("to", end_date))
    return "-".join(segments) + ".csv"


def _complaint_export_status_filter(query_values: Mapping[str, list[str]]) -> str:
    raw_status = query_values.get("status", ["substantiated"])[0]
    normalized = raw_status.strip().lower()
    if normalized in {"substantiated", "unsubstantiated", "all"}:
        return normalized
    return "substantiated"


def _complaint_export_facility_filter(query_values: Mapping[str, list[str]]) -> str | None:
    raw_facility = query_values.get("facility", [""])[0]
    normalized = raw_facility.strip()
    if not normalized:
        return None
    return normalized


def _complaint_export_serious_review_cue_filter(
    query_values: Mapping[str, list[str]],
) -> bool:
    raw_review_cue = query_values.get("review_cue", [""])[0]
    return raw_review_cue.strip().lower() == "serious"


def _complaint_export_filename_facility_segment(
    query_values: Mapping[str, list[str]],
) -> str | None:
    facility = _complaint_export_facility_filter(query_values)
    if facility is None:
        return None
    normalized = facility.lower()
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789-")
    if not normalized or any(char not in allowed for char in normalized):
        return None
    return normalized


def _complaint_export_date_filters(
    query_values: Mapping[str, list[str]],
) -> tuple[str | None, str | None]:
    raw_start = query_values.get("start_date", [""])[0]
    raw_end = query_values.get("end_date", [""])[0]
    return _validated_iso_date_or_none(raw_start), _validated_iso_date_or_none(raw_end)


def _validated_iso_date_or_none(value: str) -> str | None:
    candidate = value.strip()
    if not candidate:
        return None
    try:
        datetime.strptime(candidate, "%Y-%m-%d")
    except ValueError:
        return None
    return candidate


def _normalized_complaint_finding(value: object) -> str:
    if value is None:
        return ""
    try:
        normalized = str(value).strip().lower()
    except Exception:
        return ""
    if normalized in {"substantiated", "unsubstantiated"}:
        return normalized
    return ""


def _queue_source_record_entity_type(source_record: Mapping[str, Any]) -> str:
    raw_entity_type = source_record.get("entity_type")
    if isinstance(raw_entity_type, str) and raw_entity_type.strip():
        return raw_entity_type.strip().lower()
    try:
        identity = _mapping(source_record, "identity")
        source_record_key = _string(identity, "source_record_key")
        return source_record_key.split(":", 1)[0].strip().lower()
    except Exception:
        return ""


def _complaint_export_row_facility_number(
    source_record: Mapping[str, Any],
    return_context: CcldQueueReturnContext,
) -> str:
    if return_context.facility_number:
        return return_context.facility_number
    identity = _mapping(source_record, "identity")
    facility_id = _optional_string(identity, "facility_id")
    if facility_id.startswith("ccld:facility:"):
        suffix = facility_id.rsplit(":", 1)[-1].strip()
        if suffix:
            return suffix
    return facility_id


def _complaint_export_row_complaint_received_date(source_record: Mapping[str, Any]) -> str:
    original_values = _mapping(source_record, "original_values")
    return _optional_string(original_values, "complaint_received_date")


def _complaint_export_date_in_range(
    complaint_received_date: str,
    start_date: str | None,
    end_date: str | None,
) -> bool:
    if start_date is None and end_date is None:
        return True
    if complaint_received_date == "unknown":
        return False
    if start_date is not None and complaint_received_date < start_date:
        return False
    if end_date is not None and complaint_received_date > end_date:
        return False
    return True


def _serious_review_cue(
    source_record: Mapping[str, Any],
    related_records: list[Mapping[str, Any]],
) -> str:
    values = _mapping(source_record, "original_values")
    search_parts: list[str] = []
    for key in (
        "finding",
        "complaint_control_number",
    ):
        value = values.get(key)
        if _has_display_value(value):
            search_parts.append(str(value))

    for record in related_records:
        if _string(record, "entity_type") != "allegation":
            continue
        allegation_values = _mapping(record, "original_values")
        for key in (
            "allegation_category",
            "finding",
        ):
            value = allegation_values.get(key)
            if _has_display_value(value):
                search_parts.append(str(value))

    haystack = " ".join(search_parts).lower()
    if any(keyword in haystack for keyword in _SERIOUS_REVIEW_TOPIC_KEYWORDS):
        return "Possible serious allegation topic"
    return ""


def _serious_review_cue_record_count(records: list[Mapping[str, Any]]) -> int:
    return sum(
        1
        for record in records
        if _string(record, "entity_type") == "complaint"
        and _serious_review_cue(record, records)
    )


def _matrix_fieldnames() -> list[str]:
    return [
        "matrix_status",
        "export_boundary",
        "facility_number",
        "facility_name",
        "request_start_date",
        "request_end_date",
        "source_record_key",
        "complaint_number",
        "complaint_date",
        "visit_date",
        "report_date",
        "date_signed",
        "allegation_categories",
        "finding_or_resolution",
        "source_label",
        "source_url",
        "source_traceability_status",
        "missing_field_cues",
        "loaded_local_test_record_indicator",
        "reviewer_created_status",
        "reviewer_created_note_present",
        "reviewer_created_last_updated",
    ]


def _matrix_boundary_text() -> str:
    return (
        "local/test complaint review matrix; CSV export; Excel-ready; not a certified report; "
        "not source verification; not a complaint-coverage determination; not a source-completeness proof; "
        "not a legal finding; complaint records are requested/reviewed separately"
    )


def _empty_matrix_row(return_context: CcldQueueReturnContext) -> dict[str, str]:
    return {
        key: ""
        for key in _matrix_fieldnames()
    } | {
        "matrix_status": "No loaded local/test complaint records matched this facility/date context.",
        "export_boundary": _matrix_boundary_text(),
        "facility_number": return_context.facility_number or "",
        "request_start_date": return_context.start_date or "",
        "request_end_date": return_context.end_date or "",
        "loaded_local_test_record_indicator": "no",
    }


def _matrix_row_for_record(
    item: Mapping[str, Any],
    state_summaries: Mapping[str, Mapping[str, Any]],
    all_source_records: list[Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
) -> dict[str, str]:
    source_record = _mapping(item, "source_record")
    identity = _mapping(source_record, "identity")
    source_document = _mapping(source_record, "source_document")
    original_values = _mapping(source_record, "original_values")
    source_record_key = _string(identity, "source_record_key")
    summary = state_summaries.get(source_record_key, _empty_state_summary())
    related_records = _related_source_records(source_record, all_source_records)
    facility = _facility_context(related_records)
    return {
        "matrix_status": "loaded local/test complaint record",
        "export_boundary": _matrix_boundary_text(),
        "facility_number": return_context.facility_number or _optional_string(identity, "facility_id"),
        "facility_name": _facility_context_value(facility, "facility_name"),
        "request_start_date": return_context.start_date or "",
        "request_end_date": return_context.end_date or "",
        "source_record_key": source_record_key,
        "complaint_number": _optional_string(original_values, "complaint_control_number"),
        "complaint_date": _optional_string(original_values, "complaint_received_date"),
        "visit_date": _optional_string(original_values, "visit_date"),
        "report_date": _optional_string(original_values, "report_date"),
        "date_signed": _optional_string(original_values, "date_signed"),
        "allegation_categories": _matrix_allegation_categories(related_records),
        "finding_or_resolution": _optional_string(original_values, "finding"),
        "source_label": _matrix_source_label(source_document),
        "source_url": _optional_string(source_document, "source_url"),
        "source_traceability_status": _source_traceability_cue(source_document),
        "missing_field_cues": _matrix_missing_field_cues(original_values, source_document),
        "loaded_local_test_record_indicator": "yes",
        "reviewer_created_status": _latest_status_label_text(summary),
        "reviewer_created_note_present": "yes" if _summary_int(summary, "note_count") > 0 else "no",
        "reviewer_created_last_updated": _summary_optional_string(summary, "latest_created_at") or "",
    }


def _matrix_allegation_categories(related_records: list[Mapping[str, Any]]) -> str:
    categories = []
    for record in related_records:
        if _string(record, "entity_type") == "allegation":
            values = _mapping(record, "original_values")
            category = _display_value(values.get("allegation_category"))
            if category and category != "unknown":
                categories.append(category)
    return "; ".join(dict.fromkeys(categories))


def _matrix_source_label(source_document: Mapping[str, Any]) -> str:
    parts = [
        _optional_string(source_document, "connector_name"),
        _optional_string(source_document, "document_type"),
        _optional_string(source_document, "source_document_id"),
    ]
    return "; ".join(part for part in parts if part and part != "unknown")


def _matrix_missing_field_cues(
    original_values: Mapping[str, Any],
    source_document: Mapping[str, Any],
) -> str:
    cues: list[str] = []
    for label, key in (
        ("first investigation activity date not available locally", "missing_first_activity_date"),
        ("visit date not available locally", "missing_visit_date"),
        ("report date not available locally", "missing_report_date"),
    ):
        if original_values.get(key) is True:
            cues.append(label)
    if original_values.get("report_date_used_as_proxy") is True:
        cues.append("report date proxy cue")
    missing_traceability = _missing_traceability_values_text(source_document)
    if missing_traceability != "none":
        cues.append(f"missing local/test traceability values: {missing_traceability}")
    return "; ".join(cues) if cues else "none visible from loaded local/test fields"


def _packet_draft_response(
        query: str,
        context: ReviewerUiContext,
) -> tuple[int, str, bytes]:
        query_values = parse_qs(query, keep_blank_values=True)
        return_context = _packet_preview_context_from_values(query_values)
        if return_context.facility_number is None:
                return _html_response(
                        200,
                        _render_packet_draft_context_needed(actor_label=_signed_in_actor_label(context)),
                )
        status, _content_type, body = route_reviewer_workflow_shell_response(
                f"{REVIEWER_WORKFLOW_API_PREFIX}/queue?limit=100",
                context.workflow_shell_context,
        )
        if status != 200:
                return _workflow_error_page(status, body)
        payload = _json_object(body)
        queue = _mapping(payload, "queue")
        records = _filter_packet_preview_items(_record_list(queue, "records"), return_context)
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
                _render_packet_draft(
                        records,
                        state_summaries,
                        return_context,
                        workflow=_mapping(payload, "workflow_shell"),
                        actor_label=_signed_in_actor_label(context),
                ),
        )


def _render_packet_draft_context_needed(*, actor_label: str | None) -> str:
        return _page(
                title="Attorney Review Packet Draft",
                heading="Attorney Review Packet Draft",
                actor_label=actor_label,
                show_workflow_indicator=False,
                main=f"""
                <section class="packet-draft" aria-labelledby="packet-context-needed-heading">
                    <div class="packet-draft-header">
                        <p class="launch-kicker">Local/test preparation draft for browser copy or print</p>
                        <h2 id="packet-context-needed-heading">No facility/date packet context was supplied.</h2>
                    </div>
                    <p>Open this draft from a CCLD retrieval result, the local/test packet preview, or a reviewer detail confirmation so the facility/date context can be carried into the draft for browser copy or print preparation.</p>
                    <p>This page is not a complete local/test preparation draft without a facility/date context, and it is not a legal report, not a final export, not a certified report, and not a source-completeness proof.</p>
                    <div class="form-actions packet-draft-actions">
                        <a class="button" href="{CCLD_RECORD_REQUEST_PATH}">Open Retrieve</a>
                        <a class="button button-secondary" href="{REVIEWER_UI_RECORDS_PATH}">Open Review queue</a>
                    </div>
                </section>
                """,
        )


def _render_packet_draft(
    records: list[Mapping[str, Any]],
    state_summaries: Mapping[str, Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
    *,
    workflow: Mapping[str, Any],
    actor_label: str | None,
) -> str:
    traceability_counts = _packet_traceability_counts(records)
    state_counts = _packet_reviewer_state_counts(records, state_summaries)
    readiness_counts = _packet_readiness_counts(records, state_summaries)
    findings = _packet_finding_counts(records)
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    feedback_href = _feedback_href(
        workflow_area="packet-draft",
        page_path=REVIEWER_UI_PACKET_DRAFT_PATH,
        return_context=return_context,
        prompt="Describe browser copy or print preparation or packet readiness confusion.",
    )
    record_sections = "\n".join(
        _render_packet_draft_record(record, state_summaries, return_context)
        for record in records
    )
    if not record_sections:
        record_sections = """        <section class="packet-draft-record" aria-labelledby="draft-no-records-heading">
                    <h3 id="draft-no-records-heading">No included complaint records</h3>
                    <p>No loaded local/test complaint records match this packet draft context.</p>
                </section>"""
    copy_summary = _packet_copy_summary(
        records,
        state_summaries,
        return_context,
        traceability_counts,
        state_counts,
        findings,
        generated_at,
    )
    return _page(
        title="Attorney Review Packet Draft",
        heading="Attorney Review Packet Draft",
        actor_label=actor_label,
        show_workflow_indicator=False,
        main=f"""
                <article class="packet-draft" aria-labelledby="packet-draft-title">
                    <header class="packet-draft-header">
                        <p class="launch-kicker">Attorney Review Packet Draft</p>
                        <h2 id="packet-draft-title">Local/test preparation draft for browser copy or print</h2>
                        <p><strong>Use browser copy or print only after review.</strong> This page keeps the intentional print/copy layout, but it does not generate a server-side PDF, Word file, ZIP, CSV, or downloadable final export.</p>
                    </header>
                    <section aria-labelledby="draft-copy-print-guidance-heading">
                        <h3 id="draft-copy-print-guidance-heading">Copy/print preparation guidance</h3>
                        <p>This local/test preparation draft gathers the included complaint-record summaries, review-readiness counts, source-traceability cues, reviewer-created status/note cues, limitations, and a static copyable packet summary for manual browser copy or print.</p>
                        <p><strong>Packet readiness means local/test review readiness only.</strong> The draft can be ready for manual review, browser copy, or browser print after the tester confirms the active facility/date context, included record count, important source-derived values, visible source traceability, reviewer-created status/note cues, and possible correction-readiness concerns.</p>
                        <p><strong>Review before copying or printing:</strong> check records flagged for source check, records missing reviewer-created status/note cues, important source-derived values, missing local/test traceability values, and any wording that seems wrong, incomplete, confusing, or risky.</p>
                        <p>Source traceability available means visible source URL, raw SHA-256 hash, raw artifact reference, connector metadata, retrieval timestamp, or source document/report marker cues are available to help check important source-derived values. It is not a source-completeness proof.</p>
                        <p><strong>Correction-readiness before copying or printing:</strong> if a source-derived value looks wrong or incomplete, check source traceability first and capture the possible correction concern in a reviewer-created note or feedback for now. This draft does not change source-derived records, alter source-derived values, or submit correction decisions.</p>
                        <p>If copy/print preparation content seems wrong, incomplete, confusing, or risky, use the feedback link before using this draft.</p>
                    </section>
                    <section aria-labelledby="draft-scope-heading">
                        <h3 id="draft-scope-heading">Packet scope</h3>
                        <dl class="summary-list">
                            <dt>Facility / license</dt>
                            <dd>{_escape(_packet_facility_label(records, return_context))}</dd>
                            <dt>Date range</dt>
                            <dd>{_escape(_packet_draft_date_scope(return_context))}</dd>
                            <dt>Mode</dt>
                            <dd>{_escape(_runtime_mode_label_for_reviewer())}</dd>
                            <dt>Prepared from</dt>
                            <dd>{_escape(_packet_prepared_from(return_context))}</dd>
                            <dt>Generated</dt>
                            <dd>{_escape(generated_at)}</dd>
                            <dt>Records included</dt>
                            <dd>{len(records)}</dd>
                        </dl>
                        <p><strong>Important limitation:</strong> This is a local/test preparation draft. It is not a legal report, not a final export, not a certified report, not a production packet, not a source-completeness proof, and not a facility-wide conclusion.</p>
                    </section>
                    <section aria-labelledby="draft-summary-heading">
                        <h3 id="draft-summary-heading">Summary of included records</h3>
                        <dl class="summary-list">
                            <dt>Total records</dt>
                            <dd>{len(records)}</dd>
                            <dt>Records with reviewer-created status</dt>
                            <dd>{state_counts['with_status']}</dd>
                            <dt>Records with reviewer-created notes</dt>
                            <dd>{state_counts['with_notes']}</dd>
                            <dt>Records with review flags</dt>
                            <dd>{_packet_review_flag_count(records)}</dd>
                            <dt>Records with source traceability available</dt>
                            <dd>{traceability_counts['complete']}</dd>
                            <dt>Records ready for preparation review</dt>
                            <dd>{readiness_counts['ready']}</dd>
                            <dt>Records needing source check</dt>
                            <dd>{readiness_counts['needs_source_check']}</dd>
                            <dt>Records needing reviewer-created status/note attention</dt>
                            <dd>{readiness_counts['needs_reviewer_attention']}</dd>
                            <dt>Findings represented</dt>
                            <dd>{_escape(_packet_findings_text(findings))}</dd>
                        </dl>
                    </section>
                    <section aria-labelledby="draft-review-readiness-heading">
                        <h3 id="draft-review-readiness-heading">Review-readiness before copying or printing</h3>
                        <p>Review before copying or printing: this local/test packet draft is a preparation draft.
                        Check source traceability, review flags, and reviewer-created status/note cues
                        before relying on any source-derived value in a handoff.</p>
                        <p>Review before relying on this packet also means confirming the facility/date context and the included complaint records match the queue you intended to prepare. If the packet content looks incomplete, risky, or not ready, return to the queue, open reviewer detail, or use feedback before copying or printing.</p>
                        <p>Possible correction concerns should remain reviewer-created observations or
                        feedback for now. The future correction workflow is not implemented here, and this
                        draft does not submit correction decisions.</p>
                        <ul>
                            <li>{readiness_counts['needs_source_check']} record(s) may still need source check based on visible review flags, missing local/test dates, proxy cues, or missing traceability.</li>
                            <li>{readiness_counts['needs_reviewer_attention']} record(s) may still need reviewer-created status/note attention before packet preparation.</li>
                            <li>{readiness_counts['ready']} record(s) have source traceability available and at least one reviewer-created status/note cue.</li>
                        </ul>
                        <p>This is not a legal report, not a final export, not a certified report, and not a source-completeness proof.</p>
                    </section>
                    <section aria-labelledby="draft-traceability-heading">
                        <h3 id="draft-traceability-heading">Source traceability readiness</h3>
                        <dl class="summary-list">
                            <dt>Source URL available</dt>
                            <dd>{traceability_counts['source_url']}</dd>
                            <dt>Raw SHA-256 available</dt>
                            <dd>{traceability_counts['raw_sha256']}</dd>
                            <dt>Connector/retrieval metadata available</dt>
                            <dd>{traceability_counts['connector_retrieval']}</dd>
                            <dt>Missing visible traceability cues</dt>
                            <dd>{traceability_counts['missing_any']}</dd>
                        </dl>
                    </section>
                    <section aria-labelledby="draft-records-heading">
                        <h3 id="draft-records-heading">Included complaint records</h3>
{record_sections}
                    </section>
                    <section aria-labelledby="draft-reviewer-created-heading">
                        <h3 id="draft-reviewer-created-heading">Reviewer-created state included in this draft</h3>
                        <ul>
                            <li>Status and note presence are reviewer-created state.</li>
                            <li>They do not change source-derived complaint records.</li>
                            <li>They may point to possible correction concerns, but this draft does not alter source-derived values.</li>
                            <li>Reviewer-created note text is not printed here; use reviewer detail when note content needs review.</li>
                        </ul>
                    </section>
                    <section aria-labelledby="draft-does-not-prove-heading">
                        <h3 id="draft-does-not-prove-heading">What this draft does not prove</h3>
                        <ul>
                            <li>It is not a source-completeness proof.</li>
                            <li>It does not prove no other complaints exist.</li>
                            <li>It does not make legal, facility-wide, harm, abuse, neglect, liability, or rights-deprivation conclusions.</li>
                            <li>It does not create source conclusions beyond source-derived finding labels.</li>
                            <li>It does not submit correction decisions or replace source-derived records.</li>
                        </ul>
                    </section>
                    <section aria-labelledby="copyable-packet-summary-heading">
                        <h3 id="copyable-packet-summary-heading">Copyable packet summary</h3>
                        <p>Copy this plain text into a local note or review handoff draft when useful. The app does not save or send this text.</p>
                        <pre class="copyable-packet-summary">{_escape(copy_summary)}</pre>
                    </section>
                    <nav class="packet-draft-actions" aria-label="Packet draft navigation">
                        <ul>
                            <li><a href="{_escape(_packet_preview_href(return_context))}">Back to local/test packet preview</a></li>
                            <li><a href="{_escape(_ccld_request_href([], return_context))}">Back to review queue</a></li>
                            <li><a href="{_escape(feedback_href)}">Report copy/print preparation concern</a></li>
                        </ul>
                    </nav>
                    <details class="technical-details">
                        <summary>Technical runtime details</summary>
                        {_render_scope_notice(workflow)}
                        <p>No export file is generated by this draft. Opening, printing, or copying this page does not mutate source-derived records, reviewer-created state, audit rows, import batches, or operational metadata.</p>
                    </details>
                </article>
                """,
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
        saved_action=None,
        saved_value=None,
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
        saved_action="note",
        saved_value="added",
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
        saved_action="status",
        saved_value=_REVIEWER_STATUS_LABELS.get(reviewer_status, reviewer_status),
        return_context=return_context,
    )


def _detail_html_response(
    status: int,
    payload: Mapping[str, Any],
    context: ReviewerUiContext,
    *,
    saved_action: str | None,
    saved_value: str | None,
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
            saved_action=saved_action,
            saved_value=saved_value,
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
    cards = "\n".join(
        _render_review_item_card(record, state_summaries) for record in records
    )
    if not rows:
        rows = """        <tr>
                    <td colspan="11">No seeded source-derived review records match the
                    current search.</td>
        </tr>"""
        cards = """        <article class="empty-state-card result-card">
          <div>
            <h3>No matching complaint records</h3>
            <p>No seeded source-derived review records match the current search.</p>
          </div>
        </article>"""
        returned_count = _int_value(_mapping(queue, "pagination"), "returned_count")
    no_results_notice = _render_no_results_notice(search_query, records)
    return _page(
                title="Complaint records ready for review",
                heading="Complaint records ready for review",
        actor_label=actor_label,
        main=f"""
        {_render_reviewer_case_brief(records, state_summaries)}
                {no_results_notice}
        <section aria-labelledby="reviewer-list-heading">
                        <h2 id="reviewer-list-heading">Worklist</h2>
                <div class="result-list" aria-label="Complaint records ready for review">
        {cards}
                </div>
                <details>
                    <summary>Filter or search queue</summary>
            <form action="{REVIEWER_UI_RECORDS_PATH}" method="get">
        <p>
          <label for="q">Search seeded review records</label>
                    <input id="q" name="q" type="search" value="{_escape(search_query)}"
                        aria-describedby="reviewer-search-help">
                    <span id="reviewer-search-help">Search by complaint control number,
                    finding, facility/license number, source document ID, or loaded record key.
                    Keyboard flow: search filters this queue, and each Open record link includes
                    the complaint identifier before opening reviewer detail.</span>
        </p>
        <p>
          <button type="submit">Search</button>
          <a href="{REVIEWER_UI_RECORDS_PATH}">Clear search</a>
        </p>
      </form>
            <p class="helper-text">Showing {len(records)} of {returned_count} complaint records.</p>
                </details>
        <details>
          <summary>Show table view</summary>
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
            </details>
        {_render_scope_notice(workflow)}
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
    delay_count = sum(1 for record in records if _has_delay_flag(_mapping(_mapping(record, "source_record"), "original_values")))
    missing_date_count = sum(1 for record in records if _has_missing_date_flag(_mapping(_mapping(record, "source_record"), "original_values")))
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
    return f"""<section class="quiet-section" aria-labelledby="reviewer-queue-summary-heading">
        <h3 id="reviewer-queue-summary-heading">Queue status summary</h3>
        <div class="stat-grid" aria-label="Reviewer status counts">
{status_cards}
        </div>
        <div class="metric-strip" aria-label="Review flag summary">
            <div class="metric-card"><strong>{delay_count}</strong><span>Delay indicators</span></div>
            <div class="metric-card"><strong>{missing_date_count}</strong><span>Missing dates</span></div>
            <div class="metric-card"><strong>{traceability_count}</strong><span>Source traceability available</span></div>
        </div>
        <p class="helper-text">{note_count} with notes; {status_count} with reviewer status. {_next_review_item_markup(next_record, state_summaries)}</p>
    </section>"""


def _render_reviewer_case_brief(
    records: list[Mapping[str, Any]],
    state_summaries: Mapping[str, Mapping[str, Any]],
) -> str:
    case_records = tuple(
        _case_brief_record_from_review_item(index, record, state_summaries)
        for index, record in enumerate(records)
    )
    if not case_records:
        return """        <section class="hero-card" aria-labelledby="reviewer-queue-heading">
                        <p class="launch-kicker">Legal review work queue</p>
                        <h2 id="reviewer-queue-heading">Complaint records ready for review</h2>
                        <p>No complaint records are currently visible in this reviewer queue.</p>
        </section>"""
    first_record = case_records[0]
    return render_facility_case_brief(
        FacilityCaseBrief(
            facility_number=first_record.facility_number,
            facility_name=first_record.facility_name,
            date_range="not provided",
            mode_label=_runtime_mode_label_for_reviewer(),
            mode_badge_class=_mode_badge_class_for_reviewer(_runtime_mode_label_for_reviewer()),
            records=case_records,
            record_count_label="Complaint records visible",
            full_queue_href=REVIEWER_UI_RECORDS_PATH,
            packet_preview_href=REVIEWER_UI_PACKET_PREVIEW_PATH,
            packet_draft_href=_packet_draft_href_for_queue(case_records),
        )
    )


def _render_packet_preview(
    records: list[Mapping[str, Any]],
    state_summaries: Mapping[str, Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
    *,
    workflow: Mapping[str, Any],
    actor_label: str | None,
) -> str:
    traceability_counts = _packet_traceability_counts(records)
    state_counts = _packet_reviewer_state_counts(records, state_summaries)
    readiness_counts = _packet_readiness_counts(records, state_summaries)
    feedback_href = _feedback_href(
        workflow_area="packet-preview",
        page_path=REVIEWER_UI_PACKET_PREVIEW_PATH,
        return_context=return_context,
        prompt="Describe copy/print preparation, packet readiness, source-check, or reviewer-state confusion.",
    )
    record_cards = "\n".join(
        _render_packet_preview_record(record, state_summaries, return_context)
        for record in records
    )
    if not record_cards:
        record_cards = """        <article class="empty-state-card result-card">
          <h3>No complaint records included</h3>
          <p>No loaded local/test complaint records match this packet preview context.</p>
        </article>"""
    return _page(
                title="Review packet preview",
                heading="Review packet preview",
        actor_label=actor_label,
        main=f"""
        <section class="hero-card" aria-labelledby="packet-preview-heading">
          <p class="launch-kicker">Local/test preparation preview</p>
                    <h2 id="packet-preview-heading">Local/test packet preparation preview</h2>
                    <p>This preview helps identify which loaded local/test complaint records, readiness cues, source traceability cues, and reviewer-created status/note cues are included for the current facility/date context before browser copy or print preparation. It is not a legal report, not a final export, not a certified report, not a production packet, and not a source-completeness proof.</p>
                    <p><strong>Packet readiness means local/test review readiness only.</strong> A packet may be ready for manual review, browser copy, or browser print after the tester confirms the active facility/date context, included record count, important source-derived values, visible source traceability, reviewer-created status/note cues, and possible correction-readiness concerns.</p>
          <dl class="summary-list">
            <dt>Facility / license</dt>
            <dd>{_escape(_packet_facility_label(records, return_context))}</dd>
            <dt>Date range</dt>
            <dd>{_escape(_return_context_date_range(return_context))}</dd>
            <dt>Mode</dt>
            <dd>{_escape(_runtime_mode_label_for_reviewer())}</dd>
            <dt>Records included</dt>
            <dd>{len(records)}</dd>
                        <dt>Records with review flags or possible delay indicators</dt>
                        <dd>{_packet_review_flag_count(records)}</dd>
            <dt>Reviewer-created statuses/notes represented</dt>
            <dd>{state_counts['with_status']} with status; {state_counts['with_notes']} with notes</dd>
            <dt>Source traceability available</dt>
            <dd>{traceability_counts['complete']} complete; {traceability_counts['missing_any']} missing one or more visible traceability cues</dd>
                        <dt>Review-readiness checkpoint</dt>
                        <dd>{readiness_counts['ready']} ready for preparation review; {readiness_counts['needs_source_check']} need source check; {readiness_counts['needs_reviewer_attention']} need reviewer-created status/note attention</dd>
          </dl>
                    <div class="form-actions">
                                                <a class="button" href="{_escape(_packet_draft_href(return_context))}">Open local/test preparation draft for browser copy or print</a>
                                                <a class="button button-secondary" href="{_escape(_ccld_request_href([], return_context))}">Return to same facility/date queue</a>
                                                <a class="button button-secondary" href="{_escape(feedback_href)}">Report copy/print preparation concern</a>
                    </div>
        </section>
                <section aria-labelledby="before-copying-printing-heading">
                    <h2 id="before-copying-printing-heading">Before copying or printing</h2>
                    <p>Use this checklist before using browser copy or print from the local/test preparation draft.</p>
                    <ul>
                        <li>Confirm the active facility/date context and included complaint-record count match the queue you intended to prepare.</li>
                        <li>Review records flagged for source check before relying on important source-derived values.</li>
                        <li>Review records missing reviewer-created status/note cues when the readiness counts show attention is needed.</li>
                        <li>Confirm source traceability for important source-derived values; source traceability available means visible source URL, raw SHA-256 hash, raw artifact reference, connector metadata, retrieval timestamp, or source document/report marker cues are available for checking, not that the packet is a source-completeness proof.</li>
                        <li>If a source-derived value looks wrong or incomplete, check source traceability first and capture the possible correction concern in a reviewer-created note or feedback for now.</li>
                        <li>Use feedback if records, wording, readiness cues, or copy/print preparation content seems wrong, incomplete, confusing, or risky.</li>
                    </ul>
                </section>
                <section aria-labelledby="packet-readiness-heading">
                    <h2 id="packet-readiness-heading">Review-readiness summary</h2>
                    <p>This local/test packet preview is a preparation checkpoint. Use it to decide what still needs source check or reviewer-created status/note attention before browser copy or print.</p>
                    <p>Review before relying on this packet means using reviewer detail and source traceability to resolve confusing, incomplete, risky, or not-ready records before copying, printing, or sharing a local handoff draft.</p>
                    <dl class="summary-list">
                        <dt>Records ready for preparation review</dt>
                        <dd>{readiness_counts['ready']}</dd>
                        <dt>Records needing source check</dt>
                        <dd>{readiness_counts['needs_source_check']}</dd>
                        <dt>Records needing reviewer-created status/note attention</dt>
                        <dd>{readiness_counts['needs_reviewer_attention']}</dd>
                    </dl>
                    <p>Source-derived values should be checked against traceability when important. This preview is not a legal report, not a final export, not a certified report, and not a source-completeness proof.</p>
                    <p>Packet preview includes source-derived values and reviewer-created cues, but it does not change source-derived records or submit correction decisions. Possible correction concerns should stay in reviewer-created notes or feedback for now.</p>
                </section>
        <section aria-labelledby="packet-traceability-heading">
          <h2 id="packet-traceability-heading">Traceability readiness</h2>
          <dl class="summary-list">
            <dt>Records with source URL available</dt>
            <dd>{traceability_counts['source_url']}</dd>
            <dt>Records with raw SHA-256 available</dt>
            <dd>{traceability_counts['raw_sha256']}</dd>
            <dt>Records with connector/retrieval metadata available</dt>
            <dd>{traceability_counts['connector_retrieval']}</dd>
            <dt>Records missing visible traceability cues</dt>
            <dd>{traceability_counts['missing_any']}</dd>
          </dl>
          <p>These are availability counts only. They do not prove public-source completeness.</p>
        </section>
        <section aria-labelledby="packet-reviewer-state-heading">
          <h2 id="packet-reviewer-state-heading">Reviewer-created state summary</h2>
          <p>These counts come from existing reviewer-created status/note rows. They are reviewer-created state, not source facts.</p>
          <dl class="summary-list">
            <dt>Records with reviewer-created status</dt>
            <dd>{state_counts['with_status']}</dd>
            <dt>Records with reviewer-created notes</dt>
            <dd>{state_counts['with_notes']}</dd>
            <dt>Records without reviewer-created state</dt>
            <dd>{state_counts['without_state']}</dd>
            <dt>Not started</dt>
            <dd>{state_counts['not_started']}</dd>
            <dt>In review</dt>
            <dd>{state_counts['in_review']}</dd>
            <dt>Needs follow-up</dt>
            <dd>{state_counts['needs_follow_up']}</dd>
            <dt>Reviewed</dt>
            <dd>{state_counts['reviewed']}</dd>
            <dt>Blocked</dt>
            <dd>{state_counts['blocked']}</dd>
          </dl>
        </section>
        <section aria-labelledby="packet-records-heading">
          <h2 id="packet-records-heading">Included complaint records</h2>
          <div class="result-list" aria-label="Included complaint records">
{record_cards}
          </div>
        </section>
        <section aria-labelledby="packet-notes-heading">
          <h2 id="packet-notes-heading">Review packet notes</h2>
          <ul>
            <li>This preview is a local/test preparation aid.</li>
            <li>Source-derived fields remain separate from reviewer-created notes/status.</li>
            <li>Possible correction concerns are reviewer-created observations for notes or feedback in this local/test workflow.</li>
            <li>Review flags are screening aids, not legal conclusions.</li>
            <li>The CCLD public portal remains the source of record.</li>
            <li>This preview is not a legal report, not a final export, not a certified report, not a production packet, and not a source-completeness proof.</li>
                        <li>If packet readiness, source-check-needed wording, missing reviewer-created state, copy/print preparation, or keyboard flow is confusing, use the feedback link with this packet context.</li>
          </ul>
        </section>
        <details class="technical-details">
          <summary>Technical runtime details</summary>
          {_render_scope_notice(workflow)}
          <p>No export file is generated by this preview. Opening this page does not mutate source-derived records, reviewer-created state, audit rows, import batches, or operational metadata.</p>
        </details>
        """,
    )


def _render_packet_preview_record(
    item: Mapping[str, Any],
    state_summaries: Mapping[str, Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
) -> str:
    source_record = _mapping(item, "source_record")
    identity = _mapping(source_record, "identity")
    source_document = _mapping(source_record, "source_document")
    original_values = _mapping(source_record, "original_values")
    source_record_key = _string(identity, "source_record_key")
    state_summary = state_summaries.get(source_record_key, _empty_state_summary())
    detail_href = _reviewer_detail_href(source_record_key, return_context)
    label = _display_value(original_values.get("complaint_control_number") or source_record_key)
    readiness_cue = _packet_readiness_cue(item, state_summary)
    flags = _review_flag_labels(original_values, source_document)
    flag_items = "\n".join(f"              <li>{_escape(flag)}</li>" for flag in flags)
    if not flag_items:
        flag_items = "              <li>No review flags are visible from loaded source-derived fields.</li>"
    why_items = "\n".join(
        f"              <li>{_escape(reason)}</li>"
        for reason in _packet_inclusion_reasons(item, state_summary)
    )
    return f"""        <article class="result-card work-item" aria-labelledby="packet-record-{_escape(source_record_key)}-heading">
          <div>
            <p class="stage-kicker">Included complaint record</p>
            <h3 id="packet-record-{_escape(source_record_key)}-heading">{_escape(label)}</h3>
            <dl>
              <dt>Finding</dt>
              <dd>{_escape(_optional_string(original_values, 'finding'))}</dd>
              <dt>Key dates</dt>
              <dd>{_escape(_date_summary(original_values))}</dd>
              <dt>Reviewer-created status</dt>
              <dd>{_escape(_latest_status_text(state_summary))}</dd>
              <dt>Reviewer note</dt>
              <dd>{_escape(_card_note_presence_text(state_summary))}</dd>
              <dt>Source traceability</dt>
              <dd>{_escape(_source_traceability_cue(source_document))}</dd>
              <dt>Missing local/test traceability values</dt>
              <dd>{_escape(_missing_traceability_values_text(source_document))}</dd>
                            <dt>Review-readiness cue</dt>
                            <dd>{_escape(readiness_cue)}</dd>
            </dl>
            <section aria-labelledby="packet-why-{_escape(source_record_key)}-heading">
              <h4 id="packet-why-{_escape(source_record_key)}-heading">Why included</h4>
              <ul>
{why_items}
              </ul>
            </section>
            <section aria-labelledby="packet-flags-{_escape(source_record_key)}-heading">
              <h4 id="packet-flags-{_escape(source_record_key)}-heading">Review flags</h4>
              <ul>
{flag_items}
              </ul>
            </section>
          </div>
          <p><a class="button" href="{_escape(detail_href)}">Open record { _escape(label) }</a></p>
        </article>"""


def _render_packet_draft_record(
    item: Mapping[str, Any],
    state_summaries: Mapping[str, Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
) -> str:
    source_record = _mapping(item, "source_record")
    identity = _mapping(source_record, "identity")
    source_document = _mapping(source_record, "source_document")
    original_values = _mapping(source_record, "original_values")
    source_record_key = _string(identity, "source_record_key")
    state_summary = state_summaries.get(source_record_key, _empty_state_summary())
    detail_href = _reviewer_detail_href(source_record_key, return_context)
    label = _display_value(original_values.get("complaint_control_number") or source_record_key)
    flags = _packet_review_flags_text(original_values, source_document)
    why = "; ".join(_packet_inclusion_reasons(item, state_summary))
    readiness_cue = _packet_readiness_cue(item, state_summary)
    return f"""            <section class="packet-draft-record" aria-labelledby="draft-record-{_escape(source_record_key)}-heading">
              <h4 id="draft-record-{_escape(source_record_key)}-heading">{_escape(label)}</h4>
              <dl class="summary-list">
                <dt>Complaint control number</dt>
                <dd>{_escape(label)}</dd>
                <dt>Finding</dt>
                <dd>{_escape(_optional_string(original_values, 'finding'))}</dd>
                <dt>Key dates</dt>
                <dd>{_escape(_date_summary(original_values))}</dd>
                <dt>Review flags</dt>
                <dd>{_escape(flags)}</dd>
                <dt>Reviewer-created status</dt>
                <dd>{_escape(_latest_status_label_text(state_summary))}</dd>
                <dt>Reviewer-created note presence</dt>
                <dd>{_escape(_card_note_presence_text(state_summary))}</dd>
                <dt>Why included</dt>
                <dd>{_escape(why)}</dd>
                <dt>Source traceability summary</dt>
                <dd>{_escape(_source_traceability_cue(source_document))}</dd>
                <dt>Missing local/test traceability values</dt>
                <dd>{_escape(_missing_traceability_values_text(source_document))}</dd>
                                <dt>Review-readiness cue</dt>
                                <dd>{_escape(readiness_cue)}</dd>
              </dl>
              <p class="packet-draft-actions"><a href="{_escape(detail_href)}">Open record { _escape(label) }</a></p>
            </section>"""


def _packet_copy_summary(
    records: list[Mapping[str, Any]],
    state_summaries: Mapping[str, Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
    traceability_counts: Mapping[str, int],
    state_counts: Mapping[str, int],
    findings: Mapping[str, int],
    generated_at: str,
) -> str:
    readiness_counts = _packet_readiness_counts(records, state_summaries)
    lines = [
        "Attorney Review Packet Draft",
        f"Facility/license: {_packet_facility_label(records, return_context)}",
        f"Date range: {_packet_draft_date_scope(return_context)}",
        f"Generated: {generated_at}",
        f"Records included: {len(records)}",
        f"Findings represented: {_packet_findings_text(findings)}",
        "",
        "Reviewer-created state summary",
        f"- Records with reviewer-created status: {state_counts['with_status']}",
        f"- Records with reviewer-created notes: {state_counts['with_notes']}",
        f"- Records without reviewer-created state: {state_counts['without_state']}",
        "",
        "Review-readiness before copy/print",
        "- Packet readiness means local/test review readiness for manual browser copy or print after checking facility/date context, included records, source traceability, reviewer-created status/note cues, and possible correction-readiness concerns.",
        f"- Records ready for preparation review: {readiness_counts['ready']}",
        f"- Records needing source check: {readiness_counts['needs_source_check']}",
        "- Records needing reviewer-created status/note attention: "
        f"{readiness_counts['needs_reviewer_attention']}",
        "- Review before copy/print; this is local/test preparation only.",
        "",
        "Source traceability readiness",
        f"- Source URL available: {traceability_counts['source_url']}",
        f"- Raw SHA-256 available: {traceability_counts['raw_sha256']}",
        f"- Connector/retrieval metadata available: {traceability_counts['connector_retrieval']}",
        f"- Missing visible traceability cues: {traceability_counts['missing_any']}",
        "",
        "Included complaint records",
    ]
    if not records:
        lines.append("- None shown for this packet context.")
    for item in records:
        source_record = _mapping(item, "source_record")
        source_document = _mapping(source_record, "source_document")
        original_values = _mapping(source_record, "original_values")
        identity = _mapping(source_record, "identity")
        source_record_key = _string(identity, "source_record_key")
        state_summary = state_summaries.get(source_record_key, _empty_state_summary())
        label = _display_value(original_values.get("complaint_control_number") or source_record_key)
        lines.append(
            "- "
            + label
            + f"; finding: {_optional_string(original_values, 'finding')}"
            + f"; key dates: {_date_summary(original_values)}"
            + f"; review flags: {_packet_review_flags_text(original_values, source_document)}"
            + f"; reviewer status: {_latest_status_label_text(state_summary)}"
            + f"; reviewer note: {_card_note_presence_text(state_summary)}"
            + f"; source traceability: {_source_traceability_cue(source_document)}"
            + f"; missing local/test traceability values: {_missing_traceability_values_text(source_document)}"
        )
    lines.extend(
        [
            "",
            "Limitations",
            "- This is a local/test preparation draft, not a legal report, not a final export, not a certified report, not a source-completeness proof, and not a facility-wide conclusion.",
            "- Source-derived fields remain separate from reviewer-created notes/status.",
            "- Review flags are screening aids, not legal conclusions.",
            "- The CCLD public portal remains the source of record.",
        ]
    )
    return "\n".join(lines)


def _packet_finding_counts(records: list[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in records:
        original_values = _mapping(_mapping(item, "source_record"), "original_values")
        finding = _optional_string(original_values, "finding") or "unknown"
        counts[finding] = counts.get(finding, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (item[0] == "unknown", item[0])))


def _packet_findings_text(findings: Mapping[str, int]) -> str:
    if not findings:
        return "none represented"
    return "; ".join(f"{label}: {count}" for label, count in findings.items())


def _packet_review_flag_count(records: list[Mapping[str, Any]]) -> int:
    return sum(
        1
        for item in records
        if _review_flag_labels(
            _mapping(_mapping(item, "source_record"), "original_values"),
            _mapping(_mapping(item, "source_record"), "source_document"),
        )
    )


def _packet_readiness_counts(
    records: list[Mapping[str, Any]],
    state_summaries: Mapping[str, Mapping[str, Any]],
) -> dict[str, int]:
    counts = {
        "ready": 0,
        "needs_source_check": 0,
        "needs_reviewer_attention": 0,
    }
    for item in records:
        source_record = _mapping(item, "source_record")
        identity = _mapping(source_record, "identity")
        source_record_key = _string(identity, "source_record_key")
        summary = state_summaries.get(source_record_key, _empty_state_summary())
        needs_source_check = _packet_needs_source_check(item)
        needs_reviewer_attention = _packet_needs_reviewer_attention(summary)
        if needs_source_check:
            counts["needs_source_check"] += 1
        if needs_reviewer_attention:
            counts["needs_reviewer_attention"] += 1
        if not needs_source_check and not needs_reviewer_attention:
            counts["ready"] += 1
    return counts


def _packet_readiness_cue(
    item: Mapping[str, Any],
    state_summary: Mapping[str, Any],
) -> str:
    cues: list[str] = []
    if _packet_needs_source_check(item):
        cues.append("Needs source check before copy/print")
    else:
        cues.append("Source traceability available for preparation review")
    if _packet_needs_reviewer_attention(state_summary):
        cues.append("Reviewer-created status/note attention suggested")
    else:
        cues.append("Reviewer-created status/note cue present")
    return "; ".join(cues) + "."


def _packet_needs_source_check(item: Mapping[str, Any]) -> bool:
    source_record = _mapping(item, "source_record")
    source_document = _mapping(source_record, "source_document")
    original_values = _mapping(source_record, "original_values")
    return bool(
        _has_missing_date_flag(original_values)
        or original_values.get("report_date_used_as_proxy") is True
        or _has_delay_flag(original_values)
        or not _has_visible_traceability_document(source_document)
    )


def _packet_needs_reviewer_attention(summary: Mapping[str, Any]) -> bool:
    return not _summary_optional_string(summary, "latest_status") or _summary_int(summary, "note_count") == 0


def _packet_review_flags_text(
    original_values: Mapping[str, Any],
    source_document: Mapping[str, Any],
) -> str:
    flags = _review_flag_labels(original_values, source_document)
    if not flags:
        return "No review flags are visible from loaded source-derived fields."
    return "; ".join(flags)


def _latest_status_label_text(summary: Mapping[str, Any]) -> str:
    latest_status = _summary_optional_string(summary, "latest_status")
    if latest_status is None:
        return "No reviewer-created status"
    return _REVIEWER_STATUS_LABELS.get(latest_status, latest_status)


def _packet_draft_date_scope(return_context: CcldQueueReturnContext) -> str:
    if return_context.start_date or return_context.end_date:
        return _return_context_date_range(return_context)
    return "All loaded local/test records for this facility"


def _render_packet_preview_context_needed(*, actor_label: str | None) -> str:
        return _page(
                title="Review packet preview",
                heading="Review packet preview",
                actor_label=actor_label,
                main=f"""
                <section class="hero-card" aria-labelledby="packet-context-needed-heading">
                    <p class="launch-kicker">Local/test preparation preview</p>
                    <h2 id="packet-context-needed-heading">No facility/date packet context was supplied.</h2>
                    <p>Start from Retrieve or the Review queue to build a packet for a specific facility/date range.</p>
                    <div class="form-actions">
                        <a class="button" href="{CCLD_RECORD_REQUEST_PATH}">Open Retrieve</a>
                        <a class="button button-secondary" href="{REVIEWER_UI_RECORDS_PATH}">Open Review queue</a>
                    </div>
                    <p>This preview is not a bounded facility/date packet and does not show included records until a facility/date context is supplied. It is not a legal report, not a final export, not a certified report, and not a source-completeness proof.</p>
                </section>
                """,
        )


def _packet_prepared_from(return_context: CcldQueueReturnContext) -> str:
    if return_context.context_origin == "facility_lookup":
        return "Facility lookup CCLD request context"
    if return_context.context_origin == "prefilled_link":
        return "Prefilled CCLD request context"
    return "Manual CCLD request or reviewer queue context"


def _packet_inclusion_reasons(
    item: Mapping[str, Any],
    state_summary: Mapping[str, Any],
) -> tuple[str, ...]:
    source_record = _mapping(item, "source_record")
    source_document = _mapping(source_record, "source_document")
    original_values = _mapping(source_record, "original_values")
    reasons = ["Part of the current loaded facility/date review queue."]
    if _summary_optional_string(state_summary, "latest_status"):
        reasons.append("Reviewer status added.")
    else:
        reasons.append("No reviewer-created status yet.")
    if _summary_int(state_summary, "note_count") > 0:
        reasons.append("Reviewer note added.")
    if _review_flag_labels(original_values, source_document):
        if _has_delay_flag(original_values):
            reasons.append("Possible delay indicator.")
        if _has_missing_date_flag(original_values):
            reasons.append("Needs source check.")
        if original_values.get("report_date_used_as_proxy") is True:
            reasons.append("Report date proxy cue.")
    if _has_visible_traceability_document(source_document):
        reasons.append("Source traceability available.")
    else:
        reasons.append("Local/test traceability value missing; needs source check.")
    finding = _optional_string(original_values, "finding")
    if finding and finding != "unknown":
        reasons.append(f"Finding value shown: {finding}.")
    return tuple(dict.fromkeys(reasons))


def _packet_traceability_counts(records: list[Mapping[str, Any]]) -> dict[str, int]:
    counts = {
        "source_url": 0,
        "raw_sha256": 0,
        "connector_retrieval": 0,
        "complete": 0,
        "missing_any": 0,
    }
    for item in records:
        source_document = _mapping(_mapping(item, "source_record"), "source_document")
        has_source_url = _has_display_value(source_document.get("source_url"))
        has_raw_sha = _has_display_value(source_document.get("raw_sha256"))
        has_connector_retrieval = _has_display_value(source_document.get("connector_name")) and _has_display_value(source_document.get("retrieved_at"))
        if has_source_url:
            counts["source_url"] += 1
        if has_raw_sha:
            counts["raw_sha256"] += 1
        if has_connector_retrieval:
            counts["connector_retrieval"] += 1
        if has_source_url and has_raw_sha and has_connector_retrieval:
            counts["complete"] += 1
        else:
            counts["missing_any"] += 1
    return counts


def _packet_reviewer_state_counts(
    records: list[Mapping[str, Any]],
    state_summaries: Mapping[str, Mapping[str, Any]],
) -> dict[str, int]:
    counts = {
        "with_status": 0,
        "with_notes": 0,
        "without_state": 0,
        "not_started": 0,
        "in_review": 0,
        "needs_follow_up": 0,
        "reviewed": 0,
        "blocked": 0,
    }
    for item in records:
        summary = _state_summary_for_item(item, state_summaries)
        status = _reviewer_queue_status(summary)
        counts[status] += 1
        if _summary_optional_string(summary, "latest_status"):
            counts["with_status"] += 1
        if _summary_int(summary, "note_count") > 0:
            counts["with_notes"] += 1
        if _summary_int(summary, "total_rows") == 0:
            counts["without_state"] += 1
    return counts


def _packet_facility_label(
    records: list[Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
) -> str:
    if return_context.facility_number:
        if return_context.lookup_facility_name:
            return f"{return_context.facility_number}; {return_context.lookup_facility_name}"
        return return_context.facility_number
    for item in records:
        identity = _mapping(_mapping(item, "source_record"), "identity")
        facility_number = _optional_string(identity, "facility_id")
        if facility_number != "unknown":
            return facility_number
    return "unknown"


def _filter_packet_preview_items(
    records: list[Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
) -> list[Mapping[str, Any]]:
    return [
        record
        for record in records
        if _packet_item_matches_context(record, return_context)
    ]


def _packet_item_matches_context(
    item: Mapping[str, Any],
    return_context: CcldQueueReturnContext,
) -> bool:
    source_record = _mapping(item, "source_record")
    if return_context.facility_number and not _packet_record_matches_facility(source_record, return_context.facility_number):
        return False
    if return_context.start_date or return_context.end_date:
        return _packet_record_matches_date_range(source_record, return_context)
    return True


def _packet_record_matches_facility(
    source_record: Mapping[str, Any],
    facility_number: str,
) -> bool:
    identity = _mapping(source_record, "identity")
    original_values = _mapping(source_record, "original_values")
    source_document = _mapping(source_record, "source_document")
    facility_id = _optional_string(identity, "facility_id")
    source_url = _optional_string(source_document, "source_url")
    return (
        original_values.get("external_facility_number") == facility_number
        or original_values.get("facility_number") == facility_number
        or facility_id.endswith(facility_number)
        or f"facNum={facility_number}" in source_url
    )


def _packet_record_matches_date_range(
    source_record: Mapping[str, Any],
    return_context: CcldQueueReturnContext,
) -> bool:
    original_values = _mapping(source_record, "original_values")
    record_dates = [
        str(value)[:10]
        for key in (
            "complaint_received_date",
            "visit_date",
            "report_date",
            "date_signed",
            "retrieved_at",
        )
        if _has_display_value(value := original_values.get(key))
    ]
    if not record_dates:
        return return_context.start_date is None and return_context.end_date is None
    for record_date in record_dates:
        if return_context.start_date and record_date < return_context.start_date:
            continue
        if return_context.end_date and record_date > return_context.end_date:
            continue
        return True
    return False


def _packet_preview_context_from_values(values: Mapping[str, list[str]]) -> CcldQueueReturnContext:
    return CcldQueueReturnContext(
        facility_number=_optional_form_value(values, "facility_number")
        or _optional_form_value(values, "return_facility_number"),
        start_date=_optional_form_value(values, "start_date")
        or _optional_form_value(values, "return_start_date"),
        end_date=_optional_form_value(values, "end_date")
        or _optional_form_value(values, "return_end_date"),
        context_origin=_optional_form_value(values, "request_context_origin")
        or _optional_form_value(values, "return_context_origin"),
        lookup_facility_name=_optional_form_value(values, "lookup_facility_name")
        or _optional_form_value(values, "return_lookup_facility_name"),
    )


def _packet_preview_href(return_context: CcldQueueReturnContext) -> str:
    if return_context.facility_number is None:
        return REVIEWER_UI_PACKET_PREVIEW_PATH
    query_values = {
        "facility_number": return_context.facility_number,
        "start_date": return_context.start_date or "",
        "end_date": return_context.end_date or "",
        "request_context_origin": return_context.context_origin or "manual_entry",
        "lookup_facility_name": return_context.lookup_facility_name or "",
    }
    return f"{REVIEWER_UI_PACKET_PREVIEW_PATH}?{urlencode(query_values)}"


def _packet_draft_href(return_context: CcldQueueReturnContext) -> str:
    if return_context.facility_number is None:
        return REVIEWER_UI_PACKET_DRAFT_PATH
    query_values = {
        "facility_number": return_context.facility_number,
        "start_date": return_context.start_date or "",
        "end_date": return_context.end_date or "",
        "request_context_origin": return_context.context_origin or "manual_entry",
        "lookup_facility_name": return_context.lookup_facility_name or "",
    }
    return f"{REVIEWER_UI_PACKET_DRAFT_PATH}?{urlencode(query_values)}"


def _matrix_export_href(return_context: CcldQueueReturnContext) -> str:
    if return_context.facility_number is None:
        return REVIEWER_UI_MATRIX_EXPORT_PATH
    query_values = {
        "facility_number": return_context.facility_number,
        "start_date": return_context.start_date or "",
        "end_date": return_context.end_date or "",
        "request_context_origin": return_context.context_origin or "manual_entry",
        "lookup_facility_name": return_context.lookup_facility_name or "",
    }
    return f"{REVIEWER_UI_MATRIX_EXPORT_PATH}?{urlencode(query_values)}"


def _substantiated_export_href(return_context: CcldQueueReturnContext) -> str:
    return _complaint_export_href(return_context, "substantiated")


def _unsubstantiated_export_href(return_context: CcldQueueReturnContext) -> str:
    return _complaint_export_href(return_context, "unsubstantiated")


def _all_complaints_export_href(return_context: CcldQueueReturnContext) -> str:
    return _complaint_export_href(return_context, "all")


def _serious_review_cue_export_href(return_context: CcldQueueReturnContext) -> str:
    return _complaint_export_href(return_context, "all", review_cue="serious")


def _complaint_export_href(
    return_context: CcldQueueReturnContext,
    status: str,
    review_cue: str | None = None,
) -> str:
    if return_context.facility_number is None:
        if status == "substantiated":
            return REVIEWER_UI_SUBSTANTIATED_EXPORT_PATH
        query_values = {"status": status}
        if review_cue is not None:
            query_values["review_cue"] = review_cue
        return f"{REVIEWER_UI_SUBSTANTIATED_EXPORT_PATH}?{urlencode(query_values)}"
    query_values = {
        "facility_number": return_context.facility_number,
        "start_date": return_context.start_date or "",
        "end_date": return_context.end_date or "",
        "request_context_origin": return_context.context_origin or "manual_entry",
        "lookup_facility_name": return_context.lookup_facility_name or "",
        "facility": return_context.facility_number,
    }
    if status != "substantiated":
        query_values["status"] = status
    if review_cue is not None:
        query_values["review_cue"] = review_cue
    return f"{REVIEWER_UI_SUBSTANTIATED_EXPORT_PATH}?{urlencode(query_values)}"


def _packet_draft_href_for_queue(records: tuple[FacilityCaseBriefRecord, ...]) -> str:
    if not records:
        return REVIEWER_UI_PACKET_DRAFT_PATH
    first_record = records[0]
    query_values = {
        "facility_number": first_record.facility_number,
        "request_context_origin": "prefilled_link",
        "packet_scope": "all_loaded",
    }
    return f"{REVIEWER_UI_PACKET_DRAFT_PATH}?{urlencode(query_values)}"


def _packet_preview_confirmation_link(return_context: CcldQueueReturnContext) -> str:
    if return_context.facility_number is None:
        return ""
    return f'<a class="button button-secondary" href="{_escape(_packet_preview_href(return_context))}">Review packet readiness before copying or printing</a>'


def _packet_draft_confirmation_link(return_context: CcldQueueReturnContext) -> str:
    if return_context.facility_number is None:
        return ""
    return f'<a class="button button-secondary" href="{_escape(_packet_draft_href(return_context))}">Open local/test preparation draft for browser copy or print</a>'


def _case_brief_record_from_review_item(
    index: int,
    item: Mapping[str, Any],
    state_summaries: Mapping[str, Mapping[str, Any]],
) -> FacilityCaseBriefRecord:
    source_record = _mapping(item, "source_record")
    identity = _mapping(source_record, "identity")
    source_document = _mapping(source_record, "source_document")
    original_values = _mapping(source_record, "original_values")
    source_record_key = _string(identity, "source_record_key")
    state_summary = state_summaries.get(source_record_key, _empty_state_summary())
    latest_status = _summary_optional_string(state_summary, "latest_status")
    detail_href = f"{REVIEWER_UI_DETAIL_PATH}?{urlencode({'source_record_key': source_record_key})}"
    facility_number = _optional_string(identity, "facility_id")
    facility_name = _optional_string(original_values, "facility_name")
    if facility_name == "unknown":
        facility_name = ""
    return FacilityCaseBriefRecord(
        source_record_key=source_record_key,
        detail_href=detail_href,
        complaint_control_number=_display_value(
            original_values.get("complaint_control_number") or source_record_key
        ),
        finding=_optional_string(original_values, "finding"),
        complaint_received_date=_optional_string(original_values, "complaint_received_date"),
        visit_date=_optional_string(original_values, "visit_date"),
        report_date=_optional_string(original_values, "report_date"),
        date_signed=_optional_string(original_values, "date_signed"),
        facility_number=facility_number,
        facility_name=facility_name,
        has_source_traceability=_has_visible_traceability_document(source_document),
        reviewer_status=latest_status,
        reviewer_status_label=_REVIEWER_STATUS_LABELS.get(latest_status or "", latest_status),
        reviewer_note_count=_summary_int(state_summary, "note_count"),
        delay_thresholds=_delay_thresholds(original_values),
        missing_first_activity_date=original_values.get("missing_first_activity_date") is True,
        missing_visit_date=not _has_display_value(original_values.get("visit_date")),
        missing_report_date=not _has_display_value(original_values.get("report_date")),
        missing_signed_date=not _has_display_value(original_values.get("date_signed")),
        report_date_used_as_proxy=original_values.get("report_date_used_as_proxy") is True,
        order_index=index,
    )


def _render_detail_flag_reason_section(
    source_record: Mapping[str, Any],
    detail: Mapping[str, Any],
    related_records: list[Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
) -> str:
    record = _case_brief_record_from_detail(source_record, detail, related_records, return_context)
    return render_record_flag_reason_section(record)


def _case_brief_record_from_detail(
    source_record: Mapping[str, Any],
    detail: Mapping[str, Any],
    related_records: list[Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
) -> FacilityCaseBriefRecord:
    identity = _mapping(source_record, "identity")
    source_document = _mapping(source_record, "source_document")
    original_values = _mapping(source_record, "original_values")
    state_summary = _mapping(detail, "associated_reviewer_created_state_summary")
    source_record_key = _string(identity, "source_record_key")
    reviewer_statuses = tuple(_string_items(state_summary.get("reviewer_statuses_present", [])))
    reviewer_status = reviewer_statuses[0] if reviewer_statuses else None
    facility = _facility_context(related_records)
    facility_number = return_context.facility_number or _facility_context_value(facility, "external_facility_number")
    facility_name = _facility_context_value(facility, "facility_name")
    return FacilityCaseBriefRecord(
        source_record_key=source_record_key,
        detail_href=_reviewer_detail_href(source_record_key, return_context),
        complaint_control_number=_display_value(
            original_values.get("complaint_control_number") or source_record_key
        ),
        finding=_optional_string(original_values, "finding"),
        complaint_received_date=_optional_string(original_values, "complaint_received_date"),
        visit_date=_optional_string(original_values, "visit_date"),
        report_date=_optional_string(original_values, "report_date"),
        date_signed=_optional_string(original_values, "date_signed"),
        facility_number=facility_number,
        facility_name=facility_name,
        has_source_traceability=_has_visible_traceability_document(source_document),
        reviewer_status=reviewer_status,
        reviewer_status_label=_REVIEWER_STATUS_LABELS.get(reviewer_status or "", reviewer_status),
        reviewer_note_count=_int_value(state_summary, "total_associated_rows"),
        delay_thresholds=_delay_thresholds(original_values),
        missing_first_activity_date=original_values.get("missing_first_activity_date") is True,
        missing_visit_date=not _has_display_value(original_values.get("visit_date")),
        missing_report_date=not _has_display_value(original_values.get("report_date")),
        missing_signed_date=not _has_display_value(original_values.get("date_signed")),
        report_date_used_as_proxy=original_values.get("report_date_used_as_proxy") is True,
        order_index=0,
    )


def _delay_thresholds(values: Mapping[str, Any]) -> tuple[int, ...]:
    thresholds: list[int] = []
    for days in (30, 60, 90, 120):
        if values.get(f"review_delay_over_{days}_days") is True:
            thresholds.append(days)
    return tuple(thresholds)


def _runtime_mode_label_for_reviewer() -> str:
    demo_mode = os.environ.get("CCLD_RETRIEVAL_DEMO_MODE", "").strip().casefold()
    retrieval_enabled = os.environ.get("CCLD_RETRIEVAL_ENABLED", "").strip().casefold()
    raw_dir = os.environ.get("CCLD_RETRIEVAL_RAW_DIR", "").strip()
    if demo_mode == "mock-success":
        return "Fixture/mock demo"
    if retrieval_enabled == "enabled" and raw_dir:
        return "Live public CCLD"
    return "Retrieval not configured"


def _mode_badge_class_for_reviewer(label: str) -> str:
    if label == "Live public CCLD":
        return "badge badge-live"
    if label == "Fixture/mock demo":
        return "badge badge-demo"
    return "badge badge-muted"


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


def _render_review_item_card(
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
        control_number = _display_value(original_values.get("complaint_control_number") or source_record_key)
        facility_number = _optional_string(identity, "facility_id")
        finding = _optional_string(original_values, "finding")
        reviewer_status_text = _latest_status_text(state_summary)
        note_presence_text = _card_note_presence_text(state_summary)
        return f"""        <article class="result-card work-item" aria-labelledby="record-{_escape(source_record_key)}-heading">
                    <div>
                        <p class="stage-kicker">{_escape(_queue_cue_text(state_summary))}</p>
                        <h3 id="record-{_escape(source_record_key)}-heading">{_escape(control_number)}</h3>
                        <p><span class="badge badge-muted">Finding: {_escape(finding)}</span> <span class="badge badge-demo">Reviewer-created status: {_escape(reviewer_status_text)}</span> <span class="badge badge-muted">{_escape(note_presence_text)}</span></p>
                        {_render_review_flag_chips(original_values, source_document)}
                        <dl>
                            <dt>Facility/license</dt>
                            <dd>{_escape(facility_number)}</dd>
                            <dt>Complaint received</dt>
                            <dd>{_escape(_optional_string(original_values, 'complaint_received_date'))}</dd>
                            <dt>Visit date</dt>
                            <dd>{_escape(_optional_string(original_values, 'visit_date'))}</dd>
                            <dt>Report date</dt>
                            <dd>{_escape(_optional_string(original_values, 'report_date'))}</dd>
                            <dt>Signed</dt>
                            <dd>{_escape(_optional_string(original_values, 'date_signed'))}</dd>
                            <dt>Reviewer-created notes</dt>
                            <dd>{_escape(note_presence_text)}</dd>
                            <dt>Source traceability</dt>
                            <dd>{_escape(_source_traceability_cue(source_document))}</dd>
                        </dl>
                    </div>
                    <p><a class="button" href="{_escape(detail_href)}">Open record</a></p>
                </article>"""


def _card_note_presence_text(summary: Mapping[str, Any]) -> str:
        note_count = _summary_int(summary, "note_count")
        if note_count == 0:
                return "No reviewer note"
        return "Reviewer note added"


def _next_review_item_href(item: Mapping[str, Any] | None) -> str:
        if item is None:
                return REVIEWER_UI_RECORDS_PATH
        source_record = _mapping(item, "source_record")
        identity = _mapping(source_record, "identity")
        source_record_key = _string(identity, "source_record_key")
        return f"{REVIEWER_UI_DETAIL_PATH}?{urlencode({'source_record_key': source_record_key})}"


def _review_action_label(original_values: Mapping[str, Any]) -> str:
    complaint_control_number = original_values.get("complaint_control_number")
    if _has_display_value(complaint_control_number):
        return f"Open record {_display_value(complaint_control_number)}"
    return "Open record"


def _source_traceability_cue(source_document: Mapping[str, Any]) -> str:
    available, missing = _traceability_value_labels(source_document)
    if available and not missing:
        return (
            "Source traceability available: "
            + ", ".join(available)
            + ". Missing local/test traceability values: none. Check source traceability before relying on source-derived values."
        )
    if available:
        return (
            "Source traceability available for: "
            + ", ".join(available)
            + ". Local/test traceability value missing: "
            + ", ".join(missing)
            + ". Check source traceability before relying on source-derived values."
        )
    return (
        "No source traceability values are visible in this local/test row. Local/test traceability value missing: "
        + ", ".join(missing)
        + ". This is not proof of public-source absence and not a source-completeness proof."
    )


def _traceability_value_labels(source_document: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    fields = (
        ("source URL", source_document.get("source_url")),
        ("raw SHA-256 hash", source_document.get("raw_sha256")),
        ("raw artifact reference", source_document.get("raw_path")),
        ("connector metadata", _connector_label(source_document)),
        ("retrieval timestamp", source_document.get("retrieved_at")),
        (
            "source document/report marker",
            source_document.get("report_index") or source_document.get("source_document_id"),
        ),
    )
    available = [label for label, value in fields if _has_display_value(value)]
    missing = [label for label, value in fields if not _has_display_value(value)]
    return available, missing


def _available_traceability_values_text(source_document: Mapping[str, Any]) -> str:
    available, _missing = _traceability_value_labels(source_document)
    if not available:
        return "none visible in this local/test record"
    return ", ".join(available)


def _missing_traceability_values_text(source_document: Mapping[str, Any]) -> str:
    _available, missing = _traceability_value_labels(source_document)
    if not missing:
        return "none"
    return ", ".join(missing)


def _has_delay_flag(original_values: Mapping[str, Any]) -> bool:
    return any(
        original_values.get(field_name) is True
        for field_name in (
            "review_delay_over_30_days",
            "review_delay_over_60_days",
            "review_delay_over_90_days",
            "review_delay_over_120_days",
        )
    )


def _has_missing_date_flag(original_values: Mapping[str, Any]) -> bool:
    return any(
        original_values.get(field_name) is True
        for field_name in (
            "missing_first_activity_date",
            "missing_visit_date",
            "missing_report_date",
        )
    )


def _render_review_flag_chips(
    original_values: Mapping[str, Any],
    source_document: Mapping[str, Any],
) -> str:
    flags = _review_flag_labels(original_values, source_document)
    if not flags:
        return '<p class="sr-note">No review flags are visible from loaded source-derived fields.</p>'
    items = "\n".join(
        f'                            <li><span class="review-chip">{_escape(label)}</span></li>'
        for label in flags
    )
    return f"""                        <p class="sr-note">Review flags</p>
                        <ul class="flag-list" aria-label="Review flags">
{items}
                        </ul>"""


def _review_flag_labels(
    original_values: Mapping[str, Any],
    source_document: Mapping[str, Any],
) -> tuple[str, ...]:
    flags: list[str] = []
    for field_name, label in (
        ("review_delay_over_120_days", "Possible delay indicator: over 120 days"),
        ("review_delay_over_90_days", "Possible delay indicator: over 90 days"),
        ("review_delay_over_60_days", "Possible delay indicator: over 60 days"),
        ("review_delay_over_30_days", "Possible delay indicator: over 30 days"),
    ):
        if original_values.get(field_name) is True:
            flags.append(label)
            break
    for field_name, label in (
        ("missing_first_activity_date", "Needs source check: first activity date missing locally"),
        ("missing_visit_date", "Needs source check: visit date missing locally"),
        ("missing_report_date", "Needs source check: report date missing locally"),
    ):
        if original_values.get(field_name) is True:
            flags.append(label)
    if original_values.get("report_date_used_as_proxy") is True:
        flags.append("Review flag: report date used as proxy")
    if _has_visible_traceability_document(source_document):
        flags.append("Source traceability available")
    return tuple(flags)


def _has_visible_traceability_document(source_document: Mapping[str, Any]) -> bool:
    return any(
        _has_display_value(source_document.get(field_name))
        for field_name in ("source_url", "raw_sha256", "connector_name", "retrieved_at")
    )


def _queue_cue_text(summary: Mapping[str, Any]) -> str:
    status = _reviewer_queue_status(summary)
    note_count = _summary_int(summary, "note_count")
    if status == "not_started" and note_count == 0:
        return "Priority: not started"
    if status == "not_started":
        return "Priority: note present"
    if status == "in_review":
        return "Priority: in review"
    if status == "needs_follow_up":
        return "Priority: needs follow-up"
    if status == "blocked":
        return "Priority: blocked"
    return "Priority: reviewed"


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
    saved_action: str | None,
    saved_value: str | None,
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
    {_render_notice(saved_action, saved_value, source_record_key, related_records, return_context)}
                <div class="detail-shell">
                <section class="hero-card" aria-labelledby="detail-hero-heading">
                    <p class="launch-kicker">Complaint review workspace</p>
                    <h2 id="detail-hero-heading">Complaint overview</h2>
                    <p>{_escape(_detail_summary_sentence(source_record, related_records))}</p>
                    <p><span class="badge badge-muted">Finding: {_escape(_optional_string(original_values, 'finding'))}</span></p>
                    {_render_review_flag_chips(original_values, source_document)}
                </section>
            {_render_detail_decision_continuity(source_record, detail, related_records, return_context)}
            {_render_detail_flag_reason_section(source_record, detail, related_records, return_context)}
                                                                {_render_source_traceability_section(
                                                                                                identity,
                                                                                                source_document,
                                                                                                source_traceability,
                                                                                                import_batch,
                                                                )}
                    <div class="detail-top-grid">
                        <div>
        {_render_record_summary_section(source_record, related_records, detail)}
                {_render_key_date_cards(original_values)}
                        </div>
                        <aside aria-label="Reviewer-created notes and status">
        {_render_reviewer_state_section(detail)}
                        </aside>
                    </div>
        {_render_review_actions(source_record_key, detail, return_context)}
        <section aria-labelledby="source-derived-heading">
                        <h2 id="source-derived-heading">Source-derived full field details</h2>
            <p>These are safe scalar fields from the selected source-derived row. Narrative
            source text is hidden in this local/test browser UI.</p>
            <details>
                <summary>Show source-derived fields</summary>
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
            </details>
    </section>
                <details class="technical-details">
                    <summary>Source-confidence cues</summary>
        {_render_source_confidence_cues_section(source_record, related_records)}
                </details>
                <details class="technical-details">
                    <summary>Field-note and technical context</summary>
        {_render_field_note_guidance_section()}
        {_render_source_context_section(related_records, source_record_key)}
                </details>
        <details class="technical-details">
        <summary>Detail navigation</summary>
        {_render_detail_navigation(source_record_key, related_records, return_context)}
        </details>
    {_render_scope_notice(_mapping(payload, 'workflow_shell'))}
        <details class="technical-details">
        <summary>First-run detail steps</summary>
        {_render_detail_first_run_steps(source_record_key, related_records, return_context)}
        </details>
        <details class="technical-details">
        <summary>Feedback handoff details</summary>
            {_render_detail_feedback_guidance(source_record, related_records, return_context)}
        </details>
                </div>""",
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


def _render_detail_decision_continuity(
    source_record: Mapping[str, Any],
    detail: Mapping[str, Any],
    related_records: list[Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
) -> str:
    identity = _mapping(source_record, "identity")
    original_values = _mapping(source_record, "original_values")
    source_record_key = _string(identity, "source_record_key")
    control_number = _optional_string(original_values, "complaint_control_number")
    finding = _optional_string(original_values, "finding")
    record = _case_brief_record_from_detail(source_record, detail, related_records, return_context)
    reasons = priority_reason_labels(record)
    reason_items = "\n".join(f"              <li>{_escape(reason)}</li>" for reason in reasons)
    check_items = "\n".join(
        f"              <li>{_escape(item)}</li>"
        for item in _detail_check_first_items(original_values)
    )
    ccld_request_href = _ccld_request_href(related_records, return_context)
    next_record_href = _next_priority_record_href(source_record_key, related_records, return_context)
    next_record_text = (
        "Open next recommended record from this same facility/date context"
        if next_record_href != ccld_request_href
        else "Return to the same facility/date queue to choose the next record"
    )
    packet_links = _detail_packet_links(return_context, related_records)
    feedback_href = _feedback_href(
        workflow_area="reviewer-detail",
        page_path=REVIEWER_UI_DETAIL_PATH,
        return_context=return_context,
        source_record_key=source_record_key,
        complaint_control_number=control_number,
        prompt="Describe what was confusing about this reviewer detail step.",
    )
    return f"""<section class="summary-card" aria-labelledby="detail-decision-continuity-heading">
          <p class="launch-kicker">Queue-to-detail continuity</p>
          <h2 id="detail-decision-continuity-heading">Complaint review workspace decision flow</h2>
          <p>This detail page continues the review-priority queue decision flow. Use it to confirm
          why the record was opened, check source-derived values, record a cautious
          reviewer-created status/note when appropriate, and return to the same CCLD request
          context.</p>
          <section aria-labelledby="detail-active-context-heading">
            <h3 id="detail-active-context-heading">Active CCLD request context</h3>
            <dl>
              <dt>Facility/license number</dt>
              <dd>{_escape(_display_value(return_context.facility_number))}</dd>
              <dt>Date range</dt>
              <dd>{_escape(_return_context_date_range(return_context))}</dd>
              <dt>Request origin</dt>
              <dd>{_escape(_request_origin_label(return_context.context_origin))}</dd>
            </dl>
          </section>
                      {_render_detail_facility_context_cues(related_records, return_context)}
          <section aria-labelledby="selected-record-identity-heading">
            <h3 id="selected-record-identity-heading">Selected record identity</h3>
            <dl>
              <dt>Complaint/control identifier</dt>
              <dd>{_escape(control_number)}</dd>
              <dt>Source record key</dt>
              <dd>{_escape(source_record_key)}</dd>
              <dt>Source-derived finding value</dt>
              <dd>{_escape(finding)}</dd>
              <dt>Source-derived date/flag summary</dt>
              <dd>{_escape(_detail_date_flag_summary(original_values))}</dd>
            </dl>
          </section>
          <section aria-labelledby="detail-priority-rationale-heading">
            <h3 id="detail-priority-rationale-heading">Why this record is prioritized from the worklist</h3>
            <p>These are existing source-derived and reviewer-created cues. They are review flags,
            not legal conclusions or source-completeness proof.</p>
            <ul>
{reason_items}
            </ul>
          </section>
          <section aria-labelledby="check-first-heading">
            <h3 id="check-first-heading">What to check first</h3>
            <p>Check these source-derived values before saving a reviewer-created observation.</p>
            <ul>
{check_items}
            </ul>
          </section>
                    <section aria-labelledby="detail-correction-readiness-heading">
                        <h3 id="detail-correction-readiness-heading">Correction-readiness cue</h3>
                        <p>If a source-derived value looks wrong or incomplete, check source traceability first.
                        Use a reviewer-created note to describe the possible correction concern for now, including
                        the field label, the local/test value shown, and what still needs source review.</p>
                        <p>Use feedback if the correction path itself is confusing, if the record appears
                        unexpected for this facility/date request, or if you are unsure whether to use a note
                        or feedback. This local/test workflow does not change source-derived records or submit
                        correction decisions. A future correction workflow would be reviewer-created state, not
                        a source-derived public-source fact.</p>
                    </section>
          <section aria-labelledby="detail-next-steps-heading">
            <h3 id="detail-next-steps-heading">After this detail</h3>
            <p>Save only cautious reviewer-created status/note observations. GET rendering does not
            write reviewer-created state and does not mutate source-derived records.</p>
                        <p>Return links preserve the same facility/date request context. Reviewer-created
                        status filters are chosen on the queue view and do not assign, claim, or persist a
                        record-specific workflow state.</p>
            <div class="form-actions">
              <a class="button" href="{_escape(ccld_request_href)}">Return to same facility/date queue</a>
              <a class="button button-secondary" href="{_escape(next_record_href)}">{_escape(next_record_text)}</a>
                              {_detail_facility_hub_action(return_context)}
                              <a class="button button-secondary" href="{CCLD_FACILITY_REVIEW_PRIORITY_PATH}">Return to facility review priority list</a>
                              <a class="button button-secondary" href="{_escape(_ccld_request_href(related_records, return_context))}">Start complaint request if needed</a>
{packet_links}
              <a class="button button-secondary" href="{_escape(feedback_href)}">Report confusion about this reviewer detail</a>
            </div>
            <p class="helper-text">Packet links are local/test copy/print preparation aids, not a legal report,
            not a final export, not a certified report, and not a source-completeness proof.</p>
          </section>
        </section>"""


def _request_origin_label(value: str | None) -> str:
    if value == "facility_lookup":
        return "Facility lookup result"
    if value == "prefilled_link":
        return "Prefilled facility/license link"
    return "Manual facility/license entry"


def _render_detail_facility_context_cues(
    related_records: list[Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
) -> str:
    facility_number = _detail_facility_number(related_records, return_context)
    context_label, context_guidance, hub_link = _detail_facility_context_status(
        facility_number
    )
    hub_item = (
        f'              <li><a href="{_escape(hub_link)}">Open {context_label}</a></li>'
        if hub_link
        else ""
    )
    return f"""          <section aria-labelledby="detail-facility-context-heading">
            <h3 id="detail-facility-context-heading">Facility context cues</h3>
                        <p>{_escape(context_guidance)} This local/test review cue and source-traceability cue helps choose the next safe navigation step without changing source-derived values.</p>
            <dl>
              <dt>Facility context type</dt>
              <dd>{_escape(context_label)}</dd>
              <dt>Facility/license number</dt>
              <dd>{_escape(_display_value(facility_number))}</dd>
                              <dt>Request context source</dt>
                              <dd>{_escape(_detail_request_context_label(return_context.context_origin))}</dd>
              <dt>Boundary</dt>
              <dd>Complaint records are requested/reviewed separately; this cue is not source verification, not a complaint-coverage determination, not a source-completeness proof, and not a legal finding.</dd>
            </dl>
            <ul>
{hub_item}
              <li><a href="{CCLD_FACILITY_REVIEW_PRIORITY_PATH}">Return to facility review priority list</a></li>
              <li><a href="{_escape(_ccld_request_href(related_records, return_context))}">Start complaint request if needed</a></li>
            </ul>
          </section>"""


def _detail_facility_context_status(
    facility_number: str | None,
) -> tuple[str, str, str | None]:
    if not facility_number:
        return (
            "manual request context",
            "No facility/license number is available for a facility hub cue on this local/test detail page. Use the same queue or start a complaint request when a facility/license number is needed.",
            None,
        )
    if _active_directory_has_facility(facility_number):
        return (
            "facility hub",
            "This record has a directory-backed facility hub cue from the active local/test facility-directory context. Use it to return to facility context before continuing review.",
            _facility_hub_href(facility_number),
        )
    if load_active_facility_review_signals().summary_for_facility(facility_number) is not None:
        return (
            "signal-only facility hub",
            "This record has a signal-only facility hub cue because uploaded public summary signals are available but the active local/test directory row is not available here.",
            _facility_hub_href(facility_number),
        )
    return (
        "manual request context",
        "This record is tied to a manual request context in local/test review. A facility hub cue is not available from the active directory or uploaded summary signals, so return to the same queue or start a complaint request if more context is needed.",
        None,
    )


def _detail_request_context_label(value: str | None) -> str:
    if value == "facility_lookup":
        return "facility lookup context"
    if value == "prefilled_link":
        return "prefilled request context"
    return "manual request context"


def _detail_facility_number(
    related_records: list[Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
) -> str | None:
    if return_context.facility_number:
        return return_context.facility_number
    facility = _facility_context(related_records)
    facility_number = _facility_context_value(facility, "external_facility_number")
    if facility_number == "unknown":
        return None
    return facility_number


def _active_directory_has_facility(facility_number: str) -> bool:
    reference_source = load_active_ccld_facility_reference()
    return any(
        record.facility_number == facility_number
        for record in reference_source.records
    )


def _facility_hub_href(facility_number: str) -> str:
    return f"{CCLD_FACILITY_REVIEW_HUB_PATH}?{urlencode({'facility_number': facility_number})}"


def _detail_facility_hub_action(return_context: CcldQueueReturnContext) -> str:
    if return_context.facility_number is None:
        return ""
    context_label, _context_guidance, hub_link = _detail_facility_context_status(
        return_context.facility_number
    )
    if hub_link is None:
        return ""
    return f'<a class="button button-secondary" href="{_escape(hub_link)}">Return to {context_label}</a>'


def _detail_packet_links(
    return_context: CcldQueueReturnContext,
    related_records: list[Mapping[str, Any]],
) -> str:
    if return_context.facility_number is None:
        return ""
    serious_review_cue_count = _serious_review_cue_record_count(related_records)
    complaint_counts = _complaint_export_status_counts(related_records)
    return f"""              <a class="button button-secondary" href="{_escape(_packet_preview_href(return_context))}">Review packet readiness before copying or printing</a>
              <p class="helper-text">Complaint export records (source-derived): {complaint_counts['all']} all, {complaint_counts['substantiated']} substantiated, {complaint_counts['unsubstantiated']} unsubstantiated</p>
              <p class="helper-text">Serious review cue records: {serious_review_cue_count}</p>
              <p class="helper-text">Serious review cues are deterministic keyword-based review aids and are not verified severity findings.</p>
              <p class="helper-text">Start with the substantiated complaint CSV for the clearest first review set. Use the serious review cue CSV to triage possible priority topics across all complaint statuses.</p>
              <a class="button button-secondary" href="{_escape(_matrix_export_href(return_context))}">Download local/test complaint review matrix CSV</a>
              <a class="button button-secondary" href="{_escape(_substantiated_export_href(return_context))}">Download substantiated complaint CSV</a>
              <a class="button button-secondary" href="{_escape(_unsubstantiated_export_href(return_context))}">Download unsubstantiated complaint CSV</a>
              <a class="button button-secondary" href="{_escape(_all_complaints_export_href(return_context))}">Download all complaint CSV</a>
              <a class="button button-secondary" href="{_escape(_serious_review_cue_export_href(return_context))}">Download serious review cue CSV</a>
              <a class="button button-secondary" href="{_escape(_packet_draft_href(return_context))}">Open local/test preparation draft for browser copy or print</a>"""


def _complaint_export_status_counts(records: list[Mapping[str, Any]]) -> dict[str, int]:
    counts = {
        "all": 0,
        "substantiated": 0,
        "unsubstantiated": 0,
    }
    for record in records:
        if _string(record, "entity_type") != "complaint":
            continue
        counts["all"] += 1
        finding = _mapping(record, "original_values").get("finding")
        finding_norm = _normalized_complaint_finding(finding)
        if finding_norm in {"substantiated", "unsubstantiated"}:
            counts[finding_norm] += 1
    return counts


def _detail_check_first_items(original_values: Mapping[str, Any]) -> tuple[str, ...]:
    items = [
        f"Complaint received date: {_optional_string(original_values, 'complaint_received_date')}",
        f"Visit date: {_optional_string(original_values, 'visit_date')}",
        f"Report date: {_optional_string(original_values, 'report_date')}",
        f"Date signed: {_optional_string(original_values, 'date_signed')}",
        f"Finding value: {_optional_string(original_values, 'finding')}",
    ]
    if original_values.get("missing_first_activity_date") is True:
        items.append("Needs source check: first activity date missing locally.")
    if original_values.get("report_date_used_as_proxy") is True:
        items.append("Review flag: report date used as proxy; use cautious proxy wording only after source traceability review.")
    items.append("Review source traceability before relying on missing, confusing, or proxy-related values.")
    items.append("If a source-derived value looks wrong or incomplete, treat it as a possible correction concern for reviewer-created notes or feedback, not as a changed source record.")
    return tuple(items)


def _detail_date_flag_summary(original_values: Mapping[str, Any]) -> str:
    parts = [_date_summary(original_values)]
    thresholds = _delay_thresholds(original_values)
    if thresholds:
        parts.append(f"possible delay indicator over {max(thresholds)} days")
    if original_values.get("missing_first_activity_date") is True:
        parts.append("needs source check: first activity date missing locally")
    if original_values.get("report_date_used_as_proxy") is True:
        parts.append("review flag: report date used as proxy")
    return "; ".join(parts)


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
    next_record_href = _next_priority_record_href(source_record_key, related_records, return_context)
    packet_links = _detail_navigation_packet_items(return_context)
    feedback_href = _feedback_href(
        workflow_area="reviewer-detail",
        page_path=REVIEWER_UI_DETAIL_PATH,
        return_context=return_context,
        source_record_key=source_record_key,
        prompt="Describe a reviewer detail, return-to-queue, or next-record concern.",
    )
    return f"""<section aria-labelledby="detail-navigation-heading">
      <h2 id="detail-navigation-heading">Detail navigation</h2>
            <ul>
                <li><a href="{_escape(ccld_request_href)}">Return to same facility/date queue</a></li>
                <li><a href="{_escape(next_record_href)}">Open next recommended record from this context</a></li>
{packet_links}
                <li><a href="{CCLD_FACILITY_LOOKUP_PATH}">Find another CCLD facility</a></li>
                <li><a href="{CCLD_HELP_PATH}">Open CCLD workflow help</a></li>
                <li><a href="{REVIEWER_UI_RECORDS_PATH}">Back to reviewer records</a></li>
                <li><a href="/ccld/retrieval/jobs">Job history</a></li>
                <li><a href="{_escape(feedback_href)}">Report reviewer-detail feedback with safe context</a></li>
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


def _detail_navigation_packet_items(return_context: CcldQueueReturnContext) -> str:
    if return_context.facility_number is None:
        return ""
    return f"""                <li><a href="{_escape(_packet_preview_href(return_context))}">Review packet readiness before copying or printing</a></li>
                <li><a href="{_escape(_matrix_export_href(return_context))}">Download local/test complaint review matrix CSV</a></li>
                <li><a href="{_escape(_substantiated_export_href(return_context))}">Download substantiated complaint CSV</a></li>
                <li><a href="{_escape(_unsubstantiated_export_href(return_context))}">Download unsubstantiated complaint CSV</a></li>
                <li><a href="{_escape(_all_complaints_export_href(return_context))}">Download all complaint CSV</a></li>
                <li><a href="{_escape(_packet_draft_href(return_context))}">Open local/test preparation draft for browser copy or print</a></li>"""


def _feedback_href(
    *,
    workflow_area: str,
    page_path: str,
    return_context: CcldQueueReturnContext,
    prompt: str,
    source_record_key: str | None = None,
    complaint_control_number: str | None = None,
) -> str:
    query_values = {
        "feedback_type": "Bug report",
        "workflow_area": workflow_area,
        "page_path": page_path,
        "facility_number": return_context.facility_number or "",
        "start_date": return_context.start_date or "",
        "end_date": return_context.end_date or "",
        "request_context_origin": return_context.context_origin or "manual_entry",
        "source_record_key": source_record_key or "",
        "complaint_control_number": complaint_control_number or "",
        "prompt": prompt,
    }
    return f"{FEEDBACK_PATH}?{urlencode(query_values)}"


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
            <dl class="summary-list">
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
            <h2 id="source-confidence-title">Legal-review flags and source checks</h2>
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
            <p>Next safe action: check source traceability, use cautious reviewer-created
            note/status wording only when it helps the local/test queue, use feedback when
            the cue or wording remains confusing, then return to the same queue for the
            suggested next record.</p>
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
                        investigation activity did or did not happen. Use feedback if the
                        missing-value next step is unclear.</td>
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
                        local/test field identifies a proxy-derived delay basis; use feedback
                        if proxy wording or next action remains confusing.</td>
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
            <h2 id="traceability-title">Source traceability summary</h2>
            <p>This summary names which traceability cues are visible and which are locally
            missing in this local/test detail view so reviewers can decide what to check before
            reviewer-created notes/status, packet preparation, or feedback.</p>
        <p><strong>Traceability values available means</strong> this page has visible local/test
        identifiers or source-document cues that help identify and check the selected
        source-derived record. It does not verify the source record or make a completeness
        claim.</p>
        <p><strong>Missing local/test traceability values means</strong> this local/test display
        does not have that cue. It is not public-source absence, not proof that the source
        lacks a record/event, and not source-completeness proof.</p>
        <p><strong>Check first:</strong> confirm available and missing traceability cues before
        relying on source-derived values in reviewer-created notes/status, packet preview, or
        packet draft. If traceability looks confusing or incomplete, use feedback with the
        selected record identifiers below.</p>
        <p><strong>Next safe actions:</strong> continue review, add cautious reviewer-created
        note/status wording only when it helps the local/test queue, use feedback when
        traceability is confusing, or return to the queue.</p>
        <p><strong>Correction-readiness cue:</strong> if a source-derived value looks wrong or
        incomplete, check source traceability first, then document the possible correction concern
        in a reviewer-created note for now. Use feedback when the correction-readiness path is
        confusing or the record appears unexpected.</p>
      <p>Missing values are shown as <q>not available in this local/test record</q>. A missing
      local/test value is not proof that the public source lacks a record or that any event did
      or did not happen.</p>
      <p>This page is a local/test review aid. It does not make legal, facility-wide,
      completeness, harm, abuse, neglect, liability, or automated complaint-finding
            conclusions. It does not change source-derived records or submit correction decisions.</p>
            <dl class="summary-list">
                <dt>Record-level source traceability status</dt>
                <dd>{_escape(_source_traceability_cue(source_document))}</dd>
                <dt>Traceability values available</dt>
                <dd>{_escape(_available_traceability_values_text(source_document))}</dd>
                <dt>What available means</dt>
                <dd>Visible local/test identifiers or source-document cues can help identify and
                check the selected source-derived record; they are not source verification or a
                source-completeness claim.</dd>
                <dt>Missing local/test traceability values</dt>
                <dd>{_escape(_missing_traceability_values_text(source_document))}</dd>
                <dt>What missing locally means</dt>
                <dd>This local/test detail view does not have that cue; it is not public-source
                absence, not proof that an event did or did not happen, and not source-completeness
                proof.</dd>
                <dt>Source URL</dt>
                <dd>{_escape(_availability_label(source_document.get('source_url')))}</dd>
                <dt>Raw SHA-256</dt>
                <dd>{_escape(_availability_label(source_document.get('raw_sha256')))}</dd>
                <dt>Connector and retrieval time</dt>
                <dd>{_escape(_connector_retrieval_availability(source_document))}</dd>
                <dt>Reviewer-created separation</dt>
                <dd>Source-derived values remain separate from reviewer-created notes/status.</dd>
                <dt>Next safe action</dt>
                <dd>Check traceability first, use cautious reviewer-created note/status wording
                only when it helps, use feedback for confusing traceability, or return to the
                queue.</dd>
            </dl>
            {_render_traceability_summary(source_document, source_traceability, import_batch)}
            <details class="technical-details">
                <summary>Show selected source traceability fields</summary>
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
      </details>
    </section>"""


def _availability_label(value: object) -> str:
    if _has_display_value(value):
        return "available"
    return "missing in this local/test record"


def _connector_retrieval_availability(source_document: Mapping[str, Any]) -> str:
    connector_available = _has_display_value(source_document.get("connector_name"))
    retrieved_available = _has_display_value(source_document.get("retrieved_at"))
    if connector_available and retrieved_available:
        return "connector available; retrieval time available"
    if connector_available:
        return "connector available; retrieval time missing in this local/test record"
    if retrieved_available:
        return "connector missing in this local/test record; retrieval time available"
    return "connector and retrieval time missing in this local/test record"


def _render_field_note_guidance_section() -> str:
    return """<section id="field-note-guidance-heading"
            aria-labelledby="field-note-guidance-title">
            <h2 id="field-note-guidance-title">Field-note guidance</h2>
            <p>Use this guidance after checking source traceability and the source-confidence
            cues. Reviewer notes/status are reviewer-created observations for this local/test
            queue; they do not edit source-derived fields.</p>
            <p>If a source-derived value looks wrong or incomplete, check source traceability first.
            For now, use a reviewer-created note to describe the possible correction concern or use
            feedback if the correction path is confusing. The local/test workflow does not submit
            correction decisions.</p>
            <p>For missing, confusing, or proxy-related source-derived values, the safe next
            action is to name the local/test cue, avoid source absence or verification claims,
            use feedback when the note/status wording is unclear, and continue review from the
            same queue context.</p>
            <p>Keep notes short and cautious. When a value is unclear, describe what the
            local/test page showed and what still needs checking rather than making a source,
            legal, facility-wide, or public-source conclusion.</p>
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
                        <td>Do not say the value is legally verified or a public-source conclusion.</td>
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
                    <tr>
                        <th scope="row">Possible correction concern</th>
                        <td>Say which source-derived value looked wrong or incomplete after checking
                        source traceability, and what should receive correction review later.</td>
                        <td>Do not say this note submitted, decided, or changed correction review or
                        packet output.</td>
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
        facility_number=_optional_form_value(values, "return_facility_number")
        or _optional_form_value(values, "facility_number"),
        start_date=_optional_form_value(values, "return_start_date")
        or _optional_form_value(values, "start_date"),
        end_date=_optional_form_value(values, "return_end_date")
        or _optional_form_value(values, "end_date"),
        context_origin=_optional_form_value(values, "return_context_origin")
        or _optional_form_value(values, "request_context_origin"),
        lookup_facility_name=_optional_form_value(values, "return_lookup_facility_name")
        or _optional_form_value(values, "lookup_facility_name"),
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
            <p>Status filters are reviewer-created queue views selected on the request queue;
            returning here preserves facility/date context, not assignment, record claiming, or
            persisted workflow state.</p>
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
    for label, field_name in (
        ("Complaint received", "complaint_received_date"),
        ("Visit", "visit_date"),
        ("Report", "report_date"),
        ("Date signed", "date_signed"),
    ):
        value = values.get(field_name)
        if _has_display_value(value):
            parts.append(f"{label}: {_display_value(value)}")
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
    detail: Mapping[str, Any],
    return_context: CcldQueueReturnContext,
) -> str:
    summary = _mapping(detail, "associated_reviewer_created_state_summary")
    current_status = _current_reviewer_status_text(summary)
    note_presence = _detail_note_presence_text(summary)
    next_action = _recommended_review_action(summary)
    return f"""<section class="action-card reviewer-action-panel" id="review-actions-heading" aria-labelledby="review-actions-title">
            <p class="launch-kicker">Guided reviewer-created action</p>
            <h2 id="review-actions-title">Record review action</h2>
            <p>Use this panel after reading the complaint overview and review flags. The controls
            below save reviewer-created state through the existing note/status workflow actions;
            Source-derived fields remain unchanged.</p>
            <dl class="summary-list">
                <dt>Current reviewer-created status</dt>
                <dd>{_escape(current_status)}</dd>
                <dt>Reviewer-created note</dt>
                <dd>{_escape(note_presence)}</dd>
                <dt>Recommended next action</dt>
                <dd>{_escape(next_action)}</dd>
            </dl>
            <p>After saving, the confirmation shows what changed, states that it is reviewer-created
            state, confirms source-derived fields remain unchanged, and offers Return to facility
            queue plus Open next priority record guidance.</p>
            <p class="helper-text">Keyboard flow: Tab to the reviewer-created note field or status selector, save one action, then use the confirmation links to return to the same queue or open the next priority record.</p>
            <section aria-labelledby="cautious-action-guidance-heading">
                <h3 id="cautious-action-guidance-heading">Cautious note/status guidance</h3>
                <p>Use note text to record what you checked, not to create legal conclusions.
                Helpful local/test wording can mention a review flag, possible delay indicator,
                missing local/test value, source traceability available, or needs source check cue.
                Check source traceability before relying on this value in a note or status.</p>
                <p>When a source-derived value may need correction review, describe the possible
                correction concern in a reviewer-created note for now. Status values can help the
                queue reflect review progress, but status does not correct, verify, or replace
                source-derived data, and correction decisions are not implemented in this local/test
                workflow.</p>
                <p>Do not write that abuse, neglect, harm, liability, rights deprivation, or source
                completeness has been verified by this page.</p>
            </section>
            {_return_context_hidden_summary(return_context)}
            {_render_note_form(source_record_key, return_context)}
            {_render_status_form(source_record_key, return_context)}
        </section>"""


def _current_reviewer_status_text(summary: Mapping[str, Any]) -> str:
    statuses = tuple(_string_items(summary.get("reviewer_statuses_present", [])))
    if not statuses:
        return "No reviewer-created status"
    return _REVIEWER_STATUS_LABELS.get(statuses[0], statuses[0])


def _detail_note_presence_text(summary: Mapping[str, Any]) -> str:
    payload_kinds = tuple(_string_items(summary.get("payload_kinds_present", [])))
    if "reviewer_note_scaffold" in payload_kinds:
        return "Reviewer note added"
    return "No reviewer note"


def _recommended_review_action(summary: Mapping[str, Any]) -> str:
    has_status = bool(tuple(_string_items(summary.get("reviewer_statuses_present", []))))
    has_note = "reviewer_note_scaffold" in tuple(
        _string_items(summary.get("payload_kinds_present", []))
    )
    if not has_status and not has_note:
        return "Add a review status or note."
    if has_status and not has_note:
        return "Add a note if source-traceability or missing-field context needs explanation."
    if has_note and not has_status:
        return "Set a review status so the queue can reflect progress."
    return "Return to the queue or open the next record."


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
        <h3 id="note-form-heading">Reviewer-created note</h3>
      <form action="{REVIEWER_UI_NOTE_PATH}" method="post">
        <input type="hidden" name="source_record_key" value="{_escape(source_record_key)}">
                {_return_context_hidden_inputs(return_context)}
        <p>
                    <label for="note_text">Reviewer-created note for this record</label>
                    <textarea id="note_text" name="note_text" rows="4" required
                        aria-describedby="note-text-help"></textarea>
                                            <span id="note-text-help">
                                        Use safe plain text. Notes appear below after saving.
                                        They can document a possible correction concern after source
                                        traceability review, but they do not change the source-derived
                                        record or submit a correction decision. Keyboard flow after saving:
                                        use the confirmation links to return to the same queue or open the
                                        next priority record.</span>
        </p>
                                <p><button type="submit">Save reviewer-created note for this record</button></p>
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
            <h3 id="status-form-heading">Reviewer-created status</h3>
      <form action="{REVIEWER_UI_STATUS_PATH}" method="post">
        <input type="hidden" name="source_record_key" value="{_escape(source_record_key)}">
                {_return_context_hidden_inputs(return_context)}
        <p>
          <label for="reviewer_status">Reviewer-created status for this record</label>
                    <select id="reviewer_status" name="reviewer_status" required
                        aria-describedby="reviewer-status-help">
{options}
          </select>
                    <span id="reviewer-status-help">Status is reviewer-created local/test state for
                    queue progress, appears below after saving, and is not a public-source
                    finding. It does not correct or verify source-derived data. Keyboard flow after
                    saving: use the confirmation links to return to the same queue or open the next
                    priority record.</span>
        </p>
                                <p><button type="submit">Save reviewer-created status for this record</button></p>
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
    source_record_key = _string(identity, "source_record_key")
    feedback_href = _feedback_href(
        workflow_area="reviewer-detail",
        page_path=REVIEWER_UI_DETAIL_PATH,
        return_context=return_context,
        source_record_key=source_record_key,
        complaint_control_number=_optional_string(original_values, "complaint_control_number"),
        prompt="Describe source traceability, wording, keyboard flow, or next-step confusion.",
    )
    return f"""<section id="detail-feedback-heading" aria-labelledby="detail-feedback-title">
            <h2 id="detail-feedback-title">Feedback clues for this record</h2>
            <p>If this detail looks wrong or incomplete, return to the CCLD request page and copy
            the tester feedback checklist. Include the record identifiers below and describe what
            looked missing, confusing, or unexpected.</p>
            <p>If source traceability fields are confusing or missing, report the field label and
            the wording shown on this page, such as source URL, raw SHA-256 hash, connector
            metadata, retrieval timestamp, source document/report marker, or local/test
            traceability value missing. Do not treat missing local/test traceability display as
            proof of public-source completeness or absence.</p>
            <p>If a source-derived value appears wrong or incomplete after checking traceability,
            include it as a possible correction concern in a reviewer-created note. Use feedback
            instead when the correction-readiness guidance is confusing, the record appears
            unexpected, or you are unsure whether the issue belongs in a note or feedback.</p>
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
                    <li>Source-confidence next-step confusion: missing local/test values,
                    proxy-related cues, or wording that made it unclear whether to add a
                    cautious reviewer-created note/status or use feedback.</li>
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
                    local/test record, proxy-flag context that affected review, and whether
                    the next safe action was clear.</li>
                    <li>Field-note uncertainty: note wording you were unsure how to phrase after
                    checking source traceability.</li>
                    <li>Possible correction concern: note which source-derived value looked wrong
                    or incomplete, what traceability you checked first, and whether feedback was
                    needed because the future correction workflow path was unclear.</li>
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
                <li><a href="{_escape(feedback_href)}">Open feedback with this record context</a></li>
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
    return f"""<details class="technical-details">
            <summary>Technical runtime details</summary>
            <p>This pilot environment uses an authorized local runtime context for reviewer actions.</p>
            <p>Current review scope: {scope_type} / {scope_id}.</p>
            <p>Reviewer-created notes/status remain separate from source-derived records and audit rows.</p>
            <p>This runtime does not add production sign-in, deployment, exports, reset/reload execution, live crawling, or connector execution.</p>
        </details>"""


def _render_notice(
    saved_action: str | None,
    saved_value: str | None,
    source_record_key: str,
    related_records: list[Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
) -> str:
    if saved_action is None:
        return ""
    detail_href = _reviewer_detail_href(source_record_key, return_context)
    ccld_request_href = _ccld_request_href(related_records, return_context)
    next_record_href = _next_priority_record_href(source_record_key, related_records, return_context)
    next_record_note = (
        "Open next priority record uses another visible complaint record from this facility context."
        if next_record_href != ccld_request_href
        else "No separate next priority record is visible; this opens the facility queue."
    )
    feedback_href = _feedback_href(
        workflow_area="save-confirmation",
        page_path=REVIEWER_UI_DETAIL_PATH,
        return_context=return_context,
        source_record_key=source_record_key,
        prompt="Describe note/status save, return-to-queue, or next-record confusion.",
    )
    return f"""<section class="summary-card" aria-labelledby="form-result-heading">
            <p class="launch-kicker">Reviewer-created state saved</p>
            <h2 id="form-result-heading">Reviewer-created state saved</h2>
            <p>{_escape(_saved_action_sentence(saved_action))}</p>
            <p>This confirmation is reviewer-created local/test state. Source-derived fields remain unchanged, and no correction decision was submitted.</p>
            <section aria-labelledby="saved-changed-heading">
                <h3 id="saved-changed-heading">What changed</h3>
                <ul>
                    {_saved_change_item(saved_action, saved_value)}
                </ul>
            </section>
            <section aria-labelledby="saved-unchanged-heading">
                <h3 id="saved-unchanged-heading">What did not change</h3>
                <ul>
                    <li>Source-derived complaint fields</li>
                    <li>Source traceability</li>
                    <li>Public-source records</li>
                    <li>Correction workflow state</li>
                </ul>
            </section>
            <section aria-labelledby="queue-return-progress-heading">
                <h3 id="queue-return-progress-heading">Next</h3>
                <p>Queue progress and note/status cues are derived from reviewer-created state.
                Return to the same CCLD request context, use the same facility/license number
                and date range, and submit the request again if the local/test queue page needs
                to refresh its displayed cues.</p>
                <p>Status filters are reviewer-created queue views. Showing no rows under a
                status filter is a filtered-empty queue state, not public-source absence,
                assignment state, record claiming, or source-completeness proof.</p>
                <p>After the queue shows the updated cue, open the suggested next record or the
                next not-started record before continuing to the next record.</p>
                <p>The suggested next record is not a persisted assignment, automatic record
                claim, or official workflow state. It is local/test navigation guidance based
                on the same request context and existing reviewer-created note/status cues.</p>
                <p>If the saved confirmation, same-context return link, or refreshed queue cue
                did not behave as expected, include that record-specific observation in the
                existing manual feedback checklist. Also carry forward any source traceability,
                source-confidence, field-note, or possible correction concern wording that was
                confusing for this record.</p>
                <p>Use packet preview or draft only when you are ready for local/test preparation;
                they are not a legal report, not a final export, not a certified report, and not a source-completeness proof.</p>
                <dl>
                    <dt>Same facility/license number</dt>
                    <dd>{_escape(_display_value(return_context.facility_number))}</dd>
                    <dt>Same date range</dt>
                    <dd>{_escape(_return_context_date_range(return_context))}</dd>
                </dl>
            </section>
            <div class="form-actions">
                <a class="button" href="{_escape(ccld_request_href)}">Return to facility queue</a>
                {_packet_preview_confirmation_link(return_context)}
                {_packet_draft_confirmation_link(return_context)}
                <a class="button button-secondary" href="{_escape(next_record_href)}">Open next priority record</a>
                <a class="button button-secondary" href="{_escape(feedback_href)}">Report save or return-to-queue confusion</a>
                <a class="button button-secondary" href="{_escape(detail_href)}">Refresh this reviewer detail</a>
            </div>
            <p class="helper-text">{_escape(next_record_note)}</p>
            <p><a href="#reviewer-state-heading">Review saved notes and statuses below</a></p>
    </section>"""


def _saved_action_sentence(saved_action: str) -> str:
    if saved_action == "note":
        return "Reviewer note saved for this record. The note now appears in reviewer-created state below."
    if saved_action == "status":
        return "Reviewer status saved for this record. The status now appears in reviewer-created state below."
    return "Reviewer-created state saved for this record."


def _saved_change_item(saved_action: str, saved_value: str | None) -> str:
    if saved_action == "note":
        return "<li>Note: added</li>"
    if saved_action == "status":
        value = saved_value or "saved"
        return f"<li>Status: {_escape(value)}</li>"
    return "<li>Reviewer-created state: saved</li>"


def _next_priority_record_href(
    current_source_record_key: str,
    related_records: list[Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
) -> str:
    candidates = [
        record
        for record in related_records
        if _string(record, "entity_type") == "complaint"
        and _string(record, "source_record_key") != current_source_record_key
    ]
    if not candidates:
        return _ccld_request_href(related_records, return_context)
    selected = sorted(candidates, key=_source_record_priority_sort_key)[0]
    return _reviewer_detail_href(_string(selected, "source_record_key"), return_context)


def _source_record_priority_sort_key(record: Mapping[str, Any]) -> tuple[int, int, str]:
    original_values = _mapping(record, "original_values")
    strongest_delay = 0
    for days in (120, 90, 60, 30):
        if original_values.get(f"review_delay_over_{days}_days") is True:
            strongest_delay = days
            break
    missing_rank = 1 if _has_missing_date_flag(original_values) else 0
    date_value = _optional_string(original_values, "complaint_received_date")
    return (-strongest_delay, -missing_rank, date_value)


def _reviewer_detail_href(
    source_record_key: str,
    return_context: CcldQueueReturnContext,
) -> str:
    query_values = {"source_record_key": source_record_key}
    query_values.update(dict(_return_context_form_values(return_context)))
    return f"{REVIEWER_UI_DETAIL_PATH}?{urlencode(query_values)}"


def _page(
    *,
    title: str,
    heading: str,
    main: str,
    actor_label: str | None = None,
    show_workflow_indicator: bool = True,
) -> str:
        return render_page_shell(
                title=title,
                heading=heading,
                main=main,
                skip_label="Skip to main reviewer content",
                nav_label="Reviewer navigation",
                eyebrow="Source-traceable complaint review.",
                actor_label=actor_label,
                extra_nav_links=(),
                active_path=REVIEWER_UI_PREFIX,
                step_id="review_records",
                next_action="Open next record or add reviewer-created notes/status",
                show_workflow_indicator=show_workflow_indicator,
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
