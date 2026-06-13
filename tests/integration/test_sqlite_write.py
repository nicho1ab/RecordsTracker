from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import cast

from ccld_complaints.connectors.base import SourceDocument
from ccld_complaints.connectors.ccld import CcldFacilityReportsConnector
from ccld_complaints.storage.sqlite import write_normalized_records
from ccld_complaints.utils.hash import sha256_bytes

FIXTURE_URL = "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=157806098&inx=3"
RAW_FIXTURE = Path("tests/fixtures/ccld/raw/157806098_inx3.html")
RETRIEVED_AT = "2026-06-10T00:00:00+00:00"


def test_write_normalized_ccld_report_to_sqlite(tmp_path: Path) -> None:
    db_path = tmp_path / "ccld.sqlite"
    normalized = _normalized_fixture()

    write_normalized_records(db_path, [normalized])

    assert _row_count(db_path, "facilities") == 1
    assert _row_count(db_path, "source_documents") == 1
    assert _row_count(db_path, "complaints") == 1
    assert _row_count(db_path, "allegations") == 2
    assert _row_count(db_path, "events") == 0
    assert _row_count(db_path, "extraction_audit") == 21
    assert _source_traceability(db_path) == {
        "source_url": FIXTURE_URL,
        "raw_sha256": sha256_bytes(RAW_FIXTURE.read_bytes()),
        "raw_path": RAW_FIXTURE.as_posix(),
        "connector_name": "ccld_facility_reports",
        "connector_version": "0.1.0",
        "retrieved_at": RETRIEVED_AT,
        "report_index": 3,
    }
    assert _complaint_delay_fields(db_path) == {
        "days_received_to_first_activity": None,
        "days_received_to_visit": 139,
        "days_received_to_report": 139,
        "days_report_to_signed": 2,
        "review_delay_over_30_days": 1,
        "review_delay_over_60_days": 1,
        "review_delay_over_90_days": 1,
        "review_delay_over_120_days": 1,
        "missing_first_activity_date": 1,
        "report_date_used_as_proxy": 0,
    }


