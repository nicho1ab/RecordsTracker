from __future__ import annotations

from pathlib import Path

REQUIRED = [
    ".github/copilot-instructions.md",
    "README.md",
    "PROJECT_CHARTER.md",
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
    "docs/developer/setup.md",
    "docs/developer/architecture.md",
    "docs/developer/adding-a-source.md",
    "docs/developer/testing.md",
    "docs/developer/data-contract.md",
    "docs/developer/accessibility.md",
    "docs/developer/copilot-workflow.md",
    "docs/developer/release-process.md",
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
    "DOCUMENTATION_STRATEGY.md": [
        "Documentation impact and currency",
        "Every feature, workflow, source connector, CLI or script, database or view",
        "README.md",
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

    print("Documentation check passed.")


if __name__ == "__main__":
    main()
