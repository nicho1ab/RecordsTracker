from __future__ import annotations

import argparse
from pathlib import Path

from ccld_complaints.local_sample import DEFAULT_SAMPLE_DB_PATH
from ccld_complaints.stakeholder_extract import (
    DEFAULT_STAKEHOLDER_EXTRACT_ROOT,
    export_stakeholder_facility_overview,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export a stakeholder facility overview extract (CSV ZIP) "
            "from the local SQLite database."
        )
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_SAMPLE_DB_PATH,
        help="SQLite database path to export from.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_STAKEHOLDER_EXTRACT_ROOT,
        help="Root directory under which a timestamped output folder is created.",
    )
    parser.add_argument(
        "--facility-reference-csv",
        type=Path,
        default=None,
        help=(
            "Optional path to a facility reference CSV. When provided, "
            "facilities in the reference are included in facility-overview.csv "
            "even when no complaint records are loaded for them. "
            "Complaint counts are always based only on loaded records."
        ),
    )
    args = parser.parse_args(argv)

    result = export_stakeholder_facility_overview(
        args.db_path,
        args.output_root,
        facility_reference_csv=args.facility_reference_csv,
    )

    print(f"Output directory: {result.output_dir.as_posix()}")
    print(f"facility-overview.csv: {result.facility_row_count} facilities")
    print(
        f"substantiated-complaints.csv: "
        f"{result.substantiated_complaint_row_count} substantiated/equivalent records"
    )
    if result.facility_reference_csv != "none":
        print(
            f"Facility reference: {result.facility_reference_csv} "
            f"({result.facility_reference_row_count} rows, "
            f"{result.facility_reference_matched_count} matched loaded complaints)"
        )
    print(f"ZIP: {result.zip_path.as_posix()}")
    print(f"Git commit: {result.git_commit}")
    print(result.limitations)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
