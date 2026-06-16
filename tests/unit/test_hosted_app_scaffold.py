from __future__ import annotations

import json
from html.parser import HTMLParser
from pathlib import Path

from ccld_complaints.hosted_app.app import (
    SourceRecordFilters,
    build_source_traceability_summary,
    filter_sample_source_records,
    get_sample_facility_record,
    get_sample_source_record,
    health_response,
    load_sample_facility_records,
    render_app_shell,
    route_response,
    source_record_filters_from_query,
)
from ccld_complaints.hosted_app.auth import load_hosted_auth_runtime_config
from ccld_complaints.hosted_app.smoke import run_scaffold_smoke_check

ROOT = Path(__file__).resolve().parents[2]


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
    assert payload["local_test_reviewer_ui_shell"] is True
    assert payload["review_workflows_implemented"] is False
    assert payload["authentication_implemented"] is False
    assert payload["source_data_loaded"] is False


def test_app_shell_labels_placeholder_boundaries() -> None:
    html = render_app_shell()
    normalized_html = " ".join(html.split())

    assert "Skip to main CCLD review content" in html
    assert '<main id="main-content" tabindex="-1">' in html
    assert "Local/test scaffold only: not a production reviewer workflow." in html
    assert "Request CCLD facility records" in html
    assert "Start here: CCLD facility request" in html
    assert "Start a CCLD review session here" in html
    assert "Start first CCLD review" in html
    assert "Open the suggested queue record in reviewer detail" in normalized_html
    assert "check source traceability, source-confidence cues, and field-note guidance" in (
        normalized_html
    )
    assert "return to the same queue/request context" in normalized_html
    assert "single manual feedback checklist" in normalized_html
    assert "does not save a review session or persist feedback" in normalized_html
    assert "Find a CCLD facility" in html
    assert "facility/license number manually" in normalized_html
    assert "Workflow overview" in html
    assert "Request loaded local/test CCLD records" in normalized_html
    assert "Use reviewer detail to check source traceability" in normalized_html
    assert "No saved review session, persisted queue state, duplicate checklist" in (
        normalized_html
    )
    assert "What the main words mean" in html
    assert "Feedback guidance" in html
    assert "Local/test boundaries" in html
    assert "Browser pages do not run live CCLD retrieval" in html
    assert "Production sign-in, sessions, cookies, exports, deployment" in normalized_html
    assert "Request CCLD records" in html
    assert "How this works" in html
    assert "Review loaded local/test records" in html
    assert "/reviewer" in html


def test_polished_shared_layout_navigation_and_boundaries_on_key_pages() -> None:
    auth_config = load_hosted_auth_runtime_config(
        environ={
            "CCLD_HOSTED_TESTER_AUTH_MODE": "local-dev",
            "CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH": "enabled",
        }
    )
    route_specs = (
        ("/", "Skip to main CCLD review content"),
        ("/ccld/facilities", "Skip to main CCLD facility lookup content"),
        ("/ccld/records/request", "Skip to main CCLD request content"),
        ("/ccld/help", "Skip to main CCLD request content"),
        ("/reviewer", "Skip to main reviewer content"),
        ("/feedback", "Skip to main feedback content"),
    )

    for path, skip_text in route_specs:
        status, content_type, body = route_response(
            path,
            auth_runtime_config=auth_config,
            page_data_mode="fixture-demo",
        )
        html = body.decode("utf-8")
        normalized_html = " ".join(html.split())

        assert status == 200
        assert content_type == "text/html; charset=utf-8"
        assert skip_text in html
        assert '<a class="skip-link" href="#main-content">' in html
        assert '<nav class="site-nav"' in html
        assert '<main id="main-content" tabindex="-1">' in html
        assert 'class="shell page-main"' in html
        assert "Facility Lookup" in html
        assert "CCLD record request" in html
        assert "Retrieval job history" in html
        assert "Feedback" in html
        assert "How this works" in html
        assert "CCLD public portal material remains the source of record" in normalized_html
        assert "does not prove source completeness" in normalized_html
        assert "legal findings" in normalized_html
        assert "button:focus-visible" in html
        assert "@media (max-width: 760px)" in html


