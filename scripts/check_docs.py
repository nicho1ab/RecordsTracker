from __future__ import annotations

import re
import subprocess
from collections.abc import Iterable
from pathlib import Path

REQUIRED = [
    ".github/copilot-instructions.md",
    "README.md",
    "PROJECT_CHARTER.md",
    "GOVERNANCE_INVENTORY.md",
    "PUBLIC_SOURCE_DATA_INVENTORY.md",
    "ROADMAP.md",
    "CHANGELOG.md",
    "ARCHITECTURE.md",
    "DECISIONS.md",
    "DATA_CONTRACT.md",
    "SOURCE_CONNECTOR_CONTRACT.md",
    "TESTING_STRATEGY.md",
    "DOCUMENTATION_STRATEGY.md",
    "PRODUCTION_DISCOVERY_REQUIREMENTS.md",
    "DESIGN_AND_USABILITY.md",
    "ACCESSIBILITY_REQUIREMENTS.md",
    "SECURITY_AND_PRIVACY.md",
    "KNOWN_LIMITATIONS.md",
    "RUNBOOK.md",
    "SETUP_INSTRUCTIONS.md",
    "docs/decisions/ADR-0002-local-review-experience.md",
    "docs/decisions/ADR-0005-retain-datasette-as-validation-layer.md",
    "docs/decisions/ADR-0006-hosted-tester-mvp-architecture-boundaries.md",
    "docs/decisions/ADR-0007-hosted-tester-mvp-stack-evaluation.md",
    "docs/decisions/ADR-0008-hosted-tester-mvp-data-review-state-model.md",
    "docs/decisions/ADR-0009-hosted-tester-mvp-import-sync-strategy.md",
    "docs/decisions/ADR-0010-hosted-tester-mvp-schema-migration-strategy.md",
    "docs/decisions/ADR-0011-hosted-tester-mvp-auth-access-roles.md",
    "docs/decisions/ADR-0012-hosted-tester-mvp-scope-scaffold-sequencing.md",
    "docs/decisions/ADR-0013-hosted-tester-mvp-operational-boundaries.md",
    "docs/decisions/ADR-0014-hosted-tester-mvp-auth-provider-and-role-implementation.md",
    "docs/decisions/ADR-0015-hosted-tester-mvp-database-and-migration-tooling.md",
    "docs/decisions/ADR-0016-controlled-browser-triggered-ccld-retrieval-jobs.md",
    "docs/developer/setup.md",
    "docs/developer/architecture.md",
    "docs/developer/hosted-scaffold.md",
    "docs/developer/adding-a-source.md",
    "docs/developer/testing.md",
    "docs/developer/data-contract.md",
    "docs/developer/accessibility.md",
    "docs/developer/copilot-workflow.md",
    "docs/developer/release-process.md",
    "docs/developer/qnap-pilot-deployment-inventory.md",
    "docs/developer/qnap-seed-data-import-runbook.md",
    "docs/user/getting-started.md",
    "docs/user/local-review-workflow.md",
    "docs/user/reviewing-records.md",
    "docs/user/searching-and-filtering.md",
    "docs/user/data-dictionary.md",
    "docs/user/exporting-data.md",
    "docs/user/known-limitations.md",
]

