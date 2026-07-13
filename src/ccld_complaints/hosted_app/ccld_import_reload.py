from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy.engine import Connection

from ccld_complaints.hosted_app.auth import HostedAccessScope
from ccld_complaints.hosted_app.ccld_hosted_artifact_builder import (
    DEFAULT_GENERATED_CCLD_HOSTED_ARTIFACT,
)
from ccld_complaints.hosted_app.seeded_import import (
    SeededSourceDerivedRecord,
    flatten_seeded_corpus_records,
    import_seeded_corpus_artifact,
    load_seeded_corpus_artifact,
)
from ccld_complaints.hosted_app.source_derived_reads import list_source_derived_records

DEFAULT_LOCAL_VALIDATED_CCLD_ARTIFACT = Path(
    "tests/fixtures/hosted_seeded_corpus/validated_seeded_corpus.json"
)
DEFAULT_LOCAL_VALIDATED_CCLD_ARTIFACT_PATHS = (
    DEFAULT_GENERATED_CCLD_HOSTED_ARTIFACT,
)
_FACILITY_NUMBER_RE = re.compile(r"^\d+$")
_CCLD_CONNECTOR_NAME = "ccld_facility_reports"
_DATE_FIELDS = (
    "complaint_received_date",
    "visit_date",
    "report_date",
    "date_signed",
    "retrieved_at",
)


@dataclass(frozen=True)
class CcldImportReloadRequest:
    facility_number: str
    start_date: str | None = None
    end_date: str | None = None


@dataclass(frozen=True)
class CcldImportReloadContext:
    connection: Connection
    scope: HostedAccessScope
    artifact_paths: tuple[Path, ...]


@dataclass(frozen=True)
class CcldImportReloadResult:
    facility_number: str
    start_date: str | None
    end_date: str | None
    import_executed: bool
    available_before_count: int
    available_after_count: int
    imported_source_record_count: int
    refreshed_source_record_count: int
    skipped_duplicate_source_record_count: int
    skipped_non_matching_source_record_count: int
    source_artifact_identities: tuple[str, ...]
    deferred_reasons: tuple[str, ...]


def ccld_import_reload_context_for_connection(
    connection: Connection,
    *,
    scope: HostedAccessScope,
    artifact_paths: tuple[Path, ...] | None = None,
    allow_committed_fixture: bool = False,
) -> CcldImportReloadContext:
    return CcldImportReloadContext(
        connection=connection,
        scope=scope,
        artifact_paths=(
            artifact_paths
            if artifact_paths is not None
            else _default_local_validated_ccld_artifact_paths(
                allow_committed_fixture=allow_committed_fixture
            )
        ),
    )


def _default_local_validated_ccld_artifact_paths(
    *,
    allow_committed_fixture: bool = False,
) -> tuple[Path, ...]:
    generated_path = _resolve_artifact_path(DEFAULT_GENERATED_CCLD_HOSTED_ARTIFACT)
    if generated_path.exists():
        return (DEFAULT_GENERATED_CCLD_HOSTED_ARTIFACT,)
    if allow_committed_fixture:
        return (DEFAULT_LOCAL_VALIDATED_CCLD_ARTIFACT,)
    return ()


def import_reload_validated_ccld_records(
    context: CcldImportReloadContext,
    request: CcldImportReloadRequest,
) -> CcldImportReloadResult:
    _validate_request(request)
    before_records = _scoped_records(context)
    before_matching_count = _matching_read_record_count(before_records, request)
    before_keys = {record.source_record_key for record in before_records}

    imported_count = 0
    refreshed_count = 0
    skipped_non_matching_count = 0
    source_artifact_identities: list[str] = []
    deferred_reasons: list[str] = []
    import_executed = False

    for artifact_path in context.artifact_paths:
        artifact = load_seeded_corpus_artifact(_resolve_artifact_path(artifact_path))
        flattened = flatten_seeded_corpus_records(artifact)
        ccld_records = [record for record in flattened if _is_ccld_record(record)]
        non_ccld_count = len(flattened) - len(ccld_records)
        if non_ccld_count:
            deferred_reasons.append(
                "Local validated artifact contained non-CCLD source-derived rows."
            )
            skipped_non_matching_count += len(flattened)
            continue
        if artifact.import_batch_id != context.scope.scope_id:
            deferred_reasons.append(
                "Local validated artifact import batch is outside the authorized "
                "local/test seeded corpus scope."
            )
            skipped_non_matching_count += len(flattened)
            continue

        matching_records = _matching_artifact_records(ccld_records, request)
        skipped_non_matching_count += len(ccld_records) - len(matching_records)
        if not matching_records:
            deferred_reasons.append(
                f"No local validated CCLD records matched facility/license number "
                f"{request.facility_number} and the requested date range."
            )
            continue

        import_result = import_seeded_corpus_artifact(context.connection, artifact)
        source_artifact_identities.append(artifact.source_artifact_identity)
        import_executed = True
        artifact_keys = _source_record_keys(flattened)
        imported_count += len(artifact_keys - before_keys)
        refreshed_count += len(artifact_keys & before_keys)
        before_keys |= artifact_keys
        skipped_non_matching_count += max(
            import_result.imported_record_count - len(artifact_keys),
            0,
        )

    after_records = _scoped_records(context)
    after_matching_count = _matching_read_record_count(after_records, request)

    return CcldImportReloadResult(
        facility_number=request.facility_number,
        start_date=request.start_date,
        end_date=request.end_date,
        import_executed=import_executed,
        available_before_count=before_matching_count,
        available_after_count=after_matching_count,
        imported_source_record_count=imported_count,
        refreshed_source_record_count=refreshed_count,
        skipped_duplicate_source_record_count=refreshed_count,
        skipped_non_matching_source_record_count=skipped_non_matching_count,
        source_artifact_identities=tuple(dict.fromkeys(source_artifact_identities)),
        deferred_reasons=tuple(dict.fromkeys(deferred_reasons)),
    )


