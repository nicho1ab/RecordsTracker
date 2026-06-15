from __future__ import annotations

import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal, Protocol, cast
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from sqlalchemy import JSON, Boolean, CheckConstraint, Column, String, Table, Text, select
from sqlalchemy.engine import Connection

from ccld_complaints.connectors.ccld.facility_reports import (
    FACILITY_DETAIL_URL,
    LIVE_REQUEST_TIMEOUT_SECONDS,
    LIVE_USER_AGENT,
    CcldFacilityReportsConnector,
    ingest_facility_reports_for_facility,
)
from ccld_complaints.hosted_app.auth import (
    RETRIEVAL_JOB_TRIGGER_PERMISSION,
    AuthenticatedActor,
    AuthorizationTarget,
    HostedAccessScope,
    HostedAccountDisabledError,
    HostedAuthenticationRequiredError,
    HostedRoleDeniedError,
    HostedScopeDeniedError,
    require_permission,
)
from ccld_complaints.hosted_app.seeded_import import (
    SeededCorpusArtifact,
    flatten_seeded_corpus_records,
    hosted_seeded_import_metadata,
    import_seeded_corpus_artifact,
    parse_seeded_corpus_artifact,
)

CCLD_RETRIEVAL_RAW_DIR_ENV = "CCLD_RETRIEVAL_RAW_DIR"
CCLD_RETRIEVAL_ENABLED_ENV = "CCLD_RETRIEVAL_ENABLED"
CCLD_RETRIEVAL_MAX_DATE_RANGE_DAYS_ENV = "CCLD_RETRIEVAL_MAX_DATE_RANGE_DAYS"
CCLD_RETRIEVAL_PER_JOB_LIMIT_ENV = "CCLD_RETRIEVAL_PER_JOB_LIMIT"
CCLD_RETRIEVAL_RATE_LIMIT_PER_ACTOR_ENV = "CCLD_RETRIEVAL_RATE_LIMIT_PER_ACTOR"
CCLD_RETRIEVAL_TIMEOUT_SECONDS_ENV = "CCLD_RETRIEVAL_TIMEOUT_SECONDS"
CCLD_RETRIEVAL_RETRY_LIMIT_ENV = "CCLD_RETRIEVAL_RETRY_LIMIT"
CCLD_RETRIEVAL_ENABLED_VALUE = "enabled"
DEFAULT_MAX_DATE_RANGE_DAYS = 366
DEFAULT_PER_JOB_REQUEST_LIMIT = 5
DEFAULT_RATE_LIMIT_PER_ACTOR = 3
DEFAULT_RETRY_LIMIT = 1
CCLD_SOURCE_HOST = "www.ccld.dss.ca.gov"
CCLD_CONNECTOR_NAME = "ccld_facility_reports"
SUPPORTED_RECORD_TYPES = ("complaints", "all_supported")
RECORD_TYPE_LABELS = {
    "complaints": "Complaint records",
    "all_supported": "All supported record types (currently complaint records only)",
}

RetrievalJobState = Literal[
    "queued",
    "running",
    "completed",
    "completed_with_warnings",
    "failed",
    "blocked_by_validation",
    "rate_limited",
]

TERMINAL_JOB_STATES: frozenset[RetrievalJobState] = frozenset(
    {
        "completed",
        "completed_with_warnings",
        "failed",
        "blocked_by_validation",
        "rate_limited",
    }
)

