from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

DATABASE_URL_ENV = "CCLD_HOSTED_TESTER_DATABASE_URL"
DATABASE_PRODUCT = "PostgreSQL"
MIGRATION_TOOL = "Alembic"
ALEMBIC_CONFIG_PATH = Path("alembic.ini")
ALEMBIC_SCRIPT_LOCATION = Path("migrations")
POSTGRESQL_URL_SCHEMES = frozenset(
    {
        "postgresql",
        "postgresql+psycopg",
        "postgresql+psycopg2",
    }
)

PersistenceDomain = Literal[
    "import-metadata",
    "source-derived",
    "reviewer-created",
    "audit",
    "export",
    "feedback",
    "operations",
    "auth-access",
]


class HostedDatabaseConfigError(ValueError):
    pass


@dataclass(frozen=True)
class HostedDatabaseConfig:
    database_url: str | None
    database_url_env: str
    database_product: str
    migration_tool: str
    alembic_config_path: Path
    migration_script_location: Path

    @property
    def configured(self) -> bool:
        return self.database_url is not None

    @property
    def safe_database_url(self) -> str:
        if self.database_url is None:
            return "<unset>"
        return redact_database_url(self.database_url)


@dataclass(frozen=True)
class PersistenceBoundary:
    boundary_id: str
    label: str
    domain: PersistenceDomain
    purpose: str
    preserves: tuple[str, ...]
    must_not: tuple[str, ...]


REQUIRED_ADR_0010_BOUNDARY_IDS = frozenset(
    {
        "import_batches",
        "source_derived_records",
        "reviewer_created_state",
        "audit_events",
        "export_packet_state",
        "tester_feedback",
        "operational_reset_metadata",
    }
)

HOSTED_PERSISTENCE_BOUNDARIES = (
    PersistenceBoundary(
        boundary_id="import_batches",
        label="Import and batch metadata",
        domain="import-metadata",
        purpose="Future controlled snapshot imports from validated pipeline output.",
        preserves=(
            "import batch identity",
            "validation status",
            "source artifact or pipeline reference",
        ),
        must_not=(
            "run hosted live crawling",
            "run hosted connector execution",
            "silently reset reviewer-created state",
        ),
    ),
    PersistenceBoundary(
        boundary_id="source_derived_records",
        label="Source-derived imported records",
        domain="source-derived",
        purpose="Future hosted copies of validated source-derived records for review.",
        preserves=(
            "source URL",
            "raw SHA-256 hash",
            "connector metadata",
            "retrieval timestamp",
            "original extracted values",
        ),
        must_not=(
            "store reviewer-created state inside source-derived records",
            "overwrite raw source files",
            "change canonical source-derived fields without the data-contract path",
        ),
    ),
    PersistenceBoundary(
        boundary_id="reviewer_created_state",
        label="Reviewer-created state",
        domain="reviewer-created",
        purpose="Future review status, notes, annotations, and correction workflow state.",
        preserves=(
            "stable links to source-derived identities",
            "authenticated actor attribution",
            "history of reviewer-created changes",
        ),
        must_not=(
            "overwrite source-derived canonical values",
            "erase original extracted values",
            "allow anonymous reviewer-created writes",
        ),
    ),
    PersistenceBoundary(
        boundary_id="audit_events",
        label="Audit events",
        domain="audit",
        purpose="Future actor, timestamp, action, target, and context audit records.",
        preserves=(
            "actor category",
            "ISO datetime with timezone",
            "target and relevant context",
        ),
        must_not=(
            "store secrets, tokens, cookies, or private headers",
            "overwrite prior audit events",
            "replace source retrieval or extraction audit timestamps",
        ),
    ),
    PersistenceBoundary(
        boundary_id="export_packet_state",
        label="Export packet state",
        domain="export",
        purpose="Future packet membership and export lifecycle state.",
        preserves=(
            "packet-scoped inclusion or exclusion",
            "source traceability references",
            "original values when corrected values are presented",
        ),
        must_not=(
            "treat export inclusion as a public-source fact",
            "hide source traceability",
            "generate export artifacts in this scaffold",
        ),
    ),
    PersistenceBoundary(
        boundary_id="tester_feedback",
        label="Tester feedback",
        domain="feedback",
        purpose="Future tester feedback linked to workflow and source context.",
        preserves=(
            "workflow context",
            "approved tester or actor reference",
            "enough non-secret context to reproduce issues",
        ),
        must_not=(
            "store provider credentials",
            "treat usability feedback as a source-derived correction",
            "store unnecessary sensitive narrative content",
        ),
    ),
    PersistenceBoundary(
        boundary_id="operational_reset_metadata",
        label="Operational and reset/reload metadata",
        domain="operations",
        purpose="Future reset, reload, recovery, comparison, and retention metadata.",
        preserves=(
            "reset or reload scope",
            "actor or approved process identity",
            "affected record counts where available",
        ),
        must_not=(
            "silently delete reviewer-created state",
            "load seeded data from unvalidated artifacts",
            "perform destructive reset in this scaffold",
        ),
    ),
    PersistenceBoundary(
        boundary_id="auth_identity_scope",
        label="Authenticated actor and role/scope references",
        domain="auth-access",
        purpose="Future provider subject, role, and project or corpus scope references.",
        preserves=(
            "managed provider subject reference",
            "role or permission assignment",
            "project or corpus scope assignment",
        ),
        must_not=(
            "store provider secrets",
            "store tokens or cookies",
            "replace application authorization checks",
        ),
    ),
)


