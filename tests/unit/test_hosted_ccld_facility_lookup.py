from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from typing import Any, cast

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Connection

from ccld_complaints.hosted_app import ccld_facility_lookup as facility_lookup
from ccld_complaints.hosted_app import facility_review_signals as review_signals
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
    CCLD_FACILITY_LOOKUP_PATH,
    CCLD_FACILITY_REFERENCE_CSV_ENV,
    CCLD_FACILITY_REVIEW_HUB_PATH,
    CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH,
    CCLD_FACILITY_REVIEW_PRIORITY_PATH,
    CCLD_RECORD_REQUEST_PATH,
    PRELOADED_FACILITY_DIRECTORY_EXAMPLE_NUMBER,
    CcldFacilityLookupRecord,
    CcldFacilityReferenceSource,
    load_active_ccld_facility_reference,
    load_ccld_facility_reference,
    no_reference_facility_source,
    render_ccld_facility_lookup_page,
    search_ccld_facilities,
)
from ccld_complaints.hosted_app.ccld_record_request_ui import (
    ccld_record_request_context_for_reviewer_context,
)
from ccld_complaints.hosted_app.facility_review_signals import (
    FACILITY_REVIEW_SIGNALS_CSVS_ENV,
)
from ccld_complaints.hosted_app.reset_reload_dry_run import (
    hosted_reset_reload_planning_metadata,
)
from ccld_complaints.hosted_app.reviewer_created_state import hosted_reviewer_created_state
from ccld_complaints.hosted_app.reviewer_ui import (
    LOCAL_REVIEWER_UI_SCOPE,
    REVIEWER_UI_MATRIX_EXPORT_PATH,
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


class _ButtonClassParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._button_stack: list[dict[str, str]] = []
        self._button_text: list[str] = []
        self.buttons: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "button":
            self._button_stack.append({key: value or "" for key, value in attrs})
            self._button_text.append("")

    def handle_data(self, data: str) -> None:
        if self._button_stack:
            self._button_text[-1] += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "button" and self._button_stack:
            attrs = self._button_stack.pop()
            text = " ".join(self._button_text.pop().split())
            self.buttons.append((text, attrs.get("class", "")))


def _button_classes(html: str, text: str) -> list[str]:
    parser = _ButtonClassParser()
    parser.feed(html)
    return [classes for button_text, classes in parser.buttons if button_text == text]


def _assert_primary_button(html: str, text: str) -> None:
    matching_classes = _button_classes(html, text)
    assert matching_classes
    for classes in matching_classes:
        class_names = set(classes.split())
        assert "secondary" not in class_names
        assert "button-secondary" not in class_names
        assert "button secondary" not in classes


def _assert_collapsed_disclosure(html: str, label: str) -> None:
    summary = f"<summary>{label}</summary>"
    summary_index = html.index(summary)
    details_start = html.rfind("<details", 0, summary_index)
    assert details_start != -1
    details_tag = html[details_start : html.index(">", details_start) + 1]
    assert " open" not in details_tag


@pytest.fixture(autouse=True)
def _ignore_local_default_full_facility_reference(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        facility_lookup,
        "DEFAULT_FULL_CCLD_FACILITY_REFERENCE_PATH",
        tmp_path / "missing-facility-reference.csv",
    )
    monkeypatch.setattr(
        review_signals,
        "DEFAULT_FACILITY_REVIEW_SIGNAL_PATHS",
        (tmp_path / "missing-review-signals.csv",),
    )


def _local_dev_auth_config() -> Any:
    return load_hosted_auth_runtime_config(
        environ={
            "CCLD_HOSTED_TESTER_AUTH_MODE": "local-dev",
            "CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH": "enabled",
        }
    )


def test_ccld_facility_reference_loads_safe_lookup_columns() -> None:
    records = load_ccld_facility_reference()

    assert len(records) == 2
    assert records == tuple(sorted(records, key=lambda record: record.facility_name))
    assert records[0] == CcldFacilityLookupRecord(
        facility_number="900000001",
        facility_name="Synthetic Orchard Child Care",
        city="Sample City",
        state="CA",
        county="Los Angeles",
        zip_code="90001",
        facility_type="Child Care Center",
        program_type="",
        capacity="24",
        status="Licensed",
        closed_date="",
    )
    assert {record.facility_number for record in records} == {"900000001", "900000002"}


def test_postgres_mode_without_database_shows_setup_required_state() -> None:
    status, content_type, body = route_response(
        CCLD_FACILITY_LOOKUP_PATH,
        auth_runtime_config=_local_dev_auth_config(),
        page_data_mode="postgres",
    )
    html = body.decode("utf-8")

    assert status == 503
    assert content_type == "text/html; charset=utf-8"
    assert "Facility search setup required" in html
    assert "Source-derived records are not yet available" in html
    assert "Check that the database is migrated" in html
    assert_no_secret_html(html)


def test_postgres_mode_facility_lookup_uses_source_derived_records() -> None:
    with _seeded_connection() as connection:
        context = ccld_record_request_context_for_reviewer_context(
            reviewer_ui_context_for_connection(
                connection,
                actor=_actor(roles=("tester_reviewer",)),
            )
        )
        status, content_type, body = route_response(
            f"{CCLD_FACILITY_LOOKUP_PATH}?q=157806098",
            auth_runtime_config=_local_dev_auth_config(),
            page_data_mode="postgres",
            ccld_record_request_ui_context=context,
        )
        counts = _table_counts(connection)

    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Find CCLD facility" in html
    assert "157806098" in html
    assert "A. MIRIAM JAMISON CHILDREN" in html
    assert "Tiny committed CCLD facility fixture fallback" not in html
    assert counts == _empty_reviewer_counts()
    assert_no_secret_html(html)


def test_active_ccld_facility_reference_uses_tiny_fallback_when_full_csv_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(CCLD_FACILITY_REFERENCE_CSV_ENV, raising=False)

    source = load_active_ccld_facility_reference()

    assert source.source_kind == "tiny_fixture_fallback"
    assert source.label == "Tiny committed CCLD facility fixture fallback"
    assert source.path_label == (
        "tests/fixtures/public_source_facilities/ccld_program_facilities_tiny.csv"
    )
    assert len(source.records) == 2
    assert source.warnings == (
        "No full CCLD facility reference CSV is configured or available. "
        "Using tiny fixture fallback.",
    )


def test_active_ccld_facility_reference_uses_configured_full_local_csv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    full_csv = tmp_path / "full-ccld-facilities.csv"
    _write_facility_reference_csv(
        full_csv,
        rows=(
            {
                "Facility Type": "Adult Residential Facility",
                "Facility Number": "910000001",
                "Facility Name": "Full Reference Orchard Home",
                "Facility City": "Fullerton",
                "Facility Zip": "92832",
                "County Name": "Orange",
                "Facility Status": "Licensed",
                "Closed Date": "",
                "Licensee": "Do Not Display Licensee",
                "Facility Administrator": "Do Not Display Admin",
                "Facility Telephone Number": "555-0199",
                "Facility Address": "1 Private Fixture Way",
            },
        ),
    )
    monkeypatch.setenv(CCLD_FACILITY_REFERENCE_CSV_ENV, str(full_csv))

    source = load_active_ccld_facility_reference()
    result = search_ccld_facilities(
        "fullerton adult",
        source.records,
        reference_source=source,
    )

    assert source.source_kind == "full_local_test_csv"
    assert source.label == "Full CCLD facility reference CSV"
    assert source.path_label == full_csv.name
    assert source.warnings == ()
    assert [record.facility_number for record in result.returned_records] == ["910000001"]
    assert result.reference_source == source


def test_active_ccld_facility_reference_loads_cdss_chhs_facility_directory_shape(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    full_csv = tmp_path / "CDSS_CCL_Facilities_2065342970436235361.csv"
    _write_chhs_facility_directory_csv(
        full_csv,
        rows=(
            {
                "FAC_NBR": "214005552",
                "NAME": "SUSD- TOMALES PRESCHOOL",
                "PROGRAM_TYPE": "CHILD CARE",
                "STATUS": "3",
                "CAPACITY": "24",
                "RES_CITY": "TOMALES",
                "RES_STATE": "CA",
                "RES_ZIP_CODE": "94971",
                "COUNTY": "Marin",
                "FAC_TYPE_DESC": "DAY CARE CENTER",
                "RES_STREET_ADDR": "40 JOHN STREET",
                "FAC_PHONE_NBR": "7078782214",
                "FAC_LATITUDE": "38.24546602",
                "FAC_LONGITUDE": "-122.901353",
            },
        ),
    )
    monkeypatch.setenv(CCLD_FACILITY_REFERENCE_CSV_ENV, str(full_csv))

    source = load_active_ccld_facility_reference()
    [record] = source.records

    assert source.source_kind == "full_local_test_csv"
    assert source.path_label == full_csv.name
    assert record.facility_number == "214005552"
    assert isinstance(record.facility_number, str)
    assert record.facility_name == "SUSD- TOMALES PRESCHOOL"
    assert record.city == "TOMALES"
    assert record.state == "CA"
    assert record.county == "Marin"
    assert record.zip_code == "94971"
    assert record.facility_type == "DAY CARE CENTER"
    assert record.program_type == "CHILD CARE"
    assert record.capacity == "24"
    assert record.status == "3"
    assert record.closed_date == ""


def test_cdss_chhs_facility_directory_searches_supported_fields(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    full_csv = tmp_path / "facility-reference.csv"
    _write_chhs_facility_directory_csv(
        full_csv,
        rows=(
            {
                "FAC_NBR": "214005552",
                "NAME": "SUSD- TOMALES PRESCHOOL",
                "PROGRAM_TYPE": "CHILD CARE",
                "STATUS": "3",
                "CAPACITY": "24",
                "RES_CITY": "TOMALES",
                "RES_STATE": "CA",
                "RES_ZIP_CODE": "94971",
                "COUNTY": "Marin",
                "FAC_TYPE_DESC": "DAY CARE CENTER",
            },
            {
                "FAC_NBR": "496804122",
                "NAME": "MIRABEL LODGE",
                "PROGRAM_TYPE": "ADULT AND SENIOR",
                "STATUS": "3",
                "CAPACITY": "34",
                "RES_CITY": "FORESTVILLE",
                "RES_STATE": "CA",
                "RES_ZIP_CODE": "95436",
                "COUNTY": "Sonoma",
                "FAC_TYPE_DESC": "RESIDENTIAL-ELDERLY",
            },
        ),
    )
    monkeypatch.setenv(CCLD_FACILITY_REFERENCE_CSV_ENV, str(full_csv))
    records = load_active_ccld_facility_reference().records

    assert _matching_facility_numbers("214005", records) == ["214005552"]
    assert _matching_facility_numbers("tomales preschool", records) == ["214005552"]
    assert _matching_facility_numbers("forestville sonoma", records) == ["496804122"]
    assert _matching_facility_numbers("95436", records) == ["496804122"]
    assert _matching_facility_numbers("residential elderly", records) == ["496804122"]
    assert _matching_facility_numbers("adult senior", records) == ["496804122"]
    assert _matching_facility_numbers("capacity 34", records) == []
    assert _matching_facility_numbers("34", records) == ["496804122"]


def test_facility_directory_duplicate_facility_numbers_are_deterministic(
    tmp_path: Path,
) -> None:
    full_csv = tmp_path / "duplicate-facility-reference.csv"
    _write_chhs_facility_directory_csv(
        full_csv,
        rows=(
            {
                "FAC_NBR": "900123456",
                "NAME": "DUPLICATE NUMBER CHILD CARE",
                "PROGRAM_TYPE": "CHILD CARE",
                "STATUS": "3",
                "CAPACITY": "24",
                "RES_CITY": "ALPHA",
                "RES_STATE": "CA",
                "RES_ZIP_CODE": "90001",
                "COUNTY": "Los Angeles",
                "FAC_TYPE_DESC": "DAY CARE CENTER",
            },
            {
                "FAC_NBR": "900123456",
                "NAME": "DUPLICATE NUMBER CHILD CARE",
                "PROGRAM_TYPE": "CHILD CARE",
                "STATUS": "3",
                "CAPACITY": "24",
                "RES_CITY": "ALPHA",
                "RES_STATE": "CA",
                "RES_ZIP_CODE": "90001",
                "COUNTY": "Los Angeles",
                "FAC_TYPE_DESC": "DAY CARE CENTER",
            },
            {
                "FAC_NBR": "900123456",
                "NAME": "DUPLICATE NUMBER SENIOR CARE",
                "PROGRAM_TYPE": "ADULT AND SENIOR",
                "STATUS": "3",
                "CAPACITY": "12",
                "RES_CITY": "BETA",
                "RES_STATE": "CA",
                "RES_ZIP_CODE": "90002",
                "COUNTY": "Los Angeles",
                "FAC_TYPE_DESC": "RESIDENTIAL-ELDERLY",
            },
        ),
    )

    records = load_ccld_facility_reference(full_csv)
    result = search_ccld_facilities("900123456", records, result_limit=10)

    assert len(records) == 2
    assert [record.facility_name for record in records] == [
        "DUPLICATE NUMBER CHILD CARE",
        "DUPLICATE NUMBER SENIOR CARE",
    ]
    assert [record.facility_number for record in result.returned_records] == [
        "900123456",
        "900123456",
    ]


def test_ccld_facility_lookup_route_renders_configured_full_csv_source(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    full_csv = tmp_path / "full-ccld-facilities.csv"
    _write_facility_reference_csv(
        full_csv,
        rows=(
            {
                "Facility Type": "Adult Residential Facility",
                "Facility Number": "910000001",
                "Facility Name": "Full Reference Orchard Home",
                "Facility City": "Fullerton",
                "Facility Zip": "92832",
                "County Name": "Orange",
                "Facility Status": "Licensed",
                "Closed Date": "",
                "Licensee": "Do Not Display Licensee",
                "Facility Administrator": "Do Not Display Admin",
                "Facility Telephone Number": "555-0199",
                "Facility Address": "1 Private Fixture Way",
            },
        ),
    )
    monkeypatch.setenv(CCLD_FACILITY_REFERENCE_CSV_ENV, str(full_csv))

    status, content_type, body = route_response(
        f"{CCLD_FACILITY_LOOKUP_PATH}?q=fullerton",
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Find CCLD facility" in html
    assert "CCLD RecordsTracker" in html
    assert "Do Not Display" not in html
    assert "555-0199" not in html
    assert "1 Private Fixture Way" not in html
    assert_no_secret_html(html)


def test_configured_missing_full_csv_falls_back_with_guidance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    missing_path = tmp_path / "missing-ccld-facilities.csv"
    monkeypatch.setenv(CCLD_FACILITY_REFERENCE_CSV_ENV, str(missing_path))

    status, content_type, body = route_response(
        f"{CCLD_FACILITY_LOOKUP_PATH}?q=orchard",
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Limited reference list" in html
    assert "Configured full CCLD facility reference CSV was not found" in html
    assert "Using tiny fixture fallback." in html
    assert "Synthetic Orchard Child Care" in html
    assert_no_secret_html(html)


def test_configured_malformed_full_csv_falls_back_with_guidance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    malformed_path = tmp_path / "malformed-ccld-facilities.csv"
    malformed_path.write_text("Facility Name,Facility City\nBad Row,Nowhere\n", encoding="utf-8")
    monkeypatch.setenv(CCLD_FACILITY_REFERENCE_CSV_ENV, str(malformed_path))

    status, content_type, body = route_response(
        f"{CCLD_FACILITY_LOOKUP_PATH}?q=orchard",
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Limited reference list" in html
    assert "could not be loaded" in html
    assert "Facility Number" in html
    assert "Using tiny fixture fallback." in html
    assert "Synthetic Orchard Child Care" in html
    assert_no_secret_html(html)


def test_ccld_facility_search_matches_name_id_city_county_zip_type_and_status() -> None:
    records = load_ccld_facility_reference()

    assert _matching_facility_numbers("orchard", records) == ["900000001"]
    assert _matching_facility_numbers("900000002", records) == ["900000002"]
    assert _matching_facility_numbers("sample city", records) == ["900000001"]
    assert _matching_facility_numbers("SACRAMENTO", records) == ["900000002"]
    assert _matching_facility_numbers("90001", records) == ["900000001"]
    assert _matching_facility_numbers("foster agency", records) == ["900000002"]
    assert _matching_facility_numbers("licensed", records) == ["900000001"]


def test_ccld_facility_search_is_bounded_and_deterministic() -> None:
    records = tuple(
        CcldFacilityLookupRecord(
            facility_number=f"9000000{index:02d}",
            facility_name=f"Synthetic Match {index:02d}",
            city="Sample City",
            state="CA",
            county="Los Angeles",
            zip_code="90001",
            facility_type="Child Care Center",
            program_type="Child Care",
            capacity="24",
            status="Licensed",
            closed_date="",
        )
        for index in range(30)
    )

    first = search_ccld_facilities("synthetic", records, result_limit=25)
    second = search_ccld_facilities("synthetic", records, result_limit=25)

    assert first == second
    assert first.total_match_count == 30
    assert len(first.returned_records) == 25
    assert first.has_more_matches is True
    assert first.returned_records[0].facility_number == "900000000"
    assert first.returned_records[-1].facility_number == "900000024"


def test_ccld_facility_lookup_page_shows_empty_search_guidance() -> None:
    status, content_type, body = route_response(
        CCLD_FACILITY_LOOKUP_PATH,
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Find CCLD facility" in html
    assert "Skip to main CCLD facility lookup content" in html
    assert '<main id="main-content" tabindex="-1">' in html
    assert "Find a facility" in html
    assert "Start review by finding the CCLD facility/license number" in html
    assert "preloaded facility directory" in html
    assert "Lookup or manual entry?" not in html
    assert "<summary>When to use lookup vs. manual entry</summary>" in html
    assert "Use facility lookup when you know a facility name" in html
    assert "facility type, program type, or status code" in html
    assert "Use manual entry when you already know the digit facility/license number" in html
    assert "Try a preloaded facility-directory example" in html
    assert "known loaded facility 434417302" in html
    assert f"{CCLD_FACILITY_REVIEW_HUB_PATH}?facility_number=434417302" in html
    assert PRELOADED_FACILITY_DIRECTORY_EXAMPLE_NUMBER == "434417302"
    assert "Lookup rows are public facility-directory data" in html
    assert "Complaint records are retrieved separately" in html
    assert "not complaint coverage" in html
    assert "not source-completeness proof" in html
    assert "not license-validity proof" in html
    assert 'for="facility-search-input"' in html
    example_index = html.index("Try a preloaded facility-directory example")
    form_index = html.index(
        f'<form action="{CCLD_FACILITY_LOOKUP_PATH}" method="get" class="facility-search-form">'
    )
    disclosure_index = html.index("<summary>When to use lookup vs. manual entry</summary>")
    pre_form_html = html[:form_index]
    assert example_index < form_index < disclosure_index
    assert "Use facility lookup when you know a facility name" not in pre_form_html
    assert (
        "Use manual entry when you already know the digit facility/license number"
        not in pre_form_html
    )
    assert "Lookup rows are public facility-directory data" not in pre_form_html
    _assert_collapsed_disclosure(html, "When to use lookup vs. manual entry")
    assert "facility-suggestion-list" in html
    assert "Search CCLD facilities" in html
    _assert_primary_button(html, "Search CCLD facilities")
    assert any(
        "button-secondary" in classes
        for classes in _button_classes(html, "Change selected facility")
    )
    assert "Search by name, license number, city, county, ZIP" in (
        normalized_html
    )
    assert "facility type, program type, or status code" in normalized_html
    assert "Keyboard flow: type a search, use arrow keys or Tab" not in html
    assert "selected facility link to continue to the request page" not in html
    assert "Enter a facility/license number directly" in html
    assert "Open request form" in html
    assert "CCLD public portal remains" in html
    assert_no_secret_html(html)


def test_ccld_facility_lookup_page_renders_results_and_use_link() -> None:
    status, content_type, body = route_response(
        f"{CCLD_FACILITY_LOOKUP_PATH}?q=orchard",
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())
    request_href = f"{CCLD_RECORD_REQUEST_PATH}?facility_number=900000001"

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Facility matches" in html
    assert "Facility-directory results" in html
    assert "These are public facility-directory results" in html
    assert "Complaint records are retrieved separately" in html
    assert "Showing 1 of 1 matching facility." in normalized_html
    assert "Start complaint request for facility 900000001" in html
    assert "Open facility review hub" in html
    assert f"{CCLD_FACILITY_REVIEW_HUB_PATH}?facility_number=900000001" in html
    assert "Find a facility" in html
    assert request_href in html
    assert "request_context_origin=facility_lookup" in html
    assert "lookup_facility_name=Synthetic+Orchard+Child+Care" in html
    assert "900000001" in html
    assert "Synthetic Orchard Child Care" in html
    assert "Sample City" in html
    assert "CA 90001" in html
    assert "Los Angeles" in html
    assert "90001" in html
    assert "Child Care Center" in html
    assert "Capacity directory field" in html
    assert "24" in html
    assert "Status code directory field" in html
    assert "Licensed" in html
    assert "Example Licensee" not in html
    assert "555-0101" not in html
    assert "100 Example Way" not in html
    assert_no_secret_html(html)


def test_ccld_facility_review_hub_renders_safe_directory_context() -> None:
    status, content_type, body = route_response(
        f"{CCLD_FACILITY_REVIEW_HUB_PATH}?facility_number=900000001",
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Facility review hub" in html
    assert "Facility-directory context" in html
    assert "Synthetic Orchard Child Care" in html
    assert "Facility-directory details" in html
    assert "Facility number directory field" in html
    assert "900000001" in html
    assert "Program type directory field" in html
    assert "Facility type directory field" in html
    assert "Child Care Center" in html
    assert "City/state/ZIP directory field" in html
    assert "Sample City, CA 90001" in html
    assert "County directory field" in html
    assert "Los Angeles" in html
    assert "Capacity directory field" in html
    assert "24" in html
    assert "Status code directory field" in html
    assert "Licensed" in html
    assert "Complaint records are requested and reviewed separately" in html
    assert "public CCLD portal remains the source of record" in html
    assert "No complaint context is currently available" in html
    assert "Date range is needed before the review queue" in html
    assert "Start complaint request for this facility" in html
    assert "Return to facility lookup" in html
    assert f"{CCLD_RECORD_REQUEST_PATH}?facility_number=900000001" in html
    assert "does not check all complaints" in normalized_html
    assert "does not prove complaint coverage" in normalized_html
    assert (
        "does not prove complaint coverage, source completeness, license validity"
        in normalized_html
    )
    assert "Opening this page does not auto-submit retrieval" in normalized_html
    assert "create reviewer-created notes/statuses" in normalized_html
    assert "Example Licensee" not in html
    assert "555-0101" not in html
    assert "100 Example Way" not in html
    assert_no_secret_html(html)


def test_ccld_facility_review_hub_known_loaded_preloaded_example_renders(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    full_csv = tmp_path / "facility-reference.csv"
    _write_chhs_facility_directory_csv(
        full_csv,
        rows=(
            {
                "FAC_NBR": "434417302",
                "NAME": "7 MAGIC FLOWERS BILINGUAL MONTESSORI PRESCHOOL",
                "PROGRAM_TYPE": "CHILD CARE",
                "STATUS": "3",
                "CAPACITY": "45",
                "RES_CITY": "SAN JOSE",
                "RES_STATE": "CA",
                "RES_ZIP_CODE": "95112",
                "COUNTY": "Santa Clara",
                "FAC_TYPE_DESC": "DAY CARE CENTER",
            },
        ),
    )
    monkeypatch.setenv(CCLD_FACILITY_REFERENCE_CSV_ENV, str(full_csv))

    status, content_type, body = route_response(
        f"{CCLD_FACILITY_REVIEW_HUB_PATH}?facility_number=434417302",
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Facility review hub" in html
    assert "Facility-directory result not found" not in html
    assert "7 MAGIC FLOWERS BILINGUAL MONTESSORI PRESCHOOL" in html
    assert "434417302" in html
    assert "DAY CARE CENTER" in html
    assert "Santa Clara" in html
    assert "Complaint records are requested and reviewed separately" in html
    assert_no_secret_html(html)


def test_ccld_facility_review_hub_not_found_state_is_safe() -> None:
    status, content_type, body = route_response(
        f"{CCLD_FACILITY_REVIEW_HUB_PATH}?facility_number=999999999",
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Facility-directory result not found" in html
    assert "999999999" in html
    assert "does not prove the facility is absent from public sources" in normalized_html
    assert "does not prove complaint availability" in normalized_html
    assert "does not validate or invalidate a license" in normalized_html
    assert "Return to facility lookup" in html
    assert "Start complaint request for facility 999999999" in html
    assert_no_secret_html(html)


def test_ccld_facility_review_hub_renders_signal_only_context_without_mutation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    facility_csv = tmp_path / "facility-reference.csv"
    signals_csv = tmp_path / "24HourResidentialCareforChildren06072026.csv"
    _write_chhs_facility_directory_csv(
        facility_csv,
        rows=(
            {
                "FAC_NBR": "434417302",
                "NAME": "7 MAGIC FLOWERS BILINGUAL MONTESSORI PRESCHOOL",
                "PROGRAM_TYPE": "CHILD CARE",
                "STATUS": "3",
                "CAPACITY": "45",
                "RES_CITY": "SAN JOSE",
                "RES_STATE": "CA",
                "RES_ZIP_CODE": "95112",
                "COUNTY": "Santa Clara",
                "FAC_TYPE_DESC": "DAY CARE CENTER",
            },
        ),
    )
    _write_program_summary_signals_csv(
        signals_csv,
        rows=(
            {
                "Facility Type": "TEMPORARY SHELTER CARE FACILITY",
                "Facility Number": "157806098",
                "Facility Name": "A. MIRIAM JAMISON CHILDREN'S CENTER",
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
                "Inspect TypeA": "",
                "Inspect TypeB": "",
                "Other TypeA": "A citation",
                "Other TypeB": "B citation",
            },
        ),
    )
    monkeypatch.setenv(CCLD_FACILITY_REFERENCE_CSV_ENV, str(facility_csv))
    monkeypatch.setenv(FACILITY_REVIEW_SIGNALS_CSVS_ENV, str(signals_csv))

    with _seeded_connection() as connection:
        before_source_rows = _source_rows(connection)
        before_counts = _table_counts(connection)
        status, content_type, body = route_response(
            f"{CCLD_FACILITY_REVIEW_HUB_PATH}?facility_number=157806098",
            page_data_mode="fixture-demo",
            ccld_record_request_ui_context=ccld_record_request_context_for_reviewer_context(
                reviewer_ui_context_for_connection(
                    connection,
                    actor=_actor(roles=("tester_reviewer",)),
                )
            ),
        )
        after_source_rows = _source_rows(connection)
        after_counts = _table_counts(connection)

    html = body.decode("utf-8")
    normalized_html = " ".join(html.split()).casefold()

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert before_source_rows == after_source_rows
    assert before_counts == after_counts == _empty_reviewer_counts()
    assert "signal-only facility hub" in html
    assert "Facility-directory record not available" in html
    assert "Showing uploaded public summary fields" in html
    assert "A. MIRIAM JAMISON CHILDREN&#x27;S CENTER" in html
    assert "157806098" in html
    assert "TEMPORARY SHELTER CARE FACILITY" in html
    assert "KERN" in html
    assert "LICENSED" in html
    assert "48" in html
    assert "2026-05-04" in html
    assert "43 total; 0 inspection; 12 complaint; 31 other" in html
    assert "Complaint visit activity present review cue" in html
    assert "Citation indicator present review cue" in html
    assert "POC indicator present review cue" in html
    assert "Start complaint request for this facility" in html
    assert f"{CCLD_RECORD_REQUEST_PATH}?facility_number=157806098" in html
    assert "Open facility review priority list" in html
    assert "Return to facility lookup" in html
    assert "1 loaded complaint record(s)" in html
    assert "/reviewer/packet/preview?facility_number=157806098" in html
    assert "not a facility-directory record" in normalized_html
    assert "not source verification" in normalized_html
    assert "not a complaint-coverage determination" in normalized_html
    assert "not a source-completeness proof" in normalized_html
    assert "not a legal finding" in normalized_html
    assert "complaint records are requested/reviewed separately" in normalized_html
    assert "verified complaint" not in normalized_html
    assert "facility has no complaints" not in normalized_html
    assert "source complete" not in normalized_html
    assert "directory error" not in normalized_html
    assert "missing from official records" not in normalized_html
    assert "Do Not Display" not in html
    assert "555-0199" not in html
    assert "1 Private Fixture Way" not in html
    assert_no_secret_html(html)


def test_ccld_facility_review_hub_shows_loaded_complaint_context_without_mutation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # 157806098 is used here as the seeded manual complaint request context.
    # Preloaded facility-directory examples use 434417302.
    full_csv = tmp_path / "facility-reference.csv"
    _write_chhs_facility_directory_csv(
        full_csv,
        rows=(
            {
                "FAC_NBR": "157806098",
                "NAME": "A. MIRIAM JAMISON CHILDREN'S CENTER",
                "PROGRAM_TYPE": "CHILD CARE",
                "STATUS": "3",
                "CAPACITY": "24",
                "RES_CITY": "BAKERSFIELD",
                "RES_STATE": "CA",
                "RES_ZIP_CODE": "93307",
                "COUNTY": "Kern",
                "FAC_TYPE_DESC": "CHILDREN'S CENTER",
            },
        ),
    )
    monkeypatch.setenv(CCLD_FACILITY_REFERENCE_CSV_ENV, str(full_csv))

    with _seeded_connection() as connection:
        before_source_rows = _source_rows(connection)
        before_counts = _table_counts(connection)
        status, content_type, body = route_response(
            f"{CCLD_FACILITY_REVIEW_HUB_PATH}?facility_number=157806098",
            page_data_mode="fixture-demo",
            ccld_record_request_ui_context=ccld_record_request_context_for_reviewer_context(
                reviewer_ui_context_for_connection(
                    connection,
                    actor=_actor(roles=("tester_reviewer",)),
                )
            ),
        )
        after_source_rows = _source_rows(connection)
        after_counts = _table_counts(connection)

    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert before_source_rows == after_source_rows
    assert before_counts == after_counts == _empty_reviewer_counts()
    assert "A. MIRIAM JAMISON CHILDREN&#x27;S CENTER" in html
    assert "1 loaded complaint record(s)" in html
    assert "2022-04-07 to 2022-08-26" in html
    assert "Review loaded records for this facility/date context" in html
    assert "Open reviewer queue filtered to this facility" in html
    assert "/reviewer/records?q=157806098" in html
    assert "Download complaint review matrix CSV" in html
    assert f"{REVIEWER_UI_MATRIX_EXPORT_PATH}?facility_number=157806098" in html
    assert "Open packet preview for this facility/date context" in html
    assert "/reviewer/packet/preview?facility_number=157806098" in html
    assert "start_date=2022-04-07" in html
    assert "end_date=2022-08-26" in html
    assert "Open packet draft for this facility/date context" in html
    assert "not complaint coverage" in normalized_html
    assert "not public-source absence proof" in normalized_html
    assert "not a source-completeness proof" in normalized_html
    assert_no_secret_html(html)


def test_ccld_facility_review_hub_renders_uploaded_public_summary_signals(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    facility_csv = tmp_path / "facility-reference.csv"
    signals_csv = tmp_path / "24HourResidentialCareforChildren06072026.csv"
    _write_chhs_facility_directory_csv(
        facility_csv,
        rows=(
            {
                "FAC_NBR": "434417302",
                "NAME": "7 MAGIC FLOWERS BILINGUAL MONTESSORI PRESCHOOL",
                "PROGRAM_TYPE": "CHILD CARE",
                "STATUS": "3",
                "CAPACITY": "48",
                "RES_CITY": "SAN JOSE",
                "RES_STATE": "CA",
                "RES_ZIP_CODE": "95112",
                "COUNTY": "Santa Clara",
                "FAC_TYPE_DESC": "DAY CARE CENTER",
            },
        ),
    )
    _write_program_summary_signals_csv(
        signals_csv,
        rows=(
            {
                "Facility Type": "DAY CARE CENTER",
                "Facility Number": "434417302",
                "Facility Name": "7 MAGIC FLOWERS BILINGUAL MONTESSORI PRESCHOOL",
                "Licensee": "Do Not Display Licensee",
                "Facility Administrator": "Do Not Display Admin",
                "Facility Telephone Number": "555-0199",
                "Facility Address": "1 Private Fixture Way",
                "Facility City": "SAN JOSE",
                "Facility State": "CA",
                "Facility Zip": "95112",
                "County Name": "Santa Clara",
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
                "Inspect TypeA": "",
                "Inspect TypeB": "",
                "Other TypeA": "A citation",
                "Other TypeB": "B citation, another B citation",
            },
        ),
    )
    monkeypatch.setenv(CCLD_FACILITY_REFERENCE_CSV_ENV, str(facility_csv))
    monkeypatch.setenv(FACILITY_REVIEW_SIGNALS_CSVS_ENV, str(signals_csv))

    status, content_type, body = route_response(
        f"{CCLD_FACILITY_REVIEW_HUB_PATH}?facility_number=434417302",
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Facility review signals" in html
    assert "uploaded public summary fields" in html
    assert "public licensing/visit/citation summary" in html
    assert "complaint records are requested/reviewed separately" in normalized_html
    assert "not a legal finding" in html
    assert "not source verification" in html
    assert "not a complaint-coverage determination" in html
    assert "not a source-completeness proof" in html
    assert "check source traceability before relying on summary fields" in normalized_html
    assert "24HourResidentialCareforChildren06072026.csv" in html
    assert "DAY CARE CENTER" in html
    assert "LICENSED" in html
    assert "48" in html
    assert "Santa Clara" in html
    assert "Central Valley" in html
    assert "2018-07-30" in html
    assert "2026-05-04" in html
    assert "43 total; 0 inspection; 12 complaint; 31 other" in html
    assert "2 citation value(s); 1 Type A value(s); 2 Type B value(s)" in html
    assert "POC date indicators in uploaded summary" in html
    assert "Complaint visit activity present review cue" in html
    assert "Citation indicator present review cue" in html
    assert "POC indicator present review cue" in html
    assert "Recent visit activity review cue" in html
    assert "verified complaint" not in normalized_html.casefold()
    assert "facility has no complaints" not in normalized_html.casefold()
    assert "source complete." not in normalized_html.casefold()
    assert "official finding." not in normalized_html.casefold()
    assert "licensed and valid" not in normalized_html.casefold()
    assert "Do Not Display" not in html
    assert "555-0199" not in html
    assert "1 Private Fixture Way" not in html
    assert_no_secret_html(html)


def test_ccld_facility_review_priority_page_empty_state_is_safe() -> None:
    status, content_type, body = route_response(
        CCLD_FACILITY_REVIEW_PRIORITY_PATH,
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Facility review priority" in html
    assert "uploaded public summary fields" in html
    assert "review cue" in html
    _assert_primary_button(html, "Apply review cue filter")
    _assert_collapsed_disclosure(
        html,
        "About these review cues and their limitations",
    )
    assert html.index("Apply review cue filter") < html.index(
        "About these review cues and their limitations"
    )
    assert html.index("No facility review priority rows are available") < html.index(
        "About these review cues and their limitations"
    )
    assert "No facility review priority rows are available" in html
    assert "complaint records are requested/reviewed separately" in normalized_html
    assert "not a legal finding" in html
    assert "not source verification" in html
    assert "not a complaint-coverage determination" in html
    assert "not a source-completeness proof" in html
    assert "missing signal is not complaint absence" in html
    # Empty state must link back to facility lookup (clear next action)
    assert "Return to facility lookup" in normalized_html
    assert CCLD_FACILITY_LOOKUP_PATH in html
    # Empty state must note it is optional
    assert "optional feature" in normalized_html
    assert_no_secret_html(html)


def test_ccld_facility_lookup_page_review_priority_link_is_collapsed_not_primary() -> None:
    """Review-priority link must be inside a <details> element, not a primary button."""
    status, _content_type, body = route_response(
        CCLD_FACILITY_LOOKUP_PATH,
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())

    assert status == 200
    assert "Optional: review-priority and intelligence" in html
    assert "These views require uploaded public summary CSVs" in normalized_html
    assert "not required for complaint retrieval and review" in normalized_html
    assert_no_secret_html(html)


def test_ccld_facility_review_priority_page_orders_filters_and_links_to_hubs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    signals_csv = tmp_path / "ChildCareCenters06072026.csv"
    _write_program_summary_signals_csv(
        signals_csv,
        rows=(
            _program_summary_signal_row(
                facility_number="900000001",
                facility_name="Single Cue Facility",
                last_visit_date="5/4/2026",
                inspection_visits="1",
                total_visits="1",
            ),
            _program_summary_signal_row(
                facility_number="900000002",
                facility_name="Multi Cue Facility",
                capacity="75",
                last_visit_date="6/1/2026",
                complaint_visits="2",
                total_visits="3",
                citation_numbers="101, 102",
                poc_dates="06/02/2026",
            ),
            _program_summary_signal_row(
                facility_number="900000003",
                facility_name="Long Gap Facility",
                last_visit_date="1/5/2020",
                total_visits="1",
            ),
            _program_summary_signal_row(
                facility_number="900000004",
                facility_name="Secret Garden Fixture",
                complaint_visits="1",
                total_visits="1",
            ),
        ),
    )
    monkeypatch.setenv(FACILITY_REVIEW_SIGNALS_CSVS_ENV, str(signals_csv))

    status, content_type, body = route_response(
        CCLD_FACILITY_REVIEW_PRIORITY_PATH,
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Multiple signal types present review cue" in html
    assert "Complaint visit activity present review cue" in html
    assert "Citation indicator present review cue" in html
    assert "POC indicator present review cue" in html
    assert "High-capacity facility review cue" in html
    assert "Recent visit activity review cue" in html
    assert "Long gap since last visit review cue" in html
    assert html.index("Multi Cue Facility") < html.index("Single Cue Facility")
    assert html.index("Single Cue Facility") < html.index("Long Gap Facility")
    assert f"{CCLD_FACILITY_REVIEW_HUB_PATH}?facility_number=900000002" in html
    assert "Open facility review hub for 900000002" in html
    _assert_collapsed_disclosure(
        html,
        "About these review cues and their limitations",
    )
    assert html.index("Apply review cue filter") < html.index(
        "About these review cues and their limitations"
    )
    assert html.index("Facilities grouped by review cue priority") < html.index(
        "About these review cues and their limitations"
    )
    assert "review label hidden" in html
    assert "Secret Garden Fixture" not in html
    assert "3 total visits; 2 complaint visits" in html
    assert "2 citation value(s); 1 POC date(s)" in html
    assert "not a legal finding" in html
    assert "not source verification" in html
    assert "not a complaint-coverage determination" in html
    assert "not a source-completeness proof" in html
    assert "verified complaint" not in normalized_html.casefold()
    assert "risk score" not in normalized_html.casefold()
    assert "facility has no complaints" not in normalized_html.casefold()
    assert "official finding." not in normalized_html.casefold()
    assert_no_secret_html(html)

    filtered_status, _filtered_content_type, filtered_body = route_response(
        f"{CCLD_FACILITY_REVIEW_PRIORITY_PATH}?cue=Complaint+visit+activity+present",
        page_data_mode="fixture-demo",
    )
    filtered_html = filtered_body.decode("utf-8")

    assert filtered_status == 200
    assert "Multi Cue Facility" in filtered_html
    assert "Single Cue Facility" not in filtered_html
    assert "Long Gap Facility" not in filtered_html

    # cue=all must show the same result set as the unfiltered default, not 0 rows.
    all_cue_status, _all_cue_content_type, all_cue_body = route_response(
        f"{CCLD_FACILITY_REVIEW_PRIORITY_PATH}?cue=all",
        page_data_mode="fixture-demo",
    )
    all_cue_html = all_cue_body.decode("utf-8")

    assert all_cue_status == 200
    assert "No facility review priority rows are available" not in all_cue_html
    assert "Multi Cue Facility" in all_cue_html
    assert "Single Cue Facility" in all_cue_html
    assert "Long Gap Facility" in all_cue_html
    # "all" is a sentinel value, not a real cue; no row should show "all" as its cue label.
    assert ">all review cue<" not in all_cue_html.casefold()


def test_ccld_facility_review_priority_page_does_not_mutate_hosted_tables(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    signals_csv = tmp_path / "FosterFamilyAgencies06072026.csv"
    _write_program_summary_signals_csv(
        signals_csv,
        rows=(
            _program_summary_signal_row(
                facility_number="157806098",
                facility_name="A. MIRIAM JAMISON CHILDREN'S CENTER",
                complaint_visits="1",
                total_visits="1",
            ),
        ),
    )
    monkeypatch.setenv(FACILITY_REVIEW_SIGNALS_CSVS_ENV, str(signals_csv))

    with _seeded_connection() as connection:
        before_source_rows = _source_rows(connection)
        before_counts = _table_counts(connection)
        status, content_type, body = route_response(
            CCLD_FACILITY_REVIEW_PRIORITY_PATH,
            page_data_mode="fixture-demo",
            ccld_record_request_ui_context=ccld_record_request_context_for_reviewer_context(
                reviewer_ui_context_for_connection(
                    connection,
                    actor=_actor(roles=("tester_reviewer",)),
                )
            ),
        )
        after_source_rows = _source_rows(connection)
        after_counts = _table_counts(connection)

    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert before_source_rows == after_source_rows
    assert before_counts == after_counts == _empty_reviewer_counts()
    assert "Facility review priority" in html
    assert "A. MIRIAM JAMISON CHILDREN&#x27;S CENTER" in html
    assert_no_secret_html(html)


def test_ccld_facility_review_intelligence_dashboard_filters_sorts_and_links(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    signals_csv = tmp_path / "ChildCareCenters06072026.csv"
    _write_program_summary_signals_csv(
        signals_csv,
        rows=(
            _program_summary_signal_row(
                facility_number="900000001",
                facility_name="Complaint Citation Facility",
                county="ALAMEDA",
                capacity="24",
                status="LICENSED",
                last_visit_date="5/4/2026",
                complaint_visits="4",
                total_visits="6",
                citation_numbers="101, 102",
                poc_dates="06/02/2026",
            ),
            _program_summary_signal_row(
                facility_number="900000002",
                facility_name="High Capacity Facility",
                county="SACRAMENTO",
                capacity="80",
                status="CLOSED",
                closed_date="1/2/2025",
                last_visit_date="1/5/2020",
                total_visits="1",
            ),
            _program_summary_signal_row(
                facility_number="900000003",
                facility_name="Recent Visit Facility",
                county="ALAMEDA",
                capacity="30",
                status="LICENSED",
                last_visit_date="6/1/2026",
                inspection_visits="1",
                total_visits="1",
            ),
        ),
    )
    monkeypatch.setenv(FACILITY_REVIEW_SIGNALS_CSVS_ENV, str(signals_csv))

    status, content_type, body = route_response(
        f"{CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH}?sort=complaint_activity",
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")
    normalized_html = " ".join(html.split()).casefold()

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Facility Review Intelligence Dashboard" in html
    assert "Where should reviewers spend time first?" in html
    _assert_primary_button(html, "Apply intelligence filters")
    _assert_collapsed_disclosure(
        html,
        "About these indicators and their limitations",
    )
    assert html.index("Apply intelligence filters") < html.index(
        "About these indicators and their limitations"
    )
    assert html.index("Facilities by review-priority indicator") < html.index(
        "About these indicators and their limitations"
    )
    assert "transparent review-priority indicators" in normalized_html
    assert "Facilities with complaint activity" in html
    assert "Facilities with citation activity" in html
    assert "Facilities with POC activity" in html
    assert "Facilities with recent visit activity" in html
    assert "Facilities with long periods since last visit" in html
    assert "High-capacity facilities" in html
    assert "Closed facilities" in html
    assert "Complaint visit activity present review cue" in html
    assert "Citation indicator present review cue" in html
    assert "POC indicator present review cue" in html
    assert "Recent visit activity review cue" in html
    assert "Long gap since last visit review cue" in html
    assert "High-capacity facility review cue" in html
    assert "Closed status in uploaded summary review cue" in html
    assert html.index("Complaint Citation Facility") < html.index("Recent Visit Facility")
    assert "Open Facility Review Hub for 900000001" in html
    assert f"{CCLD_FACILITY_REVIEW_HUB_PATH}?facility_number=900000001" in html
    assert "Start Complaint Request for 900000001" in html
    assert f"{CCLD_RECORD_REQUEST_PATH}?facility_number=900000001" in html
    assert "Open Review Queue filtered to 900000001" in html
    assert "not risk scores" in normalized_html
    assert "not wrongdoing determinations" in normalized_html
    assert "not source verification" in normalized_html
    assert "not a complaint-coverage determination" in normalized_html
    assert "not a source-completeness proof" in normalized_html
    assert "not a legal finding" in normalized_html
    assert "verified complaint" not in normalized_html
    assert "risk score:" not in normalized_html
    assert "wrongdoing determination:" not in normalized_html
    assert "facility has no complaints" not in normalized_html
    assert_no_secret_html(html)

    filtered_status, _filtered_content_type, filtered_body = route_response(
        f"{CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH}?cue=High-capacity+facility&county=SACRAMENTO&status=CLOSED&sort=capacity",
        page_data_mode="fixture-demo",
    )
    filtered_html = filtered_body.decode("utf-8")

    assert filtered_status == 200
    assert "High Capacity Facility" in filtered_html
    assert "Complaint Citation Facility" not in filtered_html
    assert "Recent Visit Facility" not in filtered_html


def test_ccld_facility_review_intelligence_dashboard_does_not_mutate_hosted_tables(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    signals_csv = tmp_path / "FosterFamilyAgencies06072026.csv"
    _write_program_summary_signals_csv(
        signals_csv,
        rows=(
            _program_summary_signal_row(
                facility_number="157806098",
                facility_name="A. MIRIAM JAMISON CHILDREN'S CENTER",
                complaint_visits="1",
                total_visits="1",
            ),
        ),
    )
    monkeypatch.setenv(FACILITY_REVIEW_SIGNALS_CSVS_ENV, str(signals_csv))

    with _seeded_connection() as connection:
        before_source_rows = _source_rows(connection)
        before_counts = _table_counts(connection)
        status, content_type, body = route_response(
            CCLD_FACILITY_REVIEW_INTELLIGENCE_PATH,
            page_data_mode="fixture-demo",
            ccld_record_request_ui_context=ccld_record_request_context_for_reviewer_context(
                reviewer_ui_context_for_connection(
                    connection,
                    actor=_actor(roles=("tester_reviewer",)),
                )
            ),
        )
        after_source_rows = _source_rows(connection)
        after_counts = _table_counts(connection)

    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert before_source_rows == after_source_rows
    assert before_counts == after_counts == _empty_reviewer_counts()
    assert "Facility Review Intelligence Dashboard" in html
    assert "A. MIRIAM JAMISON CHILDREN&#x27;S CENTER" in html
    assert_no_secret_html(html)


def test_ccld_facility_lookup_page_shows_no_match_guidance() -> None:
    status, content_type, body = route_response(
        f"{CCLD_FACILITY_LOOKUP_PATH}?q=no-match",
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "No facility-directory results matched" in html
    assert "Try a shorter name, license number, city, county, ZIP" in (
        normalized_html
    )
    assert "facility type, or program type" in normalized_html
    assert "Open request form" in html
    assert_no_secret_html(html)


def test_ccld_facility_lookup_selection_prefills_request_form_without_mutation() -> None:
    with _seeded_connection() as connection:
        before_source_rows = _source_rows(connection)
        status, content_type, body = route_response(
            f"{CCLD_RECORD_REQUEST_PATH}?facility_number=900000001",
            ccld_record_request_ui_context=ccld_record_request_context_for_reviewer_context(
                reviewer_ui_context_for_connection(
                    connection,
                    actor=_actor(roles=("tester_reviewer",)),
                )
            ),
        )
        after_source_rows = _source_rows(connection)
        counts = _table_counts(connection)

    html = body.decode("utf-8")

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert before_source_rows == after_source_rows
    assert counts == _empty_reviewer_counts()
    assert "Selected request context" in html or "No facility selected yet" not in html
    assert "Prefilled facility/license link" in html
    assert "Facility/license number being requested" in html
    assert "value=\"900000001\"" in html
    assert "Choose complaint date range" in html
    assert "Complaint records" in html
    assert "Active facility reference source" in html
    assert "Retrieve complaint records" in html
    assert "Change facility" in html
    assert_no_secret_html(html)


def test_ccld_facility_lookup_does_not_mutate_hosted_tables() -> None:
    with _seeded_connection() as connection:
        before_source_rows = _source_rows(connection)
        before_counts = _table_counts(connection)

        status, _content_type, body = route_response(
            f"{CCLD_FACILITY_LOOKUP_PATH}?q=valley",
            page_data_mode="fixture-demo",
        )

        after_source_rows = _source_rows(connection)
        after_counts = _table_counts(connection)

    html = body.decode("utf-8")

    assert status == 200
    assert before_source_rows == after_source_rows
    assert before_counts == after_counts == _empty_reviewer_counts()
    assert "Synthetic Valley Family Agency" in html
    assert_no_secret_html(html)


def test_ccld_facility_lookup_page_has_accessible_combobox_label() -> None:
    """Facility selector input must have an accessible name (label with matching for= attribute)."""
    status, content_type, body = route_response(
        CCLD_FACILITY_LOOKUP_PATH,
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")

    assert status == 200
    assert 'for="facility-search-input"' in html
    assert 'id="facility-search-input"' in html
    assert_no_secret_html(html)


def test_ccld_facility_lookup_page_has_concise_placeholder_not_full_helper_sentence() -> None:
    """Placeholder must be short; helper text in a separate element, not the placeholder."""
    status, content_type, body = route_response(
        CCLD_FACILITY_LOOKUP_PATH,
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())

    assert status == 200
    # Concise placeholder (not the full helper sentence)
    assert 'placeholder="Name, license number, city, or ZIP"' in html
    # Full helper text must appear separately (not inside the placeholder)
    assert "Search by name, license number, city, county, ZIP" in normalized_html
    assert "facility type, program type, or status code" in normalized_html
    assert_no_secret_html(html)


def test_ccld_facility_lookup_page_combobox_embeds_reference_json() -> None:
    """Facility selector must embed facility reference data as JSON for JS combobox."""
    status, content_type, body = route_response(
        CCLD_FACILITY_LOOKUP_PATH,
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")

    assert status == 200
    assert 'id="facility-reference-json"' in html
    assert '"900000001"' in html  # facility number in JSON
    assert '"Synthetic Orchard Child Care"' in html  # facility name in JSON
    assert_no_secret_html(html)


def test_ccld_facility_lookup_page_reference_details_are_collapsed() -> None:
    """Reference source technical details must appear in a collapsed <details> element."""
    status, content_type, body = route_response(
        CCLD_FACILITY_LOOKUP_PATH,
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")

    assert status == 200
    assert "Reference data details" in html
    assert "<details" in html
    # Internal labels must NOT appear prominently (may appear inside collapsed details)
    assert "Facility reference source</h2>" not in html  # old prominent section heading gone
    assert_no_secret_html(html)


def test_ccld_facility_lookup_page_limited_reference_note_shows_for_tiny_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When only the tiny fallback is active, a concise limited-reference note must appear."""
    monkeypatch.delenv(CCLD_FACILITY_REFERENCE_CSV_ENV, raising=False)

    status, content_type, body = route_response(
        CCLD_FACILITY_LOOKUP_PATH,
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")

    assert status == 200
    assert "Limited reference list" in html
    assert "suggestions may not include every CCLD facility" in html
    assert_no_secret_html(html)


def test_ccld_facility_lookup_page_no_internal_paths_in_primary_ui() -> None:
    """Internal file paths must not appear in the primary UI (only inside collapsed details)."""
    status, content_type, body = route_response(
        CCLD_FACILITY_LOOKUP_PATH,
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")

    assert status == 200
    # Internal paths must not be in primary headings/paragraphs outside <details>
    # The reference details section is collapsed; internal path label only appears there
    assert "Tiny committed CCLD facility fixture fallback" not in html
    assert "Full local/test CCLD facility reference CSV" not in html
    assert_no_secret_html(html)


def test_ccld_facility_lookup_result_card_review_action_has_descriptive_label() -> None:
    """Each result card's use button has a descriptive accessible label."""
    status, content_type, body = route_response(
        f"{CCLD_FACILITY_LOOKUP_PATH}?q=orchard",
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")

    assert status == 200
    assert (
        'aria-label="Start complaint request for facility 900000001 (Synthetic Orchard Child Care)"'
        in html
    )
    assert_no_secret_html(html)


def test_live_mode_facility_lookup_page_no_reference_shows_not_configured_messaging() -> None:
    """In live mode with no_reference, the page must clearly state lookup is not configured."""
    html = render_ccld_facility_lookup_page(reference_source=no_reference_facility_source())

    assert "Facility directory lookup is not configured" in html
    assert "Enter a known CCLD facility/license number" in html
    assert "Directory lookup is optional" in html
    assert "does not affect controlled complaint retrieval" in html
    # Manual entry is the primary path
    assert "Enter a facility/license number directly" in html
    assert "Open request form" in html
    assert f'href="{CCLD_RECORD_REQUEST_PATH}"' in html
    # No synthetic fixture facility names
    assert "Synthetic Orchard" not in html
    assert "Synthetic Valley" not in html
    assert "900000001" not in html
    assert "900000002" not in html
    # No JS combobox with empty data (no facility-reference-json element)
    assert "facility-reference-json" not in html
    assert_no_secret_html(html)


def test_live_mode_facility_lookup_page_empty_postgres_source_shows_not_configured_messaging(
) -> None:
    """Empty postgres_source_derived must also show not-configured messaging, not tiny fixture."""
    empty_postgres_source = CcldFacilityReferenceSource(
        source_kind="postgres_source_derived",
        label="PostgreSQL source-derived facility records",
        path_label="hosted_source_derived_records",
        records=(),
        warnings=(
            "Facility lookup suggestions are not available. "
            "Source-derived records may not include facility directory rows. "
            "Enter a facility/license number directly if you know it.",
        ),
    )
    html = render_ccld_facility_lookup_page(reference_source=empty_postgres_source)

    assert "Facility directory lookup is not configured" in html
    assert "Enter a known CCLD facility/license number" in html
    # Manual entry is the primary path
    assert "Enter a facility/license number directly" in html
    assert "Open request form" in html
    # No synthetic fixture facility names
    assert "Synthetic Orchard" not in html
    assert "Synthetic Valley" not in html
    assert "900000001" not in html
    # No JS combobox with empty data
    assert "facility-reference-json" not in html
    assert_no_secret_html(html)


def test_live_mode_facility_lookup_page_does_not_imply_directory_lookup_is_working() -> None:
    """In live mode with no_reference, page must not present lookup as a working primary path."""
    html = render_ccld_facility_lookup_page(reference_source=no_reference_facility_source())

    # Must NOT say directory is the primary/working path
    assert "preloaded facility directory" not in html
    # Must NOT prompt users to start by searching the directory
    assert "Start review by finding the CCLD facility/license number in the preloaded" not in html
    assert_no_secret_html(html)


def test_fixture_demo_mode_facility_lookup_page_still_shows_tiny_fixture_suggestions() -> None:
    """fixture-demo mode must continue to use the tiny fixture reference."""
    status, content_type, body = route_response(
        f"{CCLD_FACILITY_LOOKUP_PATH}?q=orchard",
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")

    assert status == 200
    # fixture-demo mode: tiny fixture suggestions still shown
    assert "Synthetic Orchard Child Care" in html
    assert "900000001" in html
    # facility-reference-json is present in fixture-demo mode (has real fixture data)
    assert "facility-reference-json" in html
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


def _matching_facility_numbers(
    query: str,
    records: tuple[CcldFacilityLookupRecord, ...],
) -> list[str]:
    return [
        record.facility_number
        for record in search_ccld_facilities(query, records).returned_records
    ]


def _write_facility_reference_csv(
    path: Path,
    *,
    rows: tuple[dict[str, str], ...],
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
    )
    with path.open("w", encoding="utf-8", newline="") as fixture_file:
        fixture_file.write(",".join(fieldnames) + "\n")
        for row in rows:
            fixture_file.write(
                ",".join(row.get(fieldname, "") for fieldname in fieldnames) + "\n"
            )


def _write_chhs_facility_directory_csv(
    path: Path,
    *,
    rows: tuple[dict[str, str], ...],
) -> None:
    fieldnames = (
        "FAC_LATITUDE",
        "FAC_LONGITUDE",
        "FAC_NBR",
        "TYPE",
        "PROGRAM_TYPE",
        "STATUS",
        "CLIENT_SERVED",
        "CAPACITY",
        "NAME",
        "RES_STREET_ADDR",
        "RES_CITY",
        "RES_STATE",
        "RES_ZIP_CODE",
        "FAC_PHONE_NBR",
        "FAC_CO_NBR",
        "COUNTY",
        "FAC_DO_DESC",
        "FAC_TYPE_DESC",
        "ObjectId",
        "x",
        "y",
    )
    with path.open("w", encoding="utf-8", newline="") as fixture_file:
        fixture_file.write(",".join(fieldnames) + "\n")
        for row in rows:
            fixture_file.write(
                ",".join(row.get(fieldname, "") for fieldname in fieldnames) + "\n"
            )


def _write_program_summary_signals_csv(
    path: Path,
    *,
    rows: tuple[dict[str, str], ...],
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
    with path.open("w", encoding="utf-8", newline="") as fixture_file:
        fixture_file.write(",".join(f'"{fieldname}"' for fieldname in fieldnames) + "\n")
        for row in rows:
            fixture_file.write(
                ",".join(f'"{row.get(fieldname, "")}"' for fieldname in fieldnames)
                + "\n"
            )


def _program_summary_signal_row(
    *,
    facility_number: str,
    facility_name: str,
    facility_type: str = "CHILD CARE CENTER",
    status: str = "LICENSED",
    capacity: str = "24",
    county: str = "Los Angeles",
    regional_office: str = "Regional Office",
    license_first_date: str = "",
    closed_date: str = "",
    last_visit_date: str = "",
    inspection_visits: str = "0",
    complaint_visits: str = "0",
    other_visits: str = "0",
    total_visits: str = "0",
    citation_numbers: str = "",
    poc_dates: str = "",
) -> dict[str, str]:
    return {
        "Facility Type": facility_type,
        "Facility Number": facility_number,
        "Facility Name": facility_name,
        "Licensee": "Do Not Display Licensee",
        "Facility Administrator": "Do Not Display Admin",
        "Facility Telephone Number": "555-0199",
        "Facility Address": "1 Private Fixture Way",
        "Facility City": "Sample City",
        "Facility State": "CA",
        "Facility Zip": "90001",
        "County Name": county,
        "Regional Office": regional_office,
        "Facility Capacity": capacity,
        "Facility Status": status,
        "License First Date": license_first_date,
        "Closed Date": closed_date,
        "Last Visit Date": last_visit_date,
        "Inspection Visits": inspection_visits,
        "Complaint Visits": complaint_visits,
        "Other Visits": other_visits,
        "Total Visits": total_visits,
        "Citation Numbers": citation_numbers,
        "POC Dates": poc_dates,
        "All Visit Dates": "",
        "Inspection Visit Dates": "",
        "Inspect TypeA": "",
        "Inspect TypeB": "",
        "Other Visit Dates": "",
        "Other TypeA": "",
        "Other TypeB": "",
        "Complaint Info- Date, #Sub Aleg, # Inc Aleg, # Uns Aleg, # TypeA, # TypeB ...": "",
    }


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
    provider_subject: str = "fixture-ccld-facility-lookup-reviewer",
    display_name: str = "Fixture CCLD Facility Lookup Reviewer",
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


def _empty_reviewer_counts() -> dict[str, int]:
    return {
        "import_batches": 1,
        "source_records": 6,
        "reviewer_created_state": 0,
        "audit_events": 0,
        "reset_reload_planning_metadata": 0,
    }
