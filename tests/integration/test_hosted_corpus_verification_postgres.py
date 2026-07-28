from __future__ import annotations

import copy
import os
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, select, update
from sqlalchemy.engine import Connection

from ccld_complaints.hosted_app.corpus_verification import (
    run_hosted_corpus_verification,
    validate_corpus_verification_result,
)
from ccld_complaints.hosted_app.seeded_import import (
    hosted_import_batches,
    hosted_seeded_import_metadata,
    hosted_source_derived_records,
    import_seeded_corpus_artifact,
    load_seeded_corpus_artifact,
)

POSTGRES_TEST_URL_ENV = "CCLD_TEST_POSTGRES_URL"
POSTGRES_SCHEMA_MUTATION_ENV = "CCLD_TEST_POSTGRES_ALLOW_SCHEMA_MUTATION"
FIXTURE = Path("tests/fixtures/hosted_seeded_corpus/validated_seeded_corpus.json")


@pytest.fixture(scope="module")
def postgres_corpus_connection() -> Iterator[Connection]:
    database_url = os.environ.get(POSTGRES_TEST_URL_ENV, "").strip()
    mutation_allowed = os.environ.get(POSTGRES_SCHEMA_MUTATION_ENV, "").strip() == "1"
    if not database_url or not mutation_allowed:
        pytest.skip(
            f"Set {POSTGRES_TEST_URL_ENV} and {POSTGRES_SCHEMA_MUTATION_ENV}=1 "
            "to run the isolated PostgreSQL corpus-verification regression."
        )
    if not database_url.startswith("postgresql+"):
        pytest.fail(f"{POSTGRES_TEST_URL_ENV} must use a PostgreSQL SQLAlchemy URL.")

    schema_name = f"issue638_corpus_{uuid.uuid4().hex}"
    engine = create_engine(database_url)
    with engine.connect() as connection:
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema_name}"')
        connection.exec_driver_sql(f'SET search_path TO "{schema_name}"')
        hosted_seeded_import_metadata.create_all(connection)
        import_seeded_corpus_artifact(connection, load_seeded_corpus_artifact(FIXTURE))
        connection.execute(
            update(hosted_import_batches).values(
                source_artifact_identity="ccld-retrieval-job:live-corpus",
                source_pipeline_version="live-public-ccld",
            )
        )
        _add_second_facility_bundle(connection)
        connection.commit()
        try:
            yield connection
        finally:
            connection.rollback()
            connection.exec_driver_sql("SET search_path TO public")
            connection.exec_driver_sql(f'DROP SCHEMA "{schema_name}" CASCADE')
            connection.commit()
    engine.dispose()


def test_postgres_json_rows_keep_public_marker_words_and_block_known_synthetic_identity(
    postgres_corpus_connection: Connection,
) -> None:
    connection = postgres_corpus_connection
    facility = _row(connection, "facility")
    public_values = copy.deepcopy(facility["original_values"])
    public_values["facility_name"] = "Public Test Services"
    connection.execute(
        update(hosted_source_derived_records)
        .where(
            hosted_source_derived_records.c.source_record_key == facility["source_record_key"]
        )
        .values(original_values=public_values)
    )

    result = run_hosted_corpus_verification(
        connection,
        deployed_sha="a" * 40,
        environ={"CCLD_HOSTED_PAGE_DATA_MODE": "postgres"},
    )

    validate_corpus_verification_result(result)
    assert result["counts"]["persisted_facility_count"] == 2
    assert result["counts"]["read_model_facility_count"] == 2
    assert result["synthetic_and_fallback"]["synthetic_records"] == []
    assert result["blocking_failures"] == []

    public_values["external_facility_number"] = "900000001"
    connection.execute(
        update(hosted_source_derived_records)
        .where(
            hosted_source_derived_records.c.source_record_key == facility["source_record_key"]
        )
        .values(original_values=public_values)
    )
    blocked = run_hosted_corpus_verification(
        connection,
        deployed_sha="b" * 40,
        environ={"CCLD_HOSTED_PAGE_DATA_MODE": "postgres"},
    )

    assert "synthetic_records_detected" in blocked["blocking_failures"]
    assert blocked["synthetic_and_fallback"]["synthetic_records"] == [
        {
            "record_key": facility["source_record_key"],
            "reason": "known synthetic facility identity",
            "field": "original_values.external_facility_number",
            "marker": "900000001",
        }
    ]


def _add_second_facility_bundle(connection: Connection) -> None:
    facility_number = "200000002"
    facility_id = f"ccld:facility:{facility_number}"
    document_id = f"ccld:document:{facility_number}:1"
    _insert_copy(
        connection,
        "facility",
        source_record_key=f"facility:{facility_id}",
        stable_source_id=facility_id,
        source_document_id=document_id,
        facility_id=facility_id,
        original_values={
            "facility_id": facility_id,
            "external_facility_number": facility_number,
            "facility_number": facility_number,
            "facility_name": "Second Public Facility",
        },
    )
    _insert_copy(
        connection,
        "source_document",
        source_record_key=f"source_document:{document_id}",
        stable_source_id=document_id,
        source_document_id=document_id,
        facility_id=facility_id,
        original_values={"document_id": document_id, "facility_id": facility_id},
    )
    _insert_copy(
        connection,
        "complaint",
        source_record_key="complaint:ccld:complaint:postgres-200000002",
        stable_source_id="ccld:complaint:postgres-200000002",
        source_document_id=document_id,
        facility_id=facility_id,
        original_values={
            "complaint_id": "ccld:complaint:postgres-200000002",
            "facility_id": facility_id,
            "document_id": document_id,
            "complaint_control_number": "postgres-200000002",
            "complaint_received_date": "2026-07-28",
        },
    )


def _insert_copy(
    connection: Connection,
    entity_type: str,
    *,
    source_record_key: str,
    stable_source_id: str,
    source_document_id: str,
    facility_id: str,
    original_values: dict[str, str],
) -> None:
    values = _row(connection, entity_type)
    values.update(
        source_record_key=source_record_key,
        stable_source_id=stable_source_id,
        source_document_id=source_document_id,
        facility_id=facility_id,
        original_values=original_values,
        source_traceability={"source_document_id": source_document_id},
    )
    connection.execute(hosted_source_derived_records.insert().values(**values))


def _row(connection: Connection, entity_type: str) -> dict[str, Any]:
    row = connection.execute(
        select(hosted_source_derived_records).where(
            hosted_source_derived_records.c.entity_type == entity_type
        )
    ).mappings().first()
    assert row is not None
    return dict(row)
