from __future__ import annotations

import html as html_lib
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
from ccld_complaints.hosted_app.ccld_facility_lookup import CCLD_FACILITY_LOOKUP_PATH
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
    REVIEWER_UI_NOTE_PATH,
    REVIEWER_UI_STATUS_PATH,
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
    assert "Find a CCLD facility by name" in html
    assert CCLD_FACILITY_LOOKUP_PATH in html
    assert "Queue status filter" in html
    assert "Records with no status are counted" in html
    assert "Workflow overview" in html
    assert "Key terms" in html
    assert "Feedback guidance" in html
    assert "structured checklist" in html
    assert "browser-triggered connector execution" in normalized_html
    assert "Read how this CCLD review workflow works" in normalized_html
    assert "provider" not in html.casefold()
    assert_no_secret_html(html)


def test_ccld_help_page_explains_workflow_terms_and_feedback() -> None:
    status, content_type, body = route_response("/ccld/help")
    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "How CCLD review works" in html
    assert "What this local/test app does" in html
    assert "Workflow overview" in html
    assert "Facility/license number" in html
    assert "Date range" in html
    assert "Loaded records" in html
    assert "Source records" in html
    assert "Review queue" in html
    assert "Reviewer notes" in html
    assert "Reviewer status" in html
    assert "Useful tester feedback includes" in normalized_html
    assert "copy the structured checklist" in normalized_html
    assert "Open the CCLD record request form" in html
    assert_no_secret_html(html)


def test_ccld_record_request_prefills_selected_facility_from_lookup() -> None:
    status, content_type, body = route_response(
        f"{CCLD_RECORD_REQUEST_PATH}?facility_number=900000001"
    )
    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Selected facility/license number from lookup" in html
    assert "value=\"900000001\"" in html
    assert "Find a CCLD facility by name" in html
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


def test_ccld_record_request_rejects_unknown_queue_status_filter() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            CCLD_RECORD_REQUEST_PATH,
            method="POST",
            request_body=_form_bytes(
                {
                    "facility_number": "157806098",
                    "reviewer_status_filter": "source_checked",
                }
            ),
            ccld_record_request_ui_context=_context(connection),
        )
        counts = _table_counts(connection)

    html = body.decode("utf-8")

    assert status == 400
    assert "Choose a supported reviewer status queue filter." in html
    assert counts == _empty_reviewer_counts()
    assert_no_secret_html(html)


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
    assert "CCLD review queue" in html
    assert "Facility/date-scoped CCLD complaint records ready for review" in html
    assert "Queue progress summary" in html
    assert "Counts use existing reviewer-created status rows" in normalized_html
    assert "Total matching complaint records" in html
    assert "<dt>Not started</dt>" in html
    assert "<dd>1</dd>" in html
    assert "Queue triage summary" in html
    assert "Records with reviewer notes" in html
    assert "Records with reviewer status" in html
    assert "Records with source traceability available" in html
    assert "Suggested next record to open" in html
    assert "Open reviewer detail for 32-CR-20220407124448" in html
    assert "Find another CCLD facility" in html
    assert "Start a new CCLD request" in html
    assert "Open CCLD workflow help" in html
    assert "Copy tester feedback checklist" in html
    assert "Filter queue by reviewer status" in html
    assert "Apply queue status filter" in html
    assert "Showing 1 of 1 matching complaint" in normalized_html
    assert "A. MIRIAM JAMISON" in html
    assert "32-CR-20220407124448" in html
    assert detail_href in html
    assert "Complete source traceability" in html
    assert "Records with source traceability available</dt>" in html
    assert "No reviewer notes or status yet" in html
    assert "1 loaded source records in bundle" not in html
    assert "6 loaded source records in bundle" in html
    assert "Copyable tester feedback checklist" in html
    assert "Structured CCLD feedback checklist" in html
    assert "id=\"feedback-checklist-section\"" in html
    assert "CCLD tester feedback checklist" in html
    assert "- Matching source-derived rows shown: 6" in html
    assert "- Matching complaint records in queue: 1" in html
    assert "- Not started: 1" in html
    assert "- Reviewer notes present: no" in html
    assert "- Reviewer statuses present: no" in html
    assert "- Records that seemed missing:" in html
    assert "Copy this checklist into the agreed external feedback channel manually." in html
    assert "Open reviewer records" in html
    assert "did not run live retrieval" in html
    assert "run-ccld-live-fetch.ps1 -FacilityNumber 157806098" in html
    assert_no_secret_html(html)


