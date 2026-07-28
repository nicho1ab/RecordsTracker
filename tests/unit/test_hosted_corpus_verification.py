from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from jsonschema import ValidationError
from sqlalchemy import create_engine, select, update

from ccld_complaints.cli import verify_hosted_corpus
from ccld_complaints.hosted_app.corpus_verification import (
    _provenance,
    _synthetic_records,
    run_hosted_corpus_verification,
    validate_corpus_verification_result,
    write_corpus_verification_result,
)
from ccld_complaints.hosted_app.seeded_import import (
    hosted_import_batches,
    hosted_seeded_import_metadata,
    hosted_source_derived_records,
    import_seeded_corpus_artifact,
    load_seeded_corpus_artifact,
)
from ccld_complaints.hosted_app.source_derived_reads import (
    ImportBatchRead,
    SourceDerivedRecordRead,
)

FIXTURE = Path("tests/fixtures/hosted_seeded_corpus/validated_seeded_corpus.json")


def test_successful_audit_result_uses_read_model_and_schema(tmp_path: Path) -> None:
    engine = _prepared_engine(extra_pair=True)
    with engine.begin() as connection:
        result = run_hosted_corpus_verification(
            connection,
            deployed_sha="a" * 40,
            environ={"CCLD_HOSTED_PAGE_DATA_MODE": "postgres"},
            now=datetime(2026, 7, 28, tzinfo=UTC),
        )
    validate_corpus_verification_result(result)
    output = tmp_path / "audit.json"
    digest = write_corpus_verification_result(output, result)
    assert len(digest) == 64
    assert json.loads(output.read_text(encoding="utf-8"))["blocking_failures"] == []
    assert result["counts"]["read_model_facility_count"] == 2
    assert result["reviewer_state_separation"]["mutation_performed"] is False


@pytest.mark.parametrize(
    ("mutation", "expected_failure"),
    (
        ("facility_count", "facility_count_mismatch"),
        ("duplicate_facility", "duplicate_or_repeated_identity"),
        ("duplicate_complaint", "duplicate_or_repeated_identity"),
        ("missing_source", "source_document_linkage_failure"),
        ("synthetic", "synthetic_records_detected"),
        ("fallback", "fallback_provenance_detected"),
        ("missing_provenance", "missing_provenance"),
    ),
)
def test_audit_detects_blocking_corpus_conditions(mutation: str, expected_failure: str) -> None:
    engine = _prepared_engine(extra_pair=True)
    with engine.begin() as connection:
        if mutation == "facility_count":
            connection.execute(
                hosted_source_derived_records.delete().where(
                    hosted_source_derived_records.c.entity_type == "facility",
                    hosted_source_derived_records.c.source_record_key
                    == "facility:ccld:facility:extra",
                )
            )
        elif mutation == "duplicate_facility":
            _duplicate(connection, "facility", "facility:ccld:facility:duplicate")
        elif mutation == "duplicate_complaint":
            _duplicate(connection, "complaint", "complaint:ccld:complaint:duplicate")
        elif mutation == "missing_source":
            connection.execute(
                update(hosted_source_derived_records)
                .where(hosted_source_derived_records.c.entity_type == "complaint")
                .values(source_document_id="missing:document")
            )
        elif mutation == "synthetic":
            connection.execute(
                update(hosted_source_derived_records)
                .where(
                    hosted_source_derived_records.c.source_record_key
                    == "facility:ccld:facility:extra"
                )
                .values(
                    stable_source_id="ccld:facility:900000001",
                    original_values={
                        "facility_id": "ccld:facility:900000001",
                        "external_facility_number": "900000001",
                    },
                )
            )
        elif mutation == "fallback":
            connection.execute(
                update(hosted_import_batches).values(source_artifact_identity="fixture-corpus")
            )
        elif mutation == "missing_provenance":
            connection.execute(
                update(hosted_source_derived_records)
                .where(hosted_source_derived_records.c.entity_type == "complaint")
                .values(raw_sha256="not-a-hash")
            )
        result = run_hosted_corpus_verification(
            connection,
            deployed_sha="b" * 40,
            environ={"CCLD_HOSTED_PAGE_DATA_MODE": "postgres"},
        )
    assert expected_failure in result["blocking_failures"]


