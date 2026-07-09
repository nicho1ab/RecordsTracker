from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path

from pytest import MonkeyPatch

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
HOSTED_RUNTIME_ENV_KEYS = (
    "CCLD_HOSTED_TESTER_AUTH_MODE",
    "CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH",
    "CCLD_HOSTED_PAGE_DATA_MODE",
    "CCLD_RETRIEVAL_DEMO_MODE",
    "CCLD_RETRIEVAL_ENABLED",
    "CCLD_RETRIEVAL_RAW_DIR",
)


def clear_hosted_runtime_env(monkeypatch: MonkeyPatch) -> None:
    for key in HOSTED_RUNTIME_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


class HtmlStructureParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[str] = []
        self.links: list[str] = []
        self.summary_texts: list[str] = []
        self.start_attrs_by_tag: dict[str, list[dict[str, str]]] = {}
        self.text_by_tag: dict[str, list[str]] = {}
        self._stack: list[str] = []
        self._current_summary_parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag)
        self._stack.append(tag)
        if tag == "summary":
            self._current_summary_parts = []
        attr_dict = {name: value for name, value in attrs if value is not None}
        self.start_attrs_by_tag.setdefault(tag, []).append(attr_dict)
        if tag == "a":
            for name, value in attrs:
                if name == "href" and value is not None:
                    self.links.append(value)

    def handle_endtag(self, tag: str) -> None:
        if tag == "summary" and self._current_summary_parts is not None:
            self.summary_texts.append(" ".join(self._current_summary_parts).strip())
            self._current_summary_parts = None
        if tag in self._stack:
            while self._stack:
                open_tag = self._stack.pop()
                if open_tag == tag:
                    break

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        if self._current_summary_parts is not None and "summary" in self._stack:
            self._current_summary_parts.append(text)
        for tag in self._stack:
            self.text_by_tag.setdefault(tag, []).append(text)

    def text_for(self, tag: str) -> str:
        return " ".join(self.text_by_tag.get(tag, []))


def parse_html_structure(markup: str) -> HtmlStructureParser:
    parser = HtmlStructureParser()
    parser.feed(markup)
    return parser


def assert_no_buttons_inside_list_items(markup: str) -> None:
    assert not re.search(
        r"<li\b(?![^>]*role=\"option\")[^>]*>(?:(?!</li>).)*(?:<button\b|class=\"[^\"]*\bbutton\b)",
        markup,
        flags=re.DOTALL,
    )


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
    assert "source_data_loaded" in payload


def test_app_shell_labels_placeholder_scope(monkeypatch: MonkeyPatch) -> None:
    clear_hosted_runtime_env(monkeypatch)

    html = render_app_shell()
    normalized_html = " ".join(html.split())
    parser = parse_html_structure(html)

    assert "Skip to main CCLD facility lookup content" in html
    assert '<main id="main-content" class="ds-page-main app-page" tabindex="-1">' in html
    assert "CCLD-only public-record review workspace." not in html
    assert "CCLD RecordsTracker" in html
    assert '<a class="product-name" href="/">Records<span>Tracker</span></a>' in html
    assert '<span class="workspace-label">Reviewer Workspace</span>' in html
    assert (
        '<form class="shell-lookup" action="/ccld/facilities" method="get" role="search">'
        in html
    )
    assert (
        '<label class="sr-only" for="shell-facility-search">'
        "Search complaint, facility, Facility ID, or source record</label>"
        in html
    )
    assert (
        '<label class="sr-only" for="shell-facility-search">Search facilities</label>'
        not in html
    )
    assert 'placeholder="Search complaint, facility, Facility ID, or source record..."' in html
    assert "Search complaint, facility, license, or source record" not in html
    assert parser.tags.count("h1") == 1
    assert parser.text_for("h1") == "Find a Facility"
    assert parser.text_for("h1") != "CCLD RecordsTracker"
    assert "Review aids only" in html
    assert "Find a Facility" in html
    assert "Facility intake" in html
    assert "Find a facility" in html
    assert '<form action="/ccld/facilities" method="get" class="facility-search-form">' in html
    assert 'for="facility-search-input"' in html
    assert 'placeholder="Name, Facility ID, city, or ZIP"' in html
    assert "Search CCLD facilities" in html
    assert 'class="selected-facility-request-form"' in html
    assert "Continue to Request Records" in html
    assert "Change selected facility" in html
    assert (
        '<summary id="manual-entry-heading">'
        "Enter a Facility ID directly</summary>"
    ) in html
    assert (
        "Start review by finding the CCLD Facility ID in the preloaded "
        "facility directory"
        in html
    )
    assert "then carry that selected facility into the request page" in html
    assert "Review path" not in html
    assert "1. Find the facility" not in html
    assert "2. Request records" not in html
    assert "3. Review complaints" not in html
    assert 'href="/reviewer">Open review queue</a>' not in html
    assert 'href="/reviewer/packet/preview">Open packet preview</a>' not in html
    assert "workflow_area=entry-orientation" not in html
    assert "Attorney-focused public CCLD complaint/facility record review" not in html
    assert "New to this tool?" not in html
    assert "See Help for the review workflow" not in html
    assert "Open review queue" not in html
    assert "Feedback" in html
    assert "Developer/operator commands" not in html
    assert "Local pilot runtime" not in html
    assert "Live public CCLD retrieval" not in html
    assert "Fixture/mock demo" not in html
    assert "Starts the local pilot runtime" not in html
    assert '<section class="action-card"' not in html
    assert "Commands</a>" not in html
    assert "Health check</a>" not in html
    assert "No non-CCLD sources" not in normalized_html
    assert "Public records stay separate from saved notes/status" not in html
    assert "/reviewer" in html
    assert "sr-only" in html
    assert "Keyboard flow: use the skip link, top navigation, and step links" not in html
    assert "current step and next action are stated in text" not in html
    assert "Start facility complaint review." not in html
    assert "Select the Facility ID." not in html
    assert "Choose the complaint date range." not in html
    assert_no_buttons_inside_list_items(html)