def test_review_views_return_fixture_backed_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "ccld.sqlite"
    normalized = _normalized_fixture()

    write_normalized_records(db_path, [normalized])

    assert _complaint_review_summary(db_path) == {
        "facility_number": "157806098",
        "facility_name": "A. MIRIAM JAMISON CHILDREN'S CENTER",
        "complaint_control_number": "32-CR-20220407124448",
        "complaint_received_date": "2022-04-07",
        "first_investigation_activity_date": None,
        "visit_date": "2022-08-24",
        "report_date": "2022-08-24",
        "date_signed": "2022-08-26",
        "finding": "Unsubstantiated",
        "allegation_count": 2,
        "days_received_to_first_activity": None,
        "days_received_to_visit": 139,
        "days_received_to_report": 139,
        "days_report_to_signed": 2,
        "review_delay_over_30_days": 1,
        "review_delay_over_60_days": 1,
        "review_delay_over_90_days": 1,
        "review_delay_over_120_days": 1,
        "missing_first_activity_date": 1,
        "report_date_used_as_proxy": 0,
        "source_url": FIXTURE_URL,
        "raw_path": RAW_FIXTURE.as_posix(),
    }
    assert _complaint_first_pass_review(db_path) == {
        "facility_number": "157806098",
        "facility_name": "A. MIRIAM JAMISON CHILDREN'S CENTER",
        "complaint_control_number": "32-CR-20220407124448",
        "complaint_received_date": "2022-04-07",
        "visit_date": "2022-08-24",
        "report_date": "2022-08-24",
        "finding": "Unsubstantiated",
        "allegation_count": 2,
        "review_flags_summary": (
            "over 30 days; over 60 days; over 90 days; over 120 days; "
            "missing first activity date"
        ),
        "source_url": FIXTURE_URL,
        "raw_sha256": sha256_bytes(RAW_FIXTURE.read_bytes()),
        "raw_path": RAW_FIXTURE.as_posix(),
        "connector_name": "ccld_facility_reports",
        "connector_version": "0.1.0",
        "retrieved_at": RETRIEVED_AT,
        "report_index": 3,
    }
    allegation_summary = _view_value(
        db_path, "complaint_review_summary", "allegation_summary"
    )
    assert "Facility clients are being mistreated while in care" in allegation_summary
    assert (
        "Facility staff do not provide adequate supervision to the facility clients"
        in allegation_summary
    )
    assert _facility_complaint_summary(db_path) == {
        "facility_number": "157806098",
        "facility_name": "A. MIRIAM JAMISON CHILDREN'S CENTER",
        "complaint_count": 1,
        "allegation_count": 2,
        "earliest_complaint_received_date": "2022-04-07",
        "latest_complaint_received_date": "2022-04-07",
        "records_with_delay_review_flags": 1,
    }
    assert _facility_pattern_review(db_path) == {
        "facility_number": "157806098",
        "facility_name": "A. MIRIAM JAMISON CHILDREN'S CENTER",
        "complaint_count": 1,
        "source_document_count": 1,
        "allegation_count": 2,
        "allegation_categories": "Unknown",
        "substantiated_complaint_count": 0,
        "unsubstantiated_complaint_count": 1,
        "inconclusive_complaint_count": 0,
        "unknown_finding_complaint_count": 0,
        "missing_first_activity_count": 1,
        "report_date_proxy_count": 0,
        "records_with_review_flags": 1,
        "earliest_complaint_received_date": "2022-04-07",
        "latest_complaint_received_date": "2022-04-07",
        "earliest_retrieved_at": RETRIEVED_AT,
        "latest_retrieved_at": RETRIEVED_AT,
    }
    assert _source_traceability_review(db_path) == {
        "facility_number": "157806098",
        "facility_name": "A. MIRIAM JAMISON CHILDREN'S CENTER",
        "source_url": FIXTURE_URL,
        "raw_sha256": sha256_bytes(RAW_FIXTURE.read_bytes()),
        "raw_path": RAW_FIXTURE.as_posix(),
        "connector_name": "ccld_facility_reports",
        "connector_version": "0.1.0",
        "retrieved_at": RETRIEVED_AT,
        "report_index": 3,
    }
    assert _complaint_timeline_review(db_path) == [
        {
            "timeline_sequence": 1,
            "timeline_item_type": "complaint received",
            "timeline_source_field": "complaint_received_date",
            "timeline_date": "2022-04-07",
            "source_url": FIXTURE_URL,
            "raw_sha256": sha256_bytes(RAW_FIXTURE.read_bytes()),
            "connector_name": "ccld_facility_reports",
        },
        {
            "timeline_sequence": 3,
            "timeline_item_type": "visit",
            "timeline_source_field": "visit_date",
            "timeline_date": "2022-08-24",
            "source_url": FIXTURE_URL,
            "raw_sha256": sha256_bytes(RAW_FIXTURE.read_bytes()),
            "connector_name": "ccld_facility_reports",
        },
        {
            "timeline_sequence": 4,
            "timeline_item_type": "report",
            "timeline_source_field": "report_date",
            "timeline_date": "2022-08-24",
            "source_url": FIXTURE_URL,
            "raw_sha256": sha256_bytes(RAW_FIXTURE.read_bytes()),
            "connector_name": "ccld_facility_reports",
        },
        {
            "timeline_sequence": 5,
            "timeline_item_type": "date signed",
            "timeline_source_field": "date_signed",
            "timeline_date": "2022-08-26",
            "source_url": FIXTURE_URL,
            "raw_sha256": sha256_bytes(RAW_FIXTURE.read_bytes()),
            "connector_name": "ccld_facility_reports",
        },
    ]
    assert _field_source_traceability_review(db_path) == {
        "facility_number": "157806098",
        "complaint_control_number": "32-CR-20220407124448",
        "field_name": "facility_number",
        "extracted_value": "157806098",
        "source_text": None,
        "source_section": None,
        "warning": None,
        "confidence": 1.0,
        "extraction_method": "ccld_facility_report_html_labels",
        "extractor_version": "0.1.0",
        "source_url": FIXTURE_URL,
        "raw_sha256": sha256_bytes(RAW_FIXTURE.read_bytes()),
        "connector_name": "ccld_facility_reports",
        "connector_version": "0.1.0",
        "report_index": 3,
    }


def test_delay_review_flags_view_exposes_flagged_records(tmp_path: Path) -> None:
    db_path = tmp_path / "ccld.sqlite"
    normalized = _normalized_fixture()

    write_normalized_records(db_path, [normalized])

    assert _delay_review_flags(db_path) == {
        "facility_number": "157806098",
        "complaint_control_number": "32-CR-20220407124448",
        "days_received_to_visit": 139,
        "review_delay_over_30_days": 1,
        "review_delay_over_60_days": 1,
        "review_delay_over_90_days": 1,
        "review_delay_over_120_days": 1,
        "missing_first_activity_date": 1,
        "report_date_used_as_proxy": 0,
    }


