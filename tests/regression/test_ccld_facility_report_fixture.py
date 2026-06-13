from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, cast

from ccld_complaints.connectors.base import SourceDocument, SourceDocumentCandidate
from ccld_complaints.connectors.ccld import CcldFacilityReportsConnector
from ccld_complaints.connectors.ccld.facility_reports import (
    _allegation_text,
    ingest_facility_reports_for_facility,
)
from ccld_complaints.utils.hash import sha256_bytes

FIXTURE_URL = "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=157806098&inx=3"
NUMBERED_ALLEGATIONS_FIXTURE_URL = (
    "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=157806098&inx=40"
)
INLINE_RECEIVED_DATE_FIXTURE_URL = (
    "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=157806098&inx=41"
)
MISSING_VISIT_DATE_FIXTURE_URL = (
    "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=157806098&inx=42"
)
LABELED_FINDING_FIXTURE_URL = (
    "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=157806098&inx=43"
)
WRAPPED_ALLEGATION_FIXTURE_URL = (
    "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=157806098&inx=44"
)
SPLIT_FINDING_FIXTURE_URL = (
    "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=157806098&inx=45"
)
ALLEGATION_HEADING_VARIANT_FIXTURE_URL = (
    "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=157806098&inx=46"
)
INVESTIGATION_FINDING_HEADING_FIXTURE_URL = (
    "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=157806098&inx=47"
)
ALLEGATION_HEADING_NO_COLON_FIXTURE_URL = (
    "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=157806098&inx=48"
)
PUNCTUATED_FINDING_FIXTURE_URL = (
    "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=157806098&inx=49"
)
DASHED_FINDING_LABEL_FIXTURE_URL = (
    "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=157806098&inx=50"
)
WAS_RECEIVED_DATE_FIXTURE_URL = (
    "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=157806098&inx=51"
)
SPLIT_REPORT_DATE_FIXTURE_URL = (
    "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=157806098&inx=52"
)
SPLIT_DATE_SIGNED_FIXTURE_URL = (
    "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=157806098&inx=53"
)
SPLIT_VISIT_DATE_FIXTURE_URL = (
    "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=157806098&inx=54"
)
SPLIT_COMPLAINT_CONTROL_FIXTURE_URL = (
    "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=157806098&inx=55"
)
SPLIT_FACILITY_NAME_FIXTURE_URL = (
    "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=157806098&inx=56"
)
SPLIT_FACILITY_NUMBER_FIXTURE_URL = (
    "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=157806098&inx=57"
)
REPORT_TYPE_CASE_FIXTURE_URL = (
    "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=157806098&inx=58"
)
SPACED_ALLEGATION_HEADING_FIXTURE_URL = (
    "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=157806098&inx=59"
)
RAW_FIXTURE = Path("tests/fixtures/ccld/raw/157806098_inx3.html")
NUMBERED_ALLEGATIONS_RAW_FIXTURE = Path(
    "tests/fixtures/ccld/raw/157806098_inx40_numbered_allegations.html"
)
INLINE_RECEIVED_DATE_RAW_FIXTURE = Path(
    "tests/fixtures/ccld/raw/157806098_inx41_inline_received_date.html"
)
MISSING_VISIT_DATE_RAW_FIXTURE = Path(
    "tests/fixtures/ccld/raw/157806098_inx42_missing_visit_date.html"
)
LABELED_FINDING_RAW_FIXTURE = Path(
    "tests/fixtures/ccld/raw/157806098_inx43_labeled_finding.html"
)
WRAPPED_ALLEGATION_RAW_FIXTURE = Path(
    "tests/fixtures/ccld/raw/157806098_inx44_wrapped_allegation.html"
)
SPLIT_FINDING_RAW_FIXTURE = Path(
    "tests/fixtures/ccld/raw/157806098_inx45_split_finding.html"
)
ALLEGATION_HEADING_VARIANT_RAW_FIXTURE = Path(
    "tests/fixtures/ccld/raw/157806098_inx46_allegations_heading.html"
)
INVESTIGATION_FINDING_HEADING_RAW_FIXTURE = Path(
    "tests/fixtures/ccld/raw/157806098_inx47_investigation_finding_heading.html"
)
ALLEGATION_HEADING_NO_COLON_RAW_FIXTURE = Path(
    "tests/fixtures/ccld/raw/157806098_inx48_allegations_heading_no_colon.html"
)
PUNCTUATED_FINDING_RAW_FIXTURE = Path(
    "tests/fixtures/ccld/raw/157806098_inx49_punctuated_finding.html"
)
DASHED_FINDING_LABEL_RAW_FIXTURE = Path(
    "tests/fixtures/ccld/raw/157806098_inx50_dashed_finding_label.html"
)
WAS_RECEIVED_DATE_RAW_FIXTURE = Path(
    "tests/fixtures/ccld/raw/157806098_inx51_was_received_date.html"
)
SPLIT_REPORT_DATE_RAW_FIXTURE = Path(
    "tests/fixtures/ccld/raw/157806098_inx52_split_report_date.html"
)
SPLIT_DATE_SIGNED_RAW_FIXTURE = Path(
    "tests/fixtures/ccld/raw/157806098_inx53_split_date_signed.html"
)
SPLIT_VISIT_DATE_RAW_FIXTURE = Path(
    "tests/fixtures/ccld/raw/157806098_inx54_split_visit_date.html"
)
SPLIT_COMPLAINT_CONTROL_RAW_FIXTURE = Path(
    "tests/fixtures/ccld/raw/157806098_inx55_split_complaint_control.html"
)
SPLIT_FACILITY_NAME_RAW_FIXTURE = Path(
    "tests/fixtures/ccld/raw/157806098_inx56_split_facility_name.html"
)
SPLIT_FACILITY_NUMBER_RAW_FIXTURE = Path(
    "tests/fixtures/ccld/raw/157806098_inx57_split_facility_number.html"
)
REPORT_TYPE_CASE_RAW_FIXTURE = Path(
    "tests/fixtures/ccld/raw/157806098_inx58_report_type_case.html"
)
SPACED_ALLEGATION_HEADING_RAW_FIXTURE = Path(
    "tests/fixtures/ccld/raw/157806098_inx59_spaced_allegation_heading.html"
)
RAW_DETAIL_FIXTURE = Path("tests/fixtures/ccld/raw/157806098_facility_detail.html")
EXPECTED_FIXTURE = Path("tests/fixtures/ccld/expected/157806098_inx3.json")
NUMBERED_ALLEGATIONS_EXPECTED_FIXTURE = Path(
    "tests/fixtures/ccld/expected/157806098_inx40_numbered_allegations.json"
)
INLINE_RECEIVED_DATE_EXPECTED_FIXTURE = Path(
    "tests/fixtures/ccld/expected/157806098_inx41_inline_received_date.json"
)
MISSING_VISIT_DATE_EXPECTED_FIXTURE = Path(
    "tests/fixtures/ccld/expected/157806098_inx42_missing_visit_date.json"
)
LABELED_FINDING_EXPECTED_FIXTURE = Path(
    "tests/fixtures/ccld/expected/157806098_inx43_labeled_finding.json"
)
WRAPPED_ALLEGATION_EXPECTED_FIXTURE = Path(
    "tests/fixtures/ccld/expected/157806098_inx44_wrapped_allegation.json"
)
SPLIT_FINDING_EXPECTED_FIXTURE = Path(
    "tests/fixtures/ccld/expected/157806098_inx45_split_finding.json"
)
ALLEGATION_HEADING_VARIANT_EXPECTED_FIXTURE = Path(
    "tests/fixtures/ccld/expected/157806098_inx46_allegations_heading.json"
)
INVESTIGATION_FINDING_HEADING_EXPECTED_FIXTURE = Path(
    "tests/fixtures/ccld/expected/157806098_inx47_investigation_finding_heading.json"
)
ALLEGATION_HEADING_NO_COLON_EXPECTED_FIXTURE = Path(
    "tests/fixtures/ccld/expected/157806098_inx48_allegations_heading_no_colon.json"
)
PUNCTUATED_FINDING_EXPECTED_FIXTURE = Path(
    "tests/fixtures/ccld/expected/157806098_inx49_punctuated_finding.json"
)
DASHED_FINDING_LABEL_EXPECTED_FIXTURE = Path(
    "tests/fixtures/ccld/expected/157806098_inx50_dashed_finding_label.json"
)
WAS_RECEIVED_DATE_EXPECTED_FIXTURE = Path(
    "tests/fixtures/ccld/expected/157806098_inx51_was_received_date.json"
)
SPLIT_REPORT_DATE_EXPECTED_FIXTURE = Path(
    "tests/fixtures/ccld/expected/157806098_inx52_split_report_date.json"
)
SPLIT_DATE_SIGNED_EXPECTED_FIXTURE = Path(
    "tests/fixtures/ccld/expected/157806098_inx53_split_date_signed.json"
)
SPLIT_VISIT_DATE_EXPECTED_FIXTURE = Path(
    "tests/fixtures/ccld/expected/157806098_inx54_split_visit_date.json"
)
SPLIT_COMPLAINT_CONTROL_EXPECTED_FIXTURE = Path(
    "tests/fixtures/ccld/expected/157806098_inx55_split_complaint_control.json"
)
SPLIT_FACILITY_NAME_EXPECTED_FIXTURE = Path(
    "tests/fixtures/ccld/expected/157806098_inx56_split_facility_name.json"
)
SPLIT_FACILITY_NUMBER_EXPECTED_FIXTURE = Path(
    "tests/fixtures/ccld/expected/157806098_inx57_split_facility_number.json"
)
REPORT_TYPE_CASE_EXPECTED_FIXTURE = Path(
    "tests/fixtures/ccld/expected/157806098_inx58_report_type_case.json"
)
SPACED_ALLEGATION_HEADING_EXPECTED_FIXTURE = Path(
    "tests/fixtures/ccld/expected/157806098_inx59_spaced_allegation_heading.json"
)
RETRIEVED_AT = "2026-06-10T00:00:00+00:00"
NUMBERED_ALLEGATIONS_RETRIEVED_AT = "2026-06-12T00:00:00+00:00"
INLINE_RECEIVED_DATE_RETRIEVED_AT = "2026-06-12T00:00:00+00:00"
MISSING_VISIT_DATE_RETRIEVED_AT = "2026-06-12T00:00:00+00:00"
LABELED_FINDING_RETRIEVED_AT = "2026-06-12T00:00:00+00:00"
WRAPPED_ALLEGATION_RETRIEVED_AT = "2026-06-12T00:00:00+00:00"
SPLIT_FINDING_RETRIEVED_AT = "2026-06-12T00:00:00+00:00"
ALLEGATION_HEADING_VARIANT_RETRIEVED_AT = "2026-06-12T00:00:00+00:00"
INVESTIGATION_FINDING_HEADING_RETRIEVED_AT = "2026-06-12T00:00:00+00:00"
ALLEGATION_HEADING_NO_COLON_RETRIEVED_AT = "2026-06-12T00:00:00+00:00"
PUNCTUATED_FINDING_RETRIEVED_AT = "2026-06-12T00:00:00+00:00"
DASHED_FINDING_LABEL_RETRIEVED_AT = "2026-06-12T00:00:00+00:00"
WAS_RECEIVED_DATE_RETRIEVED_AT = "2026-06-12T00:00:00+00:00"
SPLIT_REPORT_DATE_RETRIEVED_AT = "2026-06-12T00:00:00+00:00"
SPLIT_DATE_SIGNED_RETRIEVED_AT = "2026-06-12T00:00:00+00:00"
SPLIT_VISIT_DATE_RETRIEVED_AT = "2026-06-12T00:00:00+00:00"
SPLIT_COMPLAINT_CONTROL_RETRIEVED_AT = "2026-06-12T00:00:00+00:00"
SPLIT_FACILITY_NAME_RETRIEVED_AT = "2026-06-12T00:00:00+00:00"
SPLIT_FACILITY_NUMBER_RETRIEVED_AT = "2026-06-12T00:00:00+00:00"
REPORT_TYPE_CASE_RETRIEVED_AT = "2026-06-12T00:00:00+00:00"
SPACED_ALLEGATION_HEADING_RETRIEVED_AT = "2026-06-12T00:00:00+00:00"


