from __future__ import annotations

from pathlib import Path

import pytest

from ccld_complaints.hosted_app.persistence import (
    DATABASE_PRODUCT,
    DATABASE_URL_ENV,
    MIGRATION_TOOL,
    HostedDatabaseConfigError,
    hosted_persistence_boundaries,
    load_hosted_database_config,
    missing_required_persistence_boundaries,
    redact_database_url,
    validate_postgresql_database_url,
)
from ccld_complaints.hosted_app.schema_api_scaffold import (
    build_hosted_schema_api_scaffold,
    hosted_api_boundaries,
)


def test_hosted_database_config_is_safe_when_unset() -> None:
    config = load_hosted_database_config(environ={}, project_root=Path("<repo-root>"))

    assert config.configured is False
    assert config.safe_database_url == "<unset>"
    assert config.database_url_env == DATABASE_URL_ENV
    assert config.database_product == DATABASE_PRODUCT
    assert config.migration_tool == MIGRATION_TOOL
    assert config.alembic_config_path == Path("<repo-root>") / "alembic.ini"
    assert config.migration_script_location == Path("<repo-root>") / "migrations"


def test_hosted_database_config_accepts_postgresql_url_without_printing_it() -> None:
    raw_url = "postgresql+psycopg://db.example.invalid:5432/ccld_tester"
    config = load_hosted_database_config(environ={DATABASE_URL_ENV: raw_url})

    assert config.configured is True
    assert config.database_url == raw_url
    assert config.safe_database_url == "postgresql+psycopg://<redacted-host>/<redacted-database>"
    assert "db.example.invalid" not in config.safe_database_url
    assert "ccld_tester" not in config.safe_database_url


def test_hosted_database_config_rejects_non_postgresql_urls() -> None:
    with pytest.raises(HostedDatabaseConfigError, match="PostgreSQL"):
        validate_postgresql_database_url("sqlite:///local.db")

    with pytest.raises(HostedDatabaseConfigError, match="database name"):
        validate_postgresql_database_url("postgresql://db.example.invalid")


def test_hosted_database_config_can_require_url_for_migration_runs() -> None:
    with pytest.raises(HostedDatabaseConfigError, match=DATABASE_URL_ENV):
        load_hosted_database_config(environ={}, require_url=True)


def test_redacted_database_url_does_not_expose_connection_details() -> None:
    redacted = redact_database_url("postgresql://db.example.invalid:5432/private_db")

    assert redacted == "postgresql://<redacted-host>/<redacted-database>"
    assert "db.example.invalid" not in redacted
    assert "private_db" not in redacted


def test_persistence_boundaries_cover_required_adr_0010_table_groups() -> None:
    boundaries = hosted_persistence_boundaries()
    boundary_by_id = {boundary.boundary_id: boundary for boundary in boundaries}

    assert missing_required_persistence_boundaries() == frozenset()
    assert boundary_by_id["source_derived_records"].domain == "source-derived"
    assert boundary_by_id["reviewer_created_state"].domain == "reviewer-created"
    assert "source URL" in boundary_by_id["source_derived_records"].preserves
    assert "raw SHA-256 hash" in boundary_by_id["source_derived_records"].preserves
    assert "authenticated actor attribution" in boundary_by_id[
        "reviewer_created_state"
    ].preserves
    assert "overwrite source-derived canonical values" in boundary_by_id[
        "reviewer_created_state"
    ].must_not


