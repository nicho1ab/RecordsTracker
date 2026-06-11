from __future__ import annotations

import argparse
from pathlib import Path

from ccld_complaints.connectors.ccld import CcldFacilityReportsConnector
from ccld_complaints.connectors.ccld.facility_reports import (
    LIVE_REQUEST_TIMEOUT_SECONDS,
    LIVE_USER_AGENT,
    ingest_facility_reports_for_facility,
)
from ccld_complaints.local_sample import DEFAULT_SAMPLE_DB_PATH, datasette_command

DEFAULT_LIVE_RAW_DIR = Path("data/raw/ccld")
DEFAULT_LIVE_FACILITY_NUMBER = "157806098"
DEFAULT_LIVE_LIMIT = 1
DEFAULT_LIVE_MAX_REQUESTS = 5


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch live public CCLD report content for one facility, store raw files locally, "
            "and ingest the saved files into SQLite."
        )
    )
    parser.add_argument(
        "--facility-number",
        default=DEFAULT_LIVE_FACILITY_NUMBER,
        help="Public CCLD facility number to fetch. Defaults to the POC facility.",
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

    limit = None if args.all else args.limit
    estimated_request_count = "discovery requests plus all discovered report requests"
    if limit is not None:
        estimated_request_count = f"up to 2 discovery requests plus {limit} report request(s)"

    print("Warning: this command accesses the public CCLD external site.")
    print("Run it only when you intend to make live public web requests.")
    print(f"Facility number: {args.facility_number}")
    print(f"Raw files: {args.raw_dir.as_posix()}")
    print(f"SQLite database: {args.db_path.as_posix()}")
    print(f"Request policy: timeout {LIVE_REQUEST_TIMEOUT_SECONDS}s, user-agent {LIVE_USER_AGENT}")
    print(
        f"Request count: {estimated_request_count}; "
        f"max report requests {args.max_requests}; no retry loop is used."
    )

    connector = CcldFacilityReportsConnector(
        facility_number=args.facility_number,
        raw_dir=args.raw_dir,
        db_path=args.db_path,
    )
    result = ingest_facility_reports_for_facility(
        facility_number=args.facility_number,
        connector=connector,
        limit=limit,
        max_requests=args.max_requests,
    )

    print(f"Discovered candidates selected: {len(result.candidates)}")
    print(f"Records written: {len(result.records)}")
    print(f"Failures recorded: {len(result.failures)}")
    for failure in result.failures:
        print(
            "Failure: "
            f"report_index={failure.candidate.report_index} "
            f"stage={failure.stage} "
            f"error={failure.error_type} "
            f"message={failure.message}"
        )

    print("Open in Datasette:")
    print(datasette_command(args.db_path))


if __name__ == "__main__":
    main()