from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import cast

import pytest
from sqlalchemy import create_engine, text

from ccld_complaints.connectors.base import SourceDocument
from ccld_complaints.connectors.ccld.facility_reports import (
    FIELD_STATUS_ABSENT,
    FIELD_STATUS_BLANK,
    FIELD_STATUS_COVERAGE_UNAVAILABLE,
    FIELD_STATUS_EXTRACTED,
    FIELD_STATUS_FAILED,
    CcldFacilityReportsConnector,
    FieldEvidence,
    _first_investigation_activity,
    _html_table_cells,
    _integer_field_evidence,
    _regional_office_evidence,
    _table_label_evidence,
)
from ccld_complaints.extraction_gap_evidence import (
    OUTPUT_FILES,
    EvidenceExecutionError,
    run_evidence,
    unavailable_artifact_status,
)
from ccld_complaints.utils.hash import sha256_bytes

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_FIXTURE = REPO_ROOT / "tests/fixtures/ccld/raw/157806098_inx3.html"
SOURCE_URL = (
    "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports"
    "?facNum=157806098&inx=3"
)


def test_governed_fixture_extracts_target_complaint_event_and_facility_fields() -> None:
    extracted, normalized = _extract_fixture()
    field_evidence = cast(dict[str, FieldEvidence], extracted["_field_evidence"])
    events = cast(list[dict[str, object]], normalized["events"])
    complaint = cast(dict[str, object], normalized["complaint"])
    facility = cast(dict[str, object], normalized["facility"])

    assert complaint["first_investigation_activity_date"] == "2022-04-14"
    assert events == [
        {
            "event_id": "ccld-complaint-32-CR-20220407124448-event-1",
            "complaint_id": "ccld-complaint-32-CR-20220407124448",
            "event_date": "2022-04-14",
            "event_type": "investigation_activity",
            "event_text": cast(list[dict[str, object]], extracted["events"])[0][
                "event_text"
            ],
            "extracted_from_section": "investigation findings",
            "extraction_confidence": 1.0,
        }
    ]
    assert facility["capacity"] == 48
    assert facility["regional_office"] == "CCLD Regional Office"
    assert field_evidence["facility_address"].status == FIELD_STATUS_BLANK
    assert field_evidence["facility_city"].status == FIELD_STATUS_BLANK
    assert field_evidence["facility_capacity"].status == FIELD_STATUS_EXTRACTED
    assert field_evidence["regional_office"].status == FIELD_STATUS_EXTRACTED


def test_target_extraction_audits_preserve_section_text_and_document_link() -> None:
    _extracted, normalized = _extract_fixture()
    audits = cast(list[dict[str, object]], normalized["extraction_audit"])
    target_fields = {
        "first_investigation_activity_date",
        "event.event_date",
        "event.event_text",
        "event.event_type",
        "facility_address",
        "facility_capacity",
        "facility_city",
        "regional_office",
    }
    target_audits = [row for row in audits if row["field_name"] in target_fields]

    assert len(target_audits) == len(target_fields)
    assert {row["document_id"] for row in target_audits} == {
        "ccld-157806098-inx-3"
    }
    assert all(row["source_section"] for row in target_audits)
    assert all(row["source_text"] for row in target_audits)
    blank_audits = {
        str(row["field_name"]): row
        for row in target_audits
        if row["field_name"] in {"facility_address", "facility_city"}
    }
    assert blank_audits["facility_address"]["extracted_value"] is None
    assert blank_audits["facility_city"]["extracted_value"] is None
    assert {row["warning"] for row in blank_audits.values()} == {
        "Source element is present but blank."
    }


@pytest.mark.parametrize(
    ("lines", "expected_status"),
    [
        (
            [
                "INVESTIGATION FINDINGS:",
                "LPA interviewed facility staff on 13/40/2022.",
            ],
            FIELD_STATUS_FAILED,
        ),
        (["INVESTIGATION FINDINGS:", "No dated activity is stated."], FIELD_STATUS_ABSENT),
        (["ALLEGATION(S):", "A source allegation."], FIELD_STATUS_ABSENT),
    ],
)
def test_first_activity_date_malformed_and_missing_states_are_explicit(
    lines: list[str], expected_status: str
) -> None:
    event, evidence = _first_investigation_activity(lines)

    assert event is None
    assert evidence.status == expected_status
    assert evidence.source_value is None


def test_present_blank_is_distinct_from_unavailable_source_coverage(tmp_path: Path) -> None:
    extracted, _normalized = _extract_fixture()
    field_evidence = cast(dict[str, FieldEvidence], extracted["_field_evidence"])

    assert field_evidence["facility_address"].status == FIELD_STATUS_BLANK
    assert unavailable_artifact_status(None) == FIELD_STATUS_COVERAGE_UNAVAILABLE
    assert unavailable_artifact_status(tmp_path / "missing.html") == (
        FIELD_STATUS_COVERAGE_UNAVAILABLE
    )
    assert FIELD_STATUS_BLANK != FIELD_STATUS_COVERAGE_UNAVAILABLE


