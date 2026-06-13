from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from ccld_complaints.cli.fetch_live_ccld import (
    _collect_facility_number_intake,
    facility_intake_summary_lines,
    live_fetch_summary_lines,
)
from ccld_complaints.connectors.base import SourceDocument
from ccld_complaints.connectors.ccld import CcldFacilityReportsConnector, facility_reports
from ccld_complaints.connectors.ccld.facility_reports import (
    FacilityNumberIntakeResult,
    ingest_facility_reports_for_facilities,
    ingest_facility_reports_for_facility,
    inspect_facility_numbers,
    read_facility_number_input_file,
    read_facility_numbers_file,
)

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


def test_live_fetch_workflow_fetches_multiple_reports_into_sqlite(tmp_path: Path) -> None:
    db_path = tmp_path / "processed" / "ccld.sqlite"
    raw_dir = tmp_path / "raw" / "ccld"
    connector = CcldFacilityReportsConnector(raw_dir=raw_dir, db_path=db_path)

    result = ingest_facility_reports_for_facility(
        connector=connector,
        facility_detail_html=RAW_DETAIL_FIXTURE.read_text(encoding="utf-8"),
        discovered_at=RETRIEVED_AT,
        limit=3,
        max_requests=3,
        fetch_report=_fake_report_fetch,
    )

    assert len(result.records) == 3
    assert result.failures == []
    assert _table_count(db_path, "source_documents") == 3
    assert _table_count(db_path, "complaints") == 3
    assert _table_count(db_path, "allegations") == 6

    with sqlite3.connect(db_path) as conn:
        source_documents = conn.execute(
            """
            SELECT source_url,
                   raw_sha256,
                   raw_path,
                   connector_name,
                   connector_version,
                   retrieved_at,
                   report_index
            FROM source_documents
            ORDER BY report_index
            """
        ).fetchall()

    assert [row[6] for row in source_documents] == [29, 37, 39]
    for source_url, raw_sha256, raw_path, connector_name, connector_version, retrieved_at, _ in (
        source_documents
    ):
        assert source_url.startswith(
            "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports"
        )
        assert raw_sha256
        assert Path(str(raw_path)).exists()
        assert connector_name == "ccld_facility_reports"
        assert connector_version == "0.1.0"
        assert retrieved_at


def test_live_fetch_workflow_rerun_does_not_duplicate_sqlite_records(tmp_path: Path) -> None:
    db_path = tmp_path / "processed" / "ccld.sqlite"
    raw_dir = tmp_path / "raw" / "ccld"
    connector = CcldFacilityReportsConnector(raw_dir=raw_dir, db_path=db_path)

    for _run in range(2):
        result = ingest_facility_reports_for_facility(
            connector=connector,
            facility_detail_html=RAW_DETAIL_FIXTURE.read_text(encoding="utf-8"),
            discovered_at=RETRIEVED_AT,
            limit=2,
            max_requests=2,
            fetch_report=_fake_report_fetch,
        )
        assert len(result.records) == 2
        assert result.failures == []

    assert _table_count(db_path, "source_documents") == 2
    assert _table_count(db_path, "complaints") == 2
    assert _table_count(db_path, "allegations") == 4


