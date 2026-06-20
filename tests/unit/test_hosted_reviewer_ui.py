from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote, urlencode

import pytest
from sqlalchemy import create_engine, func, select, update
from sqlalchemy.engine import Connection

from ccld_complaints.hosted_app.app import _content_disposition_header, route_response
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
    CCLD_FACILITY_REFERENCE_CSV_ENV,
    CCLD_FACILITY_REVIEW_HUB_PATH,
    CCLD_FACILITY_REVIEW_PRIORITY_PATH,
)
from ccld_complaints.hosted_app.facility_case_brief import (
    FacilityCaseBriefRecord,
    select_priority_record,
)
from ccld_complaints.hosted_app.facility_review_signals import (
    FACILITY_REVIEW_SIGNALS_CSVS_ENV,
)
from ccld_complaints.hosted_app.reset_reload_dry_run import (
    hosted_reset_reload_planning_metadata,
)
from ccld_complaints.hosted_app.reviewer_created_state import (
    REVIEWER_STATUS_VALUES,
    create_reviewer_note_scaffold,
    create_reviewer_status_scaffold,
    hosted_reviewer_created_state,
)
from ccld_complaints.hosted_app.reviewer_ui import (
    LOCAL_REVIEWER_UI_SCOPE,
    REVIEWER_UI_DETAIL_PATH,
    REVIEWER_UI_MATRIX_EXPORT_PATH,
    REVIEWER_UI_NOTE_PATH,
    REVIEWER_UI_PACKET_DRAFT_PATH,
    REVIEWER_UI_PACKET_PREVIEW_PATH,
    REVIEWER_UI_STATUS_PATH,
    REVIEWER_UI_SUBSTANTIATED_EXPORT_PATH,
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
    assert "Complaint records ready for review" in html
    assert "Facility case brief" in html
    assert "Complaint records visible" in html
    assert "Records with review flags" in html
    assert "Reviewer-created notes/statuses" in html
    assert "Findings represented" in html
    assert "Suggested first record for review" in html
    assert "Why open this first" in html
    assert "Open priority record" in html
    assert "Open full queue" in html
    assert "Open local/test packet preview" in html
    assert REVIEWER_UI_PACKET_PREVIEW_PATH in html
    assert "Open local/test preparation draft for browser copy or print" in html
    assert REVIEWER_UI_PACKET_DRAFT_PATH in html
    assert "Skip to main reviewer content" in html
    assert '<main id="main-content" tabindex="-1">' in html
    assert "Technical runtime details" in html
    assert "Local/test reviewer UI shell" not in html
    assert "fixture actor context" not in normalized_html
    assert "seeded corpus scope" not in normalized_html
    assert "review-chip" in html
    assert "Source traceability available" in html
    assert "Worklist" in html
    assert "Filter or search queue" in html
    assert "Keyboard flow: search filters this queue" in html
    assert "Open record link includes" in html
    assert "Show table view" in html
    assert "Source-derived records stay separate" in normalized_html
    assert "Worklist" in html
    assert "Queue status summary" not in html
    assert "Source traceability available" in html
    assert "Open record" in html
    assert "No reviewer-created status recorded yet" in html
    assert "Reviewer-created notes/statuses" in html
    assert "Source traceability available" in html
    assert "Reviewer status" in html
    assert "Reviewer-created notes" in html
    assert "Reviewer-created status: No reviewer-created status" in html
    assert "No reviewer note" in html
    assert "Complaint received date" in html
    assert "Visit date" in html
    assert "Report date" in html
    assert "No reviewer-created status" in html
    assert "No reviewer-created notes" in html
    assert "No reviewer-created status" in html
    assert "Source traceability available" in html
    assert "Open record 32-CR-20220407124448" in html
    assert "32-CR-20220407124448" in html
    assert COMPLAINT_KEY in html
    assert "raw SHA-256" in html
    assert (
        "Source-derived records stay separate from reviewer-created notes/status"
        in normalized_html
    )
    assert "This runtime does not add production sign-in" in normalized_html
    assert "Open record 32-CR-20220407124448" in html
    assert_no_secret_html(html)


def test_reviewer_packet_preview_renders_context_and_is_non_mutating() -> None:
    with _seeded_connection() as connection:
        create_reviewer_note_scaffold(
            connection,
            _actor(roles=("tester_reviewer",), display_name="Fixture Packet Note Reviewer"),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            note_text="Packet preview note.",
        )
        create_reviewer_status_scaffold(
            connection,
            _actor(roles=("tester_reviewer",), display_name="Fixture Packet Status Reviewer"),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            reviewer_status="in_review",
        )
        before_source_rows = _source_rows(connection)
        before_counts = _table_counts(connection)

        status, content_type, body = route_response(
            f"{REVIEWER_UI_PACKET_PREVIEW_PATH}?"
            "facility_number=157806098&start_date=2022-08-01&end_date=2022-08-31"
            "&request_context_origin=manual_entry",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

        after_source_rows = _source_rows(connection)
        after_counts = _table_counts(connection)

    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert before_source_rows == after_source_rows
    assert before_counts == after_counts == {
        "import_batches": 1,
        "source_records": 6,
        "reviewer_created_state": 2,
        "audit_events": 2,
        "reset_reload_planning_metadata": 0,
    }
    assert "Review packet preview" in html
    assert "Local/test packet preparation preview" in html
    assert "Open local/test preparation draft for browser copy or print" in html
    assert f"{REVIEWER_UI_PACKET_DRAFT_PATH}?facility_number=157806098" in html
    assert "Return to same facility/date queue" in html
    assert "/ccld/records/request?facility_number=157806098" in html
    assert "Report copy/print preparation concern" in html
    assert "workflow_area=packet-preview" in html
    assert "Describe+copy%2Fprint+preparation%2C+packet+readiness" in html
    assert "Packet readiness means local/test review readiness only" in html
    assert "ready for manual review, browser copy, or browser print" in normalized_html
    assert "active facility/date context, included record count" in normalized_html
    assert "Before copying or printing" in html
    assert "Use this checklist before using browser copy or print" in normalized_html
    assert "Confirm the active facility/date context" in html
    assert "Review records flagged for source check" in html
    assert "Review records missing reviewer-created status/note cues" in html
    assert "Confirm source traceability for important source-derived values" in html
    assert "capture the possible correction concern in a reviewer-created note or feedback" in html
    assert (
        "Use feedback if records, wording, readiness cues, or copy/print preparation "
        "content seems wrong"
        in html
    )
    assert "Facility / license" in html
    assert "157806098" in html
    assert "Date range" in html
    assert "2022-08-01 to 2022-08-31" in html
    assert "Records included" in html
    assert "Records with review flags or possible delay indicators" in html
    assert "Review-readiness checkpoint" in html
    assert "Review-readiness summary" in html
    assert "before browser copy or print" in normalized_html
    assert "Review before relying on this packet" in normalized_html
    assert "confusing, incomplete, risky, or not-ready records" in normalized_html
    assert "Records ready for preparation review" in html
    assert "Records needing source check" in html
    assert "Records needing reviewer-created status/note attention" in html
    assert "Packet preview includes source-derived values and reviewer-created cues" in html
    assert (
        "does not change source-derived records or submit correction decisions"
        in normalized_html
    )
    assert "Possible correction concerns should stay in reviewer-created notes or feedback" in html
    assert (
        "what still needs source check or reviewer-created status/note attention"
        in normalized_html
    )
    assert "Traceability readiness" in html
    assert "Records with source URL available" in html
    assert "Records with raw SHA-256 available" in html
    assert "Records with connector/retrieval metadata available" in html
    assert "Reviewer-created state summary" in html
    assert "Records with reviewer-created status" in html
    assert "Records with reviewer-created notes" in html
    assert "Records without reviewer-created state" in html
    assert "In review" in html
    assert "Included complaint records" in html
    assert "32-CR-20220407124448" in html
    assert "Finding" in html
    assert "Key dates" in html
    assert "Reviewer-created status" in html
    assert "Reviewer note" in html
    assert "Reviewer note added" in html
    assert "Source traceability available" in html
    assert "Review-readiness cue" in html
    assert "Needs source check before copy/print" in html
    assert "Reviewer-created status/note cue present" in html
    assert "Why included" in html
    assert "Part of the current loaded facility/date review queue." in html
    assert "Reviewer status added." in html
    assert "Reviewer note added." in html
    assert "Needs source check." in html
    assert "Finding value shown:" in html
    assert "Review flags" in html
    assert "Open record 32-CR-20220407124448" in html
    assert "Review packet notes" in html
    assert "This preview is a local/test preparation aid." in html
    assert "use the feedback link with this packet context" in html
    assert "Source-derived fields remain separate from reviewer-created notes/status." in html
    assert "Possible correction concerns are reviewer-created observations" in html
    assert "Review flags are screening aids, not legal conclusions." in html
    assert "The CCLD public portal remains the source of record." in html
    assert (
        "not a legal report, not a final export, not a certified report, not a production packet"
        in normalized_html
    )
    assert "not a legal report, not a final export" in normalized_html
    assert "not a certified report" in normalized_html
    assert "not a source-completeness proof" in normalized_html
    assert "No export file is generated by this preview" in html
    assert (
        "does not mutate source-derived records, reviewer-created state, audit rows"
        in normalized_html
    )
    assert "legal priority" not in normalized_html.casefold()
    assert_no_correction_workflow_html(html)
    assert_no_secret_html(html)


def test_reviewer_packet_draft_renders_print_copy_content_without_mutation() -> None:
    with _seeded_connection() as connection:
        create_reviewer_note_scaffold(
            connection,
            _actor(roles=("tester_reviewer",), display_name="Fixture Draft Note Reviewer"),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            note_text="Draft route note.",
        )
        create_reviewer_status_scaffold(
            connection,
            _actor(roles=("tester_reviewer",), display_name="Fixture Draft Status Reviewer"),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            reviewer_status="needs_follow_up",
        )
        before_source_rows = _source_rows(connection)
        before_counts = _table_counts(connection)

        status, content_type, body = route_response(
            f"{REVIEWER_UI_PACKET_DRAFT_PATH}?"
            "facility_number=157806098&start_date=2022-08-01&end_date=2022-08-31"
            "&request_context_origin=manual_entry",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

        after_source_rows = _source_rows(connection)
        after_counts = _table_counts(connection)

    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert before_source_rows == after_source_rows
    assert before_counts == after_counts == {
        "import_batches": 1,
        "source_records": 6,
        "reviewer_created_state": 2,
        "audit_events": 2,
        "reset_reload_planning_metadata": 0,
    }
    assert "Attorney Review Packet Draft" in html
    assert "Local/test preparation draft for browser copy or print" in html
    assert "Use browser copy or print only after review" in html
    assert "Copy/print preparation guidance" in html
    assert "manual browser copy or print" in normalized_html
    assert "Packet readiness means local/test review readiness only" in html
    assert "ready for manual review, browser copy, or browser print" in normalized_html
    assert "active facility/date context, included record count" in normalized_html
    assert "Review before copying or printing" in html
    assert "Source traceability available means visible source URL" in html
    assert "raw SHA-256 hash" in html
    assert "source document/report marker cues" in html
    assert "missing local/test traceability values" in normalized_html
    assert "Correction-readiness before copying or printing" in html
    assert "capture the possible correction concern in a reviewer-created note or feedback" in html
    assert "does not change source-derived records, alter source-derived values" in html
    assert "If copy/print preparation content seems wrong" in html
    assert "Facility / license" in html
    assert "157806098" in html
    assert "Date range" in html
    assert "2022-08-01 to 2022-08-31" in html
    assert "Prepared from" in html
    assert "Generated" in html
    assert "Records included" in html
    assert "Important limitation" in html
    assert "Summary of included records" in html
    assert "Records ready for preparation review" in html
    assert "Records needing source check" in html
    assert "Records needing reviewer-created status/note attention" in html
    assert "Review-readiness before copying or printing" in html
    assert "Review before copying or printing" in html
    assert "Review before relying on this packet" in normalized_html
    assert "return to the queue, open reviewer detail, or use feedback" in normalized_html
    assert "preparation draft" in html
    assert "Possible correction concerns should remain reviewer-created observations" in html
    assert "future correction workflow is not implemented here" in html
    assert "draft does not submit correction decisions" in html
    assert "Findings represented" in html
    assert "Source traceability readiness" in html
    assert "Reviewer-created state included in this draft" in html
    assert "They may point to possible correction concerns" in html
    assert "this draft does not alter source-derived values" in html
    assert "Included complaint records" in html
    assert "32-CR-20220407124448" in html
    assert "Complaint control number" in html
    assert "Finding" in html
    assert "Key dates" in html
    assert "Review flags" in html
    assert "Reviewer-created status" in html
    assert "Reviewer-created note presence" in html
    assert "Why included" in html
    assert "Source traceability summary" in html
    assert "Review-readiness cue" in html
    assert "Missing local/test traceability values" in html
    assert "Check source traceability before relying on source-derived values" in html
    assert "Needs source check before copy/print" in html
    assert "Reviewer-created status/note cue present" in html
    assert "Open record 32-CR-20220407124448" in html
    assert "What this draft does not prove" in html
    assert "It is not a source-completeness proof." in html
    assert "It does not prove no other complaints exist." in html
    assert "source conclusions beyond source-derived finding labels" in html
    assert "It does not submit correction decisions or replace source-derived records" in html
    assert "Copyable packet summary" in html
    assert "Attorney Review Packet Draft" in html
    assert "Facility/license: 157806098" in html
    assert "Reviewer-created state summary" in html
    assert "Records ready for preparation review" in html
    assert (
        "Packet readiness means local/test review readiness for manual browser copy or print"
        in html
    )
    assert "Review-readiness before copy/print" in html
    assert "Source traceability readiness" in html
    assert "Back to local/test packet preview" in html
    assert "Back to review queue" in html
    assert "Report copy/print preparation concern" in html
    assert "workflow_area=packet-draft" in html
    assert "Describe+browser+copy+or+print+preparation+or+packet+readiness+confusion" in html
    assert "@media print" in html
    assert "packet-draft" in html
    assert "site-header" in html and "display: none" in html
    assert "No export file is generated by this draft" in html
    assert "not a legal report, not a final export" in normalized_html
    assert "not a certified report" in normalized_html
    assert "not a source-completeness proof" in normalized_html
    assert (
        "does not mutate source-derived records, reviewer-created state, audit rows"
        in normalized_html
    )
    assert "legal priority" not in normalized_html.casefold()
    assert_no_correction_workflow_html(html)
    assert_no_secret_html(html)


def test_reviewer_packet_draft_without_context_shows_context_needed_state() -> None:
    with _seeded_connection() as connection:
        before_counts = _table_counts(connection)

        status, content_type, body = route_response(
            REVIEWER_UI_PACKET_DRAFT_PATH,
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

        after_counts = _table_counts(connection)

    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert before_counts == after_counts == {
        "import_batches": 1,
        "source_records": 6,
        "reviewer_created_state": 0,
        "audit_events": 0,
        "reset_reload_planning_metadata": 0,
    }
    assert "Attorney Review Packet Draft" in html
    assert "No facility/date packet context was supplied." in html
    assert "not a complete local/test preparation draft without a facility/date context" in html
    assert "not a certified report" in html
    assert "Open Retrieve" in html
    assert "Open Review queue" in html
    assert "Date range: not provided" not in html
    assert_no_secret_html(html)


def test_reviewer_packet_preview_without_context_shows_context_needed() -> None:
    with _seeded_connection() as connection:
        before_counts = _table_counts(connection)

        status, content_type, body = route_response(
            REVIEWER_UI_PACKET_PREVIEW_PATH,
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

        after_counts = _table_counts(connection)

    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert before_counts == after_counts == {
        "import_batches": 1,
        "source_records": 6,
        "reviewer_created_state": 0,
        "audit_events": 0,
        "reset_reload_planning_metadata": 0,
    }
    assert "Review packet preview" in html
    assert "No facility/date packet context was supplied." in html
    assert "Start from Retrieve or the Review queue" in html
    assert "build a packet for a specific facility/date range." in html
    assert "not a certified report" in html
    assert "Date range: not provided" not in html
    assert_no_secret_html(html)


def test_reviewer_ui_landing_shows_reviewer_created_state_indicators() -> None:
    with _seeded_connection() as connection:
        create_reviewer_note_scaffold(
            connection,
            _actor(roles=("tester_reviewer",), display_name="Fixture List Note Reviewer"),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            note_text="List indicator note.",
        )
        create_reviewer_status_scaffold(
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
    assert "1 reviewer-created note" in html
    assert "Reviewer-created status: reviewed" in html
    assert "Reviewer note added" in html
    assert "reviewed" in html
    assert "Facility case brief" in html
    assert "Reviewer-created notes/statuses" in html
    assert "Queue status summary" not in html
    assert "Reviewed" in html
    assert "Reviewer-created notes" in html
    assert "No reviewer-created note/status yet" not in html
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


def test_reviewer_priority_prefers_records_without_reviewer_created_state_then_flags() -> None:
    reviewed_stronger_flag = _case_brief_record_for_priority(
        "reviewed-record",
        reviewer_status="reviewed",
        reviewer_note_count=1,
        delay_thresholds=(120,),
        order_index=0,
    )
    unreviewed_weaker_flag = _case_brief_record_for_priority(
        "unreviewed-record",
        reviewer_status=None,
        reviewer_note_count=0,
        delay_thresholds=(30,),
        order_index=1,
    )
    unreviewed_stronger_flag = _case_brief_record_for_priority(
        "unreviewed-stronger-record",
        reviewer_status=None,
        reviewer_note_count=0,
        delay_thresholds=(90,),
        order_index=2,
    )

    selected = select_priority_record(
        (reviewed_stronger_flag, unreviewed_weaker_flag, unreviewed_stronger_flag)
    )

    assert selected.source_record_key == "unreviewed-stronger-record"


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
    assert "32-CR-20220407124448" in html
    assert "Complaint overview" in html
    assert "Complaint review workspace decision flow" in html
    assert "Queue-to-detail continuity" in html
    assert "Active CCLD request context" in html
    assert "Selected record identity" in html
    assert "Why this record is prioritized from the worklist" in html
    assert "What to check first" in html
    assert "After this detail" in html
    assert "Return to same facility/date queue" in html
    assert "Return links preserve the same facility/date request context" in html
    assert "status filters are chosen on the queue view" in normalized_html
    assert "do not assign, claim, or persist" in normalized_html
    assert "Open next recommended record from this context" in html
    assert "Report confusion about this reviewer detail" in html
    assert "workflow_area=reviewer-detail" in html
    assert "source_record_key=complaint%3Accld%3Acomplaint%3A32-CR-20220407124448" in html
    assert "Describe+what+was+confusing+about+this+reviewer+detail+step" in html
    assert (
        "Review source traceability before relying on missing, confusing, or proxy-related values"
        in html
    )
    assert "GET rendering does not write reviewer-created state" in normalized_html
    assert "does not mutate source-derived records" in normalized_html
    assert "not a legal report, not a final export, not a certified report" in normalized_html
    assert "Why this record is flagged" in html
    assert "Record review action" in html
    assert "Source traceability summary" in html
    assert html.index("Complaint overview") < html.index("Complaint review workspace decision flow")
    assert html.index("Complaint review workspace decision flow") < html.index(
        "Why this record is flagged"
    )
    assert html.index("Why this record is flagged") < html.index("Source traceability summary")
    assert html.index("Source traceability summary") < html.index("Record summary")
    assert html.index("Reviewer-created state") < html.index("Record review action")
    assert "screening aids, not legal conclusions" in normalized_html
    assert "Needs source check: first activity date missing locally" in html
    assert "Source traceability available" in html
    assert "Key dates and finding" in html
    assert "Skip to main reviewer content" in html
    assert '<main id="main-content" tabindex="-1">' in html
    assert "First-run detail steps" in html
    assert "reviewer detail step of the same CCLD review session" in normalized_html
    assert "save reviewer notes/status only as tester-created observations" in (
        normalized_html
    )
    assert "Confirm the selected complaint record" in html
    assert "Review the source traceability fields and source-context cues" in html
    assert "Return to the CCLD request queue" in html
    assert "use the refreshed queue's suggested next record to continue" in normalized_html
    assert "Next-record guidance is local/test navigation help" in html
    assert "not a persisted assignment" in html
    assert "automatic record claim" in normalized_html
    assert "official workflow state" in html
    assert "Detail navigation" in html
    assert "Return to same facility/date queue" in html
    assert "Open next recommended record from this context" in html
    assert "Download local/test complaint review matrix CSV" in html
    assert f"{REVIEWER_UI_MATRIX_EXPORT_PATH}?facility_number=157806098" in html
    assert "Find another CCLD facility" in html
    assert "Open CCLD workflow help" in html
    assert "Back to reviewer records" in html
    assert "Review record summary" in html
    assert "Review source-confidence cues" in html
    assert "Review field-note guidance" in html
    assert "Review source traceability" in html
    assert "Review source-derived context" in html
    assert "Prepare tester feedback" in html
    assert "Report reviewer-detail feedback with safe context" in html
    assert "Record summary" in html
    assert "This summary orients the selected CCLD complaint record" not in normalized_html
    assert "Complaint review workspace" in html
    assert "Legal-review flags and source checks" in html
    assert "detail-top-grid" in html
    assert "Source-confidence cues" in html
    assert "Field-note and technical context" in html
    assert "Complaint and report dates" in html
    assert "Facility/license number" in html
    assert "157806098" in html
    assert "Facility name" in html
    assert "A. MIRIAM JAMISON" in html
    assert "Reviewer-created status recorded" in html
    assert "Source-derived record" in html
    assert "These are safe scalar fields from the selected source-derived row" in (
        normalized_html
    )
    assert "Safe source-derived values for the selected seeded record" in html
    assert "complaint_control_number" in html
    assert "32-CR-20220407124448" in html
    assert "Source-confidence cues" in html
    assert "Source-confidence cues for visible complaint fields" in html
    assert "visible source-derived complaint fields already loaded" in normalized_html
    assert "not a source-confidence score" in normalized_html
    assert "automated source verification" in html
    assert "public-source absence finding" in html
    assert "record-completeness claim" in html
    assert "Missing local/test values should be described" in normalized_html
    assert "not as source absence, record incompleteness, or data loss" in normalized_html
    assert "Next safe action: check source traceability" in normalized_html
    assert "use cautious reviewer-created note/status wording only when it helps" in (
        normalized_html
    )
    assert "use feedback when the cue or wording remains confusing" in normalized_html
    assert "then return to the same queue for the suggested next record" in normalized_html
    assert "Complaint field" in html
    assert "Source-confidence cue" in html
    assert "Present in this local/test source-derived record" in html
    assert "First investigation activity date" in html
    assert "local/test missing-field flag is true" in normalized_html
    assert "Report date proxy flag" in html
    assert "Current local/test field does not mark report date as the delay-review proxy" in (
        normalized_html
    )
    assert "Use fallback/proxy wording only when this cue says" in normalized_html
    assert "Field-note guidance" in html
    assert "Cautious wording for reviewer-created notes/status" in html
    assert "Reviewer notes/status are reviewer-created observations" in normalized_html
    assert "they do not edit source-derived fields" in normalized_html
    assert (
        "For now, use a reviewer-created note to describe the possible correction concern"
        in html
    )
    assert "The local/test workflow does not submit correction decisions" in normalized_html
    assert "For missing, confusing, or proxy-related source-derived values" in normalized_html
    assert "avoid source absence or verification claims" in normalized_html
    assert "continue review from the same queue context" in normalized_html
    assert "Field is present" in html
    assert "local/test record shows complaint received date" in html
    assert (
        "Do not say the value is legally verified or a public-source conclusion"
        in normalized_html
    )
    assert "Field is not available locally" in html
    assert "Do not say the source does not contain this" in normalized_html
    assert "the record is incomplete" in html
    assert "or data was lost" in html
    assert "Report-date proxy flag is shown" in html
    assert "local/test cue marks report date as a proxy" in normalized_html
    assert "Do not use the proxy flag alone" in normalized_html
    assert "use feedback if proxy wording or next action remains confusing" in (
        normalized_html
    )
    assert "Field remains confusing after source traceability" in html
    assert "field remained unclear after checking source traceability" in normalized_html
    assert "Value looks like a UI or data issue" in html
    assert "Use the manual feedback checklist" in html
    assert "instead of treating the note as a source-derived edit" in normalized_html
    assert "Possible correction concern" in html
    assert "what should receive correction review later" in html
    assert "Source traceability" in html
    assert "Selected complaint source traceability fields" in html
    assert "Record-level source traceability status" in html
    assert "Traceability values available" in html
    assert "Traceability values available means" in html
    assert "visible local/test identifiers or source-document cues" in normalized_html
    assert "What available means" in html
    assert "not source verification or a source-completeness claim" in normalized_html
    assert "Missing local/test traceability values" in html
    assert "Missing local/test traceability values means" in html
    assert "this local/test display does not have that cue" in normalized_html
    assert "What missing locally means" in html
    assert "not public-source absence" in normalized_html
    assert "Check source traceability before relying on source-derived values" in html
    assert "Check first:" in html
    assert "available and missing traceability cues" in normalized_html
    assert "Next safe actions:" in html
    assert "add cautious reviewer-created note/status wording only when it helps" in (
        normalized_html
    )
    assert "use feedback when traceability is confusing" in normalized_html
    assert "Next safe action" in html
    assert "Correction-readiness cue" in html
    assert "If a source-derived value looks wrong or incomplete" in html
    assert "check source traceability first" in normalized_html
    assert "document the possible correction concern in a reviewer-created note" in normalized_html
    assert (
        "does not change source-derived records or submit correction decisions"
        in normalized_html
    )
    assert "source URL, raw SHA-256 hash, raw artifact reference" in normalized_html
    assert "which traceability cues are visible and which are locally missing" in (
        normalized_html
    )
    assert "so reviewers can decide what to check" in normalized_html
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
    assert "Record review action" in html
    assert "Current reviewer-created status" in html
    assert "No reviewer-created status" in html
    assert "Reviewer-created note" in html
    assert "No reviewer note" in html
    assert "Recommended next action" in html
    assert "Add a review status or note." in html
    assert "Source-derived fields remain unchanged" in html
    assert "Use this panel after reading the complaint overview and review flags" in (
        normalized_html
    )
    assert "Cautious note/status guidance" in html
    assert "Keyboard flow: Tab to the reviewer-created note field or status selector" in html
    assert "use the confirmation links to return to the same queue" in normalized_html
    assert "Use note text to record what you checked" in html
    assert "review flag, possible delay indicator" in normalized_html
    assert "When a source-derived value may need correction review" in html
    assert "Status values can help the queue reflect review progress" in normalized_html
    assert "status does not correct, verify, or replace source-derived data" in normalized_html
    assert "correction decisions are not implemented in this local/test workflow" in normalized_html
    assert "Do not write that abuse, neglect, harm" in html
    assert "Add a review status or note." in html
    assert "Status is reviewer-created local/test state for queue progress" in (
        normalized_html
    )
    assert "Reviewer-created note" in html
    assert "Reviewer-created note for this record" in html
    assert "Use safe plain text" in html
    assert "appear below after saving" in normalized_html
    assert "document a possible correction concern after source" in normalized_html
    assert "Keyboard flow after saving" in html
    assert (
        "do not change the source-derived record or submit a correction decision"
        in normalized_html
    )
    assert "Save reviewer-created note for this record" in html
    assert f"action=\"{REVIEWER_UI_NOTE_PATH}\"" in html
    assert "Return to the same CCLD queue" in html
    assert "submit the request again to see queue progress" in normalized_html
    assert "return_facility_number" in html
    assert "Reviewer-created status" in html
    assert "Reviewer-created status for this record" in html
    assert "Status is reviewer-created local/test state for" in normalized_html
    assert "It does not correct or verify source-derived data" in html
    assert "use the confirmation links to return to the same queue" in normalized_html
    assert "Save reviewer-created status for this record" in html
    assert ">Needs follow-up</option>" in html
    assert f"action=\"{REVIEWER_UI_STATUS_PATH}\"" in html
    assert_no_correction_workflow_html(html)
    assert "Reviewer-created state is stored separately" in normalized_html
    assert "Feedback clues for this record" in html
    assert "If source traceability fields are confusing or missing" in html
    assert "local/test traceability value missing" in normalized_html
    assert "source document/report marker" in normalized_html
    assert "appears wrong or incomplete after checking traceability" in html
    assert (
        "Use feedback instead when the correction-readiness guidance is confusing"
        in normalized_html
    )
    assert "copy the tester feedback checklist" in normalized_html
    assert "Return request context" in html
    assert "facility/license number 157806098; date range not provided" in html
    assert "Record-specific feedback handoff" in html
    assert "Carry these observations into the existing manual feedback checklist" in (
        normalized_html
    )
    assert "Feedback remains manual-copy only" in html
    assert "use the existing manual feedback checklist" in normalized_html
    assert "does not create a second checklist or save feedback" in normalized_html
    assert "Manual feedback checklist bridge" in html
    assert "record-specific observations from this detail" in normalized_html
    assert "Do not create a separate checklist from this page" in normalized_html
    assert "Use that same checklist for queue-level observations and detail-level" in (
        normalized_html
    )
    assert "request context, queue filters, source traceability" in normalized_html
    assert "return-to-queue refresh, and suggested-next-record confusion stay together" in (
        normalized_html
    )
    assert "Source traceability observations" in html
    assert "Source-confidence next-step confusion" in html
    assert "whether to add a cautious reviewer-created note/status or use feedback" in (
        normalized_html
    )
    assert "Source traceability: note fields that were easy to confirm" in html
    assert "Source-confidence cues: note present values" in html
    assert "values not available in the local/test record" in normalized_html
    assert "proxy-flag context that affected review" in html
    assert "whether the next safe action was clear" in normalized_html
    assert "Field-note uncertainty" in html
    assert "Possible correction concern: note which source-derived value looked wrong" in html
    assert "future correction workflow path was unclear" in html
    assert "Note/status confirmation" in html
    assert "Return-to-queue flow" in html
    assert "Source context confusion" in html
    assert "Request-context fit" in html
    assert "whether this complaint seemed unexpected" in normalized_html
    assert "Note/status behavior" in html
    assert "Queue refresh behavior" in html
    assert "confusing labels, wording, keyboard flow" in normalized_html
    assert "/ccld/records/request?facility_number=157806098" in html
    assert "Open feedback with this record context" in html
    assert "/ccld/facilities" in html
    assert "/ccld/help" in html
    assert_no_secret_html(html)


def test_reviewer_ui_matrix_export_returns_excel_ready_csv_without_mutation() -> None:
    with _seeded_connection() as connection:
        create_reviewer_note_scaffold(
            connection,
            _actor(roles=("tester_reviewer",), display_name="Fixture Matrix Note Reviewer"),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            note_text="Matrix export note marker.",
        )
        create_reviewer_status_scaffold(
            connection,
            _actor(roles=("tester_reviewer",), display_name="Fixture Matrix Status Reviewer"),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            reviewer_status="needs_follow_up",
        )
        before_source_rows = _source_rows(connection)
        before_counts = _table_counts(connection)

        status, content_type, body = route_response(
            f"{REVIEWER_UI_MATRIX_EXPORT_PATH}?"
            "facility_number=157806098&start_date=2022-08-01&end_date=2022-08-31"
            "&request_context_origin=manual_entry",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

        after_source_rows = _source_rows(connection)
        after_counts = _table_counts(connection)

    csv_text = body.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(csv_text)))

    assert status == 200
    assert content_type == "text/csv; charset=utf-8"
    assert before_source_rows == after_source_rows
    assert before_counts == after_counts == {
        "import_batches": 1,
        "source_records": 6,
        "reviewer_created_state": 2,
        "audit_events": 2,
        "reset_reload_planning_metadata": 0,
    }
    assert rows
    [row] = rows
    assert row["matrix_status"] == "loaded local/test complaint record"
    assert "local/test complaint review matrix" in row["export_boundary"]
    assert "CSV export" in row["export_boundary"]
    assert "Excel-ready" in row["export_boundary"]
    assert "not a certified report" in row["export_boundary"]
    assert "not source verification" in row["export_boundary"]
    assert "not a complaint-coverage determination" in row["export_boundary"]
    assert "not a source-completeness proof" in row["export_boundary"]
    assert "not a legal finding" in row["export_boundary"]
    assert row["facility_number"] == "157806098"
    assert row["facility_name"] == "A. MIRIAM JAMISON CHILDREN'S CENTER"
    assert row["request_start_date"] == "2022-08-01"
    assert row["request_end_date"] == "2022-08-31"
    assert row["source_record_key"] == COMPLAINT_KEY
    assert row["complaint_number"] == "32-CR-20220407124448"
    assert row["complaint_date"] == "2022-04-07"
    assert row["visit_date"] == "2022-08-24"
    assert row["finding_or_resolution"] == "Unsubstantiated"
    assert "Staff conduct" in row["allegation_categories"]
    assert "Inadequate supervision" in row["allegation_categories"]
    assert "ccld_facility_reports" in row["source_label"]
    assert row["source_url"].startswith("https://www.ccld.dss.ca.gov/")
    assert "Source traceability available" in row["source_traceability_status"]
    assert row["loaded_local_test_record_indicator"] == "yes"
    assert row["reviewer_created_status"] == "Needs follow-up"
    assert row["reviewer_created_note_present"] == "yes"
    assert row["reviewer_created_last_updated"]
    assert "Matrix export note marker" not in csv_text
    assert "raw_path" not in csv_text
    assert "C:\\" not in csv_text
    assert "provider_subject" not in csv_text
    assert "token" not in csv_text.casefold()
    assert "verified complaint" not in csv_text.casefold()
    assert "source complete" not in csv_text.casefold()
    assert "export approved" not in csv_text.casefold()


def test_reviewer_ui_substantiated_export_returns_excel_ready_csv_without_mutation() -> None:
    with _seeded_connection() as connection:
        create_reviewer_note_scaffold(
            connection,
            _actor(roles=("tester_reviewer",), display_name="Fixture Subst Note Reviewer"),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            note_text="Substantiated export note.",
        )
        create_reviewer_status_scaffold(
            connection,
            _actor(roles=("tester_reviewer",), display_name="Fixture Subst Status Reviewer"),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            reviewer_status="reviewed",
        )

        # Update seeded complaint finding to Substantiated for this test
        row = connection.execute(
            select(hosted_source_derived_records).where(
                hosted_source_derived_records.c.source_record_key == COMPLAINT_KEY
            )
        ).mappings().one()
        original_values = dict(row["original_values"])
        original_values["finding"] = "Substantiated"
        connection.execute(
            update(hosted_source_derived_records)
            .where(hosted_source_derived_records.c.source_record_key == COMPLAINT_KEY)
            .values(original_values=original_values)
        )

        before_source_rows = _source_rows(connection)
        before_counts = _table_counts(connection)

        status, content_type, body = route_response(
            f"{REVIEWER_UI_SUBSTANTIATED_EXPORT_PATH}?"
            "facility_number=157806098&start_date=2022-04-01&end_date=2022-04-30"
            "&request_context_origin=manual_entry",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

        after_source_rows = _source_rows(connection)
        after_counts = _table_counts(connection)

    csv_text = body.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(csv_text)))

    assert status == 200
    assert content_type == "text/csv; charset=utf-8"
    assert before_source_rows == after_source_rows
    assert before_counts == after_counts == {
        "import_batches": 1,
        "source_records": 6,
        "reviewer_created_state": 2,
        "audit_events": 2,
        "reset_reload_planning_metadata": 0,
    }
    assert rows
    [row] = rows  # type: ignore[assignment]
    assert row["Facility Name"] == "A. MIRIAM JAMISON CHILDREN'S CENTER"
    assert row["Facility/License Number"] == "157806098"
    assert row["Complaint Received Date"] == "2022-04-07"
    assert row["Visit Date"] == "2022-08-24"
    assert row["Finding/Status"] == "Substantiated"
    assert row["Complaint Control Number"] == "32-CR-20220407124448"
    assert row["Source Report URL"].startswith("https://www.ccld.dss.ca.gov/")
    assert "Source traceability available" in row["Source Traceability Status"]
    assert row["Reviewer-created status"] == "Reviewed"
    assert row["Reviewer-created note present"] == "yes"
    assert "Substantiated export note" not in csv_text
    assert "raw_path" not in csv_text
    assert "C:\\" not in csv_text
    assert "provider_subject" not in csv_text
    assert "token" not in csv_text.casefold()


@pytest.mark.parametrize(
    ("status_value", "finding_value", "facility_value", "expect_row"),
    (
        ("all", "Unsubstantiated", "157806098", True),
        ("substantiated", "Substantiated", "157806098", True),
        ("unsubstantiated", "Unsubstantiated", "157806098", True),
        ("all", "Unsubstantiated", "999999999", False),
    ),
)
def test_reviewer_ui_complaint_export_status_query_filters_without_mutation(
    status_value: str,
    finding_value: str,
    facility_value: str,
    expect_row: bool,
) -> None:
    with _seeded_connection() as connection:
        create_reviewer_note_scaffold(
            connection,
            _actor(roles=("tester_reviewer",), display_name="Fixture Status Note Reviewer"),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            note_text="Status query export note.",
        )
        create_reviewer_status_scaffold(
            connection,
            _actor(roles=("tester_reviewer",), display_name="Fixture Status Reviewer"),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            reviewer_status="reviewed",
        )

        row = connection.execute(
            select(hosted_source_derived_records).where(
                hosted_source_derived_records.c.source_record_key == COMPLAINT_KEY
            )
        ).mappings().one()
        original_values = dict(row["original_values"])
        original_values["finding"] = finding_value
        connection.execute(
            update(hosted_source_derived_records)
            .where(hosted_source_derived_records.c.source_record_key == COMPLAINT_KEY)
            .values(original_values=original_values)
        )

        before_source_rows = _source_rows(connection)
        before_counts = _table_counts(connection)

        status, content_type, body = route_response(
            f"{REVIEWER_UI_SUBSTANTIATED_EXPORT_PATH}?"
            "request_context_origin=manual_entry"
            f"&status={quote(status_value)}"
            f"&facility={quote(facility_value)}",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

        after_source_rows = _source_rows(connection)
        after_counts = _table_counts(connection)

    csv_text = body.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(csv_text)))

    assert status == 200
    assert content_type == "text/csv; charset=utf-8"
    assert before_source_rows == after_source_rows
    assert before_counts == after_counts == {
        "import_batches": 1,
        "source_records": 6,
        "reviewer_created_state": 2,
        "audit_events": 2,
        "reset_reload_planning_metadata": 0,
    }
    assert rows
    [record] = rows
    if expect_row:
        assert record["Facility Name"] == "A. MIRIAM JAMISON CHILDREN'S CENTER"
        assert record["Facility/License Number"] == "157806098"
        assert record["Complaint Received Date"] == "2022-04-07"
        assert record["Visit Date"] == "2022-08-24"
        assert record["Finding/Status"] == finding_value
        assert record["Complaint Control Number"] == "32-CR-20220407124448"
        assert record["Source Report URL"].startswith("https://www.ccld.dss.ca.gov/")
        assert "Source traceability available" in record["Source Traceability Status"]
        assert record["Reviewer-created status"] == "Reviewed"
        assert record["Reviewer-created note present"] == "yes"
    else:
        assert record["Facility Name"] == ""
        assert record["Facility/License Number"] == ""
        assert record["Finding/Status"] == ""
        assert record["Complaint Control Number"] == ""
    assert "Status query export note" not in csv_text
    assert "raw_path" not in csv_text
    assert "C:\\" not in csv_text
    assert "provider_subject" not in csv_text
    assert "token" not in csv_text.casefold()


@pytest.mark.parametrize(
    (
        "status_value",
        "finding_value",
        "facility_value",
        "start_date_value",
        "end_date_value",
        "expect_row",
    ),
    (
        ("all", "Unsubstantiated", None, "2022-04-01", "2022-04-30", True),
        ("all", "Unsubstantiated", "157806098", "2022-04-01", "2022-04-30", True),
        ("substantiated", "Substantiated", "157806098", "2022-04-01", "2022-04-30", True),
        ("all", "Unsubstantiated", "157806098", "2022-04-01", "", True),
        ("all", "Unsubstantiated", "157806098", "invalid-date", "2022-04-30", True),
    ),
)
def test_reviewer_ui_complaint_export_date_query_filters_without_mutation(
    status_value: str,
    finding_value: str,
    facility_value: str | None,
    start_date_value: str,
    end_date_value: str,
    expect_row: bool,
) -> None:
    with _seeded_connection() as connection:
        create_reviewer_note_scaffold(
            connection,
            _actor(roles=("tester_reviewer",), display_name="Fixture Date Filter Note Reviewer"),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            note_text="Date query export note.",
        )
        create_reviewer_status_scaffold(
            connection,
            _actor(roles=("tester_reviewer",), display_name="Fixture Date Filter Reviewer"),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            reviewer_status="reviewed",
        )

        row = connection.execute(
            select(hosted_source_derived_records).where(
                hosted_source_derived_records.c.source_record_key == COMPLAINT_KEY
            )
        ).mappings().one()
        original_values = dict(row["original_values"])
        original_values["finding"] = finding_value
        connection.execute(
            update(hosted_source_derived_records)
            .where(hosted_source_derived_records.c.source_record_key == COMPLAINT_KEY)
            .values(original_values=original_values)
        )

        before_source_rows = _source_rows(connection)
        before_counts = _table_counts(connection)

        query = (
            f"{REVIEWER_UI_SUBSTANTIATED_EXPORT_PATH}?"
            "request_context_origin=manual_entry"
            f"&status={quote(status_value)}"
            f"&start_date={quote(start_date_value)}"
            f"&end_date={quote(end_date_value)}"
        )
        if facility_value is not None:
            query = f"{query}&facility={quote(facility_value)}"

        status, content_type, body = route_response(
            query,
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

        after_source_rows = _source_rows(connection)
        after_counts = _table_counts(connection)

    csv_text = body.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(csv_text)))

    assert status == 200
    assert content_type == "text/csv; charset=utf-8"
    assert before_source_rows == after_source_rows
    assert before_counts == after_counts == {
        "import_batches": 1,
        "source_records": 6,
        "reviewer_created_state": 2,
        "audit_events": 2,
        "reset_reload_planning_metadata": 0,
    }
    assert rows
    [record] = rows
    if expect_row:
        assert record["Facility Name"] == "A. MIRIAM JAMISON CHILDREN'S CENTER"
        assert record["Facility/License Number"] == "157806098"
        assert record["Complaint Received Date"] == "2022-04-07"
        assert record["Finding/Status"] == finding_value
        assert record["Complaint Control Number"] == "32-CR-20220407124448"
        assert record["Reviewer-created status"] == "Reviewed"
        assert record["Reviewer-created note present"] == "yes"
    else:
        assert record["Facility Name"] == ""
        assert record["Facility/License Number"] == ""
        assert record["Finding/Status"] == ""
        assert record["Complaint Control Number"] == ""
    assert "Date query export note" not in csv_text
    assert "raw_path" not in csv_text
    assert "C:\\" not in csv_text
    assert "provider_subject" not in csv_text
    assert "token" not in csv_text.casefold()


@pytest.mark.parametrize(
    ("finding_value", "allegation_category", "expect_cue"),
    (
        ("Unsubstantiated", "staff misconduct concern", "Possible serious allegation topic"),
        ("Unsubstantiated", "licensing paperwork", ""),
    ),
)
def test_reviewer_ui_complaint_export_serious_review_cue_without_mutation(
    finding_value: str,
    allegation_category: str,
    expect_cue: str,
) -> None:
    with _seeded_connection() as connection:
        create_reviewer_note_scaffold(
            connection,
            _actor(roles=("tester_reviewer",), display_name="Fixture Serious Cue Note Reviewer"),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            note_text="Serious cue export note.",
        )
        create_reviewer_status_scaffold(
            connection,
            _actor(roles=("tester_reviewer",), display_name="Fixture Serious Cue Reviewer"),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            reviewer_status="reviewed",
        )

        complaint_row = connection.execute(
            select(hosted_source_derived_records).where(
                hosted_source_derived_records.c.source_record_key == COMPLAINT_KEY
            )
        ).mappings().one()
        complaint_values = dict(complaint_row["original_values"])
        complaint_values["finding"] = finding_value
        connection.execute(
            update(hosted_source_derived_records)
            .where(hosted_source_derived_records.c.source_record_key == COMPLAINT_KEY)
            .values(original_values=complaint_values)
        )

        allegation_key = "allegation:ccld:allegation:32-CR-20220407124448:1"
        allegation_row = connection.execute(
            select(hosted_source_derived_records).where(
                hosted_source_derived_records.c.source_record_key == allegation_key
            )
        ).mappings().one()
        allegation_values = dict(allegation_row["original_values"])
        allegation_values["allegation_category"] = allegation_category
        connection.execute(
            update(hosted_source_derived_records)
            .where(hosted_source_derived_records.c.source_record_key == allegation_key)
            .values(original_values=allegation_values)
        )

        before_source_rows = _source_rows(connection)
        before_counts = _table_counts(connection)

        status, content_type, body = route_response(
            f"{REVIEWER_UI_SUBSTANTIATED_EXPORT_PATH}?"
            "request_context_origin=manual_entry"
            "&status=all"
            "&facility=157806098"
            "&start_date=2022-04-01"
            "&end_date=2022-04-30",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

        after_source_rows = _source_rows(connection)
        after_counts = _table_counts(connection)

    csv_text = body.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(csv_text)))

    assert status == 200
    assert content_type == "text/csv; charset=utf-8"
    assert before_source_rows == after_source_rows
    assert before_counts == after_counts == {
        "import_batches": 1,
        "source_records": 6,
        "reviewer_created_state": 2,
        "audit_events": 2,
        "reset_reload_planning_metadata": 0,
    }
    assert rows
    [record] = rows
    assert "Serious Review Cue" in record
    assert record["Facility/License Number"] == "157806098"
    assert record["Complaint Received Date"] == "2022-04-07"
    assert record["Finding/Status"] == finding_value
    assert record["Serious Review Cue"] == expect_cue
    assert record["Reviewer-created status"] == "Reviewed"
    assert record["Reviewer-created note present"] == "yes"
    assert "Serious cue export note" not in csv_text
    assert "raw_path" not in csv_text
    assert "C:\\" not in csv_text
    assert "provider_subject" not in csv_text
    assert "token" not in csv_text.casefold()


def test_reviewer_ui_complaint_export_default_filename_is_attachment() -> None:
    with _seeded_connection() as connection:
        path = (
            f"{REVIEWER_UI_SUBSTANTIATED_EXPORT_PATH}?"
            "request_context_origin=manual_entry"
        )
        status, content_type, _body = route_response(
            path,
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    assert status == 200
    assert content_type == "text/csv; charset=utf-8"
    assert _content_disposition_header(path, status, content_type) == (
        'attachment; filename="complaints-substantiated.csv"'
    )


@pytest.mark.parametrize(
    ("query", "expected_filename"),
    (
        ("status=all", "complaints-all.csv"),
        ("status=unsubstantiated", "complaints-unsubstantiated.csv"),
        ("status=all&facility=157806098", "complaints-all-facility-157806098.csv"),
        (
            "status=substantiated&facility=157806098&start_date=2026-01-01&end_date=2026-01-31",
            "complaints-substantiated-facility-157806098-2026-01-01-to-2026-01-31.csv",
        ),
        (
            "status=all&facility=1578/06098&start_date=invalid&end_date=2026-01-31",
            "complaints-all-to-2026-01-31.csv",
        ),
    ),
)
def test_reviewer_ui_complaint_export_filename_segments_are_deterministic(
    query: str,
    expected_filename: str,
) -> None:
    with _seeded_connection() as connection:
        path = f"{REVIEWER_UI_SUBSTANTIATED_EXPORT_PATH}?{query}"
        status, content_type, _body = route_response(
            path,
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    assert status == 200
    assert content_type == "text/csv; charset=utf-8"
    assert _content_disposition_header(path, status, content_type) == (
        f'attachment; filename="{expected_filename}"'
    )


def test_reviewer_ui_complaint_export_csv_body_header_unchanged_for_filtered_export() -> None:
    with _seeded_connection() as connection:
        status, content_type, body = route_response(
            f"{REVIEWER_UI_SUBSTANTIATED_EXPORT_PATH}?"
            "status=all&facility=157806098&start_date=2022-04-01&end_date=2022-04-30"
            "&request_context_origin=manual_entry",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    csv_text = body.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = list(reader)

    assert status == 200
    assert content_type == "text/csv; charset=utf-8"
    assert reader.fieldnames == [
        "Facility Name",
        "Facility/License Number",
        "Complaint Received Date",
        "Report Date",
        "Visit Date",
        "Date Signed",
        "Finding/Status",
        "Complaint Control Number",
        "Source Report URL",
        "Source Traceability Status",
        "Serious Review Cue",
        "Reviewer-created status",
        "Reviewer-created note present",
    ]
    assert rows
    [record] = rows
    assert record["Facility Name"] == "A. MIRIAM JAMISON CHILDREN'S CENTER"
    assert record["Facility/License Number"] == "157806098"
    assert record["Complaint Received Date"] == "2022-04-07"
    assert record["Complaint Control Number"] == "32-CR-20220407124448"


def test_reviewer_ui_matrix_export_empty_context_is_safe() -> None:
    with _seeded_connection() as connection:
        before_source_rows = _source_rows(connection)
        before_counts = _table_counts(connection)

        status, content_type, body = route_response(
            f"{REVIEWER_UI_MATRIX_EXPORT_PATH}?"
            "facility_number=157806098&start_date=2026-01-01&end_date=2026-01-31"
            "&request_context_origin=manual_entry",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

        after_source_rows = _source_rows(connection)
        after_counts = _table_counts(connection)

    csv_text = body.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(csv_text)))

    assert status == 200
    assert content_type == "text/csv; charset=utf-8"
    assert before_source_rows == after_source_rows
    assert before_counts == after_counts == {
        "import_batches": 1,
        "source_records": 6,
        "reviewer_created_state": 0,
        "audit_events": 0,
        "reset_reload_planning_metadata": 0,
    }
    assert len(rows) == 1
    row = rows[0]
    assert row["matrix_status"] == (
        "No loaded local/test complaint records matched this facility/date context."
    )
    assert row["facility_number"] == "157806098"
    assert row["request_start_date"] == "2026-01-01"
    assert row["request_end_date"] == "2026-01-31"
    assert row["loaded_local_test_record_indicator"] == "no"
    assert "not a complaint-coverage determination" in row["export_boundary"]
    assert "no complaints found" not in csv_text.casefold()


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
    assert "Raw artifact preservation" in html
    assert "not available in this local/test record" in html
    assert "Local/test traceability value missing: raw artifact reference" in html
    assert "Missing local/test traceability values means" in html
    assert "local/test detail view does not have that cue" in normalized_html
    assert "Source-confidence cues" in html
    assert "Field-note guidance" in html
    assert "First investigation activity date" in html
    assert "local/test missing-field flag is true" in normalized_html
    assert "raw paths are not shown in the browser" in html
    assert "not proof that the public source lacks a record" in normalized_html
    assert "not proof that the source lacks a record/event" in normalized_html
    assert "does not make legal, facility-wide, completeness" in normalized_html
    assert_no_secret_html(html)


def test_reviewer_ui_detail_preserves_direct_queue_request_context() -> None:
    with _seeded_connection() as connection:
        before_counts = _table_counts(connection)

        status, content_type, body = route_response(
            f"{REVIEWER_UI_DETAIL_PATH}?source_record_key={quote(COMPLAINT_KEY)}"
            "&facility_number=157806098&start_date=2026-01-01&end_date=2026-01-31"
            "&request_context_origin=manual_entry",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

        after_counts = _table_counts(connection)

    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert before_counts == after_counts
    assert "Complaint review workspace decision flow" in html
    assert "Facility/license number" in html
    assert "157806098" in html
    assert "Date range" in html
    assert "2026-01-01 to 2026-01-31" in html
    assert "Manual facility/license entry" in html
    assert "return_facility_number" in html
    assert "return_start_date" in html
    assert "return_end_date" in html
    assert "Review packet readiness before copying or printing" in html
    assert "Open local/test preparation draft for browser copy or print" in html
    assert "not a legal report, not a final export, not a certified report" in (
        normalized_html
    )
    assert "legally sufficient" not in normalized_html.casefold()
    assert "verified abuse" not in normalized_html.casefold()
    assert "complete source record" not in normalized_html.casefold()
    assert_no_secret_html(html)


def test_reviewer_ui_detail_links_signal_only_facility_context_without_mutation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    facility_csv = tmp_path / "facility-reference.csv"
    signals_csv = tmp_path / "24HourResidentialCareforChildren06072026.csv"
    _write_chhs_facility_directory_csv(facility_csv, facility_numbers=("434417302",))
    _write_program_summary_signals_csv(
        signals_csv,
        facility_number="157806098",
        facility_name="A. MIRIAM JAMISON CHILDREN'S CENTER",
    )
    monkeypatch.setenv(CCLD_FACILITY_REFERENCE_CSV_ENV, str(facility_csv))
    monkeypatch.setenv(FACILITY_REVIEW_SIGNALS_CSVS_ENV, str(signals_csv))

    with _seeded_connection() as connection:
        before_source_rows = _source_rows(connection)
        before_counts = _table_counts(connection)
        status, content_type, body = route_response(
            f"{REVIEWER_UI_DETAIL_PATH}?source_record_key={quote(COMPLAINT_KEY)}"
            "&facility_number=157806098&start_date=2026-01-01&end_date=2026-01-31"
            "&request_context_origin=manual_entry",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )
        after_source_rows = _source_rows(connection)
        after_counts = _table_counts(connection)

    html = body.decode("utf-8")
    normalized_html = " ".join(html.split()).casefold()

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
    assert "Facility context cues" in html
    assert "signal-only facility hub" in html
    assert "uploaded public summary signals are available" in html
    assert f"{CCLD_FACILITY_REVIEW_HUB_PATH}?facility_number=157806098" in html
    assert "Open signal-only facility hub" in html
    assert "Return to signal-only facility hub" in html
    assert CCLD_FACILITY_REVIEW_PRIORITY_PATH in html
    assert "Return to facility review priority list" in html
    assert "Start complaint request if needed" in html
    assert "/ccld/records/request?facility_number=157806098" in html
    assert "Return to same facility/date queue" in html
    assert f"{REVIEWER_UI_PACKET_PREVIEW_PATH}?facility_number=157806098" in html
    assert f"{REVIEWER_UI_PACKET_DRAFT_PATH}?facility_number=157806098" in html
    assert "complaint records are requested/reviewed separately" in normalized_html
    assert "not source verification" in normalized_html
    assert "not a complaint-coverage determination" in normalized_html
    assert "not a source-completeness proof" in normalized_html
    assert "not a legal finding" in normalized_html
    assert "review cue" in normalized_html
    assert "source-traceability cue" in normalized_html
    assert "source-derived value" in normalized_html
    assert "reviewer-created note/status" in normalized_html
    assert "local/test review" in normalized_html
    assert "manual request context" in normalized_html
    assert "verified complaint" not in normalized_html
    assert "proven complaint" not in normalized_html
    assert "complete public record" not in normalized_html
    assert "facility has no complaints" not in normalized_html
    assert "no complaints found" not in normalized_html
    assert "official finding" not in normalized_html
    assert "licensed and valid" not in normalized_html
    assert "assigned record" not in normalized_html
    assert "claimed record" not in normalized_html
    assert "export approved" not in normalized_html
    assert "correction applied" not in normalized_html
    assert_no_secret_html(html)


def test_reviewer_ui_detail_distinguishes_directory_backed_facility_context(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    facility_csv = tmp_path / "facility-reference.csv"
    signals_csv = tmp_path / "missing-signals.csv"
    _write_chhs_facility_directory_csv(facility_csv, facility_numbers=("157806098",))
    monkeypatch.setenv(CCLD_FACILITY_REFERENCE_CSV_ENV, str(facility_csv))
    monkeypatch.setenv(FACILITY_REVIEW_SIGNALS_CSVS_ENV, str(signals_csv))

    with _seeded_connection() as connection:
        status, content_type, body = route_response(
            f"{REVIEWER_UI_DETAIL_PATH}?source_record_key={quote(COMPLAINT_KEY)}"
            "&facility_number=157806098&request_context_origin=facility_lookup",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Facility context cues" in html
    assert "directory-backed facility hub cue" in html
    assert "Facility context type" in html
    assert "facility hub" in html
    assert f"{CCLD_FACILITY_REVIEW_HUB_PATH}?facility_number=157806098" in html
    assert "Open facility hub" in html
    assert "Return to facility hub" in html
    assert "signal-only facility hub" not in html
    assert_no_secret_html(html)


def test_reviewer_ui_detail_shows_manual_context_when_facility_hub_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    facility_csv = tmp_path / "facility-reference.csv"
    signals_csv = tmp_path / "missing-signals.csv"
    _write_chhs_facility_directory_csv(facility_csv, facility_numbers=("434417302",))
    monkeypatch.setenv(CCLD_FACILITY_REFERENCE_CSV_ENV, str(facility_csv))
    monkeypatch.setenv(FACILITY_REVIEW_SIGNALS_CSVS_ENV, str(signals_csv))

    with _seeded_connection() as connection:
        before_counts = _table_counts(connection)
        status, content_type, body = route_response(
            f"{REVIEWER_UI_DETAIL_PATH}?source_record_key={quote(COMPLAINT_KEY)}"
            "&facility_number=157806098&request_context_origin=manual_entry",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )
        after_counts = _table_counts(connection)

    html = body.decode("utf-8")
    normalized_html = " ".join(html.split()).casefold()

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert before_counts == after_counts == {
        "import_batches": 1,
        "source_records": 6,
        "reviewer_created_state": 0,
        "audit_events": 0,
        "reset_reload_planning_metadata": 0,
    }
    assert "Facility context cues" in html
    assert "manual request context" in normalized_html
    assert "A facility hub cue is not available" in html
    assert f"{CCLD_FACILITY_REVIEW_HUB_PATH}?facility_number=157806098" not in html
    assert "Open signal-only facility hub" not in html
    assert "Open facility hub" not in html
    assert "Return to facility review priority list" in html
    assert "Start complaint request if needed" in html
    assert_no_secret_html(html)


def test_reviewer_ui_detail_source_confidence_proxy_cues_are_non_mutating() -> None:
    with _seeded_connection() as connection:
        complaint_row = connection.execute(
            select(hosted_source_derived_records.c.original_values).where(
                hosted_source_derived_records.c.source_record_key == COMPLAINT_KEY
            )
        ).scalar_one()
        updated_values = dict(complaint_row)
        updated_values["report_date_used_as_proxy"] = True
        updated_values["visit_date"] = None
        connection.execute(
            update(hosted_source_derived_records)
            .where(hosted_source_derived_records.c.source_record_key == COMPLAINT_KEY)
            .values(original_values=updated_values)
        )
        before_source_rows = _source_rows(connection)
        before_counts = _table_counts(connection)

        status, content_type, body = route_response(
            f"{REVIEWER_UI_DETAIL_PATH}?source_record_key={quote(COMPLAINT_KEY)}",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

        after_source_rows = _source_rows(connection)
        after_counts = _table_counts(connection)

    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())

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
    assert "Source-confidence cues" in html
    assert "Visit date" in html
    assert "Not available in this local/test record" in html
    assert "Fallback/proxy-derived delay basis indicated" in normalized_html
    assert "Field-note guidance" in html
    assert "local/test cue marks report date as a proxy" in normalized_html
    assert "Do not use the proxy flag alone" in normalized_html
    assert "Use fallback/proxy wording only when this cue says" in normalized_html
    assert "use feedback if proxy wording or next action remains confusing" in (
        normalized_html
    )
    assert "not a source-confidence score" in normalized_html
    assert "public-source absence finding" in html
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
    assert "Field-note guidance" in html
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
    assert "Reviewer-created state saved" in html
    assert "Reviewer note saved for this record" in html
    assert "The note now appears in reviewer-created state below" in html
    assert "What changed" in html
    assert "Note: added" in html
    assert "What did not change" in html
    assert "Source-derived complaint fields" in html
    assert "Source traceability" in html
    assert "Public-source records" in html
    assert "Next" in html
    assert "Return to facility queue" in html
    assert "Open next priority record" in html
    assert "Report save or return-to-queue confusion" in html
    assert "workflow_area=save-confirmation" in html
    assert "Describe+note%2Fstatus+save%2C+return-to-queue%2C+or+next-record+confusion" in html
    assert "Review packet readiness before copying or printing" in html
    assert f"{REVIEWER_UI_PACKET_PREVIEW_PATH}?facility_number=157806098" in html
    assert "Open local/test preparation draft for browser copy or print" in html
    assert f"{REVIEWER_UI_PACKET_DRAFT_PATH}?facility_number=157806098" in html
    assert "Queue progress and note/status cues are derived from reviewer-created state" in html
    assert "Status filters are reviewer-created queue views" in html
    assert "filtered-empty queue state" in html
    assert "not public-source absence" in html
    assert "source-completeness proof" in html
    assert "same facility/license number and date range" in normalized_html
    assert "submit the request again" in html
    assert "continuing to the next record" in html
    assert "suggested next record is not a persisted assignment" in html
    assert "automatic record claim" in normalized_html
    assert "official workflow state" in html
    assert "manual feedback checklist" in html
    assert "not a legal report, not a final export, not a certified report" in normalized_html
    assert "record-specific observation" in html
    assert "existing manual feedback checklist" in html
    assert (
        "source traceability, source-confidence, field-note, or possible correction concern wording"
        in normalized_html
    )
    assert "157806098" in html
    assert "2022-08-01 to 2022-08-31" in html
    assert "return_facility_number=157806098" in html
    assert "Review saved notes and statuses below" in html
    assert "Review source traceability before export." in html
    assert "reviewer_note_scaffold" in html
    assert "Reviewer-created payload kinds present" in html
    assert "Latest reviewer-created row" in html
    assert "Related seeded source-derived context" in html
    assert "Field-note guidance" in html
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
    assert "Reviewer-created state saved" in html
    assert "Reviewer status saved for this record" in html
    assert "The status now appears in reviewer-created state below" in html
    assert (
        "Source-derived fields remain unchanged, and no correction decision was submitted"
        in html
    )
    assert "What changed" in html
    assert "Status: Needs follow-up" in html
    assert "What did not change" in html
    assert "Source-derived complaint fields" in html
    assert "Source traceability" in html
    assert "Public-source records" in html
    assert "Correction workflow state" in html
    assert "Next" in html
    assert "Return to facility queue" in html
    assert "Open next priority record" in html
    assert "Report save or return-to-queue confusion" in html
    assert "workflow_area=save-confirmation" in html
    assert "Review packet readiness before copying or printing" in html
    assert f"{REVIEWER_UI_PACKET_PREVIEW_PATH}?facility_number=157806098" in html
    assert "Open local/test preparation draft for browser copy or print" in html
    assert f"{REVIEWER_UI_PACKET_DRAFT_PATH}?facility_number=157806098" in html
    assert "Queue progress and note/status cues are derived from reviewer-created state" in html
    assert "Status filters are reviewer-created queue views" in html
    assert "filtered-empty queue state" in html
    assert "not public-source absence" in html
    assert "submit the request again" in html
    assert "continuing to the next record" in html
    assert "suggested next record is not a persisted assignment" in html
    assert "automatic record claim" in " ".join(html.split())
    assert "official workflow state" in html
    assert "manual feedback checklist" in html
    assert "not a legal report, not a final export, not a certified report" in " ".join(
        html.split()
    )
    assert "record-specific observation" in html
    assert "existing manual feedback checklist" in html
    assert (
        "source traceability, source-confidence, field-note, or possible correction concern wording"
        in " ".join(html.split())
    )
    assert "return_facility_number=157806098" in html
    assert "Review saved notes and statuses below" in html
    assert "reviewer_status_scaffold" in html
    assert "needs_follow_up" in html
    assert "Reviewer-created statuses present" in html
    assert "Reviewer-created payload kinds present" in html
    assert "Latest reviewer-created row" in html
    assert "Related seeded source-derived context" in html
    assert "Field-note guidance" in html
    assert "Fixture UI Status Reviewer (tester)" in html
    assert_no_correction_workflow_html(html)
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


def test_reviewer_status_values_do_not_add_correction_workflow_status() -> None:
    assert "correction" not in " ".join(REVIEWER_STATUS_VALUES).casefold()
    assert set(REVIEWER_STATUS_VALUES) == {
        "not_started",
        "in_review",
        "reviewed",
        "blocked",
        "needs_follow_up",
    }


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
    assert "1 reviewer-created note" in list_html
    assert "blocked" in list_html
    assert "No reviewer-created note/status yet" not in list_html
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
    status, content_type, body = route_response(
        "/reviewer",
        auth_runtime_config=_local_dev_auth_config(),
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Complaint records ready for review" in html
    assert "32-CR-20220407124448" in html
    assert_no_secret_html(html)


def _local_dev_auth_config() -> Any:
    return load_hosted_auth_runtime_config(
        environ={
            "CCLD_HOSTED_TESTER_AUTH_MODE": "local-dev",
            "CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH": "enabled",
        }
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


def assert_no_correction_workflow_html(markup: str) -> None:
    lowered = " ".join(markup.casefold().split())
    for marker in [
        'action="/reviewer/correction',
        'action="/reviewer/corrections',
        'action="/ccld/correction',
        'action="/ccld/corrections',
        'name="correction_status"',
        'name="correction_decision"',
        'value="correction_',
        'href="/reviewer/correction',
        'href="/ccld/correction',
        "correction submitted",
        "correction approved",
        "correction applied",
        "corrected source record",
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


def _write_chhs_facility_directory_csv(
    path: Path,
    *,
    facility_numbers: tuple[str, ...],
) -> None:
    fieldnames = (
        "FAC_NBR",
        "NAME",
        "PROGRAM_TYPE",
        "STATUS",
        "CAPACITY",
        "RES_CITY",
        "RES_STATE",
        "RES_ZIP_CODE",
        "COUNTY",
        "FAC_TYPE_DESC",
    )
    rows = [
        {
            "FAC_NBR": facility_number,
            "NAME": f"Fixture Facility {facility_number}",
            "PROGRAM_TYPE": "CHILD CARE",
            "STATUS": "LICENSED",
            "CAPACITY": "48",
            "RES_CITY": "BAKERSFIELD",
            "RES_STATE": "CA",
            "RES_ZIP_CODE": "93307",
            "COUNTY": "KERN",
            "FAC_TYPE_DESC": "TEMPORARY SHELTER CARE FACILITY",
        }
        for facility_number in facility_numbers
    ]
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_program_summary_signals_csv(
    path: Path,
    *,
    facility_number: str,
    facility_name: str,
) -> None:
    fieldnames = (
        "Facility Type",
        "Facility Number",
        "Facility Name",
        "Licensee",
        "Facility Administrator",
        "Facility Telephone Number",
        "Facility Address",
        "Facility City",
        "Facility State",
        "Facility Zip",
        "County Name",
        "Regional Office",
        "Facility Capacity",
        "Facility Status",
        "License First Date",
        "Closed Date",
        "Last Visit Date",
        "Inspection Visits",
        "Complaint Visits",
        "Other Visits",
        "Total Visits",
        "Citation Numbers",
        "POC Dates",
        "All Visit Dates",
        "Inspection Visit Dates",
        "Inspect TypeA",
        "Inspect TypeB",
        "Other Visit Dates",
        "Other TypeA",
        "Other TypeB",
        "Complaint Info- Date, #Sub Aleg, # Inc Aleg, # Uns Aleg, # TypeA, # TypeB ...",
    )
    row = {
        "Facility Type": "TEMPORARY SHELTER CARE FACILITY",
        "Facility Number": facility_number,
        "Facility Name": facility_name,
        "Licensee": "Do Not Display Licensee",
        "Facility Administrator": "Do Not Display Admin",
        "Facility Telephone Number": "555-0199",
        "Facility Address": "1 Private Fixture Way",
        "Facility City": "BAKERSFIELD",
        "Facility State": "CA",
        "Facility Zip": "93307",
        "County Name": "KERN",
        "Regional Office": "Central Valley",
        "Facility Capacity": "48",
        "Facility Status": "LICENSED",
        "License First Date": "7/30/2018",
        "Closed Date": "",
        "Last Visit Date": "5/4/2026",
        "Inspection Visits": "0",
        "Complaint Visits": "12",
        "Other Visits": "31",
        "Total Visits": "43",
        "Citation Numbers": "84072(d)(14), 84665.5(f)",
        "POC Dates": "07/28/2021, 06/20/2024",
        "All Visit Dates": "",
        "Inspection Visit Dates": "",
        "Inspect TypeA": "",
        "Inspect TypeB": "",
        "Other Visit Dates": "",
        "Other TypeA": "A citation",
        "Other TypeB": "B citation",
        "Complaint Info- Date, #Sub Aleg, # Inc Aleg, # Uns Aleg, # TypeA, # TypeB ...": "",
    }
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(row)


def _case_brief_record_for_priority(
    source_record_key: str,
    *,
    reviewer_status: str | None,
    reviewer_note_count: int,
    delay_thresholds: tuple[int, ...],
    order_index: int,
) -> FacilityCaseBriefRecord:
    return FacilityCaseBriefRecord(
        source_record_key=source_record_key,
        detail_href=f"/reviewer/records/detail?source_record_key={source_record_key}",
        complaint_control_number=source_record_key,
        finding="Substantiated",
        complaint_received_date="2022-08-01",
        visit_date="2022-08-03",
        report_date="2022-08-05",
        date_signed="2022-08-06",
        facility_number="157806098",
        facility_name="A. MIRIAM JAMISON",
        has_source_traceability=True,
        reviewer_status=reviewer_status,
        reviewer_status_label=reviewer_status,
        reviewer_note_count=reviewer_note_count,
        delay_thresholds=delay_thresholds,
        missing_first_activity_date=False,
        missing_visit_date=False,
        missing_report_date=False,
        missing_signed_date=False,
        report_date_used_as_proxy=False,
        order_index=order_index,
    )
