"""Detect and safely describe non-portable named-user filesystem paths."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import PurePosixPath

PORTABLE_PATH_CONTRACT_VERSION = "recordstracker.portable-paths.v1"

APPROVED_PLACEHOLDERS = (
    "<Repo Path>",
    "<Evidence Path>",
    "<Output Path>",
    "<User-Accessible Output Path>",
    "<repo-root>",
    "<local-project-path>",
)

APPROVED_TRACKED_FIXTURES = frozenset(
    {
        "tests/fixtures/portable_paths/detection-cases.json",
    }
)

_CONTAINER_STATION_HOME = "/" + "/".join(("home", "containerstation"))
_USERNAME = r"""[a-z0-9](?:[a-z0-9._ -]*[a-z0-9._-])?"""
_PATTERNS = (
    (
        "windows_named_user_profile",
        re.compile(
            rf"(?i)(?<![a-z0-9_])[a-z]:(?:[\\/]+)users(?:[\\/]+)"
            rf"{_USERNAME}"
        ),
    ),
    (
        "macos_named_user_home",
        re.compile(
            rf"(?i)(?<![:a-z0-9_])/(?:users)/(?!shared(?:[\\/]|$))"
            rf"{_USERNAME}"
        ),
    ),
    (
        "linux_named_user_home",
        re.compile(
            rf"(?i)(?<![:a-z0-9_])/(?:home|var/home|export/home)/"
            rf"{_USERNAME}"
        ),
    ),
)


@dataclass(frozen=True)
class PortablePathViolation:
    """A redacted, actionable path-contract failure."""

    field: str
    pattern_id: str
    line: int
    column: int
    start: int
    end: int
    recommended_replacement: str

    def diagnostic(self) -> str:
        return (
            f"{self.field}:{self.line}:{self.column}: prohibited pattern "
            f"{self.pattern_id}; replace the local path with "
            f"{self.recommended_replacement}"
        )


class PortablePathError(ValueError):
    """Publication content contains one or more prohibited personal paths."""

    def __init__(self, violations: Iterable[PortablePathViolation]) -> None:
        self.violations = tuple(violations)
        super().__init__("; ".join(item.diagnostic() for item in self.violations))


def normalize_repository_path(path: str) -> str:
    """Normalize a repository-relative path for exact fixture authorization."""

    return PurePosixPath(path.replace("\\", "/")).as_posix().lstrip("./")


def is_approved_tracked_fixture(path: str) -> bool:
    """Return whether a tracked path is the one narrowly approved detection fixture."""

    return normalize_repository_path(path) in APPROVED_TRACKED_FIXTURES


def _line_and_column(text: str, offset: int) -> tuple[int, int]:
    line = text.count("\n", 0, offset) + 1
    last_newline = text.rfind("\n", 0, offset)
    return line, offset - last_newline


def _path_end(text: str, start: int, prefix_end: int) -> int:
    opener = text[start - 1] if start > 0 else ""
    if opener in {"`", '"', "'"}:
        closing = text.find(opener, prefix_end)
        if closing >= 0:
            return closing
    end = prefix_end
    while end < len(text) and not (
        text[end].isspace() or text[end] in {"`", '"', "'", "<", ">", "|", ",", ";", ")", "]", "}"}
    ):
        end += 1
    line_start = text.rfind("\n", 0, start) + 1
    if end < len(text) and text[end] == " " and not text[line_start:start].strip():
        line_end = text.find("\n", end)
        return len(text) if line_end < 0 else line_end
    return end


def _replacement_for_match(value: str) -> str:
    normalized = re.sub(r"[\\/]+", "/", value).casefold()
    if "/repos/" in normalized or "/repositories/" in normalized:
        return "<Repo Path>"
    if "evidence" in normalized:
        return "<Evidence Path>"
    if any(
        component in normalized
        for component in ("/desktop", "/downloads", "/documents", "/temp", "/tmp", "/output")
    ):
        return "<Output Path>"
    return "<local-project-path>"


def find_portable_path_violations(
    text: str,
    *,
    field: str,
    source_path: str | None = None,
    allow_approved_fixture: bool = False,
) -> tuple[PortablePathViolation, ...]:
    """Return redacted violations without repeating the matched personal path."""

    if (
        allow_approved_fixture
        and source_path is not None
        and is_approved_tracked_fixture(source_path)
    ):
        return ()
    violations: list[PortablePathViolation] = []
    for pattern_id, pattern in _PATTERNS:
        for match in pattern.finditer(text):
            end = _path_end(text, match.start(), match.end())
            matched_value = text[match.start() : end]
            if (
                pattern_id == "linux_named_user_home"
                and (
                    matched_value.casefold() == _CONTAINER_STATION_HOME
                    or matched_value.casefold().startswith(_CONTAINER_STATION_HOME + "/")
                )
            ):
                continue
            line, column = _line_and_column(text, match.start())
            violations.append(
                PortablePathViolation(
                    field=field,
                    pattern_id=pattern_id,
                    line=line,
                    column=column,
                    start=match.start(),
                    end=end,
                    recommended_replacement=_replacement_for_match(matched_value),
                )
            )
    return tuple(sorted(violations, key=lambda item: (item.start, item.pattern_id)))


def assert_portable_publication(text: str, *, field: str) -> None:
    """Fail before publication when content contains a named-user local path."""

    violations = find_portable_path_violations(text, field=field)
    if violations:
        raise PortablePathError(violations)


def publication_diagnostics(text: str, *, field: str) -> tuple[str, ...]:
    """Return only safe, redacted diagnostics for a proposed publication field."""

    return tuple(
        item.diagnostic() for item in find_portable_path_violations(text, field=field)
    )
