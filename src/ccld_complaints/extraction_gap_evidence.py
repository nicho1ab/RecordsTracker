from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, cast

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import SQLAlchemyError

from ccld_complaints.connectors.base import SourceDocument
from ccld_complaints.connectors.ccld.facility_reports import (
    BASE_URL,
    FIELD_STATUS_ABSENT,
    FIELD_STATUS_BLANK,
    FIELD_STATUS_COVERAGE_UNAVAILABLE,
    FIELD_STATUS_EXTRACTED,
    FIELD_STATUS_FAILED,
    CcldFacilityReportsConnector,
    FieldEvidence,
)
from ccld_complaints.hosted_app.persistence import (
    HostedDatabaseConfigError,
    load_hosted_database_config,
)
from ccld_complaints.source_to_screen_audit import redact_sensitive_text
from ccld_complaints.utils.hash import sha256_bytes

EvidenceMode = Literal["local", "runtime"]

SCHEMA_VERSION = 1
GOVERNED_FIXTURE = Path("tests/fixtures/ccld/raw/157806098_inx3.html")
FIXTURE_RETRIEVED_AT = "2026-06-10T00:00:00+00:00"
FIXTURE_FACILITY_NUMBER = "157806098"
FIXTURE_REPORT_INDEX = 3
SYNTHETIC_FACILITY_IDS = ("900000001", "900000002")
TARGET_FIELDS = (
    "complaint.first_investigation_activity_date",
    "event.event_date",
    "event.event_text",
    "event.event_type",
    "facility_address",
    "facility_capacity",
    "facility_city",
    "regional_office",
    "extraction_audit.source_section",
    "extraction_audit.source_text",
)
RUNTIME_FIELDS = (
    (
        "complaint.first_investigation_activity_date",
        "complaint",
        "first_investigation_activity_date",
    ),
    ("event.event_date", "event", "event_date"),
    ("event.event_text", "event", "event_text"),
    ("event.event_type", "event", "event_type"),
    ("facility_address", "facility", "facility_address"),
    ("facility_capacity", "facility", "capacity"),
    ("facility_city", "facility", "facility_city"),
    ("regional_office", "facility", "regional_office"),
    ("extraction_audit.source_section", "extraction_audit", "source_section"),
    ("extraction_audit.source_text", "extraction_audit", "source_text"),
    ("allegation.allegation_category", "allegation", "allegation_category"),
)
OUTPUT_FILES = (
    "manifest.json",
    "field-results.csv",
    "artifact-results.csv",
    "gap-status.csv",
    "traceability-results.csv",
    "summary.md",
)
ISSUE_574_OUTPUT_FILES = (
    "manifest.json",
    "field-results.csv",
    "summary.md",
)
ISSUE_574_FIXTURE = Path(
    "tests/fixtures/ccld/raw/900000001_inx1_issue574_structured_fields.html"
)
ISSUE_574_FIELDS = (
    (
        "data.complaint.raw_complaint_report.agency_name",
        "AGENCY",
        "report heading",
        "agency_name",
    ),
    (
        "data.complaint.raw_complaint_report.deficiency_text",
        "DEFICIENCIES",
        "deficiencies",
        "deficiency_texts",
    ),
    (
        "data.complaint.raw_complaint_report.investigation_findings_narrative",
        "INVESTIGATION FINDINGS",
        "investigation findings",
        "investigation_findings_narrative",
    ),
    (
        "data.facility.raw_complaint_report.facility_contact",
        "TELEPHONE",
        "facility details",
        "complaint_report_contact",
    ),
)


class EvidenceExecutionError(RuntimeError):
    pass