def test_routes_return_shell_health_and_not_found() -> None:
    root_status, root_content_type, root_body = route_response("/")
    health_status, health_content_type, health_body = route_response("/health")
    api_status, api_content_type, api_body = route_response("/api/health")
    missing_status, missing_content_type, missing_body = route_response("/missing")

    assert root_status == 200
    assert root_content_type == "text/html; charset=utf-8"
    assert b"not a production reviewer workflow" in root_body
    assert health_status == 200
    assert health_content_type == "application/json; charset=utf-8"
    assert json.loads(health_body)["status"] == "ok"
    assert api_status == 200
    assert api_content_type == "application/json; charset=utf-8"
    assert json.loads(api_body)["service"] == "hosted-tester-mvp-scaffold"
    assert missing_status == 404
    assert missing_content_type == "text/plain; charset=utf-8"
    assert missing_body == b"Not found"


def test_auth_placeholders_and_status_are_no_secret() -> None:
    login_status, login_content_type, login_body = route_response("/auth/login")
    logout_status, logout_content_type, logout_body = route_response("/auth/logout")
    status_status, status_content_type, status_body = route_response("/auth/status")

    login_html = login_body.decode("utf-8")
    logout_html = logout_body.decode("utf-8")
    auth_payload = json.loads(status_body)

    assert login_status == 200
    assert login_content_type == "text/html; charset=utf-8"
    assert "Managed OIDC sign-in not configured" in login_html
    assert "does not exchange auth codes" in login_html
    assert logout_status == 200
    assert logout_content_type == "text/html; charset=utf-8"
    assert "No browser session is created" in logout_html
    assert status_status == 200
    assert status_content_type == "application/json; charset=utf-8"
    assert auth_payload["auth"]["mode"] == "production"
    serialized = (login_html + logout_html + status_body.decode("utf-8")).casefold()
    assert "provider_subject" not in serialized
    assert "provider_issuer" not in serialized
    assert "client_secret" not in serialized


def test_production_mode_blocks_anonymous_workflow_routes() -> None:
    reviewer_status, reviewer_content_type, reviewer_body = route_response("/reviewer")
    ccld_status, ccld_content_type, ccld_body = route_response("/ccld")
    help_status, help_content_type, help_body = route_response("/ccld/help")

    assert reviewer_status == 401
    assert reviewer_content_type == "text/html; charset=utf-8"
    assert "Reviewer access requires sign-in" in reviewer_body.decode("utf-8")
    assert ccld_status == 401
    assert ccld_content_type == "text/html; charset=utf-8"
    assert "CCLD workflow access requires sign-in" in ccld_body.decode("utf-8")
    assert help_status == 200
    assert help_content_type == "text/html; charset=utf-8"
    assert "How CCLD review works" in help_body.decode("utf-8")


def test_explicit_local_dev_auth_mode_allows_default_workflow_actor() -> None:
    auth_config = load_hosted_auth_runtime_config(
        environ={
            "CCLD_HOSTED_TESTER_AUTH_MODE": "local-dev",
            "CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH": "enabled",
        }
    )

    reviewer_status, _content_type, reviewer_body = route_response(
        "/reviewer",
        auth_runtime_config=auth_config,
        page_data_mode="fixture-demo",
    )
    ccld_status, _content_type, ccld_body = route_response(
        "/ccld",
        auth_runtime_config=auth_config,
        page_data_mode="fixture-demo",
    )

    reviewer_html = reviewer_body.decode("utf-8")
    ccld_html = ccld_body.decode("utf-8")

    assert reviewer_status == 200
    assert "Signed in as Local Test Reviewer" in reviewer_html
    assert "provider_subject" not in reviewer_html
    assert "provider_issuer" not in reviewer_html
    assert ccld_status == 200
    assert "CCLD record request" in ccld_html


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
    assert "Sample source traceability summary" in html
    assert "2 of 2 fixture/sample records" in html
    assert "Jurisdictions represented" in html
    assert "Source families represented" in html
    assert "Visible sample traceability fields in the current result set" in html
    assert "Raw SHA-256" in html
    assert "sample-complaint-001" in html


def test_load_sample_facility_records_uses_committed_public_source_fixtures() -> None:
    records = load_sample_facility_records()

    assert len(records) == 4
    assert {record.source_fixture for record in records} == {
        "ccld_program_facilities_tiny.csv",
        "chhs_facility_master_tiny.csv",
    }
    assert {record.facility_number for record in records} == {"900000001", "900000002"}
    assert {record.facility_name for record in records} == {
        "Synthetic Orchard Child Care",
        "Synthetic Valley Family Agency",
    }
    assert {record.source_family for record in records} == {
        "ccld-public-download",
        "chhs-facility-master",
    }
    assert all(record.jurisdiction == "California" for record in records)
    assert all(record.source_url.startswith("https://example.invalid/") for record in records)
    assert all(len(record.raw_sha256) == 64 for record in records)


