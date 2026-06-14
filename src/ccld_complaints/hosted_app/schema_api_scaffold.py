from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ccld_complaints.hosted_app.persistence import (
    HostedDatabaseConfig,
    PersistenceBoundary,
    hosted_persistence_boundaries,
    load_hosted_database_config,
)

ApiDomain = Literal[
    "source-derived",
    "reviewer-created",
    "audit",
    "operational",
    "auth",
]
ImplementationStatus = Literal["scaffold-only"]


@dataclass(frozen=True)
class HostedApiBoundary:
    boundary_id: str
    label: str
    domain: ApiDomain
    implementation_status: ImplementationStatus
    intended_future_use: str
    requires_authenticated_actor_before_write: bool
    preserves: tuple[str, ...]
    deferred: tuple[str, ...]


@dataclass(frozen=True)
class HostedSchemaApiScaffold:
    database_config: HostedDatabaseConfig
    persistence_boundaries: tuple[PersistenceBoundary, ...]
    api_boundaries: tuple[HostedApiBoundary, ...]
    domain_tables_created: bool = True
    auth_boundary_scaffold_implemented: bool = True
    auth_provider_integration_plan_implemented: bool = True
    source_derived_read_service_implemented: bool = True
    source_derived_read_api_routes_implemented: bool = True
    reviewer_workflow_shell_implemented: bool = True
    reviewer_workflow_shell_state_read_integration_implemented: bool = True
    reviewer_workflow_shell_state_filter_search_implemented: bool = True
    reviewer_workflow_shell_note_action_implemented: bool = True
    reviewer_workflow_shell_status_action_implemented: bool = True
    reviewer_ui_shell_implemented: bool = True
    ccld_record_request_ui_shell_implemented: bool = True
    ccld_validated_import_reload_implemented: bool = True
    reset_reload_dry_run_implemented: bool = True
    reset_reload_execution_plan_implemented: bool = True
    reset_reload_operational_metadata_scaffold_implemented: bool = True
    reset_reload_planning_metadata_read_api_routes_implemented: bool = True
    reviewer_created_state_persistence_scaffold_implemented: bool = True
    reviewer_note_write_route_scaffold_implemented: bool = True
    reviewer_created_state_read_api_routes_implemented: bool = True
    reviewer_created_state_read_filter_search_implemented: bool = True
    audit_coverage_plan_implemented: bool = True
    audit_event_persistence_scaffold_implemented: bool = True
    audit_event_read_api_routes_implemented: bool = True
    api_routes_implemented: bool = True
    imports_implemented: bool = True
    reviewer_workflows_implemented: bool = False
    reset_reload_implemented: bool = False


