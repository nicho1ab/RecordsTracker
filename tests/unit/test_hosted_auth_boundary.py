from __future__ import annotations

from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Connection

from ccld_complaints.hosted_app import auth as hosted_auth
from ccld_complaints.hosted_app.auth import (
    AUTH_PROVIDER_CLASS_ENV,
    CCLD_RETRIEVAL_CORPUS_SCOPE,
    IMPORT_RELOAD_PERMISSION,
    MANAGED_OIDC_OAUTH2_PROVIDER_CLASS,
    REVIEWER_STATE_READ_PERMISSION,
    REVIEWER_STATE_WRITE_PERMISSION,
    SOURCE_DERIVED_READ_PERMISSION,
    USER_ROLE_ADMIN_PERMISSION,
    AuthenticatedActor,
    AuthorizationTarget,
    HostedAccessScope,
    HostedAccountDisabledError,
    HostedAccountStatus,
    HostedActorCategory,
    HostedAuthConfigError,
    HostedAuthenticationRequiredError,
    HostedRoleDeniedError,
    HostedScopeDeniedError,
    HostedTesterRole,
    get_authorized_source_derived_record_by_key,
    list_authorized_source_derived_complaint_bundle,
    list_authorized_source_derived_records,
    list_authorized_source_derived_records_by_entity_types,
    load_hosted_auth_config,
    load_hosted_auth_runtime_config,
    require_permission,
)
from ccld_complaints.hosted_app.ccld_retrieval_jobs import retrieval_import_batch_id
from ccld_complaints.hosted_app.seeded_import import (
    hosted_import_batches,
    hosted_seeded_import_metadata,
    hosted_source_derived_records,
    import_seeded_corpus_artifact,
    load_seeded_corpus_artifact,
)

FIXTURE = Path("tests/fixtures/hosted_seeded_corpus/validated_seeded_corpus.json")
TEST_SCOPE = HostedAccessScope("seeded_corpus", "seeded-ccld-fixture-2026-06-13")
OTHER_SCOPE = HostedAccessScope("seeded_corpus", "different-seeded-corpus")
POSTGRES_SCOPE = CCLD_RETRIEVAL_CORPUS_SCOPE
COMPLAINT_KEY = "complaint:ccld:complaint:32-CR-20220407124448"
SOURCE_LIST_TARGET = AuthorizationTarget(
    "source_derived_record_list",
    "seeded-ccld-fixture-2026-06-13",
)
REVIEWER_STATE_TARGET = AuthorizationTarget("reviewer_created_state", "future-review-item")
IMPORT_TARGET = AuthorizationTarget("import_batch", "seeded-ccld-fixture-2026-06-13")
AUTH_TARGET = AuthorizationTarget("auth_access", "future-role-assignment")


def test_hosted_auth_config_is_safe_when_unset() -> None:
    config = load_hosted_auth_config(environ={})

    assert config.configured is False
    assert config.provider_class is None
    assert config.safe_provider_class == "<unset>"
    assert config.provider_class_env == AUTH_PROVIDER_CLASS_ENV
    assert config.required_claims == (
        "sub",
        "iss",
        "roles",
        "scopes",
        "account_status",
    )


def test_hosted_auth_config_accepts_managed_oidc_provider_class_only() -> None:
    config = load_hosted_auth_config(
        environ={AUTH_PROVIDER_CLASS_ENV: MANAGED_OIDC_OAUTH2_PROVIDER_CLASS}
    )

    assert config.configured is True
    assert config.provider_class == "managed-oidc-oauth2"
    assert config.safe_provider_class == "managed-oidc-oauth2"

    with pytest.raises(HostedAuthConfigError, match=AUTH_PROVIDER_CLASS_ENV):
        load_hosted_auth_config(environ={AUTH_PROVIDER_CLASS_ENV: "local-password"})


def test_hosted_auth_config_can_require_provider_class() -> None:
    with pytest.raises(HostedAuthConfigError, match=AUTH_PROVIDER_CLASS_ENV):
        load_hosted_auth_config(environ={}, require_provider_class=True)


def test_hosted_auth_runtime_defaults_to_production_without_local_dev_actor() -> None:
    config = load_hosted_auth_runtime_config(environ={})

    assert config.mode == "production"
    assert config.production_mode is True
    assert config.local_dev_auth_enabled is False
    assert config.local_dev_actor_allowed is False
    assert config.safe_summary["custom_password_storage"] is False
    assert config.safe_summary["real_oidc_flow_implemented"] is False
    assert config.safe_summary["sessions_or_cookies_implemented"] is False