def test_source_record_filter_query_uses_sample_records_only() -> None:
    filters = source_record_filters_from_query(
        "q=valley&jurisdiction=California&source_family=CCLD+complaint+reports"
    )
    filtered_records = filter_sample_source_records(filters)

    assert filters == SourceRecordFilters(
        query="valley",
        jurisdiction="California",
        source_family="CCLD complaint reports",
    )
    assert [record.complaint_control_number for record in filtered_records] == ["SAMPLE-CC-002"]


def test_facility_list_route_labels_fixture_read_only_scope() -> None:
    status, content_type, body = route_response("/facilities")
    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Sample facility master records" in html
    assert "Read-only facility master sample view" in html
    assert "Fixture/sample data only" in html
    assert "No live public-source data is loaded" in html
    assert "committed tiny public-source facility fixtures" in normalized_html
    assert "does not read ignored raw CSVs" in normalized_html
    assert "generated profiling outputs" in normalized_html
    assert "SQLite, a hosted database, or an import/sync process" in normalized_html
    assert "No reviewer workflow is active" in html
    assert "no authentication is implemented" in html
    assert "no reviewer-created state is persisted" in html
    assert "Source-derived sample records and future reviewer-created state remain separate" in (
        normalized_html
    )
    assert "not official facility lists" in normalized_html
    assert "complete statewide coverage" in normalized_html
    assert "legal or facility-wide conclusions" in normalized_html
    assert "Synthetic Orchard Child Care" in html
    assert "Synthetic Valley Family Agency" in html
    assert "ccld_program_facilities_tiny.csv" in html
    assert "chhs_facility_master_tiny.csv" in html
    assert "ccld-program-facilities-tiny-900000001" in html


def test_facility_detail_route_displays_manifest_traceability_metadata() -> None:
    status, content_type, body = route_response("/facilities/chhs-facility-master-tiny-900000001")
    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Read-only facility fixture detail" in html
    assert "Synthetic Orchard Child Care" in html
    assert "Facility number" in html
    assert "900000001" in html
    assert "Facility type" in html
    assert "Child Care Center" in html
    assert "Program type" in html
    assert "Child Care" in html
    assert "County" in html
    assert "Los Angeles" in html
    assert "Source family" in html
    assert "chhs-facility-master" in html
    assert "Source fixture" in html
    assert "chhs_facility_master_tiny.csv" in html
    assert "Profiled source shape" in html
    assert "CalHHS/CHHS 21- or 22-column facility master download" in html
    assert "Source URL placeholder" in html
    assert "https://example.invalid/chhs-community-care-licensing-facilities" in html
    assert "Raw SHA-256 placeholder" in html
    assert "1111111111111111111111111111111111111111111111111111111111111111" in html
    assert "Retrieved at placeholder" in html
    assert "2026-06-07T00:00:00Z" in html
    assert "does not read ignored raw CSVs" in normalized_html
    assert "Sample source coverage" in html
    assert "Fixture source coverage indicators for this sample facility" in html
    assert "fixture metadata available" in html
    assert "sample source-record context available" in html
    assert "unknown/not implemented; not live data" in html
    assert "not imported data and not database-backed" in html
    assert "not assessed; no completeness conclusion" in html
    assert "do not prove public-source completeness" in normalized_html
    assert "legal, facility-wide, delay, harm, abuse, neglect, liability" in normalized_html
    assert "Related fixture/sample source-record context" in html
    assert "/source-records/sample-complaint-001" in html
    assert "SAMPLE-CC-001 for Synthetic Orchard Child Care" in normalized_html


def test_facility_detail_route_shows_unmapped_fixture_sample_coverage_state() -> None:
    status, content_type, body = route_response(
        "/facilities/ccld-program-facilities-tiny-900000001"
    )
    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Sample source coverage" in html
    assert "not represented in this fixture/sample mapping" in html
    assert "No related fixture/sample source-record context" in normalized_html
    assert "/source-records/sample-complaint-001" not in html
    assert "not a public-source completeness conclusion" not in normalized_html
    assert "do not prove public-source completeness" in normalized_html


def test_unknown_facility_detail_returns_not_found() -> None:
    status, content_type, body = route_response("/facilities/not-found")

    assert get_sample_facility_record("not-found") is None
    assert status == 404
    assert content_type == "text/plain; charset=utf-8"
    assert body == b"Not found"


