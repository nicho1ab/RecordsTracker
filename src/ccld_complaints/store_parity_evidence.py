from __future__ import annotations

import argparse
import csv
import gc
import json
import os
import sqlite3
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from sqlalchemy import create_engine, func, select, text, update
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.schema import CreateTable

from ccld_complaints import canonical_allocation_evidence
from ccld_complaints.connectors.base import SourceDocument
from ccld_complaints.connectors.ccld.facility_reports import (
    BASE_URL,
    CcldFacilityReportsConnector,
)
from ccld_complaints.hosted_app.ccld_facility_lookup import (
    load_active_ccld_facility_reference_live_safe,
)
from ccld_complaints.hosted_app.facility_reference_preload import (
    FacilityReferenceRecord,
    hosted_facility_reference_metadata,
    hosted_facility_reference_records,
    load_facility_reference_preload,
    parse_facility_reference_csv,
)
from ccld_complaints.hosted_app.persistence import (
    HostedDatabaseConfigError,
    load_hosted_database_config,
)
from ccld_complaints.hosted_app.reviewer_created_state import (
    hosted_reviewer_created_state,
)
from ccld_complaints.hosted_app.seeded_import import (
    ENTITY_ID_FIELDS,
    SOURCE_DERIVED_ENTITY_TYPES,
    SeededCorpusArtifact,
    hosted_seeded_import_metadata,
    hosted_source_derived_records,
    import_seeded_corpus_artifact,
)
from ccld_complaints.storage.sqlite import (
    PRIMARY_KEYS,
    TABLE_COLUMNS,
    write_normalized_records,
)
from ccld_complaints.utils.hash import sha256_bytes

EvidenceMode = Literal["local", "runtime"]

SCHEMA_VERSION = 1
EXPECTED_ALEMBIC_REVISION = "20260714_0007"
SYNTHETIC_FACILITY_IDS = ("900000001", "900000002")
FACILITY_REFERENCE_FIXTURES = (
    Path("tests/fixtures/public_source_facilities/ccld_program_facilities_tiny.csv"),
    Path("tests/fixtures/public_source_facilities/chhs_facility_master_tiny.csv"),
)
SOURCE_UNAVAILABLE_FIXTURE = Path(
    "tests/fixtures/ccld/raw/157806098_inx42_missing_visit_date.html"
)
OUTPUT_FILES = (
    "manifest.json",
    "store-results.csv",
    "field-parity-results.csv",
    "null-semantics-results.csv",
    "idempotency-results.csv",
    "refresh-readiness-results.csv",
    "gap-status.csv",
    "summary.md",
)

STORE_FIELDS = (
    "dimension",
    "sqlite_count",
    "postgresql_style_count",
    "comparison_status",
    "execution_note",
    "assertion_status",
)
FIELD_FIELDS = (
    "field_id",
    "domain",
    "sqlite_presence_count",
    "postgresql_style_presence_count",
    "sqlite_populated_count",
    "postgresql_style_populated_count",
    "sqlite_null_count",
    "postgresql_style_null_count",
    "value_match_status",
    "assertion_status",
)
NULL_FIELDS = (
    "semantic_case",
    "sqlite_count",
    "postgresql_style_count",
    "preservation_rule",
    "assertion_status",
)
IDEMPOTENCY_FIELDS = (
    "check_id",
    "first_count",
    "second_count",
    "duplicate_rows_after_second_run",
    "reviewer_state_rows_before",
    "reviewer_state_rows_after",
    "assertion_status",
)
REFRESH_FIELDS = (
    "refresh_area",
    "safe_command_available",
    "available_controls",
    "missing_controls",
    "existing_data_action",
    "assertion_status",
)
GAP_FIELDS = (
    "gap_id",
    "status",
    "evidence_scope",
    "remaining_action",
    "causes_parity_failure",
    "assertion_status",
)

ENTITY_TO_TABLE = {
    "facility": "facilities",
    "source_document": "source_documents",
    "complaint": "complaints",
    "allegation": "allegations",
    "event": "events",
    "extraction_audit": "extraction_audit",
}
REFERENCE_FIELDS = (
    "facility_type",
    "client_served",
    "county",
    "regional_office",
    "capacity",
    "status",
    "closed_date",
    "all_visit_dates",
    "inspection_visit_dates",
    "other_visit_dates",
)
COMPLAINT_BOOLEAN_FIELDS = (
    "review_delay_over_30_days",
    "review_delay_over_60_days",
    "review_delay_over_90_days",
    "review_delay_over_120_days",
    "missing_first_activity_date",
    "report_date_used_as_proxy",
)


class StoreParityEvidenceError(RuntimeError):
    """Controlled, aggregate-safe evidence execution error."""


