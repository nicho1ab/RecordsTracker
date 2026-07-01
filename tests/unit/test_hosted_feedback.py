from __future__ import annotations

import html as html_lib
import re
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlencode

from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Connection

from ccld_complaints.hosted_app.app import route_response
from ccld_complaints.hosted_app.auth import (
    AuthenticatedActor,
    HostedAccountStatus,
    HostedTesterRole,
    load_hosted_auth_runtime_config,
)
from ccld_complaints.hosted_app.feedback import (
    ALLOWED_FEEDBACK_CONTEXT_PARAMETERS,
    FEEDBACK_PATH,
    FeedbackContext,
    GitHubFeedbackConfig,
    GitHubIssueClient,
    build_issue_body,
    feedback_href,
    feedback_labels,
)
from ccld_complaints.hosted_app.reviewer_ui import LOCAL_REVIEWER_UI_SCOPE
from ccld_complaints.hosted_app.seeded_import import (
    hosted_import_batches,
    hosted_seeded_import_metadata,
    hosted_source_derived_records,
    import_seeded_corpus_artifact,
    load_seeded_corpus_artifact,
)

FIXTURE = Path("tests/fixtures/hosted_seeded_corpus/validated_seeded_corpus.json")
TEST_AUTH_VALUE = "test-auth-value-not-rendered"


class MockGitHubIssueClient:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    def create_issue(
        self,
        *,
        repo: str,
        token: str,
        title: str,
        body: str,
        labels: Sequence[str],
    ) -> dict[str, Any]:
        if self.fail:
            raise RuntimeError("mock GitHub failure")
        self.calls.append(
            {
                "repo": repo,
                "token": token,
                "title": title,
                "body": body,
                "labels": tuple(labels),
            }
        )
        return {"number": 42}


def test_feedback_page_renders_accessible_form_and_exact_type_options() -> None:
    status, content_type, body = route_response(FEEDBACK_PATH)
    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Send feedback" in html
    assert "Send safe review feedback" in html
    assert "What makes feedback actionable" in html
    assert (
        "Actionable tester feedback names the page or route, what you tried first, "
        "what you expected, what happened instead, and whether the issue blocked review."
        in html
    )
    assert (
        "facility lookup, Request Records, loaded queue, reviewer detail, packet/brief, "
        "readiness checklist, or feedback"
        in html
    )
    assert (
        "confusing loaded-context cue, source traceability cue, record order, "
        "note/status action, packet/readiness item, label, or keyboard step"
        in html
    )
    assert "Say what would have helped you continue review." in html
    assert "packet/readiness" in html
    assert "Job Status" in html
    assert "already-loaded records" in html or "loaded-record" in html
    assert "browser copy issue" in normalized_html
    assert "print issue" in normalized_html
    assert "Submit feedback" in html
    assert "copy" in html.lower()
    assert (
        '<section class="notice-card" aria-labelledby="feedback-safety-heading">'
        in html
    )
    assert (
        '<section class="notice-card" aria-labelledby="feedback-unconfigured-heading">'
        in html
    )
    assert (
        '<h2 id="feedback-unconfigured-heading">How feedback is submitted</h2>'
        in html
    )
    assert (
        "<p>Note: Server-side GitHub issue intake is not configured on this deployment."
        in html
    )
    assert (
        '<section class="helper-text" aria-labelledby="feedback-unconfigured-heading">'
        not in html
    )
    assert (
        '<p id="feedback-type-help" class="helper-text">Choose the category that best fits '
        "the route, action, loaded-context cue, packet/readiness cue, or keyboard step "
        "that was confusing.</p>"
    ) in html
    assert (
        "Describe the page, action, expected result, actual result, loaded-context cue, "
        "source traceability cue, packet/readiness concern, browser copy issue, or print issue "
        "without private material."
        in normalized_html
    )
    assert '<label for="page_path">Submitted page path</label>' in html
    assert 'name="page_path" type="text" value="/feedback" readonly' in html
    assert "This visible context is included with the feedback when submitted." in html
    assert 'type="hidden" name="page_path"' not in html
    assert (
        "The first-time tester orientation did not make facility lookup, Request Records, "
        "loaded context, prioritized records, packet/brief, readiness checklist, or feedback clear."
        in html
    )
    assert_ordered(
        html,
        (
            '<h2 id="actionable-feedback-heading">What makes feedback actionable</h2>',
            '<label for="feedback_type">Feedback type</label>',
            '<select id="feedback_type" name="feedback_type" required '
            'aria-describedby="feedback-type-help">',
            '<p id="feedback-type-help" class="helper-text">Choose the category that best fits '
            "the route, action, loaded-context cue, packet/readiness cue, or keyboard step "
            "that was confusing.</p>",
            '<h3 id="feedback-safety-heading">Do not include private material</h3>',
            '<label for="description">Description</label>',
            '<button type="submit">Submit feedback</button>',
            '<h2 id="feedback-unconfigured-heading">How feedback is submitted</h2>',
            "<p>Note: Server-side GitHub issue intake is not configured on this deployment.",
        ),
    )


