import sqlite3
from pathlib import Path

from ccld_complaints.storage.sqlite import initialize_database


def test_initialize_database(tmp_path: Path) -> None:
    db = tmp_path / "test.sqlite"
    initialize_database(db)
    assert db.exists()


def test_initialize_database_creates_review_views(tmp_path: Path) -> None:
    db = tmp_path / "test.sqlite"

    initialize_database(db)

    with sqlite3.connect(db) as conn:
        views = {
            row[0]
            for row in conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'view'
                """
            ).fetchall()
        }

    assert {
        "complaint_review_summary",
        "complaint_first_pass_review",
        "complaint_timeline_review",
        "facility_complaint_summary",
        "delay_review_flags",
        "source_traceability_review",
    }.issubset(views)


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


def test_initialize_database_recreates_review_views_on_rerun(tmp_path: Path) -> None:
    db = tmp_path / "test.sqlite"

    initialize_database(db)
    initialize_database(db)

    with sqlite3.connect(db) as conn:
        view_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM sqlite_master
            WHERE type = 'view'
              AND name IN (
                  'complaint_review_summary',
                  'complaint_first_pass_review',
                  'complaint_timeline_review',
                  'facility_complaint_summary',
                  'delay_review_flags',
                  'source_traceability_review'
              )
            """
        ).fetchone()[0]

    assert view_count == 6
