from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from ccld_complaints.extraction.dates import days_between, parse_date_or_none
from ccld_complaints.local_sample import populate_sample_database


def test_complaint_date_order_and_delay_columns_are_consistent(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "ccld.sqlite"

    populate_sample_database(db_path)

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT complaint_id,
                   complaint_received_date,
                   first_investigation_activity_date,
                   visit_date,
                   report_date,
                   date_signed,
                   days_received_to_first_activity,
                   days_received_to_visit,
                   days_received_to_report,
                   days_report_to_signed
            FROM complaints
            ORDER BY complaint_id
            """
        ).fetchall()

    for row in rows:
        complaint = dict(row)
        received_date = parse_date_or_none(complaint["complaint_received_date"])
        first_activity_date = parse_date_or_none(
            complaint["first_investigation_activity_date"]
        )
        visit_date = parse_date_or_none(complaint["visit_date"])
        report_date = parse_date_or_none(complaint["report_date"])
        signed_date = parse_date_or_none(complaint["date_signed"])

        assert _is_ordered(received_date, first_activity_date), complaint
        assert _is_ordered(received_date, visit_date), complaint
        assert _is_ordered(received_date, report_date), complaint
        assert _is_ordered(report_date, signed_date), complaint
        assert complaint["days_received_to_first_activity"] == days_between(
            received_date, first_activity_date
        )
        assert complaint["days_received_to_visit"] == days_between(
            received_date, visit_date
        )
        assert complaint["days_received_to_report"] == days_between(
            received_date, report_date
        )
        assert complaint["days_report_to_signed"] == days_between(
            report_date, signed_date
        )


def _is_ordered(start_value: date | None, end_value: date | None) -> bool:
    if start_value is None or end_value is None:
        return True
    return start_value <= end_value
