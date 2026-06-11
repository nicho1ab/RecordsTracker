import sqlite3
from pathlib import Path

from ccld_complaints.storage.sqlite import initialize_database


def test_initialize_database(tmp_path: Path) -> None:
    db = tmp_path / "test.sqlite"
    initialize_database(db)
    assert db.exists()


def test_initialize_database_backfills_existing_complaint_delay_columns(
    tmp_path: Path,
) -> None:
    db = tmp_path / "test.sqlite"
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            CREATE TABLE complaints (
                complaint_id TEXT PRIMARY KEY,
                facility_id TEXT NOT NULL,
                document_id TEXT NOT NULL,
                complaint_control_number TEXT,
                complaint_received_date TEXT,
                first_investigation_activity_date TEXT,
                visit_date TEXT,
                report_date TEXT,
                date_signed TEXT,
                finding TEXT,
                days_received_to_first_activity INTEGER,
                days_received_to_report INTEGER,
                extraction_confidence REAL
            )
            """
        )

    initialize_database(db)

    with sqlite3.connect(db) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(complaints)")}

    assert "days_received_to_visit" in columns
    assert "days_report_to_signed" in columns
    assert "review_delay_over_30_days" in columns
    assert "review_delay_over_60_days" in columns
    assert "review_delay_over_90_days" in columns
    assert "review_delay_over_120_days" in columns
    assert "missing_first_activity_date" in columns
    assert "report_date_used_as_proxy" in columns
