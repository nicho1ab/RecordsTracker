from __future__ import annotations

from pathlib import Path
from typing import Any, cast
from urllib.parse import quote, urlencode

from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Connection

from ccld_complaints.hosted_app.app import route_response
from ccld_complaints.hosted_app.audit_events import hosted_audit_events
from ccld_complaints.hosted_app.auth import (
    AuthenticatedActor,
    HostedAccessScope,
    HostedAccountStatus,
    HostedActorCategory,
    HostedTesterRole,
)
from ccld_complaints.hosted_app.ccld_record_request_ui import (
    CCLD_RECORD_REQUEST_PATH,
    CcldRecordRequestUiContext,
    ccld_record_request_context_for_reviewer_context,
)
from ccld_complaints.hosted_app.reset_reload_dry_run import (
    hosted_reset_reload_planning_metadata,
)
from ccld_complaints.hosted_app.reviewer_created_state import hosted_reviewer_created_state
from ccld_complaints.hosted_app.reviewer_ui import (
    LOCAL_REVIEWER_UI_SCOPE,
    REVIEWER_UI_DETAIL_PATH,
    reviewer_ui_context_for_connection,
)
from ccld_complaints.hosted_app.seeded_import import (
    hosted_import_batches,
    hosted_seeded_import_metadata,
    hosted_source_derived_records,
    import_seeded_corpus_artifact,
    load_seeded_corpus_artifact,
)

FIXTURE = Path("tests/fixtures/hosted_seeded_corpus/validated_seeded_corpus.json")
TEST_SCOPE = LOCAL_REVIEWER_UI_SCOPE
COMPLAINT_KEY = "complaint:ccld:complaint:32-CR-20220407124448"


def test_ccld_record_request_page_renders_from_default_context() -> None:
    status, content_type, body = route_response("/ccld")
    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "CCLD record request" in html
    assert "CCLD-only local/test request" in html
    assert "CCLD facility/license number" in html
    assert "optional date range" in html
    assert "does not run live crawling or imports" in normalized_html
    assert "provider" not in html.casefold()
    assert_no_secret_html(html)


def test_ccld_record_request_validates_required_facility_and_digits() -> None:
    with _seeded_connection() as connection:
        missing_status, _content_type, missing_body = route_response(
            CCLD_RECORD_REQUEST_PATH,
            method="POST",
            request_body=_form_bytes({}),
            ccld_record_request_ui_context=_context(connection),
        )
        alpha_status, _content_type, alpha_body = route_response(
            CCLD_RECORD_REQUEST_PATH,
            method="POST",
            request_body=_form_bytes({"facility_number": "abc-157806098"}),
            ccld_record_request_ui_context=_context(connection),
        )
        counts = _table_counts(connection)

    missing_html = missing_body.decode("utf-8")
    alpha_html = alpha_body.decode("utf-8")

    assert missing_status == 400
    assert "Facility/license number is required." in missing_html
    assert alpha_status == 400
    assert "must contain digits only for this CCLD-only request" in alpha_html
    assert counts == _empty_reviewer_counts()
    assert_no_secret_html(missing_html)
    assert_no_secret_html(alpha_html)


def test_ccld_record_request_validates_date_format_and_order() -> None:
    with _seeded_connection() as connection:
        invalid_date_status, _content_type, invalid_date_body = route_response(
            CCLD_RECORD_REQUEST_PATH,
            method="POST",
            request_body=_form_bytes({"facility_number": "157806098", "start_date": "08/24/2022"}),
            ccld_record_request_ui_context=_context(connection),
        )
        reversed_status, _content_type, reversed_body = route_response(
            CCLD_RECORD_REQUEST_PATH,
            method="POST",
            request_body=_form_bytes(
                {
                    "facility_number": "157806098",
                    "start_date": "2022-08-27",
                    "end_date": "2022-08-24",
                }
            ),
            ccld_record_request_ui_context=_context(connection),
        )
        counts = _table_counts(connection)

    invalid_date_html = invalid_date_body.decode("utf-8")
    reversed_html = reversed_body.decode("utf-8")

    assert invalid_date_status == 400
    assert "Start date must use YYYY-MM-DD format." in invalid_date_html
    assert reversed_status == 400
    assert "End date must not be before start date." in reversed_html
    assert counts == _empty_reviewer_counts()
    assert_no_secret_html(invalid_date_html)
    assert_no_secret_html(reversed_html)


