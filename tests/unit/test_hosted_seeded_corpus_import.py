from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, cast

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError

from ccld_complaints.hosted_app.seeded_import import (
    flatten_seeded_corpus_records,
    hosted_import_batches,
    hosted_seeded_import_metadata,
    hosted_source_derived_records,
    import_seeded_corpus_artifact,
    load_seeded_corpus_artifact,
    parse_seeded_corpus_artifact,
)

FIXTURE = Path("tests/fixtures/hosted_seeded_corpus/validated_seeded_corpus.json")


def test_load_seeded_corpus_artifact_preserves_batch_and_traceability() -> None:
    artifact = load_seeded_corpus_artifact(FIXTURE)
    flattened = flatten_seeded_corpus_records(artifact)
    complaint = next(record for record in flattened if record.entity_type == "complaint")
    facility = next(record for record in flattened if record.entity_type == "facility")
    event = next(record for record in flattened if record.entity_type == "event")

    assert artifact.import_batch_id == "seeded-ccld-fixture-2026-06-13"
    assert artifact.validation_status == "validated"
    assert artifact.raw_hash_validation_status == "validated"
    assert len(flattened) == 7
    assert complaint.source_document_id == "ccld:document:157806098:3"
    assert complaint.source_url.startswith("https://www.ccld.dss.ca.gov/")
    assert complaint.raw_sha256 == (
        "6088c9627374baac647e2f2a54f6e389cb68c1b92db42da00020aaf508a853bd"
    )
    assert complaint.connector_name == "ccld_facility_reports"
    assert complaint.original_values["complaint_control_number"] == "32-CR-20220407124448"
    assert complaint.original_values["first_investigation_activity_date"] == "2022-04-14"
    assert complaint.original_values["days_received_to_first_activity"] == 7
    assert facility.original_values["facility_type"] is None
    assert facility.original_values["county"] is None
    assert facility.original_values["status"] is None
    assert facility.original_values["capacity"] == 48
    assert facility.original_values["regional_office"] == "CCLD Regional Office"
    assert event.original_values["event_date"] == "2022-04-14"
    assert complaint.source_traceability["source_artifact_identity"] == (
        "tests/fixtures/hosted_seeded_corpus/validated_seeded_corpus.json"
    )


def test_import_seeded_corpus_artifact_stages_source_derived_records_only() -> None:
    artifact = load_seeded_corpus_artifact(FIXTURE)
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)

    with engine.begin() as connection:
        result = import_seeded_corpus_artifact(connection, artifact)
        batch_rows = connection.execute(select(hosted_import_batches)).mappings().all()
        source_rows = connection.execute(select(hosted_source_derived_records)).mappings().all()

    complaint_row = next(row for row in source_rows if row["entity_type"] == "complaint")

    assert result.import_batch_id == artifact.import_batch_id
    assert result.imported_record_count == 7
    assert result.imported_counts_by_entity == {
        "facility": 1,
        "source_document": 1,
        "complaint": 1,
        "allegation": 2,
        "event": 1,
        "extraction_audit": 1,
    }
    assert result.reviewer_created_state_written is False
    assert len(batch_rows) == 1
    assert len(source_rows) == 7
    assert complaint_row["import_batch_id"] == artifact.import_batch_id
    assert complaint_row["source_url"].startswith("https://www.ccld.dss.ca.gov/")
    assert complaint_row["connector_version"] == "0.1.0"
    assert complaint_row["original_values"]["finding"] == "Unsubstantiated"
    assert "review_status" not in complaint_row["original_values"]
    assert "annotation" not in complaint_row["original_values"]


def test_import_seeded_corpus_artifact_is_idempotent_for_same_stable_identity() -> None:
    artifact = load_seeded_corpus_artifact(FIXTURE)
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)

    with engine.begin() as connection:
        first_result = import_seeded_corpus_artifact(connection, artifact)
        second_result = import_seeded_corpus_artifact(connection, artifact)
        batch_count = connection.execute(
            select(func.count()).select_from(hosted_import_batches)
        ).scalar_one()
        source_count = connection.execute(
            select(func.count()).select_from(hosted_source_derived_records)
        ).scalar_one()

    assert first_result.imported_record_count == second_result.imported_record_count == 7
    assert batch_count == 1
    assert source_count == 7


