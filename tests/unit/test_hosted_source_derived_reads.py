from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, select, update
from sqlalchemy.engine import Connection

from ccld_complaints.hosted_app.seeded_import import (
    hosted_seeded_import_metadata,
    hosted_source_derived_records,
    import_seeded_corpus_artifact,
    load_seeded_corpus_artifact,
)
from ccld_complaints.hosted_app.source_derived_reads import (
    find_ccld_source_derived_records_for_request,
    get_source_derived_record_by_identity,
    get_source_derived_record_by_key,
    list_source_derived_complaint_bundle,
    list_source_derived_record_result,
    list_source_derived_records,
    list_source_derived_records_by_entity_types,
)

FIXTURE = Path("tests/fixtures/hosted_seeded_corpus/validated_seeded_corpus.json")


def test_list_source_derived_records_preserves_traceability_and_batch_context() -> None:
    with _seeded_connection() as connection:
        records = list_source_derived_records(connection)

    complaint = next(record for record in records if record.entity_type == "complaint")

    assert len(records) == 7
    assert complaint.source_record_key == "complaint:ccld:complaint:32-CR-20220407124448"
    assert complaint.stable_source_id == "ccld:complaint:32-CR-20220407124448"
    assert complaint.source_document_id == "ccld:document:157806098:3"
    assert complaint.source_url.startswith("https://www.ccld.dss.ca.gov/")
    assert complaint.raw_sha256 == (
        "6088c9627374baac647e2f2a54f6e389cb68c1b92db42da00020aaf508a853bd"
    )
    assert complaint.raw_path == "tests/fixtures/ccld/raw/157806098_inx3.html"
    assert complaint.connector_name == "ccld_facility_reports"
    assert complaint.connector_version == "0.1.0"
    assert complaint.retrieved_at == "2026-06-10T00:00:00+00:00"
    assert complaint.original_values["finding"] == "Unsubstantiated"
    assert complaint.source_traceability["source_artifact_identity"] == (
        "tests/fixtures/hosted_seeded_corpus/validated_seeded_corpus.json"
    )
    assert complaint.import_batch.import_batch_id == "seeded-ccld-fixture-2026-06-13"
    assert complaint.import_batch.validation_status == "validated"
    assert complaint.import_batch.raw_hash_validation_status == "validated"
    assert complaint.import_batch.record_counts["complaint"] == 1
    assert complaint.import_batch.warnings == (
        "Tiny fixture-backed seeded corpus for local import tests only; not complete "
        "source coverage.",
    )


def test_list_source_derived_records_can_filter_by_entity_and_batch() -> None:
    with _seeded_connection() as connection:
        allegations = list_source_derived_records(
            connection,
            entity_type="allegation",
            import_batch_id="seeded-ccld-fixture-2026-06-13",
        )

    assert [record.entity_type for record in allegations] == ["allegation", "allegation"]
    assert [record.stable_source_id for record in allegations] == [
        "ccld:allegation:32-CR-20220407124448:1",
        "ccld:allegation:32-CR-20220407124448:2",
    ]


def test_list_source_derived_records_supports_limit_and_offset() -> None:
    with _seeded_connection() as connection:
        records = list_source_derived_records(connection, limit=1, offset=2)

    assert len(records) == 1
    assert records[0].entity_type == "complaint"


def test_source_derived_list_has_no_default_cap_and_explicit_limit_is_reported() -> None:
    with _seeded_connection() as connection:
        _insert_additional_complaint_rows(connection, count=125)
        uncapped = list_source_derived_record_result(connection, entity_type="complaint")
        limited = list_source_derived_record_result(
            connection,
            entity_type="complaint",
            limit=100,
        )

    assert len(uncapped.records) == 126
    assert uncapped.aggregate.eligible_count == 126
    assert uncapped.aggregate.limit is None
    assert uncapped.aggregate.truncated is False
    assert len(limited.records) == 100
    assert limited.aggregate.eligible_count == 126
    assert limited.aggregate.status == "truncated"
    assert limited.aggregate.truncated is True


