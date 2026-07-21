# ruff: noqa: E501

from __future__ import annotations

import base64
import csv
import hashlib
import html
import io
import json
import math
import os
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from functools import cmp_to_key
from pathlib import Path
from typing import Any, Literal, cast
from urllib.parse import parse_qs, urlencode, urlparse

from ccld_complaints.hosted_app.auth import (
    AUDIT_READ_PERMISSION,
    CLOUDFLARE_ACCESS_PROVIDER_CLASS,
    AuthenticatedActor,
    AuthorizationDecision,
    AuthorizationTarget,
    CloudflareAccessAuthError,
    HostedAccessScope,
    HostedAccountDisabledError,
    HostedAuthConfigError,
    HostedAuthenticationRequiredError,
    HostedAuthRuntimeConfig,
    HostedRoleDeniedError,
    HostedScopeDeniedError,
    JwksFetcher,
    authenticate_cloudflare_access_operator_request,
    load_operator_coverage_allowed_emails,
    require_permission,
)
from ccld_complaints.hosted_app.ui_shell import render_page_shell
from ccld_complaints.source_to_screen_coverage import (
    COVERAGE_ARTIFACT_MEDIA_TYPES,
    COVERAGE_CHANGE_OUTCOMES,
    COVERAGE_CONTRACT_VERSION,
    COVERAGE_HASH_VALIDATION_STATES,
    COVERAGE_IMPORT_STATES,
    COVERAGE_JOB_STATES,
    COVERAGE_OPERATIONAL_FAILURE_CATEGORIES,
    COVERAGE_PRESERVED_ARTIFACT_STATES,
    COVERAGE_PROCESSING_OUTCOMES,
    COVERAGE_REFRESH_STATES,
    COVERAGE_RETRIEVAL_STATES,
    COVERAGE_STAGES,
    COVERAGE_TERMINAL_CLASSIFICATIONS,
    CoverageReadError,
    load_validated_coverage_package,
)

OPERATOR_COVERAGE_PREFIX = "/operator/source-coverage"
OPERATOR_COVERAGE_SUMMARY_PATH = OPERATOR_COVERAGE_PREFIX
OPERATOR_COVERAGE_FACILITIES_PATH = f"{OPERATOR_COVERAGE_PREFIX}/facilities"
OPERATOR_COVERAGE_JOBS_PATH = f"{OPERATOR_COVERAGE_PREFIX}/jobs"
OPERATOR_COVERAGE_EXPORT_PATH = f"{OPERATOR_COVERAGE_PREFIX}/export.csv"
OPERATOR_COVERAGE_FACILITY_IDS_PATH = (
    f"{OPERATOR_COVERAGE_PREFIX}/facility-ids.csv"
)
OPERATOR_COVERAGE_PATHS = frozenset(
    {
        OPERATOR_COVERAGE_SUMMARY_PATH,
        OPERATOR_COVERAGE_FACILITIES_PATH,
        OPERATOR_COVERAGE_JOBS_PATH,
        OPERATOR_COVERAGE_EXPORT_PATH,
        OPERATOR_COVERAGE_FACILITY_IDS_PATH,
    }
)

CONTRACT_VERSION = COVERAGE_CONTRACT_VERSION
CONSUMER_VERSION = "1.1.0"
CONTRACT_COMPATIBILITY = ">=1.0.0,<2.0.0"
FIXTURE_MODE_ENV = "CCLD_OPERATOR_COVERAGE_FIXTURE_MODE"
FIXTURE_PACKAGE_DIR_ENV = "CCLD_OPERATOR_COVERAGE_PACKAGE_DIR"
FIXTURE_SCENARIO_ENV = "CCLD_OPERATOR_COVERAGE_FIXTURE_SCENARIO"
FIXTURE_MODE = "contract-v1"
FIXTURE_LABEL = "Fixture coverage data"
DEFAULT_SCOPE = HostedAccessScope("corpus", "operator-source-coverage-fixture")
PRODUCTION_SCOPE = HostedAccessScope("corpus", "operator-source-coverage-runtime")
DEFAULT_RUNTIME_PACKAGE_DIR = Path(
    "/app/data/processed/source-to-screen-audit/runtime-current"
)

PackageState = Literal[
    "available",
    "partial",
    "unavailable",
    "version_mismatch",
    "hash_failed",
    "reconciliation_failed",
]

PACKAGE_STATES = frozenset(
    {
        "available",
        "partial",
        "unavailable",
        "version_mismatch",
        "hash_failed",
        "reconciliation_failed",
    }
)
ARTIFACT_AVAILABILITY = frozenset({"available", "unavailable"})
SELECTION_STATES = frozenset(
    {
        "retained_existing",
        "active_accepted",
        "inactive_candidate",
        "superseded_retained",
        "unavailable",
    }
)
PIPELINE_STAGES = frozenset(COVERAGE_STAGES)
TERMINAL_CLASSIFICATIONS = frozenset(COVERAGE_TERMINAL_CLASSIFICATIONS)
REFRESH_STATES = frozenset(COVERAGE_REFRESH_STATES)
PROCESSING_OUTCOMES = frozenset(COVERAGE_PROCESSING_OUTCOMES)
CHANGE_OUTCOMES = frozenset(COVERAGE_CHANGE_OUTCOMES)
RETRIEVAL_STATES = frozenset(COVERAGE_RETRIEVAL_STATES)
IMPORT_STATES = frozenset(COVERAGE_IMPORT_STATES)
PRESERVED_ARTIFACT_STATES = frozenset(COVERAGE_PRESERVED_ARTIFACT_STATES)
HASH_VALIDATION_STATES = frozenset(COVERAGE_HASH_VALIDATION_STATES)
REFRESH_ELIGIBILITY = frozenset({"eligible", "ineligible", "unknown"})
RETRY_ELIGIBILITY = frozenset({"eligible", "ineligible", "not_evaluated"})
CHECKPOINT_STATES = frozenset(
    {"not_started", "available", "complete", "interrupted", "failed", "unavailable"}
)
JOB_STATES = frozenset(COVERAGE_JOB_STATES)
EXECUTION_MODES = frozenset({"dry_run", "apply"})
FAILURE_CATEGORIES = frozenset(COVERAGE_OPERATIONAL_FAILURE_CATEGORIES)
RELEASE_ASSESSMENTS = frozenset(
    {"passed", "warning", "failed", "reviewed_exception_required"}
)
RECONCILIATION_STATES = frozenset({"passed", "failed"})
RETENTION_DISPOSITIONS = frozenset(
    {"retained", "superseded_retained", "expired", "pending_policy"}
)

COUNT_MAP_ENUMS: Mapping[str, frozenset[str]] = {
    "refresh_state_counts": REFRESH_STATES,
    "processing_outcome_counts": PROCESSING_OUTCOMES,
    "change_outcome_counts": CHANGE_OUTCOMES,
    "retrieval_state_counts": RETRIEVAL_STATES,
    "import_state_counts": IMPORT_STATES,
    "preserved_artifact_state_counts": PRESERVED_ARTIFACT_STATES,
    "hash_validation_state_counts": HASH_VALIDATION_STATES,
    "retry_eligibility_counts": RETRY_ELIGIBILITY,
    "job_state_counts": JOB_STATES,
}
FACILITY_ENUMS: Mapping[str, frozenset[str]] = {
    "refresh_eligibility": REFRESH_ELIGIBILITY,
    "preserved_artifact_state": PRESERVED_ARTIFACT_STATES,
    "hash_validation_state": HASH_VALIDATION_STATES,
    "processing_outcome": PROCESSING_OUTCOMES,
    "change_outcome": CHANGE_OUTCOMES,
    "refresh_state": REFRESH_STATES,
    "operational_failure_category": FAILURE_CATEGORIES,
    "retry_eligibility": RETRY_ELIGIBILITY,
    "checkpoint_state": CHECKPOINT_STATES,
}
JOB_ENUMS: Mapping[str, frozenset[str]] = {
    "job_state": JOB_STATES,
    "execution_mode": EXECUTION_MODES,
    "checkpoint_state": CHECKPOINT_STATES,
    "operational_failure_category": FAILURE_CATEGORIES,
}

FACILITY_REQUIRED_FIELDS = frozenset(
    {
        "contract_version",
        "report_id",
        "facility_entry_id",
        "facility_id",
        "source_snapshot_id",
        "refresh_eligibility",
        "preserved_source_document_count",
        "last_retrieval_attempt_at",
        "last_successful_retrieval_at",
        "last_refresh_attempt_at",
        "last_successful_refresh_at",
        "pipeline_version",
        "preserved_artifact_state",
        "hash_validation_state",
        "source_layout_classification",
        "processing_outcome",
        "change_outcome",
        "refresh_state",
        "governed_conflict",
        "operational_failure_category",
        "retry_eligibility",
        "operator_intervention_required",
        "checkpoint_state",
        "last_job_id",
    }
)
JOB_REQUIRED_FIELDS = frozenset(
    {
        "contract_version",
        "report_id",
        "job_id",
        "job_state",
        "execution_mode",
        "started_at",
        "completed_at",
        "last_successful_refresh_at",
        "pipeline_version",
        "extractor_version",
        "checkpoint_state",
        "checkpoint_id",
        "selected_count",
        "processed_count",
        "changed_count",
        "unchanged_count",
        "skipped_count",
        "warning_count",
        "failed_count",
        "operational_failure_category",
        "previous_accepted_dataset_active",
        "operator_intervention_required",
    }
)
ALLOWED_ARTIFACTS = frozenset(
    {
        "coverage-report.json",
        "operator-facility-index.jsonl",
        "operator-job-index.jsonl",
        "aggregate-coverage.csv",
    }
)
ARTIFACT_MEDIA_TYPES = COVERAGE_ARTIFACT_MEDIA_TYPES
FACILITY_ID_GROUPS = frozenset(
    {"changed", "unchanged", "warning", "failed", "missing_artifact", "retry_eligible"}
)
FACILITY_SORT_KEYS = frozenset(
    {
        "facility_id",
        "processing_outcome",
        "change_outcome",
        "refresh_state",
        "refresh_eligibility",
        "hash_validation_state",
        "source_layout_classification",
        "operational_failure_category",
        "operator_intervention_required",
        "last_retrieval_attempt_at",
        "last_refresh_attempt_at",
    }
)
TIMESTAMP_SORT_KEYS = frozenset(
    {"last_retrieval_attempt_at", "last_refresh_attempt_at"}
)
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100
STABLE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._:-]*$")
REPORT_ID_RE = re.compile(r"^coverage-report-v1-[0-9a-f]{64}$")
FACILITY_ENTRY_ID_RE = re.compile(r"^facility-v1-[0-9a-f]{64}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
UTC_TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$"
)
PROHIBITED_KEYS = frozenset(
    {
        "address",
        "administrator",
        "authentication_claim",
        "authorization_header",
        "complaint_count",
        "complaint_text",
        "connection_string",
        "container_name",
        "cookie",
        "email",
        "exception",
        "facility_name",
        "licensee",
        "narrative",
        "password",
        "private_header",
        "provider_issuer",
        "provider_subject",
        "qnap_host",
        "raw_html",
        "raw_path",
        "secret",
        "source_body",
        "source_url",
        "sql",
        "stack_trace",
        "telephone",
        "token",
    }
)
PROHIBITED_VALUE_PATTERNS = (
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"(?:^|\s)[A-Za-z]:[\\/]"),
    re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"),
    re.compile(r"\b(?:password|client[_ -]?secret|access[_ -]?token|refresh[_ -]?token)\b", re.IGNORECASE),
)


