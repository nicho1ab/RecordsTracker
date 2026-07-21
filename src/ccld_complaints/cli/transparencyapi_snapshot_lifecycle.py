from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO, cast

from sqlalchemy import func, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import SQLAlchemyError

from ccld_complaints.connectors.ccld_transparency_api.connector import (
    TransparencyApiConnectorError,
)
from ccld_complaints.connectors.ccld_transparency_api.contract import SOURCE_FAMILY_ID
from ccld_complaints.connectors.ccld_transparency_api.lifecycle import (
    TransparencySnapshotInspection,
    accept_transparencyapi_snapshot,
    inspect_transparencyapi_package,
    promote_transparencyapi_snapshot,
    rollback_transparencyapi_snapshot,
    stage_transparencyapi_snapshot,
    transparency_rows,
    validate_transparencyapi_snapshot,
)
from ccld_complaints.hosted_app.facility_identity_projection import (
    PUBLIC_FACILITY_FIELDS,
    FacilityIdentityProjection,
    FacilityProjectionField,
    FacilityValueState,
    _candidate_from_transparency_row,
    project_facility_identity,
)
from ccld_complaints.hosted_app.persistence import (
    HostedDatabaseConfigError,
    load_hosted_database_config,
)
from ccld_complaints.hosted_app.reviewer_created_state import (
    hosted_reviewer_created_state,
)
from ccld_complaints.hosted_app.source_snapshot_lifecycle import (
    OfflineSnapshotLifecycleError,
    source_snapshot_pointers,
    source_snapshots,
)
from ccld_complaints.source_to_screen_audit import _runtime_engine

NONE_SENTINEL = "none"
APPROVED_IDENTITY_CHECKS: tuple[tuple[str, str], ...] = (
    ("015600412", "R.E.F.U.G.E."),
    ("015600744", "R.E.F.U.G.E.II"),
    ("015650058", "R.E.F.U.G.E.III, THE"),
)


class OperatorCliError(ValueError):
    def __init__(self, reason_category: str) -> None:
        super().__init__(reason_category)
        self.reason_category = reason_category


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Operate the governed CCLD TransparencyAPI snapshot lifecycle.",
        epilog=(
            "Examples: python -m ccld_complaints.cli.transparencyapi_snapshot_lifecycle "
            "inspect-package <package-dir>/manifest.json; "
            "python -m ccld_complaints.cli.transparencyapi_snapshot_lifecycle "
            "promote <snapshot-id> --expected-active none --expected-prior none"
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser(
        "inspect-package", help="Inspect a preserved package without database access."
    )
    inspect_parser.add_argument("manifest", type=Path)

    stage_parser = subparsers.add_parser(
        "stage", help="Stage one immutable candidate in a database transaction."
    )
    stage_parser.add_argument("manifest", type=Path)

    validate_parser = subparsers.add_parser(
        "validate", help="Validate one staged candidate in a database transaction."
    )
    validate_parser.add_argument("snapshot_id")
    _add_timestamp_argument(validate_parser)

    accept_parser = subparsers.add_parser(
        "accept", help="Accept one validated snapshot in a database transaction."
    )
    accept_parser.add_argument("snapshot_id")
    _add_timestamp_argument(accept_parser)

    promote_parser = subparsers.add_parser(
        "promote", help="Guard and promote one accepted snapshot atomically."
    )
    promote_parser.add_argument("snapshot_id")
    _add_pointer_guards(promote_parser)
    _add_timestamp_argument(promote_parser)

    rollback_parser = subparsers.add_parser(
        "rollback", help="Guard and swap the active and prior accepted pointers atomically."
    )
    _add_pointer_guards(rollback_parser)
    _add_timestamp_argument(rollback_parser)

    status_parser = subparsers.add_parser(
        "status", help="Read aggregate lifecycle status for the TransparencyAPI family."
    )
    status_parser.add_argument(
        "--limit",
        type=_bounded_status_limit,
        default=100,
        help="Maximum recent snapshot rows to return (1-500; default 100).",
    )

    dry_run_parser = subparsers.add_parser(
        "dry-run", help="Reconcile a package without staging or changing any database row."
    )
    dry_run_parser.add_argument("manifest", type=Path)
    return parser


def _add_timestamp_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--at",
        help="Optional timezone-aware UTC timestamp; generated in UTC when omitted.",
    )


