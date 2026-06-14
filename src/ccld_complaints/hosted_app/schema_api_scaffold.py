from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ccld_complaints.hosted_app.persistence import (
    HostedDatabaseConfig,
    PersistenceBoundary,
    hosted_persistence_boundaries,
    load_hosted_database_config,
)

ApiDomain = Literal["source-derived", "reviewer-created", "audit", "operational"]
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
    source_derived_read_service_implemented: bool = True
    source_derived_read_api_routes_implemented: bool = True
    reviewer_workflow_shell_implemented: bool = True
    reset_reload_dry_run_implemented: bool = True
    reviewer_created_state_persistence_scaffold_implemented: bool = True
    audit_event_persistence_scaffold_implemented: bool = True
    api_routes_implemented: bool = True
    imports_implemented: bool = True
    reviewer_workflows_implemented: bool = False
    reset_reload_implemented: bool = False


HOSTED_API_BOUNDARIES = (
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
            "persistence scaffold table and service boundary, plus a read-only reviewer "
            "workflow shell over source-derived route responses."
        ),
        requires_authenticated_actor_before_write=True,
        preserves=(
            "separation from source-derived records",
            "future authenticated actor attribution",
            "future audit event support",
            "stable links to source-derived identities",
        ),
        deferred=(
            "auth middleware",
            "full reviewer-created workflow persistence",
            "stateful reviewer workflows",
            "audit logging",
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
            "scaffold writes."
        ),
        requires_authenticated_actor_before_write=True,
        preserves=(
            "source-derived versus reviewer-created state separation",
            "authenticated actor attribution",
            "project or corpus scope",
            "target and source-derived context",
        ),
        deferred=(
            "audit API routes",
            "full audit policy coverage",
            "audit UI or export behavior",
            "retention automation",
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
            "source-derived and future reviewer-created state categories."
        ),
        requires_authenticated_actor_before_write=True,
        preserves=(
            "source-derived versus reviewer-created state separation",
            "stable source-derived identities",
            "source traceability",
            "future audit requirements for operational changes",
        ),
        deferred=(
            "destructive reset execution",
            "seeded corpus reload execution",
            "reviewer-created state archival or clearing",
            "audit event persistence",
            "operational/reset metadata persistence",
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