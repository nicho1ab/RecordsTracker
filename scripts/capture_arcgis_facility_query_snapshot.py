from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = REPOSITORY_ROOT / "src"
if str(SOURCE_PATH) not in sys.path:
    sys.path.insert(0, str(SOURCE_PATH))

from ccld_complaints.connectors.arcgis_ccl_facilities.live_query import (  # noqa: E402
    capture_live_arcgis_query_snapshot,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Capture the fixed-policy Issue #518 ArcGIS query observation under the "
            "repository's ignored evidence root."
        )
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=1000,
        help="Governed resultRecordCount from 1 through 1000 (default: 1000).",
    )
    arguments = parser.parse_args()
    capture = capture_live_arcgis_query_snapshot(
        REPOSITORY_ROOT,
        page_size=arguments.page_size,
    )
    print(
        json.dumps(
            {
                "evidence_directory": capture.evidence_directory.relative_to(REPOSITORY_ROOT)
                .as_posix(),
                "manifest": capture.manifest_path.name,
                "snapshot_id": capture.snapshot_id,
                "row_count": capture.row_count,
                "unique_object_id_count": capture.unique_object_id_count,
                "unique_facility_number_count": capture.unique_facility_number_count,
                "duplicate_facility_number_count": capture.duplicate_facility_number_count,
                "nonempty_page_count": capture.nonempty_page_count,
                "terminal_offset": capture.terminal_offset,
                "raw_response_set_sha256": capture.raw_response_set_sha256,
                "normalized_content_sha256": capture.normalized_content_sha256,
                "schema_fingerprint": capture.schema_fingerprint,
                "domain_fingerprint": capture.domain_fingerprint,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
