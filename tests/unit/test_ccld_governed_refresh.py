from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, cast

import pytest
from sqlalchemy import create_engine, select

from ccld_complaints.connectors.base import SourceDocument
from ccld_complaints.connectors.ccld.facility_reports import CcldFacilityReportsConnector
from ccld_complaints.hosted_app.ccld_source_refresh import (
    FacilityReferenceConfigurationError,
    prepare_ccld_hosted_source_records,
)
from ccld_complaints.hosted_app.facility_reference_preload import (
    FACILITY_REFERENCE_DATASET_SLUG,
    FACILITY_REFERENCE_DATASET_URL,
    hosted_facility_reference_metadata,
    hosted_facility_reference_records,
)
from ccld_complaints.hosted_app.seeded_import import (
    SeededCorpusArtifact,
    hosted_seeded_import_metadata,
    hosted_source_derived_records,
    import_seeded_corpus_artifact,
)
from ccld_complaints.utils.hash import sha256_bytes

RAW_FIXTURE = Path("tests/fixtures/ccld/raw/425802141_inx1_governed_refresh.html")
SOURCE_URL = (
    "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports"
    "?facNum=425802141&inx=1"
)
APPROVED_RESOURCE_ID = "c9df723a-437f-4dcd-be37-ec73ae518bb9"


def test_governed_refresh_fixture_extracts_structured_type_and_activity() -> None:
    normalized = _normalized_fixture()
    facility = cast(dict[str, Any], normalized["facility"])
    complaint = cast(dict[str, Any], normalized["complaint"])
    audits = cast(list[dict[str, Any]], normalized["extraction_audit"])

    assert facility["facility_type"] == "733"
    assert facility["status"] is None
    assert complaint["complaint_control_number"] == "31-CR-20240425094018"
    assert complaint["complaint_received_date"] == "2024-04-25"
    assert complaint["visit_date"] == "2025-11-07"
    assert complaint["first_investigation_activity_date"] == "2025-11-07"
    assert complaint["report_date"] == "2025-11-07"
    assert complaint["date_signed"] == "2025-11-07"
    assert complaint["days_received_to_first_activity"] == 561
    assert complaint["missing_first_activity_date"] is False
    assert complaint["review_delay_over_120_days"] is True
    activity_audit = next(
        row for row in audits if row["field_name"] == "first_investigation_activity_date"
    )
    assert activity_audit["source_section"] == "investigation findings"
    assert "investigative visit" in activity_audit["source_text"]
    facility_type_audit = next(row for row in audits if row["field_name"] == "facility_type")
    assert facility_type_audit["extracted_value"] == "733"
    assert facility_type_audit["source_section"] == "facility details"


def test_structured_visit_is_activity_evidence_but_report_date_alone_is_not(
    tmp_path: Path,
) -> None:
    connector = CcldFacilityReportsConnector(facility_number="425802141")
    visit_html = RAW_FIXTURE.read_text(encoding="utf-8").replace(
        "On 11/07/2025, an evaluator performed an investigative visit at the facility.",
        "No dated narrative activity is stated in this fixture variant.",
    )
    visit_path = tmp_path / "visit_evidence.html"
    report_only_html = visit_html.replace(
        "<tr><td>VISIT DATE:</td><td>11/07/2025</td></tr>",
        "",
    )
    visit_path.write_text(visit_html, encoding="utf-8")
    visit_normalized = _normalize_content(connector, visit_path, visit_html.encode())
    visit_complaint = cast(dict[str, Any], visit_normalized["complaint"])
    assert visit_complaint["visit_date"] == "2025-11-07"
    assert visit_complaint["first_investigation_activity_date"] == "2025-11-07"

    visit_path.write_text(report_only_html, encoding="utf-8")
    report_normalized = _normalize_content(
        connector,
        visit_path,
        report_only_html.encode(),
    )
    report_complaint = cast(dict[str, Any], report_normalized["complaint"])
    assert report_complaint["first_investigation_activity_date"] is None
    assert report_complaint["report_date_used_as_proxy"] is True


def test_approved_reference_owns_master_fields_and_keeps_report_provenance() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)
    hosted_facility_reference_metadata.create_all(engine)
    with engine.begin() as connection:
        _insert_reference(connection)
        prepared = prepare_ccld_hosted_source_records(connection, (_normalized_fixture(),))
        [record] = prepared.records
        facility = cast(dict[str, Any], record["facility"])
        audits = cast(list[dict[str, Any]], record["extraction_audit"])
        refresh = cast(dict[str, Any], record["hosted_refresh"])

    assert facility["facility_type"] == "Children's Residential Facility"
    assert facility["county"] == "Los Angeles"
    assert facility["status"] == "Licensed"
    assert prepared.conflicted_field_count == 1
    report_audit = next(row for row in audits if row["field_name"] == "facility_type")
    reference_audit = next(
        row for row in audits if row["field_name"] == "facility.facility_type"
    )
    assert report_audit["extracted_value"] == "733"
    assert reference_audit["extracted_value"] == "Children's Residential Facility"
    assert "took precedence" in reference_audit["warning"]
    assert all(row.get("extracted_value") != "UNANNOUNCED" for row in audits)
    type_provenance = refresh["facility_field_provenance"]["facility_type"]
    assert type_provenance["source_dataset_slug"] == FACILITY_REFERENCE_DATASET_SLUG
    assert type_provenance["source_field"] == (
        "hosted_facility_reference_records.facility_type"
    )
    assert type_provenance["snapshot_date"] == "2026-06-07"
    assert refresh["facility_reference_conflicts"][0]["source_resource_id"] == (
        "c9df723a-437f-4dcd-be37-ec73ae518bb9"
    )


