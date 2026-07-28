from __future__ import annotations

import ast
import importlib.util
import json
import re
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ccld_complaints.portable_paths import (  # noqa: E402
    find_portable_path_violations,
)

EVIDENCE_POLICY_PATH = ".github/evidence-reuse-validation-impact-policy.json"
EVIDENCE_SCHEMA_PATH = "schemas/evidence-reuse-validation-impact-v1.schema.json"
EVIDENCE_EVALUATOR_PATH = "scripts/evaluate_evidence_reuse_policy.py"
EVIDENCE_INDEPENDENT_VERIFIER_PATH = "scripts/check_independent_verification.py"
EVIDENCE_PREPARATION_PATH = "scripts/prepare_pr_body.py"
EVIDENCE_DOCUMENTATION_PATH = "docs/developer/codex-workflow.md"
EVIDENCE_TESTING_STRATEGY_PATH = "TESTING_STRATEGY.md"
EVIDENCE_POLICY_HEADING = "Governed evidence reuse and validation-impact policy"
EVIDENCE_COMPACT_HEADING = "Validation impact and evidence delta"
EVIDENCE_REQUIRED_CHECKS = ("validate", "docs-check", "fixtures", "security")
EVIDENCE_GOVERNED_DISCLOSURES = (
    "requires disclosure when governed workflow boundaries change",
    "no branch-protection or ruleset change",
    "no required-check rename or removal",
    "no autonomous approval or merge",
)
EVIDENCE_ENVELOPE_FIELDS = (
    "kind",
    "schema_version",
    "policy_input",
    "policy_result",
    "delta",
    "validation_newly_performed",
    "live_evidence_recollected",
)
EVIDENCE_RESULT_FIELDS = (
    "decision",
    "repository_state",
    "change_inventory",
    "impact_classes",
    "validation_requirements",
    "evidence_reused",
    "evidence_recollected",
    "evidence_superseded",
    "evidence_invalidated",
    "live_obligations",
    "blockers",
    "authorized_mutations",
    "unauthorized_mutations",
    "governed_boundary_disclosures",
    "reasons",
)
EVIDENCE_TEMPLATE_MARKERS = (
    "exact base/head identity",
    "inventory count and digest",
    "impact classes",
    "requirements",
    "retained/recollected/",
    "superseded/invalidated evidence",
    "live obligations",
    "blockers",
    "authorized/unauthorized mutations",
    "- Decision:",
    "- Delta:",
    "- Policy version:",
    "- Compact evidence envelope:",
    "- Validation newly performed:",
    "- Retained evidence reused:",
    "- Live evidence recollected:",
    "- Superseded evidence:",
    "- Invalidated evidence:",
    "- Required-check state:",
    "- Blockers:",
    "- Governed-boundary disclosures:",
    "- Authorized mutations:",
    "- Unauthorized mutations:",
)
EVIDENCE_DOCUMENTATION_MARKERS = (
    "### Documentation-contract enforcement",
    "## Validation-impact matrix",
    "## Evidence-reuse examples",
    "## Worktree lifecycle definitions",
    "## Publication guidance",
    "## Issue #617 and #533 ownership boundary",
    "#617 owns:",
    "#533 owns unless explicitly reassigned:",
    "The deferred `merged` timeline-event classifier remains out of scope.",
    "authoritative live PR state",
    "non-self-referential canonical body hash",
    "requires disclosure when governed workflow boundaries change",
    "no branch-protection or ruleset change",
    "no required-check rename or removal",
    "no autonomous approval or merge",
    "source tests remain retained",
    "body-dependent evidence is invalidated",
    "blocks readiness",
    "supersedes earlier successful readiness evidence",
    "documentation and whitespace validation",
    "owning collection are required",
    "classification fails closed.",
    "prior boundary review is invalidated",
    "**Active:**",
    "**Parked:**",
    "**Retained after merge:**",
    "**Blocked:**",
    "**Safe to remove:**",
    "**Preserved for evidence:**",
    "A state classification grants no cleanup authority.",
    "automatic branch deletion",
    "stash mutation, pruning, or broad",
    "maximum of three routine comments",
    "not enforced through autonomous publication",
    "failed or safety-relevant evidence must not be omitted",
)
EVIDENCE_IMPLEMENTATION_STATUS = (
    "Issue #617 implementation status: slice_1=policy-schema-evaluator; "
    "slice_2=PR-preparation-and-independent-verification; "
    "slice_3=documentation-checks; state=local-unmerged-unaccepted; "
    "issue_533_execution_authority=absent."
)
_EVIDENCE_CURRENT_STATUS_CLAIM = re.compile(
    r"(?im)^\s*(?:[-*]\s*)?(?:issue\s*#617|(?:these|the)\s+slices?|"
    r"the\s+(?:current\s+)?work)\b[^\n]*\b(?:is|are|status[^\n]*=)[^\n]*\b"
    r"(?:merged|accepted|complete(?:d)?|prevented|fully\s+implemented|deployed|production-ready|closed)\b"
)
_EVIDENCE_AUTHORITY_TRANSFER_CLAIM = re.compile(
    r"(?im)^\s*(?:[-*]\s*)?(?:#533\b[^\n]*(?:moved|transferred|superseded)[^\n]*#617\b|"
    r"(?:issue\s*)?#617\b[^\n]*(?:now\s+)?(?:owns|has|retains|inherited|replaced)[^\n]*\b"
    r"(?:execution|publication|merge|recovery|orchestration|lifecycle|closure|rerun|deployment|production-data)\b|"
    r"(?:execution|publication|merge|recovery|orchestration|lifecycle|closure|rerun|deployment|production-data)"
    r"[^\n]*\b(?:belongs to|owned by)\s+(?:issue\s*)?#617\b)"
)
EVIDENCE_MATRIX_HEADER = (
    "Impact class",
    "Focused validation",
    "Full suite",
    "Documentation validation",
    "Live GitHub evidence",
    "Body regeneration",
    "Independent review",
    "Primary invalidation triggers",
)