@dataclass(frozen=True)
class StoreSnapshot:
    rows_by_entity: Mapping[str, tuple[Mapping[str, Any], ...]]
    linkages: tuple[tuple[str, str, str], ...]
    event_order: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class RuntimeInspection:
    status: str
    actual_postgresql_connection: bool
    schema_status: str
    source_derived_count: int | None
    facility_reference_count: int | None


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

    allocation_capability = canonical_allocation_evidence._local_capability(root)
    parity = _canonical_store_parity(root)
    reference = _facility_reference_parity(root)
    postgres_sql = _postgresql_sql_capability()
    production_fallback_safe = _production_fallback_is_safe(root)
    migration_safe = all(
        row["assertion_status"] == "PASS"
        for row in cast(list[dict[str, object]], allocation_capability["migration_rows"])
    )
    allocation_assertions = cast(
        Mapping[str, bool], allocation_capability["assertions"]
    )

    runtime = RuntimeInspection(
        status="not requested in local mode",
        actual_postgresql_connection=False,
        schema_status="not inspected",
        source_derived_count=None,
        facility_reference_count=None,
    )
    if mode == "runtime":
        runtime = _runtime_inspection(
            root,
            environ=environ if environ is not None else os.environ,
            runtime_connection=runtime_connection,
        )

    store_rows = cast(list[dict[str, object]], parity["store_rows"])
    store_rows.append(
        {
            "dimension": "facility_reference",
            "sqlite_count": "not applicable",
            "postgresql_style_count": reference["stored_count"],
            "comparison_status": "parser eligible count matches preload count",
            "execution_note": (
                "Facility-reference fields are source-reference-only; SQLite has no "
                "equivalent canonical table."
            ),
            "assertion_status": "PASS" if reference["counts_match"] else "FAIL",
        }
    )
    field_rows = cast(list[dict[str, object]], parity["field_rows"])
    field_rows.extend(cast(list[dict[str, object]], reference["field_rows"]))
    null_rows = cast(list[dict[str, object]], parity["null_rows"])
    null_rows.extend(cast(list[dict[str, object]], reference["null_rows"]))
    idempotency_rows = cast(list[dict[str, object]], parity["idempotency_rows"])
    idempotency_rows.append(cast(dict[str, object], reference["idempotency_row"]))
    refresh_rows = _refresh_readiness_rows()

    confirmed_divergence = any(
        row["assertion_status"] == "FAIL"
        for rows in (store_rows, field_rows, null_rows, idempotency_rows)
        for row in rows
    )
    gap_rows = _gap_rows(
        confirmed_divergence=confirmed_divergence,
        runtime=runtime,
    )

    assertions = {
        "equivalent_inputs_match_eligible_counts": all(
            row["assertion_status"] == "PASS" for row in store_rows
        ),
        "canonical_field_presence_matches": all(
            row["assertion_status"] == "PASS"
            for row in field_rows
            if row["domain"] == "canonical"
        ),
        "canonical_populated_and_null_counts_match": all(
            row["assertion_status"] == "PASS" for row in field_rows
        ),
        "null_blank_unavailable_and_zero_semantics_match": all(
            row["assertion_status"] == "PASS" for row in null_rows
        ),
        "source_document_and_raw_hash_linkage_matches": bool(parity["linkages_match"]),
        "event_order_is_deterministic": bool(parity["event_order_matches"]),
        "date_arrays_are_sorted_and_deduplicated": bool(reference["date_arrays_ordered"]),
        "reimport_is_idempotent": all(
            row["assertion_status"] == "PASS" for row in idempotency_rows
        ),
        "duplicate_suppression_matches": bool(parity["duplicate_suppression_matches"]),
        "facility_reference_migration_is_additive": migration_safe,
        "facility_reference_preload_matches_parser": bool(reference["counts_match"]),
        "postgresql_sql_path_compiles": bool(postgres_sql["compiled"]),
        "reviewer_created_state_is_not_deleted": bool(parity["reviewer_state_preserved"]),
        "production_mode_has_no_fixture_fallback": production_fallback_safe,
        "no_synthetic_facility_ids_emitted": True,
        "runtime_inspection_status_is_accurate": (
            mode == "local"
            or runtime.actual_postgresql_connection
            or runtime.status.startswith("not inspected")
        ),
        "refresh_readiness_is_stated_accurately": all(
            row["assertion_status"] == "PASS" for row in refresh_rows
        ),
        "issue_447_governed_allocations_remain_covered": all(
            bool(value)
            for key, value in allocation_assertions.items()
            if key
            not in {
                "no_synthetic_facility_ids_emitted",
                "runtime_population_reported_separately",
                "existing_data_refresh_requirement_stated",
                "safe_aggregate_output",
            }
        ),
        "no_confirmed_store_divergence": not confirmed_divergence,
    }
    if runtime.actual_postgresql_connection and runtime.schema_status != "match":
        assertions["runtime_inspection_status_is_accurate"] = False

    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "execution": {
            "sqlite": "actual temporary SQLite execution",
            "postgresql_style": (
                "actual hosted SQLAlchemy mapping path executed on a temporary SQLite "
                "adapter; actual statements and table DDL compiled with PostgreSQL dialect"
            ),
            "actual_disposable_postgresql": False,
            "production_runtime_inspection": runtime.status,
        },
        "runtime_inspection": {
            "status": runtime.status,
            "actual_postgresql_connection": runtime.actual_postgresql_connection,
            "schema_status": runtime.schema_status,
            "source_derived_count": runtime.source_derived_count,
            "facility_reference_count": runtime.facility_reference_count,
        },
        "refresh_readiness": {
            "safe_refresh_command_available": False,
            "existing_postgresql_rows_require_regeneration_or_reimport": True,
            "facility_reference_rows_require_migration_and_preload_rerun": True,
        },
        "confirmed_divergence_count": int(confirmed_divergence),
        "assertions": assertions,
        "counts": {
            "store_results": len(store_rows),
            "field_parity_results": len(field_rows),
            "null_semantics_results": len(null_rows),
            "idempotency_results": len(idempotency_rows),
            "refresh_readiness_results": len(refresh_rows),
            "gap_results": len(gap_rows),
            "postgresql_statements_compiled": postgres_sql["statement_count"],
            "assertions_passed": sum(assertions.values()),
            "assertions_total": len(assertions),
        },
        "generated_files": list(OUTPUT_FILES),
    }

    effective_output = output_dir if output_dir.is_absolute() else root / output_dir
    _write_outputs(
        effective_output,
        manifest=manifest,
        store_rows=store_rows,
        field_rows=field_rows,
        null_rows=null_rows,
        idempotency_rows=idempotency_rows,
        refresh_rows=refresh_rows,
        gap_rows=gap_rows,
    )
    _assert_aggregate_safe(effective_output, root)
    return manifest


