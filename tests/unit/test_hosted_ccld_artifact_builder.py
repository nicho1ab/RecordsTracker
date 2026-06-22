from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, cast

import pytest
from sqlalchemy import create_engine, select

from ccld_complaints.hosted_app.ccld_hosted_artifact_builder import (
    build_ccld_hosted_seeded_corpus_artifact,
    write_ccld_hosted_seeded_corpus_artifact,
)
from ccld_complaints.hosted_app.ccld_import_reload import (
    CcldImportReloadRequest,
    ccld_import_reload_context_for_connection,
    import_reload_validated_ccld_records,
)
from ccld_complaints.hosted_app.reviewer_ui import LOCAL_REVIEWER_UI_SCOPE
from ccld_complaints.hosted_app.seeded_import import (
    flatten_seeded_corpus_records,
    hosted_seeded_import_metadata,
    hosted_source_derived_records,
    import_seeded_corpus_artifact,
    load_seeded_corpus_artifact,
    parse_seeded_corpus_artifact,
)
from ccld_complaints.local_sample import (
    populate_multi_facility_sample_database,
    populate_sample_database,
)
from ccld_complaints.utils.hash import sha256_bytes

RAW_FIXTURE = Path("tests/fixtures/ccld/raw/157806098_inx3.html")


def test_ccld_hosted_artifact_builder_converts_fixture_sqlite_to_validated_seeded_json(
    tmp_path: Path,
) -> None:
    db_path = _fixture_sqlite_db(tmp_path)

    result = build_ccld_hosted_seeded_corpus_artifact(
        db_path,
        facility_number="157806098",
        start_date="2022-08-01",
        end_date="2022-08-31",
        import_batch_id=LOCAL_REVIEWER_UI_SCOPE.scope_id,
        imported_at="2026-06-14T00:00:00+00:00",
        source_artifact_identity="fixture-ccld-sqlite-output",
    )
    artifact = parse_seeded_corpus_artifact(result.artifact)
    flattened = flatten_seeded_corpus_records(artifact)
    source_document = cast(dict[str, Any], artifact.records[0]["source_document"])
    complaint = cast(dict[str, Any], artifact.records[0]["complaint"])

    assert result.output_path is None
    assert result.facility_number == "157806098"
    assert result.record_count == 1
    assert result.source_derived_record_count == len(flattened)
    assert result.counts_by_entity == {
        "facility": 1,
        "source_document": 1,
        "complaint": 1,
        "allegation": 2,
        "event": 0,
        "extraction_audit": 21,
    }
    assert artifact.import_batch_id == LOCAL_REVIEWER_UI_SCOPE.scope_id
    assert artifact.validation_status == "validated"
    assert artifact.raw_hash_validation_status == "validated"
    assert artifact.source_pipeline_version == "ccld-sqlite-hosted-artifact-builder-0.1.0"
    assert source_document["source_url"] == (
        "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports"
        "?facNum=157806098&inx=3"
    )
    assert source_document["raw_sha256"] == sha256_bytes(RAW_FIXTURE.read_bytes())
    assert source_document["raw_path"] == RAW_FIXTURE.as_posix()
    assert source_document["connector_name"] == "ccld_facility_reports"
    assert source_document["connector_version"] == "0.1.0"
    assert complaint["complaint_control_number"] == "32-CR-20220407124448"
    assert complaint["review_delay_over_120_days"] is True
    assert {record.entity_type for record in flattened} == {
        "facility",
        "source_document",
        "complaint",
        "allegation",
        "extraction_audit",
    }


def test_ccld_hosted_artifact_builder_writes_deterministic_no_secret_output(
    tmp_path: Path,
) -> None:
    db_path = _fixture_sqlite_db(tmp_path)
    first_output_path = tmp_path / "first-ccld-artifact.json"
    second_output_path = tmp_path / "second-ccld-artifact.json"

    first_result = write_ccld_hosted_seeded_corpus_artifact(
        db_path,
        first_output_path,
        facility_number="157806098",
        import_batch_id=LOCAL_REVIEWER_UI_SCOPE.scope_id,
        imported_at="2026-06-14T00:00:00+00:00",
        source_artifact_identity="fixture-ccld-sqlite-output",
        overwrite=True,
    )
    second_result = write_ccld_hosted_seeded_corpus_artifact(
        db_path,
        second_output_path,
        facility_number="157806098",
        import_batch_id=LOCAL_REVIEWER_UI_SCOPE.scope_id,
        imported_at="2026-06-14T00:00:00+00:00",
        source_artifact_identity="fixture-ccld-sqlite-output",
        overwrite=True,
    )

    first_json = first_output_path.read_text(encoding="utf-8")
    second_json = second_output_path.read_text(encoding="utf-8")
    lowered_json = first_json.casefold()

    assert first_result.output_path == first_output_path
    assert second_result.source_derived_record_count == first_result.source_derived_record_count
    assert first_json == second_json
    assert "authorization" not in lowered_json
    assert "client_secret" not in lowered_json
    assert "connection string" not in lowered_json
    assert "cookie" not in lowered_json
    assert "password" not in lowered_json
    assert "provider_subject" not in lowered_json
    assert "token" not in lowered_json
    assert str(tmp_path).casefold() not in lowered_json