def test_review_views_do_not_duplicate_rows_on_rerun(tmp_path: Path) -> None:
    db_path = tmp_path / "ccld.sqlite"
    normalized = _normalized_fixture()

    write_normalized_records(db_path, [normalized])
    write_normalized_records(db_path, [normalized])

    assert _row_count(db_path, "complaint_review_summary") == 1
    assert _row_count(db_path, "complaint_first_pass_review") == 1
    assert _row_count(db_path, "complaint_timeline_review") == 4
    assert _row_count(db_path, "field_source_traceability_review") == 21
    assert _row_count(db_path, "facility_complaint_summary") == 1
    assert _row_count(db_path, "facility_pattern_review") == 1
    assert _row_count(db_path, "delay_review_flags") == 1
    assert _row_count(db_path, "source_traceability_review") == 1


def test_review_views_include_delay_review_flag_columns(tmp_path: Path) -> None:
    db_path = tmp_path / "ccld.sqlite"
    normalized = _normalized_fixture()

    write_normalized_records(db_path, [normalized])

    expected_columns = {
        "review_delay_over_30_days",
        "review_delay_over_60_days",
        "review_delay_over_90_days",
        "review_delay_over_120_days",
        "missing_first_activity_date",
        "report_date_used_as_proxy",
    }
    assert expected_columns.issubset(_view_columns(db_path, "complaint_review_summary"))
    assert expected_columns.issubset(_view_columns(db_path, "delay_review_flags"))
    assert expected_columns.issubset(_view_columns(db_path, "complaint_timeline_review"))


def test_write_normalized_ccld_report_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "ccld.sqlite"
    normalized = _normalized_fixture()

    write_normalized_records(db_path, [normalized])
    write_normalized_records(db_path, [normalized])

    assert _row_count(db_path, "facilities") == 1
    assert _row_count(db_path, "source_documents") == 1
    assert _row_count(db_path, "complaints") == 1
    assert _row_count(db_path, "allegations") == 2
    assert _row_count(db_path, "extraction_audit") == 21


def test_written_complaint_and_allegations_link_to_parent_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "ccld.sqlite"
    normalized = _normalized_fixture()

    write_normalized_records(db_path, [normalized])

    with sqlite3.connect(db_path) as conn:
        complaint = conn.execute(
            """
            SELECT complaint_id, facility_id, document_id
            FROM complaints
            """
        ).fetchone()
        facility_id = conn.execute(
            "SELECT facility_id FROM facilities WHERE facility_id = ?",
            (complaint[1],),
        ).fetchone()
        document_id = conn.execute(
            "SELECT document_id FROM source_documents WHERE document_id = ?",
            (complaint[2],),
        ).fetchone()
        allegation_links = conn.execute(
            "SELECT DISTINCT complaint_id FROM allegations"
        ).fetchall()

    assert facility_id == (complaint[1],)
    assert document_id == (complaint[2],)
    assert allegation_links == [(complaint[0],)]


def test_extraction_audit_rows_are_stored_if_emitted(tmp_path: Path) -> None:
    db_path = tmp_path / "ccld.sqlite"
    normalized = _normalized_fixture()

    write_normalized_records(db_path, [normalized])

    with sqlite3.connect(db_path) as conn:
        audit_row = conn.execute(
            """
            SELECT document_id, field_name, extraction_method, extractor_version, confidence
            FROM extraction_audit
            WHERE field_name = 'facility_number'
            """
        ).fetchone()

    source_document = cast(dict[str, object], normalized["source_document"])
    assert audit_row == (
        source_document["document_id"],
        "facility_number",
        "ccld_facility_report_html_labels",
        "0.1.0",
        1.0,
    )


def _normalized_fixture() -> dict[str, object]:
    connector = CcldFacilityReportsConnector()
    raw_content = RAW_FIXTURE.read_bytes()
    document = SourceDocument(
        source_url=FIXTURE_URL,
        raw_path=RAW_FIXTURE,
        raw_sha256=sha256_bytes(raw_content),
        retrieved_at=RETRIEVED_AT,
        content_type="text/html",
    )
    return connector.normalize(connector.extract(document))


def _row_count(db_path: Path, table_name: str) -> int:
    with sqlite3.connect(db_path) as conn:
        count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    return cast(int, count)


