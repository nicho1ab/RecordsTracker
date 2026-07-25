from __future__ import annotations

import importlib.util
from pathlib import Path
from subprocess import CompletedProcess
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "scripts" / "prepare_pr_body.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("prepare_pr_body", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _completed_body() -> str:
    template = (ROOT / ".github/PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8")
    replacements = (
        ("<!-- Example: Closes #123 -->", "Closes #608"),
        (
            "- Intended outcome:",
            "- Intended outcome: Preflight catches invalid PR evidence.",
        ),
        (
            "- Major files or components changed:",
            "- Major files or components changed: verification tooling",
        ),
        (
            "- Important behavior intentionally left unchanged or out of scope:",
            "- Important behavior intentionally left unchanged or out of scope: human approval",
        ),
        (
            "- Reviewer UI regression contracts: <!-- List affected, added, updated, "
            "superseded, or Not applicable - <specific reason>. -->",
            "- Reviewer UI regression contracts: Added `RT-RC-001`; remaining "
            "contracts are not applicable - verification tooling only.",
        ),
        (
            "| <!-- One criterion per row --> | <!-- Test, diff, review artifact, "
            "or other concrete result --> |",
            "| PR body is preflighted | Focused validator test passes |",
        ),
        (
            "| `<!-- command -->` | <!-- Pass, fail, or not run --> | "
            "<!-- Implementation-caused, pre-existing, environmental, or none --> |",
            "| `pytest tests/unit/test_prepare_pr_body.py` | Pass | none |",
        ),
        ("<!-- None, or command and disposition -->", "None"),
        ("<!-- None, or command and evidence that it predates this change -->", "None"),
        ("<!-- None, or command and environment limitation -->", "None"),
        (
            "- Tests intentionally not run and why:",
            "- Tests intentionally not run and why: Full suite not run for this focused test.",
        ),
        (
            "<!-- Updated docs, or why no user-facing or documentation-impacting "
            "behavior changed -->",
            "Developer workflow guidance updated.",
        ),
        (
            "- Assumptions and limitations:",
            "- Assumptions and limitations: Human review remains controlling.",
        ),
        (
            "- Remaining risks or follow-up:",
            "- Remaining risks or follow-up: Required GitHub checks remain authoritative.",
        ),
    )
    completed = template
    for old, new in replacements:
        completed = completed.replace(old, new)
    for boundary in (
        "Schemas and migrations",
        "Ingestion and source-connector contracts",
        "Security and privacy",
        "Production data and correction behavior",
        "Deployment and infrastructure",
        "Repository governance",
        "Required GitHub workflows and checks",
        "Tests or checks weakened to obtain passage",
    ):
        completed = completed.replace(
            f"| {boundary} |  |  |",
            f"| {boundary} | Authorized change | Focused Issue #608 contract evidence. |",
        )
    return completed


def test_render_copies_the_authoritative_template(tmp_path: Path) -> None:
    prepare = _load_module()
    output = tmp_path / "body.md"

    assert prepare.render_body(output) == 0
    template = (ROOT / ".github/PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8")
    assert output.read_text(encoding="utf-8") == template


def test_preflight_uses_validator_rules_and_actionable_failures(tmp_path: Path, capsys) -> None:
    prepare = _load_module()
    body = tmp_path / "body.md"
    changed = tmp_path / "changed.txt"
    body.write_text(_completed_body(), encoding="utf-8")
    changed.write_text(".github/workflows/ci.yml\n", encoding="utf-8")

    assert prepare.preflight_body(
        body_path=body,
        changed_files_path=changed,
        base="origin/main",
        repo_root=ROOT,
    ) == 1
    failure_message = (
        "Required GitHub workflows and checks: changes require Concern - review required"
    )
    assert failure_message in capsys.readouterr().out

    body.write_text(
        _completed_body().replace(
            "| Required GitHub workflows and checks | Authorized change | "
            "Focused Issue #608 contract evidence. |",
            "| Required GitHub workflows and checks | Concern - review required | "
            "Required validation changes are reviewed. |",
        ),
        encoding="utf-8",
    )
    assert prepare.preflight_body(
        body_path=body,
        changed_files_path=changed,
        base="origin/main",
        repo_root=ROOT,
    ) == 0
    assert "Independent verification passed." in capsys.readouterr().out


def test_automatic_changed_file_discovery_includes_untracked_files(monkeypatch) -> None:
    prepare = _load_module()
    commands: list[tuple[str, ...]] = []
    outputs = iter(
        (
            "committed.py\nrenamed.py\ndeleted.py\nshared.py\n",
            "unstaged.py\nshared.py\n",
            "staged.py\nshared.py\n",
            "untracked.py\n",
        )
    )

    def fake_run(command, **_kwargs):
        commands.append(command)
        output = next(outputs)
        return CompletedProcess(command, 0, stdout=output)

    monkeypatch.setattr(prepare.subprocess, "run", fake_run)

    discovered = prepare._changed_files_from_git("origin/main")

    assert discovered == [
        "committed.py",
        "renamed.py",
        "deleted.py",
        "shared.py",
        "unstaged.py",
        "staged.py",
        "untracked.py",
    ]
    assert ("git", "ls-files", "--others", "--exclude-standard") in commands
    assert "ignored.tmp" not in discovered


def test_pr_preparation_guidance_does_not_claim_open_pr_repair() -> None:
    guidance_paths = (
        ROOT / "AGENTS.md",
        ROOT / ".github" / "copilot-instructions.md",
        ROOT / "CONTRIBUTING.md",
        ROOT / "docs" / "developer" / "codex-workflow.md",
    )
    guidance = "\n".join(path.read_text(encoding="utf-8") for path in guidance_paths)

    assert "creating or repairing a PR body" not in guidance
    assert "open-PR repair remains deferred" in guidance
    assert "freeform PR body cannot substitute" in guidance