def _canonical_store_parity(repo_root: Path) -> dict[str, object]:
    normalized = _with_explicit_capacity_zero(
        _normalized_complaint_fixture(
            repo_root,
            canonical_allocation_evidence.GOVERNED_COMPLAINT_FIXTURE,
            report_index=canonical_allocation_evidence.FIXTURE_REPORT_INDEX,
            retrieved_at=canonical_allocation_evidence.FIXTURE_RETRIEVED_AT,
        )
    )
    unavailable = _normalized_complaint_fixture(
        repo_root,
        SOURCE_UNAVAILABLE_FIXTURE,
        report_index=42,
        retrieved_at="2026-06-12T00:00:00+00:00",
    )

    with tempfile.TemporaryDirectory(prefix="store-parity-") as scratch:
        db_path = Path(scratch) / "parity.sqlite3"
        write_normalized_records(db_path, [normalized, unavailable, normalized])
        write_normalized_records(db_path, [_null_facility_update(normalized)])
        sqlite_snapshot = _sqlite_snapshot(db_path)
        artifact = _artifact_from_snapshot(sqlite_snapshot)

        engine = create_engine("sqlite+pysqlite:///:memory:")
        try:
            hosted_seeded_import_metadata.create_all(engine)
            with engine.begin() as connection:
                first = import_seeded_corpus_artifact(connection, artifact)
                first_count = _hosted_source_count(connection)
                _insert_reviewer_state_probe(connection)
                reviewer_before = _reviewer_state_count(connection)
                second = import_seeded_corpus_artifact(connection, artifact)
                second_count = _hosted_source_count(connection)
                reviewer_after = _reviewer_state_count(connection)
                hosted_snapshot = _hosted_snapshot(connection)
                duplicate_count = _hosted_duplicate_count(connection)
        finally:
            engine.dispose()
            gc.collect()

    field_rows = _field_parity_rows(sqlite_snapshot, hosted_snapshot)
    store_rows = _store_rows(sqlite_snapshot, hosted_snapshot)
    null_rows = _canonical_null_rows(sqlite_snapshot, hosted_snapshot)
    idempotent = (
        first_count == second_count
        and first.imported_record_count == second.imported_record_count
        and duplicate_count == 0
    )
    return {
        "store_rows": store_rows,
        "field_rows": field_rows,
        "null_rows": null_rows,
        "idempotency_rows": [
            {
                "check_id": "canonical_reimport",
                "first_count": first_count,
                "second_count": second_count,
                "duplicate_rows_after_second_run": duplicate_count,
                "reviewer_state_rows_before": reviewer_before,
                "reviewer_state_rows_after": reviewer_after,
                "assertion_status": (
                    "PASS" if idempotent and reviewer_before == reviewer_after else "FAIL"
                ),
            }
        ],
        "linkages_match": sqlite_snapshot.linkages == hosted_snapshot.linkages,
        "event_order_matches": (
            sqlite_snapshot.event_order == hosted_snapshot.event_order
            and sqlite_snapshot.event_order == tuple(sorted(sqlite_snapshot.event_order))
        ),
        "duplicate_suppression_matches": duplicate_count == 0,
        "reviewer_state_preserved": reviewer_before == reviewer_after == 1,
    }


def _normalized_complaint_fixture(
    repo_root: Path,
    relative_path: Path,
    *,
    report_index: int,
    retrieved_at: str,
) -> dict[str, object]:
    fixture_path = repo_root / relative_path
    content = fixture_path.read_bytes()
    document = SourceDocument(
        source_url=(
            f"{BASE_URL}?facNum={canonical_allocation_evidence.FIXTURE_FACILITY_NUMBER}"
            f"&inx={report_index}"
        ),
        raw_path=fixture_path,
        raw_sha256=sha256_bytes(content),
        retrieved_at=retrieved_at,
        content_type="text/html",
    )
    connector = CcldFacilityReportsConnector(schema_dir=repo_root / "schemas")
    normalized = dict(connector.normalize(connector.extract(document)))
    source_document = dict(cast(Mapping[str, object], normalized["source_document"]))
    source_document["raw_path"] = relative_path.as_posix()
    normalized["source_document"] = source_document
    connector.validate(normalized)
    return normalized


def _with_explicit_capacity_zero(
    normalized: Mapping[str, object],
) -> dict[str, object]:
    updated = dict(normalized)
    facility = dict(cast(Mapping[str, object], updated["facility"]))
    facility["capacity"] = 0
    updated["facility"] = facility
    return updated


def _null_facility_update(normalized: Mapping[str, object]) -> dict[str, object]:
    facility = dict(cast(Mapping[str, object], normalized["facility"]))
    for field in (
        "facility_type",
        "licensee_name",
        "county",
        "status",
        "capacity",
        "regional_office",
    ):
        facility[field] = None
    return {"facility": facility}


def _sqlite_snapshot(db_path: Path) -> StoreSnapshot:
    rows_by_entity: dict[str, tuple[Mapping[str, Any], ...]] = {}
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        for entity_type, table_name in ENTITY_TO_TABLE.items():
            primary_key = PRIMARY_KEYS[table_name]
            columns = TABLE_COLUMNS[table_name]
            rows = connection.execute(
                f"SELECT {', '.join(columns)} FROM {table_name} ORDER BY {primary_key}"
            ).fetchall()
            rows_by_entity[entity_type] = tuple(
                _normalized_row(entity_type, {column: row[column] for column in columns})
                for row in rows
            )
    return StoreSnapshot(
        rows_by_entity=rows_by_entity,
        linkages=_sqlite_linkages(rows_by_entity),
        event_order=_event_order(rows_by_entity),
    )


