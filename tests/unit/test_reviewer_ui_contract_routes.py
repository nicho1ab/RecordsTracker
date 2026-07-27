"""Representative application-bound reviewer regression contracts."""

from __future__ import annotations

import importlib.util
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, urlencode

from ccld_complaints.hosted_app.app import route_response
from ccld_complaints.hosted_app.reviewer_ui import (
    CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH,
    REVIEWER_UI_DETAIL_PATH,
    REVIEWER_UI_FACILITY_PRIORITIES_PATH,
    REVIEWER_UI_UPDATE_PATH,
    build_local_test_reviewer_ui_context,
)

SPEC = importlib.util.spec_from_file_location(
    "reviewer_route_contracts",
    Path(__file__).with_name("reviewer_ui_contracts.py"),
)
assert SPEC and SPEC.loader
CONTRACTS = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CONTRACTS
SPEC.loader.exec_module(CONTRACTS)
assert_continuity = CONTRACTS.assert_continuity
assert_destinations = CONTRACTS.assert_destinations
assert_actions = CONTRACTS.assert_actions
assert_facility_identity = CONTRACTS.assert_facility_identity
assert_help_surface = CONTRACTS.assert_help_surface
assert_result_structure = CONTRACTS.assert_result_structure

COMPLAINT_KEY = "complaint:ccld:complaint:32-CR-20220407124448"


class _GlossaryParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.terms: list[dict[str, str | None]] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        attributes = dict(attrs)
        if tag == "dfn" and "inline-glossary-term" in (attributes.get("class") or "").split():
            self.terms.append(attributes)


def _glossary_terms(markup: str) -> list[dict[str, str | None]]:
    parser = _GlossaryParser()
    parser.feed(markup)
    return parser.terms


def _form_bytes(payload: dict[str, str]) -> bytes:
    return urlencode(payload).encode("utf-8")


def test_representative_reviewer_actions_reach_real_routes_and_mutation_feedback() -> None:
    context = build_local_test_reviewer_ui_context()
    assert context.engine is not None
    try:
        search_path = "/reviewer/records?q=32-CR"
        detail_path = (
            f"{REVIEWER_UI_DETAIL_PATH}?source_record_key={quote(COMPLAINT_KEY)}"
            "&return_context_origin=reviewer_worklist"
            "&return_q=32-CR"
            f"&return_source_record_key={quote(COMPLAINT_KEY)}"
        )
        facility_path = f"{REVIEWER_UI_FACILITY_PRIORITIES_PATH}?facility=157806098"

        search_status, _search_type, search_body = route_response(
            search_path,
            reviewer_ui_context=context,
        )
        detail_status, _detail_type, detail_body = route_response(
            detail_path,
            reviewer_ui_context=context,
        )
        facility_status, _facility_type, _facility_body = route_response(
            facility_path,
            reviewer_ui_context=context,
        )
        success_status, _success_type, success_body = route_response(
            REVIEWER_UI_UPDATE_PATH,
            method="POST",
            request_body=_form_bytes(
                {
                    "source_record_key": COMPLAINT_KEY,
                    "reviewer_status": "needs_follow_up",
                    "note_text": "Check the linked source report.",
                    "return_context_origin": "reviewer_worklist",
                    "return_q": "32-CR",
                    "return_source_record_key": COMPLAINT_KEY,
                }
            ),
            reviewer_ui_context=context,
        )
        failure_status, _failure_type, failure_body = route_response(
            REVIEWER_UI_UPDATE_PATH,
            method="POST",
            request_body=_form_bytes(
                {
                    "source_record_key": COMPLAINT_KEY,
                    "reviewer_status": "not-a-status",
                    "note_text": "This note must roll back with the invalid status.",
                }
            ),
            reviewer_ui_context=context,
        )

        actual_statuses = {
            search_path: search_status,
            detail_path: detail_status,
            facility_path: facility_status,
        }
        assert_destinations(
            [
                {"kind": "get", "destination": search_path},
                {"kind": "get", "destination": detail_path},
                {"kind": "get", "destination": facility_path},
                {
                    "kind": "external",
                    "provenance": "validated fixture source document and report index",
                },
                {
                    "kind": "mutation",
                    "success": success_status == 200,
                    "failure": failure_status == 400,
                },
            ],
            actual_statuses.__getitem__,
        )

        search_html = search_body.decode("utf-8")
        detail_html = detail_body.decode("utf-8")
        success_html = success_body.decode("utf-8")
        failure_html = failure_body.decode("utf-8")
        assert 'value="32-CR"' in search_html
        assert "32-CR-20220407124448" in search_html
        worklist_row_count = search_html.count('class="review-worklist-row')
        assert worklist_row_count >= 1
        assert search_html.count('<ol class="review-worklist"') == 1
        assert (
            search_html.count(
                '<a class="button" href="/reviewer/records/detail?'
            )
            == worklist_row_count
        )
        assert "Show table view" not in search_html
        assert_result_structure(
            [
                {
                    "representation_id": "complaint-worklist",
                    "section_id": "reviewer-list-heading",
                    "rows": (COMPLAINT_KEY,),
                }
            ],
            [{"section_id": "reviewer-list-heading", "empty": False}],
        )
        assert_actions(
            [
                {
                    "action_id": "review-complaint",
                    "order": 1,
                    "visible": True,
                    "keyboard": True,
                    "left": 0,
                    "right": 1,
                }
            ]
        )
        assert "Complaint overview" in detail_html
        assert "Return to Complaint Worklist" in detail_html
        assert_facility_identity(
            [
                {
                    "facility_id": "157806098",
                    "name": "A. MIRIAM JAMISON CHILDREN'S CENTER",
                }
            ]
        )
        assert "Saved status as Needs follow-up and note." in success_html
        assert 'role="status"' in success_html
        assert "Return to Complaint Worklist" in success_html
        assert "Review update was not saved" in failure_html
        assert "No status or note from this submission was added" in failure_html
        assert 'role="alert"' in failure_html

        assert_continuity(
            {
                "selection": COMPLAINT_KEY,
                "focus": "complaint worklist record",
                "context": "q=32-CR",
            },
            {
                "selection": COMPLAINT_KEY if COMPLAINT_KEY in success_html else None,
                "focus": (
                    "complaint worklist record"
                    if f"#record-{quote(COMPLAINT_KEY)}" in success_html
                    else None
                ),
                "context": (
                    "q=32-CR" if "q=32-CR" in success_html else None
                ),
            },
        )
    finally:
        context.engine.dispose()


