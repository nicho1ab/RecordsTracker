from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ccld_complaints.connectors.base import SourceDocument
from ccld_complaints.connectors.ccld import CcldFacilityReportsConnector, facility_reports
from ccld_complaints.connectors.ccld.facility_reports import ingest_facility_reports_for_facility

RAW_FIXTURE = Path("tests/fixtures/ccld/raw/157806098_inx3.html")
RAW_DETAIL_FIXTURE = Path("tests/fixtures/ccld/raw/157806098_facility_detail.html")
RETRIEVED_AT = "2026-06-10T00:00:00+00:00"


class SavedRawAssertingConnector(CcldFacilityReportsConnector):
    def __init__(self, *, expected_content: bytes, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.expected_content = expected_content
        self.extract_saw_saved_raw = False

    def extract(self, document: SourceDocument) -> dict[str, object]:
        assert document.raw_path.exists()
        assert document.raw_path.read_bytes() == self.expected_content
        self.extract_saw_saved_raw = True
        return super().extract(document)


def test_live_fetch_workflow_saves_raw_before_extraction(tmp_path: Path) -> None:
    fetched_content = RAW_FIXTURE.read_bytes()
    connector = SavedRawAssertingConnector(
        expected_content=fetched_content,
        raw_dir=tmp_path / "raw" / "ccld",
    )

    result = ingest_facility_reports_for_facility(
        connector=connector,
        facility_detail_html=RAW_DETAIL_FIXTURE.read_text(encoding="utf-8"),
        discovered_at=RETRIEVED_AT,
        limit=1,
        fetch_report=lambda _source_url: fetched_content,
    )

    assert connector.extract_saw_saved_raw is True
    assert len(result.records) == 1
    source_document = result.records[0]["source_document"]
    assert isinstance(source_document, dict)
    raw_path = Path(str(source_document["raw_path"]))
    assert raw_path.exists()
    assert raw_path.read_bytes() == fetched_content
    assert source_document["report_index"] == result.candidates[0].report_index


def test_live_fetch_workflow_ingests_saved_raw_files_into_sqlite(tmp_path: Path) -> None:
    fetched_content = RAW_FIXTURE.read_bytes()
    db_path = tmp_path / "processed" / "ccld.sqlite"
    connector = CcldFacilityReportsConnector(
        raw_dir=tmp_path / "raw" / "ccld",
        db_path=db_path,
    )

    result = ingest_facility_reports_for_facility(
        connector=connector,
        facility_detail_html=RAW_DETAIL_FIXTURE.read_text(encoding="utf-8"),
        discovered_at=RETRIEVED_AT,
        limit=1,
        fetch_report=lambda _source_url: fetched_content,
    )

    assert len(result.records) == 1
    source_document = result.records[0]["source_document"]
    assert isinstance(source_document, dict)
    raw_path = Path(str(source_document["raw_path"]))
    assert raw_path.exists()
    assert raw_path.is_relative_to(tmp_path / "raw" / "ccld")
    assert db_path.exists()


def test_live_fetch_workflow_records_fetch_failures() -> None:
    def failing_fetch(_source_url: str) -> bytes:
        raise RuntimeError("controlled fetch failure")

    result = ingest_facility_reports_for_facility(
        facility_detail_html=RAW_DETAIL_FIXTURE.read_text(encoding="utf-8"),
        discovered_at=RETRIEVED_AT,
        limit=1,
        fetch_report=failing_fetch,
    )

    assert result.records == []
    assert len(result.failures) == 1
    failure = result.failures[0]
    assert failure.stage == "fetch"
    assert failure.error_type == "RuntimeError"
    assert failure.message == "controlled fetch failure"


def test_live_fetch_workflow_tests_do_not_make_live_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def blocked_urlopen(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("test attempted a live web request")

    monkeypatch.setattr(facility_reports, "urlopen", blocked_urlopen)

    result = ingest_facility_reports_for_facility(
        facility_detail_html=RAW_DETAIL_FIXTURE.read_text(encoding="utf-8"),
        discovered_at=RETRIEVED_AT,
        limit=1,
        fetch_report=lambda _source_url: RAW_FIXTURE.read_bytes(),
    )

    assert len(result.records) == 1
    assert result.failures == []


def test_live_fetch_workflow_limit_selects_discovered_candidates() -> None:
    result = ingest_facility_reports_for_facility(
        facility_detail_html=RAW_DETAIL_FIXTURE.read_text(encoding="utf-8"),
        discovered_at=RETRIEVED_AT,
        limit=3,
        fetch_report=lambda _source_url: RAW_FIXTURE.read_bytes(),
    )

    assert [candidate.report_index for candidate in result.candidates] == [39, 37, 29]