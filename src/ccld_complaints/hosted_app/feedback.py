# ruff: noqa: E501

from __future__ import annotations

import html
import json
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

from ccld_complaints.hosted_app.auth import (
    FEEDBACK_SUBMIT_PERMISSION,
    AuthenticatedActor,
    AuthorizationTarget,
    HostedAccessScope,
    HostedAccountDisabledError,
    HostedAuthenticationRequiredError,
    HostedRoleDeniedError,
    HostedScopeDeniedError,
    require_permission,
)
from ccld_complaints.hosted_app.ui_shell import render_page_shell

FEEDBACK_PATH = "/feedback"
GITHUB_FEEDBACK_REPO_ENV = "GITHUB_FEEDBACK_REPO"
GITHUB_FEEDBACK_TOKEN_ENV = "GITHUB_FEEDBACK_TOKEN"
GITHUB_FEEDBACK_DEFAULT_LABELS_ENV = "GITHUB_FEEDBACK_DEFAULT_LABELS"
MAX_FEEDBACK_DESCRIPTION_LENGTH = 4000
FEEDBACK_TYPE_OPTIONS = (
    "Bug report",
    "Feature request",
    "Confusing page or workflow",
    "Packet/export issue",
    "Source/data concern",
    "New data source request",
)
ALLOWED_FEEDBACK_CONTEXT_PARAMETERS = (
    "feedback_type",
    "page_path",
    "workflow_area",
    "facility_number",
    "start_date",
    "end_date",
    "request_context_origin",
    "reviewer_status_filter",
    "retrieval_context",
    "retrieval_status",
    "retrieval_job_id",
    "complaint_control_number",
    "visible_workflow_state",
    "action_attempted",
    "prompt",
)
SAFE_WORKFLOW_AREAS = (
    "entry-orientation",
    "queue",
    "request-result",
    "retrieval-setup-required",
    "retrieval-job-summary",
    "retrieval-job-history",
    "retrieval-job-detail",
    "reviewer-detail",
    "save-confirmation",
    "packet-preview",
    "packet-draft",
    "help",
)
SAFE_RETRIEVAL_CONTEXTS = (
    "already-loaded-records",
    "controlled-job-submitted",
    "controlled-job-history",
    "controlled-job-detail",
    "setup-required",
    "no-jobs-yet",
)
SAFE_RETRIEVAL_STATUSES = (
    "not_submitted",
    "setup_required",
    "no_jobs_yet",
    "queued",
    "running",
    "completed",
    "completed_with_warnings",
    "failed",
    "blocked_by_validation",
    "rate_limited",
)
BASE_FEEDBACK_LABELS = ("user-feedback", "from-app", "needs-triage")
TYPE_LABELS = {
    "Bug report": "bug",
    "Feature request": "feature-request",
    "Confusing page or workflow": "workflow-confusion",
    "Packet/export issue": "packet-export",
    "Source/data concern": "source-data",
    "New data source request": "data-source-request",
}
SECRET_MARKERS = (
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


class GitHubIssueClient(Protocol):
    def create_issue(
        self,
        *,
        repo: str,
        token: str,
        title: str,
        body: str,
        labels: Sequence[str],
    ) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class GitHubFeedbackConfig:
    repo: str | None
    token: str | None
    default_labels: tuple[str, ...] = ()

    @property
    def configured(self) -> bool:
        return self.repo is not None and self.token is not None


@dataclass(frozen=True)
class FeedbackContext:
    actor: AuthenticatedActor | None
    scope: HostedAccessScope
    github_config: GitHubFeedbackConfig
    github_client: GitHubIssueClient
    now: Callable[[], datetime] = lambda: datetime.now(UTC)
    app_version: str | None = None
    app_mode: str | None = None


@dataclass(frozen=True)
class FeedbackSubmission:
    feedback_type: str
    description: str
    page_path: str | None
    handoff_context: FeedbackHandoffContext | None = None


@dataclass(frozen=True)
class FeedbackValidationResult:
    submission: FeedbackSubmission | None
    errors: tuple[str, ...]


@dataclass(frozen=True)
class FeedbackHandoffContext:
    page_path: str | None = None
    workflow_area: str | None = None
    facility_number: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    request_context_origin: str | None = None
    reviewer_status_filter: str | None = None
    retrieval_context: str | None = None
    retrieval_status: str | None = None
    retrieval_job_id: str | None = None
    complaint_control_number: str | None = None
    visible_workflow_state: str | None = None
    action_attempted: str | None = None
    prompt: str | None = None


@dataclass(frozen=True)
class GitHubRestIssueClient:
    api_base_url: str = "https://api.github.com"

    def create_issue(
        self,
        *,
        repo: str,
        token: str,
        title: str,
        body: str,
        labels: Sequence[str],
    ) -> Mapping[str, Any]:
        payload = json.dumps(
            {"title": title, "body": body, "labels": list(labels)},
            sort_keys=True,
        ).encode()
        request = Request(
            f"{self.api_base_url}/repos/{repo}/issues",
            data=payload,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "User-Agent": "ccld-feedback-intake",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            method="POST",
        )
        with urlopen(request, timeout=15) as response:
            loaded = json.loads(response.read().decode())
        if not isinstance(loaded, Mapping):
            raise RuntimeError("GitHub issue response was not an object.")
        return dict(loaded)


def load_github_feedback_config(
    environ: Mapping[str, str] | None = None,
) -> GitHubFeedbackConfig:
    active_environ = os.environ if environ is None else environ
    repo = _optional_env(active_environ, GITHUB_FEEDBACK_REPO_ENV)
    token = _optional_env(active_environ, GITHUB_FEEDBACK_TOKEN_ENV)
    default_labels = _labels_from_env(
        _optional_env(active_environ, GITHUB_FEEDBACK_DEFAULT_LABELS_ENV)
    )
    if repo is not None and not _valid_repo(repo):
        raise ValueError(f"{GITHUB_FEEDBACK_REPO_ENV} must use owner/repo format.")
    return GitHubFeedbackConfig(repo=repo, token=token, default_labels=default_labels)


def default_feedback_context() -> FeedbackContext:
    return FeedbackContext(
        actor=None,
        scope=HostedAccessScope("seeded_corpus", "seeded-ccld-fixture-2026-06-13"),
        github_config=load_github_feedback_config(),
        github_client=GitHubRestIssueClient(),
    )


def route_feedback_response(
    path: str,
    context: FeedbackContext | None,
    *,
    method: str = "GET",
    request_body: bytes | None = None,
) -> tuple[int, str, bytes]:
    active_context = context or default_feedback_context()
    parsed_url = urlparse(path)
    if parsed_url.path != FEEDBACK_PATH:
        return _html_response(
            404,
            _page(
                title="Feedback page not found",
                heading="Feedback page not found",
                main="<p>The requested feedback page was not found.</p>",
            ),
        )
    if method == "GET":
        query_values = parse_qs(parsed_url.query, keep_blank_values=True)
        handoff_context = _feedback_handoff_context_from_values(query_values)
        return _html_response(
            200,
            render_feedback_page(
                active_context,
                selected_type=_first_form_value(query_values, "feedback_type"),
                handoff_context=handoff_context,
            ),
        )
    if method == "POST":
        return _post_feedback_response(request_body, active_context)
    return _html_response(
        405,
        _page(
            title="Feedback method unavailable",
            heading="Feedback method unavailable",
            main="<p>The feedback page supports browser GET and form POST only.</p>",
        ),
    )


def render_feedback_page(
    context: FeedbackContext,
    *,
    selected_type: str = "",
    handoff_context: FeedbackHandoffContext | None = None,
) -> str:
    form_values = {"feedback_type": [selected_type]} if selected_type in FEEDBACK_TYPE_OPTIONS else {}
    if handoff_context:
        form_values.update(_feedback_handoff_context_form_values(handoff_context))
    issue_starter = _feedback_issue_starter(handoff_context)
    if issue_starter:
        form_values["description"] = [issue_starter]
    return _page(
                title="Send feedback",
                heading="Send feedback",
        main=f"""
        <section class="hero-card" aria-labelledby="feedback-purpose-heading">
            <p class="launch-kicker">Tester feedback</p>
            <h2 id="feedback-purpose-heading">Send safe review feedback</h2>
            <p>Choose the feedback type and describe what blocked Request Records, Job Status, record review, packet/readiness review, source/data review, wording, or keyboard flow.</p>
            <p class="helper-text">Actionable tester feedback names the page or route, what you tried first, what you expected, what happened instead, and whether the issue blocked review.</p>
        </section>
        <section class="notice-card" aria-labelledby="actionable-feedback-heading">
            <h2 id="actionable-feedback-heading">What makes feedback actionable</h2>
            <ul>
                <li>Name the workflow area: facility lookup, Request Records, loaded queue, reviewer detail, packet/brief, readiness checklist, or feedback.</li>
                <li>Describe the confusing loaded-context cue, source traceability cue, record order, note/status action, packet/readiness item, label, or keyboard step.</li>
                <li>Say what would have helped you continue review.</li>
            </ul>
            <p>Do not include raw source narrative, secrets, private URLs, provider claims, stack traces, server paths, legal conclusions, or source-completeness claims.</p>
        </section>
        {_feedback_context_panel(handoff_context)}
        <div class="support-layout">
            {_feedback_issue_starter_panel(issue_starter)}
            {_feedback_form(form_values)}
        </div>
    {_configuration_notice(context.github_config)}
        <details class="technical-details">
            <summary>Useful feedback examples</summary>
            <ul>
                <li>I was trying to request records from Request Records, but the Job Status notice did not make the next step clear. I expected to know whether to wait, retry, or review already-loaded records. The visible context showed the facility number and date range.</li>
                <li>I was on the reviewer queue after applying the reviewer-status filter. The shown count and empty-state recovery action looked confusing. I expected a clear way back to the full loaded queue. The visible context showed the queue page and active filter.</li>
                <li>I was reviewing a complaint detail page and checking source traceability before adding a note. A source-derived date looked wrong or incomplete, but the guidance did not make clear whether to add a cautious note or use feedback. The visible context showed the detail page and complaint/control identifier.</li>
                <li>I was preparing packet/readiness review and one prioritized record looked missing or unexpected in the packet content. I expected the packet cue to explain what to review next. The visible context showed the packet preview step and facility/date context.</li>
                <li>I was using the first-time tester path from the task guide. The transition from facility lookup to Request Records and loaded records was confusing. I expected the page to show which workflow step came next. The visible context showed the entry-orientation step.</li>
            </ul>
        </details>
""",
    )


def _feedback_type_href(feedback_type: str) -> str:
    return f"{FEEDBACK_PATH}?{urlencode({'feedback_type': feedback_type})}"


def feedback_href(**context_values: str | None) -> str:
    raw_values = {
        key: [value]
        for key in ALLOWED_FEEDBACK_CONTEXT_PARAMETERS
        if (value := context_values.get(key))
    }
    context = _feedback_handoff_context_from_values(raw_values)
    candidate_values: dict[str, str | None] = {}
    feedback_type = context_values.get("feedback_type")
    if feedback_type in FEEDBACK_TYPE_OPTIONS:
        candidate_values["feedback_type"] = feedback_type
    candidate_values.update(
        {
            "page_path": context.page_path,
            "workflow_area": context.workflow_area,
            "facility_number": context.facility_number,
            "start_date": context.start_date,
            "end_date": context.end_date,
            "request_context_origin": context.request_context_origin,
            "reviewer_status_filter": context.reviewer_status_filter,
            "retrieval_context": context.retrieval_context,
            "retrieval_status": context.retrieval_status,
            "retrieval_job_id": context.retrieval_job_id,
            "complaint_control_number": context.complaint_control_number,
            "visible_workflow_state": context.visible_workflow_state,
            "action_attempted": context.action_attempted,
            "prompt": context.prompt,
        }
    )
    safe_values = {
        key: value
        for key in ALLOWED_FEEDBACK_CONTEXT_PARAMETERS
        if (value := candidate_values.get(key)) is not None
    }
    if not safe_values:
        return FEEDBACK_PATH
    return f"{FEEDBACK_PATH}?{urlencode(safe_values)}"


def _feedback_handoff_context_from_values(
    values: Mapping[str, list[str]],
) -> FeedbackHandoffContext:
    return FeedbackHandoffContext(
        page_path=_safe_page_path(_first_form_value(values, "page_path")),
        workflow_area=_safe_choice(_first_form_value(values, "workflow_area"), SAFE_WORKFLOW_AREAS),
        facility_number=_safe_short_value(_first_form_value(values, "facility_number"), digits_only=True),
        start_date=_safe_date_value(_first_form_value(values, "start_date")),
        end_date=_safe_date_value(_first_form_value(values, "end_date")),
        request_context_origin=_safe_short_value(_first_form_value(values, "request_context_origin")),
        reviewer_status_filter=_safe_short_value(_first_form_value(values, "reviewer_status_filter")),
        retrieval_context=_safe_choice(
            _first_form_value(values, "retrieval_context"), SAFE_RETRIEVAL_CONTEXTS
        ),
        retrieval_status=_safe_choice(
            _first_form_value(values, "retrieval_status"), SAFE_RETRIEVAL_STATUSES
        ),
        retrieval_job_id=_safe_retrieval_job_id(_first_form_value(values, "retrieval_job_id")),
        complaint_control_number=_safe_short_value(_first_form_value(values, "complaint_control_number"), max_length=80),
        visible_workflow_state=_safe_short_value(
            _first_form_value(values, "visible_workflow_state"), max_length=140
        ),
        action_attempted=_safe_short_value(
            _first_form_value(values, "action_attempted"), max_length=140
        ),
        prompt=_safe_short_value(_first_form_value(values, "prompt"), max_length=220),
    )


def _feedback_context_panel(context: FeedbackHandoffContext | None) -> str:
    if context is None:
        return ""
    rows = tuple(_feedback_context_rows(context))
    if not rows:
        return ""
    row_markup = "\n".join(
        f"        <dt>{html.escape(label)}</dt>\n        <dd>{html.escape(value)}</dd>"
        for label, value in rows
    )
    return f"""        <section class="summary-card" aria-labelledby="feedback-context-heading">
            <h2 id="feedback-context-heading">Feedback context from review workflow</h2>
            <p>This context was carried from the review page you came from as a triage helper.</p>
            <dl>
{row_markup}
            </dl>
            <p>Describe what was confusing, missing, unexpected, or hard to use, including active
            reviewer-created status filter confusion, shown-count or total-count confusion,
            filtered-empty recovery problems, source traceability concerns such as source URL, raw SHA-256 hash, connector metadata,
            retrieval timestamp, Job Status history/detail context, source document/report marker, or traceability value
            missing; source-confidence next-step confusion for missing source values,
            proxy-related cues, or cautious note/status wording; possible correction concerns where a source-derived value looked wrong or
            incomplete after checking traceability; or uncertainty about whether to use a
            reviewer-created note or feedback; packet/readiness confusion, browser copy or
            print confusion, or missing or unexpected records in packet content. Do not include
            raw source narrative, secrets, provider claims, private URLs, stack traces, server
            paths, environment values, or legal conclusions.</p>
        </section>"""


def _feedback_issue_starter_panel(starter: str) -> str:
    if not starter:
        return ""
    return """    <section class="summary-card" aria-labelledby="feedback-starter-heading">
      <h2 id="feedback-starter-heading">Suggested issue starter</h2>
      <p><strong>Edit this before submitting.</strong> This starter uses only safe handoff context from the screen you came from.</p>
      <p>Do not paste secrets, private URLs, stack traces, raw source narrative, or unrelated personal information.</p>
    </section>"""


def _feedback_issue_starter(context: FeedbackHandoffContext | None) -> str:
    if context is None or not _feedback_context_rows(context):
        return ""
    surface = _feedback_starter_surface(context)
    focus = "Job Status information" if _has_retrieval_context(context) else "review workflow information"
    lines = [f"I am reporting confusion about the {focus} on {surface}."]
    if context.facility_number:
        lines.append(f"Facility/license: {context.facility_number}")
    date_range = _feedback_starter_date_range(context)
    if date_range:
        lines.append(f"Date range: {date_range}")
    if context.retrieval_context:
        lines.append(f"Job context: {context.retrieval_context}")
    if context.retrieval_status:
        lines.append(f"Job status: {context.retrieval_status}")
    if context.retrieval_job_id:
        lines.append(f"Job ID: {context.retrieval_job_id}")
    if context.prompt:
        lines.extend(["", f"Prompt from previous screen: {context.prompt}"])
    lines.extend(["", "What was confusing:", "[Edit this before submitting.]"])
    return "\n".join(lines)


def _feedback_starter_surface(context: FeedbackHandoffContext) -> str:
    if context.workflow_area:
        return context.workflow_area.replace("-", " ")
    return "the review workflow page"


def _feedback_starter_date_range(context: FeedbackHandoffContext) -> str:
    if context.start_date and context.end_date:
        return f"{context.start_date} to {context.end_date}"
    if context.start_date:
        return f"starting {context.start_date}"
    if context.end_date:
        return f"ending {context.end_date}"
    return ""


def _has_retrieval_context(context: FeedbackHandoffContext) -> bool:
    return any((context.retrieval_context, context.retrieval_status, context.retrieval_job_id))


def _feedback_context_rows(context: FeedbackHandoffContext | None) -> list[tuple[str, str]]:
    if context is None:
        return []
    fields = (
        ("Workflow area", context.workflow_area),
        ("Page path", context.page_path),
        ("Facility/license number", context.facility_number),
        ("Start date", context.start_date),
        ("End date", context.end_date),
        ("Request origin", context.request_context_origin),
        ("Reviewer-status filter", context.reviewer_status_filter),
        ("Job context", context.retrieval_context),
        ("Job status", context.retrieval_status),
        ("Job ID", context.retrieval_job_id),
        ("Complaint/control identifier", context.complaint_control_number),
        ("Visible workflow state", context.visible_workflow_state),
        ("Action attempted", context.action_attempted),
        ("Suggested prompt", context.prompt),
    )
    return [(label, value) for label, value in fields if value]


def _feedback_handoff_context_form_values(
    context: FeedbackHandoffContext,
) -> dict[str, list[str]]:
    values = {
        "page_path": context.page_path,
        "workflow_area": context.workflow_area,
        "facility_number": context.facility_number,
        "start_date": context.start_date,
        "end_date": context.end_date,
        "request_context_origin": context.request_context_origin,
        "reviewer_status_filter": context.reviewer_status_filter,
        "retrieval_context": context.retrieval_context,
        "retrieval_status": context.retrieval_status,
        "retrieval_job_id": context.retrieval_job_id,
        "complaint_control_number": context.complaint_control_number,
        "visible_workflow_state": context.visible_workflow_state,
        "action_attempted": context.action_attempted,
        "prompt": context.prompt,
    }
    return {key: [value] for key, value in values.items() if value is not None}


def _safe_choice(value: str, allowed: Sequence[str]) -> str | None:
    if value in allowed:
        return value
    return None


def _safe_date_value(value: str) -> str | None:
    if len(value) == 10 and value[4] == "-" and value[7] == "-" and value.replace("-", "").isdigit():
        return value
    return None


def _safe_retrieval_job_id(value: str) -> str | None:
    if not value or len(value) > 96:
        return None
    if _contains_secret_marker(value):
        return None
    if not all(ch.isalnum() or ch in "_.:-" for ch in value):
        return None
    return value


def _safe_short_value(
    value: str,
    *,
    max_length: int = 80,
    digits_only: bool = False,
) -> str | None:
    if not value:
        return None
    if len(value) > max_length:
        value = value[:max_length]
    if _contains_secret_marker(value) or "http" in value.casefold() or "\\" in value:
        return None
    if digits_only and not value.isdigit():
        return None
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -_:/.,?()")
    cleaned = "".join(ch for ch in value if ch in allowed).strip()
    return cleaned or None


def validate_feedback_submission(
    form_values: Mapping[str, list[str]],
) -> FeedbackValidationResult:
    feedback_type = _first_form_value(form_values, "feedback_type")
    description = _first_form_value(form_values, "description")
    handoff_context = _feedback_handoff_context_from_values(
        {
            key: form_values[key]
            for key in ALLOWED_FEEDBACK_CONTEXT_PARAMETERS
            if key in form_values
        }
    )
    page_path = handoff_context.page_path
    errors: list[str] = []
    if feedback_type not in FEEDBACK_TYPE_OPTIONS:
        errors.append("Choose a supported feedback type.")
    if not description:
        errors.append("Describe the feedback before submitting.")
    elif len(description) > MAX_FEEDBACK_DESCRIPTION_LENGTH:
        errors.append(
            f"Feedback description must be {MAX_FEEDBACK_DESCRIPTION_LENGTH} characters or fewer."
        )
    if _contains_secret_marker(description):
        errors.append(
            "Feedback must not include secrets, credentials, or private browser/session values."
        )
    if errors:
        return FeedbackValidationResult(submission=None, errors=tuple(errors))
    return FeedbackValidationResult(
        submission=FeedbackSubmission(
            feedback_type=feedback_type,
            description=description,
            page_path=page_path,
            handoff_context=handoff_context,
        ),
        errors=(),
    )


def feedback_labels(feedback_type: str, default_labels: Sequence[str] = ()) -> tuple[str, ...]:
    labels: list[str] = []
    for label in (*BASE_FEEDBACK_LABELS, *default_labels, TYPE_LABELS[feedback_type]):
        if label and label not in labels:
            labels.append(label)
    return tuple(labels)


def build_issue_title(submission: FeedbackSubmission) -> str:
    surface = _safe_title_surface(submission.handoff_context)
    if surface:
        return f"RecordsTracker feedback: {submission.feedback_type} on {surface}"
    return f"RecordsTracker feedback: {submission.feedback_type}"


def build_issue_body(
    submission: FeedbackSubmission,
    *,
    submitted_at: datetime,
    actor: AuthenticatedActor | None,
    app_version: str | None = None,
    app_mode: str | None = None,
) -> str:
    lines = [
        "## Feedback",
        "",
        f"Type: {submission.feedback_type}",
        f"Submitted at: {submitted_at.isoformat()}",
        "Private material should not be included in RecordsTracker feedback.",
    ]
    if submission.page_path is not None:
        lines.append(f"Page path: {submission.page_path}")
    actor_label = _safe_actor_label(actor)
    if actor_label is not None:
        lines.append(f"Submitted by: {actor_label}")
    if app_version is not None and app_version.strip():
        lines.append(f"App version: {app_version.strip()}")
    if app_mode is not None and app_mode.strip():
        lines.append(f"App mode: {app_mode.strip()}")
    context_rows = _feedback_context_rows(submission.handoff_context)
    if context_rows:
        lines.extend(["", "## Safe Captured Context", ""])
        lines.extend(f"- {label}: {value}" for label, value in context_rows)
    lines.extend(["", "## Description", "", submission.description])
    body = "\n".join(lines)
    if _contains_secret_marker(body):
        raise ValueError("Issue body contains secret-like content.")
    return body


def _post_feedback_response(
    request_body: bytes | None,
    context: FeedbackContext,
) -> tuple[int, str, bytes]:
    form_values = _form_values(request_body)
    validation = validate_feedback_submission(form_values)
    if validation.submission is None:
        return _html_response(
            400,
            _page(
                title="Feedback was not submitted",
                heading="Feedback was not submitted",
                main=f"""
    {_configuration_notice(context.github_config)}
    {_error_summary(validation.errors)}
    {_feedback_form(form_values)}
""",
            ),
        )
    try:
        require_permission(
            context.actor,
            permission=FEEDBACK_SUBMIT_PERMISSION,
            scope=context.scope,
            target=AuthorizationTarget("auth_access", "github-feedback"),
        )
    except HostedAuthenticationRequiredError as error:
        return _feedback_blocked_response(401, "Feedback requires sign-in", str(error))
    except (HostedAccountDisabledError, HostedRoleDeniedError, HostedScopeDeniedError) as error:
        return _feedback_blocked_response(403, "Feedback was blocked", str(error))

    if not context.github_config.configured:
        submission = validation.submission
        submitted_at = context.now()
        return _html_response(
            503,
            _page(
                title="Feedback is not configured",
                heading="Feedback is not configured",
                main=f"""
    {_configuration_notice(context.github_config)}
    <section aria-labelledby="feedback-unconfigured-heading">
      <h2 id="feedback-unconfigured-heading">Feedback was not sent</h2>
      <p>GitHub feedback intake is not configured on this server. No GitHub issue was created.</p>
    </section>
    {_feedback_confirmation_summary(submission, status_message="Review what you entered before copying it to the agreed tester support channel.")}
    {_feedback_copyable_summary(submission, submitted_at=submitted_at)}
    {_feedback_next_steps()}
    {_feedback_form(form_values)}
""",
            ),
        )

    submission = validation.submission
    labels = feedback_labels(submission.feedback_type, context.github_config.default_labels)
    try:
        issue_body = build_issue_body(
            submission,
            submitted_at=context.now(),
            actor=context.actor,
            app_version=context.app_version,
            app_mode=context.app_mode,
        )
        issue = _create_github_issue_with_label_fallback(
            context=context,
            submission=submission,
            issue_body=issue_body,
            labels=labels,
        )
    except Exception:
        submitted_at = context.now()
        return _html_response(
            502,
            _page(
                title="Feedback could not be sent",
                heading="Feedback could not be sent",
                main=f"""
    <section aria-labelledby="feedback-failure-heading">
      <h2 id="feedback-failure-heading">Feedback could not be sent</h2>
      <p>The server could not create the GitHub issue. No token or private details are shown.</p>
    </section>
    {_feedback_confirmation_summary(submission, status_message="Review what you entered before trying again or copying it to the agreed tester support channel.")}
    {_feedback_copyable_summary(submission, submitted_at=submitted_at)}
    {_feedback_next_steps()}
""",
            ),
        )
    issue_number = issue.get("number")
    issue_text = f"Issue #{issue_number}" if isinstance(issue_number, int) else "GitHub issue"
    issue_url = _safe_github_issue_url(issue.get("html_url"), context.github_config.repo)
    issue_link = (
        f'<p><a href="{html.escape(issue_url)}">Open created GitHub issue</a></p>'
        if issue_url
        else ""
    )
    return _html_response(
        201,
        _page(
            title="Feedback submitted",
            heading="Feedback submitted",
            main=f"""
    <section aria-labelledby="feedback-success-heading">
      <h2 id="feedback-success-heading">Feedback submitted</h2>
      <p>{html.escape(issue_text)} was created for triage.</p>
      {issue_link}
      <p>Labels: {html.escape(', '.join(labels))}</p>
    </section>
    {_feedback_confirmation_summary(submission, status_message="Review the submitted details below.")}
    {_feedback_next_steps()}
""",
        ),
    )


def _feedback_confirmation_summary(
    submission: FeedbackSubmission,
    *,
    status_message: str,
) -> str:
    field_rows = [
        ("Feedback type", submission.feedback_type),
        ("Submitted page path", submission.page_path or FEEDBACK_PATH),
        ("Description", submission.description),
    ]
    field_markup = "\n".join(
        f"        <dt>{html.escape(label)}</dt>\n        <dd>{html.escape(value)}</dd>"
        for label, value in field_rows
    )
    context_markup = _feedback_submitted_context_summary(submission.handoff_context)
    return f"""    <section class="summary-card" aria-labelledby="feedback-confirmation-summary-heading">
      <h2 id="feedback-confirmation-summary-heading">Submitted feedback summary</h2>
      <p>{html.escape(status_message)}</p>
      <dl>
{field_markup}
      </dl>
    </section>
{context_markup}"""


def _feedback_copyable_summary(submission: FeedbackSubmission, *, submitted_at: datetime | None = None) -> str:
    safe_summary = _manual_feedback_summary(submission, submitted_at=submitted_at)
    return f"""    <section class="summary-card" aria-labelledby="feedback-copyable-summary-heading">
      <h2 id="feedback-copyable-summary-heading">Copyable feedback summary</h2>
      <p>Copy this safe summary to the agreed tester support channel.</p>
      <textarea id="feedback-copyable-summary" rows="12" readonly>{html.escape(safe_summary)}</textarea>
    </section>"""


def _feedback_submitted_context_summary(
    context: FeedbackHandoffContext | None,
) -> str:
    if context is None:
        return ""
    rows = tuple(_feedback_context_rows(context))
    if not rows:
        return ""
    row_markup = "\n".join(
        f"        <dt>{html.escape(label)}</dt>\n        <dd>{html.escape(value)}</dd>"
        for label, value in rows
    )
    return f"""    <section class="summary-card" aria-labelledby="feedback-submitted-context-heading">
      <h2 id="feedback-submitted-context-heading">Submitted safe context</h2>
      <p>Only allowlisted, bounded context from the feedback form is shown here.</p>
      <dl>
{row_markup}
      </dl>
    </section>"""


def _manual_feedback_summary(
    submission: FeedbackSubmission,
    *,
    submitted_at: datetime | None = None,
) -> str:
    lines = [
        "RecordsTracker feedback",
        f"Type: {submission.feedback_type}",
        f"Submitted page path: {submission.page_path or FEEDBACK_PATH}",
    ]
    if submitted_at is not None:
        lines.append(f"Prepared at: {submitted_at.isoformat()}")
    context_rows = _feedback_context_rows(submission.handoff_context)
    if context_rows:
        lines.extend(["", "Safe context:"])
        lines.extend(f"- {label}: {value}" for label, value in context_rows)
    lines.extend(
        [
            "",
            "Description:",
            submission.description,
            "",
            "Private material, credentials, session values, raw artifacts, raw server paths, stack traces, and private URLs should not be included.",
        ]
    )
    return "\n".join(lines)


def _feedback_next_steps() -> str:
    return f"""    <section class="notice-card" aria-labelledby="feedback-next-steps-heading">
      <h2 id="feedback-next-steps-heading">What to do next</h2>
      <ul>
        <li><a href="/">Return to the tester task guide</a> if you want to restart the guided review path.</li>
        <li><a href="/ccld/records/request">Continue review</a> with the same facility/date context or request another loaded CCLD queue.</li>
        <li><a href="{FEEDBACK_PATH}">Add more detail</a> if the feedback above is incomplete.</li>
      </ul>
    </section>"""


def _feedback_blocked_response(status: int, heading: str, message: str) -> tuple[int, str, bytes]:
    return _html_response(
        status,
        _page(title=heading, heading=heading, main=f"<p>{html.escape(message)}</p>"),
    )


def _configuration_notice(config: GitHubFeedbackConfig) -> str:
    if config.configured:
        return """    <section aria-labelledby="feedback-configured-heading">
      <h2 id="feedback-configured-heading">GitHub issue intake is configured</h2>
      <p>Submitting this form creates a server-side GitHub issue for triage.</p>
    </section>"""
    return """    <section class="notice-card" aria-labelledby="feedback-unconfigured-heading">
      <h2 id="feedback-unconfigured-heading">How feedback is submitted</h2>
      <p>Note: Server-side GitHub issue intake is not configured on this deployment.
      Fill in the form, then copy or forward the description to the agreed tester support channel.
      Feedback is still useful for the operator to review.</p>
    </section>"""


def _feedback_form(form_values: Mapping[str, list[str]]) -> str:
    selected_type = _first_form_value(form_values, "feedback_type")
    description = _first_form_value(form_values, "description")
    if _contains_secret_marker(description):
        description = ""
    escaped_description = html.escape(description)
    page_path = _safe_page_path(_first_form_value(form_values, "page_path")) or FEEDBACK_PATH
    handoff_context = _feedback_handoff_context_from_values(
        {
            key: form_values[key]
            for key in ALLOWED_FEEDBACK_CONTEXT_PARAMETERS
            if key in form_values
        }
    )
    context_inputs = _feedback_context_form_controls(handoff_context)
    options = "\n".join(
        _feedback_type_option(option, selected_type) for option in FEEDBACK_TYPE_OPTIONS
    )
    textarea = (
        '<textarea id="description" name="description" rows="8" '
        f'maxlength="{MAX_FEEDBACK_DESCRIPTION_LENGTH}" required '
        'aria-describedby="description-help">'
        f"{escaped_description}</textarea>"
    )
    return f"""    <section aria-labelledby="feedback-form-heading">
      <h2 id="feedback-form-heading">Send tester feedback</h2>
      <form action="{FEEDBACK_PATH}" method="post">
        <div>
          <label for="feedback_type">Feedback type</label>
                    <select id="feedback_type" name="feedback_type" required aria-describedby="feedback-type-help">
            <option value="">Choose feedback type</option>
{options}
          </select>
          <p id="feedback-type-help" class="helper-text">Choose the category that best fits the route, action, loaded-context cue, packet/readiness cue, or keyboard step that was confusing.</p>
        </div>
        <section class="notice-card" aria-labelledby="feedback-safety-heading">
          <h3 id="feedback-safety-heading">Do not include private material</h3>
          <p>Do not include private facts, credentials, legal strategy, privileged work product,
          private URLs, secrets, tokens, provider claims, raw source narrative, raw artifact material,
          server paths, connection details, or unrelated sensitive details.</p>
        </section>
        <p>
          <label for="description">Description</label>
                    {textarea}
                    <span id="description-help">Describe the page, action, expected result, actual result, loaded-context cue, source traceability cue, packet/readiness concern, browser copy issue, or print issue without private material.</span>
        </p>
        <p>
          <label for="page_path">Submitted page path</label>
          <input id="page_path" name="page_path" type="text" value="{html.escape(page_path)}" readonly aria-describedby="page-path-help">
          <span id="page-path-help">This visible context is included with the feedback when submitted.</span>
        </p>
        {context_inputs}
        <p><button type="submit">Submit feedback</button></p>
      </form>
    </section>"""


def _feedback_context_form_controls(context: FeedbackHandoffContext) -> str:
    controls = []
    for name, label, value in (
        ("workflow_area", "Workflow area", context.workflow_area),
        ("facility_number", "Facility/license number", context.facility_number),
        ("start_date", "Start date", context.start_date),
        ("end_date", "End date", context.end_date),
        ("request_context_origin", "Request origin", context.request_context_origin),
        ("reviewer_status_filter", "Reviewer-status filter", context.reviewer_status_filter),
        ("retrieval_context", "Job context", context.retrieval_context),
        ("retrieval_status", "Job status", context.retrieval_status),
        ("retrieval_job_id", "Job ID", context.retrieval_job_id),
        ("complaint_control_number", "Complaint/control identifier", context.complaint_control_number),
        ("visible_workflow_state", "Visible workflow state", context.visible_workflow_state),
        ("action_attempted", "Action attempted", context.action_attempted),
        ("prompt", "Suggested prompt", context.prompt),
    ):
        if value:
            escaped_name = html.escape(name)
            escaped_value = html.escape(value)
            input_id = f"feedback-context-{escaped_name}"
            controls.append(
                f"""          <p>
            <label for="{input_id}">{html.escape(label)}</label>
            <input id="{input_id}" name="{escaped_name}" type="text" value="{escaped_value}" readonly>
          </p>"""
            )
    if not controls:
        return ""
    return f"""        <section class="summary-card" aria-labelledby="feedback-visible-context-heading">
          <h3 id="feedback-visible-context-heading">Visible context included with this feedback</h3>
{chr(10).join(controls)}
        </section>"""


def _feedback_type_option(option: str, selected_type: str) -> str:
    selected = ' selected="selected"' if option == selected_type else ""
    return (
        f'            <option value="{html.escape(option)}"{selected}>'
        f"{html.escape(option)}</option>"
    )


def _error_summary(errors: Sequence[str]) -> str:
    items = "\n".join(f"        <li>{html.escape(error)}</li>" for error in errors)
    return f"""    <section aria-labelledby="feedback-errors-heading">
      <h2 id="feedback-errors-heading">Fix feedback form errors</h2>
      <ul>
{items}
      </ul>
    </section>"""


def _page(*, title: str, heading: str, main: str) -> str:
        return render_page_shell(
                title=title,
                heading=heading,
                main=main,
                skip_label="Skip to main feedback content",
                nav_label="Feedback navigation",
                eyebrow="Safe tester feedback for the review workflow.",
                extra_nav_links=(),
                active_path=FEEDBACK_PATH,
                step_id="feedback",
                next_action="Choose feedback type and submit useful details",
        )


def _form_values(request_body: bytes | None) -> Mapping[str, list[str]]:
    if not request_body:
        return {}
    return parse_qs(request_body.decode(), keep_blank_values=True)


def _first_form_value(form_values: Mapping[str, list[str]], key: str) -> str:
    values = form_values.get(key, [])
    if not values:
        return ""
    return values[0].strip()


def _optional_env(environ: Mapping[str, str], key: str) -> str | None:
    value = environ.get(key, "").strip()
    return value or None


def _labels_from_env(raw_labels: str | None) -> tuple[str, ...]:
    if raw_labels is None:
        return ()
    labels = []
    for label in raw_labels.split(","):
        normalized = label.strip()
        if normalized and normalized not in labels:
            labels.append(normalized)
    return tuple(labels)


def _valid_repo(repo: str) -> bool:
    parts = repo.split("/")
    return len(parts) == 2 and all(part.strip() for part in parts)


def _contains_secret_marker(value: str) -> bool:
    lowered = value.casefold()
    return any(marker in lowered for marker in SECRET_MARKERS)


def _safe_page_path(value: str) -> str | None:
    if not value:
        return None
    if value.startswith("/") and not value.startswith("//") and "http" not in value.casefold():
        return value[:200]
    return None


def _safe_actor_label(actor: AuthenticatedActor | None) -> str | None:
    if actor is None:
        return None
    if actor.display_name and actor.display_name.strip():
        return actor.display_name.strip()
    return actor.actor_category


def _safe_title_surface(context: FeedbackHandoffContext | None) -> str:
    if context is None:
        return ""
    if context.workflow_area:
        return context.workflow_area.replace("-", " ").title()
    if context.page_path:
        route_titles = {
            "/": "Home",
            "/feedback": "Feedback",
            "/ccld/records/request": "Request Records",
            "/ccld/retrieval/jobs": "Job Status",
            "/ccld/retrieval/jobs/detail": "Job Status Detail",
            "/reviewer": "Review Queue",
            "/reviewer/records": "Review Queue",
            "/reviewer/packet/preview": "Packet Preview",
            "/reviewer/packet/draft": "Packet Draft",
        }
        if context.page_path in route_titles:
            return route_titles[context.page_path]
        page_name = context.page_path.strip("/").split("/")[-1].replace("-", " ")
        return page_name.title() if page_name else "Home"
    return ""


def _create_github_issue_with_label_fallback(
    *,
    context: FeedbackContext,
    submission: FeedbackSubmission,
    issue_body: str,
    labels: Sequence[str],
) -> Mapping[str, Any]:
    issue_title = build_issue_title(submission)
    try:
        return context.github_client.create_issue(
            repo=context.github_config.repo or "",
            token=context.github_config.token or "",
            title=issue_title,
            body=issue_body,
            labels=labels,
        )
    except Exception:
        if not labels:
            raise
        return context.github_client.create_issue(
            repo=context.github_config.repo or "",
            token=context.github_config.token or "",
            title=issue_title,
            body=issue_body,
            labels=(),
        )


def _safe_github_issue_url(raw_url: object, repo: str | None) -> str | None:
    if not isinstance(raw_url, str) or not raw_url.strip() or repo is None:
        return None
    expected_prefix = f"https://github.com/{repo}/issues/"
    if raw_url.startswith(expected_prefix) and _contains_secret_marker(raw_url) is False:
        return raw_url
    return None


def _html_response(status: int, markup: str) -> tuple[int, str, bytes]:
    return status, "text/html; charset=utf-8", markup.encode()
