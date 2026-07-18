from __future__ import annotations

import os
import time
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Connection, Engine

from ccld_complaints.hosted_app.seeded_import import (
    hosted_import_batches,
    hosted_seeded_import_metadata,
    hosted_source_derived_records,
)
from ccld_complaints.hosted_app.source_derived_reads import (
    FacilityIntelligenceReadFilters,
    FacilityIntelligenceSeek,
    list_facility_intelligence_page,
)

POSTGRES_TEST_URL_ENV = "CCLD_TEST_POSTGRES_URL"
POSTGRES_SCHEMA_MUTATION_ENV = "CCLD_TEST_POSTGRES_ALLOW_SCHEMA_MUTATION"
PERFORMANCE_IMPORT_BATCH_ID = "issue-419-postgres-performance"
PERFORMANCE_FACILITY_COUNT = 3_000
COMPLAINTS_PER_FACILITY = 2
BOUNDARY_IMPORT_BATCH_ID = "issue-419-postgres-boundaries"
BOUNDARY_FACILITY_COUNT = 51
MAX_PAGE_SECONDS = 20.0
STATEMENT_TIMEOUT_MILLISECONDS = 20_000


@pytest.fixture(scope="module")
def postgres_performance_connection() -> Iterator[Connection]:
    database_url = os.environ.get(POSTGRES_TEST_URL_ENV, "").strip()
    mutation_allowed = os.environ.get(POSTGRES_SCHEMA_MUTATION_ENV, "").strip() == "1"
    if not database_url or not mutation_allowed:
        pytest.skip(
            f"Set {POSTGRES_TEST_URL_ENV} and {POSTGRES_SCHEMA_MUTATION_ENV}=1 "
            "to run the isolated PostgreSQL performance regression."
        )
    if not database_url.startswith("postgresql+"):
        pytest.fail(f"{POSTGRES_TEST_URL_ENV} must use a PostgreSQL SQLAlchemy URL.")

    schema_name = f"issue419_perf_{uuid.uuid4().hex}"
    engine = create_engine(database_url)
    with engine.connect() as connection:
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema_name}"')
        connection.exec_driver_sql(f'SET search_path TO "{schema_name}"')
        hosted_seeded_import_metadata.create_all(connection)
        _seed_performance_corpus(connection)
        _seed_corpus(
            connection,
            import_batch_id=BOUNDARY_IMPORT_BATCH_ID,
            facility_count=BOUNDARY_FACILITY_COUNT,
            complaints_per_facility=1,
            facility_number_prefix="8",
        )
        connection.commit()
        try:
            yield connection
        finally:
            connection.rollback()
            connection.exec_driver_sql('SET search_path TO public')
            connection.exec_driver_sql(f'DROP SCHEMA "{schema_name}" CASCADE')
            connection.commit()
    engine.dispose()


