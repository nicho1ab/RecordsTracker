from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, TextIO, cast

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError

from ccld_complaints.hosted_app.ccld_retrieval_jobs import (
    CCLD_CONNECTOR_NAME,
    RECORD_TYPE_LABELS,
    CcldFixtureRetrievalClient,
    CcldHttpRetrievalClient,
    CcldRetrievalContext,
    CcldRetrievalJobResult,
    CcldRetrievalRequest,
    hosted_ccld_retrieval_jobs,
    load_ccld_retrieval_config,
    run_ccld_retrieval_job,
)
from ccld_complaints.hosted_app.facility_reference_preload import (
    hosted_facility_reference_records,
)
from ccld_complaints.hosted_app.persistence import (
    DATABASE_URL_ENV,
    HostedDatabaseConfigError,
    load_hosted_database_config,
)
from ccld_complaints.hosted_app.reviewer_ui import (
    LOCAL_REVIEWER_UI_SCOPE,
    local_test_reviewer_actor,
)
from ccld_complaints.hosted_app.seeded_import import hosted_source_derived_records

BATCH_MANIFEST_DIR = Path("data/processed/batch-retrieval")
DATE_WINDOW_LIMIT_DAYS = 366
DEFAULT_MANIFEST_SAMPLE_LIMIT = 5
SUPPORTED_BATCH_RECORD_TYPES = ("complaints",)

BatchWindowState = Literal["planned", "skipped", "succeeded", "failed", "warning"]

_SECRET_OUTPUT_MARKERS = (
    "authorization",
    "client_secret",
    "connection string",
    "connection_string",
    "cookie",
    "password",
    "private_header",
    "private header",
    "provider_issuer",
    "provider_subject",
    "secret",
    "token",
    "traceback",
)


@dataclass(frozen=True)
class BatchComplaintRetrievalOptions:
    facility_type: str
    start_date: str
    end_date: str
    county: str | None = None
    status: str | None = None
    facility_number: str | None = None
    max_facilities: int | None = None
    max_windows: int | None = None
    manifest_path: Path | None = None
    resume: bool = False
    apply: bool = False
    force: bool = False
    delay_seconds: float = 0.0
    record_type: str = "complaints"


@dataclass(frozen=True)
class BatchFacility:
    facility_number: str
    facility_name: str
    facility_type: str
    county: str
    status: str


@dataclass(frozen=True)
class DateWindow:
    start_date: str
    end_date: str


@dataclass(frozen=True)
class BatchPlannedWindow:
    facility: BatchFacility
    date_window: DateWindow
    record_type: str

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (
            self.facility.facility_number,
            self.record_type,
            self.date_window.start_date,
            self.date_window.end_date,
        )


@dataclass(frozen=True)
class AlreadyLoadedMatch:
    reason: str
    retrieval_job_id: str | None = None
    source_record_count: int = 0


@dataclass(frozen=True)
class BatchRunSummary:
    batch_id: str
    manifest_path: Path
    apply: bool
    planned_facility_count: int
    planned_window_count: int
    skipped_count: int
    succeeded_count: int
    failed_count: int
    warning_count: int

    @property
    def had_failures(self) -> bool:
        return self.failed_count > 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Plan or run a CCLD-only batch complaint retrieval using the existing "
            "controlled hosted retrieval/import path."
        )
    )
    parser.add_argument("--facility-type", help="Required CCLD facility type filter.")
    parser.add_argument("--start-date", help="Start date in YYYY-MM-DD format.")
    parser.add_argument("--end-date", help="End date in YYYY-MM-DD format.")
    parser.add_argument("--county", help="Optional county filter.")
    parser.add_argument("--status", help="Optional facility status filter.")
    parser.add_argument("--facility-number", help="Optional exact CCLD facility/license number.")
    parser.add_argument("--max-facilities", type=_positive_int, help="Optional facility limit.")
    parser.add_argument("--max-windows", type=_positive_int, help="Optional total window limit.")
    parser.add_argument("--manifest-path", type=Path, help="Optional JSONL manifest path.")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from an existing manifest and skip succeeded or skipped windows.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Run retrieval/import mutations. Omit for dry-run planning.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rerun windows even when an already-loaded match is found.",
    )
    parser.add_argument(
        "--delay-seconds",
        type=_nonnegative_float,
        default=0.0,
        help="Delay between apply windows. Defaults to 0.",
    )
    parser.add_argument(
        "--record-type",
        choices=SUPPORTED_BATCH_RECORD_TYPES,
        default="complaints",
        help="Record type to retrieve. Only complaints are supported for batch mode.",
    )
    return parser


def options_from_args(args: argparse.Namespace) -> BatchComplaintRetrievalOptions:
    return BatchComplaintRetrievalOptions(
        facility_type=(args.facility_type or "").strip(),
        start_date=(args.start_date or "").strip(),
        end_date=(args.end_date or "").strip(),
        county=_optional_clean(args.county),
        status=_optional_clean(args.status),
        facility_number=_optional_clean(args.facility_number),
        max_facilities=args.max_facilities,
        max_windows=args.max_windows,
        manifest_path=args.manifest_path,
        resume=bool(args.resume),
        apply=bool(args.apply),
        force=bool(args.force),
        delay_seconds=float(args.delay_seconds),
        record_type=args.record_type,
    )


def validate_options(
    options: BatchComplaintRetrievalOptions,
    *,
    allow_missing_for_resume: bool = False,
) -> None:
    errors: list[str] = []
    if not allow_missing_for_resume or options.facility_type:
        if not options.facility_type:
            errors.append("--facility-type is required.")
    if not allow_missing_for_resume or options.start_date:
        if _parse_iso_date(options.start_date) is None:
            errors.append("--start-date must use YYYY-MM-DD format.")
    if not allow_missing_for_resume or options.end_date:
        if _parse_iso_date(options.end_date) is None:
            errors.append("--end-date must use YYYY-MM-DD format.")
    start = _parse_iso_date(options.start_date)
    end = _parse_iso_date(options.end_date)
    if start is not None and end is not None and end < start:
        errors.append("--end-date must not be before --start-date.")
    if options.facility_number is not None and not options.facility_number.isdigit():
        errors.append("--facility-number must contain digits only.")
    if options.record_type not in SUPPORTED_BATCH_RECORD_TYPES:
        errors.append("--record-type supports complaints only for batch retrieval.")
    if options.delay_seconds < 0:
        errors.append("--delay-seconds must be greater than or equal to 0.")
    if options.resume and options.manifest_path is None:
        errors.append("--resume requires --manifest-path.")
    if errors:
        raise ValueError(" ".join(errors))


def split_date_range(
    start_date: str,
    end_date: str,
    *,
    max_inclusive_days: int = DATE_WINDOW_LIMIT_DAYS,
) -> tuple[DateWindow, ...]:
    if max_inclusive_days < 1:
        raise ValueError("max_inclusive_days must be at least 1.")
    start = _required_date(start_date, "start_date")
    end = _required_date(end_date, "end_date")
    if end < start:
        raise ValueError("end_date must not be before start_date.")
    windows: list[DateWindow] = []
    current = start
    while current <= end:
        window_end = min(current + timedelta(days=max_inclusive_days - 1), end)
        windows.append(DateWindow(current.isoformat(), window_end.isoformat()))
        current = window_end + timedelta(days=1)
    return tuple(windows)


def load_matching_facilities(
    connection: Connection,
    options: BatchComplaintRetrievalOptions,
) -> tuple[BatchFacility, ...]:
    rows = connection.execute(
        select(hosted_facility_reference_records).order_by(
            hosted_facility_reference_records.c.facility_name,
            hosted_facility_reference_records.c.facility_number,
            hosted_facility_reference_records.c.source_resource_name,
        )
    ).mappings()
    facilities: list[BatchFacility] = []
    seen_numbers: set[str] = set()
    for row in rows:
        facility = _facility_from_row(dict(row))
        if facility.facility_number in seen_numbers:
            continue
        if not _facility_matches_options(facility, options):
            continue
        seen_numbers.add(facility.facility_number)
        facilities.append(facility)
        if options.max_facilities is not None and len(facilities) >= options.max_facilities:
            break
    return tuple(facilities)


def build_plan(
    connection: Connection,
    options: BatchComplaintRetrievalOptions,
) -> tuple[BatchPlannedWindow, ...]:
    validate_options(options)
    facilities = load_matching_facilities(connection, options)
    date_windows = split_date_range(options.start_date, options.end_date)
    planned = [
        BatchPlannedWindow(facility=facility, date_window=window, record_type=options.record_type)
        for facility in facilities
        for window in date_windows
    ]
    if options.max_windows is not None:
        planned = planned[: options.max_windows]
    return tuple(planned)


def already_loaded_match(
    connection: Connection,
    planned_window: BatchPlannedWindow,
) -> AlreadyLoadedMatch | None:
    job_match = connection.execute(
        select(hosted_ccld_retrieval_jobs)
        .where(
            hosted_ccld_retrieval_jobs.c.facility_number
            == planned_window.facility.facility_number,
            hosted_ccld_retrieval_jobs.c.record_type.in_(
                (planned_window.record_type, "all_supported")
            ),
            hosted_ccld_retrieval_jobs.c.start_date == planned_window.date_window.start_date,
            hosted_ccld_retrieval_jobs.c.end_date == planned_window.date_window.end_date,
            hosted_ccld_retrieval_jobs.c.job_state.in_(
                ("completed", "completed_with_warnings")
            ),
            hosted_ccld_retrieval_jobs.c.data_mutations_performed.is_(True),
        )
        .order_by(hosted_ccld_retrieval_jobs.c.updated_at.desc())
        .limit(1)
    ).mappings().first()
    if job_match is not None:
        return AlreadyLoadedMatch(
            reason="matching completed retrieval job",
            retrieval_job_id=str(job_match["retrieval_job_id"]),
        )

    source_record_count = _matching_source_derived_complaint_count(connection, planned_window)
    if source_record_count:
        return AlreadyLoadedMatch(
            reason="matching source-derived complaint rows",
            source_record_count=source_record_count,
        )
    return None


