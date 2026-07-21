from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol, TextIO
from urllib.error import URLError

from ccld_complaints.cli.transparencyapi_snapshot_lifecycle import _inspection_payload
from ccld_complaints.connectors.ccld_transparency_api.connector import (
    SnapshotCapture,
    TransparencyApiConnector,
    TransparencyApiConnectorError,
)
from ccld_complaints.connectors.ccld_transparency_api.contract import EXPORT_IDS
from ccld_complaints.connectors.ccld_transparency_api.lifecycle import (
    TransparencySnapshotInspection,
    inspect_transparencyapi_package,
)


class CaptureCliError(ValueError):
    def __init__(self, reason_category: str) -> None:
        super().__init__(reason_category)
        self.reason_category = reason_category


class SnapshotCapturer(Protocol):
    def capture_snapshot(
        self, repository_root: Path, *, retrieved_at: str | None = None
    ) -> SnapshotCapture: ...


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture and locally inspect one governed CCLD TransparencyAPI package.",
        epilog=(
            "Example: python -m ccld_complaints.cli.transparencyapi_snapshot_capture "
            "capture --output-dir <repo-root>"
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    capture_parser = subparsers.add_parser(
        "capture",
        help="Capture the fixed seven-export and two-taxonomy source family.",
    )
    capture_parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help=(
            "RecordsTracker repository root; the timestamped package is written "
            "under its ignored data/raw directory."
        ),
    )
    return parser


def capture_package(
    output_dir: Path,
    *,
    connector: SnapshotCapturer | None = None,
    recorded_at: str | None = None,
) -> Mapping[str, Any]:
    """Capture the fixed source family and validate it without database access."""

    repository_root = _validated_repository_root(output_dir)
    capture = (connector or TransparencyApiConnector()).capture_snapshot(
        repository_root,
        retrieved_at=recorded_at,
    )
    inspection = inspect_transparencyapi_package(capture.manifest_path)
    inspection_payload = _inspection_payload(inspection)
    if not _is_exact_complete_source_family(capture, inspection):
        raise CaptureCliError("captured_source_family_incomplete")
    if int(inspection_payload["rejection_count"]) != 0:
        raise CaptureCliError("captured_package_rejected")
    package_directory = capture.evidence_directory.relative_to(repository_root).as_posix()
    return {
        "status": "passed",
        "package_directory": package_directory,
        "manifest_filename": capture.manifest_path.name,
        "snapshot_id": inspection.snapshot_id,
        "manifest_sha256": inspection.manifest_sha256,
        "raw_response_set_sha256": inspection.raw_response_set_sha256,
        "normalized_content_sha256": inspection.normalized_content_sha256,
        "schema_fingerprint": inspection.schema_fingerprint,
        "taxonomy_fingerprint": inspection.taxonomy_fingerprint,
        "artifact_count": len(inspection.artifacts),
        "export_count": sum(
            artifact.get("endpoint_kind") == "bulk_export"
            for artifact in inspection.artifacts
        ),
        "row_count": int(inspection_payload["row_count"]),
        "stored_row_count": int(inspection_payload["stored_row_count"]),
        "eligible_row_count": int(inspection_payload["eligible_row_count"]),
        "quarantine_count": int(inspection_payload["quarantine_count"]),
        "quarantine_category_counts": inspection_payload[
            "quarantine_category_counts"
        ],
        "warning_count": int(inspection_payload["warning_count"]),
        "rejection_count": int(inspection_payload["rejection_count"]),
        "recorded_at": inspection.recorded_at,
        "database_mutations_performed": False,
    }


def _validated_repository_root(output_dir: Path) -> Path:
    root = output_dir.resolve()
    required = (
        root / "pyproject.toml",
        root / ".gitignore",
        root / "src/ccld_complaints/connectors/ccld_transparency_api/connector.py",
        root / "data/raw/.gitkeep",
    )
    if not root.is_dir() or not all(path.is_file() for path in required):
        raise CaptureCliError("output_dir_must_be_repository_root")
    ignore_rules = {
        line.strip().lstrip("/")
        for line in (root / ".gitignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    if "data/raw/*" not in ignore_rules:
        raise CaptureCliError("governed_raw_output_is_not_ignored")
    return root


def _is_exact_complete_source_family(
    capture: SnapshotCapture,
    inspection: TransparencySnapshotInspection,
) -> bool:
    if len(capture.artifacts) != 9 or len(inspection.artifacts) != 9:
        return False
    export_counts = Counter(
        str(artifact.get("export_id"))
        for artifact in inspection.artifacts
        if artifact.get("endpoint_kind") == "bulk_export"
    )
    endpoint_counts = Counter(
        str(artifact.get("endpoint_kind")) for artifact in inspection.artifacts
    )
    return export_counts == Counter(EXPORT_IDS) and endpoint_counts == Counter(
        {
            "bulk_export": 7,
            "facility_type_taxonomy": 1,
            "county_taxonomy": 1,
        }
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = capture_package(args.output_dir)
    except Exception as error:  # Fail closed at the operator boundary.
        _write_json(
            {
                "status": "failed",
                "operation": "capture",
                "reason_category": _failure_category(error),
            },
            stream=sys.stderr,
        )
        return 2
    _write_json(payload)
    return 0


def _failure_category(error: Exception) -> str:
    if isinstance(error, CaptureCliError):
        return error.reason_category
    if isinstance(error, URLError):
        return "source_retrieval_failed"
    if isinstance(error, FileExistsError):
        return "output_collision"
    if isinstance(error, TransparencyApiConnectorError):
        return "governed_capture_failed"
    if isinstance(error, OSError):
        return "package_write_failed"
    return "capture_failed"


def _write_json(payload: Mapping[str, Any], *, stream: TextIO | None = None) -> None:
    output = sys.stdout if stream is None else stream
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")), file=output)


if __name__ == "__main__":
    raise SystemExit(main())