def test_production_refresh_rejects_fixture_reference_provenance() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)
    hosted_facility_reference_metadata.create_all(engine)
    with engine.begin() as connection:
        _insert_reference(connection, source_file_name="facility_reference_tiny_fixture.csv")
        with pytest.raises(FacilityReferenceConfigurationError, match="fixture, mock, tiny"):
            prepare_ccld_hosted_source_records(connection, (_normalized_fixture(),))


def test_hosted_merge_fills_missing_values_preserves_blanks_and_traces_conflicts() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)
    initial = _normalized_fixture()
    initial_facility = cast(dict[str, Any], initial["facility"])
    initial_complaint = cast(dict[str, Any], initial["complaint"])
    initial_facility.update(facility_type="Report Type", county="Existing County", status=None)
    initial_complaint["first_investigation_activity_date"] = None
    initial_complaint["days_received_to_first_activity"] = None
    improved = _normalized_fixture()
    improved_facility = cast(dict[str, Any], improved["facility"])
    improved_facility.update(facility_type="Reference Type", county=None, status="Licensed")

    with engine.begin() as connection:
        import_seeded_corpus_artifact(connection, _artifact("initial", initial))
        result = import_seeded_corpus_artifact(connection, _artifact("improved", improved))
        facility_row = connection.execute(
            select(hosted_source_derived_records).where(
                hosted_source_derived_records.c.entity_type == "facility"
            )
        ).mappings().one()
        complaint_row = connection.execute(
            select(hosted_source_derived_records).where(
                hosted_source_derived_records.c.entity_type == "complaint"
            )
        ).mappings().one()

    assert facility_row["original_values"]["facility_type"] == "Reference Type"
    assert facility_row["original_values"]["county"] == "Existing County"
    assert facility_row["original_values"]["status"] == "Licensed"
    assert complaint_row["original_values"]["first_investigation_activity_date"] == "2025-11-07"
    assert complaint_row["original_values"]["days_received_to_first_activity"] == 561
    assert result.conflicted_field_count >= 1
    assert facility_row["source_traceability"]["refresh_conflicts"]


def _normalized_fixture() -> dict[str, object]:
    connector = CcldFacilityReportsConnector(facility_number="425802141")
    content = RAW_FIXTURE.read_bytes()
    document = SourceDocument(
        source_url=SOURCE_URL,
        raw_path=RAW_FIXTURE,
        raw_sha256=sha256_bytes(content),
        retrieved_at="2026-07-13T00:00:00+00:00",
        content_type="text/html",
    )
    normalized = connector.normalize(connector.extract(document))
    connector.validate(normalized)
    return normalized


def _normalize_content(
    connector: CcldFacilityReportsConnector,
    path: Path,
    content: bytes,
) -> dict[str, object]:
    document = SourceDocument(
        source_url=SOURCE_URL,
        raw_path=path,
        raw_sha256=sha256_bytes(content),
        retrieved_at="2026-07-13T00:00:00+00:00",
        content_type="text/html",
    )
    return connector.normalize(connector.extract(document))


def _insert_reference(
    connection: Any,
    *,
    source_file_name: str = "24HourResidentialCareforChildren06072026.csv",
) -> None:
    connection.execute(
        hosted_facility_reference_records.insert().values(
            source_resource_id=APPROVED_RESOURCE_ID,
            facility_number="425802141",
            facility_name="GOVERNED REFRESH FIXTURE FACILITY",
            facility_type="Children's Residential Facility",
            program_type="Residential",
            client_served=None,
            licensee_name=None,
            facility_administrator=None,
            telephone=None,
            address=None,
            city=None,
            state="CA",
            zip=None,
            county="Los Angeles",
            regional_office=None,
            capacity=None,
            status="Licensed",
            license_first_date=None,
            closed_date=None,
            all_visit_dates=None,
            inspection_visit_dates=None,
            other_visit_dates=None,
            snapshot_date="2026-06-07",
            source_resource_name="24-Hour Residential Care for Children",
            source_dataset_slug=FACILITY_REFERENCE_DATASET_SLUG,
            source_dataset_url=FACILITY_REFERENCE_DATASET_URL,
            source_accessed_at="2026-06-07T00:00:00+00:00",
            source_file_name=source_file_name,
            original_row_json={"Facility Number": "425802141"},
        )
    )


def _artifact(name: str, normalized: dict[str, object]) -> SeededCorpusArtifact:
    return SeededCorpusArtifact(
        import_batch_id=f"governed-refresh-{name}",
        imported_at="2026-07-13T00:00:00+00:00",
        source_artifact_identity=f"governed-refresh:{name}",
        source_pipeline_version="test",
        validation_status="validated",
        raw_hash_validation_status="validated",
        record_counts={},
        warnings=(),
        errors=(),
        records=(copy.deepcopy(normalized),),
    )
