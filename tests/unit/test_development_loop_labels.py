from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
TAXONOMY_PATH = ROOT / ".github" / "development-loop-labels.json"
SCRIPT_PATH = ROOT / "scripts" / "Manage-DevelopmentLoopLabels.ps1"
REQUIRED_NAMES = {
    "codex-loop-ready",
    "risk-low",
    "risk-medium",
    "risk-high",
    "requires-product-decision",
    "requires-data-decision",
    "requires-security-review",
    "requires-manual-ui-review",
    "blocked",
}
REQUIRED_LOOP_READY_CONFLICTS = {
    "risk-high",
    "blocked",
    "requires-product-decision",
    "requires-data-decision",
    "requires-security-review",
    "needs-triage",
    "question",
    "invalid",
    "duplicate",
    "wontfix",
}


def _taxonomy() -> dict[str, Any]:
    return json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))


def _labels() -> list[dict[str, str]]:
    return _taxonomy()["labels"]


def _powershell_executable() -> str | None:
    return shutil.which("pwsh") or shutil.which("powershell")


def test_development_loop_taxonomy_has_exact_unique_labels() -> None:
    names = [label["name"] for label in _labels()]

    assert set(names) == REQUIRED_NAMES
    assert len(names) == len(set(names))


def test_development_loop_labels_have_valid_colors_and_descriptions() -> None:
    for label in _labels():
        assert re.fullmatch(r"[0-9A-F]{6}", label["color"])
        assert label["description"].strip()
        assert len(label["description"]) <= 100
        assert label["purpose"].strip()
        assert label["application_rule"].strip()
        assert label["removal_rule"].strip()


def test_codex_loop_ready_policy_is_fail_closed() -> None:
    taxonomy = _taxonomy()
    risk_policy = taxonomy["risk_policy"]
    eligibility = taxonomy["eligibility_policy"]
    authority = taxonomy["authority"]

    assert taxonomy["loop_ready_label"] == "codex-loop-ready"
    assert risk_policy["eligible_with_loop_ready"] == ["risk-low", "risk-medium"]
    assert risk_policy["exactly_one_required_with_loop_ready"] is True
    assert set(eligibility["prohibited_with_loop_ready"]) == (
        REQUIRED_LOOP_READY_CONFLICTS
    )
    assert eligibility["required_decisions_resolved"] is True
    assert set(eligibility["required_issue_contract_sections"]) == {
        "goal",
        "scope",
        "exclusions",
        "acceptance criteria",
        "validation",
        "risks",
    }
    assert eligibility["independently_testable"] is True
    assert eligibility["safely_reversible"] is True
    assert eligibility["autonomous_production_deployment_allowed"] is False
    assert eligibility["labels_are_routing_metadata_only"] is True
    assert authority["automation_may_validate"] is True
    assert authority["automation_may_apply"] is False
    assert authority["automation_may_remove"] is False
    assert authority["automation_may_override_human_removal"] is False
    assert authority["automation_may_override_blockers"] is False
    assert authority["automation_may_override_repository_governance"] is False
    assert authority["final_human_authority"] == "Andrew"
    assert authority["codex_loop_ready_apply"] == ["Andrew"]
    assert authority["codex_loop_ready_remove"] == ["Andrew"]


def test_manual_review_labels_have_documented_conditional_behavior() -> None:
    taxonomy = _taxonomy()

    assert taxonomy["eligibility_policy"]["conditional_completion_gates"] == [
        "requires-manual-ui-review",
        "needs:stakeholder-validation",
    ]
    assert "requires-manual-ui-review" not in REQUIRED_LOOP_READY_CONFLICTS


def test_label_script_constructs_idempotent_dry_run_without_deletion() -> None:
    executable = _powershell_executable()
    if executable is None:
        pytest.skip("PowerShell execution is unavailable on this runner.")

    result = subprocess.run(
        [
            executable,
            "-NoProfile",
            "-File",
            str(SCRIPT_PATH),
            "-Mode",
            "DryRun",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    plan = json.loads(result.stdout)

    assert len(plan) == len(REQUIRED_NAMES)
    assert {item["arguments"][2] for item in plan} == REQUIRED_NAMES
    for item in plan:
        arguments = item["arguments"]
        assert item["command"] == "gh"
        assert arguments[:2] == ["label", "create"]
        assert arguments[3:5] == ["--repo", "nicho1ab/RecordsTracker"]
        assert arguments[-1] == "--force"
        assert "delete" not in arguments

    script = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "gh label delete" not in script.casefold()
    assert "--delete" not in script.casefold()


def test_label_script_parses_as_powershell() -> None:
    executable = _powershell_executable()
    if executable is None:
        pytest.skip("PowerShell parsing is unavailable on this runner.")

    command = (
        "$tokens=$null; $errors=$null; "
        f"[System.Management.Automation.Language.Parser]::ParseFile('{SCRIPT_PATH}',"
        "[ref]$tokens,[ref]$errors) > $null; "
        "if($errors.Count){$errors | Format-List; exit 1}"
    )
    subprocess.run(
        [executable, "-NoProfile", "-Command", command],
        cwd=ROOT,
        check=True,
    )


def test_label_script_rejects_another_repository() -> None:
    executable = _powershell_executable()
    if executable is None:
        pytest.skip("PowerShell execution is unavailable on this runner.")

    result = subprocess.run(
        [
            executable,
            "-NoProfile",
            "-File",
            str(SCRIPT_PATH),
            "-Mode",
            "DryRun",
            "-Repository",
            "example/other-repository",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "may target only nicho1ab/RecordsTracker" in result.stderr