class CoveragePackageError(ValueError):
    def __init__(self, state: PackageState, message: str) -> None:
        super().__init__(message)
        self.state = state


@dataclass(frozen=True)
class OperatorCoverageDashboardContext:
    actor: AuthenticatedActor | None
    scope: HostedAccessScope
    package_dir: Path | None
    fixture_mode: bool = False
    fixture_scenario: str | None = None


@dataclass(frozen=True)
class CoveragePackage:
    package_dir: Path
    manifest: Mapping[str, Any]
    report: Mapping[str, Any]
    facility_rows: tuple[Mapping[str, Any], ...]
    job_rows: tuple[Mapping[str, Any], ...]
    aggregate_csv: bytes | None
    state: PackageState
    unavailable_dimensions: tuple[str, ...]

    @property
    def report_id(self) -> str:
        return _required_string(self.report, "report_id")


@dataclass(frozen=True)
class FacilityFilters:
    facility_id: str = ""
    query: str = ""
    processing_outcome: str = ""
    change_outcome: str = ""
    refresh_state: str = ""
    refresh_eligibility: str = ""
    hash_validation_state: str = ""
    source_layout_classification: str = ""
    operational_failure_category: str = ""
    operator_intervention_required: str = ""
    governed_conflict: str = ""
    retrieval_from: str = ""
    retrieval_to: str = ""
    refresh_from: str = ""
    refresh_to: str = ""
    sort: str = "facility_id"
    direction: str = "asc"
    limit: int = DEFAULT_PAGE_SIZE
    cursor: str = ""


@dataclass(frozen=True)
class FacilityPage:
    rows: tuple[Mapping[str, Any], ...]
    total: int
    start: int
    end: int
    previous_cursor: str | None
    next_cursor: str | None


def local_fixture_operator_coverage_context(
    package_dir: Path | None,
    *,
    scenario: str | None = None,
    scope: HostedAccessScope = DEFAULT_SCOPE,
) -> OperatorCoverageDashboardContext:
    actor = AuthenticatedActor(
        provider_subject="local-fixture-coverage-operator",
        provider_issuer="local-fixture-managed-identity",
        display_name="Fixture coverage operator",
        email=None,
        actor_category="operator",
        account_status="active",
        roles=("developer_operator",),
        scopes=(scope,),
    )
    return OperatorCoverageDashboardContext(
        actor=actor,
        scope=scope,
        package_dir=package_dir,
        fixture_mode=True,
        fixture_scenario=scenario,
    )


def default_operator_coverage_context(
    auth_runtime_config: HostedAuthRuntimeConfig,
    environ: Mapping[str, str] | None = None,
    *,
    request_headers: Mapping[str, str] | None = None,
    cloudflare_jwks_fetcher: JwksFetcher | None = None,
    cloudflare_auth_now: datetime | None = None,
) -> OperatorCoverageDashboardContext | None:
    active_environ = os.environ if environ is None else environ
    if auth_runtime_config.local_dev_actor_allowed:
        if active_environ.get(FIXTURE_MODE_ENV, "").strip() != FIXTURE_MODE:
            return None
        raw_package_dir = active_environ.get(FIXTURE_PACKAGE_DIR_ENV, "").strip()
        package_dir = Path(raw_package_dir) if raw_package_dir else None
        scenario = active_environ.get(FIXTURE_SCENARIO_ENV, "").strip() or None
        return local_fixture_operator_coverage_context(package_dir, scenario=scenario)
    if not auth_runtime_config.production_mode:
        return None
    if auth_runtime_config.provider_class != CLOUDFLARE_ACCESS_PROVIDER_CLASS:
        raise CloudflareAccessAuthError(
            "Operator source coverage requires the Cloudflare Access provider."
        )
    try:
        operator_allowed_emails = load_operator_coverage_allowed_emails(active_environ)
    except HostedAuthConfigError as error:
        raise CloudflareAccessAuthError(str(error)) from error
    actor = authenticate_cloudflare_access_operator_request(
        request_headers or {},
        auth_runtime_config.cloudflare_access,
        scope=PRODUCTION_SCOPE,
        operator_allowed_emails=operator_allowed_emails,
        now=cloudflare_auth_now,
        jwks_fetcher=cloudflare_jwks_fetcher,
    )
    raw_package_dir = active_environ.get(FIXTURE_PACKAGE_DIR_ENV, "").strip()
    package_dir = Path(raw_package_dir) if raw_package_dir else DEFAULT_RUNTIME_PACKAGE_DIR
    return OperatorCoverageDashboardContext(
        actor=actor,
        scope=PRODUCTION_SCOPE,
        package_dir=package_dir,
    )


def route_operator_coverage_response(
    path: str,
    context: OperatorCoverageDashboardContext | None,
    *,
    method: str = "GET",
) -> tuple[int, str, bytes]:
    parsed = urlparse(path)
    if parsed.path not in OPERATOR_COVERAGE_PATHS:
        return 404, "text/plain; charset=utf-8", b"Not found"
    if method != "GET":
        return _message_response(
            405,
            "Read-only route",
            "Operator source coverage supports GET requests only.",
        )

    active_context = context or OperatorCoverageDashboardContext(
        actor=None,
        scope=DEFAULT_SCOPE,
        package_dir=None,
    )
    try:
        authorization = _authorize(active_context)
    except HostedAuthenticationRequiredError as error:
        return _message_response(401, "Operator sign-in required", str(error))
    except HostedAccountDisabledError as error:
        return _message_response(403, "Operator account unavailable", str(error))
    except HostedRoleDeniedError as error:
        return _message_response(403, "Operator access denied", str(error))
    except HostedScopeDeniedError as error:
        return _message_response(403, "Operator scope denied", str(error))

    try:
        package = load_coverage_package(
            active_context.package_dir,
            allow_legacy_fixture=active_context.fixture_mode,
        )
        if parsed.path == OPERATOR_COVERAGE_SUMMARY_PATH:
            return _html_response(
                200,
                _render_summary_page(package, active_context, authorization),
            )
        if parsed.path == OPERATOR_COVERAGE_FACILITIES_PATH:
            filters = facility_filters_from_query(parsed.query, package)
            page = facility_page(package, filters)
            return _html_response(
                200,
                _render_facilities_page(package, active_context, filters, page),
            )
        if parsed.path == OPERATOR_COVERAGE_JOBS_PATH:
            return _html_response(200, _render_jobs_page(package, active_context))
        if parsed.path == OPERATOR_COVERAGE_EXPORT_PATH:
            return _aggregate_csv_response(package)
        if parsed.path == OPERATOR_COVERAGE_FACILITY_IDS_PATH:
            return _facility_ids_csv_response(package, parsed.query)
    except CoveragePackageError as error:
        return _package_error_response(error, active_context, parsed.path)
    except ValueError as error:
        return _message_response(400, "Invalid operator coverage request", str(error))
    return 404, "text/plain; charset=utf-8", b"Not found"


def load_coverage_package(
    package_dir: Path | None, *, allow_legacy_fixture: bool = False
) -> CoveragePackage:
    if package_dir is None:
        raise CoveragePackageError(
            "unavailable",
            "Coverage report unavailable. Configure a validated contract package.",
        )
    if not package_dir.is_dir():
        raise CoveragePackageError(
            "unavailable",
            "Coverage report unavailable. The configured package could not be opened.",
        )
    manifest_path = package_dir / "manifest.json"
    if not manifest_path.is_file():
        raise CoveragePackageError(
            "unavailable",
            "Coverage report unavailable. The required manifest is missing.",
        )
    try:
        validated = load_validated_coverage_package(package_dir)
    except CoverageReadError as error:
        if allow_legacy_fixture and _is_legacy_fixture_package(manifest_path):
            return _load_legacy_fixture_coverage_package(package_dir)
        raise CoveragePackageError(error.state, str(error)) from error
    return CoveragePackage(
        package_dir=validated.package_dir,
        manifest=validated.manifest,
        report=validated.report,
        facility_rows=validated.facility_rows,
        job_rows=validated.job_rows,
        aggregate_csv=validated.aggregate_csv,
        state=validated.state,
        unavailable_dimensions=validated.unavailable_dimensions,
    )


def _is_legacy_fixture_package(manifest_path: Path) -> bool:
    try:
        manifest = _load_json_object(manifest_path, "legacy fixture manifest")
    except CoveragePackageError:
        return False
    return manifest.get("producer_schema_id") == "coverage.report.schema.v1"


def _load_legacy_fixture_coverage_package(package_dir: Path) -> CoveragePackage:
    """Load Issue 477's deterministic UI scenarios, never a production package."""

    manifest_path = package_dir / "manifest.json"
    manifest = _load_json_object(manifest_path, "manifest")
    _validate_prohibited_content(manifest)
    version = _required_string(manifest, "contract_version")
    _validate_compatibility(version, _required_string(manifest, "minimum_consumer_version"))
    report_id = _required_string(manifest, "report_id")
    if not REPORT_ID_RE.fullmatch(report_id):
        raise CoveragePackageError("unavailable", "Coverage report identity is invalid.")
    _validate_timestamp(_required_string(manifest, "generated_at"), "generated_at")
    for field in (
        "evaluation_id",
        "criteria_set_id",
        "scope_id",
        "producer_schema_id",
        "producer_version",
    ):
        _validate_stable_id(_required_string(manifest, field), field)
    _validate_provenance(_required_mapping(manifest, "provenance"))
    _validate_manifest_source_snapshots(manifest)
    if report_id != _expected_report_id(manifest):
        raise CoveragePackageError(
            "unavailable", "Coverage report deterministic identity does not match."
        )
    _validate_retention(_required_mapping(manifest, "retention"))
    artifact_entries = _validate_manifest_artifacts(manifest)

    report_bytes = _read_validated_artifact(
        package_dir,
        artifact_entries,
        "coverage-report.json",
        required=True,
    )
    assert report_bytes is not None
    report = _json_object_from_bytes(report_bytes, "coverage report")
    _validate_prohibited_content(report)
    _validate_artifact_identity(report, version, report_id, "coverage report")
    if _required_string(report, "generated_at") != _required_string(
        manifest, "generated_at"
    ):
        raise CoveragePackageError(
            "unavailable", "Coverage report generation identity does not match."
        )
    state = cast(PackageState, _required_string(report, "package_availability"))
    if state not in PACKAGE_STATES:
        raise CoveragePackageError("unavailable", "Coverage package availability is invalid.")
    if state == "version_mismatch":
        raise CoveragePackageError(
            "version_mismatch", "Coverage report version is not supported."
        )
    if state == "hash_failed":
        raise CoveragePackageError("hash_failed", "Coverage report hash validation failed.")
    if state == "reconciliation_failed":
        raise CoveragePackageError(
            "reconciliation_failed", "Coverage report reconciliation failed."
        )

    facility_bytes = _read_validated_artifact(
        package_dir,
        artifact_entries,
        "operator-facility-index.jsonl",
        required=False,
    )
    job_bytes = _read_validated_artifact(
        package_dir,
        artifact_entries,
        "operator-job-index.jsonl",
        required=False,
    )
    aggregate_csv = _read_validated_artifact(
        package_dir,
        artifact_entries,
        "aggregate-coverage.csv",
        required=False,
    )
    facility_rows = _jsonl_rows(facility_bytes, "operator facility index")
    job_rows = _jsonl_rows(job_bytes, "operator job index")
    _validate_report(report)
    _validate_facility_rows(facility_rows, version, report_id, manifest)
    _validate_job_rows(job_rows, version, report_id)
    if aggregate_csv is not None:
        _validate_aggregate_csv(aggregate_csv, report_id)
    _validate_index_reconciliation(report, facility_rows)
    unavailable_dimensions = _string_tuple(report.get("unavailable_dimensions", ()))
    if state == "partial" and not unavailable_dimensions:
        raise CoveragePackageError(
            "unavailable", "Partial coverage must name unavailable dimensions."
        )
    return CoveragePackage(
        package_dir=package_dir,
        manifest=manifest,
        report=report,
        facility_rows=facility_rows,
        job_rows=job_rows,
        aggregate_csv=aggregate_csv,
        state=state,
        unavailable_dimensions=unavailable_dimensions,
    )


