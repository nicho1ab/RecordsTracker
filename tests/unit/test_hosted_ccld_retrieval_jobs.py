from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlencode

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Connection

from ccld_complaints.connectors.ccld import facility_reports as ccld_facility_reports
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
    CCLD_RETRIEVAL_JOB_DETAIL_PATH,
    CCLD_RETRIEVAL_JOBS_PATH,
    CcldRecordRequestUiContext,
    _render_retrieval_job_summary,
    ccld_record_request_context_for_reviewer_context,
    reset_default_ccld_record_request_ui_context,
)
from ccld_complaints.hosted_app.ccld_retrieval_jobs import (
    CCLD_RETRIEVAL_DEMO_MODE_ENV,
    CCLD_RETRIEVAL_DEMO_MODE_MOCK_SUCCESS,
    CCLD_RETRIEVAL_ENABLED_ENV,
    CCLD_RETRIEVAL_ENABLED_VALUE,
    CCLD_RETRIEVAL_MAX_DATE_RANGE_DAYS_ENV,
    CCLD_RETRIEVAL_RAW_DIR_ENV,
    CcldHttpRetrievalClient,
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
    reset_default_local_test_reviewer_ui_context,
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
    def __init__(
        self,
        *,
        fail_reports: bool = False,
        facility_detail_html: str | None = None,
        report_content_by_index: Mapping[int, bytes] | None = None,
    ) -> None:
        self.fail_reports = fail_reports
        self.facility_detail_html = facility_detail_html
        self.report_content_by_index = report_content_by_index
        self.facility_detail_calls: list[tuple[str, int]] = []
        self.report_calls: list[tuple[str, int]] = []

    def fetch_facility_detail(self, facility_number: str, *, timeout_seconds: int) -> str:
        self.facility_detail_calls.append((facility_number, timeout_seconds))
        if self.facility_detail_html is not None:
            return self.facility_detail_html
        return DETAIL_FIXTURE.read_text(encoding="utf-8")

    def fetch_report(self, source_url: str, *, timeout_seconds: int) -> bytes:
        self.report_calls.append((source_url, timeout_seconds))
        if self.fail_reports:
            raise RuntimeError("mock report timeout")
        if self.report_content_by_index is not None:
            report_index = _report_index_from_url(source_url)
            if report_index not in self.report_content_by_index:
                raise AssertionError(f"Unexpected report fetch for index {report_index}")
            return self.report_content_by_index[report_index]
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
    assert "Retrieve complaint records" in html
    assert "facility-suggestion-list" in html
    assert "Confirm facility" in html
    assert "Search by name, license number, city, ZIP, type, or status." in html
    assert "Review boundary" not in normalized
    assert "Confirm facility" in html
    assert "Find facility" in html
    assert "Which facility should be reviewed?" in html
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
    assert "No controlled retrieval job exists for this request" in blocked_html
    assert "Return to the request page to review already-loaded local/test records" in (
        blocked_normalized
    )
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
    assert "Complaint records ready for attorney review" in html
    assert "Job state" in html
    assert "Completed" in html
    assert "Retrieval job created" in html
    assert "Retrieval job submitted" in html
    assert "Controlled retrieval job submitted and completed" in html
    assert "1 loaded local/test queue row(s) are visible now" not in html
    assert "1 complaint queue record(s) are visible now" in html
    assert "1 complaint queue record(s) are ready for review" in html
    assert "Complaint records ready" in html
    assert "Retrieval status/progress summary" in html
    assert "Next safe action" in html
    assert "Records imported" in html
    assert "Imported source derived records" in normalized
    assert "Controlled CCLD retrieval completed and imported validated records" in html
    assert "What to do next" in html
    assert "Open the imported records in the queue" in html
    assert "Review imported records" in html
    assert "View retrieval job history" in html
    assert "View job details" in html
    assert "Send tester feedback" in html
    assert "Complaint records ready for attorney review" in html
    assert "Open reviewer detail" in html
    assert_no_secret_html(html)


def test_controlled_retrieval_fetches_only_complaint_links_in_requested_date_range(
    tmp_path: Path,
) -> None:
    client = MockCcldRetrievalClient(
        facility_detail_html=_facility_detail_with_mixed_complaint_links(),
        report_content_by_index={3: RAW_FIXTURE.read_bytes()},
    )
    with _empty_connection() as connection:
        context = _request_context(connection, tmp_path, client=client)
        status, _content_type, body = route_response(
            CCLD_RECORD_REQUEST_PATH,
            method="POST",
            request_body=_retrieval_form_bytes(
                start_date="2022-08-20",
                end_date="2022-08-31",
            ),
            ccld_record_request_ui_context=context,
        )
        counts = _table_counts(connection)
        jobs = connection.execute(select(hosted_ccld_retrieval_jobs)).mappings().all()

    html = body.decode("utf-8")

    assert status == 200
    assert len(client.facility_detail_calls) == 1
    assert [_report_index_from_url(url) for url, _timeout in client.report_calls] == [3]
    assert counts["source_records"] == 26
    assert counts["retrieval_jobs"] == 1
    assert jobs[0]["job_state"] == "completed"
    assert jobs[0]["facility_number"] == "157806098"
    assert jobs[0]["record_type"] == "complaints"
    assert jobs[0]["start_date"] == "2022-08-20"
    assert jobs[0]["end_date"] == "2022-08-31"
    assert jobs[0]["result_counts"]["discovered_report_candidates"] == 3
    assert jobs[0]["result_counts"]["selected_report_candidates"] == 1
    assert jobs[0]["result_counts"]["retrieved_record_bundles"] == 1
    assert "Controlled CCLD retrieval imported source-derived records" in html
    assert "Review imported records" in html
    assert "32-CR-20220407124448" in html
    assert "public-source completeness" not in html.casefold()
    assert_no_secret_html(html)


def test_controlled_retrieval_no_matching_complaint_dates_fetches_nothing(
    tmp_path: Path,
) -> None:
    client = MockCcldRetrievalClient(
        facility_detail_html=_facility_detail_with_mixed_complaint_links(),
        report_content_by_index={3: RAW_FIXTURE.read_bytes()},
    )
    with _empty_connection() as connection:
        context = _request_context(connection, tmp_path, client=client)
        status, _content_type, body = route_response(
            CCLD_RECORD_REQUEST_PATH,
            method="POST",
            request_body=_retrieval_form_bytes(
                start_date="2020-01-01",
                end_date="2020-01-31",
            ),
            ccld_record_request_ui_context=context,
        )
        counts = _table_counts(connection)
        jobs = connection.execute(select(hosted_ccld_retrieval_jobs)).mappings().all()

    html = body.decode("utf-8")

    assert status == 200
    assert len(client.facility_detail_calls) == 1
    assert client.report_calls == []
    assert counts["source_records"] == 0
    assert counts["retrieval_jobs"] == 1
    assert jobs[0]["job_state"] == "completed_with_warnings"
    assert jobs[0]["result_counts"]["discovered_report_candidates"] == 3
    assert jobs[0]["result_counts"]["selected_report_candidates"] == 0
    assert jobs[0]["result_counts"]["retrieved_record_bundles"] == 0
    assert "none had a discovered report date inside the requested date range" in html
    assert "No records were imported" in html
    assert "not a public-source absence" in html
    assert_no_secret_html(html)


def test_local_dev_mock_success_retrieval_flow_imports_and_links_without_live_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_live_call(*args: object, **kwargs: object) -> str:
        raise AssertionError("live CCLD client should not be used in mock-success mode")

    monkeypatch.setenv(CCLD_RETRIEVAL_ENABLED_ENV, CCLD_RETRIEVAL_ENABLED_VALUE)
    monkeypatch.setenv(CCLD_RETRIEVAL_RAW_DIR_ENV, str(tmp_path / "raw"))
    monkeypatch.setenv(CCLD_RETRIEVAL_MAX_DATE_RANGE_DAYS_ENV, "30")
    monkeypatch.setenv(CCLD_RETRIEVAL_DEMO_MODE_ENV, CCLD_RETRIEVAL_DEMO_MODE_MOCK_SUCCESS)
    monkeypatch.setattr(CcldHttpRetrievalClient, "fetch_facility_detail", fail_live_call)

    status, _content_type, body = route_response(
        CCLD_RECORD_REQUEST_PATH,
        method="POST",
        request_body=_retrieval_form_bytes(),
        auth_runtime_config=_local_dev_auth_config(),
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")
    normalized = " ".join(html.split())
    job_id = _retrieval_job_id_from_html(html)

    assert status == 200
    assert "Complaint records ready for attorney review" in html
    assert "Fixture/mock demo" in html
    assert "Completed" in html
    assert "Records imported" in html
    assert "Imported source derived records" in normalized
    assert "Review imported records" in html
    assert "View retrieval job history" in html
    assert "View job details" in html
    assert "Complaint records ready for attorney review" in html
    assert "Open reviewer detail" in html
    assert sorted((tmp_path / "raw").glob("*.html"))
    assert_no_secret_html(html)

    history_status, _content_type, history_body = route_response(
        CCLD_RETRIEVAL_JOBS_PATH,
        auth_runtime_config=_local_dev_auth_config(),
        page_data_mode="fixture-demo",
    )
    history_html = history_body.decode("utf-8")

    assert history_status == 200
    assert job_id in history_html
    assert "Fixture/mock demo" in history_html
    assert "Completed" in history_html
    assert "Review imported records in the CCLD queue" in history_html
    assert "View retrieval job details" in history_html
    assert_no_secret_html(history_html)

    detail_status, _content_type, detail_body = route_response(
        f"{CCLD_RETRIEVAL_JOB_DETAIL_PATH}?job_id={job_id}",
        auth_runtime_config=_local_dev_auth_config(),
        page_data_mode="fixture-demo",
    )
    detail_html = detail_body.decode("utf-8")

    assert detail_status == 200
    assert "Retrieval job detail" in detail_html
    assert job_id in detail_html
    assert "Fixture/mock demo" in detail_html
    assert "Completed" in detail_html
    assert "Records imported" in detail_html
    assert "raw artifact preserved" in detail_html
    assert "Review imported records in the CCLD queue" in detail_html
    assert "Return to retrieval job history" in detail_html
    assert_no_secret_html(detail_html)


def test_demo_startup_env_creates_retrieval_job_from_default_request_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_live_call(*args: object, **kwargs: object) -> str:
        raise AssertionError("live CCLD client should not be used in demo startup mode")

    reset_default_ccld_record_request_ui_context()
    reset_default_local_test_reviewer_ui_context()
    monkeypatch.setenv("CCLD_HOSTED_TESTER_AUTH_MODE", "local-dev")
    monkeypatch.setenv("CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH", "enabled")
    monkeypatch.setenv("CCLD_HOSTED_PAGE_DATA_MODE", "fixture-demo")
    monkeypatch.setenv(CCLD_RETRIEVAL_ENABLED_ENV, CCLD_RETRIEVAL_ENABLED_VALUE)
    monkeypatch.setenv(CCLD_RETRIEVAL_RAW_DIR_ENV, str(tmp_path / "raw"))
    monkeypatch.setenv(CCLD_RETRIEVAL_MAX_DATE_RANGE_DAYS_ENV, "30")
    monkeypatch.setenv(CCLD_RETRIEVAL_DEMO_MODE_ENV, CCLD_RETRIEVAL_DEMO_MODE_MOCK_SUCCESS)
    monkeypatch.setattr(CcldHttpRetrievalClient, "fetch_facility_detail", fail_live_call)
    try:
        status, _content_type, body = route_response(
            CCLD_RECORD_REQUEST_PATH,
            method="POST",
            request_body=_retrieval_form_bytes(),
        )
        history_status, _content_type, history_body = route_response(CCLD_RETRIEVAL_JOBS_PATH)
    finally:
        reset_default_ccld_record_request_ui_context()
        reset_default_local_test_reviewer_ui_context()

    html = body.decode("utf-8")
    history_html = history_body.decode("utf-8")
    job_id = _retrieval_job_id_from_html(html)

    assert status == 200
    assert "Controlled CCLD retrieval setup required" not in html
    assert "Complaint records ready for attorney review" in html
    assert "Fixture/mock demo" in html
    assert "Completed" in html
    assert "Records imported" in html
    assert sorted((tmp_path / "raw").glob("*.html"))
    assert history_status == 200
    assert job_id in history_html
    assert "Retrieval status center" in history_html
    assert "Fixture/mock demo" in history_html
    assert "Completed" in history_html
    assert "local-test-managed-identity" not in html
    assert "local-test-managed-identity" not in history_html
    assert_no_secret_html(html)
    assert_no_secret_html(history_html)


def test_live_startup_env_uses_public_ccld_client_and_imports_into_reviewer_queue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    live_facility_calls: list[tuple[str, int]] = []
    live_report_calls: list[tuple[str, int]] = []

    def fetch_live_facility_detail(
        self: CcldHttpRetrievalClient,
        facility_number: str,
        *,
        timeout_seconds: int,
    ) -> str:
        live_facility_calls.append((facility_number, timeout_seconds))
        return DETAIL_FIXTURE.read_text(encoding="utf-8")

    def fetch_live_report(
        self: CcldHttpRetrievalClient,
        source_url: str,
        *,
        timeout_seconds: int,
    ) -> bytes:
        live_report_calls.append((source_url, timeout_seconds))
        return RAW_FIXTURE.read_bytes()

    reset_default_ccld_record_request_ui_context()
    reset_default_local_test_reviewer_ui_context()
    monkeypatch.setenv("CCLD_HOSTED_TESTER_AUTH_MODE", "local-dev")
    monkeypatch.setenv("CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH", "enabled")
    monkeypatch.setenv("CCLD_HOSTED_PAGE_DATA_MODE", "fixture-demo")
    monkeypatch.setenv(CCLD_RETRIEVAL_ENABLED_ENV, CCLD_RETRIEVAL_ENABLED_VALUE)
    monkeypatch.setenv(CCLD_RETRIEVAL_RAW_DIR_ENV, str(tmp_path / "raw"))
    monkeypatch.setenv(CCLD_RETRIEVAL_MAX_DATE_RANGE_DAYS_ENV, "30")
    monkeypatch.delenv(CCLD_RETRIEVAL_DEMO_MODE_ENV, raising=False)
    monkeypatch.setattr(
        CcldHttpRetrievalClient,
        "fetch_facility_detail",
        fetch_live_facility_detail,
    )
    monkeypatch.setattr(CcldHttpRetrievalClient, "fetch_report", fetch_live_report)
    try:
        status, _content_type, body = route_response(
            CCLD_RECORD_REQUEST_PATH,
            method="POST",
            request_body=_retrieval_form_bytes(),
        )
        history_status, _content_type, history_body = route_response(CCLD_RETRIEVAL_JOBS_PATH)
        reviewer_status, _content_type, reviewer_body = route_response("/reviewer")
    finally:
        reset_default_ccld_record_request_ui_context()
        reset_default_local_test_reviewer_ui_context()

    html = body.decode("utf-8")
    history_html = history_body.decode("utf-8")
    reviewer_html = reviewer_body.decode("utf-8")
    job_id = _retrieval_job_id_from_html(html)

    assert status == 200
    assert live_facility_calls == [("157806098", 30)]
    assert len(live_report_calls) == 1
    assert _report_index_from_url(live_report_calls[0][0]) == 3
    assert "mock-success" not in html
    assert "Live public CCLD" in html
    assert "Fixture/mock demo" not in html
    assert "Records imported" in html
    assert sorted((tmp_path / "raw").glob("*.html"))
    assert history_status == 200
    assert job_id in history_html
    assert "Live public CCLD" in history_html
    assert reviewer_status == 200
    assert "32-CR-20220407124448" in reviewer_html
    assert_no_secret_html(html)
    assert_no_secret_html(history_html)
    assert_no_secret_html(reviewer_html)


def test_live_retrieval_falls_back_to_complaint_report_list_when_detail_has_no_links(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_list_json = b"""{
        "REPORTARRAY": [
            {"FACILITYNUMBER": "157806098", "REPORTDATE": "07/27/2021", "REPORTTYPE": "Complaint"},
            {"FACILITYNUMBER": "157806098", "REPORTDATE": "08/24/2022", "REPORTTYPE": "Complaint"},
            {"FACILITYNUMBER": "157806098", "REPORTDATE": "08/24/2022", "REPORTTYPE": "Other"},
            {"FACILITYNUMBER": "123456789", "REPORTDATE": "08/24/2022", "REPORTTYPE": "Complaint"}
        ]
    }"""

    def fetch_report_list(source_url: str) -> bytes:
        assert source_url == "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports/157806098"
        return report_list_json

    client = MockCcldRetrievalClient(
        facility_detail_html="<html><body><h1>Facility Detail</h1></body></html>",
        report_content_by_index={1: RAW_FIXTURE.read_bytes()},
    )
    monkeypatch.setattr(ccld_facility_reports, "_fetch_url", fetch_report_list)
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
    assert [_report_index_from_url(url) for url, _timeout in client.report_calls] == [1]
    assert counts["source_records"] == 26
    assert jobs[0]["result_counts"]["discovered_report_candidates"] == 2
    assert jobs[0]["result_counts"]["selected_report_candidates"] == 1
    assert "Live public CCLD" in html
    assert "Records imported" in html
    assert_no_secret_html(html)


def test_live_retrieval_no_complaint_candidates_reports_specific_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fetch_report_list(source_url: str) -> bytes:
        return (
            b'{"REPORTARRAY":[{"FACILITYNUMBER":"157806098",'
            b'"REPORTDATE":"08/24/2022","REPORTTYPE":"Other"}]}'
        )

    client = MockCcldRetrievalClient(
        facility_detail_html="""
        <html><body>
        <h2>All Visits</h2>
        <a href="/transparencyapi/api/FacilityReports?facNum=157806098&inx=3">08/24/2022</a>
        </body></html>
        """,
        report_content_by_index={3: RAW_FIXTURE.read_bytes()},
    )
    monkeypatch.setattr(ccld_facility_reports, "_fetch_url", fetch_report_list)
    with _empty_connection() as connection:
        context = _request_context(connection, tmp_path, client=client)
        status, _content_type, body = route_response(
            CCLD_RECORD_REQUEST_PATH,
            method="POST",
            request_body=_retrieval_form_bytes(),
            ccld_record_request_ui_context=context,
        )

    html = body.decode("utf-8")

    assert status == 200
    assert len(client.facility_detail_calls) == 1
    assert client.report_calls == []
    assert "No CCLD complaint report links were discovered for the requested facility" in html
    assert "none had a discovered report date" not in html
    assert_no_secret_html(html)


def test_live_retrieval_import_mismatch_reports_specific_warning(tmp_path: Path) -> None:
    mismatched_report = RAW_FIXTURE.read_bytes().replace(b"157806098", b"123456789")
    client = MockCcldRetrievalClient(
        facility_detail_html=_facility_detail_with_mixed_complaint_links(),
        report_content_by_index={3: mismatched_report},
    )
    with _empty_connection() as connection:
        context = _request_context(connection, tmp_path, client=client)
        status, _content_type, body = route_response(
            CCLD_RECORD_REQUEST_PATH,
            method="POST",
            request_body=_retrieval_form_bytes(
                start_date="2022-08-20",
                end_date="2022-08-31",
            ),
            ccld_record_request_ui_context=context,
        )
        counts = _table_counts(connection)

    html = body.decode("utf-8")

    assert status == 200
    assert len(client.report_calls) == 1
    assert counts["source_records"] == 0
    assert "fetched and extracted" in html
    assert "no normalized complaint records matched the requested facility/date range" in html
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
    assert (
        "Controlled CCLD retrieval (live public CCLD mode): Controlled CCLD "
        "retrieval completed with no matching imported records"
    ) in html
    assert "Report 3 failed during fetch; the public source may be unavailable" in html
    assert "Live public CCLD" in html
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
    assert "Retrieval status/progress summary" in queued_html
    assert "Current state" in queued_html
    assert "Records ready" in queued_html
    assert "0 imported source-derived record(s) are available from this job" in queued_html
    assert "Wait for the server-side job to start" in queued_html
    assert "Running" in running_html
    assert "Refresh the request status later" in running_html
    assert "Failed" in failed_html
    assert "Retry later or ask an operator" in failed_html
    assert "Traceback" not in failed_html
    assert_no_secret_html(queued_html)
    assert_no_secret_html(running_html)
    assert_no_secret_html(failed_html)


def test_retrieval_job_history_empty_state_renders_for_allowed_local_dev_actor() -> None:
    with _empty_connection() as connection:
        reviewer_context = reviewer_ui_context_for_connection(
            connection,
            actor=_actor(),
        )
        request_context = ccld_record_request_context_for_reviewer_context(reviewer_context)
        status, content_type, body = route_response(
            CCLD_RETRIEVAL_JOBS_PATH,
            ccld_record_request_ui_context=request_context,
        )
    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Retrieval status center" in html
    assert "Job list" in html
    assert "Table view" in html
    assert "No retrieval jobs have been submitted" in html
    assert "no controlled retrieval status/progress to wait on yet" in " ".join(
        html.split()
    )
    assert "already-loaded local/test records" in html
    assert "Controlled retrieval setup is missing" in html
    assert "facility/date context" in html
    assert "imported-record counts" in html
    assert "Submit or change retrieval request" in html
    assert "Send tester feedback" in html
    assert_no_secret_html(html)


def test_anonymous_production_retrieval_job_history_is_blocked() -> None:
    auth_config = load_hosted_auth_runtime_config(
        environ={"CCLD_HOSTED_TESTER_AUTH_MODE": "production"}
    )

    status, _content_type, body = route_response(
        CCLD_RETRIEVAL_JOBS_PATH,
        auth_runtime_config=auth_config,
        page_data_mode="postgres",
    )
    html = body.decode("utf-8")

    assert status == 401
    assert "CCLD workflow access requires sign-in" in html
    assert_no_secret_html(html)


def test_retrieval_job_history_renders_recent_jobs_safely_without_mutation(
    tmp_path: Path,
) -> None:
    with _empty_connection() as connection:
        context = _request_context(connection, tmp_path)
        _insert_history_job(
            connection,
            "completed-job",
            state="completed",
            created_at="2026-06-15T12:00:00+00:00",
            updated_at="2026-06-15T12:04:00+00:00",
            result_counts={"imported_source_derived_records": 6},
            source_artifact_identity="ccld-retrieval-job:completed-job",
            safe_message="Controlled CCLD retrieval imported source-derived records.",
        )
        _insert_history_job(
            connection,
            "warning-job",
            state="completed_with_warnings",
            created_at="2026-06-15T12:10:00+00:00",
            updated_at="2026-06-15T12:14:00+00:00",
            result_counts={"imported_source_derived_records": 0},
            warnings=("Report 39 failed during fetch.",),
            safe_message="Controlled CCLD retrieval completed with no matching imported records.",
        )
        _insert_history_job(
            connection,
            "failed-job",
            state="failed",
            created_at="2026-06-15T12:20:00+00:00",
            updated_at="2026-06-15T12:21:00+00:00",
            errors=("Traceback contained token and provider_subject details.",),
            safe_message="Failure included token and provider_subject values.",
        )
        _insert_history_job(
            connection,
            "rate-limited-job",
            state="rate_limited",
            created_at="2026-06-15T12:30:00+00:00",
            updated_at="2026-06-15T12:30:00+00:00",
            safe_message="Controlled CCLD retrieval is rate-limited for this tester.",
        )
        before_counts = _table_counts(connection)
        status, content_type, body = route_response(
            CCLD_RETRIEVAL_JOBS_PATH,
            ccld_record_request_ui_context=context,
        )
        after_counts = _table_counts(connection)

    html = body.decode("utf-8")
    normalized = " ".join(html.split())

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert before_counts == after_counts
    assert "Controlled retrieval is configured for this runtime" in html
    assert "To review records already loaded without submitting a job" in normalized
    assert "choose Show existing queue" in normalized
    assert "Not recorded" in html
    assert "completed-job" in html
    assert "warning-job" in html
    assert "failed-job" in html
    assert "rate-limited-job" in html
    assert f"{CCLD_RETRIEVAL_JOB_DETAIL_PATH}?job_id=completed-job" in html
    assert "View retrieval job details" in html
    assert "Facility/license number" in html
    assert "157806098" in html
    assert "Complaint records" in html
    assert "2022-08-01 to 2022-08-31" in html
    assert "Created at" in html
    assert "Started timestamp" in html
    assert "Completed or last updated at" in html
    assert "Records imported" in html
    assert "Current state" in html
    assert "These counts summarize controlled retrieval job metadata only" in html
    assert "Review imported records in the CCLD queue" in html
    assert "Report 39 failed during fetch." in html
    assert "Completed with warnings" in html
    assert "No records were imported. Review warnings" in normalized
    assert "Failed" in html
    assert "Retry later or ask an operator to inspect server logs" in normalized
    assert "Rate limited" in html
    assert "Wait for an active retrieval job to finish" in normalized
    assert "raw artifact preserved; source artifact identity available; raw paths not shown" in html
    assert "Send tester feedback" in html
    assert "Traceback" not in html
    assert "provider_subject" not in html
    assert_no_secret_html(html)


def test_retrieval_job_detail_renders_completed_job_without_mutation(tmp_path: Path) -> None:
    with _empty_connection() as connection:
        context = _request_context(connection, tmp_path)
        _insert_history_job(
            connection,
            "completed-job",
            state="completed",
            created_at="2026-06-15T12:00:00+00:00",
            updated_at="2026-06-15T12:04:00+00:00",
            result_counts={
                "imported_source_derived_records": 6,
                "retrieved_record_bundles": 1,
            },
            source_artifact_identity="ccld-retrieval-job:completed-job",
            raw_storage_path="C:/server/private/raw/artifact.html",
            safe_message="Controlled CCLD retrieval imported source-derived records.",
        )
        before_counts = _table_counts(connection)
        status, content_type, body = route_response(
            f"{CCLD_RETRIEVAL_JOB_DETAIL_PATH}?job_id=completed-job",
            ccld_record_request_ui_context=context,
        )
        after_counts = _table_counts(connection)

    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert before_counts == after_counts
    assert "Retrieval job detail" in html
    assert "Job summary and next step" in html
    assert "Current status/progress" in html
    assert "Controlled CCLD retrieval completed and imported validated records" in html
    assert "Next safe action" in html
    assert "Open imported records in the CCLD queue and review source traceability" in html
    assert "Technical counts, warnings, and errors" in html
    assert "completed-job" in html
    assert "Completed" in html
    assert "Not recorded" in html
    assert "completed" in html
    assert "Facility/license number" in html
    assert "157806098" in html
    assert "Complaint records" in html
    assert "2022-08-01 to 2022-08-31" in html
    assert "Created at" in html
    assert "Started timestamp" in html
    assert "not separately tracked in this first slice" in html
    assert "Last updated at" in html
    assert "Completed timestamp" in html
    assert "2026-06-15T12:04:00+00:00" in html
    assert "Records imported" in html
    assert "<dd>6</dd>" in html
    assert "Imported source derived records" in html
    assert "raw artifact preserved; source artifact identity available; raw paths not shown" in html
    assert "Review imported records in the CCLD queue" in html
    assert "Return to retrieval job history" in html
    assert "Submit or change a CCLD record request" in html
    assert "Read CCLD workflow help" in html
    assert "Send tester feedback" in html
    assert "C:/server/private/raw/artifact.html" not in html
    assert "157806098_inx3" not in html
    assert_no_secret_html(html)


def test_retrieval_job_detail_safe_missing_and_invalid_job_ids(tmp_path: Path) -> None:
    with _empty_connection() as connection:
        context = _request_context(connection, tmp_path)
        missing_status, _content_type, missing_body = route_response(
            f"{CCLD_RETRIEVAL_JOB_DETAIL_PATH}?job_id=missing-job",
            ccld_record_request_ui_context=context,
        )
        invalid_status, _content_type, invalid_body = route_response(
            f"{CCLD_RETRIEVAL_JOB_DETAIL_PATH}?job_id=..%2Ftoken-value",
            ccld_record_request_ui_context=context,
        )
        blank_status, _content_type, blank_body = route_response(
            CCLD_RETRIEVAL_JOB_DETAIL_PATH,
            ccld_record_request_ui_context=context,
        )
        counts = _table_counts(connection)

    missing_html = missing_body.decode("utf-8")
    invalid_html = invalid_body.decode("utf-8")
    blank_html = blank_body.decode("utf-8")

    assert missing_status == 404
    assert "Retrieval job detail not found" in missing_html
    assert "No retrieval job metadata matched" in missing_html
    assert "Return to retrieval job history" in missing_html
    assert invalid_status == 400
    assert blank_status == 400
    assert "Retrieval job detail needs a valid job ID" in invalid_html
    assert "Retrieval job detail needs a valid job ID" in blank_html
    assert "token-value" not in invalid_html
    assert counts == _empty_counts()
    assert_no_secret_html(missing_html)
    assert_no_secret_html(invalid_html)
    assert_no_secret_html(blank_html)


def test_retrieval_job_detail_distinguishes_warning_failed_and_rate_limited_states(
    tmp_path: Path,
) -> None:
    with _empty_connection() as connection:
        context = _request_context(connection, tmp_path)
        _insert_history_job(
            connection,
            "warning-job",
            state="completed_with_warnings",
            created_at="2026-06-15T12:10:00+00:00",
            updated_at="2026-06-15T12:14:00+00:00",
            result_counts={"imported_source_derived_records": 0},
            warnings=("Report 39 failed during fetch.",),
            safe_message="Controlled CCLD retrieval completed with no matching imported records.",
        )
        _insert_history_job(
            connection,
            "failed-job",
            state="failed",
            created_at="2026-06-15T12:20:00+00:00",
            updated_at="2026-06-15T12:21:00+00:00",
            errors=("Traceback contained token and provider_subject details.",),
            safe_message="Failure included token and provider_subject values.",
        )
        _insert_history_job(
            connection,
            "rate-limited-job",
            state="rate_limited",
            created_at="2026-06-15T12:30:00+00:00",
            updated_at="2026-06-15T12:30:00+00:00",
            safe_message="Controlled CCLD retrieval is rate-limited for this tester.",
        )
        warning_status, _content_type, warning_body = route_response(
            f"{CCLD_RETRIEVAL_JOB_DETAIL_PATH}?job_id=warning-job",
            ccld_record_request_ui_context=context,
        )
        failed_status, _content_type, failed_body = route_response(
            f"{CCLD_RETRIEVAL_JOB_DETAIL_PATH}?job_id=failed-job",
            ccld_record_request_ui_context=context,
        )
        rate_status, _content_type, rate_body = route_response(
            f"{CCLD_RETRIEVAL_JOB_DETAIL_PATH}?job_id=rate-limited-job",
            ccld_record_request_ui_context=context,
        )
        counts = _table_counts(connection)

    warning_html = warning_body.decode("utf-8")
    failed_html = failed_body.decode("utf-8")
    rate_html = rate_body.decode("utf-8")

    assert warning_status == 200
    assert "Completed with warnings" in warning_html
    assert "Report 39 failed during fetch." in warning_html
    assert "No records were imported. Review warnings" in " ".join(warning_html.split())
    assert failed_status == 200
    assert "Failed" in failed_html
    assert "Retry later or ask an operator to inspect server logs" in " ".join(
        failed_html.split()
    )
    assert "Controlled CCLD retrieval was blocked safely." in failed_html
    assert "Traceback" not in failed_html
    assert "provider_subject" not in failed_html
    assert rate_status == 200
    assert "Rate limited" in rate_html
    assert "Wait for an active retrieval job to finish" in " ".join(rate_html.split())
    assert counts["source_records"] == 0
    assert counts["reviewer_created_state"] == 0
    assert counts["audit_events"] == 0
    assert counts["retrieval_jobs"] == 3
    assert_no_secret_html(warning_html)
    assert_no_secret_html(failed_html)
    assert_no_secret_html(rate_html)


def test_anonymous_production_retrieval_job_detail_is_blocked() -> None:
    auth_config = load_hosted_auth_runtime_config(
        environ={"CCLD_HOSTED_TESTER_AUTH_MODE": "production"}
    )

    status, _content_type, body = route_response(
        f"{CCLD_RETRIEVAL_JOB_DETAIL_PATH}?job_id=completed-job",
        auth_runtime_config=auth_config,
        page_data_mode="postgres",
    )
    html = body.decode("utf-8")

    assert status == 401
    assert "CCLD workflow access requires sign-in" in html
    assert_no_secret_html(html)


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


def test_mock_success_mode_is_blocked_outside_local_dev(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(CCLD_RETRIEVAL_ENABLED_ENV, CCLD_RETRIEVAL_ENABLED_VALUE)
    monkeypatch.setenv(CCLD_RETRIEVAL_RAW_DIR_ENV, str(tmp_path / "raw"))
    monkeypatch.setenv(CCLD_RETRIEVAL_DEMO_MODE_ENV, CCLD_RETRIEVAL_DEMO_MODE_MOCK_SUCCESS)
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


def _retrieval_job_id_from_html(markup: str) -> str:
    match = re.search(r"ccld-retrieval-157806098-\d+", markup)
    if match is None:
        raise AssertionError("Retrieval job ID not found in response HTML.")
    return match.group(0)


def _report_index_from_url(source_url: str) -> int:
        match = re.search(r"[?&]inx=(\d+)", source_url)
        if match is None:
                raise AssertionError(f"Report index not found in {source_url}")
        return int(match.group(1))


def _facility_detail_with_mixed_complaint_links() -> str:
        return """<!doctype html>
<html lang="en">
<body>
    <h1>Facility Detail</h1>
    <h2>All Visits</h2>
    <p>
        <a href="https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=157806098&amp;inx=39">05/04/2026</a>
        <a href="https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=157806098&amp;inx=3">08/24/2022</a>
    </p>
    <h2>Complaints</h2>
    <p>
        <a href="https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=157806098&amp;inx=37">01/07/2026</a>
        <a href="https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=157806098&amp;inx=33">08/09/2022</a>
        <a href="https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=157806098&amp;inx=3">08/24/2022</a>
        <a href="https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=123456789&amp;inx=4">08/24/2022</a>
    </p>
</body>
</html>"""


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


def _insert_history_job(
    connection: Connection,
    retrieval_job_id: str,
    *,
    state: str,
    created_at: str,
    updated_at: str,
    result_counts: dict[str, int] | None = None,
    warnings: tuple[str, ...] = (),
    errors: tuple[str, ...] = (),
    source_artifact_identity: str | None = None,
    raw_storage_path: str = "raw",
    safe_message: str = "Controlled CCLD retrieval status is available.",
) -> None:
    connection.execute(
        hosted_ccld_retrieval_jobs.insert().values(
            retrieval_job_id=retrieval_job_id,
            created_at=created_at,
            updated_at=updated_at,
            job_state=state,
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
            raw_storage_path=raw_storage_path,
            source_artifact_identity=source_artifact_identity,
            result_counts=result_counts or {},
            warnings=list(warnings),
            errors=list(errors),
            safe_message=safe_message,
            data_mutations_performed=bool(result_counts),
        )
    )


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