def test_live_fetch_workflow_records_partial_failures_while_writing_successes(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "processed" / "ccld.sqlite"
    connector = CcldFacilityReportsConnector(raw_dir=tmp_path / "raw" / "ccld", db_path=db_path)

    def partially_failing_fetch(source_url: str) -> bytes:
        if "inx=37" in source_url:
            raise RuntimeError("controlled report fetch failure")
        return _fake_report_fetch(source_url)

    result = ingest_facility_reports_for_facility(
        connector=connector,
        facility_detail_html=RAW_DETAIL_FIXTURE.read_text(encoding="utf-8"),
        discovered_at=RETRIEVED_AT,
        limit=3,
        max_requests=3,
        fetch_report=partially_failing_fetch,
    )

    assert len(result.records) == 2
    assert len(result.failures) == 1
    assert result.failures[0].candidate.report_index == 37
    assert result.failures[0].stage == "fetch"
    assert _table_count(db_path, "source_documents") == 2
    assert _table_count(db_path, "complaints") == 2


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


def test_live_fetch_summary_reports_discovered_selected_and_skipped_counts() -> None:
    result = ingest_facility_reports_for_facility(
        facility_detail_html=RAW_DETAIL_FIXTURE.read_text(encoding="utf-8"),
        discovered_at=RETRIEVED_AT,
        limit=2,
        max_requests=2,
        fetch_report=_fake_report_fetch,
    )

    assert result.discovered_count == 40
    assert len(result.candidates) == 2

    summary = live_fetch_summary_lines([result], [])

    assert "- Report candidates discovered: 40" in summary
    assert "- Report candidates selected: 2" in summary
    assert "- Reports skipped by limit: 38" in summary
    assert "- Reports fetched: 2" in summary
    assert "- Records written: 2" in summary
    assert "- Report failures: 0" in summary
    assert (
        "- 157806098: discovered=40, selected=2, skipped=38, "
        "fetched=2, written=2, failed=0"
    ) in summary


def test_live_fetch_summary_separates_fetch_failures_from_fetched_reports() -> None:
    def partially_failing_fetch(source_url: str) -> bytes:
        if "inx=37" in source_url:
            raise RuntimeError("controlled report fetch failure")
        return _fake_report_fetch(source_url)

    result = ingest_facility_reports_for_facility(
        facility_detail_html=RAW_DETAIL_FIXTURE.read_text(encoding="utf-8"),
        discovered_at=RETRIEVED_AT,
        limit=3,
        max_requests=3,
        fetch_report=partially_failing_fetch,
    )

    summary = live_fetch_summary_lines([result], [])

    assert "- Reports fetched: 2" in summary
    assert "- Records written: 2" in summary
    assert "- Report failures: 1" in summary
    assert (
        "- 157806098: discovered=40, selected=3, skipped=37, "
        "fetched=2, written=2, failed=1"
    ) in summary


def test_live_fetch_workflow_enforces_max_requests() -> None:
    fetch_count = 0

    def counting_fetch(_source_url: str) -> bytes:
        nonlocal fetch_count
        fetch_count += 1
        return RAW_FIXTURE.read_bytes()

    with pytest.raises(ValueError, match="exceed max_requests"):
        ingest_facility_reports_for_facility(
            facility_detail_html=RAW_DETAIL_FIXTURE.read_text(encoding="utf-8"),
            discovered_at=RETRIEVED_AT,
            limit=3,
            max_requests=2,
            fetch_report=counting_fetch,
        )

    assert fetch_count == 0

    result = ingest_facility_reports_for_facility(
        facility_detail_html=RAW_DETAIL_FIXTURE.read_text(encoding="utf-8"),
        discovered_at=RETRIEVED_AT,
        limit=2,
        max_requests=2,
        fetch_report=counting_fetch,
    )

    assert len(result.candidates) == 2
    assert fetch_count == 2


def test_live_fetch_workflow_processes_multiple_facility_numbers(tmp_path: Path) -> None:
    db_path = tmp_path / "processed" / "ccld.sqlite"
    raw_dir = tmp_path / "raw" / "ccld"

    result = ingest_facility_reports_for_facilities(
        ["157806098", "123456789"],
        connector_factory=_connector_factory(raw_dir, db_path),
        facility_detail_html_by_number={
            "157806098": _facility_detail_html("157806098"),
            "123456789": _facility_detail_html("123456789"),
        },
        discovered_at=RETRIEVED_AT,
        per_facility_limit=1,
        max_requests=2,
        fetch_report=_fake_multi_facility_report_fetch,
    )

    assert [candidate.facility_number for candidate in result.candidates] == [
        "157806098",
        "123456789",
    ]
    assert len(result.records) == 2
    assert result.facility_failures == []
    assert _table_count(db_path, "source_documents") == 2
    assert _facility_numbers(db_path) == ["123456789", "157806098"]
    assert _source_traceability_facility_numbers(db_path) == ["123456789", "157806098"]


def test_live_fetch_workflow_keeps_running_after_one_facility_failure(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "processed" / "ccld.sqlite"
    raw_dir = tmp_path / "raw" / "ccld"

    result = ingest_facility_reports_for_facilities(
        ["000000000", "157806098"],
        connector_factory=_failing_discovery_connector_factory(raw_dir, db_path),
        facility_detail_html_by_number={"157806098": _facility_detail_html("157806098")},
        discovered_at=RETRIEVED_AT,
        per_facility_limit=1,
        max_requests=1,
        fetch_report=_fake_multi_facility_report_fetch,
    )

    assert len(result.records) == 1
    assert len(result.facility_failures) == 1
    assert result.facility_failures[0].facility_number == "000000000"
    assert result.facility_failures[0].stage == "discover"
    assert _facility_numbers(db_path) == ["157806098"]


def test_live_fetch_workflow_handles_duplicate_facility_numbers_safely(
    tmp_path: Path,
) -> None:
    fetch_count = 0

    def counting_fetch(source_url: str) -> bytes:
        nonlocal fetch_count
        fetch_count += 1
        return _fake_multi_facility_report_fetch(source_url)

    result = ingest_facility_reports_for_facilities(
        ["157806098", "157806098", " 157806098 "],
        connector_factory=_connector_factory(tmp_path / "raw" / "ccld", tmp_path / "ccld.sqlite"),
        facility_detail_html_by_number={"157806098": _facility_detail_html("157806098")},
        discovered_at=RETRIEVED_AT,
        per_facility_limit=1,
        max_requests=1,
        fetch_report=counting_fetch,
    )

    assert [candidate.facility_number for candidate in result.candidates] == ["157806098"]
    assert len(result.records) == 1
    assert fetch_count == 1


def test_live_fetch_workflow_applies_per_facility_limit(tmp_path: Path) -> None:
    result = ingest_facility_reports_for_facilities(
        ["157806098", "123456789"],
        connector_factory=_connector_factory(tmp_path / "raw" / "ccld", tmp_path / "ccld.sqlite"),
        facility_detail_html_by_number={
            "157806098": _facility_detail_html("157806098"),
            "123456789": _facility_detail_html("123456789"),
        },
        discovered_at=RETRIEVED_AT,
        per_facility_limit=2,
        max_requests=4,
        fetch_report=_fake_multi_facility_report_fetch,
    )

    assert [
        (candidate.facility_number, candidate.report_index) for candidate in result.candidates
    ] == [
        ("157806098", 39),
        ("157806098", 37),
        ("123456789", 39),
        ("123456789", 37),
    ]
    assert len(result.records) == 4


def test_live_fetch_workflow_applies_overall_max_requests(tmp_path: Path) -> None:
    fetch_count = 0

    def counting_fetch(source_url: str) -> bytes:
        nonlocal fetch_count
        fetch_count += 1
        return _fake_multi_facility_report_fetch(source_url)

    with pytest.raises(ValueError, match="exceed max_requests"):
        ingest_facility_reports_for_facilities(
            ["157806098", "123456789"],
            connector_factory=_connector_factory(
                tmp_path / "raw" / "ccld",
                tmp_path / "ccld.sqlite",
            ),
            facility_detail_html_by_number={
                "157806098": _facility_detail_html("157806098"),
                "123456789": _facility_detail_html("123456789"),
            },
            discovered_at=RETRIEVED_AT,
            per_facility_limit=2,
            max_requests=3,
            fetch_report=counting_fetch,
        )

    assert fetch_count == 0


def test_live_fetch_workflow_multi_facility_tests_do_not_make_live_requests(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def blocked_urlopen(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("test attempted a live web request")

    monkeypatch.setattr(facility_reports, "urlopen", blocked_urlopen)

    result = ingest_facility_reports_for_facilities(
        ["157806098", "123456789"],
        connector_factory=_connector_factory(tmp_path / "raw" / "ccld", tmp_path / "ccld.sqlite"),
        facility_detail_html_by_number={
            "157806098": _facility_detail_html("157806098"),
            "123456789": _facility_detail_html("123456789"),
        },
        discovered_at=RETRIEVED_AT,
        per_facility_limit=1,
        max_requests=2,
        fetch_report=_fake_multi_facility_report_fetch,
    )

    assert len(result.records) == 2
    assert result.failures == []


def test_live_fetch_workflow_reads_small_facility_input_file(tmp_path: Path) -> None:
    input_path = tmp_path / "facility-numbers.csv"
    input_path.write_text(
        "facility_number\n157806098,123456789\n# ignored comment\n157806098\n",
        encoding="utf-8",
    )

    assert read_facility_numbers_file(input_path) == ["157806098", "123456789"]


def test_facility_identifier_intake_reports_duplicates_invalid_and_ignored_values() -> None:
    intake = inspect_facility_numbers(
        [
            " facility_number ",
            "157806098",
            "157806098",
            " 123456789 ",
            "",
            "# ignored comment",
            "12A",
        ]
    )

    assert intake.facility_numbers == ["157806098", "123456789"]
    assert intake.duplicate_facility_numbers == ["157806098"]
    assert intake.ignored_value_count == 3
    assert intake.invalid_values == ["12A"]


def test_facility_input_file_reports_ignored_values_for_intake_summary(tmp_path: Path) -> None:
    input_path = tmp_path / "facility-numbers.csv"
    input_path.write_text(
        "facility_number\n\n157806098,123456789\n# ignored comment\n",
        encoding="utf-8",
    )

    file_input = read_facility_number_input_file(input_path)

    assert file_input.values == ["157806098", "123456789"]
    assert file_input.ignored_value_count == 3


def test_facility_input_file_with_only_ignored_values_is_rejected(tmp_path: Path) -> None:
    input_path = tmp_path / "facility-numbers.csv"
    input_path.write_text("facility_number\n# ignored comment\n\n", encoding="utf-8")

    with pytest.raises(ValueError, match="At least one facility number is required"):
        _collect_facility_number_intake(None, input_path)


def test_facility_intake_summary_lines_show_accepted_duplicate_and_ignored_values() -> None:
    summary = facility_intake_summary_lines(
        FacilityNumberIntakeResult(
            facility_numbers=["157806098", "123456789"],
            duplicate_facility_numbers=["157806098"],
            ignored_value_count=2,
            invalid_values=[],
        )
    )

    assert "Facility identifier intake:" in summary
    assert "- Accepted facility identifiers: 157806098, 123456789" in summary
    assert "- Duplicate identifiers ignored: 157806098" in summary
    assert "- Ignored blank, comment, or header values: 2" in summary


def _fake_report_fetch(source_url: str) -> bytes:
    for report_index in (39, 37, 29):
        if f"inx={report_index}" in source_url:
            return _report_content(report_index)
    raise AssertionError(f"Unexpected report URL: {source_url}")


def _fake_multi_facility_report_fetch(source_url: str) -> bytes:
    facility_number = _facility_number_from_url(source_url)
    report_index = _report_index_from_url(source_url)
    if report_index not in (39, 37, 29):
        raise AssertionError(f"Unexpected report URL: {source_url}")
    return _report_content_for_facility(facility_number, report_index)


def _report_content(report_index: int) -> bytes:
    return RAW_FIXTURE.read_bytes().replace(
        b"32-CR-20220407124448",
        f"32-CR-202204071244{report_index:02d}".encode("ascii"),
    )


def _report_content_for_facility(facility_number: str, report_index: int) -> bytes:
    return _report_content(report_index).replace(b"157806098", facility_number.encode("ascii"))


def _facility_detail_html(facility_number: str) -> str:
    return RAW_DETAIL_FIXTURE.read_text(encoding="utf-8").replace("157806098", facility_number)


def _connector_factory(
    raw_dir: Path,
    db_path: Path,
) -> Any:
    def create_connector(facility_number: str) -> CcldFacilityReportsConnector:
        return CcldFacilityReportsConnector(
            facility_number=facility_number,
            raw_dir=raw_dir,
            db_path=db_path,
        )

    return create_connector


def _failing_discovery_connector_factory(raw_dir: Path, db_path: Path) -> Any:
    class FailingDiscoveryConnector(CcldFacilityReportsConnector):
        def discover(
            self,
            facility_detail_html: str | None = None,
            discovered_at: str | None = None,
        ) -> list[Any]:
            raise RuntimeError("controlled facility discovery failure")

    def create_connector(facility_number: str) -> CcldFacilityReportsConnector:
        if facility_number == "000000000":
            return FailingDiscoveryConnector(
                facility_number=facility_number,
                raw_dir=raw_dir,
                db_path=db_path,
            )
        return CcldFacilityReportsConnector(
            facility_number=facility_number,
            raw_dir=raw_dir,
            db_path=db_path,
        )

    return create_connector


def _facility_number_from_url(source_url: str) -> str:
    marker = "facNum="
    return source_url.split(marker, 1)[1].split("&", 1)[0]


def _report_index_from_url(source_url: str) -> int:
    marker = "inx="
    return int(source_url.split(marker, 1)[1].split("&", 1)[0])


def _facility_numbers(db_path: Path) -> list[str]:
    with sqlite3.connect(db_path) as conn:
        return [
            str(row[0])
            for row in conn.execute(
                "SELECT external_facility_number FROM facilities ORDER BY external_facility_number"
            ).fetchall()
        ]


def _source_traceability_facility_numbers(db_path: Path) -> list[str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT facilities.external_facility_number,
                   source_documents.source_url,
                   source_documents.raw_sha256,
                   source_documents.raw_path,
                   source_documents.connector_name,
                   source_documents.connector_version,
                   source_documents.retrieved_at,
                   source_documents.report_index
            FROM source_documents
            JOIN facilities ON facilities.facility_id = source_documents.facility_id
            ORDER BY facilities.external_facility_number
            """
        ).fetchall()

    for (
        facility_number,
        source_url,
        raw_sha256,
        raw_path,
        connector_name,
        connector_version,
        retrieved_at,
        report_index,
    ) in rows:
        assert facility_number in str(source_url)
        assert raw_sha256
        assert Path(str(raw_path)).exists()
        assert connector_name == "ccld_facility_reports"
        assert connector_version == "0.1.0"
        assert retrieved_at
        assert report_index == 39

    return [str(row[0]) for row in rows]


def _table_count(db_path: Path, table_name: str) -> int:
    with sqlite3.connect(db_path) as conn:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])