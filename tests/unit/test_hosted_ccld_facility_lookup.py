from __future__ import annotations

from pathlib import Path
from typing import Any, cast

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
)
from ccld_complaints.hosted_app.ccld_facility_lookup import (
    CCLD_FACILITY_LOOKUP_PATH,
    CCLD_RECORD_REQUEST_PATH,
    CcldFacilityLookupRecord,
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
    status, content_type, body = route_response(CCLD_FACILITY_LOOKUP_PATH)
    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Find CCLD facility" in html
    assert "CCLD-only local/test facility lookup" in html
    assert "Search local/test facility reference" in html
    assert "Facility search" in html
    assert "Enter a facility name, facility/license number, city, county, ZIP code" in (
        normalized_html
    )
    assert "Manual facility/license entry" in html
    assert "Open manual CCLD request form" in html
    assert "live CCLD retrieval" in html
    assert_no_secret_html(html)


def test_ccld_facility_lookup_page_renders_results_and_use_link() -> None:
    status, content_type, body = route_response(f"{CCLD_FACILITY_LOOKUP_PATH}?q=orchard")
    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())
    request_href = f"{CCLD_RECORD_REQUEST_PATH}?facility_number=900000001"

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Local/test CCLD facility reference matches" in html
    assert "Showing 1 of 1 matching local/test facility reference row" in normalized_html
    assert "Use this facility for CCLD request" in html
    assert request_href in html
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
    status, content_type, body = route_response(f"{CCLD_FACILITY_LOOKUP_PATH}?q=no-match")
    html = body.decode("utf-8")
    normalized_html = " ".join(html.split())

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "No local/test CCLD facility reference rows matched no-match." in html
    assert "Try a shorter name, facility/license number, city, county, ZIP code" in (
        normalized_html
    )
    assert "Open manual CCLD request form" in html
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
    assert "Selected facility/license number from lookup" in html
    assert "value=\"900000001\"" in html
    assert "Request CCLD records" in html
    assert "Find a CCLD facility" in html
    assert_no_secret_html(html)


def test_ccld_facility_lookup_does_not_mutate_hosted_tables() -> None:
    with _seeded_connection() as connection:
        before_source_rows = _source_rows(connection)
        before_counts = _table_counts(connection)

        status, _content_type, body = route_response(f"{CCLD_FACILITY_LOOKUP_PATH}?q=valley")

        after_source_rows = _source_rows(connection)
        after_counts = _table_counts(connection)

    html = body.decode("utf-8")

    assert status == 200
    assert before_source_rows == after_source_rows
    assert before_counts == after_counts == _empty_reviewer_counts()
    assert "Synthetic Valley Family Agency" in html
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
