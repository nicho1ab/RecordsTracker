from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ccld_complaints.connectors.base import SourceDocument, SourceDocumentCandidate
from ccld_complaints.connectors.ccld import CcldFacilityReportsConnector, FacilityIngestionResult
from ccld_complaints.connectors.ccld.facility_reports import ingest_facility_reports_for_facility
from ccld_complaints.storage.sqlite import initialize_database
from ccld_complaints.utils.hash import sha256_bytes

DEFAULT_SAMPLE_DB_PATH = Path("data/processed/ccld.sqlite")
DEFAULT_CCLD_FIXTURE_DIR = Path("tests/fixtures/ccld")
DEFAULT_SAMPLE_FACILITY_NUMBER = "157806098"
DEFAULT_SAMPLE_RETRIEVED_AT = "2026-06-10T00:00:00+00:00"
_REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class SampleDatabaseResult:
    db_path: Path
    ingestion: FacilityIngestionResult


def populate_sample_database(
    db_path: Path = DEFAULT_SAMPLE_DB_PATH,
    *,
    fixture_dir: Path = DEFAULT_CCLD_FIXTURE_DIR,
) -> SampleDatabaseResult:
    initialize_database(db_path)
    connector = CcldFacilityReportsConnector(db_path=db_path, schema_dir=_REPO_ROOT / "schemas")
    detail_fixture = _resolve_fixture_path(
        fixture_dir / "raw" / f"{DEFAULT_SAMPLE_FACILITY_NUMBER}_facility_detail.html"
    )

    result = ingest_facility_reports_for_facility(
        facility_number=DEFAULT_SAMPLE_FACILITY_NUMBER,
        connector=connector,
        facility_detail_html=detail_fixture.read_text(encoding="utf-8"),
        discovered_at=DEFAULT_SAMPLE_RETRIEVED_AT,
        load_document=lambda candidate: _load_report_fixture(candidate, fixture_dir),
    )

    return SampleDatabaseResult(db_path=db_path, ingestion=result)


def datasette_command(db_path: Path) -> str:
    return f'datasette "{db_path.as_posix()}"'


def _load_report_fixture(
    candidate: SourceDocumentCandidate,
    fixture_dir: Path,
) -> SourceDocument | None:
    raw_path = fixture_dir / "raw" / f"{candidate.facility_number}_inx{candidate.report_index}.html"
    resolved_raw_path = _resolve_fixture_path(raw_path)
    if not resolved_raw_path.exists():
        return None

    raw_content = resolved_raw_path.read_bytes()
    return SourceDocument(
        source_url=candidate.source_url,
        raw_path=_repo_relative_path(resolved_raw_path),
        raw_sha256=sha256_bytes(raw_content),
        retrieved_at=DEFAULT_SAMPLE_RETRIEVED_AT,
        content_type="text/html",
    )


def _resolve_fixture_path(path: Path) -> Path:
    if path.exists() or path.is_absolute():
        return path
    return _REPO_ROOT / path


def _repo_relative_path(path: Path) -> Path:
    try:
        return path.relative_to(_REPO_ROOT)
    except ValueError:
        return path