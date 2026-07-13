from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Connection

from ccld_complaints.hosted_app.seeded_import import (
    hosted_seeded_import_metadata,
    import_seeded_corpus_artifact,
    load_seeded_corpus_artifact,
)
from ccld_complaints.hosted_app.source_derived_reads import (
    get_source_derived_record_by_identity,
    get_source_derived_record_by_key,
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
