from __future__ import annotations

import html as html_lib
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote, urlencode

import pytest
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
    load_hosted_auth_runtime_config,
)
from ccld_complaints.hosted_app.ccld_facility_lookup import (
    CCLD_FACILITY_LOOKUP_PATH,
    CCLD_FACILITY_REFERENCE_CSV_ENV,
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


def _local_dev_auth_config() -> Any:
    return load_hosted_auth_runtime_config(
        environ={
            "CCLD_HOSTED_TESTER_AUTH_MODE": "local-dev",
            "CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH": "enabled",
        }
    )


def test_ccld_record_request_page_renders_from_default_context() -> None:
    status, content_type, body = route_response(
        "/ccld",
        auth_runtime_config=_local_dev_auth_config(),
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Retrieve complaint records" in html
    assert "Skip to main CCLD request content" in html
    assert '<main id="main-content" tabindex="-1">' in html
    assert "Retrieve complaint records for a facility" in html
    assert "Retrieval intake" in html
    assert "Create the review request context" in html
    assert "Keyboard flow: move from facility selection to date range" in html
    assert "Start review request context" in html
    assert "Facility/license number identifies the CCLD facility" in html
    assert "Date range narrows complaint, visit, report, signed, or retrieval dates" in html
    assert "Show existing queue searches loaded local/test source-derived records" in html
    assert "without proving public-source completeness" in html
    assert "continue to the review queue" in html
    assert "Choose complaint date range" in html or "Which facility should be reviewed?" in html
    assert 'for="facility-search-input"' in html
    assert "facility-suggestion-list" in html
    assert "Which facility should be reviewed?" in html
    assert CCLD_FACILITY_LOOKUP_PATH in html
    assert "Confirm facility" in html
    assert "Search by name, license number, city, ZIP, type, or status." in html
    assert "Keyboard flow: type a search or digit number" in html
    assert "Retrieval not configured" in html
    assert "Find facility" in html
    assert "Review boundary" not in html
    assert "provider" not in html.casefold()
    assert_no_secret_html(html)


def test_ccld_trailing_slash_route_renders_request_start() -> None:
    status, content_type, body = route_response(
        "/ccld/",
        auth_runtime_config=_local_dev_auth_config(),
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Retrieve complaint records" in html
    assert "Start review request context" in html
    assert "Which facility should be reviewed?" in html
    assert_no_secret_html(html)


def test_ccld_help_page_explains_workflow_terms_and_feedback() -> None:
    status, content_type, body = route_response("/ccld/help")
    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Help" in html
    assert "What this tool helps you do" in html
    assert "How to review a facility" in html
    assert "What review flags mean" in html
    assert "How source traceability works" in html
    assert "What to do with source-confidence cues" in html
    assert "Source-confidence cues are local/test review prompts" in normalized_html
    assert "not source verification, source absence, source completeness" in normalized_html
    assert "describe only what the local/test page showed" in normalized_html
    assert "return to the same queue and continue with the suggested next record" in (
        normalized_html
    )
    assert "source URL, raw SHA-256 hash" in html
    assert "local/test traceability value missing" in normalized_html
    assert "not proof that the public CCLD portal lacks a value" in normalized_html
    assert "Before relying on a source-derived value" in html
    assert "source document/report marker" in normalized_html
    assert "How reviewer-created notes/status work" in html
    assert "How correction-readiness works" in html
    assert "Correction-readiness means a tester has noticed" in html
    assert "Check source traceability first" in html
    assert "possible correction concern in a reviewer-created note or feedback" in html
    assert "does not change source-derived records" in html
    assert "does not submit correction decisions" in normalized_html
    assert "A future correction workflow would be reviewer-created state" in normalized_html
    assert "public CCLD portal remains the source of record" in normalized_html
    assert "Retrieval modes" in html
    assert "What the app does not prove" in html
    assert "How to send useful feedback" in html
    assert "How packet preparation fits in" in html
    assert "packet preview/draft are local/test preparation" in normalized_html
    assert "feedback carries safe context" in normalized_html
    assert "Packet readiness means local/test review readiness" in html
    assert "manual review, browser copy, or browser print" in normalized_html
    assert "source-derived values, source traceability" in normalized_html
    assert "possible correction-readiness concerns" in normalized_html
    assert (
        "not legal reports, final exports, certified reports, product-generated exports, "
        "packet lifecycle state, or source-completeness proof"
        in normalized_html
    )
    assert "Source-derived records" in html
    assert "reviewer-created notes/status" in normalized_html
    assert "How reviewer-created status filters work" in html
    assert "active reviewer-created status filter" in normalized_html
    assert "records shown under that filter" in normalized_html
    assert "total records in the same facility/date queue" in normalized_html
    assert "not source-derived facts, assignments, record claims" in normalized_html
    assert "filtered-empty result can mean the filter is hiding records" in normalized_html
    assert "Correction-readiness" in html
    assert (
        "does not make reviewer-created observations into official public-source facts"
        in normalized_html
    )
    assert "no complaints exist" in normalized_html
    assert 'action="/ccld/correction' not in normalized_html
    assert 'name="correction_status"' not in normalized_html
    assert "correction approved" not in normalized_html
    assert "correction applied" not in normalized_html
    assert "corrected source record" not in normalized_html
    assert "Retrieve complaint records" in html
    assert_no_secret_html(html)


def test_ccld_record_request_prefills_selected_facility_from_lookup() -> None:
    status, content_type, body = route_response(
        f"{CCLD_RECORD_REQUEST_PATH}?"
        "facility_number=900000001&request_context_origin=facility_lookup"
        "&lookup_facility_name=Synthetic+Orchard+Child+Care",
        auth_runtime_config=_local_dev_auth_config(),
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Selected request context" in html
    assert "Facility lookup result" in html
    assert "Facility/license number being requested" in html
    assert "Synthetic Orchard Child Care" in html
    assert "Active facility reference source" in html
    assert "value=\"900000001\"" in html
    assert "name=\"request_context_origin\"" in html
    assert "value=\"facility_lookup\"" in html
    assert "name=\"lookup_facility_name\"" in html
    assert "Choose complaint date range" in html
    assert "Use a bounded date range" in html
    assert (
        "Use the date range to narrow complaint, visit, report, signed, or retrieval dates"
        in html
    )
    assert_no_secret_html(html)


def test_ccld_record_request_manual_entry_shows_context_confirmation() -> None:
    status, content_type, body = route_response(
        CCLD_RECORD_REQUEST_PATH,
        auth_runtime_config=_local_dev_auth_config(),
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Which facility should be reviewed?" in html
    assert "type the digit facility/license number directly" in html
    assert "Retrieval not configured" in html
    assert "Search by name, license number, city, ZIP, type, or status." in normalized_html
    assert "name=\"request_context_origin\"" in html
    assert "value=\"manual_entry\"" in html
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
    assert "Choose a supported reviewer-status filter." in html
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
    assert "Complaint records ready for attorney review" in html
    assert "Facility case brief" in html
    assert "Complaint records visible/imported" in html
    assert "Records with review flags" in html
    assert "Reviewer-created notes/statuses" in html
    assert "Possible delay indicators" in html
    assert "Missing first activity date" in html
    assert "Missing local key dates" not in html
    assert "Needs source check" in html
    assert "Findings represented" in html
    assert "Findings are source-derived categories, not legal conclusions" in html
    assert "Suggested first record for review" in html
    assert "Why open this first" in html
    assert "No reviewer-created status recorded yet" in html
    assert "Needs source check: first activity date missing locally" in html
    assert "Source traceability available" in html
    assert "Open priority record" in html
    assert "Open full queue" in html
    assert "Open local/test packet preview" in html
    assert "/reviewer/packet/preview?facility_number=157806098" in html
    assert "Open local/test preparation draft for browser copy or print" in html
    assert "/reviewer/packet/draft?facility_number=157806098" in html
    assert "Matching source-derived rows shown" in html
    assert "facility/license number 157806098" in html
    assert "2022-08-01 to 2022-08-31" in html
    assert "Selected request context" in html
    assert "Request started from" in html
    assert "Manual facility/license entry" in html
    assert "Facility/license number being requested" in html
    assert "Date range being requested" in html
    assert "Active facility reference source" in html
    assert "Change facility/date criteria for this request" in html
    assert "Start over with a different CCLD facility" in html
    assert "CCLD review queue" in html
    assert "Open the suggested complaint first" in normalized_html
    assert "check source traceability and source-confidence cues on detail" in normalized_html
    assert "cautious reviewer-created notes/status or feedback" in normalized_html
    assert "Table view and queue guidance" in html
    assert "First-run queue steps" in html
    assert "Read the queue progress and triage summaries" in html
    assert "check source traceability, source-confidence cues" in normalized_html
    assert "Return to this same request page, resubmit when needed" in normalized_html
    assert "Copy the single manual feedback checklist" in normalized_html
    assert "Facility/date-scoped CCLD complaint records ready for review" in html
    assert "Queue progress summary" in html
    assert "Counts use existing reviewer-created status rows" in normalized_html
    assert "Total matching complaint records" in html
    assert "<dt>Not started</dt>" in html
    assert "<dd>1</dd>" in html
    assert "Queue triage summary" in html
    assert "Queue summaries do not prove record completeness" in normalized_html
    assert "source-confidence cues before relying on a summary value" in normalized_html
    assert "Next safe action: check the detail traceability first" in normalized_html
    assert "use feedback if the source-confidence cue or next step remains confusing" in (
        normalized_html
    )
    assert "record-specific reviewer-detail observations" in normalized_html
    assert "Carry both queue-level observations and reviewer-detail observations" in (
        normalized_html
    )
    assert "does not create a second checklist or persist feedback" in normalized_html
    assert "Continue review guidance" in html
    assert "derived from this facility/date request context" in normalized_html
    assert "not a persisted queue assignment" in normalized_html
    assert "automatic record claim" in html
    assert "official workflow state" in html
    assert "After reviewing detail or saving a note/status" in normalized_html
    assert "Next record guidance" in html
    assert "Records with reviewer-created notes" in html
    assert "Records with reviewer-created status" in html
    assert "Records with source traceability available" in html
    assert "Suggested next record to open" in html
    assert "Open reviewer detail for 32-CR-20220407124448" in html
    assert "Review-priority decision flow" in html
    assert "Use this local/test worklist as a decision screen" in normalized_html
    assert "If a card shows a missing, confusing, or proxy-related value" in normalized_html
    assert "use cautious reviewer-created note/status wording only when helpful" in (
        normalized_html
    )
    assert "Active CCLD request context" in html
    assert "Request origin" in html
    assert "Active local/test reference source" in html
    assert "Loaded local/test source-derived complaint records" in html
    assert "Records with reviewer-created status/note cues" in html
    assert "Records with review flags or possible delay indicators" in html
    assert "Recommended next record action" in html
    assert "Open next priority record: 32-CR-20220407124448" in html
    assert "Why this record is prioritized" in html
    assert "Prioritized worklist records" in html
    assert "Recommended next record: 32-CR-20220407124448" in html
    assert "Review need: flagged for review from source-derived cues" in html
    assert "use cautious note/status wording or feedback if the cue remains confusing" in (
        normalized_html
    )
    assert "Complaint/control/source-record identifier" in html
    assert "Source-derived date/finding/flag summary" in html
    assert "Reviewer-created status/note cue" in html
    assert "Source traceability availability cue" in html
    assert "Open review workspace for 32-CR-20220407124448" in html
    assert "Review packet readiness before copying or printing" in html
    assert "Open local/test preparation draft for browser copy or print" in html
    assert "not a legal report, not a final export, not a certified report" in normalized_html
    assert "do not assign, claim, or mutate records" in normalized_html
    assert "Queue decision actions" in html
    assert "tester feedback for this queue context" in normalized_html
    assert "source-confidence cue, missing local/test value" in normalized_html
    assert "proxy-related value" in normalized_html
    assert "/feedback?feedback_type=Bug+report" in html
    assert "workflow_area=queue" in html
    assert "facility_number=157806098" in html
    assert "start_date=2022-08-01" in html
    assert "end_date=2022-08-31" in html
    assert "reviewer_status_filter=all" in html
    assert "Describe+what+was+confusing+about+this+queue+or+filter" in html
    assert "Find another CCLD facility" in html
    assert "Start a new CCLD request" in html
    assert "Open CCLD workflow help" in html
    assert "Copy tester feedback checklist" in html
    assert "Reviewer-status filter for this queue" in html
    assert "Apply reviewer-status filter" in html
    assert "Active reviewer-created status filter" in html
    assert "Active reviewer-created status filter: All queue records." in html
    assert "Showing 1 of 1 records for this same facility/date request." in html
    assert "Records shown under active filter" in html
    assert "Total records in this same facility/date queue" in html
    assert "Available reviewer-created status filters" in html
    assert "not record assignment" in html
    assert "not record claiming" in normalized_html
    assert "not persisted queue state" in html
    assert "A. MIRIAM JAMISON" in html
    assert "32-CR-20220407124448" in html
    assert detail_href in html
    assert "return_facility_number=157806098" in html
    assert "return_start_date=2022-08-01" in html
    assert "return_end_date=2022-08-31" in html
    assert "Source traceability available" in html
    assert "Missing local/test traceability values: none" in html
    assert "Check source traceability before relying on source-derived values" in html
    assert "Records with source traceability available</dt>" in html
    assert "Loaded record/source-confidence context" in html
    assert "No reviewer-created notes/status yet" in html
    assert "1 loaded source-derived records in bundle" not in html
    assert "6 loaded source-derived records in bundle" in html
    assert "Open detail for source-confidence cues before relying" in html
    assert "Copyable tester feedback checklist" in html
    assert "Copy details for feedback" in html
    assert "Structured CCLD feedback checklist" in html
    assert "id=\"feedback-checklist-section\"" in html
    assert "Select the checklist text, copy it, paste it" in normalized_html
    assert "Use this same manual checklist for queue observations" in normalized_html
    assert "filtered-empty recovery, no-match/load guidance" in normalized_html
    assert "CCLD tester feedback checklist" in html
    assert "- Matching source-derived rows shown: 6" in html
    assert "- Matching complaint records in queue: 1" in html
    assert "- Not started: 1" in html
    assert "- Reviewer-created notes present: no" in html
    assert "- Reviewer-created statuses present: no" in html
    assert "- Facility lookup used or skipped:" in html
    assert "- Facility lookup used or skipped: Manual facility/license entry" in html
    assert "- Active facility reference source:" in html
    assert "- Source traceability cues were easy to find:" in html
    assert "- Source-confidence cues or missing local/test fields to mention:" in html
    assert "- Next safe action was clear for missing, confusing, or proxy-related values:" in html
    assert "- Saved confirmation appeared as expected:" in html
    assert "- Queue showed updated note/status after returning" in html
    assert "- Records that seemed missing:" in html
    assert "- Records that seemed unexpected:" in html
    assert "- Manual-copy only: copy this checklist" in html
    assert "Open reviewer records" in html
    assert "did not submit a controlled retrieval job for this request" in html
    assert "run-ccld-live-fetch.ps1 -FacilityNumber 157806098" in html
    assert "legally sufficient" not in normalized_html.casefold()
    assert "verified abuse" not in normalized_html.casefold()
    assert "confirmed harm" not in normalized_html.casefold()
    assert "complete source record" not in normalized_html.casefold()
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
    assert "Reviewer note saved for this record" in note_html
    assert "Reviewer status saved for this record" in status_html
    assert "Reviewer-created state saved" in note_html
    assert "Reviewer-created state saved" in status_html
    assert "Return to facility queue" in note_html
    assert "Return to facility queue" in status_html
    assert "Open next priority record" in note_html
    assert "Open next priority record" in status_html
    assert "Queue progress and note/status cues are derived from reviewer-created state" in (
        note_html
    )
    assert "Queue progress and note/status cues are derived from reviewer-created state" in (
        status_html
    )
    assert reviewed_status == 200
    assert "Latest reviewer-created status: Reviewed" in reviewed_html
    assert "1 reviewer-created note(s)" in reviewed_html
    assert "Review-priority decision flow" in reviewed_html
    assert "Records with reviewer-created status/note cues" in reviewed_html
    assert "Reviewer-created status/note cue" in reviewed_html
    assert "Open review workspace for 32-CR-20220407124448" in reviewed_html
    assert "Records with reviewer-created notes" in reviewed_html
    assert "Records with reviewer-created status" in reviewed_html
    assert "Suggested next record to open" in reviewed_html
    assert "Continue review guidance" in reviewed_html
    assert "not a persisted queue assignment" in reviewed_normalized
    assert "- Reviewer-created rows read for this queue: 2" in reviewed_html
    assert "- Reviewer-created notes present: yes" in reviewed_html
    assert "- Reviewer-created statuses present: yes" in reviewed_html
    assert "- Reviewed: 1" in reviewed_html
    assert "Active reviewer-created status filter: Reviewed." in reviewed_html
    assert "Showing 1 of 1 records for this same facility/date request." in reviewed_html
    assert "Available reviewer-created status filters" in reviewed_html
    assert "Open reviewer detail for 32-CR-20220407124448" in reviewed_html
    assert blocked_status == 200
    assert "Active reviewer-created status filter: Blocked." in blocked_html
    assert "Showing 0 of 1 records for this same facility/date request." in blocked_html
    assert "No complaint records match the selected reviewer-status filter" in blocked_normalized
    assert "Filtered queue recovery" in blocked_html
    assert "No records match this active reviewer-created status filter" in blocked_html
    assert "same facility/date request context" in blocked_normalized
    assert "does not mean records are missing, deleted, absent" in blocked_normalized
    assert "Active request context" in blocked_html
    assert "facility/license number 157806098; date range 2022-08-01 to 2022-08-31" in (
        blocked_normalized
    )
    assert "Active reviewer-created status filter" in blocked_html
    assert "Records shown under active filter" in blocked_html
    assert "Total records in this same facility/date queue" in blocked_html
    assert "<dd>1</dd>" in blocked_html
    assert "Reviewer-status filters use existing reviewer-created state" in blocked_html
    assert "Records without a saved status are counted as not started" in blocked_normalized
    assert "Show all reviewer statuses for this facility/date request" in blocked_html
    assert "name=\"reviewer_status_filter\" value=\"all\"" in blocked_html
    assert "return to the full CCLD request queue" in blocked_normalized
    assert "manual feedback checklist" in blocked_html
    assert "what you expected to see" in blocked_normalized
    assert "choose All queue records" in blocked_normalized
    assert "filtered-empty result" in blocked_normalized
    assert "tester feedback for this filtered queue" in blocked_normalized
    assert "reviewer_status_filter=blocked" in blocked_html
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
    assert "Candidates may be outside the selected date range" in html
    assert "Rows available before date filtering" in html
    assert "<dd>6</dd>" in html
    normalized_html = " ".join(html.split())
    assert "Confirm the facility/date context" in normalized_html
    assert "How to interpret this no-match result" in html
    assert "currently loaded local/test source-derived rows only" in normalized_html
    assert "did not submit a controlled retrieval job for this request" in normalized_html
    assert "Facility/license number searched" in html
    assert "Date range searched" in html
    assert "Loaded local/test rows for this facility before date filtering" in html
    assert "Local validated load state" in html
    assert "not submitted for this request" in html
    assert "Change the facility/license number or date range" in normalized_html
    assert "use the local validated CCLD load action" in html
    assert "outside-browser live fetch and artifact-builder workflow" in normalized_html
    assert "copy the feedback checklist" in html
    assert "not a public-source absence" in html
    assert "Selected request context" in html
    assert "Change facility/date criteria for this request" in html
    assert "Copyable tester feedback checklist" in html
    assert "Technical retrieval details" in html
    assert "Copy details for feedback" in html
    assert "Advanced local/operator actions" in html
    assert "- Matching source-derived rows shown: 0" in html
    assert "- Matching complaint records in queue: 0" in html
    assert "- Local facility rows before date filtering: 6" in html
    assert "- None shown for this request." in html
    assert "Technical preparation path" in html
    assert "When controlled retrieval is configured" in html
    assert "use the browser retrieval action" in html
    assert "Server-side retrieval, raw preservation" in html
    assert "build-hosted-ccld-artifact.ps1" in html
    assert "The browser remains a trigger only" in html
    assert "SQLite conversion remains outside the browser path" in html
    assert_no_secret_html(html)


def test_ccld_record_request_queue_preserves_lookup_selected_context() -> None:
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
                    "request_context_origin": "facility_lookup",
                    "lookup_facility_name": "A. MIRIAM JAMISON",
                }
            ),
            ccld_record_request_ui_context=_context(connection),
        )

        after_source_rows = _source_rows(connection)
        counts = _table_counts(connection)

    html = body.decode("utf-8")
    checklist = _feedback_checklist(html)

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert before_source_rows == after_source_rows
    assert counts == _empty_reviewer_counts()
    assert "Selected request context" in html
    assert "Facility lookup result" in html
    assert "Selected lookup facility name" in html
    assert "A. MIRIAM JAMISON" in html
    assert "Date range being requested" in html
    assert "2022-08-01 to 2022-08-31" in html
    assert "Open the suggested complaint first" in " ".join(html.split())
    assert "request_context_origin" in html
    assert "lookup_facility_name" in html
    assert "- Facility lookup used or skipped: Facility lookup result" in checklist
    assert "- Selected lookup facility name: A. MIRIAM JAMISON" in checklist
    assert "- Active facility reference source:" in checklist
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
    assert "No loaded complaint records match this request yet" in html
    assert "Load local validated CCLD records" in html
    assert "How to interpret this no-match result" in html
    assert "currently loaded local/test source-derived rows only" in " ".join(html.split())
    assert "Loaded local/test rows for this facility before date filtering" in html
    assert "not submitted for this request" in html
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
    assert "Complaint records ready for attorney review" in html
    assert "Matching source-derived rows shown" in html
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
    assert "- Facility lookup used or skipped: Manual facility/license entry" in first_checklist
    assert "- Selected lookup facility name: unknown" in first_checklist
    assert "- Active facility reference source:" in first_checklist
    assert "- Date range requested: 2022-08-01 to 2022-08-31" in first_checklist
    assert "- Request criteria that felt unclear:" in first_checklist
    assert "- Matching source-derived rows shown: 6" in first_checklist
    assert "- Matching complaint records in queue: 1" in first_checklist
    assert "Queue triage and filters" in first_checklist
    assert "- Local validated records loaded or refreshed: no" in first_checklist
    assert "- Reviewer-created rows read for this queue: 0" in first_checklist
    assert "Queue records to spot-check" in first_checklist
    assert "source traceability cue: Source traceability available" in first_checklist
    assert "Missing local/test traceability values: none" in first_checklist
    assert "Check source traceability before relying on source-derived values" in first_checklist
    assert "reviewer note/status cue: No reviewer-created notes/status yet" in first_checklist
    assert "Reviewer detail and note/status confirmation" in first_checklist
    assert "- Review session path was clear from home/request/help:" in first_checklist
    assert "- Source traceability cues were easy to find:" in first_checklist
    assert "- Source-confidence cues or missing local/test fields to mention:" in (
        first_checklist
    )
    assert "- Next safe action was clear for missing, confusing, or proxy-related values:" in (
        first_checklist
    )
    assert "- Saved confirmation appeared as expected:" in first_checklist
    assert "- Return-to-queue link worked:" in first_checklist
    assert "- Queue showed updated note/status after returning and resubmitting:" in (
        first_checklist
    )
    assert "Missing, unexpected, or confusing results" in first_checklist
    assert "- Records that seemed missing:" in first_checklist
    assert "- Records that seemed unexpected:" in first_checklist
    assert "- Facility lookup wording that was confusing:" in first_checklist
    assert "- Request, queue, or reviewer-detail wording that was confusing:" in (
        first_checklist
    )
    assert "- Keyboard, reading-order, or checklist-copy friction:" in first_checklist
    assert "- Suggested enhancements:" in first_checklist
    assert "- Manual-copy only: copy this checklist" in first_checklist
    assert "- The app does not store, send, email, export, or persist this feedback." in (
        first_checklist
    )
    assert "does not create a saved review session, persisted queue state, or second checklist" in (
        first_checklist
    )
    assert "Rendering this checklist does not change source-derived records" in first_checklist
    assert "Browser pages only trigger controlled server-side retrieval" in first_checklist
    assert "Missing local/test rows are not proof" in first_checklist
    assert "Select the checklist text, copy it, paste it" in " ".join(first_html.split())
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
    assert "reads prepared hosted seeded-corpus JSON only" in " ".join(html.split())
    assert "No local validated CCLD records matched" in html
    assert "submitted, but no matching local validated rows were loaded" in html
    assert "No loaded complaint records match this request yet" in html
    assert "How to interpret this no-match result" in html
    assert "outside-browser live fetch and artifact-builder workflow" in " ".join(html.split())
    assert_no_secret_html(html)


def _context(connection: Connection) -> CcldRecordRequestUiContext:
    return ccld_record_request_context_for_reviewer_context(
        reviewer_ui_context_for_connection(
            connection,
            actor=_actor(roles=("tester_reviewer",)),
        )
    )


def test_ccld_request_page_facility_selector_renders() -> None:
    """Facility selector must render on the request page with accessible structure."""
    status, content_type, body = route_response(
        CCLD_RECORD_REQUEST_PATH,
        auth_runtime_config=_local_dev_auth_config(),
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")

    assert status == 200
    assert 'id="facility-selector-wrap"' in html
    assert 'for="facility-search-input"' in html
    assert 'id="facility-suggestion-list"' in html
    assert_no_secret_html(html)


def test_ccld_request_page_facility_selector_has_concise_placeholder() -> None:
    """Request page facility input placeholder must be short and not clipped."""
    status, content_type, body = route_response(
        CCLD_RECORD_REQUEST_PATH,
        auth_runtime_config=_local_dev_auth_config(),
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")

    assert status == 200
    assert 'placeholder="Facility/license number"' in html
    assert "Search by name, license number, city, ZIP, type, or status." in html
    # Placeholder must not be the full helper sentence
    assert 'placeholder="Search facility name' not in html
    assert_no_secret_html(html)


def test_ccld_request_page_limited_reference_note_appears_when_fallback_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Request page facility selector must show a limited-reference note when fallback is active."""
    monkeypatch.delenv(CCLD_FACILITY_REFERENCE_CSV_ENV, raising=False)

    status, content_type, body = route_response(
        CCLD_RECORD_REQUEST_PATH,
        auth_runtime_config=_local_dev_auth_config(),
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")

    assert status == 200
    assert "Limited reference list" in html
    assert "suggestions may not include every CCLD facility" in html
    assert_no_secret_html(html)


def test_ccld_request_page_no_internal_path_labels_in_primary_ui() -> None:
    """Internal scaffold/path labels must not appear in the primary request page UI."""
    status, content_type, body = route_response(
        CCLD_RECORD_REQUEST_PATH,
        auth_runtime_config=_local_dev_auth_config(),
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")

    assert status == 200
    assert "Tiny committed CCLD facility fixture fallback" not in html
    assert "Full local/test CCLD facility reference CSV" not in html
    assert_no_secret_html(html)


def assert_no_secret_html(markup: str) -> None:
    lowered = markup.casefold()
    for marker in [
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