def test_ccld_facility_detail_discovers_report_candidates_from_fixture() -> None:
    connector = CcldFacilityReportsConnector()
    candidates = connector.discover(
        facility_detail_html=RAW_DETAIL_FIXTURE.read_text(encoding="utf-8"),
        discovered_at=RETRIEVED_AT,
    )

    assert [candidate.report_index for candidate in candidates] == [
        39,
        37,
        29,
        38,
        26,
        28,
        27,
        25,
        24,
        22,
        23,
        21,
        20,
        36,
        19,
        18,
        16,
        17,
        6,
        35,
        15,
        14,
        13,
        5,
        12,
        4,
        11,
        34,
        10,
        3,
        33,
        8,
        9,
        2,
        32,
        31,
        1,
        0,
        7,
        30,
    ]
    assert sorted(candidate.report_index for candidate in candidates) == list(range(40))
    assert len({candidate.source_url for candidate in candidates}) == len(candidates)

    first_candidate = candidates[0]
    assert first_candidate.source_name == "ccld"
    assert first_candidate.facility_number == "157806098"
    assert first_candidate.report_index == 39
    assert first_candidate.source_url == (
        "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports"
        "?facNum=157806098&inx=39"
    )
    assert first_candidate.discovered_report_date == "2026-05-04"
    assert first_candidate.discovered_at == RETRIEVED_AT

    report_three = [candidate for candidate in candidates if candidate.report_index == 3]
    assert len(report_three) == 1
    assert report_three[0].discovered_report_date == "2022-08-24"


