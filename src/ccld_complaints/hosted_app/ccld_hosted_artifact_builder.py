from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path, PureWindowsPath
from typing import Any
from urllib.parse import parse_qs, urlparse

from ccld_complaints.hosted_app.seeded_import import (
    SOURCE_DERIVED_ENTITY_TYPES,
    flatten_seeded_corpus_records,
    parse_seeded_corpus_artifact,
)
from ccld_complaints.quality.validate import validate_schema
from ccld_complaints.storage.sqlite import TABLE_COLUMNS

ARTIFACT_BUILDER_VERSION = "ccld-sqlite-hosted-artifact-builder-0.1.0"
DEFAULT_CCLD_HOSTED_IMPORT_BATCH_ID = "seeded-ccld-fixture-2026-06-13"
DEFAULT_GENERATED_CCLD_HOSTED_ARTIFACT = Path(
    "data/processed/hosted_seeded_corpus/validated_ccld_seeded_corpus.json"
)
CCLD_CONNECTOR_NAME = "ccld_facility_reports"
CCLD_SOURCE_ID = "ccld"
CCLD_SOURCE_HOST = "www.ccld.dss.ca.gov"
RAW_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
FACILITY_NUMBER_PATTERN = re.compile(r"^\d+$")
COMPLAINT_DATE_FIELDS = (
    "complaint_received_date",
    "visit_date",
    "report_date",
    "date_signed",
)
COMPLAINT_BOOLEAN_FIELDS = (
    "review_delay_over_30_days",
    "review_delay_over_60_days",
    "review_delay_over_90_days",
    "review_delay_over_120_days",
    "missing_first_activity_date",
    "report_date_used_as_proxy",
)


@dataclass(frozen=True)
class CcldHostedArtifactBuildResult:
    artifact: Mapping[str, Any]
    output_path: Path | None
    facility_number: str
    record_count: int
    source_derived_record_count: int
    counts_by_entity: Mapping[str, int]


def build_ccld_hosted_seeded_corpus_artifact(
    db_path: Path,
    *,
    facility_number: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    import_batch_id: str = DEFAULT_CCLD_HOSTED_IMPORT_BATCH_ID,
    imported_at: str | None = None,
    source_artifact_identity: str | None = None,
    schema_dir: Path = Path("schemas"),
) -> CcldHostedArtifactBuildResult:
    resolved_db_path = _resolve_existing_db_path(db_path)
    parsed_start_date = _parse_optional_date(start_date, "start_date")
    parsed_end_date = _parse_optional_date(end_date, "end_date")
    if parsed_start_date is not None and parsed_end_date is not None:
        if parsed_end_date < parsed_start_date:
            raise ValueError("end_date must not be before start_date.")

    with sqlite3.connect(resolved_db_path) as connection:
        connection.row_factory = sqlite3.Row
        _require_sqlite_tables(connection)
        selected_facility_number = _selected_facility_number(connection, facility_number)
        records = _record_bundles(
            connection,
            facility_number=selected_facility_number,
            start_date=parsed_start_date,
            end_date=parsed_end_date,
            schema_dir=_resolve_schema_dir(schema_dir),
        )

    if not records:
        raise ValueError(
            "No validated CCLD SQLite complaint records matched the requested "
            "facility/license number and date range."
        )

    record_counts = _record_counts(records)
    artifact: dict[str, Any] = {
        "import_batch_id": _required_non_empty(import_batch_id, "import_batch_id"),
        "imported_at": imported_at or datetime.now(UTC).replace(microsecond=0).isoformat(),
        "source_artifact_identity": source_artifact_identity
        or _default_source_artifact_identity(resolved_db_path),
        "source_pipeline_version": ARTIFACT_BUILDER_VERSION,
        "validation_status": "validated",
        "raw_hash_validation_status": "validated",
        "record_counts": record_counts,
        "warnings": [
            "Local/test CCLD-only artifact built from validated SQLite output; not "
            "complete public-source coverage."
        ],
        "errors": [],
        "records": records,
    }
    parsed_artifact = parse_seeded_corpus_artifact(artifact)
    flattened_records = flatten_seeded_corpus_records(parsed_artifact)

    return CcldHostedArtifactBuildResult(
        artifact=artifact,
        output_path=None,
        facility_number=selected_facility_number,
        record_count=len(records),
        source_derived_record_count=len(flattened_records),
        counts_by_entity=record_counts,
    )


