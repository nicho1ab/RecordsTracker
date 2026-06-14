from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import create_engine

from ccld_complaints.hosted_app.persistence import load_hosted_database_config
from ccld_complaints.hosted_app.seeded_import import (
    import_seeded_corpus_artifact,
    load_seeded_corpus_artifact,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Import a controlled hosted tester seeded corpus artifact."
    )
    parser.add_argument("artifact_path", type=Path, help="Validated seeded corpus JSON artifact.")
    args = parser.parse_args(argv)

    artifact = load_seeded_corpus_artifact(args.artifact_path)
    database_config = load_hosted_database_config(require_url=True)
    if database_config.database_url is None:
        raise RuntimeError("Hosted tester database URL is required for seeded corpus import.")

    engine = create_engine(database_config.database_url)
    with engine.begin() as connection:
        result = import_seeded_corpus_artifact(connection, artifact)

    print(f"Imported hosted seeded corpus batch: {result.import_batch_id}")
    print(f"Source-derived records staged: {result.imported_record_count}")
    print("Reviewer-created state written: no")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())