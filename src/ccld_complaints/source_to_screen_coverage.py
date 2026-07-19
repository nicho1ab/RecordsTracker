"""Stable read boundary for producer-owned source-to-screen coverage packages.

Hosted consumers use this module instead of importing the Issue 453 audit
implementation directly.  The producer remains responsible for schema,
canonical serialization, hashes, deterministic identities, reconciliation,
and closed enums; this boundary exposes only the validated package artifacts.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from ccld_complaints.source_to_screen_audit import (
    COVERAGE_AGGREGATE_CSV_FIELDNAMES,
    COVERAGE_CHANGE_OUTCOMES,
    COVERAGE_CONTRACT_VERSION,
    COVERAGE_HASH_VALIDATION_STATES,
    COVERAGE_IMPORT_STATES,
    COVERAGE_JOB_STATES,
    COVERAGE_MINIMUM_CONSUMER_VERSION,
    COVERAGE_OPERATIONAL_FAILURE_CATEGORIES,
    COVERAGE_PRESERVED_ARTIFACT_STATES,
    COVERAGE_PROCESSING_OUTCOMES,
    COVERAGE_PRODUCER_SCHEMA_ID,
    COVERAGE_REFRESH_STATES,
    COVERAGE_RETRIEVAL_STATES,
    COVERAGE_SOURCE_LAYOUT_CLASSIFICATIONS,
    COVERAGE_STAGES,
    COVERAGE_TERMINAL_CLASSIFICATIONS,
    CoverageContractError,
    validate_coverage_package,
)

__all__ = (
    "COVERAGE_AGGREGATE_CSV_FIELDNAMES",
    "COVERAGE_ARTIFACT_MEDIA_TYPES",
    "COVERAGE_CHANGE_OUTCOMES",
    "COVERAGE_CONTRACT_VERSION",
    "COVERAGE_HASH_VALIDATION_STATES",
    "COVERAGE_IMPORT_STATES",
    "COVERAGE_JOB_STATES",
    "COVERAGE_MINIMUM_CONSUMER_VERSION",
    "COVERAGE_OPERATIONAL_FAILURE_CATEGORIES",
    "COVERAGE_PRESERVED_ARTIFACT_STATES",
    "COVERAGE_PROCESSING_OUTCOMES",
    "COVERAGE_PRODUCER_SCHEMA_ID",
    "COVERAGE_REFRESH_STATES",
    "COVERAGE_RETRIEVAL_STATES",
    "COVERAGE_SOURCE_LAYOUT_CLASSIFICATIONS",
    "COVERAGE_STAGES",
    "COVERAGE_TERMINAL_CLASSIFICATIONS",
    "CoverageReadError",
    "ValidatedCoveragePackage",
    "load_validated_coverage_package",
)

CoverageReadState = Literal[
    "available",
    "partial",
    "unavailable",
    "version_mismatch",
    "hash_failed",
    "reconciliation_failed",
]

COVERAGE_ARTIFACT_MEDIA_TYPES: Mapping[str, str] = {
    "coverage-report.json": "application/json",
    "operator-facility-index.jsonl": "application/x-ndjson",
    "operator-job-index.jsonl": "application/x-ndjson",
    "aggregate-coverage.csv": "text/csv",
}
COVERAGE_AVAILABLE_STATES = frozenset({"available", "partial"})


class CoverageReadError(ValueError):
    """Fail-closed, presentation-safe producer package validation error."""

    def __init__(self, state: CoverageReadState, message: str) -> None:
        super().__init__(message)
        self.state = state


@dataclass(frozen=True)
class ValidatedCoveragePackage:
    package_dir: Path
    manifest: Mapping[str, Any]
    report: Mapping[str, Any]
    facility_rows: tuple[Mapping[str, Any], ...]
    job_rows: tuple[Mapping[str, Any], ...]
    aggregate_csv: bytes
    state: Literal["available", "partial"]
    unavailable_dimensions: tuple[str, ...]


def load_validated_coverage_package(package_dir: Path) -> ValidatedCoveragePackage:
    """Load only artifacts that pass the producer's complete v1 contract checks."""

    if not package_dir.is_dir() or not (package_dir / "manifest.json").is_file():
        raise CoverageReadError(
            "unavailable",
            "Coverage report unavailable. The configured package could not be opened.",
        )
    try:
        validated_manifest = validate_coverage_package(package_dir)
    except CoverageContractError as error:
        raise _safe_read_error(error) from error

    manifest = _json_object(package_dir / "manifest.json")
    if manifest != validated_manifest:
        raise CoverageReadError(
            "unavailable", "Coverage manifest changed during validation."
        )
    _validate_artifact_media_types(manifest)
    report_bytes = _artifact_bytes(
        package_dir, manifest, "coverage-report.json", required=True
    )
    aggregate_bytes = _artifact_bytes(
        package_dir, manifest, "aggregate-coverage.csv", required=True
    )
    assert report_bytes is not None
    assert aggregate_bytes is not None
    report = _json_object_bytes(report_bytes)
    facility_rows = _jsonl_rows(
        _artifact_bytes(
            package_dir,
            manifest,
            "operator-facility-index.jsonl",
            required=False,
        )
    )
    job_rows = _jsonl_rows(
        _artifact_bytes(
            package_dir,
            manifest,
            "operator-job-index.jsonl",
            required=False,
        )
    )
    aggregate_csv = aggregate_bytes
    _validate_aggregate_header(aggregate_csv)
    _validate_consumer_invariants(manifest, report, facility_rows, job_rows)

    state = cast(str, report["package_availability"])
    if state not in COVERAGE_AVAILABLE_STATES:
        raise CoverageReadError("unavailable", "Coverage package failed closed validation.")
    unavailable = report.get("unavailable_dimensions", [])
    if not isinstance(unavailable, list) or not all(
        isinstance(value, str) for value in unavailable
    ):
        raise CoverageReadError(
            "unavailable", "Coverage unavailable dimensions are invalid."
        )
    return ValidatedCoveragePackage(
        package_dir=package_dir,
        manifest=manifest,
        report=report,
        facility_rows=facility_rows,
        job_rows=job_rows,
        aggregate_csv=aggregate_csv,
        state=cast(Literal["available", "partial"], state),
        unavailable_dimensions=tuple(unavailable),
    )