def test_ccld_facility_report_extracts_required_fields() -> None:
    extracted = _extract_fixture()

    assert extracted["facility_number"] == "157806098"
    assert extracted["facility_name"] == "A. MIRIAM JAMISON CHILDREN'S CENTER"
    assert extracted["report_type"] == "COMPLAINT INVESTIGATION REPORT"
    assert extracted["report_date"] == "2022-08-24"
    assert extracted["date_signed"] == "2022-08-26"
    assert extracted["complaint_received_date"] == "2022-04-07"
    assert extracted["complaint_control_number"] == "32-CR-20220407124448"
    assert extracted["allegations"] == [
        "Facility clients are being mistreated while in care",
        "Facility staff do not provide adequate supervision to the facility clients",
    ]
    assert extracted["finding"] == "Unsubstantiated"
    assert extracted["visit_date"] == "2022-08-24"
    assert extracted["days_received_to_first_activity"] is None
    assert extracted["days_received_to_visit"] == 139
    assert extracted["days_received_to_report"] == 139
    assert extracted["days_report_to_signed"] == 2
    assert extracted["review_delay_over_30_days"] is True
    assert extracted["review_delay_over_60_days"] is True
    assert extracted["review_delay_over_90_days"] is True
    assert extracted["review_delay_over_120_days"] is True
    assert extracted["missing_first_activity_date"] is True
    assert extracted["report_date_used_as_proxy"] is False