hosted_ccld_retrieval_jobs = Table(
    "hosted_ccld_retrieval_jobs",
    hosted_seeded_import_metadata,
    Column("retrieval_job_id", String(96), primary_key=True),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
    Column("job_state", String(32), nullable=False),
    Column("facility_number", String(32), nullable=False),
    Column("record_type", String(32), nullable=False),
    Column("start_date", String(10), nullable=False),
    Column("end_date", String(10), nullable=False),
    Column("source_scope_type", String(32), nullable=False),
    Column("source_scope_id", String(96), nullable=False),
    Column("actor_provider_subject", Text, nullable=False),
    Column("actor_provider_issuer", Text, nullable=False),
    Column("actor_display_name", Text, nullable=True),
    Column("actor_category", String(32), nullable=False),
    Column("authorization_permission", String(64), nullable=False),
    Column("request_limit", String(16), nullable=False),
    Column("retry_limit", String(16), nullable=False),
    Column("timeout_seconds", String(16), nullable=False),
    Column("raw_storage_path", Text, nullable=False),
    Column("source_artifact_identity", Text, nullable=True),
    Column("result_counts", JSON, nullable=False),
    Column("warnings", JSON, nullable=False),
    Column("errors", JSON, nullable=False),
    Column("safe_message", Text, nullable=False),
    Column("data_mutations_performed", Boolean, nullable=False),
    CheckConstraint(
        "job_state IN ('queued', 'running', 'completed', 'completed_with_warnings', "
        "'failed', 'blocked_by_validation', 'rate_limited')",
        name="ck_hosted_ccld_retrieval_jobs_state",
    ),
    CheckConstraint(
        "record_type IN ('complaints', 'all_supported')",
        name="ck_hosted_ccld_retrieval_jobs_record_type",
    ),
    CheckConstraint(
        "authorization_permission = 'retrieval_job_trigger'",
        name="ck_hosted_ccld_retrieval_jobs_permission",
    ),
)


class CcldRetrievalClient(Protocol):
    def fetch_facility_detail(self, facility_number: str, *, timeout_seconds: int) -> str: ...

    def fetch_report(self, source_url: str, *, timeout_seconds: int) -> bytes: ...


@dataclass(frozen=True)
class CcldRetrievalConfig:
    enabled: bool
    raw_dir: Path | None
    max_date_range_days: int = DEFAULT_MAX_DATE_RANGE_DAYS
    per_job_request_limit: int = DEFAULT_PER_JOB_REQUEST_LIMIT
    rate_limit_per_actor: int = DEFAULT_RATE_LIMIT_PER_ACTOR
    timeout_seconds: int = LIVE_REQUEST_TIMEOUT_SECONDS
    retry_limit: int = DEFAULT_RETRY_LIMIT

    @property
    def configured(self) -> bool:
        return self.enabled and self.raw_dir is not None


@dataclass(frozen=True)
class CcldRetrievalRequest:
    facility_number: str
    record_type: str
    start_date: str
    end_date: str


@dataclass(frozen=True)
class CcldRetrievalValidation:
    request: CcldRetrievalRequest | None
    errors: tuple[str, ...]


@dataclass(frozen=True)
class CcldRetrievalContext:
    connection: Connection
    actor: AuthenticatedActor | None
    scope: HostedAccessScope
    config: CcldRetrievalConfig
    client: CcldRetrievalClient
    now: Callable[[], datetime] = lambda: datetime.now(UTC)


@dataclass(frozen=True)
class CcldRetrievalJobResult:
    retrieval_job_id: str
    job_state: RetrievalJobState
    facility_number: str
    record_type: str
    start_date: str
    end_date: str
    source_artifact_identity: str | None
    result_counts: Mapping[str, int]
    warnings: tuple[str, ...]
    errors: tuple[str, ...]
    safe_message: str


class CcldHttpRetrievalClient:
    def fetch_facility_detail(self, facility_number: str, *, timeout_seconds: int) -> str:
        source_url = f"{FACILITY_DETAIL_URL}/{facility_number}"
        validate_ccld_source_url(source_url, facility_number=facility_number, allow_detail=True)
        return _fetch_url(source_url, timeout_seconds=timeout_seconds).decode(
            "utf-8", errors="replace"
        )

    def fetch_report(self, source_url: str, *, timeout_seconds: int) -> bytes:
        return _fetch_url(source_url, timeout_seconds=timeout_seconds)


