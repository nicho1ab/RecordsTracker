from __future__ import annotations

import argparse
from pathlib import Path

from ccld_complaints.local_sample import (
    DEFAULT_SAMPLE_DB_PATH,
    datasette_command,
    populate_sample_database,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Populate the local SQLite database from bundled CCLD fixtures."
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_SAMPLE_DB_PATH,
        help="SQLite database path to initialize and populate.",
    )
    args = parser.parse_args()

    result = populate_sample_database(args.db_path)
    db_path = result.db_path
    ingestion = result.ingestion

    print(f"SQLite database: {db_path.as_posix()}")
    print(f"Records written: {len(ingestion.records)}")
    print(f"Discovered fixture candidates: {len(ingestion.candidates)}")
    print(f"Candidates without bundled raw fixture content: {len(ingestion.failures)}")
    print("Open in Datasette:")
    print(datasette_command(db_path))


if __name__ == "__main__":
    main()