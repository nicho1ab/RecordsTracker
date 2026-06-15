from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlencode

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Connection

from ccld_complaints.hosted_app.app import route_response
from ccld_complaints.hosted_app.audit_events import hosted_audit_events
from ccld_complaints.hosted_app.auth import (
    AuthenticatedActor,
    HostedAccountStatus,
    HostedTesterRole,
    load_hosted_auth_runtime_config,
)
from ccld_complaints.hosted_app.ccld_record_request_ui import (
    CCLD_RECORD_REQUEST_PATH,
    CcldRecordRequestUiContext,
    _render_retrieval_job_summary,
    ccld_record_request_context_for_reviewer_context,
)
from ccld_complaints.hosted_app.ccld_retrieval_jobs import (
    CcldRetrievalConfig,
    CcldRetrievalContext,
    CcldRetrievalJobResult,
    hosted_ccld_retrieval_jobs,
    validate_ccld_source_url,
)
from ccld_complaints.hosted_app.feedback import FeedbackContext, GitHubFeedbackConfig
from ccld_complaints.hosted_app.reviewer_created_state import hosted_reviewer_created_state
from ccld_complaints.hosted_app.reviewer_ui import (
    LOCAL_REVIEWER_UI_SCOPE,
    reviewer_ui_context_for_connection,
)
from ccld_complaints.hosted_app.seeded_import import (
    hosted_import_batches,
    hosted_seeded_import_metadata,
    hosted_source_derived_records,
)

RAW_FIXTURE = Path("tests/fixtures/ccld/raw/157806098_inx3.html")
DETAIL_FIXTURE = Path("tests/fixtures/ccld/raw/157806098_facility_detail.html")
TEST_SCOPE = LOCAL_REVIEWER_UI_SCOPE
PLACEHOLDER_AUTH_VALUE = "test-auth-value-not-rendered"


class MockCcldRetrievalClient:
    def __init__(self, *, fail_reports: bool = False) -> None:
        self.fail_reports = fail_reports
        self.facility_detail_calls: list[tuple[str, int]] = []
        self.report_calls: list[tuple[str, int]] = []

    def fetch_facility_detail(self, facility_number: str, *, timeout_seconds: int) -> str:
        self.facility_detail_calls.append((facility_number, timeout_seconds))
        return DETAIL_FIXTURE.read_text(encoding="utf-8")

    def fetch_report(self, source_url: str, *, timeout_seconds: int) -> bytes:
        self.report_calls.append((source_url, timeout_seconds))
        if self.fail_reports:
            raise RuntimeError("mock report timeout")
        return RAW_FIXTURE.read_bytes()


class MockGitHubIssueClient:
    def create_issue(
        self,
        *,
        repo: str,
        token: str,
        title: str,
        body: str,
        labels: Sequence[str],
    ) -> dict[str, Any]:
        return {"number": 42}