def test_api_boundaries_keep_source_records_and_reviewer_state_separate() -> None:
    api_boundaries = hosted_api_boundaries()
    boundary_by_id = {boundary.boundary_id: boundary for boundary in api_boundaries}

    assert set(boundary_by_id) == {
        "auth_provider_integration_plan_api",
        "source_derived_records_api",
        "reviewer_created_state_api",
        "audit_events_api",
        "audit_coverage_plan_api",
        "seeded_corpus_reset_reload_operations_api",
    }
    assert boundary_by_id["auth_provider_integration_plan_api"].domain == "auth"
    assert "managed OpenID Connect/OAuth 2.0 provider integration" in boundary_by_id[
        "auth_provider_integration_plan_api"
    ].intended_future_use
    assert "non-secret configuration readiness inputs" in boundary_by_id[
        "auth_provider_integration_plan_api"
    ].preserves
    assert "real login flow" in boundary_by_id[
        "auth_provider_integration_plan_api"
    ].deferred
    assert "token exchange or validation" in boundary_by_id[
        "auth_provider_integration_plan_api"
    ].deferred
    assert boundary_by_id["source_derived_records_api"].domain == "source-derived"
    assert boundary_by_id["reviewer_created_state_api"].domain == "reviewer-created"
    assert "controlled snapshot imports from validated pipeline output" in boundary_by_id[
        "source_derived_records_api"
    ].intended_future_use
    assert boundary_by_id[
        "reviewer_created_state_api"
    ].requires_authenticated_actor_before_write is True
    assert "auth middleware" in boundary_by_id["reviewer_created_state_api"].deferred
    assert "listing or fetching those rows" in boundary_by_id[
        "reviewer_created_state_api"
    ].intended_future_use
    assert "workflow-shell note action" in boundary_by_id[
        "reviewer_created_state_api"
    ].intended_future_use
    assert "status action" in boundary_by_id[
        "reviewer_created_state_api"
    ].intended_future_use
    assert "read-only access to persisted reviewer-created scaffold rows" in boundary_by_id[
        "reviewer_created_state_api"
    ].preserves
    assert "bounded reviewer status payloads under the existing state kind" in boundary_by_id[
        "reviewer_created_state_api"
    ].preserves
    assert any(
        "workflow-shell source-record binding" in preserved
        for preserved in boundary_by_id["reviewer_created_state_api"].preserves
    )
    assert "production API framework" in boundary_by_id[
        "source_derived_records_api"
    ].deferred
    assert "stateful reviewer workflows" in boundary_by_id[
        "reviewer_created_state_api"
    ].deferred
    assert boundary_by_id["audit_events_api"].domain == "audit"
    assert "successful reviewer-created state scaffold writes" in boundary_by_id[
        "audit_events_api"
    ].intended_future_use
    assert "listing or fetching those rows" in boundary_by_id[
        "audit_events_api"
    ].intended_future_use
    assert "production audit API framework" in boundary_by_id[
        "audit_events_api"
    ].deferred
    assert "full audit policy coverage" in boundary_by_id["audit_events_api"].deferred
    assert boundary_by_id["audit_coverage_plan_api"].domain == "audit"
    assert "summarizes current scaffold audit coverage" in boundary_by_id[
        "audit_coverage_plan_api"
    ].intended_future_use
    assert "no-persistence planning behavior" in boundary_by_id[
        "audit_coverage_plan_api"
    ].preserves
    assert "new audit event write behavior" in boundary_by_id[
        "audit_coverage_plan_api"
    ].deferred
    assert "audit schema changes or migrations" in boundary_by_id[
        "audit_coverage_plan_api"
    ].deferred
    assert boundary_by_id["seeded_corpus_reset_reload_operations_api"].domain == (
        "operational"
    )
    assert "dry-run route seam" in boundary_by_id[
        "seeded_corpus_reset_reload_operations_api"
    ].intended_future_use
    assert "execution-plan route seam" in boundary_by_id[
        "seeded_corpus_reset_reload_operations_api"
    ].intended_future_use
    assert "operational planning metadata" in boundary_by_id[
        "seeded_corpus_reset_reload_operations_api"
    ].intended_future_use
    assert "list or fetch those persisted planning records" in boundary_by_id[
        "seeded_corpus_reset_reload_operations_api"
    ].intended_future_use
    assert "read-only access to persisted planning metadata" in boundary_by_id[
        "seeded_corpus_reset_reload_operations_api"
    ].preserves
    assert "ordered non-destructive execution-plan steps" in boundary_by_id[
        "seeded_corpus_reset_reload_operations_api"
    ].preserves
    assert "destructive reset execution" in boundary_by_id[
        "seeded_corpus_reset_reload_operations_api"
    ].deferred
    assert "production reset/reload operational framework" in boundary_by_id[
        "seeded_corpus_reset_reload_operations_api"
    ].deferred
    assert "database-backed API reads" not in boundary_by_id[
        "source_derived_records_api"
    ].deferred


