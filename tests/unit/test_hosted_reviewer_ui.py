from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote, urlencode

import pytest
from sqlalchemy import create_engine, func, select, update
from sqlalchemy.engine import Connection

from ccld_complaints.hosted_app import reviewer_ui
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
    REVIEWER_UI_SUBSTANTIATED_TRIAGE_PATH,
    _complaint_export_status_counts,
    complaint_export_attachment_filename,
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


class ElementTextByIdParser(HTMLParser):
    def __init__(self, element_id: str) -> None:
        super().__init__()
        self._element_id = element_id
        self._target_tag: str | None = None
        self._capture_depth = 0
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_values = dict(attrs)
        if self._target_tag is None and attr_values.get("id") == self._element_id:
            self._target_tag = tag
            self._capture_depth = 1
            return
        if self._capture_depth:
            self._capture_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if not self._capture_depth:
            return
        self._capture_depth -= 1
        if self._capture_depth == 0 and tag == self._target_tag:
            self._target_tag = None

    def handle_data(self, data: str) -> None:
        if self._capture_depth:
            self._text.append(data)

    @property
    def text(self) -> str:
        return " ".join("".join(self._text).split())


def _text_for_id(html: str, element_id: str) -> str:
    parser = ElementTextByIdParser(element_id)
    parser.feed(html)
    return parser.text


class ElementTextByTagParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[str] = []
        self._capture_stack: list[str] = []
        self._text_by_tag: dict[str, list[str]] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag)
        self._capture_stack.append(tag)
        self._text_by_tag.setdefault(tag, [])

    def handle_endtag(self, tag: str) -> None:
        if self._capture_stack and self._capture_stack[-1] == tag:
            self._capture_stack.pop()

    def handle_data(self, data: str) -> None:
        for tag in self._capture_stack:
            self._text_by_tag.setdefault(tag, []).append(data)

    def text_for(self, tag: str) -> str:
        return " ".join("".join(self._text_by_tag.get(tag, [])).split())


def _assert_collapsed_disclosure(html: str, label: str) -> None:
    summary = f"<summary>{label}</summary>"
    summary_index = html.index(summary)
    details_start = html.rfind("<details", 0, summary_index)
    assert details_start != -1
    details_tag = html[details_start : html.index(">", details_start) + 1]
    assert " open" not in details_tag


def test_reviewer_ui_landing_lists_seeded_source_derived_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CCLD_RETRIEVAL_DEMO_MODE", "mock-success")

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
    assert (
        _text_for_id(html, "facility-case-brief-heading")
        == "A. MIRIAM JAMISON CHILDREN'S CENTER"
    )
    assert _text_for_id(html, "facility-case-brief-heading") != "Facility"
    assert "Facility/license number: 157806098" in html
    assert "Complaint records visible" in html
    mode_panel = html.split('<div class="mode-panel" aria-label="Retrieval mode">', 1)[1].split(
        "</div>",
        1,
    )[0]
    assert html.count("Fixture/mock demo") == 1
    assert html.count('<span class="ds-badge ds-badge--info">Fixture/mock demo</span>') == 1
    assert '<span class="ds-badge ds-badge--info">Fixture/mock demo</span>' in mode_panel
    assert "Records with review flags" in html
    assert "Reviewer-created notes/statuses" in html
    assert "Findings represented" in html
    assert "Suggested first record for review" in html
    assert "Why open this first" in html
    assert "Open priority record" in html
    assert "Open full queue" in html
    assert "Open packet preview" in html
    assert REVIEWER_UI_PACKET_PREVIEW_PATH in html
    assert "Open print draft" in html
    assert REVIEWER_UI_PACKET_DRAFT_PATH in html
    assert "Open local/test packet preview" not in html
    assert "Open local/test preparation draft for browser copy or print" not in html
    assert "Skip to main reviewer content" in html
    assert '<main id="main-content" class="ds-page-main app-page" tabindex="-1">' in html
    assert "Technical runtime details" in html
    assert "reviewer UI shell" not in html
    assert "fixture actor context" not in normalized_html
    assert "seeded corpus scope" not in normalized_html
    assert "review-chip" in html
    assert "Original CCLD source link saved" in html
    assert "Attorney workflow" not in html
    assert "Current step:" not in html
    assert "Worklist" in html
    assert '<div class="dense-section-header">' in html
    assert 'class="result-list dense-card-grid"' in html
    assert 'class="technical-details dense-table-details"' in html
    assert 'class="technical-details diagnostic-details"' in html
    assert "Filter or search queue" in html
    assert "Keyboard flow: search filters this queue" not in html
    assert "Show table view" in html
    assert "Public records stay separate from saved notes/status" not in normalized_html
    assert "Worklist" in html
    assert "Queue status summary" not in html
    assert "Original CCLD source link saved" in html
    assert "Open record" in html
    assert "No reviewer-created status recorded yet" in html
    summary_metric_indexes = [
        html.index(label)
        for label in (
            "Complaint records visible",
            "Records with review flags",
            "Original source links saved",
            "Reviewer-created notes/statuses",
        )
    ]
    suggested_record_index = html.index("Suggested first record for review")
    review_flags_section_index = html.index(
        '<section class="quiet-section case-brief-section-break" '
        'aria-labelledby="case-brief-flags-heading">'
    )
    review_flags_heading_index = html.index(
        '<h3 id="case-brief-flags-heading">Review flags</h3>'
    )
    review_flags_strip_index = html.index(
        '<div class="metric-strip" aria-label="Review flag summary">'
    )
    review_flag_metric_indexes = [
        html.index(label, review_flags_strip_index)
        for label in (
            "Possible delay indicators",
            "Over 30 days",
            "Over 60 days",
            "Over 90 days",
            "Over 120 days",
            "Missing first activity date",
            "Needs source check",
        )
    ]
    findings_index = html.index("Findings represented")
    assert max(summary_metric_indexes) < suggested_record_index
    assert suggested_record_index < review_flags_section_index
    assert review_flags_section_index < review_flags_heading_index
    assert review_flags_heading_index < review_flags_strip_index
    assert review_flags_strip_index < min(review_flag_metric_indexes)
    assert max(review_flag_metric_indexes) < findings_index
    assert "Reviewer-created notes/statuses" in html
    assert "Original CCLD source link saved" in html
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
    assert "Original CCLD source link saved" in html
    assert "Open record 32-CR-20220407124448" in html
    assert "32-CR-20220407124448" in html
    assert COMPLAINT_KEY in html
    assert "raw SHA-256" in html
    assert "This runtime does not add production sign-in" in normalized_html
    assert "Open record 32-CR-20220407124448" in html
    assert_no_secret_html(html)

