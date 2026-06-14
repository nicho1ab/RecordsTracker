from __future__ import annotations

import re
from pathlib import Path

PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*=\s*['\"][^'\"]{8,}['\"]"),
    re.compile(r"ghp_[A-Za-z0-9_]{20,}"),
]

SKIP_DIRS = {".git", "__pycache__"}
SKIP_DIR_PREFIXES = (".venv",)


def should_skip_path(path: Path) -> bool:
    return any(
        part in SKIP_DIRS or any(part.startswith(prefix) for prefix in SKIP_DIR_PREFIXES)
        for part in path.parts
    )


def find_violations(root: Path = Path(".")) -> list[str]:
    violations: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if should_skip_path(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in PATTERNS:
            if pattern.search(text):
                violations.append(str(path))
                break
    return violations


def main() -> int:
    violations = find_violations()
    if violations:
        print("Potential secrets found in: " + ", ".join(violations))
        return 1
    print("Secret check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
