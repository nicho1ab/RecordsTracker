from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import sqlite3
import sys
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Literal, cast

from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate as jsonschema_validate
from sqlalchemy import (
    MetaData,
    String,
    Table,
    case,
    create_engine,
    false,
    func,
    inspect,
    select,
    text,
)
from sqlalchemy import cast as sql_cast
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import SQLAlchemyError

from ccld_complaints.hosted_app.persistence import (
    HostedDatabaseConfigError,
    load_hosted_database_config,
)
from ccld_complaints.source_to_screen_catalog import (
    AGGREGATE_FEATURES,
    GAP_CLASSIFICATIONS,
    QUERY_COVERAGE_GAPS,
    ElementSpec,
    discover_element_specs,
    safe_facility_source_header,
)

AuditMode = Literal["local", "runtime"]

AUDIT_SCHEMA_VERSION = 1
COVERAGE_CONTRACT_VERSION = "1.0.0"
COVERAGE_MINIMUM_CONSUMER_VERSION = "1.0.0"
COVERAGE_PRODUCER_SCHEMA_ID = "issues-453-477-coverage-report-v1"
COVERAGE_PRODUCER_VERSION = "source-to-screen-audit-v1"
COVERAGE_SCHEMA_PATH = Path("schemas/issues-453-477-coverage-report-v1.schema.json")
COVERAGE_STAGES = (
    "source_presence",
    "extraction",
    "normalization",
    "canonical_allocation",
    "postgresql_population",
    "read_model_exposure",
    "complaint_page_rendering",
    "facility_hub_rendering",
)
COVERAGE_STAGE_STATES = (
    "successful",
    "blank",
    "absent",
    "unavailable",
    "unsupported",
    "conflict",
    "failure",
    "skipped",
)
COVERAGE_TERMINAL_CLASSIFICATIONS = (
    "present_and_populated",
    "present_but_not_extracted",
    "extracted_but_not_allocated",
    "allocated_but_not_imported",
    "stored_but_not_read",
    "read_but_not_rendered",
    "rendered_incorrectly",
    "present_blank",
    "source_label_absent",
    "source_artifact_unavailable",
    "unsupported_layout",
    "conflicting_sources",
    "intentionally_internal",
    "not_applicable",
)
COVERAGE_REFRESH_STATES = (
    "not_started",
    "eligible",
    "in_progress",
    "completed",
    "completed_with_warnings",
    "failed",
    "unavailable",
)
COVERAGE_PROCESSING_OUTCOMES = (
    "successful",
    "skipped",
    "warning",
    "failed",
    "not_yet_processed",
)
COVERAGE_CHANGE_OUTCOMES = ("changed", "unchanged", "not_evaluated")
COVERAGE_RETRIEVAL_STATES = (
    "not_attempted",
    "successful",
    "warning",
    "failed",
    "unavailable",
)
COVERAGE_IMPORT_STATES = (
    "not_attempted",
    "successful",
    "skipped",
    "failed",
    "unavailable",
)
COVERAGE_PRESERVED_ARTIFACT_STATES = (
    "preserved",
    "missing",
    "unavailable",
    "not_applicable",
)
COVERAGE_HASH_VALIDATION_STATES = (
    "valid",
    "failed",
    "not_checked",
    "unavailable",
    "not_applicable",
)
COVERAGE_JOB_STATES = ("queued", "active", "completed", "interrupted", "failed")
COVERAGE_OPERATIONAL_FAILURE_CATEGORIES = (
    "none",
    "retrieval_failed",
    "import_failed",
    "validation_failed",
    "missing_artifact",
    "hash_validation_failed",
    "unsupported_layout",
    "conflicting_sources",
    "checkpoint_interrupted",
    "contract_unavailable",
    "contract_version_mismatch",
    "controlled_unknown_failure",
)
COVERAGE_SOURCE_LAYOUT_CLASSIFICATIONS = (
    "supported",
    "unsupported",
    "unavailable",
    "not_applicable",
)
COVERAGE_INVARIANT_IDS = (
    "coverage.facility-eligibility-total",
    "coverage.processing-outcome-total",
    "coverage.refresh-state-total",
    "coverage.change-outcome-total",
    "coverage.retrieval-state-total",
    "coverage.import-state-total",
    "coverage.preserved-artifact-state-total",
    "coverage.hash-validation-state-total",
    "coverage.preserved-artifact-total",
    "coverage.governed-conflict-total",
    "coverage.operator-facility-conflict-total",
    "coverage.operator-intervention-total",
    "coverage.job-state-total",
    "coverage.field-stage-balances",
    "coverage.field-stage-inventory",
    "coverage.terminal-classification-total",
)
COVERAGE_AGGREGATE_CSV_FIELDNAMES = (
    "contract_version",
    "report_id",
    "dimension",
    "field_id",
    "stage",
    "category",
    "numerator_count",
    "denominator_count",
    "percentage",
    "status",
    "criteria_set_id",
    "source_snapshot_id",
)
DEFAULT_SQLITE_PATH = Path("data/processed/ccld.sqlite")
SQLITE_PATH_ENV = "CCLD_SOURCE_TO_SCREEN_SQLITE_PATH"
TRACKED_BASELINE_DIR = Path("docs/data")
NEARLY_ALWAYS_NULL_PERCENT = 95.0

INVENTORY_FIELDNAMES = (
    "data_element_id",
    "reviewer_facing_name",
    "ownership",
    "source_artifact_type",
    "source_field_or_extractor_reference",
    "source_availability_status",
    "source_observed_count",
    "source_eligible_count",
    "extraction_status",
    "canonical_model_table_column",
    "sqlite_storage_status",
    "postgresql_storage_status",
    "population_measurement_status",
    "imported_populated_count",
    "eligible_record_count",
    "population_percentage",
    "null_count",
    "blank_count",
    "null_blank_count",
    "missing_key_count",
    "literal_unknown_count",
    "literal_unavailable_count",
    "literal_not_applicable_count",
    "date_unavailable_count",
    "verified_zero_count",
    "null_meaning",
    "query_service_consumer",
    "current_display_route_or_export",
    "recommended_display_location",
    "recommended_display_method",
    "traceability_availability",
    "validation_coverage",
    "gap_classification",
    "disposition",
    "priority",
    "evidence_reference_location",
)

POPULATION_FIELDNAMES = (
    "data_element_id",
    "store",
    "store_inspected",
    "measurement_status",
    "eligible_record_count",
    "populated_count",
    "population_percentage",
    "missing_key_count",
    "null_count",
    "blank_count",
    "literal_unknown_count",
    "literal_unavailable_count",
    "literal_not_applicable_count",
    "date_unavailable_count",
    "verified_zero_count",
    "nearly_always_null",
    "coverage_state",
    "zero_semantics",
)

NULL_SEMANTICS_FIELDNAMES = (
    "data_element_id",
    "data_type",
    "null_meaning",
    "blank_meaning",
    "zero_meaning",
    "unknown_literal_meaning",
    "unavailable_literal_meaning",
    "not_applicable_meaning",
    "date_unavailable_meaning",
    "audit_rule",
)

PARITY_FIELDNAMES = (
    "data_element_id",
    "sqlite_eligible_count",
    "sqlite_populated_count",
    "sqlite_missing_key_count",
    "sqlite_null_count",
    "sqlite_blank_count",
    "sqlite_literal_unknown_count",
    "sqlite_literal_unavailable_count",
    "sqlite_literal_not_applicable_count",
    "sqlite_date_unavailable_count",
    "sqlite_verified_zero_count",
    "postgresql_eligible_count",
    "postgresql_populated_count",
    "postgresql_missing_key_count",
    "postgresql_null_count",
    "postgresql_blank_count",
    "postgresql_literal_unknown_count",
    "postgresql_literal_unavailable_count",
    "postgresql_literal_not_applicable_count",
    "postgresql_date_unavailable_count",
    "postgresql_verified_zero_count",
    "parity_status",
    "gap_classification",
    "explanation",
)

FACILITY_COVERAGE_FIELDNAMES = (
    "data_element_id",
    "reviewer_facing_name",
    "source_artifact_type",
    "source_field_or_extractor_reference",
    "canonical_model_table_column",
    "current_facility_hub_coverage",
    "recommended_single_home",
    "recommended_display_method",
    "population_measurement_status",
    "population_percentage",
    "gap_classification",
    "priority",
    "evidence_reference_location",
)

COMPLAINT_COVERAGE_FIELDNAMES = (
    "data_element_id",
    "reviewer_facing_name",
    "source_artifact_type",
    "source_field_or_extractor_reference",
    "canonical_model_table_column",
    "current_complaint_detail_coverage",
    "recommended_display_location",
    "recommended_display_method",
    "population_measurement_status",
    "population_percentage",
    "gap_classification",
    "priority",
    "evidence_reference_location",
)

AGGREGATE_FIELDNAMES = (
    "feature_id",
    "reviewer_feature",
    "current_route_or_export",
    "required_data_elements",
    "data_store_inspected",
    "eligible_record_count",
    "qualifying_record_count",
    "readiness_status",
    "zero_or_unavailable_cause",
    "gap_classification",
    "known_query_limit",
    "evidence_reference_location",
    "recommended_validation",
)

GAP_FIELDNAMES = (
    "gap_id",
    "data_element_id",
    "gap_classification",
    "title",
    "description",
    "ownership",
    "priority",
    "disposition",
    "recommended_display_location",
    "dependencies",
    "evidence_reference_location",
    "validation_requirement",
)

MANDATORY_OUTPUTS = (
    "manifest.json",
    "data-element-inventory.csv",
    "data-element-inventory.json",
    "population-summary.csv",
    "null-semantics.csv",
    "facility-hub-coverage.csv",
    "complaint-detail-coverage.csv",
    "aggregate-feature-readiness.csv",
    "gap-register.csv",
    "recommended-issues.json",
    "summary.md",
)
PARITY_OUTPUT = "sqlite-postgres-parity.csv"

_SQLITE_TABLE_BY_ENTITY = {
    "facility": "facilities",
    "source_document": "source_documents",
    "complaint": "complaints",
    "allegation": "allegations",
    "event": "events",
    "extraction_audit": "extraction_audit",
}
_RUNTIME_ENTITY_BY_ENTITY = {
    "facilities": "facility",
    "source_documents": "source_document",
    "complaints": "complaint",
    "allegations": "allegation",
    "events": "event",
    "extraction_audit": "extraction_audit",
}

_ABSOLUTE_WINDOWS_PATH_RE = re.compile(
    r"(?i)\b[a-z]:[\\/][^\s,;\]\[)]+"
)
_ABSOLUTE_PRIVATE_POSIX_PATH_RE = re.compile(
    r"(?i)(?<![\w-])/(?!reviewer(?:/|$)|ccld(?:/|$)|"
    r"app/data/processed/source-to-screen-audit/runtime-post-deploy(?:\s|$))"
    r"[^\s,;\]\[)]+"
)
_CONNECTION_STRING_RE = re.compile(
    r"(?i)\b(?:postgres(?:ql)?|mysql|mariadb|mongodb|redis)(?:\+[a-z0-9_-]+)?://[^\s]+"
)
_URL_RE = re.compile(r"(?i)\bhttps?://[^\s<>\]\[)]+")
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(password|passwd|pwd|token|secret|cookie|authorization|api[_-]?key)\s*[:=]\s*[^\s,;]+"
)


@dataclass(frozen=True)
class PopulationStats:
    eligible_record_count: int
    populated_count: int
    missing_key_count: int = 0
    null_count: int = 0
    blank_count: int = 0
    literal_unknown_count: int = 0
    literal_unavailable_count: int = 0
    literal_not_applicable_count: int = 0
    date_unavailable_count: int = 0
    verified_zero_count: int = 0

    @property
    def population_percentage(self) -> float | None:
        if self.eligible_record_count == 0:
            return None
        return round(self.populated_count * 100.0 / self.eligible_record_count, 2)

    @property
    def null_blank_count(self) -> int:
        return self.missing_key_count + self.null_count + self.blank_count

    @property
    def nearly_always_null(self) -> bool:
        if self.eligible_record_count == 0:
            return False
        missing_percent = self.null_blank_count * 100.0 / self.eligible_record_count
        return missing_percent >= NEARLY_ALWAYS_NULL_PERCENT


@dataclass(frozen=True)
class StoreSnapshot:
    store: str
    available: bool
    inspection_status: str
    stats: Mapping[str, PopulationStats]
    safe_metadata: Mapping[str, int | str | bool | None]


@dataclass(frozen=True)
class SourceObservation:
    source_id: str
    inspected: bool
    artifact_count: int
    usable_artifact_count: int
    unavailable_artifact_count: int
    field_counts: Mapping[str, int]
    eligible_counts: Mapping[str, int]
    safe_note: str


@dataclass(frozen=True)
class AuditResult:
    manifest: Mapping[str, Any]
    inventory: tuple[Mapping[str, Any], ...]
    population_summary: tuple[Mapping[str, Any], ...]
    null_semantics: tuple[Mapping[str, Any], ...]
    parity: tuple[Mapping[str, Any], ...]
    facility_hub_coverage: tuple[Mapping[str, Any], ...]
    complaint_detail_coverage: tuple[Mapping[str, Any], ...]
    aggregate_feature_readiness: tuple[Mapping[str, Any], ...]
    gap_register: tuple[Mapping[str, Any], ...]
    recommended_issues: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True)
class CoveragePackageResult:
    report_id: str
    manifest: Mapping[str, Any]
    report: Mapping[str, Any]
    facility_index: tuple[Mapping[str, Any], ...]
    job_index: tuple[Mapping[str, Any], ...]
    artifact_hashes: Mapping[str, str]


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() in {"script", "style"}:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in {"script", "style"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            cleaned = " ".join(data.split())
            if cleaned:
                self.parts.append(cleaned)


def classify_scalar(value: object) -> str:
    """Classify a scalar without collapsing distinct missing-value meanings."""

    if value is None:
        return "null"
    if isinstance(value, bool):
        return "verified_false" if not value else "verified_true"
    if isinstance(value, (int, float)):
        return "verified_zero" if value == 0 else "populated_numeric"
    if isinstance(value, str):
        normalized = " ".join(value.split()).casefold()
        if not value.strip():
            return "blank"
        if normalized == "unknown":
            return "literal_unknown"
        if normalized in {"unavailable", "not available", "coverage unavailable"}:
            return "literal_unavailable"
        if normalized in {"not applicable", "n/a"}:
            return "literal_not_applicable"
        if normalized in {"date unavailable", "undated"}:
            return "date_unavailable"
        return "populated_text"
    return "populated_other"


def redact_sensitive_text(value: str, *, redact_urls: bool = True) -> str:
    """Return text safe for aggregate audit output."""

    redacted = _CONNECTION_STRING_RE.sub("<redacted-connection-string>", value)
    redacted = _SECRET_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}=<redacted>", redacted)
    if redact_urls:
        redacted = _URL_RE.sub("<redacted-url>", redacted)
    redacted = _ABSOLUTE_WINDOWS_PATH_RE.sub("<redacted-path>", redacted)
    redacted = _ABSOLUTE_PRIVATE_POSIX_PATH_RE.sub("<redacted-path>", redacted)
    return redacted


def sanitize_payload(value: Any, *, redact_urls: bool = True) -> Any:
    if isinstance(value, str):
        return redact_sensitive_text(value, redact_urls=redact_urls)
    if isinstance(value, Mapping):
        return {
            str(key): sanitize_payload(item, redact_urls=redact_urls)
            for key, item in value.items()
        }
    if isinstance(value, tuple):
        return tuple(sanitize_payload(item, redact_urls=redact_urls) for item in value)
    if isinstance(value, list):
        return [sanitize_payload(item, redact_urls=redact_urls) for item in value]
    return value


def _safe_repo_reference(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return "<configured-local-path>"


def _is_numeric_type(data_type: str) -> bool:
    normalized = data_type.casefold()
    return any(marker in normalized for marker in ("integer", "number", "float", "real"))


def _coverage_state(stats: PopulationStats | None, *, inspected: bool) -> str:
    if not inspected or stats is None:
        return "coverage unavailable"
    if stats.eligible_record_count == 0:
        return "no eligible records in inspected store"
    if stats.populated_count == 0:
        return "no populated values; inspect missing-state counts"
    if stats.nearly_always_null:
        return "nearly always null or blank"
    return "measured"


def _source_field_id(text_value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", text_value.casefold()).strip("_")
    return normalized or "unknown"


_RAW_FIELD_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("facility_number", re.compile(r"\bfacility\s+(?:number|id)\b", re.I)),
    ("facility_name", re.compile(r"\bfacility\s+name\b", re.I)),
    ("facility_address", re.compile(r"\b(?:facility\s+)?address\b", re.I)),
    ("facility_city", re.compile(r"\b(?:facility\s+)?city\b", re.I)),
    ("facility_capacity", re.compile(r"\b(?:facility\s+)?capacity\b", re.I)),
    ("regional_office", re.compile(r"\bregional\s+office\b", re.I)),
    ("complaint_control_number", re.compile(r"\bcomplaint\s+control\s+number\b", re.I)),
    ("complaint_received_date", re.compile(r"\bcomplaint\s+(?:was\s+)?received\b", re.I)),
    ("finding", re.compile(r"\bfinding\b", re.I)),
    ("report_type", re.compile(r"\bcomplaint\s+investigation\s+report\b", re.I)),
    ("report_date", re.compile(r"\breport\s+date\b", re.I)),
    ("date_signed", re.compile(r"\bdate\s+signed\b", re.I)),
    ("visit_date", re.compile(r"\bvisit\s+date\b", re.I)),
    ("allegation_text", re.compile(r"\ballegation\s*\(?s\)?\b", re.I)),
    (
        "investigation_findings_narrative",
        re.compile(r"\binvestigation\s+findings?\b", re.I),
    ),
)


def detect_raw_artifact_fields(html: str) -> tuple[str, ...]:
    """Detect only allowlisted field identities; never return source values."""

    parser = _VisibleTextParser()
    parser.feed(html)
    visible_text = "\n".join(parser.parts)
    detected = {
        field_name
        for field_name, pattern in _RAW_FIELD_PATTERNS
        if pattern.search(visible_text)
    }
    return tuple(sorted(detected))


def inspect_raw_artifacts(
    paths: Iterable[Path],
    *,
    source_id: str,
    required_identity: Sequence[str] = ("facility_number", "facility_name"),
) -> SourceObservation:
    artifact_paths = tuple(sorted({path.resolve() for path in paths if path.is_file()}))
    field_counts: Counter[str] = Counter()
    usable_count = 0
    unavailable_count = 0
    for path in artifact_paths:
        try:
            html = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            unavailable_count += 1
            continue
        fields = detect_raw_artifact_fields(html)
        if not set(required_identity).issubset(fields) or len(html.strip()) < 100:
            unavailable_count += 1
            continue
        usable_count += 1
        field_counts.update(fields)
    eligible_counts = {field_name: usable_count for field_name, _pattern in _RAW_FIELD_PATTERNS}
    return SourceObservation(
        source_id=source_id,
        inspected=bool(artifact_paths),
        artifact_count=len(artifact_paths),
        usable_artifact_count=usable_count,
        unavailable_artifact_count=unavailable_count,
        field_counts=dict(sorted(field_counts.items())),
        eligible_counts=dict(sorted(eligible_counts.items())),
        safe_note=(
            "Only allowlisted field identities were measured; source bodies and values "
            "were not retained."
        ),
    )


def inspect_facility_csvs(paths: Iterable[Path], *, source_id: str) -> SourceObservation:
    csv_paths = tuple(sorted({path.resolve() for path in paths if path.is_file()}))
    field_counts: Counter[str] = Counter()
    eligible_counts: Counter[str] = Counter()
    usable_count = 0
    unavailable_count = 0
    for path in csv_paths:
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
                reader = csv.DictReader(csv_file)
                fieldnames = tuple(
                    name for name in (reader.fieldnames or ()) if name is not None
                )
                if not fieldnames:
                    unavailable_count += 1
                    continue
                usable_count += 1
                for row in reader:
                    for column_index, field_name in enumerate(fieldnames):
                        safe_header = safe_facility_source_header(
                            field_name,
                            column_index,
                        )
                        field_id = _source_field_id(safe_header)
                        eligible_counts[field_id] += 1
                        classification = classify_scalar(row.get(field_name))
                        if classification.startswith("populated_") or classification in {
                            "verified_zero",
                            "verified_false",
                            "verified_true",
                        }:
                            field_counts[field_id] += 1
        except (OSError, UnicodeDecodeError, csv.Error):
            unavailable_count += 1
            continue
    return SourceObservation(
        source_id=source_id,
        inspected=bool(csv_paths),
        artifact_count=len(csv_paths),
        usable_artifact_count=usable_count,
        unavailable_artifact_count=unavailable_count,
        field_counts=dict(sorted(field_counts.items())),
        eligible_counts=dict(sorted(eligible_counts.items())),
        safe_note=(
            "Only CSV field names and aggregate population counts were measured; row "
            "values were not retained."
        ),
    )


def _sqlite_uri(path: Path) -> str:
    return f"{path.resolve().as_uri()}?mode=ro"


def inspect_sqlite_store(path: Path, specs: Sequence[ElementSpec]) -> StoreSnapshot:
    if not path.exists() or not path.is_file():
        return StoreSnapshot(
            store="sqlite",
            available=False,
            inspection_status="configured SQLite data unavailable",
            stats={},
            safe_metadata={"table_count": 0},
        )
    stats: dict[str, PopulationStats] = {}
    try:
        with sqlite3.connect(_sqlite_uri(path), uri=True) as connection:
            table_rows = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
            ).fetchall()
            table_names = {str(row[0]) for row in table_rows}
            table_columns = {
                table_name: {
                    str(row[1]): str(row[2])
                    for row in connection.execute(
                        f"PRAGMA table_info({_quote_sqlite_identifier(table_name)})"
                    ).fetchall()
                }
                for table_name in table_names
            }
            for spec in specs:
                table_name = _sqlite_table_name(spec.canonical_entity)
                column_name = spec.canonical_column
                if (
                    table_name is None
                    or column_name is None
                    or table_name not in table_columns
                    or column_name not in table_columns[table_name]
                ):
                    continue
                stats[spec.data_element_id] = _sqlite_column_stats(
                    connection,
                    table_name=table_name,
                    column_name=column_name,
                    data_type=spec.data_type,
                )
    except sqlite3.Error:
        return StoreSnapshot(
            store="sqlite",
            available=False,
            inspection_status="configured SQLite data could not be inspected read-only",
            stats={},
            safe_metadata={"table_count": 0},
        )
    return StoreSnapshot(
        store="sqlite",
        available=True,
        inspection_status="inspected read-only",
        stats=dict(sorted(stats.items())),
        safe_metadata={"table_count": len(table_names)},
    )