@pytest.mark.parametrize("entity_type", ("complaint", "facility"))
def test_persistence_rejects_duplicate_current_stable_identity(
    entity_type: str,
) -> None:
    artifact = load_seeded_corpus_artifact(FIXTURE)
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)

    with engine.begin() as connection:
        import_seeded_corpus_artifact(connection, artifact)
        existing = (
            connection.execute(
                select(hosted_source_derived_records).where(
                    hosted_source_derived_records.c.entity_type == entity_type
                )
            )
            .mappings()
            .one()
        )
        duplicate = {
            column.name: existing[column.name]
            for column in hosted_source_derived_records.columns
        }
        duplicate["source_record_key"] = f"00-conflicting-{entity_type}-source-key"

        with pytest.raises(IntegrityError):
            with connection.begin_nested():
                connection.execute(
                    hosted_source_derived_records.insert().values(**duplicate)
                )

        current_identity_count = connection.execute(
            select(func.count())
            .select_from(hosted_source_derived_records)
            .where(
                hosted_source_derived_records.c.entity_type == entity_type,
                hosted_source_derived_records.c.stable_source_id
                == existing["stable_source_id"],
            )
        ).scalar_one()

    assert current_identity_count == 1


def test_hosted_facility_refresh_does_not_erase_governed_values_with_nulls() -> None:
    populated = load_seeded_corpus_artifact(FIXTURE)
    sparse_data = _fixture_data()
    sparse_record = cast(list[dict[str, Any]], sparse_data["records"])[0]
    sparse_facility = cast(dict[str, Any], sparse_record["facility"])
    sparse_facility["facility_type"] = None
    sparse_facility["county"] = None
    sparse_facility["capacity"] = None
    sparse_facility["regional_office"] = None
    sparse = parse_seeded_corpus_artifact(sparse_data)
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)

    with engine.begin() as connection:
        import_seeded_corpus_artifact(connection, populated)
        import_seeded_corpus_artifact(connection, sparse)
        facility_values = connection.execute(
            select(hosted_source_derived_records.c.original_values).where(
                hosted_source_derived_records.c.entity_type == "facility"
            )
        ).scalar_one()

    assert facility_values["facility_type"] is None
    assert facility_values["county"] is None
    assert facility_values["capacity"] == 48
    assert facility_values["regional_office"] == "CCLD Regional Office"


def test_seeded_corpus_artifact_rejects_unvalidated_input() -> None:
    data = _fixture_data()
    data["validation_status"] = "draft"

    try:
        parse_seeded_corpus_artifact(data)
    except ValueError as error:
        assert "validation_status" in str(error)
    else:
        raise AssertionError("Expected unvalidated artifact to be rejected.")


def test_seeded_corpus_artifact_requires_source_traceability() -> None:
    data = _fixture_data()
    records = cast(list[dict[str, Any]], data["records"])
    source_document = cast(dict[str, Any], records[0]["source_document"])
    source_document["raw_sha256"] = (
        "6088C9627374BAAC647E2F2A54F6E389CB68C1B92DB42DA00020AAF508A853BD"
    )

    artifact = parse_seeded_corpus_artifact(data)
    try:
        flatten_seeded_corpus_records(artifact)
    except ValueError as error:
        assert "lowercase SHA-256" in str(error)
    else:
        raise AssertionError("Expected uppercase raw hash to be rejected.")


def _fixture_data() -> dict[str, Any]:
    artifact = load_seeded_corpus_artifact(FIXTURE)
    return copy.deepcopy(
        {
            "import_batch_id": artifact.import_batch_id,
            "imported_at": artifact.imported_at,
            "source_artifact_identity": artifact.source_artifact_identity,
            "source_pipeline_version": artifact.source_pipeline_version,
            "validation_status": artifact.validation_status,
            "raw_hash_validation_status": artifact.raw_hash_validation_status,
            "record_counts": dict(artifact.record_counts),
            "warnings": list(artifact.warnings),
            "errors": list(artifact.errors),
            "records": [dict(record) for record in artifact.records],
        }
    )