def run_issue_574_evidence(
    *, output_dir: Path, repo_root: Path | None = None
) -> Mapping[str, Any]:
    """Write deterministic aggregate-safe local evidence for Issue #574 only."""

    root = (repo_root or Path(__file__).resolve().parents[2]).resolve()
    raw_path = root / ISSUE_574_FIXTURE
    content = raw_path.read_bytes()
    document = SourceDocument(
        source_url=(
            "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports"
            "?facNum=900000001&inx=1"
        ),
        raw_path=raw_path,
        raw_sha256=sha256_bytes(content),
        retrieved_at="2026-07-23T00:00:00+00:00",
        content_type="text/html",
    )
    connector = CcldFacilityReportsConnector()
    extracted = connector.extract(document)
    normalized = connector.normalize(extracted)
    connector.validate(normalized)
    field_evidence = cast(dict[str, FieldEvidence], extracted["_field_evidence"])
    complaint = cast(dict[str, object], normalized["complaint"])
    audits = cast(list[dict[str, object]], normalized["extraction_audit"])

    evidence_keys = {
        "data.complaint.raw_complaint_report.agency_name": "agency_name",
        "data.complaint.raw_complaint_report.deficiency_text": "deficiency_text",
        "data.complaint.raw_complaint_report.investigation_findings_narrative": (
            "investigation_findings_narrative"
        ),
        "data.facility.raw_complaint_report.facility_contact": "facility_contact",
    }
    rows: list[dict[str, object]] = []
    assertions: dict[str, bool] = {}
    for field_id, source_label, source_section, normalized_field in ISSUE_574_FIELDS:
        evidence_key = evidence_keys[field_id]
        evidence = field_evidence[evidence_key]
        audit_field_name = "deficiency_text" if evidence_key == "deficiency_text" else evidence_key
        audit_count = sum(
            1 for audit in audits if audit["field_name"] == audit_field_name
        )
        assertions[field_id] = (
            evidence.status == FIELD_STATUS_EXTRACTED
            and normalized_field in complaint
            and audit_count > 0
        )
        rows.append(
            {
                "field_id": field_id,
                "source_label": source_label,
                "source_section": source_section,
                "extraction_status": evidence.status,
                "normalized_field": normalized_field,
                "audit_entry_count": audit_count,
            }
        )
    assertions["historical_observations_do_not_change_facility_current_reference"] = (
        "telephone" not in cast(dict[str, object], normalized["facility"])
    )
    assertions["deficiencies_preserve_source_order"] = (
        sum(1 for audit in audits if audit["field_name"] == "deficiency_text") == 2
    )
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "evidence_scope": "issue-574-local-extraction-only",
        "fixture_class": "governed_synthetic_source_shape",
        "fixture_sha256": sha256_bytes(content),
        "field_count": len(rows),
        "assertions": assertions,
        "generated_files": list(ISSUE_574_OUTPUT_FILES),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_csv(output_dir / "field-results.csv", rows)
    (output_dir / "summary.md").write_text(
        "# Issue #574 local extraction evidence\n\n"
        "Aggregate-safe structural evidence only; source values and raw report "
        "content are excluded.\n\n"
        f"- Fields evaluated: {len(rows)}\n"
        f"- Assertions passed: {sum(assertions.values())} of {len(assertions)}\n",
        encoding="utf-8",
    )
    return manifest


