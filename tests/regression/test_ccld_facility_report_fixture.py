from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ccld_complaints.connectors.base import SourceDocument
from ccld_complaints.connectors.ccld import CcldFacilityReportsConnector
from ccld_complaints.utils.hash import sha256_bytes

FIXTURE_URL = "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=157806098&inx=3"
RAW_FIXTURE = Path("tests/fixtures/ccld/raw/157806098_inx3.html")
RAW_DETAIL_FIXTURE = Path("tests/fixtures/ccld/raw/157806098_facility_detail.html")
EXPECTED_FIXTURE = Path("tests/fixtures/ccld/expected/157806098_inx3.json")
RETRIEVED_AT = "2026-06-10T00:00:00+00:00"


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
    assert extracted["days_received_to_report"] == 139


def test_ccld_facility_report_normalizes_to_expected_fixture() -> None:
    connector = CcldFacilityReportsConnector()
    normalized = connector.normalize(_extract_fixture())
    expected = json.loads(EXPECTED_FIXTURE.read_text(encoding="utf-8"))

    assert _without_audit(normalized) == expected


def test_ccld_facility_report_validates_normalized_records() -> None:
    connector = CcldFacilityReportsConnector()
    normalized = connector.normalize(_extract_fixture())

    connector.validate(normalized)


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


def _without_audit(normalized: dict[str, object]) -> dict[str, Any]:
    return {key: value for key, value in normalized.items() if key != "extraction_audit"}