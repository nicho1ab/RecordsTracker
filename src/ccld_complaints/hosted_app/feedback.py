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
FEEDBACK_TYPE_OPTIONS = ("Bug report", "Feature request", "New data source")
SAFE_WORKFLOW_AREAS = (
    "queue",
    "reviewer-detail",
    "save-confirmation",
    "packet-preview",
    "packet-draft",
    "help",
)
BASE_FEEDBACK_LABELS = ("feedback", "from-app", "needs-triage")
TYPE_LABELS = {
    "Bug report": "bug",
    "Feature request": "feature-request",
    "New data source": "new-data-source",
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


@dataclass(frozen=True)
class FeedbackSubmission:
    feedback_type: str
    description: str
    page_path: str | None


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
    source_record_key: str | None = None
    complaint_control_number: str | None = None
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
    if handoff_context and handoff_context.page_path:
        form_values["page_path"] = [handoff_context.page_path]
    return _page(
                title="Send feedback",
                heading="Send feedback",
        main=f"""
    {_configuration_notice(context.github_config)}
        <section class="hero-card" aria-labelledby="feedback-purpose-heading">
            <p class="launch-kicker">Tester support</p>
            <h2 id="feedback-purpose-heading">What issue should be reported?</h2>
            <p>Choose the feedback type and describe what blocked retrieval, review, source traceability, missing local/test traceability values, wording, or keyboard flow.</p>
        </section>
        {_feedback_context_panel(handoff_context)}
        <div class="support-layout">
            {_feedback_form(form_values)}
        </div>
        <section class="quiet-section" aria-labelledby="feedback-safety-heading">
            <h2 id="feedback-safety-heading">Do not include private material</h2>
            <p>Do not include private facts, credentials, legal strategy, privileged work product,
            private URLs, secrets, tokens, provider claims, raw source narrative, raw artifact material,
            server paths, connection details, or unrelated sensitive details.</p>
        </section>
        <details class="technical-details">
            <summary>Useful examples</summary>
            <ul>
                <li>A complaint record looked missing or unexpected.</li>
                <li>A date or finding looked confusing.</li>
                <li>A review flag was unclear.</li>
                <li>The source traceability summary was hard to use.</li>
                <li>A source URL, raw SHA-256 hash, connector metadata, retrieval timestamp, or source document/report marker looked missing or confusing.</li>
                <li>The workflow did not help me decide what to review next.</li>
            </ul>
        </details>
""",
    )


def _feedback_type_href(feedback_type: str) -> str:
    return f"{FEEDBACK_PATH}?{urlencode({'feedback_type': feedback_type})}"


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
        source_record_key=_safe_short_value(_first_form_value(values, "source_record_key"), max_length=180),
        complaint_control_number=_safe_short_value(_first_form_value(values, "complaint_control_number"), max_length=80),
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
            <p>This context was carried from a local/test review page. It is a bounded helper for
            triage, not a source fact, not a legal conclusion, not a final export, and
            not a source-completeness proof.</p>
            <dl>
{row_markup}
            </dl>
            <p>Describe what was confusing, missing, unexpected, or hard to use, including source
            traceability concerns such as source URL, raw SHA-256 hash, connector metadata,
            retrieval timestamp, source document/report marker, or local/test traceability value
            missing. Do not include
            raw source narrative, secrets, provider claims, private URLs, stack traces, server
            paths, environment values, or legal conclusions.</p>
        </section>"""


def _feedback_context_rows(context: FeedbackHandoffContext) -> list[tuple[str, str]]:
    fields = (
        ("Workflow area", context.workflow_area),
        ("Page path", context.page_path),
        ("Facility/license number", context.facility_number),
        ("Start date", context.start_date),
        ("End date", context.end_date),
        ("Request origin", context.request_context_origin),
        ("Reviewer-status filter", context.reviewer_status_filter),
        ("Source record key", context.source_record_key),
        ("Complaint/control identifier", context.complaint_control_number),
        ("Suggested prompt", context.prompt),
    )
    return [(label, value) for label, value in fields if value]


def _safe_choice(value: str, allowed: Sequence[str]) -> str | None:
    if value in allowed:
        return value
    return None


def _safe_date_value(value: str) -> str | None:
    if len(value) == 10 and value[4] == "-" and value[7] == "-" and value.replace("-", "").isdigit():
        return value
    return None


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
    page_path = _safe_page_path(_first_form_value(form_values, "page_path"))
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
        errors.append("Feedback must not include secrets, tokens, cookies, or private headers.")
    if errors:
        return FeedbackValidationResult(submission=None, errors=tuple(errors))
    return FeedbackValidationResult(
        submission=FeedbackSubmission(
            feedback_type=feedback_type,
            description=description,
            page_path=page_path,
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
    return f"[App feedback] {submission.feedback_type}"


def build_issue_body(
    submission: FeedbackSubmission,
    *,
    submitted_at: datetime,
    actor: AuthenticatedActor | None,
    app_version: str | None = None,
) -> str:
    lines = [
        "## Feedback",
        "",
        f"Type: {submission.feedback_type}",
        f"Submitted at: {submitted_at.isoformat()}",
    ]
    if submission.page_path is not None:
        lines.append(f"Page path: {submission.page_path}")
    actor_label = _safe_actor_label(actor)
    if actor_label is not None:
        lines.append(f"Submitted by: {actor_label}")
    if app_version is not None and app_version.strip():
        lines.append(f"App version: {app_version.strip()}")
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
        )
        issue = context.github_client.create_issue(
            repo=context.github_config.repo or "",
            token=context.github_config.token or "",
            title=build_issue_title(submission),
            body=issue_body,
            labels=labels,
        )
    except Exception:
        return _html_response(
            502,
            _page(
                title="Feedback could not be sent",
                heading="Feedback could not be sent",
                main="""
    <section aria-labelledby="feedback-failure-heading">
      <h2 id="feedback-failure-heading">Feedback could not be sent</h2>
      <p>The server could not create the GitHub issue. No token or private details are shown.</p>
    </section>
""",
            ),
        )
    issue_number = issue.get("number")
    issue_text = f"Issue #{issue_number}" if isinstance(issue_number, int) else "GitHub issue"
    return _html_response(
        201,
        _page(
            title="Feedback submitted",
            heading="Feedback submitted",
            main=f"""
    <section aria-labelledby="feedback-success-heading">
      <h2 id="feedback-success-heading">Feedback submitted</h2>
      <p>{html.escape(issue_text)} was created for triage.</p>
      <p>Labels: {html.escape(', '.join(labels))}</p>
    </section>
""",
        ),
    )


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
    return """    <section aria-labelledby="feedback-unconfigured-heading">
      <h2 id="feedback-unconfigured-heading">GitHub issue intake is not configured</h2>
            <p>You can preview the form, but submitting feedback will not create a GitHub issue
            until server-side configuration is added.</p>
    </section>"""


def _feedback_form(form_values: Mapping[str, list[str]]) -> str:
    selected_type = _first_form_value(form_values, "feedback_type")
    description = _first_form_value(form_values, "description")
    escaped_description = html.escape(description)
    page_path = _first_form_value(form_values, "page_path") or FEEDBACK_PATH
    options = "\n".join(
        _feedback_type_option(option, selected_type) for option in FEEDBACK_TYPE_OPTIONS
    )
    textarea = (
        '<textarea id="description" name="description" rows="8" '
        f'maxlength="{MAX_FEEDBACK_DESCRIPTION_LENGTH}" required>'
        f"{escaped_description}</textarea>"
    )
    return f"""    <section aria-labelledby="feedback-form-heading">
      <h2 id="feedback-form-heading">Send tester feedback</h2>
      <form action="{FEEDBACK_PATH}" method="post">
        <p>
          <label for="feedback_type">Feedback type</label>
          <select id="feedback_type" name="feedback_type" required>
            <option value="">Choose feedback type</option>
{options}
          </select>
        </p>
        <p>
          <label for="description">Description</label>
                    {textarea}
        </p>
        <input type="hidden" name="page_path" value="{html.escape(page_path)}">
        <p><button type="submit">Submit feedback</button></p>
      </form>
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
                eyebrow="Server-side GitHub Issues feedback intake.",
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


def _html_response(status: int, markup: str) -> tuple[int, str, bytes]:
    return status, "text/html; charset=utf-8", markup.encode()