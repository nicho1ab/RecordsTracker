"""Focused unit tests for the stakeholder facility overview extract module."""
from __future__ import annotations

import csv
import json
import sqlite3
import zipfile
from pathlib import Path

from ccld_complaints.stakeholder_extract import (
    UNKNOWN,
    FacilityReferenceError,
    export_stakeholder_facility_overview,
    is_substantiated_equivalent,
    read_facility_reference_csv,
)

# ---------------------------------------------------------------------------
# Helper: in-memory SQLite with minimal schema
# ---------------------------------------------------------------------------

_MINI_SCHEMA = """
CREATE TABLE IF NOT EXISTS facilities (
    facility_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    external_facility_number TEXT NOT NULL,
    facility_name TEXT,
    facility_type TEXT,
    licensee_name TEXT,
    county TEXT,
    status TEXT,
    capacity INTEGER,
    regional_office TEXT
);

CREATE TABLE IF NOT EXISTS source_documents (
    document_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    facility_id TEXT NOT NULL,
    source_url TEXT NOT NULL UNIQUE,
    retrieved_at TEXT NOT NULL,
    raw_sha256 TEXT,
    connector_name TEXT NOT NULL,
    connector_version TEXT NOT NULL,
    raw_path TEXT,
    document_type TEXT,
    report_index INTEGER,
    http_status INTEGER,
    content_type TEXT
);

CREATE TABLE IF NOT EXISTS complaints (
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
    days_received_to_visit INTEGER,
    days_received_to_report INTEGER,
    days_report_to_signed INTEGER,
    review_delay_over_30_days INTEGER NOT NULL DEFAULT 0,
    review_delay_over_60_days INTEGER NOT NULL DEFAULT 0,
    review_delay_over_90_days INTEGER NOT NULL DEFAULT 0,
    review_delay_over_120_days INTEGER NOT NULL DEFAULT 0,
    missing_first_activity_date INTEGER NOT NULL DEFAULT 0,
    report_date_used_as_proxy INTEGER NOT NULL DEFAULT 0,
    extraction_confidence REAL
);

CREATE TABLE IF NOT EXISTS allegations (
    allegation_id TEXT PRIMARY KEY,
    complaint_id TEXT NOT NULL,
    allegation_text TEXT NOT NULL,
    allegation_category TEXT,
    finding TEXT,
    extraction_confidence REAL
);
"""


def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(_MINI_SCHEMA)
    conn.row_factory = sqlite3.Row
    return conn


def _insert_facility(
    conn: sqlite3.Connection, *, fid: str, fnum: str, name: str | None = "Test Facility"
) -> None:
    conn.execute(
        """
        INSERT INTO facilities
            (facility_id, source_id, external_facility_number, facility_name,
             facility_type, status, county)
        VALUES (?, 'ccld', ?, ?, 'Child Care Center', 'Licensed', 'Alameda')
        """,
        (fid, fnum, name),
    )


def _insert_source_doc(
    conn: sqlite3.Connection, *, doc_id: str, fid: str, url: str, sha256: str = "abc123"
) -> None:
    conn.execute(
        """
        INSERT INTO source_documents
            (document_id, source_id, facility_id, source_url, retrieved_at,
             raw_sha256, connector_name, connector_version)
        VALUES (?, 'ccld', ?, ?, '2024-01-01T00:00:00Z', ?, 'ccld', '1.0')
        """,
        (doc_id, fid, url, sha256),
    )