REVIEWER_UI_GOVERNANCE_SECTIONS = {
    "AGENTS.md": "Reviewer-facing design enforcement",
    ".github/copilot-instructions.md": "Reviewer-facing design implementation rules",
    "DESIGN_AND_USABILITY.md": "Approved design implementation and primary-content rules",
    "ACCESSIBILITY_REQUIREMENTS.md": "Primary record inventory and disclosure accessibility",
    "TESTING_STRATEGY.md": "Reviewer UI design-conformance and source-to-screen tests",
    "docs/product/records-tracker-product-ux-lead-charter.md": "Figma and Design Handoff",
    "docs/product/records-tracker-approved-design-decisions.md": "Evidence-report format",
    "docs/planning/records-tracker-ui-ux-data-completeness-remediation-plan.md": (
        "Evidence review checklist"
    ),
    "docs/developer/ui-evidence-review.md": "Issue #479 reviewer-facing visual acceptance contract",
    "docs/developer/hosted-reviewer-acceptance.md": "Reviewer-facing visual acceptance boundary",
}

REVIEWER_UI_EVIDENCE_GATE_CONTRACT = (
    ("RT-UI-GATE-001", "design-authority"),
    ("RT-UI-GATE-002", "pre-code-variance"),
    ("RT-UI-GATE-003", "primary-content"),
    ("RT-UI-GATE-004", "source-to-screen"),
    ("RT-UI-GATE-005", "state-truthfulness"),
    ("RT-UI-GATE-006", "token-and-tlp"),
    ("RT-UI-GATE-007", "automated-route-capture"),
    ("RT-UI-GATE-008", "accessibility-responsive"),
    ("RT-UI-GATE-009", "visual-acceptance"),
)

REVIEWER_UI_EVIDENCE_TABLE_HEADER = (
    "Gate ID",
    "Rule family",
    "Required evidence",
    "Passing condition",
    "Blocking result",
)

ATTORNEY_IA_GOVERNANCE_SECTIONS = (
    (
        "docs/product/records-tracker-attorney-information-architecture.md",
        "Attorney task model",
    ),
    (
        "docs/product/records-tracker-attorney-information-architecture.md",
        "Reviewer-facing route and page inventory",
    ),
    (
        "docs/product/records-tracker-attorney-information-architecture.md",
        "Route dispositions",
    ),
    (
        "docs/product/records-tracker-attorney-information-architecture.md",
        "Approved navigation",
    ),
    (
        "docs/product/records-tracker-attorney-information-architecture.md",
        "Approved terminology",
    ),
    (
        "docs/product/records-tracker-attorney-information-architecture.md",
        "Information tiers",
    ),
    (
        "docs/product/records-tracker-attorney-information-architecture.md",
        "Responsive, keyboard, zoom, and print behavior",
    ),
    (
        "docs/product/records-tracker-attorney-information-architecture.md",
        "Figma and design package",
    ),
    (
        "docs/product/records-tracker-attorney-information-architecture.md",
        "Stale contract inventory",
    ),
    (
        "docs/product/records-tracker-attorney-information-architecture.md",
        "Ordered implementation sequence",
    ),
    ("DESIGN_AND_USABILITY.md", "Issue #501 attorney information architecture"),
    (
        "docs/planning/records-tracker-ui-ux-data-completeness-remediation-plan.md",
        "Issue #501 dependent design sequence",
    ),
)

ATTORNEY_IA_REQUIREMENT_IDS = ("RT-IA-004", "RT-NAV-001", "RT-LANG-001")
ATTORNEY_IA_NAVIGATION_ORDER = (
    "Home",
    "Find a Facility",
    "Compare Facilities",
    "Complaint Worklist",
    "Feedback",
    "Help",
)
ATTORNEY_IA_ROUTE_DISPOSITIONS = (
    ("/", "retain"),
    ("/ccld/facilities", "retain"),
    ("/ccld/facilities/intelligence", "retain"),
    ("/ccld/facilities/review-priority", "merge"),
    ("/ccld/records/request", "retain"),
    ("/reviewer", "retain"),
    ("/reviewer/records", "redirect"),
    ("/reviewer/records/substantiated", "convert to view/filter"),
    ("/reviewer/records/serious-topics", "convert to view/filter"),
    ("/reviewer/facilities/priorities", "merge"),
    ("/reviewer/facilities/trends", "convert to view/filter"),
    ("/ccld/help", "retain"),
    ("/feedback", "retain"),
)
ATTORNEY_IA_ROUTE_TABLE_HEADER = (
    "Current route or endpoint",
    "Disposition",
    "Approved destination or role",
    "Transition and preservation rule",
)

