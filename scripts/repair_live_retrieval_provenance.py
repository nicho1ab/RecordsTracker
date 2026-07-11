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
from ccld_complaints.hosted_app.retrieval_provenance_repair import (  # noqa: E402
    repair_live_retrieval_provenance,
)

MISSING_DATABASE_URL_MESSAGE = (
    f"Live retrieval provenance repair requires {DATABASE_URL_ENV} to point to a "
    "configured hosted PostgreSQL database with Alembic migrations applied. The repair "
    "uses only persisted source-traceability artifact IDs and matching live public CCLD "
    "retrieval job metadata."
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Dry-run or apply a bounded repair for source-derived rows that were imported "
            "from live public CCLD retrieval jobs but persisted under reused import batches."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the repair. Omit for read-only dry-run reporting.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        database_config = load_hosted_database_config(require_url=True)
        engine = create_engine(cast(str, database_config.database_url))
        with engine.connect() as connection:
            result = repair_live_retrieval_provenance(
                connection,
                dry_run=not args.apply,
            )
            if args.apply and connection.in_transaction():
                connection.commit()
    except HostedDatabaseConfigError:
        print(MISSING_DATABASE_URL_MESSAGE, file=sys.stderr)
        return 2
    except SQLAlchemyError:
        print(
            "Live retrieval provenance repair could not open or update the configured "
            "hosted database. Set the database URL, run migrations, and retry.",
            file=sys.stderr,
        )
        return 2
    finally:
        if "engine" in locals():
            engine.dispose()

    print(json.dumps(result.__dict__, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