@pytest.mark.parametrize(
    ("facility_number", "facility_name"),
    (
        ("100406223", "Public Test Services"),
        ("107207223", "Sampletown Child Care"),
        ("198209668", "Emergency Learning Center"),
        ("198209740", "Mockingbird Child Care"),
    ),
)
def test_public_looking_flagged_id_reproduction_does_not_scan_facility_name(
    facility_number: str, facility_name: str
) -> None:
    """Local reproductions use redacted stand-in names, not production-row values."""
    record = _record(
        source_record_key=f"facility:ccld-facility-{facility_number}",
        stable_source_id=f"ccld-facility-{facility_number}",
        original_values={
            "facility_id": f"ccld:facility:{facility_number}",
            "external_facility_number": facility_number,
            "facility_name": facility_name,
        },
    )

    assert _synthetic_records((record,)) == []


@pytest.mark.parametrize(
    ("field", "value", "expected_field"),
    (
        ("external_facility_number", "900000001", "original_values.external_facility_number"),
        ("facility_number", "900000002", "original_values.facility_number"),
        ("facility_id", "CCLD:FACILITY:900000001", "original_values.facility_id"),
    ),
)
def test_known_synthetic_facility_identity_is_blocking_with_exact_reason(
    field: str, value: str, expected_field: str
) -> None:
    record = _record(original_values={field: value})

    assert _synthetic_records((record,)) == [
        {
            "record_key": "facility:ccld-facility-200000001",
            "reason": "known synthetic facility identity",
            "field": expected_field,
            "marker": value.rsplit(":", maxsplit=1)[-1].casefold(),
        }
    ]


@pytest.mark.parametrize(
    ("source_artifact_identity", "source_pipeline_version", "connector_name", "field", "marker"),
    (
        (
            "tests/fixtures/hosted_seeded_corpus/validated_seeded_corpus.json",
            "live-pipeline",
            "ccld_facility_reports",
            "import_batch.source_artifact_identity",
            "tests",
        ),
        (
            "governed-corpus.json",
            "DEMO-pipeline",
            "ccld_facility_reports",
            "import_batch.source_pipeline_version",
            "demo",
        ),
        (
            "governed-corpus.json",
            "live-pipeline",
            "ccld-MOCK-reports",
            "connector_name",
            "mock",
        ),
        (
            "governed-corpus.json",
            "TEST-pipeline",
            "ccld_facility_reports",
            "import_batch.source_pipeline_version",
            "test",
        ),
        (
            "synthetic-corpus.json",
            "live-pipeline",
            "ccld_facility_reports",
            "import_batch.source_artifact_identity",
            "synthetic",
        ),
        (
            "emergency-fallback.json",
            "live-pipeline",
            "ccld_facility_reports",
            "import_batch.source_artifact_identity",
            "emergency",
        ),
    ),
)
def test_governed_fixture_demo_and_fallback_provenance_remains_blocking(
    source_artifact_identity: str,
    source_pipeline_version: str,
    connector_name: str,
    field: str,
    marker: str,
) -> None:
    record = _record(
        source_artifact_identity=source_artifact_identity,
        source_pipeline_version=source_pipeline_version,
        connector_name=connector_name,
    )

    assert _provenance((record,))["fallback_markers"] == [
        {
            "record_key": "facility:ccld-facility-200000001",
            "reason": "governed provenance marker",
            "field": field,
            "marker": marker,
        }
    ]


def test_marker_substrings_in_public_values_do_not_become_provenance_or_audit_output() -> None:
    record = _record(
        source_artifact_identity="contest-results.json",
        source_pipeline_version="testimony-pipeline",
        connector_name="ccld-testament-reports",
        original_values={"facility_name": "Contest Testimony Center"},
    )

    provenance = _provenance((record,))

    assert _synthetic_records((record,)) == []
    assert provenance["fallback_markers"] == []


def test_provenance_reason_redacts_the_source_value() -> None:
    sensitive_fragment = "token" + "=not-for-audit-output"
    record = _record(source_artifact_identity=f"fixture-{sensitive_fragment}")

    serialized = json.dumps(_provenance((record,)), sort_keys=True)

    assert "fixture" in serialized
    assert "token" + "=" not in serialized
    assert "not-for-audit-output" not in serialized


def test_fixture_demo_and_tiny_corpus_are_failures() -> None:
    engine = _prepared_engine(extra_pair=False)
    with engine.begin() as connection:
        result = run_hosted_corpus_verification(
            connection,
            deployed_sha=None,
            environ={
                "CCLD_HOSTED_PAGE_DATA_MODE": "fixture-demo",
                "CCLD_RETRIEVAL_DEMO_MODE": "mock-success",
            },
        )
    assert "page_data_mode_not_postgres" in result["blocking_failures"]
    assert "implausibly_small_corpus" in result["blocking_failures"]
    assert result["retrieval_mode"]["fallback_or_demo_active"] is True