def test_reviewer_ui_landing_shows_visible_complaint_export_controls() -> None:
    with _seeded_connection() as connection:
        status, content_type, body = route_response(
            "/reviewer",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert 'id="complaint-export-controls"' in html
    assert "review matrix export" in html
    assert "Download complaint review matrix CSV" in html
    assert "Global complaint exports" in html
    assert "Complaint export records (source-derived):" in html
    assert "Serious review cue records:" in html
    assert (
        "Serious review cues are deterministic keyword-based review aids and are not "
        "verified severity findings."
    ) in html
    assert "Download substantiated complaint CSV" in html
    assert "Download unsubstantiated complaint CSV" in html
    assert "Download all complaint CSV" in html
    assert "Download serious review cue CSV" in html
    assert "Open cross-facility substantiated triage" in html
    assert "Download last 30 days complaint CSV" in html
    assert "Download last 90 days complaint CSV" in html
    assert "This facility complaint export records:" in html
    assert "This facility complaint exports" in html
    assert "Download this facility's substantiated complaint CSV" in html
    assert "Download this facility's all complaint CSV" in html
    assert "Download this facility's serious review cue CSV" in html
    assert "Download this facility's last 30 days complaint CSV" in html
    assert "Download this facility's last 90 days complaint CSV" in html
    assert (
        "Use CSV exports to triage and navigate records. "
        "Open the linked source record before relying on exported values."
    ) in html
    assert "Facility case brief" in html
    assert "Worklist" in html
    assert html.index("review matrix export") < html.index(
        "Download complaint review matrix CSV"
    )
    assert html.index("Download complaint review matrix CSV") < html.index(
        "Global complaint exports"
    )
    assert html.index("Global complaint exports") < html.index(
        "Open cross-facility substantiated triage"
    )
    assert html.index("Global complaint exports") < html.index(
        "Download substantiated complaint CSV"
    )
    assert html.index("Facility case brief") < html.index("Global complaint exports")
    assert html.index("Global complaint exports") < html.index("Worklist")
    assert "triage and navigate records" in normalized_html


def test_reviewer_ui_substantiated_triage_lists_cross_facility_matches() -> None:
    with _seeded_connection() as connection:
        _set_complaint_original_values(
            connection,
            COMPLAINT_KEY,
            {
                "finding": "Substantiated",
                "complaint_received_date": "2022-04-07",
            },
        )
        second_key = _insert_substantiated_complaint_for_facility(
            connection,
            facility_number="157806097",
            facility_name="SECOND FIXTURE FACILITY",
            complaint_control_number="32-CR-20220611112233",
            complaint_received_date="2022-06-11",
            report_date="2022-06-14",
            source_value_key="status",
            source_value="Founded",
            source_url="https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=157806097&inx=1",
        )
        before_source_rows = _source_rows(connection)
        before_counts = _table_counts(connection)

        status, content_type, body = route_response(
            REVIEWER_UI_SUBSTANTIATED_TRIAGE_PATH,
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
        "source_records": 9,
        "reviewer_created_state": 0,
        "audit_events": 0,
        "reset_reload_planning_metadata": 0,
    }
    assert "Cross-facility substantiated complaint triage" in html
    assert '<details class="technical-details notice-card">' in html
    assert '<details class="technical-details">' not in html
    _assert_collapsed_disclosure(
        html,
        "How to use this triage view",
    )
    assert html.index("Loaded substantiated/equivalent complaint records") < html.index(
        "How to use this triage view"
    )
    assert "A. MIRIAM JAMISON CHILDREN&#x27;S CENTER" in html
    assert "SECOND FIXTURE FACILITY" in html
    assert "Complaint received: 2022-04-07" in html
    assert "Report date: 2022-06-14" in html
    assert "finding: Substantiated" in html
    assert "status: Founded" in html
    assert (
        "Start with records whose source-derived finding/resolution/status needs attorney review."
        in html
    )
    assert "Open the source report and reviewer detail before using a value" in html
    assert f"source_record_key={quote(COMPLAINT_KEY)}" in html
    assert f"source_record_key={quote(second_key)}" in html
    assert "Open source report" in html
    assert_no_secret_html(html)


def test_reviewer_ui_substantiated_triage_empty_state_is_cautious() -> None:
    with _seeded_connection() as connection:
        before_source_rows = _source_rows(connection)
        before_counts = _table_counts(connection)

        status, content_type, body = route_response(
            REVIEWER_UI_SUBSTANTIATED_TRIAGE_PATH,
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
    assert "No loaded substantiated/equivalent complaint records matched." in html
    assert '<details class="technical-details notice-card">' in html
    assert '<details class="technical-details">' not in html
    _assert_collapsed_disclosure(
        html,
        "How to use this triage view",
    )
    assert html.index(
        "No loaded substantiated/equivalent complaint records matched."
    ) < html.index("How to use this triage view")
    assert html.index("How to use this triage view") < html.index(
        "Next steps"
    )
    assert "Return to review queue" in html
    assert "Return to CCLD request queue" in html
    assert "Use the review queue when no currently loaded records match this triage view." in html
    assert html.count(
        "Use the review queue when no currently loaded records match this triage view."
    ) == 1
    assert "Open the source report and reviewer detail" in html
    assert_no_secret_html(html)


def test_reviewer_ui_substantiated_triage_uses_safe_fallbacks() -> None:
    with _seeded_connection() as connection:
        _set_source_record_original_values(
            connection,
            "facility:ccld:facility:157806098",
            {
                "facility_name": None,
            },
        )
        _set_complaint_original_values(
            connection,
            COMPLAINT_KEY,
            {
                "finding": None,
                "resolution": "Substantiated",
                "complaint_received_date": None,
                "report_date": None,
                "visit_date": None,
                "date_signed": None,
            },
        )

        status, content_type, body = route_response(
            REVIEWER_UI_SUBSTANTIATED_TRIAGE_PATH,
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Facility/license 157806098" in html
    assert "No complaint/report date context available in currently loaded records." in html
    assert "resolution: Substantiated" in html
    assert_no_secret_html(html)


def test_reviewer_ui_substantiated_triage_hides_raw_narrative_and_unsupported_claims() -> None:
    with _seeded_connection() as connection:
        _set_complaint_original_values(
            connection,
            COMPLAINT_KEY,
            {
                "finding": "Substantiated",
            },
        )
        connection.execute(
            update(hosted_source_derived_records)
            .where(
                hosted_source_derived_records.c.source_record_key
                == "allegation:ccld:allegation:32-CR-20220407124448:1"
            )
            .values(
                original_values={
                    "allegation_category": "Staff conduct",
                    "allegation_text": "raw narrative should never appear in triage view",
                }
            )
        )

        status, content_type, body = route_response(
            REVIEWER_UI_SUBSTANTIATED_TRIAGE_PATH,
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    html = body.decode("utf-8")
    normalized_html = " ".join(html.split()).casefold()

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "raw narrative should never appear in triage view" not in normalized_html
    assert "verified severity" not in normalized_html
    assert "Open the source report and reviewer detail" in html
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
    assert "Packet preparation preview" in html
    assert "local/test" not in html.casefold()
    assert "Open print draft" in html
    assert "Open local/test preparation draft for browser copy or print" not in html
    assert f"{REVIEWER_UI_PACKET_DRAFT_PATH}?facility_number=157806098" in html
    assert "Back to review queue" in html
    assert "Return to same facility/date queue" not in html
    assert "/ccld/records/request?facility_number=157806098" in html
    assert "Report an issue" in html
    assert "Report copy/print preparation concern" not in html
    assert "workflow_area=packet-preview" in html
    assert "Describe+copy%2Fprint+preparation%2C+packet+readiness" in html
    assert "Packet readiness means review readiness only" in html
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
    assert "Original CCLD source link saved" in html
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
    assert "This preview is a preparation aid." in html
    assert "use the feedback link with this packet context" in html
    assert "Source-derived fields remain separate from reviewer-created notes/status." in html
    assert "Possible correction concerns are reviewer-created observations" in html
    assert "Review flags identify records needing attorney review." in html
    assert "Open source links from record detail when a source check is needed." in html
    assert "Use this preview to prepare review before browser copy or print." in html
    assert "No export file is generated by this preview" in html
    assert (
        "does not mutate source-derived records, reviewer-created state, audit rows"
        in normalized_html
    )
    assert "legal priority" not in normalized_html.casefold()
    assert_no_correction_workflow_html(html)
    assert_no_secret_html(html)

def test_reviewer_packet_draft_renders_print_copy_content_without_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_generated_at = "2026-06-28T02:08:48+00:00"

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> datetime:
            value = datetime(2026, 6, 28, 2, 8, 48, tzinfo=UTC)
            if tz is None:
                return value.replace(tzinfo=None)
            return value.astimezone(tz)

    monkeypatch.setattr(reviewer_ui, "datetime", FixedDateTime)

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
    assert "Preparation draft for browser copy or print" in html
    assert "local/test" not in html.casefold()
    assert "Use browser copy or print only after review" in html
    assert '<details class="packet-draft-guidance">' in html
    assert "<summary>Copy/print preparation guidance</summary>" in html
    _assert_collapsed_disclosure(html, "Copy/print preparation guidance")
    guidance_start = html.index('<details class="packet-draft-guidance">')
    guidance_end = html.index("</details>", guidance_start) + len("</details>")
    guidance_html = html[guidance_start:guidance_end]
    packet_scope_start = html.index('<section aria-labelledby="draft-scope-heading">')
    packet_scope_html = html[
        packet_scope_start : html.index("</section>", packet_scope_start)
    ]
    between_guidance_and_scope = html[guidance_end:packet_scope_start]
    assert guidance_start < guidance_end < packet_scope_start
    assert between_guidance_and_scope.strip() == ""
    assert "Copy/print preparation guidance" in html
    normalized_guidance_html = " ".join(guidance_html.split())
    assert "manual browser copy or print" in normalized_guidance_html
    assert "Packet readiness means review readiness only" in guidance_html
    assert (
        "ready for manual review, browser copy, or browser print"
        in normalized_guidance_html
    )
    assert "active facility/date context, included record count" in normalized_guidance_html
    assert "Review before copying or printing" in guidance_html
    assert "Source traceability available means visible source URL" in guidance_html
    assert "raw SHA-256 hash" in guidance_html
    assert "source document/report marker cues" in guidance_html
    assert "missing traceability values" in normalized_guidance_html
    assert "Correction-readiness before copying or printing" in guidance_html
    assert (
        "capture the possible correction concern in a reviewer-created note or feedback"
        in guidance_html
    )
    assert (
        "does not change source-derived records, alter source-derived values"
        in guidance_html
    )
    assert "If copy/print preparation content seems wrong" in guidance_html
    assert "Packet scope" not in guidance_html
    assert "Facility / license" in packet_scope_html
    assert "157806098" in packet_scope_html
    assert "Date range" in packet_scope_html
    assert "2022-08-01 to 2022-08-31" in packet_scope_html
    assert "Prepared from" in packet_scope_html
    assert "Generated" in packet_scope_html
    assert "Jun 27, 2026, 9:08 PM CT" in packet_scope_html
    assert "Generated: Jun 27, 2026, 9:08 PM CT" in html
    assert raw_generated_at not in html
    assert raw_generated_at not in packet_scope_html
    assert "Records included" in packet_scope_html
    assert "Preparation checkpoint" in packet_scope_html
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
    assert "Missing traceability values" in html
    assert "Original CCLD source link saved" in html
    assert "Needs source check before copy/print" in html
    assert "Reviewer-created status/note cue present" in html
    assert "Open record 32-CR-20220407124448" in html
    assert "Before using this draft" in html
    assert "Confirm the facility/date context matches the queue you intended to prepare." in html
    assert "Open reviewer detail for records needing source check." in html
    assert "Send feedback before copying or printing" in html
    assert "Copyable packet summary" in html
    assert "Attorney Review Packet Draft" in html
    assert "Facility/license: 157806098" in html
    assert "Reviewer-created state summary" in html
    assert "Records ready for preparation review" in html
    assert (
        "Packet readiness means review readiness for manual browser copy or print"
        in html
    )
    assert "Review-readiness before copy/print" in html
    assert "Source traceability readiness" in html
    assert "Back to packet preview" in html
    assert "Back to review queue" in html
    assert "Report copy/print preparation concern" in html
    assert "workflow_area=packet-draft" in html
    assert "Describe+browser+copy+or+print+preparation+or+packet+readiness+confusion" in html
    assert "@media print" in html
    assert "packet-draft" in html
    assert "site-header" in html and "display: none" in html
    assert "No export file is generated by this draft" in html
    assert "Return to the queue or reviewer detail" in normalized_html
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
    assert "Use a facility/date context so the draft can include" in html
    assert "Open Request Records" in html
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
    assert "Start from Request Records or the Review queue" in html
    assert "build a packet for a specific facility/date range." in html
    assert "Supply a facility/date context to show included records" in html
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
    assert "No loaded complaint records match the current search." in (
        " ".join(empty_html.split())
    )
    assert "No matching complaint records" in empty_html
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
    assert "Select a complaint record" in missing_key_html
    assert "Choose a loaded source-derived complaint record before opening reviewer detail." in (
        missing_key_html
    )
    assert "Return to reviewer records" in missing_key_html
    assert invalid_key_status == 404
    assert "Selected complaint record was not found" in invalid_key_html
    assert "The selected complaint record is not available" in invalid_key_html
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
    parser = ElementTextByTagParser()
    parser.feed(html)

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert parser.tags.count("h1") == 1
    assert parser.text_for("h1") == "Complaint 32-CR-20220407124448"
    assert html.index("Complaint 32-CR-20220407124448") < html.index(
        "Source record key"
    )
    assert "Review queue" in html
    assert "Complaint investigation report &middot; CCLD public source record" in html
    assert "Complaint review summary" in html
    assert "A. MIRIAM JAMISON CHILDREN&#x27;S CENTER | Facility/license 157806098" in html
    assert html.index("A. MIRIAM JAMISON") < html.index("Source traceability")
    assert html.index("A. MIRIAM JAMISON") < html.index(
        "Technical and operator details"
    )

    assert "Reviewer-created review state" in html
    assert html.index("Complaint review summary") < html.index(
        "Reviewer-created review state"
    )
    assert html.index("Reviewer-created review state") < html.index(
        "Facility identity and license facts"
    )
    assert f'action="{REVIEWER_UI_NOTE_PATH}"' in html
    assert f'action="{REVIEWER_UI_STATUS_PATH}"' in html
    assert "name=\"source_record_key\"" in html
    assert "Save note for this record" in html
    assert "Save status for this record" in html

    assert "Open CCLD source record" in html
    assert "Copy complaint summary" in html
    assert "Return to facility queue" in html
    assert "Open next flagged record" in html
    review_panel_start = html.index('id="review-actions-heading"')
    review_panel_end = html.index('id="why-flagged-heading"', review_panel_start)
    review_panel_html = html[review_panel_start:review_panel_end]
    assert "Current status" in review_panel_html
    assert "Status for this record" in review_panel_html
    assert "Note for this record" in review_panel_html
    assert "Save status for this record" in review_panel_html
    assert "Save note for this record" in review_panel_html
    assert "Return to facility queue" in review_panel_html
    assert "Open next flagged record" in review_panel_html
    assert "Keep it cautious" not in review_panel_html
    assert "Record what you checked" not in review_panel_html
    assert "Do not write that abuse, neglect, harm" not in review_panel_html
    assert "submit the request again" not in review_panel_html

    assert "Why this record is flagged" in html
    assert "Complaint/report timing needs source check" in html
    assert "First investigation activity date absent in loaded record" in html
    assert "Source traceability available for checking the original CCLD record" in html
    assert html.index("Complaint review summary") < html.index(
        "Why this record is flagged"
    )
    assert html.index("Why this record is flagged") < html.index(
        "Quick review summary"
    )

    assert html.count('class="quick-review-card"') == 6
    for href, label in (
        ("#allegations-findings-heading", "Finding"),
        ("#complaint-timeline-heading", "Timing"),
        ("#why-flagged-heading", "Review flags"),
        ("#citation-poc-heading", "Citation / POC"),
        ("#traceability-heading", "Source"),
        ("#review-actions-heading", "Reviewer status"),
    ):
        assert f'href="{href}"' in html
        assert label in html

    ordered_sections = [
        'id="record-summary-heading"',
        'id="complaint-timeline-heading"',
        'id="allegations-findings-heading"',
        'id="citation-poc-heading"',
        'id="source-narrative-heading"',
        'id="traceability-heading"',
        'id="reviewer-state-heading"',
        'id="review-guidance-heading"',
        'id="source-context-heading"',
        '<summary>Full source-derived fields</summary>',
        '<summary>Technical and operator details</summary>',
    ]
    previous_index = -1
    for section in ordered_sections:
        section_index = html.index(section)
        assert section_index > previous_index
        previous_index = section_index

    assert "Facility clients are being mistreated while in care." in html
    assert "Facility staff do not provide adequate supervision" in html
    assert "No citation, deficiency, or Plan of Correction cue is loaded" in html
    assert "Source type" in html
    assert "Traceability level" in html
    assert "Record loaded date" in html
    assert "Fields extracted" in html
    assert "Extraction confidence" in html
    assert "Connector" in html
    assert "Open CCLD portal source link" in html
    assert "Raw SHA-256" in html
    assert "Selected complaint source traceability fields" in html

    for term in (
        "CCLD",
        "Citation",
        "Type A citation",
        "Type B citation",
        "POC / Plan of Correction",
        "Substantiated",
        "Unsubstantiated",
        "Inconclusive",
        "Complaint investigation report",
        "Source traceability",
        "Report date used as proxy",
    ):
        assert term in html

    related_section_start = html.index('id="source-context-heading"')
    related_details_summary = "<summary>View related source bundle details</summary>"
    related_details_start = html.index(related_details_summary, related_section_start)
    related_default_html = html[related_section_start:related_details_start]
    related_details_end = html.index(
        "<summary>Full source-derived fields</summary>",
        related_details_start,
    )
    related_details_html = html[related_details_start:related_details_end]
    assert 'class="related-activity-card"' in related_default_html
    assert "Complaint investigation report" in related_default_html
    assert "Selected complaint record" in related_default_html
    assert "Finding: Unsubstantiated" in related_default_html
    assert "<table>" not in related_default_html
    assert "Stable source ID" not in related_default_html
    assert "Source document ID" not in related_default_html
    assert "Safe context shown" not in related_default_html
    assert "Same seeded bundle" not in related_default_html
    assert COMPLAINT_KEY not in related_default_html
    assert "ccld:document:" not in related_default_html
    assert "source_document:" not in related_default_html
    assert "Facility clients are being mistreated while in care." not in (
        related_default_html
    )
    _assert_collapsed_disclosure(html, "View related source bundle details")
    assert "Related source-derived rows in the selected seeded bundle" in (
        related_details_html
    )
    assert "Stable source ID" in related_details_html
    assert "Source document ID" in related_details_html
    assert "Safe context shown" in related_details_html
    assert "ccld:document:" in related_details_html

    _assert_collapsed_disclosure(html, "Full source-derived fields")
    _assert_collapsed_disclosure(html, "Technical and operator details")
    assert "verified delay" not in normalized_html.casefold()
    assert "proof of delayed investigation" not in normalized_html.casefold()
    assert "source is complete" not in normalized_html.casefold()
    assert "verified abuse" not in normalized_html.casefold()
    assert_no_correction_workflow_html(html)
    assert_no_secret_html(html)


def test_reviewer_ui_detail_collapses_long_source_narrative() -> None:
    long_narrative = " ".join(
        ["Long source narrative sentence for disclosure testing."] * 20
    )
    with _seeded_connection() as connection:
        _set_source_record_original_values(
            connection,
            COMPLAINT_KEY,
            {"source_text": long_narrative},
        )
        status, _content_type, body = route_response(
            f"{REVIEWER_UI_DETAIL_PATH}?source_record_key={quote(COMPLAINT_KEY)}",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    html = body.decode("utf-8")

    assert status == 200
    assert "Source narrative excerpt" in html
    assert "Show full source narrative" in html
    assert html.index("Source narrative excerpt") < html.index(
        "Show full source narrative"
    )
    assert html.index("Source narrative excerpt") < html.index(
        "Full source-derived fields"
    )
    _assert_collapsed_disclosure(html, "Show full source narrative")
    assert_no_secret_html(html)

def test_reviewer_ui_complaint_export_section_smoke_regression() -> None:
    with _seeded_connection() as connection:
        status, content_type, body = route_response(
            f"{REVIEWER_UI_DETAIL_PATH}?source_record_key={quote(COMPLAINT_KEY)}",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

        csv_status, csv_content_type, csv_body = route_response(
            f"{REVIEWER_UI_SUBSTANTIATED_EXPORT_PATH}?"
            "status=all&facility=157806098&start_date=2022-04-01&end_date=2022-04-30"
            "&request_context_origin=manual_entry",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Complaint review summary" in html
    assert "Return to facility queue" in html
    assert "Global complaint exports" not in html
    assert "triage and navigate records" not in normalized_html
    assert_no_secret_html(html)

    csv_text = csv_body.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = list(reader)

    assert csv_status == 200
    assert csv_content_type == "text/csv; charset=utf-8"
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
    assert record["Facility/License Number"] == "157806098"
    assert record["Complaint Control Number"] == "32-CR-20220407124448"

def test_complaint_export_status_counts_align_with_status_filter_semantics() -> None:
    counts = _complaint_export_status_counts(
        [
            {
                "entity_type": "facility",
                "original_values": {},
            },
            {
                "entity_type": "complaint",
                "original_values": {"finding": "Substantiated"},
            },
            {
                "entity_type": "complaint",
                "original_values": {"finding": "Unsubstantiated"},
            },
            {
                "entity_type": "complaint",
                "original_values": {"finding": "Inconclusive"},
            },
            {
                "entity_type": "allegation",
                "original_values": {"finding": "Substantiated"},
            },
        ]
    )

    assert counts == {
        "all": 3,
        "substantiated": 1,
        "unsubstantiated": 1,
    }

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
    assert row["matrix_status"] == "loaded complaint record"
    assert "complaint review matrix" in row["review_guidance"]
    assert "CSV export" in row["review_guidance"]
    assert "Excel-ready" in row["review_guidance"]
    assert "open source links and reviewer detail" in row["review_guidance"]
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
    assert "Original CCLD source link saved" in row["source_traceability_status"]
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
    assert "Original CCLD source link saved" in row["Source Traceability Status"]
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
        assert "Original CCLD source link saved" in record["Source Traceability Status"]
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
    path = (
        f"{REVIEWER_UI_SUBSTANTIATED_EXPORT_PATH}?"
        "request_context_origin=manual_entry"
    )

    with _seeded_connection() as connection:
        status, content_type, _body = route_response(
            path,
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    assert status == 200
    assert content_type == "text/csv; charset=utf-8"
    assert complaint_export_attachment_filename("request_context_origin=manual_entry") == (
        "complaints-substantiated.csv"
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
    path = f"{REVIEWER_UI_SUBSTANTIATED_EXPORT_PATH}?{query}"

    with _seeded_connection() as connection:
        status, content_type, _body = route_response(
            path,
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    assert status == 200
    assert content_type == "text/csv; charset=utf-8"
    assert complaint_export_attachment_filename(query) == expected_filename

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

@pytest.mark.parametrize(
    (
        "allegation_category",
        "review_cue_query",
        "status_value",
        "expect_row",
    ),
    (
        ("staff misconduct concern", "", "all", True),
        ("staff misconduct concern", "serious", "all", True),
        ("licensing paperwork", "serious", "all", False),
        ("licensing paperwork", "not-known", "all", True),
        ("staff misconduct concern", "serious", "substantiated", True),
    ),
)
def test_reviewer_ui_complaint_export_review_cue_query_filter_without_mutation(
    allegation_category: str,
    review_cue_query: str,
    status_value: str,
    expect_row: bool,
) -> None:
    with _seeded_connection() as connection:
        create_reviewer_note_scaffold(
            connection,
            _actor(roles=("tester_reviewer",), display_name="Fixture Cue Filter Note Reviewer"),
            scope=TEST_SCOPE,
            source_record_key=COMPLAINT_KEY,
            note_text="Cue filter export note.",
        )
        create_reviewer_status_scaffold(
            connection,
            _actor(roles=("tester_reviewer",), display_name="Fixture Cue Filter Reviewer"),
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
        complaint_values["finding"] = "Substantiated"
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

        query = (
            f"{REVIEWER_UI_SUBSTANTIATED_EXPORT_PATH}?"
            f"status={quote(status_value)}"
            "&facility=157806098"
            "&start_date=2022-04-01"
            "&end_date=2022-04-30"
            "&request_context_origin=manual_entry"
        )
        if review_cue_query:
            query = f"{query}&review_cue={quote(review_cue_query)}"

        status, content_type, body = route_response(
            query,
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

        after_source_rows = _source_rows(connection)
        after_counts = _table_counts(connection)

    csv_text = body.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = list(reader)

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
    if expect_row:
        assert record["Facility Name"] == "A. MIRIAM JAMISON CHILDREN'S CENTER"
        assert record["Facility/License Number"] == "157806098"
        assert record["Complaint Received Date"] == "2022-04-07"
        assert record["Finding/Status"] == "Substantiated"
    else:
        assert record["Facility Name"] == ""
        assert record["Facility/License Number"] == ""
        assert record["Complaint Received Date"] == ""
        assert record["Finding/Status"] == ""
    assert "Cue filter export note." not in csv_text
    assert "raw_path" not in csv_text
    assert "C:\\" not in csv_text
    assert "provider_subject" not in csv_text
    assert "token" not in csv_text.casefold()

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
        "No loaded complaint records matched this facility/date context."
    )
    assert row["facility_number"] == "157806098"
    assert row["request_start_date"] == "2026-01-01"
    assert row["request_end_date"] == "2026-01-31"
    assert row["loaded_local_test_record_indicator"] == "no"
    assert "open source links and reviewer detail" in row["review_guidance"]
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
    assert "not available in this record" in html
    assert "Missing: raw artifact reference" in html
    assert "Show field-level source details" in html
    assert "Source-confidence cues" in html
    assert "Field-note guidance" in html
    assert "First investigation activity date" in html
    assert "missing-field flag is true" in normalized_html
    assert "raw paths are not shown in the browser" in html
    assert "Use these fields when checking the public source" in normalized_html
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
    assert "Complaint review summary" in html
    assert "Facility/license number" in html
    assert "157806098" in html
    assert "Date range" in html
    assert "2026-01-01 to 2026-01-31" in html
    assert "manual_entry" in html
    assert "return_facility_number" in html
    assert "return_start_date" in html
    assert "return_end_date" in html
    assert "Review packet readiness before copying or printing" in html
    assert "Open print draft" in html
    assert "legally sufficient" not in normalized_html.casefold()
    assert "verified abuse" not in normalized_html.casefold()
    assert "complete source record" not in normalized_html.casefold()
    assert_no_secret_html(html)

def test_reviewer_ui_detail_shows_serious_review_cue_count_when_present() -> None:
    with _seeded_connection() as connection:
        complaint_row = connection.execute(
            select(hosted_source_derived_records).where(
                hosted_source_derived_records.c.source_record_key == COMPLAINT_KEY
            )
        ).mappings().one()
        complaint_values = dict(complaint_row["original_values"])
        complaint_values["finding"] = "Unsubstantiated"
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
        allegation_values["allegation_category"] = "staff misconduct concern"
        connection.execute(
            update(hosted_source_derived_records)
            .where(hosted_source_derived_records.c.source_record_key == allegation_key)
            .values(original_values=allegation_values)
        )

        status, content_type, body = route_response(
            f"{REVIEWER_UI_DETAIL_PATH}?source_record_key={quote(COMPLAINT_KEY)}",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "staff misconduct concern" in html
    assert "Serious review cue records:" not in html
    assert "review_cue=serious" not in html
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
    assert CCLD_FACILITY_REVIEW_PRIORITY_PATH in html
    assert "Return to facility review priority list" in html
    assert "Start complaint request if needed" in html
    assert "/ccld/records/request?facility_number=157806098" in html
    assert "&larr; Back to queue" in html
    assert f"{REVIEWER_UI_PACKET_PREVIEW_PATH}?facility_number=157806098" in html
    assert f"{REVIEWER_UI_PACKET_DRAFT_PATH}?facility_number=157806098" in html
    assert "use this cue to return to the facility hub" in normalized_html
    assert "review cue" in normalized_html
    assert "source-traceability cue" in normalized_html
    assert "source-derived value" in normalized_html
    assert "reviewer-created note/status" in normalized_html
    assert "review" in normalized_html
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
    assert "Not available in this record" in html
    assert "Fallback/proxy-derived delay basis indicated" in normalized_html
    assert "Field-note guidance" in html
    assert "cue marks report date as a proxy" in normalized_html
    assert "Do not use the proxy flag alone" in normalized_html
    assert "Use fallback/proxy wording only when this cue says" in normalized_html
    assert "use feedback if proxy wording or next action remains confusing" in (
        normalized_html
    )
    assert "do not use it as a source-confidence score" in normalized_html
    assert "avoid source absence or verification claims" in html
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
    assert "Complaint review summary" in html
    assert "Field-note guidance" in html
    assert "Feedback for this record" in html
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
    assert "Open print draft" in html
    assert f"{REVIEWER_UI_PACKET_DRAFT_PATH}?facility_number=157806098" in html
    assert "Queue progress and note/status cues are derived from reviewer-created state" in html
    assert "Status filters are reviewer-created queue views" in html
    assert "filtered-empty queue state" in html
    assert "Use the show-all status view" in html
    assert "same facility/license number and date range" in normalized_html
    assert "submit the request again" in html
    assert "continuing to the next record" in html
    assert "The suggested next record is navigation guidance" in html
    assert "manual feedback checklist" in html
    assert "use packet preview or draft as preparation checkpoints" in normalized_html
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
    assert "Reviewer-created notes and status history" in html
    assert "Latest note/status" in html
    assert "Related facility activity" in html
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
    assert "Open print draft" in html
    assert f"{REVIEWER_UI_PACKET_DRAFT_PATH}?facility_number=157806098" in html
    assert "Queue progress and note/status cues are derived from reviewer-created state" in html
    assert "Status filters are reviewer-created queue views" in html
    assert "filtered-empty queue state" in html
    assert "Use the show-all status view" in html
    assert "submit the request again" in html
    assert "continuing to the next record" in html
    assert "The suggested next record is navigation guidance" in html
    assert "manual feedback checklist" in html
    assert "use packet preview or draft as preparation checkpoints" in " ".join(html.split())
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
    assert "Status recorded" in html
    assert "Reviewer-created notes and status history" in html
    assert "Latest note/status" in html
    assert "Related facility activity" in html
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


def _set_source_record_original_values(
    connection: Connection,
    source_record_key: str,
    updates: dict[str, Any],
) -> None:
    row = connection.execute(
        select(hosted_source_derived_records.c.original_values).where(
            hosted_source_derived_records.c.source_record_key == source_record_key
        )
    ).scalar_one()
    original_values = dict(row)
    original_values.update(updates)
    connection.execute(
        update(hosted_source_derived_records)
        .where(hosted_source_derived_records.c.source_record_key == source_record_key)
        .values(original_values=original_values)
    )


def _set_complaint_original_values(
    connection: Connection,
    source_record_key: str,
    updates: dict[str, Any],
) -> None:
    _set_source_record_original_values(connection, source_record_key, updates)


def _insert_substantiated_complaint_for_facility(
    connection: Connection,
    *,
    facility_number: str,
    facility_name: str,
    complaint_control_number: str,
    complaint_received_date: str,
    report_date: str,
    source_value_key: str,
    source_value: str,
    source_url: str,
) -> str:
    batch_id = connection.execute(
        select(hosted_import_batches.c.import_batch_id)
    ).scalar_one()
    template_row = connection.execute(
        select(hosted_source_derived_records).where(
            hosted_source_derived_records.c.source_record_key == COMPLAINT_KEY
        )
    ).mappings().one()

    facility_id = f"ccld:facility:{facility_number}"
    document_id = f"ccld:document:{facility_number}:1"
    complaint_id = f"ccld:complaint:{complaint_control_number}"
    complaint_key = f"complaint:{complaint_id}"
    source_traceability = dict(template_row["source_traceability"])
    source_traceability.update(
        {
            "source_url": source_url,
            "raw_sha256": "f" * 64,
            "raw_path": "tests/fixtures/ccld/raw/157806097_inx1.html",
        }
    )

    connection.execute(
        hosted_source_derived_records.insert().values(
            source_record_key=f"facility:{facility_id}",
            entity_type="facility",
            stable_source_id=facility_id,
            import_batch_id=batch_id,
            source_document_id=document_id,
            facility_id=facility_id,
            source_url=source_url,
            raw_sha256="f" * 64,
            raw_path="tests/fixtures/ccld/raw/157806097_inx1.html",
            connector_name="ccld_facility_reports",
            connector_version="0.1.0",
            retrieved_at="2026-06-10T00:00:00+00:00",
            original_values={
                "facility_id": facility_id,
                "source_id": "ccld",
                "external_facility_number": facility_number,
                "facility_name": facility_name,
                "facility_type": "Children's Center",
                "county": "Kern",
            },
            source_traceability=source_traceability,
        )
    )

    connection.execute(
        hosted_source_derived_records.insert().values(
            source_record_key=f"source_document:{document_id}",
            entity_type="source_document",
            stable_source_id=document_id,
            import_batch_id=batch_id,
            source_document_id=document_id,
            facility_id=facility_id,
            source_url=source_url,
            raw_sha256="f" * 64,
            raw_path="tests/fixtures/ccld/raw/157806097_inx1.html",
            connector_name="ccld_facility_reports",
            connector_version="0.1.0",
            retrieved_at="2026-06-10T00:00:00+00:00",
            original_values={
                "document_id": document_id,
                "source_id": "ccld",
                "facility_id": facility_id,
                "source_url": source_url,
                "retrieved_at": "2026-06-10T00:00:00+00:00",
                "raw_sha256": "f" * 64,
                "connector_name": "ccld_facility_reports",
                "connector_version": "0.1.0",
                "raw_path": "tests/fixtures/ccld/raw/157806097_inx1.html",
                "document_type": "complaint_investigation_report",
                "report_index": 1,
            },
            source_traceability=source_traceability,
        )
    )

    complaint_values: dict[str, Any] = {
        "complaint_id": complaint_id,
        "facility_id": facility_id,
        "document_id": document_id,
        "complaint_control_number": complaint_control_number,
        "complaint_received_date": complaint_received_date,
        "report_date": report_date,
    }
    complaint_values[source_value_key] = source_value

    connection.execute(
        hosted_source_derived_records.insert().values(
            source_record_key=complaint_key,
            entity_type="complaint",
            stable_source_id=complaint_id,
            import_batch_id=batch_id,
            source_document_id=document_id,
            facility_id=facility_id,
            source_url=source_url,
            raw_sha256="f" * 64,
            raw_path="tests/fixtures/ccld/raw/157806097_inx1.html",
            connector_name="ccld_facility_reports",
            connector_version="0.1.0",
            retrieved_at="2026-06-10T00:00:00+00:00",
            original_values=complaint_values,
            source_traceability=source_traceability,
        )
    )

    return complaint_key

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
