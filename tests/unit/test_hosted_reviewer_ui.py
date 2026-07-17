from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from urllib.parse import parse_qs, quote, urlencode, urlparse

import pytest
from sqlalchemy import create_engine, event, func, select, update
from sqlalchemy.engine import Connection

from ccld_complaints.hosted_app import app as hosted_app
from ccld_complaints.hosted_app import reviewer_ui
from ccld_complaints.hosted_app.app import route_response
from ccld_complaints.hosted_app.audit_events import hosted_audit_events
from ccld_complaints.hosted_app.auth import (
    AuthenticatedActor,
    HostedAccessScope,
    HostedAccountStatus,
    HostedActorCategory,
    HostedScopeDeniedError,
    HostedTesterRole,
    load_hosted_auth_runtime_config,
)
from ccld_complaints.hosted_app.ccld_facility_lookup import (
    CCLD_FACILITY_REFERENCE_CSV_ENV,
    CCLD_FACILITY_REVIEW_HUB_PATH,
    CCLD_FACILITY_REVIEW_PRIORITY_PATH,
)
from ccld_complaints.hosted_app.ccld_record_request_ui import (
    ccld_record_request_context_for_reviewer_context,
)
from ccld_complaints.hosted_app.ccld_retrieval_jobs import (
    hosted_ccld_retrieval_jobs,
    retrieval_import_batch_id,
)
from ccld_complaints.hosted_app.facility_case_brief import (
    FacilityCaseBrief,
    FacilityCaseBriefRecord,
    render_facility_case_brief,
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
    POSTGRES_REVIEWER_UI_SCOPE,
    REVIEWER_UI_DETAIL_PATH,
    REVIEWER_UI_MATRIX_EXPORT_PATH,
    REVIEWER_UI_NOTE_PATH,
    REVIEWER_UI_PACKET_DRAFT_PATH,
    REVIEWER_UI_PACKET_PREVIEW_PATH,
    REVIEWER_UI_PREFIX,
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


def _assert_aggregate_export_fieldnames(fieldnames: list[str] | None) -> None:
    assert fieldnames is not None
    assert {
        "Facility Name",
        "Facility/License Number",
        "Complaint Received Date",
        "First Investigation Activity Date",
        "Date Dimension",
        "Selected Date",
        "Finding/Status",
        "Complaint Control Number",
        "Source Report URL",
        "Record Universe",
        "Eligible Count",
        "Exported Count",
        "Source Coverage Count",
        "Source Unavailable Count",
        "Query Start",
        "Query End",
        "Explicit Limit",
        "Truncated",
        "Result Status",
        "Result Cause",
    }.issubset(fieldnames)


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
    summary_index = html.index(f">{label}</summary>")
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
    normalized_html = " ".join(html.split()).casefold()
    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Complaint records ready for review" in html
    assert "Source-traceable complaint review." not in html
    assert "Signed in as Local Test Reviewer" not in html
    assert "function ensureCopyStatus(button)" in html
    assert "showCopyStatus(button, 'Copied')" in html
    assert "aria-live', 'polite'" in html
    assert "2000" in html
    mode_panel = html.split('<div class="mode-panel" aria-label="Retrieval mode">', 1)[1].split(
        "</div>",
        1,
    )[0]
    assert html.count("Fixture/mock demo") == 1
    assert html.count('<span class="ds-badge ds-badge--info">Fixture/mock demo</span>') == 1
    assert '<span class="ds-badge ds-badge--info">Fixture/mock demo</span>' in mode_panel
    assert "Open local/test packet preview" not in html
    assert "Open local/test preparation draft for browser copy or print" not in html
    assert "Skip to main reviewer content" in html
    assert '<a class="product-name" href="/">Records<span>Tracker</span></a>' in html
    assert '<span class="workspace-label">Reviewer Workspace</span>' in html
    assert (
        '<form class="shell-lookup" action="/ccld/facilities" method="get" role="search">'
        in html
    )
    assert 'placeholder="Search complaint, facility, Facility ID, or source record..."' in html
    assert "Search complaint, facility, license, or source record" not in html
    assert 'href="/ccld/facilities">Facilities</a>' in html
    assert '<main id="main-content" class="ds-page-main app-page" tabindex="-1">' in html
    assert '<h1 id="page-heading">Complaint records ready for review</h1>' in html
    assert "Technical runtime details" not in html
    assert "reviewer UI shell" not in html
    assert "fixture actor context" not in normalized_html
    assert "seeded corpus scope" not in normalized_html
    assert "Attorney workflow" not in html
    assert "Current step:" not in html
    assert '<section class="worklist-intro" aria-labelledby="worklist-intro-heading">' in html
    assert "Choose the next complaint to review" in html
    assert "Search records" in html
    assert html.count("Search records") == 1
    assert '<label class="sr-only" for="q">Queue search</label>' in html
    assert 'class="compact-search-form" role="search"' in html
    assert 'list="queue-search-suggestions"' in html
    assert '<datalist id="queue-search-suggestions">' in html
    for suggestion in (
        "32-CR-20220407124448",
        "157806098",
        "A. MIRIAM JAMISON CHILDREN&#x27;S CENTER",
        "Unsubstantiated",
        "No status",
        "No note",
    ):
        assert suggestion in html
    assert "Missing first activity" not in html
    assert "Missing source date" not in html
    assert "Source unavailable" not in html
    assert "Check source" not in html
    assert "Complaint worklist" in html
    assert "Showing 1 of 1 matching complaint record." in html
    assert "The matching record is shown within the current 100-record limit." in html
    assert '<div class="dense-section-header">' in html
    assert '<ol class="review-worklist" aria-label="Complaint records ready for review">' in html
    assert 'class="result-list dense-card-grid"' not in html
    assert 'class="review-worklist-row is-suggested"' in html
    work_item_start = html.index('class="review-worklist-row is-suggested"')
    work_item_end = html.index("</article>", work_item_start)
    work_item_html = html[work_item_start:work_item_end]
    for field_name in (
        "complaint-received",
        "visit",
        "report",
    ):
        assert f'data-worklist-field="{field_name}"' in work_item_html
    assert 'aria-label="Key complaint dates"' in work_item_html
    assert 'aria-label="Reviewer and source status"' in work_item_html
    assert "Review next" in work_item_html
    assert "No reviewer status has been saved." in work_item_html
    assert "A. MIRIAM JAMISON CHILDREN&#x27;S CENTER" in work_item_html
    assert "Facility ID" in work_item_html
    assert 'aria-label="Copy complaint/control number"' in work_item_html
    assert 'aria-label="Copy Facility ID"' in work_item_html
    assert "Finding / resolution" in work_item_html
    assert "Unsubstantiated" in work_item_html
    assert "Review flags" in work_item_html
    assert "No review flags" in work_item_html
    assert "Reviewer status" in work_item_html
    assert "No status" in work_item_html
    assert "Note" in work_item_html
    assert "No note" in work_item_html
    assert "CCLD source available" in work_item_html
    assert 'class="inline-glossary-term"' in work_item_html
    assert 'class="review-chip badge-info badge-info--status"' in work_item_html
    assert 'class="review-chip badge-info badge-info--note"' in work_item_html
    assert 'class="review-chip source-chip"' in work_item_html
    assert (
        'Review complaint <span class="sr-only">32-CR-20220407124448</span>'
        in work_item_html
    )
    assert work_item_html.count('href="/reviewer/records/detail?') == 1
    assert "grid-template-areas: \"identity dates outcome state action\";" in html
    assert 'grid-template-areas: "identity" "dates" "outcome" "state" "action";' in html
    assert 'class="technical-details dense-table-details"' in html
    assert 'class="technical-details diagnostic-details"' not in html
    assert "Keyboard flow: search filters this queue" not in html
    assert "About these results" in html
    assert "Show table view" in html
    assert "Exports" in html
    _assert_collapsed_disclosure(html, "About these results")
    _assert_collapsed_disclosure(html, "Show table view")
    _assert_collapsed_disclosure(html, "Exports")
    _assert_collapsed_disclosure(html, "Facility exports")
    assert "Public records stay separate from saved notes/status" not in normalized_html
    assert "Queue status summary" not in html
    section_order = [
        "Choose the next complaint to review",
        "Search records",
        "Complaint worklist",
        "About these results",
        "Show table view",
        "Exports",
    ]
    previous_index = -1
    for label in section_order:
        section_index = html.index(label)
        assert section_index > previous_index
        previous_index = section_index
    for removed in (
        "Complaint records visible",
        "Records with review flags",
        "Original source links saved",
        "Reviewer-created notes/statuses",
        "Suggested first record for review",
        "Why open this first",
        "Open priority record",
        "Open full queue",
        "No reviewer-created status recorded yet",
        "Possible delay indicator",
        "Needs source check:",
        "Original CCLD source link saved",
        "Findings represented",
        "Findings are source-derived categories, not legal conclusions.",
        "Use this summary to decide what to review first.",
        "Review flags are screening aids, not legal conclusions.",
        "Reviewer-created notes",
        "Reviewer-created status",
        "Source link/status",
        "Facility case brief",
        "Open packet preview",
        "Open print draft",
        "raw SHA-256",
        "raw artifact reference",
        "connector metadata",
        "retrieval timestamp",
        "source document/report marker",
    ):
        assert removed not in html
    assert "Complaint received date" in html
    assert "Visit" in html
    assert "Report" in html
    assert "No status" in html
    assert "No note" in html
    assert "CCLD source available" in html
    assert "04/07/2022" in html
    assert "08/24/2022" in html
    assert "2022-04-07" not in html
    assert "2022-08-24" not in html
    assert "32-CR-20220407124448" in html
    assert "this runtime does not add production sign-in" not in normalized_html
    assert_no_secret_html(html)


def test_facility_case_brief_pluralizes_record_count_labels() -> None:
    first_record = _case_brief_record_for_priority(
        "first-record",
        reviewer_status="reviewed",
        reviewer_note_count=1,
        delay_thresholds=(),
        order_index=1,
    )
    second_record = _case_brief_record_for_priority(
        "second-record",
        reviewer_status="reviewed",
        reviewer_note_count=1,
        delay_thresholds=(),
        order_index=2,
    )

    html = render_facility_case_brief(
        FacilityCaseBrief(
            facility_number="157806098",
            facility_name="A. MIRIAM JAMISON CHILDREN'S CENTER",
            date_range="not provided",
            mode_label="Fixture/mock demo",
            mode_badge_class="ds-badge ds-badge--info",
            records=(first_record, second_record),
            record_count_label="Records",
            flag_count_label="Flagged",
            source_available_label="Source available",
            reviewer_state_label="Notes/status saved",
            show_priority_record=False,
            show_review_cue_summary=False,
            show_findings_summary=False,
        )
    )

    assert "<strong>2</strong><span>Records</span>" in html
    assert "<strong>2</strong><span>Record</span>" not in html


def test_reviewer_ui_request_records_selected_facility_uses_facility_id_contract() -> None:
    with _seeded_connection() as connection:
        reviewer_context = reviewer_ui_context_for_connection(connection)
        status, content_type, body = route_response(
            "/ccld/records/request?facility_number=157806098"
            "&request_context_origin=lookup&lookup_facility_name=A.%20Miriam%20Jamison%20Children%27s%20Center",
            reviewer_ui_context=reviewer_context,
            ccld_record_request_ui_context=ccld_record_request_context_for_reviewer_context(
                reviewer_context
            ),
        )

    html = body.decode("utf-8")
    selected_context_start = html.index('class="summary-list selected-request-context')
    selected_context_end = html.index("</dl>", selected_context_start)
    selected_context_html = html[selected_context_start:selected_context_end]

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Choose complaint date range" in html
    assert "Facility ID" in selected_context_html
    assert "157806098" in selected_context_html
    assert 'aria-label="Copy selected Facility ID"' in selected_context_html
    assert "Facility/license" not in selected_context_html
    assert "Facility/license number" not in selected_context_html
    assert "facility/license number" not in selected_context_html
    assert_no_secret_html(html)


def test_reviewer_ui_landing_keeps_complaint_export_controls_secondary() -> None:
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
    assert "<summary id=\"complaint-export-controls-heading\">Exports</summary>" in html
    _assert_collapsed_disclosure(html, "Exports")
    _assert_collapsed_disclosure(html, "Facility exports")
    assert "Download complaint CSVs for review or comparison." in html
    for label in (
        "Matrix",
        "All complaints",
        "Substantiated",
        "Unsubstantiated",
        "Last 30 days",
        "Last 90 days",
        "Priority cues",
        "Facility exports",
        "All",
    ):
        assert label in html
    for removed in (
        "review matrix export",
        "Download complaint review matrix CSV",
        "Global complaint exports",
        "Complaint export records (source-derived):",
        "Serious review cue records:",
        "Serious review cues are deterministic keyword-based review aids",
        "Download substantiated complaint CSV",
        "Download unsubstantiated complaint CSV",
        "Download all complaint CSV",
        "Download serious review cue CSV",
        "Open cross-facility substantiated triage",
        "This facility complaint export records:",
        "This facility complaint exports",
        "Use CSV exports to triage and navigate records.",
    ):
        assert removed not in html
    assert "Facility case brief" not in html
    assert "Complaint worklist" in html
    assert html.index("Complaint worklist") < html.index("Exports")
    assert "triage and navigate records" not in normalized_html


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
        "source_records": 10,
        "reviewer_created_state": 0,
        "audit_events": 0,
        "reset_reload_planning_metadata": 0,
    }
    assert "Source-traceable substantiated complaint worklist" in html
    assert "Find substantiated complaint records that need source review" in html
    assert "Counts are reconciled to authorized loaded source-derived complaint records." in html
    assert '<details class="technical-details notice-card">' in html
    assert '<details class="technical-details">' not in html
    _assert_collapsed_disclosure(
        html,
        "How to use this triage view",
    )
    assert html.index("Loaded substantiated/equivalent complaint records") < html.index(
        "How to use this triage view"
    )
    assert "Showing 1-2 of 2 matching qualifying complaint record(s); 2 total qualifying" in html
    assert "Page 1 of 1." in html
    assert "Filter and sort" in html
    assert "A. MIRIAM JAMISON CHILDREN&#x27;S CENTER" in html
    assert "SECOND FIXTURE FACILITY" in html
    assert "04/07/2022" in html
    assert "06/11/2022" in html
    assert "Substantiated" in html
    assert "Founded" in html
    assert "Facility ID" in html
    assert "Normalized finding" in html
    assert "Category or summary" in html
    assert "Facility type" in html
    assert "Geography" in html
    assert "Original public report" in html
    assert "Open complaint review workspace" in html
    assert (
        "Start with records whose source-derived finding/resolution/status indicates "
        "substantiated or equivalent."
        in html
    )
    assert "Open the source report and reviewer detail before using a value" in html
    assert f"source_record_key={quote(COMPLAINT_KEY)}" in html
    assert f"source_record_key={quote(second_key)}" in html
    assert "Open original public report for 32-CR-20220407124448" in html
    assert "Open original public report for 32-CR-20220611112233" in html
    assert_no_secret_html(html)


