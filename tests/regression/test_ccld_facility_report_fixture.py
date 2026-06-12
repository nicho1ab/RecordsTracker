from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, cast

from ccld_complaints.connectors.base import SourceDocument, SourceDocumentCandidate
from ccld_complaints.connectors.ccld import CcldFacilityReportsConnector
from ccld_complaints.connectors.ccld.facility_reports import ingest_facility_reports_for_facility
from ccld_complaints.utils.hash import sha256_bytes

FIXTURE_URL = "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=157806098&inx=3"
NUMBERED_ALLEGATIONS_FIXTURE_URL = (
    "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=157806098&inx=40"
)
RAW_FIXTURE = Path("tests/fixtures/ccld/raw/157806098_inx3.html")
NUMBERED_ALLEGATIONS_RAW_FIXTURE = Path(
    "tests/fixtures/ccld/raw/157806098_inx40_numbered_allegations.html"
)
RAW_DETAIL_FIXTURE = Path("tests/fixtures/ccld/raw/157806098_facility_detail.html")
EXPECTED_FIXTURE = Path("tests/fixtures/ccld/expected/157806098_inx3.json")
NUMBERED_ALLEGATIONS_EXPECTED_FIXTURE = Path(
    "tests/fixtures/ccld/expected/157806098_inx40_numbered_allegations.json"
)
RETRIEVED_AT = "2026-06-10T00:00:00+00:00"
NUMBERED_ALLEGATIONS_RETRIEVED_AT = "2026-06-12T00:00:00+00:00"


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