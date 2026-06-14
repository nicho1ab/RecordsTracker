from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Connection

from ccld_complaints.hosted_app.ccld_import_reload import (
    CcldImportReloadContext,
    CcldImportReloadRequest,
    ccld_import_reload_context_for_connection,
    import_reload_validated_ccld_records,
)
from ccld_complaints.hosted_app.reviewer_ui import LOCAL_REVIEWER_UI_SCOPE
from ccld_complaints.hosted_app.seeded_import import (
    hosted_import_batches,
    hosted_seeded_import_metadata,
    hosted_source_derived_records,
)

FIXTURE = Path("tests/fixtures/hosted_seeded_corpus/validated_seeded_corpus.json")


def test_ccld_import_reload_loads_validated_fixture_into_empty_hosted_records() -> None:
    with _empty_connection() as connection:
        result = import_reload_validated_ccld_records(
            _context(connection),
            CcldImportReloadRequest(
                facility_number="157806098",
                start_date="2022-08-01",
                end_date="2022-08-31",
            ),
        )
        counts = _table_counts(connection)
        complaint = (
            connection.execute(
                select(hosted_source_derived_records).where(
                    hosted_source_derived_records.c.entity_type == "complaint"
                )
            )
            .mappings()
            .one()
        )

    assert result.import_executed is True
    assert result.available_before_count == 0
    assert result.available_after_count == 6
    assert result.imported_source_record_count == 6
    assert result.refreshed_source_record_count == 0
    assert result.skipped_duplicate_source_record_count == 0
    assert result.skipped_non_matching_source_record_count == 0
    assert result.source_artifact_identities == (FIXTURE.as_posix(),)
    assert result.deferred_reasons == ()
    assert counts == {"import_batches": 1, "source_records": 6}
    assert complaint["source_url"].startswith("https://www.ccld.dss.ca.gov/")
    assert complaint["raw_sha256"] == (
        "6088c9627374baac647e2f2a54f6e389cb68c1b92db42da00020aaf508a853bd"
    )
    assert complaint["raw_path"] == "tests/fixtures/ccld/raw/157806098_inx3.html"
    assert complaint["connector_name"] == "ccld_facility_reports"
    assert complaint["source_traceability"]["source_artifact_identity"] == FIXTURE.as_posix()


def test_ccld_import_reload_refreshes_existing_rows_without_duplicates() -> None:
    with _empty_connection() as connection:
        first_result = import_reload_validated_ccld_records(
            _context(connection),
            CcldImportReloadRequest(facility_number="157806098"),
        )
        second_result = import_reload_validated_ccld_records(
            _context(connection),
            CcldImportReloadRequest(facility_number="157806098"),
        )
        counts = _table_counts(connection)

    assert first_result.imported_source_record_count == 6
    assert second_result.import_executed is True
    assert second_result.available_before_count == 6
    assert second_result.available_after_count == 6
    assert second_result.imported_source_record_count == 0
    assert second_result.refreshed_source_record_count == 6
    assert second_result.skipped_duplicate_source_record_count == 6
    assert counts == {"import_batches": 1, "source_records": 6}


def test_ccld_import_reload_defers_when_validated_output_does_not_match_date() -> None:
    with _empty_connection() as connection:
        result = import_reload_validated_ccld_records(
            _context(connection),
            CcldImportReloadRequest(
                facility_number="157806098",
                start_date="2023-01-01",
                end_date="2023-12-31",
            ),
        )
        counts = _table_counts(connection)

    assert result.import_executed is False
    assert result.available_before_count == 0
    assert result.available_after_count == 0
    assert result.imported_source_record_count == 0
    assert result.refreshed_source_record_count == 0
    assert result.skipped_non_matching_source_record_count == 6
    assert "No local validated CCLD records matched" in result.deferred_reasons[0]
    assert counts == {"import_batches": 0, "source_records": 0}


def test_ccld_import_reload_rejects_invalid_request_values() -> None:
    with _empty_connection() as connection:
        with pytest.raises(ValueError, match="digits only"):
            import_reload_validated_ccld_records(
                _context(connection),
                CcldImportReloadRequest(facility_number="abc-157806098"),
            )
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            import_reload_validated_ccld_records(
                _context(connection),
                CcldImportReloadRequest(
                    facility_number="157806098",
                    start_date="08/24/2022",
                ),
            )
        with pytest.raises(ValueError, match="End date"):
            import_reload_validated_ccld_records(
                _context(connection),
                CcldImportReloadRequest(
                    facility_number="157806098",
                    start_date="2022-08-27",
                    end_date="2022-08-24",
                ),
            )
        counts = _table_counts(connection)

    assert counts == {"import_batches": 0, "source_records": 0}


def _context(connection: Connection) -> CcldImportReloadContext:
    return ccld_import_reload_context_for_connection(
        connection,
        scope=LOCAL_REVIEWER_UI_SCOPE,
        artifact_paths=(FIXTURE,),
    )


def _empty_connection() -> Connection:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)
    return engine.connect()


def _table_counts(connection: Connection) -> dict[str, int]:
    import_batches = connection.execute(
        select(func.count()).select_from(hosted_import_batches)
    ).scalar_one()
    source_records = connection.execute(
        select(func.count()).select_from(hosted_source_derived_records)
    ).scalar_one()
    return {"import_batches": import_batches, "source_records": source_records}