def test_complaint_bundle_filters_counts_and_limits_without_offset_traversal() -> None:
    statements: list[str] = []
    with _seeded_connection() as connection:
        _insert_additional_complaint_rows(connection, count=125)

        def capture_statement(
            _connection: object,
            _cursor: object,
            statement: str,
            _parameters: object,
            _context: object,
            _executemany: bool,
        ) -> None:
            statements.append(statement)

        event.listen(connection, "before_cursor_execute", capture_statement)
        try:
            result = list_source_derived_complaint_bundle(
                connection,
                facility_number="157806098",
                start_date="2022-08-01",
                end_date="2022-08-31",
                date_dimension="any_review_date",
                limit=100,
            )
        finally:
            event.remove(connection, "before_cursor_execute", capture_statement)

    assert len(result.records) == 100
    assert result.aggregate.eligible_count == 126
    assert result.aggregate.truncated is True
    assert [record.source_record_key for record in result.records] == sorted(
        record.source_record_key for record in result.records
    )
    assert {record.entity_type for record in result.related_records}.issubset(
        {"facility", "source_document", "complaint", "allegation", "event"}
    )
    assert len(statements) == 3
    assert all("OFFSET 100" not in statement.upper() for statement in statements)
    assert all("OFFSET 200" not in statement.upper() for statement in statements)
    assert any(" LIMIT " in statement.upper() for statement in statements)


def test_complaint_bundle_date_filter_preserves_calendar_validation() -> None:
    with _seeded_connection() as connection:
        original_values = dict(
            connection.execute(
                select(hosted_source_derived_records.c.original_values).where(
                    hosted_source_derived_records.c.entity_type == "complaint"
                )
            ).scalar_one()
        )
        for field_name in (
            "complaint_received_date",
            "first_investigation_activity_date",
            "visit_date",
            "report_date",
            "date_signed",
        ):
            original_values[field_name] = ""
        original_values["complaint_received_date"] = "2022-02-31"
        connection.execute(
            update(hosted_source_derived_records)
            .where(hosted_source_derived_records.c.entity_type == "complaint")
            .values(original_values=original_values)
        )
        invalid = list_source_derived_complaint_bundle(
            connection,
            start_date="2022-02-01",
            end_date="2022-02-28",
        )

        original_values["complaint_received_date"] = "2020-02-29"
        connection.execute(
            update(hosted_source_derived_records)
            .where(hosted_source_derived_records.c.entity_type == "complaint")
            .values(original_values=original_values)
        )
        leap_day = list_source_derived_complaint_bundle(
            connection,
            start_date="2020-02-29",
            end_date="2020-02-29",
        )

    assert invalid.records == ()
    assert invalid.aggregate.eligible_count == 0
    assert len(leap_day.records) == 1
    assert leap_day.aggregate.eligible_count == 1


def test_request_lookup_applies_selected_first_activity_date_dimension() -> None:
    with _seeded_connection() as connection:
        first_activity_match = find_ccld_source_derived_records_for_request(
            connection,
            facility_number="157806098",
            start_date="2022-04-14",
            end_date="2022-04-14",
            date_dimension="first_investigation_activity_date",
        )
        received_date_does_not_match = find_ccld_source_derived_records_for_request(
            connection,
            facility_number="157806098",
            start_date="2022-04-07",
            end_date="2022-04-07",
            date_dimension="first_investigation_activity_date",
        )

    assert len(first_activity_match.matched_complaint_keys) == 1
    assert received_date_does_not_match.matched_complaint_keys == ()


def test_list_source_derived_records_by_entity_types_is_uncapped_and_excludes_audit() -> None:
    with _seeded_connection() as connection:
        _insert_extraction_audit_row(connection)
        records = list_source_derived_records_by_entity_types(
            connection,
            entity_types=("facility", "source_document", "complaint", "allegation"),
        )

    assert {record.entity_type for record in records} == {
        "facility",
        "source_document",
        "complaint",
        "allegation",
    }
    assert "AUDIT SHOULD NOT LOAD" not in {
        str(value)
        for record in records
        for value in record.original_values.values()
    }