def test_schema_api_scaffold_summary_reflects_seeded_import_without_reviewer_workflows() -> None:
    scaffold = build_hosted_schema_api_scaffold()

    assert scaffold.domain_tables_created is True
    assert scaffold.auth_boundary_scaffold_implemented is True
    assert scaffold.auth_provider_integration_plan_implemented is True
    assert scaffold.source_derived_read_service_implemented is True
    assert scaffold.source_derived_read_api_routes_implemented is True
    assert scaffold.reviewer_workflow_shell_implemented is True
    assert scaffold.reviewer_workflow_shell_state_read_integration_implemented is True
    assert scaffold.reviewer_workflow_shell_state_filter_search_implemented is True
    assert scaffold.reviewer_workflow_shell_note_action_implemented is True
    assert scaffold.reviewer_workflow_shell_status_action_implemented is True
    assert scaffold.reviewer_ui_shell_implemented is True
    assert scaffold.ccld_facility_lookup_ui_implemented is True
    assert scaffold.ccld_record_request_ui_shell_implemented is True
    assert scaffold.ccld_request_result_queue_guidance_implemented is True
    assert scaffold.ccld_request_queue_status_progress_implemented is True
    assert scaffold.ccld_request_feedback_checklist_implemented is True
    assert scaffold.ccld_validated_import_reload_implemented is True
    assert scaffold.reset_reload_dry_run_implemented is True
    assert scaffold.reset_reload_execution_plan_implemented is True
    assert scaffold.reset_reload_operational_metadata_scaffold_implemented is True
    assert scaffold.reset_reload_planning_metadata_read_api_routes_implemented is True
    assert scaffold.reviewer_created_state_persistence_scaffold_implemented is True
    assert scaffold.reviewer_note_write_route_scaffold_implemented is True
    assert scaffold.reviewer_created_state_read_api_routes_implemented is True
    assert scaffold.reviewer_created_state_read_filter_search_implemented is True
    assert scaffold.audit_coverage_plan_implemented is True
    assert scaffold.audit_event_persistence_scaffold_implemented is True
    assert scaffold.audit_event_read_api_routes_implemented is True
    assert scaffold.api_routes_implemented is True
    assert scaffold.imports_implemented is True
    assert scaffold.reviewer_workflows_implemented is False
    assert scaffold.reset_reload_implemented is False
    assert len(scaffold.persistence_boundaries) >= 7
    assert len(scaffold.api_boundaries) == 6


def test_alembic_scaffold_has_seeded_import_domain_migration_only() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    alembic_ini = repo_root / "alembic.ini"
    migrations_dir = repo_root / "migrations"
    version_files = list((migrations_dir / "versions").glob("*.py"))

    assert alembic_ini.exists()
    assert "sqlalchemy.url =" in alembic_ini.read_text(encoding="utf-8")
    assert (migrations_dir / "env.py").exists()
    assert (migrations_dir / "script.py.mako").exists()
    assert sorted(version_file.name for version_file in version_files) == [
        "20260613_0001_seeded_corpus_import.py",
        "20260614_0002_reviewer_created_state_scaffold.py",
        "20260614_0003_audit_event_scaffold.py",
        "20260614_0004_reset_reload_operational_metadata.py",
    ]
