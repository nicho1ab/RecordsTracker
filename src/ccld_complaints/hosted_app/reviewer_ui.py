# ruff: noqa: E501

from __future__ import annotations

import csv
import html
import io
import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qs, urlencode, urlparse
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.pool import StaticPool

from ccld_complaints.hosted_app.auth import (
    CCLD_RETRIEVAL_CORPUS_SCOPE,
    AuthenticatedActor,
    HostedAccessScope,
    HostedAccountDisabledError,
    HostedAccountStatus,
    HostedAuthenticationRequiredError,
    HostedRoleDeniedError,
    HostedScopeDeniedError,
    HostedTesterRole,
    list_authorized_source_derived_records_by_entity_types,
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
    display_record_label,
    prioritized_records,
    priority_reason_labels,
    render_facility_case_brief,
)
from ccld_complaints.hosted_app.facility_review_signals import (
    load_active_facility_review_signals,
)
from ccld_complaints.hosted_app.facility_trends import (
    DATE_UNAVAILABLE,
    FacilityTrendComplaint,
    FacilityTrendFilters,
    FacilityTrendPeriod,
    FacilityTrendResult,
    build_facility_trend,
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
    SourceDerivedEntityType,
    hosted_seeded_import_metadata,
    import_seeded_corpus_artifact,
    load_seeded_corpus_artifact,
)
from ccld_complaints.hosted_app.source_derived_reads import SourceDerivedRecordRead
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
REVIEWER_UI_SUBSTANTIATED_TRIAGE_PATH = f"{REVIEWER_UI_RECORDS_PATH}/substantiated"
REVIEWER_UI_SUBSTANTIATED_EXPORT_PATH = f"{REVIEWER_UI_RECORDS_PATH}/substantiated.csv"
REVIEWER_UI_SERIOUS_TOPICS_PATH = f"{REVIEWER_UI_RECORDS_PATH}/serious-topics"
REVIEWER_UI_FACILITY_PRIORITIES_PATH = f"{REVIEWER_UI_PREFIX}/facilities/priorities"
REVIEWER_UI_FACILITY_TRENDS_PATH = f"{REVIEWER_UI_PREFIX}/facilities/trends"
REVIEWER_UI_NOTE_PATH = f"{REVIEWER_UI_RECORDS_PATH}/note"
REVIEWER_UI_STATUS_PATH = f"{REVIEWER_UI_RECORDS_PATH}/status"
REVIEWER_UI_PACKET_PREVIEW_PATH = f"{REVIEWER_UI_PREFIX}/packet/preview"
REVIEWER_UI_PACKET_DRAFT_PATH = f"{REVIEWER_UI_PREFIX}/packet/draft"
CCLD_HELP_PATH = "/ccld/help"
FEEDBACK_PATH = "/feedback"
CENTRAL_TIME = ZoneInfo("America/Chicago")
LOCAL_REVIEWER_UI_SCOPE = HostedAccessScope(
    "seeded_corpus",
    "seeded-ccld-fixture-2026-06-13",
)
POSTGRES_REVIEWER_UI_SCOPE = CCLD_RETRIEVAL_CORPUS_SCOPE
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
_SERIOUS_TOPIC_CATEGORY_LABELS: Mapping[str, str] = {
    "Abuse or mistreatment": "Mistreatment-topic",
    "Neglect": "Care-omission topic",
    "Inadequate supervision": "Supervision topic",
    "Medication or medical care": "Medication/medical-care topic",
    "Runaway or AWOL": "Runaway/AWOL topic",
    "Staff conduct": "Staff-conduct topic",
}
_SERIOUS_TOPIC_CATEGORY_BY_NORMALIZED = {
    key.casefold(): value for key, value in _SERIOUS_TOPIC_CATEGORY_LABELS.items()
}
_SERIOUS_TOPIC_CUE_TERMS: tuple[str, ...] = (
    "sexual assault",
    "abuse",
    "mistreatment",
    "neglect",
    "supervision",
    "unsupervised",
    "unattended",
    "medication",
    "medical care",
    "runaway",
    "awol",
    "staff misconduct",
    "injury",
    "restraint",
)
_SERIOUS_TOPIC_CUE_EXCLUDED_PHRASES: tuple[str, ...] = (
    "substance abuse",
    "abuse prevention",
    "injury prevention",
    "restraint policy",
    "restraint training",
)
_SUBSTANTIATED_EQUIVALENT_KEYWORDS: tuple[str, ...] = (
    "substantiated",
    "founded",
    "sustained",
)
_SAFE_ORIGINAL_VALUE_DENYLIST = (
    "allegation_text",
    "event_text",
    "source_text",
)
_NARRATIVE_FIELD_NAMES = (
    "source_narrative",
    "report_narrative",
    "narrative",
    "source_text",
    "allegation_text",
    "event_text",
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
        "notice",
    ),
}
_SOURCE_CONFIDENCE_COMPLAINT_FIELDS = (
    (
        "Complaint control number",
        "complaint_control_number",
        "Use this as the complaint identifier only after checking the source document context; Send feedback if the identifier or next step is confusing.",
    ),
    (
        "Complaint received date",
        "complaint_received_date",
        "Check the source link before relying on this date in notes/status; if unclear, describe the cue cautiously or send feedback.",
    ),
    (
        "Visit date",
        "visit_date",
        "If this is missing, describe it as not available locally, not as proof no visit occurred; Send feedback if the next step is unclear.",
    ),
    (
        "Report date",
        "report_date",
        "Check whether the report date is acting as a proxy before using delay wording; use cautious reviewer-created wording only after that check.",
    ),
    (
        "Date signed",
        "date_signed",
        "Use this as a source-derived display value; check source context before relying on it or send feedback if it is confusing.",
    ),
    (
        "Finding",
        "finding",
        "Treat this as a source-derived value, not as a new reviewer finding; Send feedback if the safe wording is unclear.",
    ),
    (
        "Loaded extraction marker",
        "extraction_confidence",
        "Treat this as extraction metadata, not reviewer verification.",
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
_SOURCE_DERIVED_PAGE_LIMIT = 100
_SUBSTANTIATED_DEFAULT_PAGE_SIZE = 50
_SUBSTANTIATED_MAX_PAGE_SIZE = 100
_FACILITY_PRIORITIES_DEFAULT_PAGE_SIZE = 25
_FACILITY_PRIORITIES_MAX_PAGE_SIZE = 100
_FACILITY_TRENDS_DEFAULT_PERIOD_COUNT = 12
_FACILITY_TRENDS_MAX_PERIOD_COUNT = 24
_SUBSTANTIATED_SOURCE_ENTITY_TYPES: tuple[SourceDerivedEntityType, ...] = (
    "facility",
    "source_document",
    "complaint",
    "allegation",
    "event",
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


@dataclass(frozen=True)
class SubstantiatedWorklistFilters:
    start_date: str | None = None
    end_date: str | None = None
    facility: str = ""
    facility_type: str = ""
    geography: str = ""
    finding: str = ""
    sort: str = "complaint_date_desc"
    page: int = 1
    page_size: int = _SUBSTANTIATED_DEFAULT_PAGE_SIZE


@dataclass(frozen=True)
class SeriousTopicsFilters:
    start_date: str | None = None
    end_date: str | None = None
    facility: str = ""
    facility_type: str = ""
    geography: str = ""
    finding: str = ""
    topic: str = ""
    match_basis: str = "all"
    sort: str = "complaint_date_desc"
    page: int = 1
    page_size: int = _SUBSTANTIATED_DEFAULT_PAGE_SIZE


@dataclass(frozen=True)
class SubstantiatedFindingEvidence:
    label: str
    value: str


@dataclass(frozen=True)
class FacilityPrioritiesFilters:
    start_date: str | None = None
    end_date: str | None = None
    facility_type: str = ""
    geography: str = ""
    min_complaints: int = 1
    min_substantiated: int = 0
    indicator: str = "all"
    page: int = 1
    page_size: int = _FACILITY_PRIORITIES_DEFAULT_PAGE_SIZE


@dataclass(frozen=True)
class FacilityPriorityComplaint:
    source_record_key: str
    stable_complaint_id: str
    complaint_control_number: str
    activity_date: str
    finding: str
    detail_href: str
    source_url_href: str


@dataclass(frozen=True)
class FacilityPrioritySummary:
    facility_identity: str
    facility_number: str
    facility_name: str
    facility_type: str
    geography: str
    complaint_count: int
    substantiated_count: int
    recent_activity_date: str
    strongest_delay_days: int
    delay_flag_count: int
    missing_date_count: int
    source_available_count: int
    source_missing_count: int
    low_data: bool
    indicators: tuple[str, ...]
    factors: tuple[str, ...]
    complaints: tuple[FacilityPriorityComplaint, ...]


@dataclass(frozen=True)
class FacilityTypeClassification:
    value: str
    is_source_provided: bool

    @property
    def display_value(self) -> str:
        if self.is_source_provided:
            return self.value
        return f"{self.value} (derived from facility name)"


@dataclass(frozen=True)
class SourceRecordIndexes:
    by_import_batch_id: Mapping[str, tuple[Mapping[str, Any], ...]]
    by_facility_id: Mapping[str, tuple[Mapping[str, Any], ...]]
    by_source_document_id: Mapping[str, tuple[Mapping[str, Any], ...]]
    by_complaint_id: Mapping[str, tuple[Mapping[str, Any], ...]]
    by_stable_source_id: Mapping[str, tuple[Mapping[str, Any], ...]]
    by_source_record_key: Mapping[str, Mapping[str, Any]]


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
                message="Reviewer UI context is not configured.",
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
                    "This reviewer page supports browser GET pages "
                    "and form POST actions only."
                ),
            ),
        )
    if parsed_url.path in {REVIEWER_UI_PREFIX, REVIEWER_UI_RECORDS_PATH}:
        return _record_list_response(parsed_url.query, context)
    if parsed_url.path == REVIEWER_UI_FACILITY_PRIORITIES_PATH:
        return _facility_priorities_response(parsed_url.query, context)
    if parsed_url.path == REVIEWER_UI_FACILITY_TRENDS_PATH:
        return _facility_trends_response(parsed_url.query, context)
    if parsed_url.path == REVIEWER_UI_SUBSTANTIATED_TRIAGE_PATH:
        return _substantiated_triage_response(parsed_url.query, context)
    if parsed_url.path == REVIEWER_UI_SERIOUS_TOPICS_PATH:
        return _serious_topics_response(parsed_url.query, context)
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
            message="The requested reviewer UI page was not found.",
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
    export_context = _reviewer_queue_export_context(filtered_records)
    export_records = _all_source_derived_records(context)
    return _html_response(
        status,
        _render_record_list(
            payload,
            filtered_records,
            search_query,
            state_summaries,
            export_context,
            export_records,
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


def _facility_priorities_response(
    query: str,
    context: ReviewerUiContext,
) -> tuple[int, str, bytes]:
    query_values = parse_qs(query, keep_blank_values=True)
    filters = _facility_priorities_filters(query_values)
    source_status, source_result = _substantiated_source_records_response(context)
    if source_status != 200:
        if not isinstance(source_result, bytes):
            raise ValueError("Expected source-derived error body to be bytes.")
        return _workflow_error_page(
            source_status,
            source_result,
            title="Facility priorities blocked",
            heading="Facility priorities blocked",
            guidance=(
                "Retry with an authenticated actor that can read the loaded "
                "source-derived corpus."
            ),
            links=(("Return to reviewer records", REVIEWER_UI_RECORDS_PATH),),
        )
    if isinstance(source_result, bytes):
        raise ValueError("Expected source-derived records.")
    all_summaries = _facility_priority_summaries(source_result)
    filtered_summaries = _filter_facility_priority_summaries(all_summaries, filters)
    sorted_summaries = _sort_facility_priority_summaries(filtered_summaries)
    paged_summaries, pagination = _paginate_facility_priority_summaries(
        sorted_summaries,
        filters,
    )
    return _html_response(
        200,
        _render_facility_priorities(
            paged_summaries,
            filters=filters,
            result_count=len(filtered_summaries),
            total_facility_count=len(all_summaries),
            all_summaries=all_summaries,
            pagination=pagination,
            actor_label=_signed_in_actor_label(context),
        ),
    )


def _facility_priorities_filters(
    query_values: Mapping[str, list[str]],
) -> FacilityPrioritiesFilters:
    return FacilityPrioritiesFilters(
        start_date=_validated_iso_date_or_none(_first_form_value(query_values, "start_date")),
        end_date=_validated_iso_date_or_none(_first_form_value(query_values, "end_date")),
        facility_type=_first_form_value(query_values, "facility_type"),
        geography=_first_form_value(query_values, "geography"),
        min_complaints=_bounded_query_int(
            query_values,
            "min_complaints",
            default=1,
            minimum=0,
            maximum=9999,
        ),
        min_substantiated=_bounded_query_int(
            query_values,
            "min_substantiated",
            default=0,
            minimum=0,
            maximum=9999,
        ),
        indicator=_facility_priority_indicator_value(
            _first_form_value(query_values, "indicator")
        ),
        page=_bounded_query_int(query_values, "page", default=1, minimum=1, maximum=9999),
        page_size=_bounded_query_int(
            query_values,
            "page_size",
            default=_FACILITY_PRIORITIES_DEFAULT_PAGE_SIZE,
            minimum=1,
            maximum=_FACILITY_PRIORITIES_MAX_PAGE_SIZE,
        ),
    )


def _facility_priority_indicator_value(value: str) -> str:
    normalized = value.strip().casefold()
    if normalized in {
        "all",
        "substantiated",
        "delay",
        "missing_dates",
        "source_available",
        "source_link_missing",
        "recent_activity",
        "low_data",
    }:
        return normalized
    return "all"


def _bounded_query_int(
    query_values: Mapping[str, list[str]],
    key: str,
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    raw_value = _first_form_value(query_values, key)
    if not raw_value:
        return default
    try:
        value = int(raw_value)
    except ValueError:
        return default
    if value < minimum:
        return minimum
    if value > maximum:
        return maximum
    return value


def _facility_priority_summaries(
    source_records: list[Mapping[str, Any]],
) -> list[FacilityPrioritySummary]:
    source_indexes = _source_record_indexes(source_records)
    grouped: dict[str, list[tuple[Mapping[str, Any], list[Mapping[str, Any]]]]] = {}
    seen_complaint_ids: set[str] = set()
    for record in source_records:
        if _string(record, "entity_type") != "complaint":
            continue
        stable_complaint_id = _string(record, "stable_source_id")
        if stable_complaint_id in seen_complaint_ids:
            continue
        seen_complaint_ids.add(stable_complaint_id)
        review_item = _review_item_from_source_record(record)
        source_record = _mapping(review_item, "source_record")
        related_records = _related_source_records_from_indexes(
            source_record,
            source_indexes,
        )
        facility_identity = _facility_priority_identity(source_record, related_records)
        grouped.setdefault(facility_identity, []).append((source_record, related_records))
    summaries = [
        _facility_priority_summary(facility_identity, grouped_records)
        for facility_identity, grouped_records in grouped.items()
    ]
    return _sort_facility_priority_summaries(summaries)


def _facility_priority_summary(
    facility_identity: str,
    grouped_records: list[tuple[Mapping[str, Any], list[Mapping[str, Any]]]],
) -> FacilityPrioritySummary:
    representative_source_record, representative_related = grouped_records[0]
    facility = _facility_context(representative_related)
    facility_number = _facility_priority_facility_number(
        representative_source_record,
        facility,
    )
    facility_name = _facility_context_value(facility, "facility_name")
    if facility_name == "unknown":
        facility_name = f"Facility ID {facility_number}" if facility_number != "unknown" else "Unknown facility"
    facility_type = _facility_context_value(facility, "facility_type")
    geography = _substantiated_geography_label(facility)
    complaints = tuple(
        _facility_priority_complaint(source_record, related_records)
        for source_record, related_records in grouped_records
    )
    sorted_complaints = tuple(sorted(complaints, key=_facility_priority_complaint_sort_key))
    complaint_count = len(sorted_complaints)
    substantiated_count = sum(
        1
        for source_record, related_records in grouped_records
        if _substantiated_finding_evidence(source_record, related_records) is not None
    )
    strongest_delay_days = max(
        (_source_priority_strongest_delay(_mapping(source_record, "original_values")) for source_record, _related in grouped_records),
        default=0,
    )
    delay_flag_count = sum(
        1
        for source_record, _related in grouped_records
        if _source_priority_strongest_delay(_mapping(source_record, "original_values")) > 0
    )
    missing_date_count = sum(
        1
        for source_record, _related in grouped_records
        if _facility_priority_missing_dates(_mapping(source_record, "original_values"))
    )
    source_available_count = sum(
        1
        for source_record, _related in grouped_records
        if _has_display_value(_mapping(source_record, "source_document").get("source_url"))
    )
    source_missing_count = complaint_count - source_available_count
    recent_activity_date = max(
        (complaint.activity_date for complaint in sorted_complaints if complaint.activity_date != "unknown"),
        default="",
    )
    low_data = complaint_count == 1
    indicators = _facility_priority_indicators(
        substantiated_count=substantiated_count,
        delay_flag_count=delay_flag_count,
        missing_date_count=missing_date_count,
        source_available_count=source_available_count,
        source_missing_count=source_missing_count,
        recent_activity_date=recent_activity_date,
        low_data=low_data,
    )
    factors = _facility_priority_factors(
        complaint_count=complaint_count,
        substantiated_count=substantiated_count,
        strongest_delay_days=strongest_delay_days,
        delay_flag_count=delay_flag_count,
        missing_date_count=missing_date_count,
        source_available_count=source_available_count,
        source_missing_count=source_missing_count,
        recent_activity_date=recent_activity_date,
        low_data=low_data,
    )
    return FacilityPrioritySummary(
        facility_identity=facility_identity,
        facility_number=facility_number,
        facility_name=facility_name,
        facility_type=facility_type,
        geography=geography,
        complaint_count=complaint_count,
        substantiated_count=substantiated_count,
        recent_activity_date=recent_activity_date,
        strongest_delay_days=strongest_delay_days,
        delay_flag_count=delay_flag_count,
        missing_date_count=missing_date_count,
        source_available_count=source_available_count,
        source_missing_count=source_missing_count,
        low_data=low_data,
        indicators=indicators,
        factors=factors,
        complaints=sorted_complaints,
    )


def _facility_priority_identity(
    source_record: Mapping[str, Any],
    related_records: list[Mapping[str, Any]],
) -> str:
    facility = _facility_context(related_records)
    if facility is not None:
        for key in ("facility_id", "external_facility_number", "facility_number"):
            value = facility.get(key)
            if _has_display_value(value):
                return _display_value(value)
    identity = _mapping(source_record, "identity")
    facility_id = _optional_string(identity, "facility_id")
    if facility_id != "unknown":
        return facility_id
    original_values = _mapping(source_record, "original_values")
    for key in ("facility_id", "external_facility_number", "facility_number"):
        value = original_values.get(key)
        if _has_display_value(value):
            return _display_value(value)
    return f"unknown:{_string(identity, 'source_record_key')}"


def _facility_priority_facility_number(
    source_record: Mapping[str, Any],
    facility: Mapping[str, Any] | None,
) -> str:
    for value in (
        _facility_context_value(facility, "external_facility_number"),
        _facility_context_value(facility, "facility_number"),
        _complaint_export_row_facility_number(source_record, CcldQueueReturnContext()),
    ):
        if value != "unknown":
            return value.rsplit(":", 1)[-1] if value.startswith("ccld:facility:") else value
    return "unknown"


def _facility_priority_complaint(
    source_record: Mapping[str, Any],
    related_records: list[Mapping[str, Any]],
) -> FacilityPriorityComplaint:
    identity = _mapping(source_record, "identity")
    original_values = _mapping(source_record, "original_values")
    source_document = _mapping(source_record, "source_document")
    source_record_key = _string(identity, "source_record_key")
    activity_date = _facility_priority_activity_date(original_values)
    source_url = _optional_string(source_document, "source_url")
    return FacilityPriorityComplaint(
        source_record_key=source_record_key,
        stable_complaint_id=_optional_string(identity, "stable_source_id"),
        complaint_control_number=_optional_string(original_values, "complaint_control_number"),
        activity_date=activity_date,
        finding=_optional_string(original_values, "finding"),
        detail_href=_reviewer_detail_href(source_record_key, CcldQueueReturnContext()),
        source_url_href=source_url if _has_display_value(source_url) and source_url != "unknown" else "",
    )


def _facility_priority_activity_date(original_values: Mapping[str, Any]) -> str:
    dates = [
        _optional_string(original_values, field_name)
        for field_name in (
            "complaint_received_date",
            "visit_date",
            "report_date",
            "date_signed",
        )
    ]
    valid_dates = [value for value in dates if _looks_like_iso_date(value)]
    return max(valid_dates) if valid_dates else "unknown"


def _looks_like_iso_date(value: str) -> bool:
    return len(value) == 10 and value[4] == "-" and value[7] == "-"


def _facility_priority_complaint_sort_key(
    complaint: FacilityPriorityComplaint,
) -> tuple[bool, str, str]:
    return (
        complaint.activity_date == "unknown",
        _reverse_iso_date_key(complaint.activity_date),
        complaint.source_record_key,
    )


def _source_priority_strongest_delay(values: Mapping[str, Any]) -> int:
    for days in (120, 90, 60, 30):
        if values.get(f"review_delay_over_{days}_days") is True:
            return days
    return 0


def _facility_priority_missing_dates(values: Mapping[str, Any]) -> bool:
    return (
        values.get("missing_first_activity_date") is True
        or not _has_display_value(values.get("visit_date"))
        or not _has_display_value(values.get("report_date"))
        or not _has_display_value(values.get("date_signed"))
    )


def _facility_priority_indicators(
    *,
    substantiated_count: int,
    delay_flag_count: int,
    missing_date_count: int,
    source_available_count: int,
    source_missing_count: int,
    recent_activity_date: str,
    low_data: bool,
) -> tuple[str, ...]:
    indicators: list[str] = []
    if substantiated_count:
        indicators.append("substantiated")
    if delay_flag_count:
        indicators.append("delay")
    if missing_date_count:
        indicators.append("missing_dates")
    if source_available_count:
        indicators.append("source_available")
    if source_missing_count:
        indicators.append("source_link_missing")
    if recent_activity_date:
        indicators.append("recent_activity")
    if low_data:
        indicators.append("low_data")
    return tuple(indicators)


def _facility_priority_factors(
    *,
    complaint_count: int,
    substantiated_count: int,
    strongest_delay_days: int,
    delay_flag_count: int,
    missing_date_count: int,
    source_available_count: int,
    source_missing_count: int,
    recent_activity_date: str,
    low_data: bool,
) -> tuple[str, ...]:
    factors = [f"{complaint_count} deduplicated loaded complaint record(s)."]
    if substantiated_count:
        factors.append(f"{substantiated_count} source-derived substantiated/equivalent finding(s).")
    if delay_flag_count:
        factors.append(
            f"{delay_flag_count} complaint record(s) with timing review flags; strongest available flag is {strongest_delay_days}+ days."
        )
    if missing_date_count:
        factors.append(f"{missing_date_count} complaint record(s) with missing local date context.")
    if recent_activity_date:
        factors.append(f"Most recent supported loaded activity: {_detail_display_date(recent_activity_date)}.")
    if source_available_count:
        factors.append(f"{source_available_count} complaint record(s) with an original public report link.")
    if source_missing_count:
        factors.append(f"{source_missing_count} complaint record(s) missing an original public report link.")
    if low_data:
        factors.append("Low-data facility: one loaded complaint record, so review cues are limited.")
    return tuple(factors)


def _filter_facility_priority_summaries(
    summaries: list[FacilityPrioritySummary],
    filters: FacilityPrioritiesFilters,
) -> list[FacilityPrioritySummary]:
    return [
        summary
        for summary in summaries
        if _facility_priority_matches_filters(summary, filters)
    ]


def _facility_priority_matches_filters(
    summary: FacilityPrioritySummary,
    filters: FacilityPrioritiesFilters,
) -> bool:
    if not _facility_priority_text_matches(summary.facility_type, filters.facility_type):
        return False
    if not _facility_priority_text_matches(summary.geography, filters.geography):
        return False
    if summary.complaint_count < filters.min_complaints:
        return False
    if summary.substantiated_count < filters.min_substantiated:
        return False
    if filters.indicator != "all" and filters.indicator not in summary.indicators:
        return False
    if filters.start_date is None and filters.end_date is None:
        return True
    return any(
        complaint.activity_date != "unknown"
        and (filters.start_date is None or complaint.activity_date >= filters.start_date)
        and (filters.end_date is None or complaint.activity_date <= filters.end_date)
        for complaint in summary.complaints
    )


def _facility_priority_text_matches(value: str, filter_value: str) -> bool:
    normalized_filter = " ".join(filter_value.casefold().split())
    if not normalized_filter:
        return True
    normalized_value = " ".join(value.casefold().split())
    return normalized_filter in normalized_value


def _sort_facility_priority_summaries(
    summaries: list[FacilityPrioritySummary],
) -> list[FacilityPrioritySummary]:
    return sorted(summaries, key=_facility_priority_sort_key)


def _facility_priority_sort_key(
    summary: FacilityPrioritySummary,
) -> tuple[int, int, int, str, str, str]:
    return (
        -summary.substantiated_count,
        -summary.complaint_count,
        -summary.strongest_delay_days,
        _reverse_iso_date_key(summary.recent_activity_date or "unknown"),
        summary.facility_name.casefold(),
        summary.facility_identity.casefold(),
    )


def _paginate_facility_priority_summaries(
    summaries: list[FacilityPrioritySummary],
    filters: FacilityPrioritiesFilters,
) -> tuple[list[FacilityPrioritySummary], Mapping[str, int]]:
    total_pages = max((len(summaries) + filters.page_size - 1) // filters.page_size, 1)
    page = min(filters.page, total_pages)
    start = (page - 1) * filters.page_size
    end = start + filters.page_size
    return summaries[start:end], {
        "page": page,
        "page_size": filters.page_size,
        "total_pages": total_pages,
        "offset": start,
    }


def _render_facility_priorities(
    summaries: list[FacilityPrioritySummary],
    *,
    filters: FacilityPrioritiesFilters,
    result_count: int,
    total_facility_count: int,
    all_summaries: list[FacilityPrioritySummary],
    pagination: Mapping[str, int],
    actor_label: str | None,
) -> str:
    filter_markup = _render_facility_priorities_filter_form(filters, all_summaries)
    summary = _render_facility_priorities_count_summary(
        result_count,
        total_facility_count,
        pagination,
    )
    if not summaries:
        list_markup = f"""        <section class="hero-card" aria-labelledby="facility-priorities-empty-heading">
          <h2 id="facility-priorities-empty-heading">No facility priority rows matched.</h2>
          {summary}
          <p>Adjust the filters or clear them to return to all authorized loaded facilities with deduplicated complaint records.</p>
        </section>"""
    else:
        rows = "\n".join(_render_facility_priority_row(summary) for summary in summaries)
        list_markup = f"""        <section aria-labelledby="facility-priorities-results-heading">
          <h2 id="facility-priorities-results-heading">Facility review priority worklist</h2>
          {summary}
          <table>
            <caption>Explainable facility review prioritization over authorized loaded complaint records</caption>
            <thead>
              <tr>
                <th scope="col">Facility</th>
                <th scope="col">Facility type</th>
                <th scope="col">Geography</th>
                <th scope="col">Complaint count</th>
                <th scope="col">Substantiated count</th>
                <th scope="col">Recent activity</th>
                <th scope="col">Contributing factors</th>
                <th scope="col">Continue review</th>
              </tr>
            </thead>
            <tbody>
{rows}
            </tbody>
          </table>
          {_render_facility_priorities_pagination(filters, pagination, result_count)}
        </section>"""
    return _page(
        title="Facility review priorities",
        heading="Facility review priorities",
        actor_label=actor_label,
        main=f"""
        <section class="quiet-section" aria-labelledby="facility-priorities-decision-heading">
          <h2 id="facility-priorities-decision-heading">Find facilities that may deserve review first</h2>
          <p>This reviewer worklist aggregates authorized loaded complaint records by stable source-derived facility identity and shows the source-derived factors that surfaced each facility. It does not use a hidden score, machine learning, or unsupported legal conclusions.</p>
          <p>Counts are based on deduplicated complaint identities in the loaded corpus available to this reviewer. Missing values are shown as unknown, and missing source links are identified rather than silently omitted.</p>
        </section>
{filter_markup}
{list_markup}
        {_render_facility_priority_rules_disclosure()}
        <section class="quiet-section" aria-labelledby="facility-priorities-next-heading">
          <h2 id="facility-priorities-next-heading">Next steps</h2>
          <ul>
            <li><a href="{REVIEWER_UI_FACILITY_TRENDS_PATH}">Compare complaint trends over time</a></li>
            <li><a href="{REVIEWER_UI_SUBSTANTIATED_TRIAGE_PATH}">Open substantiated complaint worklist</a></li>
            <li><a href="{REVIEWER_UI_RECORDS_PATH}">Return to review queue</a></li>
            <li><a href="{CCLD_RECORD_REQUEST_PATH}">Return to CCLD request queue</a></li>
          </ul>
        </section>
""",
    )


def _render_facility_priorities_filter_form(
    filters: FacilityPrioritiesFilters,
    all_summaries: list[FacilityPrioritySummary],
) -> str:
    facility_type_options = _substantiated_filter_options(
        summary.facility_type for summary in all_summaries
    )
    geography_options = _substantiated_filter_options(
        summary.geography for summary in all_summaries
    )
    return f"""        <section class="quiet-section" aria-labelledby="facility-priorities-filters-heading">
          <h2 id="facility-priorities-filters-heading">Filter</h2>
          <form class="compact-filter-form" method="get" action="{REVIEWER_UI_FACILITY_PRIORITIES_PATH}">
            <div class="facility-intelligence-filter-grid">
              <p>
                <label for="facility-priorities-start-date">From activity date</label>
                <input id="facility-priorities-start-date" name="start_date" type="date" value="{_escape(filters.start_date or '')}">
              </p>
              <p>
                <label for="facility-priorities-end-date">To activity date</label>
                <input id="facility-priorities-end-date" name="end_date" type="date" value="{_escape(filters.end_date or '')}">
              </p>
              <p>
                <label for="facility-priorities-facility-type">Facility type</label>
                <input id="facility-priorities-facility-type" name="facility_type" value="{_escape(filters.facility_type)}" list="facility-priorities-facility-types">
                <datalist id="facility-priorities-facility-types">{facility_type_options}</datalist>
              </p>
              <p>
                <label for="facility-priorities-geography">Geography</label>
                <input id="facility-priorities-geography" name="geography" value="{_escape(filters.geography)}" list="facility-priorities-geographies">
                <datalist id="facility-priorities-geographies">{geography_options}</datalist>
              </p>
              <p>
                <label for="facility-priorities-min-complaints">Minimum complaint count</label>
                <input id="facility-priorities-min-complaints" name="min_complaints" type="number" min="0" max="9999" value="{filters.min_complaints}">
              </p>
              <p>
                <label for="facility-priorities-min-substantiated">Minimum substantiated count</label>
                <input id="facility-priorities-min-substantiated" name="min_substantiated" type="number" min="0" max="9999" value="{filters.min_substantiated}">
              </p>
              <p>
                <label for="facility-priorities-indicator">Supported indicator</label>
                <select id="facility-priorities-indicator" name="indicator">
                  {_facility_priority_indicator_option(filters.indicator, "all", "All supported indicators")}
                  {_facility_priority_indicator_option(filters.indicator, "substantiated", "Substantiated/equivalent findings")}
                  {_facility_priority_indicator_option(filters.indicator, "delay", "Timing review flags")}
                  {_facility_priority_indicator_option(filters.indicator, "missing_dates", "Missing date context")}
                  {_facility_priority_indicator_option(filters.indicator, "source_available", "Original report link available")}
                  {_facility_priority_indicator_option(filters.indicator, "source_link_missing", "Original report link missing")}
                  {_facility_priority_indicator_option(filters.indicator, "recent_activity", "Supported recent activity")}
                  {_facility_priority_indicator_option(filters.indicator, "low_data", "Low-data facilities")}
                </select>
              </p>
              <p>
                <label for="facility-priorities-page-size">Rows per page</label>
                <select id="facility-priorities-page-size" name="page_size">
                  {_substantiated_page_size_option(filters.page_size, 10)}
                  {_substantiated_page_size_option(filters.page_size, 25)}
                  {_substantiated_page_size_option(filters.page_size, 50)}
                  {_substantiated_page_size_option(filters.page_size, 100)}
                </select>
              </p>
            </div>
            <div class="form-actions">
              <button class="button" type="submit">Apply filters</button>
              <a class="button button-secondary" href="{REVIEWER_UI_FACILITY_PRIORITIES_PATH}">Clear filters</a>
            </div>
          </form>
        </section>"""


def _facility_priority_indicator_option(current: str, value: str, label: str) -> str:
    selected = ' selected="selected"' if current == value else ""
    return f'<option value="{_escape(value)}"{selected}>{_escape(label)}</option>'


def _render_facility_priorities_count_summary(
    result_count: int,
    total_facility_count: int,
    pagination: Mapping[str, int],
) -> str:
    page = pagination["page"]
    page_size = pagination["page_size"]
    offset = pagination["offset"]
    if result_count == 0:
        shown_range = "Showing 0"
    else:
        first = offset + 1
        last = min(offset + page_size, result_count)
        shown_range = f"Showing {first}-{last}"
    return (
        f"<p>{shown_range} of {result_count} matching facility priority row(s); "
        f"{total_facility_count} total authorized loaded facility row(s) with "
        "deduplicated complaint records.</p>"
        f"<p class=\"helper-text\">Page {page} of {pagination['total_pages']}.</p>"
    )


def _render_facility_priority_row(summary: FacilityPrioritySummary) -> str:
    factors = "\n".join(f"              <li>{_escape(factor)}</li>" for factor in summary.factors)
    complaint_queue_href = _facility_priority_queue_href(summary)
    next_complaint = summary.complaints[0] if summary.complaints else None
    next_review_link = ""
    source_link = "Original public report link not available for the first qualifying complaint."
    if next_complaint is not None:
        next_review_link = f'<a class="button" href="{_escape(next_complaint.detail_href)}">Open next complaint review workspace</a>'
        if next_complaint.source_url_href:
            suffix = (
                f" for {next_complaint.complaint_control_number}"
                if next_complaint.complaint_control_number != "unknown"
                else ""
            )
            source_link = f'<a href="{_escape(next_complaint.source_url_href)}">Open original public report{_escape(suffix)}</a>'
    return f"""        <tr>
          <th scope="row">{_escape(summary.facility_name)}<br><span class="helper-text">Facility ID: {_escape(summary.facility_number)}</span></th>
          <td>{_escape(summary.facility_type)}</td>
          <td>{_escape(summary.geography)}</td>
          <td>{summary.complaint_count}</td>
          <td>{summary.substantiated_count}</td>
          <td>{_escape(_detail_display_date(summary.recent_activity_date) if summary.recent_activity_date else "unknown")}</td>
          <td>
            <ul class="compact-list">
{factors}
            </ul>
          </td>
          <td>
            <div class="form-actions">
              <a class="button button-secondary" href="{_escape(complaint_queue_href)}">Open qualifying complaint queue</a>
              {next_review_link}
            </div>
            <p>{source_link}</p>
          </td>
        </tr>"""


def _facility_priority_queue_href(summary: FacilityPrioritySummary) -> str:
    query_values = {
        "facility_number": summary.facility_number if summary.facility_number != "unknown" else summary.facility_identity,
        "request_context_origin": "facility_priority_worklist",
    }
    return f"{CCLD_RECORD_REQUEST_PATH}?{urlencode(query_values)}"


def _render_facility_priorities_pagination(
    filters: FacilityPrioritiesFilters,
    pagination: Mapping[str, int],
    result_count: int,
) -> str:
    if result_count <= filters.page_size:
        return ""
    page = pagination["page"]
    total_pages = pagination["total_pages"]
    links = []
    if page > 1:
        links.append(
            f'<a class="button button-secondary" href="{_escape(_facility_priorities_page_href(filters, page - 1))}">Previous page</a>'
        )
    if page < total_pages:
        links.append(
            f'<a class="button button-secondary" href="{_escape(_facility_priorities_page_href(filters, page + 1))}">Next page</a>'
        )
    return f"""          <nav class="form-actions" aria-label="Facility priorities pagination">
            {"".join(links)}
          </nav>"""


def _facility_priorities_page_href(
    filters: FacilityPrioritiesFilters,
    page: int,
) -> str:
    query_values = {
        "start_date": filters.start_date or "",
        "end_date": filters.end_date or "",
        "facility_type": filters.facility_type,
        "geography": filters.geography,
        "min_complaints": str(filters.min_complaints),
        "min_substantiated": str(filters.min_substantiated),
        "indicator": filters.indicator,
        "page_size": str(filters.page_size),
        "page": str(page),
    }
    return f"{REVIEWER_UI_FACILITY_PRIORITIES_PATH}?{urlencode(query_values)}"


def _render_facility_priority_rules_disclosure() -> str:
    return """        <details class="technical-details notice-card">
          <summary>Prioritization and tie rules</summary>
          <p>This page uses deterministic contributing factors only: deduplicated loaded complaint count, substantiated/equivalent finding count, existing timing review flags, missing local date context, source-link availability, supported recent activity, and low-data status.</p>
          <p>Rows are ordered by substantiated/equivalent count descending, complaint count descending, strongest timing review flag descending, recent activity descending, facility name ascending, then stable facility identity ascending. These rules are visible ordering rules, not a stored or hidden risk score.</p>
        </details>"""


def _facility_trends_response(
    query: str,
    context: ReviewerUiContext,
) -> tuple[int, str, bytes]:
    query_values = parse_qs(query, keep_blank_values=True)
    filters = _facility_trend_filters(query_values)
    if (
        filters.start_date is not None
        and filters.end_date is not None
        and filters.start_date > filters.end_date
    ):
        return _html_response(
            400,
            _render_blocked_page(
                title="Complaint trend dates need attention",
                heading="Complaint trend dates need attention",
                message="Start date must be on or before end date.",
            ),
        )
    source_status, source_result = _substantiated_source_records_response(context)
    if source_status != 200:
        if not isinstance(source_result, bytes):
            raise ValueError("Expected source-derived error body to be bytes.")
        return _workflow_error_page(
            source_status,
            source_result,
            title="Complaint trends blocked",
            heading="Complaint trends blocked",
            guidance=(
                "Retry with an authenticated actor that can read the loaded "
                "source-derived corpus."
            ),
            links=(("Return to reviewer records", REVIEWER_UI_RECORDS_PATH),),
        )
    if isinstance(source_result, bytes):
        raise ValueError("Expected source-derived records.")
    complaints = _facility_trend_complaints(source_result)
    result = build_facility_trend(
        complaints,
        filters,
        today=datetime.now(CENTRAL_TIME).date(),
    )
    return _html_response(
        200,
        _render_facility_trends(
            result,
            filters=filters,
            all_complaints=complaints,
            actor_label=_signed_in_actor_label(context),
        ),
    )


def _facility_trend_filters(
    query_values: Mapping[str, list[str]],
) -> FacilityTrendFilters:
    start_date, end_date = _complaint_export_date_filters(query_values)
    grain = _first_form_value(query_values, "time_grain").strip().casefold()
    if grain not in {"month", "quarter"}:
        grain = "month"
    return FacilityTrendFilters(
        start_date=date.fromisoformat(start_date) if start_date else None,
        end_date=date.fromisoformat(end_date) if end_date else None,
        facility=_first_form_value(query_values, "facility"),
        facility_type=_first_form_value(query_values, "facility_type"),
        geography=_first_form_value(query_values, "geography"),
        finding=_first_form_value(query_values, "finding"),
        serious_topic=_first_form_value(query_values, "serious_topic"),
        time_grain=grain,
        period_count=_bounded_query_int(
            query_values,
            "period_count",
            default=_FACILITY_TRENDS_DEFAULT_PERIOD_COUNT,
            minimum=1,
            maximum=_FACILITY_TRENDS_MAX_PERIOD_COUNT,
        ),
    )


def _facility_trend_complaints(
    source_records: list[Mapping[str, Any]],
) -> list[FacilityTrendComplaint]:
    indexes = _source_record_indexes(source_records)
    complaints: list[FacilityTrendComplaint] = []
    seen_stable_complaint_ids: set[str] = set()
    for record in source_records:
        if _string(record, "entity_type") != "complaint":
            continue
        review_item = _review_item_from_source_record(record)
        source_record = _mapping(review_item, "source_record")
        stable_complaint_id = _stable_complaint_identity(source_record)
        if stable_complaint_id in seen_stable_complaint_ids:
            continue
        seen_stable_complaint_ids.add(stable_complaint_id)
        related_records = _related_source_records_from_indexes(source_record, indexes)
        complaint_related_records = _facility_trend_complaint_related_records(
            source_record,
            related_records,
        )
        original_values = _mapping(source_record, "original_values")
        identity = _mapping(source_record, "identity")
        source_record_key = _string(identity, "source_record_key")
        facility = _facility_context(related_records)
        facility_number = _facility_priority_facility_number(source_record, facility)
        facility_name = _facility_context_value(facility, "facility_name")
        if facility_name == "unknown":
            facility_name = (
                f"Facility ID {facility_number}"
                if facility_number != "unknown"
                else "Unknown facility"
            )
        complaint_date_value = _optional_string(
            original_values,
            "complaint_received_date",
        )
        validated_complaint_date = _validated_iso_date_or_none(complaint_date_value)
        complaint_date = (
            date.fromisoformat(validated_complaint_date)
            if validated_complaint_date
            else None
        )
        complaints.append(
            FacilityTrendComplaint(
                stable_complaint_id=stable_complaint_id,
                source_record_key=source_record_key,
                complaint_control_number=_optional_string(
                    original_values,
                    "complaint_control_number",
                ),
                facility_number=facility_number,
                facility_name=facility_name,
                facility_type=_facility_context_value(facility, "facility_type"),
                geography=_substantiated_geography_label(facility),
                complaint_date=complaint_date,
                finding=_optional_string(original_values, "finding"),
                substantiated=(
                    _substantiated_finding_evidence(
                        source_record,
                        complaint_related_records,
                    )
                    is not None
                ),
                serious_topics=_facility_trend_serious_topics(
                    source_record,
                    complaint_related_records,
                ),
                detail_href=_reviewer_detail_href(
                    source_record_key,
                    CcldQueueReturnContext(
                        facility_number=(
                            facility_number if facility_number != "unknown" else None
                        ),
                    ),
                ),
            )
        )
    return sorted(
        complaints,
        key=lambda item: (item.facility_name.casefold(), item.stable_complaint_id),
    )


def _facility_trend_serious_topics(
    source_record: Mapping[str, Any],
    related_records: list[Mapping[str, Any]],
) -> tuple[str, ...]:
    complaint_ids = set(_selected_source_complaint_ids(source_record))
    allegation_records = [
        record
        for record in related_records
        if _string(record, "entity_type") == "allegation"
        and complaint_ids.intersection(_flat_record_complaint_ids(record))
    ]
    evidence = _serious_topic_evidence(allegation_records)
    return tuple(
        sorted(
            {
                item["category_label"]
                for item in evidence
                if item["category_label"]
            },
            key=str.casefold,
        )
    )


def _facility_trend_complaint_related_records(
    source_record: Mapping[str, Any],
    related_records: list[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    complaint_ids = set(_selected_source_complaint_ids(source_record))
    return [
        record
        for record in related_records
        if _string(record, "entity_type") not in {"allegation", "event"}
        or bool(complaint_ids.intersection(_flat_record_complaint_ids(record)))
    ]


def _render_facility_trends(
    result: FacilityTrendResult,
    *,
    filters: FacilityTrendFilters,
    all_complaints: list[FacilityTrendComplaint],
    actor_label: str | None,
) -> str:
    rows = "\n".join(_render_facility_trend_period(period) for period in result.periods)
    rows += "\n" + _render_facility_trend_date_unavailable_row(result)
    period_label = "quarter" if filters.time_grain == "quarter" else "month"
    return _page(
        title="Complaint trends over time",
        heading="Review complaint trends over time",
        actor_label=actor_label,
        main=f"""
        <p>Compare deduplicated loaded complaint and finding activity by {period_label}, then open the contributing complaint records for review.</p>
        {_render_facility_trend_filter_form(filters, all_complaints)}
        <section aria-labelledby="facility-trends-results-heading">
          <h2 id="facility-trends-results-heading">Complaint activity by {period_label}</h2>
          <p>{result.qualifying_complaint_count} qualifying complaint record(s): {result.dated_qualifying_complaint_count} assigned to displayed periods and {len(result.date_unavailable_complaints)} with date unavailable.</p>
          <table>
            <caption>Deduplicated complaint activity, coverage states, and deterministic anomaly cues</caption>
            <thead>
              <tr>
                <th scope="col">Period</th>
                <th scope="col">Coverage</th>
                <th scope="col">Total complaints</th>
                <th scope="col">Substantiated/equivalent findings</th>
                <th scope="col">Serious-topic qualifying complaints</th>
                <th scope="col">Anomaly cue and contributing counts</th>
                <th scope="col">Complaint records</th>
              </tr>
            </thead>
            <tbody>
{rows}
            </tbody>
          </table>
        </section>
        {_render_facility_trend_rules()}
        <nav class="form-actions" aria-label="Complaint trend next actions">
          <a class="button button-secondary" href="{REVIEWER_UI_RECORDS_PATH}">Return to review queue</a>
          <a class="button button-secondary" href="{REVIEWER_UI_FACILITY_PRIORITIES_PATH}">Open facility review priorities</a>
        </nav>
""",
    )


def _render_facility_trend_filter_form(
    filters: FacilityTrendFilters,
    all_complaints: list[FacilityTrendComplaint],
) -> str:
    facility_options = _substantiated_filter_options(
        value
        for item in all_complaints
        for value in (item.facility_name, item.facility_number)
    )
    facility_type_options = _substantiated_filter_options(
        item.facility_type for item in all_complaints
    )
    geography_options = _substantiated_filter_options(
        item.geography for item in all_complaints
    )
    finding_options = _substantiated_filter_options(
        item.finding for item in all_complaints
    )
    serious_topic_options = _substantiated_filter_options(
        topic for item in all_complaints for topic in item.serious_topics
    )
    return f"""        <section class="quiet-section" aria-labelledby="facility-trends-filters-heading">
          <h2 id="facility-trends-filters-heading">Choose facilities and periods</h2>
          <form class="compact-filter-form" method="get" action="{REVIEWER_UI_FACILITY_TRENDS_PATH}">
            <div class="facility-intelligence-filter-grid">
              <p>
                <label for="facility-trends-facility">Facility name or ID</label>
                <input id="facility-trends-facility" name="facility" value="{_escape(filters.facility)}" list="facility-trends-facilities" autocomplete="off">
                <datalist id="facility-trends-facilities">{facility_options}</datalist>
              </p>
              <p>
                <label for="facility-trends-facility-type">Facility type</label>
                <input id="facility-trends-facility-type" name="facility_type" value="{_escape(filters.facility_type)}" list="facility-trends-facility-types">
                <datalist id="facility-trends-facility-types">{facility_type_options}</datalist>
              </p>
              <p>
                <label for="facility-trends-geography">Geography</label>
                <input id="facility-trends-geography" name="geography" value="{_escape(filters.geography)}" list="facility-trends-geographies">
                <datalist id="facility-trends-geographies">{geography_options}</datalist>
              </p>
              <p>
                <label for="facility-trends-finding">Finding or status</label>
                <input id="facility-trends-finding" name="finding" value="{_escape(filters.finding)}" list="facility-trends-findings">
                <datalist id="facility-trends-findings">{finding_options}</datalist>
              </p>
              <p>
                <label for="facility-trends-serious-topic">Serious review topic</label>
                <input id="facility-trends-serious-topic" name="serious_topic" value="{_escape(filters.serious_topic)}" list="facility-trends-serious-topics">
                <datalist id="facility-trends-serious-topics">{serious_topic_options}</datalist>
              </p>
              <p>
                <label for="facility-trends-start-date">Start date</label>
                <input id="facility-trends-start-date" name="start_date" type="date" value="{filters.start_date.isoformat() if filters.start_date else ''}">
              </p>
              <p>
                <label for="facility-trends-end-date">End date</label>
                <input id="facility-trends-end-date" name="end_date" type="date" value="{filters.end_date.isoformat() if filters.end_date else ''}">
              </p>
              <p>
                <label for="facility-trends-time-grain">Time grain</label>
                <select id="facility-trends-time-grain" name="time_grain">
                  {_facility_trend_option(filters.time_grain, "month", "Month")}
                  {_facility_trend_option(filters.time_grain, "quarter", "Quarter")}
                </select>
              </p>
              <p>
                <label for="facility-trends-period-count">Periods to show</label>
                <select id="facility-trends-period-count" name="period_count">
                  {_facility_trend_period_count_options(filters.period_count)}
                </select>
              </p>
            </div>
            <div class="form-actions">
              <button class="button" type="submit">Compare complaint activity</button>
              <a class="button button-secondary" href="{REVIEWER_UI_FACILITY_TRENDS_PATH}">Clear filters</a>
            </div>
          </form>
        </section>"""


def _facility_trend_option(current: str, value: str, label: str) -> str:
    selected = ' selected="selected"' if current == value else ""
    return f'<option value="{value}"{selected}>{label}</option>'


def _facility_trend_period_count_options(current: int) -> str:
    values = sorted({3, 6, 12, 18, 24, current})
    options = []
    for value in values:
        if not 1 <= value <= _FACILITY_TRENDS_MAX_PERIOD_COUNT:
            continue
        selected = ' selected="selected"' if value == current else ""
        options.append(f'<option value="{value}"{selected}>{value}</option>')
    return "".join(options)


def _render_facility_trend_period(period: FacilityTrendPeriod) -> str:
    previous = (
        str(period.preceding_complaint_count)
        if period.preceding_complaint_count is not None
        else "not available"
    )
    return f"""              <tr>
                <th scope="row">{_detail_display_date(period.period_start.isoformat())}–{_detail_display_date(period.period_end.isoformat())}</th>
                <td><span class="status-badge">{_escape(period.coverage_state)}</span></td>
                <td>{period.complaint_count}</td>
                <td>{period.substantiated_count}</td>
                <td>{period.serious_topic_count}</td>
                <td><strong>{_escape(period.anomaly_cue)}</strong><br>Current period: {period.complaint_count}; preceding period: {previous}.</td>
                <td>{_render_facility_trend_complaint_links(period.complaints)}</td>
              </tr>"""


def _render_facility_trend_date_unavailable_row(result: FacilityTrendResult) -> str:
    count = len(result.date_unavailable_complaints)
    substantiated_count = sum(
        complaint.substantiated for complaint in result.date_unavailable_complaints
    )
    serious_count = sum(
        bool(complaint.serious_topics)
        for complaint in result.date_unavailable_complaints
    )
    return f"""              <tr>
                <th scope="row">Complaint received date unavailable</th>
                <td><span class="status-badge">{DATE_UNAVAILABLE}</span></td>
                <td>{count}</td>
                <td>{substantiated_count}</td>
                <td>{serious_count}</td>
                <td><strong>No anomaly cue</strong><br>Current period: {count}; preceding period: not comparable.</td>
                <td>{_render_facility_trend_complaint_links(result.date_unavailable_complaints)}</td>
              </tr>"""


def _render_facility_trend_complaint_links(
    complaints: tuple[FacilityTrendComplaint, ...],
) -> str:
    if not complaints:
        return "No qualifying complaint records."
    links = "".join(
        f'<li><a href="{_escape(complaint.detail_href)}">Open complaint record {_escape(_facility_trend_complaint_label(complaint))}</a></li>'
        for complaint in complaints
    )
    return f"<ul>{links}</ul>"


def _facility_trend_complaint_label(complaint: FacilityTrendComplaint) -> str:
    if complaint.complaint_control_number != "unknown":
        return complaint.complaint_control_number
    return complaint.stable_complaint_id


def _render_facility_trend_rules() -> str:
    return """        <details class="technical-details">
          <summary>Anomaly cue definitions</summary>
          <p>Comparable complete periods use complaint counts only. New activity means at least 3 current complaints after 0; increased activity means at least 3 current complaints and at least twice the preceding count; decreased activity means at least 3 preceding complaints and a current count no more than half. Incomplete, unavailable, partial, or otherwise non-comparable periods receive no anomaly cue.</p>
        </details>"""


def _serious_topics_response(
    query: str,
    context: ReviewerUiContext,
) -> tuple[int, str, bytes]:
    query_values = parse_qs(query, keep_blank_values=True)
    filters = _serious_topics_filters(query_values)
    source_status, source_result = _substantiated_source_records_response(context)
    if source_status != 200:
        if not isinstance(source_result, bytes):
            raise ValueError("Expected source-derived error body to be bytes.")
        return _workflow_error_page(source_status, source_result)
    if isinstance(source_result, bytes):
        raise ValueError("Expected source-derived records.")
    source_records = source_result
    complaint_items = [
        _review_item_from_source_record(record)
        for record in source_records
        if _string(record, "entity_type") == "complaint"
    ]
    source_indexes = _source_record_indexes(source_records)
    serious_items = _serious_topic_items(complaint_items, source_indexes)
    filtered_items = _filter_serious_topic_items(serious_items, filters)
    sorted_items = _sort_substantiated_worklist_items(filtered_items, filters.sort)
    paged_items, pagination = _paginate_serious_topic_items(sorted_items, filters)
    return _html_response(
        200,
        _render_serious_topics_worklist(
            paged_items,
            filters=filters,
            result_count=len(filtered_items),
            total_qualifying_count=len(serious_items),
            all_items=serious_items,
            pagination=pagination,
            actor_label=_signed_in_actor_label(context),
        ),
    )


def _serious_topics_filters(
    query_values: Mapping[str, list[str]],
) -> SeriousTopicsFilters:
    start_date, end_date = _complaint_export_date_filters(query_values)
    return SeriousTopicsFilters(
        start_date=start_date,
        end_date=end_date,
        facility=_first_form_value(query_values, "facility"),
        facility_type=_first_form_value(query_values, "facility_type"),
        geography=_first_form_value(query_values, "geography"),
        finding=_first_form_value(query_values, "finding"),
        topic=_first_form_value(query_values, "topic"),
        match_basis=_serious_topics_match_basis(
            _first_form_value(query_values, "match_basis")
        ),
        sort=_substantiated_sort_value(_first_form_value(query_values, "sort")),
        page=_positive_int_query_value(
            _first_form_value(query_values, "page"),
            default=1,
            maximum=10000,
        ),
        page_size=_positive_int_query_value(
            _first_form_value(query_values, "page_size"),
            default=_SUBSTANTIATED_DEFAULT_PAGE_SIZE,
            maximum=_SUBSTANTIATED_MAX_PAGE_SIZE,
        ),
    )


def _serious_topics_match_basis(value: str) -> str:
    normalized = value.strip().casefold().replace("_", "-")
    if normalized in {"source-category", "keyword-cue"}:
        return normalized
    return "all"


def _serious_topic_items(
    records: list[Mapping[str, Any]],
    source_indexes: SourceRecordIndexes,
) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen_stable_complaint_ids: set[str] = set()
    for record in records:
        source_record = _mapping(record, "source_record")
        if _queue_source_record_entity_type(source_record) != "complaint":
            continue
        related_records = _related_source_records_from_indexes(
            source_record,
            source_indexes,
        )
        evidence = _serious_topic_evidence(related_records)
        if not evidence:
            continue
        stable_complaint_id = _stable_complaint_identity(source_record)
        if stable_complaint_id in seen_stable_complaint_ids:
            continue
        seen_stable_complaint_ids.add(stable_complaint_id)
        original_values = _mapping(source_record, "original_values")
        identity = _mapping(source_record, "identity")
        source_record_key = _string(identity, "source_record_key")
        facility = _facility_context(related_records)
        facility_name = _facility_context_value(facility, "facility_name")
        facility_type = _facility_context_value(facility, "facility_type")
        geography = _substantiated_geography_label(facility)
        facility_number = _facility_context_value(facility, "external_facility_number")
        if facility_number == "unknown":
            facility_number = _complaint_export_row_facility_number(
                source_record,
                CcldQueueReturnContext(),
            )
        facility_display = (
            f"Facility ID {_display_value(facility_number)}"
            if facility_name == "unknown"
            else facility_name
        )
        complaint_date = _substantiated_complaint_date(original_values)
        source_document = _mapping(source_record, "source_document")
        source_url = _optional_string(source_document, "source_url")
        category_labels = _joined_unique(
            item["category_label"]
            for item in evidence
            if item["category_label"]
        )
        source_categories = _joined_unique(
            item["source_category"]
            for item in evidence
            if item["source_category"]
        )
        matched_fields = _joined_unique(item["matched_field"] for item in evidence)
        matched_terms = _joined_unique(item["matched_term"] for item in evidence)
        match_bases = _joined_unique(item["match_basis"] for item in evidence)
        items.append(
            {
                "source_record_key": source_record_key,
                "facility_display": facility_display,
                "facility_number": facility_number,
                "facility_type": facility_type,
                "geography": geography,
                "complaint_date": complaint_date,
                "complaint_date_display": _substantiated_date_display(complaint_date),
                "finding_value": _optional_string(original_values, "finding"),
                "complaint_control_number": _optional_string(
                    original_values,
                    "complaint_control_number",
                ),
                "category_labels": category_labels,
                "source_categories": source_categories or "Not available in loaded record",
                "matched_fields": matched_fields,
                "matched_terms": matched_terms,
                "match_bases": match_bases,
                "detail_href": _reviewer_detail_href(
                    source_record_key,
                    CcldQueueReturnContext(
                        facility_number=facility_number
                        if facility_number != "unknown"
                        else None,
                    ),
                ),
                "source_url_href": (
                    source_url
                    if _has_display_value(source_url) and source_url != "unknown"
                    else ""
                ),
            }
        )
    return items


def _serious_topic_evidence(
    related_records: list[Mapping[str, Any]],
) -> list[dict[str, str]]:
    evidence: list[dict[str, str]] = []
    for record in related_records:
        if _string(record, "entity_type") != "allegation":
            continue
        values = _mapping(record, "original_values")
        category = _optional_string(values, "allegation_category")
        category_label = _SERIOUS_TOPIC_CATEGORY_BY_NORMALIZED.get(category.casefold())
        if category_label is not None:
            evidence.append(
                {
                    "category_label": category_label,
                    "source_category": category,
                    "matched_field": "source-derived allegation_category",
                    "matched_term": category,
                    "match_basis": "Source category",
                }
            )
            continue
        if category not in {"unknown", "Unknown", ""}:
            continue
        cue_term = _serious_topic_keyword_term(
            _optional_string(values, "allegation_text")
        )
        if cue_term is None:
            continue
        evidence.append(
            {
                "category_label": "Possible keyword cue",
                "source_category": "",
                "matched_field": "keyword-assisted allegation_text",
                "matched_term": cue_term,
                "match_basis": "Possible keyword cue",
            }
        )
    return evidence


def _serious_topic_keyword_term(value: str) -> str | None:
    if value == "unknown":
        return None
    normalized = " ".join(value.casefold().split())
    if not normalized:
        return None
    if any(phrase in normalized for phrase in _SERIOUS_TOPIC_CUE_EXCLUDED_PHRASES):
        return None
    for term in _SERIOUS_TOPIC_CUE_TERMS:
        if _bounded_text_term_matches(normalized, term.casefold()):
            return term
    return None


def _bounded_text_term_matches(text: str, term: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text) is not None


def _joined_unique(values: object) -> str:
    if not isinstance(values, list | tuple | set):
        values = tuple(values)  # type: ignore[arg-type]
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return "; ".join(result)


def _filter_serious_topic_items(
    items: list[dict[str, str]],
    filters: SeriousTopicsFilters,
) -> list[dict[str, str]]:
    return [item for item in items if _serious_topic_item_matches_filters(item, filters)]


def _serious_topic_item_matches_filters(
    item: Mapping[str, str],
    filters: SeriousTopicsFilters,
) -> bool:
    substantiated_filter_item = dict(item)
    substantiated_filter_item["finding_label"] = item["finding_value"]
    if not _substantiated_item_matches_filters(
        substantiated_filter_item,
        SubstantiatedWorklistFilters(
            start_date=filters.start_date,
            end_date=filters.end_date,
            facility=filters.facility,
            facility_type=filters.facility_type,
            geography=filters.geography,
            finding=filters.finding,
            sort=filters.sort,
            page=filters.page,
            page_size=filters.page_size,
        ),
    ):
        return False
    if filters.topic and not _text_filter_matches(
        filters.topic,
        (item["category_labels"], item["source_categories"], item["matched_terms"]),
    ):
        return False
    if filters.match_basis == "source-category" and "Source category" not in item["match_bases"]:
        return False
    if filters.match_basis == "keyword-cue" and "Possible keyword cue" not in item["match_bases"]:
        return False
    return True


def _paginate_serious_topic_items(
    items: list[dict[str, str]],
    filters: SeriousTopicsFilters,
) -> tuple[list[dict[str, str]], Mapping[str, int]]:
    total_pages = max((len(items) + filters.page_size - 1) // filters.page_size, 1)
    page = min(filters.page, total_pages)
    start = (page - 1) * filters.page_size
    end = start + filters.page_size
    return items[start:end], {
        "page": page,
        "page_size": filters.page_size,
        "total_pages": total_pages,
        "offset": start,
    }


def _render_serious_topics_worklist(
    items: list[dict[str, str]],
    *,
    filters: SeriousTopicsFilters,
    result_count: int,
    total_qualifying_count: int,
    all_items: list[dict[str, str]],
    pagination: Mapping[str, int],
    actor_label: str | None,
) -> str:
    filter_markup = _render_serious_topics_filter_form(filters, all_items)
    filter_basis_markup = _render_serious_topics_filter_basis(filters)
    summary = _render_serious_topics_count_summary(
        result_count,
        total_qualifying_count,
        pagination,
    )
    if not items:
        list_markup = f"""        <section class="hero-card" aria-labelledby="serious-topics-empty-heading">
          <h2 id="serious-topics-empty-heading">No serious-topic complaint records matched.</h2>
          {summary}
          <p>Adjust the filters or clear them to return to all qualifying loaded records.</p>
        </section>"""
    else:
        rows = "\n".join(_render_serious_topic_row(item) for item in items)
        list_markup = f"""        <section aria-labelledby="serious-topics-results-heading">
          <h2 id="serious-topics-results-heading">Loaded serious-topic complaint records</h2>
          {summary}
          <table>
            <caption>Governed serious-topic complaint worklist</caption>
            <thead>
              <tr>
                <th scope="col">Facility</th>
                <th scope="col">Facility ID</th>
                <th scope="col">Complaint date</th>
                <th scope="col">Finding</th>
                <th scope="col">Review topic</th>
                <th scope="col">Match basis</th>
                <th scope="col">Matched field and term</th>
                <th scope="col">Source-derived category</th>
                <th scope="col">Facility type</th>
                <th scope="col">Geography</th>
                <th scope="col">Original public report</th>
                <th scope="col">Review action</th>
              </tr>
            </thead>
            <tbody>
{rows}
            </tbody>
          </table>
          {_render_serious_topics_pagination(filters, pagination, result_count)}
        </section>"""
    return _page(
        title="Serious-topic complaint worklist",
        heading="Serious-topic complaint worklist",
        actor_label=actor_label,
        main=f"""
        <section class="quiet-section" aria-labelledby="serious-topics-purpose-heading">
          <h2 id="serious-topics-purpose-heading">Filter serious review topics</h2>
          <p>Source categories come from public records. Review topics and possible keyword cues help narrow records for review.</p>
        </section>
{filter_markup}
{filter_basis_markup}
{list_markup}
        <section class="quiet-section" aria-labelledby="serious-topics-next-heading">
          <h2 id="serious-topics-next-heading">Next steps</h2>
          <ul>
            <li><a href="{REVIEWER_UI_RECORDS_PATH}">Return to review queue</a></li>
            <li><a href="{REVIEWER_UI_SUBSTANTIATED_TRIAGE_PATH}">Open substantiated complaint worklist</a></li>
          </ul>
        </section>
""",
    )


def _render_serious_topic_row(item: Mapping[str, str]) -> str:
    matched = (
        f"{item['matched_fields']}: {item['matched_terms']}"
        if item["matched_terms"]
        else item["matched_fields"]
    )
    return f"""        <tr>
          <th scope="row">{_escape(item['facility_display'])}</th>
          <td>{_copyable_value("Facility ID", item['facility_number'])}</td>
          <td>{_escape(item['complaint_date_display'])}</td>
          <td>{_escape(item['finding_value'])}</td>
          <td>{_escape(item['category_labels'])}</td>
          <td>{_escape(item['match_bases'])}</td>
          <td>{_escape(matched)}</td>
          <td>{_escape(item['source_categories'])}</td>
          <td>{_escape(item['facility_type'])}</td>
          <td>{_escape(item['geography'])}</td>
          <td>{_serious_topic_source_link(item)}</td>
          <td><a class="button" href="{_escape(item['detail_href'])}">Open complaint review workspace</a></td>
        </tr>"""


def _render_serious_topics_filter_basis(filters: SeriousTopicsFilters) -> str:
    if filters.match_basis == "source-category":
        return """        <p class="helper-text">Filter basis: Source category.</p>"""
    if filters.match_basis == "keyword-cue":
        return """        <p class="helper-text">Filter basis: Possible keyword cue.</p>"""
    return ""


def _render_serious_topics_count_summary(
    result_count: int,
    total_qualifying_count: int,
    pagination: Mapping[str, int],
) -> str:
    page = pagination["page"]
    page_size = pagination["page_size"]
    offset = pagination["offset"]
    if result_count == 0:
        shown_range = "Showing 0"
    else:
        first = offset + 1
        last = min(offset + page_size, result_count)
        shown_range = f"Showing {first}-{last}"
    return (
        f"<p>{shown_range} of {result_count} matching serious-topic complaint "
        f"record(s); {total_qualifying_count} total qualifying authorized "
        "source-derived complaint record(s).</p>"
        f"<p class=\"helper-text\">Page {page} of {pagination['total_pages']}.</p>"
    )


def _render_serious_topics_filter_form(
    filters: SeriousTopicsFilters,
    all_items: list[dict[str, str]],
) -> str:
    finding_options = _substantiated_filter_options(
        item["finding_value"] for item in all_items
    )
    facility_type_options = _substantiated_filter_options(
        item["facility_type"] for item in all_items
    )
    geography_options = _substantiated_filter_options(
        item["geography"] for item in all_items
    )
    topic_options = _substantiated_filter_options(
        tuple(_SERIOUS_TOPIC_CATEGORY_LABELS.values()) + ("Possible keyword cue",)
    )
    return f"""        <section class="quiet-section" aria-labelledby="serious-topics-filters-heading">
          <h2 id="serious-topics-filters-heading">Filter and sort</h2>
          <form class="compact-filter-form" method="get" action="{REVIEWER_UI_SERIOUS_TOPICS_PATH}">
            <div class="facility-intelligence-filter-grid">
              <p>
                <label for="serious-topics-start-date">From complaint date</label>
                <input id="serious-topics-start-date" name="start_date" type="date" value="{_escape(filters.start_date or '')}">
              </p>
              <p>
                <label for="serious-topics-end-date">To complaint date</label>
                <input id="serious-topics-end-date" name="end_date" type="date" value="{_escape(filters.end_date or '')}">
              </p>
              <p>
                <label for="serious-topics-facility">Facility name, ID, or complaint ID</label>
                <input id="serious-topics-facility" name="facility" value="{_escape(filters.facility)}" autocomplete="off">
              </p>
              <p>
                <label for="serious-topics-facility-type">Facility type</label>
                <input id="serious-topics-facility-type" name="facility_type" value="{_escape(filters.facility_type)}" list="serious-topics-facility-types">
                <datalist id="serious-topics-facility-types">{facility_type_options}</datalist>
              </p>
              <p>
                <label for="serious-topics-geography">Geography</label>
                <input id="serious-topics-geography" name="geography" value="{_escape(filters.geography)}" list="serious-topics-geographies">
                <datalist id="serious-topics-geographies">{geography_options}</datalist>
              </p>
              <p>
                <label for="serious-topics-finding">Finding</label>
                <input id="serious-topics-finding" name="finding" value="{_escape(filters.finding)}" list="serious-topics-findings">
                <datalist id="serious-topics-findings">{finding_options}</datalist>
              </p>
              <p>
                <label for="serious-topics-topic">Review topic</label>
                <input id="serious-topics-topic" name="topic" value="{_escape(filters.topic)}" list="serious-topics-themes">
                <datalist id="serious-topics-themes">{topic_options}</datalist>
              </p>
              <p>
                <label for="serious-topics-match-basis">Match basis</label>
                <select id="serious-topics-match-basis" name="match_basis">
                  {_serious_topics_basis_option(filters.match_basis, "all", "Source categories and possible keyword cues")}
                  {_serious_topics_basis_option(filters.match_basis, "source-category", "Source-derived categories only")}
                  {_serious_topics_basis_option(filters.match_basis, "keyword-cue", "Possible keyword cues only")}
                </select>
              </p>
              <p>
                <label for="serious-topics-sort">Sort</label>
                <select id="serious-topics-sort" name="sort">
                  {_substantiated_sort_option(filters.sort, "complaint_date_desc", "Complaint date, newest first")}
                  {_substantiated_sort_option(filters.sort, "complaint_date_asc", "Complaint date, oldest first")}
                  {_substantiated_sort_option(filters.sort, "facility_asc", "Facility, A to Z")}
                  {_substantiated_sort_option(filters.sort, "facility_desc", "Facility, Z to A")}
                </select>
              </p>
              <p>
                <label for="serious-topics-page-size">Rows per page</label>
                <select id="serious-topics-page-size" name="page_size">
                  {_substantiated_page_size_option(filters.page_size, 25)}
                  {_substantiated_page_size_option(filters.page_size, 50)}
                  {_substantiated_page_size_option(filters.page_size, 100)}
                </select>
              </p>
            </div>
            <div class="form-actions">
              <button class="button" type="submit">Apply filters</button>
              <a class="button button-secondary" href="{REVIEWER_UI_SERIOUS_TOPICS_PATH}">Clear filters</a>
            </div>
          </form>
        </section>"""


def _serious_topics_basis_option(current: str, value: str, label: str) -> str:
    selected = ' selected="selected"' if current == value else ""
    return f'<option value="{_escape(value)}"{selected}>{_escape(label)}</option>'


def _render_serious_topics_pagination(
    filters: SeriousTopicsFilters,
    pagination: Mapping[str, int],
    result_count: int,
) -> str:
    if result_count <= filters.page_size:
        return ""
    page = pagination["page"]
    total_pages = pagination["total_pages"]
    links = []
    if page > 1:
        links.append(
            f'<a class="button button-secondary" href="{_escape(_serious_topics_page_href(filters, page - 1))}">Previous page</a>'
        )
    if page < total_pages:
        links.append(
            f'<a class="button button-secondary" href="{_escape(_serious_topics_page_href(filters, page + 1))}">Next page</a>'
        )
    return f"""          <nav class="form-actions" aria-label="Serious-topic worklist pagination">
            {"".join(links)}
          </nav>"""


def _serious_topics_page_href(filters: SeriousTopicsFilters, page: int) -> str:
    query_values = {
        "start_date": filters.start_date or "",
        "end_date": filters.end_date or "",
        "facility": filters.facility,
        "facility_type": filters.facility_type,
        "geography": filters.geography,
        "finding": filters.finding,
        "topic": filters.topic,
        "match_basis": filters.match_basis,
        "sort": filters.sort,
        "page_size": str(filters.page_size),
        "page": str(page),
    }
    return f"{REVIEWER_UI_SERIOUS_TOPICS_PATH}?{urlencode(query_values)}"


def _serious_topic_source_link(item: Mapping[str, str]) -> str:
    source_url_href = item["source_url_href"]
    if not source_url_href:
        return "Original public report link not available for this loaded complaint."
    control_number = item["complaint_control_number"]
    suffix = (
        f" for {control_number}"
        if control_number and control_number != "unknown"
        else ""
    )
    return (
        f"<a href=\"{_escape(source_url_href)}\">Open original public report{_escape(suffix)}</a>"
    )


def _substantiated_triage_response(
    query: str,
    context: ReviewerUiContext,
) -> tuple[int, str, bytes]:
    query_values = parse_qs(query, keep_blank_values=True)
    filters = _substantiated_worklist_filters(query_values)
    source_status, source_result = _substantiated_source_records_response(context)
    if source_status != 200:
        if not isinstance(source_result, bytes):
            raise ValueError("Expected source-derived error body to be bytes.")
        return _workflow_error_page(source_status, source_result)
    if isinstance(source_result, bytes):
        raise ValueError("Expected source-derived records.")
    source_records = source_result
    complaint_items = [
        _review_item_from_source_record(record)
        for record in source_records
        if _string(record, "entity_type") == "complaint"
    ]
    source_indexes = _source_record_indexes(source_records)
    substantiated_items = _substantiated_triage_items(
        complaint_items,
        source_indexes,
    )
    filtered_items = _filter_substantiated_worklist_items(substantiated_items, filters)
    sorted_items = _sort_substantiated_worklist_items(filtered_items, filters.sort)
    paged_items, pagination = _paginate_substantiated_worklist_items(
        sorted_items,
        filters,
    )
    return _html_response(
        200,
        _render_substantiated_triage(
            paged_items,
            filters=filters,
            result_count=len(filtered_items),
            total_qualifying_count=len(substantiated_items),
            all_items=substantiated_items,
            pagination=pagination,
            actor_label=_signed_in_actor_label(context),
        ),
    )


def _substantiated_triage_items(
    records: list[Mapping[str, Any]],
    source_indexes: SourceRecordIndexes,
) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen_stable_complaint_ids: set[str] = set()
    for record in records:
        source_record = _mapping(record, "source_record")
        if _queue_source_record_entity_type(source_record) != "complaint":
            continue
        original_values = _mapping(source_record, "original_values")
        identity = _mapping(source_record, "identity")
        source_record_key = _string(identity, "source_record_key")
        related_records = _related_source_records_from_indexes(
            source_record,
            source_indexes,
        )
        finding_evidence = _substantiated_finding_evidence(
            source_record,
            related_records,
        )
        if finding_evidence is None:
            continue
        stable_complaint_id = _stable_complaint_identity(source_record)
        if stable_complaint_id in seen_stable_complaint_ids:
            continue
        seen_stable_complaint_ids.add(stable_complaint_id)
        facility = _facility_context(related_records)
        facility_name = _facility_context_value(facility, "facility_name")
        facility_type = _facility_context_value(facility, "facility_type")
        geography = _substantiated_geography_label(facility)
        facility_number = _facility_context_value(facility, "external_facility_number")
        if facility_number == "unknown":
            facility_number = _complaint_export_row_facility_number(
            source_record,
            CcldQueueReturnContext(),
            )
        if facility_name == "unknown":
            facility_display = f"Facility ID {_display_value(facility_number)}"
        else:
            facility_display = facility_name
        date_context = _substantiated_date_context(original_values)
        complaint_date = _substantiated_complaint_date(original_values)
        detail_href = _reviewer_detail_href(
            source_record_key,
            CcldQueueReturnContext(
                facility_number=facility_number if facility_number != "unknown" else None,
            ),
        )
        source_document = _mapping(source_record, "source_document")
        source_url = _optional_string(source_document, "source_url")
        source_url_href = source_url if _has_display_value(source_url) and source_url != "unknown" else ""
        category_or_summary = _substantiated_category_or_summary(
            source_record,
            related_records,
        )
        complaint_control_number = _optional_string(
            original_values,
            "complaint_control_number",
        )
        items.append(
            {
                "source_record_key": source_record_key,
                "facility_display": facility_display,
                "facility_number": facility_number,
                "facility_type": facility_type,
                "geography": geography,
                "date_context": date_context,
                "complaint_date": complaint_date,
                "complaint_date_display": _substantiated_date_display(complaint_date),
                "finding_label": finding_evidence.label,
                "finding_value": finding_evidence.value,
                "category_or_summary": category_or_summary,
                "complaint_control_number": complaint_control_number,
                "detail_href": detail_href,
                "source_url_href": source_url_href,
            }
        )
    return items


def _substantiated_finding_label(values: Mapping[str, Any]) -> str | None:
    evidence = _substantiated_finding_evidence_from_values(
        "complaint",
        values,
    )
    return evidence.label if evidence is not None else None


def _substantiated_finding_evidence(
    source_record: Mapping[str, Any],
    related_records: list[Mapping[str, Any]],
) -> SubstantiatedFindingEvidence | None:
    complaint_values = _mapping(source_record, "original_values")
    complaint_evidence = _substantiated_finding_evidence_from_values(
        "complaint",
        complaint_values,
    )
    if complaint_evidence is not None:
        return complaint_evidence
    for record in related_records:
        if _string(record, "entity_type") != "allegation":
            continue
        evidence = _substantiated_finding_evidence_from_values(
            "allegation",
            _mapping(record, "original_values"),
        )
        if evidence is not None:
            return evidence
    for record in related_records:
        if _string(record, "entity_type") != "event":
            continue
        evidence = _substantiated_event_finding_evidence(record)
        if evidence is not None:
            return evidence
    return None


def _substantiated_finding_evidence_from_values(
    source_label: str,
    values: Mapping[str, Any],
) -> SubstantiatedFindingEvidence | None:
    candidate_keys = {
        "finding",
        "finding_status",
        "investigation_finding",
        "normalized_finding",
        "resolution",
        "status",
    }
    for key, raw_value in values.items():
        key_text = str(key)
        if key_text.strip().casefold() not in candidate_keys:
            continue
        display_value = _substantiated_finding_display_value(raw_value)
        if display_value is None:
            continue
        return SubstantiatedFindingEvidence(
            label=f"{source_label} {key_text}: {display_value}",
            value=display_value,
        )
    return None


def _substantiated_event_finding_evidence(
    record: Mapping[str, Any],
) -> SubstantiatedFindingEvidence | None:
    values = _mapping(record, "original_values")
    direct_evidence = _substantiated_finding_evidence_from_values(
        "event",
        values,
    )
    if direct_evidence is not None:
        return direct_evidence
    context_values = tuple(
        _display_value(values[key])
        for key in (
            "event_type",
            "field_name",
            "field",
            "source_field",
            "source_section",
            "type",
        )
        if key in values and _has_display_value(values[key])
    )
    normalized_context = " ".join(context_values).casefold()
    if not any(
        marker in normalized_context
        for marker in ("finding", "investigation", "resolution", "status")
    ):
        return None
    for key in ("event_text", "summary", "description", "text"):
        raw_value = values.get(key)
        display_value = _substantiated_normalized_finding_value(raw_value)
        if display_value is None:
            continue
        context_label = context_values[0] if context_values else key
        return SubstantiatedFindingEvidence(
            label=f"event {context_label}: {display_value}",
            value=display_value,
        )
    return None


def _substantiated_finding_display_value(value: object) -> str | None:
    if not _has_display_value(value):
        return None
    text = _display_value(value)
    if not _is_substantiated_equivalent(text):
        return None
    compact_text = " ".join(text.split())
    if len(compact_text) <= 80:
        return compact_text
    return _substantiated_normalized_finding_value(compact_text)


def _substantiated_normalized_finding_value(value: object) -> str | None:
    if not _has_display_value(value):
        return None
    text = _display_value(value)
    if not _is_substantiated_equivalent(text):
        return None
    normalized = " ".join(text.split()).casefold()
    if "founded" in normalized:
        return "Founded"
    if "sustained" in normalized:
        return "Sustained"
    return "Substantiated"


def _stable_complaint_identity(source_record: Mapping[str, Any]) -> str:
    identity = _mapping(source_record, "identity")
    stable_source_id = _optional_string(identity, "stable_source_id")
    if stable_source_id != "unknown":
        return stable_source_id
    original_values = _mapping(source_record, "original_values")
    complaint_id = _optional_string(original_values, "complaint_id")
    if complaint_id != "unknown":
        return complaint_id
    return _string(identity, "source_record_key")


def _is_substantiated_equivalent(value: str) -> bool:
    normalized = " ".join(value.strip().casefold().split())
    if not normalized:
        return False
    if "unsubstantiated" in normalized or "not substantiated" in normalized:
        return False
    return any(keyword in normalized for keyword in _SUBSTANTIATED_EQUIVALENT_KEYWORDS)


def _substantiated_date_context(values: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for label, key in (
        ("Complaint received", "complaint_received_date"),
        ("Report date", "report_date"),
        ("Visit date", "visit_date"),
        ("Date signed", "date_signed"),
    ):
        raw_value = values.get(key)
        if not _has_display_value(raw_value):
            continue
        parts.append(f"{label}: {_display_value(raw_value)}")
    if parts:
        return "; ".join(parts)
    return "No complaint/report date context available in currently loaded records."


def _substantiated_complaint_date(values: Mapping[str, Any]) -> str:
    for key in (
        "complaint_received_date",
        "report_date",
        "visit_date",
        "date_signed",
    ):
        raw_value = values.get(key)
        if _has_display_value(raw_value):
            parsed = _validated_iso_date_or_none(_display_value(raw_value)[:10])
            if parsed is not None:
                return parsed
    return "unknown"


def _substantiated_date_display(value: str) -> str:
    if not value or value == "unknown":
        return "Not available in loaded record"
    return _queue_display_date(value)


def _substantiated_finding_value(finding_label: str) -> str:
    _field, separator, value = finding_label.partition(":")
    return value.strip() if separator else finding_label


def _substantiated_geography_label(facility: Mapping[str, Any] | None) -> str:
    if facility is None:
        return "unknown"
    parts = []
    for key in ("county", "city", "state"):
        value = _facility_context_value(facility, key)
        if value != "unknown" and value not in parts:
            parts.append(value)
    return ", ".join(parts) if parts else "unknown"


def _substantiated_category_or_summary(
    source_record: Mapping[str, Any],
    related_records: list[Mapping[str, Any]],
) -> str:
    original_values = _mapping(source_record, "original_values")
    for key in (
        "allegation_category",
        "category",
        "complaint_category",
        "summary",
        "source_summary",
    ):
        value = original_values.get(key)
        if _has_display_value(value):
            return _display_value(value)
    categories: list[str] = []
    for record in related_records:
        if _string(record, "entity_type") != "allegation":
            continue
        values = _mapping(record, "original_values")
        for key in ("allegation_category", "category"):
            value = values.get(key)
            if _has_display_value(value):
                label = _display_value(value)
                if label not in categories:
                    categories.append(label)
    if categories:
        return "; ".join(categories[:3])
    return "Not available in loaded record"


def _substantiated_worklist_filters(
    query_values: Mapping[str, list[str]],
) -> SubstantiatedWorklistFilters:
    start_date, end_date = _complaint_export_date_filters(query_values)
    return SubstantiatedWorklistFilters(
        start_date=start_date,
        end_date=end_date,
        facility=_first_form_value(query_values, "facility"),
        facility_type=_first_form_value(query_values, "facility_type"),
        geography=_first_form_value(query_values, "geography"),
        finding=_first_form_value(query_values, "finding"),
        sort=_substantiated_sort_value(_first_form_value(query_values, "sort")),
        page=_positive_int_query_value(
            _first_form_value(query_values, "page"),
            default=1,
            maximum=10000,
        ),
        page_size=_positive_int_query_value(
            _first_form_value(query_values, "page_size"),
            default=_SUBSTANTIATED_DEFAULT_PAGE_SIZE,
            maximum=_SUBSTANTIATED_MAX_PAGE_SIZE,
        ),
    )


def _substantiated_sort_value(value: str) -> str:
    if value in {
        "complaint_date_desc",
        "complaint_date_asc",
        "facility_asc",
        "facility_desc",
    }:
        return value
    return "complaint_date_desc"


def _positive_int_query_value(value: str, *, default: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except ValueError:
        return default
    if parsed < 1:
        return default
    return min(parsed, maximum)


def _filter_substantiated_worklist_items(
    items: list[dict[str, str]],
    filters: SubstantiatedWorklistFilters,
) -> list[dict[str, str]]:
    return [
        item
        for item in items
        if _substantiated_item_matches_filters(item, filters)
    ]


def _substantiated_item_matches_filters(
    item: Mapping[str, str],
    filters: SubstantiatedWorklistFilters,
) -> bool:
    if filters.start_date and (
        item["complaint_date"] == "unknown"
        or item["complaint_date"] < filters.start_date
    ):
        return False
    if filters.end_date and (
        item["complaint_date"] == "unknown"
        or item["complaint_date"] > filters.end_date
    ):
        return False
    if filters.facility and not _text_filter_matches(
        filters.facility,
        (
            item["facility_display"],
            item["facility_number"],
            item["complaint_control_number"],
        ),
    ):
        return False
    if filters.facility_type and not _text_filter_matches(
        filters.facility_type,
        (item["facility_type"],),
    ):
        return False
    if filters.geography and not _text_filter_matches(
        filters.geography,
        (item["geography"],),
    ):
        return False
    if filters.finding and not _text_filter_matches(
        filters.finding,
        (item["finding_value"], item["finding_label"]),
    ):
        return False
    return True


def _text_filter_matches(query: str, values: tuple[str, ...]) -> bool:
    normalized_query = " ".join(query.casefold().split())
    if not normalized_query:
        return True
    return any(normalized_query in value.casefold() for value in values if value)


def _sort_substantiated_worklist_items(
    items: list[dict[str, str]],
    sort_value: str,
) -> list[dict[str, str]]:
    if sort_value == "complaint_date_asc":
        return sorted(items, key=_substantiated_date_asc_sort_key)
    if sort_value == "facility_asc":
        return sorted(items, key=_substantiated_facility_sort_key)
    if sort_value == "facility_desc":
        return _sort_substantiated_by_facility_desc(items)
    return sorted(items, key=_substantiated_date_desc_sort_key)


def _substantiated_date_asc_sort_key(
    item: Mapping[str, str],
) -> tuple[bool, str, str, str]:
    date_value = item["complaint_date"]
    return (
        date_value == "unknown",
        "" if date_value == "unknown" else date_value,
        item["facility_display"].casefold(),
        item["source_record_key"],
    )


def _substantiated_date_desc_sort_key(
    item: Mapping[str, str],
) -> tuple[bool, str, str, str]:
    date_value = item["complaint_date"]
    return (
        date_value == "unknown",
        _reverse_iso_date_key(date_value),
        item["facility_display"].casefold(),
        item["source_record_key"],
    )


def _substantiated_facility_sort_key(
    item: Mapping[str, str],
) -> tuple[str, bool, str, str]:
    date_key = _substantiated_date_asc_sort_key(item)
    return (
        item["facility_display"].casefold(),
        date_key[0],
        date_key[1],
        item["source_record_key"],
    )


def _sort_substantiated_by_facility_desc(
    items: list[dict[str, str]],
) -> list[dict[str, str]]:
    secondary_sorted = sorted(items, key=_substantiated_facility_sort_key)
    return sorted(
        secondary_sorted,
        key=lambda item: item["facility_display"].casefold(),
        reverse=True,
    )


def _reverse_iso_date_key(value: str) -> str:
    if value == "unknown":
        return "9999-99-99"
    return "".join(str(9 - int(ch)) if ch.isdigit() else ch for ch in value)


def _paginate_substantiated_worklist_items(
    items: list[dict[str, str]],
    filters: SubstantiatedWorklistFilters,
) -> tuple[list[dict[str, str]], Mapping[str, int]]:
    total_pages = max((len(items) + filters.page_size - 1) // filters.page_size, 1)
    page = min(filters.page, total_pages)
    start = (page - 1) * filters.page_size
    end = start + filters.page_size
    return items[start:end], {
        "page": page,
        "page_size": filters.page_size,
        "total_pages": total_pages,
        "offset": start,
    }


def _render_substantiated_triage(
    items: list[dict[str, str]],
    *,
    filters: SubstantiatedWorklistFilters,
    result_count: int,
    total_qualifying_count: int,
    all_items: list[dict[str, str]],
    pagination: Mapping[str, int],
    actor_label: str | None,
) -> str:
    filter_markup = _render_substantiated_filter_form(filters, all_items)
    summary = _render_substantiated_count_summary(
        result_count,
        total_qualifying_count,
        pagination,
    )
    if not items:
        list_markup = f"""        <section class=\"hero-card\" aria-labelledby=\"substantiated-empty-heading\">
          <h2 id=\"substantiated-empty-heading\">No loaded substantiated/equivalent complaint records matched.</h2>
          {summary}
          <p>Adjust the filters or clear them to return to all qualifying loaded records.</p>
        </section>"""
    else:
        rows = "\n".join(
            f"""        <tr>
          <th scope=\"row\">{_escape(item['facility_display'])}</th>
          <td>{_copyable_value("Facility ID", item['facility_number'])}</td>
          <td>{_escape(item['complaint_date_display'])}</td>
          <td>{_escape(item['finding_value'])}</td>
          <td>{_escape(item['category_or_summary'])}</td>
          <td>{_escape(item['facility_type'])}</td>
          <td>{_escape(item['geography'])}</td>
          <td>
            {_substantiated_source_link(item)}
          </td>
          <td>
            <a class=\"button\" href=\"{_escape(item['detail_href'])}\">Open complaint review workspace</a>
          </td>
        </tr>"""
            for item in items
        )
        list_markup = f"""        <section aria-labelledby=\"substantiated-results-heading\">
          <h2 id=\"substantiated-results-heading\">Loaded substantiated/equivalent complaint records</h2>
          {summary}
          <table>
            <caption>Source-traceable substantiated complaint worklist</caption>
            <thead>
              <tr>
                <th scope=\"col\">Facility</th>
                <th scope=\"col\">Facility ID</th>
                <th scope=\"col\">Complaint date</th>
                <th scope=\"col\">Normalized finding</th>
                <th scope=\"col\">Category or summary</th>
                <th scope=\"col\">Facility type</th>
                <th scope=\"col\">Geography</th>
                <th scope=\"col\">Original public report</th>
                <th scope=\"col\">Review action</th>
              </tr>
            </thead>
            <tbody>
{rows}
            </tbody>
          </table>
          {_render_substantiated_pagination(filters, pagination, result_count)}
        </section>"""
    return _page(
        title="Source-traceable substantiated complaint worklist",
        heading="Source-traceable substantiated complaint worklist",
        actor_label=actor_label,
        main=f"""
        <section class=\"quiet-section\" aria-labelledby=\"substantiated-decision-heading\">
          <h2 id=\"substantiated-decision-heading\">Find substantiated complaint records that need source review</h2>
          <p>Use this worklist to find loaded public complaint records whose source-reported finding indicates substantiated or an equivalent value, open the original public report, and continue in the complaint review workspace.</p>
          <p>Counts are reconciled to authorized loaded source-derived complaint records. This page does not claim source completeness or make legal conclusions.</p>
        </section>
{filter_markup}
{list_markup}
        {_render_substantiated_triage_guidance_disclosure()}
        <section class=\"quiet-section\" aria-labelledby=\"substantiated-next-heading\">
          <h2 id=\"substantiated-next-heading\">Next steps</h2>
          <ul>
            <li><a href=\"{REVIEWER_UI_RECORDS_PATH}\">Return to review queue</a></li>
            <li><a href=\"{CCLD_RECORD_REQUEST_PATH}\">Return to CCLD request queue</a></li>
          </ul>
        </section>
""",
    )


def _render_substantiated_count_summary(
    result_count: int,
    total_qualifying_count: int,
    pagination: Mapping[str, int],
) -> str:
    page = pagination["page"]
    page_size = pagination["page_size"]
    offset = pagination["offset"]
    if result_count == 0:
        shown_range = "Showing 0"
    else:
        first = offset + 1
        last = min(offset + page_size, result_count)
        shown_range = f"Showing {first}-{last}"
    return (
        f"<p>{shown_range} of {result_count} matching qualifying complaint "
        f"record(s); {total_qualifying_count} total qualifying authorized "
        "source-derived complaint record(s).</p>"
        f"<p class=\"helper-text\">Page {page} of {pagination['total_pages']}.</p>"
    )


def _render_substantiated_filter_form(
    filters: SubstantiatedWorklistFilters,
    all_items: list[dict[str, str]],
) -> str:
    finding_options = _substantiated_filter_options(
        item["finding_value"] for item in all_items
    )
    facility_type_options = _substantiated_filter_options(
        item["facility_type"] for item in all_items
    )
    geography_options = _substantiated_filter_options(
        item["geography"] for item in all_items
    )
    return f"""        <section class="quiet-section" aria-labelledby="substantiated-filters-heading">
          <h2 id="substantiated-filters-heading">Filter and sort</h2>
          <form class="compact-filter-form" method="get" action="{REVIEWER_UI_SUBSTANTIATED_TRIAGE_PATH}">
            <div class="facility-intelligence-filter-grid">
              <p>
                <label for="substantiated-start-date">From complaint date</label>
                <input id="substantiated-start-date" name="start_date" type="date" value="{_escape(filters.start_date or '')}">
              </p>
              <p>
                <label for="substantiated-end-date">To complaint date</label>
                <input id="substantiated-end-date" name="end_date" type="date" value="{_escape(filters.end_date or '')}">
              </p>
              <p>
                <label for="substantiated-facility">Facility name, ID, or complaint ID</label>
                <input id="substantiated-facility" name="facility" value="{_escape(filters.facility)}" autocomplete="off">
              </p>
              <p>
                <label for="substantiated-facility-type">Facility type</label>
                <input id="substantiated-facility-type" name="facility_type" value="{_escape(filters.facility_type)}" list="substantiated-facility-types">
                <datalist id="substantiated-facility-types">{facility_type_options}</datalist>
              </p>
              <p>
                <label for="substantiated-geography">Geography</label>
                <input id="substantiated-geography" name="geography" value="{_escape(filters.geography)}" list="substantiated-geographies">
                <datalist id="substantiated-geographies">{geography_options}</datalist>
              </p>
              <p>
                <label for="substantiated-finding">Finding</label>
                <input id="substantiated-finding" name="finding" value="{_escape(filters.finding)}" list="substantiated-findings">
                <datalist id="substantiated-findings">{finding_options}</datalist>
              </p>
              <p>
                <label for="substantiated-sort">Sort</label>
                <select id="substantiated-sort" name="sort">
                  {_substantiated_sort_option(filters.sort, "complaint_date_desc", "Complaint date, newest first")}
                  {_substantiated_sort_option(filters.sort, "complaint_date_asc", "Complaint date, oldest first")}
                  {_substantiated_sort_option(filters.sort, "facility_asc", "Facility, A to Z")}
                  {_substantiated_sort_option(filters.sort, "facility_desc", "Facility, Z to A")}
                </select>
              </p>
              <p>
                <label for="substantiated-page-size">Rows per page</label>
                <select id="substantiated-page-size" name="page_size">
                  {_substantiated_page_size_option(filters.page_size, 25)}
                  {_substantiated_page_size_option(filters.page_size, 50)}
                  {_substantiated_page_size_option(filters.page_size, 100)}
                </select>
              </p>
            </div>
            <div class="form-actions">
              <button class="button" type="submit">Apply filters</button>
              <a class="button button-secondary" href="{REVIEWER_UI_SUBSTANTIATED_TRIAGE_PATH}">Clear filters</a>
            </div>
          </form>
        </section>"""


def _substantiated_filter_options(values: object) -> str:
    if not isinstance(values, list | tuple | set):
        values = tuple(values)  # type: ignore[arg-type]
    options = []
    seen: set[str] = set()
    for value in values:
        if not value or value == "unknown" or value == "Not available in loaded record":
            continue
        text = str(value)
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        options.append(text)
    return "".join(
        f'<option value="{_escape(value)}"></option>'
        for value in sorted(options, key=str.casefold)
    )


def _substantiated_sort_option(current: str, value: str, label: str) -> str:
    selected = ' selected="selected"' if current == value else ""
    return f'<option value="{_escape(value)}"{selected}>{_escape(label)}</option>'


def _substantiated_page_size_option(current: int, value: int) -> str:
    selected = ' selected="selected"' if current == value else ""
    return f'<option value="{value}"{selected}>{value}</option>'


def _render_substantiated_pagination(
    filters: SubstantiatedWorklistFilters,
    pagination: Mapping[str, int],
    result_count: int,
) -> str:
    if result_count <= filters.page_size:
        return ""
    page = pagination["page"]
    total_pages = pagination["total_pages"]
    links = []
    if page > 1:
        links.append(
            f'<a class="button button-secondary" href="{_escape(_substantiated_page_href(filters, page - 1))}">Previous page</a>'
        )
    if page < total_pages:
        links.append(
            f'<a class="button button-secondary" href="{_escape(_substantiated_page_href(filters, page + 1))}">Next page</a>'
        )
    return f"""          <nav class="form-actions" aria-label="Substantiated worklist pagination">
            {"".join(links)}
          </nav>"""


def _substantiated_page_href(
    filters: SubstantiatedWorklistFilters,
    page: int,
) -> str:
    query_values = {
        "start_date": filters.start_date or "",
        "end_date": filters.end_date or "",
        "facility": filters.facility,
        "facility_type": filters.facility_type,
        "geography": filters.geography,
        "finding": filters.finding,
        "sort": filters.sort,
        "page_size": str(filters.page_size),
        "page": str(page),
    }
    return f"{REVIEWER_UI_SUBSTANTIATED_TRIAGE_PATH}?{urlencode(query_values)}"


def _render_substantiated_triage_guidance_disclosure() -> str:
    return """        <details class=\"technical-details notice-card\">
          <summary>How to use this triage view</summary>
          <ul>
            <li>Start with records whose source-derived finding/resolution/status indicates substantiated or equivalent.</li>
            <li>Open the source report and reviewer detail before using a value in notes or packet preparation.</li>
            <li>Use the review queue when no currently loaded records match this triage view.</li>
          </ul>
        </details>"""


def _substantiated_source_link(item: Mapping[str, str]) -> str:
    source_url_href = item["source_url_href"]
    if not source_url_href:
        return "Original public report link not available for this loaded complaint."
    control_number = item["complaint_control_number"]
    suffix = (
        f" for {control_number}"
        if control_number and control_number != "unknown"
        else ""
    )
    return (
        f"<a href=\"{_escape(source_url_href)}\">Open original public report{_escape(suffix)}</a>"
    )


def _all_source_derived_records(
    context: ReviewerUiContext,
) -> list[Mapping[str, Any]]:
    status, result = _all_source_derived_records_response(context)
    if status != 200 or isinstance(result, bytes):
        return []
    return result


def _all_source_derived_records_response(
    context: ReviewerUiContext,
) -> tuple[int, list[Mapping[str, Any]] | bytes]:
    records: list[Mapping[str, Any]] = []
    offset = 0
    while True:
        source_status, _content_type, source_body = route_source_derived_api_response(
            (
                f"{SOURCE_DERIVED_API_PREFIX}?"
                f"{urlencode({'limit': str(_SOURCE_DERIVED_PAGE_LIMIT), 'offset': str(offset)})}"
            ),
            context.workflow_shell_context.source_derived_api_context,
        )
        if source_status != 200:
            return source_status, source_body
        source_payload = _json_object(source_body)
        page_records = _record_list(source_payload, "records")
        records.extend(page_records)
        if len(page_records) < _SOURCE_DERIVED_PAGE_LIMIT:
            break
        offset += _SOURCE_DERIVED_PAGE_LIMIT
    return 200, records


def _substantiated_source_records_response(
    context: ReviewerUiContext,
) -> tuple[int, list[Mapping[str, Any]] | bytes]:
    source_context = context.workflow_shell_context.source_derived_api_context
    try:
        records = list_authorized_source_derived_records_by_entity_types(
            source_context.connection,
            source_context.actor,
            scope=source_context.scope,
            entity_types=_SUBSTANTIATED_SOURCE_ENTITY_TYPES,
        )
    except HostedAuthenticationRequiredError as error:
        return 401, _source_derived_error_body("authentication_required", str(error))
    except HostedAccountDisabledError as error:
        return 403, _source_derived_error_body("account_disabled_or_revoked", str(error))
    except HostedRoleDeniedError as error:
        return 403, _source_derived_error_body("role_denied", str(error))
    except HostedScopeDeniedError as error:
        return 403, _source_derived_error_body("scope_denied", str(error))
    except ValueError as error:
        return 400, _source_derived_error_body("invalid_request", str(error))
    return 200, [_source_derived_read_payload(record) for record in records]


def _source_derived_error_body(code: str, message: str) -> bytes:
    return json.dumps(
        {"error": {"code": code, "message": message}},
        sort_keys=True,
    ).encode("utf-8")


def _source_derived_read_payload(record: SourceDerivedRecordRead) -> dict[str, Any]:
    return {
        "source_record_key": record.source_record_key,
        "entity_type": record.entity_type,
        "stable_source_id": record.stable_source_id,
        "source_document_id": record.source_document_id,
        "facility_id": record.facility_id,
        "source_url": record.source_url,
        "raw_sha256": record.raw_sha256,
        "raw_path": record.raw_path,
        "connector_name": record.connector_name,
        "connector_version": record.connector_version,
        "retrieved_at": record.retrieved_at,
        "original_values": dict(record.original_values),
        "source_traceability": dict(record.source_traceability),
        "import_batch": {
            "import_batch_id": record.import_batch.import_batch_id,
            "imported_at": record.import_batch.imported_at,
            "source_artifact_identity": record.import_batch.source_artifact_identity,
            "source_pipeline_version": record.import_batch.source_pipeline_version,
            "validation_status": record.import_batch.validation_status,
            "raw_hash_validation_status": (
                record.import_batch.raw_hash_validation_status
            ),
            "record_counts": dict(record.import_batch.record_counts),
            "warnings": list(record.import_batch.warnings),
            "errors": list(record.import_batch.errors),
        },
    }


def _review_item_from_source_record(record: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "review_item_id": f"source-derived-review-shell:{_string(record, 'source_record_key')}",
        "source_record": {
            "identity": {
                "source_record_key": _string(record, "source_record_key"),
                "entity_type": _string(record, "entity_type"),
                "stable_source_id": _string(record, "stable_source_id"),
                "facility_id": _optional_string(record, "facility_id"),
            },
            "source_document": {
                "source_document_id": _string(record, "source_document_id"),
                "source_url": _optional_string(record, "source_url"),
                "raw_sha256": _optional_string(record, "raw_sha256"),
                "raw_path": _optional_string(record, "raw_path"),
                "connector_name": _optional_string(record, "connector_name"),
                "connector_version": _optional_string(record, "connector_version"),
                "retrieved_at": _optional_string(record, "retrieved_at"),
            },
            "original_values": _mapping(record, "original_values"),
            "source_traceability": _mapping(record, "source_traceability"),
            "import_batch": _mapping(record, "import_batch"),
        },
    }


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
    original_values = _mapping(source_record, "original_values")
    source_document = _mapping(source_record, "source_document")
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
    related_status, related_result = _substantiated_source_records_response(context)
    if related_status != 200:
        if not isinstance(related_result, bytes):
            raise ValueError("Expected source-derived error body to be bytes.")
        return _workflow_error_page(related_status, related_result)
    if isinstance(related_result, bytes):
        raise ValueError("Expected source-derived records.")
    related_records = related_result
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
        "review_guidance",
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


def _matrix_review_guidance_text() -> str:
    return (
        "complaint review matrix; CSV export; Excel-ready; open source links and reviewer detail "
        "before relying on source-derived values; complaint records are requested/reviewed separately"
    )


def _empty_matrix_row(return_context: CcldQueueReturnContext) -> dict[str, str]:
    return {
        key: ""
        for key in _matrix_fieldnames()
    } | {
        "matrix_status": "No loaded complaint records matched this facility/date context.",
        "review_guidance": _matrix_review_guidance_text(),
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
        "matrix_status": "loaded complaint record",
        "review_guidance": _matrix_review_guidance_text(),
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
        cues.append(f"missing traceability values: {missing_traceability}")
    return "; ".join(cues) if cues else "none visible from loaded fields"


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
                        <p class="launch-kicker">Preparation draft for browser copy or print</p>
                        <h2 id="packet-context-needed-heading">No facility/date packet context was supplied.</h2>
                    </div>
                    <p>Open this draft from a Request Records result, the packet preview, or a reviewer detail confirmation so the facility/date context can be carried into the draft for browser copy or print preparation.</p>
                    <p>Use a facility/date context so the draft can include the matching loaded complaint records, CCLD source cues, and reviewer-created status/note cues.</p>
                    <div class="form-actions packet-draft-actions">
                        <a class="button" href="{CCLD_RECORD_REQUEST_PATH}">Open Request Records</a>
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
    generated_at = _format_packet_generated_at(datetime.now(UTC))
    prioritized_record_context = _render_packet_prioritized_records_section(
        records,
        state_summaries,
        return_context,
        heading_level=3,
        section_id="draft-prioritized-records",
    )
    feedback_href = _feedback_href(
        workflow_area="packet-draft",
        page_path=REVIEWER_UI_PACKET_DRAFT_PATH,
        return_context=return_context,
        prompt="Describe browser copy or print preparation or packet readiness confusion.",
    )
    attorney_review_checklist = _render_attorney_review_readiness_checklist_section(
        records,
        state_summaries,
        return_context,
        heading_level=3,
        section_id="draft-attorney-review-readiness-checklist",
        feedback_href=feedback_href,
    )
    attorney_review_brief = _render_copy_ready_attorney_review_brief_section(
        records,
        state_summaries,
        return_context,
        heading_level=3,
        section_id="draft-attorney-review-brief",
    )
    record_sections = "\n".join(
        _render_packet_draft_record(record, state_summaries, return_context)
        for record in records
    )
    if not record_sections:
        record_sections = """        <section class="packet-draft-record" aria-labelledby="draft-no-records-heading">
                    <h3 id="draft-no-records-heading">No included complaint records</h3>
                    <p>No loaded complaint records match this packet draft context.</p>
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
                        <h2 id="packet-draft-title">Preparation draft for browser copy or print</h2>
                        <p><strong>Use browser copy or print only after review.</strong> This page keeps the intentional print/copy layout, but it does not generate a server-side PDF, Word file, ZIP, CSV, or downloadable final export.</p>
                    </header>
                    <details class="packet-draft-guidance">
                        <summary>Copy/print preparation guidance</summary>
                        <p>This preparation draft gathers the included complaint-record summaries, reviewer-attention counts, source-record cues, reviewer-created status/note cues, and a static copyable packet summary for manual browser copy or print.</p>
                        <p><strong>Packet readiness means review readiness only.</strong> The draft can be ready for manual review, browser copy, or browser print after the tester confirms the active facility/date context, included record count, important loaded record values, CCLD source-record access, reviewer-created status/note cues, and possible correction-readiness concerns.</p>
                        <p><strong>Review before copying or printing:</strong> check records flagged for reviewer attention, records missing reviewer-created status/note cues, important loaded record values, unavailable CCLD source links, and any wording that seems wrong, incomplete, confusing, or risky.</p>
                        <p>CCLD source available means a public CCLD source link is available to help check important loaded record values.</p>
                        <p><strong>Correction-readiness before copying or printing:</strong> if a loaded record value looks wrong or incomplete, open the CCLD source record if a date or source cue needs review and capture the possible correction concern in a reviewer-created note or feedback item for now. This draft does not change loaded records, alter loaded values, or submit correction decisions.</p>
                        <p>If copy/print preparation content seems wrong, incomplete, confusing, or risky, Send feedback before using this draft.</p>
                    </details>
                    <section aria-labelledby="draft-scope-heading">
                        <h3 id="draft-scope-heading">Packet scope</h3>
                        <dl class="summary-list">
                            <dt>Facility ID</dt>
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
                        <p><strong>Preparation checkpoint:</strong> Confirm the facility/date context, included records, CCLD source access, and reviewer-created status/note cues before browser copy or print.</p>
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
                            <dt>Records with CCLD source available</dt>
                            <dd>{traceability_counts['complete']}</dd>
                            <dt>Records ready for preparation review</dt>
                            <dd>{readiness_counts['ready']}</dd>
                            <dt>Records needing reviewer attention</dt>
                            <dd>{readiness_counts['needs_source_check']}</dd>
                            <dt>Records needing reviewer-created status/note attention</dt>
                            <dd>{readiness_counts['needs_reviewer_attention']}</dd>
                            <dt>Findings represented</dt>
                            <dd>{_escape(_packet_findings_text(findings))}</dd>
                        </dl>
                    </section>
                    <section aria-labelledby="draft-review-readiness-heading">
                        <h3 id="draft-review-readiness-heading">Review-readiness before copying or printing</h3>
                        <p>Review before copying or printing: this packet draft is a preparation draft.
                        Check date/source cues, review flags, and reviewer-created status/note cues
                        before relying on any loaded record value in a handoff.</p>
                        <p>Review before relying on this packet also means confirming the facility/date context and the included complaint records match the queue you intended to prepare. If the packet content looks incomplete, risky, or not ready, return to the queue, open reviewer detail, or send feedback before copying or printing.</p>
                        <p>Possible correction concerns should remain reviewer-created observations or
                        feedback items for now. The future correction workflow is not implemented here, and this
                        draft does not submit correction decisions.</p>
                        <ul>
                            <li>{readiness_counts['needs_source_check']} record(s) may still need reviewer attention based on visible review flags, missing dates, proxy cues, or unavailable CCLD source links.</li>
                            <li>{readiness_counts['needs_reviewer_attention']} record(s) may still need reviewer-created status/note attention before packet preparation.</li>
                            <li>{readiness_counts['ready']} record(s) have CCLD source access and at least one reviewer-created status/note cue.</li>
                        </ul>
                        <p>Return to the queue or reviewer detail when records still need reviewer attention or reviewer-created status/note attention.</p>
                    </section>
                    <section aria-labelledby="draft-source-heading">
                        <h3 id="draft-source-heading">CCLD source availability</h3>
                        <dl class="summary-list">
                            <dt>Source URL available</dt>
                            <dd>{traceability_counts['source_url']}</dd>
                            <dt>Additional source context available</dt>
                            <dd>{traceability_counts['raw_sha256']}</dd>
                            <dt>Loaded source context available</dt>
                            <dd>{traceability_counts['connector_retrieval']}</dd>
                            <dt>Records needing date/source review</dt>
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
                            <li>They do not change loaded complaint records.</li>
                            <li>They may point to possible correction concerns, but this draft does not alter loaded record values.</li>
                            <li>Reviewer-created note text is not printed here; use reviewer detail when note content needs review.</li>
                        </ul>
                    </section>
{prioritized_record_context}
{attorney_review_checklist}
{attorney_review_brief}
                    <section aria-labelledby="draft-next-review-heading">
                        <h3 id="draft-next-review-heading">Before using this draft</h3>
                        <ul>
                            <li>Confirm the facility/date context matches the queue you intended to prepare.</li>
                            <li>Open reviewer detail for records needing date/source cue review.</li>
                            <li>Resolve missing reviewer-created status/note attention when useful.</li>
                            <li>Send feedback before copying or printing when draft wording or readiness cues are confusing.</li>
                        </ul>
                    </section>
                    <section aria-labelledby="copyable-packet-summary-heading">
                        <h3 id="copyable-packet-summary-heading">Copyable packet summary</h3>
                        <p>Copy this plain text into a local note or review handoff draft when useful. The app does not save or send this text.</p>
                        <pre class="copyable-packet-summary">{_escape(copy_summary)}</pre>
                    </section>
                    <nav class="packet-draft-actions" aria-label="Packet draft navigation">
                        <ul>
                            <li><a href="{_escape(_packet_preview_href(return_context))}">Back to packet preview</a></li>
                            <li><a href="{_escape(_ccld_request_href([], return_context))}">Back to review queue</a></li>
                            <li><a href="{_escape(feedback_href)}">Report copy/print preparation concern</a></li>
                        </ul>
                    </nav>
                    <details class="technical-details">
                        <summary>Technical runtime details</summary>
                        {_render_scope_notice(workflow)}
                        <p>No export file is generated by this draft. Opening, printing, or copying this page does not mutate loaded records, reviewer-created state, audit rows, import batches, or operational metadata.</p>
                    </details>
                </article>
                """,
            )


def _format_packet_generated_at(value: datetime) -> str:
    central_value = value.astimezone(CENTRAL_TIME)
    month = central_value.strftime("%b")
    hour = central_value.hour % 12 or 12
    minute = f"{central_value.minute:02d}"
    am_pm = "AM" if central_value.hour < 12 else "PM"
    return (
        f"{month} {central_value.day}, {central_value.year}, "
        f"{hour}:{minute} {am_pm} CT"
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
                title="Select a complaint record",
                heading="Select a complaint record",
                message="Choose a loaded source-derived complaint record before opening reviewer detail.",
                guidance="Return to the reviewer list and open one of the complaint records.",
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
            missing_record_heading="Selected complaint record was not found",
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
                "Return to the detail page and choose one of the listed "
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
    import_batch = _mapping(source_record, "import_batch")
    source_status, records_or_body = _source_derived_records_for_import_batch(
        context,
        import_batch_id=_string(import_batch, "import_batch_id"),
    )
    if source_status != 200:
        if not isinstance(records_or_body, bytes):
            raise ValueError("Expected source-derived API error body to be bytes.")
        return source_status, records_or_body
    if isinstance(records_or_body, bytes):
        raise ValueError("Expected source-derived records.")
    related_records = _related_source_records(source_record, records_or_body)
    return 200, related_records


def _source_derived_records_for_import_batch(
    context: ReviewerUiContext,
    *,
    import_batch_id: str,
) -> tuple[int, list[Mapping[str, Any]] | bytes]:
    records: list[Mapping[str, Any]] = []
    limit = 100
    offset = 0
    while True:
        query = urlencode(
            {
                "limit": str(limit),
                "offset": str(offset),
                "import_batch_id": import_batch_id,
            }
        )
        source_status, _content_type, source_body = route_source_derived_api_response(
            f"{SOURCE_DERIVED_API_PREFIX}?{query}",
            context.workflow_shell_context.source_derived_api_context,
        )
        if source_status != 200:
            return source_status, source_body
        source_payload = _json_object(source_body)
        page_records = _record_list(source_payload, "records")
        records.extend(page_records)
        pagination = _mapping(source_payload, "pagination")
        returned_count = _int_value(pagination, "returned_count")
        if returned_count < limit:
            return 200, records
        offset += limit


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
    export_context: CcldQueueReturnContext,
    export_records: list[Mapping[str, Any]],
    *,
    actor_label: str | None,
) -> str:
    queue = _mapping(payload, "queue")
    returned_count = _int_value(_mapping(queue, "pagination"), "returned_count")
    suggested_item = _next_review_item(records, state_summaries)
    suggested_source_record_key = _source_record_key_for_item(suggested_item)
    rows = "\n".join(
        _render_review_item_row(record, state_summaries, export_context) for record in records
    )
    cards = "\n".join(
        _render_review_item_card(
            record,
            state_summaries,
            export_context,
            suggested=_source_record_key_for_item(record) == suggested_source_record_key,
        )
        for record in records
    )
    if not rows:
        rows = """        <tr>
                    <td colspan="9">No loaded complaint records match the
                    current search.</td>
        </tr>"""
        cards = """        <article class="empty-state-card result-card">
          <div>
            <h3>No matching complaint records</h3>
            <p>No loaded complaint records match the current search.</p>
          </div>
        </article>"""
        returned_count = _int_value(_mapping(queue, "pagination"), "returned_count")
    no_results_notice = _render_no_results_notice(search_query, records)
    return _page(
                title="Complaint records ready for review",
                heading="Complaint records ready for review",
        actor_label=actor_label,
        main=f"""
        {_render_reviewer_case_brief(records, state_summaries, export_records, export_context)}
                {no_results_notice}
        <section aria-labelledby="reviewer-list-heading">
                        <div class="dense-section-header">
                          <div>
                            <p class="stage-kicker">Review queue</p>
                            <h2 id="reviewer-list-heading">Worklist</h2>
                          </div>
                        </div>
                <div class="result-list dense-card-grid" aria-label="Complaint records ready for review">
        {cards}
                </div>
            {_render_queue_search_filter(records, search_query, state_summaries, returned_count, export_records)}
        <details class="technical-details dense-table-details">
          <summary>Show table view</summary>
      <table>
                                <caption>Complaint records ready for review with key dates and status cues</caption>
        <thead>
          <tr>
                        <th scope="col">Review action</th>
            <th scope="col">Complaint control number</th>
                        <th scope="col">Finding</th>
                        <th scope="col">Facility ID</th>
                        <th scope="col">Complaint received date</th>
                        <th scope="col">Visit date</th>
                        <th scope="col">Report date</th>
                        <th scope="col">Review status</th>
                        <th scope="col">Note</th>
                                                <th scope="col">Source</th>
          </tr>
        </thead>
        <tbody>
{rows}
        </tbody>
      </table>
            </details>
            {_render_queue_review_cue_summary(records, export_records)}
            {_render_complaint_export_controls(export_context, export_records)}
            {_DETAIL_COPY_SCRIPT}
    </section>""",
    )


def _source_record_key_for_item(item: Mapping[str, Any] | None) -> str | None:
    if item is None:
        return None
    source_record = _mapping(item, "source_record")
    identity = _mapping(source_record, "identity")
    return _string(identity, "source_record_key")


def _render_queue_search_filter(
    records: list[Mapping[str, Any]],
    search_query: str,
    state_summaries: Mapping[str, Mapping[str, Any]],
    returned_count: int,
    all_source_records: list[Mapping[str, Any]],
) -> str:
    suggestions = _queue_search_suggestions(records, state_summaries, all_source_records)
    suggestion_options = "\n".join(
        f'          <option value="{_escape(value)}"></option>' for value in suggestions
    )
    return f"""        <section class="quiet-section queue-search-section" aria-labelledby="queue-search-heading">
          <h2 id="queue-search-heading">Search records</h2>
          <form action="{REVIEWER_UI_RECORDS_PATH}" method="get" class="compact-search-form">
            <p>
              <label class="sr-only" for="q">Queue search</label>
              <input id="q" name="q" type="search" value="{_escape(search_query)}"
                list="queue-search-suggestions" aria-describedby="reviewer-search-help">
              <datalist id="queue-search-suggestions">
{suggestion_options}
              </datalist>
              <span id="reviewer-search-help">Search by complaint, facility, finding, status, or note state.</span>
            </p>
            <p class="form-actions">
              <button class="secondary" type="submit">Search</button>
              <a href="{REVIEWER_UI_RECORDS_PATH}">Clear</a>
            </p>
          </form>
          <p class="helper-text">Showing {len(records)} of {returned_count} records.</p>
        </section>"""


def _queue_search_suggestions(
    records: list[Mapping[str, Any]],
    state_summaries: Mapping[str, Mapping[str, Any]],
    all_source_records: list[Mapping[str, Any]],
) -> tuple[str, ...]:
    suggestions: set[str] = set()
    facility_names = _facility_names_by_number(all_source_records)
    for item in records:
        source_record = _mapping(item, "source_record")
        original_values = _mapping(source_record, "original_values")
        state_summary = _state_summary_for_item(item, state_summaries)
        facility_number = _complaint_export_row_facility_number(
            source_record,
            CcldQueueReturnContext(),
        )
        for value in (
            original_values.get("complaint_control_number"),
            facility_number,
            facility_names.get(facility_number),
            original_values.get("finding"),
            _latest_status_text(state_summary),
            _card_note_presence_text(state_summary),
        ):
            display = _display_value(value)
            if display and display != "unknown":
                suggestions.add(display)
    return tuple(sorted(suggestions, key=str.casefold))


def _facility_names_by_number(
    records: list[Mapping[str, Any]],
) -> dict[str, str]:
    names: dict[str, str] = {}
    for record in records:
        if _string(record, "entity_type") != "facility":
            continue
        values = _mapping(record, "original_values")
        facility_number = _optional_string(values, "external_facility_number")
        facility_name = _optional_string(values, "facility_name")
        if facility_number != "unknown" and facility_name != "unknown":
            names[facility_number] = facility_name
    return names


def _render_queue_review_cue_summary(
    records: list[Mapping[str, Any]],
    all_source_records: list[Mapping[str, Any]],
) -> str:
    cue_counts = _queue_review_cue_counts(records, all_source_records)
    cards = "\n".join(
        f"""            <div class="metric-card review-cue-card">
              <strong>{count}</strong><span>{_escape(label)}</span>
            </div>"""
        for label, count in cue_counts
        if count > 0
    )
    if not cards:
        return ""
    return f"""        <details class="technical-details dense-table-details queue-cue-summary">
          <summary id="queue-cue-summary-heading">Review cue summary</summary>
          <div class="metric-strip" aria-label="Review cue summary">
{cards}
          </div>
        </details>"""


def _queue_review_cue_counts(
    records: list[Mapping[str, Any]],
    all_source_records: list[Mapping[str, Any]],
) -> tuple[tuple[str, int], ...]:
    original_values = [
        _mapping(_mapping(item, "source_record"), "original_values")
        for item in records
    ]
    return (
        ("Possible delay", sum(1 for values in original_values if _delay_thresholds(values))),
        ("30+ day gap", sum(1 for values in original_values if values.get("review_delay_over_30_days") is True)),
        ("60+ day gap", sum(1 for values in original_values if values.get("review_delay_over_60_days") is True)),
        ("90+ day gap", sum(1 for values in original_values if values.get("review_delay_over_90_days") is True)),
        ("120+ day gap", sum(1 for values in original_values if values.get("review_delay_over_120_days") is True)),
        ("Missing first activity", sum(1 for values in original_values if _missing_first_activity_warning(values))),
        ("Missing source date", sum(1 for values in original_values if _has_missing_source_date(values))),
        ("Source unavailable", sum(1 for item in records if _source_unavailable_for_queue_item(item))),
        ("Priority cue", _serious_review_cue_record_count(all_source_records)),
    )


def _render_no_results_notice(
        search_query: str,
        records: list[Mapping[str, Any]],
) -> str:
        if records:
                return ""
        if search_query:
                return f"""<section aria-labelledby="no-results-heading">
            <h2 id="no-results-heading">No matching complaint records</h2>
            <p>No loaded complaint records match {_escape(search_query)}.</p>
            <p>Clear the search or return to the reviewer list to choose a complaint record.</p>
            <ul>
                <li><a href="{REVIEWER_UI_RECORDS_PATH}">Clear search</a></li>
                <li><a href="{REVIEWER_UI_PREFIX}">Return to reviewer home</a></li>
            </ul>
        </section>"""
        return f"""<section aria-labelledby="no-results-heading">
            <h2 id="no-results-heading">No complaint records are available</h2>
            <p>No loaded complaint records are available for this review queue.</p>
            <p>Return to Request Records or the reviewer home page to choose the next step.</p>
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
    all_source_records: list[Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
) -> str:
    case_records = tuple(
        _case_brief_record_from_review_item(
            index,
            record,
            state_summaries,
            all_source_records,
            return_context,
        )
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
            record_count_label="Records",
            flag_count_label="Flagged",
            source_available_label="Source available",
            reviewer_state_label="Notes/status saved",
            full_queue_href=REVIEWER_UI_RECORDS_PATH,
            packet_preview_href=REVIEWER_UI_PACKET_PREVIEW_PATH,
            packet_draft_href=_packet_draft_href_for_queue(case_records),
            show_priority_record=False,
            show_review_cue_summary=False,
            show_findings_summary=False,
        )
    )


def _render_packet_preview(
    records: list[Mapping[str, Any]],
    state_summaries: Mapping[str, Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
    *,
    actor_label: str | None,
) -> str:
    traceability_counts = _packet_traceability_counts(records)
    state_counts = _packet_reviewer_state_counts(records, state_summaries)
    readiness_counts = _packet_readiness_counts(records, state_summaries)
    date_range_row = ""
    if return_context.start_date is not None or return_context.end_date is not None:
        date_range_row = f"""
            <dt>Date range</dt>
            <dd>{_escape(_detail_return_context_date_range(return_context))}</dd>"""
    feedback_href = _feedback_href(
        workflow_area="packet-preview",
        page_path=REVIEWER_UI_PACKET_PREVIEW_PATH,
        return_context=return_context,
        prompt="Describe copy/print preparation, packet readiness, date/source cue, or status/note confusion.",
    )
    packet_readiness_checklist = _render_packet_preview_readiness_checklist_section(
        records,
        state_summaries,
        return_context,
        section_id="packet-attorney-review-readiness-checklist",
        feedback_href=feedback_href,
    )
    copy_ready_brief = _render_packet_preview_copy_ready_brief_section(
        records,
        state_summaries,
        return_context,
        section_id="packet-attorney-review-brief",
    )
    record_cards = "\n".join(
        _render_packet_preview_record(record, state_summaries, return_context)
        for record in records
    )
    if not record_cards:
        record_cards = """        <article class="empty-state-card result-card">
          <h3>No complaint records included</h3>
          <p>No loaded complaint records match this packet preview context.</p>
        </article>"""
    return _page(
                title="Packet preview",
                heading="Packet preview",
        actor_label=actor_label,
        main=f"""
        <section class="hero-card" aria-labelledby="packet-preview-heading">
          <p class="launch-kicker">Packet preparation</p>
                    <h2 id="packet-preview-heading">Packet preview</h2>
          <dl class="summary-list">
            <dt>Facility ID</dt>
            <dd>{_escape(_packet_facility_label(records, return_context))}</dd>
{date_range_row}
            <dt>Records included</dt>
            <dd>{len(records)}</dd>
            <dt>Review cues</dt>
            <dd>{_packet_review_cue_summary_text(records)}</dd>
            <dt>Notes/status saved</dt>
            <dd>{_packet_saved_notes_status_text(records, state_counts)}</dd>
            <dt>Source record</dt>
            <dd>{_packet_source_status_text(traceability_counts)}</dd>
                        <dt>Packet readiness</dt>
                        <dd>{_packet_readiness_summary_text(readiness_counts)}</dd>
          </dl>
                    <div class="form-actions">
                                                <a class="button" href="{_escape(_packet_draft_href(return_context))}">Open print draft</a>
                                                <a class="button button-secondary" href="{_escape(_ccld_request_href([], return_context))}">Back to review queue</a>
                                                <a class="button button-secondary" href="{_escape(feedback_href)}">Send feedback</a>
                    </div>
        </section>
        <section aria-labelledby="packet-records-heading">
          <h2 id="packet-records-heading">Included complaint records</h2>
          <div class="result-list" aria-label="Included complaint records">
{record_cards}
          </div>
        </section>
        <details class="technical-details dense-table-details">
          <summary>Readiness checks</summary>
                <section aria-labelledby="before-copying-printing-heading">
                    <h2 id="before-copying-printing-heading">Before copying or printing</h2>
                    <ul>
                        <li>Confirm this is the facility/date range you intended.</li>
                        <li>Open the CCLD source record if a date or source cue needs review.</li>
                        <li>Add status or a note if it would help the handoff.</li>
                        <li>Review included records for missing or confusing information.</li>
                        <li>Send feedback if something looks wrong or incomplete.</li>
                    </ul>
                </section>
                <section aria-labelledby="packet-readiness-heading">
                    <h2 id="packet-readiness-heading">Packet readiness summary</h2>
                    <dl class="summary-list">
                        <dt>Records included</dt>
                        <dd>{len(records)}</dd>
                        <dt>Records needing date/source review</dt>
                        <dd>{readiness_counts['needs_source_check']}</dd>
                        <dt>Records without saved status/note</dt>
                        <dd>{readiness_counts['needs_reviewer_attention']}</dd>
                        <dt>Ready for packet use</dt>
                        <dd>{_packet_ready_for_use_text(readiness_counts)}</dd>
                    </dl>
                </section>
        <section aria-labelledby="packet-source-availability-heading">
          <h2 id="packet-source-availability-heading">CCLD source availability</h2>
          <dl class="summary-list">
            <dt>Source available</dt>
            <dd>{traceability_counts['source_url']}</dd>
            <dt>Source unavailable</dt>
            <dd>{max(len(records) - traceability_counts['source_url'], 0)}</dd>
            <dt>Needs date/source review</dt>
            <dd>{readiness_counts['needs_source_check']}</dd>
          </dl>
        </section>
        <section aria-labelledby="packet-reviewer-state-heading">
          <h2 id="packet-reviewer-state-heading">Notes/status summary</h2>
          <dl class="summary-list">
            <dt>Saved status</dt>
            <dd>{state_counts['with_status']}</dd>
            <dt>Saved note</dt>
            <dd>{state_counts['with_notes']}</dd>
            <dt>No status</dt>
            <dd>{max(len(records) - state_counts['with_status'], 0)}</dd>
            <dt>No note</dt>
            <dd>{max(len(records) - state_counts['with_notes'], 0)}</dd>
          </dl>
        </section>
{packet_readiness_checklist}
        </details>
        <details class="technical-details dense-table-details copy-summary-details">
          <summary>Copy-ready brief</summary>
{copy_ready_brief}
        </details>
        <details class="technical-details dense-table-details">
          <summary>Packet notes</summary>
        <section aria-labelledby="packet-notes-heading">
          <h2 id="packet-notes-heading">Review packet notes</h2>
          <ul>
            <li>This packet preview is for preparation.</li>
            <li>Loaded record values remain separate from reviewer notes/status.</li>
            <li>Open the CCLD source record if a date or source cue needs review.</li>
            <li>Add notes/status only when useful.</li>
            <li>Send feedback if something looks wrong or incomplete.</li>
          </ul>
        </section>
        </details>
        """,
    )


def _packet_review_cue_summary_text(records: list[Mapping[str, Any]]) -> str:
    count = _packet_review_flag_count(records)
    suffix = "record needs review" if count == 1 else "records need review"
    return f"{count} {suffix}"


def _packet_saved_notes_status_text(
    records: list[Mapping[str, Any]],
    state_counts: Mapping[str, int],
) -> str:
    saved = len(records) - state_counts["without_state"]
    return f"{max(saved, 0)} saved"


def _packet_source_status_text(traceability_counts: Mapping[str, int]) -> str:
    count = traceability_counts["source_url"]
    suffix = "source available" if count == 1 else "sources available"
    return f"{count} {suffix}"


def _packet_readiness_summary_text(readiness_counts: Mapping[str, int]) -> str:
    items: list[str] = []
    if readiness_counts["needs_source_check"]:
        items.append("Needs date/source review")
    if readiness_counts["needs_reviewer_attention"]:
        items.append("needs reviewer status/note")
    if not items:
        return "Ready for packet use"
    return "; ".join(items)


def _packet_ready_for_use_text(readiness_counts: Mapping[str, int]) -> str:
    if readiness_counts["needs_source_check"] or readiness_counts["needs_reviewer_attention"]:
        return "Needs review"
    return "Ready"


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
    badge_items = "\n".join(
        f'              <li><span class="{_review_flag_chip_class(badge)}">{_escape(badge)}</span></li>'
        for badge in _packet_preview_record_badges(original_values, source_document, state_summary)
    )
    return f"""        <article class="result-card work-item packet-preview-record" aria-labelledby="packet-record-{_escape(source_record_key)}-heading">
          <div>
            <p class="stage-kicker">Included complaint record</p>
            <h3 id="packet-record-{_escape(source_record_key)}-heading">{_escape(label)}</h3>
            <ul class="flag-list" aria-label="Packet record cues">
{badge_items}
            </ul>
            <dl class="summary-list">
              <dt>Facility ID</dt>
              <dd>{_escape(_complaint_export_row_facility_number(source_record, return_context))}</dd>
              <dt>Complaint received</dt>
              <dd>{_escape(_detail_timeline_date(_optional_string(original_values, 'complaint_received_date')))}</dd>
              <dt>Visit</dt>
              <dd>{_escape(_detail_timeline_date(_optional_string(original_values, 'visit_date')))}</dd>
              <dt>Report</dt>
              <dd>{_escape(_detail_timeline_date(_optional_string(original_values, 'report_date')))}</dd>
              <dt>Signed</dt>
              <dd>{_escape(_detail_timeline_date(_optional_string(original_values, 'date_signed')))}</dd>
              <dt>Source</dt>
              <dd>{_escape(_source_availability_label(source_document))}</dd>
              <dt>Next step</dt>
              <dd>{_escape(_packet_record_next_step(item, state_summary))}</dd>
            </dl>
          </div>
          <div class="work-item-actions packet-record-actions" aria-label="Record actions">
            <a class="button" href="{_escape(detail_href)}">Open record { _escape(label) }</a>
          </div>
        </article>"""


def _packet_preview_record_badges(
    original_values: Mapping[str, Any],
    source_document: Mapping[str, Any],
    state_summary: Mapping[str, Any],
) -> tuple[str, ...]:
    badges: list[str] = []
    finding = _optional_string(original_values, "finding")
    if finding and finding != "unknown":
        badges.append(finding)
    badges.append(_latest_status_text(state_summary))
    badges.append(_card_note_presence_text(state_summary))
    badges.extend(_review_flag_labels(original_values))
    badges.append(_source_availability_label(source_document))
    return tuple(dict.fromkeys(badges))


def _packet_record_next_step(
    item: Mapping[str, Any],
    state_summary: Mapping[str, Any],
) -> str:
    steps: list[str] = []
    if _packet_needs_source_check(item):
        steps.append("Review dates and source link")
    if _packet_needs_reviewer_attention(state_summary):
        steps.append("add status/note if useful")
    if not steps:
        return "Ready for packet use."
    return "; ".join(steps) + "."


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
    source_cue = _packet_source_record_cue(source_document)
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
                <dd>{_packet_review_flags_markup(flags)}</dd>
                <dt>Reviewer-created status</dt>
                <dd>{_escape(_latest_status_label_text(state_summary))}</dd>
                <dt>Reviewer-created note presence</dt>
                <dd>{_escape(_card_note_presence_text(state_summary))}</dd>
                <dt>Why included</dt>
                <dd>{_escape(why)}</dd>
                <dt>CCLD source cue</dt>
                <dd>{_escape(source_cue)}</dd>
                                <dt>Reviewer attention cue</dt>
                                <dd>{_escape(readiness_cue)}</dd>
              </dl>
              <p class="packet-draft-actions"><a href="{_escape(detail_href)}">Open record { _escape(label) }</a></p>
            </section>"""


def _render_packet_prioritized_records_section(
    records: list[Mapping[str, Any]],
    state_summaries: Mapping[str, Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
    *,
    heading_level: int,
    section_id: str,
) -> str:
    heading_tag = f"h{heading_level}"
    prioritized = _packet_prioritized_case_records(
        records,
        state_summaries,
        return_context,
    )
    facility_hub_link = _packet_facility_hub_link(return_context)
    if not prioritized:
        return f"""                    <section aria-labelledby="{section_id}-heading">
                        <{heading_tag} id="{section_id}-heading">Prioritized records for review</{heading_tag}>
                        <p>No prioritized records are available from the loaded packet context.</p>
                        <p>Request records for this facility, review prioritized records first when they appear, or return to the queue when no loaded records are available in this context.</p>
                        <p><a href="{_escape(_ccld_request_href(records, return_context))}">Back to review queue</a>{facility_hub_link}</p>
                    </section>"""
    priority_items = "\n".join(
        _render_packet_prioritized_record_item(record, index)
        for index, record in enumerate(prioritized[:3], start=1)
    )
    return f"""                    <section aria-labelledby="{section_id}-heading">
                        <{heading_tag} id="{section_id}-heading">Prioritized records for review</{heading_tag}>
                        <p>This summary uses the existing review-next priority order for the loaded packet records. Reasons are loaded review cues and reviewer-created note/status cues only; they are not legal conclusions or source-completeness findings.</p>
                        <dl class="summary-list">
                            <dt>Prioritized records available</dt>
                            <dd>{len(prioritized)}</dd>
                            <dt>Shown first</dt>
                            <dd>{min(len(prioritized), 3)}</dd>
                        </dl>
                        <ol class="review-next-list">
{priority_items}
                        </ol>
                        <p>Use reviewer detail or the facility hub before copying or printing when a prioritized record needs date/source cue review, reviewer-created status/note attention, or possible correction-readiness review.</p>
                        <p><a href="{_escape(_ccld_request_href(records, return_context))}">Back to review queue</a>{facility_hub_link}</p>
                    </section>"""


def _render_packet_prioritized_record_item(
    record: FacilityCaseBriefRecord,
    index: int,
) -> str:
    reasons = _packet_priority_reason_labels(record)
    if not reasons:
        reasons = ("Part of the current loaded facility/date review queue.",)
    reason_items = "\n".join(
        f"                                <li>{_escape(reason)}</li>" for reason in reasons
    )
    return f"""                            <li class="review-next-item">
                                <p><strong>{index}. {_escape(display_record_label(record))}</strong></p>
                                <dl class="summary-list">
                                    <dt>Finding/status cue</dt>
                                    <dd>{_escape(_packet_prioritized_finding_status_text(record))}</dd>
                                    <dt>Date shown</dt>
                                    <dd>{_escape(_packet_prioritized_date_text(record))}</dd>
                                    <dt>Why prioritized</dt>
                                    <dd>
                                        <ul class="flag-list">
{reason_items}
                                        </ul>
                                    </dd>
                                </dl>
                                <p><a href="{_escape(record.detail_href)}">Open reviewer detail for {_escape(display_record_label(record))}</a></p>
                            </li>"""


def _render_packet_preview_readiness_checklist_section(
    records: list[Mapping[str, Any]],
    state_summaries: Mapping[str, Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
    *,
    section_id: str,
    feedback_href: str,
) -> str:
    traceability_counts = _packet_traceability_counts(records)
    readiness_counts = _packet_readiness_counts(records, state_summaries)
    review_cue_count = _packet_review_flag_count(records)
    status_note_needed = readiness_counts["needs_reviewer_attention"] > 0
    source_check_needed = readiness_counts["needs_source_check"] > 0
    checklist_rows = "\n".join(
        (
            _attorney_review_readiness_checklist_row(
                "Loaded records",
                "Ready" if records else "Needs review",
                f"{len(records)} complaint record(s) included.",
            ),
            _attorney_review_readiness_checklist_row(
                "Review cues",
                "Needs review" if review_cue_count else "Ready",
                _packet_review_cue_summary_text(records),
            ),
            _attorney_review_readiness_checklist_row(
                "Source record",
                "Ready" if traceability_counts["source_url"] == len(records) else "Needs review",
                _packet_source_status_text(traceability_counts),
            ),
            _attorney_review_readiness_checklist_row(
                "Saved status/note",
                "Needs review" if status_note_needed else "Ready",
                _packet_saved_notes_status_text(
                    records,
                    _packet_reviewer_state_counts(records, state_summaries),
                ),
            ),
            _attorney_review_readiness_checklist_row(
                "Follow-up notes",
                "Needs review" if status_note_needed else "Not applicable",
                "Add a note if it would help the handoff.",
            ),
            _attorney_review_readiness_checklist_row(
                "Date warnings",
                "Needs review" if source_check_needed else "Ready",
                "Open the CCLD source record if a date or source cue needs review.",
            ),
        )
    )
    return f"""                    <section aria-labelledby="{section_id}-heading">
                        <h2 id="{section_id}-heading">Packet readiness checklist</h2>
                        <table>
                            <caption>Packet readiness checklist for the current packet context</caption>
                            <thead>
                                <tr>
                                    <th scope="col">Checklist item</th>
                                    <th scope="col">Readiness</th>
                                    <th scope="col">Guidance</th>
                                </tr>
                            </thead>
                            <tbody>
{checklist_rows}
                            </tbody>
                        </table>
                        <p><a href="{_escape(_ccld_request_href(records, return_context))}">Back to review queue</a> or <a href="{_escape(_packet_level_feedback_href(feedback_href))}">send feedback</a>.</p>
                    </section>"""


def _render_packet_preview_copy_ready_brief_section(
    records: list[Mapping[str, Any]],
    state_summaries: Mapping[str, Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
    *,
    section_id: str,
) -> str:
    brief_text = _packet_preview_copy_ready_brief(records, state_summaries, return_context)
    return f"""                    <section aria-labelledby="{section_id}-heading">
                        <h2 id="{section_id}-heading">Copy-ready brief</h2>
                        <p>This plain-text brief is for manual copy into a review note or handoff draft. Review before use.</p>
                        <pre class="copyable-packet-summary attorney-review-brief">{_escape(brief_text)}</pre>
                    </section>"""


def _packet_preview_copy_ready_brief(
    records: list[Mapping[str, Any]],
    state_summaries: Mapping[str, Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
) -> str:
    readiness_counts = _packet_readiness_counts(records, state_summaries)
    lines = [
        "Packet preview brief",
        "",
        f"Facility ID: {_packet_facility_label(records, return_context)}",
        f"Date range: {_packet_draft_date_scope(return_context)}",
        f"Records included: {len(records)}",
        f"Packet readiness: {_packet_readiness_summary_text(readiness_counts)}",
        "",
        "Included records",
    ]
    if not records:
        lines.append("- No complaint records match this packet context.")
    for item in records:
        source_record = _mapping(item, "source_record")
        source_document = _mapping(source_record, "source_document")
        original_values = _mapping(source_record, "original_values")
        identity = _mapping(source_record, "identity")
        source_record_key = _string(identity, "source_record_key")
        state_summary = state_summaries.get(source_record_key, _empty_state_summary())
        label = _display_value(original_values.get("complaint_control_number") or source_record_key)
        lines.append(
            f"- {label}; finding: {_optional_string(original_values, 'finding')}; "
            f"dates: {_detail_date_summary(original_values)}; "
            f"status: {_latest_status_text(state_summary)}; "
            f"note: {_card_note_presence_text(state_summary)}; "
            f"source: {_source_availability_label(source_document)}"
        )
    lines.extend(
        [
            "",
            "Review before use",
            "- Review dates and source link when a date or timing cue needs review.",
            "- Add status or a note if it would help the handoff.",
            "- Send feedback if something looks wrong or incomplete.",
            "- This brief is a preparation aid, not a legal report or conclusion.",
        ]
    )
    return "\n".join(lines)


def _render_attorney_review_readiness_checklist_section(
    records: list[Mapping[str, Any]],
    state_summaries: Mapping[str, Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
    *,
    heading_level: int,
    section_id: str,
    feedback_href: str,
) -> str:
    heading_tag = f"h{heading_level}"
    traceability_counts = _packet_traceability_counts(records)
    readiness_counts = _packet_readiness_counts(records, state_summaries)
    prioritized = _packet_prioritized_case_records(
        records,
        state_summaries,
        return_context,
    )
    source_check_needed = readiness_counts["needs_source_check"] > 0
    reviewer_attention_needed = readiness_counts["needs_reviewer_attention"] > 0
    checklist_rows = "\n".join(
        (
            _attorney_review_readiness_checklist_row(
                "Loaded complaint records",
                "Ready" if records else "Not available in loaded context",
                (
                    f"{len(records)} loaded complaint record(s) match this "
                    "facility/date packet context."
                    if records
                    else "No loaded complaint records match this packet context."
                ),
            ),
            _attorney_review_readiness_checklist_row(
                "Prioritized records",
                "Ready" if prioritized else "Not available in loaded context",
                (
                    f"{len(prioritized)} prioritized record cue(s) are available "
                    "from the existing review-next ordering."
                    if prioritized
                    else "No prioritized record cues are available from the loaded context."
                ),
            ),
            _attorney_review_readiness_checklist_row(
                "Source record cues",
                _attorney_review_traceability_readiness_label(
                    records,
                    traceability_counts,
                ),
                (
                    "A CCLD source link or loaded source cue is available for checking."
                    if records and traceability_counts["missing_any"] == 0
                    else "Review unavailable CCLD source links before relying on important loaded record values."
                ),
            ),
            _attorney_review_readiness_checklist_row(
                "Reviewer-created note/status presence",
                _attorney_review_reviewer_state_readiness_label(
                    records,
                    reviewer_attention_needed,
                ),
                (
                    "Each included record has at least one reviewer-created status/note cue."
                    if records and not reviewer_attention_needed
                    else "Review records missing reviewer-created status or note cues when those cues would help the handoff."
                ),
            ),
            _attorney_review_readiness_checklist_row(
                "Follow-up questions",
                _attorney_review_follow_up_readiness_label(
                    records,
                    source_check_needed,
                    reviewer_attention_needed,
                ),
                "Use the suggested follow-up questions in the copy-ready brief below as review prompts before relying on this packet.",
            ),
        )
    )
    limited_notes = _attorney_review_limited_data_notes(
        records,
        prioritized,
        traceability_counts,
    )
    limited_note_items = "\n".join(
        f"                            <li>{_escape(note)}</li>" for note in limited_notes
    )
    limited_note_markup = (
        f"""                        <ul>
{limited_note_items}
                        </ul>"""
        if limited_notes
        else "<p>No limited-data warning is visible from the loaded checklist signals.</p>"
    )
    packet_feedback_href = _packet_level_feedback_href(feedback_href)
    return f"""                    <section aria-labelledby="{section_id}-heading">
                        <{heading_tag} id="{section_id}-heading">Attorney review readiness checklist</{heading_tag}>
                        <p>This compact checklist uses existing loaded context only. It is review readiness guidance for packet preparation, not a legal sufficiency decision, source-completeness proof, complaint-coverage finding, or facility-wide conclusion.</p>
                        <table>
                            <caption>Attorney review readiness checklist for the current packet context</caption>
                            <thead>
                                <tr>
                                    <th scope="col">Checklist signal</th>
                                    <th scope="col">Readiness</th>
                                    <th scope="col">Loaded-context guidance</th>
                                </tr>
                            </thead>
                            <tbody>
{checklist_rows}
                            </tbody>
                        </table>
                        <div class="helper-text">
                            <p><strong>Limited-data warnings</strong></p>
{limited_note_markup}
                        </div>
                        <p><a href="{_escape(_ccld_request_href(records, return_context))}">Back to review queue</a> or <a href="{_escape(packet_feedback_href)}">report packet readiness concern</a>.</p>
                    </section>"""


def _packet_level_feedback_href(feedback_href: str) -> str:
    parsed = urlparse(feedback_href)
    query_values = parse_qs(parsed.query, keep_blank_values=True)
    query_values.pop("source_record_key", None)
    query_values.pop("complaint_control_number", None)
    compact_values = {
        key: values[-1] if values else ""
        for key, values in query_values.items()
    }
    if not compact_values:
        return parsed.path
    return f"{parsed.path}?{urlencode(compact_values)}"


def _attorney_review_readiness_checklist_row(
    signal: str,
    readiness: str,
    guidance: str,
) -> str:
    return f"""                                <tr>
                                    <th scope="row">{_escape(signal)}</th>
                                    <td>{_escape(readiness)}</td>
                                    <td>{_escape(guidance)}</td>
                                </tr>"""


def _attorney_review_traceability_readiness_label(
    records: list[Mapping[str, Any]],
    traceability_counts: Mapping[str, int],
) -> str:
    if not records:
        return "Not available in loaded context"
    if traceability_counts["missing_any"] > 0:
        return "Needs review"
    return "Ready"


def _attorney_review_reviewer_state_readiness_label(
    records: list[Mapping[str, Any]],
    reviewer_attention_needed: bool,
) -> str:
    if not records:
        return "Not available in loaded context"
    if reviewer_attention_needed:
        return "Needs review"
    return "Ready"


def _attorney_review_follow_up_readiness_label(
    records: list[Mapping[str, Any]],
    source_check_needed: bool,
    reviewer_attention_needed: bool,
) -> str:
    if not records:
        return "Not available in loaded context"
    if source_check_needed or reviewer_attention_needed:
        return "Needs review"
    return "Ready"


def _attorney_review_limited_data_notes(
    records: list[Mapping[str, Any]],
    prioritized: tuple[FacilityCaseBriefRecord, ...],
    traceability_counts: Mapping[str, int],
) -> tuple[str, ...]:
    notes: list[str] = []
    if not records:
        notes.append(
            "Limited-data warning: no loaded complaint records match this packet context; request or load matching records before treating this as record-by-record review guidance."
        )
    if records and traceability_counts["missing_any"] > 0:
        notes.append(
            f"Limited-data warning: {traceability_counts['missing_any']} record(s) need date/source review; unavailable local source cues are not source-completeness proof."
        )
    if not prioritized:
        notes.append(
            "Limited-data warning: no prioritized record cues are available from the loaded context."
        )
    return tuple(notes)


def _render_copy_ready_attorney_review_brief_section(
    records: list[Mapping[str, Any]],
    state_summaries: Mapping[str, Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
    *,
    heading_level: int,
    section_id: str,
) -> str:
    heading_tag = f"h{heading_level}"
    brief_text = _copy_ready_attorney_review_brief(
        records,
        state_summaries,
        return_context,
    )
    return f"""                    <section aria-labelledby="{section_id}-heading">
                        <{heading_tag} id="{section_id}-heading">Copy-ready attorney review brief</{heading_tag}>
                        <p>This plain-text brief is for manual copy into an attorney review note or handoff draft. It uses the loaded facility/date context, prioritized records, packet readiness cues, CCLD source cues, and reviewer-created status/note presence already visible on this page.</p>
                        <p>It avoids raw source record keys, source document identifiers, import or audit details, internal diagnostics, legal conclusions, and source-completeness claims.</p>
                        <pre class="copyable-packet-summary attorney-review-brief">{_escape(brief_text)}</pre>
                    </section>"""


def _copy_ready_attorney_review_brief(
    records: list[Mapping[str, Any]],
    state_summaries: Mapping[str, Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
) -> str:
    traceability_counts = _packet_traceability_counts(records)
    state_counts = _packet_reviewer_state_counts(records, state_summaries)
    readiness_counts = _packet_readiness_counts(records, state_summaries)
    prioritized = _packet_prioritized_case_records(records, state_summaries, return_context)
    lines = [
        "Copy-ready attorney review brief",
        "",
        "Facility",
        f"- Facility ID: {_packet_facility_label(records, return_context)}",
        f"- Date range: {_packet_draft_date_scope(return_context)}",
        f"- Loaded record context: {len(records)} complaint record(s) in the current packet context.",
        "- Limited-data note: this brief reflects only records loaded in this current page context.",
        "",
        "Packet readiness cues",
        f"- Records ready for preparation review: {readiness_counts['ready']}",
        f"- Records needing reviewer attention: {readiness_counts['needs_source_check']}",
        "- Records needing reviewer-created status/note attention: "
        f"{readiness_counts['needs_reviewer_attention']}",
        f"- Records with reviewer-created status: {state_counts['with_status']}",
        f"- Records with reviewer-created notes: {state_counts['with_notes']}",
        "",
        "CCLD source cues",
        f"- Records with source URL available: {traceability_counts['source_url']}",
        f"- Records with additional source context available: {traceability_counts['raw_sha256']}",
        f"- Records with loaded source context available: {traceability_counts['connector_retrieval']}",
        f"- Records needing date/source review: {traceability_counts['missing_any']}",
        "- Unavailable local source cues are not source-completeness proof.",
        "",
        "Prioritized records",
    ]
    if not prioritized:
        lines.extend(
            [
                "- No prioritized records are available from the loaded packet context.",
                "- Limited-data note: request or load matching records before using this brief for record-by-record review.",
            ]
        )
    for index, record in enumerate(prioritized[:3], start=1):
        label = _attorney_brief_record_label(record, index)
        lines.append(f"- {index}. {label}")
        lines.append(f"  - Finding/status cue: {_packet_prioritized_finding_status_text(record)}")
        lines.append(f"  - Date context: {_packet_prioritized_date_text(record)}")
        lines.append(f"  - Source record cue: {_attorney_brief_traceability_text(record)}")
        lines.append(f"  - Reviewer-created cue: {_attorney_brief_reviewer_state_text(record)}")
        lines.append("  - Review reasons: " + _attorney_brief_reason_text(record))
    lines.extend(
        [
            "",
            "Suggested follow-up review questions",
            "- Does the facility/date context match the records intended for attorney review?",
            "- Which prioritized records need the CCLD source record checked before relying on dates, finding, or review flags?",
            "- Which records still need reviewer-created status or note attention before copy/print preparation?",
            "- Do any loaded record values appear confusing or incomplete enough to capture as a cautious reviewer-created note or feedback item?",
            "- Are any missing local values or proxy-date cues being described only as review cues, not conclusions?",
            "",
            "Boundaries",
            "- This brief is a preparation aid, not a legal report, certified export, source-completeness finding, or legal conclusion.",
            "- Loaded records are unchanged; reviewer-created status/note cues remain separate.",
        ]
    )
    return "\n".join(lines)


def _attorney_brief_record_label(record: FacilityCaseBriefRecord, index: int) -> str:
    if record.complaint_control_number:
        return record.complaint_control_number
    return f"Complaint record {index}"


def _attorney_brief_traceability_text(record: FacilityCaseBriefRecord) -> str:
    if record.has_source_traceability:
        return "CCLD source cue available on reviewer detail."
    return "CCLD source cue not visible in this loaded record."


def _attorney_brief_reviewer_state_text(record: FacilityCaseBriefRecord) -> str:
    status = record.reviewer_status_label or "No reviewer-created status"
    notes = (
        f"{record.reviewer_note_count} reviewer-created note(s)"
        if record.reviewer_note_count
        else "No reviewer-created notes"
    )
    return f"{status}; {notes}"


def _attorney_brief_reason_text(record: FacilityCaseBriefRecord) -> str:
    reasons = _packet_priority_reason_labels(record)
    if not reasons:
        return "No prioritized review reasons are visible from loaded context."
    return "; ".join(reasons)


def _packet_priority_reason_labels(record: FacilityCaseBriefRecord) -> tuple[str, ...]:
    labels: list[str] = []
    for reason in priority_reason_labels(record):
        labels.append(
            reason.replace("Needs " + "source check", "Needs date/source cue review")
            .replace("source-derived", "loaded")
            .replace("Source traceability", "CCLD source")
        )
    return tuple(labels)


def _packet_prioritized_case_records(
    records: list[Mapping[str, Any]],
    state_summaries: Mapping[str, Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
) -> tuple[FacilityCaseBriefRecord, ...]:
    case_records = tuple(
        _packet_case_brief_record(index, item, state_summaries, return_context)
        for index, item in enumerate(records)
    )
    return prioritized_records(case_records)


def _packet_case_brief_record(
    index: int,
    item: Mapping[str, Any],
    state_summaries: Mapping[str, Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
) -> FacilityCaseBriefRecord:
    source_record = _mapping(item, "source_record")
    identity = _mapping(source_record, "identity")
    source_document = _mapping(source_record, "source_document")
    original_values = _mapping(source_record, "original_values")
    source_record_key = _string(identity, "source_record_key")
    state_summary = state_summaries.get(source_record_key, _empty_state_summary())
    latest_status = _summary_optional_string(state_summary, "latest_status")
    facility_number = return_context.facility_number or _optional_string(
        original_values,
        "external_facility_number",
    )
    facility_name = return_context.lookup_facility_name or _optional_string(
        original_values,
        "facility_name",
    )
    return FacilityCaseBriefRecord(
        source_record_key=source_record_key,
        detail_href=_reviewer_detail_href(source_record_key, return_context),
        complaint_control_number=_packet_record_display_label(source_record),
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


def _packet_record_display_label(source_record: Mapping[str, Any]) -> str:
    original_values = _mapping(source_record, "original_values")
    label = _optional_string(original_values, "complaint_control_number")
    if label:
        return label
    return "Complaint record"


def _packet_prioritized_finding_status_text(record: FacilityCaseBriefRecord) -> str:
    finding = record.finding or "not listed"
    reviewer_status = record.reviewer_status_label or "No reviewer-created status"
    note_text = (
        f"{record.reviewer_note_count} reviewer-created note(s)"
        if record.reviewer_note_count
        else "No reviewer-created notes"
    )
    return f"Finding: {finding}; reviewer status: {reviewer_status}; {note_text}"


def _packet_prioritized_date_text(record: FacilityCaseBriefRecord) -> str:
    date_value = (
        record.complaint_received_date
        or record.report_date
        or record.visit_date
        or record.date_signed
    )
    if not date_value:
        return "No loaded date available"
    return f"Recent loaded activity date: {date_value}"


def _packet_facility_hub_link(return_context: CcldQueueReturnContext) -> str:
    if not return_context.facility_number:
        return ""
    query_values = {"facility_number": return_context.facility_number}
    return (
        f' or <a href="{_escape(CCLD_FACILITY_REVIEW_HUB_PATH)}?'
        f'{_escape(urlencode(query_values))}">open the facility hub</a>'
    )


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
        f"Facility ID: {_packet_facility_label(records, return_context)}",
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
        "- Packet readiness means review readiness for manual browser copy or print after checking facility/date context, included records, CCLD source access, reviewer-created status/note cues, and possible correction-readiness concerns.",
        f"- Records ready for preparation review: {readiness_counts['ready']}",
        f"- Records needing reviewer attention: {readiness_counts['needs_source_check']}",
        "- Records needing reviewer-created status/note attention: "
        f"{readiness_counts['needs_reviewer_attention']}",
        "- Review before copy/print; this is preparation only.",
        "",
        "CCLD source availability",
        f"- Source URL available: {traceability_counts['source_url']}",
        f"- Additional source context available: {traceability_counts['raw_sha256']}",
        f"- Loaded source context available: {traceability_counts['connector_retrieval']}",
        f"- Records needing date/source review: {traceability_counts['missing_any']}",
        "",
        "Prioritized records for review",
    ]
    prioritized = _packet_prioritized_case_records(records, state_summaries, return_context)
    if not prioritized:
        lines.append("- No prioritized records are available from this loaded packet context.")
    for index, record in enumerate(prioritized[:3], start=1):
        lines.append(
            f"- {index}. {display_record_label(record)}; "
            f"{_packet_prioritized_finding_status_text(record)}; "
            f"{_packet_prioritized_date_text(record)}; "
            "reasons: "
            + "; ".join(_packet_priority_reason_labels(record))
        )
    lines.extend(
        [
            "",
            "Included complaint records",
        ]
    )
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
            + f"; CCLD source cue: {_packet_source_record_cue(source_document)}"
        )
    lines.extend(
        [
            "",
            "Review guidance",
            "- Confirm facility/date context, included records, CCLD source access, and reviewer-created status/note cues before browser copy or print.",
            "- Loaded record values remain separate from reviewer notes/status.",
            "- Review flags identify records needing attorney review.",
            "- Open the CCLD source record from reviewer detail if a date or source cue needs review.",
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
            _mapping(_mapping(item, "source_record"), "original_values")
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
        cues.append("Needs reviewer attention before copy/print")
    else:
        cues.append("CCLD source available for preparation review")
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
    flags = _review_flag_labels(original_values)
    if not flags:
        return "No review flags are visible from loaded record values."
    return "; ".join(flags)


def _packet_review_flags_markup(flags: str) -> str:
    if flags == "No review flags are visible from loaded record values.":
        return _escape(flags)
    return " ".join(
        _review_chip_markup(flag.strip())
        for flag in flags.split(";")
        if flag.strip()
    )


def _latest_status_label_text(summary: Mapping[str, Any]) -> str:
    latest_status = _summary_optional_string(summary, "latest_status")
    if latest_status is None:
        return "No reviewer-created status"
    return _REVIEWER_STATUS_LABELS.get(latest_status, latest_status)


def _packet_draft_date_scope(return_context: CcldQueueReturnContext) -> str:
    if return_context.start_date or return_context.end_date:
        return _detail_return_context_date_range(return_context)
    return "All loaded records for this facility"


def _render_packet_preview_context_needed(*, actor_label: str | None) -> str:
        return _page(
                title="Packet preview",
                heading="Packet preview",
                actor_label=actor_label,
                main=f"""
                <section class="hero-card" aria-labelledby="packet-context-needed-heading">
                    <p class="launch-kicker">Preparation preview</p>
                    <h2 id="packet-context-needed-heading">No facility/date packet context was supplied.</h2>
                    <p>Start from Request Records or the Review queue to build a packet for a specific facility/date range.</p>
                    <div class="form-actions">
                        <a class="button" href="{CCLD_RECORD_REQUEST_PATH}">Open Request Records</a>
                        <a class="button button-secondary" href="{REVIEWER_UI_RECORDS_PATH}">Open Review queue</a>
                    </div>
                    <p>Supply a facility/date context to show included records and review-readiness cues for packet preparation.</p>
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
        reasons.append("No status yet.")
    if _summary_int(state_summary, "note_count") > 0:
        reasons.append("Reviewer note added.")
    if _review_flag_labels(original_values):
        if _has_delay_flag(original_values):
            reasons.append("Possible delay indicator.")
        if _has_missing_date_flag(original_values):
            reasons.append("Needs date/source cue review.")
        if original_values.get("report_date_used_as_proxy") is True:
            reasons.append("Report date proxy cue.")
    if _has_visible_traceability_document(source_document):
        reasons.append("CCLD source available.")
    else:
        reasons.append("Source not available; needs reviewer attention.")
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


def _serious_topics_href(return_context: CcldQueueReturnContext) -> str:
    if return_context.facility_number is None:
        return REVIEWER_UI_SERIOUS_TOPICS_PATH
    query_values = {
        "facility": return_context.facility_number,
        "start_date": return_context.start_date or "",
        "end_date": return_context.end_date or "",
    }
    return f"{REVIEWER_UI_SERIOUS_TOPICS_PATH}?{urlencode(query_values)}"


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


def _facility_substantiated_export_href(facility_number: str) -> str:
    query_values = {
        "facility": facility_number,
        "status": "substantiated",
    }
    return f"{REVIEWER_UI_SUBSTANTIATED_EXPORT_PATH}?{urlencode(query_values)}"


def _facility_all_complaints_export_href(facility_number: str) -> str:
    query_values = {
        "facility": facility_number,
        "status": "all",
    }
    return f"{REVIEWER_UI_SUBSTANTIATED_EXPORT_PATH}?{urlencode(query_values)}"


def _facility_serious_review_cue_export_href(facility_number: str) -> str:
    query_values = {
        "facility": facility_number,
        "status": "all",
        "review_cue": "serious",
    }
    return f"{REVIEWER_UI_SUBSTANTIATED_EXPORT_PATH}?{urlencode(query_values)}"


def _date_range_for_days_back(reference_date: datetime, days_back: int) -> tuple[str, str]:
    """Compute start_date and end_date for a date range N days back from reference_date.

    Args:
        reference_date: The end date (inclusive) for the range. Should be timezone-aware.
        days_back: Number of days to go back (inclusive). E.g., days_back=30 includes
                   the last 30 days ending on reference_date.

    Returns:
        Tuple of (start_date_str, end_date_str) in YYYY-MM-DD format.
    """
    from datetime import timedelta
    if reference_date.tzinfo is None:
        reference_date = reference_date.replace(tzinfo=UTC)
    end_date = reference_date.date()
    start_date = end_date - timedelta(days=days_back - 1)
    return (start_date.isoformat(), end_date.isoformat())


def _last_30_days_complaint_export_href(reference_date: datetime) -> str:
    start_date, end_date = _date_range_for_days_back(reference_date, 30)
    query_values = {
        "status": "all",
        "start_date": start_date,
        "end_date": end_date,
    }
    return f"{REVIEWER_UI_SUBSTANTIATED_EXPORT_PATH}?{urlencode(query_values)}"


def _last_90_days_complaint_export_href(reference_date: datetime) -> str:
    start_date, end_date = _date_range_for_days_back(reference_date, 90)
    query_values = {
        "status": "all",
        "start_date": start_date,
        "end_date": end_date,
    }
    return f"{REVIEWER_UI_SUBSTANTIATED_EXPORT_PATH}?{urlencode(query_values)}"


def _facility_last_30_days_complaint_export_href(facility_number: str, reference_date: datetime) -> str:
    start_date, end_date = _date_range_for_days_back(reference_date, 30)
    query_values = {
        "facility": facility_number,
        "status": "all",
        "start_date": start_date,
        "end_date": end_date,
    }
    return f"{REVIEWER_UI_SUBSTANTIATED_EXPORT_PATH}?{urlencode(query_values)}"


def _facility_last_90_days_complaint_export_href(facility_number: str, reference_date: datetime) -> str:
    start_date, end_date = _date_range_for_days_back(reference_date, 90)
    query_values = {
        "facility": facility_number,
        "status": "all",
        "start_date": start_date,
        "end_date": end_date,
    }
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
    return f'<a class="button button-secondary" href="{_escape(_packet_draft_href(return_context))}">Open print draft</a>'


def _case_brief_record_from_review_item(
    index: int,
    item: Mapping[str, Any],
    state_summaries: Mapping[str, Mapping[str, Any]],
    all_source_records: list[Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
) -> FacilityCaseBriefRecord:
    source_record = _mapping(item, "source_record")
    identity = _mapping(source_record, "identity")
    source_document = _mapping(source_record, "source_document")
    original_values = _mapping(source_record, "original_values")
    source_record_key = _string(identity, "source_record_key")
    state_summary = state_summaries.get(source_record_key, _empty_state_summary())
    latest_status = _summary_optional_string(state_summary, "latest_status")
    detail_href = _reviewer_detail_href(source_record_key, return_context)
    facility_number = _complaint_export_row_facility_number(
        source_record,
        CcldQueueReturnContext(),
    )
    facility_name = _optional_string(original_values, "facility_name")
    if facility_number == "unknown" or facility_name == "unknown":
        related_records = _related_source_records(source_record, all_source_records)
        facility = _facility_context(related_records)
        if facility_number == "unknown":
            facility_number = _facility_context_value(facility, "external_facility_number")
        if facility_name == "unknown":
            facility_name = _facility_context_value(facility, "facility_name")
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
    summary = _mapping(detail, "associated_reviewer_created_state_summary")
    status_text = _current_reviewer_status_text(summary)
    note_text = _detail_note_presence_text(summary)
    source_record_key = _string(_mapping(source_record, "identity"), "source_record_key")
    queue_href = _ccld_request_href(related_records, return_context)
    next_href = _next_priority_record_href(source_record_key, related_records, return_context)
    next_action = (
        f'<a class="button button-secondary" href="{_escape(next_href)}">Open next flagged record</a>'
        if next_href != queue_href
        else '<span class="button button-disabled" aria-disabled="true">Open next flagged record</span>'
    )
    return f"""<section class="why-flagged-panel summary-card" aria-labelledby="why-flagged-heading">
      <h2 id="why-flagged-heading">Why this record may need closer review</h2>
      <p>Review the badge list above as screening cues only. This page does not turn those cues into legal conclusions, source-completeness claims, or facility-wide findings.</p>
      <dl class="summary-list">
        <dt>Reviewer status</dt>
        <dd>{_escape(status_text)}</dd>
        <dt>Note state</dt>
        <dd>{_escape(note_text)}</dd>
      </dl>
      <div class="form-actions">
        <a class="button" href="{_escape(queue_href)}">Return to facility queue</a>
        {next_action}
      </div>
    </section>"""


def _detail_flag_reason_items(
    source_record: Mapping[str, Any],
    detail: Mapping[str, Any],
    related_records: list[Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
) -> tuple[str, ...]:
    record = _case_brief_record_from_detail(source_record, detail, related_records, return_context)
    original_values = _mapping(source_record, "original_values")
    source_document = _mapping(source_record, "source_document")
    summary = _mapping(detail, "associated_reviewer_created_state_summary")
    items: list[str] = []
    if record.delay_thresholds:
        items.append(
            f"Complaint/report timing needs date/source review: over {max(record.delay_thresholds)} days between loaded date fields."
        )
    if record.report_date_used_as_proxy:
        items.append("Report date used as proxy; verify against the source record before using timing language.")
    if record.missing_first_activity_date:
        items.append("First investigation activity date absent in loaded record; do not treat that as source absence.")
    if record.missing_visit_date:
        items.append("Visit date absent in loaded record; verify against the source record before relying on timing.")
    items.extend(_citation_poc_cues(original_values, related_records))
    if _current_reviewer_status_text(summary) == "No reviewer-created status":
        items.append("No reviewer-created status recorded yet.")
    if _has_visible_traceability_document(source_document):
        items.append("Source link available for checking the original CCLD record.")
    if not items:
        items.append("No review flags are visible from loaded record values.")
    return tuple(items[:7])


def _render_detail_page_actions(
    source_record: Mapping[str, Any],
    related_records: list[Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
) -> str:
    identity = _mapping(source_record, "identity")
    source_record_key = _string(identity, "source_record_key")
    queue_href = _ccld_request_href(related_records, return_context)
    next_href = _next_priority_record_href(source_record_key, related_records, return_context)
    return_label = (
        "Return to facility queue"
        if _has_explicit_facility_queue_context(return_context)
        else "Return to review queue"
    )
    next_action = (
        f'<a class="button button-secondary" href="{_escape(next_href)}">Open next flagged record</a>'
        if next_href != queue_href
        else '<span class="button button-disabled" aria-disabled="true">Open next flagged record</span>'
    )
    return f"""<section class="detail-card detail-page-actions" aria-labelledby="detail-page-actions-heading">
        <h2 id="detail-page-actions-heading">Actions</h2>
        <div class="reviewer-primary-actions" aria-label="Review navigation actions">
            <a class="button" href="{_escape(queue_href)}">{_escape(return_label)}</a>
            {next_action}
        </div>
    </section>"""


def _has_explicit_facility_queue_context(return_context: CcldQueueReturnContext) -> bool:
    return (
        return_context.facility_number is not None
        and (return_context.start_date is not None or return_context.end_date is not None)
    )


def _render_detail_review_flags_section(original_values: Mapping[str, Any]) -> str:
    flags = _review_flag_labels(original_values)
    if not flags:
        return """<section class="detail-card" aria-labelledby="detail-review-flags-heading">
      <h2 id="detail-review-flags-heading">Review flags</h2>
      <p>No review flags are visible from loaded fields.</p>
    </section>"""
    items = "\n".join(
        f'        <li><span class="{_review_flag_chip_class(label)}">{_escape(label)}</span></li>'
        for label in flags
    )
    return f"""<section class="detail-card" aria-labelledby="detail-review-flags-heading">
      <h2 id="detail-review-flags-heading">Review flags</h2>
      <ul class="flag-list" aria-label="Review flags">
{items}
      </ul>
    </section>"""


def _render_quick_review_cards(
    source_record: Mapping[str, Any],
    detail: Mapping[str, Any],
    related_records: list[Mapping[str, Any]],
    *,
    heading_level: int = 2,
) -> str:
    original_values = _mapping(source_record, "original_values")
    source_document = _mapping(source_record, "source_document")
    summary = _mapping(detail, "associated_reviewer_created_state_summary")
    cards = (
        (
            "Finding",
            _optional_string(original_values, "finding"),
            "View allegations and findings",
            "#allegations-findings-heading",
        ),
        (
            "Timing",
            _quick_timing_value(original_values),
            "View investigation timeline",
            "#complaint-timeline-heading",
        ),
        (
            "Review flags",
            _quick_review_flag_value(original_values),
            "Review why it may need closer review",
            "#why-flagged-heading",
        ),
        (
            "Citation / POC",
            _citation_poc_card_value(original_values, related_records),
            "View citation and POC",
            "#citation-poc-heading",
        ),
        (
            "Source",
            _quick_source_value(source_document),
            "Open source details",
            "#traceability-heading",
        ),
        (
            "Reviewer status",
            _current_reviewer_status_text(summary),
            "Update status or notes",
            "#review-actions-heading",
        ),
    )
    card_markup = "\n".join(
        f"""        <a class="quick-review-card" href="{href}">
          <span class="stage-kicker">{_escape(label)}</span>
          <strong>{_escape(value)}</strong>
          <span>{_escape(action)}</span>
        </a>"""
        for label, value, action, href in cards
    )
    heading_tag = f"h{heading_level}"
    return f"""<section class="quick-review-section" aria-labelledby="quick-review-heading">
      <{heading_tag} id="quick-review-heading">Quick review summary</{heading_tag}>
      <div class="quick-review-grid">
{card_markup}
      </div>
    </section>"""


def _render_top_facility_fact_strip(
    related_records: list[Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
) -> str:
    facility = _facility_context(related_records)
    facility_number = (
        return_context.facility_number
        if return_context.facility_number
        else _facility_context_value(facility, "external_facility_number")
    )
    facts = (
        (
            "license",
            _glossary_term(
                "Facility ID",
                "The public licensing identifier used to find the facility in CCLD records.",
                "detail-facility-id",
            ),
            "Facility ID",
            facility_number,
        ),
        ("name", "Facility name", "Facility name", _facility_context_value(facility, "facility_name")),
        ("type", "Facility type", "Facility type", _facility_context_value(facility, "facility_type")),
        ("status", "Status", "Facility status", _facility_context_value(facility, "license_status")),
        ("county", "County", "County", _facility_context_value(facility, "county")),
    )
    items = "\n".join(
        f"""        <div class="compact-fact compact-fact--{fact_key}">
          <dt>{label}</dt>
          <dd>{_copyable_value(copy_label, value)}</dd>
        </div>"""
        for fact_key, label, copy_label, value in facts
    )
    return f"""      <dl class="top-fact-strip" aria-label="Facility identity facts">
{items}
      </dl>"""


def _copyable_value(label: str, value: str) -> str:
    if not value or value == "unknown":
        return _escape(value or "unknown")
    if label not in {"Complaint/control number", "Facility ID"}:
        return _escape(value)
    accessible_label = _copy_button_label(label)
    return (
        f'<span class="copyable-value">{_escape(value)}'
        f'{_copy_icon_button(accessible_label, value)}</span>'
    )


def _copy_icon_button(accessible_label: str, value: str) -> str:
    return (
        f'<button class="copy-icon-button" type="button" '
        f'data-copy-value="{_escape(value)}" '
        f'data-copy-feedback="Copied" '
        f'aria-label="{_escape(accessible_label)}" title="{_escape(accessible_label)}">'
        f'{_clipboard_icon_svg()}</button>'
        '<span class="copy-feedback" data-copy-status hidden '
        'aria-live="polite" aria-atomic="true"></span>'
    )


def _copy_button_label(label: str) -> str:
    if label == "Complaint/control number":
        return "Copy complaint/control number"
    if label == "Facility ID":
        return "Copy Facility ID"
    return f"Copy {label}"


def _clipboard_icon_svg() -> str:
    return (
        '<svg aria-hidden="true" viewBox="0 0 24 24" focusable="false" '
        'width="16" height="16">'
        '<path fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round" '
        'd="M8 8h9a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2v-9a2 2 0 0 1 2-2Z"/>'
        '<path fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round" '
        'd="M4 15H3a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>'
        "</svg>"
    )


_DETAIL_COPY_SCRIPT = """<script>
function ensureCopyStatus(button) {
  var status = button.nextElementSibling;
  if (!status || !status.hasAttribute('data-copy-status')) {
    status = document.createElement('span');
    status.className = 'copy-feedback';
    status.setAttribute('data-copy-status', '');
    status.setAttribute('aria-live', 'polite');
    status.setAttribute('aria-atomic', 'true');
    status.hidden = true;
    button.insertAdjacentElement('afterend', status);
  }
  return status;
}
function showCopyStatus(button, message) {
  var status = ensureCopyStatus(button);
  window.clearTimeout(button._copyStatusTimer);
  button.setAttribute('data-copy-feedback', message);
  status.textContent = message;
  status.hidden = false;
  button._copyStatusTimer = window.setTimeout(function () {
    status.hidden = true;
    status.textContent = '';
    button.removeAttribute('data-copy-state');
  }, 1700);
}
document.querySelectorAll('[data-copy-value]').forEach(function (button) {
  button.addEventListener('click', function () {
    var value = button.getAttribute('data-copy-value') || '';
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(value).then(function () {
        button.setAttribute('data-copy-state', 'copied');
        showCopyStatus(button, 'Copied');
      }).catch(function () {
        button.setAttribute('data-copy-state', 'unavailable');
        showCopyStatus(button, 'Copy unavailable');
      });
    }
  });
});
</script>"""


def _quick_timing_value(original_values: Mapping[str, Any]) -> str:
    report_date = _optional_string(original_values, "report_date")
    if report_date != "unknown":
        return report_date
    return _optional_string(original_values, "complaint_received_date")


def _quick_review_flag_value(original_values: Mapping[str, Any]) -> str:
    thresholds = _delay_thresholds(original_values)
    if thresholds:
        return f"Over {max(thresholds)} days"
    if original_values.get("missing_first_activity_date") is True:
        return "Needs date/source review"
    if original_values.get("report_date_used_as_proxy") is True:
        return "Proxy date"
    return "No visible flags"


def _quick_source_value(source_document: Mapping[str, Any]) -> str:
    if _has_visible_traceability_document(source_document):
        return "Traceability available"
    return "Limited traceability"


def _citation_poc_card_value(
    original_values: Mapping[str, Any],
    related_records: list[Mapping[str, Any]],
) -> str:
    cues = _citation_poc_cues(original_values, related_records)
    if not cues:
        return "Not loaded"
    return cues[0].split(";", 1)[0]


def _citation_poc_cues(
    original_values: Mapping[str, Any],
    related_records: list[Mapping[str, Any]],
) -> tuple[str, ...]:
    values = [original_values]
    values.extend(_mapping(record, "original_values") for record in related_records)
    text_parts: list[str] = []
    for value_map in values:
        for key, value in value_map.items():
            if not _has_display_value(value):
                continue
            key_norm = key.casefold().replace("_", " ")
            value_norm = _display_value(value).casefold()
            text_parts.append(f"{key_norm}: {value_norm}")
    joined = " | ".join(text_parts)
    cues: list[str] = []
    if "typea" in joined or "type a" in joined or "a citation" in joined:
        cues.append("Type A citation cue loaded; verify wording in the source record.")
    elif "citation" in joined or "deficien" in joined:
        cues.append("Citation or deficiency cue loaded; verify wording in the source record.")
    if "typeb" in joined or "type b" in joined or "b citation" in joined:
        cues.append("Type B citation cue loaded; verify wording in the source record.")
    if "poc" in joined or "plan of correction" in joined:
        if "completion" not in joined and "completed" not in joined:
            cues.append("POC received cue loaded; completion status not available in loaded record.")
        else:
            cues.append("POC cue loaded; verify completion wording in the source record.")
    return tuple(dict.fromkeys(cues))


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
    return_context: CcldQueueReturnContext,
) -> str:
    source_record = _mapping(item, "source_record")
    identity = _mapping(source_record, "identity")
    source_document = _mapping(source_record, "source_document")
    original_values = _mapping(source_record, "original_values")
    source_record_key = _string(identity, "source_record_key")
    detail_href = _reviewer_detail_href(source_record_key, return_context)
    state_summary = state_summaries.get(source_record_key, _empty_state_summary())
    action_label = _review_action_label(original_values)
    return f"""        <tr>
                        <td><a class="button" href="{_escape(detail_href)}">{_escape(action_label)}</a></td>
          <td>{_escape(_optional_string(original_values, 'complaint_control_number'))}</td>
          <td>{_escape(_optional_string(original_values, 'finding'))}</td>
                    <td>{_escape(_complaint_export_row_facility_number(source_record, return_context))}</td>
                    <td>{_escape(_queue_display_date(_optional_string(original_values, 'complaint_received_date')))}</td>
                    <td>{_escape(_queue_display_date(_optional_string(original_values, 'visit_date')))}</td>
                    <td>{_escape(_queue_display_date(_optional_string(original_values, 'report_date')))}</td>
          <td>{_escape(_latest_status_text(state_summary))}</td>
                    <td>{_escape(_notes_indicator_text(state_summary))}</td>
                    <td>{_escape(_source_availability_label(source_document))}</td>
        </tr>"""


def _render_review_item_card(
        item: Mapping[str, Any],
        state_summaries: Mapping[str, Mapping[str, Any]],
        return_context: CcldQueueReturnContext,
        *,
        suggested: bool = False,
) -> str:
        source_record = _mapping(item, "source_record")
        identity = _mapping(source_record, "identity")
        source_document = _mapping(source_record, "source_document")
        original_values = _mapping(source_record, "original_values")
        source_record_key = _string(identity, "source_record_key")
        detail_href = _reviewer_detail_href(source_record_key, return_context)
        state_summary = state_summaries.get(source_record_key, _empty_state_summary())
        control_number = _display_value(original_values.get("complaint_control_number") or source_record_key)
        facility_number = _complaint_export_row_facility_number(source_record, return_context)
        finding = _optional_string(original_values, "finding")
        reviewer_status_text = _latest_status_text(state_summary)
        note_presence_text = _card_note_presence_text(state_summary)
        suggested_label = '<p class="stage-kicker">Suggested</p>' if suggested else ""
        packet_actions = ""
        if suggested:
            packet_actions = f"""
                            <a class="button button-secondary" href="{_escape(_packet_preview_href(return_context))}">Open packet preview</a>
                            <a class="button button-quiet" href="{_escape(_packet_draft_href(return_context))}">Open print draft</a>"""
        card_class = "result-card work-item is-suggested" if suggested else "result-card work-item"
        return f"""        <article class="{card_class}" aria-labelledby="record-{_escape(source_record_key)}-heading">
                    <div class="work-item-main">
                        {suggested_label}
                        <h3 id="record-{_escape(source_record_key)}-heading">{_copyable_value("Complaint/control number", control_number)}</h3>
                        {_render_queue_record_badges(finding, reviewer_status_text, note_presence_text, original_values)}
                        <dl class="work-item-facts">
                          <div class="work-item-fact-pair" data-fact-pair="facility-id">
                            <dt>Facility ID</dt>
                            <dd>{_copyable_value("Facility ID", facility_number)}</dd>
                          </div>
                          <div class="work-item-fact-pair" data-fact-pair="complaint-received">
                            <dt>Complaint received</dt>
                            <dd>{_escape(_queue_display_date(_optional_string(original_values, 'complaint_received_date')))}</dd>
                          </div>
                          <div class="work-item-fact-pair" data-fact-pair="visit">
                            <dt>Visit</dt>
                            <dd>{_escape(_queue_display_date(_optional_string(original_values, 'visit_date')))}</dd>
                          </div>
                          <div class="work-item-fact-pair" data-fact-pair="report">
                            <dt>Report</dt>
                            <dd>{_escape(_queue_display_date(_optional_string(original_values, 'report_date')))}</dd>
                          </div>
                          <div class="work-item-fact-pair" data-fact-pair="signed">
                            <dt>Signed</dt>
                            <dd>{_escape(_queue_display_date(_optional_string(original_values, 'date_signed')))}</dd>
                          </div>
                        </dl>
                        <p class="work-item-source"><span class="review-chip source-chip">{_escape(_source_availability_label(source_document))}</span></p>
                    </div>
                    <div class="work-item-actions" aria-label="Record actions">
                        <a class="button" href="{_escape(detail_href)}">Open record</a>
{packet_actions}
                    </div>
                </article>"""


def _render_queue_record_badges(
    finding: str,
    reviewer_status_text: str,
    note_presence_text: str,
    original_values: Mapping[str, Any],
) -> str:
    labels = [finding, reviewer_status_text, note_presence_text]
    labels.extend(_review_flag_labels(original_values))
    badges = " ".join(
        _review_chip_markup(label)
        for label in labels
        if label and label != "unknown"
    )
    return f'<p class="queue-record-badges">{badges}</p>'


def _queue_display_date(value: str) -> str:
    return _detail_display_date(value)


def _card_note_presence_text(summary: Mapping[str, Any]) -> str:
        note_count = _summary_int(summary, "note_count")
        if note_count == 0:
                return "No note"
        return "Note added"


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
            "Original CCLD source link saved: "
            + ", ".join(available)
            + "."
        )
    if available:
        return (
            "Source record saved for checking: "
            + ", ".join(available)
            + ". Missing: "
            + ", ".join(missing)
            + "."
        )
    return (
        "No original source link is visible in this record. Missing: "
        + ", ".join(missing)
        + "."
    )


def _source_availability_label(source_document: Mapping[str, Any]) -> str:
    if _has_display_value(source_document.get("source_url")):
        return "CCLD source available"
    return "Source not available"


def _packet_source_record_cue(source_document: Mapping[str, Any]) -> str:
    if _has_display_value(source_document.get("source_url")):
        return "CCLD source record available."
    if _has_visible_traceability_document(source_document):
        return "Loaded source cue available; open reviewer detail for the CCLD source record when needed."
    return "CCLD source record not visible in this loaded record."


def _traceability_value_labels(source_document: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    fields = (
        ("source URL", source_document.get("source_url")),
        ("source checksum", source_document.get("raw_sha256")),
        ("source support reference", source_document.get("raw_path")),
        ("source support details", _connector_label(source_document)),
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
        return "none visible in this record"
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


def _has_missing_source_date(original_values: Mapping[str, Any]) -> bool:
    return any(
        original_values.get(field_name) is True
        for field_name in (
            "missing_visit_date",
            "missing_report_date",
            "missing_signed_date",
        )
    )


def _missing_first_activity_warning(original_values: Mapping[str, Any]) -> bool:
    return (
        original_values.get("missing_first_activity_date") is True
        and not _has_display_value(original_values.get("first_investigation_activity_date"))
        and not _has_display_value(original_values.get("visit_date"))
    )


def _source_unavailable_for_queue_item(item: Mapping[str, Any]) -> bool:
    source_record = _mapping(item, "source_record")
    source_document = _mapping(source_record, "source_document")
    return not _has_display_value(source_document.get("source_url"))


def _render_review_flag_chips(
    original_values: Mapping[str, Any],
    source_document: Mapping[str, Any],
) -> str:
    flags = _review_flag_labels(original_values)
    if not flags:
        return '<p class="sr-note">No review flags are visible from loaded record values.</p>'
    items = "\n".join(
        f'                            <li><span class="{_review_flag_chip_class(label)}">{_escape(label)}</span></li>'
        for label in flags
    )
    return f"""                        <p class="sr-note">Review flags</p>
                        <ul class="flag-list" aria-label="Review flags">
{items}
                        </ul>"""


def _review_flag_chip_class(label: str) -> str:
    if label in {
        "Source unavailable",
        "Missing source date",
        "Missing first activity",
        "Date mismatch",
        "Source narrative missing",
        "Source link unavailable",
    }:
        return "review-chip badge-danger"
    if label == "CCLD source available":
        return "review-chip source-chip"
    if label.endswith("day gap"):
        return "review-chip badge-attention badge-attention--warning"
    workflow_state_labels = (
        "No status",
        "No note",
        "Note added",
        *_REVIEWER_STATUS_LABELS.values(),
    )
    if label in workflow_state_labels:
        if label == "No note":
            return "review-chip badge-info badge-info--note"
        return "review-chip badge-info badge-info--status"
    return "review-chip"


def _review_chip_markup(label: str) -> str:
    marker_class = _review_chip_marker_class(label)
    marker = (
        f'<span class="{marker_class}" aria-hidden="true"></span>'
        if marker_class
        else ""
    )
    return f'<span class="{_review_flag_chip_class(label)}">{marker}{_escape(label)}</span>'


def _review_chip_marker_class(label: str) -> str:
    if label.strip().casefold() in {"substantiated", "unsubstantiated", "inconclusive"}:
        return "review-chip__marker review-chip__marker--finding"
    if label.endswith("day gap"):
        return "review-chip__marker review-chip__marker--warning"
    if label == "No note":
        return "review-chip__marker review-chip__marker--note"
    if label in {"No status", *_REVIEWER_STATUS_LABELS.values()}:
        return "review-chip__marker review-chip__marker--status"
    return ""


def _review_flag_labels(original_values: Mapping[str, Any]) -> tuple[str, ...]:
    flags: list[str] = []
    for field_name, label in (
        ("review_delay_over_120_days", "120+ day gap"),
        ("review_delay_over_90_days", "90+ day gap"),
        ("review_delay_over_60_days", "60+ day gap"),
        ("review_delay_over_30_days", "30+ day gap"),
    ):
        if original_values.get(field_name) is True:
            flags.append(label)
            break
    return tuple(flags)


def _source_warning_labels(
    source_record: Mapping[str, Any],
    related_records: list[Mapping[str, Any]],
) -> tuple[str, ...]:
    original_values = _mapping(source_record, "original_values")
    source_document = _mapping(source_record, "source_document")
    warnings: list[str] = []
    if not _has_visible_traceability_document(source_document):
        warnings.append("Source unavailable")
    if not _has_display_value(source_document.get("source_url")):
        warnings.append("Source link unavailable")
    if _missing_first_activity_warning(original_values):
        warnings.append("Missing first activity")
    if (
        original_values.get("missing_visit_date") is True
        or original_values.get("missing_report_date") is True
        or not _has_display_value(original_values.get("visit_date"))
        or not _has_display_value(original_values.get("report_date"))
    ):
        warnings.append("Missing source date")
    if original_values.get("report_date_used_as_proxy") is True:
        warnings.append("Date mismatch")
    if not _source_narrative_text(source_record, related_records):
        warnings.append("Source narrative missing")
    return tuple(dict.fromkeys(warnings))


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
        return "No note"
    if note_count == 1:
        return "1 note"
    return f"{note_count} notes"


def _latest_status_text(summary: Mapping[str, Any]) -> str:
    latest_status = _summary_optional_string(summary, "latest_status")
    if latest_status is None:
        return "No status"
    return _REVIEWER_STATUS_LABELS.get(latest_status, latest_status)


def _latest_created_at_text(summary: Mapping[str, Any]) -> str:
    latest_created_at = _summary_optional_string(summary, "latest_created_at")
    if latest_created_at is None:
        return "Not saved"
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
    original_values = _mapping(source_record, "original_values")
    source_record_key = _string(identity, "source_record_key")
    complaint_heading = "Complaint overview"
    return _page(
        title=complaint_heading,
        heading=complaint_heading,
        actor_label=actor_label,
        main=f"""
    {_render_notice(saved_action, saved_value, source_record_key, related_records, return_context)}
        <div class="reviewer-detail-page detail-shell">
            {_render_detail_context_row(source_record, related_records, return_context)}
            {_render_detail_heading_context(original_values)}
            {_render_complaint_overview_card(source_record_key, source_record, detail, related_records, return_context)}
            {_render_allegations_findings_section(source_record, related_records)}
            {_render_citation_poc_section(source_record, related_records)}
            {_render_reviewer_state_section(detail)}
            {_DETAIL_COPY_SCRIPT}
        </div>""",
    )


def _render_detail_heading_context(original_values: Mapping[str, Any]) -> str:
    complaint_number = _optional_string(original_values, "complaint_control_number")
    finding = _optional_string(original_values, "finding")
    return (
        '<p class="detail-heading-context">'
        f"Complaint {_escape(complaint_number)} &middot; "
        f'{_glossary_term("Finding", "The outcome or status shown in the public complaint record.", "detail-finding")}: '
        f"{_finding_definition_term(finding)}"
        "</p>"
    )


def _render_complaint_overview_card(
    source_record_key: str,
    source_record: Mapping[str, Any],
    detail: Mapping[str, Any],
    related_records: list[Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
) -> str:
    original_values = _mapping(source_record, "original_values")
    source_document = _mapping(source_record, "source_document")
    finding = _optional_string(original_values, "finding")
    return f"""<section class="detail-card complaint-overview-card" aria-labelledby="complaint-overview-card-heading">
      <div class="overview-card-bar">
        <p class="launch-kicker">Complaint overview</p>
        {_source_availability_chip(source_document)}
      </div>
      <div class="overview-layout">
        <div class="overview-main">
          <div class="overview-primary-row">
            <div>
              <h2 id="complaint-overview-card-heading" class="complaint-number-heading"><span class="sr-only">Complaint/control number </span>{_copyable_value("Complaint/control number", _optional_string(original_values, "complaint_control_number"))}</h2>
              <p class="finding-context-line">{_glossary_term("Finding", "The outcome or status shown in the public complaint record.", "overview-finding")} {_finding_badge(finding)}</p>
            </div>
            <div class="overview-source-action">
              {_source_action_link(source_document)}
            </div>
          </div>
          {_render_top_facility_fact_strip(related_records, return_context)}
          {_render_overview_review_cues(source_record, detail, related_records)}
          {_render_overview_source_narrative(source_record, related_records)}
          {_render_overview_timeline(source_record)}
        </div>
        <div class="overview-side-panel">
          {_render_review_actions(source_record_key, detail, return_context)}
          {_render_detail_tertiary_actions(source_record, related_records, return_context)}
        </div>
      </div>
    </section>"""


def _source_availability_chip(source_document: Mapping[str, Any]) -> str:
    if _has_display_value(source_document.get("source_url")):
        return '<span class="review-chip source-chip">CCLD source available</span>'
    return ""


def _finding_definition_term(finding: str) -> str:
    normalized = finding.strip().casefold()
    definitions = {
        "unsubstantiated": "A source-reported finding that the allegation was not substantiated in the public complaint record.",
        "substantiated": "A source-reported finding that the allegation was substantiated in the public complaint record.",
        "inconclusive": "A source-reported finding that the public complaint record does not resolve the allegation as substantiated or unsubstantiated.",
    }
    definition = definitions.get(normalized)
    if definition is None:
        return _escape(finding)
    term_id = "finding-" + normalized.replace(" ", "-")
    return _glossary_term(finding, definition, term_id)


def _finding_badge(finding: str) -> str:
    marker = (
        f'<span class="finding-badge__marker finding-badge__marker--{_escape(_finding_badge_marker(finding))}" aria-hidden="true"></span>'
    )
    return (
        f'<span class="{_finding_badge_class(finding)}">'
        f"{marker}{_finding_definition_term(finding)}</span>"
    )


def _finding_badge_class(finding: str) -> str:
    normalized = finding.strip().casefold()
    if normalized == "substantiated":
        return "finding-badge finding-badge--substantiated finding-badge--status"
    if normalized == "inconclusive":
        return "finding-badge finding-badge--inconclusive finding-badge--status"
    if normalized == "unsubstantiated":
        return "finding-badge finding-badge--unsubstantiated finding-badge--status"
    return "finding-badge finding-badge--unknown finding-badge--status"


def _finding_badge_marker(finding: str) -> str:
    normalized = finding.strip().casefold()
    if normalized in {"substantiated", "inconclusive", "unsubstantiated"}:
        return normalized
    return "unknown"


def _render_overview_review_cues(
    source_record: Mapping[str, Any],
    detail: Mapping[str, Any],
    related_records: list[Mapping[str, Any]],
) -> str:
    original_values = _mapping(source_record, "original_values")
    summary = _mapping(detail, "associated_reviewer_created_state_summary")
    review_flags = list(_review_flag_labels(original_values))
    if _current_reviewer_status_text(summary) == "No status":
        review_flags.append("No status")
    if _detail_note_presence_text(summary) == "No note":
        review_flags.append("No note")
    review_items = _badge_list_markup(
        tuple(review_flags),
        aria_label="Review badges",
        empty_label="No active review badges",
    )
    source_warnings = _badge_list_markup(
        _source_warning_labels(source_record, related_records),
        aria_label="Specific source warnings",
        empty_label="No source warning badges",
        show_empty=False,
    )
    return f"""<section class="overview-review-cues" aria-labelledby="overview-review-cues-heading">
        <h3 id="overview-review-cues-heading">Why this may need closer review</h3>
        {review_items}
        {source_warnings}
      </section>"""


def _badge_list_markup(
    labels: tuple[str, ...],
    *,
    aria_label: str,
    empty_label: str,
    show_empty: bool = True,
) -> str:
    if not labels:
        if not show_empty:
            return ""
        return f'<p class="sr-note">{_escape(empty_label)}</p>'
    items = "\n".join(
        f"          <li>{_review_chip_markup(label)}</li>"
        for label in labels
    )
    return f"""        <ul class="flag-list" aria-label="{_escape(aria_label)}">
{items}
        </ul>"""


def _render_overview_source_narrative(
    source_record: Mapping[str, Any],
    related_records: list[Mapping[str, Any]],
) -> str:
    narrative = _source_narrative_text(source_record, related_records)
    if not narrative:
        return """<section class="overview-source-narrative" aria-labelledby="source-narrative-heading">
        <h3 id="source-narrative-heading">Source narrative</h3>
        <p>No source narrative excerpt is loaded for this complaint record.</p>
      </section>"""
    excerpt, has_more = _excerpt_text(narrative, 360)
    full_details = (
        f"""        <details>
          <summary>Show full source narrative</summary>
          <p>{_escape(narrative)}</p>
        </details>"""
        if has_more
        else ""
    )
    return f"""<section class="overview-source-narrative" aria-labelledby="source-narrative-heading">
        <div class="section-heading-with-copy">
          <h3 id="source-narrative-heading">Source narrative</h3>
          {_copy_icon_button("Copy source narrative", excerpt)}
        </div>
        <blockquote>{_escape(excerpt)}</blockquote>
{full_details}
      </section>"""


def _render_overview_timeline(source_record: Mapping[str, Any]) -> str:
    original_values = _mapping(source_record, "original_values")
    first_item = f"""          <li class="timeline-item timeline-item--received">
            <span class="timeline-marker timeline-marker--received rt-timeline__marker rt-timeline__marker--received" aria-hidden="true"></span>
            <span class="timeline-label rt-timeline__label">Complaint received</span>
            <strong class="rt-timeline__date">{_escape(_detail_timeline_date(_optional_string(original_values, "complaint_received_date")))}</strong>
          </li>"""
    remaining_rows = (
        ("Visit/investigation activity", "visit", _detail_timeline_date(_optional_string(original_values, "visit_date"))),
        ("Report", "report", _detail_timeline_date(_optional_string(original_values, "report_date"))),
        ("Signed", "signed", _detail_timeline_date(_optional_string(original_values, "date_signed"))),
    )
    remaining_items = "\n".join(
        f"""          <li class="timeline-item timeline-item--{_escape(marker)}">
            <span class="timeline-marker timeline-marker--{_escape(marker)} rt-timeline__marker rt-timeline__marker--{_escape(marker)}" aria-hidden="true"></span>
            <span class="timeline-label rt-timeline__label">{_escape(label)}</span>
            <strong class="rt-timeline__date">{_escape(value)}</strong>
          </li>"""
        for label, marker, value in remaining_rows
    )
    has_delay_badge = original_values.get("review_delay_over_120_days") is True
    delay_badge = (
        '        <div class="timeline-gap-badge timeline-gap-badge--between-first-activity rt-timeline__gap-badge" aria-label="Gap between complaint received and visit or investigation activity"><span class="review-chip badge-attention badge-attention--warning">120+ day gap</span></div>'
        if has_delay_badge
        else ""
    )
    timeline_class = "timeline-list timeline-list-linear has-gap" if has_delay_badge else "timeline-list timeline-list-linear"
    wrapper_class = "rt-timeline rt-timeline--linear has-gap" if has_delay_badge else "rt-timeline rt-timeline--linear"
    return f"""<section class="overview-timeline" aria-labelledby="complaint-timeline-heading">
        <h3 id="complaint-timeline-heading">Key dates</h3>
        <div class="{wrapper_class}">
        <div class="rt-timeline__line" aria-hidden="true"></div>
        <ol class="{timeline_class} rt-timeline__milestones">
{first_item}
{remaining_items}
        </ol>
{delay_badge}
        </div>
      </section>"""


def _render_detail_tertiary_actions(
    source_record: Mapping[str, Any],
    related_records: list[Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
) -> str:
    original_values = _mapping(source_record, "original_values")
    identity = _mapping(source_record, "identity")
    source_record_key = _string(identity, "source_record_key")
    feedback_href = _feedback_href(
        workflow_area="reviewer-detail",
        page_path=REVIEWER_UI_DETAIL_PATH,
        return_context=return_context,
        source_record_key=source_record_key,
        complaint_control_number=_optional_string(original_values, "complaint_control_number"),
        prompt="Describe what was confusing about this reviewer detail step.",
    )
    queue_href = _ccld_request_href(related_records, return_context)
    return f"""<div class="overview-tertiary-actions" aria-label="Additional reviewer actions">
            <a href="{_escape(feedback_href)}">Report an issue</a>
            <a href="{_escape(queue_href)}">Return to review queue</a>
          </div>"""


def _detail_heading(
    original_values: Mapping[str, Any],
    related_records: list[Mapping[str, Any]],
) -> str:
    complaint_control_number = _optional_string(original_values, "complaint_control_number")
    if complaint_control_number != "unknown":
        return f"Complaint {complaint_control_number}"
    return "Complaint record detail"


def _detail_complaint_label(original_values: Mapping[str, Any]) -> str:
    complaint_control_number = _optional_string(original_values, "complaint_control_number")
    if complaint_control_number != "unknown":
        return f"Complaint: {complaint_control_number}"
    return "Complaint: unknown"


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
    date_sentence = _detail_date_summary(original_values)
    cue_sentence = _detail_summary_cue_sentence(original_values, related_records)
    return (
        f"Complaint {control_number} for {facility_name} / facility {facility_number} "
        f"has source-derived finding {finding}. {date_sentence}. {cue_sentence}"
    )


def _detail_summary_cue_sentence(
    original_values: Mapping[str, Any],
    related_records: list[Mapping[str, Any]],
) -> str:
    cues: list[str] = []
    thresholds = _delay_thresholds(original_values)
    if thresholds:
        cues.append(f"complaint/report timing has a review flag over {max(thresholds)} days")
    if original_values.get("missing_first_activity_date") is True:
        cues.append("first investigation activity date is absent in the loaded record")
    if original_values.get("report_date_used_as_proxy") is True:
        cues.append("report date is marked as a proxy")
    citation_cues = _citation_poc_cues(original_values, related_records)
    cues.extend(citation_cues[:2])
    if not cues:
        return "Use the public source link before relying on source-derived values in reviewer-created notes/status."
    return "Review cues: " + "; ".join(cues) + "."


def _detail_facility_identity_line(
    related_records: list[Mapping[str, Any]],
    return_context: CcldQueueReturnContext | None = None,
) -> str:
    facility = _facility_context(related_records)
    facility_name = _facility_context_value(facility, "facility_name")
    return f"Facility: {facility_name}"


def _render_detail_context_row(
    source_record: Mapping[str, Any],
    related_records: list[Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
) -> str:
    queue_href = _ccld_request_href(related_records, return_context)
    return f"""<nav class="reviewer-detail-context" aria-label="Review context">
            <a href="{_escape(queue_href)}">Return to review queue</a>
        </nav>"""


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
    next_record_text = "Next record →"
    packet_links = _detail_packet_links(return_context, related_records)
    feedback_href = _feedback_href(
        workflow_area="reviewer-detail",
        page_path=REVIEWER_UI_DETAIL_PATH,
        return_context=return_context,
        source_record_key=source_record_key,
        complaint_control_number=control_number,
        prompt="Describe what was confusing about this reviewer detail step.",
    )
    return f"""<section class="next-action-panel action-card" aria-labelledby="detail-decision-continuity-heading">
          <p class="launch-kicker">Recommended action</p>
          <h2 id="detail-decision-continuity-heading">Check this complaint, then return to the queue</h2>
          <div class="detail-signal-grid">
            <section aria-labelledby="detail-priority-rationale-heading">
              <h3 id="detail-priority-rationale-heading">Why this record matters</h3>
              <ul>
{reason_items}
              </ul>
            </section>
            <section aria-labelledby="check-first-heading">
              <h3 id="check-first-heading">Check first</h3>
              <ul>
{check_items}
              </ul>
            </section>
          </div>
          <div class="form-actions">
            <a class="button" href="{_escape(ccld_request_href)}">&larr; Back to queue</a>
            <a class="button button-secondary" href="{_escape(next_record_href)}">{_escape(next_record_text)}</a>
          </div>
          <details class="technical-details">
            <summary>More actions and request context</summary>
            <dl>
              <dt>Facility ID</dt>
              <dd>{_escape(_display_value(return_context.facility_number))}</dd>
              <dt>Date range</dt>
              <dd>{_escape(_return_context_date_range(return_context))}</dd>
              <dt>Request origin</dt>
              <dd>{_escape(_request_origin_label(return_context.context_origin))}</dd>
              <dt>Complaint/control identifier</dt>
              <dd>{_escape(control_number)}</dd>
              <dt>Finding</dt>
              <dd>{_escape(finding)}</dd>
            </dl>
            {_render_detail_facility_context_cues(related_records, return_context)}
            <p>If a displayed value looks wrong or incomplete, check the source link first.
            Add a note only when it helps explain what still needs review, or send feedback
            when the page itself is confusing.</p>
            <div class="form-actions">
              {_detail_facility_hub_action(return_context)}
              <a class="button button-secondary" href="{CCLD_FACILITY_REVIEW_PRIORITY_PATH}">Return to facility review priority list</a>
              <a class="button button-secondary" href="{_escape(_ccld_request_href(related_records, return_context))}">Start complaint request if needed</a>
{packet_links}
              <a class="button button-secondary" href="{_escape(feedback_href)}">Send feedback</a>
            </div>
          </details>
        </section>"""


def _request_origin_label(value: str | None) -> str:
    if value == "facility_lookup":
        return "Facility lookup result"
    if value == "prefilled_link":
        return "Prefilled Facility ID link"
    return "Manual Facility ID entry"


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
                        <p>{_escape(context_guidance)} This review cue and source-link cue helps choose the next safe navigation step without changing loaded record values.</p>
            <dl>
              <dt>Facility context type</dt>
              <dd>{_escape(context_label)}</dd>
              <dt>Facility ID</dt>
              <dd>{_escape(_display_value(facility_number))}</dd>
                              <dt>Request context source</dt>
                              <dd>{_escape(_detail_request_context_label(return_context.context_origin))}</dd>
              <dt>Next review action</dt>
              <dd>Use this cue to return to the facility hub, request complaint records, or continue from the same queue.</dd>
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
            "No Facility ID is available for a facility hub cue on this detail page. Use the same queue or start a complaint request when a Facility ID is needed.",
            None,
        )
    if _active_directory_has_facility(facility_number):
        return (
            "facility hub",
            "This record has a directory-backed facility hub cue from the active facility-directory context. Use it to return to facility context before continuing review.",
            _facility_hub_href(facility_number),
        )
    if load_active_facility_review_signals().summary_for_facility(facility_number) is not None:
        return (
            "signal-only facility hub",
            "This record has a signal-only facility hub cue because uploaded public summary signals are available but the active directory row is not available here.",
            _facility_hub_href(facility_number),
        )
    return (
        "manual request context",
        "This record is tied to a manual request context in review. A facility hub cue is not available from the active directory or uploaded summary signals, so return to the same queue or start a complaint request if more context is needed.",
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
    return f"""              <a class="button button-secondary" href="{_escape(_packet_preview_href(return_context))}">Review packet readiness before copying or printing</a>
              {_render_complaint_export_controls(return_context, related_records)}
              <a class="button button-secondary" href="{_escape(_packet_draft_href(return_context))}">Open print draft</a>"""


def _render_complaint_export_controls(
    return_context: CcldQueueReturnContext,
    _related_records: list[Mapping[str, Any]],
) -> str:
    now = datetime.now(UTC)
    date_shortcut_links = f"""              <a class="button button-secondary" href="{_escape(_last_30_days_complaint_export_href(now))}">Last 30 days</a>
              <a class="button button-secondary" href="{_escape(_last_90_days_complaint_export_href(now))}">Last 90 days</a>"""
    facility_scoped_links = ""
    if return_context.facility_number is not None:
        facility_scoped_links = f"""
              <details class="compact-export-subdetails">
                <summary>Facility exports</summary>
                <div class="form-actions">
                  <a class="button button-secondary" href="{_escape(_facility_all_complaints_export_href(return_context.facility_number))}">All</a>
                  <a class="button button-secondary" href="{_escape(_facility_substantiated_export_href(return_context.facility_number))}">Substantiated</a>
                  <a class="button button-secondary" href="{_escape(_facility_last_30_days_complaint_export_href(return_context.facility_number, now))}">Last 30 days</a>
                  <a class="button button-secondary" href="{_escape(_facility_last_90_days_complaint_export_href(return_context.facility_number, now))}">Last 90 days</a>
                  <a class="button button-secondary" href="{_escape(_facility_serious_review_cue_export_href(return_context.facility_number))}">Priority cues</a>
                </div>
              </details>"""
    return f"""<details id="complaint-export-controls" class="technical-details dense-table-details compact-export-details">
              <summary id="complaint-export-controls-heading">Exports</summary>
              <p class="helper-text">Download complaint CSVs for review or comparison.</p>
              <div class="form-actions" aria-label="Complaint CSV exports">
              <a class="button button-secondary" href="{_escape(_matrix_export_href(return_context))}">Matrix</a>
              <a class="button button-secondary" href="{_escape(_serious_topics_href(return_context))}">Serious topics</a>
              <a class="button button-secondary" href="{_escape(_all_complaints_export_href(return_context))}">All complaints</a>
              <a class="button button-secondary" href="{_escape(_substantiated_export_href(return_context))}">Substantiated</a>
              <a class="button button-secondary" href="{_escape(_unsubstantiated_export_href(return_context))}">Unsubstantiated</a>
{date_shortcut_links}
              <a class="button button-secondary" href="{_escape(_serious_review_cue_export_href(return_context))}">Priority cues</a>
              </div>
{facility_scoped_links}
            </details>"""


def _queue_source_records(records: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    source_records: list[Mapping[str, Any]] = []
    for record in records:
        try:
            source_records.append(_mapping(record, "source_record"))
        except Exception:
            continue
    return source_records


def _reviewer_queue_export_context(
    records: list[Mapping[str, Any]],
) -> CcldQueueReturnContext:
    empty_context = CcldQueueReturnContext()
    facility_numbers: set[str] = set()
    for record in records:
        try:
            source_record = _mapping(record, "source_record")
            if _queue_source_record_entity_type(source_record) != "complaint":
                continue
            facility_number = _complaint_export_row_facility_number(
                source_record,
                empty_context,
            )
            if facility_number:
                facility_numbers.add(facility_number)
        except Exception:
            continue
    if len(facility_numbers) == 1:
        return CcldQueueReturnContext(facility_number=next(iter(facility_numbers)))
    return CcldQueueReturnContext()


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


def _facility_complaint_export_status_counts(
    records: list[Mapping[str, Any]], facility_number: str
) -> dict[str, int]:
    counts = {
        "all": 0,
        "substantiated": 0,
        "unsubstantiated": 0,
    }
    for record in records:
        if _string(record, "entity_type") != "complaint":
            continue
        rec_facility_id = _optional_string(record, "facility_id")
        if rec_facility_id != facility_number:
            continue
        counts["all"] += 1
        finding = _mapping(record, "original_values").get("finding")
        finding_norm = _normalized_complaint_finding(finding)
        if finding_norm in {"substantiated", "unsubstantiated"}:
            counts[finding_norm] += 1
    return counts


def _facility_serious_review_cue_record_count(
    records: list[Mapping[str, Any]], facility_number: str
) -> int:
    return sum(
        1
        for record in records
        if _string(record, "entity_type") == "complaint"
        and _optional_string(record, "facility_id") == facility_number
        and _serious_review_cue(record, records)
    )


def _detail_check_first_items(original_values: Mapping[str, Any]) -> tuple[str, ...]:
    items = [
        f"Complaint received date: {_optional_string(original_values, 'complaint_received_date')}",
        f"Visit date: {_optional_string(original_values, 'visit_date')}",
        f"Report date: {_optional_string(original_values, 'report_date')}",
        f"Date signed: {_optional_string(original_values, 'date_signed')}",
        f"Finding value: {_optional_string(original_values, 'finding')}",
    ]
    if original_values.get("missing_first_activity_date") is True:
        items.append("Needs date/source review: first activity date missing locally.")
    if original_values.get("report_date_used_as_proxy") is True:
        items.append("Review flag: report date used as proxy; use cautious proxy wording only after source record review.")
    items.append("Review the source link before relying on missing, confusing, or proxy-related values.")
    items.append("If a loaded value looks wrong or incomplete, treat it as a possible correction concern for reviewer-created notes or feedback items, not as a changed source record.")
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
            confirm the source link, read source-confidence cues and field-note guidance,
            and save reviewer notes/status only as tester-created observations.</p>
            <ol>
                <li>Confirm the selected complaint record in the record summary.</li>
                <li>Review the source link and source-context cues before adding
                reviewer-created notes or status.</li>
                <li>Check whether reviewer notes or statuses already exist.</li>
                <li>Add a note or status only after checking the source context and only if it
                helps the review queue.</li>
                <li><a href="{_escape(ccld_request_href)}">Return to the CCLD request queue</a>
                with the same request context, resubmit when needed, and use the refreshed
                queue's suggested next record to continue.</li>
                <li>Copy feedback details when ready.</li>
            </ol>
            <p>Next-record guidance is navigation help derived from existing
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
            <p>Use the same-queue link when you came from CCLD request results; it
            carries the Facility ID, date range, and lookup or manual-entry
            context back to the queue so refreshed reviewer-created cues appear there.</p>
            <ul>
                <li><a href="{_escape(ccld_request_href)}">&larr; Back to queue</a></li>
                <li><a href="{_escape(next_record_href)}">Open next recommended record from this context</a></li>
{packet_links}
                <li><a href="{CCLD_FACILITY_LOOKUP_PATH}">Find another CCLD facility</a></li>
                <li><a href="{CCLD_HELP_PATH}">Open CCLD workflow help</a></li>
                <li><a href="{REVIEWER_UI_RECORDS_PATH}">Back to reviewer records</a></li>
                <li><a href="{_escape(feedback_href)}">Send feedback with this record</a></li>
                <li><a href="{_escape(detail_href)}">Refresh this seeded detail</a></li>
                <li><a href="#record-summary-heading">Review record summary</a></li>
                <li><a href="#source-confidence-heading">Review source-confidence cues</a></li>
                <li><a href="#field-note-guidance-heading">Review field-note guidance</a></li>
                <li><a href="#traceability-heading">Review source record support</a></li>
                <li><a href="#source-context-heading">Review loaded record context</a></li>
                <li><a href="#reviewer-state-heading">Review notes and statuses</a></li>
                <li><a href="#review-actions-heading">Add note or status</a></li>
                <li><a href="#detail-feedback-heading">Prepare issue details</a></li>
            </ul>
        </section>"""


def _detail_navigation_packet_items(return_context: CcldQueueReturnContext) -> str:
    if return_context.facility_number is None:
        return ""
    return f"""                <li><a href="{_escape(_packet_preview_href(return_context))}">Review packet readiness before copying or printing</a></li>
                <li><a href="{_escape(_matrix_export_href(return_context))}">Download complaint review matrix CSV</a></li>
                <li><a href="{_escape(_substantiated_export_href(return_context))}">Download substantiated complaint CSV</a></li>
                <li><a href="{_escape(_unsubstantiated_export_href(return_context))}">Download unsubstantiated complaint CSV</a></li>
                <li><a href="{_escape(_all_complaints_export_href(return_context))}">Download all complaint CSV</a></li>
                <li><a href="{_escape(_packet_draft_href(return_context))}">Open print draft</a></li>"""


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
        "feedback_type": "Bug/problem",
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
    facility = _facility_context(related_records)
    facility_number = _facility_context_value(facility, "external_facility_number")
    facility_name = _facility_context_value(facility, "facility_name")
    return f"""<section class="detail-card" aria-labelledby="record-summary-heading">
      <p class="launch-kicker">Source</p>
      <h2 id="record-summary-heading">Facility identity and license facts</h2>
      <dl class="fact-grid">
        {_render_fact_item("Facility name", facility_name)}
        {_render_fact_item("Facility ID", facility_number)}
        {_render_fact_item("Facility type", _facility_context_value(facility, "facility_type"))}
        {_render_fact_item("County", _facility_context_value(facility, "county"))}
        {_render_fact_item("License status", _facility_context_value(facility, "license_status"))}
        {_render_fact_item("Source ID", _facility_context_value(facility, "source_id"))}
      </dl>
    </section>"""


def _render_fact_item(label: str, value: str) -> str:
    return f"""        <div class="fact-card">
          <dt>{_escape(label)}</dt>
          <dd>{_escape(value)}</dd>
        </div>"""


def _render_complaint_timeline_section(
    source_record: Mapping[str, Any],
    *,
    compact: bool = False,
) -> str:
    original_values = _mapping(source_record, "original_values")
    source_document = _mapping(source_record, "source_document")
    source_action = _source_action_link(source_document)
    rows = (
        (
            _glossary_term(
                "Received",
                "The complaint received date shown in loaded records.",
                "timeline-received",
            ),
            "Complaint received",
            _detail_timeline_date(_optional_string(original_values, "complaint_received_date")),
        ),
        (
            _glossary_term(
                "First activity",
                "The first investigation activity date shown when it is available in loaded records.",
                "timeline-first-activity",
            ),
            "First investigation activity",
            _timeline_first_activity_value(original_values),
        ),
        (
            _glossary_term(
                "Visit",
                "The visit date shown in loaded records when available.",
                "timeline-visit",
            ),
            "Visit",
            _detail_timeline_date(_optional_string(original_values, "visit_date")),
        ),
        (
            _glossary_term(
                "Report",
                "The loaded report date. If a proxy flag is present, use timing language cautiously.",
                "timeline-report-date",
            ),
            "Report",
            _detail_timeline_date(_optional_string(original_values, "report_date")),
        ),
        (
            _glossary_term(
                "Signed",
                "The date signed shown in loaded records when available.",
                "timeline-signed",
            ),
            "Signed",
            _detail_timeline_date(_optional_string(original_values, "date_signed")),
        ),
    )
    items = "\n".join(
        f"""        <li class="timeline-item">
          <span class="timeline-label">{label}</span>
          <strong>{_copyable_value(copy_label, value)}</strong>
        </li>"""
        for label, copy_label, value in rows
    )
    heading_tag = "h3" if compact else "h2"
    section_class = "compact-timeline detail-card" if compact else "detail-card"
    return f"""<section class="{section_class}" aria-labelledby="complaint-timeline-heading">
      <div class="dense-section-header">
        <div>
          <p class="launch-kicker">Source timeline</p>
          <{heading_tag} id="complaint-timeline-heading">Source timeline</{heading_tag}>
        </div>
        {source_action}
      </div>
      <ol class="timeline-list">
{items}
      </ol>
    </section>"""


def _source_action_link(source_document: Mapping[str, Any]) -> str:
    source_url = source_document.get("source_url")
    if _has_display_value(source_url):
        return f'<a class="button" href="{_escape(str(source_url))}">Open CCLD source record</a>'
    return '<span class="button button-disabled" aria-disabled="true">Source not available</span>'


def _timeline_first_activity_value(original_values: Mapping[str, Any]) -> str:
    value = original_values.get("first_investigation_activity_date")
    if _has_display_value(value):
        return _detail_display_date(_display_value(value))
    return "Not available"


def _timeline_first_activity_note(original_values: Mapping[str, Any]) -> str:
    if original_values.get("missing_first_activity_date") is True:
        return "Do not treat this missing local value as source absence."
    return "First activity value is source-derived when loaded."


def _timeline_report_date_note(original_values: Mapping[str, Any]) -> str:
    if original_values.get("report_date_used_as_proxy") is True:
        return "Report date used as proxy; verify against source."
    return "Source-derived report date when loaded."


def _render_allegations_findings_section(
    source_record: Mapping[str, Any],
    related_records: list[Mapping[str, Any]],
) -> str:
    original_values = _mapping(source_record, "original_values")
    allegation_rows = [
        record
        for record in related_records
        if _string(record, "entity_type") == "allegation"
    ]
    rows = "\n".join(_render_allegation_row(record) for record in allegation_rows)
    if not rows:
        finding = _optional_string(original_values, "finding")
        rows = f"""        <tr>
          <td>{_finding_badge(finding)}</td>
          <td>Allegation details are not loaded for this complaint record.</td>
        </tr>"""
    return f"""<section class="detail-card" aria-labelledby="allegations-findings-heading">
      <p class="launch-kicker">Source</p>
      <h2 id="allegations-findings-heading">Allegations and findings</h2>
      <table>
        <thead>
          <tr>
            <th scope="col">Finding</th>
            <th scope="col">Allegation</th>
          </tr>
        </thead>
        <tbody>
{rows}
        </tbody>
      </table>
    </section>"""


def _render_allegation_row(record: Mapping[str, Any]) -> str:
    original_values = _mapping(record, "original_values")
    finding = _optional_string(original_values, "finding")
    return f"""        <tr>
          <td>{_finding_badge(finding)}</td>
          <td>{_escape(_optional_string(original_values, "allegation_text"))}</td>
        </tr>"""


def _render_citation_poc_section(
    source_record: Mapping[str, Any],
    related_records: list[Mapping[str, Any]],
) -> str:
    original_values = _mapping(source_record, "original_values")
    cues = _citation_poc_cues(original_values, related_records)
    if not cues:
        return ""
    cue_items = "\n".join(f"        <li>{_escape(cue)}</li>" for cue in cues)
    return f"""<section class="detail-card" aria-labelledby="citation-poc-heading">
      <p class="launch-kicker">Source</p>
      <h2 id="citation-poc-heading">Citations, deficiencies, and Plan of Correction</h2>
      <ul>
{cue_items}
      </ul>
      <p>Use the original CCLD source record before relying on citation, deficiency, civil penalty, or POC wording.</p>
    </section>"""


def _render_top_source_narrative(
    source_record: Mapping[str, Any],
    related_records: list[Mapping[str, Any]],
) -> str:
    narrative = _source_narrative_text(source_record, related_records)
    if not narrative:
        return ""
    excerpt, has_more = _excerpt_text(narrative, 280)
    full_details = (
        f"""      <details class="top-narrative-details">
        <summary>Show more source narrative</summary>
        <p>{_escape(narrative)}</p>
      </details>"""
        if has_more
        else ""
    )
    return f"""      <section class="top-source-narrative" aria-labelledby="top-source-narrative-heading">
        <h3 id="top-source-narrative-heading">Source narrative</h3>
        <blockquote>{_copyable_value("Source narrative", excerpt)}</blockquote>
{full_details}
      </section>"""


def _render_source_narrative_section(
    source_record: Mapping[str, Any],
    related_records: list[Mapping[str, Any]],
) -> str:
    narrative = _source_narrative_text(source_record, related_records)
    if not narrative:
        return """<section class="detail-card" aria-labelledby="source-narrative-heading">
      <p class="launch-kicker">Source</p>
      <h2 id="source-narrative-heading">Source narrative</h2>
      <p>No source narrative excerpt is loaded for this complaint record.</p>
    </section>"""
    excerpt, has_more = _excerpt_text(narrative, 360)
    full_details = (
        f"""      <details>
        <summary>Show full source narrative</summary>
        <p>{_escape(narrative)}</p>
      </details>"""
        if has_more
        else ""
    )
    return f"""<section class="detail-card" aria-labelledby="source-narrative-heading">
      <p class="launch-kicker">Source</p>
      <h2 id="source-narrative-heading">Source narrative</h2>
      <blockquote>{_escape(excerpt)}</blockquote>
{full_details}
    </section>"""


def _source_narrative_text(
    source_record: Mapping[str, Any],
    related_records: list[Mapping[str, Any]],
) -> str:
    texts: list[str] = []
    for value_map in [_mapping(source_record, "original_values")]:
        texts.extend(_narrative_values(value_map))
    for record in related_records:
        if _string(record, "entity_type") in {"allegation", "event"}:
            texts.extend(_narrative_values(_mapping(record, "original_values")))
    deduped = list(dict.fromkeys(texts))
    return " ".join(deduped)


def _narrative_values(values: Mapping[str, Any]) -> list[str]:
    texts: list[str] = []
    for field_name in _NARRATIVE_FIELD_NAMES:
        value = values.get(field_name)
        if isinstance(value, str) and value.strip():
            texts.append(" ".join(value.split()))
    return texts


def _excerpt_text(text: str, limit: int) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    truncated = text[:limit].rsplit(" ", 1)[0].rstrip(".,;:")
    return f"{truncated}...", True


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
                "Facility ID",
                None if facility is None else facility.get("external_facility_number"),
                "Use this to confirm the detail matches the CCLD request context.",
            ),
            rows,
            _render_first_activity_confidence_row(original_values),
            _render_report_date_proxy_confidence_row(original_values),
        )
    )
    return f"""<details class="technical-details dense-table-details source-confidence-details">
        <summary>Source-derived value checks</summary>
        <section id="source-confidence-heading" aria-labelledby="source-confidence-title">
            <p class="launch-kicker">Source-derived facts</p>
            <h2 id="source-confidence-title">Review flags and source checks</h2>
            <p>These cues summarize visible source-derived complaint fields already loaded in
            this record. They help testers see which values are present, which
            expected values are not available locally, and which fields need source record
            review before a reviewer-created note or status observation relies on them.</p>
            <p>Use missing, confusing, and proxy-related cues to decide which loaded
            values need source record review before notes, status, or a feedback item.</p>
            <p>Missing values should be described in reviewer-created notes/status or
            feedback details as <q>not available in this record</q>.</p>
            <p>Next action: check the source link, use cautious reviewer-created
            note/status wording only when it helps the queue, Send feedback when
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
        </section>
    </details>"""


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
            "Not available in this record. The missing-field "
            "flag is true."
        )
    return f"""          <tr>
                        <th scope="row">First investigation activity date</th>
                        <td>{_escape(cue)}</td>
                        <td>{_escape(_source_confidence_value(value))}</td>
                        <td>When relevant, say this value is not available locally; do not say
                        investigation activity did or did not happen. Send feedback if the
                        missing-value next step is unclear.</td>
                    </tr>"""


def _render_report_date_proxy_confidence_row(values: Mapping[str, Any]) -> str:
    value = values.get("report_date_used_as_proxy")
    if value is True:
        cue = "Fallback/proxy-derived delay basis indicated by current field."
    elif value is False:
        cue = "Current field does not mark report date as the delay-review proxy."
    else:
        cue = "Not available in this record."
    return f"""          <tr>
                        <th scope="row">Report date proxy flag</th>
                        <td>{_escape(cue)}</td>
                        <td>{_escape(_source_confidence_value(value))}</td>
                        <td>Use fallback/proxy wording only when this cue says the current
                        field identifies a proxy-derived delay basis; Send feedback
                        if proxy wording or next action remains confusing.</td>
                    </tr>"""


def _source_confidence_cue(value: object) -> str:
    if _has_display_value(value):
        return "Present in this source-derived record."
    return "Not available in this record."


def _source_confidence_value(value: object) -> str:
    if not _has_display_value(value):
        return "not available in this record"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return _display_value(value)


def _render_source_traceability_section(
    identity: Mapping[str, Any],
    source_document: Mapping[str, Any],
    source_traceability: Mapping[str, Any],
    import_batch: Mapping[str, Any],
    original_values: Mapping[str, Any],
) -> str:
        source_link = _source_link_markup(source_document)
        return f"""<section class="detail-card" aria-labelledby="traceability-heading">
            <p class="launch-kicker">Source</p>
            <h2 id="traceability-heading">{_glossary_term("Source record support", "The source URL, source support context, and related review details used to check where a loaded value came from.", "detail-source-support")}</h2>
            <p>{_escape(_source_traceability_cue(source_document))}</p>
            <dl class="fact-grid">
                {_render_fact_item("Source type", _source_type_label(source_document))}
                {_render_fact_item("Traceability level", _traceability_level_label(source_document, source_traceability))}
                {_render_fact_item("Record loaded date", _record_loaded_date(import_batch, source_document))}
                {_render_fact_item("Fields extracted", _fields_extracted_label(original_values))}
                {_render_fact_item("Loaded extraction marker", _optional_string(original_values, "extraction_confidence"))}
                {_render_fact_item("Connector", _connector_label(source_document) or "not available in this record")}
            </dl>
            <p>{source_link}</p>
            <details class="technical-details">
                <summary>Show field-level source details</summary>
      <p>Use these fields when checking the public source or reporting a confusing record.</p>
            {_render_traceability_summary(source_document, source_traceability, import_batch)}
      <table>
        <caption>Selected complaint source support fields</caption>
        <thead>
          <tr>
            <th scope="col">Traceability cue</th>
            <th scope="col">Value shown for this selected record</th>
            <th scope="col">How to use it during review</th>
          </tr>
        </thead>
        <tbody>
{_render_traceability_field_rows(identity, source_document, source_traceability, import_batch)}
        </tbody>
      </table>
      </details>
    </section>"""


def _source_link_markup(source_document: Mapping[str, Any]) -> str:
    source_url = source_document.get("source_url")
    if _has_display_value(source_url):
        return f'<a href="{_escape(str(source_url))}">Open CCLD source record</a>'
    return "Source link not available in this loaded record."


def _source_type_label(source_document: Mapping[str, Any]) -> str:
    document_type = _optional_string(source_document, "document_type")
    if document_type == "complaint_investigation_report":
        return "CCLD complaint investigation report"
    return document_type


def _traceability_level_label(
    source_document: Mapping[str, Any],
    source_traceability: Mapping[str, Any],
) -> str:
    if _has_visible_traceability_document(source_document) and source_traceability:
        return "Field-level available"
    if _has_display_value(source_document.get("source_url")):
        return "Source link available"
    return "Limited in loaded record"


def _record_loaded_date(
    import_batch: Mapping[str, Any],
    source_document: Mapping[str, Any],
) -> str:
    imported_at = import_batch.get("imported_at")
    if _has_display_value(imported_at):
        return _display_value(imported_at)
    retrieved_at = source_document.get("retrieved_at")
    if _has_display_value(retrieved_at):
        return _display_value(retrieved_at)
    return "not available in this record"


def _fields_extracted_label(original_values: Mapping[str, Any]) -> str:
    scalar_fields = [
        key
        for key, value in original_values.items()
        if key not in _SAFE_ORIGINAL_VALUE_DENYLIST
        and (isinstance(value, str | int | float | bool) or value is None)
    ]
    extracted = [key for key in scalar_fields if _has_display_value(original_values.get(key))]
    return f"{len(extracted)} of {len(scalar_fields)}"


def _availability_label(value: object) -> str:
    if _has_display_value(value):
        return "available"
    return "missing in this record"


def _connector_retrieval_availability(source_document: Mapping[str, Any]) -> str:
    connector_available = _has_display_value(source_document.get("connector_name"))
    retrieved_available = _has_display_value(source_document.get("retrieved_at"))
    if connector_available and retrieved_available:
        return "connector available; retrieval time available"
    if connector_available:
        return "connector available; retrieval time missing in this record"
    if retrieved_available:
        return "connector missing in this record; retrieval time available"
    return "connector and retrieval time missing in this record"


def _render_field_note_guidance_section() -> str:
    return """<details class="technical-details reviewer-note-guidance">
            <summary>Cautious reviewer-created note guidance</summary>
            <section id="field-note-guidance-heading"
            aria-labelledby="field-note-guidance-title">
            <p class="launch-kicker">Reviewer-created guidance</p>
            <h3 id="field-note-guidance-title">Field-note guidance</h3>
            <p>Use this guidance after checking source support and the source-confidence
            cues. Reviewer notes/status are reviewer-created observations for this
            queue; they do not edit loaded record fields.</p>
            <p>If a loaded value looks wrong or incomplete, check the source link first.
            For now, use a reviewer-created note to describe the possible correction concern or use
            an feedback item if the correction path is confusing. The workflow does not submit
            correction decisions.</p>
            <p>For missing, confusing, or proxy-related loaded values, the safe next
            action is to name the cue, avoid source absence or verification claims,
            Send feedback when the note/status wording is unclear, and continue review from the
            same queue context.</p>
            <p>Keep notes short and cautious. When a value is unclear, describe what the
            page showed and what still needs checking rather than making a source,
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
                        <td>Say the record shows the value and name the field you
                        checked. Example: record shows complaint received date.</td>
                        <td>Do not say the value is legally verified or a public-source conclusion.</td>
                    </tr>
                    <tr>
                        <th scope="row">Field is not available locally</th>
                        <td>Say the field is not available in this record.</td>
                        <td>Do not say the source does not contain this, the record is incomplete,
                        or data was lost.</td>
                    </tr>
                    <tr>
                        <th scope="row">Report-date proxy flag is shown</th>
                        <td>Say the cue marks report date as a proxy before using delay
                        wording.</td>
                        <td>Do not use the proxy flag alone to say an investigation did or did not
                        happen, or that a delay is proven.</td>
                    </tr>
                    <tr>
                        <th scope="row">Field remains confusing after source review</th>
                        <td>Say the field remained unclear after checking the source link and
                        include the field label or source document ID when useful.</td>
                        <td>Do not turn uncertainty into a public-source absence or facility-wide
                        conclusion.</td>
                    </tr>
                    <tr>
                        <th scope="row">Value looks like a UI or data issue</th>
                        <td>Use feedback details for suspected wording, display, or
                        data issues instead of treating the note as a loaded-value
                        edit.</td>
                        <td>Do not imply the app corrected, edited, or replaced the loaded
                        record.</td>
                    </tr>
                    <tr>
                        <th scope="row">Possible correction concern</th>
                        <td>Say which loaded value looked wrong or incomplete after checking
                        source support, and what should receive correction review later.</td>
                        <td>Do not say this note submitted, decided, or changed correction review or
                        packet output.</td>
                    </tr>
                </tbody>
            </table>
        </section>
        </details>"""


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
            "Use this to distinguish the selected complaint from related rows.",
        ),
        (
            "Source document ID",
            source_document.get("source_document_id"),
            "Use this to connect the complaint to its source document row.",
        ),
        (
            "Source URL",
            source_document.get("source_url"),
            "Use this as the public-source pointer when checking the source page.",
        ),
        (
            "Source checksum",
            source_document.get("raw_sha256"),
            "Use this to identify the preserved raw source bytes in evidence.",
        ),
        (
            "Source support preservation",
            _raw_artifact_display(source_document.get("raw_path")),
            "Use this cue to know whether source support preservation is represented; server paths are not shown in the browser.",
        ),
        (
            "Source artifact identity",
            source_traceability.get("source_artifact_identity"),
            "Use this to identify the seeded-corpus artifact used for this page.",
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
            "Use this to report which deterministic connector produced the row.",
        ),
        (
            "Retrieved at capture time",
            source_document.get("retrieved_at"),
            "Use this as the capture timestamp, not as a public-source "
            "completeness claim.",
        ),
        (
            "Import batch ID",
            import_batch.get("import_batch_id"),
            "Use this to identify the seeded import batch.",
        ),
        (
            "Import validation status",
            import_batch.get("validation_status"),
            "Use this to report artifact validation state without changing source data.",
        ),
        (
            "Raw hash validation status",
            import_batch.get("raw_hash_validation_status"),
            "Use this to report hash validation state.",
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
    return "not available in this record"


def _traceability_value(value: object) -> str:
    if not _has_display_value(value):
        return "not available in this record"
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
            visible and use reviewer detail when the value needs more checking.</p>
            <table>
                <caption>Visible source support summary</caption>
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
        "available" if _has_display_value(value) else "not available in this record"
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
    return f"""<section class="detail-card" aria-labelledby="source-context-heading">
            <p class="launch-kicker">Source</p>
            <h2 id="source-context-heading">Related facility activity</h2>
            <p>Use these compact source-derived rows for pattern and context review. Detailed
            bundle fields remain available below when traceability or debugging context is needed.</p>
            {_render_related_activity_cards(related_records, selected_source_record_key)}
            <details class="technical-details dense-table-details related-source-details">
              <summary>View related source bundle details</summary>
              <section aria-labelledby="related-source-bundle-heading">
                <h3 id="related-source-bundle-heading">Related source bundle details</h3>
                <p>These details show the raw source-derived row identifiers and safe scalar
                context for the selected seeded bundle.</p>
                {_render_source_context_summary(related_records)}
                <table>
                <caption>Related source-derived rows in the selected seeded bundle</caption>
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
              </section>
            </details>
        </section>"""


def _render_related_activity_cards(
    related_records: list[Mapping[str, Any]],
    selected_source_record_key: str,
) -> str:
    cards = "\n".join(
        _render_related_activity_card(record, selected_source_record_key)
        for record in related_records
    )
    if not cards:
        return '<p class="helper-text">No related facility activity is loaded for this record.</p>'
    return f"""<div class="related-activity-list">
{cards}
            </div>"""


def _render_related_activity_card(
    record: Mapping[str, Any],
    selected_source_record_key: str,
) -> str:
    entity_type = _string(record, "entity_type")
    badge = _related_activity_badge(record)
    badge_html = (
        f'<span class="badge badge-muted">{_escape(badge)}</span>'
        if badge
        else ""
    )
    date_value = _related_activity_date(record)
    date_row = (
        f"""              <dt>Date</dt>
              <dd>{_escape(date_value)}</dd>"""
        if date_value
        else ""
    )
    return f"""              <article class="related-activity-card">
                <header>
                  <span class="related-activity-type">{_escape(_related_record_type_label(entity_type))}</span>
                  {badge_html}
                </header>
                <h3>{_escape(_related_activity_title(record))}</h3>
                <dl class="related-activity-meta">
                  {date_row}
                  <dt>Context</dt>
                  <dd>{_escape(_related_activity_context(record, selected_source_record_key))}</dd>
                </dl>
                <p>{_escape(_related_activity_reason(record, selected_source_record_key))}</p>
              </article>"""


def _related_record_type_label(entity_type: str) -> str:
    labels = {
        "facility": "Facility",
        "source_document": "Source report",
        "complaint": "Complaint",
        "allegation": "Allegation",
        "event": "Activity",
        "extraction_audit": "Traceability",
    }
    return labels.get(entity_type, entity_type.replace("_", " ").strip().title())


def _related_activity_title(record: Mapping[str, Any]) -> str:
    entity_type = _string(record, "entity_type")
    original_values = _mapping(record, "original_values")
    if entity_type == "facility":
        return _short_activity_value(original_values.get("facility_name"), "Facility identity")
    if entity_type == "source_document":
        document_type = _optional_string(original_values, "document_type")
        if document_type == "complaint_investigation_report":
            return "Complaint investigation report"
        return _short_activity_label(document_type, "Source report")
    if entity_type == "complaint":
        control_number = original_values.get("complaint_control_number")
        if _has_display_value(control_number):
            return f"Complaint {_display_value(control_number)}"
        return "Complaint record"
    if entity_type == "allegation":
        return _short_activity_value(
            original_values.get("allegation_category"),
            "Allegation context",
        )
    if entity_type == "event":
        return _short_activity_label(original_values.get("event_type"), "Activity cue")
    if entity_type == "extraction_audit":
        field_name = _short_activity_label(
            original_values.get("field_name"),
            "displayed field",
        )
        return f"Traceability for {field_name}"
    return _related_record_type_label(entity_type)


def _related_activity_date(record: Mapping[str, Any]) -> str:
    original_values = _mapping(record, "original_values")
    for field_name in (
        "complaint_received_date",
        "visit_date",
        "report_date",
        "date_signed",
        "event_date",
        "retrieved_at",
    ):
        value = original_values.get(field_name)
        if _has_display_value(value):
            return _display_value(value)
    return ""


def _related_activity_context(
    record: Mapping[str, Any],
    selected_source_record_key: str,
) -> str:
    if _string(record, "source_record_key") == selected_source_record_key:
        return "Selected complaint record"
    entity_type = _string(record, "entity_type")
    contexts = {
        "facility": "Same Facility ID context",
        "source_document": "Source report in this complaint bundle",
        "complaint": "Complaint row in the same facility context",
        "allegation": "Allegation row in the same source report",
        "event": "Activity row in the same source report",
        "extraction_audit": "Extraction traceability row",
    }
    return contexts.get(entity_type, "Related loaded source-derived row")


def _related_activity_badge(record: Mapping[str, Any]) -> str:
    original_values = _mapping(record, "original_values")
    for label, field_name in (
        ("Finding", "finding"),
        ("Status", "status"),
        ("Facility status", "facility_status"),
        ("License status", "license_status"),
    ):
        value = original_values.get(field_name)
        if _has_display_value(value):
            return f"{label}: {_short_activity_value(value, 'available', max_length=36)}"
    return ""


def _related_activity_reason(
    record: Mapping[str, Any],
    selected_source_record_key: str,
) -> str:
    if _string(record, "source_record_key") == selected_source_record_key:
        return "Keeps the selected complaint visible next to related facility activity."
    entity_type = _string(record, "entity_type")
    reasons = {
        "facility": "Confirms the Facility ID tied to the complaint.",
        "source_document": "Points back to the public report context before relying on displayed values.",
        "complaint": "Shows another loaded complaint for the same facility context.",
        "allegation": "Surfaces allegation and finding context without raw narrative text.",
        "event": "Adds dated activity context when the loaded bundle includes it.",
        "extraction_audit": "Shows that extraction traceability is available in the detailed bundle.",
    }
    return reasons.get(entity_type, "Adds loaded context for comparing records in the same bundle.")


def _short_activity_label(value: object, fallback: str, *, max_length: int = 72) -> str:
    text = _short_activity_value(value, fallback, max_length=max_length)
    if text == fallback:
        return fallback
    return text.replace("_", " ").strip().capitalize()


def _short_activity_value(value: object, fallback: str, *, max_length: int = 72) -> str:
    if not _has_display_value(value):
        return fallback
    text = _display_value(value).strip()
    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rstrip() + "..."


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


def _source_record_indexes(records: list[Mapping[str, Any]]) -> SourceRecordIndexes:
    by_import_batch_id: dict[str, list[Mapping[str, Any]]] = {}
    by_facility_id: dict[str, list[Mapping[str, Any]]] = {}
    by_source_document_id: dict[str, list[Mapping[str, Any]]] = {}
    by_complaint_id: dict[str, list[Mapping[str, Any]]] = {}
    by_stable_source_id: dict[str, list[Mapping[str, Any]]] = {}
    by_source_record_key: dict[str, Mapping[str, Any]] = {}
    for record in records:
        source_record_key = _string(record, "source_record_key")
        by_source_record_key[source_record_key] = record
        _append_source_index_value(
            by_import_batch_id,
            _flat_record_import_batch_id(record),
            record,
        )
        _append_source_index_value(
            by_facility_id,
            _optional_string(record, "facility_id"),
            record,
        )
        _append_source_index_value(
            by_source_document_id,
            _optional_string(record, "source_document_id"),
            record,
        )
        _append_source_index_value(
            by_stable_source_id,
            _optional_string(record, "stable_source_id"),
            record,
        )
        for complaint_id in _flat_record_complaint_ids(record):
            _append_source_index_value(by_complaint_id, complaint_id, record)
    return SourceRecordIndexes(
        by_import_batch_id=_freeze_source_index(by_import_batch_id),
        by_facility_id=_freeze_source_index(by_facility_id),
        by_source_document_id=_freeze_source_index(by_source_document_id),
        by_complaint_id=_freeze_source_index(by_complaint_id),
        by_stable_source_id=_freeze_source_index(by_stable_source_id),
        by_source_record_key=by_source_record_key,
    )


def _related_source_records_from_indexes(
    selected_source_record: Mapping[str, Any],
    indexes: SourceRecordIndexes,
) -> list[Mapping[str, Any]]:
    identity = _mapping(selected_source_record, "identity")
    selected_source_record_key = _string(identity, "source_record_key")
    selected_source_document = _mapping(selected_source_record, "source_document")
    selected_source_document_id = _string(selected_source_document, "source_document_id")
    selected_facility_id = _optional_string(identity, "facility_id")
    selected_import_batch_id = _selected_source_import_batch_id(selected_source_record)
    selected_batch_record_keys = _selected_batch_record_keys(
        indexes,
        selected_import_batch_id,
    )
    related_by_key: dict[str, Mapping[str, Any]] = {}
    selected_record = indexes.by_source_record_key.get(selected_source_record_key)
    if selected_record is not None:
        related_by_key[selected_source_record_key] = selected_record
    for record in indexes.by_source_document_id.get(selected_source_document_id, ()):
        _add_indexed_related_record(related_by_key, record, selected_batch_record_keys)
    if selected_facility_id != "unknown":
        for record in indexes.by_facility_id.get(selected_facility_id, ()):
            _add_indexed_related_record(related_by_key, record, selected_batch_record_keys)
    for complaint_id in _selected_source_complaint_ids(selected_source_record):
        for record in indexes.by_complaint_id.get(complaint_id, ()):
            _add_indexed_related_record(related_by_key, record, selected_batch_record_keys)
        for record in indexes.by_stable_source_id.get(complaint_id, ()):
            _add_indexed_related_record(related_by_key, record, selected_batch_record_keys)
    return _sort_related_source_records(tuple(related_by_key.values()))


def _add_indexed_related_record(
    related_by_key: dict[str, Mapping[str, Any]],
    record: Mapping[str, Any],
    selected_batch_record_keys: frozenset[str] | None,
) -> None:
    source_record_key = _string(record, "source_record_key")
    if (
        selected_batch_record_keys is not None
        and source_record_key not in selected_batch_record_keys
    ):
        return
    related_by_key[source_record_key] = record


def _selected_source_import_batch_id(source_record: Mapping[str, Any]) -> str:
    import_batch = _mapping(source_record, "import_batch")
    return _optional_string(import_batch, "import_batch_id")


def _selected_batch_record_keys(
    indexes: SourceRecordIndexes,
    selected_import_batch_id: str,
) -> frozenset[str] | None:
    if selected_import_batch_id == "unknown":
        return None
    return frozenset(
        _string(record, "source_record_key")
        for record in indexes.by_import_batch_id.get(selected_import_batch_id, ())
    )


def _flat_record_import_batch_id(record: Mapping[str, Any]) -> str:
    import_batch = _mapping(record, "import_batch")
    return _optional_string(import_batch, "import_batch_id")


def _flat_record_complaint_ids(record: Mapping[str, Any]) -> tuple[str, ...]:
    values = _mapping(record, "original_values")
    candidate_values = [
        _optional_string(values, "complaint_id"),
    ]
    if _string(record, "entity_type") == "complaint":
        candidate_values.append(_optional_string(record, "stable_source_id"))
    return tuple(_unique_display_values(candidate_values))


def _selected_source_complaint_ids(
    selected_source_record: Mapping[str, Any],
) -> tuple[str, ...]:
    identity = _mapping(selected_source_record, "identity")
    values = _mapping(selected_source_record, "original_values")
    candidate_values = [
        _optional_string(identity, "stable_source_id"),
        _optional_string(values, "complaint_id"),
    ]
    return tuple(_unique_display_values(candidate_values))


def _append_source_index_value(
    index: dict[str, list[Mapping[str, Any]]],
    value: str,
    record: Mapping[str, Any],
) -> None:
    if value == "unknown":
        return
    index.setdefault(value, []).append(record)


def _freeze_source_index(
    index: Mapping[str, list[Mapping[str, Any]]],
) -> Mapping[str, tuple[Mapping[str, Any], ...]]:
    return {key: tuple(value) for key, value in index.items()}


def _unique_display_values(values: list[str]) -> list[str]:
    unique: list[str] = []
    for value in values:
        if value == "unknown" or value in unique:
            continue
        unique.append(value)
    return unique


def _sort_related_source_records(
    records: tuple[Mapping[str, Any], ...],
) -> list[Mapping[str, Any]]:
    return sorted(
        records,
        key=lambda record: (
            _SOURCE_CONTEXT_ENTITY_ORDER.get(_string(record, "entity_type"), 99),
            _string(record, "stable_source_id"),
        ),
    )


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
        values.append("allegation text: shown in source narrative section when loaded")
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
    if key == "facility_type":
        return _facility_type_classification(facility).display_value
    for candidate_key in _facility_context_keys(key):
        value = facility.get(candidate_key)
        if _has_display_value(value):
            return _display_value(value)
    return "unknown"


def _facility_type_classification(
    facility: Mapping[str, Any] | None,
) -> FacilityTypeClassification:
    if facility is None:
        return FacilityTypeClassification("unknown", is_source_provided=True)
    for candidate_key in _facility_context_keys("facility_type"):
        value = facility.get(candidate_key)
        if _has_display_value(value):
            return FacilityTypeClassification(
                _display_value(value),
                is_source_provided=True,
            )
    derived_value = _facility_type_from_facility_name(
        _facility_context_value(facility, "facility_name")
    )
    if derived_value is not None:
        return FacilityTypeClassification(derived_value, is_source_provided=False)
    return FacilityTypeClassification("unknown", is_source_provided=True)


def _facility_type_from_facility_name(facility_name: str) -> str | None:
    normalized = _normalized_facility_name_phrase(facility_name)
    if not normalized:
        return None
    if " FOSTER FAMILY AGENCY " in f" {normalized} ":
        return "Foster Family Agency"
    return None


def _normalized_facility_name_phrase(value: object) -> str:
    if not _has_display_value(value):
        return ""
    text = _display_value(value).casefold()
    normalized_chars = [char.upper() if char.isalnum() else " " for char in text]
    return " ".join("".join(normalized_chars).split())


def _facility_context_keys(key: str) -> tuple[str, ...]:
    aliases = {
        "external_facility_number": (
            "external_facility_number",
            "facility_number",
            "license_number",
        ),
        "facility_name": ("facility_name", "name"),
        "facility_type": ("facility_type", "facility_type_description", "type"),
        "license_status": ("license_status", "facility_status", "status"),
        "county": ("county", "county_name"),
    }
    return aliases.get(key, (key,))


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
            <p>After saving a note or status, return to this same CCLD request
            context and submit the request again to see queue progress and note/status cues
            derived from reviewer-created state.</p>
            <p>Status filters are reviewer-created queue views selected on the request queue;
            returning here preserves facility/date context, not assignment, record claiming, or
            persisted workflow state.</p>
            <dl>
                <dt>Facility ID to reuse</dt>
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


def _detail_return_context_date_range(return_context: CcldQueueReturnContext) -> str:
    if return_context.start_date is None and return_context.end_date is None:
        return "not provided"
    start_date = (
        _detail_display_date(return_context.start_date)
        if return_context.start_date
        else "earliest available"
    )
    end_date = (
        _detail_display_date(return_context.end_date)
        if return_context.end_date
        else "latest available"
    )
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


def _detail_date_summary(values: Mapping[str, Any]) -> str:
    parts = []
    for label, field_name in (
        ("Complaint received", "complaint_received_date"),
        ("Visit", "visit_date"),
        ("Report", "report_date"),
        ("Date signed", "date_signed"),
    ):
        value = values.get(field_name)
        if _has_display_value(value):
            parts.append(f"{label}: {_detail_display_date(_display_value(value))}")
    if not parts:
        return "No complaint or report dates listed"
    return "; ".join(parts)


def _detail_display_date(value: str) -> str:
    if not value or value == "unknown":
        return value
    try:
        parsed = datetime.strptime(value[:10], "%Y-%m-%d")
    except ValueError:
        return value
    return parsed.strftime("%m/%d/%Y")


def _detail_timeline_date(value: str) -> str:
    if not value or value == "unknown":
        return "Not available"
    return _detail_display_date(value)


def _has_display_value(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _glossary_term(term: str, definition: str, term_id: str) -> str:
    return (
        f'<dfn class="inline-glossary-term" tabindex="0" role="term" '
        f'aria-description="{_escape(definition)}" title="{_escape(definition)}" '
        f'data-definition="{_escape(definition)}" data-term-id="{_escape(term_id)}">'
        f'{_escape(term)}'
        f"</dfn>"
    )


def _render_reviewer_state_section(detail: Mapping[str, Any]) -> str:
    associated_state = _mapping(detail, "associated_reviewer_created_state")
    summary = _mapping(detail, "associated_reviewer_created_state_summary")
    state_records = _record_list(associated_state, "reviewer_created_state")
    if not state_records:
        return ""
    rows = "\n".join(
        _render_reviewer_state_row(record)
        for record in state_records
    )
    statuses = ", ".join(
        _REVIEWER_STATUS_LABELS.get(status, status)
        for status in _string_items(summary.get("reviewer_statuses_present", []))
    )
    if not statuses:
        statuses = "None recorded"
    latest_created_at = summary.get("latest_created_at")
    latest_display = (
        latest_created_at if isinstance(latest_created_at, str) else "None recorded"
    )
    return f"""<section class="detail-card reviewer-history-section" aria-labelledby="reviewer-state-heading">
      <p class="launch-kicker">Review</p>
      <h2 id="reviewer-state-heading">Saved notes and statuses</h2>
      <p>Notes and statuses do not change the complaint record.</p>
      <dl>
        <dt>Status recorded</dt>
        <dd>{_escape(statuses)}</dd>
        <dt>Last saved</dt>
        <dd>{_escape(latest_display)}</dd>
      </dl>
      <table>
          <caption>Saved notes and statuses for this complaint</caption>
          <thead>
            <tr>
              <th scope="col">Type</th>
              <th scope="col">Value</th>
              <th scope="col">Created at</th>
              <th scope="col">Created by</th>
              <th scope="col">Review guidance</th>
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
    return f"""<section class="review-status-panel" id="review-actions-heading" aria-labelledby="review-actions-title">
            <h2 id="review-actions-title">Status and note</h2>
            <dl class="summary-list">
                <dt>Current status</dt>
                <dd>{_escape(current_status)}</dd>
                <dt>Current note</dt>
                <dd>{_escape(note_presence)}</dd>
            </dl>
            {_render_status_form(source_record_key, return_context, summary)}
            {_render_note_form(source_record_key, return_context)}
        </section>"""


def _current_reviewer_status_text(summary: Mapping[str, Any]) -> str:
    statuses = tuple(_string_items(summary.get("reviewer_statuses_present", [])))
    if not statuses:
        return "No status"
    return _REVIEWER_STATUS_LABELS.get(statuses[0], statuses[0])


def _detail_note_presence_text(summary: Mapping[str, Any]) -> str:
    payload_kinds = tuple(_string_items(summary.get("payload_kinds_present", [])))
    if "reviewer_note_scaffold" in payload_kinds:
        return "Note added"
    return "No note"


def _recommended_review_action(summary: Mapping[str, Any]) -> str:
    has_status = bool(tuple(_string_items(summary.get("reviewer_statuses_present", []))))
    has_note = "reviewer_note_scaffold" in tuple(
        _string_items(summary.get("payload_kinds_present", []))
    )
    if not has_status and not has_note:
        return "Skip unless it helps."
    if has_status and not has_note:
        return "Add a note only if source-link or missing-field context needs explanation."
    if has_note and not has_status:
        return "Set a status only if queue progress needs it."
    return "Return to the queue or open the next record."


def _render_reviewer_state_row(record: Mapping[str, Any]) -> str:
    state_payload = _mapping(record, "state_payload")
    created_by = _mapping(record, "created_by")
    payload_kind = _optional_string(state_payload, "payload_kind")
    value = _reviewer_state_value(state_payload)
    actor_label = _actor_label(created_by)
    return f"""        <tr>
          <td>{_escape(_reviewer_state_kind_label(payload_kind or _string(record, 'state_kind')))}</td>
          <td>{_escape(value)}</td>
          <td>{_escape(_string(record, 'created_at'))}</td>
          <td>{_escape(actor_label)}</td>
          <td>Complaint record unchanged</td>
        </tr>"""


def _reviewer_state_kind_label(kind: str) -> str:
    if kind == "reviewer_note_scaffold":
        return "Note"
    if kind == "reviewer_status_scaffold":
        return "Status"
    return "Saved state"


def _reviewer_state_value(state_payload: Mapping[str, Any]) -> str:
    note_text = state_payload.get("note_text")
    if isinstance(note_text, str):
        return note_text
    reviewer_status = state_payload.get("reviewer_status")
    if isinstance(reviewer_status, str):
        return _REVIEWER_STATUS_LABELS.get(reviewer_status, reviewer_status)
    return "scaffold row"


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
    return f"""<section class="review-form-block">
      <form action="{REVIEWER_UI_NOTE_PATH}" method="post">
        <input type="hidden" name="source_record_key" value="{_escape(source_record_key)}">
                {_return_context_hidden_inputs(return_context)}
        <p>
                    <label for="note_text">Reviewer note</label>
                    <textarea id="note_text" name="note_text" rows="4" required
                        aria-describedby="note-text-help" placeholder="Add a short note for this record"></textarea>
                                            <span id="note-text-help">Notes do not change the complaint record.</span>
        </p>
                                <p><button class="secondary" type="submit">Save note</button></p>
      </form>
    </section>"""


def _render_status_form(
    source_record_key: str,
    return_context: CcldQueueReturnContext,
    summary: Mapping[str, Any],
) -> str:
    statuses = tuple(_string_items(summary.get("reviewer_statuses_present", [])))
    current_status = statuses[0] if statuses else None
    placeholder_selected = ' selected="selected"' if current_status is None else ""
    options = "\n".join(
        _render_status_option(status, selected=status == current_status)
        for status in REVIEWER_STATUS_VALUES
    )
    return f"""<section class="review-form-block">
      <form action="{REVIEWER_UI_STATUS_PATH}" method="post">
        <input type="hidden" name="source_record_key" value="{_escape(source_record_key)}">
                {_return_context_hidden_inputs(return_context)}
        <p>
          <label for="reviewer_status">Review status</label>
                    <select id="reviewer_status" name="reviewer_status" required
                        aria-describedby="reviewer-status-help">
            <option value="" disabled{placeholder_selected}>No status selected</option>
{options}
          </select>
                    <span id="reviewer-status-help">Status helps track review progress.</span>
        </p>
                                <p><button class="secondary" type="submit">Save status</button></p>
      </form>
    </section>"""


def _render_review_guidance_glossary_section(source_record: Mapping[str, Any]) -> str:
    original_values = _mapping(source_record, "original_values")
    return f"""<section class="detail-card" aria-labelledby="review-guidance-heading">
      <p class="launch-kicker">Guidance</p>
      <h2 id="review-guidance-heading">How to read this record</h2>
      <p>Review guidance for interpreting this selected public record. Defined terms use a dotted underline and show a short definition on hover or keyboard focus.</p>
      <ol>
        <li>{_glossary_term("Source-derived", "A value extracted from public source records.", "guidance-source-derived")} fields come from public {_glossary_term("CCLD", "California Community Care Licensing Division.", "guidance-ccld")} records or loaded public data; check the visible source context before relying on them.</li>
        <li>Review cues are prompts for attorney/tester attention, not findings.</li>
        <li>Check dates, status labels, and counts against the visible record context before using them in {_glossary_term("reviewer-created status/note", "Local review state added by a tester or reviewer; it is not a source fact.", "guidance-reviewer-created")} values, packet outputs, briefs, or readiness review.</li>
        <li>Absence of a cue does not prove absence of a concern.</li>
        <li>This page does not decide abuse, neglect, liability, rights deprivation, {_glossary_term("source completeness", "A completeness conclusion about public-source coverage; this page does not make that claim.", "guidance-source-completeness")}, or whether CCLD source coverage is complete.</li>
        <li>Next action: open the source context, review related records, use the packet/brief/readiness outputs, or send feedback if this record is confusing.</li>
      </ol>
      <p>Source-derived finding value {_escape(_optional_string(original_values, "finding"))} is displayed source context only.</p>
    </section>"""


def _render_glossary_items() -> str:
    terms = (
        ("CCLD", "California Community Care Licensing Division, the public source context used for these complaint records."),
        ("Citation", "A source-derived citation or deficiency cue that must be checked in the original CCLD record before use."),
        ("Type A citation", "A higher-priority CCLD citation label when present in source-derived values; this page does not verify legal effect."),
        ("Type B citation", "A CCLD citation label when present in source-derived values; check the source record for exact wording."),
        ("POC / Plan of Correction", "A plan-of-correction cue from source-derived values when loaded; completion may not be available in this record."),
        ("Substantiated", "A source-derived finding value. Do not treat the page display as an independent legal finding."),
        ("Unsubstantiated", "A source-derived finding value. Do not infer facility-wide conclusions from this page."),
        ("Inconclusive", "A source-derived finding value that should be read with the source record."),
        ("Complaint investigation report", "The CCLD public source record type represented by this detail page when loaded."),
        ("Source record support", "The visible source link, source type, loaded date, and field-level details used to check loaded values."),
        ("Report date used as proxy", "A loaded flag that means report date is being used as a proxy value; verify the source before using timing language."),
    )
    return "\n".join(
        f"""          <dt>{_escape(term)}</dt>
          <dd>{_escape(definition)}</dd>"""
        for term, definition in terms
    )


def _render_full_source_fields_details(
    identity: Mapping[str, Any],
    original_values: Mapping[str, Any],
) -> str:
    return f"""<details class="technical-details dense-table-details">
      <summary>Loaded record values</summary>
      <section aria-labelledby="source-derived-heading">
        <h2 id="source-derived-heading">Loaded record values</h2>
        <p>These are safe scalar fields for the selected complaint. Source narrative appears only in the source narrative excerpt section above.</p>
        <dl>
          <dt>Source record key</dt>
          <dd>{_escape(_string(identity, 'source_record_key'))}</dd>
          <dt>Entity type</dt>
          <dd>{_escape(_string(identity, 'entity_type'))}</dd>
          <dt>Stable source ID</dt>
          <dd>{_escape(_string(identity, 'stable_source_id'))}</dd>
          <dt>Facility ID</dt>
          <dd>{_escape(_optional_string(identity, 'facility_id'))}</dd>
        </dl>
        <table>
          <caption>Safe loaded values for the selected seeded record</caption>
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
    </details>"""


def _render_technical_operator_details(
    source_record: Mapping[str, Any],
    related_records: list[Mapping[str, Any]],
    return_context: CcldQueueReturnContext,
    workflow: Mapping[str, Any],
) -> str:
    identity = _mapping(source_record, "identity")
    source_record_key = _string(identity, "source_record_key")
    return f"""<details class="technical-details dense-table-details technical-operator-details">
      <summary>Technical and operator details</summary>
      {_render_detail_facility_context_cues(related_records, return_context)}
      {_render_detail_navigation(source_record_key, related_records, return_context)}
      {_render_detail_first_run_steps(source_record_key, related_records, return_context)}
      {_render_detail_feedback_guidance(source_record, related_records, return_context)}
      {_render_scope_notice(workflow)}
    </details>"""


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
        prompt="Describe source link, wording, keyboard flow, or next-step confusion.",
    )
    return f"""<section id="detail-feedback-heading" aria-labelledby="detail-feedback-title">
            <h2 id="detail-feedback-title">feedback item for this record</h2>
            <p>If this detail looks wrong or incomplete, use the feedback details on
            the CCLD request queue. Include the identifiers below and what looked missing,
            confusing, or unexpected.</p>
            <p>Mention the original source link status or field label when source information is
            hard to check. Send feedback when missing local fields make the next review step unclear.</p>
            <p>Notes and statuses are optional. Send feedback instead when you are unsure what
            the next step should be.</p>
            <dl>
                <dt>Facility ID</dt>
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
            <details class="technical-details">
                <summary>What to include in the feedback item</summary>
            <section aria-labelledby="record-feedback-handoff-heading">
                <h3 id="record-feedback-handoff-heading">Record feedback notes</h3>
                <p>Use the Feedback page. This detail section only helps
                you identify safe context to include.</p>
                <ul>
                    <li>Source link or source field that was missing or confusing.</li>
                    <li>Record value, date, finding, or flag that looked wrong or incomplete.</li>
                    <li>Whether this complaint seemed unexpected for the facility/date request.</li>
                    <li>Whether note/status save confirmation or return-to-queue behavior was unclear.</li>
                    <li>Any label, wording, keyboard flow, or next step that slowed review.</li>
                </ul>
            </section>
            <section aria-labelledby="feedback-checklist-bridge-heading">
                <h3 id="feedback-checklist-bridge-heading">feedback detail bridge</h3>
                <p>Use the same Send feedback flow for both queue observations and
                record-specific observations from this detail. Do not create a separate
                feedback workflow from this page.</p>
                <ul>
                    <li>Original source: note fields that were easy to confirm, missing, or confusing.</li>
                    <li>Complaint values: note dates, findings, flags, or values that were hard to trust.</li>
                    <li>Note/status: note whether save confirmation or queue progress was unclear.</li>
                    <li>Return-to-queue flow: note whether returning, refreshing, or choosing the next
                    record was confusing.</li>
                </ul>
            </section>
            </details>
            <ul>
                <li><a href="{_escape(ccld_request_href)}">Return to CCLD request or queue</a></li>
                <li><a href="{CCLD_HELP_PATH}">Open CCLD workflow help</a></li>
                <li><a href="{_escape(feedback_href)}">Send feedback with this record context</a></li>
            </ul>
        </section>"""


def _detail_feedback_request_context(return_context: CcldQueueReturnContext) -> str:
    if return_context.facility_number is None:
        return "not carried from a CCLD request queue"
    return (
        f"Facility ID {return_context.facility_number}; "
        f"date range {_return_context_date_range(return_context)}"
    )


def _render_status_option(status: str, *, selected: bool = False) -> str:
    label = _REVIEWER_STATUS_LABELS.get(status, status.replace("_", " "))
    selected_attr = ' selected="selected"' if selected else ""
    return f'            <option value="{_escape(status)}"{selected_attr}>{_escape(label)}</option>'


def _render_scope_notice(workflow: Mapping[str, Any]) -> str:
    scope = _mapping(workflow, "scope")
    scope_type = _escape(_string(scope, "scope_type"))
    scope_id = _escape(_string(scope, "scope_id"))
    return f"""<details class="technical-details diagnostic-details">
            <summary>Technical runtime details</summary>
            <p>This pilot environment uses an authorized local runtime context for reviewer actions.</p>
            <p>Current review scope: {scope_type} / {scope_id}.</p>
            <p>Reviewer-created notes/status remain separate from loaded records and audit rows.</p>
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
        "Open next flagged record uses another visible complaint record from this facility context."
        if next_record_href != ccld_request_href
        else "No separate next flagged record is visible; this opens the facility queue."
    )
    return f"""<section class="summary-card" aria-labelledby="form-result-heading">
            <p class="launch-kicker">Notes/status saved</p>
            <h2 id="form-result-heading">Notes/status saved</h2>
            <p>{_escape(_saved_action_sentence(saved_action))}</p>
            <p>Complaint fields remain unchanged, and no correction decision was submitted.</p>
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
                    <li>Public source link and source context</li>
                    <li>Public-source records</li>
                    <li>Correction workflow state</li>
                </ul>
            </section>
            <section aria-labelledby="queue-return-progress-heading">
                <h3 id="queue-return-progress-heading">Next</h3>
                <p>Return to the same facility queue or open the next flagged record.</p>
                <dl>
                    <dt>Same Facility ID</dt>
                    <dd>{_escape(_display_value(return_context.facility_number))}</dd>
                    <dt>Same date range</dt>
                    <dd>{_escape(_detail_return_context_date_range(return_context))}</dd>
                </dl>
            </section>
            <div class="form-actions">
                <a class="button" href="{_escape(ccld_request_href)}">Return to facility queue</a>
                <a class="button button-secondary" href="{_escape(next_record_href)}">Open next flagged record</a>
                <a class="button button-secondary" href="{_escape(detail_href)}">Refresh this reviewer detail</a>
            </div>
            <p class="helper-text">{_escape(next_record_note)}</p>
    </section>"""


def _saved_action_sentence(saved_action: str) -> str:
    if saved_action == "note":
        return "Note saved for this record."
    if saved_action == "status":
        return "Status saved for this record."
    return "Notes/status saved for this record."


def _saved_change_item(saved_action: str, saved_value: str | None) -> str:
    if saved_action == "note":
        return "<li>Note: added</li>"
    if saved_action == "status":
        value = saved_value or "saved"
        return f"<li>Status: {_escape(value)}</li>"
    return "<li>Notes/status: saved</li>"


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
    show_workflow_indicator: bool = False,
) -> str:
        return render_page_shell(
                title=title,
                heading=heading,
                main=main,
                skip_label="Skip to main reviewer content",
                nav_label="Reviewer navigation",
                eyebrow=None,
                actor_label=None,
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
            "Use the reviewer list, or retry with an actor that has "
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
    missing_record_heading: str = "Selected complaint record was not found",
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
                    "The selected complaint record is not available in this "
                    "review queue."
                ),
                guidance="Return to the reviewer list and select a complaint record.",
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
                "Use the reviewer list, or retry with valid values "
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