def test_ccld_facility_report_normalizes_to_expected_fixture() -> None:
    connector = CcldFacilityReportsConnector()
    normalized = connector.normalize(_extract_fixture())
    expected = json.loads(EXPECTED_FIXTURE.read_text(encoding="utf-8"))

    assert _without_audit(normalized) == expected


def test_ccld_facility_report_strips_numbered_allegation_prefixes() -> None:
    connector = CcldFacilityReportsConnector()
    normalized = connector.normalize(_extract_numbered_allegations_fixture())
    expected = json.loads(NUMBERED_ALLEGATIONS_EXPECTED_FIXTURE.read_text(encoding="utf-8"))

    assert _without_audit(normalized) == expected


def test_ccld_facility_report_extracts_inline_complaint_received_date() -> None:
    connector = CcldFacilityReportsConnector()
    normalized = connector.normalize(_extract_inline_received_date_fixture())
    expected = json.loads(INLINE_RECEIVED_DATE_EXPECTED_FIXTURE.read_text(encoding="utf-8"))

    assert _without_audit(normalized) == expected


def test_ccld_facility_report_uses_report_date_proxy_when_visit_date_missing() -> None:
    connector = CcldFacilityReportsConnector()
    normalized = connector.normalize(_extract_missing_visit_date_fixture())
    expected = json.loads(MISSING_VISIT_DATE_EXPECTED_FIXTURE.read_text(encoding="utf-8"))

    assert _without_audit(normalized) == expected


def test_ccld_facility_report_extracts_labeled_finding_value() -> None:
    connector = CcldFacilityReportsConnector()
    normalized = connector.normalize(_extract_labeled_finding_fixture())
    expected = json.loads(LABELED_FINDING_EXPECTED_FIXTURE.read_text(encoding="utf-8"))

    assert _without_audit(normalized) == expected


def test_ccld_facility_report_merges_wrapped_allegation_continuation() -> None:
    connector = CcldFacilityReportsConnector()
    normalized = connector.normalize(_extract_wrapped_allegation_fixture())
    expected = json.loads(WRAPPED_ALLEGATION_EXPECTED_FIXTURE.read_text(encoding="utf-8"))

    assert _without_audit(normalized) == expected


def test_ccld_facility_report_extracts_split_finding_label_value() -> None:
    connector = CcldFacilityReportsConnector()
    normalized = connector.normalize(_extract_split_finding_fixture())
    expected = json.loads(SPLIT_FINDING_EXPECTED_FIXTURE.read_text(encoding="utf-8"))

    assert _without_audit(normalized) == expected


def test_ccld_facility_report_extracts_allegations_heading_variant() -> None:
    connector = CcldFacilityReportsConnector()
    normalized = connector.normalize(_extract_allegation_heading_variant_fixture())
    expected = json.loads(
        ALLEGATION_HEADING_VARIANT_EXPECTED_FIXTURE.read_text(encoding="utf-8")
    )

    assert _without_audit(normalized) == expected


def test_ccld_facility_report_extracts_investigation_finding_heading_variant() -> None:
    connector = CcldFacilityReportsConnector()
    normalized = connector.normalize(_extract_investigation_finding_heading_fixture())
    expected = json.loads(
        INVESTIGATION_FINDING_HEADING_EXPECTED_FIXTURE.read_text(encoding="utf-8")
    )

    assert _without_audit(normalized) == expected


def test_ccld_facility_report_extracts_allegation_heading_without_colon() -> None:
    connector = CcldFacilityReportsConnector()
    normalized = connector.normalize(_extract_allegation_heading_no_colon_fixture())
    expected = json.loads(ALLEGATION_HEADING_NO_COLON_EXPECTED_FIXTURE.read_text(encoding="utf-8"))

    assert _without_audit(normalized) == expected


def test_ccld_facility_report_extracts_punctuated_finding_value() -> None:
    connector = CcldFacilityReportsConnector()
    normalized = connector.normalize(_extract_punctuated_finding_fixture())
    expected = json.loads(PUNCTUATED_FINDING_EXPECTED_FIXTURE.read_text(encoding="utf-8"))

    assert _without_audit(normalized) == expected


def test_ccld_facility_report_extracts_dashed_finding_label() -> None:
    connector = CcldFacilityReportsConnector()
    normalized = connector.normalize(_extract_dashed_finding_label_fixture())
    expected = json.loads(DASHED_FINDING_LABEL_EXPECTED_FIXTURE.read_text(encoding="utf-8"))

    assert _without_audit(normalized) == expected


def test_ccld_facility_report_extracts_was_received_complaint_date() -> None:
    connector = CcldFacilityReportsConnector()
    normalized = connector.normalize(_extract_was_received_date_fixture())
    expected = json.loads(WAS_RECEIVED_DATE_EXPECTED_FIXTURE.read_text(encoding="utf-8"))

    assert _without_audit(normalized) == expected


