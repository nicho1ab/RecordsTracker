from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import Connection

from ccld_complaints.hosted_app.ccld_retrieval_jobs import (
    hosted_ccld_retrieval_jobs,
    retrieval_import_batch_id,
)
from ccld_complaints.hosted_app.seeded_import import (
    SOURCE_DERIVED_ENTITY_TYPES,
    hosted_import_batches,
    hosted_source_derived_records,
)

_LIVE_PUBLIC_MODE_MARKER = "live public ccld mode"
_RETRIEVAL_ARTIFACT_PREFIX = "ccld-retrieval-job:"
_RETRIEVAL_PIPELINE_VERSION = "ccld-controlled-retrieval-job-0.1.0"
_REPAIR_WARNING = "Import batch provenance repaired from persisted live retrieval metadata."


@dataclass(frozen=True)
class RetrievalProvenanceRepairResult:
    dry_run: bool
    candidate_source_record_count: int
    repaired_source_record_count: int
    inserted_import_batch_count: int
    updated_import_batch_count: int
    skipped_conflicting_import_batch_count: int
    repaired_import_batch_ids: tuple[str, ...]
    skipped_import_batch_ids: tuple[str, ...]


def repair_live_retrieval_provenance(
    connection: Connection,
    *,
    dry_run: bool = True,
) -> RetrievalProvenanceRepairResult:
    """Relink rows to deterministic live retrieval import batches when metadata proves it.

    The repair is deliberately narrow: it uses only each source-derived row's persisted
    source artifact identity plus the matching retrieval job row. Fixture/mock jobs,
    missing jobs, unknown artifact identities, and conflicting target batches are left
    untouched.
    """

    source_rows = _source_rows(connection)
    retrieval_jobs = _live_retrieval_jobs_by_artifact(connection)
    candidate_rows_by_batch: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    all_artifact_rows_by_batch: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    job_by_batch_id: dict[str, Mapping[str, Any]] = {}

    for row in source_rows:
        source_traceability = _mapping(row.get("source_traceability"))
        artifact_identity = _clean(source_traceability.get("source_artifact_identity"))
        if not artifact_identity.startswith(_RETRIEVAL_ARTIFACT_PREFIX):
            continue
        retrieval_job = retrieval_jobs.get(artifact_identity)
        if retrieval_job is None:
            continue
        target_batch_id = retrieval_import_batch_id(_clean(retrieval_job.get("retrieval_job_id")))
        all_artifact_rows_by_batch[target_batch_id].append(row)
        job_by_batch_id[target_batch_id] = retrieval_job
        if _clean(row.get("import_batch_id")) != target_batch_id:
            candidate_rows_by_batch[target_batch_id].append(row)

    inserted_batches = 0
    updated_batches = 0
    repaired_rows = 0
    repaired_batch_ids: list[str] = []
    skipped_batch_ids: list[str] = []

    for target_batch_id, candidate_rows in sorted(candidate_rows_by_batch.items()):
        retrieval_job = job_by_batch_id[target_batch_id]
        artifact_identity = _clean(retrieval_job.get("source_artifact_identity"))
        existing_batch = _import_batch(connection, target_batch_id)
        if (
            existing_batch
            and _clean(existing_batch.get("source_artifact_identity")) != artifact_identity
        ):
            skipped_batch_ids.append(target_batch_id)
            continue
        if not dry_run:
            counts = _record_counts(all_artifact_rows_by_batch[target_batch_id])
            if existing_batch is None:
                connection.execute(
                    hosted_import_batches.insert().values(
                        **_batch_values(target_batch_id, retrieval_job, counts)
                    )
                )
                inserted_batches += 1
            else:
                connection.execute(
                    update(hosted_import_batches)
                    .where(hosted_import_batches.c.import_batch_id == target_batch_id)
                    .values(**_batch_values(target_batch_id, retrieval_job, counts))
                )
                updated_batches += 1
            for row in candidate_rows:
                connection.execute(
                    update(hosted_source_derived_records)
                    .where(
                        hosted_source_derived_records.c.source_record_key
                        == row["source_record_key"]
                    )
                    .values(import_batch_id=target_batch_id)
                )
                repaired_rows += 1
        repaired_batch_ids.append(target_batch_id)

    return RetrievalProvenanceRepairResult(
        dry_run=dry_run,
        candidate_source_record_count=sum(len(rows) for rows in candidate_rows_by_batch.values()),
        repaired_source_record_count=repaired_rows,
        inserted_import_batch_count=inserted_batches,
        updated_import_batch_count=updated_batches,
        skipped_conflicting_import_batch_count=len(skipped_batch_ids),
        repaired_import_batch_ids=tuple(repaired_batch_ids),
        skipped_import_batch_ids=tuple(skipped_batch_ids),
    )


def _source_rows(connection: Connection) -> tuple[Mapping[str, Any], ...]:
    rows = connection.execute(select(hosted_source_derived_records)).mappings()
    return tuple(dict(row) for row in rows)


def _live_retrieval_jobs_by_artifact(
    connection: Connection,
) -> dict[str, Mapping[str, Any]]:
    rows = connection.execute(select(hosted_ccld_retrieval_jobs)).mappings()
    index: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        job = dict(row)
        artifact_identity = _clean(job.get("source_artifact_identity"))
        if not artifact_identity.startswith(_RETRIEVAL_ARTIFACT_PREFIX):
            continue
        if _clean(job.get("job_state")) not in {"completed", "completed_with_warnings"}:
            continue
        if job.get("data_mutations_performed") is not True:
            continue
        if _LIVE_PUBLIC_MODE_MARKER not in _clean(job.get("safe_message")).casefold():
            continue
        index[artifact_identity] = job
    return index


def _import_batch(connection: Connection, import_batch_id: str) -> Mapping[str, Any] | None:
    row = (
        connection.execute(
            select(hosted_import_batches).where(
                hosted_import_batches.c.import_batch_id == import_batch_id
            )
        )
        .mappings()
        .one_or_none()
    )
    return dict(row) if row is not None else None


def _batch_values(
    import_batch_id: str,
    retrieval_job: Mapping[str, Any],
    record_counts: Mapping[str, int],
) -> dict[str, Any]:
    return {
        "import_batch_id": import_batch_id,
        "imported_at": _clean(retrieval_job.get("updated_at"))
        or _clean(retrieval_job.get("created_at")),
        "source_artifact_identity": _clean(retrieval_job.get("source_artifact_identity")),
        "source_pipeline_version": _RETRIEVAL_PIPELINE_VERSION,
        "validation_status": "validated",
        "raw_hash_validation_status": "validated",
        "record_counts": dict(record_counts),
        "warnings": [_REPAIR_WARNING],
        "errors": [],
    }


def _record_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = Counter(_clean(row.get("entity_type")) for row in rows)
    return {
        entity_type: counts.get(entity_type, 0)
        for entity_type in SOURCE_DERIVED_ENTITY_TYPES
    }


def _mapping(value: object) -> Mapping[str, Any]:
    return cast(Mapping[str, Any], value) if isinstance(value, Mapping) else {}


def _clean(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())