def _safe_read_error(error: CoverageContractError) -> CoverageReadError:
    message = str(error).casefold()
    if "version" in message:
        return CoverageReadError(
            "version_mismatch", "Coverage report version is not supported."
        )
    if "hash" in message or "byte count" in message:
        return CoverageReadError(
            "hash_failed", "Coverage report hash validation failed."
        )
    if "reconciliation" in message:
        return CoverageReadError(
            "reconciliation_failed", "Coverage report reconciliation failed."
        )
    return CoverageReadError(
        "unavailable", "Coverage report unavailable. Contract validation failed."
    )


def _json_object(path: Path) -> Mapping[str, Any]:
    try:
        return _json_object_bytes(path.read_bytes())
    except OSError as error:
        raise CoverageReadError(
            "unavailable", "A validated coverage artifact became unavailable."
        ) from error


def _json_object_bytes(value: bytes) -> Mapping[str, Any]:
    try:
        parsed = json.loads(value.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CoverageReadError(
            "unavailable", "A validated coverage artifact became unavailable."
        ) from error
    if not isinstance(parsed, dict):
        raise CoverageReadError("unavailable", "A coverage artifact is invalid.")
    return cast(Mapping[str, Any], parsed)


def _artifact_entries(manifest: Mapping[str, Any]) -> Mapping[str, Mapping[str, Any]]:
    entries = manifest.get("artifacts")
    if not isinstance(entries, list):
        raise CoverageReadError("unavailable", "Coverage artifact metadata is invalid.")
    mapped: dict[str, Mapping[str, Any]] = {}
    for value in entries:
        if not isinstance(value, dict) or not isinstance(value.get("name"), str):
            raise CoverageReadError(
                "unavailable", "Coverage artifact metadata is invalid."
            )
        mapped[cast(str, value["name"])] = cast(Mapping[str, Any], value)
    return mapped


def _validate_artifact_media_types(manifest: Mapping[str, Any]) -> None:
    entries = _artifact_entries(manifest)
    if set(entries) != set(COVERAGE_ARTIFACT_MEDIA_TYPES):
        raise CoverageReadError("unavailable", "Coverage artifact set is invalid.")
    for name, media_type in COVERAGE_ARTIFACT_MEDIA_TYPES.items():
        if entries[name].get("media_type") != media_type:
            raise CoverageReadError(
                "unavailable", "Coverage artifact media type is invalid."
            )


def _artifact_bytes(
    package_dir: Path,
    manifest: Mapping[str, Any],
    name: str,
    *,
    required: bool,
) -> bytes | None:
    entry = _artifact_entries(manifest)[name]
    if entry.get("availability") == "unavailable":
        if required:
            raise CoverageReadError(
                "unavailable", "A required coverage artifact is unavailable."
            )
        return None
    try:
        value = (package_dir / name).read_bytes()
    except OSError as error:
        raise CoverageReadError(
            "unavailable", "A validated coverage artifact became unavailable."
        ) from error
    if len(value) != entry.get("byte_count"):
        raise CoverageReadError(
            "hash_failed", "Coverage artifact byte count failed validation."
        )
    if hashlib.sha256(value).hexdigest() != entry.get("sha256"):
        raise CoverageReadError(
            "hash_failed", "Coverage report hash validation failed."
        )
    return value


def _jsonl_rows(value: bytes | None) -> tuple[Mapping[str, Any], ...]:
    if value is None:
        return ()
    try:
        lines = value.decode("utf-8").splitlines()
        values = tuple(json.loads(line) for line in lines)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CoverageReadError(
            "unavailable", "A validated coverage index became unavailable."
        ) from error
    if not all(isinstance(value, dict) for value in values):
        raise CoverageReadError("unavailable", "A coverage index row is invalid.")
    return cast(tuple[Mapping[str, Any], ...], values)


def _validate_aggregate_header(value: bytes) -> None:
    try:
        reader = csv.DictReader(io.StringIO(value.decode("utf-8"), newline=""))
        tuple(reader)
    except (UnicodeDecodeError, csv.Error) as error:
        raise CoverageReadError("unavailable", "Aggregate CSV is invalid.") from error
    if tuple(reader.fieldnames or ()) != COVERAGE_AGGREGATE_CSV_FIELDNAMES:
        raise CoverageReadError("unavailable", "Aggregate CSV header is invalid.")


def _validate_consumer_invariants(
    manifest: Mapping[str, Any],
    report: Mapping[str, Any],
    facility_rows: tuple[Mapping[str, Any], ...],
    job_rows: tuple[Mapping[str, Any], ...],
) -> None:
    report_id = manifest.get("report_id")
    snapshots = manifest.get("source_snapshots")
    if not isinstance(report_id, str) or not isinstance(snapshots, list):
        raise CoverageReadError("unavailable", "Coverage package identity is invalid.")
    source_families = {
        item.get("source_snapshot_id"): item.get("source_family_id")
        for item in snapshots
        if isinstance(item, dict)
    }
    for row in facility_rows:
        layout = row.get("source_layout_classification")
        if layout not in COVERAGE_SOURCE_LAYOUT_CLASSIFICATIONS:
            raise CoverageReadError(
                "unavailable", "Coverage source layout classification is invalid."
            )
        source_family_id = source_families.get(row.get("source_snapshot_id"))
        facility_id = row.get("facility_id")
        if not isinstance(source_family_id, str) or not isinstance(facility_id, str):
            raise CoverageReadError("unavailable", "Coverage facility identity is invalid.")
        identity = json.dumps(
            {
                "facility_id": facility_id.strip().casefold(),
                "source_family_id": source_family_id,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        expected = f"facility-v1-{hashlib.sha256(identity).hexdigest()}"
        if row.get("facility_entry_id") != expected:
            raise CoverageReadError(
                "unavailable", "Coverage facility deterministic identity is invalid."
            )
    for row in (*facility_rows, *job_rows):
        if (
            row.get("contract_version") != COVERAGE_CONTRACT_VERSION
            or row.get("report_id") != report_id
        ):
            raise CoverageReadError("unavailable", "Coverage index identity is invalid.")
    if report.get("report_id") != report_id:
        raise CoverageReadError("unavailable", "Coverage report identity is invalid.")
