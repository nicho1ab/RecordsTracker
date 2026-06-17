from __future__ import annotations

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
    FEEDBACK_PATH,
    FeedbackContext,
    GitHubFeedbackConfig,
    GitHubIssueClient,
    build_issue_body,
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

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Send feedback" in html
    assert "What issue should be reported?" in html
    assert "packet/export-readiness" in html
    assert "browser copy or print" in html
    assert "A complaint record looked missing or unexpected." in html
    assert "The source traceability summary was hard to use." in html
    assert "active status-filter counts" in html
    assert "filtered-empty recovery" in html
    assert "The active reviewer-created status filter, shown count" in html
    assert "Packet readiness, browser copy or print preparation" in html
    assert "boundary between local/test packet preparation and final export" in html
    assert "missing or unexpected record" in html
    assert "reviewer-created note/status concern" in html
    assert "correction-readiness guidance" in html
    assert (
        "A source-derived value looked wrong or incomplete after checking source traceability."
        in html
    )
    assert "whether to use a reviewer-created note or feedback" in html
    assert "raw SHA-256 hash" in html
    assert "source document/report marker looked missing or confusing" in html
    assert "support-layout" in html
    assert "Do not include private material" in html
    assert "Useful examples" in html
    assert "Choose the best feedback type" not in html
    assert "Bug report" in html
    assert "Feature request" in html
    assert "New data source request" not in html
    assert "Something failed, looked wrong, or blocked" not in html
    assert "Do not include private facts, credentials" in html
    assert "Feedback is classified with labels" not in html
    assert '<label for="feedback_type">Feedback type</label>' in html
    assert '<label for="description">Description</label>' in html
    assert 'aria-describedby="feedback-type-help"' in html
    assert 'aria-describedby="description-help"' in html
    assert "Keyboard flow: choose a feedback type, Tab to Description" in html
    assert "Describe the route, control, keyboard flow" in html
    assert "packet/export-readiness concern" in html
    assert "local/test export boundary confusion" in html
    assert "Submit feedback" in html
    assert html.count('<option value="Bug report">Bug report</option>') == 1
    assert html.count('<option value="Feature request">Feature request</option>') == 1
    assert html.count('<option value="New data source">New data source</option>') == 1
    assert "GitHub issue intake is not configured" in html
    assert_no_secret_html(html)


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
    assert "complaint:ccld:complaint:32-CR-20220407124448" in html
    assert "32-CR-20220407124448" in html
    assert "Describe packet readiness confusion." in html
    assert "packet/export-readiness confusion" in normalized_html
    assert "browser copy or print confusion" in normalized_html
    assert "missing or unexpected records in packet content" in normalized_html
    assert "local/test packet boundary" in normalized_html
    assert "not a source-completeness proof" in normalized_html
    assert (
        "possible correction concerns where a source-derived value looked wrong"
        in normalized_html
    )
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
    assert 'name="page_path" value="/reviewer/packet/preview"' in html
    assert_no_secret_html(html)


def test_feedback_page_ignores_unsafe_context_parameters() -> None:
    query = urlencode(
        {
            "workflow_area": "unexpected-area",
            "page_path": "https://private.example.test/app",
            "facility_number": "157806098-secret",
            "source_record_key": "token=abc123",
            "prompt": "authorization: bearer secret",
        }
    )

    status, _content_type, body = route_response(f"{FEEDBACK_PATH}?{query}")
    html = body.decode("utf-8")

    assert status == 200
    assert "Feedback context from review workflow" not in html
    assert "private.example" not in html
    assert "authorization" not in html.casefold()
    assert "bearer" not in html.casefold()
    assert_no_secret_html(html)


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