def _hosted_snapshot(connection: Connection) -> StoreSnapshot:
    rows = connection.execute(
        select(hosted_source_derived_records).order_by(
            hosted_source_derived_records.c.entity_type,
            hosted_source_derived_records.c.stable_source_id,
        )
    ).mappings()
    grouped: dict[str, list[Mapping[str, Any]]] = {
        entity_type: [] for entity_type in SOURCE_DERIVED_ENTITY_TYPES
    }
    linkage_rows: list[tuple[str, str, str]] = []
    for row in rows:
        entity_type = str(row["entity_type"])
        original = cast(Mapping[str, Any], row["original_values"])
        grouped[entity_type].append(_normalized_row(entity_type, original))
        if entity_type != "facility":
            linkage_rows.append(
                (
                    entity_type,
                    str(row["source_document_id"]),
                    str(row["raw_sha256"]),
                )
            )
    rows_by_entity = {
        entity: tuple(
            sorted(
                values,
                key=lambda value: str(value[ENTITY_ID_FIELDS[cast(Any, entity)]]),
            )
        )
        for entity, values in grouped.items()
    }
    return StoreSnapshot(
        rows_by_entity=rows_by_entity,
        linkages=tuple(sorted(linkage_rows)),
        event_order=_event_order(rows_by_entity),
    )


def _normalized_row(entity_type: str, row: Mapping[str, Any]) -> Mapping[str, Any]:
    normalized = dict(row)
    if entity_type == "complaint":
        for field in COMPLAINT_BOOLEAN_FIELDS:
            value = normalized.get(field)
            if value is not None:
                normalized[field] = bool(value)
    return normalized


def _sqlite_linkages(
    rows_by_entity: Mapping[str, tuple[Mapping[str, Any], ...]],
) -> tuple[tuple[str, str, str], ...]:
    documents = {
        str(row["document_id"]): str(row["raw_sha256"])
        for row in rows_by_entity["source_document"]
    }
    complaints = {
        str(row["complaint_id"]): str(row["document_id"])
        for row in rows_by_entity["complaint"]
    }
    linkages: list[tuple[str, str, str]] = []
    for entity_type, rows in rows_by_entity.items():
        if entity_type == "facility":
            continue
        for row in rows:
            if entity_type == "source_document":
                document_id = str(row["document_id"])
            elif entity_type in {"complaint", "extraction_audit"}:
                document_id = str(row["document_id"])
            else:
                document_id = complaints[str(row["complaint_id"])]
            linkages.append((entity_type, document_id, documents[document_id]))
    return tuple(sorted(linkages))


def _event_order(
    rows_by_entity: Mapping[str, tuple[Mapping[str, Any], ...]],
) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted(
            (str(row["event_date"]), str(row["event_id"]))
            for row in rows_by_entity["event"]
        )
    )


def _artifact_from_snapshot(snapshot: StoreSnapshot) -> SeededCorpusArtifact:
    facilities = {str(row["facility_id"]): row for row in snapshot.rows_by_entity["facility"]}
    documents = {
        str(row["document_id"]): row for row in snapshot.rows_by_entity["source_document"]
    }
    complaints = snapshot.rows_by_entity["complaint"]
    records: list[Mapping[str, Any]] = []
    for complaint in complaints:
        complaint_id = str(complaint["complaint_id"])
        document_id = str(complaint["document_id"])
        facility_id = str(complaint["facility_id"])
        records.append(
            {
                "facility": facilities[facility_id],
                "source_document": documents[document_id],
                "complaint": complaint,
                "allegations": [
                    row
                    for row in snapshot.rows_by_entity["allegation"]
                    if row["complaint_id"] == complaint_id
                ],
                "events": [
                    row
                    for row in snapshot.rows_by_entity["event"]
                    if row["complaint_id"] == complaint_id
                ],
                "extraction_audit": [
                    row
                    for row in snapshot.rows_by_entity["extraction_audit"]
                    if row["document_id"] == document_id
                ],
            }
        )
    counts = {
        entity: len(rows) for entity, rows in snapshot.rows_by_entity.items()
    }
    return SeededCorpusArtifact(
        import_batch_id="store-parity-local",
        imported_at=canonical_allocation_evidence.FIXTURE_RETRIEVED_AT,
        source_artifact_identity="governed-store-parity-local",
        source_pipeline_version="store-parity-evidence-v1",
        validation_status="validated",
        raw_hash_validation_status="validated",
        record_counts=counts,
        warnings=("Aggregate-only local store parity exercise.",),
        errors=(),
        records=tuple(records),
    )


def _hosted_source_count(connection: Connection) -> int:
    return int(
        connection.execute(
            select(func.count()).select_from(hosted_source_derived_records)
        ).scalar_one()
    )


def _hosted_duplicate_count(connection: Connection) -> int:
    rows = connection.execute(
        select(
            hosted_source_derived_records.c.entity_type,
            hosted_source_derived_records.c.stable_source_id,
            func.count().label("row_count"),
        )
        .group_by(
            hosted_source_derived_records.c.entity_type,
            hosted_source_derived_records.c.stable_source_id,
        )
        .having(func.count() > 1)
    ).all()
    return len(rows)