def _source_traceability(db_path: Path) -> dict[str, object]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT source_url,
                   raw_sha256,
                   raw_path,
                   connector_name,
                   connector_version,
                   retrieved_at,
                   report_index
            FROM source_documents
            """
        ).fetchone()
    return dict(row)


def _complaint_delay_fields(db_path: Path) -> dict[str, object]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
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
    return dict(row)


def _complaint_review_summary(db_path: Path) -> dict[str, object]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT facility_number,
                   facility_name,
                   complaint_control_number,
                   complaint_received_date,
                   first_investigation_activity_date,
                   visit_date,
                   report_date,
                   date_signed,
                   finding,
                   allegation_count,
                   days_received_to_first_activity,
                   days_received_to_visit,
                   days_received_to_report,
                   days_report_to_signed,
                   review_delay_over_30_days,
                   review_delay_over_60_days,
                   review_delay_over_90_days,
                   review_delay_over_120_days,
                   missing_first_activity_date,
                   report_date_used_as_proxy,
                   source_url,
                   raw_path
            FROM complaint_review_summary
            """
        ).fetchone()
    return dict(row)


def _complaint_first_pass_review(db_path: Path) -> dict[str, object]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT facility_number,
                   facility_name,
                   complaint_control_number,
                   complaint_received_date,
                   visit_date,
                   report_date,
                   finding,
                   allegation_count,
                   review_flags_summary,
                   source_url,
                   raw_sha256,
                   raw_path,
                   connector_name,
                   connector_version,
                   retrieved_at,
                   report_index
            FROM complaint_first_pass_review
            """
        ).fetchone()
    return dict(row)


def _facility_complaint_summary(db_path: Path) -> dict[str, object]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT facility_number,
                   facility_name,
                   complaint_count,
                   allegation_count,
                   earliest_complaint_received_date,
                   latest_complaint_received_date,
                   records_with_delay_review_flags
            FROM facility_complaint_summary
            """
        ).fetchone()
    return dict(row)


def _facility_pattern_review(db_path: Path) -> dict[str, object]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT facility_number,
                   facility_name,
                   complaint_count,
                   source_document_count,
                   allegation_count,
                   allegation_categories,
                   substantiated_complaint_count,
                   unsubstantiated_complaint_count,
                   inconclusive_complaint_count,
                   unknown_finding_complaint_count,
                   missing_first_activity_count,
                   report_date_proxy_count,
                   records_with_review_flags,
                   earliest_complaint_received_date,
                   latest_complaint_received_date,
                   earliest_retrieved_at,
                   latest_retrieved_at
            FROM facility_pattern_review
            """
        ).fetchone()
    return dict(row)


def _delay_review_flags(db_path: Path) -> dict[str, object]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT facility_number,
                   complaint_control_number,
                   days_received_to_visit,
                   review_delay_over_30_days,
                   review_delay_over_60_days,
                   review_delay_over_90_days,
                   review_delay_over_120_days,
                   missing_first_activity_date,
                   report_date_used_as_proxy
            FROM delay_review_flags
            """
        ).fetchone()
    return dict(row)


def _source_traceability_review(db_path: Path) -> dict[str, object]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT facility_number,
                   facility_name,
                   source_url,
                   raw_sha256,
                   raw_path,
                   connector_name,
                   connector_version,
                   retrieved_at,
                   report_index
            FROM source_traceability_review
            """
        ).fetchone()
    return dict(row)


def _complaint_timeline_review(db_path: Path) -> list[dict[str, object]]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT timeline_sequence,
                   timeline_item_type,
                   timeline_source_field,
                   timeline_date,
                   source_url,
                   raw_sha256,
                   connector_name
            FROM complaint_timeline_review
            ORDER BY timeline_date, timeline_sequence
            """
        ).fetchall()
    return [dict(row) for row in rows]


def _field_source_traceability_review(db_path: Path) -> dict[str, object]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT facility_number,
                   complaint_control_number,
                   field_name,
                   extracted_value,
                   source_text,
                   source_section,
                   warning,
                   confidence,
                   extraction_method,
                   extractor_version,
                   source_url,
                   raw_sha256,
                   connector_name,
                   connector_version,
                   report_index
            FROM field_source_traceability_review
            WHERE field_name = 'facility_number'
            """
        ).fetchone()
    return dict(row)


def _view_value(db_path: Path, view_name: str, column_name: str) -> str:
    with sqlite3.connect(db_path) as conn:
        value = conn.execute(f"SELECT {column_name} FROM {view_name}").fetchone()[0]
    return cast(str, value)


def _view_columns(db_path: Path, view_name: str) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({view_name})")}