from __future__ import annotations

import argparse
from pathlib import Path

from ccld_complaints.local_sample import DEFAULT_SAMPLE_DB_PATH
from ccld_complaints.review_bundle import DEFAULT_REVIEW_BUNDLE_DIR, export_review_bundle


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export source-traceable CSV review outputs from the local SQLite database."
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_SAMPLE_DB_PATH,
        help="SQLite database path to export from.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_REVIEW_BUNDLE_DIR,
        help="Directory where review bundle CSV files will be written.",
    )
    args = parser.parse_args()

    result = export_review_bundle(args.db_path, args.output_dir)

    print(f"Review bundle: {result.output_dir.as_posix()}")
    for exported_file in result.files:
        print(f"CSV: {exported_file.path.as_posix()} ({exported_file.row_count} rows)")
    print(f"Notes: {result.readme_path.as_posix()}")
    print(
        "Delay review flags are screening aids only; "
        "verify important details against source documents."
    )


if __name__ == "__main__":
    main()