ANTI_FOSSILIZATION_DOCUMENT = (
    "docs/product/records-tracker-reviewer-redesign-artifact-governance.md"
)
ANTI_FOSSILIZATION_SECTIONS = (
    "Authority and scope",
    "Artifact classification model",
    "Required redesign inventory and change process",
    "Outcome-based test design",
    "Evidence and acceptance",
    "Pull request and handoff contract",
    "Issue 501, 502, and 503 findings",
    "Prohibited shortcuts and stop conditions",
)
ANTI_FOSSILIZATION_CLASS_MODEL = (
    ("1", "Durable product outcome"),
    ("2", "Accessibility or safety invariant"),
    ("3", "Source/data/domain contract"),
    ("4", "Approved design requirement"),
    ("5", "Implementation regression test"),
    ("6", "Presentation snapshot or exact-string assertion"),
    ("7", "Historical documentation"),
)
ANTI_FOSSILIZATION_TABLE_HEADER = (
    "Class",
    "Name",
    "What it protects",
    "Redesign treatment",
)
ANTI_FOSSILIZATION_REQUIRED_MARKERS = {
    "AGENTS.md": ANTI_FOSSILIZATION_DOCUMENT,
    ".github/copilot-instructions.md": ANTI_FOSSILIZATION_DOCUMENT,
    "docs/developer/codex-workflow.md": ANTI_FOSSILIZATION_DOCUMENT,
    "DESIGN_AND_USABILITY.md": ANTI_FOSSILIZATION_DOCUMENT,
    "TESTING_STRATEGY.md": ANTI_FOSSILIZATION_DOCUMENT,
    "ACCESSIBILITY_REQUIREMENTS.md": ANTI_FOSSILIZATION_DOCUMENT,
    "DOCUMENTATION_STRATEGY.md": ANTI_FOSSILIZATION_DOCUMENT,
    "docs/product/records-tracker-product-ux-lead-charter.md": (
        "records-tracker-reviewer-redesign-artifact-governance.md"
    ),
    "docs/product/records-tracker-approved-design-decisions.md": (
        "records-tracker-reviewer-redesign-artifact-governance.md"
    ),
    "docs/planning/records-tracker-ui-ux-data-completeness-remediation-plan.md": (
        "docs/product/records-tracker-reviewer-redesign-artifact-governance.md"
    ),
    "docs/developer/ui-evidence-review.md": (
        "records-tracker-reviewer-redesign-artifact-governance.md"
    ),
    "docs/developer/hosted-reviewer-acceptance.md": (
        "records-tracker-reviewer-redesign-artifact-governance.md"
    ),
}

