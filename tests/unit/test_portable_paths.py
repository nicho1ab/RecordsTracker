from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

from ccld_complaints.portable_paths import (
    PortablePathError,
    assert_portable_publication,
    find_portable_path_violations,
    publication_diagnostics,
)

ROOT = Path(__file__).resolve().parents[2]


def _load_script(name: str, relative_path: str) -> ModuleType:
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _windows(*parts: str, separator: str = "\\", drive: str = "C") -> str:
    return separator.join((f"{drive}:", "Users", *parts))


@pytest.mark.parametrize("separator", ["\\", "\\\\", "/", "\\/"])
@pytest.mark.parametrize("drive", ["C", "c", "D", "e"])
def test_windows_named_user_profile_variants_are_rejected(
    separator: str, drive: str
) -> None:
    value = _windows(
        "synthetic-user",
        "OneDrive",
        "Repositories",
        "RecordsTracker",
        "report.json",
        separator=separator,
        drive=drive,
    )

    violations = find_portable_path_violations(value, field="issue body")

    assert [item.pattern_id for item in violations] == ["windows_named_user_profile"]
    assert violations[0].recommended_replacement == "<Repo Path>"


@pytest.mark.parametrize(
    "prefix,pattern_id",
    [
        (("Users", "synthetic-user"), "macos_named_user_home"),
        (("home", "synthetic-user"), "linux_named_user_home"),
        (("var", "home", "synthetic-user"), "linux_named_user_home"),
        (("export", "home", "synthetic-user"), "linux_named_user_home"),
    ],
)
def test_unix_named_user_homes_are_rejected(
    prefix: tuple[str, ...], pattern_id: str
) -> None:
    value = "/" + "/".join((*prefix, "projects", "Records Tracker", "report.json"))

    violations = find_portable_path_violations(value, field="completion report")

    assert [item.pattern_id for item in violations] == [pattern_id]


@pytest.mark.parametrize(
    "wrapper",
    [
        lambda value: json.dumps({"path": value}),
        lambda value: f'path: "{value}"',
        lambda value: f"`{value}`",
        lambda value: repr(value),
        lambda value: f"$Path = '{value}'",
    ],
)
def test_json_yaml_markdown_python_and_powershell_forms_are_rejected(wrapper) -> None:
    value = _windows("another-user", "Documents", "Records Tracker", "result.json")

    assert find_portable_path_violations(wrapper(value), field="generated report")


def test_generic_username_and_spaces_are_detected_without_username_allowlist() -> None:
    value = _windows("name not tied to repository owner", "Desktop", "Output File.json")

    violation = find_portable_path_violations(value, field="evidence summary")[0]

    assert violation.pattern_id == "windows_named_user_profile"
    assert violation.recommended_replacement == "<Output Path>"


@pytest.mark.parametrize(
    "value",
    [
        "<Repo Path>/scripts/check_docs.py",
        "<Evidence Path>/manifest.json",
        "<Output Path>/report.json",
        "<User-Accessible Output Path>/report.json",
        "<repo-root>/scripts/check_docs.py",
        "<local-project-path>/output/report.json",
        "docs/developer/codex-workflow.md",
        "scripts/check_docs.py",
        "https://api.github.com/repos/nicho1ab/RecordsTracker/issues/632",
        "/repos/nicho1ab/RecordsTracker/issues/632",
        "C:/Program Files/RecordsTracker",
        "/Users/Shared/RecordsTracker",
    ],
)
def test_portable_placeholders_relative_paths_and_public_urls_are_allowed(value: str) -> None:
    assert find_portable_path_violations(value, field="publication") == ()


def test_only_the_exact_approved_detection_fixture_is_exempt_from_tracked_scan() -> None:
    fixture_path = ROOT / "tests/fixtures/portable_paths/detection-cases.json"
    content = fixture_path.read_text(encoding="utf-8")

    assert find_portable_path_violations(content, field=fixture_path.as_posix())
    assert (
        find_portable_path_violations(
            content,
            field=fixture_path.as_posix(),
            source_path="tests/fixtures/portable_paths/detection-cases.json",
            allow_approved_fixture=True,
        )
        == ()
    )
    assert find_portable_path_violations(
        content,
        field=fixture_path.as_posix(),
        source_path="tests/fixtures/portable_paths/other.json",
        allow_approved_fixture=True,
    )


def test_publication_failure_is_actionable_and_redacted() -> None:
    value = _windows("private-name", "Desktop", "evidence", "manifest.json")

    with pytest.raises(PortablePathError) as captured:
        assert_portable_publication(value, field="issue comment")

    message = str(captured.value)
    assert "issue comment:1:1" in message
    assert "windows_named_user_profile" in message
    assert "<Evidence Path>" in message
    assert "private-name" not in message
    assert value not in message


@pytest.mark.parametrize(
    "field",
    [
        "issue body",
        "issue comment",
        "pull-request body",
        "pull-request comment",
        "completion comment",
        "evidence summary",
        "completion report",
    ],
)
def test_every_publication_field_uses_the_same_contract(field: str) -> None:
    value = "/" + "/".join(("home", "synthetic-user", "result.json"))

    diagnostics = publication_diagnostics(value, field=field)

    assert diagnostics and diagnostics[0].startswith(f"{field}:1:1:")


def test_tracked_scanner_pr_lifecycle_and_ci_use_the_authoritative_module() -> None:
    check_docs = (ROOT / "scripts/check_docs.py").read_text(encoding="utf-8")
    independent = (ROOT / "scripts/check_independent_verification.py").read_text(
        encoding="utf-8"
    )
    security = (ROOT / ".github/workflows/security.yml").read_text(encoding="utf-8")

    assert "from ccld_complaints.portable_paths import" in check_docs
    assert "from ccld_complaints.portable_paths import publication_diagnostics" in independent
    assert "python scripts/audit_portable_paths.py tracked" in security


def test_pr_body_preflight_rejects_path_before_lifecycle_mutation() -> None:
    verification = _load_script(
        "portable_path_independent_verification",
        "scripts/check_independent_verification.py",
    )
    body = (
        (ROOT / "tests/fixtures/pr_body_validation/pr-615-full-template.md")
        .read_text(encoding="utf-8")
        + "\n"
        + _windows("synthetic-user", "Desktop", "evidence", "result.json")
    )

    violations = verification.validate_pr_evidence(
        ROOT, body, ["scripts/prepare_pr_body.py"]
    ).violations

    assert any("windows_named_user_profile" in value for value in violations)
