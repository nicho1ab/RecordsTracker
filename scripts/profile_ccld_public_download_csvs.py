"""CLI: Profile CCLD public download CSVs and emit normalized facility-reference CSV."""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

import argparse  # noqa: E402

from ccld_complaints.ccld_public_download import (  # noqa: E402
    LIMITATIONS_NOTE,
    filter_rows,
    parse_ccld_download_csv,
    write_facility_reference_csv,
    write_profile_csv,
    write_profile_json,
)

DEFAULT_INPUT_DIR = Path("data/raw/ccld")
DEFAULT_OUTPUT_DIR = Path("data/processed/ccld-public-downloads")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Profile CCLD public download CSVs and emit a normalized "
            "facility-reference CSV for cohort selection. "
            "Local profiling only; no database writes, schema changes, or "
            "network requests."
        )
    )
    parser.add_argument(
        "csv_files",
        nargs="*",
        type=Path,
        metavar="CSV_FILE",
        help=(
            "One or more CCLD public download CSV files to profile. "
            "If omitted, all *.csv files under --input-dir are used."
        ),
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help="Directory to scan for CSV files when no explicit files are given.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory for profile JSON, profile CSV, and reference CSV.",
    )
    parser.add_argument(
        "--facility-type",
        default=None,
        help=(
            "Filter the reference CSV to this facility type only "
            "(case-insensitive, e.g. 'Temporary Shelter Care Facility')."
        ),
    )
    parser.add_argument(
        "--facility-status",
        default=None,
        help=(
            "Filter the reference CSV to this facility status only "
            "(case-insensitive, e.g. 'Licensed')."
        ),
    )
    parser.add_argument(
        "--reference-csv-name",
        default="facility-reference.csv",
        help="Output file name for the normalized reference CSV.",
    )
    args = parser.parse_args(argv)

    # Resolve input files
    input_paths: list[Path]
    if args.csv_files:
        input_paths = [p.resolve() for p in args.csv_files]
    else:
        input_dir = args.input_dir.resolve()
        if not input_dir.exists():
            print(f"Error: input directory does not exist: {input_dir}")
            return 1
        input_paths = sorted(input_dir.glob("*.csv"))

    if not input_paths:
        print("No CSV files found.")
        return 1

    output_dir: Path = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Parse all files
    parsed = []
    for path in input_paths:
        print(f"Parsing: {path.name}")
        parsed.append(parse_ccld_download_csv(path))

    # Write profile outputs
    profile_json_path = output_dir / "ccld-download-profile.json"
    profile_csv_path = output_dir / "ccld-download-profile.csv"
    write_profile_json(parsed, profile_json_path)
    write_profile_csv(parsed, profile_csv_path)

    # Collect all facility rows across files, then filter and deduplicate
    all_rows = [row for pf in parsed for row in pf.rows]
    filtered = filter_rows(
        all_rows,
        facility_type=args.facility_type,
        status=args.facility_status,
    )

    # Deduplicate by facility number (first occurrence wins)
    seen: set[str] = set()
    deduped = []
    for row in filtered:
        if row.facility_number and row.facility_number not in seen:
            seen.add(row.facility_number)
            deduped.append(row)

    ref_csv_path = output_dir / args.reference_csv_name
    written = write_facility_reference_csv(deduped, ref_csv_path)

    # Print summary
    total_rows = sum(pf.row_count for pf in parsed)
    total_warnings = sum(pf.row_width_warning_count for pf in parsed)
    print(f"\nFiles profiled:     {len(parsed)}")
    print(f"Total rows parsed:  {total_rows}")
    print(f"Row-width warnings: {total_warnings} (rows with extra complaint-info values)")
    print(f"FacilityType filter: {args.facility_type or '(none)'}")
    print(f"FacilityStatus filter: {args.facility_status or '(none)'}")
    print(f"Reference CSV rows: {written}")
    print(f"\nProfile JSON:  {profile_json_path.as_posix()}")
    print(f"Profile CSV:   {profile_csv_path.as_posix()}")
    print(f"Reference CSV: {ref_csv_path.as_posix()}")
    print(f"\n{LIMITATIONS_NOTE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
