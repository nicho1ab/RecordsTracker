from __future__ import annotations

import argparse
import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from sqlalchemy import func, inspect, select
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError

from ccld_complaints.hosted_app.persistence import (
    HostedDatabaseConfigError,
    load_hosted_database_config,
)
from ccld_complaints.hosted_app.seeded_import import hosted_source_derived_records
from ccld_complaints.source_to_screen_audit import _runtime_engine
from ccld_complaints.source_to_screen_coverage import (
    CoverageReadError,
    load_validated_coverage_package,
)

DEFAULT_PACKAGE_DIR = Path(
    "/app/data/processed/source-to-screen-audit/runtime-current"
)
PACKAGE_DIR_ENV = "CCLD_OPERATOR_COVERAGE_PACKAGE_DIR"


def verify_runtime_coverage(
    *,
    environ: Mapping[str, str] | None = None,
    package_dir: Path | None = None,
    connection: Connection | None = None,
) -> Mapping[str, Any]:
    """Reconcile the validated package with safe SELECT-only database totals."""

    environment = os.environ if environ is None else environ
    configured_package = package_dir or Path(
        environment.get(PACKAGE_DIR_ENV, str(DEFAULT_PACKAGE_DIR))
    )
    package = load_validated_coverage_package(configured_package)
    if connection is not None:
        database_facility_total = _database_facility_total(connection)
    else:
        load_hosted_database_config(environ=environment, require_url=True)
        engine = _runtime_engine(environment)
        try:
            if engine.dialect.name != "postgresql":
                raise RuntimeError("Runtime coverage verification requires PostgreSQL.")
            with engine.connect() as runtime_connection:
                database_facility_total = _database_facility_total(runtime_connection)
        finally:
            engine.dispose()
    report_total = int(package.report["operations"]["existing_facility_total"])
    index_total = len(package.facility_rows)
    reconciled = database_facility_total == report_total == index_total
    return {
        "status": "passed" if reconciled else "failed",
        "report_id": package.report["report_id"],
        "contract_version": package.manifest["contract_version"],
        "package_state": package.state,
        "database_facility_total": database_facility_total,
        "report_existing_facility_total": report_total,
        "facility_index_total": index_total,
        "unavailable_dimensions": list(package.unavailable_dimensions),
        "hashes_and_reconciliation_validated": True,
        "database_mutations_performed": False,
    }


def _database_facility_total(connection: Connection) -> int:
    if hosted_source_derived_records.name not in inspect(connection).get_table_names():
        raise RuntimeError("The governed source-derived read table is unavailable.")
    return int(
        connection.scalar(
            select(func.count())
            .select_from(hosted_source_derived_records)
            .where(hosted_source_derived_records.c.entity_type == "facility")
        )
        or 0
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify current operator coverage with safe read-only totals."
    )
    parser.add_argument("--package-dir", type=Path)
    args = parser.parse_args(argv)
    try:
        result = verify_runtime_coverage(package_dir=args.package_dir)
    except (
        CoverageReadError,
        HostedDatabaseConfigError,
        RuntimeError,
        SQLAlchemyError,
        OSError,
    ):
        print(
            json.dumps(
                {
                    "status": "failed",
                    "reason_category": "runtime_verification_unavailable",
                    "database_mutations_performed": False,
                },
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