def test_postgres_facility_intelligence_page_is_bounded_and_completes(
    postgres_performance_connection: Connection,
) -> None:
    connection = postgres_performance_connection
    statement_timings: list[tuple[float, str]] = []

    def before_cursor_execute(
        _connection: Connection,
        _cursor: Any,
        _statement: str,
        _parameters: Any,
        context: Any,
        _executemany: bool,
    ) -> None:
        context._issue419_started_at = time.perf_counter()

    def after_cursor_execute(
        _connection: Connection,
        _cursor: Any,
        statement: str,
        _parameters: Any,
        context: Any,
        _executemany: bool,
    ) -> None:
        elapsed = time.perf_counter() - context._issue419_started_at
        statement_timings.append((elapsed, " ".join(statement.casefold().split())))

    engine = _connection_engine(connection)
    connection.exec_driver_sql(
        f"SET LOCAL statement_timeout = '{STATEMENT_TIMEOUT_MILLISECONDS}ms'"
    )
    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    event.listen(engine, "after_cursor_execute", after_cursor_execute)
    started_at = time.perf_counter()
    try:
        page = list_facility_intelligence_page(
            connection,
            filters=FacilityIntelligenceReadFilters(sort="facility_name"),
            import_batch_id=PERFORMANCE_IMPORT_BATCH_ID,
        )
    finally:
        elapsed = time.perf_counter() - started_at
        event.remove(engine, "before_cursor_execute", before_cursor_execute)
        event.remove(engine, "after_cursor_execute", after_cursor_execute)

    slowest = sorted(statement_timings, reverse=True)[:5]
    print(f"facility intelligence elapsed={elapsed:.3f}s statements={len(statement_timings)}")
    for duration, statement in slowest:
        print(f"statement elapsed={duration:.3f}s sql={statement[:240]}")

    assert page.first_position == 1
    assert page.last_position == 25
    assert len(page.facility_identities) == 25
    assert len(page.records) == 125
    assert page.total_matching_facility_count == PERFORMANCE_FACILITY_COUNT
    assert elapsed < MAX_PAGE_SECONDS
    assert max(duration for duration, _statement in statement_timings) < (
        STATEMENT_TIMEOUT_MILLISECONDS / 1_000
    )
    statements = [statement for _duration, statement in statement_timings]
    assert not any(" offset " in statement for statement in statements)
    assert sum(
        "facility_intelligence_complaint_facts_substantiated_matches" in statement
        for statement in statements
    ) == 2
    assert sum(
        "facility_intelligence_count_facts" in statement
        for statement in statements
    ) == 1
    hydration_statements = [
        statement
        for statement in statements
        if "facility_intelligence_hydration_references" in statement
    ]
    assert len(hydration_statements) == 1
    assert "facility_id in" in hydration_statements[0]
    assert "substantiated_matches" not in hydration_statements[0]
    review_next_statements = [
        statement
        for statement in statements
        if "select facility_intelligence_facilities.facility_identity from "
        "facility_intelligence_facilities order by" in statement
    ]
    assert len(review_next_statements) == 1
    assert " limit " in review_next_statements[0]


def test_postgres_seek_pages_are_complete_and_reversible(
    postgres_performance_connection: Connection,
) -> None:
    connection = postgres_performance_connection
    filters = FacilityIntelligenceReadFilters(sort="facility_name")
    first = list_facility_intelligence_page(
        connection,
        filters=filters,
        import_batch_id=BOUNDARY_IMPORT_BATCH_ID,
    )
    second = list_facility_intelligence_page(
        connection,
        filters=filters,
        import_batch_id=BOUNDARY_IMPORT_BATCH_ID,
        seek=_next_seek(first),
    )
    final = list_facility_intelligence_page(
        connection,
        filters=filters,
        import_batch_id=BOUNDARY_IMPORT_BATCH_ID,
        seek=_next_seek(second),
    )

    assert [(page.first_position, page.last_position) for page in (first, second, final)] == [
        (1, 25),
        (26, 50),
        (51, 51),
    ]
    identities = [
        identity
        for page in (first, second, final)
        for identity in page.facility_identities
    ]
    assert len(identities) == BOUNDARY_FACILITY_COUNT
    assert len(set(identities)) == BOUNDARY_FACILITY_COUNT
    assert final.next_anchor is None
    assert final.previous_anchor is not None

    back_to_second = list_facility_intelligence_page(
        connection,
        filters=filters,
        import_batch_id=BOUNDARY_IMPORT_BATCH_ID,
        seek=FacilityIntelligenceSeek(
            direction="previous",
            anchor=final.previous_anchor.order_values,
            start_position=final.previous_anchor.start_position,
            expected_total=final.total_matching_facility_count,
        ),
    )
    assert back_to_second.first_position == 26
    assert back_to_second.last_position == 50
    assert back_to_second.facility_identities == second.facility_identities


def _connection_engine(connection: Connection) -> Engine:
    return connection.engine