def test_home_orientation_uses_shared_facility_start_experience() -> None:
    html = render_app_shell()
    normalized_html = " ".join(html.split())

    assert "First-time tester orientation" not in html
    assert "Tester task guide" not in html
    assert "Expected:" not in html
    assert "Review path" not in html
    assert "1. Find the facility" not in normalized_html
    assert "2. Request records" not in normalized_html
    assert "3. Review complaints" not in normalized_html
    assert "Facility intake" in html
    assert "Find the Facility ID" in html
    assert "Search CCLD facilities" in html
    assert "Continue to Request Records" in html
    assert "Change selected facility" in html
    assert "Optional planning views" in html
    assert "workflow_area=entry-orientation" not in html
    assert "page_path=%2F" not in html
    assert "saved session" not in normalized_html.casefold()
    assert "persisted queue state" not in normalized_html.casefold()
    assert "source-completeness proof" not in normalized_html.casefold()
    assert "legal conclusion" not in normalized_html.casefold()
    assert_no_buttons_inside_list_items(html)


def test_home_and_facility_routes_share_find_facility_start_workflow() -> None:
    root_status, root_content_type, root_body = route_response("/")
    facility_status, facility_content_type, facility_body = route_response(
        "/ccld/facilities",
        page_data_mode="fixture-demo",
    )
    root_html = root_body.decode("utf-8")
    facility_html = facility_body.decode("utf-8")

    assert root_status == 200
    assert facility_status == 200
    assert root_content_type == facility_content_type == "text/html; charset=utf-8"
    for html in (root_html, facility_html):
        assert "Find a Facility" in html
        assert "Facility intake" in html
        assert "Find the Facility ID" in html
        assert "Search CCLD facilities" in html
        assert "Continue to Request Records" in html
        assert "Change selected facility" in html
        assert "Review path" not in html
        assert "1. Find the facility" not in html
        assert "Open review queue" not in html
        assert_no_buttons_inside_list_items(html)