def test_feedback_page_renders_safe_optional_handoff_context() -> None:
    query = urlencode(
        {
            "feedback_type": "Bug report",
            "workflow_area": "packet-preview",
            "page_path": "/reviewer/packet/preview",
            "facility_number": "157806098",
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
            "request_context_origin": "manual_entry",
            "reviewer_status_filter": "blocked",
            "source_record_key": "complaint:ccld:complaint:32-CR-20220407124448",
            "complaint_control_number": "32-CR-20220407124448",
            "prompt": "Describe packet readiness confusion.",
            "private_url": "https://private.example.test/path",
            "token": TEST_AUTH_VALUE,
        }
    )

    status, content_type, body = route_response(f"{FEEDBACK_PATH}?{query}")
    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Feedback context from review workflow" in html
    assert "packet-preview" in html
    assert "/reviewer/packet/preview" in html
    assert "157806098" in html
    assert "2026-01-01" in html
    assert "2026-01-31" in html
    assert "manual_entry" in html
    assert "Reviewer-status filter" in html
    assert "blocked" in html
    assert "active reviewer-created status filter confusion" in normalized_html
    assert "shown-count or total-count confusion" in normalized_html
    assert "filtered-empty recovery problems" in normalized_html
    assert "complaint:ccld:complaint:32-CR-20220407124448" not in html
    assert "32-CR-20220407124448" in html
    assert "Describe packet readiness confusion." in html
    assert "packet/readiness confusion" in normalized_html
    assert "browser copy or print confusion" in normalized_html
    assert "missing or unexpected records in packet content" in normalized_html
    assert "missing or unexpected records in packet content" in normalized_html
    assert (
        "possible correction concerns where a source-derived value looked wrong"
        in normalized_html
    )
    assert "source-confidence next-step confusion for missing source values" in (
        normalized_html
    )
    assert "proxy-related cues, or cautious note/status wording" in normalized_html
    assert "uncertainty about whether to use a reviewer-created note or feedback" in normalized_html
    assert "raw source narrative" in html
    assert 'action="/feedback"' in html
    assert 'action="/ccld/correction' not in normalized_html
    assert 'name="correction_status"' not in normalized_html
    assert "correction approved" not in normalized_html
    assert "correction applied" not in normalized_html
    assert "corrected source record" not in normalized_html
    assert "private.example" not in html
    assert TEST_AUTH_VALUE not in html
    assert '<option value="Bug report" selected="selected">Bug report</option>' in html
    assert 'name="page_path" type="text" value="/reviewer/packet/preview" readonly' in html
    assert 'type="hidden" name="page_path"' not in html
    assert_no_secret_html(html)


