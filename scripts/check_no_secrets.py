from __future__ import annotations

import re
from pathlib import Path

PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*=\s*['\"][^'\"]{8,}['\"]"),
    re.compile(r"ghp_[A-Za-z0-9_]{20,}"),
]

SKIP_DIRS = {".git", ".venv", "__pycache__"}
violations: list[str] = []
for path in Path(".").rglob("*"):
    if not path.is_file():
        continue
    if any(part in SKIP_DIRS for part in path.parts):
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    for pattern in PATTERNS:
        if pattern.search(text):
            violations.append(str(path))
            break

if violations:
    raise SystemExit("Potential secrets found in: " + ", ".join(violations))
print("Secret check passed.")