def _quote_sqlite_identifier(value: str) -> str:
    if not re.fullmatch(r"[a-z][a-z0-9_]*", value):
        raise ValueError("Unsafe SQLite identifier in source-to-screen catalog.")
    return f'"{value}"'


def _sqlite_table_name(canonical_entity: str | None) -> str | None:
    if canonical_entity is None:
        return None
    return _SQLITE_TABLE_BY_ENTITY.get(canonical_entity, canonical_entity)


def _runtime_entity_type(canonical_entity: str) -> str:
    return _RUNTIME_ENTITY_BY_ENTITY.get(canonical_entity, canonical_entity)


def _sqlite_column_stats(
    connection: sqlite3.Connection,
    *,
    table_name: str,
    column_name: str,
    data_type: str,
) -> PopulationStats:
    table_sql = _quote_sqlite_identifier(table_name)
    column_sql = _quote_sqlite_identifier(column_name)
    row = connection.execute(
        f"""
        SELECT
            COUNT(*) AS eligible,
            SUM(CASE WHEN {column_sql} IS NULL THEN 1 ELSE 0 END) AS null_count,
            SUM(CASE
                WHEN typeof({column_sql}) = 'text' AND TRIM({column_sql}) = ''
                THEN 1 ELSE 0 END
            ) AS blank_count,
            SUM(CASE
                WHEN LOWER(TRIM(CAST({column_sql} AS TEXT))) = 'unknown'
                THEN 1 ELSE 0 END
            ) AS literal_unknown_count,
            SUM(CASE
                WHEN LOWER(TRIM(CAST({column_sql} AS TEXT))) IN
                    ('unavailable', 'not available', 'coverage unavailable')
                THEN 1 ELSE 0 END
            ) AS literal_unavailable_count,
            SUM(CASE
                WHEN LOWER(TRIM(CAST({column_sql} AS TEXT))) IN
                    ('not applicable', 'n/a')
                THEN 1 ELSE 0 END
            ) AS literal_not_applicable_count,
            SUM(CASE
                WHEN LOWER(TRIM(CAST({column_sql} AS TEXT))) IN
                    ('date unavailable', 'undated')
                THEN 1 ELSE 0 END
            ) AS date_unavailable_count,
            SUM(CASE
                WHEN {column_sql} IS NOT NULL
                 AND NOT (
                    typeof({column_sql}) = 'text' AND TRIM({column_sql}) = ''
                 )
                THEN 1 ELSE 0 END
            ) AS populated_count,
            SUM(CASE
                WHEN typeof({column_sql}) IN ('integer', 'real')
                 AND {column_sql} = 0
                THEN 1 ELSE 0 END
            ) AS zero_count
        FROM {table_sql}
        """
    ).fetchone()
    assert row is not None
    return PopulationStats(
        eligible_record_count=int(row[0] or 0),
        populated_count=int(row[7] or 0),
        null_count=int(row[1] or 0),
        blank_count=int(row[2] or 0),
        literal_unknown_count=int(row[3] or 0),
        literal_unavailable_count=int(row[4] or 0),
        literal_not_applicable_count=int(row[5] or 0),
        date_unavailable_count=int(row[6] or 0),
        verified_zero_count=int(row[8] or 0) if _is_numeric_type(data_type) else 0,
    )


def inspect_runtime_store(connection: Connection, specs: Sequence[ElementSpec]) -> StoreSnapshot:
    """Inspect hosted tables with aggregate SQL only; no source values leave the database."""

    dialect = connection.dialect.name
    inspector = inspect(connection)
    table_names = set(inspector.get_table_names())
    stats: dict[str, PopulationStats] = {}
    for spec in specs:
        runtime_table = spec.runtime_table
        runtime_column = spec.runtime_column
        if (
            runtime_table is not None
            and runtime_column is not None
            and runtime_table in table_names
        ):
            column_names = {
                column["name"] for column in inspector.get_columns(runtime_table)
            }
            if runtime_column in column_names:
                stats[spec.data_element_id] = _runtime_typed_column_stats(
                    connection,
                    table_name=runtime_table,
                    column_name=runtime_column,
                    data_type=spec.data_type,
                )
                continue
        if spec.canonical_entity is not None and spec.canonical_column is not None:
            if "hosted_source_derived_records" in table_names:
                stats[spec.data_element_id] = _runtime_json_stats(
                    connection,
                    entity_type=_runtime_entity_type(spec.canonical_entity),
                    field_name=spec.canonical_column,
                    data_type=spec.data_type,
                )
            continue
    return StoreSnapshot(
        store="postgresql" if dialect == "postgresql" else f"runtime-{dialect}",
        available=True,
        inspection_status="inspected aggregate-only",
        stats=dict(sorted(stats.items())),
        safe_metadata={"table_count": len(table_names), "dialect": dialect},
    )


def _runtime_json_stats(
    connection: Connection,
    *,
    entity_type: str,
    field_name: str,
    data_type: str,
) -> PopulationStats:
    if not re.fullmatch(r"[a-z][a-z0-9_]*", entity_type):
        raise ValueError("Unsafe entity type in source-to-screen catalog.")
    if not re.fullmatch(r"[a-z][a-z0-9_]*", field_name):
        raise ValueError("Unsafe field name in source-to-screen catalog.")
    if connection.dialect.name == "postgresql":
        row = connection.execute(
            text(
                """
                WITH scoped AS (
                    SELECT original_values::jsonb AS values
                    FROM hosted_source_derived_records
                    WHERE entity_type = :entity_type
                )
                SELECT
                    COUNT(*) AS eligible,
                    COUNT(*) FILTER (WHERE NOT (values ? :field_name)) AS missing_key_count,
                    COUNT(*) FILTER (
                        WHERE values ? :field_name
                          AND jsonb_typeof(values -> :field_name) = 'null'
                    ) AS null_count,
                    COUNT(*) FILTER (
                        WHERE jsonb_typeof(values -> :field_name) = 'string'
                          AND BTRIM(values ->> :field_name) = ''
                    ) AS blank_count,
                    COUNT(*) FILTER (
                        WHERE LOWER(BTRIM(values ->> :field_name)) = 'unknown'
                    ) AS literal_unknown_count,
                    COUNT(*) FILTER (
                        WHERE LOWER(BTRIM(values ->> :field_name)) IN
                            ('unavailable', 'not available', 'coverage unavailable')
                    ) AS literal_unavailable_count,
                    COUNT(*) FILTER (
                        WHERE LOWER(BTRIM(values ->> :field_name)) IN
                            ('not applicable', 'n/a')
                    ) AS literal_not_applicable_count,
                    COUNT(*) FILTER (
                        WHERE LOWER(BTRIM(values ->> :field_name)) IN
                            ('date unavailable', 'undated')
                    ) AS date_unavailable_count,
                    COUNT(*) FILTER (
                        WHERE values ? :field_name
                          AND jsonb_typeof(values -> :field_name) <> 'null'
                          AND NOT (
                              jsonb_typeof(values -> :field_name) = 'string'
                              AND BTRIM(values ->> :field_name) = ''
                          )
                    ) AS populated_count,
                    COUNT(*) FILTER (
                        WHERE jsonb_typeof(values -> :field_name) = 'number'
                          AND (values ->> :field_name)::numeric = 0
                    ) AS zero_count
                FROM scoped
                """
            ),
            {"entity_type": entity_type, "field_name": field_name},
        ).fetchone()
    elif connection.dialect.name == "sqlite":
        json_path = f'$."{field_name}"'
        row = connection.execute(
            text(
                """
                SELECT
                    COUNT(*) AS eligible,
                    SUM(CASE
                        WHEN json_type(original_values, :json_path) IS NULL
                        THEN 1 ELSE 0 END
                    ) AS missing_key_count,
                    SUM(CASE
                        WHEN json_type(original_values, :json_path) = 'null'
                        THEN 1 ELSE 0 END
                    ) AS null_count,
                    SUM(CASE
                        WHEN json_type(original_values, :json_path) = 'text'
                         AND TRIM(json_extract(original_values, :json_path)) = ''
                        THEN 1 ELSE 0 END
                    ) AS blank_count,
                    SUM(CASE
                        WHEN LOWER(TRIM(CAST(
                            json_extract(original_values, :json_path) AS TEXT
                        ))) = 'unknown'
                        THEN 1 ELSE 0 END
                    ) AS literal_unknown_count,
                    SUM(CASE
                        WHEN LOWER(TRIM(CAST(
                            json_extract(original_values, :json_path) AS TEXT
                        ))) IN
                            ('unavailable', 'not available', 'coverage unavailable')
                        THEN 1 ELSE 0 END
                    ) AS literal_unavailable_count,
                    SUM(CASE
                        WHEN LOWER(TRIM(CAST(
                            json_extract(original_values, :json_path) AS TEXT
                        ))) IN ('not applicable', 'n/a')
                        THEN 1 ELSE 0 END
                    ) AS literal_not_applicable_count,
                    SUM(CASE
                        WHEN LOWER(TRIM(CAST(
                            json_extract(original_values, :json_path) AS TEXT
                        ))) IN ('date unavailable', 'undated')
                        THEN 1 ELSE 0 END
                    ) AS date_unavailable_count,
                    SUM(CASE
                        WHEN json_type(original_values, :json_path) IS NOT NULL
                         AND json_type(original_values, :json_path) <> 'null'
                         AND NOT (
                             json_type(original_values, :json_path) = 'text'
                             AND TRIM(json_extract(original_values, :json_path)) = ''
                         )
                        THEN 1 ELSE 0 END
                    ) AS populated_count,
                    SUM(CASE
                        WHEN json_type(original_values, :json_path) IN ('integer', 'real')
                         AND json_extract(original_values, :json_path) = 0
                        THEN 1 ELSE 0 END
                    ) AS zero_count
                FROM hosted_source_derived_records
                WHERE entity_type = :entity_type
                """
            ),
            {"entity_type": entity_type, "json_path": json_path},
        ).fetchone()
    else:
        raise ValueError(
            "Runtime source-to-screen inspection supports PostgreSQL and SQLite tests."
        )
    assert row is not None
    return PopulationStats(
        eligible_record_count=int(row[0] or 0),
        populated_count=int(row[8] or 0),
        missing_key_count=int(row[1] or 0),
        null_count=int(row[2] or 0),
        blank_count=int(row[3] or 0),
        literal_unknown_count=int(row[4] or 0),
        literal_unavailable_count=int(row[5] or 0),
        literal_not_applicable_count=int(row[6] or 0),
        date_unavailable_count=int(row[7] or 0),
        verified_zero_count=int(row[9] or 0) if _is_numeric_type(data_type) else 0,
    )