def test_ccld_record_request_matches_seeded_facility_and_links_to_reviewer_detail() -> None:
    with _seeded_connection() as connection:
        before_source_rows = _source_rows(connection)

        status, content_type, body = route_response(
            CCLD_RECORD_REQUEST_PATH,
            method="POST",
            request_body=_form_bytes(
                {
                    "facility_number": "157806098",
                    "start_date": "2022-08-01",
                    "end_date": "2022-08-31",
                }
            ),
            ccld_record_request_ui_context=_context(connection),
        )

        after_source_rows = _source_rows(connection)
        counts = _table_counts(connection)

    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())
    detail_href = f"{REVIEWER_UI_DETAIL_PATH}?source_record_key={quote(COMPLAINT_KEY)}"

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert before_source_rows == after_source_rows
    assert counts == _empty_reviewer_counts()
    assert "CCLD request accepted" in html
    assert "Found 6 local/test CCLD source-derived row(s)" in normalized_html
    assert "facility/license number 157806098" in html
    assert "Date range: 2022-08-01 to 2022-08-31." in html
    assert "A. MIRIAM JAMISON" in html
    assert "32-CR-20220407124448" in html
    assert "Open reviewer detail" in html
    assert detail_href in html
    assert "Open reviewer records" in html
    assert "did not run live retrieval or import" in html
    assert "run-ccld-live-fetch.ps1 -FacilityNumber 157806098" in html
    assert_no_secret_html(html)


def test_ccld_record_request_shows_no_match_plan_without_mutation() -> None:
    with _seeded_connection() as connection:
        before_source_rows = _source_rows(connection)

        status, content_type, body = route_response(
            CCLD_RECORD_REQUEST_PATH,
            method="POST",
            request_body=_form_bytes(
                {
                    "facility_number": "157806098",
                    "start_date": "2023-01-01",
                    "end_date": "2023-12-31",
                }
            ),
            ccld_record_request_ui_context=_context(connection),
        )

        after_source_rows = _source_rows(connection)
        counts = _table_counts(connection)

    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert before_source_rows == after_source_rows
    assert counts == _empty_reviewer_counts()
    assert "No matching local/test CCLD records found" in html
    assert "Rows for this facility currently available before date filtering: 6" in html
    assert "CCLD pipeline step still required" in html
    assert "does not run live CCLD retrieval or import" in html
    assert "safe CCLD-only import/reload path" in html
    assert_no_secret_html(html)


def test_ccld_record_request_empty_hosted_records_offers_local_validated_load() -> None:
    with _empty_connection() as connection:
        status, content_type, body = route_response(
            CCLD_RECORD_REQUEST_PATH,
            method="POST",
            request_body=_form_bytes(
                {
                    "facility_number": "157806098",
                    "start_date": "2022-08-01",
                    "end_date": "2022-08-31",
                }
            ),
            ccld_record_request_ui_context=_context(connection),
        )
        counts = _table_counts(connection)

    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert counts == _empty_unloaded_counts()
    assert "No matching local/test CCLD records found" in html
    assert "Load local validated CCLD records" in html
    assert "does not run live public web requests" in html
    assert "ccld_import_reload_action" in html
    assert_no_secret_html(html)


def test_ccld_record_request_loads_local_validated_output_then_shows_matches() -> None:
    with _empty_connection() as connection:
        before_source_rows = _source_rows(connection)

        status, content_type, body = route_response(
            CCLD_RECORD_REQUEST_PATH,
            method="POST",
            request_body=_form_bytes(
                {
                    "facility_number": "157806098",
                    "start_date": "2022-08-01",
                    "end_date": "2022-08-31",
                    "ccld_import_reload_action": "load_local_validated_ccld_records",
                }
            ),
            ccld_record_request_ui_context=_context(connection),
        )

        after_source_rows = _source_rows(connection)
        counts = _table_counts(connection)

    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())
    detail_href = f"{REVIEWER_UI_DETAIL_PATH}?source_record_key={quote(COMPLAINT_KEY)}"

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert before_source_rows == []
    assert len(after_source_rows) == 6
    assert counts == _empty_reviewer_counts()
    assert "Local validated CCLD load result" in html
    assert "Load executed: yes." in html
    assert "New source-derived rows staged" in html
    assert "validated_seeded_corpus.json" in html
    assert "CCLD request accepted" in html
    assert "Found 6 local/test CCLD source-derived row(s)" in normalized_html
    assert detail_href in html
    assert "Refresh from local validated CCLD output" in html
    assert "run live public web requests" in html
    assert_no_secret_html(html)


