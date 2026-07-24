from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, cast
from urllib.parse import parse_qs, urlparse

from sqlalchemy import select
from sqlalchemy.engine import Connection

from ccld_complaints.hosted_app.ccld_retrieval_jobs import hosted_ccld_retrieval_jobs
from ccld_complaints.hosted_app.facility_reference_preload import (
    FACILITY_REFERENCE_DATASET_URL,
    FACILITY_REFERENCE_TABLE_NAME,
    hosted_facility_reference_records,
)
from ccld_complaints.hosted_app.seeded_import import (
    RAW_SHA256_PATTERN,
    hosted_import_batches,
    hosted_source_derived_records,
)
from ccld_complaints.hosted_app.source_derived_reads import CCLD_CONNECTOR_NAME
from ccld_complaints.source_profiling import FACILITY_SOURCE_REGISTRY

SOURCE_DERIVED_TABLE_NAME = "hosted_source_derived_records"
REPRESENTATIVE_COVERAGE_REPORT_SCHEMA_VERSION = 2

RepresentativeCoverageStatus = Literal["not_ready", "partial", "candidate", "validated"]
ProvenanceClassification = Literal["real_public_source", "fixture_demo_test", "unknown"]

_REQUIRED_COMPLAINT_TRACEABILITY_FIELDS = (
    "source_url",
    "raw_sha256",
    "connector_name",
    "connector_version",
    "retrieved_at",
    "source_document_id",
)
_SOURCE_DOCUMENT_AGREEMENT_FIELDS = (
    "source_document_id",
    "source_url",
    "raw_sha256",
    "connector_name",
    "connector_version",
    "retrieved_at",
    "import_batch_id",
    "facility_id",
)
_URL_LIKE_PATTERN = re.compile(r"^https://", re.IGNORECASE)
_FIXTURE_MARKERS = (
    "demo",
    "fixture",
    "mock",
    "synthetic",
    "test",
    "tiny",
)
_REAL_RETRIEVAL_MODE_MARKER = "live public ccld mode"
_FIXTURE_RETRIEVAL_MODE_MARKER = "fixture/mock mode"
_TARGET_FACILITY_RESOURCE_IDS = frozenset(
    resource["resource_id"]
    for resource in FACILITY_SOURCE_REGISTRY["target_resources"]
    if isinstance(resource.get("resource_id"), str)
)


@dataclass(frozen=True)
class CoverageThresholds:
    min_real_facility_count: int = 2
    min_real_facility_type_count: int = 2
    require_complaint_coverage: bool = True


def build_representative_coverage_report(
    connection: Connection,
    *,
    generated_at: datetime | None = None,
    thresholds: CoverageThresholds | None = None,
) -> dict[str, Any]:
    """Build a read-only coverage and reconciliation report from hosted tables."""

    active_thresholds = thresholds or CoverageThresholds()
    generated = generated_at or datetime.now(UTC)
    facility_rows = _facility_rows(connection)
    source_rows = _source_derived_rows(connection)
    batch_rows = _import_batch_rows(connection)
    retrieval_job_rows = _retrieval_job_rows(connection)
    batch_index = {_clean(row.get("import_batch_id")): row for row in batch_rows}
    retrieval_job_index = _retrieval_job_index(retrieval_job_rows)
    source_document_index = _source_document_index(source_rows)

    complaint_rows = tuple(
        row
        for row in source_rows
        if row.get("entity_type") == "complaint"
        and row.get("connector_name") == CCLD_CONNECTOR_NAME
    )
    facility_classifications = tuple(
        _classify_facility_row(row) for row in facility_rows
    )
    complaint_classifications = tuple(
        _classify_source_row(
            row,
            batch_index=batch_index,
            retrieval_job_index=retrieval_job_index,
        )
        for row in complaint_rows
    )
    real_facility_rows = tuple(
        row
        for row, classification in zip(
            facility_rows, facility_classifications, strict=True
        )
        if classification["classification"] == "real_public_source"
    )
    real_complaint_rows = tuple(
        row
        for row, classification in zip(
            complaint_rows, complaint_classifications, strict=True
        )
        if classification["classification"] == "real_public_source"
    )
    facility_index = _facility_reference_index(real_facility_rows)

    facility_reference = _facility_reference_summary(
        facility_rows,
        classifications=facility_classifications,
        eligible_rows=real_facility_rows,
    )
    complaints = _complaint_summary(
        complaint_rows,
        classifications=complaint_classifications,
        eligible_rows=real_complaint_rows,
        facility_index=facility_index,
        source_document_index=source_document_index,
        retrieval_job_rows=retrieval_job_rows,
    )
    reconciliation = _reconciliation_summary(
        source_rows=source_rows,
        batch_rows=batch_rows,
        retrieval_job_rows=retrieval_job_rows,
        complaints=complaints,
    )
    status = _representative_status(
        facility_reference=facility_reference,
        complaints=complaints,
        thresholds=active_thresholds,
    )
    complaint_status = _complaint_coverage_status(
        complaints=complaints,
        thresholds=active_thresholds,
    )
    facility_reference_status = _facility_reference_coverage_status(
        facility_reference=facility_reference,
        thresholds=active_thresholds,
    )
    return {
        "schema_version": REPRESENTATIVE_COVERAGE_REPORT_SCHEMA_VERSION,
        "generated_at": generated.astimezone(UTC).replace(microsecond=0).isoformat(),
        "scope": {
            "source_family": "California Community Care Licensing Division public records",
            "facility_reference_table": FACILITY_REFERENCE_TABLE_NAME,
            "source_derived_table": SOURCE_DERIVED_TABLE_NAME,
            "complaint_connector": CCLD_CONNECTOR_NAME,
        },
        "representative_coverage_status": status,
        "complaint_coverage_status": complaint_status,
        "facility_reference_coverage_status": facility_reference_status,
        "thresholds": {
            "min_real_facility_count": active_thresholds.min_real_facility_count,
            "min_real_facility_type_count": active_thresholds.min_real_facility_type_count,
            "require_complaint_coverage": active_thresholds.require_complaint_coverage,
        },
        "facility_reference": facility_reference,
        "complaints": complaints,
        "reconciliation": reconciliation,
        "provenance_classification": {
            "rules": (
                "Facility rows are real_public_source only when they carry the official "
                "CHHS/CDSS CCLD dataset URL and a known target resource UUID.",
                "Complaint rows are real_public_source only when their import batch links "
                "to a persisted controlled retrieval job whose safe message identifies "
                "live public CCLD mode.",
                "Rows with fixture, demo, mock, synthetic, tiny, or test markers in "
                "available provenance metadata are fixture_demo_test.",
                "Rows without enough persisted metadata for either rule are unknown and "
                "excluded from representative coverage counting.",
            ),
            "limitations": (
                "PostgreSQL storage alone is not treated as proof of real/public-source "
                "coverage.",
                "Local validated artifacts and seeded-corpus imports remain unknown unless "
                "they are clearly marked as fixture/demo/test.",
                "Facility-reference skipped-row counts remain in the preload command output "
                "and are not persisted in the current table.",
            ),
        },
        "known_limitations": _report_limitations(
            facility_reference,
            complaints,
            status,
        ),
    }