def _scoped_records(context: CcldImportReloadContext) -> tuple[Any, ...]:
    return list_source_derived_records(
        context.connection,
        import_batch_id=context.scope.scope_id,
    )


def _source_record_keys(records: tuple[SeededSourceDerivedRecord, ...]) -> set[str]:
    return {record.source_record_key for record in records}


def _validate_request(request: CcldImportReloadRequest) -> None:
    if _FACILITY_NUMBER_RE.fullmatch(request.facility_number) is None:
        raise ValueError("Facility/license number must contain digits only.")
    start_date = _parse_iso_date(request.start_date) if request.start_date else None
    end_date = _parse_iso_date(request.end_date) if request.end_date else None
    if request.start_date and start_date is None:
        raise ValueError("Start date must use YYYY-MM-DD format.")
    if request.end_date and end_date is None:
        raise ValueError("End date must use YYYY-MM-DD format.")
    if start_date is not None and end_date is not None and end_date < start_date:
        raise ValueError("End date must not be before start date.")


def _matching_read_record_count(records: tuple[Any, ...], request: CcldImportReloadRequest) -> int:
    facility_records = [
        record
        for record in records
        if record.connector_name == _CCLD_CONNECTOR_NAME
        and _record_matches_facility(
            record.original_values,
            request.facility_number,
            record.facility_id,
            record.source_url,
        )
    ]
    if request.start_date is None and request.end_date is None:
        return len(facility_records)
    matching_complaints = [
        record
        for record in facility_records
        if record.entity_type == "complaint"
        and _record_matches_date_range(record.original_values, request)
    ]
    if not matching_complaints:
        return 0
    document_ids = {record.source_document_id for record in matching_complaints}
    facility_ids = {record.facility_id for record in matching_complaints if record.facility_id}
    return sum(
        1
        for record in facility_records
        if record.source_document_id in document_ids or record.facility_id in facility_ids
    )


def _is_ccld_record(record: SeededSourceDerivedRecord) -> bool:
    return record.connector_name == _CCLD_CONNECTOR_NAME


def _matching_artifact_records(
    records: list[SeededSourceDerivedRecord],
    request: CcldImportReloadRequest,
) -> list[SeededSourceDerivedRecord]:
    facility_records = [
        record for record in records if _record_matches_facility_request(record, request)
    ]
    if request.start_date is None and request.end_date is None:
        return facility_records
    matching_complaints = [
        record
        for record in facility_records
        if record.entity_type == "complaint"
        and _record_matches_date_range(record.original_values, request)
    ]
    if not matching_complaints:
        return []
    document_ids = {record.source_document_id for record in matching_complaints}
    facility_ids = {record.facility_id for record in matching_complaints if record.facility_id}
    return [
        record
        for record in facility_records
        if record.source_document_id in document_ids or record.facility_id in facility_ids
    ]


def _record_matches_facility_request(
    record: SeededSourceDerivedRecord,
    request: CcldImportReloadRequest,
) -> bool:
    return _record_matches_facility(
        record.original_values,
        request.facility_number,
        record.facility_id,
        record.source_url,
    )


def _record_matches_facility(
    values: Mapping[str, Any],
    facility_number: str,
    facility_id: str | None,
    source_url: str,
) -> bool:
    return (
        values.get("external_facility_number") == facility_number
        or values.get("facility_number") == facility_number
        or (facility_id or "").endswith(facility_number)
        or f"facNum={facility_number}" in source_url
    )


def _record_matches_date_range(
    values: Mapping[str, Any],
    request: CcldImportReloadRequest,
) -> bool:
    record_dates = _record_dates(values)
    if not record_dates:
        return False
    start_date = _parse_iso_date(request.start_date) if request.start_date else None
    end_date = _parse_iso_date(request.end_date) if request.end_date else None
    for record_date in record_dates:
        if start_date is not None and record_date < start_date:
            continue
        if end_date is not None and record_date > end_date:
            continue
        return True
    return False


def _record_dates(values: Mapping[str, Any]) -> tuple[date, ...]:
    dates: list[date] = []
    for key in _DATE_FIELDS:
        value = values.get(key)
        if isinstance(value, str):
            parsed = _parse_iso_date(value[:10])
            if parsed is not None:
                dates.append(parsed)
    return tuple(dates)


def _parse_iso_date(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _resolve_artifact_path(path: Path) -> Path:
    if path.exists() or path.is_absolute():
        return path
    return Path(__file__).resolve().parents[3] / path