def test_ccld_record_request_local_validated_load_defers_when_dates_do_not_match() -> None:
    with _empty_connection() as connection:
        status, content_type, body = route_response(
            CCLD_RECORD_REQUEST_PATH,
            method="POST",
            request_body=_form_bytes(
                {
                    "facility_number": "157806098",
                    "start_date": "2023-01-01",
                    "end_date": "2023-12-31",
                    "ccld_import_reload_action": "load_local_validated_ccld_records",
                }
            ),
            ccld_record_request_ui_context=_context(connection),
        )
        counts = _table_counts(connection)

    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert counts == _empty_unloaded_counts()
    assert "Local validated CCLD load result" in html
    assert "Load executed: no." in html
    assert "No local validated CCLD records matched" in html
    assert "No matching local/test CCLD records found" in html
    assert_no_secret_html(html)


def _context(connection: Connection) -> CcldRecordRequestUiContext:
    return ccld_record_request_context_for_reviewer_context(
        reviewer_ui_context_for_connection(
            connection,
            actor=_actor(roles=("tester_reviewer",)),
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
        "tester@example.invalid",
        "https://example.com",
    ]:
        assert marker not in lowered


def _form_bytes(payload: dict[str, str]) -> bytes:
    return urlencode(payload).encode("utf-8")


def _seeded_connection() -> Connection:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)
    connection = engine.connect()
    transaction = connection.begin()
    artifact = load_seeded_corpus_artifact(FIXTURE)
    import_seeded_corpus_artifact(connection, artifact)
    transaction.commit()
    return connection


def _empty_connection() -> Connection:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)
    return engine.connect()


def _actor(
    *,
    roles: tuple[str, ...],
    scopes: tuple[HostedAccessScope, ...] = (TEST_SCOPE,),
    account_status: str = "active",
    actor_category: str = "tester",
    provider_subject: str = "fixture-ccld-request-reviewer",
    display_name: str = "Fixture CCLD Request Reviewer",
) -> AuthenticatedActor:
    return AuthenticatedActor(
        provider_subject=provider_subject,
        provider_issuer="fixture-managed-oidc-provider",
        display_name=display_name,
        email="tester@example.invalid",
        actor_category=cast(HostedActorCategory, actor_category),
        account_status=cast(HostedAccountStatus, account_status),
        roles=tuple(cast(HostedTesterRole, role) for role in roles),
        scopes=scopes,
    )


def _source_rows(connection: Connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        select(hosted_source_derived_records).order_by(
            hosted_source_derived_records.c.source_record_key
        )
    ).mappings()
    return [dict(row) for row in rows]


def _table_counts(connection: Connection) -> dict[str, int]:
    import_batches = connection.execute(
        select(func.count()).select_from(hosted_import_batches)
    ).scalar_one()
    source_records = connection.execute(
        select(func.count()).select_from(hosted_source_derived_records)
    ).scalar_one()
    reviewer_created_state = connection.execute(
        select(func.count()).select_from(hosted_reviewer_created_state)
    ).scalar_one()
    audit_events = connection.execute(
        select(func.count()).select_from(hosted_audit_events)
    ).scalar_one()
    reset_reload_planning_metadata = connection.execute(
        select(func.count()).select_from(hosted_reset_reload_planning_metadata)
    ).scalar_one()
    return {
        "import_batches": import_batches,
        "source_records": source_records,
        "reviewer_created_state": reviewer_created_state,
        "audit_events": audit_events,
        "reset_reload_planning_metadata": reset_reload_planning_metadata,
    }


def _empty_reviewer_counts() -> dict[str, int]:
    return {
        "import_batches": 1,
        "source_records": 6,
        "reviewer_created_state": 0,
        "audit_events": 0,
        "reset_reload_planning_metadata": 0,
    }


def _empty_unloaded_counts() -> dict[str, int]:
    return {
        "import_batches": 0,
        "source_records": 0,
        "reviewer_created_state": 0,
        "audit_events": 0,
        "reset_reload_planning_metadata": 0,
    }