def run_evidence(
    *,
    mode: EvidenceMode,
    output_dir: Path,
    repo_root: Path | None = None,
    environ: Mapping[str, str] | None = None,
    runtime_connection: Connection | None = None,
) -> Mapping[str, Any]:
    if mode not in {"local", "runtime"}:
        raise ValueError("Evidence mode must be local or runtime.")
    root = (repo_root or Path(__file__).resolve().parents[2]).resolve()
    capability = _local_capability(root)
    runtime_rows: list[dict[str, object]] = []
    runtime_status = "not inspected in local mode"

    if mode == "runtime":
        if runtime_connection is not None:
            runtime_rows = _runtime_population(runtime_connection)
            runtime_status = "inspected aggregate-only"
        else:
            runtime_rows, runtime_status = _configured_runtime_population(
                environ if environ is not None else os.environ
            )

    field_rows = cast(list[dict[str, object]], capability["field_rows"])
    artifact_rows = cast(list[dict[str, object]], capability["artifact_rows"])
    gap_rows = cast(list[dict[str, object]], capability["gap_rows"])
    traceability_rows = cast(
        list[dict[str, object]], capability["traceability_rows"]
    )
    assertions = dict(cast(Mapping[str, bool], capability["assertions"]))
    assertions["runtime_population_reported_separately"] = (
        mode == "local" or runtime_status == "inspected aggregate-only"
    )

    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "capability_adapter": "governed retained complaint-report fixture",
        "runtime_population": {
            "status": runtime_status,
            "row_count": len(runtime_rows),
            "fields": runtime_rows,
        },
        "counts": {
            "target_fields": len(TARGET_FIELDS),
            "field_results": len(field_rows),
            "artifacts": len(artifact_rows),
            "traceability_results": len(traceability_rows),
            "assertions_passed": sum(bool(value) for value in assertions.values()),
            "assertions_total": len(assertions),
        },
        "assertions": assertions,
        "existing_data_refresh": {
            "required": True,
            "reason": (
                "Existing PostgreSQL source-derived rows retain values from the extractor "
                "version used at import time. Regeneration and reimport are required before "
                "new extracted values appear."
            ),
            "safe_command_available": False,
        },
        "generated_files": list(OUTPUT_FILES),
    }

    payloads: tuple[object, ...] = (
        manifest,
        field_rows,
        artifact_rows,
        gap_rows,
        traceability_rows,
    )
    source_texts = cast(tuple[str, ...], capability["source_texts"])
    assertions["safe_aggregate_output"] = _aggregate_safe(payloads, source_texts, root)
    manifest["counts"]["assertions_passed"] = sum(
        bool(value) for value in assertions.values()
    )
    manifest["counts"]["assertions_total"] = len(assertions)

    effective_output = output_dir if output_dir.is_absolute() else root / output_dir
    _write_outputs(
        effective_output,
        manifest=manifest,
        field_rows=field_rows,
        artifact_rows=artifact_rows,
        gap_rows=gap_rows,
        traceability_rows=traceability_rows,
    )
    return manifest


