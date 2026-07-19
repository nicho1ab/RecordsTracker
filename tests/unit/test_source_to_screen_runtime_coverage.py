from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.engine import Connection

from ccld_complaints import source_to_screen_audit as audit
from ccld_complaints.hosted_app.seeded_import import (
    hosted_import_batches,
    hosted_seeded_import_metadata,
    hosted_source_derived_records,
    import_seeded_corpus_artifact,
    load_seeded_corpus_artifact,
)
from ccld_complaints.operator_coverage_runtime_verify import verify_runtime_coverage
from ccld_complaints.source_to_screen_coverage import (
    load_validated_coverage_package,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SEEDED_FIXTURE = Path(
    "tests/fixtures/hosted_seeded_corpus/validated_seeded_corpus.json"
)
FIXED_TIME = datetime(2026, 7, 19, 20, 0, 0, tzinfo=UTC)


def test_runtime_adapter_selects_only_and_publishes_valid_partial_package(
    tmp_path: Path,
) -> None:
    engine = create_engine("sqlite://")
    statements: list[str] = []
    with engine.connect() as connection:
        _seed_runtime(connection)
        structural = audit.run_audit(
            mode="runtime",
            output_dir=tmp_path / "runtime-audit",
            repo_root=REPO_ROOT,
            runtime_connection=connection,
            generated_at=FIXED_TIME,
        )
        before = _database_counts(connection)

        def record_statement(
            _connection: Any,
            _cursor: Any,
            statement: str,
            _parameters: Any,
            _context: Any,
            _executemany: bool,
        ) -> None:
            statements.append(statement)

        event.listen(engine, "before_cursor_execute", record_statement)
        package = audit.publish_runtime_coverage_package(
            connection,
            structural,
            output_dir=tmp_path / "runtime-current",
            repo_root=REPO_ROOT,
            generated_at=FIXED_TIME,
        )
        verification = verify_runtime_coverage(
            package_dir=tmp_path / "runtime-current",
            connection=connection,
        )
        event.remove(engine, "before_cursor_execute", record_statement)
        after = _database_counts(connection)

    validated = load_validated_coverage_package(tmp_path / "runtime-current")
    status = json.loads(
        (tmp_path / "runtime-current-generation-status.json").read_text(
            encoding="utf-8"
        )
    )
    serialized = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((tmp_path / "runtime-current").iterdir())
    ).casefold()

    assert before == after
    assert statements
    assert all(
        statement.lstrip().upper().startswith(("SELECT", "WITH", "PRAGMA"))
        for statement in statements
    )
    assert package.report_id == validated.report["report_id"]
    assert verification["status"] == "passed"
    assert verification["database_mutations_performed"] is False
    assert validated.state == "partial"
    assert validated.facility_rows[0]["facility_id"] == "157806098"
    assert validated.job_rows == ()
    assert "operator_job_index" in validated.unavailable_dimensions
    assert "statewide_completeness_baseline" in validated.unavailable_dimensions
    assert status == {
        "recorded_at": "2026-07-19T20:00:00Z",
        "report_id": package.report_id,
        "status": "published",
    }
    for prohibited in (
        "a. miriam jamison",
        "32-cr-20220407124448",
        "facility clients are being mistreated",
        "https://",
        "tests/fixtures/ccld/raw",
        "authorization",
        "cookie",
        "provider_subject",
        "postgresql://",
        "strtp",
    ):
        assert prohibited not in serialized


def test_runtime_publication_preserves_previous_package_on_failure_and_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite://")
    current = tmp_path / "runtime-current"
    with engine.connect() as connection:
        _seed_runtime(connection)
        structural = audit.run_audit(
            mode="runtime",
            output_dir=tmp_path / "runtime-audit",
            repo_root=REPO_ROOT,
            runtime_connection=connection,
            generated_at=FIXED_TIME,
        )
        first = audit.publish_runtime_coverage_package(
            connection,
            structural,
            output_dir=current,
            repo_root=REPO_ROOT,
            generated_at=FIXED_TIME,
        )
        first_bytes = _tree_bytes(current)
        real_generate = audit.generate_coverage_package

        def fail_generation(*_args: Any, **_kwargs: Any) -> Any:
            raise audit.CoverageContractError("controlled generation failure")

        monkeypatch.setattr(audit, "generate_coverage_package", fail_generation)
        with pytest.raises(audit.CoverageContractError, match="controlled"):
            audit.publish_runtime_coverage_package(
                connection,
                structural,
                output_dir=current,
                repo_root=REPO_ROOT,
                generated_at=FIXED_TIME,
            )
        assert _tree_bytes(current) == first_bytes
        failure_status = json.loads(
            (tmp_path / "runtime-current-generation-status.json").read_text(
                encoding="utf-8"
            )
        )
        assert failure_status["status"] == "generation_failed"

        monkeypatch.setattr(audit, "generate_coverage_package", real_generate)
        second = audit.publish_runtime_coverage_package(
            connection,
            structural,
            output_dir=current,
            repo_root=REPO_ROOT,
            generated_at=datetime(2026, 7, 19, 20, 1, 0, tzinfo=UTC),
        )

    archives = tuple((tmp_path / "runtime-current-instances").iterdir())
    assert second.report_id == first.report_id
    assert len(archives) == 1
    assert _tree_bytes(archives[0]) == first_bytes
    assert load_validated_coverage_package(current).report["generated_at"] == (
        "2026-07-19T20:01:00Z"
    )


def test_runtime_publication_lock_prevents_concurrent_generation(tmp_path: Path) -> None:
    engine = create_engine("sqlite://")
    current = tmp_path / "runtime-current"
    lock_path = tmp_path / ".runtime-current.lock"
    with engine.connect() as connection:
        _seed_runtime(connection)
        structural = audit.run_audit(
            mode="runtime",
            output_dir=tmp_path / "runtime-audit",
            repo_root=REPO_ROOT,
            runtime_connection=connection,
            generated_at=FIXED_TIME,
        )
        lock_path.write_text("active", encoding="utf-8")
        with pytest.raises(audit.CoverageContractError, match="already active"):
            audit.publish_runtime_coverage_package(
                connection,
                structural,
                output_dir=current,
                repo_root=REPO_ROOT,
                generated_at=FIXED_TIME,
            )
    assert not current.exists()


def test_runtime_cli_exposes_exact_coverage_output_option() -> None:
    arguments = audit.build_parser().parse_args(
        [
            "--mode",
            "runtime",
            "--output-dir",
            "/app/data/processed/source-to-screen-audit/runtime-audit",
            "--coverage-output-dir",
            "/app/data/processed/source-to-screen-audit/runtime-current",
        ]
    )
    assert arguments.mode == "runtime"
    assert arguments.coverage_output_dir == Path(
        "/app/data/processed/source-to-screen-audit/runtime-current"
    )


def _seed_runtime(connection: Connection) -> None:
    hosted_seeded_import_metadata.create_all(connection)
    import_seeded_corpus_artifact(
        connection,
        load_seeded_corpus_artifact(SEEDED_FIXTURE),
    )
    connection.commit()


def _database_counts(connection: Connection) -> tuple[int, int]:
    return (
        int(connection.scalar(select(func.count()).select_from(hosted_import_batches)) or 0),
        int(
            connection.scalar(
                select(func.count()).select_from(hosted_source_derived_records)
            )
            or 0
        ),
    )


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }
