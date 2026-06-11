from __future__ import annotations

import argparse
from pathlib import Path

from ccld_complaints.connectors.ccld import CcldFacilityReportsConnector
from ccld_complaints.connectors.ccld.facility_reports import (
    LIVE_REQUEST_TIMEOUT_SECONDS,
    LIVE_USER_AGENT,
    ingest_facility_reports_for_facilities,
    ingest_facility_reports_for_facility,
    normalize_facility_numbers,
    read_facility_numbers_file,
)
from ccld_complaints.local_sample import DEFAULT_SAMPLE_DB_PATH, datasette_command

DEFAULT_LIVE_RAW_DIR = Path("data/raw/ccld")
DEFAULT_LIVE_FACILITY_NUMBER = "157806098"
DEFAULT_LIVE_LIMIT = 1
DEFAULT_LIVE_MAX_REQUESTS = 5


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch live public CCLD report content for explicit facilities, "
            "store raw files locally, and ingest the saved files into SQLite."
        )
    )
    parser.add_argument(
        "--facility-number",
        action="append",
        dest="facility_numbers",
        help=(
            "Public CCLD facility number to fetch. Repeat this option for multiple explicit "
            "facilities. Defaults to the POC facility when no facility input is provided."
        ),
    )
    parser.add_argument(
        "--facility-input-path",
        type=Path,
        help="Small text or CSV file containing public CCLD facility numbers to fetch.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_SAMPLE_DB_PATH,
        help="SQLite database path to initialize and populate.",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=DEFAULT_LIVE_RAW_DIR,
        help="Local gitignored directory for downloaded raw report files.",
    )

    limit_group = parser.add_mutually_exclusive_group()
    limit_group.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIVE_LIMIT,
        help="Maximum number of discovered reports to fetch. Use a small number first.",
    )
    limit_group.add_argument(
        "--all",
        action="store_true",
        help="Fetch all discovered reports for the facility.",
    )
    parser.add_argument(
        "--max-requests",
        type=int,
        default=DEFAULT_LIVE_MAX_REQUESTS,
        help=(
            "Safety guard for the maximum number of report requests allowed. "
            "Increase intentionally when using --all or a larger --limit."
        ),
    )
    args = parser.parse_args()

    if args.limit is not None and args.limit < 0:
        parser.error("--limit must be greater than or equal to 0.")
    if args.max_requests < 0:
        parser.error("--max-requests must be greater than or equal to 0.")
    if not args.all and args.limit > args.max_requests:
        parser.error("--limit cannot exceed --max-requests.")

    try:
        facility_numbers = _collect_facility_numbers(
            args.facility_numbers,
            args.facility_input_path,
        )
    except ValueError as exc:
        parser.error(str(exc))

    limit = None if args.all else args.limit
    estimated_request_count = "discovery requests plus all discovered report requests"
    if limit is not None:
        estimated_request_count = (
            "up to 2 discovery requests per facility plus "
            f"{limit} report request(s) per facility"
        )

    print("Warning: this command accesses the public CCLD external site.")
    print("Run it only when you intend to make live public web requests.")
    print(f"Facility numbers: {', '.join(facility_numbers)}")
    print(f"Raw files: {args.raw_dir.as_posix()}")
    print(f"SQLite database: {args.db_path.as_posix()}")
    print(f"Request policy: timeout {LIVE_REQUEST_TIMEOUT_SECONDS}s, user-agent {LIVE_USER_AGENT}")
    print(
        f"Request count: {estimated_request_count}; "
        f"max report requests {args.max_requests}; no retry loop is used."
    )

    if len(facility_numbers) == 1:
        connector = CcldFacilityReportsConnector(
            facility_number=facility_numbers[0],
            raw_dir=args.raw_dir,
            db_path=args.db_path,
        )
        single_result = ingest_facility_reports_for_facility(
            facility_number=facility_numbers[0],
            connector=connector,
            limit=limit,
            max_requests=args.max_requests,
        )
        candidates = single_result.candidates
        records = single_result.records
        report_failures = single_result.failures
        facility_failures = []
    else:
        multi_result = ingest_facility_reports_for_facilities(
            facility_numbers,
            connector_factory=lambda facility_number: CcldFacilityReportsConnector(
                facility_number=facility_number,
                raw_dir=args.raw_dir,
                db_path=args.db_path,
            ),
            per_facility_limit=limit,
            max_requests=args.max_requests,
        )
        candidates = multi_result.candidates
        records = multi_result.records
        report_failures = multi_result.failures
        facility_failures = multi_result.facility_failures

    print(f"Discovered candidates selected: {len(candidates)}")
    print(f"Records written: {len(records)}")
    print(f"Failures recorded: {len(report_failures) + len(facility_failures)}")
    for facility_failure in facility_failures:
        print(
            "Facility failure: "
            f"facility_number={facility_failure.facility_number} "
            f"stage={facility_failure.stage} "
            f"error={facility_failure.error_type} "
            f"message={facility_failure.message}"
        )
    for report_failure in report_failures:
        print(
            "Failure: "
            f"report_index={report_failure.candidate.report_index} "
            f"stage={report_failure.stage} "
            f"error={report_failure.error_type} "
            f"message={report_failure.message}"
        )

    print("Open in Datasette:")
    print(datasette_command(args.db_path))


def _collect_facility_numbers(
    facility_numbers: list[str] | None,
    facility_input_path: Path | None,
) -> list[str]:
    values = list(facility_numbers or [])
    if facility_input_path is not None:
        values.extend(read_facility_numbers_file(facility_input_path))
    if not values:
        values.append(DEFAULT_LIVE_FACILITY_NUMBER)
    return normalize_facility_numbers(values)


if __name__ == "__main__":
    main()