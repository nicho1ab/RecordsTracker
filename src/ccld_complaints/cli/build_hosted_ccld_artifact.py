from __future__ import annotations

import argparse
from pathlib import Path

from ccld_complaints.hosted_app.ccld_hosted_artifact_builder import (
    DEFAULT_CCLD_HOSTED_IMPORT_BATCH_ID,
    DEFAULT_GENERATED_CCLD_HOSTED_ARTIFACT,
    write_ccld_hosted_seeded_corpus_artifact,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a local/test CCLD-only hosted seeded-corpus JSON artifact from "
            "validated CCLD SQLite pipeline output."
        )
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        required=True,
        help="Validated CCLD SQLite pipeline output path.",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=DEFAULT_GENERATED_CCLD_HOSTED_ARTIFACT,
        help="Hosted seeded-corpus JSON artifact path to write.",
    )
    parser.add_argument(
        "--facility-number",
        help="CCLD facility/license number. Required when SQLite contains multiple facilities.",
    )
    parser.add_argument("--start-date", help="Optional inclusive YYYY-MM-DD start date filter.")
    parser.add_argument("--end-date", help="Optional inclusive YYYY-MM-DD end date filter.")
    parser.add_argument(
        "--import-batch-id",
        default=DEFAULT_CCLD_HOSTED_IMPORT_BATCH_ID,
        help="Hosted seeded corpus import batch ID. Defaults to the local/test reviewer scope.",
    )
    parser.add_argument(
        "--imported-at",
        help="Optional ISO datetime for deterministic local/test artifact generation.",
    )
    parser.add_argument(
        "--source-artifact-identity",
        help="Optional non-secret artifact identity. Defaults to a SQLite file hash identity.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace the output artifact if it already exists.",
    )
    args = parser.parse_args(argv)

    try:
        result = write_ccld_hosted_seeded_corpus_artifact(
            args.db_path,
            args.output_path,
            facility_number=args.facility_number,
            start_date=args.start_date,
            end_date=args.end_date,
            import_batch_id=args.import_batch_id,
            imported_at=args.imported_at,
            source_artifact_identity=args.source_artifact_identity,
            overwrite=args.overwrite,
        )
    except ValueError as error:
        parser.error(str(error))

    if result.output_path is None:
        raise RuntimeError("Expected artifact builder to return the written output path.")
    print(f"Hosted seeded-corpus artifact: {result.output_path.as_posix()}")
    print(f"CCLD facility/license number: {result.facility_number}")
    print(f"Normalized CCLD record bundles: {result.record_count}")
    print(f"Source-derived rows represented: {result.source_derived_record_count}")
    print("Live CCLD retrieval executed: no")
    print("Browser request execution required: no")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())