def test_retrieval_form_renders_record_type_and_safe_setup_state() -> None:
    status, _content_type, body = route_response(
        CCLD_RECORD_REQUEST_PATH,
        auth_runtime_config=_local_dev_auth_config(),
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")
    normalized = " ".join(html.split())

    assert status == 200
    assert '<label for="record_type">Record type</label>' in html
    assert 'value="complaints"' in html
    assert 'value="all_supported"' in html
    assert "All supported record types currently resolves to complaint records only" in normalized
    assert "Run controlled CCLD retrieval" in html
    assert_no_secret_html(html)

    blocked_status, _content_type, blocked_body = route_response(
        CCLD_RECORD_REQUEST_PATH,
        method="POST",
        request_body=_retrieval_form_bytes(),
        auth_runtime_config=_local_dev_auth_config(),
        page_data_mode="fixture-demo",
    )
    blocked_html = blocked_body.decode("utf-8")
    blocked_normalized = " ".join(blocked_html.split())

    assert blocked_status == 503
    assert "Controlled CCLD retrieval setup required" in blocked_html
    assert "No retrieval job was created" in blocked_html
    assert "Operator setup checklist" in blocked_html
    assert "retrieval enablement" in blocked_normalized
    assert "server-side raw source storage" in blocked_normalized
    assert "Send tester feedback" in blocked_html
    assert_no_secret_html(blocked_html)


def test_retrieval_validation_blocks_bad_inputs_before_mutation(tmp_path: Path) -> None:
    with _empty_connection() as connection:
        context = _request_context(connection, tmp_path)
        status, _content_type, body = route_response(
            CCLD_RECORD_REQUEST_PATH,
            method="POST",
            request_body=_retrieval_form_bytes(
                facility_number="157806098",
                record_type="inspection_reports",
                start_date="2022-01-01",
                end_date="2024-01-15",
            ),
            ccld_record_request_ui_context=context,
        )
        counts = _table_counts(connection)

    html = body.decode("utf-8")

    assert status == 400
    assert "Choose a supported CCLD record type." in html
    assert "Date range must be 30 days or fewer" in html
    assert "What to check next" in html
    assert "All supported record types currently means complaint records only" in html
    assert "Send tester feedback" in html
    assert counts == _empty_counts()
    assert_no_secret_html(html)


def test_validate_ccld_source_url_allowlist_blocks_non_ccld() -> None:
    validate_ccld_source_url(
        "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=157806098&inx=3",
        facility_number="157806098",
    )

    with pytest.raises(ValueError, match="outside the approved source allowlist"):
        validate_ccld_source_url(
            "https://example.invalid/transparencyapi/api/FacilityReports?facNum=157806098&inx=3",
            facility_number="157806098",
        )
    with pytest.raises(ValueError, match="facility does not match"):
        validate_ccld_source_url(
            "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=000000000&inx=3",
            facility_number="157806098",
        )


def test_controlled_retrieval_imports_records_and_links_queue(tmp_path: Path) -> None:
    client = MockCcldRetrievalClient()
    with _empty_connection() as connection:
        before_counts = _table_counts(connection)
        context = _request_context(connection, tmp_path, client=client)
        status, _content_type, body = route_response(
            CCLD_RECORD_REQUEST_PATH,
            method="POST",
            request_body=_retrieval_form_bytes(),
            ccld_record_request_ui_context=context,
        )
        after_counts = _table_counts(connection)
        jobs = connection.execute(select(hosted_ccld_retrieval_jobs)).mappings().all()

    html = body.decode("utf-8")
    normalized = " ".join(html.split())

    assert status == 200
    assert before_counts == _empty_counts()
    assert after_counts["import_batches"] == 1
    assert after_counts["source_records"] == 26
    assert after_counts["retrieval_jobs"] == 1
    assert after_counts["reviewer_created_state"] == 0
    assert after_counts["audit_events"] == 0
    assert len(client.facility_detail_calls) == 1
    assert len(client.report_calls) == 1
    assert all("www.ccld.dss.ca.gov" in url for url, _timeout in client.report_calls)
    raw_files = sorted((tmp_path / "raw").glob("*.html"))
    assert len(raw_files) == 1
    assert raw_files[0].read_bytes() == RAW_FIXTURE.read_bytes()
    assert jobs[0]["job_state"] == "completed"
    assert jobs[0]["authorization_permission"] == "retrieval_job_trigger"
    assert "Controlled CCLD retrieval job status" in html
    assert "Job state" in html
    assert "Completed" in html
    assert "Retrieval job created" in html
    assert "Records imported" in html
    assert "Imported source derived records" in normalized
    assert "Controlled CCLD retrieval completed and imported validated records" in html
    assert "What to do next" in html
    assert "Open the imported records in the queue" in html
    assert "Open imported records in this CCLD queue" in html
    assert "Send tester feedback" in html
    assert "CCLD request accepted" in html
    assert "Open reviewer detail" in html
    assert_no_secret_html(html)


def test_retrieval_all_supported_resolves_to_complaints(tmp_path: Path) -> None:
    client = MockCcldRetrievalClient()
    with _empty_connection() as connection:
        context = _request_context(connection, tmp_path, client=client)
        status, _content_type, body = route_response(
            CCLD_RECORD_REQUEST_PATH,
            method="POST",
            request_body=_retrieval_form_bytes(record_type="all_supported"),
            ccld_record_request_ui_context=context,
        )

    html = body.decode("utf-8")

    assert status == 200
    assert "All supported record types" in html
    assert "complaint records only" in html
    assert_no_secret_html(html)


def test_retrieval_failure_is_safe_and_does_not_import(tmp_path: Path) -> None:
    client = MockCcldRetrievalClient(fail_reports=True)
    with _empty_connection() as connection:
        context = _request_context(connection, tmp_path, client=client)
        status, _content_type, body = route_response(
            CCLD_RECORD_REQUEST_PATH,
            method="POST",
            request_body=_retrieval_form_bytes(),
            ccld_record_request_ui_context=context,
        )
        counts = _table_counts(connection)
        jobs = connection.execute(select(hosted_ccld_retrieval_jobs)).mappings().all()

    html = body.decode("utf-8")

    assert status == 200
    assert counts["source_records"] == 0
    assert counts["retrieval_jobs"] == 1
    assert jobs[0]["job_state"] == "completed_with_warnings"
    assert "Completed with warnings" in html
    assert "No records were imported" in html
    assert "Controlled CCLD retrieval completed with no matching imported records" in html
    assert "Report 39 failed during fetch" in html
    assert "Safe warnings" in html
    assert "Safe errors" in html
    assert "traceback" not in html.casefold()
    assert_no_secret_html(html)


def test_retrieval_rate_limit_blocks_without_network_call(tmp_path: Path) -> None:
    client = MockCcldRetrievalClient()
    with _empty_connection() as connection:
        context = _request_context(connection, tmp_path, client=client, rate_limit=1)
        connection.execute(
            hosted_ccld_retrieval_jobs.insert().values(
                retrieval_job_id="queued-test-job",
                created_at="2026-06-15T12:00:00+00:00",
                updated_at="2026-06-15T12:00:00+00:00",
                job_state="queued",
                facility_number="157806098",
                record_type="complaints",
                start_date="2022-08-01",
                end_date="2022-08-31",
                source_scope_type=TEST_SCOPE.scope_type,
                source_scope_id=TEST_SCOPE.scope_id,
                actor_provider_subject="fixture-retrieval-reviewer",
                actor_provider_issuer="fixture-managed-oidc-provider",
                actor_display_name="Fixture Retrieval Reviewer",
                actor_category="tester",
                authorization_permission="retrieval_job_trigger",
                request_limit="1",
                retry_limit="0",
                timeout_seconds="5",
                raw_storage_path="raw",
                source_artifact_identity=None,
                result_counts={},
                warnings=[],
                errors=[],
                safe_message="queued",
                data_mutations_performed=False,
            )
        )
        status, _content_type, body = route_response(
            CCLD_RECORD_REQUEST_PATH,
            method="POST",
            request_body=_retrieval_form_bytes(),
            ccld_record_request_ui_context=context,
        )
        counts = _table_counts(connection)

    html = body.decode("utf-8")

    assert status == 200
    assert counts["source_records"] == 0
    assert counts["retrieval_jobs"] == 2
    assert client.facility_detail_calls == []
    assert "rate_limited" in html
    assert "rate-limited" in html
    assert "Rate limited" in html
    assert "Wait for an active retrieval job to finish" in html
    assert_no_secret_html(html)


def test_retrieval_status_summary_explains_queued_running_and_failed_states() -> None:
    queued_html = _render_retrieval_job_summary(_job_result("queued"))
    running_html = _render_retrieval_job_summary(_job_result("running"))
    failed_html = _render_retrieval_job_summary(
        _job_result("failed", errors=("Controlled retrieval failed safely.",))
    )

    assert "Queued" in queued_html
    assert "Wait for the server-side job to start" in queued_html
    assert "Running" in running_html
    assert "Refresh the request status later" in running_html
    assert "Failed" in failed_html
    assert "Retry later or ask an operator" in failed_html
    assert "Traceback" not in failed_html
    assert_no_secret_html(queued_html)
    assert_no_secret_html(running_html)
    assert_no_secret_html(failed_html)


def test_anonymous_production_retrieval_is_blocked() -> None:
    auth_config = load_hosted_auth_runtime_config(
        environ={"CCLD_HOSTED_TESTER_AUTH_MODE": "production"}
    )

    status, _content_type, body = route_response(
        CCLD_RECORD_REQUEST_PATH,
        method="POST",
        request_body=_retrieval_form_bytes(),
        auth_runtime_config=auth_config,
        page_data_mode="postgres",
    )
    html = body.decode("utf-8")

    assert status == 401
    assert "CCLD workflow access requires sign-in" in html
    assert_no_secret_html(html)


def test_feedback_route_still_uses_mocked_client() -> None:
    github_config_kwargs: dict[str, Any] = {
        "repo": "example/repo",
        "token": PLACEHOLDER_AUTH_VALUE,
    }
    feedback_context = FeedbackContext(
        actor=_actor(),
        scope=TEST_SCOPE,
        github_config=GitHubFeedbackConfig(**github_config_kwargs),
        github_client=MockGitHubIssueClient(),
        now=lambda: datetime(2026, 6, 15, 12, 0, 0, tzinfo=UTC),
    )

    status, _content_type, body = route_response(
        "/feedback",
        method="POST",
        request_body=urlencode(
            {
                "feedback_type": "Bug report",
                "description": "Retrieval job form copy looks clear.",
                "page_path": CCLD_RECORD_REQUEST_PATH,
            }
        ).encode("utf-8"),
        feedback_context=feedback_context,
    )
    html = body.decode("utf-8")

    assert status == 201
    assert "Feedback submitted" in html
    assert_no_secret_html(html)


def _request_context(
    connection: Connection,
    tmp_path: Path,
    *,
    client: MockCcldRetrievalClient | None = None,
    rate_limit: int = 3,
) -> CcldRecordRequestUiContext:
    reviewer_context = reviewer_ui_context_for_connection(
        connection,
        actor=_actor(),
    )
    source_context = reviewer_context.workflow_shell_context.source_derived_api_context
    retrieval_context = CcldRetrievalContext(
        connection=connection,
        actor=source_context.actor,
        scope=source_context.scope,
        config=CcldRetrievalConfig(
            enabled=True,
            raw_dir=tmp_path / "raw",
            max_date_range_days=30,
            per_job_request_limit=1,
            rate_limit_per_actor=rate_limit,
            timeout_seconds=5,
            retry_limit=0,
        ),
        client=client or MockCcldRetrievalClient(),
        now=lambda: datetime(2026, 6, 15, 12, 0, 0, tzinfo=UTC),
    )
    return ccld_record_request_context_for_reviewer_context(
        reviewer_context,
        retrieval_context=retrieval_context,
    )


def _job_result(
    state: str,
    *,
    errors: tuple[str, ...] = (),
) -> CcldRetrievalJobResult:
    return CcldRetrievalJobResult(
        retrieval_job_id=f"ccld-retrieval-157806098-{state}",
        job_state=cast(Any, state),
        facility_number="157806098",
        record_type="complaints",
        start_date="2022-08-01",
        end_date="2022-08-31",
        source_artifact_identity=None,
        result_counts={},
        warnings=(),
        errors=errors,
        safe_message="test status",
    )


def _empty_connection() -> Connection:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)
    return engine.connect()