def test_hosted_auth_runtime_allows_explicit_local_dev_actor_mode_only() -> None:
    config = load_hosted_auth_runtime_config(
        environ={
            "CCLD_HOSTED_TESTER_AUTH_MODE": "local-dev",
            "CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH": "enabled",
            AUTH_PROVIDER_CLASS_ENV: MANAGED_OIDC_OAUTH2_PROVIDER_CLASS,
        }
    )

    assert config.mode == "local-dev"
    assert config.provider_class == "managed-oidc-oauth2"
    assert config.local_dev_actor_allowed is True


def test_hosted_auth_runtime_rejects_local_dev_actor_in_production() -> None:
    with pytest.raises(HostedAuthConfigError, match="LOCAL_DEV_AUTH"):
        load_hosted_auth_runtime_config(
            environ={
                "CCLD_HOSTED_TESTER_AUTH_MODE": "production",
                "CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH": "enabled",
            }
        )


def test_hosted_auth_runtime_uses_placeholder_oidc_config_without_echoing_secrets() -> None:
    config = load_hosted_auth_runtime_config(
        environ={
            "CCLD_HOSTED_TESTER_AUTH_MODE": "production",
            AUTH_PROVIDER_CLASS_ENV: MANAGED_OIDC_OAUTH2_PROVIDER_CLASS,
            "CCLD_HOSTED_TESTER_OIDC_ISSUER": "<provider-issuer-placeholder>",
            "CCLD_HOSTED_TESTER_OIDC_CLIENT_ID": "<provider-client-id-placeholder>",
            "CCLD_HOSTED_TESTER_OIDC_CALLBACK_PATH": "/auth/callback",
            "CCLD_HOSTED_TESTER_OIDC_SCOPES": "openid profile",
        }
    )

    assert config.oidc.configured is True
    assert config.oidc.safe_summary == {
        "issuer_configured": True,
        "client_id_configured": True,
        "callback_path": "/auth/callback",
        "scopes": ["openid", "profile"],
    }

    with pytest.raises(HostedAuthConfigError, match="secret-like"):
        load_hosted_auth_runtime_config(
            environ={"CCLD_HOSTED_TESTER_OIDC_CLIENT_ID": "contains-token-value"}
        )


def test_require_permission_returns_audit_ready_context_for_active_actor() -> None:
    actor = _read_only_actor()

    decision = require_permission(
        actor,
        permission=SOURCE_DERIVED_READ_PERMISSION,
        scope=TEST_SCOPE,
        target=SOURCE_LIST_TARGET,
    )

    assert decision.permission == "source_derived_read"
    assert decision.scope == TEST_SCOPE
    assert decision.target == SOURCE_LIST_TARGET
    assert decision.authorized_at.endswith("+00:00")
    assert decision.actor.provider_subject == "fixture-subject-read-only"
    assert decision.actor.provider_issuer == "fixture-managed-oidc-provider"
    assert decision.actor.actor_category == "tester"
    assert decision.actor.account_status == "active"
    assert decision.actor.roles == ("read_only_tester",)
    assert decision.actor.scopes == (TEST_SCOPE,)


def test_require_permission_rejects_unauthenticated_actor() -> None:
    with pytest.raises(HostedAuthenticationRequiredError, match="authenticated actor"):
        require_permission(
            None,
            permission=SOURCE_DERIVED_READ_PERMISSION,
            scope=TEST_SCOPE,
            target=SOURCE_LIST_TARGET,
        )


def test_require_permission_rejects_disabled_actor() -> None:
    with pytest.raises(HostedAccountDisabledError, match="disabled or revoked"):
        require_permission(
            _read_only_actor(account_status="disabled"),
            permission=SOURCE_DERIVED_READ_PERMISSION,
            scope=TEST_SCOPE,
            target=SOURCE_LIST_TARGET,
        )


def test_require_permission_rejects_role_without_required_permission() -> None:
    actor = _actor(roles=(), scopes=(TEST_SCOPE,))

    with pytest.raises(HostedRoleDeniedError, match="source_derived_read"):
        require_permission(
            actor,
            permission=SOURCE_DERIVED_READ_PERMISSION,
            scope=TEST_SCOPE,
            target=SOURCE_LIST_TARGET,
        )