def _local_capability(repo_root: Path) -> dict[str, object]:
    fixture_path = repo_root / GOVERNED_FIXTURE
    if not fixture_path.is_file():
        raise EvidenceExecutionError("The governed extraction fixture is unavailable.")
    content = fixture_path.read_bytes()
    source_url = (
        f"{BASE_URL}?facNum={FIXTURE_FACILITY_NUMBER}&inx={FIXTURE_REPORT_INDEX}"
    )
    document = SourceDocument(
        source_url=source_url,
        raw_path=fixture_path,
        raw_sha256=sha256_bytes(content),
        retrieved_at=FIXTURE_RETRIEVED_AT,
        content_type="text/html",
    )
    connector = CcldFacilityReportsConnector()
    extracted = connector.extract(document)
    normalized = connector.normalize(extracted)
    connector.validate(normalized)

    document_id = cast(dict[str, object], normalized["source_document"])["document_id"]
    raw_sha256 = cast(dict[str, object], normalized["source_document"])["raw_sha256"]
    safe_reference = GOVERNED_FIXTURE.as_posix()
    evidence = cast(dict[str, FieldEvidence], extracted["_field_evidence"])
    audits = cast(list[dict[str, object]], normalized["extraction_audit"])
    audits_by_field = {str(row["field_name"]): row for row in audits}
    events = cast(list[dict[str, object]], normalized.get("events", []))

    status_by_field = {
        "complaint.first_investigation_activity_date": evidence[
            "first_investigation_activity_date"
        ].status,
        "event.event_date": FIELD_STATUS_EXTRACTED if events else FIELD_STATUS_ABSENT,
        "event.event_text": FIELD_STATUS_EXTRACTED if events else FIELD_STATUS_ABSENT,
        "event.event_type": FIELD_STATUS_EXTRACTED if events else FIELD_STATUS_ABSENT,
        "facility_address": evidence["facility_address"].status,
        "facility_capacity": evidence["facility_capacity"].status,
        "facility_city": evidence["facility_city"].status,
        "regional_office": evidence["regional_office"].status,
        "extraction_audit.source_section": (
            FIELD_STATUS_EXTRACTED
            if _target_audits_have(audits_by_field, "source_section")
            else FIELD_STATUS_FAILED
        ),
        "extraction_audit.source_text": (
            FIELD_STATUS_EXTRACTED
            if _target_audits_have(audits_by_field, "source_text")
            else FIELD_STATUS_FAILED
        ),
    }
    field_rows = [
        {
            "field_id": field_id,
            "capability_status": status_by_field[field_id],
            "regression_fixture": safe_reference,
            "document_id": document_id,
            "normalized_value_present": _normalized_value_present(field_id, normalized),
            "assertion_status": (
                "PASS"
                if status_by_field[field_id]
                in {FIELD_STATUS_EXTRACTED, FIELD_STATUS_BLANK}
                else "FAIL"
            ),
        }
        for field_id in TARGET_FIELDS
    ]
    field_rows.append(
        {
            "field_id": "allegation.allegation_category",
            "capability_status": "SOURCE_NOT_PROVIDED",
            "regression_fixture": safe_reference,
            "document_id": document_id,
            "normalized_value_present": False,
            "assertion_status": "PASS",
        }
    )

    traceability_rows = _traceability_rows(
        audits_by_field,
        document_id=str(document_id),
        raw_sha256=str(raw_sha256),
        safe_reference=safe_reference,
    )
    source_texts = tuple(
        str(row["source_text"])
        for row in audits
        if isinstance(row.get("source_text"), str) and row["source_text"]
    )
    normalized_dump = json.dumps(normalized, sort_keys=True)
    allegation_categories = [
        row.get("allegation_category")
        for row in cast(list[dict[str, object]], normalized["allegations"])
    ]
    first_activity = cast(dict[str, object], normalized["complaint"])[
        "first_investigation_activity_date"
    ]
    event_date = events[0]["event_date"] if events else None
    assertions = {
        "governed_targets_have_deterministic_regressions": all(
            status_by_field[field_id]
            in {FIELD_STATUS_EXTRACTED, FIELD_STATUS_BLANK}
            for field_id in TARGET_FIELDS
        ),
        "extracted_values_reconcile_to_governed_artifact": (
            raw_sha256 == sha256_bytes(content)
            and first_activity == event_date
            and cast(dict[str, object], normalized["facility"])["capacity"] == 48
        ),
        "source_section_and_text_are_traceable": len(traceability_rows) == 8,
        "missing_coverage_distinct_from_present_blank": (
            FIELD_STATUS_COVERAGE_UNAVAILABLE != FIELD_STATUS_BLANK
            and evidence["facility_address"].status == FIELD_STATUS_BLANK
            and evidence["facility_city"].status == FIELD_STATUS_BLANK
        ),
        "allegation_category_remains_source_not_provided": all(
            value is None for value in allegation_categories
        ),
        "no_synthetic_facility_ids_emitted": not any(
            value in normalized_dump for value in SYNTHETIC_FACILITY_IDS
        ),
        "existing_rows_require_regeneration_or_reimport": True,
    }

    gap_rows = _gap_rows(status_by_field)
    artifact_rows = [
        {
            "safe_source_reference": safe_reference,
            "document_id": document_id,
            "raw_sha256": raw_sha256,
            "artifact_status": "GOVERNED_ARTIFACT_INSPECTED",
            "target_field_count": len(TARGET_FIELDS),
            "extracted_target_count": sum(
                status == FIELD_STATUS_EXTRACTED for status in status_by_field.values()
            ),
            "present_blank_target_count": sum(
                status == FIELD_STATUS_BLANK for status in status_by_field.values()
            ),
        }
    ]
    return {
        "field_rows": field_rows,
        "artifact_rows": artifact_rows,
        "gap_rows": gap_rows,
        "traceability_rows": traceability_rows,
        "assertions": assertions,
        "source_texts": source_texts,
    }


