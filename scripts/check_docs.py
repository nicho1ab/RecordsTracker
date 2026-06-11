from __future__ import annotations

from pathlib import Path

REQUIRED = [
    "README.md",
    "PROJECT_CHARTER.md",
    "ROADMAP.md",
    "ARCHITECTURE.md",
    "DECISIONS.md",
    "DATA_CONTRACT.md",
    "SOURCE_CONNECTOR_CONTRACT.md",
    "TESTING_STRATEGY.md",
    "DOCUMENTATION_STRATEGY.md",
    "ACCESSIBILITY_REQUIREMENTS.md",
    "SECURITY_AND_PRIVACY.md",
    "KNOWN_LIMITATIONS.md",
    "RUNBOOK.md",
    "docs/developer/setup.md",
    "docs/developer/accessibility.md",
    "docs/developer/copilot-workflow.md",
    "docs/user/getting-started.md",
    "docs/user/reviewing-records.md",
    "docs/user/data-dictionary.md",
    "docs/user/exporting-data.md",
    "docs/user/known-limitations.md",
]

REQUIRED_CONTENT = {
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
    "docs/user/exporting-data.md": [
        "Export from Datasette",
        "Accessible CSV review",
        "delay review flags are screening aids",
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


def main() -> None:
    missing_files = find_missing_files()
    if missing_files:
        raise SystemExit("Missing required documentation files: " + ", ".join(missing_files))

    missing_content = find_missing_required_content()
    if missing_content:
        raise SystemExit(
            "Missing required documentation content: " + "; ".join(missing_content)
        )

    print("Documentation check passed.")


if __name__ == "__main__":
    main()
