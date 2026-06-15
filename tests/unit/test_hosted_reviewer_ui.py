from __future__ import annotations

from pathlib import Path
from typing import Any, cast
from urllib.parse import quote, urlencode

import pytest
from sqlalchemy import create_engine, func, select, update
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
from ccld_complaints.hosted_app.reset_reload_dry_run import (
    hosted_reset_reload_planning_metadata,
)
from ccld_complaints.hosted_app.reviewer_created_state import (
    create_reviewer_note_scaffold,
    create_reviewer_status_scaffold,
    hosted_reviewer_created_state,
)
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
OTHER_SCOPE = HostedAccessScope("seeded_corpus", "different-seeded-corpus")
COMPLAINT_KEY = "complaint:ccld:complaint:32-CR-20220407124448"


def test_reviewer_ui_landing_lists_seeded_source_derived_records() -> None:
    with _seeded_connection() as connection:
        status, content_type, body = route_response(
            "/reviewer",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Local/test reviewer records" in html
    assert "Skip to main reviewer content" in html
    assert '<main id="main-content" tabindex="-1">' in html
    assert "Local/test reviewer UI shell" in html
    assert "CCLD request queue" in html
    assert "CCLD workflow help" in html
    assert "Search seeded review records" in html
    assert "Open CCLD request or queue" in html
    assert "Open CCLD workflow help" in html
    assert "Seeded source-derived review list" in html
    assert "Reviewer queue triage summary" in html
    assert "Total visible records" in html
    assert "Records with reviewer notes" in html
    assert "Records with reviewer status" in html
    assert "Records with source traceability available" in html
    assert "Suggested next record to open" in html
    assert "Reviewer state" in html
    assert "Notes" in html
    assert "Latest status" in html
    assert "Suggested queue cue" in html
    assert "Latest reviewer state at" in html
    assert "No reviewer state yet" in html
    assert "No reviewer notes" in html
    assert "No reviewer status" in html
    assert "No reviewer-created state yet" in html
    assert "Source traceability available" in html
    assert "Open next to begin review" in html
    assert "32-CR-20220407124448" in html
    assert COMPLAINT_KEY in html
    assert "raw SHA-256" in html
    assert "Source-derived records remain separate from reviewer-created notes" in normalized_html
    assert "This shell does not implement production sign-in" in normalized_html
    assert "Open reviewer detail for 32-CR-20220407124448" in html
    assert_no_secret_html(html)


def test_reviewer_ui_landing_shows_reviewer_created_state_indicators() -> None:
    with _seeded_connection() as connection:
        note = create_reviewer_note_scaffold(
            connection,
            _actor(roles=("tester_reviewer",), display_name="Fixture List Note Reviewer"),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            note_text="List indicator note.",
        )
        status_row = create_reviewer_status_scaffold(
            connection,
            _actor(roles=("tester_reviewer",), display_name="Fixture List Status Reviewer"),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            reviewer_status="reviewed",
        )

        status, content_type, body = route_response(
            "/reviewer/records",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Reviewed" in html
    assert "1 reviewer note" in html
    assert "reviewed" in html
    assert "Reviewer queue triage summary" in html
    assert "Open only if reviewed context needs checking" in html
    assert status_row.created_at in html
    assert note.created_at in html or status_row.created_at in html
    assert "No reviewer state yet" not in html
    assert_no_secret_html(html)


def test_reviewer_ui_landing_supports_simple_search() -> None:
    with _seeded_connection() as connection:
        matched_status, _content_type, matched_body = route_response(
            "/reviewer/records?q=32-CR",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )
        empty_status, _content_type, empty_body = route_response(
            "/reviewer/records?q=no-match",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    matched_html = matched_body.decode("utf-8")
    empty_html = empty_body.decode("utf-8")

    assert matched_status == 200
    assert "value=\"32-CR\"" in matched_html
    assert "32-CR-20220407124448" in matched_html
    assert empty_status == 200
    assert "No seeded source-derived review records match the current search." in (
        " ".join(empty_html.split())
    )
    assert "No matching seeded reviewer records" in empty_html
    assert "Clear search" in empty_html
    assert "Return to reviewer home" in empty_html


def test_reviewer_ui_missing_detail_record_has_clear_next_step() -> None:
    with _seeded_connection() as connection:
        missing_key_status, _content_type, missing_key_body = route_response(
            REVIEWER_UI_DETAIL_PATH,
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )
        invalid_key_status, _content_type, invalid_key_body = route_response(
            f"{REVIEWER_UI_DETAIL_PATH}?source_record_key=complaint%3Amissing",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    missing_key_html = missing_key_body.decode("utf-8")
    invalid_key_html = invalid_key_body.decode("utf-8")

    assert missing_key_status == 400
    assert "Select a seeded record" in missing_key_html
    assert "Choose a seeded source-derived record before opening reviewer detail." in (
        missing_key_html
    )
    assert "Return to reviewer records" in missing_key_html
    assert invalid_key_status == 404
    assert "Selected seeded record was not found" in invalid_key_html
    assert "The selected seeded record is not available" in invalid_key_html
    assert "Return to reviewer records" in invalid_key_html
    assert_no_secret_html(missing_key_html)
    assert_no_secret_html(invalid_key_html)


def test_reviewer_ui_detail_shows_source_traceability_and_forms() -> None:
    with _seeded_connection() as connection:
        status, content_type, body = route_response(
            f"{REVIEWER_UI_DETAIL_PATH}?source_record_key={quote(COMPLAINT_KEY)}",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Local/test reviewer detail" in html
    assert "Skip to main reviewer content" in html
    assert '<main id="main-content" tabindex="-1">' in html
    assert "First-run detail steps" in html
    assert "Confirm the selected complaint record" in html
    assert "Review the source traceability fields and source-context cues" in html
    assert "Return to the CCLD request queue" in html
    assert "use the refreshed queue's suggested next record to continue" in normalized_html
    assert "Next-record guidance is local/test navigation help" in html
    assert "not a persisted assignment" in html
    assert "automatic record claim" in normalized_html
    assert "official workflow state" in html
    assert "Detail navigation" in html
    assert "Return to CCLD request or queue" in html
    assert "Find another CCLD facility" in html
    assert "Open CCLD workflow help" in html
    assert "Back to reviewer records" in html
    assert "Review record summary" in html
    assert "Review source traceability" in html
    assert "Review source-derived context" in html
    assert "Prepare tester feedback" in html
    assert "Record summary" in html
    assert "This summary orients the selected local/test CCLD complaint record" in (
        normalized_html
    )
    assert "Complaint and report dates" in html
    assert "Facility/license number" in html
    assert "157806098" in html
    assert "Facility name" in html
    assert "A. MIRIAM JAMISON" in html
    assert "Reviewer status recorded" in html
    assert "Source-derived record" in html
    assert "These are safe scalar fields from the selected source-derived row" in (
        normalized_html
    )
    assert "Safe source-derived values for the selected seeded record" in html
    assert "complaint_control_number" in html
    assert "32-CR-20220407124448" in html
    assert "Source traceability" in html
    assert "Selected complaint source traceability fields" in html
    assert "Use these fields to confirm which local/test source-derived complaint record" in (
        normalized_html
    )
    assert "Missing values are shown as" in html
    assert "not available in this local/test record" in html
    assert "not proof that the public source lacks a record" in normalized_html
    assert "does not make legal, facility-wide, completeness, harm, abuse, neglect" in (
        normalized_html
    )
    assert "Selected source record key" in html
    assert "Stable source identity" in html
    assert "Visible source traceability summary" in html
    assert "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports" in html
    assert "Raw SHA-256" in html
    assert "6088c9627374baac647e2f2a54f6e389cb68c1b92db42da00020aaf508a853bd" in html
    assert "Source artifact identity" in html
    assert "Report index or source page marker" in html
    assert "Retrieved at capture time" in html
    assert "Raw hash validation status" in html
    assert "Use this to report local/test artifact validation state" in html
    assert "Connector name" in html
    assert "Connector name and version" in html
    assert "ccld_facility_reports" in html
    assert "Source document ID" in html
    assert "ccld:document:157806098:3" in html
    assert "Import batch ID" in html
    assert TEST_SCOPE.scope_id in html
    assert "Use these fields to confirm that the selected record remains tied" in (
        normalized_html
    )
    assert "Selected source-derived bundle summary" in html
    assert "Related seeded source-derived context" in html
    assert "Use this section to distinguish the selected complaint" in normalized_html
    assert "Safe related source-derived rows in the selected seeded bundle" in html
    assert "facility" in html
    assert "source_document" in html
    assert "complaint" in html
    assert "allegation" in html
    assert "extraction_audit" in html
    assert "facility_name: A. MIRIAM JAMISON" in html
    assert "external_facility_number: 157806098" in html
    assert "county: Kern" in html
    assert "document_type: complaint_investigation_report" in html
    assert "allegation_category: Staff conduct" in html
    assert "allegation_category: Inadequate supervision" in html
    assert "allegation_text: hidden in this local/test UI" in html
    assert "field_name: facility_number" in html
    assert "extraction_method: ccld_facility_report_html_labels" in html
    assert "Facility clients are being mistreated" not in html
    assert "adequate supervision to the facility clients" not in html
    assert "Reviewer-created state" in html
    assert "UI actions add reviewer-created rows and audit rows" in normalized_html
    assert "Use this section to see whether another local/test reviewer" in normalized_html
    assert "Reviewer-created payload kinds present" in html
    assert "Latest reviewer-created row" in html
    assert "No reviewer-created state has been recorded" in html
    assert "Reviewer actions" in html
    assert "Review the source traceability section first" in html
    assert "Set a status to keep queue progress understandable" in normalized_html
    assert "Add reviewer note" in html
    assert "Reviewer note for this record" in html
    assert "Use safe plain text" in html
    assert "appear below after saving" in normalized_html
    assert "Save reviewer note for this record" in html
    assert f"action=\"{REVIEWER_UI_NOTE_PATH}\"" in html
    assert "Return to the same CCLD queue" in html
    assert "submit the request again to see queue progress" in normalized_html
    assert "return_facility_number" in html
    assert "Set reviewer status" in html
    assert "Reviewer queue status for this record" in html
    assert "Status is reviewer-created local/test state for" in normalized_html
    assert "Save reviewer status for this record" in html
    assert ">Needs follow-up</option>" in html
    assert f"action=\"{REVIEWER_UI_STATUS_PATH}\"" in html
    assert "Reviewer-created state is stored separately" in normalized_html
    assert "Feedback clues for this record" in html
    assert "If source traceability fields are confusing or missing" in html
    assert "copy the tester feedback checklist" in normalized_html
    assert "Return request context" in html
    assert "facility/license number 157806098; date range not provided" in html
    assert "Record-specific feedback handoff" in html
    assert "Carry these observations into the existing manual feedback checklist" in (
        normalized_html
    )
    assert "Source traceability observations" in html
    assert "Source context confusion" in html
    assert "Request-context fit" in html
    assert "whether this complaint seemed unexpected" in normalized_html
    assert "Note/status behavior" in html
    assert "Queue refresh behavior" in html
    assert "confusing labels, wording, keyboard flow" in normalized_html
    assert "/ccld/records/request?facility_number=157806098" in html
    assert "/ccld/facilities" in html
    assert "/ccld/help" in html
    assert_no_secret_html(html)


def test_reviewer_ui_detail_missing_traceability_uses_clear_non_conclusive_wording() -> None:
    with _seeded_connection() as connection:
        connection.execute(update(hosted_source_derived_records).values(raw_path=None))
        before_counts = _table_counts(connection)

        status, content_type, body = route_response(
            f"{REVIEWER_UI_DETAIL_PATH}?source_record_key={quote(COMPLAINT_KEY)}",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

        after_counts = _table_counts(connection)

    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert before_counts == after_counts == {
        "import_batches": 1,
        "source_records": 6,
        "reviewer_created_state": 0,
        "audit_events": 0,
        "reset_reload_planning_metadata": 0,
    }
    assert "Raw artifact path" in html
    assert "not available in this local/test record" in html
    assert "do not treat a missing path as source loss" in html
    assert "not proof that the public source lacks a record" in normalized_html
    assert "does not make legal, facility-wide, completeness" in normalized_html
    assert_no_secret_html(html)


def test_reviewer_ui_detail_render_is_non_mutating() -> None:
    with _seeded_connection() as connection:
        before_source_rows = _source_rows(connection)
        before_counts = _table_counts(connection)

        status, content_type, body = route_response(
            f"{REVIEWER_UI_DETAIL_PATH}?source_record_key={quote(COMPLAINT_KEY)}",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

        after_source_rows = _source_rows(connection)
        after_counts = _table_counts(connection)

    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert before_source_rows == after_source_rows
    assert before_counts == after_counts == {
        "import_batches": 1,
        "source_records": 6,
        "reviewer_created_state": 0,
        "audit_events": 0,
        "reset_reload_planning_metadata": 0,
    }
    assert "Record summary" in html
    assert "Feedback clues for this record" in html
    assert_no_secret_html(html)


def test_reviewer_ui_note_form_uses_existing_workflow_and_shows_read_after_write() -> None:
    with _seeded_connection() as connection:
        before_source_rows = _source_rows(connection)

        status, content_type, body = route_response(
            REVIEWER_UI_NOTE_PATH,
            method="POST",
            request_body=_form_bytes(
                {
                    "source_record_key": COMPLAINT_KEY,
                    "note_text": "Review source traceability before export.",
                    "return_facility_number": "157806098",
                    "return_start_date": "2022-08-01",
                    "return_end_date": "2022-08-31",
                    "return_context_origin": "facility_lookup",
                    "return_lookup_facility_name": "A. MIRIAM JAMISON",
                }
            ),
            reviewer_ui_context=reviewer_ui_context_for_connection(
                connection,
                actor=_actor(
                    roles=("tester_reviewer",),
                    provider_subject="fixture-ui-note-reviewer",
                    display_name="Fixture UI Note Reviewer",
                ),
            ),
        )

        after_source_rows = _source_rows(connection)
        counts = _table_counts(connection)
        [audit_event] = connection.execute(select(hosted_audit_events)).mappings().all()

    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert before_source_rows == after_source_rows
    assert counts == {
        "import_batches": 1,
        "source_records": 6,
        "reviewer_created_state": 1,
        "audit_events": 1,
        "reset_reload_planning_metadata": 0,
    }
    assert "Reviewer update saved" in html
    assert "Reviewer note saved for this record" in html
    assert "The note now appears in reviewer-created state below" in html
    assert "Return to CCLD request queue" in html
    assert "Return and refresh queue progress" in html
    assert "Queue progress and note/status cues are derived from reviewer-created state" in html
    assert "same facility/license number and date range" in normalized_html
    assert "submit the request again" in html
    assert "continuing to the next record" in html
    assert "suggested next record is not a persisted assignment" in html
    assert "automatic record claim" in normalized_html
    assert "official workflow state" in html
    assert "manual feedback checklist" in html
    assert "record-specific observation" in html
    assert "157806098" in html
    assert "2022-08-01 to 2022-08-31" in html
    assert "return_facility_number=157806098" in html
    assert "Review saved notes and statuses below" in html
    assert "Review source traceability before export." in html
    assert "reviewer_note_scaffold" in html
    assert "Reviewer-created payload kinds present" in html
    assert "Latest reviewer-created row" in html
    assert "Related seeded source-derived context" in html
    assert "Fixture UI Note Reviewer (tester)" in html
    assert "Reviewer-created; source-derived record unchanged" in html
    assert audit_event["source_record_key"] == COMPLAINT_KEY
    assert audit_event["context_metadata"]["state_payload_keys"] == [
        "local_test_only",
        "note_format",
        "note_text",
        "payload_kind",
        "source_record_key",
    ]
    assert_no_secret_html(html)


def test_reviewer_ui_invalid_note_submission_has_clear_error_without_mutation() -> None:
    with _seeded_connection() as connection:
        missing_status, _content_type, missing_body = route_response(
            REVIEWER_UI_NOTE_PATH,
            method="POST",
            request_body=_form_bytes({"source_record_key": COMPLAINT_KEY}),
            reviewer_ui_context=reviewer_ui_context_for_connection(
                connection,
                actor=_actor(roles=("tester_reviewer",)),
            ),
        )
        blocked_value_status, _content_type, blocked_value_body = route_response(
            REVIEWER_UI_NOTE_PATH,
            method="POST",
            request_body=_form_bytes(
                {
                    "source_record_key": COMPLAINT_KEY,
                    "note_text": "A token was pasted here.",
                }
            ),
            reviewer_ui_context=reviewer_ui_context_for_connection(
                connection,
                actor=_actor(roles=("tester_reviewer",)),
            ),
        )
        counts = _table_counts(connection)

    missing_html = missing_body.decode("utf-8")
    blocked_value_html = blocked_value_body.decode("utf-8")

    assert missing_status == 400
    assert "Reviewer note was not saved" in missing_html
    assert "Enter safe plain text before saving a reviewer note for this record." in (
        missing_html
    )
    assert "What you can do next" in missing_html
    assert "Return to selected record detail" in missing_html
    assert blocked_value_status == 400
    assert "Reviewer note was not saved" in blocked_value_html
    assert "blocked private data" in blocked_value_html
    assert "token" not in blocked_value_html.casefold()
    assert counts["reviewer_created_state"] == 0
    assert counts["audit_events"] == 0
    assert_no_secret_html(missing_html)
    assert_no_secret_html(blocked_value_html)


def test_reviewer_ui_status_form_uses_existing_workflow_and_shows_read_after_write() -> None:
    with _seeded_connection() as connection:
        before_source_rows = _source_rows(connection)

        status, content_type, body = route_response(
            REVIEWER_UI_STATUS_PATH,
            method="POST",
            request_body=_form_bytes(
                {
                    "source_record_key": COMPLAINT_KEY,
                    "reviewer_status": "needs_follow_up",
                    "return_facility_number": "157806098",
                    "return_start_date": "2022-08-01",
                    "return_end_date": "2022-08-31",
                }
            ),
            reviewer_ui_context=reviewer_ui_context_for_connection(
                connection,
                actor=_actor(
                    roles=("tester_reviewer",),
                    provider_subject="fixture-ui-status-reviewer",
                    display_name="Fixture UI Status Reviewer",
                ),
            ),
        )

        after_source_rows = _source_rows(connection)
        counts = _table_counts(connection)
        [audit_event] = connection.execute(select(hosted_audit_events)).mappings().all()

    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert before_source_rows == after_source_rows
    assert counts == {
        "import_batches": 1,
        "source_records": 6,
        "reviewer_created_state": 1,
        "audit_events": 1,
        "reset_reload_planning_metadata": 0,
    }
    assert "Reviewer update saved" in html
    assert "Reviewer status saved for this record" in html
    assert "The status now appears in reviewer-created state below" in html
    assert "Return to CCLD request queue" in html
    assert "Return and refresh queue progress" in html
    assert "Queue progress and note/status cues are derived from reviewer-created state" in html
    assert "submit the request again" in html
    assert "continuing to the next record" in html
    assert "suggested next record is not a persisted assignment" in html
    assert "automatic record claim" in " ".join(html.split())
    assert "official workflow state" in html
    assert "manual feedback checklist" in html
    assert "record-specific observation" in html
    assert "return_facility_number=157806098" in html
    assert "Review saved notes and statuses below" in html
    assert "reviewer_status_scaffold" in html
    assert "needs_follow_up" in html
    assert "Reviewer statuses present" in html
    assert "Reviewer-created payload kinds present" in html
    assert "Latest reviewer-created row" in html
    assert "Related seeded source-derived context" in html
    assert "Fixture UI Status Reviewer (tester)" in html
    assert audit_event["source_record_key"] == COMPLAINT_KEY
    assert audit_event["context_metadata"]["state_payload_keys"] == [
        "local_test_only",
        "payload_kind",
        "reviewer_status",
        "source_record_key",
    ]
    assert_no_secret_html(html)


def test_reviewer_ui_invalid_status_submission_has_clear_error_without_mutation() -> None:
    with _seeded_connection() as connection:
        missing_status, _content_type, missing_body = route_response(
            REVIEWER_UI_STATUS_PATH,
            method="POST",
            request_body=_form_bytes({"source_record_key": COMPLAINT_KEY}),
            reviewer_ui_context=reviewer_ui_context_for_connection(
                connection,
                actor=_actor(roles=("tester_reviewer",)),
            ),
        )
        invalid_status, _content_type, invalid_body = route_response(
            REVIEWER_UI_STATUS_PATH,
            method="POST",
            request_body=_form_bytes(
                {
                    "source_record_key": COMPLAINT_KEY,
                    "reviewer_status": "source_checked",
                }
            ),
            reviewer_ui_context=reviewer_ui_context_for_connection(
                connection,
                actor=_actor(roles=("tester_reviewer",)),
            ),
        )
        counts = _table_counts(connection)

    missing_html = missing_body.decode("utf-8")
    invalid_html = invalid_body.decode("utf-8")

    assert missing_status == 400
    assert "Reviewer status was not saved" in missing_html
    assert "Choose a reviewer queue status before saving this record." in missing_html
    assert "Return to selected record detail" in missing_html
    assert invalid_status == 400
    assert "Reviewer status was not saved" in invalid_html
    assert "reviewer_status must be one of" in invalid_html
    assert "Status values update queue cues but do not change source-derived records" in (
        " ".join(invalid_html.split())
    )
    assert "Return to selected record detail" in invalid_html
    assert counts["reviewer_created_state"] == 0
    assert counts["audit_events"] == 0
    assert_no_secret_html(missing_html)
    assert_no_secret_html(invalid_html)


def test_reviewer_ui_note_status_writes_are_visible_on_list_after_write() -> None:
    with _seeded_connection() as connection:
        before_source_rows = _source_rows(connection)
        reviewer_context = reviewer_ui_context_for_connection(
            connection,
            actor=_actor(
                roles=("tester_reviewer",),
                provider_subject="fixture-ui-list-after-write-reviewer",
                display_name="Fixture UI List After Write Reviewer",
            ),
        )

        note_status, _content_type, _note_body = route_response(
            REVIEWER_UI_NOTE_PATH,
            method="POST",
            request_body=_form_bytes(
                {
                    "source_record_key": COMPLAINT_KEY,
                    "note_text": "Visible from the list after write.",
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
                    "reviewer_status": "blocked",
                }
            ),
            reviewer_ui_context=reviewer_context,
        )
        list_status, list_content_type, list_body = route_response(
            "/reviewer/records",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )
        after_source_rows = _source_rows(connection)
        counts = _table_counts(connection)

    status_html = status_body.decode("utf-8")
    list_html = list_body.decode("utf-8")

    assert note_status == 200
    assert status_status == 200
    assert list_status == 200
    assert list_content_type == "text/html; charset=utf-8"
    assert before_source_rows == after_source_rows
    assert counts == {
        "import_batches": 1,
        "source_records": 6,
        "reviewer_created_state": 2,
        "audit_events": 2,
        "reset_reload_planning_metadata": 0,
    }
    assert "blocked" in status_html
    assert "Blocked" in list_html
    assert "1 reviewer note" in list_html
    assert "blocked" in list_html
    assert "No reviewer state yet" not in list_html
    assert_no_secret_html(list_html)


@pytest.mark.parametrize(
    ("actor_case", "expected_status", "expected_text"),
    [
        ("unauthenticated", 401, "requires an authenticated actor"),
        ("disabled", 403, "disabled or revoked"),
        ("revoked", 403, "disabled or revoked"),
        ("role_denied", 403, "does not allow"),
        ("out_of_scope", 403, "not assigned to the requested project or corpus scope"),
    ],
)
def test_reviewer_ui_rejects_blocked_list_contexts(
    actor_case: str,
    expected_status: int,
    expected_text: str,
) -> None:
    actor: AuthenticatedActor | None
    if actor_case == "unauthenticated":
        actor = None
    elif actor_case == "disabled":
        actor = _actor(roles=("tester_reviewer",), account_status="disabled")
    elif actor_case == "revoked":
        actor = _actor(roles=("tester_reviewer",), account_status="revoked")
    elif actor_case == "out_of_scope":
        actor = _actor(roles=("tester_reviewer",), scopes=(OTHER_SCOPE,))
    else:
        actor = _actor(roles=())

    with _seeded_connection() as connection:
        status, content_type, body = route_response(
            "/reviewer/records",
            reviewer_ui_context=reviewer_ui_context_for_connection(
                connection,
                actor=actor,
            ),
        )

    html = body.decode("utf-8")

    assert status == expected_status
    assert content_type == "text/html; charset=utf-8"
    assert "Reviewer request blocked" in html
    assert expected_text in html
    assert "What you can do next" in html
    assert "Return to reviewer records" in html
    assert_no_secret_html(html)


def test_reviewer_ui_rejects_source_read_without_reviewer_state_read_on_detail() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            f"{REVIEWER_UI_DETAIL_PATH}?source_record_key={quote(COMPLAINT_KEY)}",
            reviewer_ui_context=reviewer_ui_context_for_connection(
                connection,
                actor=_actor(roles=("developer_operator",), actor_category="operator"),
            ),
        )

    html = body.decode("utf-8")

    assert status == 403
    assert "Reviewer request blocked" in html
    assert "reviewer_state_read" in html
    assert "What you can do next" in html
    assert "Return to reviewer records" in html
    assert_no_secret_html(html)


def test_reviewer_ui_rejects_source_read_without_reviewer_state_read_on_list() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            "/reviewer/records",
            reviewer_ui_context=reviewer_ui_context_for_connection(
                connection,
                actor=_actor(roles=("developer_operator",), actor_category="operator"),
            ),
        )

    html = body.decode("utf-8")

    assert status == 403
    assert "Reviewer request blocked" in html
    assert "reviewer_state_read" in html
    assert "What you can do next" in html
    assert "Return to reviewer records" in html
    assert_no_secret_html(html)


def test_reviewer_ui_rejects_note_write_without_reviewer_state_write() -> None:
    with _seeded_connection() as connection:
        status, _content_type, body = route_response(
            REVIEWER_UI_NOTE_PATH,
            method="POST",
            request_body=_form_bytes(
                {"source_record_key": COMPLAINT_KEY, "note_text": "Needs review."}
            ),
            reviewer_ui_context=reviewer_ui_context_for_connection(
                connection,
                actor=_actor(roles=("read_only_tester",)),
            ),
        )
        counts = _table_counts(connection)

    html = body.decode("utf-8")

    assert status == 403
    assert "Reviewer note was not saved" in html
    assert "reviewer_state_write" in html
    assert "What you can do next" in html
    assert "Return to selected record detail" in html
    assert counts["source_records"] == 6
    assert counts["reviewer_created_state"] == 0
    assert counts["audit_events"] == 0
    assert_no_secret_html(html)


def test_reviewer_ui_default_route_context_is_browser_accessible() -> None:
    status, content_type, body = route_response("/reviewer")
    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Local/test reviewer records" in html
    assert "32-CR-20220407124448" in html
    assert_no_secret_html(html)


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


def _actor(
    *,
    roles: tuple[str, ...],
    scopes: tuple[HostedAccessScope, ...] = (TEST_SCOPE,),
    account_status: str = "active",
    actor_category: str = "tester",
    provider_subject: str = "fixture-ui-reviewer",
    display_name: str = "Fixture UI Reviewer",
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