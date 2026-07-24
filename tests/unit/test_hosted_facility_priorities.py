from __future__ import annotations

import base64
import json
import re
from collections.abc import Mapping
from dataclasses import replace
from html import unescape
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.engine import Connection
from sqlalchemy.exc import OperationalError

from ccld_complaints.hosted_app import reviewer_ui, source_derived_reads
from ccld_complaints.hosted_app.app import (
    _legacy_compare_facilities_redirect_location,
    route_response,
)
from ccld_complaints.hosted_app.auth import (
    AuthenticatedActor,
    HostedAccessScope,
    HostedAccountStatus,
    HostedActorCategory,
    HostedTesterRole,
    load_hosted_auth_runtime_config,
)
from ccld_complaints.hosted_app.ccld_facility_lookup import (
    CCLD_FACILITY_REVIEW_HUB_PATH,
    CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH,
)
from ccld_complaints.hosted_app.ccld_record_request_ui import (
    ccld_record_request_context_for_reviewer_context,
)
from ccld_complaints.hosted_app.ccld_retrieval_jobs import hosted_ccld_retrieval_jobs
from ccld_complaints.hosted_app.facility_reference_preload import (
    hosted_facility_reference_metadata,
    hosted_facility_reference_records,
)
from ccld_complaints.hosted_app.reviewer_created_state import (
    hosted_reviewer_created_state,
)
from ccld_complaints.hosted_app.reviewer_ui import (
    LOCAL_REVIEWER_UI_SCOPE,
    REVIEWER_UI_FACILITY_PRIORITIES_PATH,
    reviewer_ui_context_for_connection,
)
from ccld_complaints.hosted_app.seeded_import import (
    hosted_import_batches,
    hosted_seeded_import_metadata,
    hosted_source_derived_records,
    import_seeded_corpus_artifact,
    load_seeded_corpus_artifact,
)

TEST_SCOPE = LOCAL_REVIEWER_UI_SCOPE
OTHER_SCOPE = HostedAccessScope("seeded_corpus", "outside-loaded-corpus")
CANONICAL_PRIORITY_PATH = (
    f"{CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH}?view=complaint-priority-compatibility"
)


