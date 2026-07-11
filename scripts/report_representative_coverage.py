from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import cast

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from ccld_complaints.hosted_app.persistence import (  # noqa: E402
    DATABASE_URL_ENV,
    HostedDatabaseConfigError,
    load_hosted_database_config,
)
from ccld_complaints.hosted_app.representative_coverage import (  # noqa: E402
    build_representative_coverage_report,
)

MISSING_DATABASE_URL_MESSAGE = (
    f"Representative coverage reporting requires {DATABASE_URL_ENV} to point to a "
    "configured local/test PostgreSQL database with Alembic migrations applied. "
    "The report is read-only, classifies persisted provenance, and excludes "
    "clearly identified fixture/demo/test rows and unknown-provenance rows from "
    "representative coverage counts."
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a read-only representative CCLD facility/complaint coverage "
            "and reconciliation report from hosted PostgreSQL tables."
        )
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        help="Optional path for the JSON report. Omit to print JSON to stdout.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        database_config = load_hosted_database_config(require_url=True)
        engine = create_engine(cast(str, database_config.database_url))
        with engine.connect() as connection:
            report = build_representative_coverage_report(connection)
    except HostedDatabaseConfigError:
        print(MISSING_DATABASE_URL_MESSAGE, file=sys.stderr)
        return 2
    except SQLAlchemyError:
        print(
            "Representative coverage report could not read the configured hosted database. "
            "Set the database URL, run migrations, and retry.",
            file=sys.stderr,
        )
        return 2
    finally:
        if "engine" in locals():
            engine.dispose()

    report_json = json.dumps(report, indent=2, sort_keys=True)
    if args.output_json is None:
        print(report_json)
    else:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(f"{report_json}\n", encoding="utf-8")
        print(f"Representative coverage report written: {args.output_json.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