def test_reviewer_ui_substantiated_worklist_filters_sorts_paginates_and_counts() -> None:
    with _seeded_connection() as connection:
        _set_complaint_original_values(
            connection,
            COMPLAINT_KEY,
            {
                "finding": "Substantiated",
                "complaint_received_date": "2022-04-07",
            },
        )
        _insert_substantiated_complaint_for_facility(
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
        missing_source_key = _insert_substantiated_complaint_for_facility(
            connection,
            facility_number="157806096",
            facility_name="ALPHA FIXTURE FACILITY",
            complaint_control_number="32-CR-20220301000000",
            complaint_received_date="2022-03-01",
            report_date="2022-03-04",
            source_value_key="finding",
            source_value="Sustained",
            source_url="",
        )

        status, content_type, body = route_response(
            (
                REVIEWER_UI_SUBSTANTIATED_TRIAGE_PATH
                +
                "?facility=157806097&facility_type=children&geography=kern"
                "&finding=Founded&sort=facility_asc&page_size=1"
            ),
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )
        missing_status, _content_type, missing_body = route_response(
            (
                REVIEWER_UI_SUBSTANTIATED_TRIAGE_PATH
                +
                "?facility=ALPHA&sort=complaint_date_asc&page_size=1"
            ),
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )
        page_status, _content_type, page_body = route_response(
            (
                REVIEWER_UI_SUBSTANTIATED_TRIAGE_PATH
                +
                "?sort=complaint_date_desc&page_size=1&page=2"
            ),
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    html = body.decode("utf-8")
    missing_html = missing_body.decode("utf-8")
    page_html = page_body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Showing 1-1 of 1 matching qualifying complaint record(s); 3 total qualifying" in html
    assert "SECOND FIXTURE FACILITY" in html
    assert "32-CR-20220611112233" in html
    assert "Founded" in html
    assert "Children&#x27;s Center" in html
    assert "Kern" in html
    assert "A. MIRIAM JAMISON" not in html
    assert "ALPHA FIXTURE FACILITY" not in html
    assert 'value="157806097"' in html
    assert 'value="children"' in html
    assert 'value="kern"' in html
    assert 'value="Founded"' in html
    assert "Open complaint review workspace" in html
    assert_no_secret_html(html)

    assert missing_status == 200
    assert (
        "Showing 1-1 of 1 matching qualifying complaint record(s); "
        "3 total qualifying"
        in missing_html
    )
    assert "ALPHA FIXTURE FACILITY" in missing_html
    assert "Original public report link not available for this loaded complaint." in missing_html
    assert f"source_record_key={quote(missing_source_key)}" in missing_html
    assert_no_secret_html(missing_html)

    assert page_status == 200
    assert (
        "Showing 2-2 of 3 matching qualifying complaint record(s); "
        "3 total qualifying"
        in page_html
    )
    assert "Page 2 of 3." in page_html
    assert "Previous page" in page_html
    assert "Next page" in page_html
    assert "A. MIRIAM JAMISON CHILDREN&#x27;S CENTER" in page_html
    assert "SECOND FIXTURE FACILITY" not in page_html
    assert_no_secret_html(page_html)


def test_reviewer_ui_substantiated_worklist_reconciles_distinct_qualifying_count() -> None:
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
            source_url=_ccld_source_url("157806097", "1"),
        )
        missing_source_key = _insert_substantiated_complaint_for_facility(
            connection,
            facility_number="157806096",
            facility_name="ALPHA FIXTURE FACILITY",
            complaint_control_number="32-CR-20220301000000",
            complaint_received_date="2022-03-01",
            report_date="2022-03-04",
            source_value_key="finding",
            source_value="Sustained",
            source_url="",
        )
        nonqualifying_key = _insert_substantiated_complaint_for_facility(
            connection,
            facility_number="157806095",
            facility_name="NONQUALIFYING FIXTURE FACILITY",
            complaint_control_number="32-CR-20220101000000",
            complaint_received_date="2022-01-01",
            report_date="2022-01-02",
            source_value_key="finding",
            source_value="Unsubstantiated",
            source_url=_ccld_source_url("157806095", "1"),
        )
        expected_count = _independent_distinct_substantiated_count(connection)

        status, content_type, body = route_response(
            REVIEWER_UI_SUBSTANTIATED_TRIAGE_PATH,
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    html = body.decode("utf-8")

    assert expected_count == 3
    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert (
        "Showing 1-3 of 3 matching qualifying complaint record(s); "
        "3 total qualifying"
        in html
    )
    assert html.count("Open complaint review workspace") == expected_count
    for source_record_key in (COMPLAINT_KEY, second_key, missing_source_key):
        assert f"source_record_key={quote(source_record_key)}" in html
    assert f"source_record_key={quote(nonqualifying_key)}" not in html
    assert "NONQUALIFYING FIXTURE FACILITY" not in html
    assert "Original public report link not available for this loaded complaint." in html
    assert_no_secret_html(html)


def test_reviewer_ui_substantiated_worklist_dedupes_duplicate_stable_identity(
) -> None:
    records = _fake_substantiated_source_bundle(
        facility_number="157806101",
        facility_name="DUPLICATE IDENTITY FACILITY",
        complaint_control_number="32-CR-20220714000000",
        complaint_received_date="2022-07-14",
        source_url=_ccld_source_url("157806101", "1"),
    )
    duplicate = dict(records[-1])
    duplicate["source_record_key"] = "complaint:ccld:duplicate:32-CR-20220714000000"
    duplicate["original_values"] = dict(duplicate["original_values"])
    duplicate["original_values"]["complaint_control_number"] = "DUPLICATE SHOULD NOT SHOW"
    source_records = [*records, duplicate]
    complaint_items = [
        reviewer_ui._review_item_from_source_record(record)
        for record in source_records
        if record["entity_type"] == "complaint"
    ]

    items = reviewer_ui._substantiated_triage_items(
        complaint_items,
        reviewer_ui._source_record_indexes(source_records),
    )

    assert len(items) == 1
    assert items[0]["complaint_control_number"] == "32-CR-20220714000000"


def test_reviewer_ui_substantiated_worklist_reads_beyond_first_source_page() -> None:
    with _seeded_connection() as connection:
        _set_complaint_original_values(
            connection,
            COMPLAINT_KEY,
            {
                "finding": "Substantiated",
                "complaint_received_date": "2022-04-07",
            },
        )
        for index in range(101):
            facility_number = f"200{index:06d}"
            _insert_substantiated_complaint_for_facility(
                connection,
                facility_number=facility_number,
                facility_name=f"BULK FACILITY {index:03d}",
                complaint_control_number=f"32-CR-202207{index:06d}",
                complaint_received_date="2022-07-01",
                report_date="2022-07-02",
                source_value_key="finding",
                source_value="Substantiated",
                source_url=(
                    "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports"
                    f"?facNum={facility_number}&inx=1"
                ),
            )

        status, content_type, body = route_response(
            (
                REVIEWER_UI_SUBSTANTIATED_TRIAGE_PATH
                +
                "?sort=facility_asc&page_size=100&page=2"
            ),
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert (
        "Showing 101-102 of 102 matching qualifying complaint record(s); "
        "102 total qualifying"
        in html
    )
    assert "Page 2 of 2." in html
    assert "Previous page" in html
    assert "BULK FACILITY 099" in html
    assert "BULK FACILITY 100" in html
    assert_no_secret_html(html)


def test_reviewer_ui_substantiated_worklist_includes_record_after_20000_source_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target_records = _fake_substantiated_source_bundle(
        facility_number="157806099",
        facility_name="AFTER CAP FIXTURE FACILITY",
        complaint_control_number="32-CR-20220712000000",
        complaint_received_date="2022-07-12",
        source_url=_ccld_source_url("157806099", "1"),
    )

    route_calls = 0

    def fake_source_route(
        path: str,
        context: object,
    ) -> tuple[int, str, bytes]:
        nonlocal route_calls
        route_calls += 1
        return _json_source_records_response(())

    def fake_authorized_bulk_read(*args: object, **kwargs: object) -> tuple[object, ...]:
        assert kwargs["entity_types"] == reviewer_ui._SUBSTANTIATED_SOURCE_ENTITY_TYPES
        return tuple(
            _read_model_from_source_payload(record)
            for record in (
                *_fake_filler_source_records(0, 20000),
                *target_records,
            )
        )

    monkeypatch.setattr(reviewer_ui, "route_source_derived_api_response", fake_source_route)
    monkeypatch.setattr(
        reviewer_ui,
        "list_authorized_source_derived_records_by_entity_types",
        fake_authorized_bulk_read,
    )

    with _seeded_connection() as connection:
        status, content_type, body = route_response(
            REVIEWER_UI_SUBSTANTIATED_TRIAGE_PATH,
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "AFTER CAP FIXTURE FACILITY" in html
    assert "32-CR-20220712000000" in html
    assert "Showing 1-1 of 1 matching qualifying complaint record(s); 1 total qualifying" in html
    assert "Open original public report for 32-CR-20220712000000" in html
    assert route_calls == 0
    assert_no_secret_html(html)


def test_substantiated_worklist_blocks_partial_results_after_authorized_read_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_authorized_bulk_read(*args: object, **kwargs: object) -> tuple[object, ...]:
        raise HostedScopeDeniedError("Synthetic source read failure.")

    monkeypatch.setattr(
        reviewer_ui,
        "list_authorized_source_derived_records_by_entity_types",
        fake_authorized_bulk_read,
    )

    with _seeded_connection() as connection:
        status, content_type, body = route_response(
            REVIEWER_UI_SUBSTANTIATED_TRIAGE_PATH,
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    html = body.decode("utf-8")

    assert status == 403
    assert content_type == "text/html; charset=utf-8"
    assert "Synthetic source read failure." in html
    assert "Loaded substantiated/equivalent complaint records" not in html
    assert "PARTIAL FAILURE FACILITY" not in html
    assert "32-CR-20220713000000" not in html
    assert_no_secret_html(html)


def test_reviewer_ui_substantiated_worklist_uses_live_related_finding_shape() -> None:
    with _seeded_connection() as connection:
        substantiated_key = _insert_substantiated_complaint_for_facility(
            connection,
            facility_number="107207198",
            facility_name="Representative Foster Family Agency",
            facility_type="FOSTER FAMILY AGENCY",
            complaint_control_number="24-CR-20260508083927",
            complaint_received_date="2026-05-08",
            report_date="2026-05-30",
            source_value_key="finding",
            source_value="Substantiated",
            source_url=_ccld_source_url("107207198", "25"),
        )
        unsubstantiated_key = _insert_substantiated_complaint_for_facility(
            connection,
            facility_number="425802141",
            facility_name="Representative Short Term Residential Therapeutic Program",
            facility_type="SHORT TERM RESIDENTIAL THERAPEUTIC PROGRAM",
            complaint_control_number="31-CR-20240425094018",
            complaint_received_date="2024-04-25",
            report_date="2024-05-21",
            source_value_key="finding",
            source_value="Unsubstantiated",
            source_url=_ccld_source_url("425802141", "33"),
        )
        _set_source_record_original_values(
            connection,
            substantiated_key,
            {"finding": None},
        )
        _set_source_record_original_values(
            connection,
            unsubstantiated_key,
            {"finding": None},
        )
        _insert_live_shape_related_finding_records(
            connection,
            substantiated_key,
            finding="Substantiated",
            event_text=(
                "The public report states the allegation was investigated and "
                "substantiated."
            ),
        )
        _insert_live_shape_related_finding_records(
            connection,
            substantiated_key,
            finding="Sustained",
            event_text="A duplicate allegation-level finding was sustained.",
            suffix="duplicate",
        )
        _insert_live_shape_related_finding_records(
            connection,
            unsubstantiated_key,
            finding="Unsubstantiated",
            event_text="The investigation finding states the allegation was unsubstantiated.",
        )
        expected_count = _independent_distinct_substantiated_count(connection)

        status, content_type, body = route_response(
            (
                REVIEWER_UI_SUBSTANTIATED_TRIAGE_PATH
                + "?facility=107207198&facility_type=FOSTER%20FAMILY%20AGENCY"
            ),
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )
        out_of_scope_status, _content_type, out_of_scope_body = route_response(
            REVIEWER_UI_SUBSTANTIATED_TRIAGE_PATH,
            reviewer_ui_context=reviewer_ui_context_for_connection(
                connection,
                actor=_actor(roles=("tester_reviewer",), scopes=(OTHER_SCOPE,)),
                scope=OTHER_SCOPE,
            ),
        )

    html = body.decode("utf-8")
    out_of_scope_html = out_of_scope_body.decode("utf-8")

    assert expected_count == 1
    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert (
        "Showing 1-1 of 1 matching qualifying complaint record(s); "
        "1 total qualifying"
        in html
    )
    assert html.count("Open complaint review workspace") == 1
    assert "107207198" in html
    assert "FOSTER FAMILY AGENCY" in html
    assert "24-CR-20260508083927" in html
    assert ">Substantiated<" in html
    assert "425802141" not in html
    assert "31-CR-20240425094018" not in html
    assert "Unsubstantiated" not in html
    assert out_of_scope_status in {200, 403}
    assert "Representative Foster Family Agency" not in out_of_scope_html
    assert "24-CR-20260508083927" not in out_of_scope_html
    assert_no_secret_html(html)
    assert_no_secret_html(out_of_scope_html)


def test_facility_type_classification_preserves_explicit_source_value() -> None:
    facility = {
        "facility_name": "4EVERGREEN FOSTER FAMILY AGENCY, INC.",
        "facility_type": "Children's Center",
    }

    classification = reviewer_ui._facility_type_classification(facility)

    assert classification.value == "Children's Center"
    assert classification.is_source_provided is True
    assert classification.display_value == "Children's Center"
    assert reviewer_ui._facility_context_value(facility, "facility_type") == "Children's Center"


def test_facility_type_classification_derives_foster_family_agency_from_name() -> None:
    facility = {
        "facility_name": "4EVERGREEN FOSTER FAMILY AGENCY, INC.",
        "facility_type": "",
    }

    classification = reviewer_ui._facility_type_classification(facility)

    assert classification.value == "Foster Family Agency"
    assert classification.is_source_provided is False
    assert classification.display_value == "Foster Family Agency (derived from facility name)"
    assert (
        reviewer_ui._facility_context_value(facility, "facility_type")
        == "Foster Family Agency (derived from facility name)"
    )


def test_facility_type_classification_leaves_ambiguous_names_unknown() -> None:
    for facility_name in (
        "Foster Support Services",
        "FFA Resource Center",
        "Family Agency Services",
    ):
        classification = reviewer_ui._facility_type_classification(
            {
                "facility_name": facility_name,
                "facility_type": None,
            }
        )
        assert classification.value == "unknown"
        assert classification.is_source_provided is True
        assert classification.display_value == "unknown"


def test_reviewer_ui_substantiated_worklist_facility_type_filter_uses_derived_ffa() -> None:
    with _seeded_connection() as connection:
        derived_key = _insert_substantiated_complaint_for_facility(
            connection,
            facility_number="157806111",
            facility_name="4EVERGREEN FOSTER FAMILY AGENCY, INC.",
            facility_type="",
            complaint_control_number="32-CR-20260701000001",
            complaint_received_date="2026-07-01",
            report_date="2026-07-02",
            source_value_key="finding",
            source_value="Substantiated",
            source_url=_ccld_source_url("157806111", "1"),
        )
        ambiguous_key = _insert_substantiated_complaint_for_facility(
            connection,
            facility_number="157806112",
            facility_name="EVERGREEN FFA RESOURCE CENTER",
            facility_type="",
            complaint_control_number="32-CR-20260701000002",
            complaint_received_date="2026-07-01",
            report_date="2026-07-02",
            source_value_key="finding",
            source_value="Substantiated",
            source_url=_ccld_source_url("157806112", "1"),
        )
        explicit_nonmatch_key = _insert_substantiated_complaint_for_facility(
            connection,
            facility_number="157806113",
            facility_name="SOURCE VALUE PRECEDENCE FOSTER FAMILY AGENCY",
            facility_type="Children's Center",
            complaint_control_number="32-CR-20260701000003",
            complaint_received_date="2026-07-01",
            report_date="2026-07-02",
            source_value_key="finding",
            source_value="Substantiated",
            source_url=_ccld_source_url("157806113", "1"),
        )
        null_type_key = _insert_substantiated_complaint_for_facility(
            connection,
            facility_number="157806114",
            facility_name="CLEAR FOSTER FAMILY AGENCY",
            facility_type="placeholder",
            complaint_control_number="32-CR-20260701000004",
            complaint_received_date="2026-07-01",
            report_date="2026-07-02",
            source_value_key="finding",
            source_value="Substantiated",
            source_url=_ccld_source_url("157806114", "1"),
        )
        _set_source_record_original_values(
            connection,
            "facility:ccld:facility:157806114",
            {"facility_type": None},
        )

        status, content_type, body = route_response(
            REVIEWER_UI_SUBSTANTIATED_TRIAGE_PATH
            + "?facility_type=FOSTER%20FAMILY%20AGENCY&sort=facility_asc",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert f"source_record_key={quote(derived_key)}" in html
    assert f"source_record_key={quote(null_type_key)}" in html
    assert f"source_record_key={quote(ambiguous_key)}" not in html
    assert f"source_record_key={quote(explicit_nonmatch_key)}" not in html
    assert "4EVERGREEN FOSTER FAMILY AGENCY, INC." in html
    assert "CLEAR FOSTER FAMILY AGENCY" in html
    assert "EVERGREEN FFA RESOURCE CENTER" not in html
    assert "SOURCE VALUE PRECEDENCE FOSTER FAMILY AGENCY" not in html
    assert "Foster Family Agency (derived from facility name)" in html
    assert "Facility type Children&#x27;s Center" not in html
    assert "Open original public report for 32-CR-20260701000001" in html
    assert "Open complaint review workspace" in html
    assert_no_secret_html(html)


def test_reviewer_ui_substantiated_worklist_uses_bounded_direct_source_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    route_calls = 0

    def fake_source_route(
        path: str,
        context: object,
    ) -> tuple[int, str, bytes]:
        nonlocal route_calls
        route_calls += 1
        return _json_source_records_response(())

    monkeypatch.setattr(reviewer_ui, "route_source_derived_api_response", fake_source_route)

    with _seeded_connection() as connection:
        _set_complaint_original_values(
            connection,
            COMPLAINT_KEY,
            {
                "finding": "Substantiated",
                "complaint_received_date": "2022-04-07",
            },
        )
        _insert_extraction_audit_marker(connection)
        select_statements: list[tuple[str, object]] = []

        def capture_select(
            conn: object,
            cursor: object,
            statement: str,
            parameters: object,
            context: object,
            executemany: bool,
        ) -> None:
            if statement.lstrip().upper().startswith("SELECT"):
                select_statements.append((statement, parameters))

        event.listen(connection, "before_cursor_execute", capture_select)
        try:
            status, content_type, body = route_response(
                REVIEWER_UI_SUBSTANTIATED_TRIAGE_PATH,
                reviewer_ui_context=reviewer_ui_context_for_connection(connection),
            )
        finally:
            event.remove(connection, "before_cursor_execute", capture_select)

    html = body.decode("utf-8")
    source_selects = [
        (statement, parameters)
        for statement, parameters in select_statements
        if "hosted_source_derived_records" in statement
    ]
    source_params = {
        str(value)
        for _statement, parameters in source_selects
        for value in _flatten_sql_parameters(parameters)
    }

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert route_calls == 0
    assert len(source_selects) == 1
    assert {"facility", "source_document", "complaint", "allegation", "event"}.issubset(
        source_params
    )
    assert "extraction_audit" not in source_params
    assert "AUDIT SHOULD NOT LOAD" not in html
    assert "A. MIRIAM JAMISON CHILDREN&#x27;S CENTER" in html
    assert_no_secret_html(html)


def test_postgres_corpus_substantiated_worklist_uses_authorized_retrieval_batches() -> None:
    substantiated = _representative_retrieval_record(
        facility_number="107207198",
        facility_name="4EVERGREEN FOSTER FAMILY AGENCY, INC.",
        facility_type="",
        county="Los Angeles",
        complaint_control_number="24-CR-20260508083927",
        report_index="25",
        finding="Substantiated",
        narrative=(
            "The public report states the allegation was investigated and "
            "substantiated."
        ),
        received_date="2026-05-08",
    )
    unsubstantiated = _representative_retrieval_record(
        facility_number="425802141",
        facility_name="Representative Short Term Residential Therapeutic Program",
        facility_type="Short Term Residential Therapeutic Program",
        county="Santa Barbara",
        complaint_control_number="31-CR-20240425094018",
        report_index="33",
        finding="Unsubstantiated",
        narrative="The investigation finding states the allegation was unsubstantiated.",
        received_date="2024-04-25",
    )
    with _seeded_connection() as connection:
        _insert_representative_live_public_retrieval_batch(
            connection,
            substantiated,
            scope=POSTGRES_REVIEWER_UI_SCOPE,
        )
        _insert_representative_live_public_retrieval_batch(
            connection,
            unsubstantiated,
            scope=POSTGRES_REVIEWER_UI_SCOPE,
        )
        context = reviewer_ui_context_for_connection(
            connection,
            actor=_actor(
                roles=("tester_reviewer",),
                scopes=(POSTGRES_REVIEWER_UI_SCOPE,),
            ),
            scope=POSTGRES_REVIEWER_UI_SCOPE,
        )
        status, content_type, body = route_response(
            REVIEWER_UI_SUBSTANTIATED_TRIAGE_PATH
            + "?facility=107207198&facility_type=Foster%20Family%20Agency",
            reviewer_ui_context=context,
        )
        future_status, _content_type, future_body = route_response(
            REVIEWER_UI_SUBSTANTIATED_TRIAGE_PATH
            + "?start_date=2099-01-01&end_date=2099-12-31",
            reviewer_ui_context=context,
        )

    html = body.decode("utf-8")
    future_html = future_body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert (
        "Showing 1-1 of 1 matching qualifying complaint record(s); "
        "1 total qualifying authorized source-derived complaint record(s)."
        in html
    )
    assert "4EVERGREEN FOSTER FAMILY AGENCY, INC." in html
    assert "107207198" in html
    assert "Foster Family Agency (derived from facility name)" in html
    assert "24-CR-20260508083927" in html
    assert ">Substantiated<" in html
    assert "425802141" not in html
    assert "Unsubstantiated" not in html

    assert future_status == 200
    assert "No loaded substantiated/equivalent complaint records matched." in future_html
    assert (
        "Showing 0 of 0 matching qualifying complaint record(s); "
        "1 total qualifying authorized source-derived complaint record(s)."
        in future_html
    )
    assert_no_secret_html(html)
    assert_no_secret_html(future_html)


def test_substantiated_event_finding_evidence_normalizes_public_event_text() -> None:
    event_record = {
        "entity_type": "event",
        "original_values": {
            "event_type": "investigation_finding",
            "event_text": (
                "The public report states the allegation was investigated and "
                "substantiated."
            ),
        },
    }
    unsubstantiated_event_record = {
        "entity_type": "event",
        "original_values": {
            "event_type": "investigation_finding",
            "event_text": "The investigation finding states the allegation was unsubstantiated.",
        },
    }

    evidence = reviewer_ui._substantiated_event_finding_evidence(event_record)

    assert evidence is not None
    assert evidence.value == "Substantiated"
    assert "public report states" not in evidence.value
    assert (
        reviewer_ui._substantiated_event_finding_evidence(unsubstantiated_event_record)
        is None
    )


def test_substantiated_worklist_sort_dates_and_facility_desc_are_deterministic() -> None:
    with _seeded_connection() as connection:
        _set_complaint_original_values(
            connection,
            COMPLAINT_KEY,
            {
                "finding": "Substantiated",
                "complaint_received_date": "2022-04-07",
            },
        )
        same_facility_old = _insert_substantiated_complaint_for_facility(
            connection,
            facility_number="157806097",
            facility_name="SAME SORT FACILITY",
            complaint_control_number="32-CR-20220101000000",
            complaint_received_date="2022-01-01",
            report_date="2022-01-02",
            source_value_key="finding",
            source_value="Substantiated",
            source_url=_ccld_source_url("157806097", "1"),
        )
        same_facility_new = _insert_substantiated_complaint_for_facility(
            connection,
            facility_number="157806096",
            facility_name="SAME SORT FACILITY",
            complaint_control_number="32-CR-20220201000000",
            complaint_received_date="2022-02-01",
            report_date="2022-02-02",
            source_value_key="finding",
            source_value="Substantiated",
            source_url=_ccld_source_url("157806096", "1"),
        )
        unknown_date_key = _insert_substantiated_complaint_for_facility(
            connection,
            facility_number="157806095",
            facility_name="ZZZ UNKNOWN DATE FACILITY",
            complaint_control_number="32-CR-UNKNOWNDATE",
            complaint_received_date="",
            report_date="",
            source_value_key="finding",
            source_value="Substantiated",
            source_url=_ccld_source_url("157806095", "1"),
        )

        asc_status, _content_type, asc_body = route_response(
            REVIEWER_UI_SUBSTANTIATED_TRIAGE_PATH
            + "?sort=complaint_date_asc&page_size=100",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )
        desc_status, _content_type, desc_body = route_response(
            REVIEWER_UI_SUBSTANTIATED_TRIAGE_PATH
            + "?sort=complaint_date_desc&page_size=100",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )
        facility_status, _content_type, facility_body = route_response(
            REVIEWER_UI_SUBSTANTIATED_TRIAGE_PATH
            + "?sort=facility_desc&page_size=100",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    asc_html = asc_body.decode("utf-8")
    desc_html = desc_body.decode("utf-8")
    facility_html = facility_body.decode("utf-8")

    assert asc_status == 200
    assert desc_status == 200
    assert facility_status == 200
    assert asc_html.index(f"source_record_key={quote(same_facility_old)}") < asc_html.index(
        f"source_record_key={quote(same_facility_new)}"
    )
    assert asc_html.index(f"source_record_key={quote(same_facility_new)}") < asc_html.index(
        f"source_record_key={quote(COMPLAINT_KEY)}"
    )
    assert asc_html.index(f"source_record_key={quote(COMPLAINT_KEY)}") < asc_html.index(
        f"source_record_key={quote(unknown_date_key)}"
    )
    assert desc_html.index(f"source_record_key={quote(COMPLAINT_KEY)}") < desc_html.index(
        f"source_record_key={quote(same_facility_new)}"
    )
    assert desc_html.index(f"source_record_key={quote(same_facility_new)}") < desc_html.index(
        f"source_record_key={quote(same_facility_old)}"
    )
    assert desc_html.index(f"source_record_key={quote(same_facility_old)}") < desc_html.index(
        f"source_record_key={quote(unknown_date_key)}"
    )
    assert facility_html.index(f"source_record_key={quote(same_facility_old)}") < (
        facility_html.index(f"source_record_key={quote(same_facility_new)}")
    )
    assert_no_secret_html(asc_html)
    assert_no_secret_html(desc_html)
    assert_no_secret_html(facility_html)


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
        "source_records": 7,
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
    assert "Facility ID 157806098" in html
    assert "Not provided" in html
    assert "Substantiated" in html
    assert "Date not provided" in html
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
        "source_records": 7,
        "reviewer_created_state": 2,
        "audit_events": 2,
        "reset_reload_planning_metadata": 0,
    }
    assert "Packet preview" in html
    assert "Packet preparation preview" not in html
    assert "local/test" not in html.casefold()
    assert "Open print draft" in html
    assert "Open local/test preparation draft for browser copy or print" not in html
    assert f"{REVIEWER_UI_PACKET_DRAFT_PATH}?facility_number=157806098" in html
    assert "Back to review queue" in html
    assert "Return to same facility/date queue" not in html
    assert "/ccld/records/request?facility_number=157806098" in html
    assert "Send feedback" in html
    assert "Report copy/print preparation concern" not in html
    assert "workflow_area=packet-preview" in html
    assert "Describe+copy%2Fprint+preparation%2C+packet+readiness" in html
    assert "Facility ID" in html
    assert "157806098" in html
    assert "Date range" in html
    assert "08/01/2022 to 08/31/2022" in html
    assert "2022-08-01 to 2022-08-31" not in html
    assert "Records included" in html
    assert "Review cues" in html
    assert "Notes/status saved" in html
    assert "Source record" in html
    assert "Packet readiness" in html
    assert "0 records need review" in html
    assert "1 saved" in html
    assert "1 source available" in html
    assert "Needs date/source review" in html
    primary_start = html.index('<section class="hero-card"')
    primary_end = html.index("Included complaint records", primary_start)
    primary_html = html[primary_start:primary_end]
    assert "Date range: not provided" not in primary_html
    assert "Before copying or printing" in html
    assert "Confirm this is the facility/date range you intended." in html
    assert "Open the CCLD source record if a date or source cue needs review." in html
    assert "Add status or a note if it would help the handoff." in html
    assert "Review included records for missing or confusing information." in html
    assert "Send feedback if something looks wrong or incomplete." in html
    assert "Packet readiness summary" in html
    assert "Records needing date/source review" in html
    assert "Records without saved status/note" in html
    assert "Ready for packet use" in html
    assert "CCLD source availability" in html
    assert "Source available" in html
    assert "Source unavailable" in html
    assert "Notes/status summary" in html
    assert "Saved status" in html
    assert "Saved note" in html
    assert "No status" in html
    assert "No note" in html
    assert "Packet readiness checklist" in html
    checklist_start = html.index("Packet readiness checklist")
    checklist_end = html.index("Copy-ready brief", checklist_start)
    checklist_html = html[checklist_start:checklist_end]
    assert "Loaded records" in checklist_html
    assert "Review cues" in checklist_html
    assert "Source record" in checklist_html
    assert "Saved status/note" in checklist_html
    assert "Follow-up notes" in checklist_html
    assert "Date warnings" in checklist_html
    assert "Ready" in checklist_html
    assert "Needs review" not in checklist_html
    assert "Back to review queue" in checklist_html
    assert "send feedback" in checklist_html
    assert COMPLAINT_KEY not in checklist_html
    assert "source_record_key" not in checklist_html
    assert "source_document_id" not in checklist_html
    assert "import_batch" not in checklist_html
    assert "audit_id" not in checklist_html
    assert "Copy-ready brief" in html
    _assert_collapsed_disclosure(html, "Readiness checks")
    _assert_collapsed_disclosure(html, "Copy-ready brief")
    _assert_collapsed_disclosure(html, "Packet notes")
    assert "manual copy into a review note or handoff draft" in html
    brief_start = html.index("Copy-ready brief")
    brief_end = html.index(">Packet notes</summary>", brief_start)
    brief_html = html[brief_start:brief_end]
    assert "Facility ID: 157806098" in brief_html
    assert "Date range: 08/01/2022 to 08/31/2022" in brief_html
    assert "Records included: 1" in brief_html
    assert "Packet readiness: Ready for packet use" in brief_html
    assert "source: CCLD source available" in brief_html
    assert "This brief is a preparation aid, not a legal report or conclusion." in brief_html
    assert "Review dates and source link when a date or timing cue needs review." in brief_html
    assert COMPLAINT_KEY not in brief_html
    assert "source_record_key" not in brief_html
    assert "source_document_id" not in brief_html
    assert "import_batch" not in brief_html
    assert "audit_id" not in brief_html
    assert "Included complaint records" in html
    assert "32-CR-20220407124448" in html
    assert "Unsubstantiated" in html
    assert "Note added" in html
    assert "Review dates and source link" in html
    assert "CCLD source available" in html
    assert "Facility ID" in html
    assert "Complaint received" in html
    assert "First investigation activity" in html
    assert "Visit" in html
    assert "Report" in html
    assert "Signed" in html
    assert "Source" in html
    assert "Next step" in html
    assert "Open record 32-CR-20220407124448" in html
    assert 'class="result-card work-item packet-preview-record"' in html
    assert (
        '<div class="work-item-actions packet-record-actions" '
        'aria-label="Record actions">'
        in html
    )
    assert ".packet-preview-record" in html
    assert ".packet-record-actions .button" in html
    assert "white-space: normal" in html
    assert ".badge-attention--warning" in html
    assert "background: #FFF1B8" in html
    assert "border-color: #B7791F" in html
    assert "color: #7A3E00" in html
    included_start = html.index("Included complaint records")
    secondary_start = html.index(">Readiness checks</summary>", included_start)
    included_html = html[included_start:secondary_start]
    assert "04/07/2022" in included_html
    assert "08/24/2022" in included_html
    assert "08/26/2022" in included_html
    assert "2022-04-07" not in included_html
    assert "No status" not in included_html
    for removed in (
        "Review-readiness cue",
        "Why included",
        "Reviewer note",
        "Part of the current loaded facility/date review queue",
        "Possible delay indicator",
        "Needs date/source cue review.",
        "Review source/date cue",
        "Finding value shown",
        "Missing traceability values",
        "raw SHA-256",
        "connector metadata",
    ):
        assert removed not in included_html
    assert "Review packet notes" in html
    assert "This packet preview is for preparation." in html
    assert "Loaded record values remain separate from reviewer notes/status." in html
    assert "Open the CCLD source record if a date or source cue needs review." in html
    assert "Add notes/status only when useful." in html
    for removed in (
        "Facility / license",
        "facility/license",
        "source-derived fields",
        "source-derived values",
        "source-derived records",
        "raw artifact",
        "connector metadata",
        "raw SHA-256",
        "source traceability",
        "source-traceability",
        "Needs source check",
        "Operator/runtime details",
        "Technical runtime details",
        "Current review scope: current review session.",
        "No export file is generated by this preview.",
        "does not change complaint records, saved notes/status",
        "Review-readiness cue",
        "Why included",
        "review-created",
        "visible traceability cues",
        "source traceability",
        "source-derived fields",
        "source-derived values",
        "source-derived records",
        "Traceability readiness",
        "raw SHA-256",
        "raw artifact reference",
        "connector metadata",
        "retrieval timestamp",
        "source document/report marker",
    ):
        assert removed.casefold() not in normalized_html.casefold()
    assert "legal priority" not in normalized_html.casefold()
    assert_no_correction_workflow_html(html)
    assert_no_secret_html(html)


def test_reviewer_packet_preview_renders_status_note_readiness_copy() -> None:
    with _seeded_connection() as connection:
        before_counts = _table_counts(connection)

        status, content_type, body = route_response(
            f"{REVIEWER_UI_PACKET_PREVIEW_PATH}?"
            "facility_number=157806098&start_date=2022-08-01&end_date=2022-08-31"
            "&request_context_origin=manual_entry",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

        after_counts = _table_counts(connection)

    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert before_counts == after_counts
    assert "Packet readiness" in html
    assert "needs reviewer status/note" in html
    assert "Records needing date/source review" in html
    assert "add status/note if useful." in html
    assert "Loaded record values remain separate from reviewer notes/status." in html
    for removed in (
        "Facility / license",
        "Needs source check",
        "Review source/date cue",
        "Records needing source check",
        "Source-derived fields remain separate from saved notes/status.",
        "source-derived fields",
    ):
        assert removed.casefold() not in normalized_html.casefold()


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
        "source_records": 7,
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
    assert "CCLD source available means a public CCLD source link" in guidance_html
    assert "unavailable CCLD source links" in normalized_guidance_html
    assert "Correction-readiness before copying or printing" in guidance_html
    assert (
        "capture the possible correction concern in a reviewer-created note or feedback item"
        in guidance_html
    )
    assert (
        "does not change loaded records, alter loaded values"
        in guidance_html
    )
    assert "If copy/print preparation content seems wrong" in guidance_html
    assert "Packet scope" not in guidance_html
    assert "Facility ID" in packet_scope_html
    assert "157806098" in packet_scope_html
    assert "Date range" in packet_scope_html
    assert "08/01/2022 to 08/31/2022" in packet_scope_html
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
    assert "Records needing reviewer attention" in html
    assert "Records needing date/source review" in html
    assert "Records needing reviewer-created status/note attention" in html
    assert "Review-readiness before copying or printing" in html
    assert "Review before copying or printing" in html
    assert "Review before relying on this packet" in normalized_html
    assert "return to the queue, open reviewer detail, or send feedback" in normalized_html
    assert "preparation draft" in html
    assert "Possible correction concerns should remain reviewer-created observations" in html
    assert "future correction workflow is not implemented here" in html
    assert "draft does not submit correction decisions" in html
    assert "Findings represented" in html
    assert "CCLD source availability" in html
    assert "Reviewer-created state included in this draft" in html
    assert "They may point to possible correction concerns" in html
    assert "this draft does not alter loaded record values" in html
    assert "Prioritized records for review" in html
    assert "existing review-next priority order" in html
    assert "Prioritized records available" in html
    assert "Shown first" in html
    assert (
        "Reasons are loaded review cues and reviewer-created "
        "note/status cues only"
        in html
    )
    assert (
        "Finding: Unsubstantiated; reviewer status: Needs follow-up; "
        "1 reviewer-created note(s)"
        in html
    )
    assert "Why prioritized" in html
    assert "Original CCLD source link saved" in html
    assert "Finding value: Unsubstantiated" in html
    assert "Reviewer status: Needs follow-up" in html
    assert "Open reviewer detail for 32-CR-20220407124448" in html
    assert "Prioritized records for review" in html
    assert "- 1. 32-CR-20220407124448; Finding: Unsubstantiated" in html
    prioritized_start = html.index("Prioritized records for review")
    prioritized_end = html.index("Before using this draft", prioritized_start)
    prioritized_html = html[prioritized_start:prioritized_end]
    assert "source_document_id" not in prioritized_html
    assert "import_batch" not in prioritized_html
    assert "audit_id" not in prioritized_html
    assert "Attorney review readiness checklist" in html
    checklist_start = html.index("Attorney review readiness checklist")
    checklist_end = html.index("Copy-ready attorney review brief", checklist_start)
    checklist_html = html[checklist_start:checklist_end]
    normalized_checklist_html = " ".join(checklist_html.split())
    assert "existing loaded context only" in checklist_html
    assert "Loaded complaint records" in checklist_html
    assert "Prioritized records" in checklist_html
    assert "Source record cues" in checklist_html
    assert "Reviewer-created note/status presence" in checklist_html
    assert "Follow-up questions" in checklist_html
    assert "Ready" in checklist_html
    assert "Needs review" not in checklist_html
    assert "Use the suggested follow-up questions in the copy-ready brief" in checklist_html
    assert "No limited-data warning is visible" in checklist_html
    assert COMPLAINT_KEY not in checklist_html
    assert "source_record_key" not in checklist_html
    assert "source_document_id" not in checklist_html
    assert "import_batch" not in checklist_html
    assert "audit_id" not in checklist_html
    assert (
        "review readiness guidance for packet preparation, not a legal sufficiency "
        "decision"
        in normalized_checklist_html
    )
    assert "Copy-ready attorney review brief" in html
    assert "manual copy into an attorney review note or handoff draft" in html
    brief_start = html.index("Copy-ready attorney review brief")
    brief_end = html.index("Before using this draft", brief_start)
    brief_html = html[brief_start:brief_end]
    normalized_brief_html = " ".join(brief_html.split())
    assert "Facility ID: 157806098" in brief_html
    assert "Date range: 08/01/2022 to 08/31/2022" in brief_html
    assert "Loaded record context: 1 complaint record(s)" in brief_html
    assert "Packet readiness cues" in brief_html
    assert "CCLD source cues" in brief_html
    assert "Prioritized records" in brief_html
    assert "Review reasons:" in brief_html
    assert "Suggested follow-up review questions" in brief_html
    assert "Which prioritized records need the CCLD source record checked" in brief_html
    assert "Limited-data note: this brief reflects only records loaded" in brief_html
    assert "Reviewer-created cue: Needs follow-up; 1 reviewer-created note(s)" in brief_html
    assert (
        "legal report, certified export, source-completeness finding, "
        "or legal conclusion"
        in normalized_brief_html
    )
    assert COMPLAINT_KEY not in brief_html
    assert "source_record_key" not in brief_html
    assert "source_document_id" not in brief_html
    assert "import_batch" not in brief_html
    assert "audit_id" not in brief_html
    assert "Included complaint records" in html
    assert "32-CR-20220407124448" in html
    assert "Complaint control number" in html
    assert "Finding" in html
    assert "Key dates" in html
    assert "Review flags" in html
    assert "Reviewer-created status" in html
    assert "Reviewer-created note presence" in html
    assert "Why included" in html
    assert "CCLD source cue" in html
    assert "Reviewer attention cue" in html
    assert "Original CCLD source link saved" in html
    assert "Reviewer-created status/note cue present" in html
    assert "Open record 32-CR-20220407124448" in html
    assert "Before using this draft" in html
    assert "Confirm the facility/date context matches the queue you intended to prepare." in html
    assert "Open reviewer detail for records needing date/source cue review." in html
    assert "Send feedback before copying or printing" in html
    assert "Copyable packet summary" in html
    assert "Attorney Review Packet Draft" in html
    assert "Facility ID: 157806098" in html
    assert "Reviewer-created state summary" in html
    assert "Records ready for preparation review" in html
    assert "Packet readiness means review readiness for manual browser copy or print" in html
    assert "Review-readiness before copy/print" in html
    assert "CCLD source availability" in html
    assert "Loaded record values remain separate from reviewer notes/status." in html
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
        "does not mutate loaded records, reviewer-created state, audit rows"
        in normalized_html
    )
    for removed in (
        "Facility / license",
        "facility/license",
        "source-derived fields",
        "source-derived values",
        "source-derived records",
        "raw artifact",
        "connector metadata",
        "raw SHA-256",
        "source traceability",
        "source-traceability",
        "Review source/date cue",
        "Needs source check",
    ):
        assert removed.casefold() not in normalized_html.casefold()
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
        "source_records": 7,
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
        "source_records": 7,
        "reviewer_created_state": 0,
        "audit_events": 0,
        "reset_reload_planning_metadata": 0,
    }
    assert "Packet preview" in html
    assert "No facility/date packet context was supplied." in html
    assert "Start from Request Records or the Review queue" in html
    assert "build a packet for a specific facility/date range." in html
    assert "Supply a facility/date context to show included records" in html
    assert "Date range: not provided" not in html
    assert_no_secret_html(html)

def test_reviewer_packet_preview_empty_context_has_limited_data_attorney_brief() -> None:
    with _seeded_connection() as connection:
        before_counts = _table_counts(connection)

        status, content_type, body = route_response(
            f"{REVIEWER_UI_PACKET_PREVIEW_PATH}?"
            "facility_number=000000000&start_date=2022-08-01&end_date=2022-08-31"
            "&request_context_origin=manual_entry",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

        after_counts = _table_counts(connection)

    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert before_counts == after_counts == {
        "import_batches": 1,
        "source_records": 7,
        "reviewer_created_state": 0,
        "audit_events": 0,
        "reset_reload_planning_metadata": 0,
    }
    assert "Copy-ready brief" in html
    assert "Packet readiness checklist" in html
    checklist_start = html.index("Packet readiness checklist")
    checklist_end = html.index("Copy-ready brief", checklist_start)
    checklist_html = html[checklist_start:checklist_end]
    assert "Loaded records" in checklist_html
    assert "Review cues" in checklist_html
    assert "Source record" in checklist_html
    assert "Saved status/note" in checklist_html
    assert "Follow-up notes" in checklist_html
    assert "Date warnings" in checklist_html
    assert "Needs review" in checklist_html
    assert "Back to review queue" in checklist_html
    assert "send feedback" in checklist_html
    assert COMPLAINT_KEY not in checklist_html
    assert "source_record_key" not in checklist_html
    assert "source_document_id" not in checklist_html
    assert "import_batch" not in checklist_html
    assert "audit_id" not in checklist_html
    brief_start = html.index("Copy-ready brief")
    brief_end = html.index(">Packet notes</summary>", brief_start)
    brief_html = html[brief_start:brief_end]
    assert "Records included: 0" in brief_html
    assert "No complaint records match this packet context." in brief_html
    assert "Review before use" in brief_html
    assert COMPLAINT_KEY not in brief_html
    assert "source_record_key" not in brief_html
    assert "source_document_id" not in brief_html
    assert "import_batch" not in brief_html
    assert "audit_id" not in brief_html
    for removed in (
        "Operator/runtime details",
        "Technical runtime details",
        "Current review scope: current review session.",
        "No export file is generated by this preview.",
        "reviewer-created",
        "review-created",
        "source traceability",
        "raw SHA-256",
        "raw artifact reference",
        "connector metadata",
        "retrieval timestamp",
        "source document/report marker",
    ):
        assert removed.casefold() not in " ".join(html.split()).casefold()
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
    assert "1 note" in html
    assert "Note added" in html
    assert "Facility case brief" not in html
    assert "Reviewer status" in html
    assert "Queue status summary" not in html
    assert "reviewer-created" not in " ".join(html.split()).casefold()
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
    assert "No loaded complaint records match no-match." in " ".join(empty_html.split())
    assert "No matching complaint records" in empty_html
    assert "Showing 0 of 0 matching complaint records." in empty_html
    assert "Clear search and show all complaint records" in empty_html
    assert "Return to reviewer home" not in empty_html


def test_reviewer_ui_landing_uses_plain_missing_values_and_source_cues() -> None:
    with _seeded_connection() as connection:
        original_values = dict(
            connection.execute(
                select(hosted_source_derived_records.c.original_values).where(
                    hosted_source_derived_records.c.source_record_key == COMPLAINT_KEY
                )
            ).scalar_one()
        )
        original_values.update(
            finding=None,
            complaint_received_date=None,
            visit_date=None,
            report_date=None,
        )
        connection.execute(
            update(hosted_source_derived_records)
            .where(hosted_source_derived_records.c.source_record_key == COMPLAINT_KEY)
            .values(original_values=original_values, source_url="unknown")
        )
        status, content_type, body = route_response(
            "/reviewer",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    html = body.decode("utf-8")
    record_start = html.index('class="review-worklist-row is-suggested"')
    record_html = html[record_start : html.index("</article>", record_start)]

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Not provided" in record_html
    assert record_html.count("Date not provided") == 3
    assert "Source not available" in record_html
    assert ">unknown<" not in record_html
    assert "raw_path" not in record_html
    assert "raw_sha256" not in record_html
    assert_no_secret_html(html)


def test_reviewer_ui_landing_displays_each_primary_review_flag_once_as_a_badge() -> None:
    with _seeded_connection() as connection:
        original_values = dict(
            connection.execute(
                select(hosted_source_derived_records.c.original_values).where(
                    hosted_source_derived_records.c.source_record_key == COMPLAINT_KEY
                )
            ).scalar_one()
        )
        original_values["review_delay_over_120_days"] = True
        connection.execute(
            update(hosted_source_derived_records)
            .where(hosted_source_derived_records.c.source_record_key == COMPLAINT_KEY)
            .values(original_values=original_values)
        )
        status, _content_type, body = route_response(
            "/reviewer",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    html = body.decode("utf-8")
    record_start = html.index('class="review-worklist-row is-suggested"')
    record_html = html[record_start : html.index("</article>", record_start)]

    assert status == 200
    assert record_html.count("120+ day gap") == 1
    assert 'class="review-chip badge-attention badge-attention--warning"' in record_html
    assert "Possible delay indicator" not in record_html
    assert_no_secret_html(html)

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


def test_reviewer_ui_detail_shows_attorney_tier_and_hides_support_details() -> None:
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
    assert parser.text_for("h1") == "Complaint overview"
    assert "Source-traceable complaint review." not in html
    assert "Signed in as Local Test Reviewer" not in html
    assert "Return to review queue" in html
    assert "Complaint overview" in html
    assert "Complaint 32-CR-20220407124448" in parser.text_for("main")
    assert (
        "Complaint 32-CR-20220407124448 &middot; "
        in html
    )
    assert ">Finding<" in html
    assert ">Unsubstantiated<" in html
    assert "Facility 157806098" not in parser.text_for("main")
    assert "Complaint/control number" in html
    assert "A. MIRIAM JAMISON CHILDREN&#x27;S CENTER" in html
    assert "Facility ID" in html
    assert "Facility/license" not in html
    assert "Facility/license number" not in html
    assert "facility/license number" not in html
    assert parser.text_for("main").count("157806098") == 1
    assert 'class="top-fact-strip"' in html
    assert 'class="compact-fact compact-fact--license"' in html
    assert 'class="compact-fact compact-fact--name"' in html
    assert 'class="compact-fact compact-fact--type"' in html
    assert 'class="compact-fact compact-fact--status"' in html
    assert 'class="compact-fact compact-fact--county"' in html
    assert "grid-template-columns: minmax(7.5rem, 0.8fr) minmax(18rem, 2.3fr)" in html
    assert "border-right: 1px solid var(--line-soft);" in html
    assert "-webkit-line-clamp: 2" in html
    facts_start = html.index('class="top-fact-strip"')
    facts_end = html.index("</dl>", facts_start)
    facts_html = html[facts_start:facts_end]
    assert "review-chip" not in facts_html
    assert "badge-attention" not in facts_html
    assert "Facility ID" in facts_html
    assert "Finding/status" not in html
    assert (
        'class="finding-badge finding-badge--unsubstantiated finding-badge--status"'
        in html
    )
    assert 'class="finding-badge__marker finding-badge__marker--unsubstantiated"' in html
    assert 'class="copy-icon-button"' in html
    assert 'aria-label="Copy complaint/control number"' in html
    assert 'aria-label="Copy Facility ID"' in html
    assert 'data-copy-feedback="Copied"' in html
    assert 'data-copy-status hidden aria-live="polite" aria-atomic="true"' in html
    assert 'aria-label="Copy complaint number"' not in html
    assert 'aria-label="Copy facility number"' not in html
    assert 'aria-label="Copy Finding/status"' not in html
    assert 'aria-label="Copy Facility name"' not in html
    assert 'aria-label="Copy Facility type"' not in html
    assert 'aria-label="Copy Facility status"' not in html
    assert 'aria-label="Copy County"' not in html
    assert 'aria-label="Copy Source URL"' not in html
    assert "navigator.clipboard.writeText" in html
    assert "showCopyStatus(button, 'Copied')" in html
    assert "status.hidden = true" in html
    assert "2000" in html
    assert "04/07/2022" in html
    assert "08/24/2022" in html
    assert "2022-04-07" not in parser.text_for("main")
    assert "2022-08-24" not in parser.text_for("main")

    assert "<aside" not in html
    assert "reviewer-detail-top" not in html
    assert "reviewer-panel-context" not in html
    ordered_sections = [
        "Complaint overview",
        "Why this may need closer review",
        "Source narrative",
        "Key dates",
        "Status and note",
        "Allegations and findings",
    ]
    previous_index = -1
    for section in ordered_sections:
        section_index = html.index(section)
        assert section_index > previous_index
        previous_index = section_index
    assert f'action="{REVIEWER_UI_NOTE_PATH}"' in html
    assert f'action="{REVIEWER_UI_STATUS_PATH}"' in html
    assert "name=\"source_record_key\"" in html
    assert "Save note" in html
    assert "Save status" in html

    assert "CCLD source available" in html
    review_cues_start = html.index('class="overview-review-cues"')
    review_cues_end = html.index('class="overview-source-narrative"', review_cues_start)
    review_cues_html = html[review_cues_start:review_cues_end]
    assert "CCLD source available" not in review_cues_html
    assert "Open CCLD source record" in html
    assert "Return to review queue" in html
    assert "Return to facility queue" not in html
    assert "Date range: not provided" not in html
    assert "Open next flagged record" not in html
    assert html.index("Open CCLD source record") < html.index("Status and note")
    review_panel_start = html.index('id="review-actions-heading"')
    review_panel_end = html.index('class="overview-tertiary-actions"', review_panel_start)
    review_panel_html = html[review_panel_start:review_panel_end]
    assert "Status and note" in review_panel_html
    assert "Current status" in review_panel_html
    assert "Current note" in review_panel_html
    assert "Review status" in review_panel_html
    assert "Reviewer note" in review_panel_html
    assert "No status selected" in review_panel_html
    assert (
        '<option value="" disabled selected="selected">No status selected</option>'
        in review_panel_html
    )
    assert '<h3 id="status-form-heading">Status</h3>' not in review_panel_html
    assert '<h3 id="note-form-heading">Note</h3>' not in review_panel_html
    assert "Save status" in review_panel_html
    assert "Save note" in review_panel_html
    assert "Status helps track review progress." in review_panel_html
    assert "Notes do not change the complaint record." in review_panel_html
    assert "Return to review queue" not in review_panel_html
    assert "Return to facility queue" not in review_panel_html
    assert "Open next flagged record" not in review_panel_html
    assert "Cautious reviewer-created note guidance" not in review_panel_html
    assert "Field-note guidance" not in review_panel_html
    assert "Keep it cautious" not in review_panel_html
    assert "Record what you checked" not in review_panel_html
    assert "Do not write that abuse, neglect, harm" not in review_panel_html
    assert "submit the request again" not in review_panel_html

    assert "Save status or a note only when it helps this review" not in html
    assert "Source-derived fields stay unchanged." not in html

    assert "Why this may need closer review" in html
    assert "Review the badge list above as screening cues only" not in html
    assert "No status" in html
    assert "No note" in html
    assert 'class="review-chip badge-info badge-info--status"' in html
    assert 'class="review-chip badge-info badge-info--note"' in html
    assert 'class="review-chip__marker review-chip__marker--status"' in html
    assert 'class="review-chip__marker review-chip__marker--note"' in html
    assert 'class="review-chip badge-attention badge-info--status"' not in html
    assert 'class="review-chip badge-attention badge-info--note"' not in html
    assert "No source warning badges" not in html
    assert "Check source" not in html
    assert "Missing first activity" not in html
    assert "Possible delay indicator: over" not in html
    assert "Needs source check: first activity date missing locally" not in html
    assert "Source-derived complaint received date" not in html
    assert "Source-derived report date when loaded" not in html
    assert 'id="reviewer-state-heading"' not in html

    assert "Facility clients are being mistreated while in care." in html
    assert "Facility staff do not provide adequate supervision" in html
    assert 'aria-label="Copy source narrative"' in html
    assert "No citation, deficiency, or Plan of Correction cue is loaded" not in html
    for unsafe_phrase in (
        "proves abuse",
        "proves neglect",
        "proves liability",
        "proves rights deprivation",
        "proves source coverage is complete",
        "decides source coverage is complete",
        "verified delay",
        "verified severity finding",
    ):
        assert unsafe_phrase not in normalized_html.casefold()

    assert '<dfn class="inline-glossary-term" tabindex="0" role="term"' in html
    assert 'aria-description="The outcome or status shown in the public complaint record."' in html
    assert 'data-definition="The outcome or status shown in the public complaint record."' in html
    assert 'class="inline-glossary-definition" role="tooltip"' not in html
    assert ".inline-glossary-term" in html
    assert "border-bottom: 1px dotted currentColor" in html
    assert "content: attr(data-definition)" in html
    assert "The outcome or status shown in the public complaint record." in html
    assert (
        "A source-reported finding that the allegation was not substantiated "
        "in the public complaint record."
        in html
    )
    assert "The public licensing identifier used to find the facility in CCLD records." in html
    assert (
        "The outcome or status shown in the public complaint record."
        not in parser.text_for("main")
    )
    assert (
        "A source-reported finding that the allegation was not substantiated "
        "in the public complaint record."
        not in parser.text_for("main")
    )
    assert (
        "The public licensing identifier used to find the facility in CCLD records."
        not in parser.text_for("main")
    )
    assert "The complaint received date shown in loaded records." not in html
    assert "The visit date shown in loaded records when available." not in html
    assert "The loaded report date. If a proxy flag is present" not in html
    assert "The date signed shown in loaded records when available." not in html
    assert "Complaint received" in html
    assert "Visit" in html
    assert "Report" in html
    assert "Signed" in html
    assert 'class="rt-timeline rt-timeline--linear"' in html
    assert 'class="rt-timeline__line" aria-hidden="true"' in html
    assert (
        'class="timeline-list timeline-list-linear rt-timeline__milestones" '
        'aria-label="Ordered complaint milestones"'
        in html
    )
    expected_timeline_markers = (
        "received",
        "activity",
        "visit",
        "report",
        "signed",
    )
    for marker in expected_timeline_markers:
        assert (
            f'class="timeline-marker timeline-marker--{marker} '
            f'rt-timeline__marker rt-timeline__marker--{marker}"'
            in html
        )
    assert 'class="rt-timeline__date"' in html
    assert (
        'class="timing-summary"'
        ' aria-label="Stored elapsed days between complaint milestones"'
        in html
    )
    assert "Elapsed days" in html
    assert "Complaint received to first investigation activity" in html
    assert "Complaint received to visit" in html
    assert "Complaint received to report" in html
    assert "Report to signed" in html
    assert ">7</dd>" in html
    assert html.count(">139</dd>") == 2
    assert ">2</dd>" in html
    assert "days_received_to_" not in html
    assert "days_report_to_signed" not in html
    assert ".rt-timeline.has-gap .rt-timeline__line::after" in html
    assert "left: 25%;" in html
    assert "top: calc(var(--timeline-line-top) - 0.68rem);" in html
    assert "transform: translateX(-50%);" in html
    assert "width: max-content;" in html
    assert "border-radius: 5px;" in html
    assert "top: 0;\n      width: 25%;" not in html
    assert "top: calc(var(--timeline-line-top) + 3.55rem);" not in html
    assert (
        "top: calc(var(--timeline-line-top) - (var(--timeline-marker-size) / 2)"
        not in html
    )
    timeline_start = html.index('class="overview-timeline"')
    timeline_end = html.index("</section>", timeline_start)
    timeline_html = html[timeline_start:timeline_end]
    received_start = timeline_html.index("timeline-item--received")
    received_end = timeline_html.index("</li>", received_start)
    received_item_html = timeline_html[received_start:received_end]
    assert "120+ day gap" not in received_item_html
    assert timeline_html.index('class="rt-timeline__line"') < timeline_html.index(
        "Complaint received"
    )
    assert "right: 10%;" in html
    assert "grid-template-columns: repeat(5, minmax(0, 1fr));" in html
    assert "width: 33.333%;" in html
    assert (
        'aria-label="Gap between complaint received and visit or investigation activity"'
        not in html
    )
    assert "A value extracted from public source records" not in html
    assert "Local review state added by a tester or reviewer" not in html
    assert "Key terms for this record" not in html

    for removed in (
        "Source traceability",
        "Raw SHA-256",
        "Connector",
        "Selected complaint source traceability fields",
        "Review flags and source checks",
        "Source-derived value checks",
        "How to read this record",
        "Full source-derived fields",
        "Technical and operator details",
        "Related facility activity",
        "View related source bundle details",
        "Source record key",
        "Stable source ID",
        "Source document ID",
        "Safe context shown",
        "Same seeded bundle",
        "feedback item for this record",
        "Request origin",
        "Date range: not provided",
        "Loaded field note",
        "Loaded allegation row",
        "Loaded allegation and finding values",
        "Allegation text or loaded summary",
        "Extraction confidence",
        "Complaint summary",
        "Source timeline",
    ):
        assert removed not in html
    assert "0.95" not in parser.text_for("main")
    assert "Finding</th>" in html
    assert "Allegation</th>" in html
    assert "ccld:document:" not in html
    assert "source_document:" not in html
    assert "verified delay" not in normalized_html.casefold()
    assert "proof of delayed investigation" not in normalized_html.casefold()
    assert "source is complete" not in normalized_html.casefold()
    assert "verified abuse" not in normalized_html.casefold()
    assert_no_correction_workflow_html(html)
    assert_no_secret_html(html)


def test_complaint_reviewer_field_inventory_dispositions_are_explicit() -> None:
    inventory = reviewer_ui.COMPLAINT_REVIEWER_FIELD_INVENTORY
    required_fields = {
        "complaint_received_date",
        "first_investigation_activity_date",
        "visit_date",
        "report_date",
        "date_signed",
        "days_received_to_first_activity",
        "days_received_to_visit",
        "days_received_to_report",
        "days_report_to_signed",
        "finding",
        "complaint_type_or_category",
        "substantiation_or_equivalent_finding",
        "serious_topic_cues",
        "facility_identity",
        "complaint_control_number",
        "source_availability",
        "reviewer_created_status",
        "reviewer_created_notes",
    }
    allowed_dispositions = {
        "primary reviewer fact",
        "secondary/collapsible reviewer fact",
        "export-only fact",
        "support/operator-only fact",
        "intentionally excluded",
    }

    assert required_fields <= inventory.keys()
    assert {disposition for disposition, _reason in inventory.values()} <= (
        allowed_dispositions
    )
    assert all(reason.strip() for _disposition, reason in inventory.values())
    assert inventory["raw_hash_connector_and_import_metadata"][0] == (
        "support/operator-only fact"
    )
    assert inventory["raw_source_body"][0] == "intentionally excluded"


@pytest.mark.parametrize(
    ("stored_value", "expected_markup"),
    (
        (0, "<dd>0</dd>"),
        (None, "Not provided"),
        ("", "Not provided"),
        ("not-a-number", "Invalid source value"),
        ("unavailable", "Not available from source"),
    ),
)
def test_reviewer_ui_detail_duration_uses_governed_presentation_states(
    stored_value: object,
    expected_markup: str,
) -> None:
    with _seeded_connection() as connection:
        _set_source_record_original_values(
            connection,
            COMPLAINT_KEY,
            {"days_received_to_visit": stored_value},
        )
        status, _content_type, body = route_response(
            f"{REVIEWER_UI_DETAIL_PATH}?source_record_key={quote(COMPLAINT_KEY)}",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    html = body.decode("utf-8")
    timing_start = html.index('class="overview-timeline"')
    timing_end = html.index("</section>", timing_start)
    timing_html = html[timing_start:timing_end]

    assert status == 200
    assert expected_markup in timing_html
    assert "days_received_to_visit" not in timing_html
    assert "not-a-number" not in timing_html
    if stored_value in {None, "", "not-a-number", "unavailable"}:
        assert 'class="inline-glossary-term"' in timing_html
        assert 'tabindex="0"' in timing_html


def test_reviewer_ui_detail_preserves_duration_when_milestone_date_is_missing() -> None:
    with _seeded_connection() as connection:
        _set_source_record_original_values(
            connection,
            COMPLAINT_KEY,
            {
                "report_date": None,
                "days_received_to_report": 139,
            },
        )
        status, _content_type, body = route_response(
            f"{REVIEWER_UI_DETAIL_PATH}?source_record_key={quote(COMPLAINT_KEY)}",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    html = body.decode("utf-8")
    timing_start = html.index('class="overview-timeline"')
    timing_end = html.index("</section>", timing_start)
    timing_html = html[timing_start:timing_end]

    assert status == 200
    assert "Date not provided" in timing_html
    assert "Complaint received to report" in timing_html
    assert ">139</dd>" in timing_html
    assert "Timing mismatch" not in timing_html


def test_reviewer_ui_detail_surfaces_stored_duration_date_conflict_once() -> None:
    with _seeded_connection() as connection:
        _set_source_record_original_values(
            connection,
            COMPLAINT_KEY,
            {
                "days_received_to_report": 1,
                "review_delay_over_120_days": True,
            },
        )
        status, _content_type, body = route_response(
            f"{REVIEWER_UI_DETAIL_PATH}?source_record_key={quote(COMPLAINT_KEY)}",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    html = body.decode("utf-8")
    timing_start = html.index('class="overview-timeline"')
    timing_end = html.index("</section>", timing_start)
    timing_html = html[timing_start:timing_end]

    assert status == 200
    assert "04/07/2022" in timing_html
    assert "08/24/2022" in timing_html
    assert "Complaint received to report" in timing_html
    assert ">1</dd>" in timing_html
    assert "Timing mismatch:" in timing_html
    assert "stored complaint received to report interval does not match" in timing_html
    assert 'role="note"' in timing_html
    assert "days_received_to_report" not in timing_html
    assert "120+ day gap" not in timing_html
    assert html.count("120+ day gap") == 1


@pytest.mark.parametrize(
    ("finding", "expected_class"),
    (
        ("Unsubstantiated", "finding-badge finding-badge--unsubstantiated finding-badge--status"),
        ("Substantiated", "finding-badge finding-badge--substantiated finding-badge--status"),
        ("Inconclusive", "finding-badge finding-badge--inconclusive finding-badge--status"),
    ),
)
def test_reviewer_ui_detail_renders_finding_badge_variants(
    finding: str,
    expected_class: str,
) -> None:
    with _seeded_connection() as connection:
        complaint_row = connection.execute(
            select(hosted_source_derived_records.c.original_values).where(
                hosted_source_derived_records.c.source_record_key == COMPLAINT_KEY
            )
        ).scalar_one()
        updated_values = dict(complaint_row)
        updated_values["finding"] = finding
        connection.execute(
            update(hosted_source_derived_records)
            .where(hosted_source_derived_records.c.source_record_key == COMPLAINT_KEY)
            .values(original_values=updated_values)
        )
        status, _content_type, body = route_response(
            f"{REVIEWER_UI_DETAIL_PATH}?source_record_key={quote(COMPLAINT_KEY)}",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    html = body.decode("utf-8")

    assert status == 200
    assert f'class="{expected_class}"' in html
    assert f">{finding}<" in html
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
    assert "Source narrative" in html
    assert "Show full source narrative" in html
    assert "Full source-derived fields" not in html
    _assert_collapsed_disclosure(html, "Show full source narrative")
    assert_no_secret_html(html)


@pytest.mark.parametrize(
    "representative",
    (
        {
            "facility_number": "107207198",
            "facility_name": "Representative Foster Family Agency",
            "facility_type": "Foster Family Agency",
            "status": "Licensed",
            "county": "Los Angeles",
            "complaint_control_number": "24-CR-20260508083927",
            "complaint_key": "complaint:ccld-complaint-24-CR-20260508083927",
            "source_document_id": "ccld-107207198-inx-25",
            "report_index": "25",
            "finding": "Substantiated",
            "allegation_text": "Facility staff did not follow the written placement plan.",
            "narrative": (
                "The public report states the allegation was investigated and "
                "substantiated."
            ),
            "received_date": "2026-05-08",
            "visit_date": "2026-05-15",
            "report_date": "2026-05-30",
            "signed_date": "2026-06-02",
        },
        {
            "facility_number": "425802141",
            "facility_name": "Representative Short Term Residential Therapeutic Program",
            "facility_type": "Short Term Residential Therapeutic Program",
            "status": "Licensed",
            "county": "Santa Barbara",
            "complaint_control_number": "31-CR-20240425094018",
            "complaint_key": "complaint:ccld-complaint-31-CR-20240425094018",
            "source_document_id": "ccld-425802141-inx-33",
            "report_index": "33",
            "finding": "Unsubstantiated",
            "allegation_text": "Facility staff did not provide adequate supervision.",
            "narrative": "The investigation finding states the allegation was unsubstantiated.",
            "received_date": "2024-04-25",
            "visit_date": "2024-05-02",
            "report_date": "2024-05-21",
            "signed_date": "2024-05-23",
        },
    ),
)
def test_reviewer_ui_detail_renders_representative_live_public_related_facts(
    representative: dict[str, str],
) -> None:
    with _seeded_connection() as connection:
        _insert_representative_live_public_retrieval_batch(connection, representative)
        status, content_type, body = route_response(
            f"{REVIEWER_UI_DETAIL_PATH}?source_record_key={quote(representative['complaint_key'])}",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    html = body.decode("utf-8")
    parser = ElementTextByTagParser()
    parser.feed(html)
    main_text = parser.text_for("main")
    source_url = _ccld_source_url(
        representative["facility_number"],
        representative["report_index"],
    )

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert representative["facility_number"] in main_text
    assert representative["facility_name"] in html
    assert representative["facility_type"] in html
    assert representative["status"] in html
    assert representative["county"] in html
    assert representative["allegation_text"] in html
    assert representative["narrative"] in html
    assert "Allegation details are not loaded for this complaint record." not in html
    assert "No source narrative excerpt is loaded for this complaint record." not in html
    assert f'href="{source_url.replace("&", "&amp;")}"' in html
    assert _mmddyyyy(representative["received_date"]) in main_text
    assert representative["received_date"] not in main_text
    fact_strip_start = html.index('class="top-fact-strip"')
    fact_strip_html = html[
        fact_strip_start : html.index("</dl>", fact_strip_start)
    ]
    assert "unknown" not in fact_strip_html
    assert_no_secret_html(html)


def test_reviewer_ui_detail_blocks_representative_live_public_scope_mismatch() -> None:
    representative = {
        "facility_number": "107207198",
        "facility_name": "Representative Foster Family Agency",
        "facility_type": "Foster Family Agency",
        "status": "Licensed",
        "county": "Los Angeles",
        "complaint_control_number": "24-CR-20260508083927",
        "complaint_key": "complaint:ccld-complaint-24-CR-20260508083927",
        "source_document_id": "ccld-107207198-inx-25",
        "report_index": "25",
        "finding": "Substantiated",
        "allegation_text": "Facility staff did not follow the written placement plan.",
        "narrative": (
            "The public report states the allegation was investigated and "
            "substantiated."
        ),
        "received_date": "2026-05-08",
        "visit_date": "2026-05-15",
        "report_date": "2026-05-30",
        "signed_date": "2026-06-02",
    }
    with _seeded_connection() as connection:
        _insert_representative_live_public_retrieval_batch(connection, representative)
        status, _content_type, body = route_response(
            f"{REVIEWER_UI_DETAIL_PATH}?source_record_key={quote(representative['complaint_key'])}",
            reviewer_ui_context=reviewer_ui_context_for_connection(
                connection,
                actor=_actor(roles=("tester_reviewer",), scopes=(OTHER_SCOPE,)),
                scope=OTHER_SCOPE,
            ),
        )

    html = body.decode("utf-8")

    assert status == 403
    assert "outside the authorized scope" in html
    assert representative["facility_name"] not in html
    assert representative["allegation_text"] not in html
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
    assert "Complaint overview" in html
    assert "Return to review queue" in html
    assert "Return to facility queue" not in html
    assert "Global complaint exports" not in html
    assert "triage and navigate records" not in normalized_html
    assert_no_secret_html(html)

    csv_text = csv_body.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = list(reader)

    assert csv_status == 200
    assert csv_content_type == "text/csv; charset=utf-8"
    _assert_aggregate_export_fieldnames(reader.fieldnames)
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
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = list(reader)

    assert status == 200
    assert content_type == "text/csv; charset=utf-8"
    assert before_source_rows == after_source_rows
    assert before_counts == after_counts == {
        "import_batches": 1,
        "source_records": 7,
        "reviewer_created_state": 2,
        "audit_events": 2,
        "reset_reload_planning_metadata": 0,
    }
    assert rows
    assert reader.fieldnames is not None
    assert len(reader.fieldnames) == len(set(reader.fieldnames))
    assert reader.fieldnames.count("facility_number") == 1
    assert reader.fieldnames.count("facility_name") == 1
    assert "FAC_DO_DESC" not in reader.fieldnames
    assert "RES_STREET_ADDR" not in reader.fieldnames
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


def test_reviewer_landing_uses_one_bounded_governed_bundle_without_offset_paging(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert not hasattr(reviewer_ui, "_all_source_derived_records")

    def fail_api_pagination(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("reviewer landing must not enumerate the source API")

    monkeypatch.setattr(
        reviewer_ui,
        "route_source_derived_api_response",
        fail_api_pagination,
    )
    statements: list[str] = []
    with _seeded_connection() as connection:
        _insert_matrix_complaint_copies(connection, count=125)

        def capture_statement(
            _connection: object,
            _cursor: object,
            statement: str,
            _parameters: object,
            _context: object,
            _executemany: bool,
        ) -> None:
            if "hosted_source_derived_records" in statement:
                statements.append(statement)

        event.listen(connection, "before_cursor_execute", capture_statement)
        try:
            status, content_type, body = route_response(
                REVIEWER_UI_PREFIX,
                reviewer_ui_context=reviewer_ui_context_for_connection(connection),
            )
        finally:
            event.remove(connection, "before_cursor_execute", capture_statement)

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    html = body.decode("utf-8")
    assert "32-CR-20220407124448" in html
    assert "Showing 100 of 126 matching complaint records." in html
    assert "The first 100 records are shown within the current 100-record limit." in html
    assert html.count('class="review-worklist-row') == 100
    assert "<dt>Eligible records</dt><dd>126</dd>" in html
    assert '<span class="status-badge">Truncated</span>' in html
    assert len(statements) == 3
    assert all("OFFSET 100" not in statement.upper() for statement in statements)
    assert all("OFFSET 200" not in statement.upper() for statement in statements)
    assert any(" LIMIT " in statement.upper() for statement in statements)


def test_matrix_export_filters_before_materialization_and_exports_more_than_100_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_api_pagination(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("matrix export must not enumerate the source API")

    monkeypatch.setattr(
        reviewer_ui,
        "route_source_derived_api_response",
        fail_api_pagination,
    )
    statements: list[tuple[str, object]] = []
    with _seeded_connection() as connection:
        _insert_matrix_complaint_copies(connection, count=105)

        def capture_statement(
            _connection: object,
            _cursor: object,
            statement: str,
            parameters: object,
            _context: object,
            _executemany: bool,
        ) -> None:
            if "hosted_source_derived_records" in statement:
                statements.append((statement, parameters))

        event.listen(connection, "before_cursor_execute", capture_statement)
        try:
            path = (
                f"{REVIEWER_UI_MATRIX_EXPORT_PATH}?facility_number=157806098"
                "&start_date=2022-08-01&end_date=2022-08-31"
                "&request_context_origin=manual_entry"
            )
            first = route_response(
                path,
                reviewer_ui_context=reviewer_ui_context_for_connection(connection),
            )
            second = route_response(
                path,
                reviewer_ui_context=reviewer_ui_context_for_connection(connection),
            )
        finally:
            event.remove(connection, "before_cursor_execute", capture_statement)

    first_status, first_content_type, first_body = first
    second_status, second_content_type, second_body = second
    rows = list(csv.DictReader(io.StringIO(first_body.decode("utf-8-sig"))))
    assert first_status == second_status == 200
    assert first_content_type == second_content_type == "text/csv; charset=utf-8"
    assert first_body == second_body
    assert len(rows) == 106
    assert len({row["source_record_key"] for row in rows}) == 106
    assert all(row["facility_number"] == "157806098" for row in rows)
    assert statements
    assert all(" OFFSET " not in statement.upper() for statement, _ in statements)
    assert any("2022-08-01" in _flatten_sql_parameters(parameters) for _, parameters in statements)
    assert any("2022-08-31" in _flatten_sql_parameters(parameters) for _, parameters in statements)
    assert any("157806098" in _flatten_sql_parameters(parameters) for _, parameters in statements)


def test_matrix_export_database_failure_returns_no_partial_csv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sqlalchemy.exc import OperationalError

    def fail_read(*_args: object, **_kwargs: object) -> None:
        raise OperationalError("SELECT", {}, Exception("database unavailable"))

    monkeypatch.setattr(
        reviewer_ui,
        "list_authorized_source_derived_complaint_bundle",
        fail_read,
    )
    with _seeded_connection() as connection:
        status, content_type, body = route_response(
            REVIEWER_UI_MATRIX_EXPORT_PATH,
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    assert status == 503
    assert content_type == "text/html; charset=utf-8"
    assert not body.startswith(b"\xef\xbb\xbf")
    assert b"source_derived_read_failed" not in body


def test_managed_reviewer_reads_complete_transactions_after_success_and_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sqlalchemy.exc import OperationalError

    with _seeded_connection() as connection:
        context = reviewer_ui_context_for_connection(
            connection,
            manage_read_transactions=True,
        )
        success_status, _content_type, _body = route_response(
            REVIEWER_UI_PREFIX,
            reviewer_ui_context=context,
        )
        assert success_status == 200
        assert connection.in_transaction() is False

        connection.begin()

        def fail_read(*_args: object, **_kwargs: object) -> None:
            raise OperationalError("SELECT", {}, Exception("database unavailable"))

        monkeypatch.setattr(
            reviewer_ui,
            "list_authorized_source_derived_complaint_bundle",
            fail_read,
        )
        failure_status, _content_type, _body = route_response(
            REVIEWER_UI_PREFIX,
            reviewer_ui_context=context,
        )
        assert failure_status == 503
        assert connection.in_transaction() is False

def test_reviewer_ui_substantiated_export_returns_excel_ready_csv_without_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_whole_corpus_helper(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("substantiated export must not enumerate the whole corpus")

    monkeypatch.setattr(
        reviewer_ui,
        "_complaint_bundle_response",
        fail_whole_corpus_helper,
    )

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
        "source_records": 7,
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
        "source_records": 7,
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
        assert record["Facility Name"] == "Not applicable"
        assert record["Facility/License Number"] == "Not applicable"
        assert record["Finding/Status"] == "Not applicable"
        assert record["Complaint Control Number"] == "Not applicable"
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
        "source_records": 7,
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
        assert record["Facility Name"] == "Not applicable"
        assert record["Facility/License Number"] == "Not applicable"
        assert record["Finding/Status"] == "Not applicable"
        assert record["Complaint Control Number"] == "Not applicable"
    assert "Date query export note" not in csv_text
    assert "raw_path" not in csv_text
    assert "C:\\" not in csv_text
    assert "provider_subject" not in csv_text
    assert "token" not in csv_text.casefold()

@pytest.mark.parametrize(
    ("finding_value", "allegation_category", "expect_cue"),
    (
        ("Unsubstantiated", "staff misconduct concern", "Possible serious allegation topic"),
        ("Unsubstantiated", "licensing paperwork", "No serious review cue"),
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
        "source_records": 7,
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
    _assert_aggregate_export_fieldnames(reader.fieldnames)
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
        "source_records": 7,
        "reviewer_created_state": 2,
        "audit_events": 2,
        "reset_reload_planning_metadata": 0,
    }
    _assert_aggregate_export_fieldnames(reader.fieldnames)
    assert rows
    [record] = rows
    if expect_row:
        assert record["Facility Name"] == "A. MIRIAM JAMISON CHILDREN'S CENTER"
        assert record["Facility/License Number"] == "157806098"
        assert record["Complaint Received Date"] == "2022-04-07"
        assert record["Finding/Status"] == "Substantiated"
    else:
        assert record["Facility Name"] == "Not applicable"
        assert record["Facility/License Number"] == "Not applicable"
        assert record["Complaint Received Date"] == "Not applicable"
        assert record["Finding/Status"] == "Not applicable"
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
        "source_records": 7,
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
        "source_records": 7,
        "reviewer_created_state": 0,
        "audit_events": 0,
        "reset_reload_planning_metadata": 0,
    }
    assert "Complaint overview" in html
    assert "Key dates" in html
    assert "Raw artifact preservation" not in html
    assert "Missing: raw artifact reference" not in html
    assert "Show field-level source details" not in html
    assert "Source-derived value checks" not in html
    assert "Review flags and source checks" not in html
    assert "Field-note guidance" not in html
    assert "Raw SHA-256" not in html
    assert "Connector" not in html
    assert "raw paths are not shown in the browser" not in html
    assert "missing-field flag is true" not in normalized_html
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
    assert "Complaint overview" in html
    assert "Facility ID" in html
    assert "Facility/license number" not in html
    assert "157806098" in html
    assert "Date range" not in html
    assert "01/01/2026 to 01/31/2026" not in html
    assert "Request origin" not in html
    assert "return_facility_number" in html
    assert "return_start_date" in html
    assert "return_end_date" in html
    assert "Return to facility queue" not in html
    assert "Return to review queue" in html
    assert "Review packet readiness before copying or printing" not in html
    assert "Open print draft" not in html
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
    assert "staff misconduct concern" not in html
    assert "Serious review cue records:" not in html
    assert "review_cue=serious" not in html
    assert "Related facility activity" not in html
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
        "source_records": 7,
        "reviewer_created_state": 0,
        "audit_events": 0,
        "reset_reload_planning_metadata": 0,
    }
    assert "Facility context cues" not in html
    assert "signal-only facility hub" not in html
    assert "uploaded public summary signals are available" not in html
    assert f"{CCLD_FACILITY_REVIEW_HUB_PATH}?facility_number=157806098" not in html
    assert "Open signal-only facility hub" not in html
    assert CCLD_FACILITY_REVIEW_PRIORITY_PATH not in html
    assert "Return to facility review priority list" not in html
    assert "Start complaint request if needed" not in html
    assert f"{REVIEWER_UI_PACKET_PREVIEW_PATH}?facility_number=157806098" not in html
    assert f"{REVIEWER_UI_PACKET_DRAFT_PATH}?facility_number=157806098" not in html
    assert "review badges" in normalized_html
    assert "status and note" in normalized_html
    assert "reviewer-created note/status" not in normalized_html
    assert "review" in normalized_html
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
    assert "Facility context cues" not in html
    assert "directory-backed facility hub cue" not in html
    assert "Facility context type" not in html
    assert f"{CCLD_FACILITY_REVIEW_HUB_PATH}?facility_number=157806098" not in html
    assert "Open facility hub" not in html
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

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert before_counts == after_counts == {
        "import_batches": 1,
        "source_records": 7,
        "reviewer_created_state": 0,
        "audit_events": 0,
        "reset_reload_planning_metadata": 0,
    }
    assert "Facility context cues" not in html
    assert "A facility hub cue is not available" not in html
    assert f"{CCLD_FACILITY_REVIEW_HUB_PATH}?facility_number=157806098" not in html
    assert "Open signal-only facility hub" not in html
    assert "Open facility hub" not in html
    assert "Return to facility review priority list" not in html
    assert "Start complaint request if needed" not in html
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
    normalized_html = " ".join(html.split()).casefold()

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert before_source_rows == after_source_rows
    assert before_counts == after_counts == {
        "import_batches": 1,
        "source_records": 7,
        "reviewer_created_state": 0,
        "audit_events": 0,
        "reset_reload_planning_metadata": 0,
    }
    assert "Source-derived value checks" not in html
    assert "Review flags and source checks" not in html
    assert "Visit" in html
    assert "Date not provided" in html
    assert "Check source" not in html
    assert "Missing source date" in html
    assert "Date mismatch" in html
    assert "Visit / inspection" not in html
    assert "Not available in loaded record" not in html
    assert "Review flag: report date used as proxy" not in html
    assert "Report date used as proxy; verify against source." not in html
    assert "Field-note guidance" not in html
    assert "Cautious reviewer-created note guidance" not in html
    assert "cue marks report date as a proxy" not in normalized_html
    assert "do not use it as a source-confidence score" not in normalized_html
    assert_no_secret_html(html)


def test_reviewer_value_states_render_explicit_accessible_labels() -> None:
    html = reviewer_ui._render_key_date_cards(  # noqa: SLF001
        {
            "complaint_received_date": "2026-07-13",
            "visit_date": "",
            "report_date": "not-a-date",
            "date_signed": "undated",
        }
    )
    zero_markup = reviewer_ui._reviewer_value_markup(  # noqa: SLF001
        0,
        kind="number",
        term_id="verified-zero",
    )
    null_markup = reviewer_ui._reviewer_value_markup(  # noqa: SLF001
        None,
        term_id="missing-finding",
    )
    unavailable_markup = reviewer_ui._reviewer_value_markup(  # noqa: SLF001
        "unavailable",
        term_id="source-unavailable",
    )

    assert "07/13/2026" in html
    assert "Date not provided" in html
    assert "Invalid source value" in html
    assert "Date not available" in html
    assert "not-a-date" not in html
    assert 'class="inline-glossary-term"' in html
    assert 'tabindex="0"' in html
    assert 'aria-description="' in html
    assert zero_markup == "0"
    assert "Not provided" in null_markup
    assert "Not available from source" in unavailable_markup
    for internal_state in (
        "present_blank",
        "source_unavailable",
        "not_applicable",
        "verified_zero",
    ):
        assert internal_state not in html
        assert internal_state not in null_markup
        assert internal_state not in unavailable_markup
    assert "database null" not in (html + null_markup).casefold()


def test_reviewer_matrix_export_preserves_blank_null_undated_and_malformed_states() -> None:
    with _seeded_connection() as connection:
        complaint_values = connection.execute(
            select(hosted_source_derived_records.c.original_values).where(
                hosted_source_derived_records.c.source_record_key == COMPLAINT_KEY
            )
        ).scalar_one()
        updated_values = dict(complaint_values)
        updated_values.update(
            {
                "first_investigation_activity_date": "",
                "visit_date": None,
                "report_date": "not-a-date",
                "date_signed": "undated",
            }
        )
        connection.execute(
            update(hosted_source_derived_records)
            .where(hosted_source_derived_records.c.source_record_key == COMPLAINT_KEY)
            .values(original_values=updated_values)
        )

        detail_status, detail_content_type, detail_body = route_response(
            f"{REVIEWER_UI_DETAIL_PATH}?source_record_key={quote(COMPLAINT_KEY)}",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

        status, content_type, body = route_response(
            f"{REVIEWER_UI_MATRIX_EXPORT_PATH}?facility_number=157806098",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    [row] = list(csv.DictReader(io.StringIO(body.decode("utf-8-sig"))))
    detail_html = detail_body.decode("utf-8")

    assert detail_status == 200
    assert detail_content_type == "text/html; charset=utf-8"
    assert "Date not provided" in detail_html
    assert "Invalid source value" in detail_html
    assert "Date not available" in detail_html
    assert "not-a-date" not in detail_html
    assert 'class="inline-glossary-term"' in detail_html
    assert status == 200
    assert content_type == "text/csv; charset=utf-8"
    assert row["first_investigation_activity_date"] == "Date not provided"
    assert row["visit_date"] == "Date not provided"
    assert row["report_date"] == "Invalid source value"
    assert row["date_signed"] == "Date not available"
    assert "not-a-date" not in body.decode("utf-8-sig")
    assert "\r\n,," not in body.decode("utf-8-sig")

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
        "source_records": 7,
        "reviewer_created_state": 0,
        "audit_events": 0,
        "reset_reload_planning_metadata": 0,
    }
    assert "Complaint overview" in html
    assert "Key dates" in html
    assert "Status and note" in html
    assert "Field-note guidance" not in html
    assert "feedback item for this record" not in html
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

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert before_source_rows == after_source_rows
    assert counts == {
        "import_batches": 1,
        "source_records": 7,
        "reviewer_created_state": 1,
        "audit_events": 1,
        "reset_reload_planning_metadata": 0,
    }
    assert "Notes/status saved" in html
    assert "Note saved for this record." in html
    assert "The note now appears in reviewer-created state below" not in html
    assert "What changed" in html
    assert "Note: added" in html
    assert "What did not change" in html
    assert "Source-derived complaint fields" in html
    assert "Public source link and source context" in html
    assert "Public-source records" in html
    assert "Next" in html
    assert "Return to facility queue" in html
    assert "Open next flagged record" in html
    assert "workflow_area=save-confirmation" not in html
    assert "Review packet readiness before copying or printing" not in html
    assert f"{REVIEWER_UI_PACKET_PREVIEW_PATH}?facility_number=157806098" not in html
    assert "Open print draft" not in html
    assert f"{REVIEWER_UI_PACKET_DRAFT_PATH}?facility_number=157806098" not in html
    assert "Return to the same facility queue or open the next flagged record" in html
    assert "submit the request again" not in html
    assert "feedback details" not in html
    assert "157806098" in html
    assert "08/01/2022 to 08/31/2022" in html
    assert "return_facility_number=157806098" in html
    assert "Review saved notes and statuses below" not in html
    assert "Review source traceability before export." in html
    assert "reviewer_note_scaffold" not in html
    assert "Saved notes and statuses" in html
    assert "Last saved" in html
    assert "Related facility activity" not in html
    assert "Field-note guidance" not in html
    assert "Fixture UI Note Reviewer (tester)" in html
    assert "Complaint record unchanged" in html
    assert "Reviewer-created; source-derived record unchanged" not in html
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
        "source_records": 7,
        "reviewer_created_state": 1,
        "audit_events": 1,
        "reset_reload_planning_metadata": 0,
    }
    assert "Notes/status saved" in html
    assert "Status saved for this record." in html
    assert "The status now appears in reviewer-created state below" not in html
    assert "Complaint fields remain unchanged, and no correction decision was submitted." in html
    assert "What changed" in html
    assert "Status: Needs follow-up" in html
    assert "What did not change" in html
    assert "Source-derived complaint fields" in html
    assert "Public source link and source context" in html
    assert "Public-source records" in html
    assert "Correction workflow state" in html
    assert "Next" in html
    assert "Return to facility queue" in html
    assert "Open next flagged record" in html
    assert "workflow_area=save-confirmation" not in html
    assert "Review packet readiness before copying or printing" not in html
    assert f"{REVIEWER_UI_PACKET_PREVIEW_PATH}?facility_number=157806098" not in html
    assert "Open print draft" not in html
    assert f"{REVIEWER_UI_PACKET_DRAFT_PATH}?facility_number=157806098" not in html
    assert "Return to the same facility queue or open the next flagged record" in html
    assert "submit the request again" not in html
    assert "feedback details" not in html
    assert "return_facility_number=157806098" in html
    assert "Review saved notes and statuses below" not in html
    assert "reviewer_status_scaffold" not in html
    assert "Needs follow-up" in html
    assert "Status recorded" in html
    assert "Saved notes and statuses" in html
    assert "Last saved" in html
    assert "Related facility activity" not in html
    assert "Field-note guidance" not in html
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
        "source_records": 7,
        "reviewer_created_state": 2,
        "audit_events": 2,
        "reset_reload_planning_metadata": 0,
    }
    assert "Blocked" in status_html
    assert "Blocked" in list_html
    assert "1 note" in list_html
    assert "Blocked" in list_html
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
    assert counts["source_records"] == 7
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


def test_fixture_demo_reviewer_context_keeps_seeded_fixture_scope() -> None:
    context = reviewer_ui.default_local_test_reviewer_ui_context()
    source_context = context.workflow_shell_context.source_derived_api_context

    assert source_context.scope == LOCAL_REVIEWER_UI_SCOPE
    assert source_context.actor is not None
    assert source_context.actor.scopes == (LOCAL_REVIEWER_UI_SCOPE,)
    assert source_context.scope.scope_id == "seeded-ccld-fixture-2026-06-13"


def test_default_postgres_reviewer_context_uses_loaded_ccld_corpus_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)
    monkeypatch.setattr(hosted_app, "_DEFAULT_POSTGRES_REVIEWER_UI_CONTEXT", None)
    monkeypatch.setattr(
        hosted_app,
        "load_hosted_database_config",
        lambda: SimpleNamespace(database_url="postgresql://example.invalid/records"),
    )
    monkeypatch.setattr(hosted_app, "create_engine", lambda _url: engine)

    try:
        context = hosted_app._default_postgres_reviewer_context()
        assert context is not None
        source_context = context.workflow_shell_context.source_derived_api_context

        assert source_context.scope == POSTGRES_REVIEWER_UI_SCOPE
        assert source_context.scope.scope_id != "seeded-ccld-fixture-2026-06-13"
        assert source_context.actor is not None
        assert source_context.actor.scopes == (POSTGRES_REVIEWER_UI_SCOPE,)
        assert context.manage_read_transactions is True
    finally:
        monkeypatch.setattr(hosted_app, "_DEFAULT_POSTGRES_REVIEWER_UI_CONTEXT", None)
        engine.dispose()

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


def _independent_distinct_substantiated_count(connection: Connection) -> int:
    rows = list(
        connection.execute(
            select(
                hosted_source_derived_records.c.source_record_key,
                hosted_source_derived_records.c.stable_source_id,
                hosted_source_derived_records.c.import_batch_id,
                hosted_source_derived_records.c.source_document_id,
                hosted_source_derived_records.c.facility_id,
                hosted_source_derived_records.c.entity_type,
                hosted_source_derived_records.c.original_values,
            )
        ).mappings()
    )
    qualifying_stable_ids: set[str] = set()
    for row in rows:
        if row["entity_type"] != "complaint":
            continue
        original_values = row["original_values"]
        assert isinstance(original_values, dict)
        if any(
            _test_is_substantiated_equivalent(original_values.get(key))
            for key in (
                "finding",
                "finding_status",
                "investigation_finding",
                "normalized_finding",
                "resolution",
                "status",
            )
        ) or _test_related_finding_qualifies(
            row,
            rows,
        ):
            qualifying_stable_ids.add(
                str(row["stable_source_id"] or row["source_record_key"])
            )
    return len(qualifying_stable_ids)


def _test_related_finding_qualifies(
    complaint_row: Mapping[str, Any],
    rows: list[Mapping[str, Any]],
) -> bool:
    complaint_values = complaint_row["original_values"]
    assert isinstance(complaint_values, dict)
    complaint_id = str(
        complaint_values.get("complaint_id") or complaint_row["stable_source_id"]
    )
    for row in rows:
        if row["import_batch_id"] != complaint_row["import_batch_id"]:
            continue
        if row["entity_type"] not in {"allegation", "event"}:
            continue
        values = row["original_values"]
        assert isinstance(values, dict)
        related_by_document = row["source_document_id"] == complaint_row["source_document_id"]
        related_by_complaint = str(values.get("complaint_id") or "") == complaint_id
        if not (related_by_document or related_by_complaint):
            continue
        if any(
            _test_is_substantiated_equivalent(values.get(key))
            for key in (
                "finding",
                "finding_status",
                "investigation_finding",
                "normalized_finding",
                "resolution",
                "status",
            )
        ):
            return True
        event_context = str(values.get("event_type") or "").casefold()
        if (
            row["entity_type"] == "event"
            and "finding" in event_context
            and _test_is_substantiated_equivalent(values.get("event_text"))
        ):
            return True
    return False


def _test_is_substantiated_equivalent(value: object) -> bool:
    if value is None:
        return False
    normalized = " ".join(str(value).strip().casefold().split())
    if not normalized:
        return False
    if "unsubstantiated" in normalized or "not substantiated" in normalized:
        return False
    return any(keyword in normalized for keyword in ("substantiated", "founded", "sustained"))


def _offset_from_source_route(path: str) -> int:
    query_values = parse_qs(urlparse(path).query, keep_blank_values=True)
    return int(query_values.get("offset", ["0"])[0])


def _json_source_records_response(records: tuple[dict[str, Any], ...]) -> tuple[int, str, bytes]:
    return (
        200,
        "application/json; charset=utf-8",
        json.dumps(
            {
                "records": list(records),
                "filters": {"entity_type": None},
                "pagination": {
                    "limit": reviewer_ui._SOURCE_DERIVED_PAGE_LIMIT,
                    "offset": 0,
                    "returned_count": len(records),
                },
            },
            sort_keys=True,
        ).encode("utf-8"),
    )


def _read_model_from_source_payload(record: Mapping[str, Any]) -> object:
    import_batch = record["import_batch"]
    return SimpleNamespace(
        source_record_key=record["source_record_key"],
        entity_type=record["entity_type"],
        stable_source_id=record["stable_source_id"],
        source_document_id=record["source_document_id"],
        facility_id=record["facility_id"],
        source_url=record["source_url"],
        raw_sha256=record["raw_sha256"],
        raw_path=record["raw_path"],
        connector_name=record["connector_name"],
        connector_version=record["connector_version"],
        retrieved_at=record["retrieved_at"],
        original_values=record["original_values"],
        original_value_presentations={},
        source_traceability=record["source_traceability"],
        import_batch=SimpleNamespace(
            import_batch_id=import_batch["import_batch_id"],
            imported_at=import_batch["imported_at"],
            source_artifact_identity=import_batch["source_artifact_identity"],
            source_pipeline_version=import_batch["source_pipeline_version"],
            validation_status=import_batch["validation_status"],
            raw_hash_validation_status=import_batch["raw_hash_validation_status"],
            record_counts=import_batch["record_counts"],
            warnings=import_batch["warnings"],
            errors=import_batch["errors"],
        ),
    )


def _fake_filler_source_records(
    offset: int,
    count: int,
) -> tuple[dict[str, Any], ...]:
    return tuple(
        _fake_source_record(
            entity_type="facility",
            source_record_key=f"facility:filler:{offset + index:05d}",
            stable_source_id=f"ccld:facility:filler:{offset + index:05d}",
            source_document_id=f"ccld:document:filler:{offset + index:05d}",
            facility_id=f"ccld:facility:filler:{offset + index:05d}",
            source_url=_ccld_source_url(f"9{offset + index:08d}", "1"),
            original_values={
                "facility_id": f"ccld:facility:filler:{offset + index:05d}",
                "external_facility_number": f"9{offset + index:08d}",
                "facility_name": f"FILLER FACILITY {offset + index:05d}",
            },
        )
        for index in range(count)
    )


def _fake_substantiated_source_bundle(
    *,
    facility_number: str,
    facility_name: str,
    complaint_control_number: str,
    complaint_received_date: str,
    source_url: str,
) -> tuple[dict[str, Any], ...]:
    facility_id = f"ccld:facility:{facility_number}"
    source_document_id = f"ccld:document:{facility_number}:1"
    complaint_id = f"ccld:complaint:{complaint_control_number}"
    return (
        _fake_source_record(
            entity_type="facility",
            source_record_key=f"facility:{facility_id}",
            stable_source_id=facility_id,
            source_document_id=source_document_id,
            facility_id=facility_id,
            source_url=source_url,
            original_values={
                "facility_id": facility_id,
                "external_facility_number": facility_number,
                "facility_name": facility_name,
                "facility_type": "Children's Center",
                "county": "Kern",
            },
        ),
        _fake_source_record(
            entity_type="source_document",
            source_record_key=f"source_document:{source_document_id}",
            stable_source_id=source_document_id,
            source_document_id=source_document_id,
            facility_id=facility_id,
            source_url=source_url,
            original_values={
                "document_id": source_document_id,
                "facility_id": facility_id,
                "source_url": source_url,
                "document_type": "complaint_investigation_report",
            },
        ),
        _fake_source_record(
            entity_type="complaint",
            source_record_key=f"complaint:{complaint_id}",
            stable_source_id=complaint_id,
            source_document_id=source_document_id,
            facility_id=facility_id,
            source_url=source_url,
            original_values={
                "complaint_id": complaint_id,
                "facility_id": facility_id,
                "document_id": source_document_id,
                "complaint_control_number": complaint_control_number,
                "complaint_received_date": complaint_received_date,
                "finding": "Substantiated",
            },
        ),
    )


def _fake_source_record(
    *,
    entity_type: str,
    source_record_key: str,
    stable_source_id: str,
    source_document_id: str,
    facility_id: str,
    source_url: str,
    original_values: dict[str, Any],
) -> dict[str, Any]:
    traceability = {
        "source_url": source_url,
        "raw_sha256": "e" * 64,
        "raw_path": "data/raw/ccld/fake-source.html",
        "connector_name": "ccld_facility_reports",
        "connector_version": "fake-test",
        "retrieved_at": "2026-07-01T12:00:00+00:00",
        "source_artifact_identity": "fake-source-artifact",
    }
    return {
        "source_record_key": source_record_key,
        "entity_type": entity_type,
        "stable_source_id": stable_source_id,
        "source_document_id": source_document_id,
        "facility_id": facility_id,
        "source_url": source_url,
        "raw_sha256": "e" * 64,
        "raw_path": "data/raw/ccld/fake-source.html",
        "connector_name": "ccld_facility_reports",
        "connector_version": "fake-test",
        "retrieved_at": "2026-07-01T12:00:00+00:00",
        "original_values": original_values,
        "source_traceability": traceability,
        "import_batch": {
            "import_batch_id": TEST_SCOPE.scope_id,
            "imported_at": "2026-07-01T12:00:00+00:00",
            "source_artifact_identity": "fake-source-artifact",
            "source_pipeline_version": "fake-test",
            "validation_status": "validated",
            "raw_hash_validation_status": "validated",
            "record_counts": {},
            "warnings": [],
            "errors": [],
        },
    }


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
    facility_type: str = "Children's Center",
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
                "facility_type": facility_type,
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


def _insert_live_shape_related_finding_records(
    connection: Connection,
    complaint_key: str,
    *,
    finding: str,
    event_text: str,
    suffix: str = "1",
) -> None:
    complaint_row = connection.execute(
        select(hosted_source_derived_records).where(
            hosted_source_derived_records.c.source_record_key == complaint_key
        )
    ).mappings().one()
    original_values = complaint_row["original_values"]
    source_traceability = complaint_row["source_traceability"]
    assert isinstance(original_values, dict)
    assert isinstance(source_traceability, dict)
    complaint_id = str(original_values["complaint_id"])
    facility_id = str(complaint_row["facility_id"])
    document_id = str(complaint_row["source_document_id"])
    common_values = {
        "import_batch_id": str(complaint_row["import_batch_id"]),
        "source_document_id": document_id,
        "facility_id": facility_id,
        "source_url": str(complaint_row["source_url"]),
        "raw_sha256": str(complaint_row["raw_sha256"]),
        "raw_path": str(complaint_row["raw_path"]),
        "connector_name": str(complaint_row["connector_name"]),
        "connector_version": str(complaint_row["connector_version"]),
        "retrieved_at": str(complaint_row["retrieved_at"]),
        "source_traceability": source_traceability,
    }
    connection.execute(
        hosted_source_derived_records.insert().values(
            source_record_key=f"allegation:{complaint_id}:{suffix}",
            entity_type="allegation",
            stable_source_id=f"{complaint_id}:allegation:{suffix}",
            original_values={
                "allegation_id": f"{complaint_id}:allegation:{suffix}",
                "complaint_id": complaint_id,
                "facility_id": facility_id,
                "document_id": document_id,
                "finding": finding,
                "allegation_text": "Loaded public allegation text.",
            },
            **common_values,
        )
    )
    connection.execute(
        hosted_source_derived_records.insert().values(
            source_record_key=f"event:{complaint_id}:finding:{suffix}",
            entity_type="event",
            stable_source_id=f"{complaint_id}:event:finding:{suffix}",
            original_values={
                "event_id": f"{complaint_id}:event:finding:{suffix}",
                "complaint_id": complaint_id,
                "facility_id": facility_id,
                "document_id": document_id,
                "event_type": "investigation_finding",
                "event_text": event_text,
            },
            **common_values,
        )
    )


def _insert_extraction_audit_marker(connection: Connection) -> None:
    template = connection.execute(
        select(hosted_source_derived_records).where(
            hosted_source_derived_records.c.source_record_key == COMPLAINT_KEY
        )
    ).mappings().one()
    connection.execute(
        hosted_source_derived_records.insert().values(
            source_record_key="extraction_audit:ccld:audit:ui-do-not-load",
            entity_type="extraction_audit",
            stable_source_id="ccld:audit:ui-do-not-load",
            import_batch_id=template["import_batch_id"],
            source_document_id=template["source_document_id"],
            facility_id=template["facility_id"],
            source_url=template["source_url"],
            raw_sha256=template["raw_sha256"],
            raw_path=template["raw_path"],
            connector_name=template["connector_name"],
            connector_version=template["connector_version"],
            retrieved_at=template["retrieved_at"],
            original_values={
                "audit_id": "ccld:audit:ui-do-not-load",
                "finding": "Substantiated",
                "complaint_control_number": "AUDIT SHOULD NOT LOAD",
            },
            source_traceability=template["source_traceability"],
        )
    )


def _insert_matrix_complaint_copies(connection: Connection, *, count: int) -> None:
    template = connection.execute(
        select(hosted_source_derived_records).where(
            hosted_source_derived_records.c.source_record_key == COMPLAINT_KEY
        )
    ).mappings().one()
    rows = []
    for index in range(count):
        values = dict(template)
        stable_source_id = f"ccld:complaint:matrix-performance-{index:03d}"
        values["source_record_key"] = f"complaint:{stable_source_id}"
        values["stable_source_id"] = stable_source_id
        original_values = dict(template["original_values"])
        original_values["complaint_id"] = stable_source_id
        original_values["complaint_control_number"] = f"MATRIX-{index:03d}"
        values["original_values"] = original_values
        rows.append(values)
    connection.execute(hosted_source_derived_records.insert(), rows)


def _flatten_sql_parameters(parameters: object) -> tuple[object, ...]:
    if isinstance(parameters, Mapping):
        return tuple(parameters.values())
    if isinstance(parameters, tuple):
        flattened: list[object] = []
        for value in parameters:
            if isinstance(value, (tuple, list)):
                flattened.extend(value)
            else:
                flattened.append(value)
        return tuple(flattened)
    if isinstance(parameters, list):
        return tuple(parameters)
    return (parameters,)


def _insert_representative_live_public_retrieval_batch(
    connection: Connection,
    representative: dict[str, str],
    *,
    scope: HostedAccessScope = TEST_SCOPE,
) -> None:
    job_id = f"fixture-job-{representative['facility_number']}-{representative['report_index']}"
    import_batch_id = retrieval_import_batch_id(job_id)
    source_url = _ccld_source_url(
        representative["facility_number"],
        representative["report_index"],
    )
    raw_sha256 = (representative["facility_number"] * 8)[:64]
    artifact_identity = f"fixture-live-public-artifact:{job_id}"
    now = "2026-07-01T12:00:00+00:00"
    connection.execute(
        hosted_ccld_retrieval_jobs.insert().values(
            retrieval_job_id=job_id,
            created_at=now,
            updated_at=now,
            job_state="completed",
            facility_number=representative["facility_number"],
            record_type="complaints",
            start_date=representative["received_date"],
            end_date=representative["signed_date"],
            source_scope_type=scope.scope_type,
            source_scope_id=scope.scope_id,
            actor_provider_subject="fixture-ui-reviewer",
            actor_provider_issuer="fixture-managed-oidc-provider",
            actor_display_name="Fixture UI Reviewer",
            actor_category="tester",
            authorization_permission="retrieval_job_trigger",
            request_limit="10",
            retry_limit="1",
            timeout_seconds="20",
            raw_storage_path="data/raw/ccld/fixture-live-public",
            source_artifact_identity=artifact_identity,
            result_counts={
                "retrieved_record_bundles": 1,
                "imported_source_derived_records": 109,
                "report_failures": 0,
            },
            warnings=[],
            errors=[],
            safe_message="Fixture retrieval completed.",
            data_mutations_performed=True,
        )
    )
    connection.execute(
        hosted_import_batches.insert().values(
            import_batch_id=import_batch_id,
            imported_at=now,
            source_artifact_identity=artifact_identity,
            source_pipeline_version="fixture-live-public",
            validation_status="validated",
            raw_hash_validation_status="validated",
            record_counts={
                "facility": 106,
                "source_document": 1,
                "complaint": 1,
                "allegation": 1,
                "event": 1,
                "extraction_audit": 0,
            },
            warnings=[],
            errors=[],
        )
    )
    for index in range(105):
        filler_facility_number = f"9009{index:05d}"
        filler_stable_prefix = f"aaa-filler-{representative['facility_number']}-{index:03d}"
        connection.execute(
            hosted_source_derived_records.insert().values(
                **_representative_source_record_values(
                    import_batch_id=import_batch_id,
                    source_artifact_identity=artifact_identity,
                    entity_type="facility",
                    stable_source_id=f"{filler_stable_prefix}-facility",
                    source_document_id=f"{filler_stable_prefix}-document",
                    facility_id=f"{filler_stable_prefix}-facility",
                    source_url=_ccld_source_url(filler_facility_number, "1"),
                    raw_sha256="a" * 64,
                    original_values={
                        "facility_id": f"{filler_stable_prefix}-facility",
                        "facility_number": filler_facility_number,
                        "facility_name": f"Unrelated Facility {index:03d}",
                    },
                )
            )
        )

    facility_id = f"ccld-facility-{representative['facility_number']}"
    source_document_id = representative["source_document_id"]
    complaint_stable_id = representative["complaint_key"].split(":", 1)[1]
    connection.execute(
        hosted_source_derived_records.insert().values(
            **_representative_source_record_values(
                import_batch_id=import_batch_id,
                source_artifact_identity=artifact_identity,
                entity_type="facility",
                stable_source_id=facility_id,
                source_document_id=source_document_id,
                facility_id=facility_id,
                source_url=source_url,
                raw_sha256=raw_sha256,
                original_values={
                    "facility_id": facility_id,
                    "facility_number": representative["facility_number"],
                    "name": representative["facility_name"],
                    "facility_type": representative["facility_type"],
                    "status": representative["status"],
                    "county": representative["county"],
                },
            )
        )
    )
    connection.execute(
        hosted_source_derived_records.insert().values(
            **_representative_source_record_values(
                import_batch_id=import_batch_id,
                source_artifact_identity=artifact_identity,
                entity_type="source_document",
                stable_source_id=source_document_id,
                source_document_id=source_document_id,
                facility_id=facility_id,
                source_url=source_url,
                raw_sha256=raw_sha256,
                original_values={
                    "document_id": source_document_id,
                    "facility_id": facility_id,
                    "source_url": source_url,
                    "raw_sha256": raw_sha256,
                    "connector_name": "ccld_facility_reports",
                    "connector_version": "fixture-live-public",
                    "retrieved_at": now,
                    "document_type": "complaint_investigation_report",
                    "report_index": representative["report_index"],
                },
            )
        )
    )
    connection.execute(
        hosted_source_derived_records.insert().values(
            **_representative_source_record_values(
                import_batch_id=import_batch_id,
                source_artifact_identity=artifact_identity,
                entity_type="complaint",
                stable_source_id=complaint_stable_id,
                source_record_key=representative["complaint_key"],
                source_document_id=source_document_id,
                facility_id=facility_id,
                source_url=source_url,
                raw_sha256=raw_sha256,
                original_values={
                    "complaint_id": complaint_stable_id,
                    "facility_id": facility_id,
                    "document_id": source_document_id,
                    "complaint_control_number": representative[
                        "complaint_control_number"
                    ],
                    "complaint_received_date": representative["received_date"],
                    "visit_date": representative["visit_date"],
                    "report_date": representative["report_date"],
                    "date_signed": representative["signed_date"],
                    "finding": representative["finding"],
                    "source_text": representative["narrative"],
                },
            )
        )
    )
    connection.execute(
        hosted_source_derived_records.insert().values(
            **_representative_source_record_values(
                import_batch_id=import_batch_id,
                source_artifact_identity=artifact_identity,
                entity_type="allegation",
                stable_source_id=f"{complaint_stable_id}:1",
                source_document_id=source_document_id,
                facility_id=facility_id,
                source_url=source_url,
                raw_sha256=raw_sha256,
                original_values={
                    "allegation_id": f"{complaint_stable_id}:1",
                    "complaint_id": complaint_stable_id,
                    "facility_id": facility_id,
                    "document_id": source_document_id,
                    "finding": representative["finding"],
                    "allegation_text": representative["allegation_text"],
                },
            )
        )
    )
    connection.execute(
        hosted_source_derived_records.insert().values(
            **_representative_source_record_values(
                import_batch_id=import_batch_id,
                source_artifact_identity=artifact_identity,
                entity_type="event",
                stable_source_id=f"{complaint_stable_id}:finding",
                source_document_id=source_document_id,
                facility_id=facility_id,
                source_url=source_url,
                raw_sha256=raw_sha256,
                original_values={
                    "event_id": f"{complaint_stable_id}:finding",
                    "complaint_id": complaint_stable_id,
                    "facility_id": facility_id,
                    "document_id": source_document_id,
                    "event_type": "investigation_finding",
                    "event_date": representative["report_date"],
                    "event_text": representative["narrative"],
                },
            )
        )
    )


def _representative_retrieval_record(
    *,
    facility_number: str,
    facility_name: str,
    facility_type: str,
    county: str,
    complaint_control_number: str,
    report_index: str,
    finding: str,
    narrative: str,
    received_date: str,
) -> dict[str, str]:
    return {
        "facility_number": facility_number,
        "facility_name": facility_name,
        "facility_type": facility_type,
        "status": "Licensed",
        "county": county,
        "complaint_control_number": complaint_control_number,
        "complaint_key": f"complaint:ccld-complaint-{complaint_control_number}",
        "source_document_id": f"ccld-{facility_number}-inx-{report_index}",
        "report_index": report_index,
        "finding": finding,
        "allegation_text": "Facility staff did not follow the written placement plan.",
        "narrative": narrative,
        "received_date": received_date,
        "visit_date": received_date,
        "report_date": received_date,
        "signed_date": received_date,
    }


def _representative_source_record_values(
    *,
    import_batch_id: str,
    source_artifact_identity: str,
    entity_type: str,
    stable_source_id: str,
    source_document_id: str,
    facility_id: str,
    source_url: str,
    raw_sha256: str,
    original_values: dict[str, Any],
    source_record_key: str | None = None,
) -> dict[str, Any]:
    return {
        "source_record_key": source_record_key or f"{entity_type}:{stable_source_id}",
        "entity_type": entity_type,
        "stable_source_id": stable_source_id,
        "import_batch_id": import_batch_id,
        "source_document_id": source_document_id,
        "facility_id": facility_id,
        "source_url": source_url,
        "raw_sha256": raw_sha256,
        "raw_path": "data/raw/ccld/fixture-live-public/report.html",
        "connector_name": "ccld_facility_reports",
        "connector_version": "fixture-live-public",
        "retrieved_at": "2026-07-01T12:00:00+00:00",
        "original_values": original_values,
        "source_traceability": {
            "source_document_id": source_document_id,
            "source_url": source_url,
            "raw_sha256": raw_sha256,
            "raw_path": "data/raw/ccld/fixture-live-public/report.html",
            "connector_name": "ccld_facility_reports",
            "connector_version": "fixture-live-public",
            "retrieved_at": "2026-07-01T12:00:00+00:00",
            "source_artifact_identity": source_artifact_identity,
        },
    }


def _ccld_source_url(facility_number: str, report_index: str) -> str:
    return (
        "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports"
        f"?facNum={facility_number}&inx={report_index}"
    )


def _mmddyyyy(iso_date: str) -> str:
    year, month, day = iso_date.split("-")
    return f"{month}/{day}/{year}"


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