def test_feedback_page_renders_safe_retrieval_handoff_context() -> None:
    query = urlencode(
        {
            "feedback_type": "Bug report",
            "workflow_area": "retrieval-job-detail",
            "page_path": "/ccld/retrieval/jobs/detail",
            "facility_number": "157806098",
            "start_date": "2022-08-01",
            "end_date": "2022-08-31",
            "retrieval_context": "controlled-job-detail",
            "retrieval_status": "completed_with_warnings",
            "retrieval_job_id": "ccld-retrieval-157806098-20260615T120000Z",
            "prompt": "Describe retrieval status confusion.",
            "raw_storage_path": "C:/server/private/raw/artifact.html",
        }
    )

    status, content_type, body = route_response(f"{FEEDBACK_PATH}?{query}")
    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Feedback context from review workflow" in html
    assert "retrieval-job-detail" in html
    assert "/ccld/retrieval/jobs/detail" in html
    assert "Job context" in html
    assert "controlled-job-detail" in html
    assert "Job status" in html
    assert "completed_with_warnings" in html
    assert "Job ID" in html
    assert "ccld-retrieval-157806098-20260615T120000Z" in html
    assert "Job Status history/detail context" in normalized_html
    assert "Describe retrieval status confusion." in html
    assert "C:/server/private/raw/artifact.html" not in html
    assert_no_secret_html(html)


def test_feedback_page_prefills_editable_starter_from_safe_handoff_context() -> None:
    query = urlencode(
        {
            "feedback_type": "Bug report",
            "workflow_area": "retrieval-job-detail",
            "page_path": "/ccld/retrieval/jobs/detail",
            "facility_number": "157806098",
            "start_date": "2022-08-01",
            "end_date": "2022-08-31",
            "retrieval_context": "controlled-job-detail",
            "retrieval_status": "completed_with_warnings",
            "retrieval_job_id": "ccld-retrieval-157806098-20260615T120000Z",
            "prompt": "Describe retrieval status confusion.",
            "raw_storage_path": "C:/server/private/raw/artifact.html",
        }
    )

    status, _content_type, body = route_response(f"{FEEDBACK_PATH}?{query}")
    html = body.decode("utf-8")
    starter = _description_textarea(html)

    assert status == 200
    assert "Suggested issue starter" in html
    assert "Edit this before submitting" in html
    assert "This starter uses only safe handoff context from the screen you came from." in html
    assert (
        "Do not paste secrets, private URLs, stack traces, raw source narrative, or "
        "unrelated personal information."
        in html
    )
    starter_opening = (
        "I am reporting confusion about the Job Status information on "
        "retrieval job detail."
    )
    assert starter == "\n".join(
        [
            starter_opening,
            "Facility/license: 157806098",
            "Date range: 2022-08-01 to 2022-08-31",
            "Job context: controlled-job-detail",
            "Job status: completed_with_warnings",
            "Job ID: ccld-retrieval-157806098-20260615T120000Z",
            "",
            "Prompt from previous screen: Describe retrieval status confusion.",
            "",
            "What was confusing:",
            "[Edit this before submitting.]",
        ]
    )
    assert "C:/server/private/raw/artifact.html" not in starter
    forbidden_starter_markers = (
        "secret",
        "private",
        "provider",
        "token",
        "stack trace",
        "raw source narrative",
        "server path",
        "public-source completeness",
        "legal conclusion",
    )
    assert not any(marker in starter.casefold() for marker in forbidden_starter_markers)
    assert_no_secret_html(html)


def test_feedback_starter_omits_unavailable_handoff_values() -> None:
    query = urlencode(
        {
            "feedback_type": "Bug report",
            "workflow_area": "request-result",
            "facility_number": "157806098",
            "retrieval_context": "already-loaded-records",
        }
    )

    status, _content_type, body = route_response(f"{FEEDBACK_PATH}?{query}")
    html = body.decode("utf-8")
    starter = _description_textarea(html)

    assert status == 200
    assert "Suggested issue starter" in html
    assert (
        "I am reporting confusion about the Job Status information on request result."
        in starter
    )
    assert "Facility/license: 157806098" in starter
    assert "Job context: already-loaded-records" in starter
    assert "Date range:" not in starter
    assert "Job status:" not in starter
    assert "Job ID:" not in starter
    assert "Prompt from previous screen:" not in starter
    assert_no_secret_html(html)