def _add_pointer_guards(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--expected-active",
        required=True,
        help="Exact active snapshot ID, or 'none' when no active pointer is expected.",
    )
    parser.add_argument(
        "--expected-prior",
        required=True,
        help="Exact prior accepted snapshot ID, or 'none' when none is expected.",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = cast(str, args.command)
    try:
        if command == "inspect-package":
            payload = _inspection_payload(inspect_transparencyapi_package(args.manifest))
            _write_json(payload)
            return 0 if payload["rejection_count"] == 0 else 2

        engine = _configured_engine()
        try:
            payload, exit_code = _run_database_command(engine, args)
        finally:
            engine.dispose()
    except (
        HostedDatabaseConfigError,
        OfflineSnapshotLifecycleError,
        OperatorCliError,
        SQLAlchemyError,
        TransparencyApiConnectorError,
        OSError,
        ValueError,
    ) as error:
        _write_failure(command, error)
        return 2
    _write_json(payload)
    return exit_code


def _configured_engine() -> Engine:
    config = load_hosted_database_config(require_url=True)
    if config.database_url is None:
        raise HostedDatabaseConfigError("database configuration is unavailable")
    return _runtime_engine({config.database_url_env: config.database_url})


def _run_database_command(
    engine: Engine, args: argparse.Namespace
) -> tuple[Mapping[str, Any], int]:
    command = cast(str, args.command)
    if command in {"status", "dry-run"}:
        with engine.connect() as connection:
            if command == "status":
                return _status_payload(connection, limit=args.limit), 0
            return _dry_run_payload(connection, args.manifest), 0

    with engine.begin() as connection:
        if command == "stage":
            inspection = stage_transparencyapi_snapshot(connection, args.manifest)
            payload = _inspection_payload(inspection)
            return {
                **payload,
                "lifecycle_state": _snapshot_state(connection, inspection.snapshot_id),
            }, 0
        if command == "validate":
            state = validate_transparencyapi_snapshot(
                connection,
                args.snapshot_id,
                validated_at=_utc_timestamp(args.at),
            )
            payload = _snapshot_payload(connection, args.snapshot_id)
            return payload, 0 if state == "validated" else 2
        if command == "accept":
            accept_transparencyapi_snapshot(
                connection,
                args.snapshot_id,
                accepted_at=_utc_timestamp(args.at),
            )
            return _snapshot_payload(connection, args.snapshot_id), 0
        if command == "promote":
            _guard_pointer(
                connection,
                expected_active=args.expected_active,
                expected_prior=args.expected_prior,
                lock=True,
            )
            promoted_at = _utc_timestamp(args.at)
            pointer = promote_transparencyapi_snapshot(
                connection,
                args.snapshot_id,
                promoted_at=promoted_at,
            )
            return {
                "status": "passed",
                "source_family_id": pointer.source_family_id,
                "active_snapshot_id": pointer.active_snapshot_id,
                "prior_accepted_snapshot_id": pointer.prior_accepted_snapshot_id,
                "lifecycle_state": _snapshot_state(connection, pointer.active_snapshot_id),
                "updated_at": promoted_at,
            }, 0
        if command == "rollback":
            _guard_pointer(
                connection,
                expected_active=args.expected_active,
                expected_prior=args.expected_prior,
                lock=True,
            )
            rolled_back_at = _utc_timestamp(args.at)
            pointer = rollback_transparencyapi_snapshot(
                connection,
                expected_active_snapshot_id=args.expected_active,
                rolled_back_at=rolled_back_at,
            )
            return {
                "status": "passed",
                "source_family_id": pointer.source_family_id,
                "active_snapshot_id": pointer.active_snapshot_id,
                "prior_accepted_snapshot_id": pointer.prior_accepted_snapshot_id,
                "updated_at": rolled_back_at,
            }, 0
    raise OperatorCliError("unsupported_command")


def _inspection_payload(inspection: TransparencySnapshotInspection) -> Mapping[str, Any]:
    report = inspection.validation_report
    eligible_rows = _eligible_rows(inspection.rows)
    quarantine_categories = Counter(
        str(row.get("category") or "uncategorized") for row in inspection.quarantines
    )
    warnings = cast(Sequence[object], report.get("warnings", ()))
    rejections = cast(Sequence[object], report.get("rejection_reasons", ()))
    return {
        "status": "passed" if not rejections else "rejected",
        "source_family_id": SOURCE_FAMILY_ID,
        "snapshot_id": inspection.snapshot_id,
        "manifest_sha256": inspection.manifest_sha256,
        "raw_response_set_sha256": inspection.raw_response_set_sha256,
        "normalized_content_sha256": inspection.normalized_content_sha256,
        "schema_fingerprint": inspection.schema_fingerprint,
        "taxonomy_fingerprint": inspection.taxonomy_fingerprint,
        "recorded_at": inspection.recorded_at,
        "artifact_count": len(inspection.artifacts),
        "row_count": int(report["row_count"]),
        "stored_row_count": int(report["stored_row_count"]),
        "eligible_row_count": len(eligible_rows),
        "quarantine_count": len(inspection.quarantines),
        "quarantine_category_counts": dict(sorted(quarantine_categories.items())),
        "disappearance_count": len(inspection.disappearances),
        "warning_count": len(warnings),
        "warning_category_counts": _category_counts(warnings, _warning_category),
        "rejection_count": len(rejections),
        "rejection_category_counts": _category_counts(rejections, _rejection_category),
        "rejection_reasons": [],
    }


def _snapshot_payload(connection: Connection, snapshot_id: str) -> Mapping[str, Any]:
    row = _snapshot_record(connection, snapshot_id)
    return {
        "status": "passed" if row["lifecycle_state"] != "rejected" else "rejected",
        "source_family_id": SOURCE_FAMILY_ID,
        "snapshot_id": snapshot_id,
        "lifecycle_state": str(row["lifecycle_state"]),
        "row_count": int(row["row_count"]),
        "stored_row_count": int(row["stored_row_count"]),
        "warning_count": int(row["warning_count"]),
        "rejection_count": int(row["rejection_reason_count"]),
        "validated_at": row["validated_at"],
        "rejected_at": row["rejected_at"],
        "accepted_at": row["accepted_at"],
    }


def _status_payload(connection: Connection, *, limit: int) -> Mapping[str, Any]:
    pointer = _pointer_record(connection, lock=False)
    snapshot_count = int(
        connection.scalar(
            select(func.count())
            .select_from(source_snapshots)
            .where(source_snapshots.c.source_family_id == SOURCE_FAMILY_ID)
        )
        or 0
    )
    snapshots = tuple(
        dict(row)
        for row in connection.execute(
            select(source_snapshots)
            .where(source_snapshots.c.source_family_id == SOURCE_FAMILY_ID)
            .order_by(
                source_snapshots.c.recorded_at.desc(),
                source_snapshots.c.snapshot_id.desc(),
            )
            .limit(limit)
        ).mappings()
    )
    rows = [
        {
            "snapshot_id": str(row["snapshot_id"]),
            "lifecycle_state": str(row["lifecycle_state"]),
            "manifest_sha256": str(row["manifest_sha256"]),
            "raw_response_set_sha256": str(row["raw_payload_sha256"]),
            "normalized_content_sha256": str(row["normalized_content_sha256"]),
            "schema_fingerprint": str(row["schema_fingerprint"]),
            "taxonomy_fingerprint": str(row["domain_fingerprint"]),
            "row_count": int(row["row_count"]),
            "stored_row_count": int(row["stored_row_count"]),
            "warning_count": int(row["warning_count"]),
            "rejection_count": int(row["rejection_reason_count"]),
            "recorded_at": str(row["recorded_at"]),
            "validated_at": row["validated_at"],
            "rejected_at": row["rejected_at"],
            "accepted_at": row["accepted_at"],
        }
        for row in snapshots
    ]
    return {
        "status": "passed",
        "source_family_id": SOURCE_FAMILY_ID,
        "snapshot_count": snapshot_count,
        "returned_snapshot_count": len(rows),
        "active_snapshot_id": _pointer_value(pointer, "active_snapshot_id"),
        "prior_accepted_snapshot_id": _pointer_value(pointer, "prior_accepted_snapshot_id"),
        "pointer_updated_at": _pointer_value(pointer, "updated_at"),
        "snapshots": rows,
    }


def _dry_run_payload(connection: Connection, manifest: Path) -> Mapping[str, Any]:
    pointer = _pointer_record(connection, lock=False)
    active_snapshot_id = _pointer_value(pointer, "active_snapshot_id")
    prior_rows: tuple[Mapping[str, Any], ...] = ()
    if active_snapshot_id is not None:
        prior_rows = tuple(
            dict(row)
            for row in connection.execute(
                select(transparency_rows).where(
                    transparency_rows.c.snapshot_id == active_snapshot_id
                )
            ).mappings()
        )
    inspection = inspect_transparencyapi_package(
        manifest,
        prior_rows=prior_rows,
        prior_snapshot_id=active_snapshot_id,
    )
    base = _inspection_payload(inspection)
    eligible_rows = _eligible_rows(inspection.rows)
    projections = _candidate_projections(inspection, eligible_rows)
    reviewer_count = _reviewer_state_count(connection)
    unresolved_code_count = sum(
        projection.field(FacilityProjectionField.FACILITY_TYPE).state
        is FacilityValueState.UNRESOLVED_RAW_CODE
        for projection in projections.values()
    )
    source_family_conflict_count = sum(
        projection.field(field).conflict
        for projection in projections.values()
        for field in PUBLIC_FACILITY_FIELDS
    )
    return {
        **base,
        "dry_run": True,
        "database_mutations_performed": False,
        "source_family_conflict_count": source_family_conflict_count,
        "duplicate_facility_number_count": int(
            inspection.validation_report["duplicate_facility_number_count"]
        ),
        "unresolved_code_count": unresolved_code_count,
        "proposed_lifecycle_transition": (
            "candidate_to_validated" if base["rejection_count"] == 0 else "candidate_to_rejected"
        ),
        "active_snapshot_id": active_snapshot_id,
        "prior_accepted_snapshot_id": _pointer_value(pointer, "prior_accepted_snapshot_id"),
        "reviewer_created_state_count_before": reviewer_count,
        "reviewer_created_state_count_projected_after": reviewer_count,
        "approved_identity_checks": _approved_identity_checks(projections),
    }


def _candidate_projections(
    inspection: TransparencySnapshotInspection,
    rows: Sequence[Mapping[str, Any]],
) -> Mapping[str, FacilityIdentityProjection]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        facility_id = str(row["facility_number"])
        grouped.setdefault(facility_id, []).append(row)
    return {
        facility_id: project_facility_identity(
            facility_id,
            tuple(
                _candidate_from_transparency_row(
                    {**row, "snapshot_id": inspection.snapshot_id},
                    observed_at=inspection.recorded_at,
                )
                for row in grouped[facility_id]
            ),
        )
        for facility_id in sorted(grouped)
    }


def _approved_identity_checks(
    projections: Mapping[str, FacilityIdentityProjection],
) -> list[Mapping[str, Any]]:
    output: list[Mapping[str, Any]] = []
    for facility_id, expected_name in APPROVED_IDENTITY_CHECKS:
        projection = projections.get(facility_id)
        name = (
            projection.field(FacilityProjectionField.FACILITY_NAME)
            if projection is not None
            else None
        )
        output.append(
            {
                "facility_id": facility_id,
                "expected_name": expected_name,
                "exists": projection is not None,
                "exact_text_identity": name is not None and name.display_value == expected_name,
                "leading_zero_preserved": (
                    projection is not None and projection.public_facility_id == facility_id
                ),
            }
        )
    return output


def _eligible_rows(rows: Sequence[Mapping[str, Any]]) -> tuple[Mapping[str, Any], ...]:
    return tuple(
        row for row in rows if not row.get("is_quarantined") and row.get("facility_number")
    )


def _reviewer_state_count(connection: Connection) -> int:
    if not sa_inspect(connection).has_table(hosted_reviewer_created_state.name):
        return 0
    return int(
        connection.scalar(select(func.count()).select_from(hosted_reviewer_created_state)) or 0
    )


def _guard_pointer(
    connection: Connection,
    *,
    expected_active: str,
    expected_prior: str,
    lock: bool,
) -> None:
    pointer = _pointer_record(connection, lock=lock)
    actual_active = _pointer_value(pointer, "active_snapshot_id")
    actual_prior = _pointer_value(pointer, "prior_accepted_snapshot_id")
    if _expected_pointer_value(expected_active) != actual_active:
        raise OperatorCliError("expected_active_guard_failed")
    if _expected_pointer_value(expected_prior) != actual_prior:
        raise OperatorCliError("expected_prior_guard_failed")


def _pointer_record(connection: Connection, *, lock: bool) -> Mapping[str, Any] | None:
    statement = select(source_snapshot_pointers).where(
        source_snapshot_pointers.c.source_family_id == SOURCE_FAMILY_ID
    )
    if lock:
        statement = statement.with_for_update()
    row = connection.execute(statement).mappings().one_or_none()
    return dict(row) if row is not None else None


def _pointer_value(pointer: Mapping[str, Any] | None, field: str) -> str | None:
    if pointer is None or pointer.get(field) is None:
        return None
    return str(pointer[field])


def _expected_pointer_value(value: str) -> str | None:
    clean = value.strip()
    if clean == NONE_SENTINEL:
        return None
    if not clean:
        raise OperatorCliError("blank_pointer_guard")
    return clean


def _snapshot_record(connection: Connection, snapshot_id: str) -> Mapping[str, Any]:
    row = (
        connection.execute(
            select(source_snapshots).where(
                source_snapshots.c.snapshot_id == snapshot_id,
                source_snapshots.c.source_family_id == SOURCE_FAMILY_ID,
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise OperatorCliError("transparencyapi_snapshot_not_found")
    return dict(row)


def _snapshot_state(connection: Connection, snapshot_id: str) -> str:
    return str(_snapshot_record(connection, snapshot_id)["lifecycle_state"])


def _utc_timestamp(value: str | None) -> str:
    if value is None:
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise OperatorCliError("timestamp_must_be_utc") from error
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise OperatorCliError("timestamp_must_be_utc")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _bounded_status_limit(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("status limit must be an integer") from error
    if not 1 <= parsed <= 500:
        raise argparse.ArgumentTypeError("status limit must be between 1 and 500")
    return parsed


def _category_counts(
    values: Sequence[object], classifier: Callable[[str], str]
) -> Mapping[str, int]:
    counts = Counter(classifier(str(value)) for value in values)
    return dict(sorted(counts.items()))


def _warning_category(value: str) -> str:
    normalized = value.casefold()
    if "disappeared" in normalized:
        return "source_disappearance"
    if "taxonomy" in normalized:
        return "taxonomy_warning"
    if "date" in normalized:
        return "source_date_warning"
    if "status" in normalized or "closed" in normalized:
        return "source_status_warning"
    return "source_warning"


def _rejection_category(value: str) -> str:
    normalized = value.casefold()
    if "manifest" in normalized:
        return "manifest_invalid"
    if "complete source family" in normalized or "group/" in normalized or "cacounty" in normalized:
        return "source_family_incomplete"
    if "sha-256" in normalized or "fingerprint" in normalized or "byte count" in normalized:
        return "immutable_evidence_mismatch"
    if "http" in normalized or "media type" in normalized or "redirect" in normalized:
        return "transport_evidence_invalid"
    if "artifact" in normalized or "bulk export" in normalized:
        return "artifact_invalid"
    return "package_validation_rejection"


def _failure_category(error: Exception) -> str:
    if isinstance(error, OperatorCliError):
        return error.reason_category
    if isinstance(error, HostedDatabaseConfigError):
        return "database_configuration_unavailable"
    if isinstance(error, OfflineSnapshotLifecycleError):
        return "lifecycle_guard_failed"
    if isinstance(error, TransparencyApiConnectorError):
        return "immutable_evidence_or_package_invalid"
    if isinstance(error, SQLAlchemyError):
        return "database_operation_failed"
    if isinstance(error, OSError):
        return "package_unavailable"
    return "invalid_argument"


def _write_failure(command: str, error: Exception) -> None:
    _write_json(
        {
            "status": "failed",
            "operation": command,
            "reason_category": _failure_category(error),
        },
        stream=sys.stderr,
    )


def _write_json(payload: Mapping[str, Any], *, stream: TextIO | None = None) -> None:
    output = sys.stdout if stream is None else stream
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")), file=output)


if __name__ == "__main__":
    raise SystemExit(main())