def test_facility_field_states_and_repeated_header_are_deterministic() -> None:
    absent_capacity = _integer_field_evidence(
        _table_label_evidence([], "CAPACITY", "facility details")
    )
    malformed_capacity = _integer_field_evidence(
        _table_label_evidence(
            ["CAPACITY:", "not reported"], "CAPACITY", "facility details"
        )
    )
    cells = _html_table_cells(RAW_FIXTURE.read_text(encoding="utf-8"))
    regional_office_evidence = _regional_office_evidence(cells)

    assert absent_capacity.status == FIELD_STATUS_ABSENT
    assert absent_capacity.source_value is None
    assert malformed_capacity.status == FIELD_STATUS_FAILED
    assert malformed_capacity.source_value is None
    assert malformed_capacity.source_text == "CAPACITY: not reported"
    assert sum("CCLD Regional Office" in cell for cell in cells) == 2
    assert regional_office_evidence.status == FIELD_STATUS_EXTRACTED
    assert regional_office_evidence.source_value == "CCLD Regional Office"
    assert regional_office_evidence == _regional_office_evidence(cells)


def test_allegation_category_is_not_inferred_from_allegation_text() -> None:
    _extracted, normalized = _extract_fixture()
    allegations = cast(list[dict[str, object]], normalized["allegations"])

    assert allegations
    assert {row["allegation_category"] for row in allegations} == {None}


def test_local_evidence_is_deterministic_complete_and_aggregate_safe(
    tmp_path: Path,
) -> None:
    first_output = tmp_path / "first"
    second_output = tmp_path / "second"

    first_manifest = run_evidence(
        mode="local", output_dir=first_output, repo_root=REPO_ROOT
    )
    second_manifest = run_evidence(
        mode="local", output_dir=second_output, repo_root=REPO_ROOT
    )

    assert all(cast(dict[str, bool], first_manifest["assertions"]).values())
    assert first_manifest == second_manifest
    assert set(path.name for path in first_output.iterdir()) == set(OUTPUT_FILES)
    for file_name in OUTPUT_FILES:
        assert (first_output / file_name).read_bytes() == (
            second_output / file_name
        ).read_bytes()
    combined_output = "\n".join(
        (first_output / file_name).read_text(encoding="utf-8")
        for file_name in OUTPUT_FILES
    )
    assert str(REPO_ROOT) not in combined_output
    assert "During the course of the investigation" not in combined_output
    assert "postgresql://" not in combined_output
    assert "900000001" not in combined_output
    assert "900000002" not in combined_output
    with (first_output / "field-results.csv").open(
        "r", encoding="utf-8", newline=""
    ) as csv_file:
        rows = list(csv.DictReader(csv_file))
    assert [row["field_id"] for row in rows] == [
        "complaint.first_investigation_activity_date",
        "event.event_date",
        "event.event_text",
        "event.event_type",
        "facility_address",
        "facility_capacity",
        "facility_city",
        "regional_office",
        "extraction_audit.source_section",
        "extraction_audit.source_text",
        "allegation.allegation_category",
    ]


def test_runtime_adapter_reports_population_separately_from_capability(
    tmp_path: Path,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE hosted_source_derived_records (
                    entity_type TEXT NOT NULL,
                    original_values TEXT NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO hosted_source_derived_records (entity_type, original_values)
                VALUES
                    ('complaint', :complaint),
                    ('facility', :facility),
                    ('event', :event),
                    ('extraction_audit', :audit),
                    ('allegation', :allegation)
                """
            ),
            {
                "complaint": json.dumps(
                    {"first_investigation_activity_date": "2022-04-14"}
                ),
                "facility": json.dumps(
                    {"capacity": 48, "regional_office": "Regional office"}
                ),
                "event": json.dumps(
                    {
                        "event_date": "2022-04-14",
                        "event_text": "bounded event evidence",
                        "event_type": "investigation_activity",
                    }
                ),
                "audit": json.dumps(
                    {"source_section": "section", "source_text": "bounded evidence"}
                ),
                "allegation": json.dumps({"allegation_category": None}),
            },
        )
        manifest = run_evidence(
            mode="runtime",
            output_dir=tmp_path / "runtime",
            repo_root=REPO_ROOT,
            runtime_connection=connection,
        )

    population = cast(dict[str, object], manifest["runtime_population"])
    rows = cast(list[dict[str, object]], population["fields"])
    rows_by_field = {str(row["field_id"]): row for row in rows}
    assert population["status"] == "inspected aggregate-only"
    assert rows_by_field["event.event_text"]["populated_count"] == 1
    assert rows_by_field["facility_address"]["populated_count"] == 0
    assert rows_by_field["allegation.allegation_category"]["populated_count"] == 0
    assert cast(dict[str, bool], manifest["assertions"])[
        "runtime_population_reported_separately"
    ]


def test_runtime_mode_never_falls_back_to_local_or_synthetic_records(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "runtime"

    with pytest.raises(
        EvidenceExecutionError,
        match="Runtime evidence requires a configured PostgreSQL database",
    ):
        run_evidence(
            mode="runtime",
            output_dir=output_dir,
            repo_root=REPO_ROOT,
            environ={},
        )

    assert not output_dir.exists()


def _extract_fixture() -> tuple[dict[str, object], dict[str, object]]:
    content = RAW_FIXTURE.read_bytes()
    document = SourceDocument(
        source_url=SOURCE_URL,
        raw_path=RAW_FIXTURE,
        raw_sha256=sha256_bytes(content),
        retrieved_at="2026-06-10T00:00:00+00:00",
        content_type="text/html",
    )
    connector = CcldFacilityReportsConnector()
    extracted = connector.extract(document)
    normalized = connector.normalize(extracted)
    connector.validate(normalized)
    return extracted, normalized