def test_source_traceability_summary_uses_filtered_sample_records() -> None:
    filters = SourceRecordFilters(query="valley")
    filtered_records = filter_sample_source_records(filters)
    summary = build_source_traceability_summary(filtered_records)

    assert summary.total_records == 1
    assert summary.complete_record_count == 1
    assert summary.jurisdictions == ("California",)
    assert summary.source_families == ("CCLD complaint reports",)
    assert {field.label: field.present_count for field in summary.fields} == {
        "Sample source URL": 1,
        "Raw SHA-256": 1,
        "Connector name": 1,
        "Retrieved at": 1,
        "Report index": 1,
        "Extraction warning": 1,
        "Jurisdiction": 1,
        "Source family": 1,
    }


def test_source_record_list_route_filters_by_query_parameter() -> None:
    status, content_type, body = route_response("/source-records?q=valley")
    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "value=\"valley\"" in html
    assert "Showing 1 of 2 fixture/sample records." in html
    assert "1 of 1 fixture/sample records" in html
    assert "SAMPLE-CC-002" in html
    assert "SAMPLE-CC-001" not in html
    assert "They do not query live public-source data or a database" in " ".join(html.split())


def test_source_record_list_route_shows_sample_no_match_state() -> None:
    status, content_type, body = route_response("/source-records?q=not-a-sample-match")
    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Showing 0 of 2 fixture/sample records." in html
    assert "0 of 0 fixture/sample records" in html
    assert "None in the current fixture/sample result set" in html
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
    assert "Sample source traceability block" in html
    assert "visible sample traceability metadata" in html
    assert "do not verify a live public-source record" in normalized_html
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
    assert "Related sample facility context" in html
    assert "not imported data, not database-backed, not live public-source coverage" in (
        normalized_html
    )
    assert "/facilities/chhs-facility-master-tiny-900000001" in html
    assert "Synthetic Orchard Child Care from chhs_facility_master_tiny.csv" in normalized_html


def test_source_record_list_has_accessible_semantic_structure() -> None:
    status, _content_type, body = route_response("/source-records")
    html = body.decode("utf-8")

    assert status == 200
    parser = assert_source_shell_semantics(
        html,
        expected_title="Sample source-derived records - CCLD Records Review",
        expected_h1="Sample source-derived records",
        required_links={"/", "/health", "/source-records/sample-complaint-001"},
    )

    assert parser.tags.count("table") == 2
    normalized_main = " ".join(parser.text_for("main").split())

    assert "Sample source traceability summary" in parser.text_for("h2")
    assert "Visible sample traceability fields in the current result set" in parser.text_for(
        "caption"
    )
    assert "Traceability-style field" in parser.text_for("th")
    assert "Fixture/sample records with visible value" in parser.text_for("th")
    assert "Sample source URL" in parser.text_for("th")
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
    assert "does not verify live public-source completeness" in normalized_main
    assert "does not read from a database" in normalized_main


def test_source_record_detail_has_accessible_semantic_structure() -> None:
    status, _content_type, body = route_response("/source-records/sample-complaint-001")
    html = body.decode("utf-8")

    assert status == 200
    parser = assert_source_shell_semantics(
        html,
        expected_title="SAMPLE-CC-001 - CCLD Records Review",
        expected_h1="SAMPLE-CC-001",
        required_links={
            "/",
            "/source-records",
            "/facilities/chhs-facility-master-tiny-900000001",
            "/health",
        },
    )

    assert parser.tags.count("dl") == 1
    normalized_main = " ".join(parser.text_for("main").split())

    assert "Sample source traceability block" in parser.text_for("main")
    assert "Related sample facility context" in parser.text_for("h2")
    assert "not imported data" in normalized_main
    assert "not live public-source coverage" in normalized_main
    assert "do not verify a live public-source record" in normalized_main
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


def test_facility_list_has_accessible_semantic_structure() -> None:
    status, _content_type, body = route_response("/facilities")
    html = body.decode("utf-8")

    assert status == 200
    parser = assert_source_shell_semantics(
        html,
        expected_title="Sample facility master records - CCLD Records Review",
        expected_h1="Sample facility master records",
        required_links={
            "/",
            "/source-records",
            "/health",
            "/facilities/chhs-facility-master-tiny-900000001",
        },
    )

    assert parser.tags.count("table") == 1
    normalized_main = " ".join(parser.text_for("main").split())

    assert "Facility fixture scope" in parser.text_for("h2")
    assert "Read-only facility master sample view" in parser.text_for("h2")
    assert "Committed tiny public-source facility fixture rows" in parser.text_for("caption")
    for label in [
        "Facility number",
        "Facility name",
        "Facility type",
        "Program type",
        "County",
        "Status",
        "Capacity",
        "Source family",
        "Source fixture",
    ]:
        assert label in parser.text_for("th")
    assert "committed tiny public-source facility fixtures" in normalized_main
    assert "does not read ignored raw CSVs" in normalized_main
    assert "not official facility lists" in normalized_main