def test_facility_priorities_orders_by_visible_factors_and_links_to_records() -> None:
    with _priority_connection() as connection:
        _insert_facility_bundle(
            connection,
            facility_number="100001",
            facility_name="Alpha Center",
            facility_type="Children's Center",
            county="Kern",
            complaints=(
                _complaint("A-1", "2026-05-01", "Substantiated", delay_days=120),
                _complaint("A-2", "2026-04-01", "Unsubstantiated", source_url=""),
            ),
        )
        _insert_facility_bundle(
            connection,
            facility_number="200002",
            facility_name="Beta Center",
            facility_type="Foster Family Agency",
            county="Alameda",
            complaints=(
                _complaint("B-1", "2026-06-01", "Unsubstantiated"),
                _complaint("B-2", "2026-03-01", "Unsubstantiated"),
            ),
        )
        _insert_facility_bundle(
            connection,
            facility_number="300003",
            facility_name="Gamma Center",
            facility_type="Children's Center",
            county="Kern",
            complaints=(
                _complaint("G-1", "2026-07-01", "Substantiated"),
            ),
        )

        status, content_type, body = route_response(
            CANONICAL_PRIORITY_PATH,
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    html = body.decode("utf-8")
    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Find Facilities That May Need Closer Review" in html
    assert "Complaint Patterns" in html
    assert "hidden score" in html
    assert "machine learning" in html
    assert html.index("Alpha Center") < html.index("Gamma Center") < html.index("Beta Center")
    assert "2 deduplicated loaded complaint record(s)." in html
    assert "1 source-derived substantiated/equivalent finding(s)." in html
    assert "strongest available flag is 120+ days" in html
    assert "1 complaint record(s) missing an original public report link." in html
    assert "Open Complaint Worklist" in html
    assert "Return to Complaint Worklist" in html
    assert "review queue" not in html.casefold()
    assert "/ccld/records/request?facility_number=100001" in html
    assert "Review Complaint" in html
    assert "/reviewer/records/detail?source_record_key=complaint%3Accld%3Acomplaint%3AA-1" in html
    assert "Open original public report for A-1" in html
    assert "raw_sha256" not in html
    assert "data/raw" not in html
    assert "legal priority" not in html.casefold()


def test_legacy_facility_priorities_redirect_preserves_supported_query() -> None:
    legacy_path = (
        f"{REVIEWER_UI_FACILITY_PRIORITIES_PATH}?facility_type=children"
        "&min_complaints=2&page=3&page_size=10"
    )

    status, _content_type, body = route_response(legacy_path)
    location = _legacy_compare_facilities_redirect_location(legacy_path)

    assert status == 302
    assert location == (
        f"{CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH}"
        "?view=complaint-priority-compatibility&facility_type=children"
        "&min_complaints=2&page=3&page_size=10"
    )
    assert b"Continue to Compare Facilities" in body


def test_facility_priorities_filters_date_type_geography_counts_and_indicator() -> None:
    with _priority_connection() as connection:
        _insert_facility_bundle(
            connection,
            facility_number="100001",
            facility_name="Alpha Center",
            facility_type="Children's Center",
            county="Kern",
            complaints=(
                _complaint("A-1", "2026-05-01", "Substantiated", delay_days=90),
                _complaint("A-2", "2026-04-01", "Unsubstantiated"),
            ),
        )
        _insert_facility_bundle(
            connection,
            facility_number="200002",
            facility_name="Beta Center",
            facility_type="Foster Family Agency",
            county="Alameda",
            complaints=(
                _complaint("B-1", "2026-06-01", "Substantiated"),
            ),
        )

        status, _content_type, body = route_response(
            (
                f"{CANONICAL_PRIORITY_PATH}"
                "&facility_type=children&geography=kern&start_date=2026-04-01"
                "&end_date=2026-05-31&min_complaints=2&min_substantiated=1"
                "&indicator=delay"
            ),
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    html = body.decode("utf-8")
    assert status == 200
    assert "Alpha Center" in html
    assert "Beta Center" not in html
    assert "Showing 1-1 of 1 matching facilities; 2 total" in html
    assert 'value="children"' in html
    assert 'value="kern"' in html
    assert 'value="2"' in html
    assert 'value="1"' in html
    assert '<option value="delay" selected="selected">' in html


def test_facility_priorities_handles_missing_low_data_empty_and_pagination() -> None:
    with _priority_connection() as connection:
        for index in range(12):
            _insert_facility_bundle(
                connection,
                facility_number=f"90000{index:02d}",
                facility_name=f"Low Data {index:02d}",
                facility_type="Unknown",
                county="",
                complaints=(
                    _complaint(
                        f"L-{index:02d}",
                        "" if index == 0 else f"2026-01-{index + 1:02d}",
                        "Unknown",
                        source_url="" if index == 0 else None,
                    ),
                ),
            )

        status, _content_type, body = route_response(
            f"{CANONICAL_PRIORITY_PATH}&indicator=low_data&page_size=10",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )
        missing_status, _missing_type, missing_body = route_response(
            f"{CANONICAL_PRIORITY_PATH}&indicator=source_link_missing&page_size=100",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )
        empty_status, _empty_type, empty_body = route_response(
            f"{CANONICAL_PRIORITY_PATH}&min_complaints=99",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    html = body.decode("utf-8")
    missing_html = missing_body.decode("utf-8")
    empty_html = empty_body.decode("utf-8")
    assert status == 200
    assert missing_status == 200
    assert empty_status == 200
    assert "Low-data facility: one loaded complaint record" in html
    assert "unknown" in html
    assert (
        "Original public report link not available for the first qualifying complaint."
        in missing_html
    )
    assert "Showing 1-10 of 12 matching facilities" in html
    assert "Next page" in html
    assert "page_size=10" in html
    assert "No facilities match these filters" in empty_html
    assert "Clear filters" in empty_html
    assert "not public-source absence" not in empty_html.casefold()


def test_facility_priorities_preserves_authorization_and_batch_isolation() -> None:
    with _priority_connection() as connection:
        _insert_facility_bundle(
            connection,
            facility_number="100001",
            facility_name="Allowed Center",
            facility_type="Children's Center",
            county="Kern",
            complaints=(_complaint("A-1", "2026-05-01", "Substantiated"),),
        )
        _insert_import_batch(connection, OTHER_SCOPE.scope_id)
        _insert_facility_bundle(
            connection,
            import_batch_id=OTHER_SCOPE.scope_id,
            facility_number="999999",
            facility_name="Outside Scope Center",
            facility_type="Children's Center",
            county="Kern",
            complaints=(_complaint("O-1", "2026-05-01", "Substantiated"),),
        )

        denied_status, _denied_type, denied_body = route_response(
            CANONICAL_PRIORITY_PATH,
            reviewer_ui_context=reviewer_ui_context_for_connection(
                connection,
                actor=None,
            ),
        )
        status, _content_type, body = route_response(
            CANONICAL_PRIORITY_PATH,
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    denied_html = denied_body.decode("utf-8")
    html = body.decode("utf-8")
    assert denied_status == 401
    assert "Facility priorities blocked" in denied_html
    assert "authenticated actor" in denied_html
    assert status == 200
    assert "Allowed Center" in html
    assert "Outside Scope Center" not in html


def test_facility_priorities_get_does_not_mutate_hosted_tables() -> None:
    with _priority_connection() as connection:
        _insert_facility_bundle(
            connection,
            facility_number="100001",
            facility_name="Allowed Center",
            facility_type="Children's Center",
            county="Kern",
            complaints=(_complaint("A-1", "2026-05-01", "Substantiated"),),
        )
        before = _table_counts(connection)

        status, _content_type, body = route_response(
            CANONICAL_PRIORITY_PATH,
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

        after = _table_counts(connection)

    assert status == 200
    assert "Allowed Center" in body.decode("utf-8")
    assert after == before


def test_facility_priorities_production_mode_does_not_fall_back_to_fixture_data() -> None:
    auth_runtime_config = load_hosted_auth_runtime_config(environ={})

    status, _content_type, body = route_response(
        CANONICAL_PRIORITY_PATH,
        auth_runtime_config=auth_runtime_config,
        page_data_mode="postgres",
    )

    html = body.decode("utf-8")
    assert status in {401, 503}
    assert "A. MIRIAM JAMISON CHILDREN" not in html
    assert "Fixture/mock demo" not in html


def test_facility_intelligence_database_unavailability_returns_governed_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(*_args: Any, **_kwargs: Any) -> None:
        raise OperationalError("SELECT", {}, Exception("database unavailable"))

    monkeypatch.setattr(
        reviewer_ui,
        "list_authorized_facility_intelligence_page",
        unavailable,
    )
    with _priority_connection() as connection:
        status, _content_type, body = route_response(
            CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH,
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    html = body.decode("utf-8")
    assert status == 503
    assert "Facilities could not be loaded" in html
    assert "Try Again" in html


def test_facility_priority_helper_deduplicates_complaint_records() -> None:
    source_records = [
        _flat_source_record(
            "facility",
            "facility:ccld:facility:100001",
            "ccld:facility:100001",
            "ccld:document:100001:1",
            "ccld:facility:100001",
            {
                "facility_id": "ccld:facility:100001",
                "external_facility_number": "100001",
                "facility_name": "Alpha Center",
                "facility_type": "Children's Center",
                "county": "Kern",
            },
        ),
        _flat_source_record(
            "complaint",
            "complaint:ccld:complaint:DUP-1",
            "ccld:complaint:DUP-1",
            "ccld:document:100001:1",
            "ccld:facility:100001",
            {
                "complaint_id": "ccld:complaint:DUP-1",
                "facility_id": "ccld:facility:100001",
                "document_id": "ccld:document:100001:1",
                "complaint_control_number": "DUP-1",
                "complaint_received_date": "2026-05-01",
                "finding": "Substantiated",
            },
        ),
        _flat_source_record(
            "complaint",
            "complaint:ccld:complaint:DUP-1-copy",
            "ccld:complaint:DUP-1",
            "ccld:document:100001:1",
            "ccld:facility:100001",
            {
                "complaint_id": "ccld:complaint:DUP-1",
                "facility_id": "ccld:facility:100001",
                "document_id": "ccld:document:100001:1",
                "complaint_control_number": "DUP-1",
                "complaint_received_date": "2026-05-01",
                "finding": "Substantiated",
            },
        ),
    ]

    summaries = reviewer_ui._facility_priority_summaries(source_records)

    assert len(summaries) == 1
    assert summaries[0].complaint_count == 1
    assert summaries[0].substantiated_count == 1


def test_facility_intelligence_filters_reconciles_and_preserves_drilldown_context() -> None:
    with _priority_connection() as connection:
        _insert_facility_bundle(
            connection,
            facility_number="100001",
            facility_name="Alpha Center",
            facility_type="Children's Center",
            county="Kern",
            complaints=(
                _complaint(
                    "A-1",
                    "2026-05-01",
                    "Substantiated",
                    delay_days=120,
                    serious=True,
                ),
                _complaint(
                    "A-2",
                    "2026-04-01",
                    "Unsubstantiated",
                    source_url="",
                ),
            ),
        )
        _insert_facility_bundle(
            connection,
            facility_number="200002",
            facility_name="Beta Center",
            facility_type="Foster Family Agency",
            county="Alameda",
            complaints=(
                _complaint("B-1", "2026-05-03", "Substantiated", serious=True),
            ),
        )

        status, content_type, body = route_response(
            (
                f"{CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH}"
                "?facility_type=children&geography=kern"
                "&start_date=2026-05-01&end_date=2026-05-31"
                "&finding=Substantiated&serious_topic=Supervision+topic"
                "&coverage=available&sort=complaint_count"
            ),
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    html = body.decode("utf-8")
    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Alpha Center" in html
    assert "Beta Center" not in html
    assert "1 exact contributing complaint" in html
    assert html.count("Open next complaint") >= 2
    assert "A-2" not in html
    assert "05/01/2026" in html
    assert "/ccld/facilities/detail?facility_number=100001" in html
    assert "origin=facility_intelligence" in html
    assert "date_dimension=complaint_received_date" in html
    assert "finding=Substantiated" in html
    assert "serious_topic=Supervision%2Btopic" not in html
    assert "serious_topic=Supervision+topic" in html
    assert "coverage=available" in html
    assert "start_date=2026-05-01" in html
    assert "end_date=2026-05-31" in html
    assert "return_context_origin=facility_intelligence" in html
    assert "Review next" in html
    assert "Open next complaint" in html
    assert "Open next complaint source" in html
    assert "Copy next complaint source URL" in html
    assert "120+ day gap" in html
    assert "Supervision topic" in html
    assert "Source available" in html
    assert "raw_sha256" not in html
    assert "tests/fixtures" not in html
    assert "connector_name" not in html


def test_facility_intelligence_coverage_missing_date_empty_and_invalid_range_states() -> None:
    with _priority_connection() as connection:
        _insert_facility_bundle(
            connection,
            facility_number="100001",
            facility_name="Partial Center",
            facility_type="Children's Center",
            county="Kern",
            complaints=(
                _complaint("P-1", "2026-05-01", "Substantiated"),
                _complaint("P-2", "", "Unknown", source_url=""),
            ),
        )
        _insert_facility_bundle(
            connection,
            facility_number="300003",
            facility_name="Unavailable Center",
            facility_type="Children's Center",
            county="Kern",
            complaints=(
                _complaint("U-1", "2026-05-02", "Unknown", source_url=""),
            ),
        )
        partial_status, _partial_type, partial_body = route_response(
            f"{CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH}?coverage=partial",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )
        unavailable_status, _unavailable_type, unavailable_body = route_response(
            f"{CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH}?coverage=unavailable",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )
        empty_status, _empty_type, empty_body = route_response(
            f"{CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH}?start_date=2099-01-01&end_date=2099-12-31",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )
        invalid_status, _invalid_type, invalid_body = route_response(
            f"{CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH}?start_date=2026-06-01&end_date=2026-05-01",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    partial_html = partial_body.decode("utf-8")
    unavailable_html = unavailable_body.decode("utf-8")
    empty_html = empty_body.decode("utf-8")
    invalid_html = invalid_body.decode("utf-8")
    assert partial_status == unavailable_status == empty_status == 200
    assert invalid_status == 400
    assert "Partial Center" in partial_html
    assert "Unavailable Center" not in partial_html
    assert "Partial source coverage" in partial_html
    assert "Unavailable Center" in unavailable_html
    assert "Partial Center" not in unavailable_html
    assert "Source unavailable" in unavailable_html
    assert "No facilities match these filters" in empty_html
    assert "Clear one filter or clear all filters" in empty_html
    assert "Start date must be on or before end date." in invalid_html
    assert "Find Facilities That May Need Closer Review" in invalid_html
    assert "Date range needs attention" in invalid_html
    assert 'value="2026-06-01"' in invalid_html
    assert 'value="2026-05-01"' in invalid_html


def test_facility_intelligence_get_is_read_only_and_production_has_no_fixture_fallback() -> None:
    with _priority_connection() as connection:
        _insert_facility_bundle(
            connection,
            facility_number="100001",
            facility_name="Read Only Center",
            facility_type="Children's Center",
            county="Kern",
            complaints=(_complaint("R-1", "2026-05-01", "Substantiated"),),
        )
        before = _table_counts(connection)
        status, _content_type, body = route_response(
            CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH,
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )
        after = _table_counts(connection)

    auth_runtime_config = load_hosted_auth_runtime_config(environ={})
    production_status, _production_type, production_body = route_response(
        CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH,
        auth_runtime_config=auth_runtime_config,
        page_data_mode="postgres",
    )
    hub_status, _hub_type, hub_body = route_response(
        f"{CCLD_FACILITY_REVIEW_HUB_PATH}?facility_number=157806098",
        auth_runtime_config=auth_runtime_config,
        page_data_mode="postgres",
    )
    html = body.decode("utf-8")
    production_html = production_body.decode("utf-8")
    hub_html = hub_body.decode("utf-8")
    assert status == 200
    assert after == before
    assert "Read Only Center" in html
    assert production_status in {401, 503}
    assert "A. MIRIAM JAMISON CHILDREN" not in production_html
    assert "Fixture/mock demo" not in production_html
    assert hub_status in {401, 503}
    assert "A. MIRIAM JAMISON CHILDREN" not in hub_html
    assert "Synthetic Orchard" not in hub_html


def test_facility_intelligence_accessible_structure_and_safe_language() -> None:
    with _priority_connection() as connection:
        _insert_facility_bundle(
            connection,
            facility_number="100001",
            facility_name="Accessible Center",
            facility_type="Children's Center",
            county="Kern",
            complaints=(
                _complaint("A11Y-1", "2026-05-01", "Unsubstantiated", serious=True),
            ),
        )
        status, _content_type, body = route_response(
            CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH,
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    html = body.decode("utf-8")
    normalized = " ".join(html.casefold().split())
    assert status == 200
    assert '<main id="main-content"' in html
    assert '<form class="compact-filter-form" method="get"' in html
    assert '<label for="facility-intelligence-facility-type">' in html
    assert '<label for="facility-intelligence-coverage">' in html
    assert '<button class="button" type="submit">Apply filters</button>' in html
    assert 'aria-label="Finding and review flags"' in html
    assert 'aria-current="page" href="/ccld/facilities/intelligence">Compare Facilities</a>' in html
    assert "Source record" in html
    assert "Reviewer state" in html
    assert "Facility ID" in html
    assert 'aria-live="polite"' in html
    assert "Find Facilities That May Need Closer Review" in html
    assert "Which facilities may warrant review next?" not in html
    assert "What the active filters surface" not in html
    assert "All contributing complaint records" not in html
    assert "<details" not in html
    assert "No substantiated count" not in html
    assert "Review public records" in html
    assert "Facilities" in html
    assert "Request Records" in html
    assert "Feedback" in html
    assert "Job Status" not in html
    assert "shell-facility-search" not in html
    assert "typeof navigator !== 'undefined'" in html
    assert "showCopyStatus(button, 'Copy unavailable');" in html
    assert "@media print" in html
    assert "@media (min-width: 1101px)" in html
    assert ".facility-inventory-context" in html
    assert "position: sticky" in html
    assert "position: static !important" in html
    assert ".facility-pagination, .facility-row-actions" in html
    assert ".site-header, .civic-header" in html
    assert ".copy-icon-button, .copy-text-control" in html
    assert ".facility-row-actions" in html
    assert "license number" not in normalized
    assert "legal conclusion" not in normalized
    assert "facility-wide conclusion" not in normalized
    assert "hidden score" not in normalized


def test_facility_intelligence_approved_state_variants_and_filter_recovery() -> None:
    with _priority_connection() as connection:
        context = reviewer_ui_context_for_connection(connection)
        no_data_status, _no_data_type, no_data_body = route_response(
            CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH,
            reviewer_ui_context=context,
        )
        _insert_facility_bundle(
            connection,
            facility_number="100001",
            facility_name="State Center",
            facility_type="Children's Center",
            county="Kern",
            complaints=(_complaint("STATE-1", "2026-05-01", "Unsubstantiated"),),
        )
        filtered_status, _filtered_type, filtered_body = route_response(
            f"{CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH}?geography=Nowhere",
            reviewer_ui_context=context,
        )

    loading_html = reviewer_ui._render_facility_intelligence(
        [],
        filters=reviewer_ui.FacilityIntelligenceFilters(),
        filter_options=reviewer_ui.FacilityIntelligenceFilterOptions(),
        pagination=reviewer_ui.FacilityIntelligencePagination(),
        total_authorized_facility_count=0,
        review_next_facility_identity=None,
        state_summaries={},
        reviewer_state_available=False,
        actor_label=None,
        page_state="loading",
    )
    no_data_html = no_data_body.decode("utf-8")
    filtered_html = filtered_body.decode("utf-8")
    assert no_data_status == filtered_status == 200
    assert "No loaded complaint records are available to compare" in no_data_html
    assert "No facility rows are rendered." in no_data_html
    assert "No facilities match these filters" in filtered_html
    assert "1 facility · Loaded complaint corpus" in filtered_html
    assert "Showing 0–0 of 0 facilities" in filtered_html
    assert 'aria-label="Clear Geography filter"' in filtered_html
    assert ">Clear all</a>" in filtered_html
    assert "Loading facilities" in loading_html
    assert 'aria-busy="true"' in loading_html
    assert "Loading source-backed ordering reasons" in loading_html


def test_facility_intelligence_binds_source_and_reviewer_actions_to_next_complaint() -> None:
    with _priority_connection() as connection:
        _insert_facility_bundle(
            connection,
            facility_number="100001",
            facility_name="Binding Center",
            facility_type="Children's Center",
            county="Kern",
            complaints=(
                _complaint(
                    "BIND-1",
                    "2026-05-03",
                    "Substantiated",
                    source_url="https://example.test/source/BIND-1",
                ),
                _complaint(
                    "BIND-2",
                    "2026-05-01",
                    "Unsubstantiated",
                    source_url="https://example.test/source/BIND-2",
                ),
            ),
        )
        _insert_reviewer_state(
            connection,
            reviewer_state_id="state:bind-1-status",
            source_record_key="complaint:ccld:complaint:BIND-1",
            created_at="2026-07-01T12:00:00+00:00",
            payload={
                "payload_kind": "reviewer_status_scaffold",
                "reviewer_status": "in_review",
            },
        )
        before = _table_counts(connection)
        status, _content_type, body = route_response(
            CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH,
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )
        after = _table_counts(connection)

    html = body.decode("utf-8")
    assert status == 200
    assert after == before
    assert "Next complaint: <strong>BIND-1</strong>" in html
    assert 'href="https://example.test/source/BIND-1"' in html
    assert 'data-copy-value="https://example.test/source/BIND-1"' in html
    assert 'aria-label="Open next complaint source for BIND-1"' in html
    assert "In review" in html
    assert html.index("Source record") < html.index("Reviewer state")
    assert "https://example.test/source/BIND-2" not in html


def test_facility_intelligence_distinguishes_verified_zero_and_unavailable_values() -> None:
    with _priority_connection() as connection:
        _insert_facility_bundle(
            connection,
            facility_number="100001",
            facility_name="Verified Zero Center",
            facility_type="Children's Center",
            county="Kern",
            complaints=(_complaint("ZERO-1", "2026-05-01", "Unsubstantiated"),),
        )
        _insert_facility_bundle(
            connection,
            facility_number="200002",
            facility_name="Unavailable Values Center",
            facility_type="Children's Center",
            county="Kern",
            complaints=(_complaint("UNKNOWN-1", "", "Unknown", source_url=""),),
        )
        status, _content_type, body = route_response(
            CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH,
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    html = body.decode("utf-8")
    assert status == 200
    assert "0 substantiated" in html
    assert "Substantiated count unavailable" in html
    assert "Latest complaint date unavailable" in html
    assert "No substantiated count" not in html
    assert "Copy next complaint source URL unavailable" in html
    assert 'aria-disabled="true">Source unavailable</span>' in html


def test_facility_intelligence_uses_public_identity_fallback_for_missing_name() -> None:
    with _priority_connection() as connection:
        _insert_complaint_without_facility(
            connection,
            facility_number="157806098",
            control="MISSING-NAME-1",
            finding="Pending",
        )
        status, _content_type, body = route_response(
            CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH,
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    html = body.decode("utf-8")
    visible_text = re.sub(r"<[^>]+>", " ", html)
    assert status == 200
    assert "Facility name unavailable" in visible_text
    assert re.search(r"Facility ID\s+157806098", visible_text)
    assert "ccld:facility:157806098" not in visible_text
    assert (
        reviewer_ui._compare_facilities_public_id("ccld-facility-157806098")
        == "157806098"
    )
    assert (
        reviewer_ui._compare_facilities_name(
            "Facility ID ccld-facility-157806098",
            "ccld-facility-157806098",
        )
        == "Facility name unavailable"
    )


def test_facility_intelligence_pagination_boundaries_and_exact_position_wording() -> None:
    cases = (0, 1, 24, 25, 26, 49, 50, 51)
    for facility_count in cases:
        with _priority_connection() as connection:
            _insert_facility_population(connection, facility_count)
            status, _content_type, body = route_response(
                f"{CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH}?sort=facility_name",
                reviewer_ui_context=reviewer_ui_context_for_connection(connection),
            )
            first_html = body.decode("utf-8")
            expected_last = min(facility_count, 25)
            expected_first = 1 if facility_count else 0
            assert status == 200
            assert (
                f"Showing {expected_first}–{expected_last} of {facility_count} facilities"
                in first_html
            )
            assert 'aria-describedby="facility-intelligence-position"' in first_html
            assert 'id="facility-intelligence-position"' in first_html
            assert (
                '<span class="button button-secondary facility-pagination__control '
                'is-disabled" aria-disabled="true">Previous</span>'
                in first_html
            )
            if facility_count <= 25:
                assert _pagination_href(first_html, "Next") is None
                assert 'aria-disabled="true">Next</span>' in first_html
                continue

            next_href = _pagination_href(first_html, "Next")
            assert next_href is not None
            assert 'aria-label="Next facilities, showing 26–' in first_html
            second_status, _second_type, second_body = route_response(
                next_href,
                reviewer_ui_context=reviewer_ui_context_for_connection(connection),
            )
            second_html = second_body.decode("utf-8")
            second_last = min(facility_count, 50)
            assert second_status == 200
            assert f"Showing 26–{second_last} of {facility_count} facilities" in second_html
            assert _pagination_href(second_html, "Previous") is not None
            if facility_count <= 50:
                assert _pagination_href(second_html, "Next") is None
                assert 'aria-disabled="true">Next</span>' in second_html
            else:
                final_href = _pagination_href(second_html, "Next")
                assert final_href is not None
                final_status, _final_type, final_body = route_response(
                    final_href,
                    reviewer_ui_context=reviewer_ui_context_for_connection(connection),
                )
                final_html = final_body.decode("utf-8")
                assert final_status == 200
                assert "Showing 51–51 of 51 facilities" in final_html
                assert 'aria-disabled="true">Next</span>' in final_html


def test_facility_intelligence_seek_pages_have_no_duplicates_or_omissions() -> None:
    with _priority_connection() as connection:
        _insert_facility_population(connection, 51)
        context = reviewer_ui_context_for_connection(connection)
        href = f"{CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH}?sort=facility_name"
        seen: list[str] = []
        positions: list[str] = []
        while href:
            status, _content_type, body = route_response(
                href,
                reviewer_ui_context=context,
            )
            html = body.decode("utf-8")
            assert status == 200
            seen.extend(_rendered_population_names(html))
            match = re.search(r"Showing \d+–\d+ of 51 facilities", html)
            assert match is not None
            positions.append(match.group(0))
            href = _pagination_href(html, "Next") or ""

        assert positions == [
            "Showing 1–25 of 51 facilities",
            "Showing 26–50 of 51 facilities",
            "Showing 51–51 of 51 facilities",
        ]
        assert len(seen) == len(set(seen)) == 51
        assert seen == [f"Page Facility {index:03d}" for index in range(51)]


def test_facility_intelligence_continuations_preserve_filters_and_reject_bad_state() -> None:
    with _priority_connection() as connection:
        _insert_facility_population(connection, 26)
        context = reviewer_ui_context_for_connection(connection)
        status, _content_type, body = route_response(
            (
                f"{CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH}"
                "?facility_type=children&sort=facility_name"
            ),
            reviewer_ui_context=context,
        )
        html = body.decode("utf-8")
        next_href = _pagination_href(html, "Next")
        assert status == 200
        assert next_href is not None
        assert "facility_type=children" in next_href
        assert "sort=facility_name" in next_href
        filter_form = html.split('<form class="compact-filter-form"', 1)[1].split(
            "</form>", 1
        )[0]
        sort_form = html.split('<form class="facility-intelligence-sort"', 1)[1].split(
            "</form>", 1
        )[0]
        assert 'name="continuation"' not in filter_form
        assert 'name="continuation"' not in sort_form

        next_status, _next_type, next_body = route_response(
            next_href,
            reviewer_ui_context=context,
        )
        assert next_status == 200
        assert "Showing 26–26 of 26 facilities" in next_body.decode("utf-8")

        token = parse_qs(urlsplit(next_href).query)["continuation"][0]
        malformed_status, _malformed_type, malformed_body = route_response(
            f"{CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH}?continuation=not-a-cursor",
            reviewer_ui_context=context,
        )
        mismatch_status, _mismatch_type, mismatch_body = route_response(
            (
                f"{CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH}"
                f"?sort=recent_activity&continuation={token}"
            ),
            reviewer_ui_context=context,
        )
        _insert_facility_population(connection, 1, start_index=26)
        stale_status, _stale_type, stale_body = route_response(
            next_href,
            reviewer_ui_context=context,
        )

    assert malformed_status == mismatch_status == stale_status == 400
    assert "Pagination link is no longer valid" in malformed_body.decode("utf-8")
    assert "does not match the active filters and ordering" in mismatch_body.decode(
        "utf-8"
    )
    assert "continuation is stale" in stale_body.decode("utf-8")


def test_facility_intelligence_rejects_modified_position_and_anchor() -> None:
    with _priority_connection() as connection:
        _insert_facility_population(connection, 51)
        context = reviewer_ui_context_for_connection(connection)
        status, _content_type, body = route_response(
            f"{CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH}?sort=facility_name",
            reviewer_ui_context=context,
        )
        next_href = _pagination_href(body.decode("utf-8"), "Next")
        assert status == 200
        assert next_href is not None

        modified_position_href = _continuation_with_payload_value(
            next_href,
            key="s",
            value=2,
        )
        position_status, _position_type, position_body = route_response(
            modified_position_href,
            reviewer_ui_context=context,
        )
        modified_anchor_href = _continuation_with_payload_value(
            next_href,
            key="a",
            value=["page facility 023", "ccld:facility:800000023"],
        )
        anchor_status, _anchor_type, anchor_body = route_response(
            modified_anchor_href,
            reviewer_ui_context=context,
        )
        missing_anchor_href = _continuation_with_payload_value(
            next_href,
            key="a",
            value=["missing facility", "ccld:facility:missing"],
        )
        missing_status, _missing_type, missing_body = route_response(
            missing_anchor_href,
            reviewer_ui_context=context,
        )

    assert position_status == anchor_status == missing_status == 400
    assert "position does not match its anchor" in position_body.decode("utf-8")
    assert "position does not match its anchor" in anchor_body.decode("utf-8")
    assert "continuation is stale" in missing_body.decode("utf-8")


def test_facility_intelligence_forward_and_backward_ranges_use_anchor_rank() -> None:
    with _priority_connection() as connection:
        _insert_facility_population(connection, 51)
        context = reviewer_ui_context_for_connection(connection)
        first_status, _first_type, first_body = route_response(
            f"{CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH}?sort=facility_name",
            reviewer_ui_context=context,
        )
        second_href = _pagination_href(first_body.decode("utf-8"), "Next")
        assert first_status == 200
        assert second_href is not None

        second_status, _second_type, second_body = route_response(
            second_href,
            reviewer_ui_context=context,
        )
        second_html = second_body.decode("utf-8")
        third_href = _pagination_href(second_html, "Next")
        assert second_status == 200
        assert "Showing 26–50 of 51 facilities" in second_html
        assert third_href is not None

        third_status, _third_type, third_body = route_response(
            third_href,
            reviewer_ui_context=context,
        )
        third_html = third_body.decode("utf-8")
        back_to_second_href = _pagination_href(third_html, "Previous")
        assert third_status == 200
        assert "Showing 51–51 of 51 facilities" in third_html
        assert back_to_second_href is not None

        back_status, _back_type, back_body = route_response(
            back_to_second_href,
            reviewer_ui_context=context,
        )
        back_html = back_body.decode("utf-8")
        back_to_first_href = _pagination_href(back_html, "Previous")
        assert back_status == 200
        assert "Showing 26–50 of 51 facilities" in back_html
        assert back_to_first_href is not None

        first_again_status, _first_again_type, first_again_body = route_response(
            back_to_first_href,
            reviewer_ui_context=context,
        )

    assert first_again_status == 200
    assert "Showing 1–25 of 51 facilities" in first_again_body.decode("utf-8")


def test_facility_intelligence_reads_only_current_page_and_uses_bounded_sql(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _priority_connection() as connection:
        _insert_facility_population(connection, 51)
        context = reviewer_ui_context_for_connection(connection)
        first_status, _first_type, first_body = route_response(
            f"{CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH}?sort=facility_name",
            reviewer_ui_context=context,
        )
        next_href = _pagination_href(first_body.decode("utf-8"), "Next")
        assert first_status == 200
        assert next_href is not None
        statements: list[str] = []
        captured_state_keys: list[tuple[str, ...]] = []
        captured_pages: list[reviewer_ui.FacilityIntelligencePageRead] = []

        def capture_statement(
            _conn: Any,
            _cursor: Any,
            statement: str,
            _parameters: Any,
            _context: Any,
            _executemany: bool,
        ) -> None:
            statements.append(" ".join(statement.casefold().split()))

        original_page_read = reviewer_ui.list_authorized_facility_intelligence_page
        original_state_read = (
            reviewer_ui._reviewer_created_state_records_for_source_records
        )

        def capture_page(*args: Any, **kwargs: Any) -> Any:
            page = original_page_read(*args, **kwargs)
            captured_pages.append(page)
            return page

        def capture_state(
            context: reviewer_ui.ReviewerUiContext,
            source_record_keys: tuple[str, ...],
        ) -> Any:
            captured_state_keys.append(source_record_keys)
            return original_state_read(context, source_record_keys)

        def reject_unbounded_read(*_args: Any, **_kwargs: Any) -> Any:
            raise AssertionError("The facility route used the unbounded corpus read.")

        monkeypatch.setattr(
            reviewer_ui,
            "list_authorized_facility_intelligence_page",
            capture_page,
        )
        monkeypatch.setattr(
            reviewer_ui,
            "_reviewer_created_state_records_for_source_records",
            capture_state,
        )
        monkeypatch.setattr(
            reviewer_ui,
            "list_authorized_source_derived_records_by_entity_types",
            reject_unbounded_read,
        )
        event.listen(connection, "before_cursor_execute", capture_statement)
        try:
            status, _content_type, body = route_response(
                next_href,
                reviewer_ui_context=context,
            )
        finally:
            event.remove(connection, "before_cursor_execute", capture_statement)

    html = body.decode("utf-8")
    assert status == 200
    assert "Showing 26–50 of 51 facilities" in html
    assert len(captured_pages) == 1
    assert len(captured_pages[0].facility_identities) == 25
    assert len(captured_pages[0].records) == 75
    assert len(captured_state_keys) == 1
    assert len(captured_state_keys[0]) == 25
    offset_statements = [
        statement for statement in statements if " offset " in f" {statement} "
    ]
    assert not offset_statements, offset_statements
    assert any(
        "select count(*) as count_1 from facility_intelligence_facilities where"
        in statement
        for statement in statements
    )
    assert any(
        "select facility_intelligence_facilities.facility_identity" in statement
        and "where" in statement
        and "order by facility_intelligence_facilities.normalized_facility_name asc"
        in statement
        and " limit " in statement
        for statement in statements
    )
    assert any(
        "limit" in statement
        and "facility_intelligence_facilities" in statement
        for statement in statements
    )
    count_statements = [
        statement
        for statement in statements
        if "facility_intelligence_count_facts" in statement
    ]
    assert len(count_statements) == 1
    assert "substantiated_matches" not in count_statements[0]
    hydration_statements = [
        statement
        for statement in statements
        if "facility_intelligence_hydration_references" in statement
    ]
    assert len(hydration_statements) == 1
    assert "facility_id in" in hydration_statements[0]
    assert "source_record_key in" in hydration_statements[0]
    assert "substantiated_matches" not in hydration_statements[0]
    review_next_statements = [
        statement
        for statement in statements
        if "select facility_intelligence_facilities.facility_identity from "
        "facility_intelligence_facilities order by" in statement
    ]
    assert len(review_next_statements) == 1
    assert "limit 1" in review_next_statements[0]


def test_facility_intelligence_pagination_preserves_authorization_and_batch_isolation() -> None:
    with _priority_connection() as connection:
        _insert_facility_population(connection, 26)
        _insert_import_batch(connection, OTHER_SCOPE.scope_id)
        _insert_facility_bundle(
            connection,
            import_batch_id=OTHER_SCOPE.scope_id,
            facility_number="999999",
            facility_name="Outside Scope Center",
            facility_type="Children's Center",
            county="Kern",
            complaints=(_complaint("OUTSIDE-1", "2026-05-01", "Substantiated"),),
        )
        denied_status, _denied_type, denied_body = route_response(
            CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH,
            reviewer_ui_context=reviewer_ui_context_for_connection(
                connection,
                actor=None,
            ),
        )
        status, _content_type, body = route_response(
            CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH,
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    html = body.decode("utf-8")
    assert denied_status == 401
    assert "Facility intelligence unavailable" in denied_body.decode("utf-8")
    assert status == 200
    assert "Showing 1–25 of 26 facilities" in html
    assert "Outside Scope Center" not in html


@pytest.mark.parametrize(
    ("filters", "expected_facility_numbers"),
    (
        (
            source_derived_reads.FacilityIntelligenceReadFilters(
                sort="facility_name"
            ),
            {"100001", "200002", "300003", "400004", "500005"},
        ),
        (
            source_derived_reads.FacilityIntelligenceReadFilters(
                coverage="available",
                sort="facility_name",
            ),
            {"100001", "400004", "500005"},
        ),
        (
            source_derived_reads.FacilityIntelligenceReadFilters(
                coverage="partial",
                sort="facility_name",
            ),
            {"200002"},
        ),
        (
            source_derived_reads.FacilityIntelligenceReadFilters(
                coverage="unavailable",
                sort="facility_name",
            ),
            {"300003"},
        ),
        (
            source_derived_reads.FacilityIntelligenceReadFilters(
                finding="Substantiated",
                sort="facility_name",
            ),
            {"400004"},
        ),
        (
            source_derived_reads.FacilityIntelligenceReadFilters(
                facility_type="Foster Family Agency",
                sort="facility_name",
            ),
            {"400004"},
        ),
        (
            source_derived_reads.FacilityIntelligenceReadFilters(
                geography="Alameda",
                sort="facility_name",
            ),
            {"400004"},
        ),
        (
            source_derived_reads.FacilityIntelligenceReadFilters(
                serious_topic="Supervision topic",
                sort="facility_name",
            ),
            {"400004"},
        ),
    ),
    ids=(
        "all",
        "coverage-available",
        "coverage-partial",
        "coverage-unavailable",
        "finding",
        "facility-type",
        "geography",
        "serious-topic",
    ),
)
def test_optimized_facility_relations_preserve_filter_count_semantics(
    filters: source_derived_reads.FacilityIntelligenceReadFilters,
    expected_facility_numbers: set[str],
) -> None:
    with _priority_connection() as connection:
        _insert_semantic_parity_corpus(connection)
        page = source_derived_reads.list_facility_intelligence_page(
            connection,
            filters=filters,
            import_batch_id=TEST_SCOPE.scope_id,
        )

    expected_identities = {
        f"ccld:facility:{facility_number}"
        for facility_number in expected_facility_numbers
    }
    assert page.total_matching_facility_count == len(expected_identities)
    assert set(page.facility_identities) == expected_identities
    assert len(page.facility_identities) == len(set(page.facility_identities))
    assert page.total_authorized_facility_count == 5
    assert page.filter_options.facility_types == (
        "Children's Center",
        "Foster Family Agency",
        "unknown",
    )
    assert page.filter_options.geographies == ("Alameda", "Kern", "unknown")
    assert page.filter_options.findings == (
        "Inconclusive",
        "Pending",
        "Substantiated",
        "Unknown",
        "Unsubstantiated",
    )
    assert page.filter_options.serious_topics == ("Supervision topic",)
    complaint_ids = [
        str(record.original_values["complaint_id"])
        for record in page.records
        if record.entity_type == "complaint"
    ]
    facility_ids = [
        str(record.original_values["facility_id"])
        for record in page.records
        if record.entity_type == "facility"
    ]
    assert len(complaint_ids) == len(set(complaint_ids))
    assert len(facility_ids) == len(set(facility_ids))


def test_filter_options_do_not_invent_unknown_without_missing_facilities() -> None:
    with _priority_connection() as connection:
        _insert_facility_bundle(
            connection,
            facility_number="100001",
            facility_name="Known Center",
            facility_type="Children's Center",
            county="Kern",
            complaints=(
                _complaint("KNOWN-1", "2026-05-01", "Unsubstantiated"),
            ),
        )
        page = source_derived_reads.list_facility_intelligence_page(
            connection,
            filters=source_derived_reads.FacilityIntelligenceReadFilters(),
            import_batch_id=TEST_SCOPE.scope_id,
        )

    assert page.filter_options.facility_types == ("Children's Center",)
    assert page.filter_options.geographies == ("Kern",)
    assert "unknown" not in page.filter_options.facility_types
    assert "unknown" not in page.filter_options.geographies


def test_facility_intelligence_paginates_valid_governed_reimported_data() -> None:
    artifact = replace(
        load_seeded_corpus_artifact(
            Path("tests/fixtures/hosted_seeded_corpus/validated_seeded_corpus.json")
        ),
        import_batch_id=TEST_SCOPE.scope_id,
    )
    with _priority_connection() as connection:
        first_import = import_seeded_corpus_artifact(connection, artifact)
        second_import = import_seeded_corpus_artifact(connection, artifact)
        page = source_derived_reads.list_facility_intelligence_page(
            connection,
            filters=source_derived_reads.FacilityIntelligenceReadFilters(),
            import_batch_id=TEST_SCOPE.scope_id,
        )
        status, _content_type, body = route_response(
            CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH,
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    assert first_import.inserted_record_count == 7
    assert second_import.unchanged_record_count == 7
    assert page.total_matching_facility_count == 1
    assert page.total_authorized_facility_count == 1
    assert page.facility_identities == ("ccld:facility:157806098",)
    assert page.first_position == 1
    assert page.last_position == 1
    assert page.previous_anchor is None
    assert page.next_anchor is None
    assert len(
        [record for record in page.records if record.entity_type == "complaint"]
    ) == 1
    assert status == 200
    assert "Showing 1–1 of 1 facilities" in body.decode("utf-8")


def test_facility_hub_reuses_intelligence_aggregates_state_and_tie_order() -> None:
    with _priority_connection() as connection:
        _insert_facility_bundle(
            connection,
            facility_number="100001",
            facility_name="Alpha Center",
            facility_type="Children's Center",
            county="Kern",
            complaints=(
                _complaint("A-2", "2026-05-03", "Unsubstantiated"),
                _complaint(
                    "A-1",
                    "2026-05-03",
                    "Substantiated",
                    delay_days=120,
                    serious=True,
                ),
                _complaint("A-3", "2026-05-02", "Substantiated"),
                _complaint(
                    "A-4",
                    "2026-04-01",
                    "Unsubstantiated",
                    source_url="",
                ),
            ),
        )
        _insert_reviewer_state(
            connection,
            reviewer_state_id="state:a-1-status",
            source_record_key="complaint:ccld:complaint:A-1",
            created_at="2026-07-01T12:00:00+00:00",
            payload={
                "payload_kind": "reviewer_status_scaffold",
                "reviewer_status": "in_review",
            },
        )
        _insert_reviewer_state(
            connection,
            reviewer_state_id="state:a-1-note",
            source_record_key="complaint:ccld:complaint:A-1",
            created_at="2026-07-01T12:01:00+00:00",
            payload={
                "payload_kind": "reviewer_note_scaffold",
                "note_text": "Fixture note content must not render.",
            },
        )
        reviewer_context = reviewer_ui_context_for_connection(connection)
        before = _table_counts(connection)
        status, content_type, body = route_response(
            (
                f"{CCLD_FACILITY_REVIEW_HUB_PATH}?facility_number=100001"
                "&origin=facility_intelligence"
                "&date_dimension=complaint_received_date"
                "&start_date=2026-04-01&end_date=2026-05-31"
                "&coverage=partial"
            ),
            page_data_mode="postgres",
            ccld_record_request_ui_context=(
                ccld_record_request_context_for_reviewer_context(reviewer_context)
            ),
        )
        after = _table_counts(connection)

    html = body.decode("utf-8")
    normalized = " ".join(html.casefold().split())
    all_start = html.index('id="facility-hub-contributors-all"')
    all_end = html.index("</details>", all_start)
    all_contributors = html[all_start:all_end]

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert after == before
    assert "<h2 id=\"facility-hub-heading\">" in html
    assert ">Alpha Center<button" in html
    assert html.count("Primary facility facts") == 1
    assert html.count("<dt>Facility type</dt>") == 1
    assert "Opened from</dt><dd>Compare Facilities" in html
    assert "04/01/2026 to 05/31/2026" in html
    assert "Source coverage</dt><dd>Partial" in html
    assert "4</a></strong><span>Deduplicated complaints" in html
    assert "04/01/2026" in html
    assert "05/03/2026" in html
    assert "Substantiated: 2 exact complaint record(s)" in html
    assert "Unsubstantiated: 2 exact complaint record(s)" in html
    assert "Supervision topic: 1 exact complaint record(s)" in html
    assert "Trend or anomaly summary" in html
    assert "Increased activity" in html
    assert "Partial: " in html
    assert "3 with a CCLD report" in html
    assert "1 without a report link" in html
    assert "In review: 1 complaint record(s)" in html
    assert "Not started: 3 complaint record(s)" in html
    assert "1 note(s) across 1 complaint record(s)" in html
    assert "Open recommended complaint A-1" in html
    assert html.index("Open recommended complaint A-1") < html.index(
        "Open complaint record A-2"
    )
    for control_number in ("A-1", "A-2", "A-3", "A-4"):
        assert f"Open complaint record {control_number}" in all_contributors
    assert all_contributors.count("120+ day gap") == 1
    assert all_contributors.count("Supervision topic") == 1
    assert 'aria-label="Copy Facility ID"' in html
    assert 'aria-label="Copy complaint or control number"' in html
    assert 'aria-label="Copy complaint date"' in html
    assert 'aria-label="Copy complaint finding"' in html
    assert 'aria-label="Copy reviewer-created status"' in html
    assert 'aria-label="Copy original CCLD report URL"' in html
    assert 'class="inline-glossary-term"' in html
    assert 'aria-describedby="inline-glossary-definition-hub-finding"' in html
    assert 'id="inline-glossary-definition-hub-finding" role="tooltip"' in html
    assert "border-bottom: 1px dotted currentColor" in html
    assert (
        'class="is-active" aria-current="page" href="/ccld/facilities">Facilities</a>'
        in html
    )
    assert "Fixture note content must not render" not in html
    assert "raw_sha256" not in html
    assert "connector_name" not in html
    assert "tests/fixtures" not in html
    assert "local/test" not in normalized
    assert "source_record_key" not in html


def test_facility_hub_renders_complaint_context_without_directory_row() -> None:
    with _priority_connection() as connection:
        hosted_facility_reference_metadata.create_all(connection)
        _insert_facility_reference_row(connection, facility_number="200002")
        _insert_facility_bundle(
            connection,
            facility_number="157806098",
            facility_name="Corpus Only Center",
            facility_type="Children's Center",
            county="Kern",
            complaints=(
                _complaint("C-1", "2026-05-03", "Substantiated"),
            ),
        )
        reviewer_context = reviewer_ui_context_for_connection(connection)
        ccld_context = ccld_record_request_context_for_reviewer_context(reviewer_context)

        status, content_type, body = route_response(
            (
                f"{CCLD_FACILITY_REVIEW_HUB_PATH}?facility_number=157806098"
                "&origin=facility_intelligence"
                "&date_dimension=complaint_received_date"
                "&lookup_facility_name=Untrusted+Query+Facility"
            ),
            page_data_mode="postgres",
            ccld_record_request_ui_context=ccld_context,
        )
        unknown_status, unknown_content_type, unknown_body = route_response(
            f"{CCLD_FACILITY_REVIEW_HUB_PATH}?facility_number=999999999",
            page_data_mode="postgres",
            ccld_record_request_ui_context=ccld_context,
        )

    html = body.decode("utf-8")
    unknown_html = unknown_body.decode("utf-8")
    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Facility-directory result not found" not in html
    assert "Facility-directory record not available" not in html
    assert "Corpus Only Center" in html
    assert "Children&#x27;s Center" in html
    assert "Kern" in html
    assert "Source unavailable" in html
    assert "ccld:facility:157806098" not in html
    assert "Untrusted Query Facility" not in html
    assert "Review summary" in html
    assert "Review next" in html
    assert "Opened from</dt><dd>Compare Facilities" in html
    assert "complaint received date" in html.casefold()
    assert "157806098" in html
    assert "Different Directory Facility" not in html
    assert "Synthetic Orchard" not in html
    assert "A. MIRIAM JAMISON CHILDREN" not in html
    assert "Fixture/mock demo" not in html
    assert unknown_status == 200
    assert unknown_content_type == "text/html; charset=utf-8"
    assert "Facility-directory result not found" not in unknown_html
    assert "Source unavailable" in unknown_html
    assert "999999999" in unknown_html
    assert "No loaded complaint records are currently available" in unknown_html
    assert "Corpus Only Center" not in unknown_html
    assert "ccld:facility:999999999" not in unknown_html
    assert "Untrusted Query Facility" not in unknown_html


def _priority_connection() -> Connection:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)
    connection = engine.connect()
    _insert_import_batch(connection, TEST_SCOPE.scope_id)
    return connection


def _insert_facility_population(
    connection: Connection,
    facility_count: int,
    *,
    start_index: int = 0,
) -> None:
    for index in range(start_index, start_index + facility_count):
        _insert_facility_bundle(
            connection,
            facility_number=f"8{index:08d}",
            facility_name=f"Page Facility {index:03d}",
            facility_type="Children's Center",
            county="Kern",
            complaints=(
                _complaint(
                    f"PAGE-{index:03d}",
                    f"2026-05-{(index % 28) + 1:02d}",
                    "Unsubstantiated",
                ),
            ),
        )


def _insert_semantic_parity_corpus(connection: Connection) -> None:
    _insert_facility_bundle(
        connection,
        facility_number="100001",
        facility_name="Available Center",
        facility_type="Children's Center",
        county="Kern",
        complaints=(
            _complaint("AVAILABLE-1", "2026-05-01", "Unsubstantiated"),
        ),
    )
    _insert_facility_bundle(
        connection,
        facility_number="200002",
        facility_name="Partial Center",
        facility_type="Children's Center",
        county="Kern",
        complaints=(
            _complaint("PARTIAL-1", "2026-05-02", "Inconclusive"),
            _complaint(
                "PARTIAL-2",
                "2026-05-03",
                "Unknown",
                source_url="",
            ),
        ),
    )
    _insert_facility_bundle(
        connection,
        facility_number="300003",
        facility_name="Unavailable Center",
        facility_type="Children's Center",
        county="Kern",
        complaints=(
            _complaint(
                "UNAVAILABLE-1",
                "2026-05-04",
                "Unknown",
                source_url="",
            ),
        ),
    )
    _insert_facility_bundle(
        connection,
        facility_number="400004",
        facility_name="Serious Topic Center",
        facility_type="Foster Family Agency",
        county="Alameda",
        complaints=(
            _complaint(
                "SERIOUS-1",
                "2026-05-05",
                "Substantiated",
                serious=True,
            ),
        ),
    )
    _insert_complaint_without_facility(
        connection,
        facility_number="500005",
        control="MISSING-1",
        finding="Pending",
    )


def _insert_complaint_without_facility(
    connection: Connection,
    *,
    facility_number: str,
    control: str,
    finding: str,
) -> None:
    facility_id = f"ccld:facility:{facility_number}"
    document_id = f"ccld:document:{facility_number}:1"
    complaint_id = f"ccld:complaint:{control}"
    source_url = _source_url(facility_number, "1")
    connection.execute(
        hosted_source_derived_records.insert().values(
            **_source_record_values(
                import_batch_id=TEST_SCOPE.scope_id,
                entity_type="source_document",
                stable_source_id=document_id,
                source_document_id=document_id,
                facility_id=facility_id,
                source_url=source_url,
                original_values={
                    "document_id": document_id,
                    "facility_id": facility_id,
                },
            )
        )
    )
    connection.execute(
        hosted_source_derived_records.insert().values(
            **_source_record_values(
                import_batch_id=TEST_SCOPE.scope_id,
                entity_type="complaint",
                stable_source_id=complaint_id,
                source_document_id=document_id,
                facility_id=facility_id,
                source_url=source_url,
                original_values={
                    "complaint_id": complaint_id,
                    "facility_id": facility_id,
                    "document_id": document_id,
                    "complaint_control_number": control,
                    "complaint_received_date": "2026-05-06",
                    "finding": finding,
                },
            )
        )
    )


def _pagination_href(html: str, label: str) -> str | None:
    match = re.search(
        rf'<a class="button button-secondary facility-pagination__control" '
        rf'href="([^"]+)" aria-label="{label} facilities,[^"]+">{label}</a>',
        html,
    )
    return unescape(match.group(1)) if match is not None else None


def _continuation_with_payload_value(
    href: str,
    *,
    key: str,
    value: Any,
) -> str:
    parsed = urlsplit(href)
    query = parse_qs(parsed.query, keep_blank_values=True)
    token = query["continuation"][0]
    padded = token + "=" * (-len(token) % 4)
    payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
    payload[key] = value
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).decode("ascii").rstrip("=")
    query["continuation"] = [encoded]
    return f"{parsed.path}?{urlencode(query, doseq=True)}"


def _rendered_population_names(html: str) -> list[str]:
    return re.findall(
        r'<h3 id="facility-intelligence-result-[^"]+-heading">(Page Facility \d{3})</h3>',
        html,
    )


def _insert_reviewer_state(
    connection: Connection,
    *,
    reviewer_state_id: str,
    source_record_key: str,
    created_at: str,
    payload: Mapping[str, Any],
) -> None:
    connection.execute(
        hosted_reviewer_created_state.insert().values(
            reviewer_state_id=reviewer_state_id,
            source_record_key=source_record_key,
            scope_type=TEST_SCOPE.scope_type,
            scope_id=TEST_SCOPE.scope_id,
            state_kind="review_item_state_scaffold",
            state_payload=dict(payload),
            created_at=created_at,
            created_by_provider_subject="fixture-reviewer",
            created_by_provider_issuer="fixture-issuer",
            created_by_display_name="Fixture Reviewer",
            created_by_actor_category="tester",
            authorization_permission="reviewer_state_write",
        )
    )


def _insert_import_batch(connection: Connection, import_batch_id: str) -> None:
    connection.execute(
        hosted_import_batches.insert().values(
            import_batch_id=import_batch_id,
            imported_at="2026-07-01T12:00:00+00:00",
            source_artifact_identity=f"fixture-artifact:{import_batch_id}",
            source_pipeline_version="fixture-priority",
            validation_status="validated",
            raw_hash_validation_status="validated",
            record_counts={},
            warnings=[],
            errors=[],
        )
    )


def _insert_facility_reference_row(
    connection: Connection,
    *,
    facility_number: str,
) -> None:
    connection.execute(
        hosted_facility_reference_records.insert().values(
            source_resource_id="approved-directory-resource",
            facility_number=facility_number,
            facility_name="Different Directory Facility",
            source_resource_name="Approved facility directory",
            source_dataset_slug="approved-facility-directory",
            source_dataset_url=(
                "https://data.ca.gov/dataset/approved-facility-directory"
            ),
            source_accessed_at="2026-07-01T12:00:00+00:00",
            original_row_json={"facility_number": facility_number},
        )
    )


def _insert_facility_bundle(
    connection: Connection,
    *,
    facility_number: str,
    facility_name: str,
    facility_type: str,
    county: str,
    complaints: tuple[dict[str, Any], ...],
    import_batch_id: str = TEST_SCOPE.scope_id,
) -> None:
    facility_id = f"ccld:facility:{facility_number}"
    connection.execute(
        hosted_source_derived_records.insert().values(
            **_source_record_values(
                import_batch_id=import_batch_id,
                entity_type="facility",
                stable_source_id=facility_id,
                source_document_id=f"ccld:document:{facility_number}:facility",
                facility_id=facility_id,
                source_url=_source_url(facility_number, "0"),
                original_values={
                    "facility_id": facility_id,
                    "source_id": "ccld",
                    "external_facility_number": facility_number,
                    "facility_name": facility_name,
                    "facility_type": facility_type,
                    "county": county,
                },
            )
        )
    )
    for index, complaint in enumerate(complaints, start=1):
        document_id = f"ccld:document:{facility_number}:{index}"
        complaint_id = f"ccld:complaint:{complaint['control']}"
        source_url = complaint["source_url"]
        if source_url is None:
            source_url = _source_url(facility_number, str(index))
        connection.execute(
            hosted_source_derived_records.insert().values(
                **_source_record_values(
                    import_batch_id=import_batch_id,
                    entity_type="source_document",
                    stable_source_id=document_id,
                    source_document_id=document_id,
                    facility_id=facility_id,
                    source_url=source_url,
                    original_values={
                        "document_id": document_id,
                        "source_id": "ccld",
                        "facility_id": facility_id,
                        "source_url": source_url,
                        "retrieved_at": "2026-07-01T12:00:00+00:00",
                        "raw_sha256": "a" * 64,
                        "connector_name": "ccld_facility_reports",
                        "connector_version": "fixture-priority",
                        "document_type": "complaint_investigation_report",
                        "report_index": index,
                    },
                )
            )
        )
        if complaint.get("serious"):
            allegation_id = f"ccld:allegation:{complaint['control']}:1"
            connection.execute(
                hosted_source_derived_records.insert().values(
                    **_source_record_values(
                        import_batch_id=import_batch_id,
                        entity_type="allegation",
                        stable_source_id=allegation_id,
                        source_document_id=document_id,
                        facility_id=facility_id,
                        source_url=source_url,
                        original_values={
                            "allegation_id": allegation_id,
                            "complaint_id": complaint_id,
                            "allegation_category": "Inadequate supervision",
                            "allegation_text": "Fixture text must not render",
                        },
                    )
                )
            )
        original_values = {
            "complaint_id": complaint_id,
            "facility_id": facility_id,
            "document_id": document_id,
            "complaint_control_number": complaint["control"],
            "finding": complaint["finding"],
        }
        if complaint["date"]:
            original_values.update(
                {
                    "complaint_received_date": complaint["date"],
                    "visit_date": complaint["date"],
                    "report_date": complaint["date"],
                    "date_signed": complaint["date"],
                }
            )
        if complaint["delay_days"]:
            original_values[f"review_delay_over_{complaint['delay_days']}_days"] = True
        connection.execute(
            hosted_source_derived_records.insert().values(
                **_source_record_values(
                    import_batch_id=import_batch_id,
                    entity_type="complaint",
                    stable_source_id=complaint_id,
                    source_document_id=document_id,
                    facility_id=facility_id,
                    source_url=source_url,
                    source_record_key=f"complaint:{complaint_id}",
                    original_values=original_values,
                )
            )
        )


def _complaint(
    control: str,
    date: str,
    finding: str,
    *,
    delay_days: int = 0,
    source_url: str | None = None,
    serious: bool = False,
) -> dict[str, Any]:
    return {
        "control": control,
        "date": date,
        "finding": finding,
        "delay_days": delay_days,
        "source_url": source_url,
        "serious": serious,
    }


def _source_record_values(
    *,
    import_batch_id: str,
    entity_type: str,
    stable_source_id: str,
    source_document_id: str,
    facility_id: str,
    source_url: str,
    original_values: Mapping[str, Any],
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
        "raw_sha256": "a" * 64,
        "raw_path": "tests/fixtures/ccld/raw/157806098_inx3.html",
        "connector_name": "ccld_facility_reports",
        "connector_version": "fixture-priority",
        "retrieved_at": "2026-07-01T12:00:00+00:00",
        "original_values": dict(original_values),
        "source_traceability": {
            "source_document_id": source_document_id,
            "source_url": source_url,
            "raw_sha256": "a" * 64,
            "raw_path": "tests/fixtures/ccld/raw/157806098_inx3.html",
            "connector_name": "ccld_facility_reports",
            "connector_version": "fixture-priority",
            "retrieved_at": "2026-07-01T12:00:00+00:00",
            "source_artifact_identity": f"fixture-artifact:{import_batch_id}",
        },
    }


def _flat_source_record(
    entity_type: str,
    source_record_key: str,
    stable_source_id: str,
    source_document_id: str,
    facility_id: str,
    original_values: Mapping[str, Any],
) -> Mapping[str, Any]:
    return {
        **_source_record_values(
            import_batch_id=TEST_SCOPE.scope_id,
            entity_type=entity_type,
            stable_source_id=stable_source_id,
            source_document_id=source_document_id,
            facility_id=facility_id,
            source_url=_source_url("100001", "1"),
            source_record_key=source_record_key,
            original_values=original_values,
        ),
        "import_batch": {
            "import_batch_id": TEST_SCOPE.scope_id,
            "imported_at": "2026-07-01T12:00:00+00:00",
            "source_artifact_identity": "fixture-artifact",
            "source_pipeline_version": "fixture-priority",
            "validation_status": "validated",
            "raw_hash_validation_status": "validated",
            "record_counts": {},
            "warnings": [],
            "errors": [],
        },
    }


def _source_url(facility_number: str, report_index: str) -> str:
    return (
        "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports"
        f"?facNum={facility_number}&inx={report_index}"
    )


def _actor(
    *,
    roles: tuple[str, ...],
    scopes: tuple[HostedAccessScope, ...] = (TEST_SCOPE,),
    account_status: str = "active",
) -> AuthenticatedActor:
    return AuthenticatedActor(
        provider_subject="fixture-ui-reviewer",
        provider_issuer="fixture-managed-oidc-provider",
        display_name="Fixture UI Reviewer",
        email=None,
        actor_category=cast(HostedActorCategory, "tester"),
        account_status=cast(HostedAccountStatus, account_status),
        roles=tuple(cast(HostedTesterRole, role) for role in roles),
        scopes=scopes,
    )


def _table_counts(connection: Connection) -> dict[str, int]:
    return {
        "import_batches": connection.execute(
            select(func.count()).select_from(hosted_import_batches)
        ).scalar_one(),
        "source_records": connection.execute(
            select(func.count()).select_from(hosted_source_derived_records)
        ).scalar_one(),
        "retrieval_jobs": connection.execute(
            select(func.count()).select_from(hosted_ccld_retrieval_jobs)
        ).scalar_one(),
    }