def test_ccld_facility_report_extracts_split_report_date_label() -> None:
    connector = CcldFacilityReportsConnector()
    normalized = connector.normalize(_extract_split_report_date_fixture())
    expected = json.loads(SPLIT_REPORT_DATE_EXPECTED_FIXTURE.read_text(encoding="utf-8"))

    assert _without_audit(normalized) == expected


def test_ccld_facility_report_extracts_split_date_signed_label() -> None:
    connector = CcldFacilityReportsConnector()
    normalized = connector.normalize(_extract_split_date_signed_fixture())
    expected = json.loads(SPLIT_DATE_SIGNED_EXPECTED_FIXTURE.read_text(encoding="utf-8"))

    assert _without_audit(normalized) == expected


def test_ccld_facility_report_extracts_split_visit_date_label() -> None:
    connector = CcldFacilityReportsConnector()
    normalized = connector.normalize(_extract_split_visit_date_fixture())
    expected = json.loads(SPLIT_VISIT_DATE_EXPECTED_FIXTURE.read_text(encoding="utf-8"))

    assert _without_audit(normalized) == expected


def test_ccld_facility_report_extracts_split_complaint_control_label() -> None:
    connector = CcldFacilityReportsConnector()
    normalized = connector.normalize(_extract_split_complaint_control_fixture())
    expected = json.loads(
        SPLIT_COMPLAINT_CONTROL_EXPECTED_FIXTURE.read_text(encoding="utf-8")
    )

    assert _without_audit(normalized) == expected


def test_ccld_facility_report_extracts_split_facility_name_label() -> None:
    connector = CcldFacilityReportsConnector()
    normalized = connector.normalize(_extract_split_facility_name_fixture())
    expected = json.loads(SPLIT_FACILITY_NAME_EXPECTED_FIXTURE.read_text(encoding="utf-8"))

    assert _without_audit(normalized) == expected


def test_ccld_facility_report_extracts_split_facility_number_label() -> None:
    connector = CcldFacilityReportsConnector()
    normalized = connector.normalize(_extract_split_facility_number_fixture())
    expected = json.loads(
        SPLIT_FACILITY_NUMBER_EXPECTED_FIXTURE.read_text(encoding="utf-8")
    )

    assert _without_audit(normalized) == expected


def test_ccld_facility_report_extracts_report_type_case_variant() -> None:
    connector = CcldFacilityReportsConnector()
    normalized = connector.normalize(_extract_report_type_case_fixture())
    expected = json.loads(REPORT_TYPE_CASE_EXPECTED_FIXTURE.read_text(encoding="utf-8"))

    assert _without_audit(normalized) == expected


def test_ccld_facility_report_extracts_spaced_allegation_heading() -> None:
    connector = CcldFacilityReportsConnector()
    normalized = connector.normalize(_extract_spaced_allegation_heading_fixture())
    expected = json.loads(
        SPACED_ALLEGATION_HEADING_EXPECTED_FIXTURE.read_text(encoding="utf-8")
    )

    assert _without_audit(normalized) == expected


def test_ccld_allegation_cleanup_handles_numbered_prefix_variants() -> None:
    assert _allegation_text("1. Facility did not follow procedures") == (
        "Facility did not follow procedures"
    )
    assert _allegation_text("2) Facility staff did not supervise") == (
        "Facility staff did not supervise"
    )
    assert _allegation_text("1 - Facility records were incomplete") == (
        "Facility records were incomplete"
    )
    assert _allegation_text("01: Facility medication log was missing") == (
        "Facility medication log was missing"
    )
    assert _allegation_text("ALLEGATION 1: Facility did not report an incident") == (
        "Facility did not report an incident"
    )
    assert _allegation_text("3") is None


def test_ccld_facility_report_validates_normalized_records() -> None:
    connector = CcldFacilityReportsConnector()
    normalized = connector.normalize(_extract_fixture())

    connector.validate(normalized)


def test_ccld_facility_ingestion_loads_existing_report_fixture() -> None:
    result = ingest_facility_reports_for_facility(
        facility_detail_html=RAW_DETAIL_FIXTURE.read_text(encoding="utf-8"),
        discovered_at=RETRIEVED_AT,
        load_document=_load_existing_report_fixture,
    )

    assert len(result.candidates) == 40
    assert len(result.records) == 1
    assert len(result.failures) == 39
    assert result.records[0]["complaint"] == json.loads(
        EXPECTED_FIXTURE.read_text(encoding="utf-8")
    )["complaint"]


def test_ccld_facility_ingestion_records_missing_report_content() -> None:
    result = ingest_facility_reports_for_facility(
        facility_detail_html=RAW_DETAIL_FIXTURE.read_text(encoding="utf-8"),
        discovered_at=RETRIEVED_AT,
        load_document=lambda _candidate: None,
    )

    assert len(result.candidates) == 40
    assert result.records == []
    assert len(result.failures) == 40
    assert {failure.stage for failure in result.failures} == {"load"}
    assert {failure.error_type for failure in result.failures} == {"ReportContentNotFound"}


