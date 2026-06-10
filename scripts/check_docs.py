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
    "docs/developer/copilot-workflow.md",
    "docs/user/getting-started.md",
    "docs/user/data-dictionary.md",
]

missing = [item for item in REQUIRED if not Path(item).exists()]
if missing:
    raise SystemExit("Missing required documentation files: " + ", ".join(missing))
print("Documentation check passed.")