REQUIRED_CONTENT = {
    ".github/copilot-instructions.md": [
        "Required task handoff",
        "Summary of changes",
        "Validation results",
        "Exact git commit and push commands",
        "PR title",
        "PR body",
        "Required GitHub checks",
        "Post-merge cleanup commands",
        "Recommended next branch name",
        "Next Copilot prompt",
        "Next task selection",
        "Do not repeatedly recommend documentation-only work",
        "select the next product or technical milestone from `ROADMAP.md`",
        "Handoff formatting rules",
        "copy/paste-safe",
        "GitHub PR title/body must be separate from PowerShell commands",
        "Run only after squash merge is complete",
        "validate",
        "docs-check",
        "fixtures",
        "security",
        "branch protection rule or repository ruleset",
    ],
    "README.md": [
        "production-discovery",
        "SQLite",
        "Datasette",
        "source traceability",
        "fixture-backed tests",
        "controlled live fetch",
    ],
    "GOVERNANCE_INVENTORY.md": [
        "Current state",
        "Active phase",
        "Public-source expansion status",
        "Recent hosted sequence",
        "PR #109",
        "Primary UX direction",
        "Local-only scaffold status",
        "Datasette role",
        "Completed ADR decisions",
        "Remaining deferred decisions",
        "Stale guidance assessment",
        "Gap analysis",
        "Local-only sample filtering/search",
        "Future fixture-backed source view expansion",
        "Future import path into hosted view",
        "Future database/schema implementation",
        "Future auth/access implementation",
        "Future deployment/hosting decision",
        "Future audit, reviewer-state, correction, export, feedback, and reset/reload",
        "Future public-source expansion",
        "Future attorney focus profiles and feedback intake",
        "Safeguards preserved",
        "Source-derived records remain separate from reviewer-created state",
        "Sample data must stay clearly marked as sample-only",
    ],
    "PUBLIC_SOURCE_DATA_INVENTORY.md": [
        "Source type classification",
        "Structured CSV/open-data sources",
        "HTML portal/detail pages",
        "PDFs/document reports",
        "Metadata/catalog pages",
        "Future multi-state public sources",
        "CCLD source inventory",
        "CCLD individual complaint report pages",
        "CCLD public download CSVs",
        "CHHS/CDSS Community Care Licensing Facilities dataset",
        "Facility master data",
        "Program-specific facility/licensing/complaint summary CSVs",
        "Metadata files",
        "Authoritative facility CSV resources",
        "Local CSV examples",
        "CDSS_CCL_Facilities_2065342970436235361.csv",
        "community-care-licensing-facilities-metadata.csv",
        "HomeCare06072026.csv",
        "CHILDCAREHOMEmorethan806072026.csv",
        "ChildCareCenters06072026.csv",
        "24HourResidentialCareforChildren06072026.csv",
        "FosterFamilyAgencies06072026.csv",
        "Do not commit raw full-size CSVs",
        "Future structured CSV facility handling must preserve at least official dataset",
        "Multi-source expansion model",
        "Attorney focus-area planning",
        "Foster youth education justice",
        "K-12 discipline, absenteeism, and placement stability",
        "Feedback and GitHub intake planning",
        "Triage review",
        "Privacy and secrets check",
        "Human approval before issue creation or implementation",
        "Deferred implementation",
        "No schema changes are approved by this inventory",
    ],
    "DOCUMENTATION_STRATEGY.md": [
        "Documentation impact and currency",
        "Every feature, workflow, source connector, CLI or script, database or view",
        "README.md",
        "GOVERNANCE_INVENTORY.md",
        "PUBLIC_SOURCE_DATA_INVENTORY.md",
        "ROADMAP.md",
        "CHANGELOG.md",
        "docs/user/*",
        "docs/developer/*",
        "DECISIONS.md and ADRs",
        "no user-facing or documentation-impacting behavior changed",
    ],
    "PRODUCTION_DISCOVERY_REQUIREMENTS.md": [
        "Minimum hosted reviewer workflows",
        "Facility search and selection",
        "Complaint review queue",
        "Complaint detail review",
        "Source verification",
        "Annotation",
        "Proposed correction",
        "Facility pattern review",
        "Export packet preparation",
        "Tester feedback",
        "Review-state requirements",
        "not reviewed",
        "in review",
        "source check needed",
        "source checked",
        "correction proposed",
        "correction reviewed",
        "reviewed",
        "included in export",
        "excluded from export",
        "Annotations do not change raw source records",
        "Proposed corrections do not overwrite original extracted values",
        "Hosted tester readiness requirements",
        "Authenticated tester access",
        "Seeded test corpus",
        "Known limitations visible",
        "Accessibility expectations",
        "Source-traceability expectations",
        "Export restrictions and cautions",
        "Feedback collection",
        "Reset and reload process",
    ],
    "ROADMAP.md": [
        "Completed CCLD proof-of-concept capabilities",
        "production-discovery",
        "controlled live fetch",
        "multi-facility input",
        "SQLite review views",
        "Datasette metadata and saved queries",
        "Near-term milestones",
        "Current next priorities",
        "Decision points",
        "Deferred product work",
    ],
    "CHANGELOG.md": [
        "CCLD complaints proof-of-concept",
        "fixture-backed sample ingestion",
        "controlled live fetch scripts",
        "multi-facility input",
        "Datasette review views",
        "documentation validation",
    ],
    "SETUP_INSTRUCTIONS.md": [
        "Run the fixture-backed sample workflow",
        "Run controlled live fetch",
        "For multiple explicitly provided facilities",
        "generated Datasette metadata path",
        "Copilot handoff expectation",
    ],
    "RUNBOOK.md": [
        "Validate changes",
        "Run fixture-backed sample ingestion",
        "Run controlled live fetch",
        "Run multi-facility live fetch",
        "generated metadata file",
        "PR and merge cleanup",
        "branch protection rule or repository ruleset",
        "validate",
        "docs-check",
        "fixtures",
        "security",
        "gh --version",
        "gh auth status",
    ],
    "docs/developer/copilot-workflow.md": [
        "Required completion handoff",
        "Summary of changes",
        "Validation results",
        "Exact git commit and push commands",
        "PR title",
        "PR body",
        "Required GitHub checks",
        "Post-merge cleanup commands",
        "Recommended next branch name",
        "Next Copilot prompt",
        "Next task selection",
        "Do not repeatedly recommend documentation-only work",
        "select the next product or technical milestone from `ROADMAP.md`",
        "Handoff formatting rules",
        "copy/paste-safe",
        "GitHub PR title/body must be separate from PowerShell commands",
        "Run only after squash merge is complete",
        "branch protection rule or repository ruleset",
        "validate",
        "docs-check",
        "fixtures",
        "security",
        "gh --version",
        "gh auth status",
        "Next-prompt quality standard",
        "current project phase",
        "latest merged PR",
        "current roadmap priorities",
        "accepted ADRs",
        "deferred decisions",
        "non-negotiable safeguards",
        "highest-leverage next milestone",
        "Prompt-mode guidance",
        "`analysis-only`",
        "`governance-change`",
        "`architecture decision`",
        "`implementation`",
        "`prototype/spike`",
        "`validation-hardening`",
        "Task mode",
        "Scope boundaries",
        "Files to read",
        "What not to do",
        "Focused validation",
        "Standard PR validation",
        "Remote required checks",
        "PR body requirements",
        "Final handoff requirements",
        "Copilot should not include a recommended next branch command unless the user asks for one",
    ],
    "docs/developer/release-process.md": [
        "Task completion checklist",
        "Validation",
        "Accessibility review",
        "Pull request checks",
        "Merge cleanup",
        "Next-task handoff",
        "Required GitHub checks",
        "post-merge cleanup commands",
        "recommended next branch name",
        "next Copilot prompt",
        "branch protection rule or repository ruleset",
        "validate",
        "docs-check",
        "fixtures",
        "security",
        "gh --version",
        "gh auth status",
    ],
    "docs/developer/accessibility.md": [
        "Local output checklist",
        "Datasette views",
        "Generated metadata",
        "Saved queries",
        "CSV exports and review bundles",
        "Script output",
        "Delay fields and review flags are described as screening aids",
        "source URL, raw SHA-256 hash, connector name, and retrieval timestamp",
    ],
    "docs/developer/hosted-scaffold.md": [
        "Required local tools",
        "Verify local prerequisites",
        "Install dependencies",
        "Start the scaffold locally",
        "Run the smoke check",
        "Run scaffold tests",
        "Open the sample read-only source view shell",
        "Intentionally not implemented",
        "Tooling impact",
        "Node.js is not required",
        "Docker is not required",
        "QNAP Container Station is not required",
        "No cloud resources",
        "check-hosted-scaffold-local.ps1",
        "source-records",
        "fixture/sample records only",
        "semantic/accessibility validation",
        "Python standard-library HTML parsing",
        "source-derived versus reviewer-created state separation",
        "Open the local/test reviewer UI shell",
        "http://127.0.0.1:8000/reviewer",
        "read-after-write reviewer-created state",
        "list-level reviewer-created note/status indicators",
        "safe related seeded bundle context",
        "permission-blocked states include clear",
        "Concise source narrative excerpts may appear on reviewer detail",
        "UI actions do not mutate source-derived records",
        "does not install software",
        "does not require admin rights",
        "not a production reviewer application",
        "not a final production frontend framework",
    ],
    "docs/user/getting-started.md": [
        "Tables to open first",
        "source_documents",
        "extraction_audit",
        "discovers 40 report candidates",
        "facility `157806098`, report index `3`",
    ],
    "docs/user/reviewing-records.md": [
        "flagged for review based on available extracted dates",
        "The public portal remains the source of record",
        "Do not treat missing dates as evidence",
    ],
    "docs/user/local-review-workflow.md": [
        "What to open first",
        "How to find concerning records",
        "How to filter by facility",
        "How to inspect source documents",
        "How to export accessible CSVs",
        "What not to conclude",
        "delay review flags are screening aids, not conclusions",
    ],
    "docs/user/exporting-data.md": [
        "Export from Datasette",
        "Accessible CSV review",
        "delay review flags are screening aids",
    ],
    "DESIGN_AND_USABILITY.md": [
        "Intended users",
        "Current local review workflows",
        "Future primary review UX requirements",
        "Design principles",
        "Usability principles",
        "Visual design principles",
        "Accessibility requirements",
        "Terminology and plain-language rules",
        "Datasette table and view usability expectations",
        "Saved-query expectations",
        "Export usability expectations",
        "Source traceability expectations",
        "Delay-flag caution language",
        "POC scope versus later product work",
    ],
    "docs/decisions/ADR-0002-local-review-experience.md": [
        "SQLite review views",
        "Datasette metadata",
        "Saved queries for common review tasks",
        "will not add a custom frontend during the proof of concept",
    ],
    "docs/decisions/ADR-0005-retain-datasette-as-validation-layer.md": [
        "Datasette is no longer governed as the primary future review experience",
        "validation, inspection, debugging, local",
        "production-discovery",
        "Non-negotiable safeguards",
        "ADR-0001 and ADR-0002 remain accepted for the initial proof of concept",
    ],
    "docs/decisions/ADR-0006-hosted-tester-mvp-architecture-boundaries.md": [
        "primary reviewer application layer separate from Datasette",
        "Comparison against hosted-application behavior during the transition",
        "Source-derived data boundary",
        "Reviewer-created state boundary",
        "Reviewer-created state must remain distinguishable from source-derived records",
        "Every proposed correction must preserve",
        "Original extracted value",
        "Proposed value",
        "Source basis",
        "Reviewer identity or tester identity where available",
        "Decision status",
        "Hosted tester MVP boundary",
        "Authenticated tester access",
        "Seeded test corpus",
        "Reset and reload process",
        "Known limitations visible in the UI",
        "Source traceability visible in review screens and exports",
        "Future stack decision criteria",
        "Deferred decisions",
        "Not yet approved for build",
        "Production app scaffold",
    ],
    "docs/decisions/ADR-0007-hosted-tester-mvp-stack-evaluation.md": [
        "Decision Drivers",
        "Options Considered",
        "Python API plus hosted relational database plus separate web frontend",
        "Full-stack JavaScript or TypeScript application",
        "Low-code or internal-tool platform",
        "Continue with SQLite/Datasette plus lightweight extensions",
        "Hybrid transition approach",
        "Comparison Table",
        "Recommended Direction",
        "Adopt the hybrid transition approach as the preferred direction",
        "Keep the existing Python ingestion and extraction pipeline",
        "Keep SQLite and Datasette for validation, inspection, debugging, local",
        "Introduce a hosted relational database boundary",
        "This recommendation is a general architecture direction",
        "Deferred Decisions",
        "Work Not Approved By This ADR",
        "Follow-up ADRs and Implementation Branches Needed",
    ],
    "docs/decisions/ADR-0008-hosted-tester-mvp-data-review-state-model.md": [
        "Decision",
        "Source-Derived Data Domain",
        "Reviewer-Created State Domain",
        "Review Statuses",
        "Annotation Boundaries",
        "Correction Boundaries",
        "Export Packet Boundaries",
        "Audit Events",
        "Import and Sync Implications",
        "Deferred Decisions",
        "Work Not Approved By This ADR",
        "Source-derived data domain",
        "Reviewer-created state domain",
        "Original extracted values",
        "Proposed replacement value",
        "No schema changes",
    ],
    "docs/decisions/ADR-0009-hosted-tester-mvp-import-sync-strategy.md": [
        "Decision",
        "Options Considered",
        "Recommended Strategy",
        "Import Batch Requirements",
        "Source-Derived Record Identity",
        "Reviewer-Created State Preservation",
        "Reset and Reload Boundary",
        "What This ADR Does Not Approve",
        "Deferred Decisions",
        "Snapshot import from validated SQLite/export output",
        "Incremental import from pipeline-generated source-derived records",
        "Hosted app directly reads from SQLite/Datasette",
        "Hosted app directly runs the connector/live fetch workflow",
        "API-mediated import from the Python pipeline",
        "Manual CSV upload/import as an early tester-only bridge",
        "Import batch ID",
        "Raw hash validation status",
        "No schema changes",
        "Direct live crawling from the hosted app",
    ],
    "docs/decisions/ADR-0010-hosted-tester-mvp-schema-migration-strategy.md": [
        "Decision",
        "Source-Derived Physical Boundary",
        "Reviewer-Created Physical Boundary",
        "Import Batch and Versioning Boundary",
        "Migration Strategy Boundary",
        "Reset and Reload Implications",
        "Testing and Validation Implications",
        "Options Considered",
        "Consequences",
        "Deferred Decisions",
        "Work Not Approved By This ADR",
        "Stable source-derived identity",
        "Import batch ID",
        "Review status history",
        "Hybrid current-state plus import-batch history",
        "One combined hosted schema",
        "Separate schemas or namespaces by data domain",
        "Separate databases for source-derived and reviewer-created state",
        "Snapshot-only source-derived tables",
        "Append-only source-derived version tables",
        "No schema changes",
    ],
    "docs/decisions/ADR-0011-hosted-tester-mvp-auth-access-roles.md": [
        "Decision",
        "Minimum Roles",
        "Permission Boundaries",
        "Tester Access Model",
        "Access to Source-Derived Versus Reviewer-Created Data",
        "Export Access",
        "Import, Reload, and Reset Access",
        "Audit Expectations",
        "Options Considered",
        "Recommended Direction",
        "Consequences",
        "Deferred Decisions",
        "Work Not Approved By This ADR",
        "Anonymous hosted tester access is not allowed",
        "Admin",
        "Tester reviewer",
        "Read-only tester",
        "Developer/operator",
        "Invite/provisioned individual tester accounts",
        "Role-based tester access",
        "No schema changes",
    ],
    "docs/decisions/ADR-0012-hosted-tester-mvp-scope-scaffold-sequencing.md": [
        "Decision",
        "Minimum Hosted Tester MVP Implementation Sequence",
        "First Scaffold Branch Boundaries",
        "Tester-Visible MVP Definition",
        "Design and UX Timing",
        "Validation Expectations for Implementation Branches",
        "Remaining Deferred Decisions",
        "Work Not Approved By This ADR",
        "Hosted tester MVP implementation may begin after this ADR",
        "scaffold-first path",
        "Health check or smoke route",
        "Facility search and read-only source-derived view",
        "Complaint and source document detail view",
        "Authenticated or controlled-access app shell",
        "document-governance dashboard concept",
        "No schema changes",
    ],
    "docs/decisions/ADR-0013-hosted-tester-mvp-operational-boundaries.md": [
        "Decision",
        "Audit Logging Boundary",
        "Export Generation Boundary",
        "Reset and Reload Boundary",
        "Tester Data Retention Boundary",
        "What Remains Blocked",
        "Implementation path unlocked by this ADR",
        "Work Not Approved By This ADR",
        "Tester",
        "Operator",
        "System",
        "ISO datetime with timezone",
        "source traceability",
        "original extracted value",
        "validated pipeline output",
        "Retention categories",
        "Provider-specific authentication and authorization implementation decision",
        "Concrete database product and migration tooling decision",
        "Minimal hosted schema/API scaffold",
        "First authenticated tester workflow",
        "No schema changes",
    ],
    "docs/decisions/ADR-0014-hosted-tester-mvp-auth-provider-and-role-implementation.md": [
        "Decision",
        "OpenID Connect",
        "OAuth 2.0 authorization code flow with PKCE",
        "Roles Needed for the MVP",
        "Admin",
        "Tester reviewer",
        "Read-only tester",
        "Developer/operator",
        "System",
        "Authorization Boundaries Before Reviewer-Created State",
        "No anonymous reviewer-created state is allowed",
        "Identity Claims and Audit Attributes",
        "actor, timestamp, action, target",
        "External Tester Access Lifecycle",
        "What Remains Blocked",
        "Implementation Now Allowed",
        "managed standards-based OpenID Connect",
        "No schema changes",
        "No source-derived canonical fields are added or changed",
    ],
    "docs/decisions/ADR-0015-hosted-tester-mvp-database-and-migration-tooling.md": [
        "Decision",
        "PostgreSQL",
        "Alembic-managed migrations",
        "Persistence Areas Supported",
        "Source-Derived Versus Reviewer-Created State Boundary",
        "ADR-0013 Operational Boundary Support",
        "ADR-0014 Auth Identity and Role/Scope Support",
        "Migration Tooling Direction",
        "Import and batch metadata",
        "Source-derived imported records",
        "Reviewer-created state",
        "Audit events",
        "Export packet state",
        "Tester feedback",
        "Operational and reset/reload metadata",
        "validated pipeline output",
        "What Remains Blocked",
        "Implementation Now Allowed",
        "No schema changes",
        "No source-derived canonical fields are added or changed",
    ],
    "docs/decisions/ADR-0016-controlled-browser-triggered-ccld-retrieval-jobs.md": [
        "Decision",
        "Browser triggers the job; server performs retrieval",
        "Approved Workflow",
        "Allowed Inputs",
        "Required Boundaries",
        "Required Controls",
        "Job States",
        "queued",
        "running",
        "completed",
        "completed_with_warnings",
        "failed",
        "blocked_by_validation",
        "rate_limited",
        "Data and Persistence Boundaries",
        "Security and Privacy Requirements",
        "Runtime and Portability Requirements",
        "Testing Requirements",
        "Implementation Non-Goals",
        "Work Now Approved",
        "Work Not Approved By This ADR",
        "Tests that mock network retrieval; CI must not make live CCLD calls",
        "QNAP Docker is the first deployment target",
        "PostgreSQL is the active production-style data store",
        "No schema changes in this branch",
    ],
    "docs/developer/qnap-pilot-deployment-inventory.md": [
        "What Gets Built And Run",
        "Named Volumes",
        "What Is Not Deployed In This Stage",
        "Pre-Cloudflare",
        "Gaps Before Pilot Is Tester-Ready",
        "CCLD_HOSTED_PAGE_DATA_MODE",
        "CCLD_HOSTED_TESTER_AUTH_MODE",
        "alembic upgrade head",
        "docker-compose.qnap.yml",
        "-SmokeStart",
    ],
    "docs/developer/qnap-seed-data-import-runbook.md": [
        "Preconditions",
        "Build The Validated Artifact On Windows",
        "Transfer The Artifact To The QNAP Host",
        "Copy The Artifact Into The App Container Volume",
        "Run The Import",
        "Verify The Import",
        "source_data_loaded",
        "import_hosted_seeded_corpus",
        "build-hosted-ccld-artifact.ps1",
        "Readiness Gate",
    ],
}

