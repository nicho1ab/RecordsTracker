from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Protocol, cast

import pytest


class CheckDocsModule(Protocol):
    def find_missing_files(self) -> list[str]: ...

    def find_missing_required_content(self) -> list[str]: ...

    def find_forbidden_content(self) -> list[str]: ...

    def find_stale_roadmap_priorities(
        self, root: Path = Path(".")
    ) -> list[str]: ...

    def find_user_specific_repository_paths(
        self, root: Path = Path("."), tracked_files: list[str] | None = None
    ) -> list[str]: ...


def _load_check_docs_module() -> CheckDocsModule:
    path = Path("scripts/check_docs.py")
    spec = importlib.util.spec_from_file_location("check_docs", path)
    if spec is None or spec.loader is None:
        raise AssertionError("Could not load scripts/check_docs.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(CheckDocsModule, module)


def test_required_accessibility_and_user_docs_exist() -> None:
    check_docs = _load_check_docs_module()

    assert check_docs.find_missing_files() == []


def test_required_public_output_guidance_is_documented() -> None:
    check_docs = _load_check_docs_module()

    assert check_docs.find_missing_required_content() == []


def test_stale_public_readme_language_is_not_present() -> None:
    check_docs = _load_check_docs_module()

    assert check_docs.find_forbidden_content() == []


def test_completed_roadmap_work_is_not_listed_as_current_priority() -> None:
    check_docs = _load_check_docs_module()

    assert check_docs.find_stale_roadmap_priorities() == []


def test_tracked_files_do_not_contain_user_specific_repository_paths() -> None:
    check_docs = _load_check_docs_module()

    assert check_docs.find_user_specific_repository_paths() == []


@pytest.mark.parametrize(
    "separator",
    ["\\", "\\\\", "/", "\\/"],
)
def test_user_specific_repository_path_variants_are_rejected(
    tmp_path: Path, separator: str
) -> None:
    check_docs = _load_check_docs_module()
    prohibited_prefix = separator.join(
        ["C:", "Users", "AnDrE", "OneDrive", "Desktop", "Repos", ""]
    )
    document = tmp_path / "example.md"
    document.write_text(
        f"Run from {prohibited_prefix}RecordsTracker{separator}scripts.\n",
        encoding="utf-8",
    )

    assert check_docs.find_user_specific_repository_paths(
        tmp_path, [document.name]
    ) == ["example.md:1"]


def test_repository_path_check_ignores_untracked_and_unrelated_windows_paths(
    tmp_path: Path,
) -> None:
    check_docs = _load_check_docs_module()
    tracked = tmp_path / "tracked.md"
    tracked.write_text(
        r"Use C:\Program Files\RecordsTracker or C:\Users\tester\RecordsTracker." + "\n",
        encoding="utf-8",
    )
    untracked = tmp_path / "generated.txt"
    prohibited_prefix = "\\".join(
        ["C:", "Users", "andre", "OneDrive", "Desktop", "Repos", ""]
    )
    untracked.write_text(prohibited_prefix + "generated", encoding="utf-8")

    assert check_docs.find_user_specific_repository_paths(
        tmp_path, [tracked.name]
    ) == []


def test_completed_review_grouping_priority_is_rejected(tmp_path: Path) -> None:
    check_docs = _load_check_docs_module()
    roadmap = tmp_path / "ROADMAP.md"
    roadmap.write_text(
        "# Roadmap\n\n"
        "## Completed CCLD proof-of-concept capabilities\n\n"
        "- Added a `review_home` Datasette saved query as a task-based "
        "start-here surface.\n\n"
        "## Current next priorities\n\n"
        "1. Group review workflows by user task rather than by implementation "
        "table.\n\n"
        "## Deferred product work\n\n"
        "- Custom frontend application.\n",
        encoding="utf-8",
    )

    expected = (
        "ROADMAP.md: Group review workflows by user task rather than by "
        "implementation table"
    )
    assert check_docs.find_stale_roadmap_priorities(tmp_path) == [expected]