def validate_postgresql_database_url(database_url: str) -> None:
    normalized_url = database_url.strip()
    if not normalized_url:
        raise HostedDatabaseConfigError(f"{DATABASE_URL_ENV} is empty.")

    parsed_url = urlsplit(normalized_url)
    if parsed_url.scheme.lower() not in POSTGRESQL_URL_SCHEMES:
        raise HostedDatabaseConfigError(
            f"{DATABASE_URL_ENV} must use a PostgreSQL SQLAlchemy URL scheme."
        )
    if not parsed_url.path or parsed_url.path == "/":
        raise HostedDatabaseConfigError(f"{DATABASE_URL_ENV} must include a database name.")
    if parsed_url.fragment:
        raise HostedDatabaseConfigError(f"{DATABASE_URL_ENV} must not include URL fragments.")


def redact_database_url(database_url: str) -> str:
    parsed_url = urlsplit(database_url.strip())
    if not parsed_url.scheme:
        return "<invalid-database-url>"
    database_placeholder = "/<redacted-database>" if parsed_url.path else ""
    return f"{parsed_url.scheme}://<redacted-host>{database_placeholder}"


def load_hosted_database_config(
    environ: Mapping[str, str] | None = None,
    project_root: Path | None = None,
    *,
    require_url: bool = False,
) -> HostedDatabaseConfig:
    active_environ = os.environ if environ is None else environ
    root = Path(".") if project_root is None else project_root
    raw_database_url = active_environ.get(DATABASE_URL_ENV, "").strip()
    database_url = raw_database_url or None

    if database_url is None:
        if require_url:
            raise HostedDatabaseConfigError(f"Set {DATABASE_URL_ENV} before running migrations.")
    else:
        validate_postgresql_database_url(database_url)

    return HostedDatabaseConfig(
        database_url=database_url,
        database_url_env=DATABASE_URL_ENV,
        database_product=DATABASE_PRODUCT,
        migration_tool=MIGRATION_TOOL,
        alembic_config_path=root / ALEMBIC_CONFIG_PATH,
        migration_script_location=root / ALEMBIC_SCRIPT_LOCATION,
    )


def hosted_persistence_boundaries() -> tuple[PersistenceBoundary, ...]:
    return HOSTED_PERSISTENCE_BOUNDARIES


def missing_required_persistence_boundaries(
    boundaries: tuple[PersistenceBoundary, ...] = HOSTED_PERSISTENCE_BOUNDARIES,
) -> frozenset[str]:
    present_boundary_ids = {boundary.boundary_id for boundary in boundaries}
    return frozenset(REQUIRED_ADR_0010_BOUNDARY_IDS - present_boundary_ids)