FORBIDDEN_CONTENT = {
    "CHANGELOG.md": [
        "Added data contract, connector contract, testing strategy, "
        "documentation strategy, accessibility requirements, and GitHub Copilot "
        "instructions.",
    ],
    "README.md": [
        "governance pack",
        "zip scaffold",
        "Extract this zip file",
        "Python project skeleton",
    ],
}

STALE_ROADMAP_CURRENT_PRIORITIES = {
    "ROADMAP.md": [
        "Group review workflows by user task rather than by implementation table",
    ],
}

USER_SPECIFIC_REPOSITORY_PATH = re.compile(
    r"(?i)c:[\\/]+users[\\/]+andre[\\/]+onedrive[\\/]+desktop[\\/]+repos[\\/]+"
)


def find_missing_files(root: Path = Path(".")) -> list[str]:
    return [item for item in REQUIRED if not (root / item).exists()]


def find_missing_required_content(root: Path = Path(".")) -> list[str]:
    missing = []
    for relative_path, required_phrases in REQUIRED_CONTENT.items():
        path = root / relative_path
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        for phrase in required_phrases:
            if phrase not in content:
                missing.append(f"{relative_path}: {phrase}")
    return missing


def find_forbidden_content(root: Path = Path(".")) -> list[str]:
    found = []
    for relative_path, forbidden_phrases in FORBIDDEN_CONTENT.items():
        path = root / relative_path
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8").lower()
        for phrase in forbidden_phrases:
            if phrase.lower() in content:
                found.append(f"{relative_path}: {phrase}")
    return found