def test_complaint_overview_print_allows_large_content_to_flow_without_orphaning() -> None:
    """Keep the print contract focused on readable pagination, not page count."""

    context = build_local_test_reviewer_ui_context()
    assert context.engine is not None
    try:
        status, _content_type, body = route_response(
            f"{REVIEWER_UI_DETAIL_PATH}?source_record_key={quote(COMPLAINT_KEY)}",
            reviewer_ui_context=context,
        )
        html = body.decode("utf-8")
        assert status == 200

        print_css = re.search(r"@media print \{(?P<rules>.*?)\n    \}", html, re.DOTALL)
        assert print_css is not None
        rules = print_css.group("rules")
        assert re.search(
            r"\.reviewer-detail-page\.detail-shell\s*\{\s*display: block;",
            rules,
        )
        assert re.search(
            r"\.complaint-overview-card\s*\{.*?break-inside: auto;.*?page-break-inside: auto;",
            rules,
            re.DOTALL,
        )
        assert re.search(
            r"\.reviewer-detail-page h2\s*\{.*?break-after: avoid-page;",
            rules,
            re.DOTALL,
        )
        assert ".overview-source-action" in rules
        assert ".review-update-form" in rules
    finally:
        context.engine.dispose()


def test_rt_rc_003_representative_routes_use_one_shared_accessible_help_contract() -> None:
    context = build_local_test_reviewer_ui_context()
    assert context.engine is not None
    try:
        intelligence_status, _intelligence_type, intelligence_body = route_response(
            CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH,
            reviewer_ui_context=context,
        )
        detail_status, _detail_type, detail_body = route_response(
            f"{REVIEWER_UI_DETAIL_PATH}?source_record_key={quote(COMPLAINT_KEY)}",
            reviewer_ui_context=context,
        )

        intelligence_html = intelligence_body.decode("utf-8")
        detail_html = detail_body.decode("utf-8")
        intelligence_terms = _glossary_terms(intelligence_html)
        detail_terms = _glossary_terms(detail_html)

        assert intelligence_status == detail_status == 200
        assert any(
            term.get("data-term-id") == "intelligence-substantiated"
            for term in intelligence_terms
        )
        assert "CCLD finding term" not in intelligence_html
        assert len(detail_terms) >= 4
        assert all(term.get("data-definition") for term in detail_terms)
        assert "var count = definitionCounts[baseId] || 0" in detail_html

        all_terms = intelligence_terms + detail_terms
        assert_help_surface(
            [
                {
                    "active": False,
                    "accessible_descriptions": int(bool(term.get("data-definition"))),
                    "native_title": "title" in term,
                    "aria_description": "aria-description" in term,
                }
                for term in all_terms
            ],
            escape_supported=True,
        )
        for html in (intelligence_html, detail_html):
            assert html.count("var activeTerm = null") == 1
            assert "if (activeTerm && activeTerm !== term) hide(activeTerm)" in html
            assert "term.addEventListener('click'" in html
            assert "document.addEventListener('pointerdown'" in html
            assert "event.pointerType === 'touch'" in html
            assert "term.focus({preventScroll: true})" in html
            assert "window.innerWidth - popup.width - viewportPadding" in html
            assert "window.innerHeight - popup.height - viewportPadding" in html
    finally:
        context.engine.dispose()
