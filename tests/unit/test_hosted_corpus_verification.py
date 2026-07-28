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
                .values(stable_source_id="synthetic-facility")
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
