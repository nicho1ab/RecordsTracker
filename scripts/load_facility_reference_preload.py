from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from ccld_complaints.hosted_app.facility_reference_preload import (  # noqa: E402
    DEFAULT_FACILITY_REFERENCE_PRELOAD_INPUT_PATH,
    load_facility_reference_preload,
    open_configured_facility_reference_connection,
)
from ccld_complaints.hosted_app.persistence import (  # noqa: E402
    DATABASE_URL_ENV,
    HostedDatabaseConfigError,
)

MISSING_DATABASE_URL_MESSAGE = (
    f"Facility reference preload requires {DATABASE_URL_ENV} to point to a "
    "configured local/test PostgreSQL database. Dry-run mode also needs the "
    "database because it compares local CSV rows against existing "
    "hosted_facility_reference_records rows to calculate inserted, updated, "
    "and unchanged counts. Set the database URL, run migrations, then rerun "
    "with -DryRun first or -Apply when ready to write rows."
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Preload local CHHS/CDSS CCLD facility CSV rows into the hosted "
            "PostgreSQL facility-reference table."
        )
    )
    parser.add_argument(
        "--input-path",
        type=Path,
        default=DEFAULT_FACILITY_REFERENCE_PRELOAD_INPUT_PATH,
        help="Local CSV file or folder to scan recursively for CSV files.",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--dry-run",
        "-DryRun",
        dest="dry_run",
        action="store_true",
        help="Compare local CSV rows to the database without writing changes.",
    )
    mode_group.add_argument(
        "--apply",
        "-Apply",
        dest="apply",
        action="store_true",
        help="Insert or refresh facility reference rows in the configured database.",
    )
    parser.add_argument(
        "--source-accessed-at",
        help=(
            "Optional ISO timestamp to store as source_accessed_at for all rows. "
            "Defaults to each CSV file modification time."
        ),
    )
    return parser


def apply_changes_from_args(args: argparse.Namespace) -> bool:
    return bool(args.apply)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    apply_changes = apply_changes_from_args(args)
    try:
        with open_configured_facility_reference_connection() as connection:
            if apply_changes:
                with connection.begin():
                    result = load_facility_reference_preload(
                        args.input_path,
                        connection=connection,
                        apply_changes=True,
                        source_accessed_at=args.source_accessed_at,
                    )
            else:
                result = load_facility_reference_preload(
                    args.input_path,
                    connection=connection,
                    apply_changes=False,
                    source_accessed_at=args.source_accessed_at,
                )
    except HostedDatabaseConfigError:
        print(MISSING_DATABASE_URL_MESSAGE, file=sys.stderr)
        return 2

    mode_label = "apply" if result.apply_changes else "dry-run"
    print(f"Facility reference preload mode: {mode_label}")
    print(f"Input path: {result.input_path.as_posix()}")
    print(
        "Totals: "
        f"inserted={result.inserted_row_count}, "
        f"updated={result.updated_row_count}, "
        f"unchanged={result.unchanged_row_count}, "
        f"skipped={result.skipped_row_count}, "
        f"warnings={result.warning_count}"
    )
    for resource in result.resource_results:
        print(
            "Resource: "
            f"{resource.source_resource_name} "
            f"({resource.source_resource_id}) from {resource.source_file_name}: "
            f"parsed={resource.parsed_row_count}, "
            f"inserted={resource.inserted_row_count}, "
            f"updated={resource.updated_row_count}, "
            f"unchanged={resource.unchanged_row_count}, "
            f"skipped={resource.skipped_row_count}, "
            f"warnings={resource.warning_count}"
        )
        for warning in resource.warnings[:5]:
            print(f"  warning row {warning.row_number}: {warning.message}")
        if len(resource.warnings) > 5:
            print(f"  warning rows omitted: {len(resource.warnings) - 5}")
    print("Boundary: local CSV preload only; no live CHHS download or retrieval was run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