def test_ccld_hosted_artifact_builder_output_imports_into_hosted_source_derived_rows(
    tmp_path: Path,
) -> None:
    db_path = _fixture_sqlite_db(tmp_path)
    output_path = tmp_path / "generated-ccld-seeded-corpus.json"
    write_ccld_hosted_seeded_corpus_artifact(
        db_path,
        output_path,
        facility_number="157806098",
        import_batch_id=LOCAL_REVIEWER_UI_SCOPE.scope_id,
        imported_at="2026-06-14T00:00:00+00:00",
        source_artifact_identity="fixture-ccld-sqlite-output",
        overwrite=True,
    )
    artifact = load_seeded_corpus_artifact(output_path)
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)

    with engine.begin() as connection:
        import_result = import_seeded_corpus_artifact(connection, artifact)
        rows = connection.execute(
            select(hosted_source_derived_records).order_by(
                hosted_source_derived_records.c.source_record_key
            )
        ).mappings().all()

    complaint_row = next(row for row in rows if row["entity_type"] == "complaint")

    assert import_result.import_batch_id == LOCAL_REVIEWER_UI_SCOPE.scope_id
    assert import_result.imported_record_count == 26
    assert len(rows) == 26
    assert complaint_row["source_url"].startswith("https://www.ccld.dss.ca.gov/")
    assert complaint_row["raw_sha256"] == sha256_bytes(RAW_FIXTURE.read_bytes())
    assert complaint_row["raw_path"] == RAW_FIXTURE.as_posix()
    assert complaint_row["connector_name"] == "ccld_facility_reports"
    assert complaint_row["source_traceability"]["source_artifact_identity"] == (
        "fixture-ccld-sqlite-output"
    )


def test_ccld_hosted_artifact_builder_output_is_compatible_with_import_reload(
    tmp_path: Path,
) -> None:
    db_path = _fixture_sqlite_db(tmp_path)
    output_path = tmp_path / "generated-ccld-seeded-corpus.json"
    write_ccld_hosted_seeded_corpus_artifact(
        db_path,
        output_path,
        facility_number="157806098",
        start_date="2022-08-01",
        end_date="2022-08-31",
        import_batch_id=LOCAL_REVIEWER_UI_SCOPE.scope_id,
        imported_at="2026-06-14T00:00:00+00:00",
        source_artifact_identity="fixture-ccld-sqlite-output",
        overwrite=True,
    )
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)

    with engine.begin() as connection:
        result = import_reload_validated_ccld_records(
            ccld_import_reload_context_for_connection(
                connection,
                scope=LOCAL_REVIEWER_UI_SCOPE,
                artifact_paths=(output_path,),
            ),
            CcldImportReloadRequest(
                facility_number="157806098",
                start_date="2022-08-01",
                end_date="2022-08-31",
            ),
        )

    assert result.import_executed is True
    assert result.available_before_count == 0
    assert result.available_after_count == 26
    assert result.imported_source_record_count == 26
    assert result.refreshed_source_record_count == 0
    assert result.skipped_non_matching_source_record_count == 0
    assert result.source_artifact_identities == ("fixture-ccld-sqlite-output",)
    assert result.deferred_reasons == ()


def test_ccld_hosted_artifact_builder_rejects_missing_traceability(tmp_path: Path) -> None:
    db_path = _fixture_sqlite_db(tmp_path)
    with sqlite3.connect(db_path) as connection:
        connection.execute("UPDATE source_documents SET raw_sha256 = 'missing-hash'")
        connection.commit()

    with pytest.raises(ValueError, match="raw_sha256"):
        build_ccld_hosted_seeded_corpus_artifact(
            db_path,
            facility_number="157806098",
            import_batch_id=LOCAL_REVIEWER_UI_SCOPE.scope_id,
            imported_at="2026-06-14T00:00:00+00:00",
            source_artifact_identity="fixture-ccld-sqlite-output",
        )


