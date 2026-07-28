"""Read-only hosted corpus verification for post-deployment acceptance."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from sqlalchemy import text
from sqlalchemy.engine import Connection

from ccld_complaints.hosted_app.ccld_retrieval_jobs import load_ccld_retrieval_config
from ccld_complaints.hosted_app.seeded_import import hosted_source_derived_records
from ccld_complaints.hosted_app.source_derived_reads import (
    FacilityIntelligenceReadFilters,
    SourceDerivedRecordRead,
    list_facility_intelligence_page,
    list_source_derived_complaint_bundle,
    list_source_derived_records,
)

CORPUS_VERIFICATION_CONTRACT_ID = "recordstracker.hosted-corpus-verification.v1"
CORPUS_VERIFICATION_CONTRACT_VERSION = "1.0.0"
SCHEMA_PATH = Path("schemas/hosted-corpus-verification-v1.schema.json")
PAGE_DATA_MODE_ENV = "CCLD_HOSTED_PAGE_DATA_MODE"
EXPECTED_PAGE_DATA_MODE = "postgres"
MINIMUM_REAL_CORPUS_FACILITY_COUNT = 2
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SYNTHETIC_MARKERS = (
    "fixture",
    "demo",
    "mock",
    "test",
    "synthetic",
    "sample",
    "tiny",
    "emergency",
)


def run_hosted_corpus_verification(
    connection: Connection,
    *,
    deployed_sha: str | None,
    displayed_facility_count: int | None = None,
    displayed_complaint_count: int | None = None,
    environ: Mapping[str, str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return one deterministic, non-secret audit result without writing data."""
    active_environ = os.environ if environ is None else environ
    execution_time = (now or datetime.now(UTC)).astimezone(UTC).isoformat().replace("+00:00", "Z")
    page_data_mode = active_environ.get(PAGE_DATA_MODE_ENV, "").strip().casefold() or "unset"
    retrieval = load_ccld_retrieval_config(active_environ)
    records = list_source_derived_records(connection)
    facilities = tuple(record for record in records if record.entity_type == "facility")
    complaints = tuple(record for record in records if record.entity_type == "complaint")
    facility_page = list_facility_intelligence_page(
        connection,
        filters=FacilityIntelligenceReadFilters(),
    )
    complaint_bundle = list_source_derived_complaint_bundle(connection)
    facility_duplicates = _duplicates(facilities, _facility_identity)
    complaint_duplicates = _duplicates(complaints, _complaint_identity)
    repeated_display = _duplicates(complaint_bundle.records, _complaint_identity)
    source_linkage = _source_linkage(complaints, records)
    synthetic = _synthetic_records(records)
    provenance = _provenance(records)
    blocking_failures = _blocking_failures(
        page_data_mode=page_data_mode,
        persisted_facility_count=len(facilities),
        read_model_facility_count=facility_page.total_matching_facility_count,
        persisted_complaint_count=len(complaints),
        displayed_complaint_count=len(complaint_bundle.records),
        facility_duplicates=facility_duplicates,
        complaint_duplicates=complaint_duplicates,
        repeated_display=repeated_display,
        source_linkage=source_linkage,
        synthetic=synthetic,
        provenance=provenance,
    )
    result: dict[str, Any] = {
        "contract_id": CORPUS_VERIFICATION_CONTRACT_ID,
        "contract_version": CORPUS_VERIFICATION_CONTRACT_VERSION,
        "executed_at": execution_time,
        "application_sha": deployed_sha or "unavailable",
        "data_mode": {"page_data_mode": page_data_mode, "expected": EXPECTED_PAGE_DATA_MODE},
        "retrieval_mode": {
            "enabled": retrieval.enabled,
            "demo_mode": retrieval.demo_mode,
            "fallback_or_demo_active": (
                retrieval.mock_success_demo_enabled or page_data_mode != EXPECTED_PAGE_DATA_MODE
            ),
        },
        "counts": {
            "persisted_facility_count": len(facilities),
            "read_model_facility_count": facility_page.total_matching_facility_count,
            "displayed_facility_count": displayed_facility_count,
            "persisted_complaint_count": len(complaints),
            "unique_complaint_count": len({_complaint_identity(record) for record in complaints}),
            "displayed_complaint_count": displayed_complaint_count,
            "read_model_displayed_complaint_count": len(complaint_bundle.records),
        },
        "counting_rules": {
            "facility": "Compare Facilities total_matching_facility_count with default filters",
            "complaint": (
                "source-derived complaint rows grouped by complaint_id, then "
                "stable_source_id"
            ),
            "display": "Complaint Worklist default read-model records",
        },
        "identity_rules": {
            "facility": (
                "facility_id, external_facility_number, facility_number, then "
                "stable_source_id"
            ),
            "complaint": "complaint_id, then stable_source_id",
        },
        "duplicates": {
            "facility_identities": facility_duplicates,
            "complaint_identities": complaint_duplicates,
            "repeated_display_identities": repeated_display,
        },
        "source_linkage": source_linkage,
        "synthetic_and_fallback": {
            "synthetic_records": synthetic,
            "fallback_markers": provenance["fallback_markers"],
            "tiny_corpus": len(facilities) < MINIMUM_REAL_CORPUS_FACILITY_COUNT,
        },
        "representatives": {
            "facilities": _representatives(facilities, _facility_identity),
            "complaints": _representatives(complaints, _complaint_identity),
        },
        "provenance": provenance,
        "reviewer_state_separation": _reviewer_state_separation(connection),
        "blocking_failures": blocking_failures,
        "warnings": _warnings(records, displayed_facility_count, displayed_complaint_count),
        "limitations": [
            "The audit reads the deployed database and runtime configuration only.",
            "Displayed counts are unavailable unless captured and supplied by the operator.",
            "No live source retrieval, reviewer-state mutation, or deployment occurs.",
        ],
        "artifact_disposition": {"disposition": "created", "content_materially_changed": True},
    }
    validate_corpus_verification_result(result)
    return result


