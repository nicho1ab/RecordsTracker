from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from ccld_complaints.hosted_app.facility_reference_preload import (  # noqa: E402
    FacilityReferenceAddressDiagnostic,
    diagnose_facility_reference_address,
    open_configured_facility_reference_connection,
)
from ccld_complaints.hosted_app.persistence import (  # noqa: E402
    DATABASE_URL_ENV,
    HostedDatabaseConfigError,
)

MISSING_DATABASE_URL_MESSAGE = (
    f"Facility reference address diagnostics require {DATABASE_URL_ENV} to point "
    "to the local/test hosted database that already contains preloaded "
    "hosted_facility_reference_records rows. The command is read-only and does "
    "not download source data, run complaint retrieval, or write database rows."
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Diagnose whether a preloaded facility reference row is missing "
            "address data in the original source row or during normalization."
        )
    )
    parser.add_argument(
        "--facility-number",
        "-FacilityNumber",
        required=True,
        help="Digit CCLD facility/license number to inspect.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the diagnostic as JSON instead of readable text.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        with open_configured_facility_reference_connection() as connection:
            diagnostics = diagnose_facility_reference_address(
                connection,
                args.facility_number,
            )
    except HostedDatabaseConfigError:
        print(MISSING_DATABASE_URL_MESSAGE, file=sys.stderr)
        return 2
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps([_diagnostic_dict(item) for item in diagnostics], indent=2))
        return 0

    facility_number = args.facility_number.strip()
    print(f"Facility reference address diagnostic for {facility_number}")
    print("Mode: read-only; no downloads, retrieval, or writes.")
    if not diagnostics:
        print("No preloaded facility reference row matched this facility number.")
        return 1
    for index, item in enumerate(diagnostics, start=1):
        print(f"Row {index}:")
        print(f"  facility_number: {item.facility_number}")
        print(f"  facility_name: {item.facility_name}")
        print(f"  source_resource_name: {item.source_resource_name}")
        print(f"  source_resource_id: {item.source_resource_id}")
        print(f"  source_file_name: {item.source_file_name or 'not listed'}")
        print("  normalized_address_fields:")
        for key, value in item.normalized_address_fields.items():
            print(f"    {key}: {value or 'not listed'}")
        print("  raw_address_like_source_columns:")
        if item.raw_address_fields:
            for key, value in item.raw_address_fields.items():
                print(f"    {key}: {value or 'blank'}")
        else:
            print("    none found")
        print(f"  conclusion: {item.conclusion}")
    return 0


def _diagnostic_dict(item: FacilityReferenceAddressDiagnostic) -> dict[str, object]:
    return {
        "facility_number": item.facility_number,
        "facility_name": item.facility_name,
        "source_resource_name": item.source_resource_name,
        "source_resource_id": item.source_resource_id,
        "source_file_name": item.source_file_name,
        "normalized_address_fields": dict(item.normalized_address_fields),
        "raw_address_like_source_columns": dict(item.raw_address_fields),
        "conclusion": item.conclusion,
    }


if __name__ == "__main__":
    raise SystemExit(main())