def test_ccld_facility_ingestion_preserves_source_traceability() -> None:
    result = ingest_facility_reports_for_facility(
        facility_detail_html=RAW_DETAIL_FIXTURE.read_text(encoding="utf-8"),
        discovered_at=RETRIEVED_AT,
        load_document=_load_existing_report_fixture,
    )

    source_document = cast(dict[str, object], result.records[0]["source_document"])

    assert source_document["source_url"] == FIXTURE_URL
    assert source_document["report_index"] == 3
    assert source_document["raw_sha256"] == sha256_bytes(RAW_FIXTURE.read_bytes())
    assert source_document["connector_name"] == "ccld_facility_reports"
    assert source_document["retrieved_at"] == RETRIEVED_AT


def test_ccld_facility_ingestion_can_emit_records_to_sqlite(tmp_path: Path) -> None:
    db_path = tmp_path / "ccld.sqlite"
    connector = CcldFacilityReportsConnector(db_path=db_path)

    result = ingest_facility_reports_for_facility(
        connector=connector,
        facility_detail_html=RAW_DETAIL_FIXTURE.read_text(encoding="utf-8"),
        discovered_at=RETRIEVED_AT,
        load_document=_load_existing_report_fixture,
    )

    assert len(result.records) == 1
    with sqlite3.connect(db_path) as conn:
        counts = {
            table_name: conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            for table_name in (
                "facilities",
                "source_documents",
                "complaints",
                "allegations",
                "extraction_audit",
            )
        }
        complaint_delay_fields = conn.execute(
            """
            SELECT days_received_to_first_activity,
                   days_received_to_visit,
                   days_received_to_report,
                   days_report_to_signed,
                   review_delay_over_30_days,
                   review_delay_over_60_days,
                   review_delay_over_90_days,
                   review_delay_over_120_days,
                   missing_first_activity_date,
                   report_date_used_as_proxy
            FROM complaints
            """
        ).fetchone()

    assert counts == {
        "facilities": 1,
        "source_documents": 1,
        "complaints": 1,
        "allegations": 2,
        "extraction_audit": 21,
    }
    assert complaint_delay_fields == (None, 139, 139, 2, 1, 1, 1, 1, 1, 0)


def _extract_fixture() -> dict[str, object]:
    raw_content = RAW_FIXTURE.read_bytes()
    document = SourceDocument(
        source_url=FIXTURE_URL,
        raw_path=RAW_FIXTURE,
        raw_sha256=sha256_bytes(raw_content),
        retrieved_at=RETRIEVED_AT,
        content_type="text/html",
    )
    return CcldFacilityReportsConnector().extract(document)


def _extract_numbered_allegations_fixture() -> dict[str, object]:
    raw_content = NUMBERED_ALLEGATIONS_RAW_FIXTURE.read_bytes()
    document = SourceDocument(
        source_url=NUMBERED_ALLEGATIONS_FIXTURE_URL,
        raw_path=NUMBERED_ALLEGATIONS_RAW_FIXTURE,
        raw_sha256=sha256_bytes(raw_content),
        retrieved_at=NUMBERED_ALLEGATIONS_RETRIEVED_AT,
        content_type="text/html",
    )
    return CcldFacilityReportsConnector().extract(document)


def _extract_inline_received_date_fixture() -> dict[str, object]:
    raw_content = INLINE_RECEIVED_DATE_RAW_FIXTURE.read_bytes()
    document = SourceDocument(
        source_url=INLINE_RECEIVED_DATE_FIXTURE_URL,
        raw_path=INLINE_RECEIVED_DATE_RAW_FIXTURE,
        raw_sha256=sha256_bytes(raw_content),
        retrieved_at=INLINE_RECEIVED_DATE_RETRIEVED_AT,
        content_type="text/html",
    )
    return CcldFacilityReportsConnector().extract(document)


def _extract_missing_visit_date_fixture() -> dict[str, object]:
    raw_content = MISSING_VISIT_DATE_RAW_FIXTURE.read_bytes()
    document = SourceDocument(
        source_url=MISSING_VISIT_DATE_FIXTURE_URL,
        raw_path=MISSING_VISIT_DATE_RAW_FIXTURE,
        raw_sha256=sha256_bytes(raw_content),
        retrieved_at=MISSING_VISIT_DATE_RETRIEVED_AT,
        content_type="text/html",
    )
    return CcldFacilityReportsConnector().extract(document)


def _extract_labeled_finding_fixture() -> dict[str, object]:
    raw_content = LABELED_FINDING_RAW_FIXTURE.read_bytes()
    document = SourceDocument(
        source_url=LABELED_FINDING_FIXTURE_URL,
        raw_path=LABELED_FINDING_RAW_FIXTURE,
        raw_sha256=sha256_bytes(raw_content),
        retrieved_at=LABELED_FINDING_RETRIEVED_AT,
        content_type="text/html",
    )
    return CcldFacilityReportsConnector().extract(document)


