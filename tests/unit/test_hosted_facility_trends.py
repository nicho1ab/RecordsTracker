from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Connection

from ccld_complaints.hosted_app import reviewer_ui
from ccld_complaints.hosted_app.app import route_response
from ccld_complaints.hosted_app.auth import HostedAccessScope
from ccld_complaints.hosted_app.facility_trends import (
    COMPLETE_PERIOD,
    COVERAGE_UNAVAILABLE,
    DATE_UNAVAILABLE,
    DECREASED_ACTIVITY,
    INCOMPLETE_CURRENT_PERIOD,
    INCREASED_ACTIVITY,
    NEW_ACTIVITY,
    NO_ANOMALY_CUE,
    ZERO_QUALIFYING_RECORDS,
    FacilityTrendComplaint,
    FacilityTrendFilters,
    build_facility_trend,
)
from ccld_complaints.hosted_app.reviewer_ui import (
    LOCAL_REVIEWER_UI_SCOPE,
    REVIEWER_UI_FACILITY_TRENDS_PATH,
    reviewer_ui_context_for_connection,
)
from ccld_complaints.hosted_app.seeded_import import (
    hosted_import_batches,
    hosted_seeded_import_metadata,
    hosted_source_derived_records,
)

TEST_SCOPE = LOCAL_REVIEWER_UI_SCOPE
OTHER_SCOPE = HostedAccessScope("seeded_corpus", "other-trend-corpus")


def test_monthly_quarterly_grouping_boundaries_and_reconciliation() -> None:
    complaints = [
        _trend_complaint("JAN-31", "2026-01-31", substantiated=True),
        _trend_complaint("FEB-01", "2026-02-01", serious=True),
        _trend_complaint("FEB-28", "2026-02-28"),
        _trend_complaint("MAR-01", "2026-03-01"),
        _trend_complaint("NO-DATE", None, substantiated=True),
    ]

    monthly = build_facility_trend(
        complaints,
        FacilityTrendFilters(
            start_date=date(2026, 1, 31),
            end_date=date(2026, 2, 28),
            period_count=2,
        ),
        today=date(2026, 7, 12),
    )
    quarterly = build_facility_trend(
        complaints,
        FacilityTrendFilters(
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            time_grain="quarter",
            period_count=1,
        ),
        today=date(2026, 7, 12),
    )
    bounded = build_facility_trend(
        complaints,
        FacilityTrendFilters(
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            period_count=2,
        ),
        today=date(2026, 7, 12),
    )

    assert [period.complaint_count for period in monthly.periods] == [1, 2]
    assert monthly.periods[0].period_start == date(2026, 1, 31)
    assert monthly.periods[1].period_end == date(2026, 2, 28)
    assert monthly.qualifying_complaint_count == 4
    assert monthly.dated_qualifying_complaint_count == 3
    assert len(monthly.date_unavailable_complaints) == 1
    assert quarterly.periods[0].complaint_count == 4
    assert quarterly.periods[0].substantiated_count == 1
    assert quarterly.periods[0].serious_topic_count == 1
    assert len(bounded.periods) == 2
    assert bounded.dated_qualifying_complaint_count == 3
    assert bounded.qualifying_complaint_count == 4


def test_anomaly_rules_use_only_adjacent_comparable_complete_periods() -> None:
    increased = build_facility_trend(
        [
            _trend_complaint("JAN-1", "2026-01-01"),
            *[_trend_complaint(f"FEB-{index}", f"2026-02-0{index}") for index in range(1, 4)],
        ],
        FacilityTrendFilters(
            start_date=date(2026, 1, 1),
            end_date=date(2026, 2, 28),
            period_count=2,
        ),
        today=date(2026, 7, 12),
    )
    new = build_facility_trend(
        [
            _trend_complaint("JAN-BASE", "2026-01-01", finding="Unsubstantiated"),
            *[
                _trend_complaint(
                    f"FEB-S-{index}",
                    f"2026-02-0{index}",
                    finding="Substantiated",
                    substantiated=True,
                )
                for index in range(1, 4)
            ],
        ],
        FacilityTrendFilters(
            start_date=date(2026, 1, 1),
            end_date=date(2026, 2, 28),
            finding="Substantiated",
            period_count=2,
        ),
        today=date(2026, 7, 12),
    )
    decreased = build_facility_trend(
        [
            *[_trend_complaint(f"JAN-{index}", f"2026-01-0{index}") for index in range(1, 5)],
            _trend_complaint("FEB-1", "2026-02-01"),
            _trend_complaint("FEB-2", "2026-02-02"),
        ],
        FacilityTrendFilters(
            start_date=date(2026, 1, 1),
            end_date=date(2026, 2, 28),
            period_count=2,
        ),
        today=date(2026, 7, 12),
    )
    incomplete = build_facility_trend(
        [_trend_complaint("CURRENT-1", "2026-07-01")],
        FacilityTrendFilters(
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 31),
            period_count=1,
        ),
        today=date(2026, 7, 12),
    )

    assert increased.periods[1].anomaly_cue == INCREASED_ACTIVITY
    assert increased.periods[1].preceding_complaint_count == 1
    assert new.periods[0].coverage_state == ZERO_QUALIFYING_RECORDS
    assert new.periods[1].anomaly_cue == NEW_ACTIVITY
    assert decreased.periods[1].anomaly_cue == DECREASED_ACTIVITY
    assert incomplete.periods[0].coverage_state == INCOMPLETE_CURRENT_PERIOD
    assert incomplete.periods[0].anomaly_cue == NO_ANOMALY_CUE


