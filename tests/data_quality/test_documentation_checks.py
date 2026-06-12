from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Protocol, cast


class CheckDocsModule(Protocol):
    def find_missing_files(self) -> list[str]: ...

    def find_missing_required_content(self) -> list[str]: ...

    def find_forbidden_content(self) -> list[str]: ...


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