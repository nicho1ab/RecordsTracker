"""Representative application-bound reviewer regression contracts."""

from __future__ import annotations

import importlib.util
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, urlencode

from ccld_complaints.hosted_app.app import route_response
from ccld_complaints.hosted_app.reviewer_ui import (
    CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH,
    REVIEWER_UI_DETAIL_PATH,
    REVIEWER_UI_FACILITY_PRIORITIES_PATH,
    REVIEWER_UI_STATUS_PATH,
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
assert_help_surface = CONTRACTS.assert_help_surface

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
            "&return_facility_number=157806098"
            "&return_start_date=2022-08-01"
            "&return_end_date=2022-08-31"
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
            reviewer_ui_context=context,
        )
        failure_status, _failure_type, failure_body = route_response(
            REVIEWER_UI_STATUS_PATH,
            method="POST",
            request_body=_form_bytes(
                {
                    "source_record_key": COMPLAINT_KEY,
                    "reviewer_status": "not-a-status",
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
        assert "Complaint overview" in detail_html
        assert "Return to review queue" in detail_html
        assert "Status saved for this record." in success_html
        assert "Return to facility queue" in success_html
        assert "Reviewer status was not saved" in failure_html
        assert "Return to selected record detail" in failure_html

        assert_continuity(
            {
                "selection": "157806098",
                "focus": "return to facility queue",
                "context": "2022-08-01..2022-08-31",
            },
            {
                "selection": "157806098" if "157806098" in success_html else None,
                "focus": (
                    "return to facility queue"
                    if "Return to facility queue" in success_html
                    else None
                ),
                "context": (
                    "2022-08-01..2022-08-31"
                    if "return_start_date=2022-08-01" in success_html
                    and "return_end_date=2022-08-31" in success_html
                    else None
                ),
            },
        )
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
        detail_section_start = detail_html.index(
            'class="detail-card historical-complaint-report"'
        )
        detail_section = detail_html[
            detail_section_start : detail_html.index(
                '<p class="helper-text">These are historical complaint-report observations.',
                detail_section_start,
            )
        ]
        intelligence_terms = _glossary_terms(intelligence_html)
        detail_terms = _glossary_terms(detail_section)

        assert intelligence_status == detail_status == 200
        assert any(
            term.get("data-term-id") == "intelligence-substantiated"
            for term in intelligence_terms
        )
        assert "CCLD finding term" not in intelligence_html
        assert len(detail_terms) >= 4
        assert len({term.get("data-term-id") for term in detail_terms}) == len(detail_terms)

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