def test_ccld_record_request_queue_filters_by_existing_reviewer_status() -> None:
    with _seeded_connection() as connection:
        reviewer_context = reviewer_ui_context_for_connection(
            connection,
            actor=_actor(roles=("tester_reviewer",), display_name="Fixture Queue Reviewer"),
        )
        note_status, _content_type, note_body = route_response(
            REVIEWER_UI_NOTE_PATH,
            method="POST",
            request_body=_form_bytes(
                {
                    "source_record_key": COMPLAINT_KEY,
                    "note_text": "Queue filter note.",
                }
            ),
            reviewer_ui_context=reviewer_context,
        )
        status_status, _content_type, status_body = route_response(
            REVIEWER_UI_STATUS_PATH,
            method="POST",
            request_body=_form_bytes(
                {
                    "source_record_key": COMPLAINT_KEY,
                    "reviewer_status": "reviewed",
                }
            ),
            reviewer_ui_context=reviewer_context,
        )

        reviewed_status, _content_type, reviewed_body = route_response(
            CCLD_RECORD_REQUEST_PATH,
            method="POST",
            request_body=_form_bytes(
                {
                    "facility_number": "157806098",
                    "start_date": "2022-08-01",
                    "end_date": "2022-08-31",
                    "reviewer_status_filter": "reviewed",
                }
            ),
            ccld_record_request_ui_context=_context(connection),
        )
        blocked_status, _content_type, blocked_body = route_response(
            CCLD_RECORD_REQUEST_PATH,
            method="POST",
            request_body=_form_bytes(
                {
                    "facility_number": "157806098",
                    "start_date": "2022-08-01",
                    "end_date": "2022-08-31",
                    "reviewer_status_filter": "blocked",
                }
            ),
            ccld_record_request_ui_context=_context(connection),
        )
        counts = _table_counts(connection)

    note_html = note_body.decode("utf-8")
    status_html = status_body.decode("utf-8")
    reviewed_html = reviewed_body.decode("utf-8")
    reviewed_normalized = " ".join(reviewed_html.split())
    blocked_html = blocked_body.decode("utf-8")
    blocked_normalized = " ".join(blocked_html.split())

    assert note_status == 200
    assert status_status == 200
    assert "Reviewer note saved through the existing local/test workflow action." in note_html
    assert "Reviewer status saved through the existing local/test workflow action." in status_html
    assert reviewed_status == 200
    assert "Latest reviewer status: Reviewed" in reviewed_html
    assert "1 reviewer note(s)" in reviewed_html
    assert "Records with reviewer notes" in reviewed_html
    assert "Records with reviewer status" in reviewed_html
    assert "Suggested next record to open" in reviewed_html
    assert "- Reviewer-created rows read for this queue: 2" in reviewed_html
    assert "- Reviewer notes present: yes" in reviewed_html
    assert "- Reviewer statuses present: yes" in reviewed_html
    assert "- Reviewed: 1" in reviewed_html
    assert "Showing 1 of 1 matching complaint record(s) for queue filter Reviewed." in (
        reviewed_normalized
    )
    assert "Open reviewer detail for 32-CR-20220407124448" in reviewed_html
    assert blocked_status == 200
    assert "Showing 0 of 1 matching complaint record(s) for queue filter Blocked." in (
        blocked_normalized
    )
    assert "No complaint records match the selected queue status filter" in blocked_html
    assert "Choose All queue records" in blocked_normalized
    assert counts == {
        "import_batches": 1,
        "source_records": 6,
        "reviewer_created_state": 2,
        "audit_events": 2,
        "reset_reload_planning_metadata": 0,
    }
    assert_no_secret_html(reviewed_html)
    assert_no_secret_html(blocked_html)
    assert_no_secret_html(note_html)
    assert_no_secret_html(status_html)


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
    assert "Copyable tester feedback checklist" in html
    assert "- Matching source-derived rows shown: 0" in html
    assert "- Matching complaint records in queue: 0" in html
    assert "- Local facility rows before date filtering: 6" in html
    assert "- None shown for this request." in html
    assert "CCLD pipeline step still required" in html
    assert "does not run live CCLD retrieval or import" in html
    assert "build-hosted-ccld-artifact.ps1" in html
    assert "Browser requests still do not run live CCLD retrieval" in html
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
    assert "Copyable tester feedback checklist" in html
    assert "- Local facility rows before date filtering: 0" in html
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
    assert "- Load action submitted on this request: yes" in html
    assert "- Local validated records loaded or refreshed: yes" in html
    assert "- New source-derived rows staged: 6" in html
    assert "- Existing source-derived rows refreshed: 0" in html
    assert detail_href in html
    assert "Refresh from local validated CCLD output" in html
    assert "run live public web requests" in html
    assert_no_secret_html(html)


def test_ccld_record_request_feedback_checklist_is_deterministic_and_non_persistent() -> None:
    with _seeded_connection() as connection:
        before_source_rows = _source_rows(connection)

        first_status, _content_type, first_body = route_response(
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
        second_status, _content_type, second_body = route_response(
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

    first_html = first_body.decode("utf-8")
    second_html = second_body.decode("utf-8")
    first_checklist = _feedback_checklist(first_html)
    second_checklist = _feedback_checklist(second_html)

    assert first_status == 200
    assert second_status == 200
    assert before_source_rows == after_source_rows
    assert counts == _empty_reviewer_counts()
    assert first_checklist == second_checklist
    assert first_checklist.startswith("CCLD tester feedback checklist")
    assert "- Source scope: CCLD public complaint records only" in first_checklist
    assert "- Facility/license number: 157806098" in first_checklist
    assert "- Date range: 2022-08-01 to 2022-08-31" in first_checklist
    assert "- Matching source-derived rows shown: 6" in first_checklist
    assert "- Matching complaint records in queue: 1" in first_checklist
    assert "- Local validated records loaded or refreshed: no" in first_checklist
    assert "- Reviewer-created rows read for this queue: 0" in first_checklist
    assert "- Records that seemed missing:" in first_checklist
    assert "- Confusing terms or instructions:" in first_checklist
    assert "- Unexpected queue or filter behavior:" in first_checklist
    assert "- Workflow friction:" in first_checklist
    assert "- Suggested enhancements:" in first_checklist
    assert "- The app does not persist this feedback." in first_checklist
    assert "- Browser pages did not run live CCLD retrieval or connector execution." in (
        first_checklist
    )
    assert "CCLD public portal remains the source of record" in first_checklist
    assert "provider" not in first_checklist.casefold()
    assert_no_secret_html(first_html)
    assert_no_secret_html(second_html)


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


def _feedback_checklist(markup: str) -> str:
    start_marker = '<textarea id="feedback-checklist"'
    start = markup.index(start_marker)
    content_start = markup.index(">", start) + 1
    content_end = markup.index("</textarea>", content_start)
    return html_lib.unescape(markup[content_start:content_end]).strip()


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