def load_ccld_retrieval_config(
    environ: Mapping[str, str] | None = None,
) -> CcldRetrievalConfig:
    active_environ = os.environ if environ is None else environ
    raw_dir_value = active_environ.get(CCLD_RETRIEVAL_RAW_DIR_ENV, "").strip()
    enabled = (
        active_environ.get(CCLD_RETRIEVAL_ENABLED_ENV, "").strip().lower()
        == CCLD_RETRIEVAL_ENABLED_VALUE
    )
    return CcldRetrievalConfig(
        enabled=enabled,
        raw_dir=Path(raw_dir_value) if raw_dir_value else None,
        max_date_range_days=_positive_int_env(
            active_environ,
            CCLD_RETRIEVAL_MAX_DATE_RANGE_DAYS_ENV,
            DEFAULT_MAX_DATE_RANGE_DAYS,
        ),
        per_job_request_limit=_positive_int_env(
            active_environ,
            CCLD_RETRIEVAL_PER_JOB_LIMIT_ENV,
            DEFAULT_PER_JOB_REQUEST_LIMIT,
        ),
        rate_limit_per_actor=_positive_int_env(
            active_environ,
            CCLD_RETRIEVAL_RATE_LIMIT_PER_ACTOR_ENV,
            DEFAULT_RATE_LIMIT_PER_ACTOR,
        ),
        timeout_seconds=_positive_int_env(
            active_environ,
            CCLD_RETRIEVAL_TIMEOUT_SECONDS_ENV,
            LIVE_REQUEST_TIMEOUT_SECONDS,
        ),
        retry_limit=_nonnegative_int_env(
            active_environ,
            CCLD_RETRIEVAL_RETRY_LIMIT_ENV,
            DEFAULT_RETRY_LIMIT,
        ),
    )


def validate_ccld_retrieval_request(
    form_values: Mapping[str, list[str]],
    *,
    max_date_range_days: int = DEFAULT_MAX_DATE_RANGE_DAYS,
) -> CcldRetrievalValidation:
    facility_number = _first_form_value(form_values, "facility_number")
    record_type = _first_form_value(form_values, "record_type") or "complaints"
    raw_start_date = _first_form_value(form_values, "start_date")
    raw_end_date = _first_form_value(form_values, "end_date")
    start_date = _parse_iso_date(raw_start_date)
    end_date = _parse_iso_date(raw_end_date)
    errors: list[str] = []
    if not facility_number:
        errors.append("Facility/license number is required.")
    elif not facility_number.isdigit():
        errors.append("Facility/license number must contain digits only for CCLD retrieval.")
    if record_type not in SUPPORTED_RECORD_TYPES:
        errors.append("Choose a supported CCLD record type.")
    if raw_start_date and start_date is None:
        errors.append("Start date must use YYYY-MM-DD format.")
    if raw_end_date and end_date is None:
        errors.append("End date must use YYYY-MM-DD format.")
    if not raw_start_date:
        errors.append("Start date is required for controlled CCLD retrieval.")
    if not raw_end_date:
        errors.append("End date is required for controlled CCLD retrieval.")
    if start_date is not None and end_date is not None:
        if end_date < start_date:
            errors.append("End date must not be before start date.")
        elif (end_date - start_date).days > max_date_range_days:
            errors.append(
                f"Date range must be {max_date_range_days} days or fewer for CCLD retrieval."
            )
    if errors:
        return CcldRetrievalValidation(request=None, errors=tuple(errors))
    return CcldRetrievalValidation(
        request=CcldRetrievalRequest(
            facility_number=facility_number,
            record_type=record_type,
            start_date=cast(date, start_date).isoformat(),
            end_date=cast(date, end_date).isoformat(),
        ),
        errors=(),
    )


