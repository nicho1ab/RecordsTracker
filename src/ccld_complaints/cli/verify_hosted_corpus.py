"""CLI for the supported read-only hosted corpus verification command."""

from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import create_engine

from ccld_complaints.hosted_app.corpus_verification import (
    run_hosted_corpus_verification,
    set_postgresql_transaction_read_only,
    write_corpus_verification_result,
)
from ccld_complaints.hosted_app.persistence import load_hosted_database_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify the hosted corpus without mutation.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--deployed-sha")
    parser.add_argument("--displayed-facility-count", type=int)
    parser.add_argument("--displayed-complaint-count", type=int)
    args = parser.parse_args(argv)
    if args.displayed_facility_count is not None and args.displayed_facility_count < 0:
        parser.error("--displayed-facility-count must not be negative")
    if args.displayed_complaint_count is not None and args.displayed_complaint_count < 0:
        parser.error("--displayed-complaint-count must not be negative")
    config = load_hosted_database_config(require_url=True)
    if config.database_url is None:
        raise RuntimeError("Hosted PostgreSQL configuration is required.")
    engine = create_engine(config.database_url)
    with engine.connect() as connection:
        with connection.begin():
            set_postgresql_transaction_read_only(connection)
            result = run_hosted_corpus_verification(
                connection,
                deployed_sha=args.deployed_sha,
                displayed_facility_count=args.displayed_facility_count,
                displayed_complaint_count=args.displayed_complaint_count,
            )
    output_hash = write_corpus_verification_result(args.output, result)
    print(f"Corpus verification JSON: {args.output.name}")
    print(f"SHA-256: {output_hash}")
    if result["blocking_failures"]:
        print("FAIL: " + ", ".join(result["blocking_failures"]))
        return 1
    print("PASS: hosted corpus verification acceptance conditions met")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
