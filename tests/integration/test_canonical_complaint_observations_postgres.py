from __future__ import annotations

import copy
import os
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import Connection

from ccld_complaints.canonical_allocation_evidence import run_evidence
from ccld_complaints.connectors.base import SourceDocument
from ccld_complaints.connectors.ccld import CcldFacilityReportsConnector
from ccld_complaints.hosted_app.facility_reference_preload import (
    hosted_facility_reference_metadata,
)
from ccld_complaints.hosted_app.reviewer_created_state import (
    hosted_reviewer_created_state,
)
from ccld_complaints.hosted_app.seeded_import import (
    SeededCorpusArtifact,
    hosted_seeded_import_metadata,
    hosted_source_derived_records,
    import_seeded_corpus_artifact,
)
from ccld_complaints.utils.hash import sha256_bytes

POSTGRES_TEST_URL_ENV = "CCLD_TEST_POSTGRES_URL"
POSTGRES_SCHEMA_MUTATION_ENV = "CCLD_TEST_POSTGRES_ALLOW_SCHEMA_MUTATION"
RAW_FIXTURE = Path(
    "tests/fixtures/ccld/raw/900000001_inx1_issue574_structured_fields.html"
)
REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def postgres_complaint_connection() -> Iterator[Connection]:
    database_url = os.environ.get(POSTGRES_TEST_URL_ENV, "").strip()
    mutation_allowed = os.environ.get(POSTGRES_SCHEMA_MUTATION_ENV, "").strip() == "1"
    if not database_url or not mutation_allowed:
        pytest.skip(
            f"Set {POSTGRES_TEST_URL_ENV} and {POSTGRES_SCHEMA_MUTATION_ENV}=1 "
            "to run the isolated PostgreSQL complaint-observation regression."
        )
    if not database_url.startswith("postgresql+"):
        pytest.fail(f"{POSTGRES_TEST_URL_ENV} must use a PostgreSQL SQLAlchemy URL.")

    schema_name = f"issue447_complaint_{uuid.uuid4().hex}"
    engine = sa.create_engine(database_url)
    with engine.connect() as connection:
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema_name}"')
        connection.exec_driver_sql(f'SET search_path TO "{schema_name}"')
        hosted_seeded_import_metadata.create_all(connection)
        hosted_facility_reference_metadata.create_all(connection)
        connection.commit()
        try:
            yield connection
        finally:
            connection.rollback()
            connection.exec_driver_sql("SET search_path TO public")
            connection.exec_driver_sql(f'DROP SCHEMA "{schema_name}" CASCADE')
            connection.commit()
    engine.dispose()


def test_postgres_complaint_observations_refresh_without_reviewer_state_loss(
    postgres_complaint_connection: Connection,
    tmp_path: Path,
) -> None:
    connection = postgres_complaint_connection
    record = _normalized_record()
    populated = _artifact("initial", record)
    first = import_seeded_corpus_artifact(connection, populated)
    complaint_key = connection.execute(
        sa.select(hosted_source_derived_records.c.source_record_key).where(
            hosted_source_derived_records.c.entity_type == "complaint"
        )
    ).scalar_one()
    connection.execute(
        hosted_reviewer_created_state.insert().values(
            reviewer_state_id="issue447-reviewer-state",
            source_record_key=complaint_key,
            scope_type="seeded_corpus",
            scope_id=populated.import_batch_id,
            state_kind="review_item_state_scaffold",
            state_payload={
                "payload_kind": "reviewer_status_scaffold",
                "reviewer_status": "in_review",
            },
            created_at="2026-07-23T00:00:00+00:00",
            created_by_provider_subject="fixture-reviewer",
            created_by_provider_issuer="fixture-provider",
            created_by_display_name="Fixture Reviewer",
            created_by_actor_category="reviewer",
            authorization_permission="reviewer_state_write",
        )
    )
    connection.commit()

    changed_record = copy.deepcopy(record)
    changed_complaint = cast(dict[str, Any], changed_record["complaint"])
    changed_complaint.update(
        {
            "agency_name": "Changed governed agency",
            "deficiency_texts": ["Changed first", "Changed second"],
            "investigation_findings_narrative": "Changed governed narrative.",
            "complaint_report_contact": "(555) 010-2222",
        }
    )
    changed = import_seeded_corpus_artifact(
        connection,
        _artifact("changed", changed_record),
        preserve_existing_import_batch=True,
    )
    repeated = import_seeded_corpus_artifact(
        connection,
        _artifact("changed", changed_record),
        preserve_existing_import_batch=True,
    )
    connection.commit()

    complaint = (
        connection.execute(
            sa.select(hosted_source_derived_records).where(
                hosted_source_derived_records.c.entity_type == "complaint"
            )
        )
        .mappings()
        .one()
    )
    reviewer_state_count = connection.scalar(
        sa.select(sa.func.count()).select_from(hosted_reviewer_created_state)
    )
    evidence_manifest = run_evidence(
        mode="runtime",
        output_dir=tmp_path / "aggregate-evidence",
        repo_root=REPO_ROOT,
        runtime_connection=connection,
    )

    assert first.inserted_record_count > 0
    assert changed.conflicted_field_count == 4
    assert repeated.conflicted_field_count == 0
    assert complaint["agency_name"] == "Changed governed agency"
    assert complaint["deficiency_texts"] == ["Changed first", "Changed second"]
    assert complaint["investigation_findings_narrative"] == (
        "Changed governed narrative."
    )
    assert complaint["complaint_report_contact"] == "(555) 010-2222"
    assert reviewer_state_count == 1
    assert all(evidence_manifest["assertions"].values())
    assert evidence_manifest["runtime_population"]["hosted_source_derived"][
        "status"
    ] == "inspected aggregate-only"


def _normalized_record() -> dict[str, object]:
    content = RAW_FIXTURE.read_bytes()
    connector = CcldFacilityReportsConnector()
    return connector.normalize(
        connector.extract(
            SourceDocument(
                source_url=(
                    "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports"
                    "?facNum=900000001&inx=1"
                ),
                raw_path=RAW_FIXTURE,
                raw_sha256=sha256_bytes(content),
                retrieved_at="2026-07-23T00:00:00+00:00",
                content_type="text/html",
            )
        )
    )


def _artifact(name: str, record: dict[str, object]) -> SeededCorpusArtifact:
    return SeededCorpusArtifact(
        import_batch_id=f"issue447-{name}",
        imported_at="2026-07-23T00:00:00+00:00",
        source_artifact_identity=f"issue447:{name}",
        source_pipeline_version="test",
        validation_status="validated",
        raw_hash_validation_status="validated",
        record_counts={},
        warnings=(),
        errors=(),
        records=(record,),
    )
