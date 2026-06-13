from __future__ import annotations

import argparse
from pathlib import Path

from ccld_complaints.connectors.ccld import CcldFacilityReportsConnector
from ccld_complaints.connectors.ccld.facility_reports import (
    LIVE_REQUEST_TIMEOUT_SECONDS,
    LIVE_USER_AGENT,
    FacilityIngestionResult,
    FacilityNumberIntakeResult,
    FacilityWorkflowFailure,
    ingest_facility_reports_for_facilities,
    ingest_facility_reports_for_facility,
    inspect_facility_numbers,
    read_facility_number_input_file,
)
from ccld_complaints.local_sample import (
    DEFAULT_SAMPLE_DB_PATH,
    datasette_command,
    review_workflow_lines,
    write_datasette_metadata,
)

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
        facility_intake = _collect_facility_number_intake(
            args.facility_numbers,
            args.facility_input_path,
        )
    except ValueError as exc:
        parser.error(str(exc))
    facility_numbers = facility_intake.facility_numbers

    limit = None if args.all else args.limit
    estimated_request_count = "discovery requests plus all discovered report requests"
    if limit is not None:
        estimated_request_count = (
            "up to 2 discovery requests per facility plus "
            f"{limit} report request(s) per facility"
        )

    print("Warning: this command accesses the public CCLD external site.")
    print("Run it only when you intend to make live public web requests.")
    for line in facility_intake_summary_lines(facility_intake):
        print(line)
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
        facility_results = [single_result]
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
        facility_results = multi_result.facility_results
        report_failures = multi_result.failures
        facility_failures = multi_result.facility_failures

    for line in live_fetch_summary_lines(facility_results, facility_failures):
        print(line)
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

    metadata_path = write_datasette_metadata(args.db_path)
    print(f"Datasette metadata: {metadata_path.as_posix()}")
    print("Open in Datasette:")
    print(datasette_command(args.db_path))
    for line in review_workflow_lines():
        print(line)


def live_fetch_summary_lines(
    facility_results: list[FacilityIngestionResult],
    facility_failures: list[FacilityWorkflowFailure],
) -> list[str]:
    discovered = sum(result.discovered_count for result in facility_results)
    selected = sum(len(result.candidates) for result in facility_results)
    skipped = sum(
        max(result.discovered_count - len(result.candidates), 0)
        for result in facility_results
    )
    written = sum(len(result.records) for result in facility_results)
    report_failures = sum(len(result.failures) for result in facility_results)
    fetched = written + sum(
        1
        for result in facility_results
        for failure in result.failures
        if failure.stage in _POST_FETCH_FAILURE_STAGES
    )

    lines = [
        "Live fetch summary:",
        f"- Facilities requested: {len(facility_results) + len(facility_failures)}",
        f"- Facilities with discovery failures: {len(facility_failures)}",
        f"- Report candidates discovered: {discovered}",
        f"- Report candidates selected: {selected}",
        f"- Reports skipped by limit: {skipped}",
        f"- Reports fetched: {fetched}",
        f"- Records written: {written}",
        f"- Report failures: {report_failures}",
    ]

    if facility_results:
        lines.append("Facility summary:")
    for result in facility_results:
        lines.append(_facility_summary_line(result))

    if facility_failures:
        lines.append("Facility failures:")
    for failure in facility_failures:
        lines.append(
            "- "
            f"{failure.facility_number}: stage={failure.stage}, "
            f"error={failure.error_type}, message={failure.message}"
        )

    return lines


def facility_intake_summary_lines(intake: FacilityNumberIntakeResult) -> list[str]:
    lines = [
        "Facility identifier intake:",
        f"- Accepted facility identifiers: {', '.join(intake.facility_numbers)}",
        f"- Duplicate identifiers ignored: {_summary_values(intake.duplicate_facility_numbers)}",
        f"- Ignored blank, comment, or header values: {intake.ignored_value_count}",
    ]
    if intake.invalid_values:
        lines.append(f"- Invalid identifiers rejected: {_summary_values(intake.invalid_values)}")
    return lines


_POST_FETCH_FAILURE_STAGES = {"extract", "normalize", "validate", "emit"}


def _facility_summary_line(result: FacilityIngestionResult) -> str:
    skipped = max(result.discovered_count - len(result.candidates), 0)
    fetched = len(result.records) + sum(
        1 for failure in result.failures if failure.stage in _POST_FETCH_FAILURE_STAGES
    )
    return (
        "- "
        f"{result.facility_number}: discovered={result.discovered_count}, "
        f"selected={len(result.candidates)}, skipped={skipped}, "
        f"fetched={fetched}, written={len(result.records)}, failed={len(result.failures)}"
    )


def _collect_facility_number_intake(
    facility_numbers: list[str] | None,
    facility_input_path: Path | None,
) -> FacilityNumberIntakeResult:
    values = list(facility_numbers or [])
    has_explicit_facility_input = bool(values) or facility_input_path is not None
    ignored_value_count = 0
    if facility_input_path is not None:
        input_file = read_facility_number_input_file(facility_input_path)
        values.extend(input_file.values)
        ignored_value_count += input_file.ignored_value_count
    if not values and not has_explicit_facility_input:
        values.append(DEFAULT_LIVE_FACILITY_NUMBER)
    intake = inspect_facility_numbers(values)
    ignored_value_count += intake.ignored_value_count
    if intake.invalid_values:
        invalid_values = ", ".join(repr(value) for value in intake.invalid_values)
        raise ValueError(f"Facility number must contain digits only: {invalid_values}")
    if not intake.facility_numbers:
        raise ValueError("At least one facility number is required.")
    return FacilityNumberIntakeResult(
        facility_numbers=intake.facility_numbers,
        duplicate_facility_numbers=intake.duplicate_facility_numbers,
        ignored_value_count=ignored_value_count,
        invalid_values=[],
    )


def _summary_values(values: list[str]) -> str:
    return ", ".join(values) if values else "none"


if __name__ == "__main__":
    main()