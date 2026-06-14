from __future__ import annotations

import json
from html.parser import HTMLParser

from ccld_complaints.hosted_app.app import (
    SourceRecordFilters,
    filter_sample_source_records,
    get_sample_source_record,
    health_response,
    render_app_shell,
    route_response,
    source_record_filters_from_query,
)
from ccld_complaints.hosted_app.smoke import run_scaffold_smoke_check


class HtmlStructureParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[str] = []
        self.links: list[str] = []
        self.text_by_tag: dict[str, list[str]] = {}
        self._stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag)
        self._stack.append(tag)
        if tag == "a":
            for name, value in attrs:
                if name == "href" and value is not None:
                    self.links.append(value)

    def handle_endtag(self, tag: str) -> None:
        if tag in self._stack:
            while self._stack:
                open_tag = self._stack.pop()
                if open_tag == tag:
                    break

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        for tag in self._stack:
            self.text_by_tag.setdefault(tag, []).append(text)

    def text_for(self, tag: str) -> str:
        return " ".join(self.text_by_tag.get(tag, []))


def parse_html_structure(markup: str) -> HtmlStructureParser:
    parser = HtmlStructureParser()
    parser.feed(markup)
    return parser


def assert_source_shell_semantics(
    markup: str,
    *,
    expected_title: str,
    expected_h1: str,
    required_links: set[str],
) -> HtmlStructureParser:
    parser = parse_html_structure(markup)
    normalized_main = " ".join(parser.text_for("main").split())

    assert parser.tags.count("main") == 1
    assert parser.tags.count("nav") >= 1
    assert parser.tags.count("h1") == 1
    assert expected_title in parser.text_for("title")
    assert expected_h1 in parser.text_for("h1")
    assert "Fixture/sample data only" in normalized_main
    assert "No live public-source data is loaded" in normalized_main
    assert "No reviewer workflow is active" in normalized_main
    assert "no authentication is implemented" in normalized_main
    assert "no reviewer-created state is persisted" in normalized_main
    assert "Source-derived sample records and future reviewer-created state remain separate" in (
        normalized_main
    )
    assert "read-only" in normalized_main.lower()
    assert required_links.issubset(set(parser.links))
    return parser


def test_health_response_marks_scaffold_only() -> None:
    payload = health_response()

    assert payload["status"] == "ok"
    assert payload["service"] == "hosted-tester-mvp-scaffold"
    assert payload["scaffold_only"] is True
    assert payload["review_workflows_implemented"] is False
    assert payload["authentication_implemented"] is False
    assert payload["source_data_loaded"] is False


def test_app_shell_labels_placeholder_boundaries() -> None:
    html = render_app_shell()
    normalized_html = " ".join(html.split())

    assert "<main>" in html
    assert "Scaffold only: not a functioning reviewer workflow yet." in html
    assert "No records are loaded" in html
    assert "Authentication and authorization" in html
    assert "QNAP, Azure, AWS, public URLs, or deployment" in normalized_html
    assert "Sample source-derived records" in html


def test_routes_return_shell_health_and_not_found() -> None:
    root_status, root_content_type, root_body = route_response("/")
    health_status, health_content_type, health_body = route_response("/health")
    api_status, api_content_type, api_body = route_response("/api/health")
    missing_status, missing_content_type, missing_body = route_response("/missing")

    assert root_status == 200
    assert root_content_type == "text/html; charset=utf-8"
    assert b"not a functioning reviewer workflow yet" in root_body
    assert health_status == 200
    assert health_content_type == "application/json; charset=utf-8"
    assert json.loads(health_body)["status"] == "ok"
    assert api_status == 200
    assert api_content_type == "application/json; charset=utf-8"
    assert json.loads(api_body)["service"] == "hosted-tester-mvp-scaffold"
    assert missing_status == 404
    assert missing_content_type == "text/plain; charset=utf-8"
    assert missing_body == b"Not found"


def test_source_record_list_route_labels_sample_read_only_scope() -> None:
    status, content_type, body = route_response("/source-records")
    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Sample source-derived records" in html
    assert "Fixture/sample data only" in html
    assert "No live public-source data is loaded" in html
    assert "No reviewer workflow is active" in html
    assert "no authentication is implemented" in html
    assert "no reviewer-created state is persisted" in html
    assert "Source-derived sample records and future reviewer-created state remain separate" in (
        normalized_html
    )
    assert "Sample filtering/search" in html
    assert "Filters apply only to the local fixture/sample records" in normalized_html
    assert "Jurisdiction" in html
    assert "Source family" in html
    assert "Source type" in html
    assert "Raw SHA-256" in html
    assert "sample-complaint-001" in html


