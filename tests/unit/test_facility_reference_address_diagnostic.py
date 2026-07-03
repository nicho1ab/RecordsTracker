from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Connection

from ccld_complaints.hosted_app.facility_reference_preload import (
    diagnose_facility_reference_address,
    hosted_facility_reference_metadata,
    hosted_facility_reference_records,
)


def test_raw_address_present_with_normalized_address_missing_is_normalization_gap() -> None:
    with _connection() as connection:
        connection.execute(
            hosted_facility_reference_records.insert(),
            _reference_row(
                source_resource_id="source-with-raw-address",
                facility_number="900000001",
                address=None,
                city=None,
                state=None,
                zip_code=None,
                original_row_json={
                    "FAC_NBR": "900000001",
                    "NAME": "RAW ADDRESS HOUSE",
                    "RES_STREET_ADDR": "10 SOURCE WAY",
                    "RES_CITY": "SOURCE CITY",
                    "RES_STATE": "CA",
                    "RES_ZIP_CODE": "90001",
                },
            ),
        )

        [diagnostic] = diagnose_facility_reference_address(connection, "900000001")

    assert diagnostic.conclusion == "normalization_gap"
    assert diagnostic.raw_address_fields["RES_STREET_ADDR"] == "10 SOURCE WAY"


def test_unavailable_raw_and_normalized_address_is_source_missing() -> None:
    with _connection() as connection:
        connection.execute(
            hosted_facility_reference_records.insert(),
            _reference_row(
                source_resource_id="refuge-sunset-source",
                source_resource_name="24-Hour Residential Care for Children",
                facility_number="347006659",
                facility_name="REFUGE SUNSET",
                address="Unavailable",
                city="Unavailable",
                state="Unavailable",
                zip_code="Unavailable",
                regional_office="Sacramento Regional Office",
                original_row_json={
                    "FAC_NBR": "347006659",
                    "NAME": "REFUGE SUNSET",
                    "Facility Address": "Unavailable",
                    "Facility City": "Unavailable",
                    "Facility State": "Unavailable",
                    "Facility Zip": "Unavailable",
                    "COUNTY": "SACRAMENTO",
                    "Facility Capacity": "4",
                    "FAC_DO_DESC": "Sacramento Regional Office",
                },
            ),
        )

        [diagnostic] = diagnose_facility_reference_address(connection, "347006659")

    assert diagnostic.conclusion == "source_missing_address"
    assert diagnostic.normalized_address_fields["address"] == "Unavailable"
    assert diagnostic.raw_address_fields["Facility Address"] == "Unavailable"
    assert diagnostic.raw_address_fields["COUNTY"] == "SACRAMENTO"
    assert "Facility Capacity" not in diagnostic.raw_address_fields


def test_raw_address_missing_with_normalized_address_missing_is_source_missing() -> None:
    with _connection() as connection:
        connection.execute(
            hosted_facility_reference_records.insert(),
            _reference_row(
                source_resource_id="source-without-address",
                facility_number="900000002",
                address=None,
                city=None,
                state=None,
                zip_code=None,
                original_row_json={
                    "FAC_NBR": "900000002",
                    "NAME": "NO ADDRESS HOUSE",
                    "COUNTY": "SACRAMENTO",
                },
            ),
        )

        [diagnostic] = diagnose_facility_reference_address(connection, "900000002")

    assert diagnostic.conclusion == "source_missing_address"
    assert diagnostic.raw_address_fields == {"COUNTY": "SACRAMENTO"}


def test_normalized_address_present_is_has_mapped_address() -> None:
    with _connection() as connection:
        connection.execute(
            hosted_facility_reference_records.insert(),
            _reference_row(
                source_resource_id="source-with-mapped-address",
                facility_number="900000003",
                address="100 MAPPED ST",
                city="MAPPED CITY",
                state="CA",
                zip_code="90003",
                original_row_json={
                    "FAC_NBR": "900000003",
                    "NAME": "MAPPED HOUSE",
                },
            ),
        )

        [diagnostic] = diagnose_facility_reference_address(connection, "900000003")

    assert diagnostic.conclusion == "has_mapped_address"
    assert diagnostic.normalized_address_fields["address"] == "100 MAPPED ST"


def test_duplicate_source_rows_with_different_address_completeness_are_marked() -> None:
    with _connection() as connection:
        connection.execute(
            hosted_facility_reference_records.insert(),
            (
                _reference_row(
                    source_resource_id="less-complete-source",
                    source_resource_name="24-Hour Residential Care for Children",
                    facility_number="347006659",
                    facility_name="REFUGE SUNSET",
                    address=None,
                    city=None,
                    state=None,
                    zip_code=None,
                    original_row_json={
                        "FAC_NBR": "347006659",
                        "NAME": "REFUGE SUNSET",
                        "COUNTY": "SACRAMENTO",
                    },
                ),
                _reference_row(
                    source_resource_id="more-complete-source",
                    source_resource_name="Statewide Facility Master",
                    facility_number="347006659",
                    facility_name="REFUGE SUNSET",
                    address="1 SUNSET WAY",
                    city="SACRAMENTO",
                    state="CA",
                    zip_code="95814",
                    original_row_json={
                        "FAC_NBR": "347006659",
                        "NAME": "REFUGE SUNSET",
                        "RES_STREET_ADDR": "1 SUNSET WAY",
                        "RES_CITY": "SACRAMENTO",
                        "RES_STATE": "CA",
                        "RES_ZIP_CODE": "95814",
                    },
                ),
            ),
        )

        diagnostics = diagnose_facility_reference_address(connection, "347006659")

    conclusions_by_source = {
        diagnostic.source_resource_id: diagnostic.conclusion
        for diagnostic in diagnostics
    }
    assert conclusions_by_source == {
        "less-complete-source": "duplicate_source_variance",
        "more-complete-source": "has_mapped_address",
    }


def _connection() -> Connection:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_facility_reference_metadata.create_all(engine)
    return engine.connect()


def _reference_row(
    *,
    source_resource_id: str,
    facility_number: str,
    address: str | None,
    city: str | None,
    state: str | None,
    zip_code: str | None,
    original_row_json: dict[str, str],
    facility_name: str = "DIAGNOSTIC FACILITY",
    source_resource_name: str = "Diagnostic Source",
    regional_office: str | None = None,
) -> dict[str, Any]:
    return {
        "source_resource_id": source_resource_id,
        "facility_number": facility_number,
        "facility_name": facility_name,
        "facility_type": "SHORT TERM RESIDENTIAL THERAPEUTIC PROGRAM",
        "program_type": "CHILDREN'S RESIDENTIAL",
        "licensee_name": None,
        "facility_administrator": None,
        "telephone": None,
        "address": address,
        "city": city,
        "state": state,
        "zip": zip_code,
        "county": "SACRAMENTO",
        "regional_office": regional_office,
        "capacity": 6,
        "status": "LICENSED",
        "license_first_date": None,
        "closed_date": None,
        "snapshot_date": "2026-06-07",
        "source_resource_name": source_resource_name,
        "source_dataset_slug": "ccl-facilities",
        "source_dataset_url": "public-ccl-facilities",
        "source_accessed_at": "2026-07-01T12:00:00+00:00",
        "source_file_name": f"{source_resource_id}.csv",
        "original_row_json": original_row_json,
    }