def facility_filters_from_query(query: str, package: CoveragePackage) -> FacilityFilters:
    values = parse_qs(query, keep_blank_values=True)
    _reject_multiple_values(values)
    source_layouts = frozenset(
        _required_string(row, "source_layout_classification")
        for row in package.facility_rows
    )
    limit = _query_int(values, "limit", DEFAULT_PAGE_SIZE)
    if limit < 1 or limit > MAX_PAGE_SIZE:
        raise ValueError(f"Facility page size must be between 1 and {MAX_PAGE_SIZE}.")
    sort = _query_value(values, "sort") or "facility_id"
    direction = _query_value(values, "direction") or "asc"
    if sort not in FACILITY_SORT_KEYS:
        raise ValueError("Unsupported facility sort key.")
    if direction not in {"asc", "desc"}:
        raise ValueError("Facility sort direction must be asc or desc.")
    filters = FacilityFilters(
        facility_id=_query_value(values, "facility_id"),
        query=_query_value(values, "q"),
        processing_outcome=_validated_query_enum(
            values, "processing_outcome", PROCESSING_OUTCOMES
        ),
        change_outcome=_validated_query_enum(values, "change_outcome", CHANGE_OUTCOMES),
        refresh_state=_validated_query_enum(values, "refresh_state", REFRESH_STATES),
        refresh_eligibility=_validated_query_enum(
            values, "refresh_eligibility", REFRESH_ELIGIBILITY
        ),
        hash_validation_state=_validated_query_enum(
            values, "hash_validation_state", HASH_VALIDATION_STATES
        ),
        source_layout_classification=_validated_query_enum(
            values,
            "source_layout_classification",
            source_layouts,
        ),
        operational_failure_category=_validated_query_enum(
            values, "operational_failure_category", FAILURE_CATEGORIES
        ),
        operator_intervention_required=_validated_boolean_filter(
            values, "operator_intervention_required"
        ),
        governed_conflict=_validated_boolean_filter(values, "governed_conflict"),
        retrieval_from=_validated_optional_timestamp_bound(values, "retrieval_from"),
        retrieval_to=_validated_optional_timestamp_bound(values, "retrieval_to"),
        refresh_from=_validated_optional_timestamp_bound(values, "refresh_from"),
        refresh_to=_validated_optional_timestamp_bound(values, "refresh_to"),
        sort=sort,
        direction=direction,
        limit=limit,
        cursor=_query_value(values, "cursor"),
    )
    return filters


def facility_page(package: CoveragePackage, filters: FacilityFilters) -> FacilityPage:
    filtered = [row for row in package.facility_rows if _facility_matches(row, filters)]

    def compare(left: Mapping[str, Any], right: Mapping[str, Any]) -> int:
        return _compare_rows(left, right, filters)

    ordered = sorted(filtered, key=cmp_to_key(compare))
    start_index = 0
    if filters.cursor:
        cursor = _decode_cursor(filters.cursor)
        _validate_cursor(cursor, package.report_id, filters)
        anchor = _required_list(cursor, "anchor")
        anchor_index = _find_anchor_index(ordered, anchor, filters)
        cursor_direction = _required_string(cursor, "page_direction")
        if cursor_direction == "next":
            start_index = anchor_index + 1
        elif cursor_direction == "previous":
            start_index = max(0, anchor_index - filters.limit)
        else:
            raise ValueError("Facility cursor direction is invalid.")
    rows = tuple(ordered[start_index : start_index + filters.limit])
    total = len(ordered)
    start = start_index + 1 if rows else 0
    end = start_index + len(rows)
    previous_cursor = None
    next_cursor = None
    if rows and start_index > 0:
        previous_cursor = _encode_cursor(
            package.report_id,
            filters,
            "previous",
            _row_order_tuple(rows[0], filters),
        )
    if rows and end < total:
        next_cursor = _encode_cursor(
            package.report_id,
            filters,
            "next",
            _row_order_tuple(rows[-1], filters),
        )
    return FacilityPage(
        rows=rows,
        total=total,
        start=start,
        end=end,
        previous_cursor=previous_cursor,
        next_cursor=next_cursor,
    )


def _authorize(context: OperatorCoverageDashboardContext) -> AuthorizationDecision:
    return require_permission(
        context.actor,
        permission=AUDIT_READ_PERMISSION,
        scope=context.scope,
        target=AuthorizationTarget("audit_event", context.scope.scope_id),
    )


def _validate_compatibility(version: str, minimum_consumer_version: str) -> None:
    version_parts = _semantic_version(version)
    minimum_parts = _semantic_version(minimum_consumer_version)
    if version_parts[0] != 1 or minimum_parts > _semantic_version(CONSUMER_VERSION):
        raise CoveragePackageError(
            "version_mismatch", "Coverage report version is not supported."
        )