def run_ccld_retrieval_job(
    context: CcldRetrievalContext,
    retrieval_request: CcldRetrievalRequest,
) -> CcldRetrievalJobResult:
    if not context.config.configured:
        return _in_memory_blocked_result(
            context,
            retrieval_request,
            "blocked_by_validation",
            "Controlled CCLD retrieval is not configured on this server.",
        )
    try:
        authorization = require_permission(
            context.actor,
            permission=RETRIEVAL_JOB_TRIGGER_PERMISSION,
            scope=context.scope,
            target=AuthorizationTarget("import_batch", "ccld-retrieval-job"),
        )
    except HostedAuthenticationRequiredError as error:
        return _in_memory_blocked_result(context, retrieval_request, "failed", str(error))
    except (HostedAccountDisabledError, HostedRoleDeniedError, HostedScopeDeniedError) as error:
        return _in_memory_blocked_result(context, retrieval_request, "failed", str(error))
    if _active_actor_job_count(context.connection, authorization.actor.provider_subject) >= (
        context.config.rate_limit_per_actor
    ):
        return _persist_initial_job(
            context,
            retrieval_request,
            actor=authorization.actor,
            state="rate_limited",
            safe_message="Controlled CCLD retrieval is rate-limited for this tester.",
            data_mutations_performed=False,
        )

    job = _persist_initial_job(
        context,
        retrieval_request,
        actor=authorization.actor,
        state="queued",
        safe_message="Controlled CCLD retrieval job queued.",
        data_mutations_performed=False,
    )
    _update_job_state(
        context,
        job.retrieval_job_id,
        state="running",
        safe_message="Controlled CCLD retrieval job is running on the server.",
        result_counts={},
        warnings=(),
        errors=(),
        data_mutations_performed=False,
    )
    try:
        final_job = _execute_job(context, retrieval_request, job.retrieval_job_id)
    except ValueError as error:
        final_job = _update_job_state(
            context,
            job.retrieval_job_id,
            state="blocked_by_validation",
            safe_message=_safe_error_message(error),
            result_counts={},
            warnings=(),
            errors=(_safe_error_message(error),),
            data_mutations_performed=False,
        )
    except Exception:
        final_job = _update_job_state(
            context,
            job.retrieval_job_id,
            state="failed",
            safe_message="Controlled CCLD retrieval failed. Check operator logs for details.",
            result_counts={},
            warnings=(),
            errors=("Controlled retrieval failed safely.",),
            data_mutations_performed=False,
        )
    return final_job


def validate_ccld_source_url(
    source_url: str,
    *,
    facility_number: str,
    allow_detail: bool = False,
) -> None:
    parsed = urlparse(source_url)
    if parsed.scheme != "https" or parsed.netloc.casefold() != CCLD_SOURCE_HOST:
        raise ValueError("CCLD retrieval source URL is outside the approved source allowlist.")
    if allow_detail and parsed.path == f"/carefacilitysearch/FacDetail/{facility_number}":
        return
    if parsed.path != "/transparencyapi/api/FacilityReports":
        raise ValueError("CCLD retrieval source URL path is not approved.")
    query = parse_qs(parsed.query)
    if query.get("facNum", [None])[0] != facility_number:
        raise ValueError("CCLD retrieval source URL facility does not match the job request.")
    report_index = query.get("inx", [None])[0]
    if report_index is None or not report_index.isdigit():
        raise ValueError("CCLD retrieval source URL is missing a supported report index.")