REQUIRED = [
    ".github/PULL_REQUEST_TEMPLATE.md",
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
    "docs/product/records-tracker-attorney-information-architecture.md",
    "docs/product/records-tracker-reviewer-redesign-artifact-governance.md",
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
        "Task-relevant context",
        "durable task specification",
        "actually read",
        "Required task handoff",
        "Implementation and RL-PREPARE handoffs are concise",
        "Required GitHub checks",
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
        "Implementation and RL-PREPARE handoffs contain only",
        "delta-only",
        "continuation never grants additional authority implicitly",
        "focused validation",
        "Standard PR validation",
        "validate",
        "docs-check",
        "fixtures",
        "security",
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

CODEX_WORKFLOW_REQUIRED_MARKERS = {
    "AGENTS.md": (
        "Use task-relevant context by default.",
        "durable task specification",
        "governing files actually read",
        "shared primary-",
        "report only unresolved blockers",
    ),
    ".github/copilot-instructions.md": (
        "Task-relevant context",
        "Implementation and RL-PREPARE handoffs are concise",
        "next-task suggestion never grants",
        "shared primary-repository",
        "Resolve documented prerequisites",
    ),
    "CONTRIBUTING.md": (
        "Use focused local validation by default:",
        "repository rule that specifically",
        "verified primary-repository",
        "a missing local `.venv` is not itself a blocker",
    ),
    "docs/developer/codex-workflow.md": (
        "This is user guidance, not a repository-enforced model",
        "The compact template below separates stable defaults",
        "## Validation environment resolution",
        "Secondary worktrees are not expected to contain their own virtual environment.",
        "Resolve the verified Python executable from the authoritative primary repository",
        "the working directory set to the current issue worktree",
        "the verified primary-repository Python executable",
        "Do not first attempt:",
        "a worktree-local `.venv`",
        "Report an environment blocker only after:",
        "the exact command and error were captured.",
        "## Known-prerequisite resolution",
        "Resolve documented, task-relevant prerequisites",
        "primary-repository virtual-environment use from secondary worktrees",
        "Do not perform broad speculative prerequisite discovery.",
        "continuation never expands authorization",
        "Investigation and implementation may be combined",
        "Use a separate investigation phase when root cause is unknown",
        "repository governance specifically requires it",
        "### Conditional queued phase transitions",
        "original explicit conditional grant.",
        "### Fresh authoritative state after lifecycle mutations",
        "Contradictory fresh",
        "### Persistent coordination branches after squash merge",
        "Broad force-push authority is prohibited",
        "## Acceptance-evidence lifecycle",
        "Successful capture, technical package",
    ),
    "docs/developer/copilot-workflow.md": (
        "durable task specification",
        "delta-only",
        "continuation never grants additional authority implicitly.",
        "Independent GitHub Actions verification",
        "fresh-context review remains advisory",
    ),
    "TESTING_STRATEGY.md": (
        "when repository governance specifically requires it",
        "when focused or CI failures require broader investigation.",
    ),
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

PULL_REQUEST_TEMPLATE_SECTIONS = (
    "Governing issue and intended outcome",
    "Implementation scope",
    "Acceptance-criteria evidence",
    "Validation and failure classification",
    "Validation impact and evidence delta",
    "UI and accessibility evidence (when applicable)",
    "Reviewer-facing redesign artifact classification (when applicable)",
    "Documentation, assumptions, and remaining risks",
    "Governed-boundary review",
    "Required GitHub checks",
)

PULL_REQUEST_TEMPLATE_MARKERS = (
    "Governing issue:",
    "Intended outcome:",
    "Major files or components changed:",
    "Reviewer UI regression contracts:",
    "| Acceptance criterion | Evidence and result |",
    "| Exact command | Result | Failure classification, if applicable |",
    "Implementation-caused failures:",
    "Pre-existing failures:",
    "Environmental failures:",
    "Complete this section only for UI or accessibility changes.",
    "Complete this section for a material reviewer-facing removal, merge, rename,",
    (
        "| Artifact or assertion | Class | Disposition | Durable reason or "
        "requirement ID | Replacement evidence |"
    ),
    "Preserved assertions:",
    "Rewritten assertions:",
    "Removed assertions:",
    "Historical-only artifacts:",
    "Intentionally superseded behavior or routes:",
    "Redirect or migration behavior:",
    "Controlled-variance approval, if used:",
    "Durable protections weakened:",
    "| Schemas and migrations |",
    "| Ingestion and source-connector contracts |",
    "| Security and privacy |",
    "| Production data and correction behavior |",
    "| Deployment and infrastructure |",
    "| Repository governance |",
    "| Required GitHub workflows and checks |",
    "| Tests or checks weakened to obtain passage |",
    '"all tests passed" does not satisfy this review.',
    "Self-reported evidence supplements, and never replaces,",
    "`validate`",
    "`docs-check`",
    "`fixtures`",
    "`security`",
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


def find_codex_workflow_contract_violations(root: Path = Path(".")) -> list[str]:
    violations = []
    for relative_path, markers in CODEX_WORKFLOW_REQUIRED_MARKERS.items():
        path = root / relative_path
        if not path.exists():
            violations.append(f"missing Codex workflow document: {relative_path}")
            continue
        content = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in content:
                violations.append(f"{relative_path}: missing Codex workflow marker: {marker}")
    return violations


def find_pull_request_template_contract_violations(
    root: Path = Path("."),
) -> list[str]:
    path = root / ".github/PULL_REQUEST_TEMPLATE.md"
    if not path.exists():
        return ["missing .github/PULL_REQUEST_TEMPLATE.md"]

    content = path.read_text(encoding="utf-8")
    violations = []
    section_positions = []
    for section in PULL_REQUEST_TEMPLATE_SECTIONS:
        heading = f"## {section}"
        count = content.count(heading)
        if count != 1:
            violations.append(f"expected exactly one heading: {heading}")
            continue
        section_positions.append(content.index(heading))

    if len(section_positions) == len(PULL_REQUEST_TEMPLATE_SECTIONS) and (
        section_positions != sorted(section_positions)
    ):
        violations.append("required headings are out of order")

    for marker in PULL_REQUEST_TEMPLATE_MARKERS:
        if marker not in content:
            violations.append(f"missing marker: {marker}")

    return violations


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
    """Scan Git-tracked text through the authoritative portable-path contract."""

    if tracked_files is None:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            check=True,
            capture_output=True,
        )
        tracked_files = result.stdout.decode("utf-8").split("\0")

    found: list[str] = []
    for relative_path in tracked_files:
        if not relative_path:
            continue
        path = root / relative_path
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        display_path = Path(relative_path).as_posix()
        found.extend(
            violation.diagnostic()
            for violation in find_portable_path_violations(
                content,
                field=display_path,
                source_path=display_path,
                allow_approved_fixture=True,
            )
        )
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


def _markdown_table_cells(line: str) -> tuple[str, ...]:
    return tuple(cell.strip().strip("`") for cell in line.strip().strip("|").split("|"))


def _load_fixed_evidence_policy_module(root: Path) -> Any:
    path = root / EVIDENCE_EVALUATOR_PATH
    spec = importlib.util.spec_from_file_location("docs_evidence_policy", path)
    if not spec or not spec.loader:
        raise RuntimeError("cannot load fixed evidence policy evaluator")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _matrix_rows(section: str) -> dict[str, tuple[str, ...]]:
    lines = section.splitlines()
    header_index = next(
        (
            index
            for index, line in enumerate(lines)
            if line.startswith("|") and _markdown_table_cells(line) == EVIDENCE_MATRIX_HEADER
        ),
        None,
    )
    if header_index is None:
        return {}
    rows: dict[str, tuple[str, ...]] = {}
    for line in lines[header_index + 1 :]:
        if not line.startswith("|"):
            if rows:
                break
            continue
        cells = _markdown_table_cells(line)
        if cells and all(re.fullmatch(r"-+", cell) for cell in cells):
            continue
        if len(cells) == len(EVIDENCE_MATRIX_HEADER):
            rows[cells[0]] = cells
    return rows


def _literal_tuple_assignment(source: str, name: str) -> tuple[str, ...] | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    for statement in tree.body:
        if not isinstance(statement, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == name for target in statement.targets
        ):
            continue
        try:
            value = ast.literal_eval(statement.value)
        except ValueError:
            return None
        if isinstance(value, tuple) and all(isinstance(item, str) for item in value):
            return value
    return None


def find_evidence_policy_documentation_contract_violations(
    root: Path = Path("."),
) -> list[str]:
    """Validate the fixed, read-only evidence-policy documentation contract."""

    violations: list[str] = []
    required_paths = (
        EVIDENCE_POLICY_PATH,
        EVIDENCE_SCHEMA_PATH,
        EVIDENCE_EVALUATOR_PATH,
        EVIDENCE_INDEPENDENT_VERIFIER_PATH,
        EVIDENCE_PREPARATION_PATH,
        EVIDENCE_DOCUMENTATION_PATH,
        EVIDENCE_TESTING_STRATEGY_PATH,
        ".github/PULL_REQUEST_TEMPLATE.md",
    )
    for relative_path in required_paths:
        if not (root / relative_path).is_file():
            violations.append(f"missing evidence-policy contract file: {relative_path}")
    if violations:
        return sorted(violations)

    try:
        policy = json.loads((root / EVIDENCE_POLICY_PATH).read_text(encoding="utf-8"))
        schema = json.loads((root / EVIDENCE_SCHEMA_PATH).read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return [f"invalid evidence-policy JSON: {error.msg}"]
    if not isinstance(policy, dict) or not isinstance(schema, dict):
        return ["invalid evidence-policy contract JSON object"]

    try:
        evaluator = _load_fixed_evidence_policy_module(root)
    except (ImportError, RuntimeError, SyntaxError) as error:
        return [f"cannot load fixed evidence policy evaluator: {error}"]

    supported_schema_version = cast(str, getattr(evaluator, "SCHEMA_VERSION", ""))
    supported_policy_version = cast(str, getattr(evaluator, "POLICY_VERSION", ""))
    if not supported_schema_version or not supported_policy_version:
        return ["fixed evidence policy evaluator does not declare supported versions"]
    if policy.get("schema_version") != supported_schema_version:
        violations.append("evidence policy schema version is unsupported")
    if policy.get("policy_version") != supported_policy_version:
        violations.append("evidence policy version is unsupported")

    schema_policy = schema.get("$defs", {}).get("policy", {}).get("properties", {})
    schema_result = schema.get("$defs", {}).get("result", {}).get("properties", {})
    if schema_policy.get("schema_version", {}).get("const") != supported_schema_version:
        violations.append("evidence schema version does not match evaluator support")
    policy_version_pattern = schema_policy.get("policy_version", {}).get("pattern", "")
    if not re.fullmatch(policy_version_pattern, supported_policy_version):
        violations.append("evidence schema policy version does not match evaluator support")
    if schema_result.get("schema_version", {}).get("const") != supported_schema_version:
        violations.append("evidence result schema version does not match evaluator support")

    required_checks = tuple(policy.get("required_check_names", ()))
    if required_checks != EVIDENCE_REQUIRED_CHECKS:
        violations.append("evidence policy required checks differ from repository contract")
    disclosures = tuple(policy.get("governed_boundary_disclosures", ()))
    if disclosures != EVIDENCE_GOVERNED_DISCLOSURES:
        violations.append(
            "evidence policy governed-boundary disclosures differ from repository contract"
        )

    evaluator_source = (root / EVIDENCE_EVALUATOR_PATH).read_text(encoding="utf-8")
    for marker in (
        'POLICY_PATH = ROOT / ".github" / "evidence-reuse-validation-impact-policy.json"',
        'SCHEMA_PATH = ROOT / "schemas" / "evidence-reuse-validation-impact-v1.schema.json"',
    ):
        if marker not in evaluator_source:
            violations.append("evidence evaluator fixed canonical path is incorrect")

    independent_source = (root / EVIDENCE_INDEPENDENT_VERIFIER_PATH).read_text(encoding="utf-8")
    for marker in (
        "SUPPORTED_POLICY_VERSION = EVIDENCE_POLICY.POLICY_VERSION",
        "SUPPORTED_SCHEMA_VERSION = EVIDENCE_POLICY.SCHEMA_VERSION",
        f'COMPACT_POLICY_HEADING = "{EVIDENCE_COMPACT_HEADING}"',
    ):
        if marker not in independent_source:
            violations.append("independent verification policy contract drift")
            break
    declared_envelope_fields = _literal_tuple_assignment(
        independent_source, "COMPACT_POLICY_REQUIRED_FIELDS"
    )
    declared_result_fields = _literal_tuple_assignment(
        independent_source, "COMPACT_POLICY_RESULT_FIELDS"
    )
    for field in EVIDENCE_ENVELOPE_FIELDS:
        if declared_envelope_fields is None or field not in declared_envelope_fields:
            violations.append(f"independent verification compact field drift: {field}")
    for field in EVIDENCE_RESULT_FIELDS:
        if declared_result_fields is None or field not in declared_result_fields:
            violations.append(f"independent verification compact field drift: {field}")

    preparation_source = (root / EVIDENCE_PREPARATION_PATH).read_text(encoding="utf-8")
    for marker in (
        "SUPPORTED_POLICY_VERSION = verification.SUPPORTED_POLICY_VERSION",
        "SUPPORTED_SCHEMA_VERSION = verification.SUPPORTED_SCHEMA_VERSION",
        "preliminary = verification.compact_policy_section(",
        "verification.bind_compact_policy_body_hash(",
    ):
        if marker not in preparation_source:
            violations.append("PR-body preparation policy contract drift")
            break

    template = (root / ".github/PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8")
    if template.count(f"## {EVIDENCE_COMPACT_HEADING}") != 1:
        violations.append("PR template compact evidence heading drift")
    for marker in EVIDENCE_TEMPLATE_MARKERS:
        if marker not in template:
            violations.append(f"PR template compact evidence field drift: {marker}")

    documentation = (root / EVIDENCE_DOCUMENTATION_PATH).read_text(encoding="utf-8")
    section = _markdown_section(documentation, EVIDENCE_POLICY_HEADING)
    for marker in EVIDENCE_DOCUMENTATION_MARKERS:
        if marker not in documentation:
            violations.append(f"evidence-policy documentation missing marker: {marker}")
    if supported_policy_version not in section or supported_schema_version not in section:
        violations.append("evidence-policy documentation version declaration drift")
    if re.search(
        r"(?i)\b(?:authorizes|allows|grants)\s+(?:an?\s+)?autonomous\s+"
        r"(?:publication|retry|merge|recovery|cleanup|issue\s+(?:write|mutation))",
        section,
    ):
        violations.append("evidence-policy documentation claims autonomous lifecycle authority")

    testing_strategy = (root / EVIDENCE_TESTING_STRATEGY_PATH).read_text(encoding="utf-8")
    for document_name, content in (
        (EVIDENCE_DOCUMENTATION_PATH, documentation),
        (EVIDENCE_TESTING_STRATEGY_PATH, testing_strategy),
    ):
        if EVIDENCE_IMPLEMENTATION_STATUS not in content:
            violations.append(f"evidence-policy implementation status missing: {document_name}")
            if re.search(
                r"(?i)(?:PR[- ]evidence|documentation[- ]check).*?\b"
                r"(?:absent|not integrated|no integration)\b",
                content,
            ):
                violations.append(
                    "evidence-policy implementation status contradicts integration: "
                    f"{document_name}"
                )
        if re.search(
            r"(?i)(?:PR-evidence|documentation-check) integration remain later "
            r"separately authorized work",
            content,
        ):
            violations.append(
                f"evidence-policy implementation status contradicts integration: {document_name}"
            )
        if _EVIDENCE_CURRENT_STATUS_CLAIM.search(content):
            violations.append(
                "evidence-policy implementation status makes an untruthful current claim: "
                f"{document_name}"
            )
        if _EVIDENCE_AUTHORITY_TRANSFER_CLAIM.search(content):
            violations.append(
                f"evidence-policy documentation transfers #533 authority: {document_name}"
            )

    rows = _matrix_rows(_markdown_section(documentation, "Validation-impact matrix"))
    policy_classes = policy.get("impact_classes", [])
    if not isinstance(policy_classes, list):
        violations.append("evidence-policy impact-class contract is malformed")
    else:
        for impact_class in policy_classes:
            requirements = evaluator._strict_requirements([impact_class], policy)
            expected = (
                impact_class,
                ", ".join(requirements["required_focused_validation_categories"]) or "none",
                "yes" if requirements["full_suite_required"] else "no",
                "yes" if requirements["docs_validation_required"] else "no",
                "yes" if requirements["live_github_evidence_required"] else "no",
                "yes" if requirements["pr_body_regeneration_required"] else "no",
                "yes" if requirements["independent_review_required"] else "no",
            )
            row = rows.get(impact_class)
            if row is None:
                violations.append(f"evidence-policy matrix missing impact class: {impact_class}")
            elif row[:7] != expected or not row[7]:
                violations.append(f"evidence-policy matrix drift: {impact_class}")

    return sorted(set(violations))


def find_reviewer_ui_governance_contract_violations(
    root: Path = Path("."),
) -> list[str]:
    violations = []
    for relative_path, heading in REVIEWER_UI_GOVERNANCE_SECTIONS.items():
        path = root / relative_path
        if not path.exists():
            violations.append(f"missing governance file: {relative_path}")
            continue
        content = path.read_text(encoding="utf-8")
        marker = f"## {heading}"
        if content.count(marker) != 1:
            violations.append(f"{relative_path}: expected exactly one section heading: {marker}")

    evidence_path = root / "docs/developer/ui-evidence-review.md"
    if not evidence_path.exists():
        return violations

    section = _markdown_section(
        evidence_path.read_text(encoding="utf-8"),
        REVIEWER_UI_GOVERNANCE_SECTIONS["docs/developer/ui-evidence-review.md"],
    )
    lines = section.splitlines()
    header_index = next(
        (
            index
            for index, line in enumerate(lines)
            if line.startswith("|")
            and _markdown_table_cells(line) == REVIEWER_UI_EVIDENCE_TABLE_HEADER
        ),
        None,
    )
    if header_index is None:
        violations.append("reviewer UI evidence gate table header is missing")
        return violations

    rows: list[tuple[str, ...]] = []
    for line in lines[header_index + 1 :]:
        if not line.startswith("|"):
            if rows:
                break
            continue
        cells = _markdown_table_cells(line)
        if cells and all(re.fullmatch(r"-+", cell) for cell in cells):
            continue
        rows.append(cells)

    expected_ids = tuple(item[0] for item in REVIEWER_UI_EVIDENCE_GATE_CONTRACT)
    actual_ids = tuple(row[0] for row in rows if row)
    if actual_ids != expected_ids:
        violations.append(
            "reviewer UI evidence gate IDs must be exactly: " + ", ".join(expected_ids)
        )

    for index, (expected_id, expected_family) in enumerate(REVIEWER_UI_EVIDENCE_GATE_CONTRACT):
        if index >= len(rows):
            continue
        row = rows[index]
        if len(row) != len(REVIEWER_UI_EVIDENCE_TABLE_HEADER):
            violations.append(f"{expected_id}: expected five structured table cells")
            continue
        gate_id, family, evidence, passing_condition, blocking_result = row
        if gate_id != expected_id:
            continue
        if family != expected_family:
            violations.append(
                f"{expected_id}: expected rule family {expected_family}, found {family}"
            )
        if not evidence:
            violations.append(f"{expected_id}: required evidence cell is empty")
        if not passing_condition:
            violations.append(f"{expected_id}: passing condition cell is empty")
        if blocking_result != "BLOCK":
            violations.append(f"{expected_id}: blocking result must be BLOCK")

    return violations


def find_attorney_information_architecture_contract_violations(
    root: Path = Path("."),
) -> list[str]:
    violations = []
    for relative_path, heading in ATTORNEY_IA_GOVERNANCE_SECTIONS:
        path = root / relative_path
        if not path.exists():
            violations.append(f"missing attorney IA governance file: {relative_path}")
            continue
        marker = f"## {heading}"
        if path.read_text(encoding="utf-8").count(marker) != 1:
            violations.append(f"{relative_path}: expected exactly one section heading: {marker}")

    decision_path = root / "docs/product/records-tracker-attorney-information-architecture.md"
    design_path = root / "docs/product/records-tracker-approved-design-decisions.md"
    if not decision_path.exists() or not design_path.exists():
        return violations

    decision_content = decision_path.read_text(encoding="utf-8")
    design_content = design_path.read_text(encoding="utf-8")
    for requirement_id in ATTORNEY_IA_REQUIREMENT_IDS:
        marker = f"### {requirement_id} —"
        if design_content.count(marker) != 1:
            violations.append("approved design register must define exactly one " + requirement_id)

    navigation_text = ", ".join(ATTORNEY_IA_NAVIGATION_ORDER)
    navigation_section = _markdown_section(decision_content, "Approved navigation")
    normalized_navigation_section = " ".join(navigation_section.split())
    if navigation_text not in normalized_navigation_section:
        violations.append("attorney navigation order must be exactly: " + navigation_text)

    route_section = _markdown_section(decision_content, "Route dispositions")
    lines = route_section.splitlines()
    header_index = next(
        (
            index
            for index, line in enumerate(lines)
            if line.startswith("|")
            and _markdown_table_cells(line) == ATTORNEY_IA_ROUTE_TABLE_HEADER
        ),
        None,
    )
    if header_index is None:
        violations.append("attorney IA route-disposition table header is missing")
        return violations

    route_rows: dict[str, str] = {}
    for line in lines[header_index + 1 :]:
        if not line.startswith("|"):
            if route_rows:
                break
            continue
        cells = _markdown_table_cells(line)
        if cells and all(re.fullmatch(r"-+", cell) for cell in cells):
            continue
        if len(cells) == len(ATTORNEY_IA_ROUTE_TABLE_HEADER):
            route_rows[cells[0]] = cells[1]

    for route, expected_disposition in ATTORNEY_IA_ROUTE_DISPOSITIONS:
        actual_disposition = route_rows.get(route)
        if actual_disposition != expected_disposition:
            violations.append(
                f"{route}: expected disposition {expected_disposition}, "
                f"found {actual_disposition or 'missing'}"
            )

    figma_section = _markdown_section(decision_content, "Figma and design package")
    normalized_figma_section = " ".join(figma_section.split())
    for required_text in (
        "No editable Figma artifact was accessed or changed",
        "visual design package is **pending**",
        "repository-readable package as the controlled variance",
    ):
        if required_text not in normalized_figma_section:
            violations.append("attorney IA Figma status must preserve: " + required_text)

    return violations


def find_anti_fossilization_contract_violations(
    root: Path = Path("."),
) -> list[str]:
    violations = []
    contract_path = root / ANTI_FOSSILIZATION_DOCUMENT
    if not contract_path.exists():
        return [f"missing anti-fossilization contract: {ANTI_FOSSILIZATION_DOCUMENT}"]

    content = contract_path.read_text(encoding="utf-8")
    for heading in ANTI_FOSSILIZATION_SECTIONS:
        marker = f"## {heading}"
        if content.count(marker) != 1:
            violations.append(
                f"{ANTI_FOSSILIZATION_DOCUMENT}: expected exactly one section heading: {marker}"
            )

    classification_section = _markdown_section(content, "Artifact classification model")
    lines = classification_section.splitlines()
    header_index = next(
        (
            index
            for index, line in enumerate(lines)
            if line.startswith("|")
            and _markdown_table_cells(line) == ANTI_FOSSILIZATION_TABLE_HEADER
        ),
        None,
    )
    if header_index is None:
        violations.append("anti-fossilization classification table header is missing")
    else:
        rows: list[tuple[str, ...]] = []
        for line in lines[header_index + 1 :]:
            if not line.startswith("|"):
                if rows:
                    break
                continue
            cells = _markdown_table_cells(line)
            if cells and all(re.fullmatch(r"-+", cell) for cell in cells):
                continue
            rows.append(cells)

        actual_model = tuple(
            (row[0], row[1]) for row in rows if len(row) == len(ANTI_FOSSILIZATION_TABLE_HEADER)
        )
        if actual_model != ANTI_FOSSILIZATION_CLASS_MODEL:
            expected = ", ".join(
                f"{number} {name}" for number, name in ANTI_FOSSILIZATION_CLASS_MODEL
            )
            violations.append("anti-fossilization class model must be exactly: " + expected)
        for row in rows:
            if len(row) != len(ANTI_FOSSILIZATION_TABLE_HEADER):
                violations.append(
                    "anti-fossilization class rows must contain four structured cells"
                )
                break
            if any(not cell for cell in row):
                violations.append("anti-fossilization class rows must not contain empty cells")
                break

    findings = _markdown_section(content, "Issue 501, 502, and 503 findings")
    for marker in ("#501 controlling design", "#502 Home and Facilities", "#503 Help"):
        if marker not in findings:
            violations.append("anti-fossilization findings must include: " + marker)

    for marker in (
        "preserve",
        "rewrite",
        "remove",
        "historical only",
        "Durable outcome test:",
        "Brittle presentation assertion:",
        "RT-UI-GATE-001",
        "RT-UI-GATE-009",
    ):
        if marker not in content:
            violations.append("anti-fossilization contract must include: " + marker)

    for relative_path, marker in ANTI_FOSSILIZATION_REQUIRED_MARKERS.items():
        path = root / relative_path
        if not path.exists():
            violations.append(f"missing anti-fossilization governance file: {relative_path}")
            continue
        if marker not in path.read_text(encoding="utf-8"):
            violations.append(f"{relative_path}: missing anti-fossilization marker: {marker}")

    return violations


def find_delivery_automation_registry_violations(root: Path = Path(".")) -> list[str]:
    """Run the canonical offline DA-registry validator through docs validation."""

    script = Path(__file__).with_name("delivery_automation_registry.py")
    if not script.is_file():
        return ["missing delivery-automation registry validator"]
    spec = importlib.util.spec_from_file_location("delivery_automation_registry", script)
    if not spec or not spec.loader:
        return ["cannot load delivery-automation registry validator"]
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return cast(list[str], module.validate_canonical_registry())


def main() -> None:
    missing_files = find_missing_files()
    if missing_files:
        raise SystemExit("Missing required documentation files: " + ", ".join(missing_files))

    missing_content = find_missing_required_content()
    if missing_content:
        raise SystemExit("Missing required documentation content: " + "; ".join(missing_content))

    codex_workflow_violations = find_codex_workflow_contract_violations()
    if codex_workflow_violations:
        raise SystemExit("Invalid Codex workflow contract: " + "; ".join(codex_workflow_violations))

    pull_request_template_violations = find_pull_request_template_contract_violations()
    if pull_request_template_violations:
        raise SystemExit(
            "Invalid pull-request template contract: " + "; ".join(pull_request_template_violations)
        )

    evidence_policy_violations = find_evidence_policy_documentation_contract_violations()
    if evidence_policy_violations:
        raise SystemExit(
            "Invalid evidence-policy documentation contract: "
            + "; ".join(evidence_policy_violations)
        )

    forbidden_content = find_forbidden_content()
    if forbidden_content:
        raise SystemExit(
            "Forbidden stale documentation content found: " + "; ".join(forbidden_content)
        )

    stale_roadmap_priorities = find_stale_roadmap_priorities()
    if stale_roadmap_priorities:
        raise SystemExit(
            "Stale completed roadmap priorities found: " + "; ".join(stale_roadmap_priorities)
        )

    user_specific_repository_paths = find_user_specific_repository_paths()
    if user_specific_repository_paths:
        raise SystemExit(
            "Prohibited personal filesystem paths found in tracked content: "
            + "; ".join(user_specific_repository_paths)
        )

    reviewer_ui_governance_violations = find_reviewer_ui_governance_contract_violations()
    if reviewer_ui_governance_violations:
        raise SystemExit(
            "Invalid reviewer UI governance contract: "
            + "; ".join(reviewer_ui_governance_violations)
        )

    attorney_ia_violations = find_attorney_information_architecture_contract_violations()
    if attorney_ia_violations:
        raise SystemExit(
            "Invalid attorney information-architecture contract: "
            + "; ".join(attorney_ia_violations)
        )

    anti_fossilization_violations = find_anti_fossilization_contract_violations()
    if anti_fossilization_violations:
        raise SystemExit(
            "Invalid anti-fossilization contract: " + "; ".join(anti_fossilization_violations)
        )

    delivery_automation_registry_violations = find_delivery_automation_registry_violations()
    if delivery_automation_registry_violations:
        raise SystemExit(
            "Invalid delivery-automation registry: "
            + "; ".join(delivery_automation_registry_violations)
        )

    print("Documentation check passed.")


if __name__ == "__main__":
    main()
