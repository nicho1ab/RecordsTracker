from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path
from typing import Protocol, cast

import pytest


class CheckDocsModule(Protocol):
    def find_missing_files(self) -> list[str]: ...

    def find_missing_required_content(self) -> list[str]: ...

    def find_pull_request_template_contract_violations(
        self, root: Path = Path(".")
    ) -> list[str]: ...

    def find_forbidden_content(self) -> list[str]: ...

    def find_stale_roadmap_priorities(
        self, root: Path = Path(".")
    ) -> list[str]: ...

    def find_user_specific_repository_paths(
        self, root: Path = Path("."), tracked_files: list[str] | None = None
    ) -> list[str]: ...

    def find_reviewer_ui_governance_contract_violations(
        self, root: Path = Path(".")
    ) -> list[str]: ...

    def find_attorney_information_architecture_contract_violations(
        self, root: Path = Path(".")
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


def test_reviewer_ui_governance_contract_is_complete() -> None:
    check_docs = _load_check_docs_module()

    assert check_docs.find_reviewer_ui_governance_contract_violations() == []


REVIEWER_UI_GOVERNANCE_SECTIONS = {
    "AGENTS.md": "Reviewer-facing design enforcement",
    ".github/copilot-instructions.md": "Reviewer-facing design implementation rules",
    "DESIGN_AND_USABILITY.md": "Approved design implementation and primary-content rules",
    "ACCESSIBILITY_REQUIREMENTS.md": "Primary record inventory and disclosure accessibility",
    "TESTING_STRATEGY.md": "Reviewer UI design-conformance and source-to-screen tests",
    "docs/product/records-tracker-product-ux-lead-charter.md": "Figma and Design Handoff",
    "docs/product/records-tracker-approved-design-decisions.md": "Evidence-report format",
    "docs/planning/records-tracker-ui-ux-data-completeness-remediation-plan.md": (
        "Evidence review checklist"
    ),
    "docs/developer/ui-evidence-review.md": "Issue #479 reviewer-facing visual acceptance contract",
    "docs/developer/hosted-reviewer-acceptance.md": "Reviewer-facing visual acceptance boundary",
}


def _copy_reviewer_ui_governance_files(tmp_path: Path) -> None:
    for relative_path in REVIEWER_UI_GOVERNANCE_SECTIONS:
        target = tmp_path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(relative_path, target)


@pytest.mark.parametrize(
    ("relative_path", "heading"), REVIEWER_UI_GOVERNANCE_SECTIONS.items()
)
def test_reviewer_ui_governance_requires_each_authoritative_section(
    tmp_path: Path, relative_path: str, heading: str
) -> None:
    check_docs = _load_check_docs_module()
    _copy_reviewer_ui_governance_files(tmp_path)
    path = tmp_path / relative_path
    content = path.read_text(encoding="utf-8")
    path.write_text(content.replace(f"## {heading}", f"## Removed {heading}", 1), encoding="utf-8")

    assert (
        f"{relative_path}: expected exactly one section heading: ## {heading}"
        in check_docs.find_reviewer_ui_governance_contract_violations(tmp_path)
    )


@pytest.mark.parametrize(
    "gate_id",
    [
        "RT-UI-GATE-003",
        "RT-UI-GATE-004",
        "RT-UI-GATE-006",
        "RT-UI-GATE-007",
    ],
)
def test_reviewer_ui_governance_rejects_missing_enforcement_gate(
    tmp_path: Path, gate_id: str
) -> None:
    check_docs = _load_check_docs_module()
    _copy_reviewer_ui_governance_files(tmp_path)
    path = tmp_path / "docs/developer/ui-evidence-review.md"
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text(
        "\n".join(line for line in lines if not line.startswith(f"| `{gate_id}` |"))
        + "\n",
        encoding="utf-8",
    )

    violations = check_docs.find_reviewer_ui_governance_contract_violations(tmp_path)
    assert any("reviewer UI evidence gate IDs must be exactly" in item for item in violations)


def test_reviewer_ui_governance_requires_evidence_and_blocking_result(
    tmp_path: Path,
) -> None:
    check_docs = _load_check_docs_module()
    _copy_reviewer_ui_governance_files(tmp_path)
    path = tmp_path / "docs/developer/ui-evidence-review.md"
    lines = path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if line.startswith("| `RT-UI-GATE-005` |"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            cells[2] = ""
            cells[4] = "WARN"
            lines[index] = "| " + " | ".join(cells) + " |"
            break
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    violations = check_docs.find_reviewer_ui_governance_contract_violations(tmp_path)
    assert "RT-UI-GATE-005: required evidence cell is empty" in violations
    assert "RT-UI-GATE-005: blocking result must be BLOCK" in violations


ATTORNEY_IA_FILES = (
    "DESIGN_AND_USABILITY.md",
    "docs/planning/records-tracker-ui-ux-data-completeness-remediation-plan.md",
    "docs/product/records-tracker-approved-design-decisions.md",
    "docs/product/records-tracker-attorney-information-architecture.md",
)


def _copy_attorney_ia_files(tmp_path: Path) -> None:
    for relative_path in ATTORNEY_IA_FILES:
        target = tmp_path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(relative_path, target)


def test_attorney_information_architecture_contract_is_complete() -> None:
    check_docs = _load_check_docs_module()

    assert check_docs.find_attorney_information_architecture_contract_violations() == []


@pytest.mark.parametrize(
    ("relative_path", "heading"),
    [
        (
            "docs/product/records-tracker-attorney-information-architecture.md",
            "Route dispositions",
        ),
        (
            "DESIGN_AND_USABILITY.md",
            "Issue #501 attorney information architecture",
        ),
        (
            "docs/planning/records-tracker-ui-ux-data-completeness-remediation-plan.md",
            "Issue #501 dependent design sequence",
        ),
    ],
)
def test_attorney_information_architecture_requires_authoritative_sections(
    tmp_path: Path,
    relative_path: str,
    heading: str,
) -> None:
    check_docs = _load_check_docs_module()
    _copy_attorney_ia_files(tmp_path)
    path = tmp_path / relative_path
    content = path.read_text(encoding="utf-8")
    path.write_text(
        content.replace(f"## {heading}", f"## Removed {heading}", 1),
        encoding="utf-8",
    )

    violations = check_docs.find_attorney_information_architecture_contract_violations(
        tmp_path
    )
    assert (
        f"{relative_path}: expected exactly one section heading: ## {heading}"
        in violations
    )


def test_attorney_information_architecture_requires_canonical_route_dispositions(
    tmp_path: Path,
) -> None:
    check_docs = _load_check_docs_module()
    _copy_attorney_ia_files(tmp_path)
    path = tmp_path / "docs/product/records-tracker-attorney-information-architecture.md"
    content = path.read_text(encoding="utf-8")
    path.write_text(
        content.replace(
            "| `/ccld/facilities/review-priority` | merge |",
            "| `/ccld/facilities/review-priority` | retain |",
            1,
        ),
        encoding="utf-8",
    )

    violations = check_docs.find_attorney_information_architecture_contract_violations(
        tmp_path
    )
    assert (
        "/ccld/facilities/review-priority: expected disposition merge, found retain"
        in violations
    )


def test_attorney_information_architecture_requires_navigation_order(
    tmp_path: Path,
) -> None:
    check_docs = _load_check_docs_module()
    _copy_attorney_ia_files(tmp_path)
    path = tmp_path / "docs/product/records-tracker-attorney-information-architecture.md"
    content = path.read_text(encoding="utf-8")
    path.write_text(
        content.replace(
            "Home, Find a Facility, Compare Facilities,\nComplaint Worklist, "
            "Feedback, Help",
            "Home, Find a Facility, Complaint Worklist, Feedback, Help",
            1,
        ),
        encoding="utf-8",
    )

    violations = check_docs.find_attorney_information_architecture_contract_violations(
        tmp_path
    )
    assert any("attorney navigation order must be exactly" in item for item in violations)


def test_attorney_information_architecture_requires_design_requirement_ids(
    tmp_path: Path,
) -> None:
    check_docs = _load_check_docs_module()
    _copy_attorney_ia_files(tmp_path)
    path = tmp_path / "docs/product/records-tracker-approved-design-decisions.md"
    content = path.read_text(encoding="utf-8")
    path.write_text(
        content.replace("### RT-NAV-001 —", "### Removed RT-NAV-001 —", 1),
        encoding="utf-8",
    )

    violations = check_docs.find_attorney_information_architecture_contract_violations(
        tmp_path
    )
    assert "approved design register must define exactly one RT-NAV-001" in violations


def test_pull_request_template_contract_is_complete() -> None:
    check_docs = _load_check_docs_module()

    assert check_docs.find_pull_request_template_contract_violations() == []


def _write_pull_request_template(tmp_path: Path, content: str) -> None:
    template = tmp_path / ".github" / "PULL_REQUEST_TEMPLATE.md"
    template.parent.mkdir()
    template.write_text(content, encoding="utf-8")


def test_pull_request_template_required_sections_are_ordered(tmp_path: Path) -> None:
    check_docs = _load_check_docs_module()
    content = Path(".github/PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8")
    first = "## Governing issue and intended outcome"
    second = "## Implementation scope"
    content = content.replace(first, "## TEMP", 1).replace(second, first, 1)
    content = content.replace("## TEMP", second, 1)
    _write_pull_request_template(tmp_path, content)

    assert "required headings are out of order" in (
        check_docs.find_pull_request_template_contract_violations(tmp_path)
    )


def test_pull_request_template_keeps_ui_evidence_conditional(tmp_path: Path) -> None:
    check_docs = _load_check_docs_module()
    content = Path(".github/PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8")
    content = content.replace(
        "Complete this section only for UI or accessibility changes.",
        "Complete this section for every change.",
    )
    _write_pull_request_template(tmp_path, content)

    assert (
        "missing marker: Complete this section only for UI or accessibility changes."
        in check_docs.find_pull_request_template_contract_violations(tmp_path)
    )


@pytest.mark.parametrize(
    "marker",
    [
        "Implementation-caused failures:",
        "Pre-existing failures:",
        "Environmental failures:",
    ],
)
def test_pull_request_template_requires_each_failure_classification(
    tmp_path: Path, marker: str
) -> None:
    check_docs = _load_check_docs_module()
    content = Path(".github/PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8")
    _write_pull_request_template(tmp_path, content.replace(marker, "", 1))

    assert f"missing marker: {marker}" in (
        check_docs.find_pull_request_template_contract_violations(tmp_path)
    )


@pytest.mark.parametrize(
    "marker",
    [
        "| Schemas and migrations |",
        "| Ingestion and source-connector contracts |",
        "| Security and privacy |",
        "| Production data and correction behavior |",
        "| Deployment and infrastructure |",
        "| Repository governance |",
        "| Tests or checks weakened to obtain passage |",
        '"all tests passed" does not satisfy this review.',
    ],
)
def test_pull_request_template_requires_each_governed_boundary(
    tmp_path: Path, marker: str
) -> None:
    check_docs = _load_check_docs_module()
    content = Path(".github/PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8")
    _write_pull_request_template(tmp_path, content.replace(marker, "", 1))

    assert f"missing marker: {marker}" in (
        check_docs.find_pull_request_template_contract_violations(tmp_path)
    )


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
