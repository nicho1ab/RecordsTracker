from __future__ import annotations

import io
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Connection

from ccld_complaints.connectors.ccld import facility_reports as ccld_facility_reports
from ccld_complaints.hosted_app.batch_complaint_retrieval import (
    BatchComplaintRetrievalOptions,
    build_parser,
    build_plan,
    run_batch,
    split_date_range,
)
from ccld_complaints.hosted_app.ccld_retrieval_jobs import (
    CcldRetrievalConfig,
    CcldRetrievalContext,
    hosted_ccld_retrieval_jobs,
)
from ccld_complaints.hosted_app.facility_reference_preload import (
    FACILITY_REFERENCE_DATASET_SLUG,
    FACILITY_REFERENCE_DATASET_URL,
    hosted_facility_reference_metadata,
    hosted_facility_reference_records,
)
from ccld_complaints.hosted_app.reviewer_ui import (
    LOCAL_REVIEWER_UI_SCOPE,
    local_test_reviewer_actor,
)
from ccld_complaints.hosted_app.seeded_import import (
    hosted_import_batches,
    hosted_seeded_import_metadata,
    hosted_source_derived_records,
)

RAW_FIXTURE = Path("tests/fixtures/ccld/raw/157806098_inx3.html")
DETAIL_FIXTURE = Path("tests/fixtures/ccld/raw/157806098_facility_detail.html")
FACILITY_TYPE = "SHORT TERM RESIDENTIAL THERAPEUTIC PROGRAM"


class MockBatchRetrievalClient:
    def __init__(
        self,
        *,
        fail_facility_numbers: set[str] | None = None,
    ) -> None:
        self.fail_facility_numbers = fail_facility_numbers or set()
        self.facility_detail_calls: list[str] = []
        self.report_calls: list[str] = []

    def fetch_facility_detail(self, facility_number: str, *, timeout_seconds: int) -> str:
        self.facility_detail_calls.append(facility_number)
        if facility_number in self.fail_facility_numbers:
            raise RuntimeError("Traceback contained token and postgresql://private-host/db")
        return DETAIL_FIXTURE.read_text(encoding="utf-8")

    def fetch_report(self, source_url: str, *, timeout_seconds: int) -> bytes:
        self.report_calls.append(source_url)
        return RAW_FIXTURE.read_bytes()


def test_one_year_date_range_creates_one_window() -> None:
    windows = split_date_range("2025-07-02", "2026-07-02")

    assert [(window.start_date, window.end_date) for window in windows] == [
        ("2025-07-02", "2026-07-02")
    ]


def test_wider_date_range_splits_into_366_day_or_less_windows() -> None:
    windows = split_date_range("2025-01-01", "2026-01-02")

    assert [(window.start_date, window.end_date) for window in windows] == [
        ("2025-01-01", "2026-01-01"),
        ("2026-01-02", "2026-01-02"),
    ]
    assert all(
        (
            datetime.fromisoformat(window.end_date).date()
            - datetime.fromisoformat(window.start_date).date()
        ).days
        <= 365
        for window in windows
    )


def test_dry_run_creates_plan_without_retrieval_or_import(tmp_path: Path) -> None:
    client = MockBatchRetrievalClient()
    with _empty_connection() as connection:
        _insert_facility(connection, facility_number="157806098")
        output = io.StringIO()
        summary = run_batch(
            _options(manifest_path=tmp_path / "manifest.jsonl"),
            connection=connection,
            retrieval_context=_retrieval_context(connection, tmp_path, client=client),
            now=_fixed_now,
            output=output,
        )
        counts = _table_counts(connection)

    manifest_entries = _manifest_entries(tmp_path / "manifest.jsonl")
    assert summary.apply is False
    assert summary.planned_window_count == 1
    assert counts == {"import_batches": 0, "source_records": 0, "retrieval_jobs": 0}
    assert client.facility_detail_calls == []
    assert client.report_calls == []
    assert any(entry.get("state") == "planned" for entry in manifest_entries)
    assert "Dry-run complete" in output.getvalue()


