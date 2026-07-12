from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Connection

from ccld_complaints.hosted_app import reviewer_ui
from ccld_complaints.hosted_app.app import route_response
from ccld_complaints.hosted_app.auth import (
    AuthenticatedActor,
    HostedAccessScope,
    HostedAccountStatus,
    HostedActorCategory,
    HostedTesterRole,
    load_hosted_auth_runtime_config,
)
from ccld_complaints.hosted_app.ccld_retrieval_jobs import hosted_ccld_retrieval_jobs
from ccld_complaints.hosted_app.reviewer_ui import (
    LOCAL_REVIEWER_UI_SCOPE,
    REVIEWER_UI_FACILITY_PRIORITIES_PATH,
    reviewer_ui_context_for_connection,
)
from ccld_complaints.hosted_app.seeded_import import (
    hosted_import_batches,
    hosted_seeded_import_metadata,
    hosted_source_derived_records,
)

TEST_SCOPE = LOCAL_REVIEWER_UI_SCOPE
OTHER_SCOPE = HostedAccessScope("seeded_corpus", "outside-loaded-corpus")


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
            REVIEWER_UI_FACILITY_PRIORITIES_PATH,
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    html = body.decode("utf-8")
    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Facility review priorities" in html
    assert "hidden score" in html
    assert "machine learning" in html
    assert html.index("Alpha Center") < html.index("Gamma Center") < html.index("Beta Center")
    assert "2 deduplicated loaded complaint record(s)." in html
    assert "1 source-derived substantiated/equivalent finding(s)." in html
    assert "strongest available flag is 120+ days" in html
    assert "1 complaint record(s) missing an original public report link." in html
    assert "Open qualifying complaint queue" in html
    assert "/ccld/records/request?facility_number=100001" in html
    assert "Open next complaint review workspace" in html
    assert "/reviewer/records/detail?source_record_key=complaint%3Accld%3Acomplaint%3AA-1" in html
    assert "Open original public report for A-1" in html
    assert "raw_sha256" not in html
    assert "data/raw" not in html
    assert "legal priority" not in html.casefold()


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
                f"{REVIEWER_UI_FACILITY_PRIORITIES_PATH}"
                "?facility_type=children&geography=kern&start_date=2026-04-01"
                "&end_date=2026-05-31&min_complaints=2&min_substantiated=1"
                "&indicator=delay"
            ),
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    html = body.decode("utf-8")
    assert status == 200
    assert "Alpha Center" in html
    assert "Beta Center" not in html
    assert "Showing 1-1 of 1 matching facility priority row(s); 2 total" in html
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
            f"{REVIEWER_UI_FACILITY_PRIORITIES_PATH}?indicator=low_data&page_size=10",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )
        missing_status, _missing_type, missing_body = route_response(
            f"{REVIEWER_UI_FACILITY_PRIORITIES_PATH}?indicator=source_link_missing&page_size=100",
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )
        empty_status, _empty_type, empty_body = route_response(
            f"{REVIEWER_UI_FACILITY_PRIORITIES_PATH}?min_complaints=99",
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
    assert "Showing 1-10 of 12 matching facility priority row(s)" in html
    assert "Next page" in html
    assert "page_size=10" in html
    assert "No facility priority rows matched." in empty_html
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
            REVIEWER_UI_FACILITY_PRIORITIES_PATH,
            reviewer_ui_context=reviewer_ui_context_for_connection(
                connection,
                actor=None,
            ),
        )
        status, _content_type, body = route_response(
            REVIEWER_UI_FACILITY_PRIORITIES_PATH,
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
            REVIEWER_UI_FACILITY_PRIORITIES_PATH,
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

        after = _table_counts(connection)

    assert status == 200
    assert "Allowed Center" in body.decode("utf-8")
    assert after == before


def test_facility_priorities_production_mode_does_not_fall_back_to_fixture_data() -> None:
    auth_runtime_config = load_hosted_auth_runtime_config(environ={})

    status, _content_type, body = route_response(
        REVIEWER_UI_FACILITY_PRIORITIES_PATH,
        auth_runtime_config=auth_runtime_config,
        page_data_mode="postgres",
    )

    html = body.decode("utf-8")
    assert status in {401, 503}
    assert "A. MIRIAM JAMISON CHILDREN" not in html
    assert "Fixture/mock demo" not in html


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


def _priority_connection() -> Connection:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)
    connection = engine.connect()
    _insert_import_batch(connection, TEST_SCOPE.scope_id)
    return connection


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
) -> dict[str, Any]:
    return {
        "control": control,
        "date": date,
        "finding": finding,
        "delay_days": delay_days,
        "source_url": source_url,
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