def test_feedback_page_ignores_unsafe_context_parameters() -> None:
    query = urlencode(
        {
            "workflow_area": "unexpected-area",
            "page_path": "https://private.example.test/app",
            "facility_number": "157806098-secret",
            "source_record_key": "token=abc123",
            "retrieval_context": "raw-storage-path",
            "retrieval_status": "provider_subject",
            "retrieval_job_id": "token=abc123",
            "prompt": "authorization: bearer secret",
        }
    )

    status, _content_type, body = route_response(f"{FEEDBACK_PATH}?{query}")
    html = body.decode("utf-8")

    assert status == 200
    assert "Feedback context from review workflow" not in html
    assert "Suggested issue starter" not in html
    assert "I am reporting confusion" not in html
    assert "private.example" not in html
    assert "authorization" not in html.casefold()
    assert "bearer" not in html.casefold()
    assert_no_secret_html(html)


def test_feedback_context_allowlist_is_explicit_and_helper_ignores_unknown_values() -> None:
    assert "source_record_key" not in ALLOWED_FEEDBACK_CONTEXT_PARAMETERS
    assert "page_path" in ALLOWED_FEEDBACK_CONTEXT_PARAMETERS
    assert "workflow_area" in ALLOWED_FEEDBACK_CONTEXT_PARAMETERS
    assert "prompt" in ALLOWED_FEEDBACK_CONTEXT_PARAMETERS

    href = feedback_href(
        feedback_type="Bug report",
        workflow_area="entry-orientation",
        page_path="/",
        prompt="Describe what was confusing.",
        source_record_key="complaint:ccld:complaint:32-CR-20220407124448",
        private_url="https://private.example.test",
    )

    assert href.startswith(f"{FEEDBACK_PATH}?")
    assert "entry-orientation" in href
    assert "source_record_key" not in href
    assert "private_url" not in href
    assert "private.example" not in href

    unsafe_href = feedback_href(
        feedback_type="Bug report",
        page_path="https://private.example.test/app",
        prompt="authorization: bearer secret",
    )

    assert unsafe_href == f"{FEEDBACK_PATH}?feedback_type=Bug+report"


def test_feedback_validation_errors_are_safe() -> None:
    context = _feedback_context(configured=False, actor=_actor())

    status, _content_type, body = route_response(
        FEEDBACK_PATH,
        method="POST",
        request_body=_form_bytes({}),
        feedback_context=context,
    )
    html = body.decode("utf-8")

    assert status == 400
    assert "Choose a supported feedback type." in html
    assert "Describe the feedback before submitting." in html
    assert "Feedback was not submitted" in html
    assert_no_secret_html(html)


def test_feedback_unconfigured_state_does_not_call_github() -> None:
    client = MockGitHubIssueClient()
    context = _feedback_context(configured=False, actor=_actor(), client=client)

    status, _content_type, body = route_response(
        FEEDBACK_PATH,
        method="POST",
        request_body=_valid_form_bytes(),
        feedback_context=context,
    )
    html = body.decode("utf-8")

    assert status == 503
    assert "Feedback was not sent" in html
    assert "No GitHub issue was created" in html
    assert client.calls == []
    assert_no_secret_html(html)