def _facility_rows(connection: Connection) -> tuple[Mapping[str, Any], ...]:
    rows = connection.execute(
        select(hosted_facility_reference_records).order_by(
            hosted_facility_reference_records.c.source_resource_name,
            hosted_facility_reference_records.c.source_file_name,
            hosted_facility_reference_records.c.facility_number,
        )
    ).mappings()
    return tuple(dict(row) for row in rows)


def _source_derived_rows(connection: Connection) -> tuple[Mapping[str, Any], ...]:
    rows = connection.execute(
        select(hosted_source_derived_records).order_by(
            hosted_source_derived_records.c.entity_type,
            hosted_source_derived_records.c.stable_source_id,
            hosted_source_derived_records.c.source_record_key,
        )
    ).mappings()
    return tuple(dict(row) for row in rows)


def _import_batch_rows(connection: Connection) -> tuple[Mapping[str, Any], ...]:
    rows = connection.execute(
        select(hosted_import_batches).order_by(hosted_import_batches.c.import_batch_id)
    ).mappings()
    return tuple(dict(row) for row in rows)


def _retrieval_job_rows(connection: Connection) -> tuple[Mapping[str, Any], ...]:
    rows = connection.execute(
        select(hosted_ccld_retrieval_jobs).order_by(
            hosted_ccld_retrieval_jobs.c.retrieval_job_id
        )
    ).mappings()
    return tuple(dict(row) for row in rows)