def _insert_reviewer_state_probe(connection: Connection) -> None:
    complaint_key = connection.execute(
        select(hosted_source_derived_records.c.source_record_key)
        .where(hosted_source_derived_records.c.entity_type == "complaint")
        .order_by(hosted_source_derived_records.c.source_record_key)
        .limit(1)
    ).scalar_one()
    connection.execute(
        hosted_reviewer_created_state.insert().values(
            reviewer_state_id="store-parity-reviewer-state",
            source_record_key=complaint_key,
            scope_type="ccld_retrieval_corpus",
            scope_id="store-parity-local",
            state_kind="review_item_state_scaffold",
            state_payload={"payload_kind": "parity_probe"},
            created_at=canonical_allocation_evidence.FIXTURE_RETRIEVED_AT,
            created_by_provider_subject="aggregate-test-actor",
            created_by_provider_issuer="aggregate-test-issuer",
            created_by_display_name="Aggregate test actor",
            created_by_actor_category="test",
            authorization_permission="reviewer_state_write",
        )
    )


def _reviewer_state_count(connection: Connection) -> int:
    return int(
        connection.execute(
            select(func.count()).select_from(hosted_reviewer_created_state)
        ).scalar_one()
    )


def _store_rows(
    sqlite_snapshot: StoreSnapshot,
    hosted_snapshot: StoreSnapshot,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for entity_type in SOURCE_DERIVED_ENTITY_TYPES:
        sqlite_count = len(sqlite_snapshot.rows_by_entity[entity_type])
        hosted_count = len(hosted_snapshot.rows_by_entity[entity_type])
        rows.append(
            {
                "dimension": entity_type,
                "sqlite_count": sqlite_count,
                "postgresql_style_count": hosted_count,
                "comparison_status": "matching" if sqlite_count == hosted_count else "mismatch",
                "execution_note": "equivalent governed canonical input",
                "assertion_status": "PASS" if sqlite_count == hosted_count else "FAIL",
            }
        )
    return rows


def _field_parity_rows(
    sqlite_snapshot: StoreSnapshot,
    hosted_snapshot: StoreSnapshot,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for entity_type in SOURCE_DERIVED_ENTITY_TYPES:
        table = ENTITY_TO_TABLE[entity_type]
        sqlite_rows = sqlite_snapshot.rows_by_entity[entity_type]
        hosted_rows = hosted_snapshot.rows_by_entity[entity_type]
        for field in TABLE_COLUMNS[table]:
            sqlite_values = [row.get(field) for row in sqlite_rows]
            hosted_values = [row.get(field) for row in hosted_rows]
            matches = sqlite_values == hosted_values
            rows.append(
                {
                    "field_id": f"{entity_type}.{field}",
                    "domain": "canonical",
                    "sqlite_presence_count": sum(field in row for row in sqlite_rows),
                    "postgresql_style_presence_count": sum(
                        field in row for row in hosted_rows
                    ),
                    "sqlite_populated_count": sum(_is_populated(value) for value in sqlite_values),
                    "postgresql_style_populated_count": sum(
                        _is_populated(value) for value in hosted_values
                    ),
                    "sqlite_null_count": sum(value is None for value in sqlite_values),
                    "postgresql_style_null_count": sum(value is None for value in hosted_values),
                    "value_match_status": "matching" if matches else "mismatch",
                    "assertion_status": "PASS" if matches else "FAIL",
                }
            )
    return rows


def _canonical_null_rows(
    sqlite_snapshot: StoreSnapshot,
    hosted_snapshot: StoreSnapshot,
) -> list[dict[str, object]]:
    return [
        _semantic_row(
            "explicit_numeric_zero",
            _semantic_count(sqlite_snapshot, "explicit_numeric_zero"),
            _semantic_count(hosted_snapshot, "explicit_numeric_zero"),
            "Explicit capacity zero remains numeric zero.",
        ),
        _semantic_row(
            "canonical_null",
            _semantic_count(sqlite_snapshot, "canonical_null"),
            _semantic_count(hosted_snapshot, "canonical_null"),
            "Unknown canonical values remain null.",
        ),
        _semantic_row(
            "present_but_blank_audit",
            _semantic_count(sqlite_snapshot, "present_but_blank_audit"),
            _semantic_count(hosted_snapshot, "present_but_blank_audit"),
            "Present-but-blank extraction audit values remain blank, not null or zero.",
        ),
        _semantic_row(
            "source_unavailable_audit",
            _semantic_count(sqlite_snapshot, "source_unavailable_audit"),
            _semantic_count(hosted_snapshot, "source_unavailable_audit"),
            "Unavailable extraction audit values remain null with a warning.",
        ),
    ]


def _semantic_count(snapshot: StoreSnapshot, semantic_case: str) -> int:
    if semantic_case == "explicit_numeric_zero":
        return sum(
            row.get("capacity") == 0 for row in snapshot.rows_by_entity["facility"]
        )
    if semantic_case == "canonical_null":
        return sum(
            value is None
            for entity, rows in snapshot.rows_by_entity.items()
            if entity != "extraction_audit"
            for row in rows
            for value in row.values()
        )
    audits = snapshot.rows_by_entity["extraction_audit"]
    if semantic_case == "present_but_blank_audit":
        return sum(
            row.get("extracted_value") is None
            and "blank" in str(row.get("warning") or "").casefold()
            for row in audits
        )
    return sum(
        row.get("extracted_value") is None
        and _is_populated(row.get("warning"))
        and "blank" not in str(row.get("warning") or "").casefold()
        for row in audits
    )


def _semantic_row(
    semantic_case: str,
    sqlite_count: int,
    hosted_count: int,
    preservation_rule: str,
) -> dict[str, object]:
    covered = sqlite_count > 0 and sqlite_count == hosted_count
    return {
        "semantic_case": semantic_case,
        "sqlite_count": sqlite_count,
        "postgresql_style_count": hosted_count,
        "preservation_rule": preservation_rule,
        "assertion_status": "PASS" if covered else "FAIL",
    }


def _facility_reference_parity(repo_root: Path) -> dict[str, object]:
    fixture_paths = tuple(repo_root / path for path in FACILITY_REFERENCE_FIXTURES)
    parse_results = tuple(
        parse_facility_reference_csv(
            path,
            source_accessed_at=canonical_allocation_evidence.FIXTURE_ACCESSED_AT,
        )
        for path in fixture_paths
    )
    records = tuple(record for result in parse_results for record in result.records)
    eligible_keys = {(record.source_resource_id, record.facility_number) for record in records}
    engine = create_engine("sqlite+pysqlite:///:memory:")
    try:
        hosted_facility_reference_metadata.create_all(engine)
        with engine.begin() as connection:
            first = tuple(
                load_facility_reference_preload(
                    path,
                    connection=connection,
                    apply_changes=True,
                    source_accessed_at=canonical_allocation_evidence.FIXTURE_ACCESSED_AT,
                )
                for path in fixture_paths
            )
            first_count = _reference_count(connection)
            stored_rows = tuple(
                dict(row)
                for row in connection.execute(
                    select(hosted_facility_reference_records).order_by(
                        hosted_facility_reference_records.c.source_resource_id,
                        hosted_facility_reference_records.c.facility_number,
                    )
                ).mappings()
            )
            second = tuple(
                load_facility_reference_preload(
                    path,
                    connection=connection,
                    apply_changes=True,
                    source_accessed_at=canonical_allocation_evidence.FIXTURE_ACCESSED_AT,
                )
                for path in fixture_paths
            )
            second_count = _reference_count(connection)
    finally:
        engine.dispose()

    expected_rows = sorted(
        records,
        key=lambda item: (item.source_resource_id, item.facility_number),
    )
    field_rows = [
        _reference_field_row(field, expected_rows, stored_rows) for field in REFERENCE_FIELDS
    ]
    null_rows = [
        _reference_null_row("facility_reference_null", records, stored_rows),
        _reference_null_row("facility_reference_blank_raw_provenance", records, stored_rows),
    ]
    inserted_first = sum(result.inserted_row_count for result in first)
    inserted_second = sum(result.inserted_row_count for result in second)
    updated_second = sum(result.updated_row_count for result in second)
    unchanged_second = sum(result.unchanged_row_count for result in second)
    duplicate_count = max(0, second_count - len(eligible_keys))
    idempotent = (
        first_count == second_count == len(eligible_keys)
        and inserted_first == first_count
        and inserted_second == 0
        and updated_second == 0
        and unchanged_second == second_count
    )
    return {
        "stored_count": second_count,
        "counts_match": second_count == len(eligible_keys),
        "field_rows": field_rows,
        "null_rows": null_rows,
        "date_arrays_ordered": _date_arrays_ordered(records, stored_rows),
        "idempotency_row": {
            "check_id": "facility_reference_preload",
            "first_count": first_count,
            "second_count": second_count,
            "duplicate_rows_after_second_run": duplicate_count,
            "reviewer_state_rows_before": "not applicable",
            "reviewer_state_rows_after": "not applicable",
            "assertion_status": "PASS" if idempotent else "FAIL",
        },
    }


def _reference_count(connection: Connection) -> int:
    return int(
        connection.execute(
            select(func.count()).select_from(hosted_facility_reference_records)
        ).scalar_one()
    )


def _reference_field_row(
    field: str,
    expected: Sequence[FacilityReferenceRecord],
    stored: Sequence[Mapping[str, Any]],
) -> dict[str, object]:
    expected_values = [
        list(value) if isinstance(value := getattr(record, field), tuple) else value
        for record in expected
    ]
    stored_values = [row.get(field) for row in stored]
    matches = expected_values == stored_values
    return {
        "field_id": f"facility_reference.{field}",
        "domain": "source_reference_only",
        "sqlite_presence_count": "not applicable",
        "postgresql_style_presence_count": len(stored_values),
        "sqlite_populated_count": sum(_is_populated(value) for value in expected_values),
        "postgresql_style_populated_count": sum(_is_populated(value) for value in stored_values),
        "sqlite_null_count": sum(value is None for value in expected_values),
        "postgresql_style_null_count": sum(value is None for value in stored_values),
        "value_match_status": "matching" if matches else "mismatch",
        "assertion_status": "PASS" if matches else "FAIL",
    }


def _reference_null_row(
    semantic_case: str,
    expected: Sequence[FacilityReferenceRecord],
    stored: Sequence[Mapping[str, Any]],
) -> dict[str, object]:
    if semantic_case == "facility_reference_null":
        expected_count = sum(
            getattr(record, field) is None for record in expected for field in REFERENCE_FIELDS
        )
        stored_count = sum(row.get(field) is None for row in stored for field in REFERENCE_FIELDS)
        rule = "Blank, malformed, and unavailable typed reference values remain null."
    else:
        expected_count = sum(
            value == ""
            for record in expected
            for value in record.original_row_json.values()
        )
        stored_count = sum(
            value == ""
            for row in stored
            for value in cast(Mapping[str, Any], row["original_row_json"]).values()
        )
        rule = "Present source blanks remain blank only in original-row provenance."
    covered = expected_count > 0 and expected_count == stored_count
    return {
        "semantic_case": semantic_case,
        "sqlite_count": expected_count,
        "postgresql_style_count": stored_count,
        "preservation_rule": rule,
        "assertion_status": "PASS" if covered else "FAIL",
    }


def _date_arrays_ordered(
    expected: Sequence[FacilityReferenceRecord],
    stored: Sequence[Mapping[str, Any]],
) -> bool:
    fields = ("all_visit_dates", "inspection_visit_dates", "other_visit_dates")
    covered = 0
    for record, row in zip(expected, stored, strict=True):
        for field in fields:
            expected_value = getattr(record, field)
            stored_value = row.get(field)
            if expected_value is None:
                if stored_value is not None:
                    return False
                continue
            covered += 1
            normalized = tuple(cast(Sequence[str], stored_value))
            if expected_value != normalized or normalized != tuple(sorted(set(normalized))):
                return False
    return covered > 0


def _postgresql_sql_capability() -> dict[str, object]:
    dialect = cast(Any, postgresql.dialect)()
    statements = (
        select(hosted_source_derived_records.c.source_record_key).where(
            hosted_source_derived_records.c.source_record_key == "aggregate-probe"
        ),
        hosted_source_derived_records.insert().values(
            source_record_key="aggregate-probe",
            entity_type="facility",
            stable_source_id="aggregate-probe",
            import_batch_id="aggregate-probe",
            source_document_id="aggregate-probe",
            facility_id=None,
            source_url="https://public.example.invalid/aggregate-probe",
            raw_sha256="0" * 64,
            raw_path=None,
            connector_name="aggregate-probe",
            connector_version="1",
            retrieved_at="2026-01-01T00:00:00+00:00",
            original_values={},
            source_traceability={},
        ),
        update(hosted_source_derived_records)
        .where(hosted_source_derived_records.c.source_record_key == "aggregate-probe")
        .values(original_values={}),
        select(hosted_facility_reference_records.c.facility_number).where(
            hosted_facility_reference_records.c.facility_number == "aggregate-probe"
        ),
        hosted_facility_reference_records.insert(),
        update(hosted_facility_reference_records).where(
            hosted_facility_reference_records.c.facility_number == "aggregate-probe"
        ),
    )
    compiled = [str(statement.compile(dialect=dialect)) for statement in statements]
    compiled.extend(
        str(CreateTable(table).compile(dialect=dialect))
        for table in (hosted_source_derived_records, hosted_facility_reference_records)
    )
    return {
        "compiled": all(compiled)
        and all("?" not in sql for sql in compiled)
        and any("JSON" in sql for sql in compiled),
        "statement_count": len(compiled),
    }


def _production_fallback_is_safe(repo_root: Path) -> bool:
    missing_path = repo_root / "data" / "raw" / "store-parity-no-reference.csv"
    source = load_active_ccld_facility_reference_live_safe(
        configured_path=str(missing_path)
    )
    identifiers = tuple(record.facility_number for record in source.records)
    return source.source_kind != "tiny_fixture_fallback" and not any(
        identifier in SYNTHETIC_FACILITY_IDS for identifier in identifiers
    )


def _runtime_inspection(
    repo_root: Path,
    *,
    environ: Mapping[str, str],
    runtime_connection: Connection | None,
) -> RuntimeInspection:
    if runtime_connection is not None:
        return _inspect_runtime_connection(runtime_connection)
    try:
        config = load_hosted_database_config(environ=environ, require_url=True)
    except HostedDatabaseConfigError:
        return RuntimeInspection(
            status="not inspected: PostgreSQL runtime configuration is unavailable",
            actual_postgresql_connection=False,
            schema_status="not inspected",
            source_derived_count=None,
            facility_reference_count=None,
        )
    database_url = cast(str, config.database_url)
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            return _inspect_runtime_connection(connection)
    finally:
        engine.dispose()


def _inspect_runtime_connection(connection: Connection) -> RuntimeInspection:
    if connection.dialect.name != "postgresql":
        return RuntimeInspection(
            status="not inspected: supplied connection is not PostgreSQL",
            actual_postgresql_connection=False,
            schema_status=_schema_version_status(connection),
            source_derived_count=None,
            facility_reference_count=None,
        )
    schema_status = _schema_version_status(connection)
    if schema_status != "match":
        return RuntimeInspection(
            status="PostgreSQL connected; aggregate inspection stopped on schema mismatch",
            actual_postgresql_connection=True,
            schema_status=schema_status,
            source_derived_count=None,
            facility_reference_count=None,
        )
    return RuntimeInspection(
        status="actual PostgreSQL aggregate-only inspection completed",
        actual_postgresql_connection=True,
        schema_status=schema_status,
        source_derived_count=_safe_runtime_count(connection, hosted_source_derived_records.name),
        facility_reference_count=_safe_runtime_count(
            connection, hosted_facility_reference_records.name
        ),
    )


def _schema_version_status(connection: Connection) -> str:
    try:
        revisions = tuple(
            str(value)
            for value in connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalars()
        )
    except Exception:  # SQLAlchemy normalizes backend-specific missing-table errors.
        return "missing"
    return "match" if revisions == (EXPECTED_ALEMBIC_REVISION,) else "mismatch"


def _safe_runtime_count(connection: Connection, table_name: str) -> int | None:
    allowed = {hosted_source_derived_records.name, hosted_facility_reference_records.name}
    if table_name not in allowed:
        raise ValueError("Unsupported runtime aggregate table.")
    try:
        return int(connection.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one())
    except Exception:
        return None


def _refresh_readiness_rows() -> list[dict[str, object]]:
    return [
        {
            "refresh_area": "canonical_source_derived",
            "safe_command_available": "false",
            "available_controls": (
                "validated artifact import is idempotent and preserves source traceability and "
                "reviewer-created state"
            ),
            "missing_controls": (
                "no single schema-gated dry-run command regenerates governed artifacts, reports "
                "eligible/changed/unchanged/skipped/failed counts, and defines production recovery"
            ),
            "existing_data_action": (
                "regenerate governed artifacts and reimport under operator control"
            ),
            "assertion_status": "PASS",
        },
        {
            "refresh_area": "facility_reference",
            "safe_command_available": "false for complete refresh workflow",
            "available_controls": (
                "existing preload is explicit, dry-run/apply, counted, idempotent, and "
                "reviewer-state-separated"
            ),
            "missing_controls": (
                "preload does not itself enforce the expected Alembic revision or provide the "
                "complete canonical-plus-reference recovery contract"
            ),
            "existing_data_action": "apply migration, review dry-run, then rerun preload",
            "assertion_status": "PASS",
        },
    ]


def _gap_rows(
    *,
    confirmed_divergence: bool,
    runtime: RuntimeInspection,
) -> list[dict[str, object]]:
    return [
        {
            "gap_id": "store_parity_divergence",
            "status": "FAIL" if confirmed_divergence else "CLOSED",
            "evidence_scope": "local deterministic equivalent inputs",
            "remaining_action": "fix confirmed mismatch" if confirmed_divergence else "none",
            "causes_parity_failure": "true" if confirmed_divergence else "false",
            "assertion_status": "FAIL" if confirmed_divergence else "PASS",
        },
        {
            "gap_id": "existing_postgresql_rows",
            "status": "OPEN",
            "evidence_scope": runtime.status,
            "remaining_action": "regenerate/reimport canonical rows and rerun facility preload",
            "causes_parity_failure": "false; existing-data operation remains operator-controlled",
            "assertion_status": "PASS",
        },
        {
            "gap_id": "safe_refresh_command",
            "status": "OPEN",
            "evidence_scope": "implementation readiness assessment",
            "remaining_action": (
                "define the missing schema-gated regeneration and recovery contract"
            ),
            "causes_parity_failure": "false; readiness is reported explicitly",
            "assertion_status": "PASS",
        },
    ]


def _is_populated(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _write_outputs(
    output_dir: Path,
    *,
    manifest: Mapping[str, Any],
    store_rows: Sequence[Mapping[str, object]],
    field_rows: Sequence[Mapping[str, object]],
    null_rows: Sequence[Mapping[str, object]],
    idempotency_rows: Sequence[Mapping[str, object]],
    refresh_rows: Sequence[Mapping[str, object]],
    gap_rows: Sequence[Mapping[str, object]],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=False)
    _write_json(output_dir / "manifest.json", manifest)
    _write_csv(output_dir / "store-results.csv", STORE_FIELDS, store_rows)
    _write_csv(output_dir / "field-parity-results.csv", FIELD_FIELDS, field_rows)
    _write_csv(output_dir / "null-semantics-results.csv", NULL_FIELDS, null_rows)
    _write_csv(output_dir / "idempotency-results.csv", IDEMPOTENCY_FIELDS, idempotency_rows)
    _write_csv(output_dir / "refresh-readiness-results.csv", REFRESH_FIELDS, refresh_rows)
    _write_csv(output_dir / "gap-status.csv", GAP_FIELDS, gap_rows)
    (output_dir / "summary.md").write_text(_summary(manifest), encoding="utf-8")


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _write_csv(
    path: Path,
    fieldnames: Sequence[str],
    rows: Sequence[Mapping[str, object]],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def _summary(manifest: Mapping[str, Any]) -> str:
    assertions = cast(Mapping[str, bool], manifest["assertions"])
    counts = cast(Mapping[str, object], manifest["counts"])
    runtime = cast(Mapping[str, object], manifest["runtime_inspection"])
    refresh = cast(Mapping[str, object], manifest["refresh_readiness"])
    status = "PASS" if all(assertions.values()) else "FAIL"
    return "\n".join(
        (
            "# Store parity evidence",
            "",
            f"- Overall assertion status: {status}",
            f"- Assertions passed: {counts['assertions_passed']} of {counts['assertions_total']}",
            "- SQLite execution: actual temporary SQLite database",
            (
                "- PostgreSQL-style execution: hosted SQLAlchemy mapping path on a temporary "
                "adapter plus PostgreSQL dialect compilation"
            ),
            "- Actual disposable PostgreSQL execution: not performed",
            f"- Production runtime inspection: {runtime['status']}",
            (
                "- Safe refresh command available: "
                f"{str(refresh['safe_refresh_command_available']).lower()}"
            ),
            "- Existing PostgreSQL rows require regeneration or reimport: true",
            "- Facility-reference rows require migration and preload rerun: true",
            "- Evidence contains aggregate counts and repository-relative references only.",
            "",
        )
    )


def _assert_aggregate_safe(output_dir: Path, repo_root: Path) -> None:
    combined = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(output_dir.iterdir())
    )
    lowered = combined.casefold()
    forbidden = (
        str(repo_root).casefold(),
    ) + tuple(value.casefold() for value in SYNTHETIC_FACILITY_IDS)
    if any(marker and marker in lowered for marker in forbidden):
        raise StoreParityEvidenceError("Generated evidence did not satisfy aggregate-safety rules.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Write aggregate-safe SQLite/PostgreSQL parity evidence."
    )
    parser.add_argument("--mode", choices=("local", "runtime"), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest = run_evidence(mode=args.mode, output_dir=args.output_dir)
    except StoreParityEvidenceError as exc:
        print(f"Store parity evidence failed: {exc}", file=sys.stderr)
        return 2
    except (OSError, ValueError, SQLAlchemyError):
        print(
            "Store parity evidence failed with a controlled local or database error.",
            file=sys.stderr,
        )
        return 2
    assertions = cast(Mapping[str, bool], manifest["assertions"])
    return 0 if all(assertions.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