def test_ccld_hosted_artifact_builder_rejects_private_or_absolute_raw_path(
    tmp_path: Path,
) -> None:
    db_path = _fixture_sqlite_db(tmp_path)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE source_documents SET raw_path = ?",
            (r"C:\Users\tester\private\157806098_inx3.html",),
        )
        connection.commit()

    with pytest.raises(ValueError, match="raw_path must be relative"):
        build_ccld_hosted_seeded_corpus_artifact(
            db_path,
            facility_number="157806098",
            import_batch_id=LOCAL_REVIEWER_UI_SCOPE.scope_id,
            imported_at="2026-06-14T00:00:00+00:00",
            source_artifact_identity="fixture-ccld-sqlite-output",
        )


def test_ccld_hosted_artifact_builder_full_corpus_builds_from_multi_facility_sqlite(
    tmp_path: Path,
) -> None:
    db_path = _multi_facility_sqlite_db(tmp_path)

    result = build_ccld_hosted_seeded_corpus_artifact(
        db_path,
        all_facilities=True,
        import_batch_id=LOCAL_REVIEWER_UI_SCOPE.scope_id,
        imported_at="2026-06-14T00:00:00+00:00",
        source_artifact_identity="fixture-ccld-multi-facility-sqlite-output",
    )

    assert result.corpus_scope == "full-corpus"
    assert result.facility_number == "all"
    assert len(result.facility_numbers) >= 2
    assert "157806097" in result.facility_numbers
    assert "157806098" in result.facility_numbers
    assert result.record_count >= 2
    artifact = parse_seeded_corpus_artifact(result.artifact)
    assert artifact.import_batch_id == LOCAL_REVIEWER_UI_SCOPE.scope_id
    assert artifact.validation_status == "validated"
    assert result.artifact.get("corpus_scope") == "full-corpus"


def test_ccld_hosted_artifact_builder_full_corpus_artifact_imports_into_hosted_rows(
    tmp_path: Path,
) -> None:
    db_path = _multi_facility_sqlite_db(tmp_path)
    output_path = tmp_path / "full-corpus-ccld-seeded-corpus.json"
    write_ccld_hosted_seeded_corpus_artifact(
        db_path,
        output_path,
        all_facilities=True,
        import_batch_id=LOCAL_REVIEWER_UI_SCOPE.scope_id,
        imported_at="2026-06-14T00:00:00+00:00",
        source_artifact_identity="fixture-ccld-multi-facility-sqlite-output",
        overwrite=True,
    )
    artifact = load_seeded_corpus_artifact(output_path)
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)

    with engine.begin() as connection:
        import_result = import_seeded_corpus_artifact(connection, artifact)
        rows = connection.execute(
            select(hosted_source_derived_records).order_by(
                hosted_source_derived_records.c.source_record_key
            )
        ).mappings().all()

    entity_types = {row["entity_type"] for row in rows}
    facility_numbers_in_db = {
        row["original_values"].get("external_facility_number")
        for row in rows
        if row["entity_type"] == "facility"
    }

    assert import_result.imported_record_count > 0
    assert len(rows) == import_result.imported_record_count
    assert "complaint" in entity_types
    assert "facility" in entity_types
    assert "157806097" in facility_numbers_in_db
    assert "157806098" in facility_numbers_in_db


def test_ccld_hosted_artifact_builder_rejects_multi_facility_sqlite_without_all_facilities(
    tmp_path: Path,
) -> None:
    db_path = _multi_facility_sqlite_db(tmp_path)

    with pytest.raises(ValueError, match="multiple"):
        build_ccld_hosted_seeded_corpus_artifact(
            db_path,
            import_batch_id=LOCAL_REVIEWER_UI_SCOPE.scope_id,
            imported_at="2026-06-14T00:00:00+00:00",
            source_artifact_identity="fixture-ccld-sqlite-output",
        )


def test_ccld_hosted_artifact_builder_rejects_all_facilities_with_facility_number(
    tmp_path: Path,
) -> None:
    db_path = _fixture_sqlite_db(tmp_path)

    with pytest.raises(ValueError, match="mutually exclusive"):
        build_ccld_hosted_seeded_corpus_artifact(
            db_path,
            facility_number="157806098",
            all_facilities=True,
            import_batch_id=LOCAL_REVIEWER_UI_SCOPE.scope_id,
            imported_at="2026-06-14T00:00:00+00:00",
            source_artifact_identity="fixture-ccld-sqlite-output",
        )


def _fixture_sqlite_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "validated-ccld.sqlite"
    populate_sample_database(db_path)
    return db_path


def _multi_facility_sqlite_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "validated-ccld-multi.sqlite"
    populate_multi_facility_sample_database(db_path)
    return db_path