def _extract_wrapped_allegation_fixture() -> dict[str, object]:
    raw_content = WRAPPED_ALLEGATION_RAW_FIXTURE.read_bytes()
    document = SourceDocument(
        source_url=WRAPPED_ALLEGATION_FIXTURE_URL,
        raw_path=WRAPPED_ALLEGATION_RAW_FIXTURE,
        raw_sha256=sha256_bytes(raw_content),
        retrieved_at=WRAPPED_ALLEGATION_RETRIEVED_AT,
        content_type="text/html",
    )
    return CcldFacilityReportsConnector().extract(document)


def _extract_split_finding_fixture() -> dict[str, object]:
    raw_content = SPLIT_FINDING_RAW_FIXTURE.read_bytes()
    document = SourceDocument(
        source_url=SPLIT_FINDING_FIXTURE_URL,
        raw_path=SPLIT_FINDING_RAW_FIXTURE,
        raw_sha256=sha256_bytes(raw_content),
        retrieved_at=SPLIT_FINDING_RETRIEVED_AT,
        content_type="text/html",
    )
    return CcldFacilityReportsConnector().extract(document)


def _extract_allegation_heading_variant_fixture() -> dict[str, object]:
    raw_content = ALLEGATION_HEADING_VARIANT_RAW_FIXTURE.read_bytes()
    document = SourceDocument(
        source_url=ALLEGATION_HEADING_VARIANT_FIXTURE_URL,
        raw_path=ALLEGATION_HEADING_VARIANT_RAW_FIXTURE,
        raw_sha256=sha256_bytes(raw_content),
        retrieved_at=ALLEGATION_HEADING_VARIANT_RETRIEVED_AT,
        content_type="text/html",
    )
    return CcldFacilityReportsConnector().extract(document)


def _extract_investigation_finding_heading_fixture() -> dict[str, object]:
    raw_content = INVESTIGATION_FINDING_HEADING_RAW_FIXTURE.read_bytes()
    document = SourceDocument(
        source_url=INVESTIGATION_FINDING_HEADING_FIXTURE_URL,
        raw_path=INVESTIGATION_FINDING_HEADING_RAW_FIXTURE,
        raw_sha256=sha256_bytes(raw_content),
        retrieved_at=INVESTIGATION_FINDING_HEADING_RETRIEVED_AT,
        content_type="text/html",
    )
    return CcldFacilityReportsConnector().extract(document)


def _extract_allegation_heading_no_colon_fixture() -> dict[str, object]:
    raw_content = ALLEGATION_HEADING_NO_COLON_RAW_FIXTURE.read_bytes()
    document = SourceDocument(
        source_url=ALLEGATION_HEADING_NO_COLON_FIXTURE_URL,
        raw_path=ALLEGATION_HEADING_NO_COLON_RAW_FIXTURE,
        raw_sha256=sha256_bytes(raw_content),
        retrieved_at=ALLEGATION_HEADING_NO_COLON_RETRIEVED_AT,
        content_type="text/html",
    )
    return CcldFacilityReportsConnector().extract(document)


def _extract_punctuated_finding_fixture() -> dict[str, object]:
    raw_content = PUNCTUATED_FINDING_RAW_FIXTURE.read_bytes()
    document = SourceDocument(
        source_url=PUNCTUATED_FINDING_FIXTURE_URL,
        raw_path=PUNCTUATED_FINDING_RAW_FIXTURE,
        raw_sha256=sha256_bytes(raw_content),
        retrieved_at=PUNCTUATED_FINDING_RETRIEVED_AT,
        content_type="text/html",
    )
    return CcldFacilityReportsConnector().extract(document)


def _extract_dashed_finding_label_fixture() -> dict[str, object]:
    raw_content = DASHED_FINDING_LABEL_RAW_FIXTURE.read_bytes()
    document = SourceDocument(
        source_url=DASHED_FINDING_LABEL_FIXTURE_URL,
        raw_path=DASHED_FINDING_LABEL_RAW_FIXTURE,
        raw_sha256=sha256_bytes(raw_content),
        retrieved_at=DASHED_FINDING_LABEL_RETRIEVED_AT,
        content_type="text/html",
    )
    return CcldFacilityReportsConnector().extract(document)


def _extract_was_received_date_fixture() -> dict[str, object]:
    raw_content = WAS_RECEIVED_DATE_RAW_FIXTURE.read_bytes()
    document = SourceDocument(
        source_url=WAS_RECEIVED_DATE_FIXTURE_URL,
        raw_path=WAS_RECEIVED_DATE_RAW_FIXTURE,
        raw_sha256=sha256_bytes(raw_content),
        retrieved_at=WAS_RECEIVED_DATE_RETRIEVED_AT,
        content_type="text/html",
    )
    return CcldFacilityReportsConnector().extract(document)


def _extract_split_report_date_fixture() -> dict[str, object]:
    raw_content = SPLIT_REPORT_DATE_RAW_FIXTURE.read_bytes()
    document = SourceDocument(
        source_url=SPLIT_REPORT_DATE_FIXTURE_URL,
        raw_path=SPLIT_REPORT_DATE_RAW_FIXTURE,
        raw_sha256=sha256_bytes(raw_content),
        retrieved_at=SPLIT_REPORT_DATE_RETRIEVED_AT,
        content_type="text/html",
    )
    return CcldFacilityReportsConnector().extract(document)