def write_corpus_verification_result(path: Path, result: Mapping[str, Any]) -> str:
    """Write canonical JSON and return its SHA-256 companion value."""
    validate_corpus_verification_result(result)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    path.write_text(payload, encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_corpus_verification_result(result: Mapping[str, Any]) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(dict(result))
    serialized = json.dumps(result, sort_keys=True, ensure_ascii=True)
    if any(
        marker in serialized.casefold()
        for marker in ("postgresql://", "password=", "authorization:")
    ):
        raise ValueError("Corpus verification result contains prohibited secret-like content.")


def set_postgresql_transaction_read_only(connection: Connection) -> None:
    """Make the current PostgreSQL transaction explicitly read-only."""
    if connection.dialect.name == "postgresql":
        connection.execute(text("SET TRANSACTION READ ONLY"))


def _facility_identity(record: SourceDerivedRecordRead) -> str:
    return _first_text(
        record.original_values.get("facility_id"),
        record.original_values.get("external_facility_number"),
        record.original_values.get("facility_number"),
        record.facility_id,
        record.stable_source_id,
    )


def _complaint_identity(record: SourceDerivedRecordRead) -> str:
    return _first_text(record.original_values.get("complaint_id"), record.stable_source_id)


def _first_text(*values: object) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return " ".join(value.split())
    return "unavailable"


def _duplicates(records: Sequence[SourceDerivedRecordRead], identity: Any) -> list[dict[str, Any]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for record in records:
        grouped[str(identity(record))].append(record.source_record_key)
    return [
        {"identity": key, "record_keys": sorted(keys)}
        for key, keys in sorted(grouped.items())
        if len(keys) > 1
    ]


def _source_linkage(
    complaints: Sequence[SourceDerivedRecordRead],
    records: Sequence[SourceDerivedRecordRead],
) -> dict[str, list[dict[str, Any]]]:
    document_ids = {
        record.stable_source_id
        for record in records
        if record.entity_type == "source_document"
    }
    missing = [
        {"record_key": record.source_record_key, "source_document_id": record.source_document_id}
        for record in complaints
        if record.source_document_id not in document_ids
    ]
    conflicts = [
        {"record_key": record.source_record_key, "source_document_id": record.source_document_id}
        for record in complaints
        if record.source_document_id
        != record.source_traceability.get("source_document_id", record.source_document_id)
    ]
    return {"missing": missing, "conflicting": conflicts}


def _synthetic_records(records: Sequence[SourceDerivedRecordRead]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for record in records:
        haystack = " ".join(
            (
                record.source_record_key,
                record.stable_source_id,
                str(record.original_values.get("facility_name", "")),
            )
        ).casefold()
        if any(marker in haystack for marker in _SYNTHETIC_MARKERS):
            findings.append({"record_key": record.source_record_key, "reason": "synthetic marker"})
    return findings


def _provenance(records: Sequence[SourceDerivedRecordRead]) -> dict[str, Any]:
    missing: list[str] = []
    fallback: list[dict[str, str]] = []
    samples: list[dict[str, str]] = []
    for record in records:
        if (
            not record.source_url
            or not _SHA256.fullmatch(record.raw_sha256)
            or not record.retrieved_at
        ):
            missing.append(record.source_record_key)
        marker_text = " ".join(
            (
                record.import_batch.source_artifact_identity,
                record.import_batch.source_pipeline_version or "",
                record.connector_name,
            )
        ).casefold()
        if any(marker in marker_text for marker in _SYNTHETIC_MARKERS):
            fallback.append({"record_key": record.source_record_key, "reason": "provenance marker"})
        if len(samples) < 10:
            samples.append(
                {
                    "record_key": record.source_record_key,
                    "source_url_available": str(bool(record.source_url)).lower(),
                    "raw_sha256": record.raw_sha256,
                    "retrieved_at": record.retrieved_at,
                    "connector": f"{record.connector_name}@{record.connector_version}",
                    "import_batch_id": record.import_batch.import_batch_id,
                }
            )
    return {"missing": sorted(missing), "fallback_markers": fallback, "samples": samples}


def _representatives(
    records: Sequence[SourceDerivedRecordRead], identity: Any
) -> list[dict[str, str]]:
    return [
        {
            "identity": str(identity(record)),
            "record_key": record.source_record_key,
            "source_document_id": record.source_document_id,
        }
        for record in sorted(
            records,
            key=lambda item: (str(identity(item)), item.source_record_key),
        )[:5]
    ]


def _reviewer_state_separation(connection: Connection) -> dict[str, Any]:
    table_names = set(connection.dialect.get_table_names(connection))
    present = "hosted_reviewer_created_state" in table_names
    return {
        "separate_table_present": present,
        "source_derived_table": hosted_source_derived_records.name,
        "reviewer_created_table": "hosted_reviewer_created_state" if present else "unavailable",
        "mutation_performed": False,
    }


def _blocking_failures(**values: Any) -> list[str]:
    failures: list[str] = []
    if values["page_data_mode"] != EXPECTED_PAGE_DATA_MODE:
        failures.append("page_data_mode_not_postgres")
    if values["persisted_facility_count"] != values["read_model_facility_count"]:
        failures.append("facility_count_mismatch")
    if values["persisted_complaint_count"] != values["displayed_complaint_count"]:
        failures.append("complaint_count_mismatch")
    if any(
        values[key]
        for key in ("facility_duplicates", "complaint_duplicates", "repeated_display")
    ):
        failures.append("duplicate_or_repeated_identity")
    if any(values["source_linkage"].values()):
        failures.append("source_document_linkage_failure")
    if values["synthetic"]:
        failures.append("synthetic_records_detected")
    if values["provenance"]["fallback_markers"]:
        failures.append("fallback_provenance_detected")
    if values["provenance"]["missing"]:
        failures.append("missing_provenance")
    if values["persisted_facility_count"] < MINIMUM_REAL_CORPUS_FACILITY_COUNT:
        failures.append("implausibly_small_corpus")
    return failures


def _warnings(
    records: Sequence[SourceDerivedRecordRead],
    displayed_facility_count: int | None,
    displayed_complaint_count: int | None,
) -> list[str]:
    warnings: list[str] = []
    if not records:
        warnings.append("No source-derived records were available.")
    if displayed_facility_count is None:
        warnings.append("Displayed facility count was not supplied.")
    if displayed_complaint_count is None:
        warnings.append("Displayed complaint count was not supplied.")
    return warnings