def run_batch(
    options: BatchComplaintRetrievalOptions,
    *,
    connection: Connection,
    retrieval_context: CcldRetrievalContext | None,
    now: Callable[[], datetime] | None = None,
    output: TextIO | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> BatchRunSummary:
    clock = now or (lambda: datetime.now(UTC))
    out = output or sys.stdout
    manifest_entries = _read_manifest_entries(options.manifest_path) if options.resume else ()
    active_options = _options_with_manifest_defaults(options, manifest_entries)
    validate_options(active_options)
    batch_id = _batch_id_from_manifest(manifest_entries) or _new_batch_id(clock)
    manifest_path = active_options.manifest_path or _default_manifest_path(batch_id)
    planned_windows = (
        _planned_windows_from_manifest(manifest_entries)
        if active_options.resume and manifest_entries
        else build_plan(connection, active_options)
    )
    skipped_manifest_keys = _resume_completed_keys(manifest_entries)
    remaining_windows = tuple(
        window for window in planned_windows if window.key not in skipped_manifest_keys
    )

    _open_manifest(manifest_path, resume=active_options.resume)
    if active_options.resume:
        _append_manifest_event(
            manifest_path,
            {
                "event": "batch_resume",
                "batch_id": batch_id,
                "resumed_at": _timestamp(clock),
                "command_options": _safe_options(active_options),
                "already_completed_window_count": len(skipped_manifest_keys),
            },
        )
    else:
        _append_manifest_event(
            manifest_path,
            {
                "event": "batch_start",
                "batch_id": batch_id,
                "started_at": _timestamp(clock),
                "command_options": _safe_options(active_options),
            },
        )
        for planned_window in planned_windows:
            _append_manifest_event(
                manifest_path,
                _manifest_window_event(
                    batch_id,
                    planned_window,
                    state="planned",
                    timestamp=_timestamp(clock),
                ),
            )

    _print_plan_summary(
        out,
        active_options,
        planned_windows,
        remaining_windows,
        manifest_path,
    )
    if not active_options.apply:
        _safe_print(
            out,
            "Dry-run complete: no retrieval jobs were created, no CCLD fetches were run, "
            "and no source rows or raw artifacts were written.",
        )
        _append_manifest_event(
            manifest_path,
            {
                "event": "batch_complete",
                "batch_id": batch_id,
                "completed_at": _timestamp(clock),
                "mode": "dry-run",
                "planned_window_count": len(planned_windows),
                "remaining_window_count": len(remaining_windows),
            },
        )
        return BatchRunSummary(
            batch_id=batch_id,
            manifest_path=manifest_path,
            apply=False,
            planned_facility_count=_facility_count(planned_windows),
            planned_window_count=len(planned_windows),
            skipped_count=0,
            succeeded_count=0,
            failed_count=0,
            warning_count=0,
        )

    if retrieval_context is None or not retrieval_context.config.configured:
        raise ValueError(
            "Apply mode requires configured controlled CCLD retrieval and raw artifact storage."
        )

    skipped = 0
    succeeded = 0
    failed = 0
    warning = 0
    for index, planned_window in enumerate(remaining_windows, start=1):
        if not active_options.force:
            existing = already_loaded_match(connection, planned_window)
            if existing is not None:
                skipped += 1
                _append_manifest_event(
                    manifest_path,
                    _manifest_window_event(
                        batch_id,
                        planned_window,
                        state="skipped",
                        timestamp=_timestamp(clock),
                        counts={"existing_source_record_count": existing.source_record_count},
                        warnings=(f"Skipped: {existing.reason}.",),
                        retrieval_job_id=existing.retrieval_job_id,
                    ),
                )
                _safe_print(
                    out,
                    _window_console_line(index, len(remaining_windows), planned_window, "skipped"),
                )
                _sleep_between_windows(
                    active_options.delay_seconds,
                    index=index,
                    total=len(remaining_windows),
                    sleep=sleep,
                )
                continue
        result = _run_window_safely(retrieval_context, planned_window)
        if result.job_state == "failed":
            state: BatchWindowState = "failed"
            failed += 1
        elif result.job_state in {
            "completed_with_warnings",
            "blocked_by_validation",
            "rate_limited",
        }:
            state = "warning"
            warning += 1
        else:
            state = "succeeded"
            succeeded += 1
        _append_manifest_event(
            manifest_path,
            _manifest_window_event(
                batch_id,
                planned_window,
                state=state,
                timestamp=_timestamp(clock),
                retrieval_job_id=result.retrieval_job_id,
                counts=dict(result.result_counts),
                warnings=result.warnings,
                errors=result.errors,
                source_artifact_identity=result.source_artifact_identity,
            ),
        )
        _safe_print(
            out,
            _window_console_line(index, len(remaining_windows), planned_window, state),
        )
        _sleep_between_windows(
            active_options.delay_seconds,
            index=index,
            total=len(remaining_windows),
            sleep=sleep,
        )

    _append_manifest_event(
        manifest_path,
        {
            "event": "batch_complete",
            "batch_id": batch_id,
            "completed_at": _timestamp(clock),
            "mode": "apply",
            "planned_window_count": len(planned_windows),
            "remaining_window_count": len(remaining_windows),
            "skipped_window_count": skipped,
            "succeeded_window_count": succeeded,
            "warning_window_count": warning,
            "failed_window_count": failed,
        },
    )
    _safe_print(
        out,
        (
            "Apply complete: "
            f"succeeded={succeeded}, warnings={warning}, skipped={skipped}, failed={failed}."
        ),
    )
    return BatchRunSummary(
        batch_id=batch_id,
        manifest_path=manifest_path,
        apply=True,
        planned_facility_count=_facility_count(planned_windows),
        planned_window_count=len(planned_windows),
        skipped_count=skipped,
        succeeded_count=succeeded,
        failed_count=failed,
        warning_count=warning,
    )


def create_retrieval_context(connection: Connection) -> CcldRetrievalContext | None:
    config = load_ccld_retrieval_config()
    if not config.configured:
        return None
    client = (
        CcldFixtureRetrievalClient()
        if config.mock_success_demo_enabled
        else CcldHttpRetrievalClient()
    )
    actor = local_test_reviewer_actor()
    return CcldRetrievalContext(
        connection=connection,
        actor=actor,
        scope=LOCAL_REVIEWER_UI_SCOPE,
        config=config,
        client=client,
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    raw_options = options_from_args(args)
    try:
        validate_options(raw_options, allow_missing_for_resume=raw_options.resume)
        database_config = load_hosted_database_config(require_url=True)
        engine = create_engine(cast(str, database_config.database_url))
        with engine.connect() as connection:
            retrieval_context = create_retrieval_context(connection)
            summary = run_batch(
                raw_options,
                connection=connection,
                retrieval_context=retrieval_context,
            )
    except (HostedDatabaseConfigError, SQLAlchemyError):
        print(
            f"Batch retrieval could not open the configured hosted database. "
            f"Set {DATABASE_URL_ENV}, run migrations, and retry.",
            file=sys.stderr,
        )
        return 2
    except ValueError as error:
        print(_safe_error_message(str(error)), file=sys.stderr)
        return 2
    finally:
        if "engine" in locals():
            engine.dispose()
    return 1 if summary.had_failures else 0


def _run_window_safely(
    retrieval_context: CcldRetrievalContext,
    planned_window: BatchPlannedWindow,
) -> CcldRetrievalJobResult:
    request = CcldRetrievalRequest(
        facility_number=planned_window.facility.facility_number,
        record_type=planned_window.record_type,
        start_date=planned_window.date_window.start_date,
        end_date=planned_window.date_window.end_date,
    )
    try:
        return run_ccld_retrieval_job(retrieval_context, request)
    except Exception:  # noqa: BLE001
        return CcldRetrievalJobResult(
            retrieval_job_id=_safe_fallback_job_id(planned_window),
            job_state="failed",
            facility_number=planned_window.facility.facility_number,
            record_type=planned_window.record_type,
            start_date=planned_window.date_window.start_date,
            end_date=planned_window.date_window.end_date,
            source_artifact_identity=None,
            result_counts={},
            warnings=(),
            errors=("Batch retrieval window failed safely.",),
            safe_message="Batch retrieval window failed safely.",
        )


def _matching_source_derived_complaint_count(
    connection: Connection,
    planned_window: BatchPlannedWindow,
) -> int:
    rows = connection.execute(
        select(hosted_source_derived_records).where(
            hosted_source_derived_records.c.entity_type == "complaint",
            hosted_source_derived_records.c.connector_name == CCLD_CONNECTOR_NAME,
        )
    ).mappings()
    return sum(
        1
        for row in rows
        if _source_record_matches_window(dict(row), planned_window)
    )


def _source_record_matches_window(
    row: Mapping[str, Any],
    planned_window: BatchPlannedWindow,
) -> bool:
    original_values = row.get("original_values")
    if not isinstance(original_values, Mapping):
        return False
    facility_number = planned_window.facility.facility_number
    if not (
        original_values.get("external_facility_number") == facility_number
        or original_values.get("facility_number") == facility_number
        or str(row.get("facility_id") or "").endswith(facility_number)
        or f"facNum={facility_number}" in str(row.get("source_url") or "")
    ):
        return False
    start = _required_date(planned_window.date_window.start_date, "start_date")
    end = _required_date(planned_window.date_window.end_date, "end_date")
    return any(start <= record_date <= end for record_date in _record_dates(original_values))


def _record_dates(original_values: Mapping[str, Any]) -> tuple[date, ...]:
    dates: list[date] = []
    for field_name in (
        "complaint_received_date",
        "visit_date",
        "report_date",
        "date_signed",
    ):
        value = original_values.get(field_name)
        if isinstance(value, str):
            parsed = _parse_iso_date(value[:10])
            if parsed is not None:
                dates.append(parsed)
    return tuple(dates)


def _facility_from_row(row: Mapping[str, Any]) -> BatchFacility:
    return BatchFacility(
        facility_number=_row_str(row, "facility_number"),
        facility_name=_row_str(row, "facility_name"),
        facility_type=_row_str(row, "facility_type"),
        county=_row_str(row, "county"),
        status=_row_str(row, "status"),
    )


def _facility_matches_options(
    facility: BatchFacility,
    options: BatchComplaintRetrievalOptions,
) -> bool:
    if _normalized(facility.facility_type) != _normalized(options.facility_type):
        return False
    if options.county is not None and _normalized(facility.county) != _normalized(options.county):
        return False
    if options.status is not None and _normalized(facility.status) != _normalized(options.status):
        return False
    return not (
        options.facility_number is not None
        and facility.facility_number != options.facility_number
    )


def _options_with_manifest_defaults(
    options: BatchComplaintRetrievalOptions,
    manifest_entries: Sequence[Mapping[str, Any]],
) -> BatchComplaintRetrievalOptions:
    if not options.resume or not manifest_entries:
        return options
    manifest_options = _manifest_start_options(manifest_entries)
    if not manifest_options:
        return options
    return replace(
        options,
        facility_type=options.facility_type or _manifest_str(manifest_options, "facility_type"),
        start_date=options.start_date or _manifest_str(manifest_options, "start_date"),
        end_date=options.end_date or _manifest_str(manifest_options, "end_date"),
        county=options.county or _manifest_optional_str(manifest_options, "county"),
        status=options.status or _manifest_optional_str(manifest_options, "status"),
        facility_number=options.facility_number
        or _manifest_optional_str(manifest_options, "facility_number"),
        max_facilities=options.max_facilities
        or _manifest_optional_int(manifest_options, "max_facilities"),
        max_windows=options.max_windows or _manifest_optional_int(manifest_options, "max_windows"),
        record_type=options.record_type or _manifest_str(manifest_options, "record_type"),
    )


def _manifest_start_options(
    manifest_entries: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any]:
    for entry in manifest_entries:
        if entry.get("event") == "batch_start" and isinstance(
            entry.get("command_options"), Mapping
        ):
            return cast(Mapping[str, Any], entry["command_options"])
    return {}


def _planned_windows_from_manifest(
    manifest_entries: Sequence[Mapping[str, Any]],
) -> tuple[BatchPlannedWindow, ...]:
    windows: list[BatchPlannedWindow] = []
    seen: set[tuple[str, str, str, str]] = set()
    for entry in manifest_entries:
        if entry.get("event") != "window" or entry.get("state") != "planned":
            continue
        facility_number = _manifest_str(entry, "facility_number")
        record_type = _manifest_str(entry, "record_type") or "complaints"
        date_window = _manifest_date_window(entry)
        facility = BatchFacility(
            facility_number=facility_number,
            facility_name=_manifest_str(entry, "facility_name"),
            facility_type=_manifest_str(entry, "facility_type"),
            county=_manifest_str(entry, "county"),
            status=_manifest_str(entry, "status"),
        )
        planned = BatchPlannedWindow(
            facility=facility,
            date_window=date_window,
            record_type=record_type,
        )
        if planned.key in seen:
            continue
        seen.add(planned.key)
        windows.append(planned)
    return tuple(windows)


def _resume_completed_keys(
    manifest_entries: Sequence[Mapping[str, Any]],
) -> frozenset[tuple[str, str, str, str]]:
    completed: set[tuple[str, str, str, str]] = set()
    for entry in manifest_entries:
        if entry.get("event") != "window":
            continue
        if entry.get("state") not in {"succeeded", "skipped"}:
            continue
        completed.add(_manifest_window_key(entry))
    return frozenset(completed)


def _manifest_window_key(entry: Mapping[str, Any]) -> tuple[str, str, str, str]:
    date_window = _manifest_date_window(entry)
    return (
        _manifest_str(entry, "facility_number"),
        _manifest_str(entry, "record_type") or "complaints",
        date_window.start_date,
        date_window.end_date,
    )


def _manifest_date_window(entry: Mapping[str, Any]) -> DateWindow:
    raw_window = entry.get("date_window")
    if not isinstance(raw_window, Mapping):
        return DateWindow("", "")
    return DateWindow(
        start_date=_manifest_str(raw_window, "start_date"),
        end_date=_manifest_str(raw_window, "end_date"),
    )


def _read_manifest_entries(manifest_path: Path | None) -> tuple[Mapping[str, Any], ...]:
    if manifest_path is None:
        return ()
    if not manifest_path.exists():
        raise ValueError("Resume manifest was not found.")
    entries: list[Mapping[str, Any]] = []
    for raw_line in manifest_path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        loaded = json.loads(raw_line)
        if isinstance(loaded, Mapping):
            entries.append(cast(Mapping[str, Any], loaded))
    return tuple(entries)


def _append_manifest_event(manifest_path: Path, event: Mapping[str, Any]) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("a", encoding="utf-8", newline="\n") as manifest_file:
        manifest_file.write(json.dumps(event, sort_keys=True, ensure_ascii=True))
        manifest_file.write("\n")


def _open_manifest(manifest_path: Path, *, resume: bool) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    if not resume:
        manifest_path.write_text("", encoding="utf-8")


def _manifest_window_event(
    batch_id: str,
    planned_window: BatchPlannedWindow,
    *,
    state: BatchWindowState,
    timestamp: str,
    retrieval_job_id: str | None = None,
    counts: Mapping[str, int] | None = None,
    warnings: Sequence[str] = (),
    errors: Sequence[str] = (),
    source_artifact_identity: str | None = None,
) -> dict[str, Any]:
    safe_counts = dict(counts or {})
    return {
        "event": "window",
        "batch_id": batch_id,
        "updated_at": timestamp,
        "state": state,
        "facility_number": planned_window.facility.facility_number,
        "facility_name": _safe_text(planned_window.facility.facility_name),
        "facility_type": _safe_text(planned_window.facility.facility_type),
        "county": _safe_text(planned_window.facility.county),
        "status": _safe_text(planned_window.facility.status),
        "record_type": planned_window.record_type,
        "date_window": {
            "start_date": planned_window.date_window.start_date,
            "end_date": planned_window.date_window.end_date,
        },
        "retrieval_job_id": retrieval_job_id,
        "counts": safe_counts,
        "discovered_count": safe_counts.get("discovered_report_candidates", 0),
        "selected_count": safe_counts.get("selected_report_candidates", 0),
        "retrieved_count": safe_counts.get("retrieved_record_bundles", 0),
        "imported_count": safe_counts.get("imported_source_derived_records", 0),
        "raw_artifact_count": safe_counts.get("retrieved_record_bundles", 0),
        "source_artifact_identity": _safe_optional_text(source_artifact_identity),
        "warnings": [_safe_error_message(warning) for warning in warnings],
        "errors": [_safe_error_message(error) for error in errors],
    }


def _safe_options(options: BatchComplaintRetrievalOptions) -> dict[str, Any]:
    return {
        "facility_type": options.facility_type,
        "start_date": options.start_date,
        "end_date": options.end_date,
        "county": options.county,
        "status": options.status,
        "facility_number": options.facility_number,
        "max_facilities": options.max_facilities,
        "max_windows": options.max_windows,
        "record_type": options.record_type,
        "apply": options.apply,
        "force": options.force,
        "delay_seconds": options.delay_seconds,
    }


def _print_plan_summary(
    output: TextIO,
    options: BatchComplaintRetrievalOptions,
    planned_windows: Sequence[BatchPlannedWindow],
    remaining_windows: Sequence[BatchPlannedWindow],
    manifest_path: Path,
) -> None:
    mode = "apply" if options.apply else "dry-run"
    _safe_print(output, f"Batch complaint retrieval mode: {mode}")
    _safe_print(output, f"Record type: {RECORD_TYPE_LABELS.get(options.record_type, 'Complaints')}")
    _safe_print(output, f"Matching facilities: {_facility_count(planned_windows)}")
    _safe_print(output, f"Planned facility/date windows: {len(planned_windows)}")
    if options.resume:
        _safe_print(output, f"Remaining windows after resume manifest: {len(remaining_windows)}")
    _safe_print(output, f"Manifest: {_safe_path_label(manifest_path)}")
    sample = tuple(remaining_windows[:DEFAULT_MANIFEST_SAMPLE_LIMIT])
    if sample:
        _safe_print(output, "Sample planned windows:")
        for planned_window in sample:
            _safe_print(
                output,
                (
                    f"  {planned_window.facility.facility_number} "
                    f"{planned_window.date_window.start_date} to "
                    f"{planned_window.date_window.end_date}"
                ),
            )


def _window_console_line(
    index: int,
    total: int,
    planned_window: BatchPlannedWindow,
    state: str,
) -> str:
    return (
        f"[{index}/{total}] {state}: {planned_window.facility.facility_number} "
        f"{planned_window.date_window.start_date} to {planned_window.date_window.end_date}"
    )


def _sleep_between_windows(
    delay_seconds: float,
    *,
    index: int,
    total: int,
    sleep: Callable[[float], None],
) -> None:
    if delay_seconds <= 0 or index >= total:
        return
    sleep(delay_seconds)


def _facility_count(planned_windows: Sequence[BatchPlannedWindow]) -> int:
    return len({window.facility.facility_number for window in planned_windows})


def _safe_print(output: TextIO, message: str) -> None:
    print(_safe_error_message(message), file=output)


def _safe_error_message(message: str) -> str:
    safe_message = message or "Batch retrieval message unavailable."
    lowered = safe_message.casefold()
    if any(marker in lowered for marker in _SECRET_OUTPUT_MARKERS):
        return "Batch retrieval message hidden because it included private-looking data."
    if "://" in lowered:
        return "Batch retrieval message hidden because it included a URL-like value."
    if "\\" in safe_message or ":/" in safe_message:
        return safe_message.replace("\\", "/")
    return safe_message


def _safe_text(value: str) -> str:
    return _safe_error_message(value.strip()) if value.strip() else ""


def _safe_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    return _safe_text(value)


def _safe_path_label(path: Path) -> str:
    if not path.is_absolute():
        return path.as_posix()
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.name


def _default_manifest_path(batch_id: str) -> Path:
    return BATCH_MANIFEST_DIR / f"{batch_id}.jsonl"


def _new_batch_id(now: Callable[[], datetime]) -> str:
    return f"ccld-batch-complaints-{now().astimezone(UTC).strftime('%Y%m%dT%H%M%SZ')}"


def _batch_id_from_manifest(
    manifest_entries: Sequence[Mapping[str, Any]],
) -> str | None:
    for entry in manifest_entries:
        batch_id = entry.get("batch_id")
        if isinstance(batch_id, str) and batch_id.strip():
            return batch_id
    return None


def _timestamp(now: Callable[[], datetime]) -> str:
    return now().astimezone(UTC).replace(microsecond=0).isoformat()


def _safe_fallback_job_id(planned_window: BatchPlannedWindow) -> str:
    return (
        "ccld-batch-window-failed-"
        f"{planned_window.facility.facility_number}-"
        f"{planned_window.date_window.start_date}"
    )


def _required_date(value: str, field_name: str) -> date:
    parsed = _parse_iso_date(value)
    if parsed is None:
        raise ValueError(f"{field_name} must use YYYY-MM-DD format.")
    return parsed


def _parse_iso_date(value: str | None) -> date | None:
    if value is None or not value.strip():
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be at least 1")
    return parsed


def _nonnegative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be greater than or equal to 0")
    return parsed


def _optional_clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def _normalized(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


def _row_str(row: Mapping[str, Any], key: str) -> str:
    value = row.get(key)
    if value is None:
        return ""
    return str(value)


def _manifest_str(entry: Mapping[str, Any], key: str) -> str:
    value = entry.get(key)
    return value if isinstance(value, str) else ""


def _manifest_optional_str(entry: Mapping[str, Any], key: str) -> str | None:
    value = _manifest_str(entry, key).strip()
    return value or None


def _manifest_optional_int(entry: Mapping[str, Any], key: str) -> int | None:
    value = entry.get(key)
    return value if isinstance(value, int) else None


if __name__ == "__main__":
    raise SystemExit(main())
