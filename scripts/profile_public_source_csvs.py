from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from ccld_complaints.source_profiling import (  # noqa: E402
    DEFAULT_LOG_PATH,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_SOURCE_ROOT,
    profile_csv_tree,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Profile local ignored public-source CSV files without importing data."
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=DEFAULT_SOURCE_ROOT,
        help="Local source-profiling folder to scan recursively for CSV files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Ignored output folder for JSON and CSV profile summaries.",
    )
    parser.add_argument(
        "--log-path",
        type=Path,
        default=DEFAULT_LOG_PATH,
        help="Ignored log file path for the profiling run.",
    )
    args = parser.parse_args()

    summary = profile_csv_tree(
        source_root=args.source_root,
        output_dir=args.output_dir,
        log_path=args.log_path,
        workspace_root=REPO_ROOT,
    )
    totals = summary["totals"]
    print(f"Profiled CSV files: {totals['csv_file_count']}")
    print(f"Skipped non-CSV files: {totals['skipped_non_csv_file_count']}")
    print(f"Total rows profiled: {totals['total_row_count']}")
    print(f"Parser warnings: {totals['total_parser_warning_count']}")
    print(f"Malformed or irregular rows: {totals['total_malformed_row_count']}")
    print(f"JSON summary: {(args.output_dir / 'csv-profile-summary.json').as_posix()}")
    print(f"CSV summary: {(args.output_dir / 'csv-profile-summary.csv').as_posix()}")
    print(f"Log: {args.log_path.as_posix()}")
    print(
        "Boundary: local profiling only; no raw file edits, imports, "
        "schema changes, or connectors."
    )


if __name__ == "__main__":
    main()