def find_stale_roadmap_priorities(root: Path = Path(".")) -> list[str]:
    found = []
    for relative_path, stale_phrases in STALE_ROADMAP_CURRENT_PRIORITIES.items():
        path = root / relative_path
        if not path.exists():
            continue
        current_priorities = _markdown_section(
            path.read_text(encoding="utf-8"), "Current next priorities"
        ).lower()
        for phrase in stale_phrases:
            if phrase.lower() in current_priorities:
                found.append(f"{relative_path}: {phrase}")
    return found


def find_user_specific_repository_paths(
    root: Path = Path("."), tracked_files: Iterable[str] | None = None
) -> list[str]:
    if tracked_files is None:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            check=True,
            capture_output=True,
        )
        tracked_files = result.stdout.decode("utf-8").split("\0")

    found = []
    for relative_path in tracked_files:
        if not relative_path:
            continue
        path = root / relative_path
        if not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(lines, start=1):
            if USER_SPECIFIC_REPOSITORY_PATH.search(line):
                found.append(f"{Path(relative_path).as_posix()}:{line_number}")
    return found


def _markdown_section(content: str, heading: str) -> str:
    marker = f"## {heading}"
    start = content.find(marker)
    if start == -1:
        return ""
    section_start = start + len(marker)
    next_heading = content.find("\n## ", section_start)
    if next_heading == -1:
        return content[section_start:]
    return content[section_start:next_heading]


def main() -> None:
    missing_files = find_missing_files()
    if missing_files:
        raise SystemExit("Missing required documentation files: " + ", ".join(missing_files))

    missing_content = find_missing_required_content()
    if missing_content:
        raise SystemExit(
            "Missing required documentation content: " + "; ".join(missing_content)
        )

    forbidden_content = find_forbidden_content()
    if forbidden_content:
        raise SystemExit(
            "Forbidden stale documentation content found: " + "; ".join(forbidden_content)
        )

    stale_roadmap_priorities = find_stale_roadmap_priorities()
    if stale_roadmap_priorities:
        raise SystemExit(
            "Stale completed roadmap priorities found: "
            + "; ".join(stale_roadmap_priorities)
        )

    user_specific_repository_paths = find_user_specific_repository_paths()
    if user_specific_repository_paths:
        raise SystemExit(
            "User-specific absolute repository paths found; replace the local "
            "repository prefix with <Repo Path>\\: "
            + "; ".join(user_specific_repository_paths)
        )

    print("Documentation check passed.")


if __name__ == "__main__":
    main()