def test_feedback_configured_submission_uses_mocked_client_and_labels() -> None:
    client = MockGitHubIssueClient()
    context = _feedback_context(configured=True, actor=_actor(), client=client)

    status, _content_type, body = route_response(
        FEEDBACK_PATH,
        method="POST",
        request_body=_valid_form_bytes(feedback_type="Feature request"),
        feedback_context=context,
    )
    html = body.decode("utf-8")

    assert status == 201
    assert "Feedback submitted" in html
    assert "Issue #42" in html
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["repo"] == "example/repo"
    assert call["token"] == TEST_AUTH_VALUE
    assert call["labels"] == (
        "feedback",
        "from-app",
        "needs-triage",
        "pilot",
        "feature-request",
    )
    assert "Feature request" in call["body"]
    assert "Please add keyboard-friendly sorting." in call["body"]
    assert TEST_AUTH_VALUE not in call["body"]
    assert "provider_subject" not in call["body"]
    assert "provider_issuer" not in call["body"]
    assert_no_secret_html(html)


def test_feedback_type_label_mapping_is_reliable() -> None:
    assert feedback_labels("Bug report") == (
        "feedback",
        "from-app",
        "needs-triage",
        "bug",
    )
    assert feedback_labels("Feature request")[-1] == "feature-request"
    assert feedback_labels("New data source")[-1] == "new-data-source"


def test_feedback_client_failure_shows_safe_failure() -> None:
    context = _feedback_context(
        configured=True,
        actor=_actor(),
        client=MockGitHubIssueClient(fail=True),
    )

    status, _content_type, body = route_response(
        FEEDBACK_PATH,
        method="POST",
        request_body=_valid_form_bytes(),
        feedback_context=context,
    )
    html = body.decode("utf-8")

    assert status == 502
    assert "Feedback could not be sent" in html
    assert "No token or private details are shown" in html
    assert_no_secret_html(html)


def test_feedback_production_anonymous_submission_is_blocked_when_configured() -> None:
    auth_config = load_hosted_auth_runtime_config(
        environ={"CCLD_HOSTED_TESTER_AUTH_MODE": "production"}
    )
    context = _feedback_context(configured=True, actor=None)

    status, _content_type, body = route_response(
        FEEDBACK_PATH,
        method="POST",
        request_body=_valid_form_bytes(),
        auth_runtime_config=auth_config,
        feedback_context=context,
    )
    html = body.decode("utf-8")

    assert status == 401
    assert "Feedback requires sign-in" in html
    assert_no_secret_html(html)


def test_feedback_production_anonymous_submission_is_blocked_when_unconfigured() -> None:
    auth_config = load_hosted_auth_runtime_config(
        environ={"CCLD_HOSTED_TESTER_AUTH_MODE": "production"}
    )
    client = MockGitHubIssueClient()
    context = _feedback_context(configured=False, actor=None, client=client)

    status, _content_type, body = route_response(
        FEEDBACK_PATH,
        method="POST",
        request_body=_valid_form_bytes(),
        auth_runtime_config=auth_config,
        feedback_context=context,
    )
    html = body.decode("utf-8")

    assert status == 401
    assert "Feedback requires sign-in" in html
    assert "Feedback is not configured" not in html
    assert client.calls == []
    assert_no_secret_html(html)


def test_feedback_local_dev_actor_can_submit_with_mocked_client() -> None:
    client = MockGitHubIssueClient()
    context = _feedback_context(configured=True, actor=_actor(), client=client)

    status, _content_type, body = route_response(
        FEEDBACK_PATH,
        method="POST",
        request_body=_valid_form_bytes(feedback_type="Bug report"),
        auth_runtime_config=_local_dev_auth_config(),
        feedback_context=context,
    )

    assert status == 201
    assert client.calls[0]["labels"][-1] == "bug"
    assert_no_secret_html(body.decode("utf-8"))


def test_feedback_submission_does_not_mutate_source_derived_records() -> None:
    client = MockGitHubIssueClient()
    context = _feedback_context(configured=True, actor=_actor(), client=client)
    with _seeded_connection() as connection:
        before_counts = _table_counts(connection)
        status, _content_type, body = route_response(
            FEEDBACK_PATH,
            method="POST",
            request_body=_valid_form_bytes(),
            feedback_context=context,
        )
        after_counts = _table_counts(connection)

    assert status == 201
    assert before_counts == after_counts
    assert_no_secret_html(body.decode("utf-8"))