def test_apply_calls_controlled_retrieval_import_path(tmp_path: Path) -> None:
    client = MockBatchRetrievalClient()
    with _empty_connection() as connection:
        _insert_facility(connection, facility_number="157806098")
        summary = run_batch(
            _options(manifest_path=tmp_path / "manifest.jsonl", apply=True),
            connection=connection,
            retrieval_context=_retrieval_context(connection, tmp_path, client=client),
            now=_fixed_now,
            output=io.StringIO(),
        )
        counts = _table_counts(connection)
        job = connection.execute(select(hosted_ccld_retrieval_jobs)).mappings().one()

    manifest_entries = _manifest_entries(tmp_path / "manifest.jsonl")
    assert summary.succeeded_count == 1
    assert counts["retrieval_jobs"] == 1
    assert counts["import_batches"] == 1
    assert counts["source_records"] == 38
    assert client.facility_detail_calls == ["157806098"]
    assert len(client.report_calls) == 1
    assert job["job_state"] == "completed"
    assert any(entry.get("state") == "succeeded" for entry in manifest_entries)


def test_facility_filtering_by_facility_type_works(tmp_path: Path) -> None:
    with _empty_connection() as connection:
        _insert_facility(connection, facility_number="111111111")
        _insert_facility(
            connection,
            facility_number="222222222",
            facility_type="CHILD CARE CENTER",
        )
        planned = build_plan(connection, _options(manifest_path=tmp_path / "manifest.jsonl"))

    assert [window.facility.facility_number for window in planned] == ["111111111"]


def test_county_status_facility_number_and_max_facilities_filters_work(
    tmp_path: Path,
) -> None:
    with _empty_connection() as connection:
        _insert_facility(connection, facility_number="111111111", county="Los Angeles")
        _insert_facility(connection, facility_number="222222222", county="Kern")
        _insert_facility(connection, facility_number="333333333", status="Closed")
        planned = build_plan(
            connection,
            _options(
                manifest_path=tmp_path / "manifest.jsonl",
                county="Los Angeles",
                status="Licensed",
                max_facilities=1,
            ),
        )
        exact = build_plan(
            connection,
            _options(
                manifest_path=tmp_path / "manifest-exact.jsonl",
                facility_number="222222222",
            ),
        )

    assert [window.facility.facility_number for window in planned] == ["111111111"]
    assert [window.facility.facility_number for window in exact] == ["222222222"]


def test_already_loaded_completed_windows_are_skipped(tmp_path: Path) -> None:
    client = MockBatchRetrievalClient()
    with _empty_connection() as connection:
        _insert_facility(connection, facility_number="157806098")
        _insert_completed_job(connection)
        output = io.StringIO()
        summary = run_batch(
            _options(manifest_path=tmp_path / "manifest.jsonl", apply=True),
            connection=connection,
            retrieval_context=_retrieval_context(connection, tmp_path, client=client),
            now=_fixed_now,
            output=output,
        )
        counts = _table_counts(connection)

    assert summary.skipped_count == 1
    assert counts == {"import_batches": 0, "source_records": 0, "retrieval_jobs": 1}
    assert client.facility_detail_calls == []
    assert "skipped" in output.getvalue()


def test_force_reruns_already_loaded_window(tmp_path: Path) -> None:
    client = MockBatchRetrievalClient()
    with _empty_connection() as connection:
        _insert_facility(connection, facility_number="157806098")
        _insert_completed_job(connection)
        summary = run_batch(
            _options(manifest_path=tmp_path / "manifest.jsonl", apply=True, force=True),
            connection=connection,
            retrieval_context=_retrieval_context(connection, tmp_path, client=client),
            now=_fixed_now,
            output=io.StringIO(),
        )
        counts = _table_counts(connection)

    assert summary.succeeded_count == 1
    assert counts["retrieval_jobs"] == 2
    assert counts["source_records"] == 38
    assert client.facility_detail_calls == ["157806098"]


