from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "scripts" / "check_independent_verification.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("independent_verification", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _valid_body() -> str:
    workflow_row = (
        "| Required GitHub workflows and checks | Concern - review required | "
        "The required validate workflow is extended. |"
    )
    return f"""# Pull Request Evidence

## Governing issue and intended outcome

- Governing issue: Closes #531
- Intended outcome: Verification evidence is checked on every pull request.

## Implementation scope

- Major files or components changed: verification policy
- Important behavior intentionally left unchanged or out of scope: human approval
- Reviewer UI regression contracts: Added `RT-RC-001`; other contracts are not
  applicable to this policy-only change.

## Acceptance-criteria evidence

| Acceptance criterion | Evidence and result |
| --- | --- |
| PR evidence is verified | Focused regression passes |

## Validation and failure classification

| Exact command | Result | Failure classification, if applicable |
| --- | --- | --- |
| `pytest tests/unit/test_independent_verification.py` | Pass | none |

- Implementation-caused failures: None
- Pre-existing failures: None
- Environmental failures: None
- Tests intentionally not run and why: Full suite not run for this focused check.

## UI and accessibility evidence (when applicable)

- Evidence: Not applicable - no UI or accessibility change

## Reviewer-facing redesign artifact classification (when applicable)

- Not applicable - no reviewer-facing redesign

## Documentation, assumptions, and remaining risks

- Documentation impact: Developer workflow policy updated.
- Assumptions and limitations: Human review remains controlling.
- Remaining risks or follow-up: Advisory fresh-context review remains manual.

## Governed-boundary review

| Governed boundary | Status | Specific explanation or evidence |
| --- | --- | --- |
| Schemas and migrations | No change | No affected paths. |
| Ingestion and source-connector contracts | No change | No affected paths. |
| Security and privacy | No change | No affected paths. |
| Production data and correction behavior | No change | No affected paths. |
| Deployment and infrastructure | No change | No affected paths. |
| Repository governance | Authorized change | Verification policy is documented. |
{workflow_row}
| Tests or checks weakened to obtain passage | Authorized change | Regression coverage is added. |

## Required GitHub checks

- [ ] `validate`
- [ ] `docs-check`
- [ ] `fixtures`
- [ ] `security`
"""


VALIDATOR = _load_module()


def _governed_summary_body() -> str:
    summary = (
        "- adds objective independent verification for governing issues, PR evidence, "
        "and governed-boundary disclosures"
    )
    return f"""## Summary
{summary}

## Required checks
- validate
- docs-check
- fixtures
- security

## Verification behavior
- identifies PRs without a governing issue
- requires disclosure when governed workflow boundaries change

## Boundaries
- no branch-protection or ruleset change
- no required-check rename or removal
- no autonomous approval or merge

## Validation
- focused tests passed

Refs #531
"""


def test_valid_evidence_passes_for_required_workflow_change() -> None:
    verification = _load_module()

    assert verification.find_pr_evidence_violations(
        _valid_body(), [".github/workflows/ci.yml"]
    ) == []


def test_missing_governing_issue_fails_closed() -> None:
    verification = _load_module()

    violations = verification.find_pr_evidence_violations(
        _valid_body().replace("Closes #531", ""), []
    )

    assert "missing governing issue reference" in violations


@pytest.mark.parametrize("heading", VALIDATOR.REQUIRED_TEMPLATE_SECTIONS)
def test_each_missing_required_template_heading_fails_closed(heading: str) -> None:
    verification = _load_module()
    body = _valid_body().replace(f"## {heading}\n", "", 1)

    violations = verification.find_pr_evidence_violations(body, [])

    assert f"missing PR evidence section: {heading}" in violations


def test_duplicate_required_template_heading_fails_closed() -> None:
    verification = _load_module()
    body = _valid_body() + "\n## Required GitHub checks\n\n- duplicate\n"

    violations = verification.find_pr_evidence_violations(body, [])

    assert "duplicate PR evidence section: Required GitHub checks" in violations


@pytest.mark.parametrize(
    "value",
    (
        "",
        "<!-- List affected contracts. -->",
        "TBD",
        "N/A",
        "none",
    ),
)
def test_reviewer_contract_placeholder_or_evasive_value_fails_closed(value: str) -> None:
    verification = _load_module()
    body = _valid_body().replace(
        "Added `RT-RC-001`; other contracts are not\n  applicable to this policy-only change.",
        value,
    )

    violations = verification.find_pr_evidence_violations(body, [])

    assert any("reviewer-contract" in violation for violation in violations) or (
        "missing PR evidence field: Reviewer UI regression contracts" in violations
    )


def test_reviewer_contract_not_applicable_requires_non_reviewer_scope() -> None:
    verification = _load_module()
    body = _valid_body().replace(
        "Added `RT-RC-001`; other contracts are not\n  applicable to this policy-only change.",
        "Not applicable - this script-only change has no reviewer-facing behavior.",
    )

    assert verification.find_pr_evidence_violations(
        body, ["scripts/prepare_pr_body.py"]
    ) == []
    assert (
        "reviewer-contract disposition cannot be not applicable for reviewer scope"
        in verification.find_pr_evidence_violations(
            body, ["tests/unit/test_hosted_reviewer_ui.py"]
        )
    )


def test_governed_summary_passes_for_required_workflow_change() -> None:
    verification = _load_module()

    assert verification.find_pr_evidence_violations(
        _governed_summary_body(), [".github/workflows/ci.yml"]
    ) == []


