from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ccld_complaints.connectors.base import SourceDocument
from ccld_complaints.connectors.ccld import CcldFacilityReportsConnector
from ccld_complaints.utils.hash import sha256_bytes

FIXTURE_URL = "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=157806098&inx=3"
RAW_FIXTURE = Path("tests/fixtures/ccld/raw/157806098_inx3.html")
EXPECTED_FIXTURE = Path("tests/fixtures/ccld/expected/157806098_inx3.json")
RETRIEVED_AT = "2026-06-10T00:00:00+00:00"


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