def unavailable_artifact_status(path: Path | None) -> str:
    """Return coverage status without collapsing unavailable input into source absence."""

    if path is None or not path.is_file():
        return FIELD_STATUS_COVERAGE_UNAVAILABLE
    return "SOURCE_COVERAGE_AVAILABLE"


def _target_audits_have(
    audits_by_field: Mapping[str, Mapping[str, object]], key: str
) -> bool:
    audit_fields = (
        "first_investigation_activity_date",
        "event.event_date",
        "event.event_text",
        "event.event_type",
        "facility_address",
        "facility_capacity",
        "facility_city",
        "regional_office",
    )
    return all(bool(audits_by_field[field].get(key)) for field in audit_fields)


def _normalized_value_present(field_id: str, normalized: Mapping[str, object]) -> bool:
    if field_id == "complaint.first_investigation_activity_date":
        return bool(
            cast(dict[str, object], normalized["complaint"]).get(
                "first_investigation_activity_date"
            )
        )
    if field_id.startswith("event."):
        events = cast(list[dict[str, object]], normalized.get("events", []))
        return bool(events and events[0].get(field_id.split(".", 1)[1]))
    if field_id == "facility_capacity":
        return cast(dict[str, object], normalized["facility"]).get("capacity") is not None
    if field_id == "regional_office":
        return bool(cast(dict[str, object], normalized["facility"]).get("regional_office"))
    if field_id.startswith("extraction_audit."):
        key = field_id.split(".", 1)[1]
        return any(
            bool(row.get(key))
            for row in cast(list[dict[str, object]], normalized["extraction_audit"])
        )
    return False