def test_coverage_states_distinguish_zero_unavailable_and_missing_date() -> None:
    result = build_facility_trend(
        [
            _trend_complaint("JAN", "2026-01-01", finding="Substantiated"),
            _trend_complaint("MAR", "2026-03-01", finding="Unsubstantiated"),
            _trend_complaint("NO-DATE", None, finding="Substantiated"),
        ],
        FacilityTrendFilters(
            start_date=date(2026, 1, 1),
            end_date=date(2026, 4, 30),
            finding="Substantiated",
            period_count=4,
        ),
        today=date(2026, 7, 12),
    )

    assert [period.coverage_state for period in result.periods] == [
        COMPLETE_PERIOD,
        ZERO_QUALIFYING_RECORDS,
        ZERO_QUALIFYING_RECORDS,
        COVERAGE_UNAVAILABLE,
    ]
    assert len(result.date_unavailable_complaints) == 1
    assert DATE_UNAVAILABLE == "Date unavailable"
    assert all(period.anomaly_cue != DECREASED_ACTIVITY for period in result.periods[1:])


def test_combined_filters_and_deterministic_complaint_ordering() -> None:
    complaints = [
        _trend_complaint(
            "B-2",
            "2026-01-20",
            facility_name="Beta Center",
            facility_number="200002",
            facility_type="Foster Family Agency",
            geography="Alameda",
            finding="Substantiated",
            substantiated=True,
            serious=True,
        ),
        _trend_complaint(
            "A-2",
            "2026-01-10",
            finding="Substantiated",
            substantiated=True,
            serious=True,
        ),
        _trend_complaint(
            "A-1",
            "2026-01-15",
            finding="Substantiated",
            substantiated=True,
            serious=True,
        ),
    ]
    result = build_facility_trend(
        complaints,
        FacilityTrendFilters(
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            facility="Alpha",
            facility_type="children",
            geography="kern",
            finding="substantiated",
            serious_topic="supervision",
            period_count=1,
        ),
        today=date(2026, 7, 12),
    )

    assert [item.stable_complaint_id for item in result.periods[0].complaints] == [
        "A-1",
        "A-2",
    ]
    assert result.periods[0].complaint_count == 2
    assert result.periods[0].substantiated_count == 2
    assert result.periods[0].serious_topic_count == 2