def test_issue_body_rejects_secret_like_description() -> None:
    submission = _submission(description="A token was pasted here.")

    try:
        build_issue_body(submission, submitted_at=_now(), actor=_actor())
    except ValueError as error:
        assert "secret-like" in str(error)
    else:
        raise AssertionError("Expected secret-like issue body to be rejected")


def _feedback_context(
    *,
    configured: bool,
    actor: AuthenticatedActor | None,
    client: GitHubIssueClient | None = None,
) -> FeedbackContext:
    return FeedbackContext(
        actor=actor,
        scope=LOCAL_REVIEWER_UI_SCOPE,
        github_config=GitHubFeedbackConfig(
            repo="example/repo" if configured else None,
            token=TEST_AUTH_VALUE if configured else None,
            default_labels=("pilot",) if configured else (),
        ),
        github_client=client or MockGitHubIssueClient(),
        now=_now,
        app_version="test-version",
    )


def _actor() -> AuthenticatedActor:
    return AuthenticatedActor(
        provider_subject="fixture-feedback-subject",
        provider_issuer="fixture-feedback-issuer",
        display_name="Fixture Feedback Tester",
        email=None,
        actor_category="tester",
        account_status=cast(HostedAccountStatus, "active"),
        roles=(cast(HostedTesterRole, "tester_reviewer"),),
        scopes=(LOCAL_REVIEWER_UI_SCOPE,),
    )


def _local_dev_auth_config() -> Any:
    return load_hosted_auth_runtime_config(
        environ={
            "CCLD_HOSTED_TESTER_AUTH_MODE": "local-dev",
            "CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH": "enabled",
        }
    )


def _valid_form_bytes(*, feedback_type: str = "Feature request") -> bytes:
    return _form_bytes(
        {
            "feedback_type": feedback_type,
            "description": "Please add keyboard-friendly sorting.",
            "page_path": "/ccld/records/request",
        }
    )


def _form_bytes(values: dict[str, str]) -> bytes:
    return urlencode(values).encode("utf-8")


def _submission(description: str) -> Any:
    from ccld_complaints.hosted_app.feedback import FeedbackSubmission

    return FeedbackSubmission(
        feedback_type="Bug report",
        description=description,
        page_path="/feedback",
    )


def _now() -> datetime:
    return datetime(2026, 6, 15, 12, 0, 0, tzinfo=UTC)


def _seeded_connection() -> Connection:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)
    connection = engine.connect()
    transaction = connection.begin()
    artifact = load_seeded_corpus_artifact(FIXTURE)
    import_seeded_corpus_artifact(connection, artifact)
    transaction.commit()
    return connection


def _table_counts(connection: Connection) -> dict[str, int]:
    return {
        "import_batches": connection.execute(
            select(func.count()).select_from(hosted_import_batches)
        ).scalar_one(),
        "source_records": connection.execute(
            select(func.count()).select_from(hosted_source_derived_records)
        ).scalar_one(),
    }


def assert_no_secret_html(markup: str) -> None:
    lowered = markup.casefold()
    for marker in [
        "client_secret",
        "provider_subject",
        "provider_issuer",
        "test-auth-value-not-rendered",
        "authorization",
        "cookie",
        "private_header",
    ]:
        assert marker not in lowered


def _description_textarea(markup: str) -> str:
    match = re.search(
        r'<textarea id="description" name="description"[^>]*>(.*?)</textarea>',
        markup,
        flags=re.DOTALL,
    )
    if match is None:
        raise AssertionError("Feedback description textarea not found")
    return html_lib.unescape(match.group(1))


def assert_ordered(markup: str, fragments: Sequence[str]) -> None:
    cursor = -1
    for fragment in fragments:
        index = markup.find(fragment)
        if index == -1:
            raise AssertionError(f"Fragment not found: {fragment}")
        if index <= cursor:
            raise AssertionError(f"Fragment appeared out of order: {fragment}")
        cursor = index