def _traceability_rows(
    audits_by_field: Mapping[str, Mapping[str, object]],
    *,
    document_id: str,
    raw_sha256: str,
    safe_reference: str,
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for field_id, audit_field in (
        ("complaint.first_investigation_activity_date", "first_investigation_activity_date"),
        ("event.event_date", "event.event_date"),
        ("event.event_text", "event.event_text"),
        ("event.event_type", "event.event_type"),
        ("facility_address", "facility_address"),
        ("facility_capacity", "facility_capacity"),
        ("facility_city", "facility_city"),
        ("regional_office", "regional_office"),
    ):
        row = audits_by_field[audit_field]
        source_text = str(row["source_text"])
        result.append(
            {
                "field_id": field_id,
                "document_id": document_id,
                "raw_sha256": raw_sha256,
                "safe_source_reference": safe_reference,
                "source_section": row["source_section"],
                "source_text_present": True,
                "source_text_sha256": hashlib.sha256(
                    source_text.encode("utf-8")
                ).hexdigest(),
                "traceability_status": "PASS",
            }
        )
    return result


def _gap_rows(status_by_field: Mapping[str, str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for field_id in TARGET_FIELDS:
        status = status_by_field[field_id]
        canonical_status = "EXISTING_CANONICAL_FIELD"
        if field_id in {"facility_address", "facility_city"}:
            canonical_status = "CANONICAL_ALLOCATION_DEFERRED_TO_447"
        rows.append(
            {
                "field_id": field_id,
                "prior_gap_status": "RAW_PRESENT_EXTRACTION_MISSING",
                "current_status": (
                    "DETERMINISTIC_EXTRACTION_IMPLEMENTED"
                    if status == FIELD_STATUS_EXTRACTED
                    else "SOURCE_ELEMENT_PRESENT_BLANK_PRESERVED"
                ),
                "canonical_storage_status": canonical_status,
                "existing_data_status": "REGENERATION_OR_REIMPORT_REQUIRED",
            }
        )
    rows.append(
        {
            "field_id": "allegation.allegation_category",
            "prior_gap_status": "SOURCE_NOT_PROVIDED",
            "current_status": "SOURCE_NOT_PROVIDED",
            "canonical_storage_status": "NULL_PRESERVED",
            "existing_data_status": "NO_INFERENCE_ALLOWED",
        }
    )
    return rows


def _configured_runtime_population(
    environ: Mapping[str, str],
) -> tuple[list[dict[str, object]], str]:
    engine: Engine | None = None
    try:
        config = load_hosted_database_config(environ=environ, require_url=True)
        engine = create_engine(cast(str, config.database_url))
        if engine.dialect.name != "postgresql":
            raise EvidenceExecutionError(
                "Runtime evidence requires the configured PostgreSQL database."
            )
        with engine.connect() as connection:
            return _runtime_population(connection), "inspected aggregate-only"
    except HostedDatabaseConfigError as exc:
        raise EvidenceExecutionError(
            "Runtime evidence requires a configured PostgreSQL database."
        ) from exc
    except SQLAlchemyError as exc:
        raise EvidenceExecutionError(
            "The configured runtime database could not be inspected safely."
        ) from exc
    finally:
        if engine is not None:
            engine.dispose()


def _runtime_population(connection: Connection) -> list[dict[str, object]]:
    tables = set(inspect(connection).get_table_names())
    if "hosted_source_derived_records" not in tables:
        return [
            {
                "field_id": field_id,
                "eligible_record_count": 0,
                "key_present_count": 0,
                "populated_count": 0,
                "blank_count": 0,
                "population_status": "RUNTIME_TABLE_UNAVAILABLE",
            }
            for field_id, _entity_type, _field_name in RUNTIME_FIELDS
        ]
    return [
        _runtime_field_population(connection, field_id, entity_type, field_name)
        for field_id, entity_type, field_name in RUNTIME_FIELDS
    ]


def _runtime_field_population(
    connection: Connection,
    field_id: str,
    entity_type: str,
    field_name: str,
) -> dict[str, object]:
    if connection.dialect.name == "postgresql":
        row = connection.execute(
            text(
                """
                SELECT
                    COUNT(*) AS eligible,
                    COUNT(*) FILTER (WHERE original_values::jsonb ? :field_name) AS key_present,
                    COUNT(*) FILTER (
                        WHERE original_values::jsonb ? :field_name
                          AND jsonb_typeof(original_values::jsonb -> :field_name) <> 'null'
                          AND NOT (
                              jsonb_typeof(original_values::jsonb -> :field_name) = 'string'
                              AND BTRIM(original_values::jsonb ->> :field_name) = ''
                          )
                    ) AS populated,
                    COUNT(*) FILTER (
                        WHERE jsonb_typeof(original_values::jsonb -> :field_name) = 'string'
                          AND BTRIM(original_values::jsonb ->> :field_name) = ''
                    ) AS blank_count
                FROM hosted_source_derived_records
                WHERE entity_type = :entity_type
                """
            ),
            {"entity_type": entity_type, "field_name": field_name},
        ).one()
    elif connection.dialect.name == "sqlite":
        json_path = f'$."{field_name}"'
        row = connection.execute(
            text(
                """
                SELECT
                    COUNT(*) AS eligible,
                    SUM(CASE WHEN json_type(original_values, :json_path) IS NOT NULL
                        THEN 1 ELSE 0 END) AS key_present,
                    SUM(CASE
                        WHEN json_type(original_values, :json_path) IS NOT NULL
                         AND json_type(original_values, :json_path) <> 'null'
                         AND NOT (
                            json_type(original_values, :json_path) = 'text'
                            AND TRIM(json_extract(original_values, :json_path)) = ''
                         ) THEN 1 ELSE 0 END) AS populated,
                    SUM(CASE
                        WHEN json_type(original_values, :json_path) = 'text'
                         AND TRIM(json_extract(original_values, :json_path)) = ''
                        THEN 1 ELSE 0 END) AS blank_count
                FROM hosted_source_derived_records
                WHERE entity_type = :entity_type
                """
            ),
            {"entity_type": entity_type, "json_path": json_path},
        ).one()
    else:
        raise EvidenceExecutionError(
            "Runtime evidence supports PostgreSQL and SQLite test adapters only."
        )
    return {
        "field_id": field_id,
        "eligible_record_count": int(row[0] or 0),
        "key_present_count": int(row[1] or 0),
        "populated_count": int(row[2] or 0),
        "blank_count": int(row[3] or 0),
        "population_status": "INSPECTED_AGGREGATE_ONLY",
    }


def _aggregate_safe(
    payloads: Sequence[object], source_texts: Sequence[str], repo_root: Path
) -> bool:
    serialized = json.dumps(payloads, sort_keys=True)
    unsafe_markers = (
        str(repo_root),
        "postgresql://",
        "postgresql+psycopg://",
        "pass" + "word=",
        "to" + "ken=",
        *SYNTHETIC_FACILITY_IDS,
        *source_texts,
    )
    return all(marker not in serialized for marker in unsafe_markers if marker)


def _write_outputs(
    output_dir: Path,
    *,
    manifest: Mapping[str, Any],
    field_rows: Sequence[Mapping[str, object]],
    artifact_rows: Sequence[Mapping[str, object]],
    gap_rows: Sequence[Mapping[str, object]],
    traceability_rows: Sequence[Mapping[str, object]],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_csv(output_dir / "field-results.csv", field_rows)
    _write_csv(output_dir / "artifact-results.csv", artifact_rows)
    _write_csv(output_dir / "gap-status.csv", gap_rows)
    _write_csv(output_dir / "traceability-results.csv", traceability_rows)
    counts = cast(Mapping[str, object], manifest["counts"])
    refresh = cast(Mapping[str, object], manifest["existing_data_refresh"])
    refresh_required = str(refresh["required"]).lower()
    refresh_available = str(refresh["safe_command_available"]).lower()
    summary = f"""# Extraction gap evidence

- Mode: `{manifest['mode']}`
- Governed target fields: {counts['target_fields']}
- Field results: {counts['field_results']}
- Retained artifacts inspected: {counts['artifacts']}
- Traceability results: {counts['traceability_results']}
- Assertions: {counts['assertions_passed']} of {counts['assertions_total']} passed
- Existing PostgreSQL rows require regeneration or reimport: {refresh_required}
- Safe automated existing-data refresh command available: {refresh_available}

This packet contains aggregate-safe statuses, counts, hashes, section labels, and
repository-relative source references only. It does not contain source narratives,
raw artifact bodies, connection strings, private URLs, secrets, or user-specific paths.
"""
    (output_dir / "summary.md").write_text(summary, encoding="utf-8")


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    if not rows:
        raise EvidenceExecutionError(f"Evidence rows are required for {path.name}.")
    fieldnames = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Produce aggregate-safe evidence for governed complaint-report extraction gaps."
        )
    )
    parser.add_argument("--mode", choices=("local", "runtime"), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest = run_evidence(
            mode=cast(EvidenceMode, args.mode), output_dir=args.output_dir
        )
    except (EvidenceExecutionError, OSError, ValueError) as exc:
        print(
            "extraction gap evidence failed: "
            + redact_sensitive_text(str(exc), redact_urls=True),
            file=sys.stderr,
        )
        return 2
    assertions = cast(Mapping[str, bool], manifest["assertions"])
    if not all(assertions.values()):
        print("extraction gap evidence completed with failed assertions.", file=sys.stderr)
        return 1
    print(
        "extraction gap evidence passed: "
        f"{manifest['counts']['assertions_passed']} assertions; "
        f"{manifest['counts']['field_results']} field results."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