def test_facility_trends_route_is_accessible_linked_compact_and_deduplicated() -> None:
    with _trend_connection() as connection:
        _insert_facility_bundle(
            connection,
            facility_number="100001",
            facility_name="Alpha Center",
            facility_type="Children's Center",
            county="Kern",
            complaints=(
                _db_complaint("A-1", "2026-01-05", "Substantiated", serious=True),
                _db_complaint("A-2", "2026-02-05", "Unsubstantiated"),
                _db_complaint("A-NO-DATE", "", "Substantiated", serious=True),
            ),
        )
        status, content_type, body = route_response(
            (
                f"{REVIEWER_UI_FACILITY_TRENDS_PATH}?facility=Alpha"
                "&facility_type=children&geography=kern&finding=Substantiated"
                "&serious_topic=Supervision&start_date=2026-01-01"
                "&end_date=2026-03-31&time_grain=month&period_count=3"
            ),
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    html = body.decode("utf-8")
    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Review complaint trends over time" in html
    assert "01/01/2026–01/31/2026" in html
    assert "Complete period" in html
    assert "Zero qualifying records" in html
    assert "Date unavailable" in html
    assert "Anomaly cue and contributing counts" in html
    assert "Current period:" in html and "preceding period:" in html
    assert '<caption>' in html and '<th scope="col">' in html
    assert '<label for="facility-trends-facility">' in html
    assert 'name="time_grain"' in html and 'name="period_count"' in html
    assert "Open complaint record A-1" in html
    assert html.count("Open complaint record A-1") == 1
    assert "/reviewer/records/detail?source_record_key=" in html
    assert "raw_sha256" not in html
    assert "tests/fixtures" not in html
    assert "DO NOT SHOW" not in html
    assert "legal conclusion" not in html.casefold()
    assert "risk score" not in html.casefold()
    assert html.count("Compare deduplicated loaded complaint and finding activity") == 1


def test_facility_trends_authorization_batch_isolation_and_no_mutation() -> None:
    with _trend_connection() as connection:
        _insert_facility_bundle(
            connection,
            facility_number="100001",
            facility_name="Allowed Center",
            facility_type="Children's Center",
            county="Kern",
            complaints=(_db_complaint("A-1", "2026-01-05", "Substantiated"),),
        )
        _insert_import_batch(connection, OTHER_SCOPE.scope_id)
        _insert_facility_bundle(
            connection,
            import_batch_id=OTHER_SCOPE.scope_id,
            facility_number="999999",
            facility_name="Outside Scope Center",
            facility_type="Children's Center",
            county="Kern",
            complaints=(_db_complaint("O-1", "2026-01-05", "Substantiated"),),
        )
        before = _table_counts(connection)

        denied_status, _denied_type, denied_body = route_response(
            REVIEWER_UI_FACILITY_TRENDS_PATH,
            reviewer_ui_context=reviewer_ui_context_for_connection(
                connection,
                actor=None,
            ),
        )
        status, _content_type, body = route_response(
            (
                f"{REVIEWER_UI_FACILITY_TRENDS_PATH}?facility=Allowed"
                "&start_date=2026-01-01&end_date=2026-01-31&period_count=1"
            ),
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )
        after = _table_counts(connection)

    assert denied_status == 401
    assert "Complaint trends blocked" in denied_body.decode("utf-8")
    assert status == 200
    html = body.decode("utf-8")
    assert "Open complaint record A-1" in html
    assert "Outside Scope Center" not in html
    assert after == before


def test_facility_trends_rejects_reversed_date_range_accessibly() -> None:
    with _trend_connection() as connection:
        status, content_type, body = route_response(
            (
                f"{REVIEWER_UI_FACILITY_TRENDS_PATH}"
                "?start_date=2026-02-01&end_date=2026-01-01"
            ),
            reviewer_ui_context=reviewer_ui_context_for_connection(connection),
        )

    html = body.decode("utf-8")
    assert status == 400
    assert content_type == "text/html; charset=utf-8"
    assert "Complaint trend dates need attention" in html
    assert "Start date must be on or before end date." in html


def test_facility_trend_flat_record_helper_deduplicates_stable_identity() -> None:
    records = [
        _flat_record(
            "facility",
            "facility:ccld:facility:100001",
            "ccld:facility:100001",
            "facility-doc",
            "ccld:facility:100001",
            {
                "facility_id": "ccld:facility:100001",
                "external_facility_number": "100001",
                "facility_name": "Alpha Center",
                "facility_type": "Children's Center",
                "county": "Kern",
            },
        ),
        _flat_record(
            "complaint",
            "complaint:ccld:complaint:DUP-1",
            "ccld:complaint:DUP-1",
            "complaint-doc",
            "ccld:facility:100001",
            {
                "complaint_id": "ccld:complaint:DUP-1",
                "facility_id": "ccld:facility:100001",
                "complaint_control_number": "DUP-1",
                "complaint_received_date": "2026-01-05",
                "finding": "Substantiated",
            },
        ),
        _flat_record(
            "complaint",
            "complaint:ccld:complaint:DUP-1-copy",
            "ccld:complaint:DUP-1",
            "complaint-doc",
            "ccld:facility:100001",
            {
                "complaint_id": "ccld:complaint:DUP-1",
                "facility_id": "ccld:facility:100001",
                "complaint_control_number": "DUP-1",
                "complaint_received_date": "2026-01-05",
                "finding": "Substantiated",
            },
        ),
    ]

    complaints = reviewer_ui._facility_trend_complaints(records)

    assert len(complaints) == 1
    assert complaints[0].stable_complaint_id == "ccld:complaint:DUP-1"


def _trend_complaint(
    identity: str,
    complaint_date: str | None,
    *,
    facility_name: str = "Alpha Center",
    facility_number: str = "100001",
    facility_type: str = "Children's Center",
    geography: str = "Kern",
    finding: str = "Unsubstantiated",
    substantiated: bool = False,
    serious: bool = False,
) -> FacilityTrendComplaint:
    return FacilityTrendComplaint(
        stable_complaint_id=identity,
        source_record_key=f"complaint:{identity}",
        complaint_control_number=identity,
        facility_number=facility_number,
        facility_name=facility_name,
        facility_type=facility_type,
        geography=geography,
        complaint_date=date.fromisoformat(complaint_date) if complaint_date else None,
        finding=finding,
        substantiated=substantiated,
        serious_topics=("Supervision topic",) if serious else (),
        detail_href=f"/reviewer/records/detail?source_record_key=complaint:{identity}",
    )


def _trend_connection() -> Connection:
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
            source_pipeline_version="fixture-trends",
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
            **_record_values(
                import_batch_id,
                "facility",
                facility_id,
                f"facility-doc:{facility_number}",
                facility_id,
                {
                    "facility_id": facility_id,
                    "external_facility_number": facility_number,
                    "facility_name": facility_name,
                    "facility_type": facility_type,
                    "county": county,
                },
            )
        )
    )
    for index, complaint in enumerate(complaints, start=1):
        control = complaint["control"]
        document_id = f"complaint-doc:{facility_number}:{index}"
        complaint_id = f"ccld:complaint:{control}"
        connection.execute(
            hosted_source_derived_records.insert().values(
                **_record_values(
                    import_batch_id,
                    "source_document",
                    document_id,
                    document_id,
                    facility_id,
                    {"document_id": document_id, "facility_id": facility_id},
                )
            )
        )
        values = {
            "complaint_id": complaint_id,
            "facility_id": facility_id,
            "document_id": document_id,
            "complaint_control_number": control,
            "finding": complaint["finding"],
        }
        if complaint["date"]:
            values["complaint_received_date"] = complaint["date"]
        connection.execute(
            hosted_source_derived_records.insert().values(
                **_record_values(
                    import_batch_id,
                    "complaint",
                    complaint_id,
                    document_id,
                    facility_id,
                    values,
                    source_record_key=f"complaint:{complaint_id}",
                )
            )
        )
        if complaint["serious"]:
            allegation_id = f"ccld:allegation:{control}:1"
            connection.execute(
                hosted_source_derived_records.insert().values(
                    **_record_values(
                        import_batch_id,
                        "allegation",
                        allegation_id,
                        document_id,
                        facility_id,
                        {
                            "allegation_id": allegation_id,
                            "complaint_id": complaint_id,
                            "allegation_category": "Inadequate supervision",
                            "allegation_text": "DO NOT SHOW",
                        },
                    )
                )
            )