def _semantic_version(value: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", value)
    if match is None:
        raise CoveragePackageError(
            "version_mismatch", "Coverage report version is not supported."
        )
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def _validate_manifest_source_snapshots(manifest: Mapping[str, Any]) -> None:
    snapshots = _required_list(manifest, "source_snapshots")
    if not snapshots:
        raise CoveragePackageError("unavailable", "Coverage source snapshots are missing.")
    seen: set[str] = set()
    ordered_ids: list[str] = []
    for item in snapshots:
        snapshot = _mapping(item, "source snapshot")
        snapshot_id = _required_string(snapshot, "source_snapshot_id")
        source_family_id = _required_string(snapshot, "source_family_id")
        _validate_stable_id(snapshot_id, "source_snapshot_id")
        _validate_stable_id(source_family_id, "source_family_id")
        if snapshot_id in seen:
            raise CoveragePackageError("unavailable", "Duplicate source snapshot identity.")
        seen.add(snapshot_id)
        ordered_ids.append(snapshot_id)
        _validate_enum(snapshot, "selection_state", SELECTION_STATES)
        cadence = _required_string(snapshot, "cadence_status")
        if cadence != "not_approved":
            raise CoveragePackageError(
                "unavailable", "Coverage package claims an unapproved refresh cadence."
            )
        availability = _required_string(snapshot, "availability")
        if availability not in {"available", "unavailable"}:
            raise CoveragePackageError("unavailable", "Source snapshot availability is invalid.")
        observed_at = snapshot.get("observed_at")
        if observed_at is not None:
            _validate_timestamp(_string(observed_at, "observed_at"), "observed_at")
        row_count = snapshot.get("row_count")
        if row_count is not None:
            _nonnegative_int(row_count, "row_count")
    if ordered_ids != sorted(ordered_ids):
        raise CoveragePackageError(
            "unavailable", "Coverage source snapshots are not canonically ordered."
        )


def _expected_report_id(manifest: Mapping[str, Any]) -> str:
    identity = {
        "contract_major": _semantic_version(
            _required_string(manifest, "contract_version")
        )[0],
        "criteria_set_id": _required_string(manifest, "criteria_set_id"),
        "evaluation_id": _required_string(manifest, "evaluation_id"),
        "producer_schema_id": _required_string(manifest, "producer_schema_id"),
        "scope_id": _required_string(manifest, "scope_id"),
        "source_snapshot_ids": [
            _required_string(_mapping(item, "source snapshot"), "source_snapshot_id")
            for item in _required_list(manifest, "source_snapshots")
        ],
    }
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return f"coverage-report-v1-{hashlib.sha256(canonical).hexdigest()}"


def _validate_retention(retention: Mapping[str, Any]) -> None:
    policy_id = retention.get("policy_id")
    disposition = _required_string(retention, "disposition")
    if disposition not in RETENTION_DISPOSITIONS:
        raise CoveragePackageError("unavailable", "Retention disposition is invalid.")
    if policy_id is None:
        if disposition != "pending_policy" or retention.get("retain_until") is not None:
            raise CoveragePackageError(
                "unavailable", "Pending retention policy fields do not reconcile."
            )
    elif not isinstance(policy_id, str):
        raise CoveragePackageError("unavailable", "Retention policy identity is invalid.")
    retain_until = retention.get("retain_until")
    if retain_until is not None:
        _validate_timestamp(_string(retain_until, "retain_until"), "retain_until")
    previous = retention.get("previous_accepted_report_id")
    if previous is not None and not REPORT_ID_RE.fullmatch(
        _string(previous, "previous_accepted_report_id")
    ):
        raise CoveragePackageError("unavailable", "Previous report identity is invalid.")


def _validate_provenance(provenance: Mapping[str, Any]) -> None:
    _validate_stable_id(
        _required_string(provenance, "generation_mode"), "generation_mode"
    )
    for field in ("input_manifest_ids", "governed_fixture_ids"):
        identities = _required_list(provenance, field)
        if not identities:
            raise CoveragePackageError(
                "unavailable", f"Required provenance field {field} is empty."
            )
        for identity in identities:
            _validate_stable_id(_string(identity, field), field)


def _validate_manifest_artifacts(
    manifest: Mapping[str, Any],
) -> Mapping[str, Mapping[str, Any]]:
    entries: dict[str, Mapping[str, Any]] = {}
    for item in _required_list(manifest, "artifacts"):
        artifact = _mapping(item, "artifact")
        name = _required_string(artifact, "name")
        if name not in ALLOWED_ARTIFACTS or name in entries:
            raise CoveragePackageError("unavailable", "Coverage artifact manifest is invalid.")
        if _required_string(artifact, "media_type") != ARTIFACT_MEDIA_TYPES[name]:
            raise CoveragePackageError("unavailable", "Coverage artifact media type is invalid.")
        availability = _required_string(artifact, "availability")
        if availability not in ARTIFACT_AVAILABILITY:
            raise CoveragePackageError("unavailable", "Coverage artifact availability is invalid.")
        if availability == "available":
            _nonnegative_int(artifact.get("byte_count"), "artifact byte_count")
            digest = _required_string(artifact, "sha256")
            if not SHA256_RE.fullmatch(digest):
                raise CoveragePackageError("hash_failed", "Coverage artifact hash is invalid.")
        else:
            reason = _required_string(artifact, "reason_category")
            _validate_stable_id(reason, "artifact reason_category")
        entries[name] = artifact
    if "coverage-report.json" not in entries:
        raise CoveragePackageError("unavailable", "Required coverage report is missing.")
    return entries


def _read_validated_artifact(
    package_dir: Path,
    entries: Mapping[str, Mapping[str, Any]],
    name: str,
    *,
    required: bool,
) -> bytes | None:
    entry = entries.get(name)
    if entry is None:
        if required:
            raise CoveragePackageError("unavailable", f"Required artifact {name} is missing.")
        return None
    if _required_string(entry, "availability") == "unavailable":
        if required:
            raise CoveragePackageError("unavailable", f"Required artifact {name} is unavailable.")
        return None
    path = package_dir / name
    if path.parent != package_dir or not path.is_file():
        raise CoveragePackageError("unavailable", f"Coverage artifact {name} is missing.")
    data = path.read_bytes()
    if len(data) != _nonnegative_int(entry.get("byte_count"), "artifact byte_count"):
        raise CoveragePackageError("hash_failed", "Coverage artifact byte count failed validation.")
    digest = hashlib.sha256(data).hexdigest()
    if digest != _required_string(entry, "sha256"):
        raise CoveragePackageError("hash_failed", "Coverage report hash validation failed.")
    return data


def _validate_artifact_identity(
    artifact: Mapping[str, Any], version: str, report_id: str, label: str
) -> None:
    if _required_string(artifact, "contract_version") != version:
        raise CoveragePackageError("version_mismatch", f"{label.title()} version does not match.")
    if _required_string(artifact, "report_id") != report_id:
        raise CoveragePackageError("unavailable", f"{label.title()} identity does not match.")


def _validate_report(report: Mapping[str, Any]) -> None:
    _validate_timestamp(_required_string(report, "generated_at"), "report generated_at")
    for field in ("pipeline_version", "extractor_version"):
        _validate_stable_id(_required_string(report, field), field)
    invariant_ids = _required_list(report, "reconciliation_invariant_ids")
    if not invariant_ids:
        raise CoveragePackageError(
            "unavailable", "Coverage reconciliation invariant identities are missing."
        )
    for invariant_id in invariant_ids:
        _validate_stable_id(
            _string(invariant_id, "reconciliation_invariant_id"),
            "reconciliation_invariant_id",
        )
    release = _required_string(report, "release_assessment")
    if release not in RELEASE_ASSESSMENTS:
        raise CoveragePackageError("unavailable", "Release assessment is invalid.")
    reconciliation = _required_string(report, "reconciliation_status")
    if reconciliation not in RECONCILIATION_STATES:
        raise CoveragePackageError("unavailable", "Reconciliation status is invalid.")
    if reconciliation == "failed":
        raise CoveragePackageError(
            "reconciliation_failed", "Coverage report reconciliation failed."
        )
    operations = _required_mapping(report, "operations")
    existing_total = _nonnegative_int(
        operations.get("existing_facility_total"), "existing_facility_total"
    )
    eligible_total = _nonnegative_int(
        operations.get("eligible_facility_total"), "eligible_facility_total"
    )
    ineligible_total = _nonnegative_int(
        operations.get("ineligible_facility_total"), "ineligible_facility_total"
    )
    unknown_total = _nonnegative_int(
        operations.get("unknown_eligibility_total"), "unknown_eligibility_total"
    )
    if eligible_total + ineligible_total + unknown_total != existing_total:
        raise CoveragePackageError(
            "reconciliation_failed", "Coverage eligibility totals do not reconcile."
        )
    for field, allowed in COUNT_MAP_ENUMS.items():
        counts = _required_mapping(operations, field)
        if set(counts) != set(allowed):
            raise CoveragePackageError("unavailable", f"{field} has an invalid closed enum.")
        for key, value in counts.items():
            _nonnegative_int(value, f"{field}.{key}")
        if field != "job_state_counts" and sum(cast(int, value) for value in counts.values()) != existing_total:
            if field in {
                "refresh_state_counts",
                "processing_outcome_counts",
                "change_outcome_counts",
                "preserved_artifact_state_counts",
                "hash_validation_state_counts",
                "retry_eligibility_counts",
            }:
                raise CoveragePackageError(
                    "reconciliation_failed", f"{field} does not reconcile."
                )
    preserved_total = _nonnegative_int(
        operations.get("preserved_artifact_facility_total"),
        "preserved_artifact_facility_total",
    )
    preserved_counts = _required_mapping(operations, "preserved_artifact_state_counts")
    if preserved_total != _nonnegative_int(preserved_counts.get("preserved"), "preserved"):
        raise CoveragePackageError(
            "reconciliation_failed", "Preserved artifact totals do not reconcile."
        )
    for field in (
        "governed_conflict_facility_total",
        "operator_intervention_required_total",
    ):
        _nonnegative_int(operations.get(field), field)
    coverage = _required_mapping(report, "coverage")
    classifications = _required_mapping(coverage, "terminal_classification_counts")
    if set(classifications) != set(TERMINAL_CLASSIFICATIONS):
        raise CoveragePackageError(
            "unavailable", "Terminal classification counts have an invalid closed enum."
        )
    for key, value in classifications.items():
        _nonnegative_int(value, f"terminal_classification_counts.{key}")
    for item in _required_list(coverage, "stage_rows"):
        row = _mapping(item, "coverage stage row")
        _validate_stable_id(_required_string(row, "field_id"), "field_id")
        _validate_enum(row, "stage", PIPELINE_STAGES)
        eligible = _nonnegative_int(row.get("eligible_count"), "eligible_count")
        parts = [
            _nonnegative_int(row.get(field), field)
            for field in (
                "successful_count",
                "blank_count",
                "absent_count",
                "unavailable_count",
                "unsupported_count",
                "conflict_count",
                "failure_count",
                "skipped_count",
            )
        ]
        if eligible != sum(parts):
            raise CoveragePackageError(
                "reconciliation_failed", "Coverage stage counts do not reconcile."
            )


def _validate_facility_rows(
    rows: Sequence[Mapping[str, Any]],
    version: str,
    report_id: str,
    manifest: Mapping[str, Any],
) -> None:
    snapshots = {
        _required_string(snapshot, "source_snapshot_id"): _required_string(
            snapshot, "source_family_id"
        )
        for item in _required_list(manifest, "source_snapshots")
        for snapshot in (_mapping(item, "source snapshot"),)
    }
    seen: set[str] = set()
    for row in rows:
        if set(row) != set(FACILITY_REQUIRED_FIELDS):
            raise CoveragePackageError("unavailable", "Operator facility index fields are invalid.")
        _validate_artifact_identity(row, version, report_id, "operator facility index row")
        entry_id = _required_string(row, "facility_entry_id")
        if not FACILITY_ENTRY_ID_RE.fullmatch(entry_id) or entry_id in seen:
            raise CoveragePackageError("unavailable", "Facility entry identity is invalid.")
        seen.add(entry_id)
        facility_id = _required_string(row, "facility_id")
        if not facility_id.strip() or any(character in facility_id for character in "\r\n,"):
            raise CoveragePackageError("unavailable", "Facility ID is invalid.")
        source_snapshot_id = _required_string(row, "source_snapshot_id")
        if source_snapshot_id not in snapshots:
            raise CoveragePackageError("unavailable", "Facility source snapshot is unknown.")
        if entry_id != _expected_facility_entry_id(
            snapshots[source_snapshot_id], facility_id
        ):
            raise CoveragePackageError(
                "unavailable", "Facility entry deterministic identity does not match."
            )
        _nonnegative_int(
            row.get("preserved_source_document_count"),
            "preserved_source_document_count",
        )
        for field, allowed in FACILITY_ENUMS.items():
            _validate_enum(row, field, allowed)
        _validate_stable_id(
            _required_string(row, "source_layout_classification"),
            "source_layout_classification",
        )
        _validate_stable_id(_required_string(row, "pipeline_version"), "pipeline_version")
        for field in (
            "last_retrieval_attempt_at",
            "last_successful_retrieval_at",
            "last_refresh_attempt_at",
            "last_successful_refresh_at",
        ):
            value = row.get(field)
            if value is not None:
                _validate_timestamp(_string(value, field), field)
        for field in ("governed_conflict", "operator_intervention_required"):
            if not isinstance(row.get(field), bool):
                raise CoveragePackageError("unavailable", f"{field} must be boolean.")
        last_job_id = row.get("last_job_id")
        if last_job_id is not None:
            _validate_stable_id(_string(last_job_id, "last_job_id"), "last_job_id")


def _validate_job_rows(
    rows: Sequence[Mapping[str, Any]], version: str, report_id: str
) -> None:
    seen: set[str] = set()
    for row in rows:
        if set(row) != set(JOB_REQUIRED_FIELDS):
            raise CoveragePackageError("unavailable", "Operator job index fields are invalid.")
        _validate_artifact_identity(row, version, report_id, "operator job index row")
        job_id = _required_string(row, "job_id")
        _validate_stable_id(job_id, "job_id")
        if job_id in seen:
            raise CoveragePackageError("unavailable", "Duplicate operator job identity.")
        seen.add(job_id)
        for field, allowed in JOB_ENUMS.items():
            _validate_enum(row, field, allowed)
        for field in ("pipeline_version", "extractor_version"):
            _validate_stable_id(_required_string(row, field), field)
        checkpoint_id = row.get("checkpoint_id")
        if checkpoint_id is not None:
            _validate_stable_id(_string(checkpoint_id, "checkpoint_id"), "checkpoint_id")
        for field in ("started_at", "completed_at", "last_successful_refresh_at"):
            value = row.get(field)
            if value is not None:
                _validate_timestamp(_string(value, field), field)
        for field in (
            "selected_count",
            "processed_count",
            "changed_count",
            "unchanged_count",
            "skipped_count",
            "warning_count",
            "failed_count",
        ):
            _nonnegative_int(row.get(field), field)
        for field in (
            "previous_accepted_dataset_active",
            "operator_intervention_required",
        ):
            if not isinstance(row.get(field), bool):
                raise CoveragePackageError("unavailable", f"{field} must be boolean.")


def _validate_aggregate_csv(data: bytes, report_id: str) -> None:
    text = _utf8_text(data, "aggregate coverage CSV")
    if "\r" in text or not text.endswith("\n"):
        raise CoveragePackageError("unavailable", "Aggregate coverage CSV must use LF lines.")
    reader = csv.DictReader(io.StringIO(text, newline=""))
    headers = reader.fieldnames or []
    required = {
        "report_id",
        "dimension",
        "category",
        "numerator_count",
        "denominator_count",
        "percentage",
        "status",
        "criteria_set_id",
        "source_family_id",
    }
    if set(headers) != required or "facility_id" in headers:
        raise CoveragePackageError("unavailable", "Aggregate coverage CSV headers are invalid.")
    for row in reader:
        if row["report_id"] != report_id:
            raise CoveragePackageError("unavailable", "Aggregate CSV report identity does not match.")
        for field in ("numerator_count", "denominator_count"):
            try:
                value = int(row[field])
            except (TypeError, ValueError) as error:
                raise CoveragePackageError(
                    "unavailable", "Aggregate CSV counts are invalid."
                ) from error
            if value < 0:
                raise CoveragePackageError("unavailable", "Aggregate CSV counts are invalid.")
        percentage = row["percentage"]
        if percentage:
            try:
                numeric_percentage = float(percentage)
            except ValueError as error:
                raise CoveragePackageError(
                    "unavailable", "Aggregate CSV percentage is invalid."
                ) from error
            if not math.isfinite(numeric_percentage):
                raise CoveragePackageError(
                    "unavailable", "Aggregate CSV percentage is invalid."
                )


def _validate_index_reconciliation(
    report: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]
) -> None:
    if not rows:
        return
    operations = _required_mapping(report, "operations")
    expected_conflicts = _nonnegative_int(
        operations.get("governed_conflict_facility_total"),
        "governed_conflict_facility_total",
    )
    actual_conflicts = sum(bool(row["governed_conflict"]) for row in rows)
    if expected_conflicts != actual_conflicts:
        raise CoveragePackageError(
            "reconciliation_failed", "Facility conflict totals do not reconcile."
        )