def _retrieval_job_index(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    index: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        source_artifact_identity = _clean(row.get("source_artifact_identity"))
        if source_artifact_identity:
            index[source_artifact_identity] = row
    return index


def _source_document_index(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    index: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if row.get("entity_type") != "source_document":
            continue
        source_document_id = _clean(row.get("source_document_id"))
        if source_document_id and source_document_id not in index:
            index[source_document_id] = row
    return index


def _facility_reference_summary(
    rows: Sequence[Mapping[str, Any]],
    *,
    classifications: Sequence[Mapping[str, Any]],
    eligible_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    complete_identity_count = sum(1 for row in rows if _facility_reference_row_has_identity(row))
    eligible_complete_identity_count = sum(
        1 for row in eligible_rows if _facility_reference_row_has_identity(row)
    )
    return {
        "current_hosted_row_count": len(rows),
        "complete_identity_row_count": complete_identity_count,
        "eligible_representative_row_count": len(eligible_rows),
        "eligible_complete_identity_row_count": eligible_complete_identity_count,
        "distinct_facility_number_count": len(
            {
                _clean(row.get("facility_number"))
                for row in rows
                if _clean(row.get("facility_number"))
            }
        ),
        "eligible_distinct_facility_number_count": len(
            {
                _clean(row.get("facility_number"))
                for row in eligible_rows
                if _clean(row.get("facility_number"))
            }
        ),
        "facility_type_count": len({_facility_type(row) for row in rows}),
        "eligible_facility_type_count": len({_facility_type(row) for row in eligible_rows}),
        "source_dataset_url": FACILITY_REFERENCE_DATASET_URL,
        "source_identity_duplicate_rows": _duplicate_count(
            (_clean(row.get("source_resource_id")), _clean(row.get("facility_number")))
            for row in rows
        ),
        "facility_number_cross_resource_duplicate_rows": _duplicate_count(
            (_clean(row.get("facility_number")),)
            for row in rows
            if _clean(row.get("facility_number"))
        ),
        "provenance_counts": _classification_counts(classifications),
        "excluded_from_representative_coverage_count": _excluded_count(classifications),
        "classification_basis": _classification_basis_summaries(classifications),
        "source_files": _facility_source_files(rows, classifications=classifications),
        "facility_types": _facility_type_summaries(rows, classifications=classifications),
        "search_fields_measured": (
            "facility_number",
            "facility_name",
            "city",
            "county",
            "zip",
            "facility_type",
            "program_type",
            "licensee_name",
            "status",
        ),
    }


def _facility_source_files(
    rows: Sequence[Mapping[str, Any]],
    *,
    classifications: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    grouped: dict[tuple[str, str, str], list[tuple[Mapping[str, Any], Mapping[str, Any]]]] = (
        defaultdict(list)
    )
    for row, classification in zip(rows, classifications, strict=True):
        key = (
            _clean(row.get("source_resource_id")),
            _clean(row.get("source_resource_name")),
            _clean(row.get("source_file_name")),
        )
        grouped[key].append((row, classification))
    summaries = []
    for (resource_id, resource_name, source_file), grouped_rows in sorted(grouped.items()):
        file_rows = tuple(row for row, _classification in grouped_rows)
        file_classifications = tuple(classification for _row, classification in grouped_rows)
        summaries.append(
            {
                "source_resource_id": resource_id,
                "source_resource_name": resource_name,
                "source_file_name": source_file,
                "source_dataset_url": _first_clean(file_rows, "source_dataset_url"),
                "source_accessed_at_values": _unique_values(file_rows, "source_accessed_at"),
                "snapshot_dates": _unique_values(file_rows, "snapshot_date"),
                "current_hosted_row_count": len(file_rows),
                "complete_identity_row_count": sum(
                    1 for row in file_rows if _facility_reference_row_has_identity(row)
                ),
                "eligible_representative_row_count": sum(
                    1
                    for classification in file_classifications
                    if classification["classification"] == "real_public_source"
                ),
                "provenance_counts": _classification_counts(file_classifications),
                "facility_types": tuple(sorted({_facility_type(row) for row in file_rows})),
            }
        )
    return tuple(summaries)


def _facility_type_summaries(
    rows: Sequence[Mapping[str, Any]],
    *,
    classifications: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    grouped: dict[str, list[tuple[Mapping[str, Any], Mapping[str, Any]]]] = defaultdict(list)
    for row, classification in zip(rows, classifications, strict=True):
        grouped[_facility_type(row)].append((row, classification))
    summaries = []
    for facility_type, grouped_rows in sorted(grouped.items()):
        type_rows = tuple(row for row, _classification in grouped_rows)
        type_classifications = tuple(classification for _row, classification in grouped_rows)
        summaries.append(
            {
                "facility_type": facility_type,
                "current_hosted_row_count": len(type_rows),
                "complete_identity_row_count": sum(
                    1 for row in type_rows if _facility_reference_row_has_identity(row)
                ),
                "eligible_representative_row_count": sum(
                    1
                    for classification in type_classifications
                    if classification["classification"] == "real_public_source"
                ),
                "distinct_facility_number_count": len(
                    {
                        _clean(row.get("facility_number"))
                        for row in type_rows
                        if _clean(row.get("facility_number"))
                    }
                ),
                "source_files": tuple(
                    sorted({_clean(row.get("source_file_name")) for row in type_rows})
                ),
                "source_resource_names": tuple(
                    sorted({_clean(row.get("source_resource_name")) for row in type_rows})
                ),
                "source_urls": tuple(
                    sorted({_clean(row.get("source_dataset_url")) for row in type_rows})
                ),
                "snapshot_dates": _unique_values(type_rows, "snapshot_date"),
                "source_accessed_at_values": _unique_values(type_rows, "source_accessed_at"),
                "provenance_counts": _classification_counts(type_classifications),
            }
        )
    return tuple(summaries)


def _complaint_summary(
    rows: Sequence[Mapping[str, Any]],
    *,
    classifications: Sequence[Mapping[str, Any]],
    eligible_rows: Sequence[Mapping[str, Any]],
    facility_index: Mapping[str, Mapping[str, Any]],
    source_document_index: Mapping[str, Mapping[str, Any]],
    retrieval_job_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    traceability = _traceability_summary(rows)
    linkage = _source_document_linkage_summary(rows, source_document_index)
    eligible_linkage = _source_document_linkage_summary(eligible_rows, source_document_index)
    eligible_traceability_complete_count = sum(
        1 for row in eligible_rows if _complaint_traceability_is_complete(row)
    )
    return {
        "current_hosted_row_count": len(rows),
        "traceability_complete_complaint_count": traceability["complete_count"],
        "traceability_incomplete_complaint_count": traceability["incomplete_count"],
        "source_document_linked_complaint_count": linkage["linked_count"],
        "eligible_representative_complaint_count": len(eligible_rows),
        "eligible_traceability_complete_complaint_count": eligible_traceability_complete_count,
        "eligible_distinct_facility_count": len(
            {
                facility_number
                for row in eligible_rows
                if (facility_number := _facility_number_from_source_row(row)) is not None
            }
        ),
        "distinct_facility_count": len(
            {
                facility_number
                for row in rows
                if (facility_number := _facility_number_from_source_row(row)) is not None
            }
        ),
        "duplicate_stable_identity_rows": _duplicate_count(
            (_clean(row.get("entity_type")), _clean(row.get("stable_source_id"))) for row in rows
        ),
        "source_url_duplicate_rows": _duplicate_count(
            (_clean(row.get("source_url")),) for row in rows if _clean(row.get("source_url"))
        ),
        "provenance_counts": _classification_counts(classifications),
        "excluded_from_representative_coverage_count": _excluded_count(classifications),
        "classification_basis": _classification_basis_summaries(classifications),
        "traceability": traceability,
        "source_document_linkage": linkage,
        "eligible_source_document_linkage": eligible_linkage,
        "retrieval_job_reconciliation": _retrieval_job_reconciliation(retrieval_job_rows),
        "facility_types": _complaint_facility_type_summaries(eligible_rows, facility_index),
    }


def _complaint_facility_type_summaries(
    rows: Sequence[Mapping[str, Any]],
    facility_index: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        facility_number = _facility_number_from_source_row(row)
        facility_type = "unmatched facility reference"
        if facility_number is not None and facility_number in facility_index:
            facility_type = _facility_type(facility_index[facility_number])
        grouped[facility_type].append(row)
    summaries = []
    for facility_type, type_rows in sorted(grouped.items()):
        summaries.append(
            {
                "facility_type": facility_type,
                "eligible_representative_complaint_count": len(type_rows),
                "traceability_complete_complaint_count": sum(
                    1 for row in type_rows if _complaint_traceability_is_complete(row)
                ),
                "distinct_facility_count": len(
                    {
                        facility_number
                        for row in type_rows
                        if (facility_number := _facility_number_from_source_row(row)) is not None
                    }
                ),
                "retrieved_at_values": _unique_values(type_rows, "retrieved_at"),
                "source_urls": tuple(sorted({_clean(row.get("source_url")) for row in type_rows})),
            }
        )
    return tuple(summaries)


def _traceability_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    field_counts: dict[str, int] = {}
    for field_name in _REQUIRED_COMPLAINT_TRACEABILITY_FIELDS:
        if field_name == "raw_sha256":
            field_counts[field_name] = sum(
                1
                for row in rows
                if RAW_SHA256_PATTERN.fullmatch(_clean(row.get("raw_sha256"))) is not None
            )
        elif field_name == "source_url":
            field_counts[field_name] = sum(
                1
                for row in rows
                if _URL_LIKE_PATTERN.search(_clean(row.get("source_url"))) is not None
            )
        else:
            field_counts[field_name] = sum(1 for row in rows if _clean(row.get(field_name)))
    complete_count = sum(1 for row in rows if _complaint_traceability_is_complete(row))
    return {
        "complete_count": complete_count,
        "incomplete_count": len(rows) - complete_count,
        "field_present_counts": field_counts,
    }


def _source_document_linkage_summary(
    rows: Sequence[Mapping[str, Any]],
    source_document_index: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    exact = 0
    partial = 0
    missing = 0
    conflicting = 0
    conflict_fields: Counter[str] = Counter()
    for row in rows:
        link = _source_document_linkage(row, source_document_index)
        if link["status"] == "exact_match":
            exact += 1
        elif link["status"] == "partial_match":
            partial += 1
        elif link["status"] == "missing_link":
            missing += 1
        else:
            conflicting += 1
        for field_name in link["conflicting_fields"]:
            conflict_fields[field_name] += 1
    return {
        "linked_count": exact + partial + conflicting,
        "exact_match_count": exact,
        "partial_match_count": partial,
        "missing_link_count": missing,
        "conflicting_link_count": conflicting,
        "conflicting_field_counts": dict(sorted(conflict_fields.items())),
    }


def _source_document_linkage(
    complaint_row: Mapping[str, Any],
    source_document_index: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    source_document_id = _clean(complaint_row.get("source_document_id"))
    source_document = source_document_index.get(source_document_id)
    if source_document is None:
        return {
            "status": "missing_link",
            "missing_fields": (),
            "conflicting_fields": (),
        }
    missing_fields = []
    conflicting_fields = []
    for field_name in _SOURCE_DOCUMENT_AGREEMENT_FIELDS:
        complaint_value = _agreement_value(complaint_row, field_name)
        document_value = _agreement_value(source_document, field_name)
        if not complaint_value or not document_value:
            missing_fields.append(field_name)
        elif complaint_value != document_value:
            conflicting_fields.append(field_name)
    if conflicting_fields:
        status = "conflicting_link"
    elif missing_fields:
        status = "partial_match"
    else:
        status = "exact_match"
    return {
        "status": status,
        "missing_fields": tuple(missing_fields),
        "conflicting_fields": tuple(conflicting_fields),
    }


def _retrieval_job_reconciliation(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    retrieval_failures = 0
    validation_rejections = 0
    skipped_records = 0
    duplicate_or_idempotent = 0
    imported_rows = 0
    retrieved_bundles = 0
    mutated_job_count = 0
    state_counts: Counter[str] = Counter()
    for row in rows:
        state_counts[_clean(row.get("job_state"))] += 1
        counts = _int_mapping(row.get("result_counts"))
        retrieval_failures += counts.get("report_failures", 0)
        validation_rejections += _sum_count_keys(
            counts,
            (
                "validation_rejections",
                "validation_rejected_records",
                "validation_failed_records",
            ),
        )
        skipped_records += _sum_count_keys(
            counts,
            (
                "skipped_records",
                "skipped_source_records",
                "skipped_non_matching_source_record_count",
            ),
        )
        duplicate_or_idempotent += _sum_count_keys(
            counts,
            (
                "duplicate_source_records",
                "duplicate_avoided_records",
                "refreshed_source_record_count",
                "skipped_duplicate_source_record_count",
            ),
        )
        imported_rows += counts.get("imported_source_derived_records", 0)
        retrieved_bundles += counts.get("retrieved_record_bundles", 0)
        if row.get("data_mutations_performed") is True:
            mutated_job_count += 1
    return {
        "job_count": len(rows),
        "job_state_counts": dict(sorted(state_counts.items())),
        "jobs_with_data_mutations": mutated_job_count,
        "retrieved_record_bundle_count": retrieved_bundles,
        "reported_imported_source_derived_record_count": imported_rows,
        "reported_retrieval_failure_count": retrieval_failures,
        "reported_validation_rejection_count": validation_rejections,
        "reported_skipped_record_count": skipped_records,
        "reported_duplicate_or_idempotent_record_count": duplicate_or_idempotent,
    }


def _reconciliation_summary(
    *,
    source_rows: Sequence[Mapping[str, Any]],
    batch_rows: Sequence[Mapping[str, Any]],
    retrieval_job_rows: Sequence[Mapping[str, Any]],
    complaints: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "source_derived_current_rows_by_entity": _entity_counts(source_rows),
        "import_batches": _import_batch_reconciliation(source_rows, batch_rows),
        "retrieval_jobs": _retrieval_job_reconciliation(retrieval_job_rows),
        "complaints": {
            "current_hosted_row_count": complaints["current_hosted_row_count"],
            "eligible_representative_complaint_count": complaints[
                "eligible_representative_complaint_count"
            ],
            "traceability_complete_complaint_count": complaints[
                "traceability_complete_complaint_count"
            ],
            "traceability_incomplete_complaint_count": complaints[
                "traceability_incomplete_complaint_count"
            ],
            "source_document_linked_complaint_count": complaints[
                "source_document_linked_complaint_count"
            ],
            "duplicate_stable_identity_rows": complaints["duplicate_stable_identity_rows"],
        },
        "unresolved_differences": _unresolved_differences(source_rows, batch_rows),
    }


def _import_batch_reconciliation(
    source_rows: Sequence[Mapping[str, Any]],
    batch_rows: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    current_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in source_rows:
        current_counts[_clean(row.get("import_batch_id"))][_clean(row.get("entity_type"))] += 1
    summaries = []
    for batch in batch_rows:
        import_batch_id = _clean(batch.get("import_batch_id"))
        declared_counts = _int_mapping(batch.get("record_counts"))
        persisted_counts = dict(sorted(current_counts.get(import_batch_id, Counter()).items()))
        differences = {
            key: declared_counts.get(key, 0) - persisted_counts.get(key, 0)
            for key in sorted(set(declared_counts) | set(persisted_counts))
            if persisted_counts.get(key, 0) != declared_counts.get(key, 0)
        }
        summaries.append(
            {
                "import_batch_id": import_batch_id,
                "source_artifact_identity": _clean(batch.get("source_artifact_identity")),
                "source_pipeline_version": _clean(batch.get("source_pipeline_version")),
                "validation_status": _clean(batch.get("validation_status")),
                "raw_hash_validation_status": _clean(batch.get("raw_hash_validation_status")),
                "declared_record_counts": dict(sorted(declared_counts.items())),
                "current_persisted_record_counts": persisted_counts,
                "declared_minus_current_differences": differences,
            }
        )
    return tuple(summaries)


def _unresolved_differences(
    source_rows: Sequence[Mapping[str, Any]],
    batch_rows: Sequence[Mapping[str, Any]],
) -> tuple[str, ...]:
    messages = []
    batch_ids = {_clean(batch.get("import_batch_id")) for batch in batch_rows}
    row_batch_ids = {_clean(row.get("import_batch_id")) for row in source_rows}
    missing_batches = tuple(sorted(row_batch_ids - batch_ids))
    if missing_batches:
        messages.append(
            "Some source-derived rows reference import batches that are not present: "
            + ", ".join(missing_batches)
        )
    for summary in _import_batch_reconciliation(source_rows, batch_rows):
        differences = cast(Mapping[str, int], summary["declared_minus_current_differences"])
        if differences:
            messages.append(
                f"Import batch {summary['import_batch_id']} declared counts differ from "
                f"current persisted rows: {dict(differences)}"
            )
    return tuple(messages)


def _representative_status(
    *,
    facility_reference: Mapping[str, Any],
    complaints: Mapping[str, Any],
    thresholds: CoverageThresholds,
) -> dict[str, Any]:
    blockers = []
    warnings = []

    if facility_reference["eligible_distinct_facility_number_count"] < (
        thresholds.min_real_facility_count
    ):
        blockers.append("fewer real/public-source facilities than the configured threshold")
    if facility_reference["eligible_facility_type_count"] < thresholds.min_real_facility_type_count:
        blockers.append("fewer real/public-source facility types than the configured threshold")
    if (
        thresholds.require_complaint_coverage
        and complaints["eligible_representative_complaint_count"] == 0
    ):
        blockers.append("no real/public-source complaint coverage")
    if complaints["eligible_representative_complaint_count"] != complaints[
        "eligible_traceability_complete_complaint_count"
    ]:
        blockers.append("not all eligible real/public-source complaints are traceability-complete")
    if complaints["duplicate_stable_identity_rows"]:
        blockers.append("duplicate source-derived stable identities are present")
    linkage = cast(Mapping[str, Any], complaints["eligible_source_document_linkage"])
    if linkage["missing_link_count"] or linkage["conflicting_link_count"]:
        blockers.append("source-document linkage is missing or conflicting")
    if facility_reference["provenance_counts"].get("unknown", 0) or complaints[
        "provenance_counts"
    ].get("unknown", 0):
        blockers.append("some loaded rows have unknown provenance")
    if complaints["provenance_counts"].get("fixture_demo_test", 0) or facility_reference[
        "provenance_counts"
    ].get("fixture_demo_test", 0):
        warnings.append("fixture/demo/test rows are loaded but excluded from representative counts")

    has_real_rows = bool(
        facility_reference["eligible_representative_row_count"]
        or complaints["eligible_representative_complaint_count"]
    )
    if not has_real_rows:
        status: RepresentativeCoverageStatus = "not_ready"
    elif blockers:
        status = "partial"
    else:
        status = "candidate"
        warnings.append(
            "Automated coverage criteria are satisfied; manual source reconciliation and "
            "stakeholder acceptance are still required before issue #414 can close."
        )
    return {
        "status": status,
        "blockers": tuple(blockers),
        "warnings": tuple(warnings),
        "validated_status_rule": (
            "This report does not mark coverage as validated from PostgreSQL rows alone. "
            "Validated status is reserved for a future workflow that records automated "
            "criteria, operator source reconciliation, and stakeholder acceptance."
        ),
    }


def _complaint_coverage_status(
    *,
    complaints: Mapping[str, Any],
    thresholds: CoverageThresholds,
) -> dict[str, Any]:
    blockers = []
    warnings = []

    if (
        thresholds.require_complaint_coverage
        and complaints["eligible_representative_complaint_count"] == 0
    ):
        blockers.append("no real/public-source complaint coverage")
    if complaints["eligible_representative_complaint_count"] != complaints[
        "eligible_traceability_complete_complaint_count"
    ]:
        blockers.append("not all eligible real/public-source complaints are traceability-complete")
    if complaints["duplicate_stable_identity_rows"]:
        blockers.append("duplicate source-derived stable identities are present")
    linkage = cast(Mapping[str, Any], complaints["eligible_source_document_linkage"])
    if linkage["missing_link_count"] or linkage["conflicting_link_count"]:
        blockers.append("source-document linkage is missing or conflicting")
    if complaints["provenance_counts"].get("unknown", 0):
        blockers.append("some loaded complaint rows have unknown provenance")
    if complaints["provenance_counts"].get("fixture_demo_test", 0):
        warnings.append(
            "fixture/demo/test complaint rows are loaded but excluded from representative counts"
        )

    if not complaints["eligible_representative_complaint_count"]:
        status: RepresentativeCoverageStatus = "not_ready"
    elif blockers:
        status = "partial"
    else:
        status = "candidate"
        warnings.append(
            "Automated complaint coverage criteria are satisfied; manual source reconciliation "
            "and stakeholder acceptance are still required before issue #414 can close."
        )
    return {
        "status": status,
        "blockers": tuple(blockers),
        "warnings": tuple(warnings),
        "validated_status_rule": (
            "This report does not mark complaint coverage as validated from PostgreSQL "
            "rows alone. Validated status is reserved for a future workflow that records "
            "automated criteria, operator source reconciliation, and stakeholder acceptance."
        ),
    }


def _facility_reference_coverage_status(
    *,
    facility_reference: Mapping[str, Any],
    thresholds: CoverageThresholds,
) -> dict[str, Any]:
    blockers = []
    warnings = []

    if facility_reference["eligible_distinct_facility_number_count"] < (
        thresholds.min_real_facility_count
    ):
        blockers.append("fewer real/public-source facilities than the configured threshold")
    if facility_reference["eligible_facility_type_count"] < thresholds.min_real_facility_type_count:
        blockers.append("fewer real/public-source facility types than the configured threshold")
    if facility_reference["provenance_counts"].get("unknown", 0):
        blockers.append("some loaded facility-reference rows have unknown provenance")
    if facility_reference["provenance_counts"].get("fixture_demo_test", 0):
        warnings.append(
            "fixture/demo/test facility-reference rows are loaded but excluded from "
            "representative counts"
        )

    if not facility_reference["eligible_representative_row_count"]:
        status: RepresentativeCoverageStatus = "not_ready"
    elif blockers:
        status = "partial"
    else:
        status = "candidate"
        warnings.append(
            "Automated facility-reference coverage criteria are satisfied; manual source "
            "reconciliation and stakeholder acceptance are still required before issue #414 "
            "can close."
        )
    return {
        "status": status,
        "blockers": tuple(blockers),
        "warnings": tuple(warnings),
        "validated_status_rule": (
            "This report does not mark facility-reference coverage as validated from "
            "PostgreSQL rows alone. Validated status is reserved for a future workflow that "
            "records automated criteria, operator source reconciliation, and stakeholder "
            "acceptance."
        ),
    }


def _classify_facility_row(row: Mapping[str, Any]) -> dict[str, Any]:
    inspected = {
        "source_resource_id": _clean(row.get("source_resource_id")),
        "source_resource_name": _clean(row.get("source_resource_name")),
        "source_dataset_url": _clean(row.get("source_dataset_url")),
        "source_file_name": _clean(row.get("source_file_name")),
        "source_accessed_at": _clean(row.get("source_accessed_at")),
    }
    if _contains_fixture_marker(inspected.values()):
        classification: ProvenanceClassification = "fixture_demo_test"
        basis = "facility reference metadata contains fixture/demo/test marker"
    elif (
        inspected["source_dataset_url"] == FACILITY_REFERENCE_DATASET_URL
        and inspected["source_resource_id"] in _TARGET_FACILITY_RESOURCE_IDS
    ):
        classification = "real_public_source"
        basis = "official CHHS/CDSS dataset URL and known target resource ID"
    else:
        classification = "unknown"
        basis = "facility reference metadata is not enough to prove real public-source provenance"
    return {
        "classification": classification,
        "basis": basis,
        "metadata": inspected,
    }


def _classify_source_row(
    row: Mapping[str, Any],
    *,
    batch_index: Mapping[str, Mapping[str, Any]],
    retrieval_job_index: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    import_batch_id = _clean(row.get("import_batch_id"))
    batch = batch_index.get(import_batch_id, {})
    source_traceability = _mapping(row.get("source_traceability"))
    source_artifact_identity = _clean(
        batch.get("source_artifact_identity")
    ) or _clean(source_traceability.get("source_artifact_identity"))
    retrieval_job = retrieval_job_index.get(source_artifact_identity)
    inspected = {
        "import_batch_id": import_batch_id,
        "source_artifact_identity": source_artifact_identity,
        "source_pipeline_version": _clean(batch.get("source_pipeline_version")),
        "validation_status": _clean(batch.get("validation_status")),
        "raw_hash_validation_status": _clean(batch.get("raw_hash_validation_status")),
        "retrieval_job_id": _clean(retrieval_job.get("retrieval_job_id"))
        if retrieval_job
        else "",
        "retrieval_job_safe_message": _clean(retrieval_job.get("safe_message"))
        if retrieval_job
        else "",
    }
    if _contains_fixture_marker(inspected.values()) or _FIXTURE_RETRIEVAL_MODE_MARKER in (
        inspected["retrieval_job_safe_message"].casefold()
    ):
        classification: ProvenanceClassification = "fixture_demo_test"
        basis = "import batch or retrieval-job metadata contains fixture/demo/test marker"
    elif (
        source_artifact_identity.startswith("ccld-retrieval-job:")
        and retrieval_job is not None
        and _REAL_RETRIEVAL_MODE_MARKER
        in inspected["retrieval_job_safe_message"].casefold()
    ):
        classification = "real_public_source"
        basis = "import batch links to a live public CCLD controlled retrieval job"
    else:
        classification = "unknown"
        basis = "persisted import metadata is not enough to prove real public-source provenance"
    return {
        "classification": classification,
        "basis": basis,
        "metadata": inspected,
    }


def _classification_counts(
    classifications: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    counter = Counter(_clean(item.get("classification")) for item in classifications)
    return {
        "real_public_source": counter.get("real_public_source", 0),
        "fixture_demo_test": counter.get("fixture_demo_test", 0),
        "unknown": counter.get("unknown", 0),
    }


def _excluded_count(classifications: Sequence[Mapping[str, Any]]) -> int:
    return sum(1 for item in classifications if item.get("classification") != "real_public_source")


def _classification_basis_summaries(
    classifications: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    grouped: Counter[tuple[str, str]] = Counter(
        (_clean(item.get("classification")), _clean(item.get("basis")))
        for item in classifications
    )
    return tuple(
        {
            "classification": classification,
            "basis": basis,
            "row_count": count,
        }
        for (classification, basis), count in sorted(grouped.items())
    )


def _report_limitations(
    facility_reference: Mapping[str, Any],
    complaints: Mapping[str, Any],
    status: Mapping[str, Any],
) -> tuple[str, ...]:
    limitations = [
        (
            "The report measures and classifies rows already loaded into hosted "
            "PostgreSQL tables; it does not run live CCLD calls, preload facility "
            "CSVs, or import source-derived complaint rows."
        ),
        (
            "PostgreSQL storage alone is not proof that rows are real production/QNAP "
            "coverage."
        ),
        (
            "Facility-reference parser skipped-row counts are available from the "
            "preload command output and are not persisted in the current table."
        ),
        (
            "Counts are source-derived coverage measurements, not public-source "
            "completeness, legal, harm, abuse, neglect, liability, or "
            "rights-deprivation conclusions."
        ),
        (
            "Missing values remain missing in the source-derived rows and are counted "
            "as unavailable rather than inferred."
        ),
        (
            "Manual browser evidence, source reconciliation against selected original "
            "public records, and stakeholder acceptance remain required before issue "
            "#414 can close."
        ),
    ]
    if facility_reference["eligible_representative_row_count"] == 0:
        limitations.append("No real/public-source facility-reference rows are proven loaded.")
    if complaints["eligible_representative_complaint_count"] == 0:
        limitations.append("No real/public-source CCLD complaint rows are proven loaded.")
    if status["status"] != "candidate":
        limitations.append("Representative coverage is not ready under the configured thresholds.")
    return tuple(limitations)


def _facility_reference_index(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    index: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        facility_number = _clean(row.get("facility_number"))
        if facility_number and facility_number not in index:
            index[facility_number] = row
    return index


def _facility_reference_row_has_identity(row: Mapping[str, Any]) -> bool:
    return bool(_clean(row.get("facility_number")) and _clean(row.get("facility_name")))


def _complaint_traceability_is_complete(row: Mapping[str, Any]) -> bool:
    return all(
        (
            RAW_SHA256_PATTERN.fullmatch(_clean(row.get("raw_sha256"))) is not None
            if field_name == "raw_sha256"
            else bool(_clean(row.get(field_name)))
        )
        for field_name in _REQUIRED_COMPLAINT_TRACEABILITY_FIELDS
    ) and _URL_LIKE_PATTERN.search(_clean(row.get("source_url"))) is not None


def _facility_type(row: Mapping[str, Any]) -> str:
    return _clean(row.get("facility_type")) or "unknown"


def _facility_number_from_source_row(row: Mapping[str, Any]) -> str | None:
    original_values = _mapping(row.get("original_values"))
    candidates = (
        original_values.get("external_facility_number"),
        original_values.get("facility_number"),
        original_values.get("facility_id"),
        row.get("facility_id"),
        row.get("stable_source_id") if row.get("entity_type") == "facility" else None,
    )
    for value in candidates:
        normalized = _normalized_facility_number(value)
        if normalized is not None:
            return normalized
    return _facility_number_from_source_url(_clean(row.get("source_url")))


def _facility_number_from_source_url(source_url: str) -> str | None:
    parsed = urlparse(source_url)
    query_values = parse_qs(parsed.query, keep_blank_values=True)
    for key, values in query_values.items():
        if key.casefold() in {"facnum", "facilitynumber"}:
            for value in values:
                normalized = _normalized_facility_number(value)
                if normalized is not None:
                    return normalized
    path_leaf = parsed.path.rstrip("/").rsplit("/", 1)[-1]
    return _normalized_facility_number(path_leaf)


def _normalized_facility_number(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return text
    suffix = text.rsplit(":", 1)[-1].strip()
    if suffix.isdigit():
        return suffix
    return None


def _agreement_value(row: Mapping[str, Any], field_name: str) -> str:
    if field_name == "source_document_id":
        return _clean(row.get("source_document_id"))
    return _clean(row.get(field_name))


def _entity_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counter = Counter(_clean(row.get("entity_type")) for row in rows)
    return dict(sorted(counter.items()))


def _sum_count_keys(counts: Mapping[str, int], keys: Sequence[str]) -> int:
    return sum(counts.get(key, 0) for key in keys)


def _duplicate_count(keys: Iterable[tuple[str, ...]]) -> int:
    counter = Counter(keys)
    return sum(count - 1 for count in counter.values() if count > 1)


def _unique_values(rows: Sequence[Mapping[str, Any]], key: str) -> tuple[str, ...]:
    return tuple(sorted({_clean(row.get(key)) for row in rows if _clean(row.get(key))}))


def _first_clean(rows: Sequence[Mapping[str, Any]], key: str) -> str:
    for row in rows:
        value = _clean(row.get(key))
        if value:
            return value
    return ""


def _contains_fixture_marker(values: Iterable[str]) -> bool:
    searchable = " ".join(value.casefold() for value in values)
    return any(marker in searchable for marker in _FIXTURE_MARKERS)


def _mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return cast(Mapping[str, Any], value)
    return {}


def _int_mapping(value: object) -> Mapping[str, int]:
    if not isinstance(value, Mapping):
        return {}
    counts: dict[str, int] = {}
    for key, count in value.items():
        if isinstance(key, str) and isinstance(count, int):
            counts[key] = count
    return counts


def _clean(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())