def _execute_job(
    context: CcldRetrievalContext,
    retrieval_request: CcldRetrievalRequest,
    retrieval_job_id: str,
) -> CcldRetrievalJobResult:
    raw_dir = cast(Path, context.config.raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    connector = CcldFacilityReportsConnector(
        facility_number=retrieval_request.facility_number,
        raw_dir=raw_dir,
    )
    facility_detail_html = context.client.fetch_facility_detail(
        retrieval_request.facility_number,
        timeout_seconds=context.config.timeout_seconds,
    )
    result = ingest_facility_reports_for_facility(
        retrieval_request.facility_number,
        connector=connector,
        facility_detail_html=facility_detail_html,
        discovered_at=context.now().isoformat(),
        limit=context.config.per_job_request_limit,
        max_requests=context.config.per_job_request_limit,
        fetch_report=lambda source_url: _fetch_report_with_controls(
            context,
            retrieval_request.facility_number,
            source_url,
        ),
    )
    matching_records = tuple(
        record
        for record in result.records
        if _normalized_record_matches_request(record, retrieval_request)
    )
    warnings = (
        [
            f"{len(result.records) - len(matching_records)} retrieved record bundle(s) "
            "were outside the requested date range."
        ]
        if len(result.records) != len(matching_records)
        else []
    )
    warnings.extend(_failure_warnings(result.failures))
    if not matching_records:
        return _update_job_state(
            context,
            retrieval_job_id,
            state="completed_with_warnings" if warnings else "completed",
            safe_message="Controlled CCLD retrieval completed with no matching imported records.",
            result_counts={
                "discovered_report_candidates": result.discovered_count,
                "selected_report_candidates": len(result.candidates),
                "retrieved_record_bundles": len(result.records),
                "imported_source_derived_records": 0,
                "report_failures": len(result.failures),
            },
            warnings=tuple(warnings),
            errors=(),
            data_mutations_performed=False,
        )
    artifact = _retrieval_artifact(
        context,
        retrieval_request,
        retrieval_job_id,
        matching_records,
        warnings=tuple(warnings),
    )
    import_result = import_seeded_corpus_artifact(context.connection, artifact)
    source_artifact_identity = artifact.source_artifact_identity
    counts: dict[str, int] = {
        "discovered_report_candidates": result.discovered_count,
        "selected_report_candidates": len(result.candidates),
        "retrieved_record_bundles": len(result.records),
        "matched_record_bundles": len(matching_records),
        "imported_source_derived_records": import_result.imported_record_count,
        "report_failures": len(result.failures),
    }
    return _update_job_state(
        context,
        retrieval_job_id,
        state="completed_with_warnings" if warnings else "completed",
        safe_message="Controlled CCLD retrieval imported source-derived records.",
        result_counts=counts,
        warnings=tuple(warnings),
        errors=(),
        data_mutations_performed=True,
        source_artifact_identity=source_artifact_identity,
    )


def _fetch_report_with_controls(
    context: CcldRetrievalContext,
    facility_number: str,
    source_url: str,
) -> bytes:
    validate_ccld_source_url(source_url, facility_number=facility_number)
    last_error: Exception | None = None
    for _attempt in range(context.config.retry_limit + 1):
        try:
            return context.client.fetch_report(
                source_url,
                timeout_seconds=context.config.timeout_seconds,
            )
        except Exception as error:
            last_error = error
    raise RuntimeError("Controlled CCLD report fetch failed after retries.") from last_error


def _retrieval_artifact(
    context: CcldRetrievalContext,
    retrieval_request: CcldRetrievalRequest,
    retrieval_job_id: str,
    records: Sequence[Mapping[str, Any]],
    *,
    warnings: tuple[str, ...],
) -> SeededCorpusArtifact:
    source_artifact_identity = f"ccld-retrieval-job:{retrieval_job_id}"
    raw_data = {
        "import_batch_id": context.scope.scope_id,
        "imported_at": context.now().replace(microsecond=0).isoformat(),
        "source_artifact_identity": source_artifact_identity,
        "source_pipeline_version": "ccld-controlled-retrieval-job-0.1.0",
        "validation_status": "validated",
        "raw_hash_validation_status": "validated",
        "record_counts": _record_counts(records),
        "warnings": list(warnings),
        "errors": [],
        "records": list(records),
    }
    artifact = parse_seeded_corpus_artifact(raw_data)
    flatten_seeded_corpus_records(artifact)
    return artifact


def _record_counts(records: Sequence[Mapping[str, Any]]) -> Mapping[str, int]:
    counts: dict[str, set[str]] = {
        "facility": set(),
        "source_document": set(),
        "complaint": set(),
        "allegation": set(),
        "event": set(),
        "extraction_audit": set(),
    }
    for record in records:
        for entity_name, id_field in (
            ("facility", "facility_id"),
            ("source_document", "document_id"),
            ("complaint", "complaint_id"),
        ):
            value = _mapping(record, entity_name).get(id_field)
            if isinstance(value, str):
                counts[entity_name].add(value)
        for entity_name, list_name, id_field in (
            ("allegation", "allegations", "allegation_id"),
            ("event", "events", "event_id"),
            ("extraction_audit", "extraction_audit", "audit_id"),
        ):
            for item in record.get(list_name, []):
                if isinstance(item, Mapping) and isinstance(item.get(id_field), str):
                    counts[entity_name].add(cast(str, item[id_field]))
    return {key: len(value) for key, value in counts.items()}


def _normalized_record_matches_request(
    record: Mapping[str, Any],
    retrieval_request: CcldRetrievalRequest,
) -> bool:
    if retrieval_request.record_type not in SUPPORTED_RECORD_TYPES:
        return False
    facility = _mapping(record, "facility")
    if facility.get("external_facility_number") != retrieval_request.facility_number:
        return False
    complaint = _mapping(record, "complaint")
    record_dates = []
    for field_name in (
        "complaint_received_date",
        "visit_date",
        "report_date",
        "date_signed",
    ):
        value = complaint.get(field_name)
        if isinstance(value, str):
            parsed = _parse_iso_date(value[:10])
            if parsed is not None:
                record_dates.append(parsed)
    start_date = cast(date, _parse_iso_date(retrieval_request.start_date))
    end_date = cast(date, _parse_iso_date(retrieval_request.end_date))
    return any(start_date <= record_date <= end_date for record_date in record_dates)


def _persist_initial_job(
    context: CcldRetrievalContext,
    request: CcldRetrievalRequest,
    *,
    actor: Any,
    state: RetrievalJobState,
    safe_message: str,
    data_mutations_performed: bool,
) -> CcldRetrievalJobResult:
    job_id = _job_id(context, request)
    now_text = context.now().replace(microsecond=0).isoformat()
    result_counts: Mapping[str, int] = {}
    values = {
        "retrieval_job_id": job_id,
        "created_at": now_text,
        "updated_at": now_text,
        "job_state": state,
        "facility_number": request.facility_number,
        "record_type": request.record_type,
        "start_date": request.start_date,
        "end_date": request.end_date,
        "source_scope_type": context.scope.scope_type,
        "source_scope_id": context.scope.scope_id,
        "actor_provider_subject": actor.provider_subject,
        "actor_provider_issuer": actor.provider_issuer,
        "actor_display_name": actor.display_name,
        "actor_category": actor.actor_category,
        "authorization_permission": RETRIEVAL_JOB_TRIGGER_PERMISSION,
        "request_limit": str(context.config.per_job_request_limit),
        "retry_limit": str(context.config.retry_limit),
        "timeout_seconds": str(context.config.timeout_seconds),
        "raw_storage_path": _safe_raw_storage_label(context.config.raw_dir),
        "source_artifact_identity": None,
        "result_counts": dict(result_counts),
        "warnings": [],
        "errors": [],
        "safe_message": safe_message,
        "data_mutations_performed": data_mutations_performed,
    }
    context.connection.execute(hosted_ccld_retrieval_jobs.insert().values(**values))
    return CcldRetrievalJobResult(
        retrieval_job_id=job_id,
        job_state=state,
        facility_number=request.facility_number,
        record_type=request.record_type,
        start_date=request.start_date,
        end_date=request.end_date,
        source_artifact_identity=None,
        result_counts=result_counts,
        warnings=(),
        errors=(),
        safe_message=safe_message,
    )


def _update_job_state(
    context: CcldRetrievalContext,
    retrieval_job_id: str,
    *,
    state: RetrievalJobState,
    safe_message: str,
    result_counts: Mapping[str, int],
    warnings: tuple[str, ...],
    errors: tuple[str, ...],
    data_mutations_performed: bool,
    source_artifact_identity: str | None = None,
) -> CcldRetrievalJobResult:
    context.connection.execute(
        hosted_ccld_retrieval_jobs.update()
        .where(hosted_ccld_retrieval_jobs.c.retrieval_job_id == retrieval_job_id)
        .values(
            updated_at=context.now().replace(microsecond=0).isoformat(),
            job_state=state,
            source_artifact_identity=source_artifact_identity,
            result_counts=dict(result_counts),
            warnings=list(warnings),
            errors=list(errors),
            safe_message=safe_message,
            data_mutations_performed=data_mutations_performed,
        )
    )
    return _job_result_from_row(context, retrieval_job_id)


def _job_result_from_row(
    context: CcldRetrievalContext,
    retrieval_job_id: str,
) -> CcldRetrievalJobResult:
    row = context.connection.execute(
        select(hosted_ccld_retrieval_jobs).where(
            hosted_ccld_retrieval_jobs.c.retrieval_job_id == retrieval_job_id
        )
    ).mappings().one()
    return CcldRetrievalJobResult(
        retrieval_job_id=str(row["retrieval_job_id"]),
        job_state=cast(RetrievalJobState, row["job_state"]),
        facility_number=str(row["facility_number"]),
        record_type=str(row["record_type"]),
        start_date=str(row["start_date"]),
        end_date=str(row["end_date"]),
        source_artifact_identity=cast(str | None, row["source_artifact_identity"]),
        result_counts=_int_mapping(row["result_counts"]),
        warnings=_string_tuple(row["warnings"]),
        errors=_string_tuple(row["errors"]),
        safe_message=str(row["safe_message"]),
    )


def _in_memory_blocked_result(
    context: CcldRetrievalContext,
    request: CcldRetrievalRequest,
    state: RetrievalJobState,
    message: str,
) -> CcldRetrievalJobResult:
    return CcldRetrievalJobResult(
        retrieval_job_id=_job_id(context, request),
        job_state=state,
        facility_number=request.facility_number,
        record_type=request.record_type,
        start_date=request.start_date,
        end_date=request.end_date,
        source_artifact_identity=None,
        result_counts={},
        warnings=(),
        errors=(_safe_error_message_text(message),),
        safe_message=_safe_error_message_text(message),
    )


def _active_actor_job_count(connection: Connection, provider_subject: str) -> int:
    rows = connection.execute(
        hosted_ccld_retrieval_jobs.select().where(
            hosted_ccld_retrieval_jobs.c.actor_provider_subject == provider_subject,
            hosted_ccld_retrieval_jobs.c.job_state.in_(("queued", "running")),
        )
    ).all()
    return len(rows)


def _job_id(context: CcldRetrievalContext, request: CcldRetrievalRequest) -> str:
    timestamp = context.now().strftime("%Y%m%d%H%M%S%f")
    return f"ccld-retrieval-{request.facility_number}-{timestamp}"


def _fetch_url(source_url: str, *, timeout_seconds: int) -> bytes:
    request = Request(source_url, headers={"User-Agent": LIVE_USER_AGENT})
    with urlopen(request, timeout=timeout_seconds) as response:
        return cast(bytes, response.read())


def _failure_warnings(failures: Sequence[Any]) -> list[str]:
    return [
        f"Report {failure.candidate.report_index} failed during {failure.stage}."
        for failure in failures
    ]


def _int_mapping(value: object) -> Mapping[str, int]:
    if not isinstance(value, Mapping):
        return {}
    counts: dict[str, int] = {}
    for key, count in value.items():
        if isinstance(key, str) and isinstance(count, int):
            counts[key] = count
    return counts


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))