def _extract_split_date_signed_fixture() -> dict[str, object]:
    raw_content = SPLIT_DATE_SIGNED_RAW_FIXTURE.read_bytes()
    document = SourceDocument(
        source_url=SPLIT_DATE_SIGNED_FIXTURE_URL,
        raw_path=SPLIT_DATE_SIGNED_RAW_FIXTURE,
        raw_sha256=sha256_bytes(raw_content),
        retrieved_at=SPLIT_DATE_SIGNED_RETRIEVED_AT,
        content_type="text/html",
    )
    return CcldFacilityReportsConnector().extract(document)


def _extract_split_visit_date_fixture() -> dict[str, object]:
    raw_content = SPLIT_VISIT_DATE_RAW_FIXTURE.read_bytes()
    document = SourceDocument(
        source_url=SPLIT_VISIT_DATE_FIXTURE_URL,
        raw_path=SPLIT_VISIT_DATE_RAW_FIXTURE,
        raw_sha256=sha256_bytes(raw_content),
        retrieved_at=SPLIT_VISIT_DATE_RETRIEVED_AT,
        content_type="text/html",
    )
    return CcldFacilityReportsConnector().extract(document)


def _extract_split_complaint_control_fixture() -> dict[str, object]:
    raw_content = SPLIT_COMPLAINT_CONTROL_RAW_FIXTURE.read_bytes()
    document = SourceDocument(
        source_url=SPLIT_COMPLAINT_CONTROL_FIXTURE_URL,
        raw_path=SPLIT_COMPLAINT_CONTROL_RAW_FIXTURE,
        raw_sha256=sha256_bytes(raw_content),
        retrieved_at=SPLIT_COMPLAINT_CONTROL_RETRIEVED_AT,
        content_type="text/html",
    )
    return CcldFacilityReportsConnector().extract(document)


def _extract_split_facility_name_fixture() -> dict[str, object]:
    raw_content = SPLIT_FACILITY_NAME_RAW_FIXTURE.read_bytes()
    document = SourceDocument(
        source_url=SPLIT_FACILITY_NAME_FIXTURE_URL,
        raw_path=SPLIT_FACILITY_NAME_RAW_FIXTURE,
        raw_sha256=sha256_bytes(raw_content),
        retrieved_at=SPLIT_FACILITY_NAME_RETRIEVED_AT,
        content_type="text/html",
    )
    return CcldFacilityReportsConnector().extract(document)


def _extract_split_facility_number_fixture() -> dict[str, object]:
    raw_content = SPLIT_FACILITY_NUMBER_RAW_FIXTURE.read_bytes()
    document = SourceDocument(
        source_url=SPLIT_FACILITY_NUMBER_FIXTURE_URL,
        raw_path=SPLIT_FACILITY_NUMBER_RAW_FIXTURE,
        raw_sha256=sha256_bytes(raw_content),
        retrieved_at=SPLIT_FACILITY_NUMBER_RETRIEVED_AT,
        content_type="text/html",
    )
    return CcldFacilityReportsConnector().extract(document)


def _extract_report_type_case_fixture() -> dict[str, object]:
    raw_content = REPORT_TYPE_CASE_RAW_FIXTURE.read_bytes()
    document = SourceDocument(
        source_url=REPORT_TYPE_CASE_FIXTURE_URL,
        raw_path=REPORT_TYPE_CASE_RAW_FIXTURE,
        raw_sha256=sha256_bytes(raw_content),
        retrieved_at=REPORT_TYPE_CASE_RETRIEVED_AT,
        content_type="text/html",
    )
    return CcldFacilityReportsConnector().extract(document)


def _extract_spaced_allegation_heading_fixture() -> dict[str, object]:
    raw_content = SPACED_ALLEGATION_HEADING_RAW_FIXTURE.read_bytes()
    document = SourceDocument(
        source_url=SPACED_ALLEGATION_HEADING_FIXTURE_URL,
        raw_path=SPACED_ALLEGATION_HEADING_RAW_FIXTURE,
        raw_sha256=sha256_bytes(raw_content),
        retrieved_at=SPACED_ALLEGATION_HEADING_RETRIEVED_AT,
        content_type="text/html",
    )
    return CcldFacilityReportsConnector().extract(document)


def _load_existing_report_fixture(candidate: SourceDocumentCandidate) -> SourceDocument | None:
    if candidate.report_index != 3:
        return None
    raw_content = RAW_FIXTURE.read_bytes()
    return SourceDocument(
        source_url=candidate.source_url,
        raw_path=RAW_FIXTURE,
        raw_sha256=sha256_bytes(raw_content),
        retrieved_at=RETRIEVED_AT,
        content_type="text/html",
    )


def _without_audit(normalized: dict[str, object]) -> dict[str, Any]:
    return {key: value for key, value in normalized.items() if key != "extraction_audit"}