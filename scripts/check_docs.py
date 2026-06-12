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
    "DESIGN_AND_USABILITY.md",
    "ACCESSIBILITY_REQUIREMENTS.md",
    "SECURITY_AND_PRIVACY.md",
    "KNOWN_LIMITATIONS.md",
    "RUNBOOK.md",
    "SETUP_INSTRUCTIONS.md",
    "docs/decisions/ADR-0002-local-review-experience.md",
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
    ],
    "README.md": [
        "CCLD complaints proof of concept",
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
    "ROADMAP.md": [
        "Completed CCLD proof-of-concept capabilities",
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
    ],
    "docs/developer/accessibility.md": [
        "Local output checklist",
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
        "Primary review workflows",
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

    print("Documentation check passed.")


if __name__ == "__main__":
    main()