def _mapping(record: Mapping[str, Any], field_name: str) -> Mapping[str, Any]:
    value = record.get(field_name)
    return cast(Mapping[str, Any], value) if isinstance(value, Mapping) else {}


def _safe_raw_storage_label(raw_dir: Path | None) -> str:
    if raw_dir is None:
        return "<unconfigured>"
    return raw_dir.name or "configured-raw-storage"


def _safe_error_message(error: Exception) -> str:
    return _safe_error_message_text(str(error))


def _safe_error_message_text(message: str) -> str:
    lowered = message.casefold()
    forbidden = (
        "authorization",
        "client_secret",
        "connection string",
        "connection_string",
        "cookie",
        "password",
        "private_header",
        "provider_issuer",
        "provider_subject",
        "secret",
        "token",
        "traceback",
    )
    if any(marker in lowered for marker in forbidden):
        return "Controlled CCLD retrieval was blocked safely."
    return message or "Controlled CCLD retrieval was blocked safely."


def _first_form_value(form_values: Mapping[str, list[str]], key: str) -> str:
    values = form_values.get(key, [])
    if not values:
        return ""
    return values[0].strip()


def _parse_iso_date(value: str | None) -> date | None:
    if value is None or not value.strip():
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _positive_int_env(environ: Mapping[str, str], env_name: str, default: int) -> int:
    value = environ.get(env_name, "").strip()
    if not value:
        return default
    parsed = int(value)
    if parsed < 1:
        raise ValueError(f"{env_name} must be at least 1.")
    return parsed


def _nonnegative_int_env(environ: Mapping[str, str], env_name: str, default: int) -> int:
    value = environ.get(env_name, "").strip()
    if not value:
        return default
    parsed = int(value)
    if parsed < 0:
        raise ValueError(f"{env_name} must be greater than or equal to 0.")
    return parsed