def test_source_record_filter_query_uses_sample_records_only() -> None:
    filters = source_record_filters_from_query(
        "q=beta&jurisdiction=California&source_family=CCLD+complaint+reports"
    )
    filtered_records = filter_sample_source_records(filters)

    assert filters == SourceRecordFilters(
        query="beta",
        jurisdiction="California",
        source_family="CCLD complaint reports",
    )
    assert [record.complaint_control_number for record in filtered_records] == ["SAMPLE-CC-002"]


def test_source_record_list_route_filters_by_query_parameter() -> None:
    status, content_type, body = route_response("/source-records?q=beta")
    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "value=\"beta\"" in html
    assert "Showing 1 of 2 fixture/sample records." in html
    assert "SAMPLE-CC-002" in html
    assert "SAMPLE-CC-001" not in html
    assert "They do not query live public-source data or a database" in " ".join(html.split())


def test_source_record_list_route_shows_sample_no_match_state() -> None:
    status, content_type, body = route_response("/source-records?q=not-a-sample-match")
    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Showing 0 of 2 fixture/sample records." in html
    assert "No fixture/sample records match the current filters." in html
    assert "SAMPLE-CC-001" not in html
    assert "SAMPLE-CC-002" not in html


def test_source_record_detail_route_displays_traceability_fields() -> None:
    status, content_type, body = route_response("/source-records/sample-complaint-001")
    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Read-only sample source-derived detail" in html
    assert "Sample source URL" in html
    assert "https://example.invalid/sample-ccld-source-document-001" in html
    assert "Jurisdiction" in html
    assert "California" in html
    assert "Source family" in html
    assert "CCLD complaint reports" in html
    assert "Source type" in html
    assert "HTML portal/detail page" in html
    assert "Raw SHA-256" in html
    assert "Connector name" in html
    assert "Retrieved at" in html
    assert "Extraction warning" in html
    assert "Sample-only value; not extracted from live public-source data." in html
    assert "Source-derived sample records and future reviewer-created state remain separate" in (
        normalized_html
    )


def test_source_record_list_has_accessible_semantic_structure() -> None:
    status, _content_type, body = route_response("/source-records")
    html = body.decode("utf-8")

    assert status == 200
    parser = assert_source_shell_semantics(
        html,
        expected_title="Sample source-derived records - CCLD Hosted Tester MVP Scaffold",
        expected_h1="Sample source-derived records",
        required_links={"/", "/health", "/source-records/sample-complaint-001"},
    )

    assert parser.tags.count("table") == 1
    normalized_main = " ".join(parser.text_for("main").split())

    assert "Local sample source-derived complaint records" in parser.text_for("caption")
    assert "Complaint control number" in parser.text_for("th")
    assert "Jurisdiction" in parser.text_for("th")
    assert "Source family" in parser.text_for("th")
    assert "Source type" in parser.text_for("th")
    assert "Facility name" in parser.text_for("th")
    assert "Raw SHA-256" in parser.text_for("th")
    assert "Filter sample source records" in parser.text_for("legend")
    assert "Search sample records" in parser.text_for("label")
    assert "Jurisdiction" in parser.text_for("label")
    assert "Source family" in parser.text_for("label")
    assert "These rows are sample-only placeholders" in normalized_main
    assert "They are not imported records" in normalized_main
    assert "not official public-source facts" in normalized_main


def test_source_record_detail_has_accessible_semantic_structure() -> None:
    status, _content_type, body = route_response("/source-records/sample-complaint-001")
    html = body.decode("utf-8")

    assert status == 200
    parser = assert_source_shell_semantics(
        html,
        expected_title="SAMPLE-CC-001 - CCLD Hosted Tester MVP Scaffold",
        expected_h1="SAMPLE-CC-001",
        required_links={"/", "/source-records", "/health"},
    )

    assert parser.tags.count("dl") == 1
    assert "Read-only sample source-derived detail" in parser.text_for("main")
    for label in [
        "Jurisdiction",
        "Source family",
        "Source type",
        "Sample source URL",
        "Raw SHA-256",
        "Connector name",
        "Retrieved at",
        "Report index",
        "Extraction warning",
    ]:
        assert label in parser.text_for("dt")
    assert "https://example.invalid/sample-ccld-source-document-001" in parser.text_for("dd")
    assert "sample-ccld-fixture" in parser.text_for("dd")
    assert "Sample-only value; not extracted from live public-source data." in parser.text_for(
        "dd"
    )


def test_unknown_source_record_detail_returns_not_found() -> None:
    status, content_type, body = route_response("/source-records/not-found")

    assert get_sample_source_record("not-found") is None
    assert status == 404
    assert content_type == "text/plain; charset=utf-8"
    assert body == b"Not found"


def test_smoke_check_hits_health_route_and_app_shell() -> None:
    payload = run_scaffold_smoke_check()

    assert payload["status"] == "ok"
    assert payload["scaffold_only"] is True