from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Connection

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
    CCLD_RECORD_REQUEST_PATH,
    CcldFacilityLookupRecord,
    load_active_ccld_facility_reference,
    load_ccld_facility_reference,
    search_ccld_facilities,
)
from ccld_complaints.hosted_app.ccld_record_request_ui import (
    ccld_record_request_context_for_reviewer_context,
)
from ccld_complaints.hosted_app.reset_reload_dry_run import (
    hosted_reset_reload_planning_metadata,
)
from ccld_complaints.hosted_app.reviewer_created_state import hosted_reviewer_created_state
from ccld_complaints.hosted_app.reviewer_ui import (
    LOCAL_REVIEWER_UI_SCOPE,
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
        county="Los Angeles",
        zip_code="90001",
        facility_type="Child Care Center",
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
    assert "Run Alembic migrations" in html
    assert "fixture-demo mode" in html
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
        "No full local/test CCLD facility reference CSV is configured or available. "
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
    assert source.label == "Full local/test CCLD facility reference CSV"
    assert source.path_label == full_csv.name
    assert source.warnings == ()
    assert [record.facility_number for record in result.returned_records] == ["910000001"]
    assert result.reference_source == source


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
    assert "Configured full local/test CCLD facility reference CSV was not found" in html
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
            county="Los Angeles",
            zip_code="90001",
            facility_type="Child Care Center",
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
    assert "Lookup or manual entry?" in html
    assert "Use facility lookup when you know a facility name" in html
    assert "Use manual entry when you already know the digit facility/license number" in html
    assert "Lookup rows are local/test reference assistance" in html
    assert "not complaint source truth" in html
    assert 'for="facility-search-input"' in html
    assert "facility-suggestion-list" in html
    assert "Search" in html
    assert "Search by name, license number, city, ZIP, type, or status." in (
        normalized_html
    )
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
    assert "Showing 1 of 1 matching facility." in normalized_html
    assert "Review this facility" in html
    assert "Find a facility" in html
    assert request_href in html
    assert "request_context_origin=facility_lookup" in html
    assert "lookup_facility_name=Synthetic+Orchard+Child+Care" in html
    assert "900000001" in html
    assert "Synthetic Orchard Child Care" in html
    assert "Sample City" in html
    assert "Los Angeles" in html
    assert "90001" in html
    assert "Child Care Center" in html
    assert "Licensed" in html
    assert "Example Licensee" not in html
    assert "555-0101" not in html
    assert "100 Example Way" not in html
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
    assert "No facilities matched" in html
    assert "Try a shorter name, license number, city, ZIP, or facility type." in (
        normalized_html
    )
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
    assert "Search by name, license number, city, ZIP, type, or status." in normalized_html
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
    """Each result card's 'Review this facility' button has a descriptive accessible label."""
    status, content_type, body = route_response(
        f"{CCLD_FACILITY_LOOKUP_PATH}?q=orchard",
        page_data_mode="fixture-demo",
    )
    html = body.decode("utf-8")

    assert status == 200
    assert 'aria-label="Review Synthetic Orchard Child Care facility complaint records"' in html
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