def test_governed_summary_requires_workflow_disclosure_rule() -> None:
    verification = _load_module()
    body = _governed_summary_body().replace(
        "- requires disclosure when governed workflow boundaries change\n", ""
    )

    violations = verification.find_pr_evidence_violations(body, [".github/workflows/ci.yml"])

    assert "missing governed workflow-boundary disclosure rule" in violations


def test_changed_governed_boundary_cannot_claim_no_change() -> None:
    verification = _load_module()
    body = _valid_body().replace(
        "| Security and privacy | No change | No affected paths. |",
        "| Security and privacy | No change | No affected paths. |",
    )

    violations = verification.find_pr_evidence_violations(body, ["scripts/check_no_secrets.py"])

    assert "Security and privacy: changed files require explicit disclosure" in violations


def test_required_workflow_change_requires_human_review_status() -> None:
    verification = _load_module()
    body = _valid_body().replace(
        "| Required GitHub workflows and checks | Concern - review required |",
        "| Required GitHub workflows and checks | Authorized change |",
    )

    violations = verification.find_pr_evidence_violations(body, [".github/workflows/ci.yml"])

    assert (
        "Required GitHub workflows and checks: changes require Concern - review required"
        in violations
    )


def test_required_workflow_contract_rejects_test_skip_controls(tmp_path: Path) -> None:
    verification = _load_module()
    workflow = tmp_path / ".github/workflows/ci.yml"
    workflow.parent.mkdir(parents=True)
    source = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    workflow.write_text(source + "\n      continue-on-error: true\n", encoding="utf-8")
    for relative_path in (
        ".github/workflows/docs-check.yml",
        ".github/workflows/regression.yml",
        ".github/workflows/security.yml",
    ):
        destination = tmp_path / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text((ROOT / relative_path).read_text(encoding="utf-8"), encoding="utf-8")

    violations = verification.find_workflow_contract_violations(tmp_path)

    assert ".github/workflows/ci.yml: continue-on-error: true is not permitted" in violations


def test_cli_reads_event_and_prints_verification_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    verification = _load_module()
    event_path = tmp_path / "event.json"
    changed_files = tmp_path / "changed-files.txt"
    event_path.write_text(json.dumps({"pull_request": {"body": _valid_body()}}), encoding="utf-8")
    changed_files.write_text(".github/workflows/ci.yml\n", encoding="utf-8")

    assert verification.main(
        [
            "--repo-root",
            str(ROOT),
            "--event-path",
            str(event_path),
            "--changed-files",
            str(changed_files),
        ]
    ) == 0

    output = capsys.readouterr().out
    assert "Independent verification summary" in output
    assert "- Governing issue: #531" in output


def test_cli_reads_current_pr_body_instead_of_stale_event(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    verification = _load_module()
    body_path = tmp_path / "current-pr-body.md"
    changed_files = tmp_path / "changed-files.txt"
    body_path.write_text(_valid_body(), encoding="utf-8")
    changed_files.write_text(".github/workflows/ci.yml\n", encoding="utf-8")

    assert verification.main(
        [
            "--repo-root",
            str(ROOT),
            "--pr-body",
            str(body_path),
            "--changed-files",
            str(changed_files),
        ]
    ) == 0

    assert "Independent verification summary" in capsys.readouterr().out


def test_cli_reports_live_body_read_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    verification = _load_module()
    changed_files = tmp_path / "changed-files.txt"
    changed_files.write_text(".github/workflows/ci.yml\n", encoding="utf-8")

    assert verification.main(
        [
            "--repo-root",
            str(ROOT),
            "--pr-body",
            str(tmp_path / "missing-body.md"),
            "--changed-files",
            str(changed_files),
        ]
    ) == 1

    assert "cannot read pull-request body:" in capsys.readouterr().out


def test_cli_preserves_multiline_special_character_live_body(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    verification = _load_module()
    body_path = tmp_path / "current-pr-body.md"
    changed_files = tmp_path / "changed-files.txt"
    body_path.write_text(
        _valid_body().replace(
            "Developer workflow policy updated.",
            "Developer workflow policy updated for review & audit.\n\nAdditional context: <safe>. ",
        ),
        encoding="utf-8",
    )
    changed_files.write_text(".github/workflows/ci.yml\n", encoding="utf-8")

    assert verification.main(
        [
            "--repo-root",
            str(ROOT),
            "--pr-body",
            str(body_path),
            "--changed-files",
            str(changed_files),
        ]
    ) == 0
    assert "Independent verification summary" in capsys.readouterr().out


def test_template_headings_match_the_validator_contract() -> None:
    verification = _load_module()
    template = (ROOT / ".github/PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8")

    assert [line[3:] for line in template.splitlines() if line.startswith("## ")] == list(
        verification.REQUIRED_TEMPLATE_SECTIONS
    )


def test_ci_fetches_live_pr_body_before_validation() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "--jq '.body' > .verification-pr-body.md" in workflow
    assert "--pr-body .verification-pr-body.md" in workflow
    assert '--event-path "$GITHUB_EVENT_PATH"' not in workflow
    assert "contents: read" in workflow
    assert "pull-requests: read" in workflow
    assert "set -euo pipefail" in workflow
    assert "write" not in workflow.partition("jobs:")[0]


def test_ci_runs_validation_for_pull_request_edits_without_write_permissions() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "types: [opened, reopened, synchronize, edited]" in workflow
    assert "contents: read" in workflow
    assert "pull-requests: read" in workflow
    assert "pull-requests: write" not in workflow
    assert "validate:" in workflow


def test_changed_governed_boundary_normalizes_windows_paths() -> None:
    verification = _load_module()

    assert verification.changed_governed_boundaries([".github\\workflows\\ci.yml"]) == {
        "Required GitHub workflows and checks": [".github/workflows/ci.yml"]
    }