def _db_complaint(
    control: str,
    complaint_date: str,
    finding: str,
    *,
    serious: bool = False,
) -> dict[str, Any]:
    return {
        "control": control,
        "date": complaint_date,
        "finding": finding,
        "serious": serious,
    }


def _record_values(
    import_batch_id: str,
    entity_type: str,
    stable_source_id: str,
    source_document_id: str,
    facility_id: str,
    original_values: Mapping[str, Any],
    *,
    source_record_key: str | None = None,
) -> dict[str, Any]:
    source_url = "https://example.invalid/public-report"
    return {
        "source_record_key": source_record_key or f"{entity_type}:{stable_source_id}",
        "entity_type": entity_type,
        "stable_source_id": stable_source_id,
        "import_batch_id": import_batch_id,
        "source_document_id": source_document_id,
        "facility_id": facility_id,
        "source_url": source_url,
        "raw_sha256": "a" * 64,
        "raw_path": "tests/fixtures/private-path-must-not-render.html",
        "connector_name": "fixture-trends",
        "connector_version": "1",
        "retrieved_at": "2026-07-01T12:00:00+00:00",
        "original_values": dict(original_values),
        "source_traceability": {
            "source_document_id": source_document_id,
            "source_url": source_url,
            "raw_sha256": "a" * 64,
            "raw_path": "tests/fixtures/private-path-must-not-render.html",
            "connector_name": "fixture-trends",
            "connector_version": "1",
            "retrieved_at": "2026-07-01T12:00:00+00:00",
            "source_artifact_identity": f"fixture-artifact:{import_batch_id}",
        },
    }


def _flat_record(
    entity_type: str,
    source_record_key: str,
    stable_source_id: str,
    source_document_id: str,
    facility_id: str,
    original_values: Mapping[str, Any],
) -> Mapping[str, Any]:
    return {
        **_record_values(
            TEST_SCOPE.scope_id,
            entity_type,
            stable_source_id,
            source_document_id,
            facility_id,
            original_values,
            source_record_key=source_record_key,
        ),
        "import_batch": {"import_batch_id": TEST_SCOPE.scope_id},
    }


def _table_counts(connection: Connection) -> dict[str, int]:
    return {
        "import_batches": connection.execute(
            select(func.count()).select_from(hosted_import_batches)
        ).scalar_one(),
        "source_records": connection.execute(
            select(func.count()).select_from(hosted_source_derived_records)
        ).scalar_one(),
    }