def _insert_complaint(
    conn: sqlite3.Connection,
    *,
    cid: str,
    fid: str,
    doc_id: str,
    control_number: str,
    finding: str = "Unsubstantiated",
    received_date: str = "2022-04-07",
    report_date: str = "2022-06-01",
) -> None:
    conn.execute(
        """
        INSERT INTO complaints
            (complaint_id, facility_id, document_id, complaint_control_number,
             complaint_received_date, report_date, finding)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (cid, fid, doc_id, control_number, received_date, report_date, finding),
    )


# ---------------------------------------------------------------------------
# is_substantiated_equivalent
# ---------------------------------------------------------------------------

class TestIsSubstantiatedEquivalent:
    def test_substantiated_matches(self) -> None:
        assert is_substantiated_equivalent("Substantiated") is True

    def test_founded_matches(self) -> None:
        assert is_substantiated_equivalent("Founded") is True

    def test_sustained_matches(self) -> None:
        assert is_substantiated_equivalent("Sustained") is True

    def test_case_insensitive(self) -> None:
        assert is_substantiated_equivalent("SUBSTANTIATED") is True

    def test_unsubstantiated_excluded(self) -> None:
        assert is_substantiated_equivalent("Unsubstantiated") is False

    def test_not_substantiated_excluded(self) -> None:
        assert is_substantiated_equivalent("Not Substantiated") is False

    def test_empty_string_false(self) -> None:
        assert is_substantiated_equivalent("") is False

    def test_none_false(self) -> None:
        assert is_substantiated_equivalent(None) is False

    def test_unrelated_string_false(self) -> None:
        assert is_substantiated_equivalent("Pending") is False


# ---------------------------------------------------------------------------
# Test 1: Facility aggregation counts loaded complaints correctly
# ---------------------------------------------------------------------------

class TestFacilityAggregation:
    def test_counts_loaded_complaints_correctly(self, tmp_path: Path) -> None:
        conn = _make_db()
        _insert_facility(conn, fid="f1", fnum="100001")
        _insert_facility(conn, fid="f2", fnum="100002")
        _insert_source_doc(conn, doc_id="d1", fid="f1", url="http://example.test/1")
        _insert_source_doc(conn, doc_id="d2", fid="f1", url="http://example.test/2")
        _insert_source_doc(conn, doc_id="d3", fid="f2", url="http://example.test/3")
        _insert_complaint(conn, cid="c1", fid="f1", doc_id="d1", control_number="CR-001")
        _insert_complaint(conn, cid="c2", fid="f1", doc_id="d2", control_number="CR-002")
        _insert_complaint(conn, cid="c3", fid="f2", doc_id="d3", control_number="CR-003")
        conn.commit()

        db_path = tmp_path / "test.sqlite"
        # Materialise to file so export_stakeholder_facility_overview can open it
        file_conn = sqlite3.connect(db_path)
        conn.backup(file_conn)
        file_conn.close()

        result = export_stakeholder_facility_overview(db_path, tmp_path / "extracts")

        assert result.facility_row_count == 2
        # Read CSV to verify counts
        rows = _read_csv(result.facility_overview_path)
        by_num = {r["FacilityNumber"]: r for r in rows}
        assert by_num["100001"]["LoadedComplaintCount"] == "2"
        assert by_num["100002"]["LoadedComplaintCount"] == "1"

    def test_substantiated_count_correct(self, tmp_path: Path) -> None:
        conn = _make_db()
        _insert_facility(conn, fid="f1", fnum="100001")
        _insert_source_doc(conn, doc_id="d1", fid="f1", url="http://example.test/1")
        _insert_source_doc(conn, doc_id="d2", fid="f1", url="http://example.test/2")
        _insert_source_doc(conn, doc_id="d3", fid="f1", url="http://example.test/3")
        _insert_complaint(
            conn, cid="c1", fid="f1", doc_id="d1",
            control_number="CR-001", finding="Substantiated",
        )
        _insert_complaint(
            conn, cid="c2", fid="f1", doc_id="d2",
            control_number="CR-002", finding="Unsubstantiated",
        )
        _insert_complaint(
            conn, cid="c3", fid="f1", doc_id="d3",
            control_number="CR-003", finding="Founded",
        )
        conn.commit()

        db_path = tmp_path / "test.sqlite"
        file_conn = sqlite3.connect(db_path)
        conn.backup(file_conn)
        file_conn.close()

        result = export_stakeholder_facility_overview(db_path, tmp_path / "extracts")

        rows = _read_csv(result.facility_overview_path)
        assert rows[0]["SubstantiatedOrEquivalentCount"] == "2"


# ---------------------------------------------------------------------------
# Test 2: Substantiated/equivalent complaints are counted and listed
# ---------------------------------------------------------------------------

class TestSubstantiatedComplaints:
    def test_substantiated_listed_in_substantiated_csv(self, tmp_path: Path) -> None:
        conn = _make_db()
        _insert_facility(conn, fid="f1", fnum="100001", name="Alpha Care Center")
        _insert_source_doc(conn, doc_id="d1", fid="f1", url="http://example.test/report1")
        _insert_source_doc(conn, doc_id="d2", fid="f1", url="http://example.test/report2")
        _insert_complaint(
            conn, cid="c1", fid="f1", doc_id="d1",
            control_number="CR-SUB-001", finding="Substantiated",
        )
        _insert_complaint(
            conn, cid="c2", fid="f1", doc_id="d2",
            control_number="CR-UNSUB-001", finding="Unsubstantiated",
        )
        conn.commit()

        db_path = tmp_path / "test.sqlite"
        file_conn = sqlite3.connect(db_path)
        conn.backup(file_conn)
        file_conn.close()

        result = export_stakeholder_facility_overview(db_path, tmp_path / "extracts")

        assert result.substantiated_complaint_row_count == 1
        rows = _read_csv(result.substantiated_complaints_path)
        assert len(rows) == 1
        assert rows[0]["ComplaintControlNumber"] == "CR-SUB-001"
        assert rows[0]["FindingOrResolution"] == "Substantiated"
        assert rows[0]["FacilityName"] == "Alpha Care Center"

    def test_founded_and_sustained_also_listed(self, tmp_path: Path) -> None:
        conn = _make_db()
        _insert_facility(conn, fid="f1", fnum="100001")
        _insert_source_doc(conn, doc_id="d1", fid="f1", url="http://example.test/1")
        _insert_source_doc(conn, doc_id="d2", fid="f1", url="http://example.test/2")
        _insert_complaint(
            conn, cid="c1", fid="f1", doc_id="d1",
            control_number="CR-001", finding="Founded",
        )
        _insert_complaint(
            conn, cid="c2", fid="f1", doc_id="d2",
            control_number="CR-002", finding="Sustained",
        )
        conn.commit()

        db_path = tmp_path / "test.sqlite"
        file_conn = sqlite3.connect(db_path)
        conn.backup(file_conn)
        file_conn.close()

        result = export_stakeholder_facility_overview(db_path, tmp_path / "extracts")

        assert result.substantiated_complaint_row_count == 2


# ---------------------------------------------------------------------------
# Test 3: Missing facility name/date/source URL uses safe fallback text
# ---------------------------------------------------------------------------

class TestSafeFallbacks:
    def test_null_facility_name_uses_unknown(self, tmp_path: Path) -> None:
        conn = _make_db()
        _insert_facility(conn, fid="f1", fnum="100001", name=None)
        _insert_source_doc(conn, doc_id="d1", fid="f1", url="http://example.test/1")
        _insert_complaint(
            conn, cid="c1", fid="f1", doc_id="d1",
            control_number="CR-001", finding="Substantiated",
        )
        conn.commit()

        db_path = tmp_path / "test.sqlite"
        file_conn = sqlite3.connect(db_path)
        conn.backup(file_conn)
        file_conn.close()

        result = export_stakeholder_facility_overview(db_path, tmp_path / "extracts")

        facility_rows = _read_csv(result.facility_overview_path)
        sub_rows = _read_csv(result.substantiated_complaints_path)
        assert facility_rows[0]["FacilityName"] == UNKNOWN
        assert sub_rows[0]["FacilityName"] == UNKNOWN

    def test_null_dates_use_unknown(self, tmp_path: Path) -> None:
        conn = _make_db()
        _insert_facility(conn, fid="f1", fnum="100001")
        _insert_source_doc(conn, doc_id="d1", fid="f1", url="http://example.test/1")
        conn.execute(
            """
            INSERT INTO complaints
                (complaint_id, facility_id, document_id, complaint_control_number, finding)
            VALUES ('c1', 'f1', 'd1', 'CR-001', 'Substantiated')
            """
        )
        conn.commit()

        db_path = tmp_path / "test.sqlite"
        file_conn = sqlite3.connect(db_path)
        conn.backup(file_conn)
        file_conn.close()

        result = export_stakeholder_facility_overview(db_path, tmp_path / "extracts")

        facility_rows = _read_csv(result.facility_overview_path)
        sub_rows = _read_csv(result.substantiated_complaints_path)
        assert facility_rows[0]["EarliestComplaintDate"] == UNKNOWN
        assert facility_rows[0]["MostRecentComplaintDate"] == UNKNOWN
        assert sub_rows[0]["ComplaintReceivedDate"] == UNKNOWN
        assert sub_rows[0]["ReportDate"] == UNKNOWN

    def test_null_source_url_uses_unknown(self, tmp_path: Path) -> None:
        conn = _make_db()
        _insert_facility(conn, fid="f1", fnum="100001")
        conn.execute(
            """
            INSERT INTO source_documents
                (document_id, source_id, facility_id, source_url, retrieved_at,
                 raw_sha256, connector_name, connector_version)
            VALUES ('d1', 'ccld', 'f1', 'http://example.test/1', '2024-01-01T00:00:00Z',
                    NULL, 'ccld', '1.0')
            """
        )
        _insert_complaint(
            conn, cid="c1", fid="f1", doc_id="d1",
            control_number="CR-001", finding="Substantiated",
        )
        conn.commit()

        db_path = tmp_path / "test.sqlite"
        file_conn = sqlite3.connect(db_path)
        conn.backup(file_conn)
        file_conn.close()

        result = export_stakeholder_facility_overview(db_path, tmp_path / "extracts")

        sub_rows = _read_csv(result.substantiated_complaints_path)
        assert sub_rows[0]["RawHashOrArtifactReference"] == UNKNOWN


# ---------------------------------------------------------------------------
# Test 4: Empty input produces headers, README, manifest, and ZIP
# ---------------------------------------------------------------------------

class TestEmptyInput:
    def test_nonexistent_db_produces_valid_empty_outputs(self, tmp_path: Path) -> None:
        db_path = tmp_path / "does_not_exist.sqlite"
        result = export_stakeholder_facility_overview(db_path, tmp_path / "extracts")

        assert result.facility_row_count == 0
        assert result.substantiated_complaint_row_count == 0

        # CSV files exist and have correct headers
        facility_rows = _read_csv_raw(result.facility_overview_path)
        assert facility_rows[0] == list(_facility_overview_headers())
        assert len(facility_rows) == 1  # header only

        sub_rows = _read_csv_raw(result.substantiated_complaints_path)
        assert sub_rows[0] == list(_substantiated_complaints_headers())
        assert len(sub_rows) == 1  # header only

    def test_empty_output_readme_has_required_caution_language(self, tmp_path: Path) -> None:
        db_path = tmp_path / "does_not_exist.sqlite"
        result = export_stakeholder_facility_overview(db_path, tmp_path / "extracts")

        readme = result.readme_path.read_text(encoding="utf-8")
        assert "source of record" in readme
        assert "does not make legal conclusions" in readme
        assert "does not make facility-wide conclusions" in readme
        assert "not independently verified" in readme
        assert "raw narrative" in readme
        assert "does not claim to be source-complete" in readme
        assert "zero" in readme.lower() or "empty" in readme.lower() or "counts" in readme.lower()

    def test_empty_output_manifest_counts_are_zero(self, tmp_path: Path) -> None:
        db_path = tmp_path / "does_not_exist.sqlite"
        result = export_stakeholder_facility_overview(db_path, tmp_path / "extracts")

        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        assert manifest["facility_row_count"] == 0
        assert manifest["substantiated_complaint_row_count"] == 0
        assert "limitations" in manifest
        assert manifest["script_name"] == "export-stakeholder-facility-overview.ps1"

    def test_empty_output_zip_created(self, tmp_path: Path) -> None:
        db_path = tmp_path / "does_not_exist.sqlite"
        result = export_stakeholder_facility_overview(db_path, tmp_path / "extracts")

        assert result.zip_path.exists()
        with zipfile.ZipFile(result.zip_path) as zf:
            names = zf.namelist()
        assert "facility-overview.csv" in names
        assert "substantiated-complaints.csv" in names
        assert "README.md" in names
        assert "manifest.json" in names

    def test_empty_output_no_misleading_count_claims(self, tmp_path: Path) -> None:
        db_path = tmp_path / "does_not_exist.sqlite"
        result = export_stakeholder_facility_overview(db_path, tmp_path / "extracts")

        readme = result.readme_path.read_text(encoding="utf-8")
        # README must not claim zero means no complaints exist
        assert "do not prove" in readme or "does not prove" in readme or "not prove" in readme


# ---------------------------------------------------------------------------
# Test 5: Raw narrative fields not included in either CSV
# ---------------------------------------------------------------------------

class TestNoRawNarrative:
    def test_allegation_text_not_in_facility_overview_csv(self, tmp_path: Path) -> None:
        conn = _make_db()
        _insert_facility(conn, fid="f1", fnum="100001")
        _insert_source_doc(conn, doc_id="d1", fid="f1", url="http://example.test/1")
        _insert_complaint(conn, cid="c1", fid="f1", doc_id="d1", control_number="CR-001")
        conn.execute(
            """
            INSERT INTO allegations (allegation_id, complaint_id, allegation_text)
            VALUES ('a1', 'c1', 'SENTINEL_NARRATIVE_TEXT_SHOULD_NOT_APPEAR')
            """
        )
        conn.commit()

        db_path = tmp_path / "test.sqlite"
        file_conn = sqlite3.connect(db_path)
        conn.backup(file_conn)
        file_conn.close()

        result = export_stakeholder_facility_overview(db_path, tmp_path / "extracts")

        content = result.facility_overview_path.read_text(encoding="utf-8")
        assert "SENTINEL_NARRATIVE_TEXT_SHOULD_NOT_APPEAR" not in content

    def test_allegation_text_not_in_substantiated_csv(self, tmp_path: Path) -> None:
        conn = _make_db()
        _insert_facility(conn, fid="f1", fnum="100001")
        _insert_source_doc(conn, doc_id="d1", fid="f1", url="http://example.test/1")
        _insert_complaint(
            conn, cid="c1", fid="f1", doc_id="d1",
            control_number="CR-001", finding="Substantiated",
        )
        conn.execute(
            """
            INSERT INTO allegations (allegation_id, complaint_id, allegation_text)
            VALUES ('a1', 'c1', 'SENTINEL_NARRATIVE_TEXT_SHOULD_NOT_APPEAR')
            """
        )
        conn.commit()

        db_path = tmp_path / "test.sqlite"
        file_conn = sqlite3.connect(db_path)
        conn.backup(file_conn)
        file_conn.close()

        result = export_stakeholder_facility_overview(db_path, tmp_path / "extracts")

        content = result.substantiated_complaints_path.read_text(encoding="utf-8")
        assert "SENTINEL_NARRATIVE_TEXT_SHOULD_NOT_APPEAR" not in content

    def test_csv_headers_contain_no_narrative_column(self, tmp_path: Path) -> None:
        db_path = tmp_path / "does_not_exist.sqlite"
        export_stakeholder_facility_overview(db_path, tmp_path / "extracts")

        facility_headers = _facility_overview_headers()
        sub_headers = _substantiated_complaints_headers()

        narrative_keywords = {"text", "narrative", "allegation_text", "description", "summary"}
        for header in facility_headers:
            assert header.lower() not in narrative_keywords, f"Unexpected column: {header}"
        for header in sub_headers:
            assert header.lower() not in narrative_keywords, f"Unexpected column: {header}"


# ---------------------------------------------------------------------------
# Test 6: Manifest counts match generated CSV row counts
# ---------------------------------------------------------------------------

class TestManifestCounts:
    def test_manifest_counts_match_csv_row_counts(self, tmp_path: Path) -> None:
        conn = _make_db()
        _insert_facility(conn, fid="f1", fnum="100001")
        _insert_facility(conn, fid="f2", fnum="100002")
        _insert_source_doc(conn, doc_id="d1", fid="f1", url="http://example.test/1")
        _insert_source_doc(conn, doc_id="d2", fid="f2", url="http://example.test/2")
        _insert_complaint(
            conn, cid="c1", fid="f1", doc_id="d1",
            control_number="CR-001", finding="Substantiated",
        )
        _insert_complaint(
            conn, cid="c2", fid="f2", doc_id="d2",
            control_number="CR-002", finding="Unsubstantiated",
        )
        conn.commit()

        db_path = tmp_path / "test.sqlite"
        file_conn = sqlite3.connect(db_path)
        conn.backup(file_conn)
        file_conn.close()

        result = export_stakeholder_facility_overview(db_path, tmp_path / "extracts")

        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

        facility_csv_rows = len(_read_csv(result.facility_overview_path))
        sub_csv_rows = len(_read_csv(result.substantiated_complaints_path))

        assert manifest["facility_row_count"] == facility_csv_rows
        assert manifest["substantiated_complaint_row_count"] == sub_csv_rows
        assert manifest["facility_row_count"] == result.facility_row_count
        sub_count = result.substantiated_complaint_row_count
        assert manifest["substantiated_complaint_row_count"] == sub_count

    def test_manifest_output_files_list_matches_actual_files(self, tmp_path: Path) -> None:
        db_path = tmp_path / "does_not_exist.sqlite"
        result = export_stakeholder_facility_overview(db_path, tmp_path / "extracts")

        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        listed = set(manifest["output_files"])
        expected = {
            "facility-overview.csv",
            "substantiated-complaints.csv",
            "README.md",
            "manifest.json",
        }
        assert expected.issubset(listed)
        # At least one .zip file listed
        assert any(f.endswith(".zip") for f in listed)


# ---------------------------------------------------------------------------
# Tests: facility reference CSV input
# ---------------------------------------------------------------------------


class TestFacilityReferenceInput:
    def test_reference_only_facility_has_zero_loaded_counts(
        self, tmp_path: Path
    ) -> None:
        """A reference-only facility (no loaded complaints) appears with zero counts."""
        ref_csv = tmp_path / "facilities.csv"
        _write_ref_csv(
            ref_csv,
            [{"FacilityNumber": "999001", "FacilityName": "Reference Only Center"}],
            header=["FacilityNumber", "FacilityName"],
        )
        db_path = tmp_path / "does_not_exist.sqlite"

        result = export_stakeholder_facility_overview(
            db_path, tmp_path / "extracts",
            facility_reference_csv=ref_csv,
        )

        rows = _read_csv(result.facility_overview_path)
        assert len(rows) == 1
        row = rows[0]
        assert row["FacilityNumber"] == "999001"
        assert row["FacilityName"] == "Reference Only Center"
        assert row["LoadedComplaintCount"] == "0"
        assert row["SubstantiatedOrEquivalentCount"] == "0"
        assert row["ComplaintDataLoadedStatus"] == "No complaints loaded"

    def test_reference_only_facility_limitations_do_not_imply_no_complaints(
        self, tmp_path: Path
    ) -> None:
        """Limitations text must not imply zero means no public complaints exist."""
        ref_csv = tmp_path / "facilities.csv"
        _write_ref_csv(
            ref_csv,
            [{"FacilityNumber": "999001", "FacilityName": "Test Center"}],
            header=["FacilityNumber", "FacilityName"],
        )
        db_path = tmp_path / "does_not_exist.sqlite"

        result = export_stakeholder_facility_overview(
            db_path, tmp_path / "extracts",
            facility_reference_csv=ref_csv,
        )

        rows = _read_csv(result.facility_overview_path)
        limitations = rows[0]["Limitations"]
        # Must carry the standard limitations sentence
        assert "source-completeness" in limitations or "source of record" in limitations

    def test_complaint_loaded_facility_merges_reference_metadata(
        self, tmp_path: Path
    ) -> None:
        """Reference metadata (city) enriches a facility that has loaded complaints."""
        conn = _make_db()
        _insert_facility(conn, fid="f1", fnum="100001", name="Loaded Center")
        _insert_source_doc(conn, doc_id="d1", fid="f1", url="http://example.test/1")
        _insert_complaint(
            conn, cid="c1", fid="f1", doc_id="d1",
            control_number="CR-001", finding="Substantiated",
        )
        conn.commit()
        db_path = tmp_path / "test.sqlite"
        _save_db(conn, db_path)

        ref_csv = tmp_path / "facilities.csv"
        _write_ref_csv(
            ref_csv,
            [{
                "FacilityNumber": "100001",
                "FacilityName": "Loaded Center",
                "City": "Sacramento",
                "County": "Sacramento County",
                "Status": "Licensed",
            }],
            header=["FacilityNumber", "FacilityName", "City", "County", "Status"],
        )

        result = export_stakeholder_facility_overview(
            db_path, tmp_path / "extracts",
            facility_reference_csv=ref_csv,
        )

        rows = _read_csv(result.facility_overview_path)
        assert len(rows) == 1
        row = rows[0]
        assert row["FacilityNumber"] == "100001"
        assert row["LoadedComplaintCount"] == "1"
        assert row["SubstantiatedOrEquivalentCount"] == "1"
        # City is reference-only (not in DB schema); it should come from reference CSV
        assert row["City"] == "Sacramento"

    def test_missing_facility_number_column_raises_clearly(
        self, tmp_path: Path
    ) -> None:
        """CSV without a recognised facility number column raises FacilityReferenceError."""
        ref_csv = tmp_path / "bad.csv"
        _write_ref_csv(
            ref_csv,
            [{"Name": "Test", "Type": "Child Care"}],
            header=["Name", "Type"],
        )

        import pytest

        with pytest.raises(FacilityReferenceError) as exc_info:
            read_facility_reference_csv(ref_csv)

        assert "facility" in str(exc_info.value).casefold()
        assert "number" in str(exc_info.value).casefold()

    def test_duplicate_reference_rows_keep_first(self, tmp_path: Path) -> None:
        """When the reference CSV has duplicate facility numbers, first row wins."""
        ref_csv = tmp_path / "facilities.csv"
        _write_ref_csv(
            ref_csv,
            [
                {"FacilityNumber": "100001", "FacilityName": "First Name"},
                {"FacilityNumber": "100001", "FacilityName": "Second Name"},
            ],
            header=["FacilityNumber", "FacilityName"],
        )

        records = read_facility_reference_csv(ref_csv)

        assert len(records) == 1
        assert records[0]["facility_name"] == "First Name"

    def test_reference_input_no_raw_narrative_in_output(
        self, tmp_path: Path
    ) -> None:
        """Raw narrative text from allegations is not present even with reference input."""
        conn = _make_db()
        _insert_facility(conn, fid="f1", fnum="100001")
        _insert_source_doc(conn, doc_id="d1", fid="f1", url="http://example.test/1")
        _insert_complaint(
            conn, cid="c1", fid="f1", doc_id="d1",
            control_number="CR-001", finding="Substantiated",
        )
        conn.execute(
            """
            INSERT INTO allegations (allegation_id, complaint_id, allegation_text)
            VALUES ('a1', 'c1', 'SENTINEL_NARRATIVE_REFERENCE_TEST')
            """
        )
        conn.commit()
        db_path = tmp_path / "test.sqlite"
        _save_db(conn, db_path)

        ref_csv = tmp_path / "facilities.csv"
        _write_ref_csv(
            ref_csv,
            [{"FacilityNumber": "100001", "FacilityName": "Test Center"}],
            header=["FacilityNumber", "FacilityName"],
        )

        result = export_stakeholder_facility_overview(
            db_path, tmp_path / "extracts",
            facility_reference_csv=ref_csv,
        )

        for output_file in [
            result.facility_overview_path,
            result.substantiated_complaints_path,
        ]:
            assert "SENTINEL_NARRATIVE_REFERENCE_TEST" not in output_file.read_text(
                encoding="utf-8"
            )

    def test_manifest_includes_reference_counts(self, tmp_path: Path) -> None:
        """Manifest includes facility_reference_csv, _row_count, _matched_count."""
        conn = _make_db()
        _insert_facility(conn, fid="f1", fnum="100001")
        _insert_source_doc(conn, doc_id="d1", fid="f1", url="http://example.test/1")
        _insert_complaint(
            conn, cid="c1", fid="f1", doc_id="d1",
            control_number="CR-001", finding="Unsubstantiated",
        )
        conn.commit()
        db_path = tmp_path / "test.sqlite"
        _save_db(conn, db_path)

        ref_csv = tmp_path / "facilities.csv"
        _write_ref_csv(
            ref_csv,
            [
                {"FacilityNumber": "100001", "FacilityName": "Matched"},
                {"FacilityNumber": "999999", "FacilityName": "Unmatched"},
            ],
            header=["FacilityNumber", "FacilityName"],
        )

        result = export_stakeholder_facility_overview(
            db_path, tmp_path / "extracts",
            facility_reference_csv=ref_csv,
        )

        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        assert "facility_reference_csv" in manifest
        assert manifest["facility_reference_row_count"] == 2
        assert manifest["facility_reference_matched_count"] == 1
        # Total facility rows = 1 loaded + 1 reference-only = 2
        assert result.facility_row_count == 2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_ref_csv(path: Path, rows: list[dict[str, str]], header: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _save_db(conn: sqlite3.Connection, path: Path) -> None:
    file_conn = sqlite3.connect(path)
    conn.backup(file_conn)
    file_conn.close()


def _read_csv(path: Path) -> list[dict[str, str]]:
    """Read CSV as list of dicts (excludes header row)."""
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _read_csv_raw(path: Path) -> list[list[str]]:
    """Read CSV as list of lists (includes header row)."""
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.reader(f))


def _facility_overview_headers() -> tuple[str, ...]:
    from ccld_complaints.stakeholder_extract import _FACILITY_OVERVIEW_FIELDS
    return _FACILITY_OVERVIEW_FIELDS


def _substantiated_complaints_headers() -> tuple[str, ...]:
    from ccld_complaints.stakeholder_extract import _SUBSTANTIATED_COMPLAINTS_FIELDS
    return _SUBSTANTIATED_COMPLAINTS_FIELDS