def test_guided_attorney_review_workflow_acceptance_route_markers(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "CCLD_FACILITY_REFERENCE_CSV",
        str(
            ROOT
            / "tests"
            / "fixtures"
            / "public_source_facilities"
            / "ccld_program_facilities_tiny.csv"
        ),
    )
    auth_config = load_hosted_auth_runtime_config(
        environ={
            "CCLD_HOSTED_TESTER_AUTH_MODE": "local-dev",
            "CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH": "enabled",
        }
    )
    route_specs = (
        (
            "entry",
            "/",
            (
                "Find a Facility",
                "Facility intake",
                "Find the Facility ID",
                "Search CCLD facilities",
                "Continue to Request Records",
            ),
        ),
        (
            "facility review",
            "/ccld/facilities/detail?facility_number=900000001",
            (
                "Facility pattern review summary",
                "Review next",
                "Packet readiness",
                "Request records for this facility before preparing packet content.",
            ),
        ),
        (
            "prioritized records",
            "/reviewer",
            (
                "Complaint records ready for review",
                "Review cue summary",
                "Worklist",
                "Open record",
            ),
        ),
        (
            "packet preview",
            (
                "/reviewer/packet/preview?facility_number=157806098"
                "&start_date=2022-08-01&end_date=2022-08-31"
            ),
            (
                "Packet preview",
                "Included complaint records",
                "Readiness checks",
                "Copy-ready brief",
            ),
        ),
        (
            "packet draft",
            (
                "/reviewer/packet/draft?facility_number=157806098"
                "&start_date=2022-08-01&end_date=2022-08-31"
            ),
            (
                "Attorney Review Packet Draft",
                "Copy-ready attorney review brief",
                "Attorney review readiness checklist",
            ),
        ),
    )

    for route_name, path, markers in route_specs:
        status, content_type, body = route_response(
            path,
            auth_runtime_config=auth_config,
            page_data_mode="fixture-demo",
        )
        html = body.decode("utf-8")

        assert status == 200, f"{route_name}: expected 200 for {path}, got {status}"
        assert content_type == "text/html; charset=utf-8"
        for marker in markers:
            assert marker in html, f"{route_name}: missing acceptance marker {marker!r}"


