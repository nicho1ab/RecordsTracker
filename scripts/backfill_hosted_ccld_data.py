from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from ccld_complaints.hosted_app.ccld_backfill import (  # noqa: E402
    CcldHostedBackfillRequest,
    run_ccld_hosted_backfill,
)
from ccld_complaints.hosted_app.ccld_source_refresh import (  # noqa: E402
    FacilityReferenceConfigurationError,
)
from ccld_complaints.hosted_app.facility_reference_preload import (  # noqa: E402
    open_configured_facility_reference_connection,
)
from ccld_complaints.hosted_app.persistence import (  # noqa: E402
    DATABASE_URL_ENV,
    HostedDatabaseConfigError,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Dry-run or apply the governed hosted CCLD facility-reference and preserved-"
            "artifact refresh without making live public-source requests."
        )
    )
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--facility-number")
    selection.add_argument("--facility-number-file", type=Path)
    selection.add_argument("--all-existing", action="store_true")
    parser.add_argument(
        "--operation",
        choices=("all", "facility-reference", "preserved-artifacts"),
        default="all",
    )
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--checkpoint-file", type=Path)
    parser.add_argument("--restart", action="store_true")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        facility_numbers = _facility_numbers(args)
        request = CcldHostedBackfillRequest(
            facility_numbers=facility_numbers,
            all_existing=bool(args.all_existing),
            operation=args.operation,
            batch_size=args.batch_size,
            apply_changes=bool(args.apply),
            checkpoint_file=args.checkpoint_file,
            restart=bool(args.restart),
        )
        with open_configured_facility_reference_connection() as connection:
            result = run_ccld_hosted_backfill(connection, request)
            if request.apply_changes:
                connection.commit()
            else:
                connection.rollback()
    except (HostedDatabaseConfigError, FacilityReferenceConfigurationError, ValueError) as error:
        print(f"Configuration validation failed: {_safe_error(error)}", file=sys.stderr)
        return 2
    except Exception:
        print(
            "Hosted CCLD backfill failed safely. Check operator logs for details.",
            file=sys.stderr,
        )
        return 1

    mode = "apply" if result.apply_changes else "dry-run"
    print(f"Hosted CCLD backfill mode: {mode}")
    print(
        "Totals: "
        f"examined={result.examined}, "
        f"eligible={result.eligible}, "
        f"updated={result.updated}, "
        f"unchanged={result.unchanged}, "
        f"skipped={result.skipped}, "
        f"conflicted={result.conflicted}, "
        f"warnings={result.warnings}, "
        f"failed={result.failed}"
    )
    print("Boundary: preserved artifacts and configured facility reference only; no live calls.")
    return 1 if result.failed else 0


def _facility_numbers(args: argparse.Namespace) -> tuple[str, ...]:
    if args.all_existing:
        return ()
    values: list[str] = []
    if args.facility_number:
        values.append(str(args.facility_number).strip())
    elif args.facility_number_file:
        for line in args.facility_number_file.read_text(encoding="utf-8-sig").splitlines():
            value = line.strip()
            if value and not value.startswith("#"):
                values.append(value)
    normalized = tuple(dict.fromkeys(values))
    if not normalized:
        raise ValueError("At least one facility number is required.")
    if any(not value.isdigit() for value in normalized):
        raise ValueError("Facility numbers must contain digits only.")
    return normalized


def _safe_error(error: Exception) -> str:
    message = str(error)
    if DATABASE_URL_ENV in message:
        return f"Set and validate {DATABASE_URL_ENV} before running the command."
    allowed_fragments = (
        "Facility-reference configuration",
        "Hosted source-derived tables",
        "batch_size",
        "Facility numbers",
        "At least one facility number",
        "checkpoint",
        "Select either",
        "Unsupported CCLD hosted backfill operation",
    )
    if any(fragment in message for fragment in allowed_fragments):
        return message
    return "The configured database, selection, checkpoint, or reference data is invalid."


if __name__ == "__main__":
    raise SystemExit(main())