def test_resume_skips_succeeded_manifest_entries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ccld_facility_reports,
        "_fetch_url",
        lambda _source_url: b'{"REPORTARRAY":[]}',
    )
    client = MockBatchRetrievalClient()
    manifest_path = tmp_path / "manifest.jsonl"
    with _empty_connection() as connection:
        _insert_facility(connection, facility_number="157806098", name="Alpha")
        _insert_facility(connection, facility_number="157806099", name="Beta")
        run_batch(
            _options(manifest_path=manifest_path),
            connection=connection,
            retrieval_context=_retrieval_context(connection, tmp_path, client=client),
            now=_fixed_now,
            output=io.StringIO(),
        )
        _append_manifest_window_state(manifest_path, "157806098", "succeeded")
        summary = run_batch(
            _options(manifest_path=manifest_path, apply=True, resume=True),
            connection=connection,
            retrieval_context=_retrieval_context(connection, tmp_path, client=client),
            now=_fixed_now,
            output=io.StringIO(),
        )

    assert summary.planned_window_count == 2
    assert summary.succeeded_count == 0
    assert summary.warning_count == 1
    assert client.facility_detail_calls == ["157806099"]


def test_failed_windows_are_recorded_without_stopping_batch(tmp_path: Path) -> None:
    client = MockBatchRetrievalClient(fail_facility_numbers={"157806099"})
    with _empty_connection() as connection:
        _insert_facility(connection, facility_number="157806098", name="Alpha")
        _insert_facility(connection, facility_number="157806099", name="Beta")
        summary = run_batch(
            _options(manifest_path=tmp_path / "manifest.jsonl", apply=True, force=True),
            connection=connection,
            retrieval_context=_retrieval_context(connection, tmp_path, client=client),
            now=_fixed_now,
            output=io.StringIO(),
        )

    states = [entry.get("state") for entry in _manifest_entries(tmp_path / "manifest.jsonl")]
    assert summary.succeeded_count == 1
    assert summary.failed_count == 1
    assert "succeeded" in states
    assert "failed" in states
    assert client.facility_detail_calls == ["157806098", "157806099"]


def test_output_and_manifest_do_not_include_private_values(tmp_path: Path) -> None:
    client = MockBatchRetrievalClient(fail_facility_numbers={"157806098"})
    output = io.StringIO()
    manifest_path = tmp_path / "manifest.jsonl"
    with _empty_connection() as connection:
        _insert_facility(connection, facility_number="157806098")
        run_batch(
            _options(manifest_path=manifest_path, apply=True, force=True),
            connection=connection,
            retrieval_context=_retrieval_context(connection, tmp_path, client=client),
            now=_fixed_now,
            output=output,
        )

    combined = (output.getvalue() + manifest_path.read_text(encoding="utf-8")).casefold()
    for marker in ("token", "postgresql://", "private-host", "traceback", "secret"):
        assert marker not in combined


def test_complaint_only_scope_is_enforced() -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "--facility-type",
                FACILITY_TYPE,
                "--start-date",
                "2025-07-02",
                "--end-date",
                "2026-07-02",
                "--record-type",
                "inspection_reports",
            ]
        )


def _options(
    *,
    manifest_path: Path,
    facility_type: str = FACILITY_TYPE,
    start_date: str = "2022-08-01",
    end_date: str = "2022-08-31",
    county: str | None = None,
    status: str | None = None,
    facility_number: str | None = None,
    max_facilities: int | None = None,
    apply: bool = False,
    force: bool = False,
    resume: bool = False,
) -> BatchComplaintRetrievalOptions:
    return BatchComplaintRetrievalOptions(
        facility_type=facility_type,
        start_date=start_date,
        end_date=end_date,
        county=county,
        status=status,
        facility_number=facility_number,
        max_facilities=max_facilities,
        manifest_path=manifest_path,
        resume=resume,
        apply=apply,
        force=force,
    )


def _fixed_now() -> datetime:
    return datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC)


def _empty_connection() -> Connection:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)
    hosted_facility_reference_metadata.create_all(engine)
    return engine.connect()