def _validate_prohibited_content(value: Any, *, key: str | None = None) -> None:
    if key is not None and key.casefold() in PROHIBITED_KEYS:
        raise CoveragePackageError("unavailable", "Coverage package contains prohibited content.")
    if isinstance(value, Mapping):
        for child_key, child_value in value.items():
            if not isinstance(child_key, str):
                raise CoveragePackageError("unavailable", "Coverage package keys are invalid.")
            _validate_prohibited_content(child_value, key=child_key)
        return
    if isinstance(value, list):
        for item in value:
            _validate_prohibited_content(item, key=key)
        return
    if isinstance(value, float) and not math.isfinite(value):
        raise CoveragePackageError("unavailable", "Coverage package contains non-finite data.")
    if isinstance(value, str):
        for pattern in PROHIBITED_VALUE_PATTERNS:
            if pattern.search(value):
                raise CoveragePackageError(
                    "unavailable", "Coverage package contains prohibited content."
                )


def _jsonl_rows(data: bytes | None, label: str) -> tuple[Mapping[str, Any], ...]:
    if data is None:
        return ()
    text = _utf8_text(data, label)
    if "\r" in text or (text and not text.endswith("\n")):
        raise CoveragePackageError("unavailable", f"{label.title()} must use LF lines.")
    rows: list[Mapping[str, Any]] = []
    for line in text.splitlines():
        if not line:
            raise CoveragePackageError("unavailable", f"{label.title()} has an empty row.")
        try:
            loaded = json.loads(line)
        except json.JSONDecodeError as error:
            raise CoveragePackageError("unavailable", f"{label.title()} is invalid JSONL.") from error
        row = _mapping(loaded, label)
        _validate_prohibited_content(row)
        rows.append(row)
    return tuple(rows)


def _facility_matches(row: Mapping[str, Any], filters: FacilityFilters) -> bool:
    facility_id = _required_string(row, "facility_id")
    if filters.facility_id and facility_id != filters.facility_id:
        return False
    if filters.query and filters.query.casefold() not in facility_id.casefold():
        return False
    for filter_name in (
        "processing_outcome",
        "change_outcome",
        "refresh_state",
        "refresh_eligibility",
        "hash_validation_state",
        "source_layout_classification",
        "operational_failure_category",
    ):
        expected = cast(str, getattr(filters, filter_name))
        if expected and row[filter_name] != expected:
            return False
    for filter_name in ("operator_intervention_required", "governed_conflict"):
        expected_boolean = cast(str, getattr(filters, filter_name))
        if expected_boolean and bool(row[filter_name]) != (expected_boolean == "true"):
            return False
    if not _timestamp_in_bounds(
        cast(str | None, row["last_retrieval_attempt_at"]),
        filters.retrieval_from,
        filters.retrieval_to,
    ):
        return False
    return _timestamp_in_bounds(
        cast(str | None, row["last_refresh_attempt_at"]),
        filters.refresh_from,
        filters.refresh_to,
    )


def _timestamp_in_bounds(value: str | None, lower: str, upper: str) -> bool:
    if not lower and not upper:
        return True
    if value is None:
        return False
    if lower and value < lower:
        return False
    return not upper or value <= upper


def _compare_rows(
    left: Mapping[str, Any], right: Mapping[str, Any], filters: FacilityFilters
) -> int:
    key = filters.sort
    if key != "facility_id":
        primary = _compare_primary(left.get(key), right.get(key), filters.direction, key)
        if primary:
            return primary
    left_facility = _normalize_facility_id(_required_string(left, "facility_id"))
    right_facility = _normalize_facility_id(_required_string(right, "facility_id"))
    if left_facility != right_facility:
        return -1 if left_facility < right_facility else 1
    left_entry = _required_string(left, "facility_entry_id")
    right_entry = _required_string(right, "facility_entry_id")
    return (left_entry > right_entry) - (left_entry < right_entry)


def _compare_primary(left: Any, right: Any, direction: str, key: str) -> int:
    if key in TIMESTAMP_SORT_KEYS:
        if left is None and right is None:
            return 0
        if left is None:
            return 1
        if right is None:
            return -1
    left_value = str(left).casefold()
    right_value = str(right).casefold()
    comparison = (left_value > right_value) - (left_value < right_value)
    return comparison if direction == "asc" else -comparison


def _row_order_tuple(row: Mapping[str, Any], filters: FacilityFilters) -> list[Any]:
    primary: Any = None
    if filters.sort != "facility_id":
        primary = row.get(filters.sort)
    return [
        primary,
        _normalize_facility_id(_required_string(row, "facility_id")),
        _required_string(row, "facility_entry_id"),
    ]


def _find_anchor_index(
    rows: Sequence[Mapping[str, Any]], anchor: Sequence[Any], filters: FacilityFilters
) -> int:
    for index, row in enumerate(rows):
        if _row_order_tuple(row, filters) == list(anchor):
            return index
    raise ValueError("Facility cursor anchor is not available in the current result set.")