def _seed_performance_corpus(connection: Connection) -> None:
    _seed_corpus(
        connection,
        import_batch_id=PERFORMANCE_IMPORT_BATCH_ID,
        facility_count=PERFORMANCE_FACILITY_COUNT,
        complaints_per_facility=COMPLAINTS_PER_FACILITY,
        facility_number_prefix="9",
    )


def _seed_corpus(
    connection: Connection,
    *,
    import_batch_id: str,
    facility_count: int,
    complaints_per_facility: int,
    facility_number_prefix: str,
) -> None:
    connection.execute(
        hosted_import_batches.insert().values(
            import_batch_id=import_batch_id,
            imported_at="2026-07-17T12:00:00+00:00",
            source_artifact_identity="issue-419-postgres-performance-fixture",
            source_pipeline_version="issue-419-performance",
            validation_status="validated",
            raw_hash_validation_status="validated",
            record_counts={},
            warnings=[],
            errors=[],
        )
    )
    rows: list[dict[str, Any]] = []
    for facility_index in range(facility_count):
        facility_number = f"{facility_number_prefix}{facility_index:08d}"
        facility_id = f"ccld:facility:{facility_number}"
        rows.append(
            _source_row(
                entity_type="facility",
                import_batch_id=import_batch_id,
                stable_source_id=facility_id,
                source_document_id=f"ccld:document:{facility_number}:facility",
                facility_id=facility_id,
                original_values={
                    "facility_id": facility_id,
                    "external_facility_number": facility_number,
                    "facility_name": f"Postgres Facility {facility_index:05d}",
                    "facility_type": "Children's Center",
                    "county": "Kern",
                },
            )
        )
        for complaint_index in range(complaints_per_facility):
            control_number = f"PG-{facility_number}-{complaint_index}"
            document_id = f"ccld:document:{facility_number}:{complaint_index}"
            rows.append(
                _source_row(
                    entity_type="source_document",
                    import_batch_id=import_batch_id,
                    stable_source_id=document_id,
                    source_document_id=document_id,
                    facility_id=facility_id,
                    original_values={
                        "document_id": document_id,
                        "facility_id": facility_id,
                    },
                )
            )
            rows.append(
                _source_row(
                    entity_type="complaint",
                    import_batch_id=import_batch_id,
                    stable_source_id=f"ccld:complaint:{control_number}",
                    source_document_id=document_id,
                    facility_id=facility_id,
                    original_values={
                        "complaint_id": f"ccld:complaint:{control_number}",
                        "facility_id": facility_id,
                        "complaint_control_number": control_number,
                        "complaint_received_date": "2026-05-01",
                        "finding": "Unsubstantiated",
                    },
                )
            )
    for start in range(0, len(rows), 2_000):
        connection.execute(
            hosted_source_derived_records.insert(),
            rows[start : start + 2_000],
        )


def _source_row(
    *,
    entity_type: str,
    import_batch_id: str,
    stable_source_id: str,
    source_document_id: str,
    facility_id: str,
    original_values: dict[str, Any],
) -> dict[str, Any]:
    return {
        "source_record_key": f"{entity_type}:{stable_source_id}",
        "entity_type": entity_type,
        "stable_source_id": stable_source_id,
        "import_batch_id": import_batch_id,
        "source_document_id": source_document_id,
        "facility_id": facility_id,
        "source_url": "https://example.test/public-source",
        "raw_sha256": "a" * 64,
        "raw_path": None,
        "connector_name": "issue-419-performance",
        "connector_version": "1",
        "retrieved_at": "2026-07-17T12:00:00+00:00",
        "original_values": original_values,
        "source_traceability": {"fixture": "issue-419-postgres-performance"},
    }


def _next_seek(page: Any) -> FacilityIntelligenceSeek:
    assert page.next_anchor is not None
    return FacilityIntelligenceSeek(
        direction="next",
        anchor=page.next_anchor.order_values,
        start_position=page.next_anchor.start_position,
        expected_total=page.total_matching_facility_count,
    )