def _retrieval_context(
    connection: Connection,
    tmp_path: Path,
    *,
    client: MockBatchRetrievalClient,
) -> CcldRetrievalContext:
    return CcldRetrievalContext(
        connection=connection,
        actor=local_test_reviewer_actor(),
        scope=LOCAL_REVIEWER_UI_SCOPE,
        config=CcldRetrievalConfig(
            enabled=True,
            raw_dir=tmp_path / "raw",
            max_date_range_days=366,
            per_job_request_limit=1,
            rate_limit_per_actor=10,
            timeout_seconds=5,
            retry_limit=0,
        ),
        client=client,
        now=_fixed_now,
    )


def _insert_facility(
    connection: Connection,
    *,
    facility_number: str,
    name: str = "Test Facility",
    facility_type: str = FACILITY_TYPE,
    county: str = "Los Angeles",
    status: str = "Licensed",
) -> None:
    connection.execute(
        hosted_facility_reference_records.insert().values(
            source_resource_id="c9df723a-437f-4dcd-be37-ec73ae518bb9",
            facility_number=facility_number,
            facility_name=name,
            facility_type=facility_type,
            program_type=None,
            licensee_name=None,
            facility_administrator=None,
            telephone=None,
            address=None,
            city="Los Angeles",
            state="CA",
            zip="90001",
            county=county,
            regional_office=None,
            capacity=None,
            status=status,
            license_first_date=None,
            closed_date=None,
            snapshot_date=None,
            source_resource_name="24-Hour Residential Care for Children",
            source_dataset_slug=FACILITY_REFERENCE_DATASET_SLUG,
            source_dataset_url=FACILITY_REFERENCE_DATASET_URL,
            source_accessed_at="2026-07-03T12:00:00+00:00",
            source_file_name="24HourResidentialCareforChildren.csv",
            original_row_json={},
        )
    )


def _insert_completed_job(connection: Connection) -> None:
    connection.execute(
        hosted_ccld_retrieval_jobs.insert().values(
            retrieval_job_id="completed-job",
            created_at="2026-07-03T12:00:00+00:00",
            updated_at="2026-07-03T12:00:00+00:00",
            job_state="completed",
            facility_number="157806098",
            record_type="complaints",
            start_date="2022-08-01",
            end_date="2022-08-31",
            source_scope_type=LOCAL_REVIEWER_UI_SCOPE.scope_type,
            source_scope_id=LOCAL_REVIEWER_UI_SCOPE.scope_id,
            actor_provider_subject="fixture-retrieval-reviewer",
            actor_provider_issuer="fixture-managed-oidc-provider",
            actor_display_name="Fixture Retrieval Reviewer",
            actor_category="tester",
            authorization_permission="retrieval_job_trigger",
            request_limit="1",
            retry_limit="0",
            timeout_seconds="5",
            raw_storage_path="raw",
            source_artifact_identity="ccld-retrieval-job:completed-job",
            result_counts={"imported_source_derived_records": 1},
            warnings=[],
            errors=[],
            safe_message="Controlled CCLD retrieval imported source-derived records.",
            data_mutations_performed=True,
        )
    )


def _table_counts(connection: Connection) -> dict[str, int]:
    return {
        "import_batches": connection.execute(
            select(func.count()).select_from(hosted_import_batches)
        ).scalar_one(),
        "source_records": connection.execute(
            select(func.count()).select_from(hosted_source_derived_records)
        ).scalar_one(),
        "retrieval_jobs": connection.execute(
            select(func.count()).select_from(hosted_ccld_retrieval_jobs)
        ).scalar_one(),
    }


def _manifest_entries(path: Path) -> list[Mapping[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _append_manifest_window_state(path: Path, facility_number: str, state: str) -> None:
    entries = _manifest_entries(path)
    planned = next(
        entry
        for entry in entries
        if entry.get("event") == "window"
        and entry.get("facility_number") == facility_number
        and entry.get("state") == "planned"
    )
    completed = dict(planned)
    completed["state"] = state
    with path.open("a", encoding="utf-8", newline="\n") as manifest_file:
        manifest_file.write(json.dumps(completed, sort_keys=True, ensure_ascii=True))
        manifest_file.write("\n")