def write_ccld_hosted_seeded_corpus_artifact(
    db_path: Path,
    output_path: Path,
    *,
    facility_number: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    import_batch_id: str = DEFAULT_CCLD_HOSTED_IMPORT_BATCH_ID,
    imported_at: str | None = None,
    source_artifact_identity: str | None = None,
    schema_dir: Path = Path("schemas"),
    overwrite: bool = False,
) -> CcldHostedArtifactBuildResult:
    if output_path.exists() and not overwrite:
        raise ValueError(f"Output artifact already exists: {output_path.as_posix()}")

    result = build_ccld_hosted_seeded_corpus_artifact(
        db_path,
        facility_number=facility_number,
        start_date=start_date,
        end_date=end_date,
        import_batch_id=import_batch_id,
        imported_at=imported_at,
        source_artifact_identity=source_artifact_identity,
        schema_dir=schema_dir,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result.artifact, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return CcldHostedArtifactBuildResult(
        artifact=result.artifact,
        output_path=output_path,
        facility_number=result.facility_number,
        record_count=result.record_count,
        source_derived_record_count=result.source_derived_record_count,
        counts_by_entity=result.counts_by_entity,
    )


def _resolve_existing_db_path(db_path: Path) -> Path:
    if not db_path.exists():
        raise ValueError(f"SQLite database path does not exist: {db_path.as_posix()}")
    if not db_path.is_file():
        raise ValueError(f"SQLite database path must be a file: {db_path.as_posix()}")
    return db_path


def _resolve_schema_dir(schema_dir: Path) -> Path:
    if schema_dir.exists() or schema_dir.is_absolute():
        return schema_dir
    return Path(__file__).resolve().parents[3] / schema_dir


def _require_sqlite_tables(connection: sqlite3.Connection) -> None:
    table_names = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    required_tables = {
        "facilities",
        "source_documents",
        "complaints",
        "allegations",
        "events",
        "extraction_audit",
    }
    missing_tables = sorted(required_tables - table_names)
    if missing_tables:
        raise ValueError(
            "Validated CCLD SQLite output is missing required table(s): "
            + ", ".join(missing_tables)
        )


def _selected_facility_number(
    connection: sqlite3.Connection,
    requested_facility_number: str | None,
) -> str:
    if requested_facility_number is not None:
        if FACILITY_NUMBER_PATTERN.fullmatch(requested_facility_number) is None:
            raise ValueError("facility_number must contain digits only for CCLD artifacts.")
        return requested_facility_number

    rows = connection.execute(
        """
        SELECT DISTINCT external_facility_number
        FROM facilities
        WHERE source_id = ?
        ORDER BY external_facility_number
        """,
        (CCLD_SOURCE_ID,),
    ).fetchall()
    facility_numbers = [str(row[0]) for row in rows if row[0] is not None]
    if not facility_numbers:
        raise ValueError("Could not infer a CCLD facility/license number from SQLite output.")
    if len(facility_numbers) > 1:
        raise ValueError(
            "SQLite output contains multiple CCLD facility/license numbers; pass "
            "facility_number explicitly."
        )
    return facility_numbers[0]


def _record_bundles(
    connection: sqlite3.Connection,
    *,
    facility_number: str,
    start_date: date | None,
    end_date: date | None,
    schema_dir: Path,
) -> list[dict[str, Any]]:
    complaint_ids = _matching_complaint_ids(
        connection,
        facility_number=facility_number,
        start_date=start_date,
        end_date=end_date,
    )
    records: list[dict[str, Any]] = []
    for complaint_id in complaint_ids:
        complaint = _table_record(connection, "complaints", "complaint_id", complaint_id)
        source_document = _table_record(
            connection,
            "source_documents",
            "document_id",
            _required_non_empty(str(complaint.get("document_id") or ""), "document_id"),
        )
        facility = _table_record(
            connection,
            "facilities",
            "facility_id",
            _required_non_empty(str(complaint.get("facility_id") or ""), "facility_id"),
        )
        _validate_ccld_traceability(facility, source_document)
        allegations = _table_records(
            connection,
            "allegations",
            "complaint_id",
            complaint_id,
            order_by="allegation_id",
        )
        events = _table_records(
            connection,
            "events",
            "complaint_id",
            complaint_id,
            order_by="event_id",
        )
        extraction_audit = _table_records(
            connection,
            "extraction_audit",
            "document_id",
            _required_non_empty(str(source_document.get("document_id") or ""), "document_id"),
            order_by="audit_id",
        )
        bundle = {
            "facility": facility,
            "source_document": source_document,
            "complaint": complaint,
            "allegations": allegations,
            "events": events,
            "extraction_audit": extraction_audit,
        }
        _validate_record_bundle(bundle, schema_dir)
        records.append(bundle)
    return records


def _matching_complaint_ids(
    connection: sqlite3.Connection,
    *,
    facility_number: str,
    start_date: date | None,
    end_date: date | None,
) -> list[str]:
    rows = connection.execute(
        """
        SELECT c.complaint_id, c.complaint_received_date, c.visit_date, c.report_date,
               c.date_signed, sd.document_id
        FROM complaints c
        JOIN facilities f ON f.facility_id = c.facility_id
        JOIN source_documents sd ON sd.document_id = c.document_id
        WHERE f.source_id = ?
          AND f.external_facility_number = ?
          AND sd.connector_name = ?
        ORDER BY
          COALESCE(c.complaint_received_date, c.visit_date, c.report_date, c.date_signed, ''),
          sd.document_id,
          c.complaint_id
        """,
        (CCLD_SOURCE_ID, facility_number, CCLD_CONNECTOR_NAME),
    ).fetchall()
    complaint_ids: list[str] = []
    for row in rows:
        values = {field: row[field] for field in COMPLAINT_DATE_FIELDS}
        if _matches_date_filter(values, start_date=start_date, end_date=end_date):
            complaint_ids.append(str(row["complaint_id"]))
    return complaint_ids


def _matches_date_filter(
    values: Mapping[str, Any],
    *,
    start_date: date | None,
    end_date: date | None,
) -> bool:
    if start_date is None and end_date is None:
        return True
    record_dates = []
    for field_name in COMPLAINT_DATE_FIELDS:
        value = values.get(field_name)
        if isinstance(value, str) and value.strip():
            parsed_date = _parse_optional_date(value[:10], field_name)
            if parsed_date is not None:
                record_dates.append(parsed_date)
    for record_date in record_dates:
        if start_date is not None and record_date < start_date:
            continue
        if end_date is not None and record_date > end_date:
            continue
        return True
    return False


def _table_record(
    connection: sqlite3.Connection,
    table_name: str,
    key_field: str,
    key_value: str,
) -> dict[str, Any]:
    rows = _table_records(connection, table_name, key_field, key_value, order_by=key_field)
    if not rows:
        raise ValueError(f"SQLite output is missing {table_name} row for {key_value}.")
    if len(rows) > 1:
        raise ValueError(f"SQLite output returned duplicate {table_name} rows for {key_value}.")
    return rows[0]


def _table_records(
    connection: sqlite3.Connection,
    table_name: str,
    key_field: str,
    key_value: str,
    *,
    order_by: str,
) -> list[dict[str, Any]]:
    if table_name not in TABLE_COLUMNS:
        raise ValueError(f"Unsupported SQLite table for CCLD artifact builder: {table_name}")
    columns = TABLE_COLUMNS[table_name]
    if key_field not in columns or order_by not in columns:
        raise ValueError(f"Unsupported SQLite field for CCLD artifact builder: {key_field}")
    selected_columns = ", ".join(columns)
    rows = connection.execute(
        f"SELECT {selected_columns} FROM {table_name} WHERE {key_field} = ? ORDER BY {order_by}",
        (key_value,),
    ).fetchall()
    return [_record_from_row(table_name, row) for row in rows]


def _record_from_row(table_name: str, row: sqlite3.Row) -> dict[str, Any]:
    record = {column: row[column] for column in TABLE_COLUMNS[table_name]}
    if table_name == "complaints":
        for field_name in COMPLAINT_BOOLEAN_FIELDS:
            record[field_name] = bool(record[field_name])
    return record


def _validate_ccld_traceability(
    facility: Mapping[str, Any],
    source_document: Mapping[str, Any],
) -> None:
    facility_number = _required_non_empty(
        _string_value(facility.get("external_facility_number")),
        "external_facility_number",
    )
    if FACILITY_NUMBER_PATTERN.fullmatch(facility_number) is None:
        raise ValueError("CCLD facility/license number must contain digits only.")
    if source_document.get("source_id") != CCLD_SOURCE_ID:
        raise ValueError("Artifact builder accepts CCLD source_documents only.")
    if source_document.get("connector_name") != CCLD_CONNECTOR_NAME:
        raise ValueError("Artifact builder accepts ccld_facility_reports rows only.")

    document_id = _required_non_empty(
        _string_value(source_document.get("document_id")),
        "document_id",
    )
    for field_name in (
        "source_url",
        "retrieved_at",
        "raw_sha256",
        "connector_name",
        "connector_version",
    ):
        _required_non_empty(_string_value(source_document.get(field_name)), field_name)

    raw_sha256 = str(source_document["raw_sha256"])
    if RAW_SHA256_PATTERN.fullmatch(raw_sha256) is None:
        raise ValueError(
            f"Source document {document_id} raw_sha256 must be lowercase SHA-256 hex."
        )
    _validate_public_ccld_url(str(source_document["source_url"]), facility_number, document_id)
    raw_path = source_document.get("raw_path")
    if raw_path is not None:
        _validate_safe_relative_raw_path(str(raw_path), document_id)


def _validate_public_ccld_url(source_url: str, facility_number: str, document_id: str) -> None:
    parsed_url = urlparse(source_url)
    if parsed_url.scheme != "https" or parsed_url.netloc.casefold() != CCLD_SOURCE_HOST:
        raise ValueError(f"Source document {document_id} must use the public CCLD source URL.")
    query = parse_qs(parsed_url.query)
    if query.get("facNum", [None])[0] != facility_number:
        raise ValueError(
            f"Source document {document_id} source_url must match the requested CCLD facility."
        )


def _validate_safe_relative_raw_path(raw_path: str, document_id: str) -> None:
    if not raw_path.strip():
        return
    windows_path = PureWindowsPath(raw_path)
    if Path(raw_path).is_absolute() or windows_path.is_absolute() or windows_path.drive:
        raise ValueError(
            f"Source document {document_id} raw_path must be relative before writing a hosted "
            "seeded-corpus artifact."
        )
    if "://" in raw_path:
        raise ValueError(f"Source document {document_id} raw_path must not be a URL.")


def _validate_record_bundle(bundle: Mapping[str, Any], schema_dir: Path) -> None:
    validate_schema(dict(bundle["facility"]), schema_dir / "facility.schema.json")
    validate_schema(dict(bundle["source_document"]), schema_dir / "source_document.schema.json")
    validate_schema(dict(bundle["complaint"]), schema_dir / "complaint.schema.json")
    for allegation in bundle["allegations"]:
        validate_schema(dict(allegation), schema_dir / "allegation.schema.json")
    for event in bundle["events"]:
        validate_schema(dict(event), schema_dir / "event.schema.json")
    for audit_record in bundle["extraction_audit"]:
        validate_schema(dict(audit_record), schema_dir / "extraction_audit.schema.json")


def _record_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    unique_counts: dict[str, set[str]] = {
        entity_type: set() for entity_type in SOURCE_DERIVED_ENTITY_TYPES
    }
    for record in records:
        facility = record["facility"]
        source_document = record["source_document"]
        complaint = record["complaint"]
        unique_counts["facility"].add(str(facility["facility_id"]))
        unique_counts["source_document"].add(str(source_document["document_id"]))
        unique_counts["complaint"].add(str(complaint["complaint_id"]))
        for allegation in record["allegations"]:
            unique_counts["allegation"].add(str(allegation["allegation_id"]))
        for event in record["events"]:
            unique_counts["event"].add(str(event["event_id"]))
        for audit_record in record["extraction_audit"]:
            unique_counts["extraction_audit"].add(str(audit_record["audit_id"]))
    return {entity_type: len(ids) for entity_type, ids in unique_counts.items()}


def _default_source_artifact_identity(db_path: Path) -> str:
    digest = hashlib.sha256(db_path.read_bytes()).hexdigest()
    return f"ccld-sqlite-output:sha256:{digest}"


def _parse_optional_date(value: str | None, field_name: str) -> date | None:
    if value is None:
        return None
    if not value.strip():
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must use YYYY-MM-DD format.") from exc


def _required_non_empty(value: str, field_name: str) -> str:
    if not value.strip():
        raise ValueError(f"Required CCLD traceability field is missing: {field_name}.")
    return value


def _string_value(value: object) -> str:
    if isinstance(value, str):
        return value
    return ""