def test_require_permission_rejects_actor_outside_requested_scope() -> None:
    with pytest.raises(HostedScopeDeniedError, match="project or corpus scope"):
        require_permission(
            _read_only_actor(scopes=(OTHER_SCOPE,)),
            permission=SOURCE_DERIVED_READ_PERMISSION,
            scope=TEST_SCOPE,
            target=SOURCE_LIST_TARGET,
        )


def test_read_only_access_does_not_grant_reviewer_or_operator_permissions() -> None:
    actor = _read_only_actor()

    require_permission(
        actor,
        permission=SOURCE_DERIVED_READ_PERMISSION,
        scope=TEST_SCOPE,
        target=SOURCE_LIST_TARGET,
    )
    denied_permissions = (
        (REVIEWER_STATE_WRITE_PERMISSION, REVIEWER_STATE_TARGET),
        (IMPORT_RELOAD_PERMISSION, IMPORT_TARGET),
        (USER_ROLE_ADMIN_PERMISSION, AUTH_TARGET),
    )
    for permission, target in denied_permissions:
        with pytest.raises(HostedRoleDeniedError):
            require_permission(
                actor,
                permission=permission,
                scope=TEST_SCOPE,
                target=target,
            )


def test_source_derived_read_permission_does_not_grant_reviewer_state_read() -> None:
    actor = _actor(
        roles=("developer_operator",),
        scopes=(TEST_SCOPE,),
        actor_category="operator",
    )

    require_permission(
        actor,
        permission=SOURCE_DERIVED_READ_PERMISSION,
        scope=TEST_SCOPE,
        target=SOURCE_LIST_TARGET,
    )

    with pytest.raises(HostedRoleDeniedError, match="reviewer_state_read"):
        require_permission(
            actor,
            permission=REVIEWER_STATE_READ_PERMISSION,
            scope=TEST_SCOPE,
            target=REVIEWER_STATE_TARGET,
        )


def test_authorized_source_derived_read_service_returns_staged_records_only() -> None:
    with _seeded_connection() as connection:
        records = list_authorized_source_derived_records(
            connection,
            _read_only_actor(),
            scope=TEST_SCOPE,
            entity_type="complaint",
        )

    assert len(records) == 1
    assert records[0].entity_type == "complaint"
    assert records[0].import_batch.import_batch_id == TEST_SCOPE.scope_id
    assert records[0].original_values["finding"] == "Unsubstantiated"
    assert "review_status" not in records[0].original_values
    assert "annotation" not in records[0].original_values


def test_postgres_corpus_authorizes_multiple_loaded_retrieval_batches() -> None:
    with _seeded_connection() as connection:
        first_key = _insert_corpus_complaint(
            connection,
            job_id="corpus-job-001",
            facility_number="107207198",
            complaint_control_number="24-CR-20260508083927",
            finding="Substantiated",
        )
        second_key = _insert_corpus_complaint(
            connection,
            job_id="corpus-job-002",
            facility_number="425802141",
            complaint_control_number="31-CR-20240425094018",
            finding="Substantiated",
        )

        records = list_authorized_source_derived_records(
            connection,
            _read_only_actor(scopes=(POSTGRES_SCOPE,)),
            scope=POSTGRES_SCOPE,
            entity_type="complaint",
        )

    keys = {record.source_record_key for record in records}
    assert first_key in keys
    assert second_key in keys
    assert COMPLAINT_KEY not in keys
    assert {
        record.import_batch.import_batch_id
        for record in records
    } == {
        retrieval_import_batch_id("corpus-job-001"),
        retrieval_import_batch_id("corpus-job-002"),
    }


def test_postgres_authorized_batch_query_has_corpus_independent_parameter_shape() -> None:
    query = hosted_auth._authorized_source_import_batch_query(POSTGRES_SCOPE)
    compiled = query.compile(dialect=postgresql.dialect())
    sql = str(compiled).upper()

    assert " UNION " in sql
    assert "HOSTED_CCLD_RETRIEVAL_JOBS" in sql
    assert "HOSTED_IMPORT_BATCHES" in sql
    assert len(compiled.params) <= 6
    assert "POSTCOMPILE" not in sql