def test_facility_detail_has_accessible_semantic_structure() -> None:
    status, _content_type, body = route_response(
        "/facilities/ccld-program-facilities-tiny-900000002"
    )
    html = body.decode("utf-8")

    assert status == 200
    parser = assert_source_shell_semantics(
        html,
        expected_title="900000002 - CCLD Records Review",
        expected_h1="900000002",
        required_links={"/", "/facilities", "/source-records", "/health"},
    )

    assert parser.tags.count("dl") == 2
    assert parser.tags.count("table") == 1
    normalized_main = " ".join(parser.text_for("main").split())

    assert "Read-only facility fixture detail" in parser.text_for("h2")
    assert "Sample source coverage" in parser.text_for("h2")
    assert "Related fixture/sample source-record context" in parser.text_for("h3")
    assert "Fixture source coverage indicators for this sample facility" in parser.text_for(
        "caption"
    )
    assert "Coverage indicator" in parser.text_for("th")
    assert "Fixture/sample status" in parser.text_for("th")
    assert "not represented in this fixture/sample mapping" in normalized_main
    assert "No related fixture/sample source-record context" in normalized_main
    assert "do not prove public-source completeness" in normalized_main
    for label in [
        "Facility name",
        "Facility number",
        "Facility type",
        "Program type",
        "County",
        "Status",
        "Capacity",
        "Source family",
        "Jurisdiction",
        "Source fixture",
        "Profiled source shape",
        "Source dataset reference",
        "Source URL placeholder",
        "Raw SHA-256 placeholder",
        "Retrieved at placeholder",
    ]:
        assert label in parser.text_for("dt")
    assert "Synthetic Valley Family Agency" in parser.text_for("dd")
    assert "CCLD 31-column program-specific facility download" in parser.text_for("dd")
    assert "ccld-public-download" in parser.text_for("dd")
    assert "does not read ignored raw CSVs" in normalized_main


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


def test_normal_scaffold_script_does_not_enable_retrieval_demo() -> None:
    script = (ROOT / "scripts" / "run-hosted-scaffold.ps1").read_text(encoding="utf-8")

    assert "CCLD_RETRIEVAL_ENABLED" not in script
    assert "CCLD_RETRIEVAL_RAW_DIR" not in script
    assert "CCLD_RETRIEVAL_DEMO_MODE" not in script
    assert "mock-success" not in script


def test_complaint_retrieval_demo_script_sets_safe_local_config() -> None:
    script_path = ROOT / "scripts" / "run-hosted-complaint-retrieval-demo.ps1"
    script = script_path.read_text(encoding="utf-8")

    assert script_path.exists()
    assert "data\\raw\\ccld\\retrieval-demo" in script
    assert 'CCLD_HOSTED_TESTER_AUTH_MODE = "local-dev"' in script
    assert 'CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH = "enabled"' in script
    assert 'CCLD_HOSTED_PAGE_DATA_MODE = "fixture-demo"' in script
    assert 'CCLD_RETRIEVAL_ENABLED = "enabled"' in script
    assert "CCLD_RETRIEVAL_RAW_DIR = $resolvedRawStorageDir" in script
    assert 'CCLD_RETRIEVAL_DEMO_MODE = "mock-success"' in script
    assert 'CCLD_RETRIEVAL_MAX_DATE_RANGE_DAYS = "30"' in script
    assert "New-Item -ItemType Directory -Force -Path $resolvedRawStorageDir" in script
    assert "Open: $baseUrl/" in script
    assert "Open: $baseUrl/ccld/records/request" in script
    assert "Open: $baseUrl/ccld/retrieval/jobs" in script
    assert "Open: $baseUrl/reviewer" in script
    assert "not production CCLD completeness proof" in script
    assert "GITHUB" not in script
    assert "TOKEN" not in script
    assert "COOKIE" not in script


def test_complaint_retrieval_demo_raw_storage_path_is_gitignored() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    script = (ROOT / "scripts" / "run-hosted-complaint-retrieval-demo.ps1").read_text(
        encoding="utf-8"
    )

    assert "data/raw/*" in gitignore
    assert 'data\\raw\\ccld\\retrieval-demo' in script