HOSTED_API_BOUNDARIES = (
    HostedApiBoundary(
        boundary_id="auth_provider_integration_plan_api",
        label="Auth provider integration planning API boundary",
        domain="auth",
        implementation_status="scaffold-only",
        intended_future_use=(
            "Plan future managed OpenID Connect/OAuth 2.0 provider integration "
            "through a local/test non-persistent route seam that validates the "
            "accepted provider class, summarizes auth boundary models, and "
            "returns bounded non-secret readiness steps without implementing login."
        ),
        requires_authenticated_actor_before_write=True,
        preserves=(
            "managed provider-class direction from ADR-0014",
            "existing local/test actor, role, permission, and scope model",
            "non-secret configuration readiness inputs",
            "no-persistence planning behavior",
        ),
        deferred=(
            "real login flow",
            "auth middleware",
            "callback handling",
            "token exchange or validation",
            "sessions or cookies",
            "provider registration",
            "user tables or role persistence",
            "hosted URLs or deployment configuration",
        ),
    ),
    HostedApiBoundary(
        boundary_id="source_derived_records_api",
        label="Seeded source-derived records API boundary",
        domain="source-derived",
        implementation_status="scaffold-only",
        intended_future_use=(
            "Read seeded source-derived records loaded from controlled snapshot imports "
            "from validated pipeline output through a local/test service and "
            "authenticated HTTP/API route seam."
        ),
        requires_authenticated_actor_before_write=True,
        preserves=(
            "public portal as source of record",
            "raw source traceability",
            "original extracted values",
            "SQLite/Datasette validation and transition comparison role",
        ),
        deferred=(
            "production API framework",
            "live crawling",
            "hosted connector execution",
            "reset/reload behavior",
        ),
    ),
    HostedApiBoundary(
        boundary_id="reviewer_created_state_api",
        label="Reviewer-created state API boundary",
        domain="reviewer-created",
        implementation_status="scaffold-only",
        intended_future_use=(
            "Persist review status, notes, annotations, correction proposals, feedback, "
            "and export packet decisions after future focused branches define each layer. "
            "The current implementation adds only a local/test reviewer-created state "
            "persistence scaffold table and service boundary, a narrow local/test "
            "authenticated read route seam for listing or fetching those rows, a narrow "
            "local/test reviewer note creation route over the existing state scaffold, plus "
            "a narrow local/test reviewer status creation route over the existing state "
            "scaffold, plus "
            "a read-only reviewer workflow shell detail seam that composes associated "
            "reviewer-created state read route output for a selected source record, and a "
            "narrow workflow-shell note action and status action that resolve the selected "
            "detail context before delegating to the existing reviewer-created write routes."
        ),
        requires_authenticated_actor_before_write=True,
        preserves=(
            "separation from source-derived records",
            "future authenticated actor attribution",
            "future audit event support",
            "stable links to source-derived identities",
            "read-only access to persisted reviewer-created scaffold rows",
            "bounded non-secret reviewer note payloads under the existing state kind",
            "bounded reviewer status payloads under the existing state kind",
            "workflow-shell source-record binding from selected detail context",
        ),
        deferred=(
            "auth middleware",
            "full reviewer-created workflow persistence",
            "stateful reviewer workflows",
            "status editing or deletion",
            "note editing or deletion",
            "full audit policy coverage",
            "export builder behavior",
        ),
    ),
    HostedApiBoundary(
        boundary_id="audit_events_api",
        label="Audit events API boundary",
        domain="audit",
        implementation_status="scaffold-only",
        intended_future_use=(
            "Persist audit events for hosted tester state-changing operations after "
            "future branches define full coverage. The current implementation adds "
            "only local/test audit rows for successful reviewer-created state "
            "scaffold writes and a local/test authenticated read route seam for "
            "listing or fetching those rows."
        ),
        requires_authenticated_actor_before_write=True,
        preserves=(
            "source-derived versus reviewer-created state separation",
            "authenticated actor attribution",
            "project or corpus scope",
            "target and source-derived context",
        ),
        deferred=(
            "production audit API framework",
            "full audit policy coverage",
            "audit UI or export behavior",
            "retention automation",
        ),
    ),
    HostedApiBoundary(
        boundary_id="audit_coverage_plan_api",
        label="Audit coverage planning API boundary",
        domain="audit",
        implementation_status="scaffold-only",
        intended_future_use=(
            "Plan future hosted tester audit coverage through a local/test "
            "non-persistent route seam that summarizes current scaffold audit "
            "coverage, deferred ADR-0013/ADR-0014 event categories, and bounded "
            "implementation-readiness steps without creating audit rows."
        ),
        requires_authenticated_actor_before_write=True,
        preserves=(
            "current reviewer-created state write audit coverage",
            "authenticated actor attribution model",
            "target and source-derived context model",
            "non-secret audit metadata rules",
            "no-persistence planning behavior",
        ),
        deferred=(
            "new audit event write behavior",
            "audit UI or export behavior",
            "export packet audit coverage",
            "provider login audit coverage",
            "reset/reload execution audit coverage",
            "retention automation",
            "audit schema changes or migrations",
        ),
    ),
    HostedApiBoundary(
        boundary_id="seeded_corpus_reset_reload_operations_api",
        label="Seeded corpus reset/reload operations API boundary",
        domain="operational",
        implementation_status="scaffold-only",
        intended_future_use=(
            "Plan seeded corpus reset/reload impact before future execution. The "
            "current implementation exposes only a local/test dry-run route seam "
            "that inspects staged seeded corpus metadata and reports affected "
            "source-derived and future reviewer-created state categories, plus a "
            "local/test execution-plan route seam that converts those summaries "
            "into an ordered bounded non-destructive action plan. It can "
            "optionally persist a separate local/test operational planning metadata "
            "record when explicitly requested, and exposes a read-only local/test "
            "route seam to list or fetch those persisted planning records."
        ),
        requires_authenticated_actor_before_write=True,
        preserves=(
            "source-derived versus reviewer-created state separation",
            "stable source-derived identities",
            "source traceability",
            "future audit requirements for operational changes",
            "ordered non-destructive execution-plan steps",
            "read-only access to persisted planning metadata",
        ),
        deferred=(
            "destructive reset execution",
            "seeded corpus reload execution",
            "reviewer-created state archival or clearing",
            "audit event persistence",
            "production reset/reload operational framework",
        ),
    ),
)


def hosted_api_boundaries() -> tuple[HostedApiBoundary, ...]:
    return HOSTED_API_BOUNDARIES


def build_hosted_schema_api_scaffold() -> HostedSchemaApiScaffold:
    return HostedSchemaApiScaffold(
        database_config=load_hosted_database_config(),
        persistence_boundaries=hosted_persistence_boundaries(),
        api_boundaries=hosted_api_boundaries(),
    )