def test_postgres_filtered_complaint_bundle_compiles_route_filters_before_reads() -> None:
    connection = MagicMock()
    connection.dialect.name = "postgresql"
    count_result = MagicMock()
    count_result.scalar_one.return_value = 0
    empty_rows = MagicMock()
    empty_rows.mappings.return_value.all.return_value = []
    connection.execute.side_effect = [count_result, empty_rows, empty_rows]

    result = list_authorized_source_derived_complaint_bundle(
        connection,
        _read_only_actor(scopes=(POSTGRES_SCOPE,)),
        scope=POSTGRES_SCOPE,
        facility_number="157806098",
        start_date="2022-08-01",
        end_date="2022-08-31",
    )

    compiled = [
        call.args[0].compile(dialect=postgresql.dialect())
        for call in connection.execute.call_args_list
    ]
    sql_statements = [str(statement).upper() for statement in compiled]
    parameter_values = [
        str(value)
        for statement in compiled
        for value in statement.params.values()
    ]
    assert result.records == ()
    assert len(sql_statements) == 3
    assert all("HOSTED_CCLD_RETRIEVAL_JOBS" in sql for sql in sql_statements)
    assert all(" OFFSET " not in sql for sql in sql_statements)
    assert any("ORDER BY" in sql and "SOURCE_RECORD_KEY" in sql for sql in sql_statements)
    assert "157806098" in parameter_values
    assert "2022-08-01" in parameter_values
    assert "2022-08-31" in parameter_values
    assert sum(len(statement.params) for statement in compiled) < 500


def test_authorized_source_derived_entity_type_bulk_read_preserves_scope() -> None:
    with _seeded_connection() as connection:
        corpus_key = _insert_corpus_complaint(
            connection,
            job_id="corpus-job-entity-bulk",
            facility_number="107207198",
            complaint_control_number="24-CR-20260508083927",
            finding="Substantiated",
        )
        unauthorized_key = _insert_non_corpus_complaint(connection)

        records = list_authorized_source_derived_records_by_entity_types(
            connection,
            _read_only_actor(scopes=(POSTGRES_SCOPE,)),
            scope=POSTGRES_SCOPE,
            entity_types=("complaint", "allegation", "facility", "source_document"),
        )

    keys = {record.source_record_key for record in records}
    assert corpus_key in keys
    assert unauthorized_key not in keys
    assert COMPLAINT_KEY not in keys
    assert {record.entity_type for record in records} == {"complaint"}


def test_postgres_corpus_denies_unauthorized_batch_and_record() -> None:
    with _seeded_connection() as connection:
        unauthorized_key = _insert_non_corpus_complaint(connection)

        with pytest.raises(HostedScopeDeniedError, match="import batch"):
            list_authorized_source_derived_records(
                connection,
                _read_only_actor(scopes=(POSTGRES_SCOPE,)),
                scope=POSTGRES_SCOPE,
                import_batch_id="outside-corpus-batch",
            )

        with pytest.raises(HostedScopeDeniedError, match="source-derived record"):
            get_authorized_source_derived_record_by_key(
                connection,
                _read_only_actor(scopes=(POSTGRES_SCOPE,)),
                scope=POSTGRES_SCOPE,
                source_record_key=unauthorized_key,
            )


def test_authorized_source_derived_fetch_rejects_unauthenticated_actor() -> None:
    with _seeded_connection() as connection:
        with pytest.raises(HostedAuthenticationRequiredError):
            get_authorized_source_derived_record_by_key(
                connection,
                None,
                scope=TEST_SCOPE,
                source_record_key="complaint:ccld:complaint:32-CR-20220407124448",
            )


def test_authorized_source_derived_list_rejects_out_of_scope_actor_before_read() -> None:
    with _seeded_connection() as connection:
        with pytest.raises(HostedScopeDeniedError):
            list_authorized_source_derived_records(
                connection,
                _read_only_actor(scopes=(OTHER_SCOPE,)),
                scope=TEST_SCOPE,
            )


def test_authorized_source_derived_list_rejects_mismatched_import_batch_scope() -> None:
    with _seeded_connection() as connection:
        with pytest.raises(HostedScopeDeniedError, match="import batch"):
            list_authorized_source_derived_records(
                connection,
                _read_only_actor(),
                scope=TEST_SCOPE,
                import_batch_id=OTHER_SCOPE.scope_id,
            )


def test_authorized_source_derived_fetch_rejects_record_outside_requested_scope() -> None:
    with _seeded_connection() as connection:
        with pytest.raises(HostedScopeDeniedError, match="source-derived record"):
            get_authorized_source_derived_record_by_key(
                connection,
                _read_only_actor(scopes=(OTHER_SCOPE,)),
                scope=OTHER_SCOPE,
                source_record_key="complaint:ccld:complaint:32-CR-20220407124448",
            )


def test_admin_scope_is_still_required_for_source_derived_reads() -> None:
    with _seeded_connection() as connection:
        with pytest.raises(HostedScopeDeniedError):
            list_authorized_source_derived_records(
                connection,
                _actor(roles=("admin",), scopes=(OTHER_SCOPE,), actor_category="admin"),
                scope=TEST_SCOPE,
            )


def _read_only_actor(
    *,
    account_status: str = "active",
    scopes: tuple[HostedAccessScope, ...] = (TEST_SCOPE,),
) -> AuthenticatedActor:
    return _actor(
        roles=("read_only_tester",),
        scopes=scopes,
        account_status=account_status,
    )


def _actor(
    *,
    roles: tuple[str, ...],
    scopes: tuple[HostedAccessScope, ...],
    account_status: str = "active",
    actor_category: str = "tester",
) -> AuthenticatedActor:
    return AuthenticatedActor(
        provider_subject="fixture-subject-read-only",
        provider_issuer="fixture-managed-oidc-provider",
        display_name="Fixture Read Only Tester",
        email="tester@example.invalid",
        actor_category=cast(HostedActorCategory, actor_category),
        account_status=cast(HostedAccountStatus, account_status),
        roles=tuple(cast(HostedTesterRole, role) for role in roles),
        scopes=scopes,
    )


def _seeded_connection() -> Connection:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    hosted_seeded_import_metadata.create_all(engine)
    connection = engine.connect()
    transaction = connection.begin()
    artifact = load_seeded_corpus_artifact(FIXTURE)
    import_seeded_corpus_artifact(connection, artifact)
    transaction.commit()
    return connection


def _insert_corpus_complaint(
    connection: Connection,
    *,
    job_id: str,
    facility_number: str,
    complaint_control_number: str,
    finding: str,
) -> str:
    return _insert_complaint_batch(
        connection,
        import_batch_id=retrieval_import_batch_id(job_id),
        facility_number=facility_number,
        complaint_control_number=complaint_control_number,
        finding=finding,
    )


def _insert_non_corpus_complaint(connection: Connection) -> str:
    return _insert_complaint_batch(
        connection,
        import_batch_id="outside-corpus-batch",
        facility_number="999999999",
        complaint_control_number="99-CR-OUTSIDE",
        finding="Substantiated",
    )


def _insert_complaint_batch(
    connection: Connection,
    *,
    import_batch_id: str,
    facility_number: str,
    complaint_control_number: str,
    finding: str,
) -> str:
    now = "2026-07-01T12:00:00+00:00"
    facility_id = f"ccld:facility:{facility_number}"
    document_id = f"ccld:document:{facility_number}:1"
    complaint_id = f"ccld:complaint:{complaint_control_number}"
    source_url = (
        "https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports"
        f"?facNum={facility_number}&inx=1"
    )
    connection.execute(
        hosted_import_batches.insert().values(
            import_batch_id=import_batch_id,
            imported_at=now,
            source_artifact_identity=f"fixture-artifact:{import_batch_id}",
            source_pipeline_version="fixture-corpus",
            validation_status="validated",
            raw_hash_validation_status="validated",
            record_counts={"complaint": 1},
            warnings=[],
            errors=[],
        )
    )
    source_record_key = f"complaint:{complaint_id}"
    connection.execute(
        hosted_source_derived_records.insert().values(
            source_record_key=source_record_key,
            entity_type="complaint",
            stable_source_id=complaint_id,
            import_batch_id=import_batch_id,
            source_document_id=document_id,
            facility_id=facility_id,
            source_url=source_url,
            raw_sha256="a" * 64,
            raw_path="data/raw/ccld/fixture/report.html",
            connector_name="ccld_facility_reports",
            connector_version="fixture-corpus",
            retrieved_at=now,
            original_values={
                "complaint_id": complaint_id,
                "facility_id": facility_id,
                "document_id": document_id,
                "facility_number": facility_number,
                "complaint_control_number": complaint_control_number,
                "complaint_received_date": "2026-05-08",
                "report_date": "2026-05-09",
                "finding": finding,
            },
            source_traceability={
                "source_document_id": document_id,
                "source_url": source_url,
                "raw_sha256": "a" * 64,
                "connector_name": "ccld_facility_reports",
                "retrieved_at": now,
            },
        )
    )
    return source_record_key