def _retrieval_form_bytes(
    *,
    facility_number: str = "157806098",
    record_type: str = "complaints",
    start_date: str = "2022-08-01",
    end_date: str = "2022-08-31",
) -> bytes:
    return urlencode(
        {
            "facility_number": facility_number,
            "record_type": record_type,
            "start_date": start_date,
            "end_date": end_date,
            "ccld_retrieval_action": "run_controlled_ccld_retrieval",
        }
    ).encode("utf-8")


def _local_dev_auth_config() -> Any:
    return load_hosted_auth_runtime_config(
        environ={
            "CCLD_HOSTED_TESTER_AUTH_MODE": "local-dev",
            "CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH": "enabled",
        }
    )


def _actor() -> AuthenticatedActor:
    return AuthenticatedActor(
        provider_subject="fixture-retrieval-reviewer",
        provider_issuer="fixture-managed-oidc-provider",
        display_name="Fixture Retrieval Reviewer",
        email=None,
        actor_category="tester",
        account_status=cast(HostedAccountStatus, "active"),
        roles=(cast(HostedTesterRole, "tester_reviewer"),),
        scopes=(TEST_SCOPE,),
    )


def _table_counts(connection: Connection) -> dict[str, int]:
    return {
        "import_batches": connection.execute(
            select(func.count()).select_from(hosted_import_batches)
        ).scalar_one(),
        "source_records": connection.execute(
            select(func.count()).select_from(hosted_source_derived_records)
        ).scalar_one(),
        "reviewer_created_state": connection.execute(
            select(func.count()).select_from(hosted_reviewer_created_state)
        ).scalar_one(),
        "audit_events": connection.execute(
            select(func.count()).select_from(hosted_audit_events)
        ).scalar_one(),
        "retrieval_jobs": connection.execute(
            select(func.count()).select_from(hosted_ccld_retrieval_jobs)
        ).scalar_one(),
    }


def _empty_counts() -> dict[str, int]:
    return {
        "import_batches": 0,
        "source_records": 0,
        "reviewer_created_state": 0,
        "audit_events": 0,
        "retrieval_jobs": 0,
    }


def assert_no_secret_html(markup: str) -> None:
    lowered = markup.casefold()
    for marker in [
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
        "fixture-managed-oidc-provider",
        "fixture-retrieval-reviewer",
        "test-auth-value-not-rendered",
    ]:
        assert marker not in lowered