def test_docker_build_contract_includes_audit_source_and_schema() -> None:
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    assert "COPY schemas ./schemas" in dockerfile
    assert "COPY src ./src" in dockerfile
    assert Path("src/ccld_complaints/cli/verify_hosted_corpus.py").is_file()
    assert Path("schemas/hosted-corpus-verification-v1.schema.json").is_file()


def test_schema_rejects_missing_contract_field() -> None:
    engine = _prepared_engine(extra_pair=True)
    with engine.begin() as connection:
        result = run_hosted_corpus_verification(
            connection, deployed_sha="c" * 40, environ={"CCLD_HOSTED_PAGE_DATA_MODE": "postgres"}
        )
    result.pop("provenance")
    with pytest.raises(ValidationError):
        validate_corpus_verification_result(result)


def test_cli_writes_result_and_returns_nonzero_for_blocking_audit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    engine = _prepared_engine(extra_pair=False)

    class _Config:
        database_url = "postgresql+psycopg://ignored/example"

    monkeypatch.setattr(verify_hosted_corpus, "load_hosted_database_config", lambda **_: _Config())
    monkeypatch.setattr(verify_hosted_corpus, "create_engine", lambda _: engine)
    output = tmp_path / "blocking.json"
    assert verify_hosted_corpus.main(["--output", str(output)]) == 1
    assert output.is_file()


def _record(
    *,
    source_record_key: str = "facility:ccld-facility-200000001",
    stable_source_id: str = "ccld-facility-200000001",
    original_values: dict[str, object] | None = None,
    source_artifact_identity: str = "governed-corpus.json",
    source_pipeline_version: str | None = "live-pipeline",
    connector_name: str = "ccld_facility_reports",
) -> SourceDerivedRecordRead:
    return SourceDerivedRecordRead(
        source_record_key=source_record_key,
        entity_type="facility",
        stable_source_id=stable_source_id,
        source_document_id="ccld-document-200000001",
        facility_id="ccld:facility:200000001",
        source_url="https://example.invalid/public-source",
        raw_sha256="a" * 64,
        raw_path=None,
        connector_name=connector_name,
        connector_version="1",
        retrieved_at="2026-07-28T00:00:00Z",
        original_values=original_values or {"facility_number": "200000001"},
        source_traceability={},
        import_batch=ImportBatchRead(
            import_batch_id="governed-corpus",
            imported_at="2026-07-28T00:00:00Z",
            source_artifact_identity=source_artifact_identity,
            source_pipeline_version=source_pipeline_version,
            validation_status="validated",
            raw_hash_validation_status="validated",
            record_counts={},
            warnings=(),
            errors=(),
        ),
    )


def _prepared_engine(*, extra_pair: bool) -> object:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)
    artifact = load_seeded_corpus_artifact(FIXTURE)
    with engine.begin() as connection:
        import_seeded_corpus_artifact(connection, artifact)
        connection.execute(
            update(hosted_import_batches).values(
                source_artifact_identity="governed-corpus.json",
                source_pipeline_version="governed-pipeline-v1",
            )
        )
        if extra_pair:
            _duplicate(
                connection,
                "facility",
                "facility:ccld:facility:extra",
                unique_identity=True,
            )
            _duplicate(
                connection,
                "complaint",
                "complaint:ccld:complaint:extra",
                unique_identity=True,
            )
    return engine


def _duplicate(
    connection: object,
    entity_type: str,
    key: str,
    *,
    unique_identity: bool = False,
) -> None:
    row = connection.execute(
        select(hosted_source_derived_records).where(
            hosted_source_derived_records.c.entity_type == entity_type
        )
    ).mappings().first()
    assert row is not None
    values = dict(row)
    values["source_record_key"] = key
    values["stable_source_id"] = key.removeprefix(f"{entity_type}:")
    if unique_identity:
        original_values = copy.deepcopy(values["original_values"])
        if entity_type == "facility":
            values["facility_id"] = "ccld:facility:extra"
            original_values["facility_id"] = "ccld:facility:extra"
            original_values["facility_number"] = "200000002"
        else:
            values["facility_id"] = "ccld:facility:extra"
            original_values["complaint_id"] = "extra-complaint"
            original_values["facility_id"] = "ccld:facility:extra"
            original_values["facility_number"] = "200000002"
        values["original_values"] = original_values
    connection.execute(hosted_source_derived_records.insert().values(**values))


def test_operator_documentation_keeps_required_safeguards() -> None:
    document = Path("docs/developer/hosted-corpus-verification.md").read_text(encoding="utf-8")
    for marker in (
        "standalone SSH session",
        "/share/Public/RecordsTracker-staging/issue-419/",
        "host `/tmp`",
        "copied unchanged",
        "reused unchanged",
        "Issue #635",
    ):
        assert marker in document