def test_fetch_source_derived_record_by_staged_key() -> None:
    with _seeded_connection() as connection:
        record = get_source_derived_record_by_key(
            connection,
            "source_document:ccld:document:157806098:3",
        )

    assert record is not None
    assert record.entity_type == "source_document"
    assert record.stable_source_id == "ccld:document:157806098:3"
    assert record.original_values["document_type"] == "complaint_investigation_report"
    assert record.source_traceability["report_index"] == 3
    assert "review_status" not in record.original_values
    assert "annotation" not in record.original_values


def test_fetch_source_derived_record_by_stable_identity() -> None:
    with _seeded_connection() as connection:
        record = get_source_derived_record_by_identity(
            connection,
            entity_type="facility",
            stable_source_id="ccld:facility:157806098",
        )

    assert record is not None
    assert record.source_record_key == "facility:ccld:facility:157806098"
    assert record.facility_id == "ccld:facility:157806098"
    assert record.original_values["facility_name"] == "A. MIRIAM JAMISON CHILDREN'S CENTER"


def test_fetch_source_derived_record_returns_none_for_missing_identity() -> None:
    with _seeded_connection() as connection:
        record = get_source_derived_record_by_identity(
            connection,
            entity_type="complaint",
            stable_source_id="missing-complaint",
        )

    assert record is None


def test_list_source_derived_records_rejects_non_positive_limit() -> None:
    with _seeded_connection() as connection:
        with pytest.raises(ValueError, match="limit"):
            list_source_derived_records(connection, limit=0)


def test_list_source_derived_records_rejects_negative_offset() -> None:
    with _seeded_connection() as connection:
        with pytest.raises(ValueError, match="offset"):
            list_source_derived_records(connection, offset=-1)


def _seeded_connection() -> Connection:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)
    connection = engine.connect()
    transaction = connection.begin()
    artifact = load_seeded_corpus_artifact(FIXTURE)
    import_seeded_corpus_artifact(connection, artifact)
    transaction.commit()
    return connection


def _insert_extraction_audit_row(connection: Connection) -> None:
    from ccld_complaints.hosted_app.seeded_import import (
        hosted_import_batches,
        hosted_source_derived_records,
    )

    batch_id = connection.execute(
        hosted_import_batches.select().with_only_columns(
            hosted_import_batches.c.import_batch_id
        )
    ).scalar_one()
    template = connection.execute(
        hosted_source_derived_records.select().where(
            hosted_source_derived_records.c.entity_type == "complaint"
        )
    ).mappings().one()
    connection.execute(
        hosted_source_derived_records.insert().values(
            source_record_key="extraction_audit:ccld:audit:do-not-load",
            entity_type="extraction_audit",
            stable_source_id="ccld:audit:do-not-load",
            import_batch_id=batch_id,
            source_document_id=template["source_document_id"],
            facility_id=template["facility_id"],
            source_url=template["source_url"],
            raw_sha256=template["raw_sha256"],
            raw_path=template["raw_path"],
            connector_name=template["connector_name"],
            connector_version=template["connector_version"],
            retrieved_at=template["retrieved_at"],
            original_values={
                "audit_id": "ccld:audit:do-not-load",
                "finding": "Substantiated",
                "complaint_control_number": "AUDIT SHOULD NOT LOAD",
            },
            source_traceability=template["source_traceability"],
        )
    )


def _insert_additional_complaint_rows(connection: Connection, *, count: int) -> None:
    from ccld_complaints.hosted_app.seeded_import import hosted_source_derived_records

    template = connection.execute(
        hosted_source_derived_records.select().where(
            hosted_source_derived_records.c.entity_type == "complaint"
        )
    ).mappings().one()
    rows = []
    for index in range(count):
        values = dict(template)
        values["source_record_key"] = f"complaint:aggregate-evidence:{index:03d}"
        values["stable_source_id"] = f"aggregate-evidence:{index:03d}"
        original_values = dict(template["original_values"])
        original_values["complaint_id"] = f"aggregate-evidence:{index:03d}"
        values["original_values"] = original_values
        rows.append(values)
    connection.execute(hosted_source_derived_records.insert(), rows)