def _runtime_typed_column_stats(
    connection: Connection,
    *,
    table_name: str,
    column_name: str,
    data_type: str,
) -> PopulationStats:
    if not re.fullmatch(r"[a-z][a-z0-9_]*", table_name):
        raise ValueError("Unsafe runtime table in source-to-screen catalog.")
    if not re.fullmatch(r"[a-z][a-z0-9_]*", column_name):
        raise ValueError("Unsafe runtime column in source-to-screen catalog.")
    metadata = MetaData()
    table = Table(table_name, metadata, autoload_with=connection)
    column = table.c[column_name]
    normalized = func.lower(func.trim(sql_cast(column, String)))
    is_blank = column.is_not(None) & (func.trim(sql_cast(column, String)) == "")
    is_verified_zero = column == 0 if _is_numeric_type(data_type) else false()
    row = connection.execute(
        select(
            func.count().label("eligible"),
            func.sum(case((column.is_(None), 1), else_=0)).label("null_count"),
            func.sum(case((is_blank, 1), else_=0)).label("blank_count"),
            func.sum(case((normalized == "unknown", 1), else_=0)).label(
                "literal_unknown_count"
            ),
            func.sum(
                case(
                    (
                        normalized.in_(
                            ("unavailable", "not available", "coverage unavailable")
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("literal_unavailable_count"),
            func.sum(
                case(
                    (normalized.in_(("not applicable", "n/a")), 1),
                    else_=0,
                )
            ).label("literal_not_applicable_count"),
            func.sum(
                case(
                    (normalized.in_(("date unavailable", "undated")), 1),
                    else_=0,
                )
            ).label("date_unavailable_count"),
            func.sum(
                case((column.is_not(None) & ~is_blank, 1), else_=0)
            ).label("populated_count"),
            func.sum(case((is_verified_zero, 1), else_=0)).label("zero_count"),
        )
    ).fetchone()
    assert row is not None
    return PopulationStats(
        eligible_record_count=int(row[0] or 0),
        populated_count=int(row[7] or 0),
        null_count=int(row[1] or 0),
        blank_count=int(row[2] or 0),
        literal_unknown_count=int(row[3] or 0),
        literal_unavailable_count=int(row[4] or 0),
        literal_not_applicable_count=int(row[5] or 0),
        date_unavailable_count=int(row[6] or 0),
        verified_zero_count=int(row[8] or 0) if _is_numeric_type(data_type) else 0,
    )


def _runtime_engine(environ: Mapping[str, str]) -> Engine:
    config = load_hosted_database_config(environ=environ, require_url=True)
    return create_engine(cast(str, config.database_url))


def _unavailable_runtime_snapshot(status: str) -> StoreSnapshot:
    return StoreSnapshot(
        store="postgresql",
        available=False,
        inspection_status=status,
        stats={},
        safe_metadata={"table_count": 0, "dialect": "postgresql"},
    )


def _source_observations(repo_root: Path) -> tuple[SourceObservation, ...]:
    retained_complaint = inspect_raw_artifacts(
        (repo_root / "data/raw/ccld").glob("*_inx*.html"),
        source_id="retained_raw_complaint_artifacts",
    )
    complaint_fixtures = inspect_raw_artifacts(
        (repo_root / "tests/fixtures/ccld/raw").glob("*_inx*.html"),
        source_id="governed_complaint_fixtures",
    )
    facility_page_fixtures = inspect_raw_artifacts(
        (repo_root / "tests/fixtures/ccld/raw").glob("*facility_detail*.html"),
        source_id="governed_facility_page_fixtures",
        required_identity=("facility_number",),
    )
    governed_facility_paths = (
        repo_root
        / "tests/fixtures/public_source_facilities/ccld_program_facilities_tiny.csv",
        repo_root
        / "tests/fixtures/public_source_facilities/chhs_facility_master_tiny.csv",
        *sorted((repo_root / "tests/fixtures/source_profiling").glob("*.csv")),
    )
    governed_facility = inspect_facility_csvs(
        governed_facility_paths,
        source_id="governed_facility_fixtures",
    )
    configured_facility_paths = tuple(
        sorted((repo_root / "data/raw/source-profiling").glob("*.csv"))
    )
    retained_facility = inspect_facility_csvs(
        configured_facility_paths,
        source_id="retained_facility_reference_artifacts",
    )
    return tuple(
        sorted(
            (
                retained_complaint,
                complaint_fixtures,
                facility_page_fixtures,
                governed_facility,
                retained_facility,
            ),
            key=lambda item: item.source_id,
        )
    )


def _observation_for_spec(
    spec: ElementSpec,
    observations: Sequence[SourceObservation],
) -> tuple[int | None, int | None]:
    observed_field = spec.source_observation_field
    observed_source_ids = set(spec.source_observation_sources)
    if observed_field is None or not observed_source_ids:
        return None, None
    matched = [item for item in observations if item.source_id in observed_source_ids]
    inspected = [item for item in matched if item.inspected]
    if not inspected:
        return None, None
    return (
        sum(item.field_counts.get(observed_field, 0) for item in inspected),
        sum(item.eligible_counts.get(observed_field, 0) for item in inspected),
    )


def _primary_stats(
    mode: AuditMode,
    sqlite_snapshot: StoreSnapshot,
    runtime_snapshot: StoreSnapshot,
    data_element_id: str,
) -> tuple[PopulationStats | None, str]:
    if mode == "runtime":
        return runtime_snapshot.stats.get(data_element_id), runtime_snapshot.inspection_status
    if sqlite_snapshot.available and data_element_id in sqlite_snapshot.stats:
        return sqlite_snapshot.stats[data_element_id], sqlite_snapshot.inspection_status
    if runtime_snapshot.available and data_element_id in runtime_snapshot.stats:
        return runtime_snapshot.stats[data_element_id], runtime_snapshot.inspection_status
    return None, "coverage unavailable"


def _spec_value(spec: ElementSpec, name: str, default: Any = "") -> Any:
    return getattr(spec, name, default)


def _canonical_reference(spec: ElementSpec) -> str:
    if spec.canonical_entity is None or spec.canonical_column is None:
        return "not allocated"
    return f"{_sqlite_table_name(spec.canonical_entity)}.{spec.canonical_column}"


def _measurement_status(
    stats: PopulationStats | None,
    snapshot: StoreSnapshot,
) -> str:
    if not snapshot.available:
        return snapshot.inspection_status
    if stats is None:
        return "field not present in inspected store"
    return snapshot.inspection_status


def _effective_gap_classification(
    spec: ElementSpec,
    *,
    stats: PopulationStats | None,
    source_observed_count: int | None,
) -> str:
    configured = str(spec.gap_classification)
    if configured not in GAP_CLASSIFICATIONS:
        raise ValueError(f"Unsupported gap classification for {spec.data_element_id}.")
    if (
        configured == "RAW_PRESENT_EXTRACTION_MISSING"
        and source_observed_count == 0
    ):
        return "SOURCE_NOT_PROVIDED"
    if configured not in {"NOT_APPLICABLE"}:
        return configured
    if not bool(_spec_value(spec, "reviewer_relevant", True)):
        return "INTENTIONALLY_INTERNAL"
    extraction_status = str(spec.extraction_status).casefold()
    if source_observed_count and "missing" in extraction_status:
        return "RAW_PRESENT_EXTRACTION_MISSING"
    if source_observed_count and (
        spec.canonical_entity is None or spec.canonical_column is None
    ):
        return "EXTRACTED_CANONICAL_MAPPING_MISSING"
    if stats is not None and stats.eligible_record_count:
        if stats.populated_count == 0:
            return "CANONICAL_IMPORT_NOT_POPULATED"
        if stats.blank_count:
            return "UNEXPLAINED_BLANK"
        if stats.nearly_always_null:
            return "CANONICAL_IMPORT_NOT_POPULATED"
        if (
            not str(spec.current_display_route_or_export).strip()
            and bool(_spec_value(spec, "reviewer_relevant", True))
        ):
            return "UI_DISPLAY_OMISSION"
    return configured


def _inventory_rows(
    specs: Sequence[ElementSpec],
    *,
    observations: Sequence[SourceObservation],
    sqlite_snapshot: StoreSnapshot,
    runtime_snapshot: StoreSnapshot,
    mode: AuditMode,
) -> tuple[Mapping[str, Any], ...]:
    rows: list[Mapping[str, Any]] = []
    for spec in sorted(specs, key=lambda item: item.data_element_id):
        stats, primary_status = _primary_stats(
            mode,
            sqlite_snapshot,
            runtime_snapshot,
            spec.data_element_id,
        )
        source_count, source_eligible = _observation_for_spec(spec, observations)
        source_status = str(spec.source_availability_status)
        if source_eligible is not None:
            source_status = (
                "observed in inspected representative artifacts"
                if source_count
                else "not observed in inspected representative artifacts"
            )
        rows.append(
            {
                "data_element_id": spec.data_element_id,
                "reviewer_facing_name": spec.reviewer_facing_name,
                "ownership": spec.ownership,
                "source_artifact_type": spec.source_artifact_type,
                "source_field_or_extractor_reference": (
                    spec.source_field_or_extractor_reference
                ),
                "source_availability_status": source_status,
                "source_observed_count": source_count,
                "source_eligible_count": source_eligible,
                "extraction_status": spec.extraction_status,
                "canonical_model_table_column": _canonical_reference(spec),
                "sqlite_storage_status": _measurement_status(
                    sqlite_snapshot.stats.get(spec.data_element_id),
                    sqlite_snapshot,
                ),
                "postgresql_storage_status": _measurement_status(
                    runtime_snapshot.stats.get(spec.data_element_id),
                    runtime_snapshot,
                ),
                "population_measurement_status": primary_status,
                "imported_populated_count": (
                    stats.populated_count if stats is not None else None
                ),
                "eligible_record_count": (
                    stats.eligible_record_count if stats is not None else None
                ),
                "population_percentage": (
                    stats.population_percentage if stats is not None else None
                ),
                "null_count": stats.null_count if stats is not None else None,
                "blank_count": stats.blank_count if stats is not None else None,
                "null_blank_count": (
                    stats.null_blank_count if stats is not None else None
                ),
                "missing_key_count": (
                    stats.missing_key_count if stats is not None else None
                ),
                "literal_unknown_count": (
                    stats.literal_unknown_count if stats is not None else None
                ),
                "literal_unavailable_count": (
                    stats.literal_unavailable_count if stats is not None else None
                ),
                "literal_not_applicable_count": (
                    stats.literal_not_applicable_count if stats is not None else None
                ),
                "date_unavailable_count": (
                    stats.date_unavailable_count if stats is not None else None
                ),
                "verified_zero_count": (
                    stats.verified_zero_count if stats is not None else None
                ),
                "null_meaning": spec.null_meaning,
                "query_service_consumer": spec.query_service_consumer,
                "current_display_route_or_export": (
                    spec.current_display_route_or_export
                ),
                "recommended_display_location": spec.recommended_display_location,
                "recommended_display_method": spec.recommended_display_method,
                "traceability_availability": spec.traceability_availability,
                "validation_coverage": spec.validation_coverage,
                "gap_classification": _effective_gap_classification(
                    spec,
                    stats=stats,
                    source_observed_count=source_count,
                ),
                "disposition": spec.disposition,
                "priority": spec.priority,
                "evidence_reference_location": spec.evidence_reference_location,
            }
        )
    return tuple(rows)


def _population_rows(
    specs: Sequence[ElementSpec],
    snapshots: Sequence[StoreSnapshot],
) -> tuple[Mapping[str, Any], ...]:
    rows: list[Mapping[str, Any]] = []
    for spec in sorted(specs, key=lambda item: item.data_element_id):
        for snapshot in snapshots:
            stats = snapshot.stats.get(spec.data_element_id)
            rows.append(
                {
                    "data_element_id": spec.data_element_id,
                    "store": snapshot.store,
                    "store_inspected": snapshot.available,
                    "measurement_status": _measurement_status(stats, snapshot),
                    "eligible_record_count": (
                        stats.eligible_record_count if stats is not None else None
                    ),
                    "populated_count": (
                        stats.populated_count if stats is not None else None
                    ),
                    "population_percentage": (
                        stats.population_percentage if stats is not None else None
                    ),
                    "missing_key_count": (
                        stats.missing_key_count if stats is not None else None
                    ),
                    "null_count": stats.null_count if stats is not None else None,
                    "blank_count": stats.blank_count if stats is not None else None,
                    "literal_unknown_count": (
                        stats.literal_unknown_count if stats is not None else None
                    ),
                    "literal_unavailable_count": (
                        stats.literal_unavailable_count if stats is not None else None
                    ),
                    "literal_not_applicable_count": (
                        stats.literal_not_applicable_count if stats is not None else None
                    ),
                    "date_unavailable_count": (
                        stats.date_unavailable_count if stats is not None else None
                    ),
                    "verified_zero_count": (
                        stats.verified_zero_count if stats is not None else None
                    ),
                    "nearly_always_null": (
                        stats.nearly_always_null if stats is not None else None
                    ),
                    "coverage_state": _coverage_state(
                        stats,
                        inspected=snapshot.available,
                    ),
                    "zero_semantics": spec.zero_meaning,
                }
            )
    return tuple(rows)


def _null_semantics_rows(
    specs: Sequence[ElementSpec],
) -> tuple[Mapping[str, Any], ...]:
    return tuple(
        {
            "data_element_id": spec.data_element_id,
            "data_type": spec.data_type,
            "null_meaning": spec.null_meaning,
            "blank_meaning": spec.blank_meaning,
            "zero_meaning": spec.zero_meaning,
            "unknown_literal_meaning": (
                "literal source value; never inferred from null or blank"
            ),
            "unavailable_literal_meaning": (
                "explicit unavailable coverage; never counted as numeric zero"
            ),
            "not_applicable_meaning": (
                "field does not apply to the record; distinct from missing"
            ),
            "date_unavailable_meaning": (
                "date coverage is explicitly unavailable or undated"
            ),
            "audit_rule": (
                "null, blank, unknown, unavailable, not applicable, undated, and "
                "verified numeric zero remain distinct"
            ),
        }
        for spec in sorted(specs, key=lambda item: item.data_element_id)
    )


def _parity_rows(
    specs: Sequence[ElementSpec],
    sqlite_snapshot: StoreSnapshot,
    runtime_snapshot: StoreSnapshot,
) -> tuple[Mapping[str, Any], ...]:
    if not (sqlite_snapshot.available and runtime_snapshot.available):
        return ()
    rows: list[Mapping[str, Any]] = []
    for spec in sorted(specs, key=lambda item: item.data_element_id):
        sqlite_stats = sqlite_snapshot.stats.get(spec.data_element_id)
        runtime_stats = runtime_snapshot.stats.get(spec.data_element_id)
        if spec.canonical_entity is None or spec.canonical_column is None:
            continue
        mapping_present = sqlite_stats is not None and runtime_stats is not None
        comparable = bool(mapping_present) and (
            sqlite_stats is not None
            and runtime_stats is not None
            and sqlite_stats.eligible_record_count == runtime_stats.eligible_record_count
            and sqlite_stats.populated_count == runtime_stats.populated_count
            and sqlite_stats.missing_key_count == runtime_stats.missing_key_count
            and sqlite_stats.null_count == runtime_stats.null_count
            and sqlite_stats.blank_count == runtime_stats.blank_count
            and sqlite_stats.literal_unknown_count
            == runtime_stats.literal_unknown_count
            and sqlite_stats.literal_unavailable_count
            == runtime_stats.literal_unavailable_count
            and sqlite_stats.literal_not_applicable_count
            == runtime_stats.literal_not_applicable_count
            and sqlite_stats.date_unavailable_count
            == runtime_stats.date_unavailable_count
            and sqlite_stats.verified_zero_count == runtime_stats.verified_zero_count
        )

        def count(stats: PopulationStats | None, name: str) -> int | None:
            return getattr(stats, name) if stats is not None else None

        rows.append(
            {
                "data_element_id": spec.data_element_id,
                "sqlite_eligible_count": count(sqlite_stats, "eligible_record_count"),
                "sqlite_populated_count": count(sqlite_stats, "populated_count"),
                "sqlite_missing_key_count": count(sqlite_stats, "missing_key_count"),
                "sqlite_null_count": count(sqlite_stats, "null_count"),
                "sqlite_blank_count": count(sqlite_stats, "blank_count"),
                "sqlite_literal_unknown_count": count(
                    sqlite_stats, "literal_unknown_count"
                ),
                "sqlite_literal_unavailable_count": count(
                    sqlite_stats, "literal_unavailable_count"
                ),
                "sqlite_literal_not_applicable_count": count(
                    sqlite_stats, "literal_not_applicable_count"
                ),
                "sqlite_date_unavailable_count": count(
                    sqlite_stats, "date_unavailable_count"
                ),
                "sqlite_verified_zero_count": count(
                    sqlite_stats, "verified_zero_count"
                ),
                "postgresql_eligible_count": count(
                    runtime_stats, "eligible_record_count"
                ),
                "postgresql_populated_count": count(runtime_stats, "populated_count"),
                "postgresql_missing_key_count": count(
                    runtime_stats, "missing_key_count"
                ),
                "postgresql_null_count": count(runtime_stats, "null_count"),
                "postgresql_blank_count": count(runtime_stats, "blank_count"),
                "postgresql_literal_unknown_count": count(
                    runtime_stats, "literal_unknown_count"
                ),
                "postgresql_literal_unavailable_count": count(
                    runtime_stats, "literal_unavailable_count"
                ),
                "postgresql_literal_not_applicable_count": count(
                    runtime_stats, "literal_not_applicable_count"
                ),
                "postgresql_date_unavailable_count": count(
                    runtime_stats, "date_unavailable_count"
                ),
                "postgresql_verified_zero_count": count(
                    runtime_stats, "verified_zero_count"
                ),
                "parity_status": (
                    "counts match"
                    if comparable
                    else (
                        "field mapping missing from one store"
                        if not mapping_present
                        else "counts diverge"
                    )
                ),
                "gap_classification": (
                    "NOT_APPLICABLE" if comparable else "SQLITE_POSTGRES_DIVERGENCE"
                ),
                "explanation": (
                    "aggregate population and missing-value counts match"
                    if comparable
                    else (
                        "canonical field mapping is absent from one inspected store"
                        if not mapping_present
                        else (
                            "aggregate population or missing-state counts differ; compare "
                            "import scope before remediation"
                        )
                    )
                ),
            }
        )
    return tuple(rows)


def _facility_coverage_rows(
    specs: Sequence[ElementSpec],
    inventory: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    inventory_by_id = {str(row["data_element_id"]): row for row in inventory}
    rows: list[Mapping[str, Any]] = []
    for spec in sorted(specs, key=lambda item: item.data_element_id):
        recommended = str(spec.recommended_display_location)
        relevant = bool(_spec_value(spec, "facility_hub_relevant", False)) or (
            spec.ownership in {"facility", "shared"}
            and (
                spec.canonical_entity in {"facility", "facilities"}
                or "facilit" in recommended.casefold()
            )
        )
        if not relevant:
            continue
        inventory_row = inventory_by_id[spec.data_element_id]
        current_surface = str(spec.current_display_route_or_export)
        rows.append(
            {
                "data_element_id": spec.data_element_id,
                "reviewer_facing_name": spec.reviewer_facing_name,
                "source_artifact_type": spec.source_artifact_type,
                "source_field_or_extractor_reference": (
                    spec.source_field_or_extractor_reference
                ),
                "canonical_model_table_column": _canonical_reference(spec),
                "current_facility_hub_coverage": (
                    current_surface
                    if "/ccld/facilities" in current_surface
                    else "not displayed in the facility hub"
                ),
                "recommended_single_home": spec.recommended_display_location,
                "recommended_display_method": spec.recommended_display_method,
                "population_measurement_status": inventory_row[
                    "population_measurement_status"
                ],
                "population_percentage": inventory_row["population_percentage"],
                "gap_classification": inventory_row["gap_classification"],
                "priority": spec.priority,
                "evidence_reference_location": spec.evidence_reference_location,
            }
        )
    return tuple(rows)


def _complaint_coverage_rows(
    specs: Sequence[ElementSpec],
    inventory: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    inventory_by_id = {str(row["data_element_id"]): row for row in inventory}
    rows: list[Mapping[str, Any]] = []
    for spec in sorted(specs, key=lambda item: item.data_element_id):
        recommended = str(spec.recommended_display_location)
        relevant = bool(_spec_value(spec, "complaint_detail_relevant", False)) or (
            spec.ownership in {"complaint", "shared"}
            and (
                spec.canonical_entity
                in {
                    "complaint",
                    "complaints",
                    "allegation",
                    "allegations",
                    "event",
                    "events",
                    "source_document",
                    "source_documents",
                }
                or "complaint" in recommended.casefold()
                or "record" in recommended.casefold()
            )
        )
        if not relevant:
            continue
        inventory_row = inventory_by_id[spec.data_element_id]
        current_surface = str(spec.current_display_route_or_export)
        rows.append(
            {
                "data_element_id": spec.data_element_id,
                "reviewer_facing_name": spec.reviewer_facing_name,
                "source_artifact_type": spec.source_artifact_type,
                "source_field_or_extractor_reference": (
                    spec.source_field_or_extractor_reference
                ),
                "canonical_model_table_column": _canonical_reference(spec),
                "current_complaint_detail_coverage": (
                    current_surface
                    if "/reviewer/records/detail" in current_surface
                    else "not displayed in complaint detail"
                ),
                "recommended_display_location": spec.recommended_display_location,
                "recommended_display_method": spec.recommended_display_method,
                "population_measurement_status": inventory_row[
                    "population_measurement_status"
                ],
                "population_percentage": inventory_row["population_percentage"],
                "gap_classification": inventory_row["gap_classification"],
                "priority": spec.priority,
                "evidence_reference_location": spec.evidence_reference_location,
            }
        )
    return tuple(rows)


def _catalog_item_value(item: Any, name: str, default: Any = "") -> Any:
    if isinstance(item, Mapping):
        return item.get(name, default)
    return getattr(item, name, default)


def _aggregate_rows(
    *,
    mode: AuditMode,
    sqlite_snapshot: StoreSnapshot,
    runtime_snapshot: StoreSnapshot,
) -> tuple[Mapping[str, Any], ...]:
    rows: list[Mapping[str, Any]] = []
    snapshot = runtime_snapshot if mode == "runtime" else sqlite_snapshot
    if mode == "local" and not snapshot.available and runtime_snapshot.available:
        snapshot = runtime_snapshot
    for feature in sorted(
        AGGREGATE_FEATURES,
        key=lambda item: str(_catalog_item_value(item, "feature_id")),
    ):
        required_ids = tuple(
            str(value)
            for value in _catalog_item_value(feature, "required_data_elements", ())
        )
        required_stats = [snapshot.stats.get(data_id) for data_id in required_ids]
        measured_stats = [stats for stats in required_stats if stats is not None]
        configured_gap = str(
            _catalog_item_value(feature, "gap_classification", "NOT_APPLICABLE")
        )
        if not snapshot.available or not measured_stats:
            eligible_count: int | None = None
            qualifying_count: int | None = None
            readiness = "coverage unavailable"
            cause = "unavailable coverage"
            gap_classification = "AGGREGATE_DATA_INSUFFICIENT"
        else:
            eligible_count = max(stats.eligible_record_count for stats in measured_stats)
            minimum_prerequisite_population = min(
                stats.populated_count for stats in measured_stats
            )
            # Population counts do not prove that prerequisites intersect on the same rows.
            qualifying_count = None
            if len(measured_stats) != len(required_ids):
                readiness = "prerequisite field coverage incomplete"
                cause = "canonical or store mapping unavailable"
                gap_classification = "AGGREGATE_DATA_INSUFFICIENT"
            elif eligible_count == 0:
                readiness = "no eligible governed records"
                cause = "unavailable coverage; not a verified zero"
                gap_classification = "AGGREGATE_DATA_INSUFFICIENT"
            elif minimum_prerequisite_population == 0:
                readiness = "zero qualifying records is not yet defensible"
                cause = "required data element is unpopulated"
                gap_classification = "AGGREGATE_DATA_INSUFFICIENT"
            elif configured_gap != "NOT_APPLICABLE":
                readiness = "data present with known coverage limitation"
                cause = str(
                    _catalog_item_value(
                        feature,
                        "zero_or_unavailable_cause",
                        "known query or coverage limitation",
                    )
                )
                gap_classification = configured_gap
            else:
                readiness = "prerequisites populated; record-level intersection unmeasured"
                cause = "aggregate field counts do not establish qualifying-row overlap"
                gap_classification = "AGGREGATE_DATA_INSUFFICIENT"
        rows.append(
            {
                "feature_id": _catalog_item_value(feature, "feature_id"),
                "reviewer_feature": _catalog_item_value(feature, "reviewer_feature"),
                "current_route_or_export": _catalog_item_value(
                    feature, "current_route_or_export"
                ),
                "required_data_elements": "; ".join(required_ids),
                "data_store_inspected": snapshot.store,
                "eligible_record_count": eligible_count,
                "qualifying_record_count": qualifying_count,
                "readiness_status": readiness,
                "zero_or_unavailable_cause": cause,
                "gap_classification": gap_classification,
                "known_query_limit": _catalog_item_value(
                    feature, "known_query_limit", ""
                ),
                "evidence_reference_location": _catalog_item_value(
                    feature, "evidence_reference_location"
                ),
                "recommended_validation": _catalog_item_value(
                    feature, "recommended_validation"
                ),
            }
        )
    return tuple(rows)


def _gap_rows(
    specs: Sequence[ElementSpec],
    inventory: Sequence[Mapping[str, Any]],
    parity: Sequence[Mapping[str, Any]],
    aggregate_rows: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    spec_by_id = {spec.data_element_id: spec for spec in specs}
    rows: list[Mapping[str, Any]] = []
    for inventory_row in inventory:
        classification = str(inventory_row["gap_classification"])
        if classification == "NOT_APPLICABLE":
            continue
        data_element_id = str(inventory_row["data_element_id"])
        spec = spec_by_id[data_element_id]
        rows.append(
            {
                "gap_id": (
                    f"gap.{data_element_id}.{classification.casefold()}"
                ),
                "data_element_id": data_element_id,
                "gap_classification": classification,
                "title": (
                    f"{spec.reviewer_facing_name}: "
                    f"{classification.replace('_', ' ').casefold()}"
                ),
                "description": (
                    "The source-to-screen inventory records this element with the stated "
                    "classification; remediation must preserve source traceability and "
                    "missing-value semantics."
                ),
                "ownership": spec.ownership,
                "priority": spec.priority,
                "disposition": spec.disposition,
                "recommended_display_location": spec.recommended_display_location,
                "dependencies": str(_spec_value(spec, "dependencies", "")),
                "evidence_reference_location": spec.evidence_reference_location,
                "validation_requirement": str(
                    _spec_value(
                        spec,
                        "validation_requirement",
                        "Add a governed source-to-screen regression before remediation.",
                    )
                ),
            }
        )
    for item in QUERY_COVERAGE_GAPS:
        classification = str(
            _catalog_item_value(item, "gap_classification", "STORED_QUERY_OMISSION")
        )
        gap_id = str(_catalog_item_value(item, "gap_id"))
        if not gap_id:
            gap_id = "gap.query." + _source_field_id(
                str(_catalog_item_value(item, "title", "query coverage"))
            )
        rows.append(
            {
                "gap_id": gap_id,
                "data_element_id": _catalog_item_value(item, "data_element_id"),
                "gap_classification": classification,
                "title": _catalog_item_value(item, "title"),
                "description": _catalog_item_value(item, "description"),
                "ownership": _catalog_item_value(item, "ownership", "shared"),
                "priority": _catalog_item_value(item, "priority", "P1"),
                "disposition": _catalog_item_value(
                    item, "disposition", "create focused remediation issue"
                ),
                "recommended_display_location": _catalog_item_value(
                    item, "recommended_display_location", "query/service layer"
                ),
                "dependencies": _catalog_item_value(item, "dependencies", ""),
                "evidence_reference_location": _catalog_item_value(
                    item, "evidence_reference_location"
                ),
                "validation_requirement": _catalog_item_value(
                    item,
                    "validation_requirement",
                    "Exercise more records than the current query limit.",
                ),
            }
        )
    for row in parity:
        if row["gap_classification"] != "SQLITE_POSTGRES_DIVERGENCE":
            continue
        data_element_id = str(row["data_element_id"])
        spec = spec_by_id[data_element_id]
        rows.append(
            {
                "gap_id": f"gap.{data_element_id}.sqlite_postgres_divergence",
                "data_element_id": data_element_id,
                "gap_classification": "SQLITE_POSTGRES_DIVERGENCE",
                "title": f"{spec.reviewer_facing_name}: SQLite/PostgreSQL divergence",
                "description": (
                    "Aggregate eligible, populated, or missing-value counts differ between "
                    "the inspected stores."
                ),
                "ownership": spec.ownership,
                "priority": "P1",
                "disposition": "investigate import parity before UI remediation",
                "recommended_display_location": "storage/import boundary",
                "dependencies": "repeat with equivalent governed store snapshots",
                "evidence_reference_location": spec.evidence_reference_location,
                "validation_requirement": (
                    "Prove equivalent governed imports produce matching aggregate counts."
                ),
            }
        )
    for row in aggregate_rows:
        classification = str(row["gap_classification"])
        if classification == "NOT_APPLICABLE":
            continue
        feature_id = str(row["feature_id"])
        rows.append(
            {
                "gap_id": f"gap.aggregate.{feature_id}.{classification.casefold()}",
                "data_element_id": "",
                "gap_classification": classification,
                "title": f"{row['reviewer_feature']}: aggregate readiness",
                "description": (
                    "The aggregate cannot yet treat zero or unavailable output as a "
                    "complete-data result."
                ),
                "ownership": "shared",
                "priority": "P1",
                "disposition": "validate prerequisites in a focused follow-up",
                "recommended_display_location": row["current_route_or_export"],
                "dependencies": row["required_data_elements"],
                "evidence_reference_location": row["evidence_reference_location"],
                "validation_requirement": row["recommended_validation"],
            }
        )
    unique: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        gap_id = str(row["gap_id"])
        if gap_id in unique and unique[gap_id] != row:
            raise ValueError(f"Conflicting gap definitions for {gap_id}.")
        unique[gap_id] = row
    return tuple(unique[gap_id] for gap_id in sorted(unique))


def _merge_string_lists(*values: Any) -> list[str]:
    merged: set[str] = set()
    for value in values:
        if isinstance(value, str):
            if value.strip():
                merged.add(value.strip())
        elif isinstance(value, Sequence):
            merged.update(str(item).strip() for item in value if str(item).strip())
    return sorted(merged)


def deduplicate_recommended_issues(
    issues: Iterable[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    """Deduplicate proposed issues without creating or mutating external issues."""

    deduplicated: dict[str, dict[str, Any]] = {}
    for issue in issues:
        title = " ".join(str(issue.get("title", "")).split())
        key = title.casefold()
        if not key:
            raise ValueError("Recommended issues require a title.")
        candidate = dict(issue)
        candidate["title"] = title
        if key not in deduplicated:
            candidate["labels"] = _merge_string_lists(candidate.get("labels", ()))
            candidate["dependencies"] = _merge_string_lists(
                candidate.get("dependencies", ())
            )
            candidate["related_gap_identifiers"] = _merge_string_lists(
                candidate.get("related_gap_identifiers", ())
            )
            candidate["acceptance_criteria"] = _merge_string_lists(
                candidate.get("acceptance_criteria", ())
            )
            candidate["validation_requirements"] = _merge_string_lists(
                candidate.get("validation_requirements", ())
            )
            deduplicated[key] = candidate
            continue
        existing = deduplicated[key]
        for field in (
            "labels",
            "dependencies",
            "related_gap_identifiers",
            "acceptance_criteria",
            "validation_requirements",
        ):
            existing[field] = _merge_string_lists(
                existing.get(field, ()), candidate.get(field, ())
            )
    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    return tuple(
        sorted(
            deduplicated.values(),
            key=lambda item: (
                priority_order.get(str(item.get("priority")), 9),
                str(item.get("issue_id", "")),
                str(item["title"]),
            ),
        )
    )


def _recommended_issues(
    specs: Sequence[ElementSpec],
    gaps: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    ownership_by_id = {spec.data_element_id: spec.ownership for spec in specs}

    def related(
        classifications: set[str],
        *,
        ownership: str | None = None,
    ) -> list[str]:
        return sorted(
            str(gap["gap_id"])
            for gap in gaps
            if str(gap["gap_classification"]) in classifications
            and (
                ownership is None
                or ownership_by_id.get(str(gap.get("data_element_id")), "shared")
                in {ownership, "shared"}
            )
        )

    common_labels = ["data-completeness", "source-to-screen"]
    issue_specs = (
        {
            "issue_id": "source-to-screen.raw-artifact-extraction",
            "title": "Close governed raw-artifact and extraction gaps",
            "body": (
                "Add deterministic extraction only for reviewer-relevant fields proven "
                "present in governed raw artifacts. Preserve raw source traceability."
            ),
            "labels": common_labels + ["extraction"],
            "priority": "P0",
            "dependencies": [],
            "related_gap_identifiers": related(
                {"SOURCE_NOT_PROVIDED", "RAW_PRESENT_EXTRACTION_MISSING"}
            ),
            "acceptance_criteria": [
                "Every selected raw field has a fixture-based extraction regression.",
                "Unavailable source coverage remains distinct from an extracted blank.",
            ],
            "validation_requirements": [
                "Run complaint and facility source fixture tests.",
            ],
        },
        {
            "issue_id": "source-to-screen.canonical-allocation",
            "title": "Allocate extracted fields to canonical storage deliberately",
            "body": (
                "Resolve canonical allocation and schema gaps in a separately reviewed "
                "change that updates contracts, mappings, migrations, and fixtures together."
            ),
            "labels": common_labels + ["schema"],
            "priority": "P0",
            "dependencies": ["source-to-screen.raw-artifact-extraction"],
            "related_gap_identifiers": related(
                {
                    "EXTRACTED_CANONICAL_MAPPING_MISSING",
                    "CANONICAL_IMPORT_NOT_POPULATED",
                }
            ),
            "acceptance_criteria": [
                "Canonical allocation is documented in DATA_CONTRACT.md.",
                "Import and initialization behavior populate the governed field.",
            ],
            "validation_requirements": [
                "Run schema, importer, and fixture regression suites.",
            ],
        },
        {
            "issue_id": "source-to-screen.store-parity",
            "title": "Enforce SQLite and PostgreSQL import parity",
            "body": (
                "Compare equivalent governed imports using aggregate counts and fix only "
                "confirmed adapter or import divergence."
            ),
            "labels": common_labels + ["database"],
            "priority": "P0",
            "dependencies": ["source-to-screen.canonical-allocation"],
            "related_gap_identifiers": related(
                {"SQLITE_POSTGRES_DIVERGENCE", "FIXTURE_RUNTIME_DIVERGENCE"}
            ),
            "acceptance_criteria": [
                "Equivalent governed data yields matching eligible and populated counts.",
            ],
            "validation_requirements": [
                "Run adapter parity tests against SQLite and PostgreSQL-style storage.",
            ],
        },
        {
            "issue_id": "source-to-screen.facility-hub",
            "title": "Complete the facility hub with one home per reviewer fact",
            "body": (
                "Display only appropriate reviewer-facing facility facts at a single "
                "deliberate home after source, canonical, and query coverage are proven."
            ),
            "labels": common_labels + ["facility-hub"],
            "priority": "P1",
            "dependencies": ["source-to-screen.store-parity"],
            "related_gap_identifiers": related(
                {"UI_DISPLAY_OMISSION", "STORED_QUERY_OMISSION"},
                ownership="facility",
            ),
            "acceptance_criteria": [
                "Each selected facility fact has one reviewer-facing home.",
                "Technical source internals remain outside the primary reviewer page.",
            ],
            "validation_requirements": [
                "Run hosted facility lookup and accessibility tests.",
            ],
        },
        {
            "issue_id": "source-to-screen.complaint-detail",
            "title": "Complete reviewer-relevant complaint detail coverage",
            "body": (
                "Expose confirmed stored complaint facts in the appropriate attorney-tier "
                "workflow without adding raw technical traceability dumps."
            ),
            "labels": common_labels + ["complaint-detail"],
            "priority": "P1",
            "dependencies": ["source-to-screen.store-parity"],
            "related_gap_identifiers": related(
                {"UI_DISPLAY_OMISSION", "STORED_QUERY_OMISSION"},
                ownership="complaint",
            ),
            "acceptance_criteria": [
                "Stored reviewer-relevant fields are shown or explicitly dispositioned.",
                "Complaint detail stays within the attorney/reviewer information tier.",
            ],
            "validation_requirements": [
                "Run hosted reviewer detail and export tests.",
            ],
        },
        {
            "issue_id": "source-to-screen.aggregate-readiness",
            "title": "Make reviewer aggregate outputs data-ready",
            "body": (
                "Prove denominator, query-range, source-coverage, and zero semantics for "
                "current priorities, trends, topic review, and exports."
            ),
            "labels": common_labels + ["aggregates"],
            "priority": "P1",
            "dependencies": ["source-to-screen.store-parity"],
            "related_gap_identifiers": related(
                {"AGGREGATE_DATA_INSUFFICIENT", "STORED_QUERY_OMISSION"}
            ),
            "acceptance_criteria": [
                "Every zero-only or unavailable aggregate reports an explicit cause.",
                "Query limits cannot silently exclude otherwise eligible records.",
            ],
            "validation_requirements": [
                "Run aggregate tests with zero, unavailable, and over-limit data sets.",
            ],
        },
        {
            "issue_id": "source-to-screen.blank-prevention",
            "title": "Prevent unexplained reviewer-facing blank values",
            "body": (
                "Preserve blank, null, unavailable, not applicable, undated, and verified "
                "zero as distinct states from import through presentation."
            ),
            "labels": common_labels + ["data-quality"],
            "priority": "P1",
            "dependencies": ["source-to-screen.canonical-allocation"],
            "related_gap_identifiers": related({"UNEXPLAINED_BLANK"}),
            "acceptance_criteria": [
                "Blank cells have a governed meaning or are replaced by an explicit state.",
                "Malformed or absent values are never coerced to numeric zero.",
            ],
            "validation_requirements": [
                "Run null-semantics and hosted rendering regressions.",
            ],
        },
        {
            "issue_id": "source-to-screen.continuous-audit",
            "title": "Automate source-to-screen coverage reporting",
            "body": (
                "Run the aggregate-only audit against governed local fixtures and the "
                "deployed database without retaining record values or source bodies."
            ),
            "labels": common_labels + ["testing"],
            "priority": "P2",
            "dependencies": [],
            "related_gap_identifiers": sorted(str(gap["gap_id"]) for gap in gaps),
            "acceptance_criteria": [
                "Audit output ordering and identifiers are deterministic.",
                "Runtime reports contain only aggregate counts and safe metadata.",
            ],
            "validation_requirements": [
                "Run redaction, determinism, and path-portability tests.",
            ],
        },
    )
    return deduplicate_recommended_issues(issue_specs)


def _manifest(
    *,
    mode: AuditMode,
    generated_at: datetime,
    observations: Sequence[SourceObservation],
    sqlite_snapshot: StoreSnapshot,
    runtime_snapshot: StoreSnapshot,
    inventory: Sequence[Mapping[str, Any]],
    gaps: Sequence[Mapping[str, Any]],
    parity_written: bool,
) -> Mapping[str, Any]:
    output_files = list(MANDATORY_OUTPUTS)
    if parity_written:
        output_files.append(PARITY_OUTPUT)
    return {
        "audit_schema_version": AUDIT_SCHEMA_VERSION,
        "mode": mode,
        "generated_at_utc": generated_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "guardrails": {
            "network_required": False if mode == "local" else None,
            "record_values_emitted": False,
            "source_document_bodies_emitted": False,
            "connection_strings_emitted": False,
            "private_urls_emitted": False,
            "raw_filesystem_paths_emitted": False,
            "synthetic_fallback_substitution": False,
        },
        "sources": [
            {
                "source_id": observation.source_id,
                "inspected": observation.inspected,
                "artifact_count": observation.artifact_count,
                "usable_artifact_count": observation.usable_artifact_count,
                "unavailable_artifact_count": observation.unavailable_artifact_count,
                "safe_note": observation.safe_note,
            }
            for observation in sorted(observations, key=lambda item: item.source_id)
        ],
        "stores": [
            {
                "store": snapshot.store,
                "inspected": snapshot.available,
                "inspection_status": snapshot.inspection_status,
                "measured_data_element_count": len(snapshot.stats),
                "safe_metadata": dict(sorted(snapshot.safe_metadata.items())),
            }
            for snapshot in (sqlite_snapshot, runtime_snapshot)
        ],
        "inventory_count": len(inventory),
        "gap_count": len(gaps),
        "gap_classifications": list(GAP_CLASSIFICATIONS),
        "output_files": sorted(output_files),
    }


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def _write_csv(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
    fieldnames: Sequence[str],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            safe_row = sanitize_payload(dict(row))
            writer.writerow({name: _csv_value(safe_row.get(name)) for name in fieldnames})


def _write_json(path: Path, payload: Any) -> None:
    safe_payload = sanitize_payload(payload)
    path.write_text(
        json.dumps(safe_payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _summary_markdown(result: AuditResult) -> str:
    gap_counts = Counter(
        str(row["gap_classification"]) for row in result.gap_register
    )
    stores = result.manifest["stores"]
    sources = result.manifest["sources"]
    lines = [
        "# Source-to-screen audit summary",
        "",
        f"- Mode: `{result.manifest['mode']}`",
        f"- Generated at (UTC): `{result.manifest['generated_at_utc']}`",
        f"- Inventoried data elements: {len(result.inventory)}",
        f"- Classified gap entries: {len(result.gap_register)}",
        f"- Recommended focused issues: {len(result.recommended_issues)}",
        "",
        "## Inspection scope",
        "",
        "| Source or store | Inspected | Safe aggregate status |",
        "| --- | --- | --- |",
    ]
    for source in sources:
        lines.append(
            "| "
            + _markdown_cell(source["source_id"])
            + " | "
            + ("yes" if source["inspected"] else "no")
            + " | "
            + _markdown_cell(source["safe_note"])
            + " |"
        )
    for store in stores:
        lines.append(
            "| "
            + _markdown_cell(store["store"])
            + " | "
            + ("yes" if store["inspected"] else "no")
            + " | "
            + _markdown_cell(store["inspection_status"])
            + " |"
        )
    lines.extend(
        [
            "",
            "## Gap categories",
            "",
            "| Classification | Count |",
            "| --- | ---: |",
        ]
    )
    for classification in GAP_CLASSIFICATIONS:
        if gap_counts[classification]:
            lines.append(f"| `{classification}` | {gap_counts[classification]} |")
    lines.extend(
        [
            "",
            "## Population semantics",
            "",
            "Null, blank, unknown, unavailable, not applicable, undated, and verified "
            "numeric zero are counted separately. A missing or uninspected source is "
            "reported as unavailable coverage, never as zero.",
            "",
            "## Safety",
            "",
            "This report contains field identities, classifications, aggregate counts, "
            "percentages, safe repository references, and safe metadata only. It does not "
            "contain complaint narratives, source bodies, connection strings, private URLs, "
            "secrets, or raw filesystem paths.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_outputs(output_dir: Path, result: AuditResult) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for output_name in (*MANDATORY_OUTPUTS, PARITY_OUTPUT):
        output_path = output_dir / output_name
        if output_path.exists() and output_path.is_file():
            output_path.unlink()
    _write_json(output_dir / "manifest.json", result.manifest)
    _write_csv(
        output_dir / "data-element-inventory.csv",
        result.inventory,
        INVENTORY_FIELDNAMES,
    )
    _write_json(output_dir / "data-element-inventory.json", list(result.inventory))
    _write_csv(
        output_dir / "population-summary.csv",
        result.population_summary,
        POPULATION_FIELDNAMES,
    )
    _write_csv(
        output_dir / "null-semantics.csv",
        result.null_semantics,
        NULL_SEMANTICS_FIELDNAMES,
    )
    if PARITY_OUTPUT in result.manifest["output_files"]:
        _write_csv(output_dir / PARITY_OUTPUT, result.parity, PARITY_FIELDNAMES)
    _write_csv(
        output_dir / "facility-hub-coverage.csv",
        result.facility_hub_coverage,
        FACILITY_COVERAGE_FIELDNAMES,
    )
    _write_csv(
        output_dir / "complaint-detail-coverage.csv",
        result.complaint_detail_coverage,
        COMPLAINT_COVERAGE_FIELDNAMES,
    )
    _write_csv(
        output_dir / "aggregate-feature-readiness.csv",
        result.aggregate_feature_readiness,
        AGGREGATE_FIELDNAMES,
    )
    _write_csv(
        output_dir / "gap-register.csv",
        result.gap_register,
        GAP_FIELDNAMES,
    )
    _write_json(output_dir / "recommended-issues.json", list(result.recommended_issues))
    (output_dir / "summary.md").write_text(
        sanitize_payload(_summary_markdown(result)),
        encoding="utf-8",
    )


def _markdown_cell(value: Any) -> str:
    return (
        str(value)
        .replace("|", "\\|")
        .replace("\r", " ")
        .replace("\n", " ")
        .strip()
    )


def _tracked_inventory_markdown(result: AuditResult) -> str:
    lines = [
        "# Source-to-screen inventory",
        "",
        "This tracked inventory is the structural baseline for the repeatable audit. It "
        "contains field identities and dispositions, not source record values or runtime "
        "population counts.",
        "",
        "The generated audit under `data/processed/source-to-screen-audit/` is the authority "
        "for environment-specific aggregate population measurements.",
        "",
        (
            "| Data element | Ownership | Source or extractor reference | Canonical "
            "allocation | Current home | Classification | Priority |"
        ),
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in result.inventory:
        lines.append(
            "| `"
            + _markdown_cell(row["data_element_id"])
            + "` | "
            + _markdown_cell(row["ownership"])
            + " | "
            + _markdown_cell(row["source_field_or_extractor_reference"])
            + " | `"
            + _markdown_cell(row["canonical_model_table_column"])
            + "` | "
            + _markdown_cell(row["current_display_route_or_export"] or "not displayed")
            + " | `"
            + _markdown_cell(row["gap_classification"])
            + "` | "
            + _markdown_cell(row["priority"])
            + " |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "`NOT_APPLICABLE` means the audit found no action represented by the selected "
            "primary classification. `INTENTIONALLY_INTERNAL` records a deliberate "
            "attorney-tier boundary; it is not permission to expose technical metadata in "
            "the primary reviewer workflow.",
            "",
        ]
    )
    return "\n".join(lines)


def _tracked_gap_markdown(result: AuditResult) -> str:
    lines = [
        "# Source-to-screen gap register",
        "",
        "This register records stable, structural gap identifiers. Generated audit reports "
        "supply aggregate counts for the inspected environment; this tracked file does not "
        "contain record values or environment-specific paths.",
        "",
        "| Gap | Classification | Data element | Priority | Disposition | Evidence |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in result.gap_register:
        lines.append(
            "| `"
            + _markdown_cell(row["gap_id"])
            + "` | `"
            + _markdown_cell(row["gap_classification"])
            + "` | `"
            + _markdown_cell(row["data_element_id"] or "aggregate/query")
            + "` | "
            + _markdown_cell(row["priority"])
            + " | "
            + _markdown_cell(row["disposition"])
            + " | `"
            + _markdown_cell(row["evidence_reference_location"])
            + "` |"
        )
    lines.extend(
        [
            "",
            "## Classification rule",
            "",
            "A populated reviewer-relevant source element must have a deliberate "
            "reviewer-facing home or a specific extraction, mapping, import, query, or "
            "presentation classification. Missing coverage is never represented as a "
            "numeric zero.",
            "",
        ]
    )
    return "\n".join(lines)


def _tracked_remediation_markdown(result: AuditResult) -> str:
    lines = [
        "# Source-to-screen remediation plan",
        "",
        "The audit proposes these deduplicated follow-up groups. This document is planning "
        "output only: it does not create GitHub issues and does not authorize broad "
        "remediation in the audit-foundation change.",
        "",
    ]
    for issue in result.recommended_issues:
        lines.extend(
            [
                f"## {issue['priority']}: {issue['title']}",
                "",
                str(issue["body"]),
                "",
                "Dependencies:",
                "",
            ]
        )
        dependencies = issue["dependencies"] or ["None."]
        lines.extend(f"- `{value}`" for value in dependencies)
        lines.extend(["", "Acceptance criteria:", ""])
        lines.extend(f"- {value}" for value in issue["acceptance_criteria"])
        lines.extend(["", "Validation:", ""])
        lines.extend(f"- {value}" for value in issue["validation_requirements"])
        lines.extend(["", "Related stable gaps:", ""])
        related_gaps = issue["related_gap_identifiers"] or [
            "No current structural gap; retain as an audit coverage workstream."
        ]
        lines.extend(f"- `{value}`" for value in related_gaps)
        lines.append("")
    return "\n".join(lines)


def _tracked_audit_markdown() -> str:
    outputs = "\n".join(f"- `{name}`" for name in (*MANDATORY_OUTPUTS, PARITY_OUTPUT))
    classifications = "\n".join(f"- `{name}`" for name in GAP_CLASSIFICATIONS)
    local_command = (
        ".\\.venv\\Scripts\\python.exe -m ccld_complaints.source_to_screen_audit "
        "--mode local --output-dir "
        "data/processed/source-to-screen-audit/local-pre-pr "
        "--write-tracked-baseline"
    )
    runtime_command = (
        "docker compose -f docker-compose.qnap.yml exec app python -m "
        "ccld_complaints.source_to_screen_audit --mode runtime --output-dir "
        "/app/data/processed/source-to-screen-audit/runtime-post-deploy"
    )
    return f"""# Source-to-screen audit

The source-to-screen audit inventories complaint, facility, and shared fields from
repository contracts through storage and current reviewer surfaces. It is diagnostic and
aggregate-only; it does not remediate identified product gaps.

## Local audit

From a PowerShell prompt:

```powershell
Set-Location '<Repo Path>\\'
{local_command}
```

Local mode inspects repository schemas, explicit mappings, retained representative
artifacts, governed fixtures, and the configured SQLite file when it exists. It never
silently substitutes tiny fixtures for unavailable configured data and does not require
network access.

## Runtime audit

Run this inside the deployed application container:

```sh
{runtime_command}
```

Runtime mode requires the configured PostgreSQL database. Its queries return aggregate
population counts only. The generated files must stay in the ignored processed-data
directory and must not be committed.

## Generated outputs

{outputs}

`sqlite-postgres-parity.csv` is emitted only when both stores are available in the same
audit invocation. All other files are emitted on every successful run.

## Missing-value rules

- Numeric zero is counted only when the stored scalar is a verified numeric zero.
- Null and missing JSON keys are measured separately.
- Empty and whitespace-only strings are blank.
- Literal unknown, unavailable, not applicable, and undated states remain distinct.
- Uninspected and missing source coverage is unavailable, never zero.
- Always-null and nearly-always-null fields are flagged for follow-up.

## Classifications

{classifications}

## Safety boundary

Reports contain stable field and gap identifiers, classifications, aggregate counts,
percentages, reviewer routes, and repository-relative evidence references. They exclude
complaint narratives, source-document bodies, record values, connection strings, tokens,
cookies, private URLs, and raw filesystem paths. Baseline generation is local-only.

## Interpretation limits

- Retained artifacts and governed fixtures establish discovery coverage; they are not
  silently treated as production population data.
- An unavailable SQLite database produces explicit unavailable coverage.
- The audit records known route/query consumers from a reviewed explicit registry; it does
  not scrape rendered reviewer pages or retain HTML.
- Aggregate readiness is conservative: missing prerequisite coverage is not a defensible
  zero.
- Standard local and runtime modes do not compare fixture rows directly. The
  `FIXTURE_RUNTIME_DIVERGENCE` classification is available for an equivalent governed
  cross-store comparison, but the audit does not infer that divergence from unrelated
  fixture and runtime scopes.
- PostgreSQL JSON population queries require confirmation through the post-deployment
  runtime command; local adapter tests use SQLite JSON support.
"""


def _write_tracked_baseline(repo_root: Path, result: AuditResult) -> None:
    baseline_dir = repo_root / TRACKED_BASELINE_DIR
    baseline_dir.mkdir(parents=True, exist_ok=True)
    documents = {
        "source-to-screen-inventory.md": _tracked_inventory_markdown(result),
        "source-to-screen-gap-register.md": _tracked_gap_markdown(result),
        "source-to-screen-remediation-plan.md": _tracked_remediation_markdown(result),
        "source-to-screen-audit.md": _tracked_audit_markdown(),
    }
    for name, content in sorted(documents.items()):
        safe_content = sanitize_payload(content)
        if "C:\\Users\\" in safe_content or "C:/Users/" in safe_content:
            raise ValueError("Tracked source-to-screen documents contain a user path.")
        (baseline_dir / name).write_text(safe_content, encoding="utf-8")


class AuditExecutionError(RuntimeError):
    """A safe, user-facing audit execution failure."""


def _runtime_source_observations() -> tuple[SourceObservation, ...]:
    return tuple(
        SourceObservation(
            source_id=source_id,
            inspected=False,
            artifact_count=0,
            usable_artifact_count=0,
            unavailable_artifact_count=0,
            field_counts={},
            eligible_counts={},
            safe_note="not inspected in runtime mode; database aggregates only",
        )
        for source_id in (
            "governed_complaint_fixtures",
            "governed_facility_fixtures",
            "governed_facility_page_fixtures",
            "retained_facility_reference_artifacts",
            "retained_raw_complaint_artifacts",
        )
    )


def run_audit(
    *,
    mode: AuditMode,
    output_dir: Path,
    write_tracked_baseline: bool = False,
    repo_root: Path | None = None,
    generated_at: datetime | None = None,
    environ: Mapping[str, str] | None = None,
    runtime_connection: Connection | None = None,
) -> AuditResult:
    """Run a local or aggregate-only runtime audit and write deterministic artifacts."""

    if mode not in {"local", "runtime"}:
        raise ValueError("Audit mode must be local or runtime.")
    if mode == "runtime" and write_tracked_baseline:
        raise AuditExecutionError("Tracked baseline generation is local-only.")
    root = (repo_root or Path(__file__).resolve().parents[2]).resolve()
    environment = environ if environ is not None else os.environ
    specs = (
        discover_element_specs(root)
        if mode == "local"
        else discover_element_specs(root, include_retained_artifacts=False)
    )
    if not specs:
        raise AuditExecutionError("No source-to-screen catalog elements were discovered.")

    if mode == "local":
        configured_sqlite = Path(
            environment.get(SQLITE_PATH_ENV, str(DEFAULT_SQLITE_PATH))
        )
        if not configured_sqlite.is_absolute():
            configured_sqlite = root / configured_sqlite
        sqlite_snapshot = inspect_sqlite_store(configured_sqlite, specs)
        observations = _source_observations(root)
        if runtime_connection is not None:
            runtime_snapshot = inspect_runtime_store(runtime_connection, specs)
        else:
            runtime_snapshot = _unavailable_runtime_snapshot(
                "PostgreSQL not inspected in local mode"
            )
    else:
        configured_runtime_sqlite = environment.get(SQLITE_PATH_ENV)
        if configured_runtime_sqlite:
            runtime_sqlite_path = Path(configured_runtime_sqlite)
            if not runtime_sqlite_path.is_absolute():
                runtime_sqlite_path = root / runtime_sqlite_path
            sqlite_snapshot = inspect_sqlite_store(runtime_sqlite_path, specs)
        else:
            sqlite_snapshot = StoreSnapshot(
                store="sqlite",
                available=False,
                inspection_status="SQLite not explicitly configured in runtime mode",
                stats={},
                safe_metadata={"table_count": 0},
            )
        observations = _runtime_source_observations()
        if runtime_connection is not None:
            runtime_snapshot = inspect_runtime_store(runtime_connection, specs)
        else:
            engine: Engine | None = None
            try:
                engine = _runtime_engine(environment)
                if engine.dialect.name != "postgresql":
                    raise AuditExecutionError(
                        "Runtime mode requires the configured PostgreSQL database."
                    )
                with engine.connect() as connection:
                    runtime_snapshot = inspect_runtime_store(connection, specs)
            except HostedDatabaseConfigError as exc:
                raise AuditExecutionError(
                    "Runtime mode requires a configured PostgreSQL database."
                ) from exc
            except SQLAlchemyError as exc:
                raise AuditExecutionError(
                    "The configured runtime database could not be inspected safely."
                ) from exc
            finally:
                if engine is not None:
                    engine.dispose()

    inventory = _inventory_rows(
        specs,
        observations=observations,
        sqlite_snapshot=sqlite_snapshot,
        runtime_snapshot=runtime_snapshot,
        mode=mode,
    )
    population = _population_rows(specs, (sqlite_snapshot, runtime_snapshot))
    null_semantics = _null_semantics_rows(specs)
    parity = _parity_rows(specs, sqlite_snapshot, runtime_snapshot)
    facility_coverage = _facility_coverage_rows(specs, inventory)
    complaint_coverage = _complaint_coverage_rows(specs, inventory)
    aggregate_rows = _aggregate_rows(
        mode=mode,
        sqlite_snapshot=sqlite_snapshot,
        runtime_snapshot=runtime_snapshot,
    )
    gaps = _gap_rows(specs, inventory, parity, aggregate_rows)
    issues = _recommended_issues(specs, gaps)
    audit_time = generated_at or datetime.now(UTC)
    if audit_time.tzinfo is None:
        audit_time = audit_time.replace(tzinfo=UTC)
    manifest = _manifest(
        mode=mode,
        generated_at=audit_time,
        observations=observations,
        sqlite_snapshot=sqlite_snapshot,
        runtime_snapshot=runtime_snapshot,
        inventory=inventory,
        gaps=gaps,
        parity_written=sqlite_snapshot.available and runtime_snapshot.available,
    )
    result = AuditResult(
        manifest=manifest,
        inventory=inventory,
        population_summary=population,
        null_semantics=null_semantics,
        parity=parity,
        facility_hub_coverage=facility_coverage,
        complaint_detail_coverage=complaint_coverage,
        aggregate_feature_readiness=aggregate_rows,
        gap_register=gaps,
        recommended_issues=issues,
    )
    effective_output_dir = output_dir
    if not effective_output_dir.is_absolute():
        effective_output_dir = root / effective_output_dir
    _write_outputs(effective_output_dir, result)
    if write_tracked_baseline:
        _write_tracked_baseline(root, result)
    return result


class CoverageContractError(RuntimeError):
    """A controlled coverage-contract validation or generation failure."""


_COVERAGE_SAFE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._:-]*$")
_COVERAGE_FACILITY_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_COVERAGE_TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
)
_COVERAGE_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COVERAGE_HTML_RE = re.compile(r"(?i)<(?:!doctype|html|body|script|style|[a-z]+\s+[^>]*)")
_COVERAGE_SQL_RE = re.compile(
    r"(?is)\b(?:select\s+.+\s+from|insert\s+into|delete\s+from|"
    r"update\s+.+\s+set|create\s+table)\b"
)
_COVERAGE_STACK_RE = re.compile(
    r"(?i)(?:traceback \(most recent call last\)|stack trace|"
    r"\b(?:exception|error)\s*:\s*.+)"
)
_COVERAGE_PROHIBITED_KEY_PARTS = (
    "narrative",
    "raw_html",
    "source_body",
    "source_url",
    "raw_path",
    "absolute_path",
    "private_url",
    "connection_string",
    "credential",
    "password",
    "token",
    "cookie",
    "authentication_claim",
    "stack_trace",
    "sql_text",
    "container_name",
    "database_host",
    "qnap",
)
_COVERAGE_AVAILABILITY_REASON_CATEGORIES = (
    "none",
    "fixture_not_provided",
    "read_boundary_unavailable",
    "stage_unavailable",
    "not_applicable",
)


def _coverage_mapping(value: Any, *, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise CoverageContractError(f"{context} must be an object.")
    return cast(Mapping[str, Any], value)


def _coverage_sequence(value: Any, *, context: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise CoverageContractError(f"{context} must be an array.")
    return value


def _coverage_exact_keys(
    value: Mapping[str, Any],
    *,
    context: str,
    required: Sequence[str],
    optional: Sequence[str] = (),
) -> None:
    allowed = set(required) | set(optional)
    if set(value) - allowed:
        raise CoverageContractError(f"{context} contains a prohibited or unknown field.")
    if set(required) - set(value):
        raise CoverageContractError(f"{context} is missing a required field.")


def _reject_prohibited_coverage_content(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized_key = str(key).casefold()
            if any(part in normalized_key for part in _COVERAGE_PROHIBITED_KEY_PARTS):
                raise CoverageContractError("Coverage input contains a prohibited field.")
            _reject_prohibited_coverage_content(item)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for item in value:
            _reject_prohibited_coverage_content(item)
        return
    if not isinstance(value, str):
        return
    if (
        _CONNECTION_STRING_RE.search(value)
        or _SECRET_ASSIGNMENT_RE.search(value)
        or _URL_RE.search(value)
        or _ABSOLUTE_WINDOWS_PATH_RE.search(value)
        or _ABSOLUTE_PRIVATE_POSIX_PATH_RE.search(value)
        or _COVERAGE_HTML_RE.search(value)
        or _COVERAGE_SQL_RE.search(value)
        or _COVERAGE_STACK_RE.search(value)
    ):
        raise CoverageContractError("Coverage input contains prohibited content.")


def _coverage_identifier(value: Any, *, context: str) -> str:
    if not isinstance(value, str) or not _COVERAGE_SAFE_ID_RE.fullmatch(value):
        raise CoverageContractError(f"{context} must be a stable safe identifier.")
    return value


def _coverage_timestamp(value: Any, *, context: str, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not _COVERAGE_TIMESTAMP_RE.fullmatch(value):
        raise CoverageContractError(f"{context} must be a UTC timestamp in Z form.")
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError as exc:
        raise CoverageContractError(
            f"{context} must be a valid UTC timestamp in Z form."
        ) from exc
    return value


def _coverage_count(value: Any, *, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CoverageContractError(f"{context} must be a nonnegative integer.")
    return value


def _coverage_enum(value: Any, allowed: Sequence[str], *, context: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise CoverageContractError(f"{context} contains an unsupported value.")
    return value


def _canonical_json_text(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise CoverageContractError("Coverage data is not canonical JSON.") from exc


def _canonical_json_bytes(value: Any) -> bytes:
    return (_canonical_json_text(value) + "\n").encode("utf-8")


def _coverage_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _deep_merge_coverage_fixture(
    base: Mapping[str, Any], override: Mapping[str, Any]
) -> dict[str, Any]:
    merged: dict[str, Any] = dict(base)
    for key, value in override.items():
        existing = merged.get(key)
        if isinstance(existing, Mapping) and isinstance(value, Mapping):
            merged[key] = _deep_merge_coverage_fixture(
                cast(Mapping[str, Any], existing),
                cast(Mapping[str, Any], value),
            )
        else:
            merged[key] = value
    return merged


def load_coverage_fixture_scenario(path: Path, scenario: str) -> Mapping[str, Any]:
    """Load one named deterministic scenario without exposing fixture paths in output."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CoverageContractError("The governed coverage fixture could not be loaded.") from exc
    bundle = _coverage_mapping(payload, context="coverage fixture bundle")
    _coverage_exact_keys(
        bundle,
        context="coverage fixture bundle",
        required=("fixture_bundle_id", "base", "scenarios"),
    )
    _coverage_identifier(bundle["fixture_bundle_id"], context="fixture_bundle_id")
    scenarios = _coverage_mapping(bundle["scenarios"], context="coverage scenarios")
    if scenario not in scenarios:
        raise CoverageContractError("The requested governed fixture scenario is unavailable.")
    base = _coverage_mapping(bundle["base"], context="coverage fixture base")
    override = _coverage_mapping(scenarios[scenario], context="coverage fixture scenario")
    merged = _deep_merge_coverage_fixture(base, override)
    merged["fixture_id"] = _coverage_identifier(scenario, context="fixture scenario")
    _reject_prohibited_coverage_content(merged)
    return merged


def _coverage_generated_at(value: datetime | None) -> str:
    generated_at = value or datetime.now(UTC)
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=UTC)
    generated_at = generated_at.astimezone(UTC).replace(microsecond=0)
    return generated_at.strftime("%Y-%m-%dT%H:%M:%SZ")


def _terminal_from_catalog_gap(gap_classification: str) -> str:
    mapping = {
        "SOURCE_NOT_PROVIDED": "source_label_absent",
        "RAW_PRESENT_EXTRACTION_MISSING": "present_but_not_extracted",
        "EXTRACTED_CANONICAL_MAPPING_MISSING": "extracted_but_not_allocated",
        "CANONICAL_IMPORT_NOT_POPULATED": "allocated_but_not_imported",
        "SQLITE_POSTGRES_DIVERGENCE": "allocated_but_not_imported",
        "STORED_QUERY_OMISSION": "stored_but_not_read",
        "UI_DISPLAY_OMISSION": "read_but_not_rendered",
        "UNEXPLAINED_BLANK": "present_blank",
        "AGGREGATE_DATA_INSUFFICIENT": "source_artifact_unavailable",
        "FIXTURE_RUNTIME_DIVERGENCE": "conflicting_sources",
        "INTENTIONALLY_INTERNAL": "intentionally_internal",
        "NOT_APPLICABLE": "present_and_populated",
    }
    try:
        return mapping[gap_classification]
    except KeyError as exc:
        raise CoverageContractError(
            "The governed inventory contains an unsupported gap classification."
        ) from exc


def _terminal_stage_states(
    classification: str,
    *,
    complaint_page_required: bool,
    facility_hub_required: bool,
) -> Mapping[str, str | None]:
    states: dict[str, str | None] = {stage: "skipped" for stage in COVERAGE_STAGES}
    if classification == "not_applicable":
        return {stage: None for stage in COVERAGE_STAGES}
    if classification == "source_artifact_unavailable":
        return {stage: "unavailable" for stage in COVERAGE_STAGES}
    if classification == "present_blank":
        states["source_presence"] = "blank"
    elif classification == "source_label_absent":
        states["source_presence"] = "absent"
    elif classification == "unsupported_layout":
        states["source_presence"] = "successful"
        states["extraction"] = "unsupported"
    elif classification == "conflicting_sources":
        states["source_presence"] = "conflict"
    else:
        failure_stage = {
            "present_but_not_extracted": "extraction",
            "extracted_but_not_allocated": "canonical_allocation",
            "allocated_but_not_imported": "postgresql_population",
            "stored_but_not_read": "read_model_exposure",
        }.get(classification)
        for stage in COVERAGE_STAGES:
            if stage in {"complaint_page_rendering", "facility_hub_rendering"}:
                continue
            if failure_stage is None or COVERAGE_STAGES.index(stage) < COVERAGE_STAGES.index(
                failure_stage
            ):
                states[stage] = "successful"
            elif stage == failure_stage:
                states[stage] = "failure"
        if classification in {
            "present_and_populated",
            "read_but_not_rendered",
            "rendered_incorrectly",
            "intentionally_internal",
        }:
            for stage in COVERAGE_STAGES[:6]:
                states[stage] = "successful"

    if complaint_page_required:
        states["complaint_page_rendering"] = (
            "failure"
            if classification in {"read_but_not_rendered", "rendered_incorrectly"}
            else states["complaint_page_rendering"]
        )
        if classification in {"present_and_populated", "intentionally_internal"}:
            states["complaint_page_rendering"] = "successful"
    else:
        states["complaint_page_rendering"] = None
    if facility_hub_required:
        states["facility_hub_rendering"] = (
            "failure"
            if classification in {"read_but_not_rendered", "rendered_incorrectly"}
            else states["facility_hub_rendering"]
        )
        if classification in {"present_and_populated", "intentionally_internal"}:
            states["facility_hub_rendering"] = "successful"
    else:
        states["facility_hub_rendering"] = None
    if classification == "intentionally_internal":
        states["complaint_page_rendering"] = None
        states["facility_hub_rendering"] = None
    return states


def _coverage_rows_from_inventory(
    specs: Sequence[ElementSpec], coverage_input: Mapping[str, Any]
) -> tuple[tuple[Mapping[str, Any], ...], Mapping[str, int], int]:
    _coverage_exact_keys(
        coverage_input,
        context="coverage input",
        required=("terminal_overrides", "stage_overrides"),
        optional=(
            "stage_count_overrides",
            "terminal_classification_counts",
            "terminal_classification_eligible_count",
        ),
    )
    terminal_overrides = _coverage_mapping(
        coverage_input["terminal_overrides"], context="terminal overrides"
    )
    stage_overrides = _coverage_mapping(
        coverage_input["stage_overrides"], context="stage overrides"
    )
    stage_count_overrides = _coverage_mapping(
        coverage_input.get("stage_count_overrides", {}),
        context="stage count overrides",
    )
    known_field_ids = {spec.data_element_id for spec in specs}
    if (
        set(terminal_overrides) - known_field_ids
        or set(stage_overrides) - known_field_ids
        or set(stage_count_overrides) - known_field_ids
    ):
        raise CoverageContractError(
            "Coverage overrides must reference the governed source-to-screen inventory."
        )
    rows: list[Mapping[str, Any]] = []
    terminal_counts = {name: 0 for name in COVERAGE_TERMINAL_CLASSIFICATIONS}
    for spec in sorted(specs, key=lambda item: item.data_element_id):
        terminal = _coverage_enum(
            terminal_overrides.get(
                spec.data_element_id,
                _terminal_from_catalog_gap(spec.gap_classification),
            ),
            COVERAGE_TERMINAL_CLASSIFICATIONS,
            context="terminal classification",
        )
        terminal_counts[terminal] += 1
        route = spec.current_display_route_or_export
        states = dict(
            _terminal_stage_states(
                terminal,
                complaint_page_required="/reviewer/records/detail" in route,
                facility_hub_required="/ccld/facilities/detail" in route,
            )
        )
        field_stage_overrides = _coverage_mapping(
            stage_overrides.get(spec.data_element_id, {}),
            context="field stage overrides",
        )
        field_count_overrides = _coverage_mapping(
            stage_count_overrides.get(spec.data_element_id, {}),
            context="field stage count overrides",
        )
        if set(field_stage_overrides) - set(COVERAGE_STAGES):
            raise CoverageContractError("Coverage input contains an unsupported stage.")
        if set(field_count_overrides) - set(COVERAGE_STAGES):
            raise CoverageContractError("Coverage input contains an unsupported count stage.")
        if set(field_stage_overrides) & set(field_count_overrides):
            raise CoverageContractError(
                "A coverage stage cannot use state and count overrides together."
            )
        for stage, state in field_stage_overrides.items():
            states[stage] = _coverage_enum(
                state,
                COVERAGE_STAGE_STATES,
                context="coverage stage state",
            )
        for stage in COVERAGE_STAGES:
            state = states[stage]
            row: dict[str, Any] = {
                "field_id": spec.data_element_id,
                "stage": stage,
                "eligible_count": 0 if state is None else 1,
            }
            row.update({f"{name}_count": 0 for name in COVERAGE_STAGE_STATES})
            if state is not None:
                row[f"{state}_count"] = 1
            if stage in field_count_overrides:
                count_override = _coverage_mapping(
                    field_count_overrides[stage], context="stage count override"
                )
                required_count_fields = (
                    "eligible_count",
                    *(f"{name}_count" for name in COVERAGE_STAGE_STATES),
                )
                _coverage_exact_keys(
                    count_override,
                    context="stage count override",
                    required=required_count_fields,
                )
                row = {
                    name: _coverage_count(
                        count_override[name], context=f"stage count {name}"
                    )
                    for name in required_count_fields
                }
                row["field_id"] = spec.data_element_id
                row["stage"] = stage
            rows.append(row)
    terminal_count_input = coverage_input.get("terminal_classification_counts")
    if terminal_count_input is not None:
        provided_counts = _coverage_mapping(
            terminal_count_input, context="terminal classification counts"
        )
        _coverage_exact_keys(
            provided_counts,
            context="terminal classification counts",
            required=COVERAGE_TERMINAL_CLASSIFICATIONS,
        )
        terminal_counts = {
            name: _coverage_count(
                provided_counts[name], context=f"terminal classification {name}"
            )
            for name in COVERAGE_TERMINAL_CLASSIFICATIONS
        }
    terminal_eligible_count = _coverage_count(
        coverage_input.get(
            "terminal_classification_eligible_count", sum(terminal_counts.values())
        ),
        context="terminal classification eligible count",
    )
    return tuple(rows), dict(sorted(terminal_counts.items())), terminal_eligible_count


def _coverage_source_snapshots(value: Any) -> tuple[Mapping[str, Any], ...]:
    snapshots: list[Mapping[str, Any]] = []
    for item in _coverage_sequence(value, context="source snapshots"):
        snapshot = _coverage_mapping(item, context="source snapshot")
        _coverage_exact_keys(
            snapshot,
            context="source snapshot",
            required=(
                "source_snapshot_id",
                "source_family_id",
                "selection_state",
                "safe_version_label",
                "observed_at",
                "row_count",
                "schema_fingerprint",
                "content_fingerprint",
                "availability",
                "reason_category",
                "cadence_status",
            ),
        )
        source_snapshot_id = _coverage_identifier(
            snapshot["source_snapshot_id"], context="source_snapshot_id"
        )
        source_family_id = _coverage_identifier(
            snapshot["source_family_id"], context="source_family_id"
        )
        selection_state = _coverage_enum(
            snapshot["selection_state"],
            (
                "retained_existing",
                "active_accepted",
                "inactive_candidate",
                "superseded_retained",
                "unavailable",
            ),
            context="source selection state",
        )
        cadence_status = _coverage_enum(
            snapshot["cadence_status"],
            ("not_approved",),
            context="source cadence status",
        )
        if selection_state == "inactive_candidate" and cadence_status != "not_approved":
            raise CoverageContractError(
                "Inactive statewide candidates must retain unapproved cadence."
            )
        safe_version_label = snapshot["safe_version_label"]
        if safe_version_label is not None:
            safe_version_label = _coverage_identifier(
                safe_version_label, context="safe_version_label"
            )
        observed_at = _coverage_timestamp(
            snapshot["observed_at"], context="source observed_at", nullable=True
        )
        row_count = snapshot["row_count"]
        if row_count is not None:
            row_count = _coverage_count(row_count, context="source row_count")
        fingerprints: dict[str, str | None] = {}
        for name in ("schema_fingerprint", "content_fingerprint"):
            fingerprint = snapshot[name]
            if fingerprint is not None and (
                not isinstance(fingerprint, str)
                or not _COVERAGE_SHA256_RE.fullmatch(fingerprint)
            ):
                raise CoverageContractError("Source fingerprints must be lowercase SHA-256.")
            fingerprints[name] = fingerprint
        snapshots.append(
            {
                "source_snapshot_id": source_snapshot_id,
                "source_family_id": source_family_id,
                "selection_state": selection_state,
                "safe_version_label": safe_version_label,
                "observed_at": observed_at,
                "row_count": row_count,
                **fingerprints,
                "availability": _coverage_enum(
                    snapshot["availability"],
                    ("available", "partial", "unavailable"),
                    context="source availability",
                ),
                "reason_category": _coverage_enum(
                    snapshot["reason_category"],
                    _COVERAGE_AVAILABILITY_REASON_CATEGORIES,
                    context="source availability reason",
                ),
                "cadence_status": cadence_status,
            }
        )
    ordered = tuple(sorted(snapshots, key=lambda item: str(item["source_snapshot_id"])))
    if not ordered:
        raise CoverageContractError("At least one governed source snapshot is required.")
    if len({str(item["source_snapshot_id"]) for item in ordered}) != len(ordered):
        raise CoverageContractError("Source snapshot identifiers must be unique.")
    if not any(item["selection_state"] == "retained_existing" for item in ordered):
        raise CoverageContractError("The retained existing source family must be represented.")
    if not any(item["selection_state"] == "inactive_candidate" for item in ordered):
        raise CoverageContractError("The inactive statewide candidate must be represented.")
    return ordered


def _coverage_index_input(value: Any, *, context: str) -> Mapping[str, Any]:
    index = _coverage_mapping(value, context=context)
    _coverage_exact_keys(
        index,
        context=context,
        required=("availability", "reason_category", "rows"),
    )
    availability = _coverage_enum(
        index["availability"], ("available", "unavailable"), context=f"{context} availability"
    )
    reason = _coverage_enum(
        index["reason_category"],
        _COVERAGE_AVAILABILITY_REASON_CATEGORIES,
        context=f"{context} reason",
    )
    rows = _coverage_sequence(index["rows"], context=f"{context} rows")
    if availability == "unavailable" and rows:
        raise CoverageContractError(f"{context} cannot retain rows while unavailable.")
    if availability == "available" and reason != "none":
        raise CoverageContractError(f"{context} must use reason none when available.")
    if availability == "unavailable" and reason == "none":
        raise CoverageContractError(f"{context} requires a controlled unavailable reason.")
    return {"availability": availability, "reason_category": reason, "rows": rows}


def _coverage_facility_rows(
    value: Sequence[Any],
    *,
    report_id: str,
    source_snapshots: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    snapshots_by_id = {
        str(snapshot["source_snapshot_id"]): snapshot for snapshot in source_snapshots
    }
    rows: list[tuple[str, Mapping[str, Any]]] = []
    input_fields = (
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
        "retrieval_state",
        "import_state",
        "governed_conflict",
        "operational_failure_category",
        "retry_eligibility",
        "operator_intervention_required",
        "checkpoint_state",
        "last_job_id",
    )
    for item in value:
        row = _coverage_mapping(item, context="operator facility input row")
        _coverage_exact_keys(
            row,
            context="operator facility input row",
            required=input_fields,
        )
        facility_id = row["facility_id"]
        if not isinstance(facility_id, str) or not _COVERAGE_FACILITY_ID_RE.fullmatch(
            facility_id
        ):
            raise CoverageContractError("Facility ID must be a safe public identifier.")
        normalized_facility_id = facility_id.strip().casefold()
        source_snapshot_id = _coverage_identifier(
            row["source_snapshot_id"], context="facility source_snapshot_id"
        )
        if source_snapshot_id not in snapshots_by_id:
            raise CoverageContractError("Facility rows must reference a package source snapshot.")
        source_family_id = str(snapshots_by_id[source_snapshot_id]["source_family_id"])
        entry_digest = _coverage_sha256(
            _canonical_json_text(
                {
                    "facility_id": normalized_facility_id,
                    "source_family_id": source_family_id,
                }
            ).encode("utf-8")
        )
        last_job_id = row["last_job_id"]
        if last_job_id is not None:
            last_job_id = _coverage_identifier(last_job_id, context="last_job_id")
        pipeline_version = _coverage_identifier(
            row["pipeline_version"], context="pipeline_version"
        )
        output_row: dict[str, Any] = {
            "contract_version": COVERAGE_CONTRACT_VERSION,
            "report_id": report_id,
            "facility_entry_id": f"facility-v1-{entry_digest}",
            "facility_id": facility_id,
            "source_snapshot_id": source_snapshot_id,
            "refresh_eligibility": _coverage_enum(
                row["refresh_eligibility"],
                ("eligible", "ineligible", "unknown"),
                context="refresh eligibility",
            ),
            "preserved_source_document_count": _coverage_count(
                row["preserved_source_document_count"],
                context="preserved source document count",
            ),
            "pipeline_version": pipeline_version,
            "preserved_artifact_state": _coverage_enum(
                row["preserved_artifact_state"],
                COVERAGE_PRESERVED_ARTIFACT_STATES,
                context="preserved artifact state",
            ),
            "hash_validation_state": _coverage_enum(
                row["hash_validation_state"],
                COVERAGE_HASH_VALIDATION_STATES,
                context="hash validation state",
            ),
            "source_layout_classification": _coverage_enum(
                row["source_layout_classification"],
                COVERAGE_SOURCE_LAYOUT_CLASSIFICATIONS,
                context="source layout classification",
            ),
            "processing_outcome": _coverage_enum(
                row["processing_outcome"],
                COVERAGE_PROCESSING_OUTCOMES,
                context="processing outcome",
            ),
            "change_outcome": _coverage_enum(
                row["change_outcome"],
                COVERAGE_CHANGE_OUTCOMES,
                context="change outcome",
            ),
            "refresh_state": _coverage_enum(
                row["refresh_state"], COVERAGE_REFRESH_STATES, context="refresh state"
            ),
            "governed_conflict": row["governed_conflict"],
            "operational_failure_category": _coverage_enum(
                row["operational_failure_category"],
                COVERAGE_OPERATIONAL_FAILURE_CATEGORIES,
                context="operational failure category",
            ),
            "retry_eligibility": _coverage_enum(
                row["retry_eligibility"],
                ("eligible", "ineligible", "not_evaluated"),
                context="retry eligibility",
            ),
            "operator_intervention_required": row["operator_intervention_required"],
            "checkpoint_state": _coverage_enum(
                row["checkpoint_state"],
                ("not_started", "available", "complete", "interrupted", "failed", "unavailable"),
                context="checkpoint state",
            ),
            "last_job_id": last_job_id,
        }
        for name in (
            "last_retrieval_attempt_at",
            "last_successful_retrieval_at",
            "last_refresh_attempt_at",
            "last_successful_refresh_at",
        ):
            output_row[name] = _coverage_timestamp(
                row[name], context=name, nullable=True
            )
        if not isinstance(output_row["governed_conflict"], bool) or not isinstance(
            output_row["operator_intervention_required"], bool
        ):
            raise CoverageContractError("Operator facility flags must be boolean.")
        output_row["retrieval_state"] = _coverage_enum(
            row["retrieval_state"],
            COVERAGE_RETRIEVAL_STATES,
            context="retrieval state",
        )
        output_row["import_state"] = _coverage_enum(
            row["import_state"], COVERAGE_IMPORT_STATES, context="import state"
        )
        rows.append((normalized_facility_id, output_row))
    ordered = tuple(
        item[1]
        for item in sorted(
            rows,
            key=lambda item: (item[0], str(item[1]["facility_entry_id"])),
        )
    )
    if len({str(row["facility_entry_id"]) for row in ordered}) != len(ordered):
        raise CoverageContractError("Operator facility identities must be unique.")
    return ordered


def _coverage_job_rows(
    value: Sequence[Any], *, report_id: str
) -> tuple[Mapping[str, Any], ...]:
    required = (
        "job_id",
        "job_state",
        "execution_mode",
        "started_at",
        "completed_at",
        "last_successful_refresh_at",
        "pipeline_version",
        "checkpoint_state",
        "checkpoint_identity",
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
    )
    rows: list[Mapping[str, Any]] = []
    for item in value:
        row = _coverage_mapping(item, context="operator job input row")
        _coverage_exact_keys(row, context="operator job input row", required=required)
        checkpoint_identity = row["checkpoint_identity"]
        if checkpoint_identity is not None:
            checkpoint_identity = _coverage_identifier(
                checkpoint_identity, context="checkpoint identity"
            )
        output: dict[str, Any] = {
            "job_id": _coverage_identifier(row["job_id"], context="job_id"),
            "contract_version": COVERAGE_CONTRACT_VERSION,
            "report_id": report_id,
            "job_state": _coverage_enum(
                row["job_state"], COVERAGE_JOB_STATES, context="job state"
            ),
            "execution_mode": _coverage_enum(
                row["execution_mode"], ("dry_run", "apply"), context="execution mode"
            ),
            "pipeline_version": _coverage_identifier(
                row["pipeline_version"], context="job pipeline_version"
            ),
            "checkpoint_state": _coverage_enum(
                row["checkpoint_state"],
                ("not_started", "available", "complete", "interrupted", "failed", "unavailable"),
                context="job checkpoint state",
            ),
            "checkpoint_identity": checkpoint_identity,
            "operational_failure_category": _coverage_enum(
                row["operational_failure_category"],
                COVERAGE_OPERATIONAL_FAILURE_CATEGORIES,
                context="job failure category",
            ),
            "previous_accepted_dataset_active": row[
                "previous_accepted_dataset_active"
            ],
            "operator_intervention_required": row["operator_intervention_required"],
        }
        for name in ("started_at", "completed_at", "last_successful_refresh_at"):
            output[name] = _coverage_timestamp(row[name], context=name, nullable=True)
        for name in (
            "selected_count",
            "processed_count",
            "changed_count",
            "unchanged_count",
            "skipped_count",
            "warning_count",
            "failed_count",
        ):
            output[name] = _coverage_count(row[name], context=name)
        if not isinstance(output["previous_accepted_dataset_active"], bool) or not isinstance(
            output["operator_intervention_required"], bool
        ):
            raise CoverageContractError("Operator job flags must be boolean.")
        rows.append(output)
    ordered = tuple(sorted(rows, key=lambda item: str(item["job_id"])))
    if len({str(row["job_id"]) for row in ordered}) != len(ordered):
        raise CoverageContractError("Operator job identifiers must be unique.")
    return ordered


def _coverage_enum_counts(
    rows: Sequence[Mapping[str, Any]], field: str, values: Sequence[str]
) -> Mapping[str, int]:
    counts = {value: 0 for value in values}
    for row in rows:
        counts[str(row[field])] += 1
    return dict(sorted(counts.items()))


def _coverage_operations(
    operational_input: Mapping[str, Any],
    *,
    report_id: str,
    source_snapshots: Sequence[Mapping[str, Any]],
) -> tuple[
    Mapping[str, Any],
    tuple[Mapping[str, Any], ...],
    tuple[Mapping[str, Any], ...],
    Mapping[str, Any],
]:
    _coverage_exact_keys(
        operational_input,
        context="operational input",
        required=("facility_index", "job_index", "declared_totals"),
    )
    facility_index_input = _coverage_index_input(
        operational_input["facility_index"], context="operator facility index"
    )
    job_index_input = _coverage_index_input(
        operational_input["job_index"], context="operator job index"
    )
    facility_rows = _coverage_facility_rows(
        _coverage_sequence(
            facility_index_input["rows"], context="operator facility index rows"
        ),
        report_id=report_id,
        source_snapshots=source_snapshots,
    )
    job_rows = _coverage_job_rows(
        _coverage_sequence(job_index_input["rows"], context="operator job index rows"),
        report_id=report_id,
    )
    declared = _coverage_mapping(
        operational_input["declared_totals"], context="declared operational totals"
    )
    _coverage_exact_keys(
        declared,
        context="declared operational totals",
        required=(),
        optional=(
            "existing_facility_total",
            "preserved_artifact_facility_total",
            "governed_conflict_facility_total",
            "operator_intervention_required_total",
        ),
    )
    computed_existing = len(facility_rows)
    existing_total = _coverage_count(
        declared.get("existing_facility_total", computed_existing),
        context="existing facility total",
    )
    preserved_counts = _coverage_enum_counts(
        facility_rows, "preserved_artifact_state", COVERAGE_PRESERVED_ARTIFACT_STATES
    )
    computed_preserved = preserved_counts["preserved"]
    preserved_total = _coverage_count(
        declared.get("preserved_artifact_facility_total", computed_preserved),
        context="preserved artifact facility total",
    )
    computed_conflicts = sum(bool(row["governed_conflict"]) for row in facility_rows)
    governed_conflict_total = _coverage_count(
        declared.get("governed_conflict_facility_total", computed_conflicts),
        context="governed conflict facility total",
    )
    computed_interventions = sum(
        bool(row["operator_intervention_required"]) for row in facility_rows
    )
    intervention_total = _coverage_count(
        declared.get(
            "operator_intervention_required_total", computed_interventions
        ),
        context="operator intervention required total",
    )
    eligibility_counts = _coverage_enum_counts(
        facility_rows,
        "refresh_eligibility",
        ("eligible", "ineligible", "unknown"),
    )
    operations: Mapping[str, Any] = {
        "existing_facility_total": existing_total,
        "preserved_artifact_facility_total": preserved_total,
        "eligible_facility_total": eligibility_counts["eligible"],
        "ineligible_facility_total": eligibility_counts["ineligible"],
        "unknown_eligibility_total": eligibility_counts["unknown"],
        "refresh_state_counts": _coverage_enum_counts(
            facility_rows, "refresh_state", COVERAGE_REFRESH_STATES
        ),
        "processing_outcome_counts": _coverage_enum_counts(
            facility_rows, "processing_outcome", COVERAGE_PROCESSING_OUTCOMES
        ),
        "change_outcome_counts": _coverage_enum_counts(
            facility_rows, "change_outcome", COVERAGE_CHANGE_OUTCOMES
        ),
        "retrieval_state_counts": _coverage_enum_counts(
            facility_rows, "retrieval_state", COVERAGE_RETRIEVAL_STATES
        ),
        "import_state_counts": _coverage_enum_counts(
            facility_rows, "import_state", COVERAGE_IMPORT_STATES
        ),
        "preserved_artifact_state_counts": preserved_counts,
        "hash_validation_state_counts": _coverage_enum_counts(
            facility_rows, "hash_validation_state", COVERAGE_HASH_VALIDATION_STATES
        ),
        "governed_conflict_facility_total": governed_conflict_total,
        "operator_intervention_required_total": intervention_total,
        "job_state_counts": _coverage_enum_counts(
            job_rows, "job_state", COVERAGE_JOB_STATES
        ),
    }
    metadata = {
        "facility_index_availability": facility_index_input["availability"],
        "facility_index_reason_category": facility_index_input["reason_category"],
        "job_index_availability": job_index_input["availability"],
        "job_index_reason_category": job_index_input["reason_category"],
        "computed_existing_facility_total": computed_existing,
        "computed_preserved_artifact_facility_total": computed_preserved,
        "computed_governed_conflict_facility_total": computed_conflicts,
        "computed_operator_intervention_required_total": computed_interventions,
    }
    return operations, facility_rows, job_rows, metadata


def _coverage_invariant(
    invariant_id: str,
    *,
    expected: int,
    actual: int,
    applicable: bool = True,
) -> Mapping[str, Any]:
    if invariant_id not in COVERAGE_INVARIANT_IDS:
        raise CoverageContractError("The producer attempted an unknown invariant ID.")
    status = "not_applicable" if not applicable else (
        "passed" if expected == actual else "failed"
    )
    return {
        "invariant_id": invariant_id,
        "status": status,
        "expected_count": expected,
        "actual_count": actual,
    }


def _coverage_reconciliation(
    *,
    operations: Mapping[str, Any],
    facility_rows: Sequence[Mapping[str, Any]],
    job_rows: Sequence[Mapping[str, Any]],
    operation_metadata: Mapping[str, Any],
    stage_rows: Sequence[Mapping[str, Any]],
    terminal_counts: Mapping[str, int],
    terminal_eligible_count: int,
    field_count: int,
) -> Mapping[str, Any]:
    existing = int(operations["existing_facility_total"])
    invariants = [
        _coverage_invariant(
            "coverage.facility-eligibility-total",
            expected=existing,
            actual=(
                int(operations["eligible_facility_total"])
                + int(operations["ineligible_facility_total"])
                + int(operations["unknown_eligibility_total"])
            ),
        ),
        _coverage_invariant(
            "coverage.processing-outcome-total",
            expected=existing,
            actual=sum(cast(Mapping[str, int], operations["processing_outcome_counts"]).values()),
        ),
        _coverage_invariant(
            "coverage.refresh-state-total",
            expected=existing,
            actual=sum(cast(Mapping[str, int], operations["refresh_state_counts"]).values()),
        ),
        _coverage_invariant(
            "coverage.change-outcome-total",
            expected=existing,
            actual=sum(cast(Mapping[str, int], operations["change_outcome_counts"]).values()),
        ),
        _coverage_invariant(
            "coverage.retrieval-state-total",
            expected=existing,
            actual=sum(cast(Mapping[str, int], operations["retrieval_state_counts"]).values()),
        ),
        _coverage_invariant(
            "coverage.import-state-total",
            expected=existing,
            actual=sum(cast(Mapping[str, int], operations["import_state_counts"]).values()),
        ),
        _coverage_invariant(
            "coverage.preserved-artifact-state-total",
            expected=existing,
            actual=sum(
                cast(
                    Mapping[str, int], operations["preserved_artifact_state_counts"]
                ).values()
            ),
        ),
        _coverage_invariant(
            "coverage.hash-validation-state-total",
            expected=existing,
            actual=sum(
                cast(
                    Mapping[str, int], operations["hash_validation_state_counts"]
                ).values()
            ),
        ),
        _coverage_invariant(
            "coverage.preserved-artifact-total",
            expected=int(operations["preserved_artifact_facility_total"]),
            actual=int(
                cast(
                    Mapping[str, int], operations["preserved_artifact_state_counts"]
                )["preserved"]
            ),
        ),
        _coverage_invariant(
            "coverage.governed-conflict-total",
            expected=int(operations["governed_conflict_facility_total"]),
            actual=int(operation_metadata["computed_governed_conflict_facility_total"]),
        ),
        _coverage_invariant(
            "coverage.operator-facility-conflict-total",
            expected=int(operations["governed_conflict_facility_total"]),
            actual=sum(bool(row["governed_conflict"]) for row in facility_rows),
            applicable=operation_metadata["facility_index_availability"] == "available",
        ),
        _coverage_invariant(
            "coverage.operator-intervention-total",
            expected=int(operations["operator_intervention_required_total"]),
            actual=int(
                operation_metadata["computed_operator_intervention_required_total"]
            ),
            applicable=operation_metadata["facility_index_availability"] == "available",
        ),
        _coverage_invariant(
            "coverage.job-state-total",
            expected=len(job_rows),
            actual=sum(cast(Mapping[str, int], operations["job_state_counts"]).values()),
            applicable=operation_metadata["job_index_availability"] == "available",
        ),
        _coverage_invariant(
            "coverage.field-stage-balances",
            expected=0,
            actual=sum(
                int(row["eligible_count"])
                != sum(int(row[f"{state}_count"]) for state in COVERAGE_STAGE_STATES)
                for row in stage_rows
            ),
        ),
        _coverage_invariant(
            "coverage.field-stage-inventory",
            expected=field_count * len(COVERAGE_STAGES),
            actual=len(stage_rows),
        ),
        _coverage_invariant(
            "coverage.terminal-classification-total",
            expected=terminal_eligible_count,
            actual=sum(terminal_counts.values()),
        ),
    ]
    status = "failed" if any(row["status"] == "failed" for row in invariants) else "passed"
    return {
        "reconciliation_status": status,
        "failure_category": "validation_failed" if status == "failed" else "none",
        "invariants": invariants,
    }


_COVERAGE_CRITERION_IDS = (
    "release.previously-populated-field-became-blank",
    "release.verified-label-regressed-to-unresolved",
    "release.facility-count-decline",
    "release.source-to-screen-stage-regression",
    "release.aggregate-reconciliation",
    "release.unresolved-or-conflicting-identity-type",
)


def _coverage_criteria(value: Any) -> Mapping[str, Any]:
    criteria = _coverage_mapping(value, context="coverage criteria")
    _coverage_exact_keys(
        criteria,
        context="coverage criteria",
        required=(
            "baseline_metrics",
            "thresholds",
            "observed_metrics",
            "reviewed_exceptions",
        ),
    )
    baseline = _coverage_mapping(criteria["baseline_metrics"], context="baseline metrics")
    _coverage_exact_keys(
        baseline,
        context="baseline metrics",
        required=(
            "existing_facility_total",
            "previously_populated_governed_field_total",
            "verified_descriptive_facility_type_label_total",
            "required_stage_success_total",
            "unresolved_identity_or_type_total",
        ),
    )
    thresholds = _coverage_mapping(criteria["thresholds"], context="coverage thresholds")
    _coverage_exact_keys(
        thresholds,
        context="coverage thresholds",
        required=(
            "maximum_facility_count_decline",
            "maximum_new_blank_regressions",
            "maximum_label_regressions",
            "maximum_stage_regressions",
            "maximum_unresolved_identity_or_type_total",
        ),
    )
    observed = _coverage_mapping(
        criteria["observed_metrics"], context="observed regression metrics"
    )
    _coverage_exact_keys(
        observed,
        context="observed regression metrics",
        required=(
            "previously_populated_now_blank_total",
            "verified_label_to_unresolved_regression_total",
            "required_stage_regression_total",
            "unresolved_identity_or_type_total",
        ),
    )
    baseline_counts = {
        name: _coverage_count(item, context=f"baseline {name}")
        for name, item in baseline.items()
    }
    threshold_counts = {
        name: _coverage_count(item, context=f"threshold {name}")
        for name, item in thresholds.items()
    }
    observed_counts = {
        name: _coverage_count(item, context=f"observed {name}")
        for name, item in observed.items()
    }
    exceptions: dict[str, str] = {}
    for item in _coverage_sequence(
        criteria["reviewed_exceptions"], context="reviewed exceptions"
    ):
        exception = _coverage_mapping(item, context="reviewed exception")
        _coverage_exact_keys(
            exception,
            context="reviewed exception",
            required=("criterion_id", "exception_id"),
        )
        criterion_id = _coverage_enum(
            exception["criterion_id"],
            _COVERAGE_CRITERION_IDS,
            context="reviewed exception criterion",
        )
        exceptions[criterion_id] = _coverage_identifier(
            exception["exception_id"], context="reviewed exception ID"
        )
    return {
        "baseline_metrics": dict(sorted(baseline_counts.items())),
        "thresholds": dict(sorted(threshold_counts.items())),
        "observed_metrics": dict(sorted(observed_counts.items())),
        "reviewed_exceptions": [
            {"criterion_id": criterion_id, "exception_id": exception_id}
            for criterion_id, exception_id in sorted(exceptions.items())
        ],
    }


def _coverage_release_assessment(
    *,
    criteria: Mapping[str, Any],
    operations: Mapping[str, Any],
    reconciliation: Mapping[str, Any],
) -> Mapping[str, Any]:
    baseline = cast(Mapping[str, int], criteria["baseline_metrics"])
    thresholds = cast(Mapping[str, int], criteria["thresholds"])
    observed = cast(Mapping[str, int], criteria["observed_metrics"])
    exceptions = {
        str(item["criterion_id"]): str(item["exception_id"])
        for item in cast(Sequence[Mapping[str, Any]], criteria["reviewed_exceptions"])
    }
    facility_decline = max(
        0,
        baseline["existing_facility_total"] - int(operations["existing_facility_total"]),
    )
    values = (
        (
            "release.previously-populated-field-became-blank",
            baseline["previously_populated_governed_field_total"],
            observed["previously_populated_now_blank_total"],
            thresholds["maximum_new_blank_regressions"],
            False,
        ),
        (
            "release.verified-label-regressed-to-unresolved",
            baseline["verified_descriptive_facility_type_label_total"],
            observed["verified_label_to_unresolved_regression_total"],
            thresholds["maximum_label_regressions"],
            False,
        ),
        (
            "release.facility-count-decline",
            baseline["existing_facility_total"],
            facility_decline,
            thresholds["maximum_facility_count_decline"],
            False,
        ),
        (
            "release.source-to-screen-stage-regression",
            baseline["required_stage_success_total"],
            observed["required_stage_regression_total"],
            thresholds["maximum_stage_regressions"],
            False,
        ),
        (
            "release.aggregate-reconciliation",
            0,
            0 if reconciliation["reconciliation_status"] == "passed" else 1,
            0,
            False,
        ),
        (
            "release.unresolved-or-conflicting-identity-type",
            baseline["unresolved_identity_or_type_total"],
            observed["unresolved_identity_or_type_total"],
            thresholds["maximum_unresolved_identity_or_type_total"],
            True,
        ),
    )
    checks: list[Mapping[str, Any]] = []
    for criterion_id, baseline_count, observed_count, threshold_count, warn_nonzero in values:
        breached = observed_count > threshold_count
        exception_id = exceptions.get(criterion_id)
        if breached and exception_id is not None:
            status = "reviewed_exception_required"
        elif breached:
            status = "failed"
        elif warn_nonzero and observed_count > 0:
            status = "warning"
        else:
            status = "passed"
        checks.append(
            {
                "criterion_id": criterion_id,
                "status": status,
                "baseline_count": baseline_count,
                "observed_count": observed_count,
                "threshold_count": threshold_count,
                "exception_id": exception_id,
            }
        )
    statuses = {str(check["status"]) for check in checks}
    overall = (
        "failed"
        if "failed" in statuses
        else "reviewed_exception_required"
        if "reviewed_exception_required" in statuses
        else "warning"
        if "warning" in statuses
        else "passed"
    )
    return {"status": overall, "checks": checks}


_COVERAGE_FACILITY_OUTPUT_FIELDS = (
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
)


def _coverage_public_facility_rows(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    return tuple(
        {name: row[name] for name in _COVERAGE_FACILITY_OUTPUT_FIELDS} for row in rows
    )


def _coverage_jsonl_bytes(rows: Sequence[Mapping[str, Any]]) -> bytes:
    return b"".join(_canonical_json_bytes(row) for row in rows)


def _coverage_percentage(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return ""
    return f"{numerator * 100 / denominator:.2f}"


def _coverage_csv_bytes(
    *,
    report_id: str,
    criteria_set_id: str,
    source_snapshots: Sequence[Mapping[str, Any]],
    stage_rows: Sequence[Mapping[str, Any]],
    terminal_counts: Mapping[str, int],
    terminal_eligible_count: int,
    operations: Mapping[str, Any],
    release_assessment: Mapping[str, Any],
) -> bytes:
    rows: list[Mapping[str, Any]] = []
    blank = ""
    for stage_row in stage_rows:
        denominator = int(stage_row["eligible_count"])
        for state in COVERAGE_STAGE_STATES:
            numerator = int(stage_row[f"{state}_count"])
            rows.append(
                {
                    "contract_version": COVERAGE_CONTRACT_VERSION,
                    "report_id": report_id,
                    "dimension": "field_stage",
                    "field_id": stage_row["field_id"],
                    "stage": stage_row["stage"],
                    "category": state,
                    "numerator_count": numerator,
                    "denominator_count": denominator,
                    "percentage": _coverage_percentage(numerator, denominator),
                    "status": blank,
                    "criteria_set_id": criteria_set_id,
                    "source_snapshot_id": blank,
                }
            )
    for category, numerator in terminal_counts.items():
        rows.append(
            {
                "contract_version": COVERAGE_CONTRACT_VERSION,
                "report_id": report_id,
                "dimension": "terminal_classification",
                "field_id": blank,
                "stage": blank,
                "category": category,
                "numerator_count": numerator,
                "denominator_count": terminal_eligible_count,
                "percentage": _coverage_percentage(
                    numerator, terminal_eligible_count
                ),
                "status": blank,
                "criteria_set_id": criteria_set_id,
                "source_snapshot_id": blank,
            }
        )
    existing_total = int(operations["existing_facility_total"])
    for dimension, field, categories in (
        ("refresh_state", "refresh_state_counts", COVERAGE_REFRESH_STATES),
        (
            "processing_outcome",
            "processing_outcome_counts",
            COVERAGE_PROCESSING_OUTCOMES,
        ),
        ("change_outcome", "change_outcome_counts", COVERAGE_CHANGE_OUTCOMES),
        ("retrieval_state", "retrieval_state_counts", COVERAGE_RETRIEVAL_STATES),
        ("import_state", "import_state_counts", COVERAGE_IMPORT_STATES),
        (
            "preserved_artifact_state",
            "preserved_artifact_state_counts",
            COVERAGE_PRESERVED_ARTIFACT_STATES,
        ),
        (
            "hash_validation_state",
            "hash_validation_state_counts",
            COVERAGE_HASH_VALIDATION_STATES,
        ),
    ):
        counts = cast(Mapping[str, int], operations[field])
        for category in categories:
            numerator = counts[category]
            rows.append(
                {
                    "contract_version": COVERAGE_CONTRACT_VERSION,
                    "report_id": report_id,
                    "dimension": dimension,
                    "field_id": blank,
                    "stage": blank,
                    "category": category,
                    "numerator_count": numerator,
                    "denominator_count": existing_total,
                    "percentage": _coverage_percentage(numerator, existing_total),
                    "status": blank,
                    "criteria_set_id": criteria_set_id,
                    "source_snapshot_id": blank,
                }
            )
    job_counts = cast(Mapping[str, int], operations["job_state_counts"])
    job_total = sum(job_counts.values())
    for category in COVERAGE_JOB_STATES:
        numerator = job_counts[category]
        rows.append(
            {
                "contract_version": COVERAGE_CONTRACT_VERSION,
                "report_id": report_id,
                "dimension": "job_state",
                "field_id": blank,
                "stage": blank,
                "category": category,
                "numerator_count": numerator,
                "denominator_count": job_total,
                "percentage": _coverage_percentage(numerator, job_total),
                "status": blank,
                "criteria_set_id": criteria_set_id,
                "source_snapshot_id": blank,
            }
        )
    for check in cast(Sequence[Mapping[str, Any]], release_assessment["checks"]):
        rows.append(
            {
                "contract_version": COVERAGE_CONTRACT_VERSION,
                "report_id": report_id,
                "dimension": "release_assessment",
                "field_id": blank,
                "stage": blank,
                "category": check["criterion_id"],
                "numerator_count": check["observed_count"],
                "denominator_count": check["threshold_count"],
                "percentage": blank,
                "status": check["status"],
                "criteria_set_id": criteria_set_id,
                "source_snapshot_id": blank,
            }
        )
    for snapshot in source_snapshots:
        row_count = snapshot["row_count"]
        rows.append(
            {
                "contract_version": COVERAGE_CONTRACT_VERSION,
                "report_id": report_id,
                "dimension": "source_snapshot",
                "field_id": blank,
                "stage": blank,
                "category": snapshot["selection_state"],
                "numerator_count": blank if row_count is None else row_count,
                "denominator_count": blank,
                "percentage": blank,
                "status": snapshot["availability"],
                "criteria_set_id": criteria_set_id,
                "source_snapshot_id": snapshot["source_snapshot_id"],
            }
        )
    rows.sort(
        key=lambda row: tuple(
            str(row[name])
            for name in (
                "dimension",
                "field_id",
                "stage",
                "category",
                "source_snapshot_id",
            )
        )
    )
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=COVERAGE_AGGREGATE_CSV_FIELDNAMES,
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _coverage_artifact_entry(
    *,
    name: str,
    availability: str,
    reason_category: str,
    media_type: str,
    content: bytes | None,
) -> Mapping[str, Any]:
    return {
        "name": name,
        "availability": availability,
        "reason_category": reason_category,
        "byte_count": 0 if content is None else len(content),
        "sha256": None if content is None else _coverage_sha256(content),
        "media_type": media_type,
    }


def _coverage_retention(value: Any) -> Mapping[str, Any]:
    retention = _coverage_mapping(value, context="coverage retention")
    _coverage_exact_keys(
        retention,
        context="coverage retention",
        required=(
            "policy_id",
            "disposition",
            "retain_until",
            "previous_accepted_report_id",
        ),
    )
    if retention["policy_id"] is not None:
        raise CoverageContractError("No coverage retention policy is currently approved.")
    if retention["disposition"] != "pending_policy" or retention["retain_until"] is not None:
        raise CoverageContractError("Coverage retention duration remains pending policy.")
    previous_report_id = retention["previous_accepted_report_id"]
    if previous_report_id is not None and (
        not isinstance(previous_report_id, str)
        or not re.fullmatch(r"coverage-report-v1-[0-9a-f]{64}", previous_report_id)
    ):
        raise CoverageContractError("Previous accepted report ID is invalid.")
    return {
        "policy_id": None,
        "disposition": "pending_policy",
        "retain_until": None,
        "previous_accepted_report_id": previous_report_id,
    }


def _coverage_provenance(value: Any, *, fixture_id: str) -> Mapping[str, Any]:
    provenance = _coverage_mapping(value, context="coverage provenance")
    _coverage_exact_keys(
        provenance,
        context="coverage provenance",
        required=("input_manifest_ids", "governed_fixture_ids"),
    )
    input_manifest_ids = sorted(
        {
            _coverage_identifier(item, context="input manifest ID")
            for item in _coverage_sequence(
                provenance["input_manifest_ids"], context="input manifest IDs"
            )
        }
    )
    governed_fixture_ids = sorted(
        {
            _coverage_identifier(item, context="governed fixture ID")
            for item in _coverage_sequence(
                provenance["governed_fixture_ids"], context="governed fixture IDs"
            )
        }
    )
    if fixture_id not in governed_fixture_ids:
        governed_fixture_ids.append(fixture_id)
        governed_fixture_ids.sort()
    return {
        "input_manifest_ids": input_manifest_ids,
        "governed_fixture_ids": governed_fixture_ids,
    }


def _coverage_schema(repo_root: Path) -> Mapping[str, Any]:
    schema_path = repo_root / COVERAGE_SCHEMA_PATH
    try:
        payload = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CoverageContractError("The coverage report schema could not be loaded.") from exc
    return _coverage_mapping(payload, context="coverage report schema")


def _validate_coverage_schema_payload(
    payload: Mapping[str, Any], *, schema: Mapping[str, Any]
) -> None:
    try:
        jsonschema_validate(instance=payload, schema=schema)
    except JsonSchemaValidationError as exc:
        location = exc.json_path or "$"
        validator = str(exc.validator or "contract")
        raise CoverageContractError(
            "Coverage output failed closed-schema validation at "
            f"{location} ({validator})."
        ) from exc


def _coverage_identity(
    *,
    evaluation_id: str,
    source_snapshots: Sequence[Mapping[str, Any]],
    criteria_set_id: str,
    scope_id: str,
    producer_schema_id: str,
) -> str:
    identity = {
        "contract_major": 1,
        "evaluation_id": evaluation_id,
        "source_snapshot_ids": [
            str(snapshot["source_snapshot_id"]) for snapshot in source_snapshots
        ],
        "criteria_set_id": criteria_set_id,
        "scope_id": scope_id,
        "producer_schema_id": producer_schema_id,
    }
    return "coverage-report-v1-" + _coverage_sha256(
        _canonical_json_text(identity).encode("utf-8")
    )


def _coverage_fixture_input(value: Mapping[str, Any]) -> Mapping[str, Any]:
    _coverage_exact_keys(
        value,
        context="coverage fixture",
        required=(
            "fixture_id",
            "contract_version",
            "evaluation_id",
            "criteria_set_id",
            "scope_id",
            "producer_schema_id",
            "producer_version",
            "generation_mode",
            "source_snapshots",
            "criteria",
            "coverage",
            "operational",
            "retention",
            "provenance",
        ),
        optional=("unavailable_dimensions",),
    )
    _reject_prohibited_coverage_content(value)
    if value["contract_version"] != COVERAGE_CONTRACT_VERSION:
        raise CoverageContractError("Coverage contract version is not supported.")
    if value["producer_schema_id"] != COVERAGE_PRODUCER_SCHEMA_ID:
        raise CoverageContractError("Coverage producer schema version is not supported.")
    _coverage_enum(
        value["generation_mode"],
        ("governed_fixture", "read_only_boundary"),
        context="coverage generation mode",
    )
    return value


def generate_coverage_package(
    fixture: Mapping[str, Any],
    *,
    output_dir: Path,
    repo_root: Path | None = None,
    generated_at: datetime | None = None,
) -> CoveragePackageResult:
    """Generate the deterministic Issues #453/#477 v1 aggregate contract package."""

    root = (repo_root or Path(__file__).resolve().parents[2]).resolve()
    fixture = _coverage_fixture_input(fixture)
    fixture_id = _coverage_identifier(fixture["fixture_id"], context="fixture_id")
    evaluation_id = _coverage_identifier(
        fixture["evaluation_id"], context="evaluation_id"
    )
    criteria_set_id = _coverage_identifier(
        fixture["criteria_set_id"], context="criteria_set_id"
    )
    scope_id = _coverage_identifier(fixture["scope_id"], context="scope_id")
    producer_schema_id = _coverage_identifier(
        fixture["producer_schema_id"], context="producer_schema_id"
    )
    producer_version = _coverage_identifier(
        fixture["producer_version"], context="producer_version"
    )
    source_snapshots = _coverage_source_snapshots(fixture["source_snapshots"])
    report_id = _coverage_identity(
        evaluation_id=evaluation_id,
        source_snapshots=source_snapshots,
        criteria_set_id=criteria_set_id,
        scope_id=scope_id,
        producer_schema_id=producer_schema_id,
    )
    specs = discover_element_specs(root)
    if not specs:
        raise CoverageContractError("The governed source-to-screen inventory is empty.")
    stage_rows, terminal_counts, terminal_eligible_count = (
        _coverage_rows_from_inventory(
            specs,
            _coverage_mapping(fixture["coverage"], context="coverage input"),
        )
    )
    operations, internal_facility_rows, job_rows, operation_metadata = (
        _coverage_operations(
            _coverage_mapping(fixture["operational"], context="operational input"),
            report_id=report_id,
            source_snapshots=source_snapshots,
        )
    )
    facility_rows = _coverage_public_facility_rows(internal_facility_rows)
    reconciliation = _coverage_reconciliation(
        operations=operations,
        facility_rows=internal_facility_rows,
        job_rows=job_rows,
        operation_metadata=operation_metadata,
        stage_rows=stage_rows,
        terminal_counts=terminal_counts,
        terminal_eligible_count=terminal_eligible_count,
        field_count=len(specs),
    )
    criteria = _coverage_criteria(fixture["criteria"])
    release_assessment = _coverage_release_assessment(
        criteria=criteria,
        operations=operations,
        reconciliation=reconciliation,
    )
    retention = _coverage_retention(fixture["retention"])
    provenance = _coverage_provenance(fixture["provenance"], fixture_id=fixture_id)
    unavailable_dimensions = {
        _coverage_identifier(item, context="unavailable dimension")
        for item in _coverage_sequence(
            fixture.get("unavailable_dimensions", []),
            context="unavailable dimensions",
        )
    }
    if operation_metadata["facility_index_availability"] == "unavailable":
        unavailable_dimensions.add("operator_facility_index")
    if operation_metadata["job_index_availability"] == "unavailable":
        unavailable_dimensions.add("operator_job_index")
    package_availability = (
        "reconciliation_failed"
        if reconciliation["reconciliation_status"] == "failed"
        else "partial"
        if unavailable_dimensions
        else "available"
    )
    generated_at_value = _coverage_generated_at(generated_at)
    report: Mapping[str, Any] = {
        "contract_version": COVERAGE_CONTRACT_VERSION,
        "report_id": report_id,
        "generated_at": generated_at_value,
        "evaluation_id": evaluation_id,
        "criteria_set_id": criteria_set_id,
        "scope_id": scope_id,
        "producer_schema_id": producer_schema_id,
        "package_availability": package_availability,
        "source_snapshots": list(source_snapshots),
        "coverage": {
            "inventory_field_total": len(specs),
            "field_stage_coverage": list(stage_rows),
            "terminal_classification_eligible_count": terminal_eligible_count,
            "terminal_classification_counts": terminal_counts,
        },
        "operations": operations,
        "criteria": criteria,
        "reconciliation": reconciliation,
        "release_assessment": release_assessment,
        "unavailable_dimensions": sorted(unavailable_dimensions),
        "issue_490_boundaries": {
            "retained_source_scope": "existing_program_specific_sources",
            "statewide_candidate_selection_state": "inactive_candidate",
            "statewide_completeness_baseline": "not_established",
            "cadence_status": "not_approved",
            "raw_733_mapping_status": "unresolved",
            "raw_733_descriptive_label_emitted": False,
        },
    }
    report_bytes = _canonical_json_bytes(report)
    facility_bytes = (
        _coverage_jsonl_bytes(facility_rows)
        if operation_metadata["facility_index_availability"] == "available"
        else None
    )
    job_bytes = (
        _coverage_jsonl_bytes(job_rows)
        if operation_metadata["job_index_availability"] == "available"
        else None
    )
    csv_bytes = _coverage_csv_bytes(
        report_id=report_id,
        criteria_set_id=criteria_set_id,
        source_snapshots=source_snapshots,
        stage_rows=stage_rows,
        terminal_counts=terminal_counts,
        terminal_eligible_count=terminal_eligible_count,
        operations=operations,
        release_assessment=release_assessment,
    )
    artifacts = (
        _coverage_artifact_entry(
            name="coverage-report.json",
            availability="available",
            reason_category="none",
            media_type="application/json",
            content=report_bytes,
        ),
        _coverage_artifact_entry(
            name="operator-facility-index.jsonl",
            availability=str(operation_metadata["facility_index_availability"]),
            reason_category=str(operation_metadata["facility_index_reason_category"]),
            media_type="application/x-ndjson",
            content=facility_bytes,
        ),
        _coverage_artifact_entry(
            name="operator-job-index.jsonl",
            availability=str(operation_metadata["job_index_availability"]),
            reason_category=str(operation_metadata["job_index_reason_category"]),
            media_type="application/x-ndjson",
            content=job_bytes,
        ),
        _coverage_artifact_entry(
            name="aggregate-coverage.csv",
            availability="available",
            reason_category="none",
            media_type="text/csv",
            content=csv_bytes,
        ),
    )
    manifest: Mapping[str, Any] = {
        "contract_version": COVERAGE_CONTRACT_VERSION,
        "minimum_consumer_version": COVERAGE_MINIMUM_CONSUMER_VERSION,
        "report_id": report_id,
        "generated_at": generated_at_value,
        "evaluation_id": evaluation_id,
        "criteria_set_id": criteria_set_id,
        "scope_id": scope_id,
        "producer_schema_id": producer_schema_id,
        "producer_version": producer_version,
        "package_availability": package_availability,
        "source_snapshots": list(source_snapshots),
        "artifacts": sorted(artifacts, key=lambda item: str(item["name"])),
        "provenance": {
            **provenance,
            "generation_mode": fixture["generation_mode"],
        },
        "retention": retention,
    }
    _reject_prohibited_coverage_content(
        {
            "manifest": manifest,
            "report": report,
            "facility_index": facility_rows,
            "job_index": job_rows,
        }
    )
    schema = _coverage_schema(root)
    _validate_coverage_schema_payload(report, schema=schema)
    _validate_coverage_schema_payload(manifest, schema=schema)
    for row in (*facility_rows, *job_rows):
        _validate_coverage_schema_payload(row, schema=schema)
    manifest_bytes = _canonical_json_bytes(manifest)
    effective_output_dir = output_dir if output_dir.is_absolute() else root / output_dir
    effective_output_dir.mkdir(parents=True, exist_ok=True)
    outputs: Mapping[str, bytes | None] = {
        "manifest.json": manifest_bytes,
        "coverage-report.json": report_bytes,
        "operator-facility-index.jsonl": facility_bytes,
        "operator-job-index.jsonl": job_bytes,
        "aggregate-coverage.csv": csv_bytes,
    }
    for name, content in outputs.items():
        path = effective_output_dir / name
        if path.exists():
            if content is None or not path.is_file() or path.read_bytes() != content:
                raise CoverageContractError(
                    "A coverage generation instance is immutable and cannot be overwritten."
                )
            continue
        if content is not None:
            path.write_bytes(content)
    artifact_hashes = {
        str(artifact["name"]): str(artifact["sha256"])
        for artifact in artifacts
        if artifact["availability"] == "available"
    }
    return CoveragePackageResult(
        report_id=report_id,
        manifest=manifest,
        report=report,
        facility_index=facility_rows,
        job_index=job_rows,
        artifact_hashes=dict(sorted(artifact_hashes.items())),
    )


def _read_canonical_coverage_json(path: Path) -> Mapping[str, Any]:
    try:
        content = path.read_bytes()
        payload = json.loads(content.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CoverageContractError("A required coverage JSON artifact is unavailable.") from exc
    mapping = _coverage_mapping(payload, context="coverage JSON artifact")
    if content != _canonical_json_bytes(mapping):
        raise CoverageContractError("Coverage JSON serialization is not canonical.")
    return mapping


def _read_canonical_coverage_jsonl(path: Path) -> tuple[Mapping[str, Any], ...]:
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise CoverageContractError("A coverage JSONL artifact is unavailable.") from exc
    if b"\r" in content or (content and not content.endswith(b"\n")):
        raise CoverageContractError("Coverage JSONL serialization is not canonical.")
    rows: list[Mapping[str, Any]] = []
    for line in content.splitlines():
        try:
            payload = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CoverageContractError("A coverage JSONL row is invalid.") from exc
        row = _coverage_mapping(payload, context="coverage JSONL row")
        if line + b"\n" != _canonical_json_bytes(row):
            raise CoverageContractError("Coverage JSONL serialization is not canonical.")
        rows.append(row)
    return tuple(rows)


def validate_coverage_package(
    package_dir: Path, *, repo_root: Path | None = None
) -> Mapping[str, Any]:
    """Validate identities, hashes, schema, serialization, and fail-closed state."""

    root = (repo_root or Path(__file__).resolve().parents[2]).resolve()
    schema = _coverage_schema(root)
    manifest_path = package_dir / "manifest.json"
    manifest = _read_canonical_coverage_json(manifest_path)
    _validate_coverage_schema_payload(manifest, schema=schema)
    if manifest["contract_version"] != COVERAGE_CONTRACT_VERSION:
        raise CoverageContractError("Coverage package version is not supported.")
    artifacts = _coverage_sequence(manifest["artifacts"], context="manifest artifacts")
    expected_artifacts = {
        "coverage-report.json",
        "operator-facility-index.jsonl",
        "operator-job-index.jsonl",
        "aggregate-coverage.csv",
    }
    artifact_names = {
        str(_coverage_mapping(item, context="artifact")["name"]) for item in artifacts
    }
    if artifact_names != expected_artifacts:
        raise CoverageContractError("Coverage manifest artifact set is invalid.")
    loaded_jsonl: dict[str, tuple[Mapping[str, Any], ...]] = {}
    report: Mapping[str, Any] | None = None
    for item in artifacts:
        artifact = _coverage_mapping(item, context="manifest artifact")
        name = str(artifact["name"])
        path = package_dir / name
        availability = str(artifact["availability"])
        if availability == "unavailable":
            if path.exists():
                raise CoverageContractError("An unavailable artifact must not retain bytes.")
            continue
        try:
            content = path.read_bytes()
        except OSError as exc:
            raise CoverageContractError("An available coverage artifact is missing.") from exc
        if len(content) != int(artifact["byte_count"]):
            raise CoverageContractError("Coverage artifact byte count validation failed.")
        if _coverage_sha256(content) != artifact["sha256"]:
            raise CoverageContractError("Coverage artifact hash validation failed.")
        if name == "coverage-report.json":
            report = _read_canonical_coverage_json(path)
            _validate_coverage_schema_payload(report, schema=schema)
        elif name.endswith(".jsonl"):
            rows = _read_canonical_coverage_jsonl(path)
            for row in rows:
                _validate_coverage_schema_payload(row, schema=schema)
                if row["contract_version"] != manifest["contract_version"] or row[
                    "report_id"
                ] != manifest["report_id"]:
                    raise CoverageContractError("Coverage artifact identity mismatch.")
            loaded_jsonl[name] = rows
        elif name == "aggregate-coverage.csv":
            if b"\r" in content:
                raise CoverageContractError("Aggregate CSV must use LF line endings.")
            try:
                csv_text = content.decode("utf-8")
                reader = csv.DictReader(io.StringIO(csv_text, newline=""))
                csv_rows = tuple(reader)
            except (UnicodeDecodeError, csv.Error) as exc:
                raise CoverageContractError("Aggregate CSV serialization is invalid.") from exc
            if tuple(reader.fieldnames or ()) != COVERAGE_AGGREGATE_CSV_FIELDNAMES:
                raise CoverageContractError("Aggregate CSV header is invalid.")
            for row in csv_rows:
                if (
                    row["contract_version"] != manifest["contract_version"]
                    or row["report_id"] != manifest["report_id"]
                ):
                    raise CoverageContractError("Aggregate CSV identity mismatch.")
    if report is None:
        raise CoverageContractError("The aggregate coverage report is unavailable.")
    for name in (
        "contract_version",
        "report_id",
        "generated_at",
        "evaluation_id",
        "criteria_set_id",
        "scope_id",
        "producer_schema_id",
        "package_availability",
    ):
        if report[name] != manifest[name]:
            raise CoverageContractError("Coverage report and manifest do not reconcile.")
    if report["source_snapshots"] != manifest["source_snapshots"]:
        raise CoverageContractError("Coverage source snapshots do not reconcile.")
    if report["reconciliation"]["reconciliation_status"] != "passed":
        raise CoverageContractError("Coverage package reconciliation failed.")
    if manifest["package_availability"] in {
        "unavailable",
        "version_mismatch",
        "hash_failed",
        "reconciliation_failed",
    }:
        raise CoverageContractError("Coverage package failed closed validation.")
    facility_rows = loaded_jsonl.get("operator-facility-index.jsonl", ())
    normalized_order = tuple(
        (str(row["facility_id"]).strip().casefold(), str(row["facility_entry_id"]))
        for row in facility_rows
    )
    if normalized_order != tuple(sorted(normalized_order)):
        raise CoverageContractError("Operator facility ordering is not canonical.")
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit complaint and facility data completeness from retained source identity "
            "through storage and current reviewer consumers."
        )
    )
    parser.add_argument(
        "--mode",
        choices=("local", "runtime"),
        default="local",
        help="local repository/SQLite audit or aggregate-only runtime PostgreSQL audit",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="directory for generated, untracked audit artifacts",
    )
    parser.add_argument(
        "--write-tracked-baseline",
        action="store_true",
        help="update the four safe tracked baseline documents (local mode only)",
    )
    parser.add_argument(
        "--coverage-fixture",
        type=Path,
        help="governed scenario bundle for an Issues #453/#477 contract package",
    )
    parser.add_argument(
        "--coverage-scenario",
        help="named scenario in --coverage-fixture",
    )
    parser.add_argument(
        "--generated-at",
        help="optional fixed UTC Z timestamp for deterministic fixture validation",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.coverage_fixture is not None:
            if not args.coverage_scenario:
                raise CoverageContractError(
                    "A named coverage scenario is required with a governed fixture."
                )
            if args.mode != "local" or args.write_tracked_baseline:
                raise CoverageContractError(
                    "Governed fixture package generation is local and does not write baselines."
                )
            fixed_time: datetime | None = None
            if args.generated_at is not None:
                timestamp = _coverage_timestamp(
                    args.generated_at, context="generated_at", nullable=False
                )
                assert timestamp is not None
                fixed_time = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=UTC
                )
            output_dir = args.output_dir or Path(
                "data/processed/source-to-screen-audit/" + args.coverage_scenario
            )
            fixture = load_coverage_fixture_scenario(
                args.coverage_fixture, args.coverage_scenario
            )
            package = generate_coverage_package(
                fixture,
                output_dir=output_dir,
                generated_at=fixed_time,
            )
            print(
                "source-to-screen coverage package complete: "
                f"{package.report_id}, {len(package.facility_index)} facility rows"
            )
            return 0
        if args.coverage_scenario is not None or args.generated_at is not None:
            raise CoverageContractError(
                "Coverage scenario metadata requires --coverage-fixture."
            )
        output_dir = args.output_dir or Path(
            f"data/processed/source-to-screen-audit/{args.mode}"
        )
        result = run_audit(
            mode=cast(AuditMode, args.mode),
            output_dir=output_dir,
            write_tracked_baseline=bool(args.write_tracked_baseline),
        )
    except (AuditExecutionError, CoverageContractError, ValueError) as exc:
        print(
            "source-to-screen audit failed: "
            + redact_sensitive_text(str(exc), redact_urls=True),
            file=sys.stderr,
        )
        return 2
    except OSError:
        print(
            "source-to-screen audit failed: audit inputs or outputs could not be accessed.",
            file=sys.stderr,
        )
        return 2
    print(
        "source-to-screen audit complete: "
        f"{len(result.inventory)} elements, {len(result.gap_register)} classified gaps"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