def _encode_cursor(
    report_id: str,
    filters: FacilityFilters,
    page_direction: str,
    anchor: Sequence[Any],
) -> str:
    payload = {
        "anchor": list(anchor),
        "direction": filters.direction,
        "filter_fingerprint": _filter_fingerprint(filters),
        "page_direction": page_direction,
        "report_id": report_id,
        "sort": filters.sort,
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(serialized).decode().rstrip("=")


def _decode_cursor(cursor: str) -> Mapping[str, Any]:
    try:
        padding = "=" * (-len(cursor) % 4)
        decoded = base64.urlsafe_b64decode(cursor + padding)
        loaded = json.loads(decoded)
    except (ValueError, json.JSONDecodeError) as error:
        raise ValueError("Facility cursor is invalid.") from error
    return _mapping(loaded, "facility cursor")


def _validate_cursor(
    cursor: Mapping[str, Any], report_id: str, filters: FacilityFilters
) -> None:
    if (
        cursor.get("report_id") != report_id
        or cursor.get("filter_fingerprint") != _filter_fingerprint(filters)
        or cursor.get("sort") != filters.sort
        or cursor.get("direction") != filters.direction
    ):
        raise ValueError("Facility cursor does not match the active report, filters, or sort.")


def _filter_fingerprint(filters: FacilityFilters) -> str:
    values = {
        key: value
        for key, value in vars(filters).items()
        if key not in {"cursor", "limit", "sort", "direction"}
    }
    serialized = json.dumps(values, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(serialized).hexdigest()


def _aggregate_csv_response(package: CoveragePackage) -> tuple[int, str, bytes]:
    if package.aggregate_csv is None:
        raise CoveragePackageError(
            "unavailable", "Aggregate coverage CSV is unavailable for this report."
        )
    return 200, "text/csv; charset=utf-8", package.aggregate_csv


def _facility_ids_csv_response(
    package: CoveragePackage, query: str
) -> tuple[int, str, bytes]:
    values = parse_qs(query, keep_blank_values=True)
    if set(values) != {"group"} or len(values.get("group", ())) != 1:
        raise ValueError("Exactly one Facility ID group is required.")
    group = values["group"][0]
    if group not in FACILITY_ID_GROUPS:
        raise ValueError("Unsupported Facility ID group.")
    facility_ids = sorted(
        {
            _required_string(row, "facility_id")
            for row in package.facility_rows
            if _row_in_group(row, group)
        },
        key=lambda value: (_normalize_facility_id(value), value),
    )
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("report_id", "group", "facility_id"))
    for facility_id in facility_ids:
        writer.writerow((package.report_id, group, facility_id))
    return 200, "text/csv; charset=utf-8", output.getvalue().encode("utf-8")


def _row_in_group(row: Mapping[str, Any], group: str) -> bool:
    return bool({
        "changed": row["change_outcome"] == "changed",
        "unchanged": row["change_outcome"] == "unchanged",
        "warning": row["processing_outcome"] == "warning",
        "failed": row["processing_outcome"] == "failed",
        "missing_artifact": row["preserved_artifact_state"] == "missing",
        "retry_eligible": row["retry_eligibility"] == "eligible",
    }[group])


def _render_summary_page(
    package: CoveragePackage,
    context: OperatorCoverageDashboardContext,
    authorization: AuthorizationDecision,
) -> str:
    report = package.report
    operations = _required_mapping(report, "operations")
    coverage = _required_mapping(report, "coverage")
    identity = _report_identity_markup(package, context)
    state_markup = _state_markup(package)
    coverage_rows = "\n".join(
        f"""<tr>
          <th scope="row">{_humanize(_required_string(_mapping(row, "stage row"), "field_id"))}</th>
          <td>{_humanize(_required_string(_mapping(row, "stage row"), "stage"))}</td>
          <td>{_nonnegative_int(_mapping(row, "stage row").get("eligible_count"), "eligible_count")}</td>
          <td>{_nonnegative_int(_mapping(row, "stage row").get("successful_count"), "successful_count")}</td>
          <td>{_nonnegative_int(_mapping(row, "stage row").get("blank_count"), "blank_count")}</td>
          <td>{_nonnegative_int(_mapping(row, "stage row").get("unavailable_count"), "unavailable_count")}</td>
          <td>{_nonnegative_int(_mapping(row, "stage row").get("failure_count"), "failure_count")}</td>
        </tr>"""
        for row in _coverage_stage_rows(coverage)
    )
    terminal_rows = _count_map_rows(
        _required_mapping(coverage, "terminal_classification_counts")
    )
    operation_sections = "\n".join(
        _count_table(field, _required_mapping(operations, field))
        for field in (
            "refresh_state_counts",
            "processing_outcome_counts",
            "change_outcome_counts",
            "retrieval_state_counts",
            "import_state_counts",
            "preserved_artifact_state_counts",
            "hash_validation_state_counts",
            "retry_eligibility_counts",
            "job_state_counts",
        )
        if field in operations
    )
    release_status = _release_assessment_status(report)
    reconciliation_status = _reconciliation_status(report)
    source_rows = "\n".join(
        _source_snapshot_row(_mapping(item, "source snapshot"))
        for item in _required_list(package.manifest, "source_snapshots")
    )
    retention = _required_mapping(package.manifest, "retention")
    previous_markup = _previous_accepted_markup(package)
    main = f"""
    {identity}
    {state_markup}
    {previous_markup}
    <nav class="operator-subnav evidence-controls" aria-label="Operator coverage views">
      <a aria-current="page" href="{OPERATOR_COVERAGE_SUMMARY_PATH}">Summary</a>
      <a href="{OPERATOR_COVERAGE_FACILITIES_PATH}">Facilities</a>
      <a href="{OPERATOR_COVERAGE_JOBS_PATH}">Jobs</a>
    </nav>
    <section class="operator-section" aria-labelledby="coverage-heading">
      <div class="section-heading-row">
        <div><p class="section-kicker">Source-to-screen</p><h2 id="coverage-heading">Coverage through reviewer surfaces</h2></div>
        <span class="{_status_class(release_status)}">Release assessment: {_humanize(release_status)}</span>
      </div>
      <p>Coverage reports whether governed fields moved through each named stage. It does not describe whether a refresh job ran successfully.</p>
      <div class="operator-table-wrap">
        <table>
          <caption>Producer-supplied source-to-screen stage counts</caption>
          <thead><tr><th scope="col">Field</th><th scope="col">Stage</th><th scope="col">Eligible</th><th scope="col">Successful</th><th scope="col">Blank</th><th scope="col">Unavailable</th><th scope="col">Failed</th></tr></thead>
          <tbody>{coverage_rows}</tbody>
        </table>
      </div>
      <div class="operator-table-wrap">
        <table>
          <caption>Terminal coverage classifications</caption>
          <thead><tr><th scope="col">Classification</th><th scope="col">Count</th></tr></thead>
          <tbody>{terminal_rows}</tbody>
        </table>
      </div>
    </section>
    <section class="operator-section" aria-labelledby="operations-heading">
      <div class="section-heading-row">
        <div><p class="section-kicker">Operations</p><h2 id="operations-heading">Retrieval, import, artifacts, checkpoints, and jobs</h2></div>
        <span class="{_status_class(reconciliation_status)}">Reconciliation: {_humanize(reconciliation_status)}</span>
      </div>
      <p>Operational status reports recorded processing facts. A successful operation does not prove correct rendering, and a coverage gap does not prove an operational failure.</p>
      <dl class="operator-facts">
        <dt>Existing facilities</dt><dd>{_nonnegative_int(operations.get('existing_facility_total'), 'existing_facility_total')}</dd>
        <dt>Eligible facilities</dt><dd>{_nonnegative_int(operations.get('eligible_facility_total'), 'eligible_facility_total')}</dd>
        <dt>Preserved-artifact facilities</dt><dd>{_nonnegative_int(operations.get('preserved_artifact_facility_total'), 'preserved_artifact_facility_total')}</dd>
        <dt>Governed conflicts</dt><dd>{_nonnegative_int(operations.get('governed_conflict_facility_total'), 'governed_conflict_facility_total')}</dd>
        <dt>Operator intervention required</dt><dd>{_nonnegative_int(operations.get('operator_intervention_required_total'), 'operator_intervention_required_total')}</dd>
      </dl>
      <div class="operator-count-grid">{operation_sections}</div>
    </section>
    <section class="operator-section" aria-labelledby="source-selection-heading">
      <h2 id="source-selection-heading">Source selection and evaluation limits</h2>
      <p>Seven existing program-specific sources remain retained for the evaluated scope. Every statewide candidate remains inactive. No statewide completeness baseline or refresh cadence is approved, and raw value <code>733</code> has no approved facility-type mapping.</p>
      <div class="operator-table-wrap"><table><caption>Safe source snapshot metadata</caption><thead><tr><th scope="col">Source family</th><th scope="col">Selection state</th><th scope="col">Observed</th><th scope="col">Rows</th><th scope="col">Cadence</th></tr></thead><tbody>{source_rows}</tbody></table></div>
    </section>
    <section class="operator-section" aria-labelledby="downloads-heading">
      <h2 id="downloads-heading">Read-only downloads</h2>
      <p>Downloads contain aggregate contract rows or one explicit Facility ID group. They do not contain actions, source bodies, paths, URLs, raw hashes, error messages, or authentication data.</p>
      <div class="evidence-controls action-group" aria-label="Coverage downloads">
        <a class="button" href="{OPERATOR_COVERAGE_EXPORT_PATH}">Download aggregate coverage CSV</a>
        <a class="button button-secondary" href="{OPERATOR_COVERAGE_FACILITY_IDS_PATH}?group=changed">Download changed Facility IDs</a>
        <a class="button button-secondary" href="{OPERATOR_COVERAGE_FACILITY_IDS_PATH}?group=failed">Download failed Facility IDs</a>
      </div>
    </section>
    <section class="operator-section" aria-labelledby="retention-heading">
      <h2 id="retention-heading">Retention and provenance</h2>
      <dl class="operator-facts"><dt>Disposition</dt><dd>{html.escape(_humanize(_required_string(retention, 'disposition')))}</dd><dt>Policy</dt><dd>{html.escape(str(retention.get('policy_id') or 'Pending policy'))}</dd><dt>Automated cleanup</dt><dd>Not authorized</dd></dl>
    </section>
    <p class="operator-boundary">Read-only phase: no retry, dry-run submission, apply, confirmation, cancel, resume, backfill, retrieval, import, job creation, checkpoint update, database write, or artifact mutation is available.</p>
    <span class="visually-hidden">Authorization permission: {html.escape(authorization.permission)}</span>
    """
    return _render_page("Operator source coverage", "Operator source coverage", main, context)


def _render_facilities_page(
    package: CoveragePackage,
    context: OperatorCoverageDashboardContext,
    filters: FacilityFilters,
    page: FacilityPage,
) -> str:
    rows = "\n".join(_facility_row(row) for row in page.rows)
    if not rows:
        rows = '<tr><td colspan="8">No facilities match the active filters. Clear filters to return to all authorized fixture facilities.</td></tr>'
    active_filters = _active_filter_text(filters)
    pagination = _pagination_markup(filters, page)
    layout_options = sorted(
        {
            _required_string(row, "source_layout_classification")
            for row in package.facility_rows
        }
    )
    main = f"""
    {_report_identity_markup(package, context)}
    <nav class="operator-subnav evidence-controls" aria-label="Operator coverage views"><a href="{OPERATOR_COVERAGE_SUMMARY_PATH}">Summary</a><a aria-current="page" href="{OPERATOR_COVERAGE_FACILITIES_PATH}">Facilities</a><a href="{OPERATOR_COVERAGE_JOBS_PATH}">Jobs</a></nav>
    <section class="operator-section evidence-controls" aria-labelledby="facility-filter-heading">
      <h2 id="facility-filter-heading">Filter authorized facility metadata</h2>
      <form class="operator-filter-grid" action="{OPERATOR_COVERAGE_FACILITIES_PATH}" method="get">
        {_text_input('facility_id', 'Exact Facility ID', filters.facility_id)}
        {_text_input('q', 'Facility ID contains', filters.query)}
        {_select_input('processing_outcome', 'Processing outcome', PROCESSING_OUTCOMES, filters.processing_outcome)}
        {_select_input('change_outcome', 'Change outcome', CHANGE_OUTCOMES, filters.change_outcome)}
        {_select_input('refresh_state', 'Refresh state', REFRESH_STATES, filters.refresh_state)}
        {_select_input('refresh_eligibility', 'Refresh eligibility', REFRESH_ELIGIBILITY, filters.refresh_eligibility)}
        {_select_input('hash_validation_state', 'Hash validation', HASH_VALIDATION_STATES, filters.hash_validation_state)}
        {_select_input('source_layout_classification', 'Source layout', layout_options, filters.source_layout_classification)}
        {_select_input('operational_failure_category', 'Failure category', FAILURE_CATEGORIES, filters.operational_failure_category)}
        {_select_input('operator_intervention_required', 'Operator intervention', ('true', 'false'), filters.operator_intervention_required)}
        {_select_input('governed_conflict', 'Governed conflict', ('true', 'false'), filters.governed_conflict)}
        {_text_input('retrieval_from', 'Retrieval from (UTC)', filters.retrieval_from)}
        {_text_input('retrieval_to', 'Retrieval to (UTC)', filters.retrieval_to)}
        {_text_input('refresh_from', 'Refresh from (UTC)', filters.refresh_from)}
        {_text_input('refresh_to', 'Refresh to (UTC)', filters.refresh_to)}
        {_select_input('sort', 'Sort by', FACILITY_SORT_KEYS, filters.sort, include_all=False)}
        {_select_input('direction', 'Sort direction', ('asc', 'desc'), filters.direction, include_all=False)}
        {_select_input('limit', 'Rows per page', ('25', '50', '100'), str(filters.limit), include_all=False)}
        <div class="operator-filter-actions"><button type="submit">Apply filters</button><a href="{OPERATOR_COVERAGE_FACILITIES_PATH}">Clear filters</a></div>
      </form>
    </section>
    <section class="operator-section" aria-labelledby="facility-results-heading">
      <div class="section-heading-row"><div><p class="section-kicker">Authorized operator index</p><h2 id="facility-results-heading">Facility coverage details</h2></div><p class="result-position">Showing {page.start}–{page.end} of {page.total} facilities</p></div>
      <p><strong>Active filters:</strong> {html.escape(active_filters)}</p>
      {pagination}
      <div class="operator-table-wrap"><table><caption>Safe facility metadata for the active report and authorized scope</caption><thead><tr><th scope="col">Facility ID</th><th scope="col">Processing</th><th scope="col">Change</th><th scope="col">Refresh</th><th scope="col">Artifact / hash</th><th scope="col">Layout</th><th scope="col">Failure</th><th scope="col">Intervention</th></tr></thead><tbody>{rows}</tbody></table></div>
      {pagination}
    </section>
    <p class="operator-boundary">This page filters producer-supplied safe index values. It does not recount coverage or execute retry, apply, cancel, resume, import, backfill, retrieval, or database work.</p>
    """
    return _render_page("Facility source coverage", "Facility source coverage", main, context)


def _render_jobs_page(
    package: CoveragePackage, context: OperatorCoverageDashboardContext
) -> str:
    rows = "\n".join(_job_row(row) for row in sorted(package.job_rows, key=lambda row: _required_string(row, "job_id")))
    if not rows:
        rows = '<tr><td colspan="8">No safe job metadata is available for this report.</td></tr>'
    main = f"""
    {_report_identity_markup(package, context)}
    {_previous_accepted_markup(package)}
    <nav class="operator-subnav evidence-controls" aria-label="Operator coverage views"><a href="{OPERATOR_COVERAGE_SUMMARY_PATH}">Summary</a><a href="{OPERATOR_COVERAGE_FACILITIES_PATH}">Facilities</a><a aria-current="page" href="{OPERATOR_COVERAGE_JOBS_PATH}">Jobs</a></nav>
    <section class="operator-section" aria-labelledby="job-results-heading">
      <div class="section-heading-row"><div><p class="section-kicker">Recorded facts only</p><h2 id="job-results-heading">Refresh job metadata</h2></div></div>
      <p>Execution mode and checkpoint state are descriptive facts from the validated package. No job action is available on this page.</p>
      <div class="operator-table-wrap"><table><caption>Safe job metadata for the active report</caption><thead><tr><th scope="col">Job ID</th><th scope="col">State</th><th scope="col">Mode</th><th scope="col">Checkpoint</th><th scope="col">Processed / selected</th><th scope="col">Changed / unchanged</th><th scope="col">Warnings / failed</th><th scope="col">Failure / intervention</th></tr></thead><tbody>{rows}</tbody></table></div>
    </section>
    <p class="operator-boundary">No retry, dry-run start, apply, confirmation, cancel, resume, job creation, checkpoint update, or database mutation is implemented.</p>
    """
    return _render_page("Coverage job status", "Coverage job status", main, context)


def _report_identity_markup(
    package: CoveragePackage, context: OperatorCoverageDashboardContext
) -> str:
    report = package.report
    manifest = package.manifest
    fixture = (
        f'<span class="ds-badge ds-badge--info">{FIXTURE_LABEL}</span>'
        if context.fixture_mode
        else ""
    )
    return f"""
    <section class="operator-identity" aria-labelledby="report-identity-heading">
      <div class="section-heading-row"><div><p class="section-kicker">Authenticated operator diagnostics</p><h2 id="report-identity-heading">Validated coverage report</h2></div>{fixture}</div>
      <dl class="operator-facts">
        <dt>Report ID</dt><dd><code>{html.escape(package.report_id)}</code></dd>
        <dt>Contract</dt><dd>{html.escape(_required_string(manifest, 'contract_version'))} ({CONTRACT_COMPATIBILITY})</dd>
        <dt>Evaluation</dt><dd>{html.escape(_required_string(manifest, 'evaluation_id'))}</dd>
        <dt>Criteria set</dt><dd>{html.escape(_required_string(manifest, 'criteria_set_id'))}</dd>
        <dt>Scope</dt><dd>{html.escape(_required_string(manifest, 'scope_id'))}</dd>
        <dt>Generated at (UTC)</dt><dd>{html.escape(_required_string(report, 'generated_at'))}</dd>
      </dl>
    </section>
    """


def _state_markup(package: CoveragePackage) -> str:
    if package.state == "available":
        existing_total = _nonnegative_int(
            _required_mapping(package.report, "operations").get(
                "existing_facility_total"
            ),
            "existing_facility_total",
        )
        if existing_total == 0:
            return '<p class="state-banner state-banner--success"><strong>Verified empty coverage report.</strong> Producer aggregates and available indexes reconcile to zero; unavailable data is not represented as zero.</p>'
        return '<p class="state-banner state-banner--success"><strong>Coverage report available.</strong> All displayed dimensions passed contract, hash, and reconciliation validation.</p>'
    unavailable = ", ".join(_humanize(value) for value in package.unavailable_dimensions)
    return f'<p class="state-banner state-banner--attention"><strong>Partial coverage.</strong> Unavailable dimensions: {html.escape(unavailable)}. Missing values are unavailable, not zero.</p>'


def _previous_accepted_markup(package: CoveragePackage) -> str:
    retention = _required_mapping(package.manifest, "retention")
    previous = retention.get("previous_accepted_report_id")
    active_jobs = [
        row for row in package.job_rows if bool(row.get("previous_accepted_dataset_active"))
    ]
    if previous is None or not active_jobs:
        return ""
    last_success = next(
        (
            row.get("last_successful_refresh_at")
            for row in active_jobs
            if row.get("last_successful_refresh_at") is not None
        ),
        None,
    )
    return f"""<p class="state-banner state-banner--attention"><strong>Previous accepted report remains active.</strong> Current processing is not labeled successful or current. Previous report: <code>{html.escape(str(previous))}</code>. Last successful refresh: {html.escape(str(last_success or 'Unavailable'))}.</p>"""


def _facility_row(row: Mapping[str, Any]) -> str:
    return f"""<tr>
      <th scope="row"><code>{html.escape(_required_string(row, 'facility_id'))}</code></th>
      <td><span class="{_status_class(_required_string(row, 'processing_outcome'))}">{html.escape(_humanize(_required_string(row, 'processing_outcome')))}</span></td>
      <td>{html.escape(_humanize(_required_string(row, 'change_outcome')))}</td>
      <td>{html.escape(_humanize(_required_string(row, 'refresh_state')))}<br><small>{html.escape(_humanize(_required_string(row, 'refresh_eligibility')))}</small></td>
      <td>{html.escape(_humanize(_required_string(row, 'preserved_artifact_state')))} / {html.escape(_humanize(_required_string(row, 'hash_validation_state')))}</td>
      <td><code>{html.escape(_required_string(row, 'source_layout_classification'))}</code></td>
      <td>{html.escape(_humanize(_required_string(row, 'operational_failure_category')))}</td>
      <td>{'Required' if bool(row['operator_intervention_required']) else 'Not required'}<br><small>Retry: {html.escape(_humanize(_required_string(row, 'retry_eligibility')))}</small></td>
    </tr>"""


def _job_row(row: Mapping[str, Any]) -> str:
    checkpoint = _humanize(_required_string(row, "checkpoint_state"))
    checkpoint_identity = row.get("checkpoint_identity", row.get("checkpoint_id"))
    if checkpoint_identity:
        checkpoint = f"{checkpoint} ({checkpoint_identity})"
    return f"""<tr>
      <th scope="row"><code>{html.escape(_required_string(row, 'job_id'))}</code></th>
      <td><span class="{_status_class(_required_string(row, 'job_state'))}">{html.escape(_humanize(_required_string(row, 'job_state')))}</span></td>
      <td>{html.escape(_humanize(_required_string(row, 'execution_mode')))}</td>
      <td>{html.escape(checkpoint)}</td>
      <td>{_nonnegative_int(row.get('processed_count'), 'processed_count')} / {_nonnegative_int(row.get('selected_count'), 'selected_count')}</td>
      <td>{_nonnegative_int(row.get('changed_count'), 'changed_count')} / {_nonnegative_int(row.get('unchanged_count'), 'unchanged_count')}</td>
      <td>{_nonnegative_int(row.get('warning_count'), 'warning_count')} / {_nonnegative_int(row.get('failed_count'), 'failed_count')}</td>
      <td>{html.escape(_humanize(_required_string(row, 'operational_failure_category')))}<br><small>{'Intervention required' if bool(row['operator_intervention_required']) else 'No intervention required'}</small></td>
    </tr>"""


def _source_snapshot_row(snapshot: Mapping[str, Any]) -> str:
    return f"""<tr><th scope="row"><code>{html.escape(_required_string(snapshot, 'source_family_id'))}</code></th><td>{html.escape(_humanize(_required_string(snapshot, 'selection_state')))}</td><td>{html.escape(str(snapshot.get('observed_at') or 'Unavailable'))}</td><td>{html.escape(str(snapshot.get('row_count') if snapshot.get('row_count') is not None else 'Unavailable'))}</td><td>{html.escape(_humanize(_required_string(snapshot, 'cadence_status')))}</td></tr>"""


def _count_table(field: str, values: Mapping[str, Any]) -> str:
    return f"""<div class="operator-count-table"><h3>{html.escape(_humanize(field.removesuffix('_counts')))}</h3><table><caption>{html.escape(_humanize(field))}</caption><thead><tr><th scope="col">State</th><th scope="col">Count</th></tr></thead><tbody>{_count_map_rows(values)}</tbody></table></div>"""


def _count_map_rows(values: Mapping[str, Any]) -> str:
    return "\n".join(
        f'<tr><th scope="row">{html.escape(_humanize(key))}</th><td>{_nonnegative_int(value, key)}</td></tr>'
        for key, value in values.items()
    )


def _coverage_stage_rows(coverage: Mapping[str, Any]) -> list[Any]:
    field = (
        "field_stage_coverage"
        if "field_stage_coverage" in coverage
        else "stage_rows"
    )
    return _required_list(coverage, field)


def _release_assessment_status(report: Mapping[str, Any]) -> str:
    assessment = report.get("release_assessment")
    if isinstance(assessment, Mapping):
        return _required_string(assessment, "status")
    return _required_string(report, "release_assessment")


def _reconciliation_status(report: Mapping[str, Any]) -> str:
    reconciliation = report.get("reconciliation")
    if isinstance(reconciliation, Mapping):
        return _required_string(reconciliation, "reconciliation_status")
    return _required_string(report, "reconciliation_status")


def _pagination_markup(filters: FacilityFilters, page: FacilityPage) -> str:
    previous = _pagination_control("Previous facilities", filters, page.previous_cursor)
    next_link = _pagination_control("Next facilities", filters, page.next_cursor)
    return f'<nav class="facility-pagination evidence-controls" aria-label="Facility result pages">{previous}<span class="result-position">Showing {page.start}–{page.end} of {page.total} facilities</span>{next_link}</nav>'


def _pagination_control(label: str, filters: FacilityFilters, cursor: str | None) -> str:
    if cursor is None:
        return f'<span class="facility-pagination__control is-disabled" aria-disabled="true">{html.escape(label)}</span>'
    query = _filters_query(filters, cursor=cursor)
    return f'<a class="facility-pagination__control button button-secondary" aria-label="{html.escape(label)}" href="{OPERATOR_COVERAGE_FACILITIES_PATH}?{html.escape(query, quote=True)}">{html.escape(label)}</a>'


def _filters_query(filters: FacilityFilters, *, cursor: str | None = None) -> str:
    values: dict[str, str] = {}
    for key, value in vars(filters).items():
        if key == "cursor":
            continue
        if value not in {"", DEFAULT_PAGE_SIZE, "facility_id", "asc"}:
            values[key] = str(value)
    if cursor:
        values["cursor"] = cursor
    return urlencode(values)


def _active_filter_text(filters: FacilityFilters) -> str:
    values = [
        f"{_humanize(key)} = {value}"
        for key, value in vars(filters).items()
        if key not in {"cursor", "limit", "sort", "direction"} and value
    ]
    if not values:
        return "None"
    return "; ".join(values)


def _text_input(name: str, label: str, value: str) -> str:
    return f'<p><label for="filter-{html.escape(name)}">{html.escape(label)}</label><input id="filter-{html.escape(name)}" name="{html.escape(name)}" value="{html.escape(value, quote=True)}"></p>'


def _select_input(
    name: str,
    label: str,
    options: Iterable[str],
    selected: str,
    *,
    include_all: bool = True,
) -> str:
    option_rows: list[str] = []
    if include_all:
        option_rows.append('<option value="">All</option>')
    for option in sorted(options):
        selected_attr = " selected" if option == selected else ""
        option_rows.append(
            f'<option value="{html.escape(option, quote=True)}"{selected_attr}>{html.escape(_humanize(option))}</option>'
        )
    return f'<p><label for="filter-{html.escape(name)}">{html.escape(label)}</label><select id="filter-{html.escape(name)}" name="{html.escape(name)}">{"".join(option_rows)}</select></p>'


def _render_page(title: str, heading: str, main: str, context: OperatorCoverageDashboardContext) -> str:
    rendered = render_page_shell(
        title=title,
        heading=heading,
        main=main,
        skip_label="Skip to operator coverage content",
        active_path=OPERATOR_COVERAGE_SUMMARY_PATH,
        mode_label=FIXTURE_LABEL if context.fixture_mode else "Operator diagnostics",
        show_operator_navigation=True,
    )
    return rendered.replace("</head>", f"  <style>\n{_OPERATOR_CSS}\n  </style>\n</head>", 1)


def _package_error_response(
    error: CoveragePackageError,
    context: OperatorCoverageDashboardContext,
    path: str,
) -> tuple[int, str, bytes]:
    if path in {OPERATOR_COVERAGE_EXPORT_PATH, OPERATOR_COVERAGE_FACILITY_IDS_PATH}:
        status = _package_error_status(error.state)
        return status, "text/plain; charset=utf-8", str(error).encode("utf-8")
    heading = {
        "unavailable": "Coverage report unavailable",
        "version_mismatch": "Coverage report version is not supported",
        "hash_failed": "Coverage report hash validation failed",
        "reconciliation_failed": "Coverage report reconciliation failed",
        "partial": "Partial coverage report",
        "available": "Coverage report unavailable",
    }[error.state]
    fixture = (
        f'<p><span class="ds-badge ds-badge--info">{FIXTURE_LABEL}</span></p>'
        if context.fixture_mode
        else ""
    )
    main = f"""
    {fixture}
    <p class="state-banner state-banner--danger"><strong>{html.escape(heading)}.</strong> {html.escape(str(error))}</p>
    <p>No package counts, Facility IDs, job rows, hashes, or stale values were serialized.</p>
    <p>Check the configured contract package, supported contract version, artifact hashes, and producer reconciliation before trying again.</p>
    <p class="operator-boundary">This state performs no retry, apply, cancel, resume, retrieval, import, backfill, job creation, checkpoint update, database write, or artifact mutation.</p>
    """
    return _html_response(
        _package_error_status(error.state),
        _render_page(heading, heading, main, context),
    )


def _package_error_status(state: PackageState) -> int:
    return {
        "available": 503,
        "partial": 503,
        "unavailable": 503,
        "version_mismatch": 409,
        "hash_failed": 422,
        "reconciliation_failed": 422,
    }[state]


def _message_response(status: int, heading: str, message: str) -> tuple[int, str, bytes]:
    context = OperatorCoverageDashboardContext(None, DEFAULT_SCOPE, None)
    main = f'<p class="state-banner state-banner--danger"><strong>{html.escape(heading)}.</strong> {html.escape(message)}</p><p>No coverage package data was read or serialized.</p>'
    return _html_response(status, _render_page(heading, heading, main, context))


def _html_response(status: int, body: str) -> tuple[int, str, bytes]:
    return status, "text/html; charset=utf-8", body.encode("utf-8")


def _status_class(value: str) -> str:
    if value in {"passed", "successful", "completed"}:
        return "ds-badge ds-badge--success"
    if value in {"failed", "hash_validation_failed", "reconciliation_failed"}:
        return "ds-badge ds-badge--danger"
    if value in {"warning", "interrupted", "completed_with_warnings", "reviewed_exception_required"}:
        return "ds-badge ds-badge--attention"
    return "ds-badge ds-badge--muted"


def _humanize(value: str) -> str:
    return value.replace("_", " ").replace(".", " ").strip().capitalize()


def _normalize_facility_id(value: str) -> str:
    return "".join(character for character in value.casefold().strip() if character.isalnum())


def _expected_facility_entry_id(source_family_id: str, facility_id: str) -> str:
    identity = {
        "facility_id": _normalize_facility_id(facility_id),
        "source_family_id": source_family_id,
    }
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return f"facility-v1-{hashlib.sha256(canonical).hexdigest()}"


def _validate_enum(row: Mapping[str, Any], field: str, allowed: frozenset[str]) -> None:
    if _required_string(row, field) not in allowed:
        raise CoveragePackageError("unavailable", f"{field} has an invalid closed enum value.")


def _validate_stable_id(value: str, label: str) -> None:
    if not STABLE_ID_RE.fullmatch(value):
        raise CoveragePackageError("unavailable", f"{label} is not a safe stable identifier.")


def _validate_timestamp(value: str, label: str) -> None:
    if not UTC_TIMESTAMP_RE.fullmatch(value):
        raise CoveragePackageError("unavailable", f"{label} must be a UTC timestamp with Z.")


def _load_json_object(path: Path, label: str) -> Mapping[str, Any]:
    return _json_object_from_bytes(path.read_bytes(), label)


def _json_object_from_bytes(data: bytes, label: str) -> Mapping[str, Any]:
    text = _utf8_text(data, label)
    if "\r" in text or text.startswith("\ufeff"):
        raise CoveragePackageError("unavailable", f"{label.title()} serialization is invalid.")
    try:
        loaded = json.loads(text, parse_constant=_reject_nonfinite_json)
    except (json.JSONDecodeError, ValueError) as error:
        raise CoveragePackageError("unavailable", f"{label.title()} is invalid JSON.") from error
    return _mapping(loaded, label)


def _reject_nonfinite_json(value: str) -> float:
    raise ValueError(f"Non-finite JSON value {value} is not permitted.")


def _utf8_text(data: bytes, label: str) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise CoveragePackageError("unavailable", f"{label.title()} is not UTF-8.") from error


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise CoveragePackageError("unavailable", f"{label.title()} must be an object.")
    return cast(Mapping[str, Any], value)


def _required_mapping(row: Mapping[str, Any], field: str) -> Mapping[str, Any]:
    if field not in row:
        raise CoveragePackageError("unavailable", f"Required field {field} is missing.")
    return _mapping(row[field], field)


def _required_list(row: Mapping[str, Any], field: str) -> list[Any]:
    value = row.get(field)
    if not isinstance(value, list):
        raise CoveragePackageError("unavailable", f"Required field {field} must be an array.")
    return value


def _required_string(row: Mapping[str, Any], field: str) -> str:
    if field not in row:
        raise CoveragePackageError("unavailable", f"Required field {field} is missing.")
    return _string(row[field], field)


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise CoveragePackageError("unavailable", f"{label} must be a non-empty string.")
    return value


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or not all(isinstance(item, str) for item in value):
        raise CoveragePackageError("unavailable", "Unavailable dimensions are invalid.")
    return tuple(cast(Sequence[str], value))


def _nonnegative_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise CoveragePackageError("unavailable", f"{label} must be a nonnegative integer.")
    return value


def _reject_multiple_values(values: Mapping[str, list[str]]) -> None:
    if any(len(items) != 1 for items in values.values()):
        raise ValueError("Each facility filter may be supplied at most once.")


def _query_value(values: Mapping[str, list[str]], name: str) -> str:
    return values.get(name, [""])[0].strip()


def _query_int(values: Mapping[str, list[str]], name: str, default: int) -> int:
    raw = _query_value(values, name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer.") from error


def _validated_query_enum(
    values: Mapping[str, list[str]], name: str, allowed: Iterable[str]
) -> str:
    value = _query_value(values, name)
    if value and value not in set(allowed):
        raise ValueError(f"Unsupported {name} filter.")
    return value


def _validated_boolean_filter(values: Mapping[str, list[str]], name: str) -> str:
    return _validated_query_enum(values, name, {"true", "false"})


def _validated_optional_timestamp_bound(
    values: Mapping[str, list[str]], name: str
) -> str:
    value = _query_value(values, name)
    if value:
        _validate_timestamp(value, name)
    return value


_OPERATOR_CSS = r"""
  .operator-identity,
  .operator-section {
    background: var(--surface);
    border: 1px solid var(--line-soft);
    border-radius: 4px;
    margin-bottom: 1rem;
    padding: 1rem;
  }
  .operator-section h2,
  .operator-identity h2 { margin-bottom: 0.35rem; }
  .section-kicker {
    color: var(--muted);
    font-size: 0.78rem;
    font-weight: 850;
    letter-spacing: 0.08em;
    margin-bottom: 0.2rem;
    text-transform: uppercase;
  }
  .section-heading-row {
    align-items: flex-start;
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem 1rem;
    justify-content: space-between;
  }
  .section-heading-row .ds-badge {
    max-width: 100%;
    overflow-wrap: anywhere;
    white-space: normal;
  }
  .operator-facts {
    grid-template-columns: minmax(11rem, 17rem) minmax(0, 1fr);
  }
  .operator-facts dd,
  .operator-facts code { overflow-wrap: anywhere; }
  .operator-subnav {
    border-bottom: 1px solid var(--line);
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem 1rem;
    margin: 0 0 1rem;
    padding: 0 0 0.65rem;
  }
  .operator-subnav a[aria-current="page"] {
    border-bottom: 3px solid var(--ds-nav-active-border);
    color: var(--ds-primary);
  }
  .state-banner {
    border: 1px solid var(--line);
    border-left-width: 5px;
    margin-bottom: 1rem;
    padding: 0.75rem 0.9rem;
  }
  .state-banner--success { background: var(--ds-surface-success); border-left-color: var(--ds-success); }
  .state-banner--attention { background: var(--ds-attention-soft); border-left-color: var(--ds-attention); }
  .state-banner--danger { background: var(--ds-danger-soft); border-left-color: var(--ds-danger); }
  .operator-count-grid {
    display: grid;
    gap: 0.8rem;
    grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr));
  }
  .operator-count-table {
    border-top: 2px solid var(--ds-primary);
    min-width: 0;
    padding-top: 0.45rem;
  }
  .operator-count-table table { font-size: 0.9rem; }
  .operator-table-wrap { max-width: 100%; overflow-x: auto; }
  .operator-table-wrap + .operator-table-wrap { margin-top: 1rem; }
  .operator-filter-grid {
    display: grid;
    gap: 0.7rem;
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  .operator-filter-grid p { margin: 0; min-width: 0; }
  .operator-filter-grid label { display: block; font-weight: 750; margin-bottom: 0.2rem; }
  .operator-filter-grid input,
  .operator-filter-grid select { box-sizing: border-box; max-width: 100%; width: 100%; }
  .operator-filter-actions { align-items: center; display: flex; flex-wrap: wrap; gap: 0.6rem; }
  .facility-pagination {
    align-items: center;
    display: flex;
    flex-wrap: wrap;
    gap: 0.65rem;
    justify-content: space-between;
    margin: 0.75rem 0;
  }
  .facility-pagination__control.is-disabled {
    border: 1px solid var(--line);
    color: var(--muted);
    cursor: not-allowed;
    padding: 0.55rem 0.8rem;
  }
  .result-position { font-weight: 750; margin: 0; }
  .operator-boundary {
    border-top: 1px solid var(--line);
    color: var(--muted);
    font-size: 0.9rem;
    padding-top: 0.75rem;
  }
  @media (max-width: 900px) {
    .operator-filter-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  }
  @media (max-width: 600px) {
    .operator-filter-grid { grid-template-columns: minmax(0, 1fr); }
    .operator-facts { display: block; }
    .operator-facts dt { margin-top: 0.55rem; }
    .operator-table-wrap table,
    .operator-table-wrap thead,
    .operator-table-wrap tbody,
    .operator-table-wrap tr,
    .operator-table-wrap th,
    .operator-table-wrap td { display: block; }
    .operator-table-wrap thead { position: absolute; left: -10000px; }
    .operator-table-wrap tr { border: 1px solid var(--line); margin-bottom: 0.7rem; }
    .operator-table-wrap th,
    .operator-table-wrap td { border: 0; border-bottom: 1px solid var(--line-soft); overflow-wrap: anywhere; }
    .operator-table-wrap th:last-child,
    .operator-table-wrap td:last-child { border-bottom: 0; }
    .facility-pagination { align-items: stretch; display: grid; }
    .facility-pagination__control { text-align: center; }
  }
  @media print {
    .evidence-controls { display: none !important; }
    .operator-identity,
    .operator-section,
    .state-banner { background: #fff !important; border-color: #000 !important; box-shadow: none !important; }
    .operator-table-wrap { overflow: visible; }
    table, th, td { border-color: #000 !important; color: #000 !important; }
    .ds-badge { background: #fff !important; border-color: #000 !important; color: #000 !important; }
  }
""".strip()