def test_polished_shared_layout_navigation_on_key_pages() -> None:
    auth_config = load_hosted_auth_runtime_config(
        environ={
            "CCLD_HOSTED_TESTER_AUTH_MODE": "local-dev",
            "CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH": "enabled",
        }
    )
    route_specs = (
        ("/", "Skip to main CCLD facility lookup content"),
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
        assert "CCLD-only public-record review workspace." not in html
        assert skip_text in html
        assert '<a class="skip-link" href="#main-content">' in html
        assert '<header class="app-shell-header site-header ds-surface">' in html
        assert '<nav class="primary-nav site-nav"' in html
        assert '<main id="main-content" class="ds-page-main app-page" tabindex="-1">' in html
        assert 'class="shell page-main app-page-main"' in html
        assert "CCLD RecordsTracker" in html
        assert '<a class="product-name" href="/">Records<span>Tracker</span></a>' in html
        assert '<span class="workspace-label">Reviewer Workspace</span>' in html
        assert (
            '<form class="shell-lookup" action="/ccld/facilities" method="get" role="search">'
            in html
        )
        assert (
            '<label class="sr-only" for="shell-facility-search">'
            "Search complaint, facility, Facility ID, or source record</label>"
            in html
        )
        assert (
            '<label class="sr-only" for="shell-facility-search">Search facilities</label>'
            not in html
        )
        assert 'placeholder="Search complaint, facility, Facility ID, or source record..."' in html
        assert "Search complaint, facility, license, or source record" not in html
        if path != "/ccld/help":
            assert "Attorney workflow" not in html
            assert "Current step" not in html
            assert "Next:" not in html
            assert "Keyboard flow:" not in html
        else:
            assert "Attorney workflow" not in html
            assert "Current step" not in html
        assert "Future step" not in html
        assert 'href="/ccld/facilities">Facility</a>' not in html
        assert 'href="/ccld/facilities">Facilities</a>' in html
        assert 'href="/">Home</a>' in html
        assert 'href="/ccld/records/request">Request Records</a>' in html
        assert 'href="/ccld/records/request">Retrieve</a>' not in html
        assert "Review" in html
        assert 'href="/ccld/retrieval/jobs">Job Status</a>' not in html
        assert 'href="/ccld/retrieval/jobs">Job diagnostics</a>' not in html
        assert 'href="/ccld/retrieval/jobs">Jobs</a>' not in html
        assert "Feedback" in html
        assert 'href="/feedback">Feedback</a>' in html
        assert "Feedbac k" not in html
        assert "Commands</a>" not in html
        assert "Health check</a>" not in html
        assert "Auth status</a>" not in html
        assert "Help" in html
        if path != "/ccld/help":
            assert "facility-wide conclusions, harm, abuse" not in normalized_html
            assert "neglect, liability, or rights-deprivation" not in normalized_html
        assert "button:focus-visible" in html
        assert ".sr-only" in html
        assert "@media (max-width: 760px)" in html
        if path in {"/", "/ccld/facilities", "/feedback", "/ccld/help"}:
            assert_no_buttons_inside_list_items(html)


def test_representative_hosted_pages_do_not_render_shared_footer_disclaimer() -> None:
    auth_config = load_hosted_auth_runtime_config(
        environ={
            "CCLD_HOSTED_TESTER_AUTH_MODE": "local-dev",
            "CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH": "enabled",
        }
    )
    removed_footer_phrases = (
        "Public records stay separate from saved notes/status",
        "facility-wide conclusions, harm, abuse",
        "neglect, liability, or rights-deprivation",
    )

    for path in ("/", "/ccld/records/request", "/reviewer", "/feedback"):
        status, _content_type, body = route_response(
            path,
            auth_runtime_config=auth_config,
            page_data_mode="fixture-demo",
        )
        html = body.decode("utf-8")
        normalized_html = " ".join(html.split())

        assert status == 200
        assert '<footer class="site-footer">' not in html
        for phrase in removed_footer_phrases:
            assert phrase not in normalized_html


def test_final_product_shell_uses_compact_unboxed_workflow_design() -> None:
    html = render_app_shell()

    assert "--ds-page-bg: #F2F4F7" in html
    assert "--ds-surface: #ffffff" in html
    assert "--ds-text: #17212B" in html
    assert "--ds-primary: #0D6E6E" in html
    assert "--ds-link: #2457A6" in html
    assert "--ds-nav-active-bg: #EEF3FA" in html
    assert "--ds-nav-active-border: #9DB4D6" in html
    assert '--ds-font-display: "Libre Baskerville", Georgia' in html
    assert '--ds-font-ui: "DM Sans", "Segoe UI"' in html
    assert '--ds-font-mono: "DM Mono", "SFMono-Regular"' in html
    assert "--teal: var(--ds-primary)" in html
    assert ".app-shell" in html
    assert ".app-shell-compact" in html
    assert ".brand-title-block" in html
    assert ".workspace-label" in html
    assert ".shell-lookup" in html
    assert ".shell-nav-cluster" in html
    shell_row_start = html.index('class="brand-title-row site-title-row"')
    shell_row_end = html.index("</header>", shell_row_start)
    shell_row_html = html[shell_row_start:shell_row_end]
    shell_regions = (
        'class="brand-title-block brand-block"',
        'class="shell-lookup"',
        'class="shell-nav-cluster"',
        'class="primary-nav site-nav"',
        'class="mode-panel"',
    )
    previous_region_index = -1
    for region in shell_regions:
        region_index = shell_row_html.index(region)
        assert region_index > previous_region_index
        previous_region_index = region_index
    assert (
        "grid-template-columns: minmax(10rem, 12rem) minmax(16rem, 30rem) max-content"
        in html
    )
    assert "min-width: max-content" in html
    facts_bar_css = (
        ".top-fact-strip {\n"
        "      background: #F8FAFB;\n"
        "      border: 1px solid var(--line-soft);\n"
        "      border-radius: 8px;\n"
        "      display: grid;"
    )
    assert facts_bar_css in html
    assert (
        "grid-template-columns: minmax(7.5rem, 0.8fr) minmax(18rem, 2.3fr)"
        in html
    )
    assert ".compact-fact--name" in html
    assert "-webkit-line-clamp: 2" in html
    assert ".compact-fact--status dd" in html
    assert ".rt-timeline {" in html
    assert "--timeline-line-top: calc(1rem + (var(--timeline-marker-size) / 2));" in html
    assert ".rt-timeline__line {" in html
    assert ".rt-timeline.has-gap .rt-timeline__line::after" in html
    assert "left: 25%;" in html
    assert "top: calc(var(--timeline-line-top) - 0.68rem);" in html
    assert "transform: translateX(-50%);" in html
    assert "width: max-content;" in html
    assert "border-radius: 5px;" in html
    assert "top: 0;\n      width: 25%;" not in html
    assert "top: calc(var(--timeline-line-top) - (var(--timeline-marker-size) / 2)" not in html
    assert ".app-page-main" in html
    assert ".ds-card--neutral" in html
    assert ".ds-card--info" in html
    assert ".ds-card--success" in html
    assert ".ds-form-control" in html
    assert ".ds-table" in html
    assert "section {" in html
    assert "box-shadow: var(--shadow);\n      margin: 0 0 1rem;\n      padding: 1rem;" not in html
    assert ".guided-stepper" in html
    assert "border-bottom: 1px solid var(--line-soft)" in html
    assert ".stepper-item.is-current" in html
    assert "border-bottom: 3px solid var(--blue)" in html
    assert ".step-index" in html
    assert "display: none;" in html
    assert '<nav class="primary-nav site-nav"' in html
    assert "Health check</a>" not in html
    assert "Commands</a>" not in html


def test_decorative_kickers_are_muted_and_navigation_uses_blue_neutral_states() -> None:
    html = render_app_shell()

    for selector in (".stepper-eyebrow", ".launch-kicker", ".stage-kicker"):
        selector_start = html.index(f"    {selector} {{")
        selector_end = html.index("    }", selector_start)
        selector_css = html[selector_start:selector_end]

        assert "color: var(--muted);" in selector_css
        assert "pointer-events: none;" in selector_css
        assert "color: var(--accent-strong);" not in selector_css

    assert "a {\n      color: var(--ds-link);" in html
    nav_active_css = (
        ".site-nav a.is-active {\n"
        "      background: transparent;\n"
        "      border-color: transparent;\n"
        "      box-shadow: inset 0 -2px 0 var(--ds-link);"
    )
    assert nav_active_css in html
    assert ".site-nav a:hover, .site-nav a.is-active" not in html
    assert "background: var(--accent-soft);\n      border-color: var(--accent);" not in html
    button_secondary_css = (
        ".button-secondary, button.secondary {\n"
        "      background: #fff;\n"
        "      border-color: var(--ds-border);\n"
        "      color: var(--ds-link);"
    )
    assert button_secondary_css in html
    assert "button, input[type=\"submit\"], .button {\n      background: var(--accent);" in html


def test_routes_return_shell_health_and_not_found() -> None:
    root_status, root_content_type, root_body = route_response("/")
    health_status, health_content_type, health_body = route_response("/health")
    api_status, api_content_type, api_body = route_response("/api/health")
    missing_status, missing_content_type, missing_body = route_response("/missing")

    assert root_status == 200
    assert root_content_type == "text/html; charset=utf-8"
    assert b"CCLD-only public-record review workspace" not in root_body
    assert b"Find the Facility ID" in root_body
    assert health_status == 200
    assert health_content_type == "application/json; charset=utf-8"
    assert json.loads(health_body)["status"] == "ok"
    assert api_status == 200
    assert api_content_type == "application/json; charset=utf-8"
    assert json.loads(api_body)["service"] == "hosted-tester-mvp-scaffold"
    assert missing_status == 404
    assert missing_content_type == "text/plain; charset=utf-8"
    assert missing_body == b"Not found"


def test_auth_placeholders_and_status_are_no_secret(monkeypatch: MonkeyPatch) -> None:
    clear_hosted_runtime_env(monkeypatch)

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


def test_production_mode_blocks_anonymous_workflow_routes(
    monkeypatch: MonkeyPatch,
) -> None:
    clear_hosted_runtime_env(monkeypatch)

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
    assert "How CCLD RecordsTracker works" in help_body.decode("utf-8")


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
    assert "Signed in as Local Test Reviewer" not in reviewer_html
    assert "Source-traceable complaint review." not in reviewer_html
    assert "provider_subject" not in reviewer_html
    assert "provider_issuer" not in reviewer_html
    assert ccld_status == 200
    assert "Request Records" in ccld_html


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
    assert "Use the sample indicators to inspect fixture relationships" in normalized_html
    assert "related sample source-record pages" in normalized_html
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
    assert "Use the sample indicators to inspect fixture relationships" in normalized_html


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
        "Extraction note": 1,
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
    assert "Extraction note" in html
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
        "Extraction note",
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
    assert "Use the sample indicators to inspect fixture relationships" in normalized_main
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
    assert "Fixture/mock demo mode" in script
    assert "does not make live CCLD calls" in script
    assert "GITHUB" not in script
    assert "TOKEN" not in script
    assert "COOKIE" not in script


def test_complaint_retrieval_live_script_sets_live_public_config() -> None:
    script_path = ROOT / "scripts" / "run-hosted-complaint-retrieval-live.ps1"
    script = script_path.read_text(encoding="utf-8")

    assert script_path.exists()
    assert "data\\raw\\ccld\\retrieval-live" in script
    assert 'CCLD_HOSTED_TESTER_AUTH_MODE = "local-dev"' in script
    assert 'CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH = "enabled"' in script
    assert 'CCLD_HOSTED_PAGE_DATA_MODE = "fixture-demo"' in script
    assert 'CCLD_RETRIEVAL_ENABLED = "enabled"' in script
    assert "CCLD_RETRIEVAL_RAW_DIR = $resolvedRawStorageDir" in script
    assert 'CCLD_RETRIEVAL_DEMO_MODE = ""' in script
    assert 'CCLD_RETRIEVAL_DEMO_MODE = "mock-success"' not in script
    assert "Live public CCLD retrieval mode" in script
    assert "Public CCLD HTTP requests will be made only after" in script
    assert "Open public CCLD pages from record detail when a source check is needed" in script
    assert "When results look incomplete, check criteria, job details, and loaded data" in script
    assert "Open: $baseUrl/" in script
    assert "Open: $baseUrl/ccld/records/request" in script
    assert "Open: $baseUrl/ccld/retrieval/jobs" in script
    assert "Open: $baseUrl/reviewer" in script
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
    assert 'data\\raw\\ccld\\retrieval-live' in (
        ROOT / "scripts" / "run-hosted-complaint-retrieval-live.ps1"
    ).read_text(encoding="utf-8")


def test_route_active_nav_highlights_correct_item() -> None:
    """Each route must highlight exactly the correct nav item via aria-current='page'."""
    auth_config = load_hosted_auth_runtime_config(
        environ={
            "CCLD_HOSTED_TESTER_AUTH_MODE": "local-dev",
            "CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH": "enabled",
        }
    )
    # (path, expected_active_href, expected_active_label)
    route_active_specs = (
        ("/", "/", "Home"),
        ("/ccld/facilities", "/ccld/facilities", "Facilities"),
        ("/ccld/records/request", "/ccld/records/request", "Request Records"),
        ("/ccld/help", "/ccld/help", "Help"),
        ("/reviewer", "/reviewer", "Review"),
        ("/ccld/retrieval/jobs", "/ccld/retrieval/jobs", "Job diagnostics"),
        ("/feedback", "/feedback", "Feedback"),
    )
    for path, expected_href, expected_label in route_active_specs:
        status, _content_type, body = route_response(
            path,
            auth_runtime_config=auth_config,
            page_data_mode="fixture-demo",
        )
        html = body.decode("utf-8")
        active_marker = f'aria-current="page" href="{expected_href}">{expected_label}'
        assert status == 200, f"Route {path} returned {status}"
        assert active_marker in html, (
            f"Route {path}: expected nav item '{expected_label}' ({expected_href}) "
            f"to be active (aria-current=page), but it was not. "
            f"Check that active_path is set correctly for this route."
        )
        # Exactly one aria-current="page" in nav
        active_count = html.count('aria-current="page"')
        assert active_count == 1, (
            f"Route {path}: expected exactly 1 aria-current=page in nav, got {active_count}."
        )


def test_help_route_does_not_activate_retrieve_nav() -> None:
    """/ccld/help must highlight Help, not Request Records, in the top nav."""
    auth_config = load_hosted_auth_runtime_config(
        environ={
            "CCLD_HOSTED_TESTER_AUTH_MODE": "local-dev",
            "CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH": "enabled",
        }
    )
    status, _content_type, body = route_response(
        "/ccld/help",
        auth_runtime_config=auth_config,
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")

    assert status == 200
    # Help must be active
    assert 'aria-current="page" href="/ccld/help">Help' in html
    # Request Records must NOT be active
    assert 'aria-current="page" href="/ccld/records/request">Request Records' not in html
    assert 'aria-current="page" href="/ccld/records/request">Retrieve' not in html
    # is-active class on Help link, not Request Records link
    assert 'class="is-active" aria-current="page" href="/ccld/help">Help' in html
    assert (
        'class="is-active" aria-current="page" href="/ccld/records/request">Request Records'
        not in html
    )
    assert 'class="is-active" aria-current="page" href="/ccld/records/request">Retrieve' not in html


def test_help_page_topics_toc_links_to_every_help_section_in_order() -> None:
    auth_config = load_hosted_auth_runtime_config(
        environ={
            "CCLD_HOSTED_TESTER_AUTH_MODE": "local-dev",
            "CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH": "enabled",
        }
    )
    status, _content_type, body = route_response(
        "/ccld/help",
        auth_runtime_config=auth_config,
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")
    parser = parse_html_structure(html)

    expected_topics = [
        ("find-facility", "Find a facility"),
        ("request-records", "Request Records"),
        ("review-queue", "Review Queue"),
        ("reviewer-detail", "Reviewer Detail"),
        ("packet-preparation", "Packet preview and preparation draft"),
        ("feedback", "Send feedback"),
    ]
    expected_hrefs = [f"#{topic_id}" for topic_id, _label in expected_topics]
    toc_start = html.index('<h2 id="help-topics-heading">Help topics</h2>')
    details_start = html.index('<section class="help-details"', toc_start)
    toc_html = html[toc_start:details_start]

    assert status == 200
    assert "Help topics" in parser.text_for("h2")
    assert "<details" not in toc_html
    assert toc_html.count('href="#') == len(expected_topics)
    assert [toc_html.index(f'href="{href}"') for href in expected_hrefs] == sorted(
        toc_html.index(f'href="{href}"') for href in expected_hrefs
    )
    for topic_id, label in expected_topics:
        assert f'<a href="#{topic_id}">{label}</a>' in toc_html

    details_attrs = parser.start_attrs_by_tag["details"]
    detail_ids = [attrs.get("id", "") for attrs in details_attrs]
    assert detail_ids[: len(expected_topics)] == [
        topic_id for topic_id, _label in expected_topics
    ]
    assert "support-operator-help" not in detail_ids
    assert "#support-operator-help" not in toc_html
    assert len(detail_ids) == len(set(detail_ids))
    assert all(detail_ids)
    assert parser.summary_texts[: len(expected_topics)] == [
        label for _topic_id, label in expected_topics
    ]
    assert "Support and runtime notes" not in parser.summary_texts


def test_retrieval_job_detail_route_highlights_support_diagnostics_nav() -> None:
    """Job detail routes must highlight the secondary diagnostics nav link."""
    auth_config = load_hosted_auth_runtime_config(
        environ={
            "CCLD_HOSTED_TESTER_AUTH_MODE": "local-dev",
            "CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH": "enabled",
        }
    )
    # A missing job_id returns 404, but the support nav still shows diagnostics as active.
    status, _content_type, body = route_response(
        "/ccld/retrieval/jobs/detail?job_id=test-missing-job",
        auth_runtime_config=auth_config,
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")

    # 404 for missing job, but the nav must still show diagnostics active (not Request Records).
    assert status == 404
    assert 'aria-current="page" href="/ccld/retrieval/jobs">Job diagnostics' in html
    assert 'aria-current="page" href="/ccld/retrieval/jobs">Job Status' not in html
    assert 'aria-current="page" href="/ccld/retrieval/jobs">Jobs' not in html
    assert 'aria-current="page" href="/ccld/records/request">Request Records' not in html
    assert 'aria-current="page" href="/ccld/records/request">Retrieve' not in html


def test_reviewer_detail_route_highlights_review_nav() -> None:
    """/reviewer/records and detail routes must highlight Review in the top nav."""
    auth_config = load_hosted_auth_runtime_config(
        environ={
            "CCLD_HOSTED_TESTER_AUTH_MODE": "local-dev",
            "CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH": "enabled",
        }
    )
    status, _content_type, body = route_response(
        "/reviewer",
        auth_runtime_config=auth_config,
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")

    assert status == 200
    assert 'aria-current="page" href="/reviewer">Review' in html
    assert 'aria-current="page" href="/ccld/records/request">Request Records' not in html
    assert 'aria-current="page" href="/ccld/records/request">Retrieve' not in html


def test_health_response_source_data_loaded_false_without_database() -> None:
    """source_data_loaded must be False when no database URL is configured."""
    payload = health_response()

    # In the test environment there is no CCLD_HOSTED_TESTER_DATABASE_URL, so
    # _check_source_data_loaded() returns False safely without raising.
    assert payload["source_data_loaded"] is False


def test_auth_pages_do_not_expose_tester_scaffold_strings() -> None:
    """Auth pages must not surface 'Open sign-in placeholder' or 'Return to scaffold home'."""
    login_status, _login_ct, login_body = route_response("/auth/login")
    logout_status, _logout_ct, logout_body = route_response("/auth/logout")

    login_html = login_body.decode("utf-8")
    logout_html = logout_body.decode("utf-8")

    assert login_status == 200
    assert "Open sign-in placeholder" not in login_html
    assert "Return to scaffold home" not in login_html
    assert "Return to home" in login_html

    assert logout_status == 200
    assert "Return to scaffold home" not in logout_html
    assert "Return to home" in logout_html


def test_sample_pages_do_not_expose_scaffold_notice() -> None:
    """Sample/fixture pages must not show the scaffold-only notice string."""
    src_status, _src_ct, src_body = route_response("/source-records")
    fac_status, _fac_ct, fac_body = route_response("/facilities")

    src_html = src_body.decode("utf-8")
    fac_html = fac_body.decode("utf-8")

    scaffold_notice_text = "scaffold only: not a production reviewer workflow."
    assert src_status == 200
    assert scaffold_notice_text not in src_html
    assert "Local sample source-derived data only" in src_html

    assert fac_status == 200
    assert scaffold_notice_text not in fac_html
    assert "Local sample source-derived data only" in fac_html


def test_tester_facing_pages_do_not_expose_developer_wording() -> None:
    """Normal tester-facing pages must not surface developer/scaffold/demo wording.

    These are the routes that a logged-in reviewer would visit in the Cloudflare
    Access pilot.  The test uses fixture-demo mode with local-dev auth so no
    PostgreSQL connection is required.
    """
    auth_config = load_hosted_auth_runtime_config(
        environ={
            "CCLD_HOSTED_TESTER_AUTH_MODE": "local-dev",
            "CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH": "enabled",
        }
    )
    pages = {
        "home": route_response("/", auth_runtime_config=auth_config, page_data_mode="fixture-demo"),
        "retrieve": route_response(
            "/ccld/records/request",
            auth_runtime_config=auth_config,
            page_data_mode="fixture-demo",
        ),
        "facilities": route_response(
            "/ccld/facilities",
            auth_runtime_config=auth_config,
            page_data_mode="fixture-demo",
        ),
        "help": route_response(
            "/ccld/help",
            auth_runtime_config=auth_config,
            page_data_mode="fixture-demo",
        ),
        "jobs": route_response(
            "/ccld/retrieval/jobs",
            auth_runtime_config=auth_config,
            page_data_mode="fixture-demo",
        ),
    }

    forbidden = [
        "local/test",
        "scaffold home",
        "Hosted scaffold",
        "not a production reviewer workflow",
        "Open sign-in placeholder",
        "Return to scaffold home",
        "Retrieval not configured",
        "No PostgreSQL-backed source-derived facility rows are loaded yet",
        "Run Alembic migrations",
        "import a validated CCLD artifact",
        "migrated/imported hosted source-derived database context",
    ]

    for page_name, (status, _ct, body) in pages.items():
        html = body.decode("utf-8")
        assert status == 200, f"{page_name}: expected 200, got {status}"
        for phrase in forbidden:
            assert phrase not in html, (
                f"{page_name}: forbidden phrase found in rendered HTML: {phrase!r}"
            )

    # Positive check: tester-facing pages use review-aid language instead of developer jargon.
    retrieve_html = pages["retrieve"][2].decode("utf-8")
    assert "See review guidance and next steps." in retrieve_html
    assert "Public records stay separate from saved notes/status." not in retrieve_html
    assert (
        "Source-derived records stay separate from reviewer-created notes/status"
        not in retrieve_html
    )


def test_live_mode_facility_lookup_not_configured_shows_safe_fallback_messaging(
    monkeypatch: MonkeyPatch,
) -> None:
    """When no real facility reference is available in live mode, the facility lookup page
    must clearly state directory lookup is not configured and not expose synthetic data.
    """
    clear_hosted_runtime_env(monkeypatch)

    from ccld_complaints.hosted_app.ccld_facility_lookup import (
        no_reference_facility_source,
        render_ccld_facility_lookup_page,
    )

    html = render_ccld_facility_lookup_page(reference_source=no_reference_facility_source())
    normalized_html = " ".join(html.split()).lower()

    assert "Facility directory lookup is not configured" in html
    assert "Enter a known CCLD Facility ID" in html
    assert "Open Request Records" in html
    # Synthetic fixture names must not appear
    assert "Synthetic Orchard" not in html
    assert "Synthetic Valley" not in html
    # No JS combobox with empty data
    assert "facility-reference-json" not in html
    # Does not use fixture/mock/scaffold wording for live users
    assert "scaffold" not in normalized_html
    assert "mock